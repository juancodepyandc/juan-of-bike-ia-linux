"""storyboard_norm.py — normalisation déterministe d'un storyboard LLM (v90).

Le LLM sous-estime systématiquement la durée de parole (31 mots -> 8 s
au lieu de ~12.4 s à 2.5 mots/s). Plutôt que de dépendre de son
arithmétique, on corrige ici :

  - duration_s >= mots_du_dialogue / WORDS_PER_SECOND + marge
  - duration_s plafonnée au cap de segmentation du pipeline (~20 s)
  - location : héritée du plan précédent si absente (continuité décor)
  - duration_s coercée en float valide

Utilisé par bridge_server.py /api/cinema/storyboard juste après le parse
JSON. Le pipeline a sa propre défense à l'exécution (extension du plan à la
durée réelle du WAV TTS) ; cette normalisation rend en plus l'ETA et le
storyboard affichés à l'UI honnêtes.
"""

WORDS_PER_SECOND = 2.5
SPEECH_MARGIN_S = 0.5
MIN_SHOT_S = 2.0
MAX_SHOT_S = 20.0  # cap segmentation cinema_pipeline (5 x 97 frames)


def _inject_character_descriptions(shot: dict, characters: list) -> None:
    """v90.1 : injecte la description de CHAQUE personnage mentionné dans la
    scène (ou speaker) si elle n'y figure pas déjà — mot pour mot.

    Le LLM ne suit pas la règle de façon fiable ("the grandfather" sans
    description) et Wan2.2 fait alors muter l'apparence à chaque plan
    (constaté : le petit-fils devenait une femme puis un enfant cartoon).
    Injection déterministe = apparence verrouillée."""
    scene = str(shot.get("scene") or "")
    if not scene:
        return
    scene_low = scene.lower()
    speaker = str(shot.get("speaker") or "").strip().lower()
    additions = []
    for char in characters or []:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name") or "").strip()
        desc = str(char.get("description") or "").strip().rstrip(".")
        if not name or not desc:
            continue
        mentioned = name.lower() in scene_low or name.lower() == speaker
        if not mentioned:
            continue
        # Déjà décrit ? On teste un fragment significatif de la description.
        probe = desc[: max(20, len(desc) // 2)].lower()
        if probe in scene_low:
            continue
        additions.append(f"{name} is {desc}.")
    if additions:
        shot["scene"] = scene.rstrip(". ") + ". " + " ".join(additions)


_FRENCH_HINTS = (
    " le ", " la ", " les ", " des ", " une ", " un ", " que ", " qui ",
    " est ", " sont ", " vous ", " je ", " nous ", " ne ", " pas ", " ce ",
    " cette ", " mais ", " avec ", " dans ", " sur ", " pour ",
    "d'", "l'", "qu'", "n'", "j'",
    "é", "è", "ê", "à", "ù", "ç", "œ",
)


def _looks_french(text: str) -> bool:
    probe = f" {str(text or '').lower()} "
    return sum(1 for h in _FRENCH_HINTS if h in probe) >= 2


def align_voice_language(payload: dict) -> dict:
    """v90.4 : aligne voice_lang/voice_preset sur la langue RÉELLE des dialogues.

    Bug LLM récurrent : un personnage étranger connu (Sherlock anglais) reçoit
    voice_lang="en" + preset *_english alors que ses dialogues sont écrits en
    français (langue de l'utilisateur) — le TTS anglais lit alors le français
    avec des phonèmes anglais. On détecte la langue du texte par heuristique
    et on corrige la config voix, dans les deux sens fr<->en."""
    shots = payload.get("shots") or []
    characters = payload.get("characters") or []
    if not shots or not characters:
        return payload

    dialogue_by_speaker = {}
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        speaker = str(shot.get("speaker") or "").strip()
        dlg = str(shot.get("dialogue") or "").strip()
        if speaker and dlg:
            dialogue_by_speaker[speaker] = dialogue_by_speaker.get(speaker, "") + " " + dlg

    for char in characters:
        if not isinstance(char, dict):
            continue
        name = str(char.get("name") or "").strip()
        text = dialogue_by_speaker.get(name, "").strip()
        if len(text.split()) < 4:
            continue
        lang = str(char.get("voice_lang") or "").strip().lower()
        preset = str(char.get("voice_preset") or "").strip()
        is_fr = _looks_french(text)
        if is_fr and lang != "fr":
            char["voice_lang"] = "fr"
            if preset.endswith("_english"):
                char["voice_preset"] = preset[: -len("_english")] + "_french"
            char["voice_lang_adjusted"] = {"from": lang or "?", "to": "fr", "reason": "dialogues en francais"}
        elif not is_fr and lang == "fr":
            char["voice_lang"] = "en"
            if preset.endswith("_french"):
                char["voice_preset"] = preset[: -len("_french")] + "_english"
            char["voice_lang_adjusted"] = {"from": "fr", "to": "en", "reason": "dialogues in english"}
    return payload


def normalize_storyboard(payload: dict) -> dict:
    """Corrige en place (et retourne) le storyboard. Ajoute `duration_adjusted`
    sur chaque shot modifié pour que l'UI puisse l'afficher."""
    shots = payload.get("shots")
    if not isinstance(shots, list):
        return payload

    # v90.3 : qualité supérieure par défaut — si l'appelant n'a rien précisé,
    # "balanced" donne un retry guidé par la QA vision (2 tentatives) avec
    # acceptation du meilleur candidat. "auto" (1 tentative sèche) reste
    # disponible explicitement pour les brouillons rapides.
    if not str(payload.get("quality_mode") or "").strip():
        payload["quality_mode"] = "balanced"

    align_voice_language(payload)

    characters = payload.get("characters") or []
    prev_location = ""
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        _inject_character_descriptions(shot, characters)

        # -- durée valide
        try:
            duration = float(shot.get("duration_s") or 0)
        except Exception:
            duration = 0.0
        if duration <= 0:
            duration = 4.0

        # -- la parole pilote la durée minimale
        dialogue = str(shot.get("dialogue") or "").strip()
        if dialogue:
            words = len(dialogue.split())
            speech_s = words / WORDS_PER_SECOND + SPEECH_MARGIN_S
            if speech_s > duration:
                shot["duration_adjusted"] = {
                    "from": round(duration, 1),
                    "to": round(min(speech_s, MAX_SHOT_S), 1),
                    "reason": f"{words} mots ~ {speech_s:.1f}s de parole",
                }
                duration = speech_s

        duration = max(MIN_SHOT_S, min(MAX_SHOT_S, duration))
        shot["duration_s"] = round(duration, 1)

        # -- continuité décor : hériter le lieu du plan précédent si absent
        location = str(shot.get("location") or "").strip()
        if not location and prev_location:
            shot["location"] = prev_location
        elif location:
            prev_location = location

    return payload
