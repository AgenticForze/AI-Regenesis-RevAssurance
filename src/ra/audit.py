"""Tamper-evident audit trail.

Every event stores the hash of the previous event, so editing or deleting any row breaks the
chain and `verify()` reports the first broken sequence number. In AWS the same events are also
shipped to an S3 Object Lock bucket in the Log Archive account (docs/product/auditing.md).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ra import db
from ra.obs import current_trace_id, metrics

GENESIS = "0" * 64


def _digest(prev: str, body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


def record(actor: str, actor_type: str, action: str, resource: str, decision: str = "allow",
           detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one event. `decision` is allow, deny, or info."""
    with db._lock:
        last = db.one("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1")
        prev = last["hash"] if last else GENESIS
        body = {"ts": db.now(), "actor": actor, "actor_type": actor_type, "action": action,
                "resource": resource, "decision": decision, "detail": detail or {},
                "trace_id": current_trace_id()}
        row = {**body, "prev_hash": prev, "hash": _digest(prev, body)}
        db.insert("audit", row)
    metrics.AUDIT_EVENTS.labels(action=action, decision=decision).inc()
    return row


def verify() -> dict[str, Any]:
    """Recompute the whole chain. Returns ok=False and the first bad sequence on tampering."""
    prev = GENESIS
    count = 0
    for row in db.query("SELECT * FROM audit ORDER BY seq"):
        body = {k: row[k] for k in ("ts", "actor", "actor_type", "action", "resource",
                                    "decision", "detail", "trace_id")}
        if row["prev_hash"] != prev or row["hash"] != _digest(prev, body):
            return {"ok": False, "events": count, "first_bad_seq": row["seq"]}
        prev = row["hash"]
        count += 1
    return {"ok": True, "events": count, "head": prev}


def search(actor: str | None = None, action: str | None = None, resource: str | None = None,
           decision: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM audit WHERE 1=1", []
    for col, val in (("actor", actor), ("decision", decision)):
        if val:
            sql += f" AND {col}=?"
            params.append(val)
    for col, val in (("action", action), ("resource", resource)):
        if val:
            sql += f" AND {col} LIKE ?"
            params.append(f"%{val}%")
    return db.query(sql + " ORDER BY seq DESC LIMIT ?", [*params, min(limit, 1000)])
