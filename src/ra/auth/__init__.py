"""Authentication (who is calling) and authorization (what they may do).

- `tokens`  : verify bearer JWTs from an external OIDC provider, or from the built-in one.
- `idp`     : built-in identity provider for local and demo use (password + client credentials).
- `policy`  : role permissions plus attribute rules (business unit, approval limit, four-eyes).
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    sub: str
    kind: str = "user"                 # user | service | agent | partner
    roles: tuple[str, ...] = ()
    bu_scope: tuple[str, ...] = ("*",)  # business units this principal may see
    approval_limit: float = 0.0
    claims: dict = field(default_factory=dict, compare=False, hash=False)

    def sees_bu(self, bu: str | None) -> bool:
        return "*" in self.bu_scope or bu is None or bu in self.bu_scope


# The agent runtime acts under its own identity, never under the identity of the user who
# started the run. It has no approval permission by construction.
AGENT = Principal(sub="agent:ra-runtime", kind="agent", roles=("agent",))
SYSTEM = Principal(sub="system", kind="service", roles=("admin",))

current_principal: ContextVar[Principal | None] = ContextVar("current_principal", default=None)
