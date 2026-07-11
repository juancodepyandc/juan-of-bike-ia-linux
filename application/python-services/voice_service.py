"""
juan of bike IA - Service vocal (STT + TTS)

Usage:
  python voice_service.py --mode stt --audio <path>
  python voice_service.py --mode tts --text "..." --output <path> [--lang fr]

STT: Voxtral-Small-24B-2507 en priorite, fallback faster-whisper large-v3
TTS: Kokoro-82M (voix locale haute qualite)
"""

import argparse
import gc
import json
import os
import subprocess
import sys

from cache_paths import configure_ml_cache_environment

# Voxtral-Small-24B-2507 : modele complet non-mini (remplace Mini-4B-Realtime)
# Plus grand (24B), plus precis, meme API HuggingFace
VOXTRAL_MODEL = "mistralai/Voxtral-Small-24B-2507"
# STT français dedie (bofenghuang, distille de large-v3) : WER français nettement
# meilleur que large-v3-turbo generaliste, ~2x plus rapide, format CTranslate2
# compatible faster-whisper. Active par defaut (AURORA_WHISPER_FR != "0") avec
# repli automatique sur large-v3-turbo si le chargement/telechargement echoue —
# donc aucune regression possible du STT existant.
# NB: si faster-whisper ne trouve pas les poids CT2 (sous-dossier "ctranslate2"),
# le repo pret-a-l-emploi "brandenkmurray/faster-whisper-large-v3-french-distil-dec16"
# est un fallback (CT2 a la racine).
WHISPER_FR_MODEL = "bofenghuang/whisper-large-v3-french-distil-dec16"
WHISPER_FR_ENABLED = os.environ.get("AURORA_WHISPER_FR", "1") != "0"
WHISPER_FALLBACK = "large-v3-turbo"
WHISPER_FALLBACK_SECONDARY = "small"
KOKORO_MODEL = "hexgrad/Kokoro-82M"

REQUIRED_STT = {
    "faster_whisper": "faster-whisper",
    "soundfile": "soundfile",
    "scipy": "scipy",
}

REQUIRED_TTS = {
    "kokoro": "kokoro>=0.9.4",
    "soundfile": "soundfile",
}

REQUIRED_PIPER = {
    "piper": "piper-tts",
    "onnxruntime": "onnxruntime",
    "soundfile": "soundfile",
}

REQUIRED_EDGE_TTS = {
    "edge_tts": "edge-tts",
}

# Voix Microsoft Neural (via edge-tts) — qualite studio, gratuit, cloud Azure
# Denise: femme FR naturelle, Henri: homme FR
EDGE_TTS_VOICES = {
    "fr": "fr-FR-DeniseNeural",
    "en": "en-US-AriaNeural",
}

# Mapping persona Aurora -> voix Edge-TTS (par langue). Permet d'avoir une voix
# distincte par agent (Lyra=Denise douce, Iris=Brigitte vive, Cinema=Henri grave,
# Glyph=Yvette neutre, Sumi=Eloise chaude, Atlas=Maurice fort, Sage=Claude posée,
# Phantom=Alain tranchant). Fallback sur la voix par defaut si persona inconnue.
EDGE_TTS_VOICE_PERSONAS = {
    "lyra-soft":      {"fr": "fr-FR-DeniseNeural",  "en": "en-US-JennyNeural"},
    "iris-bright":    {"fr": "fr-FR-BrigitteNeural", "en": "en-US-AriaNeural"},
    "cinema-deep":    {"fr": "fr-FR-HenriNeural",   "en": "en-US-GuyNeural"},
    "glyph-precise":  {"fr": "fr-FR-YvetteNeural",  "en": "en-US-AvaNeural"},
    "sumi-warm":      {"fr": "fr-FR-EloiseNeural",  "en": "en-US-EmmaNeural"},
    "atlas-strong":   {"fr": "fr-FR-MauriceNeural", "en": "en-US-RyanNeural"},
    "sage-mellow":    {"fr": "fr-FR-ClaudeNeural",  "en": "en-US-AndrewNeural"},
    "phantom-sharp":  {"fr": "fr-FR-AlainNeural",   "en": "en-US-EricNeural"},
}

PIPER_VOICES = {
    "fr": "fr_FR-siwis-medium",
    "en": "en_US-lessac-medium",
}

PIPER_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aurora-ia", "piper-voices")

REQUIRED_VOXTRAL = {
    "transformers": "transformers>=4.45.0",
    "accelerate": "accelerate",
}

# Voix Kokoro par langue
KOKORO_VOICES = {
    "fr": "ff_siwis",
    "en": "af_heart",
}
KOKORO_LANG_CODES = {
    "fr": "f",
    "en": "a",
}


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


# ---------------------------------------------------------------------------
# Rhubarb Lip Sync — phonèmes frame-accurate (optionnel)
# ---------------------------------------------------------------------------

def _find_rhubarb() -> str | None:
    """Cherche l'exécutable Rhubarb dans application/bin/ puis dans le PATH."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace  = os.path.dirname(script_dir)   # application/
    candidates = [
        os.path.join(workspace, "bin", "rhubarb.exe"),   # Windows
        os.path.join(workspace, "bin", "rhubarb"),        # Linux / Mac
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Fallback : rhubarb dans le PATH système
    try:
        result = subprocess.run(
            ["rhubarb", "--version"], capture_output=True, timeout=3
        )
        if result.returncode == 0:
            return "rhubarb"
    except Exception:
        pass
    return None


def _run_rhubarb(wav_path: str) -> list:
    """
    Appelle Rhubarb Lip Sync sur wav_path.
    Retourne [{start, end, value}] ou [] si Rhubarb absent ou en échec.
    """
    rhubarb = _find_rhubarb()
    if not rhubarb:
        return []

    json_out = wav_path + ".rhubarb.json"
    try:
        emit("rhubarb", "Analyse phonémique Rhubarb en cours...")
        result = subprocess.run(
            [rhubarb, "-f", "json", "-o", json_out, wav_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            emit(
                "rhubarb_warn",
                f"Rhubarb code {result.returncode}: "
                f"{result.stderr.decode(errors='replace')[:120]}",
            )
            return []

        with open(json_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        cues = data.get("mouthCues", [])
        emit("rhubarb", f"{len(cues)} cues phonémiques extraits")
        return [
            {"start": c["start"], "end": c["end"], "value": c["value"]}
            for c in cues
        ]
    except Exception as exc:
        emit("rhubarb_warn", f"Rhubarb erreur ({type(exc).__name__}): {str(exc)[:120]}")
        return []
    finally:
        try:
            if os.path.exists(json_out):
                os.remove(json_out)
        except Exception:
            pass


def pip_install(packages: list[str]):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"] + packages,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def ensure_packages(requirements: dict[str, str]):
    missing = []
    for import_name, pip_name in requirements.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        emit("install", f"Installation de {', '.join(missing)}...")
        pip_install(missing)


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


# ── Formules chimiques courantes ──
# Map nom symbolique -> prononciation en clair, en francais/anglais.
_CHEM_FR = {
    "H2O": "l'eau",
    "CO2": "dioxyde de carbone",
    "CO": "monoxyde de carbone",
    "NH3": "ammoniac",
    "CH4": "methane",
    "C2H6": "ethane",
    "C6H12O6": "glucose",
    "C2H5OH": "ethanol",
    "HCl": "acide chlorhydrique",
    "H2SO4": "acide sulfurique",
    "HNO3": "acide nitrique",
    "NaOH": "soude",
    "NaCl": "chlorure de sodium",
    "KCl": "chlorure de potassium",
    "CaCO3": "carbonate de calcium",
    "O2": "dioxygene",
    "O3": "ozone",
    "N2": "diazote",
    "H2": "dihydrogene",
    "Cl2": "dichlore",
    "F2": "difluor",
    "Br2": "dibrome",
    "I2": "diiode",
    "ATP": "A T P",
    "ADP": "A D P",
    "NADH": "N A D H",
    "FADH2": "F A D H 2",
    "DNA": "A D N",
    "ADN": "A D N",
    "ARN": "A R N",
    "RNA": "A R N",
    "pH": "pe ache",
}

# Map symboles uniquement (mode "spell out") pour Cl, Na, etc.
_CHEM_ELEMENT_SPELLED = {
    "Cl": "chlore",
    "Na": "sodium",
    "Mg": "magnesium",
    "Al": "aluminium",
    "Si": "silicium",
    "Ph": "phosphore",
    "Ca": "calcium",
    "Fe": "fer",
    "Cu": "cuivre",
    "Zn": "zinc",
    "Ag": "argent",
    "Au": "or",
    "Hg": "mercure",
    "Pb": "plomb",
    "Sn": "etain",
    "Br": "brome",
    "Li": "lithium",
    "Be": "beryllium",
    "Ni": "nickel",
    "Mn": "manganese",
    "Co": "cobalt",
    "Cr": "chrome",
    "Ti": "titane",
    "Pt": "platine",
    "He": "helium",
    "Ne": "neon",
    "Ar": "argon",
    "Kr": "krypton",
    "Xe": "xenon",
}

# Exposants / indices unicode -> chiffres lus
_SUB_SUP_MAP = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}

# Symboles math / fleches / operateurs -> lecture explicite
_MATH_SYMBOLS_FR = {
    "→": " donne ",
    "←": " provient de ",
    "↔": " est en equilibre avec ",
    "⇌": " est en equilibre avec ",
    "⇒": " implique ",
    "⇔": " equivaut a ",
    "≈": " est approximativement egal a ",
    "≠": " different de ",
    "≤": " inferieur ou egal a ",
    "≥": " superieur ou egal a ",
    "±": " plus ou moins ",
    "×": " fois ",
    "÷": " divise par ",
    "∞": " infini ",
    "π": " pi ",
    "Δ": " delta ",
    "δ": " delta ",
    "µ": " micro ",
    "Σ": " somme ",
    "∫": " integrale de ",
    "∑": " somme de ",
    "∂": " partielle ",
    "√": " racine carree de ",
    "°": " degres ",
    "%": " pour cent ",
    "&": " et ",
    "€": " euros ",
    "$": " dollars ",
    "£": " livres ",
}


def prepare_for_speech(text: str, lang: str = "fr") -> str:
    """
    Nettoie et transforme le texte pour une lecture TTS naturelle:
    - Retire Markdown (gras, italique, code, liens, puces, titres)
    - Remplace formules chimiques (H2O, Cl2, HCl, etc.) par leur nom
    - Remplace indices/exposants unicode par le chiffre
    - Lit les symboles math (→, ×, π, ≈, etc.) en toutes lettres
    - Normalise la ponctuation (evite les pauses excessives sur "." isole)
    """
    import re
    if not text:
        return ""

    # NB: on n'injecte PAS de tags emotionnels type [excited]/[laughter]. Les moteurs
    # reellement utilises (Kokoro / Piper / edge-tts) ne les interpretent pas — ils les
    # liraient a voix haute. (La prosodie est geree cote TS via voiceProsody.)

    # 1. Retirer Markdown avant toute chose
    text = re.sub(r"```[\s\S]*?```", " ", text)              # blocs code
    text = re.sub(r"`([^`]+)`", r"\1", text)                  # inline code
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)    # [label](url)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+[\.\)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Tableaux Markdown: retirer pipes pour eviter "pipe pipe" a la lecture
    text = re.sub(r"\|", " ", text)

    # 2. Remplacer indices / exposants unicode
    for uni, digit in _SUB_SUP_MAP.items():
        text = text.replace(uni, digit)

    # 3. Remplacer symboles math / fleches
    for sym, spoken in _MATH_SYMBOLS_FR.items():
        text = text.replace(sym, spoken)

    # 4. Formules chimiques complètes — matcher en premier les plus longues
    def _replace_chem(match: "re.Match[str]") -> str:
        token = match.group(0)
        if token in _CHEM_FR:
            return f" {_CHEM_FR[token]} "
        return token

    # Ordre: molecules multi-atomes les plus longues d'abord
    chem_keys = sorted(_CHEM_FR.keys(), key=len, reverse=True)
    pattern = r"\b(" + "|".join(re.escape(k) for k in chem_keys) + r")\b"
    text = re.sub(pattern, _replace_chem, text)

    # 5. Formules generiques type X2, Fe3+ (symbole + chiffre) apres substitutions complètes
    # Ex: "Cl2" -> "chlore 2". Chiffre ou indice traite plus haut.
    def _replace_element_plus_digit(match: "re.Match[str]") -> str:
        sym = match.group(1)
        digit = match.group(2)
        name = _CHEM_ELEMENT_SPELLED.get(sym)
        if not name:
            return match.group(0)
        return f" {name} {digit} "

    text = re.sub(
        r"\b([A-Z][a-z]?)(\d+)\b",
        _replace_element_plus_digit,
        text,
    )

    # 6. Elements isoles (sans chiffre) en contexte chimique: ne les remplacer que si non-mot francais
    # Pour eviter de casser "Si" (conjonction) -> on ne remplace pas les mots de 2 lettres communs
    # Mais on remplace les elements explicites quand la capitalisation est respectée et entoures de contexte chimique
    # Approche: entre parentheses chimiques ou apres "+", "-", "→"
    def _replace_isolated_element(match: "re.Match[str]") -> str:
        sym = match.group(1)
        name = _CHEM_ELEMENT_SPELLED.get(sym)
        return f" {name} " if name else sym

    # apres signe + ou - ou dans "X + Y -> Z"
    text = re.sub(
        r"(?<=[\+\-]\s)([A-Z][a-z]?)\b",
        _replace_isolated_element,
        text,
    )

    # 7. Exposants en notation x^2, x^n -> "x puissance 2"
    text = re.sub(r"(\w+)\s*\^\s*2\b", r"\1 au carre", text)
    text = re.sub(r"(\w+)\s*\^\s*3\b", r"\1 au cube", text)
    text = re.sub(r"(\w+)\s*\^\s*(-?\d+)", r"\1 puissance \2", text)

    # 8. Liaisons chimiques -, =, ≡ au milieu de formule -> "liaison simple/double/triple"
    text = re.sub(r"([A-Za-z\d])\s*≡\s*([A-Za-z\d])", r"\1 triple liaison \2", text)
    text = re.sub(r"([A-Za-z\d])\s*=\s*([A-Za-z\d])", r"\1 double liaison \2", text)
    # Ne pas toucher aux tirets entre mots francais

    # 9. Normaliser ponctuation et eviter les points excessifs
    text = re.sub(r"\.{3,}", "...", text)
    text = re.sub(r"[ \t]+([\.!?,;:])", r"\1", text)  # colle ponctuation
    text = re.sub(r"([\.!?])\1{2,}", r"\1", text)      # !!! -> !
    # Eviter double ponctuation type ".:" "?."
    text = re.sub(r"[\.:]{2,}", ".", text)
    # Un point immediatement suivi d'une virgule doit disparaître (artefact)
    text = re.sub(r"\.\s*,", ",", text)

    # 10. Lignes vides multiples + espaces surnumeraires
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 11. Retirer les emojis et symboles non-latins restants (excepte lettres accentuees)
    text = re.sub(r"[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF\n\.]+", " ", text)

    # 12. Re-normaliser espaces apres nettoyage
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    return text


def _strip_markdown(text: str) -> str:
    """Backwards-compatible wrapper: appelle prepare_for_speech."""
    return prepare_for_speech(text)


# ---------------------------------------------------------------------------
# STT — Voxtral (priorite) + faster-whisper (fallback)
# ---------------------------------------------------------------------------

def _try_voxtral(audio_path: str) -> dict | None:
    """Tente la transcription via Voxtral. Retourne None si echec."""
    pipe = None
    cache_dir = os.environ.get("HF_HUB_CACHE")
    try:
        import torch
        from transformers import pipeline as hf_pipeline

        emit("stt_load", "Chargement de Voxtral pour la transcription...")
        device = 0 if torch.cuda.is_available() else -1
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        pipe = hf_pipeline(
            "automatic-speech-recognition",
            model=VOXTRAL_MODEL,
            device=device,
            torch_dtype=dtype,
            model_kwargs={"attn_implementation": "eager"},
            cache_dir=cache_dir,
        )

        emit("stt_run", "Transcription Voxtral en cours...")
        result = pipe(audio_path, return_timestamps=False)
        text = result["text"].strip() if isinstance(result, dict) else str(result).strip()

        if not text:
            emit("stt_warn", "Voxtral n a retourne aucun texte, bascule sur Whisper...")
            return None

        return {
            "ok": True,
            "text": text,
            "language": "auto",
            "model_used": "voxtral",
        }
    except Exception as exc:
        emit("stt_warn", f"Voxtral indisponible ({type(exc).__name__}: {str(exc)[:120]}), bascule sur Whisper...")
        return None
    finally:
        try:
            del pipe
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()


def _is_hallucination(text: str) -> bool:
    """Detecte les hallucinations Whisper classiques."""
    import re
    t = text.strip().lower()
    if not t or len(t) < 2:
        return True
    # Texte repete (ex: "merci merci merci")
    words = t.split()
    if len(words) >= 3 and len(set(words)) == 1:
        return True
    # Patterns connus d'hallucination Whisper
    hallucination_patterns = [
        r"^(sous-titres|sous titres|subtitles|untertitel)",
        r"^(merci d.avoir regard|merci pour|thank you for watching)",
        r"^(music|musique|\[musique\]|\[music\])",
        r"^\.+$",  # Juste des points
        r"^\s*$",
        r"^(je vous remercie|thanks for)",
        r"^(s.il vous pla.t|please subscribe)",
        r"(amara\.org|subtitle|caption)",
    ]
    for pattern in hallucination_patterns:
        if re.search(pattern, t):
            return True
    # Texte trop court et sans voyelles (bruit)
    if len(t) < 4 and not re.search(r"[aeiouyAEIOUY]", t):
        return True
    return False


def _load_audio_numpy(audio_path: str):
    """
    Charge un fichier audio en numpy float32 mono 16kHz via soundfile + scipy.
    Retourne (numpy_array, sample_rate) ou None si non supporté.
    Évite la dépendance ffmpeg pour les fichiers WAV/FLAC/OGG.
    """
    try:
        import numpy as np
        import soundfile as sf
        import math

        data, sr = sf.read(audio_path, dtype="float32", always_2d=False)

        # Mono downmix
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Resample vers 16 kHz si nécessaire
        if sr != 16000:
            from scipy.signal import resample_poly
            gcd = math.gcd(int(sr), 16000)
            data = resample_poly(data, 16000 // gcd, int(sr) // gcd).astype(np.float32)

        emit("stt_load", f"Audio charge via soundfile ({len(data)} samples @ 16kHz, depuis {sr}Hz)")
        return data
    except Exception as exc:
        emit("stt_warn", f"soundfile non supporte ({type(exc).__name__}: {str(exc)[:80]}), utilise chemin direct (ffmpeg requis)...")
        return None


def _transcribe_whisper(audio_path: str) -> dict:
    """Transcription via faster-whisper avec anti-hallucination."""
    from faster_whisper import WhisperModel

    device = "cuda" if _cuda_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    model = None

    try:
        # Candidats STT par ordre de preference. Le modele francais dedie d'abord
        # (meilleur WER FR) puis repli generaliste, puis "small". Chaque echec de
        # chargement passe silencieusement au suivant → jamais de STT casse.
        candidates: list[tuple[str, int]] = []
        if WHISPER_FR_ENABLED:
            candidates.append((WHISPER_FR_MODEL, 4))
        candidates.append((WHISPER_FALLBACK, 4))
        candidates.append((WHISPER_FALLBACK_SECONDARY, 2))

        last_exc = None
        for model_name, workers in candidates:
            try:
                emit("stt_load", f"Chargement de Whisper {model_name} ({device})...")
                model = WhisperModel(
                    model_name,
                    device=device,
                    compute_type=compute_type,
                    num_workers=workers,
                    download_root=os.environ.get("HF_HOME"),
                )
                break
            except Exception as load_exc:
                last_exc = load_exc
                emit("stt_warn", f"Modele {model_name} indisponible ({type(load_exc).__name__}), essai suivant...")
        if model is None:
            raise last_exc if last_exc else RuntimeError("Aucun modele Whisper chargeable")

        # Essaie de charger en numpy (pas de ffmpeg requis pour WAV/FLAC)
        audio_input = _load_audio_numpy(audio_path)
        if audio_input is None:
            audio_input = audio_path  # fallback: chemin direct (nécessite ffmpeg)

        emit("stt_run", "Transcription Whisper en cours...")
        segments, info = model.transcribe(
            audio_input,
            beam_size=5,
            language="fr",
            # --- Anti-hallucination ---
            no_speech_threshold=0.5,
            log_prob_threshold=-0.8,
            condition_on_previous_text=False,
            suppress_blank=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,
                speech_pad_ms=200,
                threshold=0.4,
            ),
        )

        # Collecter les segments avec filtre de confiance
        good_segments = []
        for segment in segments:
            # Ignorer les segments a faible probabilite
            if segment.no_speech_prob > 0.6:
                continue
            if segment.avg_logprob < -1.0:
                continue
            text = segment.text.strip()
            if text and not _is_hallucination(text):
                good_segments.append(text)

        text = " ".join(good_segments).strip()

        if not text or _is_hallucination(text):
            return {
                "ok": True,
                "text": "(silence detecte)",
                "language": "fr",
                "model_used": "whisper",
            }

        return {
            "ok": True,
            "text": text,
            "language": getattr(info, "language", "fr"),
            "model_used": "whisper",
        }
    finally:
        try:
            del model
            if device == "cuda":
                import torch
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()


def _convert_to_wav(audio_path: str) -> str:
    """Convertit tout format audio en WAV via ffmpeg si necessaire."""
    if audio_path.lower().endswith(".wav"):
        return audio_path

    wav_path = os.path.splitext(audio_path)[0] + "_converted.wav"
    try:
        # Essaie ffmpeg (installe avec imageio[ffmpeg] ou systeme)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
            emit("stt_convert", f"Audio converti en WAV ({os.path.getsize(wav_path)} octets)")
            return wav_path
    except FileNotFoundError:
        emit("stt_warn", "ffmpeg absent, tentative de lecture directe du format source...")
    except Exception as exc:
        emit("stt_warn", f"Conversion ffmpeg echouee ({type(exc).__name__}), tentative directe...")

    # Si ffmpeg echoue, essaie avec soundfile
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(audio_path)
        # Resample to 16kHz mono if needed
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        sf.write(wav_path, data, sr)
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
            emit("stt_convert", f"Audio converti via soundfile ({os.path.getsize(wav_path)} octets)")
            return wav_path
    except Exception:
        pass

    # En dernier recours, utiliser le fichier original tel quel
    return audio_path


def run_stt(audio_path: str) -> dict:
    configure_ml_cache_environment()
    if not os.path.exists(audio_path):
        return {"ok": False, "error": f"Fichier audio introuvable: {audio_path}"}

    file_size = os.path.getsize(audio_path)
    if file_size < 100:
        return {"ok": False, "error": f"Fichier audio trop petit ({file_size} octets), enregistrement vide ou corrompu."}

    # Convertir en WAV si le format source n'est pas WAV (ex: WebM du navigateur)
    converted_path = _convert_to_wav(audio_path)

    # Installer les deps de base
    ensure_packages(REQUIRED_STT)

    # Tenter Voxtral si transformers disponible
    #try:
    #    ensure_packages(REQUIRED_VOXTRAL)
    #    result = _try_voxtral(converted_path)
    #    if result is not None:
    #        return result
    #except Exception as exc:
    #    emit("stt_warn", f"Installation Voxtral echouee ({type(exc).__name__}), bascule sur Whisper...")

    # Fallback faster-whisper
    try:
        return _transcribe_whisper(converted_path)
    except Exception as exc:
        return {"ok": False, "error": f"Tous les moteurs STT ont echoue. Dernier: {type(exc).__name__}: {str(exc)[:200]}"}


# ---------------------------------------------------------------------------
# TTS — Kokoro
# ---------------------------------------------------------------------------

def _run_tts_edge(clean_text: str, output_path: str, lang: str, persona: str | None = None) -> dict | None:
    """
    Tente edge-tts (voix Microsoft Neural studio-grade). Necessite connexion internet.
    Retourne None si echec pour laisser le fallback prendre.

    Si `persona` (lyra-soft, iris-bright, ...) est fourni et connu dans
    EDGE_TTS_VOICE_PERSONAS, on utilise la voix mappee pour donner une identite
    sonore distincte par agent Aurora.
    """
    try:
        ensure_packages(REQUIRED_EDGE_TTS)
    except Exception as err:
        emit("tts_warn", f"edge-tts indisponible: {err}")
        return None

    try:
        import asyncio
        import edge_tts  # type: ignore
    except Exception:
        return None

    persona_map = EDGE_TTS_VOICE_PERSONAS.get(persona or "", {}) if persona else {}
    voice_name = persona_map.get(lang) or EDGE_TTS_VOICES.get(lang, EDGE_TTS_VOICES["fr"])
    # Debit + pitch naturels: rate=-5% pour diction claire, pitch legerement plus grave
    rate = "-5%"
    pitch = "+0Hz"

    async def _synthesize() -> bool:
        # Generer du MP3 via edge-tts puis convertir en WAV pour Rhubarb + uniformite
        tmp_mp3 = output_path + ".edgetts.mp3"
        communicate = edge_tts.Communicate(
            clean_text,
            voice_name,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(tmp_mp3)
        if not os.path.exists(tmp_mp3) or os.path.getsize(tmp_mp3) < 200:
            return False

        # Convertir MP3 -> WAV 24 kHz mono avec ffmpeg (requis par Rhubarb et uniformite)
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            emit("tts_warn", "ffmpeg absent, impossible de convertir MP3 edge-tts en WAV.")
            try:
                os.unlink(tmp_mp3)
            except Exception:
                pass
            return False

        import subprocess as _sp
        proc = _sp.run(
            [ffmpeg, "-y", "-i", tmp_mp3, "-ar", "24000", "-ac", "1", output_path],
            capture_output=True,
            timeout=60,
        )
        try:
            os.unlink(tmp_mp3)
        except Exception:
            pass
        return proc.returncode == 0 and os.path.exists(output_path)

    try:
        emit("tts_load", f"Edge-TTS ({voice_name})...")
        ok = asyncio.run(_synthesize())
        if not ok:
            return None
        phonemes = _run_rhubarb(output_path)
        return {
            "ok": True,
            "audioPath": output_path,
            "engine": "edge-tts",
            "voice": voice_name,
            "phonemes": phonemes,
        }
    except Exception as err:
        emit("tts_warn", f"Edge-TTS a echoue ({err}), fallback sur Piper.")
        return None


def _find_ffmpeg() -> str | None:
    """Localise ffmpeg dans le PATH ou dans le workspace."""
    import shutil
    which = shutil.which("ffmpeg")
    if which:
        return which
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace = os.path.dirname(script_dir)
    for candidate in [
        os.path.join(workspace, "bin", "ffmpeg.exe"),
        os.path.join(workspace, "bin", "ffmpeg"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _download_piper_voice(voice_name: str) -> tuple[str, str] | None:
    """Download ONNX model + config json if missing. Returns (onnx_path, json_path) or None."""
    try:
        os.makedirs(PIPER_CACHE_DIR, exist_ok=True)
        onnx_path = os.path.join(PIPER_CACHE_DIR, f"{voice_name}.onnx")
        json_path = os.path.join(PIPER_CACHE_DIR, f"{voice_name}.onnx.json")
        if os.path.exists(onnx_path) and os.path.exists(json_path):
            return (onnx_path, json_path)

        # Parse voice_name: "fr_FR-siwis-medium" -> lang_locale=fr_FR, speaker=siwis, quality=medium
        parts = voice_name.split("-")
        if len(parts) < 3:
            return None
        lang_locale = parts[0]
        lang = lang_locale.split("_")[0]
        speaker = parts[1]
        quality = parts[2]
        base_url = (
            f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            f"{lang}/{lang_locale}/{speaker}/{quality}/{voice_name}"
        )

        import urllib.request
        if not os.path.exists(onnx_path):
            emit("tts_download", f"Telechargement voix Piper {voice_name} (une seule fois)...")
            urllib.request.urlretrieve(f"{base_url}.onnx", onnx_path)
        if not os.path.exists(json_path):
            urllib.request.urlretrieve(f"{base_url}.onnx.json", json_path)
        return (onnx_path, json_path)
    except Exception as err:
        emit("tts_warn", f"Impossible de telecharger la voix Piper: {err}")
        return None


def _run_tts_piper(clean_text: str, output_path: str, lang: str) -> dict | None:
    """Try Piper TTS first (more natural than Kokoro). Returns dict or None if unavailable."""
    try:
        ensure_packages(REQUIRED_PIPER)
    except Exception as err:
        emit("tts_warn", f"Piper indisponible, fallback sur Kokoro: {err}")
        return None

    try:
        from piper import PiperVoice
    except Exception:
        return None

    voice_name = PIPER_VOICES.get(lang, PIPER_VOICES["fr"])
    paths = _download_piper_voice(voice_name)
    if not paths:
        return None
    onnx_path, _ = paths

    try:
        emit("tts_load", f"Chargement Piper {voice_name}...")
        voice = PiperVoice.load(onnx_path)
        emit("tts_run", "Synthese Piper en cours...")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        import wave
        with wave.open(output_path, "wb") as wav_file:
            voice.synthesize(clean_text, wav_file)

        if not os.path.exists(output_path):
            return {"ok": False, "error": "Piper n a pas produit de fichier audio."}

        phonemes = _run_rhubarb(output_path)
        return {
            "ok": True,
            "audioPath": output_path,
            "engine": "piper",
            "voice": voice_name,
            "phonemes": phonemes,
        }
    except Exception as err:
        emit("tts_warn", f"Piper a echoue ({err}), fallback sur Kokoro.")
        return None


def maybe_generate_talking_video(audio_path: str, avatar_image: str, lang: str = "fr") -> dict | None:
    """Si un avatar image est fourni ET SadTalker installe, genere le MP4 talking video.
    Retourne {video_url, cache_hit} ou None si pas applicable / pas installe.
    Erreur silencieuse -> fallback Live 2D cote frontend."""
    if not avatar_image or not os.path.isfile(avatar_image):
        return None
    try:
        talking_head_script = os.path.join(os.path.dirname(__file__), "talking_head.py")
        if not os.path.isfile(talking_head_script):
            return None
        # Sortie dans temp/ avec un nom unique base sur l audio
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        video_out = os.path.join(WORKSPACE, "temp", f"{audio_name}_talking.mp4")
        # Appel synchrone rapide avec size=256 (latence raisonnable)
        emit("talking_video", "Generation video realiste (SadTalker)...")
        proc = subprocess.run(
            [sys.executable, talking_head_script,
             "--mode", "generate",
             "--image", avatar_image,
             "--audio", audio_path,
             "--output", video_out,
             "--size", "256",
             "--no-enhancer",  # skip gfpgan pour la latence (enhancer = +5-10s)
            ],
            capture_output=True, text=True, timeout=90,
        )
        if proc.returncode != 0:
            emit("talking_video_skip", f"SadTalker fail (non bloquant): {proc.stderr[:200] if proc.stderr else 'unknown'}")
            return None
        # Parse le JSON final
        lines = [l for l in proc.stdout.split("\n") if l.strip().startswith("{")]
        if not lines:
            return None
        result = json.loads(lines[-1])
        if result.get("ok") and result.get("video_path"):
            return {
                "video_url": result["video_path"],
                "cached": result.get("cached", False),
            }
        return None
    except subprocess.TimeoutExpired:
        emit("talking_video_skip", "SadTalker timeout (non bloquant, fallback 2D)")
        return None
    except Exception as e:
        emit("talking_video_skip", f"SadTalker error: {e}")
        return None


def run_tts(text: str, output_path: str, lang: str = "fr", persona: str | None = None) -> dict:
    configure_ml_cache_environment()
    if not text.strip():
        return {"ok": False, "error": "Texte vide."}

    clean_text = prepare_for_speech(text, lang)
    if not clean_text:
        return {"ok": False, "error": "Texte vide apres preparation vocale."}

    # ─── 1. Piper (offline, voix naturelle) — LOCAL-FIRST ───
    # App locale / RGPD : on privilegie systematiquement les moteurs offline.
    piper_result = _run_tts_piper(clean_text, output_path, lang)
    if piper_result is not None:
        return piper_result

    # ─── 2. edge-tts (voix Microsoft Neural, CLOUD Azure) — OPT-IN uniquement ───
    # On n'envoie JAMAIS le texte utilisateur a un service cloud par defaut.
    # A activer explicitement via AURORA_ALLOW_CLOUD_TTS=1.
    if os.environ.get("AURORA_ALLOW_CLOUD_TTS") == "1":
        edge_result = _run_tts_edge(clean_text, output_path, lang, persona=persona)
        if edge_result is not None:
            return edge_result

    # ─── 3. Kokoro (offline, leger) — fallback terminal ───
    ensure_packages(REQUIRED_TTS)

    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    voice = KOKORO_VOICES.get(lang, KOKORO_VOICES["fr"])
    lang_code = KOKORO_LANG_CODES.get(lang, KOKORO_LANG_CODES["fr"])

    emit("tts_load", f"Chargement de Kokoro ({lang_code}, voix {voice})...")

    pipe = None
    try:
        try:
            pipe = KPipeline(lang_code=lang_code)
        except Exception:
            emit("tts_warn", f"Langue {lang!r} non supportee par Kokoro, bascule sur anglais.")
            pipe = KPipeline(lang_code="a")
            voice = KOKORO_VOICES["en"]

        emit("tts_run", "Synthese vocale en cours...")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        all_chunks = []
        sample_rate = 24000
        # Silence court entre phrases (80ms) pour eviter les coupures
        inter_chunk_silence = np.zeros(int(sample_rate * 0.08), dtype=np.float32)

        # kokoro >= 0.9.4 yields (graphemes, phonemes, audio) -- audio est toujours en derniere position
        # speed=0.9 pour une diction plus claire (formules, noms propres)
        for *_, audio_chunk in pipe(clean_text, voice=voice, speed=0.9):
            if audio_chunk is not None and hasattr(audio_chunk, '__len__') and len(audio_chunk) > 0:
                audio_arr = np.asarray(audio_chunk, dtype=np.float32)
                if all_chunks:
                    # Crossfade de 10ms entre chunks pour transition douce
                    fade_len = min(int(sample_rate * 0.01), len(audio_arr), len(all_chunks[-1]))
                    if fade_len > 0:
                        fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
                        fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
                        all_chunks[-1][-fade_len:] *= fade_out
                        audio_arr[:fade_len] *= fade_in
                    all_chunks.append(inter_chunk_silence.copy())
                all_chunks.append(audio_arr)

        if not all_chunks:
            return {"ok": False, "error": "Kokoro n a produit aucun audio."}

        full_audio = np.concatenate(all_chunks)
        # Ajouter 200ms de silence en debut et fin pour eviter les clics
        pad = np.zeros(int(sample_rate * 0.2), dtype=np.float32)
        full_audio = np.concatenate([pad, full_audio, pad])
        sf.write(output_path, full_audio, sample_rate)

        if not os.path.exists(output_path):
            return {"ok": False, "error": "Le fichier audio n a pas ete cree."}

        # Analyse phonémique Rhubarb (optionnel — retourne [] si absent)
        phonemes = _run_rhubarb(output_path)

        emit("tts_done", f"Audio genere: {output_path}")
        return {"ok": True, "path": output_path, "lang": lang, "voice": voice, "phonemes": phonemes}
    finally:
        del pipe
        gc.collect()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Aurora voice service (STT + TTS)")
    parser.add_argument("--mode", required=True, choices=["stt", "tts"])
    parser.add_argument("--audio", help="Chemin vers le fichier audio a transcrire (mode stt)")
    parser.add_argument("--text", help="Texte a synthetiser (mode tts)")
    parser.add_argument("--output", help="Chemin de sortie WAV (mode tts)")
    parser.add_argument("--lang", default="fr", help="Langue (fr ou en)")
    parser.add_argument("--avatar", help="Chemin vers l image avatar (mode tts). Si fourni + SadTalker installe, genere un MP4 talking-video synchronise.")
    parser.add_argument("--voice", help="Persona vocal (lyra-soft, iris-bright, cinema-deep, glyph-precise, sumi-warm, atlas-strong, sage-mellow, phantom-sharp). Si fourni, edge-TTS choisit une voix Microsoft Neural distincte par agent Aurora.", default=None)
    args = parser.parse_args()

    configure_ml_cache_environment()
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    try:
        if args.mode == "stt":
            if not args.audio:
                print(json.dumps({"ok": False, "error": "--audio requis en mode stt"}))
                sys.exit(1)
            result = run_stt(args.audio)
        else:
            if not args.text or not args.output:
                print(json.dumps({"ok": False, "error": "--text et --output requis en mode tts"}))
                sys.exit(1)
            result = run_tts(args.text, args.output, args.lang, persona=args.voice)

            # Post-process optionnel: generation video talking-head si avatar fourni
            if result.get("ok") and args.avatar:
                audio_path = result.get("audioPath") or result.get("path") or args.output
                talking = maybe_generate_talking_video(audio_path, args.avatar, args.lang)
                if talking:
                    result["talking_video"] = talking["video_url"]
                    result["talking_video_cached"] = talking["cached"]

        print(json.dumps(result))
        if not result.get("ok"):
            sys.exit(1)

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[-600:]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
