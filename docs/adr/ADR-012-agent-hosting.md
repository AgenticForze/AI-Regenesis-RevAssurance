# ADR-012 Agent hosting
Status: Proposed

## Context
Investigations run 30 s-3 min, ~12K/day, up to ~75 concurrent in bill-run windows. Each case
needs session isolation, OTel traces joined to case_id, scoped tool credentials, and a version
per release for canary and rollback.

## Options
| Criterion | AgentCore Runtime | ECS Fargate | Lambda |
| --- | --- | --- | --- |
| Session isolation | Per session, built in | Build ourselves | Per invocation |
| Long-running steps | Supported | Supported | 15-minute cap |
| Tracing | Auto OTel to CloudWatch | ADOT sidecar | ADOT layer |
| Identity for tools | AgentCore Identity | Task role + custom | Role + custom |
| Versioning / canary | Runtime versions + endpoints | Task def + weighted ALB | Aliases |
| Ops effort | Low | Medium | Low |

## Decision
AgentCore Runtime for investigation agents and the analyst assistant; triage workers on
Lambda/ECS consuming SQS.

## Consequences
+ Isolation, tracing and identity without custom code.
- Depends on AgentCore quotas: request increases now; keep agent code framework-portable so
  ECS is a fallback. Reversal cost about 3 weeks.

## Verification
Week-5 spike: triage + one specialist on 100 gold cases; latency, cold start, trace completeness.
