# Architecture

The backend is a small Django REST application. `forecasts` owns the run catalog and public API; `forecasts.pipeline` retrieves ECMWF data, validates GRIB metadata, samples a forecast grid into XYZ tiles, and coordinates the short-lived cache. Scientific transformations stay outside request views.

PostgreSQL stores run identifiers, model/cycle/product metadata, forecast times, validated forecast steps, source checksum, grid metadata, and cache expiries. The filesystem keeps multi-step GRIB bundles and derived PNG tiles under independent 24-hour defaults (`FORECAST_SOURCE_CACHE_TTL_SECONDS` and `FORECAST_TILE_CACHE_TTL_SECONDS`). Atomic file replacement plus process-level locks prevents partial cache entries and duplicate downloads for one run. Cache keys include source checksum, interval, region boundary version, tile coordinates, and processing/style versions.

The React client reads available runs and the shared India boundary, requests visible 3-hour interval tiles, and requests a location series when a user selects a point inside the country polygon. Run IDs scope tile URLs, so a newer run does not replace a previously selected run while its data remains available. Vite proxies `/api` to Django in local development.
