from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "Outputs" / "auto_rl"
PYTHON = ROOT / "application" / ".venv" / "bin" / "python"
LABELS = {"3d": "3D · TRELLIS.2", "code": "Code · Qwen3-8B", "image": "Image · Flux.2", "audio": "Voix · Kokoro",
          "conversation": "Conversation · Qwen", "cyber": "Cyber · Hacker Model", "cowork": "Cowork · Agent"}


def defaults(module="3d"):
    return {
        "schema": 1, "module": module, "state_dir": str(STATE),
        "trainer": "preference_lora" if module in {"3d", "code", "conversation", "cyber", "cowork"} else "evolution",
        "kaggle_max_session": True, "rollouts_per_task": 3, "train_learning_rate": 0.0001,
        "dpo_beta": 0.1 if module in {"code", "conversation", "cyber", "cowork"} else 100.0, "anchor_penalty": 0.1,
        "checkpoint_every": 5, "max_training_artifacts_gb": 3,
        "execution": "hybrid", "stage": "full", "local_epochs": 50, "kaggle_epochs": 500,
        "kaggle_kernel": "evanpasdeloup/aurora-universal-trainer",
        "kaggle_dataset": "evanpasdeloup/aurora-rl-training-batches",
        "kaggle_timeout_seconds": 39600, "kaggle_poll_seconds": 20,
        "fallback_on_quota": True, "prepared_tasks": "", "initial_adapter": "",
        "auto_refill": True, "refill_search": True,
        "mode": "manual", "cycles": 1, "max_rejections": 3,
        "max_hours": 8, "minimum_free_gb": 12, "max_vram_gb": 14.5,
        "seed": 20260912, "prompt": "", "reference_image": "",
        "train_tasks": 3 if module in {"3d", "code"} else 2, "eval_tasks": 3, "eval_seeds": [41, 137],
        "iterations": 2, "directions": 2, "sigma": 0.08, "learning_rate": 0.04,
        "rank": 4, "max_layers": 8, "trust_radius": 0.5, "drift_penalty": 0.1,
        "min_gain": 0.002, "regression_tolerance": 0.01, "auto_min_tasks": 8,
        "generation": {"batch_size": 1, "max_new_tokens": 768,
                       "temperature": 0.7, "top_p": 0.9,
                       "steps": 12 if module == "3d" else 4,
                       "width": 512, "height": 512, "trellis_pipeline": "512",
                       "texture_size": 1024, "decimation_target": 100000,
                       "max_num_tokens": 32768, "guidance_scale": 0.0,
                       "voice": "ff_siwis", "speed": 1.0},
        "models": {"3d": "microsoft/TRELLIS.2-4B", "code": "Qwen/Qwen3-8B",
                   "image": "Comfy-Org/flux2-dev", "audio": "hexgrad/Kokoro-82M",
                   "conversation": "Qwen/Qwen3-8B", "cyber": "Qwen/Qwen3-8B", "cowork": "Qwen/Qwen3-8B",
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
    if c["eval_tasks"] < 3 or len(set(c["eval_seeds"])) < 2:
        raise ValueError("L'audit exige au moins 3 sujets et 2 graines distinctes")
    if c["mode"] == "auto" and c["eval_tasks"] < c["auto_min_tasks"]:
        raise ValueError("Le mode automatique exige au moins 8 sujets d'audit")
    if c["generation"]["batch_size"] != 1 or c["render_views"] not in range(4, 9):
        raise ValueError("Batch = 1 et 4 à 8 vues requis")
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
