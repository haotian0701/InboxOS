from enum import StrEnum


class ApplicationStage(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    FIRST_INTERVIEW = "first_interview"
    SECOND_INTERVIEW = "second_interview"
    TECHNICAL_INTERVIEW = "technical_interview"
    FINAL_INTERVIEW = "final_interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OTHER = "other"


class ApplicationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EmailProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    IGNORED = "ignored"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class JobEventType(StrEnum):
    APPLICATION_RECEIVED = "application_received"
    INTERVIEW_INVITATION = "interview_invitation"
    INTERVIEW_RESCHEDULED = "interview_rescheduled"
    ASSESSMENT_RECEIVED = "assessment_received"
    REJECTION = "rejection"
    OFFER = "offer"
    RECRUITER_MESSAGE = "recruiter_message"
    FOLLOW_UP = "follow_up"
    MANUAL_UPDATE = "manual_update"
    UNKNOWN = "unknown"


class TaskType(StrEnum):
    REPLY_TO_RECRUITER = "reply_to_recruiter"
    PREPARE_INTERVIEW = "prepare_interview"
    COMPLETE_ASSESSMENT = "complete_assessment"
    FOLLOW_UP = "follow_up"
    SUBMIT_DOCUMENT = "submit_document"
    REVIEW_OFFER = "review_offer"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"

