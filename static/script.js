// Global script file for common functionality

document.addEventListener('DOMContentLoaded', function() {
    // Highlight active nav item
    const current = window.location.pathname.split('/').pop() || 'index.html';
    const navLinks = document.querySelectorAll('nav a');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href').split('/').pop() || 'index.html';
        if (href === current) {
            link.classList.add('active');
        }
    });
});

// Utility function to show notifications
function showNotification(message, type = 'info', duration = 3000) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alert.style.position = 'fixed';
    alert.style.top = '20px';
    alert.style.right = '20px';
    alert.style.zIndex = '9999';
    alert.style.maxWidth = '500px';
    
    document.body.appendChild(alert);
    
    setTimeout(() => {
        alert.remove();
    }, duration);
}

// API helper function
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}
