import gc
import asyncio
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from .common import RateLimiter, AsyncCallAPIClient, ProductDetailStrategy, ProductDetailExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RyansScraper")


class GenericProductStrategy(ProductDetailStrategy):
    """Generic strategy for all product details"""

    async def extract(self, product_url: str, context):
        logger.info(f"Fetching product details from {product_url}")
        page = await context.new_page()
        page.set_default_navigation_timeout(30_000)

        try:
            response = await page.goto(product_url, timeout=30_000, wait_until='domcontentloaded')
            logger.warning(f"Received async response status: {response.status} for URL: {product_url}")
            content = await page.content()
        except Exception as e:
            logger.error(f"Error fetching product details from {product_url}: {str(e)}")
            await page.close()
            return {}
        finally:
            await page.close()

        soup = BeautifulSoup(content, 'html.parser')

        # Extract product details
        name = soup.find('h1', attrs={"itemprop": "name"}).get_text(strip=True)
        price_tag = soup.find('span', class_="new-sp-text")
        if not price_tag:
            price_tag = soup.find('span', class_="stock-text")
        description = soup.find("div", class_="short-desc-attr").find("ul")
        if description:
            description.attrs.pop("class", None)
            for li in description.find_all(True):
                li.attrs.pop("class", None)

        return {
            "name": name,
            "price": price_tag.get_text(strip=True),
            "description": str(description if description else ""),
        }


class ProductStrategyFactory:
    """Factory for creating product detail strategy"""
    def __init__(self):
        self.client_type = "playwright"

    def create_strategy(self, category: str) -> ProductDetailStrategy:
        # No specific strategies needed, always return generic
        return GenericProductStrategy()


class RyansScraper:
    """Main scraper class that coordinates the entire scraping process"""

    def __init__(self, base_url: str = "https://www.ryans.com/api/product-search"):
        self.rate_limiter = RateLimiter(calls_per_second=2.0)
        self.api_client = AsyncCallAPIClient(logger, base_url)
        self.extractor = ProductDetailExtractor(self.rate_limiter, ProductStrategyFactory, logger)

    async def scrape(self, query: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Scrape products based on search query"""
        all_products = []

        # Fetch products from search results
        for page in range(1, max_pages + 1):
            search_result = await self.api_client.search(query, page)
            if not search_result:
                return []
            soup = BeautifulSoup(search_result, 'html.parser')
            products = soup.find_all("a", class_="snize-item")
            # TODO: need to handle comming soon products
            for product in products:
                if product and product.get("href"):
                    all_products.extend([{"href": product.get("href")}])

        logger.info(f"Found total of {len(all_products)} products")

        # Extract detailed information for each product
        result = await self.extractor.extract_details(all_products)
        gc.collect()
        return result


async def main():
    """Example usage"""
    scraper = RyansScraper()
    products = await scraper.scrape("Ryzen 5 7600X")
    print(f"Scraped {len(products)} products")
    print(products)


if __name__ == "__main__":
    asyncio.run(main())