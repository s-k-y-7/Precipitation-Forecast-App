# Forecast Data Pipeline

`refresh_forecast_runs` checks recent 00 and 12 UTC IFS operational runs through the ECMWF Open Data client and retrieves only total precipitation (`tp`) at step 24 on the 0.25-degree grid. It validates the downloaded GRIB field before saving its catalog metadata and SHA-256 checksum.

When a requested map tile is not cached, the backend reuses the run's staged GRIB file or downloads it once under a run-level file lock. It verifies accumulated precipitation from step 0 to step 24, validates global regular latitude/longitude grid metadata and scan order, converts metres to millimetres, samples the India bounding box into a 256×256 Web Mercator tile using nearest-neighbour sampling, and encodes the configured PNG ramp. Source files and tiles expire after 24 hours. Older run metadata remains in PostgreSQL, but the API lists only runs with a live source or tile cache.

No temporal differencing is performed: the displayed `tp` field is the accumulated forecast total at +24 hours. Unexpected parameter, units, interval, grid, or orientation produces an explicit failure rather than a plausible-looking map.
