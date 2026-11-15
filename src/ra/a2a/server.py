"""Inbound A2A: lets other agents (a finance-close agent, a customer-care agent) ask this
product about exceptions. Each skill maps to a normal permission, so an agent gets exactly
what its role allows and nothing more."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request

from ra import a2a, audit, cases, db, reporting
from ra.auth import Principal
from ra.auth.policy import Forbidden, authorize
from ra.obs import metrics, span
from ra.settings import get_settings
from ra.shared.tool_base import ToolError
from ra.tools import registry

router = APIRouter()

SKILLS = {
    "explain-exception": ("Explain an exception", "exceptions:read",
                          ("Root cause, variance, evidence IDs and case findings for one "
                          "exception. Input: {exception_id}.")),
    "run-summary": ("Summarize the latest run", "reports:read",
                    ("Counts and value of exceptions by control, with the before/after "
                    "comparison. Input: {}.")),
    "investigate-exception": ("Investigate an exception", "cases:work",
                              ("Run the agent investigation and create a pending proposal. "
                              "Input: {exception_id}.")),
}


def agent_card() -> dict[str, Any]:
    base = get_settings().base_url.rstrip("/")
    return {
        "protocolVersion": a2a.PROTOCOL_VERSION, "name": "Revenue Assurance Agent",
        "description": "Reconciles ten billing and finance systems, explains every break with "
                       "evidence, and proposes corrections for human approval.",
        "url": f"{base}/a2a", "preferredTransport": "JSONRPC", "version": get_settings().release,
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
        "security": [{"bearer": []}],
        "skills": [{"id": sid, "name": name, "description": desc, "tags": ["revenue-assurance"]}
                   for sid, (name, _, desc) in SKILLS.items()],
    }


def _run_skill(p: Principal, data: dict[str, Any]) -> dict[str, Any]:
    skill = data.get("skill")
    if skill not in SKILLS:
        raise ValueError(f"unknown skill; offered: {sorted(SKILLS)}")
    authorize(p, SKILLS[skill][1], resource_id=f"a2a:{skill}")
    if skill == "run-summary":
        return reporting.before_after(_latest_run())
    exc_id = str(data.get("exception_id", ""))
    if skill == "investigate-exception":
        case = cases.investigate(exc_id, p)
        return {"case_id": case["id"], "status": case["status"],
                "verification": case["verification"], "adjustment": case["adjustment"]}
    exc = registry.invoke(p, "get_exception", {"exception_id": exc_id})["data"]
    case = db.one("SELECT status, skill, findings, verification FROM cases WHERE exception_id=?",
                  (exc_id,))
    return {"exception": {k: exc[k] for k in ("id", "control", "account_id", "variance",
                                               "currency", "severity", "status", "root_cause",
                                               "action", "confidence", "rationale", "record_uids")},
            "case": case}


def _latest_run() -> str:
    from ra.tools.builtin import latest_run
    return latest_run()


def make_router(principal_dep) -> APIRouter:
    @router.post("/a2a")
    async def rpc(request: Request, p: Principal = Depends(principal_dep)):
        body = await request.json()
        rpc_id, method, params = body.get("id"), body.get("method"), body.get("params") or {}
        version = request.headers.get("a2a-version", "0.3")
        if not version.startswith("0.3"):
            return a2a.rpc_error(rpc_id, -32600, f"A2A version {version} not supported; use 0.3")
        try:
            authorize(p, "a2a:invoke", resource_id=f"a2a:{method}")
        except Forbidden as err:
            return a2a.rpc_error(rpc_id, -32600, f"forbidden: {err.reason}")
        if method == "tasks/get":
            row = db.one("SELECT * FROM a2a_tasks WHERE id=? AND caller=?",
                         (params.get("id"), p.sub))
            if not row:
                return a2a.rpc_error(rpc_id, -32001, "task not found")
            return {"jsonrpc": "2.0", "id": rpc_id, "result": row["result"]}
        if method == "tasks/cancel":
            return a2a.rpc_error(rpc_id, -32002, "task cannot be canceled: tasks finish in-call")
        if method != "message/send":
            return a2a.rpc_error(rpc_id, -32601, "method not found")
        message = params.get("message") or {}
        data = a2a.first_data(message)
        task_id = uuid.uuid4().hex
        ctx = message.get("contextId") or uuid.uuid4().hex
        with span("a2a.inbound", **{"a2a.skill": data.get("skill"), "ra.principal": p.sub}):
            try:
                result = a2a.task(task_id, ctx, "completed", data=_run_skill(p, data),
                                  name=str(data.get("skill")))
                outcome = "ok"
            except Forbidden as err:
                result = a2a.task(task_id, ctx, "rejected", text=f"forbidden: {err.reason}")
                outcome = "forbidden"
            except (ValueError, ToolError, cases.Conflict) as err:
                result = a2a.task(task_id, ctx, "failed", text=str(err)[:300])
                outcome = "failed"
        metrics.A2A_CALLS.labels(direction="inbound", outcome=outcome).inc()
        db.insert("a2a_tasks", {"id": task_id, "context_id": ctx, "caller": p.sub,
                                "state": result["status"]["state"], "request": data,
                                "result": result, "created": db.now()})
        audit.record(p.sub, p.kind, "a2a:inbound", task_id, "info",
                     {"skill": data.get("skill"), "outcome": outcome})
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    return router
