import os
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
        legacy = Path(__file__).resolve().parents[1] / "db_vector"
        selected = (db_path or os.environ.get("AURORA_MEMORY_DIR")
                    or (legacy if legacy.is_dir() else data_dir() / "brain/vector_memory"))
        self.db_path = str(Path(selected).expanduser())
        self.collection = None
        self.client = None
        self.sqlite_path = Path(self.db_path) / "experiences.sqlite3"
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as connection:
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
        doc_id = str(uuid.uuid4())
        doc_str = json.dumps({"context": context, "outcome": outcome})
        
        def _add():
            with sqlite3.connect(self.sqlite_path) as connection:
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
                    logger.warning("[MEMORY] Rappel vectoriel échoué (%s) ; recherche lexicale SQLite.", type(exc).__name__)
            with sqlite3.connect(self.sqlite_path) as connection:
                rows = connection.execute("SELECT document FROM experiences ORDER BY rowid DESC LIMIT 500").fetchall()
            terms = set(re.findall(r"\w+", situation.casefold()))
            ranked = sorted(((sum(t in doc.casefold() for t in terms), doc) for (doc,) in rows),
                            key=lambda pair: pair[0], reverse=True)
            return [doc for score, doc in ranked if score > 0][:n_results]
            
        return await asyncio.to_thread(_query)
