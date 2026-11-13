# Observability

```mermaid
flowchart TD
  W[Workload accounts: data jobs, agents, tools, workflows,<br/>model invocation logs, business events, CloudTrail, CUR] -->|OTLP, EMF, logs; trace_id joins case_id| C[Collected per account:<br/>CloudWatch Logs, spans, metrics, ADOT tail sampling]
  C -->|OAM links| O[Observability account:<br/>Grafana, Prometheus, Application Signals, SLOs, alarms, GenAI dashboard]
  O -->|alarms| A[Alerting and on-call]
  O -->|exports| L[Analytics lake: S3 + Athena<br/>cost per case, quality]
  A & L --> D[Dashboards: finance, recon ops, AI platform, quality]
  C -.audit-grade.-> LA[Log Archive: 7-year retention]
```

## LLM span attributes
`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`ra.cache_read_tokens`, `ra.cost_usd`, `ra.case_id`, `ra.agent`, `ra.step`, `ra.prompt_version`,
`ra.release`, `ra.guardrail_action`, `ra.confidence`, `ra.verifier_result`. Prompt content goes to
invocation logs (access-controlled), never to span attributes.

## SLOs
| SLO | Target |
| --- | --- |
| Feed freshness | 99% of feeds within SLA per day |
| Bill-run recon | Complete within 2 h of cycle close |
| Intraday detection | p95 < 5 min |
| Triage completion | 99% within 4 h of cycle close |
| Agent step latency | p95 < 20 s |
| Analyst assistant | p95 first token < 3 s; full answer < 8 s |
| Auto-close precision | >= 99% on weekly audit |
