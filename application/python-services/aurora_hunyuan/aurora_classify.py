"""Heuristic scene profile classifier for AuroraIA Hunyuan3D pipeline.

Parses a free-form prompt and emits a structured SceneProfile dict describing
what animations, materials, mood, and rendering treatment should be applied.
Designed so the Blender animator stays data-driven: any prompt the classifier
doesn't recognise falls through to a beauty turntable instead of failing.

Usage:
    python aurora_classify.py "a glowing crystal lantern floating in fog"
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

# Each tuple is (animation_type, list-of-regex). First match per type wins.
ANIMATION_PATTERNS: dict[str, list[str]] = {
    "rotate_y": [r"\bspin", r"\brotat", r"\bturn(ing|s|ed)?\b", r"\borbit", r"\bturntable", r"\bcarousel"],
    "emission_pulse": [r"\bglow", r"\bluminous", r"\bneon", r"\bemissive", r"\bincandesc", r"\bbiolumin",
                        r"\bradiat", r"\blantern", r"\blight\b", r"\billuminat"],
    "particles_rain": [r"\brain", r"\bdownpour", r"\bdrizzle", r"\bstorm"],
    "particles_snow": [r"\bsnow", r"\bblizzard", r"\bsnowflake", r"\bwinter"],
    "particles_fire": [r"\bfire", r"\bflame", r"\bblazing", r"\bember", r"\binferno", r"\bburning"],
    "particles_smoke": [r"\bsmoke", r"\bfog\b", r"\bmist\b", r"\bsteam", r"\bvapor"],
    "particles_dust": [r"\bdust", r"\bsand", r"\bdesert", r"\bash\b"],
    "particles_sparks": [r"\bspark", r"\bfirefl", r"\bfaerie", r"\bmagical particle"],
    "hover_float": [r"\blevit", r"\bhover", r"\bfloat(ing)?\b", r"\bsuspend", r"\bweightless", r"\banti.?gravity"],
    "fluid_flow": [r"\bflow", r"\bripple", r"\bwave", r"\bcurrent", r"\bsplash", r"\bliquid"],
    "mechanical_articulate": [r"\bgear", r"\bpiston", r"\bengine", r"\bmachine", r"\bmechanical",
                                r"\bclockwork", r"\brobot", r"\bautomaton"],
    "shake_vibrate": [r"\bshake", r"\bvibrat", r"\btremble", r"\bquake"],
    "explode_burst": [r"\bexplo", r"\bburst", r"\bdetonat"],
    "drift_orbit": [r"\bdrift", r"\bsail", r"\bglide"],
    "character_motion": [r"\bwalk", r"\bmarche", r"\brun(s|ning)?\b", r"\bcourt", r"\bcourse", r"\bjump", r"\bsaute", r"\battack", r"\battaque", r"\bdance", r"\bdanse"],
}

MATERIAL_PATTERNS: dict[str, list[str]] = {
    "metallic": [r"\bmetal", r"\bchrome", r"\bsteel", r"\bcopper", r"\bbrass", r"\bgold(en)?\b",
                  r"\bsilver", r"\biron", r"\btitanium", r"\baluminum"],
    "glass_crystal": [r"\bglass", r"\bcrystal", r"\btransparent", r"\bdiamond"],
    "emissive": [r"\bneon", r"\blava", r"\bplasma", r"\bhologram", r"\bled"],
    "wet": [r"\bwet", r"\bsoaked", r"\bdrench"],
    "organic": [r"\bskin", r"\bfur", r"\bleaf", r"\bbark", r"\bmoss", r"\bflesh"],
    "stone": [r"\bstone", r"\brock", r"\bmarble", r"\bgranite", r"\bconcrete"],
    "fabric": [r"\bfabric", r"\bcloth", r"\bsilk", r"\bvelvet", r"\bcotton"],
}

# Order = priority. More specific moods first so generic adjectives like
# "dark <color>" don't claim dramatic_night when a "studio" cue is also present.
MOOD_PATTERNS: dict[str, list[str]] = {
    "studio_clean": [r"\bstudio", r"\bproduct shot", r"\bwhite background", r"\bclean(?:\b|ly)"],
    "cyberpunk": [r"\bcyber", r"\bneon-lit\b", r"\bdystop", r"\bfuturistic city"],
    "underwater": [r"\bunderwater", r"\bocean depth", r"\babyss", r"\bsubmerged"],
    "winter_cold": [r"\bsnow", r"\bice\b", r"\bfrozen", r"\bblizzard", r"\bglacier"],
    "desert_hot": [r"\bdesert", r"\bsahara", r"\bdune", r"\barid"],
    "lush_forest": [r"\bforest", r"\bjungle", r"\brainforest"],
    "fantasy_magic": [r"\bmagic", r"\bmythical", r"\bfantas", r"\benchant", r"\bmystic"],
    "golden_hour": [r"\bsunset", r"\bsunrise", r"\bdawn\b", r"\bdusk", r"\bgolden hour"],
    "dramatic_night": [r"\bnight\b", r"\bmoonlit", r"\bstormy", r"\bnocturnal",
                         r"\bdarkness\b", r"\bshadow(s|y)?\b"],
}

CATEGORY_PATTERNS: dict[str, list[str]] = {
    "character": [r"\bperson", r"\bman\b", r"\bwoman\b", r"\bwarrior", r"\bknight", r"\bwizard",
                   r"\belf\b", r"\borc\b", r"\bsamurai", r"\bcharacter", r"\bpersonnage", r"\bhomme", r"\bfemme", r"\bfille", r"\bgar[cç]on"],
    "creature": [r"\bdragon", r"\bbird", r"\banimal", r"\bbeast", r"\bcreature", r"\bdog\b",
                  r"\bcat\b", r"\bhorse", r"\bfish", r"\binsect", r"\bchien", r"\bchat", r"\bcheval", r"\boiseau", r"\bmonstre", r"\bcr[eé]ature"],
    "vehicle": [r"\bcar\b", r"\btruck", r"\bship", r"\bplane", r"\brocket", r"\bvehicle",
                r"\bmotorcycle", r"\bboat", r"\bspaceship", r"\bvoiture", r"\bcamion", r"\bavion", r"\bmoto", r"\bbateau", r"\bv[eé]hicule"],
    "mechanical": [r"\brobot", r"\bmecha", r"\bautomaton", r"\bdrone", r"\bturret", r"\bm[eé]ca"],
    "object": [r"\bsword", r"\blantern", r"\bbottle", r"\bbook", r"\bcrown", r"\bring",
                r"\bweapon", r"\bartifact", r"\bvase", r"\bclock", r"\bmechanism", r"\b[eé]p[eé]e", r"\bobjet", r"\blanterne", r"\blivre", r"\barme"],
    "architecture": [r"\bhouse", r"\bcastle", r"\btower", r"\bbuilding", r"\btemple",
                       r"\bcathedral", r"\bbridge", r"\bruin", r"\bmaison", r"\bch[aâ]teau", r"\bb[aâ]timent", r"\bpont", r"\barchitecture"],
    "nature": [r"\btree", r"\bplant", r"\bflower", r"\bmountain", r"\bcanyon", r"\bisland",
                r"\bwaterfall", r"\bvolcano", r"\barbre", r"\bplante", r"\bfleur", r"\bmontagne", r"\bvolcan", r"\b[iî]le", r"\bnature"],
    "scenery_landscape": [r"\blandscape", r"\bvista", r"\bscene", r"\bdiorama", r"\bpaysage", r"\bville", r"\bcity", r"\benvironnement"],
}

# Kept short so CLIP's 77-token window does not truncate it when appended to
# the refined prompt. Critical SDXL hints only.
QUALITY_BOOST = "photorealistic, intricate detail, sharp focus, vivid colors"


def _default_params(atype: str) -> dict[str, Any]:
    return {
        "rotate_y": {"period_s": 6.0},
        "emission_pulse": {"freq_hz": 0.3, "min_strength": 0.4, "max_strength": 3.5},
        "particles_rain": {"count": 6000, "wind_xy": [0.2, 0.0]},
        "particles_snow": {"count": 4000, "wind_xy": [0.05, 0.0]},
        "particles_fire": {"count": 3000, "rise_z": 1.5},
        "particles_smoke": {"count": 2500, "rise_z": 0.6},
        "particles_dust": {"count": 2000, "wind_xy": [0.4, 0.1]},
        "particles_sparks": {"count": 1500, "rise_z": 0.4},
        "hover_float": {"amplitude": 0.08, "period_s": 4.0},
        "fluid_flow": {"strength": 0.05, "freq_hz": 1.0},
        "mechanical_articulate": {"period_s": 4.0, "max_angle_deg": 25},
        "shake_vibrate": {"amplitude": 0.01, "freq_hz": 12.0},
        "explode_burst": {"start_frame": 30, "force": 5.0},
        "drift_orbit": {"radius": 0.3, "period_s": 10.0},
        "beauty_turntable": {"period_s": 6.0},
    }.get(atype, {})


@dataclass
class SceneProfile:
    name: str
    prompt_original: str
    prompt_image: str
    animations: list[dict[str, Any]] = field(default_factory=list)
    materials_hint: list[str] = field(default_factory=list)
    mood: str = "neutral"
    category: str = "object"
    has_animation: bool = False
    confidence: float = 0.0
    duration_s: float = 6.0
    fps: int = 24
    engine: str = "auto"
    pose: str = "A-pose"


def _any_match(text: str, patterns: list[str]) -> bool:
    return any(re.search(pat, text) for pat in patterns)


def _first_match(text: str, table: dict[str, list[str]], default: str) -> str:
    for key, pats in table.items():
        if _any_match(text, pats):
            return key
    return default


def _slugify(text: str, maxlen: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:maxlen] or "scene"


_HUNYUAN_COMPOSITION = (
    "isolated on plain neutral backdrop, full subject visible, centered, "
    "even balanced studio lighting, no occlusions"
)

# Phrases that drag the subject into an environment Hunyuan3D will try to
# include in the mesh (and fail at). Stripping them keeps the mood as a
# separate tonal hint but forces the subject to be alone in the frame.
_ENV_CONTEXT_PATTERNS: list[tuple[str, str]] = [
    (r",?\s+\bin\s+(?:a\s+|the\s+)?(?:lush\s+|dense\s+|vast\s+|deep\s+|dark\s+|big\s+|tropical\s+|misty\s+|stormy\s+)?(?:jungle|forest|desert|city|abyss|cave|mountains?|fog|cloud(?:s)?|room|hall|courtyard|garden|field|sky|valley|landscape|background|environment|scene)\b", ""),
    (r",?\s+\bon\s+(?:a\s+|the\s+)?(?:wet|stone|wooden|grass|marble)\s+(?:floor|surface|street|ground|table)\b", ""),
    (r",?\s+\bat\s+(?:sunset|sunrise|dawn|dusk|night|noon|midnight|twilight)\b", ""),
    (r",?\s+\bduring\s+(?:sunset|sunrise|night|dusk|dawn|twilight|the\s+golden\s+hour)\b", ""),
    (r",?\s+\bdramatic\s+(?:sunset|sunrise|night|dawn|dusk|sky|lighting|atmosphere)\b", ""),
    (r",?\s+\b(?:cinematic|moody|epic)\s+(?:lighting|atmosphere|background|setting)\b", ""),
    (r",?\s+\b(?:rain\s+wet|wet\s+rain)\s+(?:street|road|pavement|sidewalk)\b", ""),
    (r",?\s+\bin\s+(?:the\s+)?(?:dark\s+|deep\s+)?ocean(?:\s+depth)?\b", ""),
    (r",?\s+\bsurrounded\s+by\s+\w+(?:\s+\w+){0,5}", ""),
    (r",?\s+\bbackground\b[\w\s,]*$", ""),
]

# Actions that should trigger animation BUT must not be in the visual prompt
# Otherwise the 3D model generates in a twisted pose, making rigging impossible.
_ACTION_STRIP_PATTERNS: list[tuple[str, str]] = [
    (r"\b(running|run|walk|walking|marche|court|courir|jump|jumping|saute|sauter|attack|attacking)\b", ""),
    (r"\b(hover|hovering|levitating|levitate|floating)\b", ""),
]


def _strip_env_context(prompt: str) -> str:
    """Remove environmental phrases that confuse Hunyuan3D image-to-3D, while
    keeping the subject and its descriptors intact. The mood detection above
    has already captured tone from the original prompt before this strip runs.
    """
    cleaned = prompt
    for pat, repl in _ENV_CONTEXT_PATTERNS:
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)
    for pat, repl in _ACTION_STRIP_PATTERNS:
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(", ")
    return cleaned


def refine_image_prompt(prompt: str, mood: str, category: str, materials: list[str], pose: str = "A-pose") -> str:
    """Image prompt tuned for Hunyuan3D image-to-3D: front-loads composition cues
    that Hunyuan3D needs (isolation, full subject, no environment), keeps mood
    as a tonal hint at the end so it does not dominate.
    """
    clean_prompt = _strip_env_context(prompt.strip().rstrip(".,"))
    
    # Check if the prompt already describes an isolated/studio style.
    # If not, add the minimal composition hints.
    if not _any_match(clean_prompt, [r"\bisolated\b", r"\bwhite background\b", r"\bneutral\b"]):
        img_prompt = f"{clean_prompt}, {_HUNYUAN_COMPOSITION}"
    else:
        img_prompt = clean_prompt
    
    parts: list[str] = [img_prompt]
    
    if category == "character":
        parts.append(f"single character, full body, {pose}, facing camera, no held items obscuring face")
    elif category == "creature":
        parts.append("single creature, full body, neutral pose, facing camera")
    elif category == "vehicle":
        parts.append("single isolated vehicle, three-quarter front view, complete silhouette, no environment")
    elif category == "architecture":
        parts.append("single isolated building, three-quarter view, entire structure visible, no vegetation or environment around it")
    elif category == "object":
        parts.append("single isolated object, centered, no environment, no surface beneath")
    elif category == "nature":
        parts.append("single isolated natural element, no environment around it, plain backdrop")
    if materials:
        parts.append("material focus: " + ", ".join(materials))
    mood_hints = {
        "dramatic_night": "moody key light, deep contrast but subject still fully lit",
        "golden_hour": "warm rim light, soft golden tones",
        "studio_clean": "soft key light, neutral grey backdrop",
        "fantasy_magic": "ethereal glow, subtle atmosphere",
        "cyberpunk": "neon rim light, magenta and cyan accents",
        "underwater": "caustic light, blue-green tone",
        "winter_cold": "cold blue tones, soft overcast light",
        "desert_hot": "warm sun, soft shadows",
        "lush_forest": "dappled green light, subject brightly lit",
    }
    if mood in mood_hints:
        parts.append(mood_hints[mood])
    parts.append(QUALITY_BOOST)
    return ", ".join(parts)


def classify(prompt: str, name: str | None = None) -> SceneProfile:
    p = prompt.lower()
    animations: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for atype, patterns in ANIMATION_PATTERNS.items():
        if _any_match(p, patterns) and atype not in seen_types:
            animations.append({"type": atype, "params": _default_params(atype)})
            seen_types.add(atype)

    materials = [m for m, pats in MATERIAL_PATTERNS.items() if _any_match(p, pats)]
    mood = _first_match(p, MOOD_PATTERNS, "neutral")
    category = _first_match(p, CATEGORY_PATTERNS, "object")

    has_animation = bool(animations)
    if not has_animation:
        animations.append({"type": "beauty_turntable", "params": _default_params("beauty_turntable")})

    confidence = min(1.0, 0.25 + 0.18 * len(animations) + 0.08 * len(materials) +
                       (0.12 if mood != "neutral" else 0) + (0.12 if category != "object" else 0))

    pose = "A-pose"
    if _any_match(p, [r"\bpose en t\b", r"\bt-pose\b", r"\bpose t\b"]):
        pose = "T-pose"
    elif _any_match(p, [r"\bpose en a\b", r"\ba-pose\b", r"\bpose a\b"]):
        pose = "A-pose"

    engine = "auto"
    if _any_match(p, [r"\bmoge\b"]):
        engine = "moge"
    elif _any_match(p, [r"\bhunyuanworldmirror\b", r"\bworldmirror\b"]):
        engine = "hunyuanworldmirror"
    elif _any_match(p, [r"\bhunyuanworld\b", r"\bworld\b"]):
        engine = "hunyuanworld"
    elif _any_match(p, [r"\btrelli(?:s)?\b"]):
        engine = "trellis"
    elif _any_match(p, [r"\bhunyuan(?:3d)?\b"]):
        engine = "hunyuan3d"
    elif category in ("scenery_landscape", "nature"):
        engine = "hunyuanworld"  # SOTA for environment reconstruction
    elif category == "character":
        engine = "trellis"       # Better organic volume consistency
    elif category in ("object", "vehicle", "architecture"):
        engine = "hunyuanworldmirror"  # SOTA feedforward 3D reconstruction
    else:
        engine = "hunyuan3d"

    refined = refine_image_prompt(prompt, mood, category, materials, pose)
    return SceneProfile(
        name=name or _slugify(prompt),
        prompt_original=prompt,
        prompt_image=refined,
        animations=animations,
        materials_hint=materials,
        mood=mood,
        category=category,
        has_animation=has_animation,
        confidence=round(confidence, 2),
        engine=engine,
        pose=pose,
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aurora_classify.py <prompt> [name]", file=sys.stderr)
        return 2
    prompt = argv[1]
    name = argv[2] if len(argv) > 2 else None
    profile = classify(prompt, name)
    print(json.dumps(asdict(profile), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
