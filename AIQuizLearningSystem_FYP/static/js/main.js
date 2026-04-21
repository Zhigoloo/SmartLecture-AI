/**
 * Main JavaScript for SmartLecture AI
 * Handles global functionality like dropdown menus
 */

// Toggle profile dropdown
function toggleDropdown() {
    const dropdown = document.getElementById('profileDropdown');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

// Theme toggle.
// The initial data-theme on <html> is applied by an inline script in <head>
// (to avoid a flash). Here we paint the correct icon into every toggle button
// once the DOM is ready, and handle user clicks.
const MOON_ICON = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
const SUN_ICON =
    '<circle cx="12" cy="12" r="5"></circle>' +
    '<line x1="12" y1="1" x2="12" y2="3"></line>' +
    '<line x1="12" y1="21" x2="12" y2="23"></line>' +
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>' +
    '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>' +
    '<line x1="1" y1="12" x2="3" y2="12"></line>' +
    '<line x1="21" y1="12" x2="23" y2="12"></line>' +
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>' +
    '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';

function applyThemeIcon() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    // Show a sun in dark mode (click to go light), moon in light mode (click to go dark).
    const markup = isDark ? SUN_ICON : MOON_ICON;
    document.querySelectorAll('.theme-toggle-icon').forEach(function(svg) {
        svg.innerHTML = markup;
    });
}

function toggleTheme() {
    const root = document.documentElement;
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    if (next === 'dark') {
        root.setAttribute('data-theme', 'dark');
    } else {
        root.removeAttribute('data-theme');
    }
    try { localStorage.setItem('theme', next); } catch (e) { /* ignore */ }
    applyThemeIcon();
}

// Paint the icon as soon as the DOM is ready.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyThemeIcon);
} else {
    applyThemeIcon();
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const profileDropdown = document.querySelector('.profile-dropdown');
    const dropdown = document.getElementById('profileDropdown');
    
    if (dropdown && profileDropdown) {
        if (!profileDropdown.contains(event.target)) {
            dropdown.classList.remove('show');
        }
    }
});

// File upload preview
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file_upload');
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name;
            const uploadContent = document.getElementById('uploadContent');
            const uploadSuccess = document.getElementById('uploadSuccess');
            const uploadFilename = document.getElementById('uploadFilename');
            
            if (fileName) {
                uploadContent.style.display = 'none';
                uploadSuccess.style.display = 'block';
                uploadFilename.textContent = fileName;
            }
        });
    }
});
