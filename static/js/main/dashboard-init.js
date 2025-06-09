/**
 * Dashboard Initialization Script
 * Entry point voor de dashboard pagina
 */

// Wait for all dependencies to load
document.addEventListener('DOMContentLoaded', function() {
    // Check if all required dependencies are loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js is not loaded!');
        return;
    }
    
    if (typeof bootstrap === 'undefined') {
        console.error('Bootstrap is not loaded!');
        return;
    }
    
    if (typeof API === 'undefined' || typeof Format === 'undefined') {
        console.error('Common utilities not loaded!');
        return;
    }
    
    if (typeof DashboardManager === 'undefined') {
        console.error('Dashboard module not loaded!');
        return;
    }
    
    console.log('Dashboard dependencies loaded successfully');
    
    // Dashboard is automatically initialized by the DashboardManager class
    console.log('Dashboard initialized');
});