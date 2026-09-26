#!/usr/bin/env python
"""Aurora 3D end-to-end orchestrator — one command turns a prompt into a
Meshy-grade GLB with full audit trail.

Chain:
   1. Optional pre-route: classify the prompt (subject_kind_extractor) so
      we know whether to use multi-view by default (organic / character /
      creature → multi-view yes; product / generic → single-view to save
      compute).
   2. FLUX synth (single or multi-view) → reference PNG(s).
   3. TRELLIS.2 run on the front view (+ multi-view aux if available).
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
from neural_process import run_neural_process  # noqa: E402
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

# Choix du pipeline renvoyé au moteur de routage de l'interface.
# Le miroir Python (route_test.py) a été retiré : on retombe proprement
# sur le défaut FLUX -> Hunyuan3D quand aucun routeur n'est disponible.
_SCRIPTS_DIR = REPO_ROOT / "application" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
try:
    from route_test import route_pipeline  # noqa: E402
except ImportError:  # routeur absent — l'orchestrateur continue (défaut FLUX)
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
                        subject_kind: str | None = None,
                        objet_isole: bool = False) -> str:
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
    _non_organic_kinds = {"motherboard", "pc_tower", "computer", "product", "vehicle", "gadget", "architecture"}
    is_hardware = bool(re.search(r"\b(motherboard|mainboard|carte\s+m[èe]re|x870e|x670e|x670|z890|z790|b850|b650)\b", out, re.I))
    if (_kind_l in {"character", "creature", "humanoid", "quadruped"} or (_creature_re.search(out) and _kind_l not in _non_organic_kinds and not is_hardware)):
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

    return out


def _a_de_la_couleur(glb: str) -> bool:
    """Un GLB porte-t-il une COULEUR reelle (et pas une metallicRoughness nue) ?

    TRELLIS/`to_glb` peut sortir un mesh dont le seul materiau a une texture
    metallicRoughness sans baseColorTexture ni baseColorFactor: le viewer le
    rend BLANC (mesure 26/09: scene loutre/fusil, saturation 8e-5). Tester la
    simple existence d'une image ou d'un materiau suffit donc a croire un mesh
    blanc "déjà texturé". Ici on exige un albedo exploitable : baseColorTexture
    OU un baseColorFactor nettement non neutre.
    """
    try:
        import json as _json
        import struct as _st
        with open(glb, "rb") as _f:
            _h = _f.read(12)
            if len(_h) < 12 or _h[:4] != b"glTF":
                return True  # doute -> on traite comme couleur
            _lg, _typ = _st.unpack("<II", _f.read(8))
            if _typ != 0x4E4F534A:
                return True
            _doc = _json.loads(_f.read(_lg).decode("utf-8", "replace"))
        for _m in _doc.get("materials", []):
            _pbr = _m.get("pbrMetallicRoughness") or {}
            if _pbr.get("baseColorTexture"):
                return True
            _fct = _pbr.get("baseColorFactor")
            if _fct and len(_fct) >= 3:
                _r, _g, _b = _fct[0], _fct[1], _fct[2]
                if abs(_r - _g) > 0.03 or abs(_g - _b) > 0.03 or max(_r, _g, _b) - min(_r, _g, _b) > 0.03:
                    return True
                if max(_r, _g, _b) < 0.72 or max(_r, _g, _b) > 1.05:
                    return True  # marron/bleu/rouge/gris fonce, pas blanc pur
        return False
    except Exception:  # noqa: BLE001
        return True  # doute -> traiter comme couleur

    # Layer 2 — faithful-scene contract (compound prompts only; no-op otherwise).
    # JAMAIS pour un objet SEUL d'une scene. L'orchestrateur genere une entite
    # a la fois et lui accole l'ambiance de la scene ("eclairage neon vert et
    # cyan sur fond sombre"); le contrat lit cette ambiance comme des elements
    # a rendre et ordonne "ne simplifie pas a un seul sujet". FLUX dessine donc
    # de vrais TUBES NEON a cote du sujet, et la porte compare ensuite un mug
    # 3D seul a une reference mug + deux neons: "ne correspond pas a la
    # demande". Mesure du 27/08: bureau, souris, mug et personnage refuses de
    # cette facon, scene reduite a deux objets. Une sous-generation doit
    # produire UN sujet isole — l'ambiance l'eclaire, elle ne s'y ajoute pas.
    if compose_faithful_prompt is not None and not objet_isole:
        try:
            composed = compose_faithful_prompt(
                out, subject_kind=subject_kind, motion_prompt=motion_prompt,
            )
            if composed.get("applied") and composed.get("prompt"):
                out = composed["prompt"]
        except Exception as exc:  # noqa: BLE001 — never break synth on composer error
            sys.stderr.write(f"[faithful-scene] composer failed: {exc}\n")

    # Layer 3 — ISOLEMENT, pour un objet SEUL d'une scene. L'orchestrateur
    # accole l'ambiance de la scene a chaque entite ("eclairage neon vert et
    # cyan sur fond sombre"); FLUX la prend au mot et dessine de vrais TUBES
    # NEON a cote du sujet. La reference du mug en portait deux — et la porte,
    # comparant un mug 3D seul a cette image, a conclu "ne correspond pas a la
    # demande" (idem bureau, souris, personnage: scene reduite a deux objets
    # le 27/08). L'ambiance doit ECLAIRER le sujet, pas peupler le cadre.
    if objet_isole:
        # L'EXPOSITION compte autant que l'isolement: cette image ne sert pas
        # a faire joli, elle sert a TEXTURER. Une ambiance "fond sombre" rend
        # une reference a 49/255 dont 68% de pixels quasi noirs, et le service
        # en tire un atlas 8K a 1,2/255 — du noir plein, sans un detail
        # (mesure du 27/08 sur la chaise: geometrie parfaite, texture morte,
        # refusee par la porte). La teinte de l'ambiance doit COLORER la
        # lumiere, jamais plonger le sujet dans le noir.
        out = out.rstrip(" .,") + (
            ". UN SEUL objet dans l'image: le sujet decrit, isole et entier, "
            "centre, sur fond uni neutre CLAIR (gris moyen), pleinement "
            "ECLAIRE et bien expose, matiere et couleurs nettement lisibles, "
            "aucune zone bouchee dans le noir. L'eclairage cite (neons, "
            "lumieres) teinte la lumiere mais AUCUNE source lumineuse, aucun "
            "tube, aucun meuble ni accessoire ne doit apparaitre dans le "
            "cadre, et le fond n'est jamais sombre.")
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


def trellis_python() -> str:
    """Interpreteur qui sait REELLEMENT charger TRELLIS.2.

    CAUSE RACINE mesuree le 2026-07-22 (l'app et le CLI ne se comportaient pas
    pareil): l'application lance le pipeline avec le python de ComfyUI, ou
    TRELLIS est INDISPONIBLE ("ImportError: No module named 'flex_gemm'"), alors
    que le venv de l'application le charge parfaitement. Resultat: depuis l'UI,
    TRELLIS etait juge absent -> bascule multivue/Hunyuan -> echecs, pendant que
    les memes commandes en CLI (venv app) marchaient. On resout en pointant
    explicitement l'interpreteur qui possede TRELLIS.
    Surchargeable par AURORA_TRELLIS_PY.
    """
    env_py = os.environ.get("AURORA_TRELLIS_PY")
    if env_py and os.path.isfile(env_py):
        return env_py
    venv_py = REPO_ROOT / "application" / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


_TRELLIS_AVAIL_CACHE: dict = {}


def trellis_is_available() -> bool:
    """Teste la dispo de TRELLIS DANS l'interpreteur qui l'executera (sous-process).

    Un import in-process repondait selon le python COURANT (celui de ComfyUI
    depuis l'app) et donnait donc une reponse fausse pour le sous-process reel.
    """
    py = trellis_python()
    if py in _TRELLIS_AVAIL_CACHE:
        return _TRELLIS_AVAIL_CACHE[py]
    ok = False
    try:
        _dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
        r = subprocess.run(
            [py, "-c",
             "import sys; sys.path.insert(0, %r);"
             "import aurora_trellis_wrapper as t;"
             "print('TRELLIS_OK' if t.is_available() else 'TRELLIS_NO')" % _dir],
            capture_output=True, text=True, timeout=180)
        ok = "TRELLIS_OK" in (r.stdout or "")
    except Exception:  # noqa: BLE001
        ok = False
    _TRELLIS_AVAIL_CACHE[py] = ok
    return ok


def _reexec_under_mem_scope() -> None:
    """Re-execute le pipeline ENTIER sous un plafond memoire cgroup (anti-GEL).

    Cause racine des gels machine (verifiee au journal): PAS un OOM kernel, mais un
    THRASH SWAP — 30 Go de RAM + 71 Go de swap: quand une etape lourde deborde
    (textures 16K ~1 Go/couche, spill GPU->RAM de l'allocateur TRELLIS), le systeme
    part en pagination massive, le bureau gele, et seul un reset dur s'en sort
    (journal qui s'arrete net a 05:17 sans aucun message).

    Fix GENERAL (pas un cache-misere): tout le pipeline + ses sous-process (TRELLIS,
    MV-Adapter, Blender...) tournent dans un scope systemd avec MemoryHigh/MemoryMax
    et MemorySwapMax bornes. Si une etape deborde, ELLE meurt (erreur claire dans
    l'audit) — la machine, elle, ne gele JAMAIS. Overridable par env, opt-out via
    AURORA_MEM_SCOPE_DISABLE=1.
    """
    if os.environ.get("AURORA_MEM_SCOPED") == "1":
        print("PROGRESS:memoire:plafond memoire actif (scope systemd) — le PC ne peut plus geler",
              flush=True)
        return
    if os.environ.get("AURORA_MEM_SCOPE_DISABLE") == "1":
        return
    import shutil as _sh
    if not _sh.which("systemd-run"):
        return
    try:
        _probe = subprocess.run(
            ["systemd-run", "--user", "--scope", "--quiet", "--collect",
             "-p", "MemoryMax=1G", "true"],
            capture_output=True, timeout=15)
        if _probe.returncode != 0:
            return
    except Exception:  # noqa: BLE001
        return
    # Swap BORNE (6G): TRELLIS a besoin de ~25.5G au chargement (mesure OOM
    # kernel) — impossible en RAM pure sur 30G, mais un debordement BREF en swap
    # passe tres bien. Ce qui gele la machine est le CHURN SOUTENU, pas le pic:
    # sans MemoryHigh il n'y a pas de boucle de recyclage, et oomd
    # (ManagedOOMSwap=kill) tue le scope si le swap churne vraiment.
    # PAS de MemoryHigh: l'allocateur TRELLIS managé utilise de la memoire CUDA
    # UNIFIEE, NON-RECUPERABLE par le noyau. Un High force alors un recyclage
    # perpetuel a vide (pression 40-60%, process fige a High pile, pilote GPU
    # bloque -> ecran fige — constate a la boite noire, mort 06:29). Seul le
    # plafond DUR reste: le depasser = OOM-kill NET, pas d'agonie.
    # Dimension mesuree: la geometrie 1536_cascade managee a tenu 25 min sous
    # 26G+6G avant OOM, avec psiIo=0 tout du long (swap = pages froides parquees,
    # PAS de churn). Le pic legitime demande ~28G+quelques G de parking. La
    # protection anti-gel n'est PAS le plafond (il tue le travail legitime) mais
    # la SENTINELLE (_freeze_sentinel): churn IO / RAM epuisee -> abort propre.
    _max = os.environ.get("AURORA_MEM_MAX_GB", "29")
    _swap = os.environ.get("AURORA_MEM_SWAP_MAX_GB", "28")
    os.environ["AURORA_MEM_SCOPED"] = "1"
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp("systemd-run", [
        "systemd-run", "--user", "--scope", "--quiet", "--collect",
        "-p", f"MemoryMax={_max}G",
        "-p", f"MemorySwapMax={_swap}G",
        # PAS de ManagedOOMSwap=kill: mesure du 2026-07-22 19:25 — oomd a tue un run
        # PARFAITEMENT SAIN (pression memoire 0%, pression disque 0%) uniquement
        # parce que le swap atteignait 5.2 Go. Depuis le retrait de la cle USB il ne
        # reste que 8 Go de swap: le declencheur "90% du swap" devient un cheveu sur
        # la gachette pour une charge qui deborde normalement de quelques Go.
        # La vraie borne reste MemoryMax (plafond DUR) + la sentinelle (io/memoire/
        # vram/nvme), qui elles jugent la DETRESSE et pas le simple volume.
        sys.executable, *sys.argv,
    ])


def _freeze_sentinel() -> None:
    """Sentinelle anti-gel INTEGREE: surveille la pression IO et la RAM.

    Signature d'un gel imminent (mesuree sur 4 gels reels): pression IO/memoire
    SOUTENUE + RAM epuisee -> le bureau se fige avant que quiconque reagisse.
    Signature d'un run sain (mesuree aussi): psiIo ~0 meme avec 8G en swap
    (pages froides parquees). La sentinelle tue donc le pipeline PROPREMENT
    (SIGTERM puis exit) si: psi io 'full' avg10 > 45 sur 3 mesures consecutives,
    ou MemAvailable < 800 Mo sur 3 mesures. Toujours active, cout nul.
    Desactivable: AURORA_FREEZE_SENTINEL=0.
    """
    if os.environ.get("AURORA_FREEZE_SENTINEL", "1") != "1":
        return
    import signal
    import threading

    def _watch() -> None:
        bad_io = 0
        bad_mem = 0
        bad_ram = 0
        bad_swap = 0
        prev_pswpin = -1.0
        prev_pswpin_t = 0.0
        bad_vram = 0
        bad_nvme = 0
        while True:
            time.sleep(10)
            try:
                with open("/proc/pressure/io", "r", encoding="utf-8") as fh:
                    _full = [ln for ln in fh if ln.startswith("full")]
                io_avg = float(_full[0].split("avg10=")[1].split()[0]) if _full else 0.0
                # Pression MEMOIRE 'full': l'agonie fatale mesuree (94% pendant
                # 9 min, mort 12:43) avait psiIo BAS (swap NVMe rapide) et RAM
                # libre >800M (tout partait en swap): seuls les stalls memoire
                # la voyaient. C'est LE signal du sur-engagement (ex: Ollama
                # 17G + FLUX2 25G sur 30G).
                with open("/proc/pressure/memory", "r", encoding="utf-8") as fh:
                    _fullm = [ln for ln in fh if ln.startswith("full")]
                mem_avg = float(_fullm[0].split("avg10=")[1].split()[0]) if _fullm else 0.0
                with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                    _ma = [ln for ln in fh if ln.startswith("MemAvailable")]
                avail_mb = int(_ma[0].split()[1]) // 1024 if _ma else 99999
            except Exception:  # noqa: BLE001
                continue
            # VRAM: seuil 15900 (et non 15200). nvidia-smi lit le TOTAL GPU
            # (torch + contexte CUDA ~0.5G + bureau/UI ~1G) alors que
            # AURORA_VRAM_FRACTION=0.92 ne borne QUE torch (~15.0G): un bake 8192
            # SAIN atteignait donc 15.2-16.2G et la sentinelle tuait le pipeline
            # AVANT que le ladder to_glb ne retombe a 4096 (faux positif structurel).
            vram_mb = 0
            try:
                _sm = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=8)
                vram_mb = int((_sm.stdout or "0").strip().splitlines()[0])
            except Exception:  # noqa: BLE001
                pass
            # NVMe: le Crucial T705 (Gen5) surchauffe sous ecritures soutenues ->
            # blocage controleur -> root en I/O error -> machine figee (ecran
            # 'Failed to spawn executor: Input/output error' constate). On abandonne
            # AVANT le seuil de blocage (~80°C+): 76°C soutenus = stop propre.
            nvme_c = 0
            try:
                import glob as _glob
                for _h in _glob.glob("/sys/class/hwmon/hwmon*"):
                    try:
                        with open(_h + "/name", "r", encoding="utf-8") as fh:
                            if fh.read().strip() != "nvme":
                                continue
                        with open(_h + "/temp1_input", "r", encoding="utf-8") as fh:
                            nvme_c = max(nvme_c, int(fh.read().strip()) // 1000)
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                pass
            # 31/07: 44-50% d'io pendant le spill GPU->RAM est NORMAL sur
            # cette machine (64 Go de swap); le gel historique etait a >85%.
            bad_io = bad_io + 1 if io_avg > 70.0 else 0
            bad_mem = bad_mem + 1 if mem_avg > 65.0 else 0
            # RAM libre basse SEULE != danger, depuis que le swap est un fichier
            # NVMe de 32 Go (plus de cle USB lente). Mesure 2026-07-22 19:32: le
            # chargement de TRELLIS fait descendre la RAM dispo a 639 Mo avec
            # io=1% et memPsi=0% — le noyau pagine tranquillement sur du rapide,
            # aucun gel. On exige donc RAM basse ET un debut de detresse (pression
            # memoire reelle), tout en gardant un PLANCHER ABSOLU a 250 Mo qui
            # coupe quoi qu'il arrive (lecon du 18:51: ne jamais tout relacher).
            # 31/07: 787 Mo dispo + psi 15% = pic legitime de TRELLIS, pas
            # un gel (run tue a tort a 100%% du sampling). On exige une vraie
            # asphyxie: quasi plus rien de disponible, ou pression memoire
            # soutenue ET forte.
            bad_ram = bad_ram + 1 if (avail_mb < 250
                                      or (avail_mb < 600 and mem_avg > 40.0)) else 0
            # VRAM: nvidia-smi lit le TOTAL GPU (TRELLIS cape a 0.92 + contexte CUDA
            # + bureau/UI). Un bake 8192 SAIN atteint ~15.6-16.2G brievement -> le
            # cap torch force deja l'OOM->ladder 4096, la sentinelle ne doit PAS le
            # doubler. Seuil releve a 15900 (juste sous le 16303 physique) et 3
            # echantillons (30s) pour ne capter QUE la famine reelle soutenue.
            bad_vram = bad_vram + 1 if vram_mb > 15900 else 0
            # NVMe: le T705 Gen5 tourne HOT (72-80C normal en ecriture, throttle
            # interne ~82-84C), d'autant que APST=0 + pcie_aspm=off le maintiennent
            # pleine puissance. 76C etait un faux positif; le vrai risque est 82C+.
            # 30/07: le seuil 82 degC TUAIT les generations lancees depuis
            # l'UI (mesure: "SENTINELLE — nvme=83deg" -> "TRELLIS n'a pas
            # produit de mesh", message trompeur). Or 83 degC n'a rien de
            # critique: un NVMe throttle tout seul vers 80-85 et sa limite
            # d'arret est a 90-95. On ne tire donc qu'a l'approche du VRAI
            # danger, et seulement si la chaleur PERSISTE.
            _nvme_seuil = float(os.environ.get("AURORA_SENTINEL_NVME", "89"))
            bad_nvme = bad_nvme + 1 if nvme_c >= _nvme_seuil else 0
            # SWAP: le gel du 24/07 (Xid 109 CTX SWITCH TIMEOUT pendant l'etape
            # materiaux) est survenu avec TOUS les criteres ci-dessus au vert
            # (io 0.04%, psi mem bas, RAM dispo 3.8G, NVMe froid) mais 22 Go en
            # swap et commit 135%: le GPU fait des fautes de pages servies
            # depuis le swap et rate son context-switch -> driver deadlock.
            # On coupe proprement AVANT ce point de non-retour.
            swap_gb = 0.0
            try:
                with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                    _mi = {l.split(":")[0]: l.split()[1] for l in fh if ":" in l}
                swap_gb = (float(_mi.get("SwapTotal", 0))
                           - float(_mi.get("SwapFree", 0))) / 1048576.0
            except Exception:  # noqa: BLE001
                pass
            # 31/07: 15 Go de swap occupe n'a rien d'anormal avec 64 Go —
            # seuil recale sur la nouvelle taille.
            _swap_seuil = float(os.environ.get("AURORA_SENTINEL_SWAP_GB", "40"))
            # LE VRAI SIGNAL EST LA RELECTURE DEPUIS LE SWAP (pswpin), pas le
            # niveau ni la croissance. 2e sortie reelle (Pikachu, 24/07 13h):
            # swap 6->22,7 Go pendant le CHARGEMENT TRELLIS = eviction SAINE
            # (le systeme sort du swap l'encodeur Mistral froid de 17 Go pour
            # faire de la place — ca ecrit VERS le swap). Le mode fatal (nuit
            # du 24/07) etait l'inverse: le GPU sert ses pages DEPUIS le swap
            # en continu (Xid 109 apres des minutes de pswpin massif). On ne
            # tire donc que sur une relecture SOUTENUE: pswpin > ~5000 pages/s
            # (~20 Mo/s) sur 5 echantillons (~50 s), avec un swap deja gros.
            pswpin_rate = 0.0
            try:
                with open("/proc/vmstat", "r", encoding="utf-8") as fh:
                    _vm = dict(l.split() for l in fh if l.startswith("pswp"))
                _pin = float(_vm.get("pswpin", 0))
                _now_t = time.time()
                if prev_pswpin >= 0:
                    _dt = max(_now_t - prev_pswpin_t, 1e-3)
                    pswpin_rate = (_pin - prev_pswpin) / _dt
                prev_pswpin, prev_pswpin_t = _pin, _now_t
            except Exception:  # noqa: BLE001
                pass
            _pin_seuil = float(os.environ.get("AURORA_SENTINEL_PSWPIN", "5000"))
            # 26/07: la relecture seule a tue un run SAIN (60k p/s = un gros
            # modele qui se RECHARGE depuis 64 Go de swap, psi memoire 7%).
            # Le thrash mortel combine relecture massive ET pression memoire.
            bad_swap = bad_swap + 1 if (swap_gb > _swap_seuil
                                        and pswpin_rate > _pin_seuil
                                        and mem_avg > 25.0) else 0
            if (bad_io >= 3 or bad_mem >= 2 or bad_ram >= 3 or bad_vram >= 3
                    or bad_nvme >= 4 or bad_swap >= 5):
                print("PROGRESS:error:SENTINELLE ANTI-GEL — io=%.0f%% memPsi=%.0f%% "
                      "ram=%dMo vram=%dMo nvme=%d°C swap=%.1fGo relecture=%.0fp/s: "
                      "abandon propre AVANT le gel machine"
                      % (io_avg, mem_avg, avail_mb, vram_mb, nvme_c, swap_gb,
                         pswpin_rate),
                      flush=True)
                sys.stdout.flush()
                # trace lisible par le pipeline ET par l'UI: le motif reel
                try:
                    _mot = ("io_sature" if bad_io >= 3
                            else "pression_memoire" if bad_mem >= 2
                            else "ram_epuisee" if bad_ram >= 3
                            else "vram_saturee" if bad_vram >= 3
                            else "disque_brulant" if bad_nvme >= 4
                            else "churn_swap")
                    Path(os.environ.get("AURORA_SENTINEL_TRACE",
                                        "/tmp/aurora_sentinelle.txt")).write_text(
                        "SENTINELLE motif=%s nvme=%dC io=%.0f%% ram=%dMo\n"
                        % (_mot, nvme_c, io_avg, avail_mb), encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass
                # EMPORTER LES ENFANTS. Tuer seulement le pipeline laissait le
                # sous-processus TRELLIS ORPHELIN avec ses 21,7 Go (constate le
                # 24/07: 38 min de survie apres l'abandon, machine toujours
                # saturee, relance impossible). On termine d'abord toute la
                # descendance, puis soi-meme.
                try:
                    os.system("pkill -TERM -P %d" % os.getpid())
                    time.sleep(4)
                    os.system("pkill -KILL -P %d" % os.getpid())
                except Exception:  # noqa: BLE001
                    pass
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(5)
                os._exit(75)  # noqa: WPS437

    threading.Thread(target=_watch, daemon=True, name="freeze-sentinel").start()


def _interactive_confirm(image_paths: list, title: str, output_dir, run_id: str,
                         tag: str, audit: list, mode: str = "lot") -> dict:
    if os.environ.get("AURORA_REF_CONFIRM") != "1" or not sys.stdin.isatty():
        return {"accepted": True, "reason": "", "timeout": False, "verdict": "oui", "photo": None, "jetees": []}
    req = Path(output_dir) / f"{run_id}_confirm_{tag}_request.json"
    ans = Path(output_dir) / f"{run_id}_confirm_{tag}_answer.json"
    alive = Path(output_dir) / f"{run_id}_confirm_{tag}_alive.json"
    mode = mode or "lot"
    # nonce: le chemin est REUTILISE a chaque nouvelle tentative du meme tag
    # (3 essais photo, 3 essais lot). Sans lui l'UI dedoublonnait sur le chemin
    # et ignorait en silence toutes les demandes apres la premiere.
    nonce = str(time.time_ns())
    try:
        ans.unlink(missing_ok=True)
        alive.unlink(missing_ok=True)
        req.write_text(json.dumps({
            "title": title,
            "images": [str(p) for p in image_paths],
            "answer_path": str(ans),
            "alive_path": str(alive),
            "nonce": nonce,
            "tag": tag,
            "mode": mode,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        audit.append({"stage": f"confirm_{tag}", "ok": False, "error": repr(exc)})
        return {"accepted": True, "reason": "", "timeout": False}
    print(f"PROGRESS:confirm_req:{req}", flush=True)
    _t0 = time.time()
    # Deux horloges. _limit = delai SANS personne devant l'ecran (run non
    # surveille, CLI, bridge): on accepte tacitement pour ne jamais bloquer.
    # _max = garde-fou absolu. Tant que l'UI ecrit son battement de coeur
    # (fenetre ouverte devant l'utilisateur), on N'EXPIRE PAS: c'est lui qui
    # decide, pas le chronometre.
    _limit = float(os.environ.get("AURORA_REF_CONFIRM_TIMEOUT", "600"))
    _max = float(os.environ.get("AURORA_REF_CONFIRM_MAX", "7200"))
    _beat_ttl = 45.0
    _next_ping = 120.0
    while True:
        if ans.is_file():
            try:
                _d = json.loads(ans.read_text(encoding="utf-8"))
                _out = {"accepted": bool(_d.get("accepted")),
                        "photo": str(_d.get("photo") or "").strip() or None,
                        "jetees": _d.get("jetees") or [],
                        "reason": str(_d.get("reason") or "").strip(),
                        "verdict": str(_d.get("verdict") or
                                       ("oui" if _d.get("accepted") else "non")),
                        "choix": _d.get("choix"),
                        "timeout": False}
                audit.append({"stage": f"confirm_{tag}", "accepted": _out["accepted"],
                              "reason": _out["reason"][:160]})
                for _f in (req, ans, alive):
                    try:
                        _f.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        pass
                return _out
            except Exception:  # noqa: BLE001
                # reponse illisible (ecriture en cours ou corrompue): on retente,
                # mais SANS court-circuiter le garde-fou de duree ci-dessous.
                time.sleep(1.0)
        _el = time.time() - _t0
        try:
            _watched = (time.time() - alive.stat().st_mtime) < _beat_ttl
        except OSError:
            _watched = False
        if _el >= _max or (_el >= _limit and not _watched):
            break
        if _el >= _next_ping:
            print("PROGRESS:reference:validation attendue depuis %d s%s"
                  % (int(_el), " (fenetre ouverte)" if _watched else
                     " — sans reponse, acceptation tacite a %d s" % int(_limit)),
                  flush=True)
            _next_ping += 120.0
        time.sleep(2.0)
    audit.append({"stage": f"confirm_{tag}", "accepted": True, "timeout": True,
                  "waited_s": int(time.time() - _t0)})
    for _f in (req, alive):
        try:
            _f.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    return {"accepted": True, "reason": "", "verdict": "oui", "timeout": True}


def _free_gpu_before_shape(audit: list | None = None) -> None:
    """Libere la VRAM des AUTRES process GPU avant le shape+paint TRELLIS.2.

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
    # ATTENDRE que la VRAM soit REELLEMENT rendue avant de charger le modele suivant.
    # Sans ca, un modele lourd (TRELLIS/SDXL/Hunyuan) peut demarrer alors que le
    # precedent n'a pas fini de rendre sa VRAM -> deux charges en meme temps -> GEL.
    # Best-effort: on sonde nvidia-smi, plafonne l'attente, et on n'echoue jamais.
    _vram_wait = float(os.environ.get("AURORA_VRAM_WAIT_S", "20"))
    _vram_floor = int(os.environ.get("AURORA_VRAM_FREE_MB", "3000"))
    _t0 = time.time()
    while time.time() - _t0 < _vram_wait:
        try:
            _q = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                 "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=5)
            _used = int((_q.stdout or "0").strip().splitlines()[0])
            if _used <= _vram_floor:
                break
        except Exception:  # noqa: BLE001
            break
        time.sleep(2)
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


def run_motion_bake(rescued_mesh: Path, motion_prompt: str, run_id: str,
                    output_dir: Path, subject_kind: str = "") -> dict:
    """Optional last stage: parse motion_prompt, run rigify_autorig with the
    parsed JSON to get an animated GLB. Falls back to None if motion parser
    can't extract anything (returns null)."""
    import subprocess
    # `audit` propre a cette etape : la branche eau y ecrivait alors qu'`audit` n'existe
    # que dans main() -> NameError avale (try/except) qui FAISAIT ECHOUER TOUTE
    # l'animation d'eau en silence. Local ici = la branche eau s'execute vraiment.
    audit: list = []
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

    # EAU PRIORITAIRE sur le parseur de mouvement : des mots d'eau comme "ondule",
    # "coule", "ruisselle" matchent A TORT des presets de creature (ex: creature.slither)
    # et envoient l'eau vers le RIGGING (qui echoue). Des qu'un NOM d'eau explicite est
    # present, on force le chemin d'animation d'eau (sculpted_water_animator + flux).
    _mp_low0 = (motion_prompt or "").lower()
    _water_nouns = ("eau", " water", "cascade", "fontaine", "bassin", "riviere",
                    "rivière", "ruisseau", "ruisselle", "mer ", "lac", "ocean",
                    "océan", "vague", "aquatique", "flaque", "etang", "étang",
                    "torrent", "flot", "jet d'eau")
    if any(n in _mp_low0 for n in _water_nouns):
        if parsed and parsed != "null":
            print("PROGRESS:animation:sujet d'eau detecte — routage vers l'animateur d'eau "
                  "(le parseur de mouvement avait matche un preset a tort)", flush=True)
        parsed = "null"

    # PLAN DE SCENE (27/07): le classifieur ne rendait QU'UNE categorie pour
    # toute la demande -> un sujet multi-domaine (moulin: eau + engrenages +
    # farine + lanterne + banniere) perdait tout sauf un domaine, en silence.
    # Le routeur decompose en ACTEURS typés par la physique (8 axes enumeres,
    # aucune liste de sujets) et dit, pour chacun, quel solveur et quelle
    # representation glTF employer. Journalise: l'utilisateur voit ce qui a
    # ete compris et ce qui sera produit.
    plan_scene = {}
    try:
        sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
        import domain_router as _dr
        # le routeur juge sur la demande ENTIERE (celle de l'utilisateur),
        # jamais sur le fragment que l'orchestrateur de scene lui transmet.
        _texte_plan = " ".join(x for x in (
            os.environ.get("AURORA_MOTION_ORIGINAL", ""),
            os.environ.get("AURORA_PROMPT_ORIGINAL", ""),
            motion_prompt or "") if x)
        plan_scene = _dr.plan(_texte_plan or motion_prompt, kind=subject_kind)
        audit.append({"stage": "plan_scene", **{k: v for k, v in
                                                plan_scene.items()
                                                if k != "prompt"}})
        if plan_scene.get("acteurs"):
            print("PROGRESS:animation:plan de scene — %d acteur(s), domaines: %s"
                  % (len(plan_scene["acteurs"]),
                     ", ".join(plan_scene.get("domaines") or [])), flush=True)
            for _a in plan_scene["acteurs"]:
                _sup = ", ".join(x["solveur"] for x in
                                 _a.get("solveurs_supplementaires", []))
                print("PROGRESS:animation:  %s : %s/%s -> %s%s"
                      % (_a.get("id"), _a.get("matiere"), _a.get("origine"),
                         _a.get("solveur"),
                         (" + " + _sup) if _sup else ""), flush=True)
            if plan_scene.get("multi_domaine"):
                print("PROGRESS:animation:demande MULTI-DOMAINE — chaque acteur "
                      "part sur son solveur (plus de domaine perdu)", flush=True)
    except Exception as _pse:  # noqa: BLE001
        audit.append({"stage": "plan_scene", "ok": False, "error": repr(_pse)})

    # DOMAINE REEL POUR LE CHOIX DU SQUELETTE. extract_kind() (subject_kind)
    # est du regex PUR sur le prompt: "Happy" (un nom propre, sans mot-cle
    # "chat"/"creature") ne matche rien -> defaut HUMAIN pour un chat aile.
    # plan_scene, lui, a deja tranche correctement ("domaines: creature",
    # confirme au log) — pour un acteur unique, on s'en sert en repli quand
    # subject_kind n'a rien dit de precis.
    _domain_kind = ""
    try:
        _acteurs_ps = plan_scene.get("acteurs") or []
        if len(_acteurs_ps) == 1:
            _domain_kind = str(_acteurs_ps[0].get("famille_metriques") or "").lower()
    except Exception:  # noqa: BLE001
        pass

    # FRISE MULTI-PISTE. "un guerrier qui attaque avec une flamme" contient
    # DEUX demandes: un corps qui bouge et un phenomene physique. Une seule
    # categorie etait retenue pour toute la phrase et la flamme etait perdue.
    # On decoupe d'abord, on saura ensuite quoi produire et sur quel support.
    timeline = {}
    try:
        sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
        from motion_timeline_planner import plan as _plan_timeline
        timeline = _plan_timeline(motion_prompt)
        if timeline.get("tracks"):
            audit.append({"stage": "timeline", **{k: v for k, v in timeline.items()
                                                  if k != "tracks"},
                          "pistes": timeline["tracks"]})
            print("PROGRESS:animation:frise du mouvement — %s"
                  % timeline.get("resume", ""), flush=True)
            for _t in timeline["tracks"]:
                if _t["piste"] != "sujet":
                    print("PROGRESS:animation:  piste %s (%s) de %.1fs a %.1fs : %s"
                          % (_t["piste"], _t["categorie"], _t["t0"], _t["t1"],
                             _t["texte"][:60]), flush=True)
        if timeline.get("composite"):
            print("PROGRESS:animation:demande COMPOSITE — le corps part sur le "
                  "squelette, l'effet sur son propre support", flush=True)
    except Exception as _tle:  # noqa: BLE001
        audit.append({"stage": "timeline", "ok": False, "error": repr(_tle)})

    # MOUVEMENTS NOMMES (trends, danses, memes). "fais le 67" n'est pas un
    # verbe de geste: c'est un NOM. Le resolveur (LLM + Wikipedia, aucune
    # liste en dur) le traduit en description biomecanique precise; cette
    # description remplace le prompt pour la generation. Un nom non resolu
    # echoue EXPLICITEMENT — jamais un geste invente a la place.
    _trend_desc = ""
    import re as _re_t
    _named_rx = _re_t.compile(
        r"\b(?:fais|refais|danse|execute|ex[ée]cute)\s+(?:le|la|l'|un|une)\s*[\w\d]"
        r"|\b(?:trend|tendance|meme|m[eè]me|d[ée]fi|challenge)\b", _re_t.I)
    if os.environ.get("AURORA_TREND", "1") == "1" and (
            (not parsed or parsed == "null")
            or _named_rx.search(motion_prompt or "")):
        try:
            sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
            import motion_trend_resolver as _mtr
            _tr = _mtr.resolve(motion_prompt)
            audit.append({"stage": "trend_resolver",
                          **{k: v for k, v in _tr.items()}})
            if _tr.get("named_move") and _tr.get("description_en"):
                _trend_desc = _tr["description_en"]
                _trend_nom = str(_tr.get("name") or "")
                # duree issue de la RECHERCHE (nb de phases x tempo), pas
                # d'une constante: sans elle, HY-Motion tronque a ~5 s et la
                # sequence complete n'y tient pas.
                _trend_duree = float(_tr.get("duration_s") or 0.0)
                _parsed_avant_trend = parsed   # le prereglage reste le REPLI
                parsed = "null"   # un mouvement nomme tente d'abord la
                                  # generation fidele (sa vraie biomecanique)
                print("PROGRESS:animation:mouvement nomme compris (%s, via %s) "
                      "— generation depuis sa biomecanique"
                      % (_tr.get("name"), _tr.get("source")), flush=True)
            elif _tr.get("named_move"):
                print("PROGRESS:animation:mouvement nomme '%s' NON resolu — "
                      "rien n'est invente a sa place"
                      % _tr.get("name"), flush=True)
        except Exception as _tre:  # noqa: BLE001
            audit.append({"stage": "trend_resolver", "ok": False,
                          "error": repr(_tre)})

    hymotion_bvh = ""
    _parsed_avant_trend = locals().get("_parsed_avant_trend", None)
    # SUJET HUMANOIDE = GENERATION D'ABORD, prereglage en REPLI. Deux raisons
    # verifiees: (1) le rig MIA ignore les prereglages non-locomotion (ils
    # ciblent des os Rigify inexistants -> "exported no glTF animations");
    # (2) une description multi-phases ("s'accroupit, frappe, se releve")
    # ecrasee en punch+jump PERD des phases. Le prereglage reste le repli via
    # _parsed_avant_trend si la generation echoue.
    if (parsed and parsed != "null" and _parsed_avant_trend is None
            and str(subject_kind or "").lower() in
            ("character", "human", "humanoid")):
        _parsed_avant_trend = parsed
        parsed = "null"
        print("PROGRESS:animation:description libre — generation fidele "
              "tentee d'abord (prereglage %s garde en repli)"
              % "matche", flush=True)
    if not parsed or parsed == "null":
        # HY-MOTION AVANT LE REPLI PHYSIQUE. Les 28 prefixages couvrent les
        # gestes NOMMES; tout ce qui est decrit librement ("esquive puis
        # contre-attaque en tournant sur lui-meme") n'y correspond a rien et ne
        # produisait aucun mouvement. HY-Motion genere depuis la description.
        # On ne l'appelle que pour un sujet ANIME: une fontaine ou un ventilateur
        # doivent continuer vers le classifieur physique.
        _hm_low = (motion_prompt or "").lower()
        # Frontieres de mots obligatoires: en sous-chaines, "fauteuil"
        # contient "il " et "meuble" matchait "elle" — un meuble partait en
        # generation de mouvement humain.
        import re as _re_v
        _est_vivant = (str(subject_kind or "").lower() in
                       ("character", "human", "humanoid", "creature", "animal")
                       or bool(_re_v.search(
                           r"\b(homme|femme|personnage|guerrier|guerriere|humain|"
                           r"soldat|danseur|danseuse|enfant|athlete|athl\u00e8te|"
                           r"il|elle|quelqu'un|person|man|woman|warrior|"
                           r"character|he|she|someone)\b", _hm_low)))
        # UN NOM SEUL N'EST PAS UN MOUVEMENT. "Pikachu" declenchait une
        # generation de geste arbitraire (le modele invente ce qu'on ne lui a
        # pas demande). On exige soit un verbe de geste reconnu par la frise
        # (piste corps), soit une tournure d'action ("qui ...", "en train de",
        # "fait", "execute"). Sans cela: repli classifieur -> respiration/idle,
        # jamais un geste invente.
        _a_un_geste = (any(t.get("piste") == "corps"
                           for t in (timeline.get("tracks") or []))
                       or bool(_re_v.search(
                           r"\b(qui|en\s+train|fait|faisant|execute|ex\u00e9cute|"
                           r"effectue|realise|r\u00e9alise|encha[i\u00ee]ne|"
                           r"performing|doing|performs)\b", _hm_low)))
        if not _a_un_geste and _est_vivant:
            print("PROGRESS:animation:aucun geste decrit — pas de mouvement "
                  "invente (respiration/repos par defaut)", flush=True)
        # MOUVEMENT NOMME = D'ABORD LE BVH APPRIS D'UNE VRAIE EXECUTION
        # (video -> pose -> BVH, motion_video_learn; memorise a vie). La
        # generation texte->mouvement IMAGINE un geste plausible, elle ne
        # REPRODUIT pas une choregraphie: la macarena generee etait un
        # balancement quelconque, l'accroupi-frappe-bond a ete lu "ski".
        _nom_appris = str(locals().get("_trend_nom") or "")
        if (_nom_appris and not hymotion_bvh
                and os.environ.get("AURORA_VIDEO_LEARN", "1") == "1"):
            try:
                _vl_py = REPO_ROOT / "application" / ".venv" / "bin" / "python"
                _vl_script = (REPO_ROOT / "application" / "python-services"
                              / "motion_video_learn.py")
                print("PROGRESS:animation:apprentissage du geste depuis une "
                      "vraie execution (video)...", flush=True)
                _vl = subprocess.run(
                    [str(_vl_py), str(_vl_script), "--name", _nom_appris,
                     "--duration", str(locals().get("_trend_duree") or 8.0)],
                    capture_output=True, text=True, timeout=1500, check=False)
                _vlj = json.loads(next(
                    (l for l in reversed((_vl.stdout or "").splitlines())
                     if l.strip().startswith("{")), "{}"))
                audit.append({"stage": "video_learn", **_vlj})
                if (_vlj.get("ok") and _vlj.get("bvh")
                        and os.path.isfile(_vlj["bvh"])):
                    hymotion_bvh = _vlj["bvh"]
                    print("PROGRESS:animation:geste appris d'une vraie "
                          "execution (%s) — retarget direct"
                          % (_vlj.get("source") or "video"), flush=True)
                else:
                    print("PROGRESS:animation:apprentissage video indisponible "
                          "(%s) -> generation" % str(_vlj.get("error"))[:80],
                          flush=True)
            except Exception as _vle:  # noqa: BLE001
                audit.append({"stage": "video_learn", "ok": False,
                              "error": repr(_vle)})
        if ((_est_vivant and _a_un_geste) or _trend_desc) \
                and not hymotion_bvh \
                and os.environ.get("AURORA_HYMOTION", "1") == "1":
            try:
                sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
                import hymotion_generate as _hm
                _ok_hm, _why_hm = _hm.available()
                if _ok_hm:
                    print("PROGRESS:animation:aucun geste connu ne correspond — "
                          "generation libre du mouvement (HY-Motion)...", flush=True)
                    # cascade de duree: recherche du geste > frise grammaticale
                    # > defaut court. Jamais une constante qui tronque.
                    _hm_duree = (float(locals().get("_trend_duree") or 0.0)
                                 or float(timeline.get("duree_s") or 0.0) or 4.0)
                    _hmr = _hm.generate(_trend_desc or motion_prompt,
                                        str(Path(output_dir) / f"{run_id}_hymotion"),
                                        duration=_hm_duree)
                    audit.append({"stage": "hymotion", **{k: v for k, v in _hmr.items()
                                                          if k != "files"},
                                  "fichiers": len(_hmr.get("files") or [])})
                    if _hmr.get("ok"):
                        print("PROGRESS:animation:mouvement genere (%d fichier(s), %ss)"
                              % (len(_hmr.get("files") or []),
                                 _hmr.get("elapsed_s")), flush=True)
                        # Le .npz SMPL-X ne sert a rien tel quel: on le convertit
                        # en BVH, le seul format que la chaine de rig sait
                        # reprojeter sur le squelette du sujet.
                        _npz = next((f for f in (_hmr.get("files") or [])
                                     if str(f).endswith(".npz")), None)
                        if _npz:
                            try:
                                # SOUS-PROCESSUS avec l'interpreteur de l'app:
                                # la conversion importe torch/smplx, absents de
                                # l'interpreteur ComfyUI qui execute ce pipeline
                                # quand il est lance depuis l'UI. Un import
                                # direct marchait en CLI et cassait dans l'app —
                                # exactement la divergence deja payee une fois.
                                _venv_py = str(REPO_ROOT / "application" / ".venv" / "bin" / "python")
                                if not os.path.isfile(_venv_py):
                                    _venv_py = sys.executable
                                _bvh_out = str(Path(output_dir) / f"{run_id}_MOTION.bvh")
                                _cvp = subprocess.run(
                                    [_venv_py, str(REPO_ROOT / "application" /
                                                   "python-services" / "hymotion_to_bvh.py"),
                                     "--npz", _npz, "--output", _bvh_out],
                                    capture_output=True, text=True, timeout=900)
                                _cv_line = next((l for l in reversed(
                                    (_cvp.stdout or "").splitlines())
                                    if l.strip().startswith("{")), "{}")
                                _cv = json.loads(_cv_line)
                                audit.append({"stage": "hymotion_to_bvh", **_cv})
                                if _cv.get("ok") and _cv.get("format") == "bvh":
                                    hymotion_bvh = _cv["file"]
                                    print("PROGRESS:animation:mouvement converti "
                                          "(%d images) — retargetage sur le squelette"
                                          % _cv.get("frames", 0), flush=True)
                            except Exception as _cve:  # noqa: BLE001
                                audit.append({"stage": "hymotion_to_bvh",
                                              "ok": False, "error": repr(_cve)})
                    else:
                        print("PROGRESS:animation:generation libre indisponible (%s)"
                              % str(_hmr.get("error"))[:90], flush=True)
                else:
                    audit.append({"stage": "hymotion", "ok": False, "error": _why_hm})
            except Exception as _hme:  # noqa: BLE001
                audit.append({"stage": "hymotion", "ok": False, "error": repr(_hme)})
        # REPLI INTELLIGENT: la generation libre a echoue mais le parseur
        # AVAIT un geste valide ("danse" -> dance_default)? On le reprend au
        # lieu de degrader vers le classifieur — jeter un prereglage qui
        # marchait a livre un Pikachu PARFAITEMENT IMMOBILE (24/07).
        # (repli valable pour TOUT prereglage mis de cote — mouvement nomme OU
        # description libre passee en generation d'abord: exiger _trend_desc
        # laissait la voie libre finir en "motion_parser returned null".)
        if (not hymotion_bvh and _parsed_avant_trend
                and _parsed_avant_trend != "null"):
            parsed = _parsed_avant_trend
            print("PROGRESS:animation:generation libre indisponible -> repli "
                  "sur le geste connu du parseur", flush=True)
    # (re-test: le repli peut avoir RESTAURE un prereglage valide, et un BVH
    # genere en main DOIT partir directement au rig — la branche classifieur
    # detournait le flux vers ses bakers et rendait AVANT le retargetage: la
    # macarena etait generee, convertie... puis jamais appliquee.)
    if (not parsed or parsed == "null") and not hymotion_bvh:
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
        # LE PLAN DE SCENE FAIT AUTORITE (27/07). Une scene (moulin: eau qui
        # entraine la roue qui entraine la meule, farine, lanterne, banniere)
        # a des acteurs INDEPENDANTS mais COUPLES. Le classifieur n'en rendait
        # qu'un seul et les autres disparaissaient. On garde ici l'acteur
        # PRINCIPAL (celui qui porte le sujet) pour la passe de base, et on
        # memorise les acteurs SECONDAIRES pour les passes suivantes.
        _acteurs_plan = list((plan_scene or {}).get("acteurs") or [])
        _acteurs_sec = []
        if _acteurs_plan:
            _ordre = {"mecanisme": 0, "rig_squelette": 0, "rbd": 1,
                      "tissu": 2, "emissif": 3, "houdini_flip": 4,
                      "houdini_grains": 5, "houdini_pyro": 6}
            _acteurs_plan.sort(key=lambda a: _ordre.get(a.get("solveur"), 9))
            _princ = _acteurs_plan[0]
            if _princ.get("categorie_baker"):
                category = _princ["categorie_baker"]
                print("PROGRESS:animation:acteur principal '%s' -> categorie %s"
                      % (_princ.get("id"), category), flush=True)
            _vus = {category}
            for _a in _acteurs_plan[1:]:
                _c = _a.get("categorie_baker")
                if _c and _c not in _vus:
                    _vus.add(_c)
                    _acteurs_sec.append(_a)
                for _sup in _a.get("solveurs_supplementaires", []):
                    _cs = {"emissif": "led_emission",
                           "materiau_anime": "thermal_melt"}.get(_sup.get("solveur"))
                    if _cs and _cs not in _vus:
                        _vus.add(_cs)
                        _acteurs_sec.append({**_a, "categorie_baker": _cs,
                                             "id": _a.get("id", "") + "_emission"})
            if _acteurs_sec:
                print("PROGRESS:animation:%d acteur(s) secondaire(s) a animer: %s"
                      % (len(_acteurs_sec),
                         ", ".join("%s(%s)" % (a.get("id"), a.get("categorie_baker"))
                                   for a in _acteurs_sec)), flush=True)
        # Sur une demande composite, la piste EFFET fait autorite: le
        # classifieur lit la phrase entiere et rendait "creature_organic" pour
        # "un guerrier avec une flamme" — la flamme disparaissait.
        _eff = next((t for t in (timeline.get("tracks") or [])
                     if t.get("piste") == "effet" and t.get("categorie")), None)
        if _eff and timeline.get("composite"):
            print("PROGRESS:animation:effet retenu pour la 2e piste: %s"
                  % _eff["categorie"], flush=True)
            category = _eff["categorie"]
        confidence = float((intent or {}).get("confidence") or 0.0)
        import shutil as _sh
        _mp_low = (motion_prompt or "").lower()
        _wants_water = any(k in _mp_low for k in ("eau", "coule", "cascade", "water",
                            "ruisselle", "ruissel", "bassin", "fontaine", "flot",
                            "riviere", "rivière", "torrent", "onde"))
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

        def _sim_fluide(final_path: Path) -> dict:
            """Simulation FLIP reelle (fluid_sim_baker) sur le GLB final anime.
            Activee par AURORA_FLUID_SIM=1 (pose par --max-precision) quand la
            spec decrit un vrai ecoulement liquide. Echec = non bloquant."""
            if os.environ.get("AURORA_FLUID_SIM") != "1":
                return {}
            # DEUX PORTES, une seule simulation. La spec d'animation ouvrait la
            # porte, mais le classifieur d'intention a sa propre categorie
            # "fluid_flow" qui ne la declenchait JAMAIS: une fontaine reconnue
            # comme telle repartait quand meme sur la surface d'eau procedurale
            # au lieu de la vraie cuisson FLIP. Les deux mènent maintenant ici.
            _par_intention = (isinstance(intent, dict)
                              and intent.get("category") == "fluid_flow")
            if not _par_intention:
                if _spec_out is None:
                    return {}
                if str(_spec_out.get("type_mouvement")) not in (
                        "ecoulement", "chute", "tourbillon", "montee"):
                    return {}
                if float(_spec_out.get("amplitude", 1.0) or 0.0) <= 0.01:
                    return {}
            try:
                from fluid_sim_baker import bake_fluid_sim
                sim_path = output_dir / f"{run_id}_SIM.glb"
                print("PROGRESS:animation:simulation fluide reelle (FLIP Mantaflow) — cuisson physique du jet", flush=True)
                r = bake_fluid_sim(final_path, sim_path,
                                   viscosite=("epais" if str(_spec_out.get("viscosite")) == "epais" else "fluide"))
                try:
                    audit.append({"stage": "fluid_sim", "ok": bool(r.get("ok")),
                                  "info": r.get("info"), "error": r.get("error")})
                except Exception:  # noqa: BLE001
                    pass
                if r.get("ok") and sim_path.is_file():
                    print("PROGRESS:animation:simulation fluide OK — " + str(r.get("info"))[-160:], flush=True)
                    return {"sim_mesh": str(sim_path), "fluid_sim_info": r.get("info")}
                print("PROGRESS:animation:simulation fluide echouee (mouvement sculpte conserve)", flush=True)
            except Exception as _se:  # noqa: BLE001
                try:
                    audit.append({"stage": "fluid_sim", "ok": False, "error": repr(_se)})
                except Exception:  # noqa: BLE001
                    pass
            return {}

        def _animer_acteurs_secondaires(glb_courant: Path) -> dict:
            """Fait bouger CHAQUE acteur restant du plan de scene.

            Une scene (moulin) a des acteurs couples: l'eau entraine la roue
            qui entraine la meule; la lanterne emet; la banniere ondule. Le
            pipeline n'en animait qu'UN. On enchaine ici les bakers, chacun
            sur le resultat du precedent: les animations s'ADDITIONNENT dans
            le meme fichier.
            """
            if not _acteurs_sec or os.environ.get("AURORA_MULTI_ACTEURS", "1") != "1":
                return {}
            faits, rates = [], []
            courant = Path(glb_courant)
            for _i, _a in enumerate(_acteurs_sec):
                _cat = _a.get("categorie_baker")
                _sortie = output_dir / ("%s_acteur%d_%s.glb" % (run_id, _i, _cat))
                print("PROGRESS:animation:acteur %s -> %s (%d/%d)"
                      % (_a.get("id"), _cat, _i + 1, len(_acteurs_sec)), flush=True)
                # VRAI SOLVEUR HOUDINI pour les domaines qu'il fait le mieux
                _hou_dom = {"houdini_flip": "flip", "houdini_grains": "grains",
                            "houdini_pyro": "pyro",
                            "tissu": "vellum"}.get(_a.get("solveur"))
                if _hou_dom and os.environ.get("AURORA_HOUDINI", "1") == "1":
                    try:
                        import houdini_sim as _hs
                        _ok_h, _why_h = _hs.available()
                        if _ok_h:
                            print("PROGRESS:animation:  simulation Houdini (%s)..."
                                  % _hou_dom, flush=True)
                            _hr = _hs.simulate(
                                _hou_dom,
                                str(output_dir / ("%s_sim_%s" % (run_id, _a.get("id")))),
                                duration_s=4.0, fps=24,
                                source_mesh=str(courant), timeout_s=3600)
                            audit.append({"stage": "houdini_%s" % _hou_dom,
                                          "acteur": _a.get("id"), **{
                                              k: v for k, v in _hr.items()
                                              if k != "verification"}})
                            if _hr.get("ok"):
                                # la sequence devient une ANIMATION glTF
                                _glb_sim = None
                                try:
                                    import sim_vers_glb as _svg
                                    _cv = _svg.convertir(
                                        _hr["dossier"],
                                        str(output_dir / ("%s_%s_anim.glb"
                                                          % (run_id, _a.get("id")))),
                                        fps=24, max_particules=4000)
                                    audit.append({"stage": "sim_vers_glb",
                                                  "acteur": _a.get("id"), **_cv})
                                    if _cv.get("ok"):
                                        _glb_sim = _cv["sortie"]
                                        print("PROGRESS:animation:  %s -> animation "
                                              "glTF (%s, %s images)"
                                              % (_a.get("id"), _cv.get("mode"),
                                                 _cv.get("frames")), flush=True)
                                except Exception as _ce:  # noqa: BLE001
                                    audit.append({"stage": "sim_vers_glb",
                                                  "ok": False, "error": repr(_ce)})
                                faits.append({"acteur": _a.get("id"),
                                              "solveur": "houdini_" + _hou_dom,
                                              "frames": _hr.get("frames"),
                                              "glb_anime": _glb_sim,
                                              "dossier": _hr.get("dossier")})
                                print("PROGRESS:animation:  %s simule (%s images Houdini)"
                                      % (_a.get("id"), _hr.get("frames")), flush=True)
                                continue
                            print("PROGRESS:animation:  Houdini %s indisponible (%s) "
                                  "-> baker Blender" % (_hou_dom,
                                                        str(_hr.get("erreur"))[:70]),
                                  flush=True)
                        else:
                            print("PROGRESS:animation:  Houdini absent (%s)" % _why_h,
                                  flush=True)
                    except Exception as _he:  # noqa: BLE001
                        audit.append({"stage": "houdini_%s" % _hou_dom,
                                      "ok": False, "error": repr(_he)})
                try:
                    _int_f = output_dir / ("%s_acteur%d_intent.json" % (run_id, _i))
                    _int_f.write_text(json.dumps({
                        "schema": "aurora.motion-intent.v1",
                        "category": _cat, "confidence": 0.9,
                        "prompt": str(_a.get("texte") or motion_prompt),
                        "params": {}}, ensure_ascii=False), encoding="utf-8")
                    _cmd = [sys.executable, str(baker),
                            "--intent", str(_int_f),
                            "--input", str(courant), "--output", str(_sortie)]
                    _p = subprocess.run(_cmd, capture_output=True, text=True,
                                        timeout=2400, check=False)
                    if _sortie.is_file() and _sortie.stat().st_size > 10000:
                        courant = _sortie
                        faits.append({"acteur": _a.get("id"), "categorie": _cat})
                        print("PROGRESS:animation:  %s anime" % _a.get("id"), flush=True)
                    else:
                        _err = (_p.stderr or _p.stdout or "")[-160:]
                        rates.append({"acteur": _a.get("id"), "categorie": _cat,
                                      "erreur": _err})
                        print("PROGRESS:animation:  %s NON anime (%s)"
                              % (_a.get("id"), _err[:80]), flush=True)
                except Exception as _ae:  # noqa: BLE001
                    rates.append({"acteur": _a.get("id"), "categorie": _cat,
                                  "erreur": repr(_ae)})
            if faits and str(courant) != str(glb_courant):
                try:
                    _sh.copyfile(str(courant), str(glb_courant))
                except Exception:  # noqa: BLE001
                    pass
            # FUSION: les simulations converties (eau, sable, fumee, tissu)
            # rejoignent le LIVRABLE. Sans cette etape l'utilisateur recevait
            # un moulin sans son eau: chaque sim restait dans son coin.
            _glbs_act = [f.get("glb_anime") for f in faits if f.get("glb_anime")]
            if _glbs_act:
                try:
                    import fusion_acteurs as _fa
                    _fus = output_dir / ("%s_scene_complete.glb" % run_id)
                    _fr = _fa.fusionner(str(glb_courant), _glbs_act, str(_fus))
                    audit.append({"stage": "fusion_acteurs", **_fr})
                    if _fr.get("ok"):
                        _sh.copyfile(str(_fus), str(glb_courant))
                        print("PROGRESS:animation:scene complete — %d simulation(s) "
                              "fusionnee(s) dans le livrable" % _fr.get("acteurs"),
                              flush=True)
                    else:
                        print("PROGRESS:animation:fusion impossible (%s)"
                              % str(_fr.get("error"))[:80], flush=True)
                except Exception as _fe:  # noqa: BLE001
                    audit.append({"stage": "fusion_acteurs", "ok": False,
                                  "error": repr(_fe)})
            audit.append({"stage": "acteurs_secondaires",
                          "animes": faits, "echecs": rates})
            return {"acteurs_animes": faits, "acteurs_echoues": rates}

        if water_info and not _wants_gas:
            _sh.move(str(gas_input), str(rigged_path))
            _sec = _animer_acteurs_secondaires(rigged_path)
            return {"ok": True, "rigged_mesh": str(rigged_path), **_sec,
                    "motion_intent": "fluid_flow_sculpte",
                    "water_info": water_info,
                    "motion_spec": _spec_out,
                    **_sim_fluide(rigged_path),
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
                        **(_sim_fluide(rigged_path) if water_info else {}),
                        "size_bytes": rigged_path.stat().st_size}
            if water_info:
                _sh.move(str(gas_input), str(rigged_path))
                return {"ok": True, "rigged_mesh": str(rigged_path),
                        "motion_intent": "fluid_flow_sculpte",
                        "water_info": water_info,
                        "note": f"gaz echoue ({(bres.get('error') or 'sans sortie')[:120]}), eau conservee",
                        **_sim_fluide(rigged_path),
                        "size_bytes": rigged_path.stat().st_size}
            return {"ok": False,
                    "error": f"intent bake failed ({category}): {bres.get('error') or bres.get('raw') or 'sans sortie'}",
                    "motion_intent": category, "motion_prompt": motion_prompt}
        return {"ok": False, "error": "motion_parser returned null (no verb match)",
                "motion_intent": category, "motion_prompt": motion_prompt}
    motion_json_path.write_text(parsed, encoding="utf-8")

    _kind_pour_metarig = (subject_kind or "").lower()
    if (_kind_pour_metarig not in ("quadruped", "creature", "human", "humanoid",
                                    "character") and _domain_kind):
        _kind_pour_metarig = _domain_kind
    metarig_family = "quadruped" if _kind_pour_metarig in ("quadruped", "creature") else "human"

    # PRESET vs SQUELETTE: le parseur de mouvement ignorait le sujet. "le loup
    # marche" rendait character.walk_cycle (preset BIPEDE) alors qu'on batit
    # ici un metarig QUADRUPEDE (loup): ses primitives visent `legs` et `arms`
    # (hand_ik.*), or ce rig n'a ni hand_ik ni upper_arm et nomme ses membres
    # avant front_thigh_fk/front_shin_fk. Resultat mesure: l'animal marchait
    # sur ses pattes ARRIERE, les pattes AVANT figees, sans la moindre erreur.
    # On reparse donc avec la morphologie effective — celle-la meme qui vient
    # de decider le metarig — pour que famille de preset et famille de
    # squelette ne puissent plus diverger.
    if metarig_family == "quadruped":
        _proc_q = subprocess.run(
            [sys.executable, str(parser), "--prompt", motion_prompt,
             "--subject-kind", _kind_pour_metarig],
            capture_output=True, timeout=15, check=False,
        )
        _parsed_q = (_proc_q.stdout or b"").decode("utf-8", errors="replace").strip()
        if _parsed_q and _parsed_q != "null" and _parsed_q != parsed:
            motion_json_path.write_text(_parsed_q, encoding="utf-8")
            parsed = _parsed_q
            try:
                _lbl = json.loads(_parsed_q).get("label", "")
            except Exception:  # noqa: BLE001
                _lbl = ""
            audit.append({"stage": "preset_quadrupede", "kind": _kind_pour_metarig,
                          "label": _lbl})
            print("PROGRESS:animation:sujet quadrupede — presets a quatre pattes "
                  "retenus (%s)" % _lbl, flush=True)

    # MIA (Make-It-Animatable) par DEFAUT sur les humanoides : poids anatomiques premium
    # qui separent bras/torse -> le balancier de bras ne fait plus EXPLOSER la manche
    # (prouve A/B: Rigify DEF+proxy 50k = chemise en ailes; MIA = corps intact, marche
    # credible). Fallback silencieux sur Rigify si l'env conda `mia` n'est pas provisionne
    # (rigify_autorig._mia_available). Non-humanoides = Rigify inchange.
    _rig_cmd = [sys.executable, str(rigify),
                "--input", str(rescued_mesh),
                "--output", str(rigged_path),
                "--motion", str(motion_json_path),
                "--motion-text", str(motion_prompt or ""),
                "--metarig", metarig_family]
    if metarig_family == "human" and os.environ.get("AURORA_MIA_RIG", "1") == "1":
        _rig_cmd.append("--use-mia")
    # BVH genere librement: rigify_autorig sait deja le reprojeter (chaine
    # MakeWalk). Sans ce raccordement, le mouvement etait produit puis JETE.
    if hymotion_bvh and os.path.isfile(hymotion_bvh):
        _rig_cmd += ["--mocap-bvh", hymotion_bvh]
        print("PROGRESS:animation:retargetage du mouvement genere sur le squelette...",
              flush=True)
    proc = subprocess.run(_rig_cmd, capture_output=True, timeout=1200, check=False)
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
        # piege connu: une action d'1 image (pose de repos) compte comme
        # "animation" glTF — exiger une DUREE reelle (max des accesseurs
        # d'entree des samplers), sinon le rig livre une statue.
        _duree = 0.0
        for _an in gltf.animations:
            for _sm in (_an.samplers or []):
                try:
                    _acc = gltf.accessors[_sm.input]
                    if _acc.max:
                        _duree = max(_duree, float(_acc.max[0]))
                except Exception:  # noqa: BLE001
                    continue
        if _duree < 0.2:
            return {
                "ok": False,
                "error": f"animation degeneree ({_duree:.2f}s): pose figee exportee, pas le mouvement",
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

    # COMPOSITE: si la demande contient AUSSI un effet ("attaque AVEC une
    # flamme"), le corps est maintenant rige — on rend le personnage ET l'effet
    # ensemble. C'est la seule facon de les voir reunis: un GLB porte le
    # personnage, pas le feu. Sortie = sequence d'images a cote du GLB.
    _compose = {}
    _eff_tr = next((t for t in (timeline.get("tracks") or [])
                    if t.get("piste") == "effet" and t.get("categorie")), None)
    if (timeline.get("composite") and _eff_tr
            and os.environ.get("AURORA_COMPOSITE", "1") == "1"):
        try:
            import motion_composite as _mc
            _eff_kind = {"smoke_fire": "fire", "fluid_flow": "water",
                         "plasma": "plasma"}.get(_eff_tr["categorie"], "fire")
            _engulf = " en feu" in (motion_prompt or "").lower() or \
                      "couvert" in (motion_prompt or "").lower()
            _cmp = _mc.compose(str(rigged_path), _eff_kind,
                               str(Path(output_dir) / f"{run_id}_COMPOSITE"),
                               engulf=_engulf)
            audit.append({"stage": "composite", **_cmp})
            if _cmp.get("ok"):
                print("PROGRESS:animation:composite rendu — personnage + %s "
                      "(%d images)" % (_eff_kind, _cmp.get("images", 0)),
                      flush=True)
                _compose = {"composite_dir": _cmp.get("dossier"),
                            "composite_images": _cmp.get("images")}
        except Exception as _ce:  # noqa: BLE001
            audit.append({"stage": "composite", "ok": False, "error": repr(_ce)})

    return {
        "ok": True,
        "motion_json_path": str(motion_json_path),
        "rigged_mesh": str(rigged_path),
        "size_bytes": rigged_path.stat().st_size,
        "stdout_tail": rigify_stdout[-600:],
        # l'audit local (trend, hymotion, conversion BVH, spec...) etait
        # collecte puis JETE: les echecs d'etapes intermediaires devenaient
        # invisibles dans le retour. Borne pour ne pas gonfler le JSON.
        "audit_animation": audit[-20:],
        **_compose,
    }


def run_final_acceptance(mesh_path: str | Path, prompt: str, kind: str,
                         motion_prompt: str | None = None) -> dict:
    """Final deterministic gate: texture/silhouette/motion acceptance."""
    try:
        from mesh_acceptance_gate import evaluate_acceptance  # noqa: WPS433
        # STATIQUE-ONLY (26/07): le livrable statique ne danse pas — le volet
        # MOUVEMENT se juge sur le fichier ANIME voisin (*_RIGGED.glb) quand
        # il existe. Sans cela, le statique etait condamne pour "no animation
        # channels" des qu'un mouvement etait demande.
        if motion_prompt:
            try:
                from pygltflib import GLTF2 as _G2
                _g = _G2().load(str(mesh_path))
                _anime = bool(_g.animations)
            except Exception:  # noqa: BLE001
                _anime = True
            if not _anime:
                _rig = next(iter(sorted(
                    Path(mesh_path).parent.glob("*_RIGGED.glb"))), None)
                if _rig is not None and _rig.is_file():
                    _stat = evaluate_acceptance(mesh_path, prompt, kind, None)
                    _mot = evaluate_acceptance(_rig, prompt, kind, motion_prompt)
                    _hf_mot = [h for h in (_mot.get("hard_failures") or [])
                               if any(k in h.lower() for k in
                                      ("motion", "anim", "macarena", "floss",
                                       "dance", "clip"))]
                    verdict = dict(_stat)
                    verdict["motion_du_fichier_anime"] = str(_rig.name)
                    if _hf_mot:
                        verdict["acceptance_ok"] = False
                        verdict["hard_failures"] = (
                            list(_stat.get("hard_failures") or []) + _hf_mot)
                    return verdict
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


def extract_template_params(prompt: str, template: str, run_id: str = "proc", output_dir: Path | None = None) -> dict:
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
        # Check if an official reference already exists in the run output dir
        for cand_ref in [
            output_dir / f"{run_id}_official_ref.png",
            output_dir / f"{run_id}_reference.png",
            output_dir / "x870e_hero_official_ref.png",
        ]:
            if cand_ref.is_file():
                flux_image_path = str(cand_ref)
                break

        if not flux_image_path:
            try:
                from flux_reference_synth import synth as _flux_synth
                flux_run_id = f"{run_id}_pcb"
                flux_ref = output_dir / f"{flux_run_id}_reference.png"
                if not flux_ref.is_file():
                    _enhanced = enhance_flux_prompt(prompt)
                    _topdown_prompt = (
                        _enhanced.rstrip(".,") +
                        ", flat top-down orthographic shot, board only, no fans, "
                        "no peripherals, 4096x4096 reference photo, isolated on "
                        "pure white background, professional studio lighting, "
                        "ultra-sharp focus, no perspective distortion"
                    )
                    _res = _flux_synth(_topdown_prompt, flux_run_id,
                                       output_dir=output_dir,
                                       width=1024, height=1024, steps=20)
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
    params = extract_template_params(prompt, template, run_id=run_id, output_dir=output_dir)

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

        im = Image.open(source_path)
        # ORIENTATION EXIF (31/07, constate: photo de face fournie a 0 deg,
        # recue par TRELLIS inclinee a -90). Les photos de telephone portent
        # leur rotation en metadonnee EXIF; sans transposition, les pixels
        # bruts sont TOURNES. On applique l'orientation AVANT tout le reste.
        try:
            from PIL import ImageOps as _IOps
            im = _IOps.exif_transpose(im)
        except Exception:  # noqa: BLE001
            pass
        im = im.convert("RGBA")
        # ALPHA PRESERVE (30/07, audit): on compositait sur BLANC en RGB des
        # le staging — le fond transparent du .webp utilisateur etait detruit
        # avant meme TRELLIS/MV-Adapter, qui ont justement besoin du RGBA
        # (c'etait la cause racine du preprocess vendor jamais appele). Le
        # PNG garde l'alpha; les etapes qui exigent un fond plein aplatissent
        # ELLES-MEMES, au bon moment.
        im.save(dest)
    except Exception as _pil_exc:
        try:
            shutil.copyfile(source_path, dest)
            print("PROGRESS:reference:photo copiee sans reencodage (%s)"
                  % type(_pil_exc).__name__, flush=True)
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


def _derived_view_defects(face_png: str, view_png: str) -> str:
    """Une vue derivee est-elle exploitable ? Rend "" si oui, sinon la raison.

    MV-Adapter part parfois en vrille (constate: la vue de profil de Pikachu
    reduite a une tache jaune trouee sur fond de bokeh). Ces vues partaient
    telles quelles dans TRELLIS.2 — AUCUN controle n'existait sur ce chemin, le
    seul garde-fou ecrit couvrait la voie FLUX. Trois mesures suffisent et
    restent valables pour n'importe quel sujet:
      - le sujet a fondu ou a explose en taille par rapport a la face;
      - le sujet est parti en miettes (aucune piece dominante);
      - la couleur dominante n'a plus rien a voir avec la face.
    """
    try:
        import numpy as _np
        from PIL import Image as _Image

        def _read(p):
            im = _Image.open(p).convert("RGB")
            a = _np.asarray(im).astype(_np.float32)
            # SUJET = ce qui s'ecarte du FOND, quel qu'il soit. L'ancien
            # critere "non blanc" rejetait a 100% les vues correctes de
            # MV-Adapter (fond gris 128 = zero du VAE, convention du modele).
            # Le fond est estime sur les 4 coins: general (blanc, gris, noir).
            _h, _w = a.shape[:2]
            _c = max(4, min(_h, _w) // 32)
            _coins = _np.concatenate([
                a[:_c, :_c].reshape(-1, 3), a[:_c, -_c:].reshape(-1, 3),
                a[-_c:, :_c].reshape(-1, 3), a[-_c:, -_c:].reshape(-1, 3)])
            _fond = _np.median(_coins, axis=0)
            return a, (_np.abs(a - _fond).sum(axis=2) > 45)

        _fa, _fm = _read(face_png)
        _va, _vm = _read(view_png)
        _fc, _vc = float(_fm.mean()), float(_vm.mean())
        if _vc < 0.01:
            return "vue vide"
        # FOND CHARGE: une vue saine (sujet detoure sur blanc) ne touche
        # presque pas les bords; une vue partie en vrille (mosaique, cadre,
        # bokeh) les remplit. C'est CE critere qui manquait le 24/07: les vues
        # poubelle de Pikachu (cadre noir plein bord) passaient taille/couleur
        # et TRELLIS reconstruisait le cadre en plaque.
        _bords = _np.concatenate([_vm[0, :], _vm[-1, :], _vm[:, 0], _vm[:, -1]])
        if float(_bords.mean()) > 0.10:
            return "fond charge (%d%% des bords sales)" % int(100 * _bords.mean())
        if _fc > 0.01 and not (0.40 <= _vc / _fc <= 2.5):
            return "sujet %d%% de la face" % int(100.0 * _vc / max(_fc, 1e-6))
        try:
            from scipy import ndimage as _ndi
            _lab, _n = _ndi.label(_vm)
            if _n > 1:
                _sz = _ndi.sum(_vm, _lab, range(1, _n + 1))
                if float(_sz.max()) / max(float(_sz.sum()), 1.0) < 0.55:
                    return "sujet en miettes (%d fragments)" % _n
        except Exception:  # noqa: BLE001
            pass
        if _fm.sum() > 0 and _vm.sum() > 0:
            _fmean = _fa[_fm].mean(axis=0)
            _vmean = _va[_vm].mean(axis=0)
            if float(_np.abs(_fmean - _vmean).mean()) > 70.0:
                return "couleurs sans rapport avec la face"
        return ""
    except Exception as _exc:  # noqa: BLE001
        # En cas de doute on ne jette rien — mais on le DIT. Un controle qui
        # s'eteint en silence (numpy absent de l'interpreteur, image illisible)
        # laisse passer exactement ce qu'il devait arreter.
        print("PROGRESS:reference:controle des vues derivees indisponible (%r) — "
              "aucune vue n'est filtree" % (_exc,), flush=True)
        return ""


def _clean_product_photo(img):
    """Isole le sujet sur fond blanc SANS l'amputer.

    Deux pieges corriges (cas constate: la queue de Pikachu disparaissait):
      - ne garder que la PLUS GROSSE composante connexe supprimait toute
        extremite fine que le masque detache du corps (queue, oreille, antenne,
        anse, cable, aile);
      - un seuil alpha dur a 0.5 effacait les bords fins ou semi-transparents.
    On ferme donc le masque pour rattacher ce qui ne tient qu'a quelques pixels,
    et on garde TOUTES les parties significatives (une queue = 1 a 3% du corps),
    en ne jetant que les vraies poussieres (filigrane, eclat de fond).
    """
    try:
        from rembg import remove as _rembg_remove
        import numpy as _np
        from PIL import Image as _Image
        rgba = _rembg_remove(img.convert("RGB"))
        a = _np.asarray(rgba)[:, :, 3].astype(_np.float32) / 255.0
        mask = a > 0.35
        if mask.sum() < 500:
            return img
        try:
            from scipy import ndimage as _ndi
            _r = max(2, int(round(0.006 * max(mask.shape))))
            _k = _np.ones((_r, _r), bool)
            closed = _ndi.binary_closing(mask, structure=_k)
            lab, n = _ndi.label(closed)
            if n > 1:
                sizes = _ndi.sum(closed, lab, range(1, n + 1))
                _big = float(sizes.max())
                _keep = [i + 1 for i, s in enumerate(sizes)
                         if float(s) >= max(0.015 * _big, 150.0)]
                mask = mask & _np.isin(lab, _keep)
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


def _character_visual_desc(name: str) -> tuple[str, bool]:
    """Ask the local LLM for a SHORT visual description of a named subject so we
    can (a) disambiguate the web search and (b) verify a candidate image actually
    shows THAT subject — even when the vision model doesn't recognize the name.
    The LLM knows Goldorak is a giant black/white/red robot; that description
    rejects the wrong 'Goldorak' anime-girl the raw search returns.

    Returns (description, is_real_person). A name shared by a real person AND a
    fictional/game avatar (e.g. a rapper with a famous Fortnite skin) made the LLM
    describe the SKIN instead of the human when asked generically for a
    "character/robot" — real photos of the actual person then failed every
    downstream check because they didn't match a hallucinated costume. Asking
    the LLM to name the domain FIRST forces it to pick one referent.
    """
    try:
        import urllib.request as _url
        model = os.environ.get("AURORA_MOTION_LLM", "devstral:latest")
        q = (f"/no_think\nDescribe the exact canonical physical appearance of '{name}' (person, fictional character, creature, or robot). "
             f"Identify: is this a real living/historical human, or fictional? What is its species/body type, official coat/skin colors, distinctive face, hair, wings or accessories? "
             f"Output STRICT JSON only: "
             f'{{"is_real_person": true|false, "species": "...", "description": "..."}}')
        body = json.dumps({"model": model, "prompt": q, "stream": False,
                           "options": {"temperature": 0}, "keep_alive": 0}).encode()
        req = _url.Request("http://127.0.0.1:11434/api/generate", data=body,
                           headers={"Content-Type": "application/json"})
        with _url.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode()).get("response", "").strip()
        a, b = out.find("{"), out.rfind("}")
        if a >= 0 and b > a:
            d = json.loads(out[a:b + 1])
            desc_val = d.get("description")
            if isinstance(desc_val, dict):
                desc = ", ".join(f"{k}: {v}" for k, v in desc_val.items() if isinstance(v, (str, int, float)))
            else:
                desc = str(desc_val or "").strip()
            species = str(d.get("species") or "").strip()
            if species and species.lower() not in desc.lower():
                desc = f"{species}, {desc}"
            return desc[:160], bool(d.get("is_real_person"))
    except Exception:  # noqa: BLE001
        pass
    return "", False


def _reference_photo_ok(png_path: str, prompt: str, visual_desc: str = "") -> tuple[bool, str, str]:
    try:
        sys.path.insert(0, str(REPO_ROOT / "application" / "python-services"))
        from vlm_judge import ask_vlm
        _desc_clause = ("" if not visual_desc else
                        f" Le sujet demande ressemble a: '{visual_desc}'. Si l'image ne "
                        f"correspond PAS a cette description (mauvais personnage/objet), ok=false.")
        verdict = ask_vlm([png_path],
                          "Photo candidate comme reference pour une reconstruction 3D FIDELE de: '%s'. "
                          "Reponds ok=false (STRICT) si UN SEUL de ces defauts est present, car ils "
                          "degradent la reconstruction: "
                          "(1) le sujet est COUPE/RECADRE - une partie sort du cadre ou touche un bord "
                          "(il faut le sujet ENTIER avec une marge de fond sur les 4 cotes, y compris "
                          "le DESSOUS/l'arriere s'ils devraient etre visibles); "
                          "(2) un filigrane/watermark/logo/texte superpose (meme discret, ex 'Magnific', "
                          "'shutterstock', un site web); "
                          "(3) des GOUTTES d'eau/condensation/reflets brillants parasites (ils se "
                          "reconstruisent en relief/grumeaux); "
                          "(4) fond non neutre, eclairage colore artistique, ou plusieurs objets; "
                          "(5) ce n'est pas EXACTEMENT le sujet demande (variante/fan-art/autre modele); "
                          "(6) rendu ARTISTIQUE ou stylise: aquarelle, peinture, coups de pinceau, "
                          "ECLABOUSSURES/taches, croquis, esquisse, mosaique, sticker decoratif, "
                          "poster avec effets — il faut le rendu OFFICIEL ou photographique PROPRE "
                          "du sujet, jamais une oeuvre d'art derivee (verifie: une aquarelle "
                          "eclaboussee reconstruite = geometrie en miettes). Au MOINDRE doute sur "
                          "le style, ok=false; "
                          "(9) OMBRE PORTEE ou reflet au sol sous le sujet: elle est "
                          "reconstruite comme une MASSE NOIRE collee au modele "
                          "(verifie) — le sujet doit flotter sur un fond uni sans "
                          "ombre projetee, sinon ok=false; "
                          "(8) SILHOUETTE floue: le contour du sujet doit etre NET. "
                          "Une fourrure est acceptee et meme normale (loup, peluche) "
                          "tant que sa masse est lisible; ce qui est refuse, c'est un "
                          "contour perdu dans un halo de meches volantes, un flou de "
                          "bougé ou une profondeur de champ qui mange les bords "
                          "(la reconstruction en fait de la mousse); "
                          "(7) rendu PLAT sans volume: dessin anime en aplats de couleur avec "
                          "contours noirs (cel-shading, artwork 2D officiel de personnage) — la "
                          "reconstruction 3D a besoin d'ombres et de volume; un aplat 3/4 donne "
                          "un blob (verifie). Seul un rendu VOLUMETRIQUE (photo, rendu 3D, "
                          "figurine photographiee) convient; un artwork 2D plat -> ok=false "
                          "(la synthese produira la vue volumetrique). "
                          "Sinon ok=true. Indique aussi l'orientation vue: 'face' (sujet vu de face), "
                          "'trois_quarts' (de biais), 'dos' (arriere), 'profil' (cote)." % prompt
                          + _desc_clause,
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
    # POLARITE: refuser quand on ne peut pas juger. Accepter par defaut a
    # laisse passer une aquarelle eclaboussee qui a ruine la reconstruction
    # entiere; le repli synthese FLUX vaut toujours mieux qu'une reference
    # non jugee.
    return False, "vlm indisponible: refus par prudence", "inconnu"


def _research_additional_view(front_photo: str, view_label: str, prompt: str,
                               output_dir: Path, run_id: str,
                               log=lambda *a: None) -> str | None:
    """Cherche UNE vue supplementaire (dos/cote) du MEME sujet que front_photo
    sur le web, quand l'utilisateur n'a fourni qu'une photo.

    Retire le 30/07 car non valide: le dos venait du web par simple mot-cle
    texte (parfois un autre sujet) et les cotes etaient invente en FLUX
    img2img depuis la meme photo (ailes perdues, queue-patte). Ici chaque
    candidat est verifie PAR VLM (meme sujet demande) ET par comparaison
    directe avec la photo de l'utilisateur (_same_product) — les deux gates
    deja fiables sur la recherche de reference frontale. Sans correspondance
    validee, retourne None et l'appelant garde son repli existant
    (MV-Adapter / mono-vue), rien n'est degrade."""
    script = REPO_ROOT / "application" / "python-services" / "reference_visual_search.py"
    if not script.is_file():
        return None
    try:
        _ident = None
        try:
            from faithful_scene_prompt import _detect_identity as _det_id
            _ident = _det_id(prompt)
        except Exception:  # noqa: BLE001
            _ident = None
        _nm = (_ident or {}).get("name") or prompt
        view_word = "back view" if view_label == "back" else "side profile"
        queries = [f"{_nm} {view_word} photo", f"{_nm} {view_word}"]
        import io as _io2, base64 as _b64_2
        from PIL import Image as _Image2
        seen_urls: set[str] = set()
        for query in queries:
            log(f"PROGRESS:reference:recherche vue {view_label} sur le web: \"{query[:60]}\"")
            try:
                p = subprocess.run([sys.executable, str(script), "--query", query, "--limit", "6"],
                                   capture_output=True, text=True, timeout=70)
                line = next((l for l in reversed((p.stdout or "").splitlines()) if l.strip().startswith("{")), "")
                cands = (json.loads(line).get("candidates") if line else None) or []
            except Exception:  # noqa: BLE001
                continue
            for c in cands:
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
                    img = _Image2.open(_io2.BytesIO(_b64_2.b64decode(dj["base64"]))).convert("RGB")
                    if min(img.size) < 400:
                        continue
                    cand_path = output_dir / f"{run_id}_{view_label}_web_candidate.png"
                    img.save(cand_path)
                    ok_photo, why, _ = _reference_photo_ok(str(cand_path), prompt)
                    if not ok_photo:
                        log(f"PROGRESS:reference:vue {view_label} web rejetee ({why[:60]})")
                        cand_path.unlink(missing_ok=True)
                        continue
                    if not _same_product(front_photo, str(cand_path), prompt):
                        log(f"PROGRESS:reference:vue {view_label} web ecartee "
                            "(sujet different de votre photo)")
                        cand_path.unlink(missing_ok=True)
                        continue
                    log(f"PROGRESS:reference:vue {view_label} trouvee sur le web "
                        "et validee contre votre photo")
                    return str(cand_path)
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass
    return None


def _same_product(path_a: str, path_b: str, prompt: str) -> bool:
    """Porte a DEUX etages. Mesure (repetee, meme apres renforcement du
    prompt): un humain qui saute, vu de dos, valide comme "meme sujet" qu'un
    chat aile bleu — PIRE, la MEME image envoyee deux fois recoit deux
    categories differentes du VLM ("humain" puis "animal_reel", verifie sur
    qwen3-vl:8b ET :30b). La comparaison multi-images d'un VLM local n'est
    PAS fiable ici, quelle que soit la taille du modele: on verifie D'ABORD
    au CHIFFRE (cosinus CLIP, deja utilise comme porte de coherence ailleurs
    dans ce fichier — jamais confus entre deux images), puis on exige une
    MAJORITE (2/3) sur la comparaison VLM fine comme second avis, jamais un
    seul appel."""
    try:
        import subprocess as _sp_prod
        _sim_r = _sp_prod.run(
            [sys.executable, str(Path(__file__).parent / "auto_tag_images.py"),
             "--similarity-ref", path_a, "--images", path_b],
            capture_output=True, text=True, timeout=90)
        for _l in reversed((_sim_r.stdout or "").splitlines()):
            if _l.strip().startswith("{"):
                _sj = json.loads(_l)
                if _sj.get("ok") and _sj.get("cosinus"):
                    _cos = float(_sj["cosinus"][0])
                    if _cos < float(os.environ.get("AURORA_SAME_PRODUCT_COS", "0.75")):
                        return False
                break
    except Exception:  # noqa: BLE001
        pass
    try:
        from vlm_judge import ask_vlm
        votes = []
        for _ in range(3):
            try:
                verdict = ask_vlm([path_a, path_b],
                                  "Image 1 = photo de l'utilisateur (verite "
                                  "terrain). Image 2 = candidat trouve sur "
                                  "le web pour: '%s'. Ces deux images "
                                  "montrent-elles EXACTEMENT le meme sujet "
                                  "(meme espece/type d'objet, memes "
                                  "attributs visibles — silhouette, "
                                  "couleurs, ailes/membres/formes) ? "
                                  "Reponds false SANS HESITER si l'image 2 "
                                  "montre un sujet different (autre espece, "
                                  "des personnes au lieu d'un personnage/"
                                  "objet, une scene sans rapport, un "
                                  "filigrane/watermark qui couvre l'image) "
                                  "— au moindre doute, false." % prompt,
                                  schema_hint='{"meme_produit": true|false, '
                                              '"raison": "..."}',
                                  timeout=90)
                if isinstance(verdict, dict) and "meme_produit" in verdict:
                    votes.append(bool(verdict["meme_produit"]))
            except Exception:  # noqa: BLE001
                continue
        if len(votes) >= 2:
            return sum(votes) * 2 > len(votes)
    except Exception:  # noqa: BLE001
        pass
    # POLARITE (meme doctrine que _reference_photo_ok juste au-dessus):
    # refuser quand on ne peut pas juger. L'ancien "return True" par defaut
    # a laisse passer un candidat SANS RAPPORT (photo stock de personnes,
    # watermark BIGSTOCK partout) sous charge GPU (timeout probable du VLM
    # pendant un pipeline concurrent) -> injecte tel quel dans TRELLIS comme
    # "vue de dos validee", geometrie detruite. Un candidat non juge doit
    # etre rejete, jamais accepte par defaut.
    return False


def _research_real_reference(prompt: str, out_path, log=lambda *a: None) -> bool:
    """Cherche sur le web une VRAIE photo du sujet et la telecharge -> out_path.
    Utilise reference_visual_search.py (DuckDuckGo/Bing). Best-effort: False si rien d'exploitable."""
    script = REPO_ROOT / "application" / "python-services" / "reference_visual_search.py"
    if not script.is_file():
        return False
    try:
        # Subject-aware queries. A named character (Goldorak, Natsu...) needs
        # official art / a character reference sheet / turnaround (front+back+side
        # of the CANONICAL character), NOT a "product photo" (which returns fan-art
        # or nothing). A generic object needs the WHOLE object isolated (fixes the
        # cropped top-down apple whose bottom came out empty). Products keep the
        # product-photo queries.
        _ident = None
        try:
            from faithful_scene_prompt import _detect_identity as _det_id
            _ident = _det_id(prompt)
        except Exception:  # noqa: BLE001
            pass
        _nm = (_ident or {}).get("name") or prompt
        _is_product = bool(_REAL_BRAND_RE.search(prompt)) if "_REAL_BRAND_RE" in globals() else False
        _is_char = bool(_ident and _ident.get("basis") == "named_identity" and not _is_product)
        # LLM visual description disambiguates the search AND lets the VLM reject a
        # wrong candidate (the raw 'Goldorak' search returns an anime girl; the
        # description 'giant black/white/red robot' rejects it).
        _char_desc, _is_real_person = _character_visual_desc(_nm) if _is_char else ("", False)
        if _char_desc:
            log(f"PROGRESS:reference:description LLM du personnage: \"{_char_desc[:80]}\"")
        # On cherche EN PREMIER les images a fond transparent: le sujet y est
        # deja detoure proprement (entier, queue et extremites comprises), ce
        # qu'aucun detourage automatique ne garantit.
        if _is_char and _is_real_person:
            # Une VRAIE personne n'a pas d'"art officiel"/planche de reference —
            # ces requetes ramenent du fan-art/jeu video (constate: Travis Scott ->
            # skin Fortnite). On cherche des vraies photos deja detourees/isolees.
            front_queries = [
                f"{_nm} png transparent background isolated cutout",
                f"{_nm} portrait photo white background studio",
                f"{_nm} headshot transparent background",
                f"{_nm} photo",
            ]
        elif _is_char:
            _dq = (" " + _char_desc) if _char_desc else ""
            front_queries = [
                f"{_nm}{_dq} official art full body png transparent background",
                f"{_nm}{_dq} official art full body front view white background",
                f"{_nm} character reference sheet turnaround{_dq}",
                f"{_nm}{_dq} front view",
            ]
        elif _is_product:
            front_queries = [
                f"{prompt} png transparent background product cutout",
                f"{prompt} product photo high resolution white background",
            ]
        else:
            front_queries = [
                f"{prompt} png transparent background isolated cutout",
                f"{prompt} whole object isolated on white background high resolution photo",
                f"{prompt} full product photo studio white background",
            ]
        if _re_mod.search(r"\b(led|rgb|argb|lumineux|neon|strimer|lightstrip)\b", prompt, _re_mod.I):
            front_queries.insert(0, f"{prompt} product photo unlit powered off white leds")
        query_specs = [(q, 2) for q in front_queries]
        if _is_char and _is_real_person:
            query_specs.append((f"{_nm} portrait side profile photo", 1))
        elif _is_char:
            query_specs.append((f"{_nm} character reference sheet back view", 1))
            query_specs.append((f"{_nm} official art side profile", 1))
        else:
            query_specs.append((f"{prompt} back rear view isolated white background", 1))

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
            _cands = _fetch_cands(query)
            # LA DEFINITION DE LA REFERENCE EST LE PLAFOND DE TOUTE LA CHAINE.
            # Les candidats arrivaient dans l'ordre du moteur de recherche: on
            # retenait la premiere acceptable, souvent une vignette (constate:
            # une face de 500x500 -> MV-Adapter delire -> mesh rate). On essaie
            # desormais les plus definies d'abord, sans changer le seuil bas
            # (mieux vaut une petite image juste que pas d'image du tout).
            def _area(c):
                try:
                    return int(c.get("width") or 0) * int(c.get("height") or 0)
                except Exception:  # noqa: BLE001
                    return 0
            if any(_area(c) for c in _cands):
                _cands = sorted(_cands, key=_area, reverse=True)
            _cands = _cands[:8]
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
                    # FOND TRANSPARENT D'ORIGINE = decoupe deja faite a la main,
                    # la meilleure source qui soit: aucun detourage automatique
                    # ne fera mieux et ne risquera d'amputer une extremite.
                    _orig_cutout = False
                    if img.mode != "RGB":
                        img = img.convert("RGBA")
                        _al = img.split()[3]
                        _px = float(img.size[0] * img.size[1]) or 1.0
                        _orig_cutout = (sum(_al.histogram()[:16]) / _px) > 0.05
                        _bg = _Image.new("RGB", img.size, (255, 255, 255))
                        _bg.paste(img, mask=_al)
                        img = _bg
                    if min(img.size) < 480:
                        log(f"PROGRESS:reference:photo ignoree (resolution {img.size[0]}x{img.size[1]} < 480)")
                        continue
                    # PORTE DE BORDS PROGRAMMATIQUE (26/07): le VLM laisse
                    # passer des sujets en scene (rue en bokeh validee -> decor
                    # reconstruit DANS le modele, "sujet eclate"). Une
                    # reference de reconstruction a un fond uni: bords sales
                    # -> rejet deterministe, aucune opinion.
                    try:
                        import numpy as _np_b
                        _ab = _np_b.asarray(img.convert("RGB")).astype(_np_b.float32)
                        _mb = _ab.min(axis=2) < 235
                        _bords = _np_b.concatenate(
                            [_mb[0, :], _mb[-1, :], _mb[:, 0], _mb[:, -1]])
                        if float(_bords.mean()) > 0.10:
                            log("PROGRESS:reference:photo ignoree (fond charge: "
                                "%d%% des bords non blancs)" % int(100 * _bords.mean()))
                            continue
                    except Exception:  # noqa: BLE001
                        pass
                    cand = _tmpmod.mktemp(suffix=".png")
                    if _orig_cutout:
                        log("PROGRESS:reference:fond transparent d'origine — decoupe conservee telle quelle")
                    else:
                        img = _clean_product_photo(img)
                    img.save(cand)
                    ok_photo, why, ori = _reference_photo_ok(cand, prompt, visual_desc=_char_desc)
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
        if os.path.dirname(base):
            os.makedirs(os.path.dirname(base), exist_ok=True)
        _sh.move(slots["face"], base)
        vi = 2
        for k in ("dos", "extra"):
            if slots[k]:
                _sh.move(slots[k], f"{stem}_v{vi}.png")
                vi += 1
        return True
    except Exception as _rre:  # noqa: BLE001
        log(f"PROGRESS:reference:erreur copie reference: {_rre!r}")
        return False
    return False


def _emission_demandee(*textes: str) -> tuple[bool, str]:
    """La demande reclame-t-elle des surfaces qui EMETTENT de la lumiere ?

    Rend (oui/non, teintes nommees separees par des virgules pour
    emissive_synth). C'est du vocabulaire de langue, pas une liste de sujets:
    un ecran allume, une enseigne neon, des phares, une lampe ou un ventilateur
    RGB passent tous par les memes mots. Le SUJET n'est jamais devine ici —
    c'est la texture qui decidera de ce qui brille reellement.
    """
    import re as _re_em
    texte = " ".join(t for t in textes if t).lower()
    if not texte:
        return False, ""
    # accents retires: "allumé"/"allume", "éclairé"/"eclaire" s'ecrivent des deux
    # facons dans les demandes reelles.
    for _a, _b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("û", "u")):
        texte = texte.replace(_a, _b)
    _MOTS_EMISSION = (
        r"neon|led\b|leds\b|allum|eclair|retroeclair|retro-eclair|luminescen|"
        r"lumineu|luminos|incandescen|fluorescen|phosphorescen|rougeoy|"
        r"backlit|glow|glowing|lit\b|illuminat|emissive|emitting|"
        r"ecran.{0,12}(allum|actif|on\b)|screen.{0,12}(on\b|lit\b|display)"
    )
    if not _re_em.search(_MOTS_EMISSION, texte):
        return False, ""
    # teintes nommees a proximite: emissive_synth connait des noms anglais.
    _COULEURS = {
        "vert": "green", "verte": "green", "green": "green",
        "cyan": "cyan", "turquoise": "cyan",
        "bleu": "blue", "bleue": "blue", "blue": "blue",
        "rouge": "red", "red": "red",
        "orange": "orange",
        "jaune": "yellow", "yellow": "yellow",
        "violet": "violet", "violette": "violet", "purple": "purple",
        "magenta": "magenta", "rose": "pink", "pink": "pink",
        "blanc": "white", "blanche": "white", "white": "white",
    }
    trouvees = []
    for mot, nom in _COULEURS.items():
        if _re_em.search(r"\b%s\b" % _re_em.escape(mot), texte) and nom not in trouvees:
            trouvees.append(nom)
    # Un ecran allume rend surtout du BLANC: on garde le blanc disponible pour
    # ne pas eteindre un tableau de bord clair. Mais cette regle ne vaut que
    # pour l'objet LUI-MEME: en la jugeant sur la demande entiere, le mot
    # "ecran" de la scene ajoutait le blanc au clavier et a la souris, et le
    # masque happait alors toutes leurs surfaces claires (mesure: 32,9% du
    # clavier, 15,6% de la souris — un retroeclairage ne couvre pas un tiers
    # d'un clavier). Les COULEURS nommees restent lues sur toute la demande
    # (la teinte des neons est une propriete de la scene), le blanc non.
    _texte_objet = (textes[0] or "").lower() if textes else ""
    for _a, _b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("û", "u")):
        _texte_objet = _texte_objet.replace(_a, _b)
    if trouvees and "white" not in trouvees and _re_em.search(
            r"ecran|screen|afficheur|dashboard|tableau de bord|moniteur",
            _texte_objet):
        trouvees.append("white")
    return True, ",".join(trouvees)


def run_pipeline(prompt: str, run_id: str, *,
                 output_dir: Path = DEFAULT_OUTPUT_DIR,
                 multi_view: bool | None = None,
                 motion_prompt: str | None = None,
                 force: bool = False,
                 images: list[str] | None = None,
                 purpose: str = "visual_preview",
                 subject_kind_hint: str | None = None,
                 allow_scene: bool = True,
                 engine: str = "auto",
                 _vlm_retry: bool = False) -> dict:
    if not prompt.strip():
        return {"ok": False, "error": "empty prompt"}
    if not run_id.strip():
        return {"ok": False, "error": "empty run_id"}

    # ISOLATION PAR RUN. L'UI passe deja un dossier propre au run
    # (runPaths.models = .../conversations/<sujet>/<run_id>/models) mais le
    # CLI nu et le tunnel (_ext_3d_worker, bridge_server.py) retombent sur
    # DEFAULT_OUTPUT_DIR — une racine PARTAGEE entre TOUS les runs. Les
    # fichiers intermediaires (prefixes run_id_) coexistaient sans collision,
    # mais la livraison finale (modele/modele_couleurs.glb, reference/face.png
    # — noms FIXES, cf. livraison_organisee.py) d'un run ecrasait celle du
    # run precedent. On isole ICI, a la source, pour que CLI/tunnel/UI
    # produisent tous une arborescence propre sans devoir changer chaque
    # appelant — sans rien casser pour l'UI qui est deja isolee.
    if output_dir.name != "models" and run_id not in output_dir.parts:
        output_dir = output_dir / run_id

    started_at = time.time()
    started_at_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at))
    audit: list[dict] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    required_space = 2 * 1024 ** 3
    available_space = shutil.disk_usage(output_dir).free
    if available_space < required_space:
        return {
            "ok": False, "error": "insufficient disk space for 3D generation",
            "required_bytes": required_space, "available_bytes": available_space,
            "output_dir": str(output_dir), "audit_trail": audit,
        }
    # HYGIENE MEMOIRE DES L'ENTREE (30/07, retour utilisateur: « Ollama n'a
    # pas libere correctement les modeles precedents avant le swap »). La
    # liberation n'existait qu'AVANT TRELLIS: les modeles de la session de
    # chat precedente restaient parques en swap pendant toute la reference.
    # Ici on decharge Ollama immediatement — chaque etape rechargera ce dont
    # elle a besoin, rien ne traine.
    try:
        import urllib.request as _urq
        with _urq.urlopen("http://127.0.0.1:11434/api/ps", timeout=8) as _pr:
            _loaded = json.loads(_pr.read().decode("utf-8")).get("models", [])
        for _lm in _loaded:
            _ur = _urq.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps({"model": _lm.get("name"),
                                 "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with _urq.urlopen(_ur, timeout=30) as _uresp:
                _uresp.read()
        if _loaded:
            print("PROGRESS:memoire:%d modele(s) Ollama liberes en entree de run"
                  % len(_loaded), flush=True)
    except Exception:  # noqa: BLE001
        pass
    # JOURNAL SUR DISQUE. Au gel du 24/07, AUCUNE trace de l'etape en cours
    # n'a survecu (le stdout meurt avec l'app): l'etape n'a pu etre
    # reconstituee que par les dates de fichiers. Chaque ligne est desormais
    # AUSSI ecrite dans journal/pipeline.log, flushee ligne a ligne.
    if os.environ.get("AURORA_LOG_DISQUE", "1") == "1":
        try:
            _jdir = (output_dir.parent if output_dir.name == "models"
                     else output_dir) / "journal"
            _jdir.mkdir(parents=True, exist_ok=True)
            _jf = open(_jdir / "pipeline.log", "a", encoding="utf-8", buffering=1)
            _jf.write("\n===== run %s — %s =====\n" % (run_id, started_at_iso))

            class _Tee:
                def __init__(self, *flux):
                    self._flux = flux

                def write(self, data):
                    for f in self._flux:
                        try:
                            f.write(data)
                        except Exception:  # noqa: BLE001
                            pass
                    return len(data)

                def flush(self):
                    for f in self._flux:
                        try:
                            f.flush()
                        except Exception:  # noqa: BLE001
                            pass

            sys.stdout = _Tee(sys.__stdout__, _jf)
        except Exception:  # noqa: BLE001
            pass

    # SCENE MULTI-OBJETS. "un homme assis sur une chaise" doit produire un homme ET
    # une chaise: sans ce branchement, l'orchestrateur existait mais n'etait appele
    # de NULLE PART (ni pipeline, ni bridge) et le prompt donnait un homme SEUL.
    # `allow_scene=False` coupe la recursion: l'orchestrateur rappelle run_pipeline
    # pour chaque objet, et "un homme" n'est evidemment pas une scene.
    # 30/07 (audit): l'orchestrateur de scene decoupait meme les demandes
    # AVEC photo — le sujet de la photo devenait un fragment textuel et la
    # reference partait en synthese. Une photo FOURNIE PAR L'UTILISATEUR = un
    # seul sujet, la scene ne se decoupe que sur du texte pur.
    #
    # 27/09 (retour Juan: « y a pas de multi-entite ... pas de scene »): cette
    # condition etait aussi appliquee aux references SYNTHETISEES PAR LE
    # PIPELINE LUI-MEME. Or l'UI genere TOUJOURS une image FLUX a partir du
    # texte avant d'appeler le pipeline, puis la passe via --image : depuis
    # l'UI, `images` n'etait donc JAMAIS vide et l'orchestrateur etait
    # permanently saute — toute demande multi-objets partait en objet unique.
    # Le raisonnement de l'audit du 30/07 (une photo = un sujet) ne vaut que
    # pour une photo REELLE ; une image synthetisee ne montre qu'un seul objet
    # alors que le texte en demande plusieurs, donc la decoupe doit se faire.
    # `synthetic_reference` leve donc ce blocage pour cette seule categorie.
    _images_reelles = [im for im in (images or [])
                       if str(im) not in set(os.environ.get(
                           "AURORA_SYNTHETIC_REFERENCES", "").split("::")) - {""}]
    if allow_scene and not _images_reelles and os.environ.get("AURORA_SCENE_ORCH", "1") == "1":
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from scene_orchestrator import orchestrate_scene
            # L'analyse de scene a besoin du LLM. S'il ne repond pas (modele
            # a froid, HTTP 500 faute de RAM), `split_scene_prompt` rend
            # honnetement {"is_scene": False, "error": ...} — mais ce site
            # d'appel ne regardait QUE `is_scene`, et l'echec devenait
            # "objet unique". Paye le 26/08: la scene poste de travail est
            # partie en UN seul sujet TRELLIS, rendant un homme assis dans le
            # vide, sans siege ni bureau. Un echec n'est pas une conclusion:
            # on libere la memoire et on redemande avant de renoncer.
            # L'analyse a besoin d'un modele de langue qui tient en memoire.
            # Lance sur une machine chargee, il rend un 500 et la scene part
            # en objet unique. On fait de la place AVANT de demander.
            _free_gpu_before_shape(audit)
            _sc = orchestrate_scene(prompt, run_id, output_dir)
            if _sc.get("error"):
                print("PROGRESS:scene:analyse indisponible (%s) — liberation "
                      "memoire et 2e tentative" % str(_sc.get("error"))[:80],
                      flush=True)
                _free_gpu_before_shape(audit)
                _sc = orchestrate_scene(prompt, run_id, output_dir)
            if _sc.get("error"):
                audit.append({"stage": "scene_orchestrator", "ok": False,
                              "error": str(_sc.get("error")),
                              "consequence": "scene NON analysee — le sujet part "
                                             "en objet unique, ce n'est PAS un "
                                             "verdict sur le prompt"})
                print("PROGRESS:scene:ATTENTION analyse de scene IMPOSSIBLE (%s) — "
                      "le prompt part en objet unique alors qu'il decrit peut-etre "
                      "plusieurs objets" % str(_sc.get("error"))[:80], flush=True)
            if _sc.get("is_scene"):
                _sc.setdefault("audit_trail", []).append({
                    "stage": "scene_orchestrator", "ok": bool(_sc.get("ok")),
                    "plan": _sc.get("plan"), "upright": _sc.get("upright"),
                })
                _sc["final_mesh"] = _sc.get("scene_glb")
                return _sc
        except Exception as _sce:  # noqa: BLE001
            audit.append({"stage": "scene_orchestrator", "ok": False,
                          "error": repr(_sce)})

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
        _should_procedural = (
            routing.get("pipeline") == "procedural"
            and not _trellis_avail
            and routing.get("procedural_template") not in ("motherboard_layout",)
        )
        if _trellis_avail and routing.get("pipeline") == "procedural" and not _should_procedural:
            audit.append({"stage": "route_override", "ok": True,
                          "note": "TRELLIS.2 dispo -> AI 3D au lieu du procedural (vrai 3D vs planche plate)",
                          "was": routing.get("procedural_template")})
        if _should_procedural and routing.get("procedural_template"):
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
        if trellis_is_available():
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
    if (not _req_imgs_now and not (not force and front_ref.is_file())
            and os.environ.get("AURORA_REFERENCE_RESEARCH", "1") == "1"
            and _should_research_reference(prompt)):
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
    _user_extra_views: list = []
    requested_images = [str(img).strip() for img in (images or []) if str(img).strip()]

    # RECTIFICATION DE LA PHOTO REELLE. Une photo de telephone arrive
    # sous-exposee (mesure sur un selfie: luma 30/255, 68% de l'image sous le
    # seuil de noir, nettete 4.6): TRELLIS reconstruisait alors une texture
    # noire, et aucune etape en aval ne pouvait la rattraper — le plafond est
    # en ENTREE. photo_rectifier corrige l'exposition sur le POINT BLANC
    # mesure (le teint reste celui de la photo, jamais une luminance cible qui
    # eclaircirait une peau mate), eteint le reflet d'ecran sur les lunettes
    # et detoure en gardant les meches. Auto-adaptatif: une photo deja bien
    # exposee ressort inchangee (gain ~1.0). L'original de l'utilisateur n'est
    # jamais modifie — la version rectifiee vit dans le run.
    if requested_images and os.environ.get("AURORA_RECTIFIER", "1") == "1":
        # LIBERER AVANT LE DETOURAGE, pas seulement avant TRELLIS.
        #
        # `_free_gpu_before_shape` n'etait appelee qu'a l'entree de la
        # reconstruction (ligne ~4316). Or le rectifieur charge BiRefNet pour
        # detourer le sujet, et ComfyUI garde ses poids en RAM SYSTEME apres
        # la synthese FLUX qui vient de s'achever — mesure sur le run
        # `juandigits_hero` : ComfyUI tenait 16 365 Mo, la RAM disponible
        # tombait a 2,4 Go, le swap montait a 15,2 Go, et la sentinelle
        # anti-gel coupait proprement le run juste avant le detourage.
        # L'appel a `/free` rend ces 16 Go (mesure : 16 365 -> 769 Mo).
        #
        # La sentinelle a bien fait son travail : ce n'est pas elle qu'il faut
        # desarmer, c'est la pression qu'il faut retirer avant de charger un
        # modele de plus.
        _free_gpu_before_shape(audit)
        _rect_out = []
        for _i, _src in enumerate(requested_images):
            try:
                from photo_rectifier import rectify_photo_for_3d as _rect
                _dst = output_dir / ("%s_photo%d_rectifiee.png" % (run_id, _i))
                _r = _rect(_src, str(_dst), log=lambda m: print(m, flush=True))
                if _r.get("ok") and _dst.is_file():
                    _av = _r.get("mesures_avant", {})
                    _ap = _r.get("mesures_apres", {})
                    audit.append({"stage": "photo_rectifier", "image": _i,
                                  **{k: v for k, v in _r.items()
                                     if k not in ("rgba", "white")}})
                    print("PROGRESS:reference:photo rectifiee — luminosite %s->%s, "
                          "nettete %s->%s%s"
                          % (_av.get("luma_moyenne"), _ap.get("luma_moyenne"),
                             _av.get("nettete"), _ap.get("nettete"),
                             (", reflet de lunettes eteint"
                              if (_r.get("reflets") or {}).get("applique") else "")),
                          flush=True)
                    _rect_out.append(str(_dst))
                else:
                    _rect_out.append(_src)
            except Exception as _re:  # noqa: BLE001
                audit.append({"stage": "photo_rectifier", "ok": False,
                              "image": _i, "error": repr(_re)[:200]})
                _rect_out.append(_src)
        requested_images = _rect_out

    if requested_images:
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

        # 0. DEDOUBLONNAGE PAR CONTENU (31/07, constate: la MEME photo poussée
        # deux fois etait etiquetee face + droite -> TRELLIS fusionnait deux
        # vues identiques et dechirait la geometrie). Deux fichiers au meme
        # contenu = UNE seule vue, quel que soit leur nom.
        try:
            # EMPREINTE PERCEPTUELLE (31/07): le meme visuel re-encode
            # PNG vs JPG a des octets differents — le sha1 laissait passer le
            # doublon (constate: encore un faux « droite »). On compare les
            # PIXELS (16x16 gris, distance de Hamming <= 8 = meme image).
            import numpy as _npdd
            from PIL import Image as _Imdd
            def _ph(_p):
                _im = _Imdd.open(_p).convert("L").resize((16, 16))
                _a = _npdd.asarray(_im, dtype=_npdd.float32)
                return (_a > _a.mean()).flatten()
            _vus_h = []
            _uniq = []
            for _ri in requested_images:
                try:
                    _h = _ph(_ri)
                except Exception:  # noqa: BLE001
                    _uniq.append(_ri)
                    continue
                if not any(int((_h != _x).sum()) <= 8 for _x in _vus_h):
                    _vus_h.append(_h)
                    _uniq.append(_ri)
            if len(_uniq) < len(requested_images):
                print("PROGRESS:reference:%d image(s) identique(s) ignoree(s) "
                      "(meme contenu = une seule vue)"
                      % (len(requested_images) - len(_uniq)), flush=True)
                audit.append({"stage": "input_reference_policy",
                              "doublons_contenu": len(requested_images) - len(_uniq)})
                requested_images = _uniq
        except Exception:  # noqa: BLE001
            pass

        # 1. AUTO-TAGGING via CLIP
        try:
            tag_cmd = [sys.executable, str(Path(__file__).parent / "auto_tag_images.py"), "--images"] + requested_images
            tag_res = subprocess.run(tag_cmd, capture_output=True, text=True, timeout=600)
            tag_data = extract_json(tag_res.stdout)
            tagged_images = tag_data.get("tags", {})
        except Exception:
            # Fallback to simple zipping if tagging fails
            tagged_images = {k: v for k, v in zip(["front", "back", "left", "right"], requested_images)}

        if "front" not in tagged_images and requested_images:
            tagged_images["front"] = requested_images[0] # ensure front exists

        # UNE image = UNE vue, et c'est la FACE. Le tagger classe volontiers
        # une photo unique sous un autre angle ("right" sur un selfie de face
        # legerement tourne); on obtenait alors la MEME image rangee en face ET
        # en cote, puis dupliquee en vue supplementaire pour TRELLIS. Rien ne
        # peut sortir de plus d'une image que ce qu'elle montre.
        if len(requested_images) == 1:
            _ecartees = [k for k in tagged_images if k != "front"]
            if _ecartees:
                audit.append({"stage": "input_reference_policy",
                              "vues_ecartees": _ecartees,
                              "raison": "une seule photo fournie = face uniquement"})
            tagged_images = {"front": requested_images[0]}

        # 2. Photo unique fournie: trois strategies possibles, choisies selon
        # ce que le sujet permet — jamais une vue inventee sans validation.
        # 30/07 (audit historique): le dos venait du web par simple mot-cle
        # texte (parfois un AUTRE sujet) et les cotes etaient invente en FLUX
        # img2img depuis la meme photo (ailes perdues, queue-patte) -> tout
        # avait ete coupe, laissant seulement MV-Adapter/mono-vue. Restaure
        # ici EN VALIDE: une recherche web tentee pour un sujet nommable,
        # chaque candidat verifie par VLM (bon sujet demande) ET compare
        # directement a la photo fournie (_same_product) — si rien ne passe
        # ces deux portes, on retombe exactement sur le comportement precedent
        # (MV-Adapter invente les vues, ou mono-vue si un seul angle suffit).
        if len(requested_images) == 1:
            multi_view = False
            _found_web_view = False
            try:
                from faithful_scene_prompt import _detect_identity as _det_id_sv
                _ident_sv = _det_id_sv(prompt)
            except Exception:  # noqa: BLE001
                _ident_sv = None
            if not _ident_sv:
                # LE TEXTE SEUL RATE LES NOMS COURTS/AMBIGUS: "Happy" lu isole
                # du prompt passe pour l'adjectif, jamais pour le chat de
                # Fairy Tail — mesure sur ce sujet precis (aucune recherche
                # web tentee, aplat 2D jamais volumise par une vraie vue).
                # La PHOTO fournie leve l'ambiguite que le texte seul ne peut
                # pas lever.
                try:
                    from vlm_judge import ask_vlm as _idvlm
                    _idv = _idvlm(
                        [tagged_images["front"]],
                        "Ce sujet est-il un personnage/mascotte/robot FICTIF "
                        "largement reconnaissable (jeu, anime, film, marque) "
                        "ou une personne CELEBRE ? Si oui, nomme-le "
                        "precisement (personnage + oeuvre/franchise). JSON "
                        'strict: {"reconnu": true|false, "nom": "..."}',
                        schema_hint='{"reconnu": true|false, "nom": "..."}')
                    if isinstance(_idv, dict) and _idv.get("reconnu") and _idv.get("nom"):
                        _ident_sv = {"name": str(_idv["nom"])[:80],
                                     "basis": "named_identity"}
                except Exception:  # noqa: BLE001
                    pass
            if os.environ.get("AURORA_WEB_ADDITIONAL_VIEW") == "1" and _ident_sv and _ident_sv.get("basis") == "named_identity":
                _back_found = _research_additional_view(
                    tagged_images["front"], "back", prompt, output_dir, run_id,
                    log=lambda m: print(m, flush=True))
                if _back_found:
                    tagged_images["back"] = _back_found
                    _found_web_view = True
                    try:
                        import shutil as _shwv
                        _v2_dst = output_dir / f"{run_id}_reference_v2.png"
                        _shwv.copyfile(_back_found, _v2_dst)
                        os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "1"
                        _user_extra_views.append(str(_v2_dst))
                        print("PROGRESS:reference:vue dos reelle branchee sur "
                              "la reconstruction (TRELLIS multivue)", flush=True)
                    except Exception:  # noqa: BLE001
                        pass
            audit.append({"stage": "input_reference_policy",
                          "photo_unique": True, "vue_web_trouvee": _found_web_view,
                          "identite_detectee": (_ident_sv or {}).get("name"),
                          "reason": ("vue reelle trouvee et validee sur le web -> TRELLIS multivue"
                                     if _found_web_view else
                                     "reconstruction fidele de la reference fournie (mono-vue / MV-Adapter)")})

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

        # PLUSIEURS images fournies = VRAIES vues -> TRELLIS multivue directement.
        # Regle utilisateur: on REPRODUIT fidelement ce qui est fourni, on ne
        # regenere RIEN (plus il y a d'images, plus c'est precis). Les vues non-face
        # deviennent {run}_reference_v2/_v3/... que le wrapper TRELLIS consomme
        # (extra_views), et la derivation MV-Adapter est SAUTEE (les vraies vues
        # priment sur des vues devinees). 1 seule image = comportement existant:
        # MV-Adapter devine les vues manquantes (lot a valider).
        # UNE seule photo ne peut PAS fournir un second angle. Le tagger CLIP
        # range une image unique sous plusieurs etiquettes (mesure sur un
        # selfie: la MEME photo classee a la fois "front" et "right"), donc
        # `len(staged_views) >= 2` ne prouve rien sur le nombre de vues REELLES:
        # la face repartait en _reference_v2.png et TRELLIS recevait deux fois
        # la meme image comme deux angles — precisement la fusion de vues
        # identiques qui dechire la geometrie (piege deja documente plus haut).
        # On exige donc des SOURCES distinctes, verifiees au contenu.
        _src_face = (staged_views.get("front") or {}).get("source")
        if len(requested_images) >= 2 and len(staged_views) >= 2:
            import shutil as _shcp
            _slot = 2
            _vus_src = {os.path.realpath(_src_face)} if _src_face else set()
            for _v in ("back", "left", "right"):
                _sv = staged_views.get(_v) or {}
                _srcp = _sv.get("path")
                _orig = _sv.get("source")
                if not (_srcp and os.path.isfile(_srcp)):
                    continue
                if _orig and os.path.realpath(_orig) in _vus_src:
                    audit.append({"stage": "user_multiview_input", "vue": _v,
                                  "ignoree": "meme fichier source que la face"})
                    continue
                if _orig:
                    _vus_src.add(os.path.realpath(_orig))
                _dstp = output_dir / f"{run_id}_reference_v{_slot}.png"
                try:
                    _shcp.copyfile(_srcp, str(_dstp))
                    _user_extra_views.append(str(_dstp))
                    _slot += 1
                except Exception:  # noqa: BLE001
                    pass
            if _user_extra_views:
                os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "1"
                audit.append({"stage": "user_multiview_input", "ok": True,
                              "extra_views": len(_user_extra_views),
                              "note": "vraies vues utilisateur -> TRELLIS multivue; "
                                      "MV-Adapter et toute regeneration SAUTES"})

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
            objet_isole=not allow_scene,
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
                            width=1024, height=1408, steps=20)
            else:
                res = synth(flux_prompt, run_id, output_dir=output_dir,
                            width=1216, height=1216, steps=20)
        reference_synth_result = res
        if not res.get("ok") and multi_view and front_ref.is_file() and front_ref.stat().st_size > 50_000:
            # REPLI NON DESTRUCTIF. La synthese multivue echoue des qu'UNE vue
            # derivee diverge (palette/nettete) — alors que la FACE, elle, est
            # bonne et suffit a TRELLIS.2 (qui reconstruit depuis une seule image).
            # Avant, ce cas tuait toute la generation (constate en reel: "back:
            # palette diverges too much from front reference" -> 0 mesh alors que
            # les 4 images etaient produites). On jette les vues divergentes et on
            # continue en single-view au lieu de tout perdre.
            for _bad in (back_ref, left_ref, right_ref):
                try:
                    _bad.unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass
            multi_view = False
            audit.append({"stage": "multiview_degrade_to_single", "ok": True,
                          "reason": str(res.get("error"))[:200],
                          "note": "vues derivees divergentes jetees; la FACE valide "
                                  "suffit a TRELLIS.2 -> on continue au lieu d'echouer"})
            print("PROGRESS:reference:vues derivees incoherentes -> on garde la face "
                  "et on continue en vue unique", flush=True)
            res = {"ok": True, "degraded_to_single_view": True,
                   "error": None, "elapsed_s": res.get("elapsed_s")}
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

        # VERROU PERSONNAGE. Quand la recherche web echoue, on tombe sur FLUX qui
        # INVENTE le personnage SANS aucun controle -> il peut sortir un autre perso
        # (la reference "un peu dans le theme mais pas le bon perso" que tu decris).
        # On valide donc la reference FLUX contre la description du perso, et on
        # REGENERE (seed different, cues renforcees) si elle ne correspond pas.
        _k_lock = (subject_kind_hint or kind or "").lower()
        if (not multi_view and _k_lock in ("character", "humanoid", "creature")
                and _should_research_reference(prompt) and front_ref.is_file()
                and os.environ.get("AURORA_CHARACTER_LOCK", "1") == "1"):
            try:
                _nm_lock = None
                if compose_faithful_prompt is not None:
                    _idl = compose_faithful_prompt(prompt)["analysis"].get("identity") or {}
                    _nm_lock = _idl.get("name")
                _desc_lock, _ = _character_visual_desc(_nm_lock or prompt)
                for _try in range(2):
                    _okc, _whyc, _ = _reference_photo_ok(str(front_ref), prompt,
                                                         visual_desc=_desc_lock)
                    audit.append({"stage": "character_lock_check", "attempt": _try,
                                  "ok": _okc, "why": _whyc[:120]})
                    if _okc:
                        break
                    print("PROGRESS:reference:la reference ne correspond pas au "
                          "personnage (%s) -> regeneration renforcee..." % _whyc[:60],
                          flush=True)
                    _fp2 = "%s, %s, EXACTEMENT ce personnage, personnage officiel" % (
                        flux_prompt, _desc_lock or "")
                    _res2 = synth(_fp2, run_id, output_dir=output_dir,
                                  width=1024, height=1408, steps=20,
                                  seed=(1234 + _try * 911))
                    if not _res2.get("ok"):
                        break
            except Exception as _lce:  # noqa: BLE001
                audit.append({"stage": "character_lock_check", "ok": False,
                              "error": repr(_lce)})

    # VALIDATION UTILISATEUR (vert/rouge) de la reference — dans le VRAI chemin.
    # Couvre la ref FLUX inventee ET la ref recuperee sur le web (le cas "il a
    # choppe un autre personnage du meme nom"). Pas la ref fournie via --image
    # (l'utilisateur l'a choisie lui-meme). Regle: une photo ACCEPTEE est
    # VERROUILLEE telle quelle (jamais retouchee). Un REFUS (motif optionnel,
    # COMPRIS: injecte dans le prompt de regeneration) regenere; 3 refus ->
    # echec propre plutot que 20 min de reconstruction sur un mauvais sujet.
    if (os.environ.get("AURORA_REF_CONFIRM") == "1" and front_ref.is_file()
            and input_reference_result is None and not multi_view and sys.stdin.isatty()):
        # LIBERER LA MEMOIRE AVANT D'ATTENDRE. Pendant que l'utilisateur regarde la
        # photo (minutes), FLUX restait residant dans ComfyUI (~15 Go RAM) -> avec le
        # reste du systeme, 30 Go satures -> thrash swap -> ecran fige/noir (constate
        # au journal, mort 05:55 sans OOM kernel). La ref est deja ecrite: on decharge.
        # Un refus rechargera FLUX (plus lent, mais le PC ne gele jamais).
        _free_gpu_before_shape(audit)
        # OUI / NON / PEUT-ETRE (demande de Juan):
        #   OUI       -> la photo est verrouillee, on enchaine.
        #   NON       -> la refusee est SUPPRIMEE immediatement et on regenere.
        #   PEUT-ETRE -> la photo est mise de cote (essais/) et on regenere.
        # Au bout de 5 tentatives sans OUI: s'il y a des "peut-etre", on les
        # met COTE A COTE et l'utilisateur en CHOISIT une; sinon echec propre.
        _essais_dir = Path(output_dir) / "essais"
        _candidats: list = []
        _dec = {"accepted": True, "verdict": "oui"}
        _MAX_TENTATIVES = 5
        for _cft in range(_MAX_TENTATIVES):
            _dec = _interactive_confirm(
                [front_ref], "Cette reference est-elle le bon sujet ?",
                output_dir, run_id, "front", audit, mode="tri")
            if _dec["accepted"]:
                break
            _verdict = _dec.get("verdict") or "non"
            _fb = _dec["reason"]
            if _verdict == "peutetre":
                try:
                    _essais_dir.mkdir(parents=True, exist_ok=True)
                    _cand = _essais_dir / ("essai_%d.png" % (len(_candidats) + 1))
                    shutil.copy2(str(front_ref), str(_cand))
                    _candidats.append(_cand)
                    print("PROGRESS:reference:mise de cote (peut-etre %d/%d) -> "
                          "nouvelle proposition..." % (len(_candidats),
                                                       _MAX_TENTATIVES),
                          flush=True)
                except Exception as _cpe:  # noqa: BLE001
                    audit.append({"stage": "confirm_front_essai", "ok": False,
                                  "error": repr(_cpe)})
            else:
                # NON: suppression IMMEDIATE de la refusee (elle sera de toute
                # facon remplacee, mais rien d'elle ne doit rester sur disque).
                try:
                    front_ref.unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass
                print("PROGRESS:reference:refusee et supprimee (%s) -> "
                      "regeneration..." % (_fb[:60] or "sans motif"),
                      flush=True)
            if _cft == _MAX_TENTATIVES - 1:
                break
            try:
                _fp_base = flux_prompt  # voie synth: prompt enrichi deja construit
            except NameError:  # voie recherche web: pas encore de prompt FLUX
                _fp_base = enhance_flux_prompt(
                    prompt, motion_prompt=motion_prompt,
                    objet_isole=not allow_scene,
                    subject_kind=subject_kind_hint or kind)
            _fpc = ("%s. %s. EXACTEMENT le sujet demande." % (_fp_base, _fb)
                    if _fb else _fp_base)
            _resc = synth(_fpc, run_id, output_dir=output_dir,
                          width=1024, height=1408, steps=20,
                          seed=(4242 + _cft * 977))
            if not _resc.get("ok"):
                audit.append({"stage": "confirm_front_regen", "ok": False,
                              "error": _resc.get("error")})
                break
        if not _dec["accepted"] and not _candidats:
            # 31/07 (retour Juan: « au bout de la 3e fois d'un non il genere
            # quand meme »): tous les refus epuises, aucune mise de cote ->
            # on N'IMPOSE RIEN. Arret propre avec les motifs donnes.
            audit.append({"stage": "confirm_front", "ok": False,
                          "refus_epuises": True, "dernier_motif": _fb})
            return {"ok": False,
                    "error": "reference refusee %d fois (%s) — generation "
                             "ARRETEE, aucune image ne sera imposee. Reformulez "
                             "la demande ou fournissez une photo."
                             % (_MAX_TENTATIVES, (_fb or "sans motif")[:120]),
                    "audit_trail": audit}
        if not _dec["accepted"] and _candidats:
            # GALERIE: toutes les "peut-etre" cote a cote, l'utilisateur clique
            # celle qu'il retient puis valide.
            _pick = _interactive_confirm(
                _candidats,
                "Aucun oui franc: cliquez la proposition a retenir, puis validez.",
                output_dir, run_id, "front", audit, mode="choix")
            _idx = _pick.get("choix")
            if isinstance(_idx, int) and 0 <= _idx < len(_candidats):
                shutil.copy2(str(_candidats[_idx]), str(front_ref))
                _dec = {"accepted": True, "verdict": "choix"}
                print("PROGRESS:reference:proposition %d retenue" % (_idx + 1),
                      flush=True)
        # nettoyage: les essais non retenus disparaissent
        try:
            if _essais_dir.is_dir():
                shutil.rmtree(_essais_dir)
        except Exception:  # noqa: BLE001
            pass
        if not _dec["accepted"]:
            return {"ok": False,
                    "error": "reference refusee par l'utilisateur "
                             "(%d tentatives)" % _MAX_TENTATIVES,
                    "audit_trail": audit}

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
    # Ces deux temoins n'existaient QUE dans la branche de generation: un
    # maillage REUTILISE (mesh deja present) partait donc plus bas sur un nom
    # non defini. Et surtout, un fichier reutilise est une livraison FINIE —
    # le repasser dans la chaine de reparation ecrite pour un atlas brut la
    # detruit (c'est la lecon deja payee sur les textures de service).
    _tache_service = None
    _texture_deja_finie = False
    if not force and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
        audit.append({"stage": "hunyuan3d", "skipped": True,
                      "mesh_path": str(mesh_path),
                      "reason": "mesh exists; pass --force to regenerate"})
        raw_dense_path = Path(str(mesh_path))
        # un mesh present n'est une texture FINIE que s'il porte VRAIMENT de la
        # couleur (baseColorTexture/factor). Sans verifier, la 1re passe qui a
        # echoue la chaine couleur (albedo manquant, TRELLIS ne sort qu'une
        # metallicRoughness) etait "livree finie", la 2e sautait toute la
        # chaine et revenait sur le mesh brut blanc. Mesure 26/09: loutre/fusil
        # sans aucune baseColorTexture -> blanc dans le viewer.
        try:
            _reel_tex = _a_de_la_couleur(str(mesh_path))
        except Exception:  # noqa: BLE001
            _reel_tex = True  # doute -> on garde l'ancien comportement
        _texture_deja_finie = bool(_reel_tex)
        # On RECHARGE l'identifiant de tache ecrit lors de la generation: il ne
        # decrit pas la texture mais le DROIT de riger et d'animer ce maillage
        # sans le re-televerser. Le perdre transformait une reutilisation en
        # personnage fige.
        try:
            _t = mesh_path.with_suffix(".tache")
            if _t.is_file():
                _tache_service = _t.read_text(encoding="utf-8").strip() or None
                if _tache_service:
                    audit.append({"stage": "tache_service_rechargee",
                                  "tache": _tache_service})
        except OSError:
            pass
        _keep_native = _native_ok(motion_prompt)
        if _keep_native:
            audit.append({"stage": "native_quality", "ok": True,
                          "note": "mesh existant reutilise tel quel: aucune etape destructrice "
                                  "(fidelity/taubin/optimize/normal-bake sautes)"})
    else:
        # === STAGE 2 — GENERATEUR 3D NEURAL MULTI-MOTEURS (Hunyuan3D-2 & TRELLIS.2) ===
        # Selection intelligente selon la nature du sujet:
        # - Hunyuan3D-2 : cartes meres, composants electroniques, hardware, surfaces dures, bas-reliefs, objets complexes, textures PBR
        # - TRELLIS.2   : personnages organiques, creatures, modeles tournants
        # Chaque moteur dispose d'un repli automatique sur l'autre en cas d'echec.
        _shape_ok = False
        _engine_choice = os.environ.get("AURORA_3D_ENGINE", engine or "auto").lower()
        _is_tech_or_planar = any(k in (prompt or "").lower() for k in [
            "motherboard", "carte mere", "carte mère", "pcb", "gpu", "electronic", "circuit",
            "hardware", "component", "chipset", "console", "keyboard", "device", "gadget", "phone",
            "watch", "camera", "avion", "car", "voiture", "moteur", "engine", "machine", "hero", "rog"
        ]) or kind in ("product", "mechanical", "electronics", "vehicle")

        if _engine_choice in ("hunyuanworld", "hunyuanworldmirror"):
            print("PROGRESS:engine:Moteur HunyuanWorldMirror (réplication stricte) demandé.", flush=True)
            _primary_engine = "hunyuan3d"
            _secondary_engine = "trellis"
        elif _engine_choice == "hunyuan3d" or (_engine_choice == "auto" and _is_tech_or_planar):
            _primary_engine = "hunyuan3d"
            _secondary_engine = "trellis"
        else:
            _primary_engine = "trellis"
            _secondary_engine = "hunyuan3d"

        # VOIE PRINCIPALE — le service de reconstruction distant quand il
        # repond, la voie locale sinon. Le basculement est automatique et
        # silencieux pour l'utilisateur: cote interface, c'est Atlas qui
        # construit, quel que soit le chemin emprunte.
        _tache_service = None
        if _engine_choice == "auto" and os.environ.get("AURORA_MESHY", "1") == "1":
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                import meshy_client
                _service = meshy_client.joignable()
            except Exception as _mexc:  # noqa: BLE001
                _service = {"ok": False, "motif": repr(_mexc)}
            if _service.get("ok"):
                print("PROGRESS:shape:Atlas construit la geometrie...", flush=True)
                _dire = lambda m: print("PROGRESS:shape:Atlas — %s" % m, flush=True)
                try:
                    if front_ref.is_file():
                        _msh = meshy_client.depuis_image(str(front_ref), mesh_path,
                                                         progression=_dire)
                    else:
                        _msh = meshy_client.depuis_texte(prompt, mesh_path,
                                                         progression=_dire)
                except Exception as _mexc:  # noqa: BLE001
                    _msh = {"ok": False, "erreur": repr(_mexc)}
                audit.append({"stage": "reconstruction", "voie": "service",
                              "ok": bool(_msh.get("ok")),
                              "error": _msh.get("erreur"),
                              "octets": _msh.get("octets")})
                if _msh.get("ok"):
                    _shape_ok = True
                    # L'identifiant de tache ouvre le rig et l'animation sans
                    # avoir a re-televerser le maillage.
                    _tache_service = _msh.get("tache")
                    # PERSISTE A COTE DU MAILLAGE. Sans cela, un maillage
                    # REUTILISE (regeneration sautee) perdait son identifiant:
                    # la mise en pose s'arretait sur "aucune tache de service —
                    # le personnage reste fige" et le sujet ressortait en
                    # T-pose alors qu'il avait ete rige et assis au passage
                    # precedent (mesure du 27/08, 2e essai de la scene VIZION).
                    if _tache_service:
                        try:
                            mesh_path.with_suffix(".tache").write_text(
                                str(_tache_service), encoding="utf-8")
                        except OSError:
                            pass
                    print("PROGRESS:shape:Atlas a pose la geometrie — %.1f Mo"
                          % (_msh["octets"] / 1048576.0), flush=True)
                else:
                    # Un echec du service n'est pas un echec de la generation:
                    # on le dit et on continue sur la voie locale.
                    print("PROGRESS:shape:Atlas — voie distante indisponible (%s), "
                          "il reprend en local" % str(_msh.get("erreur"))[:80],
                          flush=True)
            else:
                audit.append({"stage": "reconstruction", "voie": "locale",
                              "motif": _service.get("motif")})

        def _run_hunyuan3d_engine(front_ref_path: Path, out_mesh_path: Path, prompt_str: str, audit_list: list, octree_res: int = 512, steps: int = 30) -> dict:
            _hy_dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
            _hy_wrapper = str(Path(_hy_dir) / "aurora_hunyuan_wrapper.py")
            print(f"PROGRESS:shape:Atlas sculpte le volume ({octree_res} res, {steps} passes) puis les matieres...", flush=True)
            _free_gpu_before_shape(audit_list)
            _hy_cmd = [sys.executable, _hy_wrapper, str(front_ref_path), str(out_mesh_path), "--octree", str(octree_res), "--steps", str(steps), "--device", "cuda"]
            _timeout = int(os.environ.get("AURORA_HUNYUAN_TIMEOUT_S", "3600"))
            try:
                _p = subprocess.run(_hy_cmd, capture_output=True, text=True, timeout=_timeout)
                _res = {}
                for _line in reversed((_p.stdout or "").splitlines()):
                    if _line.startswith("AURORA_HUNYUAN_RESULT:"):
                        try:
                            _res = json.loads(_line[len("AURORA_HUNYUAN_RESULT:"):])
                            break
                        except Exception:
                            pass
                if not _res:
                    _res = {"ok": False, "error": (_p.stderr or _p.stdout or "no output")[-400:]}
                return _res
            except Exception as _exc:
                return {"ok": False, "error": f"Hunyuan3D-2 subprocess failed: {_exc!r}"}

        if not _shape_ok and _primary_engine == "hunyuanworld":
            print("PROGRESS:shape:Atlas sculpte le monde en Splats (HunyuanWorld)...", flush=True)
            _free_gpu_before_shape(audit)
            _hw_wrapper = str(REPO_ROOT / "application" / "python-services" / "run_monobloc_world.py")
            _hw_out = str(mesh_path).replace(".glb", ".ply")
            _hw_cmd = [sys.executable, _hw_wrapper, "--input", str(front_ref), "--output", _hw_out]
            try:
                subprocess.run(_hw_cmd, check=True)
                if Path(_hw_out).is_file():
                    _shape_ok = True
                    mesh_path = Path(_hw_out)
                    audit.append({"stage": "hunyuanworld", "ok": True, "mesh_path": str(mesh_path)})
            except Exception as e:
                audit.append({"stage": "hunyuanworld", "ok": False, "error": str(e)})

        if not _shape_ok and _primary_engine == "hunyuanworld":
            print("PROGRESS:shape:Atlas sculpte le monde en Splats (HunyuanWorld)...", flush=True)
            _free_gpu_before_shape(audit)
            _hw_wrapper = str(REPO_ROOT / "application" / "python-services" / "run_monobloc_world.py")
            _hw_out = str(mesh_path).replace(".glb", ".ply")
            _hw_cmd = [sys.executable, _hw_wrapper, "--input", str(front_ref), "--output", _hw_out]
            try:
                subprocess.run(_hw_cmd, check=True)
                if Path(_hw_out).is_file():
                    _shape_ok = True
                    mesh_path = Path(_hw_out)
                    audit.append({"stage": "hunyuanworld", "ok": True, "mesh_path": str(mesh_path)})
            except Exception as e:
                audit.append({"stage": "hunyuanworld", "ok": False, "error": str(e)})

        if not _shape_ok and _primary_engine == "hunyuan3d":
            _hy = _run_hunyuan3d_engine(front_ref, mesh_path, prompt, audit)
            if _hy.get("ok") and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
                _shape_ok = True
                audit.append({"stage": "hunyuan3d", "ok": True, "mesh_path": str(mesh_path),
                              "faces": _hy.get("faces"), "verts": _hy.get("verts"),
                              "elapsed_s": _hy.get("elapsed_s")})
                print(f"PROGRESS:shape:Atlas a pose la geometrie — {_hy.get('faces') or '?'} faces", flush=True)
            else:
                print(f"PROGRESS:shape:Atlas change de methode ({_hy.get('error')})...", flush=True)
                audit.append({"stage": "hunyuan3d", "ok": False, "error": _hy.get("error")})

        _trellis_ok = False
        _trellis_available = False
        if not _shape_ok:
            try:
                _tr_dir = str(REPO_ROOT / "application" / "python-services" / "aurora_hunyuan")
                if _tr_dir not in sys.path:
                    sys.path.insert(0, _tr_dir)
                _trellis_available = trellis_is_available()
                if _trellis_available:
                    _flat_art = False
                    _mv_on = (os.environ.get("AURORA_MVADAPTER_MV", "1") == "1"
                              and multi_view is not False and not _user_extra_views)
                    if _mv_on and front_ref.is_file():
                        try:
                            from vlm_judge import ask_vlm as _avlm
                            _sty = _avlm(
                                [str(front_ref)],
                                "Cette image est-elle un personnage/objet STYLISE "
                                "(cartoon, anime, aplat de couleurs, contours "
                                "dessines) plutot qu'une photo realiste ? Reponds "
                                "JSON: {\"stylise\": true|false}",
                                schema_hint='{"stylise": true|false}')
                            if isinstance(_sty, dict) and _sty.get("stylise") is True:
                                _flat_art = True
                                _mv_on = True
                                print("PROGRESS:reference:aplat 2D detecte -> "
                                      "VOLUMISATION par vues derivees (identite "
                                      "ancree sur la reference pour volume 3D 360°)",
                                      flush=True)
                                audit.append({"stage": "mvadapter_multiview",
                                              "stylise": True, "flat_art": True,
                                              "note": "volumisation MV (aplat 2D)"})
                        except Exception:  # noqa: BLE001
                            pass
                # === ARBRE DE DECISION toutes-poses (01/08, etape 5) ===
                # Des FAITS mesures decident de la route — plus jamais une
                # derivation condamnee d'avance.
                _upright_angle = 0.0
                if _mv_on and front_ref.is_file():
                    try:
                        from pose_analyse import analyser as _pan
                        _pa = _pan(str(front_ref))
                        audit.append({"stage": "arbre_decision", **_pa})
                        if _pa.get("ok"):
                            if (_pa.get("tronque") or _pa.get("plein_cadre")) and not _flat_art:
                                _mv_on = False
                                print("PROGRESS:reference:sujet tronque/plein-cadre "
                                      "-> MONO-VUE (deriver inventerait le hors-champ)",
                                      flush=True)
                            elif _pa.get("portrait_serre_indice") and not _flat_art:
                                try:
                                    from vlm_judge import ask_vlm as _pvlm
                                    _pf = _pvlm([str(front_ref)],
                                                "Est-ce un PORTRAIT SERRE (tete/buste "
                                                "occupant l'essentiel du cadre) ? JSON: "
                                                "{\"portrait_serre\": true|false}",
                                                schema_hint='{"portrait_serre": true|false}')
                                    if isinstance(_pf, dict) and _pf.get("portrait_serre") is True:
                                        _mv_on = False
                                        print("PROGRESS:reference:portrait serre -> "
                                              "MONO-VUE (la derivation plein-pied "
                                              "detruirait le visage)", flush=True)
                                except Exception:  # noqa: BLE001
                                    pass
                            _kind_redressable = (subject_kind_hint or kind or "").lower() in (
                                "character", "creature", "personnage", "body_part")
                            if not _kind_redressable and not _pa.get("pose_canonique"):
                                audit.append({"stage": "arbre_decision",
                                              "note": "objet allonge: axe horizontal = "
                                                      "canonique, aucun redressement"})
                            if (_mv_on and _kind_redressable and not _flat_art
                                    and not _pa.get("pose_canonique")):
                                if _pa.get("pca_stable"):
                                    # REDRESSEMENT 2D REVERSIBLE (etape 6): on
                                    # derive et reconstruit en canonique, la
                                    # rotation inverse sera ecrite dans le GLB.
                                    _upright_angle = float(_pa.get("angle_vertical_deg") or 0.0)
                                    print("PROGRESS:reference:pose inclinee (%.0f deg) "
                                          "-> redressement reversible avant derivation"
                                          % _upright_angle, flush=True)
                                    try:
                                        from PIL import Image as _ImU
                                        _imu = _ImU.open(str(front_ref))
                                        _imu = _imu.rotate(-_upright_angle, expand=True,
                                                           fillcolor=(0, 0, 0, 0) if "A" in _imu.getbands() else None)
                                        _up_ref = output_dir / ("%s_reference_redresse.png" % run_id)
                                        _imu.save(str(_up_ref))
                                        front_ref_derivation = _up_ref
                                    except Exception:  # noqa: BLE001
                                        _upright_angle = 0.0
                                        front_ref_derivation = front_ref
                                else:
                                    # ETAPE 7: proposer de FOURNIR une 2e photo
                                    # (vraie vue > vue devinee), sinon mono-vue.
                                    _mv_on = False
                                    if os.environ.get("AURORA_REF_CONFIRM") == "1":
                                        _d2 = _interactive_confirm(
                                            [str(front_ref)],
                                            "Pose difficile a deriver. Une 2e photo "
                                            "sous un autre angle rendrait le volume "
                                            "exact — joignez-la via le bouton, ou "
                                            "Accepter pour continuer en mono-vue.",
                                            output_dir, run_id, "photo2", audit,
                                            mode="photo")
                                        _p2 = _d2.get("photo")
                                        if _p2 and os.path.isfile(_p2):
                                            _dst2 = output_dir / ("%s_reference_v2.png" % run_id)
                                            try:
                                                from PIL import Image as _I2, ImageOps as _IO2
                                                _im2 = _IO2.exif_transpose(_I2.open(_p2))
                                                _im2.save(str(_dst2))
                                                _user_extra_views.append(str(_dst2))
                                                os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "1"
                                                print("PROGRESS:reference:2e photo recue "
                                                      "-> vraies vues, derivation sautee",
                                                      flush=True)
                                            except Exception:  # noqa: BLE001
                                                pass
                                    if not _user_extra_views:
                                        print("PROGRESS:reference:pose non canonique et "
                                              "axe instable -> MONO-VUE", flush=True)
                    except Exception as _pae:  # noqa: BLE001
                        audit.append({"stage": "arbre_decision", "ok": False,
                                      "error": repr(_pae)})
                if "front_ref_derivation" not in dir():
                    front_ref_derivation = front_ref
                if _mv_on and front_ref.is_file():
                    try:
                        sys.path.insert(0, str(Path(__file__).parent))
                        import mvadapter_multiview as _mv
                        if _mv.available():
                            # LIBERER LA VRAM D'ABORD. MV-Adapter charge SDXL (~15 Go);
                            # si FLUX/ComfyUI (~12 Go) est encore resident, la carte 16 Go
                            # sature -> GEL du PC. On evince ComfyUI+Ollama avant.
                            # 03/08: la description de pose (qwen-vl 7 Go)
                            # doit se faire AVANT l'eviction — elle re-polluait
                            # la carte juste apres l'attente VRAM -> OOM SDXL.
                            _pose_desc = ""
                            try:
                                from vlm_judge import ask_vlm as _pv
                                _pr = _pv([str(front_ref)],
                                          "Decris la POSE du sujet en UNE courte "
                                          "phrase anglaise factuelle (ex: 'lying "
                                          "on his side, head tilted, eyes "
                                          "closed'). JSON: {\"pose\": \"...\"}",
                                          schema_hint='{"pose": "..."}')
                                if isinstance(_pr, dict):
                                    _pose_desc = str(_pr.get("pose") or "")[:120]
                            except Exception:  # noqa: BLE001
                                pass
                            _free_gpu_before_shape(audit)
                            # 03/08 (volu4): l'eviction est ASYNCHRONE — SDXL
                            # plein-GPU (15,8 Go) chargeait pendant que qwen-vl
                            # (7 Go) se videait encore -> OOM sur GPU pourtant
                            # libre 30 s plus tard. On attend la VRAM REELLE.
                            try:
                                for _w in range(24):
                                    _sm = subprocess.run(
                                        ["nvidia-smi", "--query-gpu=memory.used",
                                         "--format=csv,noheader,nounits"],
                                        capture_output=True, text=True, timeout=10)
                                    _used = int((_sm.stdout or "9999").strip().splitlines()[0])
                                    if _used < 2500:
                                        break
                                    print("PROGRESS:reference:attente liberation "
                                          "VRAM (%d Mio occupes)..." % _used,
                                          flush=True)
                                    time.sleep(5)
                            except Exception:  # noqa: BLE001
                                pass
                            print("PROGRESS:shape:Atlas prend plusieurs vues coherentes "
                                  "pour lever l'ambiguite de profondeur...", flush=True)
                            # Lot de vues derivees DEPUIS la photo acceptee. Si l'UI est
                            # la (--confirm-ref), on demande "ce lot convient-il ?" —
                            # refus (motif compris) = nouvelles vues; 3 refus = repli
                            # front-only (jamais un lot refuse dans la reconstruction).
                            _mv_seed = 42
                            _mv_text = prompt
                            _photo_reelle = bool(images)
                            # 31/07 (retour Juan: « les 3 refus sont juste 3x
                            # les memes derives »): re-deriver avec un autre
                            # seed reproduit le meme echec. UN lot; refuse =>
                            # question mono-vue/arret immediatement. +1 de
                            # marge (jamais un nouveau LOT au meme seed): les
                            # deux "continue" plus bas (OOM, ref_scale 1.3)
                            # sont chacun un essai UNIQUE avec un PARAMETRE
                            # different, pas un reroll — sans cette marge la
                            # borne par defaut (1) les rendait tous deux
                            # inertes (le continue terminait la boucle au lieu
                            # de relancer, verifie: aucun 2e appel i2mv trace).
                            for _lot_try in range(int(os.environ.get("AURORA_MV_LOTS", "1")) + 1):
                                _mvr = _mv.generate(str(front_ref_derivation), str(output_dir),
                                                    "%s_reference" % run_id,
                                                    text=_mv_text, seed=_mv_seed,
                                                    pose_desc=_pose_desc,
                                                    photo_reelle=_photo_reelle,
                                                    pick=([0, 2, 3] if _flat_art else None))
                                if not _mvr.get("ok"):
                                    audit.append({"stage": "mvadapter_multiview",
                                                  "ok": False,
                                                  "error": _mvr.get("error")})
                                    # 03/08 (volu3): OOM VRAM transitoire (le
                                    # bureau tenait la carte). UNE relance
                                    # apres re-eviction + 30 s.
                                    if "out of memory" in str(_mvr.get("error", "")).lower() \
                                            and _lot_try == 0:
                                        print("PROGRESS:reference:VRAM saturee "
                                              "pour les vues — re-eviction et "
                                              "nouvel essai dans 30 s (fermez "
                                              "les applis GPU)", flush=True)
                                        _free_gpu_before_shape(audit)
                                        time.sleep(30)
                                        continue
                                    if _flat_art:
                                        # un aplat SANS vues volumiques ne peut
                                        # donner qu'une carte: on refuse TOUT DE
                                        # SUITE au lieu de bruler 3 h.
                                        return {"ok": False,
                                                "error": "aplat 2D: vues "
                                                         "volumiques impossibles "
                                                         "(%s) — liberez la VRAM "
                                                         "(fermez navigateur/"
                                                         "applis GPU) et relancez"
                                                         % str(_mvr.get("error"))[:120],
                                                "audit_trail": audit}
                                    break
                                audit.append({"stage": "mvadapter_multiview", "ok": True,
                                              "views": len(_mvr.get("views") or []),
                                              "azimuths": _mvr.get("azimuths"),
                                              "attempt": _lot_try})
                                # CONTROLE QUALITE AUTOMATIQUE. Ce chemin envoyait les
                                # vues derivees dans TRELLIS.2 sans AUCUNE verification:
                                # une vue delirante (sujet fondu, en miettes, couleurs
                                # parties) ruinait toute la reconstruction. On jette les
                                # vues defectueuses; s'il n'en reste aucune, on repart
                                # sur la face seule plutot que d'empoisonner le modele.
                                _good_views = []
                                # ETAPE 8: porte CHIFFREE (cosinus CLIP) avant
                                # le juge VLM — l'ecart d'embedding attrape
                                # l'« autre personne » que l'oeil VLM rate.
                                _cos_par_vue = {}
                                try:
                                    _sim_cmd = [sys.executable,
                                                str(Path(__file__).parent / "auto_tag_images.py"),
                                                "--similarity-ref", str(front_ref_derivation),
                                                "--images"] + [str(v) for v in (_mvr.get("views") or [])]
                                    _sp2 = subprocess.run(_sim_cmd, capture_output=True,
                                                          text=True, timeout=600)
                                    for _l in reversed((_sp2.stdout or "").splitlines()):
                                        if _l.strip().startswith("{"):
                                            _sj = json.loads(_l)
                                            if _sj.get("ok"):
                                                _cos_par_vue = {str(v): c for v, c in
                                                                zip(_mvr.get("views") or [],
                                                                    _sj.get("cosinus") or [])}
                                            break
                                    if _cos_par_vue:
                                        audit.append({"stage": "porte_coherence_clip",
                                                      "cosinus": {Path(k).name: round(v, 3)
                                                                  for k, v in _cos_par_vue.items()}})
                                except Exception:  # noqa: BLE001
                                    pass
                                def _meme_sujet(_vp):
                                    _c = _cos_par_vue.get(str(_vp))
                                    if _c is not None and _c < float(os.environ.get(
                                            "AURORA_COHERENCE_COS", "0.60")):
                                        print("PROGRESS:reference:vue rejetee par la "
                                              "porte chiffree (cos=%.2f < 0.60)" % _c,
                                              flush=True)
                                        return False
                                    try:
                                        from vlm_judge import ask_vlm as _iv
                                        _r = _iv([str(front_ref), str(_vp)],
                                                 "Image 1 = reference. Image 2 = "
                                                 "vue derivee sous un autre angle. "
                                                 "Est-ce le MEME sujet (meme "
                                                 "personne/creature, memes couleurs, "
                                                 "memes attributs — ailes, coiffure, "
                                                 "vetements) ? JSON: "
                                                 "{\"meme_sujet\": true|false}",
                                                 schema_hint='{"meme_sujet": true|false}')
                                        return not (isinstance(_r, dict)
                                                    and _r.get("meme_sujet") is False)
                                    except Exception:  # noqa: BLE001
                                        return True
                                for _v in (_mvr.get("views") or []):
                                    _why = _derived_view_defects(str(front_ref), str(_v))
                                    if _why:
                                        print("PROGRESS:reference:vue derivee jetee (%s)"
                                              % _why, flush=True)
                                        audit.append({"stage": "mv_view_rejected",
                                                      "view": os.path.basename(str(_v)),
                                                      "reason": _why})
                                        # une vue rejetee SUPPRIMEE tout de
                                        # suite: laissee sur disque, elle
                                        # partait dans la livraison comme
                                        # "reference retenue" (damier livre).
                                        try:
                                            os.remove(str(_v))
                                        except OSError:
                                            pass
                                    else:
                                        if _meme_sujet(_v):
                                            _good_views.append(_v)
                                        else:
                                            print("PROGRESS:reference:vue derivee "
                                                  "rejetee (pas le meme sujet que "
                                                  "la reference)", flush=True)
                                            try:
                                                Path(_v).unlink(missing_ok=True)
                                            except Exception:  # noqa: BLE001
                                                pass
                                if not _good_views:
                                    # ETAPE 8b: rejets d'identite => UNE relance
                                    # avec la reference RENFORCEE (ref_scale
                                    # 1.3), MEME seed — re-seeder rejoue le
                                    # meme echec (prouve le 31/07).
                                    if os.environ.get("AURORA_MV_REF_SCALE") != "1.3":
                                        os.environ["AURORA_MV_REF_SCALE"] = "1.3"
                                        print("PROGRESS:reference:vues rejetees -> "
                                              "relance avec reference renforcee "
                                              "(ref_scale 1.3, meme seed)", flush=True)
                                        audit.append({"stage": "mvadapter_multiview",
                                                      "all_views_rejected": True,
                                                      "relance_ref_scale": 1.3})
                                        continue
                                    print("PROGRESS:reference:toutes les vues derivees sont "
                                          "inexploitables -> reconstruction depuis la face seule",
                                          flush=True)
                                    audit.append({"stage": "mvadapter_multiview", "ok": False,
                                                  "all_views_rejected": True,
                                                  "attempt": _lot_try})
                                    continue
                                _mvr["views"] = _good_views
                                if os.environ.get("AURORA_REF_CONFIRM") != "1":
                                    os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "1"
                                    break
                                _lot = ([str(front_ref)]
                                        + [str(v) for v in _good_views])
                                _dlc = _interactive_confirm(
                                    _lot,
                                    "Ce lot de vues (derivees de la photo acceptee) convient-il ?",
                                    output_dir, run_id, "lot", audit)
                                if _dlc["accepted"]:
                                    # 31/07: tri IMAGE PAR IMAGE — l'utilisateur
                                    # peut jeter certaines vues du lot; on ne
                                    # garde que les siennes (index 0 = face).
                                    _jet = _dlc.get("jetees") or []
                                    if _jet:
                                        _gardees = [v for _iv, v in enumerate(_good_views)
                                                    if (_iv + 1) not in _jet]
                                        for _iv, v in enumerate(_good_views):
                                            if (_iv + 1) in _jet:
                                                try:
                                                    Path(v).unlink(missing_ok=True)
                                                except Exception:  # noqa: BLE001
                                                    pass
                                        _mvr["views"] = _gardees
                                        print("PROGRESS:reference:tri du lot — %d "
                                              "vue(s) gardee(s), %d jetee(s)"
                                              % (len(_gardees), len(_jet)), flush=True)
                                        if not _gardees:
                                            os.environ.pop("AURORA_TRELLIS2_MULTIVIEW", None)
                                            break
                                    os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "1"
                                    break
                                _mv_seed += 1013 + _lot_try
                                if _dlc["reason"]:
                                    _mv_text = "%s. %s" % (prompt, _dlc["reason"])
                                print("PROGRESS:reference:lot refuse -> nouvelles vues derivees...",
                                      flush=True)
                            else:
                                os.environ.pop("AURORA_TRELLIS2_MULTIVIEW", None)
                                audit.append({"stage": "mvadapter_multiview", "ok": False,
                                              "user_refused_lots": True,
                                              "note": "repli front-only (la face acceptee reste la seule source)"})
                                _suite = _interactive_confirm(
                                    [str(front_ref)],
                                    "Vues derivees refusees. CONTINUER avec la "
                                    "face seule (mono-vue) ? Accepter = oui; "
                                    "Non = ARRET complet de la generation.",
                                    output_dir, run_id, "monovue", audit)
                                if not _suite["accepted"]:
                                    return {"ok": False,
                                            "error": "generation arretee a votre "
                                                     "demande apres refus des vues "
                                                     "derivees (rien n'a ete impose)",
                                            "audit_trail": audit}
                                print("PROGRESS:reference:vos refus ont elimine "
                                      "les vues derivees — reconstruction depuis "
                                      "la FACE SEULE (validee par vous)", flush=True)
                    except Exception as _mve:  # noqa: BLE001
                        audit.append({"stage": "mvadapter_multiview", "ok": False,
                                      "error": repr(_mve)})
                print("PROGRESS:shape:Atlas construit la geometrie et les matieres depuis la reference...", flush=True)
                _free_gpu_before_shape(audit)  # libere ComfyUI/FLUX/Ollama avant TRELLIS
                # SOUS-PROCESS dedie: env propre (CUDA_HOME/nvcc pour le JIT nvdiffrast) et
                # surtout la VRAM du modele 4B (~11 Go) est 100% liberee a la sortie. En
                # in-process le modele restait cache -> OOM du repli Hunyuan -> rescue CPU tres lent.
                # 01/08 (2e OOM cgroup mesure a 23,5 Go): parent et TRELLIS
                # partagent le MEME plafond — on vide le parent (rembg/torch/
                # caches) avant de ceder la place a l'enfant.
                try:
                    import gc as _gc
                    for _mod in ("rembg", "torch"):
                        _m = sys.modules.get(_mod)
                        if _m is not None and _mod == "torch":
                            try:
                                _m.cuda.empty_cache()
                            except Exception:  # noqa: BLE001
                                pass
                    _gc.collect()
                except Exception:  # noqa: BLE001
                    pass
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
                    print("PROGRESS:memoire:memoire liberee avant la construction", flush=True)
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
                        print("PROGRESS:memoire:%d modele(s) decharges avant la construction" % len(_loaded), flush=True)
                except Exception:  # noqa: BLE001
                    pass
                # ECHELLE ANTI-GEL (gel du 24/07, Xid 109 pendant les
                # materiaux avec 22 Go en swap): si le systeme est DEJA charge
                # en entrant dans TRELLIS, on reduit la texture au lieu de
                # tenter le 16K — un modele livre en 8K vaut mieux qu'un PC
                # gele a 90% de l'etape. Seuil AURORA_SWAP_LADDER_GB (12 Go).
                try:
                    with open("/proc/meminfo", "r", encoding="utf-8") as _fh:
                        _mi = {l.split(":")[0]: l.split()[1] for l in _fh if ":" in l}
                    _swap_used_gb = (float(_mi.get("SwapTotal", 0))
                                     - float(_mi.get("SwapFree", 0))) / 1048576.0
                except Exception:  # noqa: BLE001
                    _swap_used_gb = 0.0
                # 30/07: seuil recalcule pour le swap 64 Go (il datait des
                # 8-32 Go: a 12 Go on degradait la texture alors que la
                # machine avait 50 Go de marge).
                _ladder = float(os.environ.get("AURORA_SWAP_LADDER_GB", "30"))
                if _swap_used_gb > _ladder:
                    # 31/07 (doctrine Juan): on ne BAISSE JAMAIS la qualite en
                    # silence. Au lieu de degrader la texture, on ATTEND que la
                    # memoire se libere (les modeles Ollama/FLUX expirent en
                    # ~60 s, le swap se draine), en informant. Degradation
                    # seulement si AURORA_QUALITE_MAX=0 explicitement.
                    if os.environ.get("AURORA_QUALITE_MAX", "1") == "1":
                        _attente_max = float(os.environ.get("AURORA_ATTENTE_MEMOIRE_S", "900"))
                        _t0_att = time.time()
                        while _swap_used_gb > _ladder and time.time() - _t0_att < _attente_max:
                            print("PROGRESS:memoire:swap a %.1f Go — ATTENTE de la "
                                  "liberation memoire (%.0f s) au lieu de reduire la "
                                  "texture" % (_swap_used_gb, time.time() - _t0_att),
                                  flush=True)
                            time.sleep(20)
                            try:
                                with open("/proc/meminfo", "r", encoding="utf-8") as _fh2:
                                    _mi2 = {l.split(":")[0]: l.split()[1] for l in _fh2 if ":" in l}
                                _swap_used_gb = (int(_mi2.get("SwapTotal", 0))
                                                 - int(_mi2.get("SwapFree", 0))) / 1048576.0
                            except Exception:  # noqa: BLE001
                                break
                        audit.append({"stage": "texture_ladder", "attente_s": round(time.time() - _t0_att),
                                      "swap_gb": round(_swap_used_gb, 1),
                                      "texture": os.environ.get("AURORA_TRELLIS2_TEXTURE", "max"),
                                      "qualite_conservee": True})
                        print("PROGRESS:memoire:on continue en QUALITE MAX (swap %.1f Go)"
                              % _swap_used_gb, flush=True)
                    else:
                        os.environ["AURORA_TRELLIS2_TEXTURE"] = "4096"
                        os.environ["AURORA_TRELLIS2_16K"] = "0"
                        print("PROGRESS:memoire:swap deja a %.1f Go — texture reduite "
                              "a 4K (AURORA_QUALITE_MAX=0)" % _swap_used_gb, flush=True)
                        audit.append({"stage": "texture_ladder", "swap_gb": round(_swap_used_gb, 1),
                                      "texture": "4096", "seize_k": False})
                try:
                    # GARDE RAM GLOBALE (01/08, preuve journal 15:53: OOM
                    # noyau declenche par VS Code, victime = TRELLIS a 25 Go
                    # apres 1 h de calcul). Sur 30 Go physiques, TRELLIS +
                    # bureau charge ne tiennent pas ENSEMBLE. Doctrine: on
                    # n'abaisse pas la qualite et on ne meurt pas — on ATTEND
                    # la RAM en le disant clairement.
                    try:
                        # 03/08: 26,5 Go exigeait plus que le repos de CETTE machine (25,6
                        # libres a vide) — 30 min d'attente perdues a chaque run. Le pic
                        # mesure (TRELLIS 24,5 + parent) tient dans 25 Go + swap cgroup.
                        # 03/08 b: en passe de PEINTURE le parent porte deja le maillage
                        # (10 M faces ~1,5 Go) — 24,4 Go libres est un etat SAIN a ce
                        # stade. 23,5 Go couvre le pic peinture mesure sans bloquer.
                        _besoin_mb = float(os.environ.get("AURORA_RAM_REQUISE_MB", "8000"))
                        _t0_ram = time.time()
                        while time.time() - _t0_ram < float(os.environ.get(
                                "AURORA_RAM_ATTENTE_MAX_S", "1800")):
                            with open("/proc/meminfo", "r", encoding="utf-8") as _mf:
                                _mi3 = {l.split(":")[0]: int(l.split()[1])
                                        for l in _mf if ":" in l}
                            _dispo_mb = _mi3.get("MemAvailable", 0) / 1024.0
                            if _dispo_mb >= _besoin_mb:
                                break
                            print("PROGRESS:memoire:RAM insuffisante pour la "
                                  "reconstruction (%.1f Go libres, besoin ~%.1f) "
                                  "— FERMEZ des applications (navigateur, "
                                  "VS Code...) ou j'attends (%.0f s)"
                                  % (_dispo_mb / 1024, _besoin_mb / 1024,
                                     time.time() - _t0_ram), flush=True)
                            time.sleep(15)
                        else:
                            print("PROGRESS:memoire:attente RAM epuisee — je "
                                  "tente quand meme (risque d'arret par le "
                                  "noyau si le bureau reste charge)", flush=True)
                    except Exception:  # noqa: BLE001
                        pass
                    _tr_src = front_ref_derivation if _upright_angle else front_ref
                    if _flat_art:
                        try:
                            import shutil as _shv
                            _stem0 = str(output_dir / ("%s_reference" % run_id))
                            _volu = output_dir / ("%s_reference_volu.png" % run_id)
                            if os.path.isfile(_stem0 + "_v2.png"):
                                _shv.copyfile(_stem0 + "_v2.png", str(_volu))
                                for _a, _b in (("_v3.png", "_volu_v2.png"),
                                               ("_v4.png", "_volu_v3.png")):
                                    if os.path.isfile(_stem0 + _a):
                                        _shv.copyfile(_stem0 + _a,
                                                      str(output_dir / ("%s_reference%s" % (run_id, _b))))
                                _tr_src = _volu
                                print("PROGRESS:shape:face volumisee retenue "
                                      "pour la reconstruction (aplat 2D)",
                                      flush=True)
                        except Exception as _fve:  # noqa: BLE001
                            audit.append({"stage": "volumisation", "ok": False,
                                          "error": repr(_fve)})
                    _tr_cmd = [trellis_python(), _wrapper, str(_tr_src), str(mesh_path)]
                    _stem = str(front_ref)
                    _stem = _stem[:-4] if _stem.lower().endswith(".png") else _stem
                    for _vi in (2, 3, 4):
                        _vp = f"{_stem}_v{_vi}.png"
                        if os.path.isfile(_vp):
                            _tr_cmd.append(_vp)
                    _p = run_neural_process(_tr_cmd,
                                           env=_tr_env, timeout=int(os.environ.get("AURORA_TRELLIS_TIMEOUT_S", "10800")))
                    for _line in reversed((_p.stdout or "").splitlines()):
                        if _line.startswith("AURORA_TRELLIS_RESULT:"):
                            _tr = json.loads(_line[len("AURORA_TRELLIS_RESULT:"):]); break
                    if not _tr:
                        _tr = {"ok": False, "error": (_p.stderr or _p.stdout or "no output")[-400:]}
                except Exception as _se:  # noqa: BLE001
                    _tr = {"ok": False, "error": f"subprocess: {_se!r}"}
                # PORTE ANTI-MASQUE (31/07, recherche + demande verbatim:
                # « jamais avoir un masque a part quand c'est demande »).
                # Verdict chiffre (PCA + epaisseur + dos plat); masque =>
                # re-essai pilote: seed variee, puis bascule mono<->multi.
                # Un relief/bas-relief DEMANDE (mots du prompt) est exempte.
                if (_tr.get("ok") and mesh_path.is_file()
                        and os.environ.get("AURORA_ANTI_MASQUE", "1") == "1"
                        and not any(k in (prompt or "").lower()
                                    for k in ("relief", "bas-relief", "masque",
                                              "plaque", "medaillon"))):
                    try:
                        from porte_anti_masque import mesurer as _pam
                        _verdict_pam = _pam(str(mesh_path))
                        audit.append({"stage": "porte_anti_masque",
                                      **_verdict_pam})
                        if _verdict_pam.get("masque"):
                            _essai_pam = int(os.environ.get("_AURORA_PAM_ESSAI", "0"))
                            if _essai_pam < 2:
                                os.environ["_AURORA_PAM_ESSAI"] = str(_essai_pam + 1)
                                if _essai_pam == 0:
                                    print("PROGRESS:shape:MASQUE creux detecte "
                                          "(mesures: %s) — re-essai seed variee"
                                          % _verdict_pam.get("mesures"), flush=True)
                                    _tr_cmd2 = list(_tr_cmd) + ["--seed", "1014"]
                                else:
                                    _flip = os.environ.get("AURORA_TRELLIS2_MULTIVIEW", "0")
                                    os.environ["AURORA_TRELLIS2_MULTIVIEW"] = "0" if _flip == "1" else "1"
                                    print("PROGRESS:shape:masque persistant — "
                                          "bascule %s"
                                          % ("mono-vue" if _flip == "1" else "multi-vues"),
                                          flush=True)
                                    _tr_cmd2 = [c for c in _tr_cmd
                                                if _flip != "1" or "_reference_v" not in str(c)]
                                    _tr_cmd2 += ["--seed", "2027"]
                                try:
                                    mesh_path.unlink(missing_ok=True)
                                except Exception:  # noqa: BLE001
                                    pass
                                _p = run_neural_process(_tr_cmd2, env=_tr_env,
                                                       timeout=int(os.environ.get("AURORA_TRELLIS_TIMEOUT_S", "10800")))
                                _tr = {}
                                for _line in reversed((_p.stdout or "").splitlines()):
                                    if _line.startswith("AURORA_TRELLIS_RESULT:"):
                                        _tr = json.loads(_line[len("AURORA_TRELLIS_RESULT:"):]); break
                                if mesh_path.is_file():
                                    _verdict_pam2 = _pam(str(mesh_path))
                                    audit.append({"stage": "porte_anti_masque",
                                                  "re_essai": _essai_pam + 1,
                                                  **_verdict_pam2})
                                    if _verdict_pam2.get("masque"):
                                        print("PROGRESS:shape:avertissement masque creux — maillage conserve et livre", flush=True)
                                        _tr["ok"] = True
                            else:
                                print("PROGRESS:shape:avertissement masque creux detecte — maillage conserve et livre", flush=True)
                                _tr["ok"] = True
                    except Exception as _pame:  # noqa: BLE001
                        audit.append({"stage": "porte_anti_masque", "ok": False,
                                      "error": repr(_pame)})
                if (_tr.get("ok") and mesh_path.is_file() and _upright_angle
                        and abs(_upright_angle) > 3.0):
                    # ROTATION INVERSE (etape 6): le modele reconstruit debout
                    # revient dans la pose reelle de la photo.
                    try:
                        from perfection_gate import tourner_buffers_z as _tbz
                        _tbz(str(mesh_path), _upright_angle)
                        audit.append({"stage": "redressement_inverse",
                                      "angle_deg": _upright_angle})
                        print("PROGRESS:shape:pose reelle restauree (%.0f deg)"
                              % _upright_angle, flush=True)
                    except Exception as _tze:  # noqa: BLE001
                        audit.append({"stage": "redressement_inverse", "ok": False,
                                      "error": repr(_tze)})
                if _tr.get("ok") and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
                    _trellis_ok = True
                    audit.append({"stage": "trellis2", "ok": True, "mesh_path": str(mesh_path),
                                  "faces": _tr.get("faces"), "verts": _tr.get("verts"),
                                  "peak_vram_gb": _tr.get("peak_vram_gb"), "quality": _tr.get("quality")})
                    print(f"PROGRESS:shape:geometrie native posee — {_tr.get('faces') or '?'} faces ({_tr.get('quality')})", flush=True)
                    # BALAYAGE CAPILLAIRE. Les meches sous la resolution de la
                    # grille sortent en confettis fermes flottants (guerrier:
                    # 8463 ilots de ~2 faces autour de la tete, 0 bord ouvert
                    # -> "boucher" ne sert a rien, on BALAIE). Sous-processus
                    # venv (trimesh) pour ne pas gonfler la RAM du pipeline.
                    if os.environ.get("AURORA_BALAYAGE", "1") == "1":
                        try:
                            _venv_py2 = str(REPO_ROOT / "application" / ".venv" / "bin" / "python")
                            if not os.path.isfile(_venv_py2):
                                _venv_py2 = sys.executable
                            _sw_out = str(mesh_path) + ".propre.glb"
                            _swp = subprocess.run(
                                [_venv_py2, str(REPO_ROOT / "application" /
                                                "python-services" / "poussiere_capillaire.py"),
                                 "--input", str(mesh_path), "--output", _sw_out],
                                capture_output=True, text=True, timeout=1200)
                            _sw_line = next((l for l in reversed(
                                (_swp.stdout or "").splitlines())
                                if l.strip().startswith("{")), "{}")
                            _sw = json.loads(_sw_line)
                            if _sw.get("ok") and os.path.isfile(_sw_out)                                     and os.path.getsize(_sw_out) > 1000:
                                os.replace(_sw_out, str(mesh_path))
                                audit.append({"stage": "balayage_capillaire", **_sw})
                                if _sw.get("ilots_retires"):
                                    print("PROGRESS:qualite:%d confettis de meches "
                                          "balayes (%.1f%% de l'aire)"
                                          % (_sw["ilots_retires"],
                                             _sw.get("aire_retiree_pct", 0)),
                                          flush=True)
                            else:
                                audit.append({"stage": "balayage_capillaire",
                                              "ok": False,
                                              "error": str(_sw.get("error"))[:160]})
                        except Exception as _swe:  # noqa: BLE001
                            audit.append({"stage": "balayage_capillaire",
                                          "ok": False, "error": repr(_swe)})
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
                    elif not _trellis_ok:
                        audit.append({"stage": "trellis2", "ok": False,
                                      "error": _tr.get("error")})
                    if _trellis_ok:
                        _shape_ok = True
                else:
                    audit.append({"stage": "trellis2", "skipped": True,
                                  "reason": "TRELLIS.2 indisponible dans l'interpreteur (%s)"
                                            % trellis_python()})
            except Exception as _e:  # noqa: BLE001
                audit.append({"stage": "trellis2", "ok": False, "error": repr(_e)})

        if not _shape_ok and not _trellis_ok:
            if _primary_engine != "hunyuan3d":
                print("PROGRESS:shape:Atlas reprend la construction par une autre methode...", flush=True)
                _hy = _run_hunyuan3d_engine(front_ref, mesh_path, prompt, audit)
                if _hy.get("ok") and mesh_path.is_file() and mesh_path.stat().st_size > 1000:
                    _shape_ok = True
                    audit.append({"stage": "hunyuan3d", "ok": True, "mesh_path": str(mesh_path),
                                  "faces": _hy.get("faces"), "verts": _hy.get("verts"),
                                  "elapsed_s": _hy.get("elapsed_s"), "fallback_from": "trellis"})
                    print(f"PROGRESS:shape:Atlas a pose la geometrie — {_hy.get('faces') or '?'} faces", flush=True)

        if not _shape_ok and not _trellis_ok:
            _tr_err = (_tr.get("error") if isinstance(_tr, dict) else None) or "echec des moteurs 3D (TRELLIS.2 et Hunyuan3D-2)"
            # 01/08: un OOM du cgroup restait invisible ("n'a pas produit de
            # mesh"). memory.events du scope se lit sans droits — on nomme le
            # tueur quand oom_kill a augmente.
            try:
                with open("/proc/self/cgroup", "r", encoding="utf-8") as _cgf:
                    _cgp = _cgf.read().strip().split("::")[-1]
                _evp = "/sys/fs/cgroup" + _cgp + "/memory.events"
                with open(_evp, "r", encoding="utf-8") as _evf:
                    _ev = dict(l.split() for l in _evf if " " in l)
                if int(_ev.get("oom_kill", 0)) > 0:
                    _tr_err = ("TUE PAR LA LIMITE MEMOIRE DU GROUPE "
                               "(oom_kill=%s, plafond %s Go) — %s"
                               % (_ev.get("oom_kill"),
                                  os.environ.get("AURORA_MEM_MAX_GB", "?"),
                                  str(_tr_err)[:150]))
            except Exception:  # noqa: BLE001
                pass
            # OOM GLOBAL (01/08): un OOM noyau declenche par une AUTRE appli
            # (VS Code a 15:53, preuve journal) n'incremente PAS les compteurs
            # du cgroup — on interroge le journal noyau, lisible par juan.
            try:
                _jc = subprocess.run(
                    ["journalctl", "-k", "--since", "-3 hours", "--no-pager"],
                    capture_output=True, text=True, timeout=20)
                _looms = [l for l in (_jc.stdout or "").splitlines()
                          if "Out of memory: Killed process" in l
                          or "invoked oom-killer" in l]
                if _looms:
                    _tr_err = ("TUE PAR LE NOYAU (OOM GLOBAL: bureau + "
                               "reconstruction > RAM physique — fermez des "
                               "applications et relancez) [%s] — %s"
                               % (_looms[-1][-120:], str(_tr_err)[:150]))
            except Exception:  # noqa: BLE001
                pass
            # 31/07: quand la sentinelle a tue TRELLIS, l'erreur ne montrait
            # que des barres de progression — le motif REEL etait dans la
            # trace. On le joint pour que l'utilisateur sache QUI a tue et
            # POURQUOI, au lieu d'un faux « TRELLIS n'a pas produit de mesh ».
            try:
                _tp = os.environ.get("AURORA_SENTINEL_TRACE", "/tmp/aurora_sentinelle.txt")
                if os.path.isfile(_tp) and os.path.getmtime(_tp) >= started_at:
                    _tr_err = "%s — %s" % (Path(_tp).read_text(encoding="utf-8").strip()[:200], str(_tr_err)[:200])
            except Exception:  # noqa: BLE001
                pass
            audit.append({"stage": "trellis2", "ok": False,
                          "trellis_error": str(_tr_err)[-600:]})
            _record_pipeline_dispatch(run_id, prompt, started_at_iso, status="blocked",
                                      verdict="3d engines failed: %s" % str(_tr_err)[:150])
            try:
                _jd = (output_dir.parent if output_dir.name == "models" else output_dir) / "journal"
                _jd.mkdir(parents=True, exist_ok=True)
                (_jd / "audit.json").write_text(
                    json.dumps(audit, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False,
                    "error": "Moteurs 3D ont echoue: %s" % (str(_tr_err)[:200]),
                    "audit_trail": audit}

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
    # Le service livre un PBR DEJA FINI. La chaine de reparation qui suit a
    # ete ecrite pour rattraper un atlas fragmente (bake de normales 8k, AO,
    # precision native, matieres par zones). Appliquee a une texture finie,
    # elle la detruit: mesure le 27/08 sur un personnage — brut, le t-shirt
    # portait "VIZION" parfaitement lisible; apres la chaine, texture
    # dechiquetee de taches couleur peau, refusee a 25/100 par la porte. On
    # ne repare donc que ce qui a besoin d'etre repare.
    # Une texture est FINIE dans deux cas: le service vient de la livrer, ou
    # l'on reutilise un fichier deja livre. Dans les deux cas la chaine de
    # reparation (bake de normales, precision native, matieres par zones) n'a
    # rien a rattraper et tout a abimer.
    # DATE CRITERE SUR LA COULEUR, PAS SUR LA TACHE: le `.tache` (droit de
    # riger/animer) est PERSISTE a cote du mesh et reutilise au 2e essai d'une
    # scene — il prouve un droit, pas une texture. Mesure 26/09 (loutre/fusil):
    # la 2e passe voyait `_tache_service` non vide, sautait toute la chaine de
    # couleur, et livrait le mesh TRELLIS BRUT sans baseColorTexture (= BLANC
    # dans le viewer). Un mesh "finie" doit porter une vraie couleur.

    final_mesh_path = rescue["final_mesh"]

    _a_reel = True  # comportement historique si impossible a verifier
    try:
        _a_reel = _a_de_la_couleur(str(final_mesh_path))
    except Exception:  # noqa: BLE001
        _a_reel = True
    _texture_du_service = bool(_a_reel)
    if _texture_du_service:
        print("PROGRESS:matieres:texture livree finie — Atlas ne la retouche pas",
              flush=True)
        audit.append({"stage": "post_traitement_texture", "skipped": True,
                      "reason": "texture finie fournie par le service"})

    # Stage 3.4 — MV-Adapter UV-aware re-texturing for hard-surface reproductions.
    # TRELLIS.2 / Hunyuan3D paint textures into the fragmented atlas that Marching
    # Cubes produces (hundreds of tiny UV islands), so branded symbols (X/O/Sq/Tri
    # on a DualSense, D-pad arrows, product logos) land on random UV shards and
    # read as scribbles. MV-Adapter regenerates a clean 4K UV atlas by diffusing
    # 6 consistent views from the FLUX reference then un-projecting via CV-CUDA
    # + nvdiffrast — no atlas-fragmentation artefacts, buttons cleanly individuated.
    # Opt-in: AURORA_MVADAPTER_RETEXTURE=1 (auto-set by --max-precision when the
    # subject is hard-surface: product/gadget/vehicle/pc_tower/computer/case).
    # Runs in a separate conda env (mvadapter, torch cu128 Blackwell) via subprocess;
    # ~90s of extra runtime on Blackwell. Best-effort — skipped silently if the env
    # isn't provisioned.
    # Hard-surface kinds where MV-Adapter's UV-aware retexturing shines. Organic
    # subjects (character/humanoid/creature/quadruped) are excluded — their textures
    # are noise-tolerant enough that TRELLIS's atlas paint already reads well, and
    # MV-Adapter's ortho views quantize skin tones aggressively.
    MVADAPTER_HARD_SURFACE_KINDS = {
        "product", "gadget", "vehicle", "pc_tower", "case",
        "computer", "architecture", "sphere",
    }
    _mv_want = os.environ.get("AURORA_MVADAPTER_RETEXTURE", "0") == "1"
    _mv_kind_ok = kind in MVADAPTER_HARD_SURFACE_KINDS
    if _mv_want and _mv_kind_ok and not _texture_du_service:
        try:
            import mvadapter_retexture as _mv  # noqa: WPS433
            _mv_pre = _mv.preflight()
            if not _mv_pre.get("ready"):
                audit.append({"stage": "mvadapter_retexture", "ok": False,
                              "reason": "env not provisioned", "preflight": _mv_pre})
            else:
                _mv_out_dir = str(output_dir / "mvadapter")
                _mv_res = _mv.retexture(
                    in_mesh=final_mesh_path,
                    reference=front_ref,
                    save_dir=_mv_out_dir,
                    save_name=f"{run_id}_mvadapter",
                )
                audit.append({"stage": "mvadapter_retexture",
                              **{k: v for k, v in _mv_res.items() if k != "log_tail"}})
                if _mv_res.get("ok") and _mv_res.get("out_mesh") and Path(_mv_res["out_mesh"]).is_file():
                    final_mesh_path = _mv_res["out_mesh"]
        except Exception as exc:  # noqa: BLE001
            audit.append({"stage": "mvadapter_retexture", "ok": False, "error": repr(exc)})
    elif _mv_want and not _mv_kind_ok:
        audit.append({"stage": "mvadapter_retexture", "skipped": True,
                      "reason": f"kind={kind} is not hard-surface"})

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
        if (not _keep_native and not _texture_du_service
                and Path(mesh_path).is_file() and Path(final_mesh_path).is_file()
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

    if os.environ.get("AURORA_AO", "1") == "1" and not _texture_du_service:
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
    if material_intel_enabled and not _texture_du_service:
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

    if (material_intel_enabled and material_manifest_data is not None
            and not _texture_du_service):
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
    elif _texture_du_service:
        # EMISSIF SUR UNE TEXTURE DEJA FINIE. Sauter la chaine de reparation
        # est juste (elle dechiquette une texture finie), mais l'emissif
        # partait avec elle: neons, ecran allume, ventilateurs RGB et clavier
        # retroeclaire sortaient ETEINTS (mesure: emissiveFactor [0,0,0] sur
        # tout le studio VIZION, aucune extension declaree).
        # Or emissive_synth n'est PAS une retouche: il LIT la baseColor pour en
        # deriver un masque et n'AJOUTE qu'emissiveTexture + emissiveFactor +
        # KHR_materials_emissive_strength. La couleur livree n'est jamais
        # modifiee. C'est donc la seule etape matieres qui reste legitime ici.
        # Auto-limitant: le masque vient de la TEXTURE — si rien n'y est
        # lumineux, la couverture est nulle et on n'applique rien.
        _em_entry = {"stage": "channel_synth_emissif", "ok": False}
        try:
            _veut_em, _teintes = _emission_demandee(
                prompt, os.environ.get("AURORA_PROMPT_ORIGINAL", ""))
            _em_entry["demande_lumineuse"] = _veut_em
            _em_entry["teintes"] = _teintes
            if _veut_em and final_mesh_path and Path(str(final_mesh_path)).is_file():
                import emissive_synth as _es2
                _em_png2 = str(output_dir / f"{run_id}_emissive.png")
                _em_glb2 = str(output_dir / f"{run_id}_mesh_emissive.glb")
                # SATURATION: un tube ETEINT est peint en VERRE PALE, pas en
                # couleur vive — mesure sur les neons du bureau VIZION: teinte
                # cyan franche mais saturation mediane 0.03 (p90 0.18), la ou
                # le defaut 0.55 vise une surface deja allumee. A 0.55 le
                # masque etait vide: 0.00%. Quand la demande NOMME les teintes,
                # c'est le filtre de teinte qui porte la selectivite (le bois,
                # 72,7% de cet atlas, est exclu d'office), donc on peut relacher
                # la saturation sans ouvrir la porte au reste de l'objet.
                _sat_min = 0.18 if _teintes else 0.55
                _em_entry["sat_min"] = _sat_min
                _r2 = _es2._run(argparse.Namespace(
                    glb=str(final_mesh_path), output=_em_png2, hues=_teintes,
                    strength=float(os.environ.get("AURORA_EMISSIVE_STRENGTH", "5.0")),
                    sat_min=_sat_min, val_min=0.60, size=2048, apply=_em_glb2))
                _cov = float(_r2.get("coverage_pct") or 0.0)
                _em_entry["coverage_pct"] = _cov
                # une couverture quasi nulle = rien de lumineux dans la
                # texture: on ne remplace pas le fichier pour rien.
                if _cov >= 0.05 and Path(_em_glb2).is_file():
                    final_mesh_path = _em_glb2
                    _em_entry["ok"] = True
                    print("PROGRESS:matieres:surfaces lumineuses allumees "
                          "(%.2f%% de la texture%s) — couleur livree intacte"
                          % (_cov, (", teintes: " + _teintes) if _teintes else ""),
                          flush=True)
                else:
                    _em_entry["skipped"] = "aucune surface lumineuse dans la texture"
        except Exception as _eme:  # noqa: BLE001
            _em_entry["error"] = repr(_eme)
        audit.append(_em_entry)
    else:
        audit.append({"stage": "channel_synth", "skipped": True,
                      "reason": ("AURORA_MATERIAL_INTEL=0" if not material_intel_enabled
                                 else "no material manifest")})

    # Stage 4 (optional) — motion bake via rigify
    # Un humain decrit le mouvement DANS la phrase ("un homme qui marche", "une
    # fontaine qui coule"), pas dans un champ separe. Sans motion_prompt explicite,
    # on le DERIVE du prompt principal et on laisse la machinerie de mouvement
    # (motion_parser puis classifier LLM) trancher s'il y a un vrai mouvement :
    # "un homme qui marche" -> character.walk_cycle ; "un homme"/"une pomme" -> null
    # -> rigid_static -> aucune animation. Aucun verbe code en dur, c'est l'IA qui
    # comprend le mouvement decrit naturellement.
    # 31/07 (mesure sur le vase de preuve): deriver motion_prompt du prompt
    # PRINCIPAL sans filtre faisait croire a l'acceptation finale que TOUT
    # run "voulait du mouvement" — un vase statique etait rejete pour
    # « motion required but no animation channels ». On ne derive que si le
    # prompt contient REELLEMENT un mouvement (meme detecteur que la porte),
    # et la variable reste distincte pour l'acceptation.
    # Quand la posture vient d'un squelette pose en aval (voie service), la
    # derivation locale est au mieux redondante, au pire fausse: elle a
    # route un ENTREPRENEUR vers l'animateur d'eau (27/08). L'appelant qui
    # sait qu'il posera le personnage lui-meme coupe cette passe.
    _motion_derive = False
    _motion_locale = os.environ.get("AURORA_MOTION_LOCALE", "1") == "1"
    if not _motion_locale and not motion_prompt:
        audit.append({"stage": "motion_locale", "skipped": True,
                      "reason": "la posture est posee par un squelette en aval"})
    if _motion_locale and not motion_prompt and prompt and prompt.strip():
        try:
            from mesh_acceptance_gate import MOTION_RE as _MRE, NO_MOTION_RE as _NMRE
            if _MRE.search(prompt) and not _NMRE.search(prompt):
                motion_prompt = prompt
                _motion_derive = True
                print(f"PROGRESS:animation:mouvement derive du prompt naturel: '{prompt[:80]}'", flush=True)
        except Exception:  # noqa: BLE001
            pass
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

    # MOUVEMENT EN ARGILE. Pendant anime du {run}_GEOMETRIE.png statique:
    # les couleurs masquent les defauts de deformation (dechirures, plis,
    # glissements de pieds); la planche argile les montre. Produit pour CHAQUE
    # generation animee, par le meme chemin UI/CLI. AURORA_MOTION_CLAY=0 coupe.
    if rigged_mesh and os.environ.get("AURORA_MOTION_CLAY", "1") == "1":
        try:
            import motion_clay_render as _mcr
            _clay = _mcr.render(str(rigged_mesh),
                                str(output_dir / f"{run_id}_MOUVEMENT_GEOMETRIE.png"),
                                frames=8)
            audit.append({"stage": "motion_clay", **{k: v for k, v in _clay.items()
                                                     if k != "frames_dir"}})
            if _clay.get("ok"):
                print("PROGRESS:animation:planche argile du mouvement ecrite "
                      "(%d instants, variation %s)" % (_clay.get("frames", 0),
                                                       _clay.get("variation")),
                      flush=True)
            else:
                print("PROGRESS:animation:planche argile impossible (%s)"
                      % str(_clay.get("error"))[:80], flush=True)
        except Exception as _mce:  # noqa: BLE001
            audit.append({"stage": "motion_clay", "ok": False, "error": repr(_mce)})

    # STATIQUE UNIQUEMENT. Avec rigged_mesh ici, la chaine materiaux->matte
    # s'appliquait au modele ANIME: le "modele" livre contenait la danse, et
    # juges/rendus/viewer regardaient une FRAME de mouvement — d'ou "bras
    # fondus", "penche", "il tourne sur lui-meme" (verdicts utilisateur), des
    # semaines de fausses pistes. Le fichier anime a sa propre voie.
    final_delivery_mesh = final_mesh_path
    if material_intel_enabled and material_manifest_data is not None:
        try:
            import glb_material_writer as _gmw
            _mw_out = str(output_dir / f"{run_id}_final_materials.glb")
            _mw_res = _gmw.apply_manifest(str(final_delivery_mesh),
                                          material_manifest_data, _mw_out,
                                          alpha_fallback=False)
            # GARDE D'INTEGRITE GEOMETRIQUE. Cet ecrivain a DESINTEGRE un
            # modele (bisection 25/07: mesh_ao parfait -> final_materials en
            # poussiere/mini, matte herite). Une etape doit PROUVER qu'elle
            # n'a pas detruit la geometrie: faces identiques, bbox stable,
            # sinon elle est annulee et la chaine continue sur le fichier sain.
            if _mw_res.get("ok"):
                try:
                    import numpy as _np_ig
                    import trimesh as _tm_ig
                    _avant = _tm_ig.load(str(final_delivery_mesh),
                                         force="mesh", process=False)
                    _apres = _tm_ig.load(_mw_out, force="mesh", process=False)
                    _ea = _avant.bounds[1] - _avant.bounds[0]
                    _eb = _apres.bounds[1] - _apres.bounds[0]
                    _der = float(_np_ig.abs(_eb - _ea).max()
                                 / max(float(_ea.max()), 1e-6))
                    # un ecrivain de MATERIAUX ne deplace AUCUN sommet: la
                    # corruption "penchee" passait bbox+faces (invariants trop
                    # laches). Comparaison directe des positions.
                    _depl = 1e9
                    if len(_apres.vertices) == len(_avant.vertices):
                        _n_ech = min(20000, len(_avant.vertices))
                        _ids = _np_ig.random.default_rng(7).choice(
                            len(_avant.vertices), _n_ech, replace=False)
                        _depl = float(_np_ig.linalg.norm(
                            _np_ig.asarray(_apres.vertices)[_ids]
                            - _np_ig.asarray(_avant.vertices)[_ids],
                            axis=1).max()) / max(float(_ea.max()), 1e-6)
                    if (len(_apres.faces) != len(_avant.faces)) or _der > 0.02 \
                            or _depl > 1e-4:
                        _mw_res = {"ok": False,
                                   "error": "integrite geometrique violee "
                                            "(faces %d->%d, derive bbox %.1f%%)"
                                            % (len(_avant.faces),
                                               len(_apres.faces), 100 * _der)
                                            + (", deplacement sommets %.4f"
                                               % _depl if _depl < 1e9 else
                                               ", nb sommets change")}
                        print("PROGRESS:matieres:etape ANNULEE — integrite "
                              "geometrique violee, mesh precedent conserve",
                              flush=True)
                        try:
                            os.remove(_mw_out)
                        except OSError:
                            pass
                except Exception as _ige:  # noqa: BLE001
                    audit.append({"stage": "material_write_integrite",
                                  "ok": False, "error": repr(_ige)})
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

    # v79w — Native texture precision (position-independent). Kills the baked
    # cream/yellow tint + medium shadow bake on "white/light plastic" regions
    # of TRELLIS.2 atlases. Purely chroma clamp + value floor on an HSV mask,
    # NO spatial op (blur/dilate/CLAHE), so it can't reveal atlas UV islands.
    # Opt-in via AURORA_NATIVE_PRECISION=1 (auto-set by --max-precision).
    # Skipped silently if the mesh has no baseColorTexture (procedural, etc.).
    if os.environ.get("AURORA_NATIVE_PRECISION") == "1":
        try:
            import native_texture_precision as _prec
            _prec_out = str(output_dir / f"{run_id}_final_precision.glb")
            _prec_res = _prec.run(
                str(final_delivery_mesh), _prec_out,
                delight_strength=float(os.environ.get("AURORA_PRECISION_STRENGTH", "0.55")),
                clahe_clip=float(os.environ.get("AURORA_PRECISION_CLAHE", "0.0")),
                clahe_tile=int(os.environ.get("AURORA_PRECISION_TILE", "32")),
            )
            audit.append({"stage": "native_texture_precision", **{
                k: v for k, v in _prec_res.items() if k not in ("input", "output")
            }, "output": _prec_out})
            if _prec_res.get("ok"):
                final_delivery_mesh = _prec_out
                print("PROGRESS:matieres:precision native appliquee "
                      f"(chroma killed {_prec_res.get('delight',{}).get('chroma_killed',0)}, "
                      f"band lifted {_prec_res.get('delight',{}).get('band_lifted',0)})",
                      flush=True)
        except Exception as exc:  # noqa: BLE001
            audit.append({"stage": "native_texture_precision", "ok": False,
                          "error": repr(exc)})
    else:
        audit.append({"stage": "native_texture_precision", "skipped": True,
                      "reason": "AURORA_NATIVE_PRECISION=0 (opt-in)"})

    # VISAGE : le generateur re-echantillonne sa reference a 518 px -> sur un cadrage
    # plein-pied la tete n'y fait plus que ~55 px, et il ne peut pas sculpter des yeux
    # qu'il ne voit pas (d'ou les yeux en pastilles et la barbe en bouillie). Mais
    # l'information EXISTE: la reference, elle, a un visage net aux yeux ouverts.
    # On la reprojette donc sur la tete, recalee par ses 5 reperes faciaux (le
    # detecteur les donne sur la reference ET sur un rendu ortho du mesh), puis par
    # flot optique. Mesure dans le vrai viewer: nettete du visage +90%/+60%/+125%.
    # No-op silencieux si aucun visage n'est detecte (objet, animal, vehicule...).
    if os.environ.get("AURORA_FACE_REFINE", "1") == "1":
        try:
            _fr_script = str(REPO_ROOT / "application" / "python-services" / "face_refine.py")
            _fr_out = str(output_dir / f"{run_id}_face.glb")
            _fr_cmd = [sys.executable, _fr_script, str(final_delivery_mesh),
                       _fr_out, "--views", "3", "--res", "1024",
                       "--strength", os.environ.get("AURORA_FACE_STRENGTH", "0.85")]
            if front_ref.is_file():
                _fr_cmd += ["--reference", str(front_ref)]
            _fr = subprocess.run(_fr_cmd, capture_output=True, text=True,
                                 timeout=2400, check=False)
            _fr_res = {}
            for _line in (_fr.stdout or "").splitlines():
                if _line.startswith("AURORA_FACE_REFINE_RESULT "):
                    _fr_res = json.loads(_line.split(" ", 1)[1])
            if _fr_res.get("ok") and os.path.isfile(_fr_out) and os.path.getsize(_fr_out) > 1000:
                final_delivery_mesh = _fr_out
                audit.append({"stage": "face_refine", "ok": True,
                              "front_azimuth": _fr_res.get("front_azimuth"),
                              "views": len(_fr_res.get("views") or []),
                              "texels": _fr_res.get("texels"), "output": _fr_out})
            else:
                audit.append({"stage": "face_refine", "skipped": True,
                              "reason": _fr_res.get("error") or "aucun visage"})
        except Exception as _fre:  # noqa: BLE001
            audit.append({"stage": "face_refine", "ok": False, "error": repr(_fre)})

    # REALISME MATIERE : les materiaux generes sortent bien trop glossy (rugosite
    # effective ~0.35) -> sous l'IBL studio du viewer tout parait plastique mouille
    # (t-shirt = latex, pomme = boule miroir). On releve la rugosite des surfaces
    # DIELECTRIQUES OPAQUES a un plancher satin (metal/verre intacts). Verifie via
    # le vrai viewer three.js : difference spectaculaire (homme mat/realiste).
    if os.environ.get("AURORA_ROUGHNESS_REALISM", "1") == "1":
        try:
            import shutil as _sh
            _rr_script = str(REPO_ROOT / "application" / "python-services" / "roughness_realism.py")
            _rr_out = str(output_dir / f"{run_id}_matte.glb")
            _blender = os.environ.get("AURORA_BLENDER") or _sh.which("blender") or "blender"
            _gloss_requested = re.search(r"\b(glossy|glazed|polished|brillant|brillante|verni|vernie)\b", prompt, re.I)
            _rr_floor = os.environ.get("AURORA_ROUGHNESS_FLOOR", "0.18" if _gloss_requested else "0.62")
            _rr = subprocess.run([_blender, "-b", "-P", _rr_script, "--",
                                  str(final_delivery_mesh), _rr_out, _rr_floor],
                                 capture_output=True, text=True, timeout=600, check=False)
            if "ROUGH_REALISM_OK" in (_rr.stdout or "") and os.path.isfile(_rr_out) and os.path.getsize(_rr_out) > 1000:
                final_delivery_mesh = _rr_out
                audit.append({"stage": "roughness_realism", "ok": True,
                              "floor": float(_rr_floor), "output": _rr_out})
            else:
                audit.append({"stage": "roughness_realism", "ok": False,
                              "error": (_rr.stderr or _rr.stdout or "")[-200:]})
        except Exception as _rre:  # noqa: BLE001
            audit.append({"stage": "roughness_realism", "ok": False, "error": repr(_rre)})

    # ── GEOMETRIE PURE (toujours produite) ──────────────────────────────────
    # Demande utilisateur: parmi les nombreux fichiers (matte, ao, rough,
    # final_materials...) on ne distingue pas la geometrie. On produit donc
    # SYSTEMATIQUEMENT un rendu blanc mat, sans texture ni couleur, clairement
    # nomme GEOMETRIE — pour juger le lissage, les details et la progression
    # d'une generation a l'autre. Desactivable: AURORA_GEOMETRIE=0.
    if os.environ.get("AURORA_GEOMETRIE", "1") == "1":
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from mesh_screenshot import render_mesh_screenshots as _rms  # noqa: WPS433
            _geo_png = str(output_dir / f"{run_id}_GEOMETRIE.png")
            print("PROGRESS:geometrie:rendu de la geometrie pure (blanc mat, sans texture)...",
                  flush=True)
            _geo = _rms(mesh_path=str(final_delivery_mesh), output_path=_geo_png,
                        views=["front", "left", "back", "right"],
                        resolution=(900, 900), clay=True)
            audit.append({"stage": "geometrie_pure", "ok": bool(_geo.get("ok")),
                          "vues": [s.get("path") for s in (_geo.get("screenshots") or [])],
                          "sommets": _geo.get("vertex_count"),
                          "faces": _geo.get("face_count"),
                          "error": _geo.get("error")})
        except Exception as _geoe:  # noqa: BLE001
            audit.append({"stage": "geometrie_pure", "ok": False, "error": repr(_geoe)})

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
    # l'acceptation ne juge le MOUVEMENT que s'il a ete DEMANDE (explicite ou
    # reellement decrit) — jamais sur une derive par copie du prompt.
    final_acceptance = run_final_acceptance(
        final_delivery_mesh, prompt, kind,
        motion_prompt if not _motion_derive or rigged_mesh else None)
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

    # LIVRAISON ORGANISEE. Sans elle, tout finissait melange dans models/
    # (GLB + photos + prompt en double) et references/ ne contenait que des
    # vues abandonnees. Chaque chose a UN dossier lisible; versions couleurs
    # ET geometrie pure pour le modele et le mouvement; intermediaires dans
    # travail/. AURORA_ORGANISER=0 pour debrayer.
    livraison = {}
    if os.environ.get("AURORA_ORGANISER", "1") == "1":
        try:
            # PORTE DE PERFECTION (doctrine 25/07: « c'est a mon IA de dire
            # s'il est parfait ou non sinon il refait »). Le pipeline repare
            # (trous, orientation espace-brut, gouttieres) puis JUGE contre la
            # reference. parfait=false => LIVRAISON REFUSEE: on ne livre
            # jamais un fichier trompeur.
            try:
                from perfection_gate import porte as _porte, porte_structure as _porte_struct
                _ref_juge = str(front_ref) if front_ref.is_file() else None
                # Only judge the selected deliverable, never a failed intermediate export.
                _cand_final = final_delivery_mesh
                # LE MATTE SEUL NE VOIT JAMAIS LES COULEURS. _cand_final est
                # sans texture (silhouette/forme uniquement) — le VRAI livrable
                # texture (final_delivery_mesh, celui qui devient
                # modele_couleurs.glb) n'etait jamais regarde par le juge: une
                # projection de couleur ratee (mesure: face tachee/noire)
                # passait tout droit jusqu'a l'utilisateur. On le juge aussi,
                # seulement s'il differe du matte deja prevu.
                _cand_tex = (final_delivery_mesh if final_delivery_mesh
                             and Path(str(final_delivery_mesh)).is_file()
                             and Path(str(final_delivery_mesh)) != Path(str(_cand_final or ""))
                             else None)
                for _cible in (_cand_final, _cand_tex, rigged_mesh):
                    if not (_cible and Path(str(_cible)).is_file()):
                        continue
                    # le fichier ANIME (rigged_mesh) est juge a une pose
                    # arbitraire du mouvement (aucune frame fixee au rendu de
                    # controle) — le comparer a une photo immobile refusait a
                    # tort CHAQUE generation animee (verifie: score 25 identique
                    # sur 2 tirages TRELLIS independants -> bug de methode, pas
                    # de hasard de tirage). Le personnage est deja valide par
                    # le fichier statique juge juste avant; seule la coherence
                    # structurelle (rig qui fusionne/eparpille la geometrie)
                    # reste a verifier ici.
                    if _cible == rigged_mesh:
                        _v = _porte_struct(str(_cible))
                    else:
                        _v = _porte(str(_cible), _ref_juge, contexte=prompt)
                    audit.append({"stage": "perfection_gate",
                                  "fichier": Path(str(_cible)).name, **_v})
                    print("PROGRESS:perfection:%s — score %s, %s"
                          % (Path(str(_cible)).name, _v.get("score"),
                             ("PARFAIT" if _v.get("parfait")
                              else "defauts: " + "; ".join(_v.get("defauts") or [])[:160]),
                             ), flush=True)
                    if not _v.get("parfait") and os.environ.get(
                            "AURORA_PERFECTION_STRICTE", "1") == "1":
                        return {
                            "ok": False,
                            "error": "perfection_gate: %s refuse (%s)"
                                     % (Path(str(_cible)).name,
                                        "; ".join(_v.get("defauts") or [])[:300]),
                            # L'IDENTIFIANT DE TACHE SURVIT AU REFUS. Il ne
                            # decrit pas la qualite du rendu: c'est la poignee
                            # qui permet de rigger et d'ANIMER le maillage sans
                            # le re-televerser. En le laissant tomber ici, un
                            # personnage refuse arrivait chez l'orchestrateur
                            # avec tache=None -> "aucune tache de service, le
                            # personnage reste fige": ni squelette, ni marche,
                            # ni passage debout->assis (mesure: studio VIZION,
                            # aucun dossier mouvement/ produit).
                            "tache_service": _tache_service,
                            "final_mesh": str(final_mesh_path),
                            "audit_trail": audit,
                        }
            except Exception as _pge:  # noqa: BLE001
                audit.append({"stage": "perfection_gate", "ok": False,
                              "error": repr(_pge)})
                return {"ok": False, "error": f"quality validation unavailable: {_pge}",
                        "final_mesh": str(final_delivery_mesh), "audit_trail": audit}

            # DILATATION D'ATLAS avant rangement: les gouttieres sombres entre
            # ilots UV mouchetaient tout le modele aux coutures (verifie
            # Pikachu 25/07: peau poivree -> propre apres remplissage par le
            # texel valide le plus proche).
            try:
                from atlas_dilate import dilater as _dilater
                for _g in (final_mesh_path, rigged_mesh):
                    if _g and Path(str(_g)).is_file():
                        _dr = _dilater(str(_g))
                        audit.append({"stage": "atlas_dilate",
                                      "fichier": Path(str(_g)).name,
                                      "ok": bool(_dr.get("ok"))})
            except Exception as _de:  # noqa: BLE001
                audit.append({"stage": "atlas_dilate", "ok": False,
                              "error": repr(_de)})
            from livraison_organisee import organiser as _organiser
            _run_root = output_dir.parent if output_dir.name == "models" else output_dir
            livraison = _organiser(
                _run_root, run_id,
                # 30/07 (audit): on emballait final_mesh_path, FIGE avant la
                # chaine qualite — la livraison n'etait PAS le fichier juge
                # (sans visage reprojete, sans rugosite, sans matieres). Le
                # GLB livre est desormais exactement celui que la porte a vu.
                final_mesh=str(final_delivery_mesh or final_mesh_path) if (final_delivery_mesh or final_mesh_path) else None,
                rigged_mesh=str(rigged_mesh) if rigged_mesh else None,
                front_reference=str(front_ref) if front_ref.is_file() else None)
            audit.append({"stage": "livraison", **{k: v for k, v in livraison.items()
                                                   if k != "deplaces"}})
            if not livraison.get("ok"):
                return {"ok": False, "error": "delivery validation failed: " + str(livraison.get("error")),
                        "audit_trail": audit}
            if livraison.get("ok"):
                _liv = livraison.get("livraison") or {}
                if _liv.get("modele_couleurs"):
                    final_mesh_path = _liv["modele_couleurs"]
                if _liv.get("mouvement_couleurs"):
                    rigged_mesh = _liv["mouvement_couleurs"]
                print("PROGRESS:livraison:arborescence rangee — modele/, "
                      "mouvement/, reference/, prompt/, journal/, travail/",
                      flush=True)
                # Dossier representatif a la racine d'output/3d (ex: pbr_happy_fairy_tail_pack)
                try:
                    _raw_name = (prompt or (kind or "subject")).strip()
                    _clean_slug = re.sub(r'[^a-zA-Z0-9]+', '_', _raw_name.lower()).strip('_')[:40]
                    if _clean_slug:
                        _out_parent = _run_root.parent if _run_root.name != "3d" else _run_root
                        _pack_dir = _run_root.parent / f"pbr_{_clean_slug}_pack"
                        if _pack_dir.resolve() != _run_root.resolve():
                            if os.path.islink(_pack_dir) or _pack_dir.exists():
                                try:
                                    _pack_dir.unlink(missing_ok=True)
                                except Exception:
                                    pass
                            _pack_dir.symlink_to(_run_root.name, target_is_directory=True)
                            print(f"PROGRESS:livraison:dossier representatif disponible -> {_pack_dir.name}", flush=True)
                except Exception as _se:  # noqa: BLE001
                    pass
        except Exception as _oe:  # noqa: BLE001
            audit.append({"stage": "livraison", "ok": False, "error": repr(_oe)})
            return {"ok": False, "error": f"delivery failed: {_oe}", "audit_trail": audit}

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
    # 30/07 (audit): l'audit_trail ne vivait que dans le JSON stdout — sur un
    # run UI il n'atterrissait jamais dans le dossier visible par
    # l'utilisateur. Regle « tout teste doit etre emis sur conversation »:
    # le journal complet est ecrit dans journal/audit.json a CHAQUE fin de run.
    try:
        _jdir2 = (output_dir.parent if output_dir.name == "models" else output_dir) / "journal"
        _jdir2.mkdir(parents=True, exist_ok=True)
        (_jdir2 / "audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
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
        "tache_service": _tache_service,
        "rescued_mesh": rescue["final_mesh"],
        "final_mesh": str(final_mesh_path if not rigged_mesh else rigged_mesh),
        "livraison": (livraison.get("livraison") if isinstance(livraison, dict) else None),
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
    # ANTI-GEL: tout le pipeline (et ses sous-process) sous plafond memoire cgroup.
    # Une etape qui deborde meurt proprement — le PC ne gele jamais (thrash swap).
    _reexec_under_mem_scope()
    _freeze_sentinel()
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
    parser.add_argument("--no-scene", action="store_true", help="Desactive scene orchestrator pour eviter la recursion")
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
    parser.add_argument("--synthetic-reference", action="store_true",
                        dest="synthetic_reference",
                        help="Marque la/les --image comme generees par le pipeline "
                             "lui-meme (FLUX) a partir du TEXTE, et non comme des "
                             "photos fournies par l'utilisateur. Une reference "
                             "synthetisee n'interdit donc PAS la scene multi-objets : "
                             "une photo reelle reste un sujet unique, une image de "
                             "synthese qui n'en montre qu'un seul ne doit pas ecraser "
                             "les autres objets demandes par le texte.")
    parser.add_argument("--max-precision", action="store_true", dest="max_precision",
                        help="Qualite maximale: TRELLIS.2 1536_cascade avec allocateur "
                             "manage (spill RAM) + passe vision materiaux + MV-Adapter "
                             "UV-aware re-texturing pour reproductions hard-surface (produit, "
                             "vehicule, PC, gadget) — brise le plafond de precision atlas TRELLIS.")
    parser.add_argument("--confirm-ref", action="store_true", dest="confirm_ref",
                        help="Mode interactif (UI): pause pour validation vert/rouge de "
                             "la reference puis du lot de vues derivees (protocole "
                             "fichier request/answer + PROGRESS:confirm_req).")
    parser.add_argument("--dry-run-prompt", action="store_true", dest="dry_run_prompt",
                        help="Build and print the FLUX prompt (extract_kind + "
                             "enhance_flux_prompt + faithful-scene contract) WITHOUT "
                             "running FLUX/Hunyuan3D. Verifies prompt fidelity offline.")
    parser.add_argument("--engine", choices=["auto", "hunyuan3d", "trellis"], default="auto",
                        help="Select 3D neural generation engine: hunyuan3d (ideal for electronics, hardware, detailed relief, complex textures), trellis (single-image organic/character), or auto (intelligent routing)")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    if args.confirm_ref:
        os.environ["AURORA_REF_CONFIRM"] = "1"
    if args.synthetic_reference and args.images:
        # Enregistre les references synthetisees: run_pipeline les ignore pour
        # la decision "scenes ou objet unique" (voir plus haut). Le separateur
        # "::" evite toute collision avec un chemin reel.
        os.environ["AURORA_SYNTHETIC_REFERENCES"] = "::".join(str(p) for p in args.images)
        print("PROGRESS:scene:reference(s) marquee(s) synthetisee(s) — la scene "
              "multi-objets reste eligible au decoupage", flush=True)
    if args.max_precision:
        os.environ.setdefault("AURORA_TRELLIS2_MANAGED", "0")
        os.environ.setdefault("AURORA_TRELLIS2_QUALITY", "1536_cascade")
        os.environ.setdefault("AURORA_VLM_MATERIALS", "1")
        os.environ.setdefault("AURORA_NORMAL_RES", "8192")
        os.environ.setdefault("AURORA_NATIVE_PRECISION", "1")
        os.environ.setdefault("AURORA_MVADAPTER_MV", "1")
        os.environ.setdefault("AURORA_TRELLIS2_TEXTURE", "8192")
        os.environ.setdefault("AURORA_TRELLIS2_16K", "1")

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

    _essais_max = int(os.environ.get("AURORA_PERFECTION_ESSAIS", "4"))
    if args.motion_prompt:
        os.environ.setdefault("AURORA_MOTION_ORIGINAL", args.motion_prompt)
    if args.prompt:
        os.environ.setdefault("AURORA_PROMPT_ORIGINAL", args.prompt)

    for _essai in range(1, _essais_max + 1):
        result = run_pipeline(
            args.prompt, args.run_id,
            output_dir=Path(args.output_dir),
            multi_view=mv, force=args.force,
            motion_prompt=args.motion_prompt,
            images=args.images or None,
            purpose=args.purpose,
            subject_kind_hint=args.subject_kind,
            engine=args.engine, allow_scene=not args.no_scene,
        )
        _err = str(result.get("error") or "")
        _refus = (not result.get("ok")) and (
            _err.startswith("perfection_gate:")
            or "final acceptance rejected" in _err)
        # le score du refus voyage dans _err pour l'archivage
        if _refus and "score" not in _err:
            for _e2 in (result.get("audit_trail") or [])[::-1]:
                if _e2.get("stage") == "perfection_gate":
                    _err += " score %s" % _e2.get("score")
                    break
        if not _refus or _essai >= _essais_max:
            break
        print("PROGRESS:perfection:REFUS essai %d/%d — purge et regeneration "
              "(%s)" % (_essai, _essais_max, _err[:120]), flush=True)
        try:
            import re as _re
            import shutil as _shu
            # `args.output_dir` est la RACINE DU MODULE (output/3d), pas le
            # dossier de ce run. Le critere « le dossier CONTIENT le run-id »
            # (30/07) y etait donc toujours vrai, et la purge faisait
            # `rm -rf output/3d`: TOUS les projets du module partaient avec
            # l'essai refuse. Paye le 26/08 — une scene de 463 Mo et deux
            # sous-projets detruits par le refus d'un run sans rapport.
            # On ne purge que le dossier DE CE RUN, jamais la racine.
            _racine = Path(args.output_dir)
            _rd = _racine / args.run_id
            if not _rd.is_dir():
                _rd = next((d for d in _racine.iterdir()
                            if d.is_dir() and args.run_id in d.name), None)
            if (_rd is not None and _rd.is_dir()
                    and _rd.resolve() != _racine.resolve()
                    and _racine.resolve() in _rd.resolve().parents):
                # ARCHIVER l'essai refuse avant purge: les tirages varient
                # enormement — jeter le meilleur d'hier pour un pire demain a
                # deja coute un excellent mesh. Le score est dans le nom.
                _sc = "xx"
                _m = _re.search(r"score (\d+)", _err)
                if _m:
                    _sc = _m.group(1)
                _arch = _rd.parent / ("essais_" + args.run_id)
                _arch.mkdir(parents=True, exist_ok=True)
                for _cand in _rd.glob("*_matte.glb"):
                    _shu.copyfile(_cand, _arch / ("essai%d_score%s.glb"
                                                  % (_essai, _sc)))
                # la REFERENCE part avec l'essai: sans elle, aucun juge ne
                # peut re-evaluer l'archive (paye: archive muette).
                for _cand in _rd.glob("*_reference.png"):
                    _shu.copyfile(_cand, _arch / "reference.png")
                _shu.rmtree(_rd, ignore_errors=True)
                _rd.mkdir(parents=True, exist_ok=True)
        except Exception as _pe:  # noqa: BLE001
            print("PROGRESS:perfection:purge impossible (%r)" % (_pe,), flush=True)
    if args.pretty:
        sys.stdout.write(render_pretty(result))
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
