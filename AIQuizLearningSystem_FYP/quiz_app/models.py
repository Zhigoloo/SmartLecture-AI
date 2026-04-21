import uuid
import string
import random
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


def generate_access_code():
    """Generate a 6-character uppercase alphanumeric code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def generate_share_token():
    """Generate a unique UUID-based share token."""
    return uuid.uuid4().hex[:12]


SECURITY_QUESTIONS = [
    ('pet', "What was the name of your first pet?"),
    ('city', "In what city were you born?"),
    ('school', "What was the name of your first school?"),
    ('mother_maiden', "What is your mother's maiden name?"),
    ('favourite_teacher', "Who was your favourite teacher?"),
    ('childhood_friend', "What is the name of your childhood best friend?"),
]


class User(AbstractUser):
    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    email = models.EmailField(unique=True)  # ✅ add this
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    security_question = models.CharField(
        max_length=32, choices=SECURITY_QUESTIONS, blank=True, default=''
    )
    security_answer_hash = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'users'


class Quiz(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    title = models.CharField(max_length=255)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    time_limit = models.IntegerField(default=30, help_text='Time limit in minutes')
    pass_percentage = models.IntegerField(default=70, help_text='Minimum percentage to pass')
    access_code = models.CharField(max_length=6, unique=True, null=True, blank=True)
    share_token = models.CharField(max_length=12, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = generate_access_code()
        if not self.share_token:
            self.share_token = generate_share_token()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'questions'
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'options'
        ordering = ['order']

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField()
    percentage = models.FloatField()
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"


class Answer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE)
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'answers'

    def __str__(self):
        return f"{self.attempt.student.username} - {self.question.text[:50]}"


class LectureNote(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lecture_notes')
    title = models.CharField(max_length=255, default='Untitled')
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='lecture_notes/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lecture_notes'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


from django.db import models

# Create your models here.
