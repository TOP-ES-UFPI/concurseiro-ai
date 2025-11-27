import os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.metrics import silhouette_score
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def extract_questions_data(engine):
    sql_query = text("SELECT id, text, subject FROM concursoapp_question")
    
    with engine.connect() as connection:
        df = pd.read_sql(sql_query, connection)
    
    if df.empty:
        logger.warning("Nenhuma questão encontrada no banco de dados!")
        return None
        
    logger.info(f"Questões extraídas: {len(df)}")
    return df


def train_clustering_model(engine, n_clusters=3):
    """Treina o modelo de clustering."""
    from dags.ml.cluster_recommender import ClusterRecommender
    from dags.ml.mlflow_tracker import MLflowTracker

    df = extract_questions_data(engine)
    if df is None:
        return

    tracker = MLflowTracker(experiment_name="question_clustering")
    run = tracker.start_training_run(
        run_name=f"clustering_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        tags={'model_type': 'clustering', 'algorithm': 'kmeans_tfidf'}
    )
    
    try:
        logger.info(f"🧠 Treinando com {n_clusters} clusters...")
        
        recommender = ClusterRecommender(n_clusters=n_clusters)
        metrics = recommender.fit(df)

        silhouette = silhouette_score(
            recommender.question_vectors,
            recommender.questions_df['cluster']
        )
        
        tracker.log_hyperparameters({'n_clusters': metrics['n_clusters'], 'silhouette_score': silhouette})
        tracker.log_training_metrics({'n_questions': metrics['n_questions'], 'silhouette_score': silhouette})
        
        # 5. Salvar Modelo (Para o MLflow e um caminho local/S3)
        #model_path = "/tmp/cluster_model.pkl" # Use um caminho temporário ou S3/MinIO
        #recommender.save(model_path) 

        # 6. Log no MLflow
        tracker.log_model(recommender, model_name="clustering_model")
        
        logger.info(f"Treinamento de Clustering concluído! Silhouette: {silhouette:.4f}")

    except Exception as e:
        logger.error(f'Erro durante o treinamento de clustering: {str(e)}', exc_info=True)
        raise
    finally:
        tracker.end_run()

