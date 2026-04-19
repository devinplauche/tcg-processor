/**
 * MTG Inventory System - Client-side JavaScript
 * Main application logic and UI interactions
 */

// ============= UTILITY FUNCTIONS =============

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Format currency
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2
    }).format(amount);
}

/**
 * Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Debounce function for search/input
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Show notification toast
 */
function showNotification(message, type = 'info') {
    const container = document.querySelector('.message-container') || 
                     document.body;
    
    const el = document.createElement('div');
    el.className = `message message-${type}`;
    el.textContent = message;
    
    if (!document.querySelector('.message-container')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'message-container';
        container.insertBefore(wrapper, container.firstChild);
        wrapper.appendChild(el);
    } else {
        document.querySelector('.message-container').appendChild(el);
    }
    
    setTimeout(() => {
        el.style.animation = 'slideDown 0.3s ease reverse';
        setTimeout(() => el.remove(), 300);
    }, 5000);
}

// ============= CSV IMPORT HELPERS =============

/**
 * Count cards in CSV (for preview)
 */
function parseCSVPreview(file) {
    const parseCsvLine = (line) => {
        const values = [];
        let current = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i += 1) {
            const char = line[i];
            if (char === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i += 1;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                values.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        values.push(current);
        return values.map((v) => v.trim());
    };

    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const lines = e.target.result.split('\n');
                const rows = lines.slice(1, 9).filter(line => line.trim());
                
                const data = rows.map(line => {
                    const values = parseCsvLine(line);
                    return {
                        name: values[0] || '—',
                        set: values[1] || '—',
                        condition: values[3] || 'NM',
                        foil: (values[4] || 'normal').toLowerCase() === 'foil' ? 'Yes' : 'No',
                        location: 'BOX-0001/SLOT-????',
                        status: 'new'
                    };
                });
                
                resolve(data);
            } catch (err) {
                reject(err);
            }
        };
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

// ============= BOX/LOCATION HELPERS =============

/**
 * Format location code
 */
function formatLocationCode(boxNum, slotNum) {
    return `BOX-${String(boxNum).padStart(4, '0')}-SLOT-${String(slotNum).padStart(4, '0')}`;
}

/**
 * Generate QR code data URL (simple version)
 */
function generateQRCodeData(text) {
    // In production, use a QR library like qrcode.js
    return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(text)}`;
}

// ============= EBAY LISTING HELPERS =============

/**
 * Format card title for eBay
 */
function formatEBayTitle(cardName, set, condition, foil) {
    const foilStr = foil === 'yes' ? '· Foil ✨' : '';
    return `${cardName} ${set} MTG ${condition} ${foilStr} — Magic: The Gathering`;
}

/**
 * Calculate suggested price (placeholder)
 */
function calculateSuggestedPrice(marketPrice, condition) {
    const adjustments = {
        'NM': 1.0,
        'LP': 0.85,
        'MP': 0.70,
        'HP': 0.50,
        'PO': 0.30
    };
    const factor = adjustments[condition] || 1.0;
    return (marketPrice * factor * 1.15).toFixed(2); // 15% markup
}

// ============= API HELPERS =============

/**
 * Generic fetch with error handling
 */
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: options.body ? JSON.stringify(options.body) : undefined
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showNotification(`Error: ${error.message}`, 'danger');
        throw error;
    }
}

/**
 * Search cards
 */
async function searchCards(query) {
    if (!query || query.length < 2) return [];
    
    try {
        const response = await fetch(`/api/cards/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) return [];
        return await response.json();
    } catch (error) {
        console.error('Search failed:', error);
        return [];
    }
}

/**
 * Get pricing for card
 */
async function getCardPricing(scryfallId) {
    try {
        const response = await fetch(`/api/pricing/${scryfallId}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Pricing fetch failed:', error);
        return null;
    }
}

// ============= PAGE INITIALIZATION =============

/**
 * Handle View Boxes button click
 */
function handleViewBoxes() {
    showNotification('📦 Loading boxes...', 'info');
    setTimeout(() => {
        window.location.href = '/api/boxes';
    }, 800);
}

/**
 * Handle Create Listing button click
 */
function handleCreateListing() {
    showModal(
        'Create eBay Listing',
        `
        <form id="listingForm">
            <div class="form-group">
                <label for="cardSearch">Search Card:</label>
                <input type="text" id="cardSearch" class="form-input" placeholder="Enter card name..." />
            </div>
            <div class="form-group">
                <label for="listingPrice">Price ($):</label>
                <input type="number" id="listingPrice" class="form-input" placeholder="0.00" step="0.01" />
            </div>
            <div class="form-group">
                <label for="listingQty">Quantity:</label>
                <input type="number" id="listingQty" class="form-input" placeholder="1" value="1" />
            </div>
        </form>
        `,
        [
            {
                label: 'Cancel',
                style: 'outline',
                onclick: () => document.querySelector('.modal-overlay')?.remove()
            },
            {
                label: 'Create Listing',
                style: 'primary',
                onclick: () => createEBayListing()
            }
        ]
    );
}

/**
 * Handle Search Cards button click
 */
function handleSearchCards() {
    let searchInput = '';
    let searchResults = '';
    
    showModal(
        'Search Cards',
        `
        <div class="form-group">
            <label for="searchInput">Card Name:</label>
            <input type="text" id="searchInput" class="form-input" placeholder="Search..." autofocus />
        </div>
        <div id="searchResults" style="margin-top: 16px;"></div>
        `,
        [
            {
                label: 'Close',
                style: 'outline',
                onclick: () => document.querySelector('.modal-overlay')?.remove()
            }
        ]
    );
    
    // Add search functionality
    const input = document.getElementById('searchInput');
    const resultsDiv = document.getElementById('searchResults');
    
    if (input) {
        input.addEventListener('input', debounce(async (e) => {
            const query = e.target.value.trim();
            if (query.length < 2) {
                resultsDiv.innerHTML = '';
                return;
            }
            
            try {
                const results = await searchCards(query);
                if (results.length === 0) {
                    resultsDiv.innerHTML = '<p style="color: var(--muted);">No cards found</p>';
                } else {
                    resultsDiv.innerHTML = '';
                    results.slice(0, 5).forEach((card) => {
                        const row = document.createElement('div');
                        row.style.padding = '8px';
                        row.style.borderBottom = '1px solid var(--border)';
                        row.style.cursor = 'pointer';
                        row.addEventListener('click', () => selectCard(card.name));

                        const strong = document.createElement('strong');
                        strong.textContent = card.name || 'Unknown';
                        row.appendChild(strong);
                        row.appendChild(document.createElement('br'));

                        const meta = document.createElement('span');
                        meta.style.color = 'var(--muted)';
                        meta.style.fontSize = '0.9em';
                        meta.textContent = `${card.set || '—'} • ${card.collector_number || '—'}`;
                        row.appendChild(meta);

                        resultsDiv.appendChild(row);
                    });
                }
            } catch (error) {
                resultsDiv.innerHTML = '<p style="color: var(--danger);">Search failed</p>';
            }
        }, 300));
    }
}

/**
 * Create eBay listing from form
 */
function createEBayListing() {
    const cardSearch = document.getElementById('cardSearch')?.value;
    const price = document.getElementById('listingPrice')?.value;
    const qty = document.getElementById('listingQty')?.value;
    
    if (!cardSearch || !price || !qty) {
        showNotification('Please fill in all fields', 'danger');
        return;
    }
    
    showNotification(`✅ Listing created for "${cardSearch}" at $${price} (Qty: ${qty})`, 'success');
    document.querySelector('.modal-overlay').remove();
}

/**
 * Select card from search results
 */
function selectCard(cardName) {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.value = cardName;
        document.getElementById('searchResults').innerHTML = '';
    }
}

/**
 * Initialize page on load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add fade-in animation
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.3s ease';
        document.body.style.opacity = '1';
    }, 10);
});

// ============= DARK MODE TOGGLE (future feature) =============

/**
 * Toggle dark/light mode
 */
function toggleDarkMode() {
    const isDark = document.body.style.filter === 'invert(1)';
    document.body.style.filter = isDark ? 'none' : 'invert(1)';
    localStorage.setItem('darkMode', !isDark);
}

// ============= FORM HELPERS =============

/**
 * Validate form field
 */
function validateField(field, rules) {
    const value = field.value.trim();
    
    for (const rule of rules) {
        if (rule === 'required' && !value) {
            return false;
        }
        if (rule === 'email' && !value.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
            return false;
        }
        if (rule === 'number' && isNaN(value)) {
            return false;
        }
    }
    return true;
}

/**
 * Serialize form to object
 */
function serializeForm(form) {
    const data = new FormData(form);
    const obj = {};
    for (const [key, value] of data) {
        obj[key] = value;
    }
    return obj;
}

// ============= ANIMATION HELPERS =============

/**
 * Animate counter from 0 to target
 */
function animateCounter(element, target, duration = 1000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = formatNumber(Math.floor(current));
    }, 16);
}

/**
 * Fade in elements
 */
function fadeIn(elements, delay = 0) {
    if (!Array.isArray(elements)) elements = [elements];
    
    elements.forEach((el, i) => {
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.animation = 'fadeInUp 0.5s ease forwards';
        }, i * delay);
    });
}

/**
 * Spin animation (for loading)
 */
function spin(element) {
    const styleId = 'mtg-inventory-spin-keyframes';
    if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
    element.style.animation = 'spin 1s linear infinite';
}

// ============= MODAL HELPERS =============

/**
 * Show modal dialog
 */
function showModal(title, content, buttons = []) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    const modalBox = document.createElement('div');
    modalBox.className = 'modal';

    const header = document.createElement('div');
    header.className = 'modal-header';
    const heading = document.createElement('h2');
    heading.textContent = title;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close';
    closeBtn.type = 'button';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', () => modal.remove());
    header.appendChild(heading);
    header.appendChild(closeBtn);

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    if (content instanceof Node) {
        modalContent.appendChild(content);
    } else {
        // Content provided to this helper is app-authored markup.
        modalContent.innerHTML = String(content || '');
    }

    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    buttons.forEach((btn) => {
        const button = document.createElement('button');
        button.className = `btn btn-${btn.style || 'primary'}`;
        button.type = 'button';
        button.textContent = btn.label || 'OK';
        if (typeof btn.onclick === 'function') {
            button.addEventListener('click', btn.onclick);
        }
        footer.appendChild(button);
    });

    modalBox.appendChild(header);
    modalBox.appendChild(modalContent);
    modalBox.appendChild(footer);
    modal.appendChild(modalBox);

    const modalStyleId = 'mtg-inventory-modal-styles';
    if (!document.getElementById(modalStyleId)) {
        const style = document.createElement('style');
        style.id = modalStyleId;
        style.textContent = `
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            max-width: 500px;
            width: 90%;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px;
            border-bottom: 1px solid var(--border);
        }
        .modal-content {
            padding: 24px;
        }
        .modal-footer {
            display: flex;
            gap: 12px;
            padding: 16px 24px;
            border-top: 1px solid var(--border);
            justify-content: flex-end;
        }
        .modal-close {
            background: none;
            border: none;
            color: var(--text);
            font-size: 24px;
            cursor: pointer;
        }
    `;
        document.head.appendChild(style);
    }
    document.body.appendChild(modal);
}

// Export for use in other modules if needed
window.MTGInventory = {
    formatNumber,
    formatCurrency,
    formatDate,
    debounce,
    showNotification,
    apiCall,
    searchCards,
    getCardPricing,
    formatLocationCode,
    formatEBayTitle,
    calculateSuggestedPrice,
    validateField,
    serializeForm,
    animateCounter,
    fadeIn,
    spin,
    showModal
};
