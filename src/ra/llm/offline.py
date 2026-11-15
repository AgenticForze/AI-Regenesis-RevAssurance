"""Deterministic stand-in for the model.

It reads the same payload a model would and applies explicit rules, so demos, tests and CI run
without credentials or cost. Token counts are estimated from text length so cost reports have
realistic shape. It is not a model: on real data it will only be as good as these rules.
"""
from __future__ import annotations

from typing import Any

from ra.llm import estimate_tokens


def _triage(exc: dict[str, Any]) -> dict[str, Any]:
    f, v, c = exc["features"], exc["variance"], exc["control"]
    conf = 0.93
    if c == "C1":
        if not f.get("feed_complete", True) or v < 0:
            rc, act = "RC14_data_quality_false_break", "fix_feed"
            conf = 0.9 if not f.get("feed_complete", True) else 0.7
        else:
            rc, act = "RC03_missing_usage", "rebill"
    elif c == "C2":
        rc, act = "RC03_missing_usage", "rebill"
    elif c == "C3":
        rc, act = (("RC06_billed_not_provisioned", "credit") if f.get("has_charge")
                   else ("RC05_provisioned_not_billed", "rebill"))
    elif c == "C4":
        rc, act = "RC07_discount_misapplied", "rebill" if v > 0 else "credit"
    elif c == "C5":
        if f.get("tariff_version") != "v2":
            rc, act = "RC02_price_book_mismatch", "correct_catalog"
        else:
            rc, act, conf = "RC01_rating_error", "fix_rating_config", 0.85
    elif c == "C6":
        if f.get("payment_status") == "pending" and f.get("expected_days", 99) <= 5:
            rc, act = "RC10_timing_cutoff", "no_action"
        else:
            rc, act, conf = "RC99_other", "escalate", 0.5
    elif c == "C7":
        if f.get("posting_period") != f.get("period"):
            rc, act = "RC10_timing_cutoff", "no_action"
        else:
            rc, act = "RC13_ledger_posting_error", "journal_correction"
    elif c == "C8":
        rc, act = "RC11_partner_variance", "dispute_partner"
    elif c == "C9":
        rc, act = "RC04_duplicate_billing", "credit"
    else:
        rc, act, conf = "RC99_other", "escalate", 0.4
    return {"root_cause": rc, "action": act, "confidence": conf,
            "evidence_ids": exc["record_uids"][:5], "missing_info": [],
            "rationale": f"{exc['control']} break: {exc['summary']}"[:600]}


def _investigate(p: dict[str, Any]) -> dict[str, Any]:
    exc, triage, evidence = p["exception"], p["triage"], p["evidence"]
    amount = exc["variance"]
    notes = []
    partner = evidence.get("query_partner_statement", {}).get("data")
    if partner:
        amount = round(exc["expected"] - partner["statement_amount"], 2)
        notes.append(f"partner reported {partner['days_reported']} of {partner['days_in_period']} "
                     f"days; missing days {partner['missing_days']}")
    ids: list[str] = []
    for name, res in evidence.items():
        ids += res.get("record_uids", [])
        notes.append(f"{name}: {len(res.get('record_uids', []))} records")
    return {"root_cause": triage["root_cause"], "action": triage["action"],
            "proposed_amount": amount, "confidence": min(0.97, triage["confidence"] + 0.03),
            "evidence_ids": sorted(set(ids))[:20],
            "narrative": (f"{exc['summary']}. Evidence reviewed: " + "; ".join(notes)
                          + f". Proposed correction {amount:.2f} {exc['currency']}.")[:1200]}


class OfflineReasoner:
    name = "offline-reasoner"

    def complete_json(self, step: str, system: str, payload: dict[str, Any]):
        answer = _triage(payload["exception"]) if step == "triage" else _investigate(payload)
        return answer, estimate_tokens(system) + estimate_tokens(payload), estimate_tokens(answer)
