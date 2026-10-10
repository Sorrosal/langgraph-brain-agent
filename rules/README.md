# Agent rules

Declarative rules that govern the agent. Every `*.yaml` file in this directory is loaded
(sorted by filename) and merged into one rule set; the directory is configurable with the
`RULES_DIR` setting. The shipped example is [`default.yaml`](default.yaml).

- **Guidelines** are soft: they are written into the system prompt and the model may weigh them.
- **Hard rules** are enforced in code before any tool runs. The model cannot talk its way past them.

Edits are picked up without a restart. If an edit is invalid, the last good rules stay active
and the error is logged.

## Format

```yaml
version: 1                 # required, must be 1
persona: |                 # optional; at most one file may define it
  You are an operations assistant for ...
guidelines:
  - id: tone
    text: Be concise and professional.
    priority: 10           # higher first; default 0; ties are ordered by id
hard_rules:
  - id: external-email-needs-approval
    description: Emails to external recipients require human approval.   # shown to the model
    when:
      tool: send_email     # exact tool name or glob (fnmatch, e.g. crm_*); required
      args:                # optional; every condition must hold (AND)
        to: { not_matches: '@acme[.]com$' }
    action: require_approval   # require_approval | block
    risk: high                 # low | medium | high; default high
    reason: External recipients need a human check.   # default: description
```

Ids must be unique across all files (guidelines and hard rules share one namespace). A
duplicate id, an invalid regex or a schema error makes loading fail, naming the file (and the
rule id for regexes).

## Actions

- `require_approval` pauses the run until a human approves, edits, rejects or answers.
- `block` refuses the call: it is never executed and never offered for approval. The model
  receives an error `Blocked by rule <ids>: <reason>` and the decision is audited as `blocked`.

When several rules match, `block` wins; otherwise all matching rule ids are listed in the reason
and the highest risk is used. Tool metadata approvals (`requires_approval`, `risk: high`) still
apply; the strictest verdict wins.

## Argument conditions

Each key under `args` is an argument name, or a dotted path into nested data
(`customer.tier`; a number indexes a list: `to.5` is the sixth recipient). Each value is a map of
one or more operators, all of which must hold:

| Operator | Holds when the value ... |
| --- | --- |
| `equals` / `not_equals` | is / is not equal to the given value |
| `in` / `not_in` | is / is not one of the given list |
| `matches` / `not_matches` | does / does not match the regex (`re.search`, so anchor with `^`/`$`) |
| `gt`, `gte`, `lt`, `lte` | compares to a number (numeric strings are accepted; booleans and other text never match) |
| `exists` | is present (`true`) or absent (`false`); `null` counts as present |

**Missing arguments.** Only `exists: false` and the negative operators (`not_equals`, `not_in`,
`not_matches`) can match an argument that is absent; every other operator does not match it.

**List values.** An operator is satisfied if *any element* of the list satisfies it
(`not_matches` on `to: [a@acme.com, b@gmail.com]` matches because `b@gmail.com` does). An empty
list matches nothing. `exists` applies to the list itself.
