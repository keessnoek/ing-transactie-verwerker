/**
 * Dashboard Module - Chart.js visualisaties en drill-down functionaliteit
 * ING Transactie Verwerker
 */

class DashboardManager {
    constructor() {
        this.charts = {
            uitgaven: null,
            categorien: null,
            inkomstenUitgaven: null
        };
        this.huidigeJaar = null;
        this.huidigeMaand = null;
        this.categorieDataForClick = null;
        
        this.init();
    }

    init() {
        // Wacht tot DOM geladen is
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        // Haal default waarden op
        this.huidigeJaar = parseInt(document.getElementById('eindJaar')?.value) || new Date().getFullYear();
        this.huidigeMaand = parseInt(document.getElementById('eindMaand')?.value) || new Date().getMonth() + 1;
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Update periode label
        this.updatePeriodeLabel();
        
        // Laad dashboard data
        this.laadDashboard();
    }

    setupEventListeners() {
        // Periode selectie
        const eindMaand = document.getElementById('eindMaand');
        const eindJaar = document.getElementById('eindJaar');
        
        if (eindMaand) eindMaand.addEventListener('change', () => this.updatePeriodeLabel());
        if (eindJaar) eindJaar.addEventListener('change', () => this.updatePeriodeLabel());
        
        // Update button
        const updateBtn = document.querySelector('[onclick="updateDashboard()"]');
        if (updateBtn) {
            updateBtn.removeAttribute('onclick');
            updateBtn.addEventListener('click', () => this.updateDashboard());
        }
        
        // Reset button
        const resetBtn = document.querySelector('[onclick="resetNaarHuidige()"]');
        if (resetBtn) {
            resetBtn.removeAttribute('onclick');
            resetBtn.addEventListener('click', () => this.resetNaarHuidige());
        }
    }

    updatePeriodeLabel() {
        const jaar = document.getElementById('eindJaar')?.value;
        const maand = parseInt(document.getElementById('eindMaand')?.value);
        const labelElement = document.getElementById('periodeLabel');
        
        if (labelElement && jaar && maand) {
            labelElement.textContent = `${MAAND_NAMEN[maand - 1]} ${jaar}`;
        }
    }

    async laadDashboard() {
        try {
            UI.showLoading('loadingIndicator');
            
            // Haal huidige selectie op
            const jaar = document.getElementById('eindJaar')?.value || this.huidigeJaar;
            const maand = document.getElementById('eindMaand')?.value || this.huidigeMaand;
            
            const params = `?jaar=${jaar}&maand=${maand}`;
            
            // Parallel API calls
            const [statistieken, uitgavenData, categorienData, inkomstenUitgavenData] = await Promise.all([
                API.get('/reports/dashboard/statistieken' + params),
                API.get('/reports/dashboard/uitgaven-per-maand' + params),
                API.get('/reports/dashboard/top-categorien' + params),
                API.get('/reports/dashboard/inkomsten-uitgaven' + params)
            ]);
            
            // Toon data
            this.toonStatistieken(statistieken);
            this.maakUitgavenChart(uitgavenData);
            this.maakCategorienChart(categorienData);
            this.maakInkomstenUitgavenChart(inkomstenUitgavenData);
            
        } catch (error) {
            ErrorHandler.handle(error, 'Dashboard laden');
            UI.show('errorMessage');
        } finally {
            UI.hideLoading('loadingIndicator');
        }
    }

    toonStatistieken(stats) {
        const container = document.getElementById('statistiekenCards');
        if (!container) return;
        
        const nettoKleur = stats.netto_resultaat >= 0 ? 'success' : 'danger';
        const nettoIcon = stats.netto_resultaat >= 0 ? 'arrow-up' : 'arrow-down';
        
        container.innerHTML = `
            <div class="col-md-3">
                <div class="card text-center border-primary">
                    <div class="card-body">
                        <i class="fas fa-list fa-2x text-primary mb-2"></i>
                        <h4>${Format.aantal(stats.totaal_transacties)}</h4>
                        <p class="text-muted mb-0">Transacties</p>
                        <small class="text-muted">${stats.periode}</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center border-success">
                    <div class="card-body">
                        <i class="fas fa-arrow-up fa-2x text-success mb-2"></i>
                        <h4 class="text-success">${Format.bedrag(stats.totaal_inkomsten)}</h4>
                        <p class="text-muted mb-0">Inkomsten</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center border-danger">
                    <div class="card-body">
                        <i class="fas fa-arrow-down fa-2x text-danger mb-2"></i>
                        <h4 class="text-danger">${Format.bedrag(stats.totaal_uitgaven)}</h4>
                        <p class="text-muted mb-0">Uitgaven</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center border-${nettoKleur}">
                    <div class="card-body">
                        <i class="fas fa-${nettoIcon} fa-2x text-${nettoKleur} mb-2"></i>
                        <h4 class="text-${nettoKleur}">${stats.netto_resultaat >= 0 ? '+' : ''}${Format.bedrag(stats.netto_resultaat)}</h4>
                        <p class="text-muted mb-0">Netto Resultaat</p>
                    </div>
                </div>
            </div>
        `;
    }

    maakUitgavenChart(data) {
        const ctx = document.getElementById('uitgavenChart');
        if (!ctx) return;
        
        // Destroy bestaande chart
        if (this.charts.uitgaven) {
            this.charts.uitgaven.destroy();
        }
        
        this.charts.uitgaven = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Uitgaven',
                    data: data.data,
                    borderColor: COLORS.danger,
                    backgroundColor: COLORS.danger + '20',
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: COLORS.danger,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const elementIndex = elements[0].index;
                        const label = data.labels[elementIndex];
                        this.toonMaandDetails(label, elementIndex);
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return Format.bedrag(value);
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Uitgaven: ' + Format.bedrag(context.parsed.y);
                            },
                            afterLabel: function(context) {
                                return 'Klik voor details';
                            }
                        }
                    },
                    legend: {
                        display: false
                    }
                },
                onHover: function(event, activeElements) {
                    event.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    }

    maakCategorienChart(data) {
        const ctx = document.getElementById('categorienChart');
        if (!ctx) return;
        
        // Sla data op voor click handling
        this.categorieDataForClick = data;
        
        // Destroy bestaande chart
        if (this.charts.categorien) {
            this.charts.categorien.destroy();
        }
        
        this.charts.categorien = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: data.colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const elementIndex = elements[0].index;
                        const categorieNaam = data.labels[elementIndex];
                        const categorieId = data.categorie_ids[elementIndex];
                        this.toonCategorieDetails(categorieNaam, categorieId);
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return context.label + ': ' + Format.bedrag(context.parsed) + ' (' + percentage + '%)';
                            },
                            afterLabel: function(context) {
                                return 'Klik voor details';
                            }
                        }
                    },
                    legend: {
                        position: 'bottom'
                    }
                },
                onHover: function(event, activeElements) {
                    event.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    }

    maakInkomstenUitgavenChart(data) {
        const ctx = document.getElementById('inkomstenUitgavenChart');
        if (!ctx) return;
        
        // Destroy bestaande chart
        if (this.charts.inkomstenUitgaven) {
            this.charts.inkomstenUitgaven.destroy();
        }
        
        this.charts.inkomstenUitgaven = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Inkomsten',
                        data: data.inkomsten,
                        backgroundColor: COLORS.success + '80',
                        borderColor: COLORS.success,
                        borderWidth: 1
                    },
                    {
                        label: 'Uitgaven', 
                        data: data.uitgaven,
                        backgroundColor: COLORS.danger + '80',
                        borderColor: COLORS.danger,
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return Format.bedrag(value);
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + Format.bedrag(context.parsed.y);
                            }
                        }
                    }
                }
            }
        });
    }

    updateDashboard() {
        // Destroy bestaande charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        
        // Reset chart references
        this.charts = {
            uitgaven: null,
            categorien: null,
            inkomstenUitgaven: null
        };
        
        // Herlaad
        this.laadDashboard();
    }

    resetNaarHuidige() {
        document.getElementById('eindJaar').value = this.huidigeJaar;
        document.getElementById('eindMaand').value = this.huidigeMaand;
        this.updatePeriodeLabel();
        this.updateDashboard();
    }

    // Drill-down functionaliteit
    async toonMaandDetails(maandLabel, maandIndex) {
        // Parse jaar en maand uit het label (bijv. "Jan 2025")
        const parts = maandLabel.split(' ');
        const jaar = parseInt(parts[1]);
        const maand = MAAND_NAMEN_KORT.indexOf(parts[0]) + 1;
        
        this.openDrilldownModal(`Uitgaven ${maandLabel}`, 'calendar');
        
        try {
            const data = await API.get(`/reports/dashboard/maand-details?jaar=${jaar}&maand=${maand}`);
            this.vulModalMet(data, 'maand');
        } catch (error) {
            this.toonModalError(error.message);
        }
    }

    async toonCategorieDetails(categorieNaam, categorieId) {
        this.openDrilldownModal(`Categorie: ${categorieNaam}`, 'tag');
        
        try {
            const jaar = document.getElementById('eindJaar').value;
            const maand = document.getElementById('eindMaand').value;
            const categorieParam = categorieId !== null ? categorieId : 'null';
            
            const data = await API.get(`/reports/dashboard/categorie-details?categorie_id=${categorieParam}&jaar=${jaar}&maand=${maand}&periode=12`);
            this.vulModalMet(data, 'categorie');
        } catch (error) {
            this.toonModalError(error.message);
        }
    }

    openDrilldownModal(title, icon) {
        const modal = new bootstrap.Modal(document.getElementById('drilldownModal'));
        UI.setHtml('drilldownModalTitle', `<i class="fas fa-${icon} me-2"></i>${title}`);
        
        this.resetModalContent();
        UI.showLoading('drilldownModalLoading');
        modal.show();
    }

    resetModalContent() {
        UI.hide('drilldownModalLoading');
        UI.hide('drilldownModalStats');
        UI.hide('drilldownModalTransacties');
        UI.hide('drilldownModalGeenData');
    }

    vulModalMet(data, type) {
        UI.hideLoading('drilldownModalLoading');
        
        if (data.transacties.length === 0) {
            UI.show('drilldownModalGeenData');
            return;
        }
        
        // Vul statistieken
        UI.setText('drilldownStatAantal', data.statistieken.aantal);
        UI.setText('drilldownStatTotaal', data.statistieken.totaal_formatted);
        UI.setText('drilldownStatUitgaven', data.statistieken.uitgaven_formatted);
        UI.setText('drilldownStatInkomsten', data.statistieken.inkomsten_formatted);
        UI.show('drilldownModalStats');
        
        // Vul transacties tabel
        const tbody = document.getElementById('drilldownModalTransactiesBody');
        if (tbody) {
            tbody.innerHTML = data.transacties.map(transactie => `
                <tr>
                    <td><small>${transactie.datum}</small></td>
                    <td>${transactie.naam}</td>
                    <td class="${transactie.bedrag >= 0 ? 'transaction-positive' : 'transaction-negative'}">
                        ${transactie.bedrag_formatted}
                    </td>
                    <td><span class="badge bg-secondary">${transactie.code}</span></td>
                    <td><small class="text-muted" title="${transactie.mededelingen}">
                        ${transactie.mededelingen.length > 50 ? 
                          transactie.mededelingen.substring(0, 50) + '...' : 
                          transactie.mededelingen || '-'}
                    </small></td>
                </tr>
            `).join('');
        }
        
        UI.show('drilldownModalTransacties');
    }

    toonModalError(errorMessage) {
        UI.hideLoading('drilldownModalLoading');
        const tbody = document.getElementById('drilldownModalTransactiesBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>Fout bij laden: ${errorMessage}
                    </td>
                </tr>
            `;
        }
        UI.show('drilldownModalTransacties');
    }
}

// Initialize dashboard wanneer script geladen wordt
const dashboard = new DashboardManager();