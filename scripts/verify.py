#!/usr/bin/env python3
"""Run repeatable acceptance scenarios and write evidence artifacts."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ailab.embeddings import HashingEmbedder  # noqa: E402
from ailab.evaluation import evaluate  # noqa: E402
from ailab.models import Document  # noqa: E402
from ailab.providers import OllamaProvider  # noqa: E402
from ailab.rag import RAGService  # noqa: E402
from ailab.store import SQLiteHybridStore  # noqa: E402
from ailab.text import chunk_document, load_documents  # noqa: E402
from ailab.workflow import DurableWorkflow  # noqa: E402


def scenario(name: str, category: str, operation: Callable[[], dict]) -> dict:
    started = time.perf_counter()
    try:
        evidence = operation()
        return {"name": name, "category": category, "status": "passed", "duration_ms": round((time.perf_counter() - started) * 1000, 3), "evidence": evidence}
    except Exception as exc:
        return {"name": name, "category": category, "status": "failed", "duration_ms": round((time.perf_counter() - started) * 1000, 3), "error": f"{type(exc).__name__}: {exc}"}


def expect_exception(expected: type[BaseException], operation: Callable[[], object]) -> str:
    try:
        operation()
    except expected as exc:
        return f"{type(exc).__name__}: {exc}"
    raise AssertionError(f"Expected {expected.__name__}, but operation succeeded")


def main() -> int:
    artifact_dir = ROOT / "artifacts" / "verification"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ailab-verification-") as temp:
        temp_path = Path(temp)
        database = temp_path / "acceptance.db"
        embedder = HashingEmbedder(256)
        store = SQLiteHybridStore(database, embedder)
        documents = load_documents(ROOT / "examples" / "knowledge")
        chunks = [chunk for document in documents for chunk in chunk_document(document, 90, 18)]

        results = []

        def ingest_and_query() -> dict:
            inserted = store.upsert(chunks)
            answer = RAGService(store).answer("Why are checkpoints and idempotency both needed?", limit=3)
            assert answer.retrieved[0].chunk.source.endswith("reliability.md")
            assert "[1]" in answer.text
            return {"documents": len(documents), "chunks": inserted, "top_source": answer.retrieved[0].chunk.source, "answer": answer.text, "usage": answer.usage}

        results.append(scenario("clean_ingest_and_grounded_query", "happy_path", ingest_and_query))

        def quality_gate() -> dict:
            answer = RAGService(store).answer("How does hybrid retrieval combine lexical and dense search?", limit=3)
            evaluation = evaluate(answer, "retrieval.md")
            assert evaluation.passed
            return asdict(evaluation)

        results.append(scenario("retrieval_quality_gate", "positive", quality_gate))

        def persistent_reopen() -> dict:
            expected = store.count()
            store.close()
            reopened = SQLiteHybridStore(database, embedder)
            try:
                observed = reopened.count()
                assert observed == expected
                top = reopened.search("bounded retries and checkpoint replay", 1)[0].chunk.source
                assert top.endswith("reliability.md")
                return {"expected_chunks": expected, "observed_chunks": observed, "top_source": top}
            finally:
                reopened.close()

        results.append(scenario("index_survives_process_reopen", "positive", persistent_reopen))

        def empty_index_rejected() -> dict:
            empty = SQLiteHybridStore(temp_path / "empty.db", embedder)
            try:
                message = expect_exception(ValueError, lambda: RAGService(empty).answer("question"))
                return {"expected_error": message}
            finally:
                empty.close()

        results.append(scenario("query_empty_index", "negative", empty_index_rejected))

        def invalid_chunking_rejected() -> dict:
            document = Document("bad", "some content", "memory")
            message = expect_exception(ValueError, lambda: chunk_document(document, size=10, overlap=10))
            return {"expected_error": message}

        results.append(scenario("invalid_chunk_configuration", "negative", invalid_chunking_rejected))

        def unavailable_provider_visible() -> dict:
            provider = OllamaProvider("http://127.0.0.1:1", timeout=0.2)
            message = expect_exception(RuntimeError, lambda: provider.generate("missing", "question", ["context"]))
            return {"expected_error": message}

        results.append(scenario("unavailable_ollama_provider", "negative", unavailable_provider_visible))

        def retry_and_resume() -> dict:
            workflow = DurableWorkflow(temp_path / "workflow.db")
            calls = {"unstable": 0, "downstream": 0}

            def unstable(state: dict) -> dict:
                calls["unstable"] += 1
                if calls["unstable"] == 1:
                    raise RuntimeError("injected transient failure")
                return {"value": 21}

            def downstream(state: dict) -> dict:
                calls["downstream"] += 1
                return {"result": state["value"] * 2}

            run_id, state = workflow.run([("unstable", unstable), ("downstream", downstream)])
            workflow.run([("unstable", unstable), ("downstream", downstream)], run_id=run_id)
            assert calls == {"unstable": 2, "downstream": 1}
            return {"run_id": run_id, "state": state, "calls_after_resume": calls}

        results.append(scenario("retry_checkpoint_and_idempotent_resume", "failure_recovery", retry_and_resume))

    test_run = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    results.append({"name": "automated_test_suite", "category": "tests", "status": "passed" if test_run.returncode == 0 else "failed", "exit_code": test_run.returncode, "stdout": test_run.stdout.strip(), "stderr": test_run.stderr.strip()})
    passed = sum(item["status"] == "passed" for item in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "scenarios": results,
    }
    report_path = artifact_dir / "latest.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary_path = artifact_dir / "latest.txt"
    summary_path.write_text("\n".join([f"Verification: {passed}/{len(results)} passed", *[f"[{item['status'].upper()}] {item['category']}: {item['name']}" for item in results]]) + "\n", encoding="utf-8")
    print(summary_path.read_text(), end="")
    print(f"Artifacts: {report_path.relative_to(ROOT)}, {summary_path.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

