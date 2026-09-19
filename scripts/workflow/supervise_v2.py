"""Supervision parcours BAC v2 — split en 2 appels Ollama pour éviter
truncation des réponses qwen3:14b."""
import sys, json, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PDF1 = Path("C:/Users/Juan/Desktop/Notions essentielles Thème 3 Géographie Terminale Techno.pdf")
PDF2 = Path("C:/Users/Juan/Desktop/Résumé Cours Géographie Thème 3 Terminale Techno.pdf")

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:14b"


def log(stage, msg): print(f"[{stage}] {msg}", flush=True)


def extract_pdf_text(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n\n".join((p.extract_text() or "") for p in reader.pages)


def call_ollama(prompt, model=MODEL, timeout=900, num_predict=8192):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 16384, "num_predict": num_predict},
        "keep_alive": "10m",
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "")


def parse_json(text):
    import re
    from json_repair import repair_json
    m = re.search(r"```\s*json\s*\n([\s\S]*?)```", text, re.IGNORECASE)
    raw = m.group(1) if m else text[text.find("{"):text.rfind("}") + 1]
    if not raw:
        return None, "no JSON"
    try:
        return json.loads(raw), None
    except Exception:
        try:
            return json.loads(repair_json(raw)), None
        except Exception as e:
            return None, f"repair fail: {e}"


PROMPT_PART1 = """Tu es Aurora, professeur particulier exigeant. Analyse ce cours de
géographie (terminale techno, thème 3) et produis la PARTIE 1 du parcours
révision : synthèse + fiches + exos.

Format strict (UNIQUEMENT le bloc, sans texte autour) :
```json
{
  "synthese_20_20": {
    "titre": "<titre du chapitre>",
    "ce_qu_il_faut_savoir": ["<connaissance 1>", "<...>"],
    "pieges_classiques": ["<piège 1>", "<...>"],
    "vocabulaire_a_maitriser": [{"terme": "<x>", "definition_exacte": "<y>"}]
  },
  "fiches": [
    {"titre": "<x>", "icone": "<emoji>", "definition": "<def>",
     "idees_cles": ["<bullet 1>"], "schema_ascii_ou_data": "",
     "mnemonique": "<astuce>"}
  ],
  "exos_apprentissage": [
    {"type": "flashcard", "question": "<q>", "reponse": "<r>", "indice": ""}
  ]
}
```

Règles :
  - synthese_20_20.ce_qu_il_faut_savoir : 6-10 items pour 20/20
  - fiches : 4-8 fiches stylisées
  - exos_apprentissage : 8-15 exos type flashcard/qcm/mini-exo
  - tout en français
  - cite dates, acteurs, exemples territoriaux concrets

### COURS

"""


PROMPT_PART2 = """Tu es Aurora, professeur d'examen. Voici les fiches révision déjà
produites. Maintenant produis le CONTRÔLE D'ÉVALUATION (durée 1h, total
20 points = 10 questions + 1 développement).

Format strict :
```json
{
  "duration_min": 60,
  "points_questions": 10,
  "points_developpement": 10,
  "questions": [
    {"id": 1, "q": "<question>", "points": 1, "reponse_attendue": "<x>"}
  ],
  "developpement": {
    "consigne": "<sujet long type Étude de doc / composition>",
    "criteres_attendus": ["<x>"],
    "plan_indicatif": ["<axe 1>"],
    "points": 10
  }
}
```

Règles strictes :
  - EXACTEMENT 10 questions courtes (def, date, formule, acteur)
  - Total points_questions = 10, distribué SELON DIFFICULTÉ
    (peut être 0.5/1/1.5/2 par question — pas obligatoirement 1 chacun)
  - developpement = sujet long type bac, plan indicatif fourni
  - PAS de texte avant ou après le bloc

### FICHES RÉVISION DISPONIBLES

"""


def main():
    log("start", "supervision v2 split 2 calls")
    txt1 = extract_pdf_text(PDF1)
    txt2 = extract_pdf_text(PDF2)
    full = f"=== {PDF1.name} ===\n\n{txt1}\n\n=== {PDF2.name} ===\n\n{txt2}"[:18000]

    # Part 1 : synthese + fiches + exos
    log("part1", "calling Ollama for synthese+fiches+exos")
    t0 = time.time()
    resp1 = call_ollama(PROMPT_PART1 + full, num_predict=6000)
    log("part1", f"  -> {len(resp1)} chars in {time.time()-t0:.1f}s")
    obj1, err1 = parse_json(resp1)
    if not obj1:
        log("FAIL part1", err1)
        Path("temp_part1_raw.txt").write_text(resp1, encoding="utf-8")
        sys.exit(1)
    log("part1", f"  synthese {len(obj1['synthese_20_20']['ce_qu_il_faut_savoir'])} | fiches {len(obj1['fiches'])} | exos {len(obj1['exos_apprentissage'])}")

    # Part 2 : controle (using fiches as context)
    fiches_summary = "\n".join(f"- {f.get('icone','📄')} {f['titre']}: {f.get('definition','')[:120]}" for f in obj1["fiches"])
    log("part2", "calling Ollama for controle")
    t0 = time.time()
    resp2 = call_ollama(PROMPT_PART2 + fiches_summary + "\n\n### COURS RÉSUMÉ\n" + full[:8000], num_predict=4000)
    log("part2", f"  -> {len(resp2)} chars in {time.time()-t0:.1f}s")
    obj2, err2 = parse_json(resp2)
    if not obj2:
        log("FAIL part2", err2)
        Path("temp_part2_raw.txt").write_text(resp2, encoding="utf-8")
        sys.exit(2)
    if "questions" not in obj2:
        log("FAIL part2", "no 'questions' key")
        Path("temp_part2_raw.txt").write_text(resp2, encoding="utf-8")
        sys.exit(3)
    log("part2", f"  questions {len(obj2['questions'])} | dev: {obj2.get('developpement', {}).get('consigne', '')[:60]}...")

    # Merge.
    full_parcours = {**obj1, "controle": obj2}

    # Validate.
    expected = ["synthese_20_20", "fiches", "exos_apprentissage", "controle"]
    for k in expected:
        if k not in full_parcours:
            log("FAIL", f"missing {k}")
            sys.exit(4)
    if len(full_parcours["controle"]["questions"]) < 5:
        log("FAIL", f"only {len(full_parcours['controle']['questions'])} questions")
        sys.exit(5)

    # Save.
    out_dir = Path("application/temp/academy_parcours")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"parcours_geo_{int(time.time())}.json"
    out_path.write_text(json.dumps(full_parcours, ensure_ascii=False, indent=2), encoding="utf-8")
    log("OK", f"saved to {out_path}")

    # Summary.
    s = full_parcours["synthese_20_20"]
    c = full_parcours["controle"]
    print()
    print("=" * 60)
    print(f"TITRE     : {s['titre']}")
    print(f"savoir    : {len(s['ce_qu_il_faut_savoir'])} points clés")
    print(f"pièges    : {len(s.get('pieges_classiques', []))}")
    print(f"vocab     : {len(s.get('vocabulaire_a_maitriser', []))} termes")
    print(f"FICHES    : {len(full_parcours['fiches'])}")
    for f in full_parcours["fiches"][:5]:
        print(f"  - {f.get('icone','📄')} {f['titre']}")
    print(f"EXOS      : {len(full_parcours['exos_apprentissage'])}")
    print(f"CONTRÔLE  : {c['duration_min']} min · {c['points_questions']}+{c['points_developpement']} pts")
    print(f"  questions : {len(c['questions'])}")
    total_q_pts = sum(q.get('points', 0) for q in c['questions'])
    print(f"  total pts questions : {total_q_pts}")
    print(f"  développement : {c['developpement']['consigne'][:80]}...")
    print("=" * 60)
    print(f"\n→ Session prête : {out_path}")


if __name__ == "__main__":
    main()
