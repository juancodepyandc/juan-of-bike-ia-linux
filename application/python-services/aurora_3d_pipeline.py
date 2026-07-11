#!/usr/bin/env python
"""Aurora 3D end-to-end orchestrator — one command turns a prompt into a
Meshy-grade GLB with full audit trail.

Chain:
   1. Optional pre-route: classify the prompt (subject_kind_extractor) so
      we know whether to use multi-view by default (organic / character /
      creature → multi-view yes; product / generic → single-view to save
      compute).
   2. FLUX synth (single or multi-view) → reference PNG(s).
   3. Hunyuan3D run on the front view (+ multi-view aux if available).
   4. auto_rescue chain (extract kind → score → bake / reshape if needed).
   5. Return audit JSON: every stage's path + score + delta.

Idempotent — re-runs with the same run_id reuse existing intermediate
files unless --force is passed.

Usage:
   python aurora_3d_pipeline.py --prompt "..." --run-id X [--multi-view]
   python aurora_3d_pipeline.py --prompt "..." --run-id X --auto-multiview
                       (decides multi-view based on extracted kind)
   python aurora_3d_pipeline.py --prompt "..." --run-id X --force --pretty

Schema: aurora.pipeline.v1.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "application" / "output" / "3d"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from subject_kind_extractor import extract_kind  # noqa: E402
from flux_reference_synth import audit_multiview_consistency, synth, synth_multiview  # noqa: E402
from auto_rescue_mesh import auto_rescue  # noqa: E402
try:
    # Faithful-scene composer: forces every requested facet (identity, decor,
    # mechanical, fluids, luminous, motion) of a COMPOUND prompt into an explicit
    # MUST-render contract so the CLI/tunnel path matches the UI's fidelity
    # instead of letting FLUX collapse the scene to its dominant noun.
    from faithful_scene_prompt import compose_faithful_prompt, refine_subject_kind  # noqa: E402
except ImportError:  # composer is a soft dependency — pipeline still runs without it
    compose_faithful_prompt = None  # type: ignore[assignment]
    refine_subject_kind = None  # type: ignore[assignment]
try:
    from optimize_textured_mesh import optimize as _optimize_textured_mesh  # noqa: E402
except ImportError:  # optional viewer-optimisation step
    _optimize_textured_mesh = None  # type: ignore[assignment]
try:
    from tracker_helper import record_dispatch as _record_tracker_dispatch  # noqa: E402
except ImportError:  # tracker_helper is a soft dependency
    _record_tracker_dispatch = None  # type: ignore[assignment]

# Router (Python mirror of routePipeline() in threeDIntent.ts).
# Lives under application/scripts/route_test.py; add it to sys.path so we
# can call it programmatically before committing to FLUX -> Hunyuan3D.
_SCRIPTS_DIR = REPO_ROOT / "application" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
try:
    from route_test import route_pipeline  # noqa: E402
except ImportError:  # router missing — the orchestrator still works (falls through to FLUX)
    route_pipeline = None  # type: ignore[assignment]

# Kinds where multi-view materially helps (silhouette / aspect axis is the
# usual failure for these). For abstract-shape kinds (sphere, generic) the
# extra cost rarely pays off.
MULTIVIEW_RECOMMENDED_KINDS = {
    "character", "humanoid", "quadruped", "creature", "vehicle", "pc_tower",
    "case", "computer",
    # iter24.fix: motherboards / electrical_system need multi-view because
    # silhouette + component layout (M.2 slots, OLED screen, IO ports) is the
    # whole point of recognisability. Single front view loses ~40% of the
    # identity for users who know the brand.
    "motherboard", "electrical_system", "pcb",
}


# iter24.fix: Brand visual fidelity table. When the prompt names a
# product whose identity is anchored on specific visual cues (PCB color,
# branded heatsinks, OLED placement, AURA RGB zones), we APPEND those
# cues to the FLUX prompt so the diffusion model has a stronger signal
# to lock onto. The user's verbatim prompt stays at the front; the cue
# block is appended after a comma so it reads naturally.
#
# Trigger: regex on the user prompt (case-insensitive). One match wins.
# Multiple brand-keys are OK — they just all append.
BRAND_VISUAL_CUES = (
    # ASUS ROG X870E Hero — white PCB Hero series with LiveDash OLED
    (
        re.compile(r"\b(x870e\s*hero|rog\s+x870e|asus\s+x870e\s*hero)\b", re.I),
        ", ASUS ROG Strix X870E Hero motherboard, white PCB with silver heatsinks, "
        "OLED LiveDash 2-inch screen on left IO heatsink showing CPU temp, RGB AURA "
        "Sync zones, AM5 socket with ILM, 4 DDR5 DIMM slots, 5 M.2 NVMe heatsinks, "
        "24-pin ATX connector, 12VHPWR PCIe connector, massive VRM heatsink with "
        "chrome accents, USB4 type-C IO shield, WiFi 7 antennas, gaming aesthetic, "
        "professional product photography, isolated white background, top-down "
        "orthographic view, ultra-detailed components, 8K resolution, sharp focus",
    ),
    # ASUS ROG generic motherboard
    (
        re.compile(r"\b(asus\s+rog|rog\s+strix|rog\s+crosshair|rog\s+maximus)\b", re.I),
        ", ASUS ROG motherboard, ROG aesthetic, RGB AURA Sync, branded heatsinks, "
        "AM5 or LGA1700 socket, multiple M.2 slots, professional product photography, "
        "isolated white background, top-down orthographic view, ultra-detailed",
    ),
    # Generic motherboard fallback — without specific brand
    (
        re.compile(r"\b(motherboard|carte\s+m[èe]re|mainboard)\b", re.I),
        ", PCB motherboard, recognisable layout with CPU socket, DIMM slots, "
        "M.2 slots, IO ports, VRM heatsinks, professional product photography, "
        "isolated white background, top-down orthographic view, ultra-detailed",
    ),
    # Lian Li Strimer V2 — the canonical RGB cable
    (
        re.compile(r"\b(strimer\s*plus|lian\s*li\s*strimer|strimer\s*v2)\b", re.I),
        ", Lian Li Strimer Plus V2 RGB PSU cable, addressable LEDs along sleeve, "
        "professional product photography, isolated black background, photorealistic",
    ),
)


def enhance_flux_prompt(prompt: str, *, motion_prompt: str | None = None,
                        subject_kind: str | None = None) -> str:
    """Build the faithful FLUX prompt for the CLI/tunnel/extension path.

    Two layers, both keep the user's verbatim intent at the front:
      1. Brand-specific visual cues (X870E Hero, ROG, Strimer, ...) — append a
         stronger signal for recognisable products.
      2. Faithful-scene MULTI-ELEMENT FIDELITY CONTRACT — for COMPOUND requests
         (celebrity + decor + mechanical + fluids + luminous + motion, etc.) we
         append one explicit MUST-render line per detected facet so FLUX cannot
         silently drop the secondary elements. This is what brings the CLI path
         up to the React UI's fidelity (buildFluxVisualDescription); without it
         the tunnel/extension path honored compound requests only approximately.
    """
    out = prompt.strip()
    appended = []
    for pattern, cues in BRAND_VISUAL_CUES:
        if pattern.search(out):
            appended.append(cues.lstrip(", "))
    if appended:
        # Avoid duplicate appending if the cues already appear in the prompt.
        # Cheap check: if "isolated white background" is already there, skip.
        joined = ", ".join(appended)
        if joined.split(",")[0].strip().lower() not in out.lower():
            out = out.rstrip(",.") + ", " + joined

    _kind_l = (subject_kind or "").lower()
    _creature_re = re.compile(
        r"\b(personnage|character|creature|animal|renard|fox|dragon|chat|cat|chien|dog|loup|wolf|"
        r"oiseau|bird|robot|humanoid|hero|heros|guerrier|knight|chevalier|monstre|monster|"
        r"homme|femme|man|woman|personne|person|humain|human|garcon|fille|enfant|child|"
        r"boy|girl|adulte|soldat|soldier)\b", re.I)
    _animal_re = re.compile(
        r"\b(animal|renard|fox|dragon|chat|cat|chien|dog|loup|wolf|oiseau|bird|creature|"
        r"monstre|monster|lion|tigre|tiger|ours|bear|cheval|horse|lapin|rabbit)\b", re.I)
    if _kind_l in {"character", "creature", "humanoid", "quadruped"} or _creature_re.search(out):
        _base_cues = ("full body entirely visible, complete figure inside the frame with "
                      "generous empty margin on all sides, head and feet fully visible, "
                      "all limbs visible and separated, standing neutral pose, "
                      "three-quarter view, no limb hidden behind the body, no cropping, "
                      "feet on the ground, sharp detailed face, clear detailed eyes")
        if _kind_l in {"creature", "quadruped"} or _animal_re.search(out):
            _pose_cues = _base_cues + ", tail fully visible, highly detailed natural fur"
        else:
            _pose_cues = _base_cues + ", detailed realistic skin, detailed hands"
        if "full body entirely visible" not in out:
            out = out.rstrip(",.") + ", " + _pose_cues

    # Layer 2 — faithful-scene contract (compound prompts only; no-op otherwise).
    if compose_faithful_prompt is not None:
        try:
            composed = compose_faithful_prompt(
                out, subject_kind=subject_kind, motion_prompt=motion_prompt,
            )
            if composed.get("applied") and composed.get("prompt"):
                out = composed["prompt"]
        except Exception as exc:  # noqa: BLE001 — never break synth on composer error
            sys.stderr.write(f"[faithful-scene] composer failed: {exc}\n")
    return out


def _record_pipeline_dispatch(run_id: str, prompt: str, started_at: str, *,
                              status: str, verdict: str,
                              files_touched: list[str] | None = None,
                              metadata: dict | None = None) -> None:
    """Best-effort tracker dispatch under 3d-lead. Never raises."""
    if _record_tracker_dispatch is None:
        return
    try:
        _record_tracker_dispatch(
            "3d-lead",
            f"pipeline {run_id}: {prompt[:60]}",
            started_at=started_at,
            status=status,
            verdict=verdict,
            files_touched=files_touched or [],
            metadata=metadata,
        )
    except Exception:  # noqa: BLE001 — never break the pipeline on tracking
        pass


def _kind_to_intent_purpose(kind: str | None) -> str:
    """Map the Stage-0 subject kind to the Hunyuan worker's intent_purpose so the
    correct shape/texture quality branch fires (v90)."""
    k = (kind or "").lower()
    if k in {"character", "humanoid", "creature", "quadruped"}:
        return "character"
    if k in {"product", "gadget", "motherboard", "computer", "pc_tower", "case",
             "vehicle", "sphere"}:
        return "product"
    if k in {"mechanical_part", "assembly", "mechanism"}:
        return "mechanical_part"
    return "visual_preview"


def _free_gpu_before_hunyuan(audit: list | None = None) -> None:
    """Libere la VRAM des AUTRES process GPU avant le shape+paint Hunyuan.

    Cause racine du "mesh gris depuis l'app": FLUX reste charge dans ComfyUI (~10-12 Go)
    apres la synthese des references, et un modele Ollama (qwen3-vl) reste warm. Le paint
    PBR (~14 Go) fait alors OOM a toutes les resolutions -> shape_only -> mesh gris.
    On evince Ollama (keep_alive=0) puis ComfyUI (/free) — meme logique que le chemin video.
    Best-effort: aucun echec ne bloque la generation.
    """
    freed = []
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    # 1) Ollama: decharge tous les modeles residents
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=4) as _r:
            _ps = json.loads(_r.read().decode())
        for _m in (_ps.get("models") or []):
            _name = _m.get("name")
            if not _name:
                continue
            try:
                _req = urllib.request.Request(
                    f"{base}/api/generate",
                    data=json.dumps({"model": _name, "prompt": "",
                                     "keep_alive": 0, "stream": False}).encode(),
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(_req, timeout=15).read()
                freed.append(_name)
            except Exception:
                pass
    except Exception:
        pass
    # 2) ComfyUI: decharge FLUX/Kontext de la VRAM
    try:
        _req2 = urllib.request.Request(
            "http://127.0.0.1:8188/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(_req2, timeout=6).read()
        freed.append("comfyui/flux")
    except Exception:
        pass
    if audit is not None:
        audit.append({"stage": "vram_evict_before_paint", "ok": True, "freed": freed})
    print(f"PROGRESS:vram:VRAM liberee avant paint (evince: {', '.join(freed) or 'rien'})", flush=True)


def _ollama_reachable(timeout_s: float = 3.0) -> bool:
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout_s):
            return True
    except Exception:
        return False


def run_hunyuan3d(image_path: Path, run_id: str, output_dir: Path,
                  *, mv_front: Path | None = None,
                  mv_back: Path | None = None,
                  mv_left: Path | None = None,
                  mv_right: Path | None = None,
                  intent_purpose: str = "visual_preview",
                  motion_readiness: str = "static_only",
                  dimensional_precision: bool = False,
                  fmt: str = "glb", timeout_s: int = 14400) -> dict:
    # v83-3dloop: 4h. Le texturing Hunyuan paint via le rasteriseur CPU/numpy
    # (fallback quand custom_rasterizer/CUDA absent) est lent ; 1800s timeout
    # avant. "Le temps n'est pas important" (consigne utilisateur).
    """Subprocess hunyuan3d_run.py and wait. Returns {ok, mesh_path?, error?}."""
    import subprocess
    script = REPO_ROOT / "application" / "python-services" / "hunyuan3d_run.py"
    if not script.is_file():
        return {"ok": False, "error": f"hunyuan3d_run.py missing at {script}"}

    cmd = [
        sys.executable, str(script),
        "--image", str(image_path),
        "--output-dir", str(output_dir),
        "--run-id", run_id,
        "--format", fmt,
        # ROOT-CAUSE FIX (v90): without --intent-purpose the worker defaults to
        # 'visual_preview' and the character octree=512/steps=70 branch in
        # build_shape_strategies never fires — every face was reconstructed at
        # octree 384/448 and came out as a soft "hood". Thread the kind through.
        "--intent-purpose", intent_purpose,
        "--motion-readiness", motion_readiness,
    ]
    if dimensional_precision:
        cmd.append("--dimensional-precision")
    if mv_front: cmd += ["--mv-front", str(mv_front)]
    if mv_back:  cmd += ["--mv-back", str(mv_back)]
    if mv_left:  cmd += ["--mv-left", str(mv_left)]
    if mv_right: cmd += ["--mv-right", str(mv_right)]

    # v83-3dloop : on streame la sortie du subprocess EN TEMPS RÉEL dans
    # `<run-id>_hunyuan.log` (Popen + thread lecteur) — sinon, sur crash ou
    # timeout, on perd toute trace (subprocess.run + capture_output n'écrit le
    # log qu'APRÈS retour, donc rien en cas d'échec). C'était LE point aveugle.
    import threading
    log_path = output_dir / f"{run_id}_hunyuan.log"
    out_lines: list[str] = []
    started = time.time()
    try:
        lf = open(log_path, "w", encoding="utf-8", errors="replace")
    except Exception:
        lf = None
    if lf:
        lf.write("=== CMD ===\n" + " ".join(cmd) + "\n=== STREAM ===\n"); lf.flush()
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except Exception as e:
        if lf: lf.close()
        return {"ok": False, "error": f"Hunyuan3D failed to start: {e}"}

    def _pump():
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                out_lines.append(line)
                if lf:
                    try: lf.write(line); lf.flush()
                    except Exception: pass
        except Exception:
            pass
    _t = threading.Thread(target=_pump, daemon=True)
    _t.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try: proc.kill(); proc.wait(timeout=10)
        except Exception: pass
    _t.join(timeout=5)
    elapsed = round(time.time() - started, 1)
    if lf:
        try:
            lf.write(f"\n=== {'TIMEOUT' if timed_out else 'returncode ' + str(proc.returncode)} | elapsed {elapsed}s ===\n")
            lf.close()
        except Exception: pass
    out_txt = "".join(out_lines)

    if timed_out:
        return {"ok": False, "error": f"Hunyuan3D timed out after {timeout_s}s",
                "elapsed_s": elapsed, "hunyuan_log": str(log_path)}

    expected = output_dir / f"{run_id}_mesh.{fmt}"
    if not expected.is_file() or expected.stat().st_size < 1000:
        return {"ok": False, "error": f"mesh missing/too small at {expected}",
                "elapsed_s": elapsed, "stderr_tail": out_txt[-600:],
                "hunyuan_log": str(log_path)}
    # Extrait la stratégie de texture du stdout pour l'audit.
    tex_strategy = None
    for line in out_txt.splitlines():
        if "texture_strategy" in line or "paint_attempt" in line or "shape_only" in line or "texture_warn" in line:
            tex_strategy = line.strip()[-200:]
    return {"ok": True, "mesh_path": str(expected), "elapsed_s": elapsed,
            "size_bytes": expected.stat().st_size,
            "texture_strategy": tex_strategy, "hunyuan_log": str(log_path)}


def run_motion_bake(rescued_mesh: Path, motion_prompt: str, run_id: str,
                    output_dir: Path, subject_kind: str = "") -> dict:
    """Optional last stage: parse motion_prompt, run rigify_autorig with the
    parsed JSON to get an animated GLB. Falls back to None if motion parser
    can't extract anything (returns null)."""
    import subprocess
    parser = REPO_ROOT / "application" / "python-services" / "motion_parser.py"
    rigify = REPO_ROOT / "application" / "python-services" / "rigify_autorig.py"
    if not parser.is_file() or not rigify.is_file():
        return {"ok": False, "error": "motion_parser.py or rigify_autorig.py missing"}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    motion_json_path = output_dir / f"{run_id}_motion.json"
    rigged_path = output_dir / f"{run_id}_RIGGED.glb"

    proc = subprocess.run(
        [sys.executable, str(parser), "--prompt", motion_prompt],
        capture_output=True, timeout=15, check=False,
    )
    parsed = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if not parsed or parsed == "null":
        classifier = REPO_ROOT / "application" / "python-services" / "motion_intent_classifier.py"
        baker = REPO_ROOT / "application" / "python-services" / "motion_intent_baker.py"
        intent = {}
        if classifier.is_file() and baker.is_file():
            try:
                cp = subprocess.run([sys.executable, str(classifier), "--prompt", motion_prompt],
                                    capture_output=True, text=True, timeout=180, check=False)
                if cp.returncode == 0:
                    intent = json.loads(cp.stdout)
            except Exception:  # noqa: BLE001
                intent = {}
        category = (intent or {}).get("category", "rigid_static")
        confidence = float((intent or {}).get("confidence") or 0.0)
        import shutil as _sh
        _mp_low = (motion_prompt or "").lower()
        _wants_water = any(k in _mp_low for k in ("eau", "coule", "cascade", "water"))
        _wants_gas = (any(k in _mp_low for k in ("vapeur", "fumee", "brume", "steam", "smoke", "fog"))
                      or category == "gas_volume")
        water_info = None
        gas_input = Path(rescued_mesh)
        if category == "fluid_flow" or (_wants_water and category in ("gas_volume", "rigid_static", "", None)):
            try:
                sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
                from sculpted_water_animator import animate_sculpted_water
                from motion_spec import build_motion_spec
                _eau_path = output_dir / f"{run_id}_EAU.glb"
                _spec = build_motion_spec(prompt if "prompt" in dir() else "", motion_prompt)
                print(f"PROGRESS:animation:spec du mouvement ({_spec['element_mobile']}): "
                      f"{_spec['type_mouvement']} {_spec['direction']}, vitesse {_spec['vitesse']}, "
                      f"amplitude {_spec['amplitude']}, couleur {_spec['couleur_cible']}", flush=True)
                print(f"PROGRESS:animation:critere de verification: {_spec['description_attendue'][:160]}", flush=True)
                audit.append({"stage": "motion_spec", **_spec})
                _rubrique = _spec["description_attendue"]
                if float(_spec.get("amplitude", 1.0)) <= 0.01:
                    print("PROGRESS:animation:matiere figee demandee — aucune animation de fluide", flush=True)
                    water_info = "fige (spec)"
                else:
                  _amp = float(_spec["amplitude"])
                  for _essai in range(2):
                    sw = animate_sculpted_water(rescued_mesh, _eau_path, amp_scale=_amp,
                                                couleur_cible=str(_spec["couleur_cible"]),
                                                vitesse=float(_spec["vitesse"]))
                    if not sw.get("ok"):
                        break
                    water_info = sw.get("info")
                    gas_input = _eau_path
                    if os.environ.get("AURORA_ANIM_JUDGE", "1") != "1":
                        break
                    try:
                        from anim_frames_probe import probe_frames
                        from vlm_judge import ask_vlm
                        _sonde_dir = output_dir / f"{run_id}_sonde_eau"
                        _pr = probe_frames(_eau_path, _sonde_dir)
                        if not _pr.get("ok"):
                            break
                        print(f"PROGRESS:animation:juge IA — comparaison de {len(_pr['frames'])} frames a la description de reference (essai {_essai + 1})", flush=True)
                        _verdict = ask_vlm(_pr["frames"][:3],
                                           "Voici 3 images successives d'une animation de fontaine. "
                                           "Description de reference attendue: " + _rubrique +
                                           " Ces images sont-elles CONFORMES (mouvement d'eau credible, "
                                           "pierre immobile, pas d'artefact) ?",
                                           schema_hint='{"conforme": true|false, "defauts": ["..."], '
                                                       '"eau_trop_discrete": true|false}',
                                           timeout=180)
                        _def = ", ".join((_verdict.get("defauts") or [])[:3])
                        print(f"PROGRESS:animation:verdict juge: {'CONFORME' if _verdict.get('conforme') else 'NON conforme'} {(_def and '(' + _def[:120] + ')') or ''}", flush=True)
                        audit.append({"stage": "eau_juge", "essai": _essai + 1,
                                      "conforme": bool(_verdict.get("conforme")),
                                      "defauts": _verdict.get("defauts")})
                        if _verdict.get("conforme"):
                            break
                        if _verdict.get("eau_trop_discrete") and _essai == 0:
                            _amp = _amp * 1.7
                            print("PROGRESS:animation:mouvement trop discret — nouvelle passe amplifiee", flush=True)
                            continue
                        break
                    except Exception as _je:  # noqa: BLE001
                        audit.append({"stage": "eau_juge", "ok": False, "error": repr(_je)})
                        break
            except Exception:  # noqa: BLE001
                pass
        _spec_out = _spec if "_spec" in dir() else None
        if water_info and not _wants_gas:
            _sh.move(str(gas_input), str(rigged_path))
            return {"ok": True, "rigged_mesh": str(rigged_path),
                    "motion_intent": "fluid_flow_sculpte",
                    "water_info": water_info,
                    "motion_spec": _spec_out,
                    "size_bytes": rigged_path.stat().st_size}
        if _wants_gas:
            category = "gas_volume"
            intent = {**(intent or {}), "category": "gas_volume"}
        if category not in ("rigid_static", "", None):
            intent_path = output_dir / f"{run_id}_intent.json"
            intent_path.write_text(json.dumps(intent), encoding="utf-8")
            try:
                bp = subprocess.run([sys.executable, str(baker),
                                     "--intent", str(intent_path),
                                     "--input", str(gas_input),
                                     "--output", str(rigged_path)],
                                    capture_output=True, text=True, timeout=1800, check=False)
                bres = json.loads(bp.stdout) if (bp.stdout or "").strip().startswith("{") else {}
            except Exception as exc:  # noqa: BLE001
                bres = {"ok": False, "error": repr(exc)}
            if bres.get("ok") and rigged_path.is_file() and rigged_path.stat().st_size > 1000:
                return {"ok": True, "rigged_mesh": str(rigged_path),
                        "motion_intent": category if not water_info else category + "+eau_sculptee",
                        "intent_confidence": confidence,
                        "water_info": water_info,
                        "motion_spec": _spec_out,
                        "size_bytes": rigged_path.stat().st_size}
            if water_info:
                _sh.move(str(gas_input), str(rigged_path))
                return {"ok": True, "rigged_mesh": str(rigged_path),
                        "motion_intent": "fluid_flow_sculpte",
                        "water_info": water_info,
                        "note": f"gaz echoue ({(bres.get('error') or 'sans sortie')[:120]}), eau conservee",
                        "size_bytes": rigged_path.stat().st_size}
            return {"ok": False,
                    "error": f"intent bake failed ({category}): {bres.get('error') or bres.get('raw') or 'sans sortie'}",
                    "motion_intent": category, "motion_prompt": motion_prompt}
        return {"ok": False, "error": "motion_parser returned null (no verb match)",
                "motion_intent": category, "motion_prompt": motion_prompt}
    motion_json_path.write_text(parsed, encoding="utf-8")

    metarig_family = "quadruped" if (subject_kind or "").lower() in ("quadruped", "creature") else "human"
    proc = subprocess.run(
        [sys.executable, str(rigify),
         "--input", str(rescued_mesh),
         "--output", str(rigged_path),
         "--motion", str(motion_json_path),
         "--metarig", metarig_family],
        capture_output=True, timeout=900, check=False,
    )
    rigify_stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    rigify_stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0 or not rigged_path.is_file():
        err = rigify_stderr[-300:] or rigify_stdout[-300:]
        return {"ok": False, "error": f"rigify_autorig failed: {err}"}
    try:
        from pygltflib import GLTF2  # noqa: WPS433

        gltf = GLTF2().load(str(rigged_path))
        if not gltf.animations:
            return {
                "ok": False,
                "error": "rigify_autorig exported no glTF animations",
                "motion_json_path": str(motion_json_path),
                "rigged_mesh": str(rigged_path),
                "stdout_tail": rigify_stdout[-600:],
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"rigify_autorig animation validation failed: {type(exc).__name__}: {exc}",
            "motion_json_path": str(motion_json_path),
            "rigged_mesh": str(rigged_path),
            "stdout_tail": rigify_stdout[-600:],
        }

    return {
        "ok": True,
        "motion_json_path": str(motion_json_path),
        "rigged_mesh": str(rigged_path),
        "size_bytes": rigged_path.stat().st_size,
        "stdout_tail": rigify_stdout[-600:],
    }


def run_final_acceptance(mesh_path: str | Path, prompt: str, kind: str,
                         motion_prompt: str | None = None) -> dict:
    """Final deterministic gate: texture/silhouette/motion acceptance."""
    try:
        from mesh_acceptance_gate import evaluate_acceptance  # noqa: WPS433
        return evaluate_acceptance(mesh_path, prompt, kind, motion_prompt)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "schema": "aurora.mesh_acceptance.v1",
            "acceptance_ok": False,
            "error": f"acceptance gate failed: {type(exc).__name__}: {exc}",
            "hard_failures": [f"acceptance gate failed: {type(exc).__name__}"],
        }


def _run_vlm_critic(mesh_path: str | Path, prompt: str, run_id: str,
                    output_dir: Path) -> dict:
    try:
        from scene_intelligence import render_views  # noqa: WPS433
        from vlm_judge import ask_vlm  # noqa: WPS433
        views_dir = output_dir / f"vlm_critic_{run_id}"
        views_dir.mkdir(parents=True, exist_ok=True)
        images = render_views(str(mesh_path), str(views_dir))
        question = (
            f'Voici 4 vues d\'un modele 3D genere pour le prompt: "{prompt}". '
            "Ce modele 3D correspond-il au prompt? Tous les membres et parties attendus "
            "sont-ils presents et entiers, rien de coupe ni manquant? Les yeux et le "
            "visage sont-ils presents et nets si c'est un personnage ou un animal? "
            "suggestion_reference = complement de description a ajouter au prompt de "
            "l'image de reference pour corriger les manques (vide si tout est ok)."
        )
        schema = '{"ok": true, "missing": [], "defauts": [], "suggestion_reference": ""}'
        verdict = ask_vlm(images, question, schema)
        return {
            "ran": True,
            "ok": bool(verdict.get("ok", False)),
            "missing": [str(m) for m in (verdict.get("missing") or [])],
            "defauts": [str(d) for d in (verdict.get("defauts") or [])],
            "suggestion_reference": str(verdict.get("suggestion_reference") or ""),
            "views": [str(i) for i in images],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "ok": True, "error": repr(exc)}


def _acceptance_failure_summary(report: dict) -> list:
    failures = report.get("hard_failures") or []
    if failures:
        return failures
    error = report.get("error")
    if error:
        return [error]
    return ["final acceptance failed"]


HISTORICAL_PERSON_FALLBACK_RE = re.compile(
    r"\b(abraham\s+lincoln|lincoln)\b",
    re.IGNORECASE,
)


def _should_try_historical_person_fallback(prompt: str, kind: str,
                                           acceptance: dict) -> bool:
    """Use a volumetric known-person scaffold after AI human reconstruction fails.

    This is deliberately narrow: it fixes the single-reference named-historical
    figure failure mode (flat/billboard human GLB) without replacing arbitrary
    character prompts with a generic mannequin.
    """
    if acceptance.get("acceptance_ok", False):
        return False
    if (kind or "").lower() not in {"character", "humanoid"}:
        return False
    if not HISTORICAL_PERSON_FALLBACK_RE.search(prompt or ""):
        return False
    failures = " ".join(map(str, _acceptance_failure_summary(acceptance))).lower()
    if not failures:
        return True
    failure_tokens = (
        "low-detail", "fidelity", "pasted", "flat", "billboard",
        "texture", "motion", "engineer_grade", "acceptance failed",
    )
    return any(token in failures for token in failure_tokens)


def _run_historical_person_fallback(prompt: str, kind: str,
                                    motion_prompt: str | None,
                                    run_id: str, output_dir: Path,
                                    audit: list[dict],
                                    rejected_mesh: str | Path,
                                    rejected_acceptance: dict) -> dict:
    """Generate and gate a detailed volumetric historical-person GLB."""
    template = "historical_person_performer"
    fallback_run_id = f"{run_id}_historical_volume"
    proc_res = run_procedural_dispatch(
        template, prompt, fallback_run_id, output_dir, timeout_s=600,
    )
    audit.append({
        "stage": "volumetric_historical_fallback",
        "reason": "ai human mesh failed final acceptance; replacing final delivery with audited volumetric model",
        "from_rejected_mesh": str(rejected_mesh),
        "rejected_engineer_grade": rejected_acceptance.get("engineer_grade"),
        "rejected_failures": _acceptance_failure_summary(rejected_acceptance),
        **proc_res,
    })
    if not proc_res.get("ok"):
        return {
            "ok": False,
            "template": template,
            "error": proc_res.get("error") or "historical fallback generation failed",
            "dispatch": proc_res,
        }

    fallback_acceptance = run_final_acceptance(
        proc_res["glb_path"], prompt, kind, motion_prompt,
    )
    audit.append({
        "stage": "volumetric_historical_fallback_acceptance",
        "ok": fallback_acceptance.get("ok", False),
        "acceptance_ok": fallback_acceptance.get("acceptance_ok", False),
        "engineer_grade": fallback_acceptance.get("engineer_grade"),
        "threshold": fallback_acceptance.get("threshold"),
        "hard_failures": fallback_acceptance.get("hard_failures") or [],
        "suggested_fixes": fallback_acceptance.get("suggested_fixes") or [],
    })
    return {
        "ok": bool(fallback_acceptance.get("acceptance_ok", False)),
        "template": template,
        "glb_path": proc_res["glb_path"],
        "size_bytes": proc_res.get("size_bytes"),
        "params": proc_res.get("params"),
        "dispatch": proc_res,
        "acceptance": fallback_acceptance,
        "error": None if fallback_acceptance.get("acceptance_ok", False)
        else "historical fallback final acceptance rejected: "
        + "; ".join(map(str, _acceptance_failure_summary(fallback_acceptance)[:3])),
    }


def extract_template_params(prompt: str, template: str, run_id: str = "proc") -> dict:
    """Heuristic prompt-to-Blender-template params extractor.

    Pure-Python (no LLM, no TS counterpart needed — the procedural dispatch
    is internal to the orchestrator). The TS routePipeline() side only
    decides *which* template; we translate prompt phrasing into the
    template's specific param schema here.

    Defaults are tuned per template so a bare prompt still produces a
    sensible mesh (Strimer V2 -> 24-pin ATX; ratio absent -> 1:1).
    """
    p = (prompt or "").lower()

    if template == "historical_person_performer":
        person_name = "Abraham Lincoln"
        m = re.search(r"\b([A-Z][a-zA-Z'_-]{2,}\s+[A-Z][a-zA-Z'_-]{2,})\b", prompt or "")
        if m and "lincoln" not in m.group(1).lower():
            person_name = m.group(1)
        params = {
            "person_name": person_name,
            "skin": "#a37456",
            "hair": "#17110f",
            "jacket": "#08080a",
            "waistcoat": "#151515",
            "shirt": "#eee9dd",
            "shoes": "#050505",
        }
        face_scan = Path(__file__).with_name("reference_profiles") / "lincoln_mills_life_mask_head_high.glb"
        if face_scan.is_file():
            params["face_scan_glb_path"] = str(face_scan)
            params["face_scan_source"] = "Smithsonian CC0 Lincoln life mask GLB"
            params["face_scan_url"] = "https://3d.si.edu/object/3d/abraham-lincoln:c02c239d-5ebf-4a7a-a368-e2288bbf4b31"
        else:
            life_mask = Path(__file__).with_name("reference_profiles") / "lincoln_life_mask_smithsonian_cc0.stl"
            if life_mask.is_file():
                params["life_mask_stl_path"] = str(life_mask)
                params["life_mask_source"] = "Smithsonian/Wikimedia CC0 Lincoln life mask"
        profiles = Path(__file__).with_name("reference_profiles")
        right_hand = profiles / "lincoln_volk_right_hand_high.glb"
        left_hand = profiles / "lincoln_volk_left_hand_high.glb"
        if right_hand.is_file() and left_hand.is_file():
            params["right_hand_scan_glb_path"] = str(right_hand)
            params["left_hand_scan_glb_path"] = str(left_hand)
            params["hand_scan_source"] = "Smithsonian CC0 Lincoln Volk hand casts GLB"
            params["hand_scan_url"] = "https://3d.si.edu/object/3d/abraham-lincoln:d8c642d6-4ebc-11ea-b77f-2e728ce88125"
        return params

    if template == "strimer_plus_v2_cable":
        variant = "24pin"
        light_guides = 12
        led_count = 120
        channel_count = 6
        length = 0.267
        width = 0.0566
        cable_length = 0.220
        if "12vhpwr" in p or "12+4" in p or "16-pin" in p or "16 pin" in p:
            variant = "12vhpwr_12guide" if "12" in p and "8" not in p else "12vhpwr_8guide"
            light_guides = 12 if variant == "12vhpwr_12guide" else 8
            led_count = 162 if light_guides == 12 else 108
            channel_count = 6 if light_guides == 12 else 4
            length = 0.381
            width = 0.0564 if light_guides == 12 else 0.0398
            cable_length = 0.320
        elif "3x8" in p or "3×8" in p or "triple" in p:
            variant = "triple_8pin"
            light_guides = 12
            led_count = 162
            channel_count = 6
            length = 0.345
            width = 0.0563
            cable_length = 0.300
        elif "8-pin" in p or "8 pin" in p or "pcie" in p:
            variant = "dual_8pin"
            light_guides = 8
            led_count = 108
            channel_count = 4
            length = 0.345
            width = 0.0435
            cable_length = 0.300
        if re.search(r"\brainbow\b|arc[\s\-]?en[\s\-]?ciel", p):
            pattern = "rainbow"
        elif re.search(r"\bchase\b|\bchenil(?:lard)?\b", p):
            pattern = "chase"
        elif re.search(r"\bbreath(?:ing)?\b|\brespiration\b", p):
            pattern = "breathing"
        elif re.search(r"\bpulse?\b", p):
            pattern = "pulse"
        else:
            pattern = "rainbow"
        return {
            "variant": variant,
            "length": length,
            "width": width,
            "thickness": 0.008,
            "cable_length": cable_length,
            "light_guides": light_guides,
            "led_count": led_count,
            "channel_count": channel_count,
            "pattern": pattern,
            "led_speed_hz": 1.65,
            "led_emission_strength": 2.4,
        }

    if template == "cable_bundle_system":
        # Pin/strand count — explicit "Npin" wins, then known PSU connectors.
        # iter17.A/B: bundle_radius bumped 0.005→0.012 already (visual spread of
        # 24 strands so each wire is distinct, not a uniform white blob);
        # led_emission_strength dropped 3.5→1.0 because the runtime reader uses
        # setHSL(hue,1,0.5) which already saturates the colors — pushing
        # emissiveIntensity above 1.0 just blooms everything to white.
        strand_count = 24  # default to ATX24 (Lian Li Strimer V2 baseline)
        m = re.search(r"(\d+)[\s\-]?pin", p)
        if m:
            strand_count = max(2, min(int(m.group(1)), 64))
        elif "atx24" in p or "atx 24" in p:
            strand_count = 24
        elif "12vhpwr" in p or ("pcie" in p and ("16" in p or "12vhpwr" in p)):
            strand_count = 16
        elif "8-pin" in p or "8 pin" in p or " eps" in p or "eps12" in p:
            strand_count = 8
        elif "6-pin" in p or "6 pin" in p:
            strand_count = 6
        elif "sata" in p:
            strand_count = 4
        # Color palette — rainbow if RGB/argb/rainbow keyword present.
        colors: list[str] | None = None
        if re.search(r"\b(rainbow|arc[\s\-]?en[\s\-]?ciel|rgb|argb)\b", p):
            colors = ["#FF0000", "#FF8000", "#FFFF00", "#00FF00",
                      "#00FFFF", "#0000FF", "#8000FF"]
        led_lights = bool(re.search(r"\b(rgb|led|argb|chase|chenil|chenillard)\b", p))
        # iter15.C: animation pattern derived from prompt. "rainbow" wins over
        # "chase" (rainbow already implies a chase-style sweep through the
        # palette in the runtime reader). Default to "chase" when LEDs are on
        # but no specific pattern was requested.
        if re.search(r"\brainbow\b|arc[\s\-]?en[\s\-]?ciel", p):
            led_pattern = "rainbow"
        elif re.search(r"\bchase\b|\bchenil(?:lard)?\b", p):
            led_pattern = "chase"
        elif re.search(r"\bbreath(?:ing)?\b|\brespiration\b", p):
            led_pattern = "breathing"
        elif re.search(r"\bpulse?\b", p):
            led_pattern = "pulse"
        else:
            led_pattern = "chase" if led_lights else "static_color"
        params = {
            "strand_count": strand_count,
            # iter17.B: bundle_radius 0.005→0.012 (5mm→12mm) so 24 strands
            # spread enough that each individual wire is visible. Below 8mm the
            # bundle blends into a single white sleeve at viewport distance.
            "bundle_radius": 0.012,
            # iter17.B: strand_radius stays 0.5mm to keep wire/bundle ratio
            # proportional (bundle 24× wire diameter) — thicker wires would
            # touch and reblend into a uniform tube.
            "strand_radius": 0.0005,
            "length": 0.5,
            "sag": 0.03,
            "emissive": led_lights,
            "led_lights": 4 if led_lights else 2,
            "led_pattern": led_pattern,
            "led_speed_hz": 2.0,
            # iter17.A/E: 3.5→2.0. iter17.A first dropped to 1.0 but with the
            # viewer's hemi/directional fills at 2.75 total, the white BSDF
            # base color won (cable read as a single white sleeve). iter17.E
            # cut the fills to 0.58 total, so 2.0 gives strong saturated hues
            # without ACES bloom-to-white. Sweet spot validated visually at T=0.4
            # — 4-6 distinct hues simultaneously.
            "led_emission_strength": 2.0,
        }
        if colors:
            params["colors"] = colors
        return params

    if template == "led_strip_system":
        led_count = 60
        m = re.search(r"(\d+)\s*(?:leds?|pixels?)\b", p)
        if m:
            led_count = max(4, min(int(m.group(1)), 600))
        length = 0.5
        m = re.search(r"(\d+(?:\.\d+)?)\s*(m|cm|mm)\b", p)
        if m:
            v = float(m.group(1))
            unit = m.group(2)
            length = v if unit == "m" else (v / 100 if unit == "cm" else v / 1000)
        # iter15.C: forward the LED pattern + speed via params; the template
        # tags every material with aurora.led-emission.v1 extras so the
        # runtime reader animates emissive at draw-time (FCurves on shader
        # nodes don't survive glTF export).
        if re.search(r"\brainbow\b|arc[\s\-]?en[\s\-]?ciel", p):
            pattern = "rainbow"
        elif re.search(r"\bchase\b|\bchenil(?:lard)?\b", p):
            pattern = "chase"
        elif re.search(r"\bbreath(?:ing)?\b|\brespiration\b", p):
            pattern = "breathing"
        elif re.search(r"\bpulse?\b", p):
            pattern = "pulse"
        else:
            pattern = "rainbow"
        return {
            "led_count": led_count,
            "length": length,
            "pattern": pattern,
            "led_speed_hz": 2.0,
            # iter17.A/E: 4.0→2.2. Same rationale as cable_bundle_system —
            # iter17.E cut viewer fills to 0.58 total, so 2.2 gives the LED
            # domes saturated hues without ACES bloom. Still slightly higher
            # than cable's 2.0 because LED domes (uv_sphere @ 4mm) have less
            # surface area than 24 strands × 50cm.
            "led_emission_strength": 2.2,
        }

    if template == "humanoid_performer":
        dance = "macarena" if re.search(r"\bmacarena\b", p) else "dance"
        return {
            "dance": dance,
            "style": "original_colored_performer",
            "skin": "#7f4d36",
            "hair": "#1b1718",
            "jacket": "#d7352a",
            "shirt": "#19c5d1",
            "pants": "#26335f",
            "shoes": "#15171c",
        }

    if template == "pulley_belt_system":
        # Ratio "2:1" -> driver=2, driven=1
        params: dict = {}
        m = re.search(r"ratio\s*(\d+(?:\.\d+)?)\s*[:x/]\s*(\d+(?:\.\d+)?)", p)
        if m:
            params["ratio"] = [float(m.group(1)), float(m.group(2))]
        return params

    if template in ("gear_train_system", "cylinder_actuator_system",
                    "hinge_joint_system", "linkage_system"):
        return {}  # template defaults are tuned for each kinematic class

    if template == "motherboard_layout":
        # iter28: HYBRID approach. Generate a photoreal top-down FLUX image of
        # the motherboard and use it as the PCB texture, while keeping the
        # OLED face as a separate plane with aurora.oled-atlas.v1 extras for
        # real animated content. Procedural primitives alone read as "Lego
        # cubes" — the FLUX texture brings the actual brand identity, the
        # separate OLED plane keeps the live screen the user explicitly asked
        # for.
        flux_image_path = None
        try:
            from flux_reference_synth import synth as _flux_synth
            flux_run_id = f"{run_id}_pcb"
            flux_ref = DEFAULT_OUTPUT_DIR / f"{flux_run_id}_reference.png"
            if not flux_ref.is_file():
                # Build a top-down PCB photo prompt using brand cues we
                # already know from BRAND_VISUAL_CUES + the user's verbatim.
                _enhanced = enhance_flux_prompt(prompt)
                _topdown_prompt = (
                    _enhanced.rstrip(".,") +
                    ", flat top-down orthographic shot, board only, no fans, "
                    "no peripherals, 4096x4096 reference photo, isolated on "
                    "pure white background, professional studio lighting, "
                    "ultra-sharp focus, no perspective distortion"
                )
                _res = _flux_synth(_topdown_prompt, flux_run_id,
                                   output_dir=DEFAULT_OUTPUT_DIR,
                                   width=1024, height=1024, steps=25)
                if _res.get("ok") and flux_ref.is_file():
                    flux_image_path = str(flux_ref)
            else:
                flux_image_path = str(flux_ref)
        except Exception as exc:
            sys.stderr.write(f"[mobo-flux-prebake] failed: {exc}\n")
        try:
            from motion_intent_baker import _generate_oled_png_sequence
            atlas_run_dir = DEFAULT_OUTPUT_DIR / f"atlas_{run_id}"
            atlas_run_dir.mkdir(parents=True, exist_ok=True)
            # iter29: prefer brand_logo by default for motherboard prompts —
            # the OLED LiveDash mostly displays the brand on boot. system_stats
            # only when the user explicitly asks "temp" / "cpu %" / "stats".
            if re.search(r"\bsystem.?stats?|cpu\s*(\%|temp)|gpu\s*temp|stat", p):
                content_type = "system_stats"
            elif re.search(r"\bicon\b", p):
                content_type = "icon_rotation"
            elif re.search(r"\bmix|altern", p):
                content_type = "mixed"
            elif re.search(r"\btext\s*scroll|scroll\s*text|defile|defil", p):
                content_type = "text_scroll"
            else:
                content_type = "brand_logo"
            screen_text = "X870E HERO"
            m = re.search(r"\b(x870e|x670e|b850|b650|z890|z790)(?:\s+(\w+))?\b", p)
            if m:
                screen_text = (m.group(1).upper()
                               + (" " + m.group(2).upper() if m.group(2) else " HERO"))
            seq = _generate_oled_png_sequence(
                {"screen_anim": {
                    "content_type": content_type,
                    "frame_rate": 18.0,
                    "resolution_px": [256, 128],
                    "text": screen_text,
                }},
                str(atlas_run_dir),
            )
            atlas_path = (seq or {}).get("atlas_path") if isinstance(seq, dict) else None
            if atlas_path and os.path.isfile(atlas_path):
                _params = {
                    "oled_atlas_path": atlas_path,
                    "oled_content_type": content_type,
                    "oled_frame_count": int((seq or {}).get("png_count", 60)),
                    "oled_frame_w": 256,
                    "oled_frame_h": 128,
                    "oled_frame_rate": 18.0,
                    "oled_text": screen_text,
                }
                if flux_image_path:
                    _params["pcb_texture_path"] = flux_image_path
                return _params
        except Exception as exc:
            sys.stderr.write(f"[oled-atlas-prebake] failed: {exc}\n")
        # If the OLED atlas pre-bake failed but FLUX succeeded, still forward
        # the PCB texture so the hybrid render has the photo backing.
        if flux_image_path:
            return {"pcb_texture_path": flux_image_path}
        return {}

    return {}


def run_procedural_dispatch(template: str, prompt: str, run_id: str,
                            output_dir: Path,
                            *, timeout_s: int = 300) -> dict:
    """Dispatch to blender_bridge.py --mode procedural with template-specific params.

    Returns {ok, glb_path?, template, params, elapsed_s, error?}.
    """
    bridge = REPO_ROOT / "application" / "python-services" / "blender_bridge.py"
    if not bridge.is_file():
        return {"ok": False, "error": f"blender_bridge.py missing at {bridge}"}
    output_dir.mkdir(parents=True, exist_ok=True)
    params = extract_template_params(prompt, template, run_id=run_id)

    cmd = [
        sys.executable, str(bridge),
        "--mode", "procedural",
        "--template", template,
        "--params", json.dumps(params),
        "--output-dir", str(output_dir),
        "--run-id", run_id,
        "--format", "glb",
    ]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"procedural dispatch timed out after {timeout_s}s",
                "template": template, "params": params}
    elapsed = round(time.time() - started, 1)

    glb_path = output_dir / f"{run_id}_procedural.glb"
    stdout_tail = (proc.stdout or b"").decode("utf-8", errors="replace")[-400:]
    stderr_tail = (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]
    if proc.returncode != 0 or not glb_path.is_file() or glb_path.stat().st_size < 1000:
        return {"ok": False,
                "error": f"procedural dispatch failed (rc={proc.returncode})",
                "template": template, "params": params,
                "elapsed_s": elapsed,
                "stdout_tail": stdout_tail, "stderr_tail": stderr_tail}
    return {"ok": True,
            "glb_path": str(glb_path),
            "template": template,
            "params": params,
            "elapsed_s": elapsed,
            "size_bytes": glb_path.stat().st_size}


def run_photogrammetry_dispatch(images: list[str], run_id: str, output_dir: Path,
                                *, timeout_s: int = 1800) -> dict:
    """Dispatch to meshroom_run.py with the provided images.

    Caller must ensure len(images) >= 3. Returns {ok, glb_path?, elapsed_s, error?}.
    """
    runner = REPO_ROOT / "application" / "python-services" / "meshroom_run.py"
    if not runner.is_file():
        return {"ok": False, "error": f"meshroom_run.py missing at {runner}"}
    if not images or len(images) < 3:
        return {"ok": False, "error": f"need >=3 images, got {len(images) if images else 0}"}
    output_dir.mkdir(parents=True, exist_ok=True)

    # meshroom_run.py expects a directory or glob; if caller passed paths
    # directly, drop them into a staging dir so the runner's find_images()
    # picks them up reliably.
    img_dir = output_dir / f"{run_id}_photogrammetry_inputs"
    img_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    for i, src in enumerate(images):
        srcp = Path(src)
        if not srcp.is_file():
            continue
        dst = img_dir / f"{i:03d}_{srcp.name}"
        if not dst.is_file():
            dst.write_bytes(srcp.read_bytes())
        staged.append(str(dst))
    if len(staged) < 3:
        return {"ok": False, "error": f"only {len(staged)} valid images after staging"}

    cmd = [
        sys.executable, str(runner),
        "--images", str(img_dir),
        "--output-dir", str(output_dir),
        "--run-id", run_id,
        "--format", "glb",
        "--quality", "normal",
    ]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"photogrammetry timed out after {timeout_s}s"}
    elapsed = round(time.time() - started, 1)

    # meshroom_run.py prints {ok, path, ...} on stdout when complete.
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    glb_candidate = output_dir / f"{run_id}_photogrammetry.glb"
    try:
        # Last JSON line wins (runner may emit progress lines too).
        last_json = next((json.loads(line) for line in reversed(out.splitlines())
                          if line.strip().startswith("{")), None)
    except (ValueError, StopIteration):
        last_json = None
    if last_json and last_json.get("ok") and last_json.get("path"):
        glb_candidate = Path(last_json["path"])

    if proc.returncode != 0 or not glb_candidate.is_file() or glb_candidate.stat().st_size < 1000:
        return {"ok": False,
                "error": f"photogrammetry dispatch failed (rc={proc.returncode})",
                "elapsed_s": elapsed,
                "stdout_tail": out[-400:],
                "stderr_tail": (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]}
    return {"ok": True,
            "glb_path": str(glb_candidate),
            "elapsed_s": elapsed,
            "size_bytes": glb_candidate.stat().st_size}


def _stage_reference_image(src: str, dest: Path) -> dict:
    """Normalize a user/web reference image into the pipeline reference slot."""
    raw = (src or "").strip()
    if not raw:
        return {"ok": False, "error": "empty reference image path"}

    dest.parent.mkdir(parents=True, exist_ok=True)
    downloaded: Path | None = None
    if raw.lower().startswith(("http://", "https://")):
        downloaded = dest.with_name(dest.stem + "_source_download")
        try:
            req = urllib.request.Request(
                raw,
                headers={"User-Agent": "AuroraIA/3D-reference-stager (+local pipeline)"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                downloaded.write_bytes(resp.read())
        except Exception as exc:  # noqa: BLE001 - report exact fetch failure
            return {"ok": False, "error": f"reference image download failed: {exc}", "source": raw}
        source_path = downloaded
    else:
        source_path = Path(raw).expanduser()
        if not source_path.is_file():
            return {"ok": False, "error": f"reference image not found: {source_path}", "source": raw}

    try:
        from PIL import Image  # noqa: WPS433

        im = Image.open(source_path).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        bg.convert("RGB").save(dest)
    except Exception:
        try:
            shutil.copyfile(source_path, dest)
        except Exception as exc:  # noqa: BLE001 - fallback failed too
            return {"ok": False, "error": f"reference image staging failed: {exc}", "source": raw}
    finally:
        if downloaded is not None:
            try:
                downloaded.unlink(missing_ok=True)
            except Exception:
                pass

    return {
        "ok": True,
        "source": raw,
        "path": str(dest),
        "size_bytes": dest.stat().st_size if dest.is_file() else 0,
    }


import re as _re_mod
# Marques/produits reels + mots-cles "reproduire l'existant" -> declenche la recherche web
# d'une VRAIE photo (fidelite) au lieu d'une invention FLUX (creativite). C'est la
# distinction fidelite/creation demandee : un sujet REEL specifique se cherche, un sujet
# generique/creatif se genere.
_REAL_BRAND_RE = _re_mod.compile(
    r"\b(asus|rog|msi|gigabyte|aorus|lian.?li|strimer|corsair|nvidia|geforce|rtx|gtx|radeon|"
    r"intel|core\s?i[3579]|amd|ryzen|threadripper|razer|logitech|samsung|sony|playstation|ps[45]|"
    r"xbox|nintendo|switch|apple|iphone|ipad|macbook|dell|hp|lenovo|thermaltake|nzxt|"
    r"cooler\s?master|be\s?quiet|noctua|seasonic|evga|zotac|palit|z790|z890|x870|b650|"
    r"4090|4080|5090|5080|3080|3090)\b", _re_mod.I)
_REAL_KW_RE = _re_mod.compile(
    r"\b(qui existe|existe reellement|reel|r[ée]el|r[ée]elle|exact|exacte|vrai\s|vraie|"
    r"real\b|specifique|sp[ée]cifique|precis au pixel|pixel[- ]?pr[eè]s|reproduire fid|reference exacte)\b",
    _re_mod.I)


def _should_research_reference(prompt: str) -> bool:
    """True si le sujet est un objet/produit REEL specifique -> chercher une vraie photo."""
    p = prompt or ""
    if _REAL_BRAND_RE.search(p) or _REAL_KW_RE.search(p):
        return True
    try:  # identite nommee reelle (via le detecteur fidelite existant)
        if compose_faithful_prompt is not None:
            a = compose_faithful_prompt(p)["analysis"]
            ident = a.get("identity") or {}
            if ident and ident.get("basis") in {"named_identity", "real_product", "brand"}:
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _clean_product_photo(img):
    try:
        from rembg import remove as _rembg_remove
        import numpy as _np
        from PIL import Image as _Image
        rgba = _rembg_remove(img.convert("RGB"))
        a = _np.asarray(rgba)[:, :, 3].astype(_np.float32) / 255.0
        mask = a > 0.5
        if mask.sum() < 500:
            return img
        try:
            from scipy import ndimage as _ndi
            lab, n = _ndi.label(mask)
            if n > 1:
                sizes = _ndi.sum(mask, lab, range(1, n + 1))
                mask = lab == (1 + int(_np.argmax(sizes)))
        except Exception:  # noqa: BLE001
            pass
        cov = float(mask.mean())
        if not (0.02 < cov < 0.92):
            return img
        rgb = _np.asarray(img.convert("RGB")).astype(_np.float32)
        nonwhite = rgb.min(axis=2) < 235
        kept = float((mask & nonwhite).sum()) / max(float(nonwhite.sum()), 1.0)
        if kept < 0.75:
            return img
        out = _np.where(mask[..., None], rgb, 255.0).astype("uint8")
        return _Image.fromarray(out)
    except Exception:  # noqa: BLE001
        return img


def _reference_photo_ok(png_path: str, prompt: str) -> tuple[bool, str, str]:
    try:
        sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
        from vlm_judge import ask_vlm
        verdict = ask_vlm([png_path],
                          "Photo candidate comme reference produit pour: '%s'. "
                          "Est-elle utilisable pour une reconstruction 3D fidele ? "
                          "Criteres stricts: le sujet est bien celui demande (le MODELE EXACT, pas une "
                          "variante/edition differente), fond neutre ou blanc, "
                          "AUCUN filigrane/watermark/texte superpose, pas d'eclairage colore artistique, "
                          "produit entier non coupe. "
                          "Indique aussi l'orientation: 'face' si la face PRINCIPALE du produit est "
                          "visible de front (celle avec les commandes/boutons/ecran/cadran), "
                          "'trois_quarts' si la face principale est visible de biais, "
                          "'dos' si on voit l'arriere, 'profil' sinon." % prompt,
                          schema_hint='{"ok": true|false, "raison": "...", '
                                      '"orientation": "face|trois_quarts|dos|profil"}',
                          timeout=90)
        if isinstance(verdict, dict) and "ok" in verdict:
            ori = str(verdict.get("orientation", "")).strip().lower()
            if ori not in ("face", "trois_quarts", "dos", "profil"):
                ori = "inconnu"
            return bool(verdict["ok"]), str(verdict.get("raison", "")), ori
    except Exception:  # noqa: BLE001
        pass
    return True, "vlm indisponible: accepte par defaut", "inconnu"


def _same_product(path_a: str, path_b: str, prompt: str) -> bool:
    try:
        from vlm_judge import ask_vlm
        verdict = ask_vlm([path_a, path_b],
                          "Ces deux photos montrent-elles EXACTEMENT le meme modele de produit "
                          "(pour: '%s') ? Reponds false si c'est une variante, une autre edition, "
                          "une autre couleur ou un produit different." % prompt,
                          schema_hint='{"meme_produit": true|false, "raison": "..."}',
                          timeout=90)
        if isinstance(verdict, dict) and "meme_produit" in verdict:
            return bool(verdict["meme_produit"])
    except Exception:  # noqa: BLE001
        pass
    return True


def _research_real_reference(prompt: str, out_path, log=lambda *a: None) -> bool:
    """Cherche sur le web une VRAIE photo du sujet et la telecharge -> out_path.
    Utilise reference_visual_search.py (DuckDuckGo/Bing). Best-effort: False si rien d'exploitable."""
    script = REPO_ROOT / "application" / "python-services" / "reference_visual_search.py"
    if not script.is_file():
        return False
    try:
        front_queries = [f"{prompt} product photo high resolution"]
        if _re_mod.search(r"\b(led|rgb|argb|lumineux|neon|strimer|lightstrip)\b", prompt, _re_mod.I):
            front_queries.insert(0, f"{prompt} product photo unlit powered off white leds")
        query_specs = [(q, 2) for q in front_queries]
        query_specs.append((f"{prompt} back rear view product photo", 1))

        def _fetch_cands(query):
            p = subprocess.run([sys.executable, str(script), "--query", query, "--limit", "8"],
                               capture_output=True, text=True, timeout=70)
            line = next((l for l in reversed((p.stdout or "").splitlines()) if l.strip().startswith("{")), "")
            return (json.loads(line).get("candidates") if line else None) or []
        import io as _io, base64 as _b64
        import tempfile as _tmpmod
        from PIL import Image as _Image
        seen_urls = set()
        base = str(out_path)
        stem = base[:-4] if base.lower().endswith(".png") else base
        for _old_v in range(2, 9):
            try:
                os.remove(f"{stem}_v{_old_v}.png")
            except OSError:
                pass
        slots = {"face": None, "dos": None, "extra": None}
        for query, _quota in query_specs:
            if slots["face"] and slots["dos"]:
                break
            log(f"PROGRESS:reference:recherche web: \"{query[:80]}\"")
            _cands = _fetch_cands(query)[:8]
            log(f"PROGRESS:reference:{len(_cands)} candidate(s) trouvee(s)")
            for c in _cands:
                if slots["face"] and slots["dos"] and slots["extra"]:
                    break
                url = c.get("imageUrl")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                try:
                    d = subprocess.run([sys.executable, str(script), "--download-url", url],
                                       capture_output=True, text=True, timeout=45)
                    dl = next((l for l in reversed((d.stdout or "").splitlines()) if l.strip().startswith("{")), "")
                    dj = json.loads(dl) if dl else {}
                    if not dj.get("ok") or not dj.get("base64"):
                        continue
                    img = _Image.open(_io.BytesIO(_b64.b64decode(dj["base64"])))
                    if img.mode != "RGB":
                        img = img.convert("RGBA")
                        _bg = _Image.new("RGB", img.size, (255, 255, 255))
                        _bg.paste(img, mask=img.split()[3])
                        img = _bg
                    if min(img.size) < 480:
                        log(f"PROGRESS:reference:photo ignoree (resolution {img.size[0]}x{img.size[1]} < 480)")
                        continue
                    cand = _tmpmod.mktemp(suffix=".png")
                    img = _clean_product_photo(img)
                    img.save(cand)
                    ok_photo, why, ori = _reference_photo_ok(cand, prompt)
                    if not ok_photo:
                        log(f"PROGRESS:reference:photo rejetee par l'IA ({why[:60]})")
                        os.remove(cand)
                        continue
                    slot = None
                    if ori in ("face", "trois_quarts") and not slots["face"]:
                        if ori == "trois_quarts" and min(img.size) < 640:
                            pass
                        else:
                            slot = "face"
                    elif ori == "dos" and not slots["dos"]:
                        slot = "dos"
                    elif not slots["extra"] and ori != "inconnu":
                        slot = "extra"
                    if slot is None:
                        os.remove(cand)
                        continue
                    slots[slot] = cand
                    log(f"PROGRESS:reference:photo {slot} VALIDEE — orientation {ori}, {img.size[0]}x{img.size[1]}, source {url.split('/')[2] if '//' in url else url[:40]}")
                except Exception:  # noqa: BLE001
                    continue
        if not slots["face"]:
            for k in ("dos", "extra"):
                if slots[k]:
                    os.remove(slots[k])
            log("PROGRESS:reference:aucune photo de FACE trouvee -> repli synthese")
            return False
        for k in ("dos", "extra"):
            if slots[k] and not _same_product(slots["face"], slots[k], prompt):
                log(f"PROGRESS:reference:photo {k} ecartee (produit different de la face)")
                os.remove(slots[k])
                slots[k] = None
        log("PROGRESS:reference:selection finale: face" + (" + dos" if slots["dos"] else "") + (" + vue extra" if slots["extra"] else ""))
        import shutil as _sh
        _sh.move(slots["face"], base)
        vi = 2
        for k in ("dos", "extra"):
            if slots[k]:
                _sh.move(slots[k], f"{stem}_v{vi}.png")
                vi += 1
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def run_pipeline(prompt: str, run_id: str, *,
                 output_dir: Path = DEFAULT_OUTPUT_DIR,
                 multi_view: bool | None = None,
                 motion_prompt: str | None = None,
                 force: bool = False,
                 images: list[str] | None = None,
                 purpose: str = "visual_preview",
                 subject_kind_hint: str | None = None,
                 _vlm_retry: bool = False) -> dict:
    if not prompt.strip():
        return {"ok": False, "error": "empty prompt"}
    if not run_id.strip():
        return {"ok": False, "error": "empty run_id"}

    started_at = time.time()
    started_at_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at))
    audit: list[dict] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 0 — classify
    extraction = extract_kind(prompt)
    kind = subject_kind_hint or extraction["kind"]
    # Rescue misrouted compound prompts: a named human identity ("Keanu Reeves
    # on a motorcycle") otherwise first-matches `vehicle` and loses the human
    # fidelity + rigging contracts. Only applies when the caller did NOT pass an
    # explicit subject kind (explicit hint always wins).
    kind_refine = None
    if not subject_kind_hint and refine_subject_kind is not None:
        try:
            kind_refine = refine_subject_kind(prompt, kind, motion_prompt)
            if kind_refine.get("changed"):
                kind = kind_refine["kind"]
        except Exception:  # noqa: BLE001
            kind_refine = None
    audit.append({
        "stage": "extract_kind",
        "kind": extraction["kind"],
        "effective_kind": kind,
        "confidence": extraction["confidence"],
        "matched_pattern": extraction["matched_pattern"],
        "kind_rescued": bool(kind_refine and kind_refine.get("changed")),
        "kind_rescue_reason": (kind_refine or {}).get("reason"),
    })

    # Stage 0.5 — consult router (routePipeline mirror) BEFORE committing
    # to FLUX -> Hunyuan3D. iter14: if the router selects procedural or
    # photogrammetry we dispatch immediately and skip the AI generation
    # branch entirely. fallback_pipeline kicks in only on dispatch failure.
    image_count = len(images) if images else 0
    routing = None
    if route_pipeline is not None:
        try:
            routing = route_pipeline(
                prompt,
                image_count=image_count,
                purpose=purpose,
                subject_kind=subject_kind_hint or kind or "product",
            )
        except Exception as exc:  # noqa: BLE001 — router must never break the orchestrator
            routing = None
            audit.append({"stage": "route", "ok": False,
                          "error": f"route_pipeline raised: {exc}"})
    if routing is not None:
        audit.append({
            "stage": "route",
            "ok": True,
            "pipeline": routing.get("pipeline"),
            "procedural_template": routing.get("procedural_template"),
            "fallback_pipeline": routing.get("fallback_pipeline"),
            "system_class": routing.get("system_class"),
            "flags": routing.get("flags"),
            "probable_pipeline": routing.get("probable_pipeline"),
        })

        # ── Procedural dispatch ──
        # Aurora: si TRELLIS.2 est dispo, on IGNORE le routage procedural. Le procedural
        # produit une PLANCHE PLATE texturee (ex: une "carte mere" = photo plaquee sur un plan),
        # alors que TRELLIS donne du vrai 3D coherent sur perso/creature/objet technique. Le
        # procedural ne reste utile que si TRELLIS est indispo.
        _trellis_avail = False
        try:
            _tp_dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
            if _tp_dir not in sys.path:
                sys.path.insert(0, _tp_dir)
            import aurora_trellis_wrapper as _tp  # noqa: WPS433
            _trellis_avail = _tp.is_available()
        except Exception:  # noqa: BLE001
            _trellis_avail = False
        if _trellis_avail and routing.get("pipeline") == "procedural":
            audit.append({"stage": "route_override", "ok": True,
                          "note": "TRELLIS.2 dispo -> AI 3D au lieu du procedural (vrai 3D vs planche plate)",
                          "was": routing.get("procedural_template")})
        if (not _trellis_avail
                and routing.get("pipeline") == "procedural"
                and routing.get("procedural_template")):
            template = routing["procedural_template"]
            sys.stderr.write(f"[procedural-dispatch] {template} for "
                             f"prompt={prompt[:80]!r}\n")
            proc_res = run_procedural_dispatch(template, prompt, run_id, output_dir)
            audit.append({"stage": "procedural", **proc_res})
            proc_front_reference = None
            proc_images = [str(img).strip() for img in (images or []) if str(img).strip()]
            if proc_images:
                proc_ref = output_dir / f"{run_id}_reference.png"
                if force or not proc_ref.is_file():
                    staged = _stage_reference_image(proc_images[0], proc_ref)
                else:
                    staged = {
                        "ok": True,
                        "source": proc_images[0],
                        "path": str(proc_ref),
                        "size_bytes": proc_ref.stat().st_size,
                        "skipped": True,
                        "reason": "reference exists; pass --force to restage",
                    }
                audit.append({
                    "stage": "input_reference",
                    "ok": staged.get("ok", False),
                    "mode": "procedural_reference",
                    "views": {"front": {"path": staged.get("path"), "source": staged.get("source")}},
                    "error": staged.get("error"),
                })
                if not staged.get("ok"):
                    return {
                        "ok": False,
                        "schema": "aurora.pipeline.v1",
                        "error": f"input reference rejected: {staged.get('error')}",
                        "run_id": run_id,
                        "prompt": prompt,
                        "kind": kind,
                        "pipeline": "procedural",
                        "procedural_template": template,
                        "audit_trail": audit,
                    }
                proc_front_reference = str(proc_ref)
            if proc_res.get("ok"):
                elapsed = round(time.time() - started_at, 1)
                final_acceptance = run_final_acceptance(
                    proc_res["glb_path"], prompt, kind, motion_prompt,
                )
                print(f"PROGRESS:finalisation:controle final — note {final_acceptance.get('engineer_grade')}/100 (seuil {final_acceptance.get('threshold')})", flush=True)
                audit.append({
                    "stage": "final_acceptance_gate",
                    "ok": final_acceptance.get("ok", False),
                    "acceptance_ok": final_acceptance.get("acceptance_ok", False),
                    "engineer_grade": final_acceptance.get("engineer_grade"),
                    "threshold": final_acceptance.get("threshold"),
                    "hard_failures": final_acceptance.get("hard_failures") or [],
                    "suggested_fixes": final_acceptance.get("suggested_fixes") or [],
                })
                if not final_acceptance.get("acceptance_ok", False):
                    failures = _acceptance_failure_summary(final_acceptance)
                    _record_pipeline_dispatch(
                        run_id, prompt, started_at_iso,
                        status="blocked",
                        verdict=("procedural final acceptance rejected: "
                                 + "; ".join(map(str, failures[:3]))),
                        files_touched=[proc_res["glb_path"]],
                        metadata={
                            "run_id": run_id,
                            "kind": kind,
                            "pipeline": "procedural",
                            "procedural_template": template,
                            "elapsed_s": elapsed,
                            "final_mesh": proc_res["glb_path"],
                            "acceptance_ok": False,
                            "engineer_grade": final_acceptance.get("engineer_grade"),
                            "acceptance_failures": failures,
                        },
                    )
                    return {
                        "ok": False,
                        "schema": "aurora.pipeline.v1",
                        "error": "final acceptance rejected: "
                                 + "; ".join(map(str, failures[:3])),
                        "run_id": run_id,
                        "prompt": prompt,
                        "kind": kind,
                        "pipeline": "procedural",
                        "procedural_template": template,
                        "params": proc_res.get("params"),
                        "final_mesh": proc_res["glb_path"],
                        "raw_mesh": proc_res["glb_path"],
                        "front_reference": proc_front_reference,
                        "size_bytes": proc_res["size_bytes"],
                        "elapsed_s": elapsed,
                        "acceptance": final_acceptance,
                        "audit_trail": audit,
                    }
                _record_pipeline_dispatch(
                    run_id, prompt, started_at_iso,
                    status="done",
                    verdict=(f"procedural ({template}), elapsed {elapsed}s, "
                             f"{proc_res['size_bytes']} bytes, "
                             f"acceptance {final_acceptance.get('engineer_grade')}/"
                             f"{final_acceptance.get('threshold')}"),
                    files_touched=[proc_res["glb_path"]],
                    metadata={
                        "run_id": run_id,
                        "kind": kind,
                        "pipeline": "procedural",
                        "procedural_template": template,
                        "params": proc_res.get("params"),
                        "elapsed_s": elapsed,
                        "final_mesh": proc_res["glb_path"],
                        "acceptance_ok": True,
                        "engineer_grade": final_acceptance.get("engineer_grade"),
                    },
                )
                return {
                    "ok": True,
                    "schema": "aurora.pipeline.v1",
                    "run_id": run_id,
                    "prompt": prompt,
                    "kind": kind,
                    "pipeline": "procedural",
                    "procedural_template": template,
                    "params": proc_res.get("params"),
                    "final_mesh": proc_res["glb_path"],
                    "raw_mesh": proc_res["glb_path"],
                    "front_reference": proc_front_reference,
                    "size_bytes": proc_res["size_bytes"],
                    "elapsed_s": elapsed,
                    "acceptance": final_acceptance,
                    "audit_trail": audit,
                }
            # Procedural failed → log and fall through to AI generation.
            sys.stderr.write(f"[procedural-fallback] {proc_res.get('error')} "
                             f"-> falling back to "
                             f"{routing.get('fallback_pipeline', 'ai_generation')}\n")
            audit.append({"stage": "procedural_fallback",
                          "to": routing.get("fallback_pipeline", "ai_generation"),
                          "reason": proc_res.get("error")})

        # ── Photogrammetry dispatch ──
        elif routing.get("pipeline") == "photogrammetry":
            sys.stderr.write(f"[photogrammetry-dispatch] {len(images or [])} images\n")
            photo_res = run_photogrammetry_dispatch(images or [], run_id, output_dir)
            audit.append({"stage": "photogrammetry", **photo_res})
            if photo_res.get("ok"):
                elapsed = round(time.time() - started_at, 1)
                final_acceptance = run_final_acceptance(
                    photo_res["glb_path"], prompt, kind, motion_prompt,
                )
                audit.append({
                    "stage": "final_acceptance_gate",
                    "ok": final_acceptance.get("ok", False),
                    "acceptance_ok": final_acceptance.get("acceptance_ok", False),
                    "engineer_grade": final_acceptance.get("engineer_grade"),
                    "threshold": final_acceptance.get("threshold"),
                    "hard_failures": final_acceptance.get("hard_failures") or [],
                    "suggested_fixes": final_acceptance.get("suggested_fixes") or [],
                })
                if not final_acceptance.get("acceptance_ok", False):
                    failures = _acceptance_failure_summary(final_acceptance)
                    _record_pipeline_dispatch(
                        run_id, prompt, started_at_iso,
                        status="blocked",
                        verdict=("photogrammetry final acceptance rejected: "
                                 + "; ".join(map(str, failures[:3]))),
                        files_touched=[photo_res["glb_path"]],
                        metadata={
                            "run_id": run_id,
                            "kind": kind,
                            "pipeline": "photogrammetry",
                            "elapsed_s": elapsed,
                            "final_mesh": photo_res["glb_path"],
                            "acceptance_ok": False,
                            "engineer_grade": final_acceptance.get("engineer_grade"),
                            "acceptance_failures": failures,
                        },
                    )
                    return {
                        "ok": False,
                        "schema": "aurora.pipeline.v1",
                        "error": "final acceptance rejected: "
                                 + "; ".join(map(str, failures[:3])),
                        "run_id": run_id,
                        "prompt": prompt,
                        "kind": kind,
                        "pipeline": "photogrammetry",
                        "final_mesh": photo_res["glb_path"],
                        "raw_mesh": photo_res["glb_path"],
                        "front_reference": None,
                        "size_bytes": photo_res["size_bytes"],
                        "elapsed_s": elapsed,
                        "acceptance": final_acceptance,
                        "audit_trail": audit,
                    }
                _record_pipeline_dispatch(
                    run_id, prompt, started_at_iso,
                    status="done",
                    verdict=f"photogrammetry, elapsed {elapsed}s, "
                            f"{photo_res['size_bytes']} bytes, "
                            f"acceptance {final_acceptance.get('engineer_grade')}/"
                            f"{final_acceptance.get('threshold')}",
                    files_touched=[photo_res["glb_path"]],
                    metadata={
                        "run_id": run_id,
                        "kind": kind,
                        "pipeline": "photogrammetry",
                        "elapsed_s": elapsed,
                        "final_mesh": photo_res["glb_path"],
                        "acceptance_ok": True,
                        "engineer_grade": final_acceptance.get("engineer_grade"),
                    },
                )
                return {
                    "ok": True,
                    "schema": "aurora.pipeline.v1",
                    "run_id": run_id,
                    "prompt": prompt,
                    "kind": kind,
                    "pipeline": "photogrammetry",
                    "final_mesh": photo_res["glb_path"],
                    "raw_mesh": photo_res["glb_path"],
                    "front_reference": None,
                    "size_bytes": photo_res["size_bytes"],
                    "elapsed_s": elapsed,
                    "acceptance": final_acceptance,
                    "audit_trail": audit,
                }
            sys.stderr.write(f"[photogrammetry-fallback] {photo_res.get('error')} "
                             f"-> falling back to ai_generation\n")
            audit.append({"stage": "photogrammetry_fallback",
                          "to": "ai_generation",
                          "reason": photo_res.get("error")})

    # Decide multi-view (None means auto).
    # v83-3dloop: l'utilisateur veut systematiquement du 360° (faces avant ET
    # arriere coherentes), pas du single-view qui fait halluciner le dos par
    # Hunyuan3D-2.0. DEFAUT = True (multi-view + Hunyuan3D-2mv) pour tous les
    # sujets — le surcout temps/VRAM est assume. `--single-view` force l'ancien
    # comportement. Les sujets procedural Blender ignorent ce flag en aval.
    if multi_view is None:
        multi_view = True
    # TRELLIS.2 reconstruit une 3D COHERENTE depuis UNE seule image : la synthese 4-vues
    # (lente ~5 min ET source du double-visage via fusion incoherente) est inutile et non
    # consommee par TRELLIS. Si TRELLIS est dispo -> single-view (front only) : synthese ~4x
    # plus rapide + resultat propre. (Fallback Hunyuan garde le multivue.)
    try:
        _tr_probe_dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
        if _tr_probe_dir not in sys.path:
            sys.path.insert(0, _tr_probe_dir)
        import aurora_trellis_wrapper as _trellis_probe  # noqa: WPS433
        if _trellis_probe.is_available():
            multi_view = False
            audit.append({"stage": "trellis2_singleview", "ok": True,
                          "note": "TRELLIS.2 dispo -> single-view, synthese 4-vues sautee"})
    except Exception:  # noqa: BLE001
        pass
    audit.append({"stage": "multi_view_decision", "multi_view": multi_view,
                  "kind": kind, "auto_recommended": True,
                  "default_policy": "always_multiview_v83"})

    # Stage 1 — FLUX synth (skip if reference exists and --force not set)
    front_ref = output_dir / f"{run_id}_reference.png"
    back_ref  = output_dir / f"{run_id}_back_reference.png"
    left_ref  = output_dir / f"{run_id}_left_reference.png"
    right_ref = output_dir / f"{run_id}_right_reference.png"
    reference_synth_result = None

    # === AUTO-ALIMENTATION (fidelite vs creation) ===
    # Sujet REEL specifique (marque/modele/produit) -> l'IA cherche elle-meme une VRAIE
    # photo sur le web et TRELLIS la reproduit fidelement. Sujet generique/creatif -> FLUX invente.
    _use_researched = False
    _req_imgs_now = [str(img).strip() for img in (images or []) if str(img).strip()]
    if not _req_imgs_now and not (not force and front_ref.is_file()) and _should_research_reference(prompt):
        print("PROGRESS:reference:sujet reel detecte -> recherche autonome d'une vraie photo...", flush=True)
        if _research_real_reference(prompt, front_ref, log=lambda m: print(m, flush=True)):
            _use_researched = True
            multi_view = False  # une vraie photo -> single-view (TRELLIS reproduit fidelement)
            audit.append({"stage": "reference_research", "ok": True,
                          "note": "vraie photo web utilisee comme reference (fidelite)"})
        else:
            audit.append({"stage": "reference_research", "ok": False,
                          "note": "aucune photo web exploitable -> FLUX (creation)"})

    input_reference_result = None
    requested_images = [str(img).strip() for img in (images or []) if str(img).strip()]
    if requested_images:
        import re  # subprocess est deja importe au niveau module (l'import local ici rendait
        # `subprocess` local a toute la fonction -> UnboundLocalError dans la branche TRELLIS)

        def extract_json(text):
            # Find the last valid json object in the stdout
            try:
                # Try parsing the whole thing first
                return json.loads(text.strip())
            except Exception:
                # Fallback: find the first { and last }
                match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except:
                        pass
            return {}

        # 1. AUTO-TAGGING via CLIP
        try:
            tag_cmd = [sys.executable, str(Path(__file__).parent / "auto_tag_images.py"), "--images"] + requested_images
            tag_res = subprocess.run(tag_cmd, capture_output=True, text=True)
            tag_data = extract_json(tag_res.stdout)
            tagged_images = tag_data.get("tags", {})
        except Exception:
            # Fallback to simple zipping if tagging fails
            tagged_images = {k: v for k, v in zip(["front", "back", "left", "right"], requested_images)}

        if "front" not in tagged_images and requested_images:
            tagged_images["front"] = requested_images[0] # ensure front exists

        # 2. If single view + multi_view enabled, generate intelligent missing views
        if len(tagged_images) < 4 and multi_view:
            audit.append({"stage": "input_reference_policy", "multi_view": True, "reason": "auto-generating missing views intelligently from single view"})
            front_src = tagged_images["front"]
            
            # Fetch Web Context for Back View
            try:
                web_cmd = [sys.executable, str(Path(__file__).parent / "web_reference_search.py"), "--character", prompt, "--output-dir", str(output_dir)]
                web_res = subprocess.run(web_cmd, capture_output=True, text=True)
                web_data = extract_json(web_res.stdout)
                back_source = web_data.get("downloaded_references", [front_src])[0] if web_data.get("downloaded_references") else front_src
            except Exception:
                back_source = front_src
            
            # Generate Missing Views with FLUX Img2Img
            try:
                for v_name, src_path in [("back", back_source), ("left", front_src), ("right", front_src)]:
                    if v_name not in tagged_images:
                        gen_cmd = [sys.executable, str(Path(__file__).parent / "flux_image_to_multiview.py"), "--prompt", prompt, "--run-id", run_id, "--view", v_name, "--source-image", src_path, "--output-dir", str(output_dir), "--denoise", "0.5"]  # Aurora: 0.75->0.5, vues plus coherentes avec l'original
                        gen_res = subprocess.run(gen_cmd, capture_output=True, text=True)
                        gen_data = extract_json(gen_res.stdout)
                        if gen_data.get("ok"):
                            tagged_images[v_name] = gen_data["path"]
            except Exception as e:
                audit.append({"stage": "input_reference_policy", "warning": f"AI multiview generation failed: {e}"})
                multi_view = False # fallback to single view if AI fails
        
        # 3. Stage the views
        view_targets = {"front": front_ref, "back": back_ref, "left": left_ref, "right": right_ref}
        staged_views = {}
        for view, src in tagged_images.items():
            if view in view_targets:
                target = view_targets[view]
                if force or not target.is_file():
                    staged = _stage_reference_image(src, target)
                else:
                    staged = {"ok": True, "source": src, "path": str(target), "size_bytes": target.stat().st_size, "skipped": True}
                if staged.get("ok"):
                    staged_views[view] = staged

        input_reference_result = {
            "ok": True,
            "schema": "aurora.input_reference.v1",
            "mode": "multiview_input" if len(staged_views) == 4 else "single_input",
            "views": staged_views,
            "image_count": len(requested_images),
        }
        audit.append({
            "stage": "input_reference",
            "ok": True,
            "mode": input_reference_result["mode"],
            "views": {v: {"path": d.get("path"), "source": d.get("source")} for v, d in staged_views.items()},
        })

    if _use_researched:
        audit.append({"stage": "flux_synth", "skipped": True,
                      "reason": "reference reelle recuperee sur le web (fidelite) -> pas de FLUX"})
        reference_synth_result = {"ok": True, "researched": True}
    elif input_reference_result is not None:
        reference_synth_result = input_reference_result
    elif not force and front_ref.is_file():
        audit.append({"stage": "flux_synth", "skipped": True,
                      "reason": "reference exists; pass --force to regenerate"})
        reference_synth_result = None
    else:
        # iter24.fix: enrich the prompt with brand-specific visual cues for
        # recognisable products (X870E Hero, ROG, Strimer, ...). The user's
        # verbatim prompt stays at the front; cues are appended after a comma
        # so the FLUX diffusion model gets a stronger signal on PCB color,
        # branded heatsinks, OLED placement, AURA RGB zones, etc. The orig
        # prompt is preserved in the audit_trail for diagnostic.
        flux_prompt = enhance_flux_prompt(
            prompt, motion_prompt=motion_prompt,
            subject_kind=subject_kind_hint or kind,
        )
        if flux_prompt != prompt:
            faithful_analysis = None
            if compose_faithful_prompt is not None:
                try:
                    faithful_analysis = compose_faithful_prompt(
                        prompt, subject_kind=subject_kind_hint or kind,
                        motion_prompt=motion_prompt,
                    )["analysis"]
                except Exception:  # noqa: BLE001
                    faithful_analysis = None
            audit.append({"stage": "flux_prompt_enhanced",
                          "original_chars": len(prompt),
                          "enhanced_chars": len(flux_prompt),
                          "appended_chars": len(flux_prompt) - len(prompt),
                          "faithful_compound": bool(faithful_analysis and faithful_analysis.get("compound")),
                          "faithful_families": (faithful_analysis or {}).get("families"),
                          "faithful_identity": (faithful_analysis or {}).get("identity")})
        if multi_view:
            res = synth_multiview(
                flux_prompt, run_id, output_dir=output_dir,
                subject_kind=subject_kind_hint or kind,
                motion_prompt=motion_prompt,
            )
        else:
            _k_syn = (subject_kind_hint or kind or "").lower()
            if _k_syn in ("character", "humanoid", "creature", "quadruped"):
                res = synth(flux_prompt, run_id, output_dir=output_dir,
                            width=1024, height=1408, steps=44)
            else:
                res = synth(flux_prompt, run_id, output_dir=output_dir,
                            width=1216, height=1216, steps=44)
        reference_synth_result = res
        if not res.get("ok"):
            _record_pipeline_dispatch(run_id, prompt, started_at_iso,
                                      status="blocked",
                                      verdict=f"flux_synth failed: {res.get('error')}")
            return {"ok": False, "error": f"flux_synth failed: {res.get('error')}",
                    "audit_trail": audit}
        audit.append({"stage": "flux_synth", "ok": True,
                      "multi_view": multi_view,
                      "elapsed_s": res.get("elapsed_s"),
                      "seed": res.get("seed"),
                      "attempts": res.get("attempts"),
                      "terminal_recommendation": res.get("terminal_recommendation")})

    if multi_view:
        view_paths = {
            "front": front_ref,
            "back": back_ref,
            "left": left_ref,
            "right": right_ref,
        }
        turnaround = audit_multiview_consistency(
            view_paths, subject_kind=subject_kind_hint or kind,
            motion_prompt=motion_prompt,
        )
        audit.append({
            "stage": "turnaround_reference_audit",
            "ok": turnaround.get("ok", False),
            "failures": turnaround.get("failures") or [],
        })
        if not turnaround.get("ok"):
            failures = turnaround.get("failures") or ["turnaround reference audit failed"]
            # Aurora: fallback NON DESTRUCTIF. Avant, on effacait back+left+right et on
            # repassait en single-view -> Hunyuan hallucinait l'arriere A PLAT (ailerons
            # Goldorak en "planches"). Desormais on GARDE front+back (la vraie profondeur
            # avant/arriere), on ne jette que les vues LATERALES (souvent incoherentes).
            # On ne repasse full single-view que si le back est absent.
            back_ok = back_ref.is_file()
            audit.append({
                "stage": "turnaround_reference_audit_fallback",
                "warning": ("audit partiel: on garde front+back, on jette left/right"
                            if back_ok else "audit echoue: back absent -> single view"),
                "failures": failures,
                "kept_back": back_ok,
            })
            for view_path in [left_ref, right_ref]:
                if view_path.is_file():
                    try:
                        view_path.unlink()
                    except Exception:
                        pass
            if not back_ok:
                multi_view = False

    # Stage 2 — Hunyuan3D
    mesh_path = output_dir / f"{run_id}_mesh.glb"

    def _native_ok(_mp):
        _mp = str(_mp or "").strip().lower()
        if not _mp:
            return True
        _fluid = ("eau", "coule", "cascade", "vapeur", "fumee", "brume", "goutte",
                  "water", "steam", "smoke", "fog", "led", "clignote", "pulse")
        _rig = ("marche", "court", "danse", "saute", "vole", "nage", "assis",
                "walk", "run", "dance", "jump", "galop", "trot")
        return any(k in _mp for k in _fluid) and not any(k in _mp for k in _rig)

    _keep_native = False
    if not force and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
        audit.append({"stage": "hunyuan3d", "skipped": True,
                      "mesh_path": str(mesh_path),
                      "reason": "mesh exists; pass --force to regenerate"})
        raw_dense_path = Path(str(mesh_path))
        _keep_native = _native_ok(motion_prompt)
        if _keep_native:
            audit.append({"stage": "native_quality", "ok": True,
                          "note": "mesh existant reutilise tel quel: aucune etape destructrice "
                                  "(fidelity/taubin/optimize/normal-bake sautes)"})
    else:
        # === VOIE PRINCIPALE : TRELLIS.2 (single-image -> geometrie COHERENTE + PBR) ===
        # Attaque la RACINE du "double-visage / cornes doublees / poitrine fragmentee" :
        # une seule image reconstruite en 3D en interne, ZERO fusion de vues FLUX qui se
        # contredisent. Valide sur RTX 5070 Ti 16 Go (peak ~3.6 Go, ~4 min). Fallback
        # automatique sur Hunyuan3D si indispo (kernels absents) ou echec.
        _trellis_ok = False
        try:
            _tr_dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
            if _tr_dir not in sys.path:
                sys.path.insert(0, _tr_dir)
            import aurora_trellis_wrapper as _trellis  # noqa: WPS433
            if _trellis.is_available():
                print("PROGRESS:shape:TRELLIS.2 — geometrie coherente + PBR depuis 1 image...", flush=True)
                _free_gpu_before_hunyuan(audit)  # libere ComfyUI/FLUX/Ollama avant TRELLIS
                # SOUS-PROCESS dedie: env propre (CUDA_HOME/nvcc pour le JIT nvdiffrast) et
                # surtout la VRAM du modele 4B (~11 Go) est 100% liberee a la sortie. En
                # in-process le modele restait cache -> OOM du repli Hunyuan -> rescue CPU tres lent.
                _wrapper = str(Path(_tr_dir) / "aurora_trellis_wrapper.py")
                _tr_env = {**os.environ}
                _tr_env.setdefault("CUDA_HOME", "/usr/local/cuda-12.8")
                _tr_env["PATH"] = "/usr/local/cuda-12.8/bin" + os.pathsep + _tr_env.get("PATH", "")
                _tr_env.setdefault("ATTN_BACKEND", "xformers")
                _tr = {}
                try:
                    _free_req = urllib.request.Request(
                        "http://127.0.0.1:8188/free",
                        data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(_free_req, timeout=30) as _fr:
                        _fr.read()
                    print("PROGRESS:memoire:modeles FLUX decharges de ComfyUI avant TRELLIS", flush=True)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as _pr:
                        _loaded = json.loads(_pr.read().decode("utf-8")).get("models", [])
                    for _lm in _loaded:
                        _ur = urllib.request.Request(
                            "http://127.0.0.1:11434/api/generate",
                            data=json.dumps({"model": _lm.get("name"), "keep_alive": 0}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}, method="POST")
                        with urllib.request.urlopen(_ur, timeout=30) as _uresp:
                            _uresp.read()
                    if _loaded:
                        print("PROGRESS:memoire:%d modele(s) Ollama decharges avant TRELLIS" % len(_loaded), flush=True)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    _tr_cmd = [sys.executable, _wrapper, str(front_ref), str(mesh_path)]
                    if os.environ.get("AURORA_TRELLIS2_MULTIVIEW", "0") == "1":
                        _stem = str(front_ref)
                        _stem = _stem[:-4] if _stem.lower().endswith(".png") else _stem
                        for _vi in (2, 3):
                            _vp = f"{_stem}_v{_vi}.png"
                            if os.path.isfile(_vp):
                                _tr_cmd.append(_vp)
                    _p = subprocess.run(_tr_cmd,
                                        env=_tr_env, capture_output=True, text=True, timeout=6000)
                    for _line in reversed((_p.stdout or "").splitlines()):
                        if _line.startswith("AURORA_TRELLIS_RESULT:"):
                            _tr = json.loads(_line[len("AURORA_TRELLIS_RESULT:"):]); break
                    if not _tr:
                        _tr = {"ok": False, "error": (_p.stderr or _p.stdout or "no output")[-400:]}
                except Exception as _se:  # noqa: BLE001
                    _tr = {"ok": False, "error": f"subprocess: {_se!r}"}
                if _tr.get("ok") and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
                    _trellis_ok = True
                    audit.append({"stage": "trellis2", "ok": True, "mesh_path": str(mesh_path),
                                  "faces": _tr.get("faces"), "verts": _tr.get("verts"),
                                  "peak_vram_gb": _tr.get("peak_vram_gb"), "quality": _tr.get("quality")})
                    print(f"PROGRESS:shape:geometrie native posee — {_tr.get('faces') or '?'} faces ({_tr.get('quality')})", flush=True)
                    raw_dense_path = Path(str(mesh_path))
                    audit.append({"stage": "mesh_sanitize", "skipped": True,
                                  "reason": "geometrie TRELLIS.2 single-image native conservee "
                                            "(qualite maximale prouvee; assainissement reserve "
                                            "aux meshes issus de fusion multi-vues)"})
                    _keep_native = _native_ok(motion_prompt)
                    if _keep_native:
                        audit.append({"stage": "native_quality", "ok": True,
                                      "note": "objet statique TRELLIS.2: mesh+texture natifs "
                                              "integralement conserves (fidelity/taubin/optimize/"
                                              "normal-bake sautes, prouves destructeurs)"})
                        print("PROGRESS:qualite:mesh + texture natifs conserves integralement (aucune etape destructrice)", flush=True)
                    _k_fid = (subject_kind_hint or kind or "").lower()
                    _fid_character = _k_fid in ("character", "humanoid", "creature", "quadruped")
                    if _fid_character and not _use_researched:
                        audit.append({"stage": "texture_fidelity", "skipped": True,
                                      "reason": "personnage: texture TRELLIS.2 native conservee (protection visage/yeux)"})
                    if (os.environ.get("AURORA_TEXTURE_FIDELITY", "1") == "1"
                            and front_ref.is_file()
                            and not _keep_native
                            and not (_fid_character and not _use_researched)
                            and (_use_researched or not multi_view)):
                        try:
                            print("PROGRESS:texture_fidelity:projection de la photo de reference sur la face avant...", flush=True)
                            _fid_out = output_dir / f"{run_id}_mesh_fidelity.glb"
                            _fid_script = str(REPO_ROOT / "application" / "python-services" / "texture_fidelity.py")
                            _fid_cmd = [sys.executable, _fid_script,
                                        "--mesh", str(mesh_path),
                                        "--photo", str(front_ref),
                                        "--output", str(_fid_out)]
                            _fp = subprocess.run(_fid_cmd, capture_output=True, text=True, timeout=3600)
                            _fid = {}
                            for _fl in reversed((_fp.stdout or "").splitlines()):
                                if _fl.startswith("AURORA_FIDELITY_RESULT:"):
                                    _fid = json.loads(_fl[len("AURORA_FIDELITY_RESULT:"):]); break
                            if _fid.get("ok") and _fid_out.is_file() and _fid_out.stat().st_size > 1000:
                                try:
                                    import stage_quality_gate as _sqg
                                    _gate = _sqg.gate(mesh_path, _fid_out, "texture_fidelity")
                                except Exception as _ge:  # noqa: BLE001
                                    _gate = {"skipped": True, "reason": repr(_ge)}
                                if _gate.get("degraded"):
                                    audit.append({"stage": "texture_fidelity", "ok": False,
                                                  "reverted": True,
                                                  "gate": _gate,
                                                  "note": "projection annulee: degradation detectee, mesh precedent conserve"})
                                else:
                                    mesh_path = _fid_out
                                    audit.append({"stage": "texture_fidelity", "ok": True,
                                                  "mesh_path": str(_fid_out),
                                                  "gate": _gate,
                                                  "axis": _fid.get("axis"),
                                                  "coverage": _fid.get("coverage"),
                                                  "refined": _fid.get("refined")})
                            else:
                                audit.append({"stage": "texture_fidelity", "ok": False,
                                              "error": _fid.get("error") or (_fp.stderr or _fp.stdout or "no output")[-300:]})
                        except Exception as _fe:
                            audit.append({"stage": "texture_fidelity", "ok": False, "error": repr(_fe)})
                else:
                    audit.append({"stage": "trellis2", "ok": False,
                                  "error": _tr.get("error"), "note": "fallback Hunyuan3D"})
            else:
                audit.append({"stage": "trellis2", "skipped": True,
                              "reason": _trellis.import_error() or "indisponible",
                              "note": "fallback Hunyuan3D"})
        except Exception as _e:  # noqa: BLE001
            audit.append({"stage": "trellis2", "ok": False, "error": repr(_e),
                          "note": "fallback Hunyuan3D"})

        if not _trellis_ok:
            # v90: map the Stage-0 kind to the worker's intent_purpose so the right
            # shape-quality branch fires (character → octree 512/steps 70, etc.).
            kwargs = {"image_path": front_ref, "run_id": run_id,
                      "output_dir": output_dir,
                      "intent_purpose": _kind_to_intent_purpose(kind),
                      "motion_readiness": "rig_candidate" if _kind_to_intent_purpose(kind) == "character" else "static_only"}
            if multi_view and back_ref.is_file():
                kwargs["mv_front"] = front_ref
                kwargs["mv_back"]  = back_ref
                # front+back SEULEMENT (les vues laterales FLUX independantes doublent la tete).
                kwargs["mv_left"]  = None
                kwargs["mv_right"] = None
            _free_gpu_before_hunyuan(audit)
            h = run_hunyuan3d(**kwargs)
            if not h.get("ok"):
                _record_pipeline_dispatch(run_id, prompt, started_at_iso,
                                          status="blocked",
                                          verdict=f"hunyuan3d failed: {h.get('error')}")
                return {"ok": False, "error": f"hunyuan3d failed: {h.get('error')}",
                        "audit_trail": audit + [{"stage": "hunyuan3d", **h}]}
            audit.append({"stage": "hunyuan3d", "ok": True,
                          "mesh_path": h["mesh_path"],
                          "size_bytes": h["size_bytes"],
                          "elapsed_s": h["elapsed_s"]})
            raw_dense_path = Path(str(mesh_path))
            try:
                from mesh_sanitize import sanitize_mesh as _sanit
                _san_out = output_dir / f"{run_id}_mesh_assaini.glb"
                _sr = _sanit(mesh_path, _san_out, res=8192, target_tris=300000)
                audit.append({"stage": "mesh_sanitize",
                              **{k: _sr.get(k) for k in ("ok", "info", "error", "mode")}})
                if _sr.get("ok") and _san_out.is_file() and _san_out.stat().st_size > 1000:
                    try:
                        import stage_quality_gate as _sqg
                        _rg = _sqg.gate(mesh_path, _san_out, "mesh_sanitize")
                    except Exception as _ge:  # noqa: BLE001
                        _rg = {"skipped": True, "reason": repr(_ge)}
                    if not _rg.get("degraded"):
                        mesh_path = _san_out
                    else:
                        audit.append({"stage": "mesh_sanitize_revert", "reverted": True,
                                      "reasons": _rg.get("reasons")})
            except Exception as _rex:  # noqa: BLE001
                audit.append({"stage": "mesh_sanitize", "ok": False, "error": repr(_rex)})

    # Stage 3 — auto_rescue
    rescue_dir = output_dir / f"rescue_{run_id}"
    rescue = auto_rescue(mesh_path, front_ref, prompt, rescue_dir)
    if not rescue.get("ok"):
        _record_pipeline_dispatch(run_id, prompt, started_at_iso,
                                  status="blocked",
                                  verdict=f"auto_rescue failed: {rescue.get('error')}")
        return {"ok": False, "error": f"auto_rescue failed: {rescue.get('error')}",
                "audit_trail": audit}
    audit.append({"stage": "auto_rescue", "ok": True,
                  "initial_score": rescue["initial_score"],
                  "final_score": rescue["final_score"],
                  "score_delta": rescue["score_delta"],
                  "final_mesh": rescue["final_mesh"],
                  "rescue_audit": rescue["audit_trail"]})

    # Stage 3.5 — viewer optimisation for textured meshes (UV-preserving decimation
    # + gltfpack quantisation). Pixel-identical look, ~35-45% smaller GLB, lighter to
    # load in three.js. Best-effort: skipped silently if pymeshlab / gltfpack absent
    # or the mesh has no baseColor texture. Keeps the un-optimised mesh as raw_mesh.
    final_mesh_path = rescue["final_mesh"]
    # v90 Stage 3.45 — UV-safe Taubin smoothing on the textured mesh. The
    # manifold/smoothing rescue is skipped for textured meshes (it would wreck
    # painted UVs), leaving raw Marching-Cubes faceting (the "cubique" look).
    # Taubin moves vertex positions only (UVs/topology untouched), so it removes
    # faceting while keeping the texture intact.
    if _keep_native:
        audit.append({"stage": "taubin_smooth", "skipped": True, "reason": "mesh natif conserve"})
    else:
        try:
            import mesh_taubin as _taubin  # noqa: WPS433
            _sm_out = str(output_dir / f"{run_id}_mesh_smooth.glb")
            _sm = _taubin.taubin_smooth(final_mesh_path, _sm_out,
                                        iterations=int(os.environ.get("AURORA_TAUBIN_ITERS", "8")))
            audit.append({"stage": "taubin_smooth", **{k: v for k, v in _sm.items() if k != "output"}})
            if _sm.get("ok"):
                final_mesh_path = _sm_out
        except Exception as exc:  # noqa: BLE001
            audit.append({"stage": "taubin_smooth", "ok": False, "error": repr(exc)})
    if _keep_native:
        audit.append({"stage": "optimize_textured_mesh", "skipped": True,
                      "reason": "mesh natif conserve (decimation prouvee destructrice des UV natifs)"})
    elif _optimize_textured_mesh is not None:
        try:
            opt_out = str(output_dir / f"{run_id}_mesh_opt.glb")
            opt_res = _optimize_textured_mesh(rescue["final_mesh"], opt_out, kind)
            audit.append({"stage": "optimize_textured_mesh", **opt_res})
            if opt_res.get("ok") and opt_res.get("changed") and Path(opt_out).is_file():
                final_mesh_path = opt_out
        except Exception as exc:  # noqa: BLE001
            audit.append({"stage": "optimize_textured_mesh", "ok": False, "error": repr(exc)})

    # Stage 3.6 — bake a high→low tangent-space normal map from the raw dense
    # Hunyuan shape onto the decimated PBR mesh. Adds visual richness (surface
    # detail of the dense mesh) at the cost of a single 2k normal-map texture.
    # Best-effort: skipped silently if Blender unavailable, the bake fails, or
    # the inputs aren't valid.
    try:
        if (not _keep_native and Path(mesh_path).is_file() and Path(final_mesh_path).is_file()
                and str(final_mesh_path) != str(mesh_path)):
            import bake_normal_map as _bake  # noqa: WPS433
            _normal_png = str(output_dir / f"{run_id}_normal.png")
            # Normal map haute-res: 8192 en mode precision max (AURORA_TRELLIS2_MANAGED), sinon
            # 4096. Recupere le detail de surface fin du mesh dense sur le mesh allege du viewer.
            _nres = int(os.environ.get("AURORA_NORMAL_RES",
                        "8192" if os.environ.get("AURORA_TRELLIS2_MANAGED") == "1" else "4096"))
            _dense_src = str(raw_dense_path) if ("raw_dense_path" in dir() and Path(str(raw_dense_path)).is_file()) else str(mesh_path)
            _bake_res = _bake.bake_normal(_dense_src, str(final_mesh_path), _normal_png, res=_nres)
            audit.append({"stage": "bake_normal", **_bake_res})
            if _bake_res.get("ok") and Path(_normal_png).is_file():
                try:
                    import trimesh as _tm  # noqa: WPS433
                    from PIL import Image as _Img  # noqa: WPS433
                    _fm = _tm.load(final_mesh_path, force="mesh", process=False)
                    _mat = getattr(getattr(_fm, "visual", None), "material", None)
                    if _mat is not None:
                        _mat.normalTexture = _Img.open(_normal_png).convert("RGB")
                        _fm.export(final_mesh_path)
                except Exception as _exc:  # noqa: BLE001
                    audit.append({"stage": "bake_normal_attach", "ok": False, "error": repr(_exc)})
    except Exception as exc:  # noqa: BLE001
        audit.append({"stage": "bake_normal", "ok": False, "error": repr(exc)})

    if os.environ.get("AURORA_AO", "1") == "1":
        try:
            import bake_ao_map as _ao
            _ao_png = str(output_dir / f"{run_id}_ao.png")
            _ao_res = int(os.environ.get("AURORA_AO_RES", "4096"))
            _ao_bake = _ao.bake_ao(str(final_mesh_path), _ao_png, res=_ao_res)
            if _ao_bake.get("ok"):
                _ao_out = str(output_dir / f"{run_id}_mesh_ao.glb")
                _ao_att = _ao.attach_ao(str(final_mesh_path), _ao_png, _ao_out)
                print(f"PROGRESS:matieres:occlusion ambiante cuite ({_ao_res}px)", flush=True)
                audit.append({"stage": "ao_bake", "ok": bool(_ao_att.get("ok")),
                              "res": _ao_res, "ao_png": _ao_png,
                              "ao_mean": _ao_bake.get("ao_mean"),
                              "ao_std": _ao_bake.get("ao_std"),
                              "modes": _ao_att.get("modes"),
                              "error": _ao_att.get("error")})
                if _ao_att.get("ok"):
                    final_mesh_path = _ao_out
            else:
                audit.append({"stage": "ao_bake", "ok": False, "res": _ao_res,
                              "error": _ao_bake.get("error")})
        except Exception as exc:
            audit.append({"stage": "ao_bake", "ok": False, "error": repr(exc)})
    else:
        audit.append({"stage": "ao_bake", "skipped": True, "reason": "AURORA_AO=0"})

    material_manifest_data = None
    material_intel_enabled = os.environ.get("AURORA_MATERIAL_INTEL", "1") == "1"
    if material_intel_enabled:
        try:
            import material_intel_classifier as _matintel
            import material_manifest as _matman
            _canon = _matintel.to_canonical(_matintel.classify(prompt, kind))
            _mat_valid, _mat_errors = _matman.validate(_canon)
            if _mat_valid:
                _canon = _matman.normalize(_canon)
                _vision_info = None
                if os.environ.get("AURORA_VLM_MATERIALS") == "1" and _ollama_reachable():
                    try:
                        import material_vision_pass as _mvp
                        _mvp_in = output_dir / f"{run_id}_materials_pre_vision.json"
                        _mvp_in.write_text(json.dumps(_canon, ensure_ascii=True, indent=2),
                                           encoding="utf-8")
                        _mvp_out = output_dir / f"{run_id}_materials_vision.json"
                        _vision_info = _mvp.run_pass(
                            str(final_mesh_path), str(_mvp_in), str(_mvp_out),
                            str(output_dir / f"{run_id}_matvision"),
                            timeout=int(os.environ.get("AURORA_VISION_TIMEOUT", "300")))
                        _enriched = json.loads(_mvp_out.read_text(encoding="utf-8"))
                        _kept = [z for z in _enriched.get("zones", [])
                                 if _matman.validate({"schema": _matman.SCHEMA_ID,
                                                      "zones": [z]})[0]]
                        if _kept:
                            _canon = _matman.normalize({**_canon, "zones": _kept})
                            _canon["vision"] = _enriched.get("vision")
                    except Exception as _vexc:
                        _vision_info = {"ok": False, "error": repr(_vexc)}
                try:
                    from zone_mask_baker import bake_zone_masks as _bzm
                    _mask_res = _bzm(str(final_mesh_path), _canon,
                                     str(output_dir / f"{run_id}_masques"))
                    audit.append({"stage": "zone_masks", **_mask_res})
                    print(f"PROGRESS:matieres:{_mask_res.get('masks', 0)} masque(s) de zone genere(s) depuis la vision", flush=True)
                    try:
                        from zone_mask_baker import refine_water_masks as _rwm
                        _rw = _rwm(str(final_mesh_path), _canon)
                        if _rw.get("refined"):
                            audit.append({"stage": "zone_masks_refine", **_rw})
                            print(f"PROGRESS:matieres:masque eau affine par la couleur reelle ({_rw['refined']} zone(s), plus de bord carre)", flush=True)
                    except Exception as _rwe:  # noqa: BLE001
                        audit.append({"stage": "zone_masks_refine", "ok": False, "error": repr(_rwe)})
                    try:
                        _zeau = next((z for z in _canon.get("zones", [])
                                      if str(z.get("label", "")).lower() in ("water", "eau", "lava", "lave")
                                      and (z.get("target") or {}).get("mask_png")), None)
                        if _zeau is not None:
                            from texture_despeckle import despeckle_glb as _dspk
                            _dsp_out = output_dir / f"{run_id}_mesh_propre.glb"
                            _dsp = _dspk(str(final_mesh_path), str(_dsp_out),
                                         mask_out=str(_zeau["target"]["mask_png"]),
                                         couleur=("chaud" if "lav" in str(_zeau.get("label", "")).lower() else "bleu"))
                            audit.append({"stage": "texture_despeckle", **_dsp})
                            if _dsp.get("ok") and _dsp_out.is_file():
                                final_mesh_path = str(_dsp_out)
                                print(f"PROGRESS:matieres:{_dsp['mouchetures_purgees_px']} px de mouchetures purges de la texture (pierre propre)", flush=True)
                    except Exception as _de:  # noqa: BLE001
                        audit.append({"stage": "texture_despeckle", "ok": False, "error": repr(_de)})
                except Exception as _mze:  # noqa: BLE001
                    audit.append({"stage": "zone_masks", "ok": False, "error": repr(_mze)})
                _materials_json = output_dir / f"{run_id}_materials.json"
                _materials_json.write_text(json.dumps(_canon, ensure_ascii=True, indent=2),
                                           encoding="utf-8")
                material_manifest_data = _canon
                audit.append({"stage": "material_intel", "ok": True,
                              "manifest": str(_materials_json),
                              "model": _canon.get("model"),
                              "zones": [z.get("zone_id") for z in _canon.get("zones", [])],
                              "vision": _vision_info})
            else:
                audit.append({"stage": "material_intel", "ok": False,
                              "errors": _mat_errors[:6]})
        except Exception as exc:
            audit.append({"stage": "material_intel", "ok": False, "error": repr(exc)})
    else:
        audit.append({"stage": "material_intel", "skipped": True,
                      "reason": "AURORA_MATERIAL_INTEL=0"})

    if material_intel_enabled and material_manifest_data is not None:
        _synth_entry = {"stage": "channel_synth", "ok": False}
        _mat_zones = material_manifest_data.get("zones", [])
        try:
            import roughness_synth as _rs
            _base_rough = 0.6
            _zone_masks_rough = []
            for _z in sorted(_mat_zones, key=lambda z: -float(z.get("confidence", 0.0))):
                _zch = _z.get("channels") or {}
                _zmask = (_z.get("target") or {}).get("mask_png")
                if "roughness" in _zch and _zmask and Path(str(_zmask)).is_file():
                    _zone_masks_rough.append((str(_zmask), float(_zch["roughness"])))
            _labels_speciaux = ("water", "glass", "crystal", "led", "screen", "gem", "ice", "mirror")
            for _z in sorted(_mat_zones, key=lambda z: -float(z.get("confidence", 0.0))):
                _zch = _z.get("channels") or {}
                _zlab = str(_z.get("label") or "").lower()
                if ("roughness" in _zch and not (_z.get("target") or {}).get("mask_png")
                        and _zlab not in _labels_speciaux):
                    _base_rough = float(_zch["roughness"])
                    break
            _rough_png = str(output_dir / f"{run_id}_roughness.png")
            _rough_glb = str(output_dir / f"{run_id}_mesh_rough.glb")
            _rs_res = _rs._run(argparse.Namespace(
                glb=str(final_mesh_path), output=_rough_png, base=_base_rough,
                jitter=0.08, cavity=0.25, dark=0.07, size=2048, seed=7,
                apply=_rough_glb, masks=_zone_masks_rough))
            _synth_entry["roughness"] = {"ok": True, "base": _base_rough,
                                         "stats": _rs_res.get("stats")}
            if Path(_rough_glb).is_file():
                final_mesh_path = _rough_glb
        except Exception as exc:
            _synth_entry["roughness"] = {"ok": False, "error": repr(exc)}
        _emissive_zone = next(
            (z for z in _mat_zones
             if z.get("label") in ("led", "screen")
             or "emissiveFactor" in (z.get("channels") or {})
             or "emissiveStrength" in (z.get("channels") or {})), None)
        if _emissive_zone is not None:
            try:
                import emissive_synth as _es
                _em_png = str(output_dir / f"{run_id}_emissive.png")
                _em_glb = str(output_dir / f"{run_id}_mesh_emissive.glb")
                _em_strength = float((_emissive_zone.get("channels") or {})
                                     .get("emissiveStrength", 5.0))
                _es_res = _es._run(argparse.Namespace(
                    glb=str(final_mesh_path), output=_em_png, hues="",
                    strength=_em_strength, sat_min=0.55, val_min=0.65, size=2048,
                    apply=_em_glb))
                _synth_entry["emissive"] = {"ok": True,
                                            "zone": _emissive_zone.get("zone_id"),
                                            "strength": _em_strength,
                                            "coverage_pct": _es_res.get("coverage_pct")}
                if Path(_em_glb).is_file():
                    final_mesh_path = _em_glb
            except Exception as exc:
                _synth_entry["emissive"] = {"ok": False, "error": repr(exc)}
        else:
            _synth_entry["emissive"] = {"skipped": True,
                                        "reason": "no led/screen/emissive zone in manifest"}
        _synth_entry["ok"] = (bool(_synth_entry.get("roughness", {}).get("ok"))
                              or bool(_synth_entry.get("emissive", {}).get("ok")))
        audit.append(_synth_entry)
    else:
        audit.append({"stage": "channel_synth", "skipped": True,
                      "reason": ("AURORA_MATERIAL_INTEL=0" if not material_intel_enabled
                                 else "no material manifest")})

    # Stage 4 (optional) — motion bake via rigify
    rigged_mesh = None
    if motion_prompt:
        motion_res = run_motion_bake(
            Path(final_mesh_path), motion_prompt, run_id, output_dir,
            subject_kind=(subject_kind_hint or kind or ""),
        )
        audit.append({"stage": "motion_bake",
                      "motion_prompt": motion_prompt,
                      **motion_res})
        if motion_res.get("ok"):
            rigged_mesh = motion_res["rigged_mesh"]
            _fspec = motion_res.get("motion_spec") or {}
            if (material_manifest_data is not None
                    and float(_fspec.get("amplitude", 0.0) or 0.0) > 0.01):
                _labels_fluides = ("water", "eau", "lava", "lave", "sea", "lake", "river")
                for _z in material_manifest_data.get("zones", []):
                    if (str(_z.get("label", "")).lower() in _labels_fluides
                            and (_z.get("target") or {}).get("mask_png")):
                        _z["flow"] = {"vitesse": float(_fspec.get("vitesse", 1.0)),
                                      "direction": [0.0, -1.0]}
                        print(f"PROGRESS:matieres:ecoulement continu embarque dans le GLB "
                              f"(zone {_z.get('zone_id')}, vitesse {_fspec.get('vitesse', 1.0)})", flush=True)

    final_delivery_mesh = rigged_mesh or final_mesh_path
    if material_intel_enabled and material_manifest_data is not None:
        try:
            import glb_material_writer as _gmw
            _mw_out = str(output_dir / f"{run_id}_final_materials.glb")
            _mw_res = _gmw.apply_manifest(str(final_delivery_mesh),
                                          material_manifest_data, _mw_out,
                                          alpha_fallback=False)
            _mw_gate = {}
            if _mw_res.get("ok"):
                try:
                    import stage_quality_gate as _sqg
                    _mw_transp = any(
                        float((z.get("channels") or {}).get("transmission", 0.0)) >= 0.5
                        and (z.get("target") or {}).get("mask_png")
                        for z in (material_manifest_data.get("zones") or []))
                    _mw_gate = _sqg.gate(final_delivery_mesh, _mw_out, "material_write",
                                         expected_transparency=_mw_transp)
                    if _mw_transp:
                        print("PROGRESS:matieres:transparence attendue (zone eau/verre) — "
                              "gate saturation adapte", flush=True)
                except Exception as _ge:  # noqa: BLE001
                    _mw_gate = {"skipped": True, "reason": repr(_ge)}
            print(f"PROGRESS:matieres:{_mw_res.get('zones_applied', 0)} zone(s) de matiere appliquee(s)", flush=True)
            audit.append({"stage": "material_write", "ok": bool(_mw_res.get("ok")),
                          "output": _mw_res.get("output"),
                          "zones_applied": _mw_res.get("zones_applied"),
                          "materials_touched": _mw_res.get("materials_touched"),
                          "extensions_used": _mw_res.get("extensions_used"),
                          "gate": _mw_gate,
                          "errors": _mw_res.get("errors")})
            if _mw_res.get("ok"):
                if _mw_gate.get("degraded"):
                    try:
                        shutil.copyfile(str(final_delivery_mesh), _mw_out)
                    except Exception:  # noqa: BLE001
                        pass
                    audit.append({"stage": "material_write_revert", "reverted": True,
                                  "reasons": _mw_gate.get("reasons"),
                                  "note": "materiaux annules: degradation detectee, mesh precedent copie en final"})
                final_delivery_mesh = _mw_out
        except Exception as exc:
            audit.append({"stage": "material_write", "ok": False, "error": repr(exc)})
    else:
        audit.append({"stage": "material_write", "skipped": True,
                      "reason": ("AURORA_MATERIAL_INTEL=0" if not material_intel_enabled
                                 else "no material manifest")})
    if os.environ.get("AURORA_VLM_CRITIC") == "1":
        critic = _run_vlm_critic(final_delivery_mesh, prompt, run_id, output_dir)
        audit.append({"stage": "vlm_critic", **critic})
        suggestion = critic.get("suggestion_reference") or ", ".join(critic.get("missing") or [])
        if critic.get("ran") and not critic.get("ok") and not _vlm_retry and suggestion:
            retry_prompt = prompt.rstrip(",. ") + ", " + suggestion
            audit.append({"stage": "vlm_critic_retry", "ok": True,
                          "retry_prompt": retry_prompt[:500]})
            retry = run_pipeline(
                retry_prompt, run_id,
                output_dir=output_dir, multi_view=multi_view,
                motion_prompt=motion_prompt, force=True,
                images=images, purpose=purpose,
                subject_kind_hint=subject_kind_hint, _vlm_retry=True,
            )
            retry["audit_trail"] = audit + (retry.get("audit_trail") or [])
            retry["vlm_retry"] = True
            retry["original_prompt"] = prompt
            return retry
    final_acceptance = run_final_acceptance(final_delivery_mesh, prompt, kind, motion_prompt)
    audit.append({
        "stage": "final_acceptance_gate",
        "ok": final_acceptance.get("ok", False),
        "acceptance_ok": final_acceptance.get("acceptance_ok", False),
        "engineer_grade": final_acceptance.get("engineer_grade"),
        "threshold": final_acceptance.get("threshold"),
        "hard_failures": final_acceptance.get("hard_failures") or [],
        "suggested_fixes": final_acceptance.get("suggested_fixes") or [],
    })

    elapsed = round(time.time() - started_at, 1)
    if not final_acceptance.get("acceptance_ok", False):
        failures = final_acceptance.get("hard_failures") or [final_acceptance.get("error") or "final acceptance failed"]
        historical_fallback = None
        if _should_try_historical_person_fallback(prompt, kind, final_acceptance):
            historical_fallback = _run_historical_person_fallback(
                prompt, kind, motion_prompt, run_id, output_dir, audit,
                final_delivery_mesh, final_acceptance,
            )
            if historical_fallback.get("ok"):
                elapsed = round(time.time() - started_at, 1)
                fallback_mesh = historical_fallback["glb_path"]
                fallback_acceptance = historical_fallback["acceptance"]
                _record_pipeline_dispatch(
                    run_id, prompt, started_at_iso,
                    status="done",
                    verdict=(
                        "ai_generation rejected, accepted volumetric historical fallback "
                        f"({historical_fallback['template']}), elapsed {elapsed}s, "
                        f"acceptance {fallback_acceptance.get('engineer_grade')}/"
                        f"{fallback_acceptance.get('threshold')}"
                    ),
                    files_touched=[
                        str(front_ref), str(mesh_path), str(final_delivery_mesh),
                        str(fallback_mesh),
                    ],
                    metadata={
                        "run_id": run_id,
                        "kind": kind,
                        "multi_view": multi_view,
                        "elapsed_s": elapsed,
                        "pipeline": "ai_generation+procedural_fallback",
                        "procedural_template": historical_fallback["template"],
                        "rejected_mesh": str(final_delivery_mesh),
                        "final_mesh": str(fallback_mesh),
                        "rejected_engineer_grade": final_acceptance.get("engineer_grade"),
                        "acceptance_ok": True,
                        "engineer_grade": fallback_acceptance.get("engineer_grade"),
                    },
                )
                return {
                    "ok": True,
                    "schema": "aurora.pipeline.v1",
                    "run_id": run_id,
                    "prompt": prompt,
                    "kind": kind,
                    "pipeline": "ai_generation+procedural_fallback",
                    "procedural_template": historical_fallback["template"],
                    "params": historical_fallback.get("params"),
                    "multi_view": multi_view,
                    "motion_prompt": motion_prompt,
                    "rigged_mesh": None,
                    "front_reference": str(front_ref),
                    "raw_mesh": str(mesh_path),
                    "rescued_mesh": rescue["final_mesh"],
                    "rejected_mesh": str(final_delivery_mesh),
                    "final_mesh": str(fallback_mesh),
                    "size_bytes": historical_fallback.get("size_bytes"),
                    "initial_score": rescue["initial_score"],
                    "final_score": rescue["final_score"],
                    "score_delta": rescue["score_delta"],
                    "elapsed_s": elapsed,
                    "acceptance": fallback_acceptance,
                    "rejected_acceptance": final_acceptance,
                    "fallback_reason": "original AI/hunyuan human mesh failed final acceptance",
                    "audit_trail": audit,
                }
            audit.append({
                "stage": "volumetric_historical_fallback_failed",
                "error": historical_fallback.get("error"),
            })

        _record_pipeline_dispatch(
            run_id, prompt, started_at_iso,
            status="blocked",
            verdict=f"final acceptance rejected: {'; '.join(map(str, failures[:3]))}",
            files_touched=[str(front_ref), str(mesh_path), str(final_delivery_mesh)],
            metadata={
                "run_id": run_id,
                "kind": kind,
                "multi_view": multi_view,
                "elapsed_s": elapsed,
                "final_mesh": str(final_delivery_mesh),
                "acceptance_ok": False,
                "engineer_grade": final_acceptance.get("engineer_grade"),
                "acceptance_failures": failures,
            },
        )
        return {
            "ok": False,
            "schema": "aurora.pipeline.v1",
            "error": "final acceptance rejected: " + "; ".join(map(str, failures[:3])),
            "run_id": run_id,
            "prompt": prompt,
            "kind": kind,
            "multi_view": multi_view,
            "motion_prompt": motion_prompt,
            "rigged_mesh": rigged_mesh,
            "front_reference": str(front_ref),
            "raw_mesh": str(mesh_path),
            "rescued_mesh": rescue["final_mesh"],
            "final_mesh": str(final_delivery_mesh),
            "initial_score": rescue["initial_score"],
            "final_score": rescue["final_score"],
            "score_delta": rescue["score_delta"],
            "elapsed_s": elapsed,
            "acceptance": final_acceptance,
            "historical_fallback": historical_fallback,
            "audit_trail": audit,
        }

    _record_pipeline_dispatch(
        run_id, prompt, started_at_iso,
        status="done",
        verdict=(f"kind={kind}, score {rescue['initial_score']}->{rescue['final_score']} "
                 f"(delta {rescue['score_delta']:+}), elapsed {elapsed}s"
                 + (f", rigged={Path(rigged_mesh).name}" if rigged_mesh else "")),
        files_touched=[str(front_ref), str(mesh_path), final_mesh_path]
                      + ([rigged_mesh] if rigged_mesh else []),
        metadata={
            "run_id": run_id,
            "kind": kind,
            "multi_view": multi_view,
            "initial_score": rescue["initial_score"],
            "final_score": rescue["final_score"],
            "score_delta": rescue["score_delta"],
            "elapsed_s": elapsed,
            "has_motion": bool(rigged_mesh),
            "final_mesh": str(final_delivery_mesh),
            "acceptance_ok": True,
            "engineer_grade": final_acceptance.get("engineer_grade"),
        },
    )
    return {
        "ok": True,
        "schema": "aurora.pipeline.v1",
        "run_id": run_id,
        "prompt": prompt,
        "kind": kind,
        "multi_view": multi_view,
        "motion_prompt": motion_prompt,
        "rigged_mesh": rigged_mesh,
        "front_reference": str(front_ref),
        "raw_mesh": str(mesh_path),
        "rescued_mesh": rescue["final_mesh"],
        "final_mesh": str(final_delivery_mesh),
        "initial_score": rescue["initial_score"],
        "final_score": rescue["final_score"],
        "score_delta": rescue["score_delta"],
        "elapsed_s": elapsed,
        "acceptance": final_acceptance,
        "audit_trail": audit,
    }


def dry_run_prompt_preview(prompt: str, *, motion_prompt: str | None = None,
                           subject_kind_hint: str | None = None) -> dict:
    """Exercise the REAL CLI prompt-build path without any GPU stage.

    Runs the exact Stage 0 (extract_kind) + enhance_flux_prompt the live
    pipeline uses, then returns the composed FLUX prompt + faithful-scene facet
    analysis. Lets us verify end-to-end that every requested element of a
    compound prompt survives into what FLUX would receive — testable offline,
    aligned with the tunnel/UI behavior.
    """
    extraction = extract_kind(prompt)
    kind = subject_kind_hint or extraction["kind"]
    kind_rescued = False
    if not subject_kind_hint and refine_subject_kind is not None:
        refine = refine_subject_kind(prompt, kind, motion_prompt)
        if refine.get("changed"):
            kind = refine["kind"]
            kind_rescued = True
    flux_prompt = enhance_flux_prompt(
        prompt, motion_prompt=motion_prompt, subject_kind=kind,
    )
    analysis = None
    if compose_faithful_prompt is not None:
        analysis = compose_faithful_prompt(
            prompt, subject_kind=kind, motion_prompt=motion_prompt,
        )["analysis"]
    return {
        "ok": True,
        "schema": "aurora.pipeline_dryrun.v1",
        "mode": "dry_run_prompt",
        "prompt": prompt,
        "kind": kind,
        "extracted_kind": extraction["kind"],
        "kind_rescued": kind_rescued,
        "kind_alternatives": extraction.get("alternatives"),
        "motion_prompt": motion_prompt,
        "flux_prompt": flux_prompt,
        "flux_prompt_changed": flux_prompt != prompt.strip(),
        "faithful_scene": analysis,
    }


def render_pretty(result: dict) -> str:
    if not result.get("ok"):
        return f"FAIL: {result.get('error')}\n"
    pipeline = result.get("pipeline") or "ai_generation"
    lines = [
        f"Aurora 3D pipeline — run_id: {result['run_id']}",
        f"  prompt:        {result['prompt'][:80]}",
        f"  kind:          {result.get('kind')}",
        f"  pipeline:      {pipeline}"
        + (f" ({result.get('procedural_template')})" if result.get('procedural_template') else ""),
    ]
    if pipeline == "ai_generation":
        lines += [
            f"  multi_view:    {result.get('multi_view')}",
            f"  ref:           {result.get('front_reference')}",
            f"  raw mesh:      {result.get('raw_mesh')}",
            f"  final mesh:    {result.get('final_mesh')}",
            f"  score:         {result.get('initial_score')} -> {result.get('final_score')}  "
            f"(delta {result.get('score_delta', 0):+})",
        ]
    else:
        lines += [
            f"  final mesh:    {result.get('final_mesh')}",
            f"  size:          {result.get('size_bytes', 0)} bytes",
        ]
    lines += [
        f"  total elapsed: {result['elapsed_s']}s",
        "",
        "Audit:",
    ]
    for entry in result["audit_trail"]:
        stage = entry.get("stage", "?")
        if entry.get("skipped"):
            lines.append(f"  - {stage:<22} (skipped: {entry.get('reason', '?')})")
        elif entry.get("ok"):
            extras = {k: v for k, v in entry.items()
                      if k not in ("stage", "ok") and not isinstance(v, list)}
            lines.append(f"  - {stage:<22} ok    {extras}")
        else:
            lines.append(f"  - {stage:<22} {entry}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D end-to-end pipeline")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run-id", required=True, dest="run_id")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), dest="output_dir")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--multi-view", action="store_true",
                     help="Force multi-view FLUX synth")
    grp.add_argument("--auto-multiview", action="store_true",
                     help="Use automatic multi-view policy (default)")
    grp.add_argument("--single-view", action="store_true",
                     help="Force single-view FLUX synth")
    parser.add_argument("--force", action="store_true",
                        help="Re-run all stages even when intermediate files exist")
    parser.add_argument("--motion-prompt", default=None, dest="motion_prompt",
                        help="Optional motion description (e.g. 'le perso marche', "
                             "'engrenages tournent'). When provided, runs motion_parser "
                             "+ rigify_autorig at the end of the pipeline.")
    parser.add_argument("--purpose", default="visual_preview",
                        help="ThreeDPurpose hint (visual_preview, character, "
                             "product, game_asset, ...). Routes to DreamGaussian for character.")
    parser.add_argument("--subject-kind", default=None, dest="subject_kind",
                        help="Optional subject kind override (character, creature, "
                             "vehicle, product, ...). Used by router; defaults to extract_kind() result.")
    parser.add_argument("--image", action="append", dest="images", default=[],
                        help="Reference image path (repeatable). >=8 -> photogrammetry; "
                             ">=4 + 'photogrammetry'/'scan' keyword -> photogrammetry.")
    parser.add_argument("--max-precision", action="store_true", dest="max_precision",
                        help="Qualite maximale: TRELLIS.2 1536_cascade avec allocateur "
                             "manage (spill RAM) + passe vision materiaux.")
    parser.add_argument("--dry-run-prompt", action="store_true", dest="dry_run_prompt",
                        help="Build and print the FLUX prompt (extract_kind + "
                             "enhance_flux_prompt + faithful-scene contract) WITHOUT "
                             "running FLUX/Hunyuan3D. Verifies prompt fidelity offline.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    if args.max_precision:
        os.environ.setdefault("AURORA_TRELLIS2_MANAGED", "1")
        os.environ.setdefault("AURORA_TRELLIS2_QUALITY", "1536_cascade")
        os.environ.setdefault("AURORA_VLM_MATERIALS", "1")
        os.environ.setdefault("AURORA_NORMAL_RES", "8192")

    if args.dry_run_prompt:
        preview = dry_run_prompt_preview(
            args.prompt, motion_prompt=args.motion_prompt,
            subject_kind_hint=args.subject_kind,
        )
        if args.pretty:
            fs = preview.get("faithful_scene") or {}
            sys.stdout.write(f"kind:        {preview['kind']} "
                             f"(extracted {preview['extracted_kind']}, "
                             f"alts {preview.get('kind_alternatives')})\n")
            sys.stdout.write(f"compound:    {fs.get('compound')}\n")
            sys.stdout.write(f"identity:    {fs.get('identity')}\n")
            sys.stdout.write(f"families:    {fs.get('families')}\n\n")
            sys.stdout.write("FLUX prompt that the pipeline would send:\n")
            sys.stdout.write(preview["flux_prompt"] + "\n")
        else:
            sys.stdout.write(json.dumps(preview, indent=2, ensure_ascii=True) + "\n")
        return 0

    if args.multi_view:
        mv: bool | None = True
    elif args.auto_multiview:
        mv = None
    elif args.single_view:
        mv = False
    else:
        mv = None  # auto

    result = run_pipeline(
        args.prompt, args.run_id,
        output_dir=Path(args.output_dir),
        multi_view=mv, force=args.force,
        motion_prompt=args.motion_prompt,
        images=args.images or None,
        purpose=args.purpose,
        subject_kind_hint=args.subject_kind,
    )
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
