"""Metadata validation and regular-latitude/longitude map tile rendering."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image


class GridMetadataError(ValueError):
    """Raised when a GRIB field is not the forecast product this app expects."""


@dataclass(frozen=True)
class GridMetadata:
    width: int
    height: int
    first_longitude: float
    first_latitude: float
    longitude_increment: float
    latitude_increment: float
    precipitation_to_mm: float


INDIA_BOUNDS = (68.0, 6.0, 97.5, 37.5)  # west, south, east, north
TILE_SIZE = 256
PROCESSING_VERSION = "interval-v2-india-mask-v1"
STYLE_VERSION = "rain-mm-3h-v2"


def _number(metadata: dict, key: str) -> float:
    try:
        return float(metadata[key])
    except (KeyError, TypeError, ValueError) as error:
        raise GridMetadataError(f"Missing or invalid GRIB metadata: {key}") from error


def validate_forecast_metadata(metadata: dict, lead_hours: int) -> GridMetadata:
    """Validate the assumptions required by the first IFS precipitation layer."""
    expected = {
        "shortName": "tp",
        "units": "m",
        "stepType": "accum",
        "gridType": "regular_ll",
        "typeOfLevel": "surface",
    }
    for key, value in expected.items():
        if str(metadata.get(key, "")) != value:
            raise GridMetadataError(f"Expected GRIB {key}={value!r}; got {metadata.get(key)!r}")

    if int(_number(metadata, "startStep")) != 0:
        raise GridMetadataError("Expected total precipitation accumulated from forecast step 0")
    if int(_number(metadata, "endStep")) != lead_hours:
        raise GridMetadataError(f"Expected forecast step {lead_hours}h")

    width = int(_number(metadata, "Ni"))
    height = int(_number(metadata, "Nj"))
    lon0 = _number(metadata, "longitudeOfFirstGridPointInDegrees")
    lat0 = _number(metadata, "latitudeOfFirstGridPointInDegrees")
    di = _number(metadata, "iDirectionIncrementInDegrees")
    dj = _number(metadata, "jDirectionIncrementInDegrees")

    if width < 2 or height < 2 or not math.isclose(width * di, 360.0, abs_tol=0.26):
        raise GridMetadataError("Expected a global regular longitude/latitude grid")
    if not math.isclose(lat0, 90.0, abs_tol=1e-5) or not 0.0 <= lon0 < 360.0:
        raise GridMetadataError("Unsupported global grid origin")
    if not math.isclose(di, dj, rel_tol=1e-5) or not math.isclose(height * dj, 180.0 + dj, abs_tol=0.26):
        raise GridMetadataError("Unsupported global grid spacing")
    for key in ("iScansNegatively", "jScansPositively", "jPointsAreConsecutive", "alternativeRowScanning"):
        if int(_number(metadata, key)) != 0:
            raise GridMetadataError(f"Unsupported GRIB scan orientation: {key}")

    return GridMetadata(width, height, lon0, lat0, di, dj, 1000.0)


def cache_key(dimensions: dict) -> str:
    """Return a stable digest for all source, tile, and processing dimensions."""
    canonical = json.dumps(dimensions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sample_xyz_tile(
    values: np.ndarray,
    grid: GridMetadata,
    z: int,
    x: int,
    y: int,
    bounds: tuple[float, float, float, float] = INDIA_BOUNDS,
    input_to_mm: float | None = None,
) -> np.ndarray:
    """Nearest-neighbour sample a forecast grid into an XYZ Web Mercator tile."""
    if not 0 <= z <= 10:
        raise ValueError("Tile zoom must be between 0 and 10")
    tile_count = 1 << z
    if not 0 <= x < tile_count or not 0 <= y < tile_count:
        raise ValueError("Tile coordinates are outside this zoom level")
    if values.size != grid.width * grid.height:
        raise GridMetadataError("GRIB value count does not match grid dimensions")

    source = np.asarray(values, dtype=np.float64).reshape((grid.height, grid.width))
    pixel = np.arange(TILE_SIZE, dtype=np.float64) + 0.5
    world_x = (x * TILE_SIZE + pixel) / (tile_count * TILE_SIZE)
    world_y = (y * TILE_SIZE + pixel) / (tile_count * TILE_SIZE)
    longitudes = world_x * 360.0 - 180.0
    latitudes = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * world_y))))
    lon_mesh, lat_mesh = np.meshgrid(longitudes, latitudes)
    west, south, east, north = bounds
    inside = (lon_mesh >= west) & (lon_mesh <= east) & (lat_mesh >= south) & (lat_mesh <= north)

    # ECMWF may rotate the first longitude (for example, 180E); honor the GRIB origin.
    relative_longitude = np.mod(np.mod(lon_mesh, 360.0) - grid.first_longitude, 360.0)
    column = np.rint(relative_longitude / grid.longitude_increment).astype(np.int64) % grid.width
    row = np.rint((grid.first_latitude - lat_mesh) / grid.latitude_increment).astype(np.int64)
    safe_row = np.clip(row, 0, grid.height - 1)
    sampled = source[safe_row, column] * (grid.precipitation_to_mm if input_to_mm is None else input_to_mm)
    from forecasts.pipeline.india import india_tile_mask

    india_mask = np.asarray(india_tile_mask(z, x, y), dtype=np.uint8) > 0
    sampled = np.where(inside & india_mask & np.isfinite(sampled), sampled, np.nan)
    return sampled


def render_precipitation_tile(values_mm: np.ndarray) -> bytes:
    """Render a transparent PNG with a fixed, versioned precipitation ramp."""
    thresholds = (0.1, 1.0, 2.5, 5.0, 10.0, 20.0, 50.0, 100.0)
    colors = np.array(
        [
            (187, 222, 251, 180),
            (100, 181, 246, 190),
            (30, 136, 229, 205),
            (0, 150, 136, 215),
            (124, 179, 66, 225),
            (253, 216, 53, 230),
            (251, 140, 0, 235),
            (229, 57, 53, 240),
        ],
        dtype=np.uint8,
    )
    valid = np.isfinite(values_mm) & (values_mm >= thresholds[0])
    rgba = np.zeros((*values_mm.shape, 4), dtype=np.uint8)
    classes = np.digitize(np.nan_to_num(values_mm, nan=-1.0), thresholds[1:])
    rgba[valid] = colors[classes[valid]]
    image = Image.fromarray(rgba, mode="RGBA")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def interval_precipitation(previous: np.ndarray | None, current: np.ndarray, previous_error_m: float = 0.0,
                           current_error_m: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Difference cumulative fields and zero values within their GRIB packing precision."""
    cumulative = np.asarray(current, dtype=np.float64)
    before = np.zeros_like(cumulative) if previous is None else np.asarray(previous, dtype=np.float64)
    delta = (cumulative - before) * 1000.0
    tolerance_mm = (abs(previous_error_m) + abs(current_error_m)) * 1000.0
    valid = np.isfinite(delta) & (delta >= -tolerance_mm)
    below_precision = valid & (np.abs(delta) <= tolerance_mm)
    delta[below_precision] = 0.0
    delta[~valid] = np.nan
    return delta, valid


def summarize_interval_grid(previous: np.ndarray | None, current: np.ndarray, grid: GridMetadata,
                            previous_error_m: float = 0.0, current_error_m: float = 0.0) -> dict:
    """Summarize the maximum validated interval value at India grid-cell centers."""
    from forecasts.pipeline.india import india_grid_mask

    amount_mm, valid = interval_precipitation(
        previous, current, previous_error_m=previous_error_m, current_error_m=current_error_m
    )
    valid_inside = np.asarray(valid, dtype=bool).reshape((grid.height, grid.width)) & india_grid_mask(grid)
    valid_indices = np.flatnonzero(valid_inside.ravel())
    if not len(valid_indices):
        return {"max_precipitation_mm": None, "max_grid_point": None, "valid_grid_points": 0}

    flattened_amounts = np.asarray(amount_mm, dtype=np.float64).reshape(-1)
    maximum_index = valid_indices[np.argmax(flattened_amounts[valid_indices])]
    row, column = divmod(int(maximum_index), grid.width)
    return {
        "max_precipitation_mm": float(flattened_amounts[maximum_index]),
        "max_grid_point": {
            "lat": grid.first_latitude - row * grid.latitude_increment,
            "lon": (grid.first_longitude + column * grid.longitude_increment + 180.0) % 360.0 - 180.0,
        },
        "valid_grid_points": int(len(valid_indices)),
    }
