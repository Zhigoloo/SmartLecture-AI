from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.hashers import make_password
from .models import User, Quiz, Question, Option, LectureNote, SECURITY_QUESTIONS


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-input',
        'placeholder': 'you@example.com'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input',
        'placeholder': '••••••••'
    }))
    role = forms.ChoiceField(choices=[('teacher', 'Teacher'), ('student', 'Student')])


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]

    full_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={
        'class': 'form-input',
        'placeholder': 'John Doe'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-input',
        'placeholder': 'you@example.com'
    }))
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    security_question = forms.ChoiceField(
        choices=[('', 'Select a security question...')] + list(SECURITY_QUESTIONS),
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    security_answer = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your answer',
            'autocomplete': 'off',
        }),
        help_text="Case-insensitive. You'll need this to reset your password."
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'full_name', 'role', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_security_answer(self):
        answer = (self.cleaned_data.get('security_answer') or '').strip()
        if len(answer) < 2:
            raise forms.ValidationError("Security answer must be at least 2 characters.")
        return answer

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        full_name = self.cleaned_data['full_name'].split(' ', 1)
        user.first_name = full_name[0]
        if len(full_name) > 1:
            user.last_name = full_name[1]

        user.security_question = self.cleaned_data['security_question']
        # Normalise: lowercase + stripped, then hash with Django's password hasher
        normalised = self.cleaned_data['security_answer'].strip().lower()
        user.security_answer_hash = make_password(normalised)

        if commit:
            user.save()
        return user


class LectureNoteForm(forms.ModelForm):
    lecture_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 12,
            'placeholder': 'Paste your lecture notes here...'
        }),
        required=False
    )
    file_upload = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'file-input',
            'accept': '.pdf,.docx,.doc'
        })
    )

    class Meta:
        model = LectureNote
        fields = ['lecture_notes', 'file_upload']


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'status', 'time_limit']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'time_limit': forms.NumberInput(attrs={'class': 'form-input'}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'order']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'question-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-input'}),
        }