"""
Django management command para carregar questões dos arquivos .txt
Uso: python manage.py load_questions
"""
import os
import re
from django.core.management.base import BaseCommand
from concursoapp.models import Question, Choice


class Command(BaseCommand):
    help = 'Carrega questões dos arquivos .txt do diretório Txts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpa todas as questões existentes antes de importar',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Limpando questões existentes...'))
            Question.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Questões removidas!'))

        # Caminho para o diretório Txts
        # Tentar primeiro application/Txts, depois Txts na raiz
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        txts_dir = os.path.join(base_dir, 'application', 'Txts')

        if not os.path.exists(txts_dir):
            # Tentar na raiz do projeto
            txts_dir = os.path.join(base_dir, 'Txts')
            if not os.path.exists(txts_dir):
                self.stdout.write(self.style.ERROR(f'Diretório não encontrado: {txts_dir}'))
                return

        self.stdout.write(f'Lendo arquivos de: {txts_dir}')

        # Encontrar todos os arquivos de perguntas (-p.txt)
        question_files = [f for f in os.listdir(txts_dir) if f.endswith('-p.txt')]

        total_questions = 0
        total_files = 0

        for q_file in question_files:
            # Arquivo correspondente de respostas
            r_file = q_file.replace('-p.txt', '-r.txt')
            q_path = os.path.join(txts_dir, q_file)
            r_path = os.path.join(txts_dir, r_file)

            if not os.path.exists(r_path):
                self.stdout.write(self.style.WARNING(f'Arquivo de respostas não encontrado: {r_file}'))
                continue

            # Extrair o assunto do nome do arquivo
            # Ex: "Aula 10 constitucional - Poder legislativo-p.txt"
            subject = self.extract_subject(q_file)

            # Parse das questões e respostas
            questions = self.parse_questions(q_path)
            answers = self.parse_answers(r_path)

            if len(questions) != len(answers):
                self.stdout.write(self.style.WARNING(
                    f'Número de questões ({len(questions)}) != respostas ({len(answers)}) em {q_file}'
                ))
                continue

            # Criar questões no banco
            for i, (q_number, q_text, choices) in enumerate(questions):
                try:
                    correct_answer = answers[i]

                    # Criar questão
                    question = Question.objects.create(
                        subject=subject,
                        text=q_text,
                        source_file=q_file
                    )

                    # Criar alternativas
                    for letter, choice_text in choices:
                        is_correct = (letter == correct_answer)
                        Choice.objects.create(
                            question=question,
                            text=choice_text,
                            is_correct=is_correct
                        )

                    total_questions += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Erro ao criar questão {q_number} de {q_file}: {e}'))

            total_files += 1
            self.stdout.write(self.style.SUCCESS(f'✓ {q_file}: {len(questions)} questões importadas'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Total: {total_questions} questões de {total_files} arquivos'))

    def extract_subject(self, filename):
        """Extrai o assunto do nome do arquivo"""
        # Remove a extensão -p.txt
        name = filename.replace('-p.txt', '')

        # Tenta extrair o padrão "Aula X constitucional - Assunto"
        match = re.search(r'constitucional - (.+)', name)
        if match:
            return match.group(1).strip()

        return name

    def parse_questions(self, filepath):
        """Parse do arquivo de questões"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        questions = []

        # Limpar caracteres especiais unicode (zero-width space, etc)
        content = re.sub(r'[\u200b\u200c\u200d\ufeff​]', '', content)

        # Split por números seguidos de ponto (aceita vários formatos)
        # Padrões: "1." no início de linha, com ou sem espaços/quebras
        question_blocks = re.split(r'(?:^|\n)(\d+)\.\s*', content, flags=re.MULTILINE)

        # Remove o primeiro elemento vazio se existir
        if question_blocks and not question_blocks[0].strip():
            question_blocks = question_blocks[1:]

        # Processa em pares (número, conteúdo)
        for i in range(0, len(question_blocks) - 1, 2):
            q_number = question_blocks[i].strip()
            q_content = question_blocks[i + 1].strip()

            if not q_content:
                continue

            # Separar o texto da questão das alternativas
            # Alternativas começam com a), b), c), d), e)
            lines = q_content.split('\n')
            question_text_lines = []
            choices = []
            current_choice_letter = None
            current_choice_text = []

            for line in lines:
                line = line.strip()

                # Verifica se é uma alternativa (a), b), c), etc)
                choice_match = re.match(r'^([a-e])\)\s*(.+)', line)

                if choice_match:
                    # Se já tínhamos uma alternativa sendo processada, salva ela
                    if current_choice_letter:
                        choices.append((current_choice_letter, ' '.join(current_choice_text).strip()))

                    # Inicia nova alternativa
                    current_choice_letter = choice_match.group(1).upper()
                    current_choice_text = [choice_match.group(2)]
                elif current_choice_letter:
                    # Continua a alternativa atual
                    current_choice_text.append(line)
                else:
                    # É parte do texto da questão
                    question_text_lines.append(line)

            # Salva a última alternativa
            if current_choice_letter:
                choices.append((current_choice_letter, ' '.join(current_choice_text).strip()))

            question_text = ' '.join(question_text_lines).strip()

            if question_text and len(choices) >= 2:
                questions.append((q_number, question_text, choices))

        return questions

    def parse_answers(self, filepath):
        """Parse do arquivo de respostas"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        answers = []
        # Padrão: "1. LETRA A" ou "1. A"
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Extrai a letra da resposta
            match = re.search(r'LETRA\s+([A-E])|^\d+\.\s*([A-E])', line)
            if match:
                letter = match.group(1) or match.group(2)
                answers.append(letter)

        return answers
