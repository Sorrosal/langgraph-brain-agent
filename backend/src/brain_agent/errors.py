"""Domain exceptions for the Brain Agent backend."""


class BrainAgentError(Exception):
    """Base class for errors raised by the Brain Agent."""


class ConfigurationError(BrainAgentError):
    """Raised when required configuration is missing or invalid."""


class ThreadBusyError(BrainAgentError):
    """Raised when a new turn is started on a thread that still has unfinished work."""

    def __init__(self, thread_id: str, next_nodes: tuple[str, ...]) -> None:
        self.thread_id = thread_id
        self.next_nodes = next_nodes
        super().__init__(
            f"Thread {thread_id!r} has unfinished work (pending nodes: {', '.join(next_nodes)}); "
            "resume it before sending a new message."
        )
