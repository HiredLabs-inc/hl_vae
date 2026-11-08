# BUG-001: `.idea/` files still tracked in git

- **Status:** Fixed <!-- Triaged | Fixing | Fixed | Won't Fix -->
- **Severity:** Low
- **Area:** Infrastructure
- **Reported:** 2026-11-08
- **Updated:** 2026-11-08
- **Related:** branch `design/template-001`; commits `433e558`, `bcdac32`, `3baa67d`

## Symptoms

JetBrains IDE files under `.idea/` (`hl_vae.iml`, `workspace.xml`) show up
as modified in `git status` whenever the IDE touches them, even though
`.gitignore` already lists `.idea`. Personal IDE state can be committed and
pushed by accident, and it causes merge noise between developers.

## Steps to Reproduce

1. Open the project in PyCharm/IntelliJ, or change any IDE setting.
2. Run `git status` from the repo root.

## Expected vs Actual

- **Expected:** Nothing under any `.idea/` directory appears in `git status`
  or the index.
- **Actual:** `.idea/hl_vae.iml` and `.idea/workspace.xml` are tracked and
  show as modified.

## Root Cause

`.gitignore` only stops *untracked* files from being added. Both files were
committed in `433e558` (initial commit) and `bcdac32`, before the ignore rules
were added in `3baa67d`. Git keeps tracking files that are already in the
index, so the ignore rules have no effect on them.

`git check-ignore -v --no-index .idea/workspace.xml` confirms the rule
matches (`.gitignore:135:.idea`). The rules themselves are fine but repeat the
same thing four ways (`.gitignore` lines 133–136: `.idea/`, `.idea*`, `.idea`,
`.idea/*`).

## Fix

1. Stop tracking the files without deleting them locally:
   `git rm -r --cached .idea`
2. Replace the four `.idea` lines in `.gitignore` with one rule:
   `.idea/`. Because it has no leading slash, it matches an `.idea` directory
   at any depth, which covers "all `.idea` directories". `.idea*` is dropped
   because it would also ignore unrelated files whose names start with `.idea`.
3. Commit both changes together.

Note: after this is pulled, git will delete the tracked `.idea` files from
other clones' working trees. Anyone who wants to keep their IDE settings
should back up `.idea/` before pulling.

Rewriting history to purge `.idea` from past commits was considered and
rejected. The files hold no secrets, and a rewrite would break existing
clones.

## Verification

All four checks below were run on 2026-11-08 and passed; local `.idea/` files were kept.

- `git ls-files | grep -c '\.idea'` prints `0`.
- `git status` stays clean after IDE activity.
- `git check-ignore -v .idea/workspace.xml` still reports a match.
- `mkdir -p x/.idea && touch x/.idea/t && git check-ignore -v x/.idea/t`
  matches (nested directories are covered); then `rm -r x`.

## Changelog

- 2026-11-08 — Reported and triaged.
- 2026-11-08 — Fixed: `.idea` removed from the index, `.gitignore` rule simplified to `.idea/`.
