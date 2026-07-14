"""Phase 0.4 — Filesystem Bridge Spike.

Demonstrates Mission Control extracting pipeline state from the engine
without modifying engine source code. Two access paths:

  1. Direct checkpoint reads  — mounts engine's projects/ directory
  2. Backlot HTTP API         — reads from the running Backlot server

Usage:
    python spike/filesystem_bridge.py                          # dry-run
    python spike/filesystem_bridge.py --path /tmp/om/projects  # live
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Path 1: Direct checkpoint reads ─────────────────────────────────────────

CHECKPOINT_PATTERN = "checkpoint_*.json"


def discover_projects(projects_dir: Path) -> list[Path]:
    """List project directories under the engine's projects/ root."""
    if not projects_dir.is_dir():
        return []
    return sorted(
        p for p in projects_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def read_checkpoint(project_dir: Path, stage: str) -> Optional[dict]:
    """Read a single stage checkpoint (read-only, defensive)."""
    path = project_dir / f"checkpoint_{stage}.json"
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["_mtime"] = path.stat().st_mtime
            data["_stage"] = stage
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def read_all_checkpoints(project_dir: Path) -> dict[str, dict]:
    """Read all checkpoints in a project (sorted by filename)."""
    out: dict[str, dict] = {}
    for path in sorted(project_dir.glob(CHECKPOINT_PATTERN)):
        stage = path.stem[len("checkpoint_"):]
        cp = read_checkpoint(project_dir, stage)
        if cp is not None:
            out[stage] = cp
    return out


def read_artifact(project_dir: Path, path_str: str) -> Optional[dict]:
    """Read a referenced artifact file, enforcing project-boundary safety."""
    p = Path(path_str)
    if not p.is_absolute():
        p = project_dir / p
    try:
        p.resolve().relative_to(Path(project_dir).resolve())
    except (ValueError, OSError):
        return None  # path escape attempt
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def derive_board_state(project_dir: Path) -> dict[str, Any]:
    """Replicate Backlot's board-state derivation (read-only)."""
    checkpoints = read_all_checkpoints(project_dir)
    stages = []
    for stage_name in [
        "research", "proposal", "script", "scene_plan",
        "assets", "edit", "compose", "publish",
    ]:
        cp = checkpoints.get(stage_name)
        status = cp.get("status", "pending") if cp else "pending"
        stages.append({
            "name": stage_name,
            "status": status,
            "timestamp": cp.get("timestamp") if cp else None,
            "mtime": cp.get("_mtime") if cp else None,
        })

    # Activity window: most recent checkpoint mod time
    mtimes = [cp["_mtime"] for cp in checkpoints.values() if "_mtime" in cp]
    now = time.time()
    active_secs = now - max(mtimes) if mtimes else None
    return {
        "project": project_dir.name,
        "stages": stages,
        "checkpoint_count": len(checkpoints),
        "last_activity_ago_seconds": active_secs,
        "idle": active_secs is not None and active_secs > 300,
    }


# ── Path 2: Backlot HTTP API ────────────────────────────────────────────────

def fetch_backlot_state(
    base_url: str = "http://localhost:8765",
    project_id: Optional[str] = None,
) -> Optional[dict]:
    """Fetch board state from a running Backlot server."""
    import urllib.request
    try:
        path = f"/api/projects/{project_id}" if project_id else "/api/projects"
        with urllib.request.urlopen(f"{base_url}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"_error": str(exc)}


# ── Spike demo ──────────────────────────────────────────────────────────────

SAMPLE_CHECKPOINT = {
    "status": "completed",
    "timestamp": "2026-07-14T12:00:00Z",
    "stage": "research",
    "artifact": {
        "title": "How Neural Networks Learn",
        "data_points": [
            {"text": "Neural networks process data through layers of interconnected nodes",
             "source": "3Blue1Brown — But what is a neural network?"},
        ],
        "angles_discovered": ["biological analogy", "mathematical foundation"],
        "sources": [
            "https://example.com/neural-network-basics",
        ],
    },
}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Filesystem Bridge Spike")
    parser.add_argument("--path", default=None,
                        help="Path to engine projects/ directory")
    parser.add_argument("--backlot", default=None,
                        help="Backlot server URL (e.g. http://localhost:8765)")
    parser.add_argument("--demo-project", default="demo-video",
                        help="Project name for demo checkpoints")
    args = parser.parse_args()

    # ── Path 1: Direct filesystem reads ────────────────────────────────
    print("=" * 60)
    print("PATH 1: Direct Checkpoint Reads")
    print("=" * 60)

    if args.path:
        projects_dir = Path(args.path)
        projects = discover_projects(projects_dir)
        if not projects:
            print(f"  No projects found under {projects_dir} (empty or missing)")
        else:
            for p in projects:
                state = derive_board_state(p)
                print(f"\n  Project: {p.name}")
                for s in state["stages"]:
                    print(f"    {s['status']:>12}  {s['name']}")
                print(f"  Active: {'no' if state['idle'] else 'yes'} "
                      f"(last activity {state['last_activity_ago_seconds']}s ago)")
    else:
        # Demo mode: prove the read/write contracts work
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / args.demo_project
            proj.mkdir(parents=True)

            # Write a sample checkpoint (as the engine would)
            cp_path = proj / f"checkpoint_research.json"
            cp_path.write_text(
                json.dumps(SAMPLE_CHECKPOINT, indent=2)
            )
            print(f"  Wrote sample checkpoint → {cp_path}")

            # Mission Control reads it back
            checkpoints = read_all_checkpoints(proj)
            print(f"  Read {len(checkpoints)} checkpoint(s)")

            state = derive_board_state(proj)
            print(f"  Derived board state:")
            for s in state["stages"]:
                print(f"    {s['status']:>12}  {s['name']}")

            # Prove artifact extraction
            art_path = proj / "artifacts" / "research_brief.json"
            art_path.parent.mkdir()
            art_path.write_text(json.dumps({
                "research_brief": {
                    "title": SAMPLE_CHECKPOINT["artifact"]["title"],
                    "data_points": SAMPLE_CHECKPOINT["artifact"]["data_points"],
                }
            }))
            print(f"\n  Artifact extraction demo:")
            artifact = read_artifact(proj, "artifacts/research_brief.json")
            if artifact:
                print(f"    Loaded artifact: {list(artifact.keys())}")

            # Path escape guard demo
            print(f"    Path-escape blocked: {read_artifact(proj, '../../etc/passwd')}")

    # ── Path 2: Backlot HTTP API ───────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("PATH 2: Backlot HTTP API")
    print("=" * 60)
    if args.backlot:
        state = fetch_backlot_state(args.backlot)
        if state and "_error" in state:
            print(f"  Backlot not reachable: {state['_error']}")
        else:
            print(f"  Backlot state: {json.dumps(state, indent=2)[:500]}")
    else:
        print("  (no --backlot URL provided — skipping)")


if __name__ == "__main__":
    main()
