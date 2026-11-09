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

---

## Backlog

| ID | Title | Area | Doc | Updated | Status |
|---|---|---|---|---|---|
| DES-001 | Design docs system | Process | [doc](archive/DES-001-design-docs-system.md) | 2026-11-08 | Done |
| DES-002 | Settings package (base / dev / stage / prod) | Infrastructure | [doc](designed/DES-002-settings-split.md) | 2026-11-08 | Designed |
| DES-003 | Environment config and secrets management | Infrastructure | [doc](designed/DES-003-env-config-and-secrets.md) | 2026-11-08 | Designed |
| DES-004 | Database choice (PostgreSQL vs SQLite) | Infrastructure | merged into [DES-008](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Dropped |
| DES-005 | CI pipeline: tests and lint | Infrastructure | | 2026-11-08 | Idea |
| DES-006 | Static files and asset handling | Infrastructure | | 2026-11-08 | Idea |
| DES-007 | Deployment target and process | Infrastructure | merged into [DES-008](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Dropped |
| DES-008 | GCP infrastructure (stage on Cloud Run) | Infrastructure | [doc](designed/DES-008-gcp-infrastructure.md) | 2026-11-08 | Designed |
| DES-009 | Custom domain: veteranacademicexchange.org | Infrastructure | | 2026-11-08 | Idea |
