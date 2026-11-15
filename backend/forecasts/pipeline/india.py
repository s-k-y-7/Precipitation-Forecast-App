"""Shared India coverage boundary used for query validation, tiles, and the map UI."""

import json
import math
from functools import lru_cache
from pathlib import Path

BOUNDARY_VERSION = "india-states-simplified-v1"
BOUNDARY_PATH = Path(__file__).resolve().parent.parent / "data" / "india.geojson"


@lru_cache(maxsize=1)
def india_geojson() -> dict:
    with BOUNDARY_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def _ring_contains(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    for index, (xi, yi) in enumerate(ring):
        xj, yj = ring[index - 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def _polygons(geojson: dict):
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "Polygon":
            yield geometry["coordinates"]
        elif geometry.get("type") == "MultiPolygon":
            yield from geometry["coordinates"]


def is_inside_india(lon: float, lat: float) -> bool:
    for polygon in _polygons(india_geojson()):
        if _ring_contains((lon, lat), polygon[0]) and not any(_ring_contains((lon, lat), hole) for hole in polygon[1:]):
            return True
    return False


def india_tile_mask(z: int, x: int, y: int, size: int = 256):
    """Rasterize country polygons to a per-pixel mask in XYZ Web Mercator space."""
    from PIL import Image, ImageDraw

    scale = (1 << z) * size
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)

    def pixel(point):
        lon, lat = point[:2]
        px = (lon + 180.0) / 360.0 * scale - x * size
        sin_lat = min(max(math.sin(math.radians(lat)), -0.9999), 0.9999)
        py = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale - y * size
        return (round(px), round(py))

    for polygon in _polygons(india_geojson()):
        draw.polygon([pixel(point) for point in polygon[0]], fill=255)
        for hole in polygon[1:]:
            draw.polygon([pixel(point) for point in hole], fill=0)
    return mask


def coverage_geometry() -> dict:
    return india_geojson()
