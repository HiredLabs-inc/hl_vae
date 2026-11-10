"""Settings for every Cloud Run environment (DES-008, DES-003).

Not used directly: stage.py (and prod.py, once prod exists) import it.

Cloud Run sets three plain env vars: DJANGO_SETTINGS_MODULE, GCP_PROJECT_ID and
GCP_SECRETS_NAME. Everything else is read from the .env-format Secret Manager
secret that GCP_SECRETS_NAME names, and values already in the environment win.
A missing required value fails at import with "Set the NAME environment
variable", so a bad revision never becomes ready.

Security switches (DEBUG, cookies, HSTS, SSL) are code, not config: editing the
secret can't turn them off. Static settings are inherited from base.py and
must not be overridden here (DES-006).
"""

from urllib.parse import urlparse

from hl_vae.cloudrun import deterministic_host, load_app_env

from .base import *  # noqa: F403

DEBUG = False

load_app_env(env, env("GCP_PROJECT_ID"), env("GCP_SECRETS_NAME"))

SECRET_KEY = env("DJANGO_SECRET_KEY")
# Old keys still accepted while a rotation settles (see infra/README.md).
SECRET_KEY_FALLBACKS = [
    k for k in env.list("DJANGO_SECRET_KEY_FALLBACKS", default=[]) if k
]

# Hosts: any custom domains in ALLOWED_HOSTS (empty on stage), plus both
# Cloud Run URLs (see hl_vae/cloudrun.py).
ALLOWED_HOSTS = [h for h in env.list("ALLOWED_HOSTS", default=[]) if h]
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

CLOUDRUN_SERVICE_URL = env("CLOUDRUN_SERVICE_URL", default="").rstrip("/")
if CLOUDRUN_SERVICE_URL:
    ALLOWED_HOSTS.append(urlparse(CLOUDRUN_SERVICE_URL).netloc)
    CSRF_TRUSTED_ORIGINS.append(CLOUDRUN_SERVICE_URL)

GCP_REGION = env("GCP_REGION")
_host = deterministic_host(GCP_REGION)
if _host and _host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

# Cloud SQL on private IP over Direct VPC egress. Reuse connections for a
# minute and check one before reusing it, so a closed connection is replaced
# instead of failing the request. db-f1-micro allows about 25 connections; one
# instance with 8 gunicorn threads holds at most 8.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("GCP_CLOUDSQL_DB_NAME"),
        "USER": env("GCP_CLOUDSQL_USER"),
        "PASSWORD": env("GCP_CLOUDSQL_PASSWORD"),
        "HOST": env("GCP_CLOUDSQL_PRIVATE_IP"),
        "PORT": 5432,
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

# Cloud Run terminates TLS and forwards plain HTTP with X-Forwarded-Proto;
# trusting the header stops a redirect loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS for a year. Not preloaded: preload is hard to undo once browsers ship it.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
# check --deploy warns that preload is off (W021). That's the decision above,
# so silence it and keep `check --deploy` free of warnings.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Everything to stdout/stderr; Cloud Run sends it to Cloud Logging.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
