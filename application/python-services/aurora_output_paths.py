"""Centralized output path coordinator for Aurora Python services.

Architecture Contract:
Every module MUST place its outputs, assets, and project files under:
    application/output/<module_name>/<project_name>/...

Canonical Module Directory Mapping:
  - '3d'      -> application/output/3d/<project_name>/
  - 'code'    -> application/output/code/<project_name>/
  - 'video'   -> application/output/video/<project_name>/
  - 'image'   -> application/output/image/<project_name>/
  - 'voix'    -> application/output/voix/<project_name>/
  - 'cyber'   -> application/output/cyber/<project_name>/
  - 'context' -> application/output/context/<project_name>/
  - 'cowork'  -> application/output/cowork/<project_name>/ (or custom user-selected path)
  - 'manga'   -> application/output/manga/<project_name>/
  - 'academy' -> application/output/academy/<project_name>/

Nothing should ever be scattered at the root of output/ or dumped in random temporary dirs.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

# Canonical module names
CANONICAL_MODULES = {
    "3d": "3d",
    "three_d": "3d",
    "threed": "3d",
    "code": "code",
    "coding": "code",
    "coder": "code",
    "video": "video",
    "cinema": "video",
    "film": "video",
    "image": "image",
    "images": "image",
    "img": "image",
    "voix": "voix",
    "voice": "voix",
    "audio": "voix",
    "tts": "voix",
    "cyber": "cyber",
    "security": "cyber",
    "context": "context",
    "ent": "context",
    "cowork": "cowork",
    "manga": "manga",
    "academy": "academy",
}


def sanitize_slug(name: str, maxlen: int = 64) -> str:
    """Sanitize project or folder name for clean filesystem path."""
    if not name:
        return "projet"
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower()
    return slug[:maxlen].rstrip("-") or "projet"


def get_workspace_root() -> Path:
    """Return the application root directory (contains output/, python-services/, src/)."""
    # python-services/ is inside application/
    return Path(__file__).resolve().parents[1]


def get_output_root() -> Path:
    """Return the canonical application/output directory."""
    root = get_workspace_root() / "output"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_module_output_dir(
    module: str,
    project_name: str | None = None,
    subfolder: str | None = None,
    create: bool = True,
) -> Path:
    """Get the standard output directory for a given module and project.
    
    Structure:
      application/output/<module>/<project_name>/[<subfolder>]
    """
    canonical_mod = CANONICAL_MODULES.get(module.lower(), sanitize_slug(module))
    output_root = get_output_root()
    target = output_root / canonical_mod
    
    if project_name:
        safe_proj = sanitize_slug(project_name)
        target = target / safe_proj
        
    if subfolder:
        safe_sub = sanitize_slug(subfolder)
        target = target / safe_sub
        
    if create:
        target.mkdir(parents=True, exist_ok=True)
        
    return target


def get_code_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a code project."""
    return get_module_output_dir("code", project_name=project_name, create=create)


def get_code_assets_dir(project_name: str | None = None, run_id: str | None = None, create: bool = True) -> Path:
    """Get output directory for code-generated assets (images, audio, 3D models)."""
    if project_name:
        target = get_module_output_dir("code", project_name=project_name, subfolder="assets", create=create)
    elif run_id:
        target = get_module_output_dir("code", project_name="assets", subfolder=run_id, create=create)
    else:
        target = get_module_output_dir("code", project_name="assets", create=create)
    return target


def get_code_apk_dir(project_name: str | None = None, create: bool = True) -> Path:
    """Get output directory for code-generated APK packages."""
    if project_name:
        target = get_module_output_dir("code", project_name=project_name, subfolder="apk", create=create)
    else:
        target = get_module_output_dir("code", project_name="apk", create=create)
    return target


def get_code_sandbox_dir(sandbox_id: str | None = None, create: bool = True) -> Path:
    """Get output directory for code sandboxes."""
    if sandbox_id:
        target = get_module_output_dir("code", project_name="sandbox", subfolder=sandbox_id, create=create)
    else:
        target = get_module_output_dir("code", project_name="sandbox", create=create)
    return target


def get_3d_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a 3D model project."""
    return get_module_output_dir("3d", project_name=project_name, create=create)


def get_video_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a video/cinema project."""
    return get_module_output_dir("video", project_name=project_name, create=create)


def get_image_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for an image project."""
    return get_module_output_dir("image", project_name=project_name, create=create)


def get_voice_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a voice/audio project."""
    return get_module_output_dir("voix", project_name=project_name, create=create)


def get_cyber_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a cyber project."""
    return get_module_output_dir("cyber", project_name=project_name, create=create)


def get_cowork_project_dir(project_name: str, custom_path: str | None = None, create: bool = True) -> Path:
    """Get output directory for a cowork project.
    
    If custom_path is provided (user explicitly specified where to write),
    respects that path inside the workspace.
    """
    if custom_path:
        p = Path(custom_path)
        if not p.is_absolute():
            p = get_workspace_root() / p
        if create:
            p.mkdir(parents=True, exist_ok=True)
        return p
    return get_module_output_dir("cowork", project_name=project_name, create=create)


def get_context_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a context project."""
    return get_module_output_dir("context", project_name=project_name, create=create)


def get_manga_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for a manga project."""
    return get_module_output_dir("manga", project_name=project_name, create=create)


def get_academy_project_dir(project_name: str, create: bool = True) -> Path:
    """Get output directory for an academy project."""
    return get_module_output_dir("academy", project_name=project_name, create=create)
