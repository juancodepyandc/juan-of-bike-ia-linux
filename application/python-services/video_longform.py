#!/usr/bin/env python3
"""Orchestrateur de LONG METRAGE Aurora.

Le pipeline cinema existant rend une SCENE (quelques plans). Ce module ajoute
l'etage au-dessus : un film entier, decoupe en actes et en scenes, rendu scene
par scene, avec point de reprise, puis assemble et monte en resolution.

Pourquoi une couche separee plutot qu'un cinema_pipeline plus gros :
  - un long metrage se compte en DIZAINES D'HEURES de calcul ; il doit pouvoir
    etre interrompu et repris sans rien reperdre. Chaque scene est un artefact
    fini sur disque, valide independamment ;
  - la memoire de continuite (personnages, decors, palette) doit vivre AU-DESSUS
    des scenes, sinon chaque scene redemarre a zero et le film derive ;
  - l'estimation de temps ne peut se faire qu'a ce niveau.

ESTIMATION DE TEMPS : calibree sur des mesures reelles de CETTE machine
(RTX 5070 Ti 16 Go), pas sur des valeurs devinees. Voir CALIBRATION plus bas.
`--estimate-only` chiffre le film sans rien rendre — a lancer AVANT de partir
sur 40 heures de calcul.

TEXTE A L'IMAGE : aucun par defaut. Ni titre, ni sous-titre, ni carton. Le
prompt de chaque plan recoit une interdiction explicite, et les sous-titres ne
sont muxes que si --subtitles est passe. Un film n'a pas de texte incruste
sauf demande.

Usage :
  # chiffrer avant de s'engager
  python video_longform.py --brief "..." --minutes 10 --estimate-only

  # produire
  python video_longform.py --brief "..." --minutes 10 --out film.mp4

  # reprendre apres interruption
  python video_longform.py --project output/videos/film_xxx --resume
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.environ.get("AURORA_BRIDGE_URL", "http://127.0.0.1:3001")
OUT_ROOT = os.path.join(WORKSPACE, "output", "videos")

# ---------------------------------------------------------------------------
# CALIBRATION — mesures reelles, 2026-07-27, RTX 5070 Ti 16 Go
#
#   Test A : 704x1280 (0.90 Mpix), 60 steps, 97 frames -> 804 s
#            soit 804 / (97/24) = 199 s de calcul par seconde de video
#            soit 199 / 0.90 = 221 s par seconde de video et par Mpix
#
# On modelise donc le cout de generation comme lineaire en pixels et en steps,
# ce qui colle au comportement d'un DiT. Les autres postes viennent des
# journaux du pipeline cinema.
# ---------------------------------------------------------------------------
CALIB = {
    "gen_s_per_videosecond_per_mpix_at60steps": 230.0,  # moyenne des 2 mesures
    "ref_steps": 60,
    # surface reellement generee (le budget adaptatif plafonne, cf. estimate())
    "gen_mpix_premium": 0.51,
    "gen_mpix_balanced": 0.40,
    # fraction des plans de dialogue rendus en composite fixe (donc non generes)
    # tant qu'aucun moteur de lipsync anime n'est installe. Mesure : 1.0.
    "dialogue_still_fraction": 1.0,
    "flux_keyframe_s": 60.0,        # par tentative et par personnage
    "voice_s_per_dialogue_shot": 25.0,
    "qa_vision_s_per_shot": 18.0,   # par tentative
    "assembly_s_per_scene": 25.0,
    "upscale_s_per_frame_x4_gpu": 1.6,   # RealESRGAN x4 sur GPU
    "music_s_per_scene": 45.0,
}

NO_TEXT_CONTRACT = (
    "No text of any kind in frame: no title card, no caption, no subtitle, "
    "no watermark, no logo, no signage with readable words, no UI overlay."
)
NO_TEXT_NEGATIVE = (
    "text, caption, subtitle, title card, watermark, logo, letters, words, "
    "typography, signature, UI overlay"
)


def emit(stage, detail=""):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def post(path, payload, timeout=600):
    req = urllib.request.Request(
        BRIDGE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, timeout=60):
    with urllib.request.urlopen(BRIDGE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ffmpeg_bin():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


# ---------------------------------------------------------------- estimation
def parse_resolution(label, aspect):
    short = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}.get(label, 1080)
    ratio = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:3": 4 / 3}.get(aspect, 16 / 9)
    if ratio >= 1:
        h, w = short, int(short * ratio)
    else:
        w, h = short, int(short / ratio)
    return w - w % 32, h - h % 32


def estimate(total_minutes, n_scenes, shots_per_scene, dialogue_ratio,
             resolution, aspect, quality_mode, n_characters, upscale_target):
    """Estimation calibree. Retourne un dictionnaire de postes, en secondes."""
    # Le pipeline ne genere PAS a la resolution cible : le budget adaptatif de
    # video_generate.py plafonne la generation en Mpix-secondes, puis le master
    # est remonte. Estimer sur la resolution cible surestime d'un facteur 4.
    # Valeurs MESUREES sur cette machine (RTX 5070 Ti 16 Go) :
    #   - cinema 1080p premium 16:9  -> generation 960x536  = 0.51 Mpix
    #   - clip vertical premium 9:16 -> generation 704x1280 = 0.90 Mpix
    # Les deux mesures donnent 221 et 239 s par seconde-video et par Mpix :
    # la constante de calibration est coherente, c'est bien la surface generee
    # qui varie.
    gen_mpix = CALIB["gen_mpix_premium"] if quality_mode == "premium" \
        else CALIB["gen_mpix_balanced"]
    tw, th = parse_resolution(resolution, aspect)
    gen_ratio = math.sqrt(gen_mpix * 1e6 / max(1, tw * th))
    gen_w, gen_h = int(tw * gen_ratio), int(th * gen_ratio)
    steps = 60 if quality_mode == "premium" else 50
    attempts = {"premium": 3, "balanced": 2}.get(quality_mode, 1)

    video_seconds = total_minutes * 60.0
    n_shots = max(1, n_scenes * shots_per_scene)
    n_dialogue = int(n_shots * dialogue_ratio)

    # MESURE 2026-07-27 : dans l'etat actuel du pipeline, un plan de dialogue
    # en gros plan n'est PAS genere par le modele video — il est composite
    # (portrait + fond) puis fige en video, la bouche etant censee etre animee
    # par le lipsync. Mesure de mouvement inter-frames sur un film reel :
    # plans dialogues = 0.00 (totalement fixes), plans generes = 3.1 a 12.0.
    # Ces plans ne coutent donc quasiment rien en generation, ce qui expliquait
    # une surestimation d'un facteur 2.3 du modele initial.
    # ATTENTION : des qu'un vrai lipsync anime (S2V / InfiniteTalk) sera cable,
    # ces plans redeviendront generes et ce terme devra repasser a 1.0.
    animated_fraction = 1.0 - (dialogue_ratio * CALIB["dialogue_still_fraction"])
    generated_seconds = video_seconds * animated_fraction
    gen = (CALIB["gen_s_per_videosecond_per_mpix_at60steps"]
           * gen_mpix * generated_seconds * (steps / CALIB["ref_steps"]))
    # Les tentatives qualite ne rejouent qu'une fraction des plans (ceux qui
    # echouent la porte). Calibre sur un film reel : 15 % des plans rejoues par
    # tentative supplementaire. L'estimation conserve volontairement ~20 % de
    # marge de planification — mieux vaut annoncer trop que trop peu quand on
    # engage des jours de calcul.
    gen *= 1.0 + 0.15 * (attempts - 1)

    keyframes = CALIB["flux_keyframe_s"] * n_characters * 1.5 * max(1, n_scenes // 4)
    voice = CALIB["voice_s_per_dialogue_shot"] * n_dialogue
    qa = CALIB["qa_vision_s_per_shot"] * n_shots * attempts
    music = CALIB["music_s_per_scene"] * n_scenes
    assembly = CALIB["assembly_s_per_scene"] * n_scenes + 120

    upscale = 0.0
    if upscale_target:
        fps = 24
        upscale = CALIB["upscale_s_per_frame_x4_gpu"] * video_seconds * fps

    total = gen + keyframes + voice + qa + music + assembly + upscale
    return {
        "generation_s": round(gen),
        "keyframes_s": round(keyframes),
        "voice_s": round(voice),
        "qa_s": round(qa),
        "music_s": round(music),
        "assembly_s": round(assembly),
        "upscale_s": round(upscale),
        "total_s": round(total),
        "total_h": round(total / 3600.0, 1),
        "n_shots": n_shots,
        "gen_resolution": f"{gen_w}x{gen_h}",
        "steps": steps,
        "quality_attempts": attempts,
    }


def human_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h >= 24:
        return f"{h // 24} j {h % 24} h {m:02d} min"
    return f"{h} h {m:02d} min"


# ------------------------------------------------------------------ decoupage
def plan_structure(total_minutes, shot_seconds=5.0, shots_per_scene=6):
    """Decoupe une duree cible en scenes de longueur jouable."""
    total_shots = max(1, int(round(total_minutes * 60.0 / shot_seconds)))
    n_scenes = max(1, int(math.ceil(total_shots / shots_per_scene)))
    return n_scenes, shots_per_scene, total_shots


def build_scene_briefs(brief, n_scenes, model=None):
    """Demande au LLM local un decoupage en scenes (acte / lieu / enjeu)."""
    prompt = (
        "Tu es scenariste. Decoupe le projet suivant en exactement "
        f"{n_scenes} scenes qui s'enchainent et racontent une histoire complete.\n\n"
        f"PROJET : {brief}\n\n"
        "Reponds UNIQUEMENT par un tableau JSON de "
        f"{n_scenes} objets, sans texte autour, chaque objet ayant :\n"
        '  "titre" (court, en francais),\n'
        '  "lieu" (snake_case stable, reutilise si la scene se passe au meme endroit),\n'
        '  "resume" (2 phrases en francais, ce qui se passe),\n'
        '  "intention" (une phrase : l\'emotion ou l\'enjeu de la scene).\n'
        "Garde les memes personnages d'une scene a l'autre."
    )
    payload = {"model": model or "qwen3:30b-a3b-instruct-2507-q4_K_M",
               "prompt": prompt, "stream": False,
               "options": {"temperature": 0.6, "num_ctx": 8192}}
    req = urllib.request.Request(
        os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = json.loads(r.read().decode("utf-8")).get("response", "")
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\[.*\]", raw, flags=re.S)
    if not m:
        raise RuntimeError("le LLM n'a pas renvoye de tableau JSON de scenes")
    scenes = json.loads(m.group(0))
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("decoupage de scenes vide")
    return scenes


def enforce_no_text(storyboard, allow_text):
    """Interdit tout texte a l'image, sauf demande explicite."""
    if allow_text:
        return storyboard
    for shot in storyboard.get("shots", []):
        contract = (shot.get("action_contract") or "").strip()
        shot["action_contract"] = (contract + " " + NO_TEXT_CONTRACT).strip()
        neg = (shot.get("negative_prompt") or "").strip()
        parts = [p for p in (neg, NO_TEXT_NEGATIVE) if p]
        shot["negative_prompt"] = ", ".join(parts)
    storyboard.setdefault("subtitles", {})["enabled"] = False
    return storyboard


# ------------------------------------------------------------------- rendu
def wait_job(job_id, poll=20, label=""):
    while True:
        try:
            st = get(f"/api/cinema/job/{job_id}")
        except Exception:
            time.sleep(poll)
            continue
        s = st.get("status")
        if s in {"done", "error", "failed", "cancelled"}:
            return st
        eta = st.get("eta") or {}
        if eta.get("remaining_s"):
            emit("scene_eta", f"{label} reste ~{human_time(eta['remaining_s'])}")
        time.sleep(poll)


def render_scene(scene, idx, project, cfg):
    scene_dir = os.path.join(project, f"scene_{idx:03d}")
    os.makedirs(scene_dir, exist_ok=True)
    done_marker = os.path.join(scene_dir, "scene.mp4")
    if os.path.exists(done_marker) and os.path.getsize(done_marker) > 10000:
        emit("scene_skip", f"scene {idx} deja rendue (reprise)")
        return done_marker

    hint = (
        f"{scene.get('resume','')} Intention : {scene.get('intention','')}. "
        f"Lieu : {scene.get('lieu','')}."
    )
    emit("scene_storyboard", f"scene {idx}/{cfg['n_scenes']} : {scene.get('titre','')}")
    sb = post("/api/cinema/storyboard", {
        "prompt": hint,
        "hints": {"aspect": cfg["aspect"], "resolution": cfg["resolution"],
                  "lengthHint": f"{cfg['shots_per_scene'] * 5}s",
                  "style": cfg["style"]},
    }, timeout=900)
    storyboard = sb.get("storyboard")
    if not storyboard:
        raise RuntimeError(f"storyboard vide pour la scene {idx}: {sb.get('error')}")

    storyboard["quality_mode"] = cfg["quality_mode"]
    storyboard["resolution"] = cfg["resolution"]
    storyboard["aspect"] = cfg["aspect"]
    storyboard["style"] = cfg["style"]
    storyboard["music"] = {"enabled": cfg["music"],
                           "prompt": cfg.get("music_prompt", "")}
    storyboard = enforce_no_text(storyboard, cfg["allow_text"])
    with open(os.path.join(scene_dir, "storyboard.json"), "w") as f:
        json.dump(storyboard, f, ensure_ascii=False, indent=2)

    emit("scene_render", f"scene {idx}/{cfg['n_scenes']} lancee")
    job = post("/api/cinema/generate", {"storyboard": storyboard}, timeout=300)
    jid = job.get("jobId")
    if not jid:
        raise RuntimeError(f"job non cree pour la scene {idx}: {job}")
    with open(os.path.join(scene_dir, "job.json"), "w") as f:
        json.dump({"jobId": jid, "outputPath": job.get("outputPath")}, f)

    st = wait_job(jid, label=f"scene {idx}")
    if st.get("status") != "done":
        raise RuntimeError(f"scene {idx} echouee: {st.get('status')} {st.get('error')}")
    src = (st.get("result") or {}).get("video") or job.get("outputPath")
    if not src or not os.path.exists(src):
        raise RuntimeError(f"scene {idx}: fichier introuvable ({src})")
    shutil.copy2(src, done_marker)
    with open(os.path.join(scene_dir, "result.json"), "w") as f:
        json.dump(st.get("result") or {}, f, ensure_ascii=False, indent=2)
    return done_marker


def concat_scenes(paths, out_path):
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", "-movflags", "+faststart", out_path],
        check=True, timeout=3600,
    )
    os.remove(lst)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--style", default="realistic")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--resolution", default="1080p")
    ap.add_argument("--quality-mode", default="premium",
                    choices=["auto", "balanced", "premium"])
    ap.add_argument("--shots-per-scene", type=int, default=6)
    ap.add_argument("--shot-seconds", type=float, default=5.0)
    ap.add_argument("--characters", type=int, default=2)
    ap.add_argument("--dialogue-ratio", type=float, default=0.5)
    ap.add_argument("--music", action="store_true", default=True)
    ap.add_argument("--music-prompt", default="")
    ap.add_argument("--allow-text", action="store_true",
                    help="autorise le texte a l'image (desactive par defaut)")
    ap.add_argument("--subtitles", action="store_true")
    ap.add_argument("--upscale", default="", choices=["", "1440p", "4k"])
    ap.add_argument("--project", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--model", default="")
    args = ap.parse_args()

    n_scenes, spc, total_shots = plan_structure(
        args.minutes, args.shot_seconds, args.shots_per_scene)

    est = estimate(args.minutes, n_scenes, spc, args.dialogue_ratio,
                   args.resolution, args.aspect, args.quality_mode,
                   args.characters, args.upscale)

    if args.estimate_only:
        print(json.dumps({
            "ok": True, "estimate_only": True,
            "minutes": args.minutes, "n_scenes": n_scenes,
            "shots_per_scene": spc, "total_shots": total_shots,
            "estimate": est,
            "human": {
                "total": human_time(est["total_s"]),
                "generation": human_time(est["generation_s"]),
                "upscale": human_time(est["upscale_s"]) if est["upscale_s"] else "n/a",
            },
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.brief and not args.resume:
        print(json.dumps({"ok": False, "error": "--brief requis"}))
        return 1

    project = args.project or os.path.join(
        OUT_ROOT, "film_" + time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(project, exist_ok=True)
    cfg_path = os.path.join(project, "project.json")

    if args.resume and os.path.exists(cfg_path):
        with open(cfg_path) as f:
            saved = json.load(f)
        cfg, scenes = saved["cfg"], saved["scenes"]
        emit("resume", f"reprise du projet {project} ({len(scenes)} scenes)")
    else:
        cfg = {
            "brief": args.brief, "minutes": args.minutes, "style": args.style,
            "aspect": args.aspect, "resolution": args.resolution,
            "quality_mode": args.quality_mode, "n_scenes": n_scenes,
            "shots_per_scene": spc, "music": args.music,
            "music_prompt": args.music_prompt,
            "allow_text": args.allow_text or args.subtitles,
            "upscale": args.upscale,
        }
        emit("plan", f"{args.minutes} min -> {n_scenes} scenes x {spc} plans "
                     f"({total_shots} plans)")
        emit("estimate", f"~{human_time(est['total_s'])} de calcul estime")
        scenes = build_scene_briefs(args.brief, n_scenes, args.model or None)
        with open(cfg_path, "w") as f:
            json.dump({"cfg": cfg, "scenes": scenes, "estimate": est},
                      f, ensure_ascii=False, indent=2)

    t0 = time.time()
    paths = []
    for i, sc in enumerate(scenes, start=1):
        p = render_scene(sc, i, project, cfg)
        paths.append(p)
        el = time.time() - t0
        remain = (el / i) * (len(scenes) - i)
        emit("film_eta", f"{i}/{len(scenes)} scenes — reste ~{human_time(remain)}")

    out = args.out or os.path.join(project, "film.mp4")
    emit("concat", f"assemblage de {len(paths)} scenes")
    concat_scenes(paths, out)

    master = out
    if args.upscale:
        emit("upscale", f"montee en {args.upscale} (chaine de finition)")
        master = os.path.splitext(out)[0] + f"_{args.upscale}.mov"
        subprocess.run(
            [sys.executable, os.path.join(WORKSPACE, "python-services",
                                          "video_upscale_chain.py"),
             "--input", out, "--output", master, "--target", args.upscale,
             "--resume"],
            check=True,
        )

    result = {
        "ok": True, "project": project, "film": out, "master": master,
        "scenes": len(paths), "estimate": est,
        "elapsed_s": round(time.time() - t0, 1),
        "elapsed_human": human_time(time.time() - t0),
        "text_in_frame": bool(cfg["allow_text"]),
    }
    emit("done", f"film assemble en {result['elapsed_human']}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
