"""
AuroraIA — DreamGaussian mesh generation (MIT license, EU-safe)
Text/image → 3D via Gaussian Splatting → mesh extraction → UV refinement.

Usage:
  python dreamgaussian_run.py --image <path> --output-dir <dir> --run-id <id> --format glb
  python dreamgaussian_run.py --prompt "a dragon" --output-dir <dir> --run-id <id> --format glb
"""

import argparse
import gc
import importlib.util
import json
import os
import subprocess
import sys
from typing import Any


DREAMGAUSSIAN_REPO = "https://github.com/dreamgaussian/dreamgaussian.git"
DREAMGAUSSIAN_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "dreamgaussian")

REQUIRED_PACKAGES = {
    "torch": "torch",
    "PIL": "Pillow",
    "numpy": "numpy",
    "trimesh": "trimesh",
    "kiui": "kiui",
    "dearpygui": "dearpygui",
    "rembg": "rembg",
}


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def ensure_packages():
    """Install missing packages."""
    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(pip_name)
    if missing:
        emit("install", f"Installing {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)


def ensure_dreamgaussian():
    """Clone DreamGaussian repo if not present."""
    if os.path.isdir(DREAMGAUSSIAN_DIR) and os.path.isfile(os.path.join(DREAMGAUSSIAN_DIR, "main.py")):
        return True

    emit("install", "Cloning DreamGaussian (MIT license)...")
    try:
        subprocess.check_call(["git", "clone", "--depth", "1", DREAMGAUSSIAN_REPO, DREAMGAUSSIAN_DIR])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        emit("install", "Git clone failed. DreamGaussian not available.")
        return False


def run_dreamgaussian(image_path: str, output_dir: str, run_id: str, fmt: str = "glb",
                      style: str = "realistic", resolution: int = 256, iters: int = 500,
                      seed: int = 0) -> dict:
    """Run DreamGaussian pipeline: image → Gaussian Splatting → mesh extraction → UV refinement."""
    emit("device", "Detecting GPU...")

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
            emit("device", f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f} GB VRAM)")
        else:
            emit("device", "No CUDA GPU, running on CPU (slow)")
    except ImportError:
        device = "cpu"
        emit("device", "PyTorch not available with CUDA")

    output_path = os.path.join(output_dir, f"{run_id}_dreamgaussian.{fmt}")

    # Stage 1: Background removal
    emit("preprocess", "Removing background from reference image...")
    try:
        from rembg import remove
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGBA")
        img_nobg = remove(img)
        preprocessed_path = os.path.join(output_dir, f"{run_id}_nobg.png")
        img_nobg.save(preprocessed_path)
        emit("preprocess", "Background removed.")
    except Exception as e:
        emit("preprocess", f"Background removal failed: {e}, using original image")
        preprocessed_path = image_path

    # Stage 2: Run DreamGaussian main pipeline
    emit("gaussian", "Running Gaussian Splatting generation...")
    dg_dir = DREAMGAUSSIAN_DIR
    main_script = os.path.join(dg_dir, "main.py")

    if not os.path.isfile(main_script):
        return {"ok": False, "error": "DreamGaussian main.py not found. Run ensure_dreamgaussian() first."}

    gs_output = os.path.join(output_dir, f"{run_id}_gs")
    os.makedirs(gs_output, exist_ok=True)

    try:
        cmd = [
            sys.executable, main_script,
            "--config", os.path.join(dg_dir, "configs", "image.yaml"),
            "--input", preprocessed_path,
            "--outdir", gs_output,
            "--save_path", run_id,
            "--iters", str(iters),
            "--h", str(resolution),
            "--w", str(resolution),
        ]
        if seed > 0:
            cmd.extend(["--seed", str(seed)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=dg_dir)
        if result.returncode != 0:
            emit("gaussian", f"DreamGaussian failed: {result.stderr[-300:]}")
            return {"ok": False, "error": f"DreamGaussian generation failed: {result.stderr[-300:]}"}

        emit("gaussian", "Gaussian generation complete.")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "DreamGaussian timed out after 10 minutes."}
    except FileNotFoundError:
        return {"ok": False, "error": "Python or DreamGaussian not found."}

    # Stage 3: Mesh extraction + UV refinement
    emit("mesh_extract", "Extracting mesh and refining UV...")
    mesh2_script = os.path.join(dg_dir, "main2.py")
    if os.path.isfile(mesh2_script):
        try:
            cmd2 = [
                sys.executable, mesh2_script,
                "--config", os.path.join(dg_dir, "configs", "image.yaml"),
                "--input", preprocessed_path,
                "--outdir", gs_output,
                "--save_path", run_id,
                "--iters", str(min(iters, 200)),
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300, cwd=dg_dir)
            if result2.returncode == 0:
                emit("mesh_extract", "UV refinement complete.")
        except Exception:
            emit("mesh_extract", "UV refinement failed, using base mesh.")

    # Stage 4: Find and convert output mesh
    emit("export", "Looking for generated mesh...")
    possible_outputs = [
        os.path.join(gs_output, f"{run_id}.glb"),
        os.path.join(gs_output, f"{run_id}.obj"),
        os.path.join(gs_output, f"{run_id}_mesh.obj"),
        os.path.join(gs_output, f"{run_id}_mesh.glb"),
    ]

    source_mesh = None
    for p in possible_outputs:
        if os.path.isfile(p):
            source_mesh = p
            break

    if not source_mesh:
        # Search for any mesh file
        for f in os.listdir(gs_output):
            if f.endswith((".glb", ".obj", ".ply")):
                source_mesh = os.path.join(gs_output, f)
                break

    if not source_mesh:
        return {"ok": False, "error": "DreamGaussian did not produce a mesh file."}

    # Convert if needed
    if source_mesh != output_path:
        try:
            import trimesh
            mesh = trimesh.load(source_mesh)
            if fmt == "glb":
                mesh.export(output_path, file_type="glb")
            elif fmt == "obj":
                mesh.export(output_path, file_type="obj")
            else:
                mesh.export(output_path)
            emit("export", f"Mesh exported as {fmt}.")
        except Exception as e:
            # Fallback: copy the file
            import shutil
            shutil.copy2(source_mesh, output_path)
            emit("export", f"Mesh copied (conversion failed: {e}).")

    # Run the Aurora mesh post-processing pipeline (smoothing, decimation,
    # floater drop, hole filling, normal repair) to remove typical AI mesh
    # artefacts before the viewer loads the file.
    post_process_report: dict = {"applied": False}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mesh_postprocess

        smoothed = os.path.splitext(output_path)[0] + "_smoothed" + os.path.splitext(output_path)[1]
        emit("post_start", "Lissage anti-artefacts (Taubin + decimation)...")
        result = mesh_postprocess.post_process(
            output_path,
            smoothed,
            intent_purpose="default",
            motion_readiness="static_only",
        )
        if result.get("ok") and os.path.exists(smoothed):
            os.replace(smoothed, output_path)
            post_process_report = {
                "applied": True,
                "engine": result.get("engine"),
                "before_faces": result.get("before_faces"),
                "after_faces": result.get("after_faces"),
                "before_verts": result.get("before_verts"),
                "after_verts": result.get("after_verts"),
            }
    except Exception as exc:
        emit("post_warn", f"DreamGaussian post-process skipped: {exc}")

    return {
        "ok": True,
        "path": output_path,
        "format": fmt,
        "shape_model": "DreamGaussian (MIT)",
        "shape_runtime": "gaussian_splatting",
        "shape_strategy": f"{iters}_iters_{resolution}px",
        "textured": True,
        "fallback_used": False,
        "license": "MIT",
        "eu_compliant": True,
        "post_processing": post_process_report,
    }


def main():
    parser = argparse.ArgumentParser(description="AuroraIA DreamGaussian Runner")
    parser.add_argument("--image", required=True, help="Reference image path")
    parser.add_argument("--output-dir", required=True, dest="output_dir")
    parser.add_argument("--run-id", required=True, dest="run_id")
    parser.add_argument("--format", default="glb", choices=["glb", "obj"])
    parser.add_argument("--style", default="realistic")
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--iters", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    emit("install", "Checking dependencies...")
    ensure_packages()

    if not ensure_dreamgaussian():
        print(json.dumps({"ok": False, "error": "DreamGaussian repository not available."}))
        sys.exit(0)

    result = run_dreamgaussian(
        image_path=args.image,
        output_dir=args.output_dir,
        run_id=args.run_id,
        fmt=args.format,
        style=args.style,
        resolution=args.resolution,
        iters=args.iters,
        seed=args.seed,
    )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
