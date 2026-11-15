# Observability

Three signals, joined by trace ID. Every HTTP response carries `X-Trace-Id`; every log line
and audit event carries the same ID.

## Traces (OpenTelemetry)

```
POST /api/runs
└─ recon.run
   ├─ recon.load
   ├─ recon.controls
   ├─ recon.triage
   │  └─ agent.triage → llm.triage            (tokens, cost)
   └─ case.investigate
      └─ agent.investigate
         ├─ tool.get_rated_usage
         ├─ tool.query_partner_statement → a2a.send
         ├─ llm.investigate                    (tokens, cost)
         └─ tool.propose_adjustment
   plugin.deliver
```

Model spans use the GenAI semantic-convention attribute names (`gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`). Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export to a collector.
The console's Observability tab shows the last 2,000 spans from memory, so a trace can be
inspected with no backend.

## Metrics (Prometheus, `/metrics`)

| Metric | Answers |
| --- | --- |
| `ra_http_requests_total`, `ra_http_request_seconds` | Is the API healthy? |
| `ra_auth_events_total`, `ra_authz_decisions_total` | Is someone probing, or is a role mapping broken? |
| `ra_records_reconciled_total`, `ra_exceptions_total` | Volume and break rate by control and severity |
| `ra_triage_total`, `ra_investigations_total` | Mix of causes and routes; verifier pass rate |
| `ra_tool_calls_total`, `ra_tool_seconds` | Tool errors and latency |
| `ra_llm_tokens_total`, `ra_llm_cost_usd_total` | Token use and spend per step |
| `ra_adjustments_total`, `ra_recovered_amount_total` | Decisions and value recovered |
| `ra_plugin_deliveries_total` | External deliveries: delivered, failed, dead |
| `ra_a2a_calls_total` | Agent-to-agent calls by direction and outcome |
| `ra_open_exceptions`, `ra_pending_approvals` | Backlog |

Alert rules are in `deploy/observability/alerts.yml`: plug-in failures, denial and login
spikes, verifier fail rate above 20%, approval backlog, daily model spend.

## Logs

JSON to stdout, one object per line, with `trace_id`. No payload data is logged.

## In AWS

Swap the collector's exporter for X-Ray and CloudWatch, scrape `/metrics` with the managed
Prometheus collector, and keep the cross-account layout in
`docs/architecture/observability.md`.
