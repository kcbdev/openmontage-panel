"""Per-provider pricing for estimate calculations."""

PIPELINE_STAGES = {
    "animated-explainer": [
        ("research", 0.02),
        ("script", 0.05),
        ("voiceover", 0.08),
        ("storyboard", 0.10),
        ("asset_gen", 0.35),
        ("edit", 0.15),
        ("publish", 0.02),
    ],
    "animation": [
        ("concept", 0.02),
        ("storyboard", 0.05),
        ("voiceover", 0.08),
        ("style_frames", 0.10),
        ("animation", 0.40),
        ("sound", 0.08),
        ("edit", 0.10),
        ("publish", 0.02),
    ],
    "cinematic": [
        ("research", 0.02),
        ("script", 0.05),
        ("storyboard", 0.05),
        ("previs", 0.15),
        ("asset_gen", 0.10),
        ("video_gen", 0.35),
        ("edit", 0.08),
        ("sound", 0.05),
        ("publish", 0.02),
    ],
    "talking-head": [
        ("research", 0.02),
        ("script", 0.05),
        ("avatar", 0.30),
        ("voiceover", 0.10),
        ("backdrop", 0.05),
        ("edit", 0.05),
        ("publish", 0.02),
    ],
    "screen-demo": [
        ("research", 0.02),
        ("script", 0.05),
        ("screen_capture", 0.25),
        ("voiceover", 0.15),
        ("edit", 0.08),
        ("publish", 0.02),
    ],
    "documentary-montage": [
        ("research", 0.05),
        ("script", 0.05),
        ("asset_sourcing", 0.15),
        ("voiceover", 0.10),
        ("edit", 0.20),
        ("sound", 0.05),
        ("publish", 0.02),
    ],
    "podcast-repurpose": [
        ("transcribe", 0.02),
        ("segment", 0.03),
        ("broll", 0.20),
        ("edit", 0.10),
        ("publish", 0.02),
    ],
    "localization-dub": [
        ("transcribe", 0.03),
        ("translate", 0.10),
        ("voiceover", 0.25),
        ("lip_sync", 0.20),
        ("edit", 0.05),
        ("publish", 0.02),
    ],
    "avatar-spokesperson": [
        ("script", 0.05),
        ("avatar", 0.35),
        ("voiceover", 0.10),
        ("backdrop", 0.05),
        ("edit", 0.05),
        ("publish", 0.02),
    ],
    "character-animation": [
        ("concept", 0.02),
        ("storyboard", 0.05),
        ("character", 0.15),
        ("animation", 0.35),
        ("voiceover", 0.10),
        ("edit", 0.08),
        ("publish", 0.02),
    ],
    "clip-factory": [
        ("source", 0.02),
        ("segment", 0.05),
        ("caption", 0.08),
        ("edit", 0.08),
        ("publish", 0.02),
    ],
    "hybrid": [
        ("research", 0.02),
        ("script", 0.05),
        ("live", 0.20),
        ("generated", 0.25),
        ("edit", 0.10),
        ("publish", 0.02),
    ],
    "framework-smoke": [
        ("init", 0.05),
        ("validate", 0.10),
        ("report", 0.02),
    ],
}

DEFAULT_PIPELINE = "animated-explainer"


def estimate(body) -> dict:
    pipeline = body.pipeline_type or DEFAULT_PIPELINE
    stages = PIPELINE_STAGES.get(pipeline, PIPELINE_STAGES[DEFAULT_PIPELINE])
    duration = max(body.duration, 15)

    base_rate = body.duration / 45.0  # normalize to 45s reference
    cost_tier = body.cost_tier or "balanced"

    tier_mult = {"free": 0.0, "balanced": 0.85, "premium": 2.50}
    tier_label = {"free": "Free (simulated only)", "balanced": "Balanced", "premium": "Premium"}
    multiplier = tier_mult.get(cost_tier, 0.85)

    line_items = []
    total = 0.0
    for stage_name, stage_weight in stages:
        stage_cost = round(stage_weight * base_rate * multiplier, 4)
        line_items.append({"stage": stage_name, "cost": stage_cost})
        total += stage_cost

    total = round(total, 2)

    provider_comparison = [
        {
            "provider": "runway",
            "label": "Runway Gen-3",
            "total_cost": round(total * 0.9, 2),
            "details": "Fast generation, good quality, standard models",
        },
        {
            "provider": "kling",
            "label": "Kling 1.6",
            "total_cost": round(total * 1.1, 2),
            "details": "Higher quality, longer generation times, superior motion",
        },
        {
            "provider": "mixed",
            "label": "Mixed (smart routing)",
            "total_cost": round(total * 1.0, 2),
            "details": "Optimizes each stage to cheapest adequate provider",
            "default": True,
        },
    ]

    return {
        "pipeline_type": pipeline,
        "duration_seconds": duration,
        "cost_tier": cost_tier,
        "tier_label": tier_label.get(cost_tier, "Balanced"),
        "estimated_cost": total,
        "currency": "USD",
        "line_items": line_items,
        "provider_comparison": provider_comparison,
    }
