"""
Shared cache path helpers for Aurora Python services.

These helpers force Hugging Face, Torch, rembg and related downloads to live
inside the centralised ``modele/`` directory next to the application code,
or in ``/workspace/models`` when running on a cloud pod (RunPod).
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

# Silence the RequestsDependencyWarning that fires every time a Python service
# imports transformers / diffusers. requests 2.32 is very conservative and
# complains about urllib3 >= 2.4 and chardet >= 6, but HTTP calls work fine
# against modern urllib3 / charset-normalizer — those warnings spam the bridge
# stdout for every worker subprocess and hide real errors.
#
# CRITICAL: register the module-based filter BEFORE any `from requests ...`
# import, otherwise importing requests itself fires the warning before the
# filter is live. We also register the message-based filter as a belt-and-
# braces guard for older requests builds that raise a plain UserWarning.
warnings.filterwarnings("ignore", category=Warning, module="requests")
warnings.filterwarnings("ignore", category=Warning, module=r"requests\..*")
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 \(.+\) or chardet \(.+\)/charset_normalizer \(.+\) doesn't match a supported version!.*",
)


def _default_models_root() -> str:
    """Return the default AURORA_MODELS path based on platform.

    Local Windows:  <project_root>/modele  (sibling of application/)
    RunPod pod:     /workspace/models  (only when that volume really exists+writable)
    Local Linux:    ~/.cache  → HF_HOME=~/.cache/huggingface, TORCH_HOME=~/.cache/torch,
                    i.e. the standard XDG cache where downloaded weights already live.

    NOTE: hardcoding "/workspace/models" on every Linux box was a RunPod-ism that
    (a) crashes with PermissionError on a normal desktop (can't mkdir /workspace)
    and (b) would point HuggingFace at an empty dir and re-download ~30 GB even
    though the weights are already cached under ~/.cache/huggingface.
    """
    # python-services/ is inside application/ which is a sibling of modele/
    here = Path(__file__).resolve().parent              # …/application/python-services
    project_modele = here.parent.parent / "modele"      # …/AuroraIA/modele
    if os.name == "nt":
        return str(project_modele)
    # RunPod / cloud volume — only when the mount actually exists and is writable.
    workspace = Path("/workspace")
    if workspace.is_dir() and os.access(workspace, os.W_OK):
        return "/workspace/models"
    # Local Linux desktop: use the standard user cache so HF / torch resolve to
    # their conventional locations (where the models are already downloaded).
    return str(Path.home() / ".cache")


def configure_ml_cache_environment() -> dict[str, str]:
    models_root = Path(os.environ.get("AURORA_MODELS", _default_models_root())).expanduser()

    # HuggingFace cache lives directly under models_root (no intermediate "cache" dir)
    hf_home = models_root / "huggingface"
    hub_cache = hf_home / "hub"
    transformers_cache = hf_home / "transformers"
    datasets_cache = hf_home / "datasets"
    torch_home = models_root / "torch"
    xdg_cache = models_root / "xdg"
    u2net_home = models_root / "u2net"

    for path in (
        models_root,
        hf_home,
        hub_cache,
        transformers_cache,
        datasets_cache,
        torch_home,
        xdg_cache,
        u2net_home,
    ):
        path.mkdir(parents=True, exist_ok=True)

    # TRANSFORMERS_CACHE is deprecated since transformers 4.42 — setting it
    # triggers a FutureWarning on every import of transformers. HF_HOME +
    # HF_HUB_CACHE are the current truth source and cover the same paths.
    values = {
        "AURORA_MODELS": str(models_root),
        "HF_HOME": str(hf_home),
        "HF_HUB_CACHE": str(hub_cache),
        "HUGGINGFACE_HUB_CACHE": str(hub_cache),
        "HF_DATASETS_CACHE": str(datasets_cache),
        "TORCH_HOME": str(torch_home),
        "XDG_CACHE_HOME": str(xdg_cache),
        "U2NET_HOME": str(u2net_home),
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }

    for key, value in values.items():
        os.environ.setdefault(key, value)

    # Keep transformers_cache folder on disk for legacy shards, but drop the
    # env var so the warning disappears.
    _ = transformers_cache

    # If the user previously had TRANSFORMERS_CACHE exported in their shell,
    # strip it here so the warning also stops firing in worker subprocesses.
    os.environ.pop("TRANSFORMERS_CACHE", None)

    # Patch diffusers' load_state_dict to:
    #   1. resolve Windows symlinks before handing to safetensors (some AV /
    #      indexing setups briefly lock the symlink path, triggering a spurious
    #      SafetensorError → fallback);
    #   2. when the primary safetensors call fails, inspect ONLY the first few
    #      bytes to detect a genuine git-lfs pointer (which really does start
    #      with "version https://git-lfs.github.com/spec/v1") instead of
    #      `f.read()` on a 5 GB shard, which OOMs with MemoryError on 32 GB
    #      RAM systems. This is the root cause behind the "MemoryError inside
    #      load_state_dict line 196" crashes that kill the Wan2.2 video
    #      pipeline on Windows.
    _patch_diffusers_load_state_dict_safe_fallback()

    return values


def _patch_diffusers_load_state_dict_safe_fallback() -> None:
    try:
        import diffusers.models.model_loading_utils as _mlu  # type: ignore
    except Exception:
        return
    if getattr(_mlu, "_aurora_patched_safe_fallback", False):
        return

    import safetensors.torch as _st  # type: ignore
    try:
        import torch as _torch  # type: ignore
    except Exception:
        _torch = None

    _original = _mlu.load_state_dict

    SAFETENSORS_EXT = getattr(_mlu, "SAFETENSORS_FILE_EXTENSION", "safetensors")
    GGUF_EXT = getattr(_mlu, "GGUF_FILE_EXTENSION", "gguf")

    def _safe_load_state_dict(checkpoint_file, dduf_entries=None, disable_mmap=False, map_location="cpu"):
        # dict passthrough — same as upstream
        if isinstance(checkpoint_file, dict):
            return checkpoint_file

        original_path = checkpoint_file
        # Keep the EXTENSION from the snapshot path (where the symlink lives)
        # because that is what encodes the format. If we resolved the symlink
        # first we would see hash-only filenames from HF's blob store and the
        # upstream loader would try to parse a safetensors as a pickle.
        try:
            ext_source = os.path.basename(str(original_path)).split(".")[-1].lower()
        except Exception:
            ext_source = ""

        # Resolve symlinks for the actual IO call so safetensors sees the real
        # blob and avoids Windows symlink/mmap edge cases that otherwise
        # trigger the 5 GB `f.read()` fallback MemoryError upstream.
        resolved_path = original_path
        try:
            if isinstance(original_path, (str, os.PathLike)) and os.path.islink(original_path):
                resolved_path = os.path.realpath(original_path)
        except Exception:
            resolved_path = original_path

        # Pre-flight: detect genuine git-lfs pointer files cheaply (they're
        # always under 300 bytes and start with "version https://git-lfs").
        try:
            size = os.path.getsize(resolved_path)
        except Exception:
            size = None
        if size is not None and size < 4096:
            try:
                with open(resolved_path, "rb") as _probe:
                    head = _probe.read(200)
                if head.startswith(b"version https://git-lfs"):
                    raise OSError(
                        f"Poids incomplet dans le cache HuggingFace: "
                        f"{os.path.basename(str(original_path))} n'est qu'un pointeur git-lfs. "
                        "Supprime le fichier puis relance la generation pour que "
                        "huggingface_hub retelecharge le blob reel."
                    )
            except OSError:
                raise
            except Exception:
                pass

        try:
            if ext_source == SAFETENSORS_EXT:
                if dduf_entries:
                    return _original(checkpoint_file, dduf_entries=dduf_entries,
                                     disable_mmap=disable_mmap, map_location=map_location)
                if disable_mmap:
                    with open(resolved_path, "rb") as _fh:
                        return _st.load(_fh.read())
                return _st.load_file(resolved_path, device=map_location)
            if ext_source == GGUF_EXT:
                return _original(checkpoint_file, dduf_entries=dduf_entries,
                                 disable_mmap=disable_mmap, map_location=map_location)
            # Non-safetensors: delegate to the original implementation which
            # handles pickle / zip / mmap heuristics.
            return _original(checkpoint_file, dduf_entries=dduf_entries,
                             disable_mmap=disable_mmap, map_location=map_location)
        except OSError:
            raise
        except Exception as primary_exc:
            # Deeply defensive fallback: read a TINY window to decide whether
            # the file is an LFS pointer vs. a real binary. Never read the full
            # file — that's the 5 GB MemoryError upstream.
            try:
                with open(resolved_path, "rb") as _probe:
                    head = _probe.read(200)
            except Exception:
                head = b""
            if head.startswith(b"version https://git-lfs"):
                raise OSError(
                    f"Poids incomplet dans le cache HuggingFace: "
                    f"{os.path.basename(str(original_path))} n'est qu'un pointeur git-lfs "
                    "(download interrompu). Supprime le fichier puis relance pour qu'il soit "
                    "retelecharge."
                ) from primary_exc
            raise OSError(
                f"Impossible de charger les poids depuis "
                f"'{os.path.basename(str(original_path))}': "
                f"{type(primary_exc).__name__}: {str(primary_exc)[:300]}"
            ) from primary_exc

    _mlu.load_state_dict = _safe_load_state_dict
    _mlu._aurora_patched_safe_fallback = True
