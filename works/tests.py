import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import environ
from django.conf import settings
from django.core.management import call_command
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings


class SmokeTests(TestCase):
    def test_index_renders_template(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    def test_uses_test_settings(self):
        self.assertEqual(settings.SECRET_KEY, "test-only-not-secret")


class StaticFilesTests(SimpleTestCase):
    """DES-006: static files are collected at build time and served by WhiteNoise."""

    def test_manifest_build(self):
        # The same storage the Docker build uses (test.py swaps it out), so a
        # broken CSS url() or a missing file fails here as it would in the build.
        with tempfile.TemporaryDirectory() as tmp:
            manifest = "whitenoise.storage.CompressedManifestStaticFilesStorage"
            storages = {**settings.STORAGES, "staticfiles": {"BACKEND": manifest}}
            with override_settings(STATIC_ROOT=tmp, STORAGES=storages):
                call_command("collectstatic", interactive=False, verbosity=0)

            root = Path(tmp)
            self.assertTrue((root / "staticfiles.json").is_file())
            css_dir = root / "admin" / "css"
            hashed = [p for p in css_dir.glob("base.*.css") if p.name != "base.css"]
            self.assertEqual(len(hashed), 1, "expected one hashed copy of base.css")
            self.assertTrue(Path(f"{hashed[0]}.gz").is_file())

    def test_static_tag_renders(self):
        # Tests use plain storage, so {% static %} needs no manifest.
        rendered = Template(
            "{% load static %}{% static 'admin/css/base.css' %}"
        ).render(Context())
        self.assertEqual(rendered, "/static/admin/css/base.css")

    def test_whitenoise_middleware_position(self):
        self.assertEqual(
            settings.MIDDLEWARE[0], "django.middleware.security.SecurityMiddleware"
        )
        self.assertEqual(
            settings.MIDDLEWARE[1], "whitenoise.middleware.WhiteNoiseMiddleware"
        )


class EnvConfigTests(SimpleTestCase):
    """DES-003: dev settings come from env/.env; tests read nothing."""

    def _load_dev(self, environ_vars, *, ignore_dotenv=True):
        """Import hl_vae.settings.dev fresh, with only `environ_vars` set.

        With ignore_dotenv, a developer's own .env can't change the result.
        Importing the module doesn't change the active Django settings.
        """
        keep = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        keep.pop("DATABASE_URL", None)
        keep.pop("ALLOWED_HOSTS", None)
        patches = [mock.patch.dict(os.environ, {**keep, **environ_vars}, clear=True)]
        if ignore_dotenv:
            patches.append(
                mock.patch.object(environ.Env, "read_env", lambda *a, **k: None)
            )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return importlib.reload(importlib.import_module("hl_vae.settings.dev"))

    def test_dev_defaults(self):
        dev = self._load_dev({})
        self.assertIs(dev.DEBUG, True)
        self.assertEqual(dev.ALLOWED_HOSTS, ["localhost", "127.0.0.1", "[::1]"])
        db = dev.DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(Path(db["NAME"]), settings.BASE_DIR / "db.sqlite3")
        self.assertTrue(dev.SECRET_KEY.startswith("django-insecure-dev-only-"))

    def test_dev_database_url(self):
        dev = self._load_dev({"DATABASE_URL": "postgres://u:p@h:5432/d"})
        db = dev.DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(
            (db["NAME"], db["USER"], db["HOST"], db["PORT"]), ("d", "u", "h", 5432)
        )

    def test_dev_overrides(self):
        dev = self._load_dev(
            {
                "DJANGO_DEBUG": "false",
                "ALLOWED_HOSTS": "localhost,example.test",
                "DJANGO_SECRET_KEY": "from-env",
            }
        )
        self.assertIs(dev.DEBUG, False)
        self.assertEqual(dev.ALLOWED_HOSTS, ["localhost", "example.test"])
        self.assertEqual(dev.SECRET_KEY, "from-env")

    def test_shell_wins_over_dotenv(self):
        # Point BASE_DIR at a temp dir so dev.py reads a real .env from there,
        # not the developer's own.
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                "DJANGO_DEBUG=false\nALLOWED_HOSTS=from-dotenv\n"
            )
            with mock.patch("hl_vae.settings.base.BASE_DIR", Path(tmp)):
                dev = self._load_dev({"DJANGO_DEBUG": "true"}, ignore_dotenv=False)
        self.assertIs(dev.DEBUG, True)  # shell wins
        self.assertEqual(dev.ALLOWED_HOSTS, ["from-dotenv"])  # .env fills the gap

    def test_test_settings_ignore_dotenv(self):
        # A .env in the working directory must not leak into test settings.
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("DJANGO_SECRET_KEY=from-dotenv\n")
            child_env = {
                k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")
            }
            child_env["DJANGO_SETTINGS_MODULE"] = "hl_vae.settings.test"
            child_env["PYTHONPATH"] = str(settings.BASE_DIR)
            out = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import django; from django.conf import settings; "
                    "django.setup(); print(settings.SECRET_KEY)",
                ],
                cwd=tmp,
                env=child_env,
                capture_output=True,
                text=True,
                check=True,
            )
        self.assertEqual(out.stdout.strip(), "test-only-not-secret")
