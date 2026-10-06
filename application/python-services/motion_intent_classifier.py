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
try:  # `gemma3:27b` absent de cette machine -> appel mort, repli silencieux
    from llm_disponible import resoudre_modele as _res_llm
    DEFAULT_MODEL = _res_llm("gemma3:27b", "texte", bavard=False)
except Exception:  # noqa: BLE001
    DEFAULT_MODEL = "gemma3:27b"   # installe, non-thinking -> JSON propre (gemma3:12b n'existe pas ici)
FALLBACK_MODEL = "qwen3:14b"

# Keep this verbatim with the TS service. If you change one, update the other.
SYSTEM_PROMPT = """You are a 3D animation intent classifier for a real-time Blender pipeline.
Given a description of an object or subject, you decide which ONE of thirty-nine
motion primitives the system should bake. You DO NOT have a brand list — you
reason from first principles about what the object actually is and what it
does in real life.

Thirty-nine categories (pick exactly one):

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

7. fluid_flow — the subject is (or prominently features) liquid water in
   motion: fountain, waterfall, poured liquid, flowing stream, rippling
   pool, pond or basin, dripping tap. The system builds a clean procedural
   water surface with morph-target ripples — it never deforms the raw mesh.

8. gas_volume — the subject is (or prominently emits) a gaseous volume:
   smoke, steam, vapour, fog, mist, incense trail, chimney plume. The
   system builds crossed billboard cards with billowing morph targets.

9. cloth_drape — the subject is a flexible sheet that hangs, drapes or waves:
   curtain, flag, banner, cape, veil, tablecloth, sail, tarpaulin, dress or
   robe hanging free, hanging towel. Simulated as real cloth under gravity
   (and wind), then baked as a mesh sequence.

10. rigid_bodies — the subject is one or more SOLID pieces in free motion
    under gravity: falling object, toppling stack, collapsing structure,
    scattering debris, rolling rocks, dominoes, shattering. Solids never
    deform — they fall, hit, bounce and settle.

11. soft_body — the subject is a squishy deformable volume that wobbles or
    squashes without a skeleton: jelly, slime, dough, balloon, cushion,
    mattress, plush toy, fat/flesh jiggle, rubber ball.

12. hair_fur — the motion belongs to fine strands rather than to the body:
    hair, fur, mane, beard, feathers, tassels, wheat field or grass swaying.

13. particles — the motion belongs to a CLOUD of small independent elements:
    sparks, embers, rain, snowfall, dust, floating debris, bubbles, confetti.

14. fracture_debris — the subject BREAKS APART: shattering glass, cracking
    concrete, splintering wood, an exploding crate, a collapsing wall.

15. ocean_surface — a wide body of water with travelling waves: sea, ocean,
    lake surface, swell. Different from fluid_flow, which is a jet or a pour.

16. orbital_motion — bodies revolving at astronomical scale: planets,
    satellites, moons, rings, a star system.

17. articulated_rig — SEVERAL solid parts LINKED by joints that drive each
    other: excavator arm, robot arm, suspension, crane, chain of segments,
    vehicle. Different from mechanical_simple, which has a single joint.

18. rope_net — a rope, cable, chain, hammock or net hanging and swinging.
    Cloth-like, but taut and barely bending.

19. growth — something that GROWS or unfurls over time: plant, tree, vine,
    crystal, coral, mould, expanding foam.

20. chemistry — the MATTER changes without the shape moving: rust spreading,
    oxidation, tarnishing, embers lighting up, freezing over, burning.

21. optics — the subject IS a light phenomenon in glass, water or crystal:
    refraction, caustics, dispersion (rainbow), absorption, prism.

22. smoke_fire — a REAL volumetric simulation of smoke, steam, fire or an
    explosion (as opposed to gas_volume, which fakes it with flat cards).

23. granular — a MATERIAL made of many grains that pours and piles: sand,
    snow, soil, gravel, powder, rice, coffee beans.

24. thermal_melt — the subject MELTS into a puddle, or a puddle solidifies:
    melting ice/wax/metal/chocolate, freezing, lava cooling.

25. plasma — glowing electrical energy: plasma, lightning arc, energy field,
    electric aura, magic bolt, lightning bolt.

26. vortex_tornado — air or debris spinning in a rising funnel: tornado,
    whirlwind, vortex, cyclone, dust devil, whirlpool.

27. buoyancy_float — the subject FLOATS and bobs on water: boat, buoy, raft,
    duck on a pond, floating barrel, drifting on the sea.

28. swarm_flock — MANY small living agents flying/swimming together as one
    cloud: bee swarm, bird flock, fish school, butterfly cloud, bats.

29. wind_sway — vegetation or a slender object swaying in the wind, base
    anchored: tree, grass, wheat field, leaves trembling, lamppost in a storm.

30. periodic_locomotion — NON-humanoid rhythmic locomotion: bird or butterfly
    flapping wings, fish swimming (travelling body wave), snake slithering.

31. levitation — hovering in the air: drone, ghost, magic crystal, UFO,
    floating island. Gentle vertical bob + slow spin.

32. oscillation — pendulum, clock balance, spring bouncing, spinning top with
    precession. Damped analytic swing, pivot at the top.

33. shockwave — an impact ring / shockwave expanding from the subject.

34. muscle_tissue — flesh/muscle/fat jiggle ON a body (anchored to the bone),
    or a volumetric jelly splat. Uses a tetrahedral Vellum solve — different
    from soft_body (whole-object wobble, surface springs only).

35. dissolve_teleport — the subject disintegrates into dust / teleports away
    or materializes: "il se desintegre", "effet Thanos", "apparition magique".

36. trail_wake — the subject moves and leaves a trail/wake behind it: boat
    wake, light trail, condensation trail.

37. ground_traces — footprints or tracks appearing in the ground as the
    subject passes: "des pas dans la neige", "traces de pneus dans la boue".

38. accumulation — a layer progressively covers the subject: snow settling,
    dust or ash build-up.

39. morphing — the subject transforms into another shape: "le vase devient
    une sphere", "il se transforme en cube".

Output ONLY a JSON object, no markdown, no commentary. Schema:

{
  "schema": "aurora.motion-intent.v1",
  "category": "<one of the 39 above>",
  "confidence": <0.0-1.0 — how sure you are>,
  "rationale": "<one sentence explaining your reasoning>",
  "color_anim":     { "pattern": "chase|rainbow|breathing|pulse|static_color",
                      "speed_hz": <number>, "colors": ["#hex",…],
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
                      "locomotion": "humanoid|quadruped|serpent|auto" },
  "fluid_anim":     { "flow_type": "fountain|pour|waterfall|ripple|still",
                      "wave_amplitude": <0.0-1.0>, "loop_s": <number>,
                      "droplets": <bool> },
  "gas_anim":       { "kind": "smoke|steam|fog", "rise_speed": <number>,
                      "billow_amplitude": <number> },
  "cloth_anim":     { "pinning": "top_edge|corners|top_corners|none|auto",
                      "stiffness": <0.0-1.0>, "wind": <0.0-1.0>,
                      "loop_s": <number> },
  "rigid_anim":     { "event": "fall|topple|collapse|scatter|roll",
                      "drop_height_m": <number>, "pieces": <int?>,
                      "bounciness": <0.0-1.0>, "duration_s": <number> },
  "soft_anim":      { "trigger": "drop|squash|jiggle", "softness": <0.0-1.0>,
                      "bounce": <0.0-1.0>, "duration_s": <number> },
  "hair_anim":      { "kind": "hair|fur|mane|feathers|grass",
                      "length_m": <number>, "wind": <0.0-1.0>,
                      "loop_s": <number> },
  "particle_anim":  { "kind": "sparks|debris|rain|snow|dust",
                      "count": <int>, "spread": <0.0-3.0>,
                      "duration_s": <number> },
  "fracture_anim":  { "pieces": <int 2-40>, "bounciness": <0.0-1.0>,
                      "duration_s": <number> },
  "ocean_anim":     { "wave_scale": <number>, "choppiness": <0.0-4.0>,
                      "wind_speed": <number>, "loop_s": <number> },
  "orbital_anim":   { "bodies": <int 1-12>, "period_s": <number>,
                      "eccentricity": <0.0-0.8>, "tilt_deg": <number> },
  "articulated_anim": { "segments": <int 2-12>, "joint": "hinge|point",
                        "duration_s": <number> },
  "rope_anim":      { "slack": <0.0-1.0>, "wind": <0.0-1.0>,
                      "loop_s": <number> },
  "growth_anim":    { "start_ratio": <0.0-0.9>, "sway": <0.0-1.0>,
                      "duration_s": <number> },
  "chemistry_anim": { "reaction": "corrosion|oxydation|combustion|gel",
                      "duration_s": <number> },
  "optics_anim":    { "ior": <number 1.0-2.5>, "dispersion": <0.0-1.0>,
                      "absorption": <0.0-1.0>, "loop_s": <number> },
  "gas_anim_real":  { "kind": "smoke|steam|fire|explosion",
                      "resolution": <int 24-96>, "duration_s": <number> },
  "granular_anim":  { "grains": <int 20-400>, "duration_s": <number> },
  "thermal_anim":   { "sens": "fonte|solidification", "duration_s": <number> },
  "plasma_anim":    { "duration_s": <number> },
  "vortex_anim":    { "count": <int 30-300>, "duration_s": <number> },
  "buoyancy_anim":  { "swell": <0.0-1.0>, "loop_s": <number> },
  "swarm_anim":     { "count": <int 20-150>, "duration_s": <number> },
  "wind_anim":      { "force": <0.0-1.0>, "loop_s": <number> },
  "locomotion_anim": { "kind": "wings|swim|slither", "beats": <number>,
                       "loop_s": <number> },
  "levitation_anim": { "hover": <0.0-1.0>, "spin_turns": <number>,
                       "loop_s": <number> },
  "oscillation_anim": { "kind": "pendulum|spring|top", "angle_deg": <number>,
                        "damping": <0.0-1.0>, "cycles": <number>,
                        "duration_s": <number> },
  "shockwave_anim": { "reach": <number>, "duration_s": <number> },
  "muscle_anim":    { "mode": "jiggle|splat", "duration_s": <number> },
  "dissolve_anim":  { "sens": "disparition|apparition", "duration_s": <number> },
  "trail_anim":     { "travel_m": <number>, "duration_s": <number> },
  "traces_anim":    { "depth": <0.0-1.0>, "duration_s": <number> },
  "accumulation_anim": { "thickness": <0.0-1.0>, "duration_s": <number> },
  "morph_anim":     { "target": "sphere|cube", "duration_s": <number> }
}

Include ONLY the *_anim block matching the category you chose. Omit the
others. For rigid_static, include none of the blocks.

Reasoning checklist before answering:
- Is the subject alive or articulated as a creature? → creature_organic.
- Does it spin in normal operation around a single axis? → fan_pwm.
- Does it display dynamic text/icons on an embedded screen? → oled_screen.
- Does it have integrated programmable LEDs whose colour changes? → led_emission.
- Does it have a single-DoF moving part (hinge/button/slider)? → mechanical_simple.
- Is it liquid water in motion (fountain, waterfall, pour, ripple)? → fluid_flow.
- Is it smoke, steam, vapour, fog or mist? → gas_volume.
- Is it a hanging/waving sheet of fabric? → cloth_drape.
- Do solid pieces fall, topple, collapse, scatter or shatter? → rigid_bodies.
- Is it a squishy volume that wobbles without a skeleton? → soft_body.
- Does the motion belong to strands (hair, fur, feathers, grass)? → hair_fur.
- Is it a cloud of small independent elements (sparks, rain, snow, dust)? → particles.
- Does the subject break apart into pieces? → fracture_debris.
- Is it a wide water surface with travelling waves? → ocean_surface.
- Do bodies revolve at astronomical scale? → orbital_motion.
- Are several solid parts LINKED by joints driving each other? → articulated_rig.
- Is it a rope, cable, chain or net hanging? → rope_net.
- Does something grow or unfurl over time? → growth.
- Does the MATTER change (rust, burn, freeze) without the shape moving? → chemistry.
- Is it a material of many grains (sand, snow, gravel) pouring/piling? → granular.
- Does the subject melt into a puddle or a puddle solidify? → thermal_melt.
- Is it glowing electrical energy (plasma, lightning, energy field)? → plasma.
- Is it air/debris spinning in a rising funnel (tornado, vortex)? → vortex_tornado.
- Does the subject float and bob on water (boat, buoy, raft)? → buoyancy_float.
- Are MANY small creatures moving as one cloud (swarm, flock, school)? → swarm_flock.
- Is it vegetation swaying in the wind, base anchored? → wind_sway.
- Is it wingbeat / fish swim / snake slither (rhythmic, non-humanoid)? → periodic_locomotion.
- Does it hover in the air (drone, ghost, magic object)? → levitation.
- Is it a pendulum, spring or spinning top? → oscillation.
- Is it an expanding impact ring? → shockwave.
- Is it flesh/muscle jiggle on a body, or a volumetric jelly? → muscle_tissue.
- Does the subject disintegrate/teleport/materialize? → dissolve_teleport.
- Does it leave a trail or wake behind while moving? → trail_wake.
- Do footprints/tracks appear in the ground as it passes? → ground_traces.
- Does a layer (snow, dust) progressively cover it? → accumulation.
- Does it transform into another shape? → morphing.
- Otherwise (and especially if it's plain inert hardware): rigid_static.

Boundary rules that matter (these are the ones people get wrong):
- A CREATURE whose hair or cape also moves is still creature_organic: the body
  drives the shot. Choose cloth_drape / hair_fur only when the fabric or the
  strands ARE the subject.
- Something that FALLS but does not deform is rigid_bodies, never soft_body.
- Something that deforms but keeps its volume and has no bones is soft_body,
  never creature_organic.
- Fabric already worn and moving WITH a walking body is creature_organic.

When you choose oled_screen, ALSO choose a content_type:
  - text_scroll    if the screen scrolls a marquee/string
  - icon_rotation  if it cycles through icons (CPU, RAM, FAN, GPU)
  - system_stats   if it shows live numbers (temp/percent/RPM) — typical for LiveDash
  - mixed          if it alternates several modes
When you choose creature_organic, ALSO choose locomotion:
  - humanoid  for biped humans / humanoid robots
  - quadruped for animals on 4 legs (dog, dragon, lion, wolf)
  - serpent   for snakes, eels, worms
  - auto      when truly unsure (the system will infer from the mesh bbox)
When you choose fluid_flow, ALSO choose a flow_type:
  - fountain   for a vertical jet or spray (fountain, geyser, sprinkler)
  - pour       for liquid poured from a container (bottle, teapot, tap)
  - waterfall  for a falling sheet of water (waterfall, cascade, dam)
  - ripple     for a mostly-flat surface with waves (pool, pond, lake, basin)
  - still      for calm liquid with barely visible motion
  wave_amplitude is 0.0-1.0 (0.1 calm … 0.8 agitated), loop_s is the loop
  duration in seconds (2-6 typical), droplets=true only for fountain/waterfall.
When you choose gas_volume, ALSO choose a kind:
  - smoke  for combustion smoke (fire, chimney, incense, exhaust)
  - steam  for hot water vapour (kettle, coffee, cooking pot, sauna)
  - fog    for ambient mist/fog/haze hugging the ground
  rise_speed is in metres per second (0.1 slow fog … 1.0 fast steam),
  billow_amplitude is 0.0-1.0 (how much the volume swells as it rises).
When you choose cloth_drape, ALSO choose a pinning:
  - top_edge     for curtains, banners and tapestries hung along a rail
  - top_corners  for a flag or a sail held at two points
  - corners      for a cloth held at its four corners
  - none         for fabric simply dropped onto the ground
  - auto         when unsure (the system pins the highest edge of the mesh)
  stiffness 0.0 = silk … 1.0 = leather; wind 0.0 = indoors … 1.0 = gale.
When you choose rigid_bodies, ALSO choose an event:
  - fall     a single object dropped onto the ground
  - topple   a standing object tipping over
  - collapse a stack or structure caving in
  - scatter  many pieces bursting apart
  - roll     rounded pieces rolling down
  drop_height_m is the starting height in metres (0.2 … 5), bounciness
  0.0 = clay … 1.0 = rubber ball. pieces only for collapse/scatter.
When you choose soft_body, ALSO choose a trigger:
  - drop   the body falls and squashes on impact
  - squash the body is compressed then recovers
  - jiggle the body wobbles in place
  softness 0.0 = firm rubber … 1.0 = liquid jelly.
When you choose hair_fur, ALSO choose a kind:
  - hair / mane / fur / feathers / grass
  length_m is the strand length in metres (0.02 fur … 0.6 long hair).

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
    "fluid_flow", "gas_volume",
    # Domaines physiques que Blender sait faire depuis toujours et qui
    # n'etaient branches nulle part: tissu, corps rigides en chute/collision,
    # corps mou, et les brins (cheveux, fourrure, plumes, herbe).
    "cloth_drape", "rigid_bodies", "soft_body", "hair_fur",
    # 2e vague: particules, fracture/destruction, etendues d'eau, orbites.
    "particles", "fracture_debris", "ocean_surface", "orbital_motion",
    # 3e vague: mecanismes relies, cordages, croissance, chimie visible.
    "articulated_rig", "rope_net", "growth", "chemistry",
    # 4e vague — voie RENDU: ce que le GLB ne sait pas porter.
    "optics", "smoke_fire",
    # 5e vague: granulaires, thermique, plasma.
    "granular", "thermal_melt", "plasma",
    # 6e vague: vortex, flottaison, essaim.
    "vortex_tornado", "buoyancy_float", "swarm_flock",
    # 7e vague: vent-vegetation, locomotion periodique, levitation,
    # oscillation, onde de choc, biomecanique Vellum.
    "wind_sway", "periodic_locomotion", "levitation", "oscillation",
    "shockwave", "muscle_tissue",
    # 8e vague: effets de transformation et de passage.
    "dissolve_teleport", "trail_wake", "ground_traces", "accumulation",
    "morphing",
}

FLOW_TYPES = ("fountain", "pour", "waterfall", "ripple", "still")
GAS_KINDS = ("smoke", "steam", "fog")
CLOTH_PINNINGS = ("top_edge", "top_corners", "corners", "none", "auto")
RIGID_EVENTS = ("fall", "topple", "collapse", "scatter", "roll")
SOFT_TRIGGERS = ("drop", "squash", "jiggle")
HAIR_KINDS = ("hair", "fur", "mane", "feathers", "grass")


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
        # A JSON object alone allowed replies such as {"fan_pwm": {...}},
        # silently rejected by _normalize. Decode the required intent fields.
        "format": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": sorted(CATEGORIES)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
            "required": ["category", "confidence", "rationale"],
            "additionalProperties": True,
        },
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
    elif cat == "fluid_flow":
        fl = raw.get("fluid_anim") or {}
        flow_type = fl.get("flow_type") if fl.get("flow_type") in FLOW_TYPES else "ripple"
        loop_s = float(fl["loop_s"]) if isinstance(fl.get("loop_s"), (int, float)) and float(fl["loop_s"]) > 0 else 3.0
        intent["fluid_anim"] = {
            "flow_type": flow_type,
            "wave_amplitude": _clamp01(fl.get("wave_amplitude", 0.35)),
            "loop_s": max(0.5, min(12.0, loop_s)),
            "droplets": bool(fl["droplets"]) if isinstance(fl.get("droplets"), bool) else flow_type in ("fountain", "waterfall"),
        }
    elif cat == "gas_volume":
        g = raw.get("gas_anim") or {}
        rise = float(g["rise_speed"]) if isinstance(g.get("rise_speed"), (int, float)) and float(g["rise_speed"]) > 0 else 0.3
        intent["gas_anim"] = {
            "kind": g.get("kind") if g.get("kind") in GAS_KINDS else "smoke",
            "rise_speed": max(0.02, min(3.0, rise)),
            "billow_amplitude": _clamp01(g.get("billow_amplitude", 0.5)),
        }
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
    elif re.search(r"\b(fum[eé]e|smoke|vapeur|steam|brume|brouillard|fog|mist)\b", p):
        cat = "gas_volume"
    elif re.search(r"\b(eau|water|fontaine|fountain|cascade|waterfall|coule|couler|vers[eé]e?|liquide|liquid|ripple|ondulations?)\b", p):
        cat = "fluid_flow"
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
    elif cat == "fluid_flow":
        if re.search(r"\b(fontaine|fountain|geyser|jet)\b", p):
            flow_type = "fountain"
        elif re.search(r"\b(cascade|waterfall|chute)\b", p):
            flow_type = "waterfall"
        elif re.search(r"\b(vers[eé]e?|pouring|poured)\b", p):
            flow_type = "pour"
        else:
            flow_type = "ripple"
        intent["fluid_anim"] = {
            "flow_type": flow_type,
            "wave_amplitude": 0.35,
            "loop_s": 3.0,
            "droplets": flow_type in ("fountain", "waterfall"),
        }
    elif cat == "gas_volume":
        if re.search(r"\b(vapeur|steam)\b", p):
            gas_kind = "steam"
        elif re.search(r"\b(brume|brouillard|fog|mist)\b", p):
            gas_kind = "fog"
        else:
            gas_kind = "smoke"
        intent["gas_anim"] = {
            "kind": gas_kind,
            "rise_speed": 0.15 if gas_kind == "fog" else 0.3,
            "billow_amplitude": 0.5,
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
