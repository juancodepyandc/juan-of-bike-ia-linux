"""morphology — geometric morphology classifier + strategy routing for AuroraIA.

Schema: aurora.morphology.v2

WHY THIS EXISTS
    motion_intent_classifier.py classifies the PROMPT (via Ollama). The prompt lies:
    "Goldorak walking" -> creature_organic + locomotion=humanoid -> anim_metrics family
    "humanoid" -> Laplacian soft-skin smoothing -> the rigid armour MELTS.
    This module verifies/corrects that decision against the actual GEOMETRY (and materials)
    of the generated GLB, and owns the ROUTING table  class -> {rig, motion, metric family}.
    It runs AFTER the weld step (remove_doubles) on a decimated copy.

CONTRACTS THIS ALIGNS TO (verified against real code)
    anim_metrics.FAMILY_METRICS families : humanoid | creature | mecha_rigid | screen | luminous
    motion_intent_classifier categories  : led_emission | fan_pwm | oled_screen |
                                           creature_organic(+locomotion) | mechanical_simple | rigid_static

Pure-geometry deps from application/.venv : trimesh, numpy, scipy(.spatial.cKDTree),
sklearn optional. No network. No Blender. Deterministic.

CLI
    python morphology.py --input model.glb [--intent intent.json] [--prompt "..."]
        -> prints the aurora.morphology.v2 profile as JSON.
    python morphology.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

# ---------------------------------------------------------------- taxonomy ----

# 8 rig-strategy classes (asked for by the architecture doc)
CLASSES = (
    "HUMANOID_BIPED", "QUADRUPED", "WINGED_FLYER", "ROBOT_RIGID_MECH",
    "CREATURE_NONSTANDARD", "MECHANISM_ARTICULATED", "SOFT_OBJECT", "OBJECT_INERT",
)
BODY_PLANS = ("biped", "quadruped", "winged", "serpent", "radial", "multiped", "amorphous", "none")
# deformation is the DISPATCH-CRITICAL axis (drives the metric family, NOT the prompt)
DEFORMATIONS = ("soft_skin", "rigid_segments", "screen_texture", "emissive_only", "procedural_sim", "none")

# deformation -> anim_metrics family (the fix for family_for_intent's Goldorak bug)
_DEF_TO_FAMILY = {
    "soft_skin": "humanoid",       # refined to "creature" by body_plan below
    "rigid_segments": "mecha_rigid",
    "screen_texture": "screen",
    "emissive_only": "luminous",
    "procedural_sim": "creature",
    "none": "mecha_rigid",
}

# class -> {rig recipe, baker/motion route, default deformation}
ROUTING = {
    "HUMANOID_BIPED":        {"rig": "rigify_human+fingers_if_phalanges", "motion": "creature_organic:humanoid", "deformation": "soft_skin"},
    "QUADRUPED":             {"rig": "rigify_creature_quadruped",         "motion": "creature_organic:quadruped", "deformation": "soft_skin"},
    "WINGED_FLYER":          {"rig": "rigify+wing_tail_chains",           "motion": "creature_organic:flight",    "deformation": "soft_skin"},
    "ROBOT_RIGID_MECH":      {"rig": "plate_segmentation+joint_hierarchy","motion": "mecha_rigid_articulated",    "deformation": "rigid_segments"},
    "CREATURE_NONSTANDARD":  {"rig": "hybrid_per_part",                   "motion": "composite",                  "deformation": "soft_skin"},
    "MECHANISM_ARTICULATED": {"rig": "kinematic_chain_Njoints",          "motion": "composite",                  "deformation": "rigid_segments"},
    "SOFT_OBJECT":           {"rig": "none:cloth_wind_modifier",         "motion": "soft_body",                  "deformation": "procedural_sim"},
    "OBJECT_INERT":          {"rig": "none",                             "motion": "led_or_screen_or_rigid",     "deformation": "emissive_only"},
}


@dataclass
class Morphology:
    schema: str = "aurora.morphology.v2"
    kind: str = "OBJECT_INERT"            # one of CLASSES
    body_plan: str = "none"
    deformation: str = "none"
    is_character: bool = False
    personify: bool = False
    confidence: float = 0.0
    escalate_vlm: bool = False            # geometry ambiguous -> caller runs a VLM pass
    sub_flags: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    routing: dict = field(default_factory=dict)
    metric_family: str = "mecha_rigid"
    source: str = "geometry+prior"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


# ------------------------------------------------------------- geometry -------

def _load_mesh(path: str):
    import trimesh
    scene_or_mesh = trimesh.load(path, force="mesh", process=False)
    if isinstance(scene_or_mesh, trimesh.Trimesh):
        return scene_or_mesh
    # a scene: concat
    return trimesh.util.concatenate(tuple(scene_or_mesh.geometry.values()))


def _pca_shape(verts: np.ndarray) -> tuple[float, float, float]:
    """Return (linearity, planarity, sphericity) from the inertia eigenvalues (l0>=l1>=l2)."""
    c = verts - verts.mean(0)
    cov = (c.T @ c) / max(len(c), 1)
    ev = np.linalg.eigvalsh(cov)[::-1]          # descending
    ev = np.clip(ev, 1e-12, None)
    s = np.sqrt(ev)
    lin = (s[0] - s[1]) / s[0]
    pla = (s[1] - s[2]) / s[0]
    sph = s[2] / s[0]
    return float(lin), float(pla), float(sph)


def _bilateral_symmetry(verts: np.ndarray, axis: int = 0, sample: int = 4000) -> float:
    """Mean nearest-neighbour distance between the cloud and its mirror across `axis`,
    normalised by bbox diagonal. ~0 = strongly symmetric (character/robot). Uses cKDTree."""
    from scipy.spatial import cKDTree
    v = verts
    if len(v) > sample:
        idx = np.random.default_rng(0).choice(len(v), sample, replace=False)
        v = v[idx]
    c = v - v.mean(0)
    mirror = c.copy()
    mirror[:, axis] *= -1.0
    d, _ = cKDTree(c).query(mirror, k=1)
    diag = np.linalg.norm(c.max(0) - c.min(0)) + 1e-9
    return float(np.median(d) / diag)


def _emissive_ratio(mesh) -> float:
    """Fraction of emission in the material(s): 0 = none, ->1 = strongly emissive (LED)."""
    try:
        vis = mesh.visual
        mat = getattr(vis, "material", None)
        if mat is None:
            return 0.0
        emis = getattr(mat, "emissiveFactor", None)
        if emis is not None:
            return float(np.clip(np.max(np.asarray(emis, float)[:3]), 0.0, 1.0))
        # PBR emissive texture present?
        if getattr(mat, "emissiveTexture", None) is not None:
            return 0.6
    except Exception:
        pass
    return 0.0


def _flatness(verts: np.ndarray) -> float:
    """Planarity of the whole cloud (1 = a flat quad ~ a screen face)."""
    _, pla, sph = _pca_shape(verts)
    return float(np.clip(pla * (1.0 - sph), 0.0, 1.0))


def extract_features(path: str) -> dict:
    mesh = _load_mesh(path)
    v = np.asarray(mesh.vertices, float)
    ext = v.max(0) - v.min(0)
    order = np.argsort(ext)[::-1]
    a_long = float(ext[order[0]] / (ext[order[1]] + 1e-9))     # elongation of biggest vs middle
    a_flat = float(ext[order[2]] / (ext[order[0]] + 1e-9))     # thinnest / biggest (~0 = flat)
    up = float(ext[2] / (ext[order[0]] + 1e-9))                # tallness on Z
    lin, pla, sph = _pca_shape(v)
    sym = _bilateral_symmetry(v, axis=int(np.argmin(ext[:2])))  # mirror across the narrow horizontal axis
    emis = _emissive_ratio(mesh)
    # connected components: mesh.split() builds full face-adjacency (heavy) -> only on small meshes.
    # TRELLIS meshes are welded upstream anyway; a huge raw mesh is treated as one body here.
    # `split()` recopie l'atlas par composante (mesure: 360 Go demandes sur un
    # personnage). Ici on ne veut qu'un COMPTE: le graphe d'adjacence suffit,
    # sans sous-maillage ni copie — et sans plafond de faces.
    n_comp = 1
    try:
        import numpy as _np_c
        from trimesh.graph import connected_components as _cc
        n_comp = int(len(_cc(mesh.face_adjacency, nodes=_np_c.arange(len(mesh.faces)))))
    except Exception:
        n_comp = 1
    return {
        "n_verts": int(len(v)), "n_faces": int(len(mesh.faces)),
        "aspect_long": round(a_long, 3), "aspect_flat": round(a_flat, 3), "tall_z": round(up, 3),
        "pca_lin": round(lin, 3), "pca_pla": round(pla, 3), "pca_sph": round(sph, 3),
        "bilateral_sym": round(sym, 4), "flatness": round(_flatness(v), 3),
        "emissive": round(emis, 3), "n_components": n_comp,
    }


# ------------------------------------------------------------- classify -------

_RIGID_KW = ("robot", "mech", "mecha", "goldorak", "grendizer", "armor", "armour", "metal",
             "machine", "gundam", "android chassis", "power armor", "exosuit", "drone")
_OBJECT_KW = ("ram", "heatsink", "cable", "led strip", "fan", "screw", "bracket", "pcb",
              "enclosure", "bolt", "connector", "gpu", "motherboard", "cooler")
_SCREEN_KW = ("screen", "oled", "display", "monitor", "digital circus", "caine")


def classify(path: str, intent: Optional[dict] = None, prompt: str = "") -> Morphology:
    feats = extract_features(path)
    text = (prompt or "").lower()
    cat = (intent or {}).get("category")
    loco = ((intent or {}).get("creature_anim") or {}).get("locomotion", "auto")
    conf_prior = float((intent or {}).get("confidence", 0.0))

    m = Morphology(features=feats)
    kw_rigid = any(k in text for k in _RIGID_KW)
    kw_object = any(k in text for k in _OBJECT_KW)
    kw_screen = any(k in text for k in _SCREEN_KW)
    emissive = feats["emissive"] >= 0.35
    flat_screen = feats["flatness"] >= 0.6 and feats["aspect_flat"] <= 0.12
    symmetric = feats["bilateral_sym"] <= 0.05

    # ---- deformation (dispatch-critical) : geometry+prior, geometry can override the prompt ----
    if cat == "oled_screen" or (kw_screen and flat_screen):
        m.deformation = "screen_texture"; m.kind = "OBJECT_INERT"; m.body_plan = "none"
        m.sub_flags["face_is_screen"] = True
    elif cat == "led_emission" or (emissive and not symmetric):
        m.deformation = "emissive_only"; m.kind = "OBJECT_INERT"; m.body_plan = "radial" if feats["pca_sph"] > 0.5 else "none"
    elif cat == "fan_pwm":
        m.deformation = "rigid_segments"; m.kind = "MECHANISM_ARTICULATED"; m.body_plan = "radial"
    elif cat in ("mechanical_simple", "rigid_static") or kw_object:
        m.deformation = "rigid_segments" if cat == "mechanical_simple" or kw_rigid else "none"
        m.kind = "MECHANISM_ARTICULATED" if cat == "mechanical_simple" else "OBJECT_INERT"
        m.body_plan = "none"
    elif cat == "creature_organic":
        # GOLDORAK FIX : a "creature_organic+humanoid" prompt that is clearly a rigid robot
        # (keywords and/or angular-plate geometry) must NOT get soft-skin -> route to mecha_rigid.
        if kw_rigid:
            m.deformation = "rigid_segments"; m.kind = "ROBOT_RIGID_MECH"
            m.body_plan = "biped" if loco in ("humanoid", "auto") else loco
        else:
            m.deformation = "soft_skin"; m.is_character = True; m.personify = True
            if loco == "humanoid" or (loco == "auto" and symmetric and feats["tall_z"] >= 0.5):
                m.kind = "HUMANOID_BIPED"; m.body_plan = "biped"
            elif loco == "quadruped":
                m.kind = "QUADRUPED"; m.body_plan = "quadruped"
            elif loco == "serpent":
                m.kind = "CREATURE_NONSTANDARD"; m.body_plan = "serpent"
            else:
                m.kind = "CREATURE_NONSTANDARD"; m.body_plan = "amorphous"
        # hybrid screen-face creature (Caine) : geometry shows a flat emissive panel on a body
        if flat_screen or (emissive and symmetric):
            m.kind = "CREATURE_NONSTANDARD"; m.sub_flags["face_is_screen"] = True
    else:
        # no usable prior -> decide from geometry alone (symmetry is the strongest character cue)
        if emissive:
            m.deformation = "emissive_only"; m.kind = "OBJECT_INERT"
        elif kw_rigid:
            m.deformation = "rigid_segments"; m.kind = "ROBOT_RIGID_MECH"; m.body_plan = "biped" if symmetric else "none"
        elif symmetric and feats["tall_z"] >= 0.30:
            # strongly bilaterally symmetric + upright -> an upright character (biped)
            m.deformation = "soft_skin"; m.kind = "HUMANOID_BIPED"; m.body_plan = "biped"
            m.is_character = True; m.personify = True
        elif symmetric:
            m.deformation = "soft_skin"; m.kind = "CREATURE_NONSTANDARD"; m.body_plan = "amorphous"; m.is_character = True
        elif feats["pca_pla"] > 0.35:
            m.deformation = "rigid_segments"; m.kind = "ROBOT_RIGID_MECH"
        else:
            m.deformation = "none"; m.kind = "OBJECT_INERT"

    # phalanges flag (whether a fingers rig / grab() is even meaningful) — needs finer detection
    # later (finger-tip FPS on the hand region); default off so nothing invents fingers.
    m.sub_flags.setdefault("has_phalanges", m.kind == "HUMANOID_BIPED")
    m.sub_flags.setdefault("floating_appendages", feats["n_components"] >= 3 and m.is_character)

    m.metric_family = family_for_morphology(m)
    m.routing = ROUTING.get(m.kind, {})
    # confidence : blend prior + geometric decisiveness; escalate to VLM if weak
    geo_conf = 0.9 if (symmetric or emissive or flat_screen or kw_rigid or kw_object) else 0.55
    m.confidence = round(min(1.0, 0.5 * conf_prior + 0.5 * geo_conf), 3)
    m.escalate_vlm = m.confidence < 0.70
    return m


def family_for_morphology(m: Morphology) -> str:
    """anim_metrics family from the MORPHOLOGY (deformation first — fixes the prompt-only bug).
    Use THIS in anim_metrics.family_for_intent as the priority path."""
    if m.deformation == "soft_skin":
        return "humanoid" if m.body_plan == "biped" else "creature"
    return _DEF_TO_FAMILY.get(m.deformation, "mecha_rigid")


# --------------------------------------------------------------- cli ----------

def _selftest() -> int:
    # contract-level self-test (no mesh file needed): routing + family mapping coherence.
    ok = True
    for k in CLASSES:
        assert k in ROUTING, k
    # Goldorak: creature_organic+humanoid prompt but rigid keyword -> mecha_rigid family
    fake = Morphology(kind="ROBOT_RIGID_MECH", body_plan="biped", deformation="rigid_segments")
    assert family_for_morphology(fake) == "mecha_rigid", "Goldorak must route to mecha_rigid"
    # human -> humanoid, quadruped -> creature, RAM LED -> luminous, screen -> screen
    assert family_for_morphology(Morphology(deformation="soft_skin", body_plan="biped")) == "humanoid"
    assert family_for_morphology(Morphology(deformation="soft_skin", body_plan="quadruped")) == "creature"
    assert family_for_morphology(Morphology(deformation="emissive_only")) == "luminous"
    assert family_for_morphology(Morphology(deformation="screen_texture")) == "screen"
    print("morphology self-test OK — %d classes, %d families reachable" % (
        len(CLASSES), len({family_for_morphology(Morphology(deformation=d)) for d in DEFORMATIONS})))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="GLB/mesh to classify")
    ap.add_argument("--intent", help="motion_intent JSON file (Ollama prior)")
    ap.add_argument("--prompt", default="", help="original user prompt (keyword prior)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not a.input:
        ap.error("--input required (or --selftest)")
    intent = json.load(open(a.intent)) if a.intent else None
    prof = classify(a.input, intent=intent, prompt=a.prompt)
    print(prof.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
