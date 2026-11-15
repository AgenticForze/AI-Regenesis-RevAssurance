"""Synthetic data for the ten source systems, with known faults injected.

This is test data, not customer data: it lets the product run end to end on a laptop and
gives every exception a ground-truth root cause to score triage against. Real deployments
replace it with source plug-ins (see `ra.plugins`).
"""
from __future__ import annotations

import random
from typing import Any

from ra import db

SOURCES = {
    "S1": "Mediation (usage)", "S2": "Rating", "S3": "Billing A (consumer)",
    "S4": "Billing B (enterprise, wholesale)", "S5": "CRM contracts", "S6": "Orders and services",
    "S7": "Product catalog", "S8": "Payments", "S9": "ERP general ledger",
    "S10": "Partner settlement",
}
USAGE = {"VOICE-MIN": 0.05, "DATA-GB": 2.00, "ROAM-GB": 8.00}
OLD_PRICE = {"VOICE-MIN": 0.04, "DATA-GB": 1.60, "ROAM-GB": 6.50}   # tariff v1, superseded
PLANS = {"consumer": ("PLAN-M", 35.0), "enterprise": ("ENT-LINK", 900.0),
         "wholesale": ("WHS-ACCESS", 2500.0)}
# fault -> (ground-truth root cause, share of accounts)
FAULTS = {
    "missing_usage_rating": ("RC03_missing_usage", 0.020),
    "missing_usage_billing": ("RC03_missing_usage", 0.015),
    "stale_tariff": ("RC02_price_book_mismatch", 0.015),
    "rating_error": ("RC01_rating_error", 0.010),
    "duplicate_line": ("RC04_duplicate_billing", 0.010),
    "provisioned_not_billed": ("RC05_provisioned_not_billed", 0.015),
    "billed_not_provisioned": ("RC06_billed_not_provisioned", 0.010),
    "discount_too_high": ("RC07_discount_misapplied", 0.015),
    "gl_posting_error": ("RC13_ledger_posting_error", 0.010),
    "gl_timing": ("RC10_timing_cutoff", 0.010),
    "late_payment": ("RC10_timing_cutoff", 0.015),
    "late_feed": ("RC14_data_quality_false_break", 0.010),
    "partner_short": ("RC11_partner_variance", 0.0),   # applied to wholesale accounts only
}


def generate(run_id: str, period: str, accounts: int = 400, seed: int = 7) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{period}")
    rows: list[tuple] = []
    truth: dict[str, list[str]] = {}
    n = 0

    def add(source: str, kind: str, account: str, service: str | None, product: str | None,
            qty: float, amount: float, **attrs: Any) -> str:
        nonlocal n
        n += 1
        uid = f"{run_id}:{source}:{n:07d}"
        rows.append((uid, run_id, source, kind, account, service, product, period,
                     round(qty, 4), round(amount, 2), "USD", db.json.dumps(attrs)))
        return uid

    for code, price in USAGE.items():
        add("S7", "tariff", "-", None, code, 0, price, version="v2",
            effective_from=f"{period[:4]}-01-01", effective_to=None)
        add("S7", "tariff", "-", None, code, 0, OLD_PRICE[code], version="v1",
            effective_from="2020-01-01", effective_to=f"{int(period[:4]) - 1}-12-31")
    for (code, mrc) in PLANS.values():
        add("S7", "tariff", "-", None, code, 0, mrc, version="v2",
            effective_from=f"{period[:4]}-01-01", effective_to=None)

    fault_names = [f for f, (_, share) in FAULTS.items() if share > 0]
    weights = [FAULTS[f][1] for f in fault_names]
    for i in range(accounts):
        acct = f"ACC-{i + 1:05d}"
        bu = rng.choices(["consumer", "enterprise", "wholesale"], [0.80, 0.17, 0.03])[0]
        billing = "S3" if bu == "consumer" else "S4"
        fault = None
        if rng.random() < sum(weights):
            fault = rng.choices(fault_names, weights)[0]
        if bu == "wholesale" and rng.random() < 0.5:
            fault = "partner_short"
        if fault:
            truth[acct] = [fault, FAULTS[fault][0]]

        discount = 0.0 if bu == "consumer" else rng.choice([5.0, 10.0, 15.0, 20.0])
        add("S5", "contract", acct, None, None, 0, 0, bu=bu, discount_pct=discount,
            contract_id=f"CT-{i + 1:05d}")
        svc = f"SVC-{i + 1:05d}-1"
        plan, mrc = PLANS[bu]
        ceased = fault == "billed_not_provisioned"
        add("S6", "service", acct, svc, plan, 1, mrc, status="ceased" if ceased else "active",
            ceased_on=f"{period}-01" if ceased else None)

        scale = {"consumer": 1, "enterprise": 40, "wholesale": 400}[bu]
        billed_disc = discount + (10.0 if fault == "discount_too_high" else 0.0)
        invoice_id = f"INV-{period}-{i + 1:05d}"
        net_total = 0.0
        products = ["ROAM-GB"] if bu == "wholesale" else rng.sample(list(USAGE), k=2)
        rated_total = 0.0
        for product in products:
            price = USAGE[product]
            qty = round(rng.uniform(20, 400) * scale / (price * 10), 2)
            add("S1", "usage", acct, svc, product, qty * (0.7 if fault == "late_feed" else 1.0),
                0, feed_complete=fault != "late_feed")
            rated_qty = qty * (0.82 if fault == "missing_usage_rating" else 1.0)
            version, unit = "v2", price
            if fault == "stale_tariff":
                version, unit = "v1", OLD_PRICE[product]
            rated_amt = rated_qty * unit * (0.9 if fault == "rating_error" else 1.0)
            add("S2", "rated", acct, svc, product, rated_qty, rated_amt, tariff_version=version)
            rated_total += rated_amt
            gross = rated_amt * (0.75 if fault == "missing_usage_billing" else 1.0)
            net = gross * (1 - billed_disc / 100)
            for _ in range(2 if fault == "duplicate_line" and product == products[0] else 1):
                add(billing, "invoice_line", acct, svc, product, rated_qty, net,
                    line_type="usage", gross=round(gross, 2), discount_pct=billed_disc,
                    invoice_id=invoice_id)
                net_total += net
        if fault != "provisioned_not_billed":
            net = mrc * (1 - billed_disc / 100)
            add(billing, "invoice_line", acct, svc, plan, 1, net, line_type="recurring",
                gross=mrc, discount_pct=billed_disc, invoice_id=invoice_id)
            net_total += net

        late = fault == "late_payment"
        add("S8", "payment", acct, None, None, 0, 0 if late else net_total,
            invoice_id=invoice_id, status="pending" if late else "settled",
            expected_days=3 if late else 0)
        gl = net_total * (0.9 if fault == "gl_posting_error" else 1.0)
        add("S9", "gl_posting", acct, None, None, 0, 0 if fault == "gl_timing" else gl,
            gl_account="400100", posting_period=_next(period) if fault == "gl_timing" else period,
            deferred_amount=round(gl, 2) if fault == "gl_timing" else 0)
        if bu == "wholesale":
            short = 0.88 if fault == "partner_short" else 1.0
            add("S10", "partner_statement", acct, None, "ROAM-GB", 0, rated_total * short,
                partner_id=f"PRT-{i + 1:05d}", days_reported=27 if short < 1 else 31)

    db.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return {"records": len(rows), "accounts": accounts, "faults_injected": len(truth),
            "truth": truth}


def _next(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    return f"{y + (m == 12)}-{m % 12 + 1:02d}"
