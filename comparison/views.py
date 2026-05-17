import re
from datetime import timedelta
from django.utils import timezone

from django.db.models import Q
from django.utils.text import slugify
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework import status

from product.models import Product, Category
from product.models import PriceHistory
from product.serializers import PricePointSerializer


MAX_PRODUCT_IDS = 50
HISTORY_DAYS = 62  # ~2 months


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
        pattern = r'(^|[-_ ])(?:' + '|'.join(escaped) + r')(?:$|[-_ ])'
        qs = Category.objects.filter(Q(slug__iregex=pattern) | Q(keywords__iregex=pattern))
        return qs

    def build_product_query(self, query_words: list[str]) -> Q:
        """
        Build a DB query where product name contains ALL query words (any order).
        This is more effective than icontains for multi-word searches.
        """
        q = Q()
        for word in query_words:
            # Each word must appear in the product name (case-insensitive)
            q &= Q(slug__icontains=word)
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
                "id": product.id,
                "name": product.name,
                "url": product.url,
                "price": str(product.price),
                "description": product.description,
                "category": product.category.name if product.category else "",
            })

        return Response(results, status=HTTP_200_OK)


class PriceHistoryView(APIView):
    """
    Returns the last 2-month price history for one or more products.

    GET /api/products/price-history/?ids=1,2,3

    - ids: comma-separated list of product IDs (max 50)

    Response shape:
    {
        "<product_id>": [
            {"price": "1500.00", "recorded_at": "2026-03-10T08:00:00Z"},
            ...
        ],
        ...
    }
    Products with no history in the window are included as empty lists.
    """

    def _parse_ids(self, raw: str) -> list[int] | None:
        """Returns deduplicated list of ints, or None on parse error."""
        try:
            ids = [int(x) for x in raw.split(",") if x.strip()]
        except ValueError:
            return None
        # Deduplicate while preserving order
        return list(dict.fromkeys(ids))

    def get(self, request):
        raw_ids = request.query_params.get("ids", "").strip()
        if not raw_ids:
            return Response(
                {"error": "Query parameter 'ids' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_ids = self._parse_ids(raw_ids)
        if product_ids is None:
            return Response(
                {"error": "All product IDs must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cutoff = timezone.now() - timedelta(days=HISTORY_DAYS)

        # Single query — the composite index (product_id, recorded_at DESC) makes this
        # efficient even on a very large table: index range scan per product, no seq scan.
        rows = (
            PriceHistory.objects.filter(
                product_id__in=product_ids,
                recorded_at__gte=cutoff,
            )
            .values("product_id", "price", "recorded_at")
            .order_by("product_id", "-recorded_at")
        )

        # Pre-populate all requested IDs so missing products appear as empty lists
        result: dict[str, list] = {str(pid): [] for pid in product_ids}

        for row in rows:
            key = str(row["product_id"])
            result[key].append(
                PricePointSerializer(
                    {"price": row["price"], "recorded_at": row["recorded_at"]}
                ).data
            )

        return Response(result, status=status.HTTP_200_OK)


# uvicorn price_comparison.asgi:application --host 0.0.0.0 --port 8000
# gunicorn --bind 0.0.0.0:8000 price_comparison.asgi:application -w 3 -k uvicorn.workers.UvicornWorker