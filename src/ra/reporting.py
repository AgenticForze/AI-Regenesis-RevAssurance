"""Reporting: before/after comparison, run summary and triage quality.

"Before" is the manual, sample-based process the product replaces. Its parameters live in
config/baseline.yaml and should be replaced with your own measured baseline (Phase 0 of the
delivery plan). "After" is measured from this product's own tables. Both sides are computed
over the same run, so the comparison isolates the process, not the data.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import yaml

from ra import db
from ra.recon.controls import CONTROLS
from ra.settings import get_settings

DEFAULT_BASELINE = {"sample_rate": 0.08, "detection_rate": 0.70, "days_to_resolve": 21,
                    "analyst_hours_per_case": 2.5, "analyst_hourly_cost": 65.0,
                    "controls_covered": ["C2", "C7"]}


def baseline_params() -> dict[str, Any]:
    path = get_settings().baseline_config
    cfg = yaml.safe_load(path.read_text()) if path.exists() else {}
    return {**DEFAULT_BASELINE, **(cfg or {})}


def _sampled(account_id: str, rate: float) -> bool:
    """Deterministic stand-in for the manual sample: a fixed share of accounts by hash."""
    return int(hashlib.sha256(account_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < rate


def before_after(run_id: str) -> dict[str, Any]:
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise ValueError(f"unknown run {run_id}")
    base = baseline_params()
    excs = db.query("SELECT * FROM exceptions WHERE run_id=?", (run_id,))
    real = [e for e in excs if e["status"] != "monitor"]
    adjs = db.query("SELECT a.* FROM adjustments a JOIN exceptions e ON e.id=a.exception_id "
                    "WHERE e.run_id=?", (run_id,))
    approved = [a for a in adjs if a["status"] == "approved"]
    llm = db.one("SELECT COALESCE(SUM(cost_usd),0) c, COUNT(*) n FROM llm_calls WHERE case_ref IN "
                 "(SELECT id FROM exceptions WHERE run_id=? UNION SELECT c.id FROM cases c "
                 "JOIN exceptions e ON e.id=c.exception_id WHERE e.run_id=?)", (run_id, run_id))

    seen_before = [e for e in real if e["control"] in base["controls_covered"]
                   and _sampled(e["account_id"], base["sample_rate"])]
    before_value = sum(abs(e["variance"]) for e in seen_before) * base["detection_rate"]
    before_cases = round(len(seen_before) * base["detection_rate"])
    after_value = sum(abs(e["variance"]) for e in real)
    hours = []
    for a in approved:
        t0, t1 = datetime.fromisoformat(a["created"]), datetime.fromisoformat(a["decided"])
        hours.append((t1 - t0).total_seconds() / 3600)

    before = {
        "accounts_checked_pct": round(base["sample_rate"] * 100, 1),
        "controls_run": len(base["controls_covered"]),
        "exceptions_found": before_cases,
        "leakage_identified": round(before_value, 2),
        "leakage_recovered": round(before_value, 2),
        "median_days_to_resolve": base["days_to_resolve"],
        "cost_per_case": round(base["analyst_hours_per_case"] * base["analyst_hourly_cost"], 2),
        "evidence_trail": "spreadsheets and email",
    }
    after = {
        "accounts_checked_pct": 100.0,
        "controls_run": len(CONTROLS),
        "exceptions_found": len(real),
        "leakage_identified": round(after_value, 2),
        "leakage_recovered": round(sum(abs(a["amount"]) for a in approved), 2),
        "pending_approval": round(sum(abs(a["amount"]) for a in adjs
                                      if a["status"] == "pending"), 2),
        "median_hours_to_decision": round(sorted(hours)[len(hours) // 2], 3) if hours else None,
        "model_cost_usd": round(llm["c"], 4),
        "model_cost_per_exception": round(llm["c"] / max(len(excs), 1), 5),
        "evidence_trail": "record IDs, tool calls and hash-chained audit events",
    }
    by_control: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "value": 0.0})
    for e in real:
        by_control[e["control"]]["count"] += 1
        by_control[e["control"]]["value"] += abs(e["variance"])
    return {
        "run_id": run_id, "period": run["period"], "generated": db.now(),
        "data": run["stats"].get("data"), "match_rate": run["stats"].get("match_rate"),
        "before": before, "after": after,
        "uplift": {"additional_leakage_identified": round(after_value - before_value, 2),
                   "coverage_points": round(100 - base["sample_rate"] * 100, 1)},
        "by_control": {c: {"name": CONTROLS[c], "count": int(v["count"]),
                           "value": round(v["value"], 2)} for c, v in sorted(by_control.items())},
        "adjustments": [{"id": a["id"], "action": a["action"], "status": a["status"],
                         "before_amount": a["before_amount"], "after_amount": a["after_amount"],
                         "amount": a["amount"], "decided_by": a["decided_by"]} for a in adjs],
        "baseline_assumptions": base,
        "caveat": "Before-figures are modelled from config/baseline.yaml, not measured. "
                  "Replace them with your own baseline before using this report externally.",
    }


def triage_quality(run_id: str) -> dict[str, Any]:
    """Score triage against ground truth. Only meaningful on synthetic or labeled data."""
    rows = [e for e in db.query("SELECT root_cause, truth, control FROM exceptions WHERE run_id=?",
                                (run_id,)) if e["truth"]]
    hits = sum(1 for e in rows if e["root_cause"] == e["truth"][1])
    confusion = Counter((e["truth"][1], e["root_cause"]) for e in rows
                        if e["root_cause"] != e["truth"][1])
    return {"labeled": len(rows), "correct": hits,
            "accuracy": round(hits / len(rows), 4) if rows else None,
            "confusions": [{"truth": t, "predicted": p, "count": n}
                           for (t, p), n in confusion.most_common(10)]}


def to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric", "before", "after"])
    for k in sorted(set(report["before"]) | set(report["after"])):
        w.writerow([k, report["before"].get(k, ""), report["after"].get(k, "")])
    w.writerow([])
    w.writerow(["adjustment", "action", "status", "billed_before", "billed_after", "change"])
    for a in report["adjustments"]:
        w.writerow([a["id"], a["action"], a["status"], a["before_amount"], a["after_amount"],
                    a["amount"]])
    return buf.getvalue()


def to_html(report: dict[str, Any]) -> str:
    def fmt(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:,.2f}"
        return html.escape(str(v if v is not None else "-"))
    keys = ["accounts_checked_pct", "controls_run", "exceptions_found", "leakage_identified",
            "leakage_recovered", "evidence_trail"]
    rows = "".join(f"<tr><th>{k.replace('_', ' ')}</th><td>{fmt(report['before'].get(k))}</td>"
                   f"<td>{fmt(report['after'].get(k))}</td></tr>" for k in keys)
    ctl = "".join(f"<tr><th>{c} {html.escape(v['name'])}</th><td>{v['count']}</td>"
                  f"<td>{fmt(float(v['value']))}</td></tr>" for c, v in report["by_control"].items())
    adj = "".join(f"<tr><th>{a['id']}</th><td>{a['action']}</td><td>{a['status']}</td>"
                  f"<td>{fmt(float(a['before_amount']))}</td><td>{fmt(float(a['after_amount']))}"
                  f"</td></tr>" for a in report["adjustments"][:200])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Before and after: run {html.escape(report['run_id'])}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;
color:#1c2530}}table{{border-collapse:collapse;width:100%;margin:1rem 0 2rem}}
th,td{{text-align:left;padding:.45rem .6rem;border-bottom:1px solid #d9dee5}}
td{{font-variant-numeric:tabular-nums}}thead th{{border-bottom:2px solid #1c2530}}
.note{{background:#fff7e0;padding:.7rem 1rem;border-left:4px solid #c98a00}}</style>
<h1>Before and after</h1>
<p>Run {html.escape(report['run_id'])}, period {html.escape(report['period'])}.
Match rate {report['match_rate']}. Generated {html.escape(report['generated'])}.</p>
<p class="note">{html.escape(report['caveat'])}</p>
<table><thead><tr><th>Measure</th><th>Before (manual sample)</th><th>After (this product)</th>
</tr></thead><tbody>{rows}</tbody></table>
<h2>Exceptions by control</h2>
<table><thead><tr><th>Control</th><th>Count</th><th>Value</th></tr></thead><tbody>{ctl}</tbody></table>
<h2>Adjustments: billed amount before and after</h2>
<table><thead><tr><th>Adjustment</th><th>Action</th><th>Status</th><th>Before</th><th>After</th>
</tr></thead><tbody>{adj}</tbody></table></html>"""
