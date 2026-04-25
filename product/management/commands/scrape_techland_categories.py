import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from product.models import Site

from ._category_utils import save_categories


class Command(BaseCommand):
    help = "Scrape second-level product categories from Techland and save to the database."

    def handle(self, *args, **options):
        site = Site.objects.filter(name="Tech Land").first()
        if not site:
            self.stderr.write("Site 'Tech Land' not found in the database.")
            return

        self.stdout.write(f"Fetching Techland navigation from {site.url} ...")

        try:
            response = requests.get("https://www.techlandbd.com/ajax/header-navigation", timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(f"Failed to fetch {site.url}: {exc}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        # nav = soup.find(id="header-navigation-container")
        # if not nav:
        #     self.stderr.write("Could not find #header-navigation-container — Techland may have changed their HTML.")
        #     return

        main_ul = soup.find("ul")
        if not main_ul:
            self.stderr.write("No <ul> found inside #header-navigation-container.")
            return

        categories: list[dict] = []

        for top_li in main_ul.find_all("li", recursive=False):
            submenu = top_li.find("ul", recursive=False)
            if not submenu:
                continue

            # Direct li children of the submenu are the second-level categories
            for sub_li in submenu.find_all("li", recursive=False):
                a = sub_li.find("a", recursive=False)
                if not a:
                    continue
                href: str = a.get("href", "")
                name: str = a.get_text(strip=True)
                if href.startswith(site.url) and name:
                    categories.append({"name": name, "url": href})

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")
        created, updated = save_categories("Tech Land", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))