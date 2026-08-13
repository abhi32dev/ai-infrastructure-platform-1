import io,json
from types import SimpleNamespace
from unittest.mock import patch
from ailab.embeddings import HashingEmbedder,OllamaEmbedder
from ailab.models import Document
from ailab.rag_advanced import *
from ailab.store import SQLiteHybridStore
from ailab.text import chunk_document
def populated(tmp_path):
 s=SQLiteHybridStore(tmp_path/"i.db",HashingEmbedder());docs=[Document("a","Checkpoints and idempotency make replay safe","a.md",{"tenant":"a"}),Document("b","Dense and lexical retrieval are complementary","b.md",{"tenant":"b"})];s.upsert([c for d in docs for c in chunk_document(d,20,2)]);return s
def test_tenant_filter_and_reranking(tmp_path):
 r=AdvancedRetriever(populated(tmp_path));assert r.search("retrieval",filters={"tenant":"a"})==[];assert r.search("retrieval",filters={"tenant":"b"})[0].chunk.source=="b.md"
def test_rrf_and_eval(tmp_path):
 r=AdvancedRetriever(populated(tmp_path));result=run_retrieval_eval(r,[RAGEvalCase("1","safe replay idempotency","a.md"),RAGEvalCase("2","hybrid lexical dense","b.md")]);assert result["passed"] and result["mean_reciprocal_rank"]==1
def test_semantic_cache_hit_and_miss(tmp_path):
 e=HashingEmbedder();c=SemanticCache(tmp_path/"c.db",e,.8);c.put("checkpoint replay","answer");assert c.get("checkpoint replay")["response"]=="answer" and c.get("unrelated bananas") is None
def test_framework_document_adapters():
 lc=SimpleNamespace(page_content="hello",metadata={"source":"lc.md"});node=SimpleNamespace(get_content=lambda:"world",metadata={"source":"li.md"});assert from_langchain_documents([lc])[0].source=="lc.md" and from_llamaindex_nodes([node])[0].source=="li.md"
def test_ollama_embedding_http_contract():
 class Response(io.BytesIO):
  def __enter__(self):return self
  def __exit__(self,*args):self.close()
 def fake(request,timeout):
  body=json.loads(request.data);assert body=={"model":"test","input":"hello"};return Response(json.dumps({"embeddings":[[.1,.2,.3]]}).encode())
 with patch("urllib.request.urlopen",fake):vector=OllamaEmbedder("test").embed("hello")
 assert vector==[.1,.2,.3]
def test_ollama_embedding_failure_visible():
 import pytest
 with pytest.raises(RuntimeError):OllamaEmbedder(base_url="http://127.0.0.1:1",timeout=.01).embed("x")
