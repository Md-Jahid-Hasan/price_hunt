from django.contrib import admin
from .models import Site, Category, Product, PriceHistory

# Register your models here.

admin.site.register(Site)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(PriceHistory)

