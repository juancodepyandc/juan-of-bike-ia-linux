"""
Genere un avatar 3D via FLUX (ComfyUI) + Hunyuan3D.
Pipeline complet:
  1. Generer image de reference via FLUX (ComfyUI) ou fallback web
  2. Generer mesh 3D via Hunyuan3D (GPU)
  3. Sauvegarder le GLB

Usage: python generate_avatar.py --prompt "Natsu Dragneel" --output avatar.glb
Toute la sortie standard est du JSON ou des PROGRESS:pct:detail.
Le JSON final est TOUJOURS emis sur la DERNIERE ligne de stderr pour eviter
la confusion avec les lignes PROGRESS sur stdout.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

WORKSPACE = str(Path(__file__).parent.parent)
COMFY_URL = "http://127.0.0.1:8188"
_comfy_proc = None  # Handle du process ComfyUI pour cleanup


def emit(pct: int, detail: str):
    """Emet le pourcentage et le detail pour le suivi UI."""
    print(f"PROGRESS:{pct}:{detail}", flush=True)


def comfy_available() -> bool:
    try:
        req = urllib.request.Request(f"{COMFY_URL}/system_stats")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _comfy_post(endpoint: str, data: bytes, timeout: int = 10):
    """POST to ComfyUI, auto-detect /api prefix."""
    for prefix in ["", "/api"]:
        try:
            url = f"{COMFY_URL}{prefix}{endpoint}"
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
    return None


def _comfy_get(endpoint: str, timeout: int = 5):
    """GET from ComfyUI, auto-detect /api prefix. Returns open response."""
    for prefix in ["", "/api"]:
        try:
            url = f"{COMFY_URL}{prefix}{endpoint}"
            req = urllib.request.Request(url)
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
    return None


def wake_comfyui() -> bool:
    """Auto-demarre ComfyUI si non actif. Cherche l'installation locale."""
    if comfy_available():
        return True

    emit(3, "ComfyUI non detecte — tentative de demarrage automatique...")

    candidates = [
        os.path.join(WORKSPACE, "..", "modele", "comfyui", "comfyui"),
        os.path.join(WORKSPACE, "..", "modele", "comfyui"),
    ]

    comfy_dir = None
    for c in candidates:
        main_py = os.path.join(c, "main.py")
        if os.path.exists(main_py):
            comfy_dir = os.path.abspath(c)
            break

    if not comfy_dir:
        emit(3, "ComfyUI introuvable")
        return False

    python_path = sys.executable
    venv_python = os.path.join(comfy_dir, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        python_path = venv_python
    else:
        embedded = os.path.join(comfy_dir, "python_embeded", "python.exe")
        if os.path.exists(embedded):
            python_path = embedded

    emit(3, f"Demarrage ComfyUI...")

    global _comfy_proc
    try:
        log_out = os.path.join(comfy_dir, "comfyui_stdout.log")
        log_err = os.path.join(comfy_dir, "comfyui_stderr.log")
        with open(log_out, "w") as fout, open(log_err, "w") as ferr:
            _comfy_proc = subprocess.Popen(
                [python_path, "main.py", "--listen", "127.0.0.1", "--port", "8188",
                 "--preview-method", "auto", "--lowvram"],
                cwd=comfy_dir,
                stdout=fout, stderr=ferr,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

        for i in range(30):
            time.sleep(2)
            emit(3 + i, f"Attente ComfyUI... ({i * 2}s)")
            if comfy_available():
                emit(5, "ComfyUI demarre avec succes !")
                return True

        emit(5, "ComfyUI n'a pas repondu dans les 60s")
        return False
    except Exception as e:
        emit(3, f"Erreur demarrage ComfyUI: {str(e)[:80]}")
        return False


def stop_comfyui():
    """Arrete ComfyUI pour liberer la VRAM avant Hunyuan3D."""
    global _comfy_proc
    if _comfy_proc:
        emit(48, "Arret de ComfyUI pour liberer la VRAM...")
        try:
            _comfy_proc.terminate()
            _comfy_proc.wait(timeout=10)
        except Exception:
            try:
                _comfy_proc.kill()
            except Exception:
                pass
        _comfy_proc = None
    # Aussi tuer tout process ComfyUI orphelin sur le port
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/FI", "WINDOWTITLE eq ComfyUI*"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass
    import gc; gc.collect()


def build_avatar_prompt(user_prompt: str, research_brief: str = "") -> tuple[str, str]:
    """Construit (positive, negative) prompts pour un portrait utilisable par un avatar anime.

    research_brief: resultat optionnel de character_research.py avec infos canoniques
    (type du personnage, couleurs, anatomie faciale, accessoires). Injecte dans le prompt
    pour eviter les surprises type "dragon a cote", "profil 3/4", etc.
    """
    # Positive: on force explicitement le cadrage + pose + composition pour avoir un
    # visage utilisable (animation 2D lip-sync / SadTalker).
    positive_parts = [
        f"professional portrait of {user_prompt},",
    ]
    if research_brief.strip():
        positive_parts.append(f"{research_brief.strip()},")
    positive_parts.extend([
        "HEAD AND SHOULDERS framing, chest up ONLY,",
        "facing the camera directly, EYES LOOKING STRAIGHT AT the viewer,",
        "fully frontal view, symmetric composition, head centered and upright,",
        "neutral calm facial expression, MOUTH CLOSED and visible,",
        "both eyes clearly visible and symmetric,",
        "clean isolated solid dark grey background, no scenery, no environment,",
        "soft studio lighting, high quality face details,",
        "sharp focus on the face, photographic clarity, passport-style portrait composition",
    ])
    positive = " ".join(positive_parts)

    # Negative: on liste TOUT ce qu on ne veut pas (le gros levier anti-artwork).
    negative_parts = [
        # Poses/angles non-utilisables pour animation
        "side profile, back view, 3/4 view, tilted head, looking away, looking sideways,",
        "face cut off, cropped face, face not visible, head not in frame,",
        "eyes closed, eyes covered, mouth wide open, extreme expression,",
        # Contexte narratif parasite
        "dragon, monster, creature companion, pet, animal, sword, gun, weapon, shield,",
        "fire, explosion, action pose, combat, fighting stance, dynamic pose,",
        "multiple people, group shot, crowd, background characters,",
        # Fond / environnement
        "landscape, outdoor scene, forest, castle, sky, clouds, fantasy scenery,",
        "complex background, busy background, foreground objects, props in front of face,",
        # Style
        "cartoon sketch, rough drawing, concept art sketch, unfinished lines,",
        "low resolution, blurry, out of focus, motion blur,",
        "text, watermark, signature, logo, frame, border",
    ]
    negative = " ".join(negative_parts)
    return positive, negative


def generate_image_comfy(prompt: str, output_path: str, research_brief: str = "") -> bool:
    """Genere une image via FLUX dans ComfyUI avec prompt + negative prompt."""
    emit(5, "Preparation du workflow FLUX...")

    positive_text, negative_text = build_avatar_prompt(prompt, research_brief)
    emit(6, f"Prompt positif: {positive_text[:100]}...")
    emit(7, f"Prompt negatif: {negative_text[:80]}...")

    workflow = {
        "6": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1}
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["13", 0], "vae": ["10", 0]}
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "aurora_avatar_ref", "images": ["8", 0]}
        },
        "10": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-vae.safetensors"}
        },
        "11": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2"}
        },
        "12": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_text, "clip": ["11", 0]}
        },
        # Node 12b: prompt negatif distinct (FLUX.2 gere le negative via CFGGuider)
        "12b": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_text, "clip": ["11", 0]}
        },
        # FLUX.2 sampling: Flux2Scheduler + KSamplerSelect + CFGGuider + RandomNoise + SamplerCustomAdvanced
        "40": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 28, "width": 1024, "height": 1024}
        },
        "41": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"}
        },
        "42": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["14", 0], "positive": ["12", 0], "negative": ["12b", 0], "cfg": 5.0}
        },
        "43": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": random.randint(0, 2**32)}
        },
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["43", 0],
                "guider": ["42", 0],
                "sampler": ["41", 0],
                "sigmas": ["40", 0],
                "latent_image": ["6", 0]
            }
        },
        "14": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}
        }
    }

    try:
        emit(10, "Envoi du workflow a ComfyUI (FLUX)...")
        payload = json.dumps({"prompt": workflow}).encode()
        result = _comfy_post("/prompt", payload, timeout=10)
        if not result:
            emit(10, "Erreur: aucun endpoint ComfyUI /prompt valide")
            return False
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            emit(10, f"Erreur ComfyUI: {result}")
            return False

        emit(15, f"Generation FLUX en cours...")

        for i in range(120):
            time.sleep(2)
            pct = 15 + min(i, 30)
            try:
                hr = _comfy_get(f"/history/{prompt_id}", timeout=5)
                if hr:
                    history = json.loads(hr.read())
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        for node_id, node_out in outputs.items():
                            images = node_out.get("images", [])
                            if images:
                                img = images[0]
                                img_ep = f"/view?filename={urllib.parse.quote(img['filename'])}&subfolder={img.get('subfolder','')}&type={img.get('type','output')}"
                                emit(45, "Image generee, telechargement...")
                                ir = _comfy_get(img_ep, timeout=15)
                                if ir:
                                    with open(output_path, "wb") as f:
                                        f.write(ir.read())
                                    if os.path.getsize(output_path) > 10000:
                                        emit(50, "Image de reference FLUX prete")
                                        return True
            except Exception:
                pass
            emit(pct, f"FLUX en cours... ({i*2}s)")

        emit(45, "Timeout FLUX")
        return False

    except Exception as e:
        emit(10, f"Erreur FLUX: {str(e)[:100]}")
        return False


def generate_image_fallback(prompt: str, output_path: str) -> bool:
    """Fallback: image web via Crawl4AI ou thispersondoesnotexist."""
    emit(10, "ComfyUI indisponible — recherche image web...")

    # Essayer Crawl4AI d'abord
    try:
        crawl_script = os.path.join(os.path.dirname(__file__), "crawl4ai_search.py")
        if os.path.exists(crawl_script):
            emit(12, "Recherche image via Crawl4AI...")
            # Query specialisee pour obtenir un portrait tete+buste frontal
            result = subprocess.run(
                [sys.executable, crawl_script, "--mode", "images",
                 "--query", f"{prompt} portrait headshot front facing shoulders up",
                 "--limit", "3"],
                capture_output=True, timeout=20,
                cwd=os.path.dirname(__file__),
            )
            if result.returncode == 0:
                data = json.loads(result.stdout.decode("utf-8", errors="replace"))
                if data.get("ok") and data.get("images"):
                    img_url = data["images"][0]["url"]
                    emit(15, f"Telechargement image reference...")
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                    req = urllib.request.Request(img_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as r:
                        with open(output_path, "wb") as f:
                            f.write(r.read())
                        if os.path.getsize(output_path) > 5000:
                            emit(50, "Image de reference obtenue (web)")
                            return True
    except Exception as e:
        emit(12, f"Crawl4AI: {str(e)[:60]}")

    # Fallback: thispersondoesnotexist.com
    try:
        emit(15, "Fallback: generation visage aleatoire...")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        req = urllib.request.Request("https://thispersondoesnotexist.com", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            with open(output_path, "wb") as f:
                f.write(r.read())
            if os.path.getsize(output_path) > 5000:
                emit(50, "Image de reference obtenue (visage genere)")
                return True
    except Exception as e:
        emit(15, f"Erreur web: {e}")

    return False


def run_hunyuan3d(image_path: str, output_glb: str) -> tuple[bool, str]:
    """Lance Hunyuan3D sur GPU. Retourne (success, error_detail)."""
    emit(55, "Lancement Hunyuan3D sur GPU...")

    run_id = f"avatar_{int(time.time())}"
    out_dir = os.path.join(WORKSPACE, "temp", "avatar_gen")
    os.makedirs(out_dir, exist_ok=True)

    script = os.path.join(WORKSPACE, "python-services", "hunyuan3d_run.py")
    if not os.path.exists(script):
        return False, f"Script introuvable: {script}"

    cmd = [
        sys.executable, script,
        "--image", image_path,
        "--output-dir", out_dir,
        "--run-id", run_id,
        "--format", "glb",
        "--intent-purpose", "character_head",
        "--motion-readiness", "static_only",
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=WORKSPACE, bufsize=1,
        )
    except Exception as e:
        return False, f"Impossible de lancer Hunyuan3D: {e}"

    last_detail = ""
    step = 0
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("PROGRESS:"):
            parts = line.split(":", 2)
            if len(parts) >= 3:
                detail = parts[2][:100]
                last_detail = detail
                step += 1
                pct = min(55 + step * 2, 92)
                emit(pct, detail)
        elif line.startswith("SAVED:"):
            emit(95, "Mesh 3D genere !")
        elif "error" in line.lower() or "exception" in line.lower():
            last_detail = line[:150]

    proc.wait()

    if proc.returncode != 0:
        return False, last_detail or f"Hunyuan3D exit code {proc.returncode}"

    # Trouver le GLB
    for f in os.listdir(out_dir):
        if f.endswith(".glb") and run_id in f:
            os.makedirs(os.path.dirname(output_glb) or ".", exist_ok=True)
            shutil.copy2(os.path.join(out_dir, f), output_glb)
            size_mb = os.path.getsize(output_glb) / 1e6
            emit(98, f"GLB: {size_mb:.1f} MB")
            return True, ""

    for f in os.listdir(out_dir):
        if f.endswith(".glb"):
            os.makedirs(os.path.dirname(output_glb) or ".", exist_ok=True)
            shutil.copy2(os.path.join(out_dir, f), output_glb)
            return True, ""

    return False, "Aucun fichier GLB genere"


def run_character_research(user_prompt: str, lang: str = "fr") -> dict:
    """Lance character_research.py en subprocess et retourne le brief.
    Retourne {} si echec (pas bloquant pour la generation)."""
    try:
        script = os.path.join(os.path.dirname(__file__), "character_research.py")
        if not os.path.isfile(script):
            return {}
        proc = subprocess.run(
            [sys.executable, script, "--prompt", user_prompt, "--lang", lang],
            capture_output=True, text=True, timeout=90,
        )
        if proc.returncode != 0:
            emit(5, f"Character research failed (non bloquant): {proc.stderr[:150] if proc.stderr else 'unknown'}")
            return {}
        # Parse le JSON final
        for line in reversed([l.strip() for l in proc.stdout.split("\n") if l.strip()]):
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if data.get("ok"):
                        return data
                except json.JSONDecodeError:
                    continue
        return {}
    except Exception as e:
        emit(5, f"Research exception (non bloquant): {e}")
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--image-only", action="store_true",
                        help="Skip Hunyuan3D, return only the FLUX image (fast path for Live 2D avatar).")
    parser.add_argument("--skip-research", action="store_true",
                        help="Skip l etape de recherche personnage (plus rapide mais moins fidele).")
    parser.add_argument("--lang", default="fr", help="Langue pour la recherche Wikipedia")
    args = parser.parse_args()

    emit(0, f"Demarrage: {args.prompt}")

    # Etape 0: Recherche sur le personnage pour enrichir le prompt FLUX
    research: dict = {}
    if not args.skip_research:
        emit(1, "Recherche sur le personnage (Wikipedia + qwen3-vl)...")
        research = run_character_research(args.prompt, args.lang)
        if research:
            emit(4, f"Mode anim: {research.get('animation_mode', 'humanoid')} | Brief: {research.get('brief', '')[:60]}")

    if args.image_only:
        emit(5, "Pipeline: FLUX image only (Live 2D avatar path)")
    else:
        emit(5, "Pipeline: FLUX (image) -> Hunyuan3D (mesh 3D)")

    os.makedirs(os.path.join(WORKSPACE, "temp"), exist_ok=True)
    ref_path = os.path.join(WORKSPACE, "temp", "avatar_ref.png")

    # Etape 1: Image de reference — auto-wake ComfyUI si possible
    # Le brief de recherche est injecte dans le prompt FLUX pour eviter les derives
    research_brief = research.get("brief", "") if research else ""
    warnings = research.get("warnings", "") if research else ""
    if warnings:
        # Ajouter les warnings (elements a eviter) au prompt negatif
        research_brief = f"{research_brief}. Important: avoid {warnings}" if research_brief else f"avoid {warnings}"

    comfy_ready = wake_comfyui()
    has_ref = False
    if comfy_ready:
        emit(8, "ComfyUI pret — generation FLUX avec prompt enrichi")
        has_ref = generate_image_comfy(args.prompt, ref_path, research_brief)
    # Fallback web si FLUX echoue ou ComfyUI indisponible
    if not has_ref:
        has_ref = generate_image_fallback(args.prompt, ref_path)

    if not has_ref or not os.path.exists(ref_path) or os.path.getsize(ref_path) < 5000:
        emit(100, "Echec: pas d'image de reference")
        # JSON final TOUJOURS sur une ligne propre, pas mélangé avec PROGRESS
        print(json.dumps({"ok": False, "error": "Impossible d'obtenir une image de reference. Verifiez que ComfyUI est installe ou que l'acces internet fonctionne."}))
        sys.exit(1)

    # Mode image-only: on sauvegarde l image FLUX et on retourne directement.
    # C est le chemin rapide pour les avatars Live 2D (100% fidele, pas de Hunyuan3D).
    if args.image_only:
        img_dest = args.output.replace('.glb', '.png')
        if args.output.lower().endswith('.png'):
            img_dest = args.output
        try:
            shutil.copy2(ref_path, img_dest)
            emit(100, "Avatar 2D (image FLUX) genere avec succes !")
            print(json.dumps({
                "ok": True,
                "path": img_dest,
                "refImage": img_dest,
                "method": "flux+live2d" if comfy_ready else "web+live2d",
                "mode": "image_only",
                "animation_mode": research.get("animation_mode", "humanoid"),
                "research_brief": research.get("brief", ""),
                "how_they_speak": research.get("how_they_speak", ""),
            }))
            sys.exit(0)
        except Exception as copy_err:
            emit(100, f"Echec copie image: {copy_err}")
            print(json.dumps({"ok": False, "error": f"Impossible d ecrire l image: {copy_err}"}))
            sys.exit(1)

    # Liberer la VRAM de ComfyUI AVANT de lancer Hunyuan3D
    # (ComfyUI + Hunyuan3D ensemble = 8+ GB VRAM → crash 0xc000012d)
    stop_comfyui()

    # Etape 2: Mesh 3D
    success, error_detail = run_hunyuan3d(ref_path, args.output)

    if success and os.path.exists(args.output):
        # Copier l'image de reference a cote du GLB pour la projection texture frontend
        ref_dest = args.output.replace('.glb', '_ref.png')
        if os.path.exists(ref_path):
            try:
                shutil.copy2(ref_path, ref_dest)
                emit(99, "Image de reference copiee pour texture")
            except Exception:
                pass
        emit(100, "Avatar 3D genere avec succes !")
        print(json.dumps({
            "ok": True,
            "path": args.output,
            "refImage": ref_dest,
            "method": "flux+hunyuan3d" if comfy_ready else "web+hunyuan3d",
            "animation_mode": research.get("animation_mode", "humanoid"),
            "research_brief": research.get("brief", ""),
            "how_they_speak": research.get("how_they_speak", ""),
        }))
    else:
        emit(100, "Echec generation 3D")
        print(json.dumps({"ok": False, "error": error_detail or "Hunyuan3D a echoue. Verifiez que les modeles sont telecharges et que le GPU a assez de VRAM."}))
        sys.exit(1)


if __name__ == "__main__":
    main()
