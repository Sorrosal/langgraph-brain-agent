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
- [ ] **Phase 1 — Core graph**: LangGraph agent, PostgreSQL checkpointer, crash recovery.
- [ ] **Phase 2 — Human-in-the-loop + idempotency**: `interrupt()` approvals, idempotent
  side effects.
- [ ] **Phase 3 — Brain**: rules (`rules/*.yaml`), long-term memory, context assembly.
- [ ] **Phase 4 — Business tools**: email, tasks, CRM.
- [ ] **Phase 5 — API**: FastAPI with SSE streaming and JWT auth.
- [ ] **Phase 6 — Frontend + landing**: React (FSD) UI and GitHub Pages landing.
- [ ] **Phase 7 — Production hardening**: observability, limits, security review.

## Quickstart (dev)

Requirements: Docker, [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by `uv`).

```bash
# 1. Start PostgreSQL with pgvector
docker compose up -d postgres

# 2. Configure environment
cp .env.example .env   # then set OPENAI_API_KEY

# 3. Install and run the backend
cd backend
uv sync
uv run uvicorn brain_agent.api.app:create_app --factory --reload
# -> http://127.0.0.1:8000/health

# 4. Run the tests
uv run pytest
```

## Repository layout

```
backend/     Python backend (LangGraph agent, FastAPI) managed with uv
rules/       Declarative agent rules (phase 3)
frontend/    React UI (phase 6)
```

## License

[MIT](LICENSE)
