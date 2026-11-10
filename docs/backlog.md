# Backlog

Master index of all design work for Veteran Academic Exchange. Every feature,
infrastructure task, or refactor gets a row here. Bugs are tracked separately in
[buglog.md](buglog.md).

## How this works

| Phase | Meaning | Individual doc lives in |
|---|---|---|
| Idea | Rough idea; a single row here, no doc yet | — |
| Designed | Design doc written and agreed; not started | [`designed/`](designed/) |
| In Progress | Actively being built | [`active/`](active/) |
| Done | Shipped | [`archive/`](archive/) |
| Dropped | Rejected or abandoned after design; kept for the record | [`archive/`](archive/) |

**Conventions**

- **IDs:** `DES-001`, `DES-002`, … — sequential, never reused. Next free ID: **DES-010**.
- **File names:** `<ID>-<kebab-slug>.md`, e.g. `designed/DES-002-settings-split.md`.
- **Promoting an idea:** copy [`templates/design-template.md`](templates/design-template.md)
  into `designed/`, fill it in, and link it from the row (moving the row to *Designed*).
- **Changing phase:** `git mv` the doc into the new phase's directory, update its
  `Status:` line, move the row to the matching section below, and fix the link —
  all in one commit.
- **Merging (from 2026-11-10):** nothing is merged into `develop` directly any
  more. Every change — design, implementation or docs — goes on its own branch
  and reaches `develop` only through a pull request that's opened and reviewed
  first. Nothing touches `main` outside a PR either.

---

## Implementation order

Reviewed 2026-11-10 across every *Designed* doc. Each step is its own branch
off `develop` and its own PR; start a step only after the previous one is
merged.

1. **[DES-006](archive/DES-006-static-files.md) — Static files.** Done (PR #3). Depends only
   on DES-002 (done). Goes first because it adds `static/.gitkeep`: until then
   `manage.py check` warns `staticfiles.W004`, which fails DES-005's CI. It also
   supplies the WhiteNoise settings, `collectstatic` step and `build.py`
   docstring that DES-008 step 1 needs.
2. **[DES-005](archive/DES-005-ci-pipeline.md) — CI pipeline.** Done (PR #5); `CI / checks` is required on `develop` and `main`. Needs DES-002
   and DES-006, nothing else (it doesn't call GCP). Doing it early means every
   later PR is checked by `CI / checks`, which suits the PR-only rule above,
   and its formatting-only ruff cleanup lands before the bigger changes, so
   later branches don't conflict with it. The Terraform workflow stays dormant
   until DES-008 adds `infra/terraform/`. Afterwards the user adds branch
   protection on `develop` and `main` by hand.
3. **[DES-003](designed/DES-003-env-config-and-secrets.md) — local half.**
   Needs DES-002. Adds `django-environ`, the `env` reader, `.env.example` and
   `DATABASE_URL` in `dev.py`. Independent of DES-005, so it could swap places
   with step 2, but it's better tested once CI exists. It must land before
   DES-008 step 1, which runs the container against Postgres via
   `DATABASE_URL`.
4. **[DES-008](designed/DES-008-gcp-infrastructure.md) — GCP infrastructure,
   together with DES-003's Cloud Run half.** DES-008 step 1 starts only after
   DES-002, DES-006 and DES-003's local half are merged; DES-003's Cloud Run
   half (`load_app_env`, `google-cloud-secret-manager`, the secrets runbook in
   `infra/README.md`) is done inside that step. Steps 2–7 follow the DES-008
   plan; step 3 (bootstrap) is done by hand by the user. Once the bootstrap
   creates `staging`, add its branch-protection rule from DES-005.
5. **DES-009 — Custom domain.** Still an *Idea*: it needs a design doc first,
   and it builds on DES-008 (load balancer / domain mapping, and possibly
   Cloud CDN from DES-006's deferred options). Not ready to implement.

```
DES-002 (done) ─► DES-006 (done) ─► DES-005 (done) ─► DES-003 local ─► DES-008 + DES-003 Cloud Run half ─► DES-009 (needs design)
```

---

## Backlog

| ID | Title | Area | Doc | Updated | Status |
|---|---|---|---|---|---|
| DES-001 | Design docs system | Process | [doc](archive/DES-001-design-docs-system.md) | 2026-11-08 | Done |
| DES-002 | Settings package (base / dev / stage / prod) | Infrastructure | [doc](archive/DES-002-settings-split.md) | 2026-11-08 | Done |
| DES-003 | Environment config and secrets management | Infrastructure | [doc](designed/DES-003-env-config-and-secrets.md) | 2026-11-08 | Designed |
| DES-004 | Database choice (PostgreSQL vs SQLite) | Infrastructure | merged into [DES-008](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Dropped |
| DES-005 | CI pipeline: tests and lint | Infrastructure | [doc](archive/DES-005-ci-pipeline.md) | 2026-11-10 | Done |
| DES-006 | Static files and asset handling | Infrastructure | [doc](archive/DES-006-static-files.md) | 2026-11-10 | Done |
| DES-007 | Deployment target and process | Infrastructure | merged into [DES-008](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Dropped |
| DES-008 | GCP infrastructure (stage on Cloud Run) | Infrastructure | [doc](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Designed |
| DES-009 | Custom domain: veteranacademicexchange.org | Infrastructure | | 2026-11-08 | Idea |
