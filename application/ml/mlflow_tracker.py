"""
Integração com MLflow para tracking de experimentos e versionamento de modelos
"""
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
import os
from datetime import datetime
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)


class MLflowTracker:
    """Gerenciador de experimentos MLflow para o sistema de recomendação"""

    def __init__(self, tracking_uri=None, experiment_name="question_recommendation"):
        """
        Inicializa o tracker MLflow

        Args:
            tracking_uri: URI do servidor MLflow (None = local)
            experiment_name: Nome do experimento
        """
        # Configurar URI de tracking
        if tracking_uri is None:
            # Por padrão, salva localmente em mlruns/
            mlflow_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'mlruns'
            )
            os.makedirs(mlflow_dir, exist_ok=True)
            # Converter para URI file:/// com barras corretas (funciona no Windows)
            tracking_uri = mlflow_dir.replace('\\', '/')
            if not tracking_uri.startswith('file:'):
                tracking_uri = f"file:///{tracking_uri}"

        mlflow.set_tracking_uri(tracking_uri)

        # Criar ou obter experimento
        try:
            self.experiment_id = mlflow.create_experiment(experiment_name)
        except Exception:
            self.experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id

        mlflow.set_experiment(experiment_name)

        self.client = MlflowClient()

        logger.info(f"MLflow configurado: {tracking_uri}, experimento: {experiment_name}")

    def start_training_run(self, run_name=None, tags=None):
        """
        Inicia uma nova run de treinamento

        Args:
            run_name: Nome da run
            tags: Dict com tags adicionais

        Returns:
            Run ativa
        """
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
        """
        Registra métricas de treinamento

        Args:
            metrics: Dict com métricas (ex: {'accuracy': 0.85, 'precision': 0.80})
        """
        for key, value in metrics.items():
            mlflow.log_metric(key, value)

        logger.info(f"Métricas registradas: {metrics}")

    def log_hyperparameters(self, params: dict):
        """
        Registra hiperparâmetros do modelo

        Args:
            params: Dict com parâmetros
        """
        for key, value in params.items():
            mlflow.log_param(key, value)

        logger.info(f"Parâmetros registrados: {params}")

    def log_dataset_info(self, dataset_stats: dict):
        """
        Registra informações sobre o dataset de treinamento

        Args:
            dataset_stats: Dict com estatísticas do dataset
        """
        mlflow.log_dict(dataset_stats, "dataset_info.json")

        logger.info(f"Informações do dataset registradas")

    def log_model(self, model, model_name="recommendation_model"):
        """
        Salva o modelo treinado

        Args:
            model: Objeto do modelo
            model_name: Nome do artefato
        """
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path=model_name,
            registered_model_name=model_name
        )

        logger.info(f"Modelo registrado: {model_name}")

    def log_confusion_matrix(self, y_true, y_pred, labels=None):
        """
        Registra matriz de confusão

        Args:
            y_true: Labels verdadeiros
            y_pred: Predições
            labels: Lista de labels
        """
        from sklearn.metrics import confusion_matrix
        import matplotlib.pyplot as plt
        import seaborn as sns

        cm = confusion_matrix(y_true, y_pred, labels=labels)

        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')

        plt.savefig('/tmp/confusion_matrix.png')
        mlflow.log_artifact('/tmp/confusion_matrix.png')
        plt.close()

        logger.info("Matriz de confusão registrada")

    def log_recommendation_performance(self, metrics: dict):
        """
        Registra métricas específicas do sistema de recomendação

        Args:
            metrics: Dict com métricas (ex: {
                'mean_reciprocal_rank': 0.75,
                'precision_at_5': 0.80,
                'ndcg': 0.85
            })
        """
        self.log_training_metrics(metrics)

    def end_run(self):
        """Finaliza a run atual"""
        mlflow.end_run()
        logger.info("Run finalizada")

    def load_latest_model(self, model_name="recommendation_model", stage="Production"):
        """
        Carrega o último modelo registrado

        Args:
            model_name: Nome do modelo registrado
            stage: Stage do modelo (Production, Staging, None)

        Returns:
            Modelo carregado
        """
        try:
            model_uri = f"models:/{model_name}/{stage}"
            model = mlflow.sklearn.load_model(model_uri)
            logger.info(f"Modelo carregado: {model_uri}")
            return model
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return None

    def get_best_run(self, metric_name="final_score", ascending=False):
        """
        Retorna a melhor run baseada em uma métrica

        Args:
            metric_name: Nome da métrica para comparação
            ascending: Se True, menor é melhor

        Returns:
            Run com melhor performance
        """
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id],
            order_by=[f"metrics.{metric_name} {'ASC' if ascending else 'DESC'}"]
        )

        if runs.empty:
            return None

        best_run = runs.iloc[0]
        logger.info(f"Melhor run: {best_run['run_id']} com {metric_name}={best_run[f'metrics.{metric_name}']}")

        return best_run

    def compare_runs(self, run_ids: list):
        """
        Compara múltiplas runs

        Args:
            run_ids: Lista de IDs de runs

        Returns:
            DataFrame com comparação
        """
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=f"run_id IN ({','.join(run_ids)})"
        )

        return runs

    def register_production_model(self, run_id, model_name="recommendation_model"):
        """
        Promove um modelo para produção

        Args:
            run_id: ID da run com o modelo
            model_name: Nome do modelo
        """
        try:
            # Obter modelo da run
            model_uri = f"runs:/{run_id}/{model_name}"

            # Registrar modelo
            result = mlflow.register_model(model_uri, model_name)

            # Promover para produção
            self.client.transition_model_version_stage(
                name=model_name,
                version=result.version,
                stage="Production"
            )

            logger.info(f"Modelo promovido para produção: {model_name} v{result.version}")

            return result

        except Exception as e:
            logger.error(f"Erro ao registrar modelo: {e}")
            return None


def evaluate_recommendation_quality(recommendations, ground_truth):
    """
    Avalia a qualidade das recomendações usando métricas padrão

    Args:
        recommendations: Lista de question_ids recomendados (ordenados)
        ground_truth: Lista de question_ids que o usuário realmente acertaria

    Returns:
        Dict com métricas de avaliação
    """
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
    dcg = sum([1 / np.log2(i + 2) if rec in ground_truth else 0
               for i, rec in enumerate(recommendations[:k])])
    idcg = sum([1 / np.log2(i + 2) for i in range(min(k, len(ground_truth)))])
    ndcg = dcg / idcg if idcg > 0 else 0

    return {
        'mean_reciprocal_rank': mrr,
        'precision_at_5': precision_at_k,
        'recall_at_5': recall_at_k,
        'f1_score': f1_score,
        'ndcg': ndcg
    }
