from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

s3_bp = Blueprint('s3_bp', __name__)

# =====================================================================
#  Cowork — S3 bridge (signature SigV4 cote serveur)
# =====================================================================

@s3_bp.route("/api/cowork/storage/s3", methods=["POST"])
def cowork_storage_s3():
    """S3-compatible storage. body: {creds: 'access:secret', endpoint, operation, bucket?, key?, prefix?, body?}."""
    body = request.get_json(silent=True) or {}
    creds = (body.get("creds") or "").strip()
    endpoint = (body.get("endpoint") or "https://s3.amazonaws.com").rstrip("/")
    op = (body.get("operation") or "").strip()
    if ":" not in creds:
        return jsonify({"ok": False, "error": "creds au format <access_key>:<secret_key>"}), 400
    access_key, secret_key = creds.split(":", 1)
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "boto3 non installe (pip install boto3)"}), 500
    try:
        # Detection naive de region depuis endpoint AWS
        region = "us-east-1"
        if ".amazonaws.com" in endpoint:
            for part in endpoint.replace("https://", "").split("."):
                if part.startswith(("us-", "eu-", "ap-", "sa-", "ca-", "af-", "me-")):
                    region = part
                    break
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint if endpoint != "https://s3.amazonaws.com" else None,
            region_name=region,
            config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=30),
        )
        if op == "list_buckets":
            r = s3.list_buckets()
            return jsonify({"ok": True, "buckets": [b["Name"] for b in r.get("Buckets", [])]})
        if op == "list_objects":
            r = s3.list_objects_v2(Bucket=body["bucket"], Prefix=body.get("prefix", ""), MaxKeys=200)
            return jsonify({"ok": True, "objects": [{"key": o["Key"], "size": o["Size"], "modified": o["LastModified"].isoformat()} for o in r.get("Contents", [])]})
        if op == "get_object":
            r = s3.get_object(Bucket=body["bucket"], Key=body["key"])
            content = r["Body"].read()
            try:
                return jsonify({"ok": True, "content": content.decode("utf-8"), "bytes": len(content)})
            except UnicodeDecodeError:
                import base64
                return jsonify({"ok": True, "content_b64": base64.b64encode(content).decode("ascii"), "bytes": len(content)})
        if op == "put_object":
            content = body.get("body", "").encode("utf-8") if isinstance(body.get("body"), str) else b""
            s3.put_object(Bucket=body["bucket"], Key=body["key"], Body=content)
            return jsonify({"ok": True, "bytes": len(content)})
        if op == "delete_object":
            s3.delete_object(Bucket=body["bucket"], Key=body["key"])
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": f"operation inconnue: {op}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


