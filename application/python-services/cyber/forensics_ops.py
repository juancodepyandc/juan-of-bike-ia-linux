"""Forensics ops: file hash, strings, magic bytes, EXIF, entropy, memory scan."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _safety import safe_read_bytes, validate_read_file  # noqa: E402


REQUIRED = {"PIL": "Pillow", "exifread": "exifread"}


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


MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"GIF87a", "GIF image"),
    (b"GIF89a", "GIF image"),
    (b"%PDF-", "PDF document"),
    (b"PK\x03\x04", "ZIP / Office / JAR"),
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "PE/EXE executable"),
    (b"Rar!\x1a\x07", "RAR archive"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip archive"),
    (b"\x1f\x8b", "GZIP archive"),
    (b"RIFF", "RIFF (WAV/AVI)"),
    (b"ID3", "MP3 with ID3"),
    (b"OggS", "Ogg container"),
    (b"ftyp", "MP4/ISO BMFF (offset 4)"),
]


def magic_detect(path: str) -> dict:
    p = validate_read_file(path)
    with p.open("rb") as f:
        data = f.read(64)
    hits: list[str] = []
    for sig, name in MAGIC:
        if data.startswith(sig) or (len(data) > 4 and data[4:4 + len(sig)] == sig):
            hits.append(name)
    return {"path": str(p), "first_bytes_hex": data[:16].hex(), "matches": hits or ["unknown"]}


def file_hashes(path: str) -> dict:
    p = validate_read_file(path)
    md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
    size = 0
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            md5.update(chunk); sha1.update(chunk); sha256.update(chunk)
            size += len(chunk)
    return {
        "path": str(p), "size": size,
        "md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest(),
    }


def extract_strings(path: str, min_len: int = 4, limit: int = 2000) -> dict:
    p = validate_read_file(path)
    data = safe_read_bytes(p)
    ascii_re = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    utf16_re = re.compile(
        rb"(?:[\x20-\x7e]\x00){%d,}" % min_len,
    )
    ascii_matches = [
        {"offset": m.start(), "value": m.group(0).decode("ascii", errors="replace"), "encoding": "ascii"}
        for m in ascii_re.finditer(data)
    ]
    utf16_matches = [
        {"offset": m.start(), "value": m.group(0).decode("utf-16-le", errors="replace"), "encoding": "utf16le"}
        for m in utf16_re.finditer(data)
    ]
    merged = sorted(ascii_matches + utf16_matches, key=lambda item: item["offset"])
    return {
        "path": str(p),
        "strings": merged[:limit],
        "ascii": [s["value"] for s in ascii_matches[:limit]],
        "utf16": [s["value"] for s in utf16_matches[:limit]],
        "ascii_count": len(ascii_matches),
        "utf16_count": len(utf16_matches),
        "total_count": len(merged),
    }


def exif_extract(path: str) -> dict:
    from PIL import Image, ExifTags
    import exifread

    p = validate_read_file(path)
    result: dict = {"path": str(p), "pillow": {}, "exifread": {}}

    try:
        img = Image.open(p)
        raw = img._getexif() or {}
        for tag, val in raw.items():
            name = ExifTags.TAGS.get(tag, str(tag))
            try:
                result["pillow"][name] = str(val)
            except Exception:  # noqa: BLE001
                result["pillow"][name] = "<unserializable>"
        result["size"] = img.size
        result["format"] = img.format
        result["mode"] = img.mode
    except Exception as exc:  # noqa: BLE001
        result["pillow_error"] = str(exc)

    try:
        with p.open("rb") as f:
            tags = exifread.process_file(f, details=False)
        for k, v in tags.items():
            result["exifread"][k] = str(v)
    except Exception as exc:  # noqa: BLE001
        result["exifread_error"] = str(exc)

    return result


def _entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = [0] * 256
    for b in chunk:
        counts[b] += 1
    e = 0.0
    length = len(chunk)
    for c in counts:
        if c:
            p = c / length
            e -= p * math.log2(p)
    return e


def entropy_analysis(path: str, block: int = 65536) -> dict:
    p = validate_read_file(path)
    data = safe_read_bytes(p)
    block_values: list[float] = []
    block_rows: list[dict] = []
    for i in range(0, len(data), block):
        chunk = data[i:i + block]
        if not chunk:
            continue
        e = round(_entropy(chunk), 4)
        block_values.append(e)
        block_rows.append({"offset": i, "entropy": e, "size": len(chunk)})
    avg = sum(block_values) / len(block_values) if block_values else 0
    global_entropy = round(_entropy(data), 4) if data else 0
    return {
        "path": str(p),
        "global": global_entropy,
        "block_size": block,
        "num_blocks": len(block_rows),
        "blocks": block_rows[:512],
        "block_values": block_values[:512],
        "avg_entropy": round(avg, 4),
        "max_entropy": max(block_values) if block_values else 0,
        "min_entropy": min(block_values) if block_values else 0,
    }


def memory_scan(path: str) -> dict:
    p = validate_read_file(path)
    data = safe_read_bytes(p)
    url_re = re.compile(rb"https?://[\w\-\.:/?#&=%]+")
    ip_re = re.compile(rb"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    email_re = re.compile(rb"[\w\.\-]+@[\w\.\-]+\.[A-Za-z]{2,}")
    pw_hints = [b"password=", b"passwd=", b"pwd=", b"api_key=", b"secret=", b"token="]

    matches: list[dict] = []
    urls: list[str] = []
    ips: list[str] = []
    emails: list[str] = []
    for label, rx, bucket in [
        ("url", url_re, urls),
        ("ip", ip_re, ips),
        ("email", email_re, emails),
    ]:
        seen: set[str] = set()
        for m in rx.finditer(data):
            value = m.group(0).decode("ascii", "replace")
            if value not in seen:
                seen.add(value)
                bucket.append(value)
                matches.append({"offset": m.start(), "pattern": label, "value": value})
    suspicious: list[str] = []
    lower = data.lower()
    for h in pw_hints:
        idx = 0
        while True:
            idx = lower.find(h, idx)
            if idx < 0:
                break
            value = data[idx:idx + 64].decode("utf-8", "replace")
            suspicious.append(value)
            matches.append({"offset": idx, "pattern": h.decode("ascii", "replace").rstrip("="), "value": value})
            idx += 1
    return {
        "path": str(p),
        "matches": sorted(matches, key=lambda item: item["offset"])[:500],
        "urls": urls[:200],
        "ips": ips[:200],
        "emails": emails[:200],
        "credential_hints": suspicious[:100],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ["magic", "hash", "strings", "exif", "entropy", "memscan"]:
        p = sub.add_parser(name)
        p.add_argument("path")
    args = parser.parse_args()
    try:
        out = {
            "magic": magic_detect,
            "hash": file_hashes,
            "strings": extract_strings,
            "exif": exif_extract,
            "entropy": entropy_analysis,
            "memscan": memory_scan,
        }[args.cmd](args.path)
        print(json.dumps(out, default=str, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
