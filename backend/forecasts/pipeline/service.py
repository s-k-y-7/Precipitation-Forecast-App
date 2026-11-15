"""Coordinate ECMWF bundle retrieval, metadata validation, and cached map/point products."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone as django_timezone

from forecasts.models import ForecastRun
from forecasts.pipeline.cache import cached_tile, get_or_create_source, get_or_create_tile, invalidate_source, prune_expired_cache
from forecasts.pipeline.grib import ForecastFieldError, read_precipitation_bundle
from forecasts.pipeline.grid import PROCESSING_VERSION, STYLE_VERSION, INDIA_BOUNDS, cache_key, interval_precipitation, render_precipitation_tile, sample_xyz_tile
from forecasts.pipeline.india import BOUNDARY_VERSION, is_inside_india
from forecasts.pipeline.opendata import download_ifs_precipitation


@lru_cache(maxsize=4)
def _read_fields(path_string: str, modified_ns: int, initialization_iso: str):
    del modified_ns
    initialization = datetime.fromisoformat(initialization_iso)
    return read_precipitation_bundle(Path(path_string), tuple(settings.FORECAST_STEPS_HOURS), initialization)


def _source_for_run(run: ForecastRun) -> tuple[Path, str]:
    def downloader(target: Path) -> None:
        download_ifs_precipitation(run.initialization_time, target)

    path, digest, downloaded = get_or_create_source(run.run_id, downloader)
    try:
        fields = _read_fields(str(path), path.stat().st_mtime_ns, run.initialization_time.isoformat())
    except ForecastFieldError:
        invalidate_source(run.run_id)
        raise
    if downloaded or digest != run.source_sha256 or run.available_steps_hours != list(settings.FORECAST_STEPS_HOURS):
        run.source_sha256 = digest
        run.available_steps_hours = list(settings.FORECAST_STEPS_HOURS)
        run.source_expires_at = datetime.fromtimestamp(
            path.stat().st_mtime + settings.FORECAST_SOURCE_CACHE_TTL_SECONDS, tz=timezone.utc
        )
        run.grid_metadata = fields[settings.FORECAST_STEPS_HOURS[-1]].metadata
        run.save(update_fields=("source_sha256", "available_steps_hours", "source_expires_at", "grid_metadata"))
    return path, digest


def _identity(run: ForecastRun, digest: str, z: int, x: int, y: int, step: int | None) -> dict:
    return {
        "provider": run.source_provider, "model": run.model, "stream": run.stream,
        "resolution": run.resolution, "run": run.run_id, "source_sha256": digest,
        "parameter": run.parameter, "level": "surface", "step_type": "accum",
        "interval_hours": [0 if step is None else step - 3, run.lead_hours if step is None else step],
        "region_bounds": INDIA_BOUNDS, "z": z, "x": x, "y": y,
        "boundary_version": BOUNDARY_VERSION,
        "processing_version": PROCESSING_VERSION, "style_version": STYLE_VERSION,
    }


def _tile(run: ForecastRun, step: int | None, z: int, x: int, y: int) -> tuple[Path, bool]:
    prune_expired_cache()
    digest = run.source_sha256
    key = cache_key(_identity(run, digest, z, x, y, step))
    hit = cached_tile(key)
    if hit:
        return hit, False
    source, digest = _source_for_run(run)
    fields = _read_fields(str(source), source.stat().st_mtime_ns, run.initialization_time.isoformat())
    key = cache_key(_identity(run, digest, z, x, y, step))

    def render() -> bytes:
        current_step = run.lead_hours if step is None else step
        current = fields[current_step]
        if step is None:
            values_to_sample = current.values
        else:
            previous = None if step == settings.FORECAST_STEPS_HOURS[0] else fields[step - 3]
            values_to_sample, _valid = interval_precipitation(
                None if previous is None else previous.values, current.values,
                0.0 if previous is None else float(previous.metadata["packingError"]),
                float(current.metadata["packingError"]),
            )
        return render_precipitation_tile(sample_xyz_tile(
            values_to_sample, current.grid, z, x, y,
            input_to_mm=1.0 if step is not None else None,
        ))

    path, created = get_or_create_tile(key, render)
    if created:
        run.cache_expires_at = django_timezone.now() + timedelta(seconds=settings.FORECAST_TILE_CACHE_TTL_SECONDS)
        run.save(update_fields=("cache_expires_at",))
    return path, created


def get_forecast_tile(run: ForecastRun, z: int, x: int, y: int) -> tuple[Path, bool]:
    return _tile(run, None, z, x, y)


def get_interval_tile(run: ForecastRun, step: int, z: int, x: int, y: int) -> tuple[Path, bool]:
    if step not in run.available_steps_hours:
        raise ValueError("Forecast step is unavailable for this run")
    return _tile(run, step, z, x, y)


def get_point_forecast(run_id: str, lat: float, lon: float) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Provide valid latitude and longitude coordinates.")
    if not is_inside_india(lon, lat):
        raise ValueError("This forecast currently covers India only. Choose a location within India.")
    run = ForecastRun.objects.filter(run_id=run_id).first()
    if run is None:
        raise ForecastRun.DoesNotExist
    path, _ = _source_for_run(run)
    fields = _read_fields(str(path), path.stat().st_mtime_ns, run.initialization_time.isoformat())
    step_values = []
    grid_point = None
    for step in settings.FORECAST_STEPS_HOURS:
        current = fields[step]
        column = round(((lon % 360) - current.grid.first_longitude) % 360 / current.grid.longitude_increment) % current.grid.width
        row = round((current.grid.first_latitude - lat) / current.grid.latitude_increment)
        if not (0 <= row < current.grid.height):
            raise ValueError("Location is outside the forecast grid.")
        grid_lat = current.grid.first_latitude - row * current.grid.latitude_increment
        grid_lon = (current.grid.first_longitude + column * current.grid.longitude_increment + 180) % 360 - 180
        grid_point = {"lat": grid_lat, "lon": grid_lon}
        previous = None if step == settings.FORECAST_STEPS_HOURS[0] else fields[step - 3]
        amount, valid = interval_precipitation(
            None if previous is None else previous.values,
            current.values,
            0.0 if previous is None else float(previous.metadata["packingError"]),
            float(current.metadata["packingError"]),
        )
        mm = float(amount[row * current.grid.width + column])
        step_values.append({
            "start_step_hours": step - 3, "end_step_hours": step,
            "valid_time": (run.initialization_time + timedelta(hours=step)).isoformat(),
            "precipitation_mm": mm if bool(valid[row * current.grid.width + column]) else None,
        })
    return {"run_id": run.run_id, "requested_location": {"lat": lat, "lon": lon}, "grid_point": grid_point, "intervals": step_values}


def register_forecast_run(initialization_time: datetime) -> ForecastRun:
    from forecasts.pipeline.opendata import run_id_for
    initialization_time = initialization_time.astimezone(timezone.utc)
    run_id = run_id_for(initialization_time)
    def downloader(target: Path) -> None:
        download_ifs_precipitation(initialization_time, target)
    path, checksum, _downloaded = get_or_create_source(run_id, downloader)
    try:
        fields = read_precipitation_bundle(path, tuple(settings.FORECAST_STEPS_HOURS), initialization_time)
    except ForecastFieldError:
        invalidate_source(run_id)
        raise
    final_step = settings.FORECAST_STEPS_HOURS[-1]
    return ForecastRun.objects.update_or_create(
        run_id=run_id,
        defaults={
            "model": settings.FORECAST_MODEL, "stream": settings.FORECAST_STREAM,
            "resolution": settings.FORECAST_RESOLUTION, "parameter": "tp",
            "initialization_time": initialization_time,
            "valid_time": initialization_time + timedelta(hours=final_step),
            "lead_hours": final_step, "available_steps_hours": list(settings.FORECAST_STEPS_HOURS),
            "source_provider": "ecmwf-open-data", "source_sha256": checksum,
            "source_expires_at": datetime.fromtimestamp(
                path.stat().st_mtime + settings.FORECAST_SOURCE_CACHE_TTL_SECONDS, tz=timezone.utc
            ),
            "grid_metadata": fields[final_step].metadata,
        },
    )[0]
