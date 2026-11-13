---
name: eval
description: Run an eval suite and compare with the main baseline.
---

Run `python -m evals.harness --suite <suite> --subset <subset>`. Report overall and per-slice
metrics, deltas vs baseline, cost per case, and the 5 worst cases with trace IDs.
