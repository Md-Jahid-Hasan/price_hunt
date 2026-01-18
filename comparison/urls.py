from .views import ProductComparisonView, home_page
from django.urls import path

urlpatterns = [
    path('', home_page, name='home'),
    path('api/product-comparison/', ProductComparisonView.as_view(), name='product_comparison'),
]