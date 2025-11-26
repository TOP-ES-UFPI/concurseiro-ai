/**
 * Script para exibir estatísticas do usuário
 */

class UserStatsManager {
    constructor() {
        this.statsEndpoint = '/api/user/stats/';
        this.subjectsEndpoint = '/api/subjects/';
    }

    async fetchUserStats() {
        try {
            const response = await fetch(this.statsEndpoint, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error('Erro ao carregar estatísticas');
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Erro ao buscar estatísticas:', error);
            return null;
        }
    }

    async fetchSubjects() {
        try {
            const response = await fetch(this.subjectsEndpoint);
            if (!response.ok) {
                throw new Error('Erro ao carregar assuntos');
            }
            return await response.json();
        } catch (error) {
            console.error('Erro ao buscar assuntos:', error);
            return [];
        }
    }

    renderOverallStats(stats) {
        const container = document.getElementById('overall-stats');
        if (!container) return;

        const accuracyPercent = (stats.overall_accuracy * 100).toFixed(1);
        const totalAnswered = stats.total_questions_answered;
        const totalCorrect = stats.total_correct_answers;

        container.innerHTML = `
            <div class="row">
                <div class="col-md-4 mb-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title text-muted">Questões Respondidas</h5>
                            <h2 class="display-4 text-primary">${totalAnswered}</h2>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title text-muted">Acertos</h5>
                            <h2 class="display-4 text-success">${totalCorrect}</h2>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="card-title text-muted">Taxa de Acerto</h5>
                            <h2 class="display-4 ${this.getAccuracyClass(stats.overall_accuracy)}">
                                ${accuracyPercent}%
                            </h2>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderSubjectPerformance(subjectPerformance) {
        const container = document.getElementById('subject-performance');
        if (!container) return;

        if (!subjectPerformance || subjectPerformance.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info">
                    Responda algumas questões para ver seu desempenho por assunto!
                </div>
            `;
            return;
        }

        // Ordenar por taxa de acerto (menor primeiro = precisa estudar mais)
        const sortedSubjects = [...subjectPerformance].sort((a, b) => a.accuracy - b.accuracy);

        let html = '<div class="row">';

        sortedSubjects.forEach(subject => {
            const accuracyPercent = (subject.accuracy * 100).toFixed(1);
            const accuracyClass = this.getAccuracyClass(subject.accuracy);

            html += `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">${this.escapeHtml(subject.subject)}</h6>
                            <div class="progress mb-2" style="height: 25px;">
                                <div class="progress-bar ${accuracyClass}"
                                     role="progressbar"
                                     style="width: ${accuracyPercent}%"
                                     aria-valuenow="${accuracyPercent}"
                                     aria-valuemin="0"
                                     aria-valuemax="100">
                                    ${accuracyPercent}%
                                </div>
                            </div>
                            <small class="text-muted">
                                ${subject.correct_answers} acertos de ${subject.questions_answered} questões
                            </small>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    renderWeakSubjects(subjectPerformance) {
        const container = document.getElementById('weak-subjects');
        if (!container) return;

        if (!subjectPerformance || subjectPerformance.length === 0) {
            return;
        }

        // Pegar assuntos com menor taxa de acerto (mínimo 3 questões respondidas)
        const weakSubjects = subjectPerformance
            .filter(s => s.questions_answered >= 3)
            .sort((a, b) => a.accuracy - b.accuracy)
            .slice(0, 3);

        if (weakSubjects.length === 0) {
            container.innerHTML = `
                <div class="alert alert-success">
                    Parabéns! Você está indo bem em todos os assuntos! 🎉
                </div>
            `;
            return;
        }

        let html = `
            <div class="alert alert-warning">
                <h6 class="alert-heading">📚 Assuntos que precisam de mais atenção:</h6>
                <ul class="mb-0">
        `;

        weakSubjects.forEach(subject => {
            const accuracyPercent = (subject.accuracy * 100).toFixed(1);
            html += `
                <li>
                    <strong>${this.escapeHtml(subject.subject)}</strong>:
                    ${accuracyPercent}% de acerto
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;

        container.innerHTML = html;
    }

    getAccuracyClass(accuracy) {
        if (accuracy >= 0.8) return 'text-success';
        if (accuracy >= 0.6) return 'text-warning';
        return 'text-danger';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async initialize() {
        const stats = await this.fetchUserStats();

        if (stats) {
            this.renderOverallStats(stats);
            this.renderSubjectPerformance(stats.subject_performance);
            this.renderWeakSubjects(stats.subject_performance);
        } else {
            console.error('Não foi possível carregar as estatísticas');
        }
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    const statsManager = new UserStatsManager();
    statsManager.initialize();
});
