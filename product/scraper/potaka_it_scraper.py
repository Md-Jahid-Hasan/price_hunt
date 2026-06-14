import asyncio
import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from product.scraper.base_paginated_scraper import BasePaginatedScraper
from scraper.common import HttpClientFetcher

from product.models import Category

logger = logging.getLogger("PotakaITScraper")


class PotakaITScraper(BasePaginatedScraper):
    def __init__(self):
        super().__init__(name="Potaka IT", logger=logger, max_retries=3, retry_delay=2)
        self._session: aiohttp.ClientSession | None = None
        self._price_enum = ["Pre Order", "Out Of Stock", "Up Coming"]

    def all_categories(self):
        return list(Category.objects.filter(site__name=self.name, subcategories__isnull=True).select_related("site"))
        # return list(Category.objects.filter(url="https://www.startech.com.bd/component/processor").select_related("site"))

    async def create_fetcher(self) -> HttpClientFetcher:
        self._session = aiohttp.ClientSession()
        return HttpClientFetcher(self._session, logger)

    async def close_fetcher(self, fetcher: HttpClientFetcher) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("HTTP session closed")

    def parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            info_p = soup.find("p", string=lambda s: s and "Showing" in s and "Pages" in s)
            if not info_p:
                return 1

            text = info_p.get_text(strip=True)
            match = re.search(r"\((\d+)\s+Pages?\)", text)
            if match:
                return int(match.group(1))
            return 1
        except Exception as exc:
            logger.error("Error parsing total pages: %s", exc)
            return 1

    def get_next_page_url(self, soup:BeautifulSoup) -> str:
        try:
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return ""
            next_page_link = pagination.find("a", string="NEXT")
            if next_page_link:
                return next_page_link.get("href", "")
            return ""
        except Exception as exc:
            logger.error("Error finding next page URL: %s", exc)
            return ""

    def parse_products(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        try:
            container = soup.find("div", id="content")
            if not container:
                logger.warning("No product container found on page")
                return products

            cards = container.find_all("div", class_="product-item extra")
            logger.info("Found %s product cards on page", len(cards))

            for card in cards:
                try:
                    name_tag = card.find("h4", class_="title")
                    anchor = name_tag.find("a") if name_tag else None
                    if not anchor:
                        continue

                    name = name_tag.get_text(strip=True) if name_tag else ""
                    product_url = anchor.get("href", "")

                    price_tag = card.find("div", class_="price-info")
                    price = ""
                    if price_tag:
                        price_tag = price_tag.find("p", class_="price")
                        price_text = price_tag.get_text(strip=True) if price_tag else ""

                        if price_text in self._price_enum:
                            price = 0
                        else:
                            price = "".join(ch for ch in price_text if ch.isdigit())

                    button_tag = card.find("div", class_="cart-button-wrap")
                    is_out_of_stock = (button_tag and button_tag.get_text(strip=True) in
                                       ["Out Of Stock", "Up Coming", "Pre-Order"])

                    products.append(
                        {
                            "name": name,
                            "url": product_url,
                            "price": price,
                            "description": "",
                            "is_available": not is_out_of_stock,
                        }
                    )
                except Exception as exc:
                    logger.error("Skipping card due to extraction error: %s", exc)
                    continue

        except Exception as exc:
            logger.error("Error parsing product list: %s", exc)

        return products



if __name__ == "__main__":
    asyncio.run(PotakaITScraper().scrape())
