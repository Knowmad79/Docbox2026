import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_login():
    response = client.post("/api/auth/login", json={"email": "testuser@example.com", "password": "testpass"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_failure():
    response = client.post("/api/auth/login", json={"email": "wronguser@example.com", "password": "wrongpass"})
    assert response.status_code == 401