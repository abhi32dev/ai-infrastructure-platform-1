from __future__ import annotations
import importlib.util,json,math
from dataclasses import dataclass,asdict
from pathlib import Path

@dataclass(frozen=True)
class PortableLinearModel:
 weight:float;bias:float;framework:str;schema_version:int=1
 def predict(self,x:float)->float:
  if not math.isfinite(x):raise ValueError("input must be finite")
  return self.weight*x+self.bias
 def save(self,path:Path):path.write_text(json.dumps(asdict(self),sort_keys=True))
 @classmethod
 def load(cls,path:Path):
  if not path.exists():raise FileNotFoundError(path)
  data=json.loads(path.read_text())
  if data.get("schema_version")!=1:raise ValueError("unsupported artifact schema")
  if not all(math.isfinite(float(data[x])) for x in ("weight","bias")):raise ValueError("non-finite artifact")
  return cls(**data)

def train_linear(xs:list[float],ys:list[float],framework:str="numpy")->PortableLinearModel:
 if len(xs)!=len(ys) or len(xs)<2:raise ValueError("aligned training arrays require at least two samples")
 if any(not math.isfinite(v) for v in [*xs,*ys]):raise ValueError("training data must be finite")
 mean_x=sum(xs)/len(xs);mean_y=sum(ys)/len(ys);den=sum((x-mean_x)**2 for x in xs)
 if den==0:raise ValueError("features have zero variance")
 weight=sum((x-mean_x)*(y-mean_y) for x,y in zip(xs,ys))/den;return PortableLinearModel(weight,mean_y-weight*mean_x,framework)

def installed_frameworks()->dict[str,bool]:return {name:importlib.util.find_spec(name) is not None for name in ("torch","tensorflow","keras","jax","onnxruntime")}
def parity(models:list[PortableLinearModel],inputs:list[float],tolerance:float=1e-6)->dict:
 if not models or not inputs:raise ValueError("models and inputs required")
 if tolerance<0:raise ValueError("tolerance cannot be negative")
 predictions=[[m.predict(x) for x in inputs] for m in models];maximum=max(abs(a-b) for row in predictions[1:] for a,b in zip(predictions[0],row)) if len(predictions)>1 else 0.0;return {"passed":maximum<=tolerance,"maximum_difference":maximum}
