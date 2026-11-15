---
name: investigate-service-billing
description: "Use when a provisioned service has no charge, or a ceased service is still charged."
root_causes: [RC05_provisioned_not_billed, RC06_billed_not_provisioned]
tools: [get_services, get_invoice_lines, get_contract]
---

# investigate-service-billing

1. List the services and their status, then the recurring invoice lines.
2. Active with no recurring line: under-billing. Correction is the plan charge less the contract discount. Recommend `rebill`.
3. Ceased with a recurring line: over-billing. Correction is a credit of the billed amount. Recommend `credit`.
4. Check the cease date; charges before it are valid.
