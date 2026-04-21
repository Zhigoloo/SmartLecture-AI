import csv
import json
import time
from collections import Counter
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min
from django.db.models.functions import TruncDate
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import User, Quiz, Question, Option, QuizAttempt, Answer, LectureNote, SECURITY_QUESTIONS
from .forms import RegisterForm, LectureNoteForm
from django.http import HttpResponse
from .ai_service import extract_text_from_file, generate_quiz_questions, QuizGenerationError


# ==================== Authentication Views ====================

@ensure_csrf_cookie  # ✅ ensures CSRF cookie is set on GET
def login_view(request):
    if request.user.is_authenticated:
        role = (getattr(request.user, "role", "") or "").lower()
        if request.user.is_superuser:
            return redirect("/admin/")
        return redirect("teacher:dashboard" if role == "teacher" else "student:dashboard")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = (request.POST.get("role") or "").lower()

        try:
            u = User.objects.get(email=email)
            user = authenticate(request, username=u.username, password=password)

            if user and (user.is_superuser or (user.role or "").lower() == role):
                login(request, user)
                if user.is_superuser:
                    return redirect("/admin/")
                return redirect("teacher:dashboard" if role == "teacher" else "student:dashboard")
            else:
                messages.error(request, "Invalid credentials or role mismatch")
        except User.DoesNotExist:
            messages.error(request, "User not found")

    return render(request, "accounts/login.html")


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created successfully! Please login.")
            return redirect("login")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


# ==================== Forgot Password Flow ====================
#
# 3-step reset using security questions (no email):
#   Step 1: forgot_password          -> enter username/email, show question
#   Step 2: verify_security_answer   -> submit answer, verify hash (max 3 tries)
#   Step 3: reset_password           -> set new password, validators enforced
#
# State is tracked in request.session under the "pw_reset" key. Each step
# gates on the previous step's flag being set.

PW_RESET_KEY = "pw_reset"
PW_RESET_MAX_ATTEMPTS = 3
PW_RESET_COOLDOWN_SECONDS = 15 * 60  # 15-minute lockout after 3 wrong answers
SECURITY_QUESTION_TEXT = dict(SECURITY_QUESTIONS)
GENERIC_RESET_ERROR = (
    "We couldn't verify those details. Please check and try again."
)


def _reset_state(request):
    state = request.session.get(PW_RESET_KEY)
    return state if isinstance(state, dict) else {}


def _save_reset_state(request, state):
    request.session[PW_RESET_KEY] = state
    request.session.modified = True


def _clear_reset_state(request):
    if PW_RESET_KEY in request.session:
        del request.session[PW_RESET_KEY]
        request.session.modified = True


def _in_cooldown(state):
    until = state.get("cooldown_until", 0)
    return until and time.time() < until


def forgot_password(request):
    """Step 1 — identify the account and display its security question."""
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()

        if not identifier:
            messages.error(request, GENERIC_RESET_ERROR)
            return render(request, "accounts/forgot_password.html")

        # Look up by username OR email — don't leak which matched.
        user = User.objects.filter(username__iexact=identifier).first() \
            or User.objects.filter(email__iexact=identifier).first()

        if not user or not user.security_question or not user.security_answer_hash:
            # Generic message — don't reveal whether the account exists
            # or whether it's missing a security question.
            messages.error(request, GENERIC_RESET_ERROR)
            return render(request, "accounts/forgot_password.html")

        # Start a fresh reset session
        _save_reset_state(request, {
            "user_id": user.id,
            "question_verified": False,
            "attempts": 0,
            "cooldown_until": 0,
            "started_at": time.time(),
        })
        return redirect("verify_security_answer")

    # Coming back in for a new attempt — wipe any stale flow
    _clear_reset_state(request)
    return render(request, "accounts/forgot_password.html")


def verify_security_answer(request):
    """Step 2 — verify the answer with attempt limiting + cooldown."""
    state = _reset_state(request)
    user_id = state.get("user_id")
    if not user_id:
        messages.error(request, "Your reset session has expired. Please start again.")
        return redirect("forgot_password")

    user = User.objects.filter(id=user_id).first()
    if not user:
        _clear_reset_state(request)
        messages.error(request, GENERIC_RESET_ERROR)
        return redirect("forgot_password")

    question_text = SECURITY_QUESTION_TEXT.get(user.security_question, "Security question")

    if _in_cooldown(state):
        remaining = int(state["cooldown_until"] - time.time())
        minutes = max(1, remaining // 60)
        return render(request, "accounts/verify_security_answer.html", {
            "question_text": question_text,
            "locked_out": True,
            "cooldown_minutes": minutes,
        })

    if request.method == "POST":
        answer = (request.POST.get("security_answer") or "").strip().lower()

        if not answer:
            messages.error(request, GENERIC_RESET_ERROR)
            return render(request, "accounts/verify_security_answer.html", {
                "question_text": question_text,
                "attempts_left": PW_RESET_MAX_ATTEMPTS - state.get("attempts", 0),
            })

        if check_password(answer, user.security_answer_hash):
            state["question_verified"] = True
            state["attempts"] = 0
            _save_reset_state(request, state)
            return redirect("reset_password")

        # Wrong answer — bump attempts, possibly lock out
        state["attempts"] = state.get("attempts", 0) + 1
        if state["attempts"] >= PW_RESET_MAX_ATTEMPTS:
            state["cooldown_until"] = time.time() + PW_RESET_COOLDOWN_SECONDS
            _save_reset_state(request, state)
            return render(request, "accounts/verify_security_answer.html", {
                "question_text": question_text,
                "locked_out": True,
                "cooldown_minutes": PW_RESET_COOLDOWN_SECONDS // 60,
            })

        _save_reset_state(request, state)
        messages.error(request, GENERIC_RESET_ERROR)

    return render(request, "accounts/verify_security_answer.html", {
        "question_text": question_text,
        "attempts_left": PW_RESET_MAX_ATTEMPTS - state.get("attempts", 0),
    })


def reset_password(request):
    """Step 3 — set a new password (only reachable after successful verify)."""
    state = _reset_state(request)
    user_id = state.get("user_id")
    if not user_id or not state.get("question_verified"):
        messages.error(request, "Your reset session has expired. Please start again.")
        return redirect("forgot_password")

    user = User.objects.filter(id=user_id).first()
    if not user:
        _clear_reset_state(request)
        messages.error(request, GENERIC_RESET_ERROR)
        return redirect("forgot_password")

    if request.method == "POST":
        pw1 = request.POST.get("password1") or ""
        pw2 = request.POST.get("password2") or ""

        if pw1 != pw2:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/reset_password.html")

        try:
            validate_password(pw1, user=user)
        except ValidationError as e:
            for err in e.messages:
                messages.error(request, err)
            return render(request, "accounts/reset_password.html")

        user.set_password(pw1)
        user.save(update_fields=["password"])

        _clear_reset_state(request)
        messages.success(request, "Password reset successfully. You can now sign in.")
        return redirect("login")

    return render(request, "accounts/reset_password.html")


# ==================== Teacher Views ====================

@login_required
def teacher_dashboard(request):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    all_quizzes = Quiz.objects.filter(teacher=request.user).order_by("-created_at")
    quizzes = all_quizzes.annotate(question_count=Count("questions"))[:10]

    total_quizzes = all_quizzes.count()

    # Per-quiz stats: default to the most recent quiz, or the one selected via ?quiz_id=
    selected_quiz_id = request.GET.get("quiz_id", "").strip()
    selected_quiz = None
    if selected_quiz_id.isdigit():
        selected_quiz = all_quizzes.filter(id=int(selected_quiz_id)).first()
    if selected_quiz is None:
        selected_quiz = all_quizzes.first()

    if selected_quiz:
        quiz_attempts = QuizAttempt.objects.filter(
            quiz=selected_quiz, completed_at__isnull=False
        )
        total_students = quiz_attempts.values("student_id").distinct().count()
        avg_score = quiz_attempts.aggregate(Avg("percentage"))["percentage__avg"] or 0
    else:
        total_students = 0
        avg_score = 0

    context = {
        "show_sidebar": True,
        "quizzes": quizzes,
        "all_quizzes": all_quizzes,
        "selected_quiz": selected_quiz,
        "total_quizzes": total_quizzes,
        "total_students": total_students,
        "average_score": round(avg_score, 1),
    }
    return render(request, "teacher/dashboard.html", context)


@login_required
def my_quizzes(request):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    quizzes = Quiz.objects.filter(teacher=request.user).order_by("-created_at")

    # Search filter
    search = request.GET.get("q", "").strip()
    if search:
        quizzes = quizzes.filter(title__icontains=search)

    # Date filters
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        quizzes = quizzes.filter(created_at__date__gte=date_from)
    if date_to:
        quizzes = quizzes.filter(created_at__date__lte=date_to)

    # Status filter
    status = request.GET.get("status", "")
    if status in ("draft", "published"):
        quizzes = quizzes.filter(status=status)

    return render(request, "teacher/my_quizzes.html", {
        "show_sidebar": True,
        "quizzes": quizzes,
        "search": search,
        "date_from": date_from,
        "date_to": date_to,
        "status_filter": status,
    })


@login_required
def upload_notes(request):
    # Teacher-only guard (safe even if role attribute is missing)
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        messages.error(request, "You do not have permission to access the teacher area.")
        return redirect("student:dashboard")

    if request.method == "POST":
        lecture_text = (request.POST.get("lecture_notes") or "").strip()
        uploaded_file = request.FILES.get("file_upload")
        ai_instructions = (request.POST.get("ai_instructions") or "").strip()

        # Must provide either text or file
        if not lecture_text and not uploaded_file:
            messages.error(request, "Please paste lecture notes or upload a file.")
            return render(
                request,
                "teacher/upload_notes.html",
                {"show_sidebar": True, "lecture_notes": lecture_text, "ai_instructions": ai_instructions},
            )

        # Extract text from uploaded file if provided
        try:
            if uploaded_file:
                file_text = extract_text_from_file(uploaded_file)
                # File text takes precedence; combine if both provided
                lecture_text = file_text if not lecture_text else f"{lecture_text}\n\n{file_text}"
        except ValueError as e:
            messages.error(request, str(e))
            return render(
                request,
                "teacher/upload_notes.html",
                {"show_sidebar": True, "lecture_notes": lecture_text, "ai_instructions": ai_instructions},
            )

        if len(lecture_text) < 50:
            messages.error(request, "Please provide more content to generate meaningful questions.")
            return render(
                request,
                "teacher/upload_notes.html",
                {"show_sidebar": True, "lecture_notes": lecture_text, "ai_instructions": ai_instructions},
            )

        # Save the lecture note
        note = LectureNote.objects.create(
            teacher=request.user,
            title=lecture_text[:50].strip(),
            content=lecture_text,
            file=uploaded_file if uploaded_file else None,
        )

        # Generate quiz questions via AI
        try:
            ai_questions = generate_quiz_questions(lecture_text, instructions=ai_instructions)
        except QuizGenerationError as e:
            messages.error(request, f"Quiz generation failed: {e}")
            return render(
                request,
                "teacher/upload_notes.html",
                {"show_sidebar": True, "lecture_notes": lecture_text, "ai_instructions": ai_instructions},
            )

        # Create Quiz and associated Questions/Options
        quiz = Quiz.objects.create(
            title=f"Quiz: {note.title}",
            teacher=request.user,
            status="draft",
        )

        for i, q_data in enumerate(ai_questions):
            question = Question.objects.create(
                quiz=quiz,
                text=q_data["question"],
                order=i + 1,
            )
            for j, opt_text in enumerate(q_data["options"]):
                Option.objects.create(
                    question=question,
                    text=opt_text,
                    is_correct=(j == q_data["correct_index"]),
                    order=j,
                )

        messages.success(request, "Quiz questions generated! Review and edit them below.")
        return redirect("teacher:edit_questions", quiz_id=quiz.id)

    # GET request
    return render(request, "teacher/upload_notes.html", {"show_sidebar": True})


@login_required
def edit_questions(request, quiz_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    questions = quiz.questions.all().prefetch_related("options")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "publish":
            quiz.status = "published"
            quiz.save()
            messages.success(request, "Quiz published successfully!")
            return redirect("teacher:dashboard")
        elif action == "save_draft":
            quiz.status = "draft"
            quiz.save()
            messages.success(request, "Quiz saved as draft!")
            return redirect("teacher:dashboard")

    return render(request, "teacher/edit_questions.html", {
        "show_sidebar": True,
        "quiz": quiz,
        "questions": questions,
    })


@login_required
def save_quiz(request):
    if request.method != "POST":
        return redirect("teacher:dashboard")

    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    quiz_id = request.POST.get("quiz_id")
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)

    # Delete removed questions
    deleted_ids = request.POST.get("deleted_questions", "")
    if deleted_ids:
        for qid in deleted_ids.split(","):
            qid = qid.strip()
            if qid.isdigit():
                Question.objects.filter(id=int(qid), quiz=quiz).delete()

    # Update quiz title
    quiz_title = (request.POST.get("quiz_title") or "").strip()
    if quiz_title:
        quiz.title = quiz_title

    # Update existing questions and options
    for question in quiz.questions.all():
        new_text = request.POST.get(f"question_text_{question.id}")
        if new_text is not None:
            question.text = new_text
            question.save()

            correct_idx = request.POST.get(f"correct_answer_{question.id}")
            options = list(question.options.all().order_by("order"))
            for i, option in enumerate(options):
                opt_text = request.POST.get(f"option_{question.id}_{i}")
                if opt_text is not None:
                    option.text = opt_text
                option.is_correct = (str(i) == correct_idx)
                option.save()

    # Update quiz settings
    time_limit = request.POST.get("time_limit")
    if time_limit and time_limit.isdigit():
        quiz.time_limit = max(1, min(180, int(time_limit)))

    pass_percentage = request.POST.get("pass_percentage")
    if pass_percentage and pass_percentage.isdigit():
        quiz.pass_percentage = max(1, min(100, int(pass_percentage)))

    # Set quiz status
    action = request.POST.get("action")
    if action == "publish":
        quiz.status = "published"
        quiz.save()
        messages.success(request, "Quiz published successfully!")
    else:
        quiz.status = "draft"
        quiz.save()
        messages.success(request, "Quiz saved as draft!")

    return redirect("teacher:dashboard")


@login_required
def add_question(request, quiz_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)

    # Determine next order number
    max_order = quiz.questions.order_by("-order").values_list("order", flat=True).first() or 0
    question = Question.objects.create(
        quiz=quiz,
        text="New question",
        order=max_order + 1,
    )
    for i in range(4):
        Option.objects.create(
            question=question,
            text=f"Option {i + 1}",
            is_correct=(i == 0),
            order=i,
        )

    return redirect("teacher:edit_questions", quiz_id=quiz.id)


@login_required
def analytics_overview(request):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        return redirect("student:dashboard")

    quizzes = Quiz.objects.filter(teacher=request.user).order_by("-created_at")
    total_quizzes = quizzes.count()
    total_attempts = QuizAttempt.objects.filter(quiz__teacher=request.user).count()
    avg_score = QuizAttempt.objects.filter(
        quiz__teacher=request.user
    ).aggregate(Avg("percentage"))["percentage__avg"] or 0

    pass_count = QuizAttempt.objects.filter(
        quiz__teacher=request.user, percentage__gte=70
    ).count()
    overall_pass_rate = round((pass_count / total_attempts) * 100, 1) if total_attempts else 0

    quiz_stats = []
    for quiz in quizzes:
        q_attempts = QuizAttempt.objects.filter(quiz=quiz)
        attempt_count = q_attempts.count()
        q_agg = q_attempts.aggregate(avg=Avg("percentage"), high=Max("percentage"))
        quiz_avg = q_agg["avg"]
        quiz_high = q_agg["high"]
        q_pass = q_attempts.filter(percentage__gte=70).count()

        quiz_stats.append({
            "quiz": quiz,
            "question_count": quiz.questions.count(),
            "attempt_count": attempt_count,
            "avg_score": round(quiz_avg, 1) if quiz_avg is not None else None,
            "high_score": round(quiz_high, 1) if quiz_high is not None else None,
            "pass_rate": round((q_pass / attempt_count) * 100, 1) if attempt_count else None,
        })

    return render(request, "teacher/analytics_overview.html", {
        "show_sidebar": True,
        "total_quizzes": total_quizzes,
        "total_attempts": total_attempts,
        "average_score": round(avg_score, 1),
        "overall_pass_rate": overall_pass_rate,
        "quiz_stats": quiz_stats,
    })


@login_required
def analytics(request, quiz_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        messages.error(request, "Access denied: teacher account required to view analytics.")
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    questions = quiz.questions.all()
    attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)

    # ── Summary metrics ──
    total_attempts_all = attempts.count()  # raw attempts incl. retakes (for pass rate)
    total_students = attempts.values("student_id").distinct().count()  # unique students
    agg = attempts.aggregate(
        avg_score=Avg("percentage"),
        high_score=Max("percentage"),
        low_score=Min("percentage"),
    )
    avg_score = round(agg["avg_score"], 1) if agg["avg_score"] is not None else 0
    high_score = round(agg["high_score"], 1) if agg["high_score"] is not None else 0
    low_score = round(agg["low_score"], 1) if agg["low_score"] is not None else 0
    pass_count = attempts.filter(percentage__gte=quiz.pass_percentage).count()
    pass_rate = round((pass_count / total_attempts_all) * 100, 1) if total_attempts_all else 0

    # ── Score distribution (bar chart) ──
    buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for pct in attempts.values_list("percentage", flat=True):
        if pct < 20:
            buckets["0-19"] += 1
        elif pct < 40:
            buckets["20-39"] += 1
        elif pct < 60:
            buckets["40-59"] += 1
        elif pct < 80:
            buckets["60-79"] += 1
        else:
            buckets["80-100"] += 1

    # ── Question difficulty (bar chart) + most-missed ──
    question_analytics = []
    total_correct_all = 0
    total_answers_all = 0

    for question in questions:
        total_answers = Answer.objects.filter(question=question).count()
        correct_answers = Answer.objects.filter(question=question, is_correct=True).count()
        total_correct_all += correct_answers
        total_answers_all += total_answers

        if total_answers > 0:
            percent_correct = round((correct_answers / total_answers) * 100, 1)
            percent_incorrect = round(100 - percent_correct, 1)
        else:
            percent_correct = 0
            percent_incorrect = 0

        question_analytics.append({
            "question": question,
            "percent_correct": percent_correct,
            "percent_incorrect": percent_incorrect,
            "total_answers": total_answers,
        })

    most_missed = [q for q in question_analytics if q["percent_incorrect"] > 50]

    # ── Correct vs incorrect pie chart ──
    total_incorrect_all = total_answers_all - total_correct_all

    # ── Attempts over time (line chart) ──
    attempts_by_date = (
        attempts.annotate(date=TruncDate("started_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    timeline_labels = [entry["date"].strftime("%b %d") for entry in attempts_by_date]
    timeline_data = [entry["count"] for entry in attempts_by_date]

    # ── Student performance table (grouped per student) ──
    student_perf_map = {}
    for attempt in attempts.select_related("student").order_by("-started_at"):
        sid = attempt.student_id
        if sid not in student_perf_map:
            student_perf_map[sid] = {"student": attempt.student, "attempts": []}
        student_perf_map[sid]["attempts"].append(attempt)

    student_performance = []
    for sid, data in student_perf_map.items():
        atts = data["attempts"]
        avg = sum(a.percentage for a in atts) / len(atts) if atts else 0
        student_performance.append({
            "student": data["student"],
            "attempt_count": len(atts),
            "avg_score": round(avg, 1),
            "attempts": atts,  # ordered most-recent first
        })
    # Sort: highest average score first
    student_performance.sort(key=lambda x: x["avg_score"], reverse=True)

    # ── JSON for charts ──
    chart_data = json.dumps({
        "score_dist": {"labels": list(buckets.keys()), "data": list(buckets.values())},
        "question_diff": {
            "labels": [f"Q{q['question'].order}" for q in question_analytics],
            "correct": [q["percent_correct"] for q in question_analytics],
            "incorrect": [q["percent_incorrect"] for q in question_analytics],
        },
        "pie": {"correct": total_correct_all, "incorrect": total_incorrect_all},
        "timeline": {"labels": timeline_labels, "data": timeline_data},
    })

    return render(request, "teacher/analytics.html", {
        "show_sidebar": True,
        "quiz": quiz,
        "total_attempts": total_students,
        "avg_score": avg_score,
        "high_score": high_score,
        "low_score": low_score,
        "pass_rate": pass_rate,
        "question_analytics": question_analytics,
        "most_missed_questions": most_missed,
        "student_performance": student_performance,
        "chart_data": chart_data,
    })


# ==================== Student Views ====================

@login_required
def student_dashboard(request):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    # Handle join code / share link submission
    error_message = None
    if request.method == "POST":
        raw = (request.POST.get("access_code") or "").strip()
        if not raw:
            error_message = "Please enter a quiz code or share link."
        else:
            quiz = None
            # Detect a pasted share link — look for "/join/" anywhere in the input
            if "/join/" in raw:
                token = raw.split("/join/")[-1].strip("/")
                quiz = Quiz.objects.filter(share_token=token, status="published").first()
            else:
                # Fall back to 6-char access code
                quiz = Quiz.objects.filter(access_code=raw.upper(), status="published").first()

            if quiz:
                return redirect("student:quiz_preview", quiz_id=quiz.id)
            else:
                error_message = "Invalid or expired code / link. Please check and try again."

    # Get distinct quizzes the student has attempted, with summary stats.
    # Clear the model's default ordering so DISTINCT actually dedupes.
    attempted_quiz_ids = set(
        QuizAttempt.objects.filter(student=request.user)
        .order_by()
        .values_list("quiz_id", flat=True)
    )
    quiz_summaries = []
    for quiz_id in attempted_quiz_ids:
        quiz = Quiz.objects.filter(id=quiz_id).first()
        if not quiz:
            continue
        attempts = QuizAttempt.objects.filter(student=request.user, quiz=quiz)
        best = attempts.order_by("-percentage").first()
        quiz_summaries.append({
            "quiz": quiz,
            "attempt_count": attempts.count(),
            "best_score": round(best.percentage, 1) if best else 0,
            "last_attempt": attempts.order_by("-started_at").first().started_at,
            "passed": best.percentage >= quiz.pass_percentage if best else False,
        })
    # Sort by most recent attempt
    quiz_summaries.sort(key=lambda x: x["last_attempt"], reverse=True)

    # Practice basket summary (count + grouping by quiz title)
    basket_ids = _get_basket(request)
    basket_questions = (
        Question.objects.filter(id__in=basket_ids).select_related("quiz")
        if basket_ids else Question.objects.none()
    )
    basket_by_quiz = {}
    for q in basket_questions:
        key = q.quiz.title
        basket_by_quiz[key] = basket_by_quiz.get(key, 0) + 1
    basket_summary = [{"quiz_title": t, "count": c} for t, c in basket_by_quiz.items()]

    return render(request, "student/dashboard.html", {
        "show_sidebar": False,
        "quiz_summaries": quiz_summaries,
        "error_message": error_message,
        "basket_count": len(basket_ids),
        "basket_summary": basket_summary,
    })


@login_required
def quiz_history(request, quiz_id):
    """Show all attempts for a specific quiz."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = QuizAttempt.objects.filter(
        student=request.user, quiz=quiz
    ).order_by("-started_at")

    best = attempts.order_by("-percentage").first()

    # Build list of unique questions this student has ever answered INCORRECTLY
    # for this quiz — used to populate the "Practice Incorrect Questions" section.
    wrong_question_ids = set(
        Answer.objects.filter(
            attempt__student=request.user,
            attempt__quiz=quiz,
            is_correct=False,
        ).values_list("question_id", flat=True)
    )
    incorrect_questions = quiz.questions.filter(id__in=wrong_question_ids).order_by("order")

    return render(request, "student/quiz_history.html", {
        "show_sidebar": False,
        "quiz": quiz,
        "attempts": attempts,
        "best_score": round(best.percentage, 1) if best else 0,
        "total_attempts": attempts.count(),
        "incorrect_questions": incorrect_questions,
    })


def _get_basket(request):
    """Return the session practice basket as a list of ints."""
    raw = request.session.get("practice_basket", [])
    return [int(i) for i in raw if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]


def _save_basket(request, ids):
    """Save the practice basket as a deduped, sorted list of ints."""
    request.session["practice_basket"] = sorted({int(i) for i in ids})
    request.session.modified = True


@login_required
def practice_basket_add(request, quiz_id):
    """Add the selected question IDs from a quiz to the session practice basket."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method != "POST":
        return redirect("student:quiz_history", quiz_id=quiz.id)

    selected = [int(i) for i in request.POST.getlist("question_ids") if i.isdigit()]
    if not selected:
        messages.error(request, "Please select at least one question to add.")
        return redirect("student:quiz_history", quiz_id=quiz.id)

    # Only accept IDs that actually belong to this quiz, guard against tampering
    valid_ids = set(quiz.questions.filter(id__in=selected).values_list("id", flat=True))
    if not valid_ids:
        return redirect("student:quiz_history", quiz_id=quiz.id)

    current = set(_get_basket(request))
    current.update(valid_ids)
    _save_basket(request, current)
    messages.success(request, f"Added {len(valid_ids)} question{'s' if len(valid_ids) != 1 else ''} to your practice basket.")
    return redirect("student:quiz_history", quiz_id=quiz.id)


@login_required
def practice_basket_clear(request):
    """Empty the session practice basket."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    request.session["practice_basket"] = []
    request.session.modified = True
    messages.success(request, "Practice basket cleared.")
    return redirect("student:dashboard")


@login_required
def combined_practice(request):
    """Render a practice session using all questions in the session basket."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    ids = _get_basket(request)
    if not ids:
        messages.error(request, "Your practice basket is empty.")
        return redirect("student:dashboard")

    questions = (
        Question.objects.filter(id__in=ids)
        .select_related("quiz")
        .prefetch_related("options")
        .order_by("quiz__title", "order")
    )
    if not questions.exists():
        request.session["practice_basket"] = []
        request.session.modified = True
        messages.error(request, "Those questions are no longer available.")
        return redirect("student:dashboard")

    return render(request, "student/combined_practice.html", {
        "show_sidebar": False,
        "questions": questions,
        "question_ids_csv": ",".join(str(q.id) for q in questions),
    })


@login_required
def combined_practice_submit(request):
    """Score a combined practice submission in memory (not persisted)."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    if request.method != "POST":
        return redirect("student:dashboard")

    ids_csv = request.POST.get("question_ids_csv", "")
    selected_ids = [int(i) for i in ids_csv.split(",") if i.strip().isdigit()]
    if not selected_ids:
        return redirect("student:dashboard")

    questions = (
        Question.objects.filter(id__in=selected_ids)
        .select_related("quiz")
        .prefetch_related("options")
    )

    score = 0
    total = questions.count()
    question_results = []
    for question in questions:
        selected_option_id = request.POST.get(f"question_{question.id}")
        selected_option = None
        is_correct = False
        if selected_option_id and selected_option_id.isdigit():
            selected_option = question.options.filter(id=int(selected_option_id)).first()
            if selected_option and selected_option.is_correct:
                is_correct = True
                score += 1
        correct_option = question.options.filter(is_correct=True).first()
        question_results.append({
            "question": question,
            "quiz": question.quiz,
            "selected_answer": selected_option,
            "correct_answer": correct_option,
            "is_correct": is_correct,
        })

    percentage = round((score / total) * 100, 1) if total else 0

    # Clear the basket once the combined session is finished
    request.session["practice_basket"] = []
    request.session.modified = True

    return render(request, "student/combined_practice_results.html", {
        "show_sidebar": False,
        "score": score,
        "total_questions": total,
        "percentage": percentage,
        "question_results": question_results,
    })


@login_required
def practice_quiz(request, quiz_id):
    """Render a practice quiz containing only the selected questions.

    Accessed via POST from quiz_history with question_ids[] checkbox values.
    Practice attempts are NOT persisted — they don't affect stats or best score.
    """
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, status="published")

    if request.method != "POST":
        return redirect("student:quiz_history", quiz_id=quiz.id)

    selected_ids = request.POST.getlist("question_ids")
    selected_ids = [int(i) for i in selected_ids if i.isdigit()]
    if not selected_ids:
        messages.error(request, "Please select at least one question to practice.")
        return redirect("student:quiz_history", quiz_id=quiz.id)

    questions = quiz.questions.filter(id__in=selected_ids).prefetch_related("options").order_by("order")

    return render(request, "student/practice_quiz.html", {
        "show_sidebar": False,
        "quiz": quiz,
        "questions": questions,
        "question_ids_csv": ",".join(str(q.id) for q in questions),
    })


@login_required
def practice_submit(request, quiz_id):
    """Score a submitted practice quiz in memory (not persisted)."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, status="published")

    if request.method != "POST":
        return redirect("student:quiz_history", quiz_id=quiz.id)

    ids_csv = request.POST.get("question_ids_csv", "")
    selected_ids = [int(i) for i in ids_csv.split(",") if i.strip().isdigit()]
    if not selected_ids:
        return redirect("student:quiz_history", quiz_id=quiz.id)

    questions = quiz.questions.filter(id__in=selected_ids).prefetch_related("options")

    score = 0
    total = questions.count()
    question_results = []
    for question in questions:
        selected_option_id = request.POST.get(f"question_{question.id}")
        selected_option = None
        is_correct = False
        if selected_option_id and selected_option_id.isdigit():
            selected_option = question.options.filter(id=int(selected_option_id)).first()
            if selected_option and selected_option.is_correct:
                is_correct = True
                score += 1
        correct_option = question.options.filter(is_correct=True).first()
        question_results.append({
            "question": question,
            "selected_answer": selected_option,
            "correct_answer": correct_option,
            "is_correct": is_correct,
        })

    percentage = round((score / total) * 100, 1) if total else 0

    return render(request, "student/practice_results.html", {
        "show_sidebar": False,
        "quiz": quiz,
        "score": score,
        "total_questions": total,
        "percentage": percentage,
        "question_results": question_results,
    })


@login_required
def join_quiz_by_link(request, token):
    """Allow students to join a quiz via a shared link token."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("login")

    quiz = get_object_or_404(Quiz, share_token=token, status="published")
    return redirect("student:quiz_preview", quiz_id=quiz.id)


@login_required
def quiz_preview(request, quiz_id):
    """Show quiz details before starting."""
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, status="published")
    question_count = quiz.questions.count()
    previous_attempts = QuizAttempt.objects.filter(
        quiz=quiz, student=request.user
    ).order_by("-started_at")[:5]

    return render(request, "student/quiz_preview.html", {
        "show_sidebar": False,
        "quiz": quiz,
        "question_count": question_count,
        "previous_attempts": previous_attempts,
    })


@login_required
def student_quiz(request, quiz_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, status="published")
    questions = quiz.questions.all().prefetch_related("options")

    if request.method == "POST":
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=request.user,
            total_questions=questions.count(),
            percentage=0,
        )

        score = 0
        for question in questions:
            selected_option_id = request.POST.get(f"question_{question.id}")
            if selected_option_id:
                selected_option = Option.objects.get(id=selected_option_id)
                is_correct = selected_option.is_correct
                if is_correct:
                    score += 1

                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_option=selected_option,
                    is_correct=is_correct,
                )

        attempt.score = score
        attempt.percentage = round((score / questions.count()) * 100, 1) if questions.count() else 0
        attempt.completed_at = timezone.now()
        attempt.save()

        return redirect("student:results", quiz_id=quiz.id, attempt_id=attempt.id)

    return render(request, "student/quiz.html", {
        "show_sidebar": False,
        "quiz": quiz,
        "time_limit": quiz.time_limit,
        "questions": questions,
    })


@login_required
def student_results(request, quiz_id, attempt_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "student" and not request.user.is_superuser:
        return redirect("teacher:dashboard")

    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        student=request.user,
        quiz_id=quiz_id
    )

    answers = attempt.answers.all().select_related("question", "selected_option")

    question_results = []
    for answer in answers:
        correct_option = answer.question.options.filter(is_correct=True).first()
        question_results.append({
            "question": answer.question,
            "selected_answer": answer.selected_option,
            "correct_answer": correct_option,
            "is_correct": answer.is_correct,
            "status": "correct" if answer.is_correct else "incorrect",
        })

    pass_pct = attempt.quiz.pass_percentage
    if attempt.percentage >= pass_pct:
        result_status = "pass"
        feedback = "Great job! You have a solid understanding of the material."
    else:
        result_status = "fail"
        feedback = f"You needed {pass_pct}% to pass. Review the questions you missed to improve your understanding."

    return render(request, "student/results.html", {
        "show_sidebar": False,
        "score": attempt.score,
        "total_questions": attempt.total_questions,
        "percentage": attempt.percentage,
        "pass_percentage": pass_pct,
        "result_status": result_status,
        "question_results": question_results,
        "feedback_message": feedback,
    })


@login_required
def export_analytics(request, quiz_id):
    role = (getattr(request.user, "role", "") or "").lower()
    if role != "teacher" and not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect("teacher:dashboard")

    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="analytics_{quiz.id}.csv"'

    writer = csv.writer(response)

    # Quiz info
    writer.writerow(["Quiz Analytics Report"])
    writer.writerow(["Quiz Title", quiz.title])
    writer.writerow(["Created", quiz.created_at.strftime("%Y-%m-%d")])
    writer.writerow([])

    # Summary stats
    attempts = QuizAttempt.objects.filter(quiz=quiz, completed_at__isnull=False)
    total = attempts.count()
    agg = attempts.aggregate(avg=Avg("percentage"), high=Max("percentage"), low=Min("percentage"))
    pass_count = attempts.filter(percentage__gte=quiz.pass_percentage).count()

    writer.writerow(["Summary"])
    writer.writerow(["Total Attempts", total])
    writer.writerow(["Average Score", f"{round(agg['avg'], 1)}%" if agg["avg"] else "N/A"])
    writer.writerow(["Highest Score", f"{round(agg['high'], 1)}%" if agg["high"] else "N/A"])
    writer.writerow(["Lowest Score", f"{round(agg['low'], 1)}%" if agg["low"] else "N/A"])
    writer.writerow(["Pass Mark", f"{quiz.pass_percentage}%"])
    writer.writerow(["Pass Rate", f"{round((pass_count / total) * 100, 1)}%" if total else "N/A"])
    writer.writerow([])

    # Question breakdown
    writer.writerow(["Question Breakdown"])
    writer.writerow(["#", "Question", "Total Responses", "Correct %", "Incorrect %"])
    for question in quiz.questions.all():
        total_ans = Answer.objects.filter(question=question).count()
        correct_ans = Answer.objects.filter(question=question, is_correct=True).count()
        pct_correct = round((correct_ans / total_ans) * 100, 1) if total_ans else 0
        pct_incorrect = round(100 - pct_correct, 1) if total_ans else 0
        writer.writerow([f"Q{question.order}", question.text, total_ans, f"{pct_correct}%", f"{pct_incorrect}%"])
    writer.writerow([])

    # Student performance
    writer.writerow(["Student Performance"])
    writer.writerow(["Student", "Score", "Total Questions", "Percentage", "Result", "Date"])
    for attempt in attempts.select_related("student").order_by("-started_at"):
        writer.writerow([
            attempt.student.get_full_name() or attempt.student.username,
            attempt.score,
            attempt.total_questions,
            f"{attempt.percentage}%",
            "Passed" if attempt.percentage >= quiz.pass_percentage else "Failed",
            attempt.started_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response
