# Aurora — document maître d’architecture, d’exploitation et d’amélioration

**Référence documentaire unique. Mise à jour ciblée : 7 octobre 2026. Inventaire initial : 24 septembre 2026. Langue : français.**

Ce fichier réunit AuroraIA, Aurora Remote CLI et le dépôt de découverte `aurora-live`. Le mode « standard » désigne ici l’application native Tauri et son interface web habituelle ; il ne faut pas le confondre avec le niveau de permissions CLI `STANDARD`.

Lire [AGENTS.md](AGENTS.md) pour les règles de travail. Commencer par les sections 1 à 5 pour comprendre le système ; consulter ensuite le domaine concerné. L’index des sources et l’annexe des instructions permettent de rester dans ce fichier pour une analyse d’ensemble. Une correction précise exige toutefois de vérifier le code concerné et les tests : aucune documentation ne remplace une analyse exhaustive du comportement.

## Sommaire

- [1. Portée et preuves](#portee)
- [2. Vue d’ensemble](#ensemble)
- [3. Composants, processus et données](#composants)
- [4. Application standard, web distant et CLI](#parite)
- [5. Constats et priorités](#priorites)
- [6. Interface et état](#interface)
- [7. Modules fonctionnels](#modules)
- [8. Bridge et contrats HTTP](#bridge)
- [9. Missions, bus et mémoire](#missions)
- [10. CLI, connexion et livraison](#cli)
- [11. Tunnel et découverte](#tunnel)
- [12. Agents, commandes et skills](#agents)
- [13. Entraînement et modèles audités](#entrainement)
- [14. Stockage, RAM et GPU](#ressources)
- [15. Exploitation et diagnostic](#exploitation)
- [16. Contrats à harmoniser](#contrats)
- [17. Validation et critères de qualité](#validation)
- [18. Conservation documentaire et maintenance](#documentation)
- [19. Index mécanique du code et des routes](#index)
- [20. Instructions et fichiers de compatibilité exportables](#exports)

<a id="portee"></a>
## 1. Portée et preuves

### 1.1 Ce qui a été examiné

Trois dépôts voisins : `AuroraIA/`, `aurora-remote-cli/`, `aurora-live/`. Les chemins sans préfixe de dépôt sont relatifs à AuroraIA. `../aurora-remote-cli/` contient le client Python ; `../aurora-live/` publie un état et une adresse, pas le moteur IA.

La cartographie couvre **1 967 fichiers source/configuration/script et 654 710 lignes**  dont 1 926 fichiers dans AuroraIA et 41 dans le CLI. C’est une cartographie mécanique, **pas une affirmation de lecture sémantique de chaque ligne**. Les points d’entrée, transports, principaux orchestrateurs, registres, modèles, configurations et chemins de stockage ont été examinés directement. L’inventaire retient les fichiers Git et les nouveaux fichiers applicatifs visibles ; il exclut poids, caches, dépendances téléchargées, sorties, bases et secrets.

Le parseur trouve **598 décorateurs de routes** dans cet ensemble, qui inclut aussi tests, outils et sauvegardes. Le bridge principal en définit **14** et les **26 fichiers de blueprints en définissent 280**. Ces 294 déclarations ne prouvent pas que 294 routes sont actives : l’enregistrement des blueprints peut échouer, et certains services enregistrent leurs routes autrement. Ne jamais réutiliser le nombre historique « 237 routes » sans préciser sa date et sa méthode.

Les modifications locales préexistantes ont été prises en compte telles qu’elles étaient sur disque. Elles ne sont ni annulées ni présentées comme des modifications de cette consolidation. Le manifeste `scripts/documentation/source_inventory.json` contient les empreintes du code examiné. Le relevé initial de 1 939 fichiers a été complété par les sources HTML, C/C++/CUDA et configurations de déploiement. Les scripts de documentation ajoutés par la consolidation sont hors de ce relevé applicatif.

### 1.2 Niveaux de certitude à employer

| Marque | Signification | Ce que cela ne prouve pas |
|---|---|---|
| Code vérifié | Chemin ou comportement lu dans les sources citées | Qu’il s’exécute dans chaque déploiement |
| Observation locale datée | Mesure ou requête effectuée sur ce PC | Que l’état persiste après un redémarrage |
| Test ciblé | Cas et assertions réellement exécutés | La qualité générale de toutes les générations |
| Historique | Ancien audit, journal ou proposition archivé | Que son défaut ou son résultat est encore actuel |
| Proposition | Modification suggérée, avec critère d’acceptation | Qu’elle est déjà implémentée |

### 1.3 État historique observé pendant la consolidation du 24 septembre

- Bridge 3001, Ollama 11434, ComfyUI 8188, service des adaptateurs 11435 et viewer 3009 présents. Les contrôles locaux de statut et d’authentification du CLI répondent.
- À cet instant, **aucune écoute n’est constatée sur 3002 ni 1420**. Le bus des missions et Vite doivent être vérifiés avant d’annoncer un fonctionnement de bout en bout. L’interface peut aussi être servie par un bundle compilé ; l’absence de Vite ne suffit pas à conclure que toute interface est indisponible.
- Le CLI s’importe avec le Python système et son aide fonctionne. Le Python `application/.venv/bin/python` manque de `prompt_toolkit` pour cette entrée CLI : cet environnement est celui du backend, pas nécessairement celui du client.
- Le validateur historique `.claude/hooks/validate_agents.py` échoue déjà avant consolidation avec **38 incohérences de rattachement au tracker**. **39 fichiers d’agents** existent ; plusieurs documents et réponses API annoncent encore 37. Ne pas confondre leur présence avec leur activation.
- Aucun test de génération lourde, mission distante publique, entraînement, publication GitHub ou déploiement n’a été lancé pour écrire cette documentation.

### 1.4 Maintenance du 4 octobre 2026 : observations et limites

Le PC utilise le noyau `7.0.0-34-generic`, sans module NVIDIA pour ce noyau. Le module installé correspond à `7.0.0-31-generic` ; `nvidia-smi` échoue et ComfyUI redémarrait en boucle avec `No CUDA GPUs are available`. Le démarrage courant n'utilise pas une option recovery dans `/proc/cmdline`. L'utilisateur confirme que le message « safe mode » demandait F1 pour entrer dans le BIOS/UEFI : c'est une alerte du firmware, distincte de la panne NVIDIA sous Ubuntu. La carte mère est une ASUS ROG CROSSHAIR X870E HERO, BIOS 2306 du 15 juin 2026. [ASUS décrit plusieurs causes possibles d'une invite F1](https://www.asus.com/support/faq/1029955/) ; le message exact et sa cause restent inconnus. Le manque de stockage n'est pas une cause démontrée. Aucun réglage BIOS n'a été modifié. Le montage optionnel `AURORA_MODELS` est absent, avec `nofail` et un délai de 10 secondes.

Environ 114 Gio sont disponibles sur le SSD après le nettoyage de 339,9 Mio de caches reconstruisibles et de l'installeur VS Code déjà installé. Les poids, environnements, données, conversations, sorties et worktrees ont été conservés. Les six services utilisateur Aurora sont arrêtés et désactivés temporairement au démarrage ; Ollama système reste actif sans modèle résident, faute de droits administrateur pour l'arrêter. Aucun tunnel public n'est lancé et la découverte `aurora-live` est fermée.

Le CLI local était sur `master`, 15 commits derrière `origin/main`. Sa branche `main` contient désormais JOBIA 1.2.1, les commandes locales adaptatives et les thèmes existants, plus les correctifs de raccordement décrits en section 10. Le serveur a incorporé le registre applicatif de `origin/main` et les métriques locales non publiées. Les sources indispensables `cli_artifacts.py`, `comfy_runtime.py` et `neural_process.py` sont ajoutées au suivi Git : elles étaient importées par du code suivi mais restaient uniquement locales.

Les contrôles exécutés comprennent les tests CLI et serveur avec modèles substitués, les types TypeScript, le build web et la conformance comportementale existante. Ils ne prouvent ni une génération réelle, ni le trajet public SSE, ni la compatibilité sur un Windows/macOS réel, ni une AGI. Les relevés JSON et journaux détaillés restent privés dans `~/maintenance-pc-2026-10-04`. L'index et les empreintes de septembre restent historiques ; `--check-code` signale les écarts encore à revoir, sans les approuver automatiquement.

### 1.5 Missions vérifiables et interface terminal JOBIA 1.3.0

Le moteur des missions conserve l'objectif original séparément du contexte de dialogue, de la mémoire et des conseils. Une boucle unique remplace l'Oracle et le Gardien exécutés systématiquement avant chaque tâche. Elle établit un plan pour les actions, découvre les scripts disponibles, expérimente, conserve les observations et vérifie les critères avant de terminer. Une revue avec un contexte LLM séparé recherche les écarts ; c'est un jugement du modèle, pas une preuve empirique ni une note de qualité.

`agi_core/mission_store.py` conserve les demandes, événements numérotés, états et checkpoints dans SQLite. Les clés d'idempotence évitent une seconde acceptation de la même requête ; un bail désigne un seul exécutant et rejette les événements/checkpoints de son prédécesseur. Les opérations de fichiers volumineuses s'exécutent hors de la boucle asynchrone pour laisser passer arrêt et renouvellement du bail. Le bridge peut être redémarré sans perdre le flux. Une action interrompue reste de résultat inconnu : sa reprise impose d'inspecter l'état avant de la réexécuter. Cela ne garantit pas une transaction exactement une fois avec chaque outil externe.

JOBIA 1.3.0 ajoute une interface plein écran réelle avec conversation persistante, plan, critères, observations, fichiers reçus, choix de thème/modèle, journal, arrêt et reprise. Les tours précédents sont transmis au pont comme contexte consultatif borné, séparé de la requête actuelle ; une demande incertaine conserve exactement son payload et sa clé pour réessayer son acceptation. Les opérations locales de cette interface sont exécutées dans un processus séparé pour permettre l'arrêt de l'arbre de processus. Les scripts d'installation Linux/macOS et Windows partagent toujours le même installateur ; la détection de version Windows est corrigée et la mise à jour ne force plus la réinstallation de toutes les dépendances.

Le premier passage CI a détecté des hypothèses POSIX dans les anciens tests CLI et deux lacunes Windows : l'occupation mémoire dépendait de `ps`, et les chemins système n'étaient pas comparés comme des chemins natifs. Le gouverneur utilise désormais les mesures résidentes de `psutil` sur les trois plateformes ; les protections de provisioning résolvent aussi Windows, Program Files et ProgramData avec leurs règles de casse/volume. Une cible de provisioning résolue doit rester dans son répertoire, y compris lorsqu'un lien symbolique mène à une cible extérieure déjà existante. Les assertions de bits POSIX ne sont pas présentées comme des mesures des ACL NTFS. Aucun processus utilisateur n'est arrêté par l'attente de mémoire.

La mémoire SQLite ferme explicitement chaque connexion après lecture/écriture : le contexte transactionnel SQLite ne ferme pas lui-même le fichier. Cette correction évite les descripteurs en attente de ramasse-miettes et les fichiers encore verrouillés sous Windows/Python 3.13.

Les réglages Ollama sont ceux du modèle/moteur par défaut, avec surcharge explicite `AURORA_MODEL_OPTIONS`. Les durées et débits viennent des réponses du moteur, sans score de performance inventé. Les outils et l'historique envoyés au modèle restent bornés ; le journal durable conserve les événements. La concurrence est configurable et vaut un par défaut pour éviter de multiplier les chargements sans mesure de capacité. Les analyses de fond sont facultatives et désactivées par défaut pour privilégier la requête en cours. L'état observable du runtime n'est pas une preuve de conscience subjective.

Les tests utilisent des modèles substitués et des services HTTP temporaires : écritures/lectures et commandes réelles dans des dossiers temporaires, critères échoués puis réparés, coupure après un effet sans rejeu automatique, idempotence, bail, SQLite après réouverture, SSE après reconstruction du bridge, revue refusant une conclusion non étayée et vrai clavier de l'interface plein écran. Le stockage Auto-RL utilise des verrous Windows/POSIX et des fichiers UTF-8 ; cela ne rend pas son contrôleur d'entraînement Linux portable. Les workflows GitHub ajoutent une matrice Linux/Windows/macOS et Python 3.10/3.13 ; leur résultat est à consulter pour le commit publié. Aucun essai réel des modèles, aucune connexion MCP effective, aucun tunnel public ni unification complète des pipelines React/CLI n'est démontré par ces contrôles.

Validation finale observée le 4 octobre : **716 tests CLI et 97 tests serveur/Auto-RL réussis localement**, respectivement 18 tests ignorés/5 sous-tests et 6 sous-tests. Les six configurations de la [matrice CLI au commit `f24286e`](https://github.com/juancodepyandc/aurora-remote-cli/actions/runs/37172284511) et les six de la [matrice serveur au commit `ad14c20`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37172228136) réussissent sur Linux, Windows et macOS, avec Python 3.10 et 3.13. Les exclusions POSIX et dépendances facultatives sont visibles dans les journaux de chaque job. L'installation réelle locale de JOBIA 1.3.0, son démarrage et la correspondance des sources installées sont vérifiés. Un aperçu du vrai rendu prompt_toolkit, sans mission ni inférence synthétique, et les journaux restent privés dans `~/maintenance-agi-2026-10-04`. Ces résultats valident les cas exécutés ; ils ne mesurent pas la qualité des modèles et ne certifient pas tous les moteurs de chaque module sur chaque OS.

### 1.6 Essais initiaux de modèles réels sur CPU, jusqu'au commit `71efc87`

Le 4 octobre, des essais utilisent réellement Ollama 0.31.1 et les poids installés, sans modèle substitué ni tunnel public. `qwen3-coder:30b` charge environ 19,05 Go dans la RAM, avec `size_vram=0` et une fenêtre réelle de 4 096 tokens. Le PC a 30 Gio de RAM ; le pilote NVIDIA reste indisponible. Le modèle principal `qwen3-coder-next:q4_K_M`, dont les poids font environ 51,74 Go, n'est pas chargé sur ce CPU. Les réglages d'échantillonnage restent natifs, sans note de performance inventée. Les résultats détaillés restent privés dans `~/maintenance-agi-2026-10-04/tests-reels`.

Le parcours testé relie le CLI installé, les routes CLI/authentification de production, le flux SSE, le bus IPC, le daemon et le vrai moteur Ollama, avec des données et dossiers isolés. Le lancement du bridge utilise un bootstrap privé qui évite la publication Gist, le tunnel et les tâches de préchauffage du démarrage complet : il ne constitue pas une validation de toutes les routes natives/web. Le vrai clavier de l'application plein écran prompt_toolkit, avec entrée programmée et affichage factice, accomplit une mission de lecture avec le vrai modèle et conserve sa conversation ; cela ne certifie pas la qualité visuelle sur chaque terminal.

Les essais exposent des limites : deux calculs directs d'optimisation sont faux ; la comparaison de relevés et la reconnaissance d'une donnée manquante réussissent. Avec Python, le modèle trouve le bon optimum, 64 pièces pour 136 unités, mais les premières missions échouent sur l'écriture ou les clés JSON demandées. Après le premier correctif de format, une fonction d'union d'intervalles passe 56 cas indépendants, tandis que la mission ne converge pas : le modèle a inventé une valeur attendue incorrecte dans ses propres tests. Un rôle et un skill sont effectivement créés ; le worker CSV omet une ligne et ne termine pas correctement. Un essai de rôle arrêté par l'opérateur est explicitement exclu des conclusions sur l'autonomie.

Ces observations conduisent aux correctifs suivants :

- Les appels d'outils et les verdicts de revue utilisent le [format structuré natif d'Ollama](https://docs.ollama.com/capabilities/structured-outputs), avec validation côté application. La lecture d'un petit fichier donne son empreinte sur les octets réellement observés ; une écriture gardée exige cette empreinte et signale clairement son incompatibilité avec un fichier neuf. Les vérifications rejettent les champs inconnus au lieu de les ignorer, et expliquent les erreurs de forme d'`argv`.
- Le budget d'historique tient compte de la fenêtre du runner chargé et du rapport caractères/tokens observé sur les petits prompts, avec réserve fondée sur les réponses mesurées. C'est une estimation, pas un tokenizer exact ni une augmentation automatique de la capacité du modèle. L'objectif et l'état indispensable restent conservés ; le début et la fin d'une dernière observation trop longue sont explicitement présentés comme tronqués. La revue est aussi bornée et lit les fichiers de sortie actuels : un ancien hash ou des constantes retapées dans un test ne prouvent pas leur contenu sémantique.
- Avant de lancer un processus, le checkpoint enregistre son identité. Après interruption, la même commande reconnue est bloquée, y compris ses alias Python, ses drapeaux et l'enveloppe `timeout` ; les anciens checkpoints `run_command` sont pris en charge. Les shells opaques restent comparés par leur texte exact. Ce mécanisme ne constitue ni un sandbox OS, ni une transaction exactement une fois pour tout shell, worker ou outil externe. Les publications de fragments ne génèrent plus le journal INFO répétitif du bus.

Avant le durcissement de la section 1.7, le dernier essai réel de reprise conserve l'objectif, le script et le checkpoint, arrête le processus, redémarre le bridge et le daemon, puis conserve exactement une invocation observée et un compteur à 1. Deux tentatives de rejeu sont empêchées par le moteur ; le fichier final porte la mention de reprise demandée. Malgré ces faits, la revue du modèle rejette à tort la récupération autorisée et la mission termine `blocked`. **La protection contre ces rejeux est observée ; la réussite autonome complète de cette mission ne l'est pas dans cet essai initial.** La revue est un garde de conclusion fondé sur un jugement LLM susceptible de faux positifs et négatifs, pas une preuve empirique. L'inspection de l'état seule n'empêchait pas les rejeux dans les essais antérieurs.

Un test direct de vision CPU avec `qwen3-vl:8b` reconnaît les formes, leurs couleurs et leur ordre, ainsi que le nombre imprimé 73, sur une image de référence construite par code. Le trajet complet de cette requête prend 51,01 secondes, avec `size_vram=0` ; la requête indique qu'il existe trois formes. Cela valide ce seul cas d'identification et de lecture, sans mesure aveugle de comptage, sans passage par le module Image/3D et sans génération FLUX/TRELLIS.

Les contrôles de régression locaux atteignent **110 tests réussis et 9 sous-tests**, avec des modèles substitués pour ces tests logiciels. Les essais réels ne démontrent pas une AGI, une conscience subjective, tous les modules, un trajet public, une connexion MCP effective ou une compatibilité de chaque moteur sur chaque OS. Les services de test et les modèles résidents sont arrêtés à la fin ; les services utilisateur restent dans leur état arrêté/désactivé. Le résultat de la matrice du commit publié est consigné avec les preuves finales, distinctement des générations Image/3D GPU encore bloquées.

### 1.7 Contrats d'outils et évaluation indépendante des missions

La régression réelle de la section 1.6 motive un durcissement du protocole de mission : `agi_core/mission_protocol.py` décrit les arguments de chaque outil pour le décodage structuré Ollama. Le schéma ne propose que les outils permis au niveau courant ; après `set_plan`, chaque contrôle doit citer l'un des critères exacts du plan dans l'exécuteur. Le décodage cible les critères encore non vérifiés ; lorsque tous le sont, il permet aussi de les recontrôler. L'état envoyé au modèle et chaque résultat d'outil rappellent les critères manquants. L'exécuteur contrôle les arguments avant les effets, rejette les champs inconnus et les choix ambigus entre `argv` et `command`, et valide le statut de conclusion. Cela corrige la forme des appels ; un schéma JSON ne garantit pas la justesse du raisonnement.

`verify` dispose de contrôles `text` et `json` sur les octets effectivement lus, avec empreinte SHA-256. Le texte vérifie une égalité ou une inclusion ; le JSON vérifie une valeur complète, les clés exactes et/ou les types déclarés. Les clés dupliquées, valeurs non finies et confusions entre booléen et entier sont rejetées. Les contrôles de commande exigent le code de sortie 0 par défaut ; `expected_exit_code` permet de vérifier explicitement une erreur attendue avec sa sortie réellement observée. Une exception ne passe pas automatiquement le contrôle. Les contrôles purs de fichiers/texte/JSON sont relancés avant et après la revue, sans rejouer les commandes ; un changement d'empreinte impose une nouvelle vérification. Les lectures sont bornées par le budget de sortie configuré ; les gros fichiers demandent une vérification en flux par commande. Un contrôle des clés seul ne prouve ni les valeurs ni l'optimalité d'un calcul. Le modèle reste responsable d'associer ses contrôles aux vrais critères demandés.

Un lot partiellement échoué conserve la réussite des seuls critères dont tous les contrôles du lot réussissent ; un nouveau contrôle échoué retire la validation précédente de ce critère. Les contrôles purs enregistrés sont dédupliqués. Une écriture strictement identique aux octets UTF-8 présents conserve leur date et les validations, avec `changed=false` ; une mutation réelle invalide les contrôles. Les écritures atomiques préservent les sauts de ligne fournis sur Windows comme sur POSIX.

Le budget de contexte se réajuste aussi sur des historiques denses lorsque leur nombre de tokens laisse la place à la plus longue réponse mesurée. Une fenêtre saturée réduit l'estimation précédente selon le déficit de tokens observé, sans réapprendre un ratio gonflé par une entrée éventuellement tronquée. Les budgets n'augmentent pas à partir de prompts plus clairsemés ; le changement de modèle remet la calibration à zéro. Cela reste une estimation caractères/tokens, pas une garantie de tokenizer ni une extension de la fenêtre. Un contexte trop petit pour l'objectif et l'état obligatoires produit une erreur explicite avec travail conservé.

`inspect_csv` lit un instantané borné des octets du CSV sans mutation et renvoie son empreinte, les colonnes, le nombre de lignes de données et, pour les colonnes déclarées entières, compte/somme/min/max exacts. Il utilise `csv.DictReader` sans sauter une deuxième fois l'en-tête, prend en charge BOM UTF-8, CRLF et champs cités multilignes, et rejette les en-têtes dupliqués, lignes incohérentes et valeurs non entières demandées. L'aperçu peut être tronqué ; les agrégats portent sur toutes les lignes de l'instantané. Un CSV dépassant la borne doit être traité par un outil en flux.

Toute conclusion `completed` passe par la revue, y compris lorsque le modèle n'a établi aucun plan. La revue exige pour chaque objection une citation exacte de la requête et des identifiants d'observations disponibles, ou une liste vide pour une preuve absente. Un verdict rejeté ou mal formé est réexaminé une fois dans un contexte séparé. Les objections contradictoires, citations absentes de la requête et identifiants inventés ne sont pas acceptés comme verdict valide. Une citation valide peut néanmoins être interprétée à tort. La reprise autorisée et les corrections qui remplacent des tentatives échouées sont explicitement prises en compte. Les deux passages utilisent le même modèle : cette validation syntaxique et cette relecture restent des jugements susceptibles d'erreurs sémantiques ; elles n'équivalent pas à une preuve indépendante de qualité.

Les observations de processus conservent l'identité, le lancement effectif, la sortie capturée et le statut. Après annulation, elles décrivent un résultat inconnu et sont transmises à la revue : un lancement prouvé ne devient pas une réussite inventée. Pour un ancien checkpoint, la reprise peut reconstruire cette observation à partir du `command_output` durable de l'action en attente ; une sortie absente ne prouve pas le lancement. La protection contre le rejeu garde les limites décrites en section 1.6.

Un rôle enregistré est transmis au worker comme contexte consultatif ; sa tâche originale reste distincte et ses permissions sont bornées par le parent. Les autres étapes du parent ne sont plus recopiées comme objectif du worker, pour limiter la répétition d'actions déjà effectuées. Le lancement crée un seul worker, sans l'étage intermédiaire précédent. Le rapport contient le statut, les critères et les dernières observations ; un worker `blocked` ne devient pas un contrôle réussi du parent. Un échec de worker annule et attend les autres tâches du groupe. La reprise rafraîchit les instructions du protocole sans changer l'objectif conservé.

`scripts/evaluation/mission_regression.py` fournit des missions locales avec de nouvelles données reproductibles par seed : optimisation entière, CSV avec rôle/skill/worker et correction d'union d'intervalles. Les évaluateurs contrôlent les fichiers réels, les types, les contraintes, les octets de l'entrée CSV et 85 cas de code indépendants. La réussite exige aussi le statut `completed` ; un code correct produit par une mission non terminée reste un résultat partiel. Les seeds font varier les fixtures, pas les réponses du modèle. Ce corpus étroit ne mesure pas tous les domaines et ne fournit aucune certification AGI. Les commandes utilisent toujours l'hôte sans sandbox OS ; les cas ne sont pas présentés comme un benchmark sécurisé contre l'accès aux évaluateurs.

Exemple après vérification du modèle réellement disponible, avec le Python applicatif et un nouveau dossier de preuves :

```bash
application/.venv/bin/python scripts/evaluation/mission_regression.py \
  --model MODELE_INSTALLE --output /CHEMIN/PRIVE/NOUVEAU_DOSSIER --seed 15791
```

L'évaluateur ne démarre aucun service, ne remplace aucune réponse et n'entraîne aucun modèle. Il conserve les paramètres natifs ou les surcharges explicites, les durées et métriques réelles, les prompts, les événements et les empreintes des sources. `--case` sélectionne un cas et `--timeout` fixe son délai explicite, par défaut 480 secondes ; cette limite figure dans les résultats avec le statut, le plan et les critères finaux. Les seeds des cas restent identiques entre un corpus complet et une sélection. Le code retour vaut 1 lorsqu'au moins une mission échoue. Le parcours CLI/SSE/IPC et la reprise après redémarrage demandent leurs essais séparés ; les preuves locales ne certifient pas le tunnel ou les moteurs Image/3D.

Observations du 4 octobre pendant ces correctifs : deux reprises réelles après arrêt, redémarrage du bridge/daemon et reprise terminent `completed`, en 259,13 puis 155,25 secondes. Chacune conserve le compteur à 1, une seule invocation observée, le script et l'objectif originaux, avec inspection avant les nouveaux effets. Le corpus de seed `281049713` termine l'optimisation en 244,34 secondes avec l'optimum indépendant 54, et la correction de code en 145,55 secondes avec 85 cas indépendants réussis. Son CSV échoue au délai de 480 secondes ; l'essai suivant à 900 secondes termine son premier worker avec les bonnes valeurs 8/-25 mais relance un audit et ne crée pas `summary.json`. Les premières tentatives échouées restent conservées : ces reprises et ces succès ne sont pas un taux de réussite général. Les fichiers `results.json` privés conservent l'empreinte de la version de source de chaque passage, distincte des correctifs ultérieurs de progression et de contexte.

Les contrôles logiciels de cette version atteignent **134 tests réussis et 29 sous-tests**, avec modèles substitués pour ces tests logiciels. Les mesures réelles utilisent toujours `qwen3-coder:30b` sur CPU et les réglages natifs ; le modèle principal, les générations Image/3D GPU, le tunnel public et chaque module sur chaque OS restent non validés. Ni ces tests, ni l'introspection du runtime ne démontrent une AGI ou une conscience subjective. Les résultats CI du commit publié et les essais supplémentaires sont consignés séparément avec les preuves finales privées.

Au commit `e60655a`, les six configurations de la [matrice des contrats de mission](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37195658660) réussissent sur Linux, Windows et macOS, avec Python 3.10 et 3.13. L'essai CSV final de la même seed, avec adaptation du contexte et délai de 480 secondes, reste `stopped` sans `summary.json`. Son worker et sa revue acceptent à tort 7 lignes/-42, alors que `inspect_csv` mesure 8/-25 sur les octets inchangés ; le worker a de nouveau sauté la première ligne de données après l'en-tête. Le parent observe la contradiction, mais ne livre pas le fichier attendu. Le contexte reste mieux borné (budget final observé 13 186 caractères), sans résoudre cette erreur sémantique. **La délégation fiable et la revue de calcul restent donc non démontrées pour ce cas** ; des contrôles syntaxiques réussis ne permettent pas d'annoncer une AGI.

### 1.8 Contrats de délégation et calculs dérivés des entrées

L'échec CSV de la section 1.7 motive un contrôle `verify` de type `csv_json` : `path` désigne le CSV d'entrée, `json_path` le JSON livré, `row_field` la clé du nombre de lignes et `sum_fields` associe chaque clé JSON de somme à sa colonne CSV entière. Les noms et valeurs ne sont pas imposés par un cas d'évaluation. Le runtime calcule les agrégats depuis toutes les lignes de données puis compare les clés, types et valeurs du JSON complet. Il renvoie attendu/observé et les empreintes des deux fichiers ; `source_sha256` facultatif peut exiger la conservation des octets de l'entrée. Les lectures restent bornées comme `inspect_csv`. Le profil est celui des sommes entières, pas des décimales ou de tous les calculs tabulaires.

`spawn_agent` exige maintenant un lot non vide de `checks`, validé avant tout lancement, avec les critères exacts du parent. Le contrat est transmis au worker sans remplacer sa tâche originale ou ses permissions. Après les workers, le parent exécute lui-même ces contrôles ; `passed` exige leur réussite et le statut `completed` de tous les workers. Un rapport assuré ou une approbation du modèle ne remplace pas ce contrôle. Les critères effectivement contrôlés sont validés après les effets du worker ; les contrôles purs sont relus avant et après la revue finale. Le type `agent` vérifie l'existence et l'empreinte de la définition actuelle d'un rôle enregistré ; il ne prouve pas son exécution.

Une délégation acceptée dont tous les contrôles sont purs (fichier, texte, JSON, CSV/JSON, rôle enregistré) peut être réutilisée lorsque son contrat et toutes les empreintes observées restent identiques. Une entrée/sortie modifiée impose un nouvel essai. Les contrôles de commande et de source distante ne sont pas réutilisés automatiquement. Le cache borne ses derniers contrats dans le checkpoint ; ce mécanisme ne garantit pas une transaction exactement une fois avec n'importe quel worker ou outil externe. Les faits d'acceptation apparaissent avant les longs rapports dans les observations envoyées au modèle ; les extraits longs marquent explicitement la troncature.

Les créations d'extension identiques sont réutilisables : le skill conserve son fichier, le rôle son registre. Une définition différente produit un échec sans écraser la ressource existante ni invalider les contrôles par une mutation fictive. La comparaison de skills accepte les représentations LF/CRLF équivalentes sans réécrire leurs octets ; les nouveaux skills préservent les sauts de ligne fournis. Les fonctions publiques de création continuent de refuser un doublon ; seule la boucle de mission propose cette réutilisation explicitement marquée `changed=false`.

Le schéma commun aux contrôles `verify` et `spawn_agent` exige chaque champ `criterion` une seule fois, malgré leurs branches partagées en mémoire. Les alternatives d'appels structurés sont des objets complets : chaque outil contient ses arguments typés et ses champs obligatoires, y compris les variantes exclusives commande/argv et tâche/tâches. Les contraintes JSON et texte exigent aussi un contenu ou une structure à vérifier. Cela limite les formes invalides observées avec le décodage natif ; l'exécution valide encore les appels avant leurs effets. Les tests ciblés reproduisent le saut d'une ligne dans un vrai sous-processus, rejettent son JSON erroné malgré un worker `completed`, puis valident la réparation ; ils contrôlent aussi une modification de l'entrée, un conflit de ressource, les permissions, les octets BOM/CRLF et la conservation des faits devant un rapport volumineux. Les modèles y sont substitués. L'évaluateur réel ajoute un journal JSONL consultable pendant la mission ; son contrôle CSV exige une délégation réellement exécutée avec le rôle demandé et acceptée, en plus des fichiers et des chiffres corrects.

Les nouveaux plans structurés déclarent `required_tools`, les outils nécessaires à la demande originale, filtrés par les permissions. Les anciens plans et checkpoints restent acceptés sans ce champ. Le moteur conserve séparément les outils effectivement exécutés avec succès, dont ceux d'un worker accepté ; un appel rejeté ne figure pas dans ce registre. La fin `completed` exige aussi l'exécution des outils déclarés dans le plan courant. Les observations indiquent les actions encore manquantes et n'invitent à conclure qu'après leur réussite et les vérifications. Ce garde empêche de remplacer une délégation déclarée obligatoire par la simple présence d'un rôle. Le modèle choisit encore les exigences de son plan : le registre ne prouve pas, à lui seul, l'interprétation correcte de toute demande ni l'exécution d'une action qu'il a omise ou retirée du plan.

Ces contrats améliorent les preuves disponibles ; le modèle choisit encore les contrôles et leurs critères. Un contrôle de présence ou une existence de rôle reste insuffisant pour démontrer la justesse d'un calcul. La portée des essais réels et leurs empreintes sont conservées dans les résultats privés ; aucune certification générale d'AGI ou de conscience n'en découle.

Au commit `75181de`, les contrôles logiciels locaux atteignent **150 tests réussis et 47 sous-tests**, avec modèles substitués ; les six configurations de la [matrice serveur](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37213032573) réussissent. Le premier essai intermédiaire des contrats (seed `281049713`, délai CSV 480 secondes) livre les bons chiffres 8/-25 et préserve l'entrée, mais ne lance pas correctement le worker et reste `stopped`. Il motive les corrections de schéma et de continuité décrites ci-dessus ; ce résultat partiel n'est pas compté comme une mission réussie.

Le corpus réel du commit `75181de` utilise une nouvelle seed `915470226`. L'optimisation réussit en 205,16 secondes avec un optimum indépendant de 60 pièces. Le CSV sauvegarde les bons chiffres 12/104 et préserve son entrée, mais la boucle annonce `completed` sans avoir exécuté la délégation : l'évaluation indépendante classe le cas en échec. La réparation de code passe 85 cas indépendants, mais la mission reste `stopped` à 480 secondes et n'est pas comptée comme réussie. Ces observations motivent le registre d'exécution et le schéma complet ci-dessus. Les essais suivants conservent leurs propres empreintes ; aucun résultat d'un code intermédiaire n'est attribué à sa version finale.

Le passage logiciel du commit `08e82c1` atteint **153 tests réussis et 47 sous-tests** ; les six configurations de sa [matrice serveur](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37214496426) réussissent sur Linux/Windows/macOS, Python 3.10/3.13. Il vérifie notamment qu'une délégation déclarée mais rejetée empêche la fin `completed` même si le modèle approuverait le résultat, que le suivi indique cette action encore manquante, et que les outils exécutés par un worker accepté sont conservés. Un essai réel intermédiaire avec le schéma complet et le registre livre encore 8/-25 et préserve l'entrée, mais reste `stopped` à 480 secondes sans worker exécuté. Il révèle un contrat JSON sans contenu à vérifier et un message invitant trop tôt à conclure ; ces deux défauts sont corrigés au commit `08e82c1`.

L'essai réel final de `08e82c1` (seed de cas `915470227`, même modèle CPU et paramètres natifs) crée le skill et le rôle AuditCSV, lance réellement ce rôle, et son worker termine `completed`. Le parent accepte les agrégats depuis le CSV réel ; l'évaluateur indépendant confirme le JSON 12/104, les octets d'entrée préservés et la délégation exécutée avec le rôle demandé. Le parent revient néanmoins sur des créations de skill et ne termine pas ses contrôles : la mission reste `stopped` à 480,00 secondes, après 30 itérations du parent. **Le livrable et le worker sont validés pour ce cas ; la mission globale reste en échec.** Les cinq empreintes de sources du relevé concordent avec cette version publiée. Le modèle est déchargé et les services utilisateur restent arrêtés/désactivés après les essais. Ces observations ne confirment ni une AGI ni une conscience, et n'établissent pas la convergence de toute mission.

### 1.9 Continuité des vérifications et découverte des outils internes

Les journaux de `08e82c1` montrent que la commande de lecture `ls -l` efface les critères déjà vérifiés, et qu'`inspect_tool(create_skill)` échoue parce que l'inspection ne découvre que les scripts Python. Ces défauts concernent la boucle `agi_core` utilisée par les missions du CLI, pas une parité démontrée avec tous les orchestrateurs React.

Après un effet possible, le moteur relit les contrôles purs des critères acquis et conserve seulement ceux dont tous les résultats passent avec les mêmes empreintes. Des octets modifiés invalident donc le critère même si un contrôle de simple présence passe encore. Les autres critères restent à vérifier ; aucune exigence non contrôlée n'est automatiquement satisfaite. Les preuves mêlant des commandes ou sources ne sont pas conservées par ce mécanisme, et aucune commande n'est relancée pour rafraîchir une preuve. Les checkpoints anciens sans empreintes restent acceptés, mais leurs critères sont invalidés après un effet ; une action interrompue conserve ses protections contre le rejeu. Les contrôles purs d'un lot contenant une commande sont aussi relus après les commandes : leur verdict porte sur les fichiers finaux, pas sur une observation faite avant leur modification.

`list_tools` et `inspect_tool` découvrent maintenant les outils internes du protocole et les scripts, avec leurs modes d'appel distincts. Les outils interdits par les permissions et la délégation récursive des workers ne sont pas proposés. `list_skills` fournit les chemins et empreintes actuelles des définitions découvertes ; `verify(kind="skill", name=...)` contrôle une définition existante sans la recréer. Ce contrôle ne prouve ni son exécution ni sa qualité sémantique. Les références observées aux ressources créées/découvertes restent dans le contexte borné du checkpoint ; elles doivent être contrôlées de nouveau pour constituer une preuve actuelle.

Le compromis est une relecture supplémentaire des fichiers après les effets, en échange de critères conservés sans leur attribuer une mutation inconnue. Ce n'est ni une classification heuristique des commandes comme « lecture seule », ni une hausse mesurée de performance du modèle. Les tests logiciels utilisent de vrais fichiers et sous-processus avec réponses LLM substituées ; **167 tests et 56 sous-tests réussissent localement**. Ils couvrent les modifications d'une seule sortie, les octets d'un CSV dont les agrégats restent identiques, les lots mixtes, l'absence de rejeu, les permissions et les définitions réellement sauvegardées.

L'évaluateur indépendant ajoute un quatrième problème, `route-planning` : il doit livrer un trajet de coût minimal sous budget d'énergie, ou prouver l'absence de trajet admissible, depuis un graphe généré par seed et conservé sans modification. Le contrôle énumère les chemins indépendamment du code produit, vérifie les arêtes, les coûts, les types et les octets d'entrée ; les mauvaises solutions sont rejetées dans les tests du contrôleur. Aucun résultat du modèle réel ni confirmation d'AGI n'est déduit de ces seuls tests logiciels.

Les six configurations de la [matrice serveur au commit `276d46f`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37226267008) réussissent. Le corpus réel de cette version, seed de base `3692879451`, utilise `qwen3-coder:30b` sur CPU avec les options natives vides et le contexte observé de 4096 tokens. La mission CSV termine **`completed` en 337,53 secondes**, après 21 itérations du parent : skill et rôle créés, worker réellement exécuté et accepté, JSON 8/68 juste et octets d'entrée préservés par le contrôle indépendant. C'est une réussite complète de ce cas, sans intervention dans sa boucle.

Les trois autres livrables de ce corpus passent leurs contrôles indépendants, mais leurs missions échouent : optimum 114 trouvé, réparation réussissant 85 cas, et absence de trajet admissible correctement représentée. L'optimisation et le trajet atteignent le délai de 480 secondes ; leurs plans imposent respectivement `run_tool` et `inspect_csv`, outils non demandés et jamais exécutés. La réparation échoue après 249,79 secondes parce que le contexte ne contient plus l'objectif et l'état critique, malgré les six critères vérifiés. Ces échecs globaux restent consignés séparément des livrables corrects et motivent la section suivante. Les cinq empreintes des sources concordent avec la version publiée ; aucun résultat intermédiaire n'est attribué à une correction ultérieure.

### 1.10 Outils obligatoires rattachés à la demande et contexte compact

Le garde des outils obligatoires de la section 1.8 ne doit pas transformer les choix d'implémentation du modèle en exigences de l'utilisateur. Les nouveaux plans conservent comme `required_tools` uniquement les noms d'outils littéralement présents dans la demande originale et déclarés obligatoires par le modèle ; les autres choix sont rendus comme `optional_tools` et ne bloquent plus la fin. La mention seule ne crée pas d'obligation : le modèle doit encore interpréter la demande, notamment une négation. Cette liste n'est donc pas une preuve générale d'interprétation sémantique. Les missions en cours reprises filtrent aussi leurs anciennes obligations ; une mission déjà terminée reste idempotente.

Le schéma du décodage natif limite les outils obligatoires aux noms explicites et permis, et exige la liste vide lorsqu'aucun nom n'est présent. Une demande CSV nommant `create_skill`, `create_agent` et `spawn_agent` conserve ces obligations si son plan les déclare. Les calculs et les vérifications des critères restent nécessaires pour les autres demandes ; retirer un outil facultatif ne marque aucun critère comme satisfait.

Le contexte envoyé au modèle contient l'objectif original une seule fois, intact dans son message utilisateur, et chaque critère exact avec son état de vérification. Lorsque la capacité observée manque, le moteur retire d'abord des éléments anciens de l'historique, du plan et des références aux délégations acceptées. Ces éléments restent dans le checkpoint ; le résumé compte ses omissions. L'objectif, les critères, les obligations d'action, les références aux ressources et les traces des processus interrompus ne sont pas tronqués pour faire tenir la requête. Si cet état critique dépasse encore la capacité, l'échec reste explicite. Aucune hausse fixe du contexte ou option de performance du modèle n'est ajoutée.

Les tests logiciels atteignent **172 réussites et 56 sous-tests**, avec réponses de modèles substituées. Ils vérifient la conservation des noms explicitement déclarés, l'absence d'obligation automatique par mention, le schéma de liste vide et la réduction du contexte sans modification de l'objectif, des critères, des traces d'interruption ou du checkpoint. L'évaluateur consigne désormais aussi le dernier message d'erreur de la mission, distinct de son délai et du verdict indépendant sur le livrable.

Les six configurations de la [matrice serveur au commit `3f5017b`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37229096450) réussissent. Son corpus réel frais, seed `2472336201`, garde le même modèle CPU, les options natives vides et le contexte de 4096 tokens. Le CSV termine `completed` en 315,74 secondes avec rôle/skill créés, worker exécuté, agrégats 10/268 justes et entrée conservée. La réparation termine `completed` en 375,40 secondes et passe les 85 cas indépendants, sans l'erreur de capacité du corpus précédent. Le trajet livre le bon optimum 17, énergie 23, et préserve l'entrée, mais sa mission reste `stopped` à 480 secondes : lectures et plans se répètent après des contrôles textuels incompatibles avec le JSON formaté.

L'optimisation de ce corpus termine `completed` en 205,90 secondes, mais le contrôle indépendant la classe **en échec** : a=18, b=0 et 162 pièces sont justes, tandis que `consommation=163` copie le budget au lieu du coût réel 162. Les contrôles de clés/types et le relecteur du même modèle approuvent à tort ce calcul. Ce faux positif est conservé ; un statut `completed` et un avis du modèle ne sont pas une preuve de justesse générale. Les cinq empreintes de sources ont été comparées avant la correction suivante et concordent. Le résultat global est deux réussites sur quatre cas, pas une confirmation d'AGI.

### 1.11 Relations numériques sauvegardées et détection de cycles

Le contrôle `json` accepte désormais une liste non vide `expressions`. Chaque expression désigne le JSON sauvegardé sous le nom `data` et peut comparer ses champs, indices et littéraux, calculer +, -, *, /, //, %, et combiner des booléens. Le moteur interprète l'AST sans `eval` : appels, attributs, imports, compréhensions, affectations et puissances sont interdits, même dans une branche qui serait ignorée. La syntaxe entière est validée avant une délégation ; l'évaluation utilise ensuite les valeurs réelles. Un booléen n'est pas un nombre pour l'arithmétique et une valeur simplement non vide n'est pas un verdict booléen. Les expressions sont bornées à 512 nœuds de syntaxe et à la taille de sortie de la politique ; les vérifications complexes restent des commandes explicites.

Les prédicats et leurs résultats apparaissent avec l'observation et l'empreinte du fichier. Ils restent des contrôles purs relus après les effets et avant/après la revue : une modification des octets invalide une ancienne preuve, même si la relation passe encore. Les lots mêlant commandes et prédicats observent les fichiers après les commandes. Le parseur JSON rejette aussi le dépassement numérique exponentiel (`1e999`), en plus de NaN/Infinity et des clés dupliquées. Ces mécanismes vérifient uniquement les expressions fournies ; le choix des formules et des critères reste faillible, et l'optimalité nécessite encore un calcul ou test indépendant. Aucun solveur ou résultat attendu propre au corpus n'est injecté dans le runtime.

Les instructions de mission et de revue distinguent structure et calcul, demandent des relations ou assertions exécutées pour les affirmations quantitatives, des comparaisons JSON indépendantes de l'espacement, et un lot commun pour les critères dépendant de commandes. Ce guidage reste une instruction au modèle, pas une garantie qu'il choisira des preuves suffisantes.

La détection de stagnation compare une fenêtre des 64 dernières signatures distinctes d'actions/résultats avec leurs critères et leur progression de vérification/exécution. Une alternance de lectures identiques est donc détectable ; des octets ou critères vérifiés nouveaux sont des observations nouvelles. Le modèle reçoit un retour explicite et l'événement `stagnation_notice` indique la portée du constat. Après le nombre de répétitions configuré par `stall_attempts`, la mission échoue avec le travail conservé. L'absence de nouvelle observation ne prouve pas l'absence d'effets d'une commande ; ceux-ci ne sont ni rejoués ni annulés automatiquement. La fenêtre se réinitialise lors d'une reprise explicite, qui garde ses protections contre les processus interrompus.

Les contrôles logiciels locaux atteignent **185 tests et 96 sous-tests réussis**, avec réponses LLM substituées et vrais fichiers/processus. Ils reproduisent le coût erroné, varient les paramètres de calcul, rejettent les appels et opérations interdits sans effets, contrôlent les champs absents, débordements, prédicats périmés et lots mixtes, puis distinguent un cycle de lectures d'une modification réelle. L'évaluateur ajoute l'empreinte du nouveau module `json_predicates.py`, soit six fichiers pour ses relevés. Les six configurations de la [matrice serveur du commit `f44b9a1`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37230928775) réussissent sur Linux/Windows/macOS, Python 3.10/3.13 ; elles ne mesurent pas la qualité du modèle.

Le rejeu réel de l'optimisation en faux positif (seed `2472336201`) termine `completed` en 447,60 secondes avec a=18, b=0, pièces=162 et consommation=162, confirmés indépendamment. Il n'utilise pas les nouveaux prédicats JSON ; ce résultat du correctif complet ne démontre donc pas un effet causal de ce seul contrôle, ni une hausse de vitesse.

Le corpus frais de cette version (seed `2802599050`, même modèle CPU, options natives vides et contexte observé de 4096 tokens) obtient **deux missions réussies sur quatre**. L'optimisation termine en 403,32 secondes avec un optimum confirmé de 60 pièces et une consommation de 80 sur budget 93. Le CSV termine en 213,37 secondes : rôle/skill créés, worker réellement exécuté, JSON 10/-96 juste et octets d'entrée conservés. Le worker et le parent y exécutent effectivement des prédicats JSON comparant les valeurs sauvegardées aux agrégats observés ; cela valide leur intégration native pour ces comparaisons, pas le choix correct de toute formule.

La réparation de ce corpus reste **en échec** après 217,24 secondes et 16 itérations : elle transforme la borne invalide en rejet des intervalles vides, puis relance le test sans réparer la cause. Le contrôleur indépendant échoue aussi. Le trajet livre au contraire le bon chemin, coût minimal 51 et énergie 21 sous budget 25, et préserve l'entrée ; son parent reste **en échec** après 442,56 secondes et 34 itérations, après des créations de compétence inutiles et des lectures répétées. Dans les deux cas, le garde de stagnation arrête la mission avec ses fichiers conservés. Aucun livrable correct ne convertit cet échec global en réussite. Les six empreintes concordent avec la source publiée avant la mise à jour documentaire.

Ces résultats montrent des réussites locales d'exécution/délégation et des limites persistantes de réparation et de convergence. Le modèle produit encore des hashes fictifs pour de nouveaux fichiers et des avis de revue contradictoires ; l'exécution rejette les appels non valides, sans en déduire que tout résultat approuvé est juste. Les priorités restantes sont la réparation d'hypothèses depuis les erreurs observées, la revue des preuves actuelles et la sélection des actions qui servent la demande originale. Les essais n'exercent pas tous les moteurs, le GPU ou un parcours distant complet. Le modèle est déchargé après les essais et les six services utilisateur restent arrêtés/désactivés. **L'AGI, la conscience et la réussite universelle restent non confirmées.**

### 1.12 Reprise diagnostique depuis des observations réelles

La suite des échecs de 1.11 motive une reprise ciblée : le modèle relançait le test d'un code qui rejetait les intervalles vides, et un parent créait des ressources facultatives après la production d'un trajet juste. `agi_core/mission_recovery.py` et `mission_agent.py` ajoutent une proposition diagnostique dans un contexte distinct lorsque le garde de stagnation atteint sa limite. La demande originale, les critères exacts, les obligations d'outils, les ressources connues et les protections des processus interrompus sont conservés. Les fichiers observés sont relus sans effets pour présenter leurs octets actuels ; le déclencheur et la dernière erreur reçoivent la priorité sur l'ancien historique. Les observations omises ou tronquées sont indiquées, et un contexte qui ne peut retenir l'objectif et les obligations échoue explicitement.

Le contrat JSON impose une citation exacte de la demande, des identifiants d'observations effectivement fournis, une hypothèse, une observation attendue et une action autorisée différente du cycle détecté. Une reprise ne peut appeler `set_plan` pour effacer les critères échoués. L'hypothèse reste une donnée faillible, distincte des preuves ; l'action proposée passe par l'exécuteur normal, les permissions, les checkpoints avant effets et les protections contre les replays de processus inconnus. Aucun critère n'est validé par le diagnostic. Une proposition de `finish` exige les contrôles et la revue de fin habituels. Les propositions et observations sont journalisées ; après redémarrage, une proposition enregistrée reste une donnée et n'est pas exécutée automatiquement.

`AURORA_RECOVERY_ATTEMPTS` configure un budget de diagnostic par exécution, de deux appels par défaut, désactivable avec zéro. Un diagnostic invalide consomme ce budget sans exécuter sa proposition ; une reprise explicite renouvelle le budget d'exécution tout en conservant les hypothèses et les protections existantes. Les signatures du cycle restent actives après le diagnostic. Ce budget est une limite de ressources, pas une note de performance ; chaque diagnostic ajoute une inférence et des lectures, et un modèle peut encore proposer une mauvaise réparation. Le parcours touché est la boucle locale des missions du daemon/CLI et de ses workers ; cela n'unifie pas les orchestrateurs natifs/web ou les moteurs médias.

Cette implémentation s'inspire du retour d'expérience mémorisé décrit dans [Reflexion](https://arxiv.org/abs/2303.11366) ; elle n'en reproduit pas les résultats publiés. Les [travaux sur les limites de l'auto-correction](https://arxiv.org/abs/2310.01798) motivent l'usage des erreurs d'exécution et des fichiers actuels plutôt qu'une simple affirmation de réussite du même modèle. Le cadre [Levels of AGI](https://arxiv.org/abs/2311.02462) distingue performance, généralité et autonomie ; l'ajout d'une boucle de réparation ne démontre pas ces trois dimensions ni une conscience. Sources primaires consultées le 4 octobre 2026.

Les validations ajoutées utilisent de vrais fichiers/processus avec propositions LLM substituées : correction d'une borne depuis la trace d'échec, vérification réelle après réparation, conservation de l'entrée, refus de preuves/citations inventées et d'actions interdites, budget explicite, non-rejeu des processus interrompus, convergence depuis un livrable vérifié, bornage du contexte et conservation d'une proposition au redémarrage sans exécution automatique. La première suite locale atteint **195 tests et 101 sous-tests réussis**. L'évaluateur relève désormais les huit empreintes de ses sources, la politique de ressources effective et les tentatives/propositions diagnostiques. Les résultats 2/4 de 1.11 appartiennent à la version précédente.

Les six configurations de la [matrice du commit `6d583a7`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37237747783) réussissent. Son rejeu natif de la réparation (seed de base `2802599050`, CPU, `qwen3-coder:30b`, options `{}`, délai 600 secondes, contexte observé 4096) reste **en échec global** après 394,40 secondes et 21 itérations, sans diagnostic déclenché. Le code produit passe pourtant les 85 cas indépendants. La revue a d'abord renvoyé une approbation accompagnée d'issues, rejetée comme contradictoire ; une réponse ultérieure de 2063 tokens a réduit le budget calculé de contexte à 4608 caractères, insuffisant pour le protocole complet et l'état critique. Les huit empreintes sont contrôlées avant les modifications suivantes ; ce résultat reste celui de `6d583a7`.

La correction suivante remplace uniquement les explications redondantes du protocole par une version compacte quand le contexte mesuré ne peut plus contenir le protocole complet. La demande originale, les critères/obligations, références de ressources et protections restent intacts ; le protocole complet demeure dans le checkpoint. Les instructions compactes conservent la hiérarchie demande/données, les vrais calculs et tests, les règles de délégation/vérification/revue et le non-rejeu des processus inconnus. Les schémas exacts restent dans le décodage et l'exécuteur. Si même cette représentation ne tient pas, l'arrêt explicite reste requis. `model_metrics.protocol_variant` indique la version effectivement utilisée ; aucun paramètre Ollama n'est modifié. Le schéma de revue sépare aussi une branche approuvée avec `unmet=[]`/`issues=[]` et une branche rejetée avec ces deux listes non vides ; les citations et identifiants sont encore validés à l'exécution, sans convertir un verdict contradictoire en approbation. Les nouveaux tests conservent le refus de verdicts ou preuves fictifs et vérifient la compaction sans perte d'objectif/critères. La suite complète de cette correction atteint **197 tests et 101 sous-tests réussis** ; les six configurations de sa [matrice logicielle](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37238566003) passent. Son corpus natif est décrit en 1.13.

### 1.13 Contrôle final généré depuis la demande et les entrées

Le corpus natif frais de `ae34aae` (seed `1725827347`, quatre missions, CPU `qwen3-coder:30b`, options `{}`, contexte observé 4096, délai 600 secondes par mission) obtient **une réussite globale sur quatre**. L'optimisation termine en 326,40 secondes avec un optimum confirmé de 96 pièces, consommation 120 sous budget 122. Le CSV termine à tort `completed` en 278,52 secondes avec `rows=6,sum=122`, tandis que les données réelles donnent une somme de 139 : le worker a omis la première donnée, le parent a corrigé le nombre de lignes mais conservé la mauvaise somme, puis la revue a approuvé ce faux résultat. Le contrôleur indépendant rejette ce cas malgré le rôle/skill créés, le worker effectivement terminé et l'entrée intacte. La réparation livre du code qui passe 85 cas indépendants, mais reste `stopped` au délai après 54 itérations et deux diagnostics. Ceux-ci proposent notamment une hypothèse de tri erronée alors que le code trie déjà ses intervalles ; aucune validité de schéma ne prouve la justesse d'une hypothèse. Le trajet échoue en 329,62 secondes, après deux diagnostics et sans `route.json`. Les huit empreintes sont confirmées avant les modifications suivantes. La [matrice logicielle de `ae34aae`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37238566003) réussit dans ses six configurations ; elle ne contredit pas ces échecs de modèle.

Ce faux positif motive un contrôle supplémentaire à la proposition de fin, dans `mission_agent.py`. Un contexte séparé du même modèle reçoit la demande originale, les critères exacts, les obligations/outils exécutés, les références de ressources et les chemins/empreintes observés. Il ne reçoit ni le résultat annoncé par l'agent, ni ses valeurs attendues ou verdicts. Le modèle doit proposer un lot `verify` couvrant tous les critères et les exigences originales, avec des calculs depuis les entrées : `csv_json` pour les agrégats CSV/JSON, des assertions exécutées pour le code ou l'optimisation, des relations sauvegardées pour les contraintes. Ce générateur reste faillible ; il ne constitue ni un modèle indépendant ni une preuve sémantique universelle.

Les contrats et permissions sont validés avant exécution ; le lot passe par la boucle normale, son checkpoint avant effets et les mêmes protections contre les commandes interrompues. Un diagnostic de contrôle ne valide aucun critère. Un échec exécuté retire les preuves du groupe concerné et fournit les valeurs réellement attendues/observées au parent, qui doit réparer puis vérifier. La revue de conclusion et les relectures des fichiers restent obligatoires. Les contrôles purs peuvent être réutilisés seulement avec des vérifications fraîches et les mêmes empreintes ; les contrôles de commandes ne sont pas rejoués pour tester le cache et ne valent que pour une fin sans action intermédiaire. Une reprise après redémarrage ne récupère pas automatiquement la proposition d'action locale.

`AURORA_REQUEST_AUDIT=1` active ce contrôle par défaut ; `0` est une désactivation explicite pour comparer coût et qualité. La politique effective figure dans les résultats d'évaluation. Le compromis est une inférence et des contrôles réels supplémentaires lors d'une nouvelle proposition de livraison. Les chemins concernés sont les missions locales du daemon/CLI et leurs workers, sans unification implicite avec les orchestrateurs UI ou médias. Les tests anciens qui isolent les autres contrats désactivent explicitement ce générateur supplémentaire ; les tests `test_request_audit.py` l'activent et exécutent réellement ses vérifications. Ils reproduisent le faux positif CSV, sa réfutation et sa réparation, le rejet des contrôles incomplets/interdits, le non-rejeu d'un processus interrompu, les empreintes périmées et la réutilisation sans replay de commandes. Les citations de diagnostics/revues doivent aussi comporter au moins un caractère alphanumérique : une ponctuation seule, observée dans un diagnostic de trajet, ne constitue plus une citation acceptée. Cela ne prouve pas la pertinence de toute autre citation.

La suite de ce contrôle atteint **206 tests et 107 sous-tests réussis**, avec réponses LLM substituées. Les six configurations de la [matrice logicielle de `482ea74`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37240829482) passent. Son rejeu CSV natif sur les mêmes données reste **en échec global** : arrêt au délai de 600 secondes, parent à 7 itérations, JSON numérique 6/139 correct et entrée intacte, mais aucun worker accepté comme terminé. Le worker avait corrigé la somme avant le premier contrôle séparé ; ce dernier a ensuite choisi `row_count` et `value` comme clés attendues malgré le JSON sauvegardé `rows` et `sum`, provoquant des échecs de format répétés. Ce rejeu ne prouve donc pas une correction de la somme causée par le contrôle séparé. Les huit empreintes sont confirmées avant la correction suivante.

Le contrôle reçoit désormais aussi les clés et types des JSON réellement relus et les noms des colonnes CSV, sans transmettre leurs valeurs dans ces métadonnées au générateur. Les noms imposés par la demande restent prioritaires ; quand la demande déléguée n'en impose pas, les noms observés permettent d'éviter une invention de schéma. Les relectures sont bornées et les schémas tronqués/inaccessibles sont signalés. Les tests vérifient explicitement cette information structurelle et l'absence des sommes annoncées ou attendues dans les champs du contexte de leur fixture. Les labels de critères restent fournis par l'agent et peuvent eux-mêmes contenir des hypothèses ; ce contexte n'est donc pas une garantie d'absence de tout biais.

La [matrice de `bf60e43`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37241835941) passe ses six configurations. Un diagnostic natif ciblé, depuis un état d'échec préparé et réellement exécuté, corrige `solution.py` en une action en 60,83 secondes ; le test auparavant échoué et les 85 cas indépendants passent, avec le fichier de test conservé. Il s'agit d'un test de composant, pas d'une mission autonome entière ni d'une preuve de déclenchement automatique. Le rejeu CSV complet de cette version reste au contraire **arrêté au délai de 600 secondes**, parent à 42 itérations, avec 6/139 correct, entrée intacte et worker accepté comme terminé. Le contrôleur indépendant passe, mais la mission globale échoue. Le générateur de contrôle confond encore une colonne d'entrée et une clé de sortie malgré les métadonnées de schéma. Les huit empreintes de ces essais sont confirmées avant les modifications suivantes.

Pour les objets de statistiques constitués d'entiers, `mission_protocol.audit_response_schema` spécialise maintenant les branches CSV/JSON depuis les champs observés : cible et clé du nombre de lignes imposées par branche, autres clés de sortie requises comme sommes, sans noms de champs prédéfinis ni nombres attendus. Le schéma respecte une limite explicite de caractères ; les cas trop volumineux gardent le décodage ordinaire et le contrôle préalable. Celui-ci rejette toute proposition CSV/JSON dont les clés calculées ne correspondent pas au JSON observé, avant les effets et sans transformer ce défaut de proposition en demande de renommer un résultat correct. Les défauts de format vis-à-vis de la demande se testent séparément avec un contrôle de clés JSON ; les schémas riches utilisent des assertions exécutées. Les vérifications du parent hors de ce générateur conservent leurs contrats génériques. Les tests ajoutés rejettent un nom inventé sans toucher l'artefact et contrôlent la présence des branches natives fondées sur les champs réels.

La suite de `c9be414` atteint **207 tests et 107 sous-tests réussis** en 8,70 secondes, avec réponses LLM substituées et effets fichiers/processus réels. Les six configurations de sa [matrice logicielle](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37243341341) passent sur Linux, macOS et Windows, Python 3.10 et 3.13. Elles vérifient ces contrats logiciels ; elles ne certifient ni les générations locales sur ces trois systèmes, ni tous les moteurs médias.

Le rejeu CSV natif de `c9be414`, sur les mêmes données et avec le même modèle/options/contexte, termine `completed` en 393,29 secondes et 19 itérations du parent. Le JSON 6/139 est correct, l'entrée intacte et le rôle/skill demandés créés. Le worker a effectivement terminé, mais le `spawn_agent` a utilisé `agent=""` plutôt que le rôle `AuditCSV` demandé : le contrôleur indépendant classe donc la mission **en échec global**. Son champ `worker_completed=false` signifie ici que le contrat de délégation avec ce rôle n'est pas rempli, pas qu'aucun worker n'a fini. Les audits séparés du worker et du parent passent leurs contrôles de structure/existence/empreinte ; ils ne testent ni cette identité d'exécution ni le recalcul numérique et n'utilisent pas les branches CSV spécialisées. La justesse numérique observée ne prouve donc pas que ces audits suffisent pour une autre mission. L'écart entre le statut `completed` et le contrat demandé reste une limite de validation sémantique, conservée dans les traces.

Un essai natif distinct de composant utilise des données fraîches, une somme préparée volontairement fausse et des noms de colonnes/champs différents (`amount`, `records`, `total`). Le générateur choisit effectivement la branche CSV/JSON spécialisée ; son exécution recalcule les agrégats depuis l'entrée et rejette la somme fausse en 21,59 secondes, avec les deux fichiers inchangés. Ce contrôle valide le décodage natif et la réfutation sur ce cas préparé ; ce n'est ni une réparation autonome ni une garantie que le générateur choisit ces contrôles dans toute mission. Les huit empreintes des deux essais correspondent à `c9be414`. Les preuves restent privées dans les journaux et JSON d'évaluation ; les versions antérieures ne sont pas agrégées en un score de cette version. Après les essais, les modèles Ollama sont déchargés, aucun contrôleur d'évaluation ne reste lancé, les ports 3001/3002 sont fermés et les six services Aurora restent arrêtés/désactivés. Le worktree temporaire propre de cette reprise est supprimé ; les modifications préexistantes du worktree 3D sont conservées. **L'AGI, la conscience et la réussite universelle ne sont pas confirmées.**

### 1.14 Preuve d'utilisation effective d'un rôle délégué

L'échec natif de `c9be414` en 1.13 expose un manque concret : un rôle existait, un worker générique avait fini et les audits de définition/structure passaient, mais ce worker n'avait pas utilisé le rôle demandé. Le contrôle `verify(kind="delegation", agent=nom)` consulte maintenant les observations réelles des exécutions de `spawn_agent`. Il exige le nom exact, des workers tous terminés et les contrôles d'acceptation du parent effectivement réussis à la fin de cette exécution. Les tâches exactes et l'identifiant d'exécution peuvent aussi être imposés. `kind="agent"` reste une preuve de définition uniquement. Cette preuve de délégation est historique ; elle ne démontre ni la justesse sémantique du rapport ni la validité actuelle des livrables, qui nécessitent leurs propres contrôles.

Chaque exécution enregistrée reçoit un identifiant, le rôle effectivement passé, les tâches, statuts et empreintes des contrôles d'acceptation. Les 64 observations les plus récentes sont conservées dans le checkpoint. Une réutilisation de délégation pure garde l'identifiant original et ne crée pas une nouvelle preuve de travail. Les contrôles de preuve lisent ces données sans lancer de worker ou rejouer ses commandes. Les anciens checkpoints peuvent fournir une observation depuis leurs vrais résultats d'outil encore présents ; une définition de rôle, une affirmation sauvegardée dans un fichier ou une issue de worker inconnue ne vaut pas un résultat réussi. Un contrôle d'exécution de délégation ne peut servir de contrôle d'acceptation de la même délégation avant son lancement : il se demande ensuite avec `verify`.

L'audit distinct reçoit ces métadonnées d'exécution, sans sommes annoncées ni valeurs attendues ; les omissions dues au budget de contexte sont signalées. Le protocole et l'audit demandent le nom exact du rôle spécifié dans la demande, et un contrôle d'exécution plutôt qu'une simple existence pour cette obligation. La revue de fin reçoit aussi ces observations réelles. L'identifiant aléatoire d'une nouvelle exécution n'est pas considéré comme une progression par le détecteur de stagnation. Le compromis est un peu plus de stockage et de contexte ; aucune inférence supplémentaire systématique n'est ajoutée. Le chemin concerné reste la boucle locale de missions et ses workers, utilisée par le daemon/CLI ; les orchestrateurs web/médias ne sont pas unifiés par ce contrôle.

Les tests ciblés emploient les vrais workers de cette boucle, la vraie lecture du rôle et des fichiers/processus réels, avec réponses LLM substituées. Ils distinguent définition, worker générique et worker nommé ; rejettent un rôle/tâche/identifiant incorrect, une exécution échouée et un contrôle circulaire sans effets ; conservent la preuve à travers SQLite et une réutilisation sans replay ; puis reproduisent un audit qui réfute le mauvais rôle avant d'accepter son exécution réelle. La suite complète locale de `3be75a5` passe **215 tests et 107 sous-tests** en 8,64 secondes, ainsi que les six configurations de sa [matrice logicielle](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37266246938). L'évaluateur conserve les observations de délégation et le dernier audit, et distingue désormais `any_worker_completed` de `requested_role_worker_completed` sans modifier le critère global de réussite.

Son rejeu CSV natif (même seed `1725827347`, CPU `qwen3-coder:30b`, options `{}`, contexte 4096) reste **en échec global** après 554,40 secondes et 27 itérations du parent. Cette fois, le JSON 6/139 est juste, l'entrée intacte, le rôle/skill créés et des workers nommés `AuditCSV` effectivement terminés avec une acceptation du parent réussie. Le contrôle indépendant passe. L'audit natif du parent choisit et réussit effectivement un contrôle `delegation`; les workers emploient aussi des contrôles de recalcul CSV/JSON. Pourtant, aucun avis de revue du parent n'est atteint : il repart vers des lectures/créations/délégations, puis le garde de stagnation arrête la mission, malgré tous ses critères et outils requis vérifiés. Les huit empreintes sont confirmées avant la correction suivante. Le passage de ces contrôles de composants ne convertit pas cet échec global en réussite.

### 1.15 Transition vers la revue et évaluation d'une règle inconnue

Quand une mission avec critères a vérifié tous ses critères, exécuté ses outils obligatoires et vérifié après ses derniers effets, sans action/processus en cours ni gap de revue, le décodage de la prochaine réponse native propose uniquement `finish`. C'est une transition vers la proposition de conclusion, pas une approbation : audit distinct, contrôles des fichiers actuels, revue originale et seconde revalidation restent obligatoires. Une revue rejetée conserve un marqueur dans le checkpoint et rend les outils de travail disponibles pour réparer ; une vérification réussie de tous les critères dans un nouveau lot retire ce marqueur. Des critères manquants, obligations non exécutées, effets non vérifiés et demandes sans critères gardent le protocole de travail. `model_metrics.execution_phase` distingue travail et proposition de conclusion. Aucune commande ou conclusion n'est rejouée automatiquement au redémarrage, et les permissions restent identiques.

Les tests de transport HTTP contrôlent le schéma transmis au moteur selon ces états. Un test avec fichiers et SQLite réels expose une mauvaise valeur ayant passé un simple contrôle de présence : la revue la rejette, le marqueur persiste, la boucle de mission répare et vérifie le contenu exact, puis la conclusion est proposée à nouveau. Les réponses LLM y sont substituées. Cette transition réduit les actions facultatives après les preuves planifiées ; elle ne rend pas suffisants des critères incomplets ou des contrôles sémantiques faibles.

L'évaluateur ajoute `rule-discovery`, cinquième famille après les quatre cas existants, dont les indices de seed restent identiques. Une rotation/miroir et une permutation de cinq couleurs sont tirées depuis la seed ; trois paires de grilles déterminent une règle unique dans cette famille explicitement déclarée. La mission doit déduire cette règle, écrire une fonction `solve(grid)` et produire les résultats de quatre grilles visibles. Le contrôleur teste ensuite 24 autres grilles non fournies au modèle, la non-mutation et la conservation de l'entrée/des livrables pendant les tests. Une table des seuls exemples et un solveur qui modifie son entrée sont rejetés. Les paramètres secrets et sorties cachées restent dans la mémoire de l'évaluateur jusqu'au contrôle ; le shell hôte n'est toujours pas une isolation contre toute introspection. Les neuf sources de runtime/évaluation sont désormais empreintées.

Ce cas synthétique examine une acquisition de règle et un transfert dans une famille finie connue. Il n'est pas un test officiel ARC, une comparaison calibrée aux humains ou une certification AGI. Les principes de [mesure de l'acquisition de compétences](https://arxiv.org/abs/1911.01547) et de [généralisation d'ARC Prize](https://arcprize.org/arc-agi) motivent la distinction entre varier des paramètres et varier des problèmes ; aucun score de ces travaux n'est attribué à Aurora. La suite locale de cette seconde correction passe **221 tests et 118 sous-tests** en 9,04 secondes, avec réponses LLM substituées et effets réels. Les six configurations de la [matrice logicielle de `47ed5c2`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37267772123) réussissent. Le solveur du test de grilles ne reçoit jamais les réponses cachées dans son stdin : seules les entrées entrent dans son processus, et le contrôleur parent compare ses sorties aux réponses conservées en mémoire.

Le corpus natif de ce commit, seed de base `1427009`, utilise réellement `qwen3-coder:30b` sur CPU, options `{}`, contexte observé 4096 et délai de 600 secondes par cas. Ses neuf empreintes de sources sont confirmées après la fin, avant l'intégration suivante. Il produit **une seule réussite globale sur cinq missions** :

| Cas | Contrôle indépendant | Statut global | Durée |
|---|---|---|---|
| Optimisation | Réussi : 60 pièces, 108 unités | `completed`, réussi | 166,43 s |
| CSV / rôle nommé | Réussi : 5 lignes, somme 163, entrée intacte, worker nommé accepté | `stopped`, délai dépassé | 600,01 s |
| Réparation de code | Réussi : 85 cas fonctionnels et non-mutation | `stopped`, délai dépassé | 600,03 s |
| Graphe contraint | Échoué : le chemin vaut réellement coût 47 / énergie 54, budget 17 ; optimum 12 / 1 | `failed`, stagnation | 232,32 s |
| Règle de grilles | Livrables absents ; aucun test caché exécuté | `failed`, stagnation | 100,98 s |

La réparation exécute neuf commandes de tests, toutes échouées à cause notamment de valeurs attendues inventées : l'union `[-3,0)` et `[1,4)` vaut 6, pas 7 ; un intervalle vide ne doit pas lever `ValueError`. Les 85 cas du contrôleur indépendant passent sur la fonction sauvegardée, sans rendre la mission achevée. Le graphe ne lance aucun calcul Python ; les seuls contrôles de clés et de non-négativité ne prouvent ni les sommes du chemin ni l'optimalité. Les grilles répètent lectures/plans et proposent un rôle CSV hors sujet. Le registre de rôles est partagé entre les cas et expose effectivement la définition CSV précédente comme contexte consultatif ; chaque mission possède un nouvel agent et historique. Cette exposition est établie, sa causalité dans l'erreur du modèle ne l'est pas. Les dernières propositions de reprise du graphe et des grilles sont rejetées avant effets pour absence de citation littérale non vide de la demande originale.

Ces résultats restent privés dans `~/maintenance-agi-2026-10-05/fresh-corpus-phase-rule`. Ils concernent la boucle locale, sans bridge/tunnel, GPU ou validation de tous les modules. Un livrable juste avec une mission arrêtée n'est pas une réussite autonome complète. **Une AGI réelle, une conscience et une réussite universelle ne sont pas établies.**

Une relecture indépendante ultérieure renforce le contrôleur de grilles : la fonction livrée doit aussi réussir les trois exemples d'apprentissage et les quatre entrées publiques, séparément des prédictions JSON sauvegardées. Les 24 anciennes grilles cachées restent identiques ; quatre grilles supplémentaires de tailles `1×11`, `13×1`, `8×9` et `9×8` étendent les dimensions effectivement contrôlées, sans prouver toute taille possible. Les instantanés sérialisés sont pris avant l'exécution du solveur et vérifiés après chaque appel puis après le lot ; modifier les helpers `copy.deepcopy` ou `json.dumps` ne contourne plus ces cas de non-mutation. Le contrôleur compile les octets de `solver.py` au lieu de pouvoir importer un ancien `.pyc` valide par taille/date. Les résultats attendus restent comparés dans le parent, et le stdin du solveur ne contient que des entrées. Ce durcissement ne fournit pas d'isolation OS contre une introspection hostile. Les résultats natifs précédents restent ceux de `47ed5c2`, distincts de cette nouvelle version du contrôleur.

Le contrôleur de réparation compile lui aussi les octets de `solution.py` observés avant le test, avec un module Python enregistré normalement pour conserver notamment la compatibilité des annotations `dataclass`. Le parent compare les valeurs et exceptions aux calculs indépendants, vérifie les arguments après chaque appel puis après le lot, et refuse une source modifiée pendant l'évaluation. Un ancien `.pyc` correct avec une source actuelle incorrecte de même taille/date, une mutation masquée par un patch de `copy.deepcopy`, une mutation différée d'arguments conservés et une réécriture de source sont reproduits et rejetés. Ces contrôles ne garantissent toujours pas une isolation OS ni la conservation de chaque fichier sans contrôle spécifique.

### 1.16 Portée des preuves dans les workers

Le nouveau corpus de 1.15 expose une contamination des critères : pour la tâche enfant « vérifier le nombre de lignes et la somme », le worker copie notamment le critère du parent « la délégation est effectuée avec succès ». Son audit exige alors un contrôle `delegation` de sa propre exécution, avant qu'il puisse retourner. Cette preuve appartient au parent après son retour. Le cas CSV finit avec un livrable numérique correct et un worker nommé accepté, mais atteint le délai de 600 secondes sans conclusion globale ; les traces des contrôles circulaires restent conservées.

Les contextes des workers gardent désormais les fichiers/champs/paramètres de leurs contrôles d'acceptation, mais retirent les labels de critères du parent. Le worker doit définir des critères pour sa demande déléguée. Les schémas natifs de ses actions, de son audit et de son diagnostic de stagnation excluent les preuves de délégation ; la proposition de diagnostic et l'exécuteur rejettent aussi ces contrôles hors de leur portée, avant les autres effets du lot. Une proposition d'audit hors de cette portée est rejetée sans effets et peut être corrigée dans les tentatives bornées existantes ; les rejets répétés épuisent ce budget sans approbation. Le parent conserve le contrôle de rôle effectivement utilisé, y compris dans son diagnostic. Les contrôles de sortie du parent ne sont pas affaiblis, ses labels restent intacts et les contraintes de workspace/permissions/reprise demeurent. Ce changement n'ajoute aucun appel de modèle systématique et réduit des obligations étrangères à la tâche enfant, sans prouver le choix de tout critère sémantique.

Des tests de vrais workers avec réponses LLM substituées vérifient le retrait des labels et la conservation des mappings CSV/JSON, le maintien des critères du parent, le filtrage des schémas et le rejet d'un contrôle circulaire sans lancement de la commande du même lot. Ils vérifient aussi le rejet puis la correction d'un audit hors portée, l'épuisement borné des rejets, une proposition de reprise incorrecte suivie d'une véritable réparation avec commande et la compatibilité du contrôle de délégation parent. Les tests ciblés passent **72 tests et 38 sous-tests** en 1,68 seconde dans le worktree isolé. Après intégration des contrôleurs relus, la suite locale de `40c16a3` passe **238 tests et 122 sous-tests** en 9,45 secondes. Sa CI expose un défaut de fixture sous Windows : une écriture texte ajoute CRLF, donnant 164 octets au lieu des 161 requis pour reproduire un cache de même taille/date. `d27fc24` écrit ces fixtures en octets UTF-8 exacts et prouve l'ancien import avant le rejet du contrôleur ; ses six configurations [Linux/Windows/macOS, Python 3.10/3.13](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37276570030) passent. Ce commit ne modifie aucune des neuf sources de runtime/évaluation.

Le rejeu CSV natif de `40c16a3`, seed de cas `1427010`, même modèle/options/délai, reste arrêté à **600,00 secondes** avec un résultat indépendant réussi : 5 lignes, somme 163, entrée intacte, rôle/skill créés et worker nommé accepté. Les critères parent étrangers à la tâche enfant ne sont plus copiés. Un autre blocage apparaît : le worker demande `keys=["rows"]` puis `keys=["sum"]` pour un objet contenant les deux clés ; les expressions numériques passent, mais chaque ensemble de clés reste incorrect. La sémantique exacte était documentée dans le protocole complet, mais son échec ne donnait pas la raison du sous-contrôle et le protocole compact ne la rappelait pas. Ses reprises avec une citation paraphrasée sont aussi rejetées. Les neuf sources restent identiques après le test, y compris pendant le commit de fixtures. Les preuves privées restent dans `~/maintenance-agi-2026-10-05/scoped-worker-regression-csv`.

La correction `fa5409f` conserve l'ensemble exact et ajoute `keys_result` : statut, clés demandées/observées/manquantes/inattendues et raison explicite. Le protocole compact, le protocole complet et les descriptions natives précisent que des champs supplémentaires échouent même si les expressions passent ; une vérification d'expressions seules peut omettre `keys` lorsqu'elle ne prétend pas contrôler le format entier. Les vérifications du format complet imposées par la demande restent nécessaires. Six tests supplémentaires reproduisent le sous-ensemble incorrect avec une expression vraie, les clés complètes dans un autre ordre, les objets avec clés manquantes/supplémentaires, les valeurs non objets, les arguments malformés et la conjonction des contrôles. La suite intégrée passe **244 tests et 137 sous-tests** en 9,58 secondes avec modèles substitués. Les six configurations de sa [matrice logicielle Linux/Windows/macOS et Python 3.10/3.13](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37277316504) réussissent.

Son dernier rejeu CSV natif, même seed de cas `1427010`, reste **en échec global et indépendant** à 600,00 secondes et 15 itérations du parent : le fichier contient `rows=6, sum=163`, alors que les données comportent 5 lignes et une somme de 163. L'entrée est intacte et les définitions du rôle/skill existent ; aucun worker ne termine et aucune délégation n'est acceptée. La première délégation échoue après 390,79 secondes ; la suivante est interrompue au délai. Le modèle confond lignes du fichier et lignes de données, emploie des arguments `awk` avec apostrophes shell littérales puis un découpage par virgule incompatible avec les libellés cités, et vise aussi un fichier/format inventé. Les contrôles CSV rejettent effectivement ce format. Ses reprises sont rejetées pour une citation incorrecte de la demande, avant effets. Le parent vérifie une simple constante incorrecte qu'il vient d'écrire, sans atteindre un audit distinct ni une revue finale. **Le nouveau `keys_result` n'est pas exercé dans ce rejeu : aucun gain natif ne lui est attribué.**

Les neuf empreintes concordent avant/après ce dernier essai et avec les sources publiées/testées de `fa5409f`. Les résultats restent privés dans `~/maintenance-agi-2026-10-05/json-key-diagnostics-regression-csv`. Les résultats des différentes versions ne sont pas agrégés en un score AGI. Après les essais, les six unités Aurora sont observées inactives/désactivées, les ports 3001/3002 fermés et Ollama sans modèle résident ; le service Ollama système reste actif. Le CLI et le dépôt live restent aux commits précédemment validés, et les six modifications locales du worktree 3D sont conservées. Les seuls worktrees de cette intervention et leurs projections accidentelles sont retirés. Les exports Markdown concordent ; les 38 écarts de l'inventaire historique restent signalés, sans remplacement automatique de ses empreintes. **Une AGI réelle, une conscience subjective, tous les modules et une réussite universelle ne sont pas confirmés.**

### 1.17 Réparation du parcours 3D et des timeouts du 5 octobre

Les erreurs signalées sont « ComfyUI a quitté pendant le démarrage » dans le module 3D natif (axolotl) et « timeout on reading data from socket » dans le CLI (Natsu Dragneel avec un fusil). Les processus lancés à 09:05 UTC conservaient l'ancien code, indépendamment des unités systemd inactives. Après vérification des trois missions toutes terminales et d'Ollama sans modèle résident, ces processus et leur superviseur ont été arrêtés puis remplacés par les unités bridge/daemon. Elles répondent désormais localement ; une requête doctor authentifiée avec le vrai client CLI répond aussi via le tunnel existant. Cela ne valide ni une mission SSE publique complète ni le Mac de l'utilisateur.

Les routes 3D et quatre helpers de mouvement résolvent leurs scripts depuis `WORKSPACE`, et le worker distant fait de même. La livraison utilise le `final_mesh` du résultat réussi du run courant dans son dossier isolé, avec contrôle des symlinks et des composants du chemin. Elle lit le JSON final multiligne après les messages de progression ; les sorties scène portent aussi `schema` et `run_id`. Un GLB ancien ou un dossier déjà présent ne devient pas la réussite d'une nouvelle invocation.

Le bridge conserve un journal ComfyUI borné à 16 Kio, son code de sortie et la raison du démarrage dans `/api/comfyui/start` et le diagnostic de statut. Le shell natif restitue la fin du journal de sa tentative, sans reprendre une erreur ancienne ; son processus propre est arrêté si le délai de démarrage expire. `runtimeEnsureService` et le runtime géré n'acceptent plus `running=false` comme un service activé. Le module 3D contrôle les moteurs avant les chargements coûteux, démarre ComfyUI lorsqu'il doit réellement synthétiser une référence et inscrit aussi les services activés tard dans son nettoyage. Une image fournie ne nécessite pas les poids FLUX du pack. Cela n'unifie pas toute la préparation des parcours Blender/photogrammétrie avec le pipeline Python.

`aurora_3d_pipeline.py --check-runtime` renvoie un JSON compact avec les moteurs, leurs interpréteurs, leur disponibilité et leurs erreurs, sans prompt ni chargement de poids ; l'inspection réussie retourne le code zéro même si `ok=false`. TRELLIS et Hunyuan sont sondés dans leurs Python d'exécution avec imports et initialisation CUDA. Hunyuan accepte `AURORA_HUNYUAN_PY`. La branche neuronale indisponible échoue avant la synthèse de références ; les références, le réemploi et les branches géométriques gardent leurs conditions propres. Un personnage ne devient pas automatiquement un mannequin procédural ; l'ancien secours Lincoln exige `AURORA_HISTORICAL_PERSON_FALLBACK=1`. Le miroir Python `route_test` est absent de ce checkout : les branches procédurales/photogrammétriques testées avec routeur substitué ne prouvent pas leur sélection automatique par le routeur réel.

Le défaut de modèle du bridge respecte un modèle explicite installé et conserve les choix par requête. En automatique, les poids déclarés supérieurs à RAM totale + VRAM NVIDIA observées sont écartés. Ce filtre grossier n'est ni une mesure de mémoire résidente ni une garantie de capacité/latence. Le doctor réutilise ses mesures, expose RAM totale/disponible, VRAM, tailles et modèle effectif ; son verdict de pont prêt reste distinct de GPU/ComfyUI prêts. Le CLI donne au doctor son budget HTTP de 30 secondes, distingue les phases/types de timeout, conserve les sorties partielles de workers et termine `generate-3d` avec un code non nul à l'échec. Le flux SSE reprend seulement les GET depuis le dernier événement complet, sans répétition des POST. Le gateway précise qu'un timeout vient d'Ollama et indique le modèle et la phase avant/après réponse ; sa limite native de 300 secondes entre blocs reste configurable et n'est pas augmentée globalement.

Validation locale : **749 tests CLI réussis** (18 ignorés, 5 sous-tests), **295 tests serveur/Auto-RL réussis** (161 sous-tests), quatre cas du véritable corps du hook runtime avec dépendances React/services substituées, un test Rust des journaux, types TypeScript, build web, compilation native Linux et banc de conformance existant. Les cas 3D utilisent des processus/fichiers temporaires ou des moteurs substitués. Un premier essai de fixture a révélé le mauvais dossier du worker et appelé accidentellement le script réel ; ses processus ont été arrêtés, aucun livrable généré n'a été observé, et une garde de test refuse désormais tout script hors du dossier temporaire. Ce n'est pas une génération validée.

Le démarrage réel de ComfyUI corrigé échoue en environ trois secondes avec `process_exited`, code 1 et **`No CUDA GPUs are available`** transmis par l'API. Torch ComfyUI 2.11.0+cu128 voit zéro GPU ; la sonde des deux moteurs rapporte CUDA indisponible. Le noyau actif `7.0.0-34-generic` n'a toujours pas son module NVIDIA, et `sudo` exige le mot de passe utilisateur. La génération neuronale réelle des deux demandes reste donc non validée. La réparation ciblée des paquets NVIDIA a été simulée (16 mises à jour, 2 nouveaux paquets, aucune suppression, pas de nouveau noyau), sans exécution privilégiée.

Les preuves détaillées restent privées dans `~/maintenance-3d-runtime-2026-10-05`. L'override utilisateur `aurora-bridge.service.d/40-runtime-local.conf` conserve le bridge sur localhost et utilise `AURORA_BRIDGE_SYNC_TUNNEL=0`, `AURORA_BRIDGE_BACKGROUND_PRELOAD=0`, `AURORA_BRIDGE_NO_WATCH=1` pour cette relance ; les deux premières options gardent leur ancien défaut en production. Aucun nouveau tunnel ou Gist n'a été publié par cette intervention. Poids, environnements, données et les six modifications préexistantes du worktree 3D sont conservés.

### 1.18 Reprise du 6 octobre 2026 : contrôles actuels et checkpoint logiciel

La lecture, l'écriture d'un fichier temporaire et l'exécution de commandes sont réellement vérifiées dans cette session ; l'erreur `bwrap: loopback: Failed RTM_NEWADDR` ne se reproduit pas. Les modifications préexistantes sont conservées. Avant les nouveaux changements, **769 tests CLI et 302 tests serveur/Auto-RL** passent de nouveau le 6 octobre ; ces résultats actuels sont distincts des résultats historiques du 5 octobre et des essais de modèles.

Les trois routes restantes `motion-intent`, `custom-motion` et `auto-motion-bake` résolvent désormais leurs cinq chemins de classificateur/baker depuis `WORKSPACE/python-services`. Un processus baker sortant en erreur ne peut plus annoncer une animation réussie. Une réponse native réelle du classificateur était `{"fan_pwm": {...}}`, inutilisable par son normalisateur ; le format natif Ollama contraint maintenant les champs `category`, `confidence` et `rationale`, sans supprimer les blocs de mouvement extensibles. Le modèle explicite est transmis aux trois routes ; sans modèle explicite, `motion-intent` laisse le script sélectionner son modèle disponible.

Les essais réels emploient `qwen3-coder:30b` sur CPU et Blender installé : les trois routes répondent en local et via le tunnel existant, le classificateur choisit `fan_pwm` avec confiance 0,95, et les deux bakers produisent chacun un GLB de 2 464 octets avec une animation sur un rotor géométrique de test. La génération automatique passe de 988 à 2 464 octets. Les téléchargements locaux et publics ont la même empreinte que les fichiers produits. Cela vérifie ce rotor et ces primitives, **pas** un personnage animé ni la conformité universelle des mouvements. Les essais précédents en repli regex conservaient correctement l'original pour une confiance nulle.

La synthèse Kokoro et la transcription Whisper fonctionnent réellement sur CPU en local et via le tunnel : la phrase synthétisée « Bonjour. Aurora fonctionne en local. » est transcrite « Bonjour, Aurora fonctionne en local. ». Deux synthèses différentes reproduisent une erreur de livraison : la même URL renvoyait la plus récente, remplaçant le premier résultat. Chaque nouvelle synthèse reçoit désormais un nom unique et une URL vers son propre WAV, confinée au dossier voix ; l'ancien accès sans paramètre reste compatible. Le contrôle réel après correction conserve le premier SHA-256 après la seconde synthèse. STT utilise aussi un dossier temporaire absolu et isolé par requête, nettoyé après lecture. Les moteurs des tests unitaires de ces contrats restent substitués, distincts de ces essais réels.

Le chat avec le modèle réel renvoie `AURORA_OK` en local et via le tunnel. Une demande à un modèle inexistant terminait auparavant sans aucun événement ; elle émet désormais une erreur explicite, ainsi qu'un flux Ollama interrompu sans marqueur final. La réponse amont est fermée. Le premier essai interrompu par notre relance du bridge est exclu des preuves de conversation réussie. Deux profils navigateur isolés envoient aussi une vraie demande depuis le formulaire de conversation au même modèle ; la réponse `AURORA_UI_OK` est enregistrée et affichée sans erreur JavaScript, en 3,58 secondes localement et 1,85 seconde publiquement, depuis l’ouverture de la page avec modèle déjà chaud. Ce cas très court ne mesure pas les performances des longues conversations.

Un checkpoint réel de mission révèle que le protocole complet laisse seulement 494 caractères pour le dernier résultat d'outil de 832 caractères. Le compacteur privilégie désormais son protocole compact pour conserver les deux derniers messages lorsque la capacité observée l'exige, avant de retirer les éléments consultatifs. Sur ce même checkpoint, les 832 caractères sont conservés, sans modifier l'objectif ni les critères. Le protocole compact conserve aussi le chemin exact de livraison de la mission. Les premiers essais CSV/JSON ont calculé la bonne sortie, mais répété des inspections sans livraison complète ; ils ont été arrêtés et ne sont pas déclarés réussis. Cette mesure de contexte ne prouve pas une amélioration générale de la qualité ni une réussite AGI. Un essai ultérieur de fichier `checkpoint.txt` termine à tort `completed` après 523,5 secondes : le contenu est correct, mais le fichier reste hors du répertoire Delivery et aucun transfert n’est reçu. Les mémoires rappelées contiennent des chemins temporaires d’anciennes missions effectivement recopiés par le modèle. Le superviseur transmet désormais ce rappel comme données historiques dans un message séparé, après l’objectif original, uniquement dans le budget restant après les observations récentes. Il ne les incorpore plus aux instructions système. Les chemins workspace/Delivery actuels restent explicites dans l’état obligatoire et les contextes de vérification/revue. Les mémoires persistantes sont conservées ; les consignes des workers restent séparées de ce rappel. Après cette correction, le nouvel essai écrit le fichier dans le bon dossier Delivery et exécute l’assertion demandée ; sa fin échoue néanmoins à 248,5 secondes, car le vérificateur séparé omet un critère dans ses trois propositions. Pour plusieurs critères, son décodage impose désormais un objet avec chaque critère comme clé obligatoire et une liste non vide de contrôles. Le serveur valide ces groupes puis les transforme en contrôles ordinaires avant toute exécution ; les gros schémas conservent la borne et le contrôle de couverture à l’exécution. Ce format ne garantit pas la justesse sémantique des contrôles. La reprise réussit réellement en 89,31 secondes avec le CLI installé : statut `completed`, réception de `checkpoint.txt`, 10 octets exacts `AURORA_OK\n`, empreinte concordante et entrée CSV conservée. Le premier watcher privé avait utilisé un mauvais champ de curseur et relu d’anciens événements ; son résultat est exclu. La commande installée `jobia missions watch` a utilisé le vrai curseur de reprise.

Le tunnel conserve son adresse et son processus existants. Les diagnostics authentifiés et téléchargements passent depuis cette machine par l'URL HTTPS publique ; les diagnostics CLI sans clé sont refusés avec 401. Une vraie connexion SSE locale reprend après redémarrage du bridge au curseur observé, sans répéter l'acceptation POST. Cloudflare [maintient l'absence de support SSE des Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) (consulté le 6 octobre). Le serveur ajoute donc `GET /api/cli/mission/<id>/events`, avec curseur `Last-Event-ID`, lots de 256 événements et attente bornée à 20 secondes. Le CLI choisit automatiquement ce suivi JSON pour les hôtes `*.trycloudflare.com`, conserve les GET SSE ailleurs et refuse les trous de séquence ou les fins sans événement terminal. Ce suivi ne relance aucun outil ni POST et n'apporte pas de garantie de disponibilité du tunnel temporaire. Le chat POST et les flux frontend restent à distinguer de ce transport durable de mission. Les premiers essais publics terminés utilisaient encore la copie CLI installée avant le correctif, donc SSE : un premier événement observé à 153,38 secondes ne prouve pas le nouveau transport JSON. Après réinstallation, le SHA-256 du `bridge.py` installé correspond au dépôt et `mission_poll` est présent. Une mission neuve via le vrai client installé et le tunnel public termine en 231.34 secondes, avec premier événement à 0.352 seconde, 388 GET JSON réussis, assertion Python réelle et téléchargement exact des 10 octets attendus. Les durées de missions différentes, parfois mises en attente par le daemon, ne constituent pas un benchmark comparatif des modèles. Le CLI installé suit aussi effectivement une délégation publique par ces GET.

Une délégation publique réelle termine en 229,74 secondes. Le worker exécute `inspect_runtime`, `list_files` et `read_file`, lit `AGENT_OK`, termine `completed` et passe les contrôles du parent. L’entrée est inchangée et le workspace ne contient que `input.txt`. Le modèle a aussi créé un rôle enregistré `worker` (`dyn_9b0289a9e37e`) : il est conservé, et aucun rôle existant n’a été remplacé. **Cet essai prouve l’exécution de l’agent et la conservation du workspace, pas l’absence de tout effet hors du workspace** : le registre global a reçu cet ajout. Le jugement de fin du modèle ne démontre pas le respect universel de toutes les contraintes.

Le noyau actif reste `7.0.0-34-generic` : le module NVIDIA installé est celui de `7.0.0-31-generic`, `nvidia-smi` échoue et les sondes locales TRELLIS/Hunyuan ne voient aucun GPU CUDA. Le vrai démarrage ComfyUI échoue avec code 1 et `No CUDA GPUs are available`, transmis par l'API. Le moteur image est réellement invoqué et échoue immédiatement car ComfyUI refuse la connexion, sans image livrée. Les générations neuronales axolotl/Natsu et la qualité des modèles GPU restent non validées. `--check-runtime` en mode automatique voit par ailleurs un service Meshy configuré joignable ; cette readiness distante n'est pas une génération locale ni une validation des moteurs CUDA. Aucun crédit de génération externe n'est consommé pour ces contrôles.

`sudo -n true` exige le mot de passe de l'utilisateur. La commande préparée est `sudo apt-get --no-remove install linux-modules-nvidia-595-open-7.0.0-34-generic nvidia-driver-595-open`. La simulation actuelle prévoit 16 mises à jour et 7 nouveaux paquets, dont un noyau, sans suppression ; elle diffère de la simulation historique du 5 octobre. Aucun paquet privilégié ni réglage de protection n'est modifié par cette session.

Validation logicielle actuelle : **778 tests CLI** (18 ignorés, 5 sous-tests) et **322 tests serveur/Auto-RL** (190 sous-tests), types TypeScript, build web, quatre tests du hook runtime avec dépendances substituées, test Rust des journaux et banc de conformance. Le binaire Linux et le paquet Debian amd64 2.0.0 sont reconstruits ; un lancement du binaire reste vivant jusqu'à l'arrêt de l'essai sous Xvfb. Les pages web locale et publique rendent l'interface sans erreur JavaScript dans des profils navigateur isolés ; cela ne démontre pas tous les parcours interactifs natifs. L'installateur CLI réel réussit ; une installation neuve isolée passe `pip check`. La [matrice serveur au commit `6b5fd0e`](https://github.com/juancodepyandc/juan-of-bike-ia-linux/actions/runs/37434382150) passe ses six configurations après le correctif du format de vérification ; une fixture Windows qui traduisait LF en CRLF est corrigée en écriture d’octets exacts. La [matrice CLI au commit `f138f02`](https://github.com/juancodepyandc/aurora-remote-cli/actions/runs/37432418249) passe aussi ses six configurations. Les premiers passages serveur révèlent une dépendance HTTP absente, une assertion de chemin temporaire non canonique sur macOS et l’import du contrôleur Linux sur Windows. La dépendance CI et le test de chemin sont corrigés ; le bridge charge le contrôleur uniquement sous Linux et expose une indisponibilité explicite ailleurs. L'environnement CLI préexistant a un conflit facultatif OpenCV 5/NumPy 1.26, conservé et signalé sans mise à niveau globale. Les fichiers détaillés, checkpoints, sources de tests et journaux restent privés dans `~/maintenance-aurora-2026-10-06`. L'inventaire de septembre conserve ses écarts documentés et n'est pas approuvé par remplacement aveugle de ses empreintes.

### 1.19 Après redémarrage, 6 octobre, puis reprise du 7 octobre 2026

L'accès local est réellement vérifié les deux jours par lecture, écriture temporaire et exécution. Le noyau actif est `7.0.0-38-generic`, avec NVIDIA 595.91.07 et la RTX 5070 Ti reconnue. Le Python ComfyUI, Torch 2.11.0+cu128, exécute un calcul CUDA réel ; les sondes TRELLIS et Hunyuan voient aussi CUDA et leurs imports, sans charger leurs poids. Les limites GPU de la section 1.18 décrivent l'état **avant** redémarrage. Aucune ancienne commande administrateur pour le noyau 34 n'est rejouée.

Le checkpoint essentiel est dans `~/maintenance-aurora-2026-10-06/post-reboot-1123/checkpoint-essential.json`. Les formulaires web local et public affichent exactement `AURORA_WEB_OK`, sans erreur JavaScript observée, avec `qwen3-coder:30b`. L'application native réelle sur le bureau reçoit une demande par son champ et son bouton avec AT-SPI et affiche exactement `AURORA_NATIVE_OK` ; elle utilise `qwen3-vl:8b` et la conversation préexistante, conservée. Ce parcours prend 109,78 secondes : son contexte et son orchestration diffèrent des petits essais web et ne constituent pas une comparaison de performance contrôlée.

La commande installée `jobia connect --server ...` échouait avec un mauvais nom d'argument. Elle est corrigée ; l'échec d'enregistrement retourne un code non nul. Elle ouvre le chat automatiquement seulement dans un terminal interactif, avec choix explicite `--interactive` / `--no-interactive`. `jobia mission --permissions ...` choisit un niveau pour cette mission sans modifier la configuration sauvegardée `SAFE`. La copie installée est mise à jour avec `pip install --no-deps --no-build-isolation .`, sans toucher aux dépendances partagées. Le commit CLI `5cce9f2` est publié ; **783 tests CLI** passent, avec 18 ignorés et 5 sous-tests. Sa [matrice CI](https://github.com/juancodepyandc/aurora-remote-cli/actions/runs/37444292751) réussit.

Une mission locale via la commande installée et une mission publique via son véritable client terminent `completed`, avec réception de `checkpoint.txt`, exactement 10 octets `AURORA_OK\n` et SHA-256 `ac701401efb5d16cc099c5a2954ba8d88e725134cecf3c81be04eadef281e29c`. Le suivi public utilise 115 GET JSON, avec premier événement à 0,485 seconde ; l'entrée CSV reste identique. L'essai initial d'écriture en SAFE, arrêté par l'opérateur, est exclu. Les contrôles publics partent de ce PC, sans essai d'un Mac externe. L'adresse courante vient de `tunnel.txt` et doit être recontrôlée.

Le lanceur réutilise Ollama, ComfyUI, Vite, bridge/daemon prêts, le tunnel Aurora vérifié et le watcher existant. Les services supervisés en cours de démarrage sont attendus par leur protocole ; leurs limites et missions sont conservées. Une unité ComfyUI existante est privilégiée pour garder ses plafonds mémoire. Un verrou sérialise les lanceurs coopérants sans rester hérité par leurs enfants. Le tunnel est identifié par son argv et son propriétaire ; les anciens `pkill` globaux sont supprimés. Le vérificateur public exige le JSON `ok=true`, `service=aurora-bridge`, et rejette un simple HTTP 200 étranger. Les empreintes de sources et d'artefacts évitent de reconstruire un build inchangé ; un build échoué empêche l'ouverture d'un ancien binaire. L'application native déjà ouverte est réutilisée. Une relance réelle conserve PID et URL, en 0,85 seconde, avec cache établi. Ce constat ne garantit pas tous les gestionnaires de services et toutes les courses possibles.

Les **330 tests serveur/Auto-RL**, les types TypeScript, les builds web/natif et le banc de conformance passent. Le 7 octobre, bridge, daemon, ComfyUI, Vite, binaire natif et tunnel sont toujours actifs. Les modifications du lanceur restées locales pendant l'interruption sont conservées. Le fichier CLI non suivi `reprise` conserve son empreinte initiale. Modèles, environnements, données et secrets sont préservés. Les écarts historiques de l'inventaire de septembre restent signalés ; les empreintes ne sont pas remplacées pour masquer les alertes.

Deux générations **réelles** FLUX.2 GGUF Q4_K_M, encodeur Mistral fp8 et VAE FLUX.2, terminent : axolotl 1024², seed 42, 28 pas, environ 235 secondes ; Natsu avec un fusil 1216×832, seed 43, 28 pas, environ 217 secondes. Les PNG et métadonnées restent dans les dossiers `generated-axolotl` et `generated-natsu` du checkpoint privé. L'inspection visuelle reconnaît les sujets ; elle relève aussi un défaut : le directeur de prompt ajoute un ciel à Natsu malgré la demande de fond blanc. La conformité complète, la reconstruction 3D et une compréhension générale ne sont donc pas annoncées à partir de ces fichiers. La reprise du 7 octobre poursuit ces contrôles ; ses preuves sont dans `~/maintenance-aurora-2026-10-07`.

<a id="ensemble"></a>
## 2. Vue d’ensemble

Aurora est un ensemble de clients et de pipelines locaux. Le frontend React orchestre une partie des traitements ; le bridge Flask expose le système et les moteurs ; le daemon `agi_core` exécute les missions du CLI. Les chemins partagent du matériel et certains moteurs mais **ils ne sont pas encore un pipeline unique**.

```mermaid
flowchart TD
  Native[Application Tauri + React] --> IPC[Commandes Rust]
  Native --> Bridge[Bridge Flask :3001]
  Web[Navigateur local ou mobile] --> Bridge
  Web --> Vite[Vite :1420 en développement]
  Vite --> Bridge
  CLI[CLI Python aurora / jobia] --> HTTP[HTTP JSON et SSE]
  HTTP --> Bridge
  Remote[Client distant] --> Tunnel[Tunnel HTTPS]
  Tunnel --> Bridge
  Bridge --> Ollama[Ollama :11434]
  Bridge --> Comfy[ComfyUI :8188]
  Bridge --> Python[Services Python / Node / outils]
  Bridge --> Bus[Bus TCP local :3002]
  Bus --> AGI[Daemon agi_core]
  AGI --> Ollama
  AGI --> Python
  AGI --> Memory[Mémoire Chroma + SQLite]
  AGI --> Journal[Journal durable de missions SQLite]
  Bridge --> Journal
  IPC --> Ollama
  IPC --> Comfy
  IPC --> Python
  Training[auto_rl / campagnes Kaggle] --> Audits[Évaluations locales et registre]
  Audits --> Adapters[Adaptateurs explicitement validés :11435 et moteurs]
```

Le nom AGI dans le code désigne des classes et un daemon. Il ne prouve ni une intelligence générale, ni une autonomie sans limite, ni une capacité fiable d’auto-réparation. De même, les mots « validé », « expert » et les notes historiques doivent être rattachés à des critères mesurables.

<a id="composants"></a>
## 3. Composants, processus et données

| Composant | Entrée et responsabilité | Dépendances et sortie |
|---|---|---|
| Frontend | `application/src/main.tsx`, `App.tsx` ; navigation, skins, stores, interactions, orchestration TypeScript | React 19, Zustand, Three.js, API du bridge ou IPC Tauri |
| Natif | `application/src-tauri/src/` ; commandes Rust et accès hôte | Tauri v2, Tokio, reqwest ; bundle `application/dist` intégré au binaire |
| Bridge | `application/bridge_server.py` ; Flask, proxy, ressources, enregistrement des blueprints | Python applicatif ; HTTP 3001, services et fichiers locaux |
| Blueprints | `application/routes/*_routes.py` | CLI, voix, FS, Python, médias, matériel, recherche, connecteurs |
| Moteurs Python | `application/python-services/` | FLUX/ComfyUI, 3D, Blender, STT/TTS, extraction, évaluations et utilitaires |
| Missions | `aurora_agi_daemon.py`, `agi_core/` | Bus TCP 3002, Ollama, sous-processus, mémoire Chroma |
| CLI | `../aurora-remote-cli/aurora_cli/cli.py` | Click, Rich, prompt_toolkit, httpx ; JSON/SSE vers le bridge |
| Wrapper local CLI | `aurora_cli.py` | Importe le dépôt CLI voisin ; impose le bridge local 3001 |
| Découverte distante | `../aurora-live/tunnel.txt` | Adresse du tunnel publiée ; README d’état généré |
| Entraînement | `auto_rl/`, `cycle_app.py`, `kaggle_sync/` | Jeux de préférences, calcul distant borné, audits locaux, adaptateurs |
| Extensions | `application/extension/`, `application/aurora-connect-extension/`, `extension_chrome/` | Connecteur navigateur et interfaces de pont ; certaines variantes sont historiques |

### 3.1 Ports et supervision

| Port | Rôle dans le code | Exploitation constatée / prudence |
|---|---|---|
| 3001 | Bridge Flask | Service utilisateur `aurora-bridge` ; écoute `0.0.0.0` dans le point d’entrée |
| 3002 | IPC pub/sub du daemon | Écoute localhost ; requis par les missions, absent lors du relevé |
| 1420 | Vite dev UI | Lancé par `npm run dev:web` ou le lanceur ; absent lors du relevé |
| 8188 | ComfyUI | `aurora-comfyui`, localhost, Python de son venv |
| 11434 | Ollama | Service système `ollama` ; modèles locaux |
| 11435 | Inférence des modèles audités | `aurora-trained-models` lance `python -m auto_rl.serve` |
| 3009 | Viewer HTTP de fichiers | `aurora-viewer` ; ne remplace pas le bridge ni le bus |

`start-aurora.sh` et les unités systemd constituent deux mécanismes de lancement. Le script peut tenter de relancer des services déjà présents. Ses variables d’environnement n’affectent pas rétroactivement le processus Ollama lancé par systemd. Une supervision unique avec dépendances, readiness et versions observables est une amélioration prioritaire.

### 3.3 Variante serveur cloud et intégrations navigateur/mobile

`application/cloud/cloud_bridge.py` et `application/cloud/start.sh` constituent une variante de déploiement distincte du bridge local. `bootstrap_runpod_a100.sh` prépare un environnement de GPU distant ; les exigences Python associées sont dans `application/cloud/requirements.txt`. `scripts/start-cloud.mjs` démarre Vite avec `VITE_CLOUD_MODE=true` et une URL de bridge : cette commande seule ne provisionne pas un GPU ni tous les moteurs.

Ne pas assimiler l’ouverture de l’interface locale par tunnel à un déploiement RunPod. Le premier utilise le PC ; le second déplace les processus et le stockage. Les tarifs, disponibilités, sessions et modèles de l’ancien `CLOUD_DEPLOY.md` sont historiques, pas des recommandations actuelles. Aucun déploiement cloud n’a été testé dans cette consolidation. La compatibilité des deux bridges doit faire partie de la matrice de contrats.

`application/extension/` est identifié comme source canonique par le manifeste de `extension_chrome/`, qui conserve un fallback obsolète. `application/aurora-connect-extension/` contient une autre variante Manifest V3 avec service worker, scripts de contenu et accès aux onglets. Identifier l’extension effectivement installée avant de modifier un connecteur. Les permissions `<all_urls>`, l’origine de connexion et les données extraites demandent un contrôle explicite.

Les anciens plans Pronote/ENT décrivent collecte du DOM, authentification utilisateur, extraction structurée et rapprochement avec Academy. Une proposition dans ces plans ne prouve pas son implémentation. Les parcours d’extraction réels sont à rapprocher de `cowork_ext_bp_routes.py` et de l’extension chargée. Le mobile React, `application/mobile/` et `application/aurora-mobile-bridge/` sont également des surfaces différentes ; ne pas attribuer leurs capacités à une seule application mobile universelle.

### 3.2 Données et frontières

| Données | Emplacement / propriétaire | Règle |
|---|---|---|
| Sorties applicatives | `application/output/<module>/<projet>/...` | Contrat de `python-services/aurora_output_paths.py`, façade `sortie_module()` |
| Livraisons distantes | `<workspace>/.transfer_to_client/<mission_id>/` | Artefacts à vérifier et à télécharger ; une présence serveur ne prouve pas une livraison client |
| Sessions et états CLI serveur | `$XDG_DATA_HOME/aurora/`, par défaut `~/.local/share/aurora/` | JSON : sessions, agents dynamiques, états, connexions ; données privées |
| Configuration CLI client | Résolue par `aurora_cli/core/paths.py` et `config.py` | XDG / conventions de l’OS ; ancienne configuration `~/.aurora` migrée si nécessaire |
| Mémoire des missions | `db_vector/`, Chroma | Ancien `db_vector` conservé s’il existe ; surcharge `AURORA_MEMORY_DIR`, puis répertoire de données utilisateur |
| Conversations et UI | Stores Zustand, stockage navigateur, IndexedDB pour certains blobs | Une origine localhost et une origine de tunnel n’ont pas le même stockage navigateur |
| Modèles | `modele/`, caches Hugging Face, Ollama utilisateur et système, `~/.local/share/auroraia/` | Ne pas confondre cache de modèles et cache jetable |
| Environnements | `.venv`, ComfyUI/venv, Conda, outils locaux | À préserver avec leurs versions ; absence d’un paquet dans un venv ne prouve pas son absence partout |
| Secrets | `.secrets/`, clés d’extension, config CLI, connexions, variables d’environnement | Ne jamais copier les valeurs dans ce maître, les logs ou une archive publique |

<a id="parite"></a>
## 4. Application standard, web distant et CLI

| Fonction | Natif / interface standard | Navigateur / tunnel | CLI |
|---|---|---|---|
| Navigation et rendu | React, skins, Tauri | Même frontend si le bundle servi correspond | Interface terminal séparée |
| Accès hôte | Commandes Rust + HTTP local | HTTP du bridge, chemins d’assets accessibles à distance | Outils et fichiers côté serveur, puis transfert explicite |
| Conversation | `conversationOrchestrator.ts` : intention, recherche, génération, vérification selon le parcours | Même orchestration frontend sous réserve des transports et capacités navigateur | `chat_stream` ou mission autonome ; ne pas supposer une équivalence au pipeline UI |
| Code | `codeOrchestrator.ts`, sandbox, corrections et critères de livraison | Même pipeline ou runners Node via bridge selon l’entrée | Boucle de mission `agi_core`, outils, contrôles explicites et revue LLM de conclusion |
| Image | `useImageViewLogic.ts`, workflows FLUX, références, retouches | API/ComfyUI via bridge, reprise partielle des états | Outil `generate_image` et moteur Python ; contrat différent de la galerie UI |
| 3D | Planification TS, pipeline Python, viewer Three.js | Flux d’assets et API ; latence et chemins distants à prendre en compte | Scripts/outils accessibles ; pas de preuve de parité automatique avec toutes les étapes UI |
| Voix | Microphone, rendu, overlay, STT/TTS | Permissions navigateur, HTTPS et transport requis | Capacités disponibles par outils ; pas une réplique de l’overlay vocal |
| Progression | Événements frontend, polling, streams | Dépend des proxys et du type de tunnel | SSE avec curseur et reprise limitée |
| Arrêt / reprise | AbortController et contrats propres aux moteurs | Déconnexion réseau distincte d’une annulation | Demande d’arrêt via bridge et bus ; journal SQLite, checkpoint et reprise explicite du même objectif |
| Modèle par défaut | Config TypeScript et sélection adaptative | Config frontend + réalité des modèles serveur | `_ext_default_model()` et `LLMGateway` peuvent choisir un autre modèle |
| Connexion | Accès hôte/local selon la surface | Auth et exposition à vérifier route par route | Clé Bearer existante requise sur `/api/cli/*` |

**Conclusion d’architecture :** même machine et mêmes poids ne signifient pas même chemin logiciel, mêmes paramètres, mêmes garanties ou même résultat. L’objectif d’amélioration est un contrat partagé et une parité mesurée, pas une simple égalité de noms dans les menus.

<a id="priorites"></a>
## 5. Constats et priorités d’amélioration

Les travaux ci-dessous sont des **propositions**, pas des correctifs exécutés par cette consolidation. Les priorités reflètent l’impact ; elles ne constituent pas une note de qualité globale.

| ID | Priorité | Constat et preuve locale | Amélioration et critère d’acceptation |
|---|---|---|---|
| A01 | P0 | Suivi JSON durable dans `aurora_cli/bridge.py` pour les Quick Tunnels ; mission et livraison publiques observées en sections 1.18–1.19 | Maintenir la reprise par curseur et tester les autres transports ; ne pas attribuer à un Quick Tunnel le support SSE ni une disponibilité permanente |
| A02 | P0 | Historique : le diagnostic annonçait SSE sans flux réel ; désormais son état est `unverified` et la readiness mission exige une réponse IPC avec abonnement `mission.start` | Distinguer liveness, readiness et test fonctionnel ; vérifier daemon, abonnement IPC et événement de test non destructif ; rendre un statut dégradé et un code retour exploitable |
| A03 | P0 | Contrôle direct des outils ajouté : SAFE bloque écritures/commandes, sous-agents bornés par les permissions du parent ; le shell de l’hôte reste sans sandbox OS | Centraliser l’autorisation au point d’exécution, y compris sous-agents ; tests négatifs SAFE/STANDARD et frontières de workspace ; aucun contournement par shell |
| A04 | P0 | Plusieurs API non-CLI exposent fichiers, commandes ou moteurs ; présence d’un décorateur seule insuffisante pour juger la couverture | Matrice routes × authentification × capacité × origine ; refus vérifié des appels non autorisés, contrôle CORS et exposition du bridge ; ne pas ouvrir un tunnel en assimilant URL difficile à deviner et protection |
| A05 | P0 | Corrigé pour le journal des missions : SQLite, clés d'idempotence, événements et checkpoints, curseurs persistants et baux | Étendre la reprise propre à chaque moteur ; ne pas confondre le journal et une garantie exactement une fois pour les commandes externes ; valider aussi le tunnel réel |
| A06 | P1 | UI Code : `qwen3-coder:30b` ; CLI/AGI : priorité à `qwen3-coder-next:q4_K_M` | Un registre commun des modèles et profils, overrides explicites par mission ; mêmes prompt/seed/paramètres comparés entre clients et différence documentée |
| A07 | P1 | Corrigé pour les skills : `agi_core/context.py` découvre et injecte les instructions ; MCP et connexions restent des déclarations non testées | Charger réellement les skills/MCP/connexions utiles et tracer leur usage ; un skill de test doit changer le contexte de la mission, pas seulement apparaître dans `doctor` |
| A08 | P1 | Réutilisation et attente des services, conservation du tunnel et verrou de lancement corrigés ; relance réelle sans changement de PID/URL en section 1.19 | Poursuivre l'unification de la supervision ; les variables exportées par un script ne reconfigurent pas un Ollama système déjà actif |
| A09 | P1 | Réservation mémoire entre vision, FLUX, 3D et LLM distribuée entre composants | Ordonnanceur GPU commun avec budget mesuré, file et annulation ; corpus à qualité constante, RAM/VRAM/swap et latence médiane/p95 publiés |
| A10 | P1 | Pipelines Image/Code/3D différents entre UI et CLI | Contrat `job/artefact/erreur` commun ; corpus identique par transport, récupération vérifiée et reprise sans produire à nouveau un artefact accepté |
| A11 | P1 | Registre runtime applicatif `application/agent_registry.py` (13 rôles), distinct des exports des agents de développement ; tracker historique à réconcilier | Registre unique agents → hiérarchie → API → affichage ; validateur sans écart ; conserver les rôles existants lors de la migration |
| A12 | P1 | Empreintes de sources et d'artefacts vérifiées par `scripts/launch_runtime.py` ; reconstruction et erreurs du lanceur corrigées en section 1.19 | Rendre l'identité du build effectivement chargé observable sur chaque surface ; un binaire déjà ouvert ne recharge pas automatiquement son nouveau fichier |
| A13 | P1 | CLI `main` harmonisé à Python ≥ 3.10, conventions de chemins par OS et environnement client distinct ; seul Linux/Python 3.12 est exécuté ici | Version supportée explicite, environnements reproductibles, dépendances du CLI séparées des moteurs ; installation neuve et diagnostics sur les OS pris en charge |
| A14 | P1 | Évaluation Image/3D parfois limitée à structure, netteté, métriques ou anciennes notes | Corpus sémantique annoté : sujet, quantités, relations, texte, identité ; distinguer validité technique, conformité et qualité visuelle |
| A15 | P2 | Couplage `routes/*` → `bridge_server`, regroupements très volumineux | Extraire services de domaine et schémas, puis factory d’application testable ; tests de contrat conservant les API existantes |
| A16 | P2 | Variantes UI et scripts historiques nombreux | Graphe d’imports + couverture d’usage avant suppression ; partager logique métier, garder différences visuelles intentionnelles ; ne pas déduire « inutilisé » du seul nom V1/V3 |
| A17 | P2 | Modèle documentaire ancien fragmenté et majoritairement ignoré par Git | Deux sources éditables : ce maître et AGENTS ; exports contrôlés, empreintes de code, revue de fraîcheur ; historique dans archive vérifiée |

**Preuve externe pour A01 :** Cloudflare documente l’absence de prise en charge de SSE par les Quick Tunnels. C’est une incompatibilité annoncée avec le transport utilisé par le CLI ; cela ne prouve pas à lui seul l’origine de tous les incidents passés. La migration doit être testée sur le vrai trajet distant. [Cloudflare — Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) (consulté le 24/09/2026).

### Plan de réalisation proposé

1. Rendre les diagnostics fiables, observer daemon/bus et tester le transport externe.
2. Définir les contrats de mission, permissions, événement, annulation et livraison ; couvrir les erreurs avant unifier les implémentations.
3. Aligner modèles, profils mémoire et chemins de génération entre interface et CLI.
4. Mesurer la qualité réelle avec un corpus commun ; optimiser après attribution du temps à la file, au chargement, à l’inférence et au transfert.
5. Consolider supervision, build, stockage et observabilité ; supprimer seulement les branches réellement remplacées et testées.

<a id="interface"></a>
## 6. Interface et état

### 6.1 Structure React

`src/main.tsx` monte l’application. `App.tsx` assemble navigation, overlays, skins, états globaux, recherche, voix et diagnostics. Les vues sont chargées paresseusement et protégées par des frontières d’erreur. `utils/uiSkinViews.ts::pickView()` choisit un loader selon le skin et ses fallback ; l’existence d’une ancienne vue ne signifie pas qu’elle est morte.

Les familles Aurora V1, V3, V4 et Manga coexistent dans `src/views/` et `src/components/`. Les interfaces mobiles peuvent déléguer à `MobileGrimoire`. `utils/runtime.ts` distingue navigateur, Tauri et cloud/tunnel ; `getBridgeUrl()` utilise HTTP local hors mode distant et des URL relatives dans le chemin cloud.

`hooks/useTauri.ts` est une couche essentielle : commandes Tauri, accès Ollama/ComfyUI, requêtes bridge, progrès Python et adaptation de transport. Le nom ne signifie pas « réservé au natif ». Le code possède aussi une adaptation Node pour éviter qu’un timeout HTTP générique interrompe une commande longue correctement autorisée.

### 6.2 État et persistance

`stores/appStore.ts` gère navigation, matériel, services, travaux, profils, modèles et packs d’assets. Les stores de chat, historique par module, Cowork, apprentissage et brouillons ont leurs propres responsabilités. Les blobs d’images passent notamment par `utils/blobStore.ts`; une URL `blob:` seule n’est pas une référence durable ni transférable à un autre client.

Ne pas réunir tous les stores dans une seule persistance sans migration. Distinguer données utilisateur, état transitoire d’UI, état de tâche serveur et cache. Le partage d’une origine web change le périmètre du stockage local et ne remplace pas des sessions serveur.

### 6.3 Builds

`application/package.json` définit `typecheck`, `check`, `build`, conformance, Vite et Tauri. `npm run check` enchaîne les types TypeScript et le build Vite. `npm run build` seul ne les remplace pas. `vite.config.ts` définit proxies, chunks et métadonnées de build.

Le bundle `dist` est incorporé au binaire Tauri de release. Mettre à jour `dist` ou le serveur Vite ne suffit pas à mettre à jour un binaire natif déjà compilé. Les options CSP et les capacités hôte se trouvent dans `src-tauri/tauri.conf.json` et les fichiers Rust ; les vérifier lors d’un changement de transport ou d’assets.

<a id="modules"></a>
## 7. Modules fonctionnels et chaînes de traitement

### 7.1 Conversation

Entrées : vues Chat/Conversation et `services/conversationOrchestrator.ts`. Le moteur classe la complexité et l’intention, prépare le contexte, peut rechercher des sources, émet des tokens et des étapes, puis vérifie/affine selon le parcours. Le mode vocal peut raccourcir le chemin. Un cache module-local conserve certaines réponses avec TTL et seuil de similarité.

Composants : `realityAnalyzer.ts`, `intentRouter.ts`, `conversationToneMatcher.ts`, `webResearch.ts`, `conversationVerification.ts`, `modelJson.ts`, `responseCache.ts`, `ollamaStream.ts` et watchdog de premier token. Les citations doivent représenter les sources effectivement consultées. Un cache performant mais ignorant l’historique ou la consigne dégrade la justesse : toute optimisation doit tester les suivis de conversation et les changements de contexte.

### 7.2 Code

Entrée principale : `services/codeOrchestrator.ts::orchestrateCodeGeneration()`. La façade coordonne intention, dossier de mission, préparation, plan, préflight, génération initiale, parsing, assets intermodules, validation/correction et livraison. Les modules `codePipeline*`, `codeGeneration*`, `codeValidation*`, `codeQuality*`, `codeSandbox*` et `codeDelivery*` sont des responsabilités séparées, pas seulement des utilitaires interchangeables.

Le pipeline possède des garde-fous pour préserver le dernier état des fichiers lors d’une interruption et pour distinguer livraison partielle et réussite. Le sandbox, les sorties de build, la jouabilité, l’intégrité web, le design et la conformité à la demande ne sont pas une seule métrique. L’agent général du CLI n’exécute pas nécessairement toutes ces étapes : la parité doit être démontrée sur un même projet et les mêmes critères.

### 7.3 Image

UI : `hooks/useImageViewLogic.ts`, workflows FLUX/Kontext dans `utils/`, recherche de références, contrat de prompt, galerie, verrou de génération, historique de seed et reprise de blobs. `services/comfyJobMonitor.ts` suit les travaux et distingue erreurs, attente et sortie.

Moteur Python : `python-services/image_module_engine.py`. Il construit un workflow, soumet à ComfyUI, attend une image et produit un manifeste. Sa version présente contient une attente de 1 800 secondes et des erreurs explicites : l’ancien audit qui décrivait encore 360 secondes ne doit pas être repris comme état actuel. Les contrôles de netteté/contraste ne prouvent pas le respect du sujet.

Le modèle configuré dans le frontend est FLUX.2 avec UNet GGUF Q4_K_M, encodeur Mistral et VAE associé. Vérifier les fichiers effectivement résolus par ComfyUI, les nodes installés et le workflow exécuté avant d’attribuer une sortie à un modèle.

### 7.4 Dessin et Character Forge

`hooks/useDrawingViewLogic.ts` distingue croquis artistique et explication structurée. Les services de graphe/explication valident la structure et peuvent demander une réparation bornée. Une explication structurée valide peut encore être factuellement fausse : les deux verdicts doivent être séparés.

`services/characterForge.ts` et l’overlay correspondant coordonnent plusieurs étapes et modules. Les documents historiques décrivent notamment identité, références, génération, segmentation et livraison ; l’état réel doit être suivi dans les fonctions et sorties du pipeline. Les workflows d’édition doivent conserver seed, références, étape courante et cause d’interruption.

### 7.5 3D et animation

Routage frontend : `threeDIntent.ts`, `threeDViewPlanner.ts`, services de références, motion, mesh et validation glTF. Le pipeline Python `aurora_3d_pipeline.py` s’appuie sur des moteurs spécifiques, génération de références, contrôles géométriques, export et éventuellement rigging/motion.

Les wrappers `python-services/aurora_hunyuan/` incluent l’intégration TRELLIS ; des parcours Hunyuan, Blender procédural, DreamGaussian et photogrammétrie peuvent coexister selon installation et demande. Les noms hérités « hunyuan » ne suffisent pas à déterminer le moteur exécuté. La configuration marque TRELLIS.2 comme expérimental à partir de 24 Go de VRAM, tandis que le poste observé dispose de 16 Go : documenter le profil réel, l’offload et les limites plutôt que promettre une capacité universelle.

Une livraison 3D doit distinguer : fichier lisible, géométrie valide, échelle/axes corrects, matériaux/UV, silhouette conforme, référence respectée, rig utilisable et animation sans déformations excessives. Le validateur GLB ne prouve pas tout cela. Les outils de rescue, sharpen, comparaisons et rendu doivent rester reproductibles.

Le juge automatique 3D de `auto_rl/judges.py` rend quatre vues orthographiques par `auto_rl/render_mesh.py`, puis combine `0,45*topologie + 0,35*clip_moyen + 0,2*clip_pire`. La topologie est `1 - 5*nonmanifold - frontieres - fragments - degeneree`, multipliée par `1/(1 + auto_intersections/faces*20)`. Deux invariants doivent être lus avant de toucher au rendu : le cadrage est calibré sur l'absence de rognage et non sur le score (à 1,35 trois vues sur quatre étaient coupées ; 1,60 ne l'est plus et reste 6/6 gagnant), et le gate de `auto_rl/evaluation.py` compare des deltas candidat-base, pas des scores absolus — un cadrage commun aux trois branches déplace donc les deltas de zéro, tandis que les scores absolus ne sont comparables qu'entre audits rendus pareil. `self_intersections` reste mesuré sur la géométrie complète, jamais sur la boîte cadrée.

Fragmentation des maillages TRELLIS : diagnostic résolu, et une affirmation antérieure était doublement fausse. La cause n'est pas géométrique mais **d'indexation** : la surface est continue au 1e-9, mais chaque îlot de texture reçoit sa propre copie des sommets situés sur la couture. La distance médiane d'un sommet à son plus proche voisin situé dans une *autre* composante vaut exactement 0,000000, et 66,4 % des sommets ont un tel voisin à ≤ 1e-5. Sur la validation 12 pas, 8 103 composantes connexes pour 97 623 faces ; sur la scène Natsu, **951 618** pour 967 762 faces, soit presque un îlot par triangle. Une mesure antérieure concluait à tort que « le soudage ne fusionne que 172 sommets sur 90 609 » : c'était un artefact d'appel, trimesh 4.12 n'a pas de paramètre `tolerance` mais `digits_vertex` (arrondi à N décimales), et le fusionnement « exact » par défaut ne faisait rien.

**Ce que le juge voit, et ne voit pas.** `auto_rl/judges.py` (MeshJudge.score) soude **déjà** une copie (`topo.merge_vertices(merge_tex=True, merge_norm=True)`) avant de compter les composantes. Le juge est donc immunisé contre cet artefact : `fragment` vaut 0,93 à 0,95 sur un maillage non soudé et 0,07 à 0,32 sur le même maillage soudé, et cet écart était déjà capté avant tout correctif. **La soudure n'améliore donc pas le score du juge**, et une mesure de fragmentation prise sans la soudure du juge surestime massivement le gain. Le correctif `auto_rl/weld_fragmented_mesh.py` rapporte désormais les deux mesures séparément (`components_raw_*` pour l'indexation du fichier, `components_judge_*` et `fragment_*` pour la métrique du juge), et son rapport porte `judge_already_welds: true` pour empêcher toute relecture erronée.

**Ce que la soudure apporte réellement.** Trois bénéfices mesurés, tous vérifiés. (1) Elle débloque la décimation, qui l'était réellement : le quadric de pymeshlab est contraint par `preserveboundary=True` et bute sur chaque îlot. Validation 12 pas, cible 40 000 : 97 623 → **58 329** sans soudure, → **39 999** avec. Scène Natsu, cible 45 000 : 967 762 faces obtenues auparavant, **45 000** maintenant, 200,7 Mo → 90,4 Mo. (2) Elle livre des `.glb` dont l'indexation est saine, ce que paient le rendu temps réel, le culling et tout outillage qui ne soude pas. (3) Le rendu est rendu indexation-indépendant : les percentiles de cadrage de `render_mesh.py` portent désormais sur les positions uniques, sinon souder déplaçait les percentiles, donc la caméra, donc les scores CLIP, à forme identique. Mesuré, ce changement vaut +0,00099 de clip moyen (+0,38 %) sur le même maillage.

La soudure est non destructive (l'entrée n'est jamais modifiée, écriture atomique, refus d'écrasement, garde-fou à 0,5 % de faces perdues) et respectueuse de la texture : `merge_tex=True` ne fusionne que des sommets de même position **et** même UV, donc l'atlas n'est jamais écrasé. Vérifié : géométrie des faces identique à 1e-9, normales de faces identiques à 0,0, UV alignées sur les sommets, zéro face perdue sur Natsu. Le coût CLIP de la soudure seule est de -0,0018, et celui de la décimation 21× de Natsu de -0,0102. La fragmentation touchait tous les livrables TRELLIS, y compris un `pipeline-ok` qui mesurait 6 214 composantes. Restent écartés, pour des raisons toujours valides : plus d'étapes de diffusion dégrade la fragmentation (0,074 à 12 pas contre 0,337 à 24) et le remesh supprime les frontières mais ramène l'atlas de 8192² à 2048².

Une scène multi-entités qui échoue doit rester un échec lisible. Sur le run `Natsu_dragneel_enrage_3_4_fond_blanc`, l'orchestrateur a planifié deux entités (`loutre` + `fusil`) et n'a produit que la première : la synthèse FLUX de la référence du fusil a expiré deux fois à 1800 s, le dossier `models/fusil/` ne contenait qu'un journal, et la pipeline est repartie en objet unique alors que le prompt décrivait plusieurs entités. Trois défauts ont rendu ce naufrage muet. La libération VRAM avant paint (`_free_gpu_before_shape`) attendait 20 s puis reprenait en annonçant « VRAM libérée » sans avoir vérifié : la décharge d'un `llama-server` de 13 Go prend environ 100 s, donc FLUX partait en paint avec la VRAM pleine. L'attente est passée à 90 s et le journal dit désormais la mesure, ou prévient quand la libération échoue. `scene_orchestrator` calculait `complete` avec une condition absente du message d'erreur, si bien qu'une entité sans GLB produisait `entites refusees ou composition incomplete: []` et envoyait la maintenance chercher du côté des refus ; les entités sans GLB sont désormais nommées. Enfin `AURORA_FLUX_TIMEOUT_S` permet de borner l'attente FLUX sans toucher au code, la garde de job perdu existante ne déclenchant pas quand le job reste en queue.

Un artefact d'audit référencé n'est pas un résidu de test. `resume_audit` recopie les lignes d'évaluation mais pas les maillages ni les rendus : le rapport final référence 1815 chemins absolus pointant vers le run interrompu qui les contient, et la chaîne `lineage.json` / `config.json` rattache aussi les runs échoués. Supprimer ces runs casse la preuve du gate, pas seulement un historique. Les runs doivent être purgés en même temps que les références, jamais séparément.

Mesure de cadrage, contre un premier relevé trompeur : un contrôle « un pixel de matière au bord » signalait 1 vue rognée sur 4 à 36 pas, ce qui a fait re-investiguer le cadrage. En comptant la bande de bord entière, l'ancien facteur 1,60 ne rogne rien de significatif (0,0 % à 1,0 % de pixels de bord, sur 22 % à 32 % d'occupation) : le signal venait des débris, exclus du cadrage mais toujours rendus. Un cadrage ajusté et recentré par vue double l'occupation (47 % à 51 %) mais porte 10 % de pixels au bord, et n'a pas été retenu faute de validation CLIP. Le facteur 1,60 reste l'état validé (+0,0087 sur le clip moyen, 6/6). Toute affirmation de rognage doit distinguer l'objet coupé de la poussière au bord.

Invariance du rendu à l'indexation : les percentiles de cadrage sont calculés sur les **positions uniques** des sommets, et non sur la liste brute. Sans cela le cadrage dépendait du découpage en triangles : souder des sommets dupliqués déplace les percentiles, donc la caméra, donc les rendus et le score CLIP, alors que la surface est inchangée au 1e-9. Le rendu doit être une fonction de la forme, pas de l'indexation. Mesuré, le passage de l'ancien cadrage au nouveau vaut **+0,00099** de clip moyen (+0,38 %) sur le même maillage, soit une bascule neutre à légèrement favorable et non un décalage de référence pénalisant. Conséquence à retenir : deux artefacts de même forme mais de maillage différent ne doivent plus être comparés sur des scores rendus avec des versions antérieures du cadrage.

### 7.6 Voix

Frontend : `VoiceCopilotView`, overlays par skin et services vocaux. Backend : `routes/voice_bp_routes.py` et `python-services/voice_service.py`. Le STT configuré actuellement est faster-whisper large-v3-turbo ; le TTS principal est Kokoro-82M, avec des chemins et secours supplémentaires dans le service. Les anciennes mentions de Voxtral/Fish ne décrivent pas nécessairement le chemin actif.

Transcription, nettoyage de texte, prononciation française, synthèse, conversion audio et lipsync/Rhubarb sont des étapes distinctes. Mesurer délai de transcription, délai premier son, intelligibilité, prononciation et temps réel ; ne pas prendre un fichier audio créé pour une preuve de bonne restitution.

### 7.7 Academy / apprentissage et simulateur

Vues Academy/Learning et `services/learning/` : contenus, quiz, ressources, réponses vérifiables et parcours scolaires. `academicContentVerification.ts`, `learningResearch.ts` et `learningSemanticEval.ts` portent des contrôles différents. Les ressources externes doivent être datées ; un oracle de calcul ne certifie pas à lui seul la pédagogie.

Le simulateur possède ses services de calcul et des contraintes de reproductibilité. Préserver seed, pas de simulation et état de scène lors des optimisations ; la fréquence d’affichage ne doit pas remplacer le pas physique.

### 7.8 Cyber

Vues dédiées, `services/cyber/`, `python-services/cyber/`, prompts et outils. Les instructions de module conservées dans l’annexe définissent le périmètre pédagogique et les validations. Distinguer analyse, laboratoire local, exécution sur une cible autorisée et simple génération d’explications. La politique de permissions doit rester attachée à l’exécution effective.

### 7.9 Cowork, recherche, connecteurs, MCP

Vues Cowork, stores et services d’orchestration ; `routes/cowork_ext_bp_routes.py`, `cowork_file_bp_routes.py`, `connect_bp_routes.py`, `web_search_bp_routes.py` et `web_action_bp_routes.py`. Les fonctionnalités comprennent fichiers, extraction documentaire, recherche, navigateur, connecteurs et découvertes d’outils.

Un connecteur listé dans un catalogue n’est pas forcément authentifié ni opérationnel. Un MCP trouvé ne prouve pas qu’un outil a été exécuté. Le stub de contexte dans le daemon doit être distingué de la découverte réelle du bridge. Les mémoires partagées, profils de personnages UI et agents de développement sont trois mécanismes différents.

### 7.10 Vidéo et autres variantes historiques

Des constantes vidéo, routes cinéma, fonctions de rendu, modèles et modules d’entraînement subsistent. Cela ne prouve pas la présence d’un module Vidéo actif dans la navigation actuelle. Certains anciens documents `aurora-live/modules/` présentaient aussi Manga ou Vidéo comme surfaces principales ; ces descriptions sont archivées, pas reprises comme contrats actuels.

Les exports vidéo/animation peuvent rester des capacités de moteurs ou d’entraînement même lorsqu’une vue a été retirée. Avant de supprimer leur code, vérifier imports, API, campagnes, compatibilité des sessions et fonctions croisées.

<a id="bridge"></a>
## 8. Bridge et contrats HTTP

`bridge_server.py` initialise Flask, CORS, mesures de temps, chemins, découverte d’exécutables, authentification d’extension et proxies. Il enregistre les blueprints à la fin du point d’entrée et démarre en mode threaded sur 3001. Plusieurs blueprints importent des fonctions du bridge : les imports à froid et les chemins dérivés de `__file__` demandent une attention particulière après extraction de code.

| Famille de routes | Responsabilité |
|---|---|
| `cli_bp_routes.py` | Authentification CLI, sessions, permissions, agents, MCP, skills, connexions, missions et SSE |
| `vite_bp_routes.py` | Surface web, diagnostics et multiples outils/contrôles 3D ; groupe très large |
| `python_bp_routes.py`, `python_prog_bp_routes.py` | Exécution Python, jobs et progression |
| `cinema_bp_routes.py`, `voice_bp_routes.py` | Médias, animation et voix |
| `comfy_proxy_bp_routes.py`, `comfy_life_bp_routes.py` | Proxy et cycle de vie ComfyUI |
| `ollama_list_bp_routes.py`, `ollama_enh_bp_routes.py` | Inventaire et opérations Ollama |
| `asset_bp_routes.py`, `fs_bp_routes.py`, `upload_bp_routes.py` | Accès fichiers et assets, téléchargement entrant |
| `hardware_bp_routes.py`, `sysinfo_bp_routes.py`, `status_bp_routes.py` | Matériel, processus et état |
| `repo_bp_routes.py`, `cowork_file_bp_routes.py` | Workspaces, dépôt et fichiers Cowork |
| `connect_bp_routes.py`, `cowork_ext_bp_routes.py`, `ext_bp_routes.py` | Extension/connecteurs, extraction, intégration Cowork |
| `web_search_bp_routes.py`, `web_action_bp_routes.py` | Recherche et actions navigateur |
| `postgres_bp_routes.py`, `s3_bp_routes.py`, `iot_bp_routes.py` | Connecteurs de données et matériel |

Le registre complet des chemins statiques et handlers figure dans l’index. Ce registre n’est pas un schéma OpenAPI et n’exprime pas tous les payloads ni toutes les autorisations. Une proposition utile est de déclarer des schémas partagés, des limites explicites et un format d’erreur stable, puis de les vérifier depuis les trois surfaces.

Les journaux ne doivent pas contenir les en-têtes Bearer, mots de passe, contenus sensibles d’outils ou prompts complets par défaut. Le bus actuel journalise le message reçu : réduire et filtrer cette observabilité avant une exposition plus large.

<a id="missions"></a>
## 9. Missions, bus et mémoire

### 9.1 Parcours réel

```mermaid
sequenceDiagram
  participant C as CLI
  participant B as Bridge
  participant D as Daemon/bus 3002
  participant O as Ollama
  C->>B: POST /api/cli/mission/start + clé d’idempotence
  B->>B: Accepte une demande durable SQLite
  B->>D: mission.start (TCP JSON)
  C->>B: GET flux mission, Last-Event-ID
  D->>O: Planification et appels d’outils fondés sur l’objectif
  D->>D: Outils réels, contrôles et checkpoint
  D->>O: Revue de fin fondée sur les observations
  D-->>B: mission.event
  B-->>C: Événements SSE numérotés
  D-->>B: mission_complete, blocked, stopped ou error
  C->>B: Récupération des artefacts
```

La présence d’Ollama et d’un HTTP 200 de statut ne suffit pas si le daemon n’écoute pas, si l’IPC échoue ou si le flux terminal ne parvient pas au client.

### 9.2 Responsabilités

- `agi_core/bus.py` : pub/sub local et TCP JSON par ligne ; diffusion réseau aux clients, filtrage côté consommateur. Ce n’est pas une file durable ni un broker avec accusés de réception persistants.
- `aurora_agi_daemon.py` : initialise le cortex, abonne `mission.start/stop`, suit les tâches actives et annule sur demande.
- `consciousness.py` : mémoire, superviseur, traitement de requêtes ; analyse de fond facultative, interrompue pour les missions utilisateur. Ce nom historique ne démontre pas une conscience.
- `swarm.py` : contexte/historique/RAG puis boucle d'exécution unique. L'objectif original n'est plus remplacé par un plan présenté comme validé avant son exécution.
- `llm_gateway.py` : transport Ollama asynchrone, streaming contrôlé, options natives ou explicites, fragments regroupés, métriques effectivement retournées. Une fin de flux sans marque de fin n'est pas une réponse complète.
- `mission_agent.py` : objectif, plan, observations, critères, contrôles et revue de fin ; checkpoint avant les effets, arrêt des sous-processus, réutilisation de la connexion HTTP et contexte borné. Skills et rôles persistants sont chargés. Les workers utilisent une concurrence explicite (`AURORA_PARALLEL_WORKERS`) et ne dépassent pas les permissions du parent ; ils ne lancent pas récursivement d'autres workers.
- `mission_tools.py` : découverte/inspection de scripts sans exécution, outils de projet Python, arguments effectifs, lectures paginées, profil CSV, écritures atomiques conservant les octets, recherche et sources consultées avec empreinte, vérifications de fichiers/texte/JSON/commandes/sources et mesures du runtime. Une liste de liens de recherche n'est pas une source consultée.
- `mission_protocol.py` : schémas d'arguments communs au décodage et à l'exécuteur, outils proposés selon les permissions, critères exacts et vérifications ciblant les critères manquants. Ce contrat valide la forme, pas le raisonnement.
- `mission_store.py`, `application/mission_api.py` : journal SQLite commun au daemon et au bridge, événements dédupliqués, baux, clés d'idempotence, liste, état, SSE durable, arrêt, reprise et changement explicite de modèle pour le même objectif.
- `memory.py` : Chroma si disponible et copie SQLite persistante pour la recherche lexicale de repli. `AURORA_MEMORY_DIR` surcharge le chemin ; le `db_vector` existant est conservé, sinon les données utilisent le répertoire Aurora utilisateur. Un souvenir est une donnée, pas une instruction faisant autorité.
- `payload_manager.py`, `explorer.py` : aides au contexte et à l’exploration ; l’index fournit leurs points de définition.

### 9.3 Garanties et manques

Le journal est durable dans le répertoire de données Aurora, surcharge `AURORA_MISSION_DB`. Les événements SSE sont ordonnés et rejouables après le redémarrage du bridge. Les checkpoints enregistrent le but, le plan, les observations récentes, les critères, l'action en cours et la conversation bornée. Une reprise accorde un nouveau budget de tours et repart après le curseur du précédent événement terminal ; elle ne transforme pas une issue inconnue en succès. `watch`/`attach` suivent une mission sans la réexécuter.

Les missions terminées ont une rétention configurable (`AURORA_MISSION_RETENTION_SECONDS`, défaut 14 jours). Les snapshots de fichiers ont leur rétention propre. Le shell reste sans sandbox OS ; des outils externes et les anciens pipelines ont des contrats distincts. Les sessions de dialogue JSON ne sont pas une transaction SQLite commune avec chaque événement de mission. Les critères mécaniques ne prouvent pas à eux seuls la conformité sémantique : celle-ci demande une évaluation appropriée au domaine et des essais réels.

Paramètres explicites : `AURORA_MODEL_OPTIONS` (objet JSON d'options Ollama), `AURORA_DEFAULT_MODEL`, `AURORA_MISSION_MAX_STEPS` (128, 0 désactive cette borne), `AURORA_COMMAND_TIMEOUT`, `AURORA_STALL_ATTEMPTS`, `AURORA_PARALLEL_WORKERS`, `AURORA_CONCURRENT_MISSIONS`, `AURORA_TOOL_OUTPUT_CHARS`, `AURORA_CONTEXT_CHARS`. Ce sont des budgets et réglages, pas des mesures de qualité. `AURORA_BACKGROUND_ANALYSIS=1` active les diagnostics de fond facultatifs ; ils ne modifient pas automatiquement le code et n'effacent plus le journal de crash.

Sur la mémoire de conversation (`conversationMemory.ts`, couvert par les mesures 19/42/43) : le dédoublonnage compare le `contentHash` `kind::text` **byte-identique après `trim()`** — une variante de casse ou d’accent crée une entrée distincte, et c’est un choix documenté, pas un bug. `touch()` incrémente `usageCount` et pose `lastUsedAt` ; `removeMemory()` retire l’entrée et rééquilibre la fréquence documentaire ; le rappel pondère importance × BM25 avec rabais de fraîcheur (demi-vie 14 jours) et l’élagage respecte les entrées épinglées.

<a id="cli"></a>
## 10. CLI, connexion, événements et livraison

### 10.1 Entrées et configuration

La branche `main` du paquet `jobia-cli` expose `jobia`, `jbia` et l'alias historique `aurora`. Python ≥ 3.10 est déclaré ; Linux/Python 3.12 est vérifié dans cette maintenance. Les moteurs lourds ont leurs environnements et contraintes propres. Les répertoires sont résolus dans `core/locations.py` (XDG sous Linux, AppData sous Windows), avec surcharges `JOBIA_CONFIG_DIR` / `JOBIA_DATA_DIR` et migration de l'ancienne configuration Aurora sans écrasement.

Adresse : argument explicite, `JOBIA_SERVER_URL`, `AURORA_SERVER_URL`, configuration. Clé : `JOBIA_API_KEY`, `AURORA_API_KEY`, configuration. La clé doit déjà être autorisée par le bridge. La configuration est enregistrée par remplacement atomique avec un fichier temporaire unique privé. `is_configured()` respecte aussi la clé fournie dans l'environnement.

Le wrapper `aurora_cli.py` utilise le même paquet et définit seulement un défaut local en l'absence de surcharge d'adresse. Il ne préfixe plus le JSON d'un message de démarrage. Cela partage le code du client ; cela n'établit pas une parité de tous les pipelines avec React.

### 10.2 Missions et commandes locales

Deux commandes portaient auparavant le nom `run`, ce qui masquait la mission distante. Elles sont désormais distinctes :

- `jobia mission "demande" [--model ...] [--server-workspace ...] [--permissions ...]` : mission du daemon, progression SSE ou suivi JSON sur Quick Tunnel, livraison vérifiée dans le répertoire client, code de sortie non nul à l'échec, client fermé à la fin. Le niveau explicite vaut pour cette mission, sans changer le défaut sauvegardé.
- `jobia run --capability ... --fixture ... --goal ...` : boucle locale bornée d'amélioration mesurée. Elle ne devient pas une mission distante et ne démontre pas une autonomie générale.
- `jobia doctor` : diagnostic du terminal et des runtimes locaux ; `--remote` contrôle la readiness mission du bridge, et `--json` produit un résultat exploitable avec code 1 si indisponible. L'état de bout en bout SSE reste `unverified` tant qu'une vraie mission distante n'a pas été observée.
- `agents list/disable`, `mcp list` et `skills list` utilisent les méthodes réelles du bridge, ferment leurs clients et produisent une erreur si le serveur ne confirme pas l’opération. Des appels à des méthodes inexistantes empêchaient ces commandes de fonctionner. `connect`, `status` et les commandes locales image/3D/audio conservent leurs responsabilités. Un catalogue ou une installation ne prouve pas la capacité à exécuter le modèle sur la machine.

### 10.3 Transport, fichiers et permissions

`bridge.py` fournit HTTP JSON et SSE avec reprise par `Last-Event-ID`, contrôle de séquence et reprises bornées des GET. Une nouvelle mission porte une clé d'idempotence. L'interface conserve une demande dont l'acceptation est inconnue : `/retry` emploie la même clé et le même contenu. `/attach ID` suit une mission existante ; `/resume ID` reprend une mission interrompue/arrêtée/échouée/bloquée à son checkpoint. Le bridge conserve le journal sur disque, au-delà de son redémarrage. Une reprise peut utiliser un autre modèle explicitement choisi sans changer le but initial.

Les artefacts sont instantanés côté serveur dans `application/cli_artifacts.py`. Le client `transfers.py` contrôle noms, confinement, taille et SHA-256, puis termine atomiquement le fichier reçu. Les tests exécutés utilisent des données temporaires et un serveur simulé, avec réception d'un fichier réel vérifié sur disque ; le tunnel public n'est pas testé.

SAFE interdit les outils directs d'écriture, commandes et création. Les lectures/écritures directes sont confinées au workspace sauf FULL ; un sous-agent enregistré ne peut pas dépasser le niveau de son parent. **Les commandes AUTONOMOUS/STANDARD utilisent encore le shell de l'hôte, sans sandbox OS : les contrôles des chemins ne constituent pas une isolation du shell.** A03 reste partiellement ouvert. L'ancien `run_sudo_command` ne prétend plus disposer de privilèges root : une procédure administrateur distincte reste nécessaire.

### 10.4 Interface et validation

`jobia` ou `jobia ui` ouvre un espace plein écran basé sur prompt_toolkit : conversation conservée, objectif, plan, critères, preuves, fichiers reçus, journal et mesures du moteur. La colonne latérale s'efface sur les terminaux étroits. L'animation décrit une opération réellement active, sans pourcentage inventé. `jobia ui --text` conserve le parcours linéaire ; un pipe affiche une sortie statique et ne bloque pas en attendant des touches.

Raccourcis : F2 thème, F3 modèle servi observé, F4 conversation/journal/fichiers, F5 diagnostic, Tab navigation, Ctrl+C arrêt, Ctrl+Q sortie, Ctrl+N nouveau dialogue, Alt+Entrée nouvelle ligne. Commandes de l'espace : `/missions`, `/attach ID`, `/resume ID`, `/retry`, `/models`, `/theme`, `/mode`, `/permissions`, `/new`, `/quit`. Une demande locale s'exécute dans un processus séparé ; sa sortie et son reçu restent privés dans `ui-runs`, pour permettre l'arrêt et conserver les diagnostics. Une mission distante garde son identifiant dans la conversation pour un rattachement ultérieur.

Thèmes : `jobia`, `otter`, `abyss`, `plain`. Options globales : `--theme`, `--color auto|always|never`, `--animation auto|full|reduced|none`. Les couleurs et animations suivent les capacités du terminal et `NO_COLOR`. L'installation corrigée lit aussi les métadonnées Windows `Lib/site-packages` et utilise une mise à jour pip ordinaire, sans forcer le remplacement de toutes les dépendances.

```bash
# Dans aurora-remote-cli, sur Linux/macOS :
git fetch origin
git switch main
git pull --ff-only
./install.sh
jobia

# Hors interface, pour les missions :
jobia missions list --json
jobia missions watch IDENTIFIANT
jobia missions resume IDENTIFIANT --model MODELE_DISPONIBLE
jobia doctor --remote --json
```

Sous Windows, utiliser `./install.ps1` à la place de `./install.sh`, puis un nouveau terminal si le PATH vient d'être configuré. Une installation réelle locale, les tests du clavier et une matrice CI portable vérifient ce client ; ils ne valident pas les moteurs GPU sur chaque OS. La réparation NVIDIA du PC reste un préalable aux essais lourds. Le bundle React/natif n'est pas remplacé par cette interface terminal et sa parité complète reste à établir.

<a id="tunnel"></a>
## 11. Tunnel, découverte et publication d’état

Le lanceur courant démarre `cloudflared tunnel --url http://127.0.0.1:3001`, récupère l’URL temporaire, appelle `scripts/verify-tunnel-url.sh`, puis écrit les fichiers locaux de tunnel. `scripts/publish-live-link.sh` copie l’adresse dans `aurora-live/tunnel.txt`, réécrit seulement le bloc d’état du README et peut committer/pousser ces fichiers. `scripts/aurora-status-watcher.sh` surveille et peut invoquer cette publication.

**Attention opérationnelle :** ces scripts ne sont pas de simples vérificateurs en lecture seule. Ne pas les lancer pendant un audit documentaire en pensant qu’ils n’ont aucun effet externe. Aucun lancement/publication de cette nature n’est nécessaire pour lire ce maître.

Le dépôt `aurora-live` est un panneau de découverte. Il ne doit pas contenir clés, poids, sessions ou données d’entraînement. Un lien temporaire peut devenir périmé, et la disponibilité de GitHub est une dépendance supplémentaire du parcours de découverte.

### Amélioration proposée du parcours distant

1. Choisir un endpoint stable et un transport adapté au streaming. Un tunnel nommé est une piste ; sa configuration, son domaine, les droits et les tests restent à réaliser.
2. Tester le trajet externe avec une petite tâche non destructive : auth refusée/acceptée, flux en temps réel, coupure, reprise, arrêt et téléchargement vérifié.
3. Séparer état public et readiness privée. Une page d’accueil en HTTP 200 ne prouve pas l’état d’Ollama, de la file GPU, du daemon ou des outils.
4. Conserver un identifiant de serveur/build ; détecter qu’un client parle au bon backend après rotation de tunnel.
5. Harmoniser URL des API, assets, websocket éventuel et SSE. Un chemin `file://`, un localhost distant ou un blob navigateur ne constitue pas une livraison réseau.

<a id="agents"></a>
## 12. Agents, commandes, profils UI et skills

Le registre d’exécution du serveur est désormais défini dans `application/agent_registry.py`, indépendamment des fichiers d’éditeur. Ses 13 rôles intégrés ne sont pas une preuve de 13 processus actifs. Les exports de développement ci-dessous sont conservés pour leurs chargeurs hôtes et ne commandent pas le registre runtime.

Il existe plusieurs systèmes distincts :

| Système | Source / chargement | État documentaire |
|---|---|---|
| Agents de développement | `.claude/agents/*.md`, frontmatter YAML, hooks et tracker | 41 fichiers présents, compteur historique 37, tracker à réconcilier |
| Commandes de développement | `.claude/commands/*.md` | Instructions chargées par l’outil hôte ; fichiers nécessaires à la découverte |
| Profils d’agents de l’interface | `src/services/auroraAgents.ts`, Team Manager et stores | Personnalités/paramètres d’UI, pas les fichiers `.claude` |
| Agents dynamiques CLI | JSON sous répertoire de données Aurora | Création persistante par outil de mission ; réutilisation par `spawn_agent` avec permissions bornées par le parent |
| Skills Aurora | `.aurora/skills/<nom>/SKILL.md` dans workspace, parent, utilisateur, puis `/etc/aurora/skills` | Contexte partagé bridge/daemon, instructions bornées à 24 000 caractères ; création de skills de projet sans écrasement |
| MCP | Configurations, découverte et exécution d’outils | Un outil découvert doit être autorisé et appelé pour compter comme utilisé |

La hiérarchie historique comprend orchestrateur, leads de modules, spécialistes et rôles transversaux. Les 39 définitions exactes, les commandes et les règles locales sont incorporées dans l’annexe exportable, pas réécrites approximativement. Les exigences de modèle inscrites dans leurs frontmatters sont des réglages existants de ces agents, pas une recommandation de modèle pour l’application utilisateur.

Les hooks configurés dans `.claude/settings.json` couvrent routage de prompt, dispatch, fin de tâche, dernier commit, démarrage de session et précompaction. Leur simple déclaration ne prouve pas que la version de l’outil les invoque effectivement ; certains matchers emploient des noms historiques. Le linter doit être réparé avec son tracker, sans inventer l’historique des missions.

### Source unique sans casser les chargeurs

Les chargeurs actuels lisent des noms de fichiers précis. Supprimer physiquement toutes les définitions `.md` les désactiverait. Le compromis fonctionnel retenu est **une source éditable dans ce maître**, plus des fichiers de compatibilité matérialisés aux chemins attendus. Ils se régénèrent avec `doc_master.py --write` et se contrôlent sans option.

Les instructions sont des blocs de données Markdown délimités ; elles ne deviennent pas toutes des consignes globales pour l’IA qui lit l’architecture. Seul le rôle choisi doit guider son travail, avec les instructions de l’utilisateur et de l’outil hôte.

Aucun `SKILL.md` propre aux trois dépôts n’a été trouvé dans l’inventaire initial. Les skills externes et ceux installés dans les outils globaux ne sont pas supprimés. Pour ajouter un skill Aurora au maître, déclarer son chemin d’export, conserver ses ressources nécessaires et tester sa découverte réelle. Une future création par l’API peut encore écrire un `SKILL.md` ; il faudra ensuite l’intégrer à la source documentaire si c’est une instruction pérenne.

<a id="entrainement"></a>
## 13. Entraînement, évaluation et intégration d’adaptateurs

`auto_rl/` vise une optimisation locale auditable de modèles de base conservés. Le cycle général est : profil/curriculum → essais → préférences/récompenses → travail distant borné si nécessaire → récupération → audit local → promotion explicite d’un adaptateur compatible.

| Groupe | Fichiers | Responsabilité |
|---|---|---|
| Pilotage | `campaign.py`, `cli.py`, `control.py`, `config.py`, `cycle_app.py` | Campagnes, état durable, arrêt, profils et UI de contrôle |
| Jeux de tâches | `curriculum.py`, `challenge_curriculum.py`, `learning_curriculum.py`, `temporal_tasks.py` | Familles d’entraînement et d’audit séparées, cas reproductibles |
| Optimisation | `preference_cycle.py`, `preference_train.py`, `lora.py`, `adapters.py`, `strategy.py` | Préférences, corrections de poids, stratégie et budgets |
| Calcul distant | `cloud.py`, `cloud_worker.py`, `autonomous_train.py`, `kaggle_bridge.py` | Exécution Kaggle et collecte, sans confondre sortie distante et promotion locale |
| Moteurs et mesures | `backends.py`, `comfy_backend.py`, `temporal_backend.py`, `evaluation.py`, `judges.py`, `temporal_judges.py` | Inférence réelle ou contrats explicitement simulés, évaluations par domaine |
| Traçabilité | `storage.py`, `versions.py`, `lineage.py`, `failure_memory.py`, `rollout_cache.py` | Provenance, parent, audit, échecs et réutilisation sous contrat identique |
| Production | `runtime.py`, `serve.py`, `integration.py`, `image_runtime.py`, `hymotion_infer.py`, `media.py` | Sélection et chargement d’un adaptateur audité correspondant au modèle de base |

Les tâches Code/Cyber/Cowork peuvent partager des oracles synthétiques, sans que cela certifie la maîtrise générale d’un environnement. Les mesures Conversation, Voix, Image, 3D, Vidéo, Animation et Apprentissage ont des critères distincts. Les métriques temporelles et visuelles sont parfois des proxys : ne pas les présenter comme preuve complète de sens ou d’intention.

Le service 11435 expose une surface d’inférence compatible avec certains usages Ollama pour les modèles audités. Son `/health` avait `validated_models=0` lors du contrôle précédent : « service prêt » et « adaptateur validé disponible » sont deux états différents.

La reprise d’un cycle peut réutiliser des préférences et lots conservés ; elle n’est pas nécessairement une restauration exacte de l’état de l’optimiseur. Une campagne qui arrête un module et passe au suivant doit conserver le motif et le verdict, sans transformer l’absence de résultat en promotion.

<a id="ressources"></a>
## 14. Stockage, RAM, VRAM et performance

### 14.1 Ne pas confondre les mesures

Les poids sur disque, la mémoire vive du processus, le cache du système, la VRAM, le contexte d’inférence et le swap sont des mesures différentes. Un fichier de 52 Go ne prouve pas une utilisation de 52 Go de RAM. Une estimation doit considérer le chargement effectif, la quantification, l’offload, les activations, les buffers et le cache du contexte ; le verdict pratique doit être mesuré.

Ollama documente que concurrence et longueur du contexte affectent la mémoire, et fournit des réglages de nombre de modèles chargés, parallélisme et durée de résidence. Appliquer ces réglages au processus réellement en service, pas seulement à un shell de lancement. [Ollama — FAQ](https://docs.ollama.com/faq) (consulté le 24/09/2026).

### 14.2 Profils et choix de modèles présents

| Rôle | Source effective à consulter | Valeur constatée dans le code |
|---|---|---|
| Conversation frontend | `src/config/models.ts` | `orcarouter/Qwen3.8-27B-Uncensored` avec logique adaptative |
| Code frontend local | Même fichier + sélection de pipeline | `qwen3-coder:30b` comme primaire local |
| CLI par défaut | `bridge_server.py::_ext_default_model()` | Préférence à `qwen3-coder-next:q4_K_M` parmi les modèles présents |
| Gateway AGI | `agi_core/llm_gateway.py` | Défaut `qwen3-coder-next:q4_K_M`, override possible par appel |
| Vision live | `src/config/models.ts` | `qwen3-vl:8b` ; un profil haute qualité différent existe |
| Image | `src/config/models.ts`, workflow ComfyUI exécuté | FLUX.2 GGUF, encodeur Mistral, VAE ; présence réelle à contrôler |
| STT/TTS | Config et `voice_service.py` | faster-whisper large-v3-turbo / Kokoro, parcours de secours |

Les modèles supplémentaires catalogués par Ollama sont des installations disponibles, pas une liste de modèles actuellement résidents. `/api/tags` et `/api/ps` ne mesurent pas la même chose. Les constantes de modèle doivent être rapprochées des poids résolus et des paramètres d’une vraie requête.

### 14.3 Poste examiné

Ubuntu 24.04, environ 32 Go physiques de RAM (30 Gio affichés), RTX 5070 Ti avec environ 16 Gio de VRAM, swap actif de 64 Gio. Le nettoyage précédent a rendu environ 64 Gio disponibles sur le SSD ; cette valeur est datée et varie. Les modèles, environnements, bases et code ont été conservés.

ComfyUI était lancé par systemd avec `--novram --disable-cuda-malloc --disable-async-offload --reserve-vram 1.5`. Le lanceur applicatif utilise aussi `comfy_runtime.py` pour décider de paramètres. Aucune assertion de performance ne doit ignorer cette différence entre configuration disponible et ligne de commande active.

### 14.4 Mesure à effectuer avant optimisation

Pour chaque cas : fixer modèle, hash/version des poids, prompt, seed quand applicable, contexte, résolution et workflow. Mesurer séparément attente, chargement, premier token/aperçu, inférence, post-traitement et transfert. Collecter pics RAM/VRAM, swap réellement utilisé, erreurs, annulations et qualité. Comparer froid/chaud et plusieurs répétitions ; publier médiane et p95 si l’échantillon le permet.

Réduire steps, contexte ou précision sans mesure peut réduire la qualité. Garder un gros modèle résident peut accélérer le dialogue mais pénaliser FLUX/3D. Une politique commune de réservation et de priorité utilisateur est préférable à des évictions croisées dispersées.

<a id="exploitation"></a>
## 15. Exploitation et diagnostic

### 15.1 Vérifications en lecture seule

```bash
systemctl --user status aurora-bridge aurora-comfyui aurora-trained-models --no-pager
systemctl status ollama --no-pager
ss -lnt
free -h
swapon --show
df -h /
nvidia-smi
curl --fail --silent http://127.0.0.1:11434/api/tags
curl --fail --silent http://127.0.0.1:11434/api/ps
curl --fail --silent http://127.0.0.1:8188/system_stats
curl --fail --silent http://127.0.0.1:11435/health
python3 aurora_cli.py doctor
```

Ne pas afficher une configuration de secrets pour diagnostiquer une simple connexion. Les résultats des commandes doivent être interprétés : inventaire de modèles ≠ résidence, service actif ≠ mission possible, HTTP 200 ≠ réponse sémantiquement correcte.

### 15.2 Démarrage et construction

- `start-aurora.sh` coordonne première initialisation Linux, Ollama, ComfyUI, bridge, daemon, UI et éventuellement tunnel/publication. Il peut installer, construire, démarrer et publier : ce n’est pas un simple test.
- `scripts/linux/` contient bootstrap, première exécution, installation 3D et vérification de pile. Les dépendances CUDA, Conda, Blender et extensions natives doivent correspondre au matériel et aux versions résolues.
- Développement web : depuis `application`, `npm run dev:web`. Vérification frontend : `npm run check`. Binaire natif : commande Tauri du manifeste et toolchain Rust prévue.
- `bridge_doctor.py --check-only` est destiné au diagnostic ; les autres modes peuvent relancer ou mettre à jour. Examiner les effets du mode demandé avant de le lancer.
- `restart_tunnel.py`, `scripts/verify-tunnel-url.sh`, le lanceur et le watcher ne sont pas interchangeables. Suivre le trajet réellement utilisé.

### 15.3 Diagnostic par symptôme

| Symptôme | Vérifier d’abord | Ne pas conclure trop tôt |
|---|---|---|
| Interface ancienne | Identifiant du bundle, Vite vs dist vs Tauri | « Le correctif source est faux » avant vérifier le build servi |
| CLI connecté mais mission bloquée | Bus 3002, daemon, publication IPC, événements et modèle réel | « Ollama fonctionne donc toute la mission fonctionne » |
| Distant inaccessible | Adresse publiée, DNS, tunnel vivant, endpoint de destination, auth | « Le fichier tunnel existe donc il est valide » |
| Tokens reçus seulement à la fin | Transport SSE réel, type de tunnel, buffering | « Il suffit d’augmenter le timeout du modèle » |
| Génération lente | Temps de chargement, file GPU, résidence, contexte, offload, swap | « La taille du fichier modèle est la RAM utilisée » |
| Fichier absent sur le client | Manifeste, chemin autorisé, téléchargement, checksum, destination | « Créé sur le serveur signifie livré » |
| Résultat médiocre mais valide | Corpus sémantique et critères de demande | « JSON/GLB/PNG valide signifie travail réussi » |

<a id="contrats"></a>
## 16. Contrats à harmoniser entre les trois parcours

Ce sont des **cibles de conception**, à introduire progressivement sans annoncer qu’elles existent déjà partout.

| Contrat | Champs / propriétés nécessaires | Validation |
|---|---|---|
| Requête de job | ID/idempotence, type, paramètres, modèle résolu, profil, workspace, permissions | Même requête reçue deux fois : une seule opération |
| État | accepted, queued, running, cancel_requested, cancelled, failed, completed | Transition terminale unique, persistance et version |
| Événement | job_id, séquence, type, date, payload, version | Ordre, déduplication, reprise, borne de rétention |
| Erreur | code stable, étape, message, retryable, diagnostics expurgés | Erreur exploitable et code de sortie cohérent CLI |
| Artefact | identifiant, type, nom sûr, octets, SHA-256, provenance, URL autorisée | Écriture temporaire puis validation atomique ; aucun fichier tronqué annoncé complet |
| Validation | technique, conformité, qualité, preuves, non-vérifié | Statuts séparés ; simulation explicitement marquée |
| Capacités | moteur/version, outil réel, readiness, mémoire, permissions | UI et CLI présentent des possibilités constatées |
| Configuration | valeur demandée, valeur résolue, origine et override | Même profil observable depuis chaque surface |

« STANDARD » dans la table de permissions est une capacité d’exécution, pas le nom d’un protocole et pas la preuve qu’un outil est isolé. De même, OpenAPI, SSE, MCP et les manifests de fichiers sont des contrats différents ; adopter un nom de standard ne remplace pas la vérification de sa mise en œuvre.

<a id="validation"></a>
## 17. Validation, tests et qualité

### 17.1 Pyramide utile

1. Contrôles de schéma et unités : parsing, flux interrompu, curseur, autorisation, chemins, erreurs, budgets.
2. Intégration locale avec moteurs substitués : orchestration, annulation, livraison, replay et états terminaux.
3. Petite génération réelle locale : modèle réellement utilisé, fichier produit et qualité évaluée.
4. Même cas depuis application standard, navigateur distant et CLI ; corpus, paramètres et critères communs.
5. Pannes injectées : processus arrêté, réseau coupé, disque presque plein dans un environnement de test, mémoire limitée, fichier incomplet. Ne pas déstabiliser le PC utilisateur pour un test.

Les tests existent dans `application/src/__tests__/`, `application/test_cli_mission_events.py`, `tests_agi/`, `tests_auto_rl/`, `../aurora-remote-cli/tests/`, `.claude/hooks/` et plusieurs scripts d’audit. L’index donne leurs fichiers. Un ancien rapport « tests passés » ne remplace pas une exécution après modification.

### 17.2 Qualité par domaine

| Domaine | Critères d’acceptation concrets |
|---|---|
| Conversation | Réponse à la question, contexte respecté, sources réelles, faits distingués des hypothèses |
| Code | Installation reproductible, tests pertinents, comportement demandé, absence de faux succès et de perte de fichiers |
| Image | Sujet, nombre, relations spatiales, couleurs, identité, texte, édition et référence |
| Dessin | Graphe valide, relations orientées correctes, exactitude factuelle, lisibilité |
| 3D | Fichier, échelle, axes, géométrie, silhouette, UV/matériaux, rig et animation |
| Voix | Transcription, prononciation, intelligibilité, latence et continuité |
| Academy | Exactitude vérifiable, adaptation au niveau, absence de correction inventée |
| CLI/tunnel | Même tâche exécutée, progression reçue, reprise sans doublon, artefacts vérifiés |

### 17.3 Audits historiques conservés

Les cycles `audit/cycle-01`, `cycle-01-resilience`, `cycle-02-media` contiennent des preuves JSON/CSV, captures et journaux qui restent en place. Leurs quatre rapports Markdown sont archivés et synthétisés ici. Leurs scores étaient provisoires et leurs tests parfois simulés : ne pas en déduire une note actuelle de l’IA.

Les anciens rapports ont signalé notamment reprise durable, parité des médias, contraintes d’authentification et transferts. Certains correctifs sont maintenant visibles dans le code local ; le suivi actuel se fait par A01–A17 et par des tests datés, pas en répétant des numéros de ligne périmés.

<a id="documentation"></a>
## 18. Conservation documentaire et maintenance

### 18.1 Organisation retenue

Les deux documents à éditer sont **ARCHITECTURE_MAITRE.md** et **AGENTS.md** à la racine d’AuroraIA. Le premier contient architecture, analyses, propositions, index et définitions complètes. Le second impose sa lecture et les règles de rigueur.

Les fichiers Markdown exigés par le chargement des agents, les commandes, les règles locales, les métadonnées du paquet CLI et le panneau d’état distant sont des **exports de compatibilité**. Ils restent présents pour fonctionner, mais leur source est un bloc `AURORA_EXPORT` de l’annexe. Ce choix intègre aussi les instructions d’agents demandées par l’utilisateur sans les désactiver.

Exception supplémentaire : `CHANGELOG.md` reste un artefact généré depuis Git par `.claude/hooks/gen_changelog.py`, que le self-test existant compare à l’historique. Il n’est pas à maintenir manuellement ni à lire pour comprendre l’architecture ; sa suppression casserait ce contrôle sans améliorer la source documentaire.

Les documents techniques dispersés sont retirés après vérification de leur sauvegarde. Les dépendances tierces, modèles, sorties utilisateur, worktrees, copies de livraison et outils globaux ne sont pas une documentation projet concurrente et ne sont pas nettoyés par cette opération.

### 18.2 Archive et traçabilité

Archive locale de restauration : `/home/juan/consolidation-docs-2026-09-24/markdown-originaux.tar.gz`. Elle contient les 153 Markdown inventoriés, avec leur chemin relatif sous le nom du dépôt. Chaque fichier a été vérifié contre son SHA-256 avant et après archivage. Le dossier contient aussi `inventaire-docs.json`, le relevé initial du code, les états Git et les diffs préexistants. Cette archive privée n’est pas publiée.

Les anciennes propositions détaillées, notes de design, journaux d’évolution, instructions d’installation spécifiques et audits restent consultables dans cette archive. Leur texte historique n’est pas présenté comme une spécification actuelle. Le catalogue de migration se trouve à la fin de l’index.

Restauration prudente : extraire l’archive dans un répertoire vide pour consulter/comparer ; ne pas écraser les nouveaux fichiers du projet sans choisir explicitement ceux à restaurer.

### 18.3 Mise à jour

```bash
# Comparer les exports au maître ; lecture seule, code de sortie non nul si écart.
python3 scripts/documentation/doc_master.py
# Matérialiser uniquement les exports déclarés après édition du maître.
python3 scripts/documentation/doc_master.py --write
# Vérifier les empreintes des sources auditées.
python3 scripts/documentation/doc_master.py --check-code
```

Le contrôle des sources détecte les modifications des fichiers indexés ; il ne revendique pas la découverte automatique de toute nouvelle source non indexée. Après évolution, revoir les sections concernées, ajouter les nouveaux fichiers au manifeste et régénérer leurs entrées d’index. Ne pas actualiser les empreintes simplement pour faire disparaître une alerte.

Le bloc `STATUS` du README `aurora-live` appartient à l’automatisation d’état : le générateur le conserve. Ne pas y recopier une URL périmée depuis l’archive. Les exports de définition conservent leur frontmatter ; les 76 instructions existantes ne sont pas remplacées par des résumés qui en changeraient le comportement.

### 18.4 Règle pour une future IA

Pour une demande d’analyse : lire la synthèse, la parité, les priorités et les domaines concernés ; proposer des actions fondées sur les preuves. Pour un correctif : ouvrir seulement les sources ciblées et leurs tests, comparer avec le maître, implémenter et mettre à jour les contrats concernés. Si le code contredit le document, signaler l’écart et corriger la documentation. Ne jamais prétendre avoir exécuté un test ou lu tout le code à partir de ce seul fichier.

<a id="index"></a>
## 19. Index mécanique du code et des routes

<!-- AURORA_INDEX_BEGIN -->
### 19.1 Repères de navigation

Les chemins ci-dessous désignent des fichiers existants au relevé. Les lignes sont indicatives et doivent être revérifiées après modification. `L` indique le nombre de lignes du fichier, pas une mesure de qualité.

### 19.2 Déclarations HTTP du bridge principal

| Méthodes et chemin | Source et handler |
|---|---|
| `POST /api/code/install-model` | `application/bridge_server.py` → `code_install_model` (ligne 318) |
| `GET /api/code/detect-editor` | `application/bridge_server.py` → `code_detect_editor` (ligne 356) |
| `POST /api/code/open-folder` | `application/bridge_server.py` → `code_open_folder` (ligne 366) |
| `GET /api/ext/key/status` | `application/bridge_server.py` → `ext_key_status` (ligne 596) |
| `POST /api/ext/key/generate` | `application/bridge_server.py` → `ext_key_generate` (ligne 610) |
| `POST /api/ext/key/revoke` | `application/bridge_server.py` → `ext_key_revoke` (ligne 637) |
| `GET,OPTIONS /api/ext/ping` | `application/bridge_server.py` → `ext_ping` (ligne 655) |
| `POST,OPTIONS /api/ext/chat` | `application/bridge_server.py` → `ext_chat` (ligne 667) |
| `POST,OPTIONS /api/ext/3d/generate` | `application/bridge_server.py` → `ext_3d_generate` (ligne 839) |
| `GET,OPTIONS /api/ext/3d/status/<job_id>` | `application/bridge_server.py` → `ext_3d_status` (ligne 869) |
| `POST,OPTIONS /api/ext/do` | `application/bridge_server.py` → `ext_do` (ligne 927) |
| `GET /api/3d/list` | `application/bridge_server.py` → `three_d_list` (ligne 1026) |
| `GET /api/3d/file/<path:fname>` | `application/bridge_server.py` → `three_d_file` (ligne 1066) |
| `GET,OPTIONS /aurora-api.md` | `application/bridge_server.py` → `aurora_api_doc` (ligne 1089) |
| `POST /api/3d/select-subject` | `application/routes/asset_bp_routes.py` → `three_d_select_subject` (ligne 31) |
| `GET /aurora_viewer.html` | `application/routes/asset_bp_routes.py` → `aurora_viewer_page` (ligne 73) |
| `GET /api/asset/<path:filepath>` | `application/routes/asset_bp_routes.py` → `serve_asset` (ligne 82) |
| `GET /api/download/<path:filepath>` | `application/routes/asset_bp_routes.py` → `download_asset` (ligne 106) |
| `GET /api/generated-files` | `application/routes/asset_bp_routes.py` → `list_generated_files` (ligne 121) |
| `POST /api/image/persist` | `application/routes/asset_bp_routes.py` → `persist_generated_image` (ligne 150) |
| `POST /api/cinema/storyboard` | `application/routes/cinema_bp_routes.py` → `cinema_storyboard` (ligne 277) |
| `GET /api/academy/parcours/latest` | `application/routes/cinema_bp_routes.py` → `academy_parcours_latest` (ligne 366) |
| `POST /api/cinema/sample-render` | `application/routes/cinema_bp_routes.py` → `cinema_sample_render` (ligne 381) |
| `POST /api/cinema/regenerate-shot` | `application/routes/cinema_bp_routes.py` → `cinema_regenerate_shot` (ligne 434) |
| `POST /api/cinema/selftest` | `application/routes/cinema_bp_routes.py` → `cinema_selftest` (ligne 527) |
| `POST /api/cinema/benchmark` | `application/routes/cinema_bp_routes.py` → `cinema_video_benchmark` (ligne 610) |
| `POST /api/cinema/preview-keyframes` | `application/routes/cinema_bp_routes.py` → `cinema_preview_keyframes` (ligne 669) |
| `POST /api/cinema/generate` | `application/routes/cinema_bp_routes.py` → `cinema_generate` (ligne 722) |
| `POST /api/video/render` | `application/routes/cinema_bp_routes.py` → `video_render` (ligne 788) |
| `GET /api/cinema/films` | `application/routes/cinema_bp_routes.py` → `cinema_films` (ligne 1004) |
| `GET /api/cinema/films/<film_id>/video` | `application/routes/cinema_bp_routes.py` → `cinema_film_video` (ligne 1050) |
| `GET /api/cinema/films/<film_id>/rapport` | `application/routes/cinema_bp_routes.py` → `cinema_film_rapport` (ligne 1064) |
| `GET /api/cinema/job/<job_id>` | `application/routes/cinema_bp_routes.py` → `cinema_job_status` (ligne 1079) |
| `POST /api/cinema/cancel/<job_id>` | `application/routes/cinema_bp_routes.py` → `cinema_job_cancel` (ligne 1129) |
| `GET /api/video/queue` | `application/routes/cinema_bp_routes.py` → `video_gpu_queue_status` (ligne 1135) |
| `GET /api/storage/status` | `application/routes/cinema_bp_routes.py` → `storage_status` (ligne 1184) |
| `POST /api/storage/tier` | `application/routes/cinema_bp_routes.py` → `storage_tier` (ligne 1215) |
| `POST /api/storage/stage` | `application/routes/cinema_bp_routes.py` → `storage_stage` (ligne 1225) |
| `POST /api/storage/unstage` | `application/routes/cinema_bp_routes.py` → `storage_unstage` (ligne 1233) |
| `POST /api/storage/gc` | `application/routes/cinema_bp_routes.py` → `storage_gc` (ligne 1241) |
| `POST /api/storage/purge` | `application/routes/cinema_bp_routes.py` → `storage_purge` (ligne 1252) |
| `GET /api/video/gallery` | `application/routes/cinema_bp_routes.py` → `video_gallery` (ligne 1264) |
| `GET /api/voice/library` | `application/routes/cinema_bp_routes.py` → `voice_library_list` (ligne 1327) |
| `DELETE /api/voice/library/<slug>` | `application/routes/cinema_bp_routes.py` → `voice_library_delete` (ligne 1334) |
| `POST /api/voice/library/clear` | `application/routes/cinema_bp_routes.py` → `voice_library_clear` (ligne 1351) |
| `POST /api/voice/register` | `application/routes/cinema_bp_routes.py` → `voice_register` (ligne 1368) |
| `POST /api/voice/extract` | `application/routes/cinema_bp_routes.py` → `voice_extract_async` (ligne 1441) |
| `POST /api/voice/synthesize` | `application/routes/cinema_bp_routes.py` → `voice_synthesize` (ligne 1503) |
| `GET /api/voice/check` | `application/routes/cinema_bp_routes.py` → `voice_clone_check` (ligne 1558) |
| `POST /api/voice/studio/sample` | `application/routes/cinema_bp_routes.py` → `voice_studio_upload_sample` (ligne 1594) |
| `GET /api/voice/studio/sample/<sample_id>/audio` | `application/routes/cinema_bp_routes.py` → `voice_studio_stream_sample` (ligne 1693) |
| `POST /api/voice/studio/replicate` | `application/routes/cinema_bp_routes.py` → `voice_studio_replicate` (ligne 1712) |
| `POST /api/voice/studio/sing` | `application/routes/cinema_bp_routes.py` → `voice_studio_sing` (ligne 1779) |
| `GET /api/voice/studio/music/search` | `application/routes/cinema_bp_routes.py` → `voice_studio_music_search` (ligne 1851) |
| `GET /api/voice/studio/music/track/<track_name>/audio` | `application/routes/cinema_bp_routes.py` → `voice_studio_stream_music` (ligne 1865) |
| `POST /api/voice/studio/emotion/detect` | `application/routes/cinema_bp_routes.py` → `voice_studio_detect_emotion` (ligne 1880) |
| `POST /api/voice/studio/calibrate` | `application/routes/cinema_bp_routes.py` → `voice_studio_calibrate` (ligne 1894) |
| `GET /api/voice/studio/generation/<gen_name>/audio` | `application/routes/cinema_bp_routes.py` → `voice_studio_stream_generation` (ligne 1911) |
| `GET /api/voice/studio/tree` | `application/routes/cinema_bp_routes.py` → `voice_studio_tree` (ligne 1932) |
| `GET /api/voice/studio/profiles` | `application/routes/cinema_bp_routes.py` → `voice_studio_profiles` (ligne 1944) |
| `DELETE /api/voice/studio/profile/<slug>` | `application/routes/cinema_bp_routes.py` → `voice_studio_delete_profile` (ligne 1959) |
| `POST /api/voice/studio/clean-legacy` | `application/routes/cinema_bp_routes.py` → `voice_studio_clean_legacy` (ligne 1975) |
| `GET /api/music/status` | `application/routes/cinema_bp_routes.py` → `music_status` (ligne 2212) |
| `GET /api/music/voices` | `application/routes/cinema_bp_routes.py` → `music_voice_list` (ligne 2217) |
| `POST /api/music/voices` | `application/routes/cinema_bp_routes.py` → `music_voice_import` (ligne 2235) |
| `POST /api/music/jobs` | `application/routes/cinema_bp_routes.py` → `music_create` (ligne 2299) |
| `GET /api/music/jobs/<job_id>` | `application/routes/cinema_bp_routes.py` → `music_job` (ligne 2383) |
| `GET /api/music/exports` | `application/routes/cinema_bp_routes.py` → `music_exports` (ligne 2391) |
| `GET /api/music/exports/<path:filename>` | `application/routes/cinema_bp_routes.py` → `music_export_file` (ligne 2413) |
| `POST /api/cli/register` | `application/routes/cli_bp_routes.py` → `cli_register` (ligne 125) |
| `POST /api/cli/auth` | `application/routes/cli_bp_routes.py` → `cli_auth` (ligne 166) |
| `GET /api/cli/version` | `application/routes/cli_bp_routes.py` → `cli_version` (ligne 177) |
| `GET /api/cli/status` | `application/routes/cli_bp_routes.py` → `cli_status` (ligne 185) |
| `GET /api/cli/doctor` | `application/routes/cli_bp_routes.py` → `cli_doctor` (ligne 232) |
| `POST /api/cli/session/create` | `application/routes/cli_bp_routes.py` → `cli_session_create` (ligne 284) |
| `GET /api/cli/session/list` | `application/routes/cli_bp_routes.py` → `cli_session_list` (ligne 307) |
| `GET /api/cli/session/<session_id>` | `application/routes/cli_bp_routes.py` → `cli_session_get` (ligne 324) |
| `POST /api/cli/session/<session_id>/resume` | `application/routes/cli_bp_routes.py` → `cli_session_resume` (ligne 334) |
| `DELETE /api/cli/session/<session_id>` | `application/routes/cli_bp_routes.py` → `cli_session_delete` (ligne 346) |
| `POST /api/cli/chat` | `application/routes/cli_bp_routes.py` → `cli_chat` (ligne 358) |
| `GET /api/cli/permissions` | `application/routes/cli_bp_routes.py` → `cli_permissions_get` (ligne 428) |
| `POST /api/cli/permissions` | `application/routes/cli_bp_routes.py` → `cli_permissions_set` (ligne 435) |
| `GET /api/cli/workspace` | `application/routes/cli_bp_routes.py` → `cli_workspace_get` (ligne 455) |
| `POST /api/cli/workspace` | `application/routes/cli_bp_routes.py` → `cli_workspace_set` (ligne 461) |
| `GET /api/cli/tools` | `application/routes/cli_bp_routes.py` → `cli_tools` (ligne 473) |
| `GET /api/cli/models` | `application/routes/cli_bp_routes.py` → `cli_models` (ligne 505) |
| `GET /api/cli/agents/official` | `application/routes/cli_bp_routes.py` → `cli_agents_official` (ligne 548) |
| `POST /api/cli/agents/official/<name>/disable` | `application/routes/cli_bp_routes.py` → `cli_agent_disable` (ligne 560) |
| `POST /api/cli/agents/official/<name>/enable` | `application/routes/cli_bp_routes.py` → `cli_agent_enable` (ligne 571) |
| `GET /api/cli/agents/dynamic/list` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agents_list` (ligne 582) |
| `POST /api/cli/agents/dynamic/create` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agent_create` (ligne 589) |
| `GET /api/cli/agents/dynamic/<agent_id>` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agent_get` (ligne 614) |
| `POST /api/cli/agents/dynamic/<agent_id>/modify` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agent_modify` (ligne 624) |
| `DELETE /api/cli/agents/dynamic/<agent_id>` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agent_delete` (ligne 639) |
| `POST /api/cli/agents/dynamic/<agent_id>/save` | `application/routes/cli_bp_routes.py` → `cli_dynamic_agent_save` (ligne 649) |
| `GET /api/cli/mcp/list` | `application/routes/cli_bp_routes.py` → `cli_mcp_list` (ligne 691) |
| `GET /api/cli/mcp/tools` | `application/routes/cli_bp_routes.py` → `cli_mcp_tools` (ligne 699) |
| `POST /api/cli/mcp/call` | `application/routes/cli_bp_routes.py` → `cli_mcp_call` (ligne 740) |
| `GET /api/cli/skills/list` | `application/routes/cli_bp_routes.py` → `cli_skills_list` (ligne 821) |
| `POST /api/cli/skills/read` | `application/routes/cli_bp_routes.py` → `cli_skills_read` (ligne 829) |
| `POST /api/cli/skills/create` | `application/routes/cli_bp_routes.py` → `cli_skills_create` (ligne 847) |
| `POST /api/cli/skills/discover` | `application/routes/cli_bp_routes.py` → `cli_skills_discover` (ligne 884) |
| `GET /api/cli/connections/list` | `application/routes/cli_bp_routes.py` → `cli_connections_list` (ligne 919) |
| `POST /api/cli/connections/add` | `application/routes/cli_bp_routes.py` → `cli_connections_add` (ligne 933) |
| `POST /api/cli/connections/remove` | `application/routes/cli_bp_routes.py` → `cli_connections_remove` (ligne 960) |
| `POST /api/cli/connections/test` | `application/routes/cli_bp_routes.py` → `cli_connections_test` (ligne 971) |
| `GET /api/cli/artifacts/<token>` | `application/routes/cli_bp_routes.py` → `cli_artifact_download` (ligne 1026) |
| `POST /api/cli/mission/start` | `application/routes/cli_bp_routes.py` → `cli_mission_start` (ligne 1039) |
| `POST /api/cli/mission/<mission_id>/input` | `application/routes/cli_bp_routes.py` → `cli_mission_input` (ligne 1206) |
| `GET /api/cli/mission/<mission_id>/stream` | `application/routes/cli_bp_routes.py` → `cli_mission_stream` (ligne 1223) |
| `GET /api/cli/mission/<mission_id>/status` | `application/routes/cli_bp_routes.py` → `cli_mission_status` (ligne 1265) |
| `POST /api/cli/mission/<mission_id>/stop` | `application/routes/cli_bp_routes.py` → `cli_mission_stop` (ligne 1281) |
| `GET /api/comfyui/status` | `application/routes/comfy_life_bp_routes.py` → `comfyui_status` (ligne 14) |
| `POST /api/comfyui/start` | `application/routes/comfy_life_bp_routes.py` → `comfyui_start` (ligne 20) |
| `GET /api/comfyui/image` | `application/routes/comfy_life_bp_routes.py` → `comfyui_image` (ligne 31) |
| `GET,POST,PUT,DELETE /proxy/comfy/<path:path>` | `application/routes/comfy_proxy_bp_routes.py` → `comfyui_proxy` (ligne 13) |
| `GET /api/connect/targets/list` | `application/routes/connect_bp_routes.py` → `connect_targets_list` (ligne 42) |
| `POST /api/connect/targets/save` | `application/routes/connect_bp_routes.py` → `connect_targets_save` (ligne 52) |
| `POST /api/connect/targets/delete` | `application/routes/connect_bp_routes.py` → `connect_targets_delete` (ligne 77) |
| `POST /api/connect/ssh/probe` | `application/routes/connect_bp_routes.py` → `connect_ssh_probe` (ligne 110) |
| `POST /api/connect/ssh/run` | `application/routes/connect_bp_routes.py` → `connect_ssh_run` (ligne 155) |
| `POST /api/connect/ssh/upload` | `application/routes/connect_bp_routes.py` → `connect_ssh_upload` (ligne 200) |
| `POST /api/connect/ssh/keygen` | `application/routes/connect_bp_routes.py` → `connect_ssh_keygen` (ligne 269) |
| `POST /api/connect/tcp/probe` | `application/routes/connect_bp_routes.py` → `connect_tcp_probe` (ligne 295) |
| `GET /api/cowork/extension/poll` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_poll` (ligne 77) |
| `POST /api/cowork/extension/dispatch` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_dispatch` (ligne 106) |
| `POST /api/cowork/extension/result` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_result` (ligne 131) |
| `GET /api/cowork/extension/await-result` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_await` (ligne 145) |
| `POST /api/cowork/extension/inbound` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_inbound` (ligne 161) |
| `GET /api/cowork/extension/inbound` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_inbound_list` (ligne 172) |
| `GET /api/cowork/extension/download` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_download` (ligne 178) |
| `GET /api/cowork/extension/list` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_list` (ligne 203) |
| `GET /api/cowork/extension/status` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_status` (ligne 215) |
| `GET /api/cowork/extension/version` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_version` (ligne 236) |
| `GET /api/_dev/status` | `application/routes/cowork_ext_bp_routes.py` → `dev_status` (ligne 294) |
| `POST /api/_dev/reload` | `application/routes/cowork_ext_bp_routes.py` → `dev_reload_endpoint` (ligne 311) |
| `GET /api/warmup/status` | `application/routes/cowork_ext_bp_routes.py` → `warmup_status` (ligne 465) |
| `POST /api/warmup/restart` | `application/routes/cowork_ext_bp_routes.py` → `warmup_restart` (ligne 524) |
| `GET /api/cowork/extension/install-md` | `application/routes/cowork_ext_bp_routes.py` → `cowork_ext_install_md` (ligne 713) |
| `GET /api/picker/explain` | `application/routes/cowork_ext_bp_routes.py` → `picker_explain` (ligne 1356) |
| `GET /api/warmup/health` | `application/routes/cowork_ext_bp_routes.py` → `warmup_health` (ligne 1425) |
| `GET /api/picker/history` | `application/routes/cowork_ext_bp_routes.py` → `picker_history` (ligne 1513) |
| `POST /api/picker/history/clear` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_clear` (ligne 1530) |
| `GET /api/picker/history/stats` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_stats` (ligne 1580) |
| `GET /api/picker/history/kinds` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_kinds` (ligne 1742) |
| `GET /api/picker/history/distinct-models` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_distinct_models` (ligne 1779) |
| `GET /api/picker/history/by-model` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_by_model` (ligne 1856) |
| `GET /api/picker/history/by-reason` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_by_reason` (ligne 1940) |
| `GET /api/picker/history/timeline` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_timeline` (ligne 2042) |
| `GET /api/picker/history/timeline/summary` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_timeline_summary` (ligne 2749) |
| `GET /api/picker/history/by-model-and-reason` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_by_model_and_reason` (ligne 2819) |
| `GET /api/picker/history/intersections` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_intersections` (ligne 2941) |
| `GET /api/picker/history/cells/empty` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_cells_empty` (ligne 3050) |
| `GET /api/picker/history/coverage` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_coverage` (ligne 3168) |
| `GET /api/picker/history/coverage/global` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_coverage_global` (ligne 3288) |
| `GET /api/picker/history/coverage/timeline` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_coverage_timeline` (ligne 3454) |
| `GET /api/picker/history/coverage/heatmap` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_coverage_heatmap` (ligne 3599) |
| `POST /api/picker/history/replay` | `application/routes/cowork_ext_bp_routes.py` → `picker_history_replay` (ligne 3754) |
| `POST /api/cowork/extract-structured` | `application/routes/cowork_ext_bp_routes.py` → `cowork_extract_structured` (ligne 3850) |
| `GET /api/cowork/extraction-stats` | `application/routes/cowork_ext_bp_routes.py` → `cowork_extraction_stats` (ligne 4253) |
| `POST /api/cowork/dual-signal-event` | `application/routes/cowork_ext_bp_routes.py` → `cowork_dual_signal_event` (ligne 4450) |
| `GET /api/cowork/dual-signal-stats` | `application/routes/cowork_ext_bp_routes.py` → `cowork_dual_signal_stats` (ligne 4485) |
| `GET /api/cowork/dual-signal-effective` | `application/routes/cowork_ext_bp_routes.py` → `cowork_dual_signal_effective` (ligne 4563) |
| `POST /api/cowork/dual-signal-reset` | `application/routes/cowork_ext_bp_routes.py` → `cowork_dual_signal_reset` (ligne 4636) |
| `POST /api/cowork/trend-signal-reset` | `application/routes/cowork_ext_bp_routes.py` → `cowork_trend_signal_reset` (ligne 4698) |
| `POST /api/cowork/trend-signal-event` | `application/routes/cowork_ext_bp_routes.py` → `cowork_trend_signal_event` (ligne 4762) |
| `GET /api/cowork/trend-signal-stats` | `application/routes/cowork_ext_bp_routes.py` → `cowork_trend_signal_stats` (ligne 4795) |
| `GET /api/cowork/browsers/detect` | `application/routes/cowork_ext_bp_routes.py` → `cowork_browsers_detect` (ligne 4859) |
| `POST /api/cowork/mobile/inbound` | `application/routes/cowork_ext_bp_routes.py` → `cowork_mobile_inbound` (ligne 4953) |
| `GET /api/cowork/mobile/events` | `application/routes/cowork_ext_bp_routes.py` → `cowork_mobile_events` (ligne 4965) |
| `POST /api/cowork/mobile/dispatch` | `application/routes/cowork_ext_bp_routes.py` → `cowork_mobile_dispatch` (ligne 4972) |
| `GET /api/cowork/mobile/poll` | `application/routes/cowork_ext_bp_routes.py` → `cowork_mobile_poll` (ligne 4986) |
| `POST /api/cowork/mobile/result` | `application/routes/cowork_ext_bp_routes.py` → `cowork_mobile_result` (ligne 5000) |
| `GET /api/cowork/read` | `application/routes/cowork_file_bp_routes.py` → `cowork_read_file` (ligne 52) |
| `POST /api/cowork/write` | `application/routes/cowork_file_bp_routes.py` → `cowork_write_file` (ligne 73) |
| `POST /api/cowork/delete` | `application/routes/cowork_file_bp_routes.py` → `cowork_delete_path` (ligne 96) |
| `POST /api/cowork/session/create` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_create` (ligne 157) |
| `GET /api/cowork/session/list` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_list` (ligne 178) |
| `POST /api/cowork/session/write` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_write` (ligne 202) |
| `GET /api/cowork/session/read` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_read` (ligne 235) |
| `GET /api/cowork/session/list_files` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_list_files` (ligne 264) |
| `POST /api/cowork/session/remove` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_remove` (ligne 280) |
| `POST /api/cowork/session/cleanup` | `application/routes/cowork_file_bp_routes.py` → `cowork_session_cleanup` (ligne 300) |
| `GET /api/fs/workspace-path` | `application/routes/fs_bp_routes.py` → `fs_workspace_path` (ligne 13) |
| `POST /api/fs/exists` | `application/routes/fs_bp_routes.py` → `fs_exists` (ligne 18) |
| `POST /api/fs/mkdir` | `application/routes/fs_bp_routes.py` → `fs_mkdir` (ligne 24) |
| `POST /api/fs/read-text` | `application/routes/fs_bp_routes.py` → `fs_read_text` (ligne 31) |
| `POST /api/fs/write-text` | `application/routes/fs_bp_routes.py` → `fs_write_text` (ligne 41) |
| `POST /api/fs/write-binary` | `application/routes/fs_bp_routes.py` → `fs_write_binary` (ligne 52) |
| `POST /api/fs/read-binary` | `application/routes/fs_bp_routes.py` → `fs_read_binary` (ligne 63) |
| `POST /api/fs/remove-dir` | `application/routes/fs_bp_routes.py` → `fs_remove_dir` (ligne 73) |
| `POST /api/fs/list` | `application/routes/fs_bp_routes.py` → `fs_list_dir` (ligne 93) |
| `GET /api/hardware` | `application/routes/hardware_bp_routes.py` → `hardware` (ligne 14) |
| `GET /api/runtime/inspect` | `application/routes/hardware_bp_routes.py` → `runtime_inspect` (ligne 48) |
| `GET /api/runtime/privilege` | `application/routes/hardware_bp_routes.py` → `runtime_privilege` (ligne 84) |
| `POST /api/runtime/prepare-model` | `application/routes/hardware_bp_routes.py` → `prepare_model` (ligne 89) |
| `POST /api/cowork/iot/mqtt` | `application/routes/iot_bp_routes.py` → `cowork_iot_mqtt` (ligne 13) |
| `POST /api/cowork/iot/tuya` | `application/routes/iot_bp_routes.py` → `cowork_iot_tuya` (ligne 88) |
| `GET /api/ollama/models` | `application/routes/ollama_enh_bp_routes.py` → `ollama_models` (ligne 13) |
| `POST /api/ollama/pull` | `application/routes/ollama_enh_bp_routes.py` → `ollama_pull` (ligne 35) |
| `GET /api/ollama/tags` | `application/routes/ollama_list_bp_routes.py` → `ollama_tags` (ligne 13) |
| `POST /api/cowork/db/sql` | `application/routes/postgres_bp_routes.py` → `cowork_db_sql` (ligne 13) |
| `POST /api/python/run-async` | `application/routes/python_bp_routes.py` → `python_run_async` (ligne 830) |
| `GET,HEAD /api/ping` | `application/routes/python_bp_routes.py` → `python_bridge_ping` (ligne 863) |
| `GET /api/health` | `application/routes/python_bp_routes.py` → `python_bridge_health` (ligne 872) |
| `GET,POST /api/conformance` | `application/routes/python_bp_routes.py` → `aurora_conformance` (ligne 905) — 61 mesures comportementales : 55 TS (voix, cyber, cowork, code, image, conversation, apprentissage, dessin, mémoire, character forge, anim) + 6 Python 3D (anim/mouvement/qualité/couleur/reprise/sérialisation). |
| `GET,POST /api/architecture` | `application/routes/python_bp_routes.py` → `aurora_architecture` (ligne 1009) |
| `GET,POST /api/expertise` | `application/routes/python_bp_routes.py` → `aurora_expertise` (ligne 1033) |
| `GET /api/tunnel/url` | `application/routes/python_bp_routes.py` → `tunnel_url` (ligne 1127) |
| `GET /api/python/job/<job_id>` | `application/routes/python_bp_routes.py` → `python_job_status` (ligne 1212) |
| `POST /api/python/cancel/<job_id>` | `application/routes/python_bp_routes.py` → `python_job_cancel` (ligne 1230) |
| `POST /api/python/run` | `application/routes/python_bp_routes.py` → `python_run` (ligne 1236) |
| `POST /api/command/run` | `application/routes/python_bp_routes.py` → `command_run` (ligne 1262) |
| `POST /api/command/spawn` | `application/routes/python_bp_routes.py` → `command_spawn` (ligne 1285) |
| `GET /api/python/progress` | `application/routes/python_prog_bp_routes.py` → `python_progress` (ligne 79) |
| `POST /api/code/repo/pick` | `application/routes/repo_bp_routes.py` → `code_repo_pick` (ligne 66) |
| `POST /api/code/repo/scan` | `application/routes/repo_bp_routes.py` → `code_repo_scan` (ligne 92) |
| `POST /api/code/repo/write` | `application/routes/repo_bp_routes.py` → `code_repo_write` (ligne 184) |
| `POST /api/code/repo/git` | `application/routes/repo_bp_routes.py` → `code_repo_git_info` (ligne 242) |
| `POST /api/code/repo/install` | `application/routes/repo_bp_routes.py` → `code_repo_install` (ligne 264) |
| `GET,POST,PUT,DELETE /proxy/ollama/<path:path>` | `application/routes/repo_bp_routes.py` → `ollama_proxy` (ligne 316) |
| `POST /api/ollama/chat` | `application/routes/repo_bp_routes.py` → `ollama_chat` (ligne 324) |
| `POST /api/cowork/storage/s3` | `application/routes/s3_bp_routes.py` → `cowork_storage_s3` (ligne 13) |
| `GET /api/services/status` | `application/routes/status_bp_routes.py` → `services_status` (ligne 13) |
| `GET /api/system/info` | `application/routes/sysinfo_bp_routes.py` → `system_info` (ligne 13) |
| `POST /api/upload` | `application/routes/upload_bp_routes.py` → `upload_file` (ligne 13) |
| `GET /api/admin/status` | `application/routes/vite_bp_routes.py` → `admin_status` (ligne 149) |
| `POST,GET /api/admin/restart-bridge` | `application/routes/vite_bp_routes.py` → `admin_restart_bridge` (ligne 255) |
| `POST /api/3d/motion-compile` | `application/routes/vite_bp_routes.py` → `three_d_motion_compile` (ligne 277) |
| `POST /api/3d/motion-resolve-prompt` | `application/routes/vite_bp_routes.py` → `three_d_motion_resolve_prompt` (ligne 308) |
| `GET /api/3d/motion-parser-self-test` | `application/routes/vite_bp_routes.py` → `three_d_motion_parser_self_test` (ligne 339) |
| `GET /api/3d/motion-self-test` | `application/routes/vite_bp_routes.py` → `three_d_motion_self_test` (ligne 359) |
| `GET /api/3d/pipeline-status` | `application/routes/vite_bp_routes.py` → `three_d_pipeline_status` (ligne 385) |
| `POST /api/3d/regression-suite` | `application/routes/vite_bp_routes.py` → `three_d_regression_suite` (ligne 432) |
| `POST /api/3d/mesh-sharpen` | `application/routes/vite_bp_routes.py` → `three_d_mesh_sharpen` (ligne 545) |
| `POST /api/3d/run-pipeline` | `application/routes/vite_bp_routes.py` → `three_d_run_pipeline` (ligne 615) |
| `POST /api/3d/compose-scene` | `application/routes/vite_bp_routes.py` → `three_d_compose_scene` (ligne 730) |
| `POST /api/code/visual-audit` | `application/routes/vite_bp_routes.py` → `code_visual_audit` (ligne 1173) |
| `POST /api/code/simulation-lab` | `application/routes/vite_bp_routes.py` → `code_simulation_lab` (ligne 1229) |
| `POST /api/code/tooling-eval` | `application/routes/vite_bp_routes.py` → `code_tooling_eval` (ligne 1279) |
| `POST /api/code/assets/generate` | `application/routes/vite_bp_routes.py` → `code_assets_generate` (ligne 1325) |
| `GET /api/code/assets/file/<path:asset_path>` | `application/routes/vite_bp_routes.py` → `code_assets_file` (ligne 1399) |
| `POST /api/code/generate/stream` | `application/routes/vite_bp_routes.py` → `code_generate_stream` (ligne 1417) |
| `POST /api/aurora/<module>/<action>` | `application/routes/vite_bp_routes.py` → `aurora_module_dispatch` (ligne 1542) |
| `GET /api/3d/motion-parity` | `application/routes/vite_bp_routes.py` → `three_d_motion_parity` (ligne 1575) |
| `GET /api/3d/run-index` | `application/routes/vite_bp_routes.py` → `three_d_run_index` (ligne 1604) |
| `GET /api/3d/score-history` | `application/routes/vite_bp_routes.py` → `three_d_score_history` (ligne 1640) |
| `POST /api/3d/mesh-compare` | `application/routes/vite_bp_routes.py` → `three_d_mesh_compare` (ligne 1696) |
| `POST /api/3d/viewer-html` | `application/routes/vite_bp_routes.py` → `three_d_viewer_html` (ligne 1753) |
| `GET /draco/<path:relpath>` | `application/routes/vite_bp_routes.py` → `serve_draco_static` (ligne 1815) |
| `GET /api/agents/list` | `application/routes/vite_bp_routes.py` → `agents_list` (ligne 1862) |
| `GET /api/agents/<name>` | `application/routes/vite_bp_routes.py` → `agents_get` (ligne 1904) |
| `POST /api/3d/auto-rescue` | `application/routes/vite_bp_routes.py` → `three_d_auto_rescue` (ligne 1930) |
| `POST /api/3d/bake-colors` | `application/routes/vite_bp_routes.py` → `three_d_bake_colors` (ligne 2001) |
| `POST /api/3d/color-diagnostic` | `application/routes/vite_bp_routes.py` → `three_d_color_diagnostic` (ligne 2067) |
| `POST /api/3d/auto-validate` | `application/routes/vite_bp_routes.py` → `three_d_auto_validate` (ligne 2127) |
| `POST /api/3d/mesh-score` | `application/routes/vite_bp_routes.py` → `three_d_mesh_score` (ligne 2186) |
| `GET /api/agents/watchdog` | `application/routes/vite_bp_routes.py` → `agents_watchdog` (ligne 2236) |
| `GET /api/agents/health` | `application/routes/vite_bp_routes.py` → `agents_health` (ligne 2290) |
| `GET /api/agents/dispatches` | `application/routes/vite_bp_routes.py` → `agents_dispatches` (ligne 2327) |
| `GET /api/agents/coverage` | `application/routes/vite_bp_routes.py` → `agents_coverage` (ligne 2375) |
| `GET /api/agents/metrics` | `application/routes/vite_bp_routes.py` → `agents_metrics` (ligne 2405) |
| `POST /api/3d/route-test` | `application/routes/vite_bp_routes.py` → `three_d_route_test` (ligne 2437) |
| `POST /api/3d/motion-intent` | `application/routes/vite_bp_routes.py` → `three_d_motion_intent` (ligne 2498) |
| `POST /api/3d/custom-motion` | `application/routes/vite_bp_routes.py` → `three_d_custom_motion` (ligne 2556) |
| `POST /api/3d/auto-motion-bake` | `application/routes/vite_bp_routes.py` → `three_d_auto_motion_bake` (ligne 2632) |
| `POST,GET /api/admin/git-pull` | `application/routes/vite_bp_routes.py` → `admin_git_pull` (ligne 2783) |
| `POST,GET /api/admin/restart-vite` | `application/routes/vite_bp_routes.py` → `admin_restart_vite` (ligne 2919) |
| `GET,POST,PUT,DELETE,PATCH,HEAD,OPTIONS /` | `application/routes/vite_bp_routes.py` → `vite_root` (ligne 3109) |
| `GET,POST,PUT,DELETE,PATCH,HEAD,OPTIONS /<path:path>` | `application/routes/vite_bp_routes.py` → `vite_catchall` (ligne 3216) |
| `POST /api/voice/stt` | `application/routes/voice_bp_routes.py` → `voice_stt` (ligne 13) |
| `POST /api/voice/tts` | `application/routes/voice_bp_routes.py` → `voice_tts` (ligne 35) |
| `GET /api/voice/tts-audio` | `application/routes/voice_bp_routes.py` → `serve_tts_audio` (ligne 125) |
| `GET /api/voice/tts-video` | `application/routes/voice_bp_routes.py` → `serve_tts_video` (ligne 149) |
| `GET /api/voice/talking-head/check` | `application/routes/voice_bp_routes.py` → `talking_head_check` (ligne 158) |
| `POST /api/voice/talking-head/idle` | `application/routes/voice_bp_routes.py` → `talking_head_idle` (ligne 181) |
| `GET /api/voice/idle-video` | `application/routes/voice_bp_routes.py` → `serve_idle_video` (ligne 227) |
| `POST /api/calendar/fetch-ics` | `application/routes/voice_bp_routes.py` → `calendar_fetch_ics` (ligne 238) |
| `POST /api/ent/harvest` | `application/routes/voice_bp_routes.py` → `ent_harvest` (ligne 313) |
| `GET /api/ent/list` | `application/routes/voice_bp_routes.py` → `ent_list` (ligne 357) |
| `GET /api/ent/get` | `application/routes/voice_bp_routes.py` → `ent_get` (ligne 402) |
| `POST /api/ent/native/run` | `application/routes/voice_bp_routes.py` → `ent_native_run` (ligne 484) |
| `POST /api/ent/discover-school` | `application/routes/voice_bp_routes.py` → `ent_discover_pronote` (ligne 577) |
| `POST /api/ent/discover-pronote` | `application/routes/voice_bp_routes.py` → `ent_discover_pronote` (ligne 577) |
| `POST /api/ent/analyze-dom` | `application/routes/voice_bp_routes.py` → `ent_analyze_dom` (ligne 785) |
| `GET /api/voice/stt-info` | `application/routes/voice_bp_routes.py` → `voice_stt_info` (ligne 920) |
| `GET /api/voice/personas` | `application/routes/voice_bp_routes.py` → `voice_personas` (ligne 935) |
| `POST /api/web/action` | `application/routes/web_action_bp_routes.py` → `web_action` (ligne 13) |
| `POST /api/web/search` | `application/routes/web_search_bp_routes.py` → `web_search` (ligne 13) |
| `POST /api/web/download` | `application/routes/web_search_bp_routes.py` → `web_download` (ligne 63) |
| `POST /api/web/extract` | `application/routes/web_search_bp_routes.py` → `web_extract` (ligne 135) |
| `POST /api/web/images` | `application/routes/web_search_bp_routes.py` → `web_images` (ligne 157) |
| `POST /api/brand/enrich` | `application/routes/web_search_bp_routes.py` → `brand_enrich` (ligne 589) |
| `POST /api/web/image` | `application/routes/web_search_bp_routes.py` → `web_image_single` (ligne 680) |

### 19.3 Services d’entraînement et commandes natives

Les routes ci-dessous appartiennent à leurs services propres ; ne pas les confondre avec le bridge principal.

**`auto_rl/integration.py`**
- `GET /api/training/status` → `training_status`
- `GET /api/training/ui` → `training_ui`
- `GET /api/training/dashboard-extras.js` → `training_dashboard_extras`
- `POST /api/training/control/<action>` → `training_control`
- `POST /api/training/selection` → `training_selection`
- `GET /api/training/samples/<run_id>` → `training_samples`
- `GET /api/training/samples/<run_id>/asset` → `training_sample`
- `GET /api/training/viewer-lib/<path:name>` → `training_viewer_lib`
- `GET /api/training/diagnostic/<run_id>` → `training_diagnostic`
- `GET /api/training/runs/<run_id>/<artifact>` → `training_run_artifact`
- `POST /api/training/media` → `training_media`
- `GET /api/training/parents/<module>` → `training_parents`
- `POST /api/training/reference` → `training_reference`
- `GET /api/training/review/<run_id>` → `training_review`
- `GET /api/training/review/<run_id>/asset` → `training_review_asset`
- `GET /api/training/artifact/<path:name>` → `training_artifact`
- `GET /api/training/models` → `training_models`
- `POST /api/training/image-workflow` → `image_workflow`
- `GET,POST /proxy/trained/<path:path>` → `trained_proxy`

**`auto_rl/serve.py`**
- `GET /api/tags` → `tags`
- `GET /health` → `health`
- `POST /api/media/generate` → `media_generate`
- `POST /api/show` → `show`
- `POST /api/chat` → `chat`
- `POST /api/generate` → `chat`

#### Autres surfaces HTTP distinctes

Ces déclarations appartiennent aux variantes cloud/mobile ou au tableau de pilotage, pas au bridge local enregistré sur 3001.

| Service | Méthodes et chemin | Handler |
|---|---|---|
| `application/cloud/cloud_bridge.py` | `GET /api/python/progress` | `get_progress` |
| `application/cloud/cloud_bridge.py` | `GET /api/hardware` | `get_hardware` |
| `application/cloud/cloud_bridge.py` | `GET /api/cloud/tier` | `get_cloud_tier` |
| `application/cloud/cloud_bridge.py` | `POST /api/python/run` | `run_python_script` |
| `application/cloud/cloud_bridge.py` | `POST /api/command/run` | `run_command` |
| `application/cloud/cloud_bridge.py` | `POST /api/command/spawn` | `spawn_command` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/exists` | `fs_exists` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/mkdir` | `fs_mkdir` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/read-text` | `fs_read_text` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/write-text` | `fs_write_text` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/write-binary` | `fs_write_binary` |
| `application/cloud/cloud_bridge.py` | `POST /api/fs/read-binary` | `fs_read_binary` |
| `application/cloud/cloud_bridge.py` | `GET /api/fs/workspace-path` | `get_workspace_path` |
| `application/cloud/cloud_bridge.py` | `POST /api/voice/stt` | `voice_stt` |
| `application/cloud/cloud_bridge.py` | `POST /api/voice/tts` | `voice_tts` |
| `application/cloud/cloud_bridge.py` | `POST /api/web/search` | `web_search` |
| `application/cloud/cloud_bridge.py` | `POST /api/web/image` | `web_image` |
| `application/cloud/cloud_bridge.py` | `GET /api/services/status` | `services_status` |
| `application/cloud/cloud_bridge.py` | `GET /api/comfyui/status` | `comfyui_status` |
| `application/cloud/cloud_bridge.py` | `POST /api/comfyui/start` | `comfyui_start` |
| `application/cloud/cloud_bridge.py` | `POST /api/runtime/ensure-service` | `runtime_ensure_service` |
| `application/cloud/cloud_bridge.py` | `POST /api/runtime/prepare-model` | `runtime_prepare_model` |
| `application/cloud/cloud_bridge.py` | `GET /api/runtime/inspect` | `runtime_inspect` |
| `application/cloud/cloud_bridge.py` | `GET /api/runtime/privilege` | `runtime_privilege` |
| `application/cloud/cloud_bridge.py` | `GET /api/asset/{path:path}` | `serve_asset` |
| `application/cloud/cloud_bridge.py` | `GET /api/download/list` | `list_results` |
| `application/cloud/cloud_bridge.py` | `GET /api/download/{category}/{filename}` | `download_result` |
| `application/cloud/cloud_bridge.py` | `GET /api/health` | `health` |

Commandes Tauri déclarées dans `application/src-tauri/src/commands.rs` :

`ollama_chat`, `ollama_generate`, `ollama_list_models`, `ollama_pull_model`, `comfyui_request`, `comfyui_queue_prompt`, `comfyui_get_history`, `comfyui_get_image`, `detect_hardware`, `inspect_host_resources`, `get_host_privilege_status`, `linux_runtime_check`, `linux_runtime_install_missing`, `restart_application_as_admin`, `run_python_script`, `run_workspace_command`, `spawn_workspace_command_detached`, `check_service_status`, `get_workspace_path`, `fs_exists`, `fs_mkdir`, `fs_read_text`, `fs_write_text`, `fs_write_binary`, `fs_read_binary`, `fs_remove_dir_all`, `fs_list_dir`, `runtime_inspect_services`, `runtime_ensure_service`, `runtime_ensure_ollama_model_available`, `runtime_prepare_ollama_model`, `runtime_release_service`, `agent_pipeline_init`, `agent_pipeline_update`, `agent_pipeline_get_prompt`, `agent_pipeline_snapshot`, `execute_and_capture_error`

### 19.4 Catalogue des sources par répertoire

Cet inventaire permet de localiser les implémentations, tests et outils ; il ne prétend pas décrire chaque algorithme. Les fichiers procéduraux, patchs, sauvegardes et tests restent explicitement dans leurs répertoires. Les définitions d’agents, ignorées par Git, sont dans l’annexe suivante.

<details><summary>AuroraIA/. — 16 fichiers</summary>

```text
aurora_agi_daemon.py  (102 L)
aurora_cli.py  (30 L)
bridge_doctor.py  (284 L)
cycle_app.py  (274 L)
package.json  (13 L)
patch_routes.py  (63 L)
restart_bridge.sh  (7 L)
restart_tunnel.py  (177 L)
start-aurora.bat  (87 L)
start-aurora.sh  (240 L)
start_bridge_now.sh  (6 L)
test_cli_local.py  (54 L)
test_ipc.py  (5 L)
update-aurora-prod.bat  (102 L)
update-aurora.bat  (56 L)
workflow_world_mirror_preview.json  (68 L)
```

</details>

<details><summary>AuroraIA/_design/aurora_design_lib — 1 fichiers</summary>

```text
tokens.css  (157 L)
```

</details>

<details><summary>AuroraIA/_design/aurora_design_lib/lib — 1 fichiers</summary>

```text
tokens.css  (157 L)
```

</details>

<details><summary>AuroraIA/_design/ds2/mobile-final — 1 fichiers</summary>

```text
grimoire.css  (728 L)
```

</details>

<details><summary>AuroraIA/_dev — 1 fichiers</summary>

```text
uplift_report.json  (287 L)
```

</details>

<details><summary>AuroraIA/agi_core — 8 fichiers</summary>

```text
bus.py  (116 L)
consciousness.py  (74 L)
explorer.py  (26 L)
llm_gateway.py  (92 L)
memory.py  (43 L)
mission_agent.py  (360 L)
payload_manager.py  (39 L)
swarm.py  (155 L)
```

</details>

<details><summary>AuroraIA/application — 20 fichiers</summary>

```text
AUDIT_MODULE_CODE_data.json  (3225 L)
VERIFICATION_REFONTE_CODE_data.json  (1605 L)
aurora_native_mcp.py  (58 L)
bridge_server.py  (1338 L)
cli_artifacts.py  (52 L)
comfy_runtime.py  (38 L)
package.json  (81 L)
scan_ports.py  (47 L)
test_bridge_dual_signal.py  (229 L)
test_bridge_dual_signal_effective.py  (199 L)
test_bridge_extract_headers.py  (192 L)
test_bridge_extraction_stats.py  (438 L)
test_bridge_host_yield_delta.py  (277 L)
test_bridge_v82m7_trend_and_reset.py  (256 L)
test_bridge_v82m9_trend_reset_and_ttl.py  (242 L)
test_cli_mission_events.py  (117 L)
tsconfig.json  (23 L)
tsconfig.node.json  (15 L)
vite.config.ts  (232 L)
vite.smoke.config.ts  (20 L)
```

</details>

<details><summary>AuroraIA/application/aurora-connect-extension — 5 fichiers</summary>

```text
background.js  (388 L)
content.js  (50 L)
manifest.json  (53 L)
options.js  (48 L)
popup.js  (50 L)
```

</details>

<details><summary>AuroraIA/application/bridge_state — 1 fichiers</summary>

```text
brand_enrich_cache.json  (336 L)
```

</details>

<details><summary>AuroraIA/application/cloud — 3 fichiers</summary>

```text
bootstrap_runpod_a100.sh  (101 L)
cloud_bridge.py  (1005 L)
start.sh  (356 L)
```

</details>

<details><summary>AuroraIA/application/config — 2 fichiers</summary>

```text
storage_manifest.json  (66 L)
video_model_strategy.json  (210 L)
```

</details>

<details><summary>AuroraIA/application/extension — 9 fichiers</summary>

```text
background.js  (1127 L)
content-autologin.js  (203 L)
content-scrape.js  (553 L)
content.js  (50 L)
manifest.json  (68 L)
options.js  (48 L)
popup-credentials.js  (145 L)
popup.js  (235 L)
vault.js  (204 L)
```

</details>

<details><summary>AuroraIA/application/mobile — 1 fichiers</summary>

```text
aurora-ios-shortcuts.json  (108 L)
```

</details>

<details><summary>AuroraIA/application/public — 3 fichiers</summary>

```text
aurora-embed.js  (208 L)
basis_transcoder.js  (19 L)
sw.js  (34 L)
```

</details>

<details><summary>AuroraIA/application/public/aurora-team — 1 fichiers</summary>

```text
manifest.json  (18 L)
```

</details>

<details><summary>AuroraIA/application/public/draco — 2 fichiers</summary>

```text
draco_decoder.js  (34 L)
draco_wasm_wrapper.js  (117 L)
```

</details>

<details><summary>AuroraIA/application/public/draco/gltf — 2 fichiers</summary>

```text
draco_decoder.js  (33 L)
draco_wasm_wrapper.js  (116 L)
```

</details>

<details><summary>AuroraIA/application/python-services — 623 fichiers</summary>

```text
_bl_compat_startup.py  (54 L)
add_cyber_matrix_and_soften_ears.py  (67 L)
anim_frames_probe.py  (83 L)
anim_metrics.py  (1354 L)
anki_export.py  (139 L)
apply_mega_decal_flawless.py  (304 L)
apply_perfect_metis_color_transfer.py  (38 L)
apply_pro_tshirt_blender.py  (236 L)
apply_torso_decal.py  (204 L)
apply_torso_decal_perfect.py  (242 L)
apply_vector_decals.py  (236 L)
atlas_dilate.py  (179 L)
attach_5finger_hands.py  (168 L)
aurora_3d_mcp.py  (794 L)
aurora_3d_pipeline.py  (6273 L)
aurora_3d_viewer.py  (599 L)
aurora_cleanup_outputs.py  (154 L)
aurora_output_paths.py  (196 L)
auto_rescue_mesh.py  (599 L)
auto_tag_images.py  (109 L)
auto_validate_mesh.py  (181 L)
bac_resources.py  (287 L)
bake_ao_map.py  (452 L)
bake_dual_projection.py  (202 L)
bake_flawless_master.py  (205 L)
bake_high_definition_character.py  (236 L)
bake_normal_map.py  (233 L)
bake_perfect_master.py  (205 L)
bake_pixar_head_master_texture.py  (32 L)
bake_solid_master_glb.py  (229 L)
bake_spatial_reference_maps.py  (76 L)
bake_to_texture.py  (303 L)
bake_vertex_colors.py  (252 L)
batch_3d_pipeline_runner.py  (152 L)
birefnet_clean_mask.py  (30 L)
blender_bridge.py  (3990 L)
blender_render_benchmark.py  (127 L)
blender_uv_projector.py  (214 L)
bridge_wrist_seam.py  (29 L)
build_complete_master_scene.py  (625 L)
build_faithful_portrait_3d.py  (148 L)
build_female_avatar_masterpiece.py  (575 L)
build_final_flawless_character.py  (361 L)
build_flawless_ai_production_scene.py  (457 L)
build_flawless_sleeve_and_arms.py  (187 L)
build_flawless_two_generation_scene.py  (678 L)
build_guild_hall_authentic_final.py  (291 L)
build_guild_hall_expert_aaa.py  (256 L)
build_guild_hall_masterpiece_v2.py  (306 L)
build_guild_hall_masterpiece_v3.py  (272 L)
build_guild_hall_standalone_masterpiece.py  (196 L)
build_living_creature_scene.py  (543 L)
build_magnolia_fairy_tail_city.py  (567 L)
build_magnolia_masterpiece_realistic.py  (820 L)
build_master_living_creature_scene.py  (561 L)
build_master_pro_glb.py  (297 L)
build_masterpiece_production.py  (570 L)
build_mesh_metis.py  (189 L)
build_perfect_five_finger_hands.py  (96 L)
build_perfect_mega_glb.py  (234 L)
build_perfect_metis_caricature.py  (190 L)
build_perfect_metis_character.py  (224 L)
build_perfect_multi_material_perso.py  (351 L)
build_proportional_unified_arms.py  (181 L)
build_pure_caricature_master.py  (304 L)
build_pure_caricature_model.py  (389 L)
build_seamless_caricature_arms.py  (195 L)
build_seamless_master_glb.py  (234 L)
build_stylized_caricature_hands.py  (125 L)
build_ultimate_caricature_masterpiece.py  (539 L)
build_unified_arms_and_hands.py  (214 L)
cache_paths.py  (234 L)
character_research.py  (358 L)
check_arm_color.py  (15 L)
clean_and_dilate_atlas.py  (44 L)
clean_base_torso.py  (46 L)
clean_ear_redness_final.py  (20 L)
clean_face_texture.py  (49 L)
clean_single_building_crop.py  (23 L)
color_texture.py  (53 L)
comfy_supervisor.py  (147 L)
crawl4ai_search.py  (615 L)
create_clean_rgba_master.py  (22 L)
create_pristine_metis_texture.py  (30 L)
crop_clean_master.py  (17 L)
debug_bake_tex.py  (13 L)
depth_sculpt_enhancer.py  (106 L)
dilate_skin_to_hairline.py  (25 L)
direct_texture_projector.py  (104 L)
document_extract.py  (160 L)
domain_router.py  (293 L)
dreamgaussian_run.py  (277 L)
emissive_synth.py  (271 L)
enhance_head_texture.py  (53 L)
enhance_metis_skin_texture.py  (39 L)
ent_native_browser.py  (397 L)
ephemeral_tool_sandbox.py  (168 L)
face_refine.py  (1125 L)
face_restore.py  (959 L)
faithful_scene_prompt.py  (641 L)
find_face_island.py  (51 L)
find_skin_uv.py  (16 L)
fix_hair_color_and_render.py  (30 L)
fix_hair_zenith_texture.py  (52 L)
fix_hair_zenith_uvs.py  (37 L)
fix_leg_uv_symmetry.py  (49 L)
flood_fill_clean_matte.py  (27 L)
fluid_mesh_builder.py  (339 L)
fluid_sim_baker.py  (407 L)
flux_pose_control.py  (134 L)
flux_reference_synth.py  (1202 L)
forge_layers.py  (383 L)
forge_warmup.py  (119 L)
forge_write_rig.py  (36 L)
fusion_acteurs.py  (79 L)
generate_15_masterpiece_assets.py  (123 L)
generate_all_15_glb_models.py  (153 L)
generate_art_master.py  (185 L)
generate_avatar.py  (541 L)
generate_clean_solid_tshirt.py  (248 L)
generate_consistent_multiview_references.py  (125 L)
generate_dragon_concept.py  (49 L)
generate_face_glb.py  (237 L)
generate_female_tshirt_graphic.py  (82 L)
generate_five_finger_hand.py  (80 L)
generate_mega_streetwear_tshirt.py  (248 L)
generate_natural_tshirt_graphics.py  (61 L)
generate_perfect_isolated_masterpiece.py  (281 L)
generate_perso_master_3d.py  (191 L)
generate_pro_tshirt.py  (224 L)
generate_single_clean_masterpiece.py  (240 L)
generate_tshirt_patches.py  (44 L)
glb_animation_injector.py  (789 L)
glb_clips_merge.py  (180 L)
glb_elaguer.py  (71 L)
glb_io.py  (79 L)
glb_material_writer.py  (407 L)
harmonize_metis_complexion.py  (53 L)
head_material_pbr.py  (161 L)
houdini_sim.py  (436 L)
human_prompt_director.py  (359 L)
hymotion_generate.py  (167 L)
hymotion_to_bvh.py  (128 L)
image_module_engine.py  (584 L)
image_to_motion.py  (423 L)
inspect_arm_uv.py  (29 L)
inspect_baked_tf.py  (58 L)
inspect_base_mesh.py  (16 L)
inspect_ear_texture.py  (40 L)
inspect_ear_uvs.py  (23 L)
inspect_ears_and_hair.py  (29 L)
inspect_face_island_uv.py  (27 L)
inspect_face_skin.py  (41 L)
inspect_face_uv_pixels.py  (29 L)
inspect_forearm_cross_section.py  (24 L)
inspect_forehead_polys.py  (17 L)
inspect_hands.py  (20 L)
inspect_head_bounds.py  (29 L)
inspect_head_features.py  (25 L)
inspect_orig_texture.py  (23 L)
inspect_perso_soude_source.py  (16 L)
inspect_pristine_glb.py  (9 L)
inspect_pristine_meshes.py  (13 L)
inspect_raw_tex_islands.py  (40 L)
inspect_ref_dim.py  (29 L)
inspect_saine_glb.py  (9 L)
inspect_saine_tex.py  (12 L)
inspect_skin_palette.py  (11 L)
inspect_sleeve_cuff.py  (18 L)
inspect_sleeve_mesh.py  (28 L)
inspect_texture_atlas.py  (36 L)
inspect_texture_colors.py  (14 L)
inspect_top_head.py  (37 L)
inspect_uv_face.py  (29 L)
inspect_wrist_joint.py  (29 L)
inspect_zenith_verts.py  (33 L)
install_bl_compat.py  (58 L)
kinematics_catalog.json  (920 L)
liquide_interieur.py  (219 L)
livraison_organisee.py  (361 L)
llm_disponible.py  (98 L)
make_preview_glb.py  (33 L)
material_intel_classifier.py  (563 L)
material_manifest.py  (257 L)
material_vision_pass.py  (480 L)
mesh_acceptance_gate.py  (855 L)
mesh_batch_rescue.py  (166 L)
mesh_color_diagnostic.py  (251 L)
mesh_compare.py  (116 L)
mesh_part_split.py  (375 L)
mesh_postprocess.py  (838 L)
mesh_quality_score.py  (537 L)
mesh_reshape.py  (180 L)
mesh_run_index.py  (228 L)
mesh_sanitize.py  (536 L)
mesh_screenshot.py  (575 L)
mesh_sharpen.py  (173 L)
mesh_taubin.py  (127 L)
mesh_visual_audit.py  (243 L)
mesh_weld.py  (178 L)
meshroom_run.py  (211 L)
meshy_client.py  (420 L)
mia_mocap_retarget.py  (417 L)
mia_walk_apply.py  (159 L)
mocap_bake_bpy.py  (787 L)
mocap_pipeline.py  (214 L)
model_prepare.py  (225 L)
module_progress_tracker.py  (224 L)
momask_generate.py  (236 L)
morphology.py  (318 L)
motion_autocorrect.py  (237 L)
motion_baker.py  (1574 L)
motion_clay_render.py  (229 L)
motion_composite.py  (68 L)
motion_composite_blender.py  (86 L)
motion_intent_baker.py  (360 L)
motion_intent_bpy_runner.py  (3845 L)
motion_intent_classifier.py  (668 L)
motion_parser.py  (620 L)
motion_score.py  (216 L)
motion_spec.py  (83 L)
motion_timeline_planner.py  (148 L)
motion_trend_resolver.py  (407 L)
mvadapter_i2mv_offload.py  (169 L)
mvadapter_multiview.py  (228 L)
mvadapter_retexture.py  (296 L)
native_texture_precision.py  (334 L)
natural_pixar_skin_grading.py  (46 L)
neural_process.py  (28 L)
openpose_skeleton.py  (167 L)
optimize_textured_mesh.py  (243 L)
organize_image_by_category_and_subject.py  (79 L)
organize_image_by_subject.py  (380 L)
orient_canonique.py  (105 L)
orient_rendu_bpy.py  (90 L)
overhaul_all_character_textures.py  (136 L)
paint_pbr_v21.py  (324 L)
perfect_ears_and_skin_4k.py  (29 L)
perfect_masterpiece_perso.py  (377 L)
perfect_metis_arms_and_tone.py  (219 L)
perfect_metis_skin_and_hairline.py  (40 L)
perfection_gate.py  (710 L)
photo_rectifier.py  (414 L)
porte_anti_masque.py  (99 L)
portrait_sculpt_and_texture.py  (329 L)
portrait_texture_4k.py  (328 L)
pose_analyse.py  (100 L)
postprocess_watertight_clean.py  (156 L)
poussiere_capillaire.py  (79 L)
proc_3d_printer.py  (270 L)
proc_african_savanna_elephants.py  (1097 L)
proc_african_savanna_safari_acacia.py  (1094 L)
proc_alchemist_lab.py  (591 L)
proc_alien_planet_purple.py  (457 L)
proc_alpine_meadow_bees.py  (705 L)
proc_amazon_jungle_tribe_river.py  (978 L)
proc_amsterdam_canals_dutch_houses.py  (921 L)
proc_ancient_greek_olympics.py  (880 L)
proc_ancient_library_scholar.py  (561 L)
proc_antarctic_penguins_emperor_colony.py  (596 L)
proc_aquarium.py  (379 L)
proc_arcade_machine.py  (236 L)
proc_arctic_inuit_village.py  (811 L)
proc_argentina_tango_buenos_aires.py  (744 L)
proc_argentinian_tango_milonga.py  (916 L)
proc_art_museum_gallery.py  (470 L)
proc_astronaut.py  (318 L)
proc_atlantis_submerged_temple.py  (918 L)
proc_aurora_borealis.py  (314 L)
proc_australian_outback_aboriginal_uluru.py  (954 L)
proc_australian_outback_uluru.py  (1080 L)
proc_auto_landscape.py  (129 L)
proc_autumn_forest_falling_leaves.py  (751 L)
proc_aztec_chinampa_xochimilco.py  (1182 L)
proc_basketball_hoop.py  (352 L)
proc_bavarian_oktoberfest_beerhall.py  (991 L)
proc_bbq_grill.py  (349 L)
proc_beach_umbrella.py  (277 L)
proc_belgian_bruges_canals_chocolate.py  (638 L)
proc_bhutan_tigers_nest_cliff_monastery.py  (634 L)
proc_bicycle.py  (316 L)
proc_bike_rack.py  (392 L)
proc_billiard_table.py  (401 L)
proc_bioluminescent_abyss.py  (769 L)
proc_black_hole.py  (293 L)
proc_bonsai.py  (256 L)
proc_botswana_okavango_delta_safari.py  (788 L)
proc_bowling_lane.py  (290 L)
proc_brazilian_carnival_rio.py  (993 L)
proc_butterfly_garden.py  (532 L)
proc_cable_chain.py  (193 L)
proc_cambodian_angkor_wat_temple.py  (658 L)
proc_campfire_scene.py  (329 L)
proc_camping_tent.py  (295 L)
proc_canadian_wilderness_aurora_lake.py  (752 L)
proc_capetown_table_mountain_penguins.py  (633 L)
proc_car_lowpoly.py  (226 L)
proc_cargo_ship.py  (286 L)
proc_caribbean_jamaica_reggae_beach.py  (639 L)
proc_caribbean_pirate_island_treasure.py  (1093 L)
proc_carnival_rio_samba_brazil.py  (966 L)
proc_carousel.py  (342 L)
proc_castle.py  (287 L)
proc_cathedral_gothic_interior.py  (445 L)
proc_celtic_stonehenge_druids.py  (923 L)
proc_chandelier.py  (308 L)
proc_chess_board.py  (257 L)
proc_chess_set_board.py  (528 L)
proc_chinese_dragon_new_year.py  (947 L)
proc_chinese_great_wall_dragon.py  (977 L)
proc_christmas_market_european_lights.py  (1249 L)
proc_christmas_tree.py  (325 L)
proc_circus_tent.py  (550 L)
proc_classical_violin.py  (518 L)
proc_clock_interior_mechanism.py  (381 L)
proc_clockwork_city_steampunk.py  (468 L)
proc_comet.py  (307 L)
proc_coral_reef.py  (509 L)
proc_crystal_ball.py  (237 L)
proc_crystal_cave_geode.py  (467 L)
proc_crystal_cluster.py  (219 L)
proc_cuban_havana_salsa_classic_cars.py  (843 L)
proc_cyberpunk_city.py  (459 L)
proc_desert_oasis.py  (512 L)
proc_dinosaur_trex.py  (520 L)
proc_disco_ball.py  (206 L)
proc_dna_helix.py  (285 L)
proc_domino_chain.py  (225 L)
proc_dragon_city_battle.py  (588 L)
proc_dragon_egg_lava.py  (520 L)
proc_dragon_flying.py  (484 L)
proc_dragon_lair.py  (445 L)
proc_dragon_skull_desert.py  (526 L)
proc_drone_quad.py  (270 L)
proc_drum_kit.py  (303 L)
proc_dslr_camera.py  (340 L)
proc_dubai_burj_khalifa_desert.py  (861 L)
proc_dutch_tulip_windmill_field.py  (941 L)
proc_easel.py  (366 L)
proc_egyptian_pharaoh_tomb_pyramid.py  (859 L)
proc_egyptian_pyramid_afterlife_anubis.py  (1149 L)
proc_egyptian_temple_pharaoh.py  (497 L)
proc_espresso_machine.py  (449 L)
proc_estonian_tallinn_medieval_old_town.py  (609 L)
proc_ethiopian_lalibela_rock_churches.py  (599 L)
proc_excavator_tractopelle.py  (491 L)
proc_fantasy_market.py  (608 L)
proc_ferris_wheel.py  (310 L)
proc_fighter_jet_f35.py  (480 L)
proc_fire_hydrant.py  (362 L)
proc_fire_pit.py  (327 L)
proc_flacon_parfum_lapin.py  (313 L)
proc_floating_islands_dragons.py  (493 L)
proc_floating_market_thai.py  (536 L)
proc_food_truck.py  (519 L)
proc_fountain.py  (203 L)
proc_galapagos_islands_wildlife_diversity.py  (718 L)
proc_galaxy_spiral.py  (292 L)
proc_gear_train.py  (216 L)
proc_giant_robot_mecha_battle.py  (709 L)
proc_giant_spider_cave.py  (499 L)
proc_giant_squid_battle.py  (578 L)
proc_giant_tree_of_life.py  (546 L)
proc_globe.py  (247 L)
proc_golf_cart.py  (332 L)
proc_gramophone.py  (247 L)
proc_grand_piano.py  (302 L)
proc_grandfather_clock_workshop.py  (644 L)
proc_greek_acropolis_athens_temple.py  (1006 L)
proc_greek_olympus_pantheon.py  (932 L)
proc_hammock.py  (290 L)
proc_haunted_house.py  (531 L)
proc_hawaiian_luau_volcano_hula.py  (674 L)
proc_helicopter.py  (300 L)
proc_helicopter_apache.py  (472 L)
proc_historical_person_performer.py  (798 L)
proc_hongkong_night_skyline_skyscrapers.py  (630 L)
proc_hot_air_balloon.py  (265 L)
proc_hourglass.py  (247 L)
proc_ice_cave_aurora.py  (453 L)
proc_iceberg.py  (393 L)
proc_iceland_geysir_aurora_volcanoes.py  (614 L)
proc_iguazu_falls_rainforest_toucans.py  (632 L)
proc_inca_temple_jungle.py  (936 L)
proc_indian_diwali_festival_lights.py  (1010 L)
proc_indian_holi_festival_colors.py  (996 L)
proc_indonesian_bali_temple_kecak.py  (621 L)
proc_irish_pub_dance_celtic.py  (1177 L)
proc_jamaican_blue_mountains_coffee_plantation.py  (621 L)
proc_japanese_garden.py  (440 L)
proc_japanese_hanami_sakura.py  (785 L)
proc_japanese_kyoto_torii_zen.py  (718 L)
proc_japanese_onsen_hot_springs.py  (838 L)
proc_jellyfish_bioluminescent.py  (448 L)
proc_jet_ski.py  (297 L)
proc_jungle_sloth_canopy.py  (528 L)
proc_kayak.py  (281 L)
proc_knight_tournament.py  (459 L)
proc_korean_gyeongbokgung_palace.py  (1067 L)
proc_korean_jeju_haenyeo_volcanic.py  (517 L)
proc_korean_palace_gyeongbokgung_hanbok.py  (914 L)
proc_kraken_storm_galleon.py  (908 L)
proc_laptop.py  (346 L)
proc_lava_lamp.py  (208 L)
proc_lighthouse.py  (247 L)
proc_lighthouse_storm.py  (459 L)
proc_maasai_savanna_kilimanjaro.py  (1095 L)
proc_machu_picchu_inca_andes.py  (820 L)
proc_madagascar_baobab_avenue_lemurs.py  (681 L)
proc_mailbox.py  (310 L)
proc_maldives_overwater_bungalows_reef.py  (612 L)
proc_maori_new_zealand_haka_warriors.py  (620 L)
proc_mars_rover.py  (313 L)
proc_mayan_temple_jungle.py  (755 L)
proc_mech_battle_arena.py  (585 L)
proc_medieval_feast_tavern.py  (500 L)
proc_medieval_king_coronation.py  (1304 L)
proc_meteor_impact_crater_dinosaurs.py  (870 L)
proc_mexican_dia_de_muertos.py  (1006 L)
proc_microscope.py  (252 L)
proc_microwave.py  (342 L)
proc_minecart_underground_gold_mine.py  (833 L)
proc_mongol_horde_steppe.py  (1083 L)
proc_mongolian_steppe_nomads_eagles.py  (664 L)
proc_moon_lander.py  (344 L)
proc_moroccan_marrakech_souk_medina.py  (941 L)
proc_moroccan_medina_souk.py  (813 L)
proc_motorcycle_chopper.py  (513 L)
proc_mushroom_forest.py  (433 L)
proc_nebula_space_colony.py  (490 L)
proc_neon_arcade.py  (533 L)
proc_nepalese_kathmandu_durbar_square.py  (725 L)
proc_new_orleans_jazz_mardi_gras.py  (815 L)
proc_newtons_cradle.py  (256 L)
proc_norse_yggdrasil_world_tree.py  (871 L)
proc_norwegian_fjord_viking_ship.py  (819 L)
proc_norwegian_fjord_viking_village.py  (1011 L)
proc_observatory.py  (481 L)
proc_octopus_giant.py  (401 L)
proc_origami_paper_workshop.py  (504 L)
proc_ouzbekistan_samarkand_silk_road.py  (621 L)
proc_owl_forest_night.py  (395 L)
proc_paraglider.py  (311 L)
proc_park_bench.py  (313 L)
proc_patagonia_torres_del_paine_glaciers.py  (648 L)
proc_pendulum_clock.py  (301 L)
proc_persian_palace_1001_nights.py  (1025 L)
proc_petra_jordan_treasury_canyon.py  (673 L)
proc_philippine_banaue_rice_terraces.py  (585 L)
proc_phoenix_mythical.py  (460 L)
proc_phoenix_nest_rebirth.py  (542 L)
proc_phone_booth.py  (426 L)
proc_picnic_table.py  (305 L)
proc_pinball_machine.py  (345 L)
proc_pirate_ship.py  (537 L)
proc_pirate_treasure_island.py  (1051 L)
proc_piston_crank.py  (211 L)
proc_pizza_oven.py  (411 L)
proc_planetarium_observatory_dome.py  (891 L)
proc_playground_slide.py  (312 L)
proc_playground_swing.py  (251 L)
proc_postbox.py  (373 L)
proc_provence_lavender_fields.py  (811 L)
proc_pulley_belt.py  (334 L)
proc_pyramid_egypt.py  (399 L)
proc_rainforest_thunderstorm.py  (733 L)
proc_refrigerator.py  (398 L)
proc_ringed_planet.py  (284 L)
proc_robot_arm.py  (211 L)
proc_robot_humanoid.py  (455 L)
proc_rocket_launchpad.py  (231 L)
proc_roman_colosseum_gladiators.py  (1035 L)
proc_russian_kremlin_red_square.py  (985 L)
proc_sahara_sandstorm_caravan.py  (659 L)
proc_sailboat.py  (277 L)
proc_samurai_duel_sakura.py  (762 L)
proc_sandbox.py  (321 L)
proc_satellite.py  (259 L)
proc_savanna_safari.py  (533 L)
proc_scottish_highland_castle.py  (1107 L)
proc_scottish_highland_kilts_pipers.py  (988 L)
proc_see_saw.py  (270 L)
proc_skate_ramp.py  (386 L)
proc_snow_globe.py  (280 L)
proc_soccer_goal.py  (346 L)
proc_solar_system.py  (292 L)
proc_space_station.py  (474 L)
proc_spaceship_starship.py  (462 L)
proc_spanish_andalusian_flamenco_patio.py  (998 L)
proc_spanish_flamenco_seville.py  (846 L)
proc_sports_car_smooth.py  (499 L)
proc_spring.py  (175 L)
proc_steam_locomotive.py  (313 L)
proc_steampunk_airship.py  (457 L)
proc_steampunk_armada_balloons.py  (513 L)
proc_steampunk_clock_tower.py  (500 L)
proc_steampunk_railway_station.py  (957 L)
proc_steampunk_submarine_interior.py  (523 L)
proc_street_lamp.py  (315 L)
proc_studio_microphone.py  (392 L)
proc_supernova.py  (258 L)
proc_surfboard.py  (289 L)
proc_sushi_platter.py  (229 L)
proc_swiss_alps_chalet_yodeling.py  (990 L)
proc_swiss_chalet_alps.py  (487 L)
proc_sword.py  (255 L)
proc_tahitian_polynesian_luau.py  (1120 L)
proc_tank_military_smooth.py  (455 L)
proc_telescope.py  (265 L)
proc_tennis_court.py  (289 L)
proc_texas_cowboys_rodeo_corral.py  (789 L)
proc_thai_floating_market_lanterns.py  (789 L)
proc_tibetan_monastery_himalaya.py  (877 L)
proc_titanic_ocean_liner.py  (443 L)
proc_toaster.py  (386 L)
proc_tornado.py  (408 L)
proc_tower_crane.py  (296 L)
proc_traffic_light.py  (286 L)
proc_train_station.py  (568 L)
proc_treadmill.py  (352 L)
proc_tree.py  (279 L)
proc_treehouse_village.py  (486 L)
proc_turkish_cappadocia_hot_air_balloons.py  (603 L)
proc_typewriter.py  (348 L)
proc_ufo.py  (307 L)
proc_underwater_atlantis_ruins.py  (582 L)
proc_underwater_submarine.py  (465 L)
proc_vending_machine.py  (379 L)
proc_venetian_carnival_gondola_masks.py  (997 L)
proc_vietnamese_halong_bay_junks.py  (646 L)
proc_viking_longhouse_feast.py  (1015 L)
proc_vintage_camera_studio.py  (518 L)
proc_volcanic_eruption_lava.py  (526 L)
proc_volcano.py  (297 L)
proc_washing_machine.py  (361 L)
proc_water_wheel.py  (223 L)
proc_waterfall.py  (412 L)
proc_welsh_snowdonia_castle_dragons.py  (728 L)
proc_whale_breaching_ocean.py  (518 L)
proc_windmill.py  (233 L)
proc_winter_village.py  (600 L)
proc_wishing_well.py  (243 L)
proc_witch_cottage_forest.py  (608 L)
proc_witch_potion_brewing.py  (1038 L)
proc_workbench_scene.py  (344 L)
proc_wormhole.py  (278 L)
proc_xylophone.py  (285 L)
proc_yacht_luxury.py  (560 L)
proc_yellowstone_geysers_bison_wolves.py  (635 L)
project_photo_4k.py  (234 L)
ranger_generations.py  (55 L)
reconstruct_flawless_perso.py  (277 L)
reference_visual_search.py  (409 L)
render_360_turntable.py  (56 L)
render_double_turntable.py  (51 L)
render_dual_portrait.py  (114 L)
render_female_avatar_master.py  (117 L)
render_female_master_verification.py  (121 L)
render_hand_verification.py  (79 L)
render_hand_zoom.py  (63 L)
render_iso_turntable.py  (52 L)
render_master_verification.py  (97 L)
render_portrait_hd.py  (90 L)
render_project_turntable.py  (48 L)
render_saine_check.py  (42 L)
render_saine_preview.py  (33 L)
render_studio_verre.py  (56 L)
render_transparent_vector_tshirt.py  (209 L)
render_vector_tshirt.py  (216 L)
render_views.py  (82 L)
render_vizion_preview.py  (33 L)
restore_crisp_features_4k.py  (29 L)
reuv_rebake.py  (214 L)
rigify_autorig.py  (1759 L)
roughness_realism.py  (138 L)
roughness_synth.py  (286 L)
run_deep_image_benchmark.py  (167 L)
run_masterpiece_pack_generator.py  (67 L)
run_monobloc_world.py  (120 L)
run_mvadapter_benchmark.py  (48 L)
run_mvadapter_benchmark_cpu.py  (45 L)
run_real_pipeline_optimizer.py  (111 L)
run_sota_guild_hall_master.sh  (132 L)
run_sota_production_pipeline.py  (176 L)
run_trellis_sota_guild_hall.py  (147 L)
run_true_360_masterpiece_pipeline.py  (282 L)
run_ultimate_benchmark_dragon.py  (236 L)
run_ultra_complex_suite.py  (78 L)
runtime_prepare.py  (200 L)
sample_reference_colors.py  (29 L)
scene_compose_bpy.py  (834 L)
scene_composer.py  (222 L)
scene_intelligence.py  (228 L)
scene_orchestrator.py  (1077 L)
score_history.py  (298 L)
sculpted_water_animator.py  (270 L)
segment_materiaux_zones.py  (255 L)
selection_sujet.py  (175 L)
sim_vers_glb.py  (177 L)
smoke_card_builder.py  (357 L)
smooth_forehead_ridge.py  (29 L)
soft_drape_baker.py  (153 L)
split_multiview_strip.py  (25 L)
stage_quality_gate.py  (94 L)
studio_voix.py  (1030 L)
subject_kind_extractor.py  (215 L)
texture_despeckle.py  (76 L)
texture_despeckle_atlas.py  (706 L)
texture_fidelity.py  (266 L)
texture_fidelity_bpy.py  (410 L)
texture_hands_caramel.py  (35 L)
three_d_blender_heavy_test.py  (1124 L)
three_d_regression_suite.py  (800 L)
tool_inspector.py  (132 L)
tracker_helper.py  (119 L)
unify_metis_skin_and_pose.py  (190 L)
upright_object.py  (332 L)
uv_unwrap_propre.py  (122 L)
verify_mesh_deformation.py  (61 L)
vlm_judge.py  (127 L)
voice_service.py  (1114 L)
web_action_browser.py  (85 L)
zone_mask_baker.py  (182 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint — 3 fichiers</summary>

```text
convert_utils.py  (140 L)
demo.py  (35 L)
textureGenPipeline.py  (194 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/DifferentiableRenderer — 8 fichiers</summary>

```text
MeshRender.py  (1418 L)
__init__.py  (0 L)
camera_utils.py  (107 L)
compile_fixed.bat  (62 L)
compile_mesh_painter.sh  (1 L)
mesh_utils.py  (287 L)
setup.py  (55 L)
test_module.py  (59 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/custom_rasterizer — 1 fichiers</summary>

```text
setup.py  (50 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/custom_rasterizer/custom_rasterizer — 2 fichiers</summary>

```text
__init__.py  (4 L)
render.py  (32 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/custom_rasterizer/lib/custom_rasterizer_kernel — 1 fichiers</summary>

```text
__init__.py  (0 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/hunyuanpaintpbr — 2 fichiers</summary>

```text
__init__.py  (39 L)
pipeline.py  (736 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/hunyuanpaintpbr/unet — 3 fichiers</summary>

```text
attn_processor.py  (839 L)
model.py  (622 L)
modules.py  (1102 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/src — 1 fichiers</summary>

```text
__init__.py  (13 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/src/data — 2 fichiers</summary>

```text
__init__.py  (13 L)
objaverse_hunyuan.py  (79 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/src/data/dataloader — 2 fichiers</summary>

```text
loader_util.py  (219 L)
objaverse_loader_forTexturePBR.py  (146 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/src/utils — 2 fichiers</summary>

```text
__init__.py  (13 L)
train_util.py  (40 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/utils — 7 fichiers</summary>

```text
__init__.py  (13 L)
image_super_utils.py  (50 L)
multiview_utils.py  (129 L)
pipeline_utils.py  (135 L)
simplify_mesh_utils.py  (62 L)
torchvision_fix.py  (111 L)
uvwrap_utils.py  (32 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_patches — 2 fichiers</summary>

```text
custom_rasterizer_setup.py  (30 L)
mesh_render.py  (943 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_patches/hy3dpaint_2.1 — 3 fichiers</summary>

```text
DifferentiableRenderer_setup.py  (55 L)
build_hy3d21.bat  (36 L)
custom_rasterizer_setup.py  (50 L)
```

</details>

<details><summary>AuroraIA/application/python-services/aurora_code — 40 fichiers</summary>

```text
aurora_code_enrich.py  (178 L)
aurora_code_loop.py  (367 L)
aurora_code_remote.py  (323 L)
aurora_code_validators.py  (360 L)
bridge_agentic_stream.py  (394 L)
cdp_client.mjs  (151 L)
cdp_drive.mjs  (303 L)
cdp_scenarios.mjs  (154 L)
code_apk_package.py  (207 L)
code_loop_cli.py  (102 L)
code_loop_files.py  (137 L)
code_loop_runtime.py  (194 L)
code_loop_state.json  (144 L)
code_loop_state.py  (17 L)
execution_android.py  (340 L)
execution_android_app.py  (123 L)
execution_android_profiles.py  (19 L)
execution_embedded.py  (319 L)
execution_lab.py  (287 L)
execution_tooling.py  (140 L)
intermodule_3d_quality.py  (288 L)
intermodule_asset_reuse.py  (110 L)
intermodule_assets.py  (352 L)
intermodule_rag.py  (192 L)
model_ab_coder.py  (113 L)
model_ab_complex.py  (118 L)
model_ab_test.py  (96 L)
model_bench_hard.py  (177 L)
playwright_execute.mjs  (95 L)
queue_pages.json  (14 L)
queue_pages_v2.json  (14 L)
queue_retry_v2_failed.json  (4 L)
test_bridge_agentic_stream.py  (63 L)
test_code_loop_files.py  (35 L)
test_intermodule_assets.py  (235 L)
test_simulation_environments.py  (94 L)
tooling_eval.py  (278 L)
ui_capture.mjs  (69 L)
ui_generate_capture.mjs  (110 L)
visual_render_audit.py  (141 L)
```

</details>

<details><summary>AuroraIA/application/python-services/aurora_hunyuan — 17 fichiers</summary>

```text
aurora_animate.py  (659 L)
aurora_architect.py  (69 L)
aurora_classify.py  (307 L)
aurora_critic.py  (258 L)
aurora_hunyuan_wrapper.py  (352 L)
aurora_loop.py  (297 L)
aurora_loop_robust.py  (193 L)
aurora_rebake.py  (154 L)
aurora_rerender.py  (138 L)
aurora_scene_builder.py  (85 L)
aurora_state.json  (392 L)
aurora_trellis_wrapper.py  (596 L)
aurora_vision_research.py  (150 L)
blender_mesh_auditor.py  (69 L)
blender_mesh_repair.py  (61 L)
pipeline_hunyuan_realistic.py  (474 L)
pipeline_hunyuan_robust.py  (229 L)
```

</details>

<details><summary>AuroraIA/application/python-services/aurora_uplift — 1 fichiers</summary>

```text
aurora_module_uplift.py  (326 L)
```

</details>

<details><summary>AuroraIA/application/python-services/cyber — 7 fichiers</summary>

```text
__init__.py  (1 L)
_safety.py  (189 L)
forensics_ops.py  (253 L)
network_ops.py  (318 L)
password_ops.py  (127 L)
stego_ops.py  (286 L)
test_safety.py  (63 L)
```

</details>

<details><summary>AuroraIA/application/python-services/reference_profiles — 4 fichiers</summary>

```text
lincoln_smithsonian_head_document.json  (1123 L)
lincoln_volk_hands_document.json  (661 L)
lincoln_volk_life_mask_document.json  (1072 L)
strimer_plus_v2.json  (78 L)
```

</details>

<details><summary>AuroraIA/application/python-services/storage — 4 fichiers</summary>

```text
__init__.py  (2 L)
aurora_storage.py  (563 L)
setup_key.py  (191 L)
test_aurora_storage.py  (156 L)
```

</details>

<details><summary>AuroraIA/application/routes — 26 fichiers</summary>

```text
asset_bp_routes.py  (179 L)
cinema_bp_routes.py  (2422 L)
cli_bp_routes.py  (1292 L)
comfy_life_bp_routes.py  (63 L)
comfy_proxy_bp_routes.py  (24 L)
connect_bp_routes.py  (317 L)
cowork_ext_bp_routes.py  (5020 L)
cowork_file_bp_routes.py  (325 L)
ext_bp_routes.py  (17 L)
fs_bp_routes.py  (104 L)
hardware_bp_routes.py  (91 L)
iot_bp_routes.py  (161 L)
ollama_enh_bp_routes.py  (63 L)
ollama_list_bp_routes.py  (21 L)
postgres_bp_routes.py  (45 L)
python_bp_routes.py  (1318 L)
python_prog_bp_routes.py  (101 L)
repo_bp_routes.py  (341 L)
s3_bp_routes.py  (68 L)
status_bp_routes.py  (28 L)
sysinfo_bp_routes.py  (51 L)
upload_bp_routes.py  (40 L)
vite_bp_routes.py  (3226 L)
voice_bp_routes.py  (956 L)
web_action_bp_routes.py  (44 L)
web_search_bp_routes.py  (770 L)
```

</details>

<details><summary>AuroraIA/application/scripts — 19 fichiers</summary>

```text
apercu_glb_three.mjs  (107 L)
conformance.mjs  (59 L)
conformanceMesures.mjs  (911 L)
conformance_mesures.py  (166 L)
expertise-artefacts.py  (413 L)
expertise-livrables.mjs  (308 L)
free-dev-port.mjs  (123 L)
garde-architecture.py  (232 L)
image_cli.mjs  (849 L)
prompts-humains.json  (110 L)
reparer-livrables.mjs  (154 L)
route_test.mjs  (57 L)
run_manual_caine.sh  (7 L)
start-cloud.mjs  (21 L)
verify-explanation.mjs  (52 L)
```

</details>

<details><summary>AuroraIA/application/scripts/code_harness — 34 fichiers</summary>

```text
_chk3.mjs  (9 L)
_chk4.mjs  (8 L)
_promptchk.mjs  (14 L)
acceptance_behaviour.mjs  (286 L)
aesthetic_capture.mjs  (221 L)
bridge_ndjson_runner.mjs  (562 L)
capability_probe.mjs  (379 L)
final_heavy_validation.sh  (134 L)
final_screenshot_pixel_audit.mjs  (90 L)
final_tsc_scope_check.mjs  (52 L)
final_visual_proof.mjs  (310 L)
gatecheck.mjs  (15 L)
gatecheck1.mjs  (15 L)
harness_env.mjs  (92 L)
hooks.mjs  (44 L)
integrity_check.mjs  (30 L)
integrity_check2.mjs  (16 L)
intent.mjs  (39 L)
loadcheck.mjs  (41 L)
loopdbg.mjs  (13 L)
orphan_scan.mjs  (274 L)
parsetest.mjs  (42 L)
project_build.mjs  (250 L)
react_key_probe.ts  (19 L)
render_audit.mjs  (487 L)
run.mjs  (200 L)
runner_single_instance.mjs  (114 L)
stack_resolve.mjs  (101 L)
verify_bridge_parity.py  (155 L)
viewer.mjs  (59 L)
viewer_publish.mjs  (291 L)
ws15_asset_export_proof.ts  (89 L)
ws7_isolation_proof.mjs  (164 L)
```

</details>

<details><summary>AuroraIA/application/src — 3 fichiers</summary>

```text
App.tsx  (1513 L)
main.tsx  (115 L)
vite-env.d.ts  (8 L)
```

</details>

<details><summary>AuroraIA/application/src-tauri — 3 fichiers</summary>

```text
Cargo.toml  (39 L)
build.rs  (3 L)
tauri.conf.json  (92 L)
```

</details>

<details><summary>AuroraIA/application/src-tauri/.cargo — 1 fichiers</summary>

```text
config.toml  (2 L)
```

</details>

<details><summary>AuroraIA/application/src-tauri/capabilities — 1 fichiers</summary>

```text
main.json  (67 L)
```

</details>

<details><summary>AuroraIA/application/src-tauri/src — 3 fichiers</summary>

```text
commands.rs  (3121 L)
lib.rs  (169 L)
main.rs  (5 L)
```

</details>

<details><summary>AuroraIA/application/src/__tests__ — 3 fichiers</summary>

```text
comfyJobMonitor.test.ts  (84 L)
drawingExplanation.test.ts  (129 L)
imageGenerationSafety.test.ts  (29 L)
```

</details>

<details><summary>AuroraIA/application/src/components — 82 fichiers</summary>

```text
AcademyFlashcards.tsx  (252 L)
AcademyMindMap.tsx  (84 L)
AcademyTable.tsx  (106 L)
AchievementsPanel.tsx  (1004 L)
ApiEmbedPanel.tsx  (144 L)
AppErrorBoundary.tsx  (116 L)
AppShell.tsx  (328 L)
AskAboutContentBox.tsx  (145 L)
AuroraAgentMascot.tsx  (356 L)
AuroraAgentScene.tsx  (493 L)
AuroraAgentSettingsPanel.tsx  (210 L)
AuroraAmbientField.tsx  (174 L)
AuroraAvatar.tsx  (1583 L)
AuroraCommandPalette.tsx  (358 L)
AuroraSphereV1.tsx  (377 L)
AuroraV1AppShell.tsx  (380 L)
AuroraV1MobileShell.tsx  (392 L)
AuroraV3MobileShell.tsx  (359 L)
AuroraV4AppShell.tsx  (286 L)
AvatarLive2D.tsx  (441 L)
AvatarSelectorModal.tsx  (136 L)
AvatarTalkingVideo.tsx  (115 L)
ClarificationDialog.tsx  (175 L)
CodeBlock.tsx  (137 L)
CodeCorrectionLog.tsx  (234 L)
CodeFileTree.tsx  (169 L)
CodeMirrorViewer.tsx  (203 L)
CodeProjectPreview.tsx  (328 L)
CommandPalette.tsx  (337 L)
ConnectionIndicator.tsx  (283 L)
ConnectorRecommendationsPanel.tsx  (176 L)
ContextFilesField.tsx  (109 L)
CoworkConfirmDialog.tsx  (136 L)
CoworkExtractionStatsTile.tsx  (332 L)
CoworkOverlay.tsx  (4442 L)
CoworkSettingsDialog.tsx  (753 L)
CyberWeeklyChallenges.tsx  (131 L)
DeckMindMap.tsx  (249 L)
EntDashboard.tsx  (534 L)
ExamBlancPanel.tsx  (319 L)
FavoriteButton.tsx  (121 L)
FloatingShell.tsx  (485 L)
GeneratedDownloads.tsx  (158 L)
GlobalSearch.tsx  (192 L)
HelpFab.tsx  (40 L)
InpaintingPanel.tsx  (231 L)
KeyboardCheatsheet.tsx  (225 L)
LeitnerReviewPanel.tsx  (118 L)
LivePreviewFrame.tsx  (94 L)
MachineConnectionsPanel.tsx  (257 L)
MarkdownPro.tsx  (185 L)
MissionControlRail.tsx  (280 L)
MobileGrimoire.tsx  (1202 L)
ModuleAssetPackCard.tsx  (120 L)
ModuleErrorBoundary.tsx  (101 L)
PomodoroTimer.tsx  (145 L)
PrivilegeBootstrapDialog.tsx  (113 L)
ProgressStats.tsx  (98 L)
PromptLibraryPanel.tsx  (194 L)
RecoveryBanner.tsx  (94 L)
ReferenceInspectorPanel.tsx  (223 L)
RigEditor.tsx  (118 L)
RigPlayer.tsx  (272 L)
SaveDialog.tsx  (173 L)
ScrollToTop.tsx  (75 L)
SessionSwitcher.tsx  (167 L)
SettingsPanel.tsx  (3201 L)
Sidebar.tsx  (117 L)
SkinSafeView.tsx  (142 L)
Sparkline.tsx  (133 L)
SpatialCanvas.tsx  (948 L)
StudioHero.tsx  (109 L)
SubjectSelectPanel.tsx  (135 L)
TextPreviewExpander.tsx  (899 L)
ThreeDProgressOverlay.tsx  (228 L)
TitleBar.tsx  (194 L)
ToastContainer.tsx  (50 L)
VoiceLiveChat.tsx  (143 L)
VoicePushToTalk.tsx  (108 L)
VoiceQuickToggle.tsx  (158 L)
WeeklyChallenges.tsx  (162 L)
codeProjectPreviewHtml.ts  (122 L)
```

</details>

<details><summary>AuroraIA/application/src/components/chat — 3 fichiers</summary>

```text
InlineModelViewer.tsx  (230 L)
MediaEmbed.tsx  (504 L)
SourcesPanel.tsx  (239 L)
```

</details>

<details><summary>AuroraIA/application/src/components/generationFx — 6 fichiers</summary>

```text
GenerationFxHost.tsx  (885 L)
comfyProgress.ts  (32 L)
fxBus.ts  (120 L)
mascots.tsx  (422 L)
scenes.ts  (1256 L)
voiceCharacter.tsx  (278 L)
```

</details>

<details><summary>AuroraIA/application/src/components/learning — 2 fichiers</summary>

```text
TutorialRunner.tsx  (411 L)
TutorialsPanel.tsx  (187 L)
```

</details>

<details><summary>AuroraIA/application/src/components/learning/sim — 1 fichiers</summary>

```text
Molecule3D.tsx  (233 L)
```

</details>

<details><summary>AuroraIA/application/src/components/studio — 4 fichiers</summary>

```text
FightCloudBadge.tsx  (71 L)
Roster.tsx  (141 L)
SidebarPersona.tsx  (42 L)
avatars.tsx  (1323 L)
```

</details>

<details><summary>AuroraIA/application/src/components/voice — 5 fichiers</summary>

```text
LyraCharacter.tsx  (479 L)
MusicStudio.tsx  (357 L)
VoiceLandscape.tsx  (179 L)
VoiceReplicationStudio.tsx  (1634 L)
VoiceStage.tsx  (697 L)
```

</details>

<details><summary>AuroraIA/application/src/config — 2 fichiers</summary>

```text
models.ts  (544 L)
moduleAssetPacks.ts  (377 L)
```

</details>

<details><summary>AuroraIA/application/src/hooks — 23 fichiers</summary>

```text
useAbortableGeneration.ts  (70 L)
useAcademyViewLogic.ts  (2209 L)
useAchievementToasts.ts  (126 L)
useCameraLive.ts  (407 L)
useChatViewLogic.ts  (438 L)
useCodeViewLogic.ts  (192 L)
useCoworkLiveCounters.ts  (89 L)
useCyberViewLogic.ts  (1216 L)
useDrawingViewLogic.ts  (792 L)
useFileDrop.ts  (84 L)
useGenerationRecovery.ts  (182 L)
useImageViewLogic.ts  (1046 L)
useIsMobile.ts  (31 L)
useLinuxRuntimeFirstRun.ts  (33 L)
useManagedRuntime.ts  (335 L)
useModelViewLogic.ts  (130 L)
useModuleAssetPack.ts  (473 L)
useModuleStreak.ts  (34 L)
useRealAgents.ts  (47 L)
useRuntimeTelemetry.ts  (85 L)
useStudioDiagnostics.ts  (214 L)
useTauri.ts  (1868 L)
useVoiceLive.ts  (855 L)
```

</details>

<details><summary>AuroraIA/application/src/services — 347 fichiers</summary>

```text
academicContentVerification.ts  (201 L)
achievements.ts  (969 L)
auroraAgents.ts  (484 L)
auroraExpertPrompts.ts  (330 L)
auroraExtensionBridge.ts  (498 L)
auroraOutputPaths.ts  (133 L)
auroraVoice.ts  (570 L)
bacResources.ts  (133 L)
blenderBridge.ts  (297 L)
characterForge.ts  (601 L)
codeAcceptanceCriteria.ts  (203 L)
codeAccessibilityGate.ts  (178 L)
codeAgenticGenerationPhase.ts  (176 L)
codeApostropheRepair.ts  (105 L)
codeArchitecturePlan.ts  (348 L)
codeArchitecturePlanContract.ts  (71 L)
codeArchitecturePlanEntryContract.ts  (134 L)
codeArchitecturePlanFallback.ts  (178 L)
codeArchitecturePlanInstructions.ts  (66 L)
codeArchitecturePlanSelection.ts  (85 L)
codeArrayContainerAccess.ts  (126 L)
codeArtifactRedaction.ts  (98 L)
codeAutoCorrection.ts  (398 L)
codeBestDeliverySelection.ts  (149 L)
codeBinaryAssetPaths.ts  (69 L)
codeBriefPalette.ts  (176 L)
codeBrowserWorkspaceRuntime.ts  (381 L)
codeCodegenDependencies.ts  (214 L)
codeColorMetrics.ts  (126 L)
codeCommandStderr.ts  (104 L)
codeCompositionAttribution.ts  (100 L)
codeCompositionGate.ts  (343 L)
codeCorrectionBudget.ts  (44 L)
codeCorrectionContextGathering.ts  (119 L)
codeCorrectionCycle.ts  (124 L)
codeCorrectionErrorPatterns.ts  (94 L)
codeCorrectionInstructions.ts  (76 L)
codeCorrectionLog.ts  (38 L)
codeCorrectionMessages.ts  (191 L)
codeCorrectionPromptBudget.ts  (119 L)
codeCorrectionQualityGates.ts  (143 L)
codeCorrectionRegressionFeedback.ts  (113 L)
codeDanglingBinaryAssets.ts  (139 L)
codeDesignDirectiveBlocks.ts  (316 L)
codeDesignDirectiveLibraries.ts  (19 L)
codeDesignDirectives.ts  (224 L)
codeDesignMarketingArchetypes.ts  (231 L)
codeDesignPolishGate.ts  (107 L)
codeDesignReference.ts  (117 L)
codeDesignReferenceHtml.ts  (398 L)
codeDesignReferenceSubjects.ts  (331 L)
codeDesignReferenceThree.ts  (153 L)
codeDesignResearch.ts  (169 L)
codeDesignResearchCatalog.ts  (302 L)
codeDesignSpec.ts  (244 L)
codeDesignSpecializedBlocks.ts  (47 L)
codeDesignTokenGate.ts  (189 L)
codeDevServer.ts  (300 L)
codeDevServerCommand.ts  (129 L)
codeEscapedNewlines.ts  (59 L)
codeExecutorQualityContract.ts  (262 L)
codeFidelityGate.ts  (229 L)
codeFileExtensionCoherence.ts  (210 L)
codeFileStateCapture.ts  (30 L)
codeFileTreeModel.ts  (193 L)
codeFollowUpAnalysis.ts  (308 L)
codeFollowUpPreparation.ts  (82 L)
codeFormattingArtifacts.ts  (177 L)
codeGeneratedDependencyPolicy.ts  (37 L)
codeGeneratedFileParser.ts  (316 L)
codeGeneratedFileSanitizer.ts  (317 L)
codeGeneratedTypeScriptRepair.ts  (65 L)
codeGenerationActionProducer.ts  (308 L)
codeGenerationActionProtocol.ts  (225 L)
codeGenerationActionSalvage.ts  (180 L)
codeGenerationCommandRunner.ts  (127 L)
codeGenerationDiagnostics.ts  (70 L)
codeGenerationExecutor.ts  (239 L)
codeGenerationOutputRetry.ts  (339 L)
codeGenerationQueue.ts  (214 L)
codeGenerationTools.ts  (129 L)
codeHtmlAssetRepair.ts  (36 L)
codeImportExportShape.ts  (380 L)
codeIncrementalPatchScope.ts  (81 L)
codeInfrastructureFailure.ts  (228 L)
codeInitialAgenticGeneration.ts  (94 L)
codeIntent.ts  (21 L)
codeIntentArchitecturePrompt.ts  (56 L)
codeIntentAssetTokens.ts  (123 L)
codeIntentAssets.ts  (68 L)
codeIntentBrandProfiles.ts  (20 L)
codeIntentBrandProfilesA.ts  (369 L)
codeIntentBrandProfilesB.ts  (382 L)
codeIntentClassification.ts  (399 L)
codeIntentCommands.ts  (164 L)
codeIntentComplexity.ts  (56 L)
codeIntentFileCount.ts  (63 L)
codeIntentFinalization.ts  (135 L)
codeIntentFollowup.ts  (82 L)
codeIntentGameCatalog.ts  (260 L)
codeIntentIncrementReuse.ts  (61 L)
codeIntentLanguage.ts  (33 L)
codeIntentPlatformHeuristics.ts  (65 L)
codeIntentSemanticSignals.ts  (90 L)
codeIntentSignalUtils.ts  (30 L)
codeIntentSignals.ts  (218 L)
codeIntentSubject.ts  (111 L)
codeIntentTypes.ts  (213 L)
codeInterModuleAssetIntegration.ts  (146 L)
codeInterModuleAssets.ts  (368 L)
codeInteractive3DGate.ts  (71 L)
codeInterruptedDelivery.ts  (85 L)
codeLLMRefusal.ts  (67 L)
codeLauncherPromptContract.ts  (50 L)
codeLexicalAnalysis.ts  (211 L)
codeLivePreviewPolicy.ts  (15 L)
codeManifestVersion.ts  (41 L)
codeMissingModuleCompletion.ts  (248 L)
codeMissingRouterProvider.ts  (142 L)
codeMissingTypeImport.ts  (162 L)
codeMissionControl.ts  (323 L)
codeMissionReview.ts  (376 L)
codeMissionShared.ts  (124 L)
codeModelResidency.ts  (80 L)
codeModelRouting.ts  (230 L)
codeMultiPassCritique.ts  (113 L)
codeNpmDiagnostics.ts  (128 L)
codeOrchestrator.ts  (371 L)
codeOrchestratorReexports.ts  (29 L)
codeOrchestratorTypes.ts  (71 L)
codeOutputFiles.ts  (333 L)
codeOutputImageRepair.ts  (111 L)
codeOutputIntelligent.ts  (325 L)
codePatchMatching.ts  (114 L)
codePerformanceGate.ts  (161 L)
codePipelineFinalization.ts  (130 L)
codePipelinePhases.ts  (260 L)
codePipelinePreparation.ts  (164 L)
codePipelineRuntime.ts  (63 L)
codePreflight.ts  (326 L)
codePreflightProbe.ts  (199 L)
codeProjectEmission.ts  (393 L)
codeProjectGeneratorRegistry.ts  (105 L)
codeProjectImportGraph.ts  (122 L)
codeProjectMemory.ts  (217 L)
codeProjectMemoryPersistence.ts  (93 L)
codeProjectReadme.ts  (199 L)
codeProjectReadmeInventory.ts  (302 L)
codeProjectReadmeRunbook.ts  (245 L)
codeProjectScaffoldFiles.ts  (150 L)
codeProjectSupportFiles.ts  (361 L)
codeProjectTailwindSupport.ts  (151 L)
codeProjectTree.ts  (351 L)
codeProjectTypeStackContract.ts  (149 L)
codeProjectValidation.ts  (399 L)
codeProjectWriter.ts  (202 L)
codePromptHints.ts  (138 L)
codeProtocolLeakGuard.ts  (141 L)
codePythonEnvironment.ts  (9 L)
codeQualityGates.ts  (358 L)
codeReasoningEngine.ts  (191 L)
codeRegressionGuard.ts  (384 L)
codeRenderCausalOrder.ts  (109 L)
codeRenderedAestheticScore.ts  (236 L)
codeResearch.ts  (301 L)
codeRuntimeDependencies.ts  (29 L)
codeSandbox.ts  (365 L)
codeSandboxCacheVolume.ts  (95 L)
codeSandboxCommands.ts  (327 L)
codeSandboxEmptyTestSuite.ts  (91 L)
codeSandboxFiles.ts  (378 L)
codeSandboxGc.ts  (103 L)
codeSandboxGpu.ts  (137 L)
codeSandboxIsolation.ts  (394 L)
codeSandboxIsolationProbes.ts  (260 L)
codeSandboxLaunchRuntime.ts  (70 L)
codeSandboxNetworkPolicy.ts  (128 L)
codeSandboxRegistryRepair.ts  (336 L)
codeSandboxRuntime.ts  (17 L)
codeSandboxSilentStep.ts  (162 L)
codeSandboxToolchains.ts  (64 L)
codeSandboxTypes.ts  (48 L)
codeSandboxWorkspace.ts  (145 L)
codeSecretRemediation.ts  (59 L)
codeSemanticIntentClassifier.ts  (173 L)
codeSemanticIntentGuard.ts  (158 L)
codeSimulationLab.ts  (149 L)
codeStarterTemplates.ts  (392 L)
codeStaticAccessibility.ts  (66 L)
codeStaticCompleteness.ts  (111 L)
codeStaticComplexity.ts  (53 L)
codeStaticCriticShared.ts  (37 L)
codeStaticCritics.ts  (50 L)
codeStaticProjectIntegrity.ts  (304 L)
codeStaticSecurity.ts  (160 L)
codeStaticSecurityRules.ts  (284 L)
codeStaticStructure.ts  (93 L)
codeStaticSyntax.ts  (139 L)
codeStreamEvents.ts  (350 L)
codeStructuralAnalysis.ts  (274 L)
codeStructuralMetrics.ts  (161 L)
codeStyleConstraints.ts  (98 L)
codeSubjectAssets.ts  (80 L)
codeSubjectPromptContract.ts  (105 L)
codeSystemPromptContracts.ts  (398 L)
codeSystemPromptProductShapes.ts  (199 L)
codeSystemPrompts.ts  (189 L)
codeTailwindSignals.ts  (46 L)
codeTailwindToolchainContract.ts  (192 L)
codeTailwindUsage.ts  (98 L)
codeTargetedRepairPass.ts  (220 L)
codeTargetedRepairScope.ts  (230 L)
codeTestToolchainContract.ts  (171 L)
codeToolchainDiagnostics.ts  (111 L)
codeToolingLoop.ts  (254 L)
codeTransitiveClosure.ts  (243 L)
codeTransportBackoff.ts  (38 L)
codeTreeSitterAst.ts  (234 L)
codeTsConfigPolicy.ts  (42 L)
codeValidationCorrectionLoop.ts  (369 L)
codeValidationScoring.ts  (170 L)
codeViewerAssets.ts  (50 L)
codeViewerHtml.ts  (181 L)
codeViewerIndex.ts  (335 L)
codeVisualAuditClient.ts  (132 L)
codeVisualCorrectionDecision.ts  (73 L)
codeVisualFallbacks.ts  (40 L)
codeVisualFidelity.ts  (390 L)
codeVisualFidelityCritique.ts  (46 L)
codeVisualFidelityDetectors.ts  (101 L)
codeVisualFidelityProfiles.ts  (121 L)
codeVisualRenderAudit.ts  (246 L)
codeVisualSurfaces.ts  (36 L)
codeWebResearchClient.ts  (69 L)
comfyJobMonitor.ts  (102 L)
compoundScene.ts  (136 L)
conversationMemory.ts  (278 L)
conversationOrchestrator.ts  (785 L)
conversationSentiment.ts  (295 L)
conversationToneMatcher.ts  (186 L)
conversationVerification.ts  (55 L)
coworkActionSequenceAuditor.ts  (301 L)
coworkAudit.ts  (239 L)
coworkBrowserDetect.ts  (62 L)
coworkBrowserDetectPure.ts  (148 L)
coworkClarification.ts  (110 L)
coworkConnectorPill.ts  (93 L)
coworkConnectorPin.ts  (432 L)
coworkConnectors.ts  (3887 L)
coworkContentDigest.ts  (251 L)
coworkConversation.ts  (209 L)
coworkExecutor.ts  (980 L)
coworkExtractionStats.ts  (557 L)
coworkMission.ts  (296 L)
coworkOrchestrator.ts  (818 L)
coworkPipeline.ts  (250 L)
coworkPlanDependencyAnalyzer.ts  (246 L)
coworkPlanEstimator.ts  (410 L)
coworkPlanParser.ts  (1396 L)
coworkPlanRollback.ts  (166 L)
coworkPlanner.ts  (3821 L)
coworkPlannerCtxEnricher.ts  (259 L)
coworkProjectThread.ts  (696 L)
coworkSafety.ts  (585 L)
coworkSessionStore.ts  (192 L)
coworkSettings.ts  (405 L)
coworkTypes.ts  (173 L)
deckMindMap.ts  (220 L)
drawingAutoLayout.ts  (336 L)
drawingColorTools.ts  (268 L)
drawingCurveSmoothing.ts  (159 L)
drawingExplanation.ts  (166 L)
drawingStyleAndSvg.ts  (320 L)
entAdapters.ts  (259 L)
entCredentialBridge.ts  (391 L)
entDocParser.ts  (142 L)
entEvalDetector.ts  (165 L)
entHarvestService.ts  (111 L)
entNotesAnalysis.ts  (138 L)
entNotifScheduler.ts  (160 L)
entRevisionBuilder.ts  (208 L)
ephemeralToolRunner.ts  (89 L)
flashcardVerification.ts  (291 L)
generationContract.ts  (409 L)
humanPromptDirector.ts  (497 L)
humanoidAnatomy.ts  (120 L)
imageAspectRecommender.ts  (235 L)
imageCompositionRules.ts  (184 L)
imageConversationContract.ts  (195 L)
imageGenerationSafety.ts  (69 L)
imagePromptBuilder.ts  (708 L)
imagePromptDiff.ts  (176 L)
imageVariationPicker.ts  (200 L)
intentRouter.ts  (442 L)
kinematicsLibrary.ts  (1214 L)
labAssistant.ts  (180 L)
learningResearch.ts  (571 L)
learningSemanticEval.ts  (297 L)
llmTimebox.ts  (47 L)
machineConnectors.ts  (187 L)
meshPostprocess.ts  (198 L)
meshRescue.ts  (740 L)
modelJson.ts  (73 L)
moduleConnectorRecommendations.ts  (625 L)
moduleCoordinator.ts  (54 L)
moduleFileExchange.ts  (160 L)
modulePipelineStages.ts  (516 L)
moduleProgressTracker.ts  (292 L)
motionPipeline.ts  (187 L)
motionSerializer.ts  (122 L)
musicStudio.ts  (108 L)
ollamaFirstByteWatchdog.ts  (154 L)
ollamaResilience.ts  (928 L)
ollamaStream.ts  (46 L)
oralModeClassifier.ts  (357 L)
pbrProfile.ts  (157 L)
pythonJobClient.ts  (220 L)
realityAnalyzer.ts  (285 L)
referenceVisualResearch.ts  (592 L)
responseCache.ts  (156 L)
saveSystem.ts  (345 L)
selfInformedReference.ts  (761 L)
sessionAutoNaming.ts  (114 L)
sessionTempStorage.ts  (113 L)
sharedMemory.ts  (97 L)
subjectAnatomy.ts  (424 L)
taskIntelligence.ts  (646 L)
threeDBoundsAndCulling.ts  (216 L)
threeDClarification.ts  (298 L)
threeDGltfValidator.ts  (353 L)
threeDIntent.ts  (2611 L)
threeDLodAndRig.ts  (258 L)
threeDMotionIntent.ts  (557 L)
threeDReferenceSupport.ts  (458 L)
threeDRigRetarget.ts  (237 L)
threeDTextureAtlas.ts  (238 L)
threeDViewPlanner.ts  (1180 L)
treeAlgorithmEngine.ts  (183 L)
visionService.ts  (675 L)
visualReferenceAnalyzer.ts  (435 L)
voiceExamMode.ts  (781 L)
voiceFrPhonemizer.ts  (618 L)
voicePhonemes.ts  (280 L)
voiceProsody.ts  (221 L)
voiceStudioApi.ts  (288 L)
webActionAgent.ts  (149 L)
webResearch.ts  (535 L)
```

</details>

<details><summary>AuroraIA/application/src/services/cyber — 45 fichiers</summary>

```text
advancedNetworkEngine.ts  (155 L)
advisory.ts  (39 L)
attackGraphEngine.ts  (193 L)
autonomousInvestigator.ts  (262 L)
autonomousToolEngine.ts  (365 L)
autonomousWarRoom.ts  (328 L)
binaryAnalysisEngine.ts  (146 L)
binarySecurityAuditor.ts  (160 L)
breachChecker.ts  (153 L)
builtinLabs.ts  (169 L)
cisaKevSyncEngine.ts  (149 L)
classicalCipherAnalysis.ts  (364 L)
closedLoopPatchEngine.ts  (271 L)
cognitiveFuzzingEngine.ts  (233 L)
cryptoService.ts  (360 L)
cryptoVulnerabilities.ts  (220 L)
ctfStore.ts  (77 L)
cyberDeepReasoning.ts  (178 L)
cyberOutputManager.ts  (109 L)
dynamicAttackGraphOrchestrator.ts  (176 L)
dynamicHoneytokenEngine.ts  (132 L)
dynamicZeroDayEngine.ts  (214 L)
ebpfKernelEngine.ts  (127 L)
exploitPatchVerifier.ts  (128 L)
forensicsTools.ts  (231 L)
hashParameterParser.ts  (162 L)
hashService.ts  (182 L)
iocParser.ts  (179 L)
jwtForger.ts  (144 L)
jwtInspector.ts  (187 L)
kdfCostAnalyzer.ts  (232 L)
multiAgentWarRoomOrchestrator.ts  (165 L)
passwordAnalyzer.ts  (158 L)
postQuantumCryptoAudit.ts  (131 L)
pythonClient.ts  (136 L)
rainbowTableDemo.ts  (177 L)
sessionStateManager.ts  (134 L)
soarPlaybookEngine.ts  (124 L)
sqlInjectionSandbox.ts  (152 L)
symbolicExecutionEngine.ts  (155 L)
tlsCertInspector.ts  (346 L)
webEndpointAuditor.ts  (271 L)
wifiHandshakeSim.ts  (155 L)
zeroDayDiscoveryEngine.ts  (145 L)
zeroDayEngine.ts  (317 L)
```

</details>

<details><summary>AuroraIA/application/src/services/learning — 13 fichiers</summary>

```text
academicFormalEngine.ts  (220 L)
bacInspirationDb.ts  (201 L)
bacOfficialSearch.ts  (105 L)
bacSti2dCurriculum.ts  (345 L)
curriculumGraphSvg.ts  (86 L)
exerciseFormats.ts  (357 L)
fsrsLeitnerBridge.ts  (96 L)
knowledgeGraphBuilder.ts  (254 L)
mnemonicGenerator.ts  (202 L)
multiDocAnalyzer.ts  (270 L)
reviewQueueOptimizer.ts  (185 L)
spacedRepetition.ts  (322 L)
tutorialEngine.ts  (152 L)
```

</details>

<details><summary>AuroraIA/application/src/services/learning/tutorials — 1 fichiers</summary>

```text
physicsTutorials.ts  (333 L)
```

</details>

<details><summary>AuroraIA/application/src/services/simulator — 16 fichiers</summary>

```text
analyticIntegrators.ts  (244 L)
analyticPhenomena.ts  (673 L)
analyticSession.ts  (217 L)
chemistryReactions.ts  (154 L)
dataRecorder.ts  (237 L)
defaults.ts  (255 L)
fluidSolver.ts  (210 L)
particleSystem.ts  (177 L)
phasePortrait.ts  (200 L)
phenomena.ts  (314 L)
physicsEngine.ts  (373 L)
presets.ts  (75 L)
sceneIO.ts  (56 L)
sceneStore.ts  (638 L)
seededRandom.ts  (87 L)
types.ts  (322 L)
```

</details>

<details><summary>AuroraIA/application/src/stores — 33 fichiers</summary>

```text
academyLeaderboardStore.ts  (64 L)
academyStore.ts  (282 L)
agentRuntimeStore.ts  (241 L)
appStore.ts  (583 L)
bacSti2dSinSeed.ts  (1052 L)
calendarStore.ts  (98 L)
chatStore.ts  (277 L)
codeStreamCoreActions.ts  (120 L)
codeStreamEventLog.ts  (91 L)
codeStreamNarration.ts  (68 L)
codeStreamPreflight.ts  (38 L)
codeStreamProgress.ts  (43 L)
codeStreamRepoActions.ts  (154 L)
codeStreamRouting.ts  (69 L)
codeStreamSessions.ts  (70 L)
codeStreamStore.ts  (358 L)
codeStreamTypes.ts  (136 L)
codeWorkspaceStore.ts  (147 L)
coworkStore.ts  (104 L)
cyberLeaderboardStore.ts  (87 L)
entSessionStore.ts  (81 L)
flashcardsStore.ts  (254 L)
forgeQueueStore.ts  (212 L)
gamificationStore.ts  (106 L)
generationTrackerStore.ts  (176 L)
learningSessionStore.ts  (213 L)
lessonProgressStore.ts  (134 L)
moduleDraftsStore.ts  (77 L)
moduleHistoryStore.ts  (326 L)
moduleLogStore.ts  (45 L)
notificationStore.ts  (32 L)
promptLibraryStore.ts  (91 L)
tutorialStore.ts  (141 L)
```

</details>

<details><summary>AuroraIA/application/src/styles — 6 fichiers</summary>

```text
aurora-skin.css  (455 L)
aurora-v3-code.css  (103 L)
aurora-v4.css  (1851 L)
globals.css  (3397 L)
grimoire.css  (875 L)
manga-theme.css  (13292 L)
```

</details>

<details><summary>AuroraIA/application/src/types — 1 fichiers</summary>

```text
app.ts  (404 L)
```

</details>

<details><summary>AuroraIA/application/src/utils — 52 fichiers</summary>

```text
announceText.ts  (133 L)
backup.ts  (90 L)
blobStore.ts  (115 L)
buildRecovery.ts  (106 L)
coalesceTracker.ts  (47 L)
codeDownload.ts  (71 L)
comfyui.ts  (271 L)
dailyTip.ts  (109 L)
device.ts  (178 L)
docxExtract.ts  (16 L)
errors.ts  (120 L)
exportAnki.ts  (166 L)
exportForgeBundle.ts  (104 L)
exportPdf.ts  (153 L)
fluxKontextWorkflow.ts  (1071 L)
fluxWorkflow.ts  (881 L)
gameDetection.ts  (230 L)
imageDownload.ts  (338 L)
imagePromptParser.ts  (514 L)
kontextInstructionTranslator.ts  (395 L)
mediaLinks.ts  (212 L)
mobileDownload.ts  (91 L)
modelContext.ts  (56 L)
multimodalContext.ts  (277 L)
namedEntityEnrichment.ts  (200 L)
notificationBus.ts  (187 L)
outputScanner.ts  (91 L)
pdfExtract.ts  (77 L)
pixelArtEnforcer.ts  (252 L)
promptHistory.ts  (67 L)
quickNav.ts  (71 L)
randomChatStarters.ts  (26 L)
randomCreativePrompts.ts  (111 L)
referenceMedia.ts  (80 L)
runtime.ts  (131 L)
serviceTransitions.ts  (55 L)
simpleDiff.ts  (59 L)
slashCommands.ts  (163 L)
speakify.ts  (389 L)
streak.ts  (61 L)
subjectDetection.ts  (59 L)
tabLifecycle.ts  (84 L)
textCleaner.ts  (257 L)
textFileExtract.ts  (77 L)
theme.ts  (42 L)
titleInference.ts  (38 L)
uiSkin.ts  (89 L)
uiSkinViews.ts  (17 L)
upscaleImage.ts  (105 L)
voiceCommands.ts  (76 L)
voiceCommandsCore.ts  (48 L)
voiceSummary.ts  (24 L)
```

</details>

<details><summary>AuroraIA/application/src/views — 72 fichiers</summary>

```text
AuroraCoworkView.tsx  (1701 L)
AuroraV13DView.tsx  (605 L)
AuroraV1AcademyMobile.tsx  (434 L)
AuroraV1AcademyView.tsx  (1752 L)
AuroraV1ChatView.tsx  (1085 L)
AuroraV1CodeView.tsx  (393 L)
AuroraV1CoworkView.tsx  (564 L)
AuroraV1CyberView.tsx  (1334 L)
AuroraV1DrawingView.tsx  (621 L)
AuroraV1ImageView.tsx  (941 L)
AuroraV1VoiceView.tsx  (220 L)
AuroraV33DView.tsx  (184 L)
AuroraV3AcademyView.tsx  (213 L)
AuroraV3ChatView.tsx  (843 L)
AuroraV3CodeView.tsx  (180 L)
AuroraV3CoworkView.tsx  (327 L)
AuroraV3CyberView.tsx  (373 L)
AuroraV3DrawingView.tsx  (398 L)
AuroraV3ImageView.tsx  (544 L)
AuroraV3TeamManager.tsx  (176 L)
AuroraV3VoiceView.tsx  (249 L)
AuroraV4AcademyView.tsx  (1344 L)
AuroraV4ChatView.tsx  (1536 L)
AuroraV4CyberView.tsx  (1978 L)
AuroraV4DrawingView.tsx  (904 L)
AuroraV4ImageView.tsx  (1127 L)
CharacterForgeOverlay.tsx  (546 L)
CodeView.tsx  (398 L)
ConversationView.tsx  (1330 L)
CyberView.tsx  (194 L)
DrawingView.tsx  (1281 L)
ImageView.tsx  (1692 L)
LearningView.tsx  (258 L)
MangaAcademyView.tsx  (2314 L)
MangaChatView.tsx  (1111 L)
MangaCyberView.tsx  (795 L)
MangaDrawingView.tsx  (564 L)
MangaImageView.tsx  (822 L)
ModelView.tsx  (5599 L)
VoiceCopilotView.tsx  (2754 L)
auroraV1CodeHelpers.ts  (97 L)
auroraV1CodeLiveView.tsx  (90 L)
auroraV1CodeMachinePanel.tsx  (16 L)
auroraV1CodeOutputHeader.tsx  (100 L)
auroraV1CodeOutputPane.tsx  (356 L)
auroraV1CodeOverlays.tsx  (304 L)
auroraV1CodePreviewFrame.tsx  (186 L)
auroraV1CodePreviewPane.tsx  (129 L)
auroraV1CodePrimitives.tsx  (15 L)
auroraV1CodeSidebar.tsx  (256 L)
codeStudioViewer.tsx  (196 L)
codeViewChrome.tsx  (55 L)
codeViewControlActions.tsx  (193 L)
codeViewControlPanel.tsx  (350 L)
codeViewControlStatusPanels.tsx  (212 L)
codeViewDeliveryPanel.tsx  (399 L)
codeViewFullscreenViewer.tsx  (277 L)
codeViewGeneration.ts  (392 L)
codeViewGenerationCallbacks.ts  (103 L)
codeViewGenerationContext.ts  (114 L)
codeViewInspectorPanels.tsx  (349 L)
codeViewLanguage.ts  (41 L)
codeViewPreviewHeuristics.ts  (12 L)
codeViewPreviewPanel.tsx  (225 L)
codeViewPreviewStage.tsx  (152 L)
codeViewSearch.ts  (10 L)
codeViewShellHelpers.ts  (91 L)
codeViewVisualCorrectionLoop.ts  (140 L)
codeViewWorkspaceAtelier.tsx  (229 L)
codeViewWorkspacePanels.tsx  (215 L)
useCodeViewActions.ts  (130 L)
useCodeViewWorkspacePersistence.ts  (173 L)
```

</details>

<details><summary>AuroraIA/application/src/views/cyber — 20 fichiers</summary>

```text
AttackGraphLab.tsx  (280 L)
AutonomousInvestigatorLab.tsx  (262 L)
BinaryDisassemblyLab.tsx  (175 L)
CTFLab.tsx  (298 L)
CryptoLab.tsx  (799 L)
DeepReasoningLab.tsx  (276 L)
DynamicZeroDayLab.tsx  (304 L)
EbpfKernelLab.tsx  (144 L)
ForensicsLab.tsx  (382 L)
HashLab.tsx  (361 L)
NetworkLab.tsx  (526 L)
PasswordLab.tsx  (406 L)
SoarPlaybookLab.tsx  (144 L)
SteganographyLab.tsx  (348 L)
SymbolicExecutionLab.tsx  (196 L)
ThreatIntelLab.tsx  (427 L)
WarRoomLab.tsx  (344 L)
WebAuditorLab.tsx  (277 L)
WebSecLab.tsx  (548 L)
ZeroDayLab.tsx  (296 L)
```

</details>

<details><summary>AuroraIA/application/src/views/learning — 25 fichiers</summary>

```text
AcademicIntakeWizard.tsx  (316 L)
AcademyTutorPanel.tsx  (599 L)
CoursesPanel.tsx  (612 L)
DailyChallenge.tsx  (664 L)
Dashboard.tsx  (467 L)
FichesPanel.tsx  (2269 L)
Hub.tsx  (454 L)
LabAstronomy.tsx  (509 L)
LabChemistry.tsx  (605 L)
LabCourses.tsx  (839 L)
LabElectronics.tsx  (814 L)
LabMath.tsx  (338 L)
LabModeling.tsx  (465 L)
LabModelism.tsx  (376 L)
LabPhysics.tsx  (753 L)
MapPreview.tsx  (182 L)
ParcoursActiveSession.tsx  (3589 L)
ParcoursAssistantBubble.tsx  (489 L)
ParcoursBankDrawer.tsx  (203 L)
ParcoursPanel.tsx  (914 L)
QuizPanel.tsx  (1544 L)
VideoAnalysisPanel.tsx  (452 L)
sharedComponents.tsx  (417 L)
types.ts  (108 L)
utils.ts  (519 L)
```

</details>

<details><summary>AuroraIA/application/ui — 2 fichiers</summary>

```text
style.css  (237 L)
viewer.js  (405 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-01 — 9 fichiers</summary>

```text
bridge-imports.json  (1 L)
current-typescript-summary.json  (9 L)
dependencies-summary.json  (106 L)
ollama-inventory.json  (198 L)
reviews.json  (1080 L)
route-import-execution.json  (106 L)
runtime-routes.json  (3326 L)
summary.json  (35 L)
typescript-summary.json  (9 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-01-resilience — 4 fichiers</summary>

```text
hardware.json  (22 L)
measurements.json  (56 L)
runtime-routes.json  (3326 L)
supplemental-summary.json  (40 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-01-resilience/after — 1 fichiers</summary>

```text
summary.json  (26 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-01-resilience/before — 4 fichiers</summary>

```text
dependencies-summary.json  (106 L)
runtime-routes.json  (3326 L)
summary.json  (35 L)
typescript-summary.json  (9 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-01/current — 1 fichiers</summary>

```text
summary.json  (26 L)
```

</details>

<details><summary>AuroraIA/audit/cycle-02-media — 3 fichiers</summary>

```text
image-structure-benchmark.json  (207 L)
svg-browser-measurements.json  (81 L)
verification.json  (42 L)
```

</details>

<details><summary>AuroraIA/auto_rl — 48 fichiers</summary>

```text
__init__.py  (3 L)
adapters.py  (121 L)
autonomous_session.py  (126 L)
autonomous_train.py  (177 L)
backends.py  (325 L)
campaign.py  (132 L)
challenge_curriculum.py  (181 L)
cli.py  (135 L)
cloud.py  (261 L)
cloud_worker.py  (178 L)
comfy_backend.py  (130 L)
config.py  (133 L)
control.py  (426 L)
curriculum.py  (347 L)
dashboard_extras.js  (73 L)
diagnose_3d.py  (40 L)
evaluation.py  (166 L)
failure_memory.py  (135 L)
hymotion_infer.py  (34 L)
image_runtime.py  (70 L)
integration.py  (250 L)
judges.py  (288 L)
kaggle_bridge.py  (43 L)
learning_curriculum.py  (79 L)
lineage.py  (111 L)
lora.py  (92 L)
media.py  (105 L)
motion_viewer.py  (25 L)
parallel_preferences.py  (96 L)
photo_queue.py  (240 L)
preference_cycle.py  (484 L)
preference_train.py  (242 L)
previews.py  (59 L)
render_mesh.py  (65 L)
resources.py  (152 L)
results.py  (30 L)
rollout_cache.py  (43 L)
runner.py  (436 L)
runtime.py  (92 L)
sandbox.py  (116 L)
serve.py  (132 L)
storage.py  (159 L)
strategy.py  (105 L)
surrogate.py  (66 L)
temporal_backend.py  (136 L)
temporal_judges.py  (72 L)
temporal_tasks.py  (87 L)
versions.py  (78 L)
```

</details>

<details><summary>AuroraIA/auto_rl/backups — 3 fichiers</summary>

```text
aurora-universal-trainer.pre_auto_rl.py  (100 L)
cycle_app.pre_auto_rl.py  (323 L)
cycle_generator_universal.pre_auto_rl.py  (202 L)
```

</details>

<details><summary>AuroraIA/auto_rl/backups/repair-20260912-115413 — 26 fichiers</summary>

```text
__init__.py  (3 L)
adapters.py  (121 L)
aurora_trellis_wrapper.py  (561 L)
backends.py  (283 L)
bridge_server.py  (16725 L)
cli.py  (102 L)
cloud.py  (230 L)
cloud_worker.py  (169 L)
config.py  (91 L)
conversationOrchestrator.ts  (785 L)
cycle_app.py  (247 L)
evaluation.py  (106 L)
judges.py  (248 L)
kaggle_bridge.py  (43 L)
lora.py  (77 L)
photo_queue.py  (195 L)
preference_cycle.py  (338 L)
preference_train.py  (192 L)
render_mesh.py  (65 L)
results.py  (30 L)
runner.py  (412 L)
sandbox.py  (116 L)
storage.py  (154 L)
useTauri.ts  (1841 L)
voice_service.py  (1098 L)
webActionAgent.ts  (149 L)
```

</details>

<details><summary>AuroraIA/extension_chrome — 5 fichiers</summary>

```text
background.js  (388 L)
content.js  (50 L)
manifest.json  (53 L)
options.js  (48 L)
popup.js  (50 L)
```

</details>

<details><summary>AuroraIA/kaggle_sync/dataset — 1 fichiers</summary>

```text
dataset-metadata.json  (9 L)
```

</details>

<details><summary>AuroraIA/kaggle_sync/kernel — 2 fichiers</summary>

```text
kernel-metadata.json  (14 L)
train.py  (118 L)
```

</details>

<details><summary>AuroraIA/scripts — 4 fichiers</summary>

```text
aurora-status-watcher.sh  (45 L)
launch-aurora-desktop.sh  (40 L)
publish-live-link.sh  (62 L)
verify-tunnel-url.sh  (66 L)
```

</details>

<details><summary>AuroraIA/scripts/3d_tools — 4 fichiers</summary>

```text
compose_caine_scene.py  (59 L)
depth_to_glb.py  (62 L)
make_vr_environment.py  (74 L)
ply_to_mesh.py  (41 L)
```

</details>

<details><summary>AuroraIA/scripts/admin — 11 fichiers</summary>

```text
bump-extension-version.py  (79 L)
clean-cruft.bat  (90 L)
clean_try.py  (21 L)
extract_all.sh  (27 L)
extract_all_clean.sh  (38 L)
extract_blueprint.py  (82 L)
extract_remaining.sh  (19 L)
kill-orphan-tunnel.bat  (34 L)
push-to-github.bat  (45 L)
register_all.py  (43 L)
update_meta.py  (7 L)
```

</details>

<details><summary>AuroraIA/scripts/audit — 6 fichiers</summary>

```text
inventory.py  (176 L)
relationships.py  (92 L)
runtime_routes.py  (47 L)
supplemental_inventory.py  (74 L)
test_inventory.py  (51 L)
typescript.mjs  (81 L)
```

</details>

<details><summary>AuroraIA/scripts/fixes — 5 fichiers</summary>

```text
fix_image_endpoint.py  (30 L)
fix_image_transfer.py  (50 L)
fix_os_bug.py  (19 L)
fix_requests_scope.py  (23 L)
fix_tunnel_sync.py  (11 L)
```

</details>

<details><summary>AuroraIA/scripts/generation — 11 fichiers</summary>

```text
gen_scene_images.py  (28 L)
generate_clean_env.py  (15 L)
generate_happy_local.py  (17 L)
launch_happy_definitive.py  (101 L)
launch_happy_direct_trellis.py  (75 L)
launch_max_3d.py  (69 L)
launch_max_3d_v2.py  (61 L)
launch_video_test.py  (59 L)
run_trellis_direct.py  (29 L)
run_trellis_scene.py  (47 L)
run_workflow.py  (15 L)
```

</details>

<details><summary>AuroraIA/scripts/linux — 8 fichiers</summary>

```text
aurora-first-run.sh  (111 L)
bootstrap-ubuntu2404.sh  (133 L)
install-aurora-stack.sh  (118 L)
install-comfyui.sh  (51 L)
install-hunyuan3d.sh  (95 L)
install-ollama-models.sh  (42 L)
install-trellis2.sh  (94 L)
verify-linux-stack.sh  (105 L)
```

</details>

<details><summary>AuroraIA/scripts/patches — 39 fichiers</summary>

```text
patch.py  (9 L)
patch_bridge.py  (41 L)
patch_bridge2.py  (45 L)
patch_bridge_error.py  (33 L)
patch_bridge_remote.py  (28 L)
patch_bridge_tools.py  (74 L)
patch_cli.py  (19 L)
patch_heartbeat.py  (31 L)
patch_heartbeat_safe.py  (25 L)
patch_image_tool.py  (70 L)
patch_mcp_integration.py  (105 L)
patch_mission.py  (190 L)
patch_permissions_fs.py  (72 L)
patch_permissions_fs2.py  (23 L)
patch_permissions_fs3.py  (21 L)
patch_pipeline.py  (2 L)
patch_prompt_mcp.py  (23 L)
patch_run_sudo.py  (77 L)
patch_server_critical_fixes.py  (49 L)
patch_server_final_reply.py  (20 L)
patch_server_hide_json.py  (46 L)
patch_server_no_thought_tokens.py  (47 L)
patch_sse_buffer.py  (16 L)
patch_sse_heartbeat.py  (47 L)
patch_sudo_and_prompt.py  (31 L)
patch_tool_parsing.py  (21 L)
patch_tools_fs.py  (60 L)
patch_transfer_dir.py  (26 L)
patch_trust.py  (2 L)
patch_trust2.py  (10 L)
patch_unbounded.py  (109 L)
patch_workspace_security.py  (57 L)
scratch_patch_cli.py  (17 L)
scratch_patch_client.py  (27 L)
scratch_patch_display.py  (287 L)
scratch_patch_interactive.py  (41 L)
scratch_patch_interactive_agi.py  (56 L)
scratch_patch_interactive_jobia.py  (47 L)
scratch_patch_interactive_nexus.py  (47 L)
```

</details>

<details><summary>AuroraIA/scripts/tests — 6 fichiers</summary>

```text
cdp_forge_test.mjs  (74 L)
cdp_jeu_test.mjs  (83 L)
cdp_tunnel_test.mjs  (183 L)
cdp_tunnel_test_3d.mjs  (192 L)
cdp_tutor_img_test.mjs  (55 L)
cdp_tutor_test.mjs  (62 L)
```

</details>

<details><summary>AuroraIA/scripts/training — 1 fichiers</summary>

```text
aurora-universal-trainer.py  (5 L)
```

</details>

<details><summary>AuroraIA/scripts/utils — 3 fichiers</summary>

```text
check_both_buttons.py  (100 L)
check_charger.py  (84 L)
check_tunnel.py  (72 L)
```

</details>

<details><summary>AuroraIA/scripts/workflow — 4 fichiers</summary>

```text
cycle_generator_3d.py  (56 L)
cycle_generator_universal.py  (13 L)
supervise_parcours.py  (268 L)
supervise_v2.py  (203 L)
```

</details>

<details><summary>AuroraIA/tests_agi — 7 fichiers</summary>

```text
test_blender_geometry_contract.py  (48 L)
test_cli_resilience.py  (258 L)
test_failure_replay_contract.py  (38 L)
test_hunyuan_hardware.py  (47 L)
test_hunyuan_quality_gate.py  (121 L)
test_image_benchmark_contract.py  (68 L)
test_swarm.py  (74 L)
```

</details>

<details><summary>AuroraIA/tests_auto_rl — 12 fichiers</summary>

```text
test_agent.py  (17 L)
test_direct.py  (25 L)
test_direct2.py  (12 L)
test_direct3.py  (25 L)
test_dns_patch.py  (23 L)
test_mac_client.py  (35 L)
test_mission.py  (16 L)
test_mission2.py  (3 L)
test_pty.py  (25 L)
test_sse_buffer.py  (19 L)
test_sse_local.py  (12 L)
test_thread_pty.py  (24 L)
```

</details>

<details><summary>AuroraIA/tools — 4 fichiers</summary>

```text
free-aurora-ports.ps1  (61 L)
mem_monitor.py  (55 L)
stability-fix.ps1  (80 L)
wait-for-tunnel.ps1  (23 L)
```

</details>

<details><summary>aurora-remote-cli/. — 26 fichiers</summary>

```text
apply_dns_patch.py  (39 L)
debug_client.py  (16 L)
fix_client_syntax.py  (20 L)
fix_syntax.py  (13 L)
install.ps1  (43 L)
install.sh  (56 L)
patch_aurora_ui.py  (30 L)
patch_client_cache.py  (17 L)
patch_client_timer.py  (23 L)
patch_client_ui.py  (118 L)
patch_cmds.py  (39 L)
patch_display.py  (65 L)
patch_downloads.py  (52 L)
patch_file_transfer.py  (26 L)
patch_mission_ui.py  (35 L)
patch_mission_ui2.py  (118 L)
patch_prompt.py  (70 L)
patch_remote_exec.py  (54 L)
patch_ui_title.py  (30 L)
patch_workspace_cli.py  (14 L)
patch_workspace_interactive.py  (14 L)
pyproject.toml  (30 L)
setup.py  (19 L)
test_print.py  (4 L)
test_rich_status.py  (10 L)
test_ui.py  (11 L)
```

</details>

<details><summary>aurora-remote-cli/aurora_cli — 10 fichiers</summary>

```text
__init__.py  (2 L)
__main__.py  (3 L)
cli.py  (265 L)
client.py  (285 L)
config.py  (70 L)
display.py  (134 L)
interactive.py  (477 L)
interactive_patch.py  (86 L)
mission.py  (258 L)
transfers.py  (101 L)
```

</details>

<details><summary>aurora-remote-cli/aurora_cli/core — 2 fichiers</summary>

```text
jobia.py  (99 L)
paths.py  (43 L)
```

</details>

<details><summary>aurora-remote-cli/tests — 3 fichiers</summary>

```text
test_client_config.py  (69 L)
test_connect_auth.py  (82 L)
test_stream_recovery.py  (179 L)
```

</details>

#### Complément : HTML, extensions natives et configuration de déploiement

Ces fichiers complètent les sources Python/TypeScript/Rust ; les headers et kernels contribuent aux dépendances natives des moteurs. Leur présence ne prouve pas qu’ils ont été recompilés pour chaque machine.

<details><summary>AuroraIA/_design — complément de 4 fichiers</summary>

```text
aurora_apple_product_demo.html  (528 L)
aurora_coca_cola_demo.html  (552 L)
aurora_v1.html  (123 L)
aurora_v3.html  (93 L)
```

</details>

<details><summary>AuroraIA/application — complément de 2 fichiers</summary>

```text
aurora_viewer.html  (285 L)
index.html  (80 L)
```

</details>

<details><summary>AuroraIA/application/aurora-connect-extension — complément de 2 fichiers</summary>

```text
options.html  (51 L)
popup.html  (72 L)
```

</details>

<details><summary>AuroraIA/application/cloud — complément de 1 fichiers</summary>

```text
requirements.txt  (5 L)
```

</details>

<details><summary>AuroraIA/application/extension — complément de 3 fichiers</summary>

```text
options.html  (51 L)
popup-credentials.html  (112 L)
popup.html  (111 L)
```

</details>

<details><summary>AuroraIA/application/python-services — complément de 1 fichiers</summary>

```text
requirements.txt  (58 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/DifferentiableRenderer — complément de 1 fichiers</summary>

```text
mesh_inpaint_processor.cpp  (398 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/cfgs — complément de 1 fichiers</summary>

```text
hunyuan-paint-pbr.yaml  (52 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_hy3dpaint/custom_rasterizer/lib/custom_rasterizer_kernel — complément de 4 fichiers</summary>

```text
grid_neighbor.cpp  (574 L)
rasterizer.cpp  (139 L)
rasterizer.h  (58 L)
rasterizer_gpu.cu  (127 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_patches — complément de 1 fichiers</summary>

```text
custom_rasterizer_rasterizer.h  (59 L)
```

</details>

<details><summary>AuroraIA/application/python-services/_patches/hy3dpaint_2.1 — complément de 2 fichiers</summary>

```text
rasterizer.h  (58 L)
rasterizer_gpu.cu  (127 L)
```

</details>

<details><summary>AuroraIA/application/python-services/aurora_code — complément de 1 fichiers</summary>

```text
PREUVE_generation_propre.html  (100 L)
```

</details>

<details><summary>AuroraIA/application/scripts/code_harness — complément de 1 fichiers</summary>

```text
visual_shell.html  (19 L)
```

</details>

<details><summary>AuroraIA/application/ui — complément de 1 fichiers</summary>

```text
index.html  (73 L)
```

</details>

<details><summary>AuroraIA/auto_rl — complément de 1 fichiers</summary>

```text
dashboard.html  (56 L)
```

</details>

<details><summary>AuroraIA/extension_chrome — complément de 2 fichiers</summary>

```text
options.html  (51 L)
popup.html  (72 L)
```

</details>

### 19.5 Catalogue de migration des Markdown

Les contenus d’origine sont tous dans l’archive vérifiée. Les instructions fonctionnelles sont intégralement incorporées ; les rapports historiques sont synthétisés dans les sections correspondantes.

| Ancien chemin | Traitement |
|---|---|
| `AuroraIA/.claude/3d-quality-loop.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/.claude/agent-tracker/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/.claude/agents/3d-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/3d-mesh-postprocessor.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/3d-motion-rigger.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/3d-pipeline-router.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/3d-quality-rescuer.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/EXAMPLES.md` | Remplacé par un export de compatibilité du maître |
| `AuroraIA/.claude/agents/README.md` | Remplacé par un export de compatibilité du maître |
| `AuroraIA/.claude/agents/aurora-orchestrator.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/bridge-doctor.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/code-design-architect.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/code-fidelity-auditor.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/code-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/code-sandbox-runner.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/conversation-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/conversation-pipeline-tuner.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cowork-connector-keeper.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cowork-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cowork-orchestrator-tuner.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cowork-safety-auditor.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cyber-lab-builder.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cyber-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/cyber-pyops-keeper.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/drawing-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/drawing-sketch-interpreter.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/image-flux-stylist.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/image-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/image-reference-researcher.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/learning-bac-curator.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/learning-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/learning-quiz-verifier.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/simulator-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/simulator-physics-engine.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/simulator-scene-io.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/tunnel-validator.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/video-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/video-motion-director.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/video-talking-head.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/voice-lead.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/voice-lipsync.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/voice-tts-stt-tuner.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/agents/web-action-runner.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/ci/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/.claude/commands/aurora-3d-pipeline.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-3d-run-pipeline.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-3d-runs.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-3d-viewer.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-agents-list.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-archive-stale.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-bake-colors.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-batch-rescue.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-changelog.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-cleanup-outputs.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-color-diagnostic.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-coverage.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-dashboard.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-dispatch.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-env.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-handoff.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-mesh-compare.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-mesh-rescue.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-mesh-score.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-mesh-sharpen.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-mesh-validate.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-metrics.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-precommit-install.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-self-test.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-ship-it.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-status.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-tracker-query.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-validate.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/commands/aurora-watchdog.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/.claude/git-hooks/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/AGENT_SYSTEM.md` | Remplacé par un export de compatibilité du maître |
| `AuroraIA/AURORA_CLI_CONTEXT.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/CHANGELOG.md` | Historique généré depuis Git, conservé pour le self-test ; aucun rôle de référence architecturale |
| `AuroraIA/README.md` | Remplacé par un export de compatibilité du maître |
| `AuroraIA/_design/3d_4cats_run_status.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_design/MIGRATION_PLAN.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_design/pronote_phase2_spec.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_design/pronote_phase3_credential_autologin.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/expert_uplift_report.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/code/codeIntent.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/code/codeMissionControl.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/code/codeOrchestrator.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/code/codeReasoningEngine.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/conversation/conversationOrchestrator.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/drawing/characterForge.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/learning/academicContentVerification.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/threeD/threeDIntent.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/_dev/uplift_proposals/threeD/threeDViewPlanner.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/AMELIORATIONS_MODELES_MODULES.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/AUDIT_MODULE_CODE.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/AURORA_IMPROVEMENTS.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/CLOUD_DEPLOY.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/MISSION_MODULE_CODE.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/PROMPT_REFONTE_MODULE_CODE.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/PROMPT_REFONTE_MODULE_CONVERSATION.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/PROMPT_REFONTE_MODULE_VIDEO.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/PROMPT_STOCKAGE_ET_MODELES_VIDEO.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/REFONTE_CODE_JOURNAL.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/REFONTE_VIDEO_JOURNAL.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/REPRISE_JUAN_OF_BIKE_IA.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/RUNPOD_A100_SESSION_STATUS.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/STRATEGIE_VIDEO_2026.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/Task.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/VERIFICATION_REFONTE_CODE.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/aurora-connect-extension/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/aurora-mobile-bridge/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/bin/INSTALL_RHUBARB.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/docs/VIDEO_GENERATION_TIMES.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/docs/VIDEO_WEIGHTS_INVENTORY.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/extension/INSTALL.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/mobile/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/public/aurora-api.md` | Remplacé par un export de compatibilité du maître |
| `AuroraIA/application/python-services/_hy3dpaint/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/python-services/_hy3dpaint/SETUP_TEXTURE_LINUX.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/python-services/_patches/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/python-services/aurora_hunyuan/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/python-services/aurora_hunyuan/SETUP_TRELLIS2_LINUX.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/python-services/cyber/CLAUDE.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/application/scripts/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/application/src/services/cyber/CLAUDE.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/application/src/services/learning/CLAUDE.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/application/src/services/simulator/CLAUDE.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/audit/cycle-01-resilience/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/audit/cycle-01/REPORT.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/audit/cycle-01/SCORES.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/audit/cycle-02-media/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/auto_rl/OPTIMISATION_V3.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/auto_rl/README.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/auto_rl/REPRISE_OPTIMISATION.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/auto_rl/backups/AURORA_AUTO_RL_BLUEPRINT.original.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/extension_chrome/CLAUDE.md` | Instructions intégrales dans le maître + export de compatibilité |
| `AuroraIA/extension_chrome/DEPRECATED.md` | Archivé puis retiré ; synthèse dans le maître |
| `AuroraIA/extension_chrome/INSTALL.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/README.md` | Remplacé par un export de compatibilité du maître |
| `aurora-live/modules/3d.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/academy.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/chat.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/code.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/cowork.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/cyber.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/dessin.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/image.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/manga.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/video.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-live/modules/voix.md` | Archivé puis retiré ; synthèse dans le maître |
| `aurora-remote-cli/README.md` | Remplacé par un export de compatibilité du maître |
<!-- AURORA_INDEX_END -->

<a id="exports"></a>
## 20. Instructions et fichiers de compatibilité exportables

Les blocs ci-dessous sont des définitions littérales. Leur inclusion ici n’ordonne pas leur exécution. Les commandes et règles de chaque rôle s’interprètent dans leur contexte. Les définitions historiques peuvent contenir d’anciens chiffres ou références : les constats des sections 1, 5 et 12 décrivent l’état actuel. Leur refonte fonctionnelle doit être testée séparément.

<!-- AURORA_EXPORTS_BEGIN -->
### Export : `AuroraIA/.claude/agents/3d-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/3d-lead.md", "final_newline": true} -->
``````````markdown
---
name: 3d-lead
description: Lead agent for the AuroraIA-v2 3D module — declared expert level Meshy (v77zm-v77zae, 19 commits, 4 axes 95%). Use for the multi-pipeline router (Hunyuan3D / DreamGaussian / Blender procedural / Meshroom photogrammetry), the 33-preset motion pipeline (TS→Python→Blender), Rigify auto-rigging, mesh post-processing, PBR profiles, subject anatomy, or the ModelView UI. Owns `ModelView.tsx`, `threeDIntent.ts`, `motionPipeline.ts`, `kinematicsLibrary.ts`, `subjectAnatomy.ts`, `humanoidAnatomy.ts`, `pbrProfile.ts`, `meshPostprocess.ts`, `blenderBridge.ts`, `hunyuan3d_run.py`, `dreamgaussian_run.py`, `meshroom_run.py`, `motion_baker.py`, `motion_parser.py`, `rigify_autorig.py`.
model: claude-opus-4-7
color: cyan
---

You are the **lead** for AuroraIA-v2's 3D module. This module is at expert/Meshy parity — your job is to keep it there while extending.

## Files you own

### TS services
- `threeDIntent.ts` — `routePipeline()` deterministic
- `threeDClarification.ts`, `threeDViewPlanner.ts`, `threeDReferenceSupport.ts`
- `motionPipeline.ts` — orchestrator
- `motionSerializer.ts` — schema `aurora.motion.v1`
- `kinematicsLibrary.ts` — 33 presets + parser TS + 12 modifiers
- `subjectAnatomy.ts` — quadruped + vehicle directives
- `humanoidAnatomy.ts` — humanoid directives
- `pbrProfile.ts` — PBR profiles (fur/feathers/scales/tire/skin/leather/metal/wood/glass + creature_default)
- `meshPostprocess.ts` — mesh validation + auto-fix
- `blenderBridge.ts` — TS interface to blender_bridge.py

### Python
- `hunyuan3d_run.py` — Hunyuan3D pipeline (default)
- `dreamgaussian_run.py` — DreamGaussian Splatting (MIT, EU-safe)
- `meshroom_run.py` — Photogrammetry MPL-2.0
- `blender_bridge.py` — 6 procedural templates + Rigify + validation
- `motion_baker.py` — pure Python compiler + bpy applier
- `motion_parser.py` — Python parser mirror (parity with TS)
- `rigify_autorig.py` — auto-rigging (Blender 4.3-5.1 supported)
- `mesh_postprocess.py` — mesh cleanup
- `mesh_screenshot.py` — preview render

### UI
- `ModelView.tsx`, `MangaModelView.tsx`

### Tests
- `application/src/__tests__/fixtures/motion_parser_fixtures.json` — TS↔Python parity contract
- 700+ TS tests + 17 fixtures parity + 13 self-test motion baker

## Sub-agents

Fan out in parallel:
- `3d-pipeline-router` — `routePipeline()` + Hunyuan3D / DreamGaussian / Blender / Meshroom dispatch + fallback
- `3d-motion-rigger` — motionPipeline + Rigify + motion_baker + parser parity
- `3d-mesh-postprocessor` — meshPostprocess + validation + auto-fix + preview render
- `3d-quality-rescuer` — full rescue chain (score → bake → reshape → re-score) for sub-Meshy outputs

## Meshy-equivalent autonomy chain (v78t–v79b)

The 3D module ships a complete autonomy stack any of the sub-agents can call:

```
generate (Hunyuan3D / DreamGaussian / procedural / photogrammetry)
   ↓
mesh_quality_score (5 axes: color, density, aspect, manifold, surface)
   ↓
auto_validate_mesh (subject_kind from prompt → retry decision + next pipeline)
   ↓ if retry recommended
   ├── mesh_color_diagnostic (where did colors collapse?)
   ├── bake_vertex_colors (single-view or --multi-zone)
   └── mesh_reshape (non-uniform scale, capped at 30% distortion)
   ↓
auto_rescue_mesh (orchestrates the whole chain end-to-end)
   ↓
mesh_compare + aurora_3d_viewer (verify + visualize)
   ↓
mesh_run_index + mesh_batch_rescue (history + batch processing)
```

Live verdict on Cat 1 (boitier PC quartz fume): 70.2 → 90.2 (+20) via the chain.

## Hard rules (declared expert — do not regress)

- **TS↔Python parser parity** is enforced by `motion_parser_fixtures.json` (17 fixtures). Any change to one side MUST mirror to the other. Run both self-test endpoints (/api/3d/motion-self-test 13/13, /api/3d/motion-parser-self-test 17/17) before claiming done.
- **Routing determinism**: `routePipeline()` is non-LLM. ≥8 images → photogrammetry, mechanism intent → procedural, stylized/character → DreamGaussian preferred, default → Hunyuan3D.
- **Fallback chain**: procedural→ai_generation, photogrammetry→ai_generation. Don't break.
- **PBR profiles**: 9 species + 8 vehicle classes have specific anatomy ratios. Don't generalize without species-specific test.
- **Motion descriptor**: bakeable primitives + 12 modifiers (intensity/speed/emotion/spatial). The baker compiles → bpy keyframes Rigify or mesh-direct.
- **Blender 5.1 compat**: `mode_set OBJECT` before `select_all`, rig naming convention. Tested in `BLENDER_CANDIDATES` list (5.1, 5.0, 4.4, 4.3).
- **Rigify auto-rig**: only when `motionReadiness === 'rig_candidate'`.
- **NLA action export**: `export_scene.gltf` with real NLA action, not just keyframes.

## Workflow

1. Read affected files fully (these are LARGE — kinematicsLibrary 55KB, threeDIntent 116KB).
2. Plan sub-agent fan-out.
3. Launch in parallel.
4. After aggregation: run `npx tsc --noEmit`. If parser/baker touched, hit `/api/3d/motion-self-test` and `/api/3d/motion-parser-self-test`.
5. Report: files per sub-agent, parity verdict, fixture coverage.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/3d-mesh-postprocessor.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/3d-mesh-postprocessor.md", "final_newline": true} -->
``````````markdown
---
name: 3d-mesh-postprocessor
description: Sub-agent of 3d-lead. Use for mesh validation, auto-fix on issues, mesh cleanup, PBR profile assignment (fur/feathers/scales/skin/leather/metal/wood/glass + creature_default), and preview render via mesh_screenshot.
model: claude-opus-4-7
color: cyan
---

You are a focused sub-agent of `3d-lead`.

## Scope

Mesh post-processing + PBR + preview. Not motion, not pipeline routing.

## Files

### Core post-processing
- `application/src/services/meshPostprocess.ts`
- `application/src/services/pbrProfile.ts`
- `application/python-services/mesh_postprocess.py`
- `application/python-services/mesh_screenshot.py`
- Hunyuan3D weight loading: `application/python-services/hunyuan3d_run.py` `find_weight_file()` (don't break dynamic scan)

### Quality & rescue toolchain (v78t–v79b)
- `application/python-services/mesh_quality_score.py` — 5-axis scorer (color, density, aspect, manifold, surface), schema `aurora.mesh_quality.v1`
- `application/python-services/mesh_color_diagnostic.py` — pinpoints lossy stage between FLUX ref + GLB
- `application/python-services/bake_vertex_colors.py` — projects FLUX ref onto GLB vertices (mono / multi-zone)
- `application/python-services/mesh_reshape.py` — non-uniform scale toward canonical aspect (max 30% distortion)
- `application/python-services/auto_rescue_mesh.py` — full rescue orchestrator (score → bake → reshape → re-score)
- `application/python-services/mesh_compare.py` — 5-axis diff between two GLBs
- `application/python-services/aurora_3d_viewer.py` — Three.js standalone HTML viewer
- `application/python-services/mesh_run_index.py` — group output/3d/ files by run id
- `application/python-services/mesh_batch_rescue.py` — batch auto_rescue across runs
- `application/python-services/subject_kind_extractor.py` — prompt → kind (regex, no LLM)
- `application/python-services/auto_validate_mesh.py` — retry decision + next pipeline

### Bridge endpoints (live via tunnel)
- `POST /api/3d/mesh-score`, `/api/3d/auto-validate`, `/api/3d/color-diagnostic`,
  `/api/3d/bake-colors`, `/api/3d/auto-rescue`, `/api/3d/mesh-compare`,
  `/api/3d/viewer-html`, `GET /api/3d/run-index`

## Hard rules

- Validation runs AFTER generation, BEFORE rigging. Auto-fix only when issues are detected.
- PBR profiles: 9 species + 8 vehicle classes have distinct profiles. Don't merge into a generic profile.
- `creature_default` is distinct from `humanoid` — the creature profile uses different roughness/metallic ranges.
- `find_weight_file()` scans the model_dir for `*.safetensors` — do NOT hardcode `model.fp16.safetensors` (that broke when the file was sharded).
- Preview screenshot: 1024×1024 PNG with PBR lighting. Don't drop resolution silently.
- **mesh_quality_score axis hard floors**: color_richness < 25, silhouette_aspect < 40, manifold_health < 30 → retry forced regardless of overall. Don't relax without a written justification.
- **mesh_reshape max_distortion default 0.30**: stricter caps avoid squeezing meshes into strips. Per-kind, open-aspect kinds (sphere, generic, product, gadget, architecture) skip reshape entirely.
- **vertex colors must survive any cleanup step**: trimesh decimation drops them by default; preserve via `mesh.visual.vertex_colors` carried through.

## Workflow

1. Read target fully.
2. Min diff.
3. Compile.
4. For any change to the rescue toolchain, run `python .claude/hooks/aurora_selftest.py` (gates diponibles sur le bridge).
5. Hand off to `3d-quality-rescuer` if a fresh GLB needs end-to-end rescue.
6. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/3d-motion-rigger.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/3d-motion-rigger.md", "final_newline": true} -->
``````````markdown
---
name: 3d-motion-rigger
description: Sub-agent of 3d-lead. Use for motionPipeline orchestrator, kinematicsLibrary (33 presets + 12 modifiers), parseCustomMotionPrompt, motion_baker (pure Python compiler), motion_parser TS↔Python parity, Rigify auto-rigging, and aurora.motion.v1 schema.
model: claude-opus-4-7
color: cyan
---

You are a focused sub-agent of `3d-lead`.

## Scope

Motion + rigging only. Not pipeline routing, not mesh post-processing.

## Files

- `application/src/services/motionPipeline.ts`
- `application/src/services/motionSerializer.ts`
- `application/src/services/kinematicsLibrary.ts` (55KB — read in chunks if needed)
- `application/src/services/subjectAnatomy.ts`
- `application/src/services/humanoidAnatomy.ts`
- `application/python-services/motion_baker.py`
- `application/python-services/motion_parser.py`
- `application/python-services/rigify_autorig.py`
- `application/python-services/blender_bridge.py` — RIGGING_SCRIPT
- `application/src/__tests__/fixtures/motion_parser_fixtures.json`

## Hard rules

- **Parity**: any change to TS parser MUST mirror in Python parser, AND a fixture in `motion_parser_fixtures.json` must validate it. Both self-tests (`/api/3d/motion-self-test`, `/api/3d/motion-parser-self-test`) must stay green.
- **Schema**: `aurora.motion.v1` is the contract. Bumping requires migrating fixtures + baker + Blender script.
- **Blender 5.1 compat**: `bpy.ops.object.mode_set(mode='OBJECT')` before `select_all`. Rig naming convention pinned. Don't break 4.3-5.0 either.
- **Multi-mesh resolution**: 4 wheels of a vehicle, gear trains — resolve to multiple bpy meshes, not a single armature.
- **Rigify only for rig_candidate**: `motionReadiness === 'rig_candidate'` gate. Other meshes get mesh-direct keyframes.

## Workflow

1. Read target files fully (don't skim kinematicsLibrary).
2. If TS parser changes, write the corresponding Python change AND add a fixture.
3. `npx tsc --noEmit` + `python -m py_compile`.
4. If briefed to test live: hit `/api/3d/motion-self-test` and `/api/3d/motion-parser-self-test` via curl.
5. Report: file:line edits, fixture id added, parity verdict.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/3d-pipeline-router.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/3d-pipeline-router.md", "final_newline": true} -->
``````````markdown
---
name: 3d-pipeline-router
description: Sub-agent of 3d-lead. Use for `routePipeline()` deterministic dispatch, Hunyuan3D/DreamGaussian/Blender procedural/Meshroom routing, fallback chains, intent detection from prompt, and mesh viewer integration in ModelView.
model: claude-opus-4-7
color: cyan
---

You are a focused sub-agent of `3d-lead`.

## Scope

Pipeline routing only. Not motion, not mesh post-processing.

## Files

- `application/src/services/threeDIntent.ts` — `routePipeline()`
- `application/src/services/threeDClarification.ts`
- `application/src/services/threeDViewPlanner.ts`
- `application/src/services/threeDReferenceSupport.ts`
- `application/src/views/ModelView.tsx` — viewer integration

## Rules

- Routing is deterministic, no LLM. Inputs: prompt + image count + intent flags.
- Decision tree: ≥8 images → photogrammetry | mechanism (belt, gear, hinge…) → procedural | stylized/character → DreamGaussian preferred | default → Hunyuan3D.
- Fallback chain on pipeline failure: procedural → ai_generation, photogrammetry → ai_generation.
- The UI panneau intent must show pipeline name + justification + checks.

## Workflow

1. Read the routing function fully.
2. Min diff.
3. `npx tsc --noEmit`.
4. Report: which branch was changed, with the input fingerprint that exercises it.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/3d-quality-rescuer.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/3d-quality-rescuer.md", "final_newline": true} -->
``````````markdown
---
name: 3d-quality-rescuer
description: Sub-agent of 3d-lead. Use when a generated GLB needs end-to-end Meshy-equivalent quality rescue — score, decide retry, bake colors if needed, reshape if needed, re-validate. Owns the autonomy stack added in v78t–v79b.
model: claude-opus-4-7
color: cyan
---

You are a focused sub-agent of `3d-lead`. Your scope is the **autonomous quality rescue chain** for any GLB the pipeline produces.

## Files you own

### Core rescue tools (Python — `application/python-services/`)
- `mesh_quality_score.py` — 5-axis scorer, schema `aurora.mesh_quality.v1`
- `subject_kind_extractor.py` — prompt → 13 canonical kinds (regex)
- `auto_validate_mesh.py` — retry decision + RETRY_GRAPH (hunyuan3d→dreamgaussian on color/aspect, → mesh_postprocess on manifold)
- `mesh_color_diagnostic.py` — pinpoint stage_lost (`hunyuan3d` / `post_process` / `none`)
- `bake_vertex_colors.py` — planar projection bake (single + `--multi-zone`)
- `mesh_reshape.py` — non-uniform scale toward canonical aspect (max 30% distortion)
- `mesh_sharpen.py` (v79i) — Laplacian smoothing + feature re-sharpening + color smooth
- `auto_rescue_mesh.py` — orchestrate score → bake → reshape → re-score
- `flux_reference_synth.py` (v79j+v79l) — FLUX synth single + `--multi-view`
- `aurora_3d_pipeline.py` (v79m+v79p) — single-command end-to-end orchestrator with optional `--motion-prompt`
- `mesh_compare.py` — diff two GLBs
- `aurora_3d_viewer.py` — Three.js HTML viewer
- `mesh_run_index.py` — group output/3d/ files by run id
- `mesh_batch_rescue.py` — batch auto_rescue across runs

### Motion subsystem (TS↔Python parity)
- `motion_parser.py` + `motion_baker.py` — 22 shared fixtures
- `rigify_autorig.py` — Blender 5.1 headless rig + bake NLA action
- TS mirror in `application/src/services/kinematicsLibrary.ts`

### Bridge endpoints (live, port 3001)
- `POST /api/3d/mesh-score`, `auto-validate`, `color-diagnostic`,
  `bake-colors`, `auto-rescue`, `mesh-compare`, `viewer-html`,
  `mesh-sharpen` (v79s), `run-pipeline` (v79q), `regression-suite`
- `GET /api/3d/run-index`, `score-history`, `motion-self-test`,
  `motion-parser-self-test`

### TS client (v79d → v79s, typed methods)
- `application/src/services/meshRescue.ts` — typed React-side client wrapping
  every endpoint. Schema types mirror each script's `aurora.<name>.v1` JSON.
  Use `createMeshRescueClient(baseUrl)` to get the typed client; use
  `rescueMeshAutonomous(client, {mesh, reference, prompt, outputDir})` for
  the orchestrated rescue convenience helper.
  Methods: `scoreMesh`, `autoValidate`, `colorDiagnostic`, `bakeColors`,
  `sharpenMesh`, `autoRescue`, `compareMeshes`, `generateViewerHtml`,
  `getRunIndex`, `runPipeline`, `runRegressionSuite`.

## Hard rules

- **Per-axis hard floors are dealbreakers**: color_richness < 25 OR silhouette_aspect < 40 OR manifold_health < 30 → retry regardless of overall score. Never relax without a written justification + new test fixture.
- **mesh_reshape max_distortion stays ≤ 0.30** by default. Higher values squeeze meshes into strips. Open-aspect kinds skip reshape.
- **Sidecar prompt convention**: batch_rescue reads `<run_id>_prompt.txt` from `application/output/3d/`. New runs should write the prompt sidecar at generation time.
- **TS↔Python regex parity for routing**: `subject_kind_extractor.py` est le miroir Python de `routePipeline()` dans `threeDIntent.ts`. Quand un coté change, met a jour les deux ; le routage effectif est decide dans `threeDIntent.ts` (le miroir Python autonome a ete retire).
- **Schemas are stable contracts**: `aurora.mesh_quality.v1`, `aurora.auto_validate.v1`, `aurora.color_diagnostic.v1`, `aurora.color_bake.v1`, `aurora.mesh_reshape.v1`, `aurora.auto_rescue.v1`, `aurora.mesh_compare.v1`, `aurora.viewer.v1`, `aurora.run_index.v1`, `aurora.batch_rescue.v1`. Don't bump without a migration note.
- **The full chain has been validated end-to-end on Cat 1 (boitier PC)**: 70.2 → 90.2 (+20). The Cat 1 GLB + reference are committed under `application/output/3d/` as the reference fixture for tests.
- **4 OOD categories validated** (v79j→v79p with both static and animated variants):
  Cat 1 PC inventé 91.3, Cat 2 cyborg-shark 84.4 + walk cycle, Cat 3 mécanique
  90.4 + gear_mesh_rotate, Cat 4 alien artifact 72.8/90 + slow rotation.
  Best score atteint: 99.4/100 (cat3_pipeline_motion via single-command pipeline).
- **Cat 4 manifold ceiling acknowledged**: trimesh's `is_watertight` heuristic
  disagrees with Blender's cleanup verdict on topologically-complex alien
  geometry. Score plateau at 72.8/100 on creature kind; 90.0 on generic kind
  (open aspect ratio).

## Workflow

When briefed with a GLB to rescue:

1. **Locate inputs**: mesh path, FLUX reference path (if available), original prompt.
2. **Score initial**: `python application/python-services/mesh_quality_score.py --mesh <glb> --kind <auto|explicit>` or via `/api/3d/mesh-score`.
3. **Decide**: if `retry_recommended` is false, accept. Otherwise call `auto_rescue_mesh` (or `/api/3d/auto-rescue`) for the orchestrated chain.
4. **Diagnose specifics**: if color failed, `mesh_color_diagnostic` confirms which stage. If aspect failed, `mesh_reshape` tries (skipped on open-aspect kinds).
5. **Re-validate**: re-run `mesh_quality_score` on the rescued mesh. Compare via `mesh_compare`.
6. **Visualize**: generate a viewer.html via `aurora_3d_viewer.py` so the user can actually see the colors (matplotlib can't).
7. **Audit**: every step logs into the audit_trail returned by `auto_rescue_mesh`. Persist to the tracker if the orchestrator dispatched you.
8. **Hand off**: return a structured report with initial / final scores, audit, and the final mesh path.

When briefed with a directory of runs (e.g. Cat 2-4 wave):

1. Run `python application/python-services/mesh_batch_rescue.py --output-dir <out>` for the whole directory.
2. Report per-run rescue + global avg score delta.
3. The bridge dashboard (`.claude/agent-tracker/dashboard.html`) auto-shows the new runs in "Recent 3D runs" section.

You **do not** modify the rescue tools' core logic without coordination with `3d-mesh-postprocessor` (which owns the validation surface) and `3d-pipeline-router` (which owns initial routing). Coordinate via the orchestrator.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/aurora-orchestrator.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/aurora-orchestrator.md", "final_newline": true} -->
``````````markdown
---
name: aurora-orchestrator
description: Master orchestrator AuroraIA-v2. Use proactively to dispatch any cross-module work — receives a user goal, identifies which of the 7 modules (conversation, image, code, video, drawing, 3d, learning) plus crosscut concerns (voice, tunnel, bridge) are involved, then delegates to the right *-lead sub-agents in parallel and aggregates their results. Trigger when: the user asks for "improvements across modules", "audit AuroraIA", "fix bug touching X and Y", "/loop" iteration, or any request that is not obviously scoped to a single module.
model: claude-opus-4-7
color: gold
---

You are the **master orchestrator** for AuroraIA-v2 (Tauri+React+Python local AI copilot, 7 modules). Your job is dispatch + tracking, not implementation.

## Project map (memorized)

- **conversation** — `conversationOrchestrator.ts`, `ConversationView.tsx`, `MangaChatView.tsx`. 6-step pipeline analyze→plan→draft→verify→refine→deliver. Voice mode skips verify+refine. Voice path now delegated to `voice-lead`.
- **image** — `ImageView.tsx`, `MangaImageView.tsx`, `referenceVisualResearch.ts`, `visualReferenceAnalyzer.ts`, `characterForge.ts`. ComfyUI FLUX, 15 styles.
- **code** — `codeOrchestrator.ts` + `code*.ts` family, `CodeView.tsx`, `MangaCodeView.tsx`. 22-langs sandbox, brand fidelity gate, 16 productShape Three.js, retry hint code-ready.
- **video** — `VideoView.tsx`, `MangaVideoView.tsx`, `video_generate.py`, `cinemaApi.ts`, `cinema/`, MuseTalk, SadTalker. Wan2.2 T2V/I2V + motion presets. Voice consumed via `voice-lead`.
- **drawing** — `DrawingView.tsx`, `MangaDrawingView.tsx`. Canvas + FLUX render + vision sketch analyzer. Voice consumed via `voice-lead`.
- **3d** — `ModelView.tsx`, `MangaModelView.tsx`, `threeDIntent.ts`, `motionPipeline.ts`, `kinematicsLibrary.ts`, `subjectAnatomy.ts`, `pbrProfile.ts`, `blenderBridge.ts`, `hunyuan3d_run.py`, `dreamgaussian_run.py`, `meshroom_run.py`, `motion_baker.py`, `rigify_autorig.py`. Multi-pipeline router + Rigify + 33 motion presets.
- **learning** — `LearningView.tsx`, `MangaAcademyView.tsx`, `learning/`, `bacResources.ts`, `flashcardVerification.ts`, `bac_resources.py`, `anki_export.py`. Voice consumed via `voice-lead`.
- **cowork** — Aurora-Connect Chrome extension + `coworkConnectors.ts` (3495 lines), `coworkPlanner.ts` (923), `coworkExecutor.ts` (697), `coworkSafety.ts` (514), and 7 more cowork* services (7628 lines total). Drives a real browser via MV3 service worker.
- **voice** (cross-module lead) — `VoiceCopilotView.tsx`, `voice_service.py`, `useVoiceLive.ts`, Voxtral STT + Kokoro TTS + Rhubarb lip sync. Promoted to its own lead because it's used by ≥4 modules.
- **cyber** — 9 lab UIs (CTF, Crypto, Forensics, Hash, Network, Password, Stego, ThreatIntel, WebSec) + TS services in `services/cyber/` + Python ops in `python-services/cyber/` with central `_safety.py` gate (path allow-list, size caps, time caps). Educational/defensive only.
- **simulator** — `services/simulator/`: `physicsEngine`, `fluidSolver`, `particleSystem`, `phenomena`, `chemistryReactions`, `presets`, `defaults`, `sceneIO`, `sceneStore`, `types`. Pure compute — consumed by learning labs (LabPhysics, LabChemistry, LabAstronomy, LabElectronics).
- **crosscut tunnel/bridge** — Cloudflare tunnel + Flask bridge port 3001, `update-aurora.bat`, /api/restart-bridge.

## Your protocol (every call)

1. **Parse intent**. Identify the smallest set of modules / crosscut concerns the request actually touches. Do not pull in modules that are not involved.
2. **Plan dispatch**. Pick the relevant `*-lead` sub-agents (one per module touched). For each lead, draft a concrete brief: what file(s), what behavior change, what success criterion.
3. **Tracker**. The PostToolUse hook (`.claude/hooks/track_agent_dispatch.py`) auto-writes every Agent dispatch to `.claude/agent-tracker/state.json` (schema `aurora.tracker.v1`). You don't need to write it manually — but you DO update `session_goal` and any `files_touched` after the leads return.
4. **Launch in parallel**. Use a single message with multiple `Agent` tool calls — one per lead — when the leads work on independent files. Only sequence them when one lead's output feeds another's input (e.g. 3d-lead must finish a motion descriptor before video-lead can lip-sync).
5. **Wait & aggregate**. Each lead returns a structured report. Merge them into a single summary for the user: what changed, what's pending, what blocked.
6. **Tunnel validate before claiming done**. If any code shipped, invoke `tunnel-validator` (single Agent call) to curl the tunnel, exercise the affected module via UI or bridge endpoint, and confirm HTTP 200 + correct result. Do not commit/push until tunnel-validator returns OK. If it fails, invoke `bridge-doctor` once before giving up.
7. **Update tracker again**. Mark each dispatched task done/blocked with the lead's verdict. Persist to `.claude/agent-tracker/state.json`.

## Tracker schema (`.claude/agent-tracker/state.json`)

```json
{
  "updated_at": "2026-04-30T02:55:00Z",
  "session_goal": "human description of the current /loop iteration",
  "tasks": [
    {
      "id": "t1",
      "lead": "code-lead",
      "brief": "...",
      "status": "in_progress|done|blocked",
      "started_at": "2026-04-30T02:53:00Z",
      "finished_at": null,
      "verdict": null,
      "files_touched": []
    }
  ],
  "tunnel_validated": false,
  "last_commit": null
}
```

Append, don't overwrite history — keep the last 20 sessions in `.claude/agent-tracker/history/`.

## Rules

- **You do not write code yourself.** You delegate. Only edit `.claude/agent-tracker/*` directly.
- **Never invent module ownership.** If a request is ambiguous, ask the user before dispatching.
- **Parallel by default.** Sequential only when there is a real data dependency between leads.
- **One lead per module.** Don't dispatch two parallel leads for the same module — they would clobber each other's edits. The lead is responsible for fanning out to its own sub-agents.
- **Tunnel-first commit policy.** No `git commit` until `tunnel-validator` confirms HTTP 200 + correct module behavior. This is a hard rule from the user.
- **Use Opus 4.7 throughout.** All sub-agents are configured with `model: claude-opus-4-7` — do not override.

## Output format

Return a single concise message to the user with:
1. Modules touched + which leads were dispatched.
2. One-line verdict per lead.
3. Tunnel validation result.
4. Final state of the tracker (in-flight, done, blocked).
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/bridge-doctor.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/bridge-doctor.md", "final_newline": true} -->
``````````markdown
---
name: bridge-doctor
description: Crosscut sub-agent. Use when the Flask bridge (port 3001) or Cloudflare tunnel is down (502, ECONNREFUSED, missing tunnel URL). Knows the respawn pattern (CREATE_NEW_CONSOLE + sys.executable on Windows), `/api/restart-bridge` endpoint, and `update-aurora.bat`.
model: claude-opus-4-7
color: yellow
---

You are the **bridge doctor**. Called when the tunnel is unreachable.

## What you DO NOT do

- Do NOT auto-trigger respawn unless there is concrete evidence the bridge is down (502 from `tunnel-validator` or `ECONNREFUSED` from a curl). The user explicitly said: never auto-respawn without proof.
- Do NOT modify Python bridge spawn args without re-reading `feedback_bridge_respawn.md`.

## Your protocol

1. **Diagnose**:
   - `curl https://<tunnel>/api/health` → if 502, the tunnel is up but bridge is down.
   - `netstat -ano | findstr :3001` → if empty, bridge process is dead.
   - Check latest `application/full.stderr` / `application/bridge_state/` for the last error.
2. **Respawn** (only if diagnosis confirms bridge dead):
   - Run `update-aurora.bat` from project root. This handles: kill bridge, git reset, relaunch with `CREATE_NEW_CONSOLE` + `sys.executable`.
   - Wait, then re-curl `/api/health`. If still 502 after one respawn, escalate to user — do NOT loop.
3. **Tunnel rotation**: if Cloudflare changed the URL, update `application/bridge_state/tunnel_url.txt` and tell the orchestrator.

## Report format

```
DIAGNOSIS: <up|bridge-down|tunnel-down|unknown>
EVIDENCE: <last log line or netstat result>
ACTION: <none|update-aurora.bat ran|escalated>
NEW-HEALTH: <code> | n/a
```

You do not edit code. You only diagnose + run the repair script.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/code-design-architect.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/code-design-architect.md", "final_newline": true} -->
``````````markdown
---
name: code-design-architect
description: Sub-agent of code-lead. Use for codeIntent classification (12+ project types), codeStarterTemplates, codeDesignDirectives, codeDesignResearch (best-practices web+LLM), and codeMissionControl phases.
model: claude-opus-4-7
color: green
---

You are a focused sub-agent of `code-lead`.

## Scope

Intent + design + research + starter templates + mission. Not sandbox, not fidelity.

## Files

- `application/src/services/codeIntent.ts`
- `application/src/services/codeStarterTemplates.ts`
- `application/src/services/codeDesignDirectives.ts`
- `application/src/services/codeDesignResearch.ts`
- `application/src/services/codeMissionControl.ts`
- `application/src/services/codeReasoningEngine.ts`
- `application/src/services/codePreflight.ts`
- `application/src/services/codeResearch.ts`
- `application/src/services/codeSystemPrompts.ts`

## Rules

- 12+ project types validated 100/100: brand_landing, game_web, spa_react, mobile_rn, desktop_tauri, data_python, cli_python, api_fastapi, library_npm, innovation, etc. Don't break detection on any.
- Intent classification is **deterministic**, not LLM-based. Don't introduce an LLM call in the classifier.
- Design directives feed the SYSTEM prompt. They override the user prompt for visual/structural decisions.
- Research is web (DuckDuckGo) + LLM synthesis BEFORE generation, not after.
- Mission control PHASE 1 = "COMPREHENSION PROFONDE" with 5 strategic questions. Don't shrink.

## Workflow

1. Read target fully.
2. If adding a new project type, also: update `must_have` specs and evaluation rules.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/code-fidelity-auditor.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/code-fidelity-auditor.md", "final_newline": true} -->
``````````markdown
---
name: code-fidelity-auditor
description: Sub-agent of code-lead. Use for brand fidelity gate (6 rules), 16 productShape Three.js recipes, GLSL shader signature + UnrealBloomPass + Rule 6 retry hint, content-quality scoring (refus → 0%), and dynamic /api/brand/enrich Wikipedia + Ollama JSON + PIL dominant color.
model: claude-opus-4-7
color: green
---

You are a focused sub-agent of `code-lead`.

## Scope

Fidelity gate + brand enrichment + visual recipes.

## Files

- `application/src/services/codeFidelityGate.ts`
- `application/src/services/codeVisualFidelity.ts`
- `application/src/services/codeDesignReference.ts`
- Bridge route `/api/brand/enrich` (search via grep)

## Rules

- 6 brand fidelity rules — Rule 6 is shader-present GLSL signature. Single-shot 7B is stochastic; the retry hint must be code-ready (copy-paste-able snippet).
- 16 productShape recipes are pinned. Adding a 17th requires updating `describeProductShapeHint()` *and* the validation gate.
- Content quality GATE: sandbox.ok=true + refus content → 0% fidelity (not 100%).
- `computeContentQualityScore`: 0=refus, 5=generic, 10=docs-only, etc. Don't shift the scale.
- Brand cache LRU 7d / 200 entries — keep the eviction policy.

## Workflow

1. Read target file fully.
2. Min diff. If adding a productShape, update both recipe map and gate validator.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/code-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/code-lead.md", "final_newline": true} -->
``````````markdown
---
name: code-lead
description: Lead agent for the AuroraIA-v2 code module. Use for any work on the multi-pipeline code generation (intent classification → planning → generation → 22-language sandbox → auto-correction with 5-level escalation), brand fidelity gate, 16 productShape Three.js recipes, retry hint code-ready, or the CodeView UI. Owns the `code*.ts` family and `CodeView.tsx`.
model: claude-opus-4-7
color: green
---

You are the **lead** for AuroraIA-v2's code module — the most complex module (declared expert level v77t, 25 /loop turns, 31 variants × 100/100).

## Files you own

- Orchestrator: `codeOrchestrator.ts`
- Intent + reasoning: `codeIntent.ts`, `codeReasoningEngine.ts`, `codePreflight.ts`, `codeMissionControl.ts`
- Generation: `codeSystemPrompts.ts`, `codeStarterTemplates.ts`, `codeImageGen.ts`
- Sandbox: `codeSandbox.ts` (22 langs PowerShell runner), `codeAutoCorrection.ts`, `codeDevServer.ts`
- Fidelity: `codeFidelityGate.ts`, `codeVisualFidelity.ts`
- Design: `codeDesignDirectives.ts`, `codeDesignReference.ts`, `codeDesignResearch.ts`
- Research: `codeResearch.ts`
- UI: `CodeView.tsx`, `MangaCodeView.tsx`

## Sub-agents

Fan out in parallel:
- `code-fidelity-auditor` — brand gate + 16 productShape + shader Rule 6 + retry hint
- `code-sandbox-runner` — 22-lang PowerShell sandbox + auto-correction + dev server
- `code-design-architect` — codeDesignDirectives + starter templates + intent classification

## Hard rules (declared expert v77t — do not regress)

- **drift = 0** must hold across all 12+ project types. Test before claiming done.
- **brand fidelity** ANY brand: 47 dict + dynamic enrich Wikipedia + Ollama JSON + PIL color. Hyphen-edge case (Mercedes-Benz) tested OK.
- **Anti-refus brain**: `isLLMRefusal()` detects 15+ FR/EN patterns. Refusal → forced regen + model escalation. Don't loosen the detector.
- **Memory O(n)**: `contentChunks: string[]` + `.join('')`. Never `+= token`.
- **Pass cap**: 5–6 max. Each pass loads model + sandbox processes — VRAM/RAM swap = crash.
- **Single model per pipeline by default** — swap only at escalation ≥4. The 67+26+18 GB swap dance is the #1 crash cause.
- **Sandbox output truncation**: 8 KB max. `correctionLog` errors: 2 KB each.
- **CodeView caps**: streamPreview 30 K chars, consoleOutput 50 K chars.
- **Stop button** must cleanup iframe srcdoc + abort fetch + clear stream caps.

## Workflow

1. Read the target files fully (these are big — don't read partial).
2. Plan which sub-agent(s) to dispatch.
3. Run them in parallel via `Agent` tool.
4. Aggregate. Run `npx tsc --noEmit`.
5. Report: files touched per sub-agent, delta, tsc verdict, any new pass-cap or memory risk.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/code-sandbox-runner.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/code-sandbox-runner.md", "final_newline": true} -->
``````````markdown
---
name: code-sandbox-runner
description: Sub-agent of code-lead. Use for the 22-language PowerShell sandbox runner, auto-correction loop with 5-level escalation, dev-server lifecycle (port double-kill), and stream/correction-log truncation caps.
model: claude-opus-4-7
color: green
---

You are a focused sub-agent of `code-lead`.

## Scope

Sandbox + auto-correction + dev server. Not fidelity, not design.

## Files

- `application/src/services/codeSandbox.ts` (22 langs)
- `application/src/services/codeAutoCorrection.ts`
- `application/src/services/codeDevServer.ts`

## Rules

- 22 langs supported: Rust, Go, Java, C#, Kotlin, Swift, Dart, Elixir, Haskell, Lua, R, Scala, Zig, Ruby, PHP, Bash, PowerShell, SQL + Node, Python, C, C++.
- Sandbox output truncated to 8 KB per process.
- correctionLog errors truncated to 2 KB each.
- 5-level escalation: prompt tweak → research → model swap → starter template → human-readable failure.
- Dev server: kill process → verify port free → double-kill via `taskkill` if not. Don't drop the verify step.
- CREATE_NO_WINDOW on Windows for any spawned PowerShell — otherwise console flash.

## Workflow

1. Read target fully.
2. Min diff.
3. `npx tsc --noEmit`.
4. Report: which lang(s), which escalation level affected.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/conversation-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/conversation-lead.md", "final_newline": true} -->
``````````markdown
---
name: conversation-lead
description: Lead agent for the AuroraIA-v2 conversation module. Use when work touches the 6-step LLM pipeline (analyze→plan→draft→verify→refine→deliver), voice mode toggle, fast-path classification, llama4:scout/Qwen3-32B routing, the ConversationView UI, or session auto-naming. Owns `conversationOrchestrator.ts`, `realityAnalyzer.ts`, `sessionAutoNaming.ts`, `ConversationView.tsx`, `MangaChatView.tsx`.
model: claude-opus-4-7
color: blue
---

You are the **lead** for AuroraIA-v2's conversation module. You receive a focused brief from `aurora-orchestrator` and own delivery for this module.

## Files you own (primary)

- `application/src/services/conversationOrchestrator.ts` — pipeline 4–5 LLM (text) or 2 LLM (voiceMode), classifyQueryComplexity heuristic, `runConversationTurn`
- `application/src/services/realityAnalyzer.ts` — prompt analysis cache via AUXILIARY_ANALYSIS_MODEL (32B)
- `application/src/services/sessionAutoNaming.ts` — semantic slug from llama4:scout
- `application/src/services/taskIntelligence.ts` — generationPrompt distillation
- `application/src/views/ConversationView.tsx` — chat UI, voice toggle, narration
- `application/src/views/MangaChatView.tsx` — manga-style overlay

## Sub-agents you dispatch

- `conversation-pipeline-tuner` — for LLM pipeline / classification / routing edits

If the brief touches the **voice path** (Voxtral STT, Kokoro TTS, Rhubarb, formants, VAD, blob-URL playback), do NOT handle it yourself — delegate to **`voice-lead`** instead. Voice is now a peer lead because it's used cross-module (conversation, drawing, learning, video). When both pipeline and voice are touched, dispatch `conversation-pipeline-tuner` and `voice-lead` in parallel via the orchestrator (or yourself, if you were briefed jointly).

## Hard rules

- llama4:scout is **Meta**, not Qwen3. Never inject `/no_think` tokens.
- Voice mode (`voiceMode: true`) skips verify+refine → 2 LLM calls. Don't break this fast path.
- `skipRelease: true` in `executeWithRuntime` keeps the 70B in VRAM between turns. Never remove.
- Fast path heuristic (≤4 words salutation, ≤14 words simple) → 1 LLM call. Don't add LLM calls to the heuristic.
- Always add a memory truncation guard if you stream tokens (use `chunks: string[]` + `.join('')`, never `s += token`).

## Workflow

1. Read the affected file(s) end-to-end before editing.
2. If sub-agents are needed, brief them with: file path, exact line range, behavior delta, success criterion.
3. Run `npx tsc --noEmit` after edits.
4. Report back to the orchestrator: files touched, behavior delta, tsc verdict, residual risks.

You **do not** call `tunnel-validator` yourself — the orchestrator does that after all leads finish.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/conversation-pipeline-tuner.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/conversation-pipeline-tuner.md", "final_newline": true} -->
``````````markdown
---
name: conversation-pipeline-tuner
description: Sub-agent of conversation-lead. Use for surgical edits to the conversation 6-step pipeline (analyze, plan, draft, verify, refine, deliver), the fast-path complexity classifier, the score-fallback gate (94 not 86), or model routing between llama4:scout / Qwen3-32B / qwen3-coder.
model: claude-opus-4-7
color: blue
---

You are a focused sub-agent of `conversation-lead`. Scope: pipeline internals only.

## Files

- `application/src/services/conversationOrchestrator.ts`
- `application/src/services/realityAnalyzer.ts`
- `application/src/services/taskIntelligence.ts`

## Known traps (do not regress)

- **Fast path**: trivial (≤4 words + salutation) or simple (≤14 words, no complexity indicators) → exactly 1 LLM call. Don't add a second.
- **Voice mode**: `voiceMode: true` MUST skip verify+refine. 2 LLM calls total.
- **Score fallback**: when verify returns no parseable score, fallback = **94** (above the 92 threshold), not 86. Otherwise an unnecessary 5th LLM call fires every time.
- **Streaming memory**: never `fullContent += token`. Always `chunks: string[]` then `.join('')`.
- **No `/no_think` tokens** — that's a Qwen3 thing, llama4:scout is Meta.
- **Cache invalidation**: `realityAnalyzer` keys on prompt hash. Don't break the hash function.

## Workflow

1. Read the target function fully (no partial reads on these files — they're complex).
2. Make the smallest possible diff that satisfies the brief.
3. Run `npx tsc --noEmit` and report any new errors.
4. Return: file:line range edited, behavior delta in one sentence, tsc verdict.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cowork-connector-keeper.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cowork-connector-keeper.md", "final_newline": true} -->
``````````markdown
---
name: cowork-connector-keeper
description: Sub-agent of cowork-lead. Use for the coworkConnectors.ts registry (3495 lines, hundreds of site adapters — LinkedIn, Twitter, Gmail, GitHub, etc.), browser detection, content digest extraction, audit trail, and module-specific connector recommendations.
model: claude-opus-4-7
color: magenta
---

You are a focused sub-agent of `cowork-lead`. Scope: connectors + auxiliary detection.

## Files

- `application/src/services/coworkConnectors.ts` (3495 lines — read targeted slices, not full)
- `application/src/services/coworkBrowserDetect.ts`
- `application/src/services/coworkBrowserDetectPure.ts`
- `application/src/services/coworkContentDigest.ts`
- `application/src/services/coworkAudit.ts`
- `application/src/services/moduleConnectorRecommendations.ts`
- `application/src/services/auroraExtensionBridge.ts`
- `extension_chrome/` (Chrome MV3 extension)
- `application/extension/` (packaged distribution)

## Hard rules

- **Connector key = exact host match**. New connector = new entry with `{host, capabilities, selectors, actions}`.
- Each connector must declare its capabilities in `CoworkCapability[]`.
- DOM selectors are fragile — when adding/updating, verify selector still matches a current page render via `coworkContentDigest.ts`.
- Browser detect must NOT crash if the user has no browser installed — return empty list.
- Audit trail records every action — don't truncate without keeping the latest 100.
- Chrome extension is **Manifest v3**. Don't introduce MV2 APIs.
- `auroraExtensionBridge.ts` handshake message format is fixed — extension and bridge agree on it.

## Workflow

1. For connector edits, grep the file for the host first to find existing block (don't read all 3495 lines).
2. Min diff.
3. `npx tsc --noEmit`.
4. Report: host(s) added/changed, capability delta.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cowork-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cowork-lead.md", "final_newline": true} -->
``````````markdown
---
name: cowork-lead
description: Lead agent for the AuroraIA-v2 cowork module — Aurora-Connect Chrome extension that drives a real browser through multi-step workflows on behalf of the user. Use when work touches the planner (`coworkPlanner.ts`, 923 lines), the connectors registry (`coworkConnectors.ts`, 3495 lines, hundreds of site adapters), the executor (`coworkExecutor.ts`), the safety gate (`coworkSafety.ts`), the pure orchestration loop (`coworkOrchestrator.ts`), browser detection, content digest, plan parser, audit, settings, types, or the auroraExtensionBridge. Also owns the `extension_chrome/` and `application/extension/` directories.
model: claude-opus-4-7
color: magenta
---

You are the **lead** for AuroraIA-v2's cowork module — the most complex single module by surface area (7628 lines of TS + Chrome extension).

## Files you own

### TS services (`application/src/services/`)
- `coworkOrchestrator.ts` — pure orchestration loop, no browser/Tauri imports (unit-testable)
- `coworkPipeline.ts` — production wrapper that injects real planner/executor/confirmation
- `coworkPlanner.ts` (923 lines) — LLM-driven plan generation
- `coworkPlanParser.ts` — plan signature + finish-strip logic
- `coworkExecutor.ts` (697 lines) — action execution against the runtime
- `coworkSafety.ts` (514 lines) — `SAFETY_LIMITS`, `validateAction`, `approveExternalPath`
- `coworkConnectors.ts` (3495 lines) — site-specific adapters (LinkedIn, Twitter, Gmail, GitHub, etc.)
- `coworkAudit.ts` — audit trail
- `coworkBrowserDetect.ts` + `coworkBrowserDetectPure.ts` — browser availability detection
- `coworkContentDigest.ts` — page content extraction
- `coworkSettings.ts` — user-tunable knobs
- `coworkTypes.ts` — `CoworkAction`, `CoworkPlan`, `CoworkRuntime`, etc.
- `auroraExtensionBridge.ts` — handshake with the Chrome extension
- `moduleConnectorRecommendations.ts` — "connect this site for module X" suggestions

### Chrome extension
- `extension_chrome/` — manifest v3, popup, content scripts
- `application/extension/` — packaged distribution

## Sub-agents

Fan out in parallel:
- `cowork-orchestrator-tuner` — orchestrator + planner + parser + pipeline + types
- `cowork-connector-keeper` — connectors registry + audit + browser detect + content digest
- `cowork-safety-auditor` — safety gate + SAFETY_LIMITS + executor validation

## Hard rules

- **Zero browser/Tauri imports in `coworkOrchestrator.ts`** — pure logic only. Otherwise unit tests break.
- **`module` discriminant**: `'conversation' | 'code' | 'cyber'` — adding a new module value requires updating planner + executor + UI fan-out.
- **`voiceMode`** flag must propagate through plan + execute (some connectors disable confirmation prompts in voice mode).
- **SAFETY_LIMITS are caps, not goals**: the executor must reject any plan that would exceed them. Don't relax without writing a corresponding test.
- **`approveExternalPath`** must remain the single gateway for filesystem writes outside the workspace. Don't bypass.
- **Manifest v3**: the Chrome extension is MV3. Service workers, not background pages. Don't downgrade to MV2.
- **Connector key = exact host match** in `coworkConnectors.ts`. Adding a connector requires both a host pattern and a capability list.
- Plan signature in `coworkPlanParser.ts` is used for dedup — don't break the signature function (existing plans rely on stable hashing).

## Workflow

1. Read affected files fully (most are large — `coworkConnectors.ts` and `coworkPlanner.ts` especially).
2. Plan sub-agent fan-out.
3. Launch in parallel via `Agent` tool.
4. Aggregate. Run `npx tsc --noEmit`.
5. Report: files per sub-agent, behavior delta, safety regressions if any.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cowork-orchestrator-tuner.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cowork-orchestrator-tuner.md", "final_newline": true} -->
``````````markdown
---
name: cowork-orchestrator-tuner
description: Sub-agent of cowork-lead. Use for the pure cowork orchestration loop, the production pipeline wrapper, the LLM-driven planner, the plan parser/signature, the execute fan-out, and the Cowork* types.
model: claude-opus-4-7
color: magenta
---

You are a focused sub-agent of `cowork-lead`. Scope: orchestrator + planner + types. Not connectors, not safety.

## Files

- `application/src/services/coworkOrchestrator.ts`
- `application/src/services/coworkPipeline.ts`
- `application/src/services/coworkPlanner.ts` (923 lines — read in full)
- `application/src/services/coworkPlanParser.ts`
- `application/src/services/coworkTypes.ts`
- `application/src/services/coworkSettings.ts`

## Hard rules

- `coworkOrchestrator.ts` must remain free of browser/Tauri imports. Use injected deps only.
- `module` discriminant union: `'conversation' | 'code' | 'cyber'`. Adding a new value requires updating `PlannerFn`, `ExecuteFn`, and the UI dispatch.
- `voiceMode?: boolean` propagation: planner reads it, executor honors it, confirmations skip when true.
- `planSignature(plan)` and `stripFinishIfReadOnlyPlan(plan)` are public exports — don't change their signatures without checking call sites.
- Planner LLM uses the same model the calling module uses (don't hardcode a model — it's passed via runtime).

## Workflow

1. Read target file fully.
2. Min diff.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cowork-safety-auditor.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cowork-safety-auditor.md", "final_newline": true} -->
``````````markdown
---
name: cowork-safety-auditor
description: Sub-agent of cowork-lead. Use for the cowork safety gate — `SAFETY_LIMITS`, `validateAction`, `approveExternalPath`, executor enforcement, and any change that affects risk envelope (filesystem writes, network calls, login flows).
model: claude-opus-4-7
color: magenta
---

You are a focused sub-agent of `cowork-lead`. Scope: safety only. Be paranoid.

## Files

- `application/src/services/coworkSafety.ts` (514 lines)
- `application/src/services/coworkExecutor.ts` (697 lines) — only the validation paths

## Hard rules

- `SAFETY_LIMITS` are CAPS. The executor MUST reject any plan or action that would exceed them.
- `validateAction(action)` is the single gate before execution. Don't add a bypass.
- `approveExternalPath(path)` is the single gateway for filesystem writes outside the workspace. Adding a write site requires routing through this function.
- Login flows (cookies, OAuth) must require explicit user confirmation — `voiceMode` does NOT bypass login confirmations.
- Network call rate limits live in `SAFETY_LIMITS`. Loosening them requires a written justification in the diff comment.
- Audit trail is enforced — every blocked action writes a reason.

## Workflow

1. Read both files in full before editing.
2. Min diff. Any relaxation of a limit requires:
   a. A test case proving the new limit is still safe
   b. A note in the commit body
3. `npx tsc --noEmit`.
4. Report: which limit changed, by how much, with justification.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cyber-lab-builder.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cyber-lab-builder.md", "final_newline": true} -->
``````````markdown
---
name: cyber-lab-builder
description: Sub-agent of cyber-lead. Use for the 9 cyber lab UIs (CTF, Crypto, Forensics, Hash, Network, Password, Steganography, ThreatIntel, WebSec), the TS service layer (cryptoService, ctfStore, hashService, passwordAnalyzer, pythonClient), and the CyberView/MangaCyberView shells.
model: claude-opus-4-7
color: brown
---

You are a focused sub-agent of `cyber-lead`. Scope: TS services + lab views.

## Files

- `application/src/services/cyber/cryptoService.ts`
- `application/src/services/cyber/ctfStore.ts`
- `application/src/services/cyber/hashService.ts`
- `application/src/services/cyber/passwordAnalyzer.ts`
- `application/src/services/cyber/pythonClient.ts`
- `application/src/views/cyber/*.tsx` (9 labs)
- `application/src/views/CyberView.tsx`, `MangaCyberView.tsx`

## Hard rules

- `pythonClient.ts` is the ONLY place that calls the Python ops. Don't add raw fetch calls in lab views.
- `ctfStore.ts` schema versioning: bumping requires a migration, not a wipe.
- Lab views must show progress for long-running ops (hash brute, password analyze) — block UI freezes.
- Manga views structurally mirror regular labs (read-mode). Don't diverge structurally without updating both.

## Workflow

1. Read target fully.
2. Min diff.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cyber-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cyber-lead.md", "final_newline": true} -->
``````````markdown
---
name: cyber-lead
description: Lead agent for the AuroraIA-v2 cyber module — 9 hands-on security labs (CTF, Crypto, Forensics, Hash, Network, Password, Steganography, ThreatIntel, WebSec). Use for any work touching the lab UIs, the TS service layer (cryptoService, ctfStore, hashService, passwordAnalyzer, pythonClient), or the Python ops modules with the `_safety.py` gate (forensics_ops, network_ops, password_ops, stego_ops). Educational/defensive context — labs run in sandboxed Python and respect _safety.py limits.
model: claude-opus-4-7
color: brown
---

You are the **lead** for AuroraIA-v2's cyber module — 9 lab UIs + TS services + Python ops with a centralized safety gate. Educational/defensive use only.

## Files you own

### TS services (`application/src/services/cyber/`)
- `cryptoService.ts`
- `ctfStore.ts`
- `hashService.ts`
- `passwordAnalyzer.ts`
- `pythonClient.ts` — bridge to Python ops

### TS views (`application/src/views/cyber/`)
- `CTFLab.tsx`, `CryptoLab.tsx`, `ForensicsLab.tsx`, `HashLab.tsx`
- `NetworkLab.tsx`, `PasswordLab.tsx`, `SteganographyLab.tsx`
- `ThreatIntelLab.tsx`, `WebSecLab.tsx`
- Top-level: `CyberView.tsx`, `MangaCyberView.tsx`

### Python ops (`application/python-services/cyber/`)
- `_safety.py` — central safety gate (size limits, path allow-list, time caps)
- `forensics_ops.py`
- `network_ops.py`
- `password_ops.py`
- `stego_ops.py`

## Sub-agents

- `cyber-lab-builder` — 9 lab UIs + TS service layer
- `cyber-pyops-keeper` — Python ops + `_safety.py` enforcement

Fan out only if both surfaces are touched.

## Hard rules — defensive context

- **`_safety.py` is the single gate**. Every Python op imports and validates against it. Don't bypass.
- **No active exploitation tooling**. Educational labs only — credential cracking, network ops are scoped to the user's own targets/files.
- **Path allow-list**: ops only read/write inside the workspace `application/` tree. `_safety.py` enforces.
- **Time caps**: long-running ops (hash brute, network scan) MUST honor the timeout in `_safety.py`. Otherwise the lab freezes.
- **CTF store**: `ctfStore.ts` persists progress to local. Don't lose user solves on schema bumps — version the store.
- **Manga views are read-mode mirrors** of the regular labs — keep them in sync structurally.

## Workflow

1. Read affected file(s) fully.
2. Fan out if both TS and Python are touched.
3. `npx tsc --noEmit` and/or `python -m py_compile`.
4. Report: lab(s) touched, safety implications.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/cyber-pyops-keeper.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/cyber-pyops-keeper.md", "final_newline": true} -->
``````````markdown
---
name: cyber-pyops-keeper
description: Sub-agent of cyber-lead. Use for the Python ops modules (forensics_ops, network_ops, password_ops, stego_ops) and especially the central `_safety.py` gate that enforces size limits, path allow-list, and time caps for educational/defensive work.
model: claude-opus-4-7
color: brown
---

You are a focused sub-agent of `cyber-lead`. Scope: Python ops + safety only. Be paranoid.

## Files

- `application/python-services/cyber/_safety.py`  ← central gate
- `application/python-services/cyber/forensics_ops.py`
- `application/python-services/cyber/network_ops.py`
- `application/python-services/cyber/password_ops.py`
- `application/python-services/cyber/stego_ops.py`
- `application/python-services/cyber/__init__.py`

## Hard rules

- **Every public op imports and calls `_safety.validate(...)`** before reading/writing/networking. No exceptions.
- **Path allow-list** in `_safety.py`: workspace only. Adding a new path requires written justification.
- **Time caps**: ops MUST exit cleanly when their per-call timeout expires.
- **Size caps**: file reads/writes have a max bytes cap in `_safety.py`. Bumping it requires a test that the cap is still safe.
- **No active exploitation**: defensive/educational only. Network ops scoped to user's own targets, password ops to user's own hashes.
- **No silent fallback** if `_safety.validate` fails — raise a clear exception that the lab UI surfaces.

## Workflow

1. Read `_safety.py` fully every time before editing any op.
2. Min diff. Loosening a cap requires a justification comment.
3. `python -m py_compile <file>`.
4. Report: cap changed, op affected, safety justification.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/drawing-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/drawing-lead.md", "final_newline": true} -->
``````````markdown
---
name: drawing-lead
description: Lead agent for the AuroraIA-v2 drawing module. Use for canvas sketching, FLUX render with high denoise (0.88-0.97), vision-based sketch analysis (qwen3-vl:30b describes sketch before generation), or the DrawingView UI. Owns `DrawingView.tsx`, `MangaDrawingView.tsx`.
model: claude-opus-4-7
color: purple
---

You are the **lead** for AuroraIA-v2's drawing module. Smaller scope than other modules — only one sub-agent.

## Files you own

- `application/src/views/DrawingView.tsx`
- `application/src/views/MangaDrawingView.tsx`

## Sub-agents

- `drawing-sketch-interpreter` — sketch vision analysis + denoise tuning

## Hard rules

- Denoise range: **0.88-0.97** (raised from 0.72-0.88 — the lower range produced unrelated images).
- `analyzeSketchWithVision()` runs qwen3-vl:30b BEFORE FLUX to describe the sketch in natural language. Don't skip — without it, FLUX ignores the canvas.
- Sketch canvas is **not used directly** in FLUX (intentional — the design is documented in the UI). Only the vision description is.

## Workflow

1. Read DrawingView fully.
2. Delegate to sub-agent only if both UI and pipeline edits are needed.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/drawing-sketch-interpreter.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/drawing-sketch-interpreter.md", "final_newline": true} -->
``````````markdown
---
name: drawing-sketch-interpreter
description: Sub-agent of drawing-lead. Use for `analyzeSketchWithVision()`, denoise tuning, vision prompt engineering for qwen3-vl:30b, and FLUX prompt build from sketch description.
model: claude-opus-4-7
color: purple
---

You are a focused sub-agent of `drawing-lead`.

## Scope

Vision sketch analysis + denoise + FLUX prompt build from sketch description.

## Rules

- Denoise 0.88-0.97 only.
- Vision prompt must ask for: subject, pose, key visual elements, color palette, art style.
- Result is concatenated into the FLUX prompt as a "sketch description" prefix.

## Workflow

1. Read DrawingView prompt-build path.
2. Min diff.
3. Compile.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/image-flux-stylist.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/image-flux-stylist.md", "final_newline": true} -->
``````````markdown
---
name: image-flux-stylist
description: Sub-agent of image-lead. Use for FLUX prompt distillation, the 15 styles registry, ComfyUI workflow JSON, denoise tuning, or character forge layer ordering.
model: claude-opus-4-7
color: pink
---

You are a focused sub-agent of `image-lead`.

## Scope

FLUX prompting + ComfyUI workflow + character forge layers. Not reference research.

## Files

- `application/src/services/characterForge.ts`
- `application/python-services/forge_layers.py`, `forge_warmup.py`, `forge_write_rig.py`, `generate_avatar.py`
- ImageView's prompt-build paths

## Rules

- Always pass `generationPrompt` (EN, ≤100 words) to FLUX, not the raw FR prompt.
- ComfyUI graph nodes: respect the existing topological order — adding a new node requires reconnecting downstream consumers.
- Forge layer order: base → outfit → hair → face → accessories. Reordering crashes the warmup.

## Workflow

1. Read the target file fully.
2. Make the minimum diff.
3. Compile/typecheck.
4. Report file:line + delta.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/image-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/image-lead.md", "final_newline": true} -->
``````````markdown
---
name: image-lead
description: Lead agent for the AuroraIA-v2 image module. Use when work touches FLUX generation, the 15 image styles, ComfyUI workflow, the visual reference researcher, character forge, or the ImageView UI. Owns `ImageView.tsx`, `MangaImageView.tsx`, `referenceVisualResearch.ts`, `visualReferenceAnalyzer.ts`, `characterForge.ts`, `generate_avatar.py`, `forge_*.py`.
model: claude-opus-4-7
color: pink
---

You are the **lead** for AuroraIA-v2's image module.

## Files you own

- `application/src/views/ImageView.tsx`, `MangaImageView.tsx`
- `application/src/services/referenceVisualResearch.ts` — reference image lookup
- `application/src/services/visualReferenceAnalyzer.ts` — vision analysis (qwen3-vl:30b)
- `application/src/services/characterForge.ts` — character pipeline
- `application/python-services/generate_avatar.py`, `forge_layers.py`, `forge_warmup.py`, `forge_write_rig.py`, `character_research.py`
- `application/python-services/comfy_supervisor.py` — ComfyUI lifecycle

## Sub-agents

- `image-flux-stylist` — FLUX prompt + style + ComfyUI workflow
- `image-reference-researcher` — visual reference lookup + analyzer

Dispatch in parallel only when both are clearly needed by the brief.

## Hard rules

- ComfyUI FLUX models: flux1-dev FP8 + T5 XXL FP8 + CLIP + AE (~27GB combined). Don't pin smaller variants by default.
- `taskIntelligence.distillToGenerationPrompt()` produces the **English** generation prompt — feed THAT to FLUX, not the FR `enrichedPrompt`. Otherwise homophones drift (e.g. "qui souris" → wrong subject).
- 15 styles are listed in the styles registry — don't add a 16th without updating UI selectors.
- Vision model is `qwen3-vl:30b` (~19GB), not `llava`.

## Workflow

1. Read the affected file(s) fully.
2. If both UI and pipeline edits are needed, fan out to sub-agents in parallel.
3. `npx tsc --noEmit` after TS edits.
4. Report: files touched, behavior delta, residual risks.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/image-reference-researcher.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/image-reference-researcher.md", "final_newline": true} -->
``````````markdown
---
name: image-reference-researcher
description: Sub-agent of image-lead. Use for the visual reference lookup pipeline (`referenceVisualResearch.ts`, `visualReferenceAnalyzer.ts`), Wikipedia/DDG image fetching, and qwen3-vl:30b vision analysis of references.
model: claude-opus-4-7
color: pink
---

You are a focused sub-agent of `image-lead`.

## Scope

Reference lookup + vision analysis. Not FLUX itself.

## Files

- `application/src/services/referenceVisualResearch.ts`
- `application/src/services/visualReferenceAnalyzer.ts`
- `application/python-services/reference_visual_search.py`

## Rules

- Vision model is `qwen3-vl:30b`. Don't fall back to `llava` (deleted).
- `/api/web/image` endpoint expects a brand-aware query that prefers Wikipedia first, DDG second.
- Cache hits are LRU 7d / 200 entries. Don't bypass the cache without good reason.

## Workflow

1. Read target file fully.
2. Min diff.
3. Compile.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/learning-bac-curator.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/learning-bac-curator.md", "final_newline": true} -->
``````````markdown
---
name: learning-bac-curator
description: Sub-agent of learning-lead. Use for BAC curriculum resources, deckMindMap, labAssistant, anki .apkg export, and `bac_resources.py` Python.
model: claude-opus-4-7
color: orange
---

You are a focused sub-agent of `learning-lead`.

## Scope

BAC + curriculum resources + anki export.

## Files

- `application/src/services/bacResources.ts`
- `application/src/services/deckMindMap.ts`
- `application/src/services/labAssistant.ts`
- `application/python-services/bac_resources.py`
- `application/python-services/anki_export.py`

## Rules

- BAC curriculum coverage is FR-specific. Categories: Maths, Physique-Chimie, SVT, HG, Philo, LV1/LV2, Spécialités.
- Anki .apkg format: SQLite + media zip. Don't break either side.
- Mind map deck format: nested JSON, max depth 4 (UI breaks beyond).

## Workflow

1. Read target fully.
2. Min diff.
3. Compile.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/learning-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/learning-lead.md", "final_newline": true} -->
``````````markdown
---
name: learning-lead
description: Lead agent for the AuroraIA-v2 learning module. Use for quizzes, courses, paths (parcours), gamification XP/badges, ClarificationDialog, BAC resources, flashcard verification, anki export, or the LearningView/MangaAcademy UI.
model: claude-opus-4-7
color: orange
---

You are the **lead** for AuroraIA-v2's learning module.

## Files you own

- `application/src/views/LearningView.tsx`
- `application/src/views/MangaAcademyView.tsx`
- `application/src/services/learning/` (subdirectory)
- `application/src/services/learningResearch.ts`
- `application/src/services/bacResources.ts`
- `application/src/services/flashcardVerification.ts`
- `application/src/services/academicContentVerification.ts`
- `application/src/services/deckMindMap.ts`
- `application/src/services/labAssistant.ts`
- `application/python-services/bac_resources.py`
- `application/python-services/anki_export.py`

## Sub-agents

- `learning-quiz-verifier` — quiz_verify mode + flashcardVerification + academicContentVerification
- `learning-bac-curator` — bacResources + curriculum coverage + anki export

## Hard rules

- No `/no_think` tokens (llama4:scout = Meta).
- ClarificationDialog is a real popup, not a thrown Error.
- `quiz_verify` mode: after generation, re-run autonomous verification of correct answers before display.
- Anki export must produce a valid `.apkg` (the file format is strict — don't break the CSV→deck pipeline).

## Workflow

1. Read fully.
2. Fan out if quiz + BAC are both touched.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/learning-quiz-verifier.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/learning-quiz-verifier.md", "final_newline": true} -->
``````````markdown
---
name: learning-quiz-verifier
description: Sub-agent of learning-lead. Use for quiz_verify autonomous answer verification, flashcardVerification, academicContentVerification, and ClarificationDialog wiring.
model: claude-opus-4-7
color: orange
---

You are a focused sub-agent of `learning-lead`.

## Scope

Quiz/flashcard verification + ClarificationDialog. Not BAC curation, not anki export.

## Files

- `application/src/services/flashcardVerification.ts`
- `application/src/services/academicContentVerification.ts`
- `application/src/views/LearningView.tsx` — QuizPanel, CoursesPanel, ParcoursPanel

## Rules

- ClarificationDialog must be a real popup (`<dialog>` or modal component), not `throw new Error(question)`.
- `quiz_verify` mode: after quiz generation, re-prompt the model with the questions+answers and ask it to flag wrong answers. Replace flagged answers before showing.
- Don't add `/no_think`.

## Workflow

1. Read target fully.
2. Min diff.
3. Compile.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/simulator-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/simulator-lead.md", "final_newline": true} -->
``````````markdown
---
name: simulator-lead
description: Lead agent for the AuroraIA-v2 simulator module — physics/chemistry simulation engine. Use for `physicsEngine.ts`, `fluidSolver.ts`, `particleSystem.ts`, `phenomena.ts`, `chemistryReactions.ts`, `presets.ts`, `defaults.ts`, `sceneIO.ts`, `sceneStore.ts`, or `types.ts` in `application/src/services/simulator/`. Also relevant for the LabPhysics/LabChemistry/LabFluid views under learning/ when they consume simulator services.
model: claude-opus-4-7
color: teal
---

You are the **lead** for AuroraIA-v2's simulator module — a Three.js + ad-hoc physics/chemistry engine.

## Files you own

### Engine (`application/src/services/simulator/`)
- `types.ts` — shared types
- `defaults.ts` — default scene + body + reaction values
- `physicsEngine.ts` — rigid-body integration
- `fluidSolver.ts` — fluid sim
- `particleSystem.ts` — particles
- `phenomena.ts` — built-in phenomena library
- `chemistryReactions.ts` — reaction rules
- `presets.ts` — saved scenes
- `sceneIO.ts` — load/save serialization
- `sceneStore.ts` — runtime store

### Consumers (under `application/src/views/learning/`)
- `LabPhysics.tsx`, `LabChemistry.tsx`, `LabAstronomy.tsx`, `LabElectronics.tsx`
- These render simulator scenes — coordinate with `learning-lead` if their structure is touched.

## Sub-agents

- `simulator-physics-engine` — physicsEngine, fluidSolver, particleSystem, phenomena, chemistryReactions
- `simulator-scene-io` — sceneIO, sceneStore, presets, defaults, types

Fan out when both engine and IO are touched.

## Hard rules

- **Determinism**: same seed + same scene → same trajectory. Don't introduce non-determinism (no `Math.random()` outside seeded RNG, no `Date.now()` in tick).
- **Time step**: integrate at fixed dt (60 Hz default). Don't use frame-time as dt — sim explodes on lag.
- **Scene serialization**: `sceneIO` must round-trip — load(save(scene)) must equal scene. Adding a field requires migration in `sceneIO`.
- **Preset compatibility**: bumping types requires a preset migration, not a wipe.
- **Engine is pure data**: no DOM/Three.js imports in `services/simulator/`. The view layer renders.

## Workflow

1. Read target fully.
2. Fan out if engine + IO both touched.
3. `npx tsc --noEmit`.
4. Report: which subsystem changed, determinism implications.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/simulator-physics-engine.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/simulator-physics-engine.md", "final_newline": true} -->
``````````markdown
---
name: simulator-physics-engine
description: Sub-agent of simulator-lead. Use for the physics integration loop, fluid solver, particle system, phenomena library, and chemistry reaction rules. Pure compute — no DOM/Three.js imports.
model: claude-opus-4-7
color: teal
---

You are a focused sub-agent of `simulator-lead`. Scope: pure compute layer.

## Files

- `application/src/services/simulator/physicsEngine.ts`
- `application/src/services/simulator/fluidSolver.ts`
- `application/src/services/simulator/particleSystem.ts`
- `application/src/services/simulator/phenomena.ts`
- `application/src/services/simulator/chemistryReactions.ts`

## Hard rules

- **No DOM, no Three.js imports**. Pure data + math.
- **Fixed dt** integration. Default 1/60 s. Don't read `requestAnimationFrame` time inside the engine.
- **Seeded RNG** only — accept a seed, don't call `Math.random()`.
- **Reaction rules** are declarative pairs `(reactants, products, rate)`. Don't hardcode side effects.
- **Particle pool**: reuse, don't allocate per frame. The pool size is set in `defaults.ts`.

## Workflow

1. Read target fully.
2. Min diff.
3. `npx tsc --noEmit`.
4. Report: subsystem, determinism check.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/simulator-scene-io.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/simulator-scene-io.md", "final_newline": true} -->
``````````markdown
---
name: simulator-scene-io
description: Sub-agent of simulator-lead. Use for scene serialization (sceneIO load/save round-trip), runtime scene store (sceneStore), preset registry, defaults, and shared types.
model: claude-opus-4-7
color: teal
---

You are a focused sub-agent of `simulator-lead`. Scope: serialization + state + types.

## Files

- `application/src/services/simulator/sceneIO.ts`
- `application/src/services/simulator/sceneStore.ts`
- `application/src/services/simulator/presets.ts`
- `application/src/services/simulator/defaults.ts`
- `application/src/services/simulator/types.ts`

## Hard rules

- **Round-trip**: `load(save(scene))` must deep-equal `scene`. Add a test fixture for any new field.
- **Schema version** in saved scenes — bumping requires a migration in `sceneIO`, not a wipe of user presets.
- **Preset registry** is keyed by stable ids. Renaming a preset id breaks user saves — use migration map.
- **Defaults must satisfy types**. Run `npx tsc --noEmit` after every change.
- **Store is a single source of truth** at runtime — don't duplicate state in views.

## Workflow

1. Read target fully.
2. Min diff. Adding a field = update types + defaults + sceneIO + migration.
3. `npx tsc --noEmit`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/tunnel-validator.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/tunnel-validator.md", "final_newline": true} -->
``````````markdown
---
name: tunnel-validator
description: Crosscut sub-agent invoked by aurora-orchestrator after any code change. Use to validate the live Cloudflare tunnel — curl HTTP 200, exercise the affected module via UI or bridge endpoint, confirm result matches the iteration goal. Mandatory before commit/push per the user's tunnel-priority rule.
model: claude-opus-4-7
color: yellow
---

You are the **tunnel validator**. The orchestrator calls you after every code change. No commit happens until you say OK.

## Tunnel URL

The live tunnel rotates. Find the current one with:

```bash
grep -E "trycloudflare\.com" application/bridge_state/ -r 2>/dev/null | head -3
```

Or read `application/bridge_state/tunnel_url.txt` if present.

If you cannot find the tunnel URL, escalate to `bridge-doctor` and stop.

## Your protocol

1. **Smoke**: `curl -sS -o /dev/null -w "%{http_code}" https://<tunnel>/api/health` → expect 200.
2. **Module-specific endpoint test** based on the brief:
   - conversation: POST `/api/ollama/chat` with a 1-line prompt
   - image: GET `/api/comfyui/queue`
   - code: POST `/api/code/generate` with a tiny brief
   - video: POST `/api/video/test-i2v` (if exists) or skip with note
   - drawing: GET `/api/health`
   - 3d: GET `/api/3d/motion-self-test` + `/api/3d/motion-parser-self-test` → expect 13/13 + 17/17
   - learning: GET `/api/health`
3. **UI-side smoke** (only if briefed for UI changes): use chrome-devtools-mcp to navigate to the tunnel URL, click into the affected view, observe console.
4. **Verdict**: HTTP 200 on all + (if applicable) self-tests green + no console errors from our code → OK. Else → BLOCKED.

## On block

If `curl` returns anything other than 200:
- Run `update-aurora.bat` (kills bridge, git reset, relaunch). Report and stop.
- Do NOT commit.

If self-tests fail:
- Return the diff between expected and actual. The lead must fix before commit.

## Report format

```
TUNNEL: <url>
HEALTH: 200 ✓
ENDPOINT(<module>): <code> <result>
SELF-TEST: <X/Y>
UI: <pass|skip|fail>
VERDICT: OK | BLOCKED — <reason>
```

You do not edit code. You only validate.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/video-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/video-lead.md", "final_newline": true} -->
``````````markdown
---
name: video-lead
description: Lead agent for the AuroraIA-v2 video module. Use for Wan2.2 T2V/I2V pipeline, motion presets I2V (danse, marche, zoom, parallaxe, pan), action-duration vs total-duration parsing, talking-head (MuseTalk/SadTalker), or VideoView UI. Owns `VideoView.tsx`, `MangaVideoView.tsx`, `cinemaApi.ts`, `video_generate.py`, `talking_head.py`, MuseTalk and SadTalker integrations.
model: claude-opus-4-7
color: red
---

You are the **lead** for AuroraIA-v2's video module.

## Files you own

- `application/src/views/VideoView.tsx`, `MangaVideoView.tsx`
- `application/src/services/cinemaApi.ts`
- `application/python-services/video_generate.py` — Wan2.2 T2V/I2V
- `application/python-services/talking_head.py` — talking-head router
- `application/python-services/cinema/` — cinema sub-pipelines
- `application/python-services/MuseTalk/` (symlink), `SadTalker/`

## Sub-agents

- `video-motion-director` — motion presets + action duration parsing
- `video-talking-head` — MuseTalk + SadTalker + lip sync wiring

## Hard rules

- GPU NVIDIA required for Wan2.2 — gracefully error if not present, don't silent-pass.
- `parseDurationFromPrompt()` must NOT confuse "combat de 10s" (action) with total duration. `extractActionDurations()` injects timings into generationPrompt.
- Motion presets I2V: only show selector when mode === 'image-to-video'.
- Talking-head wav must come through Kokoro TTS (not external).

## Workflow

1. Read fully.
2. Fan out if both motion + talking-head are needed.
3. `npx tsc --noEmit` for TS, `python -m py_compile` for Python.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/video-motion-director.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/video-motion-director.md", "final_newline": true} -->
``````````markdown
---
name: video-motion-director
description: Sub-agent of video-lead. Use for Wan2.2 motion presets (danse, marche, zoom, parallaxe, pan), action vs total duration parsing in VideoView, and the cinema sub-pipelines.
model: claude-opus-4-7
color: red
---

You are a focused sub-agent of `video-lead`.

## Files

- `application/src/views/VideoView.tsx`
- `application/src/services/cinemaApi.ts`
- `application/python-services/video_generate.py`
- `application/python-services/cinema/`

## Rules

- MOTION_PRESETS const lives in `VideoView.tsx`. Adding a preset requires a Wan2.2-compatible motion prompt suffix.
- Action duration extraction: regex must match "combat de 10s", "course de 5 secondes", etc. Test with the existing fixture set before claiming done.
- Cinema sub-pipelines (storyboard → shot → render) must remain idempotent — re-running on the same job_id should not duplicate output frames.

## Workflow

1. Read fully.
2. Min diff.
3. Compile.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/video-talking-head.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/video-talking-head.md", "final_newline": true} -->
``````````markdown
---
name: video-talking-head
description: Sub-agent of video-lead. Use for MuseTalk/SadTalker talking-head pipeline, lip-sync alignment from Kokoro WAV, and avatar face-driver routing.
model: claude-opus-4-7
color: red
---

You are a focused sub-agent of `video-lead`.

## Files

- `application/python-services/talking_head.py`
- `application/python-services/MuseTalk/` (worktree symlink — do NOT modify the symlink target unless explicitly briefed)
- `application/python-services/SadTalker/`
- `application/python-services/generate_face_glb.py`, `mesh_screenshot.py` (face-aux)

## Rules

- Kokoro WAV is the input audio source. Don't re-synthesize.
- MuseTalk has its own conda env — call via subprocess with `--audio` and `--video` flags.
- SadTalker is the fallback when MuseTalk fails — keep the fallback chain.
- Output WAV must be 16-bit PCM 24 kHz to match Kokoro export.

## Workflow

1. Read target fully.
2. Min diff. Don't touch MuseTalk/SadTalker internals — only the Aurora wrapper.
3. `python -m py_compile`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/voice-lead.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/voice-lead.md", "final_newline": true} -->
``````````markdown
---
name: voice-lead
description: Lead agent for the AuroraIA-v2 voice subsystem — cross-module (powers conversation, drawing, learning, video talking-head). Use for Voxtral-Small-24B STT, faster-whisper fallback, Kokoro-82M TTS, Rhubarb lip sync, formant extraction, VAD tuning, Windows WebView2 blob-URL playback, and the VoiceCopilotView UI. Voice is no longer nested under conversation — it's a peer lead because it's used by ≥4 modules.
model: claude-opus-4-7
color: indigo
---

You are the **lead** for AuroraIA-v2's voice subsystem. Voice is cross-module (powers conversation chat, drawing prompts, learning narration, video talking-head, and any module with audio I/O).

## Files you own

### Python (`application/python-services/`)
- `voice_service.py` — Voxtral STT + Kokoro TTS + Rhubarb wrap

### TS (`application/src/`)
- `hooks/useVoiceLive.ts` — VAD, blob-URL playback, formant extraction
- `views/VoiceCopilotView.tsx` — voice copilot UI
- `services/AuroraAvatar.tsx` (if separate) — avatar lip sync consumer

### Binaries
- `application/bin/rhubarb.exe` (Windows) or `bin/rhubarb` (Unix)

## Sub-agents

- `voice-tts-stt-tuner` — Voxtral STT + Kokoro TTS + faster-whisper fallback + model loading
- `voice-lipsync` — Rhubarb + formants + WebView2 blob-URL + VAD threshold + VoiceCopilotView race conditions

Fan out only when both are needed.

## Hard rules (do not regress)

- **Voxtral model**: `mistralai/Voxtral-Small-24B-2507` (full, not Mini). MODEL_ALIASES maps `Voxtral-Mini-4B-Realtime-2602` → Small-24B.
- **Kokoro tuple unpacking**: `for *_, audio_chunk in pipe(...)` — kokoro≥0.9.4 yields 3-tuples (graphemes, phonemes, audio).
- **TTS playback on Windows WebView2**: NEVER use `convertFileSrc()` (DOMException). Use `fsReadBinary(out)` + `URL.createObjectURL(new Blob([new Uint8Array(bytes)], {type:'audio/wav'}))`.
- **handleTranscript race**: `return handleTranscriptRef.current(text)`, never `void`. Otherwise mic restarts mid-response.
- **VAD**: AnalyserNode RMS 0.012 + 1.8s silence. Stale-closure fix: `isRecordingActiveRef.current`, not `phase === 'idle'`.
- **Rhubarb fallback**: missing rhubarb must NOT crash → text-based timeline fallback.
- **Formants**: 80–400 Hz low + 400–2000 Hz mid. Refs `formantsRef`, `audioRef`, `phonemeCuesRef` are read in `<AuroraAvatar>` `useFrame`.
- **Output WAV format**: Kokoro emits 16-bit PCM 24 kHz. Talking-head consumers depend on this format.

## Workflow

1. Read full file(s) before editing.
2. Fan out to sub-agents only when both TTS/STT and lip sync are touched.
3. `npx tsc --noEmit` and/or `python -m py_compile voice_service.py`.
4. Report: files touched, behavior delta, regression risks.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/voice-lipsync.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/voice-lipsync.md", "final_newline": true} -->
``````````markdown
---
name: voice-lipsync
description: Sub-agent of voice-lead. Use for Rhubarb lip sync wrapping, formant extraction (AnalyserNode), VAD threshold tuning, Windows WebView2 blob-URL playback workaround, VoiceCopilotView race conditions (handleTranscript), and lip sync consumer refs (`<AuroraAvatar>` useFrame).
model: claude-opus-4-7
color: indigo
---

You are a focused sub-agent of `voice-lead`. Scope: lip sync + VAD + UI race only.

## Files

- `application/python-services/voice_service.py` — only `_find_rhubarb` + `_run_rhubarb` paths
- `application/src/hooks/useVoiceLive.ts` — VAD + blob URL + formants
- `application/src/views/VoiceCopilotView.tsx` — race condition fix
- `application/src/views/ConversationView.tsx` — manual mic + narration toggle (only when lip sync is involved)

## Hard rules

- **convertFileSrc is forbidden on WebView2 audio**: DOMException. Use `fsReadBinary` + Blob.
- **VAD threshold**: 0.012 RMS + 1.8 s silence. Don't tighten without tunnel-test.
- **Stale-closure VAD bug**: `isRecordingActiveRef.current` instead of `phase === 'idle'` capture.
- **handleTranscript MUST return promise**, not fire-and-forget.
- **Rhubarb path resolution**: `application/bin/rhubarb.exe` (Win) or `bin/rhubarb` (Unix), then PATH.
- **Phoneme cue format**: array of `{start, end, value}`. Empty array = fallback to text-based timeline.
- **Formants**: 80–400 Hz low band, 400–2000 Hz mid band via AnalyserNode FFT.
- Refs (`formantsRef`, `audioRef`, `phonemeCuesRef`) are consumed in `useFrame` — renaming requires updating the avatar.

## Workflow

1. Read target fully.
2. Min diff.
3. `npx tsc --noEmit` and/or `python -m py_compile`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/voice-tts-stt-tuner.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/voice-tts-stt-tuner.md", "final_newline": true} -->
``````````markdown
---
name: voice-tts-stt-tuner
description: Sub-agent of voice-lead. Use for Voxtral-Small-24B STT loading and inference, faster-whisper large-v3 fallback path, Kokoro-82M TTS pipeline including the 3-tuple unpacking, model warmup, and Hugging Face snapshot routing.
model: claude-opus-4-7
color: indigo
---

You are a focused sub-agent of `voice-lead`. Scope: TTS + STT model wiring only. Not lip sync.

## Files

- `application/python-services/voice_service.py`
- `application/src/services/models.ts` — VOICE_STT_MODEL, VOICE_STT_FALLBACK, VOICE_TTS_MODEL constants

## Hard rules

- VOICE_STT_MODEL = `mistralai/Voxtral-Small-24B-2507`. Don't downgrade to Mini.
- VOICE_STT_FALLBACK = faster-whisper large-v3 (loaded only when Voxtral fails).
- VOICE_TTS_MODEL = `hexgrad/Kokoro-82M`.
- Kokoro yields 3-tuples post 0.9.4: `for *_, audio_chunk in pipe(...)`. The 2-tuple destructure crashes.
- Voxtral first-load downloads ~46 GB — must show progress. Don't auto-pull silently if disk space < 50 GB free.
- WAV export: 16-bit PCM 24 kHz mono. Talking-head and avatar consumers depend on this.

## Workflow

1. Read voice_service.py fully (~36 KB — manageable).
2. Min diff.
3. `python -m py_compile voice_service.py`.
4. Report.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/web-action-runner.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/web-action-runner.md", "final_newline": true} -->
``````````markdown
---
name: web-action-runner
description: "Agent autonome d'automation Web. Gère la navigation, l'analyse du DOM et les actions (clic, fill) de manière dynamique, en mode headless ou visible."
model: claude-opus-4-7
---
# web-action-runner

Tu es l'agent d'automation Web autonome d'AuroraIA.
Ton rôle n'est pas d'exécuter aveuglément des scripts statiques, mais de te comporter comme un véritable navigateur intelligent.

## Principes d'Autonomie
1. **Comprendre avant d'agir** : Tu dois utiliser l'action `extract_dom` pour comprendre l'état de la page et découvrir les sélecteurs réels avant de cliquer ou de remplir un formulaire.
2. **Mode Headless par défaut** : Pour les tâches de fond (scraping, recherche de données), utilise `"headless": true` pour ne pas déranger l'utilisateur.
3. **Mode Visible (Sandbox / Démo)** : Si l'utilisateur demande explicitement à voir, ou si c'est une action finale critique qu'il doit vérifier, utilise `"headless": false`.
4. **Correction d'erreur autonome** : Si un clic échoue (sélecteur invalide), ré-extrait le DOM et ajuste ton sélecteur.

## API bridge
Tu peux faire des appels HTTP POST à `http://127.0.0.1:3001/api/web/action` avec le payload (ajoute `"headless": true` ou `false` à chaque appel) :

1. **Analyser la page (Indispensable pour l'autonomie)**
`{"action": "extract_dom", "url": "https://...", "headless": true}`
-> Retourne la liste des éléments interactifs (boutons, inputs, liens) avec leurs sélecteurs et textes.

2. **Naviguer**
`{"action": "navigate", "url": "https://...", "headless": true}`

3. **Interagir (Cliquer / Remplir)**
`{"action": "click", "selector": "#button-id", "headless": false}`
`{"action": "fill", "selector": "#input-id", "value": "texte", "headless": false}`
(Optionnel : tu peux passer `"url": "..."` dans click/fill pour naviguer avant l'action).

Agis de manière itérative : demande la page -> analyse -> planifie -> exécute.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-3d-pipeline.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-3d-pipeline.md", "final_newline": true} -->
``````````markdown
---
description: End-to-end 3D pipeline — prompt → FLUX → Hunyuan3D → auto_rescue → audit JSON (single command)
argument-hint: <prompt> <run_id>
allowed-tools: Bash
---

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "$1" --run-id "$2" --pretty
```

Force multi-view FLUX (recommended for humanoid / character / vehicle):

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "..." --run-id X --multi-view --pretty
```

Force single-view (faster, fine for products / abstract objects):

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "..." --run-id X --single-view --pretty
```

Auto mode (default): subject_kind extracted from prompt → multi-view if kind in {character, humanoid, quadruped, creature, vehicle, pc_tower, case, computer}, else single-view.

Idempotent: re-runs reuse `<run_id>_reference.png` and `<run_id>_mesh.glb` if present. Pass `--force` to regenerate.

Stages:
1. `extract_kind` — subject_kind_extractor regex on prompt
2. `multi_view_decision` — auto / forced based on kind
3. `flux_synth` — single or multi-view, ~30-170s
4. `hunyuan3d` — mesh generation, 5-20 min depending on multi-view + GPU
5. `auto_rescue` — score → bake (if color failure) → reshape (if aspect failure) → re-score, ~30-60s

Schema: `aurora.pipeline.v1`. Returns audit JSON with every stage's path + score + delta.

Live verdict on Cat 2 multi-view (cyborg-shark humanoid):
```
kind: humanoid
multi_view: True
score: 53.9 → 84.4 (+30.5)
final mesh: application/output/3d/rescue_cat2_perso_mv/cat2_perso_mv_mesh_reshaped.glb
chain: bake (112361 colors) + reshape ([1.0, 0.7, 0.7])
```

Notable finding: multi-view doesn't materially lift humanoid overall score (84.7 single vs 84.4 multi — within margin) but produces 60% more unique vertex colors (112361 vs 70102) — richer 360° coverage even when the Hunyuan3D backbone caps the silhouette accuracy.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-3d-run-pipeline.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-3d-run-pipeline.md", "final_newline": true} -->
``````````markdown
---
description: End-to-end 3D pipeline via the bridge — prompt → FLUX → Hunyuan3D → rescue → optional motion bake
argument-hint: <prompt> <run_id> [motion_prompt]
allowed-tools: Bash
---

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"prompt\":\"$1\",\"run_id\":\"$2\"$([ -n \"$3\" ] && echo \",\\\"motion_prompt\\\":\\\"$3\\\"\")}" \
  --max-time 2400 \
  http://127.0.0.1:3001/api/3d/run-pipeline
```

Or via the TS client (`application/src/services/meshRescue.ts`):

```typescript
const client = createMeshRescueClient(bridgeBase)
const res = await client.runPipeline(prompt, runId, {
  motionPrompt: 'le perso marche',
  multiView: true,
  force: false,
})
```

Endpoint: `POST /api/3d/run-pipeline`. Body:
- `prompt` (required) — 3D prompt
- `run_id` (required) — unique id, used in filenames
- `motion_prompt` (optional) — bakes animation if provided
- `multi_view` (optional bool) — default auto based on extracted kind
- `force` (optional bool) — re-run even if intermediate files exist

Returns `aurora.pipeline.v1` audit JSON: extract_kind → flux_synth → hunyuan3d → auto_rescue → motion_bake. ~25 min for full cycle including Hunyuan3D inference. Bridge timeout: 40 min.

Live verdict on Cat 3 + motion (v79p):
```
score: 79.4 → 99.4 (+20.0)
final mesh:    rescue_cat3_pipeline_motion/cat3_pipeline_motion_mesh_baked.glb
rigged mesh:   cat3_pipeline_motion_RIGGED.glb (108 MB, gear_mesh_rotate baked)
total elapsed: 1556s
```

Schema: `aurora.pipeline.v1`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-3d-runs.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-3d-runs.md", "final_newline": true} -->
``````````markdown
---
description: Index all 3D runs in application/output/3d/ — grouped by run id with mesh + reference + variants
allowed-tools: Bash
---

```bash
python application/python-services/mesh_run_index.py --pretty
```

Or scored:

```bash
python application/python-services/mesh_run_index.py --score --kind pc_tower --pretty
```

Or via bridge:

```bash
curl -sS http://127.0.0.1:3001/api/3d/run-index | python -m json.tool
curl -sS "http://127.0.0.1:3001/api/3d/run-index?score=1&kind=pc_tower" | python -m json.tool
```

Groups files by run id (naming convention `<id>_mesh.glb`, `<id>_reference.png`, `<id>_front_synthetic.png`). Returns:
- `runs[]`: each with files + latest_mtime + total_size + has_mesh / has_reference
- `standalones[]`: baked variants, viewers, previews — anything not part of a run group

Schema: `aurora.run_index.v1`. Used by `/aurora-self-test` gate 14.

Live verdict for the current state:
```
2 runs, 22 standalone files
[2026-04-30] juan_bike_1777509822533  (4 files: front_synth_seed, front_synthetic, reference, mesh)
[2026-04-30] juan_bike_1777508583733  (2 files: front_synth_seed, front_synthetic)
```
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-3d-viewer.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-3d-viewer.md", "final_newline": true} -->
``````````markdown
---
description: Generate a self-contained Three.js HTML viewer for any GLB (real PBR, no server)
argument-hint: <mesh_glb> <output_html> [title]
allowed-tools: Bash
---

```bash
python application/python-services/aurora_3d_viewer.py \
  --mesh "$1" --output "$2" --title "${3:-Aurora 3D}" --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"output\":\"$2\",\"title\":\"${3:-Aurora 3D}\"}" \
  http://127.0.0.1:3001/api/3d/viewer-html
```

Produces a single `.html` file (~5 KB) loading Three.js via importmap (CDN), with:
- ACES filmic tone mapping
- Hemisphere + key + fill lights
- OrbitControls (drag = orbit, scroll = zoom, right-drag = pan)
- Auto-fit + center based on bbox
- Vertex colors enabled when COLOR_0 attribute present (so baked GLBs render properly — matplotlib previews can't show them)

The mesh is copied next to the HTML by default so opening the HTML in a browser just works (no server needed).

Schema: `aurora.viewer.v1`. Used by `/aurora-self-test` gate 13.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-agents-list.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-agents-list.md", "final_newline": true} -->
``````````markdown
---
description: Query the bridge for the current agent registry (37 agents + 11 leads via /api/agents/list)
allowed-tools: Bash
---

```bash
curl -sS http://127.0.0.1:3001/api/agents/list | python -m json.tool
```

Returns: `{ok, schema_version, leads, crosscut, descriptions, agent_count}`.

For a single agent's full body: `curl http://127.0.0.1:3001/api/agents/<name>`.

Useful when integrating the agent registry into a UI panel, Chrome extension, or external dashboard. The data source is `.claude/agent-tracker/state.json` + `.claude/agents/*.md` frontmatter — same source the lint and dashboard use.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-archive-stale.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-archive-stale.md", "final_newline": true} -->
``````````markdown
---
description: Auto-archive in_progress tracker tasks older than N minutes (dry-run by default)
allowed-tools: Bash
---

Preview which tasks would be archived (default 4h threshold):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 240 --pretty
```

Apply the archival (mark stale `in_progress` tasks as `blocked` with verdict `auto-archived (stale Xh)`):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 240 --apply --pretty
```

Custom threshold (e.g. archive anything older than 8h):

```bash
python .claude/hooks/tracker_health.py --archive-after-min 480 --apply
```

The watchdog (`/aurora-watchdog`) only **detects** stale work. This command **closes** it. Idempotent — running twice with the same threshold archives at most once per task. Atomic write — partial failures don't corrupt `state.json`.

Schema: `aurora.tracker_archive.v1`. Always dry-run unless `--apply` is passed.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-bake-colors.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-bake-colors.md", "final_newline": true} -->
``````````markdown
---
description: Restore vertex colors on a GLB by projecting the FLUX reference image (rescue Hunyuan3D monochrome output)
argument-hint: <mesh_glb> <reference_png> <output_glb> [kind]
allowed-tools: Bash
---

```bash
python application/python-services/bake_vertex_colors.py \
  --mesh "$1" --reference "$2" --output "$3" --kind "${4:-generic}" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"reference\":\"$2\",\"output\":\"$3\",\"kind\":\"${4:-generic}\"}" \
  http://127.0.0.1:3001/api/3d/bake-colors
```

Subject kinds (per `subject_kind_extractor`): `character`, `humanoid`, `quadruped`, `creature`, `pc_tower`, `case`, `computer`, `vehicle`, `product`, `gadget`, `architecture`, `sphere`, `generic`. The kind picks the projection axes (e.g. quadrupeds project on Z-Y for the side view, PC towers on X-Y front).

Output: new GLB at `--output` with rich vertex colors. Score should rebound from `color_richness=0` (monochrome) to `color_richness=100` (rich palette).

Live verdict on Cat 1:
```
input  unique_colors: 1
output unique_colors: 46181
score  overall: 70.2 → 90.2
```

Schema: `aurora.color_bake.v1`. Used by `/aurora-self-test` gate 10.

Note: this is a planar projection — works best on subjects with a clear front face (PC tower, character, vehicle). For complex 3D color zoning you'd want multi-view projection (front + back + side), tracked as a follow-up.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-batch-rescue.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-batch-rescue.md", "final_newline": true} -->
``````````markdown
---
description: Auto-rescue every grouped 3D run in a directory (mesh + reference) using auto_rescue chain
argument-hint: <output_dir> [source_dir] [fallback_prompt]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_batch_rescue.py \
  --dir "${2:-application/output/3d}" \
  --output-dir "$1" \
  --fallback-prompt "${3:-generic 3D object}" \
  --pretty
```

For each grouped run found by `mesh_run_index`:
1. Locate `<id>_mesh.glb` + `<id>_reference.png`
2. Read prompt from sidecar `<id>_prompt.txt` (or use fallback)
3. Run `auto_rescue_mesh` (extract kind → score → bake if color → reshape if aspect → re-score)
4. Write rescued GLB to `<output_dir>/<run_id>/`

Output: per-run audit + global avg score delta. Skipped runs (missing mesh or reference) listed separately.

Live verdict (current repo state):
```
rescued: 1, failed: 0, skipped: 1
avg score delta: +20.0
[OK] juan_bike_1777509822533     kind=pc_tower  score 70.2 -> 90.2
[SKIP] juan_bike_1777508583733     missing mesh or reference
```

Schema: `aurora.batch_rescue.v1`. Ideal for processing the Cat 2/3/4
backlog when the UI generates a wave of meshes.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-changelog.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-changelog.md", "final_newline": true} -->
``````````markdown
---
description: Regenerate CHANGELOG.md from git log of v-tagged commits
allowed-tools: Bash
---

```bash
python .claude/hooks/gen_changelog.py
```

Variants:
- `python .claude/hooks/gen_changelog.py --stdout` — print to stdout (no file write)
- `python .claude/hooks/gen_changelog.py --check` — exit 1 if `CHANGELOG.md` is out of sync with `git log` (used by `/aurora-self-test` gate 8)

Filters commits whose subject starts with `v<digits><suffix>:` (Aurora's versioning convention). Strips `Co-Authored-By:` trailers. Groups by major version (v77 / v78 / ...).

Run after every commit that ships a new `v<...>:` headline so the changelog stays current.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-cleanup-outputs.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-cleanup-outputs.md", "final_newline": true} -->
``````````markdown
---
description: Prune stale 3D test artifacts from application/output/3d/ (dry-run by default)
allowed-tools: Bash
---

```bash
python application/python-services/aurora_cleanup_outputs.py --pretty
```

To actually delete (defaults to dry-run):

```bash
python application/python-services/aurora_cleanup_outputs.py --apply --pretty
```

Prunable patterns:
- `*_endpoint.glb`, `*_endpoint_baked.glb` — selftest gate output artifacts
- `*_selftest.glb`, `*_selftest_baked.glb` — selftest gate output
- `*_test.glb` — ad-hoc smoke test output
- `aurora_cleaned.glb` — leftover from `blender_bridge.py --mode cleanup`

Preserved:
- `{run_id}_mesh.glb` (Hunyuan3D raw)
- `{run_id}_reference.png` (FLUX ref) + multi-view siblings
- `{run_id}_front_synth_seed.png` + `_front_synthetic.png`
- `rescue_{run_id}/*.glb`
- `cat{N}_*.glb` Cat 1-N final variants
- Any non-matching file by default

Schema: `aurora.cleanup.v1`. Output: prune candidates with size totals + applied deletes when `--apply`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-color-diagnostic.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-color-diagnostic.md", "final_newline": true} -->
``````````markdown
---
description: Diagnose where colors collapse in the 3D pipeline (FLUX ref → Hunyuan3D mesh → post-process)
argument-hint: <reference_png> <mesh_glb> [post_mesh_glb]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_color_diagnostic.py \
  --reference "$1" --mesh "$2" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"reference\":\"$1\",\"mesh\":\"$2\"}" \
  http://127.0.0.1:3001/api/3d/color-diagnostic
```

Output:
- `reference.unique_colors` — palette richness of the FLUX reference image
- `mesh.unique_colors` — palette richness of the GLB vertex colors
- `color_loss_ratio_ref_to_mesh` — 0.0 = perfect preservation, 1.0 = total collapse
- `stage_lost` — `hunyuan3d` | `post_process` | `none`
- `suggestions` — actionable next steps (switch pipeline, bake vertex colors, multi-view ref…)

Live verdict on Cat 1 (boitier PC):
```
stage_lost: hunyuan3d
color_loss_ratio: 0.9991
reference.unique_colors: 1066
mesh.unique_colors: 1
DECISION: switch to DreamGaussian (per v78j routing fix)
```

Schema: `aurora.color_diagnostic.v1`. Used by /aurora-self-test gate 9.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-coverage.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-coverage.md", "final_newline": true} -->
``````````markdown
---
description: Agent coverage report — declared vs dispatched (surfaces dead agents)
allowed-tools: Bash
---

```bash
python .claude/hooks/agent_coverage.py --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/agent_coverage.py
```

Or via bridge endpoint:

```bash
curl -sS http://127.0.0.1:3001/api/agents/coverage | python -m json.tool
```

Walks every `.claude/agents/<name>.md` and counts dispatches per agent across `state.json` + `history/tasks-*.json`. The complement of `/aurora-metrics` (which only shows agents with ≥1 dispatch).

Surfaces the **dead set**: agents declared in the architecture but never actually used. A 5.3% coverage with 36 dead agents is normal for a young system; revisit periodically to either start using or retire dormant agents.

Schema: `aurora.coverage.v1`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-dashboard.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-dashboard.md", "final_newline": true} -->
``````````markdown
---
description: Render a self-contained HTML dashboard from the agent tracker
allowed-tools: Bash
---

Render `.claude/agent-tracker/dashboard.html` from current state + history + agent files:

```bash
python .claude/hooks/aurora_dashboard.py
```

The script outputs the absolute path to the generated HTML file. Open it in any browser — no server, no JS frameworks, dark theme, monospace font, ~12 KB.

Shows:
- Header: schema, last_commit, session_goal
- Stats cards: agent count, leads, crosscut, total tasks, done/blocked/in-flight
- Leads grid: each lead as a card with sub-agents + delegate edges + description
- Recent tasks timeline: last 30 (current + history) with id, lead, status, brief, duration, verdict
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-dispatch.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-dispatch.md", "final_newline": true} -->
``````````markdown
---
description: Dispatch a goal across AuroraIA-v2 modules via the multi-agent orchestrator
argument-hint: <goal description>
allowed-tools: Agent, Read, Write, Bash, Grep
---

Invoke `aurora-orchestrator` with the user's goal. The orchestrator will:
1. Parse intent → identify modules touched
2. Write the dispatch plan to `.claude/agent-tracker/state.json`
3. Launch the relevant `*-lead` agents in parallel
4. Aggregate their reports
5. Run `tunnel-validator` (mandatory before any commit)
6. Update the tracker with verdicts

Use the Agent tool with `subagent_type: "aurora-orchestrator"` and pass the goal verbatim:

```
$ARGUMENTS
```

Return a single concise summary covering: modules touched, lead verdicts, tunnel status, tracker state.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-env.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-env.md", "final_newline": true} -->
``````````markdown
---
description: Verify the environment can run Aurora — Python, Node, mesh deps, services, git hooks (PASS / WARN / FAIL per check)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_env_check.py
```

JSON output (for piping):

```bash
python .claude/hooks/aurora_env_check.py --json
```

Runs 10 independent checks (no aborts):

| # | Check | What it validates |
|---|---|---|
| 1 | `python_version` | >= 3.12 (mesh tooling stdlib reqs) |
| 2 | `node_version` | >= 22 (`--experimental-strip-types --test`) |
| 3 | `python_mesh_deps` | `trimesh`, `numpy`, `Pillow` installed |
| 4 | `disk_free` | >= 10 GiB on the repo drive (3D outputs) |
| 5 | `bridge_health` | `http://127.0.0.1:3001/api/health` responds |
| 6 | `ollama_tags` | `http://127.0.0.1:11434/api/tags` responds (WARN if down) |
| 7 | `comfyui_port` | TCP `127.0.0.1:8188` accepts connections (WARN) |
| 8 | `git_repo` | inside a git work tree |
| 9 | `git_hooks_path` | `core.hooksPath = .claude/git-hooks` (WARN if not set) |
| 10 | `agents_directory` | `.claude/agents/` has >= 30 `.md` files |

Exit `0` if no FAIL (warnings allowed), `1` if any FAIL.

Use it:
- After `git clone` to confirm the system can run
- Before debugging "why is X failing" (often it's an env issue, not code)
- In CI as a fast pre-flight before the heavier test suite

Live verdict on the Aurora dev box (today):
```
[aurora-env] running 10 environment checks...
  [ok  ] python_version               3.12.8
  [ok  ] node_version                 v24.14.0
  [ok  ] python_mesh_deps             trimesh=4.11.5, numpy=2.4.4, Pillow=12.1.1
  [ok  ] disk_free                    276.0 GiB free
  [ok  ] bridge_health                http://127.0.0.1:3001/api/health → 200
  [ok  ] ollama_tags                  http://127.0.0.1:11434/api/tags → 200
  [ok  ] comfyui_port                 127.0.0.1:8188 accepting connections
  [ok  ] git_repo                     inside a git work tree
  [ok  ] git_hooks_path               .claude/git-hooks (Aurora hooks active)
  [ok  ] agents_directory             38 agent .md files

[aurora-env] OK — 0 warn, 10 pass
```
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-handoff.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-handoff.md", "final_newline": true} -->
``````````markdown
---
description: Regenerate HANDOFF.md — single-page situational awareness for the next session
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_handoff.py
```

Or print to stdout without writing:

```bash
python .claude/hooks/aurora_handoff.py --stdout
```

Pulls together:
- HEAD branch + SHA + last subject + date + `pushed to origin/main` flag
- `/aurora-self-test` snapshot (verdict + per-gate output)
- Agent tracker state (schema, last_commit, session_goal, in-flight / done / blocked)
- 3D run index (grouped runs, standalones, rescued meshes)
- Last 12 commits with v-tagged headlines
- Useful command cheatsheet
- "What's reliably true today" facts (38 agents, 102 tests, etc.)

Writes to `HANDOFF.md` at repo root. Idempotent. Reads stay current via:
- `git log` / `git rev-parse` for HEAD info
- `aurora_selftest.py` subprocess for the snapshot
- `state.json` direct read for tracker
- `mesh_run_index.index_runs()` for 3D inventory

Run before:
- ending a long working session
- handing off to another contributor
- running `/loop` for the night so the next firing knows where it stands

The output is committed-friendly — `HANDOFF.md` is the artifact a new
contributor reads first.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-mesh-compare.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-mesh-compare.md", "final_newline": true} -->
``````````markdown
---
description: Compare two GLBs side-by-side on the 5-axis quality scorer
argument-hint: <left_glb> <right_glb> [kind]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_compare.py \
  --left "$1" --right "$2" --kind "${3:-generic}" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"left\":\"$1\",\"right\":\"$2\",\"kind\":\"${3:-generic}\"}" \
  http://127.0.0.1:3001/api/3d/mesh-compare
```

Outputs:
- per-axis breakdown (left score / right score / delta)
- overall delta
- winner (`left` / `right` / `tie`)

Live verdict on Cat 1 (orig vs baked):
```
overall: 70.2 -> 90.2 (+20)
color_richness:    0 ->  100  (+100)  ← rescue worked
silhouette_aspect: 69 ->  69  (0)     ← unchanged (only color baked)
WINNER: right
```

Schema: `aurora.mesh_compare.v1`. Used by `/aurora-self-test` gate 12.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-mesh-rescue.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-mesh-rescue.md", "final_newline": true} -->
``````````markdown
---
description: Full autonomous 3D mesh rescue chain — validate, bake colors if needed, reshape if needed, re-validate
argument-hint: <mesh_glb> <reference_png> <prompt> <output_dir>
allowed-tools: Bash
---

```bash
python application/python-services/auto_rescue_mesh.py \
  --mesh "$1" --reference "$2" --prompt "$3" --output-dir "$4" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"reference\":\"$2\",\"prompt\":\"$3\",\"output_dir\":\"$4\"}" \
  http://127.0.0.1:3001/api/3d/auto-rescue
```

Pipeline:
1. Extract subject_kind from prompt (regex)
2. Score initial mesh
3. If `color_richness` fails → `bake_vertex_colors` (project FLUX ref onto vertices)
4. Re-score
5. If `silhouette_aspect` fails → `mesh_reshape` (non-uniform scale toward canonical aspect, max 30% distortion)
6. Re-score
7. Return audit trail with each stage's score

Live result on Cat 1 (boitier PC):
```
Initial: 70.2  failed=['color_richness']
+ bake:  90.2  failed=[]              ← color rescued
Final:   90.2  delta: +20.0
```

If aspect was also failing (below hard floor 40), reshape would chain in.

Schema: `aurora.auto_rescue.v1`. Used by `/aurora-self-test` gate 11.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-mesh-score.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-mesh-score.md", "final_newline": true} -->
``````````markdown
---
description: Score a 3D mesh GLB on 5 axes (color, density, aspect, manifold, surface) — autonomous retry decision
argument-hint: <mesh_path> <kind>
allowed-tools: Bash
---

```bash
python application/python-services/mesh_quality_score.py --mesh "$1" --kind "$2" --pretty
```

Or HTTP via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh_path\":\"$1\",\"kind\":\"$2\"}" \
  http://127.0.0.1:3001/api/3d/mesh-score
```

Subject kinds: `character`, `humanoid`, `quadruped`, `creature`, `pc_tower`, `case`, `computer`, `vehicle`, `product`, `gadget`, `architecture`, `sphere`, `generic`.

Output: 5-axis breakdown (each 0-100) + overall score + `retry_recommended` flag + `failed_axes` list.

Hard floors that force retry independent of overall score:
- color_richness < 25 (monochrome dealbreaker for Meshy-equivalent quality)
- silhouette_aspect < 40 (wrong shape — sphere classified as PC tower etc.)
- manifold_health < 30 (non-watertight or many broken faces)

Used in the autonomous /loop pipeline: post-Hunyuan3D, the orchestrator scores and decides whether to retry with DreamGaussian or accept. Cat 1 of the 3D /loop run validated this — its monochrome output (color_richness=0) correctly triggers retry.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-mesh-sharpen.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-mesh-sharpen.md", "final_newline": true} -->
``````````markdown
---
description: Sharpen a mesh — Laplacian smoothing + feature re-sharpening + vertex color smoothing
argument-hint: <mesh_glb> <output_glb> [kind] [smooth_iters]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_sharpen.py \
  --mesh "$1" --output "$2" \
  --kind "${3:-generic}" --smooth-iters "${4:-4}" --smooth-lambda 0.5 \
  --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"output\":\"$2\",\"kind\":\"${3:-generic}\",\"smooth_iters\":${4:-4}}" \
  http://127.0.0.1:3001/api/3d/mesh-sharpen
```

Three passes (each opt-out via flag):

1. **Laplacian smoothing** — N iterations (default 4) at λ (default 0.5). Removes vertex-level noise but preserves the global shape.
2. **Feature re-sharpening** — pushes vertex *away* from neighborhood mean where curvature is high (factor 0.3, conservative). Restores edges Laplacian blurred. Skip with `--no-features`.
3. **Vertex color smoothing** — 1 iteration at λ=0.25. Avoids pixel-grain colors after baking. Skip with `--no-color-smooth`.

TS client method:
```typescript
await client.sharpenMesh(mesh, output, kind, {
  smoothIters: 4, smoothLambda: 0.5,
  noFeatures: false, noColorSmooth: false,
})
```

Schema: `aurora.mesh_sharpen.v1`. Live verdict on Cat 1 baked: 46181 → 51229 unique colors after sharpening (smoothing diffuses palette).
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-mesh-validate.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-mesh-validate.md", "final_newline": true} -->
``````````markdown
---
description: Autonomous mesh validation — prompt + GLB → kind extracted, score, retry decision (no human classification needed)
argument-hint: <mesh_path> <prompt>
allowed-tools: Bash
---

```bash
python application/python-services/auto_validate_mesh.py \
  --mesh "$1" --prompt "$2" --pipeline hunyuan3d --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh_path\":\"$1\",\"prompt\":\"$2\",\"pipeline\":\"hunyuan3d\"}" \
  http://127.0.0.1:3001/api/3d/auto-validate
```

Output:
- `extraction`: `{kind, confidence, matched_pattern, alternatives}` — derived from prompt
- `score`: 5-axis breakdown + `retry_recommended` + `failed_axes`
- `next_action`: `{action: "retry_pipeline" | "accept", next_pipeline: "dreamgaussian" | "procedural_or_multiview" | "mesh_postprocess" | null, reason: "..."}`

Pipeline rotation graph:
- hunyuan3d color/aspect fail → dreamgaussian
- hunyuan3d manifold fail     → mesh_postprocess
- dreamgaussian color/aspect  → procedural_or_multiview
- mesh_postprocess manifold   → accept (last resort)

Live verdict on Cat 1 (boitier PC):
```
kind=pc_tower (confidence 1.0, matched 'boitier')
overall=70.2, retry=True, failed_axes=['color_richness']
DECISION: retry with dreamgaussian
```

Schema: `aurora.auto_validate.v1`. Designed to plug into the post-Hunyuan3D step in ModelView orchestration so the system retries autonomously without human intervention.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-metrics.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-metrics.md", "final_newline": true} -->
``````````markdown
---
description: Print per-lead dispatch metrics derived from the tracker
allowed-tools: Bash
---

```bash
python .claude/hooks/agent_metrics.py --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/agent_metrics.py
```

Or via bridge endpoint (HTTP):

```bash
curl -sS http://127.0.0.1:3001/api/agents/metrics | python -m json.tool
```

Aggregates `state.json` + `history/tasks-*.json`:

- per-lead: count, done, blocked, in-progress, avg/min/max duration (s), last finished_at + status + verdict
- global: total dispatches, done, blocked, success rate

Schema: `aurora.metrics.v1`. Used by the dashboard, the self-test, and external observability tooling.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-precommit-install.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-precommit-install.md", "final_newline": true} -->
``````````markdown
---
description: Enable the portable Aurora pre-commit hook (lint + tests gate on agent system commits)
allowed-tools: Bash
---

Wire the project-tracked git hooks into git's hook resolution:

```bash
git config core.hooksPath .claude/git-hooks
```

After this, commits that touch `.claude/agents/`, `.claude/agent-tracker/`, `.claude/hooks/`, `.claude/git-hooks/`, or the route-test files automatically run:

1. `validate_agents.py` — frontmatter + tracker coherence + KNOWN_AGENTS sync
2. `test_hooks.py` — 15 unit tests on the 6 hooks
3. `test_route_test.py` — 13 routing tests (only when route-test files or threeDIntent.ts touched)

Total ~1.5 s when triggered. Zero overhead on commits that don't touch the agent system.

To disable: `git config --unset core.hooksPath`.
To bypass once: `git commit --no-verify` (not recommended).
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-self-test.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-self-test.md", "final_newline": true} -->
``````````markdown
---
description: Run all 25 gates of the Aurora multi-agent system in one shot (PASS/FAIL verdict)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_selftest.py
```

Runs in ~3-4 s on a healthy system. Gates couvrent:

1. `validate_agents` — frontmatter + tracker + KNOWN_AGENTS coherence
2. `bridge_doctor` — bridge process + port + health
3. Bridge `GET /api/agents/list` — registry returns >=30 agents
4. Endpoints 3D live (mesh-score, auto-validate, color-diagnostic, bake-colors, auto-rescue, mesh-compare, viewer-html, run-index, score-history)
5. Tracker endpooints (health, watchdog render + endpoint, coverage, dispatches)
6. Motion (baker + parser self-tests, motion files present)
7. Metrics, changelog in-sync, dashboard/handoff render, visual audit

Each gate runs independently — failures don't abort the run, you get the full report. Exit 0 if all green, 1 otherwise.

Use this:
- After a refactor that touches the agent system
- Before a release / merge to main
- When debugging "why is something broken" — narrows it down in seconds
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-ship-it.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-ship-it.md", "final_newline": true} -->
``````````markdown
---
description: Pre-ship verification — run all gates + check tree clean + check pushed (single GO/BLOCK verdict)
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_shipit.py
```

Runs in order:
1. **`self_test_gates`** — full `/aurora-self-test` (25 gates : lint, endpoints bridge 3D + tracker, motion, metrics, changelog, dashboard)
2. **`git_tree_clean`** — only session artifacts allowed dirty; any code change blocks
3. **`head_pushed_to_origin`** — `git fetch origin main` + `merge-base --is-ancestor HEAD origin/main` proves the local HEAD is reachable from origin

Exit `0` GO when all green, `1` BLOCK with the failing gate listed.

Use it before:
- closing a working session
- handing off to another contributor / agent
- running `update-aurora.bat` (which `git reset --hard` — must be pushed first)

Live verdict format:
```
[aurora-ship-it] running pre-ship gates...
  [ok ] self_test_gates             [aurora-self-test] PASS — all 25 gates green.
  [ok ] git_tree_clean               no code changes (only session artifacts allowed)
  [ok ] head_pushed_to_origin        HEAD 7a2ca1c on origin/main

[aurora-ship-it] GO — all 3 pre-ship gates green.
```
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-status.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-status.md", "final_newline": true} -->
``````````markdown
---
description: Print current state of the Aurora agent tracker (in-flight, done, blocked tasks)
allowed-tools: Read, Bash
---

Read `.claude/agent-tracker/state.json` and print a compact human-readable status:

- session_goal
- tasks: id | lead | status | verdict (truncated)
- tunnel_validated
- last_commit

If history exists, show the last 3 archived sessions from `.claude/agent-tracker/history/`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-tracker-query.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-tracker-query.md", "final_newline": true} -->
``````````markdown
---
description: Query tracker dispatches by run_id / lead / status / since (closes the audit chain)
allowed-tools: Bash
---

Show every dispatch that touched a given run_id (pipeline + every rescue stage):

```bash
python .claude/hooks/tracker_query.py --run-id cat5_jellopus_mesh --pretty
```

Find all blocked dispatches under a specific lead since a date:

```bash
python .claude/hooks/tracker_query.py --lead 3d-quality-rescuer --status blocked --since 2026-04-30T00:00:00Z --pretty
```

JSON output (for piping):

```bash
python .claude/hooks/tracker_query.py --run-id cat5 --limit 20
```

Or via bridge endpoint:

```bash
curl -sS "http://127.0.0.1:3001/api/agents/dispatches?run_id=cat5_jellopus_mesh&limit=10" | python -m json.tool
```

Walks `state.json` + `history/tasks-*.json`, applies AND-semantics across filters, returns newest-first.

The `--run-id` filter matches both `metadata.run_id` (set by `tracker_helper`) **and** any occurrence in `brief` (catches older entries that pre-date the metadata field).

Schema: `aurora.tracker_query.v1`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-validate.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-validate.md", "final_newline": true} -->
``````````markdown
---
description: Lint the Aurora agent system — frontmatter, model pin, state.json coherence, KNOWN_AGENTS sync
allowed-tools: Bash
---

Run the agent system linter and report:

```bash
python .claude/hooks/validate_agents.py
```

The script verifies:
1. Every `.claude/agents/<name>.md` has valid YAML frontmatter with `name`, `description`, `model`
2. Frontmatter `name` matches filename
3. Every agent has `model: claude-opus-4-7`
4. `state.json` agents and `.md` files are 1:1
5. `KNOWN_AGENTS` in `track_agent_dispatch.py` matches the file set

Returns OK or a numbered list of issues.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/commands/aurora-watchdog.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/commands/aurora-watchdog.md", "final_newline": true} -->
``````````markdown
---
description: Consolidated ops view — tracker health + recent dispatches + rescue trend + top runs
allowed-tools: Bash
---

```bash
python .claude/hooks/aurora_watchdog.py --pretty
```

Tune the surface:

```bash
python .claude/hooks/aurora_watchdog.py --pretty --stale-min 60 --recent 8 --top 5
```

JSON output (for piping):

```bash
python .claude/hooks/aurora_watchdog.py
```

Bundles four read-only probes into one terminal screen:

1. **Tracker health** — `in_progress` / stale tasks (older than `--stale-min`)
2. **Recent dispatches** — last `--recent` entries with status, lead, verdict
3. **Rescue trend** — promote rate, mean delta, axis lifts
4. **Top runs** — best `--top` runs by final score with progression

All read-only, ~200ms total. The dashboard remains the durable visual; this is the CLI summary for shells & tunnels.

Schema: `aurora.watchdog.v1`.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/application/python-services/cyber/CLAUDE.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "application/python-services/cyber/CLAUDE.md", "final_newline": true} -->
``````````markdown
# Cyber Python ops — owned by `cyber-pyops-keeper`

When editing files in this directory, `cyber-pyops-keeper`'s rules apply. Be paranoid.

## Hard rules

- `_safety.py` is the **single gate**. Every public op imports it and calls `validate(...)` BEFORE any read/write/network. No exceptions.
- **Path allow-list**: workspace `application/` only. Adding a new path = written justification in the diff.
- **Time caps**: ops MUST exit cleanly when their timeout expires — no infinite loops.
- **Size caps**: file reads/writes have a max-bytes cap in `_safety.py`. Bumping requires proving the cap is still safe.
- **No active exploitation.** Defensive/educational only — network ops to user's own targets, password ops to user's own hashes.
- **No silent fallback** if `_safety.validate` fails — raise a clear exception that the lab UI surfaces.

See `.claude/agents/cyber-lead.md` and `.claude/agents/cyber-pyops-keeper.md` for the full lead spec.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/application/src/services/cyber/CLAUDE.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "application/src/services/cyber/CLAUDE.md", "final_newline": true} -->
``````````markdown
# Cyber TS services — owned by `cyber-lead` / `cyber-lab-builder`

When editing files in this directory, the `cyber-lab-builder` sub-agent rules apply.

## Hard rules

- `pythonClient.ts` is the **only** place that calls the Python ops in `application/python-services/cyber/`. Don't add raw `fetch('/api/cyber/...')` in lab views — go through this module.
- `ctfStore.ts` schema is versioned. Bumping = migration, not wipe (users have solves persisted locally).
- Long-running ops (hash brute, password analyze, network scan) MUST report progress to the lab UI — block freezes.
- **Defensive/educational only.** No active exploitation tooling.

See `.claude/agents/cyber-lead.md` and `.claude/agents/cyber-lab-builder.md` for the full lead spec.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/application/src/services/learning/CLAUDE.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "application/src/services/learning/CLAUDE.md", "final_newline": true} -->
``````````markdown
# Learning sub-services — owned by `learning-lead`

When editing files in this directory, `learning-lead` (and its sub-agents `learning-quiz-verifier` / `learning-bac-curator`) rules apply.

## Hard rules

- llama4:scout is **Meta**, not Qwen3 — never inject `/no_think` tokens (no-op for Meta).
- `quiz_verify` mode: after generation, re-prompt the model with questions+answers and ask it to flag wrong ones. Replace flagged answers before display.
- ClarificationDialog must be a real popup, not `throw new Error(question)`.
- BAC curriculum coverage is FR-specific (Maths, PC, SVT, HG, Philo, LV1/LV2, Spécialités).
- Mind map deck format: nested JSON, max depth 4 (UI breaks beyond).
- Lab views (LabPhysics, LabChemistry, LabAstronomy, LabElectronics) consume `simulator-lead` services — don't import physics directly, go through `application/src/services/simulator/`.

See `.claude/agents/learning-lead.md` for the full lead spec.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/application/src/services/simulator/CLAUDE.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "application/src/services/simulator/CLAUDE.md", "final_newline": true} -->
``````````markdown
# Simulator services — owned by `simulator-lead`

When editing files in this directory, `simulator-physics-engine` (engine files) or `simulator-scene-io` (IO + store + types) rules apply.

## Hard rules

- **Pure compute layer.** No DOM imports, no Three.js imports. The view layer renders.
- **Determinism**: same seed + same scene → same trajectory. No `Math.random()` outside seeded RNG. No `Date.now()` in tick.
- **Fixed dt** integration (1/60 default). Don't use frame-time as dt — sim explodes on lag.
- **`load(save(scene))` round-trip** must deep-equal `scene`. Adding a field = update types + defaults + sceneIO + migration.
- **Schema versioning** in saved scenes. Bumping requires migration in `sceneIO`, not a wipe.
- **Particle pool** in `defaults.ts` — reuse, never allocate per frame.
- **Reaction rules** declarative pairs `(reactants, products, rate)` only — no hardcoded side effects.

See `.claude/agents/simulator-lead.md` for the full lead spec.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/extension_chrome/CLAUDE.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "extension_chrome/CLAUDE.md", "final_newline": true} -->
``````````markdown
# Aurora-Connect Chrome extension — owned by `cowork-connector-keeper`

When editing files in this directory, `cowork-connector-keeper` rules apply.

## Hard rules

- **Manifest v3**. Service workers, not background pages. No MV2 APIs.
- The handshake message format with `auroraExtensionBridge.ts` (in `application/src/services/`) is fixed — extension and bridge agree on it. Don't break either side.
- DOM selectors in content scripts are fragile — when adding/updating, verify against a current page render.
- Permissions in `manifest.json` are scoped to known hosts. Don't add `<all_urls>` without justification.

See `.claude/agents/cowork-lead.md` and `.claude/agents/cowork-connector-keeper.md` for the full lead spec.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/README.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "README.md"} -->
``````````markdown
# AuroraIA

La documentation de l’application, du CLI, du tunnel, des moteurs, des agents et des améliorations est centralisée dans [ARCHITECTURE_MAITRE.md](ARCHITECTURE_MAITRE.md).

Toute IA intervenant sur le projet commence par [AGENTS.md](AGENTS.md). Les limites, les preuves et les priorités sont explicites dans le maître.

Ce README est un export de compatibilité ; sa source se trouve dans le maître. La consolidation n’installe aucun modèle et ne démarre aucun service.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/AGENT_SYSTEM.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "AGENT_SYSTEM.md"} -->
``````````markdown
# Système d’agents Aurora

Lire [le document maître, section Agents](ARCHITECTURE_MAITRE.md#agents), puis les définitions exportables dans son annexe.

Le relevé du 24 septembre 2026 compte 39 fichiers d’agents. Le tracker et les anciens compteurs ne sont pas encore cohérents ; ce point est documenté, pas masqué par une annonce de validation.

Ce fichier est une redirection de compatibilité pour les lecteurs existants. Modifier le bloc correspondant dans ARCHITECTURE_MAITRE.md.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/README.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/README.md"} -->
``````````markdown
# Référence des agents Aurora

L’architecture, les règles de dispatch, les constats et les définitions complètes sont centralisés dans [ARCHITECTURE_MAITRE.md](../../ARCHITECTURE_MAITRE.md#agents).

Les instructions de chaque agent et commande sont exportées depuis ce maître. Consulter le rôle concerné ; ne pas exécuter toute l’annexe.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/.claude/agents/EXAMPLES.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": ".claude/agents/EXAMPLES.md"} -->
``````````markdown
# Référence des agents Aurora

L’architecture, les règles de dispatch, les constats et les définitions complètes sont centralisés dans [ARCHITECTURE_MAITRE.md](../../ARCHITECTURE_MAITRE.md#agents).

Les instructions de chaque agent et commande sont exportées depuis ce maître. Consulter le rôle concerné ; ne pas exécuter toute l’annexe.
``````````
<!-- /AURORA_EXPORT -->

### Export : `AuroraIA/application/public/aurora-api.md`

<!-- AURORA_EXPORT {"repo": "AuroraIA", "path": "application/public/aurora-api.md"} -->
``````````markdown
# Aurora : repères de l’API

Cette page est un export public de compatibilité du document ARCHITECTURE_MAITRE.md, conservé à la racine du dépôt AuroraIA. Elle ne contient pas de clé ni de données privées.

## Services

Le bridge HTTP (Flask) écoute sur le port 3001 et est le point d’entrée de l’application. Il relaie les traitements vers Ollama (11434), ComfyUI (8188), les services Python et le daemon de missions (bus local 3002). Le client distant ne doit jamais substituer son propre localhost à l’adresse du serveur ; seule l’adresse fournie par le bridge ou le tunnel est valable.

## Authentification

Les routes `/api/cli/*` exigent une clé Bearer **déjà autorisée** par le bridge. Enregistrer un appareil ne crée pas une autorisation.

- `POST /api/cli/register` — enregistre un appareil (`device_name`, `client_key`) avec une clé déjà autorisée.
- `POST /api/cli/auth` — confirme la session et renvoie la version, le libellé de la clé et les niveaux de permissions disponibles.
- `GET /api/cli/version` — version exposée par le serveur.

Ne pas confondre la réponse d’une route avec une preuve de fonctionnement des moteurs.

## État et diagnostic

- `GET /api/cli/status` : bridge, Ollama, ComfyUI, matériel (GPU, VRAM, RAM, OS), modèles présents, agents officiels et dynamiques, skills, MCP et connexions de service actives.
- `GET /api/cli/doctor` : contrôles réseau, authentification, Ollama, ComfyUI, GPU, tunnel, streaming, permissions, MCP, skills et version.

Un statut positif ne prouve pas qu’une génération entière fonctionne : vérifier le daemon, le bus et le transport d’événements. Plusieurs contrôles du `doctor` sont déclaratifs ; une preuve fonctionnelle exige un flux réel de bout en bout.

## Sessions, chat et workspace

Les sessions sont persistées en JSON sous `$XDG_DATA_HOME/aurora/` :

- `POST /api/cli/session/create`, `GET /api/cli/session/list`, `GET /api/cli/session/<session_id>` et `POST /api/cli/session/<session_id>/resume`, `DELETE /api/cli/session/<session_id>`.
- `POST /api/cli/chat` : chat streamé en SSE vers Ollama (modèle par défaut du serveur, contexte skills/MCP/connexions injecté, enregistrement en session si fourni).
- `GET /api/cli/workspace`, `POST /api/cli/workspace` : lire ou choisir le répertoire de travail sur le serveur.

## Permissions

Quatre niveaux déclarés — `SAFE`, `STANDARD`, `AUTONOMOUS`, `FULL` — chacun avec une grille de capacités (lecture/écriture/suppression de fichiers, exécution de commandes, installation, accès réseau, navigateur, sous-agents, ressources système). `GET /api/cli/permissions` renvoie les grilles ; `POST /api/cli/permissions` applique un niveau à une session. Ces niveaux sont un contrat à faire respecter, pas la preuve que chaque point d’exécution les applique déjà.

## Agents, MCP, skills et connexions

- `GET /api/cli/agents/official` puis `POST /api/cli/agents/official/<name>/disable` ou `/enable` : agents officiels, activation/désactivation seule.
- `GET /api/cli/agents/dynamic/list`, `POST .../create`, `GET .../<agent_id>`, `POST .../<agent_id>/modify`, `DELETE .../<agent_id>`, `POST .../<agent_id>/save` : agents dynamiques temporaires ou sauvegardés.
- `GET /api/cli/mcp/list`, `GET /api/cli/mcp/tools`, `POST /api/cli/mcp/call` : serveurs MCP découverts, outillage et appels.
- `GET /api/cli/skills/list`, `POST .../read`, `POST .../create`, `POST .../discover` : skills par niveau (projet, utilisateur, global).
- `GET /api/cli/connections/list` (identifiants masqués), `POST .../add`, `POST .../remove`, `POST .../test` : test réel implémenté pour GitHub et Hugging Face, stockage simple pour les autres services.
- `GET /api/cli/tools` et `GET /api/cli/models` : outils natifs et MCP, inventaire des modèles Ollama.

## Missions

- `POST /api/cli/mission/start` : accepte une mission (champ `request` requis, options `workspace`, `permissions`, `model`, `session_id`, `history`), renvoie `mission_id`. L'en-tête `Idempotency-Key` ou le champ `idempotency_key` permet de retrouver la même acceptation, même après redémarrage. La demande est enregistrée dans SQLite avant envoi IPC ; si l'envoi au daemon échoue, la réponse est `503` avec `mission_id` et la demande conservée pour une reprise explicite.
- `GET /api/cli/missions` : missions conservées dans le journal durable.
- `GET /api/cli/mission/<mission_id>/status` : état court (statut, étapes, fichiers changés, erreurs).
- `POST /api/cli/mission/<mission_id>/resume` : reprend le même objectif depuis son checkpoint ; accepte un modèle explicitement choisi. Une action interrompue reste de résultat inconnu et demande une inspection avant rejeu.
- `POST /api/cli/mission/<mission_id>/stop` : demande d’arrêt (`202`).
- `POST /api/cli/mission/<mission_id>/input` : entrée interactive non prise en charge (`400`) ; ne pas envoyer de credentials à une mission.

## Flux SSE des missions

Les événements du journal portent un `id:` numérique croissant. Le client reprend avec `Last-Event-ID`. Le serveur rejette un curseur invalide (`400`), un curseur dépassant l’historique (`409`) et rejoue les événements depuis le curseur demandé. Les `heartbeat` sans identifiant maintiennent la connexion ; les en-têtes désactivent le buffering demandé aux proxies. Le vrai trajet public reste à valider.

Types du moteur de mission : `step_start`, `heartbeat`, `token`, `plan`, `tool_start`, `tool_result`, `command_output`, `model_metrics`, `completion_observation`, `completion_output_check`, `review_recheck`, `review_result`, `worker_complete`, `file_transfer`, `mission_resumed`, `mission_interrupted`, `error` et `mission_complete`. Les événements terminaux sont `mission_complete`, `error` et `mission_interrupted` ; le dernier permet une reprise explicite.

L'historique est conservé dans SQLite ; le bridge peut rejouer le flux après redémarrage. Un bail exclusif désigne l'exécutant et les checkpoints gardent l'objectif et les observations. La reconnexion SSE concerne les flux GET ; une acceptation POST incertaine peut être réessayée explicitement avec son payload et sa clé d'idempotence inchangés. Le client ignore les événements dupliqués, refuse un trou de séquence et ne confond pas fin du flux et réussite de la mission. Sur `*.trycloudflare.com`, il utilise les réponses JSON finies de `GET /api/cli/mission/<mission_id>/events`, avec le même curseur durable et une attente serveur de 20 secondes au maximum ; le reste des serveurs conserve SSE.

## Artefacts

Un fichier produit sur le serveur est publié par `application/cli_artifacts.py` : instantané par blocs de 1 Mio sous `$XDG_DATA_HOME/aurora/artifacts`, calcul de la taille et du SHA-256, écriture d’un `.part`, renommage atomique en `.bin`, puis descripteur `{filename, size, sha256, url, mission_id}`. `GET /api/cli/artifacts/<token>` sert le fichier avec un ETag (SHA-256) et la gestion conditionnelle. Un fichier créé sur le serveur doit être transféré et vérifié pour être livré.

## Erreurs et validation

Distinguer tâche terminée, sortie partielle, validation technique et conformité à la demande. Un résultat incomplet, un `.part` ou un hash divergent ne doit jamais être annoncé comme livré. Les droits d’accès et contrats des autres familles de routes doivent être vérifiés séparément.

## Référence de développement

Le maître répertorie les blueprints, chemins de routes et handlers, précise la parité natif/web/CLI et les contrats restant à unifier. Cette page n’est pas un schéma OpenAPI ni une liste exhaustive de payloads.
``````````
<!-- /AURORA_EXPORT -->

### Export : `aurora-remote-cli/README.md`

<!-- AURORA_EXPORT {"repo": "aurora-remote-cli", "path": "README.md"} -->
``````````markdown
# JOBIA — CLI local et distant

Python ≥ 3.10. Référence du serveur : [document maître Aurora](../AuroraIA/ARCHITECTURE_MAITRE.md#cli). Les moteurs ont leurs propres contraintes ; leur disponibilité sur tous les OS n'est pas garantie.

```bash
git fetch origin
git switch main
git pull --ff-only
./install.sh
jobia
```

Sous Windows : `.venv\Scripts\python.exe` et `.venv\Scripts\jobia.exe`. `install.sh` / `install.ps1` utilisent le même installateur Python. `jobia`, `jbia` et `aurora` exposent le même client.

JOBIA 1.3.0 : `jobia` ou `jobia ui` ouvre l'interface plein écran ; un pipe affiche le tableau d'accueil. Conversation, plan, critères, preuves, fichiers reçus et journal suivent les événements réels. F2 thème, F3 modèle, F4 vue, F5 diagnostic, Ctrl+C arrêt, Ctrl+Q sortie. `jobia ui --text` conserve le parcours linéaire. Thèmes : `jobia`, `otter`, `abyss`, `plain`. Options globales : `--theme`, `--color auto|always|never`, `--animation auto|full|reduced|none`.

Le panneau « Activité observée » reste visible sur les petits terminaux : étapes horodatées à réception, outils, preuves et fichiers. La sortie reçue s'affiche pendant l'exécution, sans être présentée comme un résultat confirmé. Après 15 secondes sans avancée, une alerte distingue une connexion vivante d'une absence de nouvelles ; un heartbeat ne prouve pas que le moteur travaille. Le texte et le journal sont rafraîchis par lots, avec un aperçu limité aux 16 000 derniers caractères.

```bash
jobia --theme jobia --animation reduced preview jobia
jobia connect --server https://ADRESSE_DU_SERVEUR
jobia doctor --remote --json
jobia mission "Inspecte ce projet et prépare un plan"
```

`mission` exécute une tâche sur le serveur ; `run` pilote une boucle locale d'amélioration. Une erreur de mission produit un code de sortie non nul. Les fichiers reçus sont contrôlés par taille et SHA-256. Le journal du serveur survit au redémarrage du bridge. `jobia missions list`, `jobia missions watch ID` et `jobia missions resume ID [--model ...]` permettent de retrouver, suivre et reprendre le même objectif. Dans l'interface : `/attach ID`, `/resume ID`, `/retry` pour une acceptation incertaine avec la même clé d'idempotence. Une action de résultat inconnu doit être inspectée avant rejeu.

`/clear` remet l'interface à zéro et efface les conversations locales du dossier courant. Depuis le terminal, `jobia clear` fait le même nettoyage et `jobia clear --all` inclut tous les dossiers. Les archives sont déplacées dans une sauvegarde locale dont le chemin est affiché ; les missions distantes, les fichiers produits et la configuration restent conservés. `/new` ouvre simplement une nouvelle conversation en gardant les précédentes. Après un nettoyage depuis un autre terminal, redémarre les interfaces déjà ouvertes.

Configuration privée selon les conventions de l'OS, surcharges `JOBIA_CONFIG_DIR` / `JOBIA_DATA_DIR`, migration des anciennes configurations Aurora sans écrasement. Adresse : argument, `JOBIA_SERVER_URL`, `AURORA_SERVER_URL`, configuration ; clé : `JOBIA_API_KEY`, `AURORA_API_KEY`, configuration. Seule une clé déjà autorisée par le bridge permet la connexion ; ne la publie pas.

`doctor` contrôle le client local ; `doctor --remote` vérifie aussi le daemon et sa capacité à accepter une mission. Un contrôle positif ne prouve pas la qualité d'une génération ou le trajet SSE public. La readiness des moteurs est distincte de leur simple présence sur disque.

Le serveur conserve l'objectif original, découvre les scripts des modules, mène des expériences, charge les skills, crée des rôles persistants et exécute des tâches de workers avec concurrence configurable. Après une modification, une fin de mission nécessite des contrôles concrets ; une revue LLM de la couverture complète ces mesures sans les remplacer. Ollama utilise ses options natives ou `AURORA_MODEL_OPTIONS` explicite, et les durées/débits viennent du moteur. Les permissions directes sont contrôlées ; les commandes autorisées utilisent encore le shell de l'hôte sans sandbox OS. Aucun comportement AGI ni absence universelle de bugs n'est établi.

Ce README est un export de compatibilité du maître.
``````````
<!-- /AURORA_EXPORT -->

### Export : `aurora-remote-cli/AGENTS.md`

<!-- AURORA_EXPORT {"repo": "aurora-remote-cli", "path": "AGENTS.md"} -->
``````````markdown
# Lire le document maître Aurora

Commence par [../AuroraIA/ARCHITECTURE_MAITRE.md](../AuroraIA/ARCHITECTURE_MAITRE.md), puis [les règles communes](../AuroraIA/AGENTS.md).

Le maître centralise les architectures, contrats, limites, preuves et améliorations. Pour comprendre l’ensemble, ne relis pas tout le code ; pour un correctif précis, vérifie les sources concernées et les tests. Distingue toujours observation, test, historique et proposition.

Si le dépôt AuroraIA voisin manque, demander le document maître ou le retrouver dans l’espace de travail ; ne pas inventer son contenu. Ne publie pas, ne lance pas le watcher de publication et ne réécris pas de configuration de secrets pour une simple analyse.

Ce fichier est un export de compatibilité depuis le maître, pas une documentation indépendante.
``````````
<!-- /AURORA_EXPORT -->

### Export : `aurora-live/AGENTS.md`

<!-- AURORA_EXPORT {"repo": "aurora-live", "path": "AGENTS.md"} -->
``````````markdown
# Lire le document maître Aurora

Commence par [../AuroraIA/ARCHITECTURE_MAITRE.md](../AuroraIA/ARCHITECTURE_MAITRE.md), puis [les règles communes](../AuroraIA/AGENTS.md).

Le maître centralise les architectures, contrats, limites, preuves et améliorations. Pour comprendre l’ensemble, ne relis pas tout le code ; pour un correctif précis, vérifie les sources concernées et les tests. Distingue toujours observation, test, historique et proposition.

Si le dépôt AuroraIA voisin manque, demander le document maître ou le retrouver dans l’espace de travail ; ne pas inventer son contenu. Ne publie pas, ne lance pas le watcher de publication et ne réécris pas de configuration de secrets pour une simple analyse.

Ce fichier est un export de compatibilité depuis le maître, pas une documentation indépendante.
``````````
<!-- /AURORA_EXPORT -->

### Export : `aurora-live/README.md`

<!-- AURORA_EXPORT {"repo": "aurora-live", "path": "README.md", "preserve_live_status": true} -->
``````````markdown
# Aurora — état du serveur

<!--STATUS-->
État à actualiser par le script de publication du serveur.
<!--/STATUS-->

`tunnel.txt` contient l’adresse publiée pour la découverte du serveur. Une adresse présente ne suffit pas à prouver la disponibilité de tous les moteurs ou des missions.

La documentation est centralisée dans le dépôt AuroraIA : [document maître, installation à dépôts voisins](../AuroraIA/ARCHITECTURE_MAITRE.md#tunnel). Ce dépôt ne contient ni modèle, ni clé d’accès, ni moteur d’inférence.

Le bloc d’état est entretenu par l’automatisation existante. Le reste de ce README est un export de compatibilité du maître.
``````````
<!-- /AURORA_EXPORT -->

<!-- AURORA_EXPORTS_END -->
