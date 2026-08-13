from __future__ import annotations
import json,sqlite3,time
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
from .embeddings import cosine_similarity
from .models import Chunk,Document,SearchResult
from .store import SQLiteHybridStore
from .text import content_tokens,stable_id

def reciprocal_rank_fusion(results:list[SearchResult],k:int=60)->list[SearchResult]:
 dense=sorted(results,key=lambda x:(-x.dense_score,x.chunk.id));lexical=sorted(results,key=lambda x:(-x.lexical_score,x.chunk.id));scores={}
 for ranking in (dense,lexical):
  for rank,result in enumerate(ranking,1):scores[result.chunk.id]=scores.get(result.chunk.id,0)+1/(k+rank)
 lookup={x.chunk.id:x for x in results};return [SearchResult(lookup[i].chunk,lookup[i].dense_score,lookup[i].lexical_score,score) for i,score in sorted(scores.items(),key=lambda x:(-x[1],x[0]))]
def rerank(query:str,results:list[SearchResult])->list[SearchResult]:
 terms=set(content_tokens(query));scored=[]
 for result in results:
  tokens=content_tokens(result.chunk.text);coverage=len(terms&set(tokens))/max(len(terms),1);phrase=sum(1 for a,b in zip(tokens,tokens[1:]) if a in terms and b in terms)/max(len(tokens)-1,1);score=.65*coverage+.20*phrase+.15*result.combined_score;scored.append(SearchResult(result.chunk,result.dense_score,result.lexical_score,score))
 return sorted(scored,key=lambda x:(-x.combined_score,x.chunk.id))
class AdvancedRetriever:
 def __init__(self,store:SQLiteHybridStore):self.store=store
 def search(self,query:str,limit=5,filters:dict[str,Any]|None=None)->list[SearchResult]:
  candidates=self.store.search(query,limit=max(self.store.count(),limit));filters=filters or {};candidates=[r for r in candidates if (r.dense_score>0 or r.lexical_score>0) and all(r.chunk.metadata.get(k)==v for k,v in filters.items())];return rerank(query,reciprocal_rank_fusion(candidates))[:limit]
class SemanticCache:
 def __init__(self,path:Path,embedder,threshold=.92,ttl=3600):
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row;self.embedder=embedder;self.threshold=threshold;self.ttl=ttl;self.db.execute("CREATE TABLE IF NOT EXISTS cache(id TEXT PRIMARY KEY,query TEXT,embedding TEXT,response TEXT,expires REAL)");self.db.commit()
 def put(self,query,response):self.db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)",(stable_id(query),query,json.dumps(self.embedder.embed(query)),response,time.time()+self.ttl));self.db.commit()
 def get(self,query):
  vector=self.embedder.embed(query);best=None
  for row in self.db.execute("SELECT * FROM cache WHERE expires>?",(time.time(),)):
   score=cosine_similarity(vector,json.loads(row["embedding"]))
   if score>=self.threshold and (best is None or score>best[0]):best=(score,row["response"])
  return None if best is None else {"response":best[1],"similarity":best[0]}
def from_langchain_documents(documents:list[Any])->list[Document]:return [Document(stable_id(str(d.page_content),str(i)),str(d.page_content),str(getattr(d,"metadata",{}).get("source",f"langchain:{i}")),dict(getattr(d,"metadata",{}))) for i,d in enumerate(documents)]
def from_llamaindex_nodes(nodes:list[Any])->list[Document]:
 documents=[]
 for i,node in enumerate(nodes):
  text=str(node.get_content() if hasattr(node,"get_content") else node.text);metadata=dict(getattr(node,"metadata",{}));documents.append(Document(stable_id(text,str(i)),text,str(metadata.get("source",f"llamaindex:{i}")),metadata))
 return documents
@dataclass(frozen=True)
class RAGEvalCase:id:str;query:str;expected_source:str
def run_retrieval_eval(retriever:AdvancedRetriever,cases:list[RAGEvalCase],k=3)->dict:
 if not cases:raise ValueError("evaluation cases cannot be empty")
 reciprocal=[];hits=0
 for case in cases:
  results=retriever.search(case.query,k);rank=next((i for i,r in enumerate(results,1) if case.expected_source in r.chunk.source),None);hits+=rank is not None;reciprocal.append(0 if rank is None else 1/rank)
 return {"cases":len(cases),"recall_at_k":hits/len(cases),"mean_reciprocal_rank":sum(reciprocal)/len(cases),"passed":hits==len(cases)}
