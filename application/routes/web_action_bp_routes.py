"""Authenticated access to caller-isolated native browser sessions."""
import hashlib
import asyncio
from flask import Blueprint, jsonify, request
from agi_core.browser_runtime import browser_action

web_action_bp = Blueprint('web_action_bp', __name__)

@web_action_bp.route("/api/web/action", methods=["POST"])
def web_action():
    from bridge_server import WORKSPACE, _request_is_local_loopback, _ext_auth
    from application.device_pairing import request_identity
    local = _request_is_local_loopback()
    ok, record, _ = _ext_auth() if not local else (True, {}, None)
    if not ok:
        return jsonify(ok=False, error="Connect this device to Aurora first"), 403
    if (record or {}).get("permissions") == "SAFE":
        return jsonify(ok=False, error="Browser execution requires STANDARD permissions"), 403
    identity = request_identity(WORKSPACE) or ("local" if local else str(record.get("hash") or record.get("id") or ""))
    if not identity:
        return jsonify(ok=False, error="Browser caller identity unavailable"), 403
    owner = hashlib.sha256(identity.encode()).hexdigest()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Action must be a JSON object"), 400
    if data.get("action") in {"navigate", "extract_dom"} and not data.get("session_id"):
        data = {**data, "action": "open"}
    if data.get("action") == "inspect_visual":
        from agi_core.vision_observer import inspect_browser
        try:
            result = asyncio.run(inspect_browser(data.get("session_id"), data.get("question"),
                                                owner=owner, model=data.get("model")))
        except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
            result = {"ok": False, "error": str(exc)[:1200], "outcome": "unverified"}
    else:
        result = browser_action(data, owner=owner)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response
