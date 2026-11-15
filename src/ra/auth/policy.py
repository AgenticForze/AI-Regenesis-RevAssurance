"""Authorization policy: RBAC for the coarse decision, attribute rules for the fine one.

Every deny, and every allow on a state-changing action, is written to the audit trail.
The policy is default-deny: an action missing from every role is refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ra import audit
from ra.auth import Principal
from ra.obs import metrics

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"exceptions:read", "cases:read", "reports:read"},
    "analyst": {"exceptions:read", "cases:read", "cases:work", "adjustments:read",
                "adjustments:propose", "reports:read", "tools:read", "runs:read"},
    "approver": {"exceptions:read", "cases:read", "adjustments:read", "adjustments:approve",
                 "reports:read", "runs:read"},
    "auditor": {"exceptions:read", "cases:read", "adjustments:read", "reports:read",
                "audit:read", "audit:verify", "runs:read", "obs:read"},
    "operator": {"runs:execute", "runs:read", "plugins:read", "plugins:dispatch", "obs:read",
                 "exceptions:read", "reports:read"},
    "admin": {"*"},
    # Non-human principals
    "agent": {"exceptions:read", "cases:read", "cases:work", "tools:read",
              "adjustments:propose", "a2a:call"},
    "integration": {"exceptions:read", "cases:read", "tools:read", "mcp:invoke", "a2a:invoke",
                    "reports:read"},
    "partner": {"a2a:invoke"},
}
WRITE_ACTIONS = {"cases:work", "adjustments:propose", "adjustments:approve", "runs:execute",
                 "plugins:dispatch", "admin:users", "a2a:invoke"}
# No role assignment can give these to a non-human principal.
HUMAN_ONLY = {"adjustments:approve", "admin:users"}


@dataclass
class Decision:
    allow: bool
    reason: str


class Forbidden(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def permissions(p: Principal) -> set[str]:
    out: set[str] = set()
    for role in p.roles:
        out |= ROLE_PERMISSIONS.get(role, set())
    return out


def decide(p: Principal, action: str, resource: dict[str, Any] | None = None) -> Decision:
    resource = resource or {}
    perms = permissions(p)
    if action in HUMAN_ONLY and p.kind != "user":
        return Decision(False, f"{action} requires a human principal")
    if "*" not in perms and action not in perms:
        return Decision(False, f"missing permission {action}")
    if "bu" in resource and not p.sees_bu(resource["bu"]):
        return Decision(False, f"business unit {resource['bu']} is outside the caller's scope")
    if action == "adjustments:approve":
        if resource.get("proposed_by") == p.sub:
            return Decision(False, "four-eyes rule: the proposer cannot approve")
        if abs(resource.get("amount", 0.0)) > p.approval_limit:
            return Decision(False, f"amount exceeds approval limit {p.approval_limit:.0f}")
    return Decision(True, "ok")


def authorize(p: Principal, action: str, resource: dict[str, Any] | None = None,
              resource_id: str = "") -> None:
    """Raise Forbidden unless the policy allows the action. Audits per the module docstring."""
    d = decide(p, action, resource)
    metrics.AUTHZ_DECISIONS.labels(action=action, decision="allow" if d.allow else "deny").inc()
    if not d.allow:
        audit.record(p.sub, p.kind, f"authz:{action}", resource_id, "deny", {"reason": d.reason})
        raise Forbidden(d.reason)
    if action in WRITE_ACTIONS:
        audit.record(p.sub, p.kind, f"authz:{action}", resource_id, "allow")
