"""Built-in agent registry used at runtime.

Agents are executable roles, so their registry belongs to the application
code and not to an editor-specific folder or prose files.  Keeping the
definitions here also means a packaged bridge has the same agents as a
checkout.
"""

AGENTS = {
    "aurora-orchestrator": {
        "description": "Coordonne les étapes, découpe les missions complexes et choisit les outils.",
        "domain": "orchestration",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["set_plan", "revise_plan", "spawn_agent", "verify", "inspect_runtime"],
        "verification_focus": "Couverture complète des critères du plan et preuves d'exécution des sous-tâches.",
        "role": (
            "Architecte et coordinateur principal : décompose l'objectif en étapes vérifiables, "
            "sélectionne les outils ou agents spécialisés adaptés et contrôle que chaque critère "
            "dispose d'une preuve mesurée avant conclusion."
        ),
    },
    "conversation-lead": {
        "description": "Comprend la demande, synthétise le contexte et structure les réponses.",
        "domain": "conversation",
        "permissions": "SAFE",
        "preferred_tools": ["read_file", "search_code", "list_files", "verify"],
        "verification_focus": "Exactitude factuelle par rapport aux fichiers et sources réellement observés.",
        "role": (
            "Responsable d'analyse et de synthèse : clarifie les exigences, inspecte les fichiers "
            "sans les modifier et produit des réponses fidèles aux observations."
        ),
    },
    "code-lead": {
        "description": "Construit, recherche, teste et corrige le code avec preuves d'exécution.",
        "domain": "code",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_code", "read_file", "write_file", "run_command", "verify"],
        "verification_focus": "Tests automatisés passants, intégrité syntaxique et vérification des sorties.",
        "role": (
            "Ingénieur logiciel principal : localise les définitions et usages avec search_code, "
            "lit les fichiers avant modification, écrit du code propre et exécute des tests réels "
            "pour prouver chaque correction."
        ),
    },
    "image-lead": {
        "description": "Prépare, génère et vérifie les créations d'image et références visuelles.",
        "domain": "image",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["generate_image", "inspect_path", "verify"],
        "verification_focus": "Présence, intégrité SHA-256 et conformité du fichier image généré dans le dossier de livraison.",
        "role": (
            "Spécialiste génération d'images : compose des prompts fidèles au sujet demandé sans "
            "ajouter de décor non sollicité et vérifie l'artefact produit."
        ),
    },
    "3d-lead": {
        "description": "Orchestre la création, l'assemblage et la validation de modèles et scènes 3D.",
        "domain": "3d",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["generate_3d", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Maillage GLB/STL valide, respect strict du sujet sans éléments inventés, géométrie vérifiée.",
        "role": (
            "Ingénieur 3D principal : pilote la génération et l'analyse géométrique 3D en préservant "
            "strictement le sujet demandé, sans décor ni accessoires inventés."
        ),
    },
    "3d-pipeline-router": {
        "description": "Choisit le pipeline 3D adapté aux ressources matérielles et au sujet.",
        "domain": "3d",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_runtime", "list_tools", "inspect_tool", "generate_3d"],
        "verification_focus": "Adéquation entre VRAM/RAM disponible, moteur 3D sélectionné et livrable attendu.",
        "role": (
            "Routeur de pipeline 3D : inspecte les ressources GPU/CPU et les scripts 3D disponibles "
            "pour sélectionner le moteur d'exécution optimal."
        ),
    },
    "3d-quality-rescuer": {
        "description": "Diagnostique et répare un résultat 3D incomplet, ouvert ou rejeté.",
        "domain": "3d",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_path", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Fermeture du maillage, réparation des normales et validation géométrique post-correction.",
        "role": (
            "Spécialiste réparation et contrôle qualité 3D : diagnostique les défauts de maillage "
            "ou de texture et applique les outils de réparation géométrique appropriés."
        ),
    },
    "voice-lead": {
        "description": "Coordonne la transcription audio (STT) et la synthèse vocale (TTS).",
        "domain": "voice",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_tools", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Présence et taille non nulle des fichiers audio ou transcriptions générés.",
        "role": (
            "Ingénieur audio et voix : inspecte les outils de transcription et de synthèse vocale "
            "et vérifie les fichiers audio ou JSON produits."
        ),
    },
    "video-lead": {
        "description": "Coordonne l'analyse, le découpage et la production vidéo.",
        "domain": "video",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_tools", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Intégrité des flux et fichiers vidéo produits dans le dossier de livraison.",
        "role": (
            "Spécialiste pipeline vidéo : coordonne les scripts d'analyse et de génération vidéo "
            "avec contrôle des artefacts livrés."
        ),
    },
    "learning-lead": {
        "description": "Adapte l'explication, documente l'architecture et vérifie la compréhension.",
        "domain": "learning",
        "permissions": "SAFE",
        "preferred_tools": ["read_file", "search_code", "list_files", "verify"],
        "verification_focus": "Clarté pédagogique et exactitude des exemples par rapport au code réel.",
        "role": (
            "Responsable documentation et pédagogie : inspecte le code source réel pour produire "
            "des explications et guides techniques vérifiables."
        ),
    },
    "cyber-lead": {
        "description": "Analyse défensive, audit de surface et vérifications de sécurité.",
        "domain": "security",
        "permissions": "STANDARD",
        "preferred_tools": ["search_code", "read_file", "inspect_path", "run_command", "verify"],
        "verification_focus": "Absence de traversée de chemin, confinement workspace, validation des entrées et secrets.",
        "role": (
            "Ingénieur sécurité défensive : audite le code et les configurations pour détecter "
            "les failles d'injection, fuites de secrets ou contournements de permissions."
        ),
    },
    "bridge-doctor": {
        "description": "Diagnostique les moteurs, ports, tunnels et transports réseau.",
        "domain": "diagnostics",
        "permissions": "SAFE",
        "preferred_tools": ["inspect_runtime", "inspect_path", "list_tools", "list_mcp_tools", "verify"],
        "verification_focus": "État réel mesuré des services, ports, modèles et serveurs MCP sans supposition.",
        "role": (
            "Ingénieur diagnostic système et pont : observe l'état réel du runtime, des modèles "
            "et des connecteurs MCP pour isoler toute défaillance."
        ),
    },
    "cowork-lead": {
        "description": "Planifie et exécute les actions avec les applications et serveurs MCP autorisés.",
        "domain": "automation",
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_mcp_tools", "call_mcp_tool", "list_skills", "verify"],
        "verification_focus": "Exécution bornée des outils MCP et vérification des résultats retournés.",
        "role": (
            "Spécialiste intégration MCP et automatisation : découvre les outils MCP et skills "
            "du projet et exécute les appels externes autorisés avec preuves."
        ),
    },
}


def list_agents(disabled=()):
    disabled_set = set(disabled or ())
    return [
        {
            "name": name,
            **details,
            "enabled": name not in disabled_set,
            "protected": True,
        }
        for name, details in sorted(AGENTS.items())
    ]


def get_agent(name):
    details = AGENTS.get(name)
    return {"name": name, **details, "protected": True} if details else None

