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


class UncertainExecutionError(BrainAgentError):
    """Raised when a tool call whose outcome is unknown would be executed without a human."""

    def __init__(self, tool_name: str, call_id: str, reason: str) -> None:
        self.tool_name = tool_name
        self.call_id = call_id
        super().__init__(f"Tool call {call_id!r} ({tool_name}) has an uncertain outcome: {reason}")


class NotFoundError(BrainAgentError):
    """Raised when a business record (contact, deal, task) does not exist."""

    def __init__(self, kind: str, record_id: str) -> None:
        self.kind = kind
        self.record_id = record_id
        super().__init__(f"{kind} {record_id!r} not found")


class IntegrationError(BrainAgentError):
    """Raised when an external provider (SMTP, IMAP, ...) fails. Messages never hold secrets.

    ``outcome_unknown`` is set when the side effect may have happened despite the failure (a
    timeout after the message was handed over), so retrying could repeat it.
    """

    def __init__(self, message: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        super().__init__(message)
