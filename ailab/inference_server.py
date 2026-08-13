from __future__ import annotations

import hashlib
import queue
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Callable


class ServingError(RuntimeError): pass
class Overloaded(ServingError): pass
class DeadlineExceeded(ServingError): pass
class NotReady(ServingError): pass


@dataclass(frozen=True)
class InferenceRequest:
    payload: str
    request_id: str = ""
    deadline_seconds: float = 2.0


@dataclass(frozen=True)
class InferenceResponse:
    request_id: str
    output: str
    model_version: str
    queue_ms: float
    inference_ms: float
    batch_size: int


@dataclass
class _Work:
    request: InferenceRequest
    request_id: str
    submitted: float
    deadline: float
    event: threading.Event
    response: InferenceResponse | None = None
    error: Exception | None = None


class BatchedInferenceServer:
    def __init__(self, model: Callable[[list[str]], list[str]], version: str, max_batch_size: int = 8, max_batch_wait_ms: float = 10, max_queue_size: int = 64) -> None:
        if min(max_batch_size,max_queue_size)<=0: raise ValueError("batch and queue sizes must be positive")
        self.model=model; self.version=version; self.max_batch_size=max_batch_size; self.max_batch_wait=max_batch_wait_ms/1000
        self.work: queue.Queue[_Work]=queue.Queue(max_queue_size); self.stop_event=threading.Event(); self.ready_event=threading.Event(); self.metrics=Counter(); self.latencies=[]
        self.worker=threading.Thread(target=self._loop,name=f"inference-{version}",daemon=True); self.worker.start(); self.ready_event.set()

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        if not self.ready_event.is_set() or self.stop_event.is_set(): raise NotReady("server is not accepting traffic")
        now=time.perf_counter(); request_id=request.request_id or uuid.uuid4().hex; item=_Work(request,request_id,now,now+request.deadline_seconds,threading.Event())
        try: self.work.put_nowait(item)
        except queue.Full as exc: self.metrics["shed"]+=1; raise Overloaded("inference queue is full") from exc
        if not item.event.wait(request.deadline_seconds): self.metrics["deadline_exceeded"]+=1; raise DeadlineExceeded("request deadline expired while waiting")
        if item.error: raise item.error
        assert item.response is not None; return item.response

    def health(self) -> dict:
        return {"live":self.worker.is_alive(),"ready":self.ready_event.is_set() and not self.stop_event.is_set(),"queue_depth":self.work.qsize(),"model_version":self.version,"metrics":dict(self.metrics)}

    def shutdown(self, grace_seconds: float=2.0) -> None:
        self.ready_event.clear(); end=time.perf_counter()+grace_seconds
        while not self.work.empty() and time.perf_counter()<end: time.sleep(0.002)
        self.stop_event.set(); self.worker.join(max(0,end-time.perf_counter()))

    def _loop(self) -> None:
        while not self.stop_event.is_set() or not self.work.empty():
            try: first=self.work.get(timeout=0.02)
            except queue.Empty: continue
            batch=[first]; started=time.perf_counter()
            while len(batch)<self.max_batch_size:
                remaining=self.max_batch_wait-(time.perf_counter()-started)
                if remaining<=0: break
                try: batch.append(self.work.get(timeout=remaining))
                except queue.Empty: break
            active=[]
            for item in batch:
                if time.perf_counter()>item.deadline:
                    item.error=DeadlineExceeded("deadline expired before inference"); item.event.set(); self.metrics["deadline_exceeded"]+=1
                else: active.append(item)
            if not active: continue
            inference_start=time.perf_counter()
            try:
                outputs=self.model([item.request.payload for item in active])
                if len(outputs)!=len(active): raise ServingError("model output count does not match batch")
                inference_ms=(time.perf_counter()-inference_start)*1000
                for item,output in zip(active,outputs):
                    queue_ms=(inference_start-item.submitted)*1000; item.response=InferenceResponse(item.request_id,output,self.version,queue_ms,inference_ms,len(active)); item.event.set(); self.metrics["completed"]+=1; self.latencies.append(queue_ms+inference_ms)
                self.metrics["batches"]+=1; self.metrics["max_batch_size"]=max(self.metrics["max_batch_size"],len(active))
            except Exception as exc:
                self.metrics["model_errors"]+=len(active)
                for item in active: item.error=ServingError(f"model execution failed: {exc}"); item.event.set()


class CanaryDeployment:
    def __init__(self, stable: BatchedInferenceServer, canary: BatchedInferenceServer, canary_percent: int=10) -> None:
        if not 0<=canary_percent<=100: raise ValueError("canary percent must be 0..100")
        self.stable=stable; self.canary=canary; self.canary_percent=canary_percent; self.rolled_back=False

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        key=request.request_id or request.payload; bucket=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%100
        target=self.canary if not self.rolled_back and bucket<self.canary_percent else self.stable
        try: return target.infer(request)
        except ServingError:
            if target is self.canary: return self.stable.infer(request)
            raise

    def rollback(self) -> None: self.rolled_back=True


def demo_model(prefix: str="prediction", delay_seconds: float=0.001) -> Callable[[list[str]],list[str]]:
    def model(items:list[str])->list[str]: time.sleep(delay_seconds); return [f"{prefix}:{item.upper()}" for item in items]
    return model
