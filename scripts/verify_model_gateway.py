#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ailab.model_gateway import BudgetExceeded, GatewayRequest, NoHealthyModel, demo_gateway  # noqa: E402


def run(name: str, category: str, operation: Callable[[], dict]) -> dict:
    started = time.perf_counter()
    try:
        return {"name": name, "category": category, "status": "passed", "duration_ms": round((time.perf_counter()-started)*1000, 3), "evidence": operation()}
    except Exception as exc:
        return {"name": name, "category": category, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="gateway-verification-") as directory:
        root = Path(directory)
        def routes() -> dict:
            gateway = demo_gateway(root / "routes.db")
            balanced = gateway.complete(GatewayRequest("a", "short request"))
            quality = gateway.complete(GatewayRequest("a", "Analyze architecture failure tradeoffs", quality="high"))
            private = gateway.complete(GatewayRequest("a", "Analyze confidential architecture", quality="high", privacy="local"))
            assert balanced.model == "small-local" and quality.model == "large-hosted" and private.provider == "local"
            return {"balanced": balanced.model, "quality": quality.model, "private": private.model}
        results.append(run("policy_routing", "happy_path", routes))

        def fallback() -> dict:
            gateway = demo_gateway(root / "fallback.db", {"large-hosted": 1})
            response = gateway.complete(GatewayRequest("a", "Analyze architecture", quality="high"))
            assert response.fallback_count == 1
            return response.__dict__
        results.append(run("provider_failure_fallback", "failure_recovery", fallback))

        def cache() -> dict:
            gateway = demo_gateway(root / "cache.db")
            gateway.complete(GatewayRequest("a", "same"))
            hit = gateway.complete(GatewayRequest("a", "same"))
            isolated = gateway.complete(GatewayRequest("b", "same"))
            assert hit.cached and not isolated.cached
            return {"same_tenant_cached": hit.cached, "other_tenant_cached": isolated.cached}
        results.append(run("tenant_isolated_cache", "security", cache))

        def budget() -> dict:
            gateway = demo_gateway(root / "budget.db")
            try:
                gateway.complete(GatewayRequest("a", "Analyze architecture", quality="high", max_cost_usd=0.000001))
            except BudgetExceeded as exc:
                return {"expected_error": str(exc)}
            raise AssertionError("cost cap was not enforced")
        results.append(run("request_cost_cap", "negative", budget))

        def circuits() -> dict:
            gateway = demo_gateway(root / "circuit.db", {"large-hosted": 2, "medium-hosted": 2, "small-local": 2})
            for request_id in ("one", "two"):
                try: gateway.complete(GatewayRequest("a", f"Analyze architecture {request_id}", request_id=request_id, quality="high"))
                except NoHealthyModel: pass
            try: gateway.complete(GatewayRequest("a", "Analyze architecture three", quality="high"))
            except NoHealthyModel as exc:
                health = gateway.inspect()["health"]
                assert len(health) == 3 and all(row["failures"] == 2 for row in health)
                return {"expected_error": str(exc), "health": health}
            raise AssertionError("open circuits accepted traffic")
        results.append(run("circuit_breaker", "failure_recovery", circuits))

    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_model_gateway.py"], cwd=ROOT, text=True, capture_output=True)
    results.append({"name":"project_3_test_suite","category":"tests","status":"passed" if tests.returncode == 0 else "failed","stdout":tests.stdout.strip(),"stderr":tests.stderr.strip()})
    passed=sum(item["status"]=="passed" for item in results)
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"git_commit":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True).stdout.strip(),"summary":{"total":len(results),"passed":passed,"failed":len(results)-passed},"scenarios":results}
    target=ROOT/"artifacts"/"project-3-model-gateway"; target.mkdir(parents=True,exist_ok=True)
    (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=[f"Project 3 verification: {passed}/{len(results)} passed",*[f"[{x['status'].upper()}] {x['category']}: {x['name']}" for x in results]]
    (target/"latest.txt").write_text("\n".join(lines)+"\n"); print("\n".join(lines))
    return 0 if passed==len(results) else 1

if __name__ == "__main__": raise SystemExit(main())

