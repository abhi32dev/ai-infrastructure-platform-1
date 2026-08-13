from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Answer


@dataclass(frozen=True)
class EvaluationResult:
    retrieval_hit: float
    citation_validity: float
    grounded_token_ratio: float
    passed: bool


def evaluate(answer: Answer, expected_source_contains: str, minimum_grounding: float = 0.45) -> EvaluationResult:
    retrieval_hit = float(any(expected_source_contains in result.chunk.source for result in answer.retrieved))
    cited = {int(value) for value in re.findall(r"\[(\d+)]", answer.text)}
    valid = set(range(1, len(answer.citations) + 1))
    citation_validity = 1.0 if cited and cited.issubset(valid) else 0.0
    context_terms = set()
    for result in answer.retrieved:
        context_terms.update(re.findall(r"[a-z0-9]+", result.chunk.text.lower()))
    answer_terms = re.findall(r"[a-z0-9]+", answer.text.lower())
    grounded = sum(term in context_terms for term in answer_terms) / max(len(answer_terms), 1)
    passed = bool(retrieval_hit and citation_validity and grounded >= minimum_grounding)
    return EvaluationResult(retrieval_hit, citation_validity, grounded, passed)

