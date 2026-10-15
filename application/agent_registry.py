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
        "module": "orchestration",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["set_plan", "revise_plan", "create_agent", "spawn_agent", "verify", "inspect_runtime"],
        "verification_focus": "Couverture complète des critères du plan et preuves d'exécution des sous-tâches.",
        "role": (
            "Architecte et coordinateur principal : décompose l'objectif en étapes vérifiables, "
            "sélectionne ou crée les agents spécialisés adaptés par module et contrôle que chaque critère "
            "dispose d'une preuve mesurée avant conclusion."
        ),
    },
    "conversation-lead": {
        "description": "Comprend la demande, synthétise le contexte et structure les réponses.",
        "domain": "conversation",
        "module": "chat",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["read_file", "search_code", "list_files", "verify"],
        "verification_focus": "Exactitude factuelle par rapport aux fichiers et sources réellement observés.",
        "role": (
            "Responsable d'analyse et de synthèse : clarifie les exigences, inspecte les fichiers "
            "sans les modifier et produit des réponses fidèles aux observations."
        ),
    },
    "chat-lead": {
        "description": "Pilote le module conversationnel, délègue les recherches et crée des sous-agents thématiques.",
        "domain": "conversation",
        "module": "chat",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["read_file", "search_code", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Exactitude des réponses, continuité du contexte et preuves de délégation.",
        "role": (
            "Agent principal du module Chat : analyse les requêtes complexes, crée au besoin ses propres "
            "sous-agents spécialisés et vérifie chaque fait avant livraison."
        ),
    },
    "code-lead": {
        "description": "Construit, recherche, teste et corrige le code avec preuves d'exécution.",
        "domain": "code",
        "module": "code",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_code", "read_file", "write_file", "run_command", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Tests automatisés passants, intégrité syntaxique et vérification des sorties.",
        "role": (
            "Ingénieur logiciel principal : localise les définitions et usages avec search_code, "
            "lit les fichiers avant modification, écrit du code propre, crée au besoin des sous-agents "
            "de test ou d'audit et exécute des tests réels pour prouver chaque correction."
        ),
    },
    "image-lead": {
        "description": "Prépare, génère et vérifie les créations d'image et références visuelles.",
        "domain": "image",
        "module": "image",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["generate_image", "inspect_path", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Présence, intégrité SHA-256 et conformité du fichier image généré dans le dossier de livraison.",
        "role": (
            "Spécialiste génération d'images : compose des prompts fidèles au sujet demandé sans "
            "ajouter de décor non sollicité, crée des sous-agents de contrôle visuel si nécessaire et vérifie l'artefact produit."
        ),
    },
    "3d-lead": {
        "description": "Orchestre la création, l'assemblage et la validation de modèles et scènes 3D.",
        "domain": "3d",
        "module": "3d",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["generate_3d", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Maillage GLB/STL valide, textures PBR appliquées, respect strict du sujet sans éléments inventés, géométrie vérifiée.",
        "role": (
            "Ingénieur 3D principal : pilote la génération, le texturage PBR et l'analyse géométrique 3D "
            "en préservant strictement le sujet demandé et en déléguant aux sous-agents 3D (texture, viewer, motion, rescue)."
        ),
    },
    "3d-pipeline-router": {
        "description": "Choisit le pipeline 3D adapté aux ressources matérielles et au sujet.",
        "domain": "3d",
        "module": "3d",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_runtime", "list_tools", "inspect_tool", "generate_3d", "create_agent", "spawn_agent"],
        "verification_focus": "Adéquation entre VRAM/RAM disponible, moteur 3D sélectionné et livrable attendu.",
        "role": (
            "Routeur de pipeline 3D : inspecte les ressources GPU/CPU et les scripts 3D disponibles "
            "pour sélectionner le moteur d'exécution optimal."
        ),
    },
    "3d-quality-rescuer": {
        "description": "Diagnostique et répare un résultat 3D incomplet, non texturé, ouvert ou rejeté.",
        "domain": "3d",
        "module": "3d",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_path", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Fermeture du maillage, réparation des normales, application effective des textures et validation géométrique post-correction.",
        "role": (
            "Spécialiste réparation et contrôle qualité 3D : diagnostique les défauts de maillage "
            "ou de texture et applique les outils d'auto-correction géométrique et PBR."
        ),
    },
    "3d-texture-lead": {
        "description": "Spécialiste textures PBR, dépliage UV, segmentation multi-zones et matériaux glTF.",
        "domain": "3d",
        "module": "3d-texture",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_path", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Présence de baseColorTexture ou couleurs multi-zones non neutres, canaux metallicRoughness/normal/emissive et zéro texture bâclée.",
        "role": (
            "Ingénieur textures et matériaux PBR 3D : garantit que chaque texture ou matériau demandé "
            "(bois, métal, verre, tissu, cuir, émissif, organique) est réellement généré, projeté et inscrit dans le GLB."
        ),
    },
    "3d-viewer-lead": {
        "description": "Garantit l'affichage immédiat, le décodage Draco/Meshopt et le rendu des modèles dans le viewer 3D.",
        "domain": "3d",
        "module": "3d-viewer",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_path", "read_file", "search_code", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Résolution des URLs d'assets 3D (/api/3d/file, /api/asset, Tauri, tunnel), validité glTF/GLB et affichage effectif dans le viewer.",
        "role": (
            "Spécialiste viewer 3D et transport d'assets : vérifie que tout modèle généré ou réparé "
            "est immédiatement chargeable et visible dans le viewer natif, web et tunnel."
        ),
    },
    "3d-motion-lead": {
        "description": "Pilote le rigging squelettique, le skinning et l'animation sémantique 3D.",
        "domain": "3d",
        "module": "3d-motion",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Présence des clips d'animation glTF, cohérence des articulations et préservation du maillage texturé.",
        "role": (
            "Ingénieur rigging et animation 3D : applique les squelettes et clips d'animation demandés "
            "avec auto-correction sans jamais bloquer l'affichage du modèle."
        ),
    },
    "voice-lead": {
        "description": "Coordonne la transcription audio (STT) et la synthèse vocale (TTS).",
        "domain": "voice",
        "module": "voice",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_tools", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Présence et taille non nulle des fichiers audio ou transcriptions générés.",
        "role": (
            "Ingénieur audio et voix : inspecte les outils de transcription et de synthèse vocale, "
            "crée au besoin ses sous-agents audio et vérifie les fichiers produits."
        ),
    },
    "video-lead": {
        "description": "Coordonne l'analyse, le découpage et la production vidéo.",
        "domain": "video",
        "module": "video",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_tools", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Intégrité des flux et fichiers vidéo produits dans le dossier de livraison.",
        "role": (
            "Spécialiste pipeline vidéo : coordonne les scripts d'analyse et de génération vidéo, "
            "délègue aux sous-agents vidéo et contrôle les artefacts livrés."
        ),
    },
    "learning-lead": {
        "description": "Adapte l'explication, documente l'architecture et vérifie la compréhension.",
        "domain": "learning",
        "module": "learning",
        "can_create_subagents": True,
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
        "module": "cyber",
        "can_create_subagents": True,
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
        "module": "bridge",
        "can_create_subagents": True,
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
        "module": "cowork",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_mcp_tools", "call_mcp_tool", "list_skills", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Exécution bornée des outils MCP et vérification des résultats retournés.",
        "role": (
            "Spécialiste intégration MCP et automatisation : découvre les outils MCP et skills "
            "du projet, crée des sous-agents d'automatisation et exécute les appels externes autorisés avec preuves."
        ),
    },
    "memory-lead": {
        "description": "Gère la mémoire épisodique, sémantique et procédurale ainsi que la continuité inter-sessions.",
        "domain": "memory",
        "module": "memory",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["read_file", "search_code", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Exactitude des faits mémorisés, absence d'hallucination et intégrité du graphe mémoire.",
        "role": (
            "Spécialiste mémoire et contexte : structure, vérifie et consolide les connaissances "
            "persistantes du workspace sans altérer les consignes de mission."
        ),
    },
    "mcp-lead": {
        "description": "Découvre, sonde et orchestre les serveurs et outils MCP locaux ou distants.",
        "domain": "mcp",
        "module": "mcp",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_mcp_tools", "call_mcp_tool", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Disponibilité réelle des serveurs MCP stdio/HTTP et validation des réponses JSON-RPC.",
        "role": (
            "Ingénieur protocole MCP : inspecte la configuration MCP, sonde les outils disponibles "
            "et crée au besoin des sous-agents dédiés à chaque serveur MCP."
        ),
    },
    "skills-lead": {
        "description": "Crée, audite et maintient les skills réutilisables du workspace.",
        "domain": "skills",
        "module": "skills",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["list_skills", "create_skill", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Présence sur disque, validité du frontmatter SKILL.md et intégrité SHA-256.",
        "role": (
            "Architecte de compétences (Skills) : formalise les procédures vérifiées sous forme de "
            "skills réutilisables et coordonne les sous-agents spécialisés par compétence."
        ),
    },
    "cli-tunnel-lead": {
        "description": "Assure la continuité entre le CLI distant, le pont local et le tunnel Cloudflare.",
        "domain": "diagnostics",
        "module": "cli-tunnel",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_runtime", "run_command", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Parité de bout en bout entre exécution locale, pont HTTP et tunnel distant.",
        "role": (
            "Spécialiste CLI et Tunnel : diagnostique et corrige les parcours de transport, "
            "d'authentification et de synchronisation entre AuroraIA et aurora-remote-cli."
        ),
    },
}

MODULE_PRIMARY_AGENTS = {
    "orchestration": "aurora-orchestrator",
    "chat": "chat-lead",
    "conversation": "chat-lead",
    "code": "code-lead",
    "image": "image-lead",
    "3d": "3d-lead",
    "3d-texture": "3d-texture-lead",
    "3d-viewer": "3d-viewer-lead",
    "3d-motion": "3d-motion-lead",
    "voice": "voice-lead",
    "video": "video-lead",
    "learning": "learning-lead",
    "cyber": "cyber-lead",
    "security": "cyber-lead",
    "bridge": "bridge-doctor",
    "diagnostics": "bridge-doctor",
    "cowork": "cowork-lead",
    "automation": "cowork-lead",
    "memory": "memory-lead",
    "mcp": "mcp-lead",
    "skills": "skills-lead",
    "cli-tunnel": "cli-tunnel-lead",
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


def get_module_agent(module: str):
    key = (module or "").strip().lower()
    agent_name = MODULE_PRIMARY_AGENTS.get(key)
    if agent_name and agent_name in AGENTS:
        return get_agent(agent_name)
    for name, details in sorted(AGENTS.items()):
        if details.get("module") == key or details.get("domain") == key:
            return {"name": name, **details, "protected": True}
    return None


def list_module_agents(module: str | None = None):
    if not module:
        return list_agents()
    key = module.strip().lower()
    return [
        {"name": name, **details, "enabled": True, "protected": True}
        for name, details in sorted(AGENTS.items())
        if details.get("module") == key or details.get("domain") == key
    ]


