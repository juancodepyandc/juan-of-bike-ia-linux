# Cycle 1 — référence mesurée et trois correctifs

19 septembre 2026. Référence initiale : cerveau `5525496`, extension `1f5ba5a`.
Les critères d'arrêt ne sont pas atteints. La cartographie structurelle est disponible ; la revue sémantique exhaustive, les mesures de qualité des modèles et la parité complète restent à établir. Aucune note globale de 9 n'est attribuée.

## 1. Carte du système

Les deux arbres physiques ont été parcourus depuis leur parent commun. L'inventaire comprend les fichiers cachés, les dépendances installées, les données et les métadonnées Git, sans suivre les liens symboliques. Les contenus des secrets ne figurent pas dans les livrables.

| Référence initiale | Cerveau | Extension |
|---|---:|---:|
| Fichiers suivis par Git | 2 010 | 47 |
| Fichiers physiques | 259 399 | 414 |
| Répertoires physiques | 35 383 | 218 |
| Liens symboliques | 163 | 0 |
| Lignes de sources reconnues | 606 434 | 2 516 |
| Erreurs de parcours | 0 | 0 |

Les arbres complets sont dans `AuroraIA-tree.jsonl.gz` et `aurora-remote-cli-tree.jsonl.gz`. Chaque entrée contient chemin, type, taille et permissions. Les fichiers suivis avec empreintes et les appels syntaxiques Python figurent dans les inventaires JSON. Les gros JSON restent consultables localement ; leurs copies compressées sont versionnées.

L'index courant contient **26 367 fonctions Python/JS/TS**, dont **7 185 publiques selon les conventions lexicales du langage**. Il inclut tests, archives, scripts et code tiers suivi. Les fonctions imbriquées ne sont pas déclarées publiques. Ce décompte n'est pas celui des fonctionnalités accessibles. Le registre `unit-review-register.csv` fournit module → fichier → fonction → lignes → état de revue. Les autres langages, les exports indirects et les méthodes ajoutées dynamiquement nécessitent encore une analyse dédiée ; l'index n'est pas présenté comme exhaustif pour ces cas.

Cet index est figé après les correctifs fonctionnels, aux révisions `c69de9b` et `ca188b0`, avant l'ajout des outils d'audit et le retrait du suivi des caches Python. Les nouvelles sources d'audit sont vérifiées par leur suite dédiée.

| Surface ou composant | Entrée et chemin lu |
|---|---|
| CLI locale | `aurora_cli.py:10` → paquet frère `aurora_cli.cli:main` → client HTTP partagé |
| CLI distante | `../aurora-remote-cli/pyproject.toml:26` → `aurora_cli/cli.py:46` → `client.py:222` |
| Missions | `application/routes/cli_bp_routes.py:1027` → publication TCP locale → `aurora_agi_daemon.py:50` → `agi_core/swarm.py:21` → `agi_core/mission_agent.py:161` |
| Résultats | `agi_core/mission_agent.py:37` → `agi_core/bus.py:94` → listener `cli_bp_routes.py:1095` → flux SSE `cli_bp_routes.py:1146` → `client.py:229` |
| Conversation desktop | `application/src/services/conversationOrchestrator.ts:289` : routage, recherche, génération et vérification côté TypeScript |
| Code desktop | `application/src/services/codeOrchestrator.ts:68` : phases, sélection du modèle, correction et livraison côté TypeScript |
| Forge | `application/src/services/characterForge.ts:235` : pipeline frontend distinct des missions du daemon |
| Image/3D desktop | `application/src/hooks/useImageViewLogic.ts:191`, `useModelViewLogic.ts:52` ; interfaces vers les services et pipelines locaux |
| Académique | `application/src/services/learning/academicFormalEngine.ts:33` et services `learning/` ; aucun raccord à cette logique dans le faux outil de recherche MCP |
| Voix | `application/routes/voice_bp_routes.py`, `cinema_bp_routes.py:1502`, services Python ; contrats à comparer avec le client distant |
| Cyber | `application/src/services/cyber/` et `application/python-services/cyber/` ; revue fonctionnelle et tests de laboratoire restant à effectuer |
| Entraînement | `auto_rl/integration.py:7` enregistre les routes sur le bridge ; `auto_rl/config.py:34` active un mode hybride par défaut |
| MCP natif | `application/aurora_native_mcp.py:5` expose six fonctions ; plusieurs ne produisent pas le résultat annoncé |

L'enregistrement effectif des **26 blueprints réussit**, avec **313 règles Flask**, dans un processus de diagnostic qui neutralise les threads de démarrage. `runtime-routes.json` donne méthode, URL, handler et ligne. Cela ne prouve pas l'exécution de chaque route. La valeur publique codée en dur « 237 routes » (`cli_bp_routes.py:180`) ne décrit donc pas ce registre.

Le graphe comporte **2 850 dépendances de fichiers résolues**, **18 composantes cycliques** et **7 770 imports externes ou non résolus**. Le plus gros cycle comprend 59 fichiers TypeScript ; le cycle bridge ↔ blueprints en comprend 27. Les imports de types sont inclus : un cycle de types n'est pas automatiquement un cycle d'exécution. Le compilateur résout 19 935 cibles sur 70 357 appels JS/TS. Les appels Python sont syntaxiques ; les callbacks IPC, routes et appels de modèles ne sont pas artificiellement déclarés résolus. Les tests ajoutés tracent effectivement le superviseur avec doublures, puis le bridge et le vrai client HTTP.

L'inventaire courant signale 29 groupes de fichiers identiques, 824 `pass`, 359 marqueurs à examiner, 544 constantes contenant un chemin absolu et 315 contenant une URL côté cerveau. Côté extension : 8 `pass`, 24 constantes de chemins et 15 d'URL. Ce sont des candidats à qualifier, pas autant de défauts prouvés. L'absence de motif de secret connu ne certifie pas l'absence de secret. Aucun fichier n'est supprimé sur la seule base de l'absence d'appel statique.

## 2. Notation triée

Le tableau complet des **38 évaluations provisoires** est dans [SCORES.md](SCORES.md), avec chaque critère inférieur à 7 justifié par fichier et ligne. La formule est `(3J + 2R + 3T + 2A + 2C + O + 2S + D) / 16`. Les notes de fichier/module retiennent le minimum par critère des fonctions revues. Les autres unités restent marquées `unreviewed` ; elles ne reçoivent pas de note inventée.

| Fichier relu | Pondéré /10 | Défaut dominant |
|---|---:|---|
| `agi_core/explorer.py` | 1,75 | diagnostic de sécurité simulé |
| `agi_core/mission_agent.py` | 2,06 | succès non vérifié, permissions non appliquées |
| `agi_core/payload_manager.py` | 3,06 | chemin serveur présenté à un client distant |
| `aurora_agi_daemon.py` | 3,31 | traces purgées avant diagnostic réussi, pas de registre de tâches |
| `agi_core/bus.py` | 3,44 | diffusion globale sans accusé de réception |
| `agi_core/consciousness.py` | 3,44 | analyse de texte présentée comme auto-optimisation |
| `agi_core/memory.py` | 3,94 | persistance facultative et récupération sans scope |
| `agi_core/swarm.py` | 4,38 | plan déclaré validé sans vérification objective |
| `agi_core/llm_gateway.py` | 4,63 | erreurs renvoyées comme texte de résultat |
| `aurora_cli.py` | 6,25 | dépendance à un nom de dépôt frère |

Ces scores mesurent les défauts de code observés, pas une qualité d'inférence qui n'a pas encore été mesurée. Les modèles disponibles sont inventoriés dans `ollama-inventory.json`. Aucun changement de modèle n'est justifié par un classement supposé.

## 3. Défauts prioritaires et articulation

| Priorité | Preuve | Effet et correctif retenu |
|---|---|---|
| P0 | `application/routes/cli_bp_routes.py:92`, `:129`; `application/bridge_server.py:479` | Décorateur vide, auto-enregistrement public et gestion de clés autorisée sans vérification. Réparer ensemble authentification, enrôlement et couverture des routes, avec tests local/distant ; restaurer uniquement un décorateur laisserait les contournements ouverts. |
| P0 | `agi_core/mission_agent.py:163`, `:285` | Dossier partagé de transfert supprimé au début ; permissions reçues mais non appliquées. Attribuer un répertoire d'artefacts à chaque mission et appliquer les autorisations au point d'exécution. |
| P1 | `application/routes/cli_bp_routes.py:1117`, `:1193`; `aurora_agi_daemon.py:62` | Publication IPC sans statut, arrêt appelant une fonction absente, aucun abonné `mission.stop`. Définir un cycle de vie partagé avec accusés de réception, annulation réelle et état durable. |
| P1 | `application/package.json:10` | `npm test` réussit avec zéro test. Faire échouer une suite vide, puis restaurer des tests de comportement avant toute conclusion de couverture. |
| P1 | `application/aurora_native_mcp.py:11`, `:20`, `:37` | Route image inexistante ; outil 3D branché sur Cinema ; recherche académique sans recherche. Brancher les outils sur les vrais contrats, retourner artefact/statut/provenance et vérifier le résultat. |
| P1 | `agi_core/llm_gateway.py:74`, `agi_core/swarm.py:48` | Erreur de génération traitée comme texte puis poursuite du pipeline. Retour typé, échec terminal explicite et reprise réservée aux erreurs récupérables. |
| P1 | `../aurora-remote-cli/aurora_cli/core/jobia.py:56` | Le callback annonce success même si la mission a échoué. Consommer les états terminaux du contrat serveur. |
| P1 | `../aurora-remote-cli/aurora_cli/config.py:49`, `core/paths.py:25` | Écriture de configuration non atomique ; migration empêchée par la création préalable des destinations. Remplacement atomique en mode privé et migration par copie vérifiée conservant les originaux. |
| P2 | `agi_core/mission_agent.py:19`, `application/routes/cli_bp_routes.py:1003` | Le daemon renvoie un contexte vide alors que le bridge découvre skills/MCP. Un service de contexte backend partagé doit remplacer la copie simplifiée. |
| P2 | `agi_core/payload_manager.py:26`, `../aurora-remote-cli/aurora_cli/mission.py:151` | Base64 monolithique, noms de fichiers du serveur utilisés côté client. Transfert d'artefacts avec nom validé, taille, hash et reprise par plage. |

Mesure sans clé, sur le bridge actif puis sur l'application reconstruite : `/api/cli/version` → **200**, `/api/cli/auth` → **500**, statut de mission inconnue → **404**. L'erreur d'authentification est `AttributeError: cli_key_rec`. Aucun appel de génération, d'exécution shell ou de modification de clé n'a été envoyé pour cette preuve.

L'estimation de priorité combine gain, impact et effort, sur des échelles ordinales : authentification 5×5/3 ; erreurs et états terminaux 5×5/2 ; configuration 4×4/1 ; suite vide 5×4/2 ; contrats multimodaux 5×5/5. Ces valeurs orientent le travail ; elles ne sont pas des mesures de qualité des modèles. Chaque correction doit recevoir son test discriminant avant modification. Un timeout augmenté est inférieur à une reprise correctement identifiée ; il prolonge seulement une attente dont l'état est inconnu.

**Décision sur le dossier caché : conserver le dépôt source `aurora-remote-cli` visible.** Installer le paquet normalement et stocker configuration/état dans les emplacements XDG déjà prévus. Renommer le dépôt casserait le chemin explicite du lanceur (`aurora_cli.py:11`) sans créer de protection supplémentaire. Le travail retenu porte sur une installation du paquet indépendante du checkout, les permissions et la migration des données, avec conservation des originaux. Les mises à jour doivent rester visibles par la version du paquet et du protocole. Aucun déplacement de données n'a été effectué.

## 4. Correctifs appliqués et preuves

| Changement logique | Avant | Après | Régression contrôlée | Commit |
|---|---|---|---|---|
| Résolution de l'URL dans le client partagé | 2 échecs / 6 tests | 6/6 réussis | argument explicite prioritaire, clé toujours requise, URL enregistrée conservée | extension `ca188b0` |
| État du superviseur propre à chaque coroutine | 1 identité d'exécution pour 2 missions ; 1 échec / 2 tests | 2 identités séparées ; 2/2 réussis | workspace, modèle, mémoire et tokens de chaque mission contrôlés | cerveau `f71b6d2` |
| Lanceur local vers le paquet partagé | absence de preuve dédiée | 1/1 réussi | URL HTTP et en-tête Bearer observés, config distante inchangée | cerveau `b77c27c` |
| États terminaux depuis les événements IPC | 6 assertions en échec dans 5 tests | 6/6 tests réussis | fermeture SSE, durée figée, erreurs des deux formats, événements malformés et tardifs | cerveau `c69de9b` |
| Caches Python de l'extension | 9 fichiers `.pyc` suivis et modifiés par l'exécution | 0 fichier `.pyc` suivi | fichiers locaux conservés, tests 6/6 réussis après retrait du suivi | extension `2498c6b` |

Le dernier test utilise un serveur HTTP loopback éphémère et le vrai `AuroraClient` du dépôt distant. Le listener IPC reçoit une connexion contrôlée. Les tests du superviseur remplacent le modèle et l'agent d'exécution : ils prouvent l'isolation, pas la qualité d'une réponse ni celle d'un artefact. Les modifications backend ont été exécutées dans ces processus de test ; les services permanents n'ont pas été redémarrés dans ce cycle.

Référence générale : TypeScript **0 diagnostic**, compilation Vite réussie en **1,77 s** dans ce run, tests npm **0 exécuté**. L'analyse syntaxique Python du code suivi ne rapporte aucune erreur. Les tests de l'inventaire passent **5/5**. Les durées unitaires restent dans les journaux et ne constituent pas un benchmark de latence du système.

Matériel observé : RTX 5070 Ti, **16 303 MiB de VRAM** ; RAM physique **31 249 MiB**. Au début de l'audit : VRAM utilisée 5 620 MiB, RAM disponible 13 716 MiB, swap utilisé 16 222 MiB. Les contraintes réelles excluent toute conclusion fondée uniquement sur la présence des poids. Deux identifiants Ollama correspondent à des poids de 48,19 GiB chacun ; leur présence ne prouve pas une exécution sous 32 Go de RAM. Aucun chargement supplémentaire n'a été lancé.

## 5. Fonctionnalités à ajouter ou compléter

Estimations d'ingénierie, hors poids déjà chargés ; les budgets devront être mesurés sur un corpus fixé avant validation. Les fonctions existantes sont réutilisées quand elles réalisent déjà le travail.

| Classe | Fonction et valeur | Insertion exacte et implémentation | VRAM / RAM supplémentaires estimées | Dépendances | Pendant distant |
|---|---|---|---|---|---|
| Indispensable | Journal durable de mission et reprise après arrêt | entre `cli_mission_start`, bus et daemon : SQLite, transitions transactionnelles, identifiant d'opération, checkpoints ; reprise des seules étapes sûres à rejouer | 0 / 20–100 MiB, cache borné | `sqlite3` standard | statut, historique, reprise et curseur d'événement identiques |
| Indispensable | Résultats typés et vérification des artefacts | contrats partagés devant `LLMGateway`, `AutonomousMissionAgent` et MCP ; distinguer succès, échec et résultat non vérifié ; présence/hash/format puis évaluation métier | 0 / 10–100 MiB hors validateurs | schémas JSON et validation Python | afficher les mêmes états et les mêmes preuves |
| Indispensable | Mémoire persistante isolée et provenance | compléter `OmniscientMemory` : client/workspace, version de l'embedding, identifiants de sources, tests de rappel et de non-fuite ; aucune disparition silencieuse | 0 si embedding CPU / 0,5–2 GiB à mesurer | Chroma déjà référencé, embedding local explicitement configuré | recherche et gestion via API, aucun second cerveau client |
| Fort levier | Routage des modèles fondé sur les résultats | service backend commun à la passerelle et aux pipelines ; corpus séparé pour conversation, code, image, 3D, académique et voix ; mesurer qualité, erreurs, pic mémoire et régressions | 0 pour le routeur ; poids chargés à tour de rôle / métadonnées <100 MiB | inventaire Ollama/ComfyUI, évaluateurs locaux | même route choisie et même justification lisible |
| Fort levier | Planification vérifiable et boucle de correction | remplacer le plan libre de `SwarmSupervisor.run_mission` par étapes, dépendances et critères d'acceptation ; réutiliser les vérificateurs existants de `codeOrchestrator` | 0 hors modèle / état <100 MiB | contrats partagés ; adaptateur backend pour les services TS à spécifier | progression, corrections et reprise d'étape |
| Fort levier | Apprendre des échecs confirmés | relier `auto_rl/failure_memory.py` et les échecs durables du daemon ; corpus de non-régression séparé des exemples d'apprentissage, promotion conditionnée aux mesures | 0 pour indexation ; coût entraînement à mesurer séparément | infrastructure `auto_rl` existante, mode local explicite | consultation des échecs et résultats de campagne |
| Confort | Transfert reprenable des gros artefacts | remplacer `SmartPayloadManager` monolithique par manifeste, flux par blocs, hash et lecture par plages | 0 / 8–32 MiB de buffers | HTTP déjà installé, stockage local | reprise image/vidéo/mesh après interruption |

La reprise SSE utilisera le curseur `Last-Event-ID` et le découpage d'événements défini par le [standard WHATWG](https://html.spec.whatwg.org/multipage/server-sent-events.html). Le plan pourra utiliser les [sorties structurées Ollama](https://docs.ollama.com/capabilities/structured-outputs), avec validation métier indépendante. L'embedding doit être choisi explicitement et versionné selon le mécanisme documenté par [Chroma](https://docs.trychroma.com/docs/embeddings/embedding-functions). Ces choix de protocole ne prouvent pas qu'un modèle donné est le meilleur disponible.

## 6. Écarts restants cerveau / extension

- **Intelligence encore répartie** : les orchestrateurs TypeScript du desktop ne sont pas exécutés par le chemin Swarm de la CLI. Un client partagé ne suffit pas à assurer la parité avec le desktop.
- **Contexte et session** : `session_id` est stocké par `cli_mission_start`, mais le payload IPC envoyé à `mission.start` ne le contient pas ; le contexte daemon reste une copie vide. Pas de preuve de reprise d'une tâche interrompue.
- **Multimodal** : recherche MCP simulée, route image absente, 3D/Cinema confondus, artefacts non retournés dans les réponses des outils MCP. La parité image, 3D, voix et académique est donc non démontrée et comporte des défauts explicites.
- **Transport** : pas de version du message IPC, pas d'accusé de réception, pas de rejeu SSE, pas d'annulation bout en bout, pas de contrat de gros fichiers partagé.
- **Permissions et authentification** : niveaux déclarés mais non appliqués dans le daemon ; couverture d'authentification insuffisante sur le bridge. Les nouveaux tests de transport ne certifient pas l'accès distant.
- **Installation** : `pyproject.toml:6` annonce Python ≥3.8, alors que le README annonce ≥3.10 ; `setup.py` duplique et réduit les dépendances et les commandes. Le daemon importe `aiohttp` et Chroma, absents des exigences Python déclarées pour les services.
- **Exécution locale** : `auto_rl/config.py:34` choisit `hybrid` ; `aurora_cli/cli.py:71` dépend d'une découverte GitHub et `:13` de DNS-over-HTTPS pour le tunnel. Le fonctionnement entièrement local doit être vérifié sans ces services.

## 7. Cycle suivant

Priorité à l'authentification et au cycle de vie des missions : rendre l'enrôlement concret et cohérent sur les deux surfaces, tester les refus avant toute action, rendre l'arrêt effectif et supprimer les faux succès. Ensuite : réparer les contrats MCP multimodaux et la suite npm vide, puis mesurer chaque pipeline avec le même corpus local et distant. Les décisions de refonte majeure seront présentées avec leur implémentation de référence, leurs tests et leur migration avant demande de validation.

Commandes reproductibles depuis AuroraIA :

```sh
python3 scripts/audit/inventory.py --output audit/recheck --physical-tree
node scripts/audit/typescript.mjs audit/recheck
python3 scripts/audit/relationships.py audit/recheck
application/.venv/bin/python scripts/audit/runtime_routes.py audit/recheck
python3 -m unittest scripts.audit.test_inventory -v
python3 test_cli_local.py -v
application/.venv/bin/python -m unittest discover -s tests_agi -p test_swarm.py -v
application/.venv/bin/python application/test_cli_mission_events.py -v
npm --prefix application run typecheck
npm --prefix application test
npm --prefix application run build
```

Depuis l'extension : `python3 -m unittest discover -s tests -p test_client_config.py -v`.
Les journaux avant/après et les inventaires complets sont conservés dans ce dossier. Le nom `recheck` évite d'écraser la référence du cycle.
