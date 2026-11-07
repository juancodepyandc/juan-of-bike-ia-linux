"""Measured admission plans for heterogeneous workers, without launching any job."""
from __future__ import annotations

import math
import time


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def worker_capacity(worker, *, now=None, heartbeat_ttl=120, reserve_fraction=.15):
    now = time.time() if now is None else now
    heartbeat = _number(worker.get("last_heartbeat"))
    fresh = heartbeat is not None and 0 <= now - heartbeat <= heartbeat_ttl
    # VRAM is per device. Two 16 GiB GPUs are not one 32 GiB GPU.
    free = worker.get("device_free_vram_gb")
    if not isinstance(free, list) or not free or any(_number(v) is None for v in free):
        free = []
    ram = _number(worker.get("available_ram_gb"))
    deadline = _number(worker.get("session_deadline"))
    remaining = _number(worker.get("remaining_seconds"))
    if deadline is not None:
        remaining = max(0.0, deadline - now)
    elif remaining is not None and heartbeat is not None:
        remaining = max(0.0, remaining - max(0.0, now - heartbeat))
    return {
        "fresh": fresh, "age_seconds": now - heartbeat if heartbeat is not None else None,
        "device_budget_gb": [v * (1 - reserve_fraction) for v in free],
        "ram_budget_gb": ram * (1 - reserve_fraction) if ram is not None else None,
        "remaining_seconds": remaining,
        "available": worker.get("status") in {"idle", "ready", "registered"},
        "telemetry_status": "measured" if fresh and free and ram is not None else "unverified",
    }


def plan_compute(requirements, workers, *, now=None):
    """Fail closed on missing measurements; return a proposal, never a dispatch."""
    required = ("vram_per_device_gb", "ram_gb", "duration_seconds", "checkpoint_seconds")
    for field in required:
        if _number(requirements.get(field)) is None:
            raise ValueError(f"Measured nonnegative requirement missing: {field}")
    count = requirements.get("device_count", 1)
    if type(count) is not int or count < 1:
        raise ValueError("device_count must be a positive integer")
    if count > 1 and requirements.get("distributed_verified") is not True:
        raise ValueError("Multi-device admission requires a verified distributed execution path")
    decisions = []
    for worker_id, worker in workers.items():
        capacity = worker_capacity(worker, now=now)
        reasons = []
        if not capacity["fresh"]:
            reasons.append("stale_heartbeat")
        if not capacity["available"]:
            reasons.append("worker_busy_or_unknown")
        if capacity["telemetry_status"] != "measured":
            reasons.append("missing_memory_measurements")
        fitting = sum(v >= requirements["vram_per_device_gb"] for v in capacity["device_budget_gb"])
        if fitting < count:
            reasons.append("insufficient_per_device_vram")
        if capacity["ram_budget_gb"] is None or capacity["ram_budget_gb"] < requirements["ram_gb"]:
            reasons.append("insufficient_ram")
        required_time = requirements["duration_seconds"] + requirements["checkpoint_seconds"]
        if capacity["remaining_seconds"] is None:
            reasons.append("unknown_session_budget")
        elif capacity["remaining_seconds"] < required_time:
            reasons.append("checkpoint_reserve_exceeds_session")
        decisions.append({"worker_id": worker_id, "eligible": not reasons, "reasons": reasons, "capacity": capacity})
    eligible = [d for d in decisions if d["eligible"]]
    # Best fit avoids occupying the largest GPU with a job a smaller one can run.
    eligible.sort(key=lambda d: (max(d["capacity"]["device_budget_gb"]), d["worker_id"]))
    return {"kind": "admission_proposal", "dispatched": False,
            "selected_worker": eligible[0]["worker_id"] if eligible else None, "decisions": decisions,
            "scope": "Stored worker telemetry; no job launch, quota query or model promotion"}
