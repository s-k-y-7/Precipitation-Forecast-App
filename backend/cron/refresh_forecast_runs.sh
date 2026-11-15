#!/bin/sh
set -eu

BACKEND_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROJECT_DIR=$(dirname -- "$BACKEND_DIR")

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi

exec "$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/manage.py" refresh_forecast_runs --lookback-hours 24
