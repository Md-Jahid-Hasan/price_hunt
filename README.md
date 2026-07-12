# Price Hunt — RAG-based Product Search & Price Comparison

A Django backend that scrapes product/price data across multiple sites and exposes a
natural-language search API powered by a local LLM (via Ollama) combined with
pgvector semantic search and structured price analytics.

**Stack:** Django + DRF, PostgreSQL + pgvector, Celery + Redis, Ollama (Llama 3.1 + nomic-embed-text)

---

## 1. Prerequisites

- Docker & Docker Compose
- [Ollama](https://ollama.com) installed **natively on the host** (not containerized —
  this project assumes Ollama runs on the host machine so it can use hardware
  acceleration, e.g. Metal on Apple Silicon)
- Python 3.13 (only needed if running anything outside Docker)
- A Postgres dump/backup file, if restoring existing product data

---

## 2. Clone & configure environment

```bash
git clone <your-repo-url> price_hunt
cd price_hunt
cp .env.example .env
```

Edit `.env`:

```env
# Database
DATABASE_NAME=price_data
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=postgres
DATABASE_HOST=db
DATABASE_PORT=5432

# Redis / Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Ollama (native on host — reachable from containers via host.docker.internal)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

DJANGO_ALLOWED_HOSTS=*
```

> `host.docker.internal` works out of the box on Docker Desktop (Mac/Windows). On Linux
> Docker hosts you may need to add `extra_hosts: ["host.docker.internal:host-gateway"]`
> to the `django-web` service in `docker-compose.yml`.

---

## 3. Ollama setup (host machine)

```bash
brew install ollama        # or see https://ollama.com/download for your OS
ollama serve                # runs the Ollama server (may already run as a background service)

# Pull the models this project uses
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Confirm both are available
ollama list
```

Sanity check the server is reachable:

```bash
curl http://localhost:11434/api/tags
```

If you use different model names/tags, update `OLLAMA_CHAT_MODEL` /
`OLLAMA_EMBEDDING_MODEL` in `.env` to match exactly what `ollama list` shows.

---

## 4. Start Docker services

```bash
docker compose up -d --build
```

This brings up:

- `db` — PostgreSQL with the `pgvector` extension (image: `pgvector/pgvector:pg16`)
- `redis` — broker/result backend for Celery
- `django-web` — the Django app (DRF API)
- `celery-worker` / `celery-beat` — background scraping & embedding tasks

Check everything is healthy:

```bash
docker compose ps
docker compose logs -f django-web
```

---

## 5. Database restoration (existing data)

If you're restoring from an existing dump rather than starting fresh:

```bash
# Copy your dump file into the db container
docker compose cp ./backups/price_data.dump db:/tmp/price_data.dump

# Restore (adjust flags depending on whether it's a plain SQL or custom-format dump)
docker compose exec db pg_restore -U postgres -d price_data --no-owner --clean /tmp/price_data.dump

# Or, for a plain .sql dump:
docker compose exec -T db psql -U postgres -d price_data < ./backups/price_data.sql
```

After restoring onto a pgvector-based image, refresh collation to clear the common
version-mismatch warning:

```bash
docker compose exec db psql -U postgres -d price_data \
  -c "ALTER DATABASE price_data REFRESH COLLATION VERSION;"
```

Enable the vector extension (idempotent — safe even if already enabled):

```bash
docker compose exec db psql -U postgres -d price_data \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## 6. Run migrations (including the embedding model + index)

```bash
docker compose exec django-web python manage.py makemigrations
docker compose exec django-web python manage.py migrate
```

This creates/updates all tables, including:

- `ProductEmbedding` — stores a 768-dim vector per product (matches
  `nomic-embed-text`'s output size) plus the source text it was generated from
- An **HNSW index** on the vector column for fast cosine-distance similarity search

> If you change embedding models later to one with a different output dimension,
> you'll need a new migration to alter `VectorField(dimensions=...)` and a full
> re-embed (`--force` flag below).

---

## 7. Generate embeddings for existing products

```bash
docker compose exec django-web python manage.py backfill_embeddings
```

Options:

```bash
# Re-embed everything, even products that already have an embedding
docker compose exec django-web python manage.py backfill_embeddings --force
```

New products created after this point are embedded automatically via a Celery task
triggered on save — no manual step needed for those.

---

## 8. Test the LLM search API

Endpoint: `POST /api/product/llm-search/`

```bash
curl -X POST http://localhost:8000/api/product/llm-search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the cheapest gaming mouse available?"}'
```

Example response:

```json
{
  "answer": "The cheapest gaming mouse currently available is ...",
  "tools_used": [
    {"tool": "get_cheapest_product", "args": {"category_name": "gaming mouse"}}
  ]
}
```

Other things to try:

```bash
# Semantic/fuzzy search
curl -X POST http://localhost:8000/api/product/llm-search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "recommend a budget wireless keyboard"}'

# Price trend
curl -X POST http://localhost:8000/api/product/llm-search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "how has the price of iPhone 15 changed over the last 30 days?"}'

# Cross-site comparison
curl -X POST http://localhost:8000/api/product/llm-search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "compare prices for RTX 4060 across sites"}'
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `collation version mismatch` warning | DB restored/created under a different glibc version | `ALTER DATABASE ... REFRESH COLLATION VERSION;` |
| `Unknown command: 'backfill_embeddings'` | Missing `__init__.py` in `management/` or `management/commands/` | Add empty `__init__.py` files in both dirs |
| `404 Client Error ... /api/chat` | `OLLAMA_CHAT_MODEL` doesn't match a model in `ollama list` | Update `.env` to the exact name/tag shown by `ollama list`, restart `django-web` |
| Django container can't reach Ollama | `host.docker.internal` not resolving (Linux host) | Add `extra_hosts: ["host.docker.internal:host-gateway"]` to the service in compose |
| `No changes detected` on `makemigrations` | Model not actually saved, wrong app, or stale container code | Confirm bind mount is active; check `python manage.py shell -c "from product.models import ProductEmbedding"` |
| Weak/irrelevant semantic search results | Sparse `source_text` (empty description/category on many products) | Inspect `ProductEmbedding.source_text` for a few rows; enrich `build_product_text()` |

---

## 10. Useful commands reference

```bash
# Tail logs
docker compose logs -f django-web
docker compose logs -f celery-worker

# Django shell
docker compose exec django-web python manage.py shell

# Re-embed everything after changing embedding text format
docker compose exec django-web python manage.py backfill_embeddings --force

# Check Ollama models available to the host
ollama list
```
