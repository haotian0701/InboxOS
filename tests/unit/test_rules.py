from datetime import UTC, datetime

from packages.schemas.domain import ApplicationStage, JobEventType, TaskType
from packages.schemas.email import JobEmailExtraction
from packages.workflows import next_stage, task_for_event


def test_stage_advances_for_interview_invitation() -> None:
    assert (
        next_stage(
            ApplicationStage.APPLIED,
            JobEventType.INTERVIEW_INVITATION,
            ApplicationStage.SECOND_INTERVIEW,
        )
        == ApplicationStage.SECOND_INTERVIEW
    )


def test_older_event_does_not_move_stage_backwards() -> None:
    assert (
        next_stage(
            ApplicationStage.FINAL_INTERVIEW,
            JobEventType.ASSESSMENT_RECEIVED,
            ApplicationStage.ASSESSMENT,
        )
        == ApplicationStage.FINAL_INTERVIEW
    )


def test_rejection_closes_stage_regardless_of_current_rank() -> None:
    assert (
        next_stage(
            ApplicationStage.FINAL_INTERVIEW,
            JobEventType.REJECTION,
            ApplicationStage.REJECTED,
        )
        == ApplicationStage.REJECTED
    )


def test_interview_task_uses_extracted_datetime() -> None:
    due_at = datetime(2026, 10, 12, 7, 45, tzinfo=UTC)
    extraction = JobEmailExtraction(
        is_job_related=True,
        event_type=JobEventType.INTERVIEW_INVITATION,
        application_stage=ApplicationStage.SECOND_INTERVIEW,
        interview_datetime=due_at,
        action_required=True,
        action_description="Prepare for second interview",
        confidence=0.94,
    )
    task = task_for_event(extraction)
    assert task is not None
    assert task.task_type == TaskType.PREPARE_INTERVIEW
    assert task.due_at == due_at


def test_rejection_does_not_create_task() -> None:
    extraction = JobEmailExtraction(
        is_job_related=True,
        event_type=JobEventType.REJECTION,
        application_stage=ApplicationStage.REJECTED,
        action_required=False,
        confidence=0.94,
    )
    assert task_for_event(extraction) is None

