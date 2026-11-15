# Generated for the first persistent ECMWF forecast catalog.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="ForecastRun",
            fields=[
                ("run_id", models.CharField(max_length=96, primary_key=True, serialize=False)),
                ("model", models.CharField(max_length=32)),
                ("stream", models.CharField(max_length=32)),
                ("resolution", models.CharField(max_length=16)),
                ("parameter", models.CharField(default="tp", max_length=16)),
                ("initialization_time", models.DateTimeField()),
                ("valid_time", models.DateTimeField()),
                ("lead_hours", models.PositiveSmallIntegerField()),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_expires_at", models.DateTimeField()),
                ("cache_expires_at", models.DateTimeField(blank=True, null=True)),
                ("grid_metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("-initialization_time",)},
        ),
    ]
