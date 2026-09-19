import base64
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("AuroraAGI.Payload")

class SmartPayloadManager:
    """
    Gère intelligemment les fichiers (Images, 3D, PDF) selon le type de client.
    Sur mobile, il ne faut pas écrire de fichiers locaux aveuglément, mais 
    envoyer les données structurées.
    """
    @staticmethod
    def package_for_client(client_type: str, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Détecte l'environnement et emballe intelligemment le fichier."""
        if not os.path.exists(file_path):
            return {"status": "error", "message": "Fichier introuvable."}

        logger.info(f"[PAYLOAD] Formatage de {file_path} pour client : {client_type}")
        
        if client_type in ["mobile", "web"]:
            # Le client mobile ne peut pas lire le disque hôte facilement.
            # L'AGI comprend cela et encode directement en Base64.
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return {
                "type": "file_stream",
                "mime": mime_type,
                "filename": os.path.basename(file_path),
                "data_b64": encoded
            }
        else:
            # Client PC (macOS/Linux) : chemin absolu direct ou transfert réseau standard
            return {
                "type": "file_path",
                "mime": mime_type,
                "path": os.path.abspath(file_path)
            }
