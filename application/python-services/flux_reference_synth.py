#!/usr/bin/env python
"""Aurora FLUX reference image synthesizer — generates the front-view PNG
needed to drive Hunyuan3D end-to-end without the React UI.

Builds a minimal FLUX workflow JSON, POSTs to ComfyUI /prompt, polls
/history/<prompt_id> for completion, and copies the result into
application/output/3d/<run_id>_reference.png so the rest of the rescue
chain can pick it up.

Usage:
    python flux_reference_synth.py --prompt "<text>" --run-id <id>
    python flux_reference_synth.py --prompt "..." --run-id catX --width 1024 \\
        --height 1024 --steps 25 --pretty

Schema: aurora.flux_synth.v1.

Defaults match what the ModelView FLUX path uses: 1024x1024, 25 steps,
flux1-dev-fp8 + t5xxl + clip_l + ae.
"""

from __future__ import annotations

import argparse
import os
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from random import randint


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "application" / "output" / "3d"
COMFY_BASE = "http://127.0.0.1:8188"

# Model names — matched against /object_info/UNETLoader etc.
#
# FLUX.1 (et NON FLUX.2). Cause racine mesuree le 2026-07-22: les fichiers FLUX.2
# du disque sont des TELECHARGEMENTS TRONQUES de 133 octets (en-tete safetensors
# seul, zero tenseur). ComfyUI y lit "33813MB de tenseurs declares", tente de les
# charger depuis 133 octets, lit hors limites et SEGFAULTE (core dump) — ce qui
# entrainait ensuite l'effondrement de la session graphique. L'erreur
# "Could not find schema for aten::matmul" avait la meme origine (encodeur texte
# mistral_3_small_flux2_fp8 = 133 octets lui aussi).
# La pile FLUX.1 ci-dessous est REELLE et COMPLETE (unet 17.2G + t5xxl 4.9G +
# clip_l 246M + ae 335M); c'est elle qui a produit toutes les generations
# reussies, et un job de controle a rendu une image en 5.72 s.
# Pour repasser a FLUX.2: telecharger les VRAIS poids, puis definir
# AURORA_FLUX_UNET / AURORA_FLUX_VAE / AURORA_FLUX_CLIP.
# FLUX.2 en GGUF Q4_K_M (18.7 Go). Le fp8mixed (33 Go) a GELE la machine: mesure
# du 2026-07-23 03:41-03:43, ComfyUI monte a 25.2 Go RSS + 14 Go VRAM sur 30 Go ->
# 2.7 Go libres, pression memoire 82%, journal coupe net. Le Q4_K_M a l'empreinte
# de FLUX.1 (17 Go) qui tournait sans effort, en gardant les capacites FLUX.2.
DEFAULT_UNET = os.environ.get("AURORA_FLUX_UNET", "flux2-dev-Q4_K_M.gguf")
# Encodeur texte sur CPU: le fp8 COMPLET (16.8 Go) ne tient pas dans 15.8 Go de
# VRAM, mais sur CPU il donne un resultat IDENTIQUE (encodage deterministe) sans
# aucune perte de qualite — contrairement a une version quantifiee fp4. Cout: ~1 min.
CLIP_DEVICE = os.environ.get("AURORA_FLUX_CLIP_DEVICE", "cpu")
DEFAULT_VAE = os.environ.get("AURORA_FLUX_VAE", "flux2-vae.safetensors")
DEFAULT_CLIP = os.environ.get("AURORA_FLUX_CLIP", "mistral_3_small_flux2_fp8.safetensors")
DEFAULT_CLIP2 = os.environ.get("AURORA_FLUX_CLIP2", "")  # FLUX.2 = encodeur unique (Mistral)

# Taille minimale plausible d'un poids de modele. En dessous, le fichier est un
# telechargement tronque / un pointeur LFS: le signaler AVANT de faire segfauter
# ComfyUI (le message d'erreur remonte alors jusqu'a l'UI).
_MIN_MODEL_BYTES = 8 * 1024 * 1024


def check_models_present(comfy_models_dir: str | None = None) -> dict:
    """Verifie que les poids references existent VRAIMENT (pas des stubs tronques).

    Retourne {"ok": bool, "stubs": [...], "missing": [...]}. Best-effort: si le
    dossier des modeles est introuvable on ne bloque rien.
    """
    root = Path(comfy_models_dir or (REPO_ROOT / "modele" / "comfyui" / "models"))
    if not root.is_dir():
        return {"ok": True, "stubs": [], "missing": [], "skipped": True}
    _names = {DEFAULT_UNET, DEFAULT_VAE, DEFAULT_CLIP}
    if DEFAULT_CLIP2:
        _names.add(DEFAULT_CLIP2)
    wanted = [("unet", DEFAULT_UNET), ("diffusion_models", DEFAULT_UNET),
              ("vae", DEFAULT_VAE), ("clip", DEFAULT_CLIP),
              ("text_encoders", DEFAULT_CLIP), ("text_encoders", DEFAULT_CLIP2),
              ("clip", DEFAULT_CLIP2)]
    stubs, seen_ok = [], set()
    for sub, name in wanted:
        if not name:
            continue
        p = root / sub / name
        if not p.is_file():
            continue
        if p.stat().st_size < _MIN_MODEL_BYTES:
            stubs.append("%s (%d octets)" % (p, p.stat().st_size))
        else:
            seen_ok.add(name)
    missing = [n for n in _names if n not in seen_ok]
    return {"ok": not stubs and not missing, "stubs": stubs, "missing": missing}


def build_workflow(prompt: str, *, width: int = 1024, height: int = 1024,
                   steps: int = 25, seed: int | None = None,
                   filename_prefix: str = "aurora_flux") -> dict:
    """FLUX.2-dev workflow (encodeur Mistral-3, Flux2Scheduler + SamplerCustomAdvanced).
    Poids REELS presents (diffusion 33 Go + Mistral 16.8 Go + VAE 0.31 Go).
    Miroir du template officiel ComfyUI image_flux2_text_to_image."""
    if seed is None:
        seed = randint(1, 2**32 - 1)
    return {
        "11": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": DEFAULT_CLIP, "type": "flux2",
                       "device": CLIP_DEVICE},
        },
        "12": ({
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": DEFAULT_UNET},
        } if str(DEFAULT_UNET).lower().endswith(".gguf") else {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": DEFAULT_UNET, "weight_dtype": "default"},
        }),
        "10": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": DEFAULT_VAE},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["11", 0], "text": prompt},
        },
        "33": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["11", 0], "text": "cropped, cut off, out of frame, partial view, close-up, truncated body, missing limbs, blurry, low detail"},
        },
        "27": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "40": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": steps, "width": width, "height": height},
        },
        "41": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "26": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["12", 0], "positive": ["6", 0],
                       "negative": ["33", 0], "cfg": 5.0},
        },
        "42": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "31": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["42", 0], "guider": ["26", 0],
                       "sampler": ["41", 0], "sigmas": ["40", 0],
                       "latent_image": ["27", 0]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["31", 0], "vae": ["10", 0]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": filename_prefix},
        },
    }


def _unload_ollama() -> None:
    """Decharge les modeles Ollama residents AVANT de charger FLUX2.

    Mort mesuree a la boite noire (12:34-12:43): llama-server 17.4G (appels LLM
    du pipeline, service systeme NON plafonne) + ComfyUI/FLUX2 25G = 42G sur
    30G -> pression memoire 94%, agonie, gel. Les appels LLM sont finis quand
    on arrive ici: keep_alive=0 les evince. Best-effort, ne bloque jamais.
    """
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=8) as r:
            loaded = json.loads(r.read().decode("utf-8")).get("models", [])
        for m in loaded:
            req = urllib.request.Request(
                f"{base}/api/generate",
                data=json.dumps({"model": m.get("name"), "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as rr:
                rr.read()
        if loaded:
            print("PROGRESS:memoire:%d modele(s) Ollama decharges avant FLUX"
                  % len(loaded), flush=True)
    except Exception:  # noqa: BLE001
        pass


def post_prompt(workflow: dict, comfy_base: str = COMFY_BASE) -> str:
    _unload_ollama()
    body = json.dumps({"prompt": workflow}).encode("utf-8")
    last_exc = None
    for attempt in range(5):
        req = urllib.request.Request(
            f"{comfy_base}/prompt", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            pid = data.get("prompt_id")
            if not pid:
                raise RuntimeError(f"ComfyUI /prompt did not return prompt_id: {data}")
            return pid
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"ComfyUI /prompt unreachable after retries: {last_exc}")


class JobLostError(RuntimeError):
    """Le job n'existe plus cote ComfyUI (serveur redemarre en cours de route)."""


def _job_known(prompt_id: str, comfy_base: str) -> bool:
    """Le job est-il encore dans la queue (running/pending) de ComfyUI ?"""
    try:
        with urllib.request.urlopen(f"{comfy_base}/queue", timeout=10) as r:
            q = json.loads(r.read().decode("utf-8"))
        for key in ("queue_running", "queue_pending"):
            for item in q.get(key) or []:
                # format: [number, prompt_id, workflow, ...]
                if len(item) > 1 and item[1] == prompt_id:
                    return True
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return True  # doute -> on ne conclut pas a la perte
    return False


def poll_history(prompt_id: str, *, comfy_base: str = COMFY_BASE,
                 timeout_s: float = 1800.0, interval_s: float = 2.0) -> dict:
    deadline = time.time() + timeout_s
    lost_checks = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{comfy_base}/history/{prompt_id}", timeout=10,
            ) as r:
                data = json.loads(r.read().decode("utf-8"))
            entry = data.get(prompt_id)
            if entry and entry.get("status", {}).get("completed"):
                return entry
            # Job absent de l'historique: encore en queue ? Si ComfyUI a ete
            # tue/redemarre (OOM...), sa queue est VIDE et le job n'existera
            # JAMAIS -> attendre 1h en silence est un faux gel. 5 constats
            # d'absence (~10 s) => JobLostError, l'appelant re-soumet.
            if entry is None and not _job_known(prompt_id, comfy_base):
                lost_checks += 1
                if lost_checks >= 5:
                    raise JobLostError(
                        f"job {prompt_id} absent de la queue et de l'historique "
                        "(ComfyUI redemarre ?) -> re-soumettre")
            else:
                lost_checks = 0
        except JobLostError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            pass
        time.sleep(interval_s)
    raise TimeoutError(f"FLUX prompt {prompt_id} did not finish in {timeout_s}s")


def output_path_from_history(entry: dict, comfy_base: str = COMFY_BASE) -> str:
    """Return the URL to the saved image we can fetch."""
    outputs = entry.get("outputs") or {}
    for _, payload in outputs.items():
        images = payload.get("images") or []
        for img in images:
            filename = img.get("filename")
            subfolder = img.get("subfolder", "")
            if not filename:
                continue
            type_ = img.get("type", "output")
            qs = f"filename={filename}&subfolder={subfolder}&type={type_}"
            return f"{comfy_base}/view?{qs}"
    raise RuntimeError(f"no image output in history entry: {entry}")


def fetch_to(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    dest.write_bytes(data)
    return len(data)


# View-specific prompt suffixes for the multi-view mode. Mirrors what
# multi-view diffusion models inject; we use the same seed across views so
# the subject identity stays stable.
TURNAROUND_CONTRACT = (
    # FIBRE vs MASSE (27/07, mesure): une fibre fait ~0.07 mm quand la cellule
    # de reconstruction fait ~1 mm — Nyquist demanderait x18000 en volume: la
    # MECHE ne sera JAMAIS geometrique, elle appartient a la texture et au
    # materiau (sheen/anisotropie). En revanche la MASSE de fourrure
    # (criniere, collerette, queue touffue, culottes) fait 20-60 mm = 15 a 45
    # cellules: elle DOIT rester geometrique. Le contrat "tout lisse" de la
    # veille aplatissait les deux -> silhouette de levrier, lue comme "ca
    # fond". On separe donc explicitement les deux echelles.
    ", fur and hair as BOLD SCULPTED MASSES with clean readable silhouette "
    "(thick mane, ruff, bushy tail and leg feathering kept as full volumes), "
    "fine fur grain shown as SURFACE TEXTURE only, no isolated flyaway "
    "strands, no wispy hair tufts detached from the body, sharp clean "
    "contour against the background"
    ", STRICT SINGLE-VIEW RECONSTRUCTION REFERENCE, one full-body subject only, "
    "exactly one figure/object in the image, no duplicate copies, no lineup, no triptych, "
    "no contact sheet, no model sheet, no turnaround sheet inside the image, "
    "same exact requested identity, costume, materials, accessories, colors, proportions and hair silhouette, "
    "neutral rig-ready A/T-pose for this single image, both arms held clearly away from the torso "
    "with a visible background gap under each arm, hands and wrists kept well clear of the hips and "
    "thighs and never touching the body, legs slightly apart with a visible gap between the thighs, "
    "both hands and fingers visible outside clothing, hands never in pockets, "
    "feet and shoes fully visible with clear margin around the whole body, "
    "no pose redesign, no outfit redesign, no gender swap, "
    "single centered subject, sharp face and edges, no blur, no duplicate subject, no panel sheet"
)

HUMAN_FIDELITY_CONTRACT = (
    "HIGH-FIDELITY HUMAN/CHARACTER CONTRACT, do not produce a stylized mannequin, toy, chibi, blob, "
    "marshmallow avatar or generic performer, preserve the requested identity and gender, "
    "sharp readable face, eyes, nose, jawline, hair silhouette, costume geometry and material texture, "
    "skin hair clothing and accessories must carry visible texture and color separation, "
    "both hands must be real hands with wrists, palms and separate fingers visible, "
    "no mitten hands, no fused fingers, no hands hidden in sleeves or pockets"
)

ARTICULATED_MOTION_RX = re.compile(
    r"\b("
    r"marche|marcher|walk|walking|court|courir|run|running|"
    r"danse|danser|dance|dancing|macarena|floss|flossing|"
    r"saute|sauter|jump|jumping|kick|punch|wave|salue|saluer|"
    r"applaud|clap|throw|grab|lift|combat|fight"
    r")\b",
    re.I,
)

ARM_CRITICAL_MOTION_RX = re.compile(
    r"\b("
    r"danse|danser|dance|dancing|macarena|floss|flossing|wave|salue|saluer|"
    r"applaud|clap|punch|throw|grab|lift|salute"
    r")\b",
    re.I,
)


def _motion_reference_contract(motion_prompt: str | None) -> str:
    """Extra reference constraints when the final asset must move.

    A static person with hidden hands can still look like a complete image,
    but it is a bad rig source for dance, walk, fight, etc. Keep this contract
    separate from the base prompt so non-moving products are not overconstrained.
    """
    text = (motion_prompt or "").strip()
    if not text or not ARTICULATED_MOTION_RX.search(text):
        return ""
    contract = [
        "MOTION-RIG READY SOURCE, this is a neutral bind-pose reference, not the final action frame",
        "do not show the requested dance/action in the reference image; the final movement will be animated after mesh generation",
        "all major joints readable for animation",
        "arms, elbows, wrists, knees, ankles and hands clearly separated from the torso by visible background gaps",
        "no hands in pockets, no crossed arms, no hidden fingers",
        "strict rig-ready A-pose or T-pose, not a fashion pose",
    ]
    if ARM_CRITICAL_MOTION_RX.search(text):
        contract.extend([
            "expressive arm motion required",
            "both full arms extended away from the torso at shoulder or diagonal A-pose angle",
            "white background visible between each sleeve and the body",
            "open palms or visible hands outside clothing",
            "suit jacket may remain, but sleeves and hands must never touch pockets",
        ])
    return ", " + ", ".join(contract)


def _human_fidelity_contract(prompt: str, subject_kind: str | None,
                             motion_prompt: str | None = None) -> str:
    """Hard prompt block for human/character assets.

    The old procedural fallback could satisfy "there is a body" while missing
    the actual requirement: identity, readable face, textures and real hands.
    Keep this separate so product/machine prompts are not overconstrained.
    """
    kind = (subject_kind or "").lower()
    text = " ".join([prompt or "", motion_prompt or ""]).lower()
    is_character = kind in {"character", "humanoid", "creature"} or re.search(
        r"\b(personnage|personne|human|humain|character|visage|face|mains?|hands?)\b",
        text,
    )
    if not is_character:
        return ""
    block = HUMAN_FIDELITY_CONTRACT
    if re.search(r"\b(anime|manga|fairy\s*tail|shonen)\b", text):
        block += (
            ", anime identity may stay anime-styled only when explicitly requested, "
            "but the 3D asset must still have readable facial features, costume pieces, palms and separate fingers"
        )
    else:
        block += ", photorealistic adult human proportions by default, not cartoon"
    if ARM_CRITICAL_MOTION_RX.search(text):
        block += (
            ", because the motion uses arms/hands, hands must be open enough to verify palm direction "
            "and finger separation in the reference"
        )
    return block

MULTIVIEW_SUFFIXES = {
    "front": ", front view, facing camera, isolated white background, photorealistic 3D reference" + TURNAROUND_CONTRACT,
    "back":  ", back view, rear of subject, no face visible, isolated white background, photorealistic 3D reference" + TURNAROUND_CONTRACT,
    "left":  ", exact left side profile view, 90 degree side view, no front-facing pose, isolated white background, photorealistic 3D reference" + TURNAROUND_CONTRACT,
    "right": ", exact right side profile view, 90 degree side view, no front-facing pose, isolated white background, photorealistic 3D reference" + TURNAROUND_CONTRACT,
}


# Mots par lesquels un HUMAIN demande un style (francais ecrit naturellement,
# accents compris) — teste sur de vraies formulations: "goldorak facon anime",
# "un dragon en dessin anime", "un robot stylise", "style pixar", "facon peluche".
# Piege corrige: "anime" (sans accent) ne matchait PAS "anime" (avec accent),
# et un \b apres "stylis" ne matchait pas "stylise".
_STYLE_RX = re.compile(
    r"(cartoon|dessin[s]?\s*anim|anim[eé]|manga|toon|cel[-\s]?shad|comic|"
    r"bande[-\s]?dessin|\bbd\b|stylis|illustration|dessin|croquis|aquarelle|"
    r"peinture|pixel[-\s]?art|low[-\s]?poly|voxel|chibi|kawaii|"
    r"pixar|disney|ghibli|lego|playmobil|peluche|jouet|figurine\s+cartoon|"
    r"\b2d\b|plat\b|flat\b|retro|vintage|steampunk|cyberpunk|"
    r"aquarel|bd\b|comics?|manhwa|webtoon)",
    re.I)


def _style_demande(texte: str) -> bool:
    """L'utilisateur a-t-il demande un style precis ? (sinon: realiste par defaut)

    Rend True des qu'une intention de style apparait, quelle que soit la tournure:
    "facon X", "style X", "en X", "type X", "version X", "comme dans X".
    """
    return bool(_STYLE_RX.search(texte or ""))


# DETECTION DE COMPOSITION. "un Pikachu" = un sujet seul a detourer; "une ville
# la nuit sous la pluie" = un lieu avec plusieurs elements. Les deux ne se
# cadrent pas pareil et ne se decrivent pas pareil a FLUX.
_SCENE_RX = re.compile(
    r"(paysage|panorama|ville|cit[eé]|village|rue|ruelle|avenue|place\s|quartier|"
    r"gratte[-\s]?ciel|skyline|for[eê]t|montagne|vall[eé]e|d[eé]sert|plage|oc[eé]an|"
    r"mer\b|lac\b|rivi[eè]re|cascade|champ|prairie|jardin|parc\b|jungle|canyon|"
    r"int[eé]rieur|chambre|cuisine|salon|bureau\s|atelier|entrep[oô]t|usine|"
    r"temple|ch[aâ]teau|cath[eé]drale|[eé]glise|pont\b|port\b|gare\b|a[eé]roport|"
    r"march[eé]\b|stade|arene|champ\s+de\s+bataille|camp\b|base\b|station\b|"
    r"scene\b|sc[eè]ne\b|d[eé]cor|environnement|ambiance|coucher\s+de\s+soleil|"
    r"lever\s+de\s+soleil|nuit\b|brouillard|tempete|orage|pluie\b|neige\b|"
    r"landscape|cityscape|city\b|street|forest|mountain|beach|interior|"
    r"background|environment|scenery|skyline)", re.I)

# Marqueurs de PLURALITE / composition: plusieurs sujets ou des relations
# spatiales entre elements = une scene, pas un sujet isole.
_PLURIEL_RX = re.compile(
    r"(\b\w+s\s+(?:et|avec)\s+\w+s\b|\bplusieurs\b|\bgroupe\s+de\b|\bfoule\b|"
    r"\bune\s+dizaine\b|\bdes\s+\w+s\b|\bentour[eé]\s+de\b|\bau\s+milieu\s+de\b|"
    r"\bdevant\s+(?:un|une|le|la|les|des)\b|\bderri[eè]re\s+(?:un|une|le|la|les)\b|"
    r"\bassis\s+sur\b|\bpos[eé]\s+sur\b|\bsur\s+(?:un|une|le|la)\s+\w+\s+dans\b|"
    r"\bdans\s+(?:un|une|le|la)\s+\w+)", re.I)

# Le sujet est explicitement demande SEUL / detoure.
_ISOLE_RX = re.compile(
    r"(seul\b|isol[eé]|d[eé]tour[eé]|fond\s+(?:blanc|neutre|uni|transparent)|"
    r"sans\s+(?:fond|d[eé]cor|arri[eè]re[-\s]?plan)|\bstudio\b|"
    r"white\s+background|isolated|cutout|no\s+background)", re.I)


def composition_de(texte: str) -> str:
    """'scene' (plusieurs elements / un lieu) ou 'solo' (un sujet isole).

    Sert a ne PAS traiter une ville comme une figurine de collection: sans cette
    distinction, la directive realiste "collectible figure, studio product
    photography" s'appliquait a TOUT — un paysage se retrouvait pose sur un
    fond de studio comme un objet sur une table.
    """
    t = texte or ""
    if _ISOLE_RX.search(t):
        return "solo"
    if _SCENE_RX.search(t) or _PLURIEL_RX.search(t):
        return "scene"
    return "solo"


def suggest_resolution(texte: str, base: int = 1024) -> tuple[int, int]:
    """Cadrage adapte a la demande: un sujet debout se cadre en hauteur, un
    lieu se cadre en largeur. Multiples de 64 (contrainte du VAE)."""
    def _r64(v: int) -> int:
        return max(512, int(round(v / 64.0)) * 64)
    if composition_de(texte) == "scene":
        return _r64(base * 1.375), _r64(base * 0.78)   # ~16:9 paysage
    return _r64(base), _r64(base * 1.375)              # ~3:4 portrait


def _single_view_base_prompt(prompt: str) -> str:
    """Remove phrases that make FLUX draw all orthographic views in one image.

    The multi-view pipeline already generates front/back/left/right as separate
    files. Keeping "front/profile/back" wording in every per-view prompt often
    produces a model sheet, which then poisons Hunyuan reconstruction.
    """
    cleaned = prompt
    replacements = [
        r"\b(?:avec\s+)?(?:face|front)\s*,?\s*(?:profil|profile)\s*,?\s*(?:dos|back)\s+(?:coh[eé]rents?|consistent)\b",
        r"\b(?:front|face)\s*/\s*(?:side|profile|profil)\s*/\s*(?:back|dos)\b",
        r"\b(?:turnaround|model\s+sheet|character\s+sheet|contact\s+sheet|reference\s+sheet|planche\s+de\s+r[eé]f[eé]rence)\b",
        r"\b(?:plusieurs|multiple)\s+(?:vues|views)\b",
        r"\b(?:vue|view)s?\s+(?:face|front)\s*,?\s*(?:profil|profile|side)\s*,?\s*(?:dos|back)\b",
    ]
    for pattern in replacements:
        cleaned = re.sub(pattern, "single clean reconstruction view", cleaned, flags=re.I)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.")
    cleaned = cleaned or prompt
    # STYLE REALISTE PAR DEFAUT. Sans directive, FLUX rend un sujet nomme (surtout
    # un perso d'anime comme Goldorak) en illustration cartoon plate — mauvais pour
    # la reconstruction 3D ET non demande par l'utilisateur. On force un rendu 3D
    # realiste (qualite figurine/studio) SAUF si un style est explicitement demande.
    # ... mais la directive n'est pas la meme selon ce qui est demande: un sujet
    # seul se rend comme une piece de collection sur fond neutre, un lieu se rend
    # comme une photographie de ce lieu. Appliquer la formule "figurine studio" a
    # une ville la posait sur une table comme un objet.
    if not _style_demande(cleaned):
        if composition_de(cleaned) == "scene":
            cleaned += (", photorealistic photograph, natural environment lighting, "
                        "wide establishing shot, deep depth of field, coherent "
                        "perspective and scale between elements, fine material and "
                        "surface detail, NOT a flat 2D cartoon or cel-shaded drawing")
        else:
            cleaned += (", realistic 3D render, high-detail collectible figure, studio "
                        "product photography lighting, physically based materials, "
                        "sharp fine surface detail, NOT a flat 2D cartoon or cel-shaded drawing")
    # CHEVEUX EN MASSES SCULPTEES. Mesure sur le guerrier: les meches fines de
    # la reference (0.5-2 mm a l'echelle du modele) sont SOUS la cellule
    # effective de la grille TRELLIS (1.6 mm) -> la tete sort en eponge
    # (~700 tunnels + ~5000 confettis flottants, 7.5x la peau nue). La parade
    # amont: exiger des masses de cheveux pleines, comme une figurine.
    if _re_detecte_sujet_chevelu(cleaned):
        cleaned += (", hair and beard as SOLID SCULPTED MASSES like a collectible "
                    "figurine, thick chunky strands, no thin flying wisps, no "
                    "stray hairs, no frizz")
    return cleaned


_CHEVELU_RX = re.compile(
    r"(homme|femme|guerrier|guerri[eè]re|personnage|humain|soldat|chevalier|"
    r"roi|reine|elfe|nain|barbare|viking|samoura[iï]|sorcier|magicien|"
    r"cheveux|barbe|criniere|crini[eè]re|fourrure|poil|"
    r"man\b|woman|warrior|character|human|knight|hair|beard|fur)", re.I)


def _re_detecte_sujet_chevelu(texte: str) -> bool:
    """Le sujet a-t-il probablement des cheveux/poils ? (humains, creatures)"""
    return bool(_CHEVELU_RX.search(texte or ""))


def _retry_single_view_prompt(prompt: str, attempt_index: int, failures: list[str]) -> str:
    if attempt_index <= 1:
        return prompt
    failure_text = " ; ".join(failures[:6]).lower()
    additions = [
        "STRICT RETRY: generate one single centered full-body subject only",
        "zoomed out camera, empty white margin around head, hands and shoes",
        "no reference sheet, no lineup, no extra side views inside this image",
    ]
    if "bottom frame" in failure_text or "cropped" in failure_text:
        additions.append("feet and shoes must be fully visible with visible white floor margin below them")
    if "wide" in failure_text or "lineup" in failure_text or "multi-subject" in failure_text:
        additions.append("only one body silhouette, narrow vertical composition, no duplicated people")
    if "soft" in failure_text or "blurry" in failure_text:
        additions.append("sharp high-frequency detail, crisp face, crisp clothing edges, no blur")
    if "palette" in failure_text or "diverges" in failure_text:
        additions.append(
            "STRICT IDENTITY/COLOR CONSISTENCY: every view must keep the exact same black suit, "
            "white shirt, black bow tie, skin tone, hair color, beard color, lighting and contrast"
        )
    if "motion-ready" in failure_text or "arms" in failure_text or "hands" in failure_text:
        additions.append(
            "STRICT BIND POSE OVERRIDE: arms extended away from torso, visible white gap around sleeves, "
            "elbows wrists palms and fingers fully visible, hands outside pockets"
        )
    if "profile" in failure_text or "three-quarter" in failure_text or "side view" in failure_text:
        additions.append(
            "STRICT SIDE VIEW OVERRIDE: left and right outputs must be exact 90 degree orthographic side profiles, "
            "one eye and one ear visible, no second eye, no chest-front view, no three-quarter pose"
        )
    return prompt.rstrip(" ,.") + ", " + ", ".join(additions)


def _cleanup_character_reference(path: str | Path) -> dict:
    """Remove common FLUX reference-sheet artifacts from character views.

    FLUX often returns a useful central character plus pale ghost side views.
    For 3D reconstruction, those ghosts are poison. This deterministic cleanup
    keeps the main centered component, whites out pale ghosts, and adds margin.
    """
    try:
        from PIL import Image  # noqa: WPS433
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": f"Pillow unavailable: {type(exc).__name__}"}

    p = Path(path)
    try:
        im = Image.open(p).convert("RGB")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    w, h = im.size
    px = im.load()
    mask = [bytearray(w) for _ in range(h)]
    changed_ghost = 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            brightness = (r + g + b) / 3.0
            chroma = max(r, g, b) - min(r, g, b)
            if r > 242 and g > 242 and b > 242:
                continue
            if brightness > 168 and chroma < 42:
                px[x, y] = (255, 255, 255)
                changed_ghost += 1
                continue
            mask[y][x] = 1

    visited = [bytearray(w) for _ in range(h)]
    components: list[tuple[int, int, int, int, int, float, float]] = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy][sx] or visited[sy][sx]:
                continue
            stack = [(sx, sy)]
            visited[sy][sx] = 1
            area = 0
            minx = maxx = sx
            miny = maxy = sy
            sumx = 0
            sumy = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                sumx += cx
                sumy += cy
                minx = min(minx, cx); maxx = max(maxx, cx)
                miny = min(miny, cy); maxy = max(maxy, cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        continue
                    if mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = 1
                        stack.append((nx, ny))
            if area >= max(80, int(w * h * 0.002)):
                components.append((area, minx, miny, maxx, maxy, sumx / area, sumy / area))

    kept = None
    if components:
        cx0 = w * 0.5
        cy0 = h * 0.54
        diag = (w * w + h * h) ** 0.5
        kept = max(
            components,
            key=lambda c: c[0] * (1.0 - min(0.82, (((c[5] - cx0) ** 2 + (c[6] - cy0) ** 2) ** 0.5) / diag)),
        )
        keep_area, minx, miny, maxx, maxy, *_ = kept
        for y in range(h):
            for x in range(w):
                if not mask[y][x]:
                    continue
                if x < minx or x > maxx or y < miny or y > maxy:
                    px[x, y] = (255, 255, 255)

        pad = int(max(w, h) * 0.045)
        minx = max(0, minx - pad); miny = max(0, miny - pad)
        maxx = min(w - 1, maxx + pad); maxy = min(h - 1, maxy + pad)
        crop = im.crop((minx, miny, maxx + 1, maxy + 1))
        canvas = Image.new("RGB", (w, h), "white")
        target_w = int(w * 0.78)
        target_h = int(h * 0.88)
        scale = min(target_w / max(1, crop.width), target_h / max(1, crop.height), 1.0)
        resized = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
        canvas.paste(resized, ((w - resized.width) // 2, (h - resized.height) // 2))
        im = canvas

    try:
        im.save(p)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "ghost_pixels_whitened": changed_ghost,
        "component_count_before": len(components),
        "kept_area": int(kept[0]) if kept else 0,
    }


def _foreground_metrics(path: str | Path) -> dict:
    """Cheap image QA for references before the heavy 3D stage.

    This deliberately stays deterministic and CPU-only. It does not pretend to
    understand identity like a vision model, but it catches common bad inputs:
    blank views, blurry silhouettes, wildly different palettes, and side views
    that are actually three-quarter/front poses.
    """
    try:
        from PIL import Image, ImageFilter, ImageStat  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"ok": False, "error": f"Pillow unavailable: {type(exc).__name__}"}

    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "missing image", "path": str(p)}

    im = Image.open(p).convert("RGB").resize((256, 256))
    px = im.load()
    xs: list[int] = []
    ys: list[int] = []
    colors: list[tuple[int, int, int]] = []
    mask = [bytearray(256) for _ in range(256)]
    for y in range(256):
        for x in range(256):
            r, g, b = px[x, y]
            is_bg = r > 242 and g > 242 and b > 242
            if is_bg:
                continue
            mask[y][x] = 1
            xs.append(x)
            ys.append(y)
            saturated = max(r, g, b) - min(r, g, b) > 18
            if saturated and max(r, g, b) < 248:
                colors.append((r // 32 * 32, g // 32 * 32, b // 32 * 32))

    if not xs:
        return {"ok": False, "error": "no foreground", "path": str(p)}

    bbox = {
        "x": min(xs) / 256,
        "y": min(ys) / 256,
        "w": (max(xs) - min(xs) + 1) / 256,
        "h": (max(ys) - min(ys) + 1) / 256,
    }
    edges = ImageStat.Stat(im.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
    top = Counter(colors).most_common(10)
    total_color = sum(count for _, count in top) or 1
    palette = [
        {"rgb": list(rgb), "share": round(count / total_color, 4)}
        for rgb, count in top[:8]
    ]

    visited = [bytearray(256) for _ in range(256)]
    component_areas: list[int] = []
    for sy in range(256):
        row = mask[sy]
        for sx in range(256):
            if not row[sx] or visited[sy][sx]:
                continue
            area = 0
            stack = [(sx, sy)]
            visited[sy][sx] = 1
            while stack:
                cx, cy = stack.pop()
                area += 1
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= 256 or ny < 0 or ny >= 256:
                        continue
                    if mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = 1
                        stack.append((nx, ny))
            component_areas.append(area)

    component_areas.sort(reverse=True)
    foreground_area = len(xs) or 1
    significant_floor = max(80, int(foreground_area * 0.035))
    significant_components = [area for area in component_areas if area >= significant_floor]
    largest_share = component_areas[0] / foreground_area if component_areas else 0.0
    return {
        "ok": True,
        "path": str(p),
        "foreground_fraction": round(len(xs) / (256 * 256), 4),
        "bbox": bbox,
        "edge_score": round(edges, 2),
        "palette": palette,
        "connected_component_count": len(component_areas),
        "significant_component_count": len(significant_components),
        "largest_component_share": round(largest_share, 4),
        "component_areas_top5": component_areas[:5],
    }


def _palette_overlap(front: dict, other: dict) -> float:
    def as_map(metric: dict) -> dict[tuple[int, int, int], float]:
        out: dict[tuple[int, int, int], float] = {}
        for entry in metric.get("palette") or []:
            rgb = entry.get("rgb")
            if isinstance(rgb, list) and len(rgb) == 3:
                out[(int(rgb[0]), int(rgb[1]), int(rgb[2]))] = float(entry.get("share") or 0)
        return out

    a = as_map(front)
    b = as_map(other)
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    inter = sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    union = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    return round(inter / union, 4) if union else 0.0


def _motion_pose_requirements(motion_prompt: str | None) -> dict:
    text = (motion_prompt or "").strip()
    if not text or not ARTICULATED_MOTION_RX.search(text):
        return {"requires_articulated_pose": False, "requires_arm_clearance": False}
    return {
        "requires_articulated_pose": True,
        "requires_arm_clearance": bool(ARM_CRITICAL_MOTION_RX.search(text)),
    }


def audit_multiview_consistency(
    view_paths: dict[str, str | Path],
    *,
    subject_kind: str | None = None,
    motion_prompt: str | None = None,
) -> dict:
    """Return a deterministic preflight verdict for generated multi-view refs."""
    required = ("front", "back", "left", "right")
    metrics = {view: _foreground_metrics(view_paths.get(view, "")) for view in required}
    failures: list[str] = []
    motion_requirements = _motion_pose_requirements(motion_prompt)
    for view, metric in metrics.items():
        if not metric.get("ok"):
            failures.append(f"{view}: {metric.get('error') or 'invalid image'}")
            continue
        if metric.get("foreground_fraction", 0) < 0.06:
            failures.append(f"{view}: subject too small or mostly blank")
        bbox = metric.get("bbox") or {}
        if float(bbox.get("h") or 0) < 0.62:
            failures.append(f"{view}: full subject is not readable vertically")
        kind = (subject_kind or "").lower()
        min_edge_score = 9.5 if kind in {"character", "humanoid", "creature", "quadruped"} else 6.0
        if float(metric.get("edge_score", 0) or 0) < min_edge_score:
            failures.append(f"{view}: reference too soft/blurry for reconstruction")
        if kind in {"character", "humanoid", "creature", "quadruped"}:
            bbox_w = float(bbox.get("w") or 0)
            bbox_h = float(bbox.get("h") or 0) or 1.0
            bbox_y = float(bbox.get("y") or 0)
            width_height_ratio = bbox_w / bbox_h
            metric["bbox_width_height_ratio"] = round(width_height_ratio, 4)
            metric["bbox_bottom"] = round(bbox_y + bbox_h, 4)
            if bbox_y + bbox_h > 0.992:
                failures.append(f"{view}: subject touches bottom frame; likely cropped feet/lower body")
            if bbox_w > 0.82 or width_height_ratio > 0.82:  # Aurora: 0.72->0.82, moins declencheur (garde le multivue = evite les "planches" single-view)
                failures.append(f"{view}: subject silhouette is too wide for a single full-body view; likely lineup/model sheet")
            if int(metric.get("significant_component_count") or 0) > 1:
                failures.append(f"{view}: multiple separated subjects detected; likely reference/model sheet")
            if float(metric.get("largest_component_share") or 0) < 0.72:
                failures.append(f"{view}: largest subject does not dominate foreground; likely multi-subject sheet")
            if (motion_requirements["requires_arm_clearance"]
                    and view in {"front", "back"}
                    and width_height_ratio < 0.35):
                failures.append(
                    f"{view}: motion-ready pose too narrow; arms/hands likely hidden or fused to torso"
                )

    front = metrics.get("front") or {}
    if front.get("ok"):
        for view in ("back", "left", "right"):
            metric = metrics.get(view) or {}
            if not metric.get("ok"):
                continue
            overlap = _palette_overlap(front, metric)
            metric["palette_overlap_with_front"] = overlap
            if overlap < 0.16:
                failures.append(f"{view}: palette diverges too much from front reference")

        kind = (subject_kind or "").lower()
        if kind in {"character", "humanoid", "creature", "quadruped"}:
            front_w = float((front.get("bbox") or {}).get("w") or 0)
            if front_w > 0:
                for view in ("left", "right"):
                    metric = metrics.get(view) or {}
                    if not metric.get("ok"):
                        continue
                    side_w = float((metric.get("bbox") or {}).get("w") or 0)
                    ratio = side_w / front_w
                    metric["profile_width_ratio_vs_front"] = round(ratio, 4)
                    max_side_ratio = 0.78 if motion_requirements["requires_arm_clearance"] else 0.82
                    if ratio > max_side_ratio:
                        failures.append(
                            f"{view}: side profile wider than front view; likely three-quarter/front pose"
                        )

    return {
        "ok": len(failures) == 0,
        "schema": "aurora.turnaround_audit.v1",
        "subject_kind": subject_kind,
        "motion_prompt": motion_prompt,
        "motion_requirements": motion_requirements,
        "failures": failures,
        "views": metrics,
    }


def synth_multiview(prompt: str, run_id: str, *,
                    output_dir: Path = DEFAULT_OUTPUT_DIR,
                    width: int = 1024, height: int = 1024, steps: int = 25,
                    seed: int | None = None,
                    comfy_base: str = COMFY_BASE,
                    subject_kind: str | None = None,
                    max_attempts: int | None = None,
                    motion_prompt: str | None = None) -> dict:
    """Generate 4 views (front/back/left/right) of the same prompt with a
    shared seed so the subject identity is preserved across views.
    Output: <run_id>_reference.png (front, primary), plus
            <run_id>_back.png, <run_id>_left.png, <run_id>_right.png.
    Compatible with hunyuan3d_run.py --mv-front --mv-back --mv-left --mv-right."""
    if not prompt.strip():
        return {"ok": False, "error": "empty prompt"}
    if not run_id.strip():
        return {"ok": False, "error": "empty run_id"}

    started_at = time.time()
    if seed is None:
        seed = randint(1, 2**32 - 1)

    clean_prompt = _single_view_base_prompt(prompt)
    motion_contract = _motion_reference_contract(motion_prompt).lstrip(" ,")
    kind = (subject_kind or "").lower()
    human_contract = _human_fidelity_contract(clean_prompt, kind, motion_prompt).strip(" ,")
    contract_parts = [part for part in (human_contract, motion_contract) if part]
    if contract_parts:
        base_prompt = ", ".join(contract_parts + [clean_prompt])
    else:
        base_prompt = clean_prompt
    motion_requirements = _motion_pose_requirements(motion_prompt)
    default_attempts = (
        5
        if (
            kind in {"character", "humanoid", "creature", "quadruped"}
            and (
                motion_requirements["requires_articulated_pose"]
                or motion_requirements["requires_arm_clearance"]
            )
        )
        else (3 if kind in {"character", "humanoid", "creature", "quadruped"} else 1)
    )
    attempts_total = max_attempts if max_attempts is not None else default_attempts
    attempts: list[dict] = []
    views: dict[str, dict] = {}
    turnaround_audit: dict = {"ok": False, "failures": ["not run"]}
    attempt_prompt = base_prompt
    seed_used = seed

    for attempt in range(1, max(1, attempts_total) + 1):
        if seed is None:
            seed_used = randint(1, 2**32 - 1)
        else:
            seed_used = int(seed) + attempt - 1
        views = {}
        for view, suffix in MULTIVIEW_SUFFIXES.items():
            view_prompt = attempt_prompt.rstrip().rstrip(",.") + suffix
            view_run_id = f"{run_id}_{view}" if view != "front" else run_id
            sub = synth(
                view_prompt, view_run_id, output_dir=output_dir,
                width=width, height=height, steps=steps,
                seed=seed_used, comfy_base=comfy_base,
            )
            if not sub.get("ok"):
                return {"ok": False, "error": f"view '{view}' failed: {sub.get('error')}",
                        "completed_views": list(views.keys()),
                        "attempts": attempts}
            if kind in {"character", "humanoid"}:
                cleanup = _cleanup_character_reference(sub.get("reference_path", ""))
                sub["character_cleanup"] = cleanup
            views[view] = sub

        view_paths = {
            v: p["reference_path"]
            for v, p in views.items()
        }
        turnaround_audit = audit_multiview_consistency(
            view_paths, subject_kind=subject_kind, motion_prompt=motion_prompt,
        )
        failures = turnaround_audit.get("failures") or []
        attempts.append({
            "attempt": attempt,
            "seed": int(seed_used),
            "ok": bool(turnaround_audit.get("ok")),
            "failures": failures,
        })
        if turnaround_audit.get("ok"):
            break
        attempt_prompt = _retry_single_view_prompt(base_prompt, attempt + 1, failures)

    terminal_recommendation = None
    if not turnaround_audit.get("ok"):
        failure_text = " ; ".join(turnaround_audit.get("failures") or []).lower()
        if motion_requirements["requires_arm_clearance"] and (
            "motion-ready" in failure_text or "arms" in failure_text or "hands" in failure_text
        ):
            terminal_recommendation = (
                "pose_control_or_reference_images_required: FLUX did not obey the "
                "rig-ready arm/hand pose after retries; do not start 3D reconstruction "
                "from this reference."
            )
        elif "profile" in failure_text or "three-quarter" in failure_text or "side view" in failure_text:
            terminal_recommendation = (
                "orthographic_turnaround_control_required: FLUX did not produce exact "
                "90 degree side profiles after retries; do not start 3D reconstruction "
                "from this reference."
            )

    accepted = bool(turnaround_audit.get("ok"))
    result = {
        "ok": accepted,
        "schema": "aurora.flux_synth.v1",
        "mode": "multiview",
        "run_id": run_id,
        "prompt": prompt,
        "seed": int(seed_used or 0),
        "width": width,
        "height": height,
        "steps": steps,
        "views": {
            v: {"path": p["reference_path"], "size_bytes": p["size_bytes"]}
            for v, p in views.items()
        },
        "turnaround_audit": turnaround_audit,
        "attempts": attempts,
        "terminal_recommendation": terminal_recommendation,
        "elapsed_s": round(time.time() - started_at, 1),
    }
    if not accepted:
        failures = turnaround_audit.get("failures") or ["turnaround audit failed"]
        result["error"] = "turnaround reference rejected: " + "; ".join(map(str, failures[:3]))
    try:
        (output_dir / f"{run_id}_turnaround_audit.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
    return result


def synth(prompt: str, run_id: str, *,
          output_dir: Path = DEFAULT_OUTPUT_DIR,
          width: int = 1024, height: int = 1024, steps: int = 25,
          seed: int | None = None,
          comfy_base: str = COMFY_BASE) -> dict:
    if not prompt.strip():
        return {"ok": False, "error": "empty prompt"}
    if not run_id.strip():
        return {"ok": False, "error": "empty run_id"}

    started_at = time.time()
    workflow = build_workflow(
        prompt, width=width, height=height, steps=steps,
        seed=seed, filename_prefix=f"aurora_{run_id}",
    )
    # FLUX.1: le seed vit dans le KSampler "31". (Sous FLUX.2 il vivait dans le
    # noeud RandomNoise "42"; on lit les deux pour rester robuste si le graphe change.)
    seed_used = (workflow.get("31", {}).get("inputs", {}).get("seed")
                 or workflow.get("42", {}).get("inputs", {}).get("noise_seed") or 0)

    try:
        prompt_id = post_prompt(workflow, comfy_base)
    except (urllib.error.URLError, RuntimeError) as exc:
        return {"ok": False, "error": f"submit failed: {exc}"}

    try:
        try:
            entry = poll_history(prompt_id, comfy_base=comfy_base)
        except JobLostError:
            # ComfyUI tue/redemarre en cours de job (OOM...): la queue est vide,
            # le job n'aboutira jamais. On re-soumet UNE fois sur le serveur neuf.
            prompt_id = post_prompt(workflow, comfy_base)
            entry = poll_history(prompt_id, comfy_base=comfy_base)
    except (TimeoutError, JobLostError, RuntimeError, urllib.error.URLError) as exc:
        return {"ok": False, "error": str(exc), "prompt_id": prompt_id}

    try:
        url = output_path_from_history(entry, comfy_base)
    except RuntimeError as exc:
        return {"ok": False, "error": f"no output: {exc}"}

    out_path = output_dir / f"{run_id}_reference.png"
    try:
        size = fetch_to(url, out_path)
    except OSError as exc:
        return {"ok": False, "error": f"fetch failed: {exc}", "src_url": url}

    sidecar = output_dir / f"{run_id}_prompt.txt"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    try:
        sidecar.write_text(prompt, encoding="utf-8")
    except OSError:
        pass

    return {
        "ok": True,
        "schema": "aurora.flux_synth.v1",
        "run_id": run_id,
        "prompt": prompt,
        "prompt_id": prompt_id,
        "seed": int(seed_used),
        "width": width,
        "height": height,
        "steps": steps,
        "reference_path": str(out_path),
        "prompt_sidecar_path": str(sidecar),
        "src_url": url,
        "size_bytes": size,
        "elapsed_s": round(time.time() - started_at, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora FLUX reference synthesizer")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run-id", required=True, dest="run_id")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), dest="output_dir")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--comfy-base", default=COMFY_BASE, dest="comfy_base")
    parser.add_argument("--subject-kind", default=None, dest="subject_kind",
                        help="Optional subject kind for reference QA (character, product, vehicle, ...)")
    parser.add_argument("--motion-prompt", default=None, dest="motion_prompt",
                        help="Optional motion description used to require animation-ready references")
    parser.add_argument("--multi-view", action="store_true",
                        help="Generate 4 views (front/back/left/right) sharing the seed")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    if args.multi_view:
        result = synth_multiview(
            args.prompt, args.run_id,
            output_dir=Path(args.output_dir),
            width=args.width, height=args.height, steps=args.steps,
            seed=args.seed, comfy_base=args.comfy_base,
            subject_kind=args.subject_kind,
            motion_prompt=args.motion_prompt,
        )
    else:
        result = synth(
            args.prompt, args.run_id,
            output_dir=Path(args.output_dir),
            width=args.width, height=args.height, steps=args.steps,
            seed=args.seed, comfy_base=args.comfy_base,
        )
    if args.pretty and result.get("ok") and result.get("mode") == "multiview":
        sys.stdout.write(
            f"FLUX multi-view ({len(result['views'])} views, seed {result['seed']}):\n"
        )
        for v, info in result["views"].items():
            sys.stdout.write(f"  {v:<6} → {info['path']}  ({info['size_bytes']:,} bytes)\n")
        sys.stdout.write(f"  elapsed: {result['elapsed_s']}s\n")
    elif args.pretty and result.get("ok"):
        sys.stdout.write(
            f"FLUX synth → {result['reference_path']}\n"
            f"  prompt: {result['prompt'][:80]}\n"
            f"  seed:   {result['seed']}\n"
            f"  size:   {result['size_bytes']:,} bytes  ({result['width']}x{result['height']}, {result['steps']} steps)\n"
            f"  elapsed: {result['elapsed_s']}s\n"
        )
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
