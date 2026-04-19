import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol

from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup
from django.utils import timezone
from django.utils.text import slugify


class FetcherProtocol(Protocol):
    async def fetch(self, url: str) -> str:
        ...


class BasePaginatedScraper(ABC):
    """Shared template for category-based paginated scrapers."""

    def __init__(
        self,
        name: str,
        logger: logging.Logger,
        max_retries: int = 3,
        retry_delay: int = 2,
        max_concurrent_categories: int = 20,
        batch_pause: int = 5,
    ):
        self.name = name
        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_concurrent_categories = max_concurrent_categories
        self.batch_pause = batch_pause

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def all_categories(self) -> list[Any]:
        """Return the Category objects to scrape for this domain."""

    @abstractmethod
    async def create_fetcher(self) -> FetcherProtocol:
        """Create and initialize a fetcher implementation."""

    async def close_fetcher(self, fetcher: FetcherProtocol) -> None:
        """Optional cleanup hook for fetcher resources."""
        return None

    @abstractmethod
    def parse_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total page count from the first category page."""

    @abstractmethod
    def parse_products(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract products from one category page."""

    @abstractmethod
    def get_next_page_url(self, soup: BeautifulSoup) -> str:
        """Extract the URL for the next page from the pagination controls."""

    # ------------------------------------------------------------------
    # Shared flow
    # ------------------------------------------------------------------

    def _build_page_url(self, base_url: str, page: int) -> str:
        if page == 1:
            return base_url
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}page={page}"

    async def _fetch_with_retry(self, url: str, fetcher: FetcherProtocol) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                content = await fetcher.fetch(url)
                if content:
                    return content
                self.logger.warning(
                    "Empty response from %s (attempt %s/%s)",
                    url,
                    attempt,
                    self.max_retries,
                )
            except Exception as exc:
                self.logger.error(
                    "Fetch error for %s (attempt %s/%s): %s",
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                )

            if attempt < self.max_retries:
                wait = self.retry_delay * attempt
                self.logger.info("Retrying %s in %ss", url, wait)
                await asyncio.sleep(wait)

        self.logger.error("All %s fetch attempts exhausted for %s", self.max_retries, url)
        return ""

    async def _fetch_and_parse_page(
        self,
        base_url: str,
        page: int,
        fetcher: FetcherProtocol,
    ) -> list[dict[str, Any]]:
        page_url = self._build_page_url(base_url, page)
        self.logger.info("Fetching page %s: %s", page, page_url)

        content = await self._fetch_with_retry(page_url, fetcher)
        if not content:
            self.logger.warning("No content for page %s; skipping", page)
            return []

        soup = BeautifulSoup(content, "html.parser")
        products = self.parse_products(soup)
        self.logger.info("Page %s: extracted %s products", page, len(products))
        return products

    async def extract_data(self, url: str, fetcher: FetcherProtocol,  all_products: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not all_products:
            all_products: list[dict[str, Any]] = []
        self.logger.info("Fetching first page: %s", url)

        content = await self._fetch_with_retry(url, fetcher)
        if not content:
            self.logger.warning("Could not fetch first page for %s", url)
            return all_products

        soup = BeautifulSoup(content, "html.parser")

        page_products = self.parse_products(soup)
        all_products.extend(page_products)
        self.logger.info("Page %s: extracted %s products", url, len(page_products))

        next_page_link = self.get_next_page_url(soup)
        if next_page_link:
            await self.extract_data(next_page_link, fetcher, all_products)

        # total_pages = self.parse_total_pages(soup)
        # self.logger.info("Total pages detected: %s", total_pages)
        #
        # if total_pages <= 1:
        #     return all_products
        #
        # tasks = [
        #     self._fetch_and_parse_page(url, page, fetcher)
        #     for page in range(2, total_pages + 1)
        # ]
        # results = await asyncio.gather(*tasks, return_exceptions=True)
        #
        # for page_num, result in enumerate(results, start=2):
        #     if isinstance(result, Exception):
        #         self.logger.error("Page %s failed with exception: %s", page_num, result)
        #         continue
        #     all_products.extend(result)
        #
        # self.logger.info("Total products extracted from %s: %s", url, len(all_products))
        return all_products

    def _save_products(self, products: list[dict[str, Any]], category: Any) -> None:
        self.logger.info("Saving %s products for category: %s", len(products), category.url)
        from product.models import PriceHistory, Product

        today = timezone.now().date()

        # Filter out products missing required fields
        valid = [d for d in products if d.get("url") and d.get("price") and d.get("name")]
        if not valid:
            self.logger.warning("No valid products to save for category: %s", category.name)
            return

        urls = [d["url"] for d in valid]

        # --- 1. Split into create / update in one query ---
        existing_map: dict[str, Any] = {
            p.url: p for p in Product.objects.filter(url__in=urls)
        }

        to_create: list[Any] = []
        to_update: list[Any] = []

        for data in valid:
            if data["url"] in existing_map:
                product = existing_map[data["url"]]
                product.name = data["name"]
                product.slug = slugify(data["name"])
                product.price = data["price"]
                product.description = data.get("description", "")
                product.category = category
                product.site = category.site
                to_update.append(product)
            else:
                to_create.append(
                    Product(
                        url=data["url"],
                        name=data["name"],
                        slug=slugify(data["name"]),
                        price=data["price"],
                        description=data.get("description", ""),
                        category=category,
                        site=category.site,
                    )
                )

        # --- 2. Bulk write products, fall back to row-by-row on failure ---
        if to_update:
            try:
                Product.objects.bulk_update(
                    to_update, ["name", "slug", "price", "description", "category", "site"]
                )
                self.logger.info("Updated %s products for category: %s", len(to_update), category.url)
            except Exception as bulk_exc:
                self.logger.warning(
                    "Bulk update failed for category %s (%s) — falling back to row-by-row",
                    category.url, bulk_exc,
                )
                for product in to_update:
                    try:
                        product.save()
                    except Exception as exc:
                        self.logger.error(
                            "Failed to update product %s | category %s | error: %s",
                            product.url, category.url, exc,
                        )

        if to_create:
            try:
                Product.objects.bulk_create(to_create, ignore_conflicts=True)
                self.logger.info("Created %s products for category: %s", len(to_create), category.url)
            except Exception as bulk_exc:
                self.logger.warning(
                    "Bulk create failed for category %s (%s) — falling back to row-by-row",
                    category.url, bulk_exc,
                )
                for product in to_create:
                    try:
                        product.save()
                    except Exception as exc:
                        self.logger.error(
                            "Failed to create product %s | category %s | error: %s",
                            product.url, category.url, exc,
                        )

        # --- 3. Re-fetch all products to get PKs (needed after bulk_create) ---
        product_map: dict[str, Any] = {
            p.url: p for p in Product.objects.filter(url__in=urls)
        }

        # --- 4. Bulk create price history, fall back to row-by-row on failure ---
        already_recorded_ids: set[int] = set(
            PriceHistory.objects.filter(
                product__in=product_map.values(),
                recorded_at__date=today,
            ).values_list("product_id", flat=True)
        )

        price_histories = [
            PriceHistory(product=product_map[d["url"]], price=d["price"])
            for d in valid
            if d["url"] in product_map and product_map[d["url"]].id not in already_recorded_ids
        ]

        if price_histories:
            try:
                PriceHistory.objects.bulk_create(price_histories)
                self.logger.info(
                    "Recorded %s price history entries for category: %s",
                    len(price_histories), category.url,
                )
            except Exception as bulk_exc:
                self.logger.warning(
                    "Bulk price history create failed for category %s (%s) — falling back to row-by-row",
                    category.url, bulk_exc,
                )
                for ph in price_histories:
                    try:
                        ph.save()
                    except Exception as exc:
                        self.logger.error(
                            "Failed to record price history for product %s | category %s | error: %s",
                            ph.product.url, category.url, exc,
                        )

    async def _scrape_and_save_category(
        self, url: str, category: Any, fetcher: FetcherProtocol
    ) -> list[dict[str, Any]]:
        products = await self.extract_data(url, fetcher)
        if products:
            await sync_to_async(self._save_products)(products, category)
        return products

    async def scrape(self) -> list[list[dict[str, Any]]]:
        categories = await sync_to_async(self.all_categories)()
        if not categories:
            self.logger.warning("No categories configured for %s", self.name)
            return []

        total = len(categories)
        batch_size = self.max_concurrent_categories
        self.logger.info(
            "Scraping %s categories in batches of %s with %ss pause between batches",
            total,
            batch_size,
            self.batch_pause,
        )

        fetcher = await self.create_fetcher()
        try:
            all_results: list = []
            for batch_start in range(0, total, batch_size):
                batch = categories[batch_start: batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                self.logger.info(
                    "Starting batch %s/%s (%s categories)",
                    batch_num,
                    -(-total // batch_size),
                    len(batch),
                )

                tasks = [
                    self._scrape_and_save_category(category.url, category, fetcher)
                    for category in batch
                ]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                all_results.extend(zip(batch, batch_results))

                is_last_batch = batch_start + batch_size >= total
                if not is_last_batch:
                    self.logger.info("Batch %s done. Pausing %ss...", batch_num, self.batch_pause)
                    await asyncio.sleep(self.batch_pause)

            normalized: list[list[dict[str, Any]]] = []
            for category, result in all_results:
                if isinstance(result, Exception):
                    self.logger.error("Category scrape failed for %s: %s", category.url, result)
                    normalized.append([])
                else:
                    normalized.append(result)

            return normalized
        finally:
            await self.close_fetcher(fetcher)

