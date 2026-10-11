# langgraph-brain-agent

A production-grade **LangGraph** business/operations agent. It reads and drafts email, manages
tasks and talks to your CRM, while a "brain" layer keeps long-term memory, situational context
and an explicit rule set in charge. State is durable in PostgreSQL, so a crash mid-run resumes
where it left off, and every sensitive action pauses for a human to approve, edit or reject.
Served over FastAPI (SSE streaming, JWT auth) with a React UI and a public landing page.

## Features

- **Human-in-the-loop** — sensitive actions stop at a LangGraph `interrupt()` and wait for
  approval, edits or rejection before they execute.
- **Crash-safe durable state** — every step is checkpointed in PostgreSQL via
  `AsyncPostgresSaver`; a killed process resumes from the last checkpoint, with idempotent
  tool calls so nothing is sent twice.
- **A brain, not just a loop** — long-term memory (`AsyncPostgresStore` + pgvector), context
  assembly and declarative hard/soft rules in `rules/*.yaml`.
- **Business tools** — email, task management and CRM integrations designed for real
  operations work.
- **React UI** — a Feature-Sliced Design frontend to chat, stream progress and resolve
  approvals.
- **Landing page** — a public GitHub Pages site describing the project.

## Roadmap

- [x] **Phase 0 — Scaffold**: monorepo layout, `uv`-managed backend, settings, health endpoint,
  Postgres (pgvector) via Docker Compose, CI.
- [x] **Phase 1 — Core graph**: LangGraph agent, PostgreSQL checkpointer, crash recovery.
- [x] **Phase 2 — Human-in-the-loop + idempotency**: `interrupt()` approvals, idempotent
  side effects.
- [x] **Phase 3 — Brain**: rules (`rules/*.yaml`), long-term memory, context assembly.
- [x] **Phase 4 — Business tools**: email, tasks, CRM.
- [x] **Phase 5 — API**: FastAPI with SSE streaming and JWT auth.
- [ ] **Phase 6 — Frontend + landing**: React (FSD) UI and GitHub Pages landing.
- [ ] **Phase 7 — Production hardening**: observability, limits, security review.

## Quickstart (dev)

Requirements: Docker, [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by `uv`).

```bash
# 1. Start PostgreSQL with pgvector
docker compose up -d postgres

# 2. Configure environment: create a .env file at the repo root (see Configuration)
#    and set at least OPENAI_API_KEY

# 3. Install and run the backend
cd backend
uv sync
uv run uvicorn brain_agent.api.app:create_app --factory --reload
# -> http://127.0.0.1:8000/health

# 4. Run the tests
uv run pytest
```

## Configuration

Settings are read from environment variables. For local development, create a `.env` file at
the repository root with these variables (an optional `backend/.env` overrides it). Both paths
are resolved relative to the code, so the working directory does not matter.

| Variable         | Default                                         | Description                                                    |
| ---------------- | ----------------------------------------------- | -------------------------------------------------------------- |
| `OPENAI_API_KEY` | _(none, required to run the agent)_             | OpenAI API key used by the chat model.                         |
| `OPENAI_MODEL`   | `gpt-4o-mini`                                   | OpenAI chat model name.                                        |
| `DATABASE_URL`   | `postgresql://brain:brain@127.0.0.1:5432/brain` | PostgreSQL connection string (matches `docker-compose.yml`). Prefer `127.0.0.1` over `localhost` on Windows (async psycopg may stall on IPv6).   |
| `LOG_LEVEL`      | `INFO`                                          | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.        |
| `ENVIRONMENT`    | `development`                                   | One of `development`, `test`, `production`.                    |

Example `.env`:

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=postgresql://brain:brain@127.0.0.1:5432/brain
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## Repository layout

```
backend/     Python backend (LangGraph agent, FastAPI) managed with uv
rules/       Declarative agent rules (phase 3)
frontend/    React UI (phase 6)
```

## License

[MIT](LICENSE)
