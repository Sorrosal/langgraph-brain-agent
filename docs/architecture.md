# Architecture

This document describes what the code does today. For the crash-safety design in depth see
[reliability.md](reliability.md); for the rule format see [rules.md](rules.md).

## Components

| Component | Code | Responsibility |
| --- | --- | --- |
| API | `api/` | FastAPI app: auth, threads, SSE events, brain (memories, rules), business data. Middleware: CORS, security headers, request id, unhandled-error catcher. |
| Container | `api/container.py` | Composition root: builds rules, tools, graph, runner, event broker, supervisor and recovery worker. |
| RunSupervisor | `runtime/supervisor.py` | Runs each request's work as an asyncio task, at most one per thread, detached from the HTTP request. |
| AgentRunner | `runtime/runner.py` | Drives the graph per thread under a lease with heartbeats and fencing; `run`, `resume`, `approve`, `resolve_uncertain`. |
| RecoveryWorker | `runtime/recovery.py` | Claims runs whose lease expired and resumes them; wrapped in a `SupervisedLoop` that restarts it if it crashes. |
| EventBroker | `runtime/events.py` | In-process per-thread pub/sub with a bounded replay buffer, feeding SSE. |
| Graph | `graph/` | The LangGraph agent (nodes below). |
| Brain | `brain/` | Rules engine, rules-backed approval policy, system prompt, memory service, context compaction. |
| HITL | `hitl/` | Approval and uncertain-execution payloads, and approval policies. |
| Tools | `tools/` | CRM, task, email and memory tools; the exactly-once wrapper (`tools/idempotency.py`). |
| Integrations | `integrations/` | PostgreSQL CRM/task/outbox repositories, SMTP/IMAP gateway, in-memory twins for tests. |
| Persistence | `persistence/` | Connection pool and schema setup, run registry, tool ledger, users, threads. |
| Observability | `observability/` | structlog configuration, optional OpenTelemetry traces and metrics. |

A request that sends a message takes this path: the route checks the rate limit and thread
ownership, reserves the thread's run slot in the `RunSupervisor`, and returns `202`. The
supervisor starts `AgentRunner.run` as a background task whose events go to the `EventBroker`.

## The graph

Built by `graph/builder.py`. State is checkpointed after every superstep
(`durability="sync"`); the recursion limit is `5 * max_steps + 9` (`max_steps` defaults to 25),
so the step guard, not LangGraph's recursion error, ends a runaway loop.

| Node | Present when | Contract |
| --- | --- | --- |
| `load_context` | a store is given | At the start of a turn (last message is human) recalls up to `MEMORY_RECALL_LIMIT` user and organisation memories into `context`. Failures degrade to empty context. |
| `reason` | always | Calls the model (bound to the tools) with the system prompt plus `summary` and `context`. Increments `step_count`. Once `step_count` reaches `max_steps` it skips the model and answers with a "reached the maximum of N reasoning steps" message. Retried up to 3 attempts with backoff on transient errors (network, 408/409/429, 5xx). |
| `approval_gate` | tools exist | Evaluates the approval policy for each unanswered tool call. Blocked calls are answered with an error `ToolMessage` and audited as `blocked`; calls needing approval are recorded in `pending_review`. A batch that reuses a tool call id is rejected whole. Never interrupts, so its write is checkpointed first. |
| `await_approval` | tools exist | Raises `interrupt()` with an `ApprovalInterrupt` for the whole batch and applies the answers (`approve`, `edit`, `reject`, `respond`). An edited call is re-checked against blocking verdicts. Clears `pending_review`. |
| `resolve_uncertain` | a tool ledger is given | Before `tools`, finds calls whose earlier execution has an unknown outcome and interrupts once with an `UncertainExecutionInterrupt` (`confirm_done`, `retry`, `skip`). |
| `tools` | tools exist | Runs the calls through `ToolNode`; with a ledger every call goes through the exactly-once wrapper. Always returns to `reason`, or to `resolve_uncertain` when an uncertain call is left. |
| `memorize` | store and memory extraction enabled | After the final answer extracts at most 3 durable memories from the turn (one model call) and stores them deduplicated. Failures are logged and ignored. |
| `summarize` | a context budget is given | If the history exceeds `CONTEXT_MAX_TOKENS` folds older messages into `summary`, keeping the last `CONTEXT_KEEP_LAST_MESSAGES` and never splitting a tool call from its results. Failures are logged and ignored. |

Edges: `START → load_context → reason`; `reason → approval_gate` when the last AI message has
tool calls, otherwise to the turn end `memorize → summarize → END` (skipping disabled nodes);
`approval_gate` and `await_approval` route to `await_approval` while `pending_review` is set,
otherwise to `resolve_uncertain` with the unanswered calls (or `reason` if none remain).

### State schema (`graph/state.py`)

| Key | Type | Meaning |
| --- | --- | --- |
| `messages` | list, `add_messages` reducer | Conversation history. |
| `summary` | `str` | Rolling summary of older turns. |
| `context` | `str` | Memories recalled for the current turn. |
| `step_count` | `int` | Reasoning steps in the current run; reset to 0 by each new user message. |
| `approvals` | list, appended | Audit trail: action id, tool name, decision type (and rule ids for `blocked`). |
| `pending_review` | `dict \| None` | Verdicts persisted by `approval_gate` for `await_approval`: the AI message id and verdicts per call id. |

## Persistence

All state is in one PostgreSQL database (pgvector image). Schema setup is idempotent and
serialised across processes by an advisory lock, so replicas can start at the same time.

| Table | Owner | Contents |
| --- | --- | --- |
| `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | `AsyncPostgresSaver` | Graph state per thread and superstep. |
| `store`, `store_vectors` (and migrations) | `AsyncPostgresStore` | Long-term memories under namespaces per user and kind, plus the shared `("org", "knowledge")` namespace; vectors only when an embeddings model is configured. Memory kinds: `fact`, `preference`, `episode`. |
| `agent_runs` | `RunRegistry` | One row per thread: status (`running`, `interrupted`, `completed`, `failed`), owner, `lease_expires_at`, `attempts`, `last_error`, `fencing_token`. |
| `tool_executions` | `ToolExecutionLedger` | One row per tool call, keyed `thread_id:tool_call_id`: `args_hash`, status (`started`, `succeeded`, `failed`, `retry_authorized`), result, error, `attempts`. |
| `users` | `PostgresUserRepository` | Accounts: unique lowercase email, argon2 hash, role `admin` or `operator` (the first user is `admin`). |
| `threads` | `PostgresThreadRepository` | Thread id, owner `user_id`, title, timestamps. |
| `crm_contacts`, `crm_deals` | CRM repository | Contacts and deals (stages `lead`, `qualified`, `proposal`, `won`, `lost`), each with a unique `idempotency_key`. |
| `tasks` | task repository | Tasks (`open`/`done`, priority) with a unique `idempotency_key`. |
| `email_messages` | outbox gateway | Sent and received mail in the `outbox` provider, unique `idempotency_key`. |

## Event flow (SSE)

`GET /threads/{id}/events` streams `text/event-stream`. Authentication uses the bearer header
or, because `EventSource` cannot set headers, `?access_token=` (this route only). Resume with
`Last-Event-ID` or `?after=<id>`; with neither, only new events are sent.

The runner translates LangGraph's `messages` and `updates` streams into these events:

| Event | Data |
| --- | --- |
| `token` | `{text}` — a chunk of the model's answer (from `reason`). |
| `tool_call` | `{name, args, id}` — the model requested a tool. |
| `tool_result` | `{id, name, status, content}` — content truncated to 2000 characters. |
| `node` | `{node}` — a node finished. |
| `interrupt` | The approval or uncertain-execution payload. |
| `run_completed` | `{status}` — `completed` or `interrupted`. |
| `run_failed` | `{code, message}` — `lease_lost`, `thread_busy`, `temporarily_unavailable` or `run_failed`; never the exception text. |

Event ids increase per thread (they start from a millisecond epoch so they also grow across
idle clean-ups). The broker keeps the last 500 events per thread and forgets idle channels
after 10 minutes; a client that missed events should re-read `GET /threads/{id}`, which always
reflects the checkpointed state. A comment line (`: keep-alive`) is sent after
`SSE_HEARTBEAT_SECONDS` of silence.

## Approvals lifecycle

1. `reason` produces tool calls; `approval_gate` evaluates the policy and stores
   `pending_review`.
2. `await_approval` interrupts; the run ends as `interrupted`, the lease is released and the
   `interrupt` event carries the actions. `GET /approvals/pending` scans the user's latest 100
   threads for paused ones.
3. The reviewer posts decisions to `POST /threads/{id}/approvals`, keyed by action id; exactly
   one decision per pending action is required (`422 invalid_approval` otherwise, and the
   thread stays paused). The runner resumes with `Command(resume=...)`.
4. Decisions: `approve` runs the call; `edit` replaces the arguments (and is re-checked against
   blocking rules); `reject` answers the model with an error; `respond` answers the model with
   the reviewer's text instead of running the tool. Each is appended to `approvals`.
5. A new message on a thread with a pending interrupt is refused with `409 thread_busy`.

An uncertain tool execution follows the same pattern through `resolve_uncertain` and
`POST /threads/{id}/uncertain` (see [reliability.md](reliability.md)).

## Rules evaluation order

Per tool call, in `approval_gate`:

1. The `CompositeApprovalPolicy` asks the rules policy (`RulesApprovalPolicy`) and the metadata
   policy (`MetadataApprovalPolicy`: `requires_approval` or `risk: high` in tool metadata).
2. The rules policy evaluates every hard rule in definition order (files sorted by name); if any
   matching rule has action `block`, the verdict is a block, otherwise `require_approval` with
   the highest risk among the matches.
3. The strictest verdict wins: block, then approval by risk, then none; ties go to the rules.
4. Block: the call is never executed nor offered; the model gets `Blocked by rule <ids>: <reason>`.
   Approval: goes to `await_approval`. None: runs.

The engine re-checks the rule files' fingerprint on use, so edits apply without a restart. An
invalid edit (or one that removes every hard rule) keeps the last good rules; the service does
not start with invalid rules or without any hard rule. Guidelines and the persona are rebuilt into the system prompt on every
model call.

## Thread admission and ownership

Every thread belongs to one user; other users get `404` (not `403`) so ids cannot be probed.
A thread runs at most one task at a time: the supervisor reserves the slot synchronously,
validates, then starts the work; a concurrent request gets `409 thread_busy`.
