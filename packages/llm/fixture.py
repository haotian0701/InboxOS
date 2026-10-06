from datetime import timedelta

from packages.schemas.domain import ApplicationStage, JobEventType
from packages.schemas.email import EmailInput, EmailUnderstanding, JobEmailExtraction


class FixtureProviderError(RuntimeError):
    """Raised by the fixture provider to exercise failure handling."""


class FixtureEmailIntelligenceProvider:
    """Deterministic development provider; it is intentionally not an email parser."""

    async def understand(self, email: EmailInput) -> EmailUnderstanding:
        content = self._content(email)
        if "[fixture:failure]" in content:
            raise FixtureProviderError("Synthetic provider failure")
        if "[fixture:not-job]" in content or "unsubscribe from this newsletter" in content:
            return EmailUnderstanding(
                category="newsletter",
                is_action_required=False,
                intent=None,
                short_summary="Non-job fixture message",
            )
        return EmailUnderstanding(
            category="job_application",
            is_action_required=True,
            intent="application_update",
            short_summary="Job application fixture message",
        )

    async def extract_job_event(self, email: EmailInput) -> JobEmailExtraction:
        content = self._content(email)
        confidence = 0.67 if "[fixture:low-confidence]" in content else 0.94

        if "[fixture:assessment]" in content:
            return JobEmailExtraction(
                is_job_related=True,
                company_name="Contoso",
                job_title="Software Engineer",
                recruiter_name="Taylor",
                event_type=JobEventType.ASSESSMENT_RECEIVED,
                application_stage=ApplicationStage.ASSESSMENT,
                deadline=email.received_at + timedelta(days=3),
                action_required=True,
                action_description="Complete assessment",
                evidence=["fixture:assessment"],
                confidence=confidence,
            )
        if "[fixture:rejection]" in content:
            return JobEmailExtraction(
                is_job_related=True,
                company_name="Contoso",
                job_title="Software Engineer",
                recruiter_name="Taylor",
                event_type=JobEventType.REJECTION,
                application_stage=ApplicationStage.REJECTED,
                action_required=False,
                evidence=["fixture:rejection"],
                confidence=confidence,
            )
        if "[fixture:offer]" in content:
            return JobEmailExtraction(
                is_job_related=True,
                company_name="Contoso",
                job_title="Software Engineer",
                recruiter_name="Taylor",
                event_type=JobEventType.OFFER,
                application_stage=ApplicationStage.OFFER,
                deadline=email.received_at + timedelta(days=7),
                action_required=True,
                action_description="Review offer",
                evidence=["fixture:offer"],
                confidence=confidence,
            )
        if "[fixture:unknown]" in content:
            return JobEmailExtraction(
                is_job_related=True,
                company_name="Contoso",
                job_title="Software Engineer",
                recruiter_name="Taylor",
                event_type=JobEventType.UNKNOWN,
                action_required=False,
                evidence=["fixture:unknown"],
                confidence=confidence,
            )
        return JobEmailExtraction(
            is_job_related=True,
            company_name="AI-Z Group",
            job_title="AI Engineer",
            recruiter_name="Carlo",
            event_type=JobEventType.INTERVIEW_INVITATION,
            application_stage=ApplicationStage.SECOND_INTERVIEW,
            interview_datetime=email.received_at + timedelta(days=6),
            action_required=True,
            action_description="Prepare for second interview",
            evidence=["fixture:interview-invitation"],
            confidence=confidence,
        )

    @staticmethod
    def _content(email: EmailInput) -> str:
        return f"{email.subject}\n{email.body_text}".casefold()
