#!/usr/bin/env python3
"""A/B reel des modeles par role, en local via Ollama.

Teste sur des taches REPRESENTATIVES du pipeline (pas un benchmark generique):
- agentique/planification: produire un plan d architecture JSON valide + strict.
- tool-calling: emettre le protocole d actions AURORA_CODE_ACTIONS/1.
- verifieur/directeur: attraper un bug logique dans du code.
Mesure: latence, tokens/s, et validite de la sortie. But: CONFIRMER par test.
"""
import json, sys, time, urllib.request

OLLAMA = "http://localhost:11434/api/chat"

def chat(model, system, user, timeout=600):
    body = json.dumps({
        "model": model, "stream": False,
        "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}],
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }).encode()
    t0 = time.monotonic()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    dt = time.monotonic() - t0
    content = data.get("message", {}).get("content", "")
    n_tok = data.get("eval_count", 0)
    tps = round(n_tok / dt, 1) if dt > 0 else 0
    return {"content": content, "sec": round(dt, 1), "tok": n_tok, "tok_s": tps}


PLAN_SYS = "Tu es un architecte logiciel. Reponds UNIQUEMENT avec un objet JSON valide, aucun texte autour."
PLAN_USER = ('Produis un plan d architecture pour une landing page cafe (HTML/CSS/JS statique). '
             'Format JSON STRICT: {"files":[{"path":"...","role":"...","language":"..."}],"generationOrder":["..."]}. '
             'Rien d autre que le JSON.')

ACTIONS_SYS = "Tu es un generateur de code par actions-outil."
ACTIONS_USER = ('Ecris index.html (un titre h1 et un bouton). Commence EXACTEMENT par la ligne AURORA_CODE_ACTIONS/1 '
                'puis un tableau JSON: [{"kind":"write_file","path":"index.html","content":"..."}]. Rien d autre.')

VERIFY_SYS = "Tu es un relecteur de code rigoureux qui detecte les bugs."
VERIFY_USER = ('Ce code a un bug. Lequel, en une phrase ?\n\n'
               'function moyenne(a, b) { return a + b / 2; }\n'
               '// cense retourner la moyenne de a et b')


def judge_plan(txt):
    try:
        s = txt[txt.index("{"): txt.rindex("}") + 1]
        obj = json.loads(s)
        ok = isinstance(obj.get("files"), list) and len(obj["files"]) >= 1 and isinstance(obj.get("generationOrder"), list)
        return ("VALIDE" if ok else "JSON mais schema incomplet"), ok
    except Exception as e:
        return f"JSON INVALIDE ({e})", False

def judge_actions(txt):
    has_marker = "AURORA_CODE_ACTIONS/1" in txt
    try:
        s = txt[txt.index("["): txt.rindex("]") + 1]
        arr = json.loads(s)
        ok = isinstance(arr, list) and any(a.get("kind") == "write_file" for a in arr)
    except Exception:
        ok = False
    return (f"marqueur={has_marker}, actions_valides={ok}"), (has_marker and ok)

def judge_verify(txt):
    t = txt.lower()
    # Le bug: priorite operateurs -> a + (b/2) au lieu de (a+b)/2. Bonne reponse
    # mentionne parentheses / priorite / (a+b)/2.
    ok = any(k in t for k in ["parenth", "priorit", "(a + b)", "(a+b)", "b / 2", "ordre des op"])
    return ("BUG ATTRAPE" if ok else "bug manque/vague"), ok


CANDIDATES = {
    "agentique": {"models": sys.argv[1].split(",") if len(sys.argv) > 1 else ["devstral", "qwen3.6:27b"],
                  "tests": [("plan", PLAN_SYS, PLAN_USER, judge_plan), ("actions", ACTIONS_SYS, ACTIONS_USER, judge_actions)]},
    "verifieur": {"models": sys.argv[2].split(",") if len(sys.argv) > 2 else ["deepseek-r1:32b", "qwen3-coder:30b"],
                  "tests": [("verif", VERIFY_SYS, VERIFY_USER, judge_verify)]},
}

results = {}
for role, cfg in CANDIDATES.items():
    print(f"\n===== ROLE: {role} =====", flush=True)
    for model in cfg["models"]:
        results.setdefault(model, {"role": role, "tests": {}})
        for name, sysp, usr, judge in cfg["tests"]:
            try:
                r = chat(model, sysp, usr)
                verdict, ok = judge(r["content"])
                results[model]["tests"][name] = {"ok": ok, "verdict": verdict, "tok_s": r["tok_s"], "sec": r["sec"]}
                print(f"  [{model:22}] {name:8} -> {'PASS' if ok else 'FAIL'} | {verdict} | {r['tok_s']} tok/s, {r['sec']}s", flush=True)
            except Exception as e:
                results[model]["tests"][name] = {"ok": False, "verdict": f"ERREUR: {e}", "tok_s": 0, "sec": 0}
                print(f"  [{model:22}] {name:8} -> ERREUR: {str(e)[:80]}", flush=True)

print("\n===== JSON =====")
print(json.dumps(results, ensure_ascii=False, indent=1))
