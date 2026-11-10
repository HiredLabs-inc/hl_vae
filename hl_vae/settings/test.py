"""pytest and CI. Fast and fully isolated; no network, no secrets."""

from .base import *  # noqa: F403

SECRET_KEY = "test-only-not-secret"

# The test runner creates an in-memory SQLite database; NAME is only used
# if this module is run outside the test runner.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",  # noqa: F405
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No collectstatic in tests: plain storage, so {% static %} doesn't need a
# manifest. test_manifest_build checks the real manifest build separately.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
# DEBUG is False here, so WhiteNoise would warn "No directory at: …/staticfiles/"
# on every test run. Autorefresh mode skips that check and serves from finders.
WHITENOISE_AUTOREFRESH = True
