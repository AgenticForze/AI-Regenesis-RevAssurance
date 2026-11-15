"""Tool registry. One definition serves three callers: the agents, the REST API and the MCP
server. Every call is authorized, validated, traced, counted and written to the audit trail."""
from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError, validate_call

from ra import audit
from ra.auth import Principal, current_principal
from ra.auth.policy import authorize
from ra.obs import metrics, span
from ra.shared.tool_base import ToolError


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., dict]
    permission: str
    write: bool

    @property
    def input_schema(self) -> dict[str, Any]:
        props, required = {}, []
        for pname, par in inspect.signature(self.fn).parameters.items():
            ann = getattr(par.annotation, "__name__", str(par.annotation))
            js = {"int": "integer", "float": "number", "bool": "boolean"}.get(ann, "string")
            props[pname] = {"type": js}
            if par.default is inspect.Parameter.empty:
                required.append(pname)
        return {"type": "object", "properties": props, "required": required}


REGISTRY: dict[str, Tool] = {}


def tool(name: str, permission: str = "tools:read", write: bool = False):
    def wrap(fn: Callable[..., dict]):
        REGISTRY[name] = Tool(name, inspect.getdoc(fn) or name, fn, permission, write)
        return fn
    return wrap


def invoke(principal: Principal, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run a tool as `principal`. Raises Forbidden, ToolError or ValueError."""
    if name not in REGISTRY:
        raise ToolError(f"unknown tool {name}")
    t = REGISTRY[name]
    authorize(principal, t.permission, resource_id=f"tool:{name}")
    token = current_principal.set(principal)
    t0 = time.perf_counter()
    outcome = "ok"
    try:
        with span(f"tool.{name}", **{"ra.tool": name, "ra.principal": principal.sub}):
            return validate_call(t.fn)(**args)
    except ValidationError as exc:
        outcome = "invalid"
        raise ValueError(f"invalid arguments for {name}: {exc.errors()[0]['msg']}") from exc
    except Exception:
        outcome = "error"
        raise
    finally:
        current_principal.reset(token)
        metrics.TOOL_CALLS.labels(tool=name, outcome=outcome).inc()
        metrics.TOOL_LATENCY.labels(tool=name).observe(time.perf_counter() - t0)
        audit.record(principal.sub, principal.kind, f"tool:{name}", str(args)[:200],
                     "info", {"outcome": outcome, "write": t.write})


def catalog(principal: Principal | None = None) -> list[dict[str, Any]]:
    from ra.auth.policy import decide
    return [{"name": t.name, "description": t.description, "write": t.write,
             "permission": t.permission, "input_schema": t.input_schema}
            for t in REGISTRY.values()
            if principal is None or decide(principal, t.permission).allow]
