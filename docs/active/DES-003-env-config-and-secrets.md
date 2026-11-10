# DES-003: Environment config and secrets management

- **Status:** In Progress (Cloud Run half)
- **Area:** Infrastructure
- **Created:** 2026-11-08
- **Updated:** 2026-11-10
- **Related:** builds on DES-002 (settings package). Implements the secret and env parts of the DES-008 app contract (`cloud.py`, the `vae-stage-app-env` blob). Takes the local Docker overrides deferred by DES-002. DES-005 runs tests with no env. Modeled on `hl_main/hl_main/settings/cloud.py` and `hl_main/hl_main/cloudrun.py`.

## Summary

One way to read configuration in every environment: a single `django-environ`
`Env` object in `base.py`. Local dev can read an optional, gitignored `.env`.
Cloud Run loads the `.env`-format Secret Manager secret that DES-008 defines.
Tests and the Docker build read nothing. This doc also lists every variable,
says which values are secret and where each one lives, and gives the runbook
for adding, rotating and revoking secrets.

## Motivation / Problem

- The settings file has a hardcoded `SECRET_KEY` in git. DES-002 removes it
  from `base.py`, but the project still has no rule for where secrets *do* go.
- DES-008 assumes `cloud.py` loads a Secret Manager blob with `django-environ`,
  with "values already in the environment win". DES-002 left env loading,
  `.env` handling and env-driven dev overrides to this item. Nothing yet
  defines:
  - which variables exist, which are secret, and which are required;
  - how a developer overrides dev settings (for example running the container
    locally against Postgres in DES-008 step 1) without editing code;
  - what happens when a required value or the secret is missing;
  - how a secret is changed, rotated or revoked, and who can do it.
- Without this, each later feature invents its own `os.environ.get(...)` with a
  silent default, secrets drift into Terraform or Cloud Build logs, and a
  missing value on stage turns into a confusing runtime error instead of a
  clear startup failure.

## Goals and Non-goals

**Goals**

- One mechanism (`django-environ`) and one `env` object for every settings
  module. No direct `os.environ` reads in settings.
- Settings modules are the **only** code that reads the environment. App code
  reads `django.conf.settings`.
- A fresh clone still runs with **no** `.env` and no environment variables
  (the DES-002 goal is kept).
- Every required hosted value **fails at startup** with a message that names
  the variable or secret. No silent fallbacks on stage.
- Secrets never appear in git, the image, Terraform state, Cloud Build logs, or
  plain Cloud Run env vars.
- A committed `.env.example` and a variable catalogue that say what each
  variable is for and where it's set.
- A short runbook for adding a variable, and for rotating and revoking secrets.
- Keep hl_main's variable names and loading pattern.

**Non-goals**

- Terraform for the secret container, service accounts and IAM. DES-008 owns
  them. This doc states what they need to provide.
- `build.py`, WhiteNoise and the Dockerfile itself (DES-008 and DES-006).
  This doc only says what the build and the image must *not* contain.
- Prod. The design works for prod unchanged (a second blob, `vae-prod-app-env`),
  but prod isn't designed yet.
- Secret scanning in CI (for example gitleaks). It belongs to DES-005; noted
  there as a suggestion.
- Per-developer access to stage secrets. Local dev needs no secrets.
- Feature flags or runtime-editable config. Changing config means a new
  secret version or a code change, then a new revision.

## Proposed Design

### Rules

1. **One reader.** `base.py` creates `env = environ.Env()`. Every settings
   module uses `env(...)`, `env.bool(...)`, `env.list(...)` and so on. This
   replaces the `os.environ.get("DJANGO_SECRET_KEY", ...)` in DES-002's
   `dev.py`.
2. **Only settings read the environment.** If app code needs a value, a
   settings module exposes it as a setting.
3. **Required means no default.** On hosted environments a required value is
   read as `env("NAME")`. If it's missing, `django-environ` raises
   `ImproperlyConfigured: Set the NAME environment variable` at import, and the
   revision never becomes ready.
4. **Security switches are code, not config, on hosted environments.**
   `cloud.py` hardcodes `DEBUG = False`, the secure-cookie, HSTS and SSL-proxy
   settings. Editing the secret can't turn them off.
5. **Precedence** (highest first), and existing values are never overwritten:

   | Environment | 1st | 2nd | 3rd |
   |---|---|---|---|
   | Local dev | shell / `docker run -e` | `.env` at the repo root | defaults in `dev.py` |
   | Cloud Run (stage) | Cloud Run env vars (Terraform) | Secret Manager blob | defaults in `cloud.py` (non-secret only) |
   | Tests (`test.py`) | — | — | fixed values in `test.py` |
   | Docker build (`build.py`) | — | — | fixed values in `build.py` |

6. **Tests and the build read nothing.** `test.py` and `build.py` don't read
   `.env` or call Secret Manager, so a developer's `.env` can't change test
   results and the build needs no credentials.

### Where each kind of value lives

| Kind | Example | Lives in | Why |
|---|---|---|---|
| Pointers that say *which* environment and secret | `DJANGO_SETTINGS_MODULE`, `GCP_PROJECT_ID`, `GCP_SECRETS_NAME` | Cloud Run env vars, set by Terraform | Needed before the secret can be read. Not secret |
| Secrets | `DJANGO_SECRET_KEY`, `GCP_CLOUDSQL_PASSWORD` | `vae-stage-app-env` blob, versions added with `gcloud` | Never in Terraform state or git |
| Non-secret environment config | `GCP_REGION`, `GCP_CLOUDSQL_PRIVATE_IP`, `CLOUDRUN_SERVICE_URL` | the same blob | One place to look, the same as hl_main and the DES-008 contract |
| Values set by the platform | `K_SERVICE`, `PORT` | Cloud Run | Read as-is |
| Local overrides | `DATABASE_URL`, `ALLOWED_HOSTS`, `DJANGO_DEBUG` | `.env` (gitignored) or the shell | Optional; dev works without them |

### Variable catalogue

This is the complete list when DES-008 lands. A new variable is added here
(and to `.env.example` and the `infra/README.md` copy) in the same change that
starts reading it.

| Variable | Read by | Local dev | Stage: set in | Secret | Required on stage |
|---|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Django | `manage.py` default `hl_vae.settings.dev` | Cloud Run env: `hl_vae.settings.stage` | no | yes (`wsgi.py` has no default, per DES-002) |
| `GCP_PROJECT_ID` | `cloud.py` | — | Cloud Run env: `hl-vae-stage` | no | yes |
| `GCP_SECRETS_NAME` | `cloud.py` | — | Cloud Run env: `vae-stage-app-env` | no | yes |
| `DJANGO_SECRET_KEY` | `dev.py`, `cloud.py` | optional; `dev.py` has a dev-only default | blob | **yes** | yes |
| `DJANGO_SECRET_KEY_FALLBACKS` | `cloud.py` | — | blob, normally empty | **yes** | no (default `[]`) |
| `GCP_REGION` | `cloud.py` | — | blob: `us-west1` | no | yes |
| `GCP_CLOUDSQL_DB_NAME` | `cloud.py` | — | blob: `vae` | no | yes |
| `GCP_CLOUDSQL_USER` | `cloud.py` | — | blob: `vae` | no | yes |
| `GCP_CLOUDSQL_PASSWORD` | `cloud.py` | — | blob | **yes** | yes |
| `GCP_CLOUDSQL_PRIVATE_IP` | `cloud.py` | — | blob (`terraform output sql_private_ip`) | no | yes |
| `CLOUDRUN_SERVICE_URL` | `cloud.py` | — | blob (`terraform output web_url`) | no | no (default `""`; the deterministic host is still added) |
| `ALLOWED_HOSTS` | `dev.py`, `cloud.py` | optional; default `localhost,127.0.0.1,[::1]` | blob, empty on stage | no | no |
| `DJANGO_DEBUG` | `dev.py` only | optional; default `True` | **never read** | no | — |
| `DATABASE_URL` | `dev.py` only | optional; default SQLite at `db.sqlite3` | **never read** | maybe (local only) | — |
| `K_SERVICE` | `hl_vae/cloudrun.py` | — | set by Cloud Run | no | — |

`DJANGO_SECRET_KEY_FALLBACKS` is a comma-separated list that feeds Django's
`SECRET_KEY_FALLBACKS`. It lets the key be rotated without logging everyone out
(see *Rotate `DJANGO_SECRET_KEY`*).

### `base.py`

Adds the reader and nothing else. `base.py` reads no variables:

```python
import environ

env = environ.Env()
```

Because every module star-imports `base`, `env` is available everywhere.

### `dev.py` (local)

Replaces DES-002's `os.environ.get` with `env`, and adds the local Docker
overrides that DES-002 deferred:

```python
"""Local development. Never used on a hosted environment."""
from .base import *  # noqa: F403

# Optional, gitignored. Shell variables win over the file.
_dotenv = BASE_DIR / ".env"  # noqa: F405
if _dotenv.is_file():
    env.read_env(_dotenv)  # noqa: F405

DEBUG = env.bool("DJANGO_DEBUG", default=True)  # noqa: F405
SECRET_KEY = env(  # noqa: F405
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-only-<value from DES-002>",
)
ALLOWED_HOSTS = env.list(  # noqa: F405
    "ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"]
)
DATABASES = {
    "default": env.db(  # noqa: F405
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"  # noqa: F405
    )
}
```

- `.env` is read **only** here. `read_env` uses `setdefault`, so shell and
  `docker run -e` values win.
- `DATABASE_URL` is how DES-008 step 1 runs the container against a local
  Postgres (`postgres://vae:vae@host.docker.internal:5432/vae`) without
  changing code. It's dev-only; `cloud.py` builds its database from the
  `GCP_CLOUDSQL_*` values so the hl_main contract stays the same.
- With no `.env` and no variables, this produces exactly the DES-002 dev
  settings.

### `test.py` and `build.py`

Unchanged from DES-002 and DES-008: fixed, non-secret values, and they don't
call `read_env` or Secret Manager. `test.py` inherits from `base`, not `dev`, so
it never sees `.env`.

### `cloud.py` and the secret loader

The loader goes in `hl_vae/cloudrun.py`, next to DES-008's
`deterministic_host`, as in hl_main. Keeping it out of `settings/` means it
can't be mistaken for a settings module, and it can be unit-tested with a fake
client.

```python
# hl_vae/cloudrun.py
import io

from django.core.exceptions import ImproperlyConfigured


def load_app_env(env, project_id, secret_name):
    """Load the .env-format secret into os.environ. Existing values win."""
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import secretmanager

    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = secretmanager.SecretManagerServiceClient().access_secret_version(name=name)
    except GoogleAPICallError as exc:
        raise ImproperlyConfigured(
            f"Can't read secret {name} ({exc.__class__.__name__}). Check that it has "
            "an enabled version and that the runtime service account can access it."
        ) from exc
    env.read_env(io.StringIO(response.payload.data.decode("utf-8")))
```

```python
# hl_vae/settings/cloud.py (secret and env parts only; DES-008 owns the rest)
from hl_vae.cloudrun import load_app_env

from .base import *  # noqa: F403

DEBUG = False

load_app_env(env, env("GCP_PROJECT_ID"), env("GCP_SECRETS_NAME"))  # noqa: F405

SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405
SECRET_KEY_FALLBACKS = env.list("DJANGO_SECRET_KEY_FALLBACKS", default=[])  # noqa: F405
# ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS and DATABASES from the catalogue above,
# exactly as in DES-008's app contract.
```

- The Google import is inside the function, so `dev`, `test` and `build`
  never import the client or touch the metadata server.
- The error names the secret path and the exception type only. It never
  includes the payload. Nothing in settings logs a value.
- The secret is read once, at import, from `versions/latest`. A new version
  takes effect on the next revision of the web service, and on the next
  execution of a job.
- The blob is read with `django-environ`'s parser: `KEY=value` per line,
  `#` comments, no `export`, and no shell expansion. Values with `#` or spaces
  are quoted.

### `.env.example` and `.gitignore`

- Commit `.env.example` at the repo root. It lists the **local** variables
  (`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`), all
  commented out, with one line saying what each does. It ends with a pointer to
  the hosted catalogue in `infra/README.md`. It contains no real values.
- `.gitignore`: replace the `.env` and `.env.dev` lines with:

  ```
  .env
  .env.*
  !.env.example
  ```

- `.dockerignore` (created in DES-008 step 1) must list `.env` and `.env.*`, so
  a developer's `.env` can't be copied into the image.

### What DES-008 must provide

These are already in DES-008. They're listed so this design can be checked
against it:

- Terraform creates the secret **container** `vae-stage-app-env` with automatic
  replication and no versions. Versions are added only with `gcloud`.
- Only `vae-stage-app` has `roles/secretmanager.secretAccessor` on the secret.
  `vae-stage-deploy` and Cloud Build don't.
- The web service and both jobs set `DJANGO_SETTINGS_MODULE`, `GCP_PROJECT_ID`
  and `GCP_SECRETS_NAME` as plain env vars. No secret is set as a plain env var
  or a Cloud Build substitution.
- No step in `deploy.yaml` reads the secret.

One addition for the module (see Open Questions): a `secret_managers` variable
listing the people who may add and disable versions. They get
`roles/secretmanager.secretVersionManager` and `roles/secretmanager.secretAccessor`
on that one secret only.

### Runbook

These go into `infra/README.md` (DES-008 creates it) under *Secrets*.

**Edit the blob safely.** Work in memory, never in the repo, and delete the
copy afterwards:

```bash
f=$(mktemp -p /dev/shm vae-env.XXXXXX)      # 0600, RAM-backed
gcloud secrets versions access latest --secret=vae-stage-app-env --project=hl-vae-stage > "$f"
$EDITOR "$f"
gcloud secrets versions add vae-stage-app-env --data-file="$f" --project=hl-vae-stage
rm -f "$f"
```

**Add a variable**

1. Read it in a settings module with `env(...)`. Use no default if stage needs it.
2. Add it to the catalogue in `infra/README.md`, and to `.env.example` if it's
   used locally.
3. Add a new secret version that includes it **before** promoting the code to
   `staging`. Otherwise the new revision fails at startup and the old one keeps
   serving.

**Apply a changed secret.** Re-run the deploy:
`gcloud builds triggers run vae-stage-deploy --branch=staging --project=hl-vae-stage`.
That creates a new web revision and repoints the jobs, and nothing drifts from
Terraform.

**Rotate `DJANGO_SECRET_KEY`**

1. Generate a key:
   `uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`.
2. In a new version, set `DJANGO_SECRET_KEY` to the new key and
   `DJANGO_SECRET_KEY_FALLBACKS` to the old one. Apply.
3. After two weeks (Django's default session length), add a version with an
   empty `DJANGO_SECRET_KEY_FALLBACKS`. Apply.

On stage it's fine to skip the fallback and set only the new key. Everyone is
just logged out.

**Rotate the database password**

1. `gcloud sql users set-password vae --instance=vae-stage-sql --prompt-for-password --project=hl-vae-stage`.
   The instance must be running.
2. Add a version with the new `GCP_CLOUDSQL_PASSWORD`. Apply.

Requests fail between steps 1 and 2. That's acceptable on stage.

**Retire old versions.** After a change is verified, disable the previous
version (`gcloud secrets versions disable <n> --secret=vae-stage-app-env`).
Leave it disabled, not destroyed, for 30 days so it can be re-enabled to roll
back, then destroy it.

**If a secret leaks**, rotate that value now using the steps above, disable
every version that contained it, and check who had access with
`gcloud secrets get-iam-policy vae-stage-app-env --project=hl-vae-stage`. If it
leaked into git, rotating it is the fix. Rewriting history isn't required.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Plain `os.environ` reads | No dependency | No casting (`bool`, lists, DB URLs); every read reinvents defaults and errors | `django-environ` is already in the DES-008 contract and in hl_main |
| `python-dotenv` for `.env`, separate parsing | Popular | Two libraries for one job; no casting | `django-environ` does both |
| `pydantic-settings` | Typed, validated config object | New pattern, not used in hl_main; overlaps with Django settings | Same tool as hl_main |
| One secret per value, mounted by Cloud Run (`secret_key_ref`) | No client library or import-time API call; per-value IAM | One Terraform resource and env entry per value; adding a variable means a Terraform change; diverges from hl_main | The single blob is the agreed DES-008 contract, and stage has under ten values |
| Non-secret values (`GCP_REGION`, private IP) as Terraform env vars | Fewer manual edits | Config split across two places; the service URL is circular in Terraform | One place to look. The deterministic host covers the URL |
| Pin a secret version number in Terraform instead of `latest` | Explicit rollout and rollback in git | Every secret change needs a Terraform apply too | `latest` plus a redeploy is simpler; disabled versions give rollback |
| Read `.env` in `base.py` (every environment) | One code path | A developer's `.env` changes test results; a stray `.env` in an image changes stage | Read it only in `dev.py` |
| Env-driven `DEBUG` on hosted environments | Easy to debug stage | One secret edit exposes tracebacks and settings | Security switches stay in code |
| Commit encrypted secrets (SOPS, git-crypt) | Secrets versioned with code | Key management for every developer; secrets in the repo | Secret Manager and IAM already exist |

## Implementation Plan

In two parts, each on a branch off `develop`.

**Local half**, after DES-002 and before DES-008 step 1:

- [x] Add `django-environ` to `[project] dependencies` in `pyproject.toml`,
  and run `uv lock`.
- [x] Add `env = environ.Env()` to `base.py`.
- [x] Change `dev.py` to the version above: optional `.env`, `DJANGO_DEBUG`,
  `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`.
- [x] Add `.env.example` and update `.gitignore`.
- [x] Add the `.env` and `DATABASE_URL` tests below.
- [x] Update `README.md`: copy `.env.example` to `.env` to override dev
  settings; nothing is needed by default.

**Cloud Run half**, as part of DES-008 step 1:

- [x] Add `google-cloud-secret-manager` to `[project] dependencies`, and run
  `uv lock`.
- [x] Add `load_app_env` to `hl_vae/cloudrun.py` (next to `deterministic_host`,
  per the DES-008 app contract), and call it from `cloud.py` with `SECRET_KEY`
  and `SECRET_KEY_FALLBACKS` read as above.
- [x] Make sure DES-008's `.dockerignore` lists `.env` and `.env.*`.
- [x] Add the `load_app_env` tests below.
- [x] Add the catalogue and runbook to `infra/README.md`, and the
  `secret_managers` variable to `modules/vae-env` (once its value is decided).

## Testing / Verification

Automated, in `uv run pytest` with no network and no GCP credentials:

- `load_app_env` with a fake `SecretManagerServiceClient` (monkeypatched):
  - loads `KEY=value` lines into `os.environ`;
  - doesn't overwrite a variable that's already set;
  - turns a `GoogleAPICallError` into `ImproperlyConfigured` whose message has
    the secret path and no payload.
- With a `.env` in a temp directory containing `DJANGO_SECRET_KEY=from-dotenv`,
  test settings still have `SECRET_KEY == "test-only-not-secret"`.
- Importing `dev.py` with `DATABASE_URL=postgres://u:p@h:5432/d` set gives the
  Postgres engine, and with it unset gives SQLite at the repo root.

Manual:

- Fresh clone, no `.env`: `uv run python manage.py runserver` works (the DES-002
  check still passes).
- `cp .env.example .env`, set `DJANGO_DEBUG=false` and
  `ALLOWED_HOSTS=localhost`: `diffsettings` shows both.
- `git check-ignore .env .env.local` lists both; `git check-ignore .env.example`
  lists nothing.
- `docker build .`, then listing the app directory in the image shows no `.env`.
- On stage, after the first deploy:
  - `gcloud run jobs execute vae-stage-manage --args=manage.py,check,--deploy`
    passes (shows the key and DEBUG come from the right places).
  - Remove a required key in a new secret version and re-run the deploy: the
    migrate step fails with `Set the GCP_CLOUDSQL_PASSWORD environment variable`
    (or similar) and the previous web revision keeps serving. Then restore the
    version.
  - `gcloud secrets get-iam-policy vae-stage-app-env` shows accessor only for
    `vae-stage-app` and the named secret managers.
  - The Cloud Build log for a deploy contains no secret values.

## Open Questions

- Who goes in `secret_managers` (allowed to read the blob and add or disable
  versions)? Proposed: the two project authors. Until it's decided, project
  owners can do it through their owner role.
- Should Secret Manager Data Access audit logs (`DATA_READ`) be turned on for
  `hl-vae-stage`, so every read of the secret is logged? It's cheap at this
  volume. It's off by default, as it is in hl_main.

## Changelog

- 2026-11-08 — Created.
- 2026-11-08 — Implementation split into a local half (before DES-008) and a Cloud Run half (with DES-008 step 1). `deterministic_host` is now defined in DES-008's app contract.
- 2026-11-10 — Local half implemented on `feature/env-config-DES-003`. Details:
  - Installed `django-environ` 0.14.0 (`>=0.14,<0.15`).
  - With no `.env`, the dev settings are unchanged. The only difference is that `DATABASES["default"]["NAME"]` is now a string rather than a `Path`.
  - `dev.py` has no `# noqa: F405` comments, because `pyproject.toml` already ignores F403/F405 in settings (DES-005).
  - Tests in `works/tests.py`:
    - they reload `dev.py` with a controlled environment (dev defaults, `DATABASE_URL`, overrides);
    - one test points `BASE_DIR` at a temp `.env` to show that shell values win over `.env`;
    - one runs a subprocess with a `.env` in its working directory to show that test settings ignore it.
  - A `postgres://` `DATABASE_URL` parses correctly, but `manage.py` needs `psycopg`, which DES-008 step 1 adds. `.env.example` and the README say so.
  - The Cloud Run half stays with DES-008 step 1.
- 2026-11-10 — Local half done (PR #8). Cloud Run half implemented with DES-008 step 1 on `feature/cloud-run-app-DES-008`. Details:
  - Installed `google-cloud-secret-manager` 2.32.0.
  - `load_app_env` matches the design. The client is created in a small `_secret_client()` helper so tests can swap in a fake.
  - `cloud.py` also drops empty entries from `DJANGO_SECRET_KEY_FALLBACKS` and `ALLOWED_HOSTS`, since the blob sets `ALLOWED_HOSTS=` empty on stage.
  - Tests are in `hl_vae/tests/`:
    - `load_app_env`: loading, existing values win, and the error names the secret path;
    - `cloud.py` and `stage.py` with a fake secret: a missing required value fails at import, and the secret can't turn `DEBUG` on;
    - a subprocess check that `build.py` needs no env and doesn't import the Google client.
  - Still open, and waiting for DES-008 step 2: the catalogue and runbook in `infra/README.md`, and the `secret_managers` variable.
- 2026-11-10 — Cloud Run half merged in PR #9. The catalogue and runbook are now in `infra/README.md`, and `modules/vae-env` has the `secret_managers` variable on `feature/terraform-DES-008`. It defaults to `[]`; the open question about who goes in it is still open. The doc stays in `active/` until the stage checks under Testing / Verification have been run after the first deploy.
