from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL
from bridge_server import COMFYUI_PATH, _find_comfyui_path, resolve_node_exe
from routes.python_prog_bp_routes import _emit_progress

python_bp = Blueprint('python_bp', __name__)

# =====================================================================
#  Python script execution
# =====================================================================

def _resolve_script_path(script_path: str) -> str:
    if not os.path.abspath(script_path).startswith(WORKSPACE):
        script_path = os.path.join(WORKSPACE, script_path.lstrip("/\\"))
    return script_path


def _build_python_env() -> dict:
    run_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    # Allocation CUDA fragmentee -> aide l'echelle OOM du paint PBR sur 16 Go.
    run_env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    try:
        from routes.cowork_ext_bp_routes import _pick_vision_model_or_default
        vision_model, _, _ = _pick_vision_model_or_default("qwen3-vl:8b")
        if vision_model:
            run_env.setdefault("AURORA_VISION_MODEL", vision_model)
    except Exception:
        run_env.setdefault("AURORA_VISION_MODEL", "qwen3-vl:8b")
    comfy_path = COMFYUI_PATH or _find_comfyui_path()
    if comfy_path:
        run_env["COMFYUI_DIR"] = comfy_path
    workspace_p = pathlib.Path(WORKSPACE)
    for candidate in (
        workspace_p.parent / "modele",
        workspace_p.parent / "models",
        workspace_p / "modele",
    ):
        if candidate.is_dir():
            run_env.setdefault("AURORA_MODELS", str(candidate))
            break

    # HuggingFace weights: sur Linux les poids reels (Hunyuan3D-2.x, FLUX, Wan...) vivent
    # dans le cache HF standard ~/.cache/huggingface. Or AURORA_MODELS=modele fait pointer
    # HF_HOME sur <modele>/huggingface qui est VIDE -> la generation 3D re-telechargeait ~30 Go
    # (ou echouait). On epingle HF_HOME sur le hub qui contient reellement des modeles.
    if "HF_HOME" not in run_env:
        def _hub_has_models(hub: pathlib.Path) -> bool:
            try:
                return hub.is_dir() and next(hub.glob("models--*"), None) is not None
            except Exception:
                return False
        def _hub_count(hub: pathlib.Path) -> int:
            try:
                return sum(1 for _ in hub.glob("models--*"))
            except Exception:
                return 0
        _am = run_env.get("AURORA_MODELS")
        _candidates = []
        if _am:
            _candidates.append(pathlib.Path(_am) / "huggingface")
        _candidates.append(pathlib.Path.home() / ".cache" / "huggingface")
        # DEUX caches HF = DEUX telechargements du meme modele. L'app (Tauri)
        # lance python sans HF_HOME et tombe donc sur ~/.cache/huggingface,
        # tandis que le bridge epinglait <modele>/huggingface: Hunyuan3D s'est
        # retrouve en double (38 Go pour rien). On prend le cache le PLUS
        # fourni, pour que les deux chemins convergent sur le meme.
        _candidates.sort(key=lambda p: _hub_count(p / "hub"), reverse=True)
        for _hf in _candidates:
            if _hub_has_models(_hf / "hub"):
                run_env["HF_HOME"] = str(_hf)
                run_env["HF_HUB_CACHE"] = str(_hf / "hub")
                run_env["HUGGINGFACE_HUB_CACHE"] = str(_hf / "hub")
                break
    # BUDGETS 3D UNIFIES (reposes 31/07 — une fusion d'une autre session les
    # avait fait sauter). Chemin UI reel (run-async) SANS budget = OOM deja
    # paye deux fois (python 23 Go). TEXTURE: 4K natif + agrandissement x2 EN
    # TUILES = 8K livre — seule voie physiquement possible sur 30 Go de RAM
    # (pages CUDA epinglees non-swappables, cgroup OOM mesure a 23,7 Go en 8K
    # natif). 16K natif = feuille de route GPU. Ce n'est pas un rabais cache:
    # c'est journalise et explique ici.
    run_env.setdefault("AURORA_MEM_MAX_GB", "29")
    run_env.setdefault("AURORA_MEM_SWAP_MAX_GB", "48")
    run_env.setdefault("AURORA_TRELLIS2_TEXTURE", "4096")
    run_env.setdefault("AURORA_TRELLIS2_16K", "1")
    run_env.setdefault("AURORA_LLM_4BIT", "1")
    run_env.setdefault("AURORA_PERFECTION_ESSAIS", "2")
    return run_env


def _clean_stderr(raw: str) -> str:
    return "\n".join(
        line for line in raw.splitlines()
        if not (("Warning" in line or "warnings.warn(" in line.strip())
                and "Error" not in line and "Traceback" not in line)
    ).strip()


# ---------------------------------------------------------------------------
# Async Python job runner — avoids Cloudflare 524 (100s tunnel timeout).
# The synchronous /api/python/run stayed open for up to 15 min, which is way
# above the tunnel deadline. We now spawn the subprocess in a worker thread
# and let the client poll /api/python/job/<id> every few seconds: each poll
# returns in ~10ms so the tunnel never times out.
# ---------------------------------------------------------------------------

_python_jobs: dict[str, dict] = {}
_python_jobs_lock = threading.Lock()
_python_job_processes: dict[str, subprocess.Popen] = {}
import uuid as _uuid

# File FIFO partagee par tous les gros travaux du module video. Elle vit hors
# de Flask pour rester testable sans demarrer le bridge ni toucher au GPU.
_video_queue_dir = pathlib.Path(WORKSPACE) / "python-services" / "cinema"
if str(_video_queue_dir) not in sys.path:
    sys.path.insert(0, str(_video_queue_dir))
try:
    from video_gpu_queue import VideoGpuQueue
    _video_gpu_queue = VideoGpuQueue()
except ImportError:
    # Le module video a ete retire (commit 7209251) mais l'import etait reste
    # OBLIGATOIRE ici: le pont ne pouvait plus DEMARRER, et seul le processus
    # lance avant ce commit survivait encore en memoire. Le premier redemarrage
    # aurait tout casse. File inerte: les rares chemins video degradent
    # proprement, tout le reste du pont fonctionne.
    class _FileVideoInerte:
        """Remplacante sans GPU: accepte tout, ne bloque jamais, ne retient rien."""
        def enqueue(self, job_id):                    return 0
        def cancel(self, job_id):                     return None
        def wait_until_idle(self, timeout=None):      return True
        def is_cancelled(self, job_id):               return False
        def snapshot(self, job_id=None):              return {}
        def acquire(self, *a, **k):                   return True
        def release(self, job_id):                    return None

    _video_gpu_queue = _FileVideoInerte()
    print("[pont] file GPU video absente (module retire) — chemins video inertes", flush=True)


def _is_video_gpu_job(script_path: str) -> bool:
    """Vrai pour les scripts du chemin de production qui peuvent charger le GPU."""
    script = pathlib.Path(str(script_path)).name.lower()
    return script in {
        "cinema_pipeline.py",
        "cinema_preview_keyframes.py",
        "video_ab_benchmark.py",
        "video_generate.py",
        "talking_head.py",
        "voice_clone.py",
        "voice_extract.py",
        "ltx_direct_render.py",
        "musetalk_runner.py",
        # v91 : la chaine de finition charge RealESRGAN sur le GPU — sans
        # cette entree elle demarrerait en parallele d'un rendu Wan et les
        # deux se percuteraient sur les 16 Go.
        "video_upscale_chain.py",
    }


def _queue_video_job(job_id: str, script_path: str) -> int | None:
    if not _is_video_gpu_job(script_path):
        return None
    position = _video_gpu_queue.enqueue(job_id)
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is not None and job.get("status") not in {"cancelled", "done"}:
            job["status"] = "queued"
            job["queuePosition"] = position
            job["queueReason"] = "gpu_video_serialization"
    return position


def _update_video_queue_wait(job_id: str, position: int, active_job_id: str | None) -> None:
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is None or job.get("status") == "cancelled":
            return
        job.update({
            "status": "queued",
            "queuePosition": position,
            "activeGpuJobId": active_job_id,
            "queueReason": "gpu_video_serialization",
        })


def _terminate_job_process(job_id: str, *, force: bool = False) -> bool:
    """Termine le groupe complet d'un job, y compris ses workers diffusers."""
    with _python_jobs_lock:
        proc = _python_job_processes.get(job_id)
    if proc is None or proc.poll() is not None:
        return False
    try:
        if os.name == "posix":
            import signal as _signal
            os.killpg(os.getpgid(proc.pid), _signal.SIGKILL if force else _signal.SIGTERM)
        elif force:
            proc.kill()
        else:
            proc.terminate()
        return True
    except ProcessLookupError:
        return False
    except Exception:
        try:
            proc.kill() if force else proc.terminate()
            return True
        except Exception:
            return False


def _persist_job_state(job_id: str, state: dict) -> None:
    """Ecrit un etat terminal file-backed quand le job est cinema."""
    try:
        for prefix in ("job_", "sample_", "preview_", "benchmark_"):
            d = pathlib.Path(WORKSPACE) / "temp" / "cinema" / f"{prefix}{job_id}"
            if d.exists():
                (d / "status.json").write_text(
                    json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                break
    except Exception:
        pass


def _finalize_cancelled_job(job_id: str, script_path: str, started_at: float) -> None:
    state = {
        "status": "cancelled",
        "output": "",
        "error": "Job annule par l'utilisateur.",
        "exitCode": -15,
        "script": os.path.basename(script_path),
        "startedAt": started_at,
        "finishedAt": time.time(),
        "cancelledAt": time.time(),
    }
    _persist_job_state(job_id, state)
    with _python_jobs_lock:
        previous = _python_jobs.get(job_id, {})
        _python_jobs[job_id] = {**previous, **state}


def _cancel_video_job_response(job_id: str):
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
        if job is None:
            return jsonify({"ok": False, "error": "job not found"}), 404
        # 31/07 (constate par Juan: « j'appuie sur arreter, ca continue »):
        # ce garde REFUSAIT d'annuler tout job non-video (409) — le bouton
        # d'arret 3D appelait dans le vide et le pipeline continuait. Un
        # arret demande vaut pour TOUT job Python; seul le nettoyage de file
        # GPU reste specifique a la video.
        _est_video_job = _is_video_gpu_job(str(job.get("script", "")))
        if job.get("status") in {"done", "cancelled"}:
            return jsonify({
                "ok": True,
                "jobId": job_id,
                "status": job.get("status"),
                "alreadyTerminal": True,
            })
        job.update({
            "status": "cancelled",
            "cancelRequested": True,
            "cancelledAt": time.time(),
            "error": "Job annule par l'utilisateur.",
        })
        state_for_disk = dict(job)

    queue_state = _video_gpu_queue.cancel(job_id) if _est_video_job else None
    signal_sent = _terminate_job_process(job_id)
    # les pipelines 3D ont des SOUS-PROCESSUS lourds (TRELLIS ~20 Go): le
    # groupe de processus recoit TERM puis, 5 s apres, KILL s'il survit.
    if not _est_video_job:
        def _coup_de_grace(jid=job_id):
            time.sleep(5)
            _terminate_job_process(jid, force=True)
        threading.Thread(target=_coup_de_grace, daemon=True).start()
    state_for_disk.update({
        "status": "cancelled",
        "cancelRequested": True,
        "cancelledAt": time.time(),
        "error": "Job annule par l'utilisateur.",
    })
    _persist_job_state(job_id, state_for_disk)
    return jsonify({
        "ok": True,
        "jobId": job_id,
        "status": "cancelled",
        "signalSent": signal_sent,
        "wasQueued": bool(queue_state and queue_state.get("queued")),
        "wasActive": bool(queue_state and queue_state.get("active")),
    })


def _cinema_bridge_timeout_seconds(args: list[str], default: int = 1800) -> int:
    try:
        if "--spec" in [str(arg) for arg in args]:
            return 8 * 3600
        storyboard_path = None
        for idx, arg in enumerate(args):
            if str(arg) == "--storyboard" and idx + 1 < len(args):
                storyboard_path = str(args[idx + 1])
                break
        if not storyboard_path:
            return default
        p = pathlib.Path(storyboard_path)
        if not p.exists():
            return default
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        shots = data.get("shots") or []
        shot_count = max(1, len(shots))
        total_duration = sum(float(s.get("duration_s", 3.0) or 3.0) for s in shots)
        per_shot = int(os.environ.get("AURORA_CINEMA_BRIDGE_PER_SHOT_TIMEOUT", "900"))
        base = int(os.environ.get("AURORA_CINEMA_BRIDGE_BASE_TIMEOUT", "900"))
        computed = base + (shot_count * per_shot) + int(total_duration * 20)
        return max(default, min(computed, 8 * 3600))
    except Exception:
        return default


def _video_scratch_reservation_gb(script_path: str, args: list[str]) -> float:
    """Conservative internal reservation for frames, audio and temporary MP4s."""
    name = os.path.basename(str(script_path))
    if name == "cinema_pipeline.py":
        try:
            index = [str(arg) for arg in args].index("--storyboard")
            data = json.loads(pathlib.Path(str(args[index + 1])).read_text(encoding="utf-8-sig"))
            shots = data.get("shots") or []
            duration = sum(float(shot.get("duration_s") or 3.0) for shot in shots)
            return max(2.0, min(40.0, len(shots) * 0.75 + duration * 0.08))
        except Exception:
            return 4.0
    if name == "cinema_preview_keyframes.py":
        return 1.0
    if name == "video_ab_benchmark.py":
        return 8.0
    if name in {"voice_clone.py", "voice_extract.py"}:
        return 0.5
    return 2.0


# GENERATION 3D EN COURS: pendant qu'aurora_3d_pipeline tourne, les requetes
# cowork qui font tourner un LLM Ollama RECHARGENT un modele en VRAM en pleine
# etape GPU (constate au gel du 24/07: cudaMalloc OOM d'ollama a 00:15 pendant
# FLUX, puis Xid 109 pendant les materiaux). On refuse ces requetes avec un
# 503 clair le temps de la generation.
_AURORA_3D_EN_COURS = threading.Event()


def _is_3d_generation_active() -> bool:
    """Detect bridge-managed and independently launched Claude/terminal jobs."""
    if _AURORA_3D_EN_COURS.is_set():
        return True
    try:
        for process in psutil.process_iter(["pid", "cmdline", "status"]):
            if process.info.get("pid") == os.getpid() or process.info.get("status") == psutil.STATUS_ZOMBIE:
                continue
            command = " ".join(process.info.get("cmdline") or [])
            if "aurora_3d_pipeline.py" in command:
                return True
    except Exception:
        pass
    return False


def _run_python_job(job_id: str, script_path: str, args: list[str]):
    run_env = _build_python_env()
    _est_3d = "aurora_3d_pipeline" in str(script_path)
    _est_video_gpu = _is_video_gpu_job(script_path)
    _video_slot_acquired = False
    if _est_3d:
        # 31/07 (audit): la garde GPU etait unidirectionnelle — la video
        # attendait la 3D, mais un job 3D partait PENDANT un rendu Wan/FLUX
        # sur la meme carte (OOM assure). Symetrie: la 3D attend que la file
        # video soit vide, etat visible au poll.
        try:
            _t_attente = time.time()
            while not _video_gpu_queue.wait_until_idle(timeout=15):
                with _python_jobs_lock:
                    if job_id in _python_jobs:
                        _python_jobs[job_id]["step"] = "en attente: rendu video GPU en cours"
                if time.time() - _t_attente > 7200:
                    break
        except Exception:  # noqa: BLE001
            pass
        _AURORA_3D_EN_COURS.set()
    stdout_lines: list[str] = []
    # 31/07 (mesure: bridge a 24,6 Go, machine a 1 Go libre): la retention 4 h
    # des jobs gardait TOUT le stdout en RAM — les barres de progression
    # TRELLIS pesent des Go. On plafonne: 400 premieres lignes + 4000
    # dernieres (le JSON final vit a la fin), le milieu est resume.
    def _borner_stdout():
        if len(stdout_lines) > 4600:
            del stdout_lines[400:len(stdout_lines) - 4000]
            stdout_lines.insert(400, "[... sortie intermediaire tronquee par le bridge ...]")
    stderr_buf: list[str] = []
    exit_code = -1
    timed_out = False
    crashed: str | None = None

    python_exe = sys.executable or "python"
    start_ts = time.time()

    if _est_video_gpu:
        _queue_video_job(job_id, script_path)
        # Ne jamais lancer Wan/FLUX pendant une generation 3D partageant la
        # meme carte. Le job reste visible et annulable dans la file.
        while _is_3d_generation_active():
            if _video_gpu_queue.is_cancelled(job_id):
                _finalize_cancelled_job(job_id, script_path, start_ts)
                return
            with _python_jobs_lock:
                job = _python_jobs.get(job_id)
                if job is not None:
                    job.update({
                        "status": "queued",
                        "queueReason": "generation_3d_active",
                        "queuePosition": _video_gpu_queue.snapshot(job_id).get("position"),
                    })
            time.sleep(1.0)

        _video_slot_acquired = _video_gpu_queue.acquire(
            job_id,
            on_wait=lambda position, active: _update_video_queue_wait(
                job_id, position, active,
            ),
        )
        if not _video_slot_acquired:
            _finalize_cancelled_job(job_id, script_path, start_ts)
            return
        with _python_jobs_lock:
            job = _python_jobs.get(job_id)
            if job is not None:
                job.update({
                    "status": "running",
                    "queuePosition": 0,
                    "activeGpuJobId": job_id,
                    "queueReason": None,
                })

        manager = globals().get("_storage_manager")
        if manager is not None:
            reservation = _video_scratch_reservation_gb(script_path, args)
            try:
                capacity = manager.ensure_space("hot", reservation)
            except Exception as capacity_exc:
                capacity = {
                    "ok": False,
                    "reason": "storage_preflight_failed",
                    "error": str(capacity_exc)[:240],
                }
            if not capacity.get("ok"):
                _video_gpu_queue.release(job_id)
                refusal = {
                    "ok": False,
                    "error": (
                        f"Espace interne insuffisant pour reserver {reservation:.1f} Go "
                        f"sans franchir le plancher de {capacity.get('floor_gb', 20)} Go."
                    ),
                    "storage": capacity,
                }
                state = {
                    "status": "done",
                    "output": json.dumps(refusal, ensure_ascii=False),
                    "error": refusal["error"],
                    "exitCode": 1,
                    "script": os.path.basename(script_path),
                    "startedAt": start_ts,
                    "finishedAt": time.time(),
                    "storage": capacity,
                }
                _persist_job_state(job_id, state)
                with _python_jobs_lock:
                    previous = _python_jobs.get(job_id, {})
                    _python_jobs[job_id] = {**previous, **state}
                return

    # v82lz : pour les cinema jobs (long-running Wan2.2/FLUX), écrit
    # stdout/stderr directement dans des fichiers log dans le job_dir.
    # Le subprocess est ainsi DECOUPLE des pipes du bridge → si le bridge
    # respawn, le subprocess continue à écrire dans le fichier sans EPIPE.
    # Bridge thread tail le fichier pour les PROGRESS events.
    log_stdout_path = None
    log_stderr_path = None
    is_cinema_long_running = False
    try:
        for prefix in ("job_", "sample_", "preview_", "benchmark_"):
            for arg in args:
                if isinstance(arg, str) and prefix + job_id in arg:
                    is_cinema_long_running = True
                    job_dir_path = pathlib.Path(arg).parent
                    log_stdout_path = job_dir_path / "stdout.log"
                    log_stderr_path = job_dir_path / "stderr.log"
                    break
            if is_cinema_long_running:
                break
    except Exception:
        pass

    # 30/07 (audit): 1800 s tuait CHAQUE run TRELLIS max-precision lance
    # depuis l'UI (25-60 min/objet + porte de perfection) — l'echec etait
    # ensuite maquille en 'TRELLIS n a pas produit de mesh'. Un job 3D
    # obtient le meme plafond que /api/3d/run-pipeline.
    #
    # 2026-08-08 : le plafond mur-à-mur tuait aussi un film premium multi-plans
    # LEGITIMEMENT long (retries QA + FLUX keyframes + 3 shots premium). Cas
    # mesuré : job_828ffe68bf9a4a48, 3 shots × 3s, formule = 900 + 3×900 + 20×9
    # = 3780 s, tué en fin de plan 3 (2/3 déjà rendus) — le process crachait
    # encore des PROGRESS: à la mort, il n'était PAS bloqué. La discipline
    # correcte est donc "inactivité + plafond dur en filet". La ligne
    # `timeout_seconds` reste calculée comme filet ; deux autres seuils
    # gouvernent réellement la mort :
    #   - INACTIVITY : silence total (aucune ligne stdout) → probable gel
    #   - HARD CAP  : garde-fou catastrophe (job réellement runaway)
    # Configurable par env pour ne pas re-toucher le code au prochain film XXL.
    timeout_seconds = (_cinema_bridge_timeout_seconds(args) if is_cinema_long_running
                       else 14400 if _est_3d else 1800)
    inactivity_timeout_seconds = int(os.environ.get(
        "AURORA_BRIDGE_INACTIVITY_TIMEOUT",
        # 20 min : un shot Wan premium 60 étapes peut prendre 4-5 min ; un
        # FLUX2 keyframe 3-5 min ; un juge vision 30-90 s. 20 min sans
        # UN SEUL PROGRESS: ni ligne stdout = job vraiment gelé.
        str(20 * 60),
    ))
    hard_cap_seconds = int(os.environ.get(
        "AURORA_BRIDGE_HARD_CAP",
        # 24 h : catastrophe (un film 30 min à 4h/plan ferait 20 h) — au-delà,
        # on assume que quelque chose est fondamentalement cassé.
        str(24 * 3600),
    ))
    deadline = start_ts + max(timeout_seconds, hard_cap_seconds)  # legacy compat
    last_activity_ts = start_ts

    try:
        if is_cinema_long_running and log_stdout_path is not None:
            # Detached file-backed mode : subprocess writes to disk, not pipes.
            # On Windows, CREATE_NEW_PROCESS_GROUP allows survival across
            # parent restart. DETACHED_PROCESS would cut the parent link entirely.
            popen_kwargs = {
                "stdout": open(str(log_stdout_path), "w", encoding="utf-8", buffering=1),
                "stderr": open(str(log_stderr_path), "w", encoding="utf-8", buffering=1),
                "cwd": WORKSPACE,
                "env": run_env,
                "text": True,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # 31/07 (mesure: l'annulation d'un job 3D TUAIT LE BRIDGE):
                # sans session propre, le job partage le groupe de processus
                # du bridge — os.killpg fauchait tout le monde. Chaque job vit
                # desormais dans SON groupe: le kill ne touche que lui et ses
                # sous-processus (TRELLIS inclus).
                popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(
                [python_exe, "-W", "ignore", "-u", script_path] + [str(a) for a in args],
                **popen_kwargs,
            )
        else:
            popen_kwargs = {}
            # 31/07: TOUT job dans son propre groupe (pas seulement la video)
            # — un cancel par killpg fauchait le bridge entier sinon.
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True
            else:
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                [python_exe, "-W", "ignore", "-u", script_path] + [str(a) for a in args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=WORKSPACE,
                env=run_env,
                bufsize=1,
                text=False,
                **popen_kwargs,
            )
        with _python_jobs_lock:
            _python_job_processes[job_id] = proc
    except Exception as spawn_err:
        if _video_slot_acquired:
            _video_gpu_queue.release(job_id)
        with _python_jobs_lock:
            _python_jobs[job_id] = {
                "status": "done", "output": "", "error": f"Spawn echoue: {spawn_err}",
                "exitCode": -1, "finishedAt": time.time(),
            }
        return

    def _drain_stderr():
        if proc.stderr is None:
            return
        for raw_line in iter(proc.stderr.readline, b""):
            if not raw_line:
                break
            stderr_buf.append(raw_line.decode("utf-8", errors="replace").rstrip())

    stderr_thread = None
    if not is_cinema_long_running:
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

    try:
        if is_cinema_long_running and log_stdout_path is not None:
            # v82lz : tail the log file while subprocess runs. Lit ligne par
            # ligne avec polling 1s. Capture PROGRESS events pour le frontend.
            # 2026-08-08 : timeout par INACTIVITÉ + plafond dur — voir bloc
            # `inactivity_timeout_seconds` / `hard_cap_seconds` plus haut.
            log_pos = 0
            while True:
                if proc.poll() is not None:
                    break
                now = time.time()
                if now > start_ts + hard_cap_seconds:
                    timed_out = True
                    break
                if now - last_activity_ts > inactivity_timeout_seconds:
                    timed_out = True
                    break
                try:
                    if log_stdout_path.exists():
                        with open(log_stdout_path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(log_pos)
                            for line in f:
                                line = line.rstrip()
                                if line:
                                    stdout_lines.append(line); _borner_stdout(); _borner_stdout()
                                    if line.startswith("PROGRESS:"):
                                        _emit_progress(line, job_id=job_id)
                                    # Toute ligne stdout = job vivant.
                                    last_activity_ts = time.time()
                            log_pos = f.tell()
                except Exception:
                    pass
                time.sleep(1)
            # Final read to capture any trailing lines.
            try:
                if log_stdout_path.exists():
                    with open(log_stdout_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(log_pos)
                        for line in f:
                            line = line.rstrip()
                            if line:
                                stdout_lines.append(line)
                                if line.startswith("PROGRESS:"):
                                    _emit_progress(line, job_id=job_id)
            except Exception:
                pass
            # Read stderr file for errors.
            try:
                if log_stderr_path and log_stderr_path.exists():
                    stderr_buf.append(log_stderr_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
            exit_code = proc.wait(timeout=5) if not timed_out else -1
        elif proc.stdout is not None:
            for raw_line in iter(proc.stdout.readline, b""):
                if not raw_line:
                    break
                text = raw_line.decode("utf-8", errors="replace").rstrip()
                stdout_lines.append(text); _borner_stdout()
                if text.startswith("PROGRESS:"):
                    _emit_progress(text, job_id=job_id)
                # 2026-08-08 : chaque ligne stdout = job vivant. Mort par
                # inactivité seulement, plus par temps total mur-à-mur.
                last_activity_ts = time.time()
                now = time.time()
                if now > start_ts + hard_cap_seconds:
                    timed_out = True
                    break
                if now - last_activity_ts > inactivity_timeout_seconds:
                    timed_out = True
                    break
            # Après fermeture stdout : attendre la sortie process, plafonné à
            # l'inactivité restante (pas au wall-clock).
            remaining = max(1.0, (start_ts + hard_cap_seconds) - time.time())
            exit_code = proc.wait(timeout=remaining) if not timed_out else -1
        else:
            remaining = max(1.0, (start_ts + hard_cap_seconds) - time.time())
            exit_code = proc.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        timed_out = True
    except Exception as runtime_err:
        crashed = f"{type(runtime_err).__name__}: {runtime_err}"
    finally:
        if _est_3d:
            _AURORA_3D_EN_COURS.clear()
        was_cancelled = _video_gpu_queue.is_cancelled(job_id) if _est_video_gpu else False
        if proc.poll() is None:
            _terminate_job_process(job_id, force=not was_cancelled)
            try:
                proc.wait(timeout=5)
            except Exception:
                _terminate_job_process(job_id, force=True)
        if stderr_thread is not None:
            stderr_thread.join(timeout=2)
        with _python_jobs_lock:
            _python_job_processes.pop(job_id, None)
        if _video_slot_acquired:
            _video_gpu_queue.release(job_id)

    if was_cancelled:
        error_message = "Job annule par l'utilisateur."
    elif timed_out:
        # 2026-08-08 : deux modes distincts. Le job qui produit encore des
        # PROGRESS: n'était pas gelé — c'était le plafond wall-clock qui
        # tuait un rendu légitime. Maintenant on distingue.
        _now = time.time()
        if _now > start_ts + hard_cap_seconds:
            error_message = (
                f"Timeout dur ({int(hard_cap_seconds)}s = {int(hard_cap_seconds/3600)}h) "
                "atteint — le job dépasse le plafond de sécurité absolu. "
                "Aucun script légitime ne devrait durer ça ; investiguez."
            )
        else:
            silence = int(_now - last_activity_ts)
            error_message = (
                f"Timeout par inactivité ({silence}s sans stdout, seuil "
                f"{int(inactivity_timeout_seconds)}s = "
                f"{int(inactivity_timeout_seconds/60)}min). "
                "Le job est probablement gelé (pas de PROGRESS: depuis longtemps). "
                "Relance AURORA_BRIDGE_INACTIVITY_TIMEOUT plus haut si erreur de diagnostic."
            )
    elif crashed:
        error_message = crashed
    else:
        error_message = _clean_stderr("\n".join(stderr_buf))
    # TRADUCTION DES MORTS PAR SIGNAL (30/07, audit): un SIGKILL (OOM noyau ou
    # plafond cgroup) ne laisse AUCUN traceback — l'erreur remontait vide et
    # l'UI affichait un faux 'TRELLIS n a pas produit de mesh'. On nomme le
    # signal, et on joint le motif que la sentinelle ecrit expres pour ca.
    try:
        if isinstance(exit_code, int) and exit_code < 0 and not (error_message or "").strip():
            _sig = -exit_code
            error_message = ("processus tue par le signal %d%s" % (
                _sig, " (SIGKILL: memoire epuisee — noyau ou plafond cgroup)" if _sig == 9 else ""))
        _trace_p = os.environ.get("AURORA_SENTINEL_TRACE", "/tmp/aurora_sentinelle.txt")
        if (isinstance(exit_code, int) and exit_code != 0 and os.path.isfile(_trace_p)
                and os.path.getmtime(_trace_p) >= (start_ts or 0)):
            with open(_trace_p, "r", encoding="utf-8") as _tf:
                _motif = _tf.read().strip()[:300]
            if _motif:
                error_message = ((error_message + " — ") if error_message else "") + _motif
    except Exception:
        pass

    storage_result = None
    if (
        not was_cancelled
        and exit_code == 0
        and os.path.basename(script_path) == "cinema_pipeline.py"
    ):
        with _python_jobs_lock:
            output_path_for_storage = (_python_jobs.get(job_id) or {}).get("outputPath")
        manager = globals().get("_storage_manager")
        if output_path_for_storage and manager is not None:
            try:
                storage_result = manager.migrate_final_to_cold(
                    output_path_for_storage,
                    job_id=job_id,
                )
            except Exception as storage_exc:
                storage_result = {
                    "ok": False,
                    "reason": "output_migration_failed",
                    "error": str(storage_exc)[:240],
                }
        elif output_path_for_storage:
            storage_result = {
                "ok": False,
                "reason": "storage_manager_unavailable",
                "error": globals().get("_storage_import_error", ""),
            }

    # v82ly : persist final state to disk for survival across bridge respawn.
    final_state = {
        "status": "cancelled" if was_cancelled else "done",
        "output": "\n".join(stdout_lines),
        "error": error_message,
        "exitCode": -15 if was_cancelled else exit_code,
        "script": os.path.basename(script_path),
        "startedAt": start_ts,
        "finishedAt": time.time(),
    }
    if storage_result is not None:
        final_state["storage"] = storage_result
    if was_cancelled:
        final_state["cancelledAt"] = time.time()
    # Find the job dir (cinema convention) and write status.json.
    _persist_job_state(job_id, final_state)

    with _python_jobs_lock:
        previous = _python_jobs.get(job_id, {})
        _python_jobs[job_id] = {**previous, **{
            "status": "cancelled" if was_cancelled else "done",
            "output": "\n".join(stdout_lines),
            "error": error_message,
            "exitCode": -15 if was_cancelled else exit_code,
            "script": os.path.basename(script_path),
            "startedAt": start_ts,
            "finishedAt": time.time(),
            **({"storage": storage_result} if storage_result is not None else {}),
            **({"cancelledAt": time.time()} if was_cancelled else {}),
        }}


def _gc_old_jobs():
    """Remove finished jobs to bound memory.

    31/07 (audit): 10 min de retention faisait DISPARAITRE les jobs 3D
    termines — le client, en se reattachant apres un long TRELLIS, recevait
    404 et RELANCAIT un run identique a neuf. Les jobs 3D gardent leur etat
    terminal 4 h; les autres 30 min.
    """
    now = time.time()
    with _python_jobs_lock:
        stale = []
        for jid, job in _python_jobs.items():
            fin = job.get("finishedAt")
            if fin is None:
                continue
            _est3d_job = "aurora_3d_pipeline" in str(job.get("script") or job.get("scriptPath") or "")
            if now - fin > (14400 if _est3d_job else 1800):
                stale.append(jid)
        for jid in stale:
            _python_jobs.pop(jid, None)


@python_bp.route("/api/python/run-async", methods=["POST"])
def python_run_async():
    """Start a Python job in a worker thread and return a job_id.

    Use /api/python/job/<id> to poll for completion. This pattern is the only
    reliable way to run >100s Python scripts behind a Cloudflare tunnel."""
    _gc_old_jobs()
    data = request.get_json(silent=True) or {}
    script_path = _resolve_script_path(data.get("scriptPath", ""))
    args = data.get("args", []) or []

    # Reject unknown scripts with a proper JSON 404 so the frontend doesn't
    # interpret an HTML fallback page as "endpoint missing" and silently
    # downgrade to the sync /api/python/run path (which then times out at 524).
    if not os.path.isfile(script_path):
        return jsonify({
            "ok": False,
            "error": f"Script Python introuvable: {script_path}",
        }), 404

    job_id = _uuid.uuid4().hex[:16]
    with _python_jobs_lock:
        _python_jobs[job_id] = {
            "status": "running",
            "startedAt": time.time(),
            "script": os.path.basename(script_path),
        }
    _queue_video_job(job_id, script_path)
    t = threading.Thread(target=_run_python_job, args=(job_id, script_path, args), daemon=True)
    t.start()
    return jsonify({"ok": True, "jobId": job_id})


@python_bp.route("/api/ping", methods=["GET", "HEAD"])
def python_bridge_ping():
    """Ultra-light reachability probe — the frontend polls this every 30s to
    decide whether to light the 'Bridge' chip red or green, and the Forge
    overlay gates its Lancer button on it. Must stay tiny (no locks, no I/O)
    so it survives even when the bridge is busy running a long Python job."""
    return jsonify({"ok": True, "service": "aurora-bridge", "t": int(time.time())})


@python_bp.route("/api/health")
def python_bridge_health():
    """Lightweight health check used by the frontend to detect whether the bridge
    (and thus the async Python runner) is reachable before kicking off a long job."""
    with _python_jobs_lock:
        running = sum(1 for j in _python_jobs.values() if j.get("status") == "running")
        finished = sum(1 for j in _python_jobs.values() if j.get("status") == "done")
    return jsonify({
        "ok": True,
        "service": "aurora-bridge",
        "workspace": WORKSPACE,
        "pythonJobs": {"running": running, "finished": finished},
        "features": {
            "runAsync": True,
            "progressStream": True,
        },
    })


# ---------------------------------------------------------------------------
# Banc de conformite inter-modules, rejouable DEPUIS LE TUNNEL.
#
# Les corrections de modules s'accompagnent de mesures comportementales (le
# projet ne conserve plus de fichiers de tests). Cet endpoint les rejoue et
# rend le resultat en JSON, pour que l'interface (donc le tunnel) puisse le
# declencher sans passer par un terminal.
#
# LECTURE SEULE, deliberement : il n'execute que des mesures sur le code en
# place, aucun fichier n'est touche, aucune suite de tests n'est lancee.
# ---------------------------------------------------------------------------
_conformance_lock = threading.Lock()


@python_bp.route("/api/conformance", methods=["GET", "POST"])
def aurora_conformance():
    """Rejoue les mesures comportementales (lecture seule) et rend le rapport JSON.

    Parametres (query ou corps JSON) :
      mesures=1   calcule les mesures comportementales chiffrees par module
    """
    params = request.get_json(silent=True) or {}

    def flag(nom, defaut=False):
        brut = request.args.get(nom)
        if brut is None:
            brut = params.get(nom)
        if brut is None:
            return defaut
        return str(brut).strip().lower() in ("1", "true", "yes", "oui")

    if not _conformance_lock.acquire(blocking=False):
        return jsonify({
            "ok": False,
            "error": "Un banc de conformite est deja en cours.",
        }), 409

    try:
        node_exe = resolve_node_exe()
        if not node_exe:
            return jsonify({"ok": False, "error": "Node introuvable sur ce poste."}), 500
        args = [node_exe, "scripts/conformance.mjs", "--json"]
        if flag("mesures", True):
            args.append("--mesures")
        started = time.time()
        proc = subprocess.run(
            args,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=900,
        )
        # `conformance.mjs` sort en code 1 des qu'une suite echoue : c'est un
        # VERDICT, pas une panne. On ne le confond pas avec une erreur
        # d'execution, sans quoi un echec de conformite ressemblerait a une
        # indisponibilite du banc.
        rapport = None
        try:
            debut = proc.stdout.index("{")
            rapport = json.loads(proc.stdout[debut:])
        except (ValueError, json.JSONDecodeError):
            pass
        if rapport is None:
            return jsonify({
                "ok": False,
                "error": "Le banc n'a pas rendu de rapport exploitable.",
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
                "exitCode": proc.returncode,
            }), 500
        return jsonify({
            "ok": True,
            "verdict": rapport.get("verdict"),
            "durationMs": int((time.time() - started) * 1000),
            "rapport": rapport,
            "note": "Lecture seule : mesures comportementales sur le code en place, "
                    "aucune suite de tests lancee.",
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse (900 s)."}), 504
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": f"Executable introuvable : {exc}"}), 500
    finally:
        _conformance_lock.release()


# ---------------------------------------------------------------------------
# Expertise des ARTEFACTS REELS + garde d architecture, rejouables depuis
# l interface et le tunnel.
#
# Ces deux endpoints n executent aucune suite de tests : ils OUVRENT les
# fichiers presents dans `application/output/` et rendent ce qu ils mesurent.
# Lecture seule.
# ---------------------------------------------------------------------------
_expertise_lock = threading.Lock()


def _lance_outil(args, timeout=1800):
    """Execute un outil d expertise et rend son JSON."""
    proc = subprocess.run(args, cwd=WORKSPACE, capture_output=True, text=True, timeout=timeout)
    texte = proc.stdout or ""
    for ouvrant, fermant in (("{", "}"), ("[", "]")):
        debut = texte.find(ouvrant)
        if debut >= 0:
            try:
                return json.loads(texte[debut:texte.rfind(fermant) + 1]), proc.returncode
            except json.JSONDecodeError:
                continue
    return None, proc.returncode


def _python_du_projet():
    """L interpreteur du venv du projet : le python3 systeme n a ni numpy ni
    trimesh, et l expertise des GLB en depend."""
    venv = os.path.join(WORKSPACE, ".venv", "bin", "python")
    return venv if os.path.isfile(venv) else sys.executable


@python_bp.route("/api/architecture", methods=["GET", "POST"])
def aurora_architecture():
    """Garde d architecture de sortie : contrat output/<module>/<projet>/."""
    if not _expertise_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Une expertise est deja en cours."}), 409
    try:
        started = time.time()
        rapport, code = _lance_outil(
            [_python_du_projet(), os.path.join(WORKSPACE, "scripts", "garde-architecture.py"), "--json"],
            timeout=900)
        if rapport is None:
            return jsonify({"ok": False, "error": "La garde n a pas rendu de rapport."}), 500
        return jsonify({
            "ok": True,
            "conforme": bool(rapport.get("conforme")),
            "durationMs": int((time.time() - started) * 1000),
            "rapport": rapport,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse."}), 504
    finally:
        _expertise_lock.release()


@python_bp.route("/api/expertise", methods=["GET", "POST"])
def aurora_expertise():
    """Expertise des artefacts REELS.

    Parametres : `cible` = `artefacts` (GLB/MP4/WAV/images), `livrables`
    (projets de code), ou `tout` (defaut).
    """
    cible = (request.args.get("cible")
             or (request.get_json(silent=True) or {}).get("cible")
             or "tout")
    if not _expertise_lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Une expertise est deja en cours."}), 409
    try:
        started = time.time()
        out = {}
        if cible in ("tout", "artefacts"):
            rapport, _ = _lance_outil(
                [_python_du_projet(), os.path.join(WORKSPACE, "scripts", "expertise-artefacts.py"), "--json"],
                timeout=2400)
            out["artefacts"] = rapport
        if cible in ("tout", "livrables"):
            node_exe = resolve_node_exe()
            if not node_exe:
                out["livrables"] = {"error": "Node introuvable sur ce poste."}
            else:
                rapport, _ = _lance_outil(
                    [node_exe, "--experimental-strip-types",
                     os.path.join(WORKSPACE, "scripts", "expertise-livrables.mjs"), "--json"],
                    timeout=900)
                out["livrables"] = rapport
        constats = 0
        if isinstance(out.get("artefacts"), dict):
            for fiches in out["artefacts"].values():
                if isinstance(fiches, list):
                    constats += sum(len(f.get("constats") or []) for f in fiches
                                    if isinstance(f, dict))
        if isinstance(out.get("livrables"), dict):
            for p in out["livrables"].get("livrables") or []:
                constats += len(p.get("constats") or [])
        return jsonify({
            "ok": True,
            "cible": cible,
            "constats": constats,
            "durationMs": int((time.time() - started) * 1000),
            "rapport": out,
            "note": "Lecture seule : les fichiers de application/output/ sont ouverts et mesures.",
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Delai depasse."}), 504
    finally:
        _expertise_lock.release()


# v82lc — expose la tunnel URL en cours via le bridge.
# Cloudflared rotate l URL trycloudflare.com a chaque restart. Le lanceur Linux
# ecrit la nouvelle URL dans tunnel.txt (cf restart_tunnel.py). Cet endpoint
# le lit pour que UI / extension / agent externe puisse savoir ou pointe le
# tunnel sans avoir a parser le repo. Retourne 404 si le fichier n existe pas
# (cas d un user qui run le bridge en local sans tunnel).
#
# v82ld — mtime-based cache. Le fichier tunnel.txt change rarement (a chaque
# restart cloudflared, soit < 1x/heure en pratique) mais l endpoint est hit
# sans arret par UI + extension. On cache l URL en memoire et on ne re-read
# que si la mtime a bougé. Réponse contient `cached: true|false` pour debug.
_TUNNEL_URL_CACHE: "dict[str, object]" = {"url": None, "mtime": 0.0, "path": None}


def _resolve_tunnel_url_path():
    """Locate tunnel.txt, falling back to the legacy local-only filename."""
    import pathlib
    workspace = pathlib.Path(WORKSPACE).resolve()
    repo_root = workspace.parent if workspace.name == "application" else workspace
    for filename in ("tunnel.txt", "tunnel_url.txt"):
        for directory in dict.fromkeys((repo_root, workspace)):
            candidate = directory / filename
            if candidate.is_file():
                return candidate
    return None


def _tunnel_url_etag(url: str, mtime: float) -> str:
    """Compute weak ETag for /api/tunnel/url responses.

    Format : W/"<sha1(url + '|' + mtime)[:16]>". Truncated to 16 hex chars
    so the header stays compact ; collisions are irrelevant since the input
    space is "current tunnel URL + filesystem mtime" — both already unique
    per restart.
    """
    import hashlib as _hashlib
    payload = f"{url}|{mtime}".encode("utf-8")
    digest = _hashlib.sha1(payload).hexdigest()[:16]
    return f'W/"{digest}"'


@python_bp.route("/api/tunnel/url", methods=["GET"])
def tunnel_url():
    """Return the active cloudflared tunnel URL by reading tunnel.txt.

    Response:
      { ok: true, url: "https://...trycloudflare.com", source: "tunnel.txt", cached: bool }
      or
      { ok: false, error: "tunnel.txt missing — start Aurora to create the tunnel" }, 404

    v82le — ETag + Cache-Control layered on top of the mtime cache. If the
    client sends `If-None-Match: <etag>` and it matches the current ETag we
    return 304 with no body. Otherwise we return the JSON shape with both
    `ETag` and `Cache-Control: max-age=2` headers. The 2s TTL matches what
    UI/extension can tolerate (URL changes only on tunnel restart).
    """
    candidate = _resolve_tunnel_url_path()
    if candidate is None:
        return jsonify({
            "ok": False,
            "error": "tunnel.txt introuvable — lance start-aurora.sh pour creer le tunnel.",
        }), 404
    try:
        cur_mtime = candidate.stat().st_mtime
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"stat tunnel.txt echouee: {e}"}), 500

    cached_mtime = float(_TUNNEL_URL_CACHE.get("mtime") or 0.0)
    cached_path = _TUNNEL_URL_CACHE.get("path")
    cached_url = _TUNNEL_URL_CACHE.get("url")
    is_hit = (
        cached_url is not None
        and cached_path == str(candidate)
        and abs(cur_mtime - cached_mtime) < 1e-6
    )

    if is_hit:
        url_value = str(cached_url)
        etag = _tunnel_url_etag(url_value, cur_mtime)
        client_etag = request.headers.get("If-None-Match", "").strip()
        if client_etag and client_etag == etag:
            resp = Response(status=304)
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "max-age=2"
            return resp
        resp = jsonify({
            "ok": True,
            "url": url_value,
            "source": str(candidate),
            "cached": True,
        })
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "max-age=2"
        return resp

    try:
        url = candidate.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"lecture tunnel.txt echouee: {e}"}), 500
    if not url.startswith("https://"):
        return jsonify({
            "ok": False,
            "error": f"tunnel.txt content invalide: {url[:80]!r}",
        }), 500

    _TUNNEL_URL_CACHE["url"] = url
    _TUNNEL_URL_CACHE["mtime"] = cur_mtime
    _TUNNEL_URL_CACHE["path"] = str(candidate)
    etag = _tunnel_url_etag(url, cur_mtime)
    client_etag = request.headers.get("If-None-Match", "").strip()
    if client_etag and client_etag == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "max-age=2"
        return resp
    resp = jsonify({
        "ok": True,
        "url": url,
        "source": str(candidate),
        "cached": False,
    })
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "max-age=2"
    return resp


@python_bp.route("/api/python/job/<job_id>")
def python_job_status(job_id: str):
    """Return the current status of an async Python job."""
    with _python_jobs_lock:
        job = _python_jobs.get(job_id)
    if job is None:
        return jsonify({"status": "unknown", "error": "job not found (expired or invalid id)"}), 404
    resp = {"jobId": job_id, **job}
    if job.get("status") == "running" and "startedAt" in job:
        elapsed = time.time() - job["startedAt"]
        resp["elapsedSeconds"] = round(elapsed, 1)
        pct = float(job.get("progressPct", 0.0))
        if pct > 8.0:
            rate = elapsed / pct
            resp["estimatedRemainingSeconds"] = max(1, round((100.0 - pct) * rate))
    return jsonify(resp)


@python_bp.route("/api/python/cancel/<job_id>", methods=["POST"])
def python_job_cancel(job_id: str):
    """Annule un job Python video, actif ou encore dans la file GPU."""
    return _cancel_video_job_response(job_id)


@python_bp.route("/api/python/run", methods=["POST"])
def python_run():
    """Synchronous path — kept for Tauri / local browser modes where the
    tunnel timeout doesn't apply. Cloud/tunnel clients should use /run-async.
    """
    data = request.get_json()
    script_path = _resolve_script_path(data.get("scriptPath", ""))
    args = data.get("args", [])

    try:
        run_env = _build_python_env()
        result = subprocess.run(
            [sys.executable, "-W", "ignore", script_path] + args,
            capture_output=True, timeout=900, cwd=WORKSPACE, env=run_env,
        )
        return jsonify({
            "output": result.stdout.decode("utf-8", errors="replace"),
            "error": _clean_stderr(result.stderr.decode("utf-8", errors="replace")),
            "exitCode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"output": "", "error": "Timeout (900s)", "exitCode": -1})
    except Exception as e:
        return jsonify({"output": "", "error": str(e), "exitCode": -1})


@python_bp.route("/api/command/run", methods=["POST"])
def command_run():
    data = request.get_json()
    executable = data.get("executable", "")
    args = data.get("args", [])
    cwd = data.get("cwd", WORKSPACE)
    timeout_ms = data.get("timeoutMs", 60000)

    try:
        result = subprocess.run(
            [executable] + args,
            capture_output=True, timeout=timeout_ms / 1000, cwd=cwd,
        )
        return jsonify({
            "ok": result.returncode == 0,
            "exitCode": result.returncode,
            "output": result.stdout.decode("utf-8", errors="replace"),
            "command": f"{executable} {' '.join(args)}",
        })
    except Exception as e:
        return jsonify({"ok": False, "exitCode": -1, "output": str(e), "command": executable})


@python_bp.route("/api/command/spawn", methods=["POST"])
def command_spawn():
    """Lance une commande en arriere-plan (detached). Utilise par le dev server du module Code."""
    data = request.get_json()
    executable = data.get("executable", "")
    args = data.get("args", [])
    cwd = data.get("cwd", WORKSPACE)

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [executable] + args,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return jsonify({
            "ok": True,
            "pid": proc.pid,
            "command": f"{executable} {' '.join(args)}",
            "stdoutLog": None,
            "stderrLog": None,
        })
    except Exception as e:
        return jsonify({"ok": False, "pid": 0, "command": executable, "stdoutLog": None, "stderrLog": None}), 500



# --- Refactored to application/routes/fs_bp_routes.py ---
