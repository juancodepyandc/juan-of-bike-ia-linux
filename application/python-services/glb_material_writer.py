import argparse
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pygltflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import material_manifest

EXT_TRANSMISSION = "KHR_materials_transmission"
EXT_VOLUME = "KHR_materials_volume"
EXT_IOR = "KHR_materials_ior"
EXT_SPECULAR = "KHR_materials_specular"
EXT_CLEARCOAT = "KHR_materials_clearcoat"
EXT_SHEEN = "KHR_materials_sheen"
EXT_ANISOTROPY = "KHR_materials_anisotropy"
EXT_EMISSIVE_STRENGTH = "KHR_materials_emissive_strength"

DEFAULT_TEST_GLB = "/home/juan/AuroraIA/application/output/3d/generations/asus_maxprec/asus_maxprec_mesh_opt.glb"


def _ensure_used(g, name):
    if g.extensionsUsed is None:
        g.extensionsUsed = []
    if name not in g.extensionsUsed:
        g.extensionsUsed.append(name)


def _append_png_texture(g, png_bytes, name):
    blob = bytearray(g.binary_blob())
    while len(blob) % 4:
        blob.append(0)
    offset = len(blob)
    blob.extend(png_bytes)
    while len(blob) % 4:
        blob.append(0)
    g.bufferViews.append(pygltflib.BufferView(buffer=0, byteOffset=offset, byteLength=len(png_bytes)))
    g.images.append(pygltflib.Image(bufferView=len(g.bufferViews) - 1, mimeType="image/png", name=name))
    g.textures.append(pygltflib.Texture(source=len(g.images) - 1, name=name))
    g.buffers[0].byteLength = len(blob)
    g.set_binary_blob(bytes(blob))
    return len(g.textures) - 1


def _replace_glb_image(g, image_index, png_bytes):
    blob = g.binary_blob()
    target_bv = g.images[image_index].bufferView
    order = sorted(range(len(g.bufferViews)), key=lambda i: g.bufferViews[i].byteOffset or 0)
    out = bytearray()
    for i in order:
        bv = g.bufferViews[i]
        if len(out) % 4:
            out.extend(b"\x00" * (4 - len(out) % 4))
        if i == target_bv:
            data = png_bytes
        else:
            off = bv.byteOffset or 0
            data = blob[off: off + bv.byteLength]
        bv.byteOffset = len(out)
        bv.byteLength = len(data)
        out.extend(data)
    g.buffers[0].byteLength = len(out)
    g.set_binary_blob(bytes(out))


def _pack_ao_into_mr(g, mat, ao_bytes):
    pbr = mat.pbrMetallicRoughness
    if pbr is None or pbr.metallicRoughnessTexture is None:
        return False
    from PIL import Image
    img_idx = g.textures[pbr.metallicRoughnessTexture.index].source
    bv = g.bufferViews[g.images[img_idx].bufferView]
    blob = g.binary_blob()
    off = bv.byteOffset or 0
    mr = Image.open(io.BytesIO(blob[off: off + bv.byteLength])).convert("RGB")
    ao = Image.open(io.BytesIO(ao_bytes)).convert("L").resize(mr.size)
    _, gc, bc = mr.split()
    packed = Image.merge("RGB", (ao, gc, bc))
    buf = io.BytesIO()
    packed.save(buf, format="PNG")
    _replace_glb_image(g, img_idx, buf.getvalue())
    g.images[img_idx].mimeType = "image/png"
    return True


def _rgb(value):
    rgb = material_manifest.parse_color(value)
    return [round(c, 6) for c in rgb]


def _apply_zone(g, zone, alpha_fallback, mask_cache):
    ch = zone.get("channels") or {}
    idx = zone["target"]["material_index"]
    mat = g.materials[idx]
    ext = mat.extensions or {}
    mask_tex = None
    mask = zone["target"].get("mask_png")
    if mask:
        if mask in mask_cache:
            mask_tex = mask_cache[mask]
        elif Path(mask).is_file():
            mask_tex = _append_png_texture(g, Path(mask).read_bytes(), "aurora_mask_" + zone["zone_id"])
            mask_cache[mask] = mask_tex
    if "transmission" in ch:
        t = {"transmissionFactor": float(ch["transmission"])}
        if mask_tex is not None:
            t["transmissionTexture"] = {"index": mask_tex}
        ext[EXT_TRANSMISSION] = t
        _ensure_used(g, EXT_TRANSMISSION)
    if "thickness" in ch or "attenuationColor" in ch:
        v = {}
        if "thickness" in ch:
            v["thicknessFactor"] = float(ch["thickness"])
        if "attenuationColor" in ch:
            v["attenuationColor"] = _rgb(ch["attenuationColor"])
        ext[EXT_VOLUME] = v
        _ensure_used(g, EXT_VOLUME)
    if "ior" in ch:
        ext[EXT_IOR] = {"ior": float(ch["ior"])}
        _ensure_used(g, EXT_IOR)
    if "specular" in ch:
        ext[EXT_SPECULAR] = {"specularFactor": float(ch["specular"])}
        _ensure_used(g, EXT_SPECULAR)
    if "clearcoat" in ch or "clearcoatRoughness" in ch:
        c = {"clearcoatFactor": float(ch.get("clearcoat", 1.0))}
        if "clearcoatRoughness" in ch:
            c["clearcoatRoughnessFactor"] = float(ch["clearcoatRoughness"])
        ext[EXT_CLEARCOAT] = c
        _ensure_used(g, EXT_CLEARCOAT)
    if "sheen" in ch or "sheenColor" in ch:
        s = float(ch.get("sheen", 1.0))
        base = _rgb(ch.get("sheenColor", "#ffffff"))
        ext[EXT_SHEEN] = {
            "sheenColorFactor": [round(c * s, 6) for c in base],
            "sheenRoughnessFactor": float(ch.get("roughness", 0.5)),
        }
        _ensure_used(g, EXT_SHEEN)
    if "anisotropy" in ch or "anisotropyStrength" in ch:
        a = {"anisotropyStrength": float(ch.get("anisotropyStrength", 1.0))}
        if "anisotropy" in ch:
            a["anisotropyRotation"] = float(ch["anisotropy"])
        ext[EXT_ANISOTROPY] = a
        _ensure_used(g, EXT_ANISOTROPY)
    if "emissiveFactor" in ch or "emissiveStrength" in ch:
        mat.emissiveFactor = _rgb(ch.get("emissiveFactor", "#ffffff"))
        if "emissiveStrength" in ch:
            ext[EXT_EMISSIVE_STRENGTH] = {"emissiveStrength": float(ch["emissiveStrength"])}
            _ensure_used(g, EXT_EMISSIVE_STRENGTH)
        if mask_tex is not None:
            mat.emissiveTexture = pygltflib.TextureInfo(index=mask_tex)
    if "roughness" in ch or "metallic" in ch:
        if mat.pbrMetallicRoughness is None:
            mat.pbrMetallicRoughness = pygltflib.PbrMetallicRoughness()
        if "roughness" in ch:
            mat.pbrMetallicRoughness.roughnessFactor = float(ch["roughness"])
        if "metallic" in ch:
            mat.pbrMetallicRoughness.metallicFactor = float(ch["metallic"])
    if alpha_fallback and float(ch.get("transmission", 0.0)) > 0.5:
        mat.alphaMode = "BLEND"
        if mat.pbrMetallicRoughness is None:
            mat.pbrMetallicRoughness = pygltflib.PbrMetallicRoughness()
        bcf = list(mat.pbrMetallicRoughness.baseColorFactor or [1.0, 1.0, 1.0, 1.0])
        bcf[3] = 0.45
        mat.pbrMetallicRoughness.baseColorFactor = bcf
    mat.extensions = ext
    return idx


def apply_manifest(glb_path, manifest, output_path, alpha_fallback=False, ao_path=None):
    ok, errors = material_manifest.validate(manifest)
    if not ok:
        return {"ok": False, "errors": errors}
    manifest = material_manifest.normalize(manifest)
    g = pygltflib.GLTF2().load(str(glb_path))
    n_materials = len(g.materials or [])
    for i, zone in enumerate(manifest["zones"]):
        if zone["target"]["material_index"] >= n_materials:
            return {"ok": False, "errors": ["zones[%d].target.material_index %d hors limite (%d materiaux)" % (i, zone["target"]["material_index"], n_materials)]}
    original_bv_count = len(g.bufferViews)
    mask_cache = {}
    touched = []
    labels = {z.get("label") for z in manifest["zones"]}
    multi = len(manifest["zones"]) > 1 and len(labels) > 1
    surface_keys = ("sheen", "sheenColor", "clearcoat", "clearcoatRoughness",
                    "transmission", "ior", "thickness", "attenuationColor",
                    "anisotropy", "anisotropyStrength", "specular",
                    "roughness", "metallic")
    for zone in manifest["zones"]:
        z = zone
        if not zone.get("target", {}).get("mask_png"):
            ch = dict(zone.get("channels", {}))
            if multi:
                ch = {k: v for k, v in ch.items()
                      if k not in surface_keys or zone.get("label") in ("glass", "water")}
            ef = ch.get("emissiveFactor")
            if isinstance(ef, str) and ef.startswith("#") and len(ef) >= 7:
                try:
                    ef = [int(ef[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
                except ValueError:
                    ef = None
            if isinstance(ef, (list, tuple)) and len(ef) >= 3 and min(ef[:3]) > 0.7:
                ch.pop("emissiveFactor", None)
                ch.pop("emissiveStrength", None)
            if not ch:
                continue
            z = dict(zone)
            z["channels"] = ch
        touched.append(_apply_zone(g, z, alpha_fallback, mask_cache))
    if not touched and n_materials:
        touched = [0]
    ao_packed = False
    if ao_path:
        ao_bytes = Path(ao_path).read_bytes()
        ao_tex = _append_png_texture(g, ao_bytes, "aurora_ao")
        for idx in sorted(set(touched)):
            mat = g.materials[idx]
            mat.occlusionTexture = pygltflib.OcclusionTextureInfo(index=ao_tex)
            if _pack_ao_into_mr(g, mat, ao_bytes):
                ao_packed = True
    extras = g.extras if isinstance(g.extras, dict) else {}
    extras["aurora_material_intel"] = manifest
    g.extras = extras
    g.save_binary(str(output_path))
    return {
        "ok": Path(output_path).is_file() and Path(output_path).stat().st_size > 1000,
        "output": str(output_path),
        "zones_applied": len(manifest["zones"]),
        "materials_touched": sorted(set(touched)),
        "extensions_used": list(g.extensionsUsed or []),
        "images_added": len(g.bufferViews) - original_bv_count,
        "ao_packed_in_mr": ao_packed,
        "size_bytes": Path(output_path).stat().st_size if Path(output_path).is_file() else 0,
    }


def _make_fallback_glb(workdir):
    import trimesh
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    mesh.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(baseColorFactor=[180, 180, 190, 255], roughnessFactor=0.6),
    )
    path = os.path.join(workdir, "fallback_cube.glb")
    mesh.export(path)
    return path


def _self_test(glb_path, keep):
    workdir = tempfile.mkdtemp(prefix="aurora_glbmat_")
    result = {"ok": False, "checks": {}, "workdir": workdir}
    try:
        if not Path(glb_path).is_file():
            glb_path = _make_fallback_glb(workdir)
            result["fallback_glb"] = True
        result["glb"] = str(glb_path)
        manifest = {
            "schema": material_manifest.SCHEMA_ID,
            "zones": [{
                "zone_id": "selftest_body",
                "label": "paint_gloss",
                "target": {"material_index": 0},
                "channels": {
                    "clearcoat": 1.0,
                    "clearcoatRoughness": 0.08,
                    "emissiveFactor": "#ff2040",
                    "emissiveStrength": 4.0,
                },
                "confidence": 0.92,
                "source": "self_test",
            }],
        }
        out = os.path.join(workdir, "selftest_out.glb")
        apply_res = apply_manifest(glb_path, manifest, out, alpha_fallback=False, ao_path=None)
        result["apply"] = apply_res
        checks = result["checks"]
        checks["apply_ok"] = bool(apply_res.get("ok"))
        if not checks["apply_ok"]:
            return result
        g1 = pygltflib.GLTF2().load(str(glb_path))
        g2 = pygltflib.GLTF2().load(out)
        ext = (g2.materials[0].extensions or {})
        checks["clearcoat_present"] = ext.get(EXT_CLEARCOAT, {}).get("clearcoatFactor") == 1.0
        checks["clearcoat_roughness"] = ext.get(EXT_CLEARCOAT, {}).get("clearcoatRoughnessFactor") == 0.08
        checks["emissive_strength_present"] = ext.get(EXT_EMISSIVE_STRENGTH, {}).get("emissiveStrength") == 4.0
        ef = g2.materials[0].emissiveFactor or []
        checks["emissive_factor_rgb"] = len(ef) == 3 and abs(ef[0] - 1.0) < 1e-3 and abs(ef[1] - 32 / 255.0) < 1e-3 and abs(ef[2] - 64 / 255.0) < 1e-3
        used = g2.extensionsUsed or []
        checks["extensions_used_listed"] = EXT_CLEARCOAT in used and EXT_EMISSIVE_STRENGTH in used
        extras = g2.extras or {}
        checks["extras_manifest_embedded"] = isinstance(extras.get("aurora_material_intel"), dict) and extras["aurora_material_intel"].get("schema") == material_manifest.SCHEMA_ID
        checks["bufferviews_intact"] = (
            len(g2.bufferViews) >= len(g1.bufferViews)
            and all(g2.bufferViews[i].byteLength == g1.bufferViews[i].byteLength for i in range(len(g1.bufferViews)))
        )
        checks["accessors_intact"] = len(g2.accessors or []) == len(g1.accessors or [])
        checks["meshes_intact"] = len(g2.meshes or []) == len(g1.meshes or [])
        checks["animations_intact"] = len(g2.animations or []) == len(g1.animations or [])
        import trimesh
        scene = trimesh.load(out, force="scene")
        faces = sum(int(geo.faces.shape[0]) for geo in scene.geometry.values() if hasattr(geo, "faces"))
        checks["trimesh_loads"] = faces > 0
        result["trimesh_faces"] = faces
        result["output_size_bytes"] = Path(out).stat().st_size
        result["ok"] = all(checks.values())
        if keep:
            result["output"] = out
        return result
    except Exception as exc:
        result["error"] = repr(exc)
        return result
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)
            result.pop("workdir", None)


def _self_test_manifest(manifest_path, glb_path, keep):
    workdir = tempfile.mkdtemp(prefix="aurora_glbmat_manifest_")
    result = {"ok": False, "checks": {}, "workdir": workdir, "manifest": str(manifest_path)}
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        checks = result["checks"]
        valid, errors = material_manifest.validate(manifest)
        checks["manifest_valid"] = valid
        if not valid:
            result["errors"] = errors
            return result
        if not glb_path or not Path(glb_path).is_file():
            glb_path = _make_fallback_glb(workdir)
            result["fallback_glb"] = True
        result["glb"] = str(glb_path)
        out = os.path.join(workdir, "manifest_selftest_out.glb")
        apply_res = apply_manifest(glb_path, manifest, out, alpha_fallback=True, ao_path=None)
        result["apply"] = apply_res
        checks["apply_ok"] = bool(apply_res.get("ok"))
        if not checks["apply_ok"]:
            return result
        g2 = pygltflib.GLTF2().load(out)
        extras = g2.extras or {}
        checks["extras_manifest_embedded"] = (
            isinstance(extras.get("aurora_material_intel"), dict)
            and extras["aurora_material_intel"].get("schema") == material_manifest.SCHEMA_ID
        )
        checks["all_zones_applied"] = apply_res.get("zones_applied") == len(manifest.get("zones", []))
        result["extensions_used"] = list(g2.extensionsUsed or [])
        result["output_size_bytes"] = Path(out).stat().st_size
        result["ok"] = all(checks.values())
        if keep:
            result["output"] = out
        return result
    except Exception as exc:
        result["error"] = repr(exc)
        return result
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)
            result.pop("workdir", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb")
    ap.add_argument("--manifest")
    ap.add_argument("--output")
    ap.add_argument("--alpha-fallback", action="store_true")
    ap.add_argument("--ao")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--self-test-manifest", dest="self_test_manifest")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    if a.self_test_manifest:
        result = _self_test_manifest(a.self_test_manifest, a.glb, a.keep)
    elif a.self_test:
        result = _self_test(a.glb or DEFAULT_TEST_GLB, a.keep)
    elif a.glb and a.manifest and a.output:
        try:
            with open(a.manifest, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            result = apply_manifest(a.glb, manifest, a.output, alpha_fallback=a.alpha_fallback, ao_path=a.ao)
        except Exception as exc:
            result = {"ok": False, "errors": [repr(exc)]}
    else:
        result = {"ok": False, "errors": ["--glb --manifest --output requis (ou --self-test)"]}
    print("AURORA_GLB_MATERIAL_WRITER_RESULT:" + json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
