"""Observability: OpenTelemetry traces, Prometheus metrics, JSON logs joined by trace ID."""
from __future__ import annotations

import json
import logging
import sys
import threading
from collections import deque
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

from ra.obs import metrics  # noqa: F401  (re-exported)
from ra.settings import get_settings


class RecentSpans(SpanExporter):
    """Keeps the last N finished spans in memory so the console can show a trace without an
    external backend. Production traces go to the OTLP endpoint as well."""

    def __init__(self, size: int = 2000):
        self._spans: deque[dict[str, Any]] = deque(maxlen=size)
        self._lock = threading.Lock()

    def export(self, spans: list[ReadableSpan]):  # type: ignore[override]
        with self._lock:
            for s in spans:
                ctx = s.get_span_context()
                self._spans.append({
                    "trace_id": f"{ctx.trace_id:032x}", "span_id": f"{ctx.span_id:016x}",
                    "parent_id": f"{s.parent.span_id:016x}" if s.parent else None,
                    "name": s.name, "start_ns": s.start_time,
                    "duration_ms": round((s.end_time - s.start_time) / 1e6, 2),
                    "status": s.status.status_code.name,
                    "attributes": {k: v for k, v in (s.attributes or {}).items()},
                })
        from opentelemetry.sdk.trace.export import SpanExportResult
        return SpanExportResult.SUCCESS

    def by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return sorted((s for s in self._spans if s["trace_id"] == trace_id),
                          key=lambda s: s["start_ns"])

    def recent_roots(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            roots = [s for s in self._spans if s["parent_id"] is None]
        return list(reversed(roots))[:limit]


recent = RecentSpans()
_configured = False


def setup() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    provider = TracerProvider(resource=Resource.create({
        "service.name": "revenue-assurance", "service.version": s.release,
        "deployment.environment": s.env}))
    provider.add_span_processor(SimpleSpanProcessor(recent))
    if s.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore", "mcp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


tracer = trace.get_tracer("ra")


@contextmanager
def span(name: str, **attrs: Any):
    """Start a span; attributes with value None are skipped."""
    with tracer.start_as_current_span(name) as sp:
        for k, v in attrs.items():
            if v is not None:
                sp.set_attribute(k, v)
        yield sp


def current_trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return f"{ctx.trace_id:032x}" if ctx.trace_id else ""


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name,
               "msg": record.getMessage(), "trace_id": current_trace_id()}
        out.update(getattr(record, "fields", {}))
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def log(name: str, msg: str, **fields: Any) -> None:
    logging.getLogger(name).info(msg, extra={"fields": fields})
