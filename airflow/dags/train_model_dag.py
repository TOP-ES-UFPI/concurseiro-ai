from airflow.decorators import dag
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy import create_engine
from airflow.models.param import Param
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from google.cloud import storage

from ml.train_tasks import train_clustering_model


def get_connection():
    hook = PostgresHook(postgres_conn_id="concuroia_conn_id")
    engine = hook.get_sqlalchemy_engine()
    return engine
    

@dag(
    dag_id="train_model_dag",
    start_date=None,
    schedule_interval=None,
    catchup=False,
    tags=["mlflow", "ml", "train"],
    params={
        "n_clusters": Param(
            default=3,
            description="Número de clusters para o modelo de clustering (inteiro)",
            type="integer",
        ),
    },
)
def train_model_pipeline():

    @task
    def train_clusters(params: dict):
        n_clusters = params.get("n_clusters")
        engine = get_connection()
        train_clustering_model(engine, n_clusters)


    train_clusters()
    
dag = train_model_pipeline()
