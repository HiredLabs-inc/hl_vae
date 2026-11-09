"""Stage on Cloud Run. Cloud Run sets DJANGO_SETTINGS_MODULE to this module.

DES-008 replaces the base import with `from .cloud import *`. Stage-only
settings go below it.
"""

from .base import *  # noqa: F403
