import asyncio
import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from product.models import Category
from product.scraper.base_paginated_scraper import BasePaginatedScraper
from scraper.common import HttpClientFetcher

logger = logging.getLogger("TechlandScraper")


class TechlandScraper(BasePaginatedScraper):
    def __init__(self):
        super().__init__(name="Tech Land", logger=logger, max_retries=3, retry_delay=2)
        self._session: aiohttp.ClientSession | None = None

    def all_categories(self):
        return list(Category.objects.filter(site__name=self.name, subcategories__isnull=True).select_related("site"))

    async def create_fetcher(self) -> HttpClientFetcher:
        self._session = aiohttp.ClientSession()
        return HttpClientFetcher(self._session, logger)

    async def close_fetcher(self, fetcher: HttpClientFetcher) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("HTTP session closed")

    def parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            max_page = 1
            for a in soup.find_all("a", href=True):
                m = re.search(r"[?&]page=(\d+)", a["href"])
                if m:
                    max_page = max(max_page, int(m.group(1)))
            return max_page
        except Exception as exc:
            logger.error("Error parsing total pages: %s", exc)
            return 1

    def get_next_page_url(self, soup: BeautifulSoup) -> str:
        try:
            # Collect all page links
            current_page = soup.find('link', rel='canonical').get("href")
            pagination_container = soup.find("nav", attrs={'aria-label': 'Pagination'})
            current_page_number = pagination_container.find("button", attrs={'aria-current': '"page"'}).get_text(strip=True)
            if_last_page = pagination_container.find(
                "span",
                class_="sr-only",
                string=lambda s: s and "Next page (disabled)" in s,
            )
            if if_last_page:
                logging.warning("Reached last page: %s", current_page_number)
                return ""
            return f"{current_page}?page={int(current_page_number) + 1}"

        except Exception as exc:
            logger.error("Error finding next page URL: %s", exc)
            return ""

    def parse_products(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        try:
            container = soup.find("div", id="product-container")
            if not container:
                logger.warning("No product container (#product-container) found on page")
                return products

            cards = container.find_all("article", class_="products-list__item")
            logger.info("Found %s product cards on page", len(cards))

            for card in cards:
                try:
                    h4 = card.find("h4")
                    anchor = h4.find("a") if h4 else None
                    if not anchor:
                        continue

                    name = anchor.get_text(strip=True)
                    product_url = anchor.get("href", "")
                    if not name or not product_url:
                        continue

                    # Current price: first span containing ৳ without line-through
                    price = 0
                    content_section = card.find("div", class_="product-content-section")
                    if content_section:
                        for span in content_section.find_all("span"):
                            span_text = span.get_text(strip=True)
                            if "৳" in span_text and "line-through" not in " ".join(span.get("class", [])):
                                price = "".join(ch for ch in span_text if ch.isdigit())
                                break

                    products.append(
                        {
                            "name": name,
                            "url": product_url,
                            "price": price,
                            "description": "",
                        }
                    )
                except Exception as exc:
                    logger.error("Skipping card due to extraction error: %s", exc)
                    continue

        except Exception as exc:
            logger.error("Error parsing product list: %s", exc)

        return products


if __name__ == "__main__":
    asyncio.run(TechlandScraper().scrape())