from pathlib import Path

import pytest

from ailab.model_gateway import BudgetExceeded, GatewayRequest, NoHealthyModel, demo_gateway


def test_balanced_routes_to_free_local_and_records_usage(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    response = gateway.complete(GatewayRequest("tenant-a", "Summarize this short request", request_id="r1"))
    assert response.model == "small-local"
    assert response.cost_usd == 0
    assert len(gateway.inspect()["usage"]) == 1


def test_complex_quality_request_routes_to_large_model(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    response = gateway.complete(GatewayRequest("tenant-a", "Analyze architecture tradeoffs and failure modes", quality="high"))
    assert response.model == "large-hosted"


def test_privacy_local_never_uses_hosted_model(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    response = gateway.complete(GatewayRequest("tenant-a", "Analyze private architecture", quality="high", privacy="local"))
    assert response.provider == "local"


def test_fallback_after_primary_failure(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db", {"large-hosted": 1})
    response = gateway.complete(GatewayRequest("tenant-a", "Analyze architecture tradeoffs", quality="high"))
    assert response.model == "medium-hosted"
    assert response.fallback_count == 1


def test_circuit_opens_and_removes_failed_model(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db", {"large-hosted": 2, "medium-hosted": 2, "small-local": 2})
    with pytest.raises(NoHealthyModel):
        gateway.complete(GatewayRequest("a", "Analyze architecture", quality="high", request_id="one"))
    with pytest.raises(NoHealthyModel):
        gateway.complete(GatewayRequest("a", "Analyze a different architecture", quality="high", request_id="two"))
    with pytest.raises(NoHealthyModel, match="no model satisfies"):
        gateway.complete(GatewayRequest("a", "Analyze a third architecture", quality="high"))


def test_budget_cap_rejects_request(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    with pytest.raises(BudgetExceeded, match="actual request cost"):
        gateway.complete(GatewayRequest("tenant-a", "Analyze architecture", quality="high", max_cost_usd=0.000001))


def test_exact_cache_is_tenant_isolated(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    first = gateway.complete(GatewayRequest("tenant-a", "same prompt"))
    cached = gateway.complete(GatewayRequest("tenant-a", "same prompt"))
    other_tenant = gateway.complete(GatewayRequest("tenant-b", "same prompt"))
    assert not first.cached and cached.cached and not other_tenant.cached


def test_request_id_is_idempotent(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    first = gateway.complete(GatewayRequest("tenant-a", "hello", request_id="stable"))
    repeated = gateway.complete(GatewayRequest("tenant-a", "hello", request_id="stable"))
    assert repeated.cached and repeated.text == first.text
    assert len(gateway.inspect()["usage"]) == 1


def test_shadow_result_is_recorded_but_not_charged(tmp_path: Path) -> None:
    gateway = demo_gateway(tmp_path / "gateway.db")
    gateway.complete(GatewayRequest("tenant-a", "short"), shadow_model="medium-hosted")
    data = gateway.inspect()
    assert len(data["usage"]) == 1 and len(data["shadows"]) == 1
