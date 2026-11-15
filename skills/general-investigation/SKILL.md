---
name: general-investigation
description: "Fallback when no specific skill matches the root cause."
root_causes: [RC99_other]
tools: [get_contract, get_invoice_lines, get_ledger_postings, get_payments]
---

# general-investigation

1. Gather contract, invoice, ledger and payment records.
2. State what is known, what is missing, and which control raised the break.
3. Recommend `escalate` unless the records clearly support a specific correction.
