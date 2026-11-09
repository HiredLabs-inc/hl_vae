# DES-002: Settings package (base / dev / stage / prod)

- **Status:** Done
- **Area:** Infrastructure
- **Created:** 2026-11-08
- **Updated:** 2026-11-08
- **Related:** prerequisite for DES-008 (step 1 adds `cloud.py` and `build.py` on top of this, and points `stage.py` at `cloud.py`). DES-003 owns secrets and env loading, and local Docker overrides wait for it. DES-005 uses `test.py`. DES-006 owns static settings. Modeled on `hl_main/hl_main/settings/`.

## Summary

Turn `hl_vae/settings/` into a working Python package with one module per
environment: `base.py`, `dev.py`, `stage.py`, `prod.py`, plus `test.py` for
pytest. Point every entry point at an explicit module, and fix the path bugs
left over from moving `settings.py` into the folder. `stage.py` and `prod.py`
are placeholders for now. DES-008 fills in `stage.py`, and `prod.py` stays
unconfigured until there's a prod environment.

## Motivation / Problem

`settings.py` was moved into `hl_vae/settings/`, but the move left the project
in a broken state that's easy to miss:

1. **The real settings never load.** `manage.py`, `wsgi.py` and `asgi.py` all
   default to `DJANGO_SETTINGS_MODULE=hl_vae.settings`. There's no
   `hl_vae/settings/__init__.py`, so that name imports as an *empty namespace
   package*. Django falls back to its defaults: no `INSTALLED_APPS`, no
   `ROOT_URLCONF`, no `SECRET_KEY`.
   - `uv run python manage.py check` reports "no issues", but only because
     nothing is installed.
   - Anything that touches settings, like `runserver`, fails with
     `ImproperlyConfigured: The SECRET_KEY setting must not be empty.`
2. **`BASE_DIR` is one level too shallow.** It's still
   `Path(__file__).resolve().parent.parent`, which now resolves to `hl_vae/`
   rather than the repo root. If the module were loaded, the template directory
   would be `hl_vae/templates` (the real one is `templates/`), and the SQLite file
   and `STATIC_ROOT` would end up inside the package.
3. **Every environment shares one set of values.** The file hardcodes a
   `SECRET_KEY`, `DEBUG = True` and `ALLOWED_HOSTS = ["*"]`. Those are fine
   locally but can't be used on Cloud Run. DES-008 needs a shared base that
   hosted settings can inherit without inheriting the dev values.

Checked on 2026-11-08 with Django 5.2.19 (from `uv.lock`). The file's docstring
says 6.0.8, but `pyproject.toml` pins `Django>=5.1,<6.0`.

## Goals and Non-goals

**Goals**

- `uv run python manage.py runserver` works from a fresh clone with no
  environment variables set, and serves `templates/index.html`.
- One shared `base.py` with **safe defaults**: no secret key, `DEBUG = False`,
  no wildcard hosts. Each environment opts into anything less safe.
- One settings module per environment (dev, stage, prod), so each deployment
  names its own environment, and an environment can get its own settings later
  without touching the others.
- Each entry point names the settings module it uses. A missing or
  unconfigured setting fails loudly; it doesn't silently fall back to dev or
  empty settings.
- `uv run pytest` uses dedicated test settings.
- Use the same layout and naming as hl_main, so nothing has to be learned twice.

**Non-goals**

- `cloud.py`, `build.py`, Secret Manager, `django-environ` and `.env` loading.
  These are covered by DES-008 step 1 and DES-003.
- Configuring prod. DES-008 covers stage only. `prod.py` exists so the layout is
  complete, but it gets real settings only when a prod environment is designed.
- **Local Docker overrides** (env-driven `ALLOWED_HOSTS`/`DEBUG` in `dev.py`).
  These **wait for DES-003**, which adds env loading. Nobody runs the app in
  Docker locally until DES-008 step 1, and that step builds on DES-003.
- Static file changes (WhiteNoise, `STATIC_ROOT` naming, the missing `static/`
  directory). These are covered by DES-006. This item only fixes their paths.
- Local Postgres, a debug toolbar, or other dev tooling.
- Per-developer `local_settings.py` overrides. `.gitignore` already lists the
  file, but nothing reads it, and nothing needs it yet.

## Proposed Design

### Layout

```
hl_vae/settings/
├── __init__.py   # empty, so the folder is a regular package
├── base.py       # shared by every environment (git mv from settings.py)
├── dev.py        # local development: DEBUG, SQLite, dev-only key
├── stage.py      # stage on Cloud Run. Placeholder until DES-008
├── prod.py       # prod. Placeholder until a prod environment is designed
├── test.py       # pytest and CI (DES-005)
├── build.py      # (DES-008) collectstatic during docker build
└── cloud.py      # (DES-008/DES-003) shared by every Cloud Run environment
```

```
base ─┬─ dev
      ├─ test
      ├─ build                 (DES-008)
      └─ cloud ─┬─ stage       (DES-008 switches stage from base to cloud)
                └─ prod        (when prod is designed)
```

`__init__.py` stays **empty**. It doesn't star-import `dev`. A bare
`DJANGO_SETTINGS_MODULE=hl_vae.settings` therefore loads no settings at all.
`runserver` refuses to start (`You must set settings.ALLOWED_HOSTS if DEBUG is
False`), and it never quietly runs with dev settings somewhere it shouldn't.

### `base.py`

This is today's `settings.py`, moved with `git mv` so `git log --follow` keeps
its history, and then changed as follows:

| Setting | Today | `base.py` |
|---|---|---|
| `BASE_DIR` | `.parent.parent` → `hl_vae/` | `Path(__file__).resolve().parent.parent.parent` → repo root |
| `SECRET_KEY` | hardcoded `django-insecure-…` | **not set**. Each environment must provide one |
| `DEBUG` | `True` | `False` |
| `ALLOWED_HOSTS` | `["*"]` | `[]` |
| `DATABASES` | SQLite | **not set**. Each environment chooses one |
| `STATICFILES_DIRS`, `STATIC_ROOT` | `os.path.join(BASE_DIR, …)` | unchanged, but now correct because `BASE_DIR` is fixed. DES-006 revisits them |
| Docstring | "Generated by … 6.0.8" | describes the package and lists the modules |

Everything else stays in `base.py` as it is: apps, middleware, templates, auth
validators, i18n and `WSGI_APPLICATION`. Add `DEFAULT_AUTO_FIELD =
"django.db.models.BigAutoField"`, the startproject default. Without it,
`works` gets the `models.W042` warning as soon as it has a model.

### `dev.py`

```python
"""Local development. Never used on a hosted environment."""
import os

from .base import *  # noqa: F403

DEBUG = True

# Dev-only key. The "django-insecure-" prefix makes `check --deploy` flag it
# if this module is ever used somewhere it shouldn't be.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-<new random value>",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
```

- The key is a **new** value. The old key in git history was never used on a
  hosted environment, so nothing needs rotating. It's still retired so that
  there's one obvious dev key, and it lives in `dev.py`.
- `DJANGO_SECRET_KEY` uses the same variable name as DES-008's secret, so the
  same name works everywhere. Reading it through `django-environ` and `.env` is
  a DES-003 decision.
- `ALLOWED_HOSTS` is explicit rather than `["*"]`. Making it configurable for
  local Docker waits for DES-003 (see Non-goals).

### `stage.py` and `prod.py`

Both start as placeholders that import `base` and add nothing:

```python
"""Stage on Cloud Run. Cloud Run sets DJANGO_SETTINGS_MODULE to this module.

DES-008 replaces the base import with `from .cloud import *`. Stage-only
settings go below it.
"""
from .base import *  # noqa: F403
```

```python
"""Prod. There's no prod environment yet (DES-008 covers stage only).

When prod is designed, replace the base import with `from .cloud import *`
and put prod-only settings below it.
"""
from .base import *  # noqa: F403
```

- Because `base.py` sets no `SECRET_KEY`, `DATABASES` or `ALLOWED_HOSTS` and
  has `DEBUG = False`, neither module can serve anything until it's
  configured. Pointing a deployment at `prod` by mistake gets a 400 on every
  request. `migrate` fails (`settings.DATABASES is improperly configured`), and
  `runserver` refuses to start. Neither module fails at import, though. Django
  5.2 checks `SECRET_KEY` only when something reads it, so `manage.py check`
  passes and gunicorn starts.
- This is the same shape as hl_main: `stage.py` and `prod.py` are thin
  modules on top of a shared `cloud.py`. In hl_main they're legacy aliases.
  In VAE they're what each environment's deployment uses, and they're where
  that environment's own settings will go.

### `test.py`

```python
"""pytest and CI. Fast and fully isolated; no network, no secrets."""
from .base import *  # noqa: F403

SECRET_KEY = "test-only-not-secret"
# The test runner creates an in-memory SQLite database; NAME is only used
# if this module is run outside the test runner.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",  # noqa: F405
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

It inherits from `base`, not `dev`, so dev-only additions like a debug toolbar
never leak into tests. The MD5 hasher keeps user-creating tests fast.

### Entry points

| File | Today | New |
|---|---|---|
| `manage.py` | `setdefault(..., "hl_vae.settings")` | `setdefault(..., "hl_vae.settings.dev")`. Local commands work with no setup |
| `hl_vae/wsgi.py`, `hl_vae/asgi.py` | `setdefault(..., "hl_vae.settings")` | **no default**. If `DJANGO_SETTINGS_MODULE` is unset, raise `ImproperlyConfigured` with a message naming the variable |
| `pyproject.toml` | no pytest config | `[tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE = "hl_vae.settings.test"` and `python_files = ["tests.py", "test_*.py"]` |

`wsgi.py` and `asgi.py` are only used by a production server (gunicorn on Cloud
Run). The Cloud Run env always sets `DJANGO_SETTINGS_MODULE`, to
`hl_vae.settings.stage` on stage. `runserver` goes through `manage.py`, which
has already set it. Without a default, a misconfigured deploy fails at startup
instead of serving with `DEBUG = True`.

### How DES-008 builds on this

DES-008 step 1 makes these settings changes and nothing else:

- Adds `build.py`: `from .base import *` and a non-secret key. It has no
  database. It inherits every static setting (`STATIC_ROOT`, `STORAGES` with
  WhiteNoise) from `base.py` and must not override them, so the build writes
  exactly what `cloud.py` serves (DES-006).
- Adds `cloud.py`: `from .base import *`, loads the Secret Manager blob, then
  sets `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, Postgres, and the
  secure-cookie, HSTS and SSL-proxy settings.
- Changes `stage.py` to `from .cloud import *`.
- Sets `DJANGO_SETTINGS_MODULE=hl_vae.settings.stage` on the Cloud Run web
  service and jobs.

Because `base.py` already has safe defaults, `cloud.py` adds what hosted
environments need and doesn't have to override dev values.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Revert to a single `hl_vae/settings.py` driven by env vars | One file | Every environment's branching lives in one place. Diverges from hl_main | The folder was already started, and hl_main uses modules per environment |
| Cloud Run points straight at `cloud.py`, with no `stage.py`/`prod.py` (the original DES-008 contract) | Two fewer files | No place for environment-specific settings, and the deployment doesn't say which environment it is | One module per environment was chosen. An empty `prod.py` costs nothing and is ready when prod is |
| `__init__.py` star-imports `dev` | `hl_vae.settings` keeps working unchanged | A forgotten `DJANGO_SETTINGS_MODULE` silently runs with DEBUG and a dev key | Fail loudly instead |
| `wsgi.py` defaults to `prod` (like hl_main) | Matches hl_main | `prod` isn't configured, and running gunicorn locally would need GCP access once it is | No default is safer and works before and after DES-008 |
| `django-split-settings` or `django-configurations` | Composable settings | Extra dependency and indirection for a few small files | Plain imports are enough |
| `base.py` keeps the dev key and DEBUG; hosted modules override them | Fewer lines in `dev.py` | A missed override in a hosted module ships the dev key | Safe defaults in `base` |
| Tests use `dev.py` | No `test.py` | Tests change whenever dev tooling changes, and passwords hash slowly | `test.py` is three settings |

## Implementation Plan

On a branch off `develop`, before DES-008 step 1.

- [x] `git mv hl_vae/settings/settings.py hl_vae/settings/base.py` and commit
  the move on its own, so history follows the file.
- [x] Add an empty `hl_vae/settings/__init__.py`.
- [x] Edit `base.py`: fix `BASE_DIR`, remove `SECRET_KEY` and `DATABASES`, set
  `DEBUG = False` and `ALLOWED_HOSTS = []`, add `DEFAULT_AUTO_FIELD`, and replace
  the docstring.
- [x] Add `dev.py` with a newly generated dev key
  (`python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`).
- [x] Add placeholder `stage.py` and `prod.py`.
- [x] Add `test.py`.
- [x] Point `manage.py` at `hl_vae.settings.dev`. Make `wsgi.py` and `asgi.py`
  require `DJANGO_SETTINGS_MODULE`.
- [x] Add `[tool.pytest.ini_options]` to `pyproject.toml`.
- [x] Add a smoke test in `works/tests.py` (see below).
- [x] Update `README.md`: list the settings modules and say which one each
  command uses. (There's no gunicorn section. gunicorn isn't a dependency yet,
  and DES-008 adds it.)

## Testing / Verification

- `uv run python manage.py diffsettings --all | grep -E "^(BASE_DIR|DEBUG|ROOT_URLCONF|INSTALLED_APPS)"`
  shows the repo root, `True`, `hl_vae.urls` and the `works` app. This proves
  the real settings load.
- `uv run python manage.py check` passes with the apps actually installed. The
  only warning is `staticfiles.W004` for the missing `static/` directory,
  which DES-006 owns.
- `uv run python manage.py migrate && uv run python manage.py runserver`, then
  `/` renders `templates/index.html` and `/admin/` loads.
- `db.sqlite3` is created at the repo root, not under `hl_vae/`.
- `DJANGO_SETTINGS_MODULE=hl_vae.settings.dev uv run python manage.py check --deploy`
  warns about `SECRET_KEY` and `DEBUG`. That's expected for dev, and it shows the
  insecure prefix is being detected.
- With `DJANGO_SETTINGS_MODULE` set to `hl_vae.settings.stage` and then to
  `hl_vae.settings.prod`:
  - `uv run python manage.py migrate` fails with `settings.DATABASES is
    improperly configured`.
  - `uv run python manage.py runserver` fails with `You must set
    settings.ALLOWED_HOSTS if DEBUG is False`.
  - Through `hl_vae.wsgi`, `GET /` returns 400.

  This confirms both placeholders can't serve until they're configured.
- `uv run python -c "import hl_vae.wsgi"` with `DJANGO_SETTINGS_MODULE` unset
  fails with the new `ImproperlyConfigured` message.
- `uv run pytest` passes and runs the smoke test:
  - `GET /` returns 200 using `index.html`. This catches template path regressions.
  - `settings.SECRET_KEY == "test-only-not-secret"`. This confirms pytest uses `test.py`.

## Open Questions

- None.

## Changelog

- 2026-11-08 — Created. Confirmed that the current settings never load, and that `BASE_DIR` is off by one level.
- 2026-11-08 — Agreed by the user. Added `stage.py` and `prod.py` (one module per environment; prod empty for now). Local Docker overrides deferred to DES-003.
- 2026-11-08 — `build.py` no longer sets WhiteNoise storage itself; it inherits the static settings from `base.py`, matching DES-006.
- 2026-11-08 — Implementation started on `feature/settings-update-DES-002`; moved to `active/`.
- 2026-11-08 — Corrected the placeholder claims after implementation. On Django 5.2, `SECRET_KEY` is checked only when read, so stage and prod don't fail at import or in `check`. They still can't serve (400 on every request, no database). The verification steps now test that. The README has no gunicorn section until DES-008 adds gunicorn.
- 2026-11-08 — Done. Merged into `develop`; moved to `archive/`.
