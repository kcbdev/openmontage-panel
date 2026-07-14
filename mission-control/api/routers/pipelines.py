import os
from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

PIPELINE_DEFS_DIR = Path(os.environ.get("PIPELINE_DEFS_DIR", "/app/pipeline_defs"))


@router.get("")
def list_pipelines():
    pipelines = []
    if not PIPELINE_DEFS_DIR.exists():
        return []
    for f in sorted(PIPELINE_DEFS_DIR.glob("*.yaml")):
        try:
            manifest = yaml.safe_load(f.read_text())
            pipelines.append({
                "id": manifest["name"],
                "name": manifest.get("display_name", manifest["name"]),
                "description": manifest.get("description", ""),
                "best_for": manifest.get("best_for", ""),
                "category": manifest.get("category", ""),
                "stability": manifest.get("stability", ""),
                "stage_count": len(manifest.get("stages", [])),
                "stages": [
                    {
                        "name": s["name"],
                        "gated": (
                            s.get("checkpoint_required", False)
                            or s.get("human_approval_default", False)
                        ),
                    }
                    for s in manifest.get("stages", [])
                ],
            })
        except Exception:
            continue
    return pipelines


@router.get("/{pipeline_id}")
def get_pipeline(pipeline_id: str):
    for f in PIPELINE_DEFS_DIR.glob("*.yaml"):
        try:
            manifest = yaml.safe_load(f.read_text())
            if manifest.get("name") == pipeline_id:
                return manifest
        except Exception:
            continue
    return {"error": "not found"}
