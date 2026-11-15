"""Django configuration for local development and the first forecast slice."""

import os
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "forecasts.apps.ForecastsConfig",
]

MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "precipitation"),
        "USER": os.environ.get("DB_USER", "precipitation"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "precipitation"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5433"),
        "CONN_MAX_AGE": 60,
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FORECAST_MODEL = os.environ.get("FORECAST_MODEL", "ifs")
FORECAST_STREAM = os.environ.get("FORECAST_STREAM", "oper")
FORECAST_RESOLUTION = os.environ.get("FORECAST_RESOLUTION", "0p25")
FORECAST_LEAD_HOURS = int(os.environ.get("FORECAST_LEAD_HOURS", "24"))
FORECAST_CACHE_TTL_SECONDS = int(os.environ.get("FORECAST_CACHE_TTL_SECONDS", str(24 * 60 * 60)))
FORECAST_CACHE_DIR = os.environ.get(
    "FORECAST_CACHE_DIR", str(Path(tempfile.gettempdir()) / "precipitation-forecast-cache")
)
