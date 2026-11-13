# Traceability

Any posted adjustment can be walked back to the source records, rules, retrieved documents,
model calls, versions and approver that produced it.

```mermaid
flowchart LR
  R[Source record<br/>record_uid] --> RUN[Recon run<br/>run_id] --> EX[Exception<br/>exception_id] --> CASE[Case flow<br/>case_id = trace root]
  CASE --> AG[Agent session<br/>session = case_id] --> MC[Model + tool calls<br/>request metadata] --> AP[Approval<br/>user, time] --> PO[Posting<br/>adjustment_id]
  PO --> PROV[(Decision provenance record<br/>S3 Object Lock)]
```

| ID | Format | Carried in |
| --- | --- | --- |
| record_uid | sha256(source_id + natural_key + version) | Iceberg rows, exception records |
| run_id | {control}-{period}-{engine_version}-{ts} | Recon results, exception event |
| exception_id | EX-{date}-{control}-{seq} | Event payload and attributes |
| case_id | CASE-{exception_group_id} | Step Functions input, AgentCore session, span baggage, Bedrock request metadata |
| trace_id | W3C, root at case creation | All spans |
| release | release manifest ID | Case record, span attribute |
| adjustment_id | ADJ-{case_id}-{n} | ERP/billing call (idempotency key) |

Provenance record example: docs/templates/provenance-record.json.
