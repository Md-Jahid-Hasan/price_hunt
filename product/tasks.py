import logging
import queue

from asgiref.sync import async_to_sync
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="ryans_queue")
def scrape_ryans(self):
    from product.scraper.ryans_scraper import RyansScraper
    try:
        results = async_to_sync(RyansScraper().scrape)()
        total = sum(len(r) for r in results)
        logger.info("Ryans scrape complete: %s products across %s categories", total, len(results))
        return {"categories": len(results), "total_products": total}
    except Exception as exc:
        logger.error("Ryans scrape failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="startech_queue")
def scrape_startech(self):
    from product.scraper.startech_scraper import StartechScraper
    try:
        results = async_to_sync(StartechScraper().scrape)()
        total = sum(len(r) for r in results)
        logger.info("Startech scrape complete: %s products across %s categories", total, len(results))
        return {"categories": len(results), "total_products": total}
    except Exception as exc:
        logger.error("Startech scrape failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue="techland_queue")
def scrape_techland(self):
    from product.scraper.techland_scraper import TechlandScraper
    try:
        results = async_to_sync(TechlandScraper().scrape)()
        total = sum(len(r) for r in results)
        logger.info("Techland scrape complete: %s products across %s categories", total, len(results))
        return {"categories": len(results), "total_products": total}
    except Exception as exc:
        logger.error("Techland scrape failed: %s", exc)
        raise self.retry(exc=exc)