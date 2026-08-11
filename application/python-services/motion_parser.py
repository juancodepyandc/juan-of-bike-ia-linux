"""motion_parser — Python mirror of TS parseCustomMotionPrompt.

Lets the bridge validate prompts directly without spinning up the Vite
bundle. The TS parser in src/services/kinematicsLibrary.ts remains the
authoritative source for the orchestrator and FLUX prompt builder; this
module reproduces ONLY the verb-matching + modifier detection layer so a
curl from the tunnel can answer "what would parseCustomMotionPrompt do
with this prompt?" without a browser.

Tracking discipline: when a verb regex / modifier rule is added in the
TS file, mirror it here in the same commit. The self-test guards against
divergence by exercising the same fixtures both sides agree on.

Pure: stdlib only, no bpy / no flask / no requests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
#  VERB REGEXES (mirror of VERB_TO_PRESET in kinematicsLibrary.ts)
#  Order matters — first match wins per segment.
# ---------------------------------------------------------------------------

VERB_TO_PRESET: List[Tuple[re.Pattern, str]] = [
    # v80u — vocabulary expansion: each existing regex picks up 3-5 natural-
    # language synonyms (déambule, flâne, pirouette, se baisse, etc.). Plus
    # 2 newly-wired verbs for quadruped_idle and quadruped_jump.
    # MIRROR of kinematicsLibrary.ts VERB_TO_PRESET — keep both in lockstep.
    (re.compile(r"\b(roue|cartwheel|handspring|salto|backflip|frontflip|aerial)\b", re.I), "character.cartwheel"),
    (re.compile(r"\b(salue|salut\b|wave|waves|waving|saluer|fait coucou|coucou|signe de la main|hi-five|high five)\b", re.I), "character.wave"),
    (re.compile(r"\b(salut militaire|formal salute|garde a vous|garde-a-vous|attention salute)\b", re.I), "character.salute"),
    (re.compile(r"\b(applaudis(?:s|t)?|applaudit|applaud|clap|clapping|claps|claque des mains|tape des mains|ovation|cheer|cheers|cheering)\b", re.I), "character.applaud"),
    (re.compile(r"\b(s incline|s'incline|s incliner|bow|bows|bowing|reverence|r[eé]v[eé]rence|courber|courbure|incliner)\b", re.I), "character.bow"),
    # v80u: quadruped_jump must precede character.jump to win on "four-legged jump" / "chien qui saute"
    (re.compile(r"\b(quadruped(?:e)? saute|quadruped jump|four-legged leap|chien qui saute|cat jumping|saut quadrupede)\b", re.I), "creature.quadruped_jump"),
    (re.compile(r"\b(saute|sauter|jump|jumping|jumps|leap|leaps|leaping|bond|bondis|bondit|hop|hops|hopping|spring|springs|springing)\b", re.I), "character.jump"),
    # ATTAQUER / FRAPPER / SE BATTRE. Les gestes existaient (punch, kick, block,
    # parry...) mais aucun verbe francais courant n'y menait: "il attaque",
    # "il frappe", "il se bat" rendaient null. On les rattache au geste offensif
    # le plus proche plutot que de ne rien produire.
    (re.compile(r"\b(coup de pied|kick|kicks|kicking|donne un coup de pied|footstrike|round[\s-]?house|coup de tatane|balaie|balayage)\b", re.I), "character.kick"),
    (re.compile(r"\b(attaque|attaquer|attaquant|assaut|assaillir|assaille|offensive|"
                r"frappe|frapper|frappant|cogne|cogner|ass[eè]ne|assener|percute|percuter|"
                r"se bat|se battre|combat|combattre|combattant|bagarre|duel|"
                r"affronte|affronter|riposte|riposter|contre[- ]attaque|"
                r"attack|attacks|attacking|strike|strikes|striking|fight|fights|fighting)\b",
                re.I), "character.punch"),
    (re.compile(r"\b(coup de poing|punch|punches|punching|jab|cross|hook|uppercut|donne un coup de poing|frappe du poing)\b", re.I), "character.punch"),
    (re.compile(r"\b(s assoit|s'assoit|s asseoit|assis|assoit|sit|sits|sitting|seated|s installer|prend place|takes a seat)\b", re.I), "character.sit"),
    (re.compile(r"\b(s agenouille|s'agenouille|agenouille|kneel|kneeling|kneels|se baisse|s accroupit|accroupi|crouch|crouches|crouching|squat|squats|squatting)\b", re.I), "character.kneel"),
    (re.compile(r"\b(rampe|ramper|crawl|crawls|crawling|se tra[iî]ne|se traine|sur le ventre|prone crawl)\b", re.I), "character.crawl"),
    (re.compile(r"\b(nage|nager|swim|swims|swimming|crawl natation|brasse|breaststroke|freestyle swimming)\b", re.I), "character.swim"),
    (re.compile(r"\b(court|courir|run|runs|running|jog|jogs|jogging|sprint|sprints|sprinting|fonce|file|file en courant)\b", re.I), "character.run_cycle"),
    (re.compile(r"\b(marche|marcher|walk|walks|walking|d[eé]ambule|d[eé]ambuler|fl[âa]ne|fl[âa]ner|stroll|strolls|strolling|saunter|saunters|sauntering|amble|ambles|ambling|prom[eè]ne|promener|stride|strides|striding)\b", re.I), "character.walk_cycle"),
    (re.compile(r"\b(danse|danser|dance|dances|dancing|groove|grooves|grooving|boogie|boogies)\b", re.I), "character.dance_default"),
    (re.compile(r"\b(lance|lancer|throw|throws|throwing|pitch|pitches|pitching|hurl|hurls|hurling|toss|tosses|tossing)\b", re.I), "character.throw"),
    (re.compile(r"\b(tombe|tomber|fall|falls|falling|chute|s effondre|s'effondre|trip|trips|tripping|stumble|stumbles)\b", re.I), "character.fall"),
    # v80u: quadruped_idle must precede character.idle to win on "four-legged idle"
    (re.compile(r"\b(quadruped(?:e)? au repos|quadruped idle|four-legged idle|quadruped resting|chien assis tranquille|cat resting)\b", re.I), "creature.quadruped_idle"),
    (re.compile(r"\b(idle|repos|au repos|stand idle|inactif|au calme|sans bouger|stationary|breathe|breathes|breathing|respire|respirer|attente)\b", re.I), "character.idle"),
    (re.compile(r"\b(bloque|bloquer|block|blocking|blocks|garde|guard|guards|defend|defends|defending|protege|prot[eé]ger)\b", re.I), "character.block"),
    (re.compile(r"\b(pare|parer|parade|parry|parries|parrying|deflect|deflects|deflecting|deviation|d[eé]viation|repousse|repousser)\b", re.I), "character.parry"),
    (re.compile(r"\b(esquive|esquiver|dodge|dodges|dodging|sidestep|sidesteps|side-step|evade|evades|evading|fait un pas de cot[eé])\b", re.I), "character.dodge"),
    (re.compile(r"\b(roulade|combat roll|forward roll|tumble|tumbles|tumbling|fait une roulade|barrel roll)\b", re.I), "character.combat_roll"),
    (re.compile(r"\b(pousse|pousser|push|pushes|pushing|shoves?|shoving|repousse|repousser|bouscule)\b", re.I), "character.push"),
    (re.compile(r"\b(tire|tirer|pull|pulls|pulling|drag|drags|dragging|tracte|tracter|hauls?|hauling)\b", re.I), "character.pull"),
    (re.compile(r"\b(saisit|saisir|grab|grabs|grabbing|grasp|grasps|grasping|attrape|attraper|catches|catching|empoigne|empoigner|ramasse|ramasser|pick(?:s|ed)? up|picks up)\b", re.I), "character.grab"),
    (re.compile(r"\b(souleve|soulever|lift|lifts|lifting|hoist|hoists|hoisting|raises an object|porte|porter|carries an object)\b", re.I), "character.lift"),
    # v80v: 2 new character presets (climb, spin/pirouette)
    (re.compile(r"\b(grimpe|grimper|escalade|escalader|climb|climbs|climbing|scale|scaling|monter en escalade)\b", re.I), "character.climb"),
    (re.compile(r"\b(pirouette|pirouettes|tourne sur (?:lui|elle)[\s-]m[eê]me|spins?\s+on\s+the\s+spot|spin\s+in\s+place|tournoiement|whirls?|twirls?|twirling|tourbillonne)\b", re.I), "character.spin"),
    # Creature
    (re.compile(r"\b(vole|voler|fly|flying|flies|battement d ailes|battement d'ailes|plane|planes|planing|soar|soars|soaring)\b", re.I), "creature.flap_fly"),
    (re.compile(r"\b(serpente|slither|slithers|slithering|onduler|ondule|ondulant|wriggle|wriggles|wriggling|squirm|squirms)\b", re.I), "creature.slither"),
    (re.compile(r"\b(rode|r[oô]der|rodeur|prowl|prowling|stalk|stalking|sneak|sneaks|sneaking|creep|creeps|creeping)\b", re.I), "creature.prowl"),
    # Quadruped (v77zt + v80u)
    # "il charge l'ennemi" rendait creature.quadruped_run: un humain se
    # retrouvait a courir a quatre pattes. Les tournures explicitement humaines
    # passent donc AVANT la regle de galop.
    (re.compile(r"\b(se rue|se ruer|se pr[eé]cipite|se pr[eé]cipiter|fonce sur|"
                r"charge (?:l|vers|sur|contre)|charges? (?:at|towards|into))", re.I),
     "character.run_cycle"),
    (re.compile(r"\b(galop|galope|galoper|gallop|galloping|gallops|charge|charges|charging|fonce a quatre pattes)\b", re.I), "creature.quadruped_run"),
    (re.compile(r"\b(trotte|trotter|trot|trotting|trots|amble quadrupede|patte par patte)\b", re.I), "creature.quadruped_walk"),
    (re.compile(r"\b(remue queue|remuer la queue|wag tail|tail wag|wagging|tail wagging|fr[eé]tille|fretille la queue)\b", re.I), "creature.tail_wag"),
    # v80v: creature roar
    (re.compile(r"\b(rugit|rugir|roar|roars|roaring|bellows?|bellowing|growl|growls|growling|grogne|gronde)\b", re.I), "creature.roar"),
    (re.compile(r"\b(quadrupede|quadruped|on all fours|a quatre pattes|four-legged|four legged)\b", re.I), "creature.quadruped_walk"),
    # v80u: orphan-preset wirings — moved earlier in this list so they win
    # over the generic character.idle / character.jump regexes.
    # Mechanism
    (re.compile(r"\b(engrenages? (?:qui )?tourne(?:nt)?|engrenage qui tourner|gear (?:mesh|rotation|rotates|rotating|spinning)|engrenage en rotation)\b", re.I), "mechanism.gear_mesh_rotate"),
    (re.compile(r"\b(courroie en (?:marche|fonctionnement|boucle)|belt running|belt loop)\b", re.I), "mechanism.belt_loop"),
    (re.compile(r"\b(verin|piston (?:en |)course|cylinder stroke|actuator stroke)\b", re.I), "mechanism.piston_stroke"),
    (re.compile(r"\b(charniere qui (?:s ouvre|s'ouvre|bat)|hinge swing|hinge swinging)\b", re.I), "mechanism.hinge_swing"),
    (re.compile(r"\b(tringlerie|four-bar|linkage cycle|articulation a quatre barres)\b", re.I), "mechanism.linkage_cycle"),
    # v80v: machinery vibration
    (re.compile(r"\b(vibre|vibrer|vibrates?|vibrating|buzz|buzzing|buzzes|hums?|humming|trepide|tr[eé]pide)\b", re.I), "mechanism.vibrate"),
    # Generic rotation fallback (v79o) — catches "tourne lentement", "spinning",
    # "rotates", etc. Routes to gear_mesh_rotate which produces clean Y-axis
    # rotation. Keeps the TS regex in kinematicsLibrary.ts in lock-step.
    (re.compile(r"\b(tournoie|tournoient|spins?|spinning|spin (?:slowly|quickly|fast)|rotates?|rotating|gyrates?|gyrating|rotation continue|continuous rotation|tourne(?:nt)? (?:lentement|doucement|rapidement|sur (?:lui|elle|eux|elles)[\s-]m[eê]me|en place|sur place))\b", re.I), "mechanism.gear_mesh_rotate"),
    # Vehicle
    (re.compile(r"\b(roule|rouler|drive forward|rolling forward)\b", re.I), "vehicle.roll_forward"),
    (re.compile(r"\b(vol stationnaire|hover|hovering)\b", re.I), "vehicle.hover"),
]


# ---------------------------------------------------------------------------
#  MODIFIER REGEXES (mirror of MODIFIER_RULES in kinematicsLibrary.ts)
# ---------------------------------------------------------------------------

ModifierEffect = Dict[str, Any]

MODIFIER_RULES: List[Tuple[re.Pattern, ModifierEffect]] = [
    # Speed
    (re.compile(r"\b(rapidement|vite|fast|quickly|speedily|swiftly|hate(?:ment)?|en vitesse|au galop|ultra rapide|tres vite)\b", re.I),
     {"speedMul": 1.6, "matched": "speed_fast"}),
    (re.compile(r"\b(extremement vite|extr[eê]mement vite|tres rapidement|frenetiquement|fr[eé]n[eé]tiquement|frantically)\b", re.I),
     {"speedMul": 2.2, "matched": "speed_very_fast"}),
    (re.compile(r"\b(lentement|doucement|slowly|leisurely|tranquillement|au ralenti|in slow motion|posement|pos[eé]ment)\b", re.I),
     {"speedMul": 0.6, "matched": "speed_slow"}),
    (re.compile(r"\b(tres lentement|tr[eè]s lentement|extremely slowly|au ralenti extreme)\b", re.I),
     {"speedMul": 0.35, "matched": "speed_very_slow"}),
    # Intensity
    (re.compile(r"\b(fort(?:ement)?|intensement|intens[eé]ment|intense|hard|powerfully|vigoureusement|vigoroso|brutalement|avec force)\b", re.I),
     {"amplitudeMul": 1.4, "matched": "intensity_high"}),
    (re.compile(r"\b(violemment|tres fort|tr[eè]s fort|with full force|de toutes ses forces|enormous force)\b", re.I),
     {"amplitudeMul": 1.8, "matched": "intensity_very_high"}),
    (re.compile(r"\b(legerement|l[eé]g[eè]rement|gently|softly|delicatement|d[eé]licatement|a peine|barely|subtilement|en finesse)\b", re.I),
     {"amplitudeMul": 0.65, "matched": "intensity_low"}),
    (re.compile(r"\b(a peine perceptible|imperceptiblement|microscopiquement|microscopically)\b", re.I),
     {"amplitudeMul": 0.35, "matched": "intensity_very_low"}),
    # Emotion
    (re.compile(r"\b(joyeusement|happily|cheerfully|content(?:ement)?|gaiement|allegrement|all[eé]grement|enjoue|enjou[eé])\b", re.I),
     {"speedMul": 1.15, "amplitudeMul": 1.15, "emotion": "happy", "matched": "emotion_happy"}),
    (re.compile(r"\b(tristement|sadly|melancoliquement|m[eé]lancoliquement|abattu|d[eé]courag[eé]|d[eé]prim[eé])\b", re.I),
     {"speedMul": 0.7, "amplitudeMul": 0.85, "emotion": "sad", "matched": "emotion_sad"}),
    (re.compile(r"\b(en colere|angrily|fiercement|furieusement|aggressivement|agressivement|rageusement|hargneusement)\b", re.I),
     {"speedMul": 1.3, "amplitudeMul": 1.5, "emotion": "angry", "matched": "emotion_angry"}),
    (re.compile(r"\b(fatigue|fatigu[eé]|tired|exhausted|epuise|[eé]puis[eé]|las(?:sement)?|sans energie)\b", re.I),
     {"speedMul": 0.55, "amplitudeMul": 0.7, "emotion": "tired", "matched": "emotion_tired"}),
    # v77zaa: SPATIAL — height / distance / direction
    (re.compile(r"\b(haut|high|vers le haut|upward|en hauteur|sky high|en l air|en l'air)\b", re.I),
     {"heightMul": 1.6, "direction": "up", "matched": "spatial_high"}),
    (re.compile(r"\b(tres haut|tr[eè]s haut|very high|extremement haut|extr[eê]mement haut)\b", re.I),
     {"heightMul": 2.2, "direction": "up", "matched": "spatial_very_high"}),
    (re.compile(r"\b(bas|low|au sol|ground level|ras du sol|vers le bas|downward|en plongee)\b", re.I),
     {"heightMul": 0.5, "direction": "down", "matched": "spatial_low"}),
    (re.compile(r"\b(loin|far|au loin|distant|sur une longue distance|long range|tres loin|tr[eè]s loin|very far)\b", re.I),
     {"distanceMul": 1.7, "direction": "forward", "matched": "spatial_far"}),
    (re.compile(r"\b(pres|close|just there|courte distance|short range|tout pres)\b", re.I),
     {"distanceMul": 0.55, "matched": "spatial_close"}),
    (re.compile(r"\b(vers la gauche|to the left|gauche|leftward|on the left side)\b", re.I),
     {"direction": "left", "matched": "spatial_left"}),
    (re.compile(r"\b(vers la droite|to the right|droite|rightward|on the right side)\b", re.I),
     {"direction": "right", "matched": "spatial_right"}),
    (re.compile(r"\b(en arriere|en arri[eè]re|backward|behind|en recul|en reculant)\b", re.I),
     {"distanceMul": 0.8, "direction": "backward", "matched": "spatial_backward"}),
    (re.compile(r"\b(en avant|forward|toward|vers l avant|en se rapprochant)\b", re.I),
     {"direction": "forward", "matched": "spatial_forward"}),
]


# ---------------------------------------------------------------------------
#  SUBJECT-CONSTRAINED PRESET RESOLUTION
# ---------------------------------------------------------------------------
# The verb table alone is subject-BLIND: "le loup marche" matched
# character.walk_cycle, a bipedal preset whose primitives target `legs`
# (DEF-thigh/shin/foot) and `arms` (hand_ik.*). rigify_autorig.py, meanwhile,
# builds a WOLF metarig for a quadruped/creature subject — a rig that has no
# hand_ik and no upper_arm at all, and whose front limbs are front_thigh_fk /
# front_shin_fk. The animal therefore walked on its hind legs with its front
# legs frozen, and nothing reported an error.
#
# The invariant enforced here: THE PRESET FAMILY MUST MATCH THE METARIG FAMILY.
# We reuse the exact same predicate rigify_autorig is driven by
# (aurora_3d_pipeline: metarig_family = "quadruped" if kind in
# ("quadruped", "creature") else "human") so the preset and the skeleton can
# never disagree again.
#
# Only presets with a real quadruped counterpart are remapped. A gesture with
# no four-legged equivalent (punch, wave, ...) is left untouched rather than
# invented — MIRROR of kinematicsLibrary.ts QUADRUPED_PRESET_FOR.

QUADRUPED_PRESET_FOR: Dict[str, str] = {
    "character.walk_cycle": "creature.quadruped_walk",
    "character.run_cycle": "creature.quadruped_run",
    "character.idle": "creature.quadruped_idle",
    "character.jump": "creature.quadruped_jump",
}

_QUADRUPED_KINDS = frozenset({"quadruped", "creature"})


def is_quadruped_subject(subject_kind: Optional[str]) -> bool:
    """True when this subject will be rigged on the quadruped (wolf) metarig."""
    return str(subject_kind or "").strip().lower() in _QUADRUPED_KINDS


def resolve_preset_for_subject(preset_id: Optional[str],
                               subject_kind: Optional[str]) -> Optional[str]:
    """Constrain a verb-matched preset by the subject's morphology."""
    if not preset_id or not is_quadruped_subject(subject_kind):
        return preset_id
    return QUADRUPED_PRESET_FOR.get(preset_id, preset_id)


SEQUENCE_SEPARATOR_RX = re.compile(
    r"\s+(?:puis|then|et\s+ensuite|et\s+apres|et\s+apr[eè]s|after\s+that|next|ensuite|et\s+puis|and\s+then)\s+",
    re.I,
)
PARALLEL_SEPARATOR_RX = re.compile(
    r"\s+(?:en\s+m[eê]me\s+temps\s+que|while|tout\s+en|en\s+|whilst)\s+",
    re.I,
)


# ---------------------------------------------------------------------------
#  PUBLIC API
# ---------------------------------------------------------------------------

def _split_global_effects(text: str) -> List[ModifierEffect]:
    """v77zw: returns the raw per-rule effects matched in the text, in
    declaration order. Lets the caller dedupe by tag at compound-time."""
    out = []
    for rx, effect in MODIFIER_RULES:
        if rx.search(text):
            out.append(effect)
    return out


def extract_segment_modifiers(segment: str) -> Dict[str, Any]:
    out = {
        "speedMul": 1.0,
        "amplitudeMul": 1.0,
        "heightMul": 1.0,
        "distanceMul": 1.0,
        "emotion": None,
        "direction": None,
        "matched": [],
    }
    for rx, effect in MODIFIER_RULES:
        if rx.search(segment):
            if "speedMul" in effect:
                out["speedMul"] *= effect["speedMul"]
            if "amplitudeMul" in effect:
                out["amplitudeMul"] *= effect["amplitudeMul"]
            if "heightMul" in effect:
                out["heightMul"] *= effect["heightMul"]
            if "distanceMul" in effect:
                out["distanceMul"] *= effect["distanceMul"]
            if effect.get("emotion") is not None:
                out["emotion"] = effect["emotion"]
            if effect.get("direction") is not None:
                out["direction"] = effect["direction"]
            out["matched"].append(effect["matched"])
    return out


def parse_custom_motion_prompt(prompt: str,
                               subject_kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Mirror of parseCustomMotionPrompt — returns a JSON-shaped dict or None.

    The output structure matches MotionDescriptor enough for diagnostic
    purposes (id, label, source, primitives:[{kind,target,axis,...}],
    duration_seconds, loop). Primitive details are looked up against the
    preset library when possible — but since this is a pure-Python parser
    without access to the full preset library, the primitives field is
    populated with a minimal placeholder ({kind, source_target, modifiers}).
    The TS side remains the source of truth for the actual primitive
    sequence used in baking — this helper lets the user TEST a prompt
    without firing the full chain.
    """
    if not isinstance(prompt, str):
        return None
    cleaned = prompt.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) < 3:
        return None

    sequential_segments = [s.strip() for s in SEQUENCE_SEPARATOR_RX.split(cleaned) if s.strip()]

    sequenced: List[Dict[str, Any]] = []
    for segment in sequential_segments:
        matched_preset = None
        for rx, preset_id in VERB_TO_PRESET:
            if rx.search(segment):
                matched_preset = preset_id
                break
        # the subject's morphology overrides the verb's default family
        matched_preset = resolve_preset_for_subject(matched_preset, subject_kind)
        sequenced.append({"presetId": matched_preset, "segment": segment})

    has_any = any(s["presetId"] is not None for s in sequenced)
    has_separator = len(sequential_segments) > 1 or PARALLEL_SEPARATOR_RX.search(cleaned)
    if not has_any and not has_separator:
        return None

    # v77zw: when there's a single segment (no "puis"/"then" separator), the
    # whole prompt IS the segment — extracting both global and segment mods
    # would double-apply every modifier. Treat single-segment prompts as
    # segment-only; multi-segment prompts use global as a baseline that
    # individual segments can override (compounding only when they override).
    global_mods = extract_segment_modifiers(cleaned) if len(sequenced) > 1 else None
    parts: List[str] = []
    primitives: List[Dict[str, Any]] = []
    total_duration = 0.0
    for seg in sequenced:
        seg_mods = extract_segment_modifiers(seg["segment"])
        if global_mods is None:
            effective = seg_mods
        else:
            # Compound: dedupe modifier tags so a tag present in both global
            # AND segment is applied once. The segment wins for emotion.
            seen_tags = set(seg_mods["matched"])
            speed_mul = seg_mods["speedMul"]
            amp_mul = seg_mods["amplitudeMul"]
            emotion = seg_mods["emotion"]
            height_mul = seg_mods["heightMul"]
            distance_mul = seg_mods["distanceMul"]
            direction = seg_mods["direction"]
            for tag, gm in zip(global_mods["matched"], _split_global_effects(cleaned)):
                if tag in seen_tags:
                    continue
                speed_mul *= gm.get("speedMul", 1.0)
                amp_mul *= gm.get("amplitudeMul", 1.0)
                height_mul *= gm.get("heightMul", 1.0)
                distance_mul *= gm.get("distanceMul", 1.0)
                if not emotion and gm.get("emotion"):
                    emotion = gm["emotion"]
                if not direction and gm.get("direction"):
                    direction = gm["direction"]
            effective = {
                "speedMul": speed_mul,
                "amplitudeMul": amp_mul,
                "heightMul": height_mul,
                "distanceMul": distance_mul,
                "emotion": emotion,
                "direction": direction,
                "matched": seg_mods["matched"] + [t for t in global_mods["matched"] if t not in seen_tags],
            }
        if seg["presetId"]:
            primitives.append({
                "kind": "preset_ref",
                "source_target": seg["presetId"],
                "modifiers": effective,
            })
            total_duration += 1.5 / max(0.1, effective["speedMul"])
            tag = " (" + ",".join(effective["matched"]) + ")" if effective["matched"] else ""
            parts.append(seg["presetId"] + tag)
        else:
            primitives.append({
                "kind": "custom_pose",
                "source_target": seg["segment"][:120],
                "modifiers": effective,
            })
            total_duration += 1.5
            parts.append(seg["segment"])

    if not primitives:
        return None

    duration_seconds = max(total_duration, 0.5)
    fps = 24
    return {
        "schema": "aurora.motion.v1",
        "id": "custom.parsed",
        "label": " → ".join(parts),
        "source": "custom",
        "loop": False,
        "fps": fps,
        "duration_seconds": duration_seconds,
        "frame_count": max(1, int(round(duration_seconds * fps))),
        "primitives": primitives,
        "global_modifiers": global_mods,
    }


# ---------------------------------------------------------------------------
#  CLI: --self-test exercises a fixture set both TS and Python should agree
# ---------------------------------------------------------------------------

def _self_test() -> int:
    failures: List[str] = []

    # Fixture 1: simple verb resolution
    cases = [
        ("le perso marche", "character.walk_cycle"),
        ("le perso court", "character.run_cycle"),
        ("le perso danse", "character.dance_default"),
        ("le perso saute", "character.jump"),
        ("le perso fait une roue", "character.cartwheel"),
        ("le perso salue", "character.wave"),
        ("le chat trotte", "creature.quadruped_walk"),
        ("le chien galope", "creature.quadruped_run"),
        ("le chien remue queue", "creature.tail_wag"),
        ("engrenage qui tourne", "mechanism.gear_mesh_rotate"),
        ("la voiture roule", "vehicle.roll_forward"),
    ]
    for prompt, expected_id in cases:
        m = parse_custom_motion_prompt(prompt)
        if not m:
            failures.append(f"'{prompt}' returned None, expected {expected_id}")
            continue
        ids = [p.get("source_target") for p in m["primitives"]]
        if expected_id not in ids:
            failures.append(f"'{prompt}' did not resolve to {expected_id}, got {ids}")

    # Fixture 2: sequence parsing
    seq = parse_custom_motion_prompt("marche puis saute")
    if not seq or len(seq["primitives"]) != 2:
        failures.append(f"sequence: expected 2 primitives, got {seq}")

    # Fixture 3: modifier — fast walk
    fast = parse_custom_motion_prompt("le perso marche rapidement")
    if not fast:
        failures.append("'marche rapidement' returned None")
    else:
        mods = fast["primitives"][0]["modifiers"]
        if "speed_fast" not in mods.get("matched", []):
            failures.append(f"'marche rapidement' missing speed_fast modifier, got {mods}")
        if abs(mods["speedMul"] - 1.6) > 0.01:
            failures.append(f"'marche rapidement' speedMul should be 1.6, got {mods['speedMul']}")

    # Fixture 4: modifier — emotion
    happy = parse_custom_motion_prompt("danse joyeusement")
    if not happy:
        failures.append("'danse joyeusement' returned None")
    else:
        mods = happy["primitives"][0]["modifiers"]
        if mods.get("emotion") != "happy":
            failures.append(f"'danse joyeusement' emotion should be happy, got {mods.get('emotion')}")

    # Fixture 5: compound modifiers
    compound = parse_custom_motion_prompt("marche rapidement puis saute fortement")
    if not compound:
        failures.append("compound returned None")
    else:
        # Walk segment should have speedMul ≈ 1.6 (rapidement is global+segment)
        # Jump segment should have speedMul ≈ 1.6 (global) and amplitudeMul ≈ 1.4 (segment)
        walk_mods = compound["primitives"][0]["modifiers"]
        jump_mods = compound["primitives"][1]["modifiers"]
        if "intensity_high" not in jump_mods.get("matched", []):
            failures.append(f"compound jump should have intensity_high, got {jump_mods}")

    # Fixture 6: non-motion prompt
    none = parse_custom_motion_prompt("a beautiful sunset")
    if none is not None:
        failures.append(f"non-motion prompt should be None, got {none}")

    # Fixture 7: empty / short
    if parse_custom_motion_prompt("") is not None:
        failures.append("empty prompt should be None")
    if parse_custom_motion_prompt("a") is not None:
        failures.append("short prompt should be None")

    if failures:
        print("PARSER_SELF_TEST_FAIL:", failures, file=sys.stderr)
        return 1
    print("PARSER_SELF_TEST_OK: %d cases passed" % (len(cases) + 6))
    return 0


def _parity_test(fixtures_path: str) -> int:
    """v77zab: verify Python parser matches the shared fixture expectations.
    The same fixtures are consumed by motionParserParity.test.ts on the TS
    side — divergence between the two parsers is caught here at CI time.
    """
    import os.path
    failures: List[str] = []

    if not os.path.isfile(fixtures_path):
        print(f"PARITY_FAIL: fixtures file not found: {fixtures_path}", file=sys.stderr)
        return 1
    with open(fixtures_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if data.get("_schema") != "aurora.motion.parity.v1":
        failures.append(f"unexpected fixtures schema: {data.get('_schema')}")
        return 1

    for f in data.get("fixtures", []):
        name = f.get("name", "<unnamed>")
        prompt = f.get("prompt", "")
        result = parse_custom_motion_prompt(prompt, f.get("subject_kind"))

        if f.get("expected_null"):
            if result is not None:
                failures.append(f"{name}: expected null, got {result}")
            continue

        if result is None:
            failures.append(f"{name}: got null but expected a result")
            continue

        # preset_ids: every expected_preset_id must be present
        if "expected_preset_ids" in f:
            actual_ids = [p.get("source_target") for p in result["primitives"]]
            for pid in f["expected_preset_ids"]:
                if pid not in actual_ids:
                    failures.append(f"{name}: missing preset {pid}, got {actual_ids}")

        # matched_tags: per-segment if specified, else aggregate across all primitives
        if "expected_matched_tags" in f:
            primary = result["primitives"][0]["modifiers"]
            actual_tags = primary.get("matched", [])
            for tag in f["expected_matched_tags"]:
                if tag not in actual_tags:
                    failures.append(f"{name}: missing tag {tag}, got {actual_tags}")
            for tag in actual_tags:
                if tag not in f["expected_matched_tags"]:
                    failures.append(f"{name}: unexpected extra tag {tag}, expected {f['expected_matched_tags']}")

        if "expected_matched_tags_contains" in f:
            primary = result["primitives"][0]["modifiers"]
            actual_tags = primary.get("matched", [])
            for tag in f["expected_matched_tags_contains"]:
                if tag not in actual_tags:
                    failures.append(f"{name}: contains tag {tag} expected, got {actual_tags}")

        if "expected_matched_tags_segment_0" in f:
            tags = result["primitives"][0]["modifiers"].get("matched", [])
            for tag in f["expected_matched_tags_segment_0"]:
                if tag not in tags:
                    failures.append(f"{name}: seg0 missing {tag}, got {tags}")
        if "expected_matched_tags_segment_1" in f:
            # Multi-primitive segments — segment 1 starts at the first primitive
            # whose source_target differs from segment 0's.
            seg1 = None
            seg0_target = result["primitives"][0]["modifiers"]
            for p in result["primitives"][1:]:
                if p["modifiers"] is not seg0_target:
                    seg1 = p["modifiers"]
                    break
            if seg1 is None:
                failures.append(f"{name}: no segment 1 found")
            else:
                tags = seg1.get("matched", [])
                for tag in f["expected_matched_tags_segment_1"]:
                    if tag not in tags:
                        failures.append(f"{name}: seg1 missing {tag}, got {tags}")

        # speedMul / amplitudeMul exact + _min variants
        primary = result["primitives"][0]["modifiers"]
        if "expected_speedMul" in f:
            actual = primary.get("speedMul", 1.0)
            if abs(actual - f["expected_speedMul"]) > 0.01:
                failures.append(f"{name}: speedMul expected {f['expected_speedMul']}, got {actual}")
        if "expected_speedMul_segment_0" in f:
            actual = result["primitives"][0]["modifiers"].get("speedMul", 1.0)
            if abs(actual - f["expected_speedMul_segment_0"]) > 0.01:
                failures.append(f"{name}: seg0 speedMul expected {f['expected_speedMul_segment_0']}, got {actual}")
        if "expected_amplitudeMul" in f:
            actual = primary.get("amplitudeMul", 1.0)
            if abs(actual - f["expected_amplitudeMul"]) > 0.01:
                failures.append(f"{name}: amplitudeMul expected {f['expected_amplitudeMul']}, got {actual}")
        if "expected_amplitudeMul_min" in f:
            actual = primary.get("amplitudeMul", 1.0)
            if actual < f["expected_amplitudeMul_min"]:
                failures.append(f"{name}: amplitudeMul {actual} < min {f['expected_amplitudeMul_min']}")
        if "expected_heightMul" in f:
            actual = primary.get("heightMul", 1.0)
            if abs(actual - f["expected_heightMul"]) > 0.01:
                failures.append(f"{name}: heightMul expected {f['expected_heightMul']}, got {actual}")
        if "expected_heightMul_min" in f:
            actual = primary.get("heightMul", 1.0)
            if actual < f["expected_heightMul_min"]:
                failures.append(f"{name}: heightMul {actual} < min {f['expected_heightMul_min']}")
        if "expected_distanceMul" in f:
            actual = primary.get("distanceMul", 1.0)
            if abs(actual - f["expected_distanceMul"]) > 0.01:
                failures.append(f"{name}: distanceMul expected {f['expected_distanceMul']}, got {actual}")
        if "expected_direction" in f:
            actual = primary.get("direction")
            if actual != f["expected_direction"]:
                failures.append(f"{name}: direction expected {f['expected_direction']}, got {actual}")
        if "expected_emotion" in f:
            actual = primary.get("emotion")
            if actual != f["expected_emotion"]:
                failures.append(f"{name}: emotion expected {f['expected_emotion']}, got {actual}")

    if failures:
        print("PARITY_FAIL:", file=sys.stderr)
        for f_msg in failures:
            print(f"  {f_msg}", file=sys.stderr)
        return 1
    print(f"PARITY_OK: {len(data.get('fixtures', []))} fixtures pass")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", help="parse this prompt and print the result as JSON")
    ap.add_argument("--subject-kind", default=None, dest="subject_kind",
                    help="subject morphology (quadruped/creature/human/...); "
                         "constrains preset choice so it matches the metarig")
    ap.add_argument("--self-test", action="store_true", help="run smoke fixtures")
    ap.add_argument("--parity-test", help="path to motion_parser_fixtures.json")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if args.parity_test:
        return _parity_test(args.parity_test)
    if args.prompt:
        result = parse_custom_motion_prompt(args.prompt, args.subject_kind)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("usage: motion_parser.py [--self-test | --parity-test <fixtures_json> | --prompt <text>]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
