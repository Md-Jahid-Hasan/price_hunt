import aiohttp
import asyncio
import time
from typing import Dict, Any, List, TypedDict
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright


class ProductData(TypedDict):
    name: str
    price: str
    description: str


class ProductDetailStrategy(ABC):
    """Abstract strategy for extracting product details"""

    @abstractmethod
    async def extract(self, product_url: str, session: Any) -> ProductData:
        raise NotImplementedError


class RateLimiter:
    """Simple rate limiter to prevent overwhelming the server"""

    def __init__(self, calls_per_second: float = 2.0):
        self.interval = 1.0 / calls_per_second
        self.last_call = 0

    async def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self.last_call = time.time()


class AsyncCallAPIClient:
    def __init__(self, logger, base_url: str):
        self.logger = logger
        self.base_url = base_url
        self.rate_limiter = RateLimiter()

    async def search(self, query: str, page: int = 1) -> str | Dict[str, Any]:
        await self.rate_limiter.wait()
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context(user_agent='Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0')
                page_obj = await context.new_page()
                page_obj.set_default_navigation_timeout(30_000)
                url = f"{self.base_url}?keyword={query}"
                response = await page_obj.goto(url, timeout=30_000, wait_until='domcontentloaded')
                self.logger.warning(f"Received async response status: {response.status} for URL: {url}")
                content = await page_obj.content()
                await browser.close()
                return content
        except Exception as e:
            self.logger.error(f"Search error: {str(e)}")
            return False


class SearchAPIClient:
    """Client for interacting with the search API"""

    def __init__(self, logger, base_url: str):
        self.logger = logger
        self.base_url = base_url
        self.rate_limiter = RateLimiter()

    # In SearchAPIClient.search method
    async def search(self, query: str, page: int = 1) -> str | Dict[str, Any]:
        await self.rate_limiter.wait()
        try:
            async with aiohttp.ClientSession() as session:
                url = self.base_url
                params = {"keyword": query}
                header = {
                    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"
                }

                self.logger.info(f"Searching for '{query}' on page {page}")
                async with session.get(url, params=params) as response:
                    self.logger.warning(f"Received response status: {response.status}")
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '')

                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                        self.logger.warning(f"Received non-JSON response: {content_type}")
                    return data
        except Exception as e:
            self.logger.error(f"Search error: {str(e)}")
            return False


class ProductDetailExtractor:
    """Coordinates extraction of product details using appropriate strategies"""

    def __init__(self, rate_limiter: RateLimiter, strategy_factory: Any, logger):
        self.rate_limiter = rate_limiter
        self.strategy_factory = strategy_factory()
        self.logger = logger

    async def extract_details(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = []
        if self.strategy_factory.client_type == "aiohttp":
            async with aiohttp.ClientSession() as session:
                for product in products:
                    tasks.append(self._process_product(product, session))
                return await asyncio.gather(*tasks)
        elif self.strategy_factory.client_type == "playwright":
            async with async_playwright() as session:
                browser = await session.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0')
                for product in products:
                    tasks.append(self._process_product(product, context))
                return await asyncio.gather(*tasks)

    async def _process_product(self, product: Dict[str, Any], session) -> Dict[str, Any]:
        await self.rate_limiter.wait()

        # Get basic product info
        result = {
            # "id": product.get("id"),
            # "name": product.get("name"),
            # "price": product.get("price"),
            "url": product.get("href"),
            # "category": product.get("category", "")
        }

        try:
            # Get detailed info using appropriate strategy
            strategy = self.strategy_factory.create_strategy("generic")
            details = await strategy.extract(result["url"], session)
            result.update(details)
        except Exception as e:
            self.logger.error(f"Error extracting details for {result['url']}: {str(e)}")

        return result