"""
voice_clone.py -- Voice cloning + bibliotheque globale de voix.

Routage par langue:
  - francais (fr) -> Coqui XTTS-v2 (excellent FR + clonage zero-shot)
  - anglais  (en) -> F5-TTS (excellent EN + clonage)
  - autres        -> XTTS-v2 (multilingue)

Bibliotheque:
  application/voices/library/{character_slug}/
    reference.wav   <- echantillon de la voix (15-30s, mono 16kHz)
    embedding.npy   <- embedding ECAPA pour fingerprint
    metadata.json   <- {character, source, lang, extracted_at, quality_score}

Usage:
  python voice_clone.py --check
  python voice_clone.py --list
  python voice_clone.py --register --character "natsu" --reference natsu_sample.wav --lang fr
  python voice_clone.py --synthesize --character "natsu" --text "Salut, je suis Natsu" --lang fr --output out.wav
  python voice_clone.py --synthesize-fresh --voice-preset "young_male_french" --text "..." --output out.wav

Output JSON sur stdout (derniere ligne):
  {"ok": true, "wav": "out.wav", "duration_s": 3.2, "engine": "xtts-v2|f5-tts"}
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
CACHE_DIR = WORKSPACE / "temp" / "voice_clone"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def slugify(name: str) -> str:
    """Convert 'Natsu Fairy Tail VF' -> 'natsu_fairy_tail_vf'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unnamed"


def detect_language(text: str) -> str:
    """Heuristique simple FR vs EN. La detection robuste se fait cote LLM en amont,
    cette fonction est juste un filet de securite pour le routage TTS."""
    fr_markers = [" le ", " la ", " les ", " un ", " une ", " est ", " et ", " que ", " qui ", " avec ", " pour ", "ca ", "ce "]
    en_markers = [" the ", " a ", " an ", " is ", " are ", " and ", " that ", " with ", " for ", " this ", " it "]
    t = " " + text.lower() + " "
    fr = sum(1 for m in fr_markers if m in t)
    en = sum(1 for m in en_markers if m in t)
    if fr > en:
        return "fr"
    return "en"


def check_dependencies() -> dict:
    """Verify TTS engines are importable."""
    info = {"f5_tts": False, "xtts_v2": False, "torch_cuda": False}
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

    info["ok"] = info["f5_tts"] or info["xtts_v2"]
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
                "extracted_at": meta.get("extracted_at"),
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


def register_voice(character: str, reference_wav: str, lang: str = "fr",
                    source: str = "", quality_score: float = 0.0,
                    duration_s: float = 0.0) -> dict:
    """Add a voice to the global library. The reference WAV is copied in,
    and a fingerprint embedding is computed and stored.
    """
    slug = slugify(character)
    voice_dir = LIBRARY_DIR / slug
    voice_dir.mkdir(parents=True, exist_ok=True)

    src = Path(reference_wav)
    if not src.exists():
        return {"ok": False, "error": f"reference not found: {reference_wav}"}

    target_ref = voice_dir / "reference.wav"
    shutil.copy2(src, target_ref)

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
        "duration_s": duration_s,
    }
    (voice_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "slug": slug, "path": str(target_ref)}


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
    """XTTS-v2 zero-shot voice cloning. Best for FR + multilingual."""
    tts = _get_xtts()
    emit("xtts_gen", f"synthese {lang}: {text[:60]}...")
    Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
    try:
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
    """F5-TTS zero-shot. English/Chinese strong, FR weaker but ok cross-lingual."""
    f5 = _get_f5()
    emit("f5_gen", f"synthese F5: {text[:60]}...")
    Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
    try:
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


def synthesize(text: str, reference_wav: str, output_wav: str, lang: str = "auto") -> dict:
    """Top-level synth: route by language, with fallback chain."""
    if lang == "auto":
        lang = detect_language(text)

    # Cache by hash(text + ref + lang)
    key = hashlib.md5(f"{text}|{reference_wav}|{lang}".encode("utf-8")).hexdigest()[:16]
    cached = CACHE_DIR / f"{key}.wav"
    if cached.exists() and cached.stat().st_size > 1024:
        shutil.copy2(cached, output_wav)
        import soundfile as sf
        info = sf.info(output_wav)
        return {"ok": True, "wav": output_wav, "duration_s": float(info.duration), "engine": "cache"}

    # Routage: FR -> XTTS-v2 (meilleur), EN -> F5-TTS, autres -> XTTS-v2 multilingue
    if lang == "en":
        result = synthesize_f5(text, reference_wav, output_wav)
        if not result["ok"]:
            emit("fallback", "F5-TTS echec -> XTTS-v2")
            result = synthesize_xtts(text, reference_wav, output_wav, lang="en")
    else:
        result = synthesize_xtts(text, reference_wav, output_wav, lang=lang)
        if not result["ok"] and lang == "en":
            emit("fallback", "XTTS-v2 echec -> F5-TTS")
            result = synthesize_f5(text, reference_wav, output_wav)

    if result.get("ok"):
        try:
            shutil.copy2(output_wav, cached)
        except Exception:
            pass

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
    parser.add_argument("--ensure-default", action="store_true",
                        help="v82ll : auto-bootstrap default_<lang> entry via Kokoro TTS")
    parser.add_argument("--character", default="")
    parser.add_argument("--voice-preset", default="")
    parser.add_argument("--reference", help="Path to reference WAV for register")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--lang", default="auto", help="fr|en|auto")
    parser.add_argument("--output", help="Output WAV path")
    parser.add_argument("--source", default="", help="Provenance string (URL/file)")
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
        if not ref and args.character:
            found = find_voice(args.character)
            if found.get("ok"):
                ref = found["reference"]
        if not ref:
            print(json.dumps({"ok": False, "error": "no reference WAV (give --reference or --character with registered voice)"}), flush=True)
            sys.exit(1)
        result = synthesize(args.text, ref, args.output, lang=args.lang)
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
