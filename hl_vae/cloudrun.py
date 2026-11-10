"""Cloud Run runtime helpers used by settings/cloud.py (DES-008, DES-003).

They live outside settings/ so they can't be mistaken for a settings module,
and so tests can call them with fakes. Nothing here runs at import time.

Cloud Run serves each service at two URLs: the legacy hashed one
(<service>-<hash>-<region code>.a.run.app) and the deterministic one
(<service>-<project number>.<region>.run.app). The legacy URL comes from
CLOUDRUN_SERVICE_URL in the app secret; deterministic_host() derives the other
from the running service's name and the project number, so both URLs work
without editing the secret.
"""

import io
import logging
import os
import urllib.request

from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

METADATA_URL = (
    "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id"
)


def _project_number():
    request = urllib.request.Request(
        METADATA_URL, headers={"Metadata-Flavor": "Google"}
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.read().decode().strip()


def deterministic_host(region):
    """Host of this service's deterministic URL, or None outside a Cloud Run service.

    K_SERVICE is set by Cloud Run services only (not jobs, which serve no
    requests). If the metadata server can't be reached, log a warning and
    return None, so jobs and local runs still start.
    """
    service = os.environ.get("K_SERVICE")
    if not service or not region:
        return None
    try:
        number = _project_number()
    except OSError:
        logger.warning(
            "Could not read the project number from the metadata server", exc_info=True
        )
        return None
    return f"{service}-{number}.{region}.run.app"


def _secret_client():
    # Imported here so dev, test and build never import the Google client.
    from google.cloud import secretmanager

    return secretmanager.SecretManagerServiceClient()


def load_app_env(env, project_id, secret_name):
    """Load the .env-format secret into os.environ. Existing values win.

    Reads versions/latest once. A missing secret, version or permission raises
    ImproperlyConfigured naming the secret path, never its contents.
    """
    from google.api_core.exceptions import GoogleAPICallError

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = _secret_client().access_secret_version(name=name)
    except GoogleAPICallError as exc:
        raise ImproperlyConfigured(
            f"Can't read secret {name} ({exc.__class__.__name__}). Check that it "
            "has an enabled version and that the runtime service account can "
            "access it."
        ) from exc
    env.read_env(io.StringIO(response.payload.data.decode("utf-8")))
