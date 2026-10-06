import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from apps.api.app.database import create_engine, create_session_factory
from apps.api.app.models import (
    Application,
    ApplicationEvent,
    Company,
    Email,
    ReviewDecision,
    Task,
)

pytestmark = pytest.mark.integration


def payload(marker: str = "") -> dict[str, Any]:
    return {
        "sender": "carlo@ai-z.com",
        "recipients": ["haotian@example.com"],
        "subject": "Second interview",
        "body_text": f"We would love to invite you to a second interview. {marker}",
        "received_at": "2026-10-06T10:00:00+02:00",
    }


@pytest.mark.asyncio
async def test_high_confidence_email_creates_complete_trace(client: AsyncClient) -> None:
    response = await client.post(
        "/api/emails/process",
        headers={"Idempotency-Key": "create-application"},
        json=payload(),
    )
    assert response.status_code == 201
    result = response.json()
    assert result["decision"] == "created"
    assert result["email"]["processing_status"] == "processed"
    assert result["application"]["current_stage"] == "second_interview"
    assert result["event"]["event_type"] == "interview_invitation"
    assert result["task"]["task_type"] == "prepare_interview"

    detail = await client.get(f"/api/applications/{result['application']['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["emails"]) == 1
    assert len(detail.json()["events"]) == 1
    assert len(detail.json()["tasks"]) == 1


@pytest.mark.asyncio
async def test_second_email_exactly_matches_existing_application(client: AsyncClient) -> None:
    first = await client.post(
        "/api/emails/process", headers={"Idempotency-Key": "first"}, json=payload()
    )
    second_payload = payload()
    second_payload["received_at"] = "2026-10-07T10:00:00+02:00"
    second = await client.post(
        "/api/emails/process", headers={"Idempotency-Key": "second"}, json=second_payload
    )
    assert second.status_code == 201
    assert second.json()["decision"] == "matched"
    assert second.json()["application"]["id"] == first.json()["application"]["id"]


@pytest.mark.asyncio
async def test_non_job_email_is_ignored(client: AsyncClient) -> None:
    response = await client.post(
        "/api/emails/process",
        headers={"Idempotency-Key": "newsletter"},
        json=payload("[fixture:not-job]"),
    )
    assert response.status_code == 201
    result = response.json()
    assert result["decision"] == "ignored"
    assert result["application"] is None
    assert result["event"] is None
    assert result["task"] is None


@pytest.mark.asyncio
async def test_low_confidence_email_requires_review_without_mutation(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/emails/process",
        headers={"Idempotency-Key": "review"},
        json=payload("[fixture:low-confidence]"),
    )
    assert response.status_code == 201
    result = response.json()
    assert result["decision"] == "review"
    assert result["email"]["processing_status"] == "needs_review"
    assert result["application"] is None
    assert result["event"] is None
    assert result["review"]["status"] == "pending"


@pytest.mark.asyncio
async def test_idempotent_replay_and_conflict(client: AsyncClient) -> None:
    first = await client.post(
        "/api/emails/process", headers={"Idempotency-Key": "stable-key"}, json=payload()
    )
    replay = await client.post(
        "/api/emails/process", headers={"Idempotency-Key": "stable-key"}, json=payload()
    )
    changed = payload()
    changed["subject"] = "Changed subject"
    conflict = await client.post(
        "/api/emails/process", headers={"Idempotency-Key": "stable-key"}, json=changed
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_provider_failure_is_persisted_without_business_rows(
    client: AsyncClient, database_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    request_payload = payload("[fixture:failure] secret-body-marker")
    response = await client.post(
        "/api/emails/process",
        headers={"Idempotency-Key": "provider-failure"},
        json=request_payload,
    )
    assert response.status_code == 500
    assert "secret-body-marker" not in caplog.text
    assert "carlo@ai-z.com" not in caplog.text

    engine = create_engine(database_url)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        email = await session.scalar(
            select(Email).where(Email.idempotency_key == "provider-failure")
        )
        assert email is not None
        assert email.processing_status == "failed"
        assert email.processing_error == "Processing failed (FixtureProviderError)"
        assert await session.scalar(select(func.count()).select_from(Application)) == 0
        assert await session.scalar(select(func.count()).select_from(ApplicationEvent)) == 0
        assert await session.scalar(select(func.count()).select_from(Task)) == 0
        assert await session.scalar(select(func.count()).select_from(ReviewDecision)) == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_multiple_exact_candidates_require_review(
    client: AsyncClient, database_url: str
) -> None:
    engine = create_engine(database_url)
    sessions = create_session_factory(engine)
    async with sessions.begin() as session:
        company = Company(
            name="AI-Z Group",
            canonical_name="ai z group",
            domain="ai-z.com",
        )
        session.add(company)
        await session.flush()
        session.add_all(
            [
                Application(
                    company_id=company.id,
                    company_name="AI-Z Group",
                    company_domain="ai-z.com",
                    job_title="AI Engineer",
                    normalized_job_title="ai engineer",
                    source="manual",
                    current_stage="applied",
                    status="active",
                ),
                Application(
                    company_id=company.id,
                    company_name="AI-Z Group",
                    company_domain="ai-z.com",
                    job_title="AI Engineer",
                    normalized_job_title="ai engineer",
                    source="manual",
                    current_stage="applied",
                    status="active",
                ),
            ]
        )
    await engine.dispose()

    response = await client.post(
        "/api/emails/process",
        headers={"Idempotency-Key": "ambiguous-match"},
        json=payload(),
    )
    assert response.status_code == 201
    result = response.json()
    assert result["decision"] == "review"
    assert result["review"]["reason"] == "Multiple exact application candidates were found"
    assert result["event"] is None
    assert result["task"] is None


@pytest.mark.asyncio
async def test_concurrent_idempotent_requests_create_one_event_and_task(
    client: AsyncClient, database_url: str
) -> None:
    async def submit() -> object:
        return await client.post(
            "/api/emails/process",
            headers={"Idempotency-Key": "concurrent-key"},
            json=payload(),
        )

    responses = await asyncio.gather(submit(), submit())
    assert sorted(response.status_code for response in responses) == [200, 201]

    engine = create_engine(database_url)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Email)) == 1
        assert await session.scalar(select(func.count()).select_from(ApplicationEvent)) == 1
        assert await session.scalar(select(func.count()).select_from(Task)) == 1
    await engine.dispose()
