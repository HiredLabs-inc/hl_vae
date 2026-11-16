"""prod.py is a placeholder that re-exports base.py until prod is designed."""

import importlib

from django.test import SimpleTestCase

from hl_vae.settings import base


class ProdSettingsTests(SimpleTestCase):
    def test_prod_reexports_base(self):
        prod = importlib.import_module("hl_vae.settings.prod")
        self.assertEqual(prod.INSTALLED_APPS, base.INSTALLED_APPS)
