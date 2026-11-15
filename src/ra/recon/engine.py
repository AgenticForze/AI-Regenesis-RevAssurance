"""One reconciliation run: load records, run the nine controls, triage every exception, and
investigate the ones that qualify."""
from __future__ import annotations

from collections import Counter
from typing import Any

from ra import audit, cases, db, plugins
from ra.agents import runtime
from ra.auth import AGENT, Principal
from ra.auth.policy import authorize
from ra.obs import log, metrics, span
from ra.recon import controls, generator


def _load_from_sources(run_id: str, period: str) -> int:
    rows, n = [], 0
    for plugin, _ in plugins.instances():
        if isinstance(plugin, plugins.SourcePlugin):
            for r in plugin.fetch(period):
                n += 1
                rows.append((f"{run_id}:{r['source']}:{n:07d}", run_id, r["source"], r["kind"],
                             r["account_id"], r.get("service_id"), r.get("product_code"), period,
                             r.get("qty", 0), r.get("amount", 0), r.get("currency", "USD"),
                             db.json.dumps(r.get("attrs", {}))))
    db.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return n


def run(actor: Principal, period: str, accounts: int = 400, seed: int = 7,
        data: str = "synthetic", auto_investigate: bool = True) -> dict[str, Any]:
    authorize(actor, "runs:execute", resource_id=f"run:{period}")
    run_id = db.new_id("run")
    db.insert("runs", {"id": run_id, "period": period, "started": db.now(), "finished": None,
                       "started_by": actor.sub, "stats": {}})
    with span("recon.run", **{"ra.run_id": run_id, "ra.period": period, "ra.data": data}):
        truth: dict[str, list[str]] = {}
        with span("recon.load"):
            if data == "synthetic":
                gen = generator.generate(run_id, period, accounts, seed)
                truth = gen["truth"]
            else:
                _load_from_sources(run_id, period)
            records = db.query("SELECT * FROM records WHERE run_id=?", (run_id,))
        for src, n in Counter(r["source"] for r in records).items():
            metrics.RECORDS_RECONCILED.labels(source=src).inc(n)

        with span("recon.controls"):
            book = controls.Book(records)
            found: list[dict[str, Any]] = []
            for fn in controls.ALL.values():
                found.extend(fn(book))
        flagged = {uid for e in found for uid in e["record_uids"]}

        routes: Counter[str] = Counter()
        investigated = 0
        to_investigate: list[str] = []
        with span("recon.triage", **{"ra.exceptions": len(found)}):
            for e in found:
                exc = {"id": db.new_id("exc"), "run_id": run_id, **e, "bu": book.bu(e["account_id"]),
                       "period": period, "currency": "USD",
                       "severity": controls.severity(e["variance"]), "status": "open",
                       "root_cause": None, "action": None, "confidence": None, "rationale": None,
                       "truth": truth.get(e["account_id"], []), "created": db.now()}
                t = runtime.triage(exc)
                exc.update(root_cause=t["root_cause"], action=t["action"],
                           confidence=t["confidence"], rationale=t["rationale"],
                           status={"monitor": "monitor", "queue": "triaged",
                                   "investigate": "triaged"}[t["route"]])
                db.insert("exceptions", exc)
                metrics.EXCEPTIONS.labels(control=exc["control"], severity=exc["severity"]).inc()
                routes[t["route"]] += 1
                if t["route"] == "investigate":
                    to_investigate.append(exc["id"])
        if auto_investigate:
            for exc_id in to_investigate:
                cases.investigate(exc_id, AGENT)
                investigated += 1

        stats = {"records": len(records), "accounts": len(book.accounts),
                 "exceptions": len(found), "records_flagged": len(flagged),
                 "match_rate": round(1 - len(flagged) / max(len(records), 1), 4),
                 "routes": dict(routes), "investigated": investigated,
                 "by_control": dict(Counter(e["control"] for e in found)),
                 "data": data, "seed": seed}
        db.update("runs", "id", run_id, {"finished": db.now(), "stats": stats})
    audit.record(actor.sub, actor.kind, "run:completed", run_id, "info",
                 {k: stats[k] for k in ("records", "exceptions", "match_rate")})
    plugins.emit("run.completed", run_id, {"id": run_id, "period": period, **stats})
    plugins.dispatch()
    log("ra.recon", "run completed", run_id=run_id, **stats)
    return {"id": run_id, "period": period, "stats": stats}
