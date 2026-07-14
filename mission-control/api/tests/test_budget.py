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


class TestBudgetDefaults:
    def test_get_budget(self, unit_client, mock_tenant):
        mock_tenant.budget_cap_default = 25.0
        mock_tenant.budget_mode_default = "block"
        r = unit_client.get("/tenant/budget")
        assert r.status_code == 200
        assert r.json()["cap"] == 25.0
        assert r.json()["mode"] == "block"

    def test_update_budget(self, unit_client, mock_db):
        r = unit_client.put("/tenant/budget", json={"cap": 50.0, "mode": "block"})
        assert r.status_code == 200
        mock_db.commit.assert_called_once()


class TestBudgetLedger:
    def test_get_ledger_empty(self, unit_client, mock_db):
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_value=0),   # count
            MockQueryResult(scalars_list=[]),  # entries
        ]
        r = unit_client.get("/tenant/budget/ledger")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["entries"] == []

    def test_get_ledger_paginated(self, unit_client, mock_db):
        entry = MagicMock()
        entry.id = "e1"
        entry.project_id = "p1"
        entry.run_id = "r1"
        entry.action = "scene_gen"
        entry.estimated_cost = 1.0
        entry.actual_cost = 0.85
        entry.mode = "warn"
        entry.created_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_value=5),     # total count
            MockQueryResult(scalars_list=[entry]),  # entries
        ]
        r = unit_client.get("/tenant/budget/ledger?offset=0&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["entries"]) == 1
        assert data["entries"][0]["action"] == "scene_gen"

    def test_ledger_respects_limit_cap(self, unit_client, mock_db):
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_value=0),
            MockQueryResult(scalars_list=[]),
        ]
        r = unit_client.get("/tenant/budget/ledger?limit=999")
        assert r.status_code == 200
        # server caps at 100
        assert r.json()["limit"] == 100


class TestBudgetSummary:
    def test_summary_empty(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalars_list=[])
        r = unit_client.get("/tenant/budget/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_spent"] == 0
        assert data["projects"] == []

    def test_summary_with_projects(self, unit_client, mock_db):
        row = MagicMock()
        row.project_id = "p1"
        row.total_spent = 5.0
        row.total_reserved = 8.0
        row.entries_count = 3
        proj = MagicMock()
        proj.id = "p1"
        proj.name = "My Project"

        mock_db.execute.side_effect = [
            MockQueryResult(scalars_list=[row]),   # aggregation query
            MockQueryResult(scalars_list=[proj]),   # project name lookup
        ]
        r = unit_client.get("/tenant/budget/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_spent"] == 5.0
        assert data["total_reserved"] == 8.0
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "My Project"


class TestBudgetSync:
    def test_sync_ledger(self, unit_client, mock_db):
        r = unit_client.post("/tenant/budget/ledger/sync", json=[{
            "project_id": "00000000-0000-0000-0000-000000000100",
            "run_id": "00000000-0000-0000-0000-000000000200",
            "action": "scene_gen",
            "estimated_cost": 1.0,
            "actual_cost": 0.85,
            "mode": "warn",
        }])
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "synced"
        assert data["count"] == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
