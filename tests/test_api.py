from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app


def test_protected_api_roundtrip(tmp_path):
    url = f"sqlite:///{tmp_path}/api.db"
    Base.metadata.create_all(make_engine(url))
    client = TestClient(create_app(Settings(database_url=url, api_token="local-test")))
    assert client.get("/portfolio").status_code == 401
    assert client.post("/runs/daily", json={}).status_code == 401
    header = {"Authorization": "Bearer local-test"}
    payload = {
        "positions": [
            {"symbol": "012885", "name": "test", "market_value": "100.01", "source": "test"}
        ],
        "source": "test",
    }
    response = client.post("/portfolio/import", headers=header, json=payload)
    assert response.status_code == 200
    assert client.get("/portfolio", headers=header).json()["invested"] == "100.01"
    assert client.get("/instruments/999999", headers=header).status_code == 404


def test_no_token_write_closed():
    client = TestClient(create_app(Settings(api_token="")))
    assert client.post("/runs/daily", json={}).status_code == 503
