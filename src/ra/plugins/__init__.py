"""Plug-in framework for external systems.

Two kinds of plug-in:
- SinkPlugin   : receives product events (case opened, adjustment approved, ...) and delivers
                 them to an external system such as Jira, ServiceNow, Slack or the ERP.
- SourcePlugin : pulls records from a source system into a reconciliation run.

Delivery uses a transactional outbox: `emit` writes one row per subscribed plug-in with an
idempotency key, and `dispatch` delivers with retries. An event is never lost if the external
system is down, and never sent twice for the same key.

Third-party plug-ins register through the Python entry-point group `ra.plugins`
(see plugins/ra-plugin-example).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from functools import lru_cache
from importlib.metadata import entry_points
from typing import Any

import yaml

from ra import audit, db
from ra.obs import log, metrics, span
from ra.settings import get_settings

EVENTS = ("run.completed", "case.opened", "adjustment.proposed", "adjustment.approved",
          "adjustment.rejected")
MAX_ATTEMPTS = 5


class Plugin(ABC):
    type: str = ""

    def __init__(self, name: str, config: dict[str, Any], dry_run: bool = True):
        self.name, self.config, self.dry_run = name, config, dry_run

    def secret(self, key: str) -> str:
        """Secrets are referenced by environment variable name, never stored in config."""
        var = self.config.get(key, "")
        val = os.environ.get(var, "") if var else ""
        if not val and not self.dry_run:
            raise RuntimeError(f"{self.name}: environment variable for '{key}' is not set")
        return val


class SinkPlugin(Plugin):
    @abstractmethod
    def deliver(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one event. Return a reference from the external system. Raise to retry."""


class SourcePlugin(Plugin):
    @abstractmethod
    def fetch(self, period: str) -> Iterable[dict[str, Any]]:
        """Yield records: source, kind, account_id, service_id, product_code, qty, amount, attrs."""


@lru_cache(maxsize=1)
def types() -> dict[str, type[Plugin]]:
    from ra.plugins import builtin
    found: dict[str, type[Plugin]] = dict(builtin.BUILTIN)
    for ep in entry_points(group="ra.plugins"):
        found[ep.name] = ep.load()
    return found


@lru_cache(maxsize=1)
def instances() -> list[tuple[Plugin, tuple[str, ...]]]:
    path = get_settings().plugins_config
    if not path.exists():
        return []
    out = []
    for item in (yaml.safe_load(path.read_text()) or {}).get("plugins", []):
        if not item.get("enabled", True):
            continue
        cls = types().get(item["type"])
        if cls is None:
            raise ValueError(f"unknown plug-in type {item['type']}")
        out.append((cls(item["name"], item.get("config", {}), item.get("dry_run", True)),
                    tuple(item.get("events", []))))
    return out


def reload() -> None:
    types.cache_clear()
    instances.cache_clear()


def describe() -> list[dict[str, Any]]:
    return [{"name": p.name, "type": p.type, "dry_run": p.dry_run, "events": list(ev),
             "kind": "source" if isinstance(p, SourcePlugin) else "sink"}
            for p, ev in instances()]


def emit(event: str, resource_id: str, payload: dict[str, Any]) -> int:
    """Queue an event for every subscribed sink. Returns the number of rows queued."""
    queued = 0
    for plugin, events in instances():
        if isinstance(plugin, SinkPlugin) and event in events:
            key = f"{plugin.name}:{event}:{resource_id}"
            cur = db.execute(
                "INSERT OR IGNORE INTO outbox (id,plugin,event,payload,idem_key,status,created) "
                "VALUES (?,?,?,?,?,?,?)",
                (db.new_id("out"), plugin.name, event, db.json.dumps(payload), key, "pending",
                 db.now()))
            queued += cur.rowcount
    return queued


def dispatch(limit: int = 200) -> dict[str, int]:
    """Deliver pending outbox rows. Safe to call from any worker, any number of times."""
    by_name = {p.name: p for p, _ in instances()}
    stats = {"delivered": 0, "failed": 0, "dead": 0}
    for row in db.query("SELECT * FROM outbox WHERE status IN ('pending','failed') "
                        "ORDER BY created LIMIT ?", (limit,)):
        plugin = by_name.get(row["plugin"])
        attempts = row["attempts"] + 1
        try:
            if plugin is None:
                raise RuntimeError("plug-in no longer configured")
            with span("plugin.deliver", **{"ra.plugin": row["plugin"], "ra.event": row["event"]}):
                result = plugin.deliver(row["event"], row["payload"])  # type: ignore[union-attr]
            db.update("outbox", "id", row["id"],
                      {"status": "delivered", "attempts": attempts, "result": result})
            stats["delivered"] += 1
            metrics.OUTBOX.labels(plugin=row["plugin"], outcome="delivered").inc()
            audit.record("system", "service", f"plugin:{row['plugin']}", row["idem_key"], "info",
                         {"event": row["event"], "dry_run": getattr(plugin, "dry_run", None)})
        except Exception as err:  # noqa: BLE001
            status = "dead" if attempts >= MAX_ATTEMPTS else "failed"
            db.update("outbox", "id", row["id"],
                      {"status": status, "attempts": attempts, "last_error": str(err)[:300]})
            stats[status] += 1
            metrics.OUTBOX.labels(plugin=row["plugin"], outcome=status).inc()
            log("ra.plugins", "delivery failed", plugin=row["plugin"], error=str(err)[:200])
    return stats
