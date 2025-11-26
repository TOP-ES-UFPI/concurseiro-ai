"""
Visualizador de Clusters usando matplotlib e seaborn
"""
import matplotlib
matplotlib.use('Agg')  # Backend não-interativo para servidor
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from sklearn.decomposition import PCA
import io
import base64


class ClusterVisualizer:
    """Cria visualizações dos clusters"""

    def __init__(self, recommender):
        self.recommender = recommender
        self.colors = sns.color_palette('tab10', n_colors=recommender.n_clusters)

    def plot_clusters_2d(self, figsize=(14, 10), save_path=None):
        """
        Plota clusters em 2D usando PCA

        Args:
            figsize: Tamanho da figura
            save_path: Caminho para salvar (None = retorna base64)

        Returns:
            Base64 string da imagem ou None se save_path fornecido
        """
        # Reduzir dimensionalidade para 2D com PCA
        pca = PCA(n_components=2, random_state=42)
        vectors_dense = self.recommender.question_vectors.toarray()
        coords_2d = pca.fit_transform(vectors_dense)

        # Criar figura
        fig, ax = plt.subplots(figsize=figsize)

        # Plotar cada cluster
        df = self.recommender.questions_df.copy()
        df['x'] = coords_2d[:, 0]
        df['y'] = coords_2d[:, 1]

        for cluster_id in range(self.recommender.n_clusters):
            cluster_data = df[df['cluster'] == cluster_id]

            # Scatter plot
            ax.scatter(
                cluster_data['x'],
                cluster_data['y'],
                c=[self.colors[cluster_id]],
                label=f'Cluster {cluster_id} ({len(cluster_data)})',
                alpha=0.6,
                s=100,
                edgecolors='black',
                linewidth=0.5
            )

            # Centroide do cluster
            centroid_x = cluster_data['x'].mean()
            centroid_y = cluster_data['y'].mean()
            ax.scatter(
                centroid_x,
                centroid_y,
                c=[self.colors[cluster_id]],
                marker='*',
                s=500,
                edgecolors='black',
                linewidth=2,
                alpha=1.0
            )

            # Assunto dominante
            dominant_subject = cluster_data['subject'].mode()
            if len(dominant_subject) > 0:
                subject_text = dominant_subject[0][:20]
                ax.annotate(
                    f'C{cluster_id}\n{subject_text}',
                    (centroid_x, centroid_y),
                    fontsize=9,
                    ha='center',
                    va='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=self.colors[cluster_id], alpha=0.7)
                )

        ax.set_xlabel('Componente Principal 1', fontsize=12)
        ax.set_ylabel('Componente Principal 2', fontsize=12)
        ax.set_title(
            f'Visualização dos Clusters de Questões (PCA)\n'
            f'{self.recommender.n_clusters} clusters, {len(df)} questões',
            fontsize=14,
            fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # Salvar ou retornar base64
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return None
        else:
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            return image_base64

    def plot_cluster_distribution(self, figsize=(12, 6)):
        """
        Plota distribuição de questões por cluster

        Returns:
            Base64 string da imagem
        """
        df = self.recommender.questions_df

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # 1. Tamanho dos clusters (barras)
        cluster_sizes = df['cluster'].value_counts().sort_index()

        bars = ax1.bar(
            cluster_sizes.index,
            cluster_sizes.values,
            color=[self.colors[i] for i in cluster_sizes.index],
            edgecolor='black',
            linewidth=1
        )

        ax1.set_xlabel('Cluster ID', fontsize=11)
        ax1.set_ylabel('Número de Questões', fontsize=11)
        ax1.set_title('Distribuição de Questões por Cluster', fontsize=12, fontweight='bold')
        ax1.grid(axis='y', alpha=0.3)

        # Adicionar valores nas barras
        for bar in bars:
            height = bar.get_height()
            ax1.text(
                bar.get_x() + bar.get_width() / 2.,
                height,
                f'{int(height)}',
                ha='center',
                va='bottom',
                fontsize=10
            )

        # 2. Assuntos por cluster (stacked bar)
        cluster_subject_counts = []
        all_subjects = df['subject'].unique()

        for cluster_id in range(self.recommender.n_clusters):
            cluster_data = df[df['cluster'] == cluster_id]
            subject_counts = {subj: 0 for subj in all_subjects}

            for subj in cluster_data['subject']:
                subject_counts[subj] += 1

            cluster_subject_counts.append(subject_counts)

        # Plotar top 5 assuntos
        subject_totals = df['subject'].value_counts().head(5)
        bottom = np.zeros(self.recommender.n_clusters)

        for subject in subject_totals.index:
            values = [cluster_subject_counts[i].get(subject, 0) for i in range(self.recommender.n_clusters)]
            ax2.bar(
                range(self.recommender.n_clusters),
                values,
                bottom=bottom,
                label=subject[:25],
                edgecolor='white',
                linewidth=1
            )
            bottom += values

        ax2.set_xlabel('Cluster ID', fontsize=11)
        ax2.set_ylabel('Número de Questões', fontsize=11)
        ax2.set_title('Top 5 Assuntos por Cluster', fontsize=12, fontweight='bold')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()

        return image_base64

    def plot_user_recommendations(self, recommended_ids, answered_ids=None, figsize=(14, 10)):
        """
        Plota recomendações do usuário no espaço de clusters

        Args:
            recommended_ids: IDs das questões recomendadas
            answered_ids: IDs já respondidos (opcional)

        Returns:
            Base64 string da imagem
        """
        # Reduzir dimensionalidade
        pca = PCA(n_components=2, random_state=42)
        vectors_dense = self.recommender.question_vectors.toarray()
        coords_2d = pca.fit_transform(vectors_dense)

        df = self.recommender.questions_df.copy()
        df['x'] = coords_2d[:, 0]
        df['y'] = coords_2d[:, 1]

        fig, ax = plt.subplots(figsize=figsize)

        # Plotar todos os pontos (clusters)
        for cluster_id in range(self.recommender.n_clusters):
            cluster_data = df[df['cluster'] == cluster_id]
            ax.scatter(
                cluster_data['x'],
                cluster_data['y'],
                c=[self.colors[cluster_id]],
                alpha=0.3,
                s=50,
                label=f'Cluster {cluster_id}'
            )

        # Destacar questões respondidas
        if answered_ids:
            answered_data = df[df['id'].isin(answered_ids)]
            ax.scatter(
                answered_data['x'],
                answered_data['y'],
                c='gray',
                marker='x',
                s=200,
                linewidth=2,
                alpha=0.7,
                label='Respondidas',
                zorder=5
            )

        # Destacar recomendações
        recommended_data = df[df['id'].isin(recommended_ids)]
        ax.scatter(
            recommended_data['x'],
            recommended_data['y'],
            c='red',
            marker='*',
            s=500,
            edgecolors='black',
            linewidth=2,
            alpha=1.0,
            label='Recomendadas',
            zorder=10
        )

        # Numerar recomendações
        for idx, (_, row) in enumerate(recommended_data.iterrows(), 1):
            ax.annotate(
                f'{idx}',
                (row['x'], row['y']),
                fontsize=12,
                fontweight='bold',
                ha='center',
                va='center',
                color='white',
                bbox=dict(boxstyle='circle,pad=0.3', facecolor='red', alpha=0.8)
            )

        ax.set_xlabel('Componente Principal 1', fontsize=12)
        ax.set_ylabel('Componente Principal 2', fontsize=12)
        ax.set_title(
            f'Recomendações Personalizadas no Espaço de Clusters\n'
            f'{len(recommended_ids)} recomendações destacadas',
            fontsize=14,
            fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()

        return image_base64
