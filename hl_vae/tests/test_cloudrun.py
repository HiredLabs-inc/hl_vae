"""DES-008 / DES-003: Cloud Run helpers, with fakes instead of GCP."""

import os
import urllib.error
from types import SimpleNamespace
from unittest import mock

import environ
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from google.api_core.exceptions import PermissionDenied

from hl_vae import cloudrun


def fake_secret_client(blob=None, error=None):
    """A stand-in for SecretManagerServiceClient that returns `blob`."""
    client = mock.Mock()
    if error is not None:
        client.access_secret_version.side_effect = error
    else:
        payload = SimpleNamespace(data=blob.encode("utf-8"))
        client.access_secret_version.return_value = SimpleNamespace(payload=payload)
    return client


class DeterministicHostTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {"K_SERVICE": "vae-stage-web"})
    @mock.patch.object(cloudrun, "_project_number", return_value="123456789")
    def test_builds_host_from_service_project_and_region(self, _):
        self.assertEqual(
            cloudrun.deterministic_host("us-west1"),
            "vae-stage-web-123456789.us-west1.run.app",
        )

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.object(cloudrun, "_project_number")
    def test_none_outside_a_cloud_run_service(self, project_number):
        self.assertIsNone(cloudrun.deterministic_host("us-west1"))
        project_number.assert_not_called()

    @mock.patch.dict(os.environ, {"K_SERVICE": "vae-stage-web"})
    @mock.patch.object(
        cloudrun, "_project_number", side_effect=urllib.error.URLError("timed out")
    )
    def test_none_when_metadata_server_unreachable(self, _):
        with self.assertLogs("hl_vae.cloudrun", "WARNING"):
            self.assertIsNone(cloudrun.deterministic_host("us-west1"))


class LoadAppEnvTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"VAE_TEST_KEEP": "from-env"})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("VAE_TEST_NEW", None)

    def _load(self, client):
        with mock.patch.object(cloudrun, "_secret_client", return_value=client):
            cloudrun.load_app_env(environ.Env(), "proj", "app-env")

    def test_loads_lines_and_existing_values_win(self):
        client = fake_secret_client(
            "# comment\nVAE_TEST_NEW='a b#c'\nVAE_TEST_KEEP=from-secret\n"
        )
        self._load(client)
        client.access_secret_version.assert_called_once_with(
            name="projects/proj/secrets/app-env/versions/latest"
        )
        self.assertEqual(os.environ["VAE_TEST_NEW"], "a b#c")
        self.assertEqual(os.environ["VAE_TEST_KEEP"], "from-env")

    def test_api_error_names_the_secret_not_the_payload(self):
        client = fake_secret_client(error=PermissionDenied("denied"))
        with self.assertRaises(ImproperlyConfigured) as cm:
            self._load(client)
        message = str(cm.exception)
        self.assertIn("projects/proj/secrets/app-env/versions/latest", message)
        self.assertIn("PermissionDenied", message)
