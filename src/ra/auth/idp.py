"""Built-in identity provider for local, demo and test use.

Passwords and client secrets are stored as salted scrypt hashes. Five failed logins lock the
account for five minutes. For production, point RA_OIDC_ISSUER at your identity provider and
this module's token endpoint is disabled.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from ra import audit, db
from ra.auth import tokens
from ra.auth.policy import ROLE_PERMISSIONS
from ra.obs import metrics
from ra.settings import get_settings

_N, _R, _P = 2**14, 8, 1


def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(secret.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def check_secret(secret: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
    except ValueError:
        return False
    dk = hashlib.scrypt(secret.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return hmac.compare_digest(dk, expected)


def _check_roles(roles: list[str]) -> None:
    unknown = set(roles) - ROLE_PERMISSIONS.keys()
    if unknown:
        raise ValueError(f"unknown roles: {sorted(unknown)}")


def create_user(username: str, password: str, roles: list[str], bu_scope: list[str] | None = None,
                approval_limit: float = 0.0) -> None:
    _check_roles(roles)
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    db.execute("INSERT OR REPLACE INTO users (username,pw_hash,roles,bu_scope,approval_limit) "
               "VALUES (?,?,?,?,?)",
               (username, hash_secret(password), db.json.dumps(roles),
                db.json.dumps(bu_scope or ["*"]), approval_limit))


def create_client(client_id: str, roles: list[str], kind: str = "service") -> str:
    """Register a machine client and return its secret (shown once)."""
    _check_roles(roles)
    secret = secrets.token_urlsafe(32)
    db.execute("INSERT OR REPLACE INTO clients (client_id,secret_hash,roles,kind) VALUES (?,?,?,?)",
               (client_id, hash_secret(secret), db.json.dumps(roles), kind))
    return secret


class LoginFailed(Exception):
    pass


def password_grant(username: str, password: str) -> dict[str, Any]:
    s = get_settings()
    user = db.one("SELECT * FROM users WHERE username=?", (username,))
    now = time.time()
    if user and user["locked_until"] > now:
        _fail(username, "locked")
    # Hash even for unknown users so response time does not reveal which names exist.
    ok = check_secret(password, user["pw_hash"] if user else hash_secret("x" * 12))
    if not user or user["disabled"] or not ok:
        if user:
            failures = user["failures"] + 1
            locked = now + s.lockout_s if failures >= s.max_login_failures else 0
            db.execute("UPDATE users SET failures=?, locked_until=? WHERE username=?",
                       (0 if locked else failures, locked, username))
        _fail(username, "bad_credentials")
    db.execute("UPDATE users SET failures=0, locked_until=0 WHERE username=?", (username,))
    metrics.AUTH_EVENTS.labels(event="login_ok").inc()
    audit.record(username, "user", "auth:login", "idp", "allow")
    return tokens.issue(username, "user", user["roles"], user["bu_scope"], user["approval_limit"])


def client_credentials_grant(client_id: str, client_secret: str) -> dict[str, Any]:
    client = db.one("SELECT * FROM clients WHERE client_id=?", (client_id,))
    ok = check_secret(client_secret, client["secret_hash"] if client else hash_secret("x" * 12))
    if not client or client["disabled"] or not ok:
        _fail(client_id, "bad_client_credentials")
    metrics.AUTH_EVENTS.labels(event="client_ok").inc()
    audit.record(client_id, client["kind"], "auth:client_credentials", "idp", "allow")
    return tokens.issue(client_id, client["kind"], client["roles"], ["*"], 0.0)


def _fail(subject: str, reason: str) -> None:
    metrics.AUTH_EVENTS.labels(event=reason).inc()
    audit.record(subject, "unknown", "auth:login", "idp", "deny", {"reason": reason})
    raise LoginFailed("invalid credentials")  # same message for every cause


def seed_demo_users(password: str) -> list[dict[str, Any]]:
    """Create one user per role for demos. The password comes from the caller, never the repo."""
    demo = [
        ("alice.analyst", ["analyst"], ["*"], 0),
        ("ed.enterprise", ["analyst"], ["enterprise"], 0),
        ("bob.approver", ["approver"], ["*"], 10_000),
        ("carol.controller", ["approver"], ["*"], 250_000),
        ("dana.auditor", ["auditor"], ["*"], 0),
        ("omar.operator", ["operator"], ["*"], 0),
        ("root.admin", ["admin"], ["*"], 1_000_000),
    ]
    for name, roles, bu, limit in demo:
        create_user(name, password, roles, bu, limit)
    return [{"username": n, "roles": r, "bu_scope": b, "approval_limit": lim}
            for n, r, b, lim in demo]
