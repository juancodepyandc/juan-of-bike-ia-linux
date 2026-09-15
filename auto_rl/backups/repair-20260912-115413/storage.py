from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import time
import uuid
import threading
from pathlib import Path


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(paths):
    """Fingerprint actual local weight/config files, including resolved symlinks.

    Stat identity is recorded for a fast post-run integrity check. Weight SHA256s
    are recorded by the HF content-addressed cache where available.
    """
    entries = {}
    for root in paths:
        root = Path(root)
        for p in ([root] if root.is_file() else sorted(root.rglob("*"))):
            if p.is_file() and p.suffix in {".json", ".safetensors", ".bin", ".pth", ".pt"}:
                real = p.resolve()
                s = real.stat()
                entries[str(p)] = {"resolved": str(real), "size": s.st_size,
                                   "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns,
                                   "inode": s.st_ino,
                                   "content_id": real.name if len(real.name) == 64 else None}
    if not entries:
        raise RuntimeError("Aucun poids local trouvé pour l'empreinte du modèle")
    return entries


def assert_unchanged(manifest):
    for name, entry in manifest.items():
        p = Path(name).resolve()
        s = p.stat()
        if (str(p), s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino) != (
            entry["resolved"], entry["size"], entry["mtime_ns"], entry["ctime_ns"], entry["inode"]
        ):
            raise RuntimeError(f"Le fichier du modèle de base a changé : {name}")


@contextlib.contextmanager
def exclusive_lock(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Un cycle Aurora est déjà actif") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Status:
    def __init__(self, state, run_id, module):
        self.state = Path(state)
        self.run = self.state / "runs" / run_id
        self.data = {"schema": 1, "run_id": run_id, "module": module,
                     "pid": os.getpid(), "progress_percent": 0, "waiting_validation": False,
                     "loss": None, "judge_score": None, "improvement": None}
        self.lock = threading.RLock()

    def update(self, phase, message, **fields):
        with self.lock:
            self.data.update(phase=phase, status=message, updated_at=time.time(), **fields)
            self.flush()
            with (self.run / "events.jsonl").open("a") as f:
                f.write(json.dumps(self.data, ensure_ascii=False, allow_nan=False) + "\n")
        if os.environ.get("AURORA_KAGGLE_WORKER") == "1":
            print("AURORA_STATUS " + json.dumps({k: self.data.get(k) for k in
                ("phase", "status", "progress_percent", "loss", "judge_score", "epoch", "epochs", "job_id")}), flush=True)
        print(message, flush=True)

    def flush(self, **fields):
        with self.lock:
            self.data.update(fields)
            atomic_json(self.run / "status.json", self.data)
            atomic_json(self.state / "status.json", self.data)


def submit_decision(state, run_id, decision):
    if decision not in {"ACCEPT", "REJECT"}:
        raise ValueError("Décision invalide")
    s = read_json(Path(state) / "status.json", {})
    if s.get("run_id") != run_id or s.get("phase") != "awaiting_validation":
        raise ValueError("Ce cycle n'attend pas de validation")
    if decision == "ACCEPT" and not s.get("eligible"):
        raise ValueError("Ce candidat ne passe pas les contrôles de promotion")
    # A signal lives INSIDE its unique run. JSON binds it to the exact report.
    atomic_json(Path(state) / "runs" / run_id / "validation_signal.txt",
                {"run_id": run_id, "decision": decision, "report_digest": s["report_digest"]})


def promote(state, module, run_id, candidate, report, expected_champion):
    state, candidate = Path(state), Path(candidate).resolve()
    run = (state / "runs" / run_id).resolve()
    if not candidate.is_relative_to(run) or not candidate.is_file():
        raise ValueError("L'adaptateur doit appartenir au cycle validé")
    if not report["gate"]["eligible"]:
        raise ValueError("Promotion refusée par l'audit")
    if file_hash(candidate) != report["candidate_sha256"]:
        raise ValueError("L'adaptateur a changé depuis l'audit")
    path = state / "registry" / f"{module}.json"
    with exclusive_lock(state / "registry.lock"):
        current = read_json(path, {})
        if current.get("run_id") != expected_champion:
            raise ValueError("Le champion a changé depuis le début du cycle")
        record = {"schema": 1, "version": current.get("version", 0) + 1,
                  "name": f"Reinforced_Model_v{current.get('version', 0) + 1}",
                  "run_id": run_id, "adapter": str(candidate),
                  "sha256": report["candidate_sha256"], "report": str(run / "report.json"),
                  "score": report["gate"]["candidate_mean"], "promoted_at": time.time(),
                  "previous": current, "base_fingerprint": report["base_fingerprint"]}
        atomic_json(path, record)
    return record
