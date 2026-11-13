# Agent graph

```mermaid
flowchart TD
  EG[Exception group from SQS] --> TR[Triage - small model<br/>cascade to mid if confidence below 0.7]
  TR --> D1{Confident, low value,<br/>known pattern?}
  D1 -->|yes| AC[Auto-close candidate<br/>R3 only, else approval]
  D1 -->|no| SUP[Supervisor - mid model<br/>budget 12 calls, 60K tokens, 3 min]
  SUP --> LED[Ledger evidence<br/>get_records, get_account_timeline]
  SUP --> PRC[Pricing and contract<br/>get_tariff as_of, KBs]
  SUP --> IDN[Identity<br/>resolve_identity]
  SUP --> PAR[Partner settlement<br/>get_tap_summary]
  LED & PRC & IDN & PAR --> RC[Root-cause and impact<br/>compute_impact, propose_adjustment pending]
  RC --> VER[Verifier<br/>code checks, then judge]
  VER --> D2{Verified?}
  D2 -->|fail, max 2 re-plans| SUP
  D2 -->|pass| HITL[Approval queue - human in the loop]
  AC -.-> HITL
```

| Agent | Tier | Tools (allow-list) | Output |
| --- | --- | --- | --- |
| Triage | Small | search_cases, get_tariff | root cause, action, confidence, missing info |
| Supervisor | Mid | dispatch, get_budget | plan of 2-5 steps |
| Ledger evidence | Small/Mid | get_records, get_account_timeline, compare_rated_vs_billed | evidence table |
| Pricing and contract | Mid | get_tariff(as_of), search_contracts | applicable price/discount + citations |
| Identity | Small | resolve_identity, get_crm_account | mapping verdict |
| Partner settlement | Mid | get_tap_summary, search_contracts | variance explanation |
| Root-cause and impact | Mid (frontier top 1%) | compute_impact, propose_adjustment | root cause, action, explanation |
| Verifier | Mid, other prompt/model | get_records, compute_impact | pass/fail + reasons |

Design cards: src/ra/agents/cards/. Tool contracts: src/ra/tools/specs/.
