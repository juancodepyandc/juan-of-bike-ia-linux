"""Persistent state for the Aurora code generation CLI."""
from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / "code_loop_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": [], "attempts": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
