"""True Semantic Skill Understanding, Compositional Matching & Autonomous Distillation (`agi_core/skills_engine.py`).

Remplace le simple filtrage par mots-clés figés par une compréhension sémantique et structurelle
des compétences (`SKILL.md` + `scripts/` + `examples/` + `resources/`) :
  1. Analyse structurelle d'un `SKILL.md` en graphe causal :
     - `causal_preconditions` (quand et pourquoi mobiliser la compétence)
     - `procedural_operators` (séquence ordonnée d'opérations et transformations)
     - `formal_invariants` (contraintes et post-conditions vérifiables)
     - `executable_blocks` & `companion_scripts` (code et scripts compagnons exécutables)
  2. Appariement sémantique continu sans hardcode (TF-IDF dynamique sur le corpus + n-grammes
     de caractères morphologiques + symboles de code/chemins) pour sélectionner et composer
     les compétences pertinentes même sans correspondance lexicale littérale.
  3. Distillation autonome de nouvelles compétences (`distill_skill_from_trajectory`) avec
     script compagnon vérifié par AST.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any


def _normalize_text(text: str) -> str:
    norm = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _extract_semantic_features(text: str) -> Counter[str]:
    """Extrait une représentation vectorielle creuse multi-échelle (racines lexicales,
    identifiants techniques et trigrammes morphologiques) sans aucune liste codée en dur."""
    norm = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9_]{3,}", norm)
    features: Counter[str] = Counter()
    for tok in tokens:
        features[f"w:{tok}"] += 1.0
        # Racine morphologique préfixe (invariance pluriel/conjugaison/dérivation)
        if len(tok) >= 5:
            features[f"s:{tok[:5]}"] += 0.65
        if len(tok) >= 7:
            features[f"s7:{tok[:7]}"] += 0.45
        # Trigrammes internes pour capter la proximité sémantique/orthographique
        if 4 <= len(tok) <= 18:
            padded = f"^{tok}$"
            for i in range(len(padded) - 2):
                features[f"g:{padded[i:i+3]}"] += 0.18
    return features


def parse_skill_semantically(skill: dict[str, Any]) -> dict[str, Any]:
    """Transforme un dictionnaire de compétence brut (`discover_skills`) en un graphe
    sémantique et procédural structuré."""
    content = str(skill.get("content") or "")
    name = str(skill.get("name") or "")
    description = str(skill.get("description") or "")
    triggers = list(skill.get("triggers") or [])
    skill_path = Path(str(skill.get("path") or ""))

    # Séparation du corps Markdown hors frontmatter YAML
    body = content
    if content.startswith("---\n") or content.startswith("---\r\n"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()

    headings: list[str] = []
    procedural_operators: list[str] = []
    formal_invariants: list[str] = []
    causal_preconditions: list[str] = []
    if description:
        causal_preconditions.append(description)
    for tr in triggers:
        if isinstance(tr, str) and tr.strip():
            causal_preconditions.append(tr.strip())

    # Extraction des blocs de code ```lang ... ```
    code_blocks: list[dict[str, str]] = []
    for m_code in re.finditer(r"```([a-zA-Z0-9_-]*)\n(.*?)```", body, flags=re.DOTALL):
        lang = (m_code.group(1) or "text").strip().lower()
        code_txt = (m_code.group(2) or "").strip()
        if code_txt:
            code_blocks.append({"language": lang, "code": code_txt[:4000]})

    # Analyse structurelle ligne par ligne du Markdown
    current_section = ""
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        h_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if h_match:
            current_section = h_match.group(2).strip()
            headings.append(current_section)
            continue
        bullet_match = re.match(r"^(?:[-*+]|\d+\.)\s+(.+)$", line)
        if bullet_match:
            item_txt = bullet_match.group(1).strip()
            sec_low = _normalize_text(current_section)
            item_low = _normalize_text(item_txt)
            if any(k in sec_low or k in item_low for k in ("invariant", "verif", "check", "interdit", "never", "must", "doit", "garde-fou", "preuve", "assert")):
                formal_invariants.append(item_txt[:280])
            elif any(k in sec_low for k in ("when", "quand", "precondition", "contexte", "trigger", "objectif")):
                causal_preconditions.append(item_txt[:280])
            else:
                procedural_operators.append(item_txt[:280])

    # Découverte des scripts compagnons éventuels (`<skill_dir>/scripts/*.py` ou `.sh`)
    companion_scripts: list[str] = []
    if skill_path.is_dir():
        scripts_dir = skill_path / "scripts"
        if scripts_dir.is_dir():
            try:
                for sp in sorted(scripts_dir.iterdir())[:20]:
                    if sp.is_file() and sp.suffix.lower() in {".py", ".sh", ".mjs", ".js"}:
                        companion_scripts.append(str(sp.resolve()))
            except OSError:
                pass

    # Si `description` était vide dans le frontmatter, la déduire du premier paragraphe / titre
    inferred_desc = description
    if not inferred_desc:
        first_para = next(
            (ln.strip("# ").strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("```")),
            name,
        )
        inferred_desc = first_para[:240]

    semantic_text = "\n".join([
        name.replace("-", " ").replace("_", " "),
        inferred_desc,
        " ".join(headings),
        " ".join(causal_preconditions[:10]),
        " ".join(procedural_operators[:15]),
        " ".join(formal_invariants[:10]),
        body[:6000],
    ])
    feature_counts = _extract_semantic_features(semantic_text)

    return {
        **skill,
        "description": inferred_desc,
        "headings": headings[:20],
        "causal_preconditions": causal_preconditions[:12],
        "procedural_operators": procedural_operators[:20],
        "formal_invariants": formal_invariants[:12],
        "code_blocks_count": len(code_blocks),
        "code_blocks": code_blocks[:6],
        "companion_scripts": companion_scripts,
        "_feature_counts": feature_counts,
    }


def rank_and_compose_skills(
    skills: list[dict[str, Any]] | str | Path,
    query: str = "",
    *,
    module: str = "",
    max_skills: int = 10,
    max_chars: int = 24000,
) -> dict[str, Any]:
    """Classe et compose dynamiquement les compétences découvertes selon leur résonance
    sémantique et structurelle avec `query` (TF-IDF dynamique sur le corpus + similarité
    cosinus multi-échelle + invariants causaux), sans aucun dictionnaire figé."""
    if isinstance(skills, (str, Path)):
        from agi_core.context import discover_skills
        skills = discover_skills(str(skills))
    if not skills:
        return {
            "skills": [],
            "selected_skills": [],
            "skills_context": "",
            "skills_summary": "",
            "extracted_invariants": [],
            "companion_scripts": [],
        }

    parsed_skills = [parse_skill_semantically(s) for s in skills]
    n_docs = len(parsed_skills)

    if query and query.strip():
        q_feats = _extract_semantic_features(query)
        q_norm_txt = _normalize_text(query)
        # Calcul dynamique de l'IDF sur l'ensemble des skills découverts + requête
        df: Counter[str] = Counter()
        for ps in parsed_skills:
            for feat in ps["_feature_counts"]:
                df[feat] += 1

        q_vec: dict[str, float] = {}
        for feat, cnt in q_feats.items():
            idf = math.log(1.0 + (n_docs + 1.0) / (df.get(feat, 0) + 1.0))
            q_vec[feat] = cnt * idf
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scored: list[tuple[float, int, dict[str, Any]]] = []
        for idx, ps in enumerate(parsed_skills):
            s_counts: Counter[str] = ps["_feature_counts"]
            dot = 0.0
            s_norm_sq = 0.0
            for feat, cnt in s_counts.items():
                idf = math.log(1.0 + (n_docs + 1.0) / (df.get(feat, 0) + 1.0))
                w = cnt * idf
                s_norm_sq += w * w
                if feat in q_vec:
                    dot += w * q_vec[feat]
            s_norm = math.sqrt(s_norm_sq) or 1.0
            cosine = dot / (q_norm * s_norm)

            # Bonus structurel si le nom ou une précondition causale résonne directement
            struct_bonus = 0.0
            s_name_norm = _normalize_text(ps.get("name", "")).replace("-", " ").replace("_", " ")
            if s_name_norm and s_name_norm in q_norm_txt:
                struct_bonus += 0.45
            for tr in ps.get("triggers") or []:
                tr_norm = _normalize_text(str(tr))
                if tr_norm and tr_norm in q_norm_txt:
                    struct_bonus += 0.35
            if ps.get("level") == "project":
                struct_bonus += 0.08

            total_score = round(cosine + struct_bonus, 4)
            ps["semantic_score"] = total_score
            scored.append((total_score, idx, ps))

        scored.sort(key=lambda item: (-item[0], item[1]))
        ordered = [item[2] for item in scored]
    else:
        for ps in parsed_skills:
            ps["semantic_score"] = 1.0 if ps.get("level") == "project" else 0.5
        ordered = parsed_skills

    selected = ordered[:max_skills]
    bodies: list[str] = []
    all_invariants: list[str] = []
    all_scripts: list[str] = []
    remaining = max_chars

    for ps in selected:
        for inv in ps.get("formal_invariants", []):
            if inv not in all_invariants:
                all_invariants.append(inv)
        for sp in ps.get("companion_scripts", []):
            if sp not in all_scripts:
                all_scripts.append(sp)

        header = (
            f"--- Skill {ps['name']} ({ps.get('level', 'project')} | score={ps.get('semantic_score', 0.0):.2f}) ---\n"
        )
        meta_lines = []
        if ps.get("formal_invariants"):
            meta_lines.append("Invariants formels : " + " ; ".join(ps["formal_invariants"][:3]))
        if ps.get("companion_scripts"):
            meta_lines.append("Scripts exécutables : " + ", ".join(ps["companion_scripts"][:3]))
        meta_prefix = ("\n".join(meta_lines) + "\n") if meta_lines else ""
        budget = min(8000, max(0, remaining - len(header) - len(meta_prefix)))
        if budget <= 0:
            break
        body_slice = str(ps.get("content") or "")[:budget]
        block = f"{header}{meta_prefix}{body_slice}"
        bodies.append(block)
        remaining -= len(block)
        if remaining <= 0:
            break

    # Nettoyage du champ interne `_feature_counts` avant sérialisation
    clean_ordered = [
        {k: v for k, v in ps.items() if k not in {"content", "_feature_counts"}}
        for ps in ordered
    ]

    return {
        "skills": clean_ordered,
        "selected_skills": clean_ordered[:max_skills],
        "skills_context": "\n\n".join(bodies),
        "skills_summary": "\n".join(
            f"- {ps['name']} (score={ps.get('semantic_score', 0.0):.2f}): {ps.get('description', '')}"
            for ps in selected
        ),
        "extracted_invariants": all_invariants[:16],
        "companion_scripts": all_scripts[:16],
    }


def distill_skill_from_trajectory(
    workspace: str | Path = ".",
    *,
    name: str = "",
    skill_name: str = "",
    description: str = "",
    goal: str = "",
    causal_preconditions: list[str] | None = None,
    procedural_steps: list[str] | None = None,
    formal_invariants: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    verified_criteria: list[Any] | None = None,
    triggers: list[str] | None = None,
    companion_script_name: str | None = None,
    companion_script_code: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Distille de manière autonome une résolution vérifiée en une compétence structurée
    `.aurora/skills/<name>/SKILL.md` accompagnée optionnellement d'un script compagnon
    exécutable `.aurora/skills/<name>/scripts/<script>.py` validé par AST."""
    eff_name = (name or skill_name or "").strip()
    if not eff_name and goal:
        words = re.findall(r"[a-zA-Z0-9]{3,}", goal.lower())[:4]
        eff_name = "-".join(words) if words else "distilled-skill"
    eff_name = re.sub(r"[^A-Za-z0-9_-]", "-", eff_name).strip("-_")[:80]
    if not isinstance(eff_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", eff_name):
        raise ValueError("Invalid skill name")
    name = eff_name

    if not description:
        description = (goal or f"Compétence distillée : {name}").strip()[:300]
    if not causal_preconditions:
        causal_preconditions = [f"Objectif cible : {description}"]
    if not procedural_steps and evidence:
        procedural_steps = [
            f"Exécuter `{ev.get('tool', 'step')}` (preuve `{ev.get('id', idx)}`)"
            for idx, ev in enumerate(evidence[-8:], 1)
            if isinstance(ev, dict) and ev.get("ok")
        ]
    if not formal_invariants and verified_criteria:
        formal_invariants = [str(c) for c in verified_criteria[:8]]
    if companion_script_code and companion_script_code.strip() and not companion_script_name:
        companion_script_name = f"{name.replace('-', '_')}_helper.py"

    ws_root = Path(workspace).expanduser().resolve()
    skill_dir = (ws_root / ".aurora" / "skills" / name).resolve()
    if not skill_dir.is_relative_to(ws_root):
        raise ValueError("Skill directory escapes workspace")

    target_md = skill_dir / "SKILL.md"
    if target_md.exists() and not overwrite:
        raise ValueError(f"Skill '{name}' already exists; use overwrite=True to evolve it")

    auto_triggers = list(
        dict.fromkeys(
            (triggers or [])
            + [name, name.replace("-", " "), name.replace("_", " ")]
        )
    )[:10]
    triggers_yaml = "\n".join(f"  - {json.dumps(t, ensure_ascii=False)}" for t in auto_triggers)
    pre_md = "\n".join(f"- {p}" for p in (causal_preconditions or [description]))
    steps_md = "\n".join(f"{i}. {s}" for i, s in enumerate(procedural_steps or ["Inspecter l'état réel et exécuter la transformation."], 1))
    inv_md = "\n".join(f"- {inv}" for inv in (formal_invariants or ["Vérifier le résultat final avec `verify`."]))

    script_rel_note = ""
    script_saved_path: str | None = None
    if companion_script_name and companion_script_code and companion_script_code.strip():
        ast.parse(companion_script_code)
        clean_sc_name = re.sub(r"[^A-Za-z0-9_.-]", "_", companion_script_name)
        if not clean_sc_name.endswith(".py"):
            clean_sc_name += ".py"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        sc_path = (scripts_dir / clean_sc_name).resolve()
        if not sc_path.is_relative_to(skill_dir):
            raise ValueError("Companion script escapes skill directory")
        sc_path.write_text(companion_script_code, encoding="utf-8")
        try:
            sc_path.chmod(0o755)
        except OSError:
            pass
        script_saved_path = str(sc_path)
        script_rel_note = f"\n## 4. Script Compagnon Exécutable\n- Script vérifié AST : `{sc_path.relative_to(ws_root).as_posix()}`\n"

    content = (
        "---\n"
        f"name: {json.dumps(name, ensure_ascii=False)}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        "triggers:\n"
        f"{triggers_yaml}\n"
        "---\n\n"
        f"# Compétence Sémantique : `{name}`\n\n"
        f"## 1. Préconditions Causales & Contexte d'Activation\n"
        f"{pre_md}\n\n"
        f"## 2. Opérateurs Procéduraux\n"
        f"{steps_md}\n\n"
        f"## 3. Invariants Formels & Vérification\n"
        f"{inv_md}\n"
        f"{script_rel_note}"
    )

    if len(content.encode("utf-8")) > 65536:
        raise ValueError("Skill exceeds 64 KiB")

    skill_dir.mkdir(parents=True, exist_ok=True)
    target_md.write_text(content, encoding="utf-8")

    return {
        "ok": True,
        "name": name,
        "path": str(target_md),
        "companion_script": script_saved_path,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }
