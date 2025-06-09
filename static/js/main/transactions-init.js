/**
 * Transactions Initialization Script
 * Entry point voor de transactions pagina
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check dependencies
    if (typeof API === 'undefined' || typeof UI === 'undefined') {
        console.error('Common utilities not loaded!');
        return;
    }
    
    if (typeof TransactionsManager === 'undefined') {
        console.error('Transactions module not loaded!');
        return;
    }
    
    console.log('Transactions dependencies loaded successfully');
    console.log('Transactions module initialized');
    
    // Optional: Log current table stats
    const tableRows = document.querySelectorAll('#transactiesTable tbody tr');
    const searchTerm = new URLSearchParams(window.location.search).get('zoek');
    
    if (searchTerm) {
        console.log(`Showing ${tableRows.length} transactions for search: "${searchTerm}"`);
    } else {
        console.log(`Showing ${tableRows.length} transactions`);
    }
});