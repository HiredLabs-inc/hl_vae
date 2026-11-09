from django.conf import settings
from django.test import TestCase


class SmokeTests(TestCase):
    def test_index_renders_template(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    def test_uses_test_settings(self):
        self.assertEqual(settings.SECRET_KEY, "test-only-not-secret")
