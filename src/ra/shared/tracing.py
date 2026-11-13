"""Trace-context helpers (ra-tracing). Every hop carries case_id and traceparent."""
from __future__ import annotations


def message_attributes(case_id: str, traceparent: str) -> dict:
    return {
        "case_id": {"DataType": "String", "StringValue": case_id},
        "traceparent": {"DataType": "String", "StringValue": traceparent},
    }
