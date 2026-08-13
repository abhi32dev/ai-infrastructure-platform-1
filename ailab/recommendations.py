from __future__ import annotations
import hashlib,math,sqlite3,time
from collections import Counter,defaultdict
from dataclasses import dataclass
from pathlib import Path
from .eval_platform import two_proportion_z_test

@dataclass(frozen=True)
class Item:id:str;category:str;tags:tuple[str,...]
@dataclass(frozen=True)
class Recommendation:item_id:str;score:float;reasons:tuple[str,...]

class RecommendationPlatform:
 def __init__(self,path:Path,items:list[Item]):
  if not items:raise ValueError("catalog cannot be empty")
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row;self.items={x.id:x for x in items};self.db.executescript("""CREATE TABLE IF NOT EXISTS interactions(user_id TEXT,item_id TEXT,event TEXT,weight REAL,created_at REAL);CREATE TABLE IF NOT EXISTS assignments(user_id TEXT,experiment TEXT,variant TEXT,PRIMARY KEY(user_id,experiment));CREATE TABLE IF NOT EXISTS outcomes(user_id TEXT,experiment TEXT,variant TEXT,converted INTEGER,PRIMARY KEY(user_id,experiment));""");self.db.commit()
 def interact(self,user:str,item:str,event:str="view",timestamp:float|None=None):
  if item not in self.items:raise ValueError(f"unknown item: {item}")
  weights={"view":1,"click":3,"purchase":8,"dislike":-5}
  if event not in weights:raise ValueError(f"unknown event: {event}")
  self.db.execute("INSERT INTO interactions VALUES(?,?,?,?,?)",(user,item,event,weights[event],timestamp or time.time()));self.db.commit()
 def recommend(self,user:str,k:int=5)->list[Recommendation]:
  if k<=0:raise ValueError("k must be positive")
  rows=self.db.execute("SELECT * FROM interactions").fetchall();consumed={r["item_id"] for r in rows if r["user_id"]==user and r["weight"]>0};pop=Counter();user_items=defaultdict(dict)
  for r in rows:pop[r["item_id"]]+=max(0,r["weight"]);user_items[r["user_id"]][r["item_id"]]=r["weight"]
  profile=Counter()
  for item_id,weight in user_items[user].items():
   for tag in self.items[item_id].tags:profile[tag]+=weight
   profile[self.items[item_id].category]+=weight
  collaborative=Counter()
  target=set(user_items[user])
  for other,history in user_items.items():
   if other==user:continue
   similarity=len(target&set(history))/max(1,len(target|set(history)))
   for item_id,weight in history.items():
    if item_id not in consumed and weight>0:collaborative[item_id]+=similarity*weight
  max_pop=max(pop.values(),default=1) or 1;results=[]
  for item_id,item in self.items.items():
   if item_id in consumed:continue
   content=sum(max(0,profile[tag]) for tag in (*item.tags,item.category));popularity=pop[item_id]/max_pop;collab=collaborative[item_id]
   score=.45*content+.35*collab+.20*popularity;reasons=[]
   if content:reasons.append("content affinity")
   if collab:reasons.append("similar users")
   if popularity:reasons.append("popular")
   if not reasons:reasons.append("cold-start catalog fallback")
   results.append(Recommendation(item_id,score,tuple(reasons)))
  return sorted(results,key=lambda x:(-x.score,x.item_id))[:k]
 def assign(self,user:str,experiment:str="ranking-v1",treatment_percent:int=50)->str:
  if not 0<=treatment_percent<=100:raise ValueError("percentage must be 0..100")
  row=self.db.execute("SELECT variant FROM assignments WHERE user_id=? AND experiment=?",(user,experiment)).fetchone()
  if row:return row[0]
  bucket=int(hashlib.sha256(f"{experiment}:{user}".encode()).hexdigest()[:8],16)%100;variant="treatment" if bucket<treatment_percent else "control";self.db.execute("INSERT INTO assignments VALUES(?,?,?)",(user,experiment,variant));self.db.commit();return variant
 def outcome(self,user:str,converted:bool,experiment:str="ranking-v1"):
  variant=self.assign(user,experiment);self.db.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?)",(user,experiment,variant,int(converted)));self.db.commit()
 def analyze(self,experiment:str="ranking-v1")->dict:
  counts={v:self.db.execute("SELECT COALESCE(SUM(converted),0),COUNT(*) FROM outcomes WHERE experiment=? AND variant=?",(experiment,v)).fetchone() for v in ("control","treatment")}
  if min(counts["control"][1],counts["treatment"][1])==0:return {"ready":False,"reason":"both variants need outcomes"}
  return {"ready":True,**two_proportion_z_test(counts["control"][0],counts["control"][1],counts["treatment"][0],counts["treatment"][1])}

def ranking_metrics(recommended:list[str],relevant:set[str],catalog:list[Item],k:int)->dict:
 ranked=recommended[:k];hits=[int(x in relevant) for x in ranked];precision=sum(hits)/max(k,1);recall=sum(hits)/max(len(relevant),1);dcg=sum(hit/math.log2(i+2) for i,hit in enumerate(hits));ideal=sum(1/math.log2(i+2) for i in range(min(len(relevant),k)));ndcg=dcg/ideal if ideal else 0;categories={x.id:x.category for x in catalog};pairs=0;different=0
 for i in range(len(ranked)):
  for j in range(i+1,len(ranked)):pairs+=1;different+=categories.get(ranked[i])!=categories.get(ranked[j])
 return {"precision_at_k":precision,"recall_at_k":recall,"ndcg_at_k":ndcg,"coverage":len(set(ranked))/max(len(catalog),1),"diversity":different/pairs if pairs else 0}

def demo_catalog()->list[Item]:return [Item("ml-book","books",("ml","python")),Item("cloud-book","books",("cloud","aws")),Item("gpu-course","courses",("ml","gpu")),Item("k8s-course","courses",("cloud","kubernetes")),Item("python-lab","labs",("python","ml")),Item("security-lab","labs",("security","cloud"))]
