"""Mock partner settlement agent (A2A server) for demos and tests.

It stands in for a roaming or wholesale partner's own agent. It answers one skill,
`statement-detail`, from the synthetic S10 statement. Run it separately with
`uvicorn ra.a2a.mock_partner:app --port 8090`; set PARTNER_TOKEN to require a bearer token.
"""
from __future__ import annotations

import calendar
import hmac
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ra import a2a, db

app = FastAPI(title="Mock partner settlement agent")
BASE = os.environ.get("PARTNER_BASE_URL", "http://partner.local")


@app.get("/.well-known/agent-card.json")
def card() -> dict:
    return {"protocolVersion": a2a.PROTOCOL_VERSION, "name": "Partner Settlement Agent (mock)",
            "description": "Explains the detail behind a partner settlement statement.",
            "url": f"{BASE}/a2a", "preferredTransport": "JSONRPC", "version": "0.1.0",
            "capabilities": {"streaming": False, "pushNotifications": False},
            "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
            "skills": [{"id": "statement-detail", "name": "Statement detail",
                        "description": "Days reported and totals for one account and period.",
                        "tags": ["settlement"]}]}


@app.post("/a2a")
async def rpc(request: Request):
    expected = os.environ.get("PARTNER_TOKEN", "")
    got = request.headers.get("authorization", "").removeprefix("Bearer ")
    if expected and not hmac.compare_digest(expected, got):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    if body.get("method") != "message/send":
        return a2a.rpc_error(body.get("id"), -32601, "method not found")
    data = a2a.first_data(body.get("params", {}).get("message", {}))
    task_id, ctx = uuid.uuid4().hex, uuid.uuid4().hex
    stmt = db.one("SELECT * FROM records WHERE source='S10' AND account_id=? AND period=? "
                  "ORDER BY uid DESC LIMIT 1", (data.get("account_id"), data.get("period")))
    if data.get("skill") != "statement-detail" or not stmt:
        result = a2a.task(task_id, ctx, "failed", text="no statement for that account and period")
    else:
        y, m = (int(x) for x in data["period"].split("-"))
        days = calendar.monthrange(y, m)[1]
        reported = min(stmt["attrs"]["days_reported"], days)
        result = a2a.task(task_id, ctx, "completed", name="statement-detail", data={
            "partner_id": stmt["attrs"]["partner_id"], "period": data["period"],
            "statement_amount": stmt["amount"], "currency": stmt["currency"],
            "days_in_period": days, "days_reported": reported,
            "missing_days": list(range(reported + 1, days + 1)), "record_uids": [stmt["uid"]]})
    return {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
