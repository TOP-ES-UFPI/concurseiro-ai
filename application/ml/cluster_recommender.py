"""
Sistema de Recomendação baseado em Clustering de Questões
Não depende de respostas de usuários - funciona desde o primeiro dia!
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os


class ClusterRecommender:
    """Recomendador baseado em clustering TF-IDF + K-Means"""

    def __init__(self, n_clusters=3):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(
            max_features=300,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.9
        )
        self.kmeans = None
        self.question_vectors = None
        self.questions_df = None

    def fit(self, questions_df):
        """
        Treina o modelo

        Args:
            questions_df: DataFrame com ['id', 'text', 'subject']
        """
        self.questions_df = questions_df.copy()

        # Combinar texto + assunto (assunto tem mais peso)
        combined_text = (
            questions_df['text'] + ' ' +
            questions_df['subject'].str.repeat(2)
        )

        # Vetorizar
        self.question_vectors = self.vectorizer.fit_transform(combined_text)

        # Ajustar número de clusters
        n_samples = len(questions_df)
        self.n_clusters = min(self.n_clusters, max(3, n_samples // 5))

        # K-Means
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        clusters = self.kmeans.fit_predict(self.question_vectors)

        self.questions_df['cluster'] = clusters

        return {
            'n_clusters': self.n_clusters,
            'n_questions': n_samples
        }

    def recommend(self, answered_ids=[], weak_subjects=[], n=5, max_per_cluster=2):
        """
        Recomenda questões com garantia de diversidade de clusters

        Args:
            answered_ids: IDs já respondidos (para excluir)
            weak_subjects: Assuntos fracos (para priorizar)
            n: Número de recomendações (padrão: 5)
            max_per_cluster: Máximo de questões por cluster (padrão: 2)

        Returns:
            Lista de question_ids recomendados
        """
        # Filtrar disponíveis
        available = self.questions_df[~self.questions_df['id'].isin(answered_ids)].copy()

        if len(available) == 0:
            return []

        # Calcular scores para todas questões disponíveis
        scores = []
        for _, q in available.iterrows():
            score = 0

            # Priorizar assuntos fracos (peso 50%)
            if q['subject'] in weak_subjects:
                score += 0.5

            # Diversidade de clusters (peso 30%)
            cluster_id = q['cluster']
            answered_in_cluster = sum(
                1 for aid in answered_ids
                if aid in self.questions_df[
                    self.questions_df['cluster'] == cluster_id
                ]['id'].values
            )
            cluster_size = len(self.questions_df[
                self.questions_df['cluster'] == cluster_id
            ])

            if cluster_size > 0:
                exploration = 1 - (answered_in_cluster / cluster_size)
                score += exploration * 0.3

            # Bonus para clusters com erros (peso 20%)
            # Inferido: se o assunto está em weak_subjects e a questão é desse assunto
            if q['subject'] in weak_subjects:
                score += 0.2

            scores.append((q['id'], q['cluster'], q['subject'], score))

        # Ordenar por score
        scores.sort(key=lambda x: x[3], reverse=True)

        # Seleção com garantia de diversidade
        selected = []
        cluster_count = {}  # Quantas questões já selecionamos de cada cluster
        subject_count = {}  # Quantas questões já selecionamos de cada assunto

        # Primeira passada: priorizar clusters fracos com limite
        for qid, cluster_id, subject, score in scores:
            if len(selected) >= n:
                break

            current_cluster_count = cluster_count.get(cluster_id, 0)

            # Limitar questões por cluster
            if current_cluster_count >= max_per_cluster:
                continue

            selected.append(qid)
            cluster_count[cluster_id] = current_cluster_count + 1
            subject_count[subject] = subject_count.get(subject, 0) + 1

        # Se ainda falta, preencher com questões de clusters não explorados
        if len(selected) < n:
            # Clusters ainda não usados ou pouco usados
            for qid, cluster_id, subject, score in scores:
                if len(selected) >= n:
                    break

                if qid in selected:
                    continue

                current_cluster_count = cluster_count.get(cluster_id, 0)

                # Permitir até max_per_cluster + 1 se realmente necessário
                if current_cluster_count >= max_per_cluster + 1:
                    continue

                selected.append(qid)
                cluster_count[cluster_id] = current_cluster_count + 1

        return selected[:n]

    def get_similar(self, question_id, n=5):
        """Retorna questões similares baseado em clustering"""
        # Encontrar questão
        q_row = self.questions_df[self.questions_df['id'] == question_id]
        if len(q_row) == 0:
            return []

        cluster_id = q_row['cluster'].values[0]
        q_idx = q_row.index[0]

        # Questões do mesmo cluster
        same_cluster = self.questions_df[
            (self.questions_df['cluster'] == cluster_id) &
            (self.questions_df['id'] != question_id)
        ]

        if len(same_cluster) == 0:
            return []

        # Calcular similaridade por cosseno
        q_vector = self.question_vectors[q_idx]
        cluster_indices = same_cluster.index
        cluster_vectors = self.question_vectors[cluster_indices]

        similarities = cosine_similarity(q_vector, cluster_vectors).flatten()

        # Top N mais similares
        top_indices = similarities.argsort()[-n:][::-1]
        similar_ids = same_cluster.iloc[top_indices]['id'].tolist()

        return similar_ids

    def save(self, filepath):
        """Salva modelo"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'kmeans': self.kmeans,
                'question_vectors': self.question_vectors,
                'questions_df': self.questions_df,
                'n_clusters': self.n_clusters
            }, f)

    def load(self, filepath):
        """Carrega modelo"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.vectorizer = data['vectorizer']
        self.kmeans = data['kmeans']
        self.question_vectors = data['question_vectors']
        self.questions_df = data['questions_df']
        self.n_clusters = data['n_clusters']
