"""Built-in agent registry used at runtime.

Agents are executable roles, so their registry belongs to the application
code and not to an editor-specific folder or prose files.  Keeping the
definitions here also means a packaged bridge has the same agents as a
checkout.
"""

AGENTS = {
    "aurora-orchestrator": {"description": "Coordonne les étapes et choisit les outils."},
    "conversation-lead": {"description": "Comprend la demande et conduit la conversation."},
    "code-lead": {"description": "Construit, teste et corrige le code."},
    "image-lead": {"description": "Prépare et vérifie les créations d'image."},
    "3d-lead": {"description": "Orchestre la création et la validation 3D."},
    "3d-pipeline-router": {"description": "Choisit le pipeline 3D adapté aux ressources."},
    "3d-quality-rescuer": {"description": "Répare un résultat 3D incomplet ou rejeté."},
    "voice-lead": {"description": "Coordonne la transcription, la synthèse et la voix."},
    "video-lead": {"description": "Coordonne l'analyse et la production vidéo."},
    "learning-lead": {"description": "Adapte l'explication et vérifie l'apprentissage."},
    "cyber-lead": {"description": "Analyse défensive et vérifications de sécurité."},
    "bridge-doctor": {"description": "Diagnostique les moteurs, ports et transports."},
    "cowork-lead": {"description": "Planifie les actions avec les applications autorisées."},
}


def list_agents():
    return [{"name": name, **details, "enabled": True, "protected": True}
            for name, details in sorted(AGENTS.items())]


def get_agent(name):
    return AGENTS.get(name)
