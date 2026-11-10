# Veteran Academic Exchange

## Development setup with uv

### 1. Install and pin Python

```bash
uv python install 3.12
```

### 2. Sync dependencies

Install runtime + dev dependencies from `pyproject.toml`:

```bash
uv sync --extra dev
```

### 3. Run project commands through uv

```bash
uv run python manage.py runserver
uv run pytest
```

Use `uv run` for all local commands so they always execute in the synced project environment.

## Settings

Settings live in the `hl_vae/settings/` package, one module per environment.
All of them import the shared `base.py`, which has safe defaults (no secret key,
no database, `DEBUG = False`, no allowed hosts).

| Module | Used for | Used by |
|---|---|---|
| `hl_vae.settings.dev` | Local development (SQLite, `DEBUG = True`, dev-only key) | `manage.py` by default |
| `hl_vae.settings.test` | Tests and CI | `uv run pytest` (set in `pyproject.toml`) |
| `hl_vae.settings.stage` | Stage on Cloud Run (placeholder until DES-008) | Cloud Run, via `DJANGO_SETTINGS_MODULE` |
| `hl_vae.settings.prod` | Prod (placeholder; not configured yet) | Nothing yet |

`hl_vae/wsgi.py` and `hl_vae/asgi.py` have no default and refuse to start unless
`DJANGO_SETTINGS_MODULE` is set. To use a different module with `manage.py`, set
the variable, for example:

```bash
DJANGO_SETTINGS_MODULE=hl_vae.settings.test uv run python manage.py check
```

## Static files

Static files are served by [WhiteNoise](https://whitenoise.readthedocs.io/) in
every environment (DES-006 in the [backlog](docs/backlog.md)). The
settings live once in `hl_vae/settings/base.py`; don't override them per
environment.

- **Project-wide assets** (site CSS, logo, favicon) go in `static/vae/…`,
  e.g. `static/vae/css/site.css`.
- **App-specific assets** go in `<app>/static/<app>/…`, e.g.
  `works/static/works/…`.
- Reference them in templates with `{% load static %}` and `{% static 'vae/css/site.css' %}`.

`runserver` needs no `collectstatic`: with `DEBUG = True`, WhiteNoise serves
files straight from their source directories. With `DEBUG` off (for example
the `DJANGO_DEBUG=false` override from DES-003), run this first:

```bash
uv run python manage.py collectstatic --noinput
```

It writes hashed, gzipped copies to `staticfiles/`, which is gitignored. On
stage, `collectstatic` runs during `docker build`.

## Design docs

Design work is tracked in [`docs/`](docs/):

- [`docs/backlog.md`](docs/backlog.md) — all features and infrastructure work, grouped by phase
- [`docs/buglog.md`](docs/buglog.md) — all bugs, grouped by phase

Per-item design docs live in phase subdirectories (`designed/`, `active/`, `archive/`, `bugfixes/`); templates are in `docs/templates/`.
