"""
character_research.py -- Recherche web + analyse qwen3-vl pour comprendre
un personnage demande AVANT d en generer un avatar.

Objectif: eviter qu un prompt "Natsu Dragneel" produise "personnage de profil
avec un dragon a cote" -- on va chercher les elements canoniques du personnage
et injecter un brief precis dans le prompt FLUX + detecter le mode d animation
le plus adapte (humanoid / creature / robot / abstract).

Usage:
  python character_research.py --prompt "Natsu Dragneel" --lang fr
  => JSON {
    ok: true,
    brief: "young man, pink spiky hair, black eyes, tan skin, muscular build, scar on right cheek",
    animation_mode: "humanoid",
    canonical_image_url: "...",  # optionnel
    notes: "known character from Fairy Tail, has classic human mouth and eyes"
  }
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request


def emit(pct: int, detail: str):
    print(f"PROGRESS:{pct}:{detail}", flush=True)


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
VISION_MODELS = [
    "qwen3-vl:30b",
    "qwen3-vl:30b-a3b-q4_K_M",
    "qwen3-vl:8b",
    "llava:latest",
    "minicpm-v:8b",
]


def detect_installed_vision_model() -> str | None:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        installed = [m.get("name", "") for m in data.get("models", [])]
        # Match par prefix pour tolerer les variantes (qwen3-vl:30b-a3b-q4_K_M etc.)
        for candidate in VISION_MODELS:
            base = candidate.split(":")[0]
            for inst in installed:
                if inst == candidate or inst.startswith(base + ":"):
                    return inst
        return None
    except Exception:
        return None


def fetch_wikipedia_summary(query: str, lang: str = "en") -> tuple[str, str | None]:
    """Retourne (summary, image_url) -- l image est le portrait canonique si dispo."""
    try:
        # Cherche la meilleure page Wikipedia
        search_url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=1&namespace=0&format=json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "AuroraIA/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if not data or len(data) < 4 or not data[1]:
            return "", None
        title = data[1][0]
        # Recupere le summary + thumbnail
        summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
        req2 = urllib.request.Request(summary_url, headers={"User-Agent": "AuroraIA/1.0"})
        with urllib.request.urlopen(req2, timeout=8) as r:
            page = json.loads(r.read())
        summary = page.get("extract", "") or ""
        img = None
        if page.get("thumbnail", {}).get("source"):
            img = page["thumbnail"]["source"]
        elif page.get("originalimage", {}).get("source"):
            img = page["originalimage"]["source"]
        return summary[:2000], img
    except Exception as e:
        emit(0, f"Wikipedia fetch failed: {e}")
        return "", None


def classify_animation_mode_heuristic(prompt: str, summary: str) -> str:
    """Heuristique pour deviner le mode d animation sans qwen3-vl.
    Retourne: humanoid | stylized | creature | robot | abstract."""
    text = (prompt + " " + summary).lower()

    # Robot / mechanical
    if re.search(r"\b(robot|android|cyborg|droid|machine|mechanical|ai core|terminator|r2-?d2|wall[- ]?e|bender|transformers)\b", text):
        return "robot"
    # Creature a large gueule
    if re.search(r"\b(dragon|wyvern|godzilla|kaiju|beast|monster|wolf|tiger|lion|bear|shark|crocodile|t-rex|dinosaur)\b", text):
        return "creature"
    # Abstract (entite sans traits humains clairs)
    if re.search(r"\b(blob|slime|spirit|ghost|cloud|energy being|abstract|geometric|slime)\b", text):
        return "abstract"
    # Personnages cartoon/stylises connus -> stylized (overlays classiques inappropries)
    stylized_patterns = [
        r"the amazing digital circus|tadc|caine|pomni|jax|ragatha|gangle|kinger|zooble",
        r"mickey|minnie|goofy|donald|pluto|disney character|cuphead|mugman",
        r"spongebob|patrick star|squidward|krabs|mr krabs",
        r"mario|luigi|bowser|yoshi|toad|princess peach|waluigi",
        r"sonic|tails|knuckles|shadow|eggman",
        r"pokemon|pikachu|charizard|mewtwo|eevee|jigglypuff",
        r"hello kitty|sanrio|kuromi|my melody",
        r"animatronic|fnaf|freddy fazbear|bonnie|chica|foxy",
        r"mascot|mascotte|chibi|kawaii|super deformed",
        r"muppet|kermit|miss piggy|elmo|big bird",
        r"rick and morty|mr meeseeks",
        r"gorillaz|virtual (singer|idol|youtuber|vtuber)",
    ]
    for pattern in stylized_patterns:
        if re.search(pattern, text):
            return "stylized"

    # Defaut: humanoid (mais le vrai test doit passer par qwen3-vl pour etre fiable)
    return "humanoid"


def research_via_qwen3vl(summary: str, image_url: str | None, prompt: str, vision_model: str) -> dict:
    """Appelle qwen3-vl pour generer un SCHEMA ANATOMIQUE DETAILLE du personnage.
    Au lieu d un template rigide humanoid/creature, on obtient une description
    precise de COMMENT CE personnage bouge ses yeux, sa bouche, et parle."""
    instruction = (
        f'You research a character for a face-animation system. Target: "{prompt}".\n'
        f"Wikipedia summary (if any):\n{summary[:1500]}\n\n"
        "You must describe this character PRECISELY so an animator can make it speak correctly.\n\n"
        "Return STRICTLY this JSON (no prose, no markdown fences):\n"
        "{\n"
        '  "brief": "<8-20 words ENGLISH: hair, skin, eyes, outfit color, distinctive visual marks>",\n'
        '  "face_complexity": "simple" | "stylized" | "complex",\n'
        '  "eye_system": {\n'
        '    "shape": "<round pupils / oval white discs / glowing dots / no eyes / slit / cross-pattern / etc.>",\n'
        '    "blink_style": "classic_close" | "scale_to_zero" | "disappear_reappear" | "none" | "<custom>",\n'
        '    "can_detach": true|false,\n'
        '    "color": "<hex or color name>"\n'
        '  },\n'
        '  "mouth_system": {\n'
        '    "shape": "<closed lips / wavy line / horizontal gash / no mouth / entire head is mouth / visor / etc.>",\n'
        '    "speak_style": "open_close_vertical" | "stretch_distort" | "color_pulse" | "glow" | "shape_swap" | "none",\n'
        '    "color": "<hex or color name>",\n'
        '    "position_hint": "<center_lower / absent / whole_face / etc.>"\n'
        '  },\n'
        '  "head_behavior": "stable" | "floats" | "rotates" | "deforms_globally",\n'
        '  "idle_motion": "<breathing / floating / subtle pulse / eye occasional detach / etc.>",\n'
        '  "speaking_motion": "<detailed description of what visually happens when this character talks — mouth behavior, head movement, eye reaction, color shifts>",\n'
        '  "rendering_strategy": "overlay" | "global_effects" | "sprite_swap" | "none",\n'
        '  "warnings": "<elements to AVOID in image generation: side profile, companions, weapons, scenery>"\n'
        "}\n\n"
        "face_complexity guide:\n"
        "  simple = classic human / anthropomorphic with normal face\n"
        "  stylized = cartoon with non-standard features (Caine from TADC, classic cartoon villain, mascot)\n"
        "  complex = abstract entity, shape-shifter, no fixed face\n\n"
        "rendering_strategy guide:\n"
        "  overlay = dessiner une bouche/yeux classiques par dessus l image FLUX (OK pour humain)\n"
        "  global_effects = DO NOT draw local features, use scale/glow/color pulse sur l image entiere (Caine, abstract entities)\n"
        "  sprite_swap = needs multiple FLUX generations for different phonemes (advanced, skip if unsure)\n"
        "  none = static image, only idle breath, no mouth animation\n\n"
        "Rules:\n"
        "- Be concrete and VISUAL. Read the Wikipedia/image carefully.\n"
        "- For stylized/complex characters (Caine, mascots), PREFER rendering_strategy=global_effects (do not fake a human mouth on them).\n"
        "- If the character has a very specific mouth behavior (e.g. wavy line that distorts), describe it precisely.\n"
        "- OUTPUT ONLY THE JSON OBJECT."
    )

    # Si on a une URL d image, on la telecharge et on l envoie
    image_base64 = None
    if image_url:
        try:
            emit(30, "Telechargement image canonique...")
            req = urllib.request.Request(image_url, headers={"User-Agent": "AuroraIA/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                import base64
                image_base64 = base64.b64encode(r.read()).decode("ascii")
        except Exception as e:
            emit(30, f"Image download failed: {e}")

    # Appel Ollama
    body = {
        "model": vision_model,
        "messages": [{
            "role": "user",
            "content": instruction,
            **({"images": [image_base64]} if image_base64 else {}),
        }],
        "stream": False,
        "options": {"temperature": 0.2},
        # keep_alive en seconde: garde le modele charge en VRAM pour 30 min
        # Ca evite de payer le cout de reload 19GB a chaque appel.
        "keep_alive": "30m",
    }
    try:
        emit(45, f"Warmup {vision_model} (premiere reponse peut prendre 30-120s a froid)...")
        # Warmup: un appel rapide pour charger le modele en VRAM si pas deja
        try:
            warmup_body = {"model": vision_model, "prompt": "ok", "stream": False, "keep_alive": "30m"}
            warmup_req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=json.dumps(warmup_body).encode(),
                headers={"Content-Type": "application/json"},
            )
            # Timeout 150s pour le warmup (chargement 19GB peut prendre >1min)
            with urllib.request.urlopen(warmup_req, timeout=150) as _:
                pass
            emit(48, "Modele charge, analyse en cours...")
        except Exception as warmup_err:
            emit(48, f"Warmup warning (non bloquant): {warmup_err}")

        emit(50, f"Analyse via {vision_model}...")
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        # Timeout generous 180s: modele charge + image analyse + JSON strict peut
        # prendre 30-60s meme charge. Evite les fails gratuits.
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
        raw = (resp.get("message") or {}).get("content", "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        parsed = json.loads(m.group(0))
        # Derive animation_mode (legacy, pour compat) depuis face_complexity
        fc = str(parsed.get("face_complexity", "simple"))
        rs = str(parsed.get("rendering_strategy", "overlay"))
        if rs == "global_effects" or fc == "complex":
            anim_mode = "stylized"
        elif rs == "none":
            anim_mode = "abstract"
        else:
            anim_mode = "humanoid"
        return {
            "brief": str(parsed.get("brief", ""))[:400],
            "animation_mode": anim_mode,
            "face_complexity": fc,
            "rendering_strategy": rs,
            "eye_system": parsed.get("eye_system") or {},
            "mouth_system": parsed.get("mouth_system") or {},
            "head_behavior": str(parsed.get("head_behavior", "stable")),
            "idle_motion": str(parsed.get("idle_motion", ""))[:200],
            "speaking_motion": str(parsed.get("speaking_motion", ""))[:400],
            "warnings": str(parsed.get("warnings", ""))[:300],
        }
    except Exception as e:
        emit(50, f"qwen3-vl research failed: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="", help="Demande utilisateur (ex: 'Natsu Dragneel')")
    parser.add_argument("--image-path", default=None, help="Chemin vers une photo locale a analyser")
    parser.add_argument("--lang", default="fr", help="Langue Wikipedia a consulter en priorite")
    args = parser.parse_args()

    prompt_text = args.prompt or (os.path.basename(args.image-path) if args.image_path else "unknown subject")
    emit(0, f"Recherche sur: {prompt_text}")

    image_url = None
    summary = ""
    if args.image_path and os.path.exists(args.image_path):
        import base64
        emit(10, f"Lecture photo locale: {args.image_path}")
        try:
            with open(args.image_path, "rb") as img_f:
                image_base64 = base64.b64encode(img_f.read()).decode("ascii")
            image_url = f"data:image/png;base64,{image_base64}"
        except Exception as e:
            emit(10, f"Erreur lecture image locale: {e}")

    if args.prompt:
        emit(15, "Recherche Wikipedia...")
        summary, wiki_img = fetch_wikipedia_summary(args.prompt, args.lang)
        if not summary and args.lang != "en":
            summary, wiki_img = fetch_wikipedia_summary(args.prompt, "en")
        if not image_url and wiki_img:
            image_url = wiki_img

    # Etape 2: Modele vision
    emit(25, "Detection modele vision...")
    vision_model = detect_installed_vision_model()

    # Etape 3: qwen3-vl si dispo, sinon heuristique seule
    research = {}
    if vision_model:
        research = research_via_qwen3vl(summary, image_url, prompt_text, vision_model)

    # Fallback heuristique si qwen3-vl fail ou absent
    if not research:
        legacy_mode = classify_animation_mode_heuristic(prompt_text, summary)
        research = {
            "brief": f"character based on: {prompt_text}",
            "animation_mode": "stylized" if legacy_mode != "humanoid" else "humanoid",
            "face_complexity": "simple" if legacy_mode == "humanoid" else "stylized",
            "rendering_strategy": "overlay" if legacy_mode == "humanoid" else "global_effects",
            "eye_system": {},
            "mouth_system": {},
            "head_behavior": "stable",
            "idle_motion": "subtle breathing",
            "speaking_motion": "generic animation",
            "warnings": "avoid side profile, companions, weapons, scenery",
        }

    emit(100, f"Brief: {research.get('brief', '')[:60]} | strategy={research.get('rendering_strategy', '?')}")
    print(json.dumps({
        "ok": True,
        "prompt": prompt_text,
        "image_path": args.image_path,
        "brief": research.get("brief", ""),
        "animation_mode": research.get("animation_mode", "humanoid"),
        "face_complexity": research.get("face_complexity", "simple"),
        "rendering_strategy": research.get("rendering_strategy", "overlay"),
        "eye_system": research.get("eye_system", {}),
        "mouth_system": research.get("mouth_system", {}),
        "head_behavior": research.get("head_behavior", "stable"),
        "idle_motion": research.get("idle_motion", ""),
        "speaking_motion": research.get("speaking_motion", ""),
        "warnings": research.get("warnings", ""),
        "wiki_summary": summary[:500] if summary else "",
        "canonical_image": image_url if not args.image_path else None,
        "vision_model": vision_model,
    }))


if __name__ == "__main__":
    main()

