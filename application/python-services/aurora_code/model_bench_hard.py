#!/usr/bin/env python3
"""Benchmark CODEUR dur et OBJECTIF: le code genere est EXECUTE contre des cas de
test caches (bords piegeux). Score = fraction de tests reellement verts, pas une
heuristique de ressemblance. Memory-safe (un modele a la fois, decharge entre),
streaming + heartbeat (progression visible), execution en sous-processus avec
timeout (sur + anti-hang).
"""
import json, os, re, subprocess, sys, tempfile, time, urllib.request

OLLAMA = "http://localhost:11434"
SCRATCH = "/tmp/bench_hard"
os.makedirs(SCRATCH, exist_ok=True)

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
    time.sleep(2)

def chat(model, prompt, label, num_gpu=None, timeout=7200):
    opts = {"temperature": 0.1, "num_ctx": 16384, "num_predict": 2500}
    if num_gpu is not None:
        opts["num_gpu"] = num_gpu  # 0 = CPU-only -> ne touche pas la RTX -> ecran fluide
    body = json.dumps({"model": model, "stream": True,
        "messages": [{"role": "user", "content": prompt}], "options": opts}).encode()
    t0 = time.monotonic(); out = []; n = 0; beat = t0
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            t = o.get("message", {}).get("content", "")
            if t:
                out.append(t); n += 1
            now = time.monotonic()
            if now - beat >= 20:
                print(f"      [{model}] {label}: +{n} tok, {round(n/(now-t0),1)} tok/s, {round(now-t0)}s, swap {swap_gb()}GB (avance)", flush=True)
                beat = now
            if o.get("done"):
                break
    return "".join(out)

def extract_code(txt):
    if "```" in txt:
        blocks = re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", txt, re.S)
        if blocks:
            return max(blocks, key=len)
    return txt

def run_task(code, runner):
    path = os.path.join(SCRATCH, f"t_{int(time.monotonic()*1000)}.py")
    with open(path, "w") as f:
        f.write(code + "\n\n" + runner)
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=15)
        m = re.search(r"SCORE (\d+)/(\d+)", p.stdout)
        if m:
            return int(m.group(1)), int(m.group(2))
        return 0, None  # a plante / pas de score
    except subprocess.TimeoutExpired:
        return 0, None
    finally:
        try: os.remove(path)
        except OSError: pass

# --- Runner generique: importe entry, execute cases (input tuple -> expected) ---
def make_runner(entry, cases, cmp="eq"):
    # repr() -> litteraux Python valides (True/False/None), pas du JSON minuscule.
    return f'''
_cases = {repr(cases)}
_ok = 0
for _inp, _exp in _cases:
    try:
        _r = {entry}(*_inp)
        if {"_r == _exp" if cmp=="eq" else "sorted(_r) == sorted(_exp)"}:
            _ok += 1
    except Exception:
        pass
print(f"SCORE {{_ok}}/{{len(_cases)}}")
'''

TASKS = [
    {"name": "merge_intervals", "entry": "merge_intervals",
     "prompt": "Ecris UNIQUEMENT une fonction Python `merge_intervals(intervals)` qui fusionne des intervalles [debut,fin] qui se chevauchent (adjacents = chevauchent). Retourne la liste triee. Gere: vide, un seul, non tries, imbriques. Code seul.",
     "cases": [[[[]], []], [[[[1,3]]], [[1,3]]], [[[[1,3],[2,6],[8,10],[15,18]]], [[1,6],[8,10],[15,18]]],
               [[[[1,4],[4,5]]], [[1,5]]], [[[[5,6],[1,3],[2,4]]], [[1,4],[5,6]]], [[[[1,10],[2,3],[4,5]]], [[1,10]]]]},
    {"name": "calc_precedence", "entry": "calc",
     "prompt": "Ecris UNIQUEMENT une fonction Python `calc(expr: str) -> float` qui evalue une expression avec + - * / et parentheses, en respectant la priorite des operateurs. Sans eval(). Ex: calc('2+3*4')==14, calc('(2+3)*4')==20. Code seul.",
     "cases": [[["2+3*4"], 14.0], [["(2+3)*4"], 20.0], [["10/2-3"], 2.0], [["2*(3+4)*2"], 28.0],
               [["1+2+3+4"], 10.0], [["100/(2+3)/2"], 10.0]]},
    {"name": "flatten_deep", "entry": "flatten",
     "prompt": "Ecris UNIQUEMENT une fonction Python `flatten(lst)` qui aplatit une liste imbriquee a profondeur arbitraire. Gere: vide, deja plate, tres imbriquee, elements non-listes. Code seul.",
     "cases": [[[[]], []], [[[1,2,3]], [1,2,3]], [[[1,[2,[3,[4]]]]], [1,2,3,4]],
               [[[[[1]],2,[[3,4]]]], [1,2,3,4]], [[[1,[],2]], [1,2]]]},
    {"name": "roman_to_int", "entry": "roman_to_int",
     "prompt": "Ecris UNIQUEMENT une fonction Python `roman_to_int(s: str) -> int` (chiffres romains -> entier). Gere la soustraction (IV=4, IX=9, XL=40, CM=900). Code seul.",
     "cases": [[["III"], 3], [["IV"], 4], [["IX"], 9], [["LVIII"], 58], [["MCMXCIV"], 1994], [["XLII"], 42]]},
    {"name": "is_balanced", "entry": "is_balanced",
     "prompt": "Ecris UNIQUEMENT une fonction Python `is_balanced(s: str) -> bool` qui verifie que les parentheses/crochets/accolades ()[]{} sont bien equilibres et imbriques. Gere vide (True), non fermes, croises. Code seul.",
     "cases": [[[""], True], [["()"], True], [["()[]{}"], True], [["(]"], False], [["([)]"], False], [["{[()]}"], True], [["((("], False]]},
    {"name": "topo_sort", "entry": "topo_sort", "cmp": "eq",
     "prompt": "Ecris UNIQUEMENT une fonction Python `topo_sort(n, edges)` : tri topologique d un graphe oriente a n noeuds (0..n-1), edges = liste [a,b] (a avant b). Retourne None si cycle. Sinon un ordre valide (n importe lequel). Code seul.",
     "cases": [[[2, [[0,1]]], [0,1]], [[2, [[0,1],[1,0]]], None]]},
    {"name": "lru_cache_class", "entry": "_lru_test", "cmp": "eq",
     "prompt": "Ecris UNIQUEMENT une classe Python `LRUCache` avec `__init__(self, capacity)`, `get(self, key)` (-1 si absent), `put(self, key, value)` (evince le moins recemment utilise si plein). Code seul.",
     "cases": [[[], "[2,-1,-1,3,4]"]],
     "runner_override": '''
def _lru_test():
    c = LRUCache(2); c.put(1,1); c.put(2,2)
    r=[c.get(1)]; c.put(3,3); r.append(c.get(2)); c.put(4,4); r.append(c.get(1)); r.append(c.get(3)); r.append(c.get(4))
    return str(r)
_cases=[([], "[1,-1,-1,3,4]")]
_ok=0
for _inp,_exp in _cases:
    try:
        if _lru_test()==_exp: _ok+=1
    except Exception: pass
print(f"SCORE {_ok}/1")
'''},
    {"name": "fix_binary_search", "entry": "bsearch",
     "prompt": "Ce code de recherche dichotomique a un BUG (boucle infinie / mauvais resultat). Corrige-le. Retourne l index de target ou -1.\n\ndef bsearch(arr, target):\n    lo, hi = 0, len(arr)\n    while lo < hi:\n        mid = (lo+hi)//2\n        if arr[mid] == target: return mid\n        elif arr[mid] < target: lo = mid\n        else: hi = mid\n    return -1\n\nDonne UNIQUEMENT la fonction corrigee.",
     "cases": [[[[1,2,3,4,5],3], 2], [[[1,2,3,4,5],1], 0], [[[1,2,3,4,5],5], 4], [[[1,2,3,4,5],6], -1], [[[],1], -1], [[[1,3,5,7,9],7], 3]]},
]

def main():
  # Defaut SANS le 80B (qwen3-coder-next 51GB): il ne tient pas en 16GB VRAM +
  # 30GB RAM -> pagination disque -> GEL du poste (vecu). Passer un modele lourd
  # explicitement en argv si la machine peut vraiment le faire tourner.
  MODELS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["qwen3-coder:30b"]
  print(f"[{time.strftime('%H:%M:%S')}] BENCH DUR — {len(TASKS)} taches executees, swap {swap_gb()}GB", flush=True)
  results = {m: {"passed": 0, "total": 0, "tasks": {}} for m in MODELS}

  for model in MODELS:
    print(f"\n===== {model} =====", flush=True)
    unload("__x__")
    for task in TASKS:
        if swap_gb() > 45:
            print(f"  [SECURITE] swap {swap_gb()}GB -> abandon modele", flush=True); break
        try:
            # RTX liberee (affichage sur iGPU AMD) -> tous les modeles sur GPU
            # (ollama met ce qui tient en VRAM, le reste en RAM/swap). Test equitable.
            txt = chat(model, task["prompt"], task["name"], num_gpu=None)
            code = extract_code(txt)
            runner = task.get("runner_override") or make_runner(task["entry"], task["cases"], task.get("cmp", "eq"))
            ok, tot = run_task(code, runner)
            tot = tot if tot else len(task["cases"])
            results[model]["passed"] += ok; results[model]["total"] += tot
            results[model]["tasks"][task["name"]] = f"{ok}/{tot}"
            print(f"  {task['name']:20} -> {ok}/{tot} {'OK' if ok==tot else 'partiel' if ok else 'ECHEC'} | swap {swap_gb()}GB", flush=True)
        except Exception as e:
            results[model]["tasks"][task["name"]] = f"ERR:{str(e)[:30]}"
            print(f"  {task['name']:20} -> ERREUR {str(e)[:40]}", flush=True)
    unload(model)

  print("\n===== VERDICT =====", flush=True)
  for m, r in results.items():
    pct = round(100 * r["passed"] / r["total"], 1) if r["total"] else 0
    print(f"  {m:26} {r['passed']}/{r['total']} = {pct}%", flush=True)
  print("\n===== JSON =====\n" + json.dumps(results, ensure_ascii=False, indent=1))
  print(f"[{time.strftime('%H:%M:%S')}] swap final {swap_gb()}GB", flush=True)


if __name__ == "__main__":
    main()
