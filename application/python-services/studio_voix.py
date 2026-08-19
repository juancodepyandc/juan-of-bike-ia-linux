"""
Studio de réplication de voix par échantillon.

Fonctionnalités:
- Enregistrement ou import d'un échantillon vocal (durée minimale: ~3s)
- Réécoute et prévisualisation avant validation
- Synthèse de texte / chanson / discours avec la voix répliquée
- Sauvegarde permanente (avec nom personnalisé) ou session temporaire
- Arborescence organisée sous application/output/voix/ (echantillons, profils, generations, sessions)
- Fonctionne en CLI direct, en tunnel web et via l'interface utilisateur.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Chemins de l'arborescence voix
WORKSPACE = Path(__file__).resolve().parents[1]
VOIX_DIR = WORKSPACE / "output" / "voix"
ECHANTILLONS_DIR = VOIX_DIR / "echantillons"
PROFILS_DIR = VOIX_DIR / "profils"
GENERATIONS_DIR = VOIX_DIR / "generations"
CHANSONS_DIR = VOIX_DIR / "chansons"
MUSIQUES_DIR = VOIX_DIR / "musiques"
SESSIONS_DIR = VOIX_DIR / "sessions"

LEGACY_LIBRARY_DIR = WORKSPACE / "voices" / "library"
LEGACY_DROPBOX_DIR = WORKSPACE / "voices" / "echantillons"

for d in (VOIX_DIR, ECHANTILLONS_DIR, PROFILS_DIR, GENERATIONS_DIR, CHANSONS_DIR, MUSIQUES_DIR, SESSIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Imports du moteur vocal
sys.path.insert(0, str(Path(__file__).resolve().parent / "cinema"))
import voice_clone  # noqa: E402


def emit(stage: str, detail: str) -> None:
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def slugify(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "voix_sans_nom"


def auto_detect_emotion(text: str) -> dict:
    """Analyse sémantique et prosodique intelligente du texte pour guider l'émotion vocale sans rigidité."""
    t = (text or "").strip()
    if not t:
        return {"emotion": "neutre", "intensity": "modéré", "instruction": "", "score": 0.5}

    t_lower = t.lower()
    exclamations = t.count("!")
    questions = t.count("?")
    all_caps_words = len([w for w in t.split() if len(w) > 2 and w.isupper()])

    # Dictionnaires d'indices émotionnels
    joy_cues = {"joie", "heureux", "heureuse", "content", "contente", "génial", "super", "bravo", "merci", "fête", "rire", "amour", "aime", "adorer", "soleil", "victoire", "incroyable", "chouette", "magnifique", "parfait", "merveilleuse", "merveilleux", "formidable", "extraordinaire", "ravi", "ravie", "splendide", "plaisir"}
    sad_cues = {"triste", "pleurer", "larmes", "douleur", "malheur", "adieu", "seul", "seule", "solitude", "perdu", "mélancolie", "regret", "mort", "désolé", "tristesse", "sombre", "peine", "déchirant"}
    anger_cues = {"colère", "énervé", "rage", "furieux", "inacceptable", "haine", "stop", "merde", "insupportable", "idiot", "menteur", "traître", "jamais", "dégage", "taisez", "violence"}
    fear_cues = {"peur", "danger", "panique", "effrayé", "trembler", "terreur", "horreur", "angoisse", "secours", "aidez", "fuir", "menace", "effroi"}
    whisper_cues = {"chut", "doucement", "secret", "chuchote", "oreille", "silence", "discret", "nuit", "dors", "dormir", "calme", "murmure", "doucereux"}
    singing_cues = {"chante", "chanson", "musique", "mélodie", "refrain", "couplet", "lalala", "danse", "rythme", "accord", "note", "tempo", "vocalise"}
    enthusiasm_cues = {"passion", "énergie", "absolument", "victoire", "magique", "dynamique", "go", "fonce", "extraordinaire", "puissant", "vif"}
    calm_cues = {"paisible", "repos", "nature", "vent", "respiration", "serein", "tranquille", "détente", "douceur"}

    words = set(re.findall(r"\b[a-zàâéèêëîïôùûüç]+\b", t_lower))

    joy_score = len(words & joy_cues) * 2 + (1 if exclamations >= 1 else 0)
    sad_score = len(words & sad_cues) * 2
    anger_score = len(words & anger_cues) * 2 + all_caps_words + (1 if exclamations >= 2 else 0)
    fear_score = len(words & fear_cues) * 2
    whisper_score = len(words & whisper_cues) * 2
    singing_score = len(words & singing_cues) * 2
    enthusiasm_score = len(words & enthusiasm_cues) * 2 + (2 if exclamations >= 2 else 0)
    calm_score = len(words & calm_cues) * 2

    candidates = [
        ("joyeux", joy_score, "Parle avec une énergie joyeuse, lumineuse et un grand sourire dans la voix."),
        ("enthousiaste", enthusiasm_score, "Parle avec beaucoup d'enthousiasme, de passion et de dynamisme."),
        ("triste", sad_score, "Parle d'un ton touchant, mélancolique, avec une douce émotion retenue."),
        ("colère", anger_score, "Parle avec intensité, fermeté et autorité."),
        ("peur", fear_score, "Parle d'un ton haletant et inquiet."),
        ("chuchoté", whisper_score, "Chuchote doucement et intimement au creux de l'oreille."),
        ("calme", calm_score, "Parle d'une voix douce, posée, relaxante et rassurante."),
        ("chanté", singing_score, "Chante de manière mélodieuse, rythmée et expressive."),
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    top_emotion, top_score, default_instr = candidates[0]

    if top_score < 2:
        if questions >= 2:
            return {
                "emotion": "curieux",
                "intensity": "modéré",
                "instruction": "Adopte un ton curieux, expressif et interrogatif.",
                "score": 0.6,
            }
        elif exclamations >= 2:
            return {
                "emotion": "enthousiaste",
                "intensity": "intense",
                "instruction": "Parle avec beaucoup d'enthousiasme, de passion et de dynamisme.",
                "score": 0.75,
            }
        else:
            return {
                "emotion": "naturel",
                "intensity": "modéré",
                "instruction": "Parle avec un ton naturel, posé et expressif.",
                "score": 0.5,
            }

    intensity = "intense" if top_score >= 4 else "modéré"
    return {
        "emotion": top_emotion,
        "intensity": intensity,
        "instruction": default_instr,
        "score": round(min(1.0, 0.5 + top_score * 0.15), 2),
    }


def search_instrumental_tracks(query: str = "", limit: int = 12) -> list[dict]:
    """Recherche ou génère des pistes instrumentales d'accompagnement prêtes pour le chant."""
    _ensure_builtin_instrumentals()
    tracks = []
    q_tokens = set(re.findall(r"\b\w+\b", (query or "").lower()))

    for f in sorted(MUSIQUES_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if not f.is_file() or f.suffix.lower() not in {".wav", ".mp3", ".ogg", ".flac"}:
            continue
        stat = f.stat()
        name_clean = f.stem.replace("_", " ").title()
        meta_file = f.with_name(f.stem + "_meta.json")
        meta = {}
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        # Matching
        f_tokens = set(re.findall(r"\b\w+\b", f.name.lower())) | set(re.findall(r"\b\w+\b", meta.get("style", "").lower()))
        score = len(q_tokens & f_tokens) if q_tokens else 1

        if not q_tokens or score > 0:
            tracks.append({
                "id": f.name,
                "name": meta.get("title") or name_clean,
                "path": str(f),
                "filename": f.name,
                "style": meta.get("style", "Général"),
                "bpm": meta.get("bpm", 120),
                "key": meta.get("key", "C"),
                "duration_s": meta.get("duration_s", 16.0),
                "audioUrl": f"/api/voice/studio/music/track/{f.name}/audio",
                "size_bytes": stat.st_size,
            })

    return tracks[:limit]


def _ensure_builtin_instrumentals() -> None:
    """Génère des boucles harmoniques instrumentales légères si le dossier musiques est vide."""
    if any(MUSIQUES_DIR.glob("*.wav")):
        return

    try:
        import numpy as np
        import soundfile as sf

        sr = 44100
        dur = 16.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)

        presets = [
            (
                "pop_piano_ballade.wav",
                "Pop Piano Ballade",
                "Pop",
                100,
                "C",
                [[261.63, 329.63, 392.00], [220.00, 261.63, 329.63], [174.61, 220.00, 261.63], [196.00, 246.94, 293.66]],
            ),
            (
                "lofi_chill_lounge.wav",
                "Lofi Chill Lounge",
                "Lo-Fi",
                85,
                "F",
                [[174.61, 220.00, 261.63, 329.63], [146.83, 174.61, 220.00, 261.63], [130.81, 164.81, 196.00, 246.94], [196.00, 246.94, 293.66, 349.23]],
            ),
            (
                "acoustic_guitar_folk.wav",
                "Acoustic Folk Arpèges",
                "Acoustique",
                95,
                "G",
                [[196.00, 246.94, 293.66, 392.00], [164.81, 196.00, 246.94, 329.63], [261.63, 329.63, 392.00, 523.25], [146.83, 220.00, 293.66, 440.00]],
            ),
            (
                "synthwave_retro_80s.wav",
                "Synthwave Retro Drive",
                "Électro",
                115,
                "Am",
                [[220.00, 261.63, 329.63], [174.61, 220.00, 261.63], [261.63, 329.63, 392.00], [196.00, 246.94, 293.66]],
            ),
        ]

        for filename, title, style, bpm, key_sig, chord_list in presets:
            audio = np.zeros_like(t)
            sec_per_chord = dur / len(chord_list)
            for i, chord in enumerate(chord_list):
                start = int(i * sec_per_chord * sr)
                end = int((i + 1) * sec_per_chord * sr)
                sub_t = t[start:end] - (i * sec_per_chord)
                env = np.exp(-sub_t / 2.5) * np.sin(np.pi * np.clip(sub_t / 0.05, 0, 1) * 0.5)
                for freq in chord:
                    note = np.sin(2 * np.pi * freq * sub_t) * 0.4
                    note += np.sin(2 * np.pi * freq * 2 * sub_t) * 0.2
                    note += np.sin(2 * np.pi * freq * 3 * sub_t) * 0.08
                    audio[start:end] += note * env * 0.25

                root = chord[0] / 2
                bass = np.sin(2 * np.pi * root * sub_t) * 0.3 * np.exp(-sub_t / 3.0)
                audio[start:end] += bass

            audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.8
            target = MUSIQUES_DIR / filename
            sf.write(target, audio, sr)
            meta = {
                "title": title,
                "style": style,
                "bpm": bpm,
                "key": key_sig,
                "duration_s": dur,
            }
            target.with_name(target.stem + "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_tree_summary() -> dict:
    """Retourne la structure et le contenu détaillé de application/output/voix/."""
    _ensure_builtin_instrumentals()
    for d in (VOIX_DIR, ECHANTILLONS_DIR, PROFILS_DIR, GENERATIONS_DIR, CHANSONS_DIR, MUSIQUES_DIR, SESSIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    echantillons = []
    for f in sorted(ECHANTILLONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}:
            stat = f.stat()
            echantillons.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": int(stat.st_mtime),
                "date": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

    profils = []
    # Scanne profils_dir ainsi que legacy_library_dir
    seen_slugs = set()
    for base_dir in (PROFILS_DIR, LEGACY_LIBRARY_DIR):
        if not base_dir.exists():
            continue
        for d in sorted(base_dir.iterdir()):
            if not d.is_dir():
                continue
            slug = d.name
            if slug in seen_slugs:
                continue
            ref_path = d / "reference.wav"
            meta_path = d / "metadata.json"
            if not ref_path.exists():
                continue
            seen_slugs.add(slug)
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            profils.append({
                "slug": slug,
                "name": meta.get("character") or meta.get("name") or slug.replace("_", " ").title(),
                "path": str(d),
                "reference": str(ref_path),
                "lang": meta.get("lang", "fr"),
                "duration_s": meta.get("duration_s", 0.0),
                "quality_score": meta.get("reference_quality_score") or meta.get("quality_score", 0.0),
                "transcript": meta.get("transcript", ""),
                "extracted_at": meta.get("extracted_at"),
                "is_permanent": True,
            })

    chansons = []
    for f in sorted(CHANSONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if f.is_file() and f.suffix.lower() == ".wav":
            stat = f.stat()
            meta_file = f.with_name(f.stem + "_meta.json")
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            chansons.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": int(stat.st_mtime),
                "date": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "text": meta.get("text", ""),
                "voice_name": meta.get("voice_name") or meta.get("slug", "inconnue"),
                "duration_s": meta.get("duration_s", 0.0),
                "backing_track": meta.get("backing_track"),
                "style": meta.get("style", "Chanson"),
            })

    generations = []
    for f in sorted(GENERATIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if f.is_file() and f.suffix.lower() == ".wav":
            stat = f.stat()
            meta_file = f.with_name(f.stem + "_meta.json")
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            generations.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": int(stat.st_mtime),
                "date": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "text": meta.get("text", ""),
                "voice_name": meta.get("voice_name") or meta.get("slug", "inconnue"),
                "duration_s": meta.get("duration_s", 0.0),
                "engine": meta.get("engine", "cosyvoice3"),
                "emotion": meta.get("emotion"),
            })

    sessions = []
    for f in sorted(SESSIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if f.is_file() and f.suffix.lower() in {".wav", ".mp3", ".ogg"}:
            stat = f.stat()
            sessions.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": int(stat.st_mtime),
                "date": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

    return {
        "ok": True,
        "root": str(VOIX_DIR),
        "directories": {
            "echantillons": str(ECHANTILLONS_DIR),
            "profils": str(PROFILS_DIR),
            "generations": str(GENERATIONS_DIR),
            "chansons": str(CHANSONS_DIR),
            "musiques": str(MUSIQUES_DIR),
            "sessions": str(SESSIONS_DIR),
        },
        "counts": {
            "echantillons": len(echantillons),
            "profils": len(profils),
            "generations": len(generations),
            "chansons": len(chansons),
            "musiques": len(list(MUSIQUES_DIR.glob("*.wav"))),
            "sessions": len(sessions),
        },
        "echantillons": echantillons,
        "profils": profils,
        "generations": generations,
        "chansons": chansons,
        "sessions": sessions,
    }


def normalize_sample_to_wav(source_path: str | Path, target_path: str | Path | None = None) -> Path:
    """Convertit et normalise un fichier audio/vidéo en WAV 16kHz mono."""
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Fichier source introuvable: {source_path}")

    if target_path is None:
        target = ECHANTILLONS_DIR / f"sample_{int(time.time())}_{src.stem[:24]}.wav"
    else:
        target = Path(target_path)

    target.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg,
        "-y",
        "-i", str(src),
        "-vn",
        "-map_metadata", "-1",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-loglevel", "error",
        str(target),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not target.is_file():
        raise RuntimeError(f"Échec de normalisation ffmpeg: {proc.stderr or proc.stdout}")

    return target


def analyze_sample(wav_path: str | Path) -> dict:
    """Analyse un échantillon vocal avec critères minimaux (durée min: ~2.5s)."""
    return voice_clone.analyze_reference_audio(str(wav_path))


def play_audio_cli(audio_path: str | Path) -> bool:
    """Joue un fichier audio dans la console via ffplay, paplay, aplay ou mpv."""
    p = str(audio_path)
    if not os.path.isfile(p):
        print(f"[!] Fichier audio introuvable: {p}")
        return False

    players = [
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", p],
        ["paplay", p],
        ["aplay", "-q", p],
        ["mpv", "--no-video", p],
    ]
    for cmd in players:
        binary = cmd[0]
        if shutil.which(binary):
            try:
                subprocess.run(cmd, check=True, timeout=180)
                return True
            except Exception:
                continue
    print(f"[!] Aucun lecteur audio système disponible pour jouer {p}.")
    return False


def record_microphone_cli(duration_s: int = 5, output_path: Path | None = None) -> Path:
    """Enregistre la voix depuis le microphone système."""
    if output_path is None:
        output_path = ECHANTILLONS_DIR / f"record_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[•] Préparation de l'enregistrement ({duration_s} secondes minimum recommandées)...")
    for i in range(3, 0, -1):
        print(f"    Début dans {i}...", flush=True)
        time.sleep(1)
    print("    >>> PARLEZ MAINTENANT ! (Enregistrement en cours) <<<", flush=True)

    # Tente arecord puis ffmpeg
    if shutil.which("arecord"):
        cmd = [
            "arecord",
            "-d", str(duration_s),
            "-f", "cd",
            "-t", "wav",
            "-q",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 1000:
            print("    [✓] Enregistrement terminé.")
            return normalize_sample_to_wav(output_path, output_path)

    if shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "pulse",
            "-i", "default",
            "-t", str(duration_s),
            "-ac", "1",
            "-ar", "16000",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 1000:
            print("    [✓] Enregistrement terminé via ffmpeg.")
            return output_path

    raise RuntimeError("Impossible d'enregistrer depuis le microphone (arecord / ffmpeg pulse indisponibles).")


def replicate_voice(
    sample_path: str | Path,
    text: str,
    name: str = "Voix Répliquée",
    save_permanent: bool = True,
    lang: str = "fr",
    prompt_text: str = "",
    instruction: str = "",
) -> dict:
    """
    Exécute la réplication vocale complète:
    1. Validation et normalisation de l'échantillon
    2. Sauvegarde permanente (si demandée) dans application/output/voix/profils/{slug}
    3. Synthèse vocale de haute qualité
    4. Archivage dans application/output/voix/generations/
    """
    sample = Path(sample_path)
    if not sample.is_file():
        return {"ok": False, "error": f"Échantillon vocal introuvable: {sample_path}"}

    # 1. Normalisation
    normalized_sample = ECHANTILLONS_DIR / f"norm_{sample.stem}_{int(time.time())}.wav"
    normalized_sample = normalize_sample_to_wav(sample, normalized_sample)

    quality = analyze_sample(normalized_sample)
    if not quality.get("ok"):
        failures = ", ".join(quality.get("failures", []))
        return {
            "ok": False,
            "error": f"Échantillon vocal non conforme: {failures}",
            "quality": quality,
        }

    slug = slugify(name)
    profile_dir = PROFILS_DIR / slug
    ref_for_synth = normalized_sample

    # 2. Sauvegarde permanente
    if save_permanent:
        profile_dir.mkdir(parents=True, exist_ok=True)
        target_ref = profile_dir / "reference.wav"
        shutil.copy2(normalized_sample, target_ref)
        ref_for_synth = target_ref

        # Enregistrement dans la bibliothèque de voix
        reg_result = voice_clone.register_voice(
            character=name,
            reference_wav=str(target_ref),
            lang=lang,
            source=f"studio_echantillon:{sample.name}",
            quality_score=quality.get("quality_score", 0.8),
            duration_s=quality.get("duration_s", 0.0),
            transcript=prompt_text,
        )
        if not reg_result.get("ok"):
            emit("studio_warn", f"Enregistrement profil partiel: {reg_result.get('error')}")

    # 3. Synthèse
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = GENERATIONS_DIR if save_permanent else SESSIONS_DIR
    out_wav = out_dir / f"{slug}_{timestamp}_gen.wav"
    out_meta = out_dir / f"{slug}_{timestamp}_meta.json"

    emit("studio_synth", f"Synthèse de {len(text)} caractères avec la voix '{name}'...")
    synth_res = voice_clone.synthesize(
        text=text,
        reference_wav=str(ref_for_synth),
        output_wav=str(out_wav),
        lang=lang,
        prompt_text=prompt_text,
        instruction=instruction,
    )

    if not synth_res.get("ok") or not out_wav.is_file():
        return {
            "ok": False,
            "error": synth_res.get("error") or "Échec de synthèse vocale répliquée",
            "details": synth_res,
        }

    # 4. Métadonnées de génération
    meta = {
        "text": text,
        "voice_name": name,
        "slug": slug,
        "lang": lang,
        "created_at": int(time.time()),
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration_s": synth_res.get("duration_s", 0.0),
        "engine": synth_res.get("engine", "cosyvoice3"),
        "model": synth_res.get("model"),
        "is_permanent": save_permanent,
        "sample_source": str(sample),
        "quality_score": quality.get("quality_score"),
        "instruction": instruction,
    }
    out_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "name": name,
        "slug": slug,
        "is_permanent": save_permanent,
        "wav": str(out_wav),
        "meta": str(out_meta),
        "duration_s": synth_res.get("duration_s", 0.0),
        "engine": synth_res.get("engine"),
        "quality": quality,
        "text": text,
    }


def mix_vocals_with_instrumental(
    vocal_wav: str | Path,
    instrumental_wav: str | Path,
    output_wav: str | Path,
    vocal_volume: float = 1.0,
    music_volume: float = 0.55,
) -> Path:
    """Mixe la voix chantée et l'accompagnement instrumental avec équilibrage dynamique."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    out = Path(output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-i", str(vocal_wav),
        "-stream_loop", "-1", "-i", str(instrumental_wav),
        "-filter_complex",
        f"[0:a]volume={vocal_volume:.2f},highpass=f=80,lowpass=f=12000[v];[1:a]volume={music_volume:.2f}[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2",
        "-c:a", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        "-loglevel", "error",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not out.is_file():
        # Fallback simple sans filtre si ffmpeg filter_complex a échoué
        shutil.copy2(vocal_wav, out)
    return out


def replicate_singing(
    sample_path: str | Path,
    lyrics: str = "",
    guide_audio: str | Path | None = None,
    backing_music_id: str = "",
    style: str = "Pop",
    bpm: int = 120,
    name: str = "Voix Chantée",
    save_permanent: bool = True,
    lang: str = "fr",
    vocal_volume: float = 1.0,
    music_volume: float = 0.55,
) -> dict:
    """
    Fait chanter la voix répliquée :
    - Soit par conversion vocale (guide audio chanté -> voix cible) via CosyVoice 3 VC
    - Soit par synthèse mélodique des paroles avec instruction de chant
    - Mixe optionnellement avec la musique d'accompagnement sélectionnée
    """
    sample = Path(sample_path)
    if not sample.is_file():
        return {"ok": False, "error": f"Échantillon vocal introuvable: {sample_path}"}

    normalized_sample = ECHANTILLONS_DIR / f"norm_{sample.stem}_{int(time.time())}.wav"
    normalized_sample = normalize_sample_to_wav(sample, normalized_sample)

    slug = slugify(name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_raw_vocal = CHANSONS_DIR / f"{slug}_{timestamp}_vocal.wav"
    out_final_song = CHANSONS_DIR / f"{slug}_{timestamp}_song.wav"
    out_meta = CHANSONS_DIR / f"{slug}_{timestamp}_meta.json"

    # Guide audio fourni pour Voice Conversion
    guide_file: Path | None = None
    if guide_audio:
        gp = Path(guide_audio)
        if gp.is_file():
            guide_file = normalize_sample_to_wav(gp, ECHANTILLONS_DIR / f"guide_{timestamp}_{gp.stem}.wav")

    # Synthèse du chant
    if guide_file and guide_file.is_file():
        emit("studio_sing", f"Conversion vocale du chant pour '{name}'...")
        synth_res = voice_clone.synthesize(
            text=lyrics or "Chant mélodique",
            reference_wav=str(normalized_sample),
            output_wav=str(out_raw_vocal),
            lang=lang,
            source_wav=str(guide_file),
            mode="vc",
        )
    else:
        sing_instruction = f"Chante ces paroles de manière très mélodieuse, rythmée, sur un style {style} à environ {bpm} BPM."
        emit("studio_sing", f"Synthèse chantée de {len(lyrics)} caractères pour '{name}' ({style})...")
        synth_res = voice_clone.synthesize(
            text=lyrics,
            reference_wav=str(normalized_sample),
            output_wav=str(out_raw_vocal),
            lang=lang,
            instruction=sing_instruction,
            mode="zero_shot",
        )

    if not synth_res.get("ok") or not out_raw_vocal.is_file():
        return {
            "ok": False,
            "error": synth_res.get("error") or "Échec de génération du chant vocal",
            "details": synth_res,
        }

    # Résolution de la piste instrumentale
    backing_track_path: Path | None = None
    if backing_music_id:
        safe_m = Path(backing_music_id).name
        candidate = MUSIQUES_DIR / safe_m
        if candidate.is_file():
            backing_track_path = candidate
        else:
            # Recherche par style
            tracks = search_instrumental_tracks(backing_music_id, limit=1)
            if tracks:
                backing_track_path = Path(tracks[0]["path"])

    if backing_track_path and backing_track_path.is_file():
        emit("studio_mix", f"Mixage vocal avec l'accompagnement '{backing_track_path.name}'...")
        mix_vocals_with_instrumental(
            vocal_wav=out_raw_vocal,
            instrumental_wav=backing_track_path,
            output_wav=out_final_song,
            vocal_volume=vocal_volume,
            music_volume=music_volume,
        )
    else:
        shutil.copy2(out_raw_vocal, out_final_song)

    import soundfile as sf
    dur = float(sf.info(str(out_final_song)).duration)

    meta = {
        "text": lyrics,
        "voice_name": name,
        "slug": slug,
        "lang": lang,
        "style": style,
        "bpm": bpm,
        "backing_track": backing_track_path.name if backing_track_path else None,
        "has_backing_music": bool(backing_track_path),
        "duration_s": dur,
        "created_at": int(time.time()),
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": synth_res.get("engine", "cosyvoice3"),
    }
    out_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "ok": True,
        "name": name,
        "slug": slug,
        "wav": str(out_final_song),
        "vocal_wav": str(out_raw_vocal),
        "meta": str(out_meta),
        "duration_s": dur,
        "style": style,
        "has_backing_music": bool(backing_track_path),
        "backing_track": backing_track_path.name if backing_track_path else None,
        "lyrics": lyrics,
    }


def interactive_cli_wizard() -> int:
    """Assistant interactif en ligne de commande pour le studio de voix."""
    print("=" * 66)
    print("  STUDIO DE RÉPLICATION DE VOIX — PAR ÉCHANTILLON COURT")
    print("=" * 66)
    print("  Arborescence de stockage : application/output/voix/")
    print("  • echantillons/  : prises et fichiers audio sources")
    print("  • profils/       : profils vocaux permanents")
    print("  • generations/   : synthèses, chansons et textes répliqués")
    print("  • sessions/      : réplications temporaires")
    print("-" * 66)

    # Étape 1 : Acquisition de l'échantillon
    sample_file: Path | None = None
    while True:
        print("\n[ÉTAPE 1/4] Choisissez la source de la voix à répliquer :")
        print("  1) Enregistrer la voix au microphone (3 à 6 secondes)")
        print("  2) Spécifier le chemin d'un fichier audio/vidéo existant (WAV, MP3, MP4...)")
        print("  3) Utiliser un profil de voix existant dans la bibliothèque")
        print("  Q) Quitter")
        choice = input("Votre choix [1/2/3/Q] > ").strip().lower()

        if choice in ("q", "quit", "exit"):
            print("Sortie du studio.")
            return 0
        elif choice == "1":
            dur_str = input("Durée d'enregistrement en secondes [défaut: 5] > ").strip()
            duration = int(dur_str) if dur_str.isdigit() and int(dur_str) >= 3 else 5
            try:
                sample_file = record_microphone_cli(duration)
                break
            except Exception as exc:
                print(f"[!] Erreur d'enregistrement: {exc}")
        elif choice == "2":
            path_str = input("Chemin du fichier audio/vidéo > ").strip().strip('"').strip("'")
            p = Path(path_str).expanduser()
            if not p.is_file():
                print(f"[!] Fichier introuvable: {p}")
                continue
            try:
                sample_file = normalize_sample_to_wav(p)
                print(f"[✓] Échantillon converti et chargé: {sample_file.name}")
                break
            except Exception as exc:
                print(f"[!] Erreur de lecture: {exc}")
        elif choice == "3":
            tree = get_tree_summary()
            profils = tree.get("profils", [])
            if not profils:
                print("[!] Aucun profil existant trouvé dans profils/. Veuillez enregistrer un échantillon.")
                continue
            print("\nProfils enregistrés :")
            for idx, pr in enumerate(profils, 1):
                print(f"  {idx}) {pr['name']} ({pr['slug']}) - {pr['duration_s']:.1f}s")
            idx_choice = input(f"Numéro du profil [1-{len(profils)}] > ").strip()
            if idx_choice.isdigit() and 1 <= int(idx_choice) <= len(profils):
                chosen = profils[int(idx_choice) - 1]
                sample_file = Path(chosen["reference"])
                break
            else:
                print("[!] Choix invalide.")
        else:
            print("[!] Option inconnue.")

    if not sample_file or not sample_file.is_file():
        print("[!] Aucun échantillon disponible.")
        return 1

    # Étape 2 : Réécoute et Validation
    print("\n[ÉTAPE 2/4] Validation et Réécoute de l'échantillon")
    quality = analyze_sample(sample_file)
    dur = quality.get("duration_s", 0.0)
    snr = quality.get("estimated_snr_db", 0.0)
    score = quality.get("quality_score", 0.0)
    print(f"  • Durée mesurée   : {dur:.2f} s")
    print(f"  • Rapport S/B     : {snr:.1f} dB")
    print(f"  • Score Qualité   : {score * 100:.0f} %")

    if not quality.get("ok"):
        print(f"  [!] Attention : anomalies détectées -> {quality.get('failures')}")

    while True:
        print("\nActions possibles pour l'échantillon :")
        print("  [A] Accepter cet échantillon")
        print("  [R] Ré-écouter l'échantillon")
        print("  [N] Nouvel enregistrement")
        print("  [Q] Quitter")
        act = input("Action [A/R/N/Q] > ").strip().lower()
        if act == "a" or act == "":
            print("[✓] Échantillon validé.")
            break
        elif act == "r":
            print("[▶] Lecture de l'échantillon...")
            play_audio_cli(sample_file)
        elif act == "n":
            sample_file = record_microphone_cli(5)
            quality = analyze_sample(sample_file)
        elif act in ("q", "quit"):
            print("Annulé.")
            return 0

    # Étape 3 : Saisie du texte / chanson à faire dire
    print("\n[ÉTAPE 3/4] Que voulez-vous faire dire ou chanter à cette voix répliquée ?")
    print("  Exemples : un dialogue, une chanson, un poème, un message d'accueil...")
    text = input("Texte / paroles > ").strip()
    while not text:
        text = input("Texte requis > ").strip()

    # Étape 4 : Sauvegarde permanente et nom
    print("\n[ÉTAPE 4/4] Sauvegarde et Paramétrage du profil")
    save_perm_str = input("Enregistrer cette voix pour toujours dans vos profils ? [O/n] > ").strip().lower()
    save_permanent = save_perm_str not in ("n", "non", "no")

    voice_name = "Voix Répliquée"
    if save_permanent:
        name_input = input("Nom pour cet échantillon / profil vocal (ex: Jean Dupont, Narrateur) > ").strip()
        if name_input:
            voice_name = name_input
    else:
        name_input = input("Nom indicatif de la session [défaut: Voix Temporaire] > ").strip()
        if name_input:
            voice_name = name_input

    # Exécution de la réplication
    print("\n[•] Lancement de la réplication vocale en cours...")
    res = replicate_voice(
        sample_path=sample_file,
        text=text,
        name=voice_name,
        save_permanent=save_permanent,
        lang="fr",
    )

    if not res.get("ok"):
        print(f"\n[x] Erreur lors de la réplication: {res.get('error')}")
        return 1

    wav_out = res.get("wav")
    print("\n" + "=" * 66)
    print("  [✓] RÉPLICATION VOCALE TERMINÉE AVEC SUCCÈS !")
    print("=" * 66)
    print(f"  • Nom de la voix     : {res.get('name')}")
    print(f"  • Fichier audio généré: {wav_out}")
    print(f"  • Durée audio        : {res.get('duration_s', 0.0):.2f} s")
    print(f"  • Moteur utilisé     : {res.get('engine')}")
    print(f"  • Sauvegarde profil  : {'Oui (Permanent)' if res.get('is_permanent') else 'Non (Session temporaire)'}")
    print("-" * 66)

    # Proposer la lecture immédiate
    play_now = input("Écouter le rendu audio maintenant ? [O/n] > ").strip().lower()
    if play_now not in ("n", "non", "no") and wav_out:
        play_audio_cli(wav_out)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Studio de réplication de voix par échantillon")
    parser.add_argument("--interactive", action="store_true", help="Lance l'assistant interactif pas-à-pas")
    parser.add_argument("--sample", help="Chemin du fichier audio ou vidéo source")
    parser.add_argument("--record", type=int, help="Enregistre N secondes depuis le microphone")
    parser.add_argument("--listen-preview", action="store_true", help="Joue l'échantillon pour réécoute avant synthèse")
    parser.add_argument("--text", help="Texte ou paroles à faire dire à la voix répliquée")
    parser.add_argument("--name", default="Voix Répliquée", help="Nom du profil ou de l'échantillon")
    parser.add_argument("--permanent", dest="permanent", action="store_true", default=True, help="Enregistre le profil de façon permanente")
    parser.add_argument("--temporary", dest="permanent", action="store_false", help="Génération temporaire (non enregistrée dans les profils)")
    parser.add_argument("--lang", default="fr", help="Langue de synthèse (fr ou en)")
    parser.add_argument("--prompt-text", default="", help="Transcription de l'échantillon pour guidage du clonage")
    parser.add_argument("--instruction", default="", help="Instruction de prosodie ou d'émotion")
    parser.add_argument("--list-profiles", action="store_true", help="Liste tous les profils de voix enregistrés")
    parser.add_argument("--tree", action="store_true", help="Affiche l'arborescence application/output/voix")
    parser.add_argument("--json", action="store_true", help="Format de sortie JSON")

    args = parser.parse_args()

    if args.tree or (len(sys.argv) == 2 and sys.argv[1] == "--tree"):
        summary = get_tree_summary()
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(f"\nArborescence : {summary['root']}")
            print(f"├── echantillons/  ({summary['counts']['echantillons']} fichiers)")
            print(f"├── profils/       ({summary['counts']['profils']} profils)")
            for p in summary['profils']:
                print(f"│   └── {p['slug']}/ (réf: {p['name']}, {p['duration_s']:.1f}s)")
            print(f"├── generations/   ({summary['counts']['generations']} fichiers)")
            print(f"└── sessions/      ({summary['counts']['sessions']} fichiers)\n")
        sys.exit(0)

    if args.list_profiles:
        summary = get_tree_summary()
        profils = summary.get("profils", [])
        if args.json:
            print(json.dumps({"ok": True, "profils": profils}, indent=2, ensure_ascii=False))
        else:
            print(f"\nProfils de voix enregistrés ({len(profils)}) :")
            for p in profils:
                print(f"  • {p['name']} [{p['slug']}] - {p['duration_s']:.1f}s - score: {p['quality_score']}")
            print()
        sys.exit(0)

    # Si aucun argument ou --interactive -> Assistant interactif
    if len(sys.argv) == 1 or args.interactive:
        sys.exit(interactive_cli_wizard())

    # Mode scripté / CLI direct
    sample_path: Path | None = None
    if args.record:
        sample_path = record_microphone_cli(args.record)
    elif args.sample:
        sample_path = Path(args.sample)

    if not sample_path or not sample_path.is_file():
        if args.json:
            print(json.dumps({"ok": False, "error": "--sample ou --record requis"}))
        else:
            print("[!] Veuillez fournir --sample <fichier> ou --record <secondes>.")
        sys.exit(1)

    if args.listen_preview:
        print("[▶] Réécoute de l'échantillon...")
        play_audio_cli(sample_path)

    if not args.text:
        if args.json:
            print(json.dumps({"ok": False, "error": "--text requis pour la synthèse"}))
        else:
            print("[!] Veuillez fournir --text \"...\" pour la synthèse.")
        sys.exit(1)

    result = replicate_voice(
        sample_path=sample_path,
        text=args.text,
        name=args.name,
        save_permanent=args.permanent,
        lang=args.lang,
        prompt_text=args.prompt_text,
        instruction=args.instruction,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok"):
            print(f"[✓] Réplication réussie : {result.get('wav')}")
        else:
            print(f"[x] Erreur : {result.get('error')}")

    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
