# Auditing

Every security-relevant or state-changing event is appended to the `audit` table.

| Field | Meaning |
| --- | --- |
| `seq`, `ts` | Order and UTC time |
| `actor`, `actor_type` | Who: user, service, agent |
| `action` | For example `auth:login`, `authz:adjustments:approve`, `tool:get_tariff`, `adjustment:approved`, `a2a:outbound`, `plugin:erp-journal` |
| `resource` | What it touched |
| `decision` | `allow`, `deny` or `info` |
| `detail` | Reason for a denial; before and after values for a change; fields shared with a partner |
| `trace_id` | Joins the event to its trace and logs |
| `prev_hash`, `hash` | SHA-256 chain |

What is recorded: sign-ins and failures, every denial, every allow on a write, every tool call
(by people, agents and MCP clients), investigations with who requested them, proposals and
decisions with before and after amounts, A2A calls in both directions, plug-in deliveries,
runs, and user administration.

## Tamper evidence

Each event's hash covers its content and the previous event's hash. Changing or deleting any
row breaks every hash after it. `GET /api/audit/verify` (or `ra verify-audit`) recomputes the
chain and reports the first bad sequence number. A test edits a row and checks that the break
is found.

A hash chain shows tampering; it does not stop someone with database access from rewriting
the whole chain. In production also ship events to write-once storage (S3 Object Lock in the
Log Archive account) and anchor the head hash there on a schedule.

## Answering an auditor

| Question | Where |
| --- | --- |
| Who approved this adjustment, and what changed? | `GET /api/audit?resource=<adjustment id>` |
| What did the agent look at? | `tool:*` events with the case's `trace_id`; the case's evidence IDs |
| Who was refused, and why? | `GET /api/audit?decision=deny` |
| What left the company? | `a2a:outbound` and `plugin:*` events |
