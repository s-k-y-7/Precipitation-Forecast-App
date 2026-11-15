from rest_framework import serializers

from forecasts.models import ForecastRun


class ForecastRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastRun
        fields = (
            "run_id", "model", "stream", "resolution", "parameter",
            "initialization_time", "valid_time", "lead_hours", "source_provider",
            "source_sha256", "grid_metadata",
        )
