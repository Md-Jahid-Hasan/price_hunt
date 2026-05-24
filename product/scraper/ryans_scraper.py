import asyncio
import logging
import re
from typing import Any
import random

import time
from bs4 import BeautifulSoup

from product.scraper.base_paginated_scraper import BasePaginatedScraper
from scraper.common import PlaywrightClientFetcher

from product.models import Category

logger = logging.getLogger("RyansScraper")


class RyansScraper(BasePaginatedScraper):
    def __init__(self):
        super().__init__(
            name="Ryans",
            logger=logger,
            max_retries=3,
            retry_delay=2,
            max_concurrent_categories=1,
            inter_page_delay=(15, 30),
            inter_category_delay=(60, 120),
            fetcher_restart_interval=10,
        )

    def all_categories(self):
        return list(Category.objects.filter(site__name=self.name, subcategories__isnull=True, is_active=True).select_related("site"))
        # return list(Category.objects.filter(url="https://www.ryans.com/category/desktop-component-processor").select_related("site"))

    async def create_fetcher(self) -> PlaywrightClientFetcher:
        fetcher = PlaywrightClientFetcher(logger)
        await fetcher.start()
        return fetcher

    async def close_fetcher(self, fetcher: PlaywrightClientFetcher) -> None:
        await fetcher.stop()
        logger.info("Playwright browser stopped")

    def parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return 1

            max_page = 1
            for link in pagination.find_all("a", class_="page-link"):
                text = link.get_text(strip=True)
                if text.isdigit():
                    max_page = max(max_page, int(text))

            return max_page
        except Exception as exc:
            logger.error("Error parsing total pages: %s", exc)
            return 1

    def get_next_page_url(self, soup:BeautifulSoup) -> str:
        try:
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                return ""
            next_page_link = pagination.find("a", class_="page-link", attrs={"rel": "next"})
            if next_page_link:
                return next_page_link.get("href", "")
            return ""
        except Exception as exc:
            logger.error("Error finding next page URL: %s", exc)
            return ""

    def parse_products(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        delay = random.uniform(*self.inter_page_delay)
        self.logger.info("Waiting %.1fs before next page...", delay)
        time.sleep(delay)
        products: list[dict[str, Any]] = []
        try:
            container = soup.find("div", class_="product-category-card")
            if not container:
                logger.warning("No product container found on page")
                return products

            cards = container.find_all("div", class_="category-single-product")
            logger.info("Found %s product cards on page", len(cards))

            for card in cards:
                try:
                    name_tag = card.find("h4", class_="product-name")
                    anchor = name_tag.find("a") if name_tag else None
                    if not anchor:
                        continue

                    name = anchor.get("title") or anchor.get_text(strip=True)
                    name = name.split("<br>")[0] if name.split("<br>") else name
                    product_url = anchor.get("href", "")

                    price_tag = card.find("a", class_="cat-sp-text")
                    price = price_tag.get_text(strip=True) if price_tag else ""
                    price = int(re.sub(r'[^\d]', '', price)) # if price is 0 then out of stock

                    brand = soup.find("meta", attrs={"property": "product:brand"})
                    brand = brand.get("content", "") if brand else ""

                    description = ""
                    desc_div = card.find("div", class_="short-desc-attr")
                    if desc_div:
                        ul = desc_div.find("ul")
                        if ul:
                            ul.attrs.pop("class", None)
                            for tag in ul.find_all(True):
                                tag.attrs.pop("class", None)
                            for li in ul.find_all("li"):
                                li.string = li.get_text(strip=True)
                            description = str(ul)

                    products.append(
                        {
                            "name": name,
                            "url": product_url,
                            "price": price,
                            "description": description,
                            "brand": brand,
                        }
                    )
                except Exception as exc:
                    logger.error("Skipping card due to extraction error: %s", exc)
                    continue

        except Exception as exc:
            logger.error("Error parsing product list: %s", exc)

        return products



if __name__ == "__main__":
    asyncio.run(RyansScraper().scrape())
