from django.utils.text import slugify

from product.models import Category, Site


def save_categories(site_name: str, categories: list[dict]) -> tuple[int, int]:
    """
    Bulk upsert categories for a site.
    Returns (created_count, updated_count).
    """
    site = Site.objects.filter(name=site_name).first()
    if not site:
        raise ValueError(f"Site '{site_name}' not found in the database.")

    urls = [c["url"] for c in categories]
    existing_map = {c.url: c for c in Category.objects.filter(url__in=urls)}

    to_create = []
    to_update = []

    for data in categories:
        slug = slugify(data["name"])
        if data["url"] in existing_map:
            cat = existing_map[data["url"]]
            cat.name = data["name"]
            cat.slug = slug
            cat.site = site
            to_update.append(cat)
        else:
            to_create.append(
                Category(
                    name=data["name"],
                    slug=slug,
                    url=data["url"],
                    site=site,
                )
            )

    if to_update:
        Category.objects.bulk_update(to_update, ["name", "slug", "site"])

    if to_create:
        Category.objects.bulk_create(to_create, ignore_conflicts=True)

    return len(to_create), len(to_update)