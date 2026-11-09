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
