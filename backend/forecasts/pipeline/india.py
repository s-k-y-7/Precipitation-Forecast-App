"""Shared India coverage boundary used for query validation, tiles, and the map UI."""

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

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


def _ring_contains_points(longitudes: np.ndarray, latitudes: np.ndarray, ring: list[list[float]]) -> np.ndarray:
    inside = np.zeros(longitudes.shape, dtype=bool)
    previous_lon, previous_lat = ring[-1]
    for longitude, latitude in ring:
        if latitude != previous_lat:
            crosses = (latitude > latitudes) != (previous_lat > latitudes)
            intersection = (previous_lon - longitude) * (latitudes - latitude) / (previous_lat - latitude) + longitude
            inside ^= crosses & (longitudes < intersection)
        previous_lon, previous_lat = longitude, latitude
    return inside


@lru_cache(maxsize=4)
def india_grid_mask(grid) -> np.ndarray:
    """Mask grid-cell centers inside the bundled India polygon, cached by grid geometry."""
    polygons = list(_polygons(india_geojson()))
    all_points = [point for polygon in polygons for ring in polygon for point in ring]
    west = min(point[0] for point in all_points)
    east = max(point[0] for point in all_points)
    south = min(point[1] for point in all_points)
    north = max(point[1] for point in all_points)

    longitude_axis = (grid.first_longitude + np.arange(grid.width) * grid.longitude_increment + 180.0) % 360.0 - 180.0
    latitude_axis = grid.first_latitude - np.arange(grid.height) * grid.latitude_increment
    columns = np.flatnonzero((longitude_axis >= west) & (longitude_axis <= east))
    rows = np.flatnonzero((latitude_axis >= south) & (latitude_axis <= north))
    result = np.zeros((grid.height, grid.width), dtype=bool)
    if not len(columns) or not len(rows):
        return result

    longitudes, latitudes = np.meshgrid(longitude_axis[columns], latitude_axis[rows])
    points_lon, points_lat = longitudes.ravel(), latitudes.ravel()
    inside = np.zeros(points_lon.shape, dtype=bool)
    for polygon in polygons:
        outer = polygon[0]
        polygon_west = min(point[0] for point in outer)
        polygon_east = max(point[0] for point in outer)
        polygon_south = min(point[1] for point in outer)
        polygon_north = max(point[1] for point in outer)
        candidate = np.flatnonzero(
            (points_lon >= polygon_west) & (points_lon <= polygon_east)
            & (points_lat >= polygon_south) & (points_lat <= polygon_north)
        )
        if not len(candidate):
            continue
        in_polygon = _ring_contains_points(points_lon[candidate], points_lat[candidate], outer)
        for hole in polygon[1:]:
            in_polygon &= ~_ring_contains_points(points_lon[candidate], points_lat[candidate], hole)
        inside[candidate] |= in_polygon

    result[np.ix_(rows, columns)] = inside.reshape((len(rows), len(columns)))
    return result


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
