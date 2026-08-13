from pathlib import Path
import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ailab.gateway_api import create_app
from ailab.model_gateway import demo_gateway

def test_openai_compatible_gateway_happy_and_negative(tmp_path: Path):
    client = TestClient(create_app(demo_gateway(tmp_path/"gateway.db")))
    assert client.get("/health/ready").status_code == 200
    response = client.post("/v1/chat/completions", headers={"X-Tenant-ID":"acme"}, json={"messages":[{"role":"user","content":"hello"}]})
    assert response.status_code == 200 and response.json()["object"] == "chat.completion"
    assert client.post("/v1/chat/completions", json={"messages":[]}).status_code == 422
