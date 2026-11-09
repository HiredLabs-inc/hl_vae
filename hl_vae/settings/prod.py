"""Prod. There's no prod environment yet (DES-008 covers stage only).

When prod is designed, replace the base import with `from .cloud import *`
and put prod-only settings below it.
"""

from .base import *  # noqa: F403
