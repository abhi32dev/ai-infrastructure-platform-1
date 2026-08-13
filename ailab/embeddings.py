from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request

from .text import content_tokens


class HashingEmbedder:
    """Deterministic dependency-free feature hashing for local retrieval exercises.

    This is deliberately not presented as a semantic production embedding model. It
    supplies a stable dense-vector boundary that can later be replaced by Ollama,
    sentence-transformers, Bedrock, or another embedding provider.
    """

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        terms = content_tokens(text)
        features = terms + [f"{a}::{b}" for a, b in zip(terms, terms[1:])]
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class OllamaEmbedder:
    """Real Ollama `/api/embed` client; model availability is explicit."""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://127.0.0.1:11434", timeout: float = 30.0) -> None:
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout

    def embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "input": text}).encode()
        request = urllib.request.Request(f"{self.base_url}/api/embed", data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama embedding request failed at {self.base_url}: {exc}") from exc
        embeddings = body.get("embeddings")
        if not embeddings or not isinstance(embeddings[0], list):
            raise RuntimeError("Ollama embedding response did not contain embeddings")
        return [float(value) for value in embeddings[0]]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions differ")
    return sum(a * b for a, b in zip(left, right))
