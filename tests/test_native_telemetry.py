import pytest
pytest.importorskip("opentelemetry.sdk")
pytest.importorskip("prometheus_client")
from ailab.native_telemetry import NativeTelemetry

def test_native_otel_and_prometheus():
    telemetry=NativeTelemetry("gateway")
    with telemetry.operation("complete"): telemetry.record_request(True,.01)
    assert telemetry.exporter.get_finished_spans()[0].name == "complete"
    assert 'ai_requests_total{service="gateway",status="ok"} 1.0' in telemetry.prometheus_text()
