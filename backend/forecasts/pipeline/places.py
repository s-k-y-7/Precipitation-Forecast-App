"""Search the bundled India-only GeoNames place index."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path


PLACE_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "india-cities.json"
RESULT_LIMIT = 10


@lru_cache(maxsize=1)
def _load_places() -> tuple[dict, ...]:
    with PLACE_INDEX_PATH.open(encoding="utf-8") as source:
        return tuple(json.load(source))


@lru_cache(maxsize=1)
def _search_index() -> tuple[tuple[dict, tuple[str, ...], tuple[str, ...]], ...]:
    entries = []
    for place in _load_places():
        names = {place["name"], *place.get("aliases", [])}
        normalized = tuple({key for name in names if (key := normalize_place_name(name))})
        entries.append((place, normalized, tuple(name.replace(" ", "") for name in normalized)))
    return tuple(entries)


def normalize_place_name(value: str) -> str:
    """Fold accents and treat punctuation and whitespace as equivalent separators."""
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    characters = []
    for character in decomposed:
        if unicodedata.category(character).startswith("M"):
            continue
        characters.append(character if character.isalnum() else " ")
    return " ".join("".join(characters).split())


def search_places(query: str, places=None) -> list[dict]:
    normalized_query = normalize_place_name(query)
    compact_query = normalized_query.replace(" ", "")
    if len(compact_query) < 2:
        return []

    if places is None:
        candidates = _search_index()
    else:
        candidates = []
        for place in places:
            names = {place["name"], *place.get("aliases", [])}
            normalized = tuple({key for name in names if (key := normalize_place_name(name))})
            candidates.append((place, normalized, tuple(name.replace(" ", "") for name in normalized)))
    matches = []
    for place, normalized_names, compact_names in candidates:
        if normalized_query in normalized_names or compact_query in compact_names:
            rank = 0
        elif any(name.startswith(normalized_query) for name in normalized_names) or any(
            name.startswith(compact_query) for name in compact_names
        ):
            rank = 1
        elif any(normalized_query in name for name in normalized_names) or any(
            compact_query in name for name in compact_names
        ):
            rank = 2
        else:
            continue

        matches.append((
            rank,
            -int(place.get("population", 0)),
            place["name"].casefold(),
            int(place["id"]),
            place,
        ))

    matches.sort(key=lambda item: item[:4])
    return [
        {
            "id": place["id"],
            "name": place["name"],
            "admin1": place.get("admin1", ""),
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "population": place.get("population", 0),
        }
        for *_rank, place in matches[:RESULT_LIMIT]
    ]
