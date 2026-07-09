import argparse
import json
import os
import sys
import tempfile
import time

import cv2
import numpy as np
from pygltflib import GLTF2, Buffer, BufferView, Image as GltfImage, Material, NormalMaterialTexture, PbrMetallicRoughness, Texture, TextureInfo


def _print_result(d):
    print("AURORA_ROUGHNESS_RESULT:" + json.dumps(d), flush=True)


def _decode_rgb(png_bytes):
    arr = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if arr is None:
        raise RuntimeError("png decode failed")
    if arr.dtype == np.uint16:
        arr = (arr // 257).astype(np.uint8)
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
    return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)


def _load_glb_maps(path):
    g = GLTF2().load(str(path))
    blob = g.binary_blob()

    def png_of(tex_index):
        src = g.textures[tex_index].source
        bv = g.bufferViews[g.images[src].bufferView]
        off = bv.byteOffset or 0
        return bytes(blob[off: off + bv.byteLength])

    for i, m in enumerate(g.materials or []):
        pbr = m.pbrMetallicRoughness
        if pbr is not None and pbr.baseColorTexture is not None:
            albedo = png_of(pbr.baseColorTexture.index)
            normal = png_of(m.normalTexture.index) if m.normalTexture is not None else None
            return g, i, albedo, normal
    raise RuntimeError("no baseColorTexture in glb")


def _perlin(h, w, scale, rng):
    gh = h // scale + 2
    gw = w // scale + 2
    ang = rng.uniform(0.0, 2.0 * np.pi, (gh, gw)).astype(np.float32)
    gx = np.cos(ang)
    gy = np.sin(ang)
    y = np.arange(h, dtype=np.float32) / float(scale)
    x = np.arange(w, dtype=np.float32) / float(scale)
    yi = y.astype(np.int32)
    xi = x.astype(np.int32)
    yf = (y - yi)[:, None]
    xf = (x - xi)[None, :]
    u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
    v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)

    def corner(dy, dx):
        ry = (yi + dy)[:, None]
        rx = (xi + dx)[None, :]
        return gx[ry, rx] * (xf - dx) + gy[ry, rx] * (yf - dy)

    n0 = corner(0, 0) * (1.0 - u) + corner(0, 1) * u
    n1 = corner(1, 0) * (1.0 - u) + corner(1, 1) * u
    return (n0 * (1.0 - v) + n1 * v) * np.float32(1.41421356)


def _fractal_noise(h, w, scale, seed):
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w), np.float32)
    amp = 1.0
    amp_sum = 0.0
    s = max(int(scale), 2)
    for _ in range(3):
        total += amp * _perlin(h, w, s, rng)
        amp_sum += amp
        amp *= 0.5
        s = max(s // 2, 2)
    return total / amp_sum


def _cavity_map(normal_rgb):
    n = normal_rgb.astype(np.float32) / 127.5 - 1.0
    mag = np.zeros(n.shape[:2], np.float32)
    for c in range(3):
        sx = cv2.Sobel(n[..., c], cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(n[..., c], cv2.CV_32F, 0, 1, ksize=3)
        mag += sx * sx + sy * sy
    mag = cv2.GaussianBlur(np.sqrt(mag), (0, 0), 1.2)
    ref = float(np.percentile(mag, 99.0))
    if ref <= 1e-6:
        return np.zeros_like(mag)
    return np.clip(mag / ref, 0.0, 1.0)


def synthesize(albedo_rgb, normal_rgb, base, jitter, cavity_gain, dark_gain, seed):
    h, w = albedo_rgb.shape[:2]
    lum = (0.2126 * albedo_rgb[..., 0].astype(np.float32) +
           0.7152 * albedo_rgb[..., 1].astype(np.float32) +
           0.0722 * albedo_rgb[..., 2].astype(np.float32)) / 255.0
    rough = np.full((h, w), float(base), np.float32)
    cav_mean = 0.0
    if normal_rgb is not None:
        cav = _cavity_map(normal_rgb)
        rough += float(cavity_gain) * cav
        cav_mean = float(cav.mean())
    noise = _fractal_noise(h, w, max(4, min(h, w) // 128), seed)
    rough += float(jitter) * noise * (0.4 + 0.6 * lum)
    dark = np.clip((0.14 - lum) / 0.14, 0.0, 1.0)
    dark = cv2.GaussianBlur(dark, (0, 0), 2.0)
    rough += float(dark_gain) * dark
    return np.clip(rough, 0.0, 1.0), cav_mean


def _attach_texture(g, png_bytes):
    blob = bytearray(g.binary_blob())
    if len(blob) % 4:
        blob.extend(b"\x00" * (4 - len(blob) % 4))
    g.bufferViews.append(BufferView(buffer=0, byteOffset=len(blob), byteLength=len(png_bytes)))
    blob.extend(png_bytes)
    g.images.append(GltfImage(bufferView=len(g.bufferViews) - 1, mimeType="image/png"))
    g.textures.append(Texture(source=len(g.images) - 1))
    g.buffers[0].byteLength = len(blob)
    g.set_binary_blob(bytes(blob))
    return len(g.textures) - 1


def _run(a):
    g, mat_idx, albedo_png, normal_png = _load_glb_maps(a.glb)
    albedo = _decode_rgb(albedo_png)
    h0, w0 = albedo.shape[:2]
    s = float(a.size) / float(max(h0, w0))
    if s < 1.0:
        albedo = cv2.resize(albedo, (max(1, int(round(w0 * s))), max(1, int(round(h0 * s)))), interpolation=cv2.INTER_AREA)
    h, w = albedo.shape[:2]
    normal = None
    if normal_png is not None:
        normal = _decode_rgb(normal_png)
        if normal.shape[:2] != (h, w):
            normal = cv2.resize(normal, (w, h), interpolation=cv2.INTER_AREA)
    rough, cav_mean = synthesize(albedo, normal, a.base, a.jitter, a.cavity, a.dark, a.seed)
    rough_u8 = (rough * 255.0 + 0.5).astype(np.uint8)
    if not cv2.imwrite(a.output, rough_u8):
        raise RuntimeError("cannot write " + str(a.output))
    stats = {
        "min": round(float(rough.min()), 4),
        "max": round(float(rough.max()), 4),
        "mean": round(float(rough.mean()), 4),
        "std": round(float(rough.std()), 4),
        "cavity_mean": round(cav_mean, 4),
    }
    applied = None
    if a.apply:
        mr = np.empty((h, w, 3), np.uint8)
        mr[..., 0] = 255
        mr[..., 1] = rough_u8
        mr[..., 2] = 255
        ok, enc = cv2.imencode(".png", mr)
        if not ok:
            raise RuntimeError("png encode failed")
        tex = _attach_texture(g, enc.tobytes())
        pbr = g.materials[mat_idx].pbrMetallicRoughness
        pbr.metallicRoughnessTexture = TextureInfo(index=tex)
        pbr.roughnessFactor = 1.0
        g.save_binary(a.apply)
        applied = a.apply
    return {"glb": a.glb, "output": a.output, "size": [w, h], "base": a.base, "jitter": a.jitter,
            "normal_used": normal is not None, "stats": stats, "applied": applied}


def _build_test_glb(path):
    albedo = np.full((256, 256, 3), 128, np.uint8)
    albedo[:, :64] = 15
    normal = np.zeros((256, 256, 3), np.uint8)
    normal[...] = (128, 128, 255)
    yy, xx = np.mgrid[0:256, 0:256]
    checker = ((yy // 8 + xx // 8) % 2 == 0)
    bump = checker & (yy >= 160) & (xx >= 128)
    normal[bump] = (98, 158, 224)
    bump2 = (~checker) & (yy >= 160) & (xx >= 128)
    normal[bump2] = (158, 98, 224)
    pngs = []
    for arr in (albedo, normal):
        ok, enc = cv2.imencode(".png", cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError("selftest png encode failed")
        pngs.append(enc.tobytes())
    g = GLTF2()
    blob = bytearray()
    for png in pngs:
        if len(blob) % 4:
            blob.extend(b"\x00" * (4 - len(blob) % 4))
        g.bufferViews.append(BufferView(buffer=0, byteOffset=len(blob), byteLength=len(png)))
        blob.extend(png)
    g.images = [GltfImage(bufferView=0, mimeType="image/png"), GltfImage(bufferView=1, mimeType="image/png")]
    g.textures = [Texture(source=0), Texture(source=1)]
    g.materials = [Material(
        pbrMetallicRoughness=PbrMetallicRoughness(baseColorTexture=TextureInfo(index=0), metallicFactor=0.0, roughnessFactor=0.85),
        normalTexture=NormalMaterialTexture(index=1))]
    g.buffers = [Buffer(byteLength=len(blob))]
    g.set_binary_blob(bytes(blob))
    g.save_binary(path)


def _selftest():
    tmp = tempfile.mkdtemp(prefix="aurora_roughness_selftest_")
    glb = os.path.join(tmp, "test.glb")
    _build_test_glb(glb)
    out_png = os.path.join(tmp, "rough.png")
    out_glb = os.path.join(tmp, "test_rough.glb")
    a = argparse.Namespace(glb=glb, output=out_png, base=0.6, jitter=0.08, cavity=0.25, dark=0.07, size=256, seed=7, apply=out_glb)
    res = _run(a)
    rough = cv2.imread(out_png, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    mid = rough[8:150, 72:120]
    dark = rough[8:150, 8:56]
    bump = rough[170:250, 140:250]
    checks = {
        "non_uniform": bool(rough.std() > 0.01),
        "dark_rougher": bool(dark.mean() > mid.mean() + 0.02),
        "cavity_rougher": bool(bump.mean() > mid.mean() + 0.05),
        "base_respected": bool(abs(float(mid.mean()) - 0.6) < 0.1),
    }
    g2 = GLTF2().load(out_glb)
    pbr = g2.materials[0].pbrMetallicRoughness
    checks["mr_texture_attached"] = bool(pbr.metallicRoughnessTexture is not None)
    checks["roughness_factor_reset"] = bool(abs((pbr.roughnessFactor or 0.0) - 1.0) < 1e-6)
    blob2 = g2.binary_blob()
    src = g2.textures[pbr.metallicRoughnessTexture.index].source
    bv = g2.bufferViews[g2.images[src].bufferView]
    off = bv.byteOffset or 0
    mr_img = cv2.imdecode(np.frombuffer(blob2[off: off + bv.byteLength], np.uint8), cv2.IMREAD_COLOR)
    g_chan = mr_img[..., 1].astype(np.float32) / 255.0
    checks["g_channel_matches"] = bool(np.abs(g_chan - rough).max() <= 1.0 / 255.0)
    checks["b_channel_full"] = bool(int(mr_img[..., 0].min()) == 255)
    if not all(checks.values()):
        raise RuntimeError("selftest failed: " + json.dumps(checks))
    res["selftest"] = checks
    res["tmpdir"] = tmp
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb")
    ap.add_argument("--output")
    ap.add_argument("--base", type=float, default=0.6)
    ap.add_argument("--jitter", type=float, default=0.08)
    ap.add_argument("--cavity", type=float, default=0.25)
    ap.add_argument("--dark", type=float, default=0.07)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--apply", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    try:
        if a.selftest:
            res = _selftest()
        else:
            if not a.glb or not a.output:
                raise RuntimeError("--glb and --output are required")
            res = _run(a)
        res["ok"] = True
        res["ms"] = int((time.time() - t0) * 1000)
        _print_result(res)
    except Exception as e:
        _print_result({"ok": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
