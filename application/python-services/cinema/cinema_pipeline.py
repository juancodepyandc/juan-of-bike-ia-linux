"""
cinema_pipeline.py -- Orchestrateur multi-plans pour le module Cinema.

Pipeline:
  1. Lit un storyboard JSON (genere par le LLM cote frontend)
  2. Pour chaque plan:
     a. Genere keyframe FLUX (delegue a comfy_supervisor.py si dispo, sinon prompt direct)
     b. Anime en clip Wan2.2 (delegue a video_generate.py existant)
     c. Si dialogue: synthetise voix (voice_clone.py) + lipsync (talking_head.py SadTalker)
  3. Concatene tous les plans via FFmpeg
  4. Optionnel: upscale 1440p, ajout musique
  5. Emet une vraie ETA mesuree pendant la generation (PROGRESS:eta:...)

Usage:
  python cinema_pipeline.py --storyboard board.json --output final.mp4
  python cinema_pipeline.py --check

Format storyboard.json:
{
  "title": "Le frigo qui parle",
  "style": "cartoon_pixar",
  "aspect": "9:16",
  "resolution": "1080p",
  "characters": [
    {"name": "Mecano", "voice_slug": "mecano_french_older", "voice_lang": "fr",
     "description": "homme grisonnant en bleu de travail"},
    ...
  ],
  "shots": [
    {"id": 1, "speaker": "Mecano", "dialogue": "Le froid c'est une histoire de pression",
     "scene": "garage atelier au coucher du soleil, mecano cartoon souriant",
     "duration_s": 5, "camera": "medium", "needs_lipsync": true},
    ...
  ],
  "music": {"enabled": false, "prompt": ""},
  "subtitles": {"enabled": false}
}

Output JSON ligne finale:
  {"ok": true, "video": "final.mp4", "duration_s": 35.4, "shots": 7,
   "actual_time_s": 12300, "estimated_time_s": 13500}
"""

import argparse
import gc
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = WORKSPACE / "temp" / "cinema"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = WORKSPACE / "generated" / "videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VISION_MODEL = os.environ.get("AURORA_VISION_MODEL", "qwen3-vl:8b")

# v91 : plancher absolu de qualite. En dessous, un plan n'est jamais livre,
# meme si l'appelant a desactive la porte stricte. Mesure a l'origine : des
# plans notes 2.8/10 ("wheels are stationary") et 0.0/10 ont ete livres.
ABSOLUTE_QUALITY_FLOOR = float(os.environ.get("AURORA_QUALITY_FLOOR", "4.5"))


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def emit_eta(elapsed_s: float, done: int, total: int, current_stage: str):
    """Emit a structured ETA line that the frontend can parse for live progress."""
    if done <= 0:
        eta_remaining = 0
    else:
        per_unit = elapsed_s / done
        eta_remaining = per_unit * (total - done)
    payload = {
        "elapsed_s": round(elapsed_s, 1),
        "done": done,
        "total": total,
        "remaining_s": round(eta_remaining, 1),
        "stage": current_stage,
    }
    print(f"PROGRESS:eta:{json.dumps(payload)}", flush=True)


def _ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _run(cmd: list, timeout: int = 1800) -> tuple:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000  # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=creationflags)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)


# --------------------------------------------------------------------------
# Resolution mapping
# --------------------------------------------------------------------------

def parse_resolution(label: str, aspect: str = "16:9") -> tuple:
    """Map a resolution label + aspect ratio to (width, height)."""
    base = {
        "720p":   720,
        "1080p":  1080,
        "1440p":  1440,
        "2k":     1440,
        "4k":     2160,
    }.get(label.lower(), 1080)

    if aspect == "16:9":
        h = base
        w = int(round(h * 16 / 9))
    elif aspect == "9:16":
        w = base
        h = int(round(w * 16 / 9))
    elif aspect == "1:1":
        w = h = base
    elif aspect == "4:3":
        h = base
        w = int(round(h * 4 / 3))
    else:
        h = base
        w = int(round(h * 16 / 9))

    # Wan2.2 prefers multiples of 8
    w = (w // 8) * 8
    h = (h // 8) * 8
    return w, h


def resolution_for_generation(label: str, aspect: str) -> tuple:
    """Return (gen_w, gen_h, upscale_factor). Wan2.2 generates at lower res; we upscale post.

    v82m2 : safe-mode après tests live — 832x480x72 crash ACCESS_VIOLATION
    sur RTX 5070 Ti / torch 2.11+cu128. LTX direct 320x192 marche. On
    réduit drastiquement la gen_resolution pour éviter le native crash,
    puis upscale post-render pour atteindre le target.
    """
    target_w, target_h = parse_resolution(label, aspect)
    if max(target_w, target_h) >= 1440:
        gen_w = (target_w // 16) * 8
        gen_h = (target_h // 16) * 8
        upscale = 2
    elif max(target_w, target_h) >= 1080:
        gen_w = (target_w // 12) * 8
        gen_h = (target_h // 12) * 8
        upscale = 1.5
    elif max(target_w, target_h) >= 720:
        # v82m2 : 720p target -> generate at 480x288 instead of 848x480
        # to avoid the worker crash. Post-upscale recovers the perceived
        # resolution. Tested working with LTX at 320x192.
        gen_w = (target_w // 16) * 8  # ~512 for 720p
        gen_h = (target_h // 16) * 8  # ~288 for 720p
        upscale = 1.6
    else:
        gen_w = target_w
        gen_h = target_h
        upscale = 1.0
    # Lower bound to avoid degeneracy. v82m2 : reduced 384 -> 256 since
    # smaller sizes are more stable on Blackwell sm_120.
    gen_w = max(gen_w, 256)
    gen_h = max(gen_h, 256)
    gen_w = (gen_w // 8) * 8
    gen_h = (gen_h // 8) * 8
    return gen_w, gen_h, upscale


# --------------------------------------------------------------------------
# Style prompt augmentation
# --------------------------------------------------------------------------

STYLE_SUFFIX = {
    "cartoon_pixar": ", Pixar 3D animation style, soft volumetric lighting, vibrant colors, expressive characters, cinematic depth of field",
    "anime":         ", consistent hand-drawn 2D anime style, Studio Ghibli inspired background painting, cel shading, clean ink outlines, vivid colors, expressive eyes, painterly anime lighting, no photorealism",
    "manga":         ", manga panel style, dynamic ink lines, screen tones, dramatic shading",
    "realistic":     ", photorealistic, 35mm film, natural skin texture, accurate lighting, cinematic composition",
    "documentary":   ", documentary realism, natural lighting, slight handheld feel, authentic",
    "watercolor":    ", watercolor painting style, soft edges, paper texture",
    "noir":          ", film noir, high contrast black and white, dramatic shadows",
}

STYLE_NEGATIVE = {
    "anime": "photorealistic, live action, real human skin, 3d render, plastic CGI, mixed style, style drift, inconsistent art style",
    "cartoon_pixar": "photorealistic, live action, hand-drawn anime, flat 2d drawing, mixed style, style drift",
    "realistic": "cartoon, anime, painting, illustration, plastic CGI, stylized face, mixed style",
    "manga": "photorealistic, live action, full color painting, 3d render, mixed style",
    "watercolor": "photorealistic, hard cel shading, 3d render, mixed style",
    "noir": "bright saturated colors, cartoon, anime, low contrast, mixed style",
}


def style_for(style_id: str) -> str:
    if style_id == "raw":
        return ""
    return STYLE_SUFFIX.get(style_id, STYLE_SUFFIX["realistic"])


def style_negative_for(style_id: str) -> str:
    return STYLE_NEGATIVE.get(style_id, "")


def style_validation_contract(style_id: str) -> str:
    if style_id == "anime":
        return (
            "\nRequired visual style: consistent hand-drawn 2D anime/cel-shaded look. "
            "Reject photorealistic/live-action frames or style changes between shots."
        )
    if style_id in STYLE_SUFFIX:
        return f"\nRequired visual style: {STYLE_SUFFIX[style_id].strip(', ')}."
    return ""


def combine_negative_prompt(*parts: str) -> str:
    seen = set()
    out = []
    for part in parts:
        for token in (part or "").split(","):
            item = token.strip()
            if not item:
                continue
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
    return ", ".join(out)


def _score(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def shot_quality_average(q: dict) -> float:
    return (
        _score(q.get("score"))
        + _score(q.get("physics_score"))
        + _score(q.get("identity_score"))
        + _score(q.get("action_score"))
    ) / 4.0


def shot_quality_is_measured(q: dict) -> bool:
    """True only when every score used by the quality gate is real."""
    if not isinstance(q, dict):
        return False
    if q.get("graded") is False:
        return False
    return all(
        isinstance(q.get(key), (int, float)) and not isinstance(q.get(key), bool)
        for key in ("score", "physics_score", "identity_score", "action_score")
    )


def has_blocking_visual_issue(q: dict) -> bool:
    """Reject premium shots where the requested visible action/object is missing.

    Vision QA often still gives a numeric pass while naming the exact failure in
    `issues`; this catches those textual red flags without failing harmless
    framing notes such as feet being out of frame.
    """
    blocking_markers = (
        "not visible",
        "no visible",
        "not clearly visible",
        "missing",
        "not represented",
        "no clear indication",
        "cannot be confirmed",
        "pencil",
        "paper",
        "cable",
        "unreadable",
        "not readable",
        "wrong object",
        "wrong tool",
        "forbidden",
        "violating",
        "contradict",
        "open notebook",
        "floating",
        "morph",
    )
    benign_markers = (
        "feet",
        "foot",
        "boots",
        "background",
        "out of frame",
        "depth of field",
        # v90.3 : le mouvement de caméra est injugeable sur 3 frames fixes —
        # "no clear indication of the camera orbiting" déclenchait un retry
        # complet (~5 min GPU) pour rien. Idem pour les nuances "slight*".
        "camera",
        "orbit",
        "panning",
        "pan left",
        "pan right",
        "zoom",
        "dolly",
        "slight",
        "minor",
    )
    for issue in q.get("issues") or []:
        text = str(issue).lower()
        if any(marker in text for marker in blocking_markers):
            if not any(marker in text for marker in benign_markers):
                return True
    return False


def has_only_minor_continuity_issues(q: dict) -> bool:
    """Allow natural facial micro-variation when core action/object scores pass.

    Corrective retries can degrade a good shot by overfitting a harmless note
    (for example a smile becoming neutral) and introducing forbidden props.
    """
    issues = [str(issue).lower() for issue in (q.get("issues") or []) if str(issue).strip()]
    if has_blocking_visual_issue(q):
        return False
    meaningful = [
        issue for issue in issues
        if "vision json parse failed" not in issue and "validation skipped" not in issue
    ]
    if not meaningful:
        return bool(issues) or "vision json parse failed" in str(q.get("reason", "")).lower()
    minor_markers = (
        "expression",
        "facial",
        "smile",
        "neutral",
        "eye",
        "eyes",
        "blink",
        "mouth",
        "hair",
        "glasses",
        "thickness",
        "nose",
        "feature",
        "minor drift",
        "slight",
    )
    return all(any(marker in issue for marker in minor_markers) for issue in meaningful)


def has_only_validation_parse_issue(q: dict) -> bool:
    issues = [str(issue).lower() for issue in (q.get("issues") or []) if str(issue).strip()]
    reason = str(q.get("reason") or "").lower()
    if has_blocking_visual_issue(q):
        return False
    text = " ".join(issues + [reason])
    if "vision json parse failed" not in text and "validation skipped" not in text:
        return False
    return all(
        "vision json parse failed" in issue or "validation skipped" in issue
        for issue in issues
    )


def shot_quality_ok(q: dict, quality_mode: str = "auto") -> bool:
    if not shot_quality_is_measured(q):
        return False
    min_scene = 7 if quality_mode == "premium" else 6
    min_other = 7 if quality_mode == "premium" else 6
    if quality_mode in ("premium", "balanced") and has_blocking_visual_issue(q):
        return False
    if (
        quality_mode in ("premium", "balanced")
        and _score(q.get("physics_score")) >= min_other
        and _score(q.get("identity_score")) >= min_other
        and _score(q.get("action_score")) >= min_other
        and shot_quality_average(q) >= 8.0
    ):
        return True
    if (
        _score(q.get("score")) >= min_scene
        and _score(q.get("physics_score")) >= min_other
        and _score(q.get("identity_score")) >= min_other
        and _score(q.get("action_score")) >= min_other
        and shot_quality_average(q) >= min_other
    ):
        return True
    return (
        quality_mode in ("premium", "balanced")
        and _score(q.get("score")) >= 5
        and _score(q.get("physics_score")) >= min_other
        and _score(q.get("identity_score")) >= min_other
        and _score(q.get("action_score")) >= min_other
        and shot_quality_average(q) >= 7.5
        and has_only_minor_continuity_issues(q)
    )


def dedupe_shot_quality(items: list) -> list:
    """Conserve le pire passage mesure pour ne pas masquer une degradation.

    Un plan est evalue avant puis apres voix/lipsync. Garder le meilleur des
    deux autorisait une bouche degradee a heriter de la bonne note pre-audio.
    Une panne de parseur n'est toutefois pas une mesure à 0/10 : lorsqu'une
    autre passe sur le même média produit les quatre notes, elle fournit la
    couverture réelle à conserver.
    """
    worst_by_id = {}
    order = []
    for item in items or []:
        shot_id = item.get("shot_id")
        if shot_id not in worst_by_id:
            order.append(shot_id)
            worst_by_id[shot_id] = item
            continue
        previous = worst_by_id[shot_id]
        item_measured = shot_quality_is_measured(item)
        previous_measured = shot_quality_is_measured(previous)
        if item_measured and not previous_measured:
            worst_by_id[shot_id] = item
        elif item_measured == previous_measured and (
            shot_quality_average(item) < shot_quality_average(previous)
        ):
            worst_by_id[shot_id] = item
    return [worst_by_id[shot_id] for shot_id in order if shot_id in worst_by_id]


def clean_retry_note(text: str) -> str:
    clean = []
    for raw in str(text or "").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("progress:") or "vram" in low or "traceback" in low:
            continue
        clean.append(line)
    return " ".join(clean)[:240]


def should_auto_retry_shots(storyboard: dict) -> bool:
    if os.environ.get("AURORA_CINEMA_AUTO_RETRY", "1").strip().lower() in ("0", "false", "no"):
        return False
    return storyboard.get("quality_mode", "auto") in ("premium", "balanced")


def retry_scene_prompt(scene: str, style_id: str, camera: str, issues: list, reason: str, attempt: int) -> str:
    issue_text = "; ".join([clean_retry_note(i)[:120] for i in (issues or []) if clean_retry_note(i)])
    clean_reason = clean_retry_note(reason)
    if clean_reason:
        issue_text = (issue_text + "; " if issue_text else "") + clean_reason[:180]
    if not issue_text:
        issue_text = "previous attempt missed required visual cues"
    style_lock = style_for(style_id).strip(", ")
    camera_lock = SHOT_CAMERA_PROMPT.get(str(camera or "").strip().lower(), "")
    return (
        f"{scene}. RETRY PASS {attempt}: keep the exact same story beat, setting, characters, "
        f"and action. Correct these QA failures: {issue_text}. Make the main subject large and "
        f"readable, with one clear continuous action. Preserve this style exactly: {style_lock}. "
        f"{camera_lock}. Do not add new characters, do not change genre, do not change art style."
    )


# v84 : grammaire cinema par shot. Le champ storyboard `camera` (wide/medium/
# close-up) n'etait consomme par PERSONNE — il devient un descripteur de plan
# explicite dans le prompt Wan. La queue qualite positive complete le negative
# prompt (qui ne porte que les defauts) : Wan2.2 s'ancre sur ces tokens pour
# la composition, la nettete et la stabilite d'identite. Miroir Python du
# composeur TS videoPromptComposer.ts (VIDEO_QUALITY_TAIL).
SHOT_CAMERA_PROMPT = {
    "wide": "wide establishing shot",
    "medium": "medium shot",
    "close-up": "close-up shot",
    "extreme close-up": "extreme close-up shot",
}

SHOT_QUALITY_TAIL = (
    ", cinematic composition, sharp focus, high detail, natural color grading, "
    "coherent physics, stable subject identity, smooth natural motion, "
    "professional video quality"
)


def cinematography_for(shot: dict, full_prompt_so_far: str) -> str:
    """Build the per-shot cinematography suffix, skipping already-present tokens."""
    parts = []
    cam = str(shot.get("camera", "")).strip().lower()
    cam_directive = SHOT_CAMERA_PROMPT.get(cam)
    if cam_directive and cam_directive.lower() not in full_prompt_so_far.lower():
        parts.append(cam_directive)
    suffix = (", " + ", ".join(parts)) if parts else ""
    # Quality tail filtre : n'ajoute que les tokens absents du prompt.
    tail_tokens = [t.strip() for t in SHOT_QUALITY_TAIL.strip(", ").split(",")]
    lowered = (full_prompt_so_far + suffix).lower()
    missing = [t for t in tail_tokens if t.lower() not in lowered]
    if missing:
        suffix += ", " + ", ".join(missing)
    return suffix


# --------------------------------------------------------------------------
# Shot generation
# --------------------------------------------------------------------------

# v82ls : temporal coherence — detect scene cuts inside a single shot.
# Un shot = 1 moment continu. Si ffmpeg détecte un cut au milieu, c'est
# que Wan2.2 a créé une discontinuité visuelle (téléportation, jump cut,
# changement de fond) = défaut majeur.
def check_temporal_coherence(video_path: str) -> dict:
    """Run ffmpeg `select='gt(scene,0.4)'` filter to detect scene changes
    above 40% magnitude within the shot. Any detected cut = visual break.
    Returns { ok, cuts_count, cuts: [{t, magnitude}], avg_motion }.
    """
    p = Path(video_path)
    if not p.exists():
        return {
            "ok": None,
            "graded": False,
            "cuts_count": 0,
            "cuts": [],
            "error": "fichier video absent; coherence temporelle non mesuree",
        }
    try:
        # showinfo prints frame data on stderr; select with scene filter
        # only keeps frames where scene change > 0.4. We then count those.
        rc, _, stderr = _run([
            _ffmpeg_bin(),
            "-i", video_path,
            "-vf", "select='gt(scene,0.4)',showinfo",
            "-f", "null", "-",
            "-loglevel", "info",
        ], timeout=120)
        # showinfo emits per kept frame :
        #   [Parsed_showinfo_1 @ 0x...] n:0 pts:... pts_time:1.234 ...
        import re as _re
        cuts = []
        for m in _re.finditer(r"pts_time:([0-9.]+)", stderr or ""):
            t = float(m.group(1))
            if t > 0.1:  # ignore very first frame which always counts as scene
                cuts.append({"t": round(t, 2)})

        # Get total duration via showinfo on all frames is too verbose,
        # use ffprobe.
        ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        rc2, stdout2, _ = _run([
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", video_path,
        ], timeout=15)
        try:
            duration = float(stdout2.strip())
        except Exception:
            duration = 5.0

        # OK if 0 or 1 internal cuts (the natural shot boundary). >=2 = bad.
        ok = len(cuts) <= 1
        return {
            "ok": ok,
            "graded": True,
            "cuts_count": len(cuts),
            "cuts": cuts[:5],
            "duration_s": round(duration, 2),
        }
    except Exception as e:
        return {
            "ok": None,
            "graded": False,
            "cuts_count": 0,
            "cuts": [],
            "error": str(e)[:120],
        }


# v82lq : audio integrity check via ffmpeg silencedetect
def has_audio_stream(video_path: str) -> bool:
    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    rc, stdout, _ = _run([
        ffprobe, "-v", "error",
        "-select_streams", "a", "-show_entries", "stream=codec_type",
        "-of", "default=nw=1:nk=1", video_path,
    ], timeout=15)
    return rc == 0 and "audio" in stdout.strip()


def _dialogue_audio_detected(
    has_audio: bool,
    expected_duration_s: float,
    total_silence_s: float,
) -> bool:
    """Return whether a dialogue track contains a meaningful audible region.

    A ratio-only threshold rejects short, perfectly valid utterances padded
    with natural lead-in/out silence (for example a one-second sentence in a
    2.5-second shot). Require both an absolute audible span and a small
    relative span instead, while still rejecting absent or almost fully
    silent tracks.
    """
    duration = max(0.0, float(expected_duration_s or 0.0))
    silence = min(duration, max(0.0, float(total_silence_s or 0.0)))
    audible_s = max(0.0, duration - silence)
    if not has_audio or duration <= 0:
        return False
    minimum_audible_s = min(0.35, max(0.12, duration * 0.10))
    audible_ratio = audible_s / duration
    return audible_s >= minimum_audible_s and audible_ratio >= 0.05


def check_audio_silence(video_path: str, expected_duration_s: float, expected_dialogue: bool = False) -> dict:
    """Run ffmpeg silencedetect on the audio track. Returns:
      { has_audio, total_silence_s, silence_ratio, silences: [{start, end}], ok }
    A short utterance may legitimately occupy less than half of the shot.
    ``ok`` therefore means that a meaningful audible region was measured,
    while ``density_warning`` preserves a truthful sparse-dialogue warning.
    """
    p = Path(video_path)
    if not p.exists():
        return {
            "ok": None,
            "graded": False,
            "has_audio": False,
            "silences": [],
            "error": "fichier video absent; audio non mesure",
        }
    try:
        # Extract audio + run silencedetect filter.
        rc, _, stderr = _run([
            _ffmpeg_bin(), "-i", video_path,
            "-af", "silencedetect=noise=-30dB:duration=0.5",
            "-f", "null", "-",
            "-loglevel", "info",
        ], timeout=60)
        # silencedetect emits messages on stderr like:
        #   [silencedetect @ 0x...] silence_start: 1.234
        #   [silencedetect @ 0x...] silence_end: 3.456 | silence_duration: 2.222
        import re as _re
        starts = [float(m.group(1)) for m in _re.finditer(r"silence_start:\s*([0-9.]+)", stderr)]
        ends = [float(m.group(1)) for m in _re.finditer(r"silence_end:\s*([0-9.]+)", stderr)]
        durs = [float(m.group(1)) for m in _re.finditer(r"silence_duration:\s*([0-9.]+)", stderr)]
        # Pair starts and ends.
        silences = []
        for i, s in enumerate(starts):
            e = ends[i] if i < len(ends) else expected_duration_s
            silences.append({"start": round(s, 2), "end": round(e, 2)})
        total_silence = sum(durs) if durs else 0.0
        ratio = (total_silence / expected_duration_s) if expected_duration_s > 0 else 0.0
        # Detect "no audio" case : if the stream has no audio track at all,
        # silencedetect does nothing. We use ffprobe quick check.
        has_audio = has_audio_stream(video_path)
        audible_s = max(0.0, float(expected_duration_s) - total_silence)
        ok = (
            not expected_dialogue
            or _dialogue_audio_detected(has_audio, expected_duration_s, total_silence)
        )
        density_warning = bool(expected_dialogue and ratio >= 0.65)
        return {
            "ok": ok,
            "graded": True,
            "has_audio": has_audio,
            "total_silence_s": round(total_silence, 2),
            "silence_ratio": round(ratio, 3),
            "audible_s": round(audible_s, 2),
            "density_warning": density_warning,
            "silences": silences[:5],
            "expected_dialogue": expected_dialogue,
        }
    except Exception as e:
        return {
            "ok": None,
            "graded": False,
            "has_audio": False,
            "silences": [],
            "error": str(e)[:120],
        }


# v82lp : extract 3 frames (start, middle, end) for physics + identity validation
def extract_keyframes_triplet(video_path: str, work_dir: "Path", shot_id: int) -> dict:
    """Extract start/middle/end frames so vision LLM can detect:
      - identity drift (character changes between frames)
      - clipping/phasing through objects (physics)
      - floating limbs / no-contact / gravity violations
      - pose discontinuity / teleportation
    Returns { start, mid, end } paths or empty dict on failure.
    """
    try:
        ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        rc, stdout, _ = _run([
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            video_path,
        ], timeout=15)
        if rc != 0:
            return {}
        try:
            duration = float(stdout.strip())
        except Exception:
            duration = 2.0
    except Exception:
        return {}

    out = {}
    times = {
        "start": max(0.05, 0.1),
        "mid": max(0.1, duration / 2.0),
        "end": max(0.1, duration - 0.15),
    }
    for label, t in times.items():
        png_path = work_dir / f"shot_{shot_id:02d}_{label}.png"
        try:
            rc, _, _ = _run([
                _ffmpeg_bin(), "-y",
                "-ss", str(t),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                "-loglevel", "error",
                str(png_path),
            ], timeout=30)
            if rc == 0 and png_path.exists():
                out[label] = str(png_path)
        except Exception:
            pass
    return out


def _ollama_vision_json(
    prompt: str,
    images_b64: list,
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = VISION_MODEL,
    timeout: int = 180,
    num_ctx: int = 6144,
    retries: int = 1,
):
    """v90.3 : appel vision Ollama qui retourne un dict JSON parsé, ou None.

    Les validateurs perdaient ~10-15 % des scores sur "vision JSON parse
    failed" (pensée <think> ou prose autour du JSON), ce qui mettait des
    scores null, faussait le grade et pouvait déclencher de mauvais retries.
    Corrections : strip <think>, extraction par accolades, et un retry.

    v90.5b : NE PAS utiliser format="json" — mesuré sur qwen3-vl:8b, la
    grammaire contrainte + images renvoie une réponse VIDE (done_reason=stop,
    24 s) alors que sans format le modèle sort un JSON propre en 4 s.
    """
    import urllib.request
    for attempt in range(retries + 1):
        try:
            body = json.dumps({
                "model": model,
                "prompt": prompt,
                "images": images_b64,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": num_ctx},
                "keep_alive": "10m",
            }).encode()
            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            text = (data.get("response") or "").strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            first = text.find("{")
            last = text.rfind("}")
            if first >= 0 and last > first:
                payload = json.loads(text[first:last + 1])
                if isinstance(payload, dict):
                    return payload
        except Exception:
            if attempt >= retries:
                raise
        # Parse raté sans exception -> retry silencieux.
    return None


def validate_shot_physics(
    triplet: dict,
    scene: str,
    character_desc: str = "",
    action_contract: str = "",
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = VISION_MODEL,
) -> dict:
    """Vision LLM scores physics coherence + identity continuity over 3 frames.
    Returns { physics_score, identity_score, ok, issues[] }."""
    if not triplet.get("start") or not triplet.get("end"):
        return {
            "physics_score": None,
            "identity_score": None,
            "action_score": None,
            "ok": False,
            "graded": False,
            "issues": ["frames start/end absentes; validation non effectuee"],
        }

    try:
        import base64
        images_b64 = []
        for label in ("start", "mid", "end"):
            p = triplet.get(label)
            if p and Path(p).exists():
                with open(p, "rb") as f:
                    images_b64.append(base64.b64encode(f.read()).decode("ascii"))

        char_part = f"The character is: {character_desc}\n" if character_desc else ""
        action_part = f"The required action/causality is: {action_contract}\n" if action_contract else ""
        prompt = (
            f"You are evaluating a 3-frame strip from a video shot.\n"
            f"The shot was supposed to depict: {scene}\n"
            f"{char_part}\n"
            f"{action_part}\n"
            f"Score THREE aspects 1-10 :\n"
            f"  physics_score : feet on ground when standing? no clipping through objects? gravity respected? "
            f"no floating limbs? contact preserved? (10 = perfect physics, <7 = visible issues)\n"
            f"  identity_score : if a character is required, same character across 3 frames "
            f"(same outfit, face, color, proportions); if no character is required, same main object/setting across frames. "
            f"(10 = stable identity, <7 = drift / different person/object)\n"
            f"  action_score : does the visible action match the requested mechanism and cause/effect? "
            f"Reject random cabling, wrong tools, wrong light source, or an effect that appears in the wrong place. "
            f"(10 = exact coherent action, <7 = action/mechanism incoherent)\n\n"
            f"List concrete issues you see (max 3 short bullets).\n\n"
            f"Reply ONLY with JSON: "
            f'{{"physics_score": <int>, "identity_score": <int>, "action_score": <int>, "issues": ["...", "..."]}}'
        )
        payload = _ollama_vision_json(prompt, images_b64, ollama_url, model, timeout=180, num_ctx=6144)
        if payload is not None:
            try:
                required = ("physics_score", "identity_score", "action_score")
                if any(payload.get(key) is None for key in required):
                    raise ValueError("vision response missing required scores")
                phys = int(payload["physics_score"])
                idn = int(payload["identity_score"])
                action = int(payload["action_score"])
                issues = payload.get("issues") or []
                if not isinstance(issues, list):
                    issues = []
                return {
                    "physics_score": phys,
                    "identity_score": idn,
                    "action_score": action,
                    "ok": phys >= 6 and idn >= 6 and action >= 6,
                    "graded": True,
                    "issues": [str(s)[:200] for s in issues[:3]],
                }
            except Exception:
                pass
        return {
            "physics_score": None,
            "identity_score": None,
            "action_score": None,
            "ok": False,
            "graded": False,
            "issues": ["vision JSON parse failed; validation skipped"],
        }
    except Exception as e:
        return {
            "physics_score": None, "identity_score": None, "action_score": None,
            "ok": False, "graded": False,
            "issues": [f"vision skip: {str(e)[:80]}"],
        }


# v82lk : extract middle frame of a generated shot for vision validation
def extract_middle_frame(video_path: str, output_png: str) -> bool:
    """Extract a single frame at the temporal middle of a video for vision QA."""
    try:
        # First get duration via ffprobe.
        ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        rc, stdout, _ = _run([
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            video_path,
        ], timeout=15)
        if rc != 0:
            return False
        try:
            duration = float(stdout.strip())
        except Exception:
            duration = 2.0
        midpoint = max(0.1, duration / 2.0)
        # Extract that frame.
        rc, _, _ = _run([
            _ffmpeg_bin(), "-y",
            "-ss", str(midpoint),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            "-loglevel", "error",
            output_png,
        ], timeout=30)
        return rc == 0 and Path(output_png).exists()
    except Exception:
        return False


def render_shot_video(
    scene_prompt: str,
    style_id: str,
    duration_s: float,
    width: int,
    height: int,
    output_mp4: str,
    quality_mode: str = "auto",
    anchor_image: str = None,
    negative_prompt: str = None,
    seed: int = None,
    camera: str = None,
    motion_interp: str = "1",
    force_strategy: str = "auto",
) -> dict:
    """Generate a single shot video by delegating to the existing video_generate.py.

    v82l6 : ajout du paramètre `anchor_image`. Si fourni, video_generate.py
    bascule en mode i2v (image-to-video) avec ce keyframe. Pour la cohérence
    de personnage entre shots, on passe la même keyframe FLUX pour tous les
    shots où le speaker est le même personnage.
    """
    fps = 24
    num_frames = max(25, min(97, int(round(duration_s * fps))))
    full_prompt = scene_prompt + style_for(style_id)
    # v84 : valeur de plan (champ storyboard `camera`, jusqu'ici inutilise)
    # + queue qualite positive, dedupliquees contre le prompt existant.
    full_prompt += cinematography_for({"camera": camera or ""}, full_prompt)

    video_script = SERVICES_DIR / "video_generate.py"
    if not video_script.exists():
        return {"ok": False, "error": f"video_generate.py not found at {video_script}"}

    # v83 : adaptive resolution with crash recovery. We attempt (width,height)
    # first ; if the native worker crashes (Windows ACCESS_VIOLATION exit
    # 3221225477 / 0xC0000005) or OOMs — the failure that the Blackwell GPU
    # exhibited and that previously forced a permanent low-res cap — we step
    # the GEN resolution DOWN ~20% and retry instead of failing the whole job.
    # concat_shots upscales the result to the user's target either way, so a
    # downstep trades native detail (recoverable by the upscaler) for a
    # completed render. Preventive fallback, not a restrictive ceiling.
    cw, ch = int(width), int(height)
    diag_path = None
    last = {"ok": False, "error": "render not attempted"}
    for attempt in range(3):
        cmd = [
            sys.executable, str(video_script),
            "--prompt", full_prompt,
            "--output", output_mp4,
            "--width", str(cw),
            "--height", str(ch),
            "--num_frames", str(num_frames),
            "--motion_interp", str(motion_interp),
            "--force_strategy", str(force_strategy),
        ]
        if anchor_image and Path(anchor_image).exists():
            cmd.extend(["--image", anchor_image])
            if attempt == 0:
                emit("anchor", f"i2v from {Path(anchor_image).name}")
        if quality_mode in ("balanced", "premium"):
            cmd.extend(["--quality_mode", quality_mode])
        # v91 : interpolation de mouvement DESACTIVEE pour les plans du cinema.
        # video_generate.py a `--motion_interp 1` par defaut et le pipeline ne
        # le passait jamais : chaque plan etait donc double a 48 im/s par
        # ffmpeg minterpolate. Or l'estimation de mouvement par blocs ne trouve
        # JAMAIS une rotation sur une roue en aliasing — elle trouve une
        # translation, et renforce donc visuellement le glissement lateral tout
        # en ajoutant du ghosting sur les rayons. Le montage final est de toute
        # facon assemble a 24 im/s.
        cmd.extend(["--motion_interp", "0"])
        # v82ln : negative prompt anti-artefacts. Best-effort — argparse ignores
        # the flag on revs that don't support it.
        merged_negative = combine_negative_prompt(negative_prompt or "", style_negative_for(style_id))
        if merged_negative:
            cmd.extend(["--negative_prompt", merged_negative])
        # v82lo : seed pour reproduction stricte d'un shot (re-render identique).
        if seed is not None:
            cmd.extend(["--seed", str(int(seed))])

        retry_tag = f" retry#{attempt}" if attempt else ""
        emit("shot_render", f"Video {cw}x{ch} {num_frames}f{' i2v' if anchor_image else ' t2v'}{retry_tag}")
        segment_timeout_s = max(
            2400,
            int(os.environ.get("AURORA_VIDEO_SEGMENT_TIMEOUT_S", "7200")),
        )
        rc, stdout, stderr = _run(cmd, timeout=segment_timeout_s)

        # v82m0 : full stdout+stderr to disk for diagnostic (the frontend reads
        # it from job_dir). Last attempt wins the log.
        try:
            diag_path = Path(output_mp4).parent / f"{Path(output_mp4).stem}.render_log.txt"
            diag_path.write_text(
                f"=== attempt {attempt} @ {cw}x{ch} ===\n"
                f"=== STDOUT ===\n{stdout or ''}\n\n=== STDERR ===\n{stderr or ''}",
                encoding="utf-8",
            )
        except Exception:
            pass

        worker_result = None
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                candidate = json.loads(line)
            except Exception:
                continue
            if isinstance(candidate, dict):
                worker_result = candidate
                break
        if rc == 0 and Path(output_mp4).exists():
            actual_model = (worker_result or {}).get("model") or "moteur non déclaré"
            actual_strategy = (worker_result or {}).get("strategy") or "strategie non déclarée"
            emit("shot_backend", f"{actual_model} via {actual_strategy}")
            return {
                "ok": True,
                "mp4": output_mp4,
                "frames": num_frames,
                "gen_w": cw,
                "gen_h": ch,
                "downsteps": attempt,
                "model": (worker_result or {}).get("model"),
                "strategy": (worker_result or {}).get("strategy"),
                "render_truth": (worker_result or {}).get("render_truth"),
                "warnings": (worker_result or {}).get("warnings", []),
                "validation": (worker_result or {}).get("validation"),
            }

        err_text = (stderr or stdout or "")
        hint = ""
        low = err_text.lower()
        if "triton" in low:
            hint = " [hint: triton missing — pip install triton-windows or --quality_mode balanced]"
        elif "out of memory" in low or "cuda oom" in low:
            hint = " [hint: VRAM OOM]"
        elif "model" in low and "not found" in low:
            hint = " [hint: modèle Wan2.2 absent — modele/comfyui/comfyui/models/diffusion_models/]"
        last = {
            "ok": False,
            "error": (f"video_generate.py exit 0 but no output file. stderr tail:\n{err_text[-512:]}"
                      if rc == 0 else err_text[-1024:] + hint),
            "rc": rc,
            "diag_log": str(diag_path) if diag_path else None,
        }

        # Only a native crash / OOM is worth a lower-res retry ; a model-missing
        # or logic error would fail identically at any resolution.
        if attempt >= 2 or not _is_native_crash(rc, err_text):
            break
        cw = max(256, (int(cw * 0.8) // 8) * 8)
        ch = max(256, (int(ch * 0.8) // 8) * 8)
        emit("shot_retry", f"crash natif detecte (rc={rc}) -> retry a {cw}x{ch}")

    return last


# v83 : detect the native-worker crash signatures that warrant a lower-res
# retry. Windows ACCESS_VIOLATION surfaces as exit 3221225477 (unsigned) /
# -1073741819 (signed) ; CUDA/driver faults print recognizable substrings.
def _is_native_crash(rc: int, err_text: str) -> bool:
    if rc in (3221225477, -1073741819):
        return True
    low = (err_text or "").lower()
    return any(s in low for s in (
        "access violation", "0xc0000005", "3221225477",
        "out of memory", "cuda oom", "cuda error",
        "cublas", "cudnn", "illegal memory access",
    ))


def make_still_video(image_path: str, duration_s: float, output_mp4: str, width: int, height: int) -> dict:
    """Create a short stable clip from a character keyframe for lipsync shots."""
    if not image_path or not Path(image_path).exists():
        return {"ok": False, "error": "missing still image source"}
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )
    rc, stdout, stderr = _run([
        _ffmpeg_bin(), "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(max(0.5, float(duration_s or 2.0))),
        "-r", "24",
        "-vf", vf,
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-movflags", "+faststart",
        output_mp4,
    ], timeout=60)
    if rc == 0 and Path(output_mp4).exists():
        return {"ok": True, "mp4": output_mp4}
    return {"ok": False, "error": (stderr or stdout or "")[-800:]}


def probe_video_size(video_path: str) -> tuple:
    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    rc, stdout, _ = _run([
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path,
    ], timeout=30)
    if rc != 0:
        return (0, 0)
    try:
        raw = (stdout or "").strip().splitlines()[0]
        w, h = raw.split("x", 1)
        return (int(w), int(h))
    except Exception:
        return (0, 0)


def probe_video_duration(video_path: str) -> float:
    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    rc, stdout, _ = _run([
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ], timeout=30)
    if rc != 0:
        return 0.0
    try:
        return max(0.0, float((stdout or "0").strip()))
    except Exception:
        return 0.0


def probe_audio_duration(audio_path: str) -> float:
    """Durée réelle d'un fichier audio (wav/mp3) via ffprobe."""
    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    rc, stdout, _ = _run([
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ], timeout=30)
    if rc != 0:
        return 0.0
    try:
        return max(0.0, float((stdout or "0").strip()))
    except Exception:
        return 0.0


def extract_last_frame(video_path: str, output_png: str) -> bool:
    """Extract the final frame of a clip (i2v chaining anchor for the next segment)."""
    rc, _, _ = _run([
        _ffmpeg_bin(), "-y",
        "-sseof", "-0.10",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-loglevel", "error",
        output_png,
    ], timeout=30)
    if rc == 0 and Path(output_png).exists():
        return True
    # Fallback : some very short clips reject -sseof; grab last frame via -update.
    rc, _, _ = _run([
        _ffmpeg_bin(), "-y",
        "-i", video_path,
        "-update", "1",
        "-q:v", "2",
        "-loglevel", "error",
        output_png,
    ], timeout=60)
    return rc == 0 and Path(output_png).exists()


def _laplacian_variance(image_path: str) -> float:
    """Mesure de netteté sans dépendance OpenCV (Laplacien discret)."""
    try:
        import numpy as np
        from PIL import Image

        gray = np.asarray(Image.open(image_path).convert("L"), dtype=np.float32)
        if gray.shape[0] < 3 or gray.shape[1] < 3:
            return 0.0
        center = gray[1:-1, 1:-1]
        laplacian = (
            -4.0 * center
            + gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
        )
        return float(np.var(laplacian))
    except Exception:
        return 0.0


def extract_sharp_tail_frame(video_path: str, output_png: str, samples: int = 5) -> bool:
    """Choisit l'ancre la plus nette dans la dernière seconde du segment.

    Une dernière image en plein flou de mouvement propageait ce flou au segment
    suivant. On échantillonne la queue, classe par variance du Laplacien, puis
    garde la meilleure. Le chemin historique reste le repli explicite.
    """
    source = Path(video_path)
    target = Path(output_png)
    if not source.is_file():
        return False
    duration = probe_video_duration(str(source))
    sample_count = max(3, min(9, int(samples)))
    start = max(0.0, duration - 1.0)
    sample_dir = target.parent / f".{target.stem}_sharp_samples"
    try:
        if sample_dir.exists():
            shutil.rmtree(sample_dir)
        sample_dir.mkdir(parents=True, exist_ok=True)
        pattern = sample_dir / "frame_%02d.png"
        rc, _, _ = _run([
            _ffmpeg_bin(), "-y",
            "-ss", f"{start:.3f}",
            "-i", str(source),
            "-vf", f"fps={sample_count}",
            "-frames:v", str(sample_count),
            "-loglevel", "error",
            str(pattern),
        ], timeout=60)
        candidates = sorted(sample_dir.glob("frame_*.png")) if rc == 0 else []
        if candidates:
            best = max(candidates, key=lambda item: _laplacian_variance(str(item)))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best, target)
            return target.is_file()
    except Exception:
        pass
    finally:
        try:
            if sample_dir.exists():
                shutil.rmtree(sample_dir)
        except Exception:
            pass
    return extract_last_frame(str(source), str(target))


def extend_video_to_duration(video_path: str, target_s: float, output_mp4: str) -> dict:
    """Prolonge un clip jusqu'à target_s en clonant la dernière frame (tpad).

    v90 : utilisé quand la parole TTS dure plus longtemps que le clip généré,
    pour ne plus JAMAIS couper un dialogue en plein milieu de phrase.
    """
    current = probe_video_duration(video_path)
    if current <= 0:
        return {"ok": False, "error": "could not probe video duration"}
    pad = target_s - current
    if pad <= 0.05:
        return {"ok": True, "mp4": video_path, "padded_s": 0.0}
    cmd = [
        _ffmpeg_bin(), "-y",
        "-i", video_path,
        "-vf", f"tpad=stop_mode=clone:stop_duration={pad + 0.05:.3f},format=yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "17",
    ]
    if has_audio_stream(video_path):
        cmd.extend(["-af", f"apad=pad_dur={pad + 0.05:.3f}", "-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.append("-an")
    cmd.extend(["-movflags", "+faststart", "-loglevel", "error", output_mp4])
    rc, _, err = _run(cmd, timeout=300)
    if rc != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": (err or "")[-300:]}
    return {"ok": True, "mp4": output_mp4, "padded_s": round(pad, 2)}


def mux_audio_fit(video_mp4: str, audio_wav: str, output_mp4: str, tail_s: float = 0.25) -> dict:
    """Mux voix + vidéo SANS -shortest : la parole n'est jamais tronquée.

    v90 : si l'audio est plus long que la vidéo, la vidéo est prolongée
    (dernière frame clonée) jusqu'à couvrir la parole + une petite respiration.
    Si l'audio est plus court, il est paddé de silence jusqu'à la fin du clip.
    """
    vdur = probe_video_duration(video_mp4)
    adur = probe_audio_duration(audio_wav)
    if vdur <= 0:
        return {"ok": False, "error": "could not probe video duration"}
    src_video = video_mp4
    if adur > vdur + 0.05:
        extended = str(Path(output_mp4).with_suffix(".vext.mp4"))
        ext = extend_video_to_duration(video_mp4, adur + tail_s, extended)
        if ext.get("ok"):
            src_video = ext.get("mp4") or extended
            emit("audio_fit", f"video +{ext.get('padded_s', 0)}s pour couvrir la parole ({adur:.1f}s)")
        else:
            emit("audio_fit_warn", f"extension video echouee: {ext.get('error', '')[:120]}")
    final_dur = max(probe_video_duration(src_video), adur)
    cmd = [
        _ffmpeg_bin(), "-y",
        "-i", src_video,
        "-i", audio_wav,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-af", "apad",
        "-t", f"{final_dur:.3f}",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_mp4,
    ]
    rc, _, err = _run(cmd, timeout=180)
    if rc != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": (err or "")[-300:]}
    return {"ok": True, "mp4": output_mp4, "video_extended": src_video != video_mp4}


# v90 : segmentation des plans longs. Wan2.2/LTX plafonnent à ~97 frames (~4 s
# à 24 fps) — un plan storyboard de 6-8 s sortait silencieusement à 3-4 s,
# d'où la dérive cumulative sur les vidéos longues. On découpe en segments
# équilibrés <= 97 frames, chaînés visuellement par i2v sur la dernière frame.
SEGMENT_FPS = 24
SEGMENT_MAX_FRAMES = 97
SEGMENT_MIN_FRAMES = 25
SEGMENT_MAX_COUNT = 5


def plan_shot_segments(duration_s: float, fps: int = SEGMENT_FPS) -> list:
    """Découpe une durée en segments équilibrés compatibles Wan et LTX.

    LTX recommande 8k+1 images et le VAE Wan accepte cette même grille. On
    choisit donc la combinaison la plus courte qui couvre toute la durée
    demandée, sans jamais raccourcir silencieusement un plan.
    """
    total = int(round(max(0.5, float(duration_s)) * fps))
    total = max(SEGMENT_MIN_FRAMES, total)
    hard_cap = SEGMENT_MAX_FRAMES * SEGMENT_MAX_COUNT
    total = min(total, hard_cap)
    import math
    import itertools

    allowed = list(range(SEGMENT_MIN_FRAMES, SEGMENT_MAX_FRAMES + 1, 8))
    count = min(
        SEGMENT_MAX_COUNT,
        max(1, math.ceil(total / SEGMENT_MAX_FRAMES)),
    )
    candidates = (
        combo
        for combo in itertools.combinations_with_replacement(allowed, count)
        if sum(combo) >= total
    )
    best = min(
        candidates,
        key=lambda combo: (sum(combo), max(combo) - min(combo)),
    )
    # Les plus longs segments d'abord limitent la dérive d'identité avant la
    # première ancre i2v tout en gardant l'ensemble aussi équilibré que possible.
    return sorted(best, reverse=True)


def concat_segments(segment_files: list, output_mp4: str) -> dict:
    """Concat local des segments d'UN plan (pas d'upscale, pas d'audio ajouté)."""
    if not segment_files:
        return {"ok": False, "error": "no segments"}
    if len(segment_files) == 1:
        try:
            shutil.copy(segment_files[0], output_mp4)
            return {"ok": True, "mp4": output_mp4}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
    list_file = Path(output_mp4).with_suffix(".segments.txt")
    with list_file.open("w", encoding="utf-8") as f:
        for seg in segment_files:
            p = str(Path(seg).resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{p}'\n")
    rc, _, err = _run([
        _ffmpeg_bin(), "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_mp4,
    ], timeout=600)
    try:
        list_file.unlink()
    except Exception:
        pass
    if rc != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": (err or "")[-300:]}
    return {"ok": True, "mp4": output_mp4}


def render_long_shot(
    scene_prompt: str,
    style_id: str,
    duration_s: float,
    width: int,
    height: int,
    output_mp4: str,
    work_dir: Path,
    shot_id: int,
    quality_mode: str = "auto",
    anchor_image: str = None,
    negative_prompt: str = None,
    seed: int = None,
    camera: str = None,
    attempt_tag: str = "",
    motion_interp: str = "1",
    force_strategy: str = "auto",
) -> dict:
    """Rendu d'un plan de durée arbitraire via segments Wan chaînés i2v.

    v90 : chaque segment > 1 démarre sur la dernière frame du précédent
    (continuité réelle de décor, sujet et mouvement au sein du plan), avec un
    prompt de continuation pour éviter que Wan réinvente la scène.
    """
    segments = plan_shot_segments(duration_s)
    if len(segments) == 1:
        result = render_shot_video(
            scene_prompt=scene_prompt,
            style_id=style_id,
            duration_s=segments[0] / SEGMENT_FPS,
            width=width,
            height=height,
            output_mp4=output_mp4,
            quality_mode=quality_mode,
            anchor_image=anchor_image,
            negative_prompt=negative_prompt,
            seed=seed,
            camera=camera,
            motion_interp=motion_interp,
            force_strategy=force_strategy,
        )
        if result.get("ok"):
            delivered = probe_video_duration(str(result.get("mp4") or output_mp4))
            if delivered + 0.20 < duration_s:
                return {
                    **result,
                    "ok": False,
                    "error": (
                        f"plan trop court: {delivered:.2f}s mesurées pour "
                        f"{duration_s:.2f}s demandées; aucun succès partiel"
                    ),
                    "requested_duration_s": duration_s,
                    "delivered_duration_s": delivered,
                }
            result["requested_duration_s"] = duration_s
            result["delivered_duration_s"] = delivered
        return result

    emit("shot_segments", f"plan long {duration_s:.1f}s -> {len(segments)} segments chaines i2v")
    seg_files = []
    segment_results = []
    seg_anchor = anchor_image
    for si, frames in enumerate(segments, 1):
        seg_out = work_dir / f"shot_{shot_id:02d}{attempt_tag}_seg{si}.mp4"
        seg_prompt = scene_prompt
        if si > 1:
            seg_prompt = (
                f"{scene_prompt}. Seamless continuation of the exact same continuous take: "
                f"same subject, same setting, same lighting, the motion carries on naturally."
            )
        result = render_shot_video(
            scene_prompt=seg_prompt,
            style_id=style_id,
            duration_s=frames / SEGMENT_FPS,
            width=width,
            height=height,
            output_mp4=str(seg_out),
            quality_mode=quality_mode,
            anchor_image=seg_anchor,
            negative_prompt=negative_prompt,
            seed=(seed + si * 17) if seed is not None else None,
            camera=camera,
            motion_interp=motion_interp,
            force_strategy=force_strategy,
        )
        if not result.get("ok"):
            emit(
                "shot_segment_fail",
                f"segment {si}/{len(segments)} échoué : durée demandée non livrable",
            )
            return {
                **result,
                "ok": False,
                "error": (
                    f"segment {si}/{len(segments)} échoué; aucun succès partiel "
                    f"n'est présenté comme le plan complet: {result.get('error', '')}"
                ),
                "failed_segment": si,
                "completed_segments": len(seg_files),
            }
        seg_files.append(str(seg_out))
        segment_results.append(result)
        last_png = work_dir / f"shot_{shot_id:02d}{attempt_tag}_seg{si}_last.png"
        if extract_sharp_tail_frame(str(seg_out), str(last_png)):
            seg_anchor = str(last_png)
        else:
            seg_anchor = None

    cat = concat_segments(seg_files, output_mp4)
    if not cat.get("ok"):
        return {"ok": False, "error": f"segment concat failed: {cat.get('error')}"}
    delivered_duration = probe_video_duration(output_mp4)
    if delivered_duration + 0.20 < duration_s:
        return {
            "ok": False,
            "error": (
                f"plan concaténé trop court: {delivered_duration:.2f}s mesurées "
                f"pour {duration_s:.2f}s demandées; aucun succès partiel"
            ),
            "mp4": output_mp4,
            "requested_duration_s": duration_s,
            "delivered_duration_s": delivered_duration,
            "segments": len(seg_files),
            "segment_results": segment_results,
        }
    models = list(dict.fromkeys(
        str(item.get("model")) for item in segment_results if item.get("model")
    ))
    strategies = list(dict.fromkeys(
        str(item.get("strategy")) for item in segment_results if item.get("strategy")
    ))
    warnings = [
        warning
        for item in segment_results
        for warning in (item.get("warnings") or [])
        if isinstance(warning, dict)
    ]
    return {
        "ok": True,
        "mp4": output_mp4,
        "segments": len(seg_files),
        "segment_results": segment_results,
        "models": models,
        "strategies": strategies,
        "warnings": warnings,
        "anchor_strategy": "sharpest_laplacian_tail_frame",
        "requested_duration_s": duration_s,
        "delivered_duration_s": delivered_duration,
    }


def apply_text_locks(video_path: str, output_mp4: str, work_dir: Path, shot_id: int, text_locks) -> dict:
    """Burn exact short text requested by the storyboard before visual QA.

    Diffusion video is unreliable for legible short codes ("K4", labels,
    gauges). The motion remains generated, while this pass locks the literal
    text so validation can judge the real requested output.
    """
    if not text_locks:
        return {"ok": True, "mp4": video_path, "applied": 0}
    if isinstance(text_locks, dict):
        locks = [text_locks]
    elif isinstance(text_locks, list):
        locks = [lock for lock in text_locks if isinstance(lock, dict)]
    else:
        return {"ok": False, "error": "invalid text_locks format"}
    if not locks:
        return {"ok": True, "mp4": video_path, "applied": 0}

    width, height = probe_video_size(video_path)
    if width <= 0 or height <= 0:
        return {"ok": False, "error": "could not probe video size"}
    duration = probe_video_duration(video_path)
    if duration <= 0:
        return {"ok": False, "error": "could not probe video duration"}

    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont

        def as_color(value, default):
            if isinstance(value, str):
                value = value.strip().lstrip("#")
                if len(value) in (6, 8):
                    vals = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
                    if len(vals) == 3:
                        vals.append(255)
                    return tuple(vals[:4])
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                vals = [int(max(0, min(255, float(v)))) for v in value[:4]]
                if len(vals) == 3:
                    vals.append(255)
                return tuple(vals[:4])
            return default

        font_candidates = [
            "C:\\Windows\\Fonts\\segoeuib.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        overlay_paths = []
        for lock_idx, lock in enumerate(locks, start=1):
            text = str(lock.get("text") or "").strip()
            if not text:
                continue
            x = int(float(lock.get("x", 0)))
            y = int(float(lock.get("y", 0)))
            font_size = int(float(lock.get("font_size") or max(32, height * 0.22)))
            font_path = str(lock.get("font_path") or "")
            if not font_path or not Path(font_path).exists():
                font_path = next((p for p in font_candidates if Path(p).exists()), "")
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            fill = as_color(lock.get("fill"), (150, 245, 255, 255))
            glow = as_color(lock.get("glow"), (80, 220, 255, 180))
            stroke = as_color(lock.get("stroke"), (15, 120, 180, 210))

            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            for radius, alpha_mul in ((16, 0.35), (8, 0.55), (3, 0.85)):
                layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                g = (glow[0], glow[1], glow[2], int(glow[3] * alpha_mul))
                d.text((x, y), text, font=font, fill=g, stroke_width=2, stroke_fill=g)
                canvas = Image.alpha_composite(canvas, layer.filter(ImageFilter.GaussianBlur(radius=radius)))

            d = ImageDraw.Draw(canvas)
            d.text((x, y), text, font=font, fill=fill, stroke_width=2, stroke_fill=stroke)
            overlay_path = work_dir / f"shot_{shot_id:02d}_textlock_{lock_idx}.png"
            canvas.save(overlay_path)
            overlay_paths.append((overlay_path, float(lock.get("start_s", 0.0)), lock.get("end_s")))

        if not overlay_paths:
            return {"ok": True, "mp4": video_path, "applied": 0}

        cmd = [_ffmpeg_bin(), "-y", "-i", video_path]
        for overlay_path, _, _ in overlay_paths:
            cmd.extend(["-loop", "1", "-i", str(overlay_path)])

        filter_parts = []
        current = "[0:v]"
        for idx, (_, start_s, end_s) in enumerate(overlay_paths, start=1):
            out_label = f"[tl{idx}]"
            if end_s is None:
                enable = f"gte(t,{max(0.0, start_s):.3f})"
            else:
                enable = f"between(t,{max(0.0, start_s):.3f},{max(0.0, float(end_s)):.3f})"
            filter_parts.append(f"{current}[{idx}:v]overlay=0:0:enable='{enable}'{out_label}")
            current = out_label
        filter_parts.append(f"{current}format=yuv420p[vout]")

        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "[vout]",
            "-t", f"{duration:.3f}",
        ])
        if has_audio_stream(video_path):
            cmd.extend(["-map", "0:a:0", "-c:a", "copy"])
        else:
            cmd.append("-an")
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "16",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-loglevel", "error",
            output_mp4,
        ])
        rc, stdout, stderr = _run(cmd, timeout=180)
        if rc == 0 and Path(output_mp4).exists():
            return {"ok": True, "mp4": output_mp4, "applied": len(overlay_paths)}
        return {"ok": False, "error": (stderr or stdout or "")[-800:]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def make_dialogue_source_image(
    character_image: str,
    background_image: str,
    output_png: str,
    width: int,
    height: int,
) -> dict:
    """Composite a stable character portrait over the current scene background."""
    if not character_image or not Path(character_image).exists():
        return {"ok": False, "error": "missing character image"}
    if not background_image or not Path(background_image).exists():
        return {"ok": False, "error": "missing background image"}
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        def cover_resize(img, w, h):
            scale = max(w / img.width, h / img.height)
            resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
            left = max(0, (resized.width - w) // 2)
            top = max(0, (resized.height - h) // 2)
            return resized.crop((left, top, left + w, top + h))

        bg = cover_resize(Image.open(background_image).convert("RGB"), width, height)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
        bg = ImageEnhance.Brightness(bg).enhance(0.78)
        raw_char = Image.open(character_image).convert("RGBA")

        try:
            from rembg import remove
            cutout = remove(raw_char)
            if cutout.mode != "RGBA":
                cutout = cutout.convert("RGBA")
            alpha = cutout.getchannel("A")
            if alpha.getextrema()[0] < 250:
                char_rgba = cover_resize(cutout, width, height)
                fg_alpha = char_rgba.getchannel("A").filter(ImageFilter.GaussianBlur(radius=0.6))
                composed = Image.composite(char_rgba.convert("RGB"), bg, fg_alpha)
                Path(output_png).parent.mkdir(parents=True, exist_ok=True)
                composed.save(output_png)
                return {"ok": True, "image": output_png, "method": "rembg"}
        except Exception:
            pass

        char = cover_resize(raw_char.convert("RGB"), width, height)

        # Portrait keyframes use a clean studio background. Flood-fill from the
        # image edges so similarly colored skin/clothes inside the face are not
        # cut out just because their RGB value is near the background color.
        samples = []
        step = max(1, min(width, height) // 80)
        for x in range(0, width, step):
            samples.append(char.getpixel((x, 0)))
            samples.append(char.getpixel((x, height - 1)))
        for y in range(0, height, step):
            samples.append(char.getpixel((0, y)))
            samples.append(char.getpixel((width - 1, y)))
        bg_color = tuple(int(sum(c[i] for c in samples) / max(1, len(samples))) for i in range(3))

        pix = char.load()
        visited = bytearray(width * height)
        bg_mask = Image.new("L", (width, height), 0)
        mask_pix = bg_mask.load()
        queue = []
        for x in range(width):
            queue.append((x, 0))
            queue.append((x, height - 1))
        for y in range(height):
            queue.append((0, y))
            queue.append((width - 1, y))

        threshold = 125
        while queue:
            x, y = queue.pop()
            if x < 0 or y < 0 or x >= width or y >= height:
                continue
            idx = y * width + x
            if visited[idx]:
                continue
            visited[idx] = 1
            r, g, b = pix[x, y]
            dist = abs(r - bg_color[0]) + abs(g - bg_color[1]) + abs(b - bg_color[2])
            if dist > threshold:
                continue
            mask_pix[x, y] = 255
            queue.append((x + 1, y))
            queue.append((x - 1, y))
            queue.append((x, y + 1))
            queue.append((x, y - 1))

        fg_alpha = ImageOps.invert(bg_mask).filter(ImageFilter.GaussianBlur(radius=1.5))
        composed = Image.composite(char, bg, fg_alpha)
        Path(output_png).parent.mkdir(parents=True, exist_ok=True)
        composed.save(output_png)
        return {"ok": True, "image": output_png}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def validate_rendered_shot(
    final_mp4: str,
    work_dir: "Path",
    shot_id: int,
    scene: str,
    style_id: str,
    character_desc: str = "",
    action_contract: str = "",
    attempt: int = 1,
) -> dict:
    triplet = extract_keyframes_triplet(str(final_mp4), work_dir, shot_id)
    scene_score_data = {
        "score": None,
        "reason": "frame extraction failed",
        "ok": False,
        "graded": False,
    }
    if triplet.get("mid"):
        scene_score_data = validate_keyframe_with_vision(
            triplet["mid"],
            scene + style_validation_contract(style_id),
        )

    phys_data = validate_shot_physics(
        triplet,
        scene,
        character_desc=character_desc,
        action_contract=action_contract,
    )
    qa = {
        "shot_id": shot_id,
        "scene_excerpt": scene[:120],
        "score": scene_score_data.get("score"),
        "reason": scene_score_data.get("reason"),
        "ok": scene_score_data.get("ok"),
        "physics_score": phys_data.get("physics_score"),
        "identity_score": phys_data.get("identity_score"),
        "action_score": phys_data.get("action_score"),
        "issues": phys_data.get("issues", []),
        "graded": (
            scene_score_data.get("score") is not None
            and phys_data.get("physics_score") is not None
            and phys_data.get("identity_score") is not None
            and phys_data.get("action_score") is not None
        ),
        "attempt": attempt,
        "avg_score": round(shot_quality_average({
            "score": scene_score_data.get("score"),
            "physics_score": phys_data.get("physics_score"),
            "identity_score": phys_data.get("identity_score"),
            "action_score": phys_data.get("action_score"),
        }), 2),
    }
    return qa


# --------------------------------------------------------------------------
# v82l6 : Character keyframe pre-generation via FLUX (anchor for i2v)
# --------------------------------------------------------------------------

def _object_judge_model() -> str:
    """Modele de vision pour l'examen de completude d'un objet.

    Un pedalier fait quelques dizaines de pixels : c'est exactement la tache
    ou un modele 8B decroche. qwen3-vl:30b est installe sur cette machine et
    n'etait utilise par aucune porte. Il est nettement plus lent, ce qui est
    sans importance ici : la reference d'un objet est generee une seule fois
    par film et conditionne tous les plans qu'elle ancre.
    """
    return os.environ.get("AURORA_OBJECT_VISION_MODEL", "qwen3-vl:30b")


def validate_object_completeness(
    image_path: str,
    description: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = None,
) -> dict:
    """Verifie qu'une reference d'OBJET est anatomiquement COMPLETE.

    Le score de ressemblance ne suffit pas pour un objet mecanique : une
    reference peut "ressembler beaucoup" a un velo et n'avoir NI PEDALES NI
    CHAINE. C'est arrive : le velo canonique du film Natsu etait note bon par
    la porte de ressemblance alors qu'il lui manquait les pedales, et l'objet
    incomplet s'est propage a tous les plans qu'il ancrait.

    On pose donc au juge une question differente et plus dure : non pas
    "est-ce que ca ressemble ?" mais "QU'EST-CE QUI MANQUE ?". Demander une
    LISTE de pieces manquantes force un examen piece par piece, la ou une note
    globale invite a l'indulgence.

    Retourne { ok, missing[], malformed[], reason, graded }. Une panne vision
    ne fabrique jamais un succes : ok=False et graded=False.
    """
    model = model or _object_judge_model()
    try:
        import base64
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        prompt = (
            "You are a strict technical illustrator reviewing a reference image "
            "of a single object.\n"
            f"The object is supposed to be: {description}\n\n"
            "Examine it part by part. Real objects have ALL their functional "
            "parts: a bicycle has pedals, a crank, a chain, two complete wheels "
            "with hubs and spokes, a saddle, handlebars, brakes; a car has four "
            "wheels, mirrors, door handles; and so on.\n\n"
            "List EVERY essential part that is MISSING from the image, and every "
            "part that is present but MALFORMED (bent, fused, floating, "
            "duplicated, anatomically impossible).\n"
            "Also report whether any PERSON or human body part appears: a "
            "reference of an object must contain the object ALONE.\n\n"
            "Reply ONLY with JSON: {\"missing\": [\"...\"], \"malformed\": "
            "[\"...\"], \"person_present\": true|false}"
        )
        payload = _ollama_vision_json(prompt, [b64], ollama_url, model,
                                      timeout=120, num_ctx=4096)
        if payload is None:
            return {"ok": False, "missing": [], "malformed": [],
                    "reason": "vision JSON parse failed", "graded": False}
        missing = [str(x)[:60] for x in (payload.get("missing") or [])][:8]
        malformed = [str(x)[:60] for x in (payload.get("malformed") or [])][:8]
        person = bool(payload.get("person_present"))
        problems = []
        if missing:
            problems.append("pieces manquantes: " + ", ".join(missing))
        if malformed:
            problems.append("pieces deformees: " + ", ".join(malformed))
        if person:
            problems.append("une personne apparait alors que l'objet doit etre seul")
        return {
            "ok": not problems,
            "missing": missing,
            "malformed": malformed,
            "person_present": person,
            "reason": " | ".join(problems) or "objet complet",
            "graded": True,
        }
    except Exception as e:
        return {"ok": False, "missing": [], "malformed": [],
                "reason": f"vision skip: {str(e)[:80]}", "graded": False}


def validate_keyframe_with_vision(
    image_path: str,
    description: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = VISION_MODEL,
) -> dict:
    """v82la : vision-LLM quality gate. Send keyframe PNG to qwen3-vl via
    Ollama with a prompt asking to rate 1-10 how well the image matches
    the character description.

    Returns { ok, score, reason, graded }. Une panne vision ne fabrique jamais
    une note de passage : le rendu continue mais reste explicitement non note.
    """
    try:
        import base64
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        prompt = (
            f"You are a strict art director. Look at this character keyframe.\n"
            f"It is supposed to depict: {description}\n\n"
            f"Score 1-10 how well the image matches this description.\n"
            f"10 = perfect match (every visual cue present and accurate).\n"
            f"7 = acceptable (most cues present, minor issues).\n"
            f"<7 = poor match (key visual cues wrong/missing).\n"
            f"If a SIGNATURE garment or accessory explicitly named in the description "
            f"(a specific hat type, a named prop, a distinctive coat) is wrong or "
            f"replaced by a different type, score at most 5.\n\n"
            f"Reply ONLY with a JSON object: {{\"score\": <int 1-10>, \"reason\": \"<one short sentence>\"}}"
        )
        payload = _ollama_vision_json(prompt, [b64], ollama_url, model, timeout=120, num_ctx=4096)
        if payload is not None:
            try:
                score = int(payload.get("score", 0))
                reason = str(payload.get("reason", ""))[:200]
                return {
                    "ok": score >= 7,
                    "score": score,
                    "reason": reason,
                    "graded": True,
                }
            except Exception:
                pass
        return {
            "ok": False,
            "score": None,
            "reason": "vision JSON parse failed",
            "graded": False,
        }
    except Exception as e:
        return {
            "ok": False,
            "score": None,
            "reason": f"vision skip: {str(e)[:80]}",
            "graded": False,
        }


def _rewrite_desc_visually(
    desc: str,
    reject_reason: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = "gemma3:12b",
) -> str:
    """v90.6 : réécrit une description de personnage pour FLUX quand un élément
    NOMMÉ est systématiquement raté (mesuré : "deerstalker hat" -> fedora sur
    3 seeds). Le LLM local remplace le nom par une description visuelle de la
    forme — pas de glossaire en dur, ça marche pour n'importe quel élément.
    A/B mesuré : qwen2.5:7b décrit le MAUVAIS chapeau (il ne connaît pas le
    deerstalker) ; gemma3:12b le décrit correctement (ear flaps tied on top).
    Un seul appel court — Ollama décharge sur CPU si FLUX occupe la VRAM."""
    prompt = (
        "An image generator failed to render a character correctly.\n"
        f"Character description: {desc}\n"
        f"Reviewer feedback: {reject_reason}\n"
        "Rewrite the character description in english for the image generator. "
        "Replace any NAMED garment or accessory that the generator got wrong with "
        "an explicit visual description of its shape, materials and how it is worn "
        "(do not use its proper name). Keep everything else identical. "
        "Max 50 words. Reply with the rewritten description only."
    )
    try:
        import urllib.request
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 2048},
            "keep_alive": "2m",
        }).encode()
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            text = (json.loads(resp.read().decode()).get("response") or "").strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = text.strip('"').strip().replace("\n", " ")
        if 10 < len(text) < 400:
            return text
    except Exception:
        pass
    return desc


def pregenerate_character_keyframes(
    characters: dict,
    work_dir: "Path",
    style_id: str,
    width: int,
    height: int,
) -> dict:
    """For each character with a `description`, pre-render a portrait keyframe
    via flux_reference_synth.py. Returns { name: keyframe_path } so subsequent
    shots can anchor on it for visual continuity.

    Falls back gracefully if FLUX/Comfy isn't available — empty dict means
    shots will be text-to-video without anchor (degraded but functional).
    """
    if not characters:
        return {}

    flux_script = SERVICES_DIR / "flux_reference_synth.py"
    if not flux_script.exists():
        emit("char_warn", "flux_reference_synth.py absent, skip keyframes")
        return {}

    keyframes = {}
    style_suffix = style_for(style_id)

    for idx, (name, meta) in enumerate(characters.items(), 1):
        if not name:
            continue
        desc = (meta.get("description") or "").strip()
        if not desc:
            continue
        # Composite prompt : character description + style. Humanoids get a
        # portrait; drones/objects get a centered product-like concept view so
        # their silhouette is not accidentally turned into a face.
        # v91 : `anchor_as_object` prime sur l'heuristique par mots-cles pour
        # decider portrait vs objet isole (cf. build_character_keyframe_prompt).
        entity_is_object = bool(meta.get("anchor_as_object"))
        prompt = build_character_keyframe_prompt(desc, style_suffix, entity_is_object)
        keyframe_path = work_dir / f"char_{idx}_{name.lower().replace(' ', '_')}.png"
        provided_keyframe = (
            meta.get("keyframe_path")
            or meta.get("reference_image")
            or meta.get("portrait_path")
        )
        if provided_keyframe and Path(str(provided_keyframe)).exists():
            try:
                src = Path(str(provided_keyframe))
                if src.resolve() != keyframe_path.resolve():
                    shutil.copy(src, keyframe_path)
                keyframes[name] = str(keyframe_path)
                emit("char_ok", f"{name} -> {keyframe_path.name} (reused storyboard keyframe)")
            except Exception as e:
                keyframes[name] = str(provided_keyframe)
                emit("char_ok", f"{name} -> reused external keyframe ({str(e)[:60]})")
            continue
        run_id = f"cinema_{int(time.time())}_{idx}"

        # v82l9 : retry up to 2 fois avec seeds différents si FLUX échoue ou
        # produit pas de fichier. Évite que le pipeline bascule en text-to-video
        # juste à cause d'un échec ComfyUI transient (OOM, timeout, etc.).
        # v90.6 : si les 2 premiers seeds sont rejetés pour un élément nommé
        # raté (deerstalker -> fedora), le dernier essai part sur une
        # description réécrite visuellement par le LLM local.
        produced = None
        current_desc = desc
        last_reject_reason = ""
        for attempt, seed in enumerate([42, 7777, 31415], 1):
            if attempt == 3 and last_reject_reason:
                enriched = _rewrite_desc_visually(desc, last_reject_reason)
                if enriched != desc:
                    current_desc = enriched
                    prompt = build_character_keyframe_prompt(
                        current_desc, style_suffix, entity_is_object)
                    emit("char_enrich", f"{name}: {enriched[:100]}")
            emit("char_keyframe", f"FLUX {name} attempt {attempt}/3 (seed={seed})")
            attempt_run_id = f"{run_id}_a{attempt}"
            cmd = [
                sys.executable, str(flux_script),
                "--prompt", prompt,
                "--run-id", attempt_run_id,
                "--output-dir", str(work_dir),
                "--width", str(width),
                "--height", str(height),
                "--steps", "25",
                "--seed", str(seed),
            ]
            rc, stdout, stderr = _run(cmd, timeout=300)
            if rc != 0:
                emit("char_warn", f"{name} FLUX attempt {attempt} rc={rc}: {(stderr or stdout)[:120]}")
                continue

            # Find the produced image.
            candidates = list(work_dir.glob(f"*{attempt_run_id}*.png")) + list(work_dir.glob(f"*{attempt_run_id}*.webp"))
            if not candidates:
                try:
                    last = (stdout or "").strip().split("\n")[-1]
                    obj = json.loads(last)
                    p = obj.get("output_path") or (obj.get("paths") or [None])[0]
                    if p and Path(p).exists():
                        shutil.copy(p, keyframe_path)
                        candidates = [keyframe_path]
                except Exception:
                    pass

            if candidates:
                src = candidates[0]
                if src.resolve() != keyframe_path.resolve():
                    try:
                        shutil.copy(src, keyframe_path)
                    except Exception:
                        keyframe_path = src
                # v82la : vision-LLM validates that keyframe matches description.
                # On reject (score < 7), fallback au seed suivant. Last attempt
                # accepted regardless to ensure we have something.
                check = validate_keyframe_with_vision(str(keyframe_path), desc)

                # v91 : pour un OBJET, la ressemblance ne suffit pas. Une image
                # peut "ressembler beaucoup" a un velo et n'avoir ni pedales ni
                # chaine — c'est arrive, et l'objet incomplet s'est propage a
                # tous les plans qu'il ancrait. On pose donc la question dure :
                # qu'est-ce qui MANQUE ?
                completeness = None
                if entity_is_object:
                    completeness = validate_object_completeness(
                        str(keyframe_path), desc)
                    if completeness.get("graded") and not completeness["ok"]:
                        check = dict(check)
                        check["ok"] = False
                        check["reason"] = completeness["reason"]

                # v91 : un OBJET incomplet n'est JAMAIS accepte, meme au
                # dernier essai. L'acceptation inconditionnelle a `attempt == 3`
                # est raisonnable pour un personnage (mieux vaut un portrait
                # imparfait que pas de reference du tout), mais pas pour un
                # objet : une reference amputee se PROPAGE a tous les plans
                # qu'elle ancre. C'est exactement ainsi qu'un velo sans pedales
                # est parti en production avec, pour toute sanction, un tag
                # texte dans le journal.
                # Mieux vaut aucune ancre — le plan retombe en t2v — qu'une
                # ancre fausse repetee cinq fois.
                object_incomplete = bool(
                    completeness is not None
                    and completeness.get("graded")
                    and not completeness["ok"]
                )
                if object_incomplete and attempt == 3:
                    emit("char_reject_objet",
                         f"{name}: reference REFUSEE apres 3 essais — "
                         f"{completeness['reason'][:120]}. Aucune ancre ne sera "
                         f"utilisee pour cet objet (repli t2v).")
                    break

                if (check["ok"] and not object_incomplete) or attempt == 3:
                    produced = str(keyframe_path)
                    detail = f"{name} -> {keyframe_path.name} (seed {seed}, score {check['score']})"
                    emit("char_ok", detail)
                    break
                else:
                    last_reject_reason = str(check.get("reason") or "")
                    emit("char_reject", f"{name} attempt {attempt} score {check['score']}: {check['reason']}")
                    # Continue retry loop with next seed

        if produced:
            keyframes[name] = produced
        else:
            emit("char_warn", f"{name} all 3 FLUX attempts failed -> shot will use t2v fallback")

    return keyframes


def collect_backdrop_locations(shots: list, characters: dict) -> list:
    """v90.5 : repère les lieux dont la PREMIÈRE apparition est un plan de
    dialogue close-up — ces plans composites n'ont encore aucune ancre de
    scène et finissaient sur le fond studio du keyframe (constaté : Sherlock
    parlant 15 s sur fond blanc au lieu du salon au coin du feu)."""
    seen = set()
    needed = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        loc = str(shot.get("location") or "").strip().lower()
        key = loc or f"__shot_{shot.get('id')}"
        if key in seen:
            continue
        seen.add(key)
        dialogue = str(shot.get("dialogue") or "").strip()
        camera = str(shot.get("camera") or "").lower()
        speaker = shot.get("speaker")
        if dialogue and "close" in camera and speaker and speaker in characters:
            needed.append((key, str(shot.get("scene") or "")))
    return needed


def generate_scene_backdrop(
    scene: str,
    style_id: str,
    work_dir: Path,
    name: str,
    width: int,
    height: int,
) -> str:
    """Rend un fond de décor FLUX (scène SANS personnages) pour les composites
    de dialogue. Retourne le chemin PNG ou '' en cas d'échec (fallback
    keyframe brut, comportement historique)."""
    flux_script = SERVICES_DIR / "flux_reference_synth.py"
    if not flux_script.exists():
        return ""
    prompt = (
        f"empty establishing shot of: {scene}. No people, no characters, "
        f"no faces, environment only, detailed background"
        f"{style_for(style_id)}"
    )
    safe = re.sub(r"[^a-z0-9_]+", "_", name.lower())[:40]
    out_png = work_dir / f"backdrop_{safe}.png"
    run_id = f"cinema_bd_{int(time.time())}_{safe[:12]}"
    emit("backdrop", f"FLUX decor {safe}")
    cmd = [
        sys.executable, str(flux_script),
        "--prompt", prompt,
        "--run-id", run_id,
        "--output-dir", str(work_dir),
        "--width", str(width),
        "--height", str(height),
        "--steps", "25",
        "--seed", "4242",
    ]
    rc, stdout, stderr = _run(cmd, timeout=300)
    if rc != 0:
        emit("backdrop_warn", f"{safe}: {(stderr or stdout)[:100]}")
        return ""
    candidates = list(work_dir.glob(f"*{run_id}*.png")) + list(work_dir.glob(f"*{run_id}*.webp"))
    if not candidates:
        try:
            last = (stdout or "").strip().split("\n")[-1]
            obj = json.loads(last)
            p = obj.get("output_path") or (obj.get("paths") or [None])[0]
            if p and Path(p).exists():
                candidates = [Path(p)]
        except Exception:
            return ""
    if not candidates:
        return ""
    try:
        if candidates[0].resolve() != out_png.resolve():
            shutil.copy(candidates[0], out_png)
        return str(out_png)
    except Exception:
        return str(candidates[0])


def build_character_keyframe_prompt(description: str, style_suffix: str,
                                    is_object: bool = False) -> str:
    """Prompt de la reference canonique d'une entite.

    `is_object` vient du champ explicite `anchor_as_object` du storyboard et
    prime sur l'heuristique par mots-cles. Mesure a l'origine de ce parametre :
    la description "a bright red carbon road racing bicycle with drop
    handlebars..." ne contient AUCUN des mots-cles de is_object_like_character
    ("drone, robot, vehicle, machine, device, object, mechanical, triangular,
    metallic, brass"). Elle recevait donc le prompt PORTRAIT, et FLUX a place
    un garcon generique derriere le velo. Cette reference devenant l'ancre i2v,
    le garcon a remplace Natsu dans deux plans sur cinq.
    Une reference d'objet ne doit contenir QUE l'objet.
    """
    desc = (description or "").strip()
    if is_object or is_object_like_character(desc):
        return (
            f"centered full-body concept art of {desc}, exact silhouette, "
            f"the object completely alone in frame, no person, no human, "
            f"nobody holding it, nobody behind it, unoccupied, "
            f"clean background, orthographic product view, no human face, no extra eyes, "
            f"no arms or legs unless explicitly described{style_suffix}"
        )
    return (
        f"portrait of {desc}, upper body, neutral pose, looking at camera, "
        f"clean background, all clothing and accessories visible{style_suffix}"
    )


def is_object_like_character(description: str) -> bool:
    low = (description or "").lower()
    return any(token in low for token in (
        "drone", "robot", "vehicle", "machine", "device", "object", "mechanical",
        "triangular", "metallic", "brass",
    ))


def select_anchor_character(shot: dict, speaker: str, characters: dict, keyframes: dict) -> tuple:
    """Pick the best i2v anchor for a shot.

    Portrait keyframes are reliable for close-ups and medium shots on a
    simple/compatible backdrop. Wide or environment-heavy shots remain
    text-to-video because a clean portrait background can otherwise replace
    the requested location. ``identity_priority`` lets personal reproduction
    workflows explicitly prefer identity on any non-wide human shot.
    """
    if shot.get("validate_character") is False:
        return "", None

    scene = str(shot.get("scene", "")).lower()
    camera = str(shot.get("camera", "")).lower()
    early_scene = scene[:260]
    non_character_focus = (
        "hand", "hands", "glove", "gloved", "core", "seed", "soil", "tree",
        "sprout", "lock", "docking", "dock", "door", "rail", "puddle",
        "water", "glass",
    )
    # A token mention alone is not a focus signal: "Testeur makes a hand
    # gesture" is still a character shot. Treat it as object-focused only
    # when the object precedes the named subject or the framing explicitly
    # asks for a close/macro/detail view of that object.
    import re as _re
    object_positions = []
    for token in non_character_focus:
        match = _re.search(rf"\b{_re.escape(token)}\b", early_scene)
        if match:
            object_positions.append((match.start(), token))
    character_positions = []
    for name in ({speaker} | set((keyframes or {}).keys())):
        if not name:
            continue
        pos = early_scene.find(str(name).lower())
        if pos >= 0:
            character_positions.append(pos)
    first_object_pos = min((pos for pos, _ in object_positions), default=-1)
    first_character_pos = min(character_positions, default=-1)
    explicit_object_focus = any(
        _re.search(
            rf"\b(?:close[- ]?up|macro|detail(?:ed)? shot)\b[^.]*\b{_re.escape(token)}\b",
            early_scene,
        )
        for _, token in object_positions
    )
    non_character_focused = bool(
        explicit_object_focus
        or (
            first_object_pos >= 0
            and (first_character_pos < 0 or first_object_pos < first_character_pos)
        )
    )
    is_close = "close" in camera
    is_wide = any(token in camera for token in (
        "wide", "large", "long shot", "establishing", "aerial", "drone",
    ))
    simple_backdrop = any(token in early_scene for token in (
        "clean background", "plain background", "neutral background",
        "simple background", "seamless backdrop", "studio backdrop",
        "film studio", "photo studio", "photography studio",
    ))
    identity_priority = bool(shot.get("identity_priority"))
    portrait_anchor_allowed = (
        is_close
        or (
            not is_wide
            and not non_character_focused
            and (identity_priority or simple_backdrop)
        )
    )

    # v91 — ANCRAGE D'OBJET EXPLICITE (opt-in, additif, evalue AVANT la porte
    # portrait). Une entite portant `anchor_as_object: true` est un OBJET dont
    # l'apparence doit rester identique d'un plan a l'autre (un produit, un
    # vehicule, une piece unique).
    # Les regles plus bas ecartent systematiquement les entites "object-like"
    # de l'ancrage : c'est le bon reflexe pour eviter qu'un portrait-produit
    # remplace un decor demande, mais c'est exactement l'inverse de ce qu'il
    # faut quand LE PLAN PORTE SUR CET OBJET. Et la porte `portrait_anchor_
    # allowed` ne concerne que les visages : elle n'a pas a bloquer un objet.
    # Mesure a l'origine du correctif : un velo note 10/10 au plan 1 est revenu
    # meconnaissable au plan 5 (cadre deforme, roue elliptique) faute d'ancre.
    # Opt-in strict : aucun storyboard existant ne porte ce champ, le
    # comportement par defaut est donc inchange.
    if not (shot.get("needs_lipsync") or str(shot.get("dialogue") or "").strip()):
        object_anchors = []
        for name, path in (keyframes or {}).items():
            if not name or not path:
                continue
            if not (characters.get(name, {}) or {}).get("anchor_as_object"):
                continue
            idx = scene.find(str(name).lower())
            if idx >= 0:
                object_anchors.append((idx, name, path))
        if object_anchors:
            _, name, path = sorted(object_anchors, key=lambda it: it[0])[0]
            return name, path

    if speaker and keyframes.get(speaker):
        if shot.get("needs_lipsync") or str(shot.get("dialogue") or "").strip():
            desc = (characters.get(speaker, {}) or {}).get("description") or ""
            if is_object_like_character(desc):
                return "", None
            if not portrait_anchor_allowed:
                return "", None
            return speaker, keyframes.get(speaker)
        if not portrait_anchor_allowed:
            return "", None
        if non_character_focused:
            return "", None
        desc = (characters.get(speaker, {}) or {}).get("description") or ""
        if is_object_like_character(desc):
            return "", None
        return speaker, keyframes.get(speaker)

    if not portrait_anchor_allowed:
        return "", None

    mentioned = []
    for name, path in (keyframes or {}).items():
        if not name or not path:
            continue
        idx = scene.find(str(name).lower())
        if idx >= 0:
            mentioned.append((idx, name, path))
    if mentioned:
        first_idx, first_name, _ = sorted(mentioned, key=lambda item: item[0])[0]
        first_desc = (characters.get(first_name, {}) or {}).get("description") or ""
        if first_idx < 120 and is_object_like_character(first_desc):
            return "", None

    if non_character_focused:
        return "", None

    matches = []
    for idx, name, path in mentioned:
        desc = (characters.get(name, {}) or {}).get("description") or ""
        if is_object_like_character(desc):
            continue
        matches.append((idx, name, path))
    if matches:
        _, name, path = sorted(matches, key=lambda item: item[0])[0]
        return name, path
    return "", None


# --------------------------------------------------------------------------
# Voice synthesis (delegates to voice_clone.py)
# --------------------------------------------------------------------------

def synthesize_voice(
    text: str,
    character_slug: str,
    lang: str,
    output_wav: str,
    voice_preset: str = "",
    voice_policy: str = "",
    public_figure: bool = False,
) -> dict:
    """Tente voice_clone (cloning XTTS/F5) puis fallback Kokoro générique.

    v82l8 : chain de fallbacks pour ne jamais return un voice_wav vide.
      1. voice_clone --character <slug> (XTTS/F5 avec reference WAV du perso)
      2. voice_clone --character default_<lang> (voix générique langue)
      3. Kokoro TTS direct via voice_synth.py (TTS sans cloning, voix robotique
         mais audible — meilleur que silence)
      4. Échec final : return ok=False, le pipeline mute le shot.
    """
    voice_script = Path(__file__).resolve().parent / "voice_clone.py"
    base_cmd = [
        sys.executable, str(voice_script),
        "--synthesize",
        "--text", text,
        "--lang", lang,
        "--output", output_wav,
    ]

    def try_synthesize(slug: str) -> dict:
        cmd = base_cmd + ["--character", slug]
        emit("tts", f"{slug}: {text[:50]}...")
        rc, stdout, stderr = _run(cmd, timeout=300)
        if rc != 0:
            return {"ok": False, "error": (stderr or stdout)[:300]}
        last_line = (stdout or "").strip().split("\n")[-1]
        try:
            r = json.loads(last_line)
            return r if isinstance(r, dict) else {"ok": False, "error": "no JSON"}
        except Exception:
            return {"ok": False, "error": "voice_clone non-JSON: " + last_line[:160]}

    def try_fresh(preset: str) -> dict:
        if not preset:
            return {"ok": False, "error": "no voice_preset"}
        cmd = [
            sys.executable, str(voice_script),
            "--synthesize-fresh",
            "--voice-preset", preset,
            "--text", text,
            "--lang", lang,
            "--output", output_wav,
        ]
        emit("tts_style", f"{preset}: {text[:50]}...")
        rc, stdout, stderr = _run(cmd, timeout=240)
        if rc != 0:
            return {"ok": False, "error": (stderr or stdout)[:300]}
        last_line = (stdout or "").strip().split("\n")[-1]
        try:
            r = json.loads(last_line)
            return r if isinstance(r, dict) else {"ok": False, "error": "no JSON"}
        except Exception:
            return {"ok": False, "error": "fresh voice non-JSON: " + last_line[:160]}

    policy = (voice_policy or "").strip().lower()
    slug = (character_slug or "").strip()
    prefers_style_voice = bool(voice_preset) and (
        policy in {"style", "fresh", "synthetic"}
        or slug.startswith("style_")
        or (public_figure and policy != "registered")
    )
    allow_registered_clone = (
        bool(slug)
        and policy != "style"
        and not slug.startswith("style_")
        and not (public_figure and policy != "registered")
    )

    if prefers_style_voice:
        r0 = try_fresh(voice_preset)
        if r0.get("ok"):
            return r0

    # 1. Voice cloning par slug du personnage, seulement si autorise.
    if allow_registered_clone:
        r = try_synthesize(slug)
        if r.get("ok"):
            return r

    if voice_preset and not prefers_style_voice:
        r_style = try_fresh(voice_preset)
        if r_style.get("ok"):
            return r_style

    # 2. v82ll : ensure default_<lang> exists in library (auto-bootstrap
    # via Kokoro TTS si absent), puis fallback dessus avec cloning XTTS/F5.
    generic_slug = f"default_{(lang or 'fr')[:2]}"
    if slug != generic_slug:
        # Auto-bootstrap : crée default_<lang> si manquant.
        try:
            bootstrap_cmd = [
                sys.executable, str(voice_script),
                "--ensure-default", "--lang", (lang or "fr")[:2],
            ]
            _run(bootstrap_cmd, timeout=180)
        except Exception:
            pass
        emit("tts_fallback", f"slug {slug or 'none'} introuvable -> {generic_slug}")
        r2 = try_synthesize(generic_slug)
        if r2.get("ok"):
            return r2

    # 3. Fallback voice_service (Kokoro TTS sans cloning, voix robotique).
    voice_svc = SERVICES_DIR / "voice_service.py"
    if voice_svc.exists():
        emit("tts_fallback", "voice_service Kokoro TTS générique")
        kcmd = [
            sys.executable, str(voice_svc),
            "--mode", "tts",
            "--text", text,
            "--lang", (lang or "fr")[:2],
            "--output", output_wav,
        ]
        rc, stdout, stderr = _run(kcmd, timeout=180)
        if rc == 0 and Path(output_wav).exists():
            return {"ok": True, "wav": output_wav, "engine": "kokoro_fallback"}

    # 4. Total fail.
    return {
        "ok": False,
        "error": f"all voice paths failed (no slug, no generic, no kokoro)",
    }


# --------------------------------------------------------------------------
# Lipsync (delegates to existing talking_head.py SadTalker as MVP)
# --------------------------------------------------------------------------

_MUSETALK_AVAILABLE = None


def musetalk_available() -> bool:
    """Check (once per process) whether MuseTalk V1.5 weights are installed."""
    global _MUSETALK_AVAILABLE
    if _MUSETALK_AVAILABLE is not None:
        return _MUSETALK_AVAILABLE
    runner = Path(__file__).resolve().parent / "musetalk_runner.py"
    if not runner.exists():
        _MUSETALK_AVAILABLE = False
        return False
    rc, stdout, _ = _run([sys.executable, str(runner), "--check"], timeout=60)
    ok = False
    try:
        ok = bool(json.loads((stdout or "").strip().split("\n")[-1]).get("ok"))
    except Exception:
        ok = rc == 0
    _MUSETALK_AVAILABLE = ok
    return ok


_LIPSYNC_AVAILABLE = None


def lipsync_available() -> bool:
    """Vrai si AU MOINS un moteur de lipsync peut reellement animer une bouche.

    Sert a decider si l'on peut se permettre un plan fige (que le lipsync
    animera) ou s'il faut generer un plan anime. Repond une seule fois par
    process : la verification lance des sous-process.
    """
    global _LIPSYNC_AVAILABLE
    if _LIPSYNC_AVAILABLE is not None:
        return _LIPSYNC_AVAILABLE
    if musetalk_available():
        _LIPSYNC_AVAILABLE = True
        return True
    # SadTalker : repli historique, anime la premiere frame.
    try:
        th = Path(__file__).resolve().parent.parent / "talking_head.py"
        if th.exists():
            rc, stdout, _ = _run([sys.executable, str(th), "--mode", "check"],
                                 timeout=60)
            last = (stdout or "").strip().split("\n")[-1]
            _LIPSYNC_AVAILABLE = bool(json.loads(last).get("ready"))
            return _LIPSYNC_AVAILABLE
    except Exception:
        pass
    _LIPSYNC_AVAILABLE = False
    return False


def apply_lipsync(image_or_video: str, audio_wav: str, output_mp4: str) -> dict:
    """v90 : lipsync qui PRÉSERVE le mouvement du plan.

    1. MuseTalk V1.5 video-driven : anime les lèvres directement sur le clip
       Wan2.2 rendu — le mouvement du plan (marche, gestes, caméra) est
       conservé. Si l'audio est plus long que le clip, le clip est prolongé
       (dernière frame clonée) avant l'inférence pour couvrir toute la parole.
    2. Fallback SadTalker première-frame (comportement historique) si MuseTalk
       est absent ou échoue : tête parlante statique, mais parole complète.
    """
    is_video = str(image_or_video).lower().endswith((".mp4", ".mov", ".webm", ".mkv"))
    if is_video and musetalk_available():
        audio_s = probe_audio_duration(audio_wav)
        video_s = probe_video_duration(image_or_video)
        source = image_or_video
        if audio_s > video_s + 0.1 and video_s > 0:
            fitted = str(Path(output_mp4).with_suffix(".lipfit.mp4"))
            ext = extend_video_to_duration(image_or_video, audio_s + 0.2, fitted)
            if ext.get("ok"):
                source = ext.get("mp4") or fitted
        runner = Path(__file__).resolve().parent / "musetalk_runner.py"
        cmd = [
            sys.executable, str(runner),
            "--drive",
            "--source", str(source),
            "--audio", str(audio_wav),
            "--output", str(output_mp4),
        ]
        emit("lipsync", "MuseTalk V1.5 (video-drive, mouvement conserve)...")
        rc, stdout, stderr = _run(cmd, timeout=1800)
        if rc == 0 and Path(output_mp4).exists():
            if not has_audio_stream(output_mp4):
                muxed = str(Path(output_mp4).with_suffix(".with_audio.mp4"))
                mux_result = mux_audio_fit(output_mp4, audio_wav, muxed)
                if mux_result.get("ok"):
                    try:
                        Path(muxed).replace(output_mp4)
                    except Exception:
                        return {"ok": True, "mp4": muxed, "engine": "musetalk-v15"}
            # v90.1 : MuseTalk trime sa sortie à la durée audio — on restitue
            # jusqu'à 1 s de respiration (dernière frame clonée + silence) si
            # la vidéo source durait plus longtemps que la parole.
            out_d = probe_video_duration(output_mp4)
            src_d = probe_video_duration(str(source))
            if src_d > out_d + 0.15 and out_d > 0:
                padded = str(Path(output_mp4).with_suffix(".breath.mp4"))
                ext = extend_video_to_duration(output_mp4, min(src_d, out_d + 1.0), padded)
                if ext.get("ok") and str(ext.get("mp4")) != str(output_mp4):
                    try:
                        Path(str(ext["mp4"])).replace(output_mp4)
                    except Exception:
                        pass
            return {"ok": True, "mp4": output_mp4, "engine": "musetalk-v15"}
        emit("lipsync_warn", f"MuseTalk failed (rc={rc}) -> fallback SadTalker: {(stderr or stdout)[-160:]}")

    # Fallback : SadTalker via talking_head.py expects a STILL IMAGE, not a video.
    # We extract the first frame, run SadTalker — lipsync replaces the original
    # Wan2.2 motion for that shot (static talking head).
    talking_script = SERVICES_DIR / "talking_head.py"
    if not talking_script.exists():
        return {"ok": False, "error": "talking_head.py not found"}

    # Extract first frame as image
    img_path = Path(output_mp4).with_suffix(".firstframe.png")
    rc, _, err = _run([
        _ffmpeg_bin(), "-y", "-i", image_or_video, "-frames:v", "1",
        "-loglevel", "error", str(img_path),
    ], timeout=60)
    if rc != 0 or not img_path.exists():
        return {"ok": False, "error": f"frame extract failed: {err[:160]}"}

    cmd = [
        sys.executable, str(talking_script),
        "--mode", "generate",
        "--image", str(img_path),
        "--audio", audio_wav,
        "--output", output_mp4,
    ]
    emit("lipsync", "SadTalker...")
    rc, stdout, stderr = _run(cmd, timeout=900)
    if rc != 0:
        return {"ok": False, "error": (stderr or stdout)[:300]}
    if not has_audio_stream(output_mp4):
        muxed_output = str(Path(output_mp4).with_suffix(".with_audio.mp4"))
        mux_result = mux_audio(output_mp4, audio_wav, muxed_output)
        if not mux_result.get("ok"):
            return {"ok": False, "error": f"lipsync output has no audio; remux failed: {mux_result.get('error', '')[:160]}"}
        try:
            Path(muxed_output).replace(output_mp4)
        except Exception as exc:
            return {"ok": False, "error": f"lipsync audio replace failed: {exc}"}
    return {"ok": True, "mp4": output_mp4, "engine": "sadtalker"}


# --------------------------------------------------------------------------
# Mux audio onto a video clip
# --------------------------------------------------------------------------

def mux_audio(video_mp4: str, audio_wav: str, output_mp4: str) -> dict:
    """Add audio track to a video. The video keeps its visual; audio becomes the track."""
    cmd = [
        _ffmpeg_bin(), "-y",
        "-i", video_mp4,
        "-i", audio_wav,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-loglevel", "error",
        output_mp4,
    ]
    rc, _, err = _run(cmd, timeout=120)
    if rc != 0:
        return {"ok": False, "error": err[:200]}
    return {"ok": True, "mp4": output_mp4}


# --------------------------------------------------------------------------
# Final assembly: concat all shots
# --------------------------------------------------------------------------

# v82lb : integrity check via ffprobe (durée, audio, codec).
def integrity_check(mp4_path: str, expected_duration_s: float = 0.0) -> dict:
    """Run ffprobe on the output mp4. Returns dict with:
      ok, duration_s, has_video, has_audio, video_codec, audio_codec, errors[]
    Validates that:
      - file exists and is not empty
      - has at least 1 video stream
      - duration > 0
      - if expected_duration_s provided, |actual - expected| < 1.5s tolerance
    """
    p = Path(mp4_path)
    errors = []
    if not p.exists() or p.stat().st_size < 1024:
        return {"ok": False, "errors": ["file missing or too small"], "duration_s": 0}

    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    try:
        rc, stdout, stderr = _run([
            ffprobe, "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,duration",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(p),
        ], timeout=30)
    except Exception as e:
        return {"ok": False, "errors": [f"ffprobe spawn fail: {e}"], "duration_s": 0}

    if rc != 0:
        return {"ok": False, "errors": [f"ffprobe rc={rc}: {stderr[:200]}"], "duration_s": 0}

    try:
        info = json.loads(stdout)
    except Exception:
        return {"ok": False, "errors": ["ffprobe non-JSON output"], "duration_s": 0}

    streams = info.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    video_codec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "video"), None)
    audio_codec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or 0)

    if not has_video:
        errors.append("no video stream")
    if duration < 0.5:
        errors.append(f"duration too short: {duration:.2f}s")
    if expected_duration_s > 0:
        delta = abs(duration - expected_duration_s)
        if delta > 1.5:
            errors.append(f"duration mismatch: actual {duration:.1f}s vs expected {expected_duration_s:.1f}s (delta {delta:.1f}s)")

    return {
        "ok": len(errors) == 0,
        "duration_s": round(duration, 2),
        "has_video": has_video,
        "has_audio": has_audio,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "size_bytes": p.stat().st_size,
        "errors": errors,
    }


def probe_render_truth(
    mp4_path: str,
    native_width: int,
    native_height: int,
    native_fps: float = 24.0,
    native_frames: int | None = None,
    native_shots: list | None = None,
    postprocess_chain: list | None = None,
) -> dict:
    """Expose native generation facts separately from the delivered container."""
    delivered_width = 0
    delivered_height = 0
    delivered_fps = 0.0
    delivered_frames = 0
    ffprobe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    try:
        rc, stdout, _ = _run([
            ffprobe, "-v", "error", "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,nb_frames",
            "-of", "json", str(mp4_path),
        ], timeout=60)
        if rc == 0:
            stream = (json.loads(stdout).get("streams") or [{}])[0]
            delivered_width = int(stream.get("width") or 0)
            delivered_height = int(stream.get("height") or 0)
            delivered_frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
            rate = str(stream.get("r_frame_rate") or "0/1").split("/", 1)
            delivered_fps = float(rate[0]) / max(1.0, float(rate[1]))
    except Exception:
        pass
    return {
        "native_width": int(native_width),
        "native_height": int(native_height),
        "native_fps": round(float(native_fps), 3),
        "native_frames": int(native_frames if native_frames is not None else delivered_frames),
        "native_shots": list(native_shots or []),
        "delivered_width": delivered_width,
        "delivered_height": delivered_height,
        "delivered_fps": round(delivered_fps, 3),
        "delivered_frames": delivered_frames,
        "postprocess_chain": list(postprocess_chain or []),
        "is_upscaled": bool(
            delivered_width
            and delivered_height
            and (delivered_width != int(native_width) or delivered_height != int(native_height))
        ),
    }


# v82le : SRT subtitle generation from storyboard dialogues.
def build_srt_from_storyboard(shots: list, output_srt: str) -> dict:
    """For each shot with dialogue, emit one .srt entry. Subtitles span the
    full duration of the shot (dialogue is the speaker's line at that moment).
    Embed-able into mp4 via ffmpeg -c:s mov_text.
    """
    def fmt(seconds: float) -> str:
        ms = int(round((seconds - int(seconds)) * 1000))
        h = int(seconds) // 3600
        m = (int(seconds) % 3600) // 60
        s = int(seconds) % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    cursor = 0.0
    entries = []
    for idx, shot in enumerate(shots, 1):
        # v90 : caler chaque entrée sur la durée RÉELLE du clip rendu quand
        # elle est connue (actual_duration_s), pas sur la durée théorique du
        # storyboard. Avant, la dérive s'accumulait plan après plan et les
        # sous-titres finissaient complètement désynchronisés sur les vidéos
        # longues (clips Wan plafonnés ~4 s + clips lipsync = durée audio).
        dur = float(shot.get("actual_duration_s") or shot.get("duration_s", 5.0))
        dialogue = (shot.get("dialogue") or "").strip()
        if dialogue:
            speaker = shot.get("speaker") or ""
            label = f"{speaker} : {dialogue}" if speaker else dialogue
            entries.append(
                f"{len(entries) + 1}\n"
                f"{fmt(cursor)} --> {fmt(cursor + dur)}\n"
                f"{label}\n"
            )
        cursor += dur

    if not entries:
        return {"ok": False, "error": "no dialogue to subtitle"}

    Path(output_srt).write_text("\n".join(entries), encoding="utf-8")
    return {"ok": True, "srt": output_srt, "count": len(entries)}


def mix_music_under(video_mp4: str, music_wav: str, output_mp4: str, music_volume: float = 0.35) -> dict:
    """v90 : mixe une piste musicale sous la bande son existante (voix devant).

    v90.3 : ducking sidechain — la musique est compressée par la voix (elle
    s'abaisse automatiquement quand quelqu'un parle et remonte dans les
    respirations et sur l'outro). L'ancien volume fixe 0.22 rendait la
    musique quasi inaudible même dans les passages muets (-38 dB mesurés).
    """
    if not Path(music_wav).exists():
        return {"ok": False, "error": "music wav missing"}
    vdur = probe_video_duration(video_mp4)
    if vdur <= 0:
        return {"ok": False, "error": "could not probe video duration"}
    if has_audio_stream(video_mp4):
        fc = (
            f"[1:a]volume={music_volume},apad[m];"
            f"[0:a]asplit=2[voice][sc];"
            f"[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=25:release=400:makeup=1[duck];"
            f"[voice][duck]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )
    else:
        fc = f"[1:a]volume={music_volume},apad[aout]"
    rc, _, err = _run([
        _ffmpeg_bin(), "-y",
        "-i", video_mp4,
        "-i", music_wav,
        "-filter_complex", fc,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-t", f"{vdur:.3f}",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_mp4,
    ], timeout=300)
    if rc != 0 or not Path(output_mp4).exists():
        return {"ok": False, "error": (err or "")[-300:]}
    return {"ok": True, "mp4": output_mp4}


def render_music_track(prompt: str, duration_s: float, output_wav: str) -> dict:
    """v90 : branche musicgen_render.py (jusqu'ici jamais consommé) sur le
    champ storyboard music. Best-effort : tout échec est non bloquant."""
    music_script = Path(__file__).resolve().parent / "musicgen_render.py"
    if not music_script.exists():
        return {"ok": False, "error": "musicgen_render.py not found"}
    rc, stdout, stderr = _run([
        sys.executable, str(music_script),
        "--prompt", prompt,
        "--duration", f"{max(1.0, duration_s):.1f}",
        "--output", output_wav,
    ], timeout=1800)
    if rc == 0 and Path(output_wav).exists():
        return {"ok": True, "wav": output_wav}
    return {"ok": False, "error": (stderr or stdout or "")[-300:]}


def mux_subtitles(input_mp4: str, srt_path: str, output_mp4: str) -> dict:
    """Embed .srt into mp4 as mov_text track (visible in QuickTime/VLC by
    default, can be toggled in any modern player)."""
    cmd = [
        _ffmpeg_bin(), "-y",
        "-i", input_mp4,
        "-i", srt_path,
        "-c", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=fra",
        "-loglevel", "error",
        output_mp4,
    ]
    emit("subtitles", f"mux SRT -> {Path(output_mp4).name}")
    rc, _, err = _run(cmd, timeout=180)
    if rc != 0:
        return {"ok": False, "error": err[:300]}
    return {"ok": True, "mp4": output_mp4}


def concat_shots(shot_files: list, output_mp4: str,
                 target_w: int = 0, target_h: int = 0) -> dict:
    """Concat all shots into the final video.

    v83 : the shots are rendered at a GPU-safe generation resolution
    (e.g. 848x480 for 720p, 960x536 for 1080p) ; the `upscale_factor` computed
    upstream was previously DROPPED, so the final file shipped at the low gen
    resolution instead of the resolution the user asked for. We now scale the
    concatenated stream up to (target_w, target_h) with a high-quality Lanczos
    filter + light unsharp so the output actually matches its label, and we
    encode at higher quality (CRF 17, preset slow, faststart). This is the
    single biggest "rendu" win — true 720p/1080p instead of upscaled-in-name.
    """
    if not shot_files:
        return {"ok": False, "error": "no shots to concat"}

    out_path = Path(output_mp4)
    norm_dir = out_path.with_name(f"{out_path.stem}_concat_norm")
    norm_dir.mkdir(parents=True, exist_ok=True)

    if target_w and target_h:
        tw = (int(target_w) // 2) * 2
        th = (int(target_h) // 2) * 2
        vf = f"scale={tw}:{th}:flags=lanczos,unsharp=3:3:0.5:3:3:0.0,format=yuv420p"
        emit("upscale", f"per-shot normalize -> {tw}x{th} (lanczos+unsharp)")
    else:
        vf = "format=yuv420p"

    normalized_files = []
    for idx, shot in enumerate(shot_files, start=1):
        src = Path(shot)
        dst = norm_dir / f"shot_{idx:03d}.mp4"
        if has_audio_stream(str(src)):
            normalize_cmd = [
                _ffmpeg_bin(), "-y",
                "-i", str(src),
                "-map", "0:v:0",
                "-map", "0:a:0",
                "-vf", vf,
                "-r", "24",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "17",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
                "-movflags", "+faststart",
                "-loglevel", "error",
                str(dst),
            ]
        else:
            normalize_cmd = [
                _ffmpeg_bin(), "-y",
                "-i", str(src),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", vf,
                "-r", "24",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "17",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                "-loglevel", "error",
                str(dst),
            ]
        rc, _, err = _run(normalize_cmd, timeout=300)
        if rc != 0 or not dst.exists():
            return {"ok": False, "error": f"normalize shot {idx} failed: {err[:240]}"}
        normalized_files.append(str(dst))

    # FFmpeg concat demuxer requires a list file
    list_file = Path(output_mp4).with_suffix(".concat.txt")
    with list_file.open("w", encoding="utf-8") as f:
        for shot in normalized_files:
            # Escape backslashes and single quotes for ffmpeg list format
            p = str(Path(shot).resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{p}'\n")

    cmd = [
        _ffmpeg_bin(), "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
    ]
    cmd += [
        "-c", "copy",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_mp4,
    ]
    emit("concat", f"{len(shot_files)} plans -> {Path(output_mp4).name}")
    rc, _, err = _run(cmd, timeout=900)
    try:
        list_file.unlink()
    except Exception:
        pass
    if rc != 0:
        return {"ok": False, "error": err[:300]}
    return {"ok": True, "mp4": output_mp4}


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def estimate_total_seconds(shots: list, style: str, resolution: str) -> int:
    """Rough pre-generation estimate based on the table."""
    # Per-clip seconds for 5s clip on RTX 5070 Ti 16GB at the given resolution.
    # v90.1 : recalibré sur mesure réelle — E2E 4 plans parlés 720p realistic
    # (Wan segments + FLUX keyframes + MuseTalk + MusicGen) = 1722 s soit
    # ~430 s/plan ; l'ancienne table (28 min/plan) surestimait 5x.
    base = {
        ("cartoon_pixar", "720p"): 6 * 60,
        ("cartoon_pixar", "1080p"): 9 * 60,
        ("cartoon_pixar", "1440p"): 12 * 60,
        ("anime", "720p"): 5 * 60,
        ("anime", "1080p"): 8 * 60,
        ("anime", "1440p"): 11 * 60,
        ("realistic", "720p"): 7 * 60,
        ("realistic", "1080p"): 10 * 60,
        ("realistic", "1440p"): 13 * 60,
    }
    per_5s = base.get((style, resolution), 8 * 60)
    total = 0
    for shot in shots:
        d = float(shot.get("duration_s", 5.0))
        total += per_5s * (d / 5.0)
    return int(total)


def run_pipeline(storyboard: dict, output_mp4: str) -> dict:
    style = storyboard.get("style", "realistic")
    aspect = storyboard.get("aspect", "16:9")
    resolution = storyboard.get("resolution", "1080p")
    shots = storyboard.get("shots", [])
    characters = {c.get("name", ""): c for c in storyboard.get("characters", [])}

    if not shots:
        return {"ok": False, "error": "no shots in storyboard"}

    gen_w, gen_h, upscale_factor = resolution_for_generation(resolution, aspect)
    # v83 : the real target the user asked for. Shots render at gen_w x gen_h
    # (GPU-safe) and concat_shots upscales the final to target_w x target_h.
    target_w, target_h = parse_resolution(resolution, aspect)
    emit("plan", f"{len(shots)} plans, gen {gen_w}x{gen_h} -> final {target_w}x{target_h}")

    estimated = estimate_total_seconds(shots, style, resolution)
    emit("estimate", f"~{estimated // 60} min total")

    work_dir = TEMP_DIR / f"job_{int(time.time())}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # v82l6 : pre-generate character keyframes via FLUX so each shot
    # featuring the same character keeps the same face/silhouette/outfit.
    # v82ld : also retain the vision LLM score for each keyframe so the
    # final result JSON exposes "Shadow keyframe: 9/10" to the UI.
    char_keyframes = {}
    char_quality = {}
    location_backdrops = {}
    if characters:
        emit("char_phase", f"keyframes for {len(characters)} character(s)")
        char_keyframes = pregenerate_character_keyframes(
            characters, work_dir, style, gen_w, gen_h,
        )
        # v90.5 : fonds de décor pour les lieux qui s'ouvrent sur un dialogue
        # close-up (aucune ancre de scène disponible à ce moment-là). Générés
        # ici, pendant que FLUX/ComfyUI est encore chargé, avant le /free.
        for loc_key, loc_scene in collect_backdrop_locations(shots, characters):
            backdrop = generate_scene_backdrop(
                loc_scene, style, work_dir, loc_key, gen_w, gen_h,
            )
            if backdrop:
                location_backdrops[loc_key] = backdrop
                emit("backdrop_ok", f"{loc_key} -> {Path(backdrop).name}")
        # v82m1 : libère la VRAM ComfyUI (FLUX) après les keyframes pour
        # que Wan2.2 ait les ~10 GB nécessaires. Sans ça, exit 3221225477
        # ACCESS_VIOLATION quand le modèle vidéo essaie de s'allouer.
        try:
            import urllib.request as _ur
            req = _ur.Request(
                "http://127.0.0.1:8188/free",
                data=b'{"unload_models":true,"free_memory":true}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            _ur.urlopen(req, timeout=10).read()
            emit("vram_free", "ComfyUI unloaded — VRAM libérée pour Wan2.2")
        except Exception as _e:
            emit("vram_warn", f"comfy /free failed: {str(_e)[:80]}")
        # Re-run vision validation once on the FINAL keyframe per character
        # to grab a definitive score for the result payload.
        for name, path in char_keyframes.items():
            desc = (characters.get(name, {}).get("description") or "").strip()
            if desc and Path(path).exists():
                check = validate_keyframe_with_vision(path, desc)
                char_quality[name] = {
                    "score": check.get("score"),
                    "reason": check.get("reason"),
                    "ok": check.get("ok"),
                    "graded": check.get("graded", check.get("score") is not None),
                    "keyframe_path": path,
                }

    shot_files = []
    accepted_render_metadata = []
    shot_quality = []  # v82lk : per-shot vision scores
    audio_quality = []  # v82lq : per-shot audio silence/integrity scores
    dialogue_quality = []  # v86 : per-shot voice + lipsync contract state
    temporal_quality = []  # v82ls : per-shot scene-cut detection
    started = time.time()
    initial_scene_anchor = storyboard.get("initial_scene_anchor") or storyboard.get("scene_anchor")
    if initial_scene_anchor and not Path(str(initial_scene_anchor)).exists():
        initial_scene_anchor = None
    scene_anchor = str(initial_scene_anchor) if initial_scene_anchor else None
    # v90 : ancres de continuité par LIEU. Le storyboard peut fournir un champ
    # `location` (identifiant stable par décor) ; la dernière frame de chaque
    # plan y est mémorisée et sert d'ancre i2v aux plans suivants au même
    # endroit — y compris les plans muets, qui repartaient de zéro avant
    # (décor qui changeait d'un plan à l'autre = rupture de suivi long).
    location_anchors = {}
    scene_anchor_location = ""

    # v90.1 : verrouillage d'apparence — injecte la description de chaque
    # personnage mentionné dans les scènes qui ne la portent pas déjà.
    # Défense au rendu : couvre les storyboards arrivés par UI, CLI ou tunnel
    # sans repasser par la normalisation bridge.
    try:
        from storyboard_norm import _inject_character_descriptions, align_voice_language
        # v90.4 : aligne la langue des voix sur la langue réelle des dialogues
        # (Sherlock anglais + dialogues français -> voix française). Mute les
        # dicts personnages en place — le mapping `characters` voit le fix.
        align_voice_language(storyboard)
        for shot in shots:
            if isinstance(shot, dict):
                _inject_character_descriptions(shot, storyboard.get("characters") or [])
    except Exception as _e:
        emit("norm_warn", f"description inject skip: {str(_e)[:80]}")

    for idx, shot in enumerate(shots, 1):
        shot_id = shot.get("id", idx)
        scene = shot.get("scene", "")
        speaker = shot.get("speaker")
        dialogue = (shot.get("dialogue") or "").strip()
        duration = float(shot.get("duration_s", 5.0))
        action_contract = (shot.get("action_contract") or "").strip()
        needs_lipsync = bool(shot.get("needs_lipsync", bool(dialogue)))
        location = str(shot.get("location") or "").strip().lower()

        emit("shot_start", f"plan {idx}/{len(shots)}: {scene[:60]}")

        # v90 : voix AVANT rendu. La durée réelle de la parole TTS pilote la
        # durée du plan — avant, le WAV était synthétisé après le rendu et
        # muxé en -shortest : tout dialogue plus long que le clip était coupé
        # en plein milieu de phrase.
        voice_wav_path = None
        voice_result = None
        speech_s = 0.0
        if dialogue and speaker and speaker in characters:
            char_meta = characters[speaker]
            voice_wav = work_dir / f"shot_{shot_id:02d}_voice.wav"
            voice_result = synthesize_voice(
                dialogue,
                char_meta.get("voice_slug") or speaker.lower().replace(" ", "_"),
                char_meta.get("voice_lang", "fr"),
                str(voice_wav),
                voice_preset=char_meta.get("voice_preset") or "",
                voice_policy=char_meta.get("voice_policy") or "",
                public_figure=bool(char_meta.get("public_figure")),
            )
            if voice_result.get("ok"):
                voice_wav_path = str(voice_result.get("wav") or voice_wav)
                speech_s = probe_audio_duration(voice_wav_path)

        effective_duration = duration
        if speech_s > 0:
            # v90.1 : la parole pilote la durée dans les DEUX sens. MuseTalk
            # trime de toute façon sa sortie à la durée audio : rendre 6.5 s
            # de Wan pour une parole de 4.4 s = 2 s de GPU jetées (constaté en
            # E2E). Un plan parlé dure la parole + ~0.4-1.0 s de respiration.
            effective_duration = max(2.5, min(duration, speech_s + 1.0), speech_s + 0.4)
            if abs(effective_duration - duration) > 0.25:
                emit(
                    "duration_fit",
                    f"plan {idx}: parole {speech_s:.1f}s, plan {duration:.1f}s "
                    f"-> duree effective {effective_duration:.1f}s",
                )

        # v82l6/v84 : use an i2v anchor for character continuity. Dialogue
        # shots use the speaker; silent shots use the first mentioned
        # character in the scene text.
        anchor_name, anchor = select_anchor_character(shot, speaker, characters, char_keyframes)
        camera = str(shot.get("camera") or "").lower()
        # v90.1 : l'ancre de scène (v86) ne s'applique que si le plan reste
        # dans le MÊME lieu que celui où l'ancre a été capturée. Testé en E2E :
        # un flashback tempête ancré sur la frame du port calme du plan
        # précédent héritait du mauvais décor ("calm dock instead of stormy
        # boat", QA 2/10). Changement de lieu -> l'ancre du lieu correspondant
        # (location_anchors) ou rien.
        same_place = (not location and not scene_anchor_location) or (location == scene_anchor_location)
        if (dialogue or needs_lipsync) and scene_anchor and "close" not in camera and same_place:
            anchor_name, anchor = "__scene_continuity__", scene_anchor
        elif (
            location
            and location_anchors.get(location)
            and "close" not in camera
        ):
            # v90 : plan (muet ou parlé) qui revient dans un décor déjà vu ->
            # ancre sur la dernière frame de ce lieu. Prime sur le portrait
            # studio du personnage pour les plans larges/moyens : la frame du
            # lieu contient déjà décor ET personnages en situation.
            anchor_name, anchor = "__location_continuity__", location_anchors[location]

        # v82ln : negative prompt par shot (anti-artefacts). Default conservatif
        # si LLM n'a pas fourni.
        DEFAULT_NEG = "deformed, blurry, low quality, watermark, extra limbs, distorted face, bad anatomy, ugly, poorly drawn"
        neg = (shot.get("negative_prompt") or "").strip() or DEFAULT_NEG

        # v82lo : seed déterministe par shot (id stable -> reproductible).
        # Si shot.seed fourni explicitement (re-render), use it. Sinon dérivé
        # du shot_id pour que ré-runs produisent même résultat sans changer
        # de plan.
        shot_seed = shot.get("seed")
        if shot_seed is None:
            shot_seed = 1000 + (shot_id * 31)  # deterministic per shot_id

        # Step 1: render and validate the silent video. Premium/balanced modes
        # get one validation-driven retry. The retry prompt contains the
        # concrete QA failures reported by the vision checks.
        render_scene_base = scene
        if action_contract:
            render_scene_base = f"{scene}. REQUIRED ACTION LOGIC: {action_contract}"
        quality_mode = storyboard.get("quality_mode", "auto")
        max_quality_attempts = 3 if quality_mode == "premium" and should_auto_retry_shots(storyboard) else (2 if should_auto_retry_shots(storyboard) else 1)
        try:
            max_quality_attempts = int(storyboard.get("max_quality_attempts") or max_quality_attempts)
        except Exception:
            pass
        if shot.get("max_quality_attempts") is not None:
            try:
                max_quality_attempts = int(shot.get("max_quality_attempts"))
            except Exception:
                pass
        max_quality_attempts = max(1, min(4, max_quality_attempts))
        manual_accept_floor = shot.get("manual_accept_quality_floor")

        def manual_accepts_quality(qa: dict) -> bool:
            if manual_accept_floor is None or not shot_quality_is_measured(qa):
                return False
            try:
                return shot_quality_average(qa) >= float(manual_accept_floor)
            except Exception:
                return False

        # v91 — LE PLAN FIGE N'A DE SENS QUE SI UN LIPSYNC PEUT L'ANIMER.
        # Ce chemin fabrique un composite (portrait + fond) puis une video
        # STRICTEMENT FIXE, en pariant sur le lipsync pour animer la bouche.
        # Quand aucun moteur de lipsync n'est installe, le pari est perdu et le
        # plan reste une photographie avec une bande son.
        # Mesure sur un film reel : mouvement inter-frames de 0.00 sur les deux
        # plans dialogues, contre 3.12 et 12.05 sur les plans generes. Le
        # spectateur voit des images collees qui ne parlent pas.
        # Desormais : sans moteur de lipsync, on repasse par la generation i2v
        # normale — les levres ne seront pas synchronisees, mais le personnage
        # bouge, respire et le plan vit. Un plan anime imparfait vaut mieux
        # qu'une photographie muette.
        lipsync_engine_ready = lipsync_available()
        dialogue_closeup_source = bool(
            dialogue
            and needs_lipsync
            and "close" in camera
            and anchor
            and Path(str(anchor)).exists()
            and lipsync_engine_ready
        )
        if (dialogue and needs_lipsync and "close" in camera
                and anchor and not lipsync_engine_ready):
            emit(
                "lipsync_absent",
                f"plan {idx}: aucun moteur de lipsync installe -> generation "
                f"animee au lieu d'une image fixe (levres non synchronisees)",
            )
        if dialogue_closeup_source:
            max_quality_attempts = 1
        strict_quality_gate = storyboard.get("strict_quality_gate")
        if strict_quality_gate is None:
            strict_quality_gate = quality_mode == "premium"
        strict_quality_gate = bool(strict_quality_gate)
        candidate_results = []
        previous_qa = None
        last_render_error = None

        for quality_attempt in range(1, max_quality_attempts + 1):
            candidate_scene = render_scene_base
            candidate_anchor = anchor
            candidate_neg = neg
            if quality_attempt > 1 and previous_qa:
                candidate_scene = retry_scene_prompt(
                    scene=render_scene_base,
                    style_id=style,
                    camera=shot.get("camera"),
                    issues=previous_qa.get("issues", []),
                    reason=previous_qa.get("reason") or "",
                    attempt=quality_attempt,
                )
                candidate_neg = combine_negative_prompt(
                    neg,
                    "wrong scene, missing required subject, missing required action, extra character, style drift",
                )
                emit(
                    "shot_autoretry",
                    f"plan {idx} retry {quality_attempt}/{max_quality_attempts}: "
                    f"prev scene={previous_qa.get('score')}/10 "
                    f"phys={previous_qa.get('physics_score')}/10 "
                    f"id={previous_qa.get('identity_score')}/10 "
                    f"act={previous_qa.get('action_score')}/10",
                )

            suffix = "" if quality_attempt == 1 else f"_retry{quality_attempt - 1}"
            silent_mp4_candidate = work_dir / f"shot_{shot_id:02d}_silent{suffix}.mp4"
            candidate_seed = int(shot_seed) + ((quality_attempt - 1) * 9973)
            if dialogue_closeup_source:
                source_image = str(anchor)
                # v90.5 : fond du composite par priorité — dernière frame vue
                # dans CE lieu, puis ancre de scène du même lieu, puis fond
                # FLUX pré-généré. Avant, un plan 1 en dialogue close-up
                # composait sur RIEN (fond studio du keyframe).
                backdrop_png = None
                if location and location_anchors.get(location) and Path(str(location_anchors[location])).exists():
                    backdrop_png = str(location_anchors[location])
                elif scene_anchor and Path(str(scene_anchor)).exists() and same_place:
                    backdrop_png = str(scene_anchor)
                elif location and location_backdrops.get(location) and Path(str(location_backdrops[location])).exists():
                    backdrop_png = str(location_backdrops[location])
                if backdrop_png:
                    source_png = work_dir / f"shot_{shot_id:02d}_dialogue_source.png"
                    source_result = make_dialogue_source_image(
                        str(anchor),
                        backdrop_png,
                        str(source_png),
                        gen_w,
                        gen_h,
                    )
                    if source_result.get("ok"):
                        source_image = str(source_result.get("image") or source_png)
                        emit("shot_render", f"dialogue source composite {Path(source_image).name}")
                    else:
                        emit("shot_warn", f"dialogue composite failed: {source_result.get('error', '')[:100]}")
                emit("shot_render", f"talking-head source {Path(str(source_image)).name}")
                result = make_still_video(
                    str(source_image),
                    effective_duration,
                    str(silent_mp4_candidate),
                    gen_w,
                    gen_h,
                )
                if result.get("ok"):
                    # v90.5 : QA VISION RÉELLE du composite. L'ancien 8/10
                    # hardcodé a laissé passer 15 s de Sherlock sur fond
                    # studio blanc au lieu du salon au coin du feu.
                    triplet = extract_keyframes_triplet(
                        str(silent_mp4_candidate), work_dir, shot_id,
                    )
                    scene_check = {
                        "score": None,
                        "reason": "frame extraction failed",
                        "ok": False,
                        "graded": False,
                    }
                    if triplet.get("mid"):
                        scene_check = validate_keyframe_with_vision(
                            triplet["mid"],
                            scene + style_validation_contract(style),
                        )
                    phys_check = validate_shot_physics(
                        triplet,
                        scene,
                        character_desc=(characters.get(speaker, {}) or {}).get("description", ""),
                        action_contract=action_contract,
                    )
                    qa = {
                        "shot_id": shot_id,
                        "scene_excerpt": scene[:120],
                        "score": scene_check.get("score"),
                        "reason": scene_check.get("reason"),
                        "ok": scene_check.get("ok"),
                        "physics_score": phys_check.get("physics_score"),
                        "identity_score": phys_check.get("identity_score"),
                        "action_score": phys_check.get("action_score"),
                        "issues": phys_check.get("issues", []),
                        "graded": (
                            scene_check.get("score") is not None
                            and phys_check.get("physics_score") is not None
                            and phys_check.get("identity_score") is not None
                            and phys_check.get("action_score") is not None
                        ),
                        "attempt": quality_attempt,
                        "avg_score": round(shot_quality_average({
                            "score": scene_check.get("score"),
                            "physics_score": phys_check.get("physics_score"),
                            "identity_score": phys_check.get("identity_score"),
                            "action_score": phys_check.get("action_score"),
                        }), 2),
                    }
                    candidate_results.append((qa, silent_mp4_candidate, result))
                    emit(
                        "shot_score",
                        f"plan {idx} attempt {quality_attempt}: scene={scene_check.get('score')}/10 "
                        f"phys={qa.get('physics_score')}/10 "
                        f"id={qa.get('identity_score')}/10 "
                        f"act={qa.get('action_score')}/10 (composite)",
                    )
                    break
            else:
                # v90 : render_long_shot segmente automatiquement les plans
                # dont la durée dépasse ~4 s (cap Wan 97 frames) au lieu de
                # les raccourcir silencieusement.
                result = render_long_shot(
                    scene_prompt=candidate_scene,
                    style_id=style,
                    duration_s=effective_duration,
                    width=gen_w,
                    height=gen_h,
                    output_mp4=str(silent_mp4_candidate),
                    work_dir=work_dir,
                    shot_id=shot_id,
                    quality_mode=quality_mode,
                    anchor_image=candidate_anchor,
                    negative_prompt=candidate_neg,
                    seed=candidate_seed,
                    camera=shot.get("camera"),
                    attempt_tag=suffix,
                )
            if not result.get("ok"):
                last_render_error = result.get("error")
                if quality_attempt >= max_quality_attempts:
                    break
                previous_qa = {
                    "score": 0,
                    "physics_score": 0,
                    "identity_score": 0,
                    "action_score": 0,
                    "reason": "render process failed before a usable video was produced",
                    "issues": ["render failed"],
                }
                emit("shot_retry", f"plan {idx} render failed -> retry")
                continue

            text_locks = shot.get("text_locks") or shot.get("text_lock")
            if text_locks:
                locked_mp4 = work_dir / f"shot_{shot_id:02d}_silent_textlock_attempt{quality_attempt}.mp4"
                lock_result = apply_text_locks(
                    str(silent_mp4_candidate),
                    str(locked_mp4),
                    work_dir,
                    shot_id,
                    text_locks,
                )
                if lock_result.get("ok") and int(lock_result.get("applied") or 0) > 0:
                    silent_mp4_candidate = Path(lock_result.get("mp4") or locked_mp4)
                    emit("text_lock", f"plan {idx}: applied {lock_result.get('applied')} exact text lock(s)")
                elif not lock_result.get("ok"):
                    msg = f"plan {idx} text lock failed: {str(lock_result.get('error') or '')[:120]}"
                    emit("shot_warn", msg)
                    if shot.get("text_lock_required"):
                        last_render_error = msg
                        if quality_attempt >= max_quality_attempts:
                            break
                        continue

            try:
                char_desc = ""
                if shot.get("validate_character", True):
                    if candidate_anchor and anchor_name and anchor_name in characters:
                        char_desc = (characters[anchor_name].get("description") or "").strip()
                    elif speaker and speaker in characters:
                        char_desc = (characters[speaker].get("description") or "").strip()
                qa = validate_rendered_shot(
                    final_mp4=str(silent_mp4_candidate),
                    work_dir=work_dir,
                    shot_id=shot_id,
                    scene=scene,
                    style_id=style,
                    character_desc=char_desc,
                    action_contract=action_contract,
                    attempt=quality_attempt,
                )
            except Exception as _e:
                emit("shot_score_warn", f"plan {idx} validation failed: {str(_e)[:80]}")
                qa = {
                    "shot_id": shot_id, "scene_excerpt": scene[:120],
                    "score": None, "reason": str(_e)[:120], "ok": False,
                    "physics_score": None, "identity_score": None, "action_score": None, "issues": [],
                    "graded": False,
                    "attempt": quality_attempt, "avg_score": 0.0,
                }

            candidate_results.append((qa, silent_mp4_candidate, result))
            emit(
                "shot_score",
                f"plan {idx} attempt {quality_attempt}: scene={qa.get('score')}/10 "
                f"phys={qa.get('physics_score')}/10 id={qa.get('identity_score')}/10 "
                f"act={qa.get('action_score')}/10",
            )
            for issue in (qa.get("issues") or [])[:3]:
                emit("shot_issue", f"plan {idx}: {issue[:100]}")

            # Re-rendering cannot repair an unavailable/invalid QA response.
            # Keep the candidate with an explicit ungraded warning instead of
            # burning another multi-minute GPU attempt for the same frames.
            if not shot_quality_is_measured(qa):
                emit("shot_ungraded", f"plan {idx}: validation indisponible, rendu conservé sans note")
                break
            if shot_quality_ok(qa, quality_mode):
                break
            if manual_accepts_quality(qa):
                emit(
                    "shot_accept_manual",
                    f"plan {idx} accepted by manual floor avg={shot_quality_average(qa):.1f}/10",
                )
                break
            previous_qa = qa
            if quality_attempt < max_quality_attempts:
                emit(
                    "shot_reject",
                    f"plan {idx} below threshold avg={shot_quality_average(qa):.1f}/10 -> corrective retry",
                )

        if not candidate_results:
            return {"ok": False, "error": f"shot {idx} render failed: {last_render_error}", "shot": idx}

        passing_candidates = [
            item for item in candidate_results
            if shot_quality_ok(item[0], quality_mode)
        ]
        accepted_qa, silent_mp4, accepted_render = sorted(
            passing_candidates or candidate_results,
            key=lambda item: shot_quality_average(item[0]),
            reverse=True,
        )[0]
        segment_metadata = list(accepted_render.get("segment_results") or [])
        if segment_metadata:
            for segment_index, segment in enumerate(segment_metadata, 1):
                accepted_render_metadata.append({
                    "shot_id": shot_id,
                    "segment": segment_index,
                    "model": segment.get("model"),
                    "strategy": segment.get("strategy"),
                    **(segment.get("render_truth") or {}),
                })
        else:
            accepted_render_metadata.append({
                "shot_id": shot_id,
                "segment": 1,
                "model": accepted_render.get("model") or (
                    "still_frame" if dialogue_closeup_source else None
                ),
                "strategy": accepted_render.get("strategy") or (
                    "still_dialogue_source" if dialogue_closeup_source else None
                ),
                **(accepted_render.get("render_truth") or {}),
            })
        if not shot_quality_ok(accepted_qa, quality_mode):
            quality_error = (
                f"plan {idx} failed quality gate avg={shot_quality_average(accepted_qa):.1f}/10 "
                f"scene={accepted_qa.get('score')}/10 phys={accepted_qa.get('physics_score')}/10 "
                f"id={accepted_qa.get('identity_score')}/10 act={accepted_qa.get('action_score')}/10"
            )
            if manual_accepts_quality(accepted_qa):
                emit(
                    "shot_accept_manual",
                    f"plan {idx} accepted best candidate by manual floor avg={shot_quality_average(accepted_qa):.1f}/10",
                )
            elif strict_quality_gate and shot_quality_is_measured(accepted_qa):
                emit("shot_fail_quality", quality_error)
                return {
                    "ok": False,
                    "error": quality_error,
                    "shot": idx,
                    "quality": accepted_qa,
                }
            # v91 — PLANCHER ABSOLU. Constat sur un film reel : le juge a note
            # un plan 2.8/10 avec l'issue "wheels are stationary despite
            # required continuous motion", a relance deux fois, a echoue deux
            # fois... puis a livre quand meme via shot_accept_best. Un autre
            # plan a ete accepte a 0.0/10.
            # `strict_quality_gate` est un choix de l'appelant, mais il ne peut
            # pas autoriser l'indefendable : sous ce plancher, et seulement si
            # la qualite a REELLEMENT ete mesuree (une panne vision ne doit
            # jamais faire echouer un film), on refuse.
            avg = shot_quality_average(accepted_qa)
            if shot_quality_is_measured(accepted_qa) and avg < ABSOLUTE_QUALITY_FLOOR:
                emit("shot_fail_floor",
                     f"{quality_error} — sous le plancher absolu "
                     f"{ABSOLUTE_QUALITY_FLOOR}/10, plan refuse")
                return {
                    "ok": False,
                    "error": quality_error + f" (plancher absolu {ABSOLUTE_QUALITY_FLOOR}/10)",
                    "shot": idx,
                    "quality": accepted_qa,
                }
            emit(
                "shot_accept_best",
                f"plan {idx} accepted best available avg={avg:.1f}/10",
            )
        shot_quality.append(accepted_qa)

        # Step 2: dialogue + lipsync. v90 : la voix a déjà été synthétisée en
        # tête de boucle (voice-first) ; on la consomme ici. mux_audio_fit
        # remplace l'ancien mux -shortest : la vidéo est prolongée si besoin,
        # la parole n'est plus jamais tronquée.
        final_mp4 = silent_mp4
        if dialogue and speaker and speaker in characters:
            voice_preset = characters[speaker].get("voice_preset") or ""
            if not (voice_result and voice_result.get("ok") and voice_wav_path):
                err_txt = (voice_result or {}).get("error", "voice synthesis failed")
                emit("voice_warn", f"plan {idx} sans dialogue: {str(err_txt)[:80]}")
                dialogue_quality.append({
                    "shot": shot_id,
                    "speaker": speaker,
                    "voice_ok": False,
                    "lipsync_required": needs_lipsync,
                    "lipsync_ok": False,
                    "error": str(err_txt),
                })
                # Continue without dialogue rather than crash the whole pipeline
            else:
                # v91 : ne PAS tenter un lipsync quand aucun moteur n'est
                # installe. Le plan a deja ete GENERE anime pour cette raison
                # (cf. lipsync_absent plus haut) ; retenter ici produisait une
                # erreur "lipsync required but failed" qui, sous porte stricte,
                # faisait echouer tout le film au plan 1 — alors que
                # l'absence de moteur est une limite CONNUE de l'installation,
                # pas un defaut du rendu. On mute donc le contrat en
                # "impossible" (et non "echoue"), on muxe la voix, et on
                # remonte l'information sans condamner le film.
                if needs_lipsync and not lipsync_engine_ready:
                    muxed_mp4 = work_dir / f"shot_{shot_id:02d}_muxed.mp4"
                    mux_result = mux_audio_fit(str(silent_mp4), voice_wav_path,
                                               str(muxed_mp4))
                    if mux_result.get("ok"):
                        final_mp4 = muxed_mp4
                    warnings.append(
                        f"plan {idx}: lipsync impossible (aucun moteur installe) "
                        f"— plan genere anime, levres non synchronisees")
                    dialogue_quality.append({
                        "shot": shot_id,
                        "speaker": speaker,
                        "voice_ok": True,
                        "voice_engine": voice_result.get("engine"),
                        "voice_preset": voice_result.get("voice_preset") or voice_preset,
                        "lipsync_required": True,
                        "lipsync_ok": False,
                        "lipsync_impossible": True,
                        "error": "aucun moteur de lipsync installe",
                    })
                elif needs_lipsync:
                    sync_mp4 = work_dir / f"shot_{shot_id:02d}_synced.mp4"
                    sync_result = apply_lipsync(str(silent_mp4), voice_wav_path, str(sync_mp4))
                    if sync_result.get("ok"):
                        final_mp4 = Path(sync_result.get("mp4") or sync_mp4)
                        dialogue_quality.append({
                            "shot": shot_id,
                            "speaker": speaker,
                            "voice_ok": True,
                            "voice_engine": voice_result.get("engine"),
                            "voice_preset": voice_result.get("voice_preset") or voice_preset,
                            "lipsync_required": True,
                            "lipsync_ok": True,
                            "lipsync_engine": sync_result.get("engine"),
                        })
                    else:
                        lipsync_error = f"plan {idx} lipsync required but failed: {sync_result.get('error', '')[:160]}"
                        emit("lipsync_warn", lipsync_error)
                        dialogue_quality.append({
                            "shot": shot_id,
                            "speaker": speaker,
                            "voice_ok": True,
                            "voice_engine": voice_result.get("engine"),
                            "voice_preset": voice_result.get("voice_preset") or voice_preset,
                            "lipsync_required": True,
                            "lipsync_ok": False,
                            "error": sync_result.get("error", ""),
                        })
                        if strict_quality_gate:
                            return {
                                "ok": False,
                                "error": lipsync_error,
                                "shot": idx,
                                "dialogue_quality": dialogue_quality,
                            }
                        # Non-strict fallback: mux audio but expose lipsync_ok=false.
                        muxed_mp4 = work_dir / f"shot_{shot_id:02d}_muxed.mp4"
                        mux_result = mux_audio_fit(str(silent_mp4), voice_wav_path, str(muxed_mp4))
                        if mux_result.get("ok"):
                            final_mp4 = muxed_mp4
                else:
                    muxed_mp4 = work_dir / f"shot_{shot_id:02d}_muxed.mp4"
                    mux_result = mux_audio_fit(str(silent_mp4), voice_wav_path, str(muxed_mp4))
                    if mux_result.get("ok"):
                        final_mp4 = muxed_mp4
                        dialogue_quality.append({
                            "shot": shot_id,
                            "speaker": speaker,
                            "voice_ok": True,
                            "voice_engine": voice_result.get("engine"),
                            "voice_preset": voice_result.get("voice_preset") or voice_preset,
                            "lipsync_required": False,
                            "lipsync_ok": None,
                        })

        # v82lk + v82lp : multi-frame validation (start/mid/end) pour
        # physics + identity drift + scene match. 3 scores complementaires
        # informational only — no auto-retry (5-10 min/shot trop cher).
        try:
            triplet = extract_keyframes_triplet(str(final_mp4), work_dir, shot_id)
            if dialogue_closeup_source:
                scene_score_data = {
                    "score": None,
                    "reason": "frame extraction failed",
                    "ok": False,
                    "graded": False,
                }
                if triplet.get("mid"):
                    scene_score_data = validate_keyframe_with_vision(
                        triplet["mid"],
                        scene + style_validation_contract(style),
                    )
                phys_data = validate_shot_physics(
                    triplet,
                    scene,
                    character_desc=(characters.get(speaker, {}) or {}).get("description", ""),
                    action_contract=action_contract,
                )
            else:
                char_desc = ""
                if shot.get("validate_character", True):
                    if anchor_name and anchor_name in characters:
                        char_desc = (characters[anchor_name].get("description") or "").strip()
                    elif speaker and speaker in characters:
                        char_desc = (characters[speaker].get("description") or "").strip()

                # Scene match score (existing v82lk via mid frame).
                scene_score_data = {
                    "score": None,
                    "reason": "frame extraction failed",
                    "ok": False,
                    "graded": False,
                }
                if triplet.get("mid"):
                    scene_score_data = validate_keyframe_with_vision(
                        triplet["mid"],
                        scene + style_validation_contract(style),
                    )

                # Physics + identity + visible action causality.
                phys_data = validate_shot_physics(
                    triplet,
                    scene,
                    character_desc=char_desc,
                    action_contract=action_contract,
                )

            post_qa = {
                "shot_id": shot_id,
                "scene_excerpt": scene[:120],
                "score": scene_score_data.get("score"),  # legacy compat
                "reason": scene_score_data.get("reason"),
                "ok": scene_score_data.get("ok"),
                # v82lp : new fields
                "physics_score": phys_data.get("physics_score"),
                "identity_score": phys_data.get("identity_score"),
                "action_score": phys_data.get("action_score"),
                "issues": phys_data.get("issues", []),
                "graded": (
                    scene_score_data.get("score") is not None
                    and phys_data.get("physics_score") is not None
                    and phys_data.get("identity_score") is not None
                    and phys_data.get("action_score") is not None
                ),
            }
            shot_quality.append(post_qa)
            emit(
                "shot_score",
                f"plan {idx}: scene={scene_score_data.get('score')}/10 "
                f"phys={phys_data.get('physics_score')}/10 "
                f"id={phys_data.get('identity_score')}/10 "
                f"act={phys_data.get('action_score')}/10",
            )
            for issue in (phys_data.get("issues") or [])[:3]:
                emit("shot_issue", f"plan {idx}: {issue[:100]}")
            if (
                strict_quality_gate
                and shot_quality_is_measured(post_qa)
                and not shot_quality_ok(post_qa, quality_mode)
                and not dialogue_closeup_source
                and not manual_accepts_quality(post_qa)
            ):
                quality_error = (
                    f"plan {idx} failed post-audio quality gate avg={shot_quality_average(post_qa):.1f}/10 "
                    f"scene={post_qa.get('score')}/10 phys={post_qa.get('physics_score')}/10 "
                    f"id={post_qa.get('identity_score')}/10 act={post_qa.get('action_score')}/10"
                )
                emit("shot_fail_quality", quality_error)
                return {
                    "ok": False,
                    "error": quality_error,
                    "shot": idx,
                    "quality": post_qa,
                }
            if "close" not in str(shot.get("camera") or "").lower() and triplet.get("end"):
                scene_anchor = triplet.get("end")
                scene_anchor_location = location
                # v90 : mémorise aussi la dernière frame par lieu pour ancrer
                # les futurs plans qui reviennent dans ce décor.
                if location:
                    location_anchors[location] = triplet.get("end")
        except Exception as _e:
            emit("shot_score_warn", f"plan {idx} validation failed: {str(_e)[:80]}")
            shot_quality.append({
                "shot_id": shot_id, "scene_excerpt": scene[:120],
                "score": None, "reason": str(_e)[:120], "ok": False,
                "physics_score": None, "identity_score": None, "action_score": None, "issues": [],
                "graded": False,
            })

        # v90 : durée RÉELLE du clip livré. Sert au SRT, au check audio et à
        # l'intégrité finale — la durée théorique du storyboard ne reflète ni
        # le cap frames de Wan ni les clips lipsync (durée = audio).
        real_dur = probe_video_duration(str(final_mp4))
        shot["actual_duration_s"] = round(real_dur, 3) if real_dur > 0 else effective_duration

        # v82lq : audio integrity check (silence detect + has_audio).
        try:
            audio_check = check_audio_silence(
                str(final_mp4),
                expected_duration_s=float(shot["actual_duration_s"]),
                expected_dialogue=bool(dialogue),
            )
            audio_check["shot_id"] = shot_id
            audio_quality.append(audio_check)
            if not audio_check.get("ok") and dialogue:
                if strict_quality_gate:
                    return {
                        "ok": False,
                        "error": f"plan {idx} dialogue audio missing or silent",
                        "shot": idx,
                        "audio_quality": audio_check,
                    }
                emit("audio_warn", f"plan {idx} silence_ratio={audio_check.get('silence_ratio')} (dialogue présent)")
        except Exception as _e:
            emit("audio_warn", f"plan {idx} audio check failed: {str(_e)[:80]}")

        # v82ls : temporal coherence (no scene cuts inside the shot).
        try:
            temporal_check = check_temporal_coherence(str(final_mp4))
            temporal_check["shot_id"] = shot_id
            temporal_quality.append(temporal_check)
            if not temporal_check.get("ok"):
                emit("temporal_warn", f"plan {idx} {temporal_check.get('cuts_count')} cuts internes (téléportation/jump)")
        except Exception as _e:
            emit("temporal_warn", f"plan {idx} temporal check failed: {str(_e)[:80]}")

        shot_files.append(str(final_mp4))
        elapsed = time.time() - started
        emit_eta(elapsed, idx, len(shots), f"plan {idx} ok")
        gc.collect()

    # Step 3: concat all shots into final video
    concat_target = output_mp4
    subtitles_flag = bool(storyboard.get("subtitles", {}).get("enabled", False))
    if subtitles_flag:
        # Concat to intermediate then mux subtitles into the final.
        concat_target = str(Path(output_mp4).with_suffix(".nosubs.mp4"))
    final_result = concat_shots(shot_files, concat_target, target_w, target_h)
    if not final_result.get("ok"):
        return {"ok": False, "error": f"concat failed: {final_result.get('error')}"}

    # v90 : piste musicale du storyboard, jusqu'ici ignorée. Best-effort :
    # générée via MusicGen puis mixée SOUS les voix (volume bas), avant le
    # mux des sous-titres pour ne pas perdre la piste mov_text.
    music_info = None
    music_cfg = storyboard.get("music") or {}
    if music_cfg.get("enabled") and str(music_cfg.get("prompt") or "").strip():
        try:
            total_real = probe_video_duration(concat_target)
            music_wav = work_dir / "music.wav"
            emit("music", f"MusicGen {total_real:.0f}s: {str(music_cfg.get('prompt'))[:60]}")
            music_result = render_music_track(
                str(music_cfg.get("prompt")).strip(),
                total_real,
                str(music_wav),
            )
            if music_result.get("ok"):
                mixed_mp4 = str(Path(concat_target).with_suffix(".music.mp4"))
                mix_result = mix_music_under(concat_target, str(music_wav), mixed_mp4)
                if mix_result.get("ok"):
                    Path(mixed_mp4).replace(concat_target)
                    music_info = {"ok": True, "prompt": music_cfg.get("prompt")}
                else:
                    emit("music_warn", f"mix failed: {mix_result.get('error', '')[:100]}")
                    music_info = {"ok": False, "error": mix_result.get("error", "")}
            else:
                emit("music_warn", f"musicgen failed: {music_result.get('error', '')[:100]}")
                music_info = {"ok": False, "error": music_result.get("error", "")}
        except Exception as _e:
            emit("music_warn", f"music step failed: {str(_e)[:100]}")
            music_info = {"ok": False, "error": str(_e)[:200]}

    # v82le : embed subtitles if enabled in storyboard.
    subtitle_info = None
    if subtitles_flag:
        srt_path = work_dir / "subtitles.srt"
        srt_result = build_srt_from_storyboard(shots, str(srt_path))
        if srt_result.get("ok"):
            mux_result = mux_subtitles(concat_target, str(srt_path), output_mp4)
            if mux_result.get("ok"):
                subtitle_info = {"srt": str(srt_path), "count": srt_result["count"]}
                # Cleanup intermediate.
                try: Path(concat_target).unlink()
                except Exception: pass
            else:
                # Fallback: rename intermediate to final.
                try: Path(concat_target).rename(output_mp4)
                except Exception: pass
                emit("subtitles_warn", f"mux failed: {mux_result.get('error', '')[:80]}")
        else:
            try: Path(concat_target).rename(output_mp4)
            except Exception: pass
            emit("subtitles_warn", "no dialogue, skip subtitles")

    # v82lb : integrity check on the output mp4. Verifies presence of video
    # stream, non-zero duration, codec validity. Compare expected duration
    # (sum of shot durations) vs actual (ffprobe reports).
    # v90 : la durée attendue = somme des durées RÉELLES des clips livrés.
    # Comparer à la somme des duration_s théoriques mettait l'intégrité en
    # échec permanent sur les vidéos longues (cap Wan + clips lipsync).
    expected_total = sum(
        float(s.get("actual_duration_s") or s.get("duration_s", 5)) for s in shots
    )
    integrity = integrity_check(output_mp4, expected_duration_s=expected_total)
    emit("integrity", json.dumps(integrity, ensure_ascii=False)[:300])
    if not integrity["ok"]:
        # Don't fail the whole job — return a warning but keep the file.
        # User asked "no faux semblant" — surface the issues clearly.
        emit("integrity_warn", "; ".join(integrity.get("errors", [])))

    shot_quality = dedupe_shot_quality(shot_quality)
    quality_grade = _compute_quality_grade(
        shot_quality, audio_quality, temporal_quality, integrity, char_quality,
    )
    warnings = []
    for q in shot_quality:
        if not shot_quality_is_measured(q):
            warnings.append({
                "code": "shot_qa_ungraded",
                "shot_id": q.get("shot_id"),
                "message": "Validation visuelle incomplète : aucune note de remplacement n'a été inventée.",
                "impact": "Le rendu est conservé, mais son exportabilité qualité n'est pas certifiée.",
            })
    for name, q in (char_quality or {}).items():
        if not isinstance(q.get("score"), (int, float)) or isinstance(q.get("score"), bool):
            warnings.append({
                "code": "character_qa_ungraded",
                "character": name,
                "message": f"Le keyframe de {name} n'a pas pu être noté.",
                "impact": "La fidélité du personnage doit être contrôlée visuellement.",
            })
    for item in dialogue_quality:
        if item.get("voice_ok") is False:
            warnings.append({
                "code": "voice_missing",
                "shot_id": item.get("shot"),
                "message": "La voix demandée n'a pas été produite pour ce plan.",
                "impact": "Le plan peut être muet.",
            })
        elif item.get("lipsync_required") and item.get("lipsync_ok") is not True:
            warnings.append({
                "code": "lipsync_failed",
                "shot_id": item.get("shot"),
                "message": "La synchronisation labiale demandée n'a pas été obtenue.",
                "impact": "L'audio peut être présent sans mouvement de bouche fidèle.",
            })
    if music_info is not None and not music_info.get("ok"):
        warnings.append({
            "code": "music_failed",
            "message": "La musique demandée n'a pas pu être ajoutée.",
            "impact": "La vidéo finale ne contient pas la musique prévue.",
        })
    if not integrity.get("ok"):
        warnings.append({
            "code": "integrity_failed",
            "message": "; ".join(integrity.get("errors") or ["Contrôle d'intégrité échoué."]),
            "impact": "Le fichier peut être incomplet ou avoir une durée incorrecte.",
        })

    worker_postprocess = []
    for metadata in accepted_render_metadata:
        for step in metadata.get("postprocess_chain") or []:
            if step not in worker_postprocess:
                worker_postprocess.append(step)
    postprocess_chain = worker_postprocess + ["shot_concat"]
    if (gen_w, gen_h) != (target_w, target_h):
        postprocess_chain.append("lanczos_upscale_unsharp")
    if music_info and music_info.get("ok"):
        postprocess_chain.append("music_mix")
    if subtitle_info:
        postprocess_chain.append("subtitle_mux")
    measured_native = [
        item for item in accepted_render_metadata
        if item.get("native_width") and item.get("native_height")
    ]
    native_width = min(
        (int(item["native_width"]) for item in measured_native),
        default=gen_w,
    )
    native_height = min(
        (int(item["native_height"]) for item in measured_native),
        default=gen_h,
    )
    native_frames = sum(
        int(item.get("native_frames") or 0) for item in measured_native
    ) or None
    render_truth = probe_render_truth(
        output_mp4,
        native_width=native_width,
        native_height=native_height,
        native_fps=SEGMENT_FPS,
        native_frames=native_frames,
        native_shots=accepted_render_metadata,
        postprocess_chain=postprocess_chain,
    )
    actual = int(time.time() - started)

    # v91 — PUBLICATION AUTOMATIQUE DANS LA BIBLIOTHEQUE.
    # Le pipeline ecrivait uniquement dans temp/cinema/job_<id>/, c'est-a-dire
    # dans un repertoire TEMPORAIRE : rien n'apparaissait dans output/videos,
    # le resultat n'etait ni citable ni retrouvable, et il fallait lancer un
    # rangement a la main. Desormais chaque film est publie des sa fin, sous un
    # nom lisible, avec ses plans, ses references, son audio et son rapport.
    # Best-effort strict : une erreur de publication ne doit JAMAIS invalider un
    # film qui a demande des heures de calcul — elle est remontee en warning.
    published = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from video_library import publish_job  # noqa: E402

        published = publish_job(
            job_dir=str(Path(output_mp4).parent),
            work_dir=str(work_dir),
            title=storyboard.get("title") or "",
            final_mp4=output_mp4,
        )
        if published:
            emit("publie", published)
    except Exception as exc:  # pragma: no cover - defensif
        warnings.append(f"publication bibliotheque impossible: {exc}")
        emit("publie_warn", str(exc)[:160])

    return {
        "ok": integrity["ok"],
        "video": output_mp4,
        "library_path": published,
        "shots": len(shots),
        "actual_time_s": actual,
        "estimated_time_s": estimated,
        "integrity": integrity,
        # v82ld : expose char_quality so UI can show fidelity scores
        "char_quality": char_quality,
        # v82le : subtitle info if enabled
        "subtitles": subtitle_info,
        # v90 : music track state (None = not requested)
        "music": music_info,
        # v82lk : per-shot vision validation scores
        "shot_quality": shot_quality,
        # v82lq : per-shot audio integrity scores
        "audio_quality": audio_quality,
        # v86 : per-shot voice/lipsync contract state
        "dialogue_quality": dialogue_quality,
        # v82ls : per-shot temporal coherence (scene cuts inside shot)
        "temporal_quality": temporal_quality,
        # v82lt : aggregate quality grade (A/B/C/D)
        "quality_grade": quality_grade,
        "warnings": warnings,
        "render_truth": render_truth,
    }


def _compute_quality_grade(
    shot_quality: list,
    audio_quality: list,
    temporal_quality: list,
    integrity: dict,
    char_quality: dict,
) -> dict:
    """v82lt : Aggregate everything into a single grade A/B/C/D so user
    sees at-a-glance whether the render is broadcast-ready, acceptable,
    needs work, or is unusable.

    Weighting :
      40% shot_quality (mean of scene + physics + identity + action per shot)
      20% char_quality (mean of vision scores per character)
      15% audio_quality (mean ok rate for shots with dialogue)
      15% temporal_quality (mean ok rate)
      10% integrity (binary)

    A : >= 85% (excellent — no faux semblant)
    B : 70-84% (acceptable — minor issues)
    C : 55-69% (needs work — at least 1 shot needs redo)
    D : < 55% (unusable — re-render storyboard)
    """
    def numeric(value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def shot_avg(q: dict) -> float:
        # Missing dimensions count as zero for the grade and are separately
        # exposed by coverage. They must never be replaced by a passing score.
        return sum(
            float(q.get(key)) if numeric(q.get(key)) else 0.0
            for key in ("score", "physics_score", "identity_score", "action_score")
        ) / 4.0

    shot_items = list(shot_quality or [])
    shot_expected = max(1, len(shot_items)) * 4
    shot_measured = sum(
        1
        for q in shot_items
        for key in ("score", "physics_score", "identity_score", "action_score")
        if numeric(q.get(key))
    )
    shot_scores = [shot_avg(q) * 10 for q in shot_items] if shot_items else [0.0]
    shot_pct = sum(shot_scores) / len(shot_scores)

    char_items = list((char_quality or {}).values())
    char_expected = len(char_items)
    char_values = [float(c["score"]) for c in char_items if numeric(c.get("score"))]
    char_measured = len(char_values)
    char_pct = (sum(char_values) / char_expected * 10) if char_expected else None

    audio_items = list(audio_quality or [])
    audio_expected = len(audio_items)
    audio_measured_items = [a for a in audio_items if isinstance(a.get("ok"), bool)]
    audio_measured = len(audio_measured_items)
    audio_pct = (
        sum(1 for a in audio_measured_items if a["ok"]) / audio_expected * 100
        if audio_expected else None
    )

    temporal_items = list(temporal_quality or [])
    # Every rendered shot should receive the inexpensive temporal check.
    temporal_expected = max(len(shot_items), len(temporal_items))
    temporal_measured_items = [t for t in temporal_items if isinstance(t.get("ok"), bool)]
    temporal_measured = len(temporal_measured_items)
    temporal_pct = (
        sum(1 for t in temporal_measured_items if t["ok"]) / temporal_expected * 100
        if temporal_expected else None
    )
    integ_pct = 100.0 if integrity.get("ok") else 50.0

    weighted_metrics = [(0.40, shot_pct), (0.10, integ_pct)]
    if char_pct is not None:
        weighted_metrics.append((0.20, char_pct))
    if audio_pct is not None:
        weighted_metrics.append((0.15, audio_pct))
    if temporal_pct is not None:
        weighted_metrics.append((0.15, temporal_pct))
    applied_weight = sum(weight for weight, _ in weighted_metrics)
    overall = sum(weight * value for weight, value in weighted_metrics) / applied_weight

    expected = shot_expected + char_expected + audio_expected + temporal_expected + 1
    measured = shot_measured + char_measured + audio_measured + temporal_measured + 1
    coverage_pct = (measured / expected * 100) if expected else 0.0

    if overall >= 85: grade = "A"
    elif overall >= 70: grade = "B"
    elif overall >= 55: grade = "C"
    else: grade = "D"
    # A visually attractive render is not certifiable when much of its QA was
    # never measured. Preserve its raw score but cap the trust grade.
    if coverage_pct < 50:
        grade = "D"
    elif coverage_pct < 80 or shot_measured < shot_expected:
        grade = "C" if grade in ("A", "B") else grade

    # A high average must not conceal a failed mandatory dimension. For
    # example 7/10 scene + 10/10 physics + 10/10 identity + 5/10 action is
    # not an A export: the requested action is visibly absent.
    blocking_dimension = False
    weak_shots = []
    for q in shot_quality or []:
        avg = shot_avg(q)
        measured_dimensions = {
            key: float(q.get(key))
            for key in ("score", "physics_score", "identity_score", "action_score")
            if numeric(q.get(key))
        }
        failed_dimensions = [
            key for key, value in measured_dimensions.items() if value < 6
        ]
        if failed_dimensions:
            blocking_dimension = True
        if avg < 6 or failed_dimensions:
            weak_shots.append({
                "shot_id": q.get("shot_id"),
                "avg_score": round(avg, 1),
                "failed_dimensions": failed_dimensions,
            })
    if blocking_dimension and grade in ("A", "B"):
        grade = "C"

    return {
        "grade": grade,
        "overall_pct": round(overall, 1),
        "breakdown": {
            "shot_pct": round(shot_pct, 1),
            "char_pct": round(char_pct, 1) if char_pct is not None else None,
            "audio_pct": round(audio_pct, 1) if audio_pct is not None else None,
            "temporal_pct": round(temporal_pct, 1) if temporal_pct is not None else None,
            "integrity_pct": round(integ_pct, 1),
        },
        "coverage": {
            "overall_pct": round(coverage_pct, 1),
            "measured": measured,
            "expected": expected,
            "shot": {"measured": shot_measured, "expected": shot_expected},
            "character": {"measured": char_measured, "expected": char_expected},
            "audio": {"measured": audio_measured, "expected": audio_expected},
            "temporal": {"measured": temporal_measured, "expected": temporal_expected},
        },
        "weak_shots": weak_shots,
        "exportable": grade in ("A", "B") and coverage_pct >= 80 and not blocking_dimension,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--storyboard", help="Path to storyboard JSON file")
    parser.add_argument("--output", help="Output MP4 path")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        # Verify all sub-services are reachable
        info = {
            "voice_clone": (Path(__file__).resolve().parent / "voice_clone.py").exists(),
            "voice_extract": (Path(__file__).resolve().parent / "voice_extract.py").exists(),
            "video_generate": (SERVICES_DIR / "video_generate.py").exists(),
            "talking_head": (SERVICES_DIR / "talking_head.py").exists(),
            "ffmpeg": _ffmpeg_bin(),
        }
        info["ok"] = all([info["voice_clone"], info["voice_extract"], info["video_generate"]])
        print(json.dumps(info), flush=True)
        sys.exit(0 if info["ok"] else 1)

    if not args.storyboard or not args.output:
        print(json.dumps({"ok": False, "error": "--storyboard and --output required"}), flush=True)
        sys.exit(1)

    try:
        storyboard = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"storyboard parse error: {exc}"}), flush=True)
        sys.exit(1)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result = run_pipeline(storyboard, args.output)
    print(json.dumps(result), flush=True)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
