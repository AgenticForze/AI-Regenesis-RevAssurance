# Agents, tools and skills

## Agent tier (`src/ra/agents/runtime.py`)

| Step | Input | Output | Guard |
| --- | --- | --- | --- |
| Triage | One exception: control, amounts, features, record IDs | Root cause, action, confidence, route | Output validated against the taxonomy; an invalid answer becomes `RC99_other` with confidence 0 and goes to investigation |
| Investigate | Exception, triage, one skill's procedure, tool evidence | Finding: cause, action, signed amount, evidence IDs, narrative | Per-case token and call budget enforced in code |
| Verify | Finding + records | Pass or fail with named checks | No model: schema, taxonomy, action consistent with cause, evidence IDs exist, amount recomputed from records, sign matches action |

Routes after triage: `monitor` (timing or data-quality, expected to self-heal), `queue` (low
value, for an analyst), `investigate` (variance of 500 or more, or confidence below 0.80).

All model calls go through `ra.llm.call`, which checks the budget, opens a span with token
counts, records cost, and stores the call.

## Tools (`src/ra/tools`)

One registry serves the agents, `POST /api/tools/{name}` and the MCP server. Each call is
authorized, validated, traced, counted and audited.

| Tool | Reads | Permission |
| --- | --- | --- |
| `search_exceptions`, `get_exception` | Exceptions | `exceptions:read` |
| `get_usage`, `get_rated_usage` | S1, S2 | `tools:read` |
| `get_invoice_lines` | S3, S4 | `tools:read` |
| `get_contract`, `get_services` | S5, S6 | `tools:read` |
| `get_tariff` | S7 | `tools:read` |
| `get_payments`, `get_ledger_postings` | S8, S9 | `tools:read` |
| `query_partner_statement` | Partner agent over A2A | `a2a:call` |
| `get_before_after_report` | Reporting | `reports:read` |
| `propose_adjustment` | **Write**: creates a pending proposal | `adjustments:propose` |

Rules: read tools return the record IDs they used; results are capped at 200 rows; business
unit scope applies inside the tool; `propose_adjustment` is the only write tool and it cannot
post anything.

Add a tool: write a typed function in `src/ra/tools/builtin.py` with `@tool("name")`. It
appears in the API, the agent runtime and MCP at once.

## Skills (`skills/`)

A skill is a folder with a `SKILL.md`: front matter says which root causes it handles and which
tools it may use; the body is the investigation procedure. Only the selected skill's body is
loaded into a case, which keeps prompts small.

| Skill | Root causes | Tools |
| --- | --- | --- |
| investigate-usage-gap | RC03 | usage, rated usage, invoice lines |
| investigate-pricing | RC01, RC02 | rated usage, tariff |
| investigate-service-billing | RC05, RC06 | services, invoice lines, contract |
| investigate-discount | RC07 | contract, invoice lines |
| investigate-ledger | RC13 | invoice lines, ledger postings |
| investigate-partner-variance | RC11 | rated usage, partner statement (A2A) |
| investigate-duplicate | RC04 | invoice lines |
| general-investigation | everything else | contract, invoices, ledger, payments |

These are product skills. The Claude Code skills used to build the product are in
`.claude/skills/`.
