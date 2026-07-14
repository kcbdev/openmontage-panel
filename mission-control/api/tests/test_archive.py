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


class TestListAssets:
    def test_list_assets(self, unit_client, mock_db):
        project = MagicMock()
        project.id = "p1"
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=project),   # project check
            MockQueryResult(scalars_list=[]),       # assets
        ]
        r = unit_client.get("/projects/p1/assets")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_assets_returns_items(self, unit_client, mock_db):
        project = MagicMock()
        project.id = "p1"
        asset = MagicMock()
        asset.id = "a1"
        asset.run_id = "r1"
        asset.stage = "storyboard"
        asset.type = "image"
        asset.storage_path = "/path/img.png"
        asset.provider_used = "openai"
        asset.cost = 0.05
        asset.is_locked = False
        asset.scene_number = 1
        asset.thumbnail_url = None
        asset.created_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=project),
            MockQueryResult(scalars_list=[asset]),
        ]
        r = unit_client.get("/projects/p1/assets")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["stage"] == "storyboard"

    def test_assets_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.get("/projects/unknown/assets")
        assert r.status_code == 404

    def test_list_assets_with_filters(self, unit_client, mock_db):
        project = MagicMock()
        project.id = "p1"
        asset = MagicMock()
        asset.id = "a1"
        asset.run_id = "r1"
        asset.stage = "scene_plan"
        asset.type = "video"
        asset.storage_path = "/path/vid.mp4"
        asset.provider_used = "runway"
        asset.cost = 0.5
        asset.is_locked = True
        asset.scene_number = None
        asset.thumbnail_url = None
        asset.created_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=project),
            MockQueryResult(scalars_list=[asset]),
        ]
        r = unit_client.get("/projects/p1/assets?stage=scene_plan&type=video")
        assert r.status_code == 200
        assert r.json()[0]["type"] == "video"


class TestDownload:
    def test_download_project(self, unit_client, mock_db):
        project = MagicMock()
        project.id = "p1"
        project.name = "Test"
        project.pipeline_type = "animated-explainer"
        project.status = "done"
        project.created_at = None

        run = MagicMock()
        run.id = "r1"
        run.status = "done"
        run.engine_version = "mc-v0"
        run.current_stage = "publish"
        run.started_at = None
        run.finished_at = None

        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=project),   # project lookup
            MockQueryResult(scalars_list=[run]),    # runs
        ]
        r = unit_client.get("/projects/p1/download")
        assert r.status_code == 200
        data = r.json()
        assert data["project"]["name"] == "Test"
        assert len(data["runs"]) == 1

    def test_download_404(self, unit_client, mock_db):
        mock_db.execute.side_effect = [
            MockQueryResult(scalar_one=None),
        ]
        r = unit_client.get("/projects/unknown/download")
        assert r.status_code == 404


class TestRemix:
    def test_remix_project(self, unit_client, mock_db):
        src = MagicMock()
        src.id = "p1"
        src.pipeline_type = "animated-explainer"
        src.render_runtime = None
        src.style_playbook = None
        src.platform_profile = None
        src.duration_target_seconds = 45

        mock_db.execute.return_value = MockQueryResult(scalar_one=src)
        r = unit_client.post("/projects/p1/remix", json={"name": "Remix"})
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "draft"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_remix_404(self, unit_client, mock_db):
        mock_db.execute.return_value = MockQueryResult(scalar_one=None)
        r = unit_client.post("/projects/unknown/remix", json={"name": "Ghost"})
        assert r.status_code == 404
