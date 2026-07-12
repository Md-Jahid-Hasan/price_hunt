# product/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
from .tasks import embed_product_task


@receiver(post_save, sender=Product)
def trigger_product_embedding(sender, instance, **kwargs):
    embed_product_task.delay(instance.id)