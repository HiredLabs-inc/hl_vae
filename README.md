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

### 4. Check your work before pushing

This runs what CI runs. Locally it formats and fixes; CI only checks:

```bash
uv run ruff format . && uv run ruff check --fix . && uv run python manage.py makemigrations --check --dry-run && uv run pytest
```

Editors can use the Ruff extension, which reads the config in `pyproject.toml`.

To make `git blame` skip the bulk formatting commit, run this once:

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

## CI

GitHub Actions runs on every pull request into `develop`, `staging` or `main`,
and on every push to those branches (DES-005 in the [backlog](docs/backlog.md)).

- **`CI / checks`** (`.github/workflows/ci.yml`) is the required check. It
  runs these steps against `hl_vae.settings.test`:
  - `uv sync --locked`, which fails if `uv.lock` is stale;
  - `ruff format --check`;
  - `ruff check`;
  - `manage.py check --fail-level WARNING`;
  - `makemigrations --check`;
  - `pytest` with a coverage report.

  After a failure, the remaining checks still run, so one run shows every
  problem.
- **`Terraform`** (`.github/workflows/terraform.yml`) runs `terraform fmt` and
  `validate` only when `infra/terraform/` changes. It isn't required.

CI uses no secrets and has no cloud access.

## Settings

Settings live in the `hl_vae/settings/` package, one module per environment.
All of them import the shared `base.py`, which has safe defaults (no secret key,
no database, `DEBUG = False`, no allowed hosts).

| Module | Used for | Used by |
|---|---|---|
| `hl_vae.settings.dev` | Local development (SQLite, `DEBUG = True`, dev-only key) | `manage.py` by default |
| `hl_vae.settings.test` | Tests and CI | `uv run pytest` (set in `pyproject.toml`) |
| `hl_vae.settings.stage` | Stage on Cloud Run: imports `cloud.py`, which reads Secret Manager | Cloud Run, via `DJANGO_SETTINGS_MODULE` |
| `hl_vae.settings.build` | `collectstatic` during `docker build` (no secrets, no database) | the `Dockerfile` |
| `hl_vae.settings.prod` | Prod (placeholder; not configured yet) | Nothing yet |

`hl_vae/wsgi.py` and `hl_vae/asgi.py` have no default and refuse to start unless
`DJANGO_SETTINGS_MODULE` is set. To use a different module with `manage.py`, set
the variable, for example:

```bash
DJANGO_SETTINGS_MODULE=hl_vae.settings.test uv run python manage.py check
```

### Local configuration

Nothing is needed by default. A fresh clone runs on SQLite with `DEBUG` on.
To override dev settings, copy the example file and uncomment what you need:

```bash
cp .env.example .env
```

| Variable | Default in `dev.py` |
|---|---|
| `DJANGO_DEBUG` | `true` (if `false`, run `collectstatic` first; see Static files) |
| `DJANGO_SECRET_KEY` | a built-in dev-only key |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` |
| `DATABASE_URL` | SQLite at `db.sqlite3` |

- **Precedence:** shell variables, including `docker run -e`, win over `.env`.
  `.env` and every `.env.*` except `.env.example` are gitignored.
- **Who reads `.env`:** only `hl_vae.settings.dev` reads it. Tests and the
  Docker build read no environment, so a local `.env` can't change test
  results.
- **Where settings come from:** every settings module reads config through
  the single `env` object defined in `base.py` (`django-environ`). App code
  reads `django.conf.settings`, never the environment. See DES-003 in the
  [backlog](docs/backlog.md).

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

## Docker image

The `Dockerfile` builds the image Cloud Run runs (DES-008 in the
[backlog](docs/backlog.md)): Python 3.12, dependencies from `uv.lock`,
`collectstatic` at build time, and gunicorn on `$PORT`. It holds no secrets or
credentials, and `.dockerignore` keeps `.env` files out of it. It has no
default `DJANGO_SETTINGS_MODULE`; Cloud Run sets `hl_vae.settings.stage`.

To try it locally against Postgres, use the dev settings with the DES-003
overrides:

```bash
docker network create vae
docker run -d --name vae-pg --network vae -e POSTGRES_USER=vae \
  -e POSTGRES_PASSWORD=vae -e POSTGRES_DB=vae postgres:15
docker build -t vae .
docker run --rm --network vae -p 8000:8080 \
  -e DJANGO_SETTINGS_MODULE=hl_vae.settings.dev -e DJANGO_DEBUG=false \
  -e ALLOWED_HOSTS=localhost -e DATABASE_URL=postgres://vae:vae@vae-pg:5432/vae \
  vae sh -c "python manage.py migrate && exec gunicorn --bind 0.0.0.0:8080 --no-control-socket hl_vae.wsgi:application"
```

Then open http://localhost:8000/.

## Design docs

Design work is tracked in [`docs/`](docs/):

- [`docs/backlog.md`](docs/backlog.md) — all features and infrastructure work, grouped by phase
- [`docs/buglog.md`](docs/buglog.md) — all bugs, grouped by phase

Per-item design docs live in phase subdirectories (`designed/`, `active/`, `archive/`, `bugfixes/`); templates are in `docs/templates/`.
