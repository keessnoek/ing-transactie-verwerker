/**
 * Transactions Module - Table management, sorting en category updates
 * ING Transactie Verwerker
 */

class TransactionsManager {
    constructor() {
        this.currentSort = null;
        this.currentOrder = null;
        this.searchTerm = null;
        
        this.init();
    }

    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        // Haal huidige sort parameters op uit de template data
        this.getCurrentSortFromDOM();
        
        // Setup event listeners
        this.setupSortingHandlers();
        this.setupCategoryUpdateHandlers();
        this.setupColumnToggleHandlers();
        this.setupSearchForm();
        
        console.log('Transactions module initialized');
    }

    getCurrentSortFromDOM() {
        // Deze waarden worden vanuit de template doorgegeven
        const sortableHeaders = document.querySelectorAll('.sortable-header');
        sortableHeaders.forEach(header => {
            const icon = header.querySelector('i');
            if (icon && icon.classList.contains('text-primary')) {
                this.currentSort = header.getAttribute('data-column');
                this.currentOrder = icon.classList.contains('fa-sort-up') ? 'asc' : 'desc';
            }
        });
        
        // Haal search term op uit search input
        const searchInput = document.querySelector('input[name="zoek"]');
        if (searchInput) {
            this.searchTerm = searchInput.value || null;
        }
    }

    setupSortingHandlers() {
        const sortableHeaders = document.querySelectorAll('.sortable-header');
        
        sortableHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            
            // Remove any existing onclick attributes
            header.removeAttribute('onclick');
            
            header.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleSort(header);
            });
            
            // Hover effect
            header.addEventListener('mouseenter', () => {
                if (!header.classList.contains('sorting-active')) {
                    header.style.backgroundColor = '#e9ecef';
                }
            });
            
            header.addEventListener('mouseleave', () => {
                if (!header.classList.contains('sorting-active')) {
                    header.style.backgroundColor = '';
                }
            });
        });
    }

    handleSort(headerElement) {
        const column = headerElement.getAttribute('data-column');
        let newOrder = 'desc'; // Default order
        
        // Als we al op deze kolom sorteren, flip de order
        if (column === this.currentSort) {
            newOrder = this.currentOrder === 'asc' ? 'desc' : 'asc';
        } else {
            // Voor tekst kolommen start met ascending
            if (['naam', 'code', 'categorie'].includes(column)) {
                newOrder = 'asc';
            }
        }
        
        // Toon loading state
        this.showSortingLoading(headerElement);
        
        // Bouw nieuwe URL
        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set('sort', column);
        urlParams.set('order', newOrder);
        
        // Navigeer naar nieuwe URL
        window.location.href = window.location.pathname + '?' + urlParams.toString();
    }

    showSortingLoading(headerElement) {
        const icon = headerElement.querySelector('i');
        if (icon) {
            icon.className = 'fas fa-spinner fa-spin text-primary';
        }
        headerElement.style.backgroundColor = '#e3f2fd';
        headerElement.classList.add('sorting-active');
    }

    setupCategoryUpdateHandlers() {
        const categorySelects = document.querySelectorAll('.categorie-select');
        
        categorySelects.forEach(select => {
            // Remove any existing onchange attributes
            select.removeAttribute('onchange');
            
            select.addEventListener('change', (e) => {
                this.updateCategorie(e.target);
            });
        });
    }

    async updateCategorie(selectElement) {
        const transactieId = selectElement.getAttribute('data-transactie-id');
        const categorieId = selectElement.value;
        
        // Show loading state
        const originalBackgroundColor = selectElement.style.backgroundColor;
        selectElement.style.backgroundColor = '#fff3cd';
        selectElement.disabled = true;
        
        UI.showLoading('loadingIndicator');
        
        try {
            const formData = `transactie_id=${transactieId}&categorie_id=${categorieId}`;
            const response = await API.postForm('/transactions/update-categorie', formData);
            
            if (response.ok) {
                // Success state
                selectElement.style.backgroundColor = '#d4edda';
                
                // Reset after animation
                setTimeout(() => {
                    selectElement.style.backgroundColor = originalBackgroundColor;
                }, 1500);
                
                console.log(`Category updated for transaction ${transactieId}`);
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            // Error state
            selectElement.style.backgroundColor = '#f8d7da';
            selectElement.selectedIndex = 0; // Reset to "Geen categorie"
            
            ErrorHandler.handle(error, 'Category update');
            
            // Reset na 3 seconden
            setTimeout(() => {
                selectElement.style.backgroundColor = originalBackgroundColor;
            }, 3000);
            
        } finally {
            selectElement.disabled = false;
            UI.hideLoading('loadingIndicator');
        }
    }

    setupColumnToggleHandlers() {
        // Find toggle buttons door hun text content (omdat ze geen specifieke selectors hebben)
        const buttons = document.querySelectorAll('button');
        
        buttons.forEach(button => {
            const text = button.textContent.trim();
            if (text.includes('Tegenrekening')) {
                button.removeAttribute('onclick');
                button.addEventListener('click', () => this.toggleColumn('tegenrekening', button));
            } else if (text.includes('Mededelingen')) {
                button.removeAttribute('onclick');
                button.addEventListener('click', () => this.toggleColumn('mededelingen', button));
            }
        });
    }

    toggleColumn(columnClass, buttonElement) {
        const columns = document.querySelectorAll('.' + columnClass + '-col');
        if (columns.length === 0) return;
        
        const isHidden = columns[0].style.display === 'none';
        
        // Toggle visibility
        columns.forEach(col => {
            col.style.display = isHidden ? '' : 'none';
        });
        
        // Update button icon
        const icon = buttonElement.querySelector('i');
        if (icon) {
            if (isHidden) {
                icon.className = 'fas fa-eye-slash me-1';
            } else {
                icon.className = 'fas fa-eye me-1';
            }
        }
        
        // Visual feedback
        buttonElement.classList.toggle('active', !isHidden);
        
        console.log(`Column ${columnClass} ${isHidden ? 'shown' : 'hidden'}`);
    }

    setupSearchForm() {
        const searchForm = document.querySelector('form[method="GET"]');
        if (!searchForm) return;
        
        const searchInput = searchForm.querySelector('input[name="zoek"]');
        const searchButton = searchForm.querySelector('button[type="submit"]');
        
        if (searchInput && searchButton) {
            // Enhanced search experience
            searchForm.addEventListener('submit', (e) => {
                const searchValue = searchInput.value.trim();
                
                if (searchValue === '') {
                    // Als search leeg is, redirect naar clean URL
                    e.preventDefault();
                    const urlParams = new URLSearchParams();
                    if (this.currentSort) {
                        urlParams.set('sort', this.currentSort);
                        urlParams.set('order', this.currentOrder);
                    }
                    window.location.href = window.location.pathname + 
                        (urlParams.toString() ? '?' + urlParams.toString() : '');
                    return;
                }
                
                // Show loading state op search button
                searchButton.disabled = true;
                searchButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zoeken...';
            });
            
            // Auto-submit na 500ms delay (debounced)
            let searchTimeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    const value = searchInput.value.trim();
                    // Alleen auto-submit als er minimaal 3 karakters zijn
                    if (value.length >= 3 || value.length === 0) {
                        searchForm.dispatchEvent(new Event('submit'));
                    }
                }, 500);
            });
        }
    }

    // Public methods voor externe gebruik
    refreshTable() {
        window.location.reload();
    }

    getCurrentFilters() {
        return {
            sort: this.currentSort,
            order: this.currentOrder,
            search: this.searchTerm
        };
    }

    applyFilters(filters) {
        const urlParams = new URLSearchParams();
        
        if (filters.sort) urlParams.set('sort', filters.sort);
        if (filters.order) urlParams.set('order', filters.order);
        if (filters.search) urlParams.set('zoek', filters.search);
        
        window.location.href = window.location.pathname + 
            (urlParams.toString() ? '?' + urlParams.toString() : '');
    }

    // Bulk operations support (voor toekomstige uitbreidingen)
    getSelectedTransactions() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checkboxes).map(cb => cb.value).filter(v => v);
    }

    selectAllTransactions() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = true);
    }

    deselectAllTransactions() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
    }
}

// Initialize transactions manager
const transactions = new TransactionsManager();