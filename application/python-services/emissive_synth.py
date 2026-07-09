import argparse
import json
import os
import sys
import tempfile
import time

import cv2
import numpy as np
from pygltflib import GLTF2, Buffer, BufferView, Image as GltfImage, Material, PbrMetallicRoughness, Texture, TextureInfo

HUE_RANGES = {
    "red": ((0, 10), (170, 179)),
    "orange": ((10, 22),),
    "yellow": ((22, 35),),
    "green": ((35, 85),),
    "cyan": ((85, 100),),
    "blue": ((100, 130),),
    "purple": ((125, 152),),
    "violet": ((125, 152),),
    "magenta": ((140, 172),),
    "pink": ((140, 179), (0, 8)),
    "rose": ((140, 179), (0, 8)),
    "rgb": ((0, 179),),
    "led": ((0, 179),),
    "white": (),
}


def _print_result(d):
    print("AURORA_EMISSIVE_RESULT:" + json.dumps(d), flush=True)


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


def _load_glb_albedo(path):
    g = GLTF2().load(str(path))
    blob = g.binary_blob()
    for i, m in enumerate(g.materials or []):
        pbr = m.pbrMetallicRoughness
        if pbr is not None and pbr.baseColorTexture is not None:
            src = g.textures[pbr.baseColorTexture.index].source
            bv = g.bufferViews[g.images[src].bufferView]
            off = bv.byteOffset or 0
            return g, i, bytes(blob[off: off + bv.byteLength])
    raise RuntimeError("no baseColorTexture in glb")


def _parse_hues(spec):
    if not spec:
        return []
    names = [t.strip().lower() for t in spec.split(",") if t.strip()]
    return [n for n in names if n in HUE_RANGES]


def build_mask(rgb, sat_min, val_min, hues):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hch = hsv[..., 0].astype(np.int32)
    s = hsv[..., 1].astype(np.float32) / 255.0
    v = hsv[..., 2].astype(np.float32) / 255.0
    sat_mask = (s > float(sat_min)) & (v > float(val_min))
    white_mask = (v > 0.92) & (s < 0.12)
    if hues:
        allow = np.zeros(hch.shape, bool)
        keep_white = False
        for name in hues:
            if name in ("led", "white"):
                keep_white = True
            for lo, hi in HUE_RANGES.get(name, ()):
                allow |= (hch >= lo) & (hch <= hi)
        sat_mask &= allow
        if not keep_white:
            white_mask[:] = False
    mask = ((sat_mask | white_mask).astype(np.uint8)) * 255
    h, w = mask.shape
    ks = max(3, (min(h, w) // 512) * 2 + 1)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    n, labels, stats_cc, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    min_area = max(16, (h * w) // 100000)
    kept = 0
    for i in range(1, n):
        if stats_cc[i, cv2.CC_STAT_AREA] < min_area:
            mask[labels == i] = 0
        else:
            kept += 1
    return mask, kept, ks


def _circular_mean_hue_deg(hch, mask):
    sel = hch[mask > 0].astype(np.float32) * 2.0
    if sel.size == 0:
        return None
    rad = np.deg2rad(sel)
    ang = np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())
    return round(float(np.rad2deg(ang)) % 360.0, 1)


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
    g, mat_idx, albedo_png = _load_glb_albedo(a.glb)
    albedo = _decode_rgb(albedo_png)
    h0, w0 = albedo.shape[:2]
    sc = float(a.size) / float(max(h0, w0))
    if sc < 1.0:
        albedo = cv2.resize(albedo, (max(1, int(round(w0 * sc))), max(1, int(round(h0 * sc)))), interpolation=cv2.INTER_AREA)
    h, w = albedo.shape[:2]
    hues = _parse_hues(a.hues)
    mask, components, ks = build_mask(albedo, a.sat_min, a.val_min, hues)
    soft = cv2.GaussianBlur(mask, (0, 0), max(1.0, ks / 2.0)).astype(np.float32) / 255.0
    emissive = (albedo.astype(np.float32) * soft[..., None]).astype(np.uint8)
    if not cv2.imwrite(a.output, cv2.cvtColor(emissive, cv2.COLOR_RGB2BGR)):
        raise RuntimeError("cannot write " + str(a.output))
    coverage = float((mask > 0).mean()) * 100.0
    hsv = cv2.cvtColor(albedo, cv2.COLOR_RGB2HSV)
    mean_hue = _circular_mean_hue_deg(hsv[..., 0].astype(np.int32), mask)
    sel = albedo[mask > 0]
    mean_rgb = [int(x) for x in sel.mean(axis=0)] if sel.size else [0, 0, 0]
    applied = None
    if a.apply:
        ok, enc = cv2.imencode(".png", cv2.cvtColor(emissive, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError("png encode failed")
        tex = _attach_texture(g, enc.tobytes())
        m = g.materials[mat_idx]
        m.emissiveTexture = TextureInfo(index=tex)
        m.emissiveFactor = [1.0, 1.0, 1.0]
        exts = dict(m.extensions or {})
        exts["KHR_materials_emissive_strength"] = {"emissiveStrength": float(a.strength)}
        m.extensions = exts
        used = list(g.extensionsUsed or [])
        if "KHR_materials_emissive_strength" not in used:
            used.append("KHR_materials_emissive_strength")
        g.extensionsUsed = used
        g.save_binary(a.apply)
        applied = a.apply
    return {"glb": a.glb, "output": a.output, "size": [w, h], "hues": hues, "strength": a.strength,
            "coverage_pct": round(coverage, 3), "components": components,
            "mean_hue_deg": mean_hue, "mean_rgb": mean_rgb, "applied": applied}


def _build_test_glb(path):
    albedo = np.full((256, 256, 3), 60, np.uint8)
    albedo[:, :64] = 18
    albedo[96:160, 96:160] = (230, 30, 160)
    albedo[40:72, 180:220] = 250
    rng = np.random.default_rng(3)
    ys = rng.integers(8, 248, 20)
    xs = rng.integers(4, 60, 20)
    albedo[ys, xs] = (255, 0, 0)
    ok, enc = cv2.imencode(".png", cv2.cvtColor(albedo, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("selftest png encode failed")
    png = enc.tobytes()
    g = GLTF2()
    g.bufferViews = [BufferView(buffer=0, byteOffset=0, byteLength=len(png))]
    g.images = [GltfImage(bufferView=0, mimeType="image/png")]
    g.textures = [Texture(source=0)]
    g.materials = [Material(pbrMetallicRoughness=PbrMetallicRoughness(baseColorTexture=TextureInfo(index=0), metallicFactor=0.0, roughnessFactor=0.85))]
    g.buffers = [Buffer(byteLength=len(png))]
    g.set_binary_blob(png)
    g.save_binary(path)


def _selftest():
    tmp = tempfile.mkdtemp(prefix="aurora_emissive_selftest_")
    glb = os.path.join(tmp, "test.glb")
    _build_test_glb(glb)
    out_png = os.path.join(tmp, "emissive.png")
    out_glb = os.path.join(tmp, "test_emissive.glb")
    a = argparse.Namespace(glb=glb, output=out_png, hues="", strength=5.0, sat_min=0.55, val_min=0.65, size=256, apply=out_glb)
    res = _run(a)
    g2 = GLTF2().load(glb)
    blob = g2.binary_blob()
    bv = g2.bufferViews[g2.images[0].bufferView]
    albedo = _decode_rgb(bytes(blob[bv.byteOffset or 0: (bv.byteOffset or 0) + bv.byteLength]))
    mask, components, _ = build_mask(albedo, 0.55, 0.65, [])
    pink = (mask[100:156, 100:156] > 0).mean()
    white = (mask[44:68, 184:216] > 0).mean()
    outside = mask.copy()
    outside[96:160, 96:160] = 0
    outside[40:72, 180:220] = 0
    checks = {
        "pink_patch_detected": bool(pink > 0.7),
        "white_patch_detected": bool(white > 0.7),
        "background_clean": bool(float((outside > 0).mean()) < 0.005),
        "two_components": bool(components == 2),
    }
    mask_pink, comp_pink, _ = build_mask(albedo, 0.55, 0.65, ["pink"])
    checks["hues_pink_keeps_pink"] = bool((mask_pink[100:156, 100:156] > 0).mean() > 0.7)
    checks["hues_pink_drops_white"] = bool((mask_pink[44:68, 184:216] > 0).mean() < 0.05)
    mask_blue, comp_blue, _ = build_mask(albedo, 0.55, 0.65, ["blue"])
    checks["hues_blue_drops_pink"] = bool((mask_blue > 0).mean() < 0.001)
    ga = GLTF2().load(out_glb)
    m = ga.materials[0]
    checks["emissive_texture_attached"] = bool(m.emissiveTexture is not None)
    checks["emissive_factor_white"] = bool(list(m.emissiveFactor or []) == [1.0, 1.0, 1.0])
    ext = (m.extensions or {}).get("KHR_materials_emissive_strength", {})
    checks["strength_set"] = bool(abs(float(ext.get("emissiveStrength", 0.0)) - 5.0) < 1e-6)
    checks["extension_declared"] = bool("KHR_materials_emissive_strength" in (ga.extensionsUsed or []))
    if not all(checks.values()):
        raise RuntimeError("selftest failed: " + json.dumps(checks))
    res["selftest"] = checks
    res["tmpdir"] = tmp
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb")
    ap.add_argument("--output")
    ap.add_argument("--apply", default=None)
    ap.add_argument("--hues", default="")
    ap.add_argument("--strength", type=float, default=5.0)
    ap.add_argument("--sat-min", type=float, default=0.55, dest="sat_min")
    ap.add_argument("--val-min", type=float, default=0.65, dest="val_min")
    ap.add_argument("--size", type=int, default=2048)
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
