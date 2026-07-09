import argparse
import copy
import json
import sys

SCHEMA_ID = "aurora.material-intel.v1"

LABELS = {
    "glass", "water", "skin", "fabric", "fur", "brushed_metal", "led",
    "screen", "smoke", "metal", "wood", "stone", "plastic", "paint_gloss",
}

COLOR_CHANNELS = {"attenuationColor", "sheenColor", "emissiveFactor"}

CHANNEL_CLAMPS = {
    "transmission": (0.0, 1.0),
    "ior": (1.0, 2.5),
    "thickness": (0.0, 1000.0),
    "roughness": (0.0, 1.0),
    "metallic": (0.0, 1.0),
    "sheen": (0.0, 1.0),
    "clearcoat": (0.0, 1.0),
    "clearcoatRoughness": (0.0, 1.0),
    "anisotropy": (-6.2831853, 6.2831853),
    "anisotropyStrength": (0.0, 1.0),
    "specular": (0.0, 1.0),
    "emissiveStrength": (0.0, 20.0),
}

ALL_CHANNELS = set(CHANNEL_CLAMPS) | COLOR_CHANNELS


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_color(value):
    if isinstance(value, str):
        h = value.strip().lstrip("#")
        if len(h) == 3 and all(c in "0123456789abcdefABCDEF" for c in h):
            h = "".join(c * 2 for c in h)
        if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
            return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return None
    if isinstance(value, (list, tuple)) and len(value) == 3 and all(_is_number(c) for c in value):
        vals = [float(c) for c in value]
        if max(vals) > 1.0:
            vals = [c / 255.0 for c in vals]
        return tuple(min(1.0, max(0.0, c)) for c in vals)
    return None


def color_to_hex(rgb):
    return "#" + "".join("{:02x}".format(int(round(min(1.0, max(0.0, c)) * 255))) for c in rgb)


def _clamp(v, lo, hi):
    return min(hi, max(lo, float(v)))


def validate(manifest):
    errors = []
    if not isinstance(manifest, dict):
        return False, ["manifest doit etre un objet JSON"]
    if manifest.get("schema") != SCHEMA_ID:
        errors.append("schema invalide: attendu '%s', recu %r" % (SCHEMA_ID, manifest.get("schema")))
    zones = manifest.get("zones")
    if not isinstance(zones, list):
        errors.append("zones doit etre une liste")
        return False, errors
    seen_ids = set()
    for i, zone in enumerate(zones):
        prefix = "zones[%d]" % i
        if not isinstance(zone, dict):
            errors.append("%s doit etre un objet" % prefix)
            continue
        zone_id = zone.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id.strip():
            errors.append("%s.zone_id doit etre une chaine non vide" % prefix)
        elif zone_id in seen_ids:
            errors.append("%s.zone_id '%s' duplique" % (prefix, zone_id))
        else:
            seen_ids.add(zone_id)
        label = zone.get("label")
        if label not in LABELS:
            errors.append("%s.label %r invalide (attendu: %s)" % (prefix, label, "|".join(sorted(LABELS))))
        target = zone.get("target")
        if not isinstance(target, dict):
            errors.append("%s.target doit etre un objet" % prefix)
        else:
            mi = target.get("material_index")
            if not isinstance(mi, int) or isinstance(mi, bool) or mi < 0:
                errors.append("%s.target.material_index doit etre un entier >= 0" % prefix)
            mask = target.get("mask_png")
            if mask is not None and (not isinstance(mask, str) or not mask.strip()):
                errors.append("%s.target.mask_png doit etre une chaine non vide" % prefix)
        channels = zone.get("channels")
        if not isinstance(channels, dict):
            errors.append("%s.channels doit etre un objet" % prefix)
        else:
            for key, val in channels.items():
                if key not in ALL_CHANNELS:
                    errors.append("%s.channels.%s inconnu" % (prefix, key))
                elif key in COLOR_CHANNELS:
                    if parse_color(val) is None:
                        errors.append("%s.channels.%s couleur invalide: %r" % (prefix, key, val))
                elif not _is_number(val):
                    errors.append("%s.channels.%s doit etre numerique" % (prefix, key))
        conf = zone.get("confidence")
        if not _is_number(conf):
            errors.append("%s.confidence doit etre numerique" % prefix)
        source = zone.get("source")
        if not isinstance(source, str) or not source.strip():
            errors.append("%s.source doit etre une chaine non vide" % prefix)
    return len(errors) == 0, errors


def normalize(manifest):
    out = copy.deepcopy(manifest) if isinstance(manifest, dict) else {}
    out["schema"] = SCHEMA_ID
    zones = out.get("zones")
    if not isinstance(zones, list):
        out["zones"] = []
        return out
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        channels = zone.get("channels")
        if isinstance(channels, dict):
            cleaned = {}
            for key, val in channels.items():
                if key in COLOR_CHANNELS:
                    rgb = parse_color(val)
                    if rgb is not None:
                        cleaned[key] = color_to_hex(rgb)
                elif key in CHANNEL_CLAMPS and _is_number(val):
                    lo, hi = CHANNEL_CLAMPS[key]
                    cleaned[key] = _clamp(val, lo, hi)
            zone["channels"] = cleaned
        if _is_number(zone.get("confidence")):
            zone["confidence"] = _clamp(zone["confidence"], 0.0, 1.0)
    return out


def _self_test():
    checks = {}
    valid = {
        "schema": SCHEMA_ID,
        "zones": [
            {
                "zone_id": "hull",
                "label": "paint_gloss",
                "target": {"material_index": 0},
                "channels": {"clearcoat": 1.0, "clearcoatRoughness": 0.1, "roughness": 0.3},
                "confidence": 0.9,
                "source": "self_test",
            },
            {
                "zone_id": "logo_led",
                "label": "led",
                "target": {"material_index": 0, "mask_png": "mask.png"},
                "channels": {"emissiveFactor": "#ff2040", "emissiveStrength": 50.0},
                "confidence": 1.4,
                "source": "self_test",
            },
        ],
    }
    ok, errs = validate(valid)
    checks["valid_manifest_passes"] = ok and errs == []
    norm = normalize(valid)
    z0 = norm["zones"][0]["channels"]
    z1 = norm["zones"][1]["channels"]
    checks["clamp_emissive_strength"] = z1["emissiveStrength"] == 20.0
    checks["confidence_clamped"] = norm["zones"][1]["confidence"] == 1.0
    checks["color_kept_hex"] = z1["emissiveFactor"] == "#ff2040"
    checks["clearcoat_kept"] = z0["clearcoat"] == 1.0
    clampy = {
        "schema": SCHEMA_ID,
        "zones": [{
            "zone_id": "g", "label": "glass",
            "target": {"material_index": 1},
            "channels": {"transmission": 1.7, "ior": 9.0, "attenuationColor": [1.0, 0.0, 0.0], "sheenColor": "0F8", "bogus": 3},
            "confidence": 0.5, "source": "t",
        }],
    }
    ok2, errs2 = validate(clampy)
    checks["unknown_channel_flagged"] = (not ok2) and any("bogus" in e for e in errs2)
    n2 = normalize(clampy)["zones"][0]["channels"]
    checks["clamp_transmission"] = n2["transmission"] == 1.0
    checks["clamp_ior"] = n2["ior"] == 2.5
    checks["color_list_to_hex"] = n2["attenuationColor"] == "#ff0000"
    checks["color_short_hex"] = n2["sheenColor"] == "#00ff88"
    checks["unknown_channel_dropped"] = "bogus" not in n2
    bad = {
        "schema": "wrong.v9",
        "zones": [{
            "zone_id": "", "label": "chrome",
            "target": {"material_index": -1},
            "channels": {"emissiveFactor": "notacolor"},
            "confidence": "high", "source": "",
        }],
    }
    ok3, errs3 = validate(bad)
    checks["bad_manifest_fails"] = (not ok3) and len(errs3) >= 6
    checks["not_dict_fails"] = validate([1, 2])[0] is False
    return {"ok": all(checks.values()), "checks": checks, "schema": SCHEMA_ID}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--output")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        result = _self_test()
    elif a.manifest:
        result = {"ok": False, "schema": SCHEMA_ID}
        try:
            with open(a.manifest, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            ok, errors = validate(manifest)
            result["ok"] = ok
            result["errors"] = errors
            result["zones"] = len(manifest.get("zones", [])) if isinstance(manifest, dict) else 0
            if ok and a.output:
                with open(a.output, "w", encoding="utf-8") as fh:
                    json.dump(normalize(manifest), fh, ensure_ascii=False, indent=2)
                result["output"] = a.output
        except Exception as exc:
            result["errors"] = [repr(exc)]
    else:
        result = {"ok": False, "errors": ["--manifest ou --self-test requis"]}
    print("AURORA_MATERIAL_MANIFEST_RESULT:" + json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
