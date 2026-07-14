from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.auth.session import get_current_tenant, require_user
from api.db.session import get_db
from api.main import app
from api.tests.conftest import MockQueryResult


@pytest.fixture
def unit_client(mock_db, mock_user, mock_tenant):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_user] = lambda: mock_user
    app.dependency_overrides[get_current_tenant] = lambda: mock_tenant
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestCurrentTenant:
    def test_get_tenant(self, unit_client):
        r = unit_client.get("/tenant")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Test Tenant"


class TestInviteMember:
    def test_owner_can_invite(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)

        r = unit_client.post("/tenant/invite", json={"email": "new@test.com"})
        assert r.status_code == 201
        data = r.json()
        assert data["role"] == "editor"
        assert "temp_password" in data
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_invite_rejects_duplicate(self, unit_client, mock_db):
        existing = MagicMock()
        existing.id = "existing-id"
        mock_db.execute.return_value = MockQueryResult(scalar_one=existing)

        r = unit_client.post("/tenant/invite", json={"email": "dup@test.com"})
        assert r.status_code == 409

    def test_editor_cannot_invite(self, unit_client, mock_db, mock_user):
        mock_user.role = "editor"
        r = unit_client.post("/tenant/invite", json={"email": "x@test.com"})
        assert r.status_code == 403


class TestListMembers:
    def test_list_members(self, unit_client, mock_db):
        m = MagicMock()
        m.id = "m1"
        m.email = "a@test.com"
        m.role = "editor"
        m.invited_by = None
        m.created_at = None

        mock_db.execute.return_value = MockQueryResult(scalars_list=[m])
        r = unit_client.get("/tenant/members")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["email"] == "a@test.com"


class TestRemoveMember:
    def test_owner_can_remove(self, unit_client, mock_db, mock_user):
        target = MagicMock()
        target.id = "member-to-remove"
        target.email = "remove@test.com"
        mock_db.execute.return_value = MockQueryResult(scalar_one=target)

        r = unit_client.delete("/tenant/members/member-to-remove")
        assert r.status_code == 200
        mock_db.delete.assert_called_once_with(target)
        mock_db.commit.assert_called_once()

    def test_cannot_remove_self(self, unit_client, mock_db, mock_user):
        mock_db.execute.return_value = MockQueryResult(scalar_one=mock_user)
        r = unit_client.delete("/tenant/members/00000000-0000-0000-0000-000000000001")
        assert r.status_code == 400

    def test_remove_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.delete("/tenant/members/unknown")
        assert r.status_code == 404

    def test_editor_cannot_remove(self, unit_client, mock_db, mock_user):
        mock_user.role = "editor"
        r = unit_client.delete("/tenant/members/any-id")
        assert r.status_code == 403
