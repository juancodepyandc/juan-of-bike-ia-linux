"""MusicGen ambient track generator.

Loads facebook/musicgen-medium from the local HF cache and produces a WAV
file of the requested duration. Used by cinema_pipeline.py when a shot has
no dialogue track but the storyboard wants an ambient music bed.

Usage:
    python musicgen_render.py --prompt "warm cinematic score" \
        --duration 8 --output ambient.wav
"""
import argparse
import json
import sys
import time
from pathlib import Path


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, required=True, help="seconds")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    if args.duration <= 0:
        print(json.dumps({"ok": False, "error": "duration must be > 0"}), flush=True)
        return 2

    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import scipy.io.wavfile
        import numpy as np
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"import failed: {exc}"}), flush=True)
        return 2

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    t0 = time.time()
    emit("loading", "MusicGen-Medium...")
    try:
        processor = AutoProcessor.from_pretrained("facebook/musicgen-medium")
        model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-medium", torch_dtype=dtype
        ).to(device)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"model load failed: {exc}"}), flush=True)
        return 3

    emit("ready", f"loaded in {time.time() - t0:.1f}s")

    # MusicGen produces ~50 audio tokens per second at the default sampling rate.
    # We give a small head/tail margin so the trim later sounds natural.
    pad_seconds = 0.5
    target_seconds = float(args.duration) + pad_seconds
    max_new_tokens = int(50 * target_seconds) + 8

    inputs = processor(text=[args.prompt], padding=True, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    emit("generating", f"~{target_seconds:.1f}s ({max_new_tokens} tokens)")
    with torch.no_grad():
        audio = model.generate(**inputs, do_sample=True, guidance_scale=3.0, max_new_tokens=max_new_tokens)

    # audio shape: (batch, channels, samples). MusicGen-Medium = mono at 32kHz.
    sr = model.config.audio_encoder.sampling_rate
    wav = audio[0, 0].float().cpu().numpy()

    # Trim to exactly the requested duration (fade out last 100ms to avoid pops)
    target_samples = int(args.duration * sr)
    if wav.shape[0] > target_samples:
        wav = wav[:target_samples]
    elif wav.shape[0] < target_samples:
        # Loop or pad with silence so we cover the whole video
        deficit = target_samples - wav.shape[0]
        pad = np.zeros(deficit, dtype=wav.dtype)
        wav = np.concatenate([wav, pad])

    fade_samples = min(int(0.1 * sr), wav.shape[0] // 4)
    if fade_samples > 0:
        fade = np.linspace(1.0, 0.0, fade_samples, dtype=wav.dtype)
        wav[-fade_samples:] = wav[-fade_samples:] * fade

    # Normalize amplitude to ~-3 dB so it sits below dialogue when mixed
    peak = np.max(np.abs(wav)) if wav.size else 0
    if peak > 1e-3:
        wav = (wav / peak) * 0.7

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    scipy.io.wavfile.write(str(out), sr, (wav * 32767).astype(np.int16))

    print(json.dumps({
        "ok": True,
        "output": str(out),
        "duration_s": round(wav.shape[0] / sr, 2),
        "sample_rate": int(sr),
        "elapsed_s": round(time.time() - t0, 1),
    }), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
