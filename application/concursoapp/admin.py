from django.contrib import admin
from .models import Question, Choice, UserAnswer, UserProfile, SubjectPerformance


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    max_num = 5


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'text_preview', 'difficulty', 'times_answered', 'accuracy_rate']
    list_filter = ['subject', 'difficulty']
    search_fields = ['text', 'subject']
    inlines = [ChoiceInline]
    readonly_fields = ['times_answered', 'times_correct', 'difficulty']

    def text_preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    text_preview.short_description = 'Questão'

    def accuracy_rate(self, obj):
        if obj.times_answered == 0:
            return 'N/A'
        rate = (obj.times_correct / obj.times_answered) * 100
        return f'{rate:.1f}%'
    accuracy_rate.short_description = 'Taxa de Acerto'


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_preview', 'text_preview', 'is_correct']
    list_filter = ['is_correct']
    search_fields = ['text', 'question__text']

    def question_preview(self, obj):
        return obj.question.text[:50] + '...'
    question_preview.short_description = 'Questão'

    def text_preview(self, obj):
        return obj.text[:60] + '...' if len(obj.text) > 60 else obj.text
    text_preview.short_description = 'Alternativa'


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'question_preview', 'is_correct', 'answered_at', 'time_spent_seconds']
    list_filter = ['is_correct', 'answered_at', 'question__subject']
    search_fields = ['user__username', 'question__text']
    date_hierarchy = 'answered_at'
    readonly_fields = ['answered_at']

    def question_preview(self, obj):
        return obj.question.text[:50] + '...'
    question_preview.short_description = 'Questão'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_questions_answered', 'total_correct_answers', 'overall_accuracy_percent', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at', 'total_questions_answered', 'total_correct_answers', 'overall_accuracy']

    def overall_accuracy_percent(self, obj):
        return f'{obj.overall_accuracy * 100:.1f}%'
    overall_accuracy_percent.short_description = 'Taxa de Acerto'


@admin.register(SubjectPerformance)
class SubjectPerformanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'questions_answered', 'correct_answers', 'accuracy_percent', 'last_practiced']
    list_filter = ['subject', 'last_practiced']
    search_fields = ['user__username', 'subject']
    readonly_fields = ['last_practiced']

    def accuracy_percent(self, obj):
        return f'{obj.accuracy * 100:.1f}%'
    accuracy_percent.short_description = 'Taxa de Acerto'
