#!/usr/bin/env python3
"""Verifie que le canal bridge/tunnel utilise bien le MEME moteur que l UI.

Avant la correction de parite, POST /api/code/generate/stream lancait
python-services/aurora_code/bridge_agentic_stream.py: un planner-executor
autonome sans aucune des gates de qualite que l UI Tauri execute. Tout appel
arrivant par /api/aurora/code/generate (cowork, tunnel, clients externes) etait
donc servi par un moteur degrade, invisible depuis l UI.

Ce script controle quatre choses, sans dependre d un bridge demarre:

  1. la route reference bien le runner Node partage, plus le moteur Python;
  2. le runner existe a l emplacement reference;
  3. `node` est resolvable comme le fait la route (shutil.which);
  4. le runner respecte le contrat NDJSON quand on le lance EXACTEMENT comme la
     route le fait (payload JSON sur stdin, evenements sur stdout).

Le point 4 utilise un prompt vide: le runner doit repondre par un evenement
`error` immediatement, sans appeler le modele. Le controle reste donc
deterministe et rapide, la generation reelle etant prouvee par ailleurs.

Usage: python3 scripts/code_harness/verify_bridge_parity.py
Sortie: rapport JSON sur stdout, code de sortie 0 si tout passe.
"""

import json
import pathlib
import shutil
import subprocess
import sys

WORKSPACE = pathlib.Path(__file__).resolve().parents[2]
BRIDGE = WORKSPACE / "bridge_server.py"
RUNNER_REL = pathlib.Path("scripts") / "code_harness" / "bridge_ndjson_runner.mjs"
RUNNER = WORKSPACE / RUNNER_REL
SCHEMA = "aurora.code.stream/1"

checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    return ok


# 1. La route pointe sur le runner partage, et plus sur le moteur Python.
source = BRIDGE.read_text(encoding="utf-8", errors="replace")
route_start = source.find('@app.route("/api/code/generate/stream"')
route_body = source[route_start:route_start + 3000] if route_start >= 0 else ""
check("route_found", route_start >= 0, "/api/code/generate/stream")

# La docstring de la route EXPLIQUE la correction et cite donc l ancien moteur.
# Le controle doit porter sur le CODE execute, pas sur le commentaire: on retire
# la docstring avant de chercher.
route_code = route_body
if '"""' in route_code:
    head, _, rest = route_code.partition('"""')
    _, _, tail = rest.partition('"""')
    route_code = head + tail

check(
    "route_uses_shared_node_runner",
    "bridge_ndjson_runner.mjs" in route_code,
    "la route doit lancer le runner Node partage",
)
check(
    "route_no_longer_spawns_python_engine",
    "bridge_agentic_stream.py" not in route_code,
    "le moteur Python degrade ne doit plus etre lance",
)
check(
    "route_spawns_node_binary",
    "[node_bin, str(script)]" in route_code,
    "le sous-processus doit etre node, pas sys.executable",
)

# 2. Le runner existe la ou la route le cherche.
check("runner_exists", RUNNER.is_file(), str(RUNNER))

# 3. node est resolvable exactement comme dans la route.
node_bin = shutil.which("node")
check("node_resolvable", bool(node_bin), node_bin or "node introuvable")

# 4. Contrat NDJSON, lance comme la route le fait.
if node_bin and RUNNER.is_file():
    proc = subprocess.run(
        [node_bin, str(RUNNER)],
        cwd=str(WORKSPACE),
        input=json.dumps({"prompt": "", "model": "qwen3-coder:30b", "runId": 1}),
        capture_output=True,
        text=True,
        timeout=180,
    )
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    check("ndjson_emitted", len(lines) >= 1, f"{len(lines)} ligne(s)")
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError as exc:
            check("ndjson_line_parses", False, f"{exc}: {line[:120]}")
            break
    else:
        check("ndjson_line_parses", True, "toutes les lignes sont du JSON")
    check(
        "ndjson_schema_matches_bridge",
        all(e.get("schema") == SCHEMA for e in parsed),
        f"schema attendu {SCHEMA}",
    )
    check(
        "empty_prompt_yields_error_event",
        any(e.get("kind") == "error" for e in parsed),
        "prompt vide -> evenement error",
    )
    check(
        "stdout_not_polluted_by_logs",
        all(l.lstrip().startswith("{") for l in lines),
        "aucune ligne de log ne doit atterrir sur stdout",
    )

ok = all(c["ok"] for c in checks)
report = {
    "schemaVersion": "aurora.code.bridge-parity/1",
    "ok": ok,
    "runner": str(RUNNER_REL),
    "node": node_bin,
    "checks": checks,
}
print(json.dumps(report, indent=2, ensure_ascii=False))
sys.exit(0 if ok else 1)
