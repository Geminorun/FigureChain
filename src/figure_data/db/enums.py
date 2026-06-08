from enum import StrEnum


class ImportBatchStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CandidateStrength(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"
    NOT_APPLICABLE = "not_applicable"


class CandidateBasis(StrEnum):
    DIRECT_INTERACTION_LIKELY = "direct_interaction_likely"
    CO_PRESENCE_LIKELY = "co_presence_likely"
    FAMILY_CLOSE = "family_close"
    FAMILY_DISTANT = "family_distant"
    TEXTUAL_OR_INDIRECT = "textual_or_indirect"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_REVIEW = "needs_review"
    PROMOTED_TO_ENCOUNTER = "promoted_to_encounter"
    REJECTED = "rejected"


class EncounterKind(StrEnum):
    DIRECT_INTERACTION = "direct_interaction"
    CO_PRESENCE = "co_presence"
    FAMILY_CONTACT = "family_contact"
    MANUAL_CONTACT = "manual_contact"


class CertaintyLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EncounterStatus(StrEnum):
    ACTIVE = "active"
    RETRACTED = "retracted"
