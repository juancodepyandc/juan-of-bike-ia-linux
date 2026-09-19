from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

ext_bp = Blueprint('ext_bp', __name__)

# =====================================================================
#  /api/ext/* — API publique pour intégrer Aurora dans un site externe
#  (widget de chat embarqué). Sécurité :
#   • clé Bearer ; on ne stocke QUE le SHA-256 salé de la clé, jamais la
#     clé en clair ; comparaison constante (hmac.compare_digest) ;
#   • CORS verrouillé : Access-Control-Allow-Origin = le domaine déclaré
#     pour la clé (jamais "*" si un domaine est fixé) ;
#   • rate-limit glissant 40 req / 60 s par clé ;
#   • clés de gestion (generate/revoke/status) accessibles seulement en
#     local (pas exposées par défaut sur le tunnel — voir _ext_admin_ok).
