# Reporting: before and after

Three views of "before and after", all from `src/ra/reporting.py`.

| View | Before | After | Where |
| --- | --- | --- | --- |
| Process | The manual, sample-based review | This product on the same run | `GET /api/reports/before-after` (`.csv`, `.html`), `ra report`, console Overview |
| Adjustment | Billed amount before the correction | Billed amount after it | The `adjustments` list in the same report; console Approvals |
| Change | Value before a state change | Value after it | `detail.before` and `detail.after` on audit events |

## The process comparison

Both sides are computed over the same run, so the difference is the process, not the data.

| Measure | Before | After |
| --- | --- | --- |
| Accounts checked | `sample_rate` | 100% |
| Controls run | `controls_covered` | 9 |
| Exceptions found | Breaks in sampled accounts on covered controls, times `detection_rate` | All non-monitor exceptions |
| Leakage identified | Value of the above | Value of all exceptions |
| Leakage recovered | Assumed equal to identified | Approved adjustments only |
| Time | `days_to_resolve` | Measured proposal-to-decision time |
| Cost | Analyst hours per case | Measured model cost per exception |

**The before-side is a model, not a measurement.** Its parameters are placeholders in
`config/baseline.yaml`. Replace them with the baseline you measure in Phase 0, and keep the
caveat line on any report that still uses defaults. The report prints the assumptions it used.

Pending adjustments are shown separately and never counted as recovered.

## Triage quality

`GET /api/reports/triage-quality` scores triage against ground truth and lists the most
common confusions. It is only meaningful where labels exist: synthetic data, or a labeled gold
set loaded into the `truth` column.
