"""HTTP API. Every route except health, the agent card, the JWKS and the token endpoint needs
a bearer token; every data route also passes a policy check."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from ra import audit, cases, db, mcp_server, obs, plugins, reporting, skills
from ra.a2a import server as a2a_server
from ra.auth import Principal, current_principal, idp, tokens
from ra.auth.policy import Forbidden, authorize, permissions
from ra.obs import metrics
from ra.recon import engine
from ra.recon.controls import CONTROLS
from ra.recon.generator import SOURCES
from ra.settings import get_settings
from ra.shared.budgets import BudgetExceeded
from ra.shared.tool_base import NotFound, ToolError
from ra.tools import registry

WEB = Path(__file__).resolve().parents[1] / "web"
_mcp = mcp_server.build()


@asynccontextmanager
async def lifespan(_: FastAPI):
    obs.setup()
    db.conn()
    async with _mcp.session_manager.run():
        yield


app = FastAPI(title="Revenue Assurance", version=get_settings().release, lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")


# ---------- authentication ----------
def principal(authorization: str = Header(default="")) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token", {"WWW-Authenticate": "Bearer"})
    try:
        p = tokens.verify(authorization[7:].strip())
    except tokens.AuthError as err:
        metrics.AUTH_EVENTS.labels(event="token_rejected").inc()
        raise HTTPException(401, str(err), {"WWW-Authenticate": "Bearer"}) from err
    current_principal.set(p)
    return p


def require(permission: str):
    def dep(p: Principal = Depends(principal)) -> Principal:
        authorize(p, permission)
        return p
    return dep


_attempts: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(key: str, limit: int = 20, window: float = 60.0) -> None:
    q, now = _attempts[key], time.monotonic()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "too many attempts; try again in a minute")
    q.append(now)


@app.post("/auth/token")
def token(request: Request, grant_type: str = Form(...), username: str = Form(""),
          password: str = Form(""), client_id: str = Form(""), client_secret: str = Form("")):
    """OAuth 2.0 token endpoint of the built-in identity provider (password and
    client_credentials grants). Disabled when an external OIDC issuer is configured."""
    if get_settings().oidc_issuer:
        raise HTTPException(404, "sign in with the configured identity provider")
    _rate_limit(request.client.host if request.client else "unknown")
    if grant_type == "password":
        return idp.password_grant(username, password)
    if grant_type == "client_credentials":
        return idp.client_credentials_grant(client_id, client_secret)
    raise HTTPException(400, "unsupported grant_type")


@app.get("/auth/jwks.json")
def jwks():
    return tokens.jwks()


@app.get("/auth/me")
def me(p: Principal = Depends(principal)):
    return {"sub": p.sub, "kind": p.kind, "roles": p.roles, "bu_scope": p.bu_scope,
            "approval_limit": p.approval_limit, "permissions": sorted(permissions(p))}


# ---------- platform ----------
@app.get("/healthz")
def healthz():
    return {"status": "ok", "release": get_settings().release}


@app.get("/readyz")
def readyz():
    db.one("SELECT 1 AS ok")
    return {"status": "ready", "llm_mode": get_settings().llm_mode,
            "auth": "oidc" if get_settings().oidc_issuer else "built-in"}


@app.get("/metrics")
def prometheus():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/.well-known/agent-card.json")
def agent_card():
    return a2a_server.agent_card()


@app.get("/api/meta")
def meta(p: Principal = Depends(principal)):
    return {"sources": SOURCES, "controls": CONTROLS, "skills": skills.index(),
            "tools": registry.catalog(p), "plugin_types": sorted(plugins.types())}


# ---------- runs ----------
class RunRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    accounts: int = Field(default=400, ge=10, le=20000)
    seed: int = 7
    data: str = Field(default="synthetic", pattern="^(synthetic|sources)$")
    auto_investigate: bool = True


@app.post("/api/runs")
def start_run(req: RunRequest, p: Principal = Depends(principal)):
    return engine.run(p, req.period, req.accounts, req.seed, req.data, req.auto_investigate)


@app.get("/api/runs")
def list_runs(_: Principal = Depends(require("runs:read"))):
    return db.query("SELECT * FROM runs ORDER BY started DESC LIMIT 50")


# ---------- exceptions and cases ----------
def _visible(rows: list[dict], p: Principal) -> list[dict]:
    out = [r for r in rows if p.sees_bu(r.get("bu"))]
    for r in out:
        r.pop("truth", None)
    return out


@app.get("/api/exceptions")
def list_exceptions(run_id: str = "", status: str = "", control: str = "", limit: int = 200,
                    p: Principal = Depends(require("exceptions:read"))):
    run_id = run_id or (db.one("SELECT id FROM runs ORDER BY started DESC LIMIT 1") or {}).get("id")
    sql, params = "SELECT * FROM exceptions WHERE run_id=?", [run_id]
    for col, val in (("status", status), ("control", control)):
        if val:
            sql += f" AND {col}=?"
            params.append(val)
    return _visible(db.query(sql + " ORDER BY ABS(variance) DESC LIMIT ?",
                             [*params, min(limit, 1000)]), p)


@app.get("/api/exceptions/{exception_id}")
def get_exception(exception_id: str, p: Principal = Depends(principal)):
    exc = registry.invoke(p, "get_exception", {"exception_id": exception_id})["data"]
    case = db.one("SELECT * FROM cases WHERE exception_id=?", (exception_id,))
    adjs = db.query("SELECT * FROM adjustments WHERE exception_id=? ORDER BY created",
                    (exception_id,))
    return {"exception": exc, "case": case, "adjustments": adjs}


@app.post("/api/exceptions/{exception_id}/investigate")
def investigate(exception_id: str, p: Principal = Depends(principal)):
    out = cases.investigate(exception_id, p)
    plugins.dispatch()
    return out


class Proposal(BaseModel):
    action: str
    amount: float
    reason: str = Field(min_length=10, max_length=500)


@app.post("/api/cases/{case_id}/adjustments")
def propose(case_id: str, body: Proposal, p: Principal = Depends(principal)):
    out = registry.invoke(p, "propose_adjustment", {"case_id": case_id, **body.model_dump()})
    plugins.dispatch()
    return out["data"]


@app.get("/api/adjustments")
def list_adjustments(status: str = "", p: Principal = Depends(require("adjustments:read"))):
    sql, params = ("SELECT a.*, e.account_id, e.control, e.root_cause FROM adjustments a " \
                  "JOIN exceptions e ON e.id=a.exception_id"), []
    if status:
        sql += " WHERE a.status=?"
        params.append(status)
    return _visible(db.query(sql + " ORDER BY a.created DESC LIMIT 500", params), p)


class DecisionBody(BaseModel):
    approve: bool
    comment: str = Field(default="", max_length=500)


@app.post("/api/adjustments/{adjustment_id}/decision")
def decide(adjustment_id: str, body: DecisionBody, p: Principal = Depends(principal)):
    out = cases.decide(adjustment_id, body.approve, p, body.comment)
    plugins.dispatch()
    return out


# ---------- tools, reports, audit, observability, plug-ins ----------
@app.post("/api/tools/{name}")
def call_tool(name: str, args: dict[str, Any], p: Principal = Depends(principal)):
    return registry.invoke(p, name, args)


def _report(run_id: str) -> dict[str, Any]:
    run_id = run_id or (db.one("SELECT id FROM runs ORDER BY started DESC LIMIT 1") or {}).get("id")
    if not run_id:
        raise NotFound("no reconciliation run yet")
    return reporting.before_after(run_id)


@app.get("/api/reports/before-after")
def report_json(run_id: str = "", _: Principal = Depends(require("reports:read"))):
    return _report(run_id)


@app.get("/api/reports/before-after.csv")
def report_csv(run_id: str = "", _: Principal = Depends(require("reports:read"))):
    return PlainTextResponse(reporting.to_csv(_report(run_id)), media_type="text/csv")


@app.get("/api/reports/before-after.html")
def report_html(run_id: str = "", _: Principal = Depends(require("reports:read"))):
    return HTMLResponse(reporting.to_html(_report(run_id)))


@app.get("/api/reports/triage-quality")
def report_quality(run_id: str = "", _: Principal = Depends(require("audit:read"))):
    return reporting.triage_quality(run_id or _report("")["run_id"])


@app.get("/api/audit")
def audit_search(actor: str = "", action: str = "", resource: str = "", decision: str = "",
                 limit: int = 200, _: Principal = Depends(require("audit:read"))):
    return audit.search(actor or None, action or None, resource or None, decision or None, limit)


@app.get("/api/audit/verify")
def audit_verify(_: Principal = Depends(require("audit:verify"))):
    return audit.verify()


@app.get("/api/traces")
def traces(_: Principal = Depends(require("obs:read"))):
    return obs.recent.recent_roots()


@app.get("/api/traces/{trace_id}")
def trace(trace_id: str, _: Principal = Depends(require("obs:read"))):
    return obs.recent.by_trace(trace_id)


@app.get("/api/costs")
def costs(_: Principal = Depends(require("obs:read"))):
    return db.query("SELECT step, model, COUNT(*) calls, SUM(input_tokens) input_tokens, "
                    "SUM(output_tokens) output_tokens, ROUND(SUM(cost_usd),4) cost_usd, "
                    "ROUND(AVG(latency_ms),2) avg_latency_ms FROM llm_calls GROUP BY step, model")


@app.get("/api/plugins")
def list_plugins(_: Principal = Depends(require("plugins:read"))):
    return {"configured": plugins.describe(),
            "outbox": db.query("SELECT status, COUNT(*) n FROM outbox GROUP BY status"),
            "recent": db.query("SELECT id,plugin,event,status,attempts,last_error,result,created "
                               "FROM outbox ORDER BY created DESC LIMIT 50")}


@app.post("/api/plugins/dispatch")
def dispatch(_: Principal = Depends(require("plugins:dispatch"))):
    return plugins.dispatch()


class NewUser(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,40}$")
    password: str = Field(min_length=12)
    roles: list[str]
    bu_scope: list[str] = ["*"]
    approval_limit: float = 0


@app.post("/api/admin/users")
def create_user(body: NewUser, p: Principal = Depends(require("admin:users"))):
    idp.create_user(body.username, body.password, body.roles, body.bu_scope, body.approval_limit)
    audit.record(p.sub, p.kind, "admin:user_created", body.username, "info",
                 {"roles": body.roles, "bu_scope": body.bu_scope,
                  "approval_limit": body.approval_limit})
    return {"username": body.username, "roles": body.roles}


@app.get("/api/admin/users")
def list_users(_: Principal = Depends(require("admin:users"))):
    return db.query("SELECT username, roles, bu_scope, approval_limit, disabled FROM users")


# ---------- A2A and MCP ----------
app.include_router(a2a_server.make_router(principal))
app.mount("/mcp", mcp_server.BearerAuth(_mcp.streamable_http_app(
    streamable_http_path="/", json_response=True, stateless_http=True,
    transport_security=mcp_server.transport_security())))


# ---------- console ----------
@app.get("/", response_class=HTMLResponse)
def console():
    return (WEB / "console.html").read_text()


# ---------- cross-cutting ----------
@app.middleware("http")
async def observe(request: Request, call_next):
    route = request.url.path
    t0 = time.perf_counter()
    with obs.span(f"{request.method} {route}", **{"http.request.method": request.method,
                                                  "url.path": route}) as sp:
        response = await call_next(request)
        sp.set_attribute("http.response.status_code", response.status_code)
        matched = request.scope.get("route")
        label = getattr(matched, "path", route if route.startswith("/mcp") else "unmatched")
    metrics.HTTP_REQUESTS.labels(request.method, label, response.status_code).inc()
    metrics.HTTP_LATENCY.labels(label).observe(time.perf_counter() - t0)
    response.headers["X-Trace-Id"] = obs.current_trace_id() or f"{sp.get_span_context().trace_id:032x}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if route == "/":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' "
            "'unsafe-inline'; frame-ancestors 'none'")
    return response


def _error(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail, "trace_id": obs.current_trace_id()}, status_code=status)


@app.exception_handler(Forbidden)
async def _forbidden(_: Request, err: Forbidden):
    return _error(403, err.reason)


@app.exception_handler(idp.LoginFailed)
async def _login_failed(_: Request, err: idp.LoginFailed):
    return _error(401, str(err))


@app.exception_handler(NotFound)
async def _not_found(_: Request, err: NotFound):
    return _error(404, str(err))


@app.exception_handler(cases.Conflict)
async def _conflict(_: Request, err: cases.Conflict):
    return _error(409, str(err))


@app.exception_handler(BudgetExceeded)
async def _budget(_: Request, err: BudgetExceeded):
    return _error(429, str(err))


@app.exception_handler(ToolError)
async def _tool_error(_: Request, err: ToolError):
    return _error(400, str(err))


@app.exception_handler(ValueError)
async def _bad_request(_: Request, err: ValueError):
    return _error(400, str(err))
