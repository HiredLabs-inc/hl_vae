"""DES-010: home page renders through base.html with its static assets."""

from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import SimpleTestCase
from django.urls import reverse

ASSETS = ["vae/css/site.css", "vae/js/site.js"]


class HomeViewTests(SimpleTestCase):
    def test_home_uses_base_template(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")
        self.assertTemplateUsed(response, "base.html")

    def test_assets_linked_and_found(self):
        response = self.client.get(reverse("index"))

        for asset in ASSETS:
            with self.subTest(asset=asset):
                self.assertContains(response, static(asset))
                self.assertIsNotNone(
                    finders.find(asset), f"{asset} not found by staticfiles"
                )
