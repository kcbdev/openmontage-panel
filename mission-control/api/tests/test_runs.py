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


def _mock_run(**kw):
    r = MagicMock()
    for k, v in kw.items():
        setattr(r, k, v)
    return r


class TestRunState:
    def test_returns_state_with_checkpoints(self, unit_client, mock_db):
        run = _mock_run(
            id="run-1", status="awaiting_checkpoint", current_stage="storyboard",
            anomaly_reason=None,
        )
        cp = MagicMock()
        cp.stage = "storyboard"
        cp.checkpoint_json = {"stage": "storyboard"}
        cp.cost_snapshot_json = None
        cp.created_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=run),      # run lookup
            MockQueryResult(scalars_list=[cp]),    # checkpoints
        ]
        with patch("api.bridge.state.derive_board_state", return_value={"scenes": []}):
            r = unit_client.get("/runs/run-1/state")

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "awaiting_checkpoint"
        assert data["last_checkpoint"]["stage"] == "storyboard"

    def test_returns_404_for_missing_run(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.get("/runs/unknown/state")
        assert r.status_code == 404

    def test_returns_state_no_checkpoints(self, unit_client, mock_db):
        run = _mock_run(id="run-1", status="provisioning", current_stage=None, anomaly_reason=None)
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=run),
            MockQueryResult(scalars_list=[]),
        ]
        r = unit_client.get("/runs/run-1/state")
        assert r.status_code == 200
        assert r.json()["last_checkpoint"] is None


class TestRunAssets:
    def test_list_assets(self, unit_client, mock_db):
        a = MagicMock()
        a.id = "asset-1"
        a.run_id = "run-1"
        a.stage = "scene_plan"
        a.type = "image"
        a.storage_path = "/path/to/img"
        a.provider_used = "openai"
        a.cost = 0.05
        a.is_locked = False
        a.created_at = None

        mock_db.execute.return_value = MockQueryResult(scalars_list=[a])
        r = unit_client.get("/runs/run-1/assets")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["stage"] == "scene_plan"

    def test_toggle_lock(self, unit_client, mock_db):
        asset = MagicMock()
        asset.id = "asset-1"
        asset.is_locked = False
        mock_db.execute.return_value = MockQueryResult(scalar_one=asset)

        r = unit_client.post("/runs/run-1/assets/asset-1/lock")
        assert r.status_code == 200
        assert r.json()["is_locked"] is True
        mock_db.commit.assert_called_once()

    def test_toggle_lock_not_found(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.post("/runs/run-1/assets/unknown/lock")
        assert r.status_code == 404


class TestResumeRun:
    def test_resume_approve(self, unit_client, mock_db):
        run = _mock_run(id="run-1", status="awaiting_approval", current_stage="storyboard")
        gate = MagicMock()
        gate.id = "gate-1"
        gate.required_role = "editor"
        gate.resolved_by = None
        gate.resolved_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=run),   # run lookup
            MockQueryResult(scalar_one=gate),  # gate lookup
            MockQueryResult(scalar_one=gate),  # gate re-query for update
        ]
        with patch("api.routers.runs.GraphManager") as mock_gm:
            gm = AsyncMock()
            mock_gm.return_value = gm

            r = unit_client.post("/runs/run-1/resume", json={"decision": "approve"})

        assert r.status_code == 200
        assert r.json()["decision"] == "approve"
        gm.resume_run.assert_called_once()
    def test_resume_requires_role(self, unit_client, mock_db, mock_user):
        mock_user.role = "viewer"
        run = _mock_run(id="run-1", status="awaiting_approval")
        gate = MagicMock()
        gate.id = "gate-1"
        gate.required_role = "editor"
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=run),
            MockQueryResult(scalar_one=gate),
        ]
        r = unit_client.post("/runs/run-1/resume", json={"decision": "approve"})
        assert r.status_code == 403

    def test_resume_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.post("/runs/run-1/resume", json={"decision": "approve"})
        assert r.status_code == 404


class TestRetryRun:
    def test_retry_anomaly(self, unit_client, mock_db):
        run = _mock_run(id="run-1", status="anomaly", anomaly_reason="oops")
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=run),   # run lookup
        ]
        with patch("api.routers.runs.GraphManager") as mock_gm:
            gm = AsyncMock()
            mock_gm.return_value = gm
            r = unit_client.post("/runs/run-1/retry", json={"provider_override": "openai"})

        assert r.status_code == 200
        assert r.json()["status"] == "awaiting_checkpoint"
        gm.resume_run.assert_called_once()

    def test_retry_non_anomaly_rejected(self, unit_client, mock_db):
        run = _mock_run(id="run-1", status="running")
        mock_db.execute.return_value = MockQueryResult(scalar_one=run)
        r = unit_client.post("/runs/run-1/retry", json={})
        assert r.status_code == 400

    def test_retry_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.post("/runs/run-1/retry", json={})
        assert r.status_code == 404


class TestCheckpoints:
    def test_list_checkpoints(self, unit_client, mock_db):
        cp = MagicMock()
        cp.id = "cp-1"
        cp.stage = "storyboard"
        cp.checkpoint_json = {"stage": "storyboard"}
        cp.decision_log_json = None
        cp.created_at = None

        mock_db.execute.return_value = MockQueryResult(scalars_list=[cp])
        r = unit_client.get("/runs/run-1/checkpoints")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["stage"] == "storyboard"
