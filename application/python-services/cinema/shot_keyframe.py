#!/usr/bin/env python3
"""Keyframe d'ACTION par plan (FLUX.2 + references d'identite).

LE DEFAUT QU'IL CORRIGE
-----------------------
Trois defauts constates sur les films rendus tenaient a la meme cause : chaque
plan etait conditionne par une image qui ne decrivait PAS son action.

  1. « la texture passe d'anime a realiste entre les plans ». Wan derive de
     style d'un plan a l'autre quand le seul garde-fou est le texte. Les plans
     ancres derivaient moins que les plans t2v — donc le film melangeait deux
     regimes visuels.
  2. « quand il veut montrer le velo il apparait d'un coup ». L'ancre etait un
     PORTRAIT studio colle sur un fond : rien dans l'image ne disait que le
     personnage tenait deja l'objet, donc le modele le faisait apparaitre.
  3. « il glisse de profil ». Mesure : ancre i2v depuis une image du velo A
     L'ARRET -> phys 3/10, « Character stationary holding bike ». Le
     conditionnement verrouille la pose de depart ; si elle est immobile, la
     seule sortie possible pour « ca avance » est la translation rigide.

La parade est la meme pour les trois : que la premiere image de chaque plan
soit deja CE plan — bonne action, bon decor, bon style, bonne identite. FLUX
est nettement plus stable en style que Wan et dessine une mecanique complete ;
Wan n'a alors plus qu'a animer, ce qu'il fait bien.

L'identite passe par `ReferenceLatent` : les references du personnage et des
objets sont encodees et injectees dans le conditionnement, ce qui evite d'avoir
a redecrire le personnage en esperant que le texte suffise.

Usage :
  python shot_keyframe.py --check
  python shot_keyframe.py --prompt "..." --reference natsu.png \
      --reference velo.png --output plan3.png --width 960 --height 544
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
SERVICES_DIR = Path(__file__).resolve().parent.parent
ROOT = SERVICES_DIR.parent
COMFY_DIR = ROOT.parent / "modele" / "comfyui"

UNET = os.environ.get("AURORA_FLUX_UNET", "flux2-dev-Q4_K_M.gguf")
CLIP = os.environ.get("AURORA_FLUX_CLIP", "")
VAE = os.environ.get("AURORA_FLUX_VAE", "")

# Au-dela de 3 references, le conditionnement se dilue et l'identite se degrade
# au lieu de s'ameliorer : chaque reference tire le resultat vers elle.
MAX_REFERENCES = 3

NEGATIVE = (
    "photorealistic drift, mixed art style, style change, inconsistent style, "
    "deformed anatomy, extra limbs, fused limbs, missing pedals, missing parts, "
    "floating object, duplicated object, text, watermark, letters, subtitles, "
    "blurry, low detail, cropped, out of frame"
)


def emit(stage: str, detail: str = ""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _resolve_defaults():
    """Reprend les noms de poids de flux_reference_synth, seule source de verite."""
    global CLIP, VAE
    if CLIP and VAE:
        return
    sys.path.insert(0, str(SERVICES_DIR))
    try:
        import flux_reference_synth as frs
        CLIP = CLIP or getattr(frs, "DEFAULT_CLIP", "")
        VAE = VAE or getattr(frs, "DEFAULT_VAE", "")
        globals()["UNET"] = os.environ.get(
            "AURORA_FLUX_UNET", getattr(frs, "DEFAULT_UNET", UNET))
    except Exception as exc:
        emit("keyframe_warn", f"defauts FLUX non lus: {str(exc)[:120]}")


def check() -> dict:
    _resolve_defaults()
    needed = ["ReferenceLatent", "FluxKontextImageScale", "VAEEncode",
              "LoadImage", "CLIPTextEncode", "SamplerCustomAdvanced",
              "Flux2Scheduler", "EmptyFlux2LatentImage"]
    found, up = [], False
    try:
        with urllib.request.urlopen(f"{COMFY}/object_info", timeout=25) as r:
            info = json.loads(r.read().decode())
        up = True
        found = [n for n in needed if n in info]
    except Exception as exc:
        return {"ok": False, "comfyui": False, "error": str(exc)[:160]}
    return {
        "ok": up and len(found) == len(needed) and bool(CLIP) and bool(VAE),
        "comfyui": up,
        "missing_nodes": [n for n in needed if n not in found],
        "unet": UNET, "clip": CLIP, "vae": VAE,
    }


def build_workflow(prompt: str, references: list, width: int, height: int,
                   steps: int, seed: int, cfg: float, prefix: str) -> dict:
    """Graphe FLUX.2 avec chaine de references d'identite.

    Le conditionnement positif traverse un `ReferenceLatent` par reference :
    chacun ajoute son image au contexte sans remplacer le precedent, ce qui
    permet de tenir a la fois le personnage et l'objet qu'il manipule.
    """
    _resolve_defaults()
    loader = ({"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET}}
              if str(UNET).lower().endswith(".gguf")
              else {"class_type": "UNETLoader",
                    "inputs": {"unet_name": UNET, "weight_dtype": "default"}})
    wf = {
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": CLIP, "type": "flux2", "device": "cpu"}},
        "12": loader,
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["11", 0], "text": prompt}},
        "33": {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["11", 0], "text": NEGATIVE}},
        "27": {"class_type": "EmptyFlux2LatentImage",
               "inputs": {"width": width, "height": height, "batch_size": 1}},
        "40": {"class_type": "Flux2Scheduler",
               "inputs": {"steps": steps, "width": width, "height": height}},
        "41": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
    }

    positive = ["6", 0]
    for i, ref_name in enumerate(references[:MAX_REFERENCES]):
        load_id, scale_id, enc_id, ref_id = (f"1{i}0", f"1{i}1", f"1{i}2", f"1{i}3")
        wf[load_id] = {"class_type": "LoadImage", "inputs": {"image": ref_name}}
        wf[scale_id] = {"class_type": "FluxKontextImageScale",
                        "inputs": {"image": [load_id, 0]}}
        wf[enc_id] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": [scale_id, 0], "vae": ["10", 0]}}
        wf[ref_id] = {"class_type": "ReferenceLatent",
                      "inputs": {"conditioning": positive, "latent": [enc_id, 0]}}
        positive = [ref_id, 0]

    wf["26"] = {"class_type": "CFGGuider",
                "inputs": {"model": ["12", 0], "positive": positive,
                           "negative": ["33", 0], "cfg": cfg}}
    wf["31"] = {"class_type": "SamplerCustomAdvanced",
                "inputs": {"noise": ["42", 0], "guider": ["26", 0],
                           "sampler": ["41", 0], "sigmas": ["40", 0],
                           "latent_image": ["27", 0]}}
    wf["8"] = {"class_type": "VAEDecode",
               "inputs": {"samples": ["31", 0], "vae": ["10", 0]}}
    wf["9"] = {"class_type": "SaveImage",
               "inputs": {"images": ["8", 0], "filename_prefix": prefix}}
    return wf


def _comfy_dir(name: str) -> Path:
    for cand in (COMFY_DIR / name, COMFY_DIR / "comfyui" / name):
        if cand.is_dir():
            return cand
    d = COMFY_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def run(prompt: str, references: list, output_png: str, width: int = 960,
        height: int = 544, steps: int = 28, seed: int = 42, cfg: float = 5.0,
        timeout: int = 1800) -> dict:
    st = check()
    if not st.get("ok"):
        return {"ok": False, "error": f"FLUX keyframe indisponible: {st}"}

    inp = _comfy_dir("input")
    tag = uuid.uuid4().hex[:10]
    staged = []
    for i, ref in enumerate(references[:MAX_REFERENCES]):
        src = Path(ref)
        if not src.is_file():
            emit("keyframe_warn", f"reference absente ignoree: {ref}")
            continue
        name = f"shotkf_{tag}_{i}{src.suffix.lower() or '.png'}"
        shutil.copy2(src, inp / name)
        staged.append(name)

    # FLUX.2 exige des dimensions multiples de 16.
    width = max(256, (width // 16) * 16)
    height = max(256, (height // 16) * 16)

    prefix = f"aurora_shotkf_{tag}"
    wf = build_workflow(prompt, staged, width, height, steps, seed, cfg, prefix)
    emit("shot_keyframe",
         f"{width}x{height}, {steps} pas, {len(staged)} reference(s)")

    req = urllib.request.Request(
        f"{COMFY}/prompt", data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            pid = json.loads(r.read().decode()).get("prompt_id")
    except Exception as exc:
        return {"ok": False, "error": f"soumission refusee: {exc}"}
    if not pid:
        return {"ok": False, "error": "ComfyUI n'a pas renvoye de prompt_id"}

    t0 = time.time()
    images = []
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            with urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=30) as r:
                hist = json.loads(r.read().decode())
        except Exception:
            continue
        entry = hist.get(pid)
        if not entry:
            continue
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            for m in status.get("messages", []):
                if m and m[0] == "execution_error":
                    d = m[1]
                    return {"ok": False,
                            "error": f"{d.get('node_type')}: "
                                     f"{str(d.get('exception_message'))[:300]}"}
            return {"ok": False, "error": "erreur ComfyUI sans detail"}
        node = (entry.get("outputs") or {}).get("9") or {}
        if node.get("images"):
            images = node["images"]
            break
    if not images:
        return {"ok": False, "error": f"aucune image en {timeout}s"}

    src = _comfy_dir("output") / (images[0].get("subfolder") or "") / images[0]["filename"]
    if not src.is_file():
        return {"ok": False, "error": f"image annoncee mais absente: {src}"}
    Path(output_png).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, output_png)

    for name in staged:
        try:
            (inp / name).unlink()
        except OSError:
            pass

    return {"ok": True, "image": output_png, "references": len(staged),
            "width": width, "height": height, "seed": seed,
            "elapsed_s": round(time.time() - t0, 1)}


def build_shot_prompt(scene: str, style_suffix: str, action_contract: str = "",
                      entities: list = None) -> str:
    """Prompt de keyframe : une IMAGE FIXE qui montre l'action deja engagee.

    « premier instant » et non « avant l'action » : une image ou le geste a
    commence donne a i2v une pose de depart qui appelle la suite du mouvement,
    la ou une pose au repos le verrouille a l'arret.
    """
    parts = [
        "A single cinematic film still, the first frame of a shot, "
        "captured mid-action with the movement already underway.",
        scene.strip(),
    ]
    if action_contract.strip():
        parts.append(f"The action already in progress: {action_contract.strip()}")
    if entities:
        named = ", ".join(str(e) for e in entities if e)
        if named:
            parts.append(
                f"The following must appear exactly as in the reference "
                f"images, complete and with every part present: {named}.")
    parts.append("Full scene with background, natural composition, no text.")
    return " ".join(p for p in parts if p).strip() + (style_suffix or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--reference", action="append", default=[],
                    help="Image de reference (repetable, max 3)")
    ap.add_argument("--output")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=544)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cfg", type=float, default=5.0)
    args = ap.parse_args()

    if args.check:
        print(json.dumps(check(), ensure_ascii=False), flush=True)
        return 0
    if not (args.prompt and args.output):
        print(json.dumps({"ok": False, "error": "--prompt et --output requis"}),
              flush=True)
        return 1
    res = run(args.prompt, args.reference, args.output, args.width, args.height,
              args.steps, args.seed, args.cfg)
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
