from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

from product.models import Product
from .search import semantic_search


def semantic_product_search(query: str, top_k: int = 5) -> dict:
    """For fuzzy/descriptive queries — 'budget wireless earbuds', 'gaming laptop under heavy load'."""
    results = semantic_search(query, top_k=top_k, max_distance=0.6)
    if not results:
        return {"results": [], "message": "No close matches found."}
    return {
        "results": [
            {
                "name": r["product"].name,
                "price": str(r["product"].price),
                "site": r["product"].site.name if r["product"].site else None,
                "category": r["product"].category.name if r["product"].category else None,
                "url": r["product"].url,
                "similarity_distance": round(r["distance"], 4),
            }
            for r in results
        ]
    }


def get_cheapest_product(category_name: str, site_name: str | None = None) -> dict:
    """Find the cheapest product in a given category, optionally filtered by site."""
    qs = Product.objects.select_related("site", "category").filter(
        category__name__icontains=category_name
    )
    if site_name:
        qs = qs.filter(site__name__icontains=site_name)

    product = qs.order_by("price").first()
    if not product:
        return {"error": f"No products found in category matching '{category_name}'."}

    return {
        "name": product.name,
        "price": str(product.price),
        "site": product.site.name if product.site else None,
        "url": product.url,
    }


def get_price_trend(product_name: str, days: int = 30) -> dict:
    """Get price history for a product over the last N days."""
    product = Product.objects.filter(name__icontains=product_name).select_related("site").first()
    if not product:
        return {"error": f"No product found matching '{product_name}'."}

    since = timezone.now() - timedelta(days=days)
    history = product.price_history.filter(recorded_at__gte=since).order_by("recorded_at")

    points = [
        {"price": str(h.price), "recorded_at": h.recorded_at.isoformat()} for h in history
    ]

    return {
        "product": product.name,
        "current_price": str(product.price),
        "site": product.site.name if product.site else None,
        "history": points or "No recorded price changes in this window.",
    }


def compare_prices_across_sites(product_name: str) -> dict:
    """Compare prices for matching products across different sites."""
    products = Product.objects.filter(name__icontains=product_name).select_related("site")
    if not products.exists():
        return {"error": f"No products found matching '{product_name}'."}

    return {
        "results": [
            {"name": p.name, "site": p.site.name if p.site else None, "price": str(p.price), "url": p.url}
            for p in products
        ]
    }


# Registry mapping tool name -> callable, used by the router to dispatch calls
TOOL_REGISTRY = {
    "semantic_product_search": semantic_product_search,
    "get_cheapest_product": get_cheapest_product,
    "get_price_trend": get_price_trend,
    "compare_prices_across_sites": compare_prices_across_sites,
}


# Ollama tool-calling schema (OpenAI-compatible function calling format)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "semantic_product_search",
            "description": "Search for products by natural language description when the user wants recommendations or similar items, not exact facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language product description"},
                    "top_k": {"type": "integer", "description": "Number of results to return", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cheapest_product",
            "description": "Find the cheapest product in a specific category, e.g. 'cheapest headphones'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {"type": "string"},
                    "site_name": {"type": "string", "description": "Optional site filter"},
                },
                "required": ["category_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_trend",
            "description": "Get price history/trend for a specific named product over recent days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "days": {"type": "integer", "default": 30},
                },
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_prices_across_sites",
            "description": "Compare the price of a specific named product across different sites.",
            "parameters": {
                "type": "object",
                "properties": {"product_name": {"type": "string"}},
                "required": ["product_name"],
            },
        },
    },
]