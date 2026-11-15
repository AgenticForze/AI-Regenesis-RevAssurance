"""Case workflow: exception -> case -> pending adjustment -> human decision -> posting.

State changes happen only here, each one behind a policy check and followed by an audit event
that records the value before and after.
"""
from __future__ import annotations

from typing import Any

from ra import audit, db, plugins
from ra.agents import runtime
from ra.auth import AGENT, Principal
from ra.auth.policy import authorize
from ra.obs import metrics, span
from ra.shared.schemas import ACTIONS
from ra.shared.tool_base import NotFound


class Conflict(Exception):
    pass


def _exception(exception_id: str) -> dict[str, Any]:
    exc = db.one("SELECT * FROM exceptions WHERE id=?", (exception_id,))
    if not exc:
        raise NotFound(f"unknown exception {exception_id}")
    return exc


def investigate(exception_id: str, actor: Principal) -> dict[str, Any]:
    """Open (or re-open) a case and run the agent investigation. `actor` is who asked."""
    exc = _exception(exception_id)
    authorize(actor, "cases:work", {"bu": exc["bu"]}, exception_id)
    case = db.one("SELECT * FROM cases WHERE exception_id=?", (exception_id,))
    if case and case["status"] in ("proposed", "resolved"):
        raise Conflict(f"case {case['id']} is already {case['status']}")
    with span("case.investigate", **{"ra.exception_id": exception_id, "ra.actor": actor.sub}):
        if not case:
            case = {"id": db.new_id("case"), "exception_id": exception_id, "status": "open",
                    "assignee": actor.sub, "skill": "", "findings": {}, "verification": {},
                    "created": db.now(), "updated": db.now()}
            db.insert("cases", case)
            plugins.emit("case.opened", case["id"],
                         {"id": case["id"], "exception_id": exception_id,
                          "account_id": exc["account_id"], "control": exc["control"],
                          "variance": exc["variance"], "currency": exc["currency"],
                          "root_cause": exc["root_cause"]})
        finding, verification, skill = runtime.investigate(exc, case["id"])
        status = "verified" if verification["passed"] else "needs_review"
        db.update("cases", "id", case["id"], {"status": status, "skill": skill,
                                              "findings": finding, "verification": verification,
                                              "updated": db.now()})
        db.update("exceptions", "id", exception_id, {"status": "investigating"})
        audit.record(AGENT.sub, "agent", "case:investigated", case["id"], "info",
                     {"requested_by": actor.sub, "skill": skill, "passed": verification["passed"],
                      "proposed_amount": finding.get("proposed_amount")})
        adjustment = None
        if verification["passed"]:
            from ra.tools import registry
            adjustment = registry.invoke(AGENT, "propose_adjustment", {
                "case_id": case["id"], "action": finding["action"],
                "amount": finding["proposed_amount"], "reason": finding["narrative"][:500]})["data"]
    return {**db.one("SELECT * FROM cases WHERE id=?", (case["id"],)), "adjustment": adjustment}


def propose(case_id: str, action: str, amount: float, reason: str,
            principal: Principal) -> dict[str, Any]:
    case = db.one("SELECT * FROM cases WHERE id=?", (case_id,))
    if not case:
        raise NotFound(f"unknown case {case_id}")
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action}")
    exc = _exception(case["exception_id"])
    authorize(principal, "adjustments:propose", {"bu": exc["bu"]}, case_id)
    if db.one("SELECT id FROM adjustments WHERE case_id=? AND status='pending'", (case_id,)):
        raise Conflict("this case already has a pending adjustment")
    adj = {"id": db.new_id("adj"), "case_id": case_id, "exception_id": exc["id"],
           "action": action, "amount": round(amount, 2), "currency": exc["currency"],
           "bu": exc["bu"], "status": "pending", "proposed_by": principal.sub, "decided_by": None,
           "reason": reason, "before_amount": exc["actual"],
           "after_amount": round(exc["actual"] + amount, 2), "posting_ref": None,
           "created": db.now(), "decided": None}
    db.insert("adjustments", adj)
    db.update("cases", "id", case_id, {"status": "proposed", "updated": db.now()})
    db.update("exceptions", "id", exc["id"], {"status": "proposed"})
    audit.record(principal.sub, principal.kind, "adjustment:proposed", adj["id"], "info",
                 {"case_id": case_id, "action": action, "before": adj["before_amount"],
                  "after": adj["after_amount"], "amount": adj["amount"]})
    plugins.emit("adjustment.proposed", adj["id"], {**adj, "account_id": exc["account_id"]})
    _gauges()
    return adj


def decide(adjustment_id: str, approve: bool, principal: Principal,
           comment: str = "") -> dict[str, Any]:
    adj = db.one("SELECT * FROM adjustments WHERE id=?", (adjustment_id,))
    if not adj:
        raise NotFound(f"unknown adjustment {adjustment_id}")
    authorize(principal, "adjustments:approve",
              {"bu": adj["bu"], "amount": adj["amount"], "proposed_by": adj["proposed_by"]},
              adjustment_id)
    if adj["status"] != "pending":
        raise Conflict(f"adjustment is already {adj['status']}")
    if not approve and not comment.strip():
        raise ValueError("a rejection needs a comment")
    status = "approved" if approve else "rejected"
    exc = _exception(adj["exception_id"])
    db.update("adjustments", "id", adjustment_id,
              {"status": status, "decided_by": principal.sub, "decided": db.now()})
    db.update("cases", "id", adj["case_id"],
              {"status": "resolved" if approve else "needs_review", "updated": db.now()})
    db.update("exceptions", "id", adj["exception_id"],
              {"status": "resolved" if approve else "investigating"})
    audit.record(principal.sub, "user", f"adjustment:{status}", adjustment_id, "info",
                 {"comment": comment, "amount": adj["amount"], "before": adj["before_amount"],
                  "after": adj["after_amount"] if approve else adj["before_amount"],
                  "proposed_by": adj["proposed_by"]})
    metrics.ADJUSTMENTS.labels(status=status).inc()
    if approve:
        metrics.RECOVERED.labels(bu=adj["bu"]).inc(abs(adj["amount"]))
    plugins.emit(f"adjustment.{status}", adjustment_id,
                 {**adj, "status": status, "decided_by": principal.sub,
                  "account_id": exc["account_id"], "comment": comment})
    _gauges()
    return db.one("SELECT * FROM adjustments WHERE id=?", (adjustment_id,))


def _gauges() -> None:
    metrics.PENDING_APPROVALS.set(
        db.one("SELECT COUNT(*) n FROM adjustments WHERE status='pending'")["n"])
    metrics.OPEN_EXCEPTIONS.set(
        db.one("SELECT COUNT(*) n FROM exceptions WHERE status NOT IN ('resolved','monitor')")["n"])
