# Fault-injection library

Deterministic functions that corrupt a clean, fully reconciled slice in known ways. Each has
parameters, a seed and a unit test. Models never generate ledger numbers.

| Fault | Label | Expected control |
| --- | --- | --- |
| drop_usage | RC03_missing_usage | C1/C2 |
| stale_tariff | RC02_price_book_mismatch | C5, C2 |
| dup_invoice_line | RC04_duplicate_billing | C2 |
| active_unbilled | RC05_provisioned_not_billed | C3 |
| billed_after_cancel | RC06_billed_not_provisioned | C3 |
| discount_wrong | RC07_discount_misapplied | C4 |
| fx_date_shift | RC09_fx_error | C2, C7 |
| partner_truncated | RC11_partner_variance | C8 |
| key_drift | RC12_identity_mismatch | All |
| gl_misposting | RC13_ledger_posting_error | C7 |
| late_cdc, tz_skew | RC10_timing_cutoff (noise) | Should self-heal |
