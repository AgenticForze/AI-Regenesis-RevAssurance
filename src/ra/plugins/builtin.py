"""Built-in connectors. Each one is small on purpose: map an event to the external system's
request, send it, return the reference. With dry_run on (the default) the request is built and
returned but nothing leaves the process, so configuration can be reviewed safely.

These connectors follow each vendor's public REST conventions but have only been run in
dry-run mode here; test against your own instance before switching dry_run off.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

from ra.plugins import Plugin, SinkPlugin, SourcePlugin
from ra.settings import get_settings

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _title(event: str, p: dict[str, Any]) -> str:
    amount = p.get("amount", p.get("variance"))
    money = f" {amount:,.2f} {p.get('currency', 'USD')}" if amount is not None else ""
    return f"[Revenue Assurance] {event} {p.get('id', '')} account {p.get('account_id', '-')}{money}"


class _Http(SinkPlugin):
    def _send(self, url: str, body: dict[str, Any], headers: dict[str, str] | None = None,
              auth: tuple[str, str] | None = None) -> dict[str, Any]:
        if self.dry_run:
            return {"dry_run": True, "url": url, "body": body}
        resp = httpx.post(url, json=body, headers=headers, auth=auth, timeout=TIMEOUT)
        resp.raise_for_status()
        try:
            return {"status": resp.status_code, "response": resp.json()}
        except ValueError:
            return {"status": resp.status_code}


class Webhook(_Http):
    """Generic signed webhook. The receiver checks X-RA-Signature (HMAC-SHA256 of the body)."""
    type = "webhook"

    def deliver(self, event, payload):
        body = {"event": event, "data": payload}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        sig = hmac.new(self.secret("secret_env").encode(), raw, hashlib.sha256).hexdigest()
        return self._send(self.config["url"], body, {"X-RA-Signature": f"sha256={sig}"})


class Slack(_Http):
    """Slack incoming webhook; the webhook URL itself is the secret."""
    type = "slack"

    def deliver(self, event, payload):
        url = self.secret("webhook_url_env") or "https://hooks.slack.com/services/<not-set>"
        return self._send(url, {"text": _title(event, payload)})


class Jira(_Http):
    """Creates a Jira issue per event (REST API v2, basic auth with an API token)."""
    type = "jira"

    def deliver(self, event, payload):
        body = {"fields": {"project": {"key": self.config["project"]},
                           "issuetype": {"name": self.config.get("issue_type", "Task")},
                           "summary": _title(event, payload)[:250],
                           "description": json.dumps(payload, indent=2, default=str)[:30000],
                           "labels": ["revenue-assurance", event.replace(".", "-")]}}
        return self._send(self.config["base_url"].rstrip("/") + "/rest/api/2/issue", body,
                          auth=(self.config.get("user", ""), self.secret("token_env")))


class ServiceNow(_Http):
    """Creates a record through the ServiceNow Table API."""
    type = "servicenow"

    def deliver(self, event, payload):
        table = self.config.get("table", "incident")
        body = {"short_description": _title(event, payload)[:160],
                "description": json.dumps(payload, indent=2, default=str),
                "category": "Revenue Assurance", "correlation_id": payload.get("id", "")}
        return self._send(f"{self.config['instance_url'].rstrip('/')}/api/now/table/{table}",
                          body, auth=(self.config.get("user", ""), self.secret("password_env")))


class LedgerJournalFile(SinkPlugin):
    """Posts approved adjustments as journal lines to a CSV file drop that the ERP (S9) picks
    up. Two balanced lines per adjustment: receivable against revenue."""
    type = "ledger_journal_file"

    def deliver(self, event, payload):
        ref = f"RAJ-{payload['id']}"
        amount = round(float(payload["amount"]), 2)
        lines = [[ref, payload["account_id"], self.config.get("receivable_account", "120000"),
                  amount, payload["currency"], payload["action"]],
                 [ref, payload["account_id"], self.config.get("revenue_account", "400100"),
                  -amount, payload["currency"], payload["action"]]]
        if self.dry_run:
            return {"dry_run": True, "posting_ref": ref, "lines": lines}
        out = Path(self.config.get("directory") or get_settings().data_dir / "journal")
        out.mkdir(parents=True, exist_ok=True)
        with (out / f"{ref}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["journal_ref", "customer", "gl_account", "amount", "currency", "text"])
            w.writerows(lines)
        return {"posting_ref": ref, "file": str(out / f"{ref}.csv")}


class CsvSource(SourcePlugin):
    """Reads one source system's extract from CSV. Columns: account_id, service_id,
    product_code, qty, amount, then any extra columns, which become record attributes."""
    type = "csv_source"
    CORE = ("account_id", "service_id", "product_code", "qty", "amount")

    def fetch(self, period: str) -> Iterable[dict[str, Any]]:
        path = Path(self.config["path"].format(period=period))
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                attrs = {k: _coerce(v) for k, v in row.items() if k not in self.CORE}
                yield {"source": self.config["source"], "kind": self.config["kind"],
                       "account_id": row["account_id"], "service_id": row.get("service_id") or None,
                       "product_code": row.get("product_code") or None,
                       "qty": float(row.get("qty") or 0), "amount": float(row.get("amount") or 0),
                       "attrs": attrs}


def _coerce(v: str) -> Any:
    if v in ("true", "false"):
        return v == "true"
    if v == "":
        return None
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


BUILTIN: dict[str, type[Plugin]] = {c.type: c for c in (
    Webhook, Slack, Jira, ServiceNow, LedgerJournalFile, CsvSource)}
