from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from forecasts.models import ForecastRun
from forecasts.pipeline.opendata import run_id_for


class FrozenDateTime(datetime):
    current = datetime(2026, 11, 15, 12, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current


class RefreshForecastRunsCommandTests(TestCase):
    def setUp(self):
        patcher = patch("forecasts.management.commands.refresh_forecast_runs.datetime", FrozenDateTime)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_skips_a_fully_registered_run_while_its_source_is_live(self):
        initialization = FrozenDateTime.current.replace(minute=0)
        ForecastRun.objects.create(
            run_id=run_id_for(initialization), model="ifs", stream="oper", resolution="0p25",
            parameter="tp", initialization_time=initialization,
            valid_time=initialization + timedelta(hours=24), lead_hours=24,
            available_steps_hours=[3, 6, 9, 12, 15, 18, 21, 24],
            source_sha256="a" * 64, source_expires_at=FrozenDateTime.current + timedelta(hours=20),
            grid_metadata={},
        )

        with patch("forecasts.management.commands.refresh_forecast_runs.register_forecast_run") as register:
            call_command("refresh_forecast_runs", lookback_hours=1)

        register.assert_not_called()

    def test_skips_a_run_if_its_tile_cache_is_live_after_source_expiry(self):
        initialization = FrozenDateTime.current.replace(minute=0)
        ForecastRun.objects.create(
            run_id=run_id_for(initialization), model="ifs", stream="oper", resolution="0p25",
            parameter="tp", initialization_time=initialization,
            valid_time=initialization + timedelta(hours=24), lead_hours=24,
            available_steps_hours=[3, 6, 9, 12, 15, 18, 21, 24],
            source_sha256="a" * 64, source_expires_at=FrozenDateTime.current - timedelta(hours=1),
            cache_expires_at=FrozenDateTime.current + timedelta(hours=2), grid_metadata={},
        )

        with patch("forecasts.management.commands.refresh_forecast_runs.register_forecast_run") as register:
            call_command("refresh_forecast_runs", lookback_hours=1)

        register.assert_not_called()

    def test_failed_candidate_is_retried_on_a_subsequent_execution(self):
        initialization = FrozenDateTime.current.replace(minute=0)
        run_id = run_id_for(initialization)
        source_expiry = FrozenDateTime.current - timedelta(hours=2)
        ForecastRun.objects.create(
            run_id=run_id, model="ifs", stream="oper", resolution="0p25",
            parameter="tp", initialization_time=initialization,
            valid_time=initialization + timedelta(hours=24), lead_hours=24,
            available_steps_hours=[3, 6, 9, 12, 15, 18, 21, 24],
            source_sha256="a" * 64, source_expires_at=source_expiry,
            cache_expires_at=source_expiry, grid_metadata={"verified": True},
        )
        with patch(
            "forecasts.management.commands.refresh_forecast_runs.register_forecast_run",
            side_effect=RuntimeError("ECMWF run is not published yet"),
        ) as first_attempt:
            with self.assertRaises(CommandError):
                call_command("refresh_forecast_runs", lookback_hours=1)

        with patch(
            "forecasts.management.commands.refresh_forecast_runs.register_forecast_run",
            return_value=SimpleNamespace(run_id=run_id),
        ) as next_attempt:
            call_command("refresh_forecast_runs", lookback_hours=1)

        first_attempt.assert_called_once_with(initialization)
        next_attempt.assert_called_once_with(initialization)
        existing = ForecastRun.objects.get(run_id=run_id)
        self.assertEqual(existing.source_sha256, "a" * 64)
        self.assertEqual(existing.source_expires_at, source_expiry)
        self.assertEqual(existing.grid_metadata, {"verified": True})
