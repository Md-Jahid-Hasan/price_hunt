import json
import aiohttp
import asyncio
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from .common import RateLimiter, SearchAPIClient, ProductDetailStrategy, ProductDetailExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StarTechScraper")


class GenericProductStrategy(ProductDetailStrategy):
    """Generic strategy for all product details"""

    async def extract(self, product_url: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
        logger.info(f"Fetching product details from {product_url}")
        async with session.get(product_url) as response:
            logger.warning(f"Received response status: {response.status} for URL: {product_url}")
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            # Extract product details
            specs = {}
            name = soup.find('h1', class_="product-name").get_text(strip=True)
            price = soup.find('td', class_="product-price")
            if price.find("ins"):
                price = price.find("ins").get_text(strip=True)
            else:
                price = price.get_text(strip=True)
            description = soup.find("div", class_="short-description").find("ul")

            return {
                "name": name,
                "price": price,
                "description": str(description if description else ""),
            }


class ProductStrategyFactory:
    """Factory for creating product detail strategy"""
    def __init__(self):
        self.client_type = "aiohttp"

    def create_strategy(self, category: str) -> ProductDetailStrategy:
        # No specific strategies needed, always return generic
        return GenericProductStrategy()


class StarTechScraper:
    """Main scraper class that coordinates the entire scraping process"""

    def __init__(self, base_url: str = "https://www.startech.com.bd/common/search_suggestion/index"):
        self.rate_limiter = RateLimiter(calls_per_second=2.0)
        self.api_client = SearchAPIClient(logger, base_url)
        self.extractor = ProductDetailExtractor(self.rate_limiter, ProductStrategyFactory, logger)

    async def scrape(self, query: str, max_pages: int = 1):
        """Scrape products based on search query"""
        all_products = []

        # Fetch products from search results
        for page in range(1, max_pages + 1):
            search_result = await self.api_client.search(query, page)
            search_result = json.loads(search_result)
            products = search_result.get("products", [])
            if not products:
                break

            all_products.extend([product for product in products if not product.get("type")])

        logger.info(f"Found total of {len(all_products)} products")

        # Extract detailed information for each product
        return await self.extractor.extract_details(all_products)


async def main():
    """Example usage"""
    scraper = StarTechScraper()
    products = await scraper.scrape("intel core i7")
    print(f"Scraped {len(products)} products")
    print(products)


if __name__ == "__main__":
    asyncio.run(main())