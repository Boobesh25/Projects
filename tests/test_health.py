"""
Test API Health & Core Service Initialization
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "JobRadar" in data["service"]

def test_dev_login():
    response = client.post("/api/auth/dev-login", json={"email": "boobesh2509@gmail.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "boobesh2509@gmail.com"
    assert "token" in data
