from dataclasses import dataclass
from datetime import datetime

from packages.schemas.domain import (
    ApplicationStage,
    JobEventType,
    TaskPriority,
    TaskType,
)
from packages.schemas.email import JobEmailExtraction

_STAGE_ORDER = {
    ApplicationStage.SAVED: 0,
    ApplicationStage.APPLIED: 1,
    ApplicationStage.SCREENING: 2,
    ApplicationStage.ASSESSMENT: 3,
    ApplicationStage.FIRST_INTERVIEW: 4,
    ApplicationStage.SECOND_INTERVIEW: 5,
    ApplicationStage.TECHNICAL_INTERVIEW: 6,
    ApplicationStage.FINAL_INTERVIEW: 7,
    ApplicationStage.OFFER: 8,
    ApplicationStage.REJECTED: 9,
    ApplicationStage.WITHDRAWN: 9,
    ApplicationStage.OTHER: -1,
}

_INTERVIEW_STAGES = {
    ApplicationStage.FIRST_INTERVIEW,
    ApplicationStage.SECOND_INTERVIEW,
    ApplicationStage.TECHNICAL_INTERVIEW,
    ApplicationStage.FINAL_INTERVIEW,
}


@dataclass(frozen=True, slots=True)
class TaskSpec:
    task_type: TaskType
    title: str
    description: str | None
    due_at: datetime | None
    priority: TaskPriority


def next_stage(
    current: ApplicationStage,
    event_type: JobEventType,
    extracted: ApplicationStage | None,
) -> ApplicationStage:
    if event_type == JobEventType.REJECTION:
        return ApplicationStage.REJECTED
    if event_type == JobEventType.OFFER:
        return ApplicationStage.OFFER

    proposed: ApplicationStage | None = None
    if event_type == JobEventType.ASSESSMENT_RECEIVED:
        proposed = ApplicationStage.ASSESSMENT
    elif event_type in {
        JobEventType.INTERVIEW_INVITATION,
        JobEventType.INTERVIEW_RESCHEDULED,
    } and extracted in _INTERVIEW_STAGES:
        proposed = extracted

    if proposed is None:
        return current
    if _STAGE_ORDER[proposed] > _STAGE_ORDER[current]:
        return proposed
    return current


def task_for_event(extraction: JobEmailExtraction) -> TaskSpec | None:
    if extraction.event_type in {
        JobEventType.INTERVIEW_INVITATION,
        JobEventType.INTERVIEW_RESCHEDULED,
    }:
        return TaskSpec(
            task_type=TaskType.PREPARE_INTERVIEW,
            title=extraction.action_description or "Prepare for interview",
            description=None,
            due_at=extraction.interview_datetime,
            priority=TaskPriority.HIGH,
        )
    if extraction.event_type == JobEventType.ASSESSMENT_RECEIVED:
        return TaskSpec(
            task_type=TaskType.COMPLETE_ASSESSMENT,
            title=extraction.action_description or "Complete assessment",
            description=None,
            due_at=extraction.deadline,
            priority=TaskPriority.HIGH,
        )
    if extraction.event_type == JobEventType.OFFER:
        return TaskSpec(
            task_type=TaskType.REVIEW_OFFER,
            title=extraction.action_description or "Review offer",
            description=None,
            due_at=extraction.deadline,
            priority=TaskPriority.HIGH,
        )
    return None

