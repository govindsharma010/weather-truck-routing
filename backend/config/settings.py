"""Django settings for the weather-aware truck routing backend."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = []  # JSON API only; the React build is served as static files

# No database: every request is computed from upstream APIs and cached in memory.
DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Static files / built React app ----
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"))
if FRONTEND_DIST.exists():
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True

# ---- CORS (only needed if the Vite dev server calls Django directly) ----
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "truck-routing",
        "OPTIONS": {"MAX_ENTRIES": 50000},
    }
}

# ---- Third-party providers ----
# "live" = OSRM / Open-Meteo / Photon+Nominatim (free, no keys). "mock" = offline synthetic data.
PROVIDERS_MODE = os.getenv("PROVIDERS_MODE", "live").lower()

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
PHOTON_URL = os.getenv("PHOTON_URL", "https://photon.komoot.io/api/")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
HTTP_USER_AGENT = os.getenv("HTTP_USER_AGENT", "weather-truck-routing/1.0 (take-home assessment)")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "25"))

# OSRM's public server only has a car profile; trucks are slower.
TRUCK_TIME_FACTOR = float(os.getenv("TRUCK_TIME_FACTOR", "1.12"))
# "sustained" = 10 m wind speed, "gusts" = hourly max gust (more conservative).
WIND_METRIC = os.getenv("WIND_METRIC", "sustained").lower()

WEATHER_CACHE_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", str(30 * 60)))
GEOCODE_CACHE_SECONDS = int(os.getenv("GEOCODE_CACHE_SECONDS", str(24 * 3600)))
ROUTE_CACHE_SECONDS = int(os.getenv("ROUTE_CACHE_SECONDS", str(60 * 60)))

# Planner limits
HEATMAP_HOURS = 48
MAX_FORECAST_DAYS_AHEAD = 15
MAX_LOAD_LB = 150_000
ALLOWED_CHECKPOINT_INTERVALS = (10, 25, 50)
DEFAULT_CHECKPOINT_INTERVAL = 25

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}