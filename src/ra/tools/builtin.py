"""Built-in tools. Read tools return the record IDs they used; the only write tool is
`propose_adjustment`, which creates a pending proposal that a human must approve."""
from __future__ import annotations

from typing import Any

from ra import db
from ra.auth import current_principal
from ra.auth.policy import Forbidden
from ra.shared.tool_base import NotFound, TooManyRows, result
from ra.tools.get_tariff import get_tariff as _get_tariff
from ra.tools.registry import tool

MAX_ROWS = 200


def latest_run() -> str:
    row = db.one("SELECT id FROM runs ORDER BY started DESC LIMIT 1")
    if not row:
        raise NotFound("no reconciliation run yet")
    return row["id"]


def _check_account(account_id: str, run_id: str) -> str:
    """Return the account's business unit after checking the caller may see it."""
    c = db.one("SELECT attrs FROM records WHERE run_id=? AND source='S5' AND account_id=?",
               (run_id, account_id))
    if not c:
        raise NotFound(f"unknown account {account_id}")
    p = current_principal.get()
    if p and not p.sees_bu(c["attrs"]["bu"]):
        raise Forbidden(f"business unit {c['attrs']['bu']} is outside the caller's scope")
    return c["attrs"]["bu"]


def _records(account_id: str, sources: tuple[str, ...]) -> dict[str, Any]:
    run_id = latest_run()
    _check_account(account_id, run_id)
    marks = ",".join("?" * len(sources))
    rows = db.query(f"SELECT uid,source,kind,service_id,product_code,period,qty,amount,currency,"
                    f"attrs FROM records WHERE run_id=? AND account_id=? AND source IN ({marks})",
                    (run_id, account_id, *sources))
    if len(rows) > MAX_ROWS:
        raise TooManyRows(f"{len(rows)} rows; narrow the request")
    return result({"account_id": account_id, "rows": rows}, [r["uid"] for r in rows])


@tool("get_usage")
def get_usage(account_id: str) -> dict:
    """Mediation usage (S1) for an account in the latest run."""
    return _records(account_id, ("S1",))


@tool("get_rated_usage")
def get_rated_usage(account_id: str) -> dict:
    """Rated usage (S2) for an account, with the tariff version used."""
    return _records(account_id, ("S2",))


@tool("get_invoice_lines")
def get_invoice_lines(account_id: str) -> dict:
    """Invoice lines from billing systems S3 and S4 for an account."""
    return _records(account_id, ("S3", "S4"))


@tool("get_contract")
def get_contract(account_id: str) -> dict:
    """CRM contract terms (S5): business unit and agreed discount."""
    return _records(account_id, ("S5",))


@tool("get_services")
def get_services(account_id: str) -> dict:
    """Provisioned services (S6) and their status."""
    return _records(account_id, ("S6",))


@tool("get_payments")
def get_payments(account_id: str) -> dict:
    """Payments received (S8) against the account's invoices."""
    return _records(account_id, ("S8",))


@tool("get_ledger_postings")
def get_ledger_postings(account_id: str) -> dict:
    """ERP general-ledger revenue postings (S9) for an account."""
    return _records(account_id, ("S9",))


@tool("get_tariff")
def get_tariff(product_code: str, as_of: str) -> dict:
    """Catalog tariff (S7) in force for a product on a date (YYYY-MM-DD)."""
    rows = db.query("SELECT uid,product_code,amount,attrs FROM records WHERE run_id=? AND "
                    "source='S7'", (latest_run(),))
    catalog = [{"record_uid": r["uid"], "product_code": r["product_code"],
                "unit_price": r["amount"], **r["attrs"]} for r in rows]
    return _get_tariff(product_code, as_of, catalog)


@tool("search_exceptions", permission="exceptions:read")
def search_exceptions(status: str = "", control: str = "", min_variance: float = 0.0,
                      limit: int = 20) -> dict:
    """Find exceptions in the latest run by status, control and minimum absolute variance."""
    p = current_principal.get()
    sql = "SELECT id,control,account_id,bu,variance,severity,status,root_cause,summary " \
          "FROM exceptions WHERE run_id=? AND ABS(variance)>=?"
    params: list[Any] = [latest_run(), min_variance]
    for col, val in (("status", status), ("control", control)):
        if val:
            sql += f" AND {col}=?"
            params.append(val)
    rows = [r for r in db.query(sql + " ORDER BY ABS(variance) DESC", params)
            if not p or p.sees_bu(r["bu"])][:min(max(limit, 1), MAX_ROWS)]
    return result({"exceptions": rows}, [r["id"] for r in rows])


@tool("get_exception", permission="exceptions:read")
def get_exception(exception_id: str) -> dict:
    """One exception with its triage result and evidence record IDs."""
    row = db.one("SELECT * FROM exceptions WHERE id=?", (exception_id,))
    if not row:
        raise NotFound(f"unknown exception {exception_id}")
    p = current_principal.get()
    if p and not p.sees_bu(row["bu"]):
        raise Forbidden("business unit is outside the caller's scope")
    row.pop("truth", None)   # ground truth is for evaluation only
    return result(row, row["record_uids"])


@tool("query_partner_statement", permission="a2a:call")
def query_partner_statement(account_id: str) -> dict:
    """Ask the partner's settlement agent (A2A) for the detail behind its statement."""
    from ra.a2a.client import partner_client
    run = db.one("SELECT period FROM runs WHERE id=?", (latest_run(),))
    _check_account(account_id, latest_run())
    task = partner_client().send({"skill": "statement-detail", "account_id": account_id,
                                  "period": run["period"]})
    data = next((p["data"] for a in task.get("artifacts", []) for p in a["parts"]
                 if p.get("kind") == "data"), None)
    if task["status"]["state"] != "completed" or data is None:
        raise NotFound(f"partner agent returned {task['status']['state']}")
    return result({**data, "a2a_task_id": task["id"]}, data.get("record_uids", []))


@tool("propose_adjustment", permission="adjustments:propose", write=True)
def propose_adjustment(case_id: str, action: str, amount: float, reason: str) -> dict:
    """Create a PENDING adjustment for a case. Nothing is posted until a human approves it."""
    from ra import cases
    p = current_principal.get()
    adj = cases.propose(case_id, action, amount, reason, p)
    return result(adj, [adj["id"]])


@tool("get_before_after_report", permission="reports:read")
def get_before_after_report() -> dict:
    """Before/after comparison: manual baseline vs this product, for the latest run."""
    from ra.reporting import before_after
    return result(before_after(latest_run()), [])
