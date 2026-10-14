# langgraph-brain-agent

[![Backend CI](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/frontend-ci.yml)
[![Release images](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/release-images.yml/badge.svg)](https://github.com/Sorrosal/langgraph-brain-agent/actions/workflows/release-images.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A **LangGraph** business/operations agent. It reads and drafts email, manages tasks and talks to
a CRM, while a "brain" layer (long-term memory, situational context and declarative rules)
keeps it on a leash. Served over FastAPI (SSE streaming, JWT auth) with a React UI.

Landing page: <https://sorrosal.github.io/langgraph-brain-agent/>

## Key guarantees

- **Crash-safe durable execution.** Every superstep is checkpointed in PostgreSQL before the
  next one starts. A run that dies is reclaimed through an expiring lease and resumed from its
  last checkpoint by any process.
- **Exactly-once tool side effects.** A ledger records each tool call before it runs. A replay
  returns the stored result; a call whose outcome is unknown is retried only when the tool is
  declared retry-safe, otherwise a human decides.
- **Human in the loop.** Sensitive calls pause at an `interrupt()` until a person approves,
  edits, rejects or answers them.
- **Rules fail closed.** Hard rules in `rules/*.yaml` are enforced in code before any tool
  runs. The service refuses to start without valid rules that define at least one hard rule.
- **Context engineering.** A stable, cacheable system prompt; a per-turn context block (local
  date, user, summary, memories); email content spotlighted as untrusted and any write after
  it held for approval; old tool results cleared from the prompt; context and behaviour evals
  in `backend/evals/` (`uv run python -m evals.run`). See [docs/architecture.md](docs/architecture.md#context-engineering).
- **Long-term memory.** Per-user and organisation memories live in a pgvector-backed store and
  are recalled into each turn.

Details and limits: [docs/architecture.md](docs/architecture.md),
[docs/reliability.md](docs/reliability.md), [docs/rules.md](docs/rules.md).

## Architecture

```mermaid
flowchart LR
    UI[React UI] -- REST + SSE --> NGINX[nginx]
    NGINX -- /api --> API[FastAPI]
    API --> SUP[RunSupervisor]
    SUP --> RUN[AgentRunner]
    REC[RecoveryWorker] --> RUN
    RUN --> G[LangGraph agent]
    G --> LLM[OpenAI]
    G --> T[Tools: CRM, tasks, email, memory]
    RUN -- events --> BR[EventBroker]
    BR -- SSE --> API
    RUN --> PG[(PostgreSQL + pgvector)]
    G --> PG
    T --> PG
    RULES[rules/*.yaml] --> G
```

The agent graph (each node's contract is in [docs/architecture.md](docs/architecture.md)):

```mermaid
flowchart TD
    S([START]) --> LC[load_context]
    LC --> R[reason]
    R -- tool calls --> AG[approval_gate]
    R -- final answer --> MEM[memorize]
    AG -- verdicts need a human --> AW[await_approval]
    AG -- calls cleared --> RU[resolve_uncertain]
    AW --> RU
    RU --> TL[tools]
    TL --> R
    TL -- uncertain call left --> RU
    MEM --> SUM[summarize]
    SUM --> E([END])
```

`load_context`, `memorize` and `summarize` exist only when a store, memory extraction or a
context budget is configured (the API enables all three); `resolve_uncertain` exists when a
tool ledger is configured. When every call of a batch is answered at the gate (blocked), both
the gate and `await_approval` route straight back to `reason`.

## Quickstart (dev)

Requirements: Docker, [uv](https://docs.astral.sh/uv/) (installs Python 3.12) and Node 22.

```bash
# 1. PostgreSQL with pgvector
docker compose up -d postgres

# 2. Create .env at the repo root and set at least OPENAI_API_KEY (see Configuration)

# 3. Backend -> http://127.0.0.1:8000 (interactive docs at /docs)
cd backend
uv sync
uv run uvicorn brain_agent.api.app:create_app --factory --reload

# 4. Frontend -> http://localhost:5173 (see frontend/README.md)
cd ../frontend
npm ci
npm run dev
```

In development open registration is on: the first account you register becomes `admin`, later
ones `operator`. Only admins can edit rules.

## Configuration

Settings are environment variables (or a `.env` at the repo root; `backend/.env` overrides it).
Names are case-insensitive. They are defined in `backend/src/brain_agent/config.py`.

| Variable | Default | Description |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `development`, `test` or `production`. Production requires `JWT_SECRET`. |
| `DATABASE_URL` | `postgresql://brain:brain@127.0.0.1:5432/brain` | PostgreSQL connection string. Prefer `127.0.0.1` over `localhost` on Windows. |
| `OPENAI_API_KEY` | _(none)_ | OpenAI key for chat and embeddings; without it semantic recall is unavailable. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for memory search. |
| `OPENAI_TIMEOUT_SECONDS` | `60` | Timeout of each OpenAI request. |
| `JWT_SECRET` | _(generated in dev)_ | HS256 signing key; 32+ characters, required in production. In development set it too, or every backend restart signs everyone out. |
| `JWT_TTL_MINUTES` | `60` | Token lifetime, 5 to 1440. |
| `AUTH_HASH_CONCURRENCY` | `4` | Password hashes/verifications running at once. |
| `ALLOW_REGISTRATION` | _(unset)_ | Open self-registration; unset means on in development, off otherwise. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed origins. |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `10` | Login attempts per client IP and email. |
| `RATE_LIMIT_LOGIN_IP_PER_MINUTE` | `30` | Login attempts per client IP across all emails. |
| `RATE_LIMIT_REGISTER_PER_HOUR` | `5` | Registrations per client IP. |
| `RATE_LIMIT_MESSAGES_PER_MINUTE` | `30` | Messages per user. |
| `RATE_LIMIT_RULES_WRITES_PER_MINUTE` | `10` | Rule file writes per user. |
| `RATE_LIMIT_MAX_BUCKETS` | `10000` | Cap of in-memory rate-limit buckets (least recently used are evicted). |
| `SSE_HEARTBEAT_SECONDS` | `15` | Idle time before an event stream sends a keep-alive comment. |
| `CONTEXT_MAX_TOKENS` | `12000` | Approximate history size before older messages are summarised. |
| `CONTEXT_KEEP_LAST_MESSAGES` | `12` | Recent messages that are never summarised away. |
| `MEMORY_RECALL_LIMIT` | `5` | Memories recalled at the start of each turn. |
| `MEMORY_EXTRACTION_ENABLED` | `true` | Extract durable memories after each turn (one extra model call). |
| `APPROVAL_TTL_HOURS` | `72` | Pending approvals undecided for this long are dismissed automatically. |
| `APPROVAL_SWEEP_SECONDS` | `600` | How often the expiry sweep runs. |
| `RULES_DIR` | `<repo>/rules` | Directory of `*.yaml` rule files. |
| `EMAIL_PROVIDER` | `outbox` | `outbox` stores mail in PostgreSQL only; `smtp` really sends. |
| `EMAIL_FROM` | `agent@acme.com` | Sender address. |
| `EMAIL_TIMEOUT_SECONDS` | `20` | SMTP/IMAP timeout. |
| `SMTP_HOST` | _(none)_ | SMTP server. |
| `SMTP_PORT` | `465` | SMTP port. |
| `SMTP_USERNAME` | _(none)_ | SMTP user. |
| `SMTP_PASSWORD` | _(none)_ | SMTP password. |
| `SMTP_SECURITY` | `ssl` | `ssl`, `starttls` or `none` (`none` is only accepted for localhost). |
| `IMAP_HOST` | _(none)_ | IMAP server for the inbox. |
| `IMAP_PORT` | `993` | IMAP port. |
| `IMAP_USERNAME` | _(none)_ | IMAP user. |
| `IMAP_PASSWORD` | _(none)_ | IMAP password. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |
| `LOG_FORMAT` | _(unset)_ | `json` or `console`; unset means `json` in production, `console` elsewhere. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(none)_ | OTLP/HTTP base URL (e.g. `http://collector:4318`); unset disables OpenTelemetry. |

Variables that are not `Settings` fields: `FORWARDED_ALLOW_IPS` (proxies whose `X-Forwarded-For`
uvicorn trusts; container-level), `TAG` and `POSTGRES_PASSWORD` (compose only).

## Production deployment

`docker-compose.prod.yml` runs PostgreSQL, the backend and the nginx-served frontend, which
proxies `/api/` to the backend (same origin, so no CORS is needed).

```bash
# .env next to the compose file (never commit it)
ENVIRONMENT=production
JWT_SECRET=<32+ random characters>
OPENAI_API_KEY=sk-...
POSTGRES_PASSWORD=<password>
DATABASE_URL=postgresql://brain:<password>@postgres:5432/brain

docker compose -f docker-compose.prod.yml --env-file .env up -d --build
# UI + API on http://localhost:8080
```

- **Images.** Pushes to `main` and `v*` tags publish
  `ghcr.io/sorrosal/langgraph-brain-agent-backend` and `...-frontend`, but only after the backend
  and frontend tests pass (`.github/workflows/release-images.yml`). Pull them with `TAG=<tag>`
  (default `latest`) instead of building.
- **Client IPs.** The rate limiter keys on the connection address, and the backend trusts
  `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS` (default `127.0.0.1` in the image). Compose
  pins its internal network to `172.28.0.0/16` and trusts that range, so the limiter sees real
  clients through nginx. If you put another proxy in front, set `FORWARDED_ALLOW_IPS` to its
  address.
- **Registration** is off in production unless `ALLOW_REGISTRATION=true`. The first account
  becomes `admin`, so create it deliberately (enable registration, register, disable).
- **Shutdown.** The backend has `stop_grace_period: 30s`; a run cut off by a stop is recovered
  once its lease (60 s) expires.
- **One backend replica.** The event broker and rate limiter are in-process (see
  [docs/reliability.md](docs/reliability.md)).

## Observability

- **Logs:** JSON lines in production (`LOG_FORMAT`), each with a `request_id` (also returned in
  the `X-Request-ID` response header) and, inside runs, `thread_id` and `owner`.
- **OpenTelemetry:** set `OTEL_EXPORTER_OTLP_ENDPOINT` for traces (`agent.run`, `tool.execute`,
  FastAPI requests) and metrics (`brain_agent.runs.started`, `brain_agent.runs.completed`,
  `brain_agent.tool_executions`). Exception messages are never put on spans.
- **LangSmith:** LangChain reads `LANGSMITH_TRACING` and `LANGSMITH_API_KEY` from the
  environment; set them to trace model calls. They are not `Settings` fields.
- **Probes:** `GET /health` (liveness) and `GET /ready` (database, rules; `503` when
  unavailable, `degraded` with `200` when the recovery worker is down).

## Security notes

JWT bearer auth with argon2 password hashes, in-process rate limits, rule- and metadata-driven
approvals for sensitive tools, sanitized errors and security headers. See
[SECURITY.md](SECURITY.md) for the threat model and how to report a vulnerability.

## Roadmap

- [x] **Phase 0 — Scaffold**: monorepo layout, `uv`-managed backend, settings, health endpoint,
  Postgres (pgvector) via Docker Compose, CI.
- [x] **Phase 1 — Core graph**: LangGraph agent, PostgreSQL checkpointer, crash recovery.
- [x] **Phase 2 — Human-in-the-loop + idempotency**: `interrupt()` approvals, idempotent
  side effects.
- [x] **Phase 3 — Brain**: rules (`rules/*.yaml`), long-term memory, context assembly.
- [x] **Phase 4 — Business tools**: email, tasks, CRM.
- [x] **Phase 5 — API**: FastAPI with SSE streaming and JWT auth.
- [x] **Phase 6 — Frontend + landing**: React (FSD) UI and GitHub Pages landing.
- [x] **Phase 7 — Production hardening**: observability, limits, security review, production
  images and documentation.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). Released under the [MIT License](LICENSE).
