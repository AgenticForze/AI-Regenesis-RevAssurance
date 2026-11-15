---
name: investigate-ledger
description: "Use when billed revenue and the general ledger disagree."
root_causes: [RC13_ledger_posting_error]
tools: [get_invoice_lines, get_ledger_postings]
---

# investigate-ledger

1. Total the invoice lines for the account.
2. Compare with the ledger posting for the same period.
3. If the posting sits in the next period for the full amount, this is timing, not an error: recommend `no_action`.
4. Otherwise recommend `journal_correction` for the difference. Billing is the source of truth for the amount.
