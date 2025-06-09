/**
 * Auto Categorization Initialization Script
 * Entry point voor de auto categorization pagina
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check dependencies
    if (typeof API === 'undefined' || typeof UI === 'undefined' || typeof Format === 'undefined') {
        console.error('Common utilities not loaded!');
        return;
    }
    
    if (typeof AutoCategorizationManager === 'undefined') {
        console.error('Auto Categorization module not loaded!');
        return;
    }
    
    console.log('Auto Categorization dependencies loaded successfully');
    console.log('Auto Categorization module initialized');
});