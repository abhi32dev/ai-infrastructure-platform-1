from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .text import content_tokens, tokenize


class GatewayError(RuntimeError): pass
class BudgetExceeded(GatewayError): pass
class NoHealthyModel(GatewayError): pass


@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    input_cost_per_million: float
    output_cost_per_million: float
    max_context: int
    quality_tier: int
    latency_tier: int


@dataclass(frozen=True)
class GatewayRequest:
    tenant: str
    prompt: str
    request_id: str = ""
    quality: str = "balanced"
    privacy: str = "any"
    max_cost_usd: float | None = None


@dataclass(frozen=True)
class ProviderResult:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class GatewayResponse:
    request_id: str
    model: str
    provider: str
    text: str
    cost_usd: float
    cached: bool
    route_reason: str
    fallback_count: int


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Callable[[str, str], ProviderResult]] = {}

    def register(self, name: str, handler: Callable[[str, str], ProviderResult]) -> None:
        self._providers[name] = handler

    def call(self, provider: str, model: str, prompt: str) -> ProviderResult:
        if provider not in self._providers:
            raise GatewayError(f"provider is not registered: {provider}")
        return self._providers[provider](model, prompt)


class ModelGateway:
    def __init__(self, database: Path, models: list[ModelConfig], providers: ProviderRegistry, tenant_daily_budget: float = 1.0, failure_threshold: int = 2, cooldown_seconds: float = 30.0) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self._lock = threading.RLock()
        self.connection.row_factory = sqlite3.Row
        self.models = {model.name: model for model in models}
        self.providers = providers
        self.tenant_daily_budget = tenant_daily_budget
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS usage(request_id TEXT PRIMARY KEY, tenant TEXT, model TEXT, provider TEXT, response TEXT, input_tokens INTEGER, output_tokens INTEGER, cost REAL, created_at REAL);
        CREATE TABLE IF NOT EXISTS cache(cache_key TEXT PRIMARY KEY, response TEXT, model TEXT, provider TEXT, cost REAL, created_at REAL);
        CREATE TABLE IF NOT EXISTS health(model TEXT PRIMARY KEY, failures INTEGER, opened_at REAL);
        CREATE TABLE IF NOT EXISTS decisions(request_id TEXT PRIMARY KEY, tenant TEXT, selected_model TEXT, reason TEXT, candidates TEXT, fallback_count INTEGER, created_at REAL);
        CREATE TABLE IF NOT EXISTS shadows(request_id TEXT, model TEXT, status TEXT, latency_ms REAL, error TEXT, created_at REAL);
        """)
        self.connection.commit()

    def close(self) -> None: self.connection.close()

    def complete(self, request: GatewayRequest, shadow_model: str | None = None) -> GatewayResponse:
        with self._lock:
            return self._complete(request, shadow_model)

    def _complete(self, request: GatewayRequest, shadow_model: str | None = None) -> GatewayResponse:
        request_id = request.request_id or uuid.uuid4().hex
        prior = self.connection.execute("SELECT u.*, d.reason FROM usage u JOIN decisions d USING(request_id) WHERE request_id=?", (request_id,)).fetchone()
        if prior:
            return GatewayResponse(request_id, prior["model"], prior["provider"], prior["response"], prior["cost"], True, prior["reason"], 0)
        cache_key = hashlib.sha256(json.dumps({"tenant": request.tenant, "prompt": request.prompt, "quality": request.quality, "privacy": request.privacy}, sort_keys=True).encode()).hexdigest()
        cached = self.connection.execute("SELECT * FROM cache WHERE cache_key=?", (cache_key,)).fetchone()
        if cached:
            value = json.loads(cached["response"])
            return GatewayResponse(request_id, cached["model"], cached["provider"], value["text"], 0.0, True, "exact response cache hit", 0)
        candidates, reason = self._route(request)
        self._assert_budget(request, candidates[0])
        errors = []
        for fallback_count, model in enumerate(candidates):
            try:
                result = self.providers.call(model.provider, model.name, request.prompt)
                cost = (result.input_tokens * model.input_cost_per_million + result.output_tokens * model.output_cost_per_million) / 1_000_000
                if request.max_cost_usd is not None and cost > request.max_cost_usd:
                    raise BudgetExceeded(f"actual request cost {cost:.8f} exceeds cap {request.max_cost_usd:.8f}")
                self._record_success(request_id, request, model, result, cost, reason, candidates, fallback_count, cache_key)
                if shadow_model:
                    self._shadow(request_id, shadow_model, request.prompt)
                return GatewayResponse(request_id, model.name, model.provider, result.text, cost, False, reason, fallback_count)
            except BudgetExceeded:
                raise
            except Exception as exc:
                errors.append(f"{model.name}: {exc}")
                self._record_failure(model.name)
        raise NoHealthyModel("all fallback models failed: " + "; ".join(errors))

    def spent(self, tenant: str) -> float:
        cutoff = time.time() - 86400
        return float(self.connection.execute("SELECT COALESCE(SUM(cost),0) FROM usage WHERE tenant=? AND created_at>=?", (tenant, cutoff)).fetchone()[0])

    def inspect(self) -> dict:
        return {table: [dict(row) for row in self.connection.execute(f"SELECT * FROM {table}")] for table in ("usage", "health", "decisions", "shadows")}

    def _route(self, request: GatewayRequest) -> tuple[list[ModelConfig], str]:
        tokens = len(tokenize(request.prompt))
        complexity = len(content_tokens(request.prompt)) > 25 or any(word in request.prompt.lower() for word in ("analyze", "architecture", "tradeoff", "compare", "failure"))
        candidates = [model for model in self.models.values() if model.max_context >= tokens and (request.privacy != "local" or model.provider == "local") and self._healthy(model.name)]
        if not candidates: raise NoHealthyModel("no model satisfies context, privacy, and health constraints")
        if request.quality == "high" or complexity:
            candidates.sort(key=lambda model: (-model.quality_tier, model.input_cost_per_million))
            reason = "quality/complexity policy selected highest quality healthy model"
        elif request.quality == "fast":
            candidates.sort(key=lambda model: (model.latency_tier, model.input_cost_per_million))
            reason = "latency policy selected fastest healthy model"
        else:
            candidates.sort(key=lambda model: (model.input_cost_per_million + model.output_cost_per_million, -model.quality_tier))
            reason = "balanced policy selected lowest-cost adequate model"
        return candidates, reason

    def _healthy(self, model: str) -> bool:
        row = self.connection.execute("SELECT * FROM health WHERE model=?", (model,)).fetchone()
        if not row or row["failures"] < self.failure_threshold: return True
        return row["opened_at"] is not None and time.time() - row["opened_at"] >= self.cooldown_seconds

    def _assert_budget(self, request: GatewayRequest, model: ModelConfig) -> None:
        estimated_tokens = len(tokenize(request.prompt))
        estimate = estimated_tokens * model.input_cost_per_million / 1_000_000
        if self.spent(request.tenant) + estimate > self.tenant_daily_budget:
            raise BudgetExceeded(f"tenant {request.tenant} daily budget would be exceeded")

    def _record_success(self, request_id: str, request: GatewayRequest, model: ModelConfig, result: ProviderResult, cost: float, reason: str, candidates: list[ModelConfig], fallback_count: int, cache_key: str) -> None:
        now = time.time()
        self.connection.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)", (request_id, request.tenant, model.name, model.provider, result.text, result.input_tokens, result.output_tokens, cost, now))
        self.connection.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?)", (request_id, request.tenant, model.name, reason, json.dumps([item.name for item in candidates]), fallback_count, now))
        self.connection.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)", (cache_key, json.dumps({"text": result.text}), model.name, model.provider, cost, now))
        self.connection.execute("INSERT OR REPLACE INTO health VALUES (?,0,NULL)", (model.name,))
        self.connection.commit()

    def _record_failure(self, model: str) -> None:
        row = self.connection.execute("SELECT failures FROM health WHERE model=?", (model,)).fetchone()
        failures = (row["failures"] if row else 0) + 1
        opened = time.time() if failures >= self.failure_threshold else None
        self.connection.execute("INSERT OR REPLACE INTO health VALUES (?,?,?)", (model, failures, opened))
        self.connection.commit()

    def _shadow(self, request_id: str, model_name: str, prompt: str) -> None:
        if model_name not in self.models: raise ValueError(f"unknown shadow model: {model_name}")
        model = self.models[model_name]
        started = time.perf_counter()
        try:
            self.providers.call(model.provider, model.name, prompt)
            status, error = "completed", None
        except Exception as exc:
            status, error = "failed", str(exc)
        latency = (time.perf_counter() - started) * 1000
        self.connection.execute("INSERT INTO shadows VALUES (?,?,?,?,?,?)", (request_id, model.name, status, latency, error, time.time()))
        self.connection.commit()


def demo_gateway(path: Path, failures: dict[str, int] | None = None) -> ModelGateway:
    failures = failures if failures is not None else {}
    providers = ProviderRegistry()
    def handler(model: str, prompt: str) -> ProviderResult:
        if failures.get(model, 0) > 0:
            failures[model] -= 1
            raise RuntimeError("injected provider failure")
        return ProviderResult(f"{model} answered: {prompt}", len(tokenize(prompt)), 8)
    providers.register("local", handler)
    providers.register("hosted", handler)
    models = [
        ModelConfig("small-local", "local", 0.0, 0.0, 4096, 1, 1),
        ModelConfig("medium-hosted", "hosted", 0.20, 0.60, 8192, 2, 2),
        ModelConfig("large-hosted", "hosted", 2.0, 8.0, 32768, 3, 3),
    ]
    return ModelGateway(path, models, providers)
