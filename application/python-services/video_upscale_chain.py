#!/usr/bin/env python3
"""Chaine de finition video Aurora : master haute resolution honnete.

Remplace le `scale=lanczos,unsharp` du pipeline cinema, qui est un
REDIMENSIONNEMENT et non une reconstruction, et qui etait pourtant trace
sous le nom "true 1080p" (mensonge de completude).

Etages, dans l'ordre imposé par la recherche (l'ORDRE compte plus que le
choix des modeles) :

  1. extraction des frames                      (ffmpeg)
  2. deflicker                                  (ffmpeg, AVANT l'upscale :
     sinon l'upscaler "restaure" le flicker et l'amplifie)
  3. reconstruction x4                          (RealESRGAN / RRDBNet, GPU, tuile)
  4. sur-echantillonnage vers la cible exacte   (Lanczos descendant : x4 puis
     descente = anti-aliasing gratuit + attenuation du shimmer GAN, qui est
     le defaut connu d'un upscaler par-frame sans conscience temporelle)
  5. reassemblage + interpolation optionnelle   (ffmpeg)
  6. grain film                                 (DERNIER effet image)
  7. master 10 bits + dither                    (ProRes 422 HQ ou x265 10-bit)

Le 10 bits n'est pas un luxe : un degrade de ciel au coucher de soleil bande
visiblement en 8 bits, et ce defaut se voit davantage a l'ecran que le passage
de 1080p a 4K.

HONNETETE (loi §4.3 du prompt de refonte) : le JSON final porte les cinq
champs de verite — resolution native d'entree, resolution apres chaque etage,
resolution du master, profondeur de bits, et la liste ORDONNEE des modeles de
reconstruction reellement executes. Si aucun modele n'a tourne, le champ
`reconstructed` vaut false et le script REFUSE d'etiqueter la sortie "4K".

Reprise : chaque frame upscalee est ecrite sur disque ; relancer avec --resume
repart de la premiere frame manquante (indispensable, un master 4K prend des
heures et la machine a un historique de gels GPU).

Usage :
  python video_upscale_chain.py --input in.mp4 --output master.mov --target 4k
  python video_upscale_chain.py --input in.mp4 --output m.mov --target 1440p --fps 48 --grain 0.6
"""

import argparse
import gc
import json
import os
import shutil
import subprocess

# 2026-08-08 : même discipline VRAM qu'ailleurs — la fragmentation du cache
# PyTorch entre le worker vidéo (Wan 5B, 14 GiB peak) et cette chaîne de
# finition (RealESRGAN, ~2 GiB + tuiles) provoque un OOM sur une allocation
# de <2 GiB alors qu'il « reste » plus que ça. `expandable_segments:True`
# coalesce les blocs libres et évite ce mode de défaillance. Constaté sur
# film_2026-08-08_natsu-bench : `finition_echouee` — trace au niveau
# `video_upscale_chain.py:565` sur un tenseur ESRGAN qui ne tenait plus
# après un rendu Wan pourtant terminé et libéré côté processus.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import sys
import time

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESRGAN_WEIGHTS = os.path.join(
    WORKSPACE, "python-services", "_hy3dpaint", "ckpt", "RealESRGAN_x4plus.pth"
)

# Cibles exprimees par le PETIT cote : l'orientation est deduite de la source,
# jamais imposee (le bug historique de video_generate.py etait exactement un
# plafond aveugle a l'orientation qui ecrasait le 9:16 en carre).
TARGETS = {
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "4k": 2160,
    "8k": 4320,
}


def emit(stage, detail=""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def ffmpeg_bin():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_bin():
    return shutil.which("ffprobe") or "ffprobe"


def probe(path):
    out = subprocess.run(
        [
            ffprobe_bin(), "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(out.stdout or "{}")
    st = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    num, _, den = (st.get("r_frame_rate") or "24/1").partition("/")
    fps = float(num) / float(den or 1)
    return {
        "width": int(st.get("width") or 0),
        "height": int(st.get("height") or 0),
        "fps": fps,
        "duration_s": float(fmt.get("duration") or 0.0),
    }


def has_audio(path):
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=60,
    )
    return bool(out.stdout.strip())


def run(cmd, timeout=None):
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"commande echouee ({proc.returncode}): {' '.join(cmd[:6])}...\n"
            + (proc.stderr or "")[-1500:]
        )
    return proc


# 2026-08-08 : heartbeat pour ne PAS se faire tuer par le timeout inactivité
# du bridge (1200 s sans ligne stdout). Contexte : la chaîne de finition a
# de longs silences (SeedVR2 CLI opaque, RealESRGAN per-frame lent, ffmpeg
# assemble d'un master 10 bits). Le timeout wall-clock a été remplacé plus
# tôt par ce timeout inactivité — l'ancien mode de défaillance revenait donc
# par la porte de derrière. Solution : émettre `PROGRESS:heartbeat:...` à
# intervalles réguliers depuis un thread daemon pendant les stages longs.
import threading as _threading


def _make_heartbeat(stage_name: str, period_s: float = 30.0):
    """Retourne (stop_event, thread) — spawn un thread qui émet un heartbeat
    toutes les `period_s` secondes tant que stop_event n'est pas set.
    Usage :
        stop, th = _make_heartbeat("seedvr2", 30.0)
        try: work()
        finally: stop.set(); th.join(timeout=1)
    """
    stop = _threading.Event()
    t0 = time.time()

    def _beat():
        while not stop.wait(timeout=period_s):
            elapsed = int(time.time() - t0)
            print(f"PROGRESS:heartbeat:{stage_name} vivant depuis {elapsed}s", flush=True)

    th = _threading.Thread(target=_beat, daemon=True)
    th.start()
    return stop, th


# ---------------------------------------------------------------- etage 1 + 2
def extract_frames(src, frames_dir, deflicker):
    os.makedirs(frames_dir, exist_ok=True)
    vf = []
    if deflicker:
        # moyenne temporelle de luma : corrige le scintillement d'exposition
        # typique des rendus par diffusion. A faire AVANT l'upscale.
        vf.append("deflicker=size=5:mode=pm")
    cmd = [ffmpeg_bin(), "-v", "error", "-y", "-i", src]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-start_number", "0", os.path.join(frames_dir, "f_%06d.png")]
    # Heartbeat pendant l'extraction — ffmpeg deflicker sur ~220 frames peut
    # prendre plusieurs minutes en silence.
    _hb_stop_ex, _hb_thread_ex = _make_heartbeat("ffmpeg_extract", period_s=30.0)
    try:
        run(cmd, timeout=3600)
    finally:
        _hb_stop_ex.set()
        _hb_thread_ex.join(timeout=1)
    return sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))


# -------------------------------------------------------------------- etage 3
SEEDVR2_CLI = os.path.join(
    os.path.dirname(WORKSPACE), "modele", "comfyui", "custom_nodes",
    "ComfyUI-SeedVR2_VideoUpscaler", "inference_cli.py")
SEEDVR2_MODELS = os.path.join(
    os.path.dirname(WORKSPACE), "modele", "comfyui", "models", "SEEDVR2")
SEEDVR2_DIT = "seedvr2_ema_7b_sharp_fp16.safetensors"


def seedvr2_available():
    return (os.path.exists(SEEDVR2_CLI)
            and os.path.exists(os.path.join(SEEDVR2_MODELS, SEEDVR2_DIT)))


def upscale_seedvr2(src, dst, target_short, batch_size, blocks_to_swap, seed):
    """Reconstruction video par SeedVR2 v2.5 (DiT one-step, Apache 2.0).

    Superieur a RealESRGAN sur le point qui compte ici : SeedVR2 est
    TEMPORELLEMENT CONSCIENT. Un upscaler par-frame comme RealESRGAN
    re-synthetise chaque image independamment, ce qui fait scintiller les
    micro-details en mouvement ; SeedVR2 traite un lot de frames ensemble.

    Reglages imposes :
      - batch_size en 4n+1 (1, 5, 9 ... 33). Hors de cette formule le modele
        perd sa coherence temporelle. Un batch >= 25 est necessaire pour
        eviter le scintillement.
      - uniform_batch_size : sans lui, le dernier lot (plus court) recoit un
        contexte different et sort avec une luminosite legerement autre, ce
        qui se voit comme un "pompage" aux jointures.
      - offload DiT et VAE vers la RAM + blocks_to_swap : le 7B fp16 pese
        16,5 Go, il ne tient pas seul dans 16 Go de VRAM.
      - color_correction lab : recolle les derives de teinte entre lots.
    """
    if batch_size % 4 != 1:
        batch_size = max(1, (batch_size // 4) * 4 + 1)
    cmd = [
        sys.executable, SEEDVR2_CLI, src,
        "--output", dst,
        "--output_format", "mp4",
        "--model_dir", SEEDVR2_MODELS,
        "--dit_model", SEEDVR2_DIT,
        "--resolution", str(target_short),
        "--batch_size", str(batch_size),
        "--uniform_batch_size",
        "--temporal_overlap", "4",
        "--color_correction", "lab",
        "--seed", str(seed),
        "--dit_offload_device", "cpu",
        "--vae_offload_device", "cpu",
        "--tensor_offload_device", "cpu",
        "--blocks_to_swap", str(blocks_to_swap),
        "--10bit",
    ]
    emit("seedvr2", f"7B sharp fp16, cible {target_short}p, batch {batch_size}, "
                    f"block-swap {blocks_to_swap}")
    # Heartbeat pendant que le CLI SeedVR2 tourne (opaque, aucun PROGRESS
    # émis par lui-même — le bridge kill à 20 min sans stdout sinon).
    _hb_stop, _hb_thread = _make_heartbeat("seedvr2", period_s=30.0)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=86400,
                              cwd=os.path.dirname(SEEDVR2_CLI))
    finally:
        _hb_stop.set()
        _hb_thread.join(timeout=1)
    if proc.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError(
            "SeedVR2 a echoue : " + (proc.stderr or proc.stdout or "")[-1500:])
    return dst


def _shim_torchvision():
    """Alias en memoire pour `torchvision.transforms.functional_tensor`.

    basicsr (et donc realesrgan) importe ce module, retire des torchvision
    recents : sans cet alias, tout import de basicsr echoue. On le pose en
    memoire AVANT d'importer basicsr — surtout PAS de patch dans
    `application/.venv`, qui casserait FLUX et la 3D.
    """
    import sys as _sys
    import types

    name = "torchvision.transforms.functional_tensor"
    if name in _sys.modules:
        return
    try:
        import torchvision.transforms.functional as _F
    except Exception:
        return
    mod = types.ModuleType(name)
    for attr in ("rgb_to_grayscale", "to_grayscale", "normalize", "resize"):
        if hasattr(_F, attr):
            setattr(mod, attr, getattr(_F, attr))
    _sys.modules[name] = mod


def load_esrgan(device):
    """Charge RealESRGAN_x4plus via RRDBNet directement.

    Le wrapper `realesrgan.RealESRGANer` est inutilisable dans ce venv ; on
    charge donc l'architecture et les poids a la main, apres le shim.
    """
    import torch

    _shim_torchvision()
    from basicsr.archs.rrdbnet_arch import RRDBNet

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=23, num_grow_ch=32, scale=4)
    sd = torch.load(ESRGAN_WEIGHTS, map_location="cpu", weights_only=True)
    sd = sd.get("params_ema") or sd.get("params") or sd
    model.load_state_dict(sd, strict=True)
    model.eval().to(device)
    return model


def upscale_tiled(model, img, device, tile=512, overlap=32):
    """Inference x4 par tuiles avec recouvrement.

    Le recouvrement doit rester genereux : une couture visible vient presque
    toujours d'un chevauchement trop faible. On fond les tuiles par un simple
    recouvrement centre (le GAN est deterministe, donc pas de derive de bruit
    entre tuiles — contrairement a un upscaler par diffusion ou il faudrait
    imposer la meme seed partout).
    """
    import torch
    import numpy as np

    h, w = img.shape[:2]
    scale = 4
    out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
    weight = np.zeros((h * scale, w * scale, 1), dtype=np.float32)

    for y0 in range(0, h, tile - overlap):
        for x0 in range(0, w, tile - overlap):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            patch = img[y0:y1, x0:x1]
            t = torch.from_numpy(patch).permute(2, 0, 1).unsqueeze(0).to(device)
            with torch.no_grad():
                o = model(t)
            o = o.squeeze(0).permute(1, 2, 0).float().cpu().numpy()
            oy0, ox0 = y0 * scale, x0 * scale
            out[oy0:oy0 + o.shape[0], ox0:ox0 + o.shape[1]] += o
            weight[oy0:oy0 + o.shape[0], ox0:ox0 + o.shape[1]] += 1.0
            del t
    return out / np.maximum(weight, 1e-6)


def upscale_frames(frames_dir, up_dir, names, target_short, resume):
    import numpy as np
    import torch
    from PIL import Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    os.makedirs(up_dir, exist_ok=True)
    model = load_esrgan(device)
    emit("upscale_model", f"RealESRGAN_x4plus sur {device}")

    total = len(names)
    done_at_start = 0
    t0 = time.time()
    for i, name in enumerate(names):
        dst = os.path.join(up_dir, name)
        if resume and os.path.exists(dst) and os.path.getsize(dst) > 0:
            done_at_start += 1
            continue
        img = np.asarray(Image.open(os.path.join(frames_dir, name)).convert("RGB"),
                         dtype=np.float32) / 255.0
        big = upscale_tiled(model, img, device)

        # Descente vers la cible exacte : x4 puis reduction = sur-echantillonnage.
        # C'est ce qui attenue le shimmer d'un upscaler par-frame et donne un
        # anti-aliasing gratuit.
        h, w = big.shape[:2]
        short = min(h, w)
        if short != target_short:
            ratio = target_short / short
            nw, nh = int(round(w * ratio)), int(round(h * ratio))
            nw -= nw % 2
            nh -= nh % 2
            big = np.asarray(
                Image.fromarray((np.clip(big, 0, 1) * 255).astype(np.uint8))
                .resize((nw, nh), Image.LANCZOS),
                dtype=np.float32,
            ) / 255.0

        Image.fromarray((np.clip(big, 0, 1) * 255).astype(np.uint8)).save(dst)
        # 2026-08-08 : cadence d'emit basée à la fois sur le compteur ET sur
        # le temps. À 5 frames/emit ça peut faire 30 s à 5 min entre lignes
        # selon la charge — au-delà du seuil inactivité 1200 s ça reste OK,
        # mais un tick chaque 30 s garantit que le bridge voit le job vivant
        # même sur les frames particulièrement lentes.
        el = time.time() - t0
        _emit_by_count = (i + 1) % 5 == 0 or i + 1 == total
        _emit_by_time = (el - getattr(upscale_frames, "_last_emit_s", 0.0)) >= 30.0
        if _emit_by_count or _emit_by_time:
            emit("upscale", f"{i + 1}/{total} frames ({el:.0f}s)")
            upscale_frames._last_emit_s = el
        if device == "cuda":
            torch.cuda.empty_cache()

    if done_at_start:
        emit("resume", f"{done_at_start} frames deja presentes, reprises")

    # 2026-08-08 : libère explicitement le modèle avant l'étape suivante
    # (assemble/audio/grain qui n'a pas besoin du GPU). Sans ça, ~2 GiB de
    # RealESRGAN restent alloués pendant tout l'assemblage — inutile.
    try:
        del model
    except Exception:
        pass
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

    return device


# ---------------------------------------------------------------- etage 5 a 7
def assemble(up_dir, src_audio, out_path, fps, out_fps, grain, codec):
    vf = []
    if out_fps and abs(out_fps - fps) > 0.01:
        vf.append(
            f"minterpolate=fps={out_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )
    if grain and grain > 0:
        # grain par frame (jamais fixe : un grain statique donne un effet
        # "vitre sale"). Dernier effet image, juste avant l'encodage.
        vf.append(f"noise=alls={max(1, int(grain * 12))}:allf=t")

    cmd = [ffmpeg_bin(), "-v", "error", "-y",
           "-framerate", f"{fps}", "-i", os.path.join(up_dir, "f_%06d.png")]
    if src_audio:
        cmd += ["-i", src_audio]
    if vf:
        cmd += ["-vf", ",".join(vf)]

    if codec == "prores":
        cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-qscale:v", "9",
                "-pix_fmt", "yuv422p10le"]
        depth = "10 bits (ProRes 422 HQ, yuv422p10le)"
    else:
        cmd += ["-c:v", "libx265", "-crf", "14", "-preset", "slow",
                "-pix_fmt", "yuv420p10le", "-x265-params", "aq-mode=3"]
        depth = "10 bits (x265 CRF 14, yuv420p10le)"

    cmd += ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    if src_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [out_path]
    _hb_stop_ff, _hb_thread_ff = _make_heartbeat("ffmpeg_master", period_s=30.0)
    try:
        run(cmd, timeout=7200)
    finally:
        _hb_stop_ff.set()
        _hb_thread_ff.join(timeout=1)
    return depth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--target", default="4k", choices=sorted(TARGETS))
    ap.add_argument("--fps", type=float, default=0, help="fps de sortie (0 = conserver)")
    ap.add_argument("--grain", type=float, default=0.5, help="0 = aucun grain")
    ap.add_argument("--codec", default="prores", choices=["prores", "x265"])
    ap.add_argument("--no-deflicker", action="store_true")
    ap.add_argument("--no-upscale", action="store_true",
                    help="montage/master seulement, sans reconstruction")
    ap.add_argument("--upscaler", default="auto",
                    choices=["auto", "seedvr2", "realesrgan"],
                    help="auto = SeedVR2 si installe (temporellement coherent), "
                         "sinon RealESRGAN (par frame, peut scintiller)")
    ap.add_argument("--batch-size", type=int, default=33,
                    help="SeedVR2 : taille de lot, doit etre 4n+1")
    ap.add_argument("--blocks-to-swap", type=int, default=36,
                    help="SeedVR2 : blocs deportes en RAM (16 Go de VRAM)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workdir", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    t_start = time.time()
    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        print(json.dumps({"ok": False, "error": f"introuvable: {src}"}))
        return 1
    if not args.no_upscale and not os.path.exists(ESRGAN_WEIGHTS):
        print(json.dumps({"ok": False, "error": f"poids absents: {ESRGAN_WEIGHTS}"}))
        return 1

    info = probe(src)
    target_short = TARGETS[args.target]
    workdir = args.workdir or os.path.join(
        os.path.dirname(os.path.abspath(args.output)),
        "_chain_" + os.path.splitext(os.path.basename(args.output))[0],
    )
    frames_dir = os.path.join(workdir, "src")
    up_dir = os.path.join(workdir, "up")
    os.makedirs(workdir, exist_ok=True)

    emit("probe", f"{info['width']}x{info['height']} @ {info['fps']:.2f}fps, "
                  f"{info['duration_s']:.2f}s")

    stages = []
    reconstructed = False
    models_run = []

    # 1-2
    if args.resume and os.path.isdir(frames_dir) and os.listdir(frames_dir):
        names = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
        emit("extract", f"{len(names)} frames deja extraites (reprise)")
    else:
        emit("extract", "extraction" + ("" if args.no_deflicker else " + deflicker"))
        names = extract_frames(src, frames_dir, deflicker=not args.no_deflicker)
    stages.append({"stage": "extract_deflicker",
                   "resolution": f"{info['width']}x{info['height']}",
                   "frames": len(names),
                   "deflicker": not args.no_deflicker})

    # --- Chemin SeedVR2 : il traite la VIDEO entiere, pas des frames isolees,
    # donc il court-circuite les etages 3-4 par-frame ci-dessous.
    chosen = args.upscaler
    if chosen == "auto":
        chosen = "seedvr2" if seedvr2_available() else "realesrgan"
    seedvr2_ok = False
    if not args.no_upscale and chosen == "seedvr2":
        if not seedvr2_available():
            print(json.dumps({"ok": False,
                              "error": f"SeedVR2 absent ({SEEDVR2_CLI})"}))
            return 1
        tmp_out = os.path.join(workdir, "seedvr2_out.mp4")
        os.makedirs(workdir, exist_ok=True)
        # 2026-08-08 : SeedVR2 OOMe régulièrement à 2.49 GiB sur 16 GiB
        # cohabitation post-Wan (causal_inflation_lib.py forward, batch-size
        # indépendant). Repli propre vers RealESRGAN — moins bien
        # (per-frame, peut scintiller) mais tient dans le budget. Meilleur
        # qu'un master sans reconstruction du tout.
        try:
            upscale_seedvr2(src, tmp_out, target_short, args.batch_size,
                            args.blocks_to_swap, args.seed)
            seedvr2_ok = True
        except RuntimeError as _seed_exc:
            _msg = str(_seed_exc)
            if "OutOfMemoryError" in _msg or "out of memory" in _msg.lower() or "OOM" in _msg:
                emit("upscaler_fallback",
                     f"SeedVR2 OOM ({_msg[-200:]}) → repli RealESRGAN par-frame")
                chosen = "realesrgan"
            else:
                raise
    if seedvr2_ok:
        up_info = probe(tmp_out)
        stages.append({"stage": "reconstruction",
                       "model": "SeedVR2 v2.5 7B sharp fp16",
                       "resolution": f"{up_info.get('width')}x{up_info.get('height')}"})
        reconstructed = True
        models_run.append("SeedVR2 v2.5 7B sharp fp16 (DiT temporellement coherent)")
        out_fps = args.fps or info["fps"]
        emit("assemble", f"master {args.codec} depuis la sortie SeedVR2")
        # SeedVR2 a deja produit une video : on la remuxe au format master.
        audio = src if has_audio(src) else None
        vf = []
        if args.grain and args.grain > 0:
            vf.append(f"noise=alls={max(1, int(args.grain * 12))}:allf=t")
        cmd = [ffmpeg_bin(), "-v", "error", "-y", "-i", tmp_out]
        if audio:
            cmd += ["-i", audio]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        if args.codec == "prores":
            cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-qscale:v", "9",
                    "-pix_fmt", "yuv422p10le"]
            depth = "10 bits (ProRes 422 HQ, yuv422p10le)"
        else:
            cmd += ["-c:v", "libx265", "-crf", "14", "-preset", "slow",
                    "-pix_fmt", "yuv420p10le", "-x265-params", "aq-mode=3"]
            depth = "10 bits (x265 CRF 14, yuv420p10le)"
        cmd += ["-color_primaries", "bt709", "-color_trc", "bt709",
                "-colorspace", "bt709"]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += [os.path.abspath(args.output)]
        # 2026-08-08 : bug de scoping corrigé — le heartbeat + le
        # try/finally étaient sortis du bloc `if seedvr2_ok:` par une
        # replace_all précédente, causant UnboundLocalError sur le repli
        # RealESRGAN (cmd et _hb_stop_ff non définis dans cette branche).
        # Ré-indenté proprement DANS le bloc SeedVR2-only.
        _hb_stop_ff, _hb_thread_ff = _make_heartbeat("ffmpeg_master", period_s=30.0)
        try:
            run(cmd, timeout=7200)
        finally:
            _hb_stop_ff.set()
            _hb_thread_ff.join(timeout=1)
        final = probe(os.path.abspath(args.output))
        stages.append({"stage": "master",
                       "resolution": f"{final['width']}x{final['height']}",
                       "fps": final["fps"], "depth": depth,
                       "grain": args.grain, "audio": bool(audio)})
        if not args.keep_frames:
            shutil.rmtree(workdir, ignore_errors=True)
        result = {
            "ok": True, "path": os.path.abspath(args.output),
            "source_resolution": f"{info['width']}x{info['height']}",
            "stage_resolutions": [s.get("resolution") for s in stages
                                  if s.get("resolution")],
            "master_resolution": f"{final['width']}x{final['height']}",
            "bit_depth": depth, "reconstruction_models": models_run,
            "reconstructed": True, "resolution_label": args.target,
            "fps": final["fps"], "duration_s": final["duration_s"],
            "size_bytes": os.path.getsize(os.path.abspath(args.output)),
            "elapsed_s": round(time.time() - t_start, 1), "stages": stages,
        }
        emit("done", f"{result['master_resolution']} en {result['elapsed_s']}s")
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 3-4
    if args.no_upscale:
        up_dir = frames_dir
        final_short = min(info["width"], info["height"])
        emit("upscale", "saute (--no-upscale)")
    else:
        emit("upscale_start",
             f"reconstruction x4 puis descente vers petit cote {target_short}")
        upscale_frames(frames_dir, up_dir, names, target_short, args.resume)
        reconstructed = True
        models_run.append("RealESRGAN_x4plus (RRDBNet x4 + descente Lanczos)")
        final_short = target_short
        from PIL import Image
        with Image.open(os.path.join(up_dir, names[0])) as im:
            fw, fh = im.size
        stages.append({"stage": "reconstruction",
                       "model": "RealESRGAN_x4plus",
                       "resolution": f"{fw}x{fh}"})

    # 5-7
    out_fps = args.fps or info["fps"]
    emit("assemble", f"master {args.codec}, {out_fps:.0f} fps"
                     + (f", grain {args.grain}" if args.grain else ""))
    audio = src if has_audio(src) else None
    depth = assemble(up_dir, audio, os.path.abspath(args.output),
                     info["fps"], out_fps, args.grain, args.codec)

    final = probe(os.path.abspath(args.output))
    stages.append({"stage": "master",
                   "resolution": f"{final['width']}x{final['height']}",
                   "fps": final["fps"], "depth": depth,
                   "grain": args.grain, "audio": bool(audio)})

    if not args.keep_frames and not args.resume:
        shutil.rmtree(workdir, ignore_errors=True)

    # Etiquette honnete : on ne revendique une classe de resolution que si une
    # reconstruction a reellement tourne. Un agrandissement par filtre n'est
    # pas un master 4K.
    label = args.target if reconstructed else f"{args.target}-par-filtre-NON-RECONSTRUIT"

    result = {
        "ok": True,
        "path": os.path.abspath(args.output),
        # --- les cinq champs de verite (loi §4.3) ---
        "source_resolution": f"{info['width']}x{info['height']}",
        "stage_resolutions": [s.get("resolution") for s in stages if s.get("resolution")],
        "master_resolution": f"{final['width']}x{final['height']}",
        "bit_depth": depth,
        "reconstruction_models": models_run,
        # --------------------------------------------
        "reconstructed": reconstructed,
        "resolution_label": label,
        "fps": final["fps"],
        "duration_s": final["duration_s"],
        "size_bytes": os.path.getsize(os.path.abspath(args.output)),
        "elapsed_s": round(time.time() - t_start, 1),
        "stages": stages,
    }
    emit("done", f"{result['master_resolution']} en {result['elapsed_s']}s")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
