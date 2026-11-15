from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forecasts", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="forecastrun",
            name="source_provider",
            field=models.CharField(default="ecmwf-open-data", max_length=32),
        ),
    ]
