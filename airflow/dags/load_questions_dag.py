from airflow.decorators import dag
from airflow.decorators import task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import text


def get_connection():
    return create_engine("sqlite:/home/jelson/Projetos/concurseiro-ai/application/db.sqlite3")

@dag(
    dag_id="question_data_loader_pipeline",
    start_date=NotImplemented,
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
        pass
