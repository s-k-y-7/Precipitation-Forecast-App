from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from forecasts.models import ForecastRun
from forecasts.pipeline.opendata import run_id_for
from forecasts.pipeline.service import register_forecast_run


class Command(BaseCommand):
    help = "Fetch and register available recent ECMWF IFS operational precipitation runs."

    def add_arguments(self, parser):
        parser.add_argument("--lookback-hours", type=int, default=24)

    def handle(self, *args, **options):
        lookback = options["lookback_hours"]
        if not 1 <= lookback <= 168:
            self.stderr.write("--lookback-hours must be between 1 and 168")
            return

        now = datetime.now(timezone.utc)
        latest_cycle_hour = (now.hour // 12) * 12
        latest = now.replace(hour=latest_cycle_hour, minute=0, second=0, microsecond=0)
        cutoff = now - timedelta(hours=lookback)
        candidates = []
        cycle = latest
        while cycle >= cutoff:
            candidates.append(cycle)
            cycle -= timedelta(hours=12)

        registered = 0
        for initialization_time in candidates:
            run_id = run_id_for(initialization_time)
            already_available = ForecastRun.objects.filter(
                run_id=run_id,
                available_steps_hours=list(settings.FORECAST_STEPS_HOURS),
            ).filter(
                Q(source_expires_at__gt=now) | Q(cache_expires_at__gt=now)
            ).exists()
            if already_available:
                registered += 1
                self.stdout.write(f"Already available {run_id}")
                continue
            try:
                run = register_forecast_run(initialization_time)
            except Exception as error:
                self.stderr.write(
                    f"Unavailable {settings.FORECAST_MODEL.upper()} run "
                    f"{initialization_time:%Y-%m-%d %H:%M} UTC: {type(error).__name__}"
                )
                continue
            registered += 1
            self.stdout.write(self.style.SUCCESS(f"Registered {run.run_id}"))

        if not registered:
            raise CommandError("No usable ECMWF forecast runs were available in the requested window.")
        else:
            self.stdout.write(f"{registered} run(s) available to the map.")
