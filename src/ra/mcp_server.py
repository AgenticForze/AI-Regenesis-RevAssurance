"""MCP server: exposes the product's tools to MCP clients (Claude, IDEs, other agents).

Two transports:
- Streamable HTTP, mounted by the API at /mcp. Callers send the same bearer token as the REST
  API and need the `mcp:invoke` permission plus each tool's own permission.
- stdio, for local clients: `python -m ra.mcp_server` with RA_MCP_TOKEN set to a valid token.

The tools are the ones in ra.tools.registry, so MCP callers go through the same policy checks,
row limits and audit trail as the agents.
"""
from __future__ import annotations

import functools
import os
from urllib.parse import urlparse

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ra.auth import Principal, current_principal, tokens
from ra.auth.policy import authorize
from ra.settings import get_settings
from ra.tools import registry

INSTRUCTIONS = """Revenue Assurance tools. Start with search_exceptions, then get_exception.
Read tools return record_uids: cite them. propose_adjustment only creates a pending proposal;
a human approves it in the console. Amounts are in base currency; variance = expected - actual."""

_stdio_principal: Principal | None = None


def _bind(t: registry.Tool):
    @functools.wraps(t.fn)
    def wrapper(*args, **kwargs):
        p = current_principal.get() or _stdio_principal
        if p is None:
            raise PermissionError("not authenticated")
        authorize(p, "mcp:invoke", resource_id=f"mcp:{t.name}")
        return registry.invoke(p, t.name, kwargs)
    return wrapper


def build() -> MCPServer:
    server = MCPServer("revenue-assurance", instructions=INSTRUCTIONS)
    for t in registry.REGISTRY.values():
        server.add_tool(_bind(t), name=t.name, description=t.description)
    return server


def transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection: accept only the public host name and localhost."""
    host = urlparse(get_settings().base_url).netloc
    hosts = [host, "localhost:*", "127.0.0.1:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts,
        allowed_origins=[f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts])


class BearerAuth:
    """ASGI wrapper: verifies the bearer token and sets the calling principal."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        raw = headers.get(b"authorization", b"").decode()
        try:
            principal = tokens.verify(raw.removeprefix("Bearer ").strip())
        except tokens.AuthError:
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"www-authenticate", b"Bearer"),
                                    (b"content-type", b"application/json")]})
            return await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
        token = current_principal.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            current_principal.reset(token)


def main() -> None:
    global _stdio_principal
    from ra import obs
    obs.setup()
    _stdio_principal = tokens.verify(os.environ.get("RA_MCP_TOKEN", ""))
    build().run("stdio")


if __name__ == "__main__":
    main()
