# Buglog

Master index of all bugs for Veteran Academic Exchange. Feature and
infrastructure work is tracked separately in [backlog.md](backlog.md).

## How this works

| Phase | Meaning | Individual doc lives in |
|---|---|---|
| Reported | One-line report; a single row here, no doc yet | — |
| Triaged | Investigated; root cause and fix written up | [`bugfixes/open/`](bugfixes/open/) |
| Fixing | Fix underway | [`bugfixes/open/`](bugfixes/open/) |
| Closed | Fixed or Won't Fix | [`bugfixes/closed/`](bugfixes/closed/) |

**Conventions**

- **IDs:** `BUG-001`, `BUG-002`, … — sequential, never reused. Next free ID: **BUG-001**.
- **File names:** `<ID>-<kebab-slug>.md`, e.g. `bugfixes/open/BUG-001-login-redirect-loop.md`.
- **Triaging a report:** copy [`templates/bugfix-template.md`](templates/bugfix-template.md)
  into `bugfixes/open/`, fill it in, and link it from the row (moving the row to *Triaged*).
- **Changing phase:** update the doc's `Status:` line, move the row to the matching
  section below, and when closing, `git mv` the doc into `bugfixes/closed/` and fix
  the link — all in one commit.

---

## Reported

| ID | Title | Area | Doc | Updated |
|---|---|---|---|---|

## Triaged

| ID | Title | Area | Doc | Updated |
|---|---|---|---|---|

## Fixing

| ID | Title | Area | Doc | Updated |
|---|---|---|---|---|

## Closed

| ID | Title | Area | Doc | Updated |
|---|---|---|---|---|
