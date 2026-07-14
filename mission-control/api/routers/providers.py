import json
import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/providers", tags=["providers"])

CACHE_PATH = Path(os.environ.get("PROVIDER_MENU_CACHE", "/app/static/provider_menu.json"))


@router.get("/menu")
def provider_menu():
    if not CACHE_PATH.exists():
        return {"error": "provider menu not available"}
    return json.loads(CACHE_PATH.read_text())
