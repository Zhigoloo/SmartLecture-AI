from django.urls import path, include
from . import views

# --- Namespaced patterns ---
teacher_patterns = ([
    path("dashboard/", views.teacher_dashboard, name="dashboard"),
    path("upload/", views.upload_notes, name="upload_notes"),
    path("my-quizzes/", views.my_quizzes, name="my_quizzes"),
    path("quiz/<int:quiz_id>/edit/", views.edit_questions, name="edit_questions"),
    path("quiz/save/", views.save_quiz, name="save_quiz"),
    path("quiz/<int:quiz_id>/add-question/", views.add_question, name="add_question"),
    path("analytics/", views.analytics_overview, name="analytics_overview"),
    path("quiz/<int:quiz_id>/analytics/", views.analytics, name="analytics"),
    path("quiz/<int:quiz_id>/analytics/export/", views.export_analytics, name="export_analytics"),
], "teacher")


student_patterns = ([
    path("dashboard/", views.student_dashboard, name="dashboard"),
    path("quiz/<int:quiz_id>/history/", views.quiz_history, name="quiz_history"),
    path("quiz/<int:quiz_id>/preview/", views.quiz_preview, name="quiz_preview"),
    path("quiz/<int:quiz_id>/", views.student_quiz, name="quiz"),
    path("quiz/<int:quiz_id>/results/<int:attempt_id>/", views.student_results, name="results"),
    path("quiz/<int:quiz_id>/practice/", views.practice_quiz, name="practice_quiz"),
    path("quiz/<int:quiz_id>/practice/submit/", views.practice_submit, name="practice_submit"),
    path("quiz/<int:quiz_id>/practice/add/", views.practice_basket_add, name="practice_basket_add"),
    path("practice-basket/clear/", views.practice_basket_clear, name="practice_basket_clear"),
    path("practice-basket/start/", views.combined_practice, name="combined_practice"),
    path("practice-basket/submit/", views.combined_practice_submit, name="combined_practice_submit"),
    path("join/<str:token>/", views.join_quiz_by_link, name="join_link"),
], "student")

# --- Main urls ---
urlpatterns = [
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/verify/", views.verify_security_answer, name="verify_security_answer"),
    path("forgot-password/reset/", views.reset_password, name="reset_password"),

    path("teacher/", include(teacher_patterns, namespace="teacher")),
    path("student/", include(student_patterns, namespace="student")),
]
