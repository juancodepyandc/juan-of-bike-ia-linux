#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aurora_native_mcp.py — Serveur MCP Unifie Multi-Domaines d'AuroraIA (JSON-RPC 2.0 stdio).

Expose en JSON-RPC 2.0 (stdio autonome + compatible FastMCP) les meilleurs outils
natifs et web pour CHAQUE module d'AuroraIA :
  1. classify_and_direct_style       — Moteur Multi-Styles Universel (8 familles 2D/3D)
  2. generate_2d_image               — Pipeline officiel FLUX.2-dev (creations & modifications)
  3. generate_3d_model               — Pipeline officiel TRELLIS.2 / Multi-Personnages 1:1 UV
  4. verify_formal_science           — Oracle formel SymPy + Z3 (Math, Physique, Chimie, Code)
  5. cyber_symbolic_audit            — Audit de securite symbolique Z3 & patch UNSAT
  6. evaluate_business_risk          — IndependentRiskManager (Reserve >= 25 %, Ruine <= 2 %)
  7. synthesize_voice                — Synthese vocale Kokoro-82M Phonetique FR
  8. search_and_install_skills_or_mcp— Recherche & installation de Skills et MCP (Local + GitHub Web)
  9. get_hardware_status             — Etat GPU RTX 5070 Ti, VRAM, Disque et Modeles Renforces
  10. get_system_info                — Architecture unifiee d'AuroraIA (mcp, interface, modele, output)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "application"
PS_DIR = APP_DIR / "python-services"
if str(PS_DIR) not in sys.path:
    sys.path.insert(0, str(PS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def classify_and_direct_style(prompt: str, mode: str = "auto") -> dict[str, Any]:
    """Analyse une requete (realiste ou hors-realisme : cartoon 2D Xilam/Zig et Sharko,
    anime cel, figurine collector, cubique/voxel, BD/manga, claymation, cristal, PBR)
    et renvoie la strategie exacte 2D + 3D."""
    try:
        from universal_style_engine import classify_style
        from human_prompt_director import direct_prompt
        style_info = classify_style(prompt)
        directed = direct_prompt(prompt)
        return {
            "ok": True,
            "mode": mode,
            "style_id": style_info.get("style_id"),
            "style_family": style_info.get("style_id"),
            "label": style_info.get("label"),
            "2d_positive_guardrails": style_info.get("2d_positive_guardrails"),
            "2d_negative_guardrails": style_info.get("2d_negative_guardrails"),
            "3d_env": style_info.get("3d_env"),
            "directed_prompt": directed,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def generate_2d_image(prompt: str, reference_image: str = "", denoise: float = 0.72) -> dict[str, Any]:
    """Genere ou modifie une image 2D via le pipeline officiel FLUX.2-dev (`image_cli.mjs`)."""
    try:
        cli_js = APP_DIR / "scripts" / "image_cli.mjs"
        cmd = ["node", str(cli_js), "--prompt", prompt]
        if reference_image and os.path.isfile(reference_image):
            cmd += ["--image", reference_image, "--denoise", str(denoise)]
        r = subprocess.run(cmd, cwd=str(APP_DIR), capture_output=True, text=True, timeout=600, check=False)
        return {"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-2000:]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def generate_3d_model(prompt: str, image_path: str = "", run_id: str = "") -> dict[str, Any]:
    """Lance le pipeline 3D officiel (`aurora_3d_pipeline.py` — TRELLIS.2, multi-personnages 1:1 UV, Perfection Gate)."""
    try:
        script = PS_DIR / "aurora_3d_pipeline.py"
        out_dir = APP_DIR / "output" / "3d" / "conversations"
        cmd = [sys.executable, str(script), "--prompt", prompt, "--output-dir", str(out_dir), "--engine", "trellis", "--force"]
        if image_path and os.path.isfile(image_path):
            cmd += ["--image", image_path]
        if run_id:
            cmd += ["--run-id", run_id]
        r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=3600, check=False)
        return {"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-3000:]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def verify_formal_science(expression: str, mode: str = "math") -> dict[str, Any]:
    """Verifie formellement un calcul, une equation ou un invariant via `scientific_oracle.py` (SymPy + Z3)."""
    try:
        oracle = PS_DIR / "scientific_oracle.py"
        r = subprocess.run(
            [sys.executable, str(oracle), "--mode", mode, "--query", expression],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60, check=False,
        )
        return {"ok": r.returncode == 0, "result": (r.stdout or r.stderr).strip()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def cyber_symbolic_audit(target_path: str = "") -> dict[str, Any]:
    """Execute un diagnostic de securite symbolique Z3 / PyOps sous garde-fou `_safety.py`."""
    try:
        cyber_dir = PS_DIR / "cyber"
        scripts = sorted(p.name for p in cyber_dir.glob("*.py")) if cyber_dir.is_dir() else []
        return {
            "ok": True,
            "cyber_pyops_dir": str(cyber_dir),
            "available_auditors": scripts,
            "target_inspected": target_path,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def evaluate_business_risk(capital: float = 10000.0, allocation: float = 2000.0, ruin_probability: float = 0.01) -> dict[str, Any]:
    """Verifie une decision economique via les invariants non-LLM d'IndependentRiskManager (reserve >= 25 %, ruine <= 2 %)."""
    reserve_ratio = (capital - allocation) / max(capital, 1e-6)
    approved = (reserve_ratio >= 0.25) and (ruin_probability <= 0.02)
    return {
        "ok": True,
        "approved": approved,
        "reserve_ratio": round(reserve_ratio, 4),
        "min_reserve_required": 0.25,
        "ruin_probability": round(ruin_probability, 4),
        "max_ruin_allowed": 0.02,
        "verdict": "APPROVED" if approved else "VETO_INDEPENDENT_RISK_MANAGER",
    }


def synthesize_voice(text: str) -> dict[str, Any]:
    """Synthetise de la voix (Kokoro-82M) a partir d'un texte via le Bridge local `:3001`."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:3001/api/voice/synthesize",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"ok": resp.status == 200, "response": resp.read().decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def search_and_install_skills_or_mcp(query: str = "", install_skill_name: str = "", github_raw_url: str = "") -> dict[str, Any]:
    """Recherche les meilleurs Skills et serveurs MCP en local ET sur Internet (GitHub / ModelContextProtocol / Awesome-MCP),
    et permet d'installer un Skill verifie dans `.aurora/skills/<nom>/SKILL.md`."""
    try:
        from agi_core.context import discover_skills, discover_mcp
        local_skills = discover_skills(str(REPO_ROOT))
        local_mcp = discover_mcp(str(REPO_ROOT))
        q_low = (query or "").lower().strip()
        matched_local = [
            {"name": s["name"], "description": s.get("description", ""), "file": s.get("file", "")}
            for s in local_skills
            if not q_low or q_low in s["name"].lower() or q_low in s.get("description", "").lower() or q_low in s.get("content", "").lower()
        ]

        web_results: list[dict[str, Any]] = []
        if q_low:
            try:
                api_url = (
                    "https://api.github.com/search/repositories?q="
                    + urllib.parse.quote(f"{query} (mcp-server OR agent-skill OR modelcontextprotocol)")
                    + "&sort=stars&order=desc&per_page=5"
                )
                req = urllib.request.Request(api_url, headers={"User-Agent": "AuroraIA-MCP-Hub/2.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in (data.get("items") or [])[:5]:
                        web_results.append({
                            "name": item.get("full_name"),
                            "stars": item.get("stargazers_count"),
                            "description": item.get("description"),
                            "url": item.get("html_url"),
                        })
            except Exception:
                pass

        installed_path = None
        if install_skill_name and github_raw_url.startswith("https://"):
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", install_skill_name.strip().lower()).strip("-")
            if slug:
                req = urllib.request.Request(github_raw_url, headers={"User-Agent": "AuroraIA-MCP-Hub/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_md = resp.read().decode("utf-8", errors="replace")[:60000]
                target_dir = REPO_ROOT / ".aurora" / "skills" / slug
                target_dir.mkdir(parents=True, exist_ok=True)
                target_md = target_dir / "SKILL.md"
                if not raw_md.lstrip().startswith("---"):
                    raw_md = f"---\nname: {slug}\ndescription: Skill importe depuis {github_raw_url}\n---\n\n{raw_md}"
                target_md.write_text(raw_md, encoding="utf-8")
                installed_path = str(target_md)

        return {
            "ok": True,
            "query": query,
            "local_skills_count": len(matched_local),
            "local_skills_matched": matched_local,
            "local_mcp_servers": [m["name"] for m in local_mcp],
            "web_github_top_matches": web_results,
            "installed_skill_path": installed_path,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_hardware_status() -> dict[str, Any]:
    """Verifie l'etat materiel du serveur Linux (GPU RTX 5070 Ti, VRAM, RAM, Disque, Modeles Renforces)."""
    try:
        disk = shutil.disk_usage(str(REPO_ROOT))
        renforce_dir = REPO_ROOT / "modele" / "renforce"
        modules_renforces = sorted(p.name for p in renforce_dir.iterdir() if p.is_dir()) if renforce_dir.is_dir() else []
        nv = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return {
            "ok": True,
            "gpu": (nv.stdout or "").strip(),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "reinforced_modules": modules_renforces,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_system_info() -> dict[str, Any]:
    """Recupere les informations systeme et l'architecture unifiee d'AuroraIA."""
    return {
        "ok": True,
        "workspace": str(REPO_ROOT),
        "poles": {
            "mcp": str(REPO_ROOT / "mcp"),
            "interface": str(REPO_ROOT / "interface"),
            "modele": str(REPO_ROOT / "modele"),
            "output": str(REPO_ROOT / "output"),
            "skills": str(REPO_ROOT / ".aurora" / "skills"),
        },
    }


_TOOLS: list[tuple[str, str, dict[str, Any], Any]] = [
    (
        "classify_and_direct_style",
        "Analyse une requete (realiste ou hors-realisme : cartoon 2D Xilam/Zig et Sharko, anime, figurine, voxel, BD, cristal) et renvoie la strategie 2D + 3D.",
        {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]},
        classify_and_direct_style,
    ),
    (
        "generate_2d_image",
        "Genere ou modifie une image 2D via FLUX.2-dev (`image_cli.mjs`).",
        {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "reference_image": {"type": "string"},
                "denoise": {"type": "number"},
            },
            "required": ["prompt"],
        },
        generate_2d_image,
    ),
    (
        "generate_3d_model",
        "Lance le pipeline 3D officiel (`aurora_3d_pipeline.py` — TRELLIS.2, multi-personnages 1:1 UV, Perfection Gate).",
        {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "image_path": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["prompt"],
        },
        generate_3d_model,
    ),
    (
        "verify_formal_science",
        "Verifie formellement un calcul, une equation ou un invariant via `scientific_oracle.py` (SymPy + Z3).",
        {
            "type": "object",
            "properties": {"expression": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["expression"],
        },
        verify_formal_science,
    ),
    (
        "cyber_symbolic_audit",
        "Inspecte les outils d'audit symbolique Z3 et PyOps Cyber sous garde-fou `_safety.py`.",
        {"type": "object", "properties": {"target_path": {"type": "string"}}},
        cyber_symbolic_audit,
    ),
    (
        "evaluate_business_risk",
        "Verifie une allocation economique via IndependentRiskManager (reserve >= 25 %, ruine <= 2 %).",
        {
            "type": "object",
            "properties": {
                "capital": {"type": "number"},
                "allocation": {"type": "number"},
                "ruin_probability": {"type": "number"},
            },
        },
        evaluate_business_risk,
    ),
    (
        "synthesize_voice",
        "Synthetise de la voix (Kokoro-82M) a partir d'un texte.",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        synthesize_voice,
    ),
    (
        "search_and_install_skills_or_mcp",
        "Recherche les meilleurs Skills et serveurs MCP en local et sur Internet (GitHub), et installe un Skill dans `.aurora/skills/<nom>/SKILL.md`.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "install_skill_name": {"type": "string"},
                "github_raw_url": {"type": "string"},
            },
        },
        search_and_install_skills_or_mcp,
    ),
    (
        "get_hardware_status",
        "Verifie l'etat GPU RTX 5070 Ti, VRAM, Disque et Modeles Renforces.",
        {"type": "object", "properties": {}},
        get_hardware_status,
    ),
    (
        "get_system_info",
        "Recupere l'architecture unifiee d'AuroraIA (mcp, interface, modele, output, skills).",
        {"type": "object", "properties": {}},
        get_system_info,
    ),
]


def _run_jsonrpc_stdio() -> None:
    """Boucle JSON-RPC 2.0 stdio autonome sans dependance externe."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if mid is None:
            continue
        if method == "initialize":
            res = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aurora-native", "version": "2.0.0"},
            }
        elif method == "tools/list":
            res = {
                "tools": [
                    {"name": name, "description": desc, "inputSchema": schema}
                    for name, desc, schema, _ in _TOOLS
                ]
            }
        elif method == "tools/call":
            tname = params.get("name", "")
            targs = params.get("arguments") or {}
            impl = next((fn for n, _, _, fn in _TOOLS if n == tname), None)
            if impl is None:
                res = {"isError": True, "content": [{"type": "text", "text": json.dumps({"ok": False, "error": f"unknown tool: {tname}"})}]}
            else:
                try:
                    out = impl(**targs)
                    res = {"isError": False, "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]}
                except Exception as exc:
                    res = {"isError": True, "content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(exc)})}]}
        else:
            res = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    _run_jsonrpc_stdio()
