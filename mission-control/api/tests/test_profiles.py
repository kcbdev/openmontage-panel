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


class TestMissionProfiles:
    def test_list_empty(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalars_list=[])
        r = unit_client.get("/mission-profiles")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_items(self, unit_client, mock_db):
        p = MagicMock()
        p.id = "prof-1"
        p.name = "Test Profile"
        p.pipeline_type = "animated-explainer"
        p.params = {"quality": "high"}
        p.created_at = None

        mock_db.execute.return_value = MockQueryResult(scalars_list=[p])
        r = unit_client.get("/mission-profiles")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Profile"

    def test_create_profile(self, unit_client, mock_db):
        r = unit_client.post("/mission-profiles", json={
            "name": "New Profile",
            "pipeline_type": "animated-explainer",
            "params": {"quality": "high"},
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "New Profile"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_delete_profile(self, unit_client, mock_db):
        profile = MagicMock()
        profile.id = "prof-1"
        mock_db.execute.return_value = MockQueryResult(scalar_one=profile)

        r = unit_client.delete("/mission-profiles/prof-1")
        assert r.status_code == 200
        mock_db.delete.assert_called_once_with(profile)
        mock_db.commit.assert_called_once()

    def test_delete_profile_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.delete("/mission-profiles/unknown")
        assert r.status_code == 404


class TestCloneStyle:
    def test_clone_style(self, unit_client, mock_db):
        r = unit_client.post("/styles/clone", json={
            "name": "Cloned Style",
            "source_playbook_id": "src-1",
            "yaml_content": "key: value",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Cloned Style"
        assert data["source_playbook_id"] == "src-1"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
