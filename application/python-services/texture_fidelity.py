import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import cv2
from PIL import Image
from pygltflib import GLTF2

Image.MAX_IMAGE_PIXELS = None
_HERE = Path(__file__).resolve().parent
_BPY_SCRIPT = _HERE / "texture_fidelity_bpy.py"
_ESRGAN_CKPT = _HERE / "_hy3dpaint" / "ckpt" / "RealESRGAN_x4plus.pth"


def _find_blender():
    for c in (os.environ.get("AURORA_BLENDER"), os.environ.get("BLENDER_BIN"),
              os.path.expanduser("~/.local/bin/blender"), shutil.which("blender")):
        if c and os.path.isfile(c):
            return c
    return None


def _print_result(d):
    print("AURORA_FIDELITY_RESULT:" + json.dumps(d), flush=True)


def _rembg_mask(rgb):
    from rembg import remove, new_session
    out = remove(Image.fromarray(rgb), session=new_session("u2net"))
    return (np.asarray(out)[..., 3] > 127).astype(np.uint8)


def _fill_holes(comp):
    h, w = comp.shape
    inv = (1 - comp).astype(np.uint8)
    ff = inv.copy()
    ffmask = np.zeros((h + 2, w + 2), np.uint8)
    seeds = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
            [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    for sx, sy in seeds:
        if ff[sy, sx] == 1:
            cv2.floodFill(ff, ffmask, (sx, sy), 0)
    return ((comp == 1) | (ff == 1)).astype(np.uint8)


def _fill_small_holes(binm, max_area):
    h, w = binm.shape
    num, labels, stats, _ = cv2.connectedComponentsWithStats((1 - binm).astype(np.uint8), 8)
    if num <= 1:
        return binm
    x = stats[:, cv2.CC_STAT_LEFT]
    y = stats[:, cv2.CC_STAT_TOP]
    bw = stats[:, cv2.CC_STAT_WIDTH]
    bh = stats[:, cv2.CC_STAT_HEIGHT]
    area = stats[:, cv2.CC_STAT_AREA]
    fill = (x > 0) & (y > 0) & (x + bw < w) & (y + bh < h) & (area <= max_area)
    fill[0] = False
    lut = fill.astype(np.uint8)
    return np.maximum(binm, lut[labels])


def _subject_mask(rgb):
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    white_bg = float((border.min(axis=1) > 235).mean()) > 0.8
    if white_bg:
        raw = (rgb.min(axis=2) < 245).astype(np.uint8)
    else:
        raw = _rembg_mask(rgb)
    raw = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(raw, 8)
    if num <= 1:
        return raw
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return _fill_holes((labels == largest).astype(np.uint8))


def _prepare_photo(photo_path, workdir):
    rgb = np.asarray(Image.open(photo_path).convert("RGB"))
    mask = _subject_mask(rgb)
    ys, xs = np.nonzero(mask)
    if xs.size < 100:
        raise RuntimeError("subject mask empty")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    sub_rgb = rgb[y0:y1, x0:x1]
    sub_mask = mask[y0:y1, x0:x1]
    alpha = (sub_mask * 255).astype(np.uint8)
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=2)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)
    rgba_path = os.path.join(workdir, "photo_rgba.png")
    mask_path = os.path.join(workdir, "photo_mask.png")
    Image.fromarray(np.dstack([sub_rgb, alpha])).save(rgba_path)
    Image.fromarray((sub_mask * 255).astype(np.uint8)).save(mask_path)
    return rgba_path, mask_path


def _glb_albedo_info(path):
    g = GLTF2().load(str(path))
    albedo_idx = None
    normal_present = False
    for m in g.materials or []:
        if m.normalTexture is not None:
            normal_present = True
        pbr = m.pbrMetallicRoughness
        if albedo_idx is None and pbr and pbr.baseColorTexture is not None:
            albedo_idx = g.textures[pbr.baseColorTexture.index].source
    if albedo_idx is None:
        raise RuntimeError("no baseColorTexture in glb")
    blob = g.binary_blob()
    bv = g.bufferViews[g.images[albedo_idx].bufferView]
    png = blob[bv.byteOffset: bv.byteOffset + bv.byteLength]
    size = Image.open(io.BytesIO(png)).size
    return g, albedo_idx, bytes(png), size, normal_present


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


def _run_blender(mesh, photo_rgba, photo_mask, workdir, size):
    blender = _find_blender()
    if not blender:
        raise RuntimeError("blender introuvable")
    cmd = [blender, "-b", "--factory-startup", "-noaudio",
           "--python", str(_BPY_SCRIPT), "--",
           "--mesh", str(mesh), "--photo", photo_rgba, "--mask", photo_mask,
           "--workdir", workdir, "--size", str(size)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    try:
        with open(os.path.join(workdir, "blender.log"), "w") as fh:
            fh.write((p.stdout or "") + "\n--- STDERR ---\n" + (p.stderr or ""))
    except OSError:
        pass
    for line in reversed((p.stdout or "").splitlines()):
        if line.startswith("FIDELITY_RESULT:"):
            return json.loads(line[len("FIDELITY_RESULT:"):])
    return {"ok": False, "error": (p.stderr or p.stdout or "no output")[-500:]}


def _composite(orig_png, bake_color_path, bake_mask_path, facing=0.12, close_px=8, erode_px=4, sigma=3.0):
    orig = np.asarray(Image.open(io.BytesIO(orig_png)).convert("RGBA"))
    bake = np.asarray(Image.open(bake_color_path).convert("RGB"))
    mask = np.asarray(Image.open(bake_mask_path).convert("L"))
    h, w = orig.shape[:2]
    if bake.shape[:2] != (h, w):
        bake = cv2.resize(bake, (w, h), interpolation=cv2.INTER_LANCZOS4)
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    binm = (mask.astype(np.float32) / 255.0 > facing).astype(np.uint8)
    if close_px > 0:
        kc = 2 * close_px + 1
        binm = cv2.morphologyEx(binm, cv2.MORPH_CLOSE, np.ones((kc, kc), np.uint8))
    binm = _fill_small_holes(binm, int(0.01 * h * w))
    coverage = float(binm.mean())
    k = 2 * erode_px + 1
    er = cv2.erode(binm, np.ones((k, k), np.uint8))
    f = np.clip(cv2.GaussianBlur(er.astype(np.float32), (0, 0), sigma), 0.0, 1.0)[..., None]
    out = orig.copy()
    rgb = orig[..., :3].astype(np.float32) * (1.0 - f) + bake.astype(np.float32) * f
    out[..., :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    return out, coverage


def _refine_esrgan(rgba):
    sys.path.insert(0, str(_HERE))
    from paint_pbr_v21 import _apply_torchvision_fix
    _apply_torchvision_fix()
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    up = RealESRGANer(scale=4, model_path=str(_ESRGAN_CKPT), model=model,
                      tile=512, tile_pad=10, pre_pad=0, half=True)
    bgr = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2BGR)
    out_bgr, _ = up.enhance(bgr, outscale=2)
    h, w = out_bgr.shape[:2]
    alpha = cv2.resize(rgba[..., 3], (w, h), interpolation=cv2.INTER_LINEAR)
    return np.dstack([cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB), alpha])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--photo", required=True)
    ap.add_argument("--output", default=None)
    ap.add_argument("--refine", action="store_true")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--facing", type=float, default=0.12)
    a = ap.parse_args()

    mesh = Path(a.mesh)
    output = Path(a.output) if a.output else mesh.with_name(mesh.stem + "_fidelity.glb")
    workdir = a.workdir or tempfile.mkdtemp(prefix="fidelity_", dir=str(mesh.parent))
    os.makedirs(workdir, exist_ok=True)
    result = {"ok": False, "output": str(output), "axis": None, "coverage": 0.0, "refined": False}
    try:
        g, albedo_idx, orig_png, atlas_size, normal_present = _glb_albedo_info(mesh)
        bake_size = min(max(atlas_size), 8192)
        if bake_size < 1024:
            bake_size = 4096
        print(f"PROGRESS:fidelity:atlas {atlas_size[0]}x{atlas_size[1]} bake {bake_size} normal={normal_present}", flush=True)

        photo_rgba, photo_mask = _prepare_photo(a.photo, workdir)
        print("PROGRESS:fidelity:photo detouree, lancement blender...", flush=True)

        bres = _run_blender(mesh, photo_rgba, photo_mask, workdir, bake_size)
        if not bres.get("ok") and bake_size > 4096:
            print("PROGRESS:fidelity:echec bake 8k, retry 4096...", flush=True)
            bres = _run_blender(mesh, photo_rgba, photo_mask, workdir, 4096)
        if not bres.get("ok"):
            raise RuntimeError(f"blender bake failed: {bres.get('error')}")
        result["axis"] = bres.get("axis")
        print(f"PROGRESS:fidelity:axe {bres.get('axis')} scores {bres.get('scores')}", flush=True)

        comp, coverage = _composite(orig_png, bres["bake_color"], bres["bake_mask"], facing=a.facing)
        result["coverage"] = round(coverage, 4)
        print(f"PROGRESS:fidelity:coverage {coverage:.4f}", flush=True)
        if coverage < 0.01:
            raise RuntimeError(f"projection coverage too low: {coverage:.4f}")

        if a.refine and comp.shape[0] < 8192:
            print("PROGRESS:fidelity:refine realesrgan x2...", flush=True)
            comp = _refine_esrgan(comp)
            result["refined"] = True

        buf = io.BytesIO()
        Image.fromarray(comp).save(buf, format="PNG")
        _replace_glb_image(g, albedo_idx, buf.getvalue())
        g.save_binary(str(output))
        result["ok"] = output.is_file() and output.stat().st_size > 1000
        if not result["ok"]:
            result["error"] = "output glb missing"
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    _print_result(result)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
