#!/usr/bin/env python
"""Aurora tracker write-side from Python tools (rescue chain, pipeline, etc.)

Provides `record_dispatch()` which appends a single task entry to
`.claude/agent-tracker/state.json` so the agent_metrics dashboard counts
real Python work — not just hook-driven assistant Task() invocations.

The tracker schema is defined by .claude/hooks/track_agent_dispatch.py.
We mirror its essential fields here without importing across trees:

    {
      "id": "t<8-hex>",
      "lead": "<agent name>",
      "brief": "<short label>",
      "status": "done" | "blocked" | "in_progress",
      "started_at": "<iso utc>",
      "finished_at": "<iso utc> | null",
      "verdict": "<short msg or 'ok'>",
      "files_touched": [<paths>]
    }

Best-effort: if the tracker file can't be written (permissions, malformed
JSON, race), the helper returns None and never raises into the caller.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRACKER = _REPO_ROOT / ".claude" / "agent-tracker" / "state.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _truncate(text: str, n: int = 240) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def record_dispatch(
    lead: str,
    brief: str,
    *,
    started_at: str | None = None,
    finished_at: str | None = None,
    verdict: str = "ok",
    status: str = "done",
    files_touched: list[str] | None = None,
    metadata: dict | None = None,
    tracker_path: Path = _TRACKER,
) -> dict | None:
    """Append a tracker task entry. Returns the entry on success, None on
    soft failure. Never raises — the rescue chain must not break on
    bookkeeping.

    `metadata` is a free-form audit dict (run_id, score_delta, kind, etc.)
    that the dashboard uses to drill from agent → run → score sparkline.
    Keys are JSON-serializable scalars or short lists. Capped at ~32 keys
    / 4KB per entry to keep state.json bounded."""
    entry = {
        "id": f"t{uuid.uuid4().hex[:8]}",
        "lead": str(lead),
        "brief": _truncate(str(brief)),
        "status": status,
        "started_at": started_at or _now_iso(),
        "finished_at": finished_at or (_now_iso() if status != "in_progress" else None),
        "verdict": _truncate(str(verdict)),
        "files_touched": list(files_touched or []),
    }
    if metadata:
        # Defensive: only persist a small, serializable subset.
        clean: dict = {}
        for i, (k, v) in enumerate(dict(metadata).items()):
            if i >= 32:
                break
            try:
                json.dumps(v)  # serializability probe
            except (TypeError, ValueError):
                continue
            clean[str(k)[:40]] = v
        if clean:
            entry["metadata"] = clean
    try:
        if tracker_path.is_file():
            state = json.loads(tracker_path.read_text(encoding="utf-8"))
        else:
            state = {
                "schema_version": "aurora.tracker.v1",
                "updated_at": _now_iso(),
                "tasks": [], "leads": {}, "crosscut": [],
            }
    except (OSError, json.JSONDecodeError):
        return None

    state.setdefault("tasks", []).append(entry)
    state["updated_at"] = _now_iso()

    try:
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = tracker_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, tracker_path)
    except OSError:
        return None
    return entry


if __name__ == "__main__":  # smoke test
    e = record_dispatch("3d-quality-rescuer", "smoke test", verdict="smoke")
    print(json.dumps(e, indent=2))
