# Brain Agent — frontend

React 19 + TypeScript (strict) SPA for the Brain Agent backend, organised with
[Feature-Sliced Design](https://feature-sliced.design/). Phase 6b covers authentication, the
conversation list and streaming chat with inline human approvals.

## Scripts

| Command                | What it does                                      |
| ---------------------- | ------------------------------------------------- |
| `npm run dev`          | Vite dev server                                   |
| `npm run build`        | Type-check (`tsc`) and production build           |
| `npm run preview`      | Serve the production build                        |
| `npm run lint`         | ESLint (type-aware, strict)                       |
| `npm run format:check` | Prettier check (`npm run format` writes)          |
| `npm test`             | Vitest + React Testing Library (`test:watch` too) |

## Environment

| Variable        | Default                                   | Meaning                           |
| --------------- | ----------------------------------------- | --------------------------------- |
| `VITE_API_URL`  | `http://localhost:8000` (dev server only) | Base URL of the backend API       |
| `VITE_APP_NAME` | `Brain Agent`                             | Name shown in the sidebar/sign-in |

Builds must set `VITE_API_URL` (e.g. `VITE_API_URL=https://api.example.com npm run build`); the
values are validated with Zod at start-up in `src/shared/config/env.ts`. The backend must allow
the app origin in its CORS settings (`cors_origins`).

## How it talks to the backend

- **HTTP** — one Axios instance (`shared/api/axios-instance.ts`) attaches
  `Authorization: Bearer <token>`. The backend issues access tokens only (no refresh): a `401`
  from any endpoint except `/auth/login` and `/auth/register` clears the session and redirects to
  `/login` through a handler registered by the app layer (`app/providers/api-bridge.ts`). There is
  no retry logic. Errors use the backend envelope `{"error": {"code", "message", "request_id"}}`
  and surface as `ApiError` (`status`, `code`, `message`, `requestId`, `retryAfter`).
- **Auth** — `POST /auth/login`, `POST /auth/register` (202, then automatic login), `GET /auth/me`.
  Token, user and expiry (`expires_in`) are persisted in the Zustand auth store; an expired token
  counts as logged out.
- **Streaming** — `useThreadStream` opens an `EventSource` on
  `/threads/{id}/events?access_token=…` (the browser cannot set headers on `EventSource`). On
  disconnect it reconnects with exponential backoff and resumes with `?after=<last event id>`;
  replayed events are ignored by id. The persisted thread (`GET /threads/{id}`) is re-fetched on
  `interrupt`, `run_completed`, `run_failed` and after a reconnect.
- **Approvals** — a pending `approval_required` interrupt is reviewed inline
  (`POST /threads/{id}/approvals`: approve / reject / edit / respond); `uncertain_execution` uses
  `POST /threads/{id}/uncertain` (confirm done / retry / skip). All actions need a decision.

## Structure

```
src/
├── app/        providers, router (AuthGuard, layouts), api bridge, global styles
├── pages/      auth, chat, approvals, inspector, brain, data, settings, not-found   (default exports, lazy)
├── widgets/    thread-list, chat-panel, header, sidebar, theme-toggle
├── features/   auth, send-message, thread-stream, review-approval, notifications,
│               manage-memory, edit-rules
├── entities/   user, thread, message, approval
└── shared/     api (axios, ApiError, contracts), config, hooks, lib, ui (shadcn)
```

Layers only import downwards, slices never import sibling slices, and every slice exposes a
barrel `index.ts`. Backend payload schemas shared by several entities (messages, interrupts,
decisions) live in `shared/api/contracts.ts` so entities do not import each other.
Slices use `ui/`, `model/` (stores, Zod schemas, types), `api/` (TanStack Query hooks) and `lib/`.

## Conventions

Zero `any`, no `@ts-ignore`, no non-null assertions; Zod schemas are the source of truth for
types; TanStack Query holds server state and Zustand client state; components are function
declarations with named exports (pages default-export for `lazy()`); imports use the `@/` alias.
