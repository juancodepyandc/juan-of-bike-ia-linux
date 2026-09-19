from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

iot_bp = Blueprint('iot_bp', __name__)

# =====================================================================
#  Cowork — IoT bridge (MQTT publish/subscribe + Tuya HMAC)
# =====================================================================

@iot_bp.route("/api/cowork/iot/mqtt", methods=["POST"])
def cowork_iot_mqtt():
    """Publish ou subscribe-once vers un broker MQTT generique.
    body: {broker, auth: 'user:pass', operation: 'publish'|'subscribe_once'|'test',
           topic, payload, qos?, retain?, timeout?}."""
    body = request.get_json(silent=True) or {}
    broker = (body.get("broker") or "").strip()
    if not broker:
        return jsonify({"ok": False, "error": "broker manquant"}), 400
    auth = (body.get("auth") or "").strip()
    operation = (body.get("operation") or "").strip()

    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "paho-mqtt non installe (pip install paho-mqtt)"}), 500

    from urllib.parse import urlparse
    parsed = urlparse(broker)
    host = parsed.hostname
    port = parsed.port or (8883 if parsed.scheme == "mqtts" else 1883)
    if not host:
        return jsonify({"ok": False, "error": f"broker URL invalide : {broker}"}), 400

    client = mqtt.Client()
    if auth and ":" in auth:
        u, p = auth.split(":", 1)
        client.username_pw_set(u, p)
    if parsed.scheme == "mqtts":
        client.tls_set()

    try:
        client.connect(host, port, keepalive=30)
    except Exception as e:
        return jsonify({"ok": False, "error": f"connect: {e}"}), 502

    try:
        if operation == "test":
            client.disconnect()
            return jsonify({"ok": True})
        if operation == "publish":
            topic = body.get("topic") or ""
            payload = body.get("payload")
            if isinstance(payload, (dict, list)):
                import json as _json
                payload = _json.dumps(payload)
            qos = int(body.get("qos") or 0)
            retain = bool(body.get("retain"))
            client.loop_start()
            info = client.publish(topic, payload=payload, qos=qos, retain=retain)
            info.wait_for_publish(timeout=10)
            client.loop_stop()
            client.disconnect()
            return jsonify({"ok": True, "mid": info.mid})
        if operation == "subscribe_once":
            received = []
            def on_message(_client, _userdata, msg):
                received.append({"topic": msg.topic, "payload": msg.payload.decode("utf-8", errors="replace")})
            client.on_message = on_message
            client.subscribe(body.get("topic") or "", qos=int(body.get("qos") or 0))
            client.loop_start()
            timeout = float(body.get("timeout") or 10)
            deadline = _time.time() + timeout
            while _time.time() < deadline and not received:
                _time.sleep(0.1)
            client.loop_stop()
            client.disconnect()
            return jsonify({"ok": True, "messages": received})
        return jsonify({"ok": False, "error": f"operation inconnue: {operation}"}), 400
    except Exception as e:
        try: client.disconnect()
        except Exception: pass
        return jsonify({"ok": False, "error": str(e)}), 500


@iot_bp.route("/api/cowork/iot/tuya", methods=["POST"])
def cowork_iot_tuya():
    """Tuya Cloud avec signature HMAC-SHA256.
    body: {creds: 'AccessKey:Secret', baseUrl, operation, ...params}."""
    import hmac, hashlib, json as _json, time as _t
    body = request.get_json(silent=True) or {}
    creds = (body.get("creds") or "").strip()
    base_url = (body.get("baseUrl") or "").rstrip("/")
    operation = (body.get("operation") or "").strip()
    if ":" not in creds:
        return jsonify({"ok": False, "error": "creds format <AccessKey>:<Secret>"}), 400
    if not base_url:
        return jsonify({"ok": False, "error": "baseUrl region requis"}), 400
    access_key, secret = creds.split(":", 1)

    def sign(method: str, path: str, body_str: str = "", access_token: str = "") -> tuple[str, str]:
        ts = str(int(_t.time() * 1000))
        content_sha = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
        string_to_sign = f"{method}\n{content_sha}\n\n{path}"
        sig_str = access_key + access_token + ts + string_to_sign
        sig = hmac.new(secret.encode(), sig_str.encode(), hashlib.sha256).hexdigest().upper()
        return sig, ts

    try:
        # 1. Get access_token
        sig, ts = sign("GET", "/v1.0/token?grant_type=1")
        token_resp = requests.get(
            f"{base_url}/v1.0/token?grant_type=1",
            headers={
                "client_id": access_key,
                "sign": sig,
                "t": ts,
                "sign_method": "HMAC-SHA256",
            },
            timeout=10,
        )
        token_data = token_resp.json()
        if not token_data.get("success"):
            return jsonify({"ok": False, "error": token_data.get("msg") or "token failed"}), 401
        access_token = token_data["result"]["access_token"]

        # 2. Dispatch operation
        if operation == "list_devices":
            uid = body.get("uid") or ""
            path = f"/v1.0/users/{uid}/devices" if uid else "/v1.0/iot-01/associated-users/devices"
            sig2, ts2 = sign("GET", path, "", access_token)
            r = requests.get(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token,
            }, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        if operation == "device_status":
            dev = body.get("device_id")
            path = f"/v1.0/iot-03/devices/{dev}/status"
            sig2, ts2 = sign("GET", path, "", access_token)
            r = requests.get(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token,
            }, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        if operation == "send_command":
            dev = body.get("device_id")
            path = f"/v1.0/iot-03/devices/{dev}/commands"
            payload = _json.dumps({"commands": [{"code": body.get("code"), "value": body.get("value")}]})
            sig2, ts2 = sign("POST", path, payload, access_token)
            r = requests.post(f"{base_url}{path}", headers={
                "client_id": access_key, "sign": sig2, "t": ts2, "sign_method": "HMAC-SHA256",
                "access_token": access_token, "Content-Type": "application/json",
            }, data=payload, timeout=15)
            return jsonify({"ok": r.ok, "data": r.json()})
        return jsonify({"ok": False, "error": f"operation Tuya inconnue: {operation}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


