// Global state
let allProducts = [];
let filteredProducts = [];

// Convert a site name to a CSS-safe slug (e.g. "Star Tech" → "star-tech")
function slugify(name) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// Format a raw decimal price string as "৳ 75,000"
function formatPrice(priceStr) {
    const num = parseFloat(priceStr);
    if (!num) return 'Price N/A';
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

    document.getElementById('storeFilter').value = 'all';
    document.getElementById('sortSelect').value = 'price-low';

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

// Sort and display results
function sortAndDisplayResults() {
    const sortValue = document.getElementById('sortSelect').value;
    const storeFilter = document.getElementById('storeFilter').value;

    filteredProducts = [...allProducts];

    if (storeFilter !== 'all') {
        filteredProducts = filteredProducts.filter(p => p.store === storeFilter);
    }

    const availabilityFilter = document.getElementById('availabilityFilter');
    if (availabilityFilter && availabilityFilter.value === 'available') {
        filteredProducts = filteredProducts.filter(p => p.priceValue > 0);
    }

    if (sortValue === 'price-low') {
        filteredProducts.sort((a, b) => a.priceValue - b.priceValue);
    } else if (sortValue === 'price-high') {
        filteredProducts.sort((a, b) => b.priceValue - a.priceValue);
    } else if (sortValue === 'store') {
        filteredProducts.sort((a, b) => a.storeName.localeCompare(b.storeName));
    }

    updateShowingCount(filteredProducts.length, storeFilter);
    displayProducts(filteredProducts);
}

// Display products
function displayProducts(products) {
    const grid = document.getElementById('productsGrid');
    grid.innerHTML = '';

    if (products.length === 0) {
        grid.innerHTML = '<div class="empty-state"><h3>No products found</h3><p>Try adjusting your filters</p></div>';
        return;
    }

    products.forEach(product => {
        grid.appendChild(createProductCard(product));
    });
}

// Create product card
function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card';

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

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'product-actions';

    const viewBtn = document.createElement('a');
    viewBtn.href = product.url || '#';
    viewBtn.target = '_blank';
    viewBtn.className = 'btn btn-primary';
    viewBtn.textContent = 'View Details';

    actionsDiv.appendChild(viewBtn);

    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'specs-toggle-btn';
    toggleBtn.innerHTML = 'Specifications <span class="specs-chevron">&#9660;</span>';

    const specsDiv = document.createElement('div');
    specsDiv.className = 'product-specs';

    const specsContent = document.createElement('div');
    specsContent.className = 'specs-content';

    const descriptionHtml = product.description_html || product.description;
    if (descriptionHtml) {
        specsContent.innerHTML = descriptionHtml;
    } else {
        specsContent.innerHTML = '<p class="specs-empty">No specifications available</p>';
    }

    specsDiv.appendChild(specsContent);

    toggleBtn.addEventListener('click', () => {
        const isOpen = specsDiv.classList.toggle('open');
        toggleBtn.classList.toggle('open', isOpen);
    });

    card.appendChild(metaRow);
    card.appendChild(productName);
    card.appendChild(productPrice);
    card.appendChild(toggleBtn);
    card.appendChild(specsDiv);
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