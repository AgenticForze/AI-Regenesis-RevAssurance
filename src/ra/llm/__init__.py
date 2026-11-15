"""Single entry point for model calls: budget check, tracing, token and cost accounting.

Two back ends implement `complete_json`:
- `OfflineReasoner` (default): deterministic rules, so the product runs with no cloud account.
- `BedrockClient`: Amazon Bedrock Converse API (set RA_LLM_MODE=bedrock and the model IDs).
Agents never call a back end directly; they call `ra.llm.call`.
"""
from __future__ import annotations

import json
import time
from typing import Any, Protocol

from ra import db
from ra.obs import metrics, span
from ra.settings import get_settings
from ra.shared.budgets import CaseBudget

# Illustrative USD prices per million tokens (input, output). Replace with your contract rates.
PRICES = {"triage": (1.0, 5.0), "investigate": (3.0, 15.0)}
MAX_OUTPUT = {"triage": 600, "investigate": 1200}


class Backend(Protocol):
    name: str

    def complete_json(self, step: str, system: str, payload: dict[str, Any]) -> tuple[dict, int, int]:
        """Return (parsed JSON answer, input tokens, output tokens)."""


_backend: Backend | None = None


def backend() -> Backend:
    global _backend
    if _backend is None:
        if get_settings().llm_mode == "bedrock":
            from ra.llm.bedrock import BedrockClient
            _backend = BedrockClient()
        else:
            from ra.llm.offline import OfflineReasoner
            _backend = OfflineReasoner()
    return _backend


def set_backend(b: Backend | None) -> None:
    global _backend
    _backend = b


def estimate_tokens(obj: Any) -> int:
    return max(1, len(obj if isinstance(obj, str) else json.dumps(obj, default=str)) // 4)


def call(step: str, system: str, payload: dict[str, Any], case_ref: str,
         budget: CaseBudget | None = None) -> dict[str, Any]:
    b = backend()
    budget = budget or CaseBudget(max_input_tokens=get_settings().case_token_budget)
    budget.reserve(estimate_tokens(system) + estimate_tokens(payload), MAX_OUTPUT[step])
    with span(f"llm.{step}", **{"gen_ai.operation.name": "chat", "gen_ai.system": b.name,
                                "ra.case_ref": case_ref, "ra.step": step}) as sp:
        t0 = time.perf_counter()
        answer, tin, tout = b.complete_json(step, system, payload)
        ms = (time.perf_counter() - t0) * 1000
        pin, pout = PRICES[step]
        cost = (tin * pin + tout * pout) / 1e6
        sp.set_attribute("gen_ai.usage.input_tokens", tin)
        sp.set_attribute("gen_ai.usage.output_tokens", tout)
        sp.set_attribute("ra.cost_usd", round(cost, 6))
    budget.record(tin, tout)
    metrics.LLM_TOKENS.labels(step=step, direction="input").inc(tin)
    metrics.LLM_TOKENS.labels(step=step, direction="output").inc(tout)
    metrics.LLM_COST.labels(step=step).inc(cost)
    db.insert("llm_calls", {"id": db.new_id("llm"), "ts": db.now(), "case_ref": case_ref,
                            "step": step, "model": b.name, "input_tokens": tin,
                            "output_tokens": tout, "cost_usd": cost, "latency_ms": ms})
    return answer
