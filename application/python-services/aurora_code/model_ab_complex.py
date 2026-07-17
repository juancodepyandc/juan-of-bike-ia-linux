#!/usr/bin/env python3
"""A/B sur taches COMPLEXES + MEMORY-SAFE (un seul gros modele charge a la fois).

Corrige 2 defauts du 1er A/B:
1. Taches trop simples -> un modele de raisonnement sur-reflechit sans montrer sa
   profondeur. Ici: plan d architecture riche (SaaS multi-fichiers) + bug SUBTIL.
2. Empilement memoire -> crash. Ici on DECHARGE chaque modele (keep_alive:0) avant
   de charger le suivant, et on ABANDONNE si le swap grimpe (garde anti-gel).
"""
import json, subprocess, sys, time, urllib.request

OLLAMA = "http://localhost:11434"

def swap_used_gb():
    try:
        with open("/proc/meminfo") as f:
            info = {l.split(":")[0]: int(l.split()[1]) for l in f}
        return round((info["SwapTotal"] - info["SwapFree"]) / (1024 * 1024), 2)
    except Exception:
        return 0.0

def unload(model):
    try:
        urllib.request.urlopen(urllib.request.Request(
            OLLAMA + "/api/generate", data=json.dumps({"model": model, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}), timeout=30)
    except Exception:
        pass

def loaded_models():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []

def unload_all_heavy(keep=None):
    for m in loaded_models():
        if keep and m == keep:
            continue
        if any(m.startswith(p) for p in ("devstral", "qwen3-coder", "deepseek-r1", "qwen3.6")):
            unload(m)
    time.sleep(2)

def chat(model, system, user, timeout=1200):
    body = json.dumps({"model": model, "stream": False,
        "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}],
        "options": {"temperature": 0.2, "num_ctx": 16384}}).encode()
    t0 = time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/chat", data=body,
            headers={"Content-Type": "application/json"}), timeout=timeout) as r:
        data = json.loads(r.read())
    dt = time.monotonic() - t0
    return {"content": data.get("message", {}).get("content", ""), "sec": round(dt, 1),
            "tok": data.get("eval_count", 0), "tok_s": round(data.get("eval_count", 0) / dt, 1) if dt else 0}

# --- Taches COMPLEXES ---
PLAN_SYS = "Tu es un architecte logiciel senior. Reponds UNIQUEMENT avec un objet JSON valide."
PLAN_USER = ('Plan d architecture COMPLET pour un SaaS de gestion de taches: auth JWT, CRUD utilisateurs, '
             'projets, taches avec drag-and-drop, tableau de bord avec graphiques, dark mode, responsive, '
             'API REST + base de donnees. Format JSON STRICT: {"files":[{"path","role","language"}],'
             '"generationOrder":[...],"stack":{...}}. Vise >=12 fichiers coherents (front+back+db+config). JSON seul.')

# Bug SUBTIL: closure dans une boucle (var au lieu de let) -> tous les handlers voient la derniere valeur.
BUG_SYS = "Tu es un relecteur de code expert. Identifie le bug precis et sa cause en 1-2 phrases."
BUG_USER = ('Ce code doit afficher 0,1,2 au clic de chaque bouton mais affiche toujours 3. Pourquoi ?\n\n'
            'for (var i = 0; i < 3; i++) {\n'
            '  const btn = document.createElement("button");\n'
            '  btn.onclick = function () { console.log(i); };\n'
            '  document.body.appendChild(btn);\n'
            '}')

def judge_plan(txt):
    try:
        obj = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        files = obj.get("files", [])
        n = len(files)
        paths = " ".join(f.get("path", "") + " " + f.get("role", "") for f in files).lower()
        covers = sum(k in paths or k in txt.lower() for k in ["auth", "api", "dashboard", "task", "db", "schema", "route"])
        ok = n >= 10 and isinstance(obj.get("generationOrder"), list) and covers >= 4
        return f"{n} fichiers, couverture={covers}/6", ok, n
    except Exception as e:
        return f"JSON INVALIDE ({str(e)[:40]})", False, 0

def judge_bug(txt):
    t = txt.lower()
    ok = ("var" in t and ("let" in t or "closure" in t or "fermeture" in t or "portee" in t or "scope" in t)) \
        or "meme variable" in t or "partagent" in t or "hoist" in t
    return ("BUG SUBTIL ATTRAPE (closure/var)" if ok else "manque la vraie cause"), ok, 0

MODELS_AGENT = sys.argv[1].split(",") if len(sys.argv) > 1 else ["devstral", "qwen3.6:27b"]
MODELS_VERIF = sys.argv[2].split(",") if len(sys.argv) > 2 else ["deepseek-r1:32b", "qwen3-coder:30b"]

print(f"[{time.strftime('%H:%M:%S')}] swap initial: {swap_used_gb()}GB", flush=True)
results = {}
for role, models, (sysp, usr, judge) in [
    ("agent", MODELS_AGENT, (PLAN_SYS, PLAN_USER, judge_plan)),
    ("verifieur", MODELS_VERIF, (BUG_SYS, BUG_USER, judge_bug)),
]:
    print(f"\n===== ROLE {role} (tache complexe) =====", flush=True)
    for model in models:
        unload_all_heavy()  # garantit UN SEUL gros modele
        sw = swap_used_gb()
        if sw > 3.0:
            print(f"  [SECURITE] swap {sw}GB trop haut -> abandon", flush=True); break
        try:
            r = chat(model, sysp, usr)
            verdict, ok, extra = judge(r["content"])
            results.setdefault(model, {})[role] = {"ok": ok, "verdict": verdict, "tok_s": r["tok_s"], "sec": r["sec"], "extra": extra}
            print(f"  [{model:20}] {'PASS' if ok else 'FAIL'} | {verdict} | {r['tok_s']} tok/s, {r['sec']}s | swap {swap_used_gb()}GB", flush=True)
        except Exception as e:
            results.setdefault(model, {})[role] = {"ok": False, "verdict": f"ERREUR: {str(e)[:60]}"}
            print(f"  [{model:20}] ERREUR: {str(e)[:70]}", flush=True)
        unload(model)  # libere avant le suivant
        time.sleep(2)

print("\n===== JSON =====\n" + json.dumps(results, ensure_ascii=False, indent=1))
print(f"[{time.strftime('%H:%M:%S')}] swap final: {swap_used_gb()}GB", flush=True)
