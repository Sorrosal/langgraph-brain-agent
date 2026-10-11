export const QUICKSTART_CODE = `# 1. Database (PostgreSQL + pgvector)
docker compose up -d postgres

# 2. Backend
cd backend
uv sync && uv run uvicorn brain_agent.api.app:create_app --factory

# 3. Frontend
cd frontend
npm ci && npm run dev`;
