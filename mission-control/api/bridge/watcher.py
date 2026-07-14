import json
import logging
import os
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class CheckpointHandler(FileSystemEventHandler):
    def __init__(self, run_id: str, project_dir: str, on_checkpoint: Callable, on_gate: Callable, on_stall: Callable):
        self.run_id = run_id
        self.project_dir = project_dir
        self.on_checkpoint = on_checkpoint
        self.on_gate = on_gate
        self.on_stall = on_stall
        self._last_activity = time.time()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        self._last_activity = time.time()

        if path.name.startswith("checkpoint_") and path.suffix == ".json":
            try:
                data = json.loads(path.read_text())
                self.on_checkpoint(self.run_id, data)
            except Exception as e:
                logger.error("bridge: failed to read checkpoint %s: %s", path.name, e)

        elif path.name == "pending_decision.json":
            try:
                data = json.loads(path.read_text())
                self.on_gate(self.run_id, data)
            except Exception as e:
                logger.error("bridge: failed to read gate %s: %s", path.name, e)

    def on_modified(self, event):
        self._last_activity = time.time()

    @property
    def seconds_since_activity(self) -> float:
        return time.time() - self._last_activity


async def watch_run(run_id: str, project_dir: str, on_checkpoint: Callable, on_gate: Callable, on_stall: Callable):
    os.makedirs(project_dir, exist_ok=True)
    handler = CheckpointHandler(run_id, project_dir, on_checkpoint, on_gate, on_stall)
    observer = Observer()
    observer.schedule(handler, project_dir, recursive=False)
    observer.start()
    return observer, handler
