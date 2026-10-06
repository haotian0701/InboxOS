"""Create InboxOS foundation tables.

Revision ID: 20261006_0001
Revises:
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        *timestamps(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_companies"),
        sa.UniqueConstraint("canonical_name", name="uq_companies_canonical_name"),
        sa.UniqueConstraint("domain", name="uq_companies_domain"),
    )
    op.create_index("ix_companies_canonical_name", "companies", ["canonical_name"])
    op.create_index("ix_companies_domain", "companies", ["domain"])

    op.create_table(
        "applications",
        *timestamps(),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_domain", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("normalized_job_title", sa.String(length=255), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("current_stage", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_applications_company_id_companies",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
    )
    op.create_index("ix_applications_company_id", "applications", ["company_id"])
    op.create_index("ix_applications_company_domain", "applications", ["company_domain"])
    op.create_index(
        "ix_applications_normalized_job_title", "applications", ["normalized_job_title"]
    )
    op.create_index(
        "ix_applications_company_title", "applications", ["company_id", "normalized_job_title"]
    )

    op.create_table(
        "emails",
        *timestamps(),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("processing_decision", sa.String(length=50), nullable=True),
        sa.Column("processing_error", sa.String(length=255), nullable=True),
        sa.Column("structured_result", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_emails_application_id_applications",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_emails"),
        sa.UniqueConstraint("idempotency_key", name="uq_emails_idempotency_key"),
    )
    op.create_index("ix_emails_application_id", "emails", ["application_id"])
    op.create_index("ix_emails_content_hash", "emails", ["content_hash"])
    op.create_index("ix_emails_trace_id", "emails", ["trace_id"])

    op.create_table(
        "application_events",
        *timestamps(),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("stage_before", sa.String(length=50), nullable=True),
        sa.Column("stage_after", sa.String(length=50), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_email_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_application_events_application_id_applications",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_email_id"],
            ["emails.id"],
            name="fk_application_events_source_email_id_emails",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_application_events"),
        sa.UniqueConstraint(
            "deduplication_key", name="uq_application_events_deduplication_key"
        ),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )
    op.create_index(
        "ix_application_events_source_email_id", "application_events", ["source_email_id"]
    )

    op.create_table(
        "tasks",
        *timestamps(),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_tasks_application_id_applications",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["application_events.id"],
            name="fk_tasks_source_event_id_application_events",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
        sa.UniqueConstraint(
            "source_event_id", "task_type", name="uq_tasks_source_event_task_type"
        ),
    )
    op.create_index("ix_tasks_application_id", "tasks", ["application_id"])
    op.create_index("ix_tasks_source_event_id", "tasks", ["source_event_id"])

    op.create_table(
        "review_decisions",
        *timestamps(),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column("suggested_application_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_action", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("resolved_action", sa.String(length=50), nullable=True),
        sa.Column("resolved_application_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name="fk_review_decisions_email_id_emails",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["suggested_application_id"],
            ["applications.id"],
            name="fk_review_decisions_suggested_application_id_applications",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_application_id"],
            ["applications.id"],
            name="fk_review_decisions_resolved_application_id_applications",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_decisions"),
        sa.UniqueConstraint("email_id", name="uq_review_decisions_email_id"),
    )


def downgrade() -> None:
    op.drop_table("review_decisions")
    op.drop_index("ix_tasks_source_event_id", table_name="tasks")
    op.drop_index("ix_tasks_application_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_application_events_source_email_id", table_name="application_events")
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_emails_trace_id", table_name="emails")
    op.drop_index("ix_emails_content_hash", table_name="emails")
    op.drop_index("ix_emails_application_id", table_name="emails")
    op.drop_table("emails")
    op.drop_index("ix_applications_company_title", table_name="applications")
    op.drop_index("ix_applications_normalized_job_title", table_name="applications")
    op.drop_index("ix_applications_company_domain", table_name="applications")
    op.drop_index("ix_applications_company_id", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_companies_domain", table_name="companies")
    op.drop_index("ix_companies_canonical_name", table_name="companies")
    op.drop_table("companies")
