"""
voice_clone.py -- Voice cloning + bibliotheque globale de voix.

Routage par langue:
  1. Fun-CosyVoice3 0.5B (FR officiel, multilingue, clone zero-shot)
  2. XTTS-v2 / F5-TTS uniquement comme replis explicites

Bibliotheque:
  application/voices/library/{character_slug}/
    reference.wav   <- echantillon de la voix (15-30s, mono 16kHz)
    embedding.npy   <- embedding ECAPA pour fingerprint
    metadata.json   <- {character, source, lang, transcript, extracted_at, quality_score}

Usage:
  python voice_clone.py --check
  python voice_clone.py --list
  python voice_clone.py --register --character "natsu" --reference natsu_sample.wav --lang fr
  python voice_clone.py --synthesize --character "natsu" --text "Salut, je suis Natsu" --lang fr --output out.wav
  python voice_clone.py --synthesize-fresh --voice-preset "young_male_french" --text "..." --output out.wav

Output JSON sur stdout (derniere ligne):
  {"ok": true, "wav": "out.wav", "duration_s": 3.2, "engine": "cosyvoice3|xtts-v2|f5-tts"}
"""

import argparse
import gc
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Compat shims must run BEFORE any torchaudio / speechbrain / TTS import.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _compat  # noqa: F401

WORKSPACE = Path(__file__).resolve().parents[2]
LIBRARY_DIR = WORKSPACE / "voices" / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
# Depot d'echantillons : tout fichier depose ici est enrole automatiquement au
# premier dialogue du personnage correspondant. C'est le SEUL chemin par lequel
# une vraie voix peut entrer dans le systeme — sans echantillon, aucun moteur au
# monde ne « reproduit » une voix, il en invente une.
DROPBOX_DIR = WORKSPACE / "voices" / "echantillons"
CACHE_DIR = WORKSPACE / "temp" / "voice_clone"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COSYVOICE3_ADAPTER = Path(__file__).resolve().parent / "cosyvoice3_adapter.py"

# ffmpeg lit la piste audio de n'importe lequel de ces conteneurs : l'utilisateur
# peut deposer un extrait video sans le convertir au prealable.
SAMPLE_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma",
               ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts"}


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def slugify(name: str) -> str:
    """Convert 'Natsu Fairy Tail VF' -> 'natsu_fairy_tail_vf'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unnamed"


def detect_language(text: str) -> str:
    """Heuristique FR vs EN, avec le FRANCAIS par defaut.

    L'ancienne version renvoyait "en" des que le francais ne l'emportait pas
    STRICTEMENT, et comptait " a " comme marqueur anglais alors qu'il est
    omnipresent en francais ("il a", "y a", "a la"). Resultat mesure : 4 phrases
    francaises sur 6 routees vers l'anglais, dont "Merci beaucoup" et
    "Bonjour, comment vas-tu ?". Toute replique courte basculait donc sur un
    moteur anglais, avec l'accent qui va avec.

    Regles :
      - les caracteres accentues (e, a, c cedille...) sont un signal FORT de
        francais : un texte anglais n'en contient pratiquement jamais ;
      - comparaison par mots entiers, pas par sous-chaines espacees ;
      - ambiguite ou texte trop court -> FRANCAIS (langue du projet). Basculer
        en anglais doit demander une preuve, pas l'absence de preuve.
    """
    t = (text or "").lower().strip()
    if not t:
        return "fr"

    # Signal fort : accents francais.
    if re.search(r"[àâäéèêëîïôöùûüÿçœæ]", t):
        return "fr"

    words = re.findall(r"[a-z']+", t)
    if not words:
        return "fr"
    ws = set(words)

    fr_words = {
        "le", "la", "les", "un", "une", "des", "du", "de", "est", "et", "que",
        "qui", "avec", "pour", "ce", "cette", "ces", "je", "tu", "il", "elle",
        "nous", "vous", "ils", "elles", "ne", "pas", "plus", "sur", "dans",
        "mais", "tout", "tous", "bien", "merci", "bonjour", "salut", "oui",
        "non", "moi", "toi", "son", "sa", "ses", "mon", "ma", "mes", "ton",
        "ta", "tes", "au", "aux", "en", "y", "on", "se", "sont", "etre",
        "avoir", "fait", "faire", "dit", "comme", "quand", "alors", "ici",
        "rien", "peut", "veux", "veut", "jamais", "toujours", "tres",
    }
    # " a " retire volontairement : c'est le piege d'origine.
    en_words = {
        "the", "an", "is", "are", "was", "were", "and", "that", "with", "for",
        "this", "these", "those", "it", "its", "you", "your", "we", "our",
        "they", "their", "he", "she", "his", "her", "have", "has", "had",
        "will", "would", "can", "could", "should", "there", "here", "what",
        "when", "which", "because", "about", "from", "into", "hello", "thanks",
        "thank", "yes", "please", "sorry", "very", "never", "always",
    }
    fr = len(ws & fr_words)
    en = len(ws & en_words)

    # L'anglais doit gagner NETTEMENT pour l'emporter : sur un texte court, un
    # seul mot commun ne doit pas faire basculer toute une replique.
    if en >= 2 and en > fr:
        return "en"
    return "fr"


def _last_json_line(raw: str) -> dict | None:
    for line in reversed((raw or "").splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _cosyvoice3_python() -> Path:
    configured = os.environ.get("AURORA_COSYVOICE3_PYTHON", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local/share/auroraia/venvs/cosyvoice3/bin/python"


def _is_isolated_python(python_path: Path) -> bool:
    """Compare les racines de venv, pas les cibles de leurs liens python."""
    candidate_prefix = os.path.normcase(os.path.abspath(str(python_path.parent.parent)))
    current_prefix = os.path.normcase(os.path.abspath(sys.prefix))
    return candidate_prefix != current_prefix


def cosyvoice3_status() -> dict:
    """Check the isolated CosyVoice3 runtime without installing anything."""
    python_path = _cosyvoice3_python()
    base = {
        "ok": False,
        "engine": "cosyvoice3",
        "python": str(python_path),
        "adapter": str(COSYVOICE3_ADAPTER),
        "isolated": _is_isolated_python(python_path),
    }
    if not COSYVOICE3_ADAPTER.is_file():
        return {**base, "error": "adaptateur CosyVoice3 absent"}
    if not python_path.is_file():
        return {
            **base,
            "error": (
                "venv CosyVoice3 isole absent; definir AURORA_COSYVOICE3_PYTHON "
                "apres installation dans ~/.local/share/auroraia/venvs/cosyvoice3"
            ),
        }
    if not base["isolated"]:
        return {
            **base,
            "error": (
                "AURORA_COSYVOICE3_PYTHON pointe sur le venv partage AuroraIA; "
                "un venv CosyVoice3 distinct est obligatoire"
            ),
        }
    try:
        proc = subprocess.run(
            [str(python_path), str(COSYVOICE3_ADAPTER), "--check"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        parsed = _last_json_line(proc.stdout)
        if parsed is None:
            return {
                **base,
                "error": (proc.stderr or proc.stdout or "check CosyVoice3 sans JSON")[:400],
            }
        return {**base, **parsed, "ok": proc.returncode == 0 and bool(parsed.get("ok"))}
    except Exception as exc:
        return {**base, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def check_dependencies() -> dict:
    """Verify TTS engines honestly; all heavy engines may live outside this venv."""
    cosy = cosyvoice3_status()
    info = {
        "cosyvoice3": bool(cosy.get("ok")),
        "cosyvoice3_status": cosy,
        "f5_tts": False,
        "xtts_v2": False,
        "torch_cuda": False,
    }
    try:
        import torch
        info["torch_cuda"] = torch.cuda.is_available()
    except Exception:
        pass

    try:
        import f5_tts.api  # noqa
        info["f5_tts"] = True
    except Exception as exc:
        info["f5_tts_error"] = str(exc)[:120]

    try:
        from TTS.api import TTS  # noqa
        info["xtts_v2"] = True
    except Exception as exc:
        info["xtts_v2_error"] = str(exc)[:120]

    info["ok"] = info["cosyvoice3"] or info["f5_tts"] or info["xtts_v2"]
    info["preferred_engine"] = (
        "cosyvoice3" if info["cosyvoice3"]
        else "xtts-v2" if info["xtts_v2"]
        else "f5-tts" if info["f5_tts"]
        else None
    )
    return info


def list_library() -> dict:
    """Return all registered voices."""
    voices = []
    if LIBRARY_DIR.exists():
        for item in LIBRARY_DIR.iterdir():
            if not item.is_dir():
                continue
            meta_path = item / "metadata.json"
            ref = item / "reference.wav"
            if not ref.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            except Exception:
                meta = {}
            voices.append({
                "slug": item.name,
                "character": meta.get("character", item.name),
                "lang": meta.get("lang", "fr"),
                "source": meta.get("source"),
                "duration_s": meta.get("duration_s"),
                "quality_score": meta.get("quality_score"),
                "reference_quality_score": meta.get("reference_quality_score"),
                "reference_audio": meta.get("reference_audio"),
                "extracted_at": meta.get("extracted_at"),
                "has_transcript": bool((meta.get("transcript") or "").strip()),
            })
    return {"ok": True, "voices": voices, "count": len(voices)}


# v82ll : auto-bootstrap default voice library entries (default_fr, default_en).
# Sans ça, synthesize_voice tombe direct au Kokoro generic (voix robotique).
# Avec : le 1er fallback est déjà cloning XTTS/F5 sur une voix neutre saine.

DEFAULT_BOOTSTRAP_TEXT = {
    "fr": "Bonjour, je suis Aurora, votre copilote local. Cette voix est utilisée par défaut quand aucun personnage n'est spécifié.",
    "en": "Hello, I am Aurora, your local copilot. This voice is used by default when no specific character is selected.",
}


def ensure_default_voice(lang: str = "fr") -> dict:
    """Ensure a default_<lang> entry exists in the library. If missing,
    bootstrap it by generating a 5-10s reference WAV via voice_service.py
    Kokoro TTS, then registering it as a regular voice slot.

    Idempotent : returns ok=True with action='exists' if already there.
    """
    lang = (lang or "fr")[:2]
    if lang not in DEFAULT_BOOTSTRAP_TEXT:
        return {"ok": False, "error": f"unsupported lang: {lang}"}

    slug = f"default_{lang}"
    voice_dir = LIBRARY_DIR / slug
    ref_path = voice_dir / "reference.wav"
    if ref_path.exists():
        return {"ok": True, "action": "exists", "slug": slug, "path": str(ref_path)}

    # Generate via voice_service.py Kokoro (no cloning, just TTS).
    voice_service = Path(__file__).resolve().parents[1] / "voice_service.py"
    if not voice_service.exists():
        return {"ok": False, "error": "voice_service.py absent (no Kokoro)"}

    voice_dir.mkdir(parents=True, exist_ok=True)
    tmp_wav = CACHE_DIR / f"bootstrap_{slug}.wav"
    text = DEFAULT_BOOTSTRAP_TEXT[lang]

    cmd = [
        sys.executable, str(voice_service),
        "--mode", "tts",
        "--text", text,
        "--lang", lang,
        "--output", str(tmp_wav),
    ]
    emit("voice_bootstrap", f"Kokoro {lang} -> {slug}")
    rc = subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode
    if rc != 0 or not tmp_wav.exists():
        return {"ok": False, "error": f"Kokoro bootstrap failed for {lang}"}

    # Now register it as a real voice library entry.
    return register_voice(
        character=f"Default {lang.upper()}",
        reference_wav=str(tmp_wav),
        lang=lang,
        source=f"bootstrap_kokoro_{int(time.time())}",
        quality_score=0.7,
        duration_s=0.0,
    )


def analyze_reference_audio(reference_wav: str) -> dict:
    """Mesure objective minimale avant d'accepter une référence de clonage."""
    try:
        import numpy as np
        import soundfile as sf

        audio, sample_rate = sf.read(reference_wav, always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = np.mean(audio, axis=1)
        audio = np.asarray(audio, dtype=np.float32)
        duration_s = len(audio) / float(sample_rate) if sample_rate else 0.0
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        clipping_ratio = float(np.mean(np.abs(audio) >= 0.995)) if audio.size else 0.0
        dc_offset = float(np.mean(audio)) if audio.size else 0.0

        frame_len = max(1, int(sample_rate * 0.02))
        usable = (len(audio) // frame_len) * frame_len
        if usable:
            frames = audio[:usable].reshape(-1, frame_len)
            frame_rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
            active_level = float(np.percentile(frame_rms, 90))
            noise_level = float(np.percentile(frame_rms, 10))
            silence_threshold = max(10 ** (-45.0 / 20.0), active_level * 0.08)
            silence_ratio = float(np.mean(frame_rms < silence_threshold))
            snr_db = float(20.0 * np.log10((active_level + 1e-8) / (noise_level + 1e-8)))
        else:
            silence_ratio = 1.0
            snr_db = 0.0

        failures = []
        warnings = []
        if duration_s < 2.5:
            failures.append("reference_too_short")
        elif duration_s < 5.0:
            warnings.append("reference_short")
        if duration_s > 45.0:
            warnings.append("reference_long")
        if peak < 0.01:
            failures.append("reference_nearly_silent")
        if silence_ratio > 0.80:
            failures.append("too_much_silence")
        elif silence_ratio > 0.35:
            warnings.append("silence_ratio_high")
        if clipping_ratio > 0.02:
            failures.append("severe_clipping")
        elif clipping_ratio > 0.001:
            warnings.append("clipping_detected")
        if snr_db < 10.0:
            warnings.append("low_estimated_snr")
        if abs(dc_offset) > 0.03:
            warnings.append("dc_offset")

        score = 1.0
        score -= min(0.35, silence_ratio * 0.45)
        score -= min(0.35, clipping_ratio * 10.0)
        score -= 0.20 if snr_db < 10 else 0.10 if snr_db < 18 else 0.0
        score -= 0.12 if duration_s < 5.0 else 0.0
        score -= 0.05 if duration_s > 45.0 else 0.0
        return {
            "ok": not failures,
            "sample_rate": int(sample_rate),
            "channels": 1,
            "duration_s": round(duration_s, 3),
            "peak": round(peak, 6),
            "clipping_ratio": round(clipping_ratio, 6),
            "silence_ratio": round(silence_ratio, 4),
            "estimated_snr_db": round(snr_db, 2),
            "dc_offset": round(dc_offset, 6),
            "quality_score": round(max(0.0, min(1.0, score)), 3),
            "failures": failures,
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "ok": False,
            "failures": ["audio_decode_failed"],
            "warnings": [],
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }


def _normalize_reference_audio(source: Path, destination: Path) -> dict:
    """Normalise le conteneur seulement : mono PCM 16 bits / 16 kHz, sans filtre de timbre."""
    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([
        ffmpeg,
        "-y",
        "-i", str(source),
        "-vn",
        "-map_metadata", "-1",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-loglevel", "error",
        str(destination),
    ], capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not destination.is_file():
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout or "normalisation ffmpeg échouée")[-400:],
        }
    quality = analyze_reference_audio(str(destination))
    return {"ok": bool(quality.get("ok")), "quality": quality}


def register_voice(character: str, reference_wav: str, lang: str = "fr",
                    source: str = "", quality_score: float = 0.0,
                    duration_s: float = 0.0, transcript: str = "") -> dict:
    """Add a voice to the global library. The reference WAV is copied in,
    and a fingerprint embedding is computed and stored.
    """
    src = Path(reference_wav)
    if not src.is_file():
        return {"ok": False, "error": f"reference not found: {reference_wav}"}

    slug = slugify(character)
    voice_dir = LIBRARY_DIR / slug
    normalized_tmp = CACHE_DIR / f"register_{slug}_{os.getpid()}_{time.time_ns()}.wav"
    normalized = _normalize_reference_audio(src, normalized_tmp)
    audio_quality = normalized.get("quality") or {}
    if not normalized.get("ok"):
        normalized_tmp.unlink(missing_ok=True)
        return {
            "ok": False,
            "error": "reference_audio_rejected",
            "audio_quality": audio_quality,
            "detail": normalized.get("error"),
        }

    voice_dir.mkdir(parents=True, exist_ok=True)
    target_ref = voice_dir / "reference.wav"
    os.replace(normalized_tmp, target_ref)
    duration_s = float(audio_quality.get("duration_s") or duration_s or 0.0)

    # Compute fingerprint embedding so future "Natsu" lookups can verify identity.
    embedding_path = voice_dir / "embedding.npy"
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from speechbrain.inference.speaker import EncoderClassifier

        cache = WORKSPACE / "temp" / "speechbrain_models" / "ecapa_voxceleb"
        cache.mkdir(parents=True, exist_ok=True)
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(cache),
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        )
        audio, sr = sf.read(str(target_ref))
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=16000)
        tensor = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
        with torch.no_grad():
            emb = classifier.encode_batch(tensor).squeeze().cpu().numpy()
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        np.save(str(embedding_path), emb)

        if duration_s <= 0:
            duration_s = len(audio) / 16000.0
    except Exception as exc:
        emit("embed_warn", f"fingerprint skipped: {str(exc)[:120]}")

    meta = {
        "character": character,
        "slug": slug,
        "lang": lang,
        "source": source,
        "extracted_at": int(time.time()),
        "quality_score": quality_score,
        "reference_quality_score": audio_quality.get("quality_score"),
        "reference_audio": audio_quality,
        "duration_s": duration_s,
        "transcript": transcript.strip(),
    }
    (voice_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "slug": slug,
        "path": str(target_ref),
        "audio_quality": audio_quality,
    }


_DECORATIONS = {"style", "voice", "voix", "clone", "sample", "echantillon",
                "ref", "reference", "extrait"}
_LANG_TOKENS = {"fr", "en", "es", "de", "it", "jp", "ja", "vf", "vo", "vost",
                "va", "french", "francais", "english"}


def _core_tokens(slug: str) -> list:
    """Retire les decorations pour comparer ce qui identifie vraiment la voix.

    « style_natsu_fr » et « natsu_dragneel_VF.mp3 » designent la meme personne ;
    seul le noyau « natsu » les relie.
    """
    toks = [t for t in slugify(slug).split("_") if t]
    while toks and toks[0] in _DECORATIONS:
        toks.pop(0)
    while toks and (toks[-1] in _LANG_TOKENS or toks[-1] in _DECORATIONS):
        toks.pop()
    return toks


def find_sample_file(character: str) -> Path | None:
    """Cherche dans le depot un fichier qui corresponde au personnage.

    Le fichier gagnant est le plus long : entre « natsu.mp3 » et
    « natsu_dragneel_scene_complete.mkv », le second porte plus de parole donc
    un meilleur clonage.
    """
    if not DROPBOX_DIR.is_dir():
        return None
    want = _core_tokens(character)
    if not want:
        return None
    best, best_size = None, -1
    for path in sorted(DROPBOX_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SAMPLE_EXTS:
            continue
        have = _core_tokens(path.stem)
        if not have:
            continue
        # Correspondance par prefixe de jetons, dans un sens ou dans l'autre.
        n = min(len(want), len(have))
        if have[:n] != want[:n]:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size > best_size:
            best, best_size = path, size
    return best


def enroll_from_dropbox(character: str, lang: str = "fr") -> dict:
    """Enrole automatiquement un echantillon depose, s'il en existe un.

    Appele avant toute synthese : c'est ce qui fait qu'un fichier depose dans
    voices/echantillons/ devient une vraie voix clonee sans aucune commande.
    """
    sample = find_sample_file(character)
    if sample is None:
        return {"ok": False, "error": "aucun echantillon depose",
                "dropbox": str(DROPBOX_DIR)}
    emit("voice_enroll", f"{sample.name} -> {slugify(character)}")
    res = register_voice(character, str(sample), lang=lang,
                         source=f"echantillon:{sample.name}")
    if res.get("ok"):
        res["enrolled_from"] = str(sample)
    return res


def is_real_voice(meta: dict) -> bool:
    """Vrai echantillon (donc reproduction) plutot que voix amorcee par TTS.

    Une voix amorcee via Kokoro est une voix de synthese recopiee : la cloner
    reproduit fidelement... un robot. Elle ne doit jamais compter comme une
    reference.
    """
    source = str((meta or {}).get("source") or "")
    return bool(source) and not source.startswith("bootstrap_")


def resolve_voice(character: str, lang: str = "fr") -> dict:
    """Etat de la voix d'un personnage, apres tentative d'enrolement.

    Renvoie toujours un verdict explicite. `cloned` distingue une VRAIE
    reproduction d'une voix inventee : c'est ce champ que le pipeline trace,
    pour qu'une voix de synthese ne puisse plus passer pour un clonage.
    """
    character = (character or "").strip()
    if not character:
        return {"ok": False, "cloned": False, "reason": "personnage sans nom"}

    found = find_voice(character)
    if found.get("ok") and is_real_voice(found.get("metadata") or {}):
        meta = found["metadata"]
        return {"ok": True, "cloned": True, "slug": found["slug"],
                "reference": found["reference"],
                "source": meta.get("source"),
                "duration_s": meta.get("duration_s"),
                "quality": meta.get("reference_quality_score")}

    enrolled = enroll_from_dropbox(character, lang=lang)
    if enrolled.get("ok"):
        again = find_voice(character)
        return {"ok": True, "cloned": True, "slug": enrolled.get("slug"),
                "reference": again.get("reference"),
                "source": f"echantillon:{Path(enrolled['enrolled_from']).name}",
                "enrolled_now": True,
                "quality": (enrolled.get("audio_quality") or {}).get("quality_score")}

    return {
        "ok": False,
        "cloned": False,
        "reason": enrolled.get("error") or "aucune reference",
        "dropbox": str(DROPBOX_DIR),
        "hint": f"depose un extrait audio ou video de la voix, nomme "
                f"« {'_'.join(_core_tokens(character)) or slugify(character)} »"
                f" (wav/mp3/m4a/mp4/mkv/mov...), dans {DROPBOX_DIR}",
    }


def find_voice(character: str) -> dict:
    """Look up a character in the library. Returns metadata + reference path or {ok: False}."""
    slug = slugify(character)
    voice_dir = LIBRARY_DIR / slug
    if not voice_dir.exists():
        return {"ok": False}
    ref = voice_dir / "reference.wav"
    if not ref.exists():
        return {"ok": False}
    meta_path = voice_dir / "metadata.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": True, "slug": slug, "reference": str(ref), "metadata": meta}


# --------------------------------------------------------------------------
# Synthesis engines
# --------------------------------------------------------------------------

_xtts_pipeline = None


def _get_xtts():
    """Lazy-load XTTS-v2. ~2GB download on first call, cached afterwards."""
    global _xtts_pipeline
    if _xtts_pipeline is not None:
        return _xtts_pipeline
    emit("xtts_load", "chargement XTTS-v2 (premier appel: 2GB telechargement)...")
    from TTS.api import TTS
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Auto-accept CPML license for non-interactive runs.
    os.environ["COQUI_TOS_AGREED"] = "1"
    _xtts_pipeline = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    emit("xtts_ready", "XTTS-v2 charge")
    return _xtts_pipeline


_f5_pipeline = None


def _get_f5():
    """Lazy-load F5-TTS English."""
    global _f5_pipeline
    if _f5_pipeline is not None:
        return _f5_pipeline
    emit("f5_load", "chargement F5-TTS...")
    from f5_tts.api import F5TTS
    _f5_pipeline = F5TTS()
    emit("f5_ready", "F5-TTS charge")
    return _f5_pipeline


def synthesize_xtts(text: str, reference_wav: str, output_wav: str, lang: str = "fr") -> dict:
    """XTTS-v2 zero-shot voice cloning, retained as an explicit fallback."""
    try:
        tts = _get_xtts()
        emit("xtts_gen", f"synthese {lang}: {text[:60]}...")
        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        tts.tts_to_file(
            text=text,
            speaker_wav=reference_wav,
            language=lang,
            file_path=output_wav,
        )
        # Estimate duration via soundfile
        import soundfile as sf
        info = sf.info(output_wav)
        return {"ok": True, "wav": output_wav, "duration_s": float(info.duration), "engine": "xtts-v2"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "engine": "xtts-v2"}


def synthesize_f5(text: str, reference_wav: str, output_wav: str, ref_text: str = "") -> dict:
    """F5-TTS zero-shot, retained as an explicit fallback."""
    try:
        f5 = _get_f5()
        emit("f5_gen", f"synthese F5: {text[:60]}...")
        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        # F5-TTS API: infer(ref_audio, ref_text, gen_text, file_wave)
        f5.infer(
            ref_file=reference_wav,
            ref_text=ref_text,  # if empty, F5-TTS auto-transcribes via Whisper
            gen_text=text,
            file_wave=output_wav,
            seed=-1,
        )
        import soundfile as sf
        info = sf.info(output_wav)
        return {"ok": True, "wav": output_wav, "duration_s": float(info.duration), "engine": "f5-tts"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "engine": "f5-tts"}


def _reference_prompt_text(reference_wav: str) -> str:
    reference = Path(reference_wav)
    metadata_path = reference.parent / "metadata.json"
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            transcript = str(metadata.get("transcript") or "").strip()
            if transcript:
                return transcript
        except Exception:
            pass
    for sidecar in (reference.with_suffix(".txt"), reference.parent / "transcript.txt"):
        if sidecar.is_file():
            try:
                transcript = sidecar.read_text(encoding="utf-8").strip()
                if transcript:
                    return transcript
            except Exception:
                pass
    return ""


def synthesize_cosyvoice3(
    text: str,
    reference_wav: str,
    output_wav: str,
    lang: str,
    prompt_text: str = "",
    instruction: str = "",
) -> dict:
    """Run the official CosyVoice3 API through its isolated Python runtime."""
    status = cosyvoice3_status()
    if not status.get("ok"):
        return {
            "ok": False,
            "engine": "cosyvoice3",
            "error": status.get("error") or "runtime CosyVoice3 indisponible",
            "runtime": status,
        }

    cmd = [
        str(_cosyvoice3_python()),
        str(COSYVOICE3_ADAPTER),
        "--synthesize",
        "--text", text,
        "--reference", reference_wav,
        "--lang", lang,
        "--output", output_wav,
    ]
    resolved_prompt = (prompt_text or _reference_prompt_text(reference_wav)).strip()
    if resolved_prompt:
        cmd.extend(["--prompt-text", resolved_prompt])
    if instruction.strip():
        cmd.extend(["--instruction", instruction.strip()])
    emit("cosyvoice3_gen", f"synthese {lang}: {text[:60]}...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except Exception as exc:
        return {"ok": False, "engine": "cosyvoice3", "error": f"{type(exc).__name__}: {exc}"}
    parsed = _last_json_line(proc.stdout)
    if parsed is None:
        return {
            "ok": False,
            "engine": "cosyvoice3",
            "error": (proc.stderr or proc.stdout or "sortie CosyVoice3 non JSON")[:400],
        }
    if proc.returncode != 0:
        parsed["ok"] = False
        parsed.setdefault("error", (proc.stderr or "CosyVoice3 a echoue")[:400])
    return parsed


def _reference_cache_identity(reference_wav: str) -> str:
    reference = Path(reference_wav)
    try:
        stat = reference.stat()
        return f"{reference.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        return str(reference)


def synthesize(
    text: str,
    reference_wav: str,
    output_wav: str,
    lang: str = "auto",
    prompt_text: str = "",
    instruction: str = "",
) -> dict:
    """Quality-first synthesis: CosyVoice3, then explicit legacy fallbacks."""
    if lang == "auto":
        lang = detect_language(text)

    # Include reference content identity and prompt transcript to avoid stale clones.
    key_material = "|".join([
        "voice-pipeline-v3",
        text,
        _reference_cache_identity(reference_wav),
        lang,
        prompt_text,
        instruction,
    ])
    key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:20]
    cached = CACHE_DIR / f"{key}.wav"
    cached_meta = CACHE_DIR / f"{key}.json"
    if cached.exists() and cached.stat().st_size > 1024:
        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, output_wav)
        import soundfile as sf
        info = sf.info(output_wav)
        metadata = {}
        if cached_meta.is_file():
            try:
                metadata = json.loads(cached_meta.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}
        return {
            "ok": True,
            "wav": output_wav,
            "duration_s": float(info.duration),
            "engine": metadata.get("engine", "cache-legacy-engine-unknown"),
            "model": metadata.get("model"),
            "cached": True,
        }

    attempts = []
    engines = [
        (
            "cosyvoice3",
            lambda: synthesize_cosyvoice3(
                text,
                reference_wav,
                output_wav,
                lang,
                prompt_text=prompt_text,
                instruction=instruction,
            ),
        ),
    ]
    if lang == "en":
        engines.extend([
            ("f5-tts", lambda: synthesize_f5(text, reference_wav, output_wav, ref_text=prompt_text)),
            ("xtts-v2", lambda: synthesize_xtts(text, reference_wav, output_wav, lang="en")),
        ])
    else:
        engines.extend([
            ("xtts-v2", lambda: synthesize_xtts(text, reference_wav, output_wav, lang=lang)),
            ("f5-tts", lambda: synthesize_f5(text, reference_wav, output_wav, ref_text=prompt_text)),
        ])

    result = {"ok": False, "engine": None, "error": "aucun moteur vocal disponible"}
    for engine_name, run_engine in engines:
        try:
            candidate = run_engine()
        except Exception as exc:
            candidate = {
                "ok": False,
                "engine": engine_name,
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }
        attempts.append({
            "engine": engine_name,
            "ok": bool(candidate.get("ok")),
            **({"error": str(candidate.get("error") or "")[:300]} if not candidate.get("ok") else {}),
        })
        result = candidate
        if candidate.get("ok"):
            break
        emit("fallback", f"{engine_name} echec -> moteur suivant")

    if result.get("ok"):
        result["fallback_chain"] = attempts
        if attempts and attempts[0]["engine"] != result.get("engine"):
            result["warnings"] = [{
                "code": "voice_engine_fallback",
                "message": (
                    f"Moteur prioritaire indisponible; rendu vocal produit par "
                    f"{result.get('engine')}."
                ),
                "attempts": attempts,
            }]
        try:
            shutil.copy2(output_wav, cached)
            cached_meta.write_text(json.dumps({
                "engine": result.get("engine"),
                "model": result.get("model"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    else:
        result["fallback_chain"] = attempts

    return result


# --------------------------------------------------------------------------
# Voice presets for "fresh" synthetic voices when no celebrity reference exists
# --------------------------------------------------------------------------

# These are descriptors the LLM can pick from; the actual reference WAV is
# generated once by XTTS-v2 default speaker + saved in voices/library/_presets/
PRESETS = {
    "young_male_french":   {"lang": "fr", "description": "voix masculine jeune francaise, ton clair"},
    "older_male_french":   {"lang": "fr", "description": "voix masculine grave francaise, posee"},
    "young_female_french": {"lang": "fr", "description": "voix feminine jeune francaise, douce"},
    "older_female_french": {"lang": "fr", "description": "voix feminine francaise mure, chaleureuse"},
    "child_french":        {"lang": "fr", "description": "voix d'enfant francaise"},
    "young_male_english":   {"lang": "en", "description": "young male English voice"},
    "older_male_english":   {"lang": "en", "description": "older male English, deep tone"},
    "young_female_english": {"lang": "en", "description": "young female English voice"},
}


PRESET_PERSONAS = {
    "young_male_french": "atlas-strong",
    "older_male_french": "cinema-deep",
    "young_female_french": "iris-bright",
    "older_female_french": "sumi-warm",
    "child_french": "iris-bright",
    "young_male_english": "atlas-strong",
    "older_male_english": "cinema-deep",
    "young_female_english": "iris-bright",
}


def synthesize_fresh(text: str, voice_preset: str, output_wav: str, lang: str = "auto") -> dict:
    """Generate a stable synthetic style voice without cloning a real person."""
    preset = (voice_preset or "").strip().lower()
    meta = PRESETS.get(preset) or {}
    resolved_lang = (lang if lang != "auto" else meta.get("lang")) or detect_language(text)
    resolved_lang = resolved_lang[:2]
    persona = PRESET_PERSONAS.get(preset)
    if persona is None:
        if "female" in preset or "feminine" in preset:
            persona = "iris-bright" if "young" in preset else "sumi-warm"
        elif "male" in preset or "masculine" in preset:
            persona = "atlas-strong" if "young" in preset else "cinema-deep"
        else:
            persona = "lyra-soft"

    voice_service = Path(__file__).resolve().parents[1] / "voice_service.py"
    if not voice_service.exists():
        return {"ok": False, "error": "voice_service.py absent"}

    cmd = [
        sys.executable, str(voice_service),
        "--mode", "tts",
        "--text", text,
        "--lang", resolved_lang,
        "--voice", persona,
        "--output", output_wav,
    ]
    emit("fresh_voice", f"{preset or persona} ({resolved_lang})")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not Path(output_wav).exists():
        return {"ok": False, "error": (proc.stderr or proc.stdout)[:300]}

    last_json = None
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                last_json = json.loads(line)
                break
            except Exception:
                pass
    result = last_json if isinstance(last_json, dict) else {"ok": True}
    result.update({
        "ok": bool(result.get("ok", True)),
        "wav": output_wav,
        "engine": result.get("engine", "fresh-tts"),
        "voice_preset": preset or persona,
        "voice_persona": persona,
        "lang": resolved_lang,
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument("--synthesize-fresh", action="store_true")
    parser.add_argument("--resolve", action="store_true",
                        help="Etat de la voix d'un personnage, avec enrolement "
                             "automatique d'un echantillon depose")
    parser.add_argument("--ensure-default", action="store_true",
                        help="v82ll : auto-bootstrap default_<lang> entry via Kokoro TTS")
    parser.add_argument("--character", default="")
    parser.add_argument("--voice-preset", default="")
    parser.add_argument("--reference", help="Path to reference WAV for register")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--lang", default="auto", help="fr|en|auto")
    parser.add_argument("--output", help="Output WAV path")
    parser.add_argument("--source", default="", help="Provenance string (URL/file)")
    parser.add_argument(
        "--transcript",
        default="",
        help="Transcription exacte du WAV de reference, conservee dans la fiche voix",
    )
    parser.add_argument(
        "--prompt-text",
        default="",
        help="Transcription exacte de la reference pour le clonage zero-shot",
    )
    parser.add_argument("--instruction", default="", help="Direction de jeu optionnelle")
    parser.add_argument("--quality-score", type=float, default=0.0)
    parser.add_argument("--duration-s", type=float, default=0.0)
    args = parser.parse_args()

    if args.check:
        deps = check_dependencies()
        print(json.dumps(deps), flush=True)
        sys.exit(0 if deps["ok"] else 1)

    if args.list:
        result = list_library()
        print(json.dumps(result), flush=True)
        sys.exit(0)

    if args.resolve:
        result = resolve_voice(args.character,
                               args.lang if args.lang != "auto" else "fr")
        print(json.dumps(result, ensure_ascii=False), flush=True)
        sys.exit(0)

    if args.ensure_default:
        result = ensure_default_voice(args.lang if args.lang != "auto" else "fr")
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    if args.register:
        if not args.character or not args.reference:
            print(json.dumps({"ok": False, "error": "--character and --reference required"}), flush=True)
            sys.exit(1)
        result = register_voice(
            args.character,
            args.reference,
            lang=args.lang if args.lang != "auto" else "fr",
            source=args.source,
            quality_score=args.quality_score,
            duration_s=args.duration_s,
            transcript=args.transcript,
        )
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    if args.synthesize_fresh:
        if not args.text or not args.output:
            print(json.dumps({"ok": False, "error": "--text and --output required"}), flush=True)
            sys.exit(1)
        result = synthesize_fresh(args.text, args.voice_preset, args.output, lang=args.lang)
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    if args.synthesize:
        if not args.text or not args.output:
            print(json.dumps({"ok": False, "error": "--text and --output required"}), flush=True)
            sys.exit(1)
        # Find reference: explicit --reference > library lookup by --character
        ref = args.reference
        prompt_text = args.prompt_text
        if not ref and args.character:
            found = find_voice(args.character)
            if found.get("ok"):
                ref = found["reference"]
                if not prompt_text:
                    prompt_text = str((found.get("metadata") or {}).get("transcript") or "")
        if not ref:
            print(json.dumps({"ok": False, "error": "no reference WAV (give --reference or --character with registered voice)"}), flush=True)
            sys.exit(1)
        result = synthesize(
            args.text,
            ref,
            args.output,
            lang=args.lang,
            prompt_text=prompt_text,
            instruction=args.instruction,
        )
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
