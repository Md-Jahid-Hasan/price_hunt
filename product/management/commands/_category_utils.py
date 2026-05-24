from django.utils.text import slugify

from product.models import Category, Site


def save_categories(site_name: str, categories: list[dict]) -> tuple[int, int]:
    """
    Upsert categories for a site, supporting optional parent-child hierarchy.

    Each dict must have:
        name       str
        url        str
    Optional keys:
        slug       str  – full path slug (e.g. "laptop-all-laptop-lenovo");
                         defaults to slugify(name) if omitted
        parent_url str  – URL of the parent category; must appear earlier in
                         the list so it is already resolved when this item is
                         processed

    Categories must be ordered parents-before-children.
    Returns (created_count, updated_count).
    """
    site = Site.objects.filter(name=site_name).first()
    if not site:
        raise ValueError(f"Site '{site_name}' not found in the database.")

    urls = [c["url"] for c in categories]
    # Seed the map with every category that already exists in the DB.
    # Newly created categories are added to this map immediately so that
    # child categories can resolve their parent FK in the same run.
    url_to_cat: dict[str, Category] = {
        c.url: c for c in Category.objects.filter(url__in=urls)
    }

    created = 0
    to_update: list[Category] = []

    for data in categories:
        slug = data.get("slug") or slugify(data["name"])
        if data.get("parent_url"):
            parent = url_to_cat.get(data["parent_url"])
        else:
            parent = Category.objects.filter(site=site, slug=data.get("parent_slug")).first()

        if data["url"] in url_to_cat:
            cat = url_to_cat[data["url"]]
            cat.name = data["name"]
            cat.slug = slug
            cat.site = site
            cat.parent = parent
            to_update.append(cat)
        else:
            cat = Category.objects.create(
                name=data["name"],
                slug=slug,
                url=data["url"],
                site=site,
                parent=parent,
            )
            if data['url']:
                url_to_cat[data["url"]] = cat
            created += 1

    if to_update:
        Category.objects.bulk_update(to_update, ["name", "slug", "site", "parent"])

    return created, len(to_update)