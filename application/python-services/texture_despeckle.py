import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def _detect_fluide(arr, couleur="bleu"):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 1e-5, (mx - mn) / np.maximum(mx, 1e-5), 0.0)
    if couleur == "chaud":
        return (r > b * 1.2) & (r > g * 1.05) & (mx > 0.3)
    return ((b > r * 1.15) & (b > g * 1.04) & (mx > 0.18)) | ((mx > 0.82) & (sat < 0.10) & (b >= r))


def despeckle_glb(glb_path, output_path, mask_out=None, couleur="bleu"):
    import cv2
    import pygltflib
    g = pygltflib.GLTF2().load(str(glb_path))
    mat = g.materials[0]
    ti = mat.pbrMetallicRoughness.baseColorTexture.index
    img_idx = g.textures[ti].source
    bv = g.bufferViews[g.images[img_idx].bufferView]
    blob = g.binary_blob()
    off = bv.byteOffset or 0
    atlas = Image.open(io.BytesIO(blob[off: off + bv.byteLength])).convert("RGB")
    W, H = atlas.size
    arr = np.asarray(atlas, dtype=np.float32) / 255.0
    fluide = _detect_fluide(arr, couleur).astype(np.uint8)

    k = max(9, (max(W, H) // 380) | 1)
    noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    grande = cv2.morphologyEx(fluide, cv2.MORPH_OPEN, noyau)
    grande = cv2.morphologyEx(grande, cv2.MORPH_CLOSE, noyau)
    zone_ok = cv2.dilate(grande, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k * 2 + 1, k * 2 + 1)))
    moucheture = (fluide.astype(bool) & ~zone_ok.astype(bool)).astype(np.uint8)
    n_mouch = int(moucheture.sum())
    if n_mouch:
        moucheture_d = cv2.dilate(moucheture, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        bgr = cv2.cvtColor((arr * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        propre = cv2.inpaint(bgr, moucheture_d * 255, 5, cv2.INPAINT_TELEA)
        rgb = cv2.cvtColor(propre, cv2.COLOR_BGR2RGB)
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="PNG")
        import glb_material_writer as gmw
        gmw._replace_glb_image(g, img_idx, buf.getvalue())
        g.images[img_idx].mimeType = "image/png"
    g.save_binary(str(output_path))
    if mask_out:
        flou = cv2.GaussianBlur(grande * 255, (0, 0), 3)
        Image.fromarray(flou.astype(np.uint8)).save(str(mask_out))
    return {"ok": True, "mouchetures_purgees_px": n_mouch,
            "part_eau": round(float(grande.mean()), 4), "output": str(output_path)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--mask-out", dest="mask_out")
    ap.add_argument("--couleur", default="bleu")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    r = despeckle_glb(a.glb, a.output, mask_out=a.mask_out, couleur=a.couleur)
    print("AURORA_DESPECKLE_RESULT:" + json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
