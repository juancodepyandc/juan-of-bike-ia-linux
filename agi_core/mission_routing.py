"""Navigation hints and multi-module pipeline inference from explicit domain signals; never substitute a project goal."""
from __future__ import annotations

import re
from typing import Any
import unicodedata

MODULES = {
    'conversation', 'image', 'code', 'video', 'drawing', '3d',
    'learning', 'cyber', 'voice', 'business', 'simulator',
    'cowork', 'training', 'animation',
}

_DOMAIN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ('3d', re.compile(
        r'\b(?:3d|stl|glb|gltf|figurine|figurines|maillage|mesh|watertight|manifold|'
        r'impression tridimensionnelle|trellis|hunyuan3d|unirig|rigging 3d)\b'
    )),
    ('business', re.compile(
        r'\b(?:business lab|business live|business intelligence|portefeuille virtuel|'
        r'capital fictif|unit economics|ltv/cac|walk-forward|monte-carlo financier|bfr|dso)\b'
    )),
    ('cyber', re.compile(
        r'\b(?:0-day|zero-day|cve-\d+|cwe-\d+|pentest|audit de securite|execution symbolique|'
        r'exploit|vulnerabilite|patch de securite|forensics|steganographie)\b'
    )),
    ('animation', re.compile(
        r'\b(?:hy-motion|skinning dqs|foot-lock ik|cinematique inverse|squelette unirig|'
        r'animation squelettique)\b'
    )),
    ('video', re.compile(
        r'\b(?:wan2|ltx-video|storyboard video|montage video|musetalk|sadtalker|sequence mp4)\b'
    )),
    ('image', re.compile(
        r'\b(?:flux\.?2|comfyui|txt2img|img2img|inpainting|upscale 16k|rendu photo|illustration 8k)\b'
    )),
    ('drawing', re.compile(
        r'\b(?:character forge|character sheet|turnaround|croquis sur toile|controlnet scribble)\b'
    )),
    ('voice', re.compile(
        r'\b(?:kokoro tts|faster-whisper|synthese vocale|visemes rhubarb|mode duplex vocal)\b'
    )),
    ('learning', re.compile(
        r'\b(?:oracle sympy|annales du bac|fiche de revision|flashcards anki|preuve formelle lean)\b'
    )),
    ('simulator', re.compile(
        r'\b(?:simulateur physique|solveur sph|mecanique lagrangienne|integration rk4)\b'
    )),
    ('training', re.compile(
        r'\b(?:auto_rl|stop_after_cycle|modele renforce|flow-matching dpo|kaggle 2xt4)\b'
    )),
    ('cowork', re.compile(
        r'\b(?:extension chrome mv3|workflow cowork|extraction documentaire pdf)\b'
    )),
)


def _normalize(text: str) -> str:
    return unicodedata.normalize('NFKD', (text or '').casefold()).encode('ascii', 'ignore').decode()


def mission_module(payload: dict[str, Any]) -> str | None:
    explicit = payload.get('module')
    if explicit in MODULES:
        return explicit
    if payload.get('project_kind') == 'engineering':
        return '3d'
    if payload.get('project_kind') == 'business':
        return 'business'
    raw_text = payload.get('project_title') or payload.get('request', '')
    text = _normalize(raw_text)
    if not text.strip():
        return None
    for mod, pat in _DOMAIN_PATTERNS:
        if pat.search(text):
            return mod
    return None


def infer_mission_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    """Détecte le module primaire et la chaîne de synergie multi-modules ordonnée."""
    raw_text = payload.get('project_title') or payload.get('request', '')
    text = _normalize(raw_text)
    primary = mission_module(payload)
    detected: list[str] = []
    if primary:
        detected.append(primary)
    for mod, pat in _DOMAIN_PATTERNS:
        if pat.search(text) and mod not in detected:
            detected.append(mod)
    if not detected:
        detected = ['conversation']
    return {
        'primary_module': detected[0],
        'pipeline_modules': detected,
        'is_multi_module': len(detected) > 1,
    }


def direct_3d_generation(text: str) -> bool:
    normalized = _normalize(text).strip()
    return (
        mission_module({'request': text}) == '3d'
        and bool(re.match(r'(?:generer|genere|creer|cree|generate|create|modeliser|modelise|sculpter|sculpte)\b', normalized))
        and not re.search(
            r'\b[\w-]+\.py\b|\b(?:blender|openscad|freecad|cadquery|viewer|visualiseur|application|script|code|react|typescript)\b',
            normalized,
        )
    )


