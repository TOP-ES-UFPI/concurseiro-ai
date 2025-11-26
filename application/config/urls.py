"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from concursoapp import views
from api import views as api
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.HomeView.as_view(), name="index"),
    path("accounts/login/", auth_views.LoginView.as_view()),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("questionnaire/", views.questionnaireView.as_view(), name="questionnaire"),
    path("stats/", views.UserStatsView.as_view(), name="user_stats"),

    # API - Questionnaire
    path("api/questionnaire/start/", api.GetInitialquestionnaireView.as_view(), name="api_questionnaire_start"),
    path("api/questionnaire/next/", api.GetNextquestionnaireView.as_view(), name="api_questionnaire_next"),

    # API - User actions
    path("api/answer/submit/", api.SubmitAnswerView.as_view(), name="api_submit_answer"),
    path("api/user/stats/", api.UserStatsView.as_view(), name="api_user_stats"),

    # API - Questions & Subjects
    path("api/questions/", api.QuestionListView.as_view(), name="api_questions_list"),
    path("api/subjects/", api.SubjectListView.as_view(), name="api_subjects_list"),

    # API - Debug/Clustering
    path("api/debug/clusters/", api.ClusterDebugView.as_view(), name="api_cluster_debug"),
    path("api/debug/recommendations/", api.RecommendationDebugView.as_view(), name="api_recommendation_debug"),

    # API - Visualizações
    path("api/viz/clusters/", api.ClusterVisualizationView.as_view(), name="api_viz_clusters"),
    path("api/viz/distribution/", api.ClusterDistributionView.as_view(), name="api_viz_distribution"),
    path("api/viz/recommendations/", api.UserRecommendationVisualizationView.as_view(), name="api_viz_recommendations"),

    # Página de visualização
    path("clusters/", api.cluster_visualization_page, name="cluster_visualization"),

    # API - Análise de Nivelamento
    path("api/nivelamento/analysis/", api.NivelamentoAnalysisView.as_view(), name="api_nivelamento_analysis"),
]
