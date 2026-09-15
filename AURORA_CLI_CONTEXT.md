# Contexte du Projet : Aurora Remote CLI

Ce document sert de point de référence central pour toute IA intervenant sur le développement du client distant (Remote CLI) pour AuroraIA. **IL NE DOIT PAS ÊTRE SUPPRIMÉ.** Il peut être étendu avec de nouvelles idées et propositions d'amélioration.

## 1. Objectif Principal
Créer une architecture client/serveur permettant de contrôler le copilote Aurora (qui tourne de manière permanente sur un PC Linux surpuissant) depuis un client léger (Mac, Windows, ou autre machine Linux) via un terminal Zsh/Bash, sans avoir à installer de modèles, de poids ou de runtime lourd sur le client. 

## 2. Architecture Globale
- **Serveur (Linux)** : Fait tourner Ollama, ComfyUI, les modèles (Flux, Qwen3, etc.), les agents et les outils lourds via un `bridge_server.py` central (Flask, port 3001).
- **Tunnel** : Cloudflare Tunnel (`*.trycloudflare.com`) pour un accès HTTPS sécurisé au bridge depuis l'extérieur.
- **Client (CLI)** : Un paquet Python léger (`aurora-cli`) installé sur la machine distante. Il se connecte au serveur via requêtes HTTP/SSE, s'authentifie par une clé `Bearer`, et affiche une UI terminal riche (via `rich` et `prompt_toolkit`).

## 3. Ce qui a été fait (État Actuel)
1. **Analyse de l'existant** :
   - Le `bridge_server.py` contient déjà 237 routes API (code/repo, fichiers, web, 3D, chat, etc.).
   - L'authentification par `Bearer token` existe déjà (`/api/ext/*`).
2. **Implémentation Serveur (Terminée)** :
   - Ajout d'environ 1100 lignes de code dans `bridge_server.py` sans modifier le code existant (séparées dans un bloc `# CLI Remote API`).
   - Routes créées : Authentification, Gestion des sessions, Chat streaming (SSE), Missions autonomes, Permissions, Espaces de travail, Outils, Modèles.
   - Système d'Agents protégé : 37 agents officiels sont en *lecture seule* (activables/désactivables).
   - Système d'Agents dynamiques : création, sauvegarde, modification, suppression.
   - Serveurs MCP : Découverte et exécution d'outils via le standard Model Context Protocol.
   - Skills : Découverte de fichiers `SKILL.md` (niveaux projet, user, global) pour donner le contexte métier.
   - Connexions de Services externes : Gestion centralisée des clés pour GitHub, Canva, Figma, Vercel, etc.
3. **Implémentation Client (Partielle - Base posée)** :
   - Création du projet `aurora-cli/` avec `pyproject.toml` (Dépendances : `httpx`, `rich`, `click`, `prompt-toolkit`).
   - `config.py` : Gestion locale de la config dans `~/.aurora/config.json`.
   - `client.py` : Client HTTP complet avec gestion du streaming (SSE) et mapping des appels API.
   - `display.py` : Interface terminal `rich` (tables, bannières, formatage).
   - `interactive.py` : Mode REPL interactif avec autocomplétion pour les commandes internes (`/status`, `/mcp`, `/agents`, etc.) et chat en streaming.

## 4. Ce qu'il reste à faire (Immédiat)
1. **Terminer le Client CLI** :
   - Coder `cli.py` : Le point d'entrée principal utilisant `click` pour orchestrer les sous-commandes (`aurora status`, `aurora doctor`, `aurora connect`, `aurora agents`, etc.).
   - Coder `mission.py` : Le gestionnaire de mission autonome (traitement du SSE des missions, affichage en temps réel des actions, des temps, et des outils utilisés).
2. **Installation** :
   - Créer `install.sh` : Script d'installation *one-liner* (ex: `curl ... | bash`).

## 5. Règles Strictes pour les IA (Ne pas contourner)
- **Client Léger** : Le paquet `aurora-cli` ne doit **JAMAIS** inclure de dépendances lourdes (pas de PyTorch, pas de transformers). Il ne fait que du réseau et de l'affichage.
- **Sudo et Mots de Passe (Zéro Rétention)** : Si une action nécessite `sudo` ou un mot de passe, l'agent doit le demander à l'utilisateur via le client CLI. Le client l'envoie pour l'exécution immédiate, et il est **immédiatement détruit**. Aucun mot de passe n'est jamais stocké.
- **Git et Pushes (Humanisés)** : Les commits poussés sur GitHub doivent être **100% humanisés**. Aucune trace d'IA, de signature "généré par Aurora" ou autre. Utiliser les conventions standards (ex: `feat: ajout de la route auth`, `fix: correction du bug de rendu`). Les README et instructions d'installation doivent être écrits comme par un développeur humain expert.
- **Affichage Terminal (Diffs et Transparence)** : Le client doit afficher clairement les actions. Toute modification de code doit être présentée sous forme de "Diff" (rouge pour les lignes supprimées, vert pour les ajoutées) pour que l'utilisateur comprenne exactement ce que l'IA fait de manière audacieuse et moderne. Prise de contrôle *headless* possible mais toujours expliquée.
- **Agents Officiels** : Les 37 agents existants dans `.claude/agents/` sont intouchables. Ils ne peuvent être que désactivés ou réactivés.
- **Agents Dynamiques** : Ils peuvent être créés à la volée, supprimés ou sauvegardés s'ils sont jugés utiles.
- **Extensions** : Toujours privilégier l'extension de comportement via les **Skills** (`SKILL.md`) et les **MCP** (Model Context Protocol).

## 6. Pistes d'Amélioration (Pour les futures itérations)
1. *Streaming des plans d'action* : Actuellement, le plan LLM est généré en bloc côté serveur avant exécution. Cela peut être amélioré par un streaming pas à pas.
2. *Sécurité des clés (Services)* : Chiffrer les clés de l'API externe (GitHub, Canva...) stockées dans `.aurora_connections.json` avec une clé maître locale.
3. *Rétention hors ligne* : Si la connexion est coupée pendant une mission, le client CLI devrait pouvoir rattraper les logs via l'historique de la session lors de la reconnexion.
4. *Tests Intégrés* : Ajouter `pytest` dans le `aurora-cli` avec des *mocks* sur `httpx` pour valider l'UI sans solliciter le bridge.
