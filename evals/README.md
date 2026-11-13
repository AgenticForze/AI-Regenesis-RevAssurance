# Evals

| Suite | Dataset | Thresholds |
| --- | --- | --- |
| recon | Fault library scenarios | precision >= 99.5%, recall >= 99% |
| retrieval | Retrieval gold set | recall@8 >= 0.90 |
| triage | Regression set (400) | macro-F1 >= 0.85, ECE < 0.05 |
| investigation | Hard-case gold slice | correct >= 0.90, impact error 0 |
| safety | Adversarial set | 100% blocked |

Datasets live in S3; this repo holds manifests only (datasets/manifest.example.json).
The held-out set is opened only by `make eval-final` from the verification workspace.
