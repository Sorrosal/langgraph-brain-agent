# Contributing

## Setup

Requirements: Docker, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
docker compose up -d postgres          # PostgreSQL + pgvector on 127.0.0.1:5432
cd backend && uv sync                  # Python 3.12 is installed by uv
cd ../frontend && npm ci
```

Create a `.env` at the repository root for local runs (see the configuration table in the
[README](README.md)). Never commit it.

## Checks to run before opening a PR

CI runs the same commands (`.github/workflows/backend-ci.yml`, `frontend-ci.yml`).

```bash
# backend/
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run mypy tests
REQUIRE_INTEGRATION=1 uv run pytest -q   # integration tests need the PostgreSQL above

# frontend/
npm run lint
npm run format:check
npm test
VITE_API_URL=http://localhost:8000 npm run build
```

Without `REQUIRE_INTEGRATION=1` integration tests are skipped when PostgreSQL is unreachable;
set it to make them fail instead.

## Conventions

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/), as in the history:
  `feat(api): ...`, `fix: ...`, `docs: ...`, `build: ...`, `test: ...`. Keep each commit one
  reviewable unit, with its tests and docs.
- **Branches and PRs:** branch from `main` (e.g. `feat/...`) and open a PR. Keep PRs small
  enough to review (around 400 changed lines); split larger work into a chain.
- **Backend:** strict typing (mypy), ruff formatting, tests next to behaviour changes. Write the
  failing test first where a deterministic test is possible.
- **Frontend:** Feature-Sliced Design layers (`app`, `pages`, `widgets`, `features`,
  `entities`, `shared`); see [frontend/README.md](frontend/README.md).
- **Rules and tools:** a tool with an external side effect must be idempotent on the key from
  `current_idempotency_key()` and declare `retry_safe` honestly (see
  [docs/reliability.md](docs/reliability.md)).

## Review expectations

- The PR states what changed and why, and how it was verified.
- CI is green. Behaviour changes come with tests; user-facing or operational changes with docs.
- Claims in documentation must match the code. Reviewers check them against the implementation.
- Security-sensitive changes (auth, rules, approvals, the ledger) get extra scrutiny; report
  vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
