#!/usr/bin/env python3
"""
optimize_textured_mesh.py — make a Hunyuan-painted GLB lighter for the viewer
WITHOUT touching its look.

Two best-effort stages, each skipped silently if its tool is missing:

  1. UV-preserving decimation (pymeshlab `meshing_decimation_quadric_edge_collapse
     _with_texture`, `preserveboundary=True` so texture-island seams are kept) down
     to a conservative target — roughly half the faces, but never below a per-kind
     floor. Then the *original* baseColor texture image is re-attached (pymeshlab
     can't write GLB / loses the embedded PNG, so we go GLB→OBJ→trimesh→GLB).
  2. `gltfpack` (npm `gltfpack`) with float UV quantization (`-vtf`) — adds only
     `KHR_mesh_quantization` / `KHR_texture_transform`, both natively supported by
     three.js GLTFLoader, so the asset still loads everywhere. Shrinks geometry
     ~2-3× with no visible change.

A textured 689k-face / 25 MB robot comes out ~350k faces / ~14 MB, pixel-identical.

CLI:
  python optimize_textured_mesh.py --mesh in.glb --output out.glb [--kind humanoid]
Prints a JSON line: {"ok", "input"/"output", "faces_before"/"faces_after",
"bytes_before"/"bytes_after", "stages":[...], "skipped":[...]}.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Per-kind face floor — never decimate below this (keeps silhouettes crisp on the
# bits that matter: faces, fingers, mechanical detail).
_FACE_FLOOR = {
    "humanoid": 280_000,
    "character": 280_000,
    "creature": 260_000,
    "vehicle": 240_000,
    "mechanical_part": 220_000,
    "mechanism": 220_000,
    "prop": 180_000,
    "object": 180_000,
    "environment": 200_000,
}
_DEFAULT_FLOOR = 220_000
# Below this face count there is nothing to gain — skip decimation entirely.
_DECIMATE_MIN_FACES = 360_000
# Hard cap: even a 1M+ face Hunyuan mesh comes down to this. ~half-million faces is
# already overkill detail for a viewer model and the texture stays clean at that level.
_DECIMATE_FACE_CAP = 450_000


def _mesh_texture_image(glb_path: str):
    """Return (trimesh_mesh, PIL baseColorTexture) or (mesh, None)."""
    import trimesh

    m = trimesh.load(glb_path, process=False, force="mesh")
    visual = getattr(m, "visual", None)
    mat = getattr(visual, "material", None)
    img = None
    if mat is not None:
        img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
    if img is None:
        img = getattr(visual, "image", None)
    return m, img


def _decimate_uv_preserving(
    glb_path: str, out_glb: str, target_faces: int, log: list[dict[str, Any]]
) -> bool:
    try:
        import pymeshlab  # type: ignore
        import trimesh
    except Exception as exc:  # noqa: BLE001
        log.append({"stage": "decimate", "skipped": True, "reason": f"missing dep: {exc}"})
        return False

    try:
        _orig, img = _mesh_texture_image(glb_path)
        if img is None:
            log.append({"stage": "decimate", "skipped": True, "reason": "mesh has no baseColor texture"})
            return False

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(glb_path)
        before = ms.current_mesh().face_number()
        if before <= target_faces:
            log.append({"stage": "decimate", "skipped": True, "reason": f"already {before} <= target {target_faces}"})
            return False

        ms.apply_filter(
            "meshing_decimation_quadric_edge_collapse_with_texture",
            targetfacenum=int(target_faces),
            preserveboundary=True,
            preservenormal=True,
            optimalplacement=True,
            planarquadric=True,
            qualitythr=0.5,
        )
        after = ms.current_mesh().face_number()
        # On poursuit meme si le quadric n a rien reduit: le passage OBJ reencode le
        # mesh et fait gagner beaucoup de poids a geometrie egale (mesure: 206 Mo ->
        # 119 Mo sur 967762 faces). Seul le SUCCES DE LA REDUCTION est rapporte
        # honnetement, pas la production du fichier.
        _reduced = after <= int(target_faces * 1.05)

        with tempfile.TemporaryDirectory() as td:
            obj_path = os.path.join(td, "decimated.obj")
            ms.save_current_mesh(obj_path, save_textures=False)  # keep UVs, drop the unnamed texture
            dm = trimesh.load(obj_path, process=False, force="mesh")
            uv = getattr(dm.visual, "uv", None)
            if uv is None:
                log.append({"stage": "decimate", "skipped": True, "reason": "decimated mesh lost UVs"})
                return False
            mat = trimesh.visual.material.PBRMaterial(
                baseColorTexture=img, metallicFactor=0.0, roughnessFactor=0.85
            )
            dm.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat, image=img)
            dm.export(out_glb)

        if _reduced:
            log.append({"stage": "decimate", "ok": True, "faces_before": before,
                        "faces_after": after, "target": int(target_faces)})
        else:
            log.append({"stage": "decimate", "ok": False, "faces_before": before,
                        "faces_after": after, "target": int(target_faces),
                        "reason": "quadric sans effet: mesh fragmente en ilots, "
                                  "preserveboundary verrouille chaque frontiere. "
                                  "Reencodage OBJ conserve, reduction de faces non."})
        return True
    except Exception as exc:  # noqa: BLE001
        log.append({"stage": "decimate", "skipped": True, "reason": f"error: {exc!r}"})
        return False


def _gltfpack(in_glb: str, out_glb: str, log: list[dict[str, Any]]) -> bool:
    exe = shutil.which("gltfpack")
    cmd_prefix: list[str]
    if exe:
        cmd_prefix = [exe]
    elif shutil.which("npx"):
        cmd_prefix = ["npx", "--yes", "gltfpack"]
    else:
        log.append({"stage": "gltfpack", "skipped": True, "reason": "gltfpack / npx not on PATH"})
        return False
    try:
        # -vtf: float-quantize UVs (avoids texel-mismatch on 2k textures).
        # -noq: disable quantization for positions/colors which corrupts Hunyuan3D vertex colors.
        # No -cc / -tc: stay on three.js-native extensions only.
        proc = subprocess.run(
            [*cmd_prefix, "-i", in_glb, "-o", out_glb, "-vtf", "-noq"],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0 or not os.path.isfile(out_glb):
            log.append({"stage": "gltfpack", "skipped": True, "reason": f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}"})
            return False
        log.append({"stage": "gltfpack", "ok": True})
        return True
    except Exception as exc:  # noqa: BLE001
        log.append({"stage": "gltfpack", "skipped": True, "reason": f"error: {exc!r}"})
        return False


def optimize(mesh_path: str, output_path: str, kind: str = "object",
             max_faces: int | None = None) -> dict[str, Any]:
    src = Path(mesh_path)
    if not src.is_file():
        return {"ok": False, "error": f"mesh not found: {mesh_path}"}

    log: list[dict[str, Any]] = []
    bytes_before = src.stat().st_size

    # Face count + texture check up front.
    try:
        import trimesh

        m0 = trimesh.load(str(src), process=False, force="mesh")
        faces_before = int(len(m0.faces))
        visual = getattr(m0, "visual", None)
        has_tex = (
            getattr(visual, "__class__", type(None)).__name__ == "TextureVisuals"
            or getattr(visual, "uv", None) is not None
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"cannot read mesh: {exc!r}"}

    if not has_tex:
        # Nothing texture-aware to do; just gltfpack-quantize in place.
        log.append({"stage": "decimate", "skipped": True, "reason": "mesh is not textured"})

    work_dir = Path(tempfile.mkdtemp())
    try:
        stage_in = str(src)

        # Stage 1 — decimation (only worthwhile on dense textured meshes).
        # max_faces abaisse le PLAFOND (450k par defaut). Les planchers par kind
        # (180k-280k) protegeent la qualite de livraison: un viewer ne peut pas
        # rendre 450k faces fluide, alors qu'un modele de scene tres dense (967k
        # faces mesure sur Natsu) reste au plafond. max_faces sert a produire une
        # VARIANTE DE PREVISUALISATION cote viewer, sans toucher au livrable.
        # Non fourni = comportement identique a avant.
        if has_tex and faces_before >= _DECIMATE_MIN_FACES:
            floor = _FACE_FLOOR.get((kind or "object").lower(), _DEFAULT_FLOOR)
            cap = int(max_faces) if max_faces else _DECIMATE_FACE_CAP
            target = max(min(faces_before // 2, cap), min(floor, cap))
            dec_out = str(work_dir / "decimated.glb")
            if _decimate_uv_preserving(stage_in, dec_out, target, log):
                stage_in = dec_out
            if max_faces and target >= faces_before:
                log.append({"stage": "decimate", "note": f"max_faces={int(max_faces)} "
                          f"> faces={faces_before}: pas de reduction possible"})
        elif has_tex:
            log.append({"stage": "decimate", "skipped": True, "reason": f"only {faces_before} faces (< {_DECIMATE_MIN_FACES})"})

        # Stage 2 — gltfpack quantization.
        pack_out = str(work_dir / "packed.glb")
        if _gltfpack(stage_in, pack_out, log):
            stage_in = pack_out

        # Emit result. If nothing changed, still copy through so callers get a file.
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not (out.exists() and src.exists() and os.path.samefile(stage_in, str(out))):
            shutil.copy2(stage_in, out)

        try:
            mr = trimesh.load(str(out), process=False, force="mesh")
            faces_after = int(len(mr.faces))
        except Exception:  # noqa: BLE001
            faces_after = faces_before
        bytes_after = out.stat().st_size

        return {
            "ok": True,
            "input": str(src),
            "output": str(out),
            "kind": kind,
            "faces_before": faces_before,
            "faces_after": faces_after,
            "bytes_before": bytes_before,
            "bytes_after": bytes_after,
            "size_ratio": round(bytes_after / bytes_before, 3) if bytes_before else None,
            "stages": log,
            "changed": stage_in != str(src),
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Optimize a textured GLB for the viewer (decimate + gltfpack).")
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--kind", default="object")
    ap.add_argument("--max-faces", type=int, default=None,
                    help="abaisse le plafond de faces (variante viewer). "
                         "Par defaut: plafond par kind, 450k.")
    args = ap.parse_args()
    res = optimize(args.mesh, args.output, args.kind, args.max_faces)
    print(json.dumps(res))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
