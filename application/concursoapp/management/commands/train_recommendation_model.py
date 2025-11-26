"""
Django management command para treinar o modelo de recomendação
Uso: python manage.py train_recommendation_model
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from concursoapp.models import Question, UserAnswer, UserProfile, SubjectPerformance
from ml.recommendation_engine import QuestionRecommendationEngine
from ml.mlflow_tracker import MLflowTracker, evaluate_recommendation_quality
import numpy as np
from datetime import datetime


class Command(BaseCommand):
    help = 'Treina o modelo de recomendação de questões e registra no MLflow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--experiment-name',
            type=str,
            default='question_recommendation',
            help='Nome do experimento MLflow',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando treinamento do modelo de recomendação...'))

        # Inicializar componentes
        engine = QuestionRecommendationEngine()
        tracker = MLflowTracker(experiment_name=options['experiment_name'])

        # Iniciar run MLflow
        run = tracker.start_training_run(
            run_name=f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags={
                'model_version': '1.0',
                'algorithm': 'hybrid_recommendation'
            }
        )

        try:
            # Coletar dados de treinamento
            self.stdout.write('📊 Coletando dados de treinamento...')

            all_users = User.objects.all()
            all_questions = Question.objects.all()
            all_answers = UserAnswer.objects.select_related('user', 'question').all()

            n_users = all_users.count()
            n_questions = all_questions.count()
            n_answers = all_answers.count()

            self.stdout.write(f'   Usuários: {n_users}')
            self.stdout.write(f'   Questões: {n_questions}')
            self.stdout.write(f'   Respostas: {n_answers}')

            if n_answers < 10:
                self.stdout.write(self.style.WARNING(
                    '⚠️  Poucos dados para treinar (mínimo 10 respostas). '
                    'O modelo pode não ter boa performance.'
                ))

            # Registrar informações do dataset
            dataset_stats = {
                'n_users': n_users,
                'n_questions': n_questions,
                'n_answers': n_answers,
                'avg_answers_per_user': n_answers / max(n_users, 1),
                'avg_answers_per_question': n_answers / max(n_questions, 1),
                'training_date': datetime.now().isoformat()
            }

            # Estatísticas por assunto
            subjects = all_questions.values_list('subject', flat=True).distinct()
            dataset_stats['subjects'] = list(subjects)
            dataset_stats['n_subjects'] = len(subjects)

            tracker.log_dataset_info(dataset_stats)

            # Treinar modelo de collaborative filtering
            self.stdout.write('🧠 Treinando modelo de collaborative filtering...')
            engine.train_collaborative_filtering_model(all_answers)

            # Registrar hiperparâmetros
            hyperparameters = {
                'difficulty_weight': 0.30,
                'subject_weight': 0.35,
                'spaced_repetition_weight': 0.25,
                'diversity_weight': 0.10,
                'min_similarity_threshold': 0.3,
                'recommendation_batch_size': 5
            }
            tracker.log_hyperparameters(hyperparameters)

            # Avaliar modelo (se houver dados suficientes)
            if n_answers >= 20:
                self.stdout.write('📈 Avaliando performance do modelo...')
                metrics = self.evaluate_model(engine, all_users, all_questions, all_answers)
                tracker.log_recommendation_performance(metrics)

                self.stdout.write(self.style.SUCCESS('✓ Métricas de avaliação:'))
                for metric_name, value in metrics.items():
                    self.stdout.write(f'   {metric_name}: {value:.4f}')
            else:
                self.stdout.write(self.style.WARNING(
                    '⚠️  Dados insuficientes para avaliação completa'
                ))

            # Salvar modelo
            self.stdout.write('💾 Salvando modelo...')
            tracker.log_model(engine, model_name="recommendation_model")

            # Finalizar run
            tracker.end_run()

            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Treinamento concluído com sucesso!\n'
                f'   Run ID: {run.info.run_id}\n'
                f'   Para visualizar: mlflow ui --backend-store-uri file:///{tracker.client.tracking_uri.replace("file://", "")}'
            ))

        except Exception as e:
            tracker.end_run()
            self.stdout.write(self.style.ERROR(f'❌ Erro durante o treinamento: {str(e)}'))
            raise

    def evaluate_model(self, engine, all_users, all_questions, all_answers):
        """
        Avalia a performance do modelo usando validação cruzada

        Returns:
            Dict com métricas de avaliação
        """
        # Selecionar usuários com pelo menos 5 respostas para teste
        user_answer_counts = {}
        for answer in all_answers:
            user_answer_counts[answer.user_id] = user_answer_counts.get(answer.user_id, 0) + 1

        test_users = [uid for uid, count in user_answer_counts.items() if count >= 5]

        if not test_users:
            return {
                'mean_reciprocal_rank': 0.0,
                'precision_at_5': 0.0,
                'recall_at_5': 0.0,
                'f1_score': 0.0,
                'ndcg': 0.0
            }

        # Avaliar para cada usuário de teste
        all_metrics = []

        for user_id in test_users[:10]:  # Limitar a 10 usuários para teste
            user = User.objects.get(id=user_id)
            user_answers = all_answers.filter(user=user).order_by('answered_at')

            # Separar em treino (80%) e teste (20%)
            split_idx = int(len(user_answers) * 0.8)
            train_answers = user_answers[:split_idx]
            test_answers = user_answers[split_idx:]

            if len(test_answers) < 2:
                continue

            # Obter perfil e desempenho por assunto
            profile = UserProfile.objects.get_or_create(user=user)[0]
            subject_perfs = SubjectPerformance.objects.filter(user=user)

            # Questões disponíveis (excluindo as do conjunto de teste)
            test_question_ids = [ans.question_id for ans in test_answers]
            available_questions = all_questions.exclude(id__in=test_question_ids)

            # Gerar recomendações
            recommendations = engine.recommend_questions(
                user=user,
                available_questions=available_questions,
                user_answers_qs=train_answers,
                user_profile=profile,
                subject_performances=subject_perfs,
                n_recommendations=5
            )

            rec_ids = [rec['question_id'] for rec in recommendations]

            # Ground truth: questões que o usuário acertou no conjunto de teste
            ground_truth = [ans.question_id for ans in test_answers if ans.is_correct]

            # Avaliar
            if ground_truth:
                metrics = evaluate_recommendation_quality(rec_ids, ground_truth)
                all_metrics.append(metrics)

        # Calcular médias
        if not all_metrics:
            return {
                'mean_reciprocal_rank': 0.0,
                'precision_at_5': 0.0,
                'recall_at_5': 0.0,
                'f1_score': 0.0,
                'ndcg': 0.0
            }

        avg_metrics = {}
        for key in all_metrics[0].keys():
            values = [m[key] for m in all_metrics]
            avg_metrics[key] = np.mean(values)

        return avg_metrics
