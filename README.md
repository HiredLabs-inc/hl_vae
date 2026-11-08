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

## Design docs

Design work is tracked in [`docs/`](docs/):

- [`docs/backlog.md`](docs/backlog.md) — all features and infrastructure work, grouped by phase
- [`docs/buglog.md`](docs/buglog.md) — all bugs, grouped by phase

Per-item design docs live in phase subdirectories (`designed/`, `active/`, `archive/`, `bugfixes/`); templates are in `docs/templates/`.
