import asyncio

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from scraper.ryans import RyansScraper
from scraper.startech import StarTechScraper


def home_page(request):
    # render the home page template
    return render(request, 'home_page.html')


class ProductComparisonView(APIView):
    """
    View to handle product comparison requests.
    This view will accept a list of product URLs and return their details.
    """

    def get(self, request):
        # get product name from query parameters
        product_name = request.query_params.get('product', None)
        if not product_name:
            return Response({"error": "Product name is required"}, status=HTTP_400_BAD_REQUEST)

        try:
            # get data from get_scraped_data method
            results = asyncio.run(self.get_scraped_data(product_name))
            return Response(results, status=HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=HTTP_400_BAD_REQUEST)

    async def get_scraped_data(self, product_name):
        ryans = RyansScraper()
        startech = StarTechScraper()
        try:
            startech_data, ryans_data = await asyncio.gather(startech.scrape(product_name), ryans.scrape(product_name))
            return {
                "startech": startech_data,
                "ryans": ryans_data
            }
        except Exception as e:
            raise e


# uvicorn price_comparison.asgi:application --host 0.0.0.0 --port 8000