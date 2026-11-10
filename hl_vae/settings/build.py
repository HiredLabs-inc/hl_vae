"""Settings used only for `collectstatic` during `docker build`.

No secrets, credentials or database. Static settings are inherited from
base.py, so the build writes exactly what cloud.py serves. Don't override
them here.
"""

from .base import *  # noqa: F403

SECRET_KEY = "build-only-not-secret"
