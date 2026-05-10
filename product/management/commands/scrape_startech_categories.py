import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from product.models import Site

from ._category_utils import save_categories


class Command(BaseCommand):
    help = "Scrape all product categories from Star Tech (L1 → L2 → L3) and save to the database."

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

        categories: list[dict] = []

        for l1_li in nav.select("ul.navbar-nav > li.nav-item"):
            l1_a = l1_li.find("a", class_="nav-link", recursive=False)
            if not l1_a:
                continue
            l1_href: str = l1_a.get("href", "")
            l1_name: str = l1_a.get_text(strip=True)
            if not l1_href.startswith(site.url) or not l1_name:
                continue

            l1_slug = slugify(l1_name)
            categories.append({
                "name": l1_name,
                "url": l1_href,
                "parent_url": None,
                "slug": l1_slug,
            })

            drop_1 = l1_li.find("ul", class_="drop-menu-1", recursive=False)
            if not drop_1:
                continue

            for l2_li in drop_1.find_all("li", class_="nav-item", recursive=False):
                l2_a = l2_li.find("a", class_="nav-link", recursive=False)
                if not l2_a:
                    continue
                l2_href: str = l2_a.get("href", "")
                l2_name: str = l2_a.get_text(strip=True)
                if not l2_href.startswith(site.url) or not l2_name:
                    continue

                l2_slug = f"{l1_slug}-{slugify(l2_name)}"
                categories.append({
                    "name": l2_name,
                    "url": l2_href,
                    "parent_url": l1_href,
                    "slug": l2_slug,
                })

                drop_2 = l2_li.find("ul", class_="drop-menu-2", recursive=False)
                if not drop_2:
                    continue

                for l3_li in drop_2.find_all("li", class_="nav-item", recursive=False):
                    l3_a = l3_li.find("a", class_="nav-link", recursive=False)
                    if not l3_a:
                        continue
                    l3_href: str = l3_a.get("href", "")
                    l3_name: str = l3_a.get_text(strip=True)
                    if not l3_href.startswith(site.url) or not l3_name:
                        continue

                    l3_slug = f"{l2_slug}-{slugify(l3_name)}"
                    categories.append({
                        "name": l3_name,
                        "url": l3_href,
                        "parent_url": l2_href,
                        "slug": l3_slug,
                    })

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")
        created, updated = save_categories("Star Tech", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))