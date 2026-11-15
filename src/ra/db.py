"""Storage layer. SQLite for the single-node reference deployment; every statement is plain
SQL so the same schema runs on PostgreSQL/Aurora (see docs/product/deployment.md)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from ra.settings import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY, pw_hash TEXT NOT NULL, roles TEXT NOT NULL, bu_scope TEXT NOT NULL,
  approval_limit REAL NOT NULL DEFAULT 0, disabled INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS clients (
  client_id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, roles TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'service', disabled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, period TEXT, started TEXT, finished TEXT, started_by TEXT, stats TEXT);
CREATE TABLE IF NOT EXISTS records (
  uid TEXT PRIMARY KEY, run_id TEXT, source TEXT, kind TEXT, account_id TEXT, service_id TEXT,
  product_code TEXT, period TEXT, qty REAL, amount REAL, currency TEXT, attrs TEXT);
CREATE INDEX IF NOT EXISTS ix_records ON records(run_id, source, account_id);
CREATE TABLE IF NOT EXISTS exceptions (
  id TEXT PRIMARY KEY, run_id TEXT, control TEXT, account_id TEXT, bu TEXT, period TEXT,
  expected REAL, actual REAL, variance REAL, currency TEXT, severity TEXT, status TEXT,
  root_cause TEXT, action TEXT, confidence REAL, rationale TEXT, summary TEXT, features TEXT,
  record_uids TEXT, truth TEXT, created TEXT);
CREATE INDEX IF NOT EXISTS ix_exc ON exceptions(run_id, status);
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, exception_id TEXT UNIQUE, status TEXT, assignee TEXT, skill TEXT,
  findings TEXT, verification TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS adjustments (
  id TEXT PRIMARY KEY, case_id TEXT, exception_id TEXT, action TEXT, amount REAL, currency TEXT,
  bu TEXT, status TEXT, proposed_by TEXT, decided_by TEXT, reason TEXT, before_amount REAL,
  after_amount REAL, posting_ref TEXT, created TEXT, decided TEXT);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, actor_type TEXT, action TEXT,
  resource TEXT, decision TEXT, detail TEXT, trace_id TEXT, prev_hash TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY, plugin TEXT, event TEXT, payload TEXT, idem_key TEXT UNIQUE,
  status TEXT, attempts INTEGER DEFAULT 0, last_error TEXT, result TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS a2a_tasks (
  id TEXT PRIMARY KEY, context_id TEXT, state TEXT, caller TEXT, request TEXT, result TEXT,
  created TEXT);
CREATE TABLE IF NOT EXISTS llm_calls (
  id TEXT PRIMARY KEY, ts TEXT, case_ref TEXT, step TEXT, model TEXT, input_tokens INTEGER,
  output_tokens INTEGER, cost_usd REAL, latency_ms REAL);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
        return _conn


def reset() -> None:
    """Close the connection (tests point RA_DB_PATH at a fresh file)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


def execute(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur


def executemany(sql: str, rows: list[tuple]) -> None:
    with _lock:
        conn().executemany(sql, rows)
        conn().commit()


_JSON_COLS = {"roles", "bu_scope", "stats", "attrs", "record_uids", "truth", "findings",
              "verification", "detail", "payload", "result", "request", "features"}


def _row(r: sqlite3.Row) -> dict[str, Any]:
    out = dict(r)
    for k in _JSON_COLS & out.keys():
        if isinstance(out[k], str) and out[k]:
            try:
                out[k] = json.loads(out[k])
            except ValueError:
                pass
    return out


def query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    with _lock:
        return [_row(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def insert(table: str, row: dict[str, Any]) -> None:
    cols = list(row)
    vals = [json.dumps(v) if isinstance(v, dict | list) else v for v in row.values()]
    execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


def update(table: str, key: str, key_val: str, changes: dict[str, Any]) -> None:
    sets = ",".join(f"{c}=?" for c in changes)
    vals = [json.dumps(v) if isinstance(v, dict | list) else v for v in changes.values()]
    execute(f"UPDATE {table} SET {sets} WHERE {key}=?", [*vals, key_val])
