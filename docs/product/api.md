# HTTP API

Interactive reference: `/api/docs` (OpenAPI at `/api/openapi.json`). Errors are
`{"detail": "...", "trace_id": "..."}`.

| Method and path | Permission | Purpose |
| --- | --- | --- |
| `POST /auth/token` | none | Built-in provider: `password` or `client_credentials` grant |
| `GET /auth/jwks.json` | none | Public signing key |
| `GET /auth/me` | signed in | Principal and effective permissions |
| `GET /healthz`, `/readyz`, `/metrics` | none | Liveness, readiness, Prometheus |
| `POST /api/runs` | `runs:execute` | Start a reconciliation run |
| `GET /api/runs` | `runs:read` | Run history |
| `GET /api/exceptions`, `/api/exceptions/{id}` | `exceptions:read` | List and detail, scoped by business unit |
| `POST /api/exceptions/{id}/investigate` | `cases:work` | Run the agent investigation |
| `POST /api/cases/{id}/adjustments` | `adjustments:propose` | Propose manually |
| `GET /api/adjustments` | `adjustments:read` | List proposals |
| `POST /api/adjustments/{id}/decision` | `adjustments:approve` + limit + four-eyes | Approve or reject |
| `POST /api/tools/{name}` | the tool's permission | Call a tool directly |
| `GET /api/reports/before-after[.csv|.html]` | `reports:read` | Before/after report |
| `GET /api/reports/triage-quality` | `audit:read` | Triage accuracy against labels |
| `GET /api/audit`, `/api/audit/verify` | `audit:read`, `audit:verify` | Search and verify the audit chain |
| `GET /api/traces`, `/api/traces/{id}`, `/api/costs` | `obs:read` | Recent traces, model usage |
| `GET /api/plugins`, `POST /api/plugins/dispatch` | `plugins:read`, `plugins:dispatch` | Plug-ins and outbox |
| `GET/POST /api/admin/users` | `admin:users` (human only) | Built-in provider users |
| `GET /.well-known/agent-card.json` | none | A2A agent card |
| `POST /a2a` | `a2a:invoke` + skill permission | A2A JSON-RPC |
| `POST /mcp/` | `mcp:invoke` + tool permission | MCP streamable HTTP |
