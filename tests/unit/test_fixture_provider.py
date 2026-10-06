from datetime import UTC, datetime

import pytest

from packages.llm.fixture import FixtureEmailIntelligenceProvider, FixtureProviderError
from packages.llm.provider import EmailIntelligenceProvider
from packages.schemas.domain import JobEventType
from packages.schemas.email import EmailInput


def email_with_marker(marker: str) -> EmailInput:
    return EmailInput(
        sender="recruiter@example.com",
        recipients=["candidate@example.com"],
        subject="Application update",
        body_text=marker,
        received_at=datetime(2026, 10, 6, 8, 0, tzinfo=UTC),
    )


def accepts_protocol(provider: EmailIntelligenceProvider) -> None:
    assert provider is not None


@pytest.mark.asyncio
async def test_fixture_provider_implements_protocol_and_scenarios() -> None:
    provider = FixtureEmailIntelligenceProvider()
    accepts_protocol(provider)

    understanding = await provider.understand(email_with_marker("[fixture:not-job]"))
    assert understanding.category == "newsletter"

    extraction = await provider.extract_job_event(email_with_marker("[fixture:offer]"))
    assert extraction.event_type == JobEventType.OFFER
    assert extraction.confidence == 0.94

    low_confidence = await provider.extract_job_event(
        email_with_marker("[fixture:low-confidence]")
    )
    assert low_confidence.confidence == 0.67


@pytest.mark.asyncio
async def test_fixture_provider_can_simulate_failure() -> None:
    provider = FixtureEmailIntelligenceProvider()
    with pytest.raises(FixtureProviderError):
        await provider.understand(email_with_marker("[fixture:failure]"))

