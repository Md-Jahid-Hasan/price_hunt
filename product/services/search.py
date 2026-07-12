from django.db.models import F
from pgvector.django import CosineDistance
from .embedding import get_embedding
from product.models import Product, ProductEmbedding


def semantic_search(query: str, top_k: int = 5, max_distance: float | None = None):
    """
    Embeds the query text and returns the top_k most similar products
    by cosine distance (lower = more similar, range 0-2).

    max_distance: optional cutoff to filter out weak matches (e.g. 0.5).
    Tune this empirically against your actual product data.
    """
    query_vector = get_embedding(query)

    qs = (
        ProductEmbedding.objects
        .select_related("product", "product__category", "product__site")
        .annotate(distance=CosineDistance("vector", query_vector))
        .order_by("distance")
    )

    if max_distance is not None:
        qs = qs.filter(distance__lte=max_distance)

    results = qs[:top_k]

    return [
        {
            "product": pe.product,
            "distance": pe.distance,
        }
        for pe in results
    ]