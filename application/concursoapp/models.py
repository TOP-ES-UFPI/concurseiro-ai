from django.db import models
from django.contrib.auth.models import User


class Question(models.Model):
    subject = models.CharField(max_length=255)
    text = models.TextField()
    difficulty = models.FloatField(default=0.5)  # 0-1, calculado pela taxa de acerto
    source_file = models.CharField(max_length=500, null=True, blank=True)
    times_answered = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)

    def __str__(self):
        return self.text[:50]

    def update_difficulty(self):
        """Atualiza a dificuldade baseada na taxa de acerto"""
        if self.times_answered > 0:
            accuracy = self.times_correct / self.times_answered
            # Dificuldade inversa: quanto menor a taxa de acerto, maior a dificuldade
            self.difficulty = 1 - accuracy
            self.save()


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class UserProfile(models.Model):
    """Perfil do usuário com estatísticas de desempenho"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_questions_answered = models.IntegerField(default=0)
    total_correct_answers = models.IntegerField(default=0)
    overall_accuracy = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"

    def update_stats(self):
        """Atualiza as estatísticas gerais do usuário"""
        if self.total_questions_answered > 0:
            self.overall_accuracy = self.total_correct_answers / self.total_questions_answered
        self.save()


class SubjectPerformance(models.Model):
    """Desempenho do usuário por assunto"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subject_performances')
    subject = models.CharField(max_length=255)
    questions_answered = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    last_practiced = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'subject']

    def __str__(self):
        return f"{self.user.username} - {self.subject}: {self.accuracy:.2%}"

    def update_accuracy(self):
        """Atualiza a taxa de acerto do assunto"""
        if self.questions_answered > 0:
            self.accuracy = self.correct_answers / self.questions_answered
        self.save()


class UserAnswer(models.Model):
    """Registro de cada resposta do usuário"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers')
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True)
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)
    time_spent_seconds = models.IntegerField(null=True, blank=True)  # Tempo gasto na questão

    class Meta:
        ordering = ['-answered_at']

    def __str__(self):
        return f"{self.user.username} - Q{self.question.id} - {'✓' if self.is_correct else '✗'}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Atualizar estatísticas do usuário
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.total_questions_answered += 1
        if self.is_correct:
            profile.total_correct_answers += 1
        profile.update_stats()

        # Atualizar desempenho por assunto
        subject_perf, _ = SubjectPerformance.objects.get_or_create(
            user=self.user,
            subject=self.question.subject
        )
        subject_perf.questions_answered += 1
        if self.is_correct:
            subject_perf.correct_answers += 1
        subject_perf.update_accuracy()

        # Atualizar dificuldade da questão
        self.question.times_answered += 1
        if self.is_correct:
            self.question.times_correct += 1
        self.question.update_difficulty()