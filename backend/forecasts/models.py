from django.db import models


class ForecastRun(models.Model):
    """Persistent catalog and provenance; forecast grid values remain in file cache."""

    run_id = models.CharField(max_length=96, primary_key=True)
    model = models.CharField(max_length=32)
    stream = models.CharField(max_length=32)
    resolution = models.CharField(max_length=16)
    parameter = models.CharField(max_length=16, default="tp")
    initialization_time = models.DateTimeField()
    valid_time = models.DateTimeField()
    lead_hours = models.PositiveSmallIntegerField()
    source_provider = models.CharField(max_length=32, default="ecmwf-open-data")
    source_sha256 = models.CharField(max_length=64)
    source_expires_at = models.DateTimeField()
    cache_expires_at = models.DateTimeField(null=True, blank=True)
    grid_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-initialization_time",)

    def __str__(self) -> str:
        return self.run_id
