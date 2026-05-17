from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import ngettext
from product.models import Category, Site, Product, PriceHistory
from django.urls import reverse
from django.utils.html import format_html, format_html_join

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'site', 'is_active_toggle', 'is_active')
    list_filter = ('site__name', 'is_active')
    list_editable = ('is_active',)  # Bulk edit is_active inline
    search_fields = ('name', 'slug', 'url')
    prepopulated_fields = {'slug': ('name',)}
    actions = ('make_active', 'make_inactive')  # add actions
    readonly_fields = ("descendants_html",)

    @admin.action(description="Mark selected categories as active")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                "%d category was marked active.",
                "%d categories were marked active.",
                updated,
            ) % updated
        )

    @admin.action(description="Mark selected categories as inactive")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%d category was marked inactive.",
                "%d categories were marked inactive.",
                updated,
            ) % updated
        )

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'site', 'parent')
        }),
        ('URL', {
            'fields': ('url', 'keywords')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Children', {
            'fields': ('descendants_html',),
        })
    )

    def _collect_descendant_ids(self, obj: Category) -> list[int]:
        queue = list(obj.subcategories.values_list('id', flat=True))
        return queue

    def descendants_html(self, obj):
        """
        Return an HTML <ul> with links to every descendant (all levels).
        WARNING: This can be heavy if the subtree is large.
        """
        if obj is None:
            return ""
        ids = self._collect_descendant_ids(obj)
        if not ids:
            return format_html("<em>No child categories</em>")
        qs = Category.objects.filter(id__in=ids).order_by("name")
        # Build list items with admin change links
        items = [
            format_html('<a href="{}">{}</a>',
                        reverse('admin:product_category_change', args=(c.pk,)), c.name)
            for c in qs
        ]
        return format_html('<ul>{}</ul>', format_html_join('', '<li>{}</li>', ((it,) for it in items)))

    descendants_html.short_description = "All child categories (descendants)"

    def url_preview(self, obj):
        """Show truncated URL as clickable link"""
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.url,
            obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
        )
    url_preview.short_description = 'URL'

    def is_active_toggle(self, obj):
        """Visual indicator for is_active (also editable via list_editable)"""
        color = 'green' if obj.is_active else 'red'
        status = '✓ Active' if obj.is_active else '✗ Inactive'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status
        )
    is_active_toggle.short_description = 'Status'

    def created_info(self, obj):
        """Show creation time in detail view"""
        return obj.created_at if hasattr(obj, 'created_at') else 'N/A'
    created_info.short_description = 'Created'

    def get_queryset(self, request):
        """Optimize queries with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('site')


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'category_count')
    search_fields = ('name', 'url')
    readonly_fields = ('category_count',)

    def category_count(self, obj):
        return obj.categories.count()
    category_count.short_description = 'Categories'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'site', 'category', 'price', 'updated_at')
    list_filter = ('site__name', 'category', 'created_at')
    search_fields = ('name', 'url')
    readonly_fields = ('slug', 'created_at', 'updated_at')
    raw_id_fields = ('category', 'site')


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'price', 'recorded_at')
    list_filter = ('recorded_at', 'product__site')
    search_fields = ('product__name',)
    readonly_fields = ('product', 'price', 'recorded_at')