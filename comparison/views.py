from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from product.models import Product


def home_page(request):
    return render(request, 'home_page.html')


class ProductComparisonView(APIView):
    """
    Search products by keyword across all sites and return results grouped by site.
    Query param: ?product=<keyword>
    """

    def get(self, request):
        query = request.query_params.get('product', '').strip()
        if not query:
            return Response({"error": "Product name is required"}, status=HTTP_400_BAD_REQUEST)

        products = (
            Product.objects
            .filter(name__icontains=query)
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