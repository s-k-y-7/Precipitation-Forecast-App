"""Build the checked-in India city index from the GeoNames public extracts."""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path

from forecasts.pipeline.india import is_inside_india


def read_admin_names(path: Path) -> dict[str, str]:
    names = {}
    with path.open(encoding="utf-8") as source:
        for row in csv.reader(source, delimiter="\t"):
            if len(row) >= 2:
                names[row[0]] = row[2] if len(row) > 2 and row[2] else row[1]
    return names


def build_index(city_archive: Path, admin_file: Path) -> list[dict]:
    admin_names = read_admin_names(admin_file)
    places = []
    with zipfile.ZipFile(city_archive) as archive:
        member = next(name for name in archive.namelist() if name.endswith(".txt"))
        with archive.open(member) as source:
            for raw_line in source:
                columns = raw_line.decode("utf-8").rstrip("\r\n").split("\t")
                if len(columns) < 19 or columns[8] != "IN" or columns[6] != "P":
                    continue

                population = int(columns[14] or 0)
                if population <= 5000 and columns[7] != "PPLA":
                    continue
                latitude, longitude = float(columns[4]), float(columns[5])
                if not is_inside_india(longitude, latitude):
                    continue

                aliases = {columns[2].strip()}
                if columns[1].isascii():
                    aliases.add(columns[1].strip())
                aliases.update(
                    alias.strip()
                    for alias in columns[3].split(",")
                    if alias.strip() and alias.strip().isascii()
                )
                aliases.discard("")
                admin_key = f"IN.{columns[10]}" if columns[10] else ""
                places.append({
                    "id": int(columns[0]),
                    "name": columns[2].strip() or columns[1].strip(),
                    "aliases": sorted(aliases, key=str.casefold),
                    "latitude": latitude,
                    "longitude": longitude,
                    "population": population,
                    "admin1": admin_names.get(admin_key, ""),
                })

    places.sort(key=lambda place: (place["name"].casefold(), place["id"]))
    return places


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cities5000_zip", type=Path)
    parser.add_argument("admin1_codes", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("india-cities.json"),
    )
    arguments = parser.parse_args()
    places = build_index(arguments.cities5000_zip, arguments.admin1_codes)
    arguments.output.write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(places)} India places to {arguments.output}")


if __name__ == "__main__":
    main()
