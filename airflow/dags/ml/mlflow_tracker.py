# ml/mlflow_tracker.py
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
import os
from datetime import datetime
import json
import logging
import numpy as np

from airflow.models import Variable

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class MLflowTracker:
    """
    Gerenciador de experimentos MLflow que usa PostgreSQL como backend store
    e espera que o Artifact Root (GCS) seja configurado via variável de ambiente.
    """

    def __init__(self, experiment_name="question_recommendation"):
        """
        Inicializa o tracker MLflow
        
        Args:
            experiment_name: Nome do experimento
        """
        mlflow.set_tracking_uri("http://136.113.82.244:5000/")

        try:
            self.experiment_id = mlflow.create_experiment(experiment_name)
        except Exception:
            self.experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id

        mlflow.set_experiment(experiment_name)
        self.client = MlflowClient()

        logger.info(f"MLflow configurado, Experimento ID: {self.experiment_id}")

    def start_training_run(self, run_name=None, tags=None):
        if run_name is None:
            run_name = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        default_tags = {
            'model_type': 'question_recommendation',
            'timestamp': datetime.now().isoformat()
        }

        if tags:
            default_tags.update(tags)

        run = mlflow.start_run(run_name=run_name, tags=default_tags)
        logger.info(f"Run iniciada: {run.info.run_id}")
        return run

    def log_training_metrics(self, metrics: dict):
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        logger.info(f"Métricas registradas: {metrics}")

    def log_hyperparameters(self, params: dict):
        for key, value in params.items():
            mlflow.log_param(key, value)
        logger.info(f"Parâmetros registrados: {params}")

    def log_dataset_info(self, dataset_stats: dict):
        mlflow.log_dict(dataset_stats, "dataset_info.json")
        logger.info(f"Informações do dataset registradas")

    def log_model(self, model, model_name="recommendation_model"):
        """
        Salva o modelo treinado. O artefato será salvo no GCS (Artifact Root)
        e os metadados (URI do GCS) no PostgreSQL.
        """
        mlflow.sklearn.log_model(
            sk_model=model,
            name=model_name,
            registered_model_name=model_name
        )
        logger.info(f"Modelo registrado no PostgreSQL/GCS: {model_name}")

    def end_run(self):
        mlflow.end_run()
        logger.info("Run finalizada")
        

def evaluate_recommendation_quality(recommendations, ground_truth):
    if not recommendations or not ground_truth:
        return {}

    # Mean Reciprocal Rank (MRR)
    mrr = 0
    for i, rec in enumerate(recommendations):
        if rec in ground_truth:
            mrr = 1 / (i + 1)
            break

    # Precision@K
    k = min(5, len(recommendations))
    precision_at_k = len(set(recommendations[:k]) & set(ground_truth)) / k

    # Recall@K
    recall_at_k = len(set(recommendations[:k]) & set(ground_truth)) / len(ground_truth)

    # F1-Score
    if precision_at_k + recall_at_k > 0:
        f1_score = 2 * (precision_at_k * recall_at_k) / (precision_at_k + recall_at_k)
    else:
        f1_score = 0

    # NDCG (Normalized Discounted Cumulative Gain)
    idcg = sum([1 / np.log2(i + 2) for i in range(min(k, len(ground_truth)))])
    
    if idcg > 0:
        dcg = sum([1 / np.log2(i + 2) if rec in ground_truth else 0
               for i, rec in enumerate(recommendations[:k])])
        ndcg = dcg / idcg
    else:
        ndcg = 0


    return {
        'mean_reciprocal_rank': mrr,
        'precision_at_5': precision_at_k,
        'recall_at_5': recall_at_k,
        'f1_score': f1_score,
        'ndcg': ndcg
    }