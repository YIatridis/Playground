// Main JavaScript file for InvoiceScan

// Utility function to format currency
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
    }).format(amount);
}

// Utility function to format dates
function formatDate(dateString) {
    // Assuming input format is DD/MM/YYYY
    const parts = dateString.split('/');
    if (parts.length !== 3) return dateString; // Return original if not in expected format
    
    // Create date object (months are 0-indexed in JS)
    const date = new Date(parts[2], parts[1] - 1, parts[0]);
    
    // Format using browser's locale
    return date.toLocaleDateString();
}

// Function to handle API errors
function handleApiError(error) {
    console.error('API Error:', error);
    
    // Display user-friendly error
    return error.response?.data?.detail || 
           error.message || 
           'An unexpected error occurred. Please try again.';
}

// Authentication functions
const auth = {
    getToken: function() {
        return localStorage.getItem('access_token');
    },
    
    isAuthenticated: function() {
        return !!this.getToken();
    },
    
    logout: function() {
        localStorage.removeItem('access_token');
        window.location.href = '/';
    },
    
    redirectToLogin: function() {
        window.location.href = '/login';
    },
    
    checkAuth: function() {
        if (!this.isAuthenticated()) {
            this.redirectToLogin();
            return false;
        }
        return true;
    }
};

// Initialize components on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltip components
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle logout button clicks
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            auth.logout();
        });
    }
    
    // Check authentication status and update UI
    updateAuthUI();
});

// Update UI based on authentication status
function updateAuthUI() {
    const isAuthenticated = auth.isAuthenticated();
    
    // Update navigation
    const authenticatedNav = document.getElementById('authenticated-nav');
    const unauthenticatedNav = document.getElementById('unauthenticated-nav');
    
    if (authenticatedNav && unauthenticatedNav) {
        if (isAuthenticated) {
            authenticatedNav.classList.remove('d-none');
            unauthenticatedNav.classList.add('d-none');
        } else {
            authenticatedNav.classList.add('d-none');
            unauthenticatedNav.classList.remove('d-none');
        }
    }
}

// Add custom form validation
function validateForm(form) {
    form.classList.add('was-validated');
    return form.checkValidity();
}
