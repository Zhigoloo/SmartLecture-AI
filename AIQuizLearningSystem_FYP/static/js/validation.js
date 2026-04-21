/**
 * Form Validation JavaScript
 * Handles client-side validation for login and registration forms
 */

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    // Login form validation
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Clear previous errors
            clearErrors();
            
            // Validate role
            const roleSelected = document.querySelector('input[name="role"]:checked');
            if (!roleSelected) {
                showError('roleError', 'Please select a role');
                isValid = false;
            }
            
            // Validate email
            const email = document.getElementById('email').value.trim();
            if (!email) {
                showError('emailError', 'Email is required');
                isValid = false;
            } else if (!isValidEmail(email)) {
                showError('emailError', 'Please enter a valid email address');
                isValid = false;
            }
            
            // Validate password
            const password = document.getElementById('password').value;
            if (!password) {
                showError('passwordError', 'Password is required');
                isValid = false;
            } else if (password.length < 6) {
                showError('passwordError', 'Password must be at least 6 characters');
                isValid = false;
            }
            
            if (!isValid) {
                e.preventDefault();
            }
        });
    }
    
    // Register form validation
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Clear previous errors
            clearErrors();
            
            // Validate role
            const roleSelected = document.querySelector('input[name="role"]:checked');
            if (!roleSelected) {
                alert('Please select a role');
                isValid = false;
            }
            
            // Validate full name
            const fullName = document.getElementById('full_name').value.trim();
            if (!fullName) {
                alert('Full name is required');
                isValid = false;
            }
            
            // Validate email
            const email = document.getElementById('email').value.trim();
            if (!email) {
                alert('Email is required');
                isValid = false;
            } else if (!isValidEmail(email)) {
                alert('Please enter a valid email address');
                isValid = false;
            }
            
            // Validate password
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            
            if (!password) {
                alert('Password is required');
                isValid = false;
            } else if (password.length < 6) {
                alert('Password must be at least 6 characters');
                isValid = false;
            } else if (password !== confirmPassword) {
                alert('Passwords do not match');
                isValid = false;
            }
            
            if (!isValid) {
                e.preventDefault();
            }
        });
    }
    
    // Helper function to validate email
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    // Helper function to show error
    function showError(elementId, message) {
        const errorElement = document.getElementById(elementId);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'flex';
        }
    }
    
    // Helper function to clear all errors
    function clearErrors() {
        const errorElements = document.querySelectorAll('.error-message');
        errorElements.forEach(function(element) {
            element.textContent = '';
            element.style.display = 'none';
        });
    }
});
