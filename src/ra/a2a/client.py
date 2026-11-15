"""A2A client used to call partner agents."""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

import httpx

from ra import a2a, audit
from ra.auth import current_principal
from ra.obs import metrics, span
from ra.settings import get_settings


class A2AError(Exception):
    pass


class A2AClient:
    def __init__(self, base_url: str, token: str = "", http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.http = http or httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0))
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._card: dict[str, Any] | None = None

    def card(self) -> dict[str, Any]:
        if self._card is None:
            r = self.http.get(f"{self.base_url}/.well-known/agent-card.json")
            r.raise_for_status()
            self._card = r.json()
        return self._card

    def send(self, data: dict[str, Any]) -> dict[str, Any]:
        """Send one data message and return the resulting task."""
        card = self.card()
        skills = {s["id"] for s in card.get("skills", [])}
        if data.get("skill") not in skills:
            raise A2AError(f"partner agent does not offer skill {data.get('skill')}")
        p = current_principal.get()
        with span("a2a.send", **{"a2a.agent": card.get("name"), "a2a.skill": data.get("skill")}):
            try:
                r = self.http.post(card.get("url") or f"{self.base_url}/a2a", headers=self.headers,
                                   json={"jsonrpc": "2.0", "id": uuid.uuid4().hex,
                                         "method": "message/send",
                                         "params": {"message": a2a.data_message(data)}})
                r.raise_for_status()
                body = r.json()
            except httpx.HTTPError as err:
                metrics.A2A_CALLS.labels(direction="outbound", outcome="error").inc()
                raise A2AError(f"partner agent unreachable: {err}") from err
        if "error" in body:
            metrics.A2A_CALLS.labels(direction="outbound", outcome="rpc_error").inc()
            raise A2AError(body["error"].get("message", "A2A error"))
        metrics.A2A_CALLS.labels(direction="outbound", outcome="ok").inc()
        audit.record(p.sub if p else "system", p.kind if p else "service", "a2a:outbound",
                     card.get("name", self.base_url), "info",
                     {"skill": data.get("skill"), "task_id": body["result"].get("id"),
                      "shared_fields": sorted(data)})
        return body["result"]


@lru_cache(maxsize=1)
def partner_client() -> A2AClient:
    """Client for the partner settlement agent. Without RA_PARTNER_A2A_URL the bundled mock
    partner is called in-process, which keeps demos and tests self-contained."""
    s = get_settings()
    if s.partner_a2a_url:
        return A2AClient(s.partner_a2a_url, s.partner_a2a_token)
    from starlette.testclient import TestClient

    from ra.a2a.mock_partner import app
    return A2AClient("http://partner.local", http=TestClient(app, base_url="http://partner.local"))
