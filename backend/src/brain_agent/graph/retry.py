"""Retry classification for graph nodes."""

import openai

# Mirrors the statuses the OpenAI client itself treats as retryable.
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429})


def is_transient_error(exc: Exception) -> bool:
    """Return ``True`` for failures worth retrying: network issues, rate limits, 5xx."""
    if isinstance(exc, (ConnectionError, TimeoutError, openai.APIConnectionError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS_CODES or exc.status_code >= 500
    return False
