#!/usr/bin/env python3
"""motion_intent_classifier — Python mirror of threeDMotionIntent.ts.

Used by the bridge endpoint /api/3d/motion-intent so the UI (and the test
harness) can hit a single HTTP route. The TS service is the canonical
classifier; this script reuses the SAME system prompt verbatim so behaviour
is bit-identical.

Usage:
    python motion_intent_classifier.py --prompt "Lian Li Strimer Plus V2"
    python motion_intent_classifier.py --prompt "RAM verte" --custom "rotation lente axe Y"

Output: JSON on stdout matching aurora.motion-intent.v1 schema.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:27b"   # installe, non-thinking -> JSON propre (gemma3:12b n'existe pas ici)
FALLBACK_MODEL = "qwen3:14b"

# Keep this verbatim with the TS service. If you change one, update the other.
SYSTEM_PROMPT = """You are a 3D animation intent classifier for a real-time Blender pipeline.
Given a description of an object or subject, you decide which ONE of six
motion primitives the system should bake. You DO NOT have a brand list — you
reason from first principles about what the object actually is and what it
does in real life.

Six categories (pick exactly one):

1. led_emission — the subject is an LED-bearing surface or cable whose
   "motion" is purely a colour pattern on its emissive material. No rig.
   Examples (do not memorise — reason): RGB cable extension, addressable
   strip, neon sign, smart bulb, status LED.

2. fan_pwm — the subject is a fan, propeller, turbine, motor rotor, or any
   blade that spins around a fixed axis at constant RPM in normal use.

3. oled_screen — the subject contains a small embedded screen (OLED,
   e-paper, IPS dashboard) which displays scrolling text or icons in normal
   use. The screen face must be UV-unwrappable.

4. creature_organic — the subject is alive: human, humanoid, animal, fantasy
   monster, robot with anatomy. Needs a skeletal rig + idle/walk/breathing
   cycle.

5. mechanical_simple — the subject has a hinge, button, slider, lever, or
   single-DoF joint that opens/closes/presses with a clear linear or rotary
   motion. NOT a fan (use fan_pwm) and NOT a creature (use creature_organic).

6. rigid_static — the subject is inert hardware whose normal state is
   stationary: passive heatsink, RAM stick without RGB, screw, bolt,
   bracket, plain enclosure, rock, statue.

Output ONLY a JSON object, no markdown, no commentary. Schema:

{
  "schema": "aurora.motion-intent.v1",
  "category": "<one of the 6 above>",
  "confidence": <0.0-1.0 — how sure you are>,
  "rationale": "<one sentence explaining your reasoning>",
  "color_anim":     { "pattern": "chase|rainbow|breathing|pulse|static_color",
                      "speed_hz": <number>, "colors": ["#hex",...],
                      "emission_strength": <number>, "led_count": <int?> },
  "mechanical_anim": { "axis": "X|Y|Z",
                       "motion_type": "rotation|translation|oscillation",
                       "rpm": <number?>, "amplitude": <number?>,
                       "period_s": <number?> },
  "screen_anim":    { "content_kind": "text_scroll|icon_carousel|temperature_dash|logo_loop",
                      "content_type": "text_scroll|icon_rotation|system_stats|mixed",
                      "resolution_px": [<w>,<h>], "frame_rate": <number>,
                      "text": "<string?>" },
  "creature_anim":  { "base_loop": "idle_breathing|walk_cycle|run_cycle|hover",
                      "bpm": <number?>, "stride_length_m": <number?>,
                      "locomotion": "humanoid|quadruped|serpent|auto" }
}

Include ONLY the *_anim block matching the category you chose. Omit the
other three. For rigid_static, include none of the four blocks.

Reasoning checklist before answering:
- Is the subject alive or articulated as a creature? -> creature_organic.
- Does it spin in normal operation around a single axis? -> fan_pwm.
- Does it display dynamic text/icons on an embedded screen? -> oled_screen.
- Does it have integrated programmable LEDs whose colour changes? -> led_emission.
- Does it have a single-DoF moving part (hinge/button/slider)? -> mechanical_simple.
- Otherwise (and especially if it's plain inert hardware): rigid_static.

When you choose oled_screen, ALSO choose a content_type:
  - text_scroll    if the screen scrolls a marquee/string
  - icon_rotation  if it cycles through icons (CPU, RAM, FAN, GPU)
  - system_stats   if it shows live numbers (temp/percent/RPM) -- typical for LiveDash
  - mixed          if it alternates several modes
When you choose creature_organic, ALSO choose locomotion:
  - humanoid  for biped humans / humanoid robots
  - quadruped for animals on 4 legs (dog, dragon, lion, wolf)
  - serpent   for snakes, eels, worms
  - auto      when truly unsure (the system will infer from the mesh bbox)

Named-character locomotion rule:
- A named anime/manga/game/comic character or proper-name protagonist doing
  "walk", "run", "jump", "dance" or another body action is creature_organic
  with locomotion=humanoid unless the prompt clearly says animal/quadruped/serpent.
- Never reduce "walking" to vertical bobbing: walking requires articulated
  leg/arm/pelvis motion or the pipeline must report that rigging failed.

Confidence scoring:
- 0.95+ when the description is unambiguous ("RGB strip", "fan 120mm").
- 0.85-0.94 when you're sure but the prompt is brief.
- 0.70-0.84 when there's product-name knowledge involved (you can still
  reason — e.g. "Lian Li Strimer Plus V2" is clearly a cable extension
  with addressable LEDs given the name pattern).
- below 0.70 when truly ambiguous — caller will run a VLM pass on the mesh.

Custom-motion override: if the user appends a free-text instruction like
"fais clignoter en bleu toutes les 200ms" or "rotation lente axe Y", you
MUST reflect it in the chosen *_anim block (override defaults) AND copy
the raw user text into a top-level "custom_motion_text" field."""

CATEGORIES = {
    "led_emission", "fan_pwm", "oled_screen",
    "creature_organic", "mechanical_simple", "rigid_static",
}


def _ollama_chat(model: str, prompt: str, custom_text: str | None,
                 timeout_s: int = 90) -> str:
    user_msg = prompt.strip()
    if custom_text:
        user_msg = f"{user_msg}\n\nUser custom-motion override (verbatim): \"{custom_text.strip()}\""

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "format": "json",   # force un JSON valide (robuste meme pour un modele "thinking")
        "think": False,     # coupe le raisonnement verbeux quand le modele le supporte
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


def _normalize(raw: dict | None, model: str, custom_text: str | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    cat = raw.get("category")
    if cat not in CATEGORIES:
        return None
    intent: dict = {
        "schema": "aurora.motion-intent.v1",
        "category": cat,
        "confidence": _clamp01(raw.get("confidence", 0.7)),
        "rationale": str(raw.get("rationale", ""))[:400],
        "model": model,
    }
    if custom_text:
        intent["custom_motion_text"] = custom_text.strip()[:280]
    elif isinstance(raw.get("custom_motion_text"), str) and raw["custom_motion_text"].strip():
        intent["custom_motion_text"] = raw["custom_motion_text"].strip()[:280]

    if cat == "led_emission":
        c = raw.get("color_anim") or {}
        colors = c.get("colors") if isinstance(c.get("colors"), list) else None
        intent["color_anim"] = {
            "pattern": c.get("pattern") or "rainbow",
            "speed_hz": float(c.get("speed_hz", 1.0)),
            "colors": [str(x) for x in (colors or ["#ff0033", "#33ccff", "#ffaa00"])][:16],
            "emission_strength": float(c.get("emission_strength", 4.0)),
            "led_count": int(c["led_count"]) if isinstance(c.get("led_count"), (int, float)) else None,
        }
    elif cat in ("fan_pwm", "mechanical_simple"):
        m = raw.get("mechanical_anim") or {}
        intent["mechanical_anim"] = {
            "axis": m.get("axis") or "Z",
            "motion_type": m.get("motion_type") or ("rotation" if cat == "fan_pwm" else "oscillation"),
            "rpm": float(m["rpm"]) if isinstance(m.get("rpm"), (int, float)) else (1200.0 if cat == "fan_pwm" else None),
            "amplitude": float(m["amplitude"]) if isinstance(m.get("amplitude"), (int, float)) else None,
            "period_s": float(m["period_s"]) if isinstance(m.get("period_s"), (int, float)) else None,
        }
    elif cat == "oled_screen":
        s = raw.get("screen_anim") or {}
        res = s.get("resolution_px")
        if isinstance(res, list) and len(res) == 2:
            res = [int(res[0]) or 320, int(res[1]) or 240]
        else:
            res = [320, 240]
        intent["screen_anim"] = {
            "content_kind": s.get("content_kind") or "text_scroll",
            "resolution_px": res,
            "frame_rate": float(s.get("frame_rate", 12)),
            "text": s.get("text") if isinstance(s.get("text"), str) else None,
        }
        # iter5.B parity: pass through content_type when present
        if isinstance(s.get("content_type"), str):
            intent["screen_anim"]["content_type"] = s["content_type"]
    elif cat == "creature_organic":
        cr = raw.get("creature_anim") or {}
        intent["creature_anim"] = {
            "base_loop": cr.get("base_loop") or "idle_breathing",
            "bpm": float(cr["bpm"]) if isinstance(cr.get("bpm"), (int, float)) else 14.0,
            "stride_length_m": float(cr["stride_length_m"]) if isinstance(cr.get("stride_length_m"), (int, float)) else None,
        }
        # iter5.A parity: pass through locomotion hint when LLM emits it
        if isinstance(cr.get("locomotion"), str) and cr["locomotion"] in ("humanoid", "quadruped", "serpent", "auto"):
            intent["creature_anim"]["locomotion"] = cr["locomotion"]
    return intent


def _regex_fallback(prompt: str, custom_text: str | None) -> dict:
    p = (prompt or "").lower()
    cat = "rigid_static"
    explicit_locomotion = re.search(
        r"\b(marche|marcher|walk|walks|walking|court|courir|run|runs|running|jog|sprint|danse|dance|dancing|saute|jump|jumping)\b",
        p,
    )
    hard_surface_motion = re.search(
        r"\b(fan|ventilateur|propeller|pwm|rotor|gear|engrenage|hinge|button|bouton|slider|lever|levier|switch|interrupteur|cable|strimer|led|rgb|oled|screen|display)\b",
        p,
    )
    if re.search(r"\b(rgb|argb|led|strimer|neon|chase|rainbow|emissive)\b", p):
        cat = "led_emission"
    elif re.search(r"\b(fan|ventilateur|propeller|h[eé]lice|pwm|rotor)\b", p):
        cat = "fan_pwm"
    elif re.search(r"\b(oled|livedash|screen|[eé]cran|display|dashboard)\b", p):
        cat = "oled_screen"
    elif re.search(r"\b(human|humanoid|character|personnage|monster|monstre|creature|animal|dragon|wolf|loup|anime|manga|fairy\s*tail)\b", p) or (explicit_locomotion and not hard_surface_motion):
        cat = "creature_organic"
    elif re.search(r"\b(hinge|charni[eè]re|button|bouton|slider|lever|levier|switch|interrupteur)\b", p):
        cat = "mechanical_simple"
    intent = {
        "schema": "aurora.motion-intent.v1",
        "category": cat,
        "confidence": 0.82 if cat == "creature_organic" and explicit_locomotion and not hard_surface_motion else 0.0,
        "rationale": "Ollama unreachable - regex fallback",
        "model": "fallback:regex",
    }
    if cat == "led_emission":
        intent["color_anim"] = {"pattern": "rainbow", "speed_hz": 1.0,
                                "colors": ["#ff0044", "#44ff88", "#4488ff"],
                                "emission_strength": 4.0, "led_count": None}
    elif cat == "fan_pwm":
        intent["mechanical_anim"] = {"axis": "Z", "motion_type": "rotation",
                                     "rpm": 1200.0, "amplitude": None, "period_s": None}
    elif cat == "oled_screen":
        intent["screen_anim"] = {"content_kind": "text_scroll", "resolution_px": [320, 240],
                                 "frame_rate": 12.0, "text": None}
    elif cat == "creature_organic":
        if re.search(r"\b(court|courir|run|running|sprint)\b", p):
            base_loop = "run_cycle"
        elif explicit_locomotion:
            base_loop = "walk_cycle"
        else:
            base_loop = "idle_breathing"
        intent["creature_anim"] = {
            "base_loop": base_loop,
            "bpm": 14.0 if base_loop == "idle_breathing" else 96.0,
            "stride_length_m": None,
            "locomotion": "humanoid",
        }
    if custom_text:
        intent["custom_motion_text"] = custom_text.strip()[:280]
    return intent


def classify(prompt: str, custom_text: str | None = None,
             model: str = DEFAULT_MODEL) -> dict:
    if not prompt or not prompt.strip():
        return {
            "schema": "aurora.motion-intent.v1",
            "category": "rigid_static",
            "confidence": 1.0,
            "rationale": "Empty prompt",
            "model": "fallback:empty",
        }
    try:
        text = _ollama_chat(model, prompt, custom_text, timeout_s=90)
        intent = _normalize(_safe_json_extract(text), model, custom_text)
        if intent:
            return intent
        # second-shot with the larger model
        text2 = _ollama_chat(FALLBACK_MODEL, prompt, custom_text, timeout_s=120)
        intent2 = _normalize(_safe_json_extract(text2), FALLBACK_MODEL, custom_text)
        if intent2:
            return intent2
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        pass
    return _regex_fallback(prompt, custom_text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--custom", default=None, help="optional user free-text override")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    out = classify(args.prompt, args.custom, args.model)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
