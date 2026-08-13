from __future__ import annotations
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .model_gateway import BudgetExceeded, GatewayRequest, ModelGateway, NoHealthyModel

class ChatMessage(BaseModel):
    role: str
    content: str
class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage] = Field(min_length=1)
    quality: str = "balanced"
    max_cost_usd: float | None = Field(default=None, ge=0)
    user: str | None = None

def create_app(gateway: ModelGateway) -> FastAPI:
    app = FastAPI(title="AI Lab Model Gateway", version="1.0.0")
    @app.get("/health/live")
    def live() -> dict: return {"status": "ok"}
    @app.get("/health/ready")
    def ready() -> dict: return {"status": "ready", "models": len(gateway.models)}
    @app.get("/v1/models")
    def models() -> dict:
        return {"object": "list", "data": [{"id": m.name, "object": "model", "owned_by": m.provider} for m in gateway.models.values()]}
    @app.post("/v1/chat/completions")
    def complete(body: ChatCompletionRequest, x_tenant_id: str = Header(default="default"), x_request_id: str = Header(default="")) -> dict:
        prompt = "\n".join(f"{m.role}: {m.content}" for m in body.messages)
        try:
            result = gateway.complete(GatewayRequest(x_tenant_id, prompt, x_request_id, body.quality, max_cost_usd=body.max_cost_usd))
        except BudgetExceeded as exc: raise HTTPException(429, {"code": "budget_exceeded", "message": str(exc)}) from exc
        except NoHealthyModel as exc: raise HTTPException(503, {"code": "no_healthy_model", "message": str(exc)}) from exc
        return {"id": result.request_id, "object": "chat.completion", "model": result.model, "choices": [{"index": 0, "message": {"role": "assistant", "content": result.text}, "finish_reason": "stop"}], "usage": {"cost_usd": result.cost_usd, "cached": result.cached}, "routing": {"provider": result.provider, "reason": result.route_reason, "fallback_count": result.fallback_count}}
    return app
