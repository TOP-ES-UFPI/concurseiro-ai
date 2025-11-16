# Em 'seu_app/views.py'

from rest_framework.views import APIView
from rest_framework.response import Response
from concursoapp.models import Question
from .serializers import QuestionSerializer

class GetInitialquestionnaireView(APIView):
    def get(self, request, *args, **kwargs):
        questions = Question.objects.order_by('?')[:5]
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)


class GetNextquestionnaireView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        
        answered_ids = data.get('answered_ids', [])
        wrong_subjects = data.get('wrong_subjects', [])

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