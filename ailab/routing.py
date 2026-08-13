from __future__ import annotations

from .models import RouteDecision
from .text import tokenize


class CostAwareRouter:
    def __init__(self, local_model: str = "qwen2.5:3b", large_model: str = "qwen2.5:7b") -> None:
        self.local_model = local_model
        self.large_model = large_model

    def route(self, query: str, context: str, force_provider: str | None = None) -> RouteDecision:
        input_tokens = len(tokenize(query)) + len(tokenize(context))
        markers = ("compare", "analyze", "tradeoff", "design", "why", "failure", "architecture")
        complexity = min(5, int(input_tokens > 500) + int(input_tokens > 1200) + sum(m in query.lower() for m in markers))
        if force_provider == "offline":
            return RouteDecision("deterministic-grounded", "offline", "provider forced for deterministic execution", input_tokens, complexity)
        model = self.large_model if complexity >= 3 else self.local_model
        reason = "complex reasoning or long context" if complexity >= 3 else "simple query fits lower-cost local model"
        return RouteDecision(model, force_provider or "ollama", reason, input_tokens, complexity)

