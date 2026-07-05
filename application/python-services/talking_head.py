"""
talking_head.py -- Service qui genere une video realiste d un personnage qui parle
depuis une image (FLUX) + un audio (Kokoro WAV).

Utilise SadTalker (Apache 2.0) -- modele IA qui anime les levres, les yeux, et
la tete de facon realiste. Resultat: MP4 qui peut etre joue directement dans
VoiceCopilote.

Installation prerequise (1 fois, ~2GB):
  cd application/python-services
  git clone https://github.com/OpenTalker/SadTalker.git
  cd SadTalker && pip install -r requirements.txt && bash scripts/download_models.sh

Features:
  - Cache intelligent par hash(image+audio): les phrases identiques reutilisent le MP4
  - Mode idle: genere un MP4 loope silencieux de respiration (pour quand rien n est dit)
  - Qualite max: size=512, enhancer=gfpgan pour un rendu ultra-realiste
  - Mode rapide: size=256 pour latence <8s sur RTX 5070 Ti

Usage:
  python talking_head.py --mode check
  python talking_head.py --mode generate --image avatar.png --audio speech.wav --output out.mp4
  python talking_head.py --mode idle --image avatar.png --output idle.mp4 --duration 3
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

WORKSPACE = str(Path(__file__).parent.parent)
SADTALKER_DIR = os.path.join(os.path.dirname(__file__), "SadTalker")
SADTALKER_SCRIPT = os.path.join(SADTALKER_DIR, "inference.py")
CHECKPOINT_DIR = os.path.join(SADTALKER_DIR, "checkpoints")
# Cache persistant des videos generees
CACHE_DIR = os.path.join(WORKSPACE, "temp", "talking_head_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def emit(pct: int, detail: str):
    print(f"PROGRESS:{pct}:{detail}", flush=True)


def check_installation() -> dict:
    """Verifie si SadTalker est installe et pret a l emploi."""
    info = {
        "sadtalker_dir_exists": os.path.isdir(SADTALKER_DIR),
        "inference_script_exists": os.path.isfile(SADTALKER_SCRIPT),
        "checkpoint_dir_exists": os.path.isdir(CHECKPOINT_DIR),
        "checkpoints": [],
    }

    if info["checkpoint_dir_exists"]:
        try:
            files = os.listdir(CHECKPOINT_DIR)
            info["checkpoints"] = [f for f in files if f.endswith(('.pth', '.safetensors', '.ckpt'))]
        except Exception:
            pass

    required_checkpoints = [
        "SadTalker_V0.0.2_256.safetensors",
        "SadTalker_V0.0.2_512.safetensors",
        "mapping_00109-model.pth.tar",
    ]
    info["has_required_checkpoints"] = any(
        any(req in cp for req in required_checkpoints) for cp in info["checkpoints"]
    )

    info["ready"] = (
        info["sadtalker_dir_exists"]
        and info["inference_script_exists"]
        and info["checkpoint_dir_exists"]
        and info["has_required_checkpoints"]
    )
    return info


def file_hash(path: str, algo: str = "sha256") -> str:
    """Hash rapide d un fichier pour le cache. Lit par blocs de 64KB."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]  # 16 chars suffit pour notre cache


def compute_cache_key(image_path: str, audio_path: str, extra: str = "") -> str:
    """Genere une cle de cache deterministe basee sur l image + l audio + params."""
    img_h = file_hash(image_path) if os.path.isfile(image_path) else "none"
    aud_h = file_hash(audio_path) if os.path.isfile(audio_path) else "none"
    extra_h = hashlib.sha256(extra.encode()).hexdigest()[:8] if extra else "x"
    return f"{img_h}_{aud_h}_{extra_h}"


def get_cached_video(cache_key: str) -> str | None:
    """Retourne le chemin du MP4 cache si present, sinon None."""
    cached = os.path.join(CACHE_DIR, f"{cache_key}.mp4")
    if os.path.isfile(cached) and os.path.getsize(cached) > 1000:
        return cached
    return None


def save_to_cache(src_mp4: str, cache_key: str) -> str:
    """Copie le MP4 genere dans le cache et retourne son chemin final."""
    dest = os.path.join(CACHE_DIR, f"{cache_key}.mp4")
    try:
        shutil.copy2(src_mp4, dest)
        return dest
    except Exception as e:
        emit(99, f"Cache save failed (non bloquant): {e}")
        return src_mp4


def generate_silent_wav(duration_sec: float, output_path: str, sample_rate: int = 16000) -> bool:
    """Genere un WAV silencieux de duree donnee (pour le mode idle)."""
    try:
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            frames = int(sample_rate * duration_sec)
            # Frames silencieux (valeur 0)
            wf.writeframes(b"\x00\x00" * frames)
        return True
    except Exception as e:
        emit(0, f"Failed to generate silent WAV: {e}")
        return False


def run_sadtalker(
    image_path: str,
    audio_path: str,
    output_path: str,
    size: int = 256,
    use_enhancer: bool = True,
    use_cache: bool = True,
) -> tuple[bool, str]:
    """Lance SadTalker pour generer la video. Retourne (success, detail|path)."""
    # CRITIQUE: le subprocess SadTalker tourne avec cwd=SADTALKER_DIR, donc
    # les paths relatifs appele d ailleurs (ex: bridge) ne seraient pas trouves.
    # On convertit TOUT en absolu ici.
    image_path = os.path.abspath(image_path)
    audio_path = os.path.abspath(audio_path)
    output_path = os.path.abspath(output_path)

    if not os.path.isfile(image_path):
        return False, f"Image introuvable: {image_path}"
    if not os.path.isfile(audio_path):
        return False, f"Audio introuvable: {audio_path}"

    # Cache hit: reutilise le MP4 deja genere pour cette combinaison
    if use_cache:
        extra = f"s{size}_{'gfpgan' if use_enhancer else 'noenh'}"
        cache_key = compute_cache_key(image_path, audio_path, extra)
        cached = get_cached_video(cache_key)
        if cached:
            emit(100, f"Cache hit: {os.path.basename(cached)}")
            try:
                shutil.copy2(cached, output_path)
                return True, output_path
            except Exception:
                return True, cached

    info = check_installation()
    if not info["ready"]:
        hint = (
            "Installation SadTalker incomplete. Pour activer l avatar video realiste:\n"
            "  cd application/python-services\n"
            "  git clone https://github.com/OpenTalker/SadTalker.git\n"
            "  cd SadTalker\n"
            "  pip install -r requirements.txt\n"
            "  bash scripts/download_models.sh\n"
            "Apres installation, relance: python talking_head.py --mode check"
        )
        return False, hint

    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    emit(10, f"Lancement SadTalker (size={size}, enhancer={use_enhancer})...")
    cmd = [
        sys.executable,
        SADTALKER_SCRIPT,
        "--driven_audio", audio_path,
        "--source_image", image_path,
        "--result_dir", out_dir,
        "--still",
        "--preprocess", "full",
        "--size", str(size),
    ]
    if use_enhancer:
        cmd += ["--enhancer", "gfpgan"]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=SADTALKER_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        start = time.time()
        last_progress = 10
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            # Progress parse: SadTalker affiche souvent des logs de type "X/Y frames"
            # On emet simplement un progress proportionnel au temps ecoule (heuristique).
            elapsed = time.time() - start
            pct = min(90, 10 + int(elapsed * 2))
            if pct != last_progress:
                emit(pct, f"Generation video... ({int(elapsed)}s)")
                last_progress = pct

        proc.wait(timeout=300)
        # Note: on ne FAIL PAS automatiquement sur returncode != 0.
        # SadTalker peut retourner un code non-zero pour des warnings ffmpeg/opencv
        # alors que le MP4 est bien genere. On check la presence du fichier a la place.

        # SadTalker genere les MP4 dans un sous-dossier timestamp du result_dir,
        # et un MP4 final a la racine du result_dir avec le nom du timestamp.
        # On cherche le MP4 le plus recent dans out_dir (racine ET sous-dossiers).
        def find_recent_mp4(root_dir: str) -> str | None:
            candidates: list[tuple[float, str]] = []
            for item in os.listdir(root_dir):
                full = os.path.join(root_dir, item)
                if os.path.isfile(full) and item.endswith('.mp4'):
                    candidates.append((os.path.getmtime(full), full))
                elif os.path.isdir(full):
                    try:
                        for sub in os.listdir(full):
                            subfull = os.path.join(full, sub)
                            if os.path.isfile(subfull) and sub.endswith('.mp4'):
                                candidates.append((os.path.getmtime(subfull), subfull))
                    except OSError:
                        pass
            if not candidates:
                return None
            candidates.sort(reverse=True)
            # Preferer les MP4 racine (resultat final) si recents
            for mtime, path in candidates:
                if os.path.dirname(path) == root_dir:
                    return path
            return candidates[0][1]

        src_mp4_full = find_recent_mp4(out_dir)
        if not src_mp4_full:
            return False, f"Aucun .mp4 genere par SadTalker (returncode={proc.returncode})"
        src_mp4 = src_mp4_full
        # Override "generated" pour le code suivant qui s attend a un chemin complet
        generated_paths = [src_mp4]  # pour compat visuelle

        # Si fail returncode et PAS de mp4 -> vraie erreur
        if proc.returncode != 0 and not os.path.isfile(src_mp4):
            return False, f"SadTalker a retourne un code {proc.returncode} sans produire de MP4"

        # src_mp4 est deja defini plus haut via find_recent_mp4
        _ = generated_paths  # garde reference (log future)
        if src_mp4 != output_path:
            try:
                shutil.move(src_mp4, output_path)
            except Exception:
                shutil.copy2(src_mp4, output_path)

        # Cache persistant: sauvegarde pour reutilisation future
        if use_cache:
            save_to_cache(output_path, cache_key)

        return True, output_path
    except subprocess.TimeoutExpired:
        return False, "SadTalker timeout (>180s)"
    except Exception as e:
        return False, f"Erreur: {e}"


def run_idle(image_path: str, output_path: str, duration_sec: float = 3.0, size: int = 256) -> tuple[bool, str]:
    """Genere une video idle (silence) du personnage qui respire / cligne.
    Utilise pour le loop quand Aurora ne parle pas."""
    # Genere un WAV silencieux
    silent_wav = os.path.join(CACHE_DIR, f"silent_{int(duration_sec*1000)}ms.wav")
    if not os.path.isfile(silent_wav):
        if not generate_silent_wav(duration_sec, silent_wav):
            return False, "Generation WAV silencieux echouee"
    # Reuse run_sadtalker avec cache force (une idle par image = 1 seul MP4)
    return run_sadtalker(image_path, silent_wav, output_path, size=size, use_enhancer=True, use_cache=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["generate", "check", "idle"], default="generate")
    parser.add_argument("--image", help="Chemin de l image source (PNG/JPG)")
    parser.add_argument("--audio", help="Chemin du WAV (Kokoro TTS output)")
    parser.add_argument("--output", help="Chemin du MP4 de sortie")
    parser.add_argument("--duration", type=float, default=3.0, help="Duree idle en secondes (mode idle)")
    parser.add_argument("--size", type=int, default=256, choices=[256, 512], help="Taille de rendu (256 rapide, 512 qualite)")
    parser.add_argument("--no-enhancer", action="store_true", help="Skip GFPGAN enhancer (plus rapide)")
    parser.add_argument("--no-cache", action="store_true", help="Ignore le cache MP4")
    args = parser.parse_args()

    if args.mode == "check":
        info = check_installation()
        # Ajoute les infos de cache
        try:
            cache_files = os.listdir(CACHE_DIR)
            info["cache_dir"] = CACHE_DIR
            info["cache_entries"] = len([f for f in cache_files if f.endswith('.mp4')])
            info["cache_size_mb"] = round(sum(
                os.path.getsize(os.path.join(CACHE_DIR, f)) for f in cache_files if f.endswith('.mp4')
            ) / (1024 * 1024), 2)
        except Exception:
            pass
        print(json.dumps({"ok": info["ready"], "info": info}))
        sys.exit(0 if info["ready"] else 1)

    if args.mode == "idle":
        if not args.image or not args.output:
            print(json.dumps({"ok": False, "error": "--image et --output requis en mode idle"}))
            sys.exit(1)
        emit(0, f"Generation idle video: {args.image} ({args.duration}s)")
        ok, detail = run_idle(args.image, args.output, args.duration, args.size)
        if ok:
            emit(100, "Idle video OK")
            print(json.dumps({
                "ok": True,
                "video_path": args.output,
                "mode": "idle",
                "duration_sec": args.duration,
            }))
        else:
            print(json.dumps({"ok": False, "error": detail}))
            sys.exit(1)
        return

    # mode == "generate"
    if not args.image or not args.audio or not args.output:
        print(json.dumps({"ok": False, "error": "--image, --audio et --output sont requis en mode generate"}))
        sys.exit(1)

    emit(0, f"Avatar video: {args.image} + {args.audio}")
    ok, detail = run_sadtalker(
        args.image, args.audio, args.output,
        size=args.size,
        use_enhancer=not args.no_enhancer,
        use_cache=not args.no_cache,
    )

    if ok:
        emit(100, "Video generee avec succes")
        try:
            size = os.path.getsize(args.output)
        except OSError:
            size = 0
        print(json.dumps({
            "ok": True,
            "video_path": args.output,
            "size_bytes": size,
            "cached": os.path.dirname(args.output) == CACHE_DIR,
        }))
    else:
        emit(100, f"Echec: {detail[:80]}")
        print(json.dumps({
            "ok": False,
            "error": detail,
            "install_hint": detail if "Installation" in detail else None,
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
