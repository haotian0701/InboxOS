from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from packages.schemas.domain import ApplicationStage, JobEventType


class EmailInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sender: EmailStr
    recipients: list[EmailStr] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=998)
    body_text: str = Field(min_length=1, max_length=1_000_000)
    received_at: datetime

    @field_validator("body_text")
    @classmethod
    def body_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body_text must contain non-whitespace text")
        return value

    @field_validator("received_at")
    @classmethod
    def received_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value


class EmailUnderstanding(BaseModel):
    category: str
    is_action_required: bool
    deadline: datetime | None = None
    entities: list[str] = Field(default_factory=list)
    intent: str | None = None
    short_summary: str


class JobEmailExtraction(BaseModel):
    is_job_related: bool
    company_name: str | None = None
    job_title: str | None = None
    recruiter_name: str | None = None
    event_type: JobEventType
    application_stage: ApplicationStage | None = None
    interview_datetime: datetime | None = None
    deadline: datetime | None = None
    action_required: bool
    action_description: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator("interview_datetime", "deadline")
    @classmethod
    def optional_dates_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("extracted dates must include a timezone")
        return value

