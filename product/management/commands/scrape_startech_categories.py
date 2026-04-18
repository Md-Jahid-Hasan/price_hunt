import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from product.models import Site

from ._category_utils import save_categories


class Command(BaseCommand):
    help = "Scrape all product categories from Star Tech and save to the database."

    def handle(self, *args, **options):
        site = Site.objects.filter(name="Star Tech").first()
        if not site:
            self.stderr.write("Site 'Star Tech' not found in the database.")
            return

        self.stdout.write(f"Fetching Star Tech navigation from {site.url} ...")

        try:
            response = requests.get(site.url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(f"Failed to fetch {site.url}: {exc}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        nav = soup.find("nav", id="main-nav")
        if not nav:
            self.stderr.write("Could not find #main-nav — Star Tech may have changed their HTML.")
            return

        # Leaf items (no has-child) are actual product categories
        # Parent items (has-child) are menu groups — skip them
        categories: list[dict] = []

        for li in nav.find_all("li", class_="nav-item"):
            if "has-child" in li.get("class", []):
                continue
            a = li.find("a", class_="nav-link")
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

        created, updated = save_categories("Star Tech", categories)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {created} created, {updated} updated."
            )
        )