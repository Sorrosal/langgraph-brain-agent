"""Domain exceptions for the Brain Agent backend."""


class BrainAgentError(Exception):
    """Base class for errors raised by the Brain Agent."""


class ConfigurationError(BrainAgentError):
    """Raised when required configuration is missing or invalid."""


class ThreadBusyError(BrainAgentError):
    """Raised when a new turn is started on a thread that still has unfinished work."""

    def __init__(
        self, thread_id: str, next_nodes: tuple[str, ...] = (), *, approval_pending: bool = False
    ) -> None:
        self.thread_id = thread_id
        self.next_nodes = next_nodes
        if approval_pending:
            message = f"Thread {thread_id!r} is waiting for a human decision (approval pending)."
        elif next_nodes:
            message = (
                f"Thread {thread_id!r} has unfinished work (pending nodes: "
                f"{', '.join(next_nodes)}); resume it before sending a new message."
            )
        else:
            message = f"Thread {thread_id!r} is leased to another live run."
        super().__init__(message)


class LeaseLostError(BrainAgentError):
    """Raised when a run lost its lease to another owner and was stopped."""

    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        super().__init__(
            f"Lease on thread {thread_id!r} was lost to another owner; the run was stopped."
        )


class InvalidApprovalError(BrainAgentError):
    """Raised when an approval response does not match the actions awaiting a decision."""


class NoPendingApprovalError(BrainAgentError):
    """Raised when an approval is submitted for a thread that is not waiting for one."""

    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        super().__init__(f"Thread {thread_id!r} has no pending approval.")
