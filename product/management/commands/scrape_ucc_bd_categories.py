import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from product.models import Site

from ._category_utils import save_categories


class Command(BaseCommand):
    help = "Scrape second-level product categories from UCC BD and save to the database."

    def handle(self, *args, **options):
        site = Site.objects.filter(name="UCC BD").first()
        if not site:
            self.stderr.write("Site 'UCC BD' not found in the database.")
            return

        self.stdout.write(f"Fetching UCC BD navigation from {site.url} ...")

        try:
            response = requests.get(site.url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(f"Failed to fetch {site.url}: {exc}")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        # The nav is inside li.main-menu-item > div > div.flyout-menu > ul.j-menu
        nav_li = soup.find("li", class_="main-menu-item")
        if not nav_li:
            self.stderr.write("Could not find li.main-menu-item — UCC BD may have changed their HTML.")
            return

        flyout_menu = nav_li.find("div", class_="flyout-menu")
        if not flyout_menu:
            self.stderr.write("Could not find div.flyout-menu inside the main menu item.")
            return

        top_ul = flyout_menu.find("ul", class_="j-menu")
        if not top_ul:
            self.stderr.write("Could not find ul.j-menu inside the flyout menu.")
            return

        categories: list[dict] = []

        for flyout_li in top_ul.find_all("li", class_="flyout-menu-item", recursive=False):
            # Check for a direct L2 submenu (div.j-dropdown > ul.j-menu)
            inner_div = flyout_li.find("div", class_="j-dropdown", recursive=False)

            if inner_div:
                inner_ul = inner_div.find("ul", class_="j-menu")
                if not inner_ul:
                    continue
                # Each direct li child is an L2 category — we save it regardless
                # of whether it has its own L3 sub-menu (we don't go deeper)
                for sub_li in inner_ul.find_all("li", recursive=False):
                    a = sub_li.find("a", recursive=False)
                    if not a:
                        continue
                    href: str = a.get("href", "")
                    name_span = a.find("span", class_="links-text")
                    name: str = name_span.get_text(strip=True) if name_span else a.get_text(strip=True)
                    if href.startswith(site.url) and name:
                        categories.append({"name": name, "url": href})
            else:
                # No L2 submenu — save this L1 item directly (e.g. Gaming Console)
                a = flyout_li.find("a", recursive=False)
                if not a:
                    continue
                href = a.get("href", "")
                name_span = a.find("span", class_="links-text")
                name = name_span.get_text(strip=True) if name_span else a.get_text(strip=True)
                if href and href != "#" and href.startswith(site.url) and name:
                    categories.append({"name": name, "url": href})

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")

        created, updated = save_categories("UCC BD", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))