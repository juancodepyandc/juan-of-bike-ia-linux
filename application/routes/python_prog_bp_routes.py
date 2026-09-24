from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

python_prog_bp = Blueprint('python_prog_bp', __name__)

# =====================================================================
#  Python progress (polling pour le frontend cloud)
# =====================================================================

_python_progress_events: list[tuple[int, str]] = []
_python_progress_seq: int = 0
_python_progress_lock = threading.Lock()


def _update_job_progress_from_line(job_id: str, line: str):
    """Parse PROGRESS line and update _python_jobs[job_id] with rich progress fields."""
    from routes.python_bp_routes import _python_jobs, _python_jobs_lock
    if not line or not line.startswith("PROGRESS:"):
        return
    content = line[9:].strip()
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if not job:
            return

        now = time.time()
        job["lastProgressTs"] = now

        # Try parsing JSON payload
        if content.startswith("{") and content.endswith("}"):
            try:
                data = json.loads(content)
                if "pct" in data:
                    job["progressPct"] = max(float(job.get("progressPct", 0.0)), min(100.0, float(data["pct"])))
                if "stage" in data:
                    job["stage"] = str(data["stage"])
                if "stage_label" in data:
                    job["stageLabel"] = str(data["stage_label"])
                if "sub_stage" in data:
                    job["subStage"] = str(data["sub_stage"])
                if "detail" in data:
                    job["stepDetail"] = str(data["detail"])
                    job["step"] = str(data["detail"])
                if "step" in data:
                    job["currentStep"] = int(data["step"])
                if "total_steps" in data:
                    job["totalSteps"] = int(data["total_steps"])
                return
            except Exception:
                pass

        # Fallback: colon-separated format
        parts = content.split(":")
        if len(parts) >= 2:
            part0 = parts[0].strip()
            detail = ":".join(parts[1:]).strip()

            try:
                pct = float(part0)
                job["progressPct"] = max(float(job.get("progressPct", 0.0)), min(100.0, pct))
                if len(parts) >= 3:
                    job["stage"] = parts[1].strip()
                    job["stepDetail"] = ":".join(parts[2:]).strip()
                else:
                    job["stepDetail"] = detail
                return
            except ValueError:
                pass

            job["stage"] = part0
            job["subStage"] = part0
            job["stepDetail"] = detail
            job["step"] = detail


@python_prog_bp.route("/api/python/progress")
def python_progress():
    """Retourne les evenements de progression depuis le curseur donne."""
    since = int(request.args.get("since", 0))
    with _python_progress_lock:
        events = [msg for seq, msg in _python_progress_events if seq >= since]
        cursor = _python_progress_seq
    return jsonify({"events": events, "cursor": cursor})


def _emit_progress(msg: str, job_id: str | None = None):
    global _python_progress_seq
    with _python_progress_lock:
        _python_progress_events.append((_python_progress_seq, msg))
        _python_progress_seq += 1
        if len(_python_progress_events) > 1000:
            del _python_progress_events[:-500]

    if job_id:
        _update_job_progress_from_line(job_id, msg)



# --- Refactored to application/routes/python_bp_routes.py ---
