# Architecture

The backend is a small Django REST application. `forecasts` owns the run catalog and public API; `forecasts.pipeline` retrieves ECMWF data, validates GRIB metadata, samples a forecast grid into XYZ tiles, and coordinates the short-lived cache. Scientific transformations stay outside request views.

PostgreSQL stores run identifiers, model/cycle/product metadata, forecast times, source checksum, grid metadata, and cache expiries. The filesystem cache stores the source GRIB and derived PNG tiles for 24 hours. Atomic file replacement plus process-level file locks prevents partially written cache entries and duplicate downloads for the same run. Cache keys include source checksum, forecast dimensions, tile coordinates, and processing/style versions.

The React client reads available runs and requests only visible map tiles. Run IDs scope tile URLs, so arrival of a newer run does not replace a previously selected run while its data remains cached. Vite proxies `/api` to Django in local development.
