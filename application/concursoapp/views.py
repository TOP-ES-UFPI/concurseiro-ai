from django.shortcuts import render
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin


# Create your views here.

class HomeView(LoginRequiredMixin, generic.TemplateView):
    template_name = "concursoapp/index.html"
    login_url = "/accounts/login/"


class questionnaireView(LoginRequiredMixin, generic.TemplateView):
    template_name = "concursoapp/questionnaire.html"
    login_url = "/accounts/login/"