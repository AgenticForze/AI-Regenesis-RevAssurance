---
name: investigate-usage-gap
description: "Use when usage was captured but not rated or not billed (missing usage)."
root_causes: [RC03_missing_usage]
tools: [get_usage, get_rated_usage, get_invoice_lines]
---

# investigate-usage-gap

1. Compare mediation quantity, rated quantity and billed gross per product.
2. Locate the hop where quantity or value drops: mediation to rating (C1) or rating to billing (C2).
3. The correction is the value of the missing usage at the current tariff, before discount for C1 and C2.
4. Recommend `rebill`. If the mediation feed is flagged incomplete, stop and reclassify as a data-quality break.

Never propose more than the gap the records support. Cite every record you used.
