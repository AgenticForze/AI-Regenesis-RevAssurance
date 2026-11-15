---
name: investigate-partner-variance
description: "Use when a partner settlement statement differs from our rated usage. Calls the partner agent over A2A."
root_causes: [RC11_partner_variance]
tools: [get_rated_usage, query_partner_statement]
---

# investigate-partner-variance

1. Total our rated usage for the partner account.
2. Ask the partner's settlement agent for the detail behind its statement (days reported, missing days).
3. If days are missing from the partner statement, the dispute amount is our rated total minus the statement amount.
4. Recommend `dispute_partner` and list the missing days so the partner can re-run its statement.

Share only the account, period and totals with the partner agent. Never send customer-level records.
