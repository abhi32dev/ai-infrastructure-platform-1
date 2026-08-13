from __future__ import annotations
import json,math,time
from dataclasses import asdict,dataclass
from pathlib import Path
import numpy as np

class DataValidationError(ValueError):pass
@dataclass(frozen=True)
class Metrics:accuracy:float;precision:float;recall:float;f1:float
@dataclass(frozen=True)
class ModelArtifact:version:str;weights:list[float];bias:float;metrics:dict;feature_mean:list[float];created_at:float

def make_dataset(samples=500,features=4,seed=42,shift=0.0):
 rng=np.random.default_rng(seed);x=rng.normal(shift,1,(samples,features));true=np.arange(1,features+1)/features;logits=x@true+rng.normal(0,.3,samples);y=(logits>0).astype(float);return x,y
def validate(x,y):
 if x.ndim!=2 or y.ndim!=1 or len(x)!=len(y):raise DataValidationError("invalid feature/label shapes")
 if not np.isfinite(x).all():raise DataValidationError("features contain NaN or infinity")
 if not set(np.unique(y)).issubset({0,1}):raise DataValidationError("labels must be binary")
def split(x,y,validation_fraction=.2,seed=42):
 if not 0<validation_fraction<1:raise ValueError("validation fraction must be 0..1")
 rng=np.random.default_rng(seed);idx=rng.permutation(len(x));cut=int(len(x)*(1-validation_fraction));return x[idx[:cut]],x[idx[cut:]],y[idx[:cut]],y[idx[cut:]]
class LogisticModel:
 def __init__(self,features):self.weights=np.zeros(features);self.bias=0.0
 def train(self,x,y,epochs=300,learning_rate=.1):
  validate(x,y)
  for _ in range(epochs):
   p=self.predict_proba(x);error=p-y;self.weights-=learning_rate*(x.T@error/len(x));self.bias-=learning_rate*error.mean()
  return self
 def predict_proba(self,x):return 1/(1+np.exp(-np.clip(x@self.weights+self.bias,-30,30)))
 def predict(self,x):return (self.predict_proba(x)>=.5).astype(int)
def evaluate(y,pred)->Metrics:
 tp=int(((y==1)&(pred==1)).sum());tn=int(((y==0)&(pred==0)).sum());fp=int(((y==0)&(pred==1)).sum());fn=int(((y==1)&(pred==0)).sum());precision=tp/max(tp+fp,1);recall=tp/max(tp+fn,1);return Metrics((tp+tn)/len(y),precision,recall,2*precision*recall/max(precision+recall,1e-12))
class ModelRegistry:
 def __init__(self,path:Path):self.path=path;path.mkdir(parents=True,exist_ok=True);self.index=path/"registry.json";self.data=json.loads(self.index.read_text()) if self.index.exists() else {"versions":{},"production":None,"history":[]}
 def register(self,model:LogisticModel,metrics:Metrics,mean,version:str)->ModelArtifact:
  artifact=ModelArtifact(version,model.weights.tolist(),model.bias,asdict(metrics),np.asarray(mean).tolist(),time.time());(self.path/f"{version}.json").write_text(json.dumps(asdict(artifact),indent=2));self.data["versions"][version]=asdict(artifact);self._save();return artifact
 def promote(self,version,min_f1=.8):
  if version not in self.data["versions"]:raise ValueError("unknown model version")
  if self.data["versions"][version]["metrics"]["f1"]<min_f1:raise ValueError("model failed promotion quality gate")
  prior=self.data["production"];self.data["production"]=version;self.data["history"].append({"from":prior,"to":version,"at":time.time()});self._save()
 def rollback(self):
  history=self.data["history"]
  if not history or history[-1]["from"] is None:raise ValueError("no previous production version")
  self.data["production"]=history[-1]["from"];self.data["history"].append({"from":history[-1]["to"],"to":history[-1]["from"],"at":time.time()});self._save()
 def load(self,version=None)->LogisticModel:
  version=version or self.data["production"]
  if not version:raise ValueError("no production model")
  a=self.data["versions"][version];m=LogisticModel(len(a["weights"]));m.weights=np.array(a["weights"]);m.bias=a["bias"];return m
 def drift(self,x,version=None,threshold=.5):
  version=version or self.data["production"];baseline=np.array(self.data["versions"][version]["feature_mean"]);delta=np.abs(x.mean(axis=0)-baseline);return {"max_mean_shift":float(delta.max()),"per_feature":delta.tolist(),"drifted":bool((delta>threshold).any()),"retrain_recommended":bool((delta>threshold).any())}
 def _save(self):self.index.write_text(json.dumps(self.data,indent=2))

@dataclass(frozen=True)
class Box:x1:int;y1:int;x2:int;y2:int
def detect(frame:np.ndarray,threshold=.5)->list[Box]:
 mask=frame>=threshold;seen=np.zeros(mask.shape,bool);boxes=[]
 for y,x in zip(*np.where(mask)):
  if seen[y,x]:continue
  stack=[(y,x)];seen[y,x]=True;points=[]
  while stack:
   cy,cx=stack.pop();points.append((cy,cx))
   for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
    ny,nx=cy+dy,cx+dx
    if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;stack.append((ny,nx))
  ys=[p[0] for p in points];xs=[p[1] for p in points];boxes.append(Box(int(min(xs)),int(min(ys)),int(max(xs)+1),int(max(ys)+1)))
 return boxes
def iou(a:Box,b:Box)->float:
 intersection=max(0,min(a.x2,b.x2)-max(a.x1,b.x1))*max(0,min(a.y2,b.y2)-max(a.y1,b.y1));area=lambda q:(q.x2-q.x1)*(q.y2-q.y1);return intersection/max(area(a)+area(b)-intersection,1)
class CentroidTracker:
 def __init__(self,max_distance=5):self.max_distance=max_distance;self.next=1;self.tracks={}
 def update(self,boxes:list[Box])->dict[int,Box]:
  assigned={};available=set(self.tracks)
  for box in boxes:
   center=((box.x1+box.x2)/2,(box.y1+box.y2)/2);best=min(available,key=lambda i:math.dist(center,((self.tracks[i].x1+self.tracks[i].x2)/2,(self.tracks[i].y1+self.tracks[i].y2)/2)),default=None)
   if best is not None and math.dist(center,((self.tracks[best].x1+self.tracks[best].x2)/2,(self.tracks[best].y1+self.tracks[best].y2)/2))<=self.max_distance:track=best;available.remove(best)
   else:track=self.next;self.next+=1
   assigned[track]=box
  self.tracks=assigned;return assigned
