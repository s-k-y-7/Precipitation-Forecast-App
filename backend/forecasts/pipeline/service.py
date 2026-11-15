"""Coordinate source retrieval, validation, cache keys, and tile generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone as django_timezone

from forecasts.models import ForecastRun
from forecasts.pipeline.cache import (
    cached_tile,
    get_or_create_source,
    get_or_create_tile,
    prune_expired_cache,
)
from forecasts.pipeline.grib import read_precipitation_field
from forecasts.pipeline.grid import (
    PROCESSING_VERSION,
    STYLE_VERSION,
    INDIA_BOUNDS,
    cache_key,
    render_precipitation_tile,
    sample_xyz_tile,
)
from forecasts.pipeline.opendata import download_ifs_precipitation


@lru_cache(maxsize=2)
def _read_cached_field(path_string: str, modified_ns: int, lead_hours: int, initialization_iso: str):
    del modified_ns  # part of the cache identity so replacement files are decoded again.
    initialization = datetime.fromisoformat(initialization_iso)
    return read_precipitation_field(Path(path_string), lead_hours, initialization)


def tile_cache_identity(run: ForecastRun, source_sha256: str, z: int, x: int, y: int) -> dict:
    return {
        "provider": "ecmwf-open-data",
        "data_type": "fc",
        "model": run.model,
        "stream": run.stream,
        "resolution": run.resolution,
        "run": run.run_id,
        "source_sha256": source_sha256,
        "parameter": run.parameter,
        "level": "surface",
        "step_type": "accum",
        "grid_type": "regular_ll",
        "accumulation": [0, run.lead_hours],
        "lead_hours": run.lead_hours,
        "tile_scheme": "xyz-web-mercator-256-v1",
        "region_bounds": INDIA_BOUNDS,
        "z": z,
        "x": x,
        "y": y,
        "processing_version": PROCESSING_VERSION,
        "style_version": STYLE_VERSION,
    }


def get_forecast_tile(run: ForecastRun, z: int, x: int, y: int) -> tuple[Path, bool]:
    prune_expired_cache()
    tile_hash = cache_key(tile_cache_identity(run, run.source_sha256, z, x, y))
    path = cached_tile(tile_hash)
    if path:
        return path, False

    source, source_hash = _source_for_run(run)
    tile_hash = cache_key(tile_cache_identity(run, source_hash, z, x, y))

    def render() -> bytes:
        stat = source.stat()
        field = _read_cached_field(
            str(source), stat.st_mtime_ns, run.lead_hours, run.initialization_time.isoformat()
        )
        sampled = sample_xyz_tile(field.values, field.grid, z, x, y)
        return render_precipitation_tile(sampled)

    path, created = get_or_create_tile(tile_hash, render)
    if created:
        run.cache_expires_at = django_timezone.now() + timedelta(seconds=settings.FORECAST_CACHE_TTL_SECONDS)
        run.save(update_fields=("cache_expires_at",))
    return path, created


def _source_for_run(run: ForecastRun) -> tuple[Path, str]:
    def downloader(target: Path) -> None:
        download_ifs_precipitation(run.initialization_time, target)

    path, source_hash, downloaded = get_or_create_source(run.run_id, downloader)
    if downloaded or source_hash != run.source_sha256:
        field = read_precipitation_field(path, run.lead_hours, run.initialization_time)
        run.source_sha256 = source_hash
        run.source_expires_at = django_timezone.now() + timedelta(seconds=settings.FORECAST_CACHE_TTL_SECONDS)
        run.grid_metadata = field.metadata
        run.save(update_fields=("source_sha256", "source_expires_at", "grid_metadata"))
    return path, source_hash


def register_forecast_run(initialization_time: datetime) -> ForecastRun:
    from forecasts.pipeline.opendata import run_id_for

    initialization_time = initialization_time.astimezone(timezone.utc)
    run_id = run_id_for(initialization_time)
    existing = ForecastRun.objects.filter(run_id=run_id).first()
    if existing:
        # Refresh the source TTL only when the staged file itself is still fresh.
        from forecasts.pipeline.cache import _fresh, source_path as cached_source_path

        path = cached_source_path(run_id)
        if _fresh(path, settings.FORECAST_CACHE_TTL_SECONDS):
            return existing
    def downloader(target: Path) -> None:
        download_ifs_precipitation(initialization_time, target)

    from forecasts.pipeline.cache import get_or_create_source

    path, checksum, _ = get_or_create_source(run_id, downloader)
    field = read_precipitation_field(path, settings.FORECAST_LEAD_HOURS, initialization_time)
    valid_time = initialization_time + timedelta(hours=settings.FORECAST_LEAD_HOURS)
    return ForecastRun.objects.update_or_create(
        run_id=run_id,
        defaults={
            "model": settings.FORECAST_MODEL,
            "stream": settings.FORECAST_STREAM,
            "resolution": settings.FORECAST_RESOLUTION,
            "parameter": "tp",
            "initialization_time": initialization_time,
            "valid_time": valid_time,
            "lead_hours": settings.FORECAST_LEAD_HOURS,
            "source_provider": "ecmwf-open-data",
            "source_sha256": checksum,
            "source_expires_at": django_timezone.now() + timedelta(seconds=settings.FORECAST_CACHE_TTL_SECONDS),
            "grid_metadata": field.metadata,
        },
    )[0]
