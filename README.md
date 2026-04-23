# SmartLecture AI

An AI-powered quiz learning system built with Django. Teachers upload lecture notes and the system automatically generates multiple-choice and true/false quizzes using the Claude AI API. Students join quizzes via access codes or share links, attempt them under timed conditions, and practise incorrect answers.

---

## Features

### Teacher
- **AI Quiz Generation** — paste lecture notes or upload a PDF/DOCX file; Claude generates questions (4-option MCQ and true/false) automatically
- **Manual editing** — add, edit, or remove individual questions after generation
- **Quiz management** — draft / publish workflow; each quiz gets a 6-character access code and a shareable link
- **Analytics overview** — see all quizzes at a glance with attempt counts and pass rates
- **Per-quiz analytics** — unique student count, average score, pass rate, and a sortable question breakdown (Default / Hardest / Easiest); expandable per-student rows showing every attempt

### Student
- **Join by code or link** — enter the 6-char access code or paste the full share link from the teacher
- **Timed quiz** — one question at a time with a countdown timer and progress bar
- **Results & history** — score, pass/fail, per-question breakdown; all past attempts for every quiz in one place
- **Practice mode** — select specific incorrect questions from any quiz and redo them (not saved to analytics)
- **Practice basket** — pick questions across multiple quizzes, collect them in a basket on the dashboard, then take a single combined practice session

### Accounts
- Separate Teacher and Student roles on registration
- Security-question-based Forgot Password (no email required) — 3-attempt limit with a 15-minute cooldown
- Dark mode toggle (persists in localStorage; respects OS preference on first visit)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.x (Python 3.12) |
| Database | SQLite (dev) |
| AI | Anthropic Claude API (`claude-sonnet-4-*`) |
| File parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Frontend | Vanilla JS, Chart.js, CSS custom properties |
| Static files | WhiteNoise (production) |

---

## Project Structure

```
AIQuizLearningSystem_FYP/
├── AIQuizLearningSystem_FYP/   # Django project settings & WSGI
├── quiz_app/
│   ├── models.py               # User, Quiz, Question, Option, QuizAttempt, Answer, LectureNote
│   ├── views.py                # All views (teacher, student, auth, forgot-password)
│   ├── forms.py                # LoginForm, RegisterForm (with security question)
│   ├── urls.py                 # Namespaced URL patterns (teacher:, student:)
│   ├── ai_service.py           # Claude API integration & file text extraction
│   └── migrations/
├── templates/
│   ├── base.html               # Base layout with dark-mode init script
│   ├── accounts/               # login, register, forgot-password (3 steps)
│   ├── components/             # navbar, sidebar, theme toggle
│   ├── teacher/                # dashboard, upload, my-quizzes, edit, analytics
│   └── student/                # dashboard, quiz, results, history, practice
├── static/
│   ├── css/styles.css          # Full design system + dark-mode overrides
│   └── js/
│       ├── main.js             # Dropdown, dark-mode toggle, file upload
│       └── quiz.js             # Timer, navigation, submit modal
└── media/                      # Uploaded lecture note files
```

---

## Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/AIQuizLearningSystem_FYP.git
cd AIQuizLearningSystem_FYP
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install django anthropic PyMuPDF python-docx whitenoise
```

### 4. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # Windows: set ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Apply migrations & create a superuser
```bash
python manage.py migrate
python manage.py createsuperuser   # optional
```

### 6. Run the development server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key for quiz generation |
| `SECRET_KEY` | Production | Django secret key (set a strong random value) |
| `DEBUG` | Production | Set to `False` in production |

---

## Deployment (PythonAnywhere)

1. Push to GitHub, then clone inside a PythonAnywhere Bash console
2. Create a virtualenv: `mkvirtualenv --python=python3.12 smartlecture-env`
3. `pip install django anthropic PyMuPDF python-docx whitenoise`
4. In `settings.py`: set `DEBUG = False`, add your domain to `ALLOWED_HOSTS`, set `STATIC_ROOT`
5. Run `python manage.py collectstatic` and `python manage.py migrate`
6. Configure the Web tab: point the WSGI file at your project, set the virtualenv path
7. Add a `/static/` → `staticfiles/` mapping in the Static Files section
8. Set `ANTHROPIC_API_KEY` as an environment variable
9. Reload the web app

---

## Key URLs

| URL | Description |
|---|---|
| `/` | Login |
| `/register/` | Register (teacher or student) |
| `/forgot-password/` | Password reset via security question |
| `/teacher/dashboard/` | Teacher home |
| `/teacher/upload/` | Upload notes & generate quiz |
| `/teacher/quiz/<id>/edit/` | Edit questions |
| `/teacher/quiz/<id>/analytics/` | Per-quiz analytics |
| `/student/dashboard/` | Student home (join by code or link) |
| `/student/quiz/<id>/` | Take a quiz |
| `/student/quiz/<id>/history/` | Attempt history & practice mode |
| `/student/join/<token>/` | Join via share link |
| `/admin/` | Django admin panel |

---
## License

This project was built as a Final Year Project (FYP). All rights reserved.
