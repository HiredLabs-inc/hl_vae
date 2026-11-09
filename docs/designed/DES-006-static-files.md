# DES-006: Static files and asset handling

- **Status:** Designed
- **Area:** Infrastructure
- **Created:** 2026-11-08
- **Updated:** 2026-11-08
- **Related:** implements the static-files part of the DES-008 app contract (WhiteNoise, `collectstatic` in `docker build`). Builds on DES-002 (settings package, `BASE_DIR` fix) and sits beside DES-003 (`DJANGO_DEBUG` local override). DES-005 runs the tests below. Modeled on `hl_main/hl_main/settings/{base,build,cloud,dev}.py`.

## Summary

Static files are collected into the Docker image at build time and served by
**WhiteNoise** from inside the Django process, with hashed file names,
pre-compressed copies and long cache headers. All static settings live once in
`base.py`, so dev, build, stage and prod can't drift apart. No bucket, no CDN
and no Node toolchain.

## Motivation / Problem

DES-008 picked WhiteNoise but left the details here. The current state:

1. **Nothing serves static files on a hosted environment.** With `DEBUG =
   False`, Django doesn't serve `/static/`. On Cloud Run there's no web server
   or load balancer in front of gunicorn, so `/admin/` would load unstyled.
2. **The source directory doesn't exist.** `STATICFILES_DIRS` points at
   `static/`, which isn't in the repo. Once DES-002 makes the settings load,
   every `manage.py` command warns `staticfiles.W004: The directory
   '…/static' in the STATICFILES_DIRS setting does not exist`.
3. **`STATIC_ROOT` has an ad-hoc name and isn't ignored.** `static_main/` isn't
   in `.gitignore`, so a local `collectstatic` produces hundreds of
   untracked files.
4. **hl_main duplicates its static settings** in `build.py`, `dev.py` and
   `cloud.py`, with a "Static settings must match cloud.py" comment as the only
   guard. If `build.py` and `cloud.py` disagree on `STATIC_ROOT` or the
   storage backend, the image is built one way and served another, and every
   `{% static %}` tag fails with a missing-manifest error. VAE shouldn't copy
   that.
5. **Manifest storage breaks tests in a non-obvious way.** With
   `DEBUG = False` (as in `test.py`), any template that uses `{% static %}`
   raises `ValueError: Missing staticfiles manifest entry` unless
   `collectstatic` has run. The first template that adds a stylesheet would
   break the test suite.

## Goals and Non-goals

**Goals**

- `/admin/` and any project CSS/JS/images load on stage with no extra
  infrastructure, and cost nothing.
- Hashed file names with `Cache-Control: immutable` for one-year caching, and
  gzip-compressed responses.
- One definition of the static settings, in `base.py`, that the build and the
  running container share by construction.
- Dev works with `runserver` and no `collectstatic`, and serves files the same
  way stage does.
- Tests don't need `collectstatic`, but a broken asset reference (e.g. a CSS
  `url()` to a missing file) still fails CI.
- A clear place for project-wide and app-specific assets.

**Non-goals**

- **Media / user uploads.** DES-008 has no media bucket. `MEDIA_ROOT`,
  `MEDIA_URL` and the `default` storage stay at Django's defaults until a
  feature needs uploads; that feature's design adds GCS.
- **A CDN, load balancer or GCS bucket for static files.** Revisit with
  DES-009 (custom domain) or if traffic warrants it.
- **A frontend build step** (npm, Tailwind, Vite, React). See *Future frontend
  tooling* for how one would plug in.
- **Site styling or a base template.** That's UI work for a feature design.
  `templates/index.html` stays as it is.
- **Brotli.** Gzip is enough for stage traffic (see Alternatives).

## Proposed Design

### Directory layout

```
hl_vae/                  # repo root (BASE_DIR after DES-002)
├── static/              # project-wide source assets  (STATICFILES_DIRS)
│   └── .gitkeep         # keeps the dir in git until the first real asset
├── works/
│   └── static/works/    # app-specific assets, namespaced by app (when needed)
├── staticfiles/         # collectstatic output (STATIC_ROOT) — gitignored, dockerignored
└── templates/
```

- **Project-wide assets** (site CSS, logo, favicon) go in `static/`, under a
  `vae/` subfolder once there are any (`static/vae/css/site.css`), so they
  can't collide with an app's or the admin's files.
- **App-specific assets** go in `<app>/static/<app>/…`, Django's standard
  namespacing, found by `AppDirectoriesFinder`.
- **`STATIC_ROOT` is renamed** `static_main/` → `staticfiles/`, the name used
  by the Django and WhiteNoise docs. It is build output only and is never
  committed.

### Settings

Everything goes in `base.py`, replacing today's three lines:

```python
# Static files (CSS, JavaScript, images). Served by WhiteNoise in every
# environment; see DES-006. Don't override these per environment.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

`INSTALLED_APPS` and `MIDDLEWARE` in `base.py`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",   # must come before staticfiles
    "django.contrib.staticfiles",
    "works.apps.WorksConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # directly after Security
    "django.contrib.sessions.middleware.SessionMiddleware",
    # … unchanged …
]
```

- The middleware sits directly after `SecurityMiddleware`, as WhiteNoise
  requires, so static responses still get the security headers but skip
  sessions, CSRF and auth.
- `runserver_nostatic` turns off `runserver`'s own static handler, so dev
  requests go through the same WhiteNoise middleware as stage.
- `os.path.join` and the tuple are replaced with `Path` and a list, matching
  the rest of `base.py`. `import os` stays only if something else still uses
  it.
- No `WHITENOISE_*` settings are needed in `base.py`. The defaults are right:
  hashed files get `max-age=315360000, public, immutable`, unhashed files
  60 seconds, and in `DEBUG` WhiteNoise autorefreshes and serves straight from
  the finders.

### Per-environment behaviour

Nothing is overridden per environment except in `test.py`.

| Environment | Settings | How files are found | `collectstatic` needed? |
|---|---|---|---|
| Dev (`runserver`) | `dev.py` → `base` | `DEBUG = True`: WhiteNoise uses the finders and autorefreshes; `{% static %}` emits unhashed URLs | No |
| Dev with `DJANGO_DEBUG=false` (DES-003 override) | `dev.py` → `base` | Manifest in `staticfiles/` | **Yes**, `uv run python manage.py collectstatic --noinput` first |
| Docker build | `build.py` → `base` | Writes `staticfiles/` and `staticfiles.json` | It *is* the step |
| Stage / prod (Cloud Run) | `stage.py` → `cloud` → `base` | Manifest in the image's `staticfiles/` | Already done at build |
| Tests | `test.py` → `base` | Plain storage, no manifest (below) | No |

**`build.py`** (added by DES-008) needs nothing static-specific: it inherits
`STATIC_ROOT` and `STORAGES` from `base`, which is what removes hl_main's
"must match cloud.py" problem. Its docstring should say so:

```python
"""Settings used only for `collectstatic` during `docker build`.

No secrets, credentials or database. Static settings are inherited from
base.py, so the build writes exactly what cloud.py serves. Don't override
them here.
"""
from .base import *  # noqa: F403

SECRET_KEY = "build-only-not-secret"
```

**`cloud.py`** (DES-008/DES-003) also inherits and must not override them.

**`test.py`** (DES-002) adds:

```python
# No collectstatic in tests: plain storage, so {% static %} doesn't need a
# manifest. test_manifest_build checks the real manifest build separately.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
# DEBUG is False here, so WhiteNoise would warn "No directory at: …/staticfiles/"
# on every test run. Autorefresh mode skips that check and serves from finders.
WHITENOISE_AUTOREFRESH = True
```

### Docker build

DES-008 owns the Dockerfile. DES-006 specifies the static step and the ignore
rules:

```dockerfile
# after `uv sync --frozen --no-dev` and COPY of the source
RUN DJANGO_SETTINGS_MODULE=hl_vae.settings.build \
    uv run --no-sync python manage.py collectstatic --noinput
```

- It runs **after** the source is copied and **before** the final `CMD`, so
  `staticfiles/` is baked into the image layer.
- It needs no network, secrets or database. If it fails (e.g. a CSS file
  references a missing image), the build fails, and nothing broken gets
  deployed.
- `--clear` isn't needed: the build always starts without `staticfiles/`.

`.dockerignore` must include `staticfiles/`, so a developer's local
`collectstatic` output can't leak into the image and shadow the build's own.
`static/` must **not** be ignored.

`.gitignore` adds:

```
# Django collectstatic output (DES-006)
staticfiles/
```

### Request path on stage

```
browser ── HTTPS ──▶ Cloud Run front end ──▶ gunicorn (1 worker, 8 threads)
                                               └─ SecurityMiddleware
                                                  └─ WhiteNoiseMiddleware
                                                       ├─ /static/… in manifest ──▶ file from image
                                                       │     (gzip if Accept-Encoding allows,
                                                       │      immutable cache headers)
                                                       └─ anything else ──▶ rest of Django
```

WhiteNoise indexes `staticfiles/` once at startup and serves from memory-mapped
files, so static requests don't touch the database. That matters here: a
static request on stage doesn't wake `vae-stage-sql`.

Admin assets are about 1–2 MB uncompressed (plus `.gz` copies), so the image
grows by a few MB. Each revision carries its own assets, so a rollback also
rolls back the CSS that matches it.

### Future frontend tooling

If a later design adds npm/Tailwind/Vite, it should:

- build in a separate Docker stage (`node:…-slim`) and copy its output into
  `static/vae/…` *before* `collectstatic` runs, so WhiteNoise hashes and
  compresses it like everything else;
- emit unhashed file names, and let Django's manifest do the hashing, so
  there's one cache-busting scheme;
- keep Node out of the runtime image.

This design doesn't add anything for it now.

### Dependency

Add `whitenoise>=6.8,<7` to `[project] dependencies` (already in the DES-008
dependency list; this pins the range). 6.8 is the first release that supports
Django 5.2.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| GCS bucket + `django-storages` for static | Offloads requests from gunicorn; could sit behind Cloud CDN | Extra bucket, IAM, upload credentials in the build, and a deploy-ordering problem (assets must exist before the revision) | Unneeded at stage traffic; WhiteNoise was the DES-008 decision |
| Cloud CDN / load balancer in front | Edge caching, custom domain | About $18/mo | Out of scope; revisit with DES-009 |
| Static settings per environment (hl_main's layout) | Each file is self-describing | Build and runtime can drift; the "must match" comment is the only guard | Define once in `base.py` |
| `STATIC_ROOT` stays `static_main/` (or hl_main's `main_static/`) | No rename | Non-standard name, and not ignored today | `staticfiles/` matches the docs; nothing depends on the old name yet |
| `CompressedStaticFilesStorage` (no manifest) | No manifest errors anywhere | No hashed names, so caching has to be short or stale CSS is served after a deploy | Manifest gives safe one-year caching |
| `ManifestStaticFilesStorage` (Django's, no compression) | No WhiteNoise storage class | No pre-compressed files; WhiteNoise would serve everything uncompressed | WhiteNoise's class adds gzip for free |
| `whitenoise[brotli]` | About 15–20% smaller text assets | Adds the compiled `Brotli` package to the image | Not worth it for stage; a one-line change later |
| Tests run `collectstatic` in a fixture | Tests use the real storage | Slower suite, writes to disk | Plain storage in tests plus one dedicated manifest test |
| Let `runserver` serve static in dev (no `runserver_nostatic`) | One less app entry | Dev and stage serve files differently | Same path everywhere |

## Implementation Plan

Lands with or right after DES-002, and before DES-008 step 1 needs
`collectstatic` in the Dockerfile.

- [ ] Add `whitenoise>=6.8,<7` to `pyproject.toml` and `uv lock`.
- [ ] Create `static/.gitkeep`.
- [ ] In `base.py`: replace the static block with the one above, add
  `whitenoise.runserver_nostatic` and `WhiteNoiseMiddleware`.
- [ ] In `test.py`: add the `STORAGES` override and `WHITENOISE_AUTOREFRESH`.
- [ ] Add `staticfiles/` to `.gitignore`.
- [ ] Give DES-008 the `collectstatic` Dockerfile step, the `.dockerignore`
  entry and the `build.py` docstring.
- [ ] Add the tests below to `works/tests.py`, next to DES-002's smoke test.
- [ ] README: a short "Static files" section — where to put assets, that dev
  needs no `collectstatic`, and that it's needed when running with
  `DJANGO_DEBUG=false`.

## Testing / Verification

**Automated (pytest, run by DES-005's CI):**

- `test_manifest_build`: call `collectstatic` with `STATIC_ROOT` set to
  `tmp_path` and `STORAGES["staticfiles"]` set back to
  `CompressedManifestStaticFilesStorage` (via `override_settings`). Assert it
  succeeds, `staticfiles.json` exists, and `admin/css/base.css` has a hashed
  copy and a `.gz` copy. This catches broken CSS `url()` references and
  missing files, exactly what would fail the Docker build.
- `test_static_tag_renders`: render a template string `{% load static %}{%
  static 'admin/css/base.css' %}` and assert it returns
  `/static/admin/css/base.css`. Confirms tests need no manifest.
- `test_whitenoise_middleware_position`: assert
  `WhiteNoiseMiddleware` is at index 1 in `settings.MIDDLEWARE`, right after
  `SecurityMiddleware`.

**Manual / local:**

- `uv run python manage.py check` shows no `staticfiles.W004` warning.
- `uv run python manage.py runserver` with no `staticfiles/` directory:
  `/admin/` loads styled.
- `DJANGO_SETTINGS_MODULE=hl_vae.settings.build uv run python manage.py collectstatic --noinput`
  creates `staticfiles/` at the repo root with `staticfiles.json`, and
  `git status` stays clean.
- `docker build .` succeeds, and the image contains
  `/app/staticfiles/staticfiles.json` (path depends on DES-008's `WORKDIR`).

**On stage (after the first DES-008 deploy):**

- `/admin/` loads styled on the `run.app` URL.
- `curl -sI -H 'Accept-Encoding: gzip' <url>/static/admin/css/base.<hash>.css`
  returns `200`, `Content-Encoding: gzip` and
  `Cache-Control: max-age=315360000, public, immutable`.
- Fetching a static file while `vae-stage-sql` is stopped still returns 200
  (static requests don't need the database).

## Open Questions

- None.

## Changelog

- 2026-11-08 — Created. Confirmed `static/` doesn't exist and `static_main/` isn't gitignored; compared with hl_main's duplicated static settings.
