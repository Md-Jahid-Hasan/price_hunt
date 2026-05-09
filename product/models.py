from django.db import models
from django.utils.text import slugify

class Site(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField()

    def __str__(self):
        return self.name

class Category(models.Model):
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, related_name='categories', null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='subcategories', null=True, blank=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=255)
    url = models.URLField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def deactivate_children(self) -> int:
        """
        Recursively sets is_active=False on all descendant categories.
        Returns the total number of categories updated.
        """
        # Collect all descendant IDs via BFS to avoid deep recursion
        ids_to_deactivate = []
        queue = list(self.subcategories.values_list('id', flat=True))
        while queue:
            ids_to_deactivate.extend(queue)
            queue = list(
                Category.objects.filter(parent_id__in=queue)
                .values_list('id', flat=True)
            )
        if not ids_to_deactivate:
            return 0
        return Category.objects.filter(id__in=ids_to_deactivate).update(is_active=False)


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=255)
    url = models.URLField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.site.name}"


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.product.name} - ${self.price} at {self.recorded_at}"
