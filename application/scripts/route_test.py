#!/usr/bin/env python3
"""3D routing self-test — Python mirror of `routePipeline()` in
`application/src/services/threeDIntent.ts`. Lets us verify routing decisions
deterministically without running the full pipeline (Node ESM cannot strip-load
the TS source because of `.ts`-extensionless imports across the project).

Run:
    python application/scripts/route_test.py "<prompt>"
    python application/scripts/route_test.py "<prompt>" --image-count 8
    python application/scripts/route_test.py "<prompt>" --purpose character

Output: JSON with `system_class`, branch flags, `pipeline`, `procedural_template`,
`fallback_pipeline`, `dreamgaussianPreferred`, plus a probable_pipeline string
that mirrors the TS `routePipeline()` return shape.

Keep the regex literals + branch order in 1:1 sync with `routePipeline()` and
`detectSystemClass()` in threeDIntent.ts. When you change one side, change both.
The unit tests in `route_test_test.py` guard against drift.

v82nu iter12 — extended from a 4-flag stub to a full mirror of the systemClass
decision tree (pc_cabling, led_strip, kinematic + cinematic_signal, hybrid).
The previous stub silently misreported every Strimer / belt-drive / cable-bundle
prompt as "ai_generation (Hunyuan3D default)" because the systemClass branches
weren't covered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


# ── detectSystemClass() mirror (threeDIntent.ts:194-216) ──
# Order matters: more specific patterns first, generic catch-alls last.
_SYS_CLASS_PATTERNS = [
    ('belt_drive',        r"\b(courroie|belt|poulie|pulley|belt drive|transmission courroie)\b"),
    ('gear_train',        r"\b(engrenage|gear|gearbox|reducteur|reducer|pignon|pinion|gear train|train d[\s']?engrenage)\b"),
    # cylinder_actuator excludes "engine|moteur" via a negative check below
    ('cylinder_actuator', r"\b(verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|actuator|piston)\b"),
    ('hinge_joint',       r"\b(hinge|charniere|charni[eè]re|pivot|gond)\b"),
    ('linkage',           r"\b(linkage|bielle|cam|came|lever|levier|rocker|crank|slider|biellette|manivelle|tringlerie)\b"),
    # led_strip — explicit
    ('led_strip',         r"\b(bandeau\s+led|ruban\s+led|led\s+strip|strip\s+led|ws2812|sk6812|addressable\s+led|neopixel|chaser|arc\s+en\s+ciel|rainbow\s+led|rgb\s+strip)\b"),
    # pc_cabling — known brands + PC component co-occurrence
    ('pc_cabling',        r"\b(strimer|lian li|cablemod|cable mod)\b"),
    ('pc_cabling',        r"\b(motherboard|carte mere|psu|alimentation|pcie|atx|sata|gpu|carte graphique|case wiring|cable management|argb|12vhpwr|24[\s-]?pin|8[\s-]?pin|extension cable|sleeved cable|cable extension|rallonge)\b"),
    # electrical_harness
    ('electrical_harness',r"\b(wire harness|harness|faisceau|electrique|electrical|connector|connecteur|loom|bornier|terminal block)\b"),
    # cable_routing — generic cable fallback
    ('cable_routing',     r"\b(cable|cables|wire|wiring|fil|fils|cordon)\b"),
]

_LED_FALLBACK_RE = re.compile(r"\bled\b", re.IGNORECASE)
_LED_PATTERN_RE  = re.compile(r"\b(bandeau|ruban|strip|bande|chaser|chenillard|pattern)\b", re.IGNORECASE)
_RGB_LED_RE      = re.compile(r"\b(rgb|led)\b", re.IGNORECASE)
_CABLE_KW_RE     = re.compile(r"\b(cable|extension|strip|ruban|bande)\b", re.IGNORECASE)
_ENGINE_NEG_RE   = re.compile(r"\b(engine|moteur)\b", re.IGNORECASE)

KINEMATIC_CLASSES = {'belt_drive', 'gear_train', 'cylinder_actuator', 'hinge_joint', 'linkage'}
CABLE_CLASSES = {'pc_cabling', 'cable_routing', 'electrical_harness'}


def detect_system_class(prompt: str) -> str:
    p = prompt.lower()
    for cls, pat in _SYS_CLASS_PATTERNS:
        if cls == 'cylinder_actuator':
            if re.search(pat, p, re.IGNORECASE) and not _ENGINE_NEG_RE.search(p):
                return cls
            continue
        if re.search(pat, p, re.IGNORECASE):
            return cls
    # 2-step LED fallback (threeDIntent.ts:207)
    if _LED_FALLBACK_RE.search(p) and _LED_PATTERN_RE.search(p):
        return 'led_strip'
    # 2-step RGB cable fallback (threeDIntent.ts:211)
    if _RGB_LED_RE.search(p) and _CABLE_KW_RE.search(p):
        return 'pc_cabling'
    return 'generic'


# ── routePipeline() branch flag regexes (threeDIntent.ts:1339-1500) ──
PHOTOGRAMMETRY_RE = re.compile(
    r"\b(photogramm|scan|reconstru|multi[\s-]?vues? reelle|real[\s-]?photos?|"
    r"photos? reelle|capture 3d)\b",
    re.IGNORECASE,
)
CINEMATIC_SIGNAL_RE = re.compile(
    r"\b(cinematique|kinematic|ratio|vitesse|rpm|couple|torque|course|stroke|driver|driven|transmission)\b",
    re.IGNORECASE,
)
PROCEDURAL_CABLE_KEYWORDS_RE = re.compile(
    r"\b(bundle|faisceau|routage exact|exact routing|strimer|cable management|geometry nodes)\b",
    re.IGNORECASE,
)
STRIMER_PLUS_V2_RE = re.compile(
    r"\b(strimer(?:\s+plus)?(?:\s*v2)?|lian\s+li\s+strimer)\b",
    re.IGNORECASE,
)
STYLIZED_RE = re.compile(
    r"\b(anime|manga|stylise|cartoon|lowpoly|low poly|voxel|chibi)\b",
    re.IGNORECASE,
)
NEGATED_STYLIZED_RE = re.compile(
    r"\b(non[-\s]?anime|non[-\s]?manga|non[-\s]?cartoon|"
    r"pas\s+(?:anime|manga|cartoon|stylis[eÃ©])|"
    r"not\s+(?:anime|manga|cartoon|stylized|stylised)|"
    r"rendu\s+non[-\s]?anime)\b",
    re.IGNORECASE,
)
LUXURY_MATERIAL_RE = re.compile(
    r"\b(quartz fum[eé]|fum[eé] translucide|obsidienne|obsidian|acajou nordique|"
    r"mahogany|or rose|rose gold|nacre|mother of pearl|onyx|jade noir|marbre|"
    r"marble|opalescent|dichro[iï]que|dichroic|liquid metal|chrome bross[eé]|"
    r"brushed chrome)\b",
    re.IGNORECASE,
)
HUMANOID_PERFORMER_RE = re.compile(
    r"\b(macarena|danse|dance|dancing|chor[eÃ©]graph|choreograph|"
    r"body\s+action|action\s+corporelle|gesture|gestuelle)\b",
    re.IGNORECASE,
)
# Named public/fictional subjects must not be replaced by the generic
# procedural dancer fallback. These mirrors the TypeScript router guard.
KNOWN_CHARACTER_CONTEXT_RE = re.compile(
    r"\b(anime|manga|shonen|comic|comics|bd|serie|series|film|movie|game|jeu|"
    r"franchise|fairy\s*tail|one\s*piece|naruto|dragon\s*ball|bleach|"
    r"jujutsu|demon\s*slayer|kimetsu|marvel|dc|pokemon|zelda|"
    r"final\s*fantasy)\b",
    re.IGNORECASE,
)
PROPER_NAME_RE = re.compile(r"\b[A-Z][a-zA-Z'_-]{2,}\s+[A-Z][a-zA-Z'_-]{2,}\b")
FLOSS_RE = re.compile(r"\bfloss(?:ing)?\b", re.IGNORECASE)
EXPLICIT_PROCEDURAL_HUMANOID_RE = re.compile(
    r"\b(procedural|prototype|mannequin|gabarit|test\s+rig|rig\s+test|"
    r"placeholder|simple\s+rig|avatar\s+generique)\b",
    re.IGNORECASE,
)
HAND_FIDELITY_RE = re.compile(
    r"\b(mains?|hands?|doigts?|fingers?|palms?|paumes?|poignets?|wrists?|"
    r"retourner\s+ses\s+mains|open\s+palms?)\b",
    re.IGNORECASE,
)
HISTORICAL_PUBLIC_FIGURE_RE = re.compile(
    r"\b(abraham\s+lincoln|lincoln)\b",
    re.IGNORECASE,
)
HUMANOID_ACTION_OR_CUE_RE = re.compile(
    r"\b(marche|marcher|walk|walking|court|courir|run|running|danse|danser|"
    r"dance|dancing|macarena|pose|visage|face|cheveux|hair|costume|outfit|"
    r"heros|hero|personnage|character)\b",
    re.IGNORECASE,
)
ORIGINAL_GENERIC_CHARACTER_RE = re.compile(
    r"\b(original|generique|g[eÃ©]n[eÃ©]rique|generic|avatar|performer|"
    r"danseur|dancer|personnage\s+(?:original|invent[eÃ©]|cr[eÃ©][eÃ©]))\b",
    re.IGNORECASE,
)

# Mechanism legacy regex kept for backwards-compat with callers that read the
# `flags.mechanism` field.
MECHANISM_RE = re.compile(
    r"\b(belt|courroie|gear|engrenage|pulley|poulie|hinge|charniere|linkage|"
    r"bielle|cylinder actuator|verin|cable bundle|faisceau)\b",
    re.IGNORECASE,
)


def route_pipeline(
    prompt: str,
    image_count: int = 0,
    purpose: str = 'visual_preview',
    subject_kind: str = 'product',
    motion_readiness: str = 'static_only',
) -> dict:
    """Mirror of routePipeline() in threeDIntent.ts.

    Returns the same shape as the TS function, plus a probable_pipeline
    string for human-readable triage.
    """
    p = prompt.lower()
    system_class = detect_system_class(prompt)
    proper_name = bool(PROPER_NAME_RE.search(prompt))
    known_character = (
        bool(KNOWN_CHARACTER_CONTEXT_RE.search(p))
        and (proper_name or bool(HUMANOID_ACTION_OR_CUE_RE.search(p)) or bool(FLOSS_RE.search(p)))
    ) or (proper_name and (bool(HUMANOID_ACTION_OR_CUE_RE.search(p)) or bool(FLOSS_RE.search(p))))
    original_generic_character = bool(ORIGINAL_GENERIC_CHARACTER_RE.search(p)) and not known_character
    character_request = purpose == 'character' or subject_kind == 'character'
    explicit_procedural_humanoid = bool(EXPLICIT_PROCEDURAL_HUMANOID_RE.search(p))
    requires_human_fidelity = bool(character_request and not explicit_procedural_humanoid)
    requires_hand_fidelity = bool(
        character_request
        and (HAND_FIDELITY_RE.search(p) or HUMANOID_PERFORMER_RE.search(p) or FLOSS_RE.search(p))
    )

    # Branch flag extraction
    has_photogrammetry = bool(PHOTOGRAMMETRY_RE.search(p))
    has_cinematic = bool(CINEMATIC_SIGNAL_RE.search(p))
    has_procedural_cable_kw = bool(PROCEDURAL_CABLE_KEYWORDS_RE.search(p))
    is_kinematic = system_class in KINEMATIC_CLASSES
    wants_procedural_cable = (system_class in CABLE_CLASSES) and has_procedural_cable_kw
    is_stylized = bool(STYLIZED_RE.search(p)) and not bool(NEGATED_STYLIZED_RE.search(p))
    has_luxury = bool(LUXURY_MATERIAL_RE.search(p))
    has_mechanism = bool(MECHANISM_RE.search(p))

    flags = {
        'photogrammetry': has_photogrammetry,
        'mechanism': has_mechanism,
        'kinematic': is_kinematic,
        'cinematic_signal': has_cinematic,
        'procedural_cable': wants_procedural_cable,
        'led_strip': system_class == 'led_strip',
        'stylized': is_stylized,
        'luxury_material': has_luxury,
        'known_character': known_character,
        'human_fidelity': requires_human_fidelity,
        'hand_fidelity': requires_hand_fidelity,
    }

    # ── Branch 1: PHOTOGRAMMETRY ──
    if image_count >= 8 or (image_count >= 4 and has_photogrammetry):
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'photogrammetry',
            'procedural_template': None,
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': True,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'photogrammetry (>=4 multi-view photos required)',
        }

    # ── Branch 2: PROCEDURAL kinematic with cinematic signal ──
    if is_kinematic and (has_cinematic or motion_readiness == 'articulated'):
        template_map = {
            'belt_drive':        'pulley_belt_system',
            'gear_train':        'gear_train_system',
            'cylinder_actuator': 'cylinder_actuator_system',
            'hinge_joint':       'hinge_joint_system',
            'linkage':           'linkage_system',
        }
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': template_map[system_class],
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': f'procedural ({template_map[system_class]})',
        }

    # ── Branch 3: PROCEDURAL cable bundle ──
    if wants_procedural_cable:
        template = 'strimer_plus_v2_cable' if STRIMER_PLUS_V2_RE.search(p) else 'cable_bundle_system'
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': template,
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': f'procedural ({template})',
        }

    # ── Branch 4: PROCEDURAL led_strip ──
    if system_class == 'led_strip':
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': 'led_strip_system',
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'procedural (led_strip_system)',
        }

    # ── Branch 4.5: PROCEDURAL motherboard_layout (iter25) ──
    # Brand mobos / generic motherboard prompts go to procedural so the OLED
    # face stays a separate plane carrying aurora.oled-atlas.v1 extras (real
    # animated screen, not baked image).
    _PROCEDURAL_MOBO_RE = re.compile(
        r"\b(x870e|x670e|x670|b850|b650|z890|z790|z690|"
        r"rog\s+strix|rog\s+crosshair|rog\s+maximus|rog\s+(?:c|h)ero|"
        r"tuf\s+gaming|prime\s+(?:x|z|b)\d|msi\s+(?:meg|mpg|mag)|"
        r"gigabyte\s+aorus|asrock\s+(?:taichi|phantom)|"
        r"motherboard|carte\s+m[èe]re|mainboard|pcb\s+motherboard)\b",
        re.IGNORECASE,
    )
    if _PROCEDURAL_MOBO_RE.search(p):
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': 'motherboard_layout',
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'procedural (motherboard_layout)',
        }

    # ── Branch 5: HYBRID (kinematic + visual_preview without cinematic signal) ──
    if character_request and HISTORICAL_PUBLIC_FIGURE_RE.search(prompt):
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': 'historical_person_performer',
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'procedural (historical_person_performer)',
        }

    if (
        image_count == 0
        and (purpose == 'character' or subject_kind == 'character')
        and original_generic_character
        and not requires_human_fidelity
        and (HUMANOID_PERFORMER_RE.search(p) or FLOSS_RE.search(p))
    ):
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'procedural',
            'procedural_template': 'humanoid_performer',
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'procedural (humanoid_performer)',
        }

    if is_kinematic and not has_cinematic and purpose == 'visual_preview':
        return {
            'prompt': prompt,
            'image_count': image_count,
            'system_class': system_class,
            'flags': flags,
            'pipeline': 'hybrid',
            'procedural_template': 'pulley_belt_system' if system_class == 'belt_drive' else None,
            'fallback_pipeline': 'ai_generation',
            'blender_required': True,
            'meshroom_required': False,
            'dreamgaussianPreferred': False,
            'probable_pipeline': 'hybrid (procedural skeleton + AI texture)',
        }

    # ── Branch 6: AI GENERATION default ──
    dreamgaussian_preferred = (
        is_stylized
        or has_luxury
        or requires_human_fidelity
        or purpose == 'character'
        or subject_kind in ('character', 'creature')
        or purpose == 'game_asset'
    )
    label = 'DreamGaussian preferred -- MIT, EU-safe' if dreamgaussian_preferred \
        else 'Hunyuan3D default -- license warning for EU'
    return {
        'prompt': prompt,
        'image_count': image_count,
        'system_class': system_class,
        'flags': flags,
        'pipeline': 'ai_generation',
        'procedural_template': None,
        'fallback_pipeline': 'ai_generation',
        'blender_required': False,
        'meshroom_required': False,
        'dreamgaussianPreferred': dreamgaussian_preferred,
        'probable_pipeline': f'ai_generation ({label})',
    }


# Back-compat shim: callers that imported the old `evaluate(prompt)` get a
# subset view + the old "signal-only" probable_pipeline semantics.
#
# Pre-iter12, evaluate() reported probable_pipeline based on flag presence
# alone, NOT on image_count gating. Legacy tests + scripts rely on that:
# "8 photos d'un chateau pour photogrammetrie" returns probable_pipeline
# = "photogrammetry (...)" even though no actual image files are attached.
# Keeping that contract avoids breaking existing test_route_test.py +
# any out-of-tree callers that imported `evaluate`.
def evaluate(prompt: str) -> dict:
    p = prompt.lower()
    photogrammetry = bool(PHOTOGRAMMETRY_RE.search(p))
    mechanism = bool(MECHANISM_RE.search(p))
    stylized = bool(STYLIZED_RE.search(p)) and not bool(NEGATED_STYLIZED_RE.search(p))
    luxury_material = bool(LUXURY_MATERIAL_RE.search(p))
    dreamgaussian_preferred = stylized or luxury_material

    if photogrammetry:
        probable = 'photogrammetry (>=4 multi-view photos required)'
    elif mechanism:
        probable = 'procedural (Blender mechanism template)'
    elif dreamgaussian_preferred:
        probable = 'ai_generation (DreamGaussian preferred -- MIT, EU-safe)'
    else:
        probable = 'ai_generation (Hunyuan3D default -- license warning for EU)'

    return {
        'prompt': prompt,
        'flags': {
            'photogrammetry': photogrammetry,
            'mechanism': mechanism,
            'stylized': stylized,
            'luxury_material': luxury_material,
        },
        'dreamgaussianPreferred': dreamgaussian_preferred,
        'probable_pipeline': probable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Mirror of routePipeline() in threeDIntent.ts',
    )
    parser.add_argument('prompt', nargs='+', help='Prompt to route')
    parser.add_argument('--image-count', type=int, default=0,
                        help='Number of reference images attached (gates photogrammetry)')
    parser.add_argument('--purpose', default='visual_preview',
                        help='ThreeDPurpose (visual_preview, character, product, etc.)')
    parser.add_argument('--subject-kind', default='product',
                        help='ThreeDSubjectKind (product, character, creature, etc.)')
    parser.add_argument('--motion-readiness', default='static_only',
                        help='MotionReadiness (static_only, articulated, rig_candidate, poseable)')
    parser.add_argument('--legacy', action='store_true',
                        help='Output the old 4-flag evaluate() shape for back-compat')
    args = parser.parse_args()

    prompt = ' '.join(args.prompt).strip()
    if not prompt:
        sys.stderr.write('usage: route_test.py "<prompt>" [--image-count N] [--purpose ...]\n')
        return 2

    if args.legacy:
        out = evaluate(prompt)
    else:
        out = route_pipeline(
            prompt,
            image_count=args.image_count,
            purpose=args.purpose,
            subject_kind=args.subject_kind,
            motion_readiness=args.motion_readiness,
        )
    sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
