import asyncio
import logging

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from product.models import Site
from scraper.common import PlaywrightClientFetcher

from ._category_utils import save_categories

logger = logging.getLogger("RyansScraper")


def _fetch_via_playwright(url: str) -> str:
    async def _run():
        fetcher = PlaywrightClientFetcher(logger)
        await fetcher.start()
        try:
            return await fetcher.fetch(url)
        finally:
            await fetcher.stop()

    return asyncio.run(_run())


class Command(BaseCommand):
    help = "Scrape all product categories from Ryans and save to the database."

    def handle(self, *args, **options):
        site = Site.objects.filter(name="Ryans").first()
        if not site:
            self.stderr.write("Site 'Ryans' not found in the database.")
            return

        self.stdout.write(f"Fetching Ryans navigation from {site.url} ...")
        html = _fetch_via_playwright(site.url)
        if not html:
            self.stderr.write("Failed to fetch Ryans homepage.")
            return

        soup = BeautifulSoup(html, "html.parser")
        nav = soup.find("nav", id="navbar_main")
        if not nav:
            self.stderr.write("Could not find #navbar_main — Ryans may have changed their HTML.")
            return

        seen_urls: set[str] = set()
        categories: list[dict] = []

        for a in nav.find_all("a", href=True):
            href: str = a["href"]
            name: str = a.get_text(strip=True)
            if "/category/" in href and href not in seen_urls and name:
                seen_urls.add(href)
                categories.append({"name": name, "url": href})

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")
        created, updated = save_categories("Ryans", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))