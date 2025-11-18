"""
Sistema de Recomendação de Questões usando Machine Learning
Combina múltiplas estratégias:
1. Dificuldade adaptativa baseada no desempenho do usuário
2. Spaced Repetition para reforço de aprendizado
3. Collaborative Filtering para identificar questões similares
4. Recomendação por assunto baseada no histórico de erros
"""
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class QuestionRecommendationEngine:
    """Motor de recomendação de questões personalizado"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.user_question_matrix = None
        self.question_similarity_matrix = None

    def build_user_question_matrix(self, user_answers):
        """
        Constrói matriz usuário-questão para collaborative filtering

        Args:
            user_answers: QuerySet de UserAnswer

        Returns:
            DataFrame com matriz usuário x questão
        """
        data = []
        for answer in user_answers:
            data.append({
                'user_id': answer.user_id,
                'question_id': answer.question_id,
                'is_correct': 1 if answer.is_correct else 0,
                'timestamp': answer.answered_at
            })

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Criar matriz pivot: usuários x questões
        matrix = df.pivot_table(
            index='user_id',
            columns='question_id',
            values='is_correct',
            aggfunc='mean',  # Se respondeu múltiplas vezes, usa a média
            fill_value=-1  # -1 = não respondida
        )

        return matrix

    def calculate_question_similarity(self, matrix):
        """
        Calcula similaridade entre questões usando collaborative filtering

        Args:
            matrix: DataFrame com matriz usuário x questão

        Returns:
            Matriz de similaridade entre questões
        """
        if matrix.empty:
            return None

        # Transpor para ter questões nas linhas
        question_matrix = matrix.T

        # Substituir -1 por 0 para cálculo de similaridade
        question_matrix_filled = question_matrix.replace(-1, 0)

        # Calcular similaridade de cosseno entre questões
        similarity = cosine_similarity(question_matrix_filled)

        return pd.DataFrame(
            similarity,
            index=question_matrix.index,
            columns=question_matrix.index
        )

    def calculate_difficulty_match_score(self, user_accuracy, question_difficulty):
        """
        Calcula quão apropriada é a dificuldade de uma questão para o usuário

        Args:
            user_accuracy: Taxa de acerto geral do usuário (0-1)
            question_difficulty: Dificuldade da questão (0-1)

        Returns:
            Score de match (0-1), maior = mais apropriado
        """
        # Questão ideal: um pouco mais difícil que o nível do usuário
        # Isso promove o crescimento sem frustração
        ideal_difficulty = user_accuracy + 0.1

        # Calcular diferença normalizada
        diff = abs(question_difficulty - ideal_difficulty)

        # Converter para score (0-1), onde 0 = muito diferente, 1 = perfeito
        score = max(0, 1 - (diff * 2))

        return score

    def calculate_spaced_repetition_priority(self, last_answered_date, is_correct, days_since=None):
        """
        Implementa Spaced Repetition para priorizar revisão
        Baseado no algoritmo SM-2 simplificado

        Args:
            last_answered_date: Data da última resposta
            is_correct: Se o usuário acertou
            days_since: Dias desde a última resposta (opcional)

        Returns:
            Score de prioridade (0-1), maior = mais prioritário
        """
        if last_answered_date is None:
            return 0.5  # Nunca respondida = prioridade média

        if days_since is None:
            days_since = (datetime.now() - last_answered_date).days

        if is_correct:
            # Acertou: aumenta intervalo progressivamente
            intervals = [1, 3, 7, 14, 30, 60]  # dias
            for i, interval in enumerate(intervals):
                if days_since >= interval:
                    # Chegou a hora de revisar
                    return min(1.0, 0.3 + (i * 0.1))
            return 0.1  # Ainda não precisa revisar
        else:
            # Errou: precisa revisar logo
            if days_since >= 1:
                return 0.9
            return 0.7

    def calculate_subject_priority(self, user_subject_performance, question_subject):
        """
        Prioriza assuntos onde o usuário tem mais dificuldade

        Args:
            user_subject_performance: Dict com {subject: accuracy}
            question_subject: Assunto da questão

        Returns:
            Score de prioridade (0-1)
        """
        if question_subject not in user_subject_performance:
            return 0.5  # Assunto novo = prioridade média

        accuracy = user_subject_performance[question_subject]

        # Quanto menor a taxa de acerto, maior a prioridade
        priority = 1 - accuracy

        return priority

    def recommend_questions(
        self,
        user,
        available_questions,
        user_answers_qs,
        user_profile,
        subject_performances,
        n_recommendations=5
    ) -> List[Dict]:
        """
        Recomenda questões personalizadas para o usuário

        Args:
            user: Objeto User do Django
            available_questions: QuerySet de Questions disponíveis
            user_answers_qs: QuerySet de UserAnswer do usuário
            user_profile: UserProfile do usuário
            subject_performances: QuerySet de SubjectPerformance do usuário
            n_recommendations: Número de questões a recomendar

        Returns:
            Lista de dicts com question_id e scores
        """
        # Construir dict de desempenho por assunto
        subject_perf_dict = {
            sp.subject: sp.accuracy
            for sp in subject_performances
        }

        # Histórico de respostas do usuário
        user_history = {
            ans.question_id: {
                'is_correct': ans.is_correct,
                'answered_at': ans.answered_at
            }
            for ans in user_answers_qs
        }

        # Calcular score para cada questão
        question_scores = []

        for question in available_questions:
            # Skip questões já respondidas recentemente (últimas 24h)
            if question.id in user_history:
                last_answer = user_history[question.id]
                hours_since = (datetime.now() - last_answer['answered_at'].replace(tzinfo=None)).total_seconds() / 3600
                if hours_since < 24:
                    continue

            # 1. Score de dificuldade apropriada (peso 0.3)
            difficulty_score = self.calculate_difficulty_match_score(
                user_profile.overall_accuracy if user_profile.total_questions_answered > 0 else 0.5,
                question.difficulty
            )

            # 2. Score de prioridade por assunto (peso 0.35)
            subject_score = self.calculate_subject_priority(
                subject_perf_dict,
                question.subject
            )

            # 3. Score de spaced repetition (peso 0.25)
            if question.id in user_history:
                last_answer = user_history[question.id]
                spaced_score = self.calculate_spaced_repetition_priority(
                    last_answer['answered_at'],
                    last_answer['is_correct']
                )
            else:
                spaced_score = 0.5  # Nunca respondida

            # 4. Diversidade - penaliza questões muito respondidas (peso 0.1)
            if question.times_answered > 0:
                diversity_score = 1 / (1 + np.log(question.times_answered + 1))
            else:
                diversity_score = 1.0

            # Score final ponderado
            final_score = (
                difficulty_score * 0.30 +
                subject_score * 0.35 +
                spaced_score * 0.25 +
                diversity_score * 0.10
            )

            question_scores.append({
                'question': question,
                'question_id': question.id,
                'final_score': final_score,
                'difficulty_score': difficulty_score,
                'subject_score': subject_score,
                'spaced_score': spaced_score,
                'diversity_score': diversity_score
            })

        # Ordenar por score final
        question_scores.sort(key=lambda x: x['final_score'], reverse=True)

        # Retornar top N
        recommendations = question_scores[:n_recommendations]

        logger.info(f"Recomendação para usuário {user.id}: {len(recommendations)} questões")

        return recommendations

    def train_collaborative_filtering_model(self, all_user_answers):
        """
        Treina modelo de collaborative filtering
        Deve ser executado periodicamente (ex: diariamente)

        Args:
            all_user_answers: QuerySet com todas as UserAnswer
        """
        logger.info("Treinando modelo de collaborative filtering...")

        # Construir matriz usuário-questão
        self.user_question_matrix = self.build_user_question_matrix(all_user_answers)

        if self.user_question_matrix.empty:
            logger.warning("Matriz vazia, não há dados suficientes para treinar")
            return

        # Calcular similaridade entre questões
        self.question_similarity_matrix = self.calculate_question_similarity(
            self.user_question_matrix
        )

        logger.info(f"Modelo treinado: {self.user_question_matrix.shape[0]} usuários, "
                   f"{self.user_question_matrix.shape[1]} questões")

    def get_similar_questions(self, question_id, n_similar=5):
        """
        Retorna questões similares usando collaborative filtering

        Args:
            question_id: ID da questão de referência
            n_similar: Número de questões similares a retornar

        Returns:
            Lista de (question_id, similarity_score)
        """
        if self.question_similarity_matrix is None:
            logger.warning("Modelo não treinado ainda")
            return []

        if question_id not in self.question_similarity_matrix.index:
            return []

        # Pegar similaridades da questão
        similarities = self.question_similarity_matrix[question_id].sort_values(ascending=False)

        # Remover a própria questão e retornar top N
        similar = similarities[similarities.index != question_id].head(n_similar)

        return list(zip(similar.index, similar.values))
