// Global state
let allProducts = [];
let filteredProducts = [];
let currentSort = 'price-low';
let currentAvailability = 'all';
let currentPage = 1;
const ITEMS_PER_PAGE = 12;

// Convert a site name to a CSS-safe slug (e.g. "Star Tech" → "star-tech")
function slugify(name) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// Format a raw decimal price string as "৳ 75,000"
function formatPrice(priceStr) {
    const num = parseFloat(priceStr);
    if (!num) return 'Not Available';
    return '৳ ' + Math.round(num).toLocaleString();
}

// Search functionality
async function searchProducts() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput.value.trim();

    if (!query) {
        showError('Please enter a product name');
        return;
    }

    document.getElementById('loading').classList.add('active');
    document.getElementById('resultsContainer').classList.remove('active');
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('errorMessage').classList.remove('active');
    document.getElementById('filterControls').style.display = 'none';
    document.getElementById('resultsSummary').style.display = 'none';

    try {
        const response = await fetch(`/api/product-comparison/?product=${encodeURIComponent(query)}`);

        if (!response.ok) {
            throw new Error('Failed to fetch products');
        }

        const data = await response.json();
        document.getElementById('loading').classList.remove('active');
        displayResults(data);

    } catch (error) {
        document.getElementById('loading').classList.remove('active');
        showError('Failed to search products. Please try again.');
        console.error('Error:', error);
    }
}

// Display results — works with any number of sites
function displayResults(data) {
    if (data.error) {
        showError(data.error);
        return;
    }

    allProducts = [];

    // Iterate over every site key returned by the API dynamically
    Object.entries(data).forEach(([siteName, products]) => {
        if (!Array.isArray(products) || products.length === 0) return;
        const storeSlug = slugify(siteName);
        products.forEach(p => {
            allProducts.push({
                ...p,
                store: storeSlug,
                storeName: siteName,
                priceValue: extractPrice(p.price),
            });
        });
    });

    if (allProducts.length === 0) {
        document.getElementById('emptyState').style.display = 'block';
        return;
    }

    populateStoreFilter();

    currentSort = 'price-low';
    currentAvailability = 'all';
    document.getElementById('storeFilter').value = 'all';
    document.getElementById('sortFilter').value = 'sort:price-low';

    updateSummary();
    sortAndDisplayResults();

    document.getElementById('filterControls').style.display = 'flex';
    document.getElementById('resultsSummary').style.display = 'flex';
    document.getElementById('resultsContainer').classList.add('active');
}

// Rebuild the store filter dropdown from the current result set
function populateStoreFilter() {
    const storeFilter = document.getElementById('storeFilter');

    // Remove only previously injected dynamic options, keep the static "All" option
    storeFilter.querySelectorAll('option[data-dynamic]').forEach(o => o.remove());

    const seen = new Set();
    allProducts.forEach(({ store, storeName }) => {
        if (seen.has(store)) return;
        seen.add(store);
        const option = document.createElement('option');
        option.value = store;
        option.textContent = storeName;
        option.dataset.dynamic = '1';
        storeFilter.appendChild(option);
    });
}

// Called when the combined Sort / Filter dropdown changes
function onSortFilterChange(select) {
    const [prefix, value] = select.value.split(':');
    if (prefix === 'sort') {
        currentSort = value;
    } else if (prefix === 'avail') {
        currentAvailability = value;
    }
    sortAndDisplayResults();
}

// Sort and display results
function sortAndDisplayResults() {
    const storeFilter = document.getElementById('storeFilter').value;

    filteredProducts = [...allProducts];

    if (storeFilter !== 'all') {
        filteredProducts = filteredProducts.filter(p => p.store === storeFilter);
    }

    if (currentAvailability === 'available') {
        filteredProducts = filteredProducts.filter(p => p.priceValue > 0);
    }

    if (currentSort === 'price-low') {
        filteredProducts.sort((a, b) => a.priceValue - b.priceValue);
    } else if (currentSort === 'price-high') {
        filteredProducts.sort((a, b) => b.priceValue - a.priceValue);
    } else if (currentSort === 'store') {
        filteredProducts.sort((a, b) => a.storeName.localeCompare(b.storeName));
    }

    currentPage = 1;
    updateShowingCount(filteredProducts.length, storeFilter);

    const grid = document.getElementById('productsGrid');
    grid.innerHTML = '';
    document.getElementById('pagination').innerHTML = '';

    if (filteredProducts.length === 0) {
        grid.innerHTML = '<div class="empty-state"><h3>No products found</h3><p>Try adjusting your filters</p></div>';
        return;
    }

    renderPage();
}

// Append current page of products to the grid, then fetch price history for the batch
function renderPage() {
    const total = filteredProducts.length;
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = Math.min(start + ITEMS_PER_PAGE, total);
    const batch = filteredProducts.slice(start, end);
    const grid = document.getElementById('productsGrid');

    batch.forEach(p => grid.appendChild(createProductCard(p)));
    renderLoadMoreBtn(end < total, end, total);

    const ids = batch.map(p => p.id).filter(Boolean);
    if (ids.length) fetchPriceHistory(ids);
}

// Load the next batch of products
function loadMore() {
    currentPage++;
    renderPage();
}

// Render the load-more button (or a completion note when all products are shown)
function renderLoadMoreBtn(hasMore, loaded, total) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';

    if (!hasMore) {
        if (total > ITEMS_PER_PAGE) {
            const msg = document.createElement('p');
            msg.className = 'all-loaded-msg';
            msg.textContent = `All ${total} products loaded`;
            container.appendChild(msg);
        }
        return;
    }

    const remaining = Math.min(total - loaded, ITEMS_PER_PAGE);
    const btn = document.createElement('button');
    btn.className = 'load-more-btn';
    btn.innerHTML = `&#43; Load ${remaining} More <span class="load-more-badge">${loaded} / ${total}</span>`;
    btn.addEventListener('click', loadMore);
    container.appendChild(btn);
}

// Fetch price history for a batch of product IDs and paint cards
async function fetchPriceHistory(ids) {
    try {
        const res = await fetch(`/api/pice-history/?ids=${ids.join(',')}`);
        if (!res.ok) return;
        const data = await res.json();
        Object.entries(data).forEach(([productId, points]) => {
            paintHistory(productId, points);
        });
    } catch (e) {
        console.error('Price history error:', e);
    }
}

// Replace the skeleton in a card with real history data
function paintHistory(productId, points) {
    const card = document.querySelector(`[data-product-id="${productId}"]`);
    if (!card) return;
    const panel = card.querySelector('.price-history');
    if (!panel) return;

    if (!points || points.length === 0) {
        panel.innerHTML = '<p class="history-empty">No price history available</p>';
        return;
    }

    const sorted = [...points].sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at));
    const prices = sorted.map(p => parseFloat(p.price));
    const first = prices[0];
    const last = prices[prices.length - 1];
    const pct = ((last - first) / first * 100).toFixed(1);
    const isDown = last < first;
    const isFlat = last === first;
    const trendClass = isFlat ? 'trend-stable' : isDown ? 'trend-down' : 'trend-up';
    const trendText = isFlat ? '→ Stable' : `${isDown ? '↓' : '↑'} ${Math.abs(pct)}%`;

    panel.innerHTML = `
        <div class="history-header">
            <span class="history-label">2-month trend</span>
            <span class="price-trend ${trendClass}">${trendText}</span>
        </div>
        ${buildSparkline(prices, isDown, isFlat)}
    `;
}

// Build an SVG area sparkline from an array of prices
function buildSparkline(prices, isDown, isFlat) {
    const W = 200, H = 40;
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const pad = 4;

    const pts = prices.map((p, i) => ({
        x: (i / Math.max(prices.length - 1, 1)) * W,
        y: H - pad - ((p - min) / range) * (H - pad * 2),
    }));

    const linePts = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const areaPath = `M${pts[0].x},${H} ${pts.map(p => `L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')} L${pts[pts.length - 1].x},${H} Z`;

    const stroke = isFlat ? '#94a3b8' : isDown ? '#10b981' : '#ef4444';
    const fill   = isFlat ? 'rgba(148,163,184,0.1)' : isDown ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.1)';

    return `<svg class="sparkline" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <path d="${areaPath}" fill="${fill}"/>
        <polyline points="${linePts}" fill="none" stroke="${stroke}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
}

// Create product card
function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card';
    if (product.id) card.dataset.productId = product.id;

    // Meta row: store badge + category tag
    const metaRow = document.createElement('div');
    metaRow.className = 'card-meta';

    const storeBadge = document.createElement('span');
    storeBadge.className = `store-badge badge-${product.store}`;
    storeBadge.textContent = product.storeName;
    metaRow.appendChild(storeBadge);

    if (product.category) {
        const categoryTag = document.createElement('span');
        categoryTag.className = 'category-tag';
        categoryTag.textContent = product.category;
        metaRow.appendChild(categoryTag);
    }

    const productName = document.createElement('div');
    productName.className = 'product-name';
    productName.textContent = product.name || 'Product Name';

    const productPrice = document.createElement('div');
    productPrice.className = 'product-price';
    productPrice.textContent = formatPrice(product.price);

    const historyPanel = document.createElement('div');
    historyPanel.className = 'price-history';
    if (product.id) {
        historyPanel.innerHTML = '<div class="history-skeleton"></div>';
    } else {
        historyPanel.innerHTML = '<p class="history-empty">No price history available</p>';
    }

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'product-actions';

    const viewBtn = document.createElement('a');
    viewBtn.href = product.url || '#';
    viewBtn.target = '_blank';
    viewBtn.className = 'btn btn-primary';
    viewBtn.textContent = 'View Details';

    actionsDiv.appendChild(viewBtn);

    card.appendChild(metaRow);
    card.appendChild(productName);
    card.appendChild(productPrice);
    card.appendChild(historyPanel);
    card.appendChild(actionsDiv);

    return card;
}

// Extract numeric price from a decimal string like "75000.00"
function extractPrice(priceStr) {
    if (!priceStr) return 0;
    return parseFloat(String(priceStr).replace(/,/g, '')) || 0;
}

// Update total counters (called once per search)
function updateSummary() {
    const stores = new Set(allProducts.map(p => p.store));
    document.getElementById('totalStores').textContent = String(stores.size);
    document.getElementById('totalProducts').textContent = String(allProducts.length);
    document.getElementById('showingCount').textContent = String(allProducts.length);
    document.getElementById('showingLabel').textContent = 'Showing';
}

// Update the "Showing" counter after filters are applied
function updateShowingCount(count, storeSlug) {
    document.getElementById('showingCount').textContent = String(count);
    if (storeSlug === 'all') {
        document.getElementById('showingLabel').textContent = 'Showing';
    } else {
        const storeFilter = document.getElementById('storeFilter');
        const selected = storeFilter.options[storeFilter.selectedIndex];
        document.getElementById('showingLabel').textContent = `From ${selected.textContent}`;
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.add('active');
    setTimeout(() => errorDiv.classList.remove('active'), 5000);
}

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('searchInput').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') searchProducts();
    });
});