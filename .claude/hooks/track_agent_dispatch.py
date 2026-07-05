#!/usr/bin/env python3
"""PostToolUse hook for AuroraIA-v2 multi-agent tracker.

Captures every Task (Agent) tool invocation and persists it to
.claude/agent-tracker/state.json. The hook is idempotent and silent on
success — if it can't write the tracker (permission, malformed JSON), it
prints a one-line warning to stderr and exits 0 so the harness keeps going.

Hook receives JSON on stdin with fields:
  hook_event_name: "PostToolUse"
  tool_name:       "Task"
  tool_input:      { description, prompt, subagent_type? }
  tool_response:   { ... }     # may be absent on PreToolUse

We only care when tool_name == "Task". Everything else is a no-op.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / ".claude" / "agent-tracker" / "state.json"
HISTORY_DIR = REPO_ROOT / ".claude" / "agent-tracker" / "history"
KNOWN_AGENTS = {
    "aurora-orchestrator",
    "conversation-lead", "conversation-pipeline-tuner",
    "image-lead", "image-flux-stylist", "image-reference-researcher",
    "code-lead", "code-fidelity-auditor", "code-sandbox-runner", "code-design-architect",
    "video-lead", "video-motion-director", "video-talking-head",
    "drawing-lead", "drawing-sketch-interpreter",
    "3d-lead", "3d-pipeline-router", "3d-motion-rigger", "3d-mesh-postprocessor",
    "3d-quality-rescuer",
    "learning-lead", "learning-quiz-verifier", "learning-bac-curator",
    "cowork-lead", "cowork-orchestrator-tuner", "cowork-connector-keeper", "cowork-safety-auditor",
    "voice-lead", "voice-tts-stt-tuner", "voice-lipsync",
    "cyber-lead", "cyber-lab-builder", "cyber-pyops-keeper",
    "simulator-lead", "simulator-physics-engine", "simulator-scene-io",
    "tunnel-validator", "bridge-doctor",
}


def warn(msg: str) -> None:
    sys.stderr.write(f"[agent-tracker] {msg}\n")


def load_state() -> dict:
    if not TRACKER.exists():
        return {
            "schema_version": "aurora.tracker.v1",
            "updated_at": now_iso(),
            "session_goal": None,
            "tasks": [],
            "tunnel_validated": False,
            "last_commit": None,
            "leads": {},
            "crosscut": [],
        }
    try:
        return json.loads(TRACKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"could not read state.json ({exc}); starting fresh")
        return {"schema_version": "aurora.tracker.v1", "tasks": []}


MAX_TASKS = 50          # cap before rotating to history
ROTATE_KEEP = 25        # keep this many recent tasks after rotation


def rotate_history(state: dict) -> None:
    """When tasks list exceeds MAX_TASKS, archive the oldest closed ones to
    .claude/agent-tracker/history/<timestamp>.json and keep ROTATE_KEEP newest."""
    tasks = state.get("tasks") or []
    if len(tasks) <= MAX_TASKS:
        return
    closed = [i for i, t in enumerate(tasks) if t.get("status") in ("done", "blocked")]
    if len(tasks) - len(closed) > ROTATE_KEEP:
        # Too many in-flight to safely rotate; leave alone.
        return
    overflow = max(0, len(tasks) - ROTATE_KEEP)
    archive, kept = tasks[:overflow], tasks[overflow:]
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    archive_path = HISTORY_DIR / f"tasks-{stamp}.json"
    try:
        archive_path.write_text(
            json.dumps({"archived_at": now_iso(), "tasks": archive}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        warn(f"could not archive tasks ({exc}); keeping in-place")
        return
    state["tasks"] = kept


def save_state(state: dict) -> None:
    state["updated_at"] = now_iso()
    rotate_history(state)
    TRACKER.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRACKER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, TRACKER)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def truncate(text: str, n: int = 240) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        warn(f"bad hook payload ({exc})")
        return 0

    if payload.get("tool_name") != "Task":
        return 0

    tool_input = payload.get("tool_input") or {}
    subagent = tool_input.get("subagent_type") or "general-purpose"
    if subagent not in KNOWN_AGENTS:
        return 0

    description = tool_input.get("description") or ""
    prompt = tool_input.get("prompt") or ""
    response = payload.get("tool_response") or {}
    event = payload.get("hook_event_name", "")

    state = load_state()
    state.setdefault("tasks", [])

    if event == "PreToolUse":
        state["tasks"].append({
            "id": f"t{uuid.uuid4().hex[:8]}",
            "lead": subagent,
            "brief": truncate(description or prompt),
            "status": "in_progress",
            "started_at": now_iso(),
            "finished_at": None,
            "verdict": None,
            "files_touched": [],
        })
    else:
        match = next(
            (t for t in reversed(state["tasks"])
             if t.get("lead") == subagent and t.get("status") == "in_progress"),
            None,
        )
        if match is None:
            match = {
                "id": f"t{uuid.uuid4().hex[:8]}",
                "lead": subagent,
                "brief": truncate(description or prompt),
                "status": "in_progress",
                "started_at": now_iso(),
                "finished_at": None,
                "verdict": None,
                "files_touched": [],
            }
            state["tasks"].append(match)
        match["finished_at"] = now_iso()
        match["status"] = "done" if not response.get("error") else "blocked"
        match["verdict"] = truncate(str(response.get("error") or "ok"))

    try:
        save_state(state)
    except OSError as exc:
        warn(f"could not write state.json ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
