from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "Outputs" / "auto_rl"
PYTHON = ROOT / "application" / ".venv" / "bin" / "python"
TEXT_MODULES = {"code", "conversation", "cyber", "cowork", "learning"}
LABELS = {"3d": "3D · TRELLIS.2", "code": "Code · Qwen3-8B", "image": "Image · Flux.2", "audio": "Voix · Kokoro",
          "conversation": "Conversation · Qwen3-8B", "cyber": "Cyber · Qwen3-8B", "cowork": "Cowork · Qwen3-8B", "learning": "Apprentissage · Qwen3-8B",
          "video": "Vidéo · Wan2.2 5B", "animation": "Animation · HY-Motion"}


def defaults(module="3d"):
    return {
        "schema": 1, "module": module, "state_dir": str(STATE),
        "trainer": "surrogate_es" if module in {"image", "video", "animation"} else "preference_lora" if module in {"3d", "code", "conversation", "cyber", "cowork", "learning"} else "evolution",
        "kaggle_max_session": False, "rollouts_per_task": 3, "train_learning_rate": 0.00005,
        "oracle_teaching": module in {"conversation", "learning"},
        "training_context_length": 3072,
        "dpo_beta": 0.1 if module in {"code", "conversation", "cyber", "cowork", "learning"} else 100.0, "anchor_penalty": 0.1,
        "comfy_unet": str(ROOT / "modele/comfyui/models/unet/flux2-dev-Q4_K_M.gguf"),
        "comfy_clip": str(ROOT / "modele/comfyui/models/text_encoders/mistral_3_small_flux2_fp8.safetensors"),
        "comfy_vae": str(ROOT / "modele/comfyui/models/vae/flux2-vae.safetensors"),
        "video_unet": str(ROOT / "modele/comfyui/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"),
        "video_clip": str(ROOT / "modele/comfyui/models/text_encoders/umt5-xxl-encoder-Q5_K_M.gguf"),
        "video_vae": str(ROOT / "modele/comfyui/models/vae/wan2.2_vae.safetensors"),
        "hymotion_root": str(Path.home() / ".local/share/auroraia/external/HY-Motion"),
        "checkpoint_every": 5, "max_training_artifacts_gb": 3,
        "execution": "hybrid", "stage": "full", "local_epochs": 20, "kaggle_epochs": 40,
        "kaggle_kernel": "evanpasdeloup/aurora-universal-trainer",
        "kaggle_dataset": "evanpasdeloup/aurora-rl-training-batches",
        "kaggle_timeout_seconds": 7200, "kaggle_poll_seconds": 20,
        "early_stopping_patience": 8, "kaggle_accelerator": "gpu_t4_x2",
        "fallback_on_quota": True, "prepared_tasks": "", "initial_adapter": "",
        "auto_refill": True, "refill_search": False,
        # Failed training subjects are durable hard negatives.  They are
        # replayed on the next cycle; held-out audit subjects are never saved.
        "failure_replay_tasks": 4, "failure_memory_limit": 256,
        "failure_score_threshold": 0.999,
        "mode": "manual", "cycles": 1, "max_rejections": 3,
        "max_hours": 8, "minimum_free_gb": 12, "max_vram_gb": 14.5,
        "seed": 20260912, "prompt": "", "reference_image": "",
        "train_tasks": 6 if module in TEXT_MODULES else 3, "eval_tasks": 3, "eval_seeds": [41, 137],
        "iterations": 2, "directions": 2, "sigma": 0.08, "learning_rate": 0.04,
        "rank": 4, "max_layers": 8, "trust_radius": 0.5, "drift_penalty": 0.1,
        "min_gain": 0.002, "regression_tolerance": 0.01, "auto_min_tasks": 8,
        "generation": {"batch_size": 1, "max_new_tokens": 768,
                       "temperature": 0.7, "top_p": 0.9,
                       "steps": 50 if module == "animation" else 20 if module == "video" else 12 if module == "3d" else 4,
                       "frames": 33, "fps": 16, "duration": 3.0, "motion_cfg": 5.0, "video_cfg": 5.0, "video_shift": 8.0,
                       "width": 512, "height": 512, "trellis_pipeline": "512",
                       "texture_size": 1024, "decimation_target": 100000,
                       "max_num_tokens": 32768, "guidance_scale": 0.0,
                       # TRELLIS.2 reconstruit la topologie par Dual Contouring
                       # AVANT le bake de texture: la couleur survit, et la
                       # surface sort manifolde, sans auto-intersection. Le
                       # juge 3D retire la totalite des auto-intersections
                       # (diviseur `1/(1+inter/faces*20)`), c'est donc le
                       # levier de qualite le plus direct. Valide par A/B dans
                       # Outputs/auto_rl/diagnostics/remesh_ab_*.log.
                       "remesh": False,
                       "judge_face_limit": 250000,
                       "voice": "ff_siwis", "speed": 1.0},
        "models": {"3d": "microsoft/TRELLIS.2-4B", "code": "Qwen/Qwen3-8B",
                   "image": "Comfy-Org/flux2-dev", "audio": "hexgrad/Kokoro-82M",
                   "conversation": "Qwen/Qwen3-8B", "cyber": "Qwen/Qwen3-8B", "cowork": "Qwen/Qwen3-8B",
                   "learning": "Qwen/Qwen3-8B", "video": "Wan-AI/Wan2.2-TI2V-5B",
                   "animation": "tencent/HY-Motion-1.0", "motion_text": "Qwen/Qwen3-8B",
                   "motion_clip": "openai/clip-vit-large-patch14",
                   "clip": "openai/clip-vit-base-patch32",
                   "asr": "Systran/faster-whisper-large-v3"},
        "trellis_root": str(Path.home() / ".local/share/auroraia/external/TRELLIS.2"),
        "python_image": "docker.io/library/python:3.12-slim",
        "cpp_image": "localhost/aurora-rl-cpp:1", "sandbox_timeout": 12,
        "render_views": 4, "render_size": 256,
        "aesthetic_weights": str(Path.home() / ".cache/aurora-rl-judges/aesthetic-vit-b32.safetensors"),
    }


def validate(c):
    if c["module"] not in LABELS or c["mode"] not in {"manual", "auto"}:
        raise ValueError("Module ou mode inconnu")
    for key in ("cycles", "train_tasks", "eval_tasks", "directions", "rank", "max_layers", "max_rejections"):
        if not isinstance(c[key], int) or not 1 <= c[key] <= 100:
            raise ValueError(f"{key}: entier entre 1 et 100 requis")
    for key in ("iterations", "local_epochs", "kaggle_epochs"):
        if not isinstance(c[key], int) or not 0 <= c[key] <= 10000:
            raise ValueError(f"{key}: entier entre 0 et 10000 requis")
    if c["execution"] not in {"hybrid", "local", "kaggle", "kaggle_only"} or c["stage"] not in {"full", "remote"}:
        raise ValueError("Destination d'entraînement invalide")
    if c["execution"] == "kaggle_only":
        raise ValueError("Le cycle intégral Kaggle n'est pas compatible avec les moteurs locaux. Choisir hybride : essais PC, poids Kaggle, audit PC.")
    if not 2 <= c["rollouts_per_task"] <= 16:
        raise ValueError("Il faut 2 à 16 essais par sujet pour comparer les préférences")
    if not 1200 <= c["kaggle_timeout_seconds"] <= 39600:
        raise ValueError("La session Kaggle doit durer entre 20 minutes et 11 heures")
    if 'training_budget_seconds' in c and (type(c['training_budget_seconds']) is not int or not 60 <= c['training_budget_seconds'] <= 36000):
        raise ValueError('Budget d’optimisation invalide : 60 à 36000 secondes')
    if c.get('sft_weight',0)<0 or c.get('sft_weight',0)>2:raise ValueError('Poids de supervision invalide')
    if c.get('strict_audit') and (c['regression_tolerance']!=0 or c['eval_tasks']<24 or len(set(c['eval_seeds']))<4):
        raise ValueError('Audit renforcé : 24 sujets, quatre graines et aucune régression tolérée')
    if c["trainer"] == "preference_lora" and c["train_tasks"] < 3:
        raise ValueError("Au moins 3 sujets sont requis pour apprentissage et validation séparés")
    if c["eval_tasks"] < 3 or len(set(c["eval_seeds"])) < 2:
        raise ValueError("L'audit exige au moins 3 sujets et 2 graines distinctes")
    if c["mode"] == "auto" and c["eval_tasks"] < c["auto_min_tasks"]:
        raise ValueError("Le mode automatique exige au moins 8 sujets d'audit")
    if c["generation"]["batch_size"] != 1 or c["render_views"] not in range(4, 9):
        raise ValueError("Batch = 1 et 4 à 8 vues requis")
    if c['module'] in {'video', 'animation'}:
        g=c['generation']
        if c['trainer'] != 'surrogate_es':
            raise ValueError('Vidéo et animation utilisent les corrections de poids mesurées puis optimisées sur Kaggle')
        if not 1 <= g['steps'] <= 100 or not .7 <= g['duration'] <= 12:
            raise ValueError('Profil temporel hors limites')
        if c['module']=='video' and (g['frames'] not in range(9,82,4) or not 1<=g['fps']<=60
                                     or any(g[k]%32 or not 128<=g[k]<=1280 for k in ('width','height'))):
            raise ValueError('Vidéo : 9 à 81 images (4n+1), dimensions multiples de 32 et 1 à 60 fps')
    for key in ("sigma", "learning_rate", "trust_radius", "max_hours", "max_vram_gb"):
        if not 0 < float(c[key]) < 100:
            raise ValueError(f"{key}: valeur positive bornée requise")
    state = Path(c["state_dir"]).expanduser().resolve()
    # All writes belong to a dedicated local output tree, never a model cache.
    if state != STATE.resolve() and not state.name.startswith("aurora-rl-test-"):
        raise ValueError(f"Les résultats doivent être dans {STATE}")
    c["state_dir"] = str(state)
    return c


def read_config(path=None, module=None):
    custom = json.loads(Path(path).read_text()) if path else {}
    c = defaults(module or custom.get("module", "3d"))
    for key, value in custom.items():
        if key in ("generation", "models"):
            c[key].update(value)
        else:
            c[key] = value
    if module:
        c["module"] = module
    return validate(c)
