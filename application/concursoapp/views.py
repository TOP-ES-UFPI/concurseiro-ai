from django.shortcuts import render
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from application.api.model_state import MODEL_VERSION_GLOBAL



# Create your views here.

class HomeView(LoginRequiredMixin, generic.TemplateView):
    template_name = "concursoapp/index.html"
    login_url = "/accounts/login/"


class questionnaireView(LoginRequiredMixin, generic.TemplateView):
    template_name = "concursoapp/questionnaire.html"
    login_url = "/accounts/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['MODEL_VERSION'] = MODEL_VERSION_GLOBAL
        return context


class UserStatsView(LoginRequiredMixin, generic.TemplateView):
    template_name = "user_stats.html"
    login_url = "/accounts/login/"