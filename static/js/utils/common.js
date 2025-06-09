/**
 * Common utilities voor de ING Transactie Verwerker
 * Herbruikbare functies die door meerdere modules gebruikt worden
 */

// API Base functions
const API = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    },

    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    },

    async postForm(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });
        return response;
    }
};

// Formatting utilities
const Format = {
    /**
     * Format bedrag voor display
     * @param {number} bedrag 
     * @returns {string} Geformatteerd bedrag
     */
    bedrag(bedrag) {
        if (bedrag === 0) return '€0,00';
        
        const absValue = Math.abs(bedrag);
        const formatted = '€' + absValue.toLocaleString('nl-NL', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        return bedrag < 0 ? `-${formatted}` : formatted;
    },

    /**
     * Format bedrag met HTML classes voor kleuren
     * @param {number} bedrag 
     * @returns {string} HTML string met class
     */
    bedragHtml(bedrag) {
        if (bedrag === 0) return '<span>€0,00</span>';
        
        const absValue = Math.abs(bedrag);
        const formatted = '€' + absValue.toLocaleString('nl-NL', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        if (bedrag < 0) {
            return `<span class="transaction-negative">${formatted}</span>`;
        } else {
            return `<span class="transaction-positive">${formatted}</span>`;
        }
    },

    /**
     * Format aantal met lokale formatting
     * @param {number} aantal 
     * @returns {string}
     */
    aantal(aantal) {
        return aantal.toLocaleString('nl-NL');
    }
};

// UI Utilities
const UI = {
    /**
     * Toon loading indicator
     * @param {string} elementId 
     */
    showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.remove('d-none');
        }
    },

    /**
     * Verberg loading indicator
     * @param {string} elementId 
     */
    hideLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.add('d-none');
        }
    },

    /**
     * Toon element
     * @param {string} elementId 
     */
    show(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.remove('d-none');
        }
    },

    /**
     * Verberg element
     * @param {string} elementId 
     */
    hide(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.add('d-none');
        }
    },

    /**
     * Update tekst content van element
     * @param {string} elementId 
     * @param {string} content 
     */
    setText(elementId, content) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = content;
        }
    },

    /**
     * Update HTML content van element
     * @param {string} elementId 
     * @param {string} html 
     */
    setHtml(elementId, html) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = html;
        }
    }
};

// Constants
const COLORS = {
    primary: '#007bff',
    success: '#28a745', 
    danger: '#dc3545',
    warning: '#ffc107',
    info: '#17a2b8',
    light: '#f8f9fa',
    dark: '#343a40'
};

const MAAND_NAMEN = [
    'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
    'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December'
];

const MAAND_NAMEN_KORT = [
    'Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 
    'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'
];

// Error handling
const ErrorHandler = {
    /**
     * Log en toon error aan gebruiker
     * @param {Error} error 
     * @param {string} context 
     */
    handle(error, context = '') {
        console.error(`Error in ${context}:`, error);
        alert(`Er is een fout opgetreden: ${error.message}`);
    },

    /**
     * Log error zonder user notification
     * @param {Error} error 
     * @param {string} context 
     */
    log(error, context = '') {
        console.error(`Error in ${context}:`, error);
    }
};

// Export alles voor gebruik in andere modules
window.API = API;
window.Format = Format;
window.UI = UI;
window.COLORS = COLORS;
window.MAAND_NAMEN = MAAND_NAMEN;
window.MAAND_NAMEN_KORT = MAAND_NAMEN_KORT;
window.ErrorHandler = ErrorHandler;