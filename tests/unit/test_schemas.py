from datetime import datetime

import pytest
from pydantic import ValidationError

from packages.schemas.email import EmailInput, JobEmailExtraction


def valid_email() -> dict[str, object]:
    return {
        "sender": "recruiter@example.com",
        "recipients": ["candidate@example.com"],
        "subject": "Application update",
        "body_text": "Your application has been updated.",
        "received_at": "2026-10-06T10:00:00+02:00",
    }


def test_email_input_accepts_timezone_aware_datetime() -> None:
    email = EmailInput.model_validate(valid_email())
    assert email.received_at.utcoffset() is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sender", "not-an-email"),
        ("body_text", "   "),
        ("received_at", datetime(2026, 10, 6, 10, 0)),
    ],
)
def test_email_input_rejects_invalid_fields(field: str, value: object) -> None:
    payload = valid_email()
    payload[field] = value
    with pytest.raises(ValidationError):
        EmailInput.model_validate(payload)


def test_job_extraction_rejects_invalid_enum() -> None:
    with pytest.raises(ValidationError):
        JobEmailExtraction.model_validate(
            {
                "is_job_related": True,
                "event_type": "invented_event",
                "action_required": False,
                "confidence": 0.9,
            }
        )

