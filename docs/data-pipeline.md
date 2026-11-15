# Forecast Data Pipeline

`refresh_forecast_runs` checks recent 00 and 12 UTC IFS operational runs through the ECMWF Open Data client and retrieves total precipitation (`tp`) at steps +3, +6, …, +24 on the 0.25-degree grid. It requires exactly one GRIB message for every step and validates each message's parameter, units, accumulation interval, initialization, valid time, and grid before saving the catalog and whole-bundle SHA-256 checksum. Old single-step cache files use a separate namespace and cannot be mistaken for a valid bundle.

When a tile or point series is requested, the backend reuses the staged bundle or downloads it once under a run-level file lock. Source bundles expire after `FORECAST_SOURCE_CACHE_TTL_SECONDS`; generated tiles expire after `FORECAST_TILE_CACHE_TTL_SECONDS`. Reads never extend either file's lifetime. The API lists only runs with a live source or tile cache and a fully validated step catalog.

V2 displays the previous 3-hour interval: +3h is differenced from zero, and subsequent fields are differenced from the previous cumulative field. Differences within the sum of both fields' reported packing errors are zero; more negative values are unavailable. V1 retains cumulative +24h semantics. One bundled India polygon is shared by point validation, tile masking, and map feedback; outside points are rejected without geocoding.
