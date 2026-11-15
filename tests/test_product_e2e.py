"""End-to-end checks through the HTTP API: sign-in, policy, workflow, audit, MCP, A2A."""
import json

from conftest import PASSWORD

from ra import audit, db


def test_requires_token(client):
    assert client.get("/api/exceptions").status_code == 401
    assert client.get("/api/exceptions", headers={"Authorization": "Bearer x.y.z"}).status_code == 401
    assert client.get("/healthz").status_code == 200


def test_bad_password_is_rejected_and_audited(client):
    r = client.post("/auth/token", data={"grant_type": "password", "username": "alice.analyst",
                                         "password": "wrong-password-1"})
    assert r.status_code == 401
    assert audit.search(action="auth:login", decision="deny")


def test_tampered_token_rejected(client, login):
    tok = login("alice.analyst")["Authorization"]
    assert client.get("/auth/me", headers={"Authorization": tok[:-4] + "AAAA"}).status_code == 401


def test_run_and_match_rate(run):
    s = run["stats"]
    assert s["exceptions"] > 0 and 0.9 < s["match_rate"] < 1
    assert set(s["by_control"]) <= {f"C{i}" for i in range(1, 10)}


def test_rbac_viewer_cannot_run_or_read_audit(client, login, run):
    assert client.post("/api/runs", json={"period": "2026-10"},
                       headers=login("alice.analyst")).status_code == 403
    assert client.get("/api/audit", headers=login("alice.analyst")).status_code == 403
    assert client.get("/api/audit", headers=login("dana.auditor")).status_code == 200


def test_business_unit_scope(client, login, run):
    rows = client.get("/api/exceptions?limit=1000", headers=login("ed.enterprise")).json()
    assert rows and {r["bu"] for r in rows} == {"enterprise"}
    other = db.one("SELECT id, account_id FROM exceptions WHERE bu='consumer' LIMIT 1")
    assert client.get(f"/api/exceptions/{other['id']}",
                      headers=login("ed.enterprise")).status_code == 403
    r = client.post("/api/tools/get_invoice_lines", json={"account_id": other["account_id"]},
                    headers=login("ed.enterprise"))
    assert r.status_code == 403


def test_ground_truth_never_leaves_api(client, login, run):
    rows = client.get("/api/exceptions", headers=login("alice.analyst")).json()
    assert all("truth" not in r for r in rows)


def _pending(max_amount=None, min_amount=0.0):
    rows = db.query("SELECT * FROM adjustments WHERE status='pending' ORDER BY ABS(amount)")
    rows = [r for r in rows if abs(r["amount"]) >= min_amount
            and (max_amount is None or abs(r["amount"]) <= max_amount)]
    return rows[0] if rows else None


def test_agent_proposals_are_pending_and_verified(run):
    cases = db.query("SELECT * FROM cases")
    assert cases and all(c["status"] == "proposed" for c in cases)
    assert all(c["verification"]["passed"] for c in cases)
    assert all(a["proposed_by"] == "agent:ra-runtime"
               for a in db.query("SELECT proposed_by FROM adjustments"))


def test_analyst_cannot_approve(client, login, run):
    adj = _pending()
    r = client.post(f"/api/adjustments/{adj['id']}/decision", json={"approve": True},
                    headers=login("alice.analyst"))
    assert r.status_code == 403


def test_approval_limit_then_approve(client, login, run):
    big = _pending(min_amount=10_001)
    if big:
        r = client.post(f"/api/adjustments/{big['id']}/decision", json={"approve": True},
                        headers=login("bob.approver"))
        assert r.status_code == 403 and "limit" in r.json()["detail"]
    adj = _pending(max_amount=10_000)
    r = client.post(f"/api/adjustments/{adj['id']}/decision", json={"approve": True},
                    headers=login("bob.approver"))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # decided twice -> conflict
    assert client.post(f"/api/adjustments/{adj['id']}/decision", json={"approve": True},
                       headers=login("carol.controller")).status_code == 409
    out = db.one("SELECT * FROM outbox WHERE plugin='erp-journal' AND idem_key LIKE ?",
                 (f"%{adj['id']}",))
    assert out["status"] == "delivered" and out["result"]["posting_ref"] == f"RAJ-{adj['id']}"


def test_rejection_needs_comment(client, login, run):
    adj = _pending(max_amount=10_000)
    h = login("bob.approver")
    assert client.post(f"/api/adjustments/{adj['id']}/decision", json={"approve": False},
                       headers=h).status_code == 400
    r = client.post(f"/api/adjustments/{adj['id']}/decision",
                    json={"approve": False, "comment": "customer already credited"}, headers=h)
    assert r.json()["status"] == "rejected"


def test_four_eyes(client, login, run):
    exc = db.one("SELECT id FROM exceptions WHERE status='triaged' AND bu='consumer' "
                 "ORDER BY ABS(variance) DESC LIMIT 1")
    root = login("root.admin")
    case = client.post(f"/api/exceptions/{exc['id']}/investigate", headers=root).json()
    # reject the agent's proposal, then the admin proposes one personally
    client.post(f"/api/adjustments/{case['adjustment']['id']}/decision",
                json={"approve": False, "comment": "testing manual proposal"}, headers=root)
    mine = client.post(f"/api/cases/{case['id']}/adjustments", headers=root,
                       json={"action": "rebill", "amount": 12.5, "reason": "manual correction test"})
    assert mine.status_code == 200, mine.text
    r = client.post(f"/api/adjustments/{mine.json()['id']}/decision", json={"approve": True},
                    headers=root)
    assert r.status_code == 403 and "four-eyes" in r.json()["detail"]


def test_before_after_report(client, login, run):
    h = login("dana.auditor")
    rep = client.get("/api/reports/before-after", headers=h).json()
    assert rep["after"]["accounts_checked_pct"] == 100.0
    assert rep["after"]["leakage_identified"] >= rep["before"]["leakage_identified"]
    assert rep["after"]["leakage_recovered"] > 0
    assert "modelled" in rep["caveat"]
    assert "metric,before,after" in client.get("/api/reports/before-after.csv", headers=h).text
    assert "<table>" in client.get("/api/reports/before-after.html", headers=h).text
    assert client.get("/api/reports/triage-quality", headers=h).json()["accuracy"] >= 0.95


def test_audit_chain_detects_tampering(client, login, run):
    h = login("dana.auditor")
    assert client.get("/api/audit/verify", headers=h).json()["ok"] is True
    row = db.one("SELECT seq, actor FROM audit ORDER BY seq LIMIT 1 OFFSET 5")
    db.execute("UPDATE audit SET actor='mallory' WHERE seq=?", (row["seq"],))
    bad = client.get("/api/audit/verify", headers=h).json()
    assert bad["ok"] is False and bad["first_bad_seq"] == row["seq"]
    db.execute("UPDATE audit SET actor=? WHERE seq=?", (row["actor"], row["seq"]))
    assert client.get("/api/audit/verify", headers=h).json()["ok"] is True


def test_observability(client, login, run):
    text = client.get("/metrics").text
    for name in ("ra_exceptions_total", "ra_tool_calls_total", "ra_llm_tokens_total",
                 "ra_authz_decisions_total", "ra_a2a_calls_total"):
        assert name in text
    h = login("omar.operator")
    roots = client.get("/api/traces", headers=h).json()
    assert roots and client.get(f"/api/traces/{roots[0]['trace_id']}", headers=h).json()
    assert "X-Trace-Id" in client.get("/healthz").headers
    assert client.get("/api/costs", headers=h).json()


def test_a2a_card_and_skills(client, login, run):
    card = client.get("/.well-known/agent-card.json").json()
    assert card["protocolVersion"].startswith("0.3") and len(card["skills"]) == 3
    exc = db.one("SELECT id FROM exceptions WHERE status='proposed' LIMIT 1")
    msg = {"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": {
        "kind": "message", "role": "user", "messageId": "m1",
        "parts": [{"kind": "data", "data": {"skill": "explain-exception",
                                            "exception_id": exc["id"]}}]}}}
    assert client.post("/a2a", json=msg).status_code == 401
    # an approver lacks a2a:invoke
    assert "forbidden" in client.post("/a2a", json=msg,
                                      headers=login("bob.approver")).json()["error"]["message"]
    res = client.post("/a2a", json=msg, headers=login("root.admin")).json()["result"]
    assert res["status"]["state"] == "completed"
    assert res["artifacts"][0]["parts"][0]["data"]["exception"]["id"] == exc["id"]
    got = client.post("/a2a", headers=login("root.admin"), json={
        "jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": res["id"]}}).json()
    assert got["result"]["id"] == res["id"]
    v1 = client.post("/a2a", json=msg, headers={**login("root.admin"), "A2A-Version": "1.0"})
    assert "not supported" in v1.json()["error"]["message"]


def test_a2a_outbound_partner_call(run):
    c = db.one("SELECT * FROM cases WHERE skill='investigate-partner-variance' LIMIT 1")
    assert c and "missing days" in c["findings"]["narrative"]
    assert audit.search(action="a2a:outbound")


def _mcp(client, headers, method, params=None, rid=1):
    r = client.post("/mcp/", headers={**headers, "Accept": "application/json, text/event-stream",
                                      "MCP-Protocol-Version": "2025-06-18"},
                    json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
    return r


def test_mcp_tools(client, login, run):
    secret = __import__("ra.auth.idp", fromlist=["x"]).create_client("mcp-test", ["integration"])
    tok = client.post("/auth/token", data={"grant_type": "client_credentials",
                                           "client_id": "mcp-test", "client_secret": secret}).json()
    h = {"Authorization": "Bearer " + tok["access_token"]}
    assert _mcp(client, {}, "tools/list").status_code == 401
    names = {t["name"] for t in _mcp(client, h, "tools/list").json()["result"]["tools"]}
    assert {"search_exceptions", "get_exception", "propose_adjustment"} <= names
    r = _mcp(client, h, "tools/call", {"name": "search_exceptions",
                                       "arguments": {"limit": 3}}).json()["result"]
    assert not r.get("isError"), r
    assert len(json.loads(r["content"][0]["text"])["data"]["exceptions"]) == 3
    # the integration role cannot write: propose_adjustment is refused by policy
    w = _mcp(client, h, "tools/call", {"name": "propose_adjustment", "arguments": {
        "case_id": "case-x", "action": "rebill", "amount": 1.0, "reason": "should be refused"}})
    assert w.json()["result"]["isError"] is True
    # a human without mcp:invoke is refused as well
    a = _mcp(client, login("alice.analyst"), "tools/call",
             {"name": "search_exceptions", "arguments": {}}).json()["result"]
    assert a["isError"] is True


def test_lockout(client):
    for _ in range(5):
        client.post("/auth/token", data={"grant_type": "password", "username": "dana.auditor",
                                         "password": "nope-nope-nope"})
    r = client.post("/auth/token", data={"grant_type": "password", "username": "dana.auditor",
                                         "password": PASSWORD})
    assert r.status_code == 401
    db.execute("UPDATE users SET locked_until=0 WHERE username='dana.auditor'")
