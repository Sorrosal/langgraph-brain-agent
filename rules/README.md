# Agent rules

This directory will hold the declarative rule set that governs the agent's behaviour
(planned for **phase 3 – brain: rules, memory and context**).

Rules are expressed as YAML files (`*.yaml`) and loaded at startup. Two kinds are planned:

- **Hard rules** — non-negotiable constraints the agent can never violate (for example,
  never send an email without human approval, never delete CRM records).
- **Soft rules** — preferences and heuristics that steer behaviour but may be weighed
  against context (for example, tone of voice, preferred working hours, escalation hints).

Nothing is loaded from this directory yet. The schema and loader will be introduced together
with the first rule files in phase 3.
