"""Phase 0.3 — Headless Driver Spike.

Proves that Mission Control can drive an OpenMontage pipeline end-to-end
via OpenRouter, reading stage skills as system prompts and routing each
stage to the correct model per MODEL_ROUTING config.

Usage:
    OPENROUTER_API_KEY=sk-... python spike/headless_driver.py

Environment:
    OPENROUTER_API_KEY    — OpenRouter API key
    MODEL_ROUTING         — optional JSON override: {stage_name: model_id}
    DEFAULT_MODEL         — fallback model (default: openai/gpt-4o-mini)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # dry-run mode without openai installed

ENGINE_ROOT = Path("/app")  # inside container
ENGINE_ROOT_DEV = Path("/tmp/openmontage-clone")  # host-side for spike

CANONICAL_STAGES = [
    "research", "proposal", "script", "scene_plan",
    "assets", "edit", "compose", "publish",
]

MODEL_ROUTING_DEFAULT: dict[str, str] = {
    "research":    "anthropic/claude-haiku-4.5",
    "proposal":    "anthropic/claude-sonnet-4.5",
    "script":      "anthropic/claude-sonnet-4.5",
    "scene_plan":  "openai/gpt-4o",
    "assets":      "openai/gpt-4o",
    "edit":        "anthropic/claude-haiku-4.5",
    "compose":     "openai/gpt-4o",
    "publish":     "anthropic/claude-haiku-4.5",
}

FALLBACK_MODEL = "openai/gpt-4o-mini"


def load_pipeline_manifest(pipeline: str) -> dict[str, Any]:
    path = ENGINE_ROOT / "pipeline_defs" / f"{pipeline}.yaml"
    dev_path = ENGINE_ROOT_DEV / "pipeline_defs" / f"{pipeline}.yaml"

    # Try host-side first (spike mode), then container
    p = dev_path if dev_path.exists() else path
    if not p.exists():
        raise FileNotFoundError(f"Pipeline manifest not found: {p}")

    import yaml
    with open(p) as f:
        return yaml.safe_load(f)


def load_skill_content(pipeline: str, stage: str) -> str:
    path = ENGINE_ROOT / "skills" / "pipelines" / pipeline / f"{stage}-director.md"
    dev_path = ENGINE_ROOT_DEV / "skills" / "pipelines" / pipeline / f"{stage}-director.md"
    p = dev_path if dev_path.exists() else path
    if not p.exists():
        return f"# {stage}-director\n\n(No skill file found at {p})"
    return p.read_text()


def load_checkpoint_skill() -> str:
    p = ENGINE_ROOT / "skills" / "meta" / "checkpoint-protocol.md"
    dev_p = ENGINE_ROOT_DEV / "skills" / "meta" / "checkpoint-protocol.md"
    fp = dev_p if dev_p.exists() else p
    if fp.exists():
        return fp.read_text()
    return ""


def load_agent_guide() -> str:
    p = ENGINE_ROOT / "AGENT_GUIDE.md"
    dev_p = ENGINE_ROOT_DEV / "AGENT_GUIDE.md"
    fp = dev_p if dev_p.exists() else p
    if fp.exists():
        return fp.read_text()
    return ""


# ── OpenRouter Session ──────────────────────────────────────────────────────

def decide_model(stage: str, routing: dict[str, str]) -> str:
    return routing.get(stage, FALLBACK_MODEL)


def create_session() -> Any:
    if OpenAI is None:
        raise RuntimeError("openai package not installed — install with: pip install openai")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/calesthio/OpenMontage",
            "X-Title": "OpenMontage Mission Control - Headless Driver Spike",
        },
    )


def call_llm(
    client: Any,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 4096,
) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


# ── Checkpoint / Approval Helpers ───────────────────────────────────────────

def write_checkpoint(stage: str, artifact: dict) -> None:
    dest = Path(".om/checkpoints") / f"{stage}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps({"stage": stage, "artifact": artifact}, indent=2)
    )
    print(f"  [checkpoint] wrote {dest}")


def read_checkpoint(stage: str) -> dict | None:
    p = Path(".om/checkpoints") / f"{stage}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def simulate_human_approval(stage: str) -> bool:
    print(f"\n  ⏸── HUMAN CHECKPOINT: {stage} ────────────────────")
    print("  Stage complete. Press Enter to approve, 'r' to reject: ", end="")
    choice = input().strip().lower()
    return choice != "r"


# ── Pipeline Runner ─────────────────────────────────────────────────────────

def run_pipeline(pipeline: str, topic: str, routing: dict[str, str]) -> None:
    manifest = load_pipeline_manifest(pipeline)
    stages = [s["name"] for s in manifest.get("stages", [])]
    print(f"Loaded pipeline '{manifest['name']}' ({len(stages)} stages)")
    print(f"Topic: {topic}\n")

    # Bootstrap checkpoint — previous stages' artifacts accumulate
    context = {"topic": topic}

    agent_guide = load_agent_guide()
    checkpoint_skill = load_checkpoint_skill()

    for i, stage in enumerate(stages):
        model = decide_model(stage, routing)
        print(f"\n{'='*60}")
        print(f"STAGE {i+1}/{len(stages)}: {stage}  →  {model}")

        skill_content = load_skill_content(pipeline, stage)

        # Build system prompt from AGENT_GUIDE + checkpoint protocol + stage skill
        system_parts = []
        if agent_guide:
            system_parts.append(agent_guide)
        if checkpoint_skill:
            system_parts.append(checkpoint_skill)
        system_parts.append(
            f"You are the {stage}-director for the {pipeline} pipeline.\n"
            f"Your job is to produce a valid {stage} artifact.\n"
            f"---\n{skill_content}"
        )
        system_prompt = "\n\n---\n\n".join(system_parts)

        user_prompt = json.dumps({
            "stage": stage,
            "pipeline": pipeline,
            "context": {
                k: v for k, v in context.items()
                if not k.startswith("_")
            },
            "instructions": (
                f"Execute the {stage} stage of the {pipeline} pipeline. "
                f"Produce the {stage} artifact as valid JSON matching the schema, "
                f"then write a checkpoint."
            ),
        }, indent=2)

        if not os.environ.get("OPENROUTER_API_KEY"):
            print("  [SKIP] No OPENROUTER_API_KEY set — printing prompt instead")
            print(f"  System prompt ({len(system_prompt)} chars)")
            print(f"  User prompt:\n{user_prompt[:2000]}")
            print()
            write_checkpoint(stage, {"_dry_run": True, "_model": model})
            continue

        result = call_llm(create_session(), model, system_prompt, user_prompt)
        print(f"  Result ({len(result)} chars)")

        try:
            artifact = json.loads(result)
        except json.JSONDecodeError:
            artifact = {"_raw": result}

        write_checkpoint(stage, artifact)
        context[f"{stage}_artifact"] = artifact

        # Approval gate
        stage_def = manifest["stages"][i]
        if stage_def.get("checkpoint_required"):
            approved = simulate_human_approval(stage)
            if not approved:
                print(f"\n  ✗ Stage '{stage}' rejected by human. Pipeline paused.")
                break
            print("  ✓ Approved")

    print(f"\nPipeline '{pipeline}' finished.")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="OpenMontage Headless Driver Spike")
    parser.add_argument("--pipeline", default="animated-explainer",
                        help="Pipeline name (default: animated-explainer)")
    parser.add_argument("--topic", default="How neural networks learn",
                        help="Video topic / user request")
    parser.add_argument("--model-routing", default=None,
                        help="JSON string overriding MODEL_ROUTING per stage")
    args = parser.parse_args()

    routing = MODEL_ROUTING_DEFAULT.copy()
    if args.model_routing:
        routing.update(json.loads(args.model_routing))
    env_override = os.environ.get("MODEL_ROUTING")
    if env_override:
        routing.update(json.loads(env_override))

    print(f"Model routing: {json.dumps(routing, indent=2)}")
    run_pipeline(args.pipeline, args.topic, routing)


if __name__ == "__main__":
    main()
