from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .text import content_tokens, tokenize


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int


class DeterministicGroundedProvider:
    """Extractive provider for repeatable offline demos and evaluation tests."""

    name = "offline"

    def generate(self, model: str, query: str, contexts: list[str]) -> Generation:
        query_terms = set(content_tokens(query))
        candidates: list[tuple[int, int, str]] = []
        for citation, context in enumerate(contexts, 1):
            sentences = re.split(r"(?<=[.!?])\s+", context.strip())
            for sentence in sentences:
                overlap = len(query_terms.intersection(tokenize(sentence)))
                candidates.append((overlap, citation, sentence))
        selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:3]
        selected = [item for item in selected if item[0] > 0] or candidates[:1]
        text = " ".join(f"{sentence} [{citation}]" for _, citation, sentence in selected)
        return Generation(text or "The indexed context does not contain enough information.", sum(map(lambda x: len(tokenize(x)), contexts)) + len(query_terms), len(tokenize(text)))


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, model: str, query: str, contexts: list[str]) -> Generation:
        context = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(contexts, 1))
        prompt = (
            "Answer only from the supplied context. Cite supporting passages with [n]. "
            "If evidence is insufficient, say so.\n\n"
            f"Question: {query}\n\nContext:\n{context}"
        )
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(f"{self.base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama request failed at {self.base_url}: {exc}") from exc
        return Generation(result["response"], int(result.get("prompt_eval_count", 0)), int(result.get("eval_count", 0)))
