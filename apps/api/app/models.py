from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from apps.api.app.database import Base
from packages.schemas.domain import (
    ApplicationStage,
    ApplicationStatus,
    EmailProcessingStatus,
    ReviewStatus,
    TaskPriority,
    TaskStatus,
)


class UUIDTimestampMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Company(UUIDTimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    applications: Mapped[list["Application"]] = relationship(back_populates="company")

    __table_args__ = (
        UniqueConstraint("canonical_name", name="uq_companies_canonical_name"),
        UniqueConstraint("domain", name="uq_companies_domain"),
    )


class Application(UUIDTimestampMixin, Base):
    __tablename__ = "applications"

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_job_title: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="email")
    current_stage: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApplicationStage.APPLIED.value
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApplicationStatus.ACTIVE.value
    )

    company: Mapped[Company | None] = relationship(back_populates="applications")
    emails: Mapped[list["Email"]] = relationship(back_populates="application")
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application")
    tasks: Mapped[list["Task"]] = relationship(back_populates="application")

    __table_args__ = (
        Index("ix_applications_company_title", "company_id", "normalized_job_title"),
    )


class Email(UUIDTimestampMixin, Base):
    __tablename__ = "emails"

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EmailProcessingStatus.PENDING.value
    )
    processing_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[UUID] = mapped_column(nullable=False, default=uuid4, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped[Application | None] = relationship(back_populates="emails")
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="source_email")
    reviews: Mapped[list["ReviewDecision"]] = relationship(back_populates="email")


class ApplicationEvent(UUIDTimestampMixin, Base):
    __tablename__ = "application_events"

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stage_before: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stage_after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_email_id: Mapped[UUID] = mapped_column(
        ForeignKey("emails.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    application: Mapped[Application] = relationship(back_populates="events")
    source_email: Mapped[Email] = relationship(back_populates="events")
    tasks: Mapped[list["Task"]] = relationship(back_populates="source_event")


class Task(UUIDTimestampMixin, Base):
    __tablename__ = "tasks"

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_events.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TaskPriority.MEDIUM.value
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=TaskStatus.OPEN.value)

    application: Mapped[Application] = relationship(back_populates="tasks")
    source_event: Mapped[ApplicationEvent] = relationship(back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("source_event_id", "task_type", name="uq_tasks_source_event_task_type"),
    )


class ReviewDecision(UUIDTimestampMixin, Base):
    __tablename__ = "review_decisions"

    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("emails.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    suggested_application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    suggested_action: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ReviewStatus.PENDING.value
    )
    resolved_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved_application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    email: Mapped[Email] = relationship(back_populates="reviews")
