# InboxOS

InboxOS turns job-related emails into persistent application state, timeline events, and
actionable tasks. This repository currently contains the phase-one backend foundation with a
deterministic fixture intelligence provider.

## Requirements

- Docker with Docker Compose
- Or Python 3.12, uv, and PostgreSQL 17

## Start locally

Database migrations are explicit and are never run by API startup.

```bash
docker compose up -d postgres
docker compose --profile tools run --rm migrate
docker compose up --build api
```

OpenAPI is available at <http://localhost:8000/docs> and health at
<http://localhost:8000/healthz>.

## Process the fixture interview email

```bash
curl -i http://localhost:8000/api/emails/process \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-interview-1' \
  -d '{
    "sender": "carlo@ai-z.com",
    "recipients": ["haotian@example.com"],
    "subject": "Second interview",
    "body_text": "We would love to invite you to a second interview.",
    "received_at": "2026-10-06T10:00:00+02:00"
  }'
```

Fixture markers supported in the subject or body are:

- `[fixture:not-job]`
- `[fixture:low-confidence]`
- `[fixture:assessment]`
- `[fixture:rejection]`
- `[fixture:offer]`
- `[fixture:unknown]`
- `[fixture:failure]`

These markers are development/test behavior only and must not be used as product extraction.

## Development checks

```bash
uv sync --frozen --all-extras
uv run ruff check .
uv run pyright
uv run pytest
```

PostgreSQL integration tests require `TEST_DATABASE_URL`. The application uses
`INBOXOS_DATABASE_URL`; see `.env.example` for all settings.
