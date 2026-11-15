---
name: investigate-discount
description: "Use when the discount on the invoice differs from the contract."
root_causes: [RC07_discount_misapplied]
tools: [get_contract, get_invoice_lines]
---

# investigate-discount

1. Read the agreed discount from the contract.
2. Read the discount applied on every invoice line.
3. Correction is gross times the difference between applied and agreed discount.
4. Positive correction means under-billing (`rebill`); negative means the customer is owed a `credit`.
