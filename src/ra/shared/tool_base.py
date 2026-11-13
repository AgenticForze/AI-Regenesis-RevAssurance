"""Base class for Gateway tools: typed errors, row limits, record IDs in every result."""
from __future__ import annotations


class ToolError(Exception):
    code = "ERROR"


class NotFound(ToolError):
    code = "NOT_FOUND"


class Ambiguous(ToolError):
    code = "AMBIGUOUS"


class TooManyRows(ToolError):
    code = "TOO_MANY_ROWS"


def result(payload: dict, record_uids: list[str], as_of: str | None = None) -> dict:
    """Every tool result carries the record IDs it read, so answers stay traceable."""
    return {"data": payload, "record_uids": record_uids, "as_of": as_of}
