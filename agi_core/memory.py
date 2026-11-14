import os
from contextlib import closing
import logging
import uuid
import json
from pathlib import Path
import sqlite3
import re

logger = logging.getLogger("AuroraAGI.Memory")

class OmniscientMemory:
    """Mémoire Vectorielle Globale du Serveur."""
    def __init__(self, db_path: str | None = None):
        from agi_core.context import data_dir
        repo_root = Path(__file__).resolve().parents[1]
        canonical = repo_root / "modele" / "db_vector"
        legacy = repo_root / "db_vector"
        selected = (db_path or os.environ.get("AURORA_MEMORY_DIR")
                    or (canonical if canonical.is_dir() else (legacy if legacy.is_dir() else data_dir() / "brain/vector_memory")))
        self.db_path = str(Path(selected).expanduser())
        self.collection = None
        self.client = None
        self.sqlite_path = Path(self.db_path) / "experiences.sqlite3"
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.sqlite_path)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS experiences (id TEXT PRIMARY KEY, document TEXT NOT NULL)")
        self._init_db()

    def _init_db(self):
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(name="aurora_omniscience")
            logger.info("[MEMORY] Cortex vectoriel ChromaDB activé.")
        except Exception as exc:
            logger.warning("[MEMORY] Recherche vectorielle indisponible (%s). Repli SQLite persistant.", type(exc).__name__)

    async def embed_experience(self, context: str, outcome: str, metadata: dict = None):
        import asyncio
        import time
        doc_id = str(uuid.uuid4())
        payload: dict = {"context": context, "outcome": outcome, "ts": time.time()}
        if metadata:
            payload["metadata"] = metadata
        doc_str = json.dumps(payload, ensure_ascii=False)
        
        def _add():
            with closing(sqlite3.connect(self.sqlite_path)) as connection, connection:
                connection.execute("INSERT INTO experiences VALUES (?, ?)", (doc_id, doc_str))
            if self.collection is not None:
                options = {"documents": [doc_str], "ids": [doc_id]}
                if metadata:
                    options["metadatas"] = [metadata]
                try:
                    self.collection.add(**options)
                except Exception as exc:
                    logger.warning("[MEMORY] Indexation vectorielle échouée (%s) ; expérience conservée.", type(exc).__name__)
            
        await asyncio.to_thread(_add)

    async def query_experience(self, situation: str, n_results: int = 3) -> list:
        import asyncio
        import math
        n_results = max(1, min(int(n_results), 50))
        
        def _query():
            if self.collection is not None:
                try:
                    count = self.collection.count()
                    if count:
                        result = self.collection.query(query_texts=[situation], n_results=min(n_results, count))
                        docs = result.get("documents") or [[]]
                        if docs[0]:
                            return docs[0]
                except Exception as exc:
                    logger.warning("[MEMORY] Rappel vectoriel échoué (%s) ; recherche BM25 SQLite.", type(exc).__name__)
            with closing(sqlite3.connect(self.sqlite_path)) as connection:
                rows = connection.execute("SELECT document FROM experiences ORDER BY rowid DESC LIMIT 500").fetchall()
            if not rows:
                return []
            terms = [t for t in set(re.findall(r"\w+", situation.casefold())) if len(t) >= 2]
            if not terms:
                return [doc for (doc,) in rows[:n_results]]
            n_docs = len(rows)
            doc_lowers = [doc.casefold() for (doc,) in rows]
            df = {t: sum(1 for dl in doc_lowers if t in dl) for t in terms}
            idf = {t: math.log(1.0 + (n_docs - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}
            ranked = []
            for idx, ((doc,), dl) in enumerate(zip(rows, doc_lowers)):
                bm25_score = sum(idf[t] for t in terms if t in dl)
                if bm25_score <= 0:
                    continue
                recency_bonus = 0.15 * max(0.0, 1.0 - (idx / max(1, n_docs)))
                verified_bonus = 0.25 if '"explicit_checks_only"' in dl or '"verified": true' in dl else 0.0
                ranked.append((bm25_score + recency_bonus + verified_bonus, doc))
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            return [doc for _, doc in ranked[:n_results]]
            
        return await asyncio.to_thread(_query)

