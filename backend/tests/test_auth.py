"""test_auth.py - Authentication endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
TEST_USER = {
    "email": "testuser@example.com",
    "username": "testuser123",
    "password": "TestPass1",
    "full_name": "Test User"
}

def test_register_user():
    response = client.post("/api/auth/register", json=TEST_USER)
    assert response.status_code in (201, 409)

def test_login_success():
    client.post("/api/auth/register", json=TEST_USER)
    response = client.post("/api/auth/login", json={
        "email": TEST_USER["email"], "password": TEST_USER["password"]
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_wrong_password():
    response = client.post("/api/auth/login", json={
        "email": TEST_USER["email"], "password": "WrongPassword1"
    })
    assert response.status_code == 401

def test_get_profile_unauthenticated():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
