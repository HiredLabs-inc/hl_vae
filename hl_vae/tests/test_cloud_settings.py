"""DES-008 / DES-003: cloud.py and stage.py with a fake secret, and build.py."""

import importlib
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from hl_vae import cloudrun

from .test_cloudrun import fake_secret_client

# What Cloud Run sets as plain env vars (Terraform).
CLOUD_RUN_ENV = {
    "GCP_PROJECT_ID": "hl-vae-stage",
    "GCP_SECRETS_NAME": "vae-stage-app-env",
}

# The vae-stage-app-env blob, as in the DES-008 app contract.
SECRET = {
    "DJANGO_SECRET_KEY": "from-secret",
    "GCP_REGION": "us-west1",
    "GCP_CLOUDSQL_DB_NAME": "vae",
    "GCP_CLOUDSQL_USER": "vae",
    "GCP_CLOUDSQL_PASSWORD": "pw",
    "GCP_CLOUDSQL_PRIVATE_IP": "10.0.32.9",
    "CLOUDRUN_SERVICE_URL": "https://vae-stage-web-abc123-uw.a.run.app/",
    "ALLOWED_HOSTS": "",
}

# Every variable the cloud settings read, cleared before each load so the
# developer's shell can't change the result.
CATALOGUE = {
    *SECRET,
    *CLOUD_RUN_ENV,
    "DJANGO_SECRET_KEY_FALLBACKS",
    "K_SERVICE",
}


def blob(values):
    return "".join(f"{k}={v}\n" for k, v in values.items())


class CloudSettingsTests(SimpleTestCase):
    def _load(self, *, environ_vars=None, secret=None, module="cloud"):
        """Import hl_vae.settings.<module> fresh against a fake secret.

        Returns (module, fake client, fake _project_number). Importing the
        module doesn't change the active Django settings.
        """
        keep = {k: v for k, v in os.environ.items() if k not in CATALOGUE}
        env = {**keep, **CLOUD_RUN_ENV, **(environ_vars or {})}
        client = fake_secret_client(blob(SECRET if secret is None else secret))
        patches = [
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(cloudrun, "_secret_client", return_value=client),
            mock.patch.object(cloudrun, "_project_number", return_value="123456789"),
        ]
        mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        mod = importlib.reload(importlib.import_module("hl_vae.settings.cloud"))
        if module != "cloud":
            mod = importlib.reload(importlib.import_module(f"hl_vae.settings.{module}"))
        return mod, client, mocks[2]

    def test_web_service(self):
        cloud, client, _ = self._load(environ_vars={"K_SERVICE": "vae-stage-web"})
        client.access_secret_version.assert_called_once_with(
            name="projects/hl-vae-stage/secrets/vae-stage-app-env/versions/latest"
        )
        self.assertIs(cloud.DEBUG, False)
        self.assertEqual(cloud.SECRET_KEY, "from-secret")
        self.assertEqual(cloud.SECRET_KEY_FALLBACKS, [])
        self.assertEqual(
            cloud.ALLOWED_HOSTS,
            [
                "vae-stage-web-abc123-uw.a.run.app",
                "vae-stage-web-123456789.us-west1.run.app",
            ],
        )
        self.assertEqual(
            cloud.CSRF_TRUSTED_ORIGINS,
            [
                "https://vae-stage-web-abc123-uw.a.run.app",
                "https://vae-stage-web-123456789.us-west1.run.app",
            ],
        )
        db = cloud.DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(
            (db["NAME"], db["USER"], db["PASSWORD"], db["HOST"], db["PORT"]),
            ("vae", "vae", "pw", "10.0.32.9", 5432),
        )
        self.assertEqual((db["CONN_MAX_AGE"], db["CONN_HEALTH_CHECKS"]), (60, True))

    def test_security_switches(self):
        cloud, _, _ = self._load()
        self.assertIs(cloud.SECURE_SSL_REDIRECT, True)
        self.assertEqual(
            cloud.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https")
        )
        self.assertIs(cloud.SESSION_COOKIE_SECURE, True)
        self.assertIs(cloud.CSRF_COOKIE_SECURE, True)
        self.assertEqual(cloud.SECURE_HSTS_SECONDS, 31536000)
        self.assertEqual(cloud.SILENCED_SYSTEM_CHECKS, ["security.W021"])

    def test_secret_cannot_turn_debug_on(self):
        cloud, _, _ = self._load(secret={**SECRET, "DJANGO_DEBUG": "true"})
        self.assertIs(cloud.DEBUG, False)

    def test_job_has_no_deterministic_host(self):
        # Jobs have no K_SERVICE, so the metadata server isn't asked.
        cloud, _, project_number = self._load()
        self.assertEqual(cloud.ALLOWED_HOSTS, ["vae-stage-web-abc123-uw.a.run.app"])
        project_number.assert_not_called()

    def test_environment_wins_over_secret(self):
        cloud, _, _ = self._load(environ_vars={"GCP_CLOUDSQL_PRIVATE_IP": "10.0.0.1"})
        self.assertEqual(cloud.DATABASES["default"]["HOST"], "10.0.0.1")

    def test_custom_hosts_and_key_fallbacks(self):
        cloud, _, _ = self._load(
            secret={
                **SECRET,
                "ALLOWED_HOSTS": "a.example,b.example",
                "CLOUDRUN_SERVICE_URL": "",
                "DJANGO_SECRET_KEY_FALLBACKS": "old1,old2",
            }
        )
        self.assertEqual(cloud.ALLOWED_HOSTS, ["a.example", "b.example"])
        self.assertEqual(
            cloud.CSRF_TRUSTED_ORIGINS, ["https://a.example", "https://b.example"]
        )
        self.assertEqual(cloud.SECRET_KEY_FALLBACKS, ["old1", "old2"])

    def test_missing_required_value_fails_at_import(self):
        secret = {k: v for k, v in SECRET.items() if k != "GCP_CLOUDSQL_PASSWORD"}
        with self.assertRaisesMessage(
            ImproperlyConfigured, "Set the GCP_CLOUDSQL_PASSWORD environment variable"
        ):
            self._load(secret=secret)

    def test_missing_pointer_fails_before_reading_secret(self):
        keep = {k: v for k, v in os.environ.items() if k not in CATALOGUE}
        client = fake_secret_client(blob(SECRET))
        with (
            mock.patch.dict(os.environ, keep, clear=True),
            mock.patch.object(cloudrun, "_secret_client", return_value=client),
            self.assertRaisesMessage(
                ImproperlyConfigured, "Set the GCP_PROJECT_ID environment variable"
            ),
        ):
            importlib.reload(importlib.import_module("hl_vae.settings.cloud"))
        client.access_secret_version.assert_not_called()

    def test_stage_is_cloud(self):
        stage, _, _ = self._load(module="stage")
        self.assertEqual(stage.SECRET_KEY, "from-secret")
        self.assertIs(stage.DEBUG, False)
        self.assertEqual(stage.DATABASES["default"]["NAME"], "vae")

    def test_static_settings_come_from_base(self):
        # DES-006: the build writes exactly what cloud.py serves.
        base = importlib.import_module("hl_vae.settings.base")
        build = importlib.import_module("hl_vae.settings.build")
        cloud, _, _ = self._load()
        for mod in (build, cloud):
            self.assertEqual(mod.STATIC_ROOT, base.STATIC_ROOT)
            self.assertEqual(mod.STATICFILES_DIRS, base.STATICFILES_DIRS)
            self.assertEqual(mod.STORAGES, base.STORAGES)


class BuildSettingsTests(SimpleTestCase):
    def test_build_needs_no_secrets_or_google_client(self):
        # The Docker build runs with no env and no credentials.
        child_env = {
            k: v
            for k, v in os.environ.items()
            if k not in CATALOGUE and not k.startswith("DJANGO_")
        }
        child_env["DJANGO_SETTINGS_MODULE"] = "hl_vae.settings.build"
        child_env["PYTHONPATH"] = str(settings.BASE_DIR)
        out = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, django; from django.conf import settings; "
                "django.setup(); "
                "print(settings.SECRET_KEY, 'google.cloud' in sys.modules)",
            ],
            env=child_env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(out.stdout.strip(), "build-only-not-secret False")
