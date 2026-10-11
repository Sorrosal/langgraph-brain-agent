# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately through
[GitHub private vulnerability reporting](https://github.com/Sorrosal/langgraph-brain-agent/security/advisories/new)
on this repository. Include what you found, how to reproduce it and the affected version or
commit. You can expect an acknowledgement and a plan for a fix or mitigation; please allow time
to release it before disclosing.

Only the latest `main` (and the images published from it) is supported.

## Threat model summary

The agent acts on email, CRM and tasks on behalf of a team, driven by a language model whose
output is untrusted. The design assumes the model can be manipulated by the content it reads
(prompt injection) and limits what that can do.

| Area | What the code does |
| --- | --- |
| **Authentication** | JWT bearer tokens (HS256, issuer `brain-agent`, required `sub`/`exp`/`iat`/`iss`), lifetime `JWT_TTL_MINUTES`. The account is re-read on each request, so deleting a user revokes access at once. Passwords are argon2 hashes, minimum 10 characters; an unknown email costs the same time as a wrong password; registration answers `202` whether or not the email exists. In production `JWT_SECRET` (32+ characters) is mandatory and registration is off unless enabled. Event streams also accept `?access_token=` because `EventSource` cannot set headers; that is only on the stream route. |
| **Authorization** | Threads are owned by one user; other users get `404`. Rule edits require the `admin` role (the first registered user). |
| **Rate limiting** | In-process token buckets for login (per IP and email, and per IP), registration (per IP), messages and rule writes (per user), returning `429` with `Retry-After`. They are per process and rely on `FORWARDED_ALLOW_IPS` being set to the real reverse proxy, otherwise all clients look like the proxy. They do not replace limits at the edge. |
| **Tool approval** | Hard rules in `rules/*.yaml` can `block` or require human approval before a tool runs; tool metadata (`requires_approval`, `risk: high`) adds more. The strictest verdict wins, an edited call is re-checked, and blocked calls are never offered for approval. Rules fail closed. The default rules block CRM deletion and require approval for external or bulk email, large deals and task deletion. |
| **Side-effect safety** | A ledger prevents a replayed tool call from repeating its effect; unknown outcomes go to a human (see [docs/reliability.md](docs/reliability.md)). |
| **Secret handling** | Secrets (`JWT_SECRET`, API keys, SMTP/IMAP passwords) are read from the environment as `SecretStr` and never logged. Clients get stable error codes with a request id, never exception text; stored run errors are sanitized; exception messages are not recorded on trace spans. Do not commit `.env` files. |
| **Transport and headers** | The API sets `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` and `Cache-Control: no-store`; the frontend nginx adds a CSP, `Permissions-Policy` and the same headers on every location. TLS is not terminated by the compose stack: put it behind an HTTPS proxy. |
| **Outbound email** | The default `outbox` provider never leaves the system. `smtp` sends real mail, and plain-text SMTP (`SMTP_SECURITY=none`) is only accepted for localhost. |

Known limits: single-replica rate limiter and event broker, a single shared signing secret with
no key rotation overlap, and no per-tenant isolation of CRM, task and email data (it is shared by
all users of an installation). Memories are scoped per user plus a shared organisation namespace.
