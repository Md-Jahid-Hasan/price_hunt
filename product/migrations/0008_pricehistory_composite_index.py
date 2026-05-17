from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0007_category_parent"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="pricehistory",
            index=models.Index(
                fields=["product", "-recorded_at"],
                name="ph_product_recorded_at_idx",
            ),
        ),
    ]