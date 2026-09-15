"""Safe two-tier storage manager for Aurora model weights and video outputs.

Cold storage is considered available only when its configured path is a real
mount point. Merely creating ``/mnt/aurora_models`` on the internal disk must
never be mistaken for an attached drive.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable


GIB = 1024 ** 3
DEFAULT_FLOOR_GB = 20.0


class StorageError(RuntimeError):
    def __init__(self, payload: dict):
        super().__init__(payload.get("reason") or payload.get("error") or "storage_error")
        self.payload = payload


class AuroraStorageManager:
    def __init__(
        self,
        manifest_path: str | Path | None = None,
        cold_root: str | Path | None = None,
        internal_root: str | Path | None = None,
        workspace: str | Path | None = None,
        floor_gb: float = DEFAULT_FLOOR_GB,
        disk_usage_fn: Callable = shutil.disk_usage,
        ismount_fn: Callable[[str], bool] = os.path.ismount,
    ):
        service_dir = Path(__file__).resolve().parent
        self.workspace = Path(workspace or service_dir.parents[1]).resolve()
        self.manifest_path = Path(
            manifest_path or self.workspace / "config" / "storage_manifest.json"
        ).resolve()
        self.cold_root = Path(
            cold_root or os.environ.get("AURORA_COLD_STORAGE", "/mnt/aurora_models")
        )
        self.internal_root = Path(internal_root or self.workspace).resolve()
        self.floor_gb = float(floor_gb)
        self._disk_usage = disk_usage_fn
        self._ismount = ismount_fn
        self._lock = threading.RLock()

    def cold_mounted(self) -> bool:
        try:
            return self.cold_root.is_dir() and bool(self._ismount(str(self.cold_root)))
        except OSError:
            return False

    def _load_document(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "entries": []}
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"version": 1, "entries": data}
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise StorageError({"ok": False, "reason": "invalid_storage_manifest"})
        return data

    def entries(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._load_document()["entries"]]

    def _save_document(self, document: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".storage-manifest-",
            suffix=".json",
            dir=str(self.manifest_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.manifest_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _entry(self, model_id: str, document: dict | None = None) -> tuple[dict, dict]:
        doc = document or self._load_document()
        for item in doc["entries"]:
            if item.get("id") == model_id:
                return item, doc
        raise StorageError({
            "ok": False,
            "reason": "model_not_registered",
            "model": model_id,
        })

    def _paths_for(self, item: dict) -> tuple[Path, Path]:
        hot_raw = str(item.get("hot_path") or "").strip()
        cold_raw = str(item.get("cold_path") or "").strip()
        if not hot_raw or not cold_raw:
            raise StorageError({"ok": False, "reason": "paths_missing", "model": item.get("id")})
        hot_path = Path(hot_raw)
        cold_path = Path(cold_raw)
        if not hot_path.is_absolute() or not cold_path.is_absolute():
            raise StorageError({"ok": False, "reason": "paths_must_be_absolute", "model": item.get("id")})
        protected = {
            Path("/"),
            Path.home().resolve(),
            self.workspace,
            self.internal_root,
            self.cold_root,
        }
        if hot_path.resolve(strict=False) in protected or cold_path.resolve(strict=False) in protected:
            raise StorageError({"ok": False, "reason": "unsafe_broad_path", "model": item.get("id")})
        try:
            cold_path.resolve(strict=False).relative_to(self.cold_root.resolve(strict=False))
        except ValueError as exc:
            raise StorageError({
                "ok": False,
                "reason": "cold_path_outside_mount",
                "model": item.get("id"),
                "path": str(cold_path),
            }) from exc
        return hot_path, cold_path

    @staticmethod
    def _usage_dict(usage) -> dict:
        return {
            "total_gb": round(usage.total / GIB, 2),
            "used_gb": round(usage.used / GIB, 2),
            "free_gb": round(usage.free / GIB, 2),
        }

    def _tier_usage(self, tier: str):
        if tier == "cold":
            if not self.cold_mounted():
                raise StorageError({
                    "ok": False,
                    "reason": "cold_storage_offline",
                    "tier": "cold",
                    "action": "rebrancher et monter le support AURORA_MODELS",
                })
            return self._disk_usage(str(self.cold_root))
        return self._disk_usage(str(self.internal_root))

    def ensure_space(
        self,
        target_tier: str,
        needed_gb: float,
        *,
        allow_eviction: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """Reserve capacity while preserving the hard free-space floor."""
        tier = "cold" if target_tier == "cold" else "hot"
        needed = max(0.0, float(needed_gb))
        evictions: list[str] = []
        usage = self._tier_usage(tier)
        free_gb = usage.free / GIB
        if free_gb - needed >= self.floor_gb:
            return {
                "ok": True,
                "tier": tier,
                "needed_gb": needed,
                "free_gb": round(free_gb, 2),
                "floor_gb": self.floor_gb,
                "evictions": evictions,
                "dry_run": dry_run,
            }

        if tier == "hot" and allow_eviction and self.cold_mounted():
            candidates = sorted(
                (
                    item for item in self.entries()
                    if item.get("tier") == "hot"
                    and not item.get("pin")
                    and item.get("kind") not in {"llm", "output"}
                    and item.get("hot_path")
                    and item.get("cold_path")
                ),
                key=lambda item: float(item.get("last_access") or 0),
            )
            for item in candidates:
                evictions.append(str(item["id"]))
                if not dry_run:
                    self.tier_model(str(item["id"]), "cold", _skip_hot_space_check=True)
                    usage = self._tier_usage("hot")
                    free_gb = usage.free / GIB
                else:
                    free_gb += float(item.get("size_gb") or 0)
                if free_gb - needed >= self.floor_gb:
                    return {
                        "ok": True,
                        "tier": tier,
                        "needed_gb": needed,
                        "free_gb": round(free_gb, 2),
                        "floor_gb": self.floor_gb,
                        "evictions": evictions,
                        "dry_run": dry_run,
                    }

        return {
            "ok": False,
            "reason": "disk_full",
            "tier": tier,
            "free_gb": round(free_gb, 2),
            "needed_gb": needed,
            "floor_gb": self.floor_gb,
            "evictions": evictions,
            "suggestion": (
                "libérer de l'espace ou connecter un support froid plus grand; "
                f"Aurora conserve toujours {self.floor_gb:g} Go libres"
            ),
        }

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_symlink():
            return 0
        if path.is_file():
            return path.stat().st_size
        total = 0
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        return total

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)

    def _copy_verified(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.parent / f".{destination.name}.aurora-partial"
        self._remove_path(temp)
        try:
            if source.is_dir():
                shutil.copytree(source, temp, symlinks=True)
            else:
                shutil.copy2(source, temp)
            if self._path_size(source) != self._path_size(temp):
                raise StorageError({
                    "ok": False,
                    "reason": "copy_verification_failed",
                    "source": str(source),
                    "destination": str(destination),
                })
            if destination.exists() or destination.is_symlink():
                raise StorageError({
                    "ok": False,
                    "reason": "destination_exists",
                    "destination": str(destination),
                })
            os.replace(temp, destination)
        finally:
            self._remove_path(temp)

    def _replace_with_symlink(self, hot_path: Path, cold_path: Path) -> None:
        backup = hot_path.parent / f".{hot_path.name}.aurora-backup"
        self._remove_path(backup)
        hot_path.parent.mkdir(parents=True, exist_ok=True)
        if hot_path.exists() and not hot_path.is_symlink():
            os.replace(hot_path, backup)
        elif hot_path.is_symlink():
            hot_path.unlink()
        try:
            os.symlink(
                str(cold_path),
                str(hot_path),
                target_is_directory=cold_path.is_dir(),
            )
        except Exception:
            if hot_path.is_symlink():
                hot_path.unlink()
            if backup.exists():
                os.replace(backup, hot_path)
            raise
        self._remove_path(backup)

    def tier_model(
        self,
        model_id: str,
        tier: str,
        *,
        _skip_hot_space_check: bool = False,
    ) -> dict:
        if tier not in {"hot", "cold"}:
            return {"ok": False, "reason": "invalid_tier", "tier": tier}
        if tier == "hot":
            return self.stage(model_id, _skip_space_check=_skip_hot_space_check)
        with self._lock:
            item, document = self._entry(model_id)
            if item.get("pin"):
                return {"ok": False, "reason": "model_pinned", "model": model_id}
            if not self.cold_mounted():
                return {
                    "ok": False,
                    "reason": "cold_storage_offline",
                    "model": model_id,
                    "action": "rebrancher et monter le support AURORA_MODELS",
                }
            try:
                hot_path, cold_path = self._paths_for(item)
            except StorageError as exc:
                return exc.payload
            if hot_path.is_symlink() and hot_path.resolve(strict=False) == cold_path.resolve(strict=False):
                item.update({"tier": "cold", "last_access": time.time()})
                self._save_document(document)
                return {"ok": True, "model": model_id, "tier": "cold", "already": True}
            if not hot_path.exists():
                return {"ok": False, "reason": "hot_source_missing", "path": str(hot_path)}
            needed = max(float(item.get("size_gb") or 0), self._path_size(hot_path) / GIB)
            capacity = self.ensure_space("cold", needed, allow_eviction=False)
            if not capacity.get("ok"):
                return capacity
            try:
                if not cold_path.exists():
                    self._copy_verified(hot_path, cold_path)
                elif self._path_size(hot_path) != self._path_size(cold_path):
                    return {
                        "ok": False,
                        "reason": "cold_destination_conflict",
                        "path": str(cold_path),
                    }
                self._replace_with_symlink(hot_path, cold_path)
            except Exception as exc:
                payload = getattr(exc, "payload", None)
                return payload or {"ok": False, "reason": "migration_failed", "error": str(exc)}
            item.update({
                "tier": "cold",
                "size_gb": round(needed, 3),
                "last_access": time.time(),
            })
            self._save_document(document)
            return {
                "ok": True,
                "model": model_id,
                "tier": "cold",
                "path": str(cold_path),
                "hot_link": str(hot_path),
            }

    def stage(self, model_id: str, *, _skip_space_check: bool = False) -> dict:
        """Copy cold source to internal storage without deleting cold truth."""
        with self._lock:
            item, document = self._entry(model_id)
            if not self.cold_mounted():
                return {
                    "ok": False,
                    "reason": "cold_storage_offline",
                    "model": model_id,
                    "action": "rebrancher et monter le support AURORA_MODELS",
                }
            try:
                hot_path, cold_path = self._paths_for(item)
            except StorageError as exc:
                return exc.payload
            if not cold_path.exists():
                return {"ok": False, "reason": "cold_source_missing", "path": str(cold_path)}
            if hot_path.exists() and not hot_path.is_symlink():
                item.update({"tier": "staged", "last_access": time.time()})
                self._save_document(document)
                return {"ok": True, "model": model_id, "tier": "staged", "already": True}
            needed = max(float(item.get("size_gb") or 0), self._path_size(cold_path) / GIB)
            if not _skip_space_check:
                capacity = self.ensure_space("hot", needed)
                if not capacity.get("ok"):
                    return capacity
            try:
                if hot_path.is_symlink():
                    hot_path.unlink()
                self._copy_verified(cold_path, hot_path)
            except Exception as exc:
                if not hot_path.exists() and cold_path.exists():
                    try:
                        os.symlink(str(cold_path), str(hot_path), target_is_directory=cold_path.is_dir())
                    except Exception:
                        pass
                payload = getattr(exc, "payload", None)
                return payload or {"ok": False, "reason": "stage_failed", "error": str(exc)}
            item.update({"tier": "staged", "size_gb": round(needed, 3), "last_access": time.time()})
            self._save_document(document)
            return {"ok": True, "model": model_id, "tier": "staged", "path": str(hot_path)}

    def unstage(self, model_id: str) -> dict:
        with self._lock:
            item, document = self._entry(model_id)
            try:
                hot_path, cold_path = self._paths_for(item)
            except StorageError as exc:
                return exc.payload
            if not self.cold_mounted() or not cold_path.exists():
                return {
                    "ok": False,
                    "reason": "cold_storage_offline" if not self.cold_mounted() else "cold_source_missing",
                    "model": model_id,
                }
            try:
                self._replace_with_symlink(hot_path, cold_path)
            except Exception as exc:
                return {"ok": False, "reason": "unstage_failed", "error": str(exc)}
            item.update({"tier": "cold", "last_access": time.time()})
            self._save_document(document)
            return {"ok": True, "model": model_id, "tier": "cold", "path": str(cold_path)}

    def purge(self, model_id: str, *, dry_run: bool = False) -> dict:
        with self._lock:
            item, document = self._entry(model_id)
            if item.get("pin"):
                return {"ok": False, "reason": "model_pinned", "model": model_id}
            try:
                paths = list(self._paths_for(item))
            except StorageError as exc:
                return exc.payload
            if dry_run:
                return {"ok": True, "dry_run": True, "model": model_id, "paths": [str(p) for p in paths]}
            for path in paths:
                # Only paths explicitly registered in the manifest can reach here.
                self._remove_path(path)
            document["entries"] = [entry for entry in document["entries"] if entry.get("id") != model_id]
            self._save_document(document)
            return {"ok": True, "model": model_id, "purged": [str(p) for p in paths]}

    def ensure_output_target(self, needed_gb: float = 0.0) -> dict:
        internal = self.workspace / "output" / "video"
        if not self.cold_mounted():
            internal.mkdir(parents=True, exist_ok=True)
            return {
                "ok": True,
                "tier": "hot",
                "path": str(internal),
                "warnings": [{
                    "code": "cold_storage_offline",
                    "message": "Support froid absent : sortie conservée temporairement sur le NVMe interne.",
                }],
            }
        capacity = self.ensure_space("cold", needed_gb, allow_eviction=False)
        if not capacity.get("ok"):
            return capacity
        target = self.cold_root / "outputs" / "videos"
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "tier": "cold", "path": str(target), "warnings": []}

    def migrate_final_to_cold(self, final_path: str | Path, job_id: str = "") -> dict:
        source = Path(final_path)
        if not source.exists() or source.is_symlink():
            return {"ok": False, "reason": "output_missing", "path": str(source)}
        target_info = self.ensure_output_target(source.stat().st_size / GIB)
        if not target_info.get("ok") or target_info.get("tier") != "cold":
            return target_info
        safe_job = "".join(c for c in job_id if c.isalnum() or c in "-_")[:32]
        name = f"{safe_job}_{source.name}" if safe_job else source.name
        destination = Path(target_info["path"]) / name
        if destination.exists():
            destination = destination.with_name(f"{destination.stem}_{int(time.time())}{destination.suffix}")
        try:
            self._copy_verified(source, destination)
            self._replace_with_symlink(source, destination)
        except Exception as exc:
            payload = getattr(exc, "payload", None)
            return payload or {"ok": False, "reason": "output_migration_failed", "error": str(exc)}
        return {
            "ok": True,
            "tier": "cold",
            "path": str(destination),
            "source_link": str(source),
            "warnings": [],
        }

    def gc(self, *, dry_run: bool = True, max_age_minutes: int = 180) -> dict:
        cinema_temp = self.workspace / "temp" / "cinema"
        cutoff = time.time() - max(1, int(max_age_minutes)) * 60
        candidates = []
        reclaimed = 0
        if cinema_temp.exists():
            for directory in cinema_temp.iterdir():
                if not directory.is_dir() or not directory.name.startswith(
                    ("job_", "sample_", "preview_", "benchmark_")
                ):
                    continue
                status_path = directory / "status.json"
                if not status_path.exists() or status_path.stat().st_mtime > cutoff:
                    continue
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
                except Exception:
                    continue
                if status not in {"done", "cancelled"}:
                    continue
                size = self._path_size(directory)
                candidates.append({"path": str(directory), "size_bytes": size, "status": status})
                reclaimed += size
                if not dry_run:
                    shutil.rmtree(directory)
        return {
            "ok": True,
            "dry_run": dry_run,
            "candidates": candidates,
            "reclaimed_bytes": reclaimed,
            "suggestions": [
                "Les scratchpads et modèles orphelins sont seulement signalés; utilisez purge(model_id) explicitement.",
            ],
        }

    def status(self) -> dict:
        warnings = []
        internal = self._usage_dict(self._disk_usage(str(self.internal_root)))
        key_mounted = self.cold_mounted()
        key = None
        if key_mounted:
            key = self._usage_dict(self._disk_usage(str(self.cold_root)))
        else:
            warnings.append({
                "code": "cold_storage_offline",
                "message": f"{self.cold_root} n'est pas un point de montage distinct.",
                "action": "rebrancher et monter le support AURORA_MODELS",
            })
        models = []
        for item in self.entries():
            path = item.get("cold_path") if item.get("tier") == "cold" else item.get("hot_path")
            available = bool(path and (Path(path).exists() or Path(path).is_symlink()))
            if item.get("tier") == "cold" and not key_mounted:
                available = False
            models.append({
                **item,
                "path": path,
                "available": available,
            })
        if key_mounted:
            outputs_tier = "cold"
            outputs_path = str(self.cold_root / "outputs" / "videos")
        else:
            outputs_tier = "hot"
            outputs_path = str(self.workspace / "output" / "video")
            warnings.append({
                "code": "output_fallback_internal",
                "message": "Les nouvelles sorties resteront sur le NVMe interne tant que le support froid est absent.",
            })
        return {
            "ok": True,
            "key_mounted": key_mounted,
            "mount_path": str(self.cold_root),
            "tiers": {"internal": internal, "key": key},
            "models": models,
            "outputs_tier": outputs_tier,
            "outputs_path": outputs_path,
            "floor_gb": self.floor_gb,
            "warnings": warnings,
        }


def default_manager() -> AuroraStorageManager:
    return AuroraStorageManager()
