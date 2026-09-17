import os
import logging
import uuid
import json

logger = logging.getLogger("AuroraAGI.Memory")

class OmniscientMemory:
    """Mémoire Vectorielle Globale du Serveur."""
    def __init__(self, db_path: str = "/home/juan/AuroraIA/db_vector"):
        self.db_path = db_path
        self.collection = None
        self._init_db()

    def _init_db(self):
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(name="aurora_omniscience")
            logger.info("[MEMORY] Cortex vectoriel ChromaDB activé.")
        except ImportError:
            logger.warning("[MEMORY] ChromaDB manquant. Exécution avec mémoire volatile.")

    def embed_experience(self, context: str, outcome: str, metadata: dict = None):
        if not self.collection: return
        doc_id = str(uuid.uuid4())
        doc_str = json.dumps({"context": context, "outcome": outcome})
        self.collection.add(documents=[doc_str], metadatas=[metadata or {}], ids=[doc_id])

    def query_experience(self, situation: str, n_results: int = 3) -> list:
        if not self.collection: return []
        res = self.collection.query(query_texts=[situation], n_results=n_results)
        return res.get("documents", [[]])[0]
