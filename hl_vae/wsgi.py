"""
WSGI config for hl_vae project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application

# No default: a production server must name its environment explicitly
# (e.g. hl_vae.settings.stage on Cloud Run), so a misconfigured deploy fails
# at startup instead of running with the wrong settings.
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    raise ImproperlyConfigured(
        'DJANGO_SETTINGS_MODULE must be set, e.g. to hl_vae.settings.stage. '
        'wsgi.py has no default settings module.'
    )

application = get_wsgi_application()
