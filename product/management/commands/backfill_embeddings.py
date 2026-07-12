# product/management/commands/backfill_embeddings.py
from django.core.management.base import BaseCommand
from product.models import Product
from product.services.embedding import embed_product, OllamaEmbeddingError


class Command(BaseCommand):
    help = "Generate embeddings for all products missing one (or all, with --force)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Re-embed all products, not just missing ones"
        )

    def handle(self, *args, **options):
        qs = Product.objects.select_related("category", "site")
        if not options["force"]:
            qs = qs.filter(embedding__isnull=True)

        total = qs.count()
        self.stdout.write(f"Embedding {total} products...")

        success, failed = 0, 0
        for i, product in enumerate(qs.iterator(), start=1):
            try:
                embed_product(product)
                success += 1
            except OllamaEmbeddingError as exc:
                failed += 1
                self.stderr.write(f"Failed on product {product.id}: {exc}")

            if i % 50 == 0:
                self.stdout.write(f"  ...{i}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Done. {success} succeeded, {failed} failed."))