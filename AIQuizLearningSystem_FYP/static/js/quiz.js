/**
 * Quiz Navigation JavaScript
 * Handles quiz question navigation, progress tracking, and submission
 */

let currentQuestionIndex = 0;
let totalQuestions = 0;
let answers = {};
let timerInterval;
let timeRemaining; // in seconds

document.addEventListener('DOMContentLoaded', function() {
    // Initialize quiz
    const questionCards = document.querySelectorAll('.question-card');
    totalQuestions = questionCards.length;
    
    // Initialize timer if time limit exists
    const timeLimitElement = document.getElementById('timeRemaining');
    if (timeLimitElement && typeof timeLimit !== 'undefined') {
        timeRemaining = timeLimit * 60; // Convert minutes to seconds
        startTimer();
    }
    
    // Track answer selections
    const radioButtons = document.querySelectorAll('.option-radio');
    radioButtons.forEach(function(radio) {
        radio.addEventListener('change', function() {
            const questionNumber = this.getAttribute('data-question');
            answers[questionNumber] = this.value;
            updateNavigationButtons();
        });
    });
    
    // Initialize navigation buttons
    updateNavigationButtons();
});

function startTimer() {
    timerInterval = setInterval(function() {
        timeRemaining--;
        
        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            alert('Time is up! Submitting your quiz...');
            submitQuiz();
            return;
        }
        
        updateTimerDisplay();
    }, 1000);
}

function updateTimerDisplay() {
    const minutes = Math.floor(timeRemaining / 60);
    const seconds = timeRemaining % 60;
    const display = minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
    
    const timerElement = document.getElementById('timeRemaining');
    if (timerElement) {
        timerElement.textContent = display + ' remaining';
    }
}

function nextQuestion() {
    if (currentQuestionIndex < totalQuestions - 1) {
        // Hide current question
        const questions = document.querySelectorAll('.question-card');
        questions[currentQuestionIndex].classList.remove('active');
        
        // Show next question
        currentQuestionIndex++;
        questions[currentQuestionIndex].classList.add('active');
        
        // Update UI
        updateProgress();
        updateNavigationButtons();
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function previousQuestion() {
    if (currentQuestionIndex > 0) {
        // Hide current question
        const questions = document.querySelectorAll('.question-card');
        questions[currentQuestionIndex].classList.remove('active');
        
        // Show previous question
        currentQuestionIndex--;
        questions[currentQuestionIndex].classList.add('active');
        
        // Update UI
        updateProgress();
        updateNavigationButtons();
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function updateProgress() {
    const progress = ((currentQuestionIndex + 1) / totalQuestions) * 100;
    
    // Update progress bar
    const progressFill = document.getElementById('progressFill');
    if (progressFill) {
        progressFill.style.width = progress + '%';
    }
    
    // Update current question number
    const currentQuestionElement = document.getElementById('currentQuestion');
    if (currentQuestionElement) {
        currentQuestionElement.textContent = currentQuestionIndex + 1;
    }
    
    // Update progress percentage
    const progressPercent = document.getElementById('progressPercent');
    if (progressPercent) {
        progressPercent.textContent = Math.round(progress) + '% Complete';
    }
}

function updateNavigationButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    
    // Update previous button
    if (prevBtn) {
        prevBtn.disabled = currentQuestionIndex === 0;
    }
    
    // Check if current question is answered
    const currentQuestion = currentQuestionIndex + 1;
    const isAnswered = answers.hasOwnProperty(currentQuestion);
    
    // Show/hide next vs submit button
    if (currentQuestionIndex === totalQuestions - 1) {
        if (nextBtn) nextBtn.style.display = 'none';
        if (submitBtn) {
            submitBtn.style.display = 'flex';
            submitBtn.disabled = !isAnswered;
        }
    } else {
        if (nextBtn) {
            nextBtn.style.display = 'flex';
            nextBtn.disabled = !isAnswered;
        }
        if (submitBtn) submitBtn.style.display = 'none';
    }
}

function confirmSubmit() {
    const modal = document.getElementById('confirmModal');
    if (modal) {
        modal.classList.add('show');
    }
}

function closeModal() {
    const modal = document.getElementById('confirmModal');
    if (modal) {
        modal.classList.remove('show');
    }
}

function submitQuiz() {
    // Stop timer
    if (timerInterval) {
        clearInterval(timerInterval);
    }
    
    // Submit the form
    const form = document.getElementById('quizForm');
    if (form) {
        form.submit();
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('confirmModal');
    if (event.target === modal) {
        closeModal();
    }
});
