"""End-to-end test of the Code module on NON-BRAND projects.

Until tour 13 every E2E test focused on brand_landing pages (Coca-Cola,
Tesla, Lipton). The user pointed out that the module is also for game
clones (Tetris, Snake, Clash Royale...), app clones (Instagram, Facebook,
TikTok...), and innovation projects — and it should pick the best
language for each project type. This harness covers that wider scope.

The script detects the project type from the prompt (game/spa_react/
fullstack/etc.) using simplified rules from codeIntent.ts, builds a
matching system prompt (visual design contract for web/app, non-visual
quality contract for CLI/library/data), then asks Ollama and scores the
output with type-specific criteria — NOT the brand fidelity rules.

Usage:
    python scripts/test-project-type-e2e.py "clone de Tetris jouable"
    python scripts/test-project-type-e2e.py "Instagram clone avec stories"
    python scripts/test-project-type-e2e.py "app de gestion taches IA"
"""

from __future__ import annotations

import json
import os as _os
import re
import sys
import time

import requests

TUNNEL = "https://fin-isaac-reduce-fingers.trycloudflare.com"
MODEL = _os.environ.get("AURORA_TEST_MODEL", "qwen3-coder-next:q4_K_M")


def detect_project_type(prompt: str) -> dict:
    """Mirror simplified rules from codeIntent.ts to predict what the LLM should produce."""
    lowered = prompt.lower()

    # Known games — should produce canvas + game loop + scoring etc.
    known_games = {
        "tetris": {
            "type": "game_web", "canonical": "Tetris",
            "must_have": ["canvas", "tetromino", "rotation", "score", "game loop"],
            "controls": "fleches gauche/droite/bas, haut/Z rotation, espace hard drop",
        },
        "snake": {
            "type": "game_web", "canonical": "Snake",
            "must_have": ["canvas", "grid", "fruit", "score", "game loop", "collision"],
            "controls": "fleches directionnelles ou WASD",
        },
        "pong": {
            "type": "game_web", "canonical": "Pong",
            "must_have": ["canvas", "paddle", "ball", "score"],
            "controls": "joueur W/S, IA ou joueur 2 fleches",
        },
        "flappy": {
            "type": "game_web", "canonical": "Flappy Bird",
            "must_have": ["canvas", "gravity", "pipes", "score"],
            "controls": "espace ou clic = flap",
            # Flappy se joue principalement au clic/tap, pas au clavier — donc
            # le check has_keyboard du game_web gate est inadequat ici.
            "keyboard_optional": True,
        },
        "2048": {
            "type": "game_web", "canonical": "2048",
            "must_have": ["grid", "merge", "fusion", "score"],
            "controls": "fleches ou swipe",
        },
        "breakout": {
            "type": "game_web", "canonical": "Breakout",
            "must_have": ["canvas", "paddle", "ball", "brick", "score"],
            "controls": "fleches ou souris",
        },
        "asteroid": {
            "type": "game_web", "canonical": "Asteroids",
            "must_have": ["canvas", "vaisseau", "asteroide", "score"],
            "controls": "fleches + espace tir",
        },
    }
    for token, spec in known_games.items():
        if token in lowered:
            return {**spec, "kind": "known_game"}

    # Generic game request — canvas-based but no canonical mechanics.
    if any(kw in lowered for kw in ["jeu", "game", "playable", "jouable", "arcade", "playable game"]):
        return {
            "kind": "generic_game", "type": "game_web", "canonical": None,
            "must_have": ["canvas", "game loop", "score", "controls"],
        }

    # App clones — should produce SPA with components, feed, etc.
    app_clones = {
        "instagram": {
            "canonical": "Instagram", "type": "spa_react",
            "must_have": ["feed", "post", "story", "like", "follow"],
        },
        "facebook": {
            "canonical": "Facebook", "type": "spa_react",
            "must_have": ["feed", "post", "friend", "comment"],
        },
        "twitter": {
            "canonical": "Twitter", "type": "spa_react",
            "must_have": ["timeline", "tweet", "follow", "retweet"],
        },
        "tiktok": {
            "canonical": "TikTok", "type": "spa_react",
            "must_have": ["video feed", "scroll", "like", "follow"],
        },
        "spotify": {
            "canonical": "Spotify", "type": "spa_react",
            "must_have": ["playlist", "play", "library", "audio"],
        },
        "whatsapp": {
            "canonical": "WhatsApp", "type": "spa_react",
            "must_have": ["chat", "message", "contact"],
        },
    }
    for token, spec in app_clones.items():
        if token in lowered:
            return {**spec, "kind": "app_clone"}

    # Backend / API
    if any(kw in lowered for kw in ["fastapi", "rest api python"]) or "api fastapi" in lowered:
        return {"kind": "api", "type": "api_fastapi", "canonical": None,
                "must_have": ["fastapi", "app", "router", "endpoint"]}
    if any(kw in lowered for kw in ["spring boot", "spring-boot", "java spring", "api java"]):
        return {"kind": "api", "type": "api_java", "canonical": None,
                "must_have": ["@RestController", "@SpringBootApplication", "public class", "@RequestMapping"]}
    if any(kw in lowered for kw in ["go api", "gin framework", "golang api", "api gin"]):
        return {"kind": "api", "type": "api_go", "canonical": None,
                "must_have": ["package main", "func main", "import", "http"]}
    if any(kw in lowered for kw in ["api rest", "express", "rest api"]) or "api node" in lowered:
        return {"kind": "api", "type": "api_express", "canonical": None,
                "must_have": ["express", "app", "router", "middleware"]}

    # CLI — Python first (most common for "cli" + "script" prompts).
    if any(kw in lowered for kw in ["cli python", "outil python", "script python", "argparse"]):
        return {"kind": "cli", "type": "cli_python", "canonical": None,
                "must_have": ["argparse", "main", "sys.exit"]}
    if any(kw in lowered for kw in ["cli node", "cli nodejs", "outil node"]):
        return {"kind": "cli", "type": "cli_node", "canonical": None,
                "must_have": ["yargs", "process.argv", "main"]}
    if any(kw in lowered for kw in ["cli rust", "outil rust", "rust tool"]):
        return {"kind": "cli", "type": "cli_rust", "canonical": None,
                "must_have": ["fn main", "use", "std::"]}
    if any(kw in lowered for kw in ["cli go", "outil go", "go tool", "golang tool"]):
        return {"kind": "cli", "type": "cli_go", "canonical": None,
                "must_have": ["package main", "func main", "import", "os.Args"]}
    if any(kw in lowered for kw in ["cli", "terminal", "command line", "outil ligne"]):
        return {"kind": "cli", "type": "cli_python", "canonical": None,
                "must_have": ["argparse", "main", "sys.exit"]}

    # Library — npm package or pypi
    if any(kw in lowered for kw in ["npm package", "lib npm", "package npm", "library npm", "librairie npm"]):
        return {"kind": "library", "type": "library_npm", "canonical": None,
                "must_have": ["package.json", "module.exports", "readme"]}
    if any(kw in lowered for kw in ["pypi package", "lib python", "library python", "librairie python"]):
        return {"kind": "library", "type": "library_pypi", "canonical": None,
                "must_have": ["setup.py", "__init__", "readme"]}

    # Mobile — React Native or Flutter
    if any(kw in lowered for kw in ["react native", "expo", "rn app", "app react native"]):
        return {"kind": "mobile", "type": "mobile_rn", "canonical": None,
                "must_have": ["expo", "react native", "view", "stylesheet"]}
    if any(kw in lowered for kw in ["flutter", "dart app"]):
        return {"kind": "mobile", "type": "mobile_flutter", "canonical": None,
                "must_have": ["pubspec", "material", "widget", "scaffold"]}

    # Desktop — Tauri or Electron
    if any(kw in lowered for kw in ["tauri", "app tauri"]):
        return {"kind": "desktop", "type": "desktop_tauri", "canonical": None,
                "must_have": ["cargo.toml", "tauri.conf", "main.rs", "package.json"]}
    if any(kw in lowered for kw in ["electron", "app electron"]):
        return {"kind": "desktop", "type": "desktop_electron", "canonical": None,
                "must_have": ["main.js", "package.json", "browserwindow"]}

    # Data / ML — split between data analysis (pandas+plot) and ML proper.
    is_ml = any(kw in lowered for kw in ["scikit", "tensorflow", "pytorch", "machine learning", "ml model", "neural", "deep learning", "train model"])
    is_data = any(kw in lowered for kw in ["pandas", "analyse de donnees", "analyse donnees", "visualisation", "matplotlib", "data analysis"])
    if is_ml:
        return {"kind": "data_ml", "type": "data_python", "canonical": None,
                "must_have": ["import", "train", "model", "predict"]}
    if is_data:
        return {"kind": "data_analysis", "type": "data_python", "canonical": None,
                "must_have": ["import", "pandas", "plot"]}

    # Subject variants for SPA-class prompts (saas/portfolio/ecommerce/dashboard).
    # These all route through spa_react but inject variant-specific design
    # sections that mirror codeDesignReference.SUBJECT_VARIANTS in TS.
    if re.search(r"\b(dashboard|admin|console|analytics|stats|metrics|monitoring|kpi|backoffice|tableau de bord)\b", lowered):
        return {"kind": "spa_dashboard", "type": "spa_react", "subject_variant": "dashboard", "canonical": None,
                "must_have": ["sidebar", "kpi", "chart", "table"]}
    if re.search(r"\b(boutique|shop|magasin|ecommerce|e-commerce|panier|cart|store|catalogue|achat)\b", lowered):
        return {"kind": "spa_ecommerce", "type": "spa_react", "subject_variant": "ecommerce", "canonical": None,
                "must_have": ["product", "cart", "price", "rating"]}
    if re.search(r"\b(portfolio|portefeuille|cv|curriculum|showcase|freelance|graphiste|photographe|artiste)\b", lowered):
        return {"kind": "spa_portfolio", "type": "spa_react", "subject_variant": "portfolio", "canonical": None,
                "must_have": ["project", "gallery", "tag", "skill"]}
    if re.search(r"\b(saas|abonnement|subscription|pricing|tarif|enterprise|productivit|crm|erp)\b", lowered):
        return {"kind": "spa_saas", "type": "spa_react", "subject_variant": "saas", "canonical": None,
                "must_have": ["pricing", "tier", "feature", "enterprise"]}

    # Default — probably a SPA / web app innovation
    return {"kind": "innovation", "type": "spa_react", "canonical": None,
            "must_have": ["component", "state"]}


def build_system_prompt(prompt: str, spec: dict) -> str:
    """Build a prompt that mirrors what codeOrchestrator would assemble for
    this project type — without any brand subject lock.
    """
    type_label = spec.get("type", "unknown")
    must_have = spec.get("must_have", [])
    canonical = spec.get("canonical")
    is_visual = type_label in ("game_web", "spa_react", "spa_vue", "static_web", "ssr_nextjs", "fullstack_mern")

    lines = [
        "Tu es un Developpeur Senior du pipeline AuroraIA. Tu generes du CODE SOURCE PUR.",
        "Format: chaque fichier commence par `--- FICHIER: chemin/nom.ext ---` puis contenu complet.",
        "",
        "## CHOIX DU LANGAGE / STACK",
        "Tu choisis LE MEILLEUR langage et stack pour ce projet. Critere:",
        "- Le plus simple qui fait le job.",
        "- Aligne avec les conventions du domaine (canvas pour les jeux 2D, React pour les SPA modernes, FastAPI/Express pour les API, etc.).",
        "- Si l user demande une stack specifique, respecte-la. Sinon, choisis.",
        "",
        f"## TYPE DE PROJET DETECTE: {type_label}",
    ]
    if canonical:
        lines.append(f"## SUJET CANONIQUE: {canonical}")
        lines.append(f'- Tu construis un clone de {canonical}. Le code DOIT respecter les regles connues de {canonical} (mecanique, controles, score).')
        lines.append('- INTERDIT de inventer des regles fantaisistes — reproduis les mecaniques canoniques.')
    if must_have:
        lines.append("")
        lines.append(f"## ELEMENTS CLES OBLIGATOIRES")
        lines.append(f"- Le code doit inclure: {', '.join(must_have)}.")
    lines.append("")

    if is_visual:
        lines.extend([
            "## DESIGN CONTRACT — non negociable",
            "- Hero / interface principale: layout propre, palette coherente, typo lisible.",
            "- Animations: transitions fluides, scroll reveal, hover states. Pas d UI rigide.",
            "- Mode sombre/clair quand pertinent (CSS variables + prefers-color-scheme).",
            "- Code propre, modulaire, lisible.",
            "",
        ])
        if type_label == "game_web":
            lines.extend([
                "## SPECIFICITES JEU WEB",
                "- requestAnimationFrame avec delta time (PAS setInterval).",
                "- keydown + keyup events, prevent default sur fleches/espace.",
                "- localStorage pour high score persistent.",
                "- Web Audio API pour sons synthetises (oscillator + gain) sur action/score/game over — apres 1er user gesture.",
                "- ECRANS: demarrage stylise + jeu + game over avec score + bouton Rejouer.",
                "- Particles, screen shake, flash blanc 100ms = juice obligatoire.",
                "- Responsive canvas via resize listener.",
                "",
            ])
        elif type_label in ("spa_react", "fullstack_mern"):
            lines.extend([
                "## SPECIFICITES SPA / APP",
                "- React 18+ avec hooks (useState/useEffect/useCallback).",
                "- Composants modulaires dans src/components/.",
                "- State management simple (useState ou Context, pas de Redux sauf necessaire).",
                "- CSS Modules ou Tailwind ou inline styles propres.",
                "- Mock data realiste pour le feed/posts/messages.",
                "",
            ])
            # Subject-variant specific sections (mirror codeDesignReference.SUBJECT_VARIANTS).
            subject_variant = spec.get("subject_variant")
            variant_sections = {
                "saas": [
                    "## SECTIONS SPECIFIQUES SAAS",
                    "- Hero focus value-prop B2B + dashboard preview a droite.",
                    "- 'Logos clients' marquee horizontal anime.",
                    "- 'Features grid' 6-9 cards avec icone SVG + titre + 2 lignes.",
                    "- 'Comment ca marche' 3 etapes numerotees avec stepper.",
                    "- 'Pricing tiers' 3 plans (free/pro/enterprise) en cartes, plan recommande highlight.",
                    "- 'Integrations' grille 12-20 logos.",
                    "- 'Testimonials' avec avatar + nom + role.",
                    "- 'FAQ' accordion avec animation hauteur.",
                    "- CTA final XL gradient avec microcopy ('essai gratuit, sans CB').",
                    "",
                ],
                "portfolio": [
                    "## SECTIONS SPECIFIQUES PORTFOLIO",
                    "- Hero personnel: nom + role + 1 ligne mission, photo/illustration ronde.",
                    "- 'Selected work' gallery masonry (grid auto-fill minmax 280px).",
                    "- Project cards: image + titre + tags + hover overlay description.",
                    "- Animation gallery: stagger fade-in (delay 80ms par card).",
                    "- 'Case study' detail: cover + contexte + role/stack + screenshots.",
                    "- 'About me' colonne gauche photo, droite bio + skills tags (pills).",
                    "- 'Contact' form simple + email direct + reseaux icons SVG.",
                    "- Footer minimal avec annee dynamique.",
                    "",
                ],
                "ecommerce": [
                    "## SECTIONS SPECIFIQUES ECOMMERCE",
                    "- Hero: best-seller en vedette + CTA 'Decouvrir' + visuel produit central.",
                    "- 'Categories' grid 4-6 cards image + label, hover scale 1.04.",
                    "- 'Products grid' 12-24 cards: image, badge promo, prix barre, rating, bouton Ajouter au panier.",
                    "- Quick view au hover: overlay translucent.",
                    "- 'Filters sidebar' (desktop) ou drawer mobile: categories, prix range, marques.",
                    "- 'Cart drawer' sticky right avec items, qty +/-, total, Commander.",
                    "- 'Reviews' carousel scroll horizontal scroll-snap.",
                    "- Footer 4 cols: shop, aide, marque, newsletter.",
                    "- Trust badges: livraison gratuite, retour 30j, paiement secure.",
                    "",
                ],
                "dashboard": [
                    "## SECTIONS SPECIFIQUES DASHBOARD",
                    "- Layout: sidebar fixe gauche 240px + main contenu.",
                    "- Sidebar: logo top, nav items (icone + label), user pill bottom.",
                    "- Top bar: titre, search bar, notifications icon+badge, theme toggle, avatar.",
                    "- 'KPI cards' row: 4 cartes avec gros chiffre + delta % (vert/rouge), sparkline mini.",
                    "- 'Main chart' panel: line/bar chart en CSS pur ou canvas.",
                    "- 'Data table' avec header sticky, rows zebrees, sort icons, pagination.",
                    "- 'Activity feed' colonne droite: events recents + icones colorees + timestamp.",
                    "- 'Quick actions' cards 2x2 avec icone gradient + label.",
                    "- Skeleton loaders pendant data fetch.",
                    "- Mobile: sidebar drawer, KPI stack, table scroll-x.",
                    "",
                ],
            }
            if subject_variant and subject_variant in variant_sections:
                lines.extend(variant_sections[subject_variant])
    else:
        lines.extend([
            "## QUALITE OUTPUT (non-visuel)",
            "- Error handling explicite, pas de catch silent.",
            "- README.md avec install + usage.",
            "- Tests pour les API publiques quand pertinent.",
            "",
        ])

    lines.extend([
        "## REGLES UNIVERSELLES",
        "- ZERO TODO / ZERO placeholder / ZERO 'reste du code ici'.",
        "- Chaque fichier complet et autonome.",
        "- Le code doit s executer sans modification.",
        "- README.md court (install + run).",
        "",
        "GENERE LE CODE MAINTENANT.",
    ])
    return "\n".join(lines)


def call_ollama(system_prompt: str, user_prompt: str, *, timeout: int = 480) -> str:
    """Streaming call via /proxy/ollama/api/chat to avoid Cloudflare 524."""
    url = f"{TUNNEL}/proxy/ollama/api/chat"
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "options": {"temperature": 0.05, "num_predict": 6000, "num_ctx": 16384},
    }
    print(f"[1/3] POST {url} (model={MODEL}, system={len(system_prompt)} chars)")
    t0 = time.time()
    chunks: list[str] = []
    with requests.post(url, json=body, timeout=timeout, stream=True) as resp:
        print(f"[2/3] HTTP {resp.status_code}")
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = obj.get("message", {}).get("content") or obj.get("response") or ""
            if piece:
                chunks.append(piece)
            if obj.get("done"):
                break
    total = sum(len(c) for c in chunks)
    elapsed = time.time() - t0
    print(f"[2/3] streamed {total} chars over {elapsed:.1f}s ({len(chunks)} chunks)")
    return "".join(chunks)


def evaluate_output(output: str, spec: dict) -> dict:
    """Type-specific scoring — NOT brand-fidelity rules."""
    lowered = output.lower()
    must_have = spec.get("must_have", [])
    canonical = spec.get("canonical")
    type_label = spec.get("type")

    matched_keywords = [kw for kw in must_have if kw.lower() in lowered]
    canonical_present = canonical.lower() in lowered if canonical else None
    # parseCodeFiles in TS accepts many forms: "--- FICHIER:", "FICHIER:",
    # "### FICHIER:", "**FICHIER:**". Match all variants — line that has
    # FICHIER: followed by a path-like string. Case-insensitive (catches
    # "Fichier:" too). Works in French and English (file: also accepted).
    file_count = len(re.findall(r"(?:^|\n)[^\n]{0,8}(?:FICHIER|FILE):\s*\S+\.\w+", output, re.IGNORECASE))

    # Type-specific signals
    has_canvas = "canvas" in lowered or "<canvas" in lowered
    has_game_loop = "requestanimationframe" in lowered or "game loop" in lowered
    has_react = ("react" in lowered or "usestate" in lowered) and ("import" in lowered)
    has_keyboard = "keydown" in lowered or "addeventlistener('key" in lowered or 'addeventlistener("key' in lowered
    has_score = "score" in lowered
    has_localstorage = "localstorage" in lowered
    has_components = "function " in lowered and ("return (" in lowered or "return <" in lowered)
    has_components |= "const " in lowered and "=> " in lowered and "<" in lowered
    has_audio = "audiocontext" in lowered or "oscillator" in lowered or "<audio" in lowered

    # v77j — non-visual signals
    has_argparse = "import argparse" in lowered or "argparse.argumentparser" in lowered
    has_main_block = "if __name__" in lowered and "__main__" in lowered
    has_sys_exit = "sys.exit" in lowered or "exit(" in lowered
    has_fastapi = "from fastapi" in lowered or "fastapi import" in lowered
    has_app_decorator = "@app." in lowered or "@router." in lowered
    has_express = "require('express')" in lowered or 'require("express")' in lowered or "import express" in lowered
    has_package_json = '"name"' in output and '"version"' in output and '"main"' in output
    has_module_exports = "module.exports" in lowered or "export default" in lowered or "export {" in lowered
    has_readme = re.search(r"readme(?:\.md)?", lowered) is not None
    has_setup_py = "setup.py" in lowered or "setup(" in lowered or "pyproject.toml" in lowered
    has_init_py = "__init__.py" in lowered

    return {
        "type_detected": type_label,
        "canonical": canonical,
        "canonical_present": canonical_present,
        "must_have_matched": matched_keywords,
        "must_have_total": len(must_have),
        "file_count": file_count,
        "has_canvas": has_canvas,
        "has_game_loop": has_game_loop,
        "has_react": has_react,
        "has_keyboard": has_keyboard,
        "has_score": has_score,
        "has_localstorage": has_localstorage,
        "has_components": has_components,
        "has_audio": has_audio,
        "has_argparse": has_argparse,
        "has_main_block": has_main_block,
        "has_sys_exit": has_sys_exit,
        "has_fastapi": has_fastapi,
        "has_app_decorator": has_app_decorator,
        "has_express": has_express,
        "has_package_json": has_package_json,
        "has_module_exports": has_module_exports,
        "has_readme": has_readme,
        "has_setup_py": has_setup_py,
        "has_init_py": has_init_py,
        "output_length": len(output),
    }


def score_output(report: dict, spec: dict, output: str = "") -> tuple[int, list[str]]:
    """Return (score 0-100, list of issues)."""
    issues: list[str] = []
    score = 100
    type_label = spec.get("type")
    canonical = spec.get("canonical")
    must_have_total = report["must_have_total"] or 1

    # Universal — must have at least one file
    if report["file_count"] == 0:
        issues.append("no --- FICHIER: --- separator (output not parseable)")
        score = min(score, 30)

    # Universal — must hit majority of must_have keywords
    matched_ratio = len(report["must_have_matched"]) / must_have_total
    if matched_ratio < 0.5:
        issues.append(f"only {len(report['must_have_matched'])}/{must_have_total} must-have keywords matched ({int(matched_ratio*100)}%)")
        score -= 25

    # Canonical-aware — when a known game/app, the name should appear
    if canonical and report["canonical_present"] is False:
        issues.append(f'"{canonical}" missing from output')
        score -= 15

    # Type-specific gates
    if type_label == "game_web":
        if not report["has_canvas"]:
            issues.append("game_web: no <canvas> (-15)")
            score -= 15
        if not report["has_game_loop"]:
            issues.append("game_web: no requestAnimationFrame (-10)")
            score -= 10
        # v77p: certains games (Flappy, mobile-first arcades) se jouent au
        # clic/tap, pas au clavier. Quand spec.keyboard_optional, on accepte
        # un click handler en remplacement du keyboard.
        keyboard_optional = bool(spec.get("keyboard_optional"))
        has_click_input = "addeventlistener('click'" in output.lower() or 'addeventlistener("click"' in output.lower() \
            or "onclick" in output.lower() or "ontouchstart" in output.lower() or "addeventlistener('touch" in output.lower()
        if not report["has_keyboard"] and not (keyboard_optional and has_click_input):
            issues.append("game_web: no keyboard or click input handlers (-10)")
            score -= 10
        if not report["has_score"]:
            issues.append("game_web: no score variable (-5)")
            score -= 5
    elif type_label in ("spa_react", "fullstack_mern"):
        if not report["has_react"]:
            issues.append("spa: no React imports / useState detected (-15)")
            score -= 15
        if not report["has_components"]:
            issues.append("spa: no functional components detected (-10)")
            score -= 10
    elif type_label == "cli_python":
        if not report["has_argparse"]:
            issues.append("cli_python: no argparse import (-15)")
            score -= 15
        if not report["has_main_block"]:
            issues.append('cli_python: no `if __name__ == "__main__"` block (-10)')
            score -= 10
        if not report["has_sys_exit"]:
            issues.append("cli_python: no sys.exit() — exit codes missing (-5)")
            score -= 5
    elif type_label == "cli_node":
        # Node CLI uses process.argv or yargs/commander.
        if not (report["has_module_exports"] or "process.argv" in output):
            issues.append("cli_node: no process.argv / yargs detected (-15)")
            score -= 15
    elif type_label == "api_fastapi":
        if not report["has_fastapi"]:
            issues.append("api_fastapi: no FastAPI import (-15)")
            score -= 15
        if not report["has_app_decorator"]:
            issues.append("api_fastapi: no @app./router. decorator (-10)")
            score -= 10
    elif type_label == "api_express":
        if not report["has_express"]:
            issues.append("api_express: no express import (-15)")
            score -= 15
        if not report["has_app_decorator"] and "app.get" not in output.lower() and "app.post" not in output.lower():
            issues.append("api_express: no app.get/post route (-10)")
            score -= 10
    elif type_label == "api_java":
        # Spring Boot Java API: must have @SpringBootApplication or @RestController.
        java_signals = ("@springbootapplication", "@restcontroller", "@requestmapping", "@getmapping", "public class")
        if not any(sig in output.lower() for sig in java_signals):
            issues.append("api_java: no Spring Boot annotations / class detected (-15)")
            score -= 15
    elif type_label == "api_go":
        go_signals = ("package main", "func main", "net/http", "gin.")
        matched = sum(1 for sig in go_signals if sig in output.lower())
        if matched < 2:
            issues.append(f"api_go: only {matched}/{len(go_signals)} Go signals detected (-15)")
            score -= 15
    elif type_label == "cli_rust":
        rust_signals = ("fn main", "use std", "let mut", "println!", "cargo.toml")
        matched = sum(1 for sig in rust_signals if sig in output.lower())
        if matched < 2:
            issues.append(f"cli_rust: only {matched}/{len(rust_signals)} Rust signals detected (-15)")
            score -= 15
    elif type_label == "cli_go":
        go_signals = ("package main", "func main", "os.args", "flag.")
        matched = sum(1 for sig in go_signals if sig in output.lower())
        if matched < 2:
            issues.append(f"cli_go: only {matched}/{len(go_signals)} Go CLI signals detected (-15)")
            score -= 15
    elif type_label == "library_npm":
        if not report["has_package_json"]:
            issues.append('library_npm: no proper package.json (name/version/main fields) (-15)')
            score -= 15
        if not report["has_module_exports"]:
            issues.append("library_npm: no module.exports / export (-10)")
            score -= 10
        if not report["has_readme"]:
            issues.append("library_npm: no README.md (-5)")
            score -= 5
    elif type_label == "library_pypi":
        if not (report["has_setup_py"] or "pyproject.toml" in output.lower()):
            issues.append("library_pypi: no setup.py / pyproject.toml (-15)")
            score -= 15
        if not report["has_init_py"]:
            issues.append("library_pypi: no __init__.py (-10)")
            score -= 10
    elif type_label == "data_python":
        # Data ML — must have at least one of the ML libs.
        ml_libs = ("pandas", "numpy", "scikit", "torch", "tensorflow")
        if not any(lib in output.lower() for lib in ml_libs):
            issues.append("data_python: no ML library import (-15)")
            score -= 15
    elif type_label == "mobile_rn":
        # React Native specific signals.
        rn_signals = ("react-native", "react native", "from 'react-native'", 'from "react-native"', "stylesheet", "expo")
        if not any(sig in output.lower() for sig in rn_signals):
            issues.append("mobile_rn: no React Native imports detected (-15)")
            score -= 15
    elif type_label == "mobile_flutter":
        flutter_signals = ("import 'package:flutter", "scaffold", "widget", "pubspec.yaml")
        if not any(sig in output.lower() for sig in flutter_signals):
            issues.append("mobile_flutter: no Flutter imports/widgets detected (-15)")
            score -= 15
    elif type_label == "desktop_tauri":
        tauri_signals = ("tauri.conf.json", "cargo.toml", "src-tauri", "use tauri", "tauri::")
        if not any(sig in output.lower() for sig in tauri_signals):
            issues.append("desktop_tauri: no Tauri files / Rust source (-15)")
            score -= 15
    elif type_label == "desktop_electron":
        electron_signals = ("require('electron')", 'require("electron")', "browserwindow", "ipcmain")
        if not any(sig in output.lower() for sig in electron_signals):
            issues.append("desktop_electron: no electron imports / BrowserWindow (-15)")
            score -= 15

    # Output length sanity — too short = probably truncated
    if report["output_length"] < 1500:
        issues.append(f"output too short ({report['output_length']} chars) — probably truncated")
        score -= 20

    return max(0, score), issues


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test-project-type-e2e.py '<prompt>'", file=sys.stderr)
        return 2
    prompt = sys.argv[1]

    spec = detect_project_type(prompt)
    print(f"[0/3] Detected: kind={spec['kind']} type={spec.get('type')} canonical={spec.get('canonical')}")

    system_prompt = build_system_prompt(prompt, spec)

    try:
        output = call_ollama(system_prompt, prompt)
    except Exception as exc:
        print(f"[FAIL] Ollama call failed: {exc}", file=sys.stderr)
        return 2

    print(f"[3/3] Output length: {len(output)} chars")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", prompt).strip("-").lower()[:60] or "project"
    out_dir = _os.environ.get("AURORA_TEST_OUT") or _os.path.join(
        _os.environ.get("TEMP") or _os.environ.get("TMPDIR") or "/tmp",
        "aurora-test-outputs",
    )
    output_path = _os.path.join(out_dir, f"project-e2e-{slug}.txt")
    try:
        _os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[3/3] Saved raw output -> {output_path}")
    except OSError:
        pass

    report = evaluate_output(output, spec)
    score, issues = score_output(report, spec, output)

    print()
    print("=" * 64)
    print(f"PROJECT FIDELITY REPORT — {prompt!r}")
    print("=" * 64)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print()
    print(f"SCORE: {score}/100")
    if issues:
        print("ISSUES:")
        for line in issues:
            print(f"  - {line}")
    else:
        print("ISSUES: none")
    print("=" * 64)
    return 0 if score >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
