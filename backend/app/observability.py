import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

request_id_context = ContextVar("harvestguard_request_id", default="-")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        span = trace.get_current_span()
        context = span.get_span_context()
        trace_id = format(context.trace_id, "032x") if context.is_valid else "-"
        span_id = format(context.span_id, "016x") if context.is_valid else "-"

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
            "trace_id": trace_id,
            "span_id": span_id,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "")
        # Do not accept arbitrary long or control-character identifiers.
        if (
            not supplied_id
            or len(supplied_id) > 100
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in supplied_id)
        ):
            supplied_id = str(uuid.uuid4())

        token = request_id_context.set(supplied_id)
        started = time.perf_counter()
        logger = logging.getLogger("harvestguard.http")

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info("http_request_received method=%s path=%s", request.method, request.url.path)
            response.headers["X-Request-ID"] = supplied_id
            logger.info(
                "request_completed method=%s path=%s status=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            logger.exception(
                "request_failed method=%s path=%s",
                request.method,
                request.url.path,
            )
            raise
        finally:
            request_id_context.reset(token)

def install_observability(app):
    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # Replace handlers only once; avoid duplicate JSON lines on reload.
    if not getattr(root, "_harvestguard_json_configured", False):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers.clear()
        root.addHandler(handler)
        root._harvestguard_json_configured = True

    app.add_middleware(RequestCorrelationMiddleware)

    # Export traces only when an OTLP endpoint is configured.
    # No endpoint means local instrumentation without external transmission.
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if endpoint:
        provider = TracerProvider(
            resource=Resource.create({
                "service.name": os.getenv(
                    "OTEL_SERVICE_NAME", "harvestguard-api"
                )
            })
        )
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
