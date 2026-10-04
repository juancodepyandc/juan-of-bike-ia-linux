"""Durable mission state shared by the bridge and daemon, without model dependencies."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

TERMINAL = frozenset({"completed", "failed", "stopped", "blocked"})


def database_path() -> Path:
    if os.environ.get("AURORA_MISSION_DB"):
        return Path(os.environ["AURORA_MISSION_DB"]).expanduser()
    from .context import data_dir
    return data_dir() / "missions.sqlite3"


class MissionStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, finished REAL, owner TEXT, lease REAL,
                    idem TEXT UNIQUE, fingerprint TEXT NOT NULL, result TEXT,
                    steps INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
                    files INTEGER NOT NULL DEFAULT 0, replay_from INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    mission TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL, uid TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(mission, seq), UNIQUE(mission, uid)
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    mission TEXT PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
                    payload TEXT NOT NULL, updated REAL NOT NULL
                );
            """)
            if 'replay_from' not in {row['name'] for row in db.execute('PRAGMA table_info(missions)')}:
                db.execute('ALTER TABLE missions ADD COLUMN replay_from INTEGER NOT NULL DEFAULT 0')
        if os.name != "nt":
            self.path.chmod(0o600)

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def create(self, payload: dict, idempotency_key: str = "") -> tuple[dict, bool]:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        fingerprint_data = {key: value for key,value in payload.items() if key != 'history'}
        if 'requested_model' in fingerprint_data:
            fingerprint_data['model'] = fingerprint_data['requested_model']
        fingerprint = hashlib.sha256(json.dumps(fingerprint_data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        now = time.time()
        with self.connect(write=True) as db:
            if idempotency_key:
                old = db.execute("SELECT id,fingerprint FROM missions WHERE idem=?", (idempotency_key,)).fetchone()
                if old:
                    if old["fingerprint"] != fingerprint:
                        raise ValueError("Idempotency key was already used for a different request")
                    return self._get(db, old["id"]), False
            mid = "mis_" + uuid4().hex[:16]
            db.execute("INSERT INTO missions(id,payload,status,created,idem,fingerprint) VALUES(?,?,?,?,?,?)",
                       (mid, canonical, "planning", now, idempotency_key or None, fingerprint))
            return self._get(db, mid), True

    def _get(self, db, mid):
        row = db.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        item["last_event_id"] = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE mission=?", (mid,)).fetchone()[0]
        if item["status"] in {"running", "stopping"} and (item["lease"] or 0) < time.time():
            item["status"] = "interrupted"
        if item["status"] == "planning" and time.time() - item["created"] > 30:
            item["status"] = "interrupted"
        return item

    def get(self, mid):
        with self.connect() as db:
            return self._get(db, mid)

    def list(self, limit=50):
        with self.connect() as db:
            ids = db.execute("SELECT id FROM missions ORDER BY created DESC LIMIT ?", (min(max(int(limit), 1), 200),)).fetchall()
            return [self._get(db, row[0]) for row in ids]

    def append(self, mid: str, event: dict) -> int | None:
        event = dict(event)
        event.setdefault("event_id", uuid4().hex)
        event.setdefault("ts", time.time())
        with self.connect(write=True) as db:
            mission = db.execute("SELECT status,owner,lease FROM missions WHERE id=?", (mid,)).fetchone()
            if mission is None:
                return None
            if event.get('lease_owner') and (event['lease_owner'] != mission['owner'] or (mission['lease'] or 0) < time.time()):
                return None
            existing = db.execute("SELECT seq FROM events WHERE mission=? AND uid=?", (mid, event["event_id"])).fetchone()
            if existing:
                return existing[0]
            if mission["status"] in TERMINAL:
                return None
            seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE mission=?", (mid,)).fetchone()[0]
            db.execute("INSERT INTO events VALUES(?,?,?,?)", (mid, seq, event["event_id"], json.dumps(event, ensure_ascii=False)))
            kind = event.get("type")
            if kind in {"error", "mission_complete"}:
                status = ("failed" if kind == "error" else "stopped" if event.get("stopped") else
                          "blocked" if event.get("status") == "blocked" else "completed")
                result = event.get("result", event.get("message", event.get("error", "")))
                db.execute("UPDATE missions SET status=?,finished=?,result=?,owner=NULL,lease=NULL,errors=errors+? WHERE id=?",
                           (status, time.time(), str(result), int(kind == "error"), mid))
            else:
                db.execute("UPDATE missions SET steps=steps+?, files=files+? WHERE id=?",
                           (int(kind == "step_start"), int(kind == "file_transfer"), mid))
            return seq

    def events(self, mid, after=0, limit=256):
        with self.connect() as db:
            return [(row[0], json.loads(row[1])) for row in db.execute(
                "SELECT seq,payload FROM events WHERE mission=? AND seq>? ORDER BY seq LIMIT ?",
                (mid, after, limit)).fetchall()]

    def claim(self, mid: str, owner: str, seconds=45) -> bool:
        with self.connect(write=True) as db:
            mission = self._get(db, mid)
            if not mission or mission["status"] in TERMINAL or ((mission["lease"] or 0) > time.time()):
                return False
            db.execute("UPDATE missions SET owner=?,lease=?,status='running' WHERE id=?", (owner, time.time()+seconds, mid))
            return True

    def renew(self, mid, owner, seconds=45):
        with self.connect(write=True) as db:
            now = time.time()
            return db.execute("UPDATE missions SET lease=? WHERE id=? AND owner=? AND lease>? AND status NOT IN ('completed','failed','stopped','blocked')",
                              (now+seconds, mid, owner, now)).rowcount == 1

    def resume(self, mid, model=None):
        with self.connect(write=True) as db:
            item = self._get(db, mid)
            if not item:
                raise KeyError(mid)
            if item["status"] not in {"failed", "stopped", "blocked", "interrupted"}:
                raise ValueError("Only interrupted, stopped, blocked or failed missions can resume")
            cursor = item["last_event_id"]
            if model:
                item['payload']['model'] = model
                db.execute('UPDATE missions SET payload=? WHERE id=?',
                           (json.dumps(item['payload'],ensure_ascii=False),mid))
            db.execute("UPDATE missions SET status='planning',created=?,finished=NULL,result=NULL,owner=NULL,lease=NULL,replay_from=? WHERE id=?",
                       (time.time(), cursor, mid))
            return item, cursor

    def stop_requested(self, mid):
        with self.connect(write=True) as db:
            db.execute("UPDATE missions SET status='stopping' WHERE id=? AND status NOT IN ('completed','failed','stopped','blocked')", (mid,))

    def save_checkpoint(self, mid, state, owner=None):
        with self.connect(write=True) as db:
            if owner:
                row = db.execute('SELECT owner,lease FROM missions WHERE id=?',(mid,)).fetchone()
                if not row or row['owner'] != owner or (row['lease'] or 0) < time.time():
                    return False
            db.execute("INSERT INTO checkpoints VALUES(?,?,?) ON CONFLICT(mission) DO UPDATE SET payload=excluded.payload,updated=excluded.updated",
                       (mid, json.dumps(state, ensure_ascii=False), time.time()))
            return True

    def checkpoint(self, mid):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM checkpoints WHERE mission=?", (mid,)).fetchone()
            return json.loads(row[0]) if row else None

    def prune(self, age_seconds):
        with self.connect(write=True) as db:
            return db.execute("DELETE FROM missions WHERE finished<?", (time.time()-age_seconds,)).rowcount
