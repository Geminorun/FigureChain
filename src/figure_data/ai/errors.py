class AIError(Exception):
    """Base class for AI infrastructure errors."""


class AIPromptError(AIError):
    """Raised when a prompt definition cannot be resolved."""


class AIProviderConfigurationError(AIError):
    """Raised when AI provider configuration is missing or unsupported."""


class AIProviderError(AIError):
    """Raised when an AI provider cannot produce a response."""


class AIProviderTimeoutError(AIProviderError):
    """Raised when the provider request times out."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when the provider returns a rate-limit response."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when the provider is unavailable or returns a retryable server error."""


class AIOutputValidationError(AIError):
    """Raised when model output cannot satisfy the expected schema."""


class AIOutputPolicyViolation(AIOutputValidationError):
    """Raised when valid model output violates FigureChain business boundaries."""


class AIRunNotFoundError(AIError):
    """Raised when an AI run id does not exist."""
