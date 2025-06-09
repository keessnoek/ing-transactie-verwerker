/**
 * Auto Categorization Module - Slimme pattern matching en bulk categorization
 * ING Transactie Verwerker
 */

class AutoCategorizationManager {
    constructor() {
        this.huidigeModalData = null;
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
        this.setupEventListeners();
        this.laadAnalyse();
        
        console.log('Auto Categorization module initialized');
    }

    setupEventListeners() {
        // Preview modal event listeners
        const modal = document.getElementById('transactiePreviewModal');
        if (modal) {
            modal.addEventListener('change', (e) => {
                if (e.target.classList.contains('preview-checkbox')) {
                    this.updatePreviewButton();
                }
            });
        }

        // Modal buttons
        const categoriseerBtn = document.getElementById('categoriseerGeselecteerd');
        if (categoriseerBtn) {
            categoriseerBtn.removeAttribute('onclick');
            categoriseerBtn.addEventListener('click', () => this.categoriseerGeselecteerdUitModal());
        }

        // Select all/none buttons in modal
        this.setupModalButtons();
    }

    setupModalButtons() {
        // Find buttons by their onclick attributes and replace with proper event listeners
        const buttons = document.querySelectorAll('button[onclick*="selectAllPreview"], button[onclick*="selectNonePreview"], button[onclick*="toggleAllPreview"]');
        
        buttons.forEach(button => {
            const onclick = button.getAttribute('onclick');
            button.removeAttribute('onclick');
            
            if (onclick.includes('selectAllPreview')) {
                button.addEventListener('click', () => this.selectAllPreview());
            } else if (onclick.includes('selectNonePreview')) {
                button.addEventListener('click', () => this.selectNonePreview());
            } else if (onclick.includes('toggleAllPreview')) {
                button.addEventListener('click', () => this.toggleAllPreview());
            }
        });
    }

    async laadAnalyse() {
        try {
            UI.showLoading('loadingIndicator');
            
            const data = await API.get('/reports/categoriseer-analyse');
            
            UI.hideLoading('loadingIndicator');
            
            // Update statistieken
            UI.setText('totaalOngecategoriseerd', Format.aantal(data.totaal_ongecategoriseerd));
            UI.setText('totaalGecategoriseerd', Format.aantal(data.totaal_gecategoriseerd));
            UI.show('statistieken');
            
            // Toon suggesties
            if (data.categoriseer_suggesties.length > 0) {
                this.toonSuggesties(data.categoriseer_suggesties, data.bestaande_categorien);
                UI.show('suggesties');
            }
            
            // Toon potentiële patronen
            if (data.potentiele_patronen.length > 0) {
                this.toonPotentiele(data.potentiele_patronen);
                UI.show('potentiele');
            }
            
            // Als geen suggesties, toon melding
            if (data.categoriseer_suggesties.length === 0 && data.potentiele_patronen.length === 0) {
                UI.show('geenSuggesties');
            }
            
        } catch (error) {
            UI.hideLoading('loadingIndicator');
            ErrorHandler.handle(error, 'Analyse laden');
            UI.show('errorMessage');
        }
    }

    toonSuggesties(suggesties, categorien) {
        const container = document.getElementById('suggestiesLijst');
        if (!container) return;
        
        container.innerHTML = '';
        
        suggesties.forEach((suggestie, index) => {
            const voorbeelden = suggestie.voorbeelden.join(', ');
            const bedragFormatted = Format.bedrag(suggestie.totaal_bedrag);
            
            // Bepaal categorie opties
            let categorieOpties = '';
            if (suggestie.suggested_category_id) {
                categorieOpties = `<option value="${suggestie.suggested_category_id}">${categorien[suggestie.suggested_category_id]} (aanbevolen)</option>`;
            }
            
            // Voeg alle andere categorieën toe
            Object.entries(categorien).forEach(([id, naam]) => {
                if (id != suggestie.suggested_category_id) {
                    categorieOpties += `<option value="${id}">${naam}</option>`;
                }
            });
            
            const card = this.createSuggestieCard(suggestie, index, voorbeelden, bedragFormatted, categorieOpties);
            container.innerHTML += card;
            
            // Setup event listeners for this suggestion
            this.setupSuggestieEvents(index, suggestie);
            
            // Pre-selecteer aanbevolen categorie
            if (suggestie.suggested_category_id) {
                setTimeout(() => {
                    const select = document.getElementById(`categorie_${index}`);
                    if (select) select.value = suggestie.suggested_category_id;
                }, 100);
            }
        });
    }

    createSuggestieCard(suggestie, index, voorbeelden, bedragFormatted, categorieOpties) {
        return `
            <div class="border-bottom p-3">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <h6 class="mb-1">${suggestie.categorie}</h6>
                        <small class="text-muted">Patronen: ${voorbeelden}</small>
                        <div class="mt-2">
                            <span class="badge bg-primary">${suggestie.totaal_transacties} transacties</span>
                            <span class="badge bg-success">${bedragFormatted}</span>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <select class="form-select form-select-sm" id="categorie_${index}">
                            <option value="">Kies categorie...</option>
                            ${categorieOpties}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <button class="btn btn-info btn-sm w-100 me-1 mb-1" data-action="preview" data-index="${index}">
                            <i class="fas fa-eye me-1"></i>Bekijk Alle
                        </button>
                        <button class="btn btn-success btn-sm w-100" data-action="categorize" data-index="${index}">
                            <i class="fas fa-magic me-1"></i>Categoriseren
                        </button>
                    </div>
                </div>
                
                <!-- Voorbeelden -->
                <div class="mt-2">
                    <small class="text-muted">Voorbeelden:</small>
                    <div class="mt-1">
                        ${suggestie.matched_namen.slice(0, 3).map(m => 
                            `<span class="badge bg-light text-dark me-1">${m.naam} (${m.aantal}x)</span>`
                        ).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    setupSuggestieEvents(index, suggestie) {
        // Setup event listeners voor deze suggestie
        setTimeout(() => {
            const previewBtn = document.querySelector(`button[data-action="preview"][data-index="${index}"]`);
            const categorizeBtn = document.querySelector(`button[data-action="categorize"][data-index="${index}"]`);
            
            if (previewBtn) {
                previewBtn.addEventListener('click', () => {
                    this.bekijkTransacties(index, suggestie.categorie, suggestie.patronen);
                });
            }
            
            if (categorizeBtn) {
                categorizeBtn.addEventListener('click', () => {
                    this.categoriseer(index, suggestie.categorie, suggestie.patronen);
                });
            }
        }, 150);
    }

    toonPotentiele(potentiele) {
        const container = document.getElementById('potentieleLijst');
        if (!container) return;
        
        container.innerHTML = '';
        
        potentiele.forEach(patroon => {
            const gemiddeldFormatted = Format.bedrag(patroon.gemiddeld_bedrag);
            
            const card = `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-body py-2">
                            <h6 class="card-title mb-1">${patroon.naam}</h6>
                            <div>
                                <span class="badge bg-info">${patroon.aantal} transacties</span>
                                <span class="badge bg-secondary">Ø ${gemiddeldFormatted}</span>
                            </div>
                            <small class="text-muted">Maak hier handmatig een categorie voor</small>
                        </div>
                    </div>
                </div>
            `;
            
            container.innerHTML += card;
        });
    }

    async bekijkTransacties(index, categorieNaam, patronen) {
        // Sla gegevens op voor later gebruik
        this.huidigeModalData = {
            index: index,
            categorieNaam: categorieNaam,
            patronen: patronen
        };
        
        // Modal openen
        const modal = new bootstrap.Modal(document.getElementById('transactiePreviewModal'));
        UI.setHtml('previewModalTitle', `<i class="fas fa-list me-2"></i>Preview: ${categorieNaam}`);
        
        // Reset modal content
        UI.showLoading('previewLoading');
        UI.hide('previewControls');
        UI.hide('previewTransacties');
        UI.hide('previewGeenData');
        
        modal.show();
        
        try {
            const data = await API.post('/reports/preview-transacties', { patronen: patronen });
            
            UI.hideLoading('previewLoading');
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (data.transacties.length === 0) {
                UI.show('previewGeenData');
                return;
            }
            
            // Update aantal
            UI.setText('previewAantal', data.aantal);
            UI.show('previewControls');
            
            // Vul transacties tabel
            this.vulPreviewTabel(data.transacties);
            UI.show('previewTransacties');
            
            // Update button
            this.updatePreviewButton();
            
        } catch (error) {
            UI.hideLoading('previewLoading');
            ErrorHandler.log(error, 'Preview transacties');
            UI.show('previewGeenData');
        }
    }

    vulPreviewTabel(transacties) {
        const tbody = document.getElementById('previewTransactiesBody');
        if (!tbody) return;
        
        tbody.innerHTML = transacties.map(transactie => `
            <tr>
                <td>
                    <input type="checkbox" class="preview-checkbox" value="${transactie.id}" checked>
                </td>
                <td><small>${transactie.datum}</small></td>
                <td title="${transactie.naam}">${transactie.naam.length > 50 ? transactie.naam.substring(0, 47) + '...' : transactie.naam}</td>
                <td class="${transactie.bedrag >= 0 ? 'transaction-positive' : 'transaction-negative'}">
                    ${transactie.bedrag_formatted}
                </td>
                <td><span class="badge bg-secondary">${transactie.code}</span></td>
            </tr>
        `).join('');
    }

    selectAllPreview() {
        document.querySelectorAll('.preview-checkbox').forEach(cb => cb.checked = true);
        const selectAllCheckbox = document.getElementById('selectAllPreviewCheckbox');
        if (selectAllCheckbox) selectAllCheckbox.checked = true;
        this.updatePreviewButton();
    }

    selectNonePreview() {
        document.querySelectorAll('.preview-checkbox').forEach(cb => cb.checked = false);
        const selectAllCheckbox = document.getElementById('selectAllPreviewCheckbox');
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        this.updatePreviewButton();
    }

    toggleAllPreview() {
        const selectAllCheckbox = document.getElementById('selectAllPreviewCheckbox');
        if (!selectAllCheckbox) return;
        
        const isChecked = selectAllCheckbox.checked;
        document.querySelectorAll('.preview-checkbox').forEach(cb => cb.checked = isChecked);
        this.updatePreviewButton();
    }

    updatePreviewButton() {
        const checked = document.querySelectorAll('.preview-checkbox:checked').length;
        const button = document.getElementById('categoriseerGeselecteerd');
        
        if (!button) return;
        
        button.disabled = checked === 0;
        button.innerHTML = checked > 0 
            ? `<i class="fas fa-magic me-1"></i>Categoriseer ${checked} Geselecteerde`
            : `<i class="fas fa-magic me-1"></i>Categoriseer Geselecteerde`;
    }

    async categoriseerGeselecteerdUitModal() {
        if (!this.huidigeModalData) return;
        
        const categorieSelect = document.getElementById(`categorie_${this.huidigeModalData.index}`);
        if (!categorieSelect) return;
        
        const categorieId = categorieSelect.value;
        
        if (!categorieId) {
            alert('Selecteer eerst een categorie');
            return;
        }
        
        const categorieNaamGekozen = categorieSelect.options[categorieSelect.selectedIndex].text;
        const geselecteerdeIds = Array.from(document.querySelectorAll('.preview-checkbox:checked')).map(cb => parseInt(cb.value));
        
        if (geselecteerdeIds.length === 0) {
            alert('Selecteer minimaal één transactie');
            return;
        }
        
        if (!confirm(`${geselecteerdeIds.length} transacties toewijzen aan "${categorieNaamGekozen}"?`)) {
            return;
        }
        
        // Sluit modal
        bootstrap.Modal.getInstance(document.getElementById('transactiePreviewModal')).hide();
        
        await this.voerCategorizationUit(categorieId, categorieNaamGekozen, this.huidigeModalData.patronen, geselecteerdeIds);
    }

    async categoriseer(index, categorieNaam, patronen) {
        const categorieSelect = document.getElementById(`categorie_${index}`);
        if (!categorieSelect) return;
        
        const categorieId = categorieSelect.value;
        
        if (!categorieId) {
            alert('Selecteer eerst een categorie');
            return;
        }
        
        const categorieNaamGekozen = categorieSelect.options[categorieSelect.selectedIndex].text;
        
        if (!confirm(`${patronen.length} patronen toewijzen aan "${categorieNaamGekozen}"?\n\nDit kan niet ongedaan worden gemaakt.`)) {
            return;
        }
        
        await this.voerCategorizationUit(categorieId, categorieNaamGekozen, patronen, null, index);
    }

    async voerCategorizationUit(categorieId, categorieNaam, patronen, transactieIds = null, buttonIndex = null) {
        // Find button voor loading state
        let button = null;
        if (buttonIndex !== null) {
            button = document.querySelector(`button[data-action="categorize"][data-index="${buttonIndex}"]`);
        }
        
        // Disable button tijdens verwerking
        const originalHtml = button ? button.innerHTML : '';
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Bezig...';
        }
        
        try {
            const payload = {
                patronen: patronen,
                categorie_id: parseInt(categorieId),
                categorie_naam: categorieNaam
            };
            
            if (transactieIds) {
                payload.transactie_ids = transactieIds;
            }
            
            const data = await API.post('/reports/auto-categoriseren', payload);
            
            if (data.aantal_updated > 0) {
                alert(`Succes! ${data.aantal_updated} transacties toegewezen aan "${categorieNaam}"`);
                
                // Herlaad de analyse na 1 seconde
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                alert('Geen transacties bijgewerkt: ' + data.message);
                if (button) {
                    button.disabled = false;
                    button.innerHTML = originalHtml;
                }
            }
            
        } catch (error) {
            ErrorHandler.handle(error, 'Auto categoriseren');
            if (button) {
                button.disabled = false;
                button.innerHTML = originalHtml;
            }
        }
    }
}

// Initialize auto categorization manager
const autoCategorizationManager = new AutoCategorizationManager();