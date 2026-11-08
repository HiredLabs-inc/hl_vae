# DES-001: Design docs system

- **Status:** Done
- **Area:** Process
- **Created:** 2026-11-08
- **Updated:** 2026-11-08
- **Related:** branch `design/template-001`

## Summary

A two-layer documentation system in `docs/`: index files that list every item
by phase, plus one design doc per item, filed in a directory that matches its
phase.

## Motivation / Problem

The project is only a basic Django framework so far. From here on, design docs
will drive the build, starting with infrastructure. Without a single place to
see every planned, active, and finished piece of work, design docs drift and
get lost.

## Goals and Non-goals

**Goals**

- One place to see all work at a glance, grouped by phase.
- Bugs tracked in a separate index with the same format.
- Every item past the rough-idea phase has its own doc, in a directory that
  matches its phase.

**Non-goals**

- Replacing an issue tracker or adding tooling or automation. This is plain
  Markdown in git.

## Proposed Design

**Layer 1: index files**

- [`docs/backlog.md`](../backlog.md) lists features and infrastructure work
  in the phases Idea → Designed → In Progress → Done, plus Dropped.
- [`docs/buglog.md`](../buglog.md) lists bugs in the phases Reported →
  Triaged → Fixing → Closed.

Each phase has its own section with a table: `| ID | Title | Area | Doc | Updated |`.

**Layer 2: per-item docs**

```
docs/
├── backlog.md
├── buglog.md
├── designed/        # DES docs: designed, not started
├── active/          # DES docs: in progress
├── archive/         # DES docs: done or dropped
├── bugfixes/
│   ├── open/        # BUG docs: triaged or fixing
│   └── closed/      # BUG docs: fixed or won't fix
└── templates/
    ├── design-template.md
    └── bugfix-template.md
```

Ideas and new bug reports are a single row in the index, with no doc yet.

**Conventions**

- IDs are `DES-NNN` and `BUG-NNN`. They're sequential and never reused.
- File names follow `<ID>-<kebab-slug>.md`.
- To change an item's phase, `git mv` its doc, update the `Status:` line, and
  move its row in the index, all in one commit.

## Alternatives Considered

| Option | Pros | Cons | Why not |
|---|---|---|---|
| Single flat `docs/` folder with status in front matter | No file moves | Hard to see what's active at a glance | Directory-per-phase was requested and is easier to browse |
| External tracker (GitHub Issues/Projects) | Rich tooling | Design lives apart from code; harder for agents to read | Keep design versioned alongside code |

## Implementation Plan

- [x] Create `backlog.md` and `buglog.md` with phase sections
- [x] Create phase directories (with `.gitkeep`)
- [x] Add design and bugfix templates
- [x] Seed backlog with infrastructure ideas
- [x] Link from `README.md`

## Testing / Verification

- `find docs -type f | sort` matches the layout above.
- All relative links in the index files resolve to existing files or directories.

## Open Questions

- None.

## Changelog

- 2026-11-08 — Created and implemented.
