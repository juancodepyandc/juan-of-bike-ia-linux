"""Lecture/ecriture bas niveau d'un GLB: accesseurs numpy, sans dependance lourde."""
import json, struct
import numpy as np
from pathlib import Path

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def load(path):
    d = Path(path).read_bytes()
    assert d[:4] == b"glTF"
    off, chunks = 12, {}
    while off < len(d):
        ln, ty = struct.unpack("<II", d[off:off+8])
        chunks[ty] = d[off+8:off+8+ln]
        off += 8 + ln
    j = json.loads(chunks[0x4E4F534A])
    return j, chunks[0x004E4942]

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
    bl = blob + b"\0" * ((4 - len(blob) % 4) % 4)
    out = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(bl))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bl), 0x004E4942) + bl
    Path(path).write_bytes(out)
    return len(out)
