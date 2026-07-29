"""Idempotent setup for an already-mounted AURORA_MODELS support.

This script never partitions or formats a device. It refuses to create the
cold tree unless the configured path is a distinct mounted filesystem.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from aurora_storage import AuroraStorageManager


COLD_DIRECTORIES = (
    "hf/hub",
    "comfyui/checkpoints",
    "comfyui/unet",
    "comfyui/vae",
    "comfyui/loras",
    "comfyui/upscale_models",
    "comfyui/frame_interpolation",
    "comfyui/audio_encoders",
    "outputs/videos",
    "archive",
)


def configure_comfy_paths(manager: AuroraStorageManager) -> dict:
    candidates = [
        manager.workspace.parent / "modele" / "comfyui" / "comfyui",
        manager.workspace.parent / "modele" / "comfyui",
    ]
    comfy_root = next((path for path in candidates if path.is_dir()), None)
    if comfy_root is None:
        return {"ok": False, "reason": "comfyui_not_found"}
    yaml_path = comfy_root / "extra_model_paths.yaml"
    marker_start = "# BEGIN AURORA COLD STORAGE"
    marker_end = "# END AURORA COLD STORAGE"
    block = (
        f"{marker_start}\n"
        "aurora_cold_storage:\n"
        f"  base_path: {manager.cold_root / 'comfyui'}\n"
        "  checkpoints: checkpoints\n"
        "  unet: unet\n"
        "  vae: vae\n"
        "  loras: loras\n"
        "  upscale_models: upscale_models\n"
        "  audio_encoders: audio_encoders\n"
        f"{marker_end}\n"
    )
    existing = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
    if marker_start in existing and marker_end in existing:
        before, tail = existing.split(marker_start, 1)
        _, after = tail.split(marker_end, 1)
        updated = before.rstrip() + "\n\n" + block + after.lstrip("\n")
    else:
        updated = existing.rstrip() + ("\n\n" if existing.strip() else "") + block
    if updated != existing:
        temp = yaml_path.with_suffix(".yaml.aurora-tmp")
        temp.write_text(updated, encoding="utf-8")
        os.replace(temp, yaml_path)
    return {"ok": True, "path": str(yaml_path)}


def redirect_outputs(manager: AuroraStorageManager) -> dict:
    target_info = manager.ensure_output_target(0)
    if not target_info.get("ok") or target_info.get("tier") != "cold":
        return target_info
    source = manager.workspace / "output" / "videos"
    target = Path(target_info["path"])
    if source.is_symlink():
        if source.resolve(strict=False) == target.resolve(strict=False):
            return {"ok": True, "already": True, "source": str(source), "target": str(target)}
        return {"ok": False, "reason": "output_symlink_conflict", "path": str(source)}
    source.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        destination = target / child.name
        if destination.exists():
            if manager._path_size(child) != manager._path_size(destination):
                return {
                    "ok": False,
                    "reason": "output_destination_conflict",
                    "source": str(child),
                    "destination": str(destination),
                }
            continue
        manager._copy_verified(child, destination)
    backup = source.parent / ".videos.aurora-backup"
    manager._remove_path(backup)
    os.replace(source, backup)
    try:
        os.symlink(str(target), str(source), target_is_directory=True)
    except Exception:
        os.replace(backup, source)
        raise
    manager._remove_path(backup)
    return {"ok": True, "source": str(source), "target": str(target)}


def inventory_markdown(manager: AuroraStorageManager, setup: dict) -> str:
    status = manager.status()
    lines = [
        "# Inventaire des poids vidéo Aurora",
        "",
        f"_Généré le {time.strftime('%Y-%m-%d %H:%M:%S')}._",
        "",
        f"- Support froid monté : **{'oui' if status['key_mounted'] else 'non'}**",
        f"- Point configuré : `{status['mount_path']}`",
        f"- Plancher de sécurité : **{status['floor_gb']} Go** par étage",
        f"- Sorties : **{status['outputs_tier']}** (`{status['outputs_path']}`)",
        "",
        "| ID | Type | Taille déclarée | Étage | Disponible | Chemin actif |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in status["models"]:
        lines.append(
            f"| {item.get('id')} | {item.get('kind')} | {item.get('size_gb', 0)} Go "
            f"| {item.get('tier')} | {'oui' if item.get('available') else 'non'} "
            f"| `{item.get('path')}` |"
        )
    lines.extend([
        "",
        "## État du setup",
        "",
        "```json",
        json.dumps(setup, ensure_ascii=False, indent=2),
        "```",
        "",
        "Les licences sont documentées séparément et n'influencent pas la sélection",
        "qualitative pour un usage personnel ; elles restent utiles si le déploiement",
        "devient un jour public ou commercial.",
        "",
    ])
    return "\n".join(lines)


def run_setup(manager: AuroraStorageManager, *, apply: bool) -> dict:
    if not manager.cold_mounted():
        return {
            "ok": False,
            "reason": "cold_storage_offline",
            "mount_path": str(manager.cold_root),
            "action": "monter un support distinct avant tout déplacement; aucun formatage automatique",
        }
    capacity = manager.ensure_space("cold", 0, allow_eviction=False)
    if not capacity.get("ok"):
        return capacity
    if not apply:
        return {
            "ok": True,
            "dry_run": True,
            "mount_path": str(manager.cold_root),
            "would_create": [str(manager.cold_root / rel) for rel in COLD_DIRECTORIES],
        }
    for relative in COLD_DIRECTORIES:
        (manager.cold_root / relative).mkdir(parents=True, exist_ok=True)
    comfy = configure_comfy_paths(manager)
    outputs = redirect_outputs(manager)
    return {
        "ok": bool(comfy.get("ok") and outputs.get("ok")),
        "dry_run": False,
        "mount_path": str(manager.cold_root),
        "comfyui": comfy,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Créer les dossiers et redirections")
    parser.add_argument("--mount-path", default=os.environ.get("AURORA_COLD_STORAGE", "/mnt/aurora_models"))
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    manager = AuroraStorageManager(cold_root=args.mount_path)
    result = run_setup(manager, apply=args.apply)
    report_path = Path(args.report) if args.report else manager.workspace / "docs" / "VIDEO_WEIGHTS_INVENTORY.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(inventory_markdown(manager, result), encoding="utf-8")
    print(json.dumps({**result, "report": str(report_path)}, ensure_ascii=False))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())

