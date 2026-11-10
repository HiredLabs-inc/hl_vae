import tempfile
from pathlib import Path

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
