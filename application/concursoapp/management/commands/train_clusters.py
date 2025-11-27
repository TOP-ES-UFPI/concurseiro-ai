"""
Comando para treinar modelo de clustering
Uso: python manage.py train_clusters
"""
from django.core.management.base import BaseCommand
from concursoapp.models import Question
from ml.cluster_recommender import ClusterRecommender
from ml.mlflow_tracker import MLflowTracker
import pandas as pd
import os
from datetime import datetime
from sklearn.metrics import silhouette_score


class Command(BaseCommand):
    help = 'Treina modelo de clustering de questões'

    def add_arguments(self, parser):
        parser.add_argument(
            '--n-clusters',
            type=int,
            default=3,
            help='Número de clusters (padrão: 8)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(' Treinando modelo de clustering...'))

        # Inicializar MLflow
        tracker = MLflowTracker(experiment_name="question_clustering_v2")
        run = tracker.start_training_run(
            run_name=f"clustering_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags={
                'model_type': 'clustering',
                'algorithm': 'kmeans_tfidf'
            }
        )

        try:
            # Buscar questões
            questions = Question.objects.all()

            if questions.count() == 0:
                self.stdout.write(self.style.ERROR('❌ Nenhuma questão no banco!'))
                self.stdout.write('Execute: python manage.py load_questions')
                tracker.end_run()
                return

            # Preparar dados
            df = pd.DataFrame({
                'id': [q.id for q in questions],
                'text': [q.text for q in questions],
                'subject': [q.subject for q in questions]
            })

            self.stdout.write(f' Questões: {len(df)}')

            # Treinar
            n_clusters = options['n_clusters']
            recommender = ClusterRecommender(n_clusters=n_clusters)
            metrics = recommender.fit(df)

            self.stdout.write(f' Clusters criados: {metrics["n_clusters"]}')

            # Calcular Silhouette Score
            silhouette = silhouette_score(
                recommender.question_vectors,
                recommender.questions_df['cluster']
            )

            # Log hiperparâmetros no MLflow
            tracker.log_hyperparameters({
                'n_clusters': metrics['n_clusters'],
                'max_features': 300,
                'ngram_range': '(1,2)',
                'vectorizer': 'TfidfVectorizer',
                'algorithm': 'KMeans'
            })

            # Log métricas no MLflow
            tracker.log_training_metrics({
                'n_questions': metrics['n_questions'],
                'n_clusters': metrics['n_clusters'],
                'silhouette_score': silhouette
            })

            # Estatísticas por cluster
            clustered_df = recommender.questions_df
            cluster_stats = {}

            for cluster_id in range(metrics['n_clusters']):
                cluster_qs = clustered_df[clustered_df['cluster'] == cluster_id]
                dominant = cluster_qs['subject'].mode()
                dominant_subject = dominant[0] if len(dominant) > 0 else 'N/A'

                cluster_stats[f'cluster_{cluster_id}_size'] = len(cluster_qs)
                cluster_stats[f'cluster_{cluster_id}_subject'] = dominant_subject

                self.stdout.write(
                    f'  Cluster {cluster_id}: {len(cluster_qs)} questões '
                    f'(tema: {dominant_subject})'
                )

            # Log dataset info no MLflow
            dataset_info = {
                'n_questions': metrics['n_questions'],
                'n_clusters': metrics['n_clusters'],
                'subjects': df['subject'].unique().tolist(),
                'cluster_distribution': cluster_stats,
                'training_date': datetime.now().isoformat()
            }
            tracker.log_dataset_info(dataset_info)

            # Salvar modelo
            models_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'ml', 'models'
            )
            os.makedirs(models_dir, exist_ok=True)
            model_path = os.path.join(models_dir, 'cluster_model.pkl')

            recommender.save(model_path)

            # Log modelo no MLflow
            tracker.log_model(recommender, model_name="clustering_model")

            # Finalizar run MLflow
            tracker.end_run()

            self.stdout.write(self.style.SUCCESS(f'\n Métricas:'))
            self.stdout.write(f'   Silhouette Score: {silhouette:.4f}')
            self.stdout.write(self.style.SUCCESS(f'\n Modelo salvo: {model_path}'))
            self.stdout.write(self.style.SUCCESS(
                f' Pronto para recomendar!\n'
                f'   Run ID: {run.info.run_id}\n'
                f'   Para visualizar: mlflow ui'
            ))

        except Exception as e:
            tracker.end_run()
            self.stdout.write(self.style.ERROR(f'❌ Erro: {str(e)}'))
            raise
