import argparse
import base64
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from vlm_judge import ask_vlm

_RENDER_SCRIPT = _HERE / "render_views.py"
_RESULT_TAG = "AURORA_MATERIAL_VISION_RESULT:"
_CANALS = ("albedo", "roughness", "metallic", "normal", "emissive", "transmission")
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _print_result(d):
    print(_RESULT_TAG + json.dumps(d, ensure_ascii=True), flush=True)


def _find_blender():
    for c in (os.environ.get("AURORA_BLENDER"), os.environ.get("BLENDER_BIN"),
              os.path.expanduser("~/.local/bin/blender"), shutil.which("blender")):
        if c and os.path.isfile(c):
            return c
    return None


def _glb_context(glb_path):
    try:
        with open(glb_path, "rb") as fh:
            magic, _ver, _total = struct.unpack("<III", fh.read(12))
            if magic != 0x46546C67:
                return {}
            clen, _ctype = struct.unpack("<II", fh.read(8))
            j = json.loads(fh.read(clen))
        names = [m.get("name") for m in j.get("materials", []) if isinstance(m, dict)]
        return {
            "material_names": [n for n in names if n],
            "n_materials": len(j.get("materials", [])),
            "n_images": len(j.get("images", [])),
        }
    except Exception:
        return {}


def _render_views(glb, views_dir, timeout=1800):
    blender = _find_blender()
    if not blender:
        raise RuntimeError("blender introuvable")
    os.makedirs(views_dir, exist_ok=True)
    cmd = [blender, "-b", "--factory-startup", "-noaudio",
           "--python", str(_RENDER_SCRIPT), "--", str(glb), str(views_dir)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    try:
        with open(os.path.join(views_dir, "blender_render.log"), "w") as fh:
            fh.write((p.stdout or "") + "\n--- STDERR ---\n" + (p.stderr or ""))
    except OSError:
        pass
    if "DONE" not in (p.stdout or ""):
        raise RuntimeError("rendu blender incomplet: %s" % (p.stderr or p.stdout or "no output")[-400:])
    return _collect_views(views_dir)


def _collect_views(views_dir):
    pngs = sorted(Path(views_dir).glob("*.png"))
    if not pngs:
        raise RuntimeError("aucune vue png dans %s" % views_dir)
    return [str(p) for p in pngs[:4]]


def _norm(label):
    s = unicodedata.normalize("NFKD", str(label))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _tokens(label):
    return [t for t in _norm(label).split() if len(t) > 1]


def _token_eq(a, b):
    return a == b or (len(a) > 3 and len(b) > 3 and (a.startswith(b) or b.startswith(a)))


def _label_score(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.8
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    hit = sum(1 for x in ta if any(_token_eq(x, y) for y in tb))
    union = len(set(ta) | set(tb))
    return hit / union if union else 0.0


def _norm_canal(c):
    c = _norm(c).replace(" ", "")
    for known in _CANALS:
        if c and (c == known or c.startswith(known[:5])):
            return known
    aliases = {"basecolor": "albedo", "couleur": "albedo", "diffuse": "albedo",
               "rugosite": "roughness", "metal": "metallic", "emission": "emissive"}
    return aliases.get(c, c or "albedo")


def _valid_bbox(v):
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        return None
    try:
        b = [max(0, min(1000, int(round(float(x))))) for x in v]
    except (TypeError, ValueError):
        return None
    if b[0] >= b[2] or b[1] >= b[3]:
        return None
    return b


def _zones_key(manifest):
    for k in ("zones", "materials", "regions"):
        if isinstance(manifest.get(k), list):
            return k
    return None


def _zone_label(zone):
    for k in ("label", "name", "material", "zone"):
        if zone.get(k):
            return str(zone[k])
    return ""


def _zone_canal(zone):
    for k in ("canal_dominant", "canal", "channel", "dominant_channel"):
        if zone.get(k):
            return _norm_canal(zone[k])
    return ""


def _build_question(zone_labels, glb_ctx):
    lines = [
        "Tu analyses 4 rendus (vues 1 a 4, dans l'ordre des images) d'un meme objet 3D texture.",
        "Pour CHAQUE vue, liste les regions de materiaux visiblement distincts.",
        "Pour chaque region donne: label (nom court du materiau), bbox_0_1000 [x1,y1,x2,y2] "
        "coordonnees normalisees 0-1000 (origine coin haut-gauche), canal_dominant parmi: "
        + ", ".join(_CANALS) + ".",
    ]
    if zone_labels:
        lines.append("Materiaux predits par un classifieur (confirme, corrige ou ignore): "
                     + "; ".join(zone_labels[:24]) + ".")
    if glb_ctx.get("material_names"):
        lines.append("Noms de materiaux dans le fichier: " + ", ".join(glb_ctx["material_names"][:16]) + ".")
    lines.append("Ne liste que ce qui est reellement visible dans la vue concernee.")
    return "\n".join(lines)


_SCHEMA_HINT = json.dumps({
    "views": [{"view": 1, "regions": [
        {"label": "string", "bbox_0_1000": [0, 0, 1000, 1000], "canal_dominant": "albedo"}
    ]}]
}, ensure_ascii=True)


def _parse_vlm(data, n_views):
    per_view = {i: [] for i in range(1, n_views + 1)}
    raw_views = data.get("views") if isinstance(data, dict) else None
    if not isinstance(raw_views, list):
        return per_view
    for idx, entry in enumerate(raw_views):
        if not isinstance(entry, dict):
            continue
        try:
            vi = int(entry.get("view", idx + 1))
        except (TypeError, ValueError):
            vi = idx + 1
        if vi not in per_view:
            continue
        regions = entry.get("regions")
        if not isinstance(regions, list):
            continue
        for r in regions:
            if not isinstance(r, dict):
                continue
            label = str(r.get("label", "")).strip()
            if not label:
                continue
            per_view[vi].append({
                "label": label,
                "bbox_0_1000": _valid_bbox(r.get("bbox_0_1000", r.get("bbox"))),
                "canal_dominant": _norm_canal(r.get("canal_dominant", r.get("canal", ""))),
            })
    return per_view


def _majority(items):
    counts = {}
    for it in items:
        if it:
            counts[it] = counts.get(it, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _merge(manifest, per_view):
    zones_key = _zones_key(manifest) or "zones"
    zones = [dict(z) for z in manifest.get(zones_key, []) if isinstance(z, dict)]
    hits = {i: {"views": [], "bboxes": [], "canals": []} for i in range(len(zones))}
    extras = {}
    total_regions = 0
    for vi in sorted(per_view):
        for region in per_view[vi]:
            total_regions += 1
            best_i, best_s = None, 0.0
            for i, z in enumerate(zones):
                s = _label_score(region["label"], _zone_label(z))
                if s > best_s:
                    best_i, best_s = i, s
            if best_i is not None and best_s >= 0.5:
                h = hits[best_i]
                if vi not in h["views"]:
                    h["views"].append(vi)
                if region["bbox_0_1000"]:
                    h["bboxes"].append({"view": vi, "bbox_0_1000": region["bbox_0_1000"]})
                h["canals"].append(region["canal_dominant"])
            else:
                key = _norm(region["label"])
                e = extras.setdefault(key, {"label": region["label"], "views": [],
                                            "bboxes": [], "canals": []})
                if vi not in e["views"]:
                    e["views"].append(vi)
                if region["bbox_0_1000"]:
                    e["bboxes"].append({"view": vi, "bbox_0_1000": region["bbox_0_1000"]})
                e["canals"].append(region["canal_dominant"])

    kept, removed = [], []
    for i, z in enumerate(zones):
        h = hits[i]
        if not h["views"]:
            removed.append(_zone_label(z) or ("zone_%d" % i))
            continue
        prior = z.get("confidence")
        try:
            prior_f = min(1.0, max(0.0, float(prior)))
        except (TypeError, ValueError):
            prior_f = 0.5
        canal_vision = _majority(h["canals"])
        canal_match = bool(canal_vision) and canal_vision == _zone_canal(z)
        conf = prior_f + 0.08 * len(h["views"]) + (0.05 if canal_match else -0.1)
        z["confidence"] = round(min(0.99, max(0.05, conf)), 3)
        z["vision"] = {
            "status": "confirmed",
            "views_seen": h["views"],
            "canal_vision": canal_vision,
            "canal_match": canal_match,
            "bboxes": h["bboxes"],
            "confidence_prior": round(prior_f, 3),
        }
        kept.append(z)

    added = []
    for e in extras.values():
        canal = _majority(e["canals"]) or "albedo"
        nz = {
            "label": e["label"],
            "canal_dominant": canal,
            "confidence": round(min(0.85, 0.3 + 0.12 * len(e["views"])), 3),
            "source": "vision",
            "vision": {
                "status": "added",
                "views_seen": e["views"],
                "canal_vision": canal,
                "canal_match": True,
                "bboxes": e["bboxes"],
            },
        }
        kept.append(nz)
        added.append(e["label"])

    enriched = dict(manifest)
    enriched[zones_key] = kept
    enriched["vision"] = {
        "views": len(per_view),
        "regions": total_regions,
        "confirmed": len(kept) - len(added),
        "added": len(added),
        "removed": len(removed),
        "removed_labels": removed,
        "added_labels": added,
    }
    return enriched, zones_key


def run_pass(glb, manifest_path, output_path, workdir, skip_render=False,
             views_dir=None, timeout=120):
    os.makedirs(workdir, exist_ok=True)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    if isinstance(manifest, list):
        manifest = {"zones": manifest}
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest invalide: objet JSON attendu")

    if skip_render:
        views = _collect_views(views_dir or os.path.join(workdir, "views"))
    else:
        views = _render_views(glb, os.path.join(workdir, "views"))

    zones_key = _zones_key(manifest) or "zones"
    labels = []
    for z in manifest.get(zones_key, []):
        if isinstance(z, dict):
            lab = _zone_label(z)
            canal = _zone_canal(z)
            if lab:
                labels.append("%s (%s)" % (lab, canal) if canal else lab)

    glb_ctx = _glb_context(glb) if glb and os.path.isfile(str(glb)) else {}
    question = _build_question(labels, glb_ctx)
    answer = ask_vlm(views, question, schema_hint=_SCHEMA_HINT, timeout=timeout)
    per_view = _parse_vlm(answer, len(views))
    enriched, zones_key = _merge(manifest, per_view)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(enriched, fh, indent=2, ensure_ascii=True)
    v = enriched["vision"]
    return {
        "ok": True,
        "output": str(output_path),
        "views": v["views"],
        "regions_vision": v["regions"],
        "zones_key": zones_key,
        "zones_out": len(enriched[zones_key]),
        "confirmed": v["confirmed"],
        "added": v["added"],
        "removed": v["removed"],
        "view_files": [os.path.basename(p) for p in views],
    }


def _self_test():
    tmp = tempfile.mkdtemp(prefix="mvp_selftest_")
    old_mock = os.environ.get("AURORA_VLM_MOCK")
    try:
        views_dir = os.path.join(tmp, "views")
        os.makedirs(views_dir, exist_ok=True)
        for i in range(1, 5):
            with open(os.path.join(views_dir, "view_%02d.png" % i), "wb") as fh:
                fh.write(_TINY_PNG)

        manifest = {
            "schema": "aurora.material_manifest.v1",
            "zones": [
                {"label": "coque plastique noir", "canal_dominant": "roughness", "confidence": 0.6},
                {"label": "ecran verre", "canal_dominant": "metallic", "confidence": 0.5},
                {"label": "pieds caoutchouc", "canal_dominant": "roughness", "confidence": 0.4},
            ],
        }
        manifest_path = os.path.join(tmp, "manifest_in.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        mock = {"default": {"views": [
            {"view": 1, "regions": [
                {"label": "plastique noir", "bbox_0_1000": [100, 150, 900, 800], "canal_dominant": "roughness"},
                {"label": "ecran", "bbox_0_1000": [200, 200, 800, 500], "canal_dominant": "metallic"},
                {"label": "logo metal", "bbox_0_1000": [430, 600, 570, 680], "canal_dominant": "metallic"},
            ]},
            {"view": 2, "regions": [
                {"label": "plastique noir", "bbox_0_1000": [120, 160, 880, 790], "canal_dominant": "roughness"},
                {"label": "logo metal", "bbox_0_1000": [400, 580, 600, 700], "canal_dominant": "metallic"},
            ]},
            {"view": 3, "regions": [
                {"label": "plastique noir", "bbox_0_1000": [90, 140, 910, 810], "canal_dominant": "roughness"},
            ]},
            {"view": 4, "regions": [
                {"label": "ecran verre", "bbox_0_1000": [220, 210, 780, 520], "canal_dominant": "albedo"},
            ]},
        ]}}
        mock_path = os.path.join(tmp, "vlm_mock.json")
        with open(mock_path, "w", encoding="utf-8") as fh:
            json.dump(mock, fh)
        os.environ["AURORA_VLM_MOCK"] = mock_path

        out_path = os.path.join(tmp, "manifest_out.json")
        res = run_pass(None, manifest_path, out_path, tmp,
                       skip_render=True, views_dir=views_dir)
        with open(out_path, "r", encoding="utf-8") as fh:
            enriched = json.load(fh)

        labels = {_norm(_zone_label(z)): z for z in enriched["zones"]}
        assert res["views"] == 4, res
        assert res["regions_vision"] == 7, res
        assert "coque plastique noir" in labels, labels.keys()
        assert "ecran verre" in labels, labels.keys()
        assert "logo metal" in labels, labels.keys()
        assert "pieds caoutchouc" not in labels, labels.keys()
        coque = labels["coque plastique noir"]
        assert coque["vision"]["status"] == "confirmed"
        assert coque["vision"]["views_seen"] == [1, 2, 3]
        assert coque["vision"]["canal_match"] is True
        assert coque["confidence"] > 0.6
        ecran = labels["ecran verre"]
        assert ecran["vision"]["views_seen"] == [1, 4]
        logo = labels["logo metal"]
        assert logo["source"] == "vision"
        assert logo["canal_dominant"] == "metallic"
        assert logo["vision"]["views_seen"] == [1, 2]
        assert enriched["vision"]["views"] == 4
        assert enriched["vision"]["regions"] == 7
        assert enriched["vision"]["removed_labels"] == ["pieds caoutchouc"]
        assert res["confirmed"] == 2 and res["added"] == 1 and res["removed"] == 1
        return {"ok": True, "self_test": "pass", "checks": 15,
                "views": res["views"], "regions_vision": res["regions_vision"]}
    finally:
        if old_mock is None:
            os.environ.pop("AURORA_VLM_MOCK", None)
        else:
            os.environ["AURORA_VLM_MOCK"] = old_mock
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--skip-render", action="store_true", dest="skip_render")
    ap.add_argument("--views-dir", default=None, dest="views_dir")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--self-test", action="store_true", dest="self_test")
    a = ap.parse_args()

    if a.self_test:
        try:
            result = _self_test()
        except Exception as exc:
            result = {"ok": False, "self_test": "fail", "error": repr(exc)}
        _print_result(result)
        sys.exit(0 if result["ok"] else 1)

    if not a.manifest or not a.output:
        _print_result({"ok": False, "error": "--manifest et --output requis"})
        sys.exit(1)
    if not a.skip_render and not a.glb:
        _print_result({"ok": False, "error": "--glb requis sans --skip-render"})
        sys.exit(1)

    workdir = a.workdir or tempfile.mkdtemp(prefix="material_vision_")
    try:
        result = run_pass(a.glb, a.manifest, a.output, workdir,
                          skip_render=a.skip_render, views_dir=a.views_dir,
                          timeout=a.timeout)
    except Exception as exc:
        result = {"ok": False, "error": repr(exc), "output": a.output}
    finally:
        if not a.workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    _print_result(result)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
