"""Each test session gets its own data directory, database and signing key."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="ra-test-")
os.environ.update(RA_DATA_DIR=_tmp, RA_LLM_MODE="offline", RA_BASE_URL="http://testserver")
os.environ.pop("RA_OIDC_ISSUER", None)

import pytest
from fastapi.testclient import TestClient

PASSWORD = "test-only-" + os.urandom(6).hex()


@pytest.fixture(scope="session")
def client():
    from ra.api.app import app
    from ra.auth import idp
    with TestClient(app) as c:
        idp.seed_demo_users(PASSWORD)
        yield c


@pytest.fixture(scope="session")
def login(client):
    cache = {}

    def _login(username: str) -> dict:
        if username not in cache:
            r = client.post("/auth/token", data={"grant_type": "password", "username": username,
                                                 "password": PASSWORD})
            assert r.status_code == 200, r.text
            cache[username] = {"Authorization": "Bearer " + r.json()["access_token"]}
        return cache[username]
    return _login


@pytest.fixture(scope="session")
def run(client, login):
    r = client.post("/api/runs", json={"period": "2026-10", "accounts": 300},
                    headers=login("omar.operator"))
    assert r.status_code == 200, r.text
    return r.json()
