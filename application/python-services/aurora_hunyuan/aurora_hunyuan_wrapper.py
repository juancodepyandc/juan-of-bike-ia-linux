#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AuroraIA Hunyuan3D-2 Native Engine Wrapper with UHD PBR Remastering.

Provides first-class Image-to-3D generation using Tencent Hunyuan3D-2:
- Hunyuan3DDiTFlowMatchingPipeline for high-resolution volumetric/relief shape generation
- Intelligent Quadric Decimation (100k faces) preserving sharp boundaries and topology
- Hunyuan3DPaintPipeline for photorealistic surface texturing and PBR painting
- UHD Texture Remastering: Gamma & shadow lift, micro-contrast enhancement, 4K upscale,
  and optimal PBR material settings (roughness 0.45, metallic 0.20) for crystal clear
  rendering in f3d, Blender, Three.js, and all GLTF viewers.

Usage CLI:
    python aurora_hunyuan_wrapper.py <input_image> <output_glb> [--octree 512] [--steps 30] [--no-paint]
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import logging
import os
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("hunyuan3d_wrapper")


def _free_vram():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass


def is_available() -> bool:
    try:
        import torch
        import hy3dgen
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dgen.texgen import Hunyuan3DPaintPipeline
        return torch.cuda.is_available()
    except Exception:
        return False


def souder_doublons(mesh):
    """Refusionne les sommets reellement superposes, avant que le paint ne deplie.

    A placer imperativement AVANT le depliage (mesh_uv_wrap): un deplieur dedouble
    les sommets le long de ses coutures, et fusionner apres coup recollerait ces
    coutures — ce qui detruirait la texture au lieu de la reparer. Ici le maillage
    sort du Marching Cubes et n'a pas encore d'UV: la fusion est sans risque.

    L'etape se neutralise seule quand il n'y a rien a fusionner, et journalise ses
    comptes: c'est ce qui permet de savoir si ce generateur produit ou non des
    sommets dupliques, au lieu de le supposer.
    """
    import trimesh as tm

    sommets = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if len(sommets) == 0 or len(faces) == 0:
        return mesh
    diagonale = float(np.linalg.norm(sommets.max(axis=0) - sommets.min(axis=0)))
    if diagonale <= 0:
        return mesh
    # Tolerance RELATIVE a la taille du sujet: la meme regle vaut pour une
    # figurine et pour un batiment, sans seuil metrique a maintenir.
    grille = np.round(sommets / (diagonale * 1e-6)).astype(np.int64)
    _, correspondance = np.unique(grille, axis=0, return_inverse=True)
    nb = int(correspondance.max()) + 1
    if nb >= len(sommets):
        return mesh

    fusionnes = np.zeros((nb, 3), dtype=np.float64)
    np.add.at(fusionnes, correspondance, sommets)
    fusionnes /= np.bincount(correspondance, minlength=nb)[:, None]
    nouvelles = correspondance[faces]
    # Une face dont deux coins se rejoignent n'a plus d'aire: elle disparait.
    vivantes = ((nouvelles[:, 0] != nouvelles[:, 1])
                & (nouvelles[:, 1] != nouvelles[:, 2])
                & (nouvelles[:, 0] != nouvelles[:, 2]))
    soude = tm.Trimesh(vertices=fusionnes, faces=nouvelles[vivantes], process=False)
    log.info(f"[Hunyuan3D-2] Soudure: {len(sommets)} -> {nb} sommets, "
             f"{len(faces)} -> {len(soude.faces)} faces")
    return soude


def decimate_mesh_for_paint(mesh, target_faces: int = 100000):
    """Simplify raw volumetric mesh to target face count for fast UV unwrapping and baking."""
    if len(mesh.faces) <= target_faces * 1.05:
        return mesh
    log.info(f"[Hunyuan3D-2] Simplifying mesh from {len(mesh.faces)} to ~{target_faces} faces...")
    t0 = time.time()
    try:
        import pymeshlab
        import trimesh as tm
        ms = pymeshlab.MeshSet()
        ms.add_mesh(pymeshlab.Mesh(
            vertex_matrix=np.asarray(mesh.vertices),
            face_matrix=np.asarray(mesh.faces),
        ))
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target_faces,
            preserveboundary=True,
            preservenormal=True,
            preservetopology=True,
            optimalplacement=True,
            planarquadric=True,
            qualitythr=0.4,
        )
        m2 = ms.current_mesh()
        out = tm.Trimesh(
            vertices=m2.vertex_matrix(),
            faces=m2.face_matrix(),
            process=False,
        )
        log.info(f"[Hunyuan3D-2] Decimated to {len(out.faces)} faces in {time.time() - t0:.2f}s")
        return out
    except Exception as exc:
        log.warning(f"[Hunyuan3D-2] pymeshlab decimation fallback: {exc}")
        return mesh


def remaster_pbr_glb(glb_path: str | Path, image_ref_path: str | Path = None, target_texture_size: int = 4096):
    """Post-process GLB to enhance PBR materials, lift dark shadows, and boost texture clarity."""
    try:
        import pygltflib
        glb_path = Path(glb_path)
        if not glb_path.is_file():
            return
        
        glb = pygltflib.GLTF2().load(str(glb_path))
        
        # 1. PBR Material Calibration (prevents dark crushing in f3d / OpenGL viewers)
        for mat in glb.materials:
            if mat.pbrMetallicRoughness:
                mat.pbrMetallicRoughness.roughnessFactor = 0.45
                mat.pbrMetallicRoughness.metallicFactor = 0.20
                mat.pbrMetallicRoughness.baseColorFactor = [1.0, 1.0, 1.0, 1.0]

        # 2. Texture Remastering (Dynamic Range, Gamma, Micro-contrast & 4K Lanczos upscale)
        for img_meta in glb.images:
            if img_meta.bufferView is not None:
                bv = glb.bufferViews[img_meta.bufferView]
                buf = glb.buffers[bv.buffer]
                img_bytes = glb.get_data_from_buffer_uri(buf.uri)[bv.byteOffset:bv.byteOffset + bv.byteLength]
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                
                r, g, b, a = pil_img.split()
                rgb = Image.merge("RGB", (r, g, b))
                
                # Non-linear gamma lift for dark tones + shadow preservation
                arr = np.array(rgb, dtype=np.float32) / 255.0
                arr = np.power(arr, 0.82) * 1.30
                arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
                boosted = Image.fromarray(arr)
                boosted = ImageEnhance.Contrast(boosted).enhance(1.20)
                boosted = ImageEnhance.Color(boosted).enhance(1.25)
                boosted = ImageEnhance.Sharpness(boosted).enhance(1.50)
                
                if boosted.width < target_texture_size:
                    boosted = boosted.resize((target_texture_size, target_texture_size), Image.Resampling.LANCZOS)
                    a = a.resize((target_texture_size, target_texture_size), Image.Resampling.LANCZOS)
                
                boosted.putalpha(a)
                out_bytes = io.BytesIO()
                boosted.save(out_bytes, format="PNG")
                
                img_meta.uri = None
                img_meta.mimeType = "image/png"

        glb.save_binary(str(glb_path))
        log.info(f"[Hunyuan3D-2] Remastered UHD PBR texture & lighting saved to {glb_path.name}")
    except Exception as e:
        log.warning(f"[Hunyuan3D-2] Remastering warning: {e}")


def generate_glb(
    image_path: str | Path,
    out_glb_path: str | Path,
    *,
    model_id: str = "tencent/Hunyuan3D-2",
    octree_resolution: int = 512,
    num_inference_steps: int = 30,
    guidance_scale: float = 5.5,
    target_faces: int = 100000,
    do_paint: bool = True,
    texture_size: int = 2048,
    render_size: int = 2048,
    device: str = "cuda",
) -> dict:
    """Generate a high-fidelity 3D GLB model from a single 2D image via Hunyuan3D-2."""
    image_path = Path(image_path)
    out_glb_path = Path(out_glb_path)
    out_glb_path.parent.mkdir(parents=True, exist_ok=True)

    if not image_path.is_file():
        return {"ok": False, "error": f"Input image not found: {image_path}"}

    import torch
    import trimesh
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    _free_vram()
    start_t = time.time()
    dtype = torch.float16 if device == "cuda" else torch.float32

    log.info(f"[Hunyuan3D-2] Stage 1/2: Loading shape pipeline ({model_id}) on {device}")
    try:
        shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            model_id,
            device=device,
            dtype=dtype,
        )

        img = Image.open(image_path).convert("RGBA")
        
        log.info(f"[Hunyuan3D-2] Stage 1/2: Generating 3D shape (octree={octree_resolution}, steps={num_inference_steps})...")
        shape_t0 = time.time()
        mesh = shape_pipe(
            image=img,
            octree_resolution=octree_resolution,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
        )[0]
        shape_elapsed = time.time() - shape_t0
        log.info(f"[Hunyuan3D-2] Shape generated in {shape_elapsed:.1f}s — raw {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

        del shape_pipe
        _free_vram()

        if do_paint:
            mesh = souder_doublons(mesh)
            mesh = decimate_mesh_for_paint(mesh, target_faces=target_faces)
            
            # Export raw unpainted geometry for paint_pbr_v21
            temp_white = out_glb_path.parent / f"{out_glb_path.stem}_white.obj"
            mesh.export(str(temp_white))
            
            pbr_ok = False
            try:
                ps_dir = Path(__file__).resolve().parent.parent
                if str(ps_dir) not in sys.path:
                    sys.path.insert(0, str(ps_dir))
                import paint_pbr_v21 as _pbr_v21
                if _pbr_v21.is_available():
                    log.info("[Hunyuan3D-2] Stage 2/2: Painting mesh with hy3dpaint PBR 2.1...")
                    pbr_res = _pbr_v21.paint_pbr_v21(
                        str(temp_white),
                        str(image_path),
                        str(out_glb_path),
                        work_dir=str(out_glb_path.parent / "_hy3d_pbr_tmp"),
                        max_num_view=4,
                        resolution=512,
                        log=log.info,
                    )
                    if pbr_res.get("ok") and out_glb_path.is_file():
                        pbr_ok = True
                        log.info("[Hunyuan3D-2] hy3dpaint PBR 2.1 successful!")
            except Exception as _pbr_err:
                log.warning(f"[Hunyuan3D-2] hy3dpaint PBR failed: {_pbr_err!r}")
            
            if not pbr_ok:
                try:
                    from hy3dgen.texgen import Hunyuan3DPaintPipeline
                    log.info(f"[Hunyuan3D-2] Stage 2/2: Fallback to Hunyuan3DPaintPipeline...")
                    paint_pipe = Hunyuan3DPaintPipeline.from_pretrained(model_id)
                    mesh = paint_pipe(mesh, image=img)
                    mesh.export(str(out_glb_path))
                    del paint_pipe
                    _free_vram()
                except Exception as _fbe:
                    log.warning(f"[Hunyuan3D-2] Fallback paint also failed: {_fbe!r}, saving raw mesh")
                    mesh.export(str(out_glb_path))
            
            try:
                temp_white.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            mesh.export(str(out_glb_path))
        
        # Apply UHD Texture Remastering & PBR calibration
        if do_paint and out_glb_path.is_file():
            # Apply final PBR calibration & gamma/lighting boost
            remaster_pbr_glb(out_glb_path, image_ref_path=image_path, target_texture_size=4096)

        total_elapsed = time.time() - start_t
        file_size = out_glb_path.stat().st_size if out_glb_path.is_file() else 0

        res = {
            "ok": True,
            "engine": "Hunyuan3D-2",
            "out_glb": str(out_glb_path),
            "verts": len(mesh.vertices),
            "faces": len(mesh.faces),
            "size_bytes": file_size,
            "elapsed_s": round(total_elapsed, 2),
        }
        return res

    except Exception as exc:
        log.exception(f"[Hunyuan3D-2] Generation error: {exc}")
        _free_vram()
        return {"ok": False, "engine": "Hunyuan3D-2", "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="Hunyuan3D-2 Image to 3D Standalone CLI")
    parser.add_argument("input_image", help="Path to reference image")
    parser.add_argument("output_glb", help="Path to output GLB")
    parser.add_argument("--model-id", default="tencent/Hunyuan3D-2", help="HuggingFace model ID")
    parser.add_argument("--octree", type=int, default=512, help="Octree resolution")
    parser.add_argument("--steps", type=int, default=30, help="Inference steps")
    parser.add_argument("--guidance", type=float, default=5.5, help="Guidance scale")
    parser.add_argument("--faces", type=int, default=100000, help="Target faces for texturing")
    parser.add_argument("--no-paint", action="store_true", help="Skip PBR paint pass")
    parser.add_argument("--texture-size", type=int, default=2048, help="Texture size")
    parser.add_argument("--device", default="cuda", help="Execution device (cuda/cpu)")

    args = parser.parse_args()

    result = generate_glb(
        image_path=args.input_image,
        out_glb_path=args.output_glb,
        model_id=args.model_id,
        octree_resolution=args.octree,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        target_faces=args.faces,
        do_paint=not args.no_paint,
        texture_size=args.texture_size,
        device=args.device,
    )

    print("AURORA_HUNYUAN_RESULT:" + json.dumps(result))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
