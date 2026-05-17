from django.core.management.base import BaseCommand

from product.models import Category, Product


class Command(BaseCommand):
    """
    Custom Django management command to populate the Category.keywords field. Run this rarely to populate keywords
     based on product slugs, which improves search relevance. It processes categories in batches for efficiency.
    """
    help = "Populate Category.keywords from the slugs of products in each category."

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Categories per bulk_update call (default: 200)',
        )

    def handle(self, *args, **options):
        STOPWORDS = {
            # articles / conjunctions / prepositions
            "the", "an", "and", "or", "of", "in", "on", "at", "to", "for",
            "by", "as", "up", "off", "out", "over", "under", "with", "from",
            "through", "without", "after", "above", "between", "beyond",
            "near", "like", "around", "per", "so", "no", "not", "but",
            # pronouns / aux verbs
            "he", "her", "my", "we", "us", "am", "is", "it", "be",
            # filler
            "get", "set", "back", "more", "every", "all", "only", "also",
            "just", "last", "next", "good", "best", "easy", "vs", "eg",
            # number words
            "one", "two", "three", "four", "five", "six", "seven", "eight",
            "nine", "ten", "first", "second", "third",
            # noise 2-letter fragments
            "al", "ba", "ca", "da", "di", "du", "ea", "el", "em", "en",
            "he", "her", "my", "we", "us", "am", "is", "it", "be",
            # filler
            "get", "set", "back", "more", "every", "all", "only", "also",
            "just", "last", "next", "good", "best", "easy", "vs", "eg",
            # number words
            "one", "two", "three", "four", "five", "six", "seven", "eight",
            "nine", "ten", "first", "second", "third",
            # noise 2-letter fragments
            "al", "ba", "ca", "da", "di", "du", "ea", "el", "em", "en",
            "ga", "ja", "ki", "la", "le", "li", "ma", "na", "ni", "pa",
            "ra", "ri", "sa", "si", "ta", "va", "vi", "wi", "ya", "za",
        }

        batch_size = options['batch_size']

        categories = list(Category.objects.filter(subcategories__isnull=True, is_active=True))
        self.stdout.write(f"Found {len(categories)} categories. Building keyword index ...")

        # One query: all (category_id, slug) pairs — no N+1
        rows = (
            Product.objects
            .exclude(category__isnull=True)
            .exclude(slug='')
            .values_list('category_id', 'slug')
            .iterator(chunk_size=2000)
        )

        # Build category_id → set of words
        cat_words: dict[int, set[str]] = {}
        for category_id, slug in rows:
            words = cat_words.setdefault(category_id, set())
            for token in slug.split('-'):
                token = token.strip().lower()
                if len(token) >= 2 and token not in STOPWORDS and not token.isdigit():
                    words.add(token)

        # Write sorted, space-joined keywords back to each category
        to_update = []
        for cat in categories:
            cat.keywords = ' '.join(sorted(cat_words.get(cat.id, set())))
            to_update.append(cat)

        # Bulk update in batches
        total = 0
        for i in range(0, len(to_update), batch_size):
            batch = to_update[i : i + batch_size]
            Category.objects.bulk_update(batch, ['keywords'])
            total += len(batch)

        self.stdout.write(self.style.SUCCESS(f"Done — {total} categories updated."))