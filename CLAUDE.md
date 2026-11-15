# Revenue Assurance AI - project context

## What we are building
A revenue assurance system that reconciles 4M transactions/day across 10 billing and data
systems (S1-S10). Deterministic rules match ~98%; Amazon Bedrock agents on AgentCore
investigate the rest and propose adjustments that humans approve.
Design: docs/architecture/. Delivery playbooks: docs/asdlc/.

## Current phase
Update this line at every gate: **Phase 0 - Inception** (gate G0 on day 10).

## Rules for Claude in this repo
- Draft, never decide. End documents with "Open questions" and "Assumptions".
- Never invent numbers. Every figure cites a file in inputs/, spike/ or evals/, or is
  marked ASSUMPTION with an owner.
- No customer PII anywhere in the repo. Data under data/samples/ is masked.
- Models generate text only, never ledger numbers. Synthetic records come from evals/faults/.
- Work on one task from specs/<unit>/tasks.md at a time, on its own branch and worktree.
- Write or update the acceptance test first; it must fail before you implement.
- Never edit ADRs, agent cards, tool contracts or specs/*/design.md during construction;
  write problems to specs/<unit>/questions.md.
- Every Bedrock call goes through src/ra/llm (ra.llm.call) (routing, budgets, tracing).
- Agents never post money. Only propose_adjustment writes, to a pending state.
- Commit messages: "<task-id>: <summary>".

## Where things are
- Glossary: docs/steering/glossary.md
- Decisions: docs/steering/decisions.md
- Taxonomy: data/taxonomy.yaml
- Eval plan: docs/asdlc/05-evaluation.md, evals/
