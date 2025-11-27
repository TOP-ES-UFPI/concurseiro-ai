from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404, render
from django.db import models
from concursoapp.models import Question, UserAnswer, UserProfile, SubjectPerformance, Choice
from .serializers import QuestionSerializer
from ml.recommendation_engine import QuestionRecommendationEngine
from ml.cluster_recommender import ClusterRecommender
from ml.cluster_visualizer import ClusterVisualizer
import os
import logging
from django.http import HttpResponse
import mlflow
from django.conf import settings
from google.cloud import storage


logger = logging.getLogger(__name__)

GCS_BUCKET_NAME = "data-mlflow-concursoia"
GCS_RUN_ID_PREFIX = "artefatos/6/models"


MODEL_NAME = "clustering_model"
MODEL_LOCAL_FILENAME = 'cluster_model.pkl'
LATEST_MODEL_URI = f"models:/{MODEL_NAME}/latest"
MODEL_ARTIFACT_FILENAME = 'model.pkl'
MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'ml', 'models'
)
LOCAL_FILE_PATH = os.path.join(MODELS_DIR, MODEL_LOCAL_FILENAME)


def download_model():
    mlflow.set_tracking_uri("http://136.113.82.244:5000/")
    latest_version = mlflow.tracking.MlflowClient().get_latest_versions(
        name=MODEL_NAME, 
        stages=["None"]
    )[0]

    model_version = latest_version._version
    run_id = latest_version._source.split("/")[1]

    settings.MODEL_VERSION_GLOBAL = f"v{model_version}"

    gcs_blob_path = (
        f"{GCS_RUN_ID_PREFIX}/"
        f"{run_id}/"
        f"artifacts/"
        f"{MODEL_ARTIFACT_FILENAME}"
    )
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_blob_path)

    if not blob.exists():
        raise FileNotFoundError(f"Objeto não encontrado no GCS: {gcs_blob_path}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    blob.download_to_filename(LOCAL_FILE_PATH)
    


def load_cluster_model():
    """Carrega modelo de clustering (cached)"""

    download_model()

    model_path = os.path.join(MODELS_DIR, 'cluster_model.pkl')

    if os.path.exists(model_path):
        recommender = ClusterRecommender()
        recommender.load(model_path)
        return recommender
    return None


class GetInitialquestionnaireView(APIView):
    """
    Retorna questões iniciais para o usuário
    Se autenticado, usa ML para personalizar
    Se não autenticado, retorna questões aleatórias
    """
    def get(self, request, *args, **kwargs):
        # Tentar usar modelo de clustering
        recommender = load_cluster_model()

        if recommender and request.user.is_authenticated:
            try:
                # Obter histórico do usuário
                user_answers = UserAnswer.objects.filter(user=request.user)
                answered_ids = list(user_answers.values_list('question_id', flat=True))

                # Assuntos fracos
                subject_perfs = SubjectPerformance.objects.filter(user=request.user)
                weak_subjects = [
                    sp.subject for sp in subject_perfs
                    if sp.accuracy < 0.6 and sp.questions_answered >= 3
                ]

                # Recomendar baseado em clustering
                recommended_ids = recommender.recommend(
                    answered_ids=answered_ids,
                    weak_subjects=weak_subjects,
                    n=5
                )

                questions = Question.objects.filter(id__in=recommended_ids)
                serializer = QuestionSerializer(questions, many=True)

                logger.info(f"Clustering recommendation for user {request.user.id}")
                return Response(serializer.data)

            except Exception as e:
                raise
                logger.error(f"Erro clustering: {e}")

        # Fallback: questões aleatórias
        questions = Question.objects.order_by('?')[:5]
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)


class GetNextquestionnaireView(APIView):
    """
    Retorna próximas questões baseadas nas respostas anteriores
    Usa clustering para recomendação
    """
    def post(self, request, *args, **kwargs):
        data = request.data

        answered_ids = data.get('answered_ids', [])
        wrong_subjects = data.get('wrong_subjects', [])

        # Tentar usar clustering
        recommender = load_cluster_model()

        if recommender:
            try:
                recommended_ids = recommender.recommend(
                    answered_ids=answered_ids,
                    weak_subjects=wrong_subjects,
                    n=5
                )

                questions = Question.objects.filter(id__in=recommended_ids)
                serializer = QuestionSerializer(questions, many=True)

                logger.info(f"Clustering next questions")
                return Response(serializer.data)

            except Exception as e:
                logger.error(f"Erro clustering: {e}")

        # Fallback: lógica baseada em regras
        priority_questions = Question.objects.filter(
            subject__in=wrong_subjects
        ).exclude(
            id__in=answered_ids
        ).order_by('?')[:5]

        final_questions_list = list(priority_questions)
        all_excluded_ids = list(answered_ids) + [q.id for q in final_questions_list]
        count_needed = 5 - len(final_questions_list)

        if count_needed > 0:
            additional_questions = Question.objects.exclude(
                id__in=all_excluded_ids
            ).order_by('?')[:count_needed]

            final_questions_list.extend(list(additional_questions))

        serializer = QuestionSerializer(final_questions_list, many=True)
        return Response(serializer.data)


class SubmitAnswerView(APIView):
    """
    Registra a resposta do usuário e atualiza métricas
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data

        question_id = data.get('question_id')
        choice_id = data.get('choice_id')
        time_spent = data.get('time_spent_seconds')

        if not question_id or not choice_id:
            return Response(
                {'error': 'question_id e choice_id são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar questão e escolha
        question = get_object_or_404(Question, id=question_id)
        choice = get_object_or_404(Choice, id=choice_id, question=question)

        # Registrar resposta
        user_answer = UserAnswer.objects.create(
            user=request.user,
            question=question,
            selected_choice=choice,
            is_correct=choice.is_correct,
            time_spent_seconds=time_spent
        )

        return Response({
            'success': True,
            'is_correct': choice.is_correct,
            'correct_choice_id': question.choices.filter(is_correct=True).first().id
        })


class UserStatsView(APIView):
    """
    Retorna estatísticas do usuário
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        subject_perfs = SubjectPerformance.objects.filter(user=request.user)

        subject_stats = [
            {
                'subject': sp.subject,
                'accuracy': sp.accuracy,
                'questions_answered': sp.questions_answered,
                'correct_answers': sp.correct_answers
            }
            for sp in subject_perfs
        ]

        return Response({
            'total_questions_answered': profile.total_questions_answered,
            'total_correct_answers': profile.total_correct_answers,
            'overall_accuracy': profile.overall_accuracy,
            'subject_performance': subject_stats
        })


class QuestionListView(APIView):
    """
    Lista todas as questões com filtros opcionais
    """
    def get(self, request, *args, **kwargs):
        questions = Question.objects.all()

        # Filtros opcionais
        subject = request.query_params.get('subject')
        if subject:
            questions = questions.filter(subject__icontains=subject)

        difficulty_min = request.query_params.get('difficulty_min')
        if difficulty_min:
            questions = questions.filter(difficulty__gte=float(difficulty_min))

        difficulty_max = request.query_params.get('difficulty_max')
        if difficulty_max:
            questions = questions.filter(difficulty__lte=float(difficulty_max))

        # Paginação simples
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))

        start = (page - 1) * page_size
        end = start + page_size

        total = questions.count()
        questions_page = questions[start:end]

        serializer = QuestionSerializer(questions_page, many=True)

        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'results': serializer.data
        })


class SubjectListView(APIView):
    """
    Lista todos os assuntos disponíveis
    """
    def get(self, request, *args, **kwargs):
        subjects = Question.objects.values_list('subject', flat=True).distinct()

        subject_stats = []
        for subject in subjects:
            count = Question.objects.filter(subject=subject).count()
            avg_difficulty = Question.objects.filter(subject=subject).aggregate(
                avg=models.Avg('difficulty')
            )['avg'] or 0.5

            subject_stats.append({
                'subject': subject,
                'question_count': count,
                'avg_difficulty': avg_difficulty
            })

        return Response(subject_stats)


class ClusterDebugView(APIView):
    """
    View de debug para visualizar clusters e recomendações
    """
    def get(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo de clustering não encontrado',
                'message': 'Execute: python manage.py train_clusters'
            }, status=status.HTTP_404_NOT_FOUND)

        # Estatísticas dos clusters
        clustered_df = recommender.questions_df
        cluster_info = []

        for cluster_id in range(recommender.n_clusters):
            cluster_qs = clustered_df[clustered_df['cluster'] == cluster_id]

            # Assuntos no cluster
            subject_counts = cluster_qs['subject'].value_counts().to_dict()
            top_subjects = list(subject_counts.keys())[:3]

            # Questões do cluster
            questions_in_cluster = []
            for _, row in cluster_qs.head(5).iterrows():
                questions_in_cluster.append({
                    'id': int(row['id']),
                    'text_preview': row['text'][:100] + '...',
                    'subject': row['subject']
                })

            cluster_info.append({
                'cluster_id': cluster_id,
                'count': len(cluster_qs),
                'top_subjects': top_subjects,
                'subjects': subject_counts,
                'sample_questions': questions_in_cluster
            })

        # Calcular Silhouette Score se possível
        silhouette = None
        try:
            from sklearn.metrics import silhouette_score
            if len(clustered_df) > recommender.n_clusters:
                silhouette = silhouette_score(
                    recommender.question_vectors,
                    clustered_df['cluster']
                )
        except:
            pass

        # Contar assuntos únicos
        total_subjects = clustered_df['subject'].nunique()

        return Response({
            'n_clusters': recommender.n_clusters,
            'total_questions': len(clustered_df),
            'total_subjects': total_subjects,
            'silhouette_score': silhouette,
            'clusters': cluster_info
        })


class RecommendationDebugView(APIView):
    """
    Testa recomendação e mostra detalhes dos clusters
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        # Obter histórico do usuário
        user_answers = UserAnswer.objects.filter(user=request.user)
        answered_ids = list(user_answers.values_list('question_id', flat=True))

        # Assuntos fracos
        subject_perfs = SubjectPerformance.objects.filter(user=request.user)
        weak_subjects = [
            sp.subject for sp in subject_perfs
            if sp.accuracy < 0.6 and sp.questions_answered >= 3
        ]

        # Recomendar
        recommended_ids = recommender.recommend(
            answered_ids=answered_ids,
            weak_subjects=weak_subjects,
            n=5
        )

        # Obter detalhes completos
        recommendations_detail = []
        for q_id in recommended_ids:
            question = Question.objects.get(id=q_id)

            # Encontrar cluster da questão
            q_row = recommender.questions_df[recommender.questions_df['id'] == q_id]
            cluster_id = int(q_row['cluster'].values[0]) if len(q_row) > 0 else None

            recommendations_detail.append({
                'question_id': q_id,
                'text': question.text[:150] + '...',
                'subject': question.subject,
                'cluster_id': cluster_id,
                'difficulty': question.difficulty
            })

        return Response({
            'user': request.user.username,
            'answered_count': len(answered_ids),
            'weak_subjects': weak_subjects,
            'recommendations': recommendations_detail,
            'cluster_distribution': self._get_cluster_distribution(recommended_ids, recommender)
        })

    def _get_cluster_distribution(self, question_ids, recommender):
        """Calcula distribuição de clusters nas recomendações"""
        distribution = {}
        for q_id in question_ids:
            q_row = recommender.questions_df[recommender.questions_df['id'] == q_id]
            if len(q_row) > 0:
                cluster_id = int(q_row['cluster'].values[0])
                distribution[cluster_id] = distribution.get(cluster_id, 0) + 1
        return distribution


class ClusterVisualizationView(APIView):
    """
    Retorna visualização 2D dos clusters
    """
    def get(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            visualizer = ClusterVisualizer(recommender)

            # Gerar gráfico 2D
            image_base64 = visualizer.plot_clusters_2d()

            return Response({
                'image': image_base64,
                'n_clusters': recommender.n_clusters,
                'total_questions': len(recommender.questions_df)
            })

        except Exception as e:
            logger.error(f"Erro ao gerar visualização: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClusterDistributionView(APIView):
    """
    Retorna gráfico de distribuição de clusters
    """
    def get(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            visualizer = ClusterVisualizer(recommender)
            image_base64 = visualizer.plot_cluster_distribution()

            return Response({
                'image': image_base64
            })

        except Exception as e:
            logger.error(f"Erro ao gerar distribuição: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRecommendationVisualizationView(APIView):
    """
    Visualização das recomendações do usuário
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            # Obter dados do usuário
            user_answers = UserAnswer.objects.filter(user=request.user)
            answered_ids = list(user_answers.values_list('question_id', flat=True))

            subject_perfs = SubjectPerformance.objects.filter(user=request.user)
            weak_subjects = [
                sp.subject for sp in subject_perfs
                if sp.accuracy < 0.6 and sp.questions_answered >= 3
            ]

            # Recomendar
            recommended_ids = recommender.recommend(
                answered_ids=answered_ids,
                weak_subjects=weak_subjects,
                n=5
            )

            # Gerar visualização
            visualizer = ClusterVisualizer(recommender)
            image_base64 = visualizer.plot_user_recommendations(
                recommended_ids=recommended_ids,
                answered_ids=answered_ids
            )

            return Response({
                'image': image_base64,
                'recommended_ids': recommended_ids,
                'answered_count': len(answered_ids)
            })

        except Exception as e:
            logger.error(f"Erro ao gerar visualização de recomendações: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def cluster_visualization_page(request):
    """
    Renderiza página HTML de visualização dos clusters
    """
    return render(request, 'cluster_visualization.html')


class NivelamentoAnalysisView(APIView):
    """
    Analisa resultados do nivelamento mostrando erros por cluster e recomendações
    """
    def post(self, request, *args, **kwargs):
        recommender = load_cluster_model()

        if not recommender:
            return Response({
                'error': 'Modelo não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            # Dados do nivelamento
            results = request.data.get('results', [])

            if not results:
                return Response({
                    'error': 'Nenhum resultado fornecido'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Separar acertos e erros
            correct_ids = [r['question_id'] for r in results if r['was_correct']]
            wrong_ids = [r['question_id'] for r in results if not r['was_correct']]

            # Analisar erros por cluster
            errors_by_cluster = {}
            errors_by_subject = {}

            for wrong_id in wrong_ids:
                question = Question.objects.get(id=wrong_id)
                q_row = recommender.questions_df[recommender.questions_df['id'] == wrong_id]

                if len(q_row) > 0:
                    cluster_id = int(q_row['cluster'].values[0])

                    if cluster_id not in errors_by_cluster:
                        errors_by_cluster[cluster_id] = {
                            'count': 0,
                            'questions': [],
                            'subjects': set()
                        }

                    errors_by_cluster[cluster_id]['count'] += 1
                    errors_by_cluster[cluster_id]['questions'].append({
                        'id': wrong_id,
                        'text_preview': question.text[:80] + '...',
                        'subject': question.subject
                    })
                    errors_by_cluster[cluster_id]['subjects'].add(question.subject)

                    # Contagem por assunto
                    if question.subject not in errors_by_subject:
                        errors_by_subject[question.subject] = 0
                    errors_by_subject[question.subject] += 1

            # Converter sets para listas
            for cluster_id in errors_by_cluster:
                errors_by_cluster[cluster_id]['subjects'] = list(errors_by_cluster[cluster_id]['subjects'])

            # Obter recomendações
            answered_ids = [r['question_id'] for r in results]
            weak_subjects = list(errors_by_subject.keys())

            recommended_ids = recommender.recommend(
                answered_ids=answered_ids,
                weak_subjects=weak_subjects,
                n=5
            )

            # Analisar recomendações por cluster
            recommendations_by_cluster = {}
            recommendations_detail = []

            for rec_id in recommended_ids:
                question = Question.objects.get(id=rec_id)
                q_row = recommender.questions_df[recommender.questions_df['id'] == rec_id]

                if len(q_row) > 0:
                    cluster_id = int(q_row['cluster'].values[0])

                    if cluster_id not in recommendations_by_cluster:
                        recommendations_by_cluster[cluster_id] = 0
                    recommendations_by_cluster[cluster_id] += 1

                    recommendations_detail.append({
                        'question_id': rec_id,
                        'text_preview': question.text[:100] + '...',
                        'subject': question.subject,
                        'cluster_id': cluster_id,
                        'was_error_cluster': cluster_id in errors_by_cluster
                    })

            # Calcular estatísticas
            total_questions = len(results)
            total_correct = len(correct_ids)
            total_wrong = len(wrong_ids)
            accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

            return Response({
                'summary': {
                    'total_questions': total_questions,
                    'total_correct': total_correct,
                    'total_wrong': total_wrong,
                    'accuracy': round(accuracy, 1)
                },
                'errors_by_cluster': {
                    str(k): {
                        'count': v['count'],
                        'subjects': v['subjects'],
                        'sample_questions': v['questions'][:2]
                    } for k, v in errors_by_cluster.items()
                },
                'errors_by_subject': errors_by_subject,
                'recommendations': {
                    'questions': recommendations_detail,
                    'by_cluster': recommendations_by_cluster,
                    'targeting_weak_clusters': sum(
                        1 for rec in recommendations_detail if rec['was_error_cluster']
                    )
                },
                'clusters_with_errors': list(errors_by_cluster.keys()),
                'weak_subjects': weak_subjects
            })

        except Exception as e:
            logger.error(f"Erro ao analisar nivelamento: {e}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)