import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from product.models import Site

from ._category_utils import save_categories


class Command(BaseCommand):
    help = "Scrape all product categories from Tech Land (L1 → L2 → L3 → L4) and save to the database."

    def handle(self, *args, **options):
        site = Site.objects.filter(name="Tech Land").first()
        if not site:
            self.stderr.write("Site 'Tech Land' not found in the database.")
            return

        self.stdout.write("Fetching Tech Land navigation ...")

        try:
            response = requests.get(
                "https://www.techlandbd.com/ajax/header-navigation",
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self.stderr.write(f"Failed to fetch navigation: {exc}")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        main_ul = soup.find("ul")
        if not main_ul:
            self.stderr.write("Could not find the top-level <ul> inside #header-navigation-container.")
            return

        categories: list[dict] = []

        for l1_li in main_ul.find_all("li", class_="menu-item", recursive=False):
            l1_a = l1_li.find("a", recursive=False)
            if not l1_a:
                continue
            l1_href: str = l1_a.get("href", "")
            l1_name: str = l1_a.get_text(strip=True)
            if not l1_href.startswith(site.url) or not l1_name:
                continue

            l1_slug = slugify(l1_name)
            categories.append({"name": l1_name, "url": l1_href, "parent_url": None, "slug": l1_slug})

            l2_ul = l1_li.find("ul", class_="submenu", recursive=False)
            if not l2_ul:
                continue

            for l2_li in l2_ul.find_all("li", class_="menu-item", recursive=False):
                l2_a = l2_li.find("a", recursive=False)
                if not l2_a:
                    continue
                l2_href: str = l2_a.get("href", "")
                l2_span = l2_a.find("span", class_="flex-grow")
                l2_name: str = l2_span.get_text(strip=True) if l2_span else l2_a.get_text(strip=True)
                if not l2_href.startswith(site.url) or not l2_name:
                    continue

                l2_slug = f"{l1_slug}-{slugify(l2_name)}"
                categories.append({"name": l2_name, "url": l2_href, "parent_url": l1_href, "slug": l2_slug})

                l3_ul = l2_li.find("ul", class_="submenu", recursive=False)
                if not l3_ul:
                    continue

                for l3_li in l3_ul.find_all("li", class_="menu-item", recursive=False):
                    l3_a = l3_li.find("a", recursive=False)
                    if not l3_a:
                        continue
                    l3_href: str = l3_a.get("href", "")
                    l3_span = l3_a.find("span", class_="flex-grow")
                    l3_name: str = l3_span.get_text(strip=True) if l3_span else l3_a.get_text(strip=True)
                    if not l3_href.startswith(site.url) or not l3_name:
                        continue

                    l3_slug = f"{l2_slug}-{slugify(l3_name)}"
                    categories.append({"name": l3_name, "url": l3_href, "parent_url": l2_href, "slug": l3_slug})

                    l4_ul = l3_li.find("ul", class_="submenu", recursive=False)
                    if not l4_ul:
                        continue

                    for l4_li in l4_ul.find_all("li", class_="menu-item", recursive=False):
                        l4_a = l4_li.find("a", recursive=False)
                        if not l4_a:
                            continue
                        l4_href: str = l4_a.get("href", "")
                        l4_span = l4_a.find("span", class_="flex-grow")
                        l4_name: str = l4_span.get_text(strip=True) if l4_span else l4_a.get_text(strip=True)
                        if not l4_href.startswith(site.url) or not l4_name:
                            continue

                        l4_slug = f"{l3_slug}-{slugify(l4_name)}"
                        categories.append({"name": l4_name, "url": l4_href, "parent_url": l3_href, "slug": l4_slug})

        if not categories:
            self.stderr.write("No categories found — check the HTML structure.")
            return

        self.stdout.write(f"Found {len(categories)} categories. Saving...")
        created, updated = save_categories("Tech Land", categories)
        self.stdout.write(self.style.SUCCESS(f"Done — {created} created, {updated} updated."))