"""JWT issue and verification.

Verification order:
1. If RA_OIDC_ISSUER is set, the token must be signed by that provider (Amazon Cognito,
   Microsoft Entra ID, Okta, Keycloak, ...). Keys come from its JWKS endpoint; issuer,
   audience, expiry and signature are all checked. Roles are read from RA_OIDC_ROLES_CLAIM
   (falls back to `cognito:groups` and `groups`).
2. Otherwise the built-in provider's RS256 key is used. The key pair is generated on first
   start and kept in the data directory with owner-only permissions.
"""
from __future__ import annotations

import os
import time
import uuid
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

from ra import db
from ra.auth import Principal
from ra.settings import get_settings

ALG = "RS256"
KID = "ra-local-1"


class AuthError(Exception):
    pass


@lru_cache(maxsize=1)
def _private_key():
    path = get_settings().data_dir / "idp_private_key.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    return key


def reset_keys() -> None:
    _private_key.cache_clear()
    _jwks_client.cache_clear()


def local_issuer() -> str:
    return get_settings().base_url.rstrip("/") + "/auth"


def jwks() -> dict[str, Any]:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_private_key().public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": KID, "use": "sig", "alg": ALG}]}


def issue(sub: str, kind: str, roles: list[str], bu_scope: list[str], approval_limit: float,
          ttl_s: int | None = None) -> dict[str, Any]:
    s = get_settings()
    now = int(time.time())
    ttl = ttl_s or s.token_ttl_s
    claims = {"iss": local_issuer(), "aud": s.oidc_audience, "sub": sub, "iat": now,
              "nbf": now, "exp": now + ttl, "jti": uuid.uuid4().hex, "kind": kind,
              "roles": roles, "bu_scope": bu_scope, "approval_limit": approval_limit}
    token = jwt.encode(claims, _private_key(), algorithm=ALG, headers={"kid": KID})
    return {"access_token": token, "token_type": "Bearer", "expires_in": ttl}


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    s = get_settings()
    url = s.oidc_jwks_url or s.oidc_issuer.rstrip("/") + "/.well-known/jwks.json"
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify(token: str) -> Principal:
    s = get_settings()
    try:
        if s.oidc_issuer:
            key = _jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256", "ES256"], issuer=s.oidc_issuer,
                                audience=s.oidc_audience,
                                options={"require": ["exp", "iss", "sub"]})
            return _external_principal(claims)
        claims = jwt.decode(token, _private_key().public_key(), algorithms=[ALG],
                            issuer=local_issuer(), audience=s.oidc_audience,
                            options={"require": ["exp", "iss", "sub", "aud"]})
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid token: {exc}") from exc
    # Built-in provider: re-check the account so a disabled user loses access immediately.
    table, col = ("users", "username") if claims["kind"] == "user" else ("clients", "client_id")
    row = db.one(f"SELECT disabled FROM {table} WHERE {col}=?", (claims["sub"],))
    if row is None or row["disabled"]:
        raise AuthError("account disabled or removed")
    return Principal(sub=claims["sub"], kind=claims["kind"], roles=tuple(claims["roles"]),
                     bu_scope=tuple(claims["bu_scope"]),
                     approval_limit=float(claims["approval_limit"]), claims=claims)


def _external_principal(claims: dict[str, Any]) -> Principal:
    s = get_settings()
    roles = claims.get(s.oidc_roles_claim) or claims.get("cognito:groups") or claims.get("groups")
    if isinstance(roles, str):
        roles = roles.split()
    is_client = claims.get("token_use") == "access" and "username" not in claims \
        and "client_id" in claims
    bu = claims.get("bu_scope") or claims.get("custom:bu_scope") or "*"
    bu_scope = tuple(bu.split(",")) if isinstance(bu, str) else tuple(bu)
    limit = float(claims.get("approval_limit") or claims.get("custom:approval_limit") or 0)
    return Principal(sub=claims["sub"], kind="service" if is_client else "user",
                     roles=tuple(roles or ()), bu_scope=bu_scope, approval_limit=limit,
                     claims=claims)
