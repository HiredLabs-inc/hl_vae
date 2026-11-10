# DES-005: CI pipeline (tests and lint)

- **Status:** In Progress
- **Area:** Infrastructure
- **Created:** 2026-11-08
- **Updated:** 2026-11-10
- **Related:** depends on DES-002 (`hl_vae.settings.test`, pytest config, smoke test). Complements DES-008 (Cloud Build deploys `staging`; this checks code before it gets there, and lints `infra/terraform`). Branch `design/ci-pipeline-005`.

## Summary

Every pull request and every push to `develop`, `staging` and `main` runs one
GitHub Actions workflow. It checks formatting and lint with **Ruff**, runs
Django's system and migration checks, and runs the **pytest** suite against the
DES-002 test settings. A second, path-filtered workflow runs
`terraform fmt` and `validate` on `infra/terraform/`. Branch protection on
`staging` and `main` requires the main check to pass, so nothing reaches stage
without it.

## Motivation / Problem

Today nothing runs automatically. There are no lint rules, no formatter, and
`works/tests.py` is empty. DES-002 adds the first real test, and DES-008 adds a
deploy that fires on every push to `staging`. Without CI:

- A broken commit on `develop` is found only when someone runs it locally, or
  when Cloud Build migrates and deploys it to stage.
- Style drifts between the two authors, and review time goes on formatting.
- A model change without a migration can be promoted and then fail the
  `vae-stage-migrate` job, or worse, deploy with a schema that doesn't match
  the code.

hl_main has no CI or linter to copy, so this design sets the pattern.

## Goals and Non-goals

**Goals**

- One required status check, `CI / checks`, that gates merges and promotion.
  (GitHub lists it as `CI / checks`; in the branch-protection picker the
  context is the job name, `checks`.)
- The same commands run locally and in CI, through `uv run`, with versions
  pinned by `uv.lock`.
- Fast: under 2 minutes for a typical run, with the uv cache.
- Catch missing migrations and a stale `uv.lock` before they reach stage.
- Lint the DES-008 Terraform once it exists, without slowing app-only changes.
- No secrets and no cloud access in CI.

**Non-goals**

- Deploying. Cloud Build owns deploys (DES-008). CI doesn't call GCP.
- Building the Docker image in CI. Cloud Build builds it on `staging`;
  revisit if Dockerfile breakage becomes a real problem.
- Running tests against Postgres. Tests use SQLite through `test.py`
  (DES-002). See Open Questions.
- Type checking (mypy/pyright), security scanning, and automated dependency
  updates (Dependabot). Each can be its own item later.
- A coverage threshold. Coverage is reported, not enforced, while the suite is
  this small.
- A pre-commit framework. The README gives the one-line local command instead.

## Proposed Design

### Platform: GitHub Actions

`HiredLabs-inc/hl_vae` is **public**, so standard GitHub-hosted runners are free
with no minute limit. Status checks, PR annotations and branch protection are
native. CI also works now, before any of DES-008's GCP infrastructure exists.
Actions is already enabled on the repo (checked 2026-11-08).

### Workflows

```
.github/
└── workflows/
    ├── ci.yml          # app checks: always runs, required
    └── terraform.yml   # infra checks: runs only when infra/terraform/** changes, not required
```

**Triggers (both workflows)**

| Event | Branches |
|---|---|
| `pull_request` | targeting `develop`, `staging`, `main` |
| `push` | `develop`, `staging`, `main` |
| `workflow_dispatch` | manual re-run |

`terraform.yml` adds `paths: ["infra/terraform/**", ".github/workflows/terraform.yml"]`
to both events. `ci.yml` has **no** path filter. A required check that's
skipped by a path filter stays pending forever and blocks the merge, so the
required workflow always runs. A docs-only change costs about a minute, which
is fine.

**Common settings**

- `permissions: contents: read`. No write tokens, no `id-token`.
- `concurrency: group: ${{ github.workflow }}-${{ github.ref }}`, with
  `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so only
  superseded PR runs are cancelled. Pushes to protected
  branches always finish, so every commit on `develop` has a result.
- `runs-on: ubuntu-latest`, `timeout-minutes: 10`.
- Third-party actions are pinned to a full commit SHA, with the version in a
  trailing comment (`# v4.2.2`). Tags can be moved; SHAs can't.

### `ci.yml`: job `checks`

Environment for every step: `DJANGO_SETTINGS_MODULE=hl_vae.settings.test`.

| # | Step | Command | Catches |
|---|---|---|---|
| 1 | Checkout | `actions/checkout` | |
| 2 | Set up uv and Python | `astral-sh/setup-uv` with `enable-cache: true`, `python-version: "3.12"` | |
| 3 | Install | `uv sync --locked --extra dev` | `uv.lock` out of sync with `pyproject.toml` (`--locked` fails instead of re-locking) |
| 4 | Format | `uv run ruff format --check .` | Unformatted code |
| 5 | Lint | `uv run ruff check --output-format=github .` | Lint errors, shown as inline PR annotations |
| 6 | Django checks | `uv run python manage.py check --fail-level WARNING` | Broken settings, URL or model config |
| 7 | Migrations | `uv run python manage.py makemigrations --check --dry-run` | Model changes without a migration |
| 8 | Tests | `uv run pytest --cov --cov-report=term-missing` | Test failures; coverage shown in the log |

Step 3 has `id: install`. Steps 4–8 use
`if: (success() || failure()) && steps.install.outcome == 'success'`, so one
run reports every failing check, not just the first, but nothing runs if
install fails.

Python is **3.12 only**, matching `requires-python` and the DES-008
`python:3.12-slim` image. There is no version matrix.

`.python-version` is in `.gitignore`, so CI sets the version explicitly in
step 2 rather than reading the file.

### `terraform.yml`: job `terraform`

Runs only when DES-008's `infra/terraform/` changes. Until that directory
exists, the workflow never triggers.

| # | Step | Command |
|---|---|---|
| 1 | Checkout | `actions/checkout` |
| 2 | Set up Terraform | `hashicorp/setup-terraform`, version matching DES-008's `>= 1.5` pin |
| 3 | Format | `terraform fmt -check -recursive infra/terraform` |
| 4 | Validate | for each root (`shared`, `envs/stage`): `terraform init -backend=false` then `terraform validate` |

`-backend=false` means no GCS state access and no credentials. `plan` and
`apply` stay manual, as DES-008 describes. This job isn't a required check,
because of the path-filter problem above. A failing run still shows a red X
on the PR.

### Ruff configuration

Ruff replaces flake8, isort and black with one fast tool. Config goes in
`pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88
extend-exclude = [".venv"]

[tool.ruff.lint]
select = [
  "E", "W",   # pycodestyle
  "F",        # pyflakes
  "I",        # isort
  "B",        # flake8-bugbear
  "UP",       # pyupgrade
  "DJ",       # flake8-django
  "SIM",      # flake8-simplify
]

[tool.ruff.lint.per-file-ignores]
"*/migrations/*.py" = ["E501"]   # generated; long lines are fine
"hl_vae/settings/*.py" = ["F403", "F405"]  # star imports between settings modules (DES-002)

[tool.ruff.lint.isort]
known-first-party = ["hl_vae", "works"]
```

- The rule set is deliberately small. It catches real bugs (`F`, `B`) and
  Django mistakes (`DJ`, e.g. `null=True` on a `CharField`) without a long
  tail of style rules. Add rules later with a dedicated cleanup commit.
- Migrations are formatted and linted except for line length, so generated
  code stays consistent.
- The settings ignores replace the per-line `# noqa: F403`/`F405` comments
  in DES-002's examples. Either works; the file-level ignore is less noise.

### Test configuration

DES-002 adds `[tool.pytest.ini_options]` with
`DJANGO_SETTINGS_MODULE = "hl_vae.settings.test"`. This design adds:

```toml
[tool.pytest.ini_options]
# from DES-002
DJANGO_SETTINGS_MODULE = "hl_vae.settings.test"
python_files = ["tests.py", "test_*.py"]
# added here
addopts = "--strict-markers"
testpaths = ["works", "hl_vae"]

[tool.coverage.run]
source = ["hl_vae", "works"]
omit = ["*/migrations/*", "hl_vae/asgi.py", "hl_vae/wsgi.py"]
```

`--cov` is passed in CI, not in `addopts`, so local `uv run pytest` stays
fast and doesn't print a report unless asked.

pytest exits with code 5 when it collects no tests. DES-002's smoke test means
the suite is never empty, so CI doesn't need to special-case that.

### Dependencies

Added to the `dev` extra in `pyproject.toml`, exact versions pinned by `uv.lock`:

- `ruff`
- `pytest-cov`

`pytest` and `pytest-django` are already there.

### Local parity

The README gets one command that runs what `CI / checks` runs:

```bash
uv run ruff format . && uv run ruff check --fix . && uv run python manage.py makemigrations --check --dry-run && uv run pytest
```

Local commands format and fix; CI only checks. Editors can use the Ruff
extension and pick up the `pyproject.toml` config.

### Branch protection and promotion

Protection is set by hand in GitHub settings (it's not in Terraform or the repo):

| Branch | Rule |
|---|---|
| `develop` | Require a pull request; require status check `CI / checks` |
| `staging` | Require status check `CI / checks`; no PR required |
| `main` | Require a pull request; require status check `CI / checks` |

DES-008 promotes with `git push origin develop:staging`, which is a direct push,
not a PR. GitHub allows a direct push to a branch with required checks when
the pushed commit has **already passed** those checks on another branch. The
push to `develop` runs CI on the same SHA, so promoting a green commit works
and promoting a red or still-running one is rejected. That gates the DES-008
Cloud Build deploy without any change to Cloud Build.

```
PR ──CI──▶ develop ──CI (push)──▶ git push develop:staging ──(rejected unless green)──▶ staging ──Cloud Build──▶ vae-stage-web
```

The `staging` branch doesn't exist yet. DES-008's bootstrap creates it, and
its protection rule is added then.

### First-run cleanup

Turning on Ruff over existing code will produce changes. Those go in **one
commit** that only runs `ruff format .` and `ruff check --fix .`, with no other
edits. Its SHA is added to a new `.git-blame-ignore-revs` file, so
`git blame` skips it (GitHub honours that file automatically).

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Cloud Build PR trigger in `hl-vae-stage` | Same tool as deploys; GitHub App connection already planned in DES-008 | Needs DES-008 bootstrapped first; billed build minutes; slower PR feedback; annotations are weaker | Actions is free for a public repo and works today |
| Run tests as a step in DES-008's `deploy.yaml` | One pipeline | Feedback only after promotion; nothing checks PRs | Too late; a failed deploy is the wrong place to find a test failure |
| flake8 + isort + black | Familiar | Three tools, three configs, slower | Ruff does all three in one |
| pre-commit framework | Catches issues before push | Another tool to install; easy to bypass with `--no-verify` | CI is the source of truth; README command is enough for two developers |
| Postgres service container for tests | Matches stage's database | Slower; `test.py` would need DB env vars; nothing Postgres-specific in the app yet | Revisit when a feature uses Postgres-only behaviour (see Open Questions) |
| Python version matrix | Catches version issues | Doubles run time for a single deploy target | Only 3.12 is deployed |
| Path filters on `ci.yml` | Skips docs-only changes | A skipped required check blocks merges | A minute of CI on docs PRs is cheaper than the workaround |
| Coverage threshold | Prevents coverage regressions | Arbitrary number on a near-empty suite | Report now; add a floor once there's real code |

## Implementation Plan

Lands after DES-002 **and DES-006**, on a branch off `develop`.

> **Note (from DES-002 implementation, 2026-11-08):** with the DES-002
> settings loading, `manage.py check` warns `staticfiles.W004` because
> `static/` doesn't exist yet. Step 6 runs with `--fail-level WARNING`, so it
> fails until DES-006 adds `static/.gitkeep`. Land DES-006 first, or this PR
> starts red.

- [ ] Add `ruff` and `pytest-cov` to the `dev` extra; run `uv lock`.
- [ ] Add `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.coverage.run]` and the
  extra pytest options to `pyproject.toml`.
- [ ] Commit the formatting-only cleanup on its own, then add its SHA to
  `.git-blame-ignore-revs` in the next commit.
- [ ] Add `.github/workflows/ci.yml` with job `checks`.
- [ ] Add `.github/workflows/terraform.yml` (dormant until `infra/terraform/` exists).
- [ ] Add the local check command and a CI section to `README.md`.
- [ ] Open the PR and confirm `CI / checks` runs and passes.
- [ ] **By hand (user):** add branch protection on `develop` and `main`
  requiring `CI / checks`. Add the `staging` rule when DES-008's bootstrap
  creates the branch.

## Testing / Verification

- `CI / checks` passes on the implementing PR and on the resulting push to `develop`.
- Each check fails when it should. On a throwaway branch, confirm separately:
  - An unformatted file fails step 4.
  - An unused import fails step 5, with an annotation on the PR diff.
  - A new model field without a migration fails step 7.
  - A failing assertion fails step 8.
  - Editing `pyproject.toml` dependencies without `uv lock` fails step 3.
  - All failing steps report in the same run (not just the first).
- A docs-only PR still runs and passes `CI / checks`.
- `terraform.yml` doesn't run on an app-only PR. Once `infra/terraform/`
  exists, an unformatted `.tf` file fails it.
- With protection on, `git push origin <red-sha>:staging` is rejected, and the
  same push of a green `develop` SHA succeeds.
- A typical run finishes in under 2 minutes with a warm uv cache.
- The workflow logs show no secrets in use, and the token has `contents: read` only.

## Open Questions

- Should tests run against Postgres too? Not now: the app has no
  Postgres-specific code. Revisit when a feature uses Postgres-only behaviour
  (e.g. `JSONField` lookups, full-text search, `ArrayField`); then add a
  `postgres` service container and a CI-only settings override.
- Should `develop` require a PR, or allow direct pushes with the status check
  only? This design assumes PRs, matching how design branches are merged today.
  The user decides when setting branch protection.

## Changelog

- 2026-11-08 — Created.
- 2026-11-08 — Noted from the DES-002 implementation: step 6 fails on `staticfiles.W004` until DES-006 lands, so this now lands after DES-006 too.
