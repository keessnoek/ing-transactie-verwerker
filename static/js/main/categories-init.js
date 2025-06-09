/**
 * Categories Initialization Script
 * Entry point voor de categories pagina
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check dependencies
    if (typeof API === 'undefined' || typeof UI === 'undefined') {
        console.error('Common utilities not loaded!');
        return;
    }
    
    if (typeof CategoriesManager === 'undefined') {
        console.error('Categories module not loaded!');
        return;
    }
    
    console.log('Categories dependencies loaded successfully');
    console.log('Categories module initialized');
    
    // Optional: Log current categories count
    const categoryRows = document.querySelectorAll('tbody tr');
    console.log(`Managing ${categoryRows.length} categories`);
});