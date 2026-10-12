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
            if 'started_at' not in {row['name'] for row in db.execute('PRAGMA table_info(missions)')}:
                db.execute('ALTER TABLE missions ADD COLUMN started_at REAL')
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

    def create(self, payload: dict, idempotency_key: str = "", *, queued=False) -> tuple[dict, bool]:
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
                       (mid, canonical, "queued" if queued else "planning", now, idempotency_key or None, fingerprint))
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

    def enqueue(self, mid):
        with self.connect(write=True) as db:
            return db.execute("UPDATE missions SET status='queued' WHERE id=? AND status IN ('planning','queued') AND owner IS NULL",(mid,)).rowcount==1

    def queued(self,limit=200):
        with self.connect() as db:
            ids=db.execute("SELECT id FROM missions WHERE status='queued' AND json_extract(payload,'$.project_kind') IS NOT 'frontend' ORDER BY created,id LIMIT ?",(limit,)).fetchall()
            return [self._get(db,r['id']) for r in ids]

    def cancel_queued(self,mid):
        with self.connect(write=True) as db:
            changed=db.execute("UPDATE missions SET status='stopped',finished=?,result='Annulé avant démarrage' WHERE id=? AND status='queued' AND owner IS NULL AND started_at IS NULL",(time.time(),mid)).rowcount
            if changed:
                seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE mission=?',(mid,)).fetchone()[0]
                event={'type':'mission_complete','stopped':True,'result':'Annulé avant démarrage','ts':time.time()};uid=uuid4().hex;event['event_id']=uid
                db.execute('INSERT INTO events VALUES(?,?,?,?)',(mid,seq,uid,json.dumps(event)))
            return bool(changed)

    def scheduling(self,mid):
        """Measured history, never an invented estimate of model reasoning."""
        import statistics
        with self.connect() as db:
            item=self._get(db,mid)
            if not item:return {}
            active=[self._get(db,r['id']) for r in db.execute("SELECT id FROM missions WHERE status IN ('queued','running','stopping') ORDER BY created,id")]
            def family(p):
                if p.get('project_kind')=='frontend':return 'frontend:'+p.get('module','unknown')
                return 'engineering' if p.get('project_kind')=='engineering' or 'engineering-design' in p.get('workspace','') else 'mission'
            def estimate(job):
                rows=db.execute("SELECT payload,started_at,finished FROM missions WHERE status='completed' AND started_at IS NOT NULL AND finished>started_at ORDER BY finished DESC LIMIT 100").fetchall()
                durations=[r['finished']-r['started_at'] for r in rows if (lambda p:p.get('model')==job['payload'].get('model') and family(p)==family(job['payload']))(json.loads(r['payload']))][:20]
                if len(durations)<3:return None,len(durations)
                return statistics.median(durations),len(durations)
            own,n=estimate(item);elapsed=max(0,(item['finished'] or time.time())-item['started_at']) if item['started_at'] else 0
            ahead=[j for j in active if j['id']!=mid and (j['status'] in {'running','stopping'} or (j['created'],j['id'])<(item['created'],item['id']))]
            if item['status'] not in {'queued','running','stopping'}:ahead=[]
            waits=[]
            for job in ahead:
                total,_=estimate(job);used=max(0,time.time()-job['started_at']) if job['started_at'] else 0
                waits.append(max(0,total-used) if total is not None and used<total else None)
            return {'queue_position':1+sum(j['status']=='queued' for j in ahead) if item['status']=='queued' else 0,'ahead_count':len(ahead),'elapsed_seconds':elapsed,'wait_seconds':sum(waits) if all(v is not None for v in waits) else None,'estimated_duration_seconds':own,'remaining_seconds':own-elapsed if own is not None and elapsed<own and item['status']=='running' else None,'estimate_sample_count':n,'estimate_basis':'Median of completed same-model/same-family runs; variable project complexity, no guarantee.' if own is not None else 'Insufficient measured comparable runs.'}

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

    def claim(self, mid: str, owner: str, seconds=45, *, serialize=False) -> bool:
        with self.connect(write=True) as db:
            mission = self._get(db, mid)
            if not mission or mission["status"] in TERMINAL or ((mission["lease"] or 0) > time.time()):
                return False
            if serialize:
                capacity=int(os.environ.get('AURORA_CONCURRENT_MISSIONS','1'))
                occupied=db.execute("SELECT COUNT(*) FROM missions WHERE id<>? AND status IN ('running','stopping') AND (lease>? OR json_extract(payload,'$.project_kind')='frontend')",(mid,time.time())).fetchone()[0]
                earlier=db.execute("SELECT COUNT(*) FROM missions WHERE status='queued' AND (created<? OR (created=? AND id<?))",(mission['created'],mission['created'],mid)).fetchone()[0]
                if occupied>=capacity or (capacity==1 and earlier):return False
            db.execute("UPDATE missions SET owner=?,lease=?,status='running',started_at=COALESCE(started_at,?) WHERE id=?", (owner, time.time()+seconds,time.time(), mid))
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
            db.execute("UPDATE missions SET status='planning',created=?,finished=NULL,result=NULL,owner=NULL,lease=NULL,started_at=NULL,replay_from=? WHERE id=?",
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
