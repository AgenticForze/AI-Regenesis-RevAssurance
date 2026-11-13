# Phase 7 - Operations and continuous improvement (week 28+)

```mermaid
flowchart LR
  S[Production signals] --> O[Ops agents + reviews] --> B[Improvement backlog] --> BO[Bolts] --> EG[Eval gate] --> RL[Release] --> S
```

## Rhythm
| Cadence | Activity |
| --- | --- |
| Daily | AgentOps digest (ops-analyst) and 20-minute review |
| Weekly | Auto-close audit; override mining; backlog grooming |
| Monthly | Drift review; cost review; value report |
| Quarterly | Gold-set refresh; model upgrade in shadow; model risk review; DR test; access review |

## Drift response
```mermaid
flowchart TD
  A[Drift alert] --> D1{Source data changed?}
  D1 -->|yes| DI[Data incident: quarantine feed]
  D1 -->|no| D2{Business change?}
  D2 -->|yes| RU[Reference update: KB, catalog, controls]
  D2 -->|no| D3{Model behaviour changed?}
  D3 -->|yes| MI[Model incident: class to R2, pin last good version]
  D3 -->|no| ML[Monitor and label]
  DI & RU & MI & ML --> C[Close with a cause]
```

## Model and prompt upgrades
New version -> offline eval (every slice equal or better) -> shadow 5% for 7 days -> agrees with
analysts -> canary 10/50/100% via AppConfig -> pin and record (manifest, validation pack, ADR).

## Ongoing governance (quarterly)
- [ ] Autonomy register current; weekly audits >= 99% precision per class
- [ ] Gold set refreshed with a newest-quarter held-out slice
- [ ] Drift alerts closed with causes; DR test passed; access review done
- [ ] Cost per case within budget; value report signed by finance
