# DES-011: Dimension tables (work types, institutions, subjects, disciplines, topics, publications)

- **Status:** Done
- **Area:** Works
- **Created:** 2026-11-17
- **Updated:** 2026-11-18
- **Related:** comes before the `Work` model, which will reference these tables. Builds on [DES-010](DES-010-frontend-foundation-and-home-page.md) (the `/works/` page) and runs on the stage set up in [DES-008](DES-008-gcp-infrastructure.md).

## Summary

Add six lookup ("dimension") tables to the `works` app: work types,
institutions, subjects, disciplines, topics and publications. Each one is a
plain list of unique names, managed in Django admin. This is the first backend
step toward a real `/works/` page.

## Motivation / Problem

- `works/models.py` is empty, and `works_view` passes a hard-coded
  `[1, 2, 3]` list.
- The planned `Work` model will have foreign keys to these six tables. A
  migration can't reference a table that doesn't exist, and a work can't be
  saved without rows to point at. So the tables, and a way to fill them, have
  to come first.
- Keeping these values in their own tables means one spelling per value, a
  rename in one place, and ready-made lists for later filters and dropdowns.

## Goals and Non-goals

**Goals**

- Six models in `works/models.py`: `WorkType`, `Institution`, `Subject`,
  `Discipline`, `Topic` and `Publication`. Each is written out on its own,
  with no shared base class, and each has:
  - `name`: up to 120 characters, unique within its table;
  - default ordering by `name`;
  - `__str__` returning `name`, so admin and dropdowns show the name.
- All six registered in `works/admin.py`, listing and searching by name.
  Searching by name also lets a later `Work` admin use autocomplete.
- One initial migration, `works/migrations/0001_initial.py`.

**Non-goals**

- The `Work` model.
- Authors and accounts. These will be designed later, together with
  authentication and login.
- Media and file uploads.
- Any view, URL or template change.
- Seed data.
- A hierarchy between subject, discipline and topic. All three are
  independent lists. A parent link can be added later as a nullable foreign
  key without moving data.

## Proposed Design

- **Models:** six independent tables, each holding an auto `id` (the
  project's `DEFAULT_AUTO_FIELD`) and a unique `name`. There are no
  relationships between them.
- **Admin:** each model gets a `ModelAdmin` with `list_display` and
  `search_fields` set to `name`.
- **Migration:** created with `makemigrations`. Stage applies it
  automatically, because the `vae-stage-migrate` job runs on every deploy
  (`infra/cloudbuild/deploy.yaml`).
- **Data entry:** by hand in Django admin. A stage superuser is created with
  `createsuperuser --no-input` through the `vae-stage-manage` job, as
  `infra/README.md` describes.

No settings or infra changes are needed.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| A shared abstract base class | Less repetition | Less explicit, and one change affects every table | Kept each model separate by choice |
| Subject, discipline and topic as a hierarchy | Models how topics nest | More foreign keys and rules before any real data exists | Flat is enough to start, and a parent link can be added later |
| Plain text fields on `Work` | No extra tables | Inconsistent spellings, no shared lists | Lookups keep values consistent |

## Implementation Plan

- [x] Add the six models to `works/models.py`.
- [x] Register them in `works/admin.py`.
- [x] Run `makemigrations` to create `works/migrations/0001_initial.py`.
- [x] Add the tests below to `works/tests.py`.
- [x] In `docs/backlog.md`, move DES-011 to *In Progress* and then *Done*, as the conventions describe.
- [x] Run the README's *Check your work before pushing* command, then open a
  PR into `develop`.

## Testing / Verification

**Automated (`uv run pytest`; `CI / checks` on the PR)**, run for each of the six models:

- `__str__` returns the name.
- A duplicate name raises `IntegrityError`.
- Rows come back ordered by name.
- The admin changelist returns 200 for a superuser.
- Coverage stays at 100%, and `makemigrations --check` passes in CI.

**Manual**

- `uv run python manage.py runserver`: all six tables appear in `/admin/`,
  and rows can be added, searched and edited.
- After the PR is promoted to stage, the migration has run and the tables
  appear in stage admin.

## Open Questions

- Should starting values be seeded with a data migration or a fixture?
- Should subject, discipline and topic get parent links later?

## Changelog

- 2026-11-17 — Created. Flat dimension tables only. Authors are left out and will be designed later, together with authentication and login.
- 2026-11-18 — Implemented on `feature/dimension-tables-01` (PR #20). It differs from the design:
  - `Topic` has no `name`. It links a `Subject` and a `Discipline` (both optional foreign keys, `CASCADE` on delete). This adds the subject/discipline/topic hierarchy that the design listed as a non-goal.
  - `Subject`, `Discipline` and `Topic` have no default ordering.
  - `__str__` includes the row id (for example `Engineering 3`), and `Topic` shows `discipline , subject , #id`.
  - Admin uses the plain default registration, with no `list_display` or `search_fields`.
  - There are five migrations (`0001`–`0005`) rather than a single `0001_initial.py`.
  - Tests are in `works/test_models.py` and cover `__str__` only, enough for 100% coverage. The duplicate-name, ordering and admin checks weren't added.

  Archived.
