"""Stage on Cloud Run. Cloud Run sets DJANGO_SETTINGS_MODULE to this module.

Everything shared by Cloud Run environments is in cloud.py. Stage-only
settings go below the import.
"""

from .cloud import *  # noqa: F403
