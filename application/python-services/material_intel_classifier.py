#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:27b"
FALLBACK_MODEL = "qwen3:14b"

SYSTEM_PROMPT = """You are a 3D material intelligence classifier for a real-time Blender/glTF pipeline.
Given a description of an object or scene (and optionally its subject kind),
you list the material ZONES the final textured mesh is EXPECTED to contain,
and for each zone the physically-based channels the pipeline must author.
You do not see the mesh — you reason from first principles about what the
described object is made of in real life.

Known material classes and their reference channel values (use these values
unless the prompt clearly demands otherwise):

- glass          -> transmission 1.0, ior 1.5, roughness 0.05, metallic 0.0
- water          -> transmission 1.0, ior 1.33, roughness 0.02, metallic 0.0,
                    attenuation_color blue-green hex (e.g. "#3fbfae"),
                    attenuation_distance 0.8
- fabric         -> sheen 0.8, sheen_color "#ffffff", roughness 0.85, metallic 0.0
- car_paint      -> clearcoat 1.0, clearcoat_roughness 0.03, metallic 0.9,
                    roughness 0.4 (any varnished / lacquered body shell)
- brushed_metal  -> anisotropy 0.8, anisotropy_rotation 0.0, metallic 1.0,
                    roughness 0.35
- metal          -> metallic 1.0, roughness 0.3 (plain metal: armor, steel,
                    chrome, gold, sword blades)
- led            -> emissive_strength 6.0, emissive_color hex (RGB strips,
                    neon, glowing panels)
- skin           -> specular 0.028, roughness 0.5, metallic 0.0,
                    roughness_zonal {"forehead":0.35,"nose":0.3,"cheeks":0.55,"body":0.65}
- stone          -> roughness 0.9, metallic 0.0
- default        -> roughness 0.6, metallic 0.0 (anything else: wood, plastic,
                    painted matte surfaces)

Output ONLY a JSON object, no markdown, no commentary. Schema:

{
  "schema": "aurora.material-intel.v1",
  "confidence": <0.0-1.0 — how sure you are>,
  "rationale": "<one sentence explaining your reasoning>",
  "zones": [
    {
      "zone": "<short lowercase name of the region, e.g. 'water_basin'>",
      "material_class": "<one of the classes above>",
      "keywords": ["<words from the prompt that map to this zone>"],
      "channels": { <channel values for this class, reference values unless overridden> }
    }
  ]
}

Rules:
- List EVERY distinct material zone the prompt implies (a knight in armor
  with a cloth cape has at least a metal zone AND a fabric zone).
- Use ONLY the material classes listed above; map synonyms onto them
  (varnish/lacquer -> car_paint, cloth/textile -> fabric, rock -> stone).
- Emit only channels that belong to the chosen class.
- Never invent zones the prompt does not imply; if nothing matches, emit a
  single zone with material_class "default".
- confidence 0.95+ when materials are stated explicitly, 0.7-0.94 when
  inferred from the object identity, below 0.7 when guessing."""

CLASS_CHANNELS = {
    "glass": {"transmission": 1.0, "ior": 1.5, "roughness": 0.05, "metallic": 0.0},
    "water": {"transmission": 1.0, "ior": 1.33, "roughness": 0.02, "metallic": 0.0,
              "attenuation_color": "#3fbfae", "attenuation_distance": 0.8},
    "fabric": {"sheen": 0.8, "sheen_color": "#ffffff", "roughness": 0.85, "metallic": 0.0},
    "car_paint": {"clearcoat": 1.0, "clearcoat_roughness": 0.03, "metallic": 0.9, "roughness": 0.4},
    "brushed_metal": {"anisotropy": 0.8, "anisotropy_rotation": 0.0, "metallic": 1.0, "roughness": 0.35},
    "metal": {"metallic": 1.0, "roughness": 0.3},
    "led": {"emissive_strength": 6.0, "emissive_color": "#ffffff"},
    "skin": {"specular": 0.028, "roughness": 0.5, "metallic": 0.0,
             "roughness_zonal": {"forehead": 0.35, "nose": 0.3, "cheeks": 0.55, "body": 0.65}},
    "stone": {"roughness": 0.9, "metallic": 0.0},
    "default": {"roughness": 0.6, "metallic": 0.0},
}

CLASS_ALIASES = {
    "carpaint": "car_paint", "car paint": "car_paint", "varnish": "car_paint",
    "lacquer": "car_paint", "clearcoat": "car_paint",
    "cloth": "fabric", "textile": "fabric", "sheen": "fabric",
    "metal_brushed": "brushed_metal", "brushed metal": "brushed_metal",
    "anisotropic_metal": "brushed_metal",
    "rock": "stone", "concrete": "stone", "marble": "stone",
    "emissive": "led", "neon": "led", "rgb": "led",
    "flesh": "skin", "crystal": "glass", "liquid": "water",
}

CHANNEL_RANGES = {
    "transmission": (0.0, 1.0), "roughness": (0.0, 1.0), "metallic": (0.0, 1.0),
    "sheen": (0.0, 1.0), "clearcoat": (0.0, 1.0), "clearcoat_roughness": (0.0, 1.0),
    "anisotropy": (0.0, 1.0), "anisotropy_rotation": (0.0, 1.0),
    "specular": (0.0, 1.0), "ior": (1.0, 2.5),
    "emissive_strength": (0.0, 20.0), "attenuation_distance": (0.01, 100.0),
}

COLOR_CHANNELS = {"attenuation_color", "sheen_color", "emissive_color"}

CANONICAL_SCHEMA = "aurora.material-intel.v1"

CANONICAL_LABELS = {
    "glass": "glass", "water": "water", "fabric": "fabric",
    "car_paint": "paint_gloss", "brushed_metal": "brushed_metal",
    "metal": "metal", "led": "led", "skin": "skin", "stone": "stone",
    "default": "plastic",
}

CANONICAL_CHANNEL_MAP = {
    "transmission": "transmission", "ior": "ior", "roughness": "roughness",
    "metallic": "metallic", "sheen": "sheen", "sheen_color": "sheenColor",
    "clearcoat": "clearcoat", "clearcoat_roughness": "clearcoatRoughness",
    "anisotropy": "anisotropyStrength", "anisotropy_rotation": "anisotropy",
    "specular": "specular", "emissive_strength": "emissiveStrength",
    "emissive_color": "emissiveFactor", "attenuation_color": "attenuationColor",
}

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

ZONE_PATTERNS = [
    ("water", r"\b(eau|water|aquatique|fontaine|fountain|oc[eé]an|ocean|mer|sea|lac|lake|rivi[eè]re|river|cascade|waterfall|piscine|pool|liquide|liquid|vague|waves?|aquarium)\b"),
    ("glass", r"\b(verre|vitre|vitrail|vitr[eé]e?s?|glass|crystal|cristal|windows?|fen[eê]tres?|bouteilles?|bottles?|miroirs?|mirrors?|lentilles?|lens)\b"),
    ("led", r"\b(leds?|rgb|argb|strimer|rog|strix|aura\s+sync|n[eé]ons?|neon|emissive|glow(?:ing)?|lumineu(?:x|se)s?|backlight|r[eé]tro[- ]?[eé]clairage)\b"),
    ("fabric", r"\b(tissus?|fabric|cloth(?:es|ing)?|textiles?|capes?|velours|velvet|soie|silk|laine|wool|coton|cotton|rideaux?|curtains?|drapeaux?|flags?|toile|canvas|v[eê]tements?|robes?|dress|tuniques?|tunic|manteaux?|coat|banni[eè]res?|banners?|cuir|leather)\b"),
    ("brushed_metal", r"\b(brushed|bross[eé]e?s?)\b"),
    ("car_paint", r"\b(voitures?|cars?|automobiles?|carrosserie|bodywork|vernis|varnish(?:ed)?|laques?|laqu[eé]e?s?|lacquer(?:ed)?|clearcoat|supercar|roadster)\b"),
    ("metal", r"\b(m[eé]tal(?:lique)?s?|metal(?:lic)?|acier|steel|fer|iron|chrom[eé]?e?|chrome|aluminium|alu|inox|stainless|cuivre|copper|bronze|laiton|brass|gold|dor[eé]e?s?|argent[eé]?e?s?|silver|armures?|armou?r|chevaliers?|knights?|[eé]p[eé]es?|swords?|blades?|lames?|motherboards?|cartes?\s+m[eè]res?|heatsinks?|dissipateurs?|pcb|vrm)\b"),
    ("skin", r"\b(peau|skin|visages?|face|portrait|chair|flesh)\b"),
    ("stone", r"\b(pierres?|stones?|roches?|rocks?|granite?|marbre|marble|b[eé]ton|concrete|briques?|bricks?|pav[eé]s?|statues?)\b"),
]

KIND_SKIN_RE = re.compile(r"\b(character|creature|humanoid|personnage|humain|human|avatar|portrait)\b")
KIND_CAR_RE = re.compile(r"\b(vehicle|v[eé]hicule|voiture|car|automobile)\b")


def _ollama_chat(model: str, prompt: str, kind: str | None,
                 timeout_s: int = 90) -> str:
    user_msg = prompt.strip()
    if kind:
        user_msg = f"{user_msg}\n\nSubject kind: {kind.strip()}"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0.1, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    payload = json.loads(raw)
    return (payload.get("message", {}) or {}).get("content", "") or ""


def _safe_json_extract(text: str) -> dict | None:
    if not text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _clamp01(n) -> float:
    try:
        f = float(n)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def _clamp_channel(name: str, value) -> float | None:
    lo, hi = CHANNEL_RANGES.get(name, (0.0, 1.0))
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, f))


def _normalize_channels(cls: str, raw_channels) -> dict:
    defaults = CLASS_CHANNELS[cls]
    channels: dict = {}
    src = raw_channels if isinstance(raw_channels, dict) else {}
    for key, default in defaults.items():
        val = src.get(key, default)
        if key in COLOR_CHANNELS:
            channels[key] = val if isinstance(val, str) and HEX_RE.match(val) else default
        elif key == "roughness_zonal":
            zonal = val if isinstance(val, dict) else default
            channels[key] = {str(k): _clamp01(v) for k, v in zonal.items()
                             if isinstance(v, (int, float))} or dict(default)
        else:
            clamped = _clamp_channel(key, val)
            channels[key] = clamped if clamped is not None else default
    return channels


def _resolve_class(name) -> str | None:
    if not isinstance(name, str):
        return None
    key = name.strip().lower()
    if key in CLASS_CHANNELS:
        return key
    return CLASS_ALIASES.get(key)


def _normalize(raw: dict | None, model: str, prompt: str,
               kind: str | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    raw_zones = raw.get("zones")
    if not isinstance(raw_zones, list) or not raw_zones:
        return None
    zones = []
    seen = set()
    for rz in raw_zones:
        if not isinstance(rz, dict):
            continue
        cls = _resolve_class(rz.get("material_class"))
        if cls is None:
            continue
        zone_name = rz.get("zone")
        zone_name = zone_name.strip().lower()[:64] if isinstance(zone_name, str) and zone_name.strip() else cls
        dedupe_key = (zone_name, cls)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        kws = rz.get("keywords")
        keywords = [str(k)[:40] for k in kws if isinstance(k, str)][:8] if isinstance(kws, list) else []
        zones.append({
            "zone": zone_name,
            "material_class": cls,
            "keywords": keywords,
            "channels": _normalize_channels(cls, rz.get("channels")),
        })
    if not zones:
        return None
    return {
        "schema": "aurora.material-intel.v1",
        "prompt": prompt.strip()[:400],
        "kind": kind.strip()[:64] if kind else None,
        "confidence": _clamp01(raw.get("confidence", 0.7)),
        "rationale": str(raw.get("rationale", ""))[:400],
        "model": model,
        "zones": zones,
    }


def _regex_fallback(prompt: str, kind: str | None) -> dict:
    text = (prompt or "").lower()
    if kind:
        text = f"{text} {kind.lower()}"
    zones = []
    matched_classes = set()
    for cls, pattern in ZONE_PATTERNS:
        hits = re.findall(pattern, text)
        if not hits:
            continue
        keywords = []
        for h in hits:
            word = h if isinstance(h, str) else next((g for g in h if g), "")
            if word and word not in keywords:
                keywords.append(word)
        zones.append({
            "zone": cls,
            "material_class": cls,
            "keywords": keywords[:8],
            "channels": _normalize_channels(cls, None),
        })
        matched_classes.add(cls)
    if kind:
        k = kind.lower()
        if KIND_SKIN_RE.search(k) and "skin" not in matched_classes:
            zones.append({"zone": "skin", "material_class": "skin",
                          "keywords": [k.strip()[:40]],
                          "channels": _normalize_channels("skin", None)})
            matched_classes.add("skin")
        if KIND_CAR_RE.search(k) and "car_paint" not in matched_classes:
            zones.append({"zone": "car_paint", "material_class": "car_paint",
                          "keywords": [k.strip()[:40]],
                          "channels": _normalize_channels("car_paint", None)})
            matched_classes.add("car_paint")
    if not zones:
        zones.append({"zone": "default", "material_class": "default",
                      "keywords": [],
                      "channels": _normalize_channels("default", None)})
    return {
        "schema": "aurora.material-intel.v1",
        "prompt": (prompt or "").strip()[:400],
        "kind": kind.strip()[:64] if kind else None,
        "confidence": 0.6 if matched_classes else 0.0,
        "rationale": "Ollama unreachable or disabled - regex fallback",
        "model": "fallback:regex",
        "zones": zones,
    }


def classify(prompt: str, kind: str | None = None,
             model: str = DEFAULT_MODEL) -> dict:
    if not prompt or not prompt.strip():
        return {
            "schema": "aurora.material-intel.v1",
            "prompt": "",
            "kind": kind.strip()[:64] if kind else None,
            "confidence": 1.0,
            "rationale": "Empty prompt",
            "model": "fallback:empty",
            "zones": [{"zone": "default", "material_class": "default",
                       "keywords": [],
                       "channels": _normalize_channels("default", None)}],
        }
    if os.environ.get("AURORA_MATINTEL_NO_LLM") == "1":
        return _regex_fallback(prompt, kind)
    try:
        text = _ollama_chat(model, prompt, kind, timeout_s=90)
        manifest = _normalize(_safe_json_extract(text), model, prompt, kind)
        if manifest:
            return manifest
        text2 = _ollama_chat(FALLBACK_MODEL, prompt, kind, timeout_s=120)
        manifest2 = _normalize(_safe_json_extract(text2), FALLBACK_MODEL, prompt, kind)
        if manifest2:
            return manifest2
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        pass
    return _regex_fallback(prompt, kind)


def to_canonical(manifest: dict) -> dict:
    src = manifest if isinstance(manifest, dict) else {}
    conf = _clamp01(src.get("confidence", 0.5))
    zones = []
    seen = set()
    raw_zones = src.get("zones")
    for rz in raw_zones if isinstance(raw_zones, list) else []:
        if not isinstance(rz, dict):
            continue
        cls = _resolve_class(rz.get("material_class"))
        label = CANONICAL_LABELS.get(cls or "")
        if label is None:
            continue
        raw_id = rz.get("zone")
        zone_id = raw_id.strip().lower()[:64] if isinstance(raw_id, str) and raw_id.strip() else label
        base_id = zone_id
        n = 2
        while zone_id in seen:
            zone_id = "%s_%d" % (base_id, n)
            n += 1
        seen.add(zone_id)
        channels = {}
        raw_ch = rz.get("channels")
        for key, val in (raw_ch if isinstance(raw_ch, dict) else {}).items():
            ck = CANONICAL_CHANNEL_MAP.get(key)
            if ck is not None:
                channels[ck] = val
        zones.append({
            "zone_id": zone_id,
            "label": label,
            "target": {"material_index": 0},
            "channels": channels,
            "confidence": conf,
            "source": "classifier",
        })
    out = {"schema": CANONICAL_SCHEMA, "zones": zones}
    for key in ("prompt", "kind", "rationale", "model"):
        if src.get(key) is not None:
            out[key] = src[key]
    return out


def _zone_by_class(manifest: dict, cls: str) -> dict | None:
    for z in manifest.get("zones", []):
        if z.get("material_class") == cls:
            return z
    return None


def self_test() -> dict:
    os.environ["AURORA_MATINTEL_NO_LLM"] = "1"
    cases = [
        {
            "prompt": "une fontaine en pierre avec eau",
            "kind": None,
            "expect_classes": ["stone", "water"],
            "expect_channels": [("water", "transmission", 1.0), ("water", "ior", 1.33)],
        },
        {
            "prompt": "Lian Li Strimer cables RGB",
            "kind": None,
            "expect_classes": ["led"],
            "expect_channels": [("led", "emissive_strength", 6.0)],
        },
        {
            "prompt": "un chevalier armure + cape tissu",
            "kind": None,
            "expect_classes": ["metal", "fabric"],
            "expect_channels": [("fabric", "sheen", 0.8)],
        },
        {
            "prompt": "un vase en verre souffle",
            "kind": None,
            "expect_classes": ["glass"],
            "expect_channels": [("glass", "transmission", 1.0), ("glass", "ior", 1.5)],
        },
        {
            "prompt": "boitier PC aluminium brosse",
            "kind": None,
            "expect_classes": ["brushed_metal"],
            "expect_channels": [("brushed_metal", "anisotropy", 0.8)],
        },
        {
            "prompt": "une voiture de sport vernis rouge",
            "kind": "vehicle",
            "expect_classes": ["car_paint"],
            "expect_channels": [("car_paint", "clearcoat", 1.0)],
        },
        {
            "prompt": "portrait realiste peau visage",
            "kind": "character",
            "expect_classes": ["skin"],
            "expect_channels": [("skin", "specular", 0.028)],
        },
        {
            "prompt": "ASUS ROG STRIX motherboard",
            "kind": "motherboard",
            "expect_classes": ["metal", "led"],
            "expect_channels": [("metal", "metallic", 1.0), ("led", "emissive_strength", 6.0)],
        },
    ]
    results = []
    all_ok = True
    for case in cases:
        manifest = classify(case["prompt"], case["kind"])
        classes = [z["material_class"] for z in manifest["zones"]]
        ok = all(c in classes for c in case["expect_classes"])
        for cls, channel, expected in case["expect_channels"]:
            zone = _zone_by_class(manifest, cls)
            if zone is None or abs(zone["channels"].get(channel, -1.0) - expected) > 1e-6:
                ok = False
        water_zone = _zone_by_class(manifest, "water")
        if water_zone is not None and not HEX_RE.match(water_zone["channels"].get("attenuation_color", "")):
            ok = False
        all_ok = all_ok and ok
        results.append({"prompt": case["prompt"], "ok": ok, "classes": classes})
    fountain = classify("une fontaine en pierre avec eau", None)
    canonical = to_canonical(fountain)
    canon_ok = canonical.get("schema") == CANONICAL_SCHEMA
    for z in canonical.get("zones", []):
        canon_ok = canon_ok and z.get("source") == "classifier"
        canon_ok = canon_ok and z.get("target", {}).get("material_index") == 0
        canon_ok = canon_ok and "attenuation_distance" not in z.get("channels", {})
    water = next((z for z in canonical.get("zones", []) if z.get("label") == "water"), None)
    canon_ok = canon_ok and water is not None
    canon_ok = canon_ok and water["channels"].get("attenuationColor") == "#3fbfae"
    canon_ok = canon_ok and abs(water["channels"].get("ior", -1.0) - 1.33) < 1e-6
    try:
        import material_manifest
        v_ok, v_errs = material_manifest.validate(canonical)
    except Exception as exc:
        v_ok, v_errs = False, [repr(exc)]
    canon_ok = canon_ok and v_ok
    all_ok = all_ok and canon_ok
    results.append({"prompt": "to_canonical(fontaine) -> material_manifest.validate",
                    "ok": canon_ok,
                    "classes": [z.get("label") for z in canonical.get("zones", [])],
                    "validate_errors": v_errs})
    return {"self_test": True, "passed": all_ok, "cases": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--kind", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--canonical", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        out = self_test()
        print("AURORA_MATINTEL_RESULT:" + json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        return 0 if out["passed"] else 1
    if not args.prompt:
        ap.error("--prompt is required unless --self-test is given")
    out = classify(args.prompt, args.kind, args.model)
    if args.canonical:
        out = to_canonical(out)
    print("AURORA_MATINTEL_RESULT:" + json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
