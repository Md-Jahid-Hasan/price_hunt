import asyncio
import logging

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify

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
        with open("ucc_bd_product.html", "r", encoding="utf-8") as f:
            html = f.read()
        # html = _fetch_via_playwright(site.url)
        if not html:
            self.stderr.write("Failed to fetch Ryans homepage.")
            return

        soup = BeautifulSoup(html, "html.parser")
        nav = soup.find("div", id="navbar_main")
        if not nav:
            self.stderr.write("Could not find #navbar_main — Ryans may have changed their HTML.")
            return

        top_ul = nav.find("ul", class_="navbar-nav")
        if not top_ul:
            self.stderr.write("Could not find .navbar-nav inside #navbar_main.")
            return

        categories: list[dict] = []

        for l1_li in top_ul.find_all("li", class_="nav-item", recursive=False):
            btn = l1_li.find("button", class_="nav-link")
            if not btn:
                continue
            l1_name: str = btn.get_text(strip=True)
            if not l1_name:
                continue
            l1_slug = slugify(l1_name)

            dropdown = l1_li.find("div", class_="dropdown-menu")
            if not dropdown:
                continue

            # L1 nav group — no URL, used only as a parent anchor
            categories.append({
                "name": l1_name,
                "url": None,
                "slug": l1_slug,
                "parent_url": None,
            })

            # Each column is a <ul class="list-unstyled">
            for col_ul in dropdown.find_all("ul", class_="list-unstyled"):
                for l2_li in col_ul.find_all("li", recursive=False):
                    l2_a = l2_li.find("a", recursive=False)
                    if not l2_a:
                        continue

                    l2_href: str = l2_a.get("href", "")
                    l2_name: str = l2_a.get_text(strip=True)

                    # Skip section dividers (href="#") and non-category links
                    if not l2_href or l2_href == "#" or "/category/" not in l2_href:
                        continue

                    l2_slug = f"{l1_slug}-{slugify(l2_name)}"
                    categories.append({
                        "name": l2_name,
                        "url": l2_href,
                        "slug": l2_slug,
                        "parent_slug": l1_slug,  # L1 has no URL — reference by slug
                    })

                    # L3: sub-items of dropend li
                    sub_ul = l2_li.find("ul", recursive=False)
                    if not sub_ul:
                        continue

                    for l3_li in sub_ul.find_all("li", recursive=False):
                        l3_a = l3_li.find("a", recursive=False)
                        if not l3_a:
                            continue

                        l3_href: str = l3_a.get("href", "")
                        l3_name: str = l3_a.get_text(strip=True)

                        # Skip if same URL as parent (Ryans "All Brands" pattern)
                        if not l3_href or l3_href == l2_href or "/category/" not in l3_href:
                            continue

                        l3_slug = f"{l2_slug}-{slugify(l3_name)}"
                        categories.append({
                            "name": l3_name,
                            "url": l3_href,
                            "slug": l3_slug,
                            "parent_url": l2_href,
                        })

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")
        created, updated = save_categories("Ryans", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))