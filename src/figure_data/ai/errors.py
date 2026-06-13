class AIError(Exception):
    """Base class for AI infrastructure errors."""


class AIPromptError(AIError):
    """Raised when a prompt definition cannot be resolved."""


class AIProviderConfigurationError(AIError):
    """Raised when AI provider configuration is missing or unsupported."""


class AIProviderError(AIError):
    """Raised when an AI provider cannot produce a response."""


class AIOutputValidationError(AIError):
    """Raised when model output cannot satisfy the expected schema."""


class AIRunNotFoundError(AIError):
    """Raised when an AI run id does not exist."""
