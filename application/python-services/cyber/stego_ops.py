"""Steganography: LSB image (PNG) + audio (WAV), whitespace + zero-width text."""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _safety import (  # noqa: E402
    safe_read_text,
    validate_output_path,
    validate_read_file,
    validate_text_payload,
)


REQUIRED = {"PIL": "Pillow", "numpy": "numpy"}


def ensure_deps() -> None:
    missing = []
    for imp, pip in REQUIRED.items():
        try:
            __import__(imp)
        except ImportError:
            missing.append(pip)
    if missing:
        print(f"PROGRESS:install:Installing {', '.join(missing)}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing],
            stdout=subprocess.DEVNULL,
        )


ensure_deps()


MAGIC = b"AURORASTEG\x01"


def _bytes_to_bits(data: bytes) -> list[int]:
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)


# --- Image LSB --------------------------------------------------------------

def image_encode(cover: str, secret: str, out_path: str) -> dict:
    from PIL import Image
    import numpy as np

    cover_path = validate_read_file(cover)
    out = validate_output_path(out_path)
    secret = validate_text_payload("secret", secret)

    img = Image.open(cover_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1, 4)[:, :3].flatten()  # RGB only, skip alpha

    payload = MAGIC + len(secret.encode()).to_bytes(4, "big") + secret.encode()
    bits = _bytes_to_bits(payload)
    if len(bits) > flat.size:
        raise ValueError(f"Cover too small: need {len(bits)} bits, have {flat.size}")

    flat_mod = flat.copy()
    flat_mod[:len(bits)] = (flat[:len(bits)] & 0xFE) | np.array(bits, dtype=np.uint8)

    arr2 = arr.copy()
    rgb = arr2.reshape(-1, 4)
    rgb[:, :3] = flat_mod.reshape(-1, 3)
    Image.fromarray(rgb.reshape(arr.shape), "RGBA").save(out, "PNG")
    return {"out": str(out), "payload_bytes": len(payload), "capacity_bytes": flat.size // 8}


def image_decode(stego: str) -> dict:
    from PIL import Image
    import numpy as np

    stego_path = validate_read_file(stego)
    img = Image.open(stego_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1, 4)[:, :3].flatten()
    header_bits = (len(MAGIC) + 4) * 8
    header = _bits_to_bytes([int(b) & 1 for b in flat[:header_bits]])
    if not header.startswith(MAGIC):
        return {"error": "No AuroraSteg magic found"}
    length = int.from_bytes(header[len(MAGIC):len(MAGIC) + 4], "big")
    total_bits = (len(MAGIC) + 4 + length) * 8
    data = _bits_to_bytes([int(b) & 1 for b in flat[:total_bits]])
    secret = data[len(MAGIC) + 4:].decode("utf-8", errors="replace")
    return {"secret": secret, "length": length}


def image_diff(cover: str, stego: str, out_path: str) -> dict:
    from PIL import Image
    import numpy as np

    cover_path = validate_read_file(cover)
    stego_path = validate_read_file(stego)
    out = validate_output_path(out_path)

    a = np.array(Image.open(cover_path).convert("RGB"), dtype=np.int16)
    b = np.array(Image.open(stego_path).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return {"error": "shapes differ"}
    diff = np.any(a != b, axis=2)
    heat = np.zeros_like(a, dtype=np.uint8)
    heat[..., 0] = diff.astype(np.uint8) * 255  # red where differs
    Image.fromarray(heat, "RGB").save(out, "PNG")
    changed = int(diff.sum())
    total = int(diff.size)
    return {"out": str(out), "changed_pixels": changed, "total_pixels": total, "ratio": changed / total}


# --- Audio LSB --------------------------------------------------------------

def audio_encode(cover_wav: str, secret: str, out_path: str) -> dict:
    import numpy as np

    cover_path = validate_read_file(cover_wav)
    out = validate_output_path(out_path)
    secret = validate_text_payload("secret", secret)

    with wave.open(str(cover_path), "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    if params.sampwidth != 2:
        raise ValueError("Only 16-bit PCM WAV supported")
    samples = np.frombuffer(frames, dtype=np.int16).copy()

    payload = MAGIC + len(secret.encode()).to_bytes(4, "big") + secret.encode()
    bits = _bytes_to_bits(payload)
    if len(bits) > samples.size:
        raise ValueError("Cover audio too short")
    samples[:len(bits)] = (samples[:len(bits)] & ~1) | np.array(bits, dtype=np.int16)

    with wave.open(str(out), "wb") as w:
        w.setparams(params)
        w.writeframes(samples.tobytes())
    return {"out": str(out), "payload_bytes": len(payload)}


def audio_decode(stego_wav: str) -> dict:
    import numpy as np

    stego_path = validate_read_file(stego_wav)
    with wave.open(str(stego_path), "rb") as w:
        frames = w.readframes(w.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16)
    header_bits = (len(MAGIC) + 4) * 8
    header = _bits_to_bytes([int(s) & 1 for s in samples[:header_bits]])
    if not header.startswith(MAGIC):
        return {"error": "No magic"}
    length = int.from_bytes(header[len(MAGIC):len(MAGIC) + 4], "big")
    total_bits = (len(MAGIC) + 4 + length) * 8
    data = _bits_to_bytes([int(s) & 1 for s in samples[:total_bits]])
    return {"secret": data[len(MAGIC) + 4:].decode("utf-8", "replace"), "length": length}


# --- LSB statistical detector ------------------------------------------------

def lsb_stats(path: str) -> dict:
    from PIL import Image
    import numpy as np

    p = validate_read_file(path)
    arr = np.array(Image.open(p).convert("RGB"), dtype=np.uint8).flatten()
    lsbs = arr & 1
    total = lsbs.size
    ones = int(lsbs.sum())
    zeros = total - ones
    ratio = ones / total if total else 0
    chi = abs(ratio - 0.5) * 2  # 0 = perfectly even (suspicious), 1 = skewed
    return {
        "total": total, "ones": ones, "zeros": zeros,
        "ratio_ones": round(ratio, 6),
        "lsb_balance_score": round(chi, 6),
        "verdict": "suspicious (LSB payload likely)" if chi < 0.01 else "normal",
    }


# --- Whitespace text steganography (trailing spaces/tabs) -------------------

def whitespace_encode(cover_text: str, secret: str) -> str:
    secret = validate_text_payload("secret", secret)
    payload = MAGIC + len(secret.encode()).to_bytes(4, "big") + secret.encode()
    bits = _bytes_to_bits(payload)
    lines = cover_text.split("\n")
    if len(bits) > len(lines):
        # Pad cover with empty lines if needed
        lines += [""] * (len(bits) - len(lines))
    out = []
    for i, ln in enumerate(lines):
        if i < len(bits):
            ln = ln.rstrip() + (" \t" if bits[i] else "\t ")
        out.append(ln)
    return "\n".join(out)


def whitespace_decode(stego_text: str) -> dict:
    bits: list[int] = []
    for ln in stego_text.split("\n"):
        # trailing whitespace pattern
        tail = ""
        for c in reversed(ln):
            if c in (" ", "\t"):
                tail = c + tail
            else:
                break
        if tail.endswith(" \t"):
            bits.append(1)
        elif tail.endswith("\t "):
            bits.append(0)
    header_bits = (len(MAGIC) + 4) * 8
    if len(bits) < header_bits:
        return {"error": "too short"}
    header = _bits_to_bytes(bits[:header_bits])
    if not header.startswith(MAGIC):
        return {"error": "no magic"}
    length = int.from_bytes(header[len(MAGIC):len(MAGIC) + 4], "big")
    total_bits = (len(MAGIC) + 4 + length) * 8
    data = _bits_to_bytes(bits[:total_bits])
    return {"secret": data[len(MAGIC) + 4:].decode("utf-8", "replace")}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    for cmd in ["img-enc", "img-dec", "img-diff", "aud-enc", "aud-dec", "lsb-stats", "ws-enc", "ws-dec"]:
        p = sub.add_parser(cmd)
        p.add_argument("--cover", default="")
        p.add_argument("--stego", default="")
        p.add_argument("--secret", default="")
        p.add_argument("--out", default="")
        p.add_argument("--text", default="")

    args = parser.parse_args()
    try:
        if args.cmd == "img-enc":
            out = image_encode(args.cover, args.secret, args.out)
        elif args.cmd == "img-dec":
            out = image_decode(args.stego)
        elif args.cmd == "img-diff":
            out = image_diff(args.cover, args.stego, args.out)
        elif args.cmd == "aud-enc":
            out = audio_encode(args.cover, args.secret, args.out)
        elif args.cmd == "aud-dec":
            out = audio_decode(args.stego)
        elif args.cmd == "lsb-stats":
            out = lsb_stats(args.stego or args.cover)
        elif args.cmd == "ws-enc":
            text_in = args.text or safe_read_text(args.cover)
            result = whitespace_encode(text_in, args.secret)
            if args.out:
                out_path = validate_output_path(args.out)
                out_path.write_text(result, encoding="utf-8")
                out = {"out": str(out_path), "bytes": len(result)}
            else:
                out = {"text_b64": base64.b64encode(result.encode()).decode()}
        elif args.cmd == "ws-dec":
            text_in = args.text or safe_read_text(args.stego)
            out = whitespace_decode(text_in)
        else:
            raise SystemExit(2)
        print(json.dumps(out, default=str, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
