import gc
import asyncio
import logging
from typing import List, Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from .common import HttpClientFetcher, PlaywrightClientFetcher, SmartFetcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RyansScraper")


class RyansScraper:
    """Main scraper class that coordinates the entire scraping process"""

    def __init__(self, base_url: str = "https://www.ryans.com/api/product-search"):
        self.base_url = base_url
        self.smart_fetcher = None

    async def extract(self, url):
        try:
            content = await self.smart_fetcher.fetch(url)
            if content:
                soup = BeautifulSoup(content, 'html.parser')

                # Extract product details
                name = soup.find('h1', attrs={"itemprop": "name"})
                price_tag = soup.select_one("span.stock-text, span.comming-soon-font, span.new-sp-text")
                description = soup.find("div", class_="short-desc-attr").find("ul")
                if description:
                    description.attrs.pop("class", None)
                    for li in description.find_all(True):
                        li.attrs.pop("class", None)
                if name and price_tag and description:
                    return {
                        "url": url,
                        "name": name.get_text(strip=True),
                        "price": price_tag.get_text(strip=True),
                        "description": str(description if description else ""),
                    }
                else:
                    logger.error(f"Missing data fields in product page: {url}")
                    return {}
            return {}
        except Exception as e:
            logger.error(f"Error extracting product details from {url}: {str(e)}")
            return {}

    async def extract_details(self, products):
        tasks = []
        for product in products:
            if product and product.get("href"):
                tasks.append(self.extract(product.get("href")))
        return await asyncio.gather(*tasks)

    async def scrape(self, query: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Scrape products based on search query"""
        try:
            all_products = []
            search_result = None
            client_session = None
            playwright_fetcher = None
            url = f"{self.base_url}?keyword={query}"

            # Fetch products from search results
            try:
                client_session = aiohttp.ClientSession()
                http_fetcher = HttpClientFetcher(client_session, logger)
                playwright_fetcher = PlaywrightClientFetcher(logger)
                self.smart_fetcher = SmartFetcher(http_fetcher, playwright_fetcher, logger)
                search_result = await self.smart_fetcher.fetch(url)
            except Exception as e:
                logger.error(f"Error fetching search results for query '{query}' on page {url}: {str(e)}")
                if client_session and playwright_fetcher:
                    await client_session.close()
                    await playwright_fetcher.stop()

            if not search_result:
                return []

            soup = BeautifulSoup(search_result, 'html.parser')
            products = soup.find_all("a", class_="snize-item")

            for product in products:
                if product and product.get("href"):
                    all_products.extend([{"href": product.get("href")}])

            logger.info(f"Found total of {len(all_products)} products")
            result = await self.extract_details(all_products)
            gc.collect()
            return result
        except Exception as e:
            logger.error(f"Error during scraping process for query '{query}': {str(e)}")
            return []
        finally:
            if client_session and playwright_fetcher:
                await client_session.close()
                await playwright_fetcher.stop()


async def main():
    """Example usage"""
    scraper = RyansScraper()
    products = await scraper.scrape("Ryzen 5 7600X")
    print(f"Scraped {len(products)} products")
    print(products)


if __name__ == "__main__":
    asyncio.run(main())
