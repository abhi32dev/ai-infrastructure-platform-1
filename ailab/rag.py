from __future__ import annotations

from .models import Answer, Citation
from .providers import DeterministicGroundedProvider, OllamaProvider
from .routing import CostAwareRouter
from .store import SQLiteHybridStore


class RAGService:
    def __init__(self, store: SQLiteHybridStore, router: CostAwareRouter | None = None) -> None:
        self.store = store
        self.router = router or CostAwareRouter()
        self.providers = {"offline": DeterministicGroundedProvider(), "ollama": OllamaProvider()}

    def answer(self, query: str, limit: int = 4, provider: str = "offline") -> Answer:
        results = self.store.search(query, limit=limit)
        if not results:
            raise ValueError("The index is empty; ingest documents before asking questions")
        contexts = [result.chunk.text for result in results]
        route = self.router.route(query, "\n".join(contexts), force_provider=provider)
        generation = self.providers[route.provider].generate(route.model, query, contexts)
        citations = [Citation(index, result.chunk.id, result.chunk.source) for index, result in enumerate(results, 1)]
        return Answer(
            query=query,
            text=generation.text,
            citations=citations,
            route=route,
            retrieved=results,
            usage={"prompt_tokens": generation.prompt_tokens, "completion_tokens": generation.completion_tokens},
        )

