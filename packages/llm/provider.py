from typing import Protocol

from packages.schemas.email import EmailInput, EmailUnderstanding, JobEmailExtraction


class EmailIntelligenceProvider(Protocol):
    async def understand(self, email: EmailInput) -> EmailUnderstanding: ...

    async def extract_job_event(self, email: EmailInput) -> JobEmailExtraction: ...

