# Revenue Assurance AI on Amazon Bedrock

Reconcile **4 million transactions a day** across **10 billing and data systems**, find revenue leakage, and explain every break with evidence, using a deterministic reconciliation engine plus a multi-agent AI tier on Amazon Bedrock and AgentCore. The project is delivered with an **agentic SDLC** in Claude Code.

> Design principle: **rules first, AI for exceptions.** About 98% of records are matched by deterministic rules. Bedrock agents investigate only the breaks, propose fixes, and a human approves every adjustment until the evidence earns more autonomy.

## At a glance

| | |
| --- | --- |
| Volume | 4M business transactions/day, ~16M source records/day, 5x bill-run peaks |
| Sources | S1 mediation, S2 rating, S3/S4 billing, S5 CRM, S6 orders, S7 catalog, S8 payments, S9 ERP, S10 partner settlement |
| Controls | C1-C9 across the revenue chain (usage, rating, billing, provisioning, contracts, cash, ledger, partners, migration) |
| AI tier | Triage, supervisor, 4 specialists, root-cause, verifier on AgentCore Runtime; Bedrock Knowledge Bases; Guardrails |
| Delivery | 8 aSDLC phases, 7 gates, ~28 weeks to production |
| Website | [`website/index.html`](website/index.html), deployed by GitHub Pages |

## Architecture

```mermaid
flowchart TD
  S[10 source systems] --> N[Network account: DX, TGW, firewall]
  N --> D[Data Platform: MSK, DMS, Glue, EMR, Flink, Iceberg]
  D -->|~98% matched by rules| G[(Gold: recon results)]
  D -->|exceptions only| AI[AI Platform: Bedrock + AgentCore]
  AI -->|pending proposals| C[Case Mgmt: Step Functions, DynamoDB, UI]
  C -->|human approval| P[Posting to billing / ERP]
  D & AI & C -.telemetry.-> O[Observability + Log Archive]
```

```mermaid
flowchart TD
  E[Exception group] --> T[Triage agent - small model]
  T -->|confident, low value| A[Auto-close candidate - R3 only]
  T -->|otherwise| SUP[Supervisor - mid model]
  SUP --> L[Ledger] & PR[Pricing + contract] & ID[Identity] & PA[Partner]
  L & PR & ID & PA --> RC[Root-cause + impact]
  RC --> V{Verifier}
  V -->|fail, max 2| SUP
  V -->|pass| H[Approval queue - human in the loop]
```

Full design: [`docs/architecture/`](docs/architecture/).

## The agentic SDLC

| Phase | Weeks | AI drafts | People decide | Gate |
| --- | --- | --- | --- | --- |
| [0 Inception](docs/asdlc/00-inception.md) | 1-2 | Intent, KPI tree, risk tier, spike | Scope, autonomy ceiling, funding | G0 |
| [1 Discovery](docs/asdlc/01-discovery.md) | 2-5 | Stories, controls, taxonomy | Accept in mob sessions | G1 |
| [2 Data readiness](docs/asdlc/02-data-readiness.md) | 3-10 | Profiles, contracts, pre-labels | Confirm labels, sign contracts | G2 |
| [3 Architecture](docs/asdlc/03-architecture.md) | 4-7 | ADR options, agent cards, specs | Accept ADRs, eval thresholds | G3 |
| [4 Construction](docs/asdlc/04-construction.md) | 6-24 | Code in bolts | Review and merge | G4 |
| [5 Evaluation](docs/asdlc/05-evaluation.md) | 8-26 | Evals, red-team cases | Sign validation pack | G5 |
| [6 Release](docs/asdlc/06-release.md) | 24-32 | Notes, SOPs, digests | Raise autonomy per class | G6 |
| [7 Operations](docs/asdlc/07-operations.md) | 28+ | Drift, audits, cost reports | Improve, upgrade, audit | Quarterly |

Read [`docs/asdlc/anti-patterns.md`](docs/asdlc/anti-patterns.md) at every gate.

## Repository map

```text
.
├── CLAUDE.md                 # project context for Claude Code (phase, rules)
├── .claude/                  # settings, hooks, subagents, skills
├── .github/                  # CI, eval gate, Pages deploy, templates, CODEOWNERS
├── docs/                     # architecture, aSDLC playbooks, ADRs, steering, templates
├── specs/                    # one spec folder per unit of work (U1-U7)
├── features/                 # Gherkin acceptance scenarios
├── data/                     # taxonomy, data contracts, control specs, mappings
├── src/ra/                   # Python package: shared libs, agents, tools, recon
├── prompts/                  # prompt templates (synced to Bedrock Prompt Management)
├── config/                   # routing table and HITL thresholds per environment
├── evals/                    # eval harness, suites, dataset manifests, fault library
├── infra/                    # IaC (CDK or Terraform) by account and environment
├── tests/                    # unit tests
└── website/                  # project website (GitHub Pages)
```

## Getting started

```bash
git clone https://github.com/your-org/revenue-assurance-ai.git
cd revenue-assurance-ai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make test          # unit tests, including the Claude Code hooks
make eval-quick    # placeholder eval suite (wire to Bedrock in Phase 4)
claude             # start Claude Code with the project context
```

Claude Code picks up `CLAUDE.md`, `.claude/settings.json`, the subagents in `.claude/agents/` and the skills in `.claude/skills/` (`/intent`, `/bolt`, `/pr`, `/eval`, `/adr`, ...).

## Status

This repository is a **reference scaffold**: documents, specs, configuration and code skeletons ready for a team to start Phase 0. Figures such as volumes, thresholds and costs are planning assumptions to replace with your own baseline.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Choose and add a `LICENSE` before publishing the repository.
