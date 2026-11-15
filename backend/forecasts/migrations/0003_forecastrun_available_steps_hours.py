from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forecasts", "0002_source_provider")]

    operations = [
        migrations.AddField(
            model_name="forecastrun",
            name="available_steps_hours",
            field=models.JSONField(default=list),
        ),
    ]
