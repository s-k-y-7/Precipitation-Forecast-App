from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
import numpy as np

from forecasts.models import ForecastRun
from forecasts.pipeline.grid import GridMetadata


@override_settings(ROOT_URLCONF="config.urls")
class ForecastRunApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()
        self.latest = ForecastRun.objects.create(
            run_id="ifs-oper-0p25-20261114T12Z-t24",
            model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now, valid_time=now + timedelta(hours=24), lead_hours=24,
            available_steps_hours=[3, 6, 9, 12, 15, 18, 21, 24],
            source_sha256="a" * 64, source_expires_at=now + timedelta(hours=24),
            grid_metadata={"shortName": "tp", "units": "m"},
        )
        self.old = ForecastRun.objects.create(
            run_id="ifs-oper-0p25-20261114T00Z-t24",
            model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now - timedelta(hours=12), valid_time=now + timedelta(hours=12), lead_hours=24,
            available_steps_hours=[3, 6, 9, 12, 15, 18, 21, 24],
            source_sha256="b" * 64, source_expires_at=now - timedelta(hours=1),
            cache_expires_at=now + timedelta(hours=4), grid_metadata={"shortName": "tp"},
        )
        self.unvalidated = ForecastRun.objects.create(
            run_id="ifs-oper-0p25-unvalidated-t24",
            model="ifs", stream="oper", resolution="0p25", parameter="tp",
            initialization_time=now - timedelta(hours=6), valid_time=now + timedelta(hours=18), lead_hours=24,
            source_sha256="d" * 64, source_expires_at=now + timedelta(hours=24), grid_metadata={},
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
        self.assertNotIn(self.unvalidated.run_id, [run["run_id"] for run in response.data["runs"]])
        self.assertEqual(response.data["runs"][0]["source_provider"], "ecmwf-open-data")
        self.assertEqual(response.data["runs"][0]["source_sha256"], "a" * 64)
        self.assertEqual(response.data["runs"][0]["available_steps_hours"], [3, 6, 9, 12, 15, 18, 21, 24])

    def test_tile_rejects_invalid_coordinates_without_network_access(self):
        response = self.client.get(f"/api/forecast-runs/{self.latest.run_id}/precipitation/v1/2/4/0.png")

        self.assertEqual(response.status_code, 400)

    def test_expired_run_is_not_retrieved_again_by_direct_tile_url(self):
        response = self.client.get("/api/forecast-runs/expired-run/precipitation/v1/2/1/1.png")

        self.assertEqual(response.status_code, 410)

    def test_invalid_interval_step_is_rejected(self):
        response = self.client.get(f"/api/forecast-runs/{self.latest.run_id}/precipitation/v2/4/2/1/1.png")

        self.assertEqual(response.status_code, 400)

    def test_point_query_outside_india_is_rejected_without_source_access(self):
        response = self.client.get(f"/api/forecast-runs/{self.latest.run_id}/precipitation/point/?lat=23.8&lon=90.4")

        self.assertEqual(response.status_code, 400)
        self.assertIn("India only", response.data["detail"])

    def test_bhopal_is_inside_india_but_missing_run_is_reported_as_unavailable(self):
        from forecasts.pipeline.india import is_inside_india

        self.assertTrue(is_inside_india(77.41, 23.26))
        response = self.client.get("/api/forecast-runs/not-registered/precipitation/point/?lat=23.26&lon=77.41")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Forecast run is unavailable.")

    def test_point_forecast_uses_nearest_gridpoint_and_reports_eight_intervals(self):
        grid = GridMetadata(4, 4, 77.0, 24.0, 0.25, 0.25, 1000.0)
        fields = {
            step: SimpleNamespace(
                values=np.arange(16, dtype=np.float64) * (step / 1000.0),
                grid=grid,
                metadata={"packingError": 0.000001},
            )
            for step in (3, 6, 9, 12, 15, 18, 21, 24)
        }
        with (
            patch("forecasts.pipeline.service._source_for_run", return_value=(Path(__file__), "a" * 64)),
            patch("forecasts.pipeline.service._read_fields", return_value=fields),
        ):
            response = self.client.get(
                f"/api/forecast-runs/{self.latest.run_id}/precipitation/point/?lat=23.26&lon=77.41"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["requested_location"], {"lat": 23.26, "lon": 77.41})
        self.assertEqual(response.data["grid_point"], {"lat": 23.25, "lon": 77.5})
        self.assertEqual([item["end_step_hours"] for item in response.data["intervals"]], [3, 6, 9, 12, 15, 18, 21, 24])
        for item in response.data["intervals"]:
            self.assertAlmostEqual(item["precipitation_mm"], 42.0)

    def test_india_coverage_api_serves_polygon_geometry(self):
        response = self.client.get("/api/coverage/india/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertGreater(len(response.data["features"]), 1)
