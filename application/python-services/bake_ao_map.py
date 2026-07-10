from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from pygltflib import (
    ARRAY_BUFFER,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    GLTF2,
    SCALAR,
    UNSIGNED_SHORT,
    VEC2,
    VEC3,
    Accessor,
    Attributes,
    Buffer,
    BufferView,
    Material,
    Mesh,
    Node,
    OcclusionTextureInfo,
    PbrMetallicRoughness,
    Primitive,
    Scene,
    TextureInfo,
)
from pygltflib import Image as GLTFImage
from pygltflib import Texture as GLTFTexture

Image.MAX_IMAGE_PIXELS = None


def _find_blender():
    for c in (os.environ.get("AURORA_BLENDER"), os.environ.get("BLENDER_BIN"),
              os.path.expanduser("~/.local/bin/blender"), shutil.which("blender")):
        if c and os.path.isfile(c):
            return c
    return None


def _print_result(d):
    print("AURORA_BAKE_AO_RESULT:" + json.dumps(d), flush=True)


_BLENDER_SCRIPT = r'''
import bpy, sys, os, traceback


def _argv():
    a = sys.argv
    if "--" in a:
        return a[a.index("--") + 1:]
    return []


def main():
    args = _argv()
    if len(args) < 4:
        print("AOBAKE_FAIL: not enough args", flush=True)
        sys.exit(2)
    mesh_path, out_png, res, samples = args[0], args[1], int(args[2]), int(args[3])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.cycles.device = "CPU"
    except Exception:
        pass
    sc.cycles.samples = samples
    if sc.world is None:
        sc.world = bpy.data.worlds.new("AOWorld")

    ext = os.path.splitext(mesh_path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=mesh_path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=mesh_path)
    else:
        print("AOBAKE_FAIL: unsupported ext %s" % ext, flush=True)
        sys.exit(3)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        print("AOBAKE_FAIL: no mesh imported", flush=True)
        sys.exit(4)
    target = max(meshes, key=lambda o: len(o.data.polygons))
    if not target.data.uv_layers:
        print("AOBAKE_FAIL: mesh has no UV map", flush=True)
        sys.exit(5)

    img = bpy.data.images.new("BakeAO", width=res, height=res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"

    mat = bpy.data.materials.new("BakeAOMat")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    for n in nt.nodes:
        n.select = False
    tex.select = True
    nt.nodes.active = tex
    target.data.materials.clear()
    target.data.materials.append(mat)

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    try:
        sc.world.light_settings.distance = max(max(target.dimensions) * 0.02, 0.001)
    except Exception:
        pass

    try:
        bpy.ops.object.bake(type="AO", use_selected_to_active=False, margin=8)
    except Exception as exc:
        traceback.print_exc()
        print("AOBAKE_FAIL: bake exception: %r" % (exc,), flush=True)
        sys.exit(6)

    try:
        import numpy as np
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        rgb = px.reshape(-1, 4)
        rgb[:, :3] = 0.55 + 0.45 * rgb[:, :3]
        img.pixels.foreach_set(px)
    except Exception:
        pass

    img.filepath_raw = out_png
    img.file_format = "PNG"
    img.save()
    print("AOBAKE_OK: %s" % out_png, flush=True)


try:
    main()
except SystemExit:
    raise
except Exception as exc:
    traceback.print_exc()
    print("AOBAKE_FAIL: top-level: %r" % (exc,), flush=True)
    sys.exit(99)
'''


def _mock_ao(res):
    cx = (res - 1) / 2.0
    yy, xx = np.mgrid[0:res, 0:res]
    d = np.sqrt((xx - cx) ** 2 + (yy - cx) ** 2) / max(cx, 1.0)
    return np.clip(255.0 * (1.0 - 0.55 * d), 0.0, 255.0).astype(np.uint8)


def bake_ao(mesh_path, out_png, res=4096, samples=64, timeout_s=1800, log=print):
    t0 = time.time()
    os.makedirs(os.path.dirname(str(out_png)) or ".", exist_ok=True)

    if os.environ.get("AURORA_AO_MOCK") == "1":
        arr = _mock_ao(res)
        Image.fromarray(arr, "L").save(str(out_png))
        return {"ok": True, "ao_png": str(out_png), "mock": True, "res": res,
                "ao_mean": round(float(arr.mean()), 2), "ao_std": round(float(arr.std()), 2),
                "elapsed_s": round(time.time() - t0, 2), "size_bytes": os.path.getsize(str(out_png))}

    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "blender introuvable (AURORA_BLENDER, BLENDER_BIN, ~/.local/bin/blender, PATH)"}
    if not os.path.isfile(str(mesh_path)):
        return {"ok": False, "error": f"mesh introuvable: {mesh_path}"}

    workdir = Path(tempfile.mkdtemp(prefix="bake_ao_"))
    try:
        script = workdir / "bake_ao_bpy.py"
        script.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        raw_png = workdir / "ao_raw.png"
        cmd = [blender, "-b", "--factory-startup", "-noaudio", "--python", str(script), "--",
               str(mesh_path), str(raw_png), str(res), str(samples)]
        log(f"PROGRESS:bake_ao:Blender AO bake (mesh={Path(str(mesh_path)).name}, res={res}, samples={samples})...")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"blender bake timeout apres {timeout_s}s"}

        if proc.returncode != 0 or "AOBAKE_OK" not in (proc.stdout or "") or not raw_png.is_file():
            tail = "\n".join((proc.stdout or "").splitlines()[-12:] + (proc.stderr or "").splitlines()[-12:])
            return {"ok": False, "error": f"blender bake failed (exit {proc.returncode})",
                    "log_tail": tail, "elapsed_s": round(time.time() - t0, 1)}

        arr = np.asarray(Image.open(raw_png).convert("L"))
        Image.fromarray(arr, "L").save(str(out_png))
        return {"ok": True, "ao_png": str(out_png), "res": res, "samples": samples,
                "ao_mean": round(float(arr.mean()), 2), "ao_std": round(float(arr.std()), 2),
                "elapsed_s": round(time.time() - t0, 1), "size_bytes": os.path.getsize(str(out_png))}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _load_image_bytes(g, image_index):
    img = g.images[image_index]
    if img.bufferView is None:
        raise RuntimeError(f"image {image_index} has no bufferView")
    blob = g.binary_blob()
    bv = g.bufferViews[img.bufferView]
    off = bv.byteOffset or 0
    return bytes(blob[off: off + bv.byteLength])


def _replace_image_bytes(g, image_index, png_bytes):
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


def _append_texture(g, png_bytes, name):
    blob = bytearray(g.binary_blob())
    if len(blob) % 4:
        blob.extend(b"\x00" * (4 - len(blob) % 4))
    g.bufferViews.append(BufferView(buffer=0, byteOffset=len(blob), byteLength=len(png_bytes)))
    blob.extend(png_bytes)
    g.images.append(GLTFImage(mimeType="image/png", bufferView=len(g.bufferViews) - 1, name=name))
    g.textures.append(GLTFTexture(source=len(g.images) - 1))
    g.buffers[0].byteLength = len(blob)
    g.set_binary_blob(bytes(blob))
    return len(g.textures) - 1


def attach_ao(glb_path, ao_png_path, out_path, log=print):
    t0 = time.time()
    g = GLTF2().load(str(glb_path))
    if not g.materials:
        return {"ok": False, "error": "no materials in glb"}
    ao_img = Image.open(str(ao_png_path)).convert("L")
    modes = []
    orm_tex_idx = None
    for m in g.materials:
        pbr = m.pbrMetallicRoughness
        if pbr is None:
            pbr = PbrMetallicRoughness()
            m.pbrMetallicRoughness = pbr
        if pbr.metallicRoughnessTexture is not None:
            tex_idx = pbr.metallicRoughnessTexture.index
            img_idx = g.textures[tex_idx].source
            mr = Image.open(io.BytesIO(_load_image_bytes(g, img_idx))).convert("RGB")
            ao_r = ao_img.resize(mr.size, Image.LANCZOS) if ao_img.size != mr.size else ao_img
            _, gch, bch = mr.split()
            buf = io.BytesIO()
            Image.merge("RGB", (ao_r, gch, bch)).save(buf, format="PNG")
            _replace_image_bytes(g, img_idx, buf.getvalue())
            m.occlusionTexture = OcclusionTextureInfo(index=tex_idx)
            modes.append("replace_mr_r")
        else:
            if orm_tex_idx is None:
                white = Image.new("L", ao_img.size, 255)
                buf = io.BytesIO()
                Image.merge("RGB", (ao_img, white, white)).save(buf, format="PNG")
                orm_tex_idx = _append_texture(g, buf.getvalue(), "aurora_orm")
            pbr.metallicRoughnessTexture = TextureInfo(index=orm_tex_idx)
            m.occlusionTexture = OcclusionTextureInfo(index=orm_tex_idx)
            modes.append("new_orm")
    os.makedirs(os.path.dirname(str(out_path)) or ".", exist_ok=True)
    g.save_binary(str(out_path))
    ok = os.path.isfile(str(out_path)) and os.path.getsize(str(out_path)) > 1000
    log(f"PROGRESS:bake_ao:attach {modes} -> {out_path}")
    return {"ok": ok, "output": str(out_path), "materials_touched": len(modes), "modes": modes,
            "size_bytes": os.path.getsize(str(out_path)) if ok else 0,
            "elapsed_s": round(time.time() - t0, 2)}


def verify_attach(glb_path, ao_png_path, tol=2.0):
    g = GLTF2().load(str(glb_path))
    ao = Image.open(str(ao_png_path)).convert("L")
    mats = []
    all_ok = bool(g.materials)
    for m in g.materials or []:
        pbr = m.pbrMetallicRoughness
        occl_ok = m.occlusionTexture is not None
        mr_ok = pbr is not None and pbr.metallicRoughnessTexture is not None
        mad = None
        if occl_ok:
            img_idx = g.textures[m.occlusionTexture.index].source
            arr = np.asarray(Image.open(io.BytesIO(_load_image_bytes(g, img_idx))).convert("RGB")).astype(np.float32)
            ao_rs = np.asarray(ao.resize((arr.shape[1], arr.shape[0]), Image.LANCZOS)).astype(np.float32)
            mad = round(float(np.abs(arr[..., 0] - ao_rs).mean()), 3)
        entry_ok = occl_ok and mr_ok and mad is not None and mad < tol
        all_ok = all_ok and entry_ok
        mats.append({"ok": entry_ok, "occlusion_set": occl_ok, "mr_texture_set": mr_ok, "r_channel_mad": mad})
    return {"ok": all_ok, "materials": mats}


def _make_test_glb(path, with_mr):
    positions = np.array([[-0.5, -0.5, 0.0], [0.5, -0.5, 0.0], [0.5, 0.5, 0.0], [-0.5, 0.5, 0.0]], dtype=np.float32)
    uvs = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32)
    indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint16)
    blob = bytearray()
    blob.extend(indices.tobytes())
    pos_off = len(blob)
    blob.extend(positions.tobytes())
    uv_off = len(blob)
    blob.extend(uvs.tobytes())
    g = GLTF2(
        scene=0,
        scenes=[Scene(nodes=[0])],
        nodes=[Node(mesh=0)],
        meshes=[Mesh(primitives=[Primitive(attributes=Attributes(POSITION=1, TEXCOORD_0=2), indices=0, material=0)])],
        materials=[Material(name="test", pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorFactor=[0.8, 0.8, 0.8, 1.0], metallicFactor=0.0, roughnessFactor=0.9))],
        accessors=[
            Accessor(bufferView=0, componentType=UNSIGNED_SHORT, count=6, type=SCALAR),
            Accessor(bufferView=1, componentType=FLOAT, count=4, type=VEC3,
                     min=[-0.5, -0.5, 0.0], max=[0.5, 0.5, 0.0]),
            Accessor(bufferView=2, componentType=FLOAT, count=4, type=VEC2),
        ],
        bufferViews=[
            BufferView(buffer=0, byteOffset=0, byteLength=12, target=ELEMENT_ARRAY_BUFFER),
            BufferView(buffer=0, byteOffset=pos_off, byteLength=48, target=ARRAY_BUFFER),
            BufferView(buffer=0, byteOffset=uv_off, byteLength=32, target=ARRAY_BUFFER),
        ],
        buffers=[Buffer(byteLength=len(blob))],
    )
    g.set_binary_blob(bytes(blob))
    if with_mr:
        mr = Image.merge("RGB", tuple(Image.new("L", (32, 32), v) for v in (7, 120, 30)))
        buf = io.BytesIO()
        mr.save(buf, format="PNG")
        tex_idx = _append_texture(g, buf.getvalue(), "test_mr")
        g.materials[0].pbrMetallicRoughness.metallicRoughnessTexture = TextureInfo(index=tex_idx)
    g.save_binary(str(path))


def _gb_channels_preserved(glb_path, expected_g=120, expected_b=30):
    g = GLTF2().load(str(glb_path))
    pbr = g.materials[0].pbrMetallicRoughness
    img_idx = g.textures[pbr.metallicRoughnessTexture.index].source
    arr = np.asarray(Image.open(io.BytesIO(_load_image_bytes(g, img_idx))).convert("RGB"))
    return bool((arr[..., 1] == expected_g).all() and (arr[..., 2] == expected_b).all())


def self_test():
    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="bake_ao_selftest_"))
    prev = os.environ.get("AURORA_AO_MOCK")
    os.environ["AURORA_AO_MOCK"] = "1"
    checks = {}
    try:
        ao_png = tmp / "ao.png"
        bake = bake_ao("dummy.glb", str(ao_png), res=64)
        checks["bake_mock_ok"] = bool(bake.get("ok"))
        checks["ao_std_gt2"] = float(bake.get("ao_std") or 0) > 2.0
        checks["grayscale"] = ao_png.is_file() and Image.open(ao_png).mode == "L"

        glb_no_mr = tmp / "quad_no_mr.glb"
        _make_test_glb(glb_no_mr, with_mr=False)
        out_no_mr = tmp / "quad_no_mr_ao.glb"
        att = attach_ao(glb_no_mr, ao_png, out_no_mr, log=lambda *_: None)
        ver = verify_attach(out_no_mr, ao_png)
        checks["attach_new_orm"] = bool(att.get("ok")) and att.get("modes") == ["new_orm"] and bool(ver.get("ok"))

        glb_mr = tmp / "quad_mr.glb"
        _make_test_glb(glb_mr, with_mr=True)
        out_mr = tmp / "quad_mr_ao.glb"
        att2 = attach_ao(glb_mr, ao_png, out_mr, log=lambda *_: None)
        ver2 = verify_attach(out_mr, ao_png)
        checks["attach_replace_mr_r"] = bool(att2.get("ok")) and att2.get("modes") == ["replace_mr_r"] and bool(ver2.get("ok"))
        checks["gb_channels_preserved"] = _gb_channels_preserved(out_mr)

        return {"ok": all(checks.values()), "self_test": True, "checks": checks,
                "elapsed_s": round(time.time() - t0, 2)}
    except Exception as exc:
        checks["exception"] = repr(exc)
        return {"ok": False, "self_test": True, "checks": checks, "elapsed_s": round(time.time() - t0, 2)}
    finally:
        if prev is None:
            os.environ.pop("AURORA_AO_MOCK", None)
        else:
            os.environ["AURORA_AO_MOCK"] = prev
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh")
    ap.add_argument("--output")
    ap.add_argument("--res", type=int, default=4096)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--attach", default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--self-test", action="store_true", dest="self_test")
    a = ap.parse_args()

    if a.self_test:
        r = self_test()
        _print_result(r)
        sys.exit(0 if r.get("ok") else 1)

    if not a.mesh or not a.output:
        ap.error("--mesh et --output requis (ou --self-test)")

    r = bake_ao(a.mesh, a.output, res=a.res, samples=a.samples, timeout_s=a.timeout)
    if r.get("ok") and a.attach:
        r["attach"] = attach_ao(a.mesh, a.output, a.attach)
        if r["attach"].get("ok"):
            r["verify"] = verify_attach(a.attach, a.output)
            r["ok"] = bool(r["verify"].get("ok"))
        else:
            r["ok"] = False
    _print_result(r)
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
