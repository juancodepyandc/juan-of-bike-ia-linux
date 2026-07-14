"""Orchestrateur host de composition de scene 3D (parse instruction + lance Blender)."""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

OLLAMA_URL = os.environ.get("AURORA_OLLAMA_URL", "http://127.0.0.1:11434")
BLENDER_BIN = os.environ.get("AURORA_BLENDER", os.path.expanduser("~/.local/bin/blender"))
RELATIONS = ("sit_on", "stand_on", "lie_on", "next_to", "hold")
SYSTEM_PROMPT = (
    "Tu extrais la relation spatiale d'une instruction de scene 3D entre un acteur et un objet cible. "
    'Reponds uniquement en JSON strict: {"relation": "<sit_on|stand_on|lie_on|next_to|hold>", "animate": <true|false>}. '
    "animate=true si l'instruction decrit un deplacement ou un mouvement (marcher, courir, s'approcher, se lever)."
)


def _strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def parse_instruction_llm(text):
    import requests
    payload = {
        "model": "gemma3:27b",
        "format": "json",
        "think": False,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    }
    resp = requests.post(OLLAMA_URL + "/api/chat", json=payload, timeout=60)
    resp.raise_for_status()
    data = json.loads(resp.json()["message"]["content"])
    relation = data.get("relation")
    if relation not in RELATIONS:
        raise ValueError("relation invalide: %r" % relation)
    return {"relation": relation, "animate": bool(data.get("animate"))}


def parse_instruction_regex(text):
    t = _strip_accents(text.lower())
    relation = "next_to"
    if re.search(r"s'?\s*assoi|s'?\s*assied|s'?\s*asseoir|\bassis(e|es)?\b|\bsit(s|ting)?\b|\bseat(s|ed)?\b", t):
        relation = "sit_on"
    elif re.search(r"s'?\s*allonge|s'?\s*etend|\bcouche\b|\blie(s)?\b|lying|lie down", t):
        relation = "lie_on"
    elif re.search(r"debout sur|se tient sur|se met debout|monte sur|stand(s|ing)? on", t):
        relation = "stand_on"
    elif re.search(r"\btient\b|\btenir\b|\bporte\b|\bprend\b|\bhold(s|ing)?\b|\bcarr(y|ies)\b|\bgrab(s)?\b", t):
        relation = "hold"
    elif re.search(r"a cote|aupres de|pres de|next to|beside|\bnear\b", t):
        relation = "next_to"
    animate = bool(re.search(
        r"\bmarche\b|\bcourt\b|s'?\s*approche|s'?\s*avance|se leve|se deplace|se dirige|"
        r"\brejoint\b|va vers|\bvient\b|\bpuis\b|\bmonte\b|\bwalk(s|ing)?\b|\brun(s|ning)?\b|"
        r"approach(es)?|moves? (to|toward)|gets? up|\bthen\b", t))
    return {"relation": relation, "animate": animate}


def parse_instruction(text):
    if os.environ.get("AURORA_SCENE_NO_LLM"):
        return parse_instruction_regex(text)
    try:
        return parse_instruction_llm(text)
    except Exception:
        return parse_instruction_regex(text)


def _glb_has_skin(path):
    try:
        import struct
        with open(path, "rb") as f:
            head = f.read(20)
            if len(head) < 20 or head[:4] != b"glTF":
                return False
            jlen = struct.unpack("<I", head[12:16])[0]
            doc = json.loads(f.read(jlen))
        return bool(doc.get("skins"))
    except Exception:
        return False


def run_blender(actor, target, relation, output, animate, fps, overrides=None):
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_compose_bpy.py")
    cmd = [BLENDER_BIN, "--background", "--factory-startup",
           "--python-exit-code", "1", "--python", script, "--",
           "--actor", actor, "--target", target,
           "--relation", relation, "--output", output]
    if animate:
        cmd += ["--animate", "--fps", str(fps)]
    for flag, value in (overrides or {}).items():
        if value is not None:
            cmd += ["--" + flag, str(value)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1740)
    payload = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("SCENE_RESULT:"):
            try:
                payload = json.loads(line[len("SCENE_RESULT:"):])
            except ValueError:
                payload = None
            break
    if payload is None:
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-800:]
        return {"ok": False, "error": "blender sans SCENE_RESULT (code %s): %s" % (proc.returncode, tail)}
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--animate", action="store_true")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--seat-height-frac", type=float, default=None, dest="seat_height_frac")
    parser.add_argument("--seat-depth-frac", type=float, default=None, dest="seat_depth_frac")
    parser.add_argument("--scale-mul", type=float, default=None, dest="scale_mul")
    parser.add_argument("--strategy", default=None,
                        choices=["legs_bent", "edge", "stand", "lie", "none"])
    parser.add_argument("--dz-frac", type=float, default=None, dest="dz_frac")
    parser.add_argument("--dfwd-frac", type=float, default=None, dest="dfwd_frac")
    # Tailles REELLES (metres). Les objets sont generes normalises: sans elles, un
    # homme et une chaise font la meme hauteur.
    parser.add_argument("--actor-height-m", type=float, default=None,
                        dest="actor_height_m")
    parser.add_argument("--target-height-m", type=float, default=None,
                        dest="target_height_m")
    args = parser.parse_args()
    parsed = parse_instruction(args.instruction)
    relation = parsed["relation"]
    strategy_relations = {"legs_bent": "sit_on", "edge": "sit_on", "stand": "stand_on", "lie": "lie_on"}
    if args.strategy in strategy_relations:
        relation = strategy_relations[args.strategy]
    overrides = {"seat-height-frac": args.seat_height_frac,
                 "seat-depth-frac": args.seat_depth_frac,
                 "scale-mul": args.scale_mul,
                 "actor-height-m": args.actor_height_m,
                 "target-height-m": args.target_height_m,
                 "strategy": args.strategy,
                 "dz-frac": args.dz_frac,
                 "dfwd-frac": args.dfwd_frac}
    animate = bool(args.animate or parsed["animate"])
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    actor_path = args.actor
    rigged = False
    if (relation in ("sit_on", "lie_on") and args.strategy in (None, "legs_bent")
            and not _glb_has_skin(actor_path)):
        rig_out = os.path.join(out_dir, "actor_rigged.glb")
        rig_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rigify_autorig.py")
        try:
            rig_cmd = [sys.executable, rig_script, "--input", actor_path, "--output", rig_out]
            if relation == "sit_on":
                rig_cmd += ["--pose", "sit"]
            rp = subprocess.run(rig_cmd, capture_output=True, text=True, timeout=1500)
            if rp.returncode == 0 and os.path.isfile(rig_out) and os.path.getsize(rig_out) > 1000000:
                actor_path = rig_out
                rigged = True
        except Exception:
            pass
    try:
        scene = run_blender(actor_path, args.target, relation, args.output, animate, args.fps,
                            overrides=overrides)
    except subprocess.TimeoutExpired:
        scene = {"ok": False, "error": "blender timeout (1740s)"}
    except FileNotFoundError as exc:
        scene = {"ok": False, "error": "blender introuvable: %s" % exc}
    final = {
        "ok": bool(scene.get("ok")) and os.path.isfile(args.output),
        "output": args.output,
        "relation": relation,
        "strategy": args.strategy,
        "overrides": {k: v for k, v in overrides.items() if v is not None},
        # l'echelle reellement appliquee doit REMONTER: sans elle, impossible de
        # savoir si la mise a l'echelle a eu lieu (la charge utile est une liste
        # blanche de cles, et tout le reste est silencieusement jete).
        "scale_from_real_size": scene.get("scale_from_real_size"),
        "animated": bool(scene.get("animated")),
        "contact_gap": scene.get("contact_gap"),
        "overlap_fixed": scene.get("overlap_fixed"),
        "seat_height": scene.get("seat_height"),
        "has_armature": scene.get("has_armature"),
        "posed": scene.get("posed"),
        "auto_rigged": rigged,
        "overlap_zone0": scene.get("overlap_zone0"),
        "overlap_zone": scene.get("overlap_zone"),
        "skin_built": scene.get("skin_built"),
        "fit": scene.get("fit"),
        "sit_fallback": scene.get("sit_fallback"),
        "seat_override": scene.get("seat_override"),
        "seat_depth_override": scene.get("seat_depth_override"),
        "scale_mul": scene.get("scale_mul"),
        "offset_applied": scene.get("offset_applied"),
    }
    if scene.get("error"):
        final["error"] = scene["error"]
    elif bool(scene.get("ok")) and not os.path.isfile(args.output):
        final["error"] = "export absent: %s" % args.output
    print("AURORA_SCENE_RESULT:" + json.dumps(final))
    sys.stdout.flush()
    sys.exit(0 if final["ok"] else 1)


if __name__ == "__main__":
    main()
