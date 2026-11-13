# Sequence diagrams

## One exception group, end to end

```mermaid
sequenceDiagram
  participant DP as Data platform
  participant EB as Event bus
  participant CF as Case flow (Step Functions)
  participant AG as Agents (AgentCore)
  participant GW as Gateway tools
  participant BR as Bedrock (models, KB)
  participant CS as Case store
  participant AN as Analyst
  DP->>EB: exception group (group_key)
  EB->>CF: start case (case_id, traceparent)
  CF->>CS: create case, provenance v0
  CF->>AG: invoke triage (session = case_id)
  AG->>BR: triage (cached prefix + group)
  BR-->>AG: root cause, confidence 0.62
  AG->>AG: confidence below 0.7: cascade, supervisor plans
  AG->>GW: get_records, get_tariff(as_of)
  GW->>DP: read gold and silver (read-only role)
  DP-->>GW: rows + record_uids
  GW-->>AG: typed evidence
  AG->>BR: KB retrieve + rerank; root-cause call
  BR-->>AG: proposal + chunk citations
  AG->>GW: compute_impact, propose_adjustment
  GW->>CS: pending proposal (idempotency key)
  AG->>BR: verifier: code checks + judge
  BR-->>AG: pass
  AG-->>CF: proposal_id, verified
  CF->>AN: approval task (task token)
  AN->>CF: approve (user, timestamp)
  CF->>CS: lock provenance; trigger posting
```

## Bill run with batch triage

```mermaid
sequenceDiagram
  participant SC as Scheduler
  participant BO as Batch orchestration
  participant EMR as Recon jobs
  participant LK as Lakehouse
  participant PB as Publisher
  participant BD as Batch builder
  participant BK as Bedrock batch
  participant CF as Case flow
  SC->>BO: cycle close (period)
  BO->>EMR: run controls C1-C9
  EMR->>LK: write results + exceptions
  EMR-->>BO: run_ids, break counts
  BO->>PB: group, prioritize, publish
  PB->>CF: high priority: on-demand triage
  BO->>BD: build JSONL for remaining groups
  BD->>BK: CreateModelInvocationJob
  BK-->>BD: output JSONL in S3
  BD->>CF: triage results by case_id
```

## Analyst assistant question

```mermaid
sequenceDiagram
  participant AN as Analyst
  participant UI as Web UI
  participant API as API
  participant AS as Assistant (AgentCore)
  participant GR as Guardrails
  participant KB as Knowledge bases
  participant RS as Redshift (curated views)
  participant M as Model
  AN->>UI: why did S4 under-bill roaming in October?
  UI->>API: POST /ask (JWT)
  API->>AS: invoke as analyst (entitlements)
  AS->>GR: input guardrail
  GR-->>AS: pass
  AS->>RS: text-to-SQL (row-level security)
  RS-->>AS: rows + generated SQL
  AS->>KB: retrieve contracts, tariffs (as_of)
  KB-->>AS: chunks + versions
  AS->>M: answer with citations (stream)
  AS->>GR: output guardrail
  AS-->>UI: answer + SQL + sources
```
