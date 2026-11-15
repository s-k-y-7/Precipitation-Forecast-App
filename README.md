# Precipitation Forecast App

Interactive India precipitation map for ECMWF IFS operational forecasts. The first layer shows total precipitation accumulated from the forecast initialization through +24 hours. Forecast values are decoded from real ECMWF Open Data; the application does not substitute mock data.

## Architecture

- `backend/` contains the Django REST API, persistent forecast-run metadata, ECMWF retrieval, GRIB validation, and XYZ map-tile rendering.
- `frontend/` contains the React/TypeScript map and the run selector.
- PostgreSQL stores forecast metadata and provenance. GRIB source files and generated precipitation tiles live in a temporary filesystem cache with a 24-hour lifetime; complete forecast grids are not stored in the database.
- Forecast data is attributed to ECMWF and distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The map uses OpenStreetMap standard raster tiles for its basemap and displays visible attribution. See the [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Local setup

Prerequisites: Python 3.12+, Node.js 20+, and Docker Compose. Copy `.env.example` to `.env`, replace the local Django secret, then load those values in the shell before running the backend.

```sh
cp .env.example .env
set -a && source .env && set +a
docker compose up -d db
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python manage.py migrate
python manage.py refresh_forecast_runs
python manage.py runserver
```

In another terminal, install and start the frontend:

```sh
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal. Refreshing forecast runs retrieves recent 00/12 UTC IFS `oper` cycles when ECMWF makes the +24-hour total-precipitation field available. Retrieval may take time and requires network access. To refresh later, rerun `python manage.py refresh_forecast_runs` from `backend/` with the virtual environment active.

## API

- `GET /api/forecast-runs/` lists runs whose source or tile cache is still available and identifies the latest run.
- `GET /api/forecast-runs/{run_id}/precipitation/v1/{z}/{x}/{y}.png` returns a run-scoped, 256-pixel XYZ tile.

The tile renderer validates GRIB parameter, units, accumulation interval, global grid spacing, and scan orientation. It converts metres to millimetres and applies a versioned precipitation color ramp. Unsupported metadata fails explicitly.

## Checks

```sh
cd backend
python manage.py test --settings=config.settings_test
cd ../frontend
npm test
npm run build
```

Backend tests use deterministic metadata and grid fixtures. The manual live-data check is to refresh runs, open the map, confirm a run appears, and inspect the tile response headers for the selected run and valid time.
