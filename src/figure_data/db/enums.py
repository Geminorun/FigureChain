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


class AIPromptStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class AIRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    SCHEMA_INVALID = "schema_invalid"
    INPUT_INVALID = "input_invalid"
    OUTPUT_POLICY_VIOLATION = "output_policy_violation"
    CONFIGURATION_MISSING = "configuration_missing"
    INVALID_CHAIN_CONTEXT = "invalid_chain_context"


class AICandidateReviewSuggestedAction(StrEnum):
    PROMOTE_CANDIDATE = "promote_candidate"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    REJECT_DUPLICATE = "reject_duplicate"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_PATH_CANDIDATE = "not_path_candidate"


class AICandidateSuggestionStatus(StrEnum):
    GENERATED = "generated"
    ARCHIVED = "archived"


class AIChainExplanationStatus(StrEnum):
    GENERATED = "generated"
    ARCHIVED = "archived"


class AIJobType(StrEnum):
    CANDIDATE_REVIEW_SUGGESTION = "candidate_review_suggestion"


class AIJobTargetType(StrEnum):
    CANDIDATE = "candidate"


class AIJobTargetKind(StrEnum):
    RELATIONSHIP = "relationship"
    KINSHIP = "kinship"


class AIJobQueueBackend(StrEnum):
    DATABASE = "database"
    RQ = "rq"


class AIJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJobEventType(StrEnum):
    CREATED = "created"
    ENQUEUED = "enqueued"
    ENQUEUE_FAILED = "enqueue_failed"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REQUEUED = "requeued"
