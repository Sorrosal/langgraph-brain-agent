# Rules

Rules are the agent's declarative guard rails: soft **guidelines** that shape the system prompt
and **hard rules** that are enforced in code before any tool runs. The format, the argument
operators and the reload behaviour are documented next to the rule files, in
[`rules/README.md`](../rules/README.md); the shipped example is
[`rules/default.yaml`](../rules/default.yaml).

How rules fit into the system:

- **Fail closed:** the service does not start without valid rules that define at least one hard
  rule, and an invalid edit keeps the last good set.
- **Evaluation order** (rules, then tool metadata, strictest verdict wins) is described in
  [architecture.md](architecture.md#rules-evaluation-order).
- **Editing:** admins can read rules with `GET /rules` and replace a file with
  `PUT /rules/{filename}` (`^[a-z0-9-]+\.yaml$`, rate limited per user). The whole resulting
  rule set is validated before anything is written, and the file is swapped atomically.
- **Audit:** every blocked call and every human decision is appended to the thread's
  `approvals` state.
