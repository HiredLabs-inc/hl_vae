"""Local development. Never used on a hosted environment."""

import os

from .base import *  # noqa: F403

DEBUG = True

# Dev-only key. The "django-insecure-" prefix makes `check --deploy` flag it
# if this module is ever used somewhere it shouldn't be.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-p7+l#%wo3n^wq=y$2)3ki)dhr50x&t^lnlgwk3bm(dy*3lu7-f",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
