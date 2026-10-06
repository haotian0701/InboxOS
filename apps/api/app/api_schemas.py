from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.domain import (
    ApplicationStage,
    ApplicationStatus,
    EmailProcessingStatus,
    JobEventType,
    ReviewStatus,
    TaskPriority,
    TaskStatus,
    TaskType,
)


class ProcessDecision(StrEnum):
    MATCHED = "matched"
    CREATED = "created"
    IGNORED = "ignored"
    REVIEW = "review"
    PENDING = "pending"
    FAILED = "failed"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmailRead(ORMModel):
    id: UUID
    sender: str
    recipients: list[str]
    subject: str
    received_at: datetime
    application_id: UUID | None
    processing_status: EmailProcessingStatus
    processing_error: str | None
    trace_id: UUID
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmailDetail(EmailRead):
    body_text: str
    structured_result: dict[str, object] | None


class ApplicationRead(ORMModel):
    id: UUID
    company_id: UUID | None
    company_name: str
    company_domain: str | None
    job_title: str | None
    location: str | None
    source: str
    current_stage: ApplicationStage
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class EventRead(ORMModel):
    id: UUID
    application_id: UUID
    event_type: JobEventType
    stage_before: ApplicationStage | None
    stage_after: ApplicationStage | None
    event_date: datetime
    source_email_id: UUID
    summary: str
    confidence: float = Field(ge=0, le=1)
    created_at: datetime


class TaskRead(ORMModel):
    id: UUID
    application_id: UUID
    source_event_id: UUID
    task_type: TaskType
    title: str
    description: str | None
    due_at: datetime | None
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime


class ReviewRead(ORMModel):
    id: UUID
    email_id: UUID
    suggested_application_id: UUID | None
    suggested_action: str
    confidence: float = Field(ge=0, le=1)
    reason: str
    evidence: list[str]
    status: ReviewStatus
    created_at: datetime


class ProcessEmailResponse(BaseModel):
    trace_id: UUID
    decision: ProcessDecision
    email: EmailRead
    application: ApplicationRead | None = None
    event: EventRead | None = None
    task: TaskRead | None = None
    review: ReviewRead | None = None


class ApplicationDetail(ApplicationRead):
    emails: list[EmailRead]
    events: list[EventRead]
    tasks: list[TaskRead]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
    trace_id: UUID | None = None

