"""Example plug-in: post product events to a Microsoft Teams channel webhook.

Install with `pip install -e plugins/ra-plugin-example`, then add to config/plugins.yaml:

    - name: teams-approvals
      type: teams
      events: [adjustment.proposed]
      dry_run: true
      config: {webhook_url_env: RA_TEAMS_WEBHOOK_URL}
"""
from __future__ import annotations

from typing import Any

import httpx

from ra.plugins import SinkPlugin


class TeamsNotifier(SinkPlugin):
    type = "teams"

    def deliver(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"text": f"Revenue Assurance: {event} {payload.get('id', '')} "
                        f"({payload.get('amount', payload.get('variance', ''))} "
                        f"{payload.get('currency', '')})"}
        if self.dry_run:
            return {"dry_run": True, "body": body}
        resp = httpx.post(self.secret("webhook_url_env"), json=body, timeout=10.0)
        resp.raise_for_status()   # raising makes the outbox retry
        return {"status": resp.status_code}
