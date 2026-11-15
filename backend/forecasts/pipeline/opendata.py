"""ECMWF Open Data retrieval and deterministic forecast-run identity."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings


def run_id_for(initialization_time: datetime, lead_hours: int | None = None) -> str:
    lead = settings.FORECAST_LEAD_HOURS if lead_hours is None else lead_hours
    stamp = initialization_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
    return f"{settings.FORECAST_MODEL}-{settings.FORECAST_STREAM}-{settings.FORECAST_RESOLUTION}-{stamp}-t{lead}"


def download_ifs_precipitation(initialization_time: datetime, target: Path) -> None:
    """Retrieve only the IFS total-precipitation field at the configured lead."""
    try:
        from ecmwf.opendata import Client
    except ImportError as error:
        raise RuntimeError("Install the project dependencies to retrieve ECMWF Open Data") from error

    client = Client(
        source="ecmwf",
        model=settings.FORECAST_MODEL,
        resol=settings.FORECAST_RESOLUTION,
    )
    client.retrieve(
        type="fc",
        stream=settings.FORECAST_STREAM,
        date=initialization_time.astimezone(timezone.utc).strftime("%Y%m%d"),
        time=initialization_time.astimezone(timezone.utc).hour,
        step=settings.FORECAST_LEAD_HOURS,
        param="tp",
        target=str(target),
    )
