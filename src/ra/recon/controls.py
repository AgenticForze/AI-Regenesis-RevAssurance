"""The nine deterministic controls. No model is involved here: a control either matches two
sides within tolerance or raises an exception with the records that prove the break.

variance = expected - actual, in base currency. Positive means under-billed (leakage);
negative means over-billed (customer credit due).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator
from typing import Any

from ra.recon.generator import USAGE

TOLERANCE = 0.50
CONTROLS = {
    "C1": "Usage completeness: mediation vs rating",
    "C2": "Rated vs billed usage",
    "C3": "Provisioned vs billed services",
    "C4": "Contract discount compliance",
    "C5": "Tariff compliance of rated usage",
    "C6": "Billed vs cash collected",
    "C7": "Billing vs general ledger",
    "C8": "Partner settlement",
    "C9": "Duplicate charges",
}


class Book:
    """Records of one run, indexed by source and account."""

    def __init__(self, records: list[dict[str, Any]]):
        self.by: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for r in records:
            self.by[r["source"]][r["account_id"]].append(r)
        self.contracts = {a: rs[0] for a, rs in self.by["S5"].items()}
        self.accounts = sorted(self.contracts)

    def lines(self, account: str) -> list[dict]:
        return self.by["S3"].get(account, []) + self.by["S4"].get(account, [])

    def unique_lines(self, account: str) -> list[dict]:
        seen, out = set(), []
        for ln in self.lines(account):
            key = (ln["service_id"], ln["product_code"], ln["attrs"]["line_type"])
            if key not in seen:
                seen.add(key)
                out.append(ln)
        return out

    def bu(self, account: str) -> str:
        return self.contracts[account]["attrs"]["bu"]


def _exc(control: str, account: str, expected: float, actual: float, summary: str,
         records: list[dict], **features: Any) -> dict[str, Any]:
    return {"control": control, "account_id": account, "expected": round(expected, 2),
            "actual": round(actual, 2), "variance": round(expected - actual, 2),
            "summary": summary, "record_uids": [r["uid"] for r in records], "features": features}


def c1(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        rated = {r["product_code"]: r for r in b.by["S2"].get(acct, [])}
        for u in b.by["S1"].get(acct, []):
            r = rated.get(u["product_code"])
            price = USAGE[u["product_code"]]
            r_qty = r["qty"] if r else 0.0
            if abs(u["qty"] - r_qty) * price > TOLERANCE:
                yield _exc("C1", acct, u["qty"] * price, r_qty * price,
                           f"{u['product_code']}: mediation {u['qty']} vs rated {r_qty}",
                           [u] + ([r] if r else []), product=u["product_code"],
                           usage_qty=u["qty"], rated_qty=r_qty,
                           feed_complete=u["attrs"]["feed_complete"])


def c2(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        billed = {ln["product_code"]: ln for ln in b.unique_lines(acct)
                  if ln["attrs"]["line_type"] == "usage"}
        for r in b.by["S2"].get(acct, []):
            ln = billed.get(r["product_code"])
            gross = ln["attrs"]["gross"] if ln else 0.0
            if abs(r["amount"] - gross) > TOLERANCE:
                yield _exc("C2", acct, r["amount"], gross,
                           f"{r['product_code']}: rated {r['amount']} vs billed gross {gross}",
                           [r] + ([ln] if ln else []), product=r["product_code"],
                           billed_share=round(gross / r["amount"], 3) if r["amount"] else 0)


def c3(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        rec = [ln for ln in b.unique_lines(acct) if ln["attrs"]["line_type"] == "recurring"]
        disc = b.contracts[acct]["attrs"]["discount_pct"]
        for svc in b.by["S6"].get(acct, []):
            line = next((ln for ln in rec if ln["service_id"] == svc["service_id"]), None)
            active = svc["attrs"]["status"] == "active"
            if active and line is None:
                yield _exc("C3", acct, svc["amount"] * (1 - disc / 100), 0.0,
                           f"service {svc['service_id']} active but no recurring charge",
                           [svc], service_status="active", has_charge=False)
            elif not active and line is not None:
                yield _exc("C3", acct, 0.0, line["amount"],
                           f"service {svc['service_id']} ceased but still charged",
                           [svc, line], service_status="ceased", has_charge=True)


def c4(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        agreed = b.contracts[acct]["attrs"]["discount_pct"]
        lines = b.unique_lines(acct)
        off = [ln for ln in lines if abs(ln["attrs"]["discount_pct"] - agreed) > 0.01]
        if off:
            gross = sum(ln["attrs"]["gross"] for ln in off)
            applied = off[0]["attrs"]["discount_pct"]
            diff = gross * (applied - agreed) / 100
            if abs(diff) > TOLERANCE:
                net = sum(ln["amount"] for ln in off)
                yield _exc("C4", acct, net + diff, net,
                           f"discount applied {applied}% vs contract {agreed}%",
                           [b.contracts[acct], *off], agreed_pct=agreed, applied_pct=applied)


def c5(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        for r in b.by["S2"].get(acct, []):
            expected = r["qty"] * USAGE[r["product_code"]]
            if abs(expected - r["amount"]) > TOLERANCE:
                yield _exc("C5", acct, expected, r["amount"],
                           f"{r['product_code']}: rated {r['amount']} vs tariff {expected:.2f}",
                           [r], product=r["product_code"],
                           tariff_version=r["attrs"]["tariff_version"],
                           effective_unit_price=round(r["amount"] / r["qty"], 4))


def _billed(b: Book, acct: str) -> float:
    return sum(ln["amount"] for ln in b.lines(acct))


def c6(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        billed = _billed(b, acct)
        for p in b.by["S8"].get(acct, []):
            if abs(billed - p["amount"]) > TOLERANCE:
                yield _exc("C6", acct, billed, p["amount"],
                           f"invoice {p['attrs']['invoice_id']}: billed {billed:.2f}, "
                           f"collected {p['amount']}", [p], payment_status=p["attrs"]["status"],
                           expected_days=p["attrs"]["expected_days"])


def c7(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        billed = _billed(b, acct)
        for g in b.by["S9"].get(acct, []):
            if abs(billed - g["amount"]) > TOLERANCE:
                yield _exc("C7", acct, billed, g["amount"],
                           f"billed {billed:.2f} vs ledger {g['amount']}", [g],
                           posting_period=g["attrs"]["posting_period"], period=g["period"],
                           deferred_amount=g["attrs"]["deferred_amount"])


def c8(b: Book) -> Iterator[dict]:
    for acct, stmts in b.by["S10"].items():
        rated = b.by["S2"].get(acct, [])
        ours = sum(r["amount"] for r in rated)
        for st in stmts:
            if abs(ours - st["amount"]) > TOLERANCE:
                yield _exc("C8", acct, ours, st["amount"],
                           f"our rated usage {ours:.2f} vs partner statement {st['amount']}",
                           [st, *rated], partner_id=st["attrs"]["partner_id"],
                           days_reported=st["attrs"]["days_reported"])


def c9(b: Book) -> Iterator[dict]:
    for acct in b.accounts:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for ln in b.lines(acct):
            groups[(ln["service_id"], ln["product_code"], ln["attrs"]["line_type"],
                    ln["attrs"]["invoice_id"])].append(ln)
        for lines in groups.values():
            if len(lines) > 1:
                yield _exc("C9", acct, lines[0]["amount"], sum(ln["amount"] for ln in lines),
                           f"{len(lines)} identical lines on {lines[0]['attrs']['invoice_id']}",
                           lines, copies=len(lines), product=lines[0]["product_code"])


ALL: dict[str, Callable[[Book], Iterator[dict]]] = {
    "C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7, "C8": c8, "C9": c9}


def severity(variance: float) -> str:
    v = abs(variance)
    return "S1" if v >= 25000 else "S2" if v >= 5000 else "S3" if v >= 500 else "S4"
