"""
AuroraIA — Meshroom photogrammetry pipeline (MPL-2.0 license, EU-safe)
Multi-view photos → SfM/MVS → textured mesh via AliceVision/Meshroom.

Usage:
  python meshroom_run.py --images <dir_or_files> --output-dir <dir> --run-id <id> --format glb
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


MESHROOM_BIN = None  # Will be auto-detected


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def find_meshroom() -> str | None:
    """Find Meshroom executable."""
    candidates = [
        shutil.which("meshroom_photogrammetry"),
        shutil.which("meshroom_batch"),
        # Windows common paths
        r"C:\Program Files\Meshroom\meshroom_photogrammetry.exe",
        r"C:\Program Files\AliceVision\meshroom_photogrammetry.exe",
        os.path.expanduser(r"~\Meshroom\meshroom_photogrammetry.exe"),
        # Linux
        "/usr/bin/meshroom_photogrammetry",
        "/opt/meshroom/meshroom_photogrammetry",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def find_images(path_or_glob: str) -> list[str]:
    """Find all image files from a path (directory or glob pattern)."""
    images = []
    extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}

    if os.path.isdir(path_or_glob):
        for f in os.listdir(path_or_glob):
            if os.path.splitext(f)[1].lower() in extensions:
                images.append(os.path.join(path_or_glob, f))
    else:
        # Glob pattern or single file
        matched = glob.glob(path_or_glob)
        for f in matched:
            if os.path.splitext(f)[1].lower() in extensions:
                images.append(f)

    return sorted(images)


def run_meshroom(images: list[str], output_dir: str, run_id: str, fmt: str = "glb",
                 quality: str = "normal") -> dict:
    """Run Meshroom photogrammetry pipeline."""
    meshroom = find_meshroom()
    if not meshroom:
        return {"ok": False, "error": "Meshroom not found. Install Meshroom 2025.1.0+ from https://alicevision.org/"}

    if len(images) < 3:
        return {"ok": False, "error": f"Photogrammetry needs at least 3 images, got {len(images)}."}

    emit("photogrammetry", f"Starting Meshroom with {len(images)} images...")

    # Create input directory
    input_dir = os.path.join(output_dir, f"{run_id}_input")
    meshroom_output = os.path.join(output_dir, f"{run_id}_meshroom")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(meshroom_output, exist_ok=True)

    # Symlink or copy images to input dir
    for i, img in enumerate(images):
        ext = os.path.splitext(img)[1]
        dst = os.path.join(input_dir, f"view_{i:04d}{ext}")
        if not os.path.exists(dst):
            shutil.copy2(img, dst)

    # Run Meshroom pipeline
    emit("sfm", "Structure from Motion (feature extraction + matching)...")
    try:
        cmd = [
            meshroom,
            "--input", input_dir,
            "--output", meshroom_output,
        ]

        # Quality presets
        if quality == "draft":
            cmd.extend(["--paramOverrides", "DepthMap:downscale=4"])
        elif quality == "high":
            cmd.extend(["--paramOverrides", "DepthMap:downscale=1"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if result.returncode != 0:
            emit("sfm", f"Meshroom failed: {result.stderr[-500:]}")
            return {"ok": False, "error": f"Meshroom pipeline failed: {result.stderr[-500:]}"}

        emit("sfm", "Meshroom pipeline complete.")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Meshroom timed out after 60 minutes."}
    except FileNotFoundError:
        return {"ok": False, "error": f"Meshroom binary not found at {meshroom}"}

    # Find output mesh
    emit("export", "Looking for reconstructed mesh...")
    mesh_candidates = []
    for root, dirs, files in os.walk(meshroom_output):
        for f in files:
            if f.endswith((".obj", ".ply", ".abc")):
                mesh_candidates.append(os.path.join(root, f))

    if not mesh_candidates:
        return {"ok": False, "error": "Meshroom did not produce a mesh file."}

    source_mesh = mesh_candidates[0]
    output_path = os.path.join(output_dir, f"{run_id}_photogrammetry.{fmt}")

    # Convert to requested format
    emit("export", f"Converting mesh to {fmt}...")
    try:
        import trimesh
        mesh = trimesh.load(source_mesh)
        if fmt == "glb":
            mesh.export(output_path, file_type="glb")
        elif fmt == "obj":
            mesh.export(output_path, file_type="obj")
        else:
            mesh.export(output_path)
        emit("export", f"Mesh exported: {mesh.vertices.shape[0]} vertices, {mesh.faces.shape[0]} faces")
        vertex_count = int(mesh.vertices.shape[0])
        face_count = int(mesh.faces.shape[0])
    except ImportError:
        # Fallback: copy raw output
        shutil.copy2(source_mesh, output_path)
        vertex_count = 0
        face_count = 0
        emit("export", "Trimesh not available, copied raw mesh.")
    except Exception as e:
        shutil.copy2(source_mesh, output_path)
        vertex_count = 0
        face_count = 0
        emit("export", f"Conversion failed ({e}), copied raw mesh.")

    # Look for textures
    texture_files = []
    for root, dirs, files in os.walk(meshroom_output):
        for f in files:
            if f.endswith((".png", ".jpg", ".jpeg", ".exr")) and "texture" in f.lower():
                texture_files.append(os.path.join(root, f))

    return {
        "ok": True,
        "path": output_path,
        "format": fmt,
        "shape_model": "Meshroom/AliceVision",
        "shape_runtime": "photogrammetry",
        "shape_strategy": f"{quality}_{len(images)}_views",
        "textured": len(texture_files) > 0,
        "texture_files": texture_files[:5],
        "vertex_count": vertex_count,
        "face_count": face_count,
        "image_count": len(images),
        "fallback_used": False,
        "license": "MPL-2.0",
        "eu_compliant": True,
    }


def main():
    parser = argparse.ArgumentParser(description="AuroraIA Meshroom Photogrammetry Runner")
    parser.add_argument("--images", required=True, help="Directory of images or glob pattern")
    parser.add_argument("--output-dir", required=True, dest="output_dir")
    parser.add_argument("--run-id", required=True, dest="run_id")
    parser.add_argument("--format", default="glb", choices=["glb", "obj"])
    parser.add_argument("--quality", default="normal", choices=["draft", "normal", "high"])

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    images = find_images(args.images)
    emit("scan", f"Found {len(images)} images.")

    if len(images) < 3:
        print(json.dumps({"ok": False, "error": f"Need at least 3 images for photogrammetry, found {len(images)}."}))
        sys.exit(0)

    result = run_meshroom(
        images=images,
        output_dir=args.output_dir,
        run_id=args.run_id,
        fmt=args.format,
        quality=args.quality,
    )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
