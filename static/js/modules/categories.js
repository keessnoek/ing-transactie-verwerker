/**
 * Categories Module - Category management en basis functionaliteit
 * ING Transactie Verwerker
 */

class CategoriesManager {
    constructor() {
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
        this.setupCategoryModals();
        this.setupBulkOperations();
        this.setupFormValidation();
        
        console.log('Categories module initialized');
    }

    setupCategoryModals() {
        // Remove any existing onclick attributes from edit buttons
        const editButtons = document.querySelectorAll('button[onclick*="editCategory"]');
        editButtons.forEach(button => {
            const onclick = button.getAttribute('onclick');
            if (onclick) {
                // Extract parameters from onclick
                const match = onclick.match(/editCategory\((\d+),\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)/);
                if (match) {
                    const [, id, naam, beschrijving, kleur] = match;
                    button.removeAttribute('onclick');
                    button.addEventListener('click', () => {
                        this.editCategory(parseInt(id), naam, beschrijving, kleur);
                    });
                }
            }
        });

        // Setup form submission
        const editForm = document.getElementById('editForm');
        if (editForm) {
            editForm.addEventListener('submit', (e) => this.handleEditSubmit(e));
        }
    }

    setupBulkOperations() {
        // Bulk winkel assignment forms
        const bulkForms = document.querySelectorAll('form[action*="bulk_winkel_toewijzen"]');
        bulkForms.forEach(form => {
            form.addEventListener('submit', (e) => this.handleBulkWinkelSubmit(e, form));
        });

        // Individual transaction bulk assignment
        const bulkForm = document.querySelector('form[action*="bulk_toewijzen"]');
        if (bulkForm) {
            this.setupTransactionSelection(bulkForm);
        }
    }

    setupTransactionSelection(form) {
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        const transactionCheckboxes = document.querySelectorAll('.transaction-checkbox');
        const submitBtn = document.getElementById('submitBtn');

        // Select all functionality
        if (selectAllCheckbox) {
            selectAllCheckbox.removeAttribute('onchange');
            selectAllCheckbox.addEventListener('change', () => {
                const isChecked = selectAllCheckbox.checked;
                transactionCheckboxes.forEach(cb => cb.checked = isChecked);
                this.updateSubmitButton(submitBtn, transactionCheckboxes);
            });
        }

        // Individual checkbox handling
        transactionCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                this.updateSubmitButton(submitBtn, transactionCheckboxes);
                this.updateSelectAllState(selectAllCheckbox, transactionCheckboxes);
            });
        });

        // Initial state
        this.updateSubmitButton(submitBtn, transactionCheckboxes);

        // Bulk action buttons
        this.setupBulkActionButtons(transactionCheckboxes, selectAllCheckbox, submitBtn);
    }

    setupBulkActionButtons(checkboxes, selectAllCheckbox, submitBtn) {
        // Remove existing onclick handlers and add proper event listeners
        const selectAllBtn = document.querySelector('button[onclick="selectAll()"]');
        const selectNoneBtn = document.querySelector('button[onclick="selectNone()"]');

        if (selectAllBtn) {
            selectAllBtn.removeAttribute('onclick');
            selectAllBtn.addEventListener('click', () => {
                checkboxes.forEach(cb => cb.checked = true);
                if (selectAllCheckbox) selectAllCheckbox.checked = true;
                this.updateSubmitButton(submitBtn, checkboxes);
            });
        }

        if (selectNoneBtn) {
            selectNoneBtn.removeAttribute('onclick');
            selectNoneBtn.addEventListener('click', () => {
                checkboxes.forEach(cb => cb.checked = false);
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
                this.updateSubmitButton(submitBtn, checkboxes);
            });
        }
    }

    setupFormValidation() {
        // New category form
        const newCategoryForm = document.querySelector('form[action*="nieuwe_categorie"]');
        if (newCategoryForm) {
            newCategoryForm.addEventListener('submit', (e) => this.validateCategoryForm(e, newCategoryForm));
        }

        // Delete forms
        const deleteForms = document.querySelectorAll('form[action*="verwijder_categorie"]');
        deleteForms.forEach(form => {
            form.addEventListener('submit', (e) => this.handleDeleteSubmit(e, form));
        });
    }

    // Category CRUD operations
    editCategory(id, naam, beschrijving, kleur) {
        const editForm = document.getElementById('editForm');
        const modal = document.getElementById('editModal');
        
        if (!editForm || !modal) return;

        // Set form action
        editForm.action = `/categories/${id}/bewerken`;
        
        // Fill form fields
        document.getElementById('editNaam').value = naam;
        document.getElementById('editBeschrijving').value = beschrijving || '';
        document.getElementById('editKleur').value = kleur || '#3498db';
        
        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    handleEditSubmit(e) {
        const form = e.target;
        const naam = form.querySelector('#editNaam').value.trim();
        
        if (!naam) {
            e.preventDefault();
            alert('Categorienaam is verplicht');
            return false;
        }

        // Add loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Opslaan...';
        }

        return true;
    }

    handleDeleteSubmit(e, form) {
        // Find category name from the row
        const row = form.closest('tr');
        const categoryName = row ? row.querySelector('strong')?.textContent || 'deze categorie' : 'deze categorie';
        
        if (!confirm(`Weet je zeker dat je "${categoryName}" wilt verwijderen?\n\nTransacties worden behouden maar krijgen geen categorie meer.`)) {
            e.preventDefault();
            return false;
        }

        // Add loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        return true;
    }

    handleBulkWinkelSubmit(e, form) {
        const winkelNaam = form.querySelector('input[name="winkel_naam"]').value;
        const formData = new FormData(form);
        const categorieId = formData.get('categorie_id');
        
        // Find category name
        const categoryRow = document.querySelector(`tr:has(form[action*="${categorieId}/bewerken"])`);
        const categoryName = categoryRow ? categoryRow.querySelector('strong')?.textContent || 'deze categorie' : 'deze categorie';
        
        const aantalElement = form.parentElement.querySelector('small');
        const aantal = aantalElement ? aantalElement.textContent.match(/\d+/)?.[0] || 'alle' : 'alle';
        
        if (!confirm(`${aantal} ${winkelNaam} transacties toewijzen aan "${categoryName}"?`)) {
            e.preventDefault();
            return false;
        }

        // Add loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Bezig...';
        }

        return true;
    }

    validateCategoryForm(e, form) {
        const naam = form.querySelector('input[name="naam"]').value.trim();
        
        if (!naam) {
            e.preventDefault();
            alert('Categorienaam is verplicht');
            form.querySelector('input[name="naam"]').focus();
            return false;
        }

        // Add loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Toevoegen...';
        }

        return true;
    }

    // Utility methods
    updateSubmitButton(submitBtn, checkboxes) {
        if (!submitBtn) return;
        
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        submitBtn.disabled = checkedCount === 0;
        
        if (checkedCount > 0) {
            const originalText = submitBtn.getAttribute('data-original-text') || submitBtn.textContent;
            submitBtn.setAttribute('data-original-text', originalText);
            submitBtn.innerHTML = `<i class="fas fa-check me-1"></i>${checkedCount} toewijzen`;
        } else {
            const originalText = submitBtn.getAttribute('data-original-text');
            if (originalText) {
                submitBtn.innerHTML = originalText;
            }
        }
    }

    updateSelectAllState(selectAllCheckbox, transactionCheckboxes) {
        if (!selectAllCheckbox) return;
        
        const checkedCount = Array.from(transactionCheckboxes).filter(cb => cb.checked).length;
        const totalCount = transactionCheckboxes.length;
        
        selectAllCheckbox.checked = checkedCount === totalCount;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
    }

    // Public API methods
    selectAll() {
        const checkboxes = document.querySelectorAll('.transaction-checkbox');
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        const submitBtn = document.getElementById('submitBtn');
        
        checkboxes.forEach(cb => cb.checked = true);
        if (selectAllCheckbox) selectAllCheckbox.checked = true;
        this.updateSubmitButton(submitBtn, checkboxes);
    }

    selectNone() {
        const checkboxes = document.querySelectorAll('.transaction-checkbox');
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        const submitBtn = document.getElementById('submitBtn');
        
        checkboxes.forEach(cb => cb.checked = false);
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        this.updateSubmitButton(submitBtn, checkboxes);
    }

    getSelectedTransactions() {
        const checkboxes = document.querySelectorAll('.transaction-checkbox:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    }
}

// Initialize categories manager
const categories = new CategoriesManager();