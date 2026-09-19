from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

postgres_bp = Blueprint('postgres_bp', __name__)

# =====================================================================
#  Cowork — Postgres SQL bridge (le DSN ne quitte jamais la machine)
# =====================================================================

@postgres_bp.route("/api/cowork/db/sql", methods=["POST"])
def cowork_db_sql():
    """Execute un SQL via psycopg2. body: {dsn, sql, args?, allowWrite?}."""
    body = request.get_json(silent=True) or {}
    dsn = (body.get("dsn") or "").strip()
    sql = (body.get("sql") or "").strip()
    args = body.get("args") or []
    allow_write = bool(body.get("allowWrite"))
    if not dsn or not sql:
        return jsonify({"ok": False, "error": "dsn + sql requis"}), 400
    is_select = sql.lstrip().lower().startswith(("select", "with"))
    if not is_select and not allow_write:
        return jsonify({"ok": False, "error": "SQL d ecriture detecte mais allowWrite=false"}), 400
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        return jsonify({"ok": False, "error": "psycopg2 non installe (pip install psycopg2-binary)"}), 500
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                if cur.description:
                    rows = cur.fetchmany(500)
                    return jsonify({"ok": True, "rows": rows, "rowcount": cur.rowcount})
                conn.commit()
                return jsonify({"ok": True, "rowcount": cur.rowcount})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


