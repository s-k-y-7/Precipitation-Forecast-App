from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from forecasts.models import ForecastRun


@override_settings(ROOT_URLCONF="config.urls")
class ForecastRunApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()
        self.latest = ForecastRun.objects.create(
            run_id="ifs-oper-0p25-20261114T12Z-t24",
            model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now, valid_time=now + timedelta(hours=24), lead_hours=24,
            source_sha256="a" * 64, source_expires_at=now + timedelta(hours=24),
            grid_metadata={"shortName": "tp", "units": "m"},
        )
        self.old = ForecastRun.objects.create(
            run_id="ifs-oper-0p25-20261114T00Z-t24",
            model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now - timedelta(hours=12), valid_time=now + timedelta(hours=12), lead_hours=24,
            source_sha256="b" * 64, source_expires_at=now - timedelta(hours=1),
            cache_expires_at=now + timedelta(hours=4), grid_metadata={"shortName": "tp"},
        )
        ForecastRun.objects.create(
            run_id="expired-run", model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now - timedelta(days=4), valid_time=now - timedelta(days=3), lead_hours=24,
            source_sha256="c" * 64, source_expires_at=now - timedelta(days=3),
            cache_expires_at=now - timedelta(days=2), grid_metadata={},
        )

    def test_catalog_keeps_recent_cached_previous_run_and_excludes_expired(self):
        response = self.client.get("/api/forecast-runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latest_run_id"], self.latest.run_id)
        self.assertEqual([run["run_id"] for run in response.data["runs"]], [self.latest.run_id, self.old.run_id])
        self.assertEqual(response.data["runs"][0]["source_provider"], "ecmwf-open-data")
        self.assertEqual(response.data["runs"][0]["source_sha256"], "a" * 64)

    def test_tile_rejects_invalid_coordinates_without_network_access(self):
        response = self.client.get(f"/api/forecast-runs/{self.latest.run_id}/precipitation/v1/2/4/0.png")

        self.assertEqual(response.status_code, 400)

    def test_expired_run_is_not_retrieved_again_by_direct_tile_url(self):
        response = self.client.get("/api/forecast-runs/expired-run/precipitation/v1/2/1/1.png")

        self.assertEqual(response.status_code, 410)
