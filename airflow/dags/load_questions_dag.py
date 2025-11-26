from airflow.decorators import dag
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from google.cloud import storage
import re


BUCKET_NAME = "data-questions"


def get_connection():
    hook = PostgresHook(postgres_conn_id="concuroia_conn_id")
    engine = hook.get_sqlalchemy_engine()
    return engine

def list_question_files(bucket_name: str, prefix: str):
    """
    Lista todos os arquivos de perguntas (-p.txt) no bucket/prefix.
    Ex.: data-v1/minhas-questoes-p.txt
    """
    client = storage.Client()
    blobs = client.list_blobs(bucket_name, prefix=prefix)

    question_files = []
    for blob in blobs:
        name = blob.name
        if not name.endswith('-p.txt'):
            continue
        question_files.append(name)
    return question_files


def read_gcs_file(bucket_name: str, blob_name: str) -> str:
    """
    Lê o conteúdo de um arquivo de texto no GCS e retorna como string.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text(encoding='utf-8')


def extract_subject(filename: str) -> str:
    """
    Extrai o assunto do nome do arquivo (apenas o nome, sem o prefixo/pasta).
    Ex: "data-v1/Aula 10 constitucional - Poder legislativo-p.txt"
    """
    base_name = filename.split('/')[-1]
    name = base_name.replace('-p.txt', '')
    match = re.search(r'constitucional - (.+)', name, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return name


def parse_questions(content: str):
    """
    Parse do conteúdo de questões (string do arquivo -p.txt).
    Retorna lista de tuplas:
    (q_number, question_text, choices)
    choices: lista de tuplas (letter, text)
    """
    content = re.sub(r'[\u200b\u200c\u200d\ufeff​]', '', content)
    question_blocks = re.split(r'(?:^|\n)(\d+)\.\s*', content, flags=re.MULTILINE)

    if question_blocks and not question_blocks[0].strip():
        question_blocks = question_blocks[1:]

    questions = []

    for i in range(0, len(question_blocks) - 1, 2):
        q_number = question_blocks[i].strip()
        q_content = question_blocks[i + 1].strip()

        if not q_content:
            continue

        lines = q_content.split('\n')
        question_text_lines = []
        choices = []
        current_choice_letter = None
        current_choice_text = []

        for line in lines:
            line = line.strip()

            choice_match = re.match(r'^([a-e])\)\s*(.+)', line, flags=re.IGNORECASE)

            if choice_match:
                if current_choice_letter:
                    choices.append(
                        (current_choice_letter, ' '.join(current_choice_text).strip())
                    )

                current_choice_letter = choice_match.group(1).upper()
                current_choice_text = [choice_match.group(2)]
            elif current_choice_letter:
                current_choice_text.append(line)
            else:
                question_text_lines.append(line)

        if current_choice_letter:
            choices.append(
                (current_choice_letter, ' '.join(current_choice_text).strip())
            )

        question_text = ' '.join(question_text_lines).strip()

        if question_text and len(choices) >= 2:
            questions.append((q_number, question_text, choices))

    return questions


def parse_answers(content: str):
    """
    Parse do conteúdo de respostas (string do arquivo -r.txt).
    Retorna lista com as letras corretas na ordem das questões.
    """
    answers = []

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Padrão: "1. LETRA A" ou "1. A"
        match = re.search(r'LETRA\s+([A-E])|^\d+\.\s*([A-E])', line, flags=re.IGNORECASE)
        if match:
            letter = match.group(1) or match.group(2)
            answers.append(letter.upper())

    return answers


def insert_question(conn, subject: str, text_q: str, source_file: str):
    """
    Insere uma questão na tabela questions e retorna o id gerado.
    """
    sql = text("""
        INSERT INTO questions (subject, text, source_file)
        VALUES (:subject, :text, :source_file)
        RETURNING id
    """)
    result = conn.execute(sql, {
        "subject": subject,
        "text": text_q,
        "source_file": source_file,
    })
    row = result.fetchone()
    return row[0]


def insert_choice(conn, question_id: int, choice_text: str, is_correct: bool):
    """
    Insere uma alternativa na tabela choices.
    """
    sql = text("""
        INSERT INTO choices (question_id, text, is_correct)
        VALUES (:question_id, :text, :is_correct)
    """)
    conn.execute(sql, {
        "question_id": question_id,
        "text": choice_text,
        "is_correct": is_correct,
    })
    

@dag(
    dag_id="question_data_loader_pipeline",
    start_date=None,
    schedule_interval=None,
    catchup=False,
    tags=["etl", "data_load"],
)
def question_loader_etl():

    @task
    def remove_old_questions():
        engine = get_connection()
        with Session(engine) as session:
            session.execute(text("DELETE FROM question"))
            session.commit()
    
    @task
    def load_questions():
        engine = get_connection()
        prefix = "data-v1/"
        bucket_name = BUCKET_NAME
        question_files = list_question_files(bucket_name, prefix)

        if not question_files:
            return FileNotFoundError("Nenhum arquivo de questão encontrado no bucket.")
        
        total_questions = 0
        total_files = 0

        with engine.begin() as conn:
            for q_blob_name in question_files:
                r_blob_name = q_blob_name.replace('-p.txt', '-r.txt')

                try:
                    answers_content = read_gcs_file(bucket_name, r_blob_name)
                except Exception:
                    print(f"Arquivo de respostas não encontrado no bucket: {r_blob_name}")
                    continue

                subject = extract_subject(q_blob_name)
                questions_content = read_gcs_file(bucket_name, q_blob_name)
                questions = parse_questions(questions_content)
                answers = parse_answers(answers_content)

                if len(questions) != len(answers):
                    print(f"Número de questões ({len(questions)}) != respostas ({len(answers)}) em {q_blob_name}")
                    continue

                for i, (q_number, q_text, choices) in enumerate(questions):
                    try:
                        correct_answer = answers[i]
                        question_id = insert_question(conn, subject, q_text, q_blob_name)
                        for letter, choice_text in choices:
                            is_correct = (letter.upper() == correct_answer.upper())
                            insert_choice(conn, question_id, choice_text, is_correct)

                        total_questions += 1

                    except Exception as e:
                        print(f"Erro ao criar questão {q_number} de {q_blob_name}: {e}")

                total_files += 1
                print(f"✓ {q_blob_name}: {len(questions)} questões importadas")

        print(f"\n✓ Total: {total_questions} questões de {total_files} arquivos")


    remove_old_questions() >> load_questions()

dag = question_loader_etl()
