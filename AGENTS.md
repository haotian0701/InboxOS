# InboxOS Agent Guide

## Purpose

InboxOS turns job-related emails into persistent application state, timeline events,
review decisions, and actionable tasks.

## Stack

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic
- PostgreSQL
- pytest, Ruff, Pyright, and uv


## Verification

Run the checks relevant to the change, and before handoff prefer:

```powershell
uv run ruff check .
uv run pyright
uv run pytest
uv run alembic check
```

If a required check cannot run, report which check was skipped and why.

## Git Workflow

- Keep `main` stable; use short-lived branches such as `feat/...`, `fix/...`, or `chore/...` for non-trivial changes.
- Do not commit, push, merge, force-push, or rewrite history unless explicitly requested.
- Before handoff, report changed files and verification results.
