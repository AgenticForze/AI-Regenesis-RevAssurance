# Anti-patterns and lessons

Review the rows relevant to the current phase at every gate.

| Area | Anti-pattern | Where it fails | Fix | Next time |
| --- | --- | --- | --- | --- |
| Strategy | LLM on every transaction | All 4M tx sent to a model | Rules first; AI on exceptions | KPI: calls per 1,000 transactions |
| Strategy | Autonomy before evidence | Auto-close in release 1 | Back to recommend; audit closures | Autonomy ladder as a G0 condition |
| Strategy | No baseline | Value cannot be proven | Rebuild from history | Baseline is a G0 blocker |
| Data | Identity as an afterthought | Floods of false breaks | Identity map; suppress unresolved | Gate on >= 98% coverage |
| Data | No data contracts | Silent breakage after a source release | Quarantine; sign contract | Contracts at G2; drift-watcher |
| Data | Single labeler | Biased gold set | Double-label, kappa, adjudicate | Budget 3 labelers in Phase 0 |
| Data | Pre-labels rubber-stamped | Circular evals | Re-label blind sample | 20% blind; track anchoring gap |
| Data | Tuning on the test set | Inflated final scores | New held-out slice | One command, one person, logged |
| Data | Stale documents | Wrong tariff in explanations | Effective dates; as_of filters | Mandatory metadata at ingestion |
| Agents | One giant agent | Unpredictable tools, hard evals | Supervisor + specialists + verifier | Agent graph and cards first |
| Agents | Model computes money | Arithmetic errors | Deterministic compute_impact | Number-diff check in CI |
| Agents | Write tools for investigators | Real postings from injection | Pending proposals only | Read-only by default |
| Agents | Unbounded loops | Runaway cost | Budgets, re-plan limit | Budgets in every card |
| Agents | Memory dumping ground | Bloat, poisoning | Summarize, prune, tag untrusted | Memory scopes and TTLs in Phase 3 |
| Agents | Self-judging model | Inflated scores | Different judge, calibrated | Judge independence in eval plan |
| Delivery | Vibe coding without specs | Drift and rework | Spec, then regenerate | Specs are a G3 deliverable |
| Delivery | Endless bolts | Wasted spend | Stop after 3 fails or 2 days | Track cycle time and rework |
| Delivery | Too many agents per human | Rubber-stamp reviews | 2-3 per reviewer | Watch review wait and escapes |
| Delivery | Agents with prod credentials | Accidental prod changes | Revoke; pipelines only | Deny in settings and SCPs |
| Release | Average-only metrics | Costly slice regresses | Gate per slice | Critical slices in eval plan |
| Release | Big-bang go-live | Unclear failure cause | Roll back to rules; stage releases | Three-release ladder |
| Release | No kill switch | Slow incident response | AppConfig flags | Test switches before R1 |
| Ops | Ignoring overrides | Repeated mistakes | Mine weekly | Show analysts the impact |
| Ops | Blaming the model for drift | Wrong fixes | Drift flowchart | Source, business, then model |
| Ops | Unpinned model versions | Overnight behaviour change | Pin; shadow + canary | Validator forbids aliases |

## How to improve next time
1. Run a pre-mortem at G0 and map each answer to a row with an owner.
2. Spend 10 minutes per gate on the relevant rows.
3. Watch leading indicators: identity coverage, kappa, calls per 1,000 tx, override rate, bolt cycle time, cost per case.
4. Add new rows after each gate and incident.
5. Reuse this repo's templates, skills, subagents, fault library, eval harness and runbooks.
