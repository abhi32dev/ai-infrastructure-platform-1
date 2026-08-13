from __future__ import annotations
from contextlib import contextmanager
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

class NativeTelemetry:
    def __init__(self, service: str) -> None:
        self.exporter = InMemorySpanExporter(); provider = TracerProvider(); provider.add_span_processor(SimpleSpanProcessor(self.exporter)); self.tracer = provider.get_tracer(service)
        self.registry = CollectorRegistry(); self.requests = Counter("ai_requests_total", "AI requests", ("service", "status"), registry=self.registry); self.latency = Histogram("ai_request_latency_seconds", "AI request latency", ("service",), registry=self.registry); self.service = service
    @contextmanager
    def operation(self, name: str):
        with self.tracer.start_as_current_span(name) as span: yield span
    def record_request(self, success: bool, latency_seconds: float) -> None:
        self.requests.labels(self.service, "ok" if success else "error").inc(); self.latency.labels(self.service).observe(latency_seconds)
    def prometheus_text(self) -> str: return generate_latest(self.registry).decode()
