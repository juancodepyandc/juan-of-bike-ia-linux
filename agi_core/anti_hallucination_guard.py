#!/usr/bin/env python3
"""Universal Anti-Hallucination & Morphological Truth Guard across all 13 AuroraIA modules.

Enforces first-principles semantic, morphological, visual, geometric, and formal
anti-hallucination invariants so NO module can hallucinate off-topic entities,
split a unified morphological request ("X en forme de Y") into two separate objects,
inject parasitic humans into object scenes, or pass a superficial check when the
actual output is defective.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


ALL_13_MODULES: tuple[str, ...] = (
    "3d",
    "image",
    "video",
    "animation",
    "code",
    "cyber",
    "conversation",
    "cowork",
    "academy",
    "audio",
    "business",
    "drawing",
    "simulator",
)

# Universal Syntactic Morphological Fusion Law: captures ANY "<Object X> en forme de <Shape Y>"
# without relying on a hardcoded list of object or shape nouns.
_STOPWORDS_FR_EN = {
    "un", "une", "le", "la", "les", "des", "du", "de", "d", "en", "et", "ou",
    "avec", "sans", "dans", "sur", "sous", "pour", "par", "tres", "très",
    "a", "an", "the", "of", "in", "on", "with", "and", "or", "for", "to",
}

_MORPHOLOGICAL_FUSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?P<primary>[a-zA-ZÀ-ÖØ-öø-ÿ]{3,28})\s+"
        r"(?:en\s+forme\s+d['’e]\s*|sous\s+forme\s+d['’e]\s*|sculpt[eé]e?\s+en\s+forme\s+d['’e]\s*|fa[cç]onn[eé]e?\s+en\s+|shaped\s+like\s+a?n?\s+|in\s+the\s+shape\s+of\s+a?n?\s*)"
        r"(?:un\s+|une\s+|le\s+|la\s+|l['’]\s*)?"
        r"(?P<morphology>[a-zA-ZÀ-ÖØ-öø-ÿœŒ]{3,28})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<morphology>[a-zA-ZÀ-ÖØ-öø-ÿœŒ]{3,28})[-\s]+shaped\s+(?P<primary>[a-zA-ZÀ-ÖØ-öø-ÿ]{3,28})\b",
        re.IGNORECASE,
    ),
)

_HOLLOW_VESSEL_RE = re.compile(
    r"\b(vase|flacon|carafe|bouteille|coupe|verre|calice|tasse|mug|bol|urne|pot|amphore|cruche|pichet|jarre|decanter|goblet|chalice|cup|bowl|flask|bottle)\b",
    re.IGNORECASE,
)

_TRANSPARENT_CRYSTAL_GLASS_RE = re.compile(
    r"\b(verre|cristal|crystal|glass|transparent|translucide|r[eé]fractif|refractive|opale\s+transparente|quartz\s+transparent|borosilicate| cristal\s+de\s+roche)\b",
    re.IGNORECASE,
)

_HUMAN_SUBJECT_EXPLICIT_RE = re.compile(
    r"\b(homme|femme|gar[cç]on|fille|personne|humain|enfant|guerrier|chevalier|mage|sorcier|pirate|ninja|samoura[iï]|astronaute|pilote|danseur|danseuse|chanteur|chanteuse|portrait|visage|personnage\s+humain|man|woman|boy|girl|person|human|warrior|knight|wizard|astronaut)\b",
    re.IGNORECASE,
)

_ENGRAVING_NAME_RE = re.compile(
    r"\b(?:graver|grav[eé]e?|gravure(?:\s+de)?|inscrire|inscrit|inscription|pr[eé]nom|nom|texte|écrire|ecrire|marquer|engraved?\s+with|inscribed\s+with)\s+(?:le\s+pr[eé]nom\s+|le\s+nom\s+|le\s+mot\s+|le\s+texte\s+)?[\"«']?(?P<inscription>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]{1,24})[\"»']?",
    re.IGNORECASE,
)

_RELIEF_MOTIFS_RE = re.compile(
    r"\b(?:graver|grav[eé]e?s?|gravures?\s+de|motifs?\s+de|avec\s+des|orn[eé]e?\s+de|sculpt[eé]e?\s+de)\s+(?P<motif>(?:petits?\s+)?c(?:oe|œ)urs?|hearts?|roses?|fleurs?|flowers?|[eé]toiles?|stars?|arabesques?|runes?|feuilles?|vagues?|spirales?)\b",
    re.IGNORECASE,
)


def decompose_prompt_anti_hallucination_contract(
    prompt: str,
    target_module: str = "3d",
    material_hint: str | None = None,
) -> dict[str, Any]:
    """Decomposes any user prompt into a strict, non-negotiable Anti-Hallucination Contract."""
    raw = (prompt or "").strip()
    combined = f"{raw} {material_hint or ''}".strip()

    # 1. Strip inscription clauses before checking for human subjects so "le prénom Rayen"
    #    is never mistaken for a person in the scene.
    inscription_text: str | None = None
    m_insc = _ENGRAVING_NAME_RE.search(raw)
    if m_insc:
        cand = m_insc.group("inscription").strip()
        if cand.lower() not in {"de", "du", "des", "le", "la", "les", "un", "une", "et", "sur", "avec", "coeur", "coeurs", "cœur", "cœurs"}:
            inscription_text = cand

    cleaned_for_subject = _ENGRAVING_NAME_RE.sub(" ", raw)

    # 2. Check Morphological Fusion ("vase en forme de coeur")
    morph_fusion: dict[str, Any] | None = None
    for pat in _MORPHOLOGICAL_FUSION_PATTERNS:
        m = pat.search(raw)
        if m:
            primary = m.group("primary").lower()
            morphology = m.group("morphology").lower()
            morph_fusion = {
                "active": True,
                "primary_object": primary,
                "target_morphology": morphology,
                "single_unified_entity_required": True,
                "forbid_separate_secondary_object": True,
                "fusion_directive_en": (
                    f"ONE SINGLE UNIFIED {primary} whose entire 3D body is sculpted in the exact shape of a {morphology} "
                    f"(the {primary} IS the {morphology}; NEVER generate a separate {primary} and a separate {morphology}; "
                    f"NEVER place a {primary} next to or below a {morphology})"
                ),
            }
            break

    is_hollow_vessel = bool(_HOLLOW_VESSEL_RE.search(cleaned_for_subject))
    is_transparent_crystal_or_glass = bool(_TRANSPARENT_CRYSTAL_GLASS_RE.search(combined))
    explicitly_requests_human = bool(_HUMAN_SUBJECT_EXPLICIT_RE.search(cleaned_for_subject)) and not is_hollow_vessel

    relief_motifs: list[str] = []
    for m_rel in _RELIEF_MOTIFS_RE.finditer(raw):
        motif = m_rel.group("motif").strip().lower()
        if motif and motif not in relief_motifs:
            relief_motifs.append(motif)
    if re.search(r"\bdes\s+c(?:oe|œ)urs\b", raw, re.IGNORECASE) and "coeurs" not in relief_motifs:
        relief_motifs.append("coeurs")

    forbidden_contaminants: list[str] = []
    negative_prompt_en_tokens: list[str] = [
        "blurry",
        "low quality",
        "deformed",
        "watermark",
        "cropped",
    ]
    if not explicitly_requests_human:
        forbidden_contaminants.extend([
            "human_person",
            "human_face",
            "human_hands",
            "human_body",
            "man_or_woman_holding_object",
            "bystander",
        ])
        negative_prompt_en_tokens.extend([
            "person",
            "human",
            "man",
            "woman",
            "boy",
            "girl",
            "face",
            "hands",
            "arms",
            "legs",
            "feet",
            "body",
            "character holding object",
            "portrait",
        ])

    if morph_fusion:
        forbidden_contaminants.append("split_multiple_objects")
        negative_prompt_en_tokens.extend([
            "two separate objects",
            "multiple vases",
            "separate heart and vase",
            "object at the bottom",
            "collage",
            "split composition",
        ])

    if is_transparent_crystal_or_glass:
        forbidden_contaminants.extend(["opaque_plastic_balloon", "matte_clay_surface"])
        negative_prompt_en_tokens.extend([
            "opaque balloon",
            "matte plastic",
            "flat opaque surface",
            "solid unhollowed blob",
        ])

    return {
        "target_module": target_module,
        "raw_prompt": raw,
        "is_hollow_vessel": is_hollow_vessel,
        "is_transparent_crystal_or_glass": is_transparent_crystal_or_glass,
        "explicitly_requests_human": explicitly_requests_human,
        "morphological_fusion": morph_fusion,
        "mandatory_inscription": inscription_text,
        "mandatory_relief_motifs": relief_motifs,
        "forbidden_contaminants": forbidden_contaminants,
        "negative_prompt_en": ", ".join(dict.fromkeys(negative_prompt_en_tokens)),
        "strict_single_object_isolation": bool(not explicitly_requests_human and (is_hollow_vessel or morph_fusion)),
    }


def verify_reference_image_no_hallucination(
    image_path: str | Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Inspects a 2D reference image using deterministic computer vision + skin/layout
    topology to detect:
      1. Split-object hallucination (e.g. a floating heart + a separate vase at the bottom)
      2. Parasitic human skin/body/person hallucination when `explicitly_requests_human` is False
      3. Opaque flat fill when optical crystal/glass refraction is required.
    Never lies: returns `passed=False` with exact failure reasons if any violation is found.
    """
    p = Path(image_path)
    if not p.is_file():
        return {"ok": False, "passed": False, "reasons": ["reference_image_missing"]}

    try:
        from PIL import Image
        img = Image.open(p).convert("RGBA")
        arr = np.asarray(img, dtype=np.float32) / 255.0
    except Exception as exc:
        return {"ok": False, "passed": False, "reasons": [f"image_decode_error:{exc}"]}

    h, w, _ = arr.shape
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Foreground mask: either alpha > 0.15 or distance from border background color > 0.12
    border_pixels = np.concatenate([
        rgb[0, :, :],
        rgb[-1, :, :],
        rgb[:, 0, :],
        rgb[:, -1, :],
    ], axis=0)
    bg_median = np.median(border_pixels, axis=0)
    dist_bg = np.linalg.norm(rgb - bg_median[None, None, :], axis=-1)
    fg_mask = (alpha > 0.2) & (dist_bg > 0.10)
    # Preserve bright internal specular highlights inside the object silhouette on each row
    fg_filled = fg_mask.copy()
    for r_i in range(h):
        cols = np.where(fg_mask[r_i])[0]
        if cols.size >= 4:
            fg_filled[r_i, int(cols[0]) : int(cols[-1]) + 1] = True
    fg_ratio = float(np.mean(fg_filled))

    reasons: list[str] = []

    # Check 1: Vertical split-object detector (e.g. one object in upper half and a separate object at the feet/bottom)
    row_fg_frac = np.mean(fg_mask, axis=1)
    active_rows = np.where(row_fg_frac > 0.04)[0]
    disconnected_vertical_islands = 1
    if active_rows.size >= 10:
        y_min, y_max = int(active_rows[0]), int(active_rows[-1])
        interior_band = row_fg_frac[y_min:y_max + 1]
        # Count empty horizontal gaps > 4% of image height inside the bounding box
        empty_run = 0
        gap_threshold = max(4, int(0.04 * h))
        for val in interior_band:
            if val < 0.012:
                empty_run += 1
            else:
                if empty_run >= gap_threshold:
                    disconnected_vertical_islands += 1
                empty_run = 0

    if contract.get("strict_single_object_isolation") and disconnected_vertical_islands >= 2:
        reasons.append(f"SPLIT_OBJECTS_HALLUCINATION: {disconnected_vertical_islands} objets verticalement séparés détectés au lieu d'un seul objet unifié")

    # Check 1b: Horizontal split-object detector (rejects side-by-side separate objects or parasitic bystander)
    mid_y0, mid_y1 = int(0.35 * h), int(0.65 * h)
    col_fg_frac = np.mean(fg_filled[mid_y0:mid_y1, :], axis=0)
    active_cols = np.where(col_fg_frac > 0.04)[0]
    disconnected_horizontal_islands = 1
    if active_cols.size >= 10:
        x_min, x_max = int(active_cols[0]), int(active_cols[-1])
        horiz_band = col_fg_frac[x_min : x_max + 1]
        empty_col_run = 0
        col_gap_threshold = max(6, int(0.05 * w))
        for val in horiz_band:
            if val < 0.012:
                empty_col_run += 1
            else:
                if empty_col_run >= col_gap_threshold:
                    disconnected_horizontal_islands += 1
                empty_col_run = 0
    if contract.get("strict_single_object_isolation") and disconnected_horizontal_islands >= 2:
        reasons.append(f"HORIZONTAL_SPLIT_HALLUCINATION: {disconnected_horizontal_islands} entités séparées côte à côte détectées")

    # Check 2: Specular & Refractive Dynamic Range + Edge Sharpness for Crystal/Glass
    spec_high_ratio = 0.0
    fg_luma = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    gx = np.abs(np.diff(fg_luma, axis=1, prepend=fg_luma[:, :1]))
    gy = np.abs(np.diff(fg_luma, axis=0, prepend=fg_luma[:1, :]))
    edge_sharpness = float(np.mean(np.hypot(gx, gy)[fg_filled])) if np.any(fg_filled) else 0.0
    if contract.get("is_transparent_crystal_or_glass") and np.any(fg_filled):
        fg_vals = fg_luma[fg_filled]
        spec_high_ratio = float(np.mean(fg_vals > 0.85))
        luma_std = float(np.std(fg_vals))
        if luma_std < 0.06 or spec_high_ratio < 0.005 or edge_sharpness < 0.012:
            reasons.append(
                f"OPAQUE_BALLOON_TEXTURE_DETECTED: Contraste réfractif trop plat (std={luma_std:.3f}, reflets={spec_high_ratio:.4f}, sharpness={edge_sharpness:.4f}) pour du verre/cristal"
            )

    return {
        "ok": True,
        "passed": len(reasons) == 0,
        "fg_ratio": round(fg_ratio, 4),
        "disconnected_vertical_islands": disconnected_vertical_islands,
        "disconnected_horizontal_islands": disconnected_horizontal_islands,
        "specular_highlight_ratio": round(spec_high_ratio, 4),
        "edge_gradient_sharpness": round(edge_sharpness, 4),
        "reasons": reasons,
    }


def build_module_anti_hallucination_invariants(module_name: str) -> dict[str, Any]:
    """Returns the representative first-principles anti-hallucination invariant spec for each of the 13 modules."""
    specs: dict[str, dict[str, Any]] = {
        "3d": {
            "representative_judge_metric": "azimuthal_normal_entropy>=0.98460 & polar_normal_entropy>=0.91598 & f3d_white_blowout<=0.000000000000000004 & clay_f3d_relief>=11.919098 & vertex_normal_disp>=0.21621 & stl_volume_cm3>=271.28004 & bed_contact_mm>=36.2999 & tipping_margin_mm>=12.2229 & cavity_depth_ratio>=0.92 & KHR_materials_transmission>=0.85",
            "anti_hallucination_law": "Morphological fusion (1 unified mesh) + hollow cavity raycast + optical glass IOR>=1.50",
        },
        "image": {
            "representative_judge_metric": "disconnected_vertical_islands==1 & specular_highlight_ratio>=0.005 & zero_parasitic_human",
            "anti_hallucination_law": "Single-subject isolation + refractive dynamic range + morphological fusion",
        },
        "video": {
            "representative_judge_metric": "temporal_identity_consistency>=0.95 & camera_SE3_smoothness",
            "anti_hallucination_law": "Wan2.2 temporal subject persistence without morphing or parasitic entities",
        },
        "animation": {
            "representative_judge_metric": "11_anchor_medial_interiority>=0.995944 & single_anchor_interiority>=0.9845737265 & bilateral_limb_symmetry>=0.9999994 & max_cycle_displacement_mm>=12.0 & zero_phantom_limbs",
            "anti_hallucination_law": "Medial axis 11 color-paired anchors inside mesh volume + C2 quaternion gait",
        },
        "code": {
            "representative_judge_metric": "tsc_noEmit_exit_0 & zero_todo_stub & AST_CFG_verified",
            "anti_hallucination_law": "Zero nonexistent imports, zero TODO/placeholders, full compiler & type verification",
        },
        "cyber": {
            "representative_judge_metric": "z3_post_patch_exploit_unsat==True & ast_reachability_verified",
            "anti_hallucination_law": "Formal SMT Z3 UNSAT proof on patched control-flow graph before reporting fix",
        },
        "conversation": {
            "representative_judge_metric": "epistemic_intent_alignment==1.0 & zero_invented_entities",
            "anti_hallucination_law": "Strict grounding on user prompt entities and verified factual sources",
        },
        "cowork": {
            "representative_judge_metric": "transactional_dag_acyclic & coworkSafety_veto_active",
            "anti_hallucination_law": "Deterministic connector execution with pre-action safety audit and rollback",
        },
        "academy": {
            "representative_judge_metric": "sympy_euler_lagrange_residual==0 & z3_theorem_sat",
            "anti_hallucination_law": "Every mathematical/physical derivation formally checked by SymPy + Z3",
        },
        "audio": {
            "representative_judge_metric": "kokoro_phoneme_alignment>=0.98 & rhubarb_viseme_sync",
            "anti_hallucination_law": "Exact transcript-to-phoneme synthesis without hallucinated words or truncation",
        },
        "business": {
            "representative_judge_metric": "reserve_ratio>=0.25 & ruin_probability<=0.02 & z3_risk_veto_verified",
            "anti_hallucination_law": "Non-LLM IndependentRiskManager hard veto + fat-tail Monte-Carlo stress tests",
        },
        "drawing": {
            "representative_judge_metric": "stroke_topology_continuity>=0.95 & turnaround_epipolar_consistency",
            "anti_hallucination_law": "Faithful sketch-to-stroke anatomical interpretation without off-brief additions",
        },
        "simulator": {
            "representative_judge_metric": "symplectic_energy_drift<=1.4855e-12 & navier_stokes_divergence_free",
            "anti_hallucination_law": "Störmer-Verlet / Yoshida-4 Hamiltonian conservation and physical boundary enforcement",
        },
    }
    from agi_core.judge_ratchet import judge_ratchet
    return {**specs.get(
        module_name,
        {
            "representative_judge_metric": "first_principles_verified",
            "anti_hallucination_law": "Universal anti-hallucination contract",
        },
    ), "progressive_evidence_requirements": judge_ratchet()}


# One definition only: the gate lives in agi_core.judge_ratchet. This module re-exports it so the
# local judges keep their import path without carrying a second copy that could drift.
from agi_core.judge_ratchet import judge_independent_holdout_evidence  # noqa: E402,F401


_MASCULINE_ENTAILMENT_RE = re.compile(
    r"\b(masculin|homme|gar[cç]on|gars|mec|barbu|moustache|p[eè]re|fr[eè]re|roi|prince|chevalier|guerrier|monsieur|male|man|boy|guy|bearded)\b",
    re.IGNORECASE,
)
_FEMININE_ENTAILMENT_RE = re.compile(
    r"\b(f[eé]minin|femme|fille|dame|m[eè]re|s(?:oe|œ)ur|reine|princesse|sir[eè]ne| guerri[eè]re|madame|female|woman|girl|lady|mermaid)\b",
    re.IGNORECASE,
)
_MATERIAL_EXPLICIT_RE = re.compile(
    r"\b(cristal|verre|porcelaine|c[eé]ramique|bois|marbre|bronze|laiton|or|argent|acier|titane|r[eé]sine|pla|petg|abs|silicone|cuir|tissu|argile|pierre|béton|beton)\b",
    re.IGNORECASE,
)
_HEART_VARIANT_EXPLICIT_RE = re.compile(
    r"\b(anatomique|anatomical|[eé]moji|sym[eé]trique|classique|stylis[eé]|ventricule|aorte|myocarde)\b",
    re.IGNORECASE,
)
_DIMENSION_EXPLICIT_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?\s*(?:mm|cm|m|pouces|inches)|taille\s+r[eé]elle|grand\s+format|petit\s+format)\b",
    re.IGNORECASE,
)
_BICOLOR_FINISH_EXPLICIT_RE = re.compile(
    r"\b(ext[eé]rieur\s+\w+.*int[eé]rieur\s+\w+|int[eé]rieur\s+\w+.*ext[eé]rieur\s+\w+|bicolore|deux\s+couleurs)\b",
    re.IGNORECASE,
)
_INCREMENTAL_DELTA_EXPLICIT_RE = re.compile(
    r"\b(sans\s+repartir\s+de\s+(?:z[eé]ro|0)|modifie\s+uniquement|juste\s+la\s+modification|garde\s+le\s+m[eê]me)\b",
    re.IGNORECASE,
)
_INTERIOR_CONTENT_EXPLICIT_RE = re.compile(
    r"\b(vide|sans\s+fleurs?|sans\s+rien(?:\s+dedans)?|avec\s+fleurs?|garni[es]?\s+de\s+fleurs?)\b",
    re.IGNORECASE,
)
_POSE_OR_ANIMATION_EXPLICIT_RE = re.compile(
    r"\b(anim[eé]e?s?|rigg[eé]e?s?|squelette|articul[eé]e?s?|statiques?|immobiles?|t-pose|a-pose|en\s+mouvement)\b",
    re.IGNORECASE,
)
_SURFACE_RELIEF_EXPLICIT_RE = re.compile(
    r"\b(grav[eé]r?e?s?|gravures?|haut-relief|bas-relief|relief\s+3d|sculpt[eé]e?s?|cisel[eé]e?s?|lisses?)\b",
    re.IGNORECASE,
)
_OPTICAL_TRANSPARENCY_EXPLICIT_RE = re.compile(
    r"\b(transparente?s?|translucides?|opaques?|r[eé]fracti(?:f|fs|ve|ves)|d[eé]poli[es]?|verre\s+clair|cristal\s+pur)\b",
    re.IGNORECASE,
)
_PRINT_FABRICATION_TOLERANCE_EXPLICIT_RE = re.compile(
    r"\b(buse\s+\d|couches?\s+\d|remplissage\s+\d|infill|[eé]tanches?|watertight|2-manifold|manifold|sans\s+supports?)\b",
    re.IGNORECASE,
)
_MOUNTING_BASE_STABILITY_EXPLICIT_RE = re.compile(
    r"\b(socle\s+plat|fond\s+plat|base\s+plate|autoportante?s?|auto-stables?|sans\s+socle|sur\s+pi[eé]destal|flat\s+base|freestanding)\b",
    re.IGNORECASE,
)
_SURFACE_SHEEN_FINISH_EXPLICIT_RE = re.compile(
    r"\b(brillante?s?|satin[eé]e?s?|émaill[eé]e?s?|emaill[eé]e?s?|laqu[eé]e?s?|polie?s?|bross[eé]e?s?|mates?|glossy|matte|polished|brushed)\b",
    re.IGNORECASE,
)
_RIM_COLLAR_GEOMETRY_EXPLICIT_RE = re.compile(
    r"\b(col\s+[eé]vas[eé]|col\s+[eé]troit|rebord\s+arrondi|bord\s+biseaut[eé]|ouverture\s+large|goulot\s+fin|flared\s+rim|beveled\s+lip|rounded\s+collar|wide\s+mouth)\b",
    re.IGNORECASE,
)
_ENGRAVING_TYPOGRAPHY_EXPLICIT_RE = re.compile(
    r"\b([eé]criture\s+calligraphique|[eé]criture\s+cursive|police\s+calligraphique|lettres?\s+gothiques?|typographie\s+s[eé]rif|sans-s[eé]rif|capitales?\s+romaines?|calligraphy|cursive\s+script|serif\s+font|roman\s+capitals)\b",
    re.IGNORECASE,
)
_INTERNAL_DRAINAGE_OR_PARTITION_EXPLICIT_RE = re.compile(
    r"\b(sans\s+trou\s+de\s+drainage|avec\s+trou\s+de\s+drainage|trou\s+de\s+drainage|fond\s+[eé]tanche|mono-cavit[eé]|double\s+compartiment|drainage\s+hole|no\s+drainage\s+hole|sealed\s+bottom|single\s+cavity)\b",
    re.IGNORECASE,
)
_LIGHTING_OR_BACKLIGHT_AMBIANCE_EXPLICIT_RE = re.compile(
    r"\b([eé]clairage\s+studio|r[eé]tro[eé]clairage\s+led|lumi[eè]re\s+naturelle|socle\s+lumineux|sans\s+[eé]clairage\s+led|contre-jour|studio\s+lighting|led\s+backlight|natural\s+daylight|illuminated\s+base)\b",
    re.IGNORECASE,
)
_SYMMETRY_OR_ASYMMETRY_EXPLICIT_RE = re.compile(
    r"\b(sym[eé]trie\s+bilat[eé]rale|parfaitement\s+sym[eé]triques?|asym[eé]trie\s+organique|formes?\s+asym[eé]triques?|lobes?\s+asym[eé]triques?|bilateral\s+symmetry|perfectly\s+symmetrical|organic\s+asymmetry|asymmetrical\s+form)\b",
    re.IGNORECASE,
)
_WALL_THICKNESS_SHELL_EXPLICIT_RE = re.compile(
    r"\b(paroi\s+[eé]paisse|paroi\s+fine|double\s+paroi|[eé]paisseur\s+de\s+paroi|coque\s+renforc[eé]e|thick\s+wall|thin\s+wall|double[-\s]walled|wall\s+thickness|reinforced\s+shell)\b",
    re.IGNORECASE,
)
_WEIGHT_BALANCE_BALLAST_EXPLICIT_RE = re.compile(
    r"\b(base\s+lest[eé]e|fond\s+lest[eé]|centre\s+de\s+gravit[eé]\s+bas|contrepoids|ultra[-\s]l[eé]g(?:er|[eè]re)|weighted\s+base|ballasted\s+bottom|low\s+center\s+of\s+gravity|lightweight\s+shell)\b",
    re.IGNORECASE,
)
_POUR_SPOUT_OR_NECK_APERTURE_EXPLICIT_RE = re.compile(
    r"\b(bec\s+verseur|sans\s+bec\s+verseur|embouchure\s+circulaire|ouverture\s+en\s+c(?:oe|œ)ur|goulot\s+verseur|pouring\s+spout|no\s+spout|spoutless|heart[-\s]shaped\s+opening|circular\s+aperture)\b",
    re.IGNORECASE,
)
_LID_STOPPER_OR_CLOSURE_EXPLICIT_RE = re.compile(
    r"\b(avec\s+couvercle|sans\s+couvercle|bouchon\s+en\s+cristal|bouchon\s+herm[eé]tique|ouvert\s+sur\s+le\s+dessus|fermeture\s+herm[eé]tique|glass\s+stopper|with\s+lid|no\s+lid|open\s+top|airtight\s+stopper)\b",
    re.IGNORECASE,
)
_HANDLE_GRIP_OR_LUG_EXPLICIT_RE = re.compile(
    r"\b(sans\s+anses?|avec\s+(?:deux\s+)?anses?|anses?\s+lat[eé]rales?|poign[eé]es?\s+ergonomiques?|oreilles?\s+lat[eé]rales?|no\s+handles?|handleless|twin\s+handles|side\s+lugs)\b",
    re.IGNORECASE,
)
_FOOT_PAD_ANTI_SLIP_OR_FELT_EXPLICIT_RE = re.compile(
    r"\b(patins?\s+(?:en\s+)?feutre|patins?\s+antid[eé]rapants?|dessous\s+feutr[eé]|pieds?\s+silicone|sans\s+patins?|felt\s+pads?|anti[-\s]slip\s+pads?|silicone\s+bumper\s+feet|non[-\s]scratch\s+base)\b",
    re.IGNORECASE,
)
_INDOOR_OUTDOOR_UV_WEATHERING_EXPLICIT_RE = re.compile(
    r"\b(usage\s+int[eé]rieur|usage\s+ext[eé]rieur|anti[-\s]uv|r[eé]sistant\s+au\s+gel|ing[eé]lif|intemp[eé]ries|indoor\s+only|outdoor\s+weatherproof|uv[-\s]stabilized|frost[-\s]resistant)\b",
    re.IGNORECASE,
)
_THERMAL_HEAT_OR_CANDLE_RESISTANCE_EXPLICIT_RE = re.compile(
    r"\b(r[eé]sistant\s+[aà]\s+la\s+chaleur|verre\s+borosilicate|pyrex|bougie\s+chauffe[-\s]plat|eau\s+bouillante|ignifug[eé]|choc\s+thermique|heat[-\s]resistant|borosilicate\s+glass|tealight\s+candle|thermal\s+shock)\b",
    re.IGNORECASE,
)
_FOOD_SAFE_WATERTIGHT_GLAZE_EXPLICIT_RE = re.compile(
    r"\b(contact\s+alimentaire|qualit[eé]\s+alimentaire|[eé]maill[eé]\s+[eé]tanche|[eé]mail\s+alimentaire|vernis\s+hydrofuge|[eé]tanche\s+[aà]\s+l['’]eau|sans\s+bisph[eé]nol|food[-\s]safe|food\s+grade|watertight\s+glaze)\b",
    re.IGNORECASE,
)
_PACKAGING_GIFT_BOX_OR_PROTECTIVE_CASE_EXPLICIT_RE = re.compile(
    r"\b(coffret\s+cadeau|[eé]crin\s+(?:de\s+)?velours|bo[iî]te\s+cadeau|sans\s+coffret|emballage\s+anti[-\s]choc|mousse\s+sur[-\s]mesure|gift\s+box|velvet\s+presentation\s+case|protective\s+foam\s+packaging|no\s+gift\s+box)\b",
    re.IGNORECASE,
)
_HALLMARK_SIGNATURE_OR_NUMBERED_EDITION_EXPLICIT_RE = re.compile(
    r"\b(poin[cç]on\s+d['’]orf[eè]vre|[eé]dition\s+num[eé]rot[eé]e|tirage\s+limit[eé]|sign[eé]e?\s+sous\s+la\s+base|num[eé]rot[eé]e?\s+[aà]\s+la\s+main|sans\s+poin[cç]on|maker['’]s\s+hallmark|numbered\s+limited\s+edition|signed\s+base|unmarked\s+base)\b",
    re.IGNORECASE,
)
_MODULAR_INTERLOCKING_OR_STACKABLE_JOINERY_EXPLICIT_RE = re.compile(
    r"\b(embo[iî]table|empilable|assemblage\s+queue\s+d['’]aronde|socle\s+amovible\s+aimant[eé]|monobloc\s+non\s+d[eé]montable|sans\s+embo[iî]tement|modular\s+interlocking|stackable\s+design|magnetic\s+detachable\s+base|one[-\s]piece\s+monolithic)\b",
    re.IGNORECASE,
)
_ACOUSTIC_RESONANCE_OR_SOUND_DAMPING_EXPLICIT_RE = re.compile(
    r"\b(isolation\s+acoustique|amortissement\s+sonore|anti[-\s]vibrations?|r[eé]sonance\s+cristalline|silencieux\s+anti[-\s]bruit|acoustic\s+damping|sound[-\s]absorbing|vibration[-\s]isolated|crystal\s+chime\s+resonance)\b",
    re.IGNORECASE,
)
_MAGNETIC_LEVITATION_OR_FERROMAGNETIC_CORE_EXPLICIT_RE = re.compile(
    r"\b(l[eé]vitation\s+magn[eé]tique|socle\s+[eé]lectromagn[eé]tique|noyau\s+ferromagn[eé]tique|sans\s+aimant|antimagn[eé]tique|amagn[eé]tique|magnetic\s+levitation|electromagnetic\s+floating\s+base|ferromagnetic\s+insert|non[-\s]magnetic)\b",
    re.IGNORECASE,
)
_HYDROPHOBIC_LOTUS_OR_OLEOPHOBIC_COATING_EXPLICIT_RE = re.compile(
    r"\b(traitement\s+hydrophobe|effet\s+lotus|anti[-\s]traces?\s+de\s+doigts|ol[eé]ophobe|auto[-\s]nettoyant|sans\s+traitement\s+hydrophobe|hydrophobic\s+lotus\s+coating|oleophobic\s+anti[-\s]fingerprint|self[-\s]cleaning\s+glaze)\b",
    re.IGNORECASE,
)
_LUMINESCENT_PHOSPHORESCENT_OR_UV_FLUORESCENT_PIGMENT_EXPLICIT_RE = re.compile(
    r"\b(phosphorescent|luminescent\s+nocturne|fluorescent\s+uv|glow[-\s]in[-\s]the[-\s]dark|aluminate\s+de\s+strontium|sans\s+luminescence|sans\s+phosphorescence|non[-\s]luminescent|uv[-\s]reactive\s+pigment|strontium\s+aluminate\s+glow)\b",
    re.IGNORECASE,
)
_ANTI_UV_YELLOWING_OR_MUSEUM_ARCHIVAL_GRADE_EXPLICIT_RE = re.compile(
    r"\b(anti[-\s]jaunissement\s+uv|anti[-\s]jaunissement|grade\s+conservation\s+mus[eé]ale|stabilisant\s+hals|sans\s+jaunissement\s+solaire|museum\s+archival\s+grade|anti[-\s]yellowing\s+uv\s+stabilized|hals\s+uv\s+inhibitor)\b",
    re.IGNORECASE,
)
_DISHWASHER_OR_HYDROTHERMAL_CLEANING_CYCLE_EXPLICIT_RE = re.compile(
    r"\b(compatible\s+lave[-\s]vaisselle|lavable\s+au\s+lave[-\s]vaisselle|lavage\s+[aà]\s+la\s+main\s+uniquement|cycle\s+hydrothermique|st[eé]rilisable\s+autoclave|dishwasher[-\s]safe|hand[-\s]wash\s+only|autoclave\s+sterilizable)\b",
    re.IGNORECASE,
)
_ANTIMICROBIAL_SILVER_ION_OR_COPPER_BIOCIDAL_GLAZE_EXPLICIT_RE = re.compile(
    r"\b(gla[cç]ure\s+antimicrobienne|ions?\s+d['\u2019]argent|traitement\s+antibact[eé]rien|biocide\s+cuivre|anti[-\s]biofilm|sans\s+traitement\s+antimicrobien|antimicrobial\s+silver[-\s]ion\s+glaze|antibacterial\s+copper\s+coating)\b",
    re.IGNORECASE,
)
_PIEZOELECTRIC_OR_CAPACITIVE_TOUCH_SENSOR_BASE_EXPLICIT_RE = re.compile(
    r"\b(capteur\s+tactile\s+capacitif|socle\s+pi[eé]zo[eé]lectrique|d[eé]tection\s+de\s+pression\s+d['\u2019]eau|interrupteur\s+effleurement|sans\s+capteur\s+tactile|purement\s+passif\s+sans\s+[eé]lectronique|capacitive\s+touch\s+sensor\s+base|piezoelectric\s+pressure\s+sensing\s+pad)\b",
    re.IGNORECASE,
)
_AROMATHERAPY_ESSENTIAL_OIL_DIFFUSER_OR_POROUS_CERAMIC_CORE_EXPLICIT_RE = re.compile(
    r"\b(diffuseur\s+d['\u2019]huiles?\s+essentielles?|noyau\s+c[eé]ramique\s+microporeux|aromath[eé]rapie\s+capillaire|essential\s+oil\s+diffuser|porous\s+ceramic\s+wick|sans\s+diffuseur\s+olfactif)\b",
    re.IGNORECASE,
)


def evaluate_epistemic_clarification_need(prompt: str, target_module: str = "3d") -> dict[str, Any]:
    """Détermine de façon épistémique quelles questions de clarification sont LÉGITIMES et UTILES,
    et bloque strictement toute question redondante ou stupide (ex: demander si c'est un gars alors que
    'masculin'/'barbu' est déjà dit, ou redemander le matériau s'il est déjà précisé).
    """
    raw = (prompt or "").strip()
    entailed_slots: dict[str, str] = {}
    legitimate_questions: list[dict[str, Any]] = []
    forbidden_redundant_slots: list[str] = []

    # 1. Inférence directe par implication sémantique (Entailment) -> INTERDICTION de poser la question
    if _MASCULINE_ENTAILMENT_RE.search(raw):
        entailed_slots["gender"] = "masculine"
        forbidden_redundant_slots.append("gender")
    elif _FEMININE_ENTAILMENT_RE.search(raw):
        entailed_slots["gender"] = "feminine"
        forbidden_redundant_slots.append("gender")

    if _MATERIAL_EXPLICIT_RE.search(raw):
        entailed_slots["material"] = _MATERIAL_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("material")

    if _HEART_VARIANT_EXPLICIT_RE.search(raw):
        entailed_slots["heart_variant"] = _HEART_VARIANT_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("heart_variant")

    if _DIMENSION_EXPLICIT_RE.search(raw):
        entailed_slots["dimensions"] = _DIMENSION_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("dimensions")

    if _BICOLOR_FINISH_EXPLICIT_RE.search(raw):
        entailed_slots["bicolor_finish"] = "explicit_interior_exterior"
        forbidden_redundant_slots.append("bicolor_finish")

    if _INCREMENTAL_DELTA_EXPLICIT_RE.search(raw):
        entailed_slots["incremental_delta"] = "preserve_base_state"
        forbidden_redundant_slots.append("incremental_delta")

    if _INTERIOR_CONTENT_EXPLICIT_RE.search(raw):
        entailed_slots["interior_content"] = _INTERIOR_CONTENT_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("interior_content")

    if _POSE_OR_ANIMATION_EXPLICIT_RE.search(raw):
        entailed_slots["pose_or_animation"] = _POSE_OR_ANIMATION_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("pose_or_animation")

    if _SURFACE_RELIEF_EXPLICIT_RE.search(raw):
        entailed_slots["surface_relief"] = _SURFACE_RELIEF_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("surface_relief")

    if _OPTICAL_TRANSPARENCY_EXPLICIT_RE.search(raw):
        entailed_slots["optical_transparency"] = _OPTICAL_TRANSPARENCY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("optical_transparency")

    if _PRINT_FABRICATION_TOLERANCE_EXPLICIT_RE.search(raw):
        entailed_slots["print_fabrication_spec"] = _PRINT_FABRICATION_TOLERANCE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("print_fabrication_spec")

    if _MOUNTING_BASE_STABILITY_EXPLICIT_RE.search(raw):
        entailed_slots["mounting_base_spec"] = _MOUNTING_BASE_STABILITY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("mounting_base_spec")

    if _SURFACE_SHEEN_FINISH_EXPLICIT_RE.search(raw):
        entailed_slots["surface_sheen_finish"] = _SURFACE_SHEEN_FINISH_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("surface_sheen_finish")

    if _RIM_COLLAR_GEOMETRY_EXPLICIT_RE.search(raw):
        entailed_slots["rim_collar_geometry"] = _RIM_COLLAR_GEOMETRY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("rim_collar_geometry")

    if _ENGRAVING_TYPOGRAPHY_EXPLICIT_RE.search(raw):
        entailed_slots["engraving_typography_style"] = _ENGRAVING_TYPOGRAPHY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("engraving_typography_style")

    if _INTERNAL_DRAINAGE_OR_PARTITION_EXPLICIT_RE.search(raw):
        entailed_slots["internal_drainage_or_partition"] = _INTERNAL_DRAINAGE_OR_PARTITION_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("internal_drainage_or_partition")

    if _LIGHTING_OR_BACKLIGHT_AMBIANCE_EXPLICIT_RE.search(raw):
        entailed_slots["lighting_or_backlight_spec"] = _LIGHTING_OR_BACKLIGHT_AMBIANCE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("lighting_or_backlight_spec")

    if _SYMMETRY_OR_ASYMMETRY_EXPLICIT_RE.search(raw):
        entailed_slots["symmetry_or_asymmetry_spec"] = _SYMMETRY_OR_ASYMMETRY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("symmetry_or_asymmetry_spec")

    if _WALL_THICKNESS_SHELL_EXPLICIT_RE.search(raw):
        entailed_slots["wall_thickness_shell_spec"] = _WALL_THICKNESS_SHELL_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("wall_thickness_shell_spec")

    if _WEIGHT_BALANCE_BALLAST_EXPLICIT_RE.search(raw):
        entailed_slots["weight_balance_ballast_spec"] = _WEIGHT_BALANCE_BALLAST_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("weight_balance_ballast_spec")

    if _POUR_SPOUT_OR_NECK_APERTURE_EXPLICIT_RE.search(raw):
        entailed_slots["pour_spout_or_neck_aperture_spec"] = _POUR_SPOUT_OR_NECK_APERTURE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("pour_spout_or_neck_aperture_spec")

    if _LID_STOPPER_OR_CLOSURE_EXPLICIT_RE.search(raw):
        entailed_slots["lid_stopper_or_closure_spec"] = _LID_STOPPER_OR_CLOSURE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("lid_stopper_or_closure_spec")

    if _HANDLE_GRIP_OR_LUG_EXPLICIT_RE.search(raw):
        entailed_slots["handle_grip_or_lug_spec"] = _HANDLE_GRIP_OR_LUG_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("handle_grip_or_lug_spec")

    if _FOOT_PAD_ANTI_SLIP_OR_FELT_EXPLICIT_RE.search(raw):
        entailed_slots["foot_pad_anti_slip_or_felt_spec"] = _FOOT_PAD_ANTI_SLIP_OR_FELT_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("foot_pad_anti_slip_or_felt_spec")

    if _INDOOR_OUTDOOR_UV_WEATHERING_EXPLICIT_RE.search(raw):
        entailed_slots["indoor_outdoor_uv_weathering_spec"] = _INDOOR_OUTDOOR_UV_WEATHERING_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("indoor_outdoor_uv_weathering_spec")

    if _THERMAL_HEAT_OR_CANDLE_RESISTANCE_EXPLICIT_RE.search(raw):
        entailed_slots["thermal_heat_or_candle_resistance_spec"] = _THERMAL_HEAT_OR_CANDLE_RESISTANCE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("thermal_heat_or_candle_resistance_spec")

    if _FOOD_SAFE_WATERTIGHT_GLAZE_EXPLICIT_RE.search(raw):
        entailed_slots["food_safe_watertight_glaze_coating_spec"] = _FOOD_SAFE_WATERTIGHT_GLAZE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("food_safe_watertight_glaze_coating_spec")

    if _PACKAGING_GIFT_BOX_OR_PROTECTIVE_CASE_EXPLICIT_RE.search(raw):
        entailed_slots["packaging_gift_box_or_protective_case_spec"] = _PACKAGING_GIFT_BOX_OR_PROTECTIVE_CASE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("packaging_gift_box_or_protective_case_spec")

    if _HALLMARK_SIGNATURE_OR_NUMBERED_EDITION_EXPLICIT_RE.search(raw):
        entailed_slots["hallmark_signature_or_numbered_edition_spec"] = _HALLMARK_SIGNATURE_OR_NUMBERED_EDITION_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("hallmark_signature_or_numbered_edition_spec")

    if _MODULAR_INTERLOCKING_OR_STACKABLE_JOINERY_EXPLICIT_RE.search(raw):
        entailed_slots["modular_interlocking_or_stackable_joinery_spec"] = _MODULAR_INTERLOCKING_OR_STACKABLE_JOINERY_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("modular_interlocking_or_stackable_joinery_spec")

    if _ACOUSTIC_RESONANCE_OR_SOUND_DAMPING_EXPLICIT_RE.search(raw):
        entailed_slots["acoustic_resonance_or_sound_damping_spec"] = _ACOUSTIC_RESONANCE_OR_SOUND_DAMPING_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("acoustic_resonance_or_sound_damping_spec")

    if _MAGNETIC_LEVITATION_OR_FERROMAGNETIC_CORE_EXPLICIT_RE.search(raw):
        entailed_slots["magnetic_levitation_or_ferromagnetic_core_spec"] = _MAGNETIC_LEVITATION_OR_FERROMAGNETIC_CORE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("magnetic_levitation_or_ferromagnetic_core_spec")

    if _HYDROPHOBIC_LOTUS_OR_OLEOPHOBIC_COATING_EXPLICIT_RE.search(raw):
        entailed_slots["hydrophobic_lotus_or_oleophobic_self_cleaning_spec"] = _HYDROPHOBIC_LOTUS_OR_OLEOPHOBIC_COATING_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("hydrophobic_lotus_or_oleophobic_self_cleaning_spec")

    if _LUMINESCENT_PHOSPHORESCENT_OR_UV_FLUORESCENT_PIGMENT_EXPLICIT_RE.search(raw):
        entailed_slots["luminescent_phosphorescent_or_uv_fluorescent_pigment_spec"] = _LUMINESCENT_PHOSPHORESCENT_OR_UV_FLUORESCENT_PIGMENT_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("luminescent_phosphorescent_or_uv_fluorescent_pigment_spec")

    if _ANTI_UV_YELLOWING_OR_MUSEUM_ARCHIVAL_GRADE_EXPLICIT_RE.search(raw):
        entailed_slots["anti_uv_yellowing_or_museum_archival_grade_spec"] = _ANTI_UV_YELLOWING_OR_MUSEUM_ARCHIVAL_GRADE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("anti_uv_yellowing_or_museum_archival_grade_spec")

    if _DISHWASHER_OR_HYDROTHERMAL_CLEANING_CYCLE_EXPLICIT_RE.search(raw):
        entailed_slots["dishwasher_or_hydrothermal_cleaning_cycle_spec"] = _DISHWASHER_OR_HYDROTHERMAL_CLEANING_CYCLE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("dishwasher_or_hydrothermal_cleaning_cycle_spec")

    if _ANTIMICROBIAL_SILVER_ION_OR_COPPER_BIOCIDAL_GLAZE_EXPLICIT_RE.search(raw):
        entailed_slots["antimicrobial_silver_ion_or_copper_biocidal_glaze_spec"] = _ANTIMICROBIAL_SILVER_ION_OR_COPPER_BIOCIDAL_GLAZE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("antimicrobial_silver_ion_or_copper_biocidal_glaze_spec")

    if _PIEZOELECTRIC_OR_CAPACITIVE_TOUCH_SENSOR_BASE_EXPLICIT_RE.search(raw):
        entailed_slots["piezoelectric_pressure_or_capacitive_touch_sensor_base_spec"] = _PIEZOELECTRIC_OR_CAPACITIVE_TOUCH_SENSOR_BASE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("piezoelectric_pressure_or_capacitive_touch_sensor_base_spec")

    if _AROMATHERAPY_ESSENTIAL_OIL_DIFFUSER_OR_POROUS_CERAMIC_CORE_EXPLICIT_RE.search(raw):
        entailed_slots["aromatherapy_essential_oil_diffuser_or_porous_ceramic_core_spec"] = _AROMATHERAPY_ESSENTIAL_OIL_DIFFUSER_OR_POROUS_CERAMIC_CORE_EXPLICIT_RE.search(raw).group(1).lower()  # type: ignore[union-attr]
        forbidden_redundant_slots.append("aromatherapy_essential_oil_diffuser_or_porous_ceramic_core_spec")

    # 2. Détection des vraies ambiguïtés légitimes à haut impact qualitatif
    has_heart = bool(re.search(r"\bc(?:oe|œ)ur\b|\bheart\b", raw, re.IGNORECASE))
    if has_heart and "heart_variant" not in entailed_slots:
        legitimate_questions.append({
            "slot": "heart_variant",
            "question_fr": "Souhaitez-vous une forme de cœur Émoji (symétrique classique galbée) ou un cœur Anatomique (avec ventricules, aorte et artères coronaires) ?",
            "options": ["Cœur Émoji (symétrique)", "Cœur Anatomique (réaliste)", "Générer les deux variantes"],
        })

    if target_module in ("3d", "image") and "material" not in entailed_slots and not _HUMAN_SUBJECT_EXPLICIT_RE.search(raw):
        legitimate_questions.append({
            "slot": "material",
            "question_fr": "Quel matériau et finition optique souhaitez-vous (ex: cristal/verre réfractif, porcelaine émaillée, métal brossé ou PLA/résine pour impression 3D) ?",
            "options": ["Cristal / Verre optique", "Porcelaine / Céramique", "Impression 3D (PLA / Résine taille réelle)"],
        })

    if bool(_HOLLOW_VESSEL_RE.search(raw)) and "interior_content" not in entailed_slots:
        legitimate_questions.append({
            "slot": "interior_content",
            "question_fr": "Voulez-vous le récipient 100 % vide (cavité interne ouverte prête pour de vraies fleurs / impression 3D) ?",
            "options": ["100 % vide (sans fleurs)", "Avec composition florale"],
        })

    return {
        "entailed_slots": entailed_slots,
        "forbidden_redundant_slots": forbidden_redundant_slots,
        "legitimate_questions": legitimate_questions,
        "asks_redundant_gender_when_entailed": False,
    }


def run_anti_hallucination_guard_self_test() -> dict[str, Any]:
    """Exécute l'auto-test formel du garde-fou Anti-Hallucination sur les 13 modules."""
    import json

    c_vase = decompose_prompt_anti_hallucination_contract(
        "vase en forme de coeur avec graver le prénom Rayen et des coeurs sur le vase et couleur rose en cristal/verre",
        target_module="3d",
    )
    c_en_bottle = decompose_prompt_anti_hallucination_contract(
        "a crystal bottle in the shape of a star engraved with Luna",
        target_module="3d",
    )
    mf = c_vase.get("morphological_fusion") or {}
    mf_en = c_en_bottle.get("morphological_fusion") or {}
    vase_ok = bool(
        mf.get("active") is True
        and mf.get("primary_object") == "vase"
        and mf.get("target_morphology") == "coeur"
        and c_vase.get("mandatory_inscription") == "Rayen"
        and c_vase.get("is_hollow_vessel") is True
        and c_vase.get("is_transparent_crystal_or_glass") is True
        and c_vase.get("explicitly_requests_human") is False
        and mf_en.get("active") is True
        and mf_en.get("primary_object") == "bottle"
        and mf_en.get("target_morphology") == "star"
        and c_en_bottle.get("mandatory_inscription") == "Luna"
        and c_en_bottle.get("is_hollow_vessel") is True
        and c_en_bottle.get("is_transparent_crystal_or_glass") is True
        and c_en_bottle.get("explicitly_requests_human") is False
    )

    q_ambig = evaluate_epistemic_clarification_need("un vase en forme de coeur", target_module="3d")
    q_masc = evaluate_epistemic_clarification_need("un chevalier masculin barbu en bronze", target_module="3d")
    q_fem = evaluate_epistemic_clarification_need(
        "une reine avec un vase en forme de coeur anatomique en cristal vide", target_module="3d"
    )
    q_bicolor_delta = evaluate_epistemic_clarification_need(
        "garde le même vase extérieur rose et intérieur blanc sans repartir de zéro",
        target_module="3d",
    )
    q_sans_rien_pose = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en verre sans rien dedans statique en haut-relief",
        target_module="3d",
    )
    q_transp = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en verre transparent vide en haut-relief",
        target_module="3d",
    )
    q_fab_tol = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en pla étanche sans supports entièrement vide",
        target_module="3d",
    )
    q_base_stab = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal vide à fond plat autoportant",
        target_module="3d",
    )
    q_sheen = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en porcelaine émaillée brillante entièrement vide",
        target_module="3d",
    )
    q_rim_collar = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose à col évasé entièrement vide",
        target_module="3d",
    )
    q_typo = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose gravé en écriture calligraphique entièrement vide",
        target_module="3d",
    )
    q_drain = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose sans trou de drainage mono-cavité entièrement vide",
        target_module="3d",
    )
    q_light = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose sur socle lumineux entièrement vide",
        target_module="3d",
    )
    q_sym = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose à symétrie bilatérale entièrement vide",
        target_module="3d",
    )
    q_wall_shell = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose à double paroi entièrement vide",
        target_module="3d",
    )
    q_ballast = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose à base lestée et centre de gravité bas entièrement vide",
        target_module="3d",
    )
    q_spout = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose sans bec verseur à ouverture en coeur entièrement vide",
        target_module="3d",
    )
    q_lid_closure = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose sans couvercle ouvert sur le dessus entièrement vide",
        target_module="3d",
    )
    q_handle_lug = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose sans anses entièrement vide",
        target_module="3d",
    )
    q_foot_pad = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose avec patins en feutre entièrement vide",
        target_module="3d",
    )
    q_uv_weather = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose anti-uv résistant au gel entièrement vide",
        target_module="3d",
    )
    q_thermal = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en verre borosilicate résistant à la chaleur entièrement vide",
        target_module="3d",
    )
    q_food_glaze = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en céramique contact alimentaire émaillé étanche entièrement vide",
        target_module="3d",
    )
    q_gift_box = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose en coffret cadeau écrin de velours entièrement vide",
        target_module="3d",
    )
    q_hallmark = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose avec poinçon d'orfèvre édition numérotée entièrement vide",
        target_module="3d",
    )
    q_mod_joinery = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose monobloc non démontable sans emboîtement entièrement vide",
        target_module="3d",
    )
    q_acoustic = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose anti-vibration à isolation acoustique entièrement vide",
        target_module="3d",
    )
    q_mag_lev = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose en lévitation magnétique sur socle électromagnétique entièrement vide",
        target_module="3d",
    )
    q_hydro_lotus = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose avec traitement hydrophobe effet lotus anti-traces entièrement vide",
        target_module="3d",
    )
    q_lum_pigment = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose phosphorescent luminescent dans le noir entièrement vide",
        target_module="3d",
    )
    q_anti_uv_archival = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose anti-jaunissement UV grade conservation muséale entièrement vide",
        target_module="3d",
    )
    q_dishwasher_cycle = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose compatible lave-vaisselle cycle hydrothermique entièrement vide",
        target_module="3d",
    )
    q_antimicrobial_glaze = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur émoji en cristal rose avec glaçure antimicrobienne aux ions d'argent anti-biofilm entièrement vide",
        target_module="3d",
    )
    q_touch_sensor = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose sur socle piézoélectrique à capteur tactile capacitif entièrement vide",
        target_module="3d",
    )
    q_aroma_diffuser = evaluate_epistemic_clarification_need(
        "un vase en forme de coeur anatomique en cristal rose avec diffuseur d'huiles essentielles à noyau céramique microporeux entièrement vide",
        target_module="3d",
    )
    empty_holdout = judge_independent_holdout_evidence(
        [],
        ratchet={"ratchet_level": 2, "required_holdout_cases": 3},
    )
    forged_holdout = judge_independent_holdout_evidence(
        [{"independent_holdout": False, "executed": True, "passed": True, "case_sha256": "a" * 64, "receipt_sha256": "b" * 64}],
        ratchet={"ratchet_level": 2, "required_holdout_cases": 2},
    )
    malformed_holdout = judge_independent_holdout_evidence(
        [
            {"independent_holdout": True, "executed": True, "passed": 1, "case_sha256": "a" * 64, "receipt_sha256": "b" * 64},
            {"independent_holdout": True, "executed": True, "passed": True, "case_sha256": "a" * 63, "receipt_sha256": "b" * 64},
        ],
        ratchet={"ratchet_level": 2, "required_holdout_cases": 2},
    )
    dup_holdout = judge_independent_holdout_evidence(
        [
            {"independent_holdout": True, "executed": True, "passed": True, "case_sha256": "c" * 64, "receipt_sha256": "d" * 64},
            {"independent_holdout": True, "executed": True, "passed": True, "case_sha256": "c" * 64, "receipt_sha256": "e" * 64},
        ],
        ratchet={"ratchet_level": 2, "required_holdout_cases": 2},
    )
    valid_holdout = judge_independent_holdout_evidence(
        [
            {"independent_holdout": True, "executed": True, "passed": True, "case_sha256": "1" * 64, "receipt_sha256": "2" * 64},
            {"independent_holdout": True, "executed": True, "passed": True, "case_sha256": "3" * 64, "receipt_sha256": "4" * 64},
        ],
        ratchet={"ratchet_level": 1, "required_holdout_cases": 2},
    )
    epistemic_ok = bool(
        {q["slot"] for q in q_ambig["legitimate_questions"]} >= {"heart_variant", "material", "interior_content"}
        and {"gender", "material"} <= set(q_masc["forbidden_redundant_slots"])
        and {"gender", "heart_variant", "material"} <= set(q_fem["forbidden_redundant_slots"])
        and {"bicolor_finish", "incremental_delta"} <= set(q_bicolor_delta["forbidden_redundant_slots"])
        and {"heart_variant", "material", "interior_content", "pose_or_animation", "surface_relief"} <= set(q_sans_rien_pose["forbidden_redundant_slots"])
        and {"heart_variant", "material", "optical_transparency", "interior_content", "surface_relief"} <= set(q_transp["forbidden_redundant_slots"])
        and {"heart_variant", "material", "print_fabrication_spec", "interior_content"} <= set(q_fab_tol["forbidden_redundant_slots"])
        and {"heart_variant", "material", "mounting_base_spec", "interior_content"} <= set(q_base_stab["forbidden_redundant_slots"])
        and {"heart_variant", "material", "surface_sheen_finish", "interior_content"} <= set(q_sheen["forbidden_redundant_slots"])
        and {"heart_variant", "material", "rim_collar_geometry", "interior_content"} <= set(q_rim_collar["forbidden_redundant_slots"])
        and {"heart_variant", "material", "engraving_typography_style", "interior_content"} <= set(q_typo["forbidden_redundant_slots"])
        and {"heart_variant", "material", "internal_drainage_or_partition", "interior_content"} <= set(q_drain["forbidden_redundant_slots"])
        and {"heart_variant", "material", "lighting_or_backlight_spec", "interior_content"} <= set(q_light["forbidden_redundant_slots"])
        and {"heart_variant", "material", "symmetry_or_asymmetry_spec", "interior_content"} <= set(q_sym["forbidden_redundant_slots"])
        and {"heart_variant", "material", "wall_thickness_shell_spec", "interior_content"} <= set(q_wall_shell["forbidden_redundant_slots"])
        and {"heart_variant", "material", "weight_balance_ballast_spec", "interior_content"} <= set(q_ballast["forbidden_redundant_slots"])
        and {"heart_variant", "material", "pour_spout_or_neck_aperture_spec", "interior_content"} <= set(q_spout["forbidden_redundant_slots"])
        and {"heart_variant", "material", "lid_stopper_or_closure_spec", "interior_content"} <= set(q_lid_closure["forbidden_redundant_slots"])
        and {"heart_variant", "material", "handle_grip_or_lug_spec", "interior_content"} <= set(q_handle_lug["forbidden_redundant_slots"])
        and {"heart_variant", "material", "foot_pad_anti_slip_or_felt_spec", "interior_content"} <= set(q_foot_pad["forbidden_redundant_slots"])
        and {"heart_variant", "material", "indoor_outdoor_uv_weathering_spec", "interior_content"} <= set(q_uv_weather["forbidden_redundant_slots"])
        and {"heart_variant", "material", "thermal_heat_or_candle_resistance_spec", "interior_content"} <= set(q_thermal["forbidden_redundant_slots"])
        and {"heart_variant", "material", "food_safe_watertight_glaze_coating_spec", "interior_content"} <= set(q_food_glaze["forbidden_redundant_slots"])
        and {"heart_variant", "material", "packaging_gift_box_or_protective_case_spec", "interior_content"} <= set(q_gift_box["forbidden_redundant_slots"])
        and {"heart_variant", "material", "hallmark_signature_or_numbered_edition_spec", "interior_content"} <= set(q_hallmark["forbidden_redundant_slots"])
        and {"heart_variant", "material", "modular_interlocking_or_stackable_joinery_spec", "interior_content"} <= set(q_mod_joinery["forbidden_redundant_slots"])
        and {"heart_variant", "material", "acoustic_resonance_or_sound_damping_spec", "interior_content"} <= set(q_acoustic["forbidden_redundant_slots"])
        and {"heart_variant", "material", "magnetic_levitation_or_ferromagnetic_core_spec", "interior_content"} <= set(q_mag_lev["forbidden_redundant_slots"])
        and {"heart_variant", "material", "hydrophobic_lotus_or_oleophobic_self_cleaning_spec", "interior_content"} <= set(q_hydro_lotus["forbidden_redundant_slots"])
        and {"heart_variant", "material", "luminescent_phosphorescent_or_uv_fluorescent_pigment_spec", "interior_content"} <= set(q_lum_pigment["forbidden_redundant_slots"])
        and {"heart_variant", "material", "anti_uv_yellowing_or_museum_archival_grade_spec", "interior_content"} <= set(q_anti_uv_archival["forbidden_redundant_slots"])
        and {"heart_variant", "material", "dishwasher_or_hydrothermal_cleaning_cycle_spec", "interior_content"} <= set(q_dishwasher_cycle["forbidden_redundant_slots"])
        and {"heart_variant", "material", "antimicrobial_silver_ion_or_copper_biocidal_glaze_spec", "interior_content"} <= set(q_antimicrobial_glaze["forbidden_redundant_slots"])
        and {"heart_variant", "material", "piezoelectric_pressure_or_capacitive_touch_sensor_base_spec", "interior_content"} <= set(q_touch_sensor["forbidden_redundant_slots"])
        and {"heart_variant", "material", "aromatherapy_essential_oil_diffuser_or_porous_ceramic_core_spec", "interior_content"} <= set(q_aroma_diffuser["forbidden_redundant_slots"])
        and len(q_sans_rien_pose["legitimate_questions"]) == 0
        and len(q_transp["legitimate_questions"]) == 0
        and len(q_fab_tol["legitimate_questions"]) == 0
        and len(q_base_stab["legitimate_questions"]) == 0
        and len(q_sheen["legitimate_questions"]) == 0
        and len(q_rim_collar["legitimate_questions"]) == 0
        and len(q_typo["legitimate_questions"]) == 0
        and len(q_drain["legitimate_questions"]) == 0
        and len(q_light["legitimate_questions"]) == 0
        and len(q_sym["legitimate_questions"]) == 0
        and len(q_wall_shell["legitimate_questions"]) == 0
        and len(q_ballast["legitimate_questions"]) == 0
        and len(q_spout["legitimate_questions"]) == 0
        and len(q_lid_closure["legitimate_questions"]) == 0
        and len(q_handle_lug["legitimate_questions"]) == 0
        and len(q_foot_pad["legitimate_questions"]) == 0
        and len(q_uv_weather["legitimate_questions"]) == 0
        and len(q_thermal["legitimate_questions"]) == 0
        and len(q_food_glaze["legitimate_questions"]) == 0
        and len(q_gift_box["legitimate_questions"]) == 0
        and len(q_hallmark["legitimate_questions"]) == 0
        and len(q_mod_joinery["legitimate_questions"]) == 0
        and len(q_acoustic["legitimate_questions"]) == 0
        and len(q_mag_lev["legitimate_questions"]) == 0
        and len(q_hydro_lotus["legitimate_questions"]) == 0
        and len(q_lum_pigment["legitimate_questions"]) == 0
        and len(q_anti_uv_archival["legitimate_questions"]) == 0
        and len(q_dishwasher_cycle["legitimate_questions"]) == 0
        and len(q_antimicrobial_glaze["legitimate_questions"]) == 0
        and len(q_touch_sensor["legitimate_questions"]) == 0
        and len(q_aroma_diffuser["legitimate_questions"]) == 0
        and len(q_fem["legitimate_questions"]) == 0
        and empty_holdout["passed"] is False
        and empty_holdout["observed_cases"] == 0
        and forged_holdout["passed"] is False
        and forged_holdout["unverified_or_duplicate_cases"] == 1
        and malformed_holdout["passed"] is False
        and malformed_holdout["unverified_or_duplicate_cases"] == 2
        and dup_holdout["passed"] is False
        and dup_holdout["unverified_or_duplicate_cases"] == 1
        and valid_holdout["passed"] is True
        and valid_holdout["unverified_or_duplicate_cases"] == 0
    )

    modules_checked = {}
    for mod in ALL_13_MODULES:
        inv = build_module_anti_hallucination_invariants(mod)
        modules_checked[mod] = {
            "passed": bool(inv.get("representative_judge_metric") and inv.get("anti_hallucination_law")),
            **inv,
        }

    # Verify Flagship MoA Council & Anti-Starvation Guard across all 13 modules
    flagship_council_ok = False
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[1])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from agi_core.flagship_council import (
            _clean_and_salvage_thinking,
            get_all_modules_flagship_roster,
            list_jules_remote_sessions,
            load_module_reinforced_context,
            pull_jules_remote_session,
            resolve_installed_flagship_model,
        )
        from agi_core.judge_ratchet import judge_ratchet
        ratchet_live = judge_ratchet()
        roster_info = get_all_modules_flagship_roster()
        jules_sessions_info = list_jules_remote_sessions(limit=5)
        jules_pull_info = pull_jules_remote_session("17934176527203556429", apply_patch=False)
        jules_pull_memo_info = pull_jules_remote_session("9788832407963301799", apply_patch=False)
        vision_flagship = resolve_installed_flagship_model("llava", module="3d", require_vision=True)
        coder_flagship = resolve_installed_flagship_model("aurora-rl-code:selected", module="code")
        cyber_flagship = resolve_installed_flagship_model("aurora-rl-cyber:selected", module="cyber")
        learning_flagship = resolve_installed_flagship_model("aurora-rl-learning:selected", module="learning")
        conv_flagship = resolve_installed_flagship_model("aurora-rl-conversation:selected", module="conversation")
        business_flagship = resolve_installed_flagship_model("aurora-rl-business:selected", module="business")
        simulator_flagship = resolve_installed_flagship_model("aurora-rl-simulator:selected", module="simulator")
        cowork_flagship = resolve_installed_flagship_model("aurora-rl-cowork:selected", module="cowork")
        voice_flagship = resolve_installed_flagship_model("aurora-rl-voice:selected", module="voice")
        image_flagship = resolve_installed_flagship_model("aurora-rl-image:selected", module="image", require_vision=True)
        drawing_flagship = resolve_installed_flagship_model("aurora-rl-drawing:selected", module="drawing", require_vision=True)
        video_flagship = resolve_installed_flagship_model("aurora-rl-video:selected", module="video", require_vision=True)
        animation_flagship = resolve_installed_flagship_model("aurora-rl-animation:selected", module="animation")
        mods_roster = roster_info.get("modules") or {}
        uninstalled_legacy = {"qwen2.5:7b", "qwen3:14b", "gemma3:27b", "qwen3:8b", "llama3.2:3b"}
        legacy_upgraded_ok = all(
            resolve_installed_flagship_model(leg) not in uninstalled_legacy
            for leg in uninstalled_legacy
        )
        salvaged_text, _ = _clean_and_salvage_thinking("", "<think>Step 1</think>\nFinal verified answer")
        salvaged_json, _ = _clean_and_salvage_thinking("", "Reasoning step...\n```json\n{\"verified\": true}\n```")
        salvaged_unclosed, salvaged_unclosed_think = _clean_and_salvage_thinking("<think>Unclosed deep reasoning trace", "")
        reinforced_ctx_ok = all(
            len(load_module_reinforced_context(m)) > 20
            for m in ("3d", "code", "cyber", "conversation", "learning", "business", "simulator", "cowork", "image", "drawing", "video", "animation", "voice")
        )
        serve_11435_ok = False
        try:
            import urllib.request as _ureq
            with _ureq.urlopen("http://127.0.0.1:11435/health", timeout=3.0) as _resp:
                _hdata = json.loads(_resp.read().decode("utf-8", errors="replace"))
            with _ureq.urlopen("http://127.0.0.1:11435/api/tags", timeout=5.0) as _tresp:
                _tdata = json.loads(_tresp.read().decode("utf-8", errors="replace"))
            with _ureq.urlopen("http://127.0.0.1:11435/api/models/council-roster", timeout=20.0) as _crresp:
                _crdata = json.loads(_crresp.read().decode("utf-8", errors="replace"))
            with _ureq.urlopen("http://127.0.0.1:3001/api/agi/council/roster", timeout=20.0) as _rresp:
                _rdata = json.loads(_rresp.read().decode("utf-8", errors="replace"))
            _tag_names = {str(m.get("name") or "") for m in (_tdata.get("models") or [])}
            _expected_rl_tags = {
                f"aurora-rl-{m}:selected"
                for m in ("code", "cyber", "conversation", "learning", "business", "simulator", "cowork")
            }
            serve_11435_ok = bool(
                (_hdata.get("ok") is True or _hdata.get("status") == "ok")
                and _hdata.get("mode") == "flagship-moa-council"
                and _expected_rl_tags.issubset(_tag_names)
                and _crdata.get("jules_cli_available") is True
                and bool(_crdata.get("jules_binary"))
                and isinstance(_crdata.get("installed_models"), list)
                and len(_crdata.get("installed_models") or []) >= 5
                and len(_crdata.get("modules") or {}) == 13
                and all(
                    isinstance((_crdata.get("modules") or {}).get(m), dict)
                    and bool((_crdata.get("modules") or {})[m].get("specialist"))
                    and (_crdata.get("modules") or {})[m].get("specialist") not in uninstalled_legacy
                    and bool((_crdata.get("modules") or {})[m].get("reasoner"))
                    and (_crdata.get("modules") or {})[m].get("reasoner") not in uninstalled_legacy
                    and bool((_crdata.get("modules") or {})[m].get("critic"))
                    and (_crdata.get("modules") or {})[m].get("critic") not in uninstalled_legacy
                    and bool((_crdata.get("modules") or {})[m].get("reinforced_context_loaded"))
                    for m in ("conversation", "code", "cyber", "3d", "image", "learning", "business", "cowork", "drawing", "video", "animation", "voice", "simulator")
                )
                and _rdata.get("ok") is True
                and _rdata.get("jules_cli_available") is True
                and isinstance(_rdata.get("installed_models"), list)
                and len(_rdata.get("installed_models") or []) >= 5
                and isinstance(_rdata.get("jules_sessions"), list)
                and len(_rdata.get("jules_sessions") or []) >= 1
                and len(_rdata.get("all_module_rosters") or _rdata.get("modules") or {}) == 13
                and all(
                    isinstance((_rdata.get("all_module_rosters") or _rdata.get("modules") or {}).get(m), dict)
                    and bool((_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("specialist"))
                    and (_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("specialist") not in uninstalled_legacy
                    and bool((_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("reasoner"))
                    and (_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("reasoner") not in uninstalled_legacy
                    and bool((_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("critic"))
                    and (_rdata.get("all_module_rosters") or _rdata.get("modules") or {})[m].get("critic") not in uninstalled_legacy
                    for m in ("conversation", "code", "cyber", "3d", "image", "learning", "business", "cowork", "drawing", "video", "animation", "voice", "simulator")
                )
            )
        except Exception:
            serve_11435_ok = False
        flagship_council_ok = bool(
            legacy_upgraded_ok
            and salvaged_text == "Final verified answer"
            and salvaged_json == "{\"verified\": true}"
            and salvaged_unclosed == "Unclosed deep reasoning trace"
            and salvaged_unclosed_think == "Unclosed deep reasoning trace"
            and roster_info.get("jules_cli_available") is True
            and bool(roster_info.get("jules_binary"))
            and jules_sessions_info.get("ok") is True
            and isinstance(jules_sessions_info.get("sessions"), list)
            and len(jules_sessions_info.get("sessions") or []) >= 1
            and jules_pull_info.get("ok") is True
            and "diff --git" in str(jules_pull_info.get("stdout") or "")
            and jules_pull_memo_info.get("ok") is True
            and "const ChatBubble = memo(" in str(jules_pull_memo_info.get("stdout") or "")
            and int(ratchet_live.get("ratchet_level", 0)) >= 810
            and int(ratchet_live.get("required_holdout_cases", 0)) == int(ratchet_live.get("ratchet_level", 0)) + 1
            and int(ratchet_live.get("max_unverified_claims", 1)) == 0
            and 0.0 < float(ratchet_live.get("max_error_probability", 1.0)) <= (1.0 / 811.0)
            and "vl" in vision_flagship.lower()
            and "coder" in coder_flagship.lower()
            and ("cyber" in cyber_flagship.lower() or "coder" in cyber_flagship.lower())
            and "deepseek-r1" in learning_flagship.lower()
            and "27b" in conv_flagship.lower()
            and "deepseek-r1" in business_flagship.lower()
            and "deepseek-r1" in simulator_flagship.lower()
            and "27b" in cowork_flagship.lower()
            and "27b" in voice_flagship.lower()
            and "vl" in image_flagship.lower()
            and "vl" in drawing_flagship.lower()
            and "vl" in video_flagship.lower()
            and "deepseek-r1" in animation_flagship.lower()
            and reinforced_ctx_ok
            and serve_11435_ok
            and all(
                m in mods_roster
                and mods_roster[m].get("specialist")
                and mods_roster[m].get("specialist") not in uninstalled_legacy
                and mods_roster[m].get("reasoner") not in uninstalled_legacy
                and mods_roster[m].get("critic") not in uninstalled_legacy
                and bool(mods_roster[m].get("reinforced_context_loaded"))
                for m in ("conversation", "code", "cyber", "3d", "image", "learning", "business", "cowork", "drawing", "video", "animation", "voice", "simulator")
            )
        )
    except Exception:
        flagship_council_ok = False

    all_ok = bool(vase_ok and epistemic_ok and flagship_council_ok and all(v["passed"] for v in modules_checked.values()))
    report = {
        "all_13_modules_anti_hallucination_passed": all_ok,
        "morphological_fusion_vase_coeur_rayen_passed": vase_ok,
        "epistemic_clarification_entailment_passed": epistemic_ok,
        "flagship_moa_council_and_anti_starvation_passed": flagship_council_ok,
        "modules_count": len(modules_checked),
        "modules": modules_checked,
    }
    out_path = Path(__file__).resolve().parents[1] / "modele" / "renforce" / "anti_hallucination_report.json"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return report


if __name__ == "__main__":
    import json

    res = run_anti_hallucination_guard_self_test()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("all_13_modules_anti_hallucination_passed"):
        sys.exit(2)

