from django.urls import path
from .views import LLMSearchView

urlpatterns = [
    path("llm-search/", LLMSearchView.as_view(), name="llm-search"),
]