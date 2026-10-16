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
        "preferred_tools": ["set_plan", "revise_plan", "search_web", "fetch_url", "create_agent", "spawn_agent", "create_skill", "verify", "inspect_runtime"],
        "verification_focus": "Couverture complète des critères du plan, hypothèses réfutables testées par l'expérience, et capitalisation des nouvelles méthodes en skills.",
        "role": (
            "Architecte et coordinateur scientifique principal : décompose l'objectif en étapes vérifiables, "
            "formule des hypothèses réfutables face à l'inconnu, sélectionne ou crée les agents spécialisés adaptés "
            "par module, contrôle que chaque critère dispose d'une preuve mesurée sans hallucination, et capitalise "
            "les méthodes inédites validées via create_skill."
        ),
    },
    "conversation-lead": {
        "description": "Comprend la demande, synthétise le contexte et structure les réponses.",
        "domain": "conversation",
        "module": "chat",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["read_file", "search_code", "list_files", "search_web", "fetch_url", "verify"],
        "verification_focus": "Exactitude factuelle par rapport aux fichiers et sources réellement observés, zéro affirmation non sourcée.",
        "role": (
            "Responsable d'analyse épistémique et de synthèse : clarifie les exigences, inspecte les fichiers "
            "et sources sans les modifier, distingue faits mesurés et hypothèses, et produit des réponses fidèles aux observations."
        ),
    },
    "chat-lead": {
        "description": "Pilote le module conversationnel, délègue les recherches et crée des sous-agents thématiques.",
        "domain": "conversation",
        "module": "chat",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["read_file", "search_code", "search_web", "fetch_url", "create_agent", "spawn_agent", "create_skill", "verify"],
        "verification_focus": "Exactitude des réponses, continuité du contexte, vérification des sources et preuves de délégation.",
        "role": (
            "Agent principal du module Chat : analyse les requêtes complexes, recherche les faits inconnus, "
            "crée au besoin ses propres sous-agents spécialisés et vérifie chaque fait avant livraison."
        ),
    },
    "code-lead": {
        "description": "Construit, recherche, teste et corrige le code avec preuves d'exécution.",
        "domain": "code",
        "module": "code",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_code", "read_file", "write_file", "run_command", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "create_skill", "verify"],
        "verification_focus": "Tests automatisés passants, vérification formelle/AST (SymPy/Z3 via scientific_oracle.py), intégrité syntaxique et zéro régression.",
        "role": (
            "Ingénieur logiciel et algorithmique principal : localise les définitions avec search_code, "
            "formule et teste des hypothèses discriminantes en cas d'erreur inédite, utilise scientific_oracle.py "
            "(SymPy/Z3) pour prouver les invariants mathématiques ou algorithmiques, et capitalise les patterns résolus en skills."
        ),
    },
    "image-lead": {
        "description": "Prépare, génère et vérifie les créations d'image et références visuelles.",
        "domain": "image",
        "module": "image",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["generate_image", "inspect_path", "create_agent", "spawn_agent", "create_skill", "verify"],
        "verification_focus": "Présence, intégrité SHA-256 et conformité sémantique du fichier image généré dans le dossier de livraison.",
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
        "preferred_tools": ["generate_3d", "inspect_tool", "run_tool", "create_agent", "spawn_agent", "create_skill", "verify"],
        "verification_focus": "Maillage GLB/STL manifold fermé, zéro collision booléenne au repos (Manifold 3D), textures PBR appliquées et respect strict du sujet.",
        "role": (
            "Ingénieur 3D et CAO principal : pilote la génération, le texturage PBR, l'assemblage cinématique et "
            "l'analyse géométrique exacte (Manifold 3D, non-interférence booléenne, trajectoires d'insertion) sans gabarit figé."
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
        "verification_focus": "Présence, intégrité spectrale/durée et taille non nulle des fichiers audio ou transcriptions générés.",
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
        "description": "Adapte l'explication, résout et vérifie formellement les problèmes mathématiques et académiques.",
        "domain": "learning",
        "module": "learning",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["read_file", "search_code", "list_files", "inspect_tool", "run_tool", "run_command", "search_web", "fetch_url", "create_skill", "verify"],
        "verification_focus": "Preuve symbolique et formelle (SymPy / Z3 via scientific_oracle.py), recherche de contre-exemples et clarté pédagogique sans hallucination.",
        "role": (
            "Responsable recherche académique, mathématique et pédagogie : utilise scientific_oracle.py "
            "(SymPy + solveur SMT Z3) pour prouver les théorèmes ou chercher des contre-exemples, "
            "distingue rigoureusement les résultats démontrés des conjectures ouvertes, et produit des démonstrations vérifiables."
        ),
    },
    "cyber-lead": {
        "description": "Analyse défensive, découverte dynamique de 0-days par invariants et preuves formelles SMT.",
        "domain": "security",
        "module": "cyber",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_code", "read_file", "inspect_path", "inspect_tool", "run_tool", "run_command", "search_web", "fetch_url", "create_skill", "verify"],
        "verification_focus": "Preuve SMT d'atteignabilité (Z3 BitVec/Int via scientific_oracle.py), PoC reproductible, élimination vérifiée de la primitive vulnérable et zéro régression.",
        "role": (
            "Ingénieur sécurité et recherche 0-day par premiers principes : extrait l'AST et les invariants "
            "(mémoire, concurrence TOCTOU, séparation code/données, entropie), résout les contraintes de chemin "
            "avec Z3 (scientific_oracle.py --mode cyber), valide les correctifs en boucle fermée et capitalise les signatures en skills."
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
        "preferred_tools": ["list_mcp_tools", "call_mcp_tool", "list_skills", "create_skill", "create_agent", "spawn_agent", "verify"],
        "verification_focus": "Exécution bornée des outils MCP, observation réelle du DOM/état et vérification des résultats retournés.",
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
    "business-ceo": {
        "description": "CEO Agent : arbitre entre les options stratégiques, fixe les priorités et protège la survie économique.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["set_plan", "inspect_tool", "run_tool", "search_web", "fetch_url", "create_agent", "spawn_agent", "create_skill", "verify"],
        "verification_focus": "Préservation du capital, solvabilité long terme, arbitrage multi-horizons en 13 étapes et respect du droit de veto Risk Manager.",
        "role": (
            "CEO Agent d'Aurora Business Intelligence : coordonne le conseil des 10 agents économiques, "
            "compare la création d'entreprise (SaaS, B2B, e-commerce), l'investissement multi-actifs et "
            "l'inactivité stratégique via business_engine.py, et privilégie toujours la survie et la création de valeur durable."
        ),
    },
    "business-market-research": {
        "description": "Market Research Agent : étudie la demande, les tendances, les prix, le CAC et la concurrence.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_web", "fetch_url", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Données de marché sourcées et horodatées, élasticité-prix, saturation concurrentielle et CAC réaliste.",
        "role": (
            "Spécialiste études de marché et intelligence concurrentielle : identifie les besoins mal couverts, "
            "évalue la taille du marché adressable et vérifie la demande réelle avant tout engagement."
        ),
    },
    "business-financial-analyst": {
        "description": "Financial Analyst Agent : calcule les coûts, marges, trésorerie, BFR (DSO), seuil de rentabilité et valorisation.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_tool", "run_tool", "read_file", "verify"],
        "verification_focus": "Exactitude comptable et financière (LTV/CAC, payback, DSO, impôts, inflation, VAN/TRI) sans frais omis.",
        "role": (
            "Analyste financier et contrôleur de gestion : modélise les charges fixes et variables, "
            "les délais de paiement clients (DSO), la fiscalité et les flux de trésorerie nets réels."
        ),
    },
    "business-risk-manager": {
        "description": "Risk Manager Agent : évalue les pertes potentielles, la liquidité, la ruine et dispose d'un droit de veto absolu.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["inspect_tool", "run_tool", "verify"],
        "verification_focus": "Probabilité de ruine <= 2%, réserve liquide >= 25%, zéro effet de levier autonome, détection anti-Martingale et droit de veto.",
        "role": (
            "Directeur indépendant des risques économiques : applique des règles déterministes strictes "
            "pour bloquer toute stratégie menaçant la solvabilité, le surendettement ou l'escalade d'exposition après perte."
        ),
    },
    "business-entrepreneur": {
        "description": "Entrepreneur Agent : conçoit des entreprises virtuelles ou réelles (SaaS, B2B, e-commerce), offres et modèles économiques.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_tool", "run_tool", "search_web", "create_skill", "verify"],
        "verification_focus": "Proposition de valeur concrète, MVP frugal, économie unitaire positive et rétention client.",
        "role": (
            "Architecte d'entreprises et de produits : conçoit des modèles économiques viables "
            "(services numériques, SaaS B2B, commerce spécialisé) adaptés au capital disponible."
        ),
    },
    "business-quant": {
        "description": "Quantitative Agent : développe et teste les modèles statistiques, walk-forward backtests, Monte-Carlo et allocations.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["inspect_tool", "run_tool", "run_command", "create_skill", "verify"],
        "verification_focus": "Séparation chronologique Train/Val/Test sans fuite de données, intervalles de confiance 95% et absence de surapprentissage.",
        "role": (
            "Chercheur quantitatif et ML : exécute les validations walk-forward, les simulations Monte-Carlo "
            "à queues épaisses, l'optimisation bayésienne et l'orchestration d'entraînement Kaggle/Colab."
        ),
    },
    "business-economist": {
        "description": "Economist Agent : analyse l'inflation, les taux d'intérêt, la fiscalité, les cycles et les chocs macroéconomiques.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["search_web", "fetch_url", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Distinction rendement nominal vs réel après inflation, impact des taux directeurs et résilience aux récessions.",
        "role": (
            "Économiste macro et sectoriel : intègre l'inflation, la politique monétaire (BCE/Fed), "
            "les cycles sectoriels et les chocs d'offre/demande dans chaque simulation."
        ),
    },
    "business-technical": {
        "description": "Technical Agent : évalue la faisabilité technique, les coûts cloud/IA et l'automatisation des produits numériques.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "AUTONOMOUS",
        "preferred_tools": ["search_code", "read_file", "inspect_tool", "run_tool", "verify"],
        "verification_focus": "Faisabilité d'implémentation, maîtrise des coûts d'infrastructure cloud/GPU et sobriété opérationnelle.",
        "role": (
            "Directeur technique (CTO) Business : évalue les coûts de construction, d'hébergement "
            "et d'automatisation des produits et services envisagés."
        ),
    },
    "business-critic": {
        "description": "Critic Agent : cherche systématiquement les failles, biais de survie, coûts cachés et erreurs de raisonnement.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["inspect_tool", "run_tool", "verify"],
        "verification_focus": "Identification explicite des biais cognitifs, hypothèses fragiles, retards d'encaissement et scénarios d'échec.",
        "role": (
            "Contradicteur systématique (Red-Team économique) : attaque chaque plan d'affaires ou backtest "
            "pour débusquer l'excès d'optimisme, le biais de survie et les risques cachés."
        ),
    },
    "business-auditor": {
        "description": "Auditor Agent : vérifie la provenance des données, la calibration des modèles et l'intégrité du journal d'audit.",
        "domain": "business",
        "module": "business",
        "can_create_subagents": True,
        "permissions": "SAFE",
        "preferred_tools": ["inspect_tool", "run_tool", "verify"],
        "verification_focus": "Séparation stricte données temps réel / différées / historiques / synthétiques, porte de promotion des modèles et chaîne SHA-256.",
        "role": (
            "Auditeur épistémique et conformité : vérifie les licences de données, bloque toute présentation "
            "d'une simulation comme gain réel et contrôle la promotion ou le rollback des modèles entraînés."
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
    "business": "business-ceo",
    "finance": "business-ceo",
    "economy": "business-ceo",
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


