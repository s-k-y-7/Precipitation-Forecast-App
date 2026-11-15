# India Coverage Boundary

`india.geojson` is the simplified state and union territory GeoJSON from [AbhinavSwami28/india-official-geojson](https://github.com/AbhinavSwami28/india-official-geojson), licensed under the MIT License (see `LICENSE-india-boundary.txt`). It includes the repository's stated India national boundary depiction, including its supplied Jammu and Kashmir, Ladakh, and Arunachal Pradesh extents. The upstream describes the simplification tolerance as 0.01° (about 1 km).

The checked-in file is the pinned application copy used by the API for point-in-polygon checks, tile masking, and the frontend outline. Verify it against current Survey of India publications before changing or redistributing the coverage interpretation. The source is not a live geocoder or an authority for legal boundary determinations.

Boundary GeoJSON SHA-256: `6c1448b9ec08ee9cb5a1aafd3fea30c0310b4c893ef4c7aae374274a9b501c2c`.

## City search index

`india-cities.json` is generated from GeoNames `cities5000.zip` and `admin1CodesASCII.txt`, downloaded 2026-11-15. It includes populated-place records with country code `IN` whose coordinates fall inside the bundled application boundary. The GeoNames cities5000 extract includes places with population greater than 5,000 or administrative seats at PPLA level. Names are stored as Latin/ASCII forms with Latin-script aliases; coordinates, population, and first-level administrative names provide search result context.

GeoNames data is provided under CC BY 4.0 and requires attribution: [GeoNames](https://www.geonames.org/) / [GeoNames data license and extract format](https://download.geonames.org/export/dump/readme.txt). The data is provided as-is and may be incomplete or inaccurate. The application boundary filter ensures indexed results follow the same geographic scope as point forecasts.

To regenerate the index, download the two public extracts above and run from `backend/`:

```sh
python forecasts/data/build_city_index.py /path/to/cities5000.zip /path/to/admin1CodesASCII.txt
```
