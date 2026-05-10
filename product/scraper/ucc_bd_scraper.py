import asyncio
import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from product.models import Category
from product.scraper.base_paginated_scraper import BasePaginatedScraper
from scraper.common import HttpClientFetcher

logger = logging.getLogger("UccBdScraper")


class UccBdScraper(BasePaginatedScraper):
    def __init__(self):
        super().__init__(name="UCC BD", logger=logger, max_retries=3, retry_delay=2)
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

    def get_next_page_url(self, soup: BeautifulSoup) -> str:
        try:
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return ""
            next_link = pagination.find("a", class_="next")
            if next_link:
                return next_link.get("href", "")
            return ""
        except Exception as exc:
            logger.error("Error finding next page URL: %s", exc)
            return ""

    def parse_products(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        try:
            container = soup.find("div", class_="main-products")
            if not container:
                logger.warning("No product container (.main-products) found on page")
                return products

            cards = container.find_all("div", class_="product-layout")
            logger.info("Found %s product cards on page", len(cards))

            for card in cards:
                try:
                    name_div = card.find("div", class_="name")
                    anchor = name_div.find("a") if name_div else None
                    if not anchor:
                        continue

                    name = anchor.get_text(strip=True)
                    product_url = anchor.get("href", "")
                    if not name or not product_url:
                        continue

                    price = ""
                    price_div = card.find("div", class_="price")
                    if price_div:
                        price_span = price_div.find("span", class_="price-new") or price_div.find("span", class_="price-normal")
                        if price_span:
                            price = "".join(ch for ch in price_span.get_text(strip=True) if ch.isdigit())

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
    asyncio.run(UccBdScraper().scrape())