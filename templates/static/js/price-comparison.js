// Global state
let allProducts = [];
let filteredProducts = [];

// Search functionality
async function searchProducts() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput.value.trim();

    if (!query) {
        showError('Please enter a product name');
        return;
    }

    // Show loading state
    document.getElementById('loading').classList.add('active');
    document.getElementById('resultsContainer').classList.remove('active');
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('errorMessage').classList.remove('active');
    document.getElementById('filterControls').style.display = 'none';
    document.getElementById('resultsSummary').style.display = 'none';

    try {
        // Make API call
        const response = await fetch(`/api/product-comparison/?product=${encodeURIComponent(query)}`);

        if (!response.ok) {
            throw new Error('Failed to fetch products');
        }

        const data = await response.json();

        // Hide loading
        document.getElementById('loading').classList.remove('active');

        // Display results
        displayResults(data);

    } catch (error) {
        console.log(error)
        document.getElementById('loading').classList.remove('active');
        showError('Failed to search products. Please try again.');
        console.error('Error:', error);
    }
}

// Display results
function displayResults(data) {
    // Check if there's an error in the response
    if (data.error) {
        showError(data.error);
        return;
    }

    allProducts = [];

    // Collect all products with store info
    if (data.ryans && Array.isArray(data.ryans) && data.ryans.length > 0) {
        data.ryans.forEach(p => {
            const price = extractPrice(p.price);
            if (price >= 0) { // Filter out products with "BDT 0" or invalid prices
                allProducts.push({...p, store: 'ryans', storeName: 'Ryans', priceValue: price});
            }
        });
    }

    if (data.startech && Array.isArray(data.startech) && data.startech.length > 0) {
        data.startech.forEach(p => {
            const price = extractPrice(p.price);
            if (price >= 0) { // Filter out products with "BDT 0" or invalid prices
                allProducts.push({...p, store: 'startech', storeName: 'Star Tech', priceValue: price});
            }
        });
    }

    if (allProducts.length === 0) {
        showError('No products found. Try a different search term.');
        return;
    }
    console.log(allProducts)

    // Reset filters
    document.getElementById('storeFilter').value = 'all';
    document.getElementById('availabilityFilter').value = 'all';
    document.getElementById('sortSelect').value = 'price-low';

    // Update summary and display
    updateSummary();
    sortAndDisplayResults();

    // Show controls
    document.getElementById('filterControls').style.display = 'flex';
    document.getElementById('resultsSummary').style.display = 'flex';
    document.getElementById('resultsContainer').classList.add('active');
}

// Sort and display results
function sortAndDisplayResults() {
    const sortValue = document.getElementById('sortSelect').value;
    const storeFilter = document.getElementById('storeFilter').value;
    const availabilityFilter = document.getElementById('availabilityFilter').value;

    // Start with all products
    filteredProducts = [...allProducts];

    // Filter by store
    if (storeFilter !== 'all') {
        filteredProducts = filteredProducts.filter(p => p.store === storeFilter);
    }

    // Filter by availability (price > 0)
    if (availabilityFilter === 'available') {
        filteredProducts = filteredProducts.filter(p => p.priceValue > 0);
    }

    // Sort
    if (sortValue === 'price-low') {
        filteredProducts.sort((a, b) => a.priceValue - b.priceValue);
    } else if (sortValue === 'price-high') {
        filteredProducts.sort((a, b) => b.priceValue - a.priceValue);
    } else if (sortValue === 'store') {
        filteredProducts.sort((a, b) => a.storeName.localeCompare(b.storeName));
    }

    // Display products
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

    // Store badge
    const storeBadge = document.createElement('span');
    storeBadge.className = `store-badge badge-${product.store}`;
    storeBadge.textContent = product.storeName;

    // Product name
    const productName = document.createElement('div');
    productName.className = 'product-name';
    productName.textContent = product.name || 'Product Name';

    // Product price
    const productPrice = document.createElement('div');
    productPrice.className = 'product-price';
    productPrice.textContent = product.price || 'Price N/A';

    // Specs
    const specsDiv = document.createElement('div');
    specsDiv.className = 'product-specs';
    if (product.description_html) {
        specsDiv.innerHTML = product.description_html;
    } else if (product.description) {
        specsDiv.innerHTML = product.description;
    }

    // Actions
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'product-actions';

    const viewBtn = document.createElement('a');
    viewBtn.href = product.url || '#';
    viewBtn.target = '_blank';
    viewBtn.className = 'btn btn-primary';
    viewBtn.textContent = 'View Details';

    actionsDiv.appendChild(viewBtn);

    card.appendChild(storeBadge);
    card.appendChild(productName);
    card.appendChild(productPrice);
    if (product.description || product.description_html) {
        card.appendChild(specsDiv);
    }
    card.appendChild(actionsDiv);

    return card;
}

// Extract numeric price from string
function extractPrice(priceStr) {
    if (!priceStr) return 0;
    const match = priceStr.match(/[\d,]+/);
    if (!match) return 0;
    const price = parseFloat(match[0].replace(/,/g, ''));
    return price || 0;
}

// Update summary
function updateSummary() {
    const stores = new Set(allProducts.map(p => p.store));
    document.getElementById('totalStores').textContent = stores.size;
    document.getElementById('totalProducts').textContent = allProducts.length;
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.add('active');

    setTimeout(() => {
        errorDiv.classList.remove('active');
    }, 5000);
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Search on Enter key
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchProducts();
        }
    });
});
