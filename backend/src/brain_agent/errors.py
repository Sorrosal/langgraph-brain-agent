"""Domain exceptions for the Brain Agent backend."""


class BrainAgentError(Exception):
    """Base class for errors raised by the Brain Agent."""


class ConfigurationError(BrainAgentError):
    """Raised when required configuration is missing or invalid."""
