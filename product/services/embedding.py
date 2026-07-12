import requests
from django.conf import settings


class OllamaEmbeddingError(Exception):
    pass


def build_product_text(product) -> str:
    """
    Build a single text blob representing a product for embedding.
    Keep this deterministic — if you change the format, re-embed everything.
    """
    parts = [
        product.name,
        product.category.name if product.category else "",
        product.site.name if product.site else "",
        product.description or "",
    ]
    return " | ".join(p for p in parts if p)


def get_embedding(text: str) -> list[float]:
    """
    Calls Ollama's embedding endpoint. Raises OllamaEmbeddingError on failure
    so callers (management command / celery task) can retry or log clearly.
    """
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": settings.EMBEDDING_MODEL, "prompt": text},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaEmbeddingError(f"Ollama request failed: {exc}") from exc

    data = response.json()
    embedding = data.get("embedding")
    if not embedding:
        raise OllamaEmbeddingError(f"No embedding returned: {data}")
    return embedding


def embed_product(product) -> None:
    """
    Generates/updates the embedding for a single product.
    Safe to call repeatedly (idempotent upsert).
    """
    from product.models import ProductEmbedding  # local import avoids circulars

    text = build_product_text(product)
    vector = get_embedding(text)

    ProductEmbedding.objects.update_or_create(
        product=product,
        defaults={"vector": vector, "source_text": text},
    )