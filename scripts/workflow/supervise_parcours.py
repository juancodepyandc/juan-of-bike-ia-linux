"""Supervise un parcours BAC complet end-to-end :
  1. Extrait texte + images des 2 PDF géo
  2. Appelle Ollama qwen3-vl avec le system prompt parcours-bac
  3. Valide la structure JSON
  4. Si OK : écrit dans application/temp/parcours_geo_session.json + rapporte
  5. Si KO : retry avec context plus court (drop images si trop)
"""
import sys, os, json, time, base64
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PDF1 = Path("C:/Users/Juan/Desktop/Notions essentielles Thème 3 Géographie Terminale Techno.pdf")
PDF2 = Path("C:/Users/Juan/Desktop/Résumé Cours Géographie Thème 3 Terminale Techno.pdf")

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_TEXT = "qwen3:14b"
MODEL_VISION = "qwen3-vl:30b"

def log(stage, msg):
    print(f"[{stage}] {msg}", flush=True)


def extract_pdf_text(path):
    """Extract plain text via pypdf or pdfminer."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        log("pdf-text-err", f"{path.name}: {e}")
        return ""


def extract_pdf_images(path, max_pages=4):
    """Render PDF pages to PNG via pdf2image for vision LLM. Max max_pages."""
    try:
        from pdf2image import convert_from_path
        # poppler may not be on PATH; try to find it
        poppler_path = None
        for cand in ["C:/Program Files/poppler/bin", "C:/poppler/bin"]:
            if Path(cand).exists():
                poppler_path = cand
                break
        kwargs = {"dpi": 120, "first_page": 1, "last_page": max_pages}
        if poppler_path:
            kwargs["poppler_path"] = poppler_path
        images = convert_from_path(str(path), **kwargs)
        return images
    except Exception as e:
        log("pdf-img-err", f"{path.name}: {e}")
        return []


def img_to_b64(pil_img, max_side=1024):
    from io import BytesIO
    w, h = pil_img.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        pil_img = pil_img.resize((int(w * ratio), int(h * ratio)))
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


SYSTEM_PROMPT = """Tu es Aurora, professeur particulier exigeant. L'utilisateur a uploadé 2 PDFs
de cours de géographie (terminale techno, thème 3). Analyse texte + images
(cartes, schémas, tableaux). Tu produis un parcours révision EXHAUSTIF en
UN SEUL bloc JSON valide.

Format strict (rends UNIQUEMENT le bloc, sans texte autour) :

```json
{
  "synthese_20_20": {
    "titre": "<titre du chapitre>",
    "ce_qu_il_faut_savoir": ["<connaissance critique 1>", "<...>"],
    "pieges_classiques": ["<piège 1>", "<...>"],
    "vocabulaire_a_maitriser": [{"terme": "<x>", "definition_exacte": "<y>"}]
  },
  "fiches": [
    {"titre": "<x>", "icone": "<emoji>", "definition": "<def>",
     "idees_cles": ["<bullet 1>"], "schema_ascii_ou_data": "",
     "mnemonique": "<astuce>", "ressources_externes": []}
  ],
  "exos_apprentissage": [
    {"type": "flashcard", "question": "<q>", "reponse": "<r>", "indice": ""}
  ],
  "controle": {
    "duration_min": 60,
    "points_questions": 10,
    "points_developpement": 10,
    "questions": [
      {"id": 1, "q": "<question>", "points": 1, "reponse_attendue": "<x>"}
    ],
    "developpement": {
      "consigne": "<sujet>",
      "criteres_attendus": ["<x>"],
      "plan_indicatif": ["<axe 1>"],
      "points": 10
    }
  }
}
```

Règles :
  - Géographie : utilise dates, acteurs nommés, exemples territoriaux concrets,
    cartes mentales et plans-types HG.
  - "ce_qu_il_faut_savoir" : 6-10 connaissances pour 20/20.
  - "fiches" : 4-8 fiches stylisées.
  - "exos_apprentissage" : 8-15 exos.
  - "controle.questions" : EXACTEMENT 10 questions, total points = 10
    (distribué selon difficulté, peut être 0.5/1/1.5/2 par question).
  - "controle.developpement" : sujet long type "Étude de doc" ou
    "composition", 10 points.
  - Tout en français.
"""


def call_ollama_vision(prompt, images_b64, model=MODEL_VISION, timeout=600):
    """Stream Ollama generate with images. Returns response text."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": images_b64,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 16384},
        "keep_alive": "10m",
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return data.get("response", "")


def parse_parcours_json(text):
    """Extract and validate the parcours JSON."""
    import re
    # Try fenced block first.
    m = re.search(r"```\s*json\s*\n([\s\S]*?)```", text, re.IGNORECASE)
    raw = m.group(1).strip() if m else None
    if not raw:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            raw = text[first:last + 1]
    if not raw:
        return None, "no JSON found"
    try:
        obj = json.loads(raw)
    except Exception:
        # Tolerant repair via json-repair (truncated commas, missing braces, etc.).
        try:
            from json_repair import repair_json
            repaired = repair_json(raw)
            obj = json.loads(repaired)
            log("repair", "JSON repaired via json-repair")
        except Exception as e2:
            return None, f"JSON parse + repair failed: {e2}"
    # Validate shape.
    required = ["synthese_20_20", "fiches", "exos_apprentissage", "controle"]
    for k in required:
        if k not in obj:
            return None, f"missing key: {k}"
    if not isinstance(obj["controle"].get("questions"), list):
        return None, "controle.questions not a list"
    if len(obj["controle"]["questions"]) < 5:
        return None, f"only {len(obj['controle']['questions'])} questions (expect ~10)"
    if not obj["controle"].get("developpement"):
        return None, "no developpement"
    return obj, None


def main():
    log("start", "supervision parcours BAC géographie")

    # Step 1 : extract text
    log("pdf", f"extracting text from {PDF1.name}")
    txt1 = extract_pdf_text(PDF1)
    log("pdf", f"  -> {len(txt1)} chars")
    log("pdf", f"extracting text from {PDF2.name}")
    txt2 = extract_pdf_text(PDF2)
    log("pdf", f"  -> {len(txt2)} chars")
    if not txt1 and not txt2:
        log("FAIL", "0 text extracted, abort")
        sys.exit(1)
    full_text = f"=== {PDF1.name} ===\n\n{txt1}\n\n=== {PDF2.name} ===\n\n{txt2}"
    full_text = full_text[:25000]  # cap to fit context

    # Step 2 : extract images (max 3 per pdf to fit context).
    log("img", f"extracting images from {PDF1.name}")
    imgs1 = extract_pdf_images(PDF1, max_pages=3)
    log("img", f"  -> {len(imgs1)} pages")
    log("img", f"extracting images from {PDF2.name}")
    imgs2 = extract_pdf_images(PDF2, max_pages=3)
    log("img", f"  -> {len(imgs2)} pages")
    images_b64 = []
    for img in (imgs1 + imgs2)[:6]:
        try:
            images_b64.append(img_to_b64(img))
        except Exception as e:
            log("img-encode-err", str(e))
    log("img", f"total {len(images_b64)} images encoded for vision LLM")

    # Step 3 : call Ollama (vision if images, text otherwise).
    user_prompt = f"### CONTENU LEÇON\n\n{full_text}\n\nGénère maintenant le parcours JSON complet."
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    if images_b64:
        log("ollama", f"calling {MODEL_VISION} with {len(images_b64)} images...")
        t0 = time.time()
        try:
            response = call_ollama_vision(full_prompt, images_b64, model=MODEL_VISION, timeout=900)
            log("ollama", f"  -> response {len(response)} chars in {time.time()-t0:.1f}s")
        except Exception as e:
            log("ollama-err", str(e))
            log("retry", "fallback to text-only model")
            response = call_ollama_vision(full_prompt, [], model=MODEL_TEXT, timeout=600)
            log("ollama", f"  fallback -> {len(response)} chars in {time.time()-t0:.1f}s")
    else:
        log("ollama", f"calling {MODEL_TEXT} (text-only)...")
        t0 = time.time()
        response = call_ollama_vision(full_prompt, [], model=MODEL_TEXT, timeout=600)
        log("ollama", f"  -> response {len(response)} chars in {time.time()-t0:.1f}s")

    # Step 4 : parse and validate.
    parcours, err = parse_parcours_json(response)
    if not parcours:
        log("FAIL", f"validation failed: {err}")
        # Save raw output for debug.
        Path("temp_parcours_raw.txt").write_text(response, encoding="utf-8")
        log("debug", "raw response saved to temp_parcours_raw.txt")
        sys.exit(2)

    # Step 5 : save and report.
    out_dir = Path("application/temp/academy_parcours")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"parcours_geo_{int(time.time())}.json"
    out_path.write_text(json.dumps(parcours, ensure_ascii=False, indent=2), encoding="utf-8")
    log("OK", f"saved to {out_path}")

    # Quick summary.
    s = parcours["synthese_20_20"]
    print()
    print("=" * 60)
    print(f"TITRE     : {s['titre']}")
    print(f"savoir    : {len(s['ce_qu_il_faut_savoir'])} points clés")
    print(f"pièges    : {len(s.get('pieges_classiques', []))}")
    print(f"vocab     : {len(s.get('vocabulaire_a_maitriser', []))} termes")
    print(f"FICHES    : {len(parcours['fiches'])}")
    for f in parcours["fiches"][:3]:
        print(f"  - {f.get('icone','📄')} {f['titre']}")
    print(f"EXOS      : {len(parcours['exos_apprentissage'])}")
    c = parcours["controle"]
    print(f"CONTRÔLE  : {c['duration_min']} min · {c['points_questions']}+{c['points_developpement']} pts")
    print(f"  questions : {len(c['questions'])}")
    total_q_pts = sum(q.get("points", 0) for q in c["questions"])
    print(f"  total pts questions : {total_q_pts}")
    print(f"  développement : {c['developpement']['consigne'][:80]}...")
    print("=" * 60)
    print(f"\n→ Session prête : {out_path}")


if __name__ == "__main__":
    main()
