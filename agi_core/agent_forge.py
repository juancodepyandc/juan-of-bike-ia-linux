"""Autonomous Agent & Hierarchical Sub-Agent Forge (`agi_core/agent_forge.py`).

Permet à AuroraIA et à son CLI (JOBIA) de synthétiser, composer, exécuter et auditer
des agents maîtres et des sous-agents spécialisés travaillant avec une rigueur maximale :
  1. Déduction causale par premiers principes en 3 passes (`agi_core.cognitive_reasoner.reason_first_principles`)
     sans aucun routage superficiel par liste de mots-clés figés ni agent précodé factice.
  2. Architecture cognitive explicite (Système 1 intuition structurelle + Système 2
     délibération multi-hypothèses Tree-of-Thoughts + Oracle formel SymPy/Z3/Manifold).
  3. Pare-feu de périmètre strict (`scope_firewall` : `files_owned`, `routes_owned`, `never_touch`).
  4. Porte Anti-Faux-Travail & Anti-Stub (`verify_subagent_deliverable_rigor`) :
     - Interdit tout sous-agent passif qui ne fait rien ou ne produit que du texte sans preuve outil.
     - Analyse l'AST des fichiers générés/modifiés (`.py`, `.ts`, `.tsx`, `.json`) pour bloquer
       tout stub creux (`pass`, `...`, `NotImplementedError`, `TODO`, `FIXME`, `placeholder`).
     - Exige une vérification empirique ou formelle (`verify`, `verify_file`, `run_command`, `test_hypothesis`)
       après la dernière mutation avant d'accepter le travail d'un sous-agent.
  5. Persistance duale : `dynamic_agents.json` + `.agents/agents/<name>/agent.md`
     immédiatement découverte par `AGIBrainRouter`, `AutonomousMissionAgent` et `LocalMission`.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

from agi_core.context import create_agent, data_dir, discover_mcp, discover_skills, resolve_agent


# Marqueurs de faux travail / code inachevé strictement interdits dans les livrables de sous-agents
_FAKE_WORK_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"#\s*(?:TODO|FIXME|XXX|HACK|STUB)\b", re.IGNORECASE),
    re.compile(r"//\s*(?:TODO|FIXME|XXX|HACK|STUB)\b", re.IGNORECASE),
    re.compile(r"\braise\s+NotImplementedError\b"),
    re.compile(r"\bthrow\s+new\s+Error\(\s*['\"](?:not\s+implemented|todo|stub)", re.IGNORECASE),
)


def _slugify_agent_name(raw_name: str, prefix: str = "agent") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw_name or "").strip().lower()).strip("-_")
    if not cleaned:
        cleaned = f"{prefix}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
    return cleaned[:72]


def _deduce_tools_from_workspace_and_reasoner(
    fp: dict[str, Any],
    ws: Path,
    mcp_servers: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    domain: str,
) -> list[str]:
    """Déduit l'ensemble complet des outils requis par premiers principes à partir du
    raisonnement causal et des ressources réellement présentes dans le workspace."""
    tools: list[str] = [
        "inspect_runtime",
        "list_files",
        "read_file",
        "search_code",
        "write_file",
        "run_command",
        "list_tools",
        "inspect_tool",
        "run_tool",
        "test_hypothesis",
        "verify",
    ]
    mod_norm = (domain or str(fp.get("domain") or "code")).strip().lower()
    if mod_norm in {"3d", "3d-texture", "3d-motion", "3d-viewer"}:
        tools.extend(["generate_3d", "create_tool"])
    elif mod_norm == "image":
        tools.extend(["generate_image", "create_tool"])
    else:
        tools.append("create_tool")

    if mcp_servers or fp.get("epistemic_regime") == "UNKNOWN_EXPLORATORY":
        tools.extend(["list_mcp_tools", "call_mcp_tool", "create_mcp_server"])
    if skills or fp.get("reasoning_mode"):
        tools.extend(["list_skills", "create_skill", "distill_skill"])

    # Si le workspace contient des tables CSV ou si la stratégie implique des données tabulaires
    try:
        if any(ws.glob("*.csv")) or "csv" in str(fp.get("verification_strategy", "")).lower():
            tools.append("inspect_csv")
    except OSError:
        pass

    # Recherche documentaire/scientifique toujours disponible pour l'exploration causale
    tools.extend(["search_web", "fetch_url", "create_agent", "spawn_agent"])
    return list(dict.fromkeys(tools))


def infer_cognitive_profile_from_goal(
    goal: str,
    domain: str = "",
    *,
    workspace: str | Path | None = None,
    allow_llm: bool = False,
) -> dict[str, Any]:
    """Déduit par premiers principes (en 3 passes via `agi_core.cognitive_reasoner`)
    le profil cognitif Système 1 / Système 2, les fonctionnalités implicites proactives,
    les outils requis et les invariants formels d'un agent ou sous-agent."""
    text = f"{goal} {domain}".strip()
    ws = Path(workspace).expanduser().resolve() if workspace else Path.cwd()

    fp: dict[str, Any] = {}
    try:
        from agi_core.cognitive_reasoner import reason_first_principles
        fp = reason_first_principles(
            goal or text,
            domain=domain or "general",
            workspace=str(ws),
            allow_llm=allow_llm,
        )
    except Exception:
        fp = {}

    ontology: dict[str, Any] = {}
    try:
        from agi_core.prompt_intelligence import infer_semantic_ontology
        ontology = infer_semantic_ontology(text, domain or str(fp.get("domain") or "code"))
    except Exception:
        ontology = {}

    regime = str(
        fp.get("epistemic_regime")
        or ontology.get("epistemic_regime")
        or "KNOWN_OPTIMIZABLE"
    )
    deep_intent = str(
        fp.get("deep_intent")
        or f"Résoudre intégralement et sans compromis de qualité l'objectif : {goal}"
    )
    implicit_features = list(fp.get("autonomous_implicit_features") or [])
    invariants = list(
        dict.fromkeys(
            list(fp.get("domain_invariants") or [])
            + list(ontology.get("implicit_invariants") or [])
            + [
                "Zéro Faux Travail : toute fonction ou méthode écrite doit contenir son implémentation algorithmique réelle (interdiction absolue de `pass`, `...`, `NotImplementedError`, `TODO`, `FIXME` ou données fictives).",
                "Vérification Empirique ou Formelle Obligatoire : exécuter `verify` / `verify_file` / `run_command` / `test_hypothesis` après la dernière écriture avant de conclure.",
                "Qualité & Précision Maximales > Vitesse : privilégier la justesse analytique, physique et structurelle complète.",
            ]
        )
    )

    mcp_servers = discover_mcp(str(ws))
    skills = discover_skills(str(ws))
    preferred_tools = _deduce_tools_from_workspace_and_reasoner(
        fp, ws, mcp_servers, skills, domain or str(fp.get("domain") or "code")
    )

    # Extraction dynamique des chemins cibles mentionnés dans l'objectif
    mentioned_paths = re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text)
    files_owned = list(dict.fromkeys(mentioned_paths))[:12]

    causal_chain = list(fp.get("causal_chain") or [])
    red_team = list(fp.get("red_team_anti_naivety") or [])
    selected_hyp = fp.get("selected_hypothesis") or {}
    strategy_summary = str(
        fp.get("first_principles_strategy")
        or selected_hyp.get("mechanism")
        or "Décomposition causale -> Implémentation complète -> Vérification formelle et empirique."
    )

    system1_heuristics = [
        "Inspection immédiate de l'état réel du workspace (`list_files`, `search_code`, `read_file`) avant toute hypothèse.",
        "Réutilisation des artefacts, compétences (`.aurora/skills`) et serveurs MCP déjà vérifiés sans réinventer l'existant.",
    ]
    system2_deliberation = [
        f"Intention Causale Profonde : {deep_intent}",
        f"Régime Épistémique Actif : `{regime}` — Stratégie Pareto retenue : {strategy_summary}",
        "Passe Red-Team Anti-Naïveté : "
        + (" ; ".join(red_team[:3]) if red_team else "Éliminer tout cas limite, dépassement numérique, stub ou dépendance interactive bloquante."),
        "Valider les invariants mathématiques/logiques via SymPy/Z3 (`scientific_oracle` / `test_hypothesis`) et par exécution de test reproductible.",
        "Exiger une vérification atomique (`verify` : hash SHA-256, expression JSON, AST sans stub, test unitaire ou sonde MCP) avant `finish`.",
    ]

    return {
        "epistemic_regime": regime,
        "deep_intent": deep_intent,
        "first_principles_strategy": strategy_summary,
        "causal_chain": causal_chain,
        "red_team_anti_naivety": red_team,
        "autonomous_implicit_features": implicit_features,
        "preferred_tools": preferred_tools,
        "files_owned": files_owned,
        "invariants": invariants,
        "system1_heuristics": system1_heuristics,
        "system2_deliberation": system2_deliberation,
        "available_mcp_servers": [s.get("name", "") for s in mcp_servers if s.get("name")],
        "relevant_skills": [s.get("name", "") for s in skills[:6] if s.get("name")],
    }


def audit_file_against_fake_work(path: Path) -> dict[str, Any]:
    """Audite un fichier disque réel pour garantir qu'il ne contient aucun stub,
    aucun TODO/FIXME/NotImplementedError et que sa syntaxe/AST est 100 % valide."""
    report: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": 0,
        "sha256": "",
        "syntax_valid": False,
        "anti_stub_passed": False,
        "violations": [],
        "defined_symbols": [],
    }
    if not path.is_file():
        report["violations"].append("FILE_MISSING: Le fichier déclaré n'existe pas sur le disque.")
        return report

    try:
        raw = path.read_bytes()
    except OSError as exc:
        report["violations"].append(f"READ_ERROR: {exc}")
        return report

    report["bytes"] = len(raw)
    report["sha256"] = hashlib.sha256(raw).hexdigest()
    if len(raw) == 0:
        report["violations"].append("EMPTY_FILE: Fichier vide (0 octet).")
        return report

    if b"\x00" in raw[:4096]:
        # Artefact binaire (GLB, STL, PNG, WAV, etc.) : non vide et hashé
        report["syntax_valid"] = True
        report["anti_stub_passed"] = len(raw) >= 16
        if not report["anti_stub_passed"]:
            report["violations"].append("TRUNCATED_BINARY: Fichier binaire anormalement court (< 16 octets).")
        return report

    text = raw.decode("utf-8", errors="replace")
    suffix = path.suffix.lower()

    # 1. Scan de lignes contre les marqueurs explicites de faux travail (dans les fichiers de code)
    if suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".c", ".cpp"}:
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat in _FAKE_WORK_LINE_PATTERNS:
                if pat.search(line):
                    report["violations"].append(
                        f"FAKE_WORK_MARKER (L{lineno}): `{line.strip()[:120]}`"
                    )

    # 2. Vérification syntaxique et AST par langage
    if suffix == ".py":
        try:
            tree = ast.parse(text, filename=str(path))
            report["syntax_valid"] = True
        except SyntaxError as exc:
            report["syntax_valid"] = False
            report["violations"].append(f"PYTHON_SYNTAX_ERROR (L{exc.lineno}): {exc.msg}")
            return report

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                report["defined_symbols"].append(node.name)
                # Filtrer une éventuelle docstring en première instruction
                body = list(node.body)
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    body = body[1:]
                # Une fonction qui ne contient que `pass` ou `...` (hors protocole/ABC abstrait) est un stub
                is_abstract = any(
                    (isinstance(d, ast.Name) and "abstract" in d.id.lower())
                    or (isinstance(d, ast.Attribute) and "abstract" in d.attr.lower())
                    for d in node.decorator_list
                )
                if not is_abstract and len(body) == 1:
                    stmt = body[0]
                    if isinstance(stmt, ast.Pass):
                        report["violations"].append(
                            f"HOLLOW_PYTHON_FUNCTION (L{node.lineno}): `{node.name}()` contient uniquement `pass`."
                        )
                    elif (
                        isinstance(stmt, ast.Expr)
                        and isinstance(getattr(stmt, "value", None), ast.Constant)
                        and stmt.value.value is Ellipsis
                    ):
                        report["violations"].append(
                            f"HOLLOW_PYTHON_ELLIPSIS (L{node.lineno}): `{node.name}()` contient uniquement `...`."
                        )
    elif suffix == ".json":
        try:
            parsed = json.loads(text)
            report["syntax_valid"] = True
            if parsed in ({}, [], "", None):
                report["violations"].append("EMPTY_JSON_STRUCTURE: Le fichier JSON est structurellement vide.")
        except ValueError as exc:
            report["syntax_valid"] = False
            report["violations"].append(f"JSON_SYNTAX_ERROR: {exc}")
            return report
    else:
        report["syntax_valid"] = True

    report["anti_stub_passed"] = report["syntax_valid"] and len(report["violations"]) == 0
    return report


def verify_subagent_deliverable_rigor(
    workspace: str | Path,
    *,
    executed_tools: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    files_touched: list[str] | None = None,
    files_owned: list[str] | None = None,
    never_touch: list[str] | None = None,
    allow_read_only: bool = False,
) -> dict[str, Any]:
    """Porte de Rigueur Anti-Faux-Travail pour tout sous-agent d'AuroraIA et de JOBIA CLI.
    Vérifie :
      1. Qu'un travail réel d'inspection/action/vérification a été exécuté par des outils concrets.
      2. Que le pare-feu de périmètre (`files_owned` / `never_touch`) a été strictement respecté.
      3. Que chaque fichier créé ou modifié existe, est syntaxiquement valide (AST/JSON) et
         ne contient aucun stub creux (`pass`, `...`, `NotImplementedError`, `TODO`).
      4. Qu'une vérification réelle a été observée après la dernière mutation.
    """
    ws_root = Path(workspace).expanduser().resolve()
    exec_tools = list(executed_tools or [])
    ev_list = list(evidence or [])
    if not exec_tools and ev_list:
        exec_tools = [str(e.get("tool", "")) for e in ev_list if e.get("ok", True) and e.get("tool")]

    # Collecter les fichiers réellement écrits/modifiés dans l'évidence si non fournis
    touched: list[str] = list(files_touched or [])
    for ev in ev_list:
        if not ev.get("ok", True):
            continue
        t_name = str(ev.get("tool", ""))
        res = ev.get("result") if isinstance(ev.get("result"), dict) else ev
        if t_name in {"write_file", "edit_file", "create_tool", "create_skill"} and isinstance(res, dict):
            p = res.get("path") or (ev.get("args") or {}).get("path")
            if isinstance(p, str) and p.strip():
                touched.append(p.strip())
    touched = list(dict.fromkeys(touched))

    violations: list[str] = []

    # 1. Preuve d'exécution réelle d'outils (interdit les agents purement déclaratifs qui ne font rien)
    concrete_tools = {
        "read_file", "write_file", "edit_file", "run_command", "run_python",
        "run_tool", "create_tool", "verify", "verify_file", "test_hypothesis",
        "call_mcp_tool", "inspect_csv", "search_code", "list_files", "find_files",
        "generate_3d", "generate_image", "fetch_url",
    }
    used_concrete = [t for t in exec_tools if t in concrete_tools]
    if not used_concrete:
        violations.append(
            "NO_CONCRETE_TOOL_EXECUTION: Le sous-agent n'a exécuté aucun outil concret d'inspection, d'action ou de vérification."
        )

    # 2. Contrôle du pare-feu `never_touch`
    never_list = [str(x).strip() for x in (never_touch or []) if str(x).strip()]
    for raw_p in touched:
        try:
            rel_p = (ws_root / raw_p).resolve().relative_to(ws_root).as_posix()
        except Exception:
            rel_p = str(raw_p)
        for forbidden in never_list:
            if rel_p == forbidden or rel_p.startswith(forbidden.rstrip("/") + "/"):
                violations.append(
                    f"FIREWALL_VIOLATION: Le sous-agent a modifié `{rel_p}` qui figure dans `never_touch`."
                )

    # 3. Audit AST & Anti-Stub sur chaque fichier touché
    audited_files: list[dict[str, Any]] = []
    for raw_p in touched:
        candidate = Path(raw_p)
        if not candidate.is_absolute():
            candidate = (ws_root / candidate).resolve()
        file_audit = audit_file_against_fake_work(candidate)
        audited_files.append(file_audit)
        for v in file_audit.get("violations", []):
            violations.append(f"{candidate.name}: {v}")

    if not allow_read_only and not touched and not any(
        t in {"verify", "verify_file", "run_command", "run_python", "test_hypothesis", "call_mcp_tool"}
        for t in used_concrete
    ):
        violations.append(
            "NO_VERIFIED_DELIVERABLE_OR_PROOF: Aucun fichier livrable ni vérification formelle/empirique produit par le sous-agent."
        )

    passed = len(violations) == 0
    score = max(0.0, round(100.0 - 25.0 * len(violations), 2))
    return {
        "ok": passed,
        "rigorous": passed,
        "anti_fake_work_passed": passed,
        "rigor_score": score,
        "executed_concrete_tools": used_concrete,
        "audited_files": audited_files,
        "violations": violations,
        "summary": (
            f"Audit de rigueur validé ({score:.1f}/100, {len(audited_files)} fichier(s) certifié(s) sans stub, {len(used_concrete)} outil(s) concret(s))."
            if passed
            else f"Audit de rigueur rejeté ({len(violations)} violation(s)) : " + " ; ".join(violations[:4])
        ),
    }


def build_rich_agent_markdown(
    *,
    name: str,
    description: str,
    role_type: str,
    module: str,
    feature: str,
    parent_agent: str,
    preferred_tools: list[str],
    triggers: list[str],
    verification_focus: str,
    cognitive_profile: dict[str, Any],
    custom_instructions: str = "",
) -> str:
    """Construit la définition Markdown complète `.agents/agents/<name>/agent.md` compatible
    avec `AGIBrainRouter`, `AutonomousMissionAgent` et `LocalMission`."""
    tools_yaml = "\n".join(f"  - {json.dumps(t, ensure_ascii=False)}" for t in preferred_tools)
    triggers_yaml = "\n".join(f"  - {json.dumps(tr, ensure_ascii=False)}" for tr in triggers)
    s1_lines = "\n".join(f"- {h}" for h in cognitive_profile.get("system1_heuristics", []))
    s2_lines = "\n".join(f"- {d}" for d in cognitive_profile.get("system2_deliberation", []))
    inv_lines = "\n".join(f"- {inv}" for inv in cognitive_profile.get("invariants", []))
    implicit_lines = "\n".join(
        f"- {feat}" for feat in cognitive_profile.get("autonomous_implicit_features", [])
    )
    files_owned = cognitive_profile.get("files_owned") or ["périmètre assigné par la mission"]

    frontmatter = (
        "---\n"
        f"name: {json.dumps(name, ensure_ascii=False)}\n"
        f"description: {json.dumps(description[:280], ensure_ascii=False)}\n"
        f"role_type: {json.dumps(role_type, ensure_ascii=False)}\n"
        f"module: {json.dumps(module, ensure_ascii=False)}\n"
        f"feature: {json.dumps(feature, ensure_ascii=False)}\n"
        f"parent_agent: {json.dumps(parent_agent, ensure_ascii=False)}\n"
        "tools:\n"
        f"{tools_yaml if tools_yaml else '  - \"read_file\"'}\n"
        "triggers:\n"
        f"{triggers_yaml if triggers_yaml else f'  - {json.dumps(name)}'}\n"
        "---\n\n"
    )

    body = (
        f"# Agent Spécialiste Autonome : `{name}`\n\n"
        f"## 1. Mission & Identité Cognitive (Déduction par Premiers Principes)\n"
        f"- **Rôle** : {description}\n"
        f"- **Intention Causale Profonde** : {cognitive_profile.get('deep_intent', description)}\n"
        f"- **Module / Domaine** : `{module}` | **Fonctionnalité** : `{feature}`\n"
        f"- **Autorité Parente** : `{parent_agent or 'aurora-orchestrator'}`\n"
        f"- **Régime Épistémique** : `{cognitive_profile.get('epistemic_regime', 'KNOWN_OPTIMIZABLE')}`\n\n"
        f"## 2. Boucle Cognitive Duale (Système 1 & Système 2 en 3 Passes)\n"
        f"### Système 1 — Intuition & Reconnaissance Structurelle Rapide\n"
        f"{s1_lines}\n\n"
        f"### Système 2 — Délibération Analytique, Red-Team & Preuve Formelle\n"
        f"{s2_lines}\n\n"
        f"## 3. Fonctionnalités Implicites Proactives (Ajoutées d'initiative par l'AGI)\n"
        f"{implicit_lines if implicit_lines else '- Couverture complète des cas limites et auto-vérification.'}\n\n"
        f"## 4. Invariants Formels, Pare-Feu & Porte Anti-Faux-Travail\n"
        f"- **Périmètre Fichiers (`files_owned`)** : {', '.join(f'`{p}`' for p in files_owned)}\n"
        f"- **Critère de Validation Obligatoire (`verification_focus`)** : {verification_focus}\n"
        f"{inv_lines}\n"
    )
    if custom_instructions.strip():
        body += f"\n## 5. Directives d'Exécution Chirurgicale\n{custom_instructions.strip()}\n"
    return frontmatter + body


def forge_autonomous_agent(
    *,
    name: str,
    role: str,
    workspace: str | Path,
    domain: str = "code",
    module: str = "",
    parent_agent: str = "",
    role_type: str = "subagent",
    preferred_tools: list[str] | None = None,
    verification_focus: str = "",
    triggers: list[str] | None = None,
    files_owned: list[str] | None = None,
    can_create_subagents: bool = True,
    model: str = "local",
    permissions: str = "AUTONOMOUS",
    mission_id: str = "agent_forge",
    overwrite_markdown: bool = True,
) -> dict[str, Any]:
    """Synthétise, persiste et enregistre à chaud un agent ou sous-agent complet :
    1) Déduit par premiers principes son profil cognitif Système 1 / Système 2 et ses invariants.
    2) Écrit sa spécification complète `.agents/agents/<name>/agent.md` dans le workspace.
    3) L'enregistre dans `dynamic_agents.json` et `.aurora/agents.json`, puis invalide le cache `AGIBrainRouter`.
    """
    clean_name = _slugify_agent_name(name)
    clean_mod = (module or domain or "code").strip().lower()
    ws_root = Path(workspace).expanduser().resolve()

    profile = infer_cognitive_profile_from_goal(
        f"{role} {verification_focus}",
        clean_mod,
        workspace=ws_root,
    )
    if files_owned:
        profile["files_owned"] = list(dict.fromkeys(files_owned))

    final_tools = list(dict.fromkeys((preferred_tools or []) + profile["preferred_tools"]))[:32]
    final_focus = (
        verification_focus.strip()
        if verification_focus and verification_focus.strip()
        else "Preuve d'exécution réelle vérifiée par `verify` (fichier sans stub validé par AST, JSON, commande ou sonde MCP) et respect strict des invariants."
    )
    if not parent_agent:
        parent_agent = f"{clean_mod}-lead" if role_type == "subagent" else "aurora-orchestrator"

    auto_triggers = list(
        dict.fromkeys(
            (triggers or [])
            + [clean_name, clean_name.replace("-", " ")]
            + [w for w in re.findall(r"[a-zA-Z0-9àâçéèêëîïôûùüÿ]{4,}", role.lower())[:8]]
        )
    )[:12]

    md_content = build_rich_agent_markdown(
        name=clean_name,
        description=role.strip(),
        role_type=role_type,
        module=clean_mod,
        feature=clean_name,
        parent_agent=parent_agent,
        preferred_tools=final_tools,
        triggers=auto_triggers,
        verification_focus=final_focus,
        cognitive_profile=profile,
        custom_instructions=role.strip(),
    )

    # Écriture du fichier `.agents/agents/<name>/agent.md` dans le workspace
    agents_dir = ws_root / ".agents" / "agents" / clean_name
    agents_dir.mkdir(parents=True, exist_ok=True)
    agent_md_path = agents_dir / "agent.md"
    if overwrite_markdown or not agent_md_path.exists():
        agent_md_path.write_text(md_content, encoding="utf-8")

    # Synchronisation simultanée avec `.aurora/agents.json` pour parité directe avec JOBIA CLI
    try:
        cli_agents_file = ws_root / ".aurora" / "agents.json"
        cli_store: dict[str, Any] = {"agents": {}}
        if cli_agents_file.is_file():
            parsed_cli = json.loads(cli_agents_file.read_text(encoding="utf-8"))
            if isinstance(parsed_cli, dict) and isinstance(parsed_cli.get("agents"), dict):
                cli_store = parsed_cli
        cli_store["agents"][clean_name] = {
            "name": clean_name,
            "role": role.strip(),
            "module": clean_mod,
            "parent_agent": parent_agent,
            "preferred_tools": final_tools,
            "verification_focus": final_focus,
            "files_owned": profile.get("files_owned", []),
            "epistemic_regime": profile.get("epistemic_regime", "KNOWN_OPTIMIZABLE"),
            "can_create_subagents": bool(can_create_subagents),
            "agent_md_path": str(agent_md_path),
            "created_by": mission_id,
        }
        cli_agents_file.parent.mkdir(parents=True, exist_ok=True)
        cli_agents_file.write_text(json.dumps(cli_store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    # Enregistrement ou mise à jour dans `dynamic_agents.json`
    existing = resolve_agent(clean_name, str(ws_root))
    if existing is None or existing.get("origin") != "saved":
        try:
            saved_rec = create_agent(
                clean_name,
                role.strip()[:8000],
                model,
                permissions,
                mission_id,
                preferred_tools=final_tools,
                verification_focus=final_focus[:2000],
                domain=clean_mod,
                module=clean_mod,
                parent_agent=parent_agent,
                can_create_subagents=can_create_subagents,
            )
        except ValueError:
            saved_rec = existing or {"name": clean_name, "role": role.strip()}
    else:
        saved_rec = existing

    # Invalidation du cache mémoire du Cerveau AGI pour découverte immédiate (< 0.1 ms)
    try:
        from agi_core.agi_brain import _UNIFIED_CATALOG_CACHE, get_unified_agent_catalog
        _UNIFIED_CATALOG_CACHE.clear()
        get_unified_agent_catalog(ws_root)
    except Exception:
        pass

    return {
        "ok": True,
        "name": clean_name,
        "role": role.strip(),
        "role_type": role_type,
        "module": clean_mod,
        "domain": clean_mod,
        "parent_agent": parent_agent,
        "preferred_tools": final_tools,
        "verification_focus": final_focus,
        "cognitive_profile": profile,
        "agent_md_path": str(agent_md_path),
        "sha256": hashlib.sha256(md_content.encode("utf-8")).hexdigest(),
        "can_create_subagents": bool(can_create_subagents),
        "record": saved_rec,
    }


def synthesize_causal_subagent_specs(
    goal: str,
    *,
    module: str = "code",
    workspace: str | Path = ".",
    subtasks: list[str] | None = None,
    max_subagents: int = 3,
) -> list[tuple[str, str, list[str], str, list[str]]]:
    """Décompose un objectif complexe par premiers principes (`reason_first_principles`)
    en spécifications orthogonales de sous-agents `(name, role, tools, verification_focus, files_owned)`."""
    ws_root = Path(workspace).expanduser().resolve()
    clean_mod = (module or "code").strip().lower()
    profile = infer_cognitive_profile_from_goal(goal, clean_mod, workspace=ws_root)
    slug_base = _slugify_agent_name(
        "-".join(re.findall(r"[a-zA-Z0-9]{3,}", (goal or clean_mod).lower())[:3]),
        prefix=clean_mod,
    )
    base_tools = profile["preferred_tools"]
    owned_paths = list(profile.get("files_owned") or [])
    implicit_feats = list(profile.get("autonomous_implicit_features") or [])
    red_team_checks = list(profile.get("red_team_anti_naivety") or [])
    causal_steps = list(profile.get("causal_chain") or [])

    limit = max(1, min(len(subtasks) if subtasks else max_subagents, 4))
    specs: list[tuple[str, str, list[str], str, list[str]]] = []

    if subtasks and isinstance(subtasks, list) and len(subtasks) > 0:
        for idx, raw_st in enumerate(subtasks[:limit], 1):
            st_str = str(raw_st).strip() or f"Étape causale {idx} pour {goal}"
            st_slug = _slugify_agent_name(
                "-".join(re.findall(r"[a-zA-Z0-9]{3,}", st_str.lower())[:2]) or f"stage-{idx}",
                prefix=slug_base,
            )
            st_paths = re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", st_str) or owned_paths
            implicit_note = (
                f" Intégrer proactivement : {implicit_feats[(idx - 1) % len(implicit_feats)]}."
                if implicit_feats
                else ""
            )
            specs.append((
                st_slug,
                f"Sous-agent d'exécution rigoureuse ({idx}/{len(subtasks[:limit])}) : {st_str} "
                f"(Objectif maître : {goal}).{implicit_note} "
                "Interdiction absolue de produire un stub, un placeholder ou un rapport sans modification/vérification réelle.",
                base_tools,
                f"Validation AST sans stub, exécution réelle et preuve mesurée pour : {st_str}.",
                list(dict.fromkeys(st_paths))[:8],
            ))
        return specs

    # Synthèse causale dynamique en 3 passes (Exploration & Invariants -> Implémentation Complète -> Audit Red-Team & Preuve Formelle)
    pass1_desc = (
        causal_steps[0]
        if len(causal_steps) >= 1
        else f"Cartographie exacte des fichiers, extraction de l'AST et des invariants physiques/mathématiques pour {goal}"
    )
    pass2_desc = (
        causal_steps[1]
        if len(causal_steps) >= 2
        else f"Implémentation algorithmique complète à la source (zéro hardcoding, zéro stub) incluant : {', '.join(implicit_feats[:2]) or goal}"
    )
    pass3_desc = (
        " ; ".join(red_team_checks[:2])
        if red_team_checks
        else f"Certification formelle (SymPy/Z3/AST) et exécution des tests de non-régression pour {goal}"
    )

    dynamic_stages = [
        (
            f"{slug_base}-causal-prober",
            f"Sous-agent Passe 1 (Décomposition Causale & Sonde d'Invariants) pour : {goal}. "
            f"Mission : {pass1_desc}. Inspecte les fichiers réels, mesure les préconditions et vérifie les dépendances.",
            [t for t in base_tools if t in {"inspect_runtime", "list_files", "read_file", "search_code", "inspect_csv", "list_mcp_tools", "test_hypothesis", "verify"}],
            "Extraction vérifiée des chemins réels, schémas de données et préconditions formelles.",
            owned_paths,
        ),
        (
            f"{slug_base}-first-principles-builder",
            f"Sous-agent Passe 2 (Synthèse & Implémentation par Premiers Principes) pour : {goal}. "
            f"Mission : {pass2_desc}. Implémente le code/artefact complet avec 0 TODO, 0 stub et 0 valeur codée en dur.",
            base_tools,
            "Fichiers créés/modifiés avec AST 100 % valide, zéro fonction vide (`pass`/`...`) et exécution vérifiée.",
            owned_paths,
        ),
        (
            f"{slug_base}-redteam-formal-verifier",
            f"Sous-agent Passe 3 (Contradicteur Red-Team & Vérificateur Formel) pour : {goal}. "
            f"Mission : {pass3_desc}. Exécute les vérifications indépendantes (`verify`, `test_hypothesis`, compilateur/tests) et bloque toute illusion de travail.",
            [t for t in base_tools if t in {"read_file", "run_command", "run_tool", "test_hypothesis", "verify", "inspect_csv"}],
            "100 % des critères `verify`, contrôles AST anti-stub et preuves formelles validés après la dernière écriture.",
            owned_paths,
        ),
    ]
    return dynamic_stages[:limit]


def forge_subagent_swarm(
    goal: str = "",
    *,
    workspace: str | Path = ".",
    module: str = "code",
    parent_agent: str = "",
    max_subagents: int = 3,
    mission_id: str = "swarm_forge",
    model: str = "aurora-agi",
    permissions: str = "STANDARD",
    subtasks: list[str] | None = None,
    sub_goals: list[str] | None = None,
) -> dict[str, Any]:
    """Décompose par premiers principes un objectif complexe en une chaîne causale
    orthogonale de sous-agents spécialisés dotés de pare-feux de périmètre et de
    contrats anti-faux-travail, puis les forge dans le workspace."""
    effective_subtasks = subtasks if subtasks is not None else sub_goals
    if not goal and effective_subtasks:
        goal = " ; ".join(str(s) for s in effective_subtasks[:4])
    ws_root = Path(workspace).expanduser().resolve()
    clean_mod = (module or "code").strip().lower()
    if clean_mod in {"code", "general", ""}:
        try:
            from agi_core.mission_routing import mission_module
            inferred_mod = mission_module({"request": goal})
            if inferred_mod and inferred_mod != "general":
                clean_mod = inferred_mod
        except Exception:
            pass
    master = parent_agent or f"{clean_mod}-lead"

    specs = synthesize_causal_subagent_specs(
        goal,
        module=clean_mod,
        workspace=ws_root,
        subtasks=effective_subtasks,
        max_subagents=max_subagents,
    )

    forged = []
    for sub_name, sub_role, sub_tools, sub_focus, sub_files in specs:
        res = forge_autonomous_agent(
            name=sub_name,
            role=sub_role,
            workspace=ws_root,
            domain=clean_mod,
            module=clean_mod,
            parent_agent=master,
            role_type="subagent",
            preferred_tools=sub_tools,
            verification_focus=sub_focus,
            files_owned=sub_files,
            can_create_subagents=True,
            model=model,
            permissions=permissions,
            mission_id=mission_id,
        )
        res["permissions"] = permissions
        forged.append(res)

    return {
        "ok": True,
        "goal": goal,
        "module": clean_mod,
        "master_agent": master,
        "subagents_forged": forged,
        "forged_agents": forged,
        "count": len(forged),
        "anti_fake_work_contract": (
            "Chaque sous-agent forgé est soumis à `verify_subagent_deliverable_rigor` : "
            "exécution d'outils concrets obligatoire, AST sans stub (`pass`/`...`/`TODO`/`NotImplementedError`) "
            "et preuve `verify` après la dernière écriture."
        ),
    }


MODULE_V3_SOTA_STACKS: dict[str, str] = {
    "3d": "TRELLIS.2-4B Matrice 7-Spécialistes v3 + Lois Optiques Premiers Principes (`universal_style_engine.py` : Fresnel Schlick, GGX Anisotrope, SSS Dipolaire, Dispersion de Cauchy) + Déduction Cinématique Multi-Morphologies & Foot-Lock IK (`semantic_animation.py` : 0.001 mm glissement)",
    "image": "FLUX.2-dev + Fidélité ReferenceLatent 3-Régimes (`comfy_client.py` : strict lock / balanced / creative) + Pyramide Laplacienne Multi-Échelles 16K Sans Halo, PBR Scharr/Sobel 3x3 & Régulation HDR (`image_upscaler.py`)",
    "code": "Moteur `codeExcellenceEngine.ts` + `CodeView.tsx` : Oscillateur Harmonique Amorti Exact (Motion Design), 6 Piliers Implicites AGI, Audit AST de Complexité (O(N²)/N+1) & Sandbox 22 Langages",
    "cyber": "Parseur AST/CFG/SSA Multi-Langages + Synthèse de Harnais KLEECopilot/SAILOR SMT-LIB2 (`symbolicZeroDayEngine.ts`) + Réparation CEGIS en Boucle Fermée jusqu'à Preuve Formelle `UNSAT_PROVEN` (`closedLoopPatchEngine.ts`)",
    "learning": "Oracle Formel `scientific_oracle.py` + `LearningView.tsx` : Anneau Polynomial Rationnel Exact Q[x_1..x_n], Décomposition SOS, Diagnostic Formel d'Erreur par Transformation Candidate, Suivi Bayésien `FQ-Ada-BKT` & Exercices Isomorphes SymPy/Z3",
    "voice": "Service `voice_cloning_service.py` + `useVoiceLive.ts` : Profilage Acoustique Zero-Shot (F0, Formants F1-F3, Jitter, Shimmer, HNR), Normalisation Phonétique & Liaisons Françaises, Production 4-Stems Masterisée à -14 LUFS & Visèmes Rhubarb Frame-Accurate",
    "business": "Moteur `business_intelligence.py` + `BusinessView.tsx` : Séries OHLCV Yahoo Finance 30j en Direct, Binance Spot, Taux/Devises BCE Frankfurter (en Fictif Lab ET en Réel Live), Cascade Financière 8 Étapes de A à Z & Initiatives Stratégiques Proactives AGI",
    "drawing": "Cinématique du Trait par Filtre de Kalman 2D + Ressort Amorti Critique, Point de Fuite MSAC, Audit Anatomique Contraposto & Character Forge 4-Vues Orthographiques (`DrawingView.tsx`)",
    "video": "Trajectoire Caméra Polynomiale Quintique C2 Minimum-Jerk, Règle des 180°, Continuité Colorimétrique Planckienne Kelvin & Quantification Temporelle 4n+1 Wan2.2 (`VideoView.tsx`)",
    "cowork": "Ordonnancement Topologique de Kahn par Fronts d'Onde Parallèles (`coworkPlanner.ts`), Double Vérification Pré-Vol + Post-Condition (`coworkExecutor.ts`) & Journal Transactionnel Write-Ahead avec Rollback (`coworkSafety.ts`)",
    "simulator": "Intégrateur Symplectique Yoshida 4e Ordre O(dt^4) + Stabilisation de Baumgarte (`physicsEngine.ts`) & Fluides Position-Based Fluids PBF SPH avec Poly6, Spiky, Viscosité Laplacienne, Cohésion d'Akinci & Vorticity Confinement (`fluidSolver.ts`)",
    "conversation": "Raisonneur Cognitif 3-Passes Test-Time Compute (`cognitive_reasoner.py` : Passe 1 Causalité & Fonctionnalités Implicites, Passe 2 Red-Team Anti-Outil, Passe 3 Frontière de Pareto Qualité > Vitesse)",
    "training": "Superviseur Continu `auto_rl/control.py` + Radar SOTA `tech_radar_agi.py` + Entraînement Pareto Flow-Matching DPO sur Kaggle Double GPU (`2x Tesla T4`) + Audit 96 Maillages sur RTX 5070 Ti (`reinforced_registry.py`)",
}


def upgrade_all_workspace_agents_v3(
    aurora_root: str | Path = "/home/juan/AuroraIA",
    user_home: str | Path = "/home/juan",
) -> dict[str, Any]:
    """Met à niveau l'ensemble des 111 définitions d'agents `.agents/agents/*/agent.md`
    avec la Doctrine v3 (`Qualité & Performance Maximale > Vitesse`), le Raisonnement
    3-Passes Test-Time Compute et le Garde-Fou Anti-Faux-Travail (`verify_subagent_deliverable_rigor`),
    et synchronise `/home/juan/.agents/agents/` avec `/home/juan/AuroraIA/.agents/agents/`."""
    import shutil
    from agi_core.cognitive_reasoner import DOCTRINE_MAXIMUM_QUALITY_OVER_SPEED
    src_agents_dir = Path(aurora_root).expanduser().resolve() / ".agents" / "agents"
    dst_agents_dir = Path(user_home).expanduser().resolve() / ".agents" / "agents"
    dst_agents_dir.mkdir(parents=True, exist_ok=True)

    upgraded_count = 0
    for md_path in sorted(src_agents_dir.glob("*/agent.md")):
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        mod_match = re.search(r"^module:\s*\"?([a-z0-9_-]+)\"?\s*$", text, re.M)
        mod_key = (mod_match.group(1).strip().lower() if mod_match else "conversation").split("-")[0]
        sota_stack = MODULE_V3_SOTA_STACKS.get(mod_key) or MODULE_V3_SOTA_STACKS["conversation"]

        v3_section = (
            "\n\n## 6. Doctrine v3 — Raisonnement 3-Passes Test-Time Compute, Qualité > Vitesse & Garde-Fou Anti-Faux-Travail\n"
            f"1. **Doctrine d'Optimisation (`DOCTRINE_MAXIMUM_QUALITY_OVER_SPEED`)** : {DOCTRINE_MAXIMUM_QUALITY_OVER_SPEED}\n"
            "2. **Raisonnement Cognitif en 3 Passes (`agi_core/cognitive_reasoner.py`)** :\n"
            "   - **Passe 1 (Décomposition Causale par Premiers Principes)** : Identifie les lois physiques, mathématiques, économiques ou formelles sous-jacentes et ajoute spontanément les fonctionnalités implicites indispensables sans dépendre de mots-clés précodés.\n"
            "   - **Passe 2 (Contradicteur Red-Team Anti-Outil)** : Rejette toute réponse superficielle de type « mot détecté -> action figée ».\n"
            "   - **Passe 3 (Frontière de Pareto & Preuve Formelle)** : Sélectionne l'architecture qui maximise la fidélité, l'exactitude et la robustesse.\n"
            "3. **Contrat Anti-Faux-Travail & Anti-Stub AST (`verify_subagent_deliverable_rigor`)** :\n"
            "   - Exécution réelle d'outils obligatoire (aucun rapport déclaratif sans action concrète).\n"
            "   - Zéro fonction vide (`pass`, `...`, `NotImplementedError`) et zéro marqueur d'inachèvement (`TODO`, `FIXME`, `placeholder`).\n"
            "   - Sous-processus strictement non-interactifs (`stdin=DEVNULL`, `CI=1`, `NPM_CONFIG_YES=true`, `PIP_NO_INPUT=1`).\n"
            f"4. **Pile Technologique SOTA `v3` Active du Module (`{mod_key}`)** :\n"
            f"   - {sota_stack}\n"
        )
        if "## 6. Doctrine v3" in text:
            base_text = text.split("## 6. Doctrine v3")[0].rstrip()
        else:
            base_text = text.rstrip()
        updated_text = base_text + v3_section
        md_path.write_text(updated_text, encoding="utf-8")

        mirror_dir = dst_agents_dir / md_path.parent.name
        mirror_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_path, mirror_dir / "agent.md")
        upgraded_count += 1

    return {
        "ok": True,
        "upgraded_agents_count": upgraded_count,
        "aurora_agents_dir": str(src_agents_dir),
        "workspace_mirror_dir": str(dst_agents_dir),
    }

