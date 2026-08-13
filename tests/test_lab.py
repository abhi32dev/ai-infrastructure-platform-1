from pathlib import Path

from ailab.embeddings import HashingEmbedder
from ailab.evaluation import evaluate
from ailab.models import Document
from ailab.rag import RAGService
from ailab.store import SQLiteHybridStore
from ailab.text import chunk_document
from ailab.workflow import DurableWorkflow


def populated_store(tmp_path: Path) -> SQLiteHybridStore:
    store = SQLiteHybridStore(tmp_path / "index.db", HashingEmbedder(128))
    documents = [
        Document("recovery", "A checkpoint lets a crashed worker resume. Idempotency keys prevent duplicate side effects during deterministic replay.", "reliability.md"),
        Document("retrieval", "Hybrid retrieval combines BM25 lexical matching with dense vector similarity. A reranker improves precision.", "retrieval.md"),
    ]
    store.upsert([chunk for document in documents for chunk in chunk_document(document, size=30, overlap=5)])
    return store


def test_hybrid_retrieval_finds_expected_source(tmp_path: Path) -> None:
    store = populated_store(tmp_path)
    results = store.search("How do idempotency keys help replay?", limit=1)
    assert results[0].chunk.source == "reliability.md"


def test_rag_answer_is_cited_and_passes_gate(tmp_path: Path) -> None:
    store = populated_store(tmp_path)
    answer = RAGService(store).answer("What prevents duplicate effects during replay?")
    result = evaluate(answer, "reliability.md")
    assert "[1]" in answer.text
    assert result.passed


def test_natural_checkpoint_question_does_not_get_distracted(tmp_path: Path) -> None:
    store = populated_store(tmp_path)
    answer = RAGService(store).answer("Why are checkpoints and idempotency both needed?", limit=2)
    assert answer.retrieved[0].chunk.source == "reliability.md"
    assert "Idempotency" in answer.text or "checkpoint" in answer.text


def test_plural_query_matches_singular_checkpoint(tmp_path: Path) -> None:
    store = populated_store(tmp_path)
    assert store.search("checkpoints", limit=1)[0].chunk.source == "reliability.md"


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    store = populated_store(tmp_path)
    before = store.count()
    chunk = chunk_document(Document("recovery", "A checkpoint lets a crashed worker resume. Idempotency keys prevent duplicate side effects during deterministic replay.", "reliability.md"), size=30, overlap=5)[0]
    store.upsert([chunk])
    assert store.count() == before


def test_workflow_retries_then_checkpoints_and_resumes(tmp_path: Path) -> None:
    workflow = DurableWorkflow(tmp_path / "workflow.db")
    calls = {"unstable": 0, "later": 0}

    def unstable(state: dict) -> dict:
        calls["unstable"] += 1
        if calls["unstable"] == 1:
            raise RuntimeError("injected failure")
        return {"value": 7}

    def later(state: dict) -> dict:
        calls["later"] += 1
        return {"result": state["value"] * 2}

    run_id, state = workflow.run([("unstable", unstable), ("later", later)])
    assert state["result"] == 14
    workflow.run([("unstable", unstable), ("later", later)], run_id=run_id)
    assert calls == {"unstable": 2, "later": 1}
