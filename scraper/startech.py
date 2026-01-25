import json, gc, aiohttp, asyncio, logging

from bs4 import BeautifulSoup

from .common import HttpClientFetcher, PlaywrightClientFetcher, SmartFetcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StarTechScraper")


class StarTechScraper:
    """Main scraper class that coordinates the entire scraping process"""

    def __init__(self, base_url: str = "https://www.startech.com.bd/common/search_suggestion/index"):
        self.base_url = base_url
        self.smart_fetcher = None

    async def extract(self, url):
        content = await self.smart_fetcher.fetch(url)
        soup = BeautifulSoup(content, 'html.parser')

        # Extract product details
        name = soup.find('h1', class_="product-name").get_text(strip=True)
        price = soup.find('td', class_="product-price")
        if price.find("ins"):
            price = price.find("ins").get_text(strip=True)
        else:
            price = price.get_text(strip=True)
        description = soup.find("div", class_="short-description").find("ul")

        return {
            "url": url,
            "name": name,
            "price": price,
            "description": str(description if description else ""),
        }

    async def extract_details(self, products):
        tasks = []
        for product in products:
            if product and product.get("href"):
                tasks.append(self.extract(product.get("href")))
        return await asyncio.gather(*tasks)

    async def scrape(self, query: str, max_pages: int = 1):
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

            search_result = json.loads(search_result)
            products = search_result.get("products", [])
            if not products:
                return []

            all_products.extend([product for product in products if not product.get("type")])
            logger.info(f"Found total of {len(all_products)} products")

            # Extract detailed information for each product
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
    scraper = StarTechScraper()
    products = await scraper.scrape("intel core i7")
    print(f"Scraped {len(products)} products")
    print(products)


if __name__ == "__main__":
    asyncio.run(main())
