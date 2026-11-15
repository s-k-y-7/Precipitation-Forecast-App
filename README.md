# Precipitation Forecast App

Interactive India precipitation map for ECMWF IFS operational forecasts. Select a 3-hour interval through +24h, click a location inside India, and inspect the real forecast interval series at the nearest ECMWF grid point. Forecast values come from ECMWF Open Data; the application does not substitute mock forecast data.

## Architecture

- `backend/` contains the Django REST API, persistent forecast-run metadata, ECMWF retrieval, GRIB validation, and XYZ map-tile rendering.
- `frontend/` contains the React/TypeScript map and the run selector.
- PostgreSQL stores forecast metadata and provenance. GRIB source bundles and generated tiles live in separate temporary filesystem caches. `FORECAST_SOURCE_CACHE_TTL_SECONDS` and `FORECAST_TILE_CACHE_TTL_SECONDS` each default to 24 hours; cache hits do not extend either lifetime. Complete forecast grids are not stored in the database.
- The map outline, point-query boundary, and tile mask use the same bundled simplified state geometry. See `backend/forecasts/data/README.md` for its source and license.
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

Open the Vite URL shown in the terminal. Refreshing forecast runs retrieves recent 00/12 UTC IFS `oper` cycles when ECMWF makes all eight steps (+3 through +24h) available. Retrieval may take time and requires network access. Older catalog rows remain hidden until refresh validates a complete bundle. To refresh later, rerun `python manage.py refresh_forecast_runs` from `backend/` with the virtual environment active.

### Automatic forecast updates

For deployment, install the host's existing cron scheduler using [`backend/cron/forecast-refresh.crontab.example`](backend/cron/forecast-refresh.crontab.example). Replace `/srv/precipitation-forecast` with the deployed project path and ensure the cron user can write the configured log file. The entry runs the existing refresh command every three hours in UTC; it sources the project `.env` and uses the backend virtual environment. No scheduler service or Python dependency is added.

The command skips fully validated runs while their source or tile cache is still within its configured lifetime. Failed or unavailable cycles are logged and do not create partial run records; later cron executions recheck the recent 24-hour window. The frontend refreshes the run catalog every five minutes and keeps the user's selected run if it remains available.

For the single-VM Oracle Cloud deployment setup, see [`deploy/README.md`](deploy/README.md). It covers production serving, persistent storage, TLS, environment configuration, and the existing scheduled refresh.

## API

- `GET /api/forecast-runs/` lists runs whose source or tile cache is still available and identifies the latest run.
- `GET /api/places/search/?q={query}` searches the bundled India-only city and town index (English names and Latin aliases; at most 10 results).
- `GET /api/forecast-runs/{run_id}/precipitation/v1/{z}/{x}/{y}.png` returns a run-scoped, 256-pixel XYZ tile.
- `GET /api/forecast-runs/{run_id}/precipitation/v2/{step}/{z}/{x}/{y}.png` returns the 3-hour interval tile ending at `step`.
- `GET /api/forecast-runs/{run_id}/precipitation/point/?lat={lat}&lon={lon}` returns eight interval values at the nearest ECMWF grid point; coordinates outside India are rejected.
- `GET /api/coverage/india/` returns the geometry used for server validation, tile masking, and the frontend outline.

The pipeline validates every GRIB message's parameter, actual step, initialization and valid time, grid, and scan orientation. It differences cumulative precipitation into 3-hour amounts, treats differences within reported GRIB packing precision as zero, and marks materially negative differences unavailable. The v1 cumulative tile remains available.

## Checks

```sh
cd backend
python manage.py test --settings=config.settings_test
cd ../frontend
npm test
npm run build
```

Backend tests use deterministic metadata and grid fixtures. The manual live-data check is to refresh runs, open the map, confirm a run appears, and inspect the tile response headers for the selected run and valid time.
