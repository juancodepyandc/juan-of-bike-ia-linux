# PROMPT MAÎTRE — Module Code d'AuroraIA : excellence, autonomie, "tout produire proprement"

> **À l'IA qui reçoit ce prompt.** Ce document est ton brief **complet, autonome et à jour**. Il décrit l'état RÉEL du module (déjà largement refondu), les lois inviolables, les chantiers restants, et — au cœur — l'**autonomie / auto-amélioration / skills / MCP** attendues. Objectif unique : que le Module Code puisse **produire n'importe quel projet, proprement, à qualité maximale, sans jamais mentir sur son résultat**. Tu travailles sur un dépôt Git réel (Linux). **Tu commences par vérifier l'état (reprise), puis tu agis. Le seul critère de décision est la qualité finale** — jamais la rapidité, la simplicité, ni l'économie de ressources.

---

## 0. PRINCIPE DIRECTEUR (non négociable)

- **Qualité absolue.** Si une solution 10× plus coûteuse produit un résultat nettement supérieur, c'est elle. Plus de calcul / mémoire / recherche / étapes est acceptable si la qualité monte.
- **Jamais de mensonge de complétude.** Un test vert ne prouve rien s'il n'exerce pas le comportement réel. Une capacité "livrée" mais **jamais appelée en production** = défaut grave (c'est le mal historique de ce module). Tu ne déclares "fini" que ce que tu as **exécuté et observé**.
- **Face à une limite, tu ne dis jamais "impossible" sans recherche approfondie** (doc, GitHub, benchmarks, modèles, outils). Tu fais une **veille permanente** et remplaces une brique si une meilleure existe **et** améliore réellement le résultat.
- **Honnêteté sur les frontières.** Ce qui exige un environnement live (GPU en génération, vrai navigateur) et ne peut être prouvé sur-le-champ : tu le câbles au mieux ET tu écris exactement ce qui reste à valider en réel. Pas de "parfait sur le papier".
- **Langue.** Tous les livrables destinés à l'humain (journal, commits, réponses, docs) sont en **français** ; le code et les identifiants restent en anglais si c'est la convention du dépôt.

**But concret :** produire, à qualité constante et sans dégradation quand ça se complexifie — calculatrice, landing, site, web-app, SaaS, CRM, ERP, IDE, moteur graphique/3D, jeu, app mobile native, desktop, compilateur, OS, système distribué, microcontrôleur (ESP32/Arduino), projets très volumineux.

---

## 1. ENVIRONNEMENT RÉEL (exact — ne rien deviner)

- **Dépôt** : `AuroraIA` (mono-repo). Code applicatif sous `application/`. Branche de travail : `refonte/module-code`.
- **Front** : Tauri v2 + React 19 + TypeScript 6 + Vite 8 + Tailwind 4 + Zustand 5 + Three.js. Tourne en WebView (Linux → WebKitGTK).
- **Services** : Python sous `application/python-services/`.
- **Bridge** : Flask sur `http://localhost:3001` (`application/bridge_server.py`), tunnel cloudflared. Démarrage : `python bridge_server.py` (le laisser tourner ; **un seul process lourd Python à la fois** — tuer les orphelins avant relance).
- **Front web** : `npm run dev:web` (Vite :1420) ou `npm run dev` (Tauri). Tunnel : `npm run start:cloud` (URL dans `application/tunnel_url.txt`).
- **LLM** : Ollama local `http://localhost:11434`. **Modèles réellement installés** : `qwen3-coder:30b` (coder), `qwen3-coder-next:q4_K_M`, `qwen3:30b-a3b-instruct-2507-q4_K_M` (raisonnement/instruct), `qwen3-vl:30b` et `qwen3-vl:8b` (vision), `nomic-embed-text` (embeddings RAG). Tirer un manquant : `ollama pull <name>`.
- **Matériel** : GPU RTX 5070 Ti **16 Go VRAM** + 30 Go RAM + swap. **Un seul gros modèle chargé à la fois** (sérialiser Ollama ; le swap est lent <1 tok/s).
- **Tests** : runner natif Node (pas de vitest), **Node ≥ 22.6** (hôte v24). Depuis `application/` : `npm test` (tous). Sous-ensemble code : `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'`.
- **Baseline actuelle (2026-07-16)** : **718 tests code verts**, **4555/4556 au total** (le seul échec, `coworkExtract.test.ts`, est un test d'intégration cowork qui exige crawl4ai/Playwright live → 502 environnemental, **hors périmètre code, préexistant**). Typecheck (`node_modules/.bin/tsc --noEmit`) : **33 erreurs préexistantes, toutes hors module Code** (sessionTempStorage, cowork, flux, pixelArt) — ne pas les toucher.
- **MCP réel** : `.mcp.json` déclare le serveur `aurora-3d-audit` (`python-services/aurora_3d_mcp.py`) — inspection experte de fichiers 3D. Le Module Code peut le consommer comme service d'audit.
- **Agents & skills** : agents `code-lead` + sous-agents (`code-design-architect`, `code-fidelity-auditor`, `code-sandbox-runner`) ; skills `aurora-*` (pipeline 3D, mesh-score, etc.). Ce sont ton substrat d'orchestration.

---

## 2. CONTRAINTES DURES (violation = échec)

1. **Modifier UNIQUEMENT le Module Code.** Les autres modules (image, 3D, vidéo, voix, vision, analyse, cyber, learning, cowork, conversation, simulator) sont **consommés comme services** via le bridge, jamais réécrits. Tu peux **ajouter** des routes `/api/code/*` au bridge sans casser l'existant.
2. **Ne jamais dégrader un endpoint partagé.** (Bug déjà corrigé : `voice_tts`/`web_*` avaient été rebranchés sur un venv du Code + timeouts ×6 → régression voix/cowork/learning. Ne pas reproduire ce type de couplage.)
3. **Ne jamais casser le Viewer 3D.** Intégration par panneau isolé + non-régression.
4. **JAMAIS d'install dans `application/.venv`** (casserait FLUX/3D). Installs lourdes → **venv isolé dédié** (`~/.local/share/auroraia/venvs/<nom>`) et/ou conteneur. **Aucune accumulation** : ce qui n'améliore pas réellement est retiré proprement.
5. **Licences permissives** (Apache/MIT). GPL/AGPL uniquement en process externe / HTTP (non linké).
6. **Ne pas polluer la racine.** Artefacts/logs → `application/output/…`. Docs de refonte → `application/`.
7. **Aucun secret committé.** Env vars uniquement.

---

## 3. ÉTAT RÉEL DU MODULE (déjà refondu — point de départ)

> Le module N'EST PLUS dans son état cassé initial. Ce qui suit est **vrai** ; vérifie-le par `git log` + lecture avant d'agir. Le pipeline in-app réel : `CodeView → codeViewGeneration → orchestrateCodeGeneration → runAgenticGenerationPhase` (boucle à outils sur FS virtuel WS3), puis sandbox + critiques + correction, puis finalisation + audit visuel.

**Déjà fait et CÂBLÉ (à préserver, ne pas ré-orphaniser) :**
- **Génération agentique** fichier-par-fichier sur `ProjectTree` (WS2/WS3), plan d'architecture JSON contractualisé, protocole d'émission à longueur déclarée **avec récupération** (un fichier mal compté n'est plus droppé en silence).
- **Routage multi-modèles** réel (WS4) : `selectModel` a un corps (raisonnement/coder/vérifieur), best-of-N, plan JSON rejeté si invalide.
- **Classifieur sémantique LLM** (WS6) + **registre de générateurs** pour cibles étendues (compiler, os_kernel, distributed_system, mobile natif, embedded, engine_3d, ide) — câblés en classification et planification, avec fallback déterministe.
- **Design-spec** platform-aware (WS10) : injectée en planification + **gate de vérification** dans la boucle de correction (pas de contrat CSS web sur mobile/jeu ; brand-check deltaE).
- **AST réel tree-sitter** (WS8) dans le critique de syntaxe (fallback lexical), WASM vérifié fonctionnel.
- **Writer disque WS2** (nesting + binaire) branché sur la sauvegarde "Workspace".
- **Garde anti-régression de portée** (WS5) enforcée sur les modifications incrémentales.
- **Juge visuel** (WS9) : l'audit rendu réel est **reponderé dans le finalScore** livré + sauvegardé.
- **Moteur unique in-app** (WS3) : le second moteur bridge NDJSON dormant a été retiré du chemin UI ; le bridge (`/api/code/generate/stream`) reste réservé à l'**API externe** `/api/aurora/code/generate`.
- **Acceptation non-gameable** (WS7 partiel) : un opérateur arithmétique inversé (calculatrice fausse) échoue désormais l'acceptation.
- **Client 3D qualité max** (`python-services/aurora_code/intermodule_3d_quality.py`) : `multi_view=True` (chemin MV-Adapter→TRELLIS) + `purpose=product`, boucle score→rescue→re-run→meilleur candidat, **suppression des runs 3D commandés** après copie, sorties code/3D distinctes.
- **Garde anti-orphelin** (`src/__tests__/codeNoOrphanCapabilities.test.ts`) : échoue si une capacité livrable perd son appelant de production (10 capacités gardées). **Ajoute-y toute nouvelle capacité que tu livres.**
- **Auto-amélioration WS14 DÉJÀ CÂBLÉE (partielle)** : `evaluateAutoToolingForCorrection` (`src/services/codeToolingLoop.ts`) est déclenché **au plateau** de la boucle de correction (`codeValidationCorrectionLoop.ts:224`, quand `isFlatlining && !toolingEvaluationUsed`), endpoint `/api/code/tooling-eval`. Ne repars PAS de zéro : le mécanisme existe mais son A/B keep/remove est **scripté (scénarios de démo `slugify_gain`/`slugify_no_gain`)** — à remplacer par une vraie mesure (§7.2).

**Point d'entrée d'exécution du VRAI pipeline (pour "exécuter et observer").** Le moteur réel est in-app TS : `orchestrateCodeGeneration()` (`src/services/codeOrchestrator.ts`). Les endpoints one-shot `/api/aurora/code/generate` et `/api/code/generate/stream` ne sont PAS ce moteur (ils servent l'API externe) — ne t'en sers pas pour "prouver" la qualité. Pour observer le vrai pipeline en headless : écris un harnais `node --experimental-strip-types` qui importe et appelle `orchestrateCodeGeneration({prompt, enrichedPrompt, configuredCodeModel:'qwen3-coder:30b', …})` avec les callbacks de phase/fichiers/score, Ollama tournant ; les artefacts atterrissent sous `output/code_assets/<run>`. Si ce harnais n'existe pas, **crée-le** (c'est un prérequis de la Loi §0 "exécuté et observé").

**Ce qui RESTE (chantiers §6).** Exécution comportementale réelle en conteneur (WS7), boucle d'auto-régénération visuelle (WS9), émulateurs live multi-appareils (WS12), auto-amélioration/autonomie complètes (§7), correction des artefacts 3D à la source (via collaboration, sans modifier le module 3D).

---

## 4. LOIS INVIOLABLES (à faire respecter dans TOUT ce que tu ajoutes)

1. **Anti-orphelin.** Toute capacité livrée est **appelée depuis le chemin de production** et ajoutée au garde `codeNoOrphanCapabilities.test.ts`. Sinon : câble-la ou retire-la. Pas d'exception.
2. **Zéro échec silencieux.** Toute dégradation (fichier perdu, asset réutilisé, gate contourné, modèle absent, service indisponible) est **remontée explicitement** (note/phase/warning/log), jamais avalée.
3. **Sorties distinctes.** Sorties Code sous `output/code_assets/<run>/{models,images,audio}` et, dans le projet généré, `assets/generated/<run>/…`. Les arbres des autres modules (`output/3d/generations/…`) ne contiennent pas de résidus Code.
4. **Zéro accumulation.** Ce qui est produit pour itérer puis devenu inutile est supprimé (runs 3D commandés, venvs d'essai, outils A/B rejetés). Ne jamais toucher ce qui appartient à un autre module.
5. **Qualité 3D maximale.** Toute demande 3D passe par `intermodule_3d_quality` : `multi_view=True` + `purpose=product`, boucle score→rescue→retry jusqu'au seuil ou budget épuisé, meilleur candidat conservé, warning si sous seuil.
6. **Vérification réelle > proxy.** Un score de qualité doit venir d'une **exécution/rendu réel**, pas d'une regex de présence, dès que c'est techniquement possible.

---

## 5. MÉTHODE DE TRAVAIL (ordre imposé)

Pour chaque chantier : **1) Reprise** (lis le code réel, confirme l'état §3, vérifie chaque preuve `fichier:ligne` avant d'agir — ne fais jamais confiance aveuglément) → **2) Recherche** si limite → **3) Implémentation** vers l'état cible → **4) Tests exhaustifs** (§9) → **5) Auto-correction** (détecter/corriger/re-tester/vérifier non-régression) → **6) Validation finale** (§10) → **7) Traçabilité** (**APPENDRE** au journal existant `application/REFONTE_CODE_JOURNAL.md` — il fait déjà ~217 Ko, ne pas le recréer/écraser : recherches, choix, raisons, avant/après mesurable).

**Git** : branche `refonte/module-code`, commits atomiques par sous-étape (messages français, style `refonte code wsX ...`), tests verts après chaque changement, arbre propre. **Garde WS1 : aucun fichier du module > 400 lignes** (extrais si besoin).

---

## 6. CHANTIERS RESTANTS (état cible → DoD testable)

**WS7 — Exécution comportementale réelle en conteneur** *(XL, transformationnel).*
- **Cible** : sandbox conteneurisé (Podman rootless / Firecracker, **jamais `.venv`**) exécutant le vrai toolchain (tsc/eslint/vitest/playwright ; pytest/mypy/ruff ; cargo/clippy ; go test). Génération + exécution de **tests d'acceptation dérivés du brief**, figés hors périmètre modifiable. Score = **fraction de critères verts réellement exécutés**. Quotas (cgroups v2, quota disque, egress coupé sauf registres). GPU via nvidia-container-toolkit. GC des sandboxes.
- **DoD** : une calculatrice au calcul faux **échoue à l'exécution** (pas seulement à l'analyse statique déjà en place) ; isolation prouvée (le code ne lit pas hors conteneur, fork-bomb/disk-fill contenus) par un test end-to-end réel.

**WS9 — Boucle d'auto-régénération visuelle** *(L, fort).*
- **Cible** : quand le juge visuel (déjà reponderé dans le score) est **sous le seuil**, déclencher une **re-génération ciblée** avec la critique de rendu en indice ; étendre l'audit à `static_web` (servir le preview statique).
- **DoD** : une page laide est détectée puis **corrigée** en re-génération ; `static_web` est audité au rendu réel.

**WS12 — Labo de simulation multi-appareils réel** *(XL, fort).*
- **Cible** : Web (Playwright multi-navigateurs + throttling), **mobile RÉEL** (AVD/Waydroid exécutant l'APK/PWA — jamais un simple redimensionnement), ESP32/Arduino via Renode, Raspberry/OS via QEMU. Consoles : documentées OU différées avec justification.
- **DoD** : la simulation mobile **exécute** le code ; ≥1 firmware simulé (Renode) ; ≥1 image OS bootée (QEMU) jusqu'à un état vérifiable.

**Artefacts 3D à la source** *(via collaboration, sans modifier le module 3D).*
- **Cible** : quand un mesh commandé revient avec artefacts (score bas), la boucle `intermodule_3d_quality` invoque déjà rescue/retry ; **compléter** : si le module 3D expose (ou doit exposer) un correctif à la source, le **demander** via le bridge/MCP `aurora-3d-audit`, pas le recréer côté Code. Documenter tout manque du module 3D dans le journal (chantier séparé côté 3D).
- **DoD** : un mesh à artefacts est soit rescué à qualité acceptable, soit **rejeté avec warning explicite** (jamais livré en silence).

---

## 7. AUTONOMIE, AUTO-AMÉLIORATION, SKILLS & MCP *(cœur de la demande)*

Le Module Code doit devenir **autonome et auto-améliorant** : détecter ses propres limites, aller chercher/installer/évaluer la ressource manquante, garder si meilleur sinon retirer proprement — **tout en restant propre et honnête**.

**7.1 Détection de ses propres limites.** Instrumente le pipeline pour **mesurer** ses échecs récurrents (catégorie d'erreur, langage/cible où le score plafonne, gate qui bloque, temps/VRAM). Écris un journal structuré sous **`output/code-metrics/`** (à créer — seul `output/code_assets/` existe aujourd'hui). **Seuils réels existants à réutiliser** (ne pas réinventer) : plateau de correction `isFlatlining` (~4 pts, `codeValidationCorrectionLoop.ts:196`), seuil visuel dans `blendRenderedVisualIntoFinalScore` (`codeViewGeneration.ts`), seuil de retry du scorer 3D (`retry_threshold` renvoyé par `/api/3d/mesh-score`). Aucune limite n'est "acceptée" en silence : elle est mesurée puis traitée.

**7.2 Auto-amélioration à outils (compléter `codeToolingLoop.ts`, WS14).** Boucle **ReAct** (`run_shell` / `run_tests` / `search_pkg` / `install_dep` / `add_model`) exécutée **dans le sandbox isolé WS7** (jamais `.venv`). Quand la correction plafonne : le module cherche une lib/outil/modèle adapté, l'installe **dans un venv/conteneur isolé**, mesure l'effet **A/B contre la référence** (mêmes briefs, même barème), **conserve si réellement meilleur, sinon retire proprement** (zéro résidu). Registre d'outils approuvés, quotas, allow-list réseau. Résolveur multi-registres (npm/PyPI/crates.io/Maven).
- **État réel** : `codeToolingLoop.ts` est câblé au plateau mais son A/B est **scripté** (scénarios `slugify_gain`/`slugify_no_gain`) — à remplacer par une vraie mesure sur de vrais briefs, au barème réel du pipeline.
- **DoD** : démonstration réelle — le module détecte une limite, installe un outil en venv isolé, mesure un gain A/B **sur briefs réels**, le conserve ; ET un cas où il **retire** proprement un outil inutile ; `.venv` reste intact ; `evaluateAutoToolingForCorrection` reste dans le garde anti-orphelin.

> **Distinction CAPITALE — deux plans à ne jamais confondre :**
> - **Plan AGENT (toi, l'IA de refonte, via le harnais Claude Code)** : tu utilises les **skills `aurora-*`** (outil `Skill`) et le **serveur MCP `aurora-3d-audit`** (stdio) *pendant ton travail* pour analyser, générer, auditer, faire de la veille.
> - **Plan PRODUIT (le Module Code à l'exécution, in-app TS/Python)** : le pipeline **n'est pas un client MCP** et **ne peut pas invoquer les skills du harnais**. Au runtime, il atteint les autres modules **uniquement par le bridge HTTP** (`/api/*`). Ne fais jamais écrire au produit du code qui "appelle un skill" ou "parle MCP" à l'exécution.

**7.3 Skills (plan AGENT).** Sers-toi des skills `aurora-*` comme compétences réutilisables *pour ton travail de refonte* (ex. `aurora-3d-*`/`aurora-mesh-score` pour la 3D, `deep-research` pour la veille techno, `dataviz` pour des visualisations). Tu peux **créer un nouveau skill** (dans `.claude/skills/`, exception permise au périmètre module-only) **seulement s'il est réellement utilisé** — par un agent `code-*` ou une procédure documentée — sinon c'est un skill orphelin (interdit). Un skill n'est adopté que s'il améliore un résultat **mesurable**.

**7.4 MCP.** *Plan AGENT* : consomme `aurora-3d-audit` (`.mcp.json`) pour l'audit 3D expert pendant la refonte. *Plan PRODUIT* : si le pipeline a besoin de cet audit **au runtime**, expose-le par une **route bridge** (`/api/3d/mesh-score` existe déjà ; sinon nouvelle `/api/code/*` qui wrappe les heuristiques de `aurora_3d_mcp.py`) — jamais via le protocole MCP. **Ajout autorisé** : tu peux ajouter *additivement* une entrée `mcpServers` au `.mcp.json` racine (ce n'est PAS une pollution ni une violation du périmètre module-only) **sans toucher** l'entrée `aurora-3d-audit` existante ; toute capacité ajoutée est câblée + testée + documentée, sans dupliquer un autre module.

**7.5 Auto-correction permanente.** Détecter erreurs / incohérences / régressions / pertes de perf / défauts graphiques / bugs → proposer + appliquer un correctif **ciblé par cause** (pas par compteur de tentatives) → **re-tester** → vérifier **aucune régression** (snapshot comportemental + rollback auto si capacité réduite). Une correction qui dégrade une feature est **interdite** et rollback.

**7.6 Autonomie de bout en bout.** L'objectif final : à partir d'un brief (court ou long), le module **planifie, génère, exécute, teste, juge (fonctionnel + visuel), corrige, et se déclare terminé UNIQUEMENT quand la validation réelle passe** — en demandant aux autres modules (image/3D/audio/vision) leurs ressources, en s'auto-outillant si nécessaire, sans intervention humaine et sans jamais surdéclarer sa réussite.

---

## 8. COOPÉRATION INTER-MODULES (endpoints réels — ne pas modifier ces modules)

| Service | Routes réelles (vérifiées) |
|---|---|
| **Assets Code (entrée canonique)** | **`POST /api/code/assets/generate`** (`bridge_server.py:11896`) → `intermodule_assets.py`, orchestre image+3D+voix pour un projet |
| **Image** (FLUX/ComfyUI) | génération = soumission à la file ComfyUI (`POST /proxy/comfy/prompt`) puis récupération **`GET /api/comfyui/image?filename=…`** (route GET, proxy de récupération — PAS un déclencheur) ; statut `GET /api/comfyui/status` ; fallback `POST /api/web/image` |
| **3D** (qualité max) | via `intermodule_3d_quality` → `POST /api/3d/run-pipeline` (`multi_view=True`,`purpose=product`) ; score `POST /api/3d/mesh-score` ; rescue `POST /api/3d/auto-rescue` ; audit 3D expert au runtime = **route bridge** (existante `/api/3d/mesh-score`, ou nouvelle `/api/code/*` qui wrappe les heuristiques de `aurora_3d_mcp.py`) — **jamais le protocole MCP** (voir §7.4) |
| **Voix** (seul audio réel) | `POST /api/voice/tts`, `POST /api/voice/synthesize` |
| **Web/RAG** | `POST /api/web/search|image|extract` ; embeddings `nomic-embed-text` via Ollama |

Assets écrits en fichiers optimisés (avif/webp + srcset ; GLB), **jamais** base64 inline massif, **jamais** `source.unsplash.com`. Ordonnancement VRAM (éviter le swap coder↔vision).

---

## 9. TESTS & VÉRIFICATION (aucune génération "terminée" sans validation réelle)

- **Types à couvrir** : unitaire, intégration, e2e, fonctionnel, UI, rendu, responsive, multi-appareils, perf, mémoire, CPU, GPU, réseau, stabilité, robustesse, sécurité, régression, cohérence.
- **Module** : maintenir **≥ 718 tests code verts** (tu ajoutes des tests par chantier, tu n'en retires pas). Ré-établir le chiffre avec le bon glob avant de t'y fier.
- **Projets générés** : harnais WS7 = génération + exécution de tests d'acceptation figés dans le conteneur ; score = fraction de critères **réellement verts**.
- **Anti-régression** : snapshot comportemental avant/après chaque patch + rollback auto. Re-test complet après chaque correction importante.
- **Anti-orphelin** : `codeNoOrphanCapabilities.test.ts` doit rester vert (ajoute-y tes nouvelles capacités).

---

## 10. DEFINITION OF DONE & VALIDATION FINALE

Un chantier est terminé quand : (a) ses critères d'acceptation §6/§7 sont verts **par exécution réelle** ; (b) la batterie §9 pertinente passe ; (c) la baseline ≥ 718 tests reste verte (augmentée) ; (d) aucune régression ; (e) l'anti-orphelin couvre la nouvelle capacité ; (f) la traçabilité est écrite.

À la fin de chaque tâche, demande-toi : « **Serais-je satisfait, comme ingénieur en chef, de livrer ça ?** » Si non, continue. Tu ne t'arrêtes que quand tu as atteint le **meilleur niveau techniquement réalisable** — et tu documentes honnêtement ce qui reste à valider en environnement live.

---

## 11. LIVRABLES

1. Code (branche `refonte/module-code`), commits atomiques français.
2. Tests (module + harnais + exemples), garde anti-orphelin à jour.
3. `application/REFONTE_CODE_JOURNAL.md` (**existant ~217 Ko — appendre, ne pas recréer**) : par chantier — fait, recherches/technos évaluées, choix + raisons, résultats, avant/après.
4. Mise à jour de `AUDIT_MODULE_CODE.md` / `VERIFICATION_REFONTE_CODE.md` (limites résolues).
5. Récapitulatif final : reste à faire, risques ouverts, ce qui exige une validation live.

---

**Commence par la REPRISE (§5.1), confirme l'état §3, fais respecter les LOIS §4, puis exécute §6–§7. Le seul critère est la qualité finale — et tu ne mens jamais sur ton résultat.**
