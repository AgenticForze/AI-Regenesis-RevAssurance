"""Agent2Agent (A2A) integration, protocol version 0.3, JSON-RPC binding.

Inbound : other agents discover this product at /.well-known/agent-card.json and call /a2a.
Outbound: the partner-variance skill calls a partner's settlement agent (ra.a2a.client).

Implemented: agent card, message/send, tasks/get, tasks/cancel. Not implemented: streaming,
push notifications and the 1.0 operation names; requests with `A2A-Version: 1.0` are refused.
"""
from __future__ import annotations

import uuid
from typing import Any

from ra import db

PROTOCOL_VERSION = "0.3.0"


def data_message(data: dict[str, Any], role: str = "user") -> dict[str, Any]:
    return {"kind": "message", "role": role, "messageId": uuid.uuid4().hex,
            "parts": [{"kind": "data", "data": data}]}


def task(task_id: str, context_id: str, state: str, data: dict[str, Any] | None = None,
         text: str | None = None, name: str = "result") -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "task", "id": task_id, "contextId": context_id,
                           "status": {"state": state, "timestamp": db.now()}}
    if text and data is None:
        out["status"]["message"] = {"kind": "message", "role": "agent",
                                    "messageId": uuid.uuid4().hex,
                                    "parts": [{"kind": "text", "text": text}]}
    if data is not None:
        parts = [{"kind": "data", "data": data}]
        if text:
            parts.insert(0, {"kind": "text", "text": text})
        out["artifacts"] = [{"artifactId": uuid.uuid4().hex, "name": name, "parts": parts}]
    return out


def first_data(message: dict[str, Any]) -> dict[str, Any]:
    for part in message.get("parts", []):
        if part.get("kind") == "data" and isinstance(part.get("data"), dict):
            return part["data"]
    return {}


def rpc_error(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
