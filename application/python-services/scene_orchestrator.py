"""scene_orchestrator — turn a natural multi-object prompt into a composed scene.

The single-mesh pipeline (aurora_3d_pipeline) treats 'un homme assis sur une
chaise' as ONE humanoid and TRELLIS renders a sitting man with no chair. True
multi-object scenes need: split the prompt into its objects + spatial relation,
GENERATE each object separately, then COMPOSE them (scene_composer). This module
is that missing orchestrator. It is deliberately model-driven (an LLM splits the
prompt) — no hardcoded object list.

Flow:
  1. split_scene_prompt(prompt) -> {is_scene, actor{desc,motion}, target{desc},
     relation, animate}  (LLM; falls back to single-object when not a scene).
  2. For a scene: generate the actor GLB and the target GLB via run_pipeline,
     then compose via scene_composer.py with the parsed relation.

Public: split_scene_prompt(prompt), orchestrate_scene(prompt, run_id, output_dir).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

HERE = Path(__file__).resolve().parent
RELATIONS = ("sit_on", "stand_on", "lie_on", "next_to", "hold")
_LLM = os.environ.get("AURORA_MOTION_LLM", "qwen3:30b-a3b-instruct-2507-q4_K_M")


def _ollama(prompt: str, timeout: int = 90) -> str:
    """One-shot Ollama call; unloads the model afterwards (keep_alive:0) so the
    GPU is free for the heavy TRELLIS/MoMask stages that follow."""
    body = json.dumps({
        "model": _LLM, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1}, "keep_alive": 0,
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "").strip()


def _extract_json(text: str) -> Optional[dict]:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except Exception:
        return None


def split_scene_prompt(prompt: str) -> Dict[str, Any]:
    """LLM: decide whether the prompt is a multi-object scene and, if so, split it
    into an actor (the main subject, possibly moving), a target (the object it
    relates to), the spatial relation, and whether it is animated. Returns
    {"is_scene": False} for a single object."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"is_scene": False}
    q = (
        "You analyse a 3D generation prompt. Decide if it describes TWO distinct "
        "physical objects in a spatial relation (e.g. a person on a chair, a cat "
        "on a sofa, a book on a table), or just ONE object/subject. "
        "Reply ONLY strict JSON. If two objects: "
        '{"is_scene": true, "actor": "<short desc of the main/animate object>", '
        '"actor_posed": "<same actor described AS ALREADY IN the resting pose of the '
        'relation, e.g. a sitting man, a lying cat; same language as the prompt>", '
        '"actor_motion": "<motion phrase or empty>", "target": "<short desc of the '
        'object it sits/stands/lies on or is next to>", "relation": '
        '"<sit_on|stand_on|lie_on|next_to|hold>"}. '
        'If one object: {"is_scene": false}. '
        "A single subject in a pose (a man standing) is NOT a scene. "
        # `actor_motion` doit etre un MOUVEMENT, pas la relation redite: "assis sur
        # une chaise" a pour relation sit_on et pour mouvement RIEN. Sans cette
        # precision le LLM renvoie actor_motion='assis', on fait baker une animation
        # "assis" au rig, et le compositeur doit ensuite la purger pour poser le
        # personnage. Du travail pour rien, et un rig incoherent.
        "actor_motion must be a real MOVEMENT (walking, running, dancing). The "
        "static relation itself is NOT a motion: for 'a man sitting on a chair', "
        'relation is sit_on and actor_motion is "". '
        "Prompt: " + prompt
    )
    # Un echec de l'appel LLM ne doit PAS etre confondu avec "ce n'est pas une
    # scene": avale silencieusement, il rend un homme SANS chaise et personne ne
    # sait pourquoi. On reessaie, et si ca echoue toujours on le DIT (`error`),
    # au lieu de degrader sans bruit.
    data, err = {}, None
    for attempt in range(2):
        try:
            data = _extract_json(_ollama(q)) or {}
            err = None
            break
        except Exception as exc:  # noqa: BLE001
            err = repr(exc)
            time.sleep(1.0 + attempt)
    if err is not None:
        print("SCENE_ORCH: analyse du prompt IMPOSSIBLE (%s) -> traite comme objet "
              "unique, mais ce n'est PAS une conclusion" % err, file=sys.stderr)
        return {"is_scene": False, "error": err}
    if not data.get("is_scene"):
        return {"is_scene": False}
    rel = data.get("relation")
    if rel not in RELATIONS:
        rel = "next_to"
    actor = str(data.get("actor") or "").strip()
    target = str(data.get("target") or "").strip()
    if not actor or not target:
        return {"is_scene": False}
    motion = str(data.get("actor_motion") or "").strip()
    posed = str(data.get("actor_posed") or "").strip()
    return {
        "is_scene": True, "actor": actor, "target": target,
        "relation": rel, "actor_motion": motion,
        "actor_posed": posed,
        "animate": bool(motion) or rel in ("sit_on", "lie_on"),
    }


def real_heights(actor: str, target: str) -> Dict[str, Optional[float]]:
    """Hauteurs REELLES des deux objets, en metres.

    Chaque objet est genere NORMALISE (~1 unite): un homme et une chaise sortent
    donc exactement de la meme taille, et composer sur les hauteurs mesurees donne
    un homme minuscule sur un fauteuil geant. La bonne echelle n'est pas une
    propriete de la geometrie, c'est une connaissance du MONDE - on la demande donc
    au LLM plutot que de coder une table d'objets, qui ne generaliserait a rien.
    """
    # Hauteur telle que MONTREE, pose comprise: un mesh d'homme ASSIS mesure sa
    # hauteur ASSISE (~1.3 m du sol au sommet du crane), pas sa taille debout. Passer
    # 1.75 a un mesh assis le rend geant (verifie: 4 unites pour une chaise de 2).
    q = (
        "Give the TYPICAL real-world height in METERS of each object AS DESCRIBED, "
        "POSE INCLUDED, floor to top, as a human would know it: a standing adult "
        "~1.75, a SEATED adult ~1.3, a lying adult ~0.5, a chair ~0.9, a mug ~0.1.\n"
        'Reply ONLY strict JSON: {"actor_m": <number>, "target_m": <number>}\n'
        "Object A (actor): %s\nObject B (target): %s" % (actor, target)
    )
    try:
        d = _extract_json(_ollama(q)) or {}
        a, t = float(d.get("actor_m")), float(d.get("target_m"))
    except Exception as exc:  # noqa: BLE001
        print("SCENE_ORCH: tailles reelles indisponibles (%r) -> echelle non "
              "corrigee" % exc, file=sys.stderr)
        return {"actor_m": None, "target_m": None}
    # garde-fou: une valeur aberrante ferait pire que rien
    if not (0.01 <= a <= 100.0 and 0.01 <= t <= 100.0):
        print("SCENE_ORCH: tailles aberrantes (%s, %s) -> ignorees" % (a, t),
              file=sys.stderr)
        return {"actor_m": None, "target_m": None}
    return {"actor_m": a, "target_m": t}


def _generate_object(desc: str, run_id: str, output_dir: Path,
                     motion: str = "", purpose: str = "visual_preview") -> Optional[str]:
    """Generate a single object GLB via the normal pipeline. Returns the final
    GLB path or None."""
    try:
        from aurora_3d_pipeline import run_pipeline
    except Exception as exc:  # noqa: BLE001
        print(f"SCENE_ORCH: cannot import run_pipeline: {exc}", file=sys.stderr)
        return None
    sub = output_dir / run_id
    sub.mkdir(parents=True, exist_ok=True)
    # allow_scene=False: l'orchestrateur EST deja dans une scene. Sans ce garde-fou,
    # run_pipeline redetecterait une scene et se rappellerait sans fin.
    res = run_pipeline(desc, run_id, output_dir=sub,
                       motion_prompt=(motion or None), purpose=purpose,
                       allow_scene=False)
    if not isinstance(res, dict):
        return None
    # Use the produced mesh even when res["ok"] is False: run_pipeline reports
    # ok=False on a SOFT acceptance miss (e.g. "single merged mesh, no
    # articulatable parts" — normal and fine for a chair), but the mesh geometry
    # is perfectly usable for composition. Prefer rigged/animated, else final.
    mesh = res.get("rigged_mesh") or res.get("final_mesh") or res.get("rescued_mesh")
    if mesh and os.path.isfile(str(mesh)):
        return str(mesh)
    return None


def orchestrate_scene(prompt: str, run_id: str, output_dir: str | Path) -> Dict[str, Any]:
    """Full multi-object flow. If the prompt is a single object, signals the
    caller to use the normal pipeline (is_scene False)."""
    output_dir = Path(output_dir)
    plan = split_scene_prompt(prompt)
    if not plan.get("is_scene"):
        return {"ok": True, "is_scene": False, "plan": plan}
    print(f"SCENE_ORCH: scene detecte -> acteur='{plan['actor']}' cible='{plan['target']}' "
          f"relation={plan['relation']} motion='{plan['actor_motion']}'", flush=True)

    # POSE STATIQUE = GENERER DEJA POSE, NE PAS PLIER. Plier un homme debout
    # auto-riggé sur un maillage TRELLIS (soupe de ~77k ilots) etire la jambe: la
    # deformation d'un maillage genere est un probleme non fiable. Pour une pose
    # STATIQUE (s'asseoir, s'allonger) sans mouvement, on genere donc l'acteur DEJA
    # dans la pose - TRELLIS produit un maillage coherent - et le compositeur le
    # PLACE sans le deformer. On ne rig-plie que s'il y a un vrai MOUVEMENT.
    prepose = (plan["relation"] in ("sit_on", "lie_on") and not plan["actor_motion"])
    actor_desc = plan["actor"]
    if prepose:
        # actor_posed du LLM peut n'etre que l'ADJECTIF ("assis") -> generer "assis"
        # tout seul a piege la recherche de reference vers l'entreprise "ASSIS". On
        # construit donc une description COMPLETE: acteur + pose, plein pied et
        # photorealiste (ce qui coupe aussi la recherche web parasite).
        posed = (plan.get("actor_posed") or "").strip()
        pose_word = {"sit_on": "assis", "lie_on": "allonge"}[plan["relation"]]
        if not posed or len(posed.split()) < 2:
            posed = "%s %s" % (plan["actor"], pose_word)
        actor_desc = "%s, photorealiste, corps entier" % posed
        print("SCENE_ORCH: pose statique -> generation de l'acteur DEJA pose "
              "('%s'), pas de rig-pliage" % actor_desc, flush=True)
    actor_glb = _generate_object(actor_desc, run_id + "_actor", output_dir,
                                 motion=plan["actor_motion"])
    if not actor_glb:
        return {"ok": False, "is_scene": True, "error": "actor generation failed", "plan": plan}
    target_glb = _generate_object(plan["target"], run_id + "_target", output_dir)
    if not target_glb:
        return {"ok": False, "is_scene": True, "error": "target generation failed",
                "plan": plan, "actor_glb": actor_glb}

    # Le generateur ne garantit aucune convention d'axe: la cible sort souvent
    # COUCHEE (une chaise sur son dossier). Composer par-dessus n'a alors aucun
    # sens - on assied le personnage sur une chaise renversee. On la redresse.
    upright_info = None
    try:
        import upright_object
        up_out = str(Path(target_glb).with_name(Path(target_glb).stem + "_droit.glb"))
        upright_info = upright_object.upright(target_glb, up_out, desc=plan["target"])
        if upright_info.get("ok") and not upright_info.get("already_upright"):
            target_glb = upright_info["output"]
    except Exception as exc:  # noqa: BLE001
        upright_info = {"ok": False, "error": repr(exc)}

    scene_out = output_dir / run_id / f"{run_id}_scene.glb"
    scene_out.parent.mkdir(parents=True, exist_ok=True)
    composer = HERE / "scene_composer.py"
    instruction = f"{plan['actor']} {plan['relation'].replace('_', ' ')} {plan['target']}"
    if plan["actor_motion"]:
        instruction += f", {plan['actor_motion']}"
    cmd = [sys.executable, str(composer), "--actor", actor_glb, "--target", target_glb,
           "--instruction", instruction, "--output", str(scene_out)]
    # pour un acteur pre-pose, la taille pertinente est celle de la POSE (assis ~1.3m)
    sizes = real_heights(actor_desc if prepose else plan["actor"], plan["target"])
    if sizes["actor_m"] and sizes["target_m"]:
        cmd += ["--actor-height-m", str(sizes["actor_m"]),
                "--target-height-m", str(sizes["target_m"])]
        print("SCENE_ORCH: tailles reelles -> acteur %.2f m, cible %.2f m"
              % (sizes["actor_m"], sizes["target_m"]), flush=True)
    if prepose:
        # l'acteur est DEJA pose: placer sans rigger ni plier.
        cmd.append("--actor-preposed")
    if plan["animate"] and not prepose:
        cmd.append("--animate")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "is_scene": True, "error": f"compose failed: {exc}",
                "plan": plan, "actor_glb": actor_glb, "target_glb": target_glb}
    ok = scene_out.is_file() and scene_out.stat().st_size > 1000
    return {
        "ok": ok, "is_scene": True, "plan": plan,
        "actor_glb": actor_glb, "target_glb": target_glb,
        "upright": upright_info,
        "scene_glb": str(scene_out) if ok else None,
        "composer_tail": (p.stdout or "")[-400:] + (p.stderr or "")[-200:],
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--split-only", action="store_true", help="only print the LLM scene split")
    args = ap.parse_args()
    if args.split_only:
        print(json.dumps(split_scene_prompt(args.prompt), ensure_ascii=False))
        return 0
    res = orchestrate_scene(args.prompt, args.run_id, args.output_dir)
    print(json.dumps(res, ensure_ascii=False, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
