#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hymotion_generate — texte libre -> mouvement humain (HY-Motion 1.0).

Pourquoi ce module existe: la bibliotheque de prefixages couvre 28 gestes
nommes (marcher, courir, s'asseoir, frapper...). Tout ce qui sort de cette
liste — un mouvement invente, une choregraphie decrite en trois phrases, un
enchainement precis — ne trouvait AUCUNE correspondance et ne produisait rien.
HY-Motion genere le mouvement directement depuis la description, sans
vocabulaire a maintenir.

Deux pieges evites:
  - le `requirements.txt` du depot epingle `torch==2.5.1`, qui NE CONNAIT PAS
    l'architecture Blackwell (sm_120). On utilise l'interpreteur de l'app, qui
    a torch 2.11+cu128 avec sm_120. Ne jamais suivre l'epinglage.
  - la reecriture de texte et l'estimation de duree appellent un Qwen3-8B
    supplementaire (plusieurs Go). On les desactive: la description de
    l'utilisateur est deja ce qu'il veut, et la duree lui appartient.

Usage:
    python hymotion_generate.py --prompt "un homme esquive puis contre-attaque" \
        --output-dir <dir> [--duration 4.0] [--seeds 1] [--cfg 5.0]

Sortie: JSON sur stdout {ok, files[], elapsed_s, ...}.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HY_ROOT = Path(os.environ.get(
    "AURORA_HYMOTION_ROOT",
    Path.home() / ".local/share/auroraia/external/HY-Motion"))
REPO_ROOT = Path(__file__).resolve().parents[2]


def _python() -> str:
    """Interpreteur qui a torch cu128 (Blackwell), pas celui du depot."""
    env = os.environ.get("AURORA_HYMOTION_PY")
    if env:
        return env
    for rel in (("application", ".venv", "bin", "python"), ("application", ".venv", "Scripts", "python.exe")):
        venv = REPO_ROOT.joinpath(*rel)
        if venv.is_file():
            return str(venv)
    return sys.executable


def _model_path() -> Path | None:
    """Checkpoint HY-Motion, ou None s'il n'est pas la."""
    for cand in (HY_ROOT / "ckpts" / "tencent" / "HY-Motion-1.0",
                 HY_ROOT / "ckpts" / "HY-Motion-1.0"):
        if (cand / "latest.ckpt").is_file():
            return cand
    return None


def available() -> tuple[bool, str]:
    if not (HY_ROOT / "local_infer.py").is_file():
        return False, "HY-Motion absent (%s)" % HY_ROOT
    if _model_path() is None:
        return False, "checkpoint HY-Motion introuvable sous %s/ckpts" % HY_ROOT
    return True, ""


_FRENCH_DETECTION_RX = (
    r"\b(un|une|le|la|les|du|des|au|aux|qui|que|sur|dans|avec|sans|pour|par|vers|"
    r"fais|fait|faire|homme|femme|personnage|guerrier|chevalier|samourai|samouraï|"
    r"robot|marche|marcher|court|courir|saute|sauter|bondit|bondir|esquive|esquiver|"
    r"attaque|attaquer|frappe|frapper|danse|danser|salue|saluer|boxe|boxer|pare|parer|"
    r"puis|ensuite|avant|apr[eè]s|lentement|rapidement|doucement|vivement|en\s+garde|"
    r"bouclier|[eé]p[eé]e|coup|poing|pied|genou|coude|t[eê]te|bras|main|mains|jambe|jambes|"
    r"roulade|salto|pirouette|tourne|tourner|pivote|pivoter|recule|reculer|avance|avancer|"
    r"accroupit|accroupir|rel[eè]ve|relever|incline|incliner|applaudit|applaudir|"
    r"uppercut|crochet|revers|balayage|feinte|garde|jongle|titube|glisse|sprinte|trottine)\b"
)

_FRENCH_BIOMECH_CLAUSES: list[tuple[str, str]] = [
    (r"\bfais[- ]moi\s+", ""),
    (r"\bcr[eé]e[- ]moi\s+(?:une\s+animation\s+(?:3d\s+)?(?:d['’]|de\s+)?)?", ""),
    (r"\banime[- ]moi\s+", ""),
    (r"\bmaintenant\s+(?:fais[- ]le|fais[- ]la)\s+", "A person "),
    (r"\b(?:fais[- ]le|fais[- ]la)\s+", "A person "),
    (r"\b(?:un|une|le|la)\s+(?:guerrier|guerri[eè]re|chevalier|samoura[iï]|combattant|combattante|soldat|homme|femme|personnage|robot|danseur|danseuse|ma[iî]tre(?:\s+d['’]arts\s+martiaux)?|boxeur|ninja|athl[eè]te)\s+(?:qui\s+)?", "A person "),
    (r"\b(?:il|elle)\s+", "the person "),
    (r"\bmarche\s+prudemment\s+en\s+garde\b", "walks forward in a martial arts guard"),
    (r"\bavance\s+prudemment\s+en\s+garde\b", "steps forward in a martial arts guard"),
    (r"\bavance\s+en\s+garde\b", "steps forward in a martial arts guard"),
    (r"\bse\s+met\s+en\s+garde\b", "stands in a martial arts guard"),
    (r"\bposition\s+de\s+garde\b", "stands in a martial arts guard"),
    (r"\ben\s+garde\b", "in a martial arts guard"),
    (r"\bmarche\s+en\s+garde\b", "walks forward in a martial arts guard"),
    (r"\bmarche\s+lentement\b", "walks forward slowly"),
    (r"\bmarche\s+vite\b", "walks forward briskly"),
    (r"\b(?:marche|marcher)\b", "walks forward"),
    (r"\b(?:avance|avancer)\b", "steps forward"),
    (r"\brecule\s+d['’]un\s+pas\b", "steps backward"),
    (r"\b(?:recule|reculer)\b", "steps backward"),
    (r"\bcourt\s+rapidement\b", "runs forward fast"),
    (r"\b(?:sprinte|sprinter)\b", "sprints forward fast"),
    (r"\b(?:trottine|trottiner)\b", "jogs forward lightly"),
    (r"\b(?:court|courir)\b", "runs forward"),
    (r"\bfait\s+un\s+pas\s+chass[eé]\b", "sidesteps quickly"),
    (r"\bpas\s+chass[eé]\b", "sidesteps quickly"),
    (r"\besquive\s+(?:une\s+attaque\s+)?sur\s+le\s+c[oô]t[eé]\b", "steps sideways to dodge"),
    (r"\besquive\s+une\s+attaque\b", "steps sideways to dodge"),
    (r"\b(?:esquive|esquiver)\b", "steps sideways to dodge"),
    (r"\b(?:feinte|feinter)\b", "makes a quick feint step"),
    (r"\bl[eè]ve\s+son\s+bouclier\s+pour\s+parer\b", "raises the left arm to block"),
    (r"\b(?:pare|parer)\b", "raises the arms to block"),
    (r"\bsaute\s+de\s+joie\s+en\s+levant\s+les\s+bras\b", "jumps with joy while raising both arms overhead"),
    (r"\bsaute\s+en\s+tournant\s+pour\s+(?:frapper|donner\s+un\s+(?:grand\s+)?coup)\s+(?:avec\s+son\s+[eé]p[eé]e|d['’][eé]p[eé]e)\b", "jumps and spins in the air while swinging the right arm in a sword slash"),
    (r"\bsaute\s+en\s+tournant\b", "jumps and spins in the air"),
    (r"\b(?:saute|sauter|bondit|bondir)\b", "jumps up"),
    (r"\bdonne\s+un\s+coup\s+de\s+pied\s+retourn[eé]\b", "performs a spinning roundhouse kick"),
    (r"\bcoup\s+de\s+pied\s+retourn[eé]\b", "performs a spinning roundhouse kick"),
    (r"\bbalayage\b", "performs a low sweeping kick"),
    (r"\bdonne\s+un\s+(?:grand\s+)?coup\s+d['’][eé]p[eé]e\b", "swings the right arm in a sword slash"),
    (r"\bfrappe\s+avec\s+son\s+[eé]p[eé]e\b", "swings the right arm in a sword slash"),
    (r"\b(?:donne\s+un\s+)?coup\s+de\s+pied\b", "performs a forward kick"),
    (r"\b(?:donne\s+un\s+)?coup\s+de\s+genou\b", "performs a rising knee strike"),
    (r"\b(?:donne\s+un\s+)?coup\s+de\s+coude\b", "throws a spinning elbow strike"),
    (r"\bencha[iî]ne\s+deux\s+coups\s+de\s+poing\b", "throws a left and right punch combination"),
    (r"\b(?:donne\s+un\s+)?uppercut\b", "throws a rising uppercut punch"),
    (r"\b(?:donne\s+un\s+)?crochet\b", "throws a wide hook punch"),
    (r"\b(?:donne\s+un\s+)?revers\b", "throws a spinning backhand strike"),
    (r"\b(?:donne\s+un\s+)?coup\s+de\s+poing\b", "throws a forward punch"),
    (r"\b(?:boxe|boxer)\b", "throws a rhythmic boxing punch combination"),
    (r"\bcontre[- ]attaque\b", "throws a forward strike"),
    (r"\b(?:frappe|frapper|attaque|attaquer)\b", "throws a forward strike"),
    (r"\bs['’]accroupit\b", "squats down"),
    (r"\baccroupi\b", "squats down"),
    (r"\bse\s+rel[eè]ve\b", "stands back up"),
    (r"\bs['’][eé]tire\b", "stretches both arms overhead"),
    (r"\btourne\s+sur\s+(?:lui[- ]m[eê]me|elle[- ]m[eê]me)\b", "turns around 360 degrees"),
    (r"\b(?:tourne|tourner|pivote|pivoter)\b", "turns around"),
    (r"\bfait\s+une\s+pirouette\b", "performs a graceful spin"),
    (r"\bpirouette\b", "performs a graceful spin"),
    (r"\bl[eè]ve\s+les\s+bras\b", "raises both arms overhead"),
    (r"\ben\s+levant\s+les\s+bras\b", "while raising both arms overhead"),
    (r"\b(?:applaudit|applaudir)\b", "claps both hands"),
    (r"\bavant\s+de\s+saluer\s+de\s+la\s+main\b", "and then stands upright and waves hello with the right hand"),
    (r"\bavant\s+de\s+saluer\b", "and then stands upright and waves hello with the right hand"),
    (r"\bsalue\s+de\s+la\s+main\b", "waves hello with the right hand"),
    (r"\bsaluer\s+de\s+la\s+main\b", "waving hello with the right hand"),
    (r"\bsalue\b", "waves hello with the right hand"),
    (r"\bsaluer\b", "waving hello with the right hand"),
    (r"\bde\s+la\s+main\b", "with the right hand"),
    (r"\bs['’]incline\b", "bows forward respectfully"),
    (r"\b(?:danse|danser)\b", "dances rhythmically"),
    (r"\b(?:jongle|jongler)\b", "juggles rhythmically with both hands"),
    (r"\b(?:titube|tituber)\b", "stumbles and regains balance"),
    (r"\bfait\s+un\s+salto\b", "performs a jump flip"),
    (r"\bsalto\b", "performs a jump flip"),
    (r"\bfait\s+une\s+roulade\b", "performs a forward roll"),
    (r"\broulade\b", "performs a forward roll"),
    (r"\bpuis\b", "then"),
    (r"\bensuite\b", "then"),
    (r"\bavant\s+de\b", "and then"),
    (r"\bet\s+enfin\b", "and finally"),
    (r"\bet\b", "and"),
]


def _translate_french_to_english_biomechanics(prompt: str, duration: float) -> tuple[str, float]:
    """Traduit toute demande en français (courte, inventée ou complexe) vers une phrase
    anglaise concise du style HumanML3D / HY-Motion-1.0."""
    import re
    import urllib.request

    raw = (prompt or "").strip()
    if "Current user request" in raw:
        raw = raw.split("Current user request")[-1].split(":", 1)[-1].strip()
    clean = " ".join(raw.split())
    if not clean:
        return "A person walks forward.", duration

    phases = re.split(r"\b(?:puis|ensuite|avant\s+de|et\s+apr[eè]s|apr[eè]s\s+quoi|then|and\s+then|before)\b", clean, flags=re.I)
    num_phases = max(1, len([p for p in phases if p.strip()]))
    effective_duration = float(duration or 4.0)
    if effective_duration <= 5.0 and num_phases >= 2:
        effective_duration = min(8.0, max(5.0, 1.8 * num_phases))

    if os.environ.get("AURORA_HYMOTION_RAW_PROMPT") == "1":
        return clean, effective_duration

    # 1. Traduction déterministe HumanML3D / HY-Motion (prioritaire pour les clauses connues)
    translated = clean
    matched_clause = False
    for pattern, repl in _FRENCH_BIOMECH_CLAUSES:
        new_t = re.sub(pattern, repl, translated, flags=re.I)
        if new_t != translated:
            matched_clause = True
            translated = new_t
    translated = re.sub(r"\s+", " ", translated).strip(" ,.")

    is_french = (
        matched_clause
        or bool(re.search(_FRENCH_DETECTION_RX, clean, flags=re.I))
        or any(c in clean for c in "éèêàùçôîûœ")
    )
    if not is_french and clean.lower().startswith(("a person", "a man", "a woman", "someone", "the person")):
        return clean, effective_duration

    if not translated.lower().startswith(("a person", "a man", "a woman")):
        translated = "A person " + translated
    if not translated.endswith("."):
        translated += "."

    still_has_french = (
        bool(re.search(_FRENCH_DETECTION_RX, translated, flags=re.I))
        or any(c in translated for c in "éèêàùçôîûœ")
        or (not matched_clause and is_french)
    )
    if not still_has_french:
        return translated, effective_duration

    # 2. Pour tout mouvement français libre, inventé ou idiomatique non entièrement couvert,
    # traduction directe via Ollama local (avec keep_alive=0 pour libérer la VRAM immédiatement)
    if os.environ.get("AURORA_HYMOTION_LLM_TRANSLATE", "1") == "1":
        try:
            ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
            model = os.environ.get("AURORA_MOTION_LLM", "")
            if not model:
                try:
                    from llm_disponible import resoudre_modele as _res_llm
                    model = _res_llm("orcarouter/Qwen3.8-27B-Uncensored:latest", "texte", bavard=False)
                except Exception:
                    model = "orcarouter/Qwen3.8-27B-Uncensored:latest"
            body = json.dumps({
                "model": model,
                "prompt": (
                    "Translate this French 3D character animation request into one simple, clear English sentence "
                    "describing the physical body movement in HumanML3D dataset style (e.g. 'A person walks forward, "
                    "steps sideways to dodge, jumps and spins while swinging their right arm, and waves hello with their right hand.'). "
                    "Even if the French request is short or creative, describe the concrete body motion starting with 'A person ' "
                    "and output ONLY the English sentence.\n"
                    f"French request: {clean}"
                ),
                "think": False,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            }).encode("utf-8")
            req = urllib.request.Request(f"{ollama_url}/api/generate", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                out = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
            out = out.splitlines()[-1].strip().strip('"').strip("'") if out else ""
            if out and len(out.split()) >= 3:
                if not out.lower().startswith(("a person", "a man", "a woman", "someone", "the person")):
                    out = "A person " + out[0].lower() + out[1:]
                if not out.endswith("."):
                    out += "."
                return out, effective_duration
        except Exception:
            pass

    return translated, effective_duration


def generate(prompt: str, output_dir: str, *, duration: float = 4.0,
             seeds: int = 1, cfg_scale: float = 5.0,
             timeout_s: int = 1800) -> dict:
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Traduction biomécanique FR -> EN et ajustement de durée multi-phases
    effective_prompt, effective_duration = _translate_french_to_english_biomechanics(prompt, duration)

    # local_infer lit un DOSSIER de fichiers texte, pas un prompt direct.
    # Syntaxe native "texte#duree": sans suffixe c'est 150 frames (~5 s) —
    # une sequence complete (macarena ~12-16 s) etait TRONQUEE au premier
    # geste. La duree vient de la structure du geste (resolveur), pas d'une
    # constante.
    tmp = Path(tempfile.mkdtemp(prefix="hymotion_txt_"))
    _ligne = " ".join(effective_prompt.strip().split())
    if effective_duration and float(effective_duration) > 0:
        # le suffixe est en FRAMES ENTIERES a 30 fps (int(split[1]) cote
        # local_infer — "#6.0" levait ValueError et tuait la generation).
        _ligne += "#%d" % int(round(max(1.0, min(float(effective_duration), 30.0)) * 30))
    (tmp / "0.txt").write_text(_ligne + "\n", encoding="utf-8")

    # Offload CPU par défaut pour l'encodeur Qwen3-8B en bfloat16 (0 risque d'OOM
    # sur 16 Go VRAM à côté du DiT HY-Motion 4.17 Go + CLIP-L), même si le parent
    # (ex: vite_bp_routes.py) a posé AURORA_LLM_4BIT=1 dans os.environ.
    force_cuda = os.environ.get("AURORA_HYMOTION_FORCE_CUDA", "0") == "1"
    env = {**os.environ,
           "PYTHONPATH": str(HY_ROOT),
           "AURORA_LLM_DEVICE": "cuda" if force_cuda else "cpu",
           "AURORA_LLM_4BIT": "1" if force_cuda else "0",
           "USE_HF_MODELS": os.environ.get("USE_HF_MODELS", "1"),
           "HF_HOME": os.environ.get(
               "HF_HOME", str(Path.home() / ".cache" / "huggingface"))}
    cmd = [_python(), str(REPO_ROOT / "auto_rl" / "hymotion_infer.py"),
           "--model_path", str(_model_path()),
           "--input_text_dir", str(tmp),
           "--output_dir", str(out),
           "--cfg_scale", str(cfg_scale),
           "--num_seeds", str(max(1, int(seeds))),
           # sans ces deux drapeaux, un LLM supplementaire est charge
           "--disable_rewrite", "--disable_duration_est"]

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(HY_ROOT), env=env,
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "HY-Motion: delai depasse (%ds)" % timeout_s}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "HY-Motion: %r" % (exc,)}

    files = sorted(str(p) for p in out.rglob("*")
                   if p.is_file() and p.suffix.lower() in
                   (".bvh", ".npy", ".npz", ".fbx", ".json"))
    if proc.returncode != 0 and not files:
        tail = (proc.stderr or proc.stdout or "")[-600:]
        return {"ok": False, "error": "HY-Motion a echoue: %s" % tail,
                "elapsed_s": round(time.time() - t0, 1)}
    if not files:
        return {"ok": False, "error": "HY-Motion n'a produit aucun fichier",
                "elapsed_s": round(time.time() - t0, 1)}
    return {"ok": True, "files": files, "prompt": prompt,
            "effective_prompt_en": effective_prompt,
            "duration_s": effective_duration, "elapsed_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt")
    ap.add_argument("--output-dir", dest="output_dir")
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--cfg", type=float, default=5.0, dest="cfg_scale")
    ap.add_argument("--check", action="store_true",
                    help="verifie seulement la disponibilite")
    a = ap.parse_args()
    if a.check:
        # --check n'a besoin d'aucun prompt: il repond juste "utilisable ou non".
        ok, why = available()
        print(json.dumps({"ok": ok, "error": why or None,
                          "root": str(HY_ROOT),
                          "model_path": str(_model_path() or "")},
                         ensure_ascii=False))
        return 0 if ok else 1
    if not a.prompt or not a.output_dir:
        ap.error("--prompt et --output-dir sont requis (sauf avec --check)")
    res = generate(a.prompt, a.output_dir, duration=a.duration,
                   seeds=a.seeds, cfg_scale=a.cfg_scale)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

