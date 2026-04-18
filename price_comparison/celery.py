import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "price_comparison.settings")

app = Celery("price_comparison")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()