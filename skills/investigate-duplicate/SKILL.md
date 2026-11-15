---
name: investigate-duplicate
description: "Use when the same charge appears more than once on an invoice."
root_causes: [RC04_duplicate_billing]
tools: [get_invoice_lines]
---

# investigate-duplicate

1. Group invoice lines by service, product, line type and invoice.
2. Any group with more than one line is a duplicate.
3. Correction is a `credit` for every copy after the first. The amount is negative: we owe the customer.
