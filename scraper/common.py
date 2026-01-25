import aiohttp, asyncio, os
from typing import TypedDict

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()


class ProductData(TypedDict):
    name: str
    price: str
    description: str


class HttpClientFetcher:
    """Fetches HTML content using aiohttp client"""

    def __init__(self, session: aiohttp.ClientSession, logger):
        self.logger = logger
        self.session = session

    async def fetch(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"
        }
        async with self.session.get(url, headers=headers) as response:
            self.logger.info(f"Fetching URL: {url} - Status: {response.status}")
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')

            if 'application/json' in content_type:
                data = await response.json()
            else:
                data = await response.text()
            return data

class PlaywrightClientFetcher:
    """Fetches HTML content using Playwright"""

    def __init__(self, logger):
        self.logger = logger
        self._browser = None
        self._context = None
        self._playwright = None
        self._sem = None

    async def start(self):
        if self._browser:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-first-run",
                "--disable-features=site-per-process"
            ]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1366, "height": 768}, java_script_enabled=True
        )
        await self._context.route(
            "**/*",
            lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font",
                                                                           "media"] else route.continue_())
        self._sem = asyncio.Semaphore(int(os.getenv('PLAYWRIGHT_CONCURRENCY', '10')))
        self.logger.info("Playwright browser started")

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.logger.info("Playwright browser stopped")

    async def fetch(self, url: str) -> str:
        async with self._sem:
            page = await self._context.new_page()
            page.set_default_navigation_timeout(30_000)
            try:
                response = await page.goto(url, timeout=30_000, wait_until='domcontentloaded')
                self.logger.info(f"Fetching URL: {url} - Status: {response.status}")
                content = await page.content()
                return content
            except Exception as e:
                self.logger.error(f"Error fetching URL {url}: {str(e)}")
                return ""
            finally:
                await page.close()


class SmartFetcher:
    """Fetcher that chooses between HTTP client and Playwright based on response status"""

    def __init__(self, http_fetcher: HttpClientFetcher, playwright_fetcher: PlaywrightClientFetcher, logger):
        self.http_fetcher = http_fetcher
        self.playwright_fetcher = playwright_fetcher
        self.is_blocked = False
        self.logger = logger

    async def fetch(self, url: str) -> str:
        try:
            if not self.is_blocked:
                self.logger.info(f"Using HTTP client for URL: {url}")
                content = await self.http_fetcher.fetch(url)
                if not content or "Please enable JavaScript" in content:
                    self.is_blocked = True
                return content
            if self.is_blocked:
                self.logger.info(f"Using Playwright for URL: {url}")
                await self.playwright_fetcher.start()
                content = await self.playwright_fetcher.fetch(url)
                return content
        except Exception as e:
            self.logger.error(f"Error in SmartFetcher for URL {url}: {str(e)}")
            status = getattr(e, "status", None)
            if status == 403:
                self.is_blocked = True
                self.logger.info(f"Using Playwright for URL: {url}")
                await self.playwright_fetcher.start()
                return await self.playwright_fetcher.fetch(url)
            return ""

