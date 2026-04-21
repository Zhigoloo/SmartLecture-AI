from django.contrib import admin
from .models import User, Quiz, Question, Option, QuizAttempt, Answer, LectureNote


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['username', 'email']


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'teacher__username']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'order']
    list_filter = ['quiz']
    inlines = [OptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'score', 'percentage', 'completed_at']
    list_filter = ['quiz', 'completed_at']
    search_fields = ['student__username', 'quiz__title']


@admin.register(LectureNote)
class LectureNoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'teacher__username']


from django.contrib import admin

# Register your models here.
