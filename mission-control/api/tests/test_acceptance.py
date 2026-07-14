"""
Phase 5 acceptance tests — run against a live server (port 8001).

The first user already exists, so registration is invite-only.
All tests use the existing owner account or invited editors.
"""

import os

import httpx
import pytest

BASE = os.environ.get("TEST_API_URL", "http://localhost:8001")
OWNER_EMAIL = "admin@test.com"
OWNER_PASS = "secret123"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=10)


@pytest.fixture(scope="module")
def owner_token(client):
    r = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASS})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def owner_headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}


class TestAuthFlow:
    def test_me_without_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401
        assert "authentication required" in r.text

    def test_login_wrong_password(self, client):
        r = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_and_me(self, client, owner_token):
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200, r.text
        assert r.json()["email"] == OWNER_EMAIL
        assert r.json()["role"] == "owner"


class TestTenantScoping:
    def test_projects_require_auth(self, client):
        r = client.get("/projects")
        assert r.status_code == 401

    def test_tenant_requires_auth(self, client):
        r = client.get("/tenant")
        assert r.status_code == 401

    def test_tenant_budget_requires_auth(self, client):
        r = client.get("/tenant/budget")
        assert r.status_code == 401

    def test_own_tenant(self, client, owner_headers):
        r = client.get("/tenant", headers=owner_headers)
        assert r.status_code == 200, r.text
        assert r.json()["id"] is not None

    def test_credentials_scoped(self, client, owner_headers):
        r = client.get("/credentials", headers=owner_headers)
        assert r.status_code == 200, r.text
        # May be empty or contain creds — just verify it doesn't error


class TestTeamManagement:
    def test_list_members(self, client, owner_headers):
        r = client.get("/tenant/members", headers=owner_headers)
        assert r.status_code == 200
        emails = [m["email"] for m in r.json()]
        assert OWNER_EMAIL in emails

    def test_invite_and_list(self, client, owner_headers):
        editor_email = f"editor-{os.urandom(4).hex()}@test.com"
        r = client.post("/tenant/invite", headers=owner_headers, json={"email": editor_email})
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "editor"

        r = client.get("/tenant/members", headers=owner_headers)
        emails = [m["email"] for m in r.json()]
        assert editor_email in emails

    def test_editor_cannot_invite(self, client, owner_headers):
        # Create an editor
        editor_email = f"ed-{os.urandom(4).hex()}@test.com"
        r = client.post("/tenant/invite", headers=owner_headers, json={"email": editor_email})
        assert r.status_code == 201
        temp_pw = r.json()["temp_password"]

        # Login as editor
        r = client.post("/auth/login", json={"email": editor_email, "password": temp_pw})
        assert r.status_code == 200
        editor_token = r.json()["access_token"]

        # Try to invite
        r = client.post("/tenant/invite", headers={"Authorization": f"Bearer {editor_token}"},
                         json={"email": "x@test.com"})
        assert r.status_code == 403

    def test_remove_member(self, client, owner_headers):
        # Create member
        r = client.post("/tenant/invite", headers=owner_headers, json={"email": "toremove@test.com"})
        assert r.status_code == 201
        member_id = r.json()["id"]

        # Remove them
        r = client.delete(f"/tenant/members/{member_id}", headers=owner_headers)
        assert r.status_code == 200

        # Verify removed
        r = client.get("/tenant/members", headers=owner_headers)
        ids = [m["id"] for m in r.json()]
        assert member_id not in ids


class TestBudget:
    def test_budget_crud(self, client, owner_headers):
        # Read
        r = client.get("/tenant/budget", headers=owner_headers)
        assert r.status_code == 200
        data = r.json()
        assert "cap" in data
        assert "mode" in data

        # Update
        r = client.put("/tenant/budget", headers=owner_headers, json={"cap": 25.0, "mode": "block"})
        assert r.status_code == 200

        # Verify
        r = client.get("/tenant/budget", headers=owner_headers)
        assert r.json()["cap"] == 25.0
        assert r.json()["mode"] == "block"

        # Reset
        client.put("/tenant/budget", headers=owner_headers, json={"cap": 10.0, "mode": "warn"})
