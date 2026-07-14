import logging
import os

import httpx

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


async def send_slack(payload: dict) -> bool:
    if not SLACK_WEBHOOK_URL:
        logger.debug("no SLACK_WEBHOOK_URL configured, skipping slack notification")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(SLACK_WEBHOOK_URL, json=payload)
            r.raise_for_status()
        logger.info("slack notification sent")
        return True
    except Exception as exc:
        logger.warning("slack notification failed: %s", exc)
        return False


async def notify_gate_created(run_id: str, stage: str, gate_type: str, required_role: str):
    await send_slack({
        "text": f"*Approval Required* — {stage}\n"
                f"Run: `{run_id}`\n"
                f"Gate: `{gate_type}` — requires *{required_role}* role\n"
                f"Action required: approve, revise, or reject.",
    })


async def notify_gate_resolved(run_id: str, stage: str, status: str):
    emoji = {"approved": ":white_check_mark:", "revision_requested": ":arrows_counterclockwise:",
             "rejected": ":x:"}.get(status, ":grey_question:")
    await send_slack({
        "text": f"{emoji} Gate *{status}* — {stage}\nRun: `{run_id}`",
    })


async def notify_anomaly(run_id: str, reason: str, stage: str | None):
    await send_slack({
        "text": f":warning: *Run Failed* — Anomaly\n"
                f"Run: `{run_id}`\n"
                f"Stage: `{stage or 'unknown'}`\n"
                f"Reason: {reason}",
    })


async def notify_done(run_id: str, finished_at: str | None):
    await send_slack({
        "text": f":rocket: *Run Complete*\n"
                f"Run: `{run_id}`\n"
                f"Finished: {finished_at or 'now'}",
    })
