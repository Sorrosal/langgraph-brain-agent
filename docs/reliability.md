# Reliability

How a run survives a crash, why a tool side effect is not repeated, what is *not* guaranteed,
and what to do when something is stuck. Code references are to `backend/src/brain_agent/`.

## The model in one paragraph

LangGraph gives at-least-once execution: after a crash the node that was running is executed
again from the last checkpoint. Three mechanisms turn that into a safe system: synchronous
checkpoints (no lost progress), a run lease with fencing (one live owner per thread, a
recoverable orphan when it dies) and a tool ledger (a replayed tool call does not repeat its
side effect). When the ledger cannot know whether a side effect happened, it asks a human.

## 1. Synchronous durability

`AgentRunner` invokes the graph with `durability="sync"`: each superstep's checkpoint is
written to PostgreSQL before the next superstep starts. The most that a crash can lose is the
node that was executing; it re-runs on resume. Because nodes can re-run, the approval payload
is a pure function of the state (`hitl/models.py`), `await_approval` only reads persisted
verdicts, and `memorize` deduplicates what it stores.

## 2. Leases, heartbeats and fencing tokens

Each thread has one row in `agent_runs` (`persistence/runs.py`).

- **Claim.** `mark_running` inserts or updates the row to `running` with an owner and
  `lease_expires_at = now() + lease`. It succeeds only if the run is not running, its lease has
  expired, or the caller is already the owner; otherwise `ThreadBusyError` (`409`). Every claim
  increments `fencing_token`.
- **Heartbeat.** While the graph runs, a background task renews the lease every `lease / 3`
  (lease default 60 s, so every 20 s). A failed beat (database blip) is logged and survived;
  the lease outlasts several intervals.
- **Fencing.** Heartbeat, `mark_finished` and `record_error` all require
  `owner AND fencing_token` to match. If a heartbeat finds that it no longer holds the row
  (another process claimed it after a stall), the runner cancels its graph task and raises
  `LeaseLostError` (`503 lease_lost`); it never writes the run as finished. The same check runs
  when the run ends: a stale owner's `mark_finished` writes nothing and surfaces `lease_lost`.
- **Release.** `completed` and `interrupted` release the lease (owner and expiry cleared). A
  thread paused on a human decision is `interrupted`, not an orphan.
- **Shutdown.** On SIGINT/SIGTERM or lifespan shutdown the supervisor cancels active runs.
  Cancellation is not recorded: the row stays `running` and is recovered after the lease expires.

What fencing does not cover: it guards the `agent_runs` row. A stalled process that is cancelled
only stops at its next `await`, so a tool call already in flight may still finish, and checkpoint
writes are not themselves fenced. The tool ledger (section 4) is what keeps such an overlap from
duplicating a side effect.

## 3. Recovery: `SKIP LOCKED` and the poison-pill limit

`RecoveryWorker` polls every 15 s (inside a `SupervisedLoop` that restarts it with backoff, and
makes `/ready` report `degraded` while it is down).

- **Claim.** `claim_orphans` selects up to `batch_size` (10) rows with `status = 'running'` and
  an expired or missing lease, using `FOR UPDATE SKIP LOCKED`, and in the same statement takes
  the lease for this process, increments `attempts` and `fencing_token`. Concurrent workers or
  replicas never get the same run.
- **Resume.** Claimed runs are resumed with `AgentRunner.resume`, up to 4 at a time, each with a
  300 s timeout (a timed-out run stays `running` and is retried when its lease expires). The
  thread owner is looked up so memory and tools act for the right user. Resume of a thread that
  is waiting for a human does nothing and closes the row as `interrupted`.
- **Poison pill.** Orphans that already used `max_attempts` (3) are not claimed again. They are
  set to `failed` with `last_error` ending in
  `gave up after N recovery attempts (max attempts reached)` and a `run_abandoned` error is
  logged. `attempts` resets to 0 when a user starts a new run; resuming keeps the count.
- **Failure policy** (runner, after node-level retries are exhausted):
  - transient errors (network, timeouts, OpenAI 408/409/429/5xx): `last_error` is recorded,
    the status stays `running`, the lease is not renewed, so recovery retries later;
  - any other error: the run is marked `failed`, since retrying a deterministic failure
    cannot help.
- **Failed threads are not wedged.** The next user message on a thread whose run is `failed`
  first answers its dangling tool calls with an error `ToolMessage` ("the run was abandoned"),
  then starts the new turn.

## 4. The tool ledger

`tools/idempotency.py` and `persistence/tool_ledger.py`. Every tool call is recorded in
`tool_executions` under the key `thread_id:tool_call_id`, together with a SHA-256 of its
canonical arguments, **before** the tool runs.

| Status | Meaning | On replay |
| --- | --- | --- |
| `started` | Recorded; the tool was (or is being) executed, no outcome stored. | Outcome unknown: see below. |
| `succeeded` | The result is stored. | Stored result returned, tool not run (`tool_replayed`). |
| `failed` | The tool errored (or was interrupted, or skipped by a human). | Runs again, as a failure is not a committed side effect. A call a human skipped returns "Skipped by human" instead. |
| `retry_authorized` | A human decided the effect did not happen and the call may run again. | Runs again (the row goes back to `started`, `attempts` + 1). |

Flow for a call: `begin` inserts `started` or returns the existing row. A new row runs the tool,
then `complete` or `fail`. An existing row is checked first: if the stored argument hash differs
from the call's (the key is per tool call id, so that indicates a bug) it is treated as uncertain.

### `retry_safe` semantics

A tool declares `metadata["retry_safe"] = True` when repeating it with the same idempotency key
cannot repeat the effect, because the provider deduplicates on that key. `make_tool` defaults it
to `True` for the built-in tools: CRM, task and outbox-email writes carry the key in a `UNIQUE
idempotency_key` column and memory writes are deduplicated. The one exception is real email:
the `smtp` gateway sets `retry_safe = False` (SMTP cannot deduplicate); it sends a deterministic
`Message-ID` and an `X-Idempotency-Key` header so a human can look for the message.

- A `started` row and `retry_safe` tool: run again with the same key, no human needed.
- A `started` row and a tool that is **not** retry-safe: the effect may have happened; escalate.

### `outcome_unknown` escalation

A tool failure marked `outcome_unknown` (for example a timeout after the SMTP `DATA` command)
on a non-retry-safe tool is *not* recorded as `failed`. The row stays `started` and
`UncertainExecutionError` is raised, so the case is escalated exactly like a crash mid-call.

### Human resolution

The `resolve_uncertain` node runs before `tools`. For all uncertain calls of the batch it raises
one `UncertainExecutionInterrupt`; the run pauses as `interrupted` and the UI shows the calls.
The reviewer answers each call (`POST /threads/{id}/uncertain`, decisions keyed by call id):

| Decision | Ledger effect |
| --- | --- |
| `confirm_done` | Marked `succeeded` with the given message (default "Confirmed done by human"); the tool does not run. |
| `retry` | Marked `retry_authorized`; the tool runs again with the same key. |
| `skip` | Marked `failed` with "Skipped by human"; the model is told it was skipped. |

The `tools` node itself never asks a human: if an uncertain call reaches it, it does nothing and
the graph routes back to `resolve_uncertain`.

## 5. What is and is not guaranteed

Guaranteed (given PostgreSQL durability):

- A run interrupted by a crash, restart or lost lease is resumed from its last checkpoint,
  provided a backend process is running and the run has not exhausted `max_attempts`.
- A tool call with a stored result is never executed again. A call with an unknown outcome is
  never silently repeated unless the tool is declared retry-safe.
- A thread has at most one live owner of its run row; a stale owner cannot overwrite the new
  owner's state in `agent_runs`.
- Rules are evaluated in code before a tool runs, on every execution of the gate.

Not guaranteed:

- **Single replica for the event broker.** The `EventBroker` is in-process. A client connected
  to replica A never sees events of a run on replica B. Clients that miss events re-read
  `GET /threads/{id}`, which reflects the checkpointed state. The broker keeps 500 events per
  thread and forgets idle ones after 10 minutes.
- **Single replica for the rate limiter.** Buckets are per process: with N replicas a client
  can make up to N times the configured rate. A restart resets the buckets.
- **Run status memory.** The "last failure" shown for a thread that failed in this process is
  held in memory (latest 1000 threads); it is lost on restart (the registry still has the
  `failed` row).
- **The pending-approvals list** scans the user's latest 100 threads; the checkpointer has no
  index of paused threads.
- **Side effects of non-retry-safe tools** are at most once only because a human resolves the
  uncertain window; the system cannot verify what an external provider did.
- Availability depends on PostgreSQL and the OpenAI API; recovery needs a live backend process
  and a lease that has expired (up to 60 s plus the 15 s poll interval).

## 6. Operations runbook

All queries run against the application database (`psql "$DATABASE_URL"`).

### A run looks stuck

1. `GET /threads/{id}` shows `run.status`. `running` with no progress means a live owner or an
   orphan waiting for its lease to expire.
2. Look at the row:

   ```sql
   SELECT status, owner, lease_expires_at, attempts, last_error, fencing_token
   FROM agent_runs WHERE thread_id = '<thread id>';
   ```

3. If `lease_expires_at` is in the past, the recovery worker picks it up within about 15 s.
   If it does not, check `GET /ready` (`degraded` means the worker is down) and the logs for
   `recovery_pass_failed`, `background_worker_crashed` and `recovery_resume_failed`.
4. If the lease keeps being renewed, the run is genuinely executing (a slow model call or
   tool). It ends by itself or fails with a stable error code.
5. If the thread is `interrupted`, it is waiting for a person, not stuck: resolve the approval
   or uncertain execution.

### A run is poisoned (`failed` after repeated recovery)

1. Read `last_error` in `agent_runs`, and the logs for `run_abandoned` and the thread id.
2. Fix the cause (credentials, a bad tool argument, an outage).
3. Easiest recovery: send a new message on the thread. The dangling tool calls are closed with
   an error and the new turn starts (`attempts` is reset).
4. To retry the *same* pending work, an operator can make the row claimable again, after the
   cause is fixed:

   ```sql
   UPDATE agent_runs SET status = 'running', lease_expires_at = NULL, attempts = 0
   WHERE thread_id = '<thread id>' AND status = 'failed';
   ```

   The recovery worker claims it on its next pass. This is a manual database intervention.

### Resolve an uncertain execution

1. The thread shows a pending `uncertain_execution` interrupt (UI approvals page, or
   `GET /threads/{id}` → `pending_interrupt`) listing the tool, its arguments and why.
2. Check the outside world: for email, search the sent folder or the provider for the
   `Message-ID` / `X-Idempotency-Key` header; for other systems look for the record.
3. Answer with one decision per call id:

   ```bash
   curl -X POST "$API/threads/$THREAD/uncertain" -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"decisions": {"<tool call id>": {"type": "confirm_done"}}}'
   ```

   Use `confirm_done` if it happened, `retry` if it did not, `skip` to abandon the call. A
   decision missing for a pending call, or for an unknown id, is rejected with `422` and the
   thread stays paused.
4. The ledger row for the call is in `tool_executions` (`idempotency_key`
   `<thread id>:<tool call id>`) if you need to audit it.

### Rotate `JWT_SECRET`

Tokens are HS256 and the API holds exactly one secret; there is no key overlap.

1. Generate a new value of 32+ characters and update `JWT_SECRET` in the environment/`.env`.
2. Restart the backend (`docker compose -f docker-compose.prod.yml up -d --force-recreate backend`).
3. Every previously issued token is now invalid: users sign in again, and new or reconnecting
   event streams need a new token. Running agent work is not affected; only API authentication is.
4. Passwords are not affected (they are argon2 hashes, independent of the secret).
