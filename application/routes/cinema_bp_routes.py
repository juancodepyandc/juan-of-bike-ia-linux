from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

cinema_bp = Blueprint('cinema_bp', __name__)

# =====================================================================
#  Cinema / Voice — module Cinema (videos multi-plans avec voix clonees)
# =====================================================================

CINEMA_DIR = pathlib.Path(WORKSPACE) / "python-services" / "cinema"
VOIX_OUTPUT_DIR = pathlib.Path(WORKSPACE) / "output" / "voix"
VOIX_ECHANTILLONS_DIR = VOIX_OUTPUT_DIR / "echantillons"
VOIX_PROFILS_DIR = VOIX_OUTPUT_DIR / "profils"
VOIX_GENERATIONS_DIR = VOIX_OUTPUT_DIR / "generations"
VOIX_CHANSONS_DIR = VOIX_OUTPUT_DIR / "chansons"
VOIX_MUSIQUES_DIR = VOIX_OUTPUT_DIR / "musiques"
VOIX_SESSIONS_DIR = VOIX_OUTPUT_DIR / "sessions"
LEGACY_LIBRARY_DIR = pathlib.Path(WORKSPACE) / "voices" / "library"
LEGACY_DROPBOX_DIR = pathlib.Path(WORKSPACE) / "voices" / "echantillons"

for _vd in (VOIX_OUTPUT_DIR, VOIX_ECHANTILLONS_DIR, VOIX_PROFILS_DIR, VOIX_GENERATIONS_DIR, VOIX_CHANSONS_DIR, VOIX_MUSIQUES_DIR, VOIX_SESSIONS_DIR, LEGACY_LIBRARY_DIR, LEGACY_DROPBOX_DIR):
    _vd.mkdir(parents=True, exist_ok=True)

VOICES_LIBRARY = VOIX_PROFILS_DIR
CINEMA_TEMP = pathlib.Path(WORKSPACE) / "temp" / "cinema"
CINEMA_TEMP.mkdir(parents=True, exist_ok=True)
STORAGE__VIDEO_SERVICES_DIR = pathlib.Path(WORKSPACE) / "python-services" / "storage"
if str(STORAGE__VIDEO_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(STORAGE__VIDEO_SERVICES_DIR))
try:
    from aurora_storage import AuroraStorageManager, StorageError
    _storage_manager = AuroraStorageManager(workspace=WORKSPACE)
    _storage_import_error = ""
except Exception as _storage_exc:
    AuroraStorageManager = None
    StorageError = RuntimeError
    _storage_manager = None
    _storage_import_error = f"{type(_storage_exc).__name__}: {_storage_exc}"


def _run_cinema_script_sync(script_name: str, args: list[str], timeout: int = 300) -> dict:
    """Run a cinema/* script synchronously and parse the last JSON line of stdout."""
    script = CINEMA_DIR / script_name
    if not script.exists():
        return {"ok": False, "error": f"script absent: {script}"}
    run_env = _build_python_env()
    try:
        result = subprocess.run(
            [sys.executable, "-W", "ignore", str(script)] + [str(a) for a in args],
            capture_output=True, timeout=timeout, cwd=WORKSPACE, env=run_env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout}s sur {script_name}"}
    except Exception as exc:
        return {"ok": False, "error": f"spawn {script_name}: {exc}"}

    out = result.stdout.decode("utf-8", errors="replace")
    err = _clean_stderr(result.stderr.decode("utf-8", errors="replace"))
    last_line = ""
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            last_line = line
            break
    if not last_line:
        return {"ok": False, "error": err or "pas de JSON dans la sortie", "raw": out[-400:]}
    try:
        parsed = json.loads(last_line)
    except Exception as exc:
        return {"ok": False, "error": f"JSON invalide: {exc}", "raw": last_line[:400]}
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "sortie JSON non-objet", "raw": last_line[:400]}
    if result.returncode != 0 and "error" not in parsed:
        parsed.setdefault("error", err or f"exit {result.returncode}")
        parsed.setdefault("ok", False)
    return parsed


# ---------------------------------------------------------------------------
# Storyboard generation via Ollama
# ---------------------------------------------------------------------------

STORYBOARD_PROMPT = """Tu es un story-boarder de cinema. A partir du prompt utilisateur, tu produis UNIQUEMENT un objet JSON valide (pas de prose, pas de markdown).

Si la requete est trop ambigue pour decider du sujet de base, reponds UNIQUEMENT:
{"clarification": "<une question courte dans la langue de l'utilisateur>"}

Sinon reponds UNIQUEMENT avec ce schema:
{
  "title": "<titre court>",
  "summary": "<2-3 phrases: theme + ce qui va se passer>",
  "style": "<cartoon_pixar | anime | manga | realistic | documentary | watercolor | noir>",
  "aspect": "<16:9 | 9:16 | 1:1 | 4:3>",
  "resolution": "<720p | 1080p | 1440p>",
  "characters": [
    {
      "name": "<nom>",
      "voice_slug": "<snake_case>",
      "voice_lang": "<fr|en>",
      "voice_preset": "<young_male_french | older_male_french | young_female_french | older_female_french | child_french | young_male_english | older_male_english | young_female_english>",
      "voice_policy": "<registered | style>",
      "public_figure": false,
      "description": "<apparence courte en anglais pour le modele de diffusion>"
    }
  ],
  "shots": [
    {
      "id": 1,
      "scene": "<description visuelle detaillee EN ANGLAIS pour le modele de diffusion>",
      "location": "<identifiant snake_case stable du lieu, ex: garage_interior>",
      "speaker": "<nom de personnage ou null>",
      "dialogue": "<dialogue exact dans la langue de l'utilisateur, ou chaine vide>",
      "duration_s": 4,
      "camera": "<wide | medium | close-up>",
      "needs_lipsync": true,
      "action_contract": "<une phrase EN ANGLAIS: mouvement visible + objet manipule + resultat attendu dans ce plan>",
      "negative_prompt": "<EN ANGLAIS, choses A EVITER pour ce shot specifiquement: deformed face, extra limbs, multiple subjects when only one is wanted, watermark, low quality, blurry, anachronistic objects>"
    }
  ],
  "music": {"enabled": false, "prompt": ""},
  "subtitles": {"enabled": false}
}

Regles strictes:
- Chaque plan dure 3 a 8 secondes. Le moteur segmente automatiquement les
  plans longs en interne (jusqu'a ~20 s par plan), donc un plan de 5-8 s est
  autorise quand l'action ou le dialogue l'exige.
- DUREE ET DIALOGUE (critique) : si un plan a un dialogue, "duration_s" DOIT
  couvrir le temps de parole. Compte environ 2.5 mots par seconde :
  10 mots -> 4 s minimum, 15 mots -> 6 s, 20 mots -> 8 s. Si le dialogue
  depasse 8 s de parole, coupe-le en deux plans consecutifs du meme speaker.
- Si la duree totale n'est pas precisee, choisis 10 a 30 secondes.
- Si l'utilisateur demande une video longue ou complexe, cree 8 a 12 plans
  de 3 a 6 secondes avec une progression narrative claire.
- "location" DOIT etre fourni pour CHAQUE shot : un identifiant snake_case
  stable du decor (ex: "garage_interior", "city_street_night"). REUTILISE
  exactement le meme identifiant quand deux plans se passent au meme endroit
  — le moteur s'en sert pour garder le decor identique entre plans (ancre
  visuelle). Change d'identifiant seulement quand le lieu change vraiment.
- "scene" DOIT etre en anglais (modele de diffusion).
- "dialogue" DOIT etre dans la langue de l'utilisateur.
- "voice_slug" est un identifiant snake_case stable (utilise pour retrouver une voix dans la bibliotheque).
- Par defaut, une video avec personnages DOIT utiliser du dialogue diegetique
  entre personnages. N'utilise un narrateur / voice-over que si l'utilisateur
  le demande explicitement ("narrateur", "voix off", "documentaire", "explique").
- Si un personnage parle face camera ou dans le champ, "speaker" DOIT etre son
  nom exact, "dialogue" non vide, "needs_lipsync" true, et "scene" DOIT montrer
  clairement son visage et sa bouche. Si la bouche n'est pas visible, ne le fais
  pas parler dans ce plan.
- Pour une celebrite/personne publique reelle, NE demande PAS de clonage exact
  implicite. Mets "voice_policy":"style", "public_figure":true, un voice_slug
  commencant par "style_", et choisis un "voice_preset" coherent (age/genre/langue).
  Une voix exacte n'est utilisee que si elle est deja enregistree explicitement
  dans la bibliotheque voix.
- Pour un personnage invente, choisis un voice_slug stable et un voice_preset
  coherent; garde la meme voix sur tous les plans.
- "needs_lipsync" est true uniquement si le personnage parle a l'ecran ET que la bouche est visible.
- "action_contract" DOIT etre fourni pour CHAQUE shot. Il decrit l'action
  observable du plan: sujet -> mouvement -> objet/effet visible. N'invente pas
  de cablage, ecriture, dessin, outil ou manipulation non demande par l'action.
- "negative_prompt" DOIT etre fourni pour CHAQUE shot. C'est en anglais.
  Default conservateur si rien de specifique : "deformed, blurry, low quality,
  watermark, extra limbs, distorted face, bad anatomy, ugly, poorly drawn".
  Adapte selon le shot : si plan large (wide), evite "close-up artifacts" ;
  si action rapide (leap, run), evite "motion blur, smeared".
- Sortie: UNIQUEMENT le JSON, rien d'autre, pas de balise ```json.

CONTINUITE PERSONNAGE (critique) :
- Le champ "scene" DOIT inclure mot-pour-mot la description de CHAQUE
  personnage VISIBLE dans le plan (pas seulement le speaker), telle qu'elle
  apparait dans characters[].description. Un personnage present mais non
  decrit change d'apparence a chaque plan (teste : le petit-fils devenait
  une femme puis un enfant cartoon).
  Exemple : si characters = [{"name":"Shadow","description":"a sleek black cat with amber eyes"}]
  et un shot a speaker="Shadow", alors scene DOIT contenir "a sleek black cat with amber eyes"
  (en plus de l'action specifique du shot).
  Raison : Wan2.2 a besoin de la description complete du personnage dans CHAQUE prompt
  pour preserver l'apparence shot-to-shot. Sans ca, le visage / la couleur / les yeux
  changent entre plans = rupture de continuite.

COHERENCE ACTION :
- Les shots forment une sequence narrative continue. Chaque scene doit decrire
  l'instant present (pas le passe ni le futur), avec une action verbe-actif claire
  ("the cat leaps", pas "the cat will leap" ni "after leaping").
- Pas de coupes temporelles brutales sauf si volontaires (l'utilisateur le precise).

GRAMMAIRE CINEMA (v84, critique pour la qualite Wan2.2) :
- Chaque "scene" DOIT contenir, en anglais : (a) UN mouvement de camera explicite
  ("slow dolly in", "static locked shot", "smooth pan left", "camera slowly
  orbiting", "handheld follow") coherent avec l'action ; (b) la lumiere/ambiance
  ("golden hour light", "soft overcast light", "neon night", "warm interior
  light") coherente d'un shot a l'autre ; (c) 1-2 descripteurs de matiere/detail
  ("detailed fur", "wet asphalt reflections").
- Si l'utilisateur demande explicitement un mouvement de camera, un type de plan,
  une lumiere ou un style (indices "cinematography" ci-dessous), chaque shot
  concerne DOIT le respecter mot pour mot — c'est non negociable.
- Varier les valeurs de plan entre shots (wide / medium / close-up) sauf demande
  contraire, pour un montage lisible.

Indices optionnels donnes par l'utilisateur (peut etre vide):
{HINTS}

Prompt utilisateur:
{PROMPT}
"""


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s


def _ollama_installed_models() -> list[str]:
    """Return the list of installed Ollama model names (best-effort)."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def _resolve_storyboard_model(requested: str | None) -> tuple[str, list[str]]:
    """Pick the best installed model for the storyboard task.

    Order:
      1. The model explicitly requested by the caller (if installed)
      2. orcarouter/Qwen3.8-27B-Uncensored — modele generaliste dense & multimodal
      3. qwen3.8:27b — variante standard Qwen 3.8
      4. qwen3-vl:30b — repli generaliste multimodal
      5. qwen3-coder:30b — repli installe, structure JSON solide
      6. qwen3-vl:8b — vision rapide

    Returns (chosen_model, candidates_tried). Empty chosen means none available.
    """
    installed = set(_ollama_installed_models())
    candidates: list[str] = []
    if requested:
        candidates.append(requested.strip())
    candidates.extend([
        "orcarouter/Qwen3.8-27B-Uncensored",
        "orcarouter/Qwen3.8-27B-Uncensored:latest",
        "qwen3.8:27b",
        "qwen3.6:27b",
        "qwen3-vl:30b",
        "qwen3-coder:30b",
        "qwen3-vl:8b",
    ])
    tried: list[str] = []
    for c in candidates:
        if not c:
            continue
        tried.append(c)
        if c in installed:
            return c, tried
        c_norm = c.lower().replace(":latest", "")
        for inst in installed:
            inst_norm = inst.lower().replace(":latest", "")
            if inst_norm == c_norm or inst_norm.endswith("/" + c_norm) or c_norm.endswith("/" + inst_norm):
                return inst, tried
            if inst.startswith(c.split(":")[0] + ":") and c.split(":", 1)[-1] in inst:
                return inst, tried
    return "", tried


@cinema_bp.route("/api/cinema/storyboard", methods=["POST"])
def cinema_storyboard():
    """Genere un storyboard JSON via Ollama."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt manquant"}), 400
    requested = (data.get("model") or "").strip()
    hints = data.get("hints") or {}

    model, tried = _resolve_storyboard_model(requested)
    if not model:
        return jsonify({
            "ok": False,
            "error": (
                "Aucun modele adapte au storyboard n'est installe. "
                "Installe orcarouter/Qwen3.8-27B-Uncensored ou fournis explicitement un modele."
            ),
            "tried": tried,
        }), 502

    full_prompt = STORYBOARD_PROMPT.replace("{HINTS}", json.dumps(hints, ensure_ascii=False)).replace("{PROMPT}", prompt)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_ctx": 8192},
                "keep_alive": "30m",
            },
            timeout=300,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Ollama injoignable: {exc}"}), 502

    if resp.status_code != 200:
        return jsonify({
            "ok": False,
            "error": f"Ollama HTTP {resp.status_code}: {resp.text[:240]}",
            "model": model,
            "tried": tried,
        }), 502

    try:
        text = resp.json().get("response", "")
    except Exception:
        text = resp.text or ""

    text = _strip_json_fence(text)

    try:
        payload = json.loads(text)
    except Exception:
        # Try to extract a JSON object from the text using brace matching
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            try:
                payload = json.loads(text[first : last + 1])
            except Exception as exc:
                return jsonify({"ok": False, "error": f"JSON invalide: {exc}", "raw": text[:600]}), 500
        else:
            return jsonify({"ok": False, "error": "pas de JSON dans la reponse Ollama", "raw": text[:600]}), 500

    if "clarification" in payload and payload.get("clarification"):
        return jsonify({"ok": True, "clarification": payload["clarification"]})

    # Validation minimale
    if not isinstance(payload.get("shots"), list) or not payload["shots"]:
        return jsonify({"ok": False, "error": "storyboard sans shots", "raw": payload, "model": model}), 500

    # v90 : normalisation déterministe — duration_s couvre la parole
    # (~2.5 mots/s), location héritée si absente. Le LLM sous-estime
    # systématiquement le temps de parole ; on ne dépend plus de lui.
    try:
        cinema_dir = str(CINEMA_DIR)
        if cinema_dir not in sys.path:
            sys.path.insert(0, cinema_dir)
        from storyboard_norm import normalize_storyboard
        payload = normalize_storyboard(payload)
    except Exception as _norm_exc:
        print(f"[cinema] storyboard normalize skip: {_norm_exc}", flush=True)

    return jsonify({"ok": True, "storyboard": payload, "model": model})


@cinema_bp.route("/api/academy/parcours/latest", methods=["GET"])
def academy_parcours_latest():
    """v82m5 : retourne le dernier parcours BAC généré côté serveur
    (via supervise_v2.py par exemple). Permet à l'UI Academy de charger
    une session déjà générée sans re-streamer."""
    p = pathlib.Path(WORKSPACE) / "temp" / "academy_parcours" / "latest.json"
    if not p.exists():
        return jsonify({"ok": False, "error": "no parcours generated yet"}), 404
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return jsonify({"ok": True, "parcours": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cinema_bp.route("/api/cinema/sample-render", methods=["POST"])
def cinema_sample_render():
    """v82lx : render JUST the first shot of a storyboard at low quality
    (balanced, 720p) en ~5-7 min au lieu de 30+ min. User valide la
    cohérence prompt/render avant de commit le full storyboard.

    Body : { storyboard: {...} }
    Retour : { ok, jobId, sampleId, mode: 'sample' }
    """
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400
    shots = storyboard.get("shots") or []
    if not shots:
        return jsonify({"ok": False, "error": "storyboard sans shots"}), 400

    # Narrow : 1 shot only + balanced quality + 720p forced.
    sample_storyboard = {
        **storyboard,
        "shots": [shots[0]],
        "quality_mode": "balanced",
        "resolution": "720p",
        "_sample_mode": True,
    }

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"sample_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    sb_path = job_dir / "storyboard.json"
    sb_path.write_text(json.dumps(sample_storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    output_mp4 = job_dir / "sample.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "cinema_pipeline.py introuvable"}), 500

    args = ["--storyboard", str(sb_path), "--output", str(output_mp4)]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema_sample",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
            "mode": "sample",
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "mode": "sample"})


@cinema_bp.route("/api/cinema/regenerate-shot", methods=["POST"])
def cinema_regenerate_shot():
    """v82lr : re-render UN SEUL shot d'un job existant avec un nouveau seed,
    puis re-concat le final.mp4. Évite de tout regénérer pour fixer un seul
    plan faible (économie 80%+ du temps).

    Body : {
      jobId: "<id du job précédent>",
      shotId: <int>,
      alterSeed?: <int — nouveau seed, default = old+1000>,
      modifiedScene?: "<override scene description for retry>"
    }
    Retour : { ok, newJobId } — async via _run_python_script.
    """
    data = request.get_json(silent=True) or {}
    job_id = data.get("jobId")
    shot_id = data.get("shotId")
    if not job_id or shot_id is None:
        return jsonify({"ok": False, "error": "jobId + shotId requis"}), 400

    # Look up the previous job dir to grab storyboard.
    prev_dir = CINEMA_TEMP / f"job_{job_id}"
    if not prev_dir.exists():
        return jsonify({"ok": False, "error": f"job {job_id} introuvable"}), 404
    sb_path = prev_dir / "storyboard.json"
    if not sb_path.exists():
        return jsonify({"ok": False, "error": "storyboard manquant"}), 404
    try:
        storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    except Exception as e:
        return jsonify({"ok": False, "error": f"storyboard parse fail: {e}"}), 500

    # Modify the requested shot : new seed + optional scene override.
    shots = storyboard.get("shots", [])
    target = None
    for s in shots:
        if int(s.get("id", 0)) == int(shot_id):
            target = s
            break
    if target is None:
        return jsonify({"ok": False, "error": f"shot {shot_id} pas dans storyboard"}), 404

    alter_seed = data.get("alterSeed")
    if alter_seed is None:
        prev_seed = target.get("seed") or (1000 + int(shot_id) * 31)
        alter_seed = int(prev_seed) + 1000
    target["seed"] = int(alter_seed)
    if data.get("modifiedScene"):
        target["scene"] = str(data["modifiedScene"])[:1000]

    # Spawn a fresh job for this single shot. We narrow the storyboard
    # to ONLY this shot so we don't waste time re-rendering all the others.
    # Note: characters are kept so FLUX keyframe is consistent.
    narrow_storyboard = {
        **storyboard,
        "shots": [target],
        "_regeneration_of": {"jobId": job_id, "shotId": shot_id},
    }

    new_job_id = _uuid.uuid4().hex[:16]
    new_dir = CINEMA_TEMP / f"job_{new_job_id}"
    new_dir.mkdir(parents=True, exist_ok=True)
    sb_new = new_dir / "storyboard.json"
    sb_new.write_text(json.dumps(narrow_storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    output_mp4 = new_dir / "final.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "cinema_pipeline.py introuvable"}), 500

    args = ["--storyboard", str(sb_new), "--output", str(output_mp4)]
    with _python_jobs_lock:
        _python_jobs[new_job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema_regenerate_shot",
            "outputPath": str(output_mp4),
            "jobDir": str(new_dir),
            "regenerationOf": {"jobId": job_id, "shotId": shot_id, "seed": alter_seed},
        }
    _queue_video_job(new_job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(new_job_id, str(script), args), daemon=True)
    t.start()

    return jsonify({
        "ok": True,
        "jobId": new_job_id,
        "shotId": shot_id,
        "seed": alter_seed,
        "outputPath": str(output_mp4),
    })


@cinema_bp.route("/api/cinema/selftest", methods=["POST"])
def cinema_selftest():
    """Queue a real, minimal end-to-end render instead of a file/port check."""
    _gc_old_jobs()
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"cinema_pipeline.py introuvable: {script}"}), 500

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"sample_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    storyboard = {
        "title": "Aurora video self-test",
        "summary": "Micro-rendu reel de validation de la chaine video.",
        "style": "cinematic",
        "aspect": "16:9",
        "resolution": "720p",
        "quality_mode": "auto",
        "max_quality_attempts": 1,
        "strict_quality_gate": False,
        "characters": [{
            "name": "Testeur",
            "description": (
                "an adult technician wearing a plain cobalt blue jacket, "
                "short dark hair, neutral friendly expression"
            ),
            "voice_lang": "fr",
            "voice_preset": "default_french",
        }],
        "shots": [{
            "id": 1,
            "scene": (
                "Medium shot of Testeur in a softly lit film studio, making "
                "one small natural hand gesture toward the camera. Testeur is "
                "an adult technician wearing a plain cobalt blue jacket, short "
                "dark hair, neutral friendly expression."
            ),
            "camera": "medium shot, locked camera",
            "location": "film studio",
            "duration_s": 2.0,
            "speaker": "Testeur",
            "dialogue": "Test réussi.",
            "needs_lipsync": False,
            "max_quality_attempts": 1,
        }],
        "music": {"enabled": False},
        "subtitles": {"enabled": False},
        "_selftest_mode": True,
    }
    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_mp4 = job_dir / "sample.mp4"
    args = ["--storyboard", str(storyboard_path), "--output", str(output_mp4)]

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "cinema_selftest",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
            "mode": "selftest",
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "stages": {"queue": {"ok": True, "ms": 0}},
        "overall_ok": False,
        "summary": "Micro-rendu reel mis en file (FLUX, video, voix, mux et ffprobe).",
    })


@cinema_bp.route("/api/cinema/benchmark", methods=["POST"])
def cinema_video_benchmark():
    """Queue a reproducible same-prompt/same-seed Wan-vs-LTX A/B campaign."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), dict) else {}
    shots = storyboard.get("shots") or []
    first_shot = shots[0] if shots and isinstance(shots[0], dict) else {}
    prompt = str(data.get("prompt") or first_shot.get("scene") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt ou storyboard avec un plan requis"}), 400

    spec = {
        "prompt": prompt,
        "negative_prompt": data.get("negative_prompt") or first_shot.get("negative_prompt"),
        "width": data.get("width") or 832,
        "height": data.get("height") or 480,
        "num_frames": data.get("num_frames") or 49,
        "seed": data.get("seed") if data.get("seed") is not None else first_shot.get("seed", 424242),
        "image": data.get("image") or "",
        "variants": data.get("variants") or ["wan5b", "ltx"],
        "style": data.get("style") or storyboard.get("style") or "cinematic",
        "character_description": data.get("character_description") or "",
        "action_contract": data.get("action_contract") or first_shot.get("action_contract") or prompt,
    }
    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"benchmark_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    spec_path = job_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    script = CINEMA_DIR / "video_ab_benchmark.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"harnais A/B introuvable: {script}"}), 500

    args = ["--spec", str(spec_path), "--output-dir", str(job_dir)]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "video_ab_benchmark",
            "jobDir": str(job_dir),
            "outputPath": str(job_dir / "report.json"),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "reportPath": str(job_dir / "report.json"),
        "variants": spec["variants"],
    })


@cinema_bp.route("/api/cinema/preview-keyframes", methods=["POST"])
def cinema_preview_keyframes():
    """Lance l'apercu FLUX en job file-backed pour survivre au tunnel."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"preview_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result_path = job_dir / "preview.json"
    script = CINEMA_DIR / "cinema_preview_keyframes.py"
    if not script.exists():
        return jsonify({
            "ok": False,
            "error": f"cinema_preview_keyframes.py introuvable: {script}",
        }), 500

    args = [
        "--storyboard", str(storyboard_path),
        "--work-dir", str(job_dir),
        "--output-json", str(result_path),
    ]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "cinema_preview_keyframes",
            "jobDir": str(job_dir),
            "outputPath": str(result_path),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "previewId": job_id,
        "status": "queued",
    })


@cinema_bp.route("/api/cinema/generate", methods=["POST"])
def cinema_generate():
    """Lance cinema_pipeline.py en async. Retourne {ok, jobId, output}.

    Le storyboard est ecrit dans temp/cinema/job_<id>/storyboard.json puis le
    pipeline genere temp/cinema/job_<id>/final.mp4.
    """
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        return jsonify({"ok": False, "error": "storyboard manquant"}), 400

    # v90.3 : normalisation aussi au lancement (idempotente) — couvre les
    # storyboards edites cote UI ou postes directement sans repasser par
    # /api/cinema/storyboard : durees couvrant la parole, location heritee,
    # descriptions personnages injectees, quality_mode par defaut "balanced".
    try:
        cinema_dir = str(CINEMA_DIR)
        if cinema_dir not in sys.path:
            sys.path.insert(0, cinema_dir)
        from storyboard_norm import normalize_storyboard
        storyboard = normalize_storyboard(storyboard)
    except Exception as _norm_exc:
        print(f"[cinema] generate normalize skip: {_norm_exc}", flush=True)

    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    storyboard_path = job_dir / "storyboard.json"
    storyboard_path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

    output_mp4 = job_dir / "final.mp4"
    script = CINEMA_DIR / "cinema_pipeline.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"cinema_pipeline.py introuvable: {script}"}), 500

    args = ["--storyboard", str(storyboard_path), "--output", str(output_mp4)]

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "cinema_pipeline.py",
            "kind": "cinema",
            "outputPath": str(output_mp4),
            "jobDir": str(job_dir),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "outputPath": str(output_mp4)})


# WS-V-P (2026-08-07) : point d'entrée unique du rendu vidéo mono-plan.
# Toute UI, CLI ou tunnel doit passer par ici et NON pas invoquer
# `video_generate.py` directement (Tauri contourne encore actuellement, cf.
# `PROMPT_REFONTE_MODULE_VIDEO §3.3` — chantier séparé). Le body accepte
# deux formes équivalentes :
#   1. { "intent": { "prompt": "...", "aspect": "16:9", "duration_s": 3, ... } }
#      → build_spec_from_intent() résout, on obtient un `VideoJobSpec`.
#   2. { "spec": { ... } } où spec est déjà une `VideoJobSpec` sérialisée
#      → chargée telle quelle (cas CLI `video_render --spec fichier.json`).
# La réponse contient `spec` résolue + `spec_hash` : le client peut afficher
# la spec avant lancement (équivalent HTTP de `--print-spec`).
@cinema_bp.route("/api/video/render", methods=["POST"])
def video_render():
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run"))
    # SERVICES_DIR n'existe pas comme constante nommée dans bridge_server —
    # on la reconstruit à partir de WORKSPACE (CINEMA_DIR.parent === le dossier
    # python-services).
    _video_services_dir = pathlib.Path(WORKSPACE) / "python-services"
    try:
        services_dir = str(_video_services_dir)
        if services_dir not in sys.path:
            sys.path.insert(0, services_dir)
        import video_job_spec as _vjs
        import video_spec_builder as _vsb
    except Exception as _imp_exc:
        return jsonify({
            "ok": False,
            "error": f"video_job_spec/video_spec_builder introuvable: {_imp_exc}",
        }), 500

    try:
        if "spec" in data and isinstance(data["spec"], dict):
            spec = _vjs.from_dict(data["spec"])
        elif "intent" in data and isinstance(data["intent"], dict):
            spec = _vsb.build_spec_from_intent(**data["intent"])
        else:
            return jsonify({
                "ok": False,
                "error": "body doit contenir 'intent' (dict) ou 'spec' (dict)",
            }), 400
    except (TypeError, ValueError) as _spec_exc:
        return jsonify({
            "ok": False,
            "error": f"spec invalide: {_spec_exc}",
        }), 400

    spec_dict = spec.to_dict()

    if dry_run:
        # --print-spec équivalent HTTP : on résout, on retourne, sans rendre.
        return jsonify({"ok": True, "spec": spec_dict, "dry_run": True})

    # Rendu réel : passe par le worker existant via --worker-config-json,
    # même contrat que le rendu direct interne. On écrit la spec dans le
    # jobDir pour audit et pour permettre la reprise en cas de crash.
    job_id = _uuid.uuid4().hex[:16]
    job_dir = CINEMA_TEMP / f"video_render_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    spec_path = job_dir / "spec.json"
    spec_path.write_text(spec.to_json(indent=2), encoding="utf-8")

    output_mp4 = str(job_dir / "final.mp4")
    thumbnail = str(job_dir / "final.thumb.png")

    # Convert spec → CLI args for video_generate.py (existing contract).
    args = [
        "--prompt", spec.prompt_composed,
        "--output", output_mp4,
        "--thumbnail", thumbnail,
        "--width", str(spec.width),
        "--height", str(spec.height),
        "--num_frames", str(spec.num_frames),
        "--quality_mode", spec.quality_mode,
        "--motion_interp", str(spec.motion_interp),
        "--force_strategy", spec.force_strategy,
        "--seed", str(spec.seed),
    ]
    if spec.image_path:
        args += ["--image", spec.image_path]
    if spec.negative_prompt:
        args += ["--negative_prompt", spec.negative_prompt]

    script = _video_services_dir / "video_generate.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"video_generate.py introuvable: {script}"}), 500

    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "video_generate.py",
            "kind": "video_render",
            "spec_hash": spec.spec_hash(),
            "specPath": str(spec_path),
            "outputPath": output_mp4,
            "jobDir": str(job_dir),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    )
    t.start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "outputPath": output_mp4,
        "specPath": str(spec_path),
        "specHash": spec.spec_hash(),
        "spec": spec_dict,
    })


def _parse_eta_from_progress(events: list[str]) -> dict | None:
    """Find the most recent PROGRESS:eta:<json> event and return its payload."""
    for line in reversed(events):
        if not isinstance(line, str):
            continue
        if line.startswith("PROGRESS:eta:"):
            try:
                return json.loads(line[len("PROGRESS:eta:"):])
            except Exception:
                continue
    return None


def _reload_lost_cinema_job(job_id: str) -> dict | None:
    """v82ly : reconstruit le state d'un cinema job depuis disk après bridge respawn.
    Le bridge en RAM perd _python_jobs au respawn. Cette fn :
      1. Cherche job_<id> ou sample_<id> dans CINEMA_TEMP
      2. Si dir existe, lit storyboard.json + cherche final.mp4/sample.mp4
      3. Status :
         - 'done' si output mp4 existe et size > 1KB → result reconstruit
         - 'running' si dir + storyboard mais pas de mp4 (interrupted)
         - 'unknown' sinon
    """
    for prefix in ("job_", "sample_", "preview_", "benchmark_"):
        d = CINEMA_TEMP / f"{prefix}{job_id}"
        if not d.exists():
            continue
        # v82ly : priority 1 — read status.json if it exists (final state
        # was persisted to disk by _run_python_job).
        status_path = d / "status.json"
        if status_path.exists():
            try:
                state = json.loads(status_path.read_text(encoding="utf-8"))
                state["kind"] = "cinema_recovered_from_disk"
                state["jobDir"] = str(d)
                return state
            except Exception:
                pass
        # priority 2 — output mp4 exists.
        out_mp4 = None
        for candidate in ("final.mp4", "sample.mp4"):
            p = d / candidate
            if p.exists() and p.stat().st_size > 1024:
                out_mp4 = p
                break
        control_path = d / ("spec.json" if prefix == "benchmark_" else "storyboard.json")
        if not out_mp4 and control_path.exists():
            # v82lz : if the job was running file-backed (cinema), tail stdout.log
            # to give recent PROGRESS events.
            stdout_log = d / "stdout.log"
            recent_output = ""
            if stdout_log.exists():
                try:
                    txt = stdout_log.read_text(encoding="utf-8", errors="replace")
                    # Last 4KB only.
                    recent_output = txt[-4096:] if len(txt) > 4096 else txt
                except Exception:
                    pass
            return {
                "status": "running",
                "kind": "cinema_lost_after_respawn",
                "jobDir": str(d),
                "output": recent_output,
                "note": "Job lost when bridge respawned. Subprocess may still be running (file-backed).",
            }
        if out_mp4:
            # v90.2 : re-expose le result JSON depuis stdout.log pour que
            # cinema_job_status puisse le parser après un respawn du bridge
            # (sinon l'UI perd scores/grade d'un job pourtant terminé).
            tail_output = ""
            stdout_log = d / "stdout.log"
            if stdout_log.exists():
                try:
                    txt = stdout_log.read_text(encoding="utf-8", errors="replace")
                    tail_output = txt[-16384:] if len(txt) > 16384 else txt
                except Exception:
                    pass
            return {
                "status": "done",
                "kind": "cinema_recovered",
                "outputPath": str(out_mp4),
                "jobDir": str(d),
                "output": tail_output,
                "exitCode": 0,
            }
    return None


def _job_eta_from_disk(job_id: str) -> dict | None:
    """v90.1 : ETA lue depuis le stdout.log du job LUI-MÊME (file-backed).

    Avant, l'ETA venait de `_python_progress_events`, liste GLOBALE partagée
    entre tous les jobs : un job fraîchement lancé renvoyait l'ETA périmée du
    job précédent ("plan 4/4 ok" au démarrage). Par-job ou rien."""
    for prefix in ("job_", "sample_", "preview_", "benchmark_"):
        log = CINEMA_TEMP / f"{prefix}{job_id}" / "stdout.log"
        if log.exists():
            try:
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                return None
            return _parse_eta_from_progress(lines[-400:])
    return None


VIDEO_OUTPUT_DIR = os.path.join(WORKSPACE, "output", "video")
# `output/RESULTATS` n est pas un module canonique : les resultats de rendu
# video appartiennent au module video, sous un projet.
RESULTATS_DIR = os.path.join(WORKSPACE, "output", "video", "_resultats")


@cinema_bp.route("/api/cinema/films")
def cinema_films():
    """Bibliotheque des films livres dans application/output/video/<projet>/."""
    films = []
    seen_ids = set()
    dirs_to_scan = [VIDEO_OUTPUT_DIR]
    if os.path.isdir(RESULTATS_DIR) and os.path.realpath(RESULTATS_DIR) != os.path.realpath(VIDEO_OUTPUT_DIR):
        dirs_to_scan.append(RESULTATS_DIR)

    for scan_dir in dirs_to_scan:
        if not os.path.isdir(scan_dir):
            continue
        for nom in sorted(os.listdir(scan_dir), reverse=True):
            if nom in seen_ids or nom.startswith("."):
                continue
            dossier = os.path.join(scan_dir, nom)
            if not os.path.isdir(dossier):
                continue
            mp4 = os.path.join(dossier, "film.mp4")
            if not os.path.isfile(mp4):
                continue
            seen_ids.add(nom)
            rapport = {}
            chemin_rapport = os.path.join(dossier, "rapport.json")
            if os.path.isfile(chemin_rapport):
                try:
                    with open(chemin_rapport, encoding="utf-8") as f:
                        rapport = json.load(f)
                except Exception:
                    pass
            films.append({
                "id": nom,
                "module": nom.split("_", 1)[0],
                "titre": nom.split("_", 2)[-1].replace("-", " "),
                "video": f"/api/cinema/films/{nom}/video",
                "taille_mo": round(os.path.getsize(mp4) / 1e6, 1),
                "modifie": int(os.path.getmtime(mp4)),
                "plans_livres": rapport.get("plans_livres"),
                "plans_demandes": rapport.get("plans_demandes"),
                "moteur": rapport.get("moteur_video"),
                "note": rapport.get("quality_grade"),
                "avertissements": len(rapport.get("warnings") or []),
            })
    return jsonify({"ok": True, "films": films, "dossier": VIDEO_OUTPUT_DIR})


@cinema_bp.route("/api/cinema/films/<film_id>/video")
def cinema_film_video(film_id: str):
    """Sert le mp4 d'un film livre. `conditional` autorise le seek du lecteur."""
    if "/" in film_id or "\\" in film_id or film_id.startswith("."):
        abort(400)
    for base_dir in (VIDEO_OUTPUT_DIR, RESULTATS_DIR):
        if not os.path.isdir(base_dir):
            continue
        chemin = os.path.join(base_dir, film_id, "film.mp4")
        if os.path.isfile(os.path.realpath(chemin)) and os.path.realpath(chemin).startswith(os.path.realpath(base_dir)):
            return send_file(chemin, mimetype="video/mp4", conditional=True)
    abort(404)


@cinema_bp.route("/api/cinema/films/<film_id>/rapport")
def cinema_film_rapport(film_id: str):
    """Rapport chiffre du film : plans livres, mesures, voix, avertissements."""
    if "/" in film_id or "\\" in film_id or film_id.startswith("."):
        abort(400)
    for base_dir in (VIDEO_OUTPUT_DIR, RESULTATS_DIR):
        if not os.path.isdir(base_dir):
            continue
        chemin = os.path.join(base_dir, film_id, "rapport.json")
        if os.path.isfile(chemin) and os.path.realpath(chemin).startswith(os.path.realpath(base_dir)):
            with open(chemin, encoding="utf-8") as f:
                return jsonify(json.load(f))
    abort(404)


@cinema_bp.route("/api/cinema/job/<job_id>")
def cinema_job_status(job_id: str):
    """Status of a cinema job + parsed ETA from PROGRESS:eta:* events."""
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
    if job is None:
        # v82ly : fallback — try to reconstruct from disk after bridge respawn.
        job = _reload_lost_cinema_job(job_id)
        if job is None:
            return jsonify({"status": "unknown", "error": "job not found"}), 404

    # v90.1 : sources par-job uniquement (stdout.log disque, puis output RAM
    # du job) — jamais la liste globale, qui mélange les jobs.
    eta = _job_eta_from_disk(job_id)
    if eta is None and job.get("output"):
        eta = _parse_eta_from_progress(job["output"].splitlines()[-400:])

    payload = {"jobId": job_id, **job}
    if eta:
        payload["eta"] = eta

    # If done, also try to parse the final result line from job["output"]
    if job.get("status") == "done" and job.get("output"):
        for line in reversed(job["output"].splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload["result"] = json.loads(line)
                except Exception:
                    pass
                break
    if job.get("storage") is not None:
        result = payload.setdefault("result", {})
        result["storage"] = job["storage"]
        storage_warnings = job["storage"].get("warnings") or []
        if not job["storage"].get("ok"):
            storage_warnings = [
                *storage_warnings,
                {
                    "code": job["storage"].get("reason", "storage_warning"),
                    "message": job["storage"].get("error")
                    or "La sortie reste sur le stockage interne.",
                },
            ]
        if storage_warnings:
            result["warnings"] = [*(result.get("warnings") or []), *storage_warnings]

    return jsonify(payload)


@cinema_bp.route("/api/cinema/cancel/<job_id>", methods=["POST"])
def cinema_job_cancel(job_id: str):
    """Annule reellement le groupe de processus, pas seulement le polling UI."""
    return _cancel_video_job_response(job_id)


@cinema_bp.route("/api/video/queue", methods=["GET"])
def video_gpu_queue_status():
    """Expose la file GPU effective pour une UI honnete et les diagnostics."""
    snapshot = _video_gpu_queue.snapshot()
    return jsonify({
        "ok": True,
        "activeJobId": snapshot["active_job_id"],
        "pendingJobIds": snapshot["pending_job_ids"],
        "generation3dActive": _is_3d_generation_active(),
    })


def _storage_response(callable_fn):
    if _storage_manager is None:
        return jsonify({
            "ok": False,
            "reason": "storage_manager_unavailable",
            "error": _storage_import_error,
        }), 503
    try:
        result = callable_fn()
    except StorageError as exc:
        result = exc.payload
    except Exception as exc:
        result = {
            "ok": False,
            "reason": "storage_operation_failed",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }
    return jsonify(result), (200 if result.get("ok") else 409)


def _video_model_strategy() -> dict:
    """Load the reviewed strategy as runtime truth instead of duplicating labels."""
    strategy_path = pathlib.Path(WORKSPACE) / "config" / "video_model_strategy.json"
    try:
        strategy = json.loads(strategy_path.read_text(encoding="utf-8"))
        if not isinstance(strategy, dict) or not isinstance(strategy.get("active"), dict):
            raise ValueError("schema actif absent")
        return strategy
    except Exception as exc:
        return {
            "version": 0,
            "profile": "unknown",
            "active": {},
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }


@cinema_bp.route("/api/storage/status", methods=["GET"])
def storage_status():
    """Read-only truth view; a directory is not a cold tier unless mounted."""
    def status_with_strategy():
        result = _storage_manager.status()
        strategy = _video_model_strategy()
        model_state = {item.get("id"): item for item in result.get("models", [])}
        cosy_python = pathlib.Path.home() / ".local/share/auroraia/venvs/cosyvoice3/bin/python"
        cosy_repo = pathlib.Path.home() / ".local/share/auroraia/engines/CosyVoice"
        cosy_model = (
            _storage_manager.cold_root / "models" / "Fun-CosyVoice3-0.5B-2512"
            if result.get("key_mounted")
            else pathlib.Path.home() / ".local/share/auroraia/models/Fun-CosyVoice3-0.5B-2512"
        )
        strategy["runtime"] = {
            "generator_available": bool(
                model_state.get("wan2.2-ti2v-5b", {}).get("available")
            ),
            "voice_clone_ready": bool(
                cosy_python.is_file()
                and (cosy_repo / "cosyvoice").is_dir()
                and (cosy_model / "cosyvoice3.yaml").is_file()
            ),
            "voice_clone_model_path": str(cosy_model),
        }
        result["model_strategy"] = strategy
        return result

    return _storage_response(status_with_strategy)


@cinema_bp.route("/api/storage/tier", methods=["POST"])
def storage_tier():
    data = request.get_json(silent=True) or {}
    model_id = str(data.get("model_id") or "").strip()
    tier = str(data.get("tier") or "").strip()
    if not model_id or tier not in {"hot", "cold"}:
        return jsonify({"ok": False, "reason": "model_id_and_valid_tier_required"}), 400
    return _storage_response(lambda: _storage_manager.tier_model(model_id, tier))


@cinema_bp.route("/api/storage/stage", methods=["POST"])
def storage_stage():
    model_id = str((request.get_json(silent=True) or {}).get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    return _storage_response(lambda: _storage_manager.stage(model_id))


@cinema_bp.route("/api/storage/unstage", methods=["POST"])
def storage_unstage():
    model_id = str((request.get_json(silent=True) or {}).get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    return _storage_response(lambda: _storage_manager.unstage(model_id))


@cinema_bp.route("/api/storage/gc", methods=["POST"])
def storage_gc():
    data = request.get_json(silent=True) or {}
    dry_run = data.get("dry_run") is not False
    max_age = int(data.get("max_age_minutes") or 180)
    return _storage_response(lambda: _storage_manager.gc(
        dry_run=dry_run,
        max_age_minutes=max_age,
    ))


@cinema_bp.route("/api/storage/purge", methods=["POST"])
def storage_purge():
    data = request.get_json(silent=True) or {}
    model_id = str(data.get("model_id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "reason": "model_id_required"}), 400
    # A first call is always a recoverable dry-run. Deletion requires an
    # explicit confirmation in the request that names the resolved model.
    confirm = data.get("confirm") is True
    return _storage_response(lambda: _storage_manager.purge(model_id, dry_run=not confirm))


@cinema_bp.route("/api/video/gallery", methods=["GET"])
def video_gallery():
    """Persistent gallery across module reloads and bridge restarts."""
    roots = []
    if _storage_manager is not None and _storage_manager.cold_mounted():
        roots.append(("cold", _storage_manager.cold_root / "outputs" / "videos"))
    roots.append(("hot", pathlib.Path(WORKSPACE) / "output" / "videos"))
    files = []
    seen = set()

    def append_video(path: pathlib.Path, tier: str, asset_path: str):
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".webm", ".mov", ".mkv"}:
            return
        resolved = str(path.resolve(strict=False))
        if resolved in seen:
            return
        seen.add(resolved)
        stat = path.stat()
        files.append({
            "name": path.name,
            "path": str(path),
            "asset_url": f"/api/asset/{asset_path}",
            "tier": tier,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        })

    for tier, root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if tier == "cold":
                asset_path = f"aurora-models/outputs/videos/{quote(path.name)}"
            else:
                asset_path = "/".join(quote(part) for part in ("output", "videos", path.name))
            append_video(path, tier, asset_path)

    # Les jobs récents restent consultables avant migration/GC, y compris les
    # sorties du harnais A/B. Le chemin asset demeure strictement sous WORKSPACE.
    if CINEMA_TEMP.is_dir():
        for job_dir in CINEMA_TEMP.iterdir():
            if not job_dir.is_dir() or not job_dir.name.startswith(
                ("job_", "sample_", "benchmark_")
            ):
                continue
            for path in job_dir.glob("*.mp4"):
                asset_path = "/".join(
                    quote(part)
                    for part in ("temp", "cinema", job_dir.name, path.name)
                )
                append_video(path, "hot", asset_path)
    files.sort(key=lambda item: item["modified"], reverse=True)
    return jsonify({
        "ok": True,
        "key_mounted": bool(_storage_manager and _storage_manager.cold_mounted()),
        "files": files[:500],
    })


# ---------------------------------------------------------------------------
# Voice library + extract + register + synthesize
# ---------------------------------------------------------------------------

@cinema_bp.route("/api/voice/library", methods=["GET"])
def voice_library_list():
    """List all registered voices via voice_clone.py --list."""
    result = _run_cinema_script_sync("voice_clone.py", ["--list"], timeout=30)
    return jsonify(result), (200 if result.get("ok") else 500)


@cinema_bp.route("/api/voice/library/<slug>", methods=["DELETE"])
def voice_library_delete(slug: str):
    """Delete a voice from the global library."""
    safe = re.sub(r"[^a-z0-9_]+", "", slug.lower())
    if not safe or safe != slug.lower().replace("-", "_"):
        return jsonify({"ok": False, "error": "slug invalide"}), 400
    target = VOICES_LIBRARY / safe
    if not target.is_dir():
        return jsonify({"ok": False, "error": "voix introuvable"}), 404
    try:
        import shutil as _sh
        _sh.rmtree(target)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "slug": safe})


@cinema_bp.route("/api/voice/library/clear", methods=["POST"])
def voice_library_clear():
    """Vide toute la bibliotheque de voix (utilise pour le bouton 'vider cache')."""
    if not VOICES_LIBRARY.exists():
        return jsonify({"ok": True, "deleted": 0})
    deleted = 0
    import shutil as _sh
    for entry in VOICES_LIBRARY.iterdir():
        if entry.is_dir():
            try:
                _sh.rmtree(entry)
                deleted += 1
            except Exception:
                pass
    return jsonify({"ok": True, "deleted": deleted})


@cinema_bp.route("/api/voice/register", methods=["POST"])
def voice_register():
    """Register a voice from an uploaded WAV (file path OR base64 bytes)."""
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "").strip()
    lang = (data.get("lang") or "fr").strip()
    source = (data.get("source") or "").strip()
    transcript = (data.get("transcript") or "").strip()
    if not character:
        return jsonify({"ok": False, "error": "character manquant"}), 400

    ref_path: str | None = None

    # Mode A: file path on disk (Tauri or local browser)
    file_path = (data.get("filePath") or data.get("referencePath") or "").strip()
    if file_path and os.path.exists(file_path):
        ref_path = file_path

    # Mode B: base64-encoded WAV bytes (mobile / tunnel)
    b64 = data.get("wavBase64") or ""
    if not ref_path and b64:
        import base64 as _b64
        try:
            raw = _b64.b64decode(b64)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"base64 invalide: {exc}"}), 400
        slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
        upload_dir = pathlib.Path(WORKSPACE) / "temp" / "voice_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        target = upload_dir / f"{slug_safe}_{int(time.time())}.wav"
        target.write_bytes(raw)
        ref_path = str(target)

    if not ref_path:
        return jsonify({"ok": False, "error": "fournir filePath ou wavBase64"}), 400

    args = [
        "--register",
        "--character", character,
        "--reference", ref_path,
        "--lang", lang,
    ]
    if source:
        args.extend(["--source", source])
    if transcript:
        args.extend(["--transcript", transcript])

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "voice_clone.py introuvable"}), 500
    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "voice_register",
            "slug": re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_"),
        }
    _queue_video_job(job_id, str(script))
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), args),
        daemon=True,
    ).start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "slug": _python_jobs[job_id]["slug"],
    })


@cinema_bp.route("/api/voice/extract", methods=["POST"])
def voice_extract_async():
    """Run voice_extract.py async (YouTube search + Demucs + ECAPA + cluster)."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "imported").strip()
    query = (data.get("query") or "").strip()
    input_path = (data.get("inputPath") or "").strip()
    target_duration = float(data.get("targetDuration") or 20.0)
    min_confidence = float(data.get("minConfidence") or 0.55)
    max_videos = int(data.get("maxVideos") or 4)
    auto_register = bool(data.get("autoRegister", True))
    lang = (data.get("lang") or "fr").strip()
    transcript = (data.get("transcript") or "").strip()

    if not query and not input_path:
        return jsonify({"ok": False, "error": "fournir query ou inputPath"}), 400

    slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
    output_wav = VOICES_LIBRARY / slug_safe / "reference.wav"
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    args = [
        "--character", character,
        "--output", str(output_wav),
        "--target-duration", str(target_duration),
        "--min-confidence", str(min_confidence),
        "--max-videos", str(max_videos),
        "--lang", lang,
    ]
    if auto_register:
        args.append("--auto-register")
    if transcript:
        args.extend(["--transcript", transcript])
    if input_path:
        args.extend(["--input", input_path])
    elif query:
        args.extend(["--query", query])

    script = CINEMA_DIR / "voice_extract.py"
    if not script.exists():
        return jsonify({"ok": False, "error": f"voice_extract.py introuvable: {script}"}), 500

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "voice_extract.py",
            "kind": "voice_extract",
            "character": character,
            "slug": slug_safe,
            "outputPath": str(output_wav),
            "autoRegister": auto_register,
            "lang": lang,
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id, "outputPath": str(output_wav), "slug": slug_safe})


@cinema_bp.route("/api/voice/synthesize", methods=["POST"])
def voice_synthesize():
    """One-shot synthesis for UI preview. Async to survive tunnel timeout."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    character = (data.get("character") or "").strip()
    text = (data.get("text") or "").strip()
    lang = (data.get("lang") or "auto").strip()
    prompt_text = (data.get("promptText") or data.get("transcript") or "").strip()
    instruction = (data.get("instruction") or "").strip()
    if not character or not text:
        return jsonify({"ok": False, "error": "character et text requis"}), 400

    slug_safe = re.sub(r"[^a-z0-9_]+", "_", character.lower()).strip("_") or "imported"
    out_dir = pathlib.Path(WORKSPACE) / "temp" / "voice_preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / f"{slug_safe}_{int(time.time())}.wav"

    args = [
        "--synthesize",
        "--character", character,
        "--text", text,
        "--lang", lang,
        "--output", str(out_wav),
    ]
    if prompt_text:
        args.extend(["--prompt-text", prompt_text])
    if instruction:
        args.extend(["--instruction", instruction])

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "voice_clone.py introuvable"}), 500

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": "voice_clone.py",
            "kind": "voice_synthesize",
            "outputPath": str(out_wav),
        }
    _queue_video_job(job_id, str(script))
    t = threading.Thread(target=_run_python_job, args=(job_id, str(script), args), daemon=True)
    t.start()
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "outputPath": str(out_wav),
        "status": "queued",
        **({"warning": "sync_desactive_pour_respecter_la_file_gpu"} if data.get("sync") else {}),
    })


@cinema_bp.route("/api/voice/check", methods=["GET"])
def voice_clone_check():
    """Verify TTS engines + dependencies (proxy for voice_clone.py --check)."""
    result = _run_cinema_script_sync("voice_clone.py", ["--check"], timeout=60)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Studio de Réplication Vocale par échantillon (CLI, Tunnel, Web UI)
# ---------------------------------------------------------------------------

def _guess_audio_ext_and_bytes(b64_str: str) -> tuple[str, bytes]:
    """Extrait les octets et devine l'extension audio appropriée pour ffmpeg."""
    mime_type = ""
    clean_b64 = b64_str
    if "," in b64_str and ";base64" in b64_str:
        header, clean_b64 = b64_str.split(",", 1)
        mime_type = header.lower()

    raw_bytes = base64.b64decode(clean_b64)
    ext = ".wav"
    if "webm" in mime_type or raw_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        ext = ".webm"
    elif "ogg" in mime_type or raw_bytes.startswith(b"OggS"):
        ext = ".ogg"
    elif "mp4" in mime_type or "m4a" in mime_type or "aac" in mime_type or b"ftyp" in raw_bytes[:16]:
        ext = ".mp4"
    elif "mp3" in mime_type or raw_bytes.startswith(b"ID3") or raw_bytes.startswith(b"\xff\xfb") or raw_bytes.startswith(b"\xff\xf3"):
        ext = ".mp3"
    elif "flac" in mime_type or raw_bytes.startswith(b"fLaC"):
        ext = ".flac"
    elif raw_bytes.startswith(b"RIFF"):
        ext = ".wav"
    return ext, raw_bytes


@cinema_bp.route("/api/voice/studio/sample", methods=["POST"])
def voice_studio_upload_sample():
    """Reçoit un échantillon vocal (upload multipart, base64 ou raw binary), normalise et analyse."""
    try:
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_id = uuid.uuid4().hex[:8]
        sample_id = f"sample_{now_str}_{rand_id}"
        target_wav = VOIX_ECHANTILLONS_DIR / f"{sample_id}.wav"
        target_raw: pathlib.Path | None = None

        # Option 1: JSON avec base64 ou filePath
        data = request.get_json(silent=True) or {}
        b64 = data.get("wavBase64") or data.get("audioBase64") or data.get("audio") or data.get("base64") or ""
        file_path = data.get("filePath") or data.get("path") or ""

        if not b64 and request.form:
            b64 = request.form.get("wavBase64") or request.form.get("audioBase64") or request.form.get("audio") or ""
            if not file_path:
                file_path = request.form.get("filePath") or ""

        if b64:
            try:
                ext, raw_bytes = _guess_audio_ext_and_bytes(b64)
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                target_raw.write_bytes(raw_bytes)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"Décodage Base64 échoué: {exc}"}), 400
        elif file_path and os.path.exists(file_path):
            try:
                src = pathlib.Path(file_path)
                ext = src.suffix or ".wav"
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                shutil.copy2(file_path, target_raw)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"Impossible de copier le fichier source: {exc}"}), 400

        # Option 2: multipart/form-data ("audio" ou "file")
        if (not target_raw or not target_raw.exists()) and request.files:
            file = request.files.get("audio") or request.files.get("file")
            if file:
                orig_name = file.filename or "audio.webm"
                ext = pathlib.Path(orig_name).suffix or ".webm"
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw{ext}"
                file.save(str(target_raw))

        # Option 3: Raw body bytes si Content-Type commence par audio/
        if (not target_raw or not target_raw.exists() or target_raw.stat().st_size == 0):
            raw_body = request.get_data()
            if raw_body and len(raw_body) > 300:
                target_raw = VOIX_ECHANTILLONS_DIR / f"{sample_id}_raw.webm"
                target_raw.write_bytes(raw_body)

        if not target_raw or not target_raw.exists() or target_raw.stat().st_size < 300:
            return jsonify({"ok": False, "error": "Aucun flux audio valide reçu (upload vide ou trop court)"}), 400

        # Normalisation audio 16kHz mono PCM_S16LE via ffmpeg
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        proc = subprocess.run([
            ffmpeg, "-y", "-i", str(target_raw),
            "-vn", "-map_metadata", "-1",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-loglevel", "error", str(target_wav)
        ], capture_output=True, text=True, timeout=60)

        try:
            if target_raw and target_raw.exists():
                target_raw.unlink()
        except Exception:
            pass

        if proc.returncode != 0 or not target_wav.exists() or target_wav.stat().st_size < 500:
            return jsonify({
                "ok": False,
                "error": f"Échec de conversion audio: {proc.stderr.strip() or 'format audio non reconnu'}"
            }), 400

        # Analyse de la qualité de l'échantillon
        quality = {"ok": True, "quality_score": 0.85, "duration_s": 3.5}
        try:
            sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services" / "cinema"))
            import voice_clone
            quality = voice_clone.analyze_reference_audio(str(target_wav))
        except Exception as exc:
            quality["warning"] = str(exc)

        return jsonify({
            "ok": True,
            "sampleId": sample_id,
            "samplePath": str(target_wav),
            "audioUrl": f"/api/voice/studio/sample/{sample_id}/audio",
            "duration_s": quality.get("duration_s", 0.0),
            "quality": quality,
        })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur serveur studio vocal: {exc}"}), 500


@cinema_bp.route("/api/voice/studio/sample/<sample_id>/audio", methods=["GET"])
def voice_studio_stream_sample(sample_id: str):
    """Sert l'audio de l'échantillon pour réécoute avant validation."""
    try:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
        candidates = [
            VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
            VOIX_ECHANTILLONS_DIR / safe_id,
            VOIX_PROFILS_DIR / safe_id / "reference.wav",
            LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
        ]
        for c in candidates:
            if c.is_file():
                return send_file(str(c), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": f"Échantillon '{safe_id}' introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/replicate", methods=["POST"])
def voice_studio_replicate():
    """Génère la parole ou chanson avec la voix répliquée, avec option de sauvegarde permanente."""
    try:
        data = request.get_json(silent=True) or {}
        sample_id = (data.get("sampleId") or data.get("samplePath") or "").strip()
        profile_slug = (data.get("profileSlug") or "").strip()
        text = (data.get("text") or "").strip()
        name = (data.get("name") or "Voix Répliquée").strip()
        save_permanent = bool(data.get("savePermanent", True))
        lang = (data.get("lang") or "fr").strip()
        prompt_text = (data.get("promptText") or "").strip()
        instruction = (data.get("instruction") or "").strip()

        if not text:
            return jsonify({"ok": False, "error": "Texte ou paroles requis"}), 400

        # Résolution de la référence audio
        sample_file: pathlib.Path | None = None
        if sample_id:
            safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
            for c in [
                pathlib.Path(sample_id),
                VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
                VOIX_ECHANTILLONS_DIR / safe_id,
                VOIX_PROFILS_DIR / safe_id / "reference.wav",
                LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file and profile_slug:
            for c in [
                VOIX_PROFILS_DIR / profile_slug / "reference.wav",
                LEGACY_LIBRARY_DIR / profile_slug / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file or not sample_file.is_file():
            return jsonify({"ok": False, "error": "Échantillon audio source introuvable"}), 400

        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        result = studio_voix.replicate_voice(
            sample_path=sample_file,
            text=text,
            name=name,
            save_permanent=save_permanent,
            lang=lang,
            prompt_text=prompt_text,
            instruction=instruction,
        )
        if not result.get("ok"):
            return jsonify(result), 400

        wav_path = pathlib.Path(result["wav"])
        result["audioUrl"] = f"/api/voice/studio/generation/{wav_path.name}/audio"
        return jsonify(result)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur de réplication: {exc}"}), 500


@cinema_bp.route("/api/voice/studio/sing", methods=["POST"])
def voice_studio_sing():
    """Génère un chant vocal ou convertit un guide audio avec accompagnement musical optionnel."""
    try:
        data = request.get_json(silent=True) or {}
        sample_id = (data.get("sampleId") or data.get("samplePath") or "").strip()
        profile_slug = (data.get("profileSlug") or "").strip()
        lyrics = (data.get("lyrics") or data.get("text") or "").strip()
        guide_audio = (data.get("guideAudio") or data.get("guidePath") or "").strip()
        backing_music_id = (data.get("backingMusicId") or data.get("musicId") or "").strip()
        style = (data.get("style") or "Pop").strip()
        bpm = int(data.get("bpm") or 120)
        name = (data.get("name") or "Voix Chantée").strip()
        save_permanent = bool(data.get("savePermanent", True))
        lang = (data.get("lang") or "fr").strip()
        vocal_volume = float(data.get("vocalVolume") or 1.0)
        music_volume = float(data.get("musicVolume") or 0.55)

        # Résolution de la référence audio
        sample_file: pathlib.Path | None = None
        if sample_id:
            safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", sample_id)
            for c in [
                pathlib.Path(sample_id),
                VOIX_ECHANTILLONS_DIR / f"{safe_id}.wav",
                VOIX_ECHANTILLONS_DIR / safe_id,
                VOIX_PROFILS_DIR / safe_id / "reference.wav",
                LEGACY_LIBRARY_DIR / safe_id / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file and profile_slug:
            for c in [
                VOIX_PROFILS_DIR / profile_slug / "reference.wav",
                LEGACY_LIBRARY_DIR / profile_slug / "reference.wav",
            ]:
                if c.is_file():
                    sample_file = c
                    break

        if not sample_file or not sample_file.is_file():
            return jsonify({"ok": False, "error": "Échantillon audio source introuvable"}), 400

        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        result = studio_voix.replicate_singing(
            sample_path=sample_file,
            lyrics=lyrics,
            guide_audio=guide_audio or None,
            backing_music_id=backing_music_id,
            style=style,
            bpm=bpm,
            name=name,
            save_permanent=save_permanent,
            lang=lang,
            vocal_volume=vocal_volume,
            music_volume=music_volume,
        )
        if not result.get("ok"):
            return jsonify(result), 400

        wav_path = pathlib.Path(result["wav"])
        result["audioUrl"] = f"/api/voice/studio/generation/{wav_path.name}/audio"
        return jsonify(result)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Erreur de chant: {exc}"}), 500


@cinema_bp.route("/api/voice/studio/music/search", methods=["GET"])
def voice_studio_music_search():
    """Recherche des pistes musicales et accompagnements disponibles."""
    try:
        q = request.args.get("q", "").strip()
        limit = int(request.args.get("limit", 12))
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        tracks = studio_voix.search_instrumental_tracks(q, limit=limit)
        return jsonify({"ok": True, "tracks": tracks, "count": len(tracks)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/music/track/<track_name>/audio", methods=["GET"])
def voice_studio_stream_music(track_name: str):
    """Sert l'audio d'une piste instrumentale d'accompagnement."""
    try:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", track_name)
        target = VOIX_MUSIQUES_DIR / safe_name
        if not target.is_file():
            target = VOIX_MUSIQUES_DIR / f"{safe_name}.wav"
        if target.is_file():
            return send_file(str(target), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": "Piste musicale introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/emotion/detect", methods=["POST"])
def voice_studio_detect_emotion():
    """Analyse l'émotion et fournit des consignes de prosodie intelligentes sans hardcoding."""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        advice = studio_voix.auto_detect_emotion(text)
        return jsonify({"ok": True, **advice})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/calibrate", methods=["POST"])
def voice_studio_calibrate():
    """Calibre un ou tous les profils de voix avec Whisper pour une réplication parfaite."""
    try:
        data = request.get_json(silent=True) or {}
        slug = (data.get("slug") or "").strip()
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services" / "cinema"))
        import voice_clone
        if slug:
            res = voice_clone.calibrate_profile(slug)
        else:
            res = voice_clone.calibrate_all_library_profiles()
        return jsonify(res)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/generation/<gen_name>/audio", methods=["GET"])
def voice_studio_stream_generation(gen_name: str):
    """Sert l'audio généré par le studio de réplication (parole ou chanson)."""
    try:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", gen_name)
        candidates = [
            VOIX_GENERATIONS_DIR / safe_name,
            VOIX_GENERATIONS_DIR / f"{safe_name}.wav",
            VOIX_CHANSONS_DIR / safe_name,
            VOIX_CHANSONS_DIR / f"{safe_name}.wav",
            VOIX_SESSIONS_DIR / safe_name,
            VOIX_SESSIONS_DIR / f"{safe_name}.wav",
        ]
        for c in candidates:
            if c.is_file():
                return send_file(str(c), mimetype="audio/wav", as_attachment=False)
        return jsonify({"ok": False, "error": f"Génération '{safe_name}' introuvable"}), 404
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/tree", methods=["GET"])
def voice_studio_tree():
    """Renvoie l'arborescence et les statistiques complètes de application/output/voix/."""
    try:
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        summary = studio_voix.get_tree_summary()
        return jsonify(summary)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/profiles", methods=["GET"])
def voice_studio_profiles():
    """Liste tous les profils vocaux disponibles avec URL d'écoute."""
    try:
        sys.path.insert(0, str(pathlib.Path(WORKSPACE) / "python-services"))
        import studio_voix
        summary = studio_voix.get_tree_summary()
        profils = summary.get("profils", [])
        for p in profils:
            p["audioUrl"] = f"/api/voice/studio/sample/{p['slug']}/audio"
        return jsonify({"ok": True, "profils": profils, "count": len(profils)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/profile/<slug>", methods=["DELETE"])
def voice_studio_delete_profile(slug: str):
    """Supprime un profil vocal spécifique."""
    try:
        safe = re.sub(r"[^a-z0-9_]+", "", slug.lower())
        target = VOIX_PROFILS_DIR / safe
        if not target.is_dir():
            target = LEGACY_LIBRARY_DIR / safe
        if not target.is_dir():
            return jsonify({"ok": False, "error": "Profil introuvable"}), 404
        shutil.rmtree(target)
        return jsonify({"ok": True, "slug": safe})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@cinema_bp.route("/api/voice/studio/clean-legacy", methods=["POST"])
def voice_studio_clean_legacy():
    """Nettoie les dossiers de sortie obsolètes ou vides (ex: output/videos)."""
    try:
        cleaned = []
        legacy_candidates = [
            pathlib.Path(WORKSPACE) / "output" / "videos",
        ]
        for c in legacy_candidates:
            if c.is_dir() and not any(c.iterdir()):
                try:
                    c.rmdir()
                    cleaned.append(str(c))
                except Exception:
                    pass
        return jsonify({"ok": True, "cleaned": cleaned})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Music studio — local ACE-Step gateway
# ---------------------------------------------------------------------------

MUSIC_ENGINE_URL = os.environ.get("AURORA_MUSIC_URL", "http://127.0.0.1:8001").rstrip("/")
MUSIC_OUTPUT_DIR = pathlib.Path(WORKSPACE) / "output" / "music"
MUSIC_UPLOAD_DIR = pathlib.Path(WORKSPACE) / "temp" / "music_uploads"
MUSIC_MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MUSIC_MAX_TEXT_CHARS = 12000
_music_jobs: dict[str, dict] = {}
_music_jobs_lock = threading.Lock()


def _music_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("ACESTEP_API_KEY", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _music_engine_json(path: str, *, method: str = "GET", payload: dict | None = None,
                       timeout: int = 20) -> tuple[dict | None, str | None]:
    """Call the locally configured composer and unwrap its documented envelope."""
    try:
        response = requests.request(
            method,
            f"{MUSIC_ENGINE_URL}{path}",
            headers=_music_headers(),
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, f"service local indisponible: {type(exc).__name__}: {str(exc)[:180]}"
    try:
        body = response.json()
    except ValueError:
        return None, f"reponse non JSON du service (HTTP {response.status_code})"
    if not response.ok or body.get("code", 200) >= 400:
        return None, str(body.get("error") or f"HTTP {response.status_code}")[:300]
    return body, None


def _music_safe_slug(value: str, fallback: str = "piste") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return (cleaned or fallback)[:56]


def _music_number(value, default: int | float, low: int | float, high: int | float) -> int | float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < low or parsed > high:
        return default
    return int(parsed) if isinstance(default, int) else parsed


def _music_choose_model(models: list[dict], quality: str) -> str | None:
    names = [str(item.get("name") or "") for item in models if item.get("name")]
    default = next((str(item["name"]) for item in models if item.get("is_default")), None)
    if quality == "studio":
        preferred = (
            "acestep-v15-xl-sft",
            "acestep-v15-xl-turbo",
            "acestep-v15-sft",
            "acestep-v15-turbo",
        )
    else:
        preferred = ("acestep-v15-turbo", "acestep-v15-sft")
    return next((name for name in preferred if name in names), default or (names[0] if names else None))


def _music_status_payload() -> dict:
    health, health_error = _music_engine_json("/health")
    if health_error:
        return {
            "ok": True,
            "ready": False,
            "models": [],
            "output_count": len(list(MUSIC_OUTPUT_DIR.glob("*"))) if MUSIC_OUTPUT_DIR.is_dir() else 0,
            "error": health_error,
        }
    model_data, model_error = _music_engine_json("/v1/models")
    models = [] if model_error else list((model_data or {}).get("data", {}).get("models") or [])
    return {
        "ok": True,
        "ready": True,
        "service": (health or {}).get("data", {}).get("service"),
        "version": (health or {}).get("data", {}).get("version"),
        "models": models,
        "default_model": (model_data or {}).get("data", {}).get("default_model"),
        "output_count": len(list(MUSIC_OUTPUT_DIR.glob("*"))) if MUSIC_OUTPUT_DIR.is_dir() else 0,
        **({"error": model_error} if model_error else {}),
    }


def _music_result_audio_url(file_value: str) -> str | None:
    if not file_value:
        return None
    if file_value.startswith(("http://", "https://")):
        engine = urlparse(MUSIC_ENGINE_URL)
        candidate = urlparse(file_value)
        if candidate.netloc != engine.netloc:
            return None
        return file_value
    if file_value.startswith("/"):
        return f"{MUSIC_ENGINE_URL}{file_value}"
    return f"{MUSIC_ENGINE_URL}/v1/audio?path={quote(file_value, safe='')}"


def _music_store_result(job: dict, result: dict) -> tuple[str | None, str | None]:
    file_url = _music_result_audio_url(str(result.get("file") or ""))
    if not file_url:
        return None, "fichier audio absent dans le resultat"
    try:
        response = requests.get(file_url, headers={k: v for k, v in _music_headers().items() if k != "Content-Type"}, stream=True, timeout=90)
        response.raise_for_status()
        content_length = int(response.headers.get("content-length") or 0)
        if content_length > 150 * 1024 * 1024:
            return None, "sortie trop volumineuse"
        parsed_url = urlparse(file_url)
        source_path = parse_qs(parsed_url.query).get("path", [parsed_url.path])[0]
        suffix = pathlib.PurePosixPath(source_path).suffix.lower()
        if suffix not in {".wav", ".mp3", ".flac", ".opus", ".aac", ".m4a"}:
            suffix = ".mp3"
        MUSIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stem = _music_safe_slug(str(job.get("title") or "piste"))
        filename = f"{int(time.time())}_{job['id'][:8]}_{stem}{suffix}"
        target = MUSIC_OUTPUT_DIR / filename
        written = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                written += len(chunk)
                if written > 150 * 1024 * 1024:
                    handle.close()
                    target.unlink(missing_ok=True)
                    return None, "sortie trop volumineuse"
                handle.write(chunk)
        metadata = {
            "title": job.get("title"),
            "created_at": time.time(),
            "request": job.get("request"),
            "engine_result": result,
        }
        target.with_suffix(target.suffix + ".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return filename, None
    except requests.RequestException as exc:
        return None, f"telechargement de la sortie impossible: {type(exc).__name__}: {str(exc)[:180]}"
    except OSError as exc:
        return None, f"ecriture de la sortie impossible: {str(exc)[:180]}"


def _music_refresh_job(job_id: str) -> dict | None:
    with _music_jobs_lock:
        job = _music_jobs.get(job_id)
        if job is None:
            return None
        if job.get("status") in {"completed", "failed"}:
            return dict(job)
        engine_task_id = job.get("engine_task_id")
    body, error = _music_engine_json("/query_result", method="POST", payload={"task_id_list": [engine_task_id]}, timeout=20)
    if error:
        with _music_jobs_lock:
            live = _music_jobs.get(job_id)
            if live is not None:
                live["last_poll_error"] = error
                return dict(live)
        return None
    records = list((body or {}).get("data") or [])
    record = records[0] if records else {}
    state = int(record.get("status") or 0)
    with _music_jobs_lock:
        live = _music_jobs.get(job_id)
        if live is None:
            return None
        if state == 0:
            live["status"] = "running"
            return dict(live)
        if state == 2:
            live.update({
                "status": "failed",
                "error": str(record.get("error") or "la composition a echoue")[:400],
                "completed_at": time.time(),
            })
            return dict(live)
        raw_result = record.get("result")
        try:
            parsed_result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except (TypeError, ValueError):
            parsed_result = None
        result = parsed_result[0] if isinstance(parsed_result, list) and parsed_result else (parsed_result if isinstance(parsed_result, dict) else None)
        if not result:
            live.update({"status": "failed", "error": "resultat de composition vide", "completed_at": time.time()})
            return dict(live)
        filename, store_error = _music_store_result(dict(live), result)
        if store_error:
            live.update({"status": "failed", "error": store_error, "completed_at": time.time()})
        else:
            live.update({
                "status": "completed",
                "filename": filename,
                "audio_url": f"/api/music/exports/{quote(filename)}",
                "metadata": result,
                "completed_at": time.time(),
            })
        return dict(live)


def _music_public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key not in {"engine_task_id", "request"}}


@cinema_bp.route("/api/music/status", methods=["GET"])
def music_status():
    return jsonify(_music_status_payload())


@cinema_bp.route("/api/music/voices", methods=["GET"])
def music_voice_list():
    result = _run_cinema_script_sync("voice_clone.py", ["--list"], timeout=30)
    if not result.get("ok"):
        return jsonify({"ok": False, "voices": [], "error": result.get("error", "bibliotheque indisponible")}), 503
    voices = [
        {
            "slug": item.get("slug"),
            "name": item.get("character") or item.get("slug"),
            "lang": item.get("lang") or "auto",
            "duration_s": item.get("duration_s"),
            "quality_score": item.get("quality_score"),
        }
        for item in result.get("voices") or []
    ]
    return jsonify({"ok": True, "voices": voices})


@cinema_bp.route("/api/music/voices", methods=["POST"])
def music_voice_import():
    """Import a user-supplied reference only after an explicit ownership confirmation."""
    if (request.form.get("consent") or "").strip().lower() != "true":
        return jsonify({"ok": False, "error": "confirmation de droits requise"}), 400
    if request.content_length and request.content_length > MUSIC_MAX_UPLOAD_BYTES:
        return jsonify({"ok": False, "error": "echantillon limite a 30 Mo"}), 413
    audio = request.files.get("audio")
    if audio is None or not (audio.filename or "").strip():
        return jsonify({"ok": False, "error": "fichier audio requis"}), 400
    name = (request.form.get("name") or "").strip()[:80]
    if not name:
        return jsonify({"ok": False, "error": "nom de voix requis"}), 400
    language = (request.form.get("language") or "fr").strip().lower()[:10]
    if language not in {"fr", "en", "es", "de", "it", "ja", "ko", "zh", "auto"}:
        return jsonify({"ok": False, "error": "langue non prise en charge"}), 400
    suffix = pathlib.Path(audio.filename).suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm"}:
        return jsonify({"ok": False, "error": "format audio non pris en charge"}), 400
    slug = _music_safe_slug(name, "voix")
    MUSIC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{int(time.time())}_{_uuid.uuid4().hex[:8]}"
    source = MUSIC_UPLOAD_DIR / f"{slug}_{stamp}{suffix}"
    reference = MUSIC_UPLOAD_DIR / f"{slug}_{stamp}.wav"
    try:
        audio.save(source)
        if source.stat().st_size == 0 or source.stat().st_size > MUSIC_MAX_UPLOAD_BYTES:
            source.unlink(missing_ok=True)
            return jsonify({"ok": False, "error": "echantillon vide ou trop volumineux"}), 400
        convert = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(reference)],
            capture_output=True,
            timeout=90,
        )
        if convert.returncode != 0 or not reference.is_file():
            return jsonify({"ok": False, "error": "conversion audio impossible; verifie le fichier envoye"}), 422
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "ffmpeg est requis pour importer un echantillon"}), 503
    except (OSError, subprocess.TimeoutExpired) as exc:
        return jsonify({"ok": False, "error": f"preparation de l echantillon impossible: {str(exc)[:180]}"}), 422

    script = CINEMA_DIR / "voice_clone.py"
    if not script.exists():
        return jsonify({"ok": False, "error": "service de voix introuvable"}), 500
    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "queued",
            "startedAt": time.time(),
            "script": script.name,
            "kind": "music_voice_register",
            "slug": slug,
        }
    threading.Thread(
        target=_run_python_job,
        args=(job_id, str(script), [
            "--register", "--character", name, "--reference", str(reference),
            "--lang", language, "--source", "music_studio_user_confirmed",
        ]),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "jobId": job_id, "status": "queued", "slug": slug})


@cinema_bp.route("/api/music/jobs", methods=["POST"])
def music_create():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "").strip()[:MUSIC_MAX_TEXT_CHARS]
    lyrics = str(data.get("lyrics") or "").strip()[:MUSIC_MAX_TEXT_CHARS]
    mode = str(data.get("mode") or "instrumental").strip().lower()
    title = str(data.get("title") or "Piste sans titre").strip()[:100]
    if mode not in {"instrumental", "song"}:
        return jsonify({"ok": False, "error": "mode invalide"}), 400
    if not prompt:
        return jsonify({"ok": False, "error": "decris le morceau a composer"}), 400
    if mode == "song" and not lyrics:
        return jsonify({"ok": False, "error": "des paroles sont requises pour un morceau chante"}), 400
    duration = _music_number(data.get("duration"), 45, 10, 600)
    bpm = _music_number(data.get("bpm"), 120, 30, 300)
    quality = str(data.get("quality") or "studio").strip().lower()
    if quality not in {"preview", "studio"}:
        quality = "studio"
    language = str(data.get("language") or "fr").strip().lower()[:10]
    key_scale = str(data.get("key") or "").strip()[:32]
    time_signature = str(data.get("timeSignature") or "4").strip()
    if time_signature not in {"2", "3", "4", "6"}:
        time_signature = "4"
    voice_slug = _music_safe_slug(str(data.get("voiceSlug") or ""), "")
    reference_path = None
    if voice_slug:
        candidate = (VOICES_LIBRARY / voice_slug / "reference.wav").resolve()
        library_root = VOICES_LIBRARY.resolve()
        if not str(candidate).startswith(str(library_root) + os.sep) or not candidate.is_file():
            return jsonify({"ok": False, "error": "voix de reference introuvable"}), 404
        reference_path = str(candidate)

    engine = _music_status_payload()
    if not engine.get("ready"):
        return jsonify({"ok": False, "error": engine.get("error") or "service musical indisponible"}), 503
    model = _music_choose_model(list(engine.get("models") or []), quality)
    engine_prompt = prompt if mode == "song" else f"{prompt}, instrumental only, no vocals, no spoken words"
    payload = {
        "prompt": engine_prompt,
        "lyrics": lyrics if mode == "song" else "",
        "vocal_language": language,
        "audio_duration": duration,
        "bpm": bpm,
        "key_scale": key_scale,
        "time_signature": time_signature,
        "batch_size": 1,
        "thinking": quality == "studio",
        "use_format": mode == "song",
        "use_cot_caption": True,
        "use_cot_language": True,
        "inference_steps": 8,
        "task_type": "text2music",
    }
    if model:
        payload["model"] = model
    if model and "base" in model:
        payload["inference_steps"] = 50
    if reference_path:
        payload["reference_audio_path"] = reference_path
    seed = data.get("seed")
    if isinstance(seed, int) and seed >= 0:
        payload.update({"seed": seed, "use_random_seed": False})
    body, error = _music_engine_json("/release_task", method="POST", payload=payload, timeout=45)
    if error:
        return jsonify({"ok": False, "error": error}), 502
    engine_data = (body or {}).get("data") or {}
    engine_task_id = str(engine_data.get("task_id") or "")
    if not engine_task_id:
        return jsonify({"ok": False, "error": "le service n a pas retourne de tache"}), 502
    job_id = _uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "queued_at": time.time(),
        "queue_position": engine_data.get("queue_position"),
        "engine_task_id": engine_task_id,
        "title": title,
        "request": {"mode": mode, "prompt": prompt, "lyrics": lyrics, "duration": duration, "bpm": bpm, "voice": voice_slug or None, "model": model},
    }
    with _music_jobs_lock:
        _music_jobs[job_id] = job
    return jsonify({"ok": True, **_music_public_job(job)})


@cinema_bp.route("/api/music/jobs/<job_id>", methods=["GET"])
def music_job(job_id: str):
    job = _music_refresh_job(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "tache introuvable"}), 404
    return jsonify({"ok": True, **_music_public_job(job)})


@cinema_bp.route("/api/music/exports", methods=["GET"])
def music_exports():
    files = []
    if MUSIC_OUTPUT_DIR.is_dir():
        for path in MUSIC_OUTPUT_DIR.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".wav", ".mp3", ".flac", ".opus", ".aac", ".m4a"}:
                continue
            metadata = {}
            try:
                metadata = json.loads(path.with_suffix(path.suffix + ".json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            files.append({
                "filename": path.name,
                "url": f"/api/music/exports/{quote(path.name)}",
                "modified": path.stat().st_mtime,
                "metadata": metadata,
            })
    files.sort(key=lambda item: item["modified"], reverse=True)
    return jsonify({"ok": True, "files": files[:100]})


@cinema_bp.route("/api/music/exports/<path:filename>", methods=["GET"])
def music_export_file(filename: str):
    safe_name = pathlib.PurePosixPath(filename).name
    if safe_name != filename or not safe_name:
        abort(404)
    target = (MUSIC_OUTPUT_DIR / safe_name).resolve()
    if target.parent != MUSIC_OUTPUT_DIR.resolve() or not target.is_file():
        abort(404)
    return send_file(target, conditional=True)


