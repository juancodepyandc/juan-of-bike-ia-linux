#!/usr/bin/env python3
"""A/B du CODEUR PUR sur une tache de GENERATION de code vraiment complexe.

Un seul gros modele charge a la fois (decharge entre chaque). Le swap est
TOLERE (l utilisateur accepte la lenteur si ca AVANCE): on ne coupe que sur un
swap runaway (>40GB), et on affiche le swap en continu pour prevenir.
Juge la QUALITE du code genere: completude, absence de troncature/TODO,
couverture des fonctionnalites demandees, taille reelle.
"""
import json, sys, time, urllib.request

OLLAMA = "http://localhost:11434"

def swap_gb():
    try:
        with open("/proc/meminfo") as f:
            info = {l.split(":")[0]: int(l.split()[1]) for l in f}
        return round((info["SwapTotal"] - info["SwapFree"]) / (1024 * 1024), 2)
    except Exception:
        return 0.0

def unload(model):
    try:
        urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}), timeout=60)
    except Exception:
        pass
    time.sleep(3)

def chat(model, user, timeout=5400):
    # STREAMING: on voit la progression EN DIRECT (tokens qui arrivent = vivant).
    # Heartbeat toutes les 15s: [MODEL] +N tokens, X tok/s, swap Y GB -> jamais
    # une boite noire ou on croit que c est fige.
    body = json.dumps({"model": model, "stream": True,
        "messages": [{"role": "user", "content": user}],
        "options": {"temperature": 0.2, "num_ctx": 24576, "num_predict": 8000}}).encode()
    t0 = time.monotonic()
    content, ntok, last_beat = [], 0, t0
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    print(f"    [{model}] chargement du modele (peut prendre plusieurs minutes en swap)...", flush=True)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            tok = obj.get("message", {}).get("content", "")
            if tok:
                content.append(tok); ntok += 1
            now = time.monotonic()
            if now - last_beat >= 15:
                el = now - t0
                print(f"    [{model}] +{ntok} tokens, {round(ntok/el,1)} tok/s, {round(el)}s, swap {swap_gb()}GB (ca AVANCE)", flush=True)
                last_beat = now
            if obj.get("done"):
                break
    dt = time.monotonic() - t0
    return {"content": "".join(content), "sec": round(dt, 1), "tok": ntok,
            "tok_s": round(ntok / dt, 1) if dt else 0}

# Tache CODEUR complexe: un composant riche, complet, sans placeholder.
TASK = ("Ecris un composant React TypeScript COMPLET et production-ready: une DataTable "
        "generique avec tri par colonne (asc/desc), filtre texte multi-colonnes, pagination, "
        "edition inline de cellule (double-clic), navigation clavier (fleches + Entree), et "
        "accessibilite ARIA (role=grid, aria-sort). Code COMPLET, aucun TODO, aucun placeholder, "
        "aucune omission. Un seul fichier .tsx. Reponds avec UNIQUEMENT le code dans un bloc.")

def judge(txt):
    code = txt
    if "```" in txt:
        parts = txt.split("```")
        code = max((p for i, p in enumerate(parts) if i % 2 == 1), key=len, default=txt)
    t = code.lower()
    feats = {
        "tri": any(k in t for k in ["sort", "asc", "desc", "aria-sort"]),
        "filtre": "filter" in t,
        "pagination": any(k in t for k in ["page", "pagination", "slice"]),
        "edition_inline": any(k in t for k in ["ondoubleclick", "editing", "contenteditable", "onblur", "edit"]),
        "clavier": any(k in t for k in ["onkeydown", "arrow", "key ==", "keydown"]),
        "aria": "aria" in t or "role=" in t,
    }
    covered = sum(feats.values())
    no_todo = not any(k in t for k in ["todo", "// ...", "/* ... */", "placeholder", "a implementer", "a completer"])
    complete = code.count("\n") >= 60 and no_todo  # un vrai composant riche
    ok = covered >= 5 and complete
    return {"lignes": code.count("\n"), "couverture": f"{covered}/6", "sans_todo": no_todo,
            "features": [k for k, v in feats.items() if v]}, ok

# Defaut SANS le 80B (qwen3-coder-next 51GB) qui fige un poste local (16GB VRAM +
# 30GB RAM). Le passer en argv seulement sur une machine qui le fait tenir.
MODELS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["qwen3-coder:30b"]
print(f"[{time.strftime('%H:%M:%S')}] swap initial {swap_gb()}GB — CODEUR sur tache complexe", flush=True)
results = {}
for model in MODELS:
    unload("__none__")  # laisse Ollama decharger ce qui traine
    sw = swap_gb()
    print(f"\n[{model}] chargement... (swap avant {sw}GB)", flush=True)
    if sw > 40:
        print(f"  [SECURITE] swap {sw}GB runaway -> abandon", flush=True); break
    try:
        r = chat(model, TASK)
        detail, ok = judge(r["content"])
        results[model] = {"ok": ok, **detail, "tok_s": r["tok_s"], "sec": r["sec"], "swap_apres": swap_gb()}
        print(f"  {'PASS' if ok else 'FAIL'} | {detail['lignes']} lignes, couverture {detail['couverture']}, "
              f"sans_todo={detail['sans_todo']} | {r['tok_s']} tok/s, {r['sec']}s | swap {swap_gb()}GB", flush=True)
    except Exception as e:
        results[model] = {"ok": False, "erreur": str(e)[:80]}
        print(f"  ERREUR: {str(e)[:80]}", flush=True)
    unload(model)

print("\n===== JSON =====\n" + json.dumps(results, ensure_ascii=False, indent=1))
print(f"[{time.strftime('%H:%M:%S')}] swap final {swap_gb()}GB", flush=True)
