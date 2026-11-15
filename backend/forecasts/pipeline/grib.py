"""ecCodes access isolated from Django and map rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from forecasts.pipeline.grid import GridMetadata, validate_forecast_metadata


@dataclass
class PrecipitationField:
    values: np.ndarray
    grid: GridMetadata
    metadata: dict


class ForecastFieldError(ValueError):
    pass


GRIB_KEYS = (
    "shortName", "units", "stepType", "typeOfLevel", "startStep", "endStep", "dataDate", "dataTime",
    "validityDate", "validityTime", "gridType", "Ni", "Nj", "packingError",
    "latitudeOfFirstGridPointInDegrees", "longitudeOfFirstGridPointInDegrees",
    "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees", "iScansNegatively",
    "jScansPositively", "jPointsAreConsecutive", "alternativeRowScanning", "missingValue",
)


def read_precipitation_field(
    path: Path, lead_hours: int, expected_initialization: datetime | None = None
) -> PrecipitationField:
    try:
        import eccodes
    except ImportError as error:
        raise ForecastFieldError("Install the project dependencies to decode GRIB data") from error

    with path.open("rb") as source:
        handle = eccodes.codes_grib_new_from_file(source)
        if handle is None:
            raise ForecastFieldError("No GRIB message found in ECMWF source")
        try:
            metadata = {}
            for key in GRIB_KEYS:
                try:
                    metadata[key] = eccodes.codes_get(handle, key)
                except eccodes.CodesInternalError:
                    if key in {"missingValue"}:
                        continue
                    raise ForecastFieldError(f"Required GRIB metadata is missing: {key}")
            grid = validate_forecast_metadata(metadata, lead_hours)
            values = np.array(eccodes.codes_get_values(handle), dtype=np.float64, copy=True)
        except ForecastFieldError:
            raise
        except Exception as error:
            raise ForecastFieldError(f"Could not decode ECMWF GRIB field: {error}") from error
        finally:
            eccodes.codes_release(handle)

    if values.size != grid.width * grid.height:
        raise ForecastFieldError("GRIB values do not match the declared grid shape")
    if expected_initialization is not None:
        initialization = expected_initialization.astimezone(timezone.utc)
        valid_time = initialization + timedelta(hours=lead_hours)
        expected_times = {
            "dataDate": int(initialization.strftime("%Y%m%d")),
            "dataTime": initialization.hour * 100,
            "validityDate": int(valid_time.strftime("%Y%m%d")),
            "validityTime": valid_time.hour * 100,
        }
        for key, expected in expected_times.items():
            if int(metadata[key]) != expected:
                raise ForecastFieldError(f"GRIB {key} does not match the selected forecast run")
    missing = metadata.get("missingValue")
    if missing is not None:
        values[np.isclose(values, float(missing), rtol=0.0, atol=1e-10)] = np.nan
    return PrecipitationField(values=values, grid=grid, metadata=metadata)


def read_precipitation_bundle(
    path: Path, expected_steps: tuple[int, ...], expected_initialization: datetime
) -> dict[int, PrecipitationField]:
    """Decode and validate every message in a cumulative precipitation bundle."""
    try:
        import eccodes
    except ImportError as error:
        raise ForecastFieldError("Install the project dependencies to decode GRIB data") from error

    fields: dict[int, PrecipitationField] = {}
    try:
        with path.open("rb") as source:
            while handle := eccodes.codes_grib_new_from_file(source):
                try:
                    metadata = {}
                    for key in GRIB_KEYS:
                        try:
                            metadata[key] = eccodes.codes_get(handle, key)
                        except eccodes.CodesInternalError:
                            if key == "missingValue":
                                continue
                            raise ForecastFieldError(f"Required GRIB metadata is missing: {key}")
                    step = int(metadata["endStep"])
                    if step not in expected_steps or step in fields:
                        raise ForecastFieldError(f"Unexpected or duplicate forecast step {step}h")
                    grid = validate_forecast_metadata(metadata, step)
                    initialization = expected_initialization.astimezone(timezone.utc)
                    valid_time = initialization + timedelta(hours=step)
                    expected_times = {
                        "dataDate": int(initialization.strftime("%Y%m%d")),
                        "dataTime": initialization.hour * 100,
                        "validityDate": int(valid_time.strftime("%Y%m%d")),
                        "validityTime": valid_time.hour * 100,
                    }
                    for key, expected in expected_times.items():
                        if int(metadata[key]) != expected:
                            raise ForecastFieldError(f"GRIB {key} does not match forecast step {step}h")
                    values = np.array(eccodes.codes_get_values(handle), dtype=np.float64, copy=True)
                    if values.size != grid.width * grid.height:
                        raise ForecastFieldError("GRIB values do not match the declared grid shape")
                    missing = metadata.get("missingValue")
                    if missing is not None:
                        values[np.isclose(values, float(missing), rtol=0.0, atol=1e-10)] = np.nan
                    fields[step] = PrecipitationField(values, grid, metadata)
                finally:
                    eccodes.codes_release(handle)
    except ForecastFieldError:
        raise
    except Exception as error:
        raise ForecastFieldError(f"Could not decode ECMWF GRIB bundle: {error}") from error
    if tuple(sorted(fields)) != tuple(expected_steps):
        missing = sorted(set(expected_steps) - set(fields))
        raise ForecastFieldError(f"ECMWF bundle is missing forecast steps: {missing}")
    first = fields[expected_steps[0]].grid
    for field in fields.values():
        if field.grid != first:
            raise ForecastFieldError("Forecast steps do not share identical grid metadata")
    return fields
