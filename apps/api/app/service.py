import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from apps.api.app.api_schemas import (
    ApplicationRead,
    EmailRead,
    EventRead,
    ProcessDecision,
    ProcessEmailResponse,
    ReviewRead,
    TaskRead,
)
from apps.api.app.models import (
    Application,
    ApplicationEvent,
    Company,
    Email,
    ReviewDecision,
    Task,
)
from packages.email import (
    extract_sender_domain,
    normalize_company_name,
    normalize_job_title,
)
from packages.llm.provider import EmailIntelligenceProvider
from packages.schemas.domain import (
    ApplicationStage,
    ApplicationStatus,
    EmailProcessingStatus,
    ReviewStatus,
    TaskStatus,
)
from packages.schemas.email import EmailInput, JobEmailExtraction
from packages.workflows import next_stage, task_for_event

logger = logging.getLogger("inboxos.processing")
AUTO_DECISION_THRESHOLD = 0.85


class IdempotencyConflictError(RuntimeError):
    pass


class ProcessingFailedError(RuntimeError):
    def __init__(self, email_id: UUID, trace_id: UUID) -> None:
        self.email_id = email_id
        self.trace_id = trace_id
        super().__init__("Email processing failed")


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    response: ProcessEmailResponse
    replayed: bool


class EmailProcessingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: EmailIntelligenceProvider,
    ) -> None:
        self._sessions = session_factory
        self._provider = provider

    async def process(
        self, payload: EmailInput, idempotency_key: str
    ) -> ProcessingOutcome:
        request_hash = self._request_hash(payload)
        email_id, replayed = await self._create_pending_email(
            payload, idempotency_key, request_hash
        )
        if replayed:
            return ProcessingOutcome(await self._load_result(email_id), replayed=True)

        try:
            understanding = await self._provider.understand(payload)
            if understanding.category != "job_application":
                async with self._sessions.begin() as session:
                    email = await self._locked_email(session, email_id)
                    email.processing_status = EmailProcessingStatus.IGNORED.value
                    email.processing_decision = ProcessDecision.IGNORED.value
                    email.processed_at = datetime.now(UTC)
                return ProcessingOutcome(await self._load_result(email_id), replayed=False)

            extraction = await self._provider.extract_job_event(payload)
            async with self._sessions.begin() as session:
                email = await self._locked_email(session, email_id)
                email.structured_result = extraction.model_dump(mode="json")

                application, candidates = await self._find_exact_candidates(
                    session, extraction, str(payload.sender)
                )
                needs_review = (
                    extraction.confidence < AUTO_DECISION_THRESHOLD
                    or len(candidates) > 1
                    or (application is None and extraction.company_name is None)
                )
                if needs_review:
                    await self._create_review(session, email, extraction, candidates)
                else:
                    decision = ProcessDecision.MATCHED
                    if application is None:
                        application = await self._create_application(
                            session, extraction, str(payload.sender)
                        )
                        decision = ProcessDecision.CREATED

                    email.application_id = application.id
                    event = await self._create_event(
                        session, email, application, extraction, payload
                    )
                    await self._create_task(session, application, event, extraction)
                    email.processing_status = EmailProcessingStatus.PROCESSED.value
                    email.processing_decision = decision.value
                    email.processed_at = datetime.now(UTC)

            return ProcessingOutcome(await self._load_result(email_id), replayed=False)
        except Exception as exc:
            await self._mark_failed(email_id, type(exc).__name__)
            trace_id = await self._trace_id(email_id)
            logger.error(
                json.dumps(
                    {
                        "event": "email_processing_failed",
                        "email_id": str(email_id),
                        "trace_id": str(trace_id),
                        "exception_type": type(exc).__name__,
                    }
                )
            )
            raise ProcessingFailedError(email_id, trace_id) from exc

    async def _create_pending_email(
        self, payload: EmailInput, idempotency_key: str, request_hash: str
    ) -> tuple[UUID, bool]:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(Email).where(Email.idempotency_key == idempotency_key)
            )
            if existing is not None:
                self._check_request_hash(existing, request_hash)
                return existing.id, True

            email = Email(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                content_hash=self._content_hash(payload),
                sender=str(payload.sender),
                recipients=[str(item) for item in payload.recipients],
                subject=payload.subject,
                body_text=payload.body_text,
                received_at=payload.received_at.astimezone(UTC),
                processing_status=EmailProcessingStatus.PENDING.value,
            )
            session.add(email)
            try:
                await session.commit()
                return email.id, False
            except IntegrityError:
                await session.rollback()
                existing = await session.scalar(
                    select(Email).where(Email.idempotency_key == idempotency_key)
                )
                if existing is None:
                    raise
                self._check_request_hash(existing, request_hash)
                return existing.id, True

    @staticmethod
    def _check_request_hash(email: Email, request_hash: str) -> None:
        if email.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Idempotency-Key was already used with a different request"
            )

    async def _find_exact_candidates(
        self,
        session: AsyncSession,
        extraction: JobEmailExtraction,
        sender: str,
    ) -> tuple[Application | None, list[Application]]:
        canonical_name = (
            normalize_company_name(extraction.company_name) if extraction.company_name else None
        )
        sender_domain = extract_sender_domain(sender)
        filters: list[ColumnElement[bool]] = []
        if canonical_name:
            company_ids = select(Company.id).where(Company.canonical_name == canonical_name)
            filters.append(Application.company_id.in_(company_ids))
        if sender_domain:
            filters.append(Application.company_domain == sender_domain)
        if not filters:
            return None, []

        result = await session.scalars(
            select(Application)
            .where(or_(*filters))
            .with_for_update()
        )
        candidates = list(result.unique())
        normalized_title = normalize_job_title(extraction.job_title)
        if normalized_title:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.normalized_job_title in {None, normalized_title}
            ]
        return (candidates[0] if len(candidates) == 1 else None), candidates

    async def _create_application(
        self,
        session: AsyncSession,
        extraction: JobEmailExtraction,
        sender: str,
    ) -> Application:
        assert extraction.company_name is not None
        canonical_name = normalize_company_name(extraction.company_name)
        sender_domain = extract_sender_domain(sender)
        company_filters: list[ColumnElement[bool]] = [
            Company.canonical_name == canonical_name
        ]
        if sender_domain:
            company_filters.append(Company.domain == sender_domain)
        company = await session.scalar(select(Company).where(or_(*company_filters)))
        if company is None:
            company = Company(
                name=extraction.company_name,
                canonical_name=canonical_name,
                domain=sender_domain,
            )
            session.add(company)
            await session.flush()

        application = Application(
            company_id=company.id,
            company_name=extraction.company_name,
            company_domain=sender_domain,
            job_title=extraction.job_title,
            normalized_job_title=normalize_job_title(extraction.job_title),
            source="email",
            current_stage=ApplicationStage.APPLIED.value,
            status=ApplicationStatus.ACTIVE.value,
        )
        session.add(application)
        await session.flush()
        return application

    async def _create_review(
        self,
        session: AsyncSession,
        email: Email,
        extraction: JobEmailExtraction,
        candidates: list[Application],
    ) -> None:
        suggested = candidates[0] if len(candidates) == 1 else None
        reason = (
            "Extraction confidence is below the automatic decision threshold"
            if extraction.confidence < AUTO_DECISION_THRESHOLD
            else "Multiple exact application candidates were found"
        )
        if not candidates and extraction.company_name is None:
            reason = "A company could not be identified"
        review = ReviewDecision(
            email_id=email.id,
            suggested_application_id=suggested.id if suggested else None,
            suggested_action="confirm_match" if suggested else "create_application",
            confidence=extraction.confidence,
            reason=reason,
            evidence=extraction.evidence,
            status=ReviewStatus.PENDING.value,
        )
        session.add(review)
        email.processing_status = EmailProcessingStatus.NEEDS_REVIEW.value
        email.processing_decision = ProcessDecision.REVIEW.value
        email.processed_at = datetime.now(UTC)

    async def _create_event(
        self,
        session: AsyncSession,
        email: Email,
        application: Application,
        extraction: JobEmailExtraction,
        payload: EmailInput,
    ) -> ApplicationEvent:
        before = ApplicationStage(application.current_stage)
        after = next_stage(before, extraction.event_type, extraction.application_stage)
        event_date = (
            extraction.interview_datetime or extraction.deadline or payload.received_at
        ).astimezone(UTC)
        deduplication_key = hashlib.sha256(
            f"{email.id}:{extraction.event_type.value}:{event_date.isoformat()}".encode()
        ).hexdigest()
        event = ApplicationEvent(
            application_id=application.id,
            event_type=extraction.event_type.value,
            stage_before=before.value,
            stage_after=after.value,
            event_date=event_date,
            source_email_id=email.id,
            summary=extraction.action_description
            or extraction.event_type.value.replace("_", " ").capitalize(),
            confidence=extraction.confidence,
            deduplication_key=deduplication_key,
        )
        session.add(event)
        application.current_stage = after.value
        if after in {ApplicationStage.REJECTED, ApplicationStage.WITHDRAWN}:
            application.status = ApplicationStatus.CLOSED.value
        await session.flush()
        return event

    @staticmethod
    async def _create_task(
        session: AsyncSession,
        application: Application,
        event: ApplicationEvent,
        extraction: JobEmailExtraction,
    ) -> Task | None:
        task_spec = task_for_event(extraction)
        if task_spec is None:
            return None
        task = Task(
            application_id=application.id,
            source_event_id=event.id,
            task_type=task_spec.task_type.value,
            title=task_spec.title,
            description=task_spec.description,
            due_at=task_spec.due_at,
            priority=task_spec.priority.value,
            status=TaskStatus.OPEN.value,
        )
        session.add(task)
        return task

    async def _load_result(self, email_id: UUID) -> ProcessEmailResponse:
        async with self._sessions() as session:
            email = await session.get(Email, email_id)
            if email is None:
                raise LookupError("Email disappeared during processing")
            application = (
                await session.get(Application, email.application_id)
                if email.application_id
                else None
            )
            event = await session.scalar(
                select(ApplicationEvent)
                .where(ApplicationEvent.source_email_id == email.id)
                .order_by(ApplicationEvent.created_at.desc())
                .limit(1)
            )
            task = None
            if event is not None:
                task = await session.scalar(
                    select(Task)
                    .where(Task.source_event_id == event.id)
                    .order_by(Task.created_at.desc())
                    .limit(1)
                )
            review = await session.scalar(
                select(ReviewDecision).where(ReviewDecision.email_id == email.id)
            )
            decision = ProcessDecision(email.processing_decision or ProcessDecision.PENDING.value)
            return ProcessEmailResponse(
                trace_id=email.trace_id,
                decision=decision,
                email=EmailRead.model_validate(email),
                application=ApplicationRead.model_validate(application) if application else None,
                event=EventRead.model_validate(event) if event else None,
                task=TaskRead.model_validate(task) if task else None,
                review=ReviewRead.model_validate(review) if review else None,
            )

    async def _mark_failed(self, email_id: UUID, exception_type: str) -> None:
        async with self._sessions.begin() as session:
            email = await self._locked_email(session, email_id)
            email.processing_status = EmailProcessingStatus.FAILED.value
            email.processing_decision = ProcessDecision.FAILED.value
            email.processing_error = f"Processing failed ({exception_type})"[:255]
            email.processed_at = datetime.now(UTC)

    async def _trace_id(self, email_id: UUID) -> UUID:
        async with self._sessions() as session:
            trace_id = await session.scalar(select(Email.trace_id).where(Email.id == email_id))
            if trace_id is None:
                raise LookupError("Email trace ID is missing")
            return trace_id

    @staticmethod
    async def _locked_email(session: AsyncSession, email_id: UUID) -> Email:
        email = await session.scalar(
            select(Email).where(Email.id == email_id).with_for_update()
        )
        if email is None:
            raise LookupError("Email does not exist")
        return email

    @staticmethod
    def _request_hash(payload: EmailInput) -> str:
        serialized = json.dumps(
            payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _content_hash(payload: EmailInput) -> str:
        content = "\n".join(
            [
                str(payload.sender),
                payload.subject,
                payload.body_text,
                payload.received_at.isoformat(),
            ]
        )
        return hashlib.sha256(content.encode()).hexdigest()
