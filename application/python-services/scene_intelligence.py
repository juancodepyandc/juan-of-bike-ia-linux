import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlm_judge import ask_vlm

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_BIN = os.environ.get("AURORA_BLENDER", os.path.expanduser("~/.local/bin/blender"))
RENDER_SCRIPT = os.environ.get("AURORA_RENDER_SCRIPT", os.path.join(HERE, "render_views.py"))
COMPOSER = os.path.join(HERE, "scene_composer.py")
RELATIONS = ("sit_on", "stand_on", "lie_on", "next_to", "hold")
STRATEGIES = ("legs_bent", "edge", "stand", "lie", "none")
SIDES = ("front", "back", "left", "right")


def _clampf(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def render_views(glb, outdir):
    os.makedirs(outdir, exist_ok=True)
    cmd = [BLENDER_BIN, "--background", "--factory-startup",
           "--python", RENDER_SCRIPT, "--", str(glb), str(outdir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    images = sorted(os.path.join(outdir, f) for f in os.listdir(outdir) if f.lower().endswith(".png"))
    if not images:
        raise RuntimeError("rendu sans image (code %s): %s"
                           % (proc.returncode, (proc.stderr or proc.stdout or "")[-400:]))
    return images


def _glb_height(path):
    try:
        import trimesh
        scene = trimesh.load(path, force="scene", process=False)
        bounds = scene.bounds
        return float(bounds[1][1] - bounds[0][1])
    except Exception:
        return None


def _scale_mul_from_plan(plan, actor_glb, target_glb):
    ratio = _clampf(plan.get("scale_ratio"), 0.05, 20.0, None)
    if ratio is None:
        return None
    ah = _glb_height(actor_glb)
    th = _glb_height(target_glb)
    if not ah or not th:
        return None
    return round(_clampf(ratio * th / ah, 0.05, 20.0, 1.0), 4)


def decide(actor_glb, target_glb, instruction, workdir):
    os.makedirs(workdir, exist_ok=True)
    target_views = render_views(target_glb, os.path.join(workdir, "target_views"))
    actor_views = render_views(actor_glb, os.path.join(workdir, "actor_views"))
    question = (
        "Images 1 a 4: l'objet CIBLE seul sous 4 angles. Images 5 a 8: l'ACTEUR seul sous 4 angles. "
        'Instruction de scene: "%s". '
        "Decris les deux objets. Identifie la relation spatiale demandee parmi sit_on|stand_on|lie_on|next_to|hold. "
        "Localise la surface d'interaction sur la CIBLE en fractions normalisees: "
        "seat_height_frac = hauteur de la surface d'interaction entre 0.0 (base de la cible) et 1.0 (sommet), "
        "seat_depth_frac = position en profondeur entre 0.0 (bord avant) et 1.0 (bord arriere), "
        "face_side = cote de la cible qui constitue sa face avant. "
        "Donne l'echelle relative naturelle: scale_ratio = hauteur naturelle de l'acteur divisee par la hauteur "
        "naturelle de la cible (exemple: un humain fait environ 2.5 fois la hauteur d'une chaise). "
        "Choisis la strategie de pose de l'acteur parmi legs_bent|edge|stand|lie|none."
    ) % instruction
    schema = ('{"actor_desc": "...", "target_desc": "...", '
              '"relation": "sit_on|stand_on|lie_on|next_to|hold", '
              '"seat_height_frac": 0.0, "seat_depth_frac": 0.0, '
              '"face_side": "front|back|left|right", "scale_ratio": 1.0, '
              '"strategy": "legs_bent|edge|stand|lie|none"}')
    raw = ask_vlm(target_views + actor_views, question, schema)
    return {
        "actor_desc": str(raw.get("actor_desc") or ""),
        "target_desc": str(raw.get("target_desc") or ""),
        "relation": raw.get("relation") if raw.get("relation") in RELATIONS else None,
        "seat_height_frac": _clampf(raw.get("seat_height_frac"), 0.0, 1.0, None),
        "seat_depth_frac": _clampf(raw.get("seat_depth_frac"), 0.0, 1.0, None),
        "face_side": raw.get("face_side") if raw.get("face_side") in SIDES else None,
        "scale_ratio": _clampf(raw.get("scale_ratio"), 0.05, 20.0, None),
        "strategy": raw.get("strategy") if raw.get("strategy") in STRATEGIES else None,
        "target_views": target_views,
        "actor_views": actor_views,
    }


def judge(scene_glb, instruction, workdir, plan):
    views_dir = os.path.join(workdir, "judge_views_%d" % int(time.time() * 1000))
    images = render_views(scene_glb, views_dir)
    question = (
        'Voici 4 vues de la scene 3D composee. Instruction: "%s". '
        "Plan prevu: acteur=%s, cible=%s, strategie=%s. "
        "Juge le resultat: l'instruction est-elle respectee visuellement? "
        "Liste chaque probleme observe parmi flottement|traverse|mauvaise_position|mauvaise_echelle|autre. "
        "Propose une correction chiffree: dz = decalage vertical de l'acteur en fraction de la hauteur de la cible "
        "(-1.0 a 1.0, positif = monter), davant = decalage horizontal vers l'avant de la cible en fraction "
        "(-1.0 a 1.0, positif = vers l'avant), scale_mul = facteur d'echelle a appliquer a l'acteur "
        "(0.5 a 2.0, 1.0 = inchange)."
    ) % (instruction, plan.get("actor_desc") or "?", plan.get("target_desc") or "?", plan.get("strategy") or "auto")
    schema = ('{"success": true, "problems": ["flottement|traverse|mauvaise_position|mauvaise_echelle|autre"], '
              '"correction": {"dz": 0.0, "davant": 0.0, "scale_mul": 1.0}}')
    raw = ask_vlm(images, question, schema)
    corr = raw.get("correction") if isinstance(raw.get("correction"), dict) else {}
    return {
        "success": bool(raw.get("success")),
        "problems": [str(p) for p in (raw.get("problems") or [])],
        "correction": {
            "dz": _clampf(corr.get("dz"), -1.0, 1.0, 0.0),
            "davant": _clampf(corr.get("davant"), -1.0, 1.0, 0.0),
            "scale_mul": _clampf(corr.get("scale_mul"), 0.5, 2.0, 1.0),
        },
        "views": images,
    }


def _run_composer(actor, target, instruction, output, animate, overrides):
    cmd = [sys.executable, COMPOSER, "--actor", str(actor), "--target", str(target),
           "--instruction", instruction, "--output", str(output)]
    if animate:
        cmd.append("--animate")
    for flag, value in overrides.items():
        if value is not None:
            cmd += ["--" + flag, str(value)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2800)
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("AURORA_SCENE_RESULT:"):
            try:
                return json.loads(line[len("AURORA_SCENE_RESULT:"):])
            except ValueError:
                break
    return {"ok": False, "error": ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-500:]}


def compose_with_intelligence(actor, target, instruction, output, animate=False, max_rounds=3, workdir=None):
    output = os.path.abspath(output)
    workdir = os.path.abspath(workdir or output + "_intel")
    os.makedirs(workdir, exist_ok=True)
    plan = decide(actor, target, instruction, workdir)
    state = {
        "seat-height-frac": plan.get("seat_height_frac"),
        "seat-depth-frac": plan.get("seat_depth_frac"),
        "scale-mul": _scale_mul_from_plan(plan, actor, target),
        "strategy": plan.get("strategy"),
        "dz-frac": None,
        "dfwd-frac": None,
    }
    history = []
    best = None
    for rnd in range(1, max(1, int(max_rounds)) + 1):
        round_glb = os.path.join(workdir, "round_%d.glb" % rnd)
        overrides = dict(state)
        res = _run_composer(actor, target, instruction, round_glb, animate, overrides)
        if res.get("ok") and os.path.isfile(round_glb):
            verdict = judge(round_glb, instruction, workdir, plan)
        else:
            verdict = {"success": False, "problems": ["compose_echec"],
                       "correction": {"dz": 0.0, "davant": 0.0, "scale_mul": 1.0}}
        entry = {"round": rnd,
                 "overrides": {k: v for k, v in overrides.items() if v is not None},
                 "compose": res,
                 "verdict": verdict,
                 "glb": round_glb if os.path.isfile(round_glb) else None}
        history.append(entry)
        score = (1 if verdict["success"] else 0, -len(verdict["problems"]))
        if entry["glb"] is not None and (best is None or score > best[0]):
            best = (score, entry)
        if verdict["success"]:
            break
        corr = verdict["correction"]
        if corr["dz"]:
            state["dz-frac"] = round(max(-1.0, min(1.0, (state["dz-frac"] or 0.0) + corr["dz"])), 4)
        if corr["davant"]:
            state["dfwd-frac"] = round(max(-1.0, min(1.0, (state["dfwd-frac"] or 0.0) + corr["davant"])), 4)
        if abs(corr["scale_mul"] - 1.0) > 1e-3:
            state["scale-mul"] = round(max(0.05, min(20.0, (state["scale-mul"] or 1.0) * corr["scale_mul"])), 4)
    result = {"ok": False, "output": output, "plan": plan, "rounds": len(history),
              "best_round": None, "success": False, "history": history}
    if best is not None:
        entry = best[1]
        out_dir = os.path.dirname(output)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        if os.path.abspath(entry["glb"]) != output:
            shutil.copyfile(entry["glb"], output)
        result["ok"] = os.path.isfile(output)
        result["best_round"] = entry["round"]
        result["success"] = bool(entry["verdict"]["success"])
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--instruction", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--max-rounds", type=int, default=3, dest="max_rounds")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()
    result = compose_with_intelligence(a.actor, a.target, a.instruction, a.output,
                                       animate=a.animate, max_rounds=a.max_rounds, workdir=a.workdir)
    print("AURORA_SCENE_INTEL_RESULT:" + json.dumps(result, ensure_ascii=True))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
