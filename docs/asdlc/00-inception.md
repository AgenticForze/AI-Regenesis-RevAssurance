# Phase 0 - Inception (weeks 1-2)

**Goal**: a signed intent, measured baseline, AI risk tier, feasibility result and business case. Gate **G0**.

```mermaid
flowchart LR
  subgraph Business track
    I[Interviews d2-3] --> IN[Intent d3] --> B[Baseline + KPIs d4-5] --> R[Risk tier + RACI d6-7] --> BC[Business case d8]
  end
  subgraph Technical track
    A[Data access d1-2] --> M[Masked extract d3] --> PM[Profile + match d4-5] --> E[20 breaks graded d6] --> SR[Spike report d7-8]
  end
  BC & SR --> DA[Devil's-advocate review d9] --> G0{G0 day 10}
  G0 --> GO[Go] & GC[Go with conditions] & NG[No-go]
```

## Claude Code
- Skills: `/intent`, `/baseline`, `/kpi-tree`, `/risk-classify`, `/raci`, `/business-case`
- Subagents: `data-profiler`, `break-explainer`, `devils-advocate`
- Hooks: PII guard before writes; change log after writes

## Feasibility spike success criteria
| Criterion | Pass if |
| --- | --- |
| Match quality | >= 90% of S2 records matched after key normalization |
| Real breaks | >= 5 confirmed by analysts |
| Explanation quality | >= 14 of 20 rated correct and useful |
| Groundedness | 0 invented numbers |
| Unit cost | Within the design's cost envelope |

## G0 checklist
- [ ] Intent approved; baseline spot-checked; KPI tree with targets and owners
- [ ] AI risk tier agreed; release-1 autonomy = recommend-only
- [ ] Data access committed for >= 3 sources; spike criteria met or conditions written
- [ ] Business case with three scenarios; devil's-advocate blockers closed
