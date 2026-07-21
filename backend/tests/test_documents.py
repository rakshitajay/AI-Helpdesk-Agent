"""test_documents.py - Document endpoint tests."""
import io
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def get_auth_token():
    client.post("/api/auth/register", json={
        "email": "doctest@example.com", "username": "doctest", "password": "DocTest1"
    })
    resp = client.post("/api/auth/login", json={
        "email": "doctest@example.com", "password": "DocTest1"
    })
    return resp.json().get("access_token", "")

def test_list_documents_authenticated():
    token = get_auth_token()
    resp = client.get("/api/documents/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_list_documents_unauthenticated():
    resp = client.get("/api/documents/")
    assert resp.status_code == 401

def test_upload_invalid_extension():
    token = get_auth_token()
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("bad.exe", io.BytesIO(b"data"), "application/octet-stream")},
        data={},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
