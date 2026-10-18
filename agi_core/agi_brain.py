"""Cerveau AGI & Orchestrateur d'Appliquants Spécialisés (Brain + Module Masters + Feature Applicators).

Ce module dote AuroraIA du même système multi-agents hiérarchique que l'environnement de
développement Antigravity :
  1. Découverte bi-racine des définitions d'agents :
     - Workspace : `<workspace>/.agents/agents/{agent_name}/agent.md`
     - Global    : `~/.gemini/config/agents/{agent_name}/agent.md`
     - Registre  : `application/agent_registry.py` (`AGENTS`)
  2. Décomposition cognitive d'une requête complexe en sous-tâches atomiques sans divagation.
  3. Attribution déterministe de chaque sous-tâche à :
     - 1 Agent Maître de Module (`role_type: "master"`)
     - 1 Sous-Agent Appliquant de Fonctionnalité (`role_type: "subagent"`)
  4. Pare-feu d'exécution (`scope_firewall`) garantissant qu'aucun appliquant ne déborde sur
     les fichiers (`files_owned`), routes (`routes_owned`) ou zones interdites (`never_touch`)
     d'un autre agent.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

DEFAULT_WORKSPACE = Path(__file__).resolve().parents[1]
GLOBAL_AGENTS_DIR = Path.home() / ".gemini" / "config" / "agents"


def parse_agent_md(content: str, fallback_name: str = "") -> dict[str, Any]:
    """Parse un fichier `agent.md` (frontmatter YAML + corps d'instructions Markdown)."""
    meta: dict[str, Any] = {
        "name": fallback_name,
        "description": "",
        "role_type": "subagent",
        "module": "",
        "feature": fallback_name,
        "parent_agent": "",
        "tools": [],
        "triggers": [],
        "hidden": False,
        "body": content.strip(),
    }
    if not content.startswith("---\n") and not content.startswith("---\r\n"):
        return meta

    parts = content.split("---", 2)
    if len(parts) < 3:
        return meta

    frontmatter_raw, body = parts[1], parts[2].strip()
    meta["body"] = body
    current_list_key: str | None = None

    for line in frontmatter_raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kv_match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if kv_match:
            key, raw_val = kv_match.group(1), kv_match.group(2).strip()
            if not raw_val:
                current_list_key = key if key in {"tools", "triggers"} else None
                continue
            current_list_key = None
            try:
                val = json.loads(raw_val)
            except ValueError:
                if raw_val.lower() in {"true", "false"}:
                    val = raw_val.lower() == "true"
                else:
                    val = raw_val.strip("'\"")
            meta[key] = val
        elif current_list_key and re.match(r"^\s*-\s+(.+)$", line):
            item_raw = re.sub(r"^\s*-\s+", "", line).strip()
            try:
                item_val = json.loads(item_raw)
            except ValueError:
                item_val = item_raw.strip("'\"")
            if isinstance(meta.get(current_list_key), list):
                meta[current_list_key].append(item_val)

    return meta


def discover_markdown_agents(workspace: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Découvre tous les fichiers `agent.md` dans Workspace (`.agents/agents/*/agent.md`)
    et Global (`~/.gemini/config/agents/*/agent.md`), avec priorité au Workspace.
    """
    ws_root = Path(workspace).expanduser().resolve() if workspace else DEFAULT_WORKSPACE
    # Si workspace pointe sur application/, remonter à la racine du dépôt AuroraIA si .agents y existe
    if not (ws_root / ".agents" / "agents").is_dir() and (ws_root.parent / ".agents" / "agents").is_dir():
        ws_root = ws_root.parent

    roots = [
        ("global", GLOBAL_AGENTS_DIR),
        ("workspace", ws_root / ".agents" / "agents"),
    ]
    discovered: dict[str, dict[str, Any]] = {}
    for scope, base_dir in roots:
        if not base_dir.is_dir():
            continue
        try:
            entries = sorted(base_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            agent_file = entry / "agent.md"
            if not entry.is_dir() or not agent_file.is_file():
                continue
            try:
                if agent_file.stat().st_size > 256 * 1024:
                    continue
                raw = agent_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            parsed = parse_agent_md(raw, fallback_name=entry.name)
            name = str(parsed.get("name") or entry.name).strip()
            prev = discovered.get(name, {})
            discovered[name] = {
                **prev,
                **parsed,
                "name": name,
                "scope": scope,
                "agent_md_path": str(agent_file),
                "workspace_agent_md": str(ws_root / ".agents" / "agents" / name / "agent.md"),
                "global_agent_md": str(GLOBAL_AGENTS_DIR / name / "agent.md"),
            }
    return discovered


def get_unified_agent_catalog(workspace: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Fusionne le registre Python `application/agent_registry.py` et les fichiers
    `.agents/agents/{agent_name}/agent.md` + `~/.gemini/config/agents/{agent_name}/agent.md`.
    """
    try:
        from application.agent_registry import AGENTS
    except ImportError:
        try:
            from agent_registry import AGENTS
        except ImportError:
            AGENTS = {}

    md_agents = discover_markdown_agents(workspace)
    unified: dict[str, dict[str, Any]] = {}

    all_names = sorted(set(AGENTS.keys()) | set(md_agents.keys()))
    for name in all_names:
        reg_info = dict(AGENTS.get(name, {}))
        md_info = dict(md_agents.get(name, {}))
        merged = {
            "name": name,
            "role_type": reg_info.get("role_type") or md_info.get("role_type") or "subagent",
            "module": reg_info.get("module") or md_info.get("module") or reg_info.get("domain") or "orchestration",
            "domain": reg_info.get("domain") or reg_info.get("module") or md_info.get("module") or "orchestration",
            "feature": reg_info.get("feature") or md_info.get("feature") or name,
            "parent_agent": reg_info.get("parent_agent") or md_info.get("parent_agent") or "",
            "description": reg_info.get("description") or md_info.get("description") or "",
            "role": reg_info.get("role") or md_info.get("body") or md_info.get("description") or "",
            "files_owned": list(reg_info.get("files_owned") or []),
            "routes_owned": list(reg_info.get("routes_owned") or []),
            "never_touch": list(reg_info.get("never_touch") or []),
            "subagents": list(reg_info.get("subagents") or []),
            "preferred_tools": list(reg_info.get("preferred_tools") or md_info.get("tools") or []),
            "verification_focus": reg_info.get("verification_focus") or "",
            "can_create_subagents": bool(
                reg_info.get("can_create_subagents", (reg_info.get("role_type") in {"orchestrator", "master"}))
            ),
            "permissions": reg_info.get("permissions", "AUTONOMOUS"),
            "agent_md_path": md_info.get("agent_md_path") or str(DEFAULT_WORKSPACE / ".agents" / "agents" / name / "agent.md"),
            "workspace_agent_md": md_info.get("workspace_agent_md") or str(DEFAULT_WORKSPACE / ".agents" / "agents" / name / "agent.md"),
            "global_agent_md": md_info.get("global_agent_md") or str(GLOBAL_AGENTS_DIR / name / "agent.md"),
            "body": md_info.get("body") or "",
        }
        unified[name] = merged
    return unified


# Mots-clés sémantiques de haut niveau vers les modules et sous-agents appliquants
FEATURE_KEYWORDS_INDEX: dict[str, tuple[str, ...]] = {
    # Conversation
    "conversation-intent-router": ("intention", "intent", "router", "routage", "ambigu", "classification dialogue"),
    "conversation-pipeline-tuner": ("streaming", "sse", "think", "latence chat", "conversation", "ollama chat"),
    "conversation-web-factchecker": ("recherche web", "factcheck", "source web", "citation", "actualité", "wikipedia"),
    "conversation-memory-keeper": ("mémoire conversation", "historique chat", "bm25", "souvenir"),
    "conversation-vision-multimodal": ("image jointe", "vision", "ocr", "qwen-vl", "capture écran"),
    # Code
    "code-architecture-planner": ("architecture", "arborescence", "plan code", "multi-fichiers", "contrat typescript"),
    "code-design-architect": ("motion design", "ui", "ux", "animation", "shader", "webgl", "design", "css", "glassmorphism", "60fps"),
    "code-backend-performance": ("backend", "sql", "index", "performance", "complexité", "concurrence", "api", "latence serveur"),
    "code-fidelity-auditor": ("fidélité", "audit code", "todo", "placeholder", "stub", "score code"),
    "code-sandbox-runner": ("sandbox", "preview", "iframe", "babel", "compilation live", "exécution code"),
    "code-delivery-packager": ("zip", "export code", "livraison projet", "workspace_projects"),
    # Image
    "image-prompt-director": ("prompt image", "développer prompt", "expansion prompt", "direction photo", "éclairage", "focale"),
    "image-flux-stylist": ("flux", "flux2", "flux.2", "comfyui", "txt2img", "img2img", "inpainting", "génération image"),
    "image-reference-researcher": ("référence", "personnage connu", "marque", "reproduction", "wikimedia"),
    "image-upscale-16k-pbr": ("8k", "16k", "upscale", "netteté", "super-résolution", "32-bit", "exr", "texture pbr image"),
    "image-job-cancellation": ("arrêter génération", "stop image", "interrupt", "étape image", "progression image"),
    "image-output-organizer": ("dossier création", "dossier modification", "creations", "modifications", "galerie image"),
    # Drawing
    "drawing-canvas-stroke": ("pinceau", "calque", "trait", "dessin", "croquis", "canvas"),
    "drawing-sketch-interpreter": ("interpréter dessin", "esquisse", "sumi", "geste"),
    "drawing-controlnet-renderer": ("controlnet", "scribble", "canny", "lineart", "sketch to image"),
    "drawing-character-forge": ("character forge", "character sheet", "turnaround", "fiche personnage"),
    # 3D
    "3d-pipeline-router": ("pipeline 3d", "classification 3d", "mode 3d"),
    "3d-neural-generator": ("hunyuan3d", "trellis", "maillage neuronal", "génération 3d", "lora 3d"),
    "3d-mesh-postprocessor": ("topologie", "manifold", "watertight", "normales", "décimation", "quad", "maillage"),
    "3d-texture-lead": ("texture 3d", "uv", "xatlas", "pbr", "albedo", "roughness", "metallic", "bake"),
    "3d-quality-rescuer": ("auto-rescue", "validation 3d", "4 vues", "score 3d", "réparation 3d"),
    "3d-motion-rigger": ("rigging", "squelette", "skinning", "armature", "animation 3d"),
    "3d-cad-engineering": ("cao", "cad", "b-rep", "géométrie pure", "step", "stl", "iso", "paramétrique", "cadquery", "openscad"),
    "3d-assembly-kinematics": ("assemblage", "éclaté", "cinématique", "collision", "bvh", "liaison", "multi-pièces"),
    "3d-splat-telemetry": ("splat", "gaussian splatting", "télémétrie 3d"),
    "3d-viewer-lead": ("viewer 3d", "three.js", "draco", "meshopt", "coupe 3d", "wireframe"),
    # Video
    "video-storyboard-director": ("storyboard", "découpage plans", "cadrage vidéo"),
    "video-motion-director": ("vidéo", "ltx", "wan2.1", "mp4", "ffmpeg", "rendu vidéo"),
    "video-hymotion-kinematics": ("hy-motion", "mouvement humain", "trajectoire caméra"),
    "video-talking-head": ("talking head", "musetalk", "liveportrait", "portrait parlant"),
    # Voice
    "voice-stt-transcriber": ("stt", "whisper", "transcription", "microphone", " reconnaissance vocale"),
    "voice-tts-stt-tuner": ("tts", "kokoro", "voix", "synthèse vocale", "prosodie"),
    "voice-lipsync": ("lipsync", "visème", "rhubarb", "synchronisation labiale"),
    "voice-live-duplex": ("duplex", "barge-in", "mains-libres", "push-to-talk"),
    # Learning & Simulator
    "learning-formal-oracle": ("preuve formelle", "sympy", "z3", "lean4", "démonstration mathématique", "oracle"),
    "learning-bac-curator": ("cours", "bac", "fiche révision", "programme scolaire"),
    "learning-quiz-verifier": ("quiz", "exercice", "anki", "flashcard", "qcm"),
    "learning-lab-integrator": ("passerelle labo", "formule vers simulateur"),
    "simulator-physics-engine": ("physique", "rk4", "rapier", "gravité", "pendule", "mécanique"),
    "simulator-fluid-particles": ("fluide", "sph", "électromagnétisme", "onde", "optique"),
    "simulator-chemistry-electronics": ("chimie", "molécule", "circuit", "électronique", "rlc"),
    "simulator-scene-io": ("preset simulation", "export csv simulation", "scène physique"),
    # Cyber
    "cyber-symbolic-zeroday": ("z3 cyber", "exécution symbolique", "taint", "ast audit", "cve", "cwe", "vulnérabilité"),
    "cyber-closedloop-patcher": ("patch sécurité", "remédiation", "correctif vulnérabilité"),
    "cyber-lab-builder": ("ctf", "lab cyber", "sandbox sécurité"),
    "cyber-pyops-keeper": ("sbom", "dépendances sécurité", "scan secrets"),
    "cyber-network-recon": ("ports", "headers http", "csp", "cors", "tls"),
    # Cowork
    "cowork-orchestrator-tuner": ("cowork", "automatisation multi-étapes", "workflow cowork"),
    "cowork-connector-keeper": ("extension chrome", "connecteur", "ssh", "dom"),
    "cowork-safety-auditor": ("permission cowork", "validation humaine", "safe standard autonomous"),
    "cowork-doc-extractor": ("extraction pdf", "docx", "xlsx", "document structuré"),
    # Business
    "business-market-research": ("étude de marché", "tam", "sam", "som", "concurrence", "demande"),
    "business-financial-analyst": ("trésorerie", "cashflow", "marge", "bfr", "dso", "ltv", "cac", "van", "tri"),
    "business-risk-manager": ("risque", "ruine", "kelly", "drawdown", "veto"),
    "business-entrepreneur": ("saas", "offre", "pricing", "go-to-market", "mvp"),
    "business-quant": ("monte-carlo", "walk-forward", "backtest", "quant"),
    "business-economist": ("macroéconomie", "inflation", "taux directeur", "fiscalité"),
    "business-technical": ("coût cloud", "coût gpu", "faisabilité technique"),
    "business-critic": ("red-team", "pré-mortem", "biais de survie", "coût caché"),
    "business-auditor": ("provenance données", "kill-switch", "calibration business"),
    # Training
    "training-control-supervisor": ("stop_after_cycle", "fin de cycle", "arrêt entraînement", "démon auto-rl"),
    "training-kaggle-cloud": ("kaggle", "colab", "2xt4", "kernel gpu", "cloud training"),
    "training-3d-flow-dpo": ("3d-flow-dpo", "chamfer", "entraînement 3d", "nocturne 3d"),
    "training-multi-module-dpo": ("dpo", "grpo", "fine-tuning", "lora multi-module"),
    "training-audit-evaluator": ("holdout", "benchmark entraînement", "vrai gain", "promotion modèle"),
    "training-reinforced-registry": ("modèle renforcé", "modèle de base", "gains.md", "modele/renforce"),
    # Missions, Bridge, CLI
    "missions-store-lease": ("file d'attente", "bouton projet", "mission active", "lease", "heartbeat"),
    "missions-protocol-verifier": ("critère d'acceptation", "sha-256", "reçu atomique", "verified"),
    "missions-epistemic-recovery": ("stagnation", "black swan", "reprise mission", "cause racine"),
    "missions-delegation-spawner": ("délégation", "sous-mission", "spawn_agent"),
    "bridge-routes-contract": ("route flask", "blueprint", " bridge 3001", "contrat json"),
    "bridge-gpu-governor": ("vram", "rtx 5080", "arbitrage gpu", "oom"),
    "bridge-tauri-native": ("tauri", "rust", "webkitgtk", "fenêtre native"),
    "bridge-systemd-watchdog": ("systemd", "watchdog", "service", "port 3001"),
    "cli-jobia-tui": ("jobia", "tui", "cli terminal", "raccourcis cli"),
    "tunnel-validator": ("tunnel", "cloudflared", "trycloudflare", "aurora-live"),
    "cli-artifact-delivery": ("téléchargement cli", "transfert artefact", "pull fichier"),
    "web-action-runner": ("port 3034", "workspace persistant", "contrôle mobile"),
}


class AGIBrainRouter:
    """Cerveau central AGI qui analyse toute requête, sélectionne le(s) Maître(s) de Module
    et le(s) Sous-Agent(s) Appliquant(s) de Fonctionnalité, et génère un contrat d'exécution
    strictement cloisonné (sans mélange ni divagation).
    """

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace).expanduser().resolve() if workspace else DEFAULT_WORKSPACE
        self.catalog = get_unified_agent_catalog(self.workspace)

    def score_applicator(
        self,
        agent_name: str,
        agent_info: dict[str, Any],
        query_lower: str,
        active_module: str | None = None,
        target_paths: list[str] | None = None,
    ) -> float:
        score = 0.0
        if agent_info.get("role_type") != "subagent":
            return 0.0

        # 1. Bonus fort si le module actif correspond
        if active_module and (
            agent_info.get("module") == active_module or agent_info.get("domain") == active_module
        ):
            score += 15.0

        # 2. Correspondance directe sur les fichiers ou routes propriétaires
        targets = [t.lower() for t in (target_paths or [])]
        for owned_file in agent_info.get("files_owned", []):
            owned_lower = owned_file.lower()
            base_name = Path(owned_lower.split("#")[0]).name
            if base_name and base_name in query_lower:
                score += 45.0
            if any(owned_lower in t or base_name in t for t in targets):
                score += 60.0

        for owned_route in agent_info.get("routes_owned", []):
            route_lower = owned_route.lower()
            if route_lower in query_lower or any(route_lower in t for t in targets):
                score += 55.0

        # 3. Correspondance sur les mots-clés de fonctionnalité exclusifs
        for kw in FEATURE_KEYWORDS_INDEX.get(agent_name, ()):
            if kw in query_lower:
                score += 25.0 + len(kw) * 0.5

        # 4. Correspondance sur feature / nom d'agent / description
        feat = (agent_info.get("feature") or "").lower().replace("_", " ")
        if feat and feat in query_lower:
            score += 30.0
        if agent_name.lower() in query_lower:
            score += 80.0

        desc_tokens = set(re.findall(r"[a-z0-9àâçéèêëîïôûùüÿñæœ]{4,}", (agent_info.get("description") or "").lower()))
        query_tokens = set(re.findall(r"[a-z0-9àâçéèêëîïôûùüÿñæœ]{4,}", query_lower))
        overlap = len(desc_tokens & query_tokens)
        score += overlap * 3.5

        return round(score, 2)

    def plan_execution(
        self,
        request_text: str,
        *,
        active_module: str | None = None,
        target_paths: list[str] | None = None,
        max_applicators: int = 4,
    ) -> dict[str, Any]:
        """Construit le plan cognitif complet Cerveau AGI -> Agent(s) Maître(s) -> Appliquant(s)
        avec pare-feu anti-mélange (`scope_firewall`) et critères de validation (`verification_gate`).
        """
        query = (request_text or "").strip()
        query_lower = query.lower()
        norm_module = (active_module or "").strip().lower() or None

        scored: list[tuple[float, str, dict[str, Any]]] = []
        for name, info in self.catalog.items():
            sc = self.score_applicator(name, info, query_lower, norm_module, target_paths)
            if sc > 0:
                scored.append((sc, name, info))

        scored.sort(key=lambda item: (-item[0], item[1]))

        # Sélectionner les meilleurs appliquants sans redondance de fonctionnalité
        selected_applicators: list[dict[str, Any]] = []
        seen_features: set[str] = set()
        for sc, name, info in scored:
            if len(selected_applicators) >= max_applicators:
                break
            if sc < 10.0 and selected_applicators:
                break
            feat = info.get("feature") or name
            if feat in seen_features:
                continue
            seen_features.add(feat)
            master_name = info.get("parent_agent") or f"{info.get('module', 'conversation')}-lead"
            master_info = self.catalog.get(master_name) or {}
            selected_applicators.append({
                "applicator_agent": name,
                "score": sc,
                "module": info.get("module"),
                "feature": feat,
                "master_agent": master_name,
                "master_description": master_info.get("description", ""),
                "description": info.get("description", ""),
                "scope_firewall": {
                    "files_owned": info.get("files_owned", []),
                    "routes_owned": info.get("routes_owned", []),
                    "never_touch": info.get("never_touch", []),
                },
                "preferred_tools": info.get("preferred_tools", []),
                "verification_gate": info.get("verification_focus", ""),
                "agent_md_path": info.get("agent_md_path", ""),
            })

        # Fallback si la requête est très générale : utiliser le Maître du module actif (ou conversation-lead)
        if not selected_applicators:
            fallback_mod = norm_module or "conversation"
            from application.agent_registry import get_module_agent
            master = get_module_agent(fallback_mod) or self.catalog.get("conversation-lead", {})
            master_name = master.get("name", "conversation-lead")
            subs = master.get("subagents") or ["conversation-intent-router"]
            first_sub = subs[0] if subs else master_name
            sub_info = self.catalog.get(first_sub, master)
            selected_applicators.append({
                "applicator_agent": first_sub,
                "score": 10.0,
                "module": fallback_mod,
                "feature": sub_info.get("feature", fallback_mod),
                "master_agent": master_name,
                "master_description": master.get("description", ""),
                "description": sub_info.get("description", ""),
                "scope_firewall": {
                    "files_owned": sub_info.get("files_owned", []),
                    "routes_owned": sub_info.get("routes_owned", []),
                    "never_touch": sub_info.get("never_touch", []),
                },
                "preferred_tools": sub_info.get("preferred_tools", []),
                "verification_gate": sub_info.get("verification_focus", ""),
                "agent_md_path": sub_info.get("agent_md_path", ""),
            })

        masters_involved = list(dict.fromkeys(app["master_agent"] for app in selected_applicators))
        modules_involved = list(dict.fromkeys(app["module"] for app in selected_applicators))
        complexity = (
            "multi_module"
            if len(modules_involved) > 1
            else ("multi_feature" if len(selected_applicators) > 1 else "single_feature_surgical")
        )

        execution_steps = []
        for idx, app in enumerate(selected_applicators, start=1):
            execution_steps.append({
                "step": idx,
                "master": app["master_agent"],
                "applicator": app["applicator_agent"],
                "feature": app["feature"],
                "directive": (
                    f"[{app['master_agent']} → {app['applicator_agent']}] "
                    f"Traiter exclusivement la fonctionnalité `{app['feature']}` sur "
                    f"{', '.join(app['scope_firewall']['files_owned'][:3]) or 'son périmètre'} "
                    f"sans toucher à {', '.join(app['scope_firewall']['never_touch'][:3]) or 'aucun autre module'}."
                ),
                "verification": app["verification_gate"],
            })

        return {
            "ok": True,
            "schema_version": "aurora.agi_brain.v1",
            "brain_orchestrator": "aurora-orchestrator",
            "request": query,
            "complexity": complexity,
            "modules_involved": modules_involved,
            "masters_involved": masters_involved,
            "applicators": selected_applicators,
            "execution_plan": execution_steps,
            "anti_drift_contract": {
                "zero_mixing": True,
                "zero_placeholder": True,
                "require_code_evidence_before_edit": True,
                "require_verification_gate_before_done": True,
            },
        }

    def format_prompt_injection(
        self,
        request_text: str,
        *,
        active_module: str | None = None,
        agent_name: str | None = None,
    ) -> str:
        """Construit le bloc d'instructions Cerveau AGI + Appliquant à injecter dans le prompt
        système de `AutonomousMissionAgent` ou des pipelines AuroraIA.
        """
        if agent_name and agent_name in self.catalog:
            info = self.catalog[agent_name]
            parent = info.get("parent_agent") or "aurora-orchestrator"
            files_str = ", ".join(info.get("files_owned", [])) or "périmètre assigné"
            routes_str = ", ".join(info.get("routes_owned", [])) or "aucune route directe"
            never_str = ", ".join(info.get("never_touch", [])) or "tout fichier hors module"
            return (
                f"\n[ARCHITECTURE CERVEAU AGI — APPLIQUANT ACTIF : {agent_name}]\n"
                f"- Autorité Maître : {parent} | Module : {info.get('module')} | Fonctionnalité exclusive : {info.get('feature')}\n"
                f"- Périmètre Fichiers Exclusif (files_owned) : {files_str}\n"
                f"- Périmètre Routes Exclusif (routes_owned) : {routes_str}\n"
                f"- PARE-FEU ANTI-MÉLANGE (never_touch) : INTERDICTION FORMELLE de modifier {never_str}\n"
                f"- Critère de Validation Obligatoire : {info.get('verification_focus')}\n"
                f"- Règle Anti-Divagation : Reste 100% verrouillé sur la demande et ta fonctionnalité `{info.get('feature')}`. Zéro supposition sans preuve.\n"
            )

        plan = self.plan_execution(request_text, active_module=active_module)
        lines = [
            "\n[CERVEAU AGI AURORA — ROUTAGE HIÉRARCHIQUE MAÎTRE → APPLIQUANTS SPÉCIALISÉS]",
            f"- Orchestrateur Cerveau : {plan['brain_orchestrator']} | Complexité : {plan['complexity']}",
            f"- Agents Maîtres mobilisés : {', '.join(plan['masters_involved'])}",
        ]
        for step in plan["execution_plan"]:
            lines.append(
                f"  {step['step']}. {step['directive']} (Validation : {step['verification']})"
            )
        lines.append(
            "- Discipline AGI : Chaque appliquant exécute exclusivement sa fonctionnalité sans jamais mélanger les fichiers ni divaguer."
        )
        return "\n".join(lines) + "\n"
