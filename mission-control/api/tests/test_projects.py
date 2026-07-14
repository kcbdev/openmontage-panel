from unittest.mock import AsyncMock, MagicMock, patch

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


class TestEstimate:
    def test_estimate_basic(self, unit_client):
        r = unit_client.post("/projects/estimate", json={
            "brief": "test brief", "duration": 45, "pipeline_type": "animated-explainer",
        })
        assert r.status_code == 200
        data = r.json()
        assert "estimated_cost" in data
        assert data["currency"] == "USD"

    def test_estimate_premium(self, unit_client):
        r = unit_client.post("/projects/estimate", json={
            "brief": "premium", "cost_tier": "premium",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["estimated_cost"] > 0
        assert "line_items" in data
        assert "provider_comparison" in data
        assert data["pipeline_type"] == "animated-explainer"


class TestCreateProject:
    def test_creates_project_and_run(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_value=0)
        with patch("api.routers.projects.GraphManager") as mock_gm:
            gm_instance = AsyncMock()
            mock_gm.return_value = gm_instance

            r = unit_client.post("/projects", json={
                "name": "Test Project",
                "pipeline_type": "animated-explainer",
            })

        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "provisioning"
        assert "project_id" in data
        assert "run_id" in data
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        gm_instance.start_run.assert_called_once()

    def test_rejects_when_at_max_concurrency(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_value=3)
        r = unit_client.post("/projects", json={"name": "Overloaded"})
        assert r.status_code == 429
        assert "max concurrent runs" in r.text


class TestListAndGet:
    def test_list_projects_returns_empty(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalars_list=[])
        r = unit_client.get("/projects")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_projects_returns_items(self, unit_client, mock_db):
        p = MagicMock()
        p.id = "p1"
        p.name = "Proj A"
        p.pipeline_type = "animated-explainer"
        p.status = "provisioning"
        p.created_at = None
        mock_db.execute.return_value = MockQueryResult(scalars_list=[(p, "run-1")])
        r = unit_client.get("/projects")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "Proj A"

    def test_get_project_found(self, unit_client, mock_db):
        p = MagicMock()
        p.id = "p1"
        p.name = "Found"
        p.pipeline_type = "animated-explainer"
        p.status = "done"
        p.render_runtime = None
        p.style_playbook = None
        p.platform_profile = None
        p.duration_target_seconds = 45
        p.created_at = None
        mock_db.execute.return_value = MockQueryResult(scalar_one=p)
        r = unit_client.get("/projects/p1")
        assert r.status_code == 200
        assert r.json()["name"] == "Found"

    def test_get_project_not_found(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.get("/projects/p-unknown")
        assert r.status_code == 404


class TestAuth:
    def test_401_without_token(self):
        """Verify endpoint is protected — dependency override removed."""
        client = TestClient(app)
        r = client.get("/projects")
        assert r.status_code == 401
