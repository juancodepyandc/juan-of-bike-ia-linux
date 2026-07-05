"""
voice_extract.py -- Extraction intelligente de voix depuis YouTube ou fichier importe.

Chaine:
  1. yt-dlp recupere des clips candidats (ou utilise un fichier audio/video importe)
  2. ffmpeg extrait l'audio en mono 16kHz WAV
  3. Demucs separe voix <-> musique (isolation propre de la piste vocale)
  4. SpeechBrain ECAPA-TDNN calcule les embeddings de voix
  5. AgglomerativeClustering identifie les speakers distincts
  6. On selectionne les segments du speaker dominant qui matchent le profil cible
  7. Concatenation -> sample propre de 15-30s contenant UNE seule voix

Usage:
  python voice_extract.py --query "Natsu Fairy Tail VF" --character "natsu" --output ref.wav
  python voice_extract.py --input local_video.mp4 --character "natsu" --output ref.wav
  python voice_extract.py --check

Output JSON sur stdout (derniere ligne):
  {"ok": true, "wav": "ref.wav", "duration_s": 18.4, "confidence": 0.87, "source": "youtube|imported"}
"""

import argparse
import gc
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Compat shims must run BEFORE any torchaudio / speechbrain / TTS import.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _compat  # noqa: F401

WORKSPACE = Path(__file__).resolve().parents[2]
TEMP_DIR = WORKSPACE / "temp" / "voice_extract"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def _ffmpeg_bin() -> str:
    """Use the ffmpeg binary bundled by imageio-ffmpeg. Avoids needing it on PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _run(cmd: list, timeout: int = 600) -> tuple:
    """Run a subprocess, capture stdout/stderr. Returns (returncode, stdout, stderr)."""
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000  # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)


def check_dependencies() -> dict:
    """Verify all dependencies are available. Returns {ok, missing[], details}."""
    missing = []
    details = {}

    try:
        import yt_dlp
        details["yt_dlp"] = yt_dlp.version.__version__
    except Exception as exc:
        missing.append(f"yt-dlp ({exc})")

    try:
        import demucs
        details["demucs"] = "OK"
    except Exception as exc:
        missing.append(f"demucs ({exc})")

    try:
        import speechbrain  # noqa
        details["speechbrain"] = "OK"
    except Exception as exc:
        missing.append(f"speechbrain ({exc})")

    try:
        import torch
        details["torch"] = torch.__version__
        details["cuda"] = torch.cuda.is_available()
    except Exception as exc:
        missing.append(f"torch ({exc})")

    ffmpeg = _ffmpeg_bin()
    if not Path(ffmpeg).exists() and ffmpeg == "ffmpeg":
        missing.append("ffmpeg (no embedded binary, no system ffmpeg)")
    else:
        details["ffmpeg"] = ffmpeg

    return {"ok": len(missing) == 0, "missing": missing, "details": details}


def youtube_search_and_download(query: str, max_videos: int = 4, max_duration_s: int = 600) -> list:
    """Search YouTube for clips matching the query and download up to max_videos.
    Returns a list of local file paths to downloaded media.
    """
    import yt_dlp

    emit("search", f"YouTube: {query}")

    out_dir = TEMP_DIR / "yt_downloads" / hashlib.md5(query.encode()).hexdigest()[:12]
    out_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio[abr<=192]/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "match_filter": lambda info: None if info.get("duration", 0) <= max_duration_s else "too long",
        "ffmpeg_location": _ffmpeg_bin(),
        "default_search": f"ytsearch{max_videos}",
    }

    downloaded = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            entries = info.get("entries", []) if info else []
            for entry in entries:
                if not entry:
                    continue
                fp = ydl.prepare_filename(entry)
                if Path(fp).exists():
                    downloaded.append(fp)
                else:
                    # yt-dlp may have post-processed; find file by id
                    for f in out_dir.glob(f"{entry.get('id', '')}*"):
                        downloaded.append(str(f))
                        break
    except Exception as exc:
        emit("search_error", str(exc)[:120])

    emit("search_done", f"{len(downloaded)} clip(s)")
    return downloaded


def to_mono_16k_wav(input_path: str, output_wav: str) -> bool:
    """Convert any media file to mono 16kHz WAV using ffmpeg."""
    cmd = [
        _ffmpeg_bin(),
        "-y",
        "-i", input_path,
        "-ac", "1",          # mono
        "-ar", "16000",      # 16 kHz (standard for speech models)
        "-vn",               # no video
        "-loglevel", "error",
        output_wav,
    ]
    rc, _, err = _run(cmd, timeout=300)
    if rc != 0:
        emit("ffmpeg_error", err[:160] if err else "unknown")
    return rc == 0 and Path(output_wav).exists()


def demucs_isolate_vocals(wav_path: str, output_dir: str) -> str:
    """Run Demucs to separate vocals from music. Returns path to vocals.wav."""
    emit("demucs", "isolation voix/musique...")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Demucs CLI: htdemucs is the default, faster than mdx_extra. Two stems = vocals + others.
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "--two-stems", "vocals",
        "-o", str(out_dir),
        wav_path,
    ]
    rc, _, err = _run(cmd, timeout=600)
    if rc != 0:
        emit("demucs_error", err[:200] if err else "unknown")
        return ""

    # Demucs writes to {out_dir}/htdemucs/{stem}/vocals.wav
    base = Path(wav_path).stem
    vocals = out_dir / "htdemucs" / base / "vocals.wav"
    if vocals.exists():
        emit("demucs_done", f"voix isolee: {vocals.name}")
        return str(vocals)
    return ""


def detect_speech_segments(wav_path: str, min_duration_s: float = 1.5, max_silence_s: float = 0.4) -> list:
    """Detect speech segments using energy-based VAD (no model needed, robust on isolated vocals).
    Returns [(start_s, end_s), ...] of segments.
    """
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(wav_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Energy threshold: 0.01 * RMS of the loudest 10% of frames
    frame_len = int(0.025 * sr)        # 25 ms frames
    hop = int(0.010 * sr)              # 10 ms hop
    energies = []
    for i in range(0, len(audio) - frame_len, hop):
        e = float(np.sqrt(np.mean(audio[i:i + frame_len] ** 2)))
        energies.append(e)
    energies = np.array(energies)
    if len(energies) == 0:
        return []

    threshold = max(0.005, np.percentile(energies, 60) * 0.4)
    is_speech = energies > threshold

    segments = []
    start = None
    silence_run = 0
    max_silence_frames = int(max_silence_s / 0.010)
    for i, sp in enumerate(is_speech):
        if sp:
            if start is None:
                start = i
            silence_run = 0
        else:
            if start is not None:
                silence_run += 1
                if silence_run >= max_silence_frames:
                    end = i - silence_run
                    duration = (end - start) * 0.010
                    if duration >= min_duration_s:
                        segments.append((start * 0.010, end * 0.010))
                    start = None
                    silence_run = 0
    if start is not None:
        end = len(is_speech)
        duration = (end - start) * 0.010
        if duration >= min_duration_s:
            segments.append((start * 0.010, end * 0.010))

    return segments


def compute_embeddings_for_segments(wav_path: str, segments: list) -> list:
    """Compute SpeechBrain ECAPA-TDNN embeddings for each segment.
    Returns list of (segment_index, embedding_vector). No HF token required.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    emit("embed", f"calcul embeddings ({len(segments)} segments)...")

    cache_dir = WORKSPACE / "temp" / "speechbrain_models"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # speechbrain/spkrec-ecapa-voxceleb is the standard ECAPA-TDNN model.
    # Public, no token needed, ~80MB, downloads automatically on first use.
    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(cache_dir / "ecapa_voxceleb"),
        run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
    )

    audio, sr = sf.read(wav_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # ECAPA expects 16kHz; resample if needed (we already converted earlier but defensive).
    if sr != 16000:
        import librosa
        audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=16000)
        sr = 16000

    embeddings = []
    for idx, (start_s, end_s) in enumerate(segments):
        a = int(start_s * sr)
        b = int(end_s * sr)
        chunk = audio[a:b]
        if len(chunk) < sr * 0.5:  # skip <0.5s
            continue
        tensor = torch.from_numpy(chunk.astype(np.float32)).unsqueeze(0)
        with torch.no_grad():
            emb = classifier.encode_batch(tensor).squeeze().cpu().numpy()
        # L2-normalize for cosine clustering
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        embeddings.append((idx, emb))

    return embeddings


def cluster_speakers(embeddings: list, max_speakers: int = 4) -> dict:
    """Cluster embeddings into speaker groups. Returns {segment_idx: speaker_id}."""
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    if len(embeddings) < 2:
        return {idx: 0 for idx, _ in embeddings}

    matrix = np.stack([e for _, e in embeddings])

    # Auto-determine n_clusters: try 1..max_speakers, pick by silhouette score
    from sklearn.metrics import silhouette_score
    best_n = 1
    best_score = -1.0
    for n in range(2, min(max_speakers, len(embeddings)) + 1):
        try:
            labels = AgglomerativeClustering(n_clusters=n, metric="cosine", linkage="average").fit_predict(matrix)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(matrix, labels, metric="cosine")
            if score > best_score:
                best_score = score
                best_n = n
        except Exception:
            continue

    if best_n == 1:
        return {idx: 0 for idx, _ in embeddings}

    labels = AgglomerativeClustering(n_clusters=best_n, metric="cosine", linkage="average").fit_predict(matrix)
    return {idx: int(label) for (idx, _), label in zip(embeddings, labels)}


def select_dominant_speaker(speaker_map: dict, segments: list) -> tuple:
    """Pick the speaker_id with the most speech time. Returns (speaker_id, total_seconds, confidence)."""
    durations = {}
    for seg_idx, spk in speaker_map.items():
        s, e = segments[seg_idx]
        durations[spk] = durations.get(spk, 0.0) + (e - s)

    if not durations:
        return -1, 0.0, 0.0

    sorted_spk = sorted(durations.items(), key=lambda x: x[1], reverse=True)
    top_spk, top_dur = sorted_spk[0]
    second_dur = sorted_spk[1][1] if len(sorted_spk) > 1 else 0.0
    total = sum(durations.values())
    # Confidence = how dominant the top speaker is
    confidence = top_dur / total if total > 0 else 0.0
    return top_spk, top_dur, confidence


def concatenate_segments(wav_path: str, segments: list, output_wav: str, target_duration_s: float = 25.0) -> bool:
    """Concatenate the provided segments into a single WAV up to target_duration_s. Returns success."""
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(wav_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Pick segments greedily up to target_duration_s, prefer longer segments first
    segs_sorted = sorted(segments, key=lambda s: s[1] - s[0], reverse=True)
    chunks = []
    total = 0.0
    for s, e in segs_sorted:
        d = e - s
        if total + d > target_duration_s + 2.0:
            continue
        chunks.append((s, e))
        total += d
        if total >= target_duration_s:
            break

    if not chunks:
        return False

    # Re-sort chronologically for natural prosody continuity
    chunks.sort(key=lambda c: c[0])

    out = []
    for s, e in chunks:
        a = int(s * sr)
        b = int(e * sr)
        out.append(audio[a:b])
        # Add 100 ms silence between chunks
        out.append(np.zeros(int(0.1 * sr), dtype=audio.dtype))

    final = np.concatenate(out)
    sf.write(output_wav, final, sr)
    return True


def extract_voice(
    sources: list,
    output_wav: str,
    target_duration_s: float = 20.0,
    min_confidence: float = 0.55,
) -> dict:
    """Pipeline complet: liste de fichiers media -> WAV propre d'une seule voix."""
    if not sources:
        return {"ok": False, "error": "no sources provided"}

    work_dir = TEMP_DIR / hashlib.md5(("|".join(sources)).encode()).hexdigest()[:10]
    work_dir.mkdir(parents=True, exist_ok=True)

    best_result = None

    for src in sources:
        try:
            emit("process", f"traitement {Path(src).name}")
            base = Path(src).stem
            mono_wav = work_dir / f"{base}_mono.wav"

            if not to_mono_16k_wav(src, str(mono_wav)):
                continue

            vocals_wav = demucs_isolate_vocals(str(mono_wav), str(work_dir / "demucs"))
            if not vocals_wav:
                continue

            segments = detect_speech_segments(vocals_wav, min_duration_s=1.5)
            if len(segments) < 2:
                emit("skip", f"{base}: <2 segments de parole")
                continue

            emit("vad", f"{len(segments)} segments detectes")

            embeddings = compute_embeddings_for_segments(vocals_wav, segments)
            if len(embeddings) < 2:
                continue

            speaker_map = cluster_speakers(embeddings)
            top_spk, top_dur, confidence = select_dominant_speaker(speaker_map, segments)

            emit("cluster", f"speaker {top_spk}: {top_dur:.1f}s, conf {confidence:.2f}")

            if confidence < min_confidence:
                emit("skip", f"{base}: conf {confidence:.2f} < {min_confidence}")
                continue

            target_segments = [
                segments[seg_idx] for seg_idx, spk in speaker_map.items() if spk == top_spk
            ]
            if not target_segments:
                continue

            ok = concatenate_segments(vocals_wav, target_segments, output_wav, target_duration_s)
            if not ok:
                continue

            result = {
                "ok": True,
                "wav": output_wav,
                "duration_s": min(top_dur, target_duration_s),
                "confidence": confidence,
                "source": src,
                "candidates": len(sources),
            }

            if best_result is None or confidence > best_result["confidence"]:
                best_result = result

            # Stop early if confidence is very high
            if confidence >= 0.85:
                break
        except Exception as exc:
            emit("error", f"{Path(src).name}: {str(exc)[:120]}")
            continue
        finally:
            gc.collect()

    if best_result:
        return best_result
    return {
        "ok": False,
        "error": "Aucun sample propre trouve. Confidence trop basse ou trop de bruit.",
        "candidates": len(sources),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="YouTube search query")
    parser.add_argument("--input", help="Local audio/video file (skips YouTube)")
    parser.add_argument("--character", default="character", help="Character slug for naming")
    parser.add_argument("--output", required=False, help="Output WAV path")
    parser.add_argument("--target-duration", type=float, default=20.0)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--max-videos", type=int, default=4)
    parser.add_argument("--check", action="store_true", help="Check dependencies only")
    args = parser.parse_args()

    if args.check:
        result = check_dependencies()
        print(json.dumps(result), flush=True)
        sys.exit(0 if result["ok"] else 1)

    deps = check_dependencies()
    if not deps["ok"]:
        print(json.dumps({"ok": False, "error": "missing deps", "missing": deps["missing"]}), flush=True)
        sys.exit(1)

    sources = []
    if args.input:
        if Path(args.input).exists():
            sources.append(args.input)
        else:
            print(json.dumps({"ok": False, "error": f"input not found: {args.input}"}), flush=True)
            sys.exit(1)
    elif args.query:
        sources = youtube_search_and_download(args.query, max_videos=args.max_videos)
        if not sources:
            print(json.dumps({"ok": False, "error": "no YouTube results / download failed"}), flush=True)
            sys.exit(1)
    else:
        print(json.dumps({"ok": False, "error": "must provide --query or --input"}), flush=True)
        sys.exit(1)

    output = args.output or str(WORKSPACE / "voices" / "library" / args.character / "reference.wav")
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    result = extract_voice(
        sources,
        output,
        target_duration_s=args.target_duration,
        min_confidence=args.min_confidence,
    )

    print(json.dumps(result), flush=True)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
