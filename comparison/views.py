import re

from django.db.models import Q
from django.utils.text import slugify
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from product.models import Product, Category


def home_page(request):
    return render(request, 'home_page.html')


class ProductComparisonView(APIView):
    """
    Search products by keyword across all sites and return results grouped by site.
    Query param: ?product=<keyword>
    """

    def fetch_related_category(self, product_query):
        # Fetch related categories for the product query

        escaped = [re.escape(w) for w in product_query]
        pattern = r'(^|[-_])(?:' + '|'.join(escaped) + r')(?:$|[-_])'
        qs = Category.objects.filter(slug__iregex=pattern)
        return qs

    def build_product_query(self, query_words: list[str]) -> Q:
        """
        Build a DB query where product name contains ALL query words (any order).
        This is more effective than icontains for multi-word searches.
        """
        q = Q()
        for word in query_words:
            # Each word must appear in the product name (case-insensitive)
            q &= Q(name__icontains=word)
        return q

    def get(self, request):
        query = request.query_params.get('product', '').strip()
        if not query:
            return Response({"error": "Product name is required"}, status=HTTP_400_BAD_REQUEST)

        words = query.lower().split()
        words_norm = [slugify(w) for w in words if w]
        related_categories = self.fetch_related_category(words_norm)

        # Build query: product name contains ALL query words (improved from icontains)
        product_query = self.build_product_query(words_norm)

        products = list(
            Product.objects
            .filter(product_query, category__in=related_categories)
            .select_related('site', 'category')
            .order_by('site__name', 'price')
        )

        results: dict[str, list] = {}
        for product in products:
            site_name = product.site.name if product.site else "Unknown"
            results.setdefault(site_name, []).append({
                "name": product.name,
                "url": product.url,
                "price": str(product.price),
                "description": product.description,
                "category": product.category.name if product.category else "",
            })

        return Response(results, status=HTTP_200_OK)


# uvicorn price_comparison.asgi:application --host 0.0.0.0 --port 8000
# gunicorn --bind 0.0.0.0:8000 price_comparison.asgi:application -w 3 -k uvicorn.workers.UvicornWorker