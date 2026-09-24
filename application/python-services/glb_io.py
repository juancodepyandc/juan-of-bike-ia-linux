"""Lecture/ecriture bas niveau d'un GLB: accesseurs numpy, sans dependance lourde."""
import json, struct
import os
import tempfile
import numpy as np
from pathlib import Path

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def load(path):
    d = Path(path).read_bytes()
    if len(d) < 20 or d[:4] != b"glTF":
        raise ValueError("Invalid GLB header")
    version, declared_size = struct.unpack_from("<II", d, 4)
    if version != 2 or declared_size != len(d):
        raise ValueError("Truncated GLB or unsupported version")
    off, chunks = 12, {}
    while off < len(d):
        if off + 8 > len(d):
            raise ValueError("Truncated GLB chunk header")
        ln, ty = struct.unpack_from("<II", d, off)
        if ln % 4 or off + 8 + ln > len(d) or ty in chunks:
            raise ValueError("Invalid GLB chunk length or duplicate chunk")
        chunks[ty] = d[off+8:off+8+ln]
        off += 8 + ln
    if 0x4E4F534A not in chunks or 0x004E4942 not in chunks:
        raise ValueError("GLB is missing its JSON or binary data")
    j = json.loads(chunks[0x4E4F534A])
    blob = chunks[0x004E4942]
    for buffer in j.get("buffers", []):
        if not buffer.get("uri") and buffer.get("byteLength", 0) > len(blob):
            raise ValueError("GLB binary buffer is truncated")
    for view in j.get("bufferViews", []):
        start, length = view.get("byteOffset", 0), view.get("byteLength", 0)
        if view.get("buffer", 0) == 0 and (start < 0 or length < 0 or start + length > len(blob)):
            raise ValueError("GLB buffer view exceeds binary data")
    return j, blob

def accessor(j, blob, idx):
    a = j["accessors"][idx]
    n, dt = NC[a["type"]], CT[a["componentType"]]
    bv = j["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * np.dtype(dt).itemsize
    count = a["count"]
    if stride == n * np.dtype(dt).itemsize:
        arr = np.frombuffer(blob, dtype=dt, count=count*n, offset=start).reshape(count, n)
    else:
        raw = np.frombuffer(blob, dtype=np.uint8, count=stride*count, offset=start).reshape(count, stride)
        arr = raw[:, :n*np.dtype(dt).itemsize].copy().view(dt).reshape(count, n)
    return arr

def image_bytes(j, blob, image_index):
    bv = j["bufferViews"][j["images"][image_index]["bufferView"]]
    o = bv.get("byteOffset", 0)
    return blob[o:o+bv["byteLength"]]

def save(path, j, blob):
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    padding = b"\0" * ((4 - len(blob) % 4) % 4)
    size = 12 + 8 + len(js) + 8 + len(blob) + len(padding)
    target = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as writer:
            writer.write(b"glTF" + struct.pack("<II", 2, size))
            writer.write(struct.pack("<II", len(js), 0x4E4F534A))
            writer.write(js)
            writer.write(struct.pack("<II", len(blob) + len(padding), 0x004E4942))
            writer.write(blob)
            writer.write(padding)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return size
