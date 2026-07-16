# PROMPT MAÎTRE — Refonte complète du « Module Code » d'AuroraIA vers l'excellence technique absolue

> **À l'IA qui reçoit ce prompt.** Ce document est ton brief **complet et autonome**. Il contient : la mission, la philosophie de qualité, l'environnement, les contraintes dures, l'inventaire exact du code, un **diagnostic déjà réalisé (avec preuves `fichier:ligne`)**, les **15 chantiers** détaillés avec critères d'acceptation, le séquencement, la veille technologique justifiée, la matrice de tests, et la définition de « terminé ». Tu n'as pas besoin de la conversation d'origine. Tu travailles sur un dépôt Git réel (Linux). **Tu commences par ta propre analyse (reprise), tu confirmes ou corriges le diagnostic ci-dessous, puis tu implémentes.** Le seul critère de décision est la **qualité finale**.

---

## 0. RÔLE ET MISSION

Tu es l'ingénieur en chef chargé de rendre le **Module Code** d'AuroraIA aussi **puissant, intelligent, autonome, fiable, précis et qualitatif** que techniquement réalisable. Ce n'est **pas** une amélioration ponctuelle : c'est une **refonte complète**.

**Philosophie non négociable :**
- Le temps de développement, le nombre de recherches, la complexité d'implémentation, le coût en calcul/mémoire **ne sont PAS des critères de décision**. Le **seul** critère est la qualité du résultat final.
- Si une solution demande 10× plus de travail mais produit un résultat nettement supérieur, **c'est elle qu'on retient**.
- Tu ne choisis **jamais** une solution parce qu'elle est plus rapide, plus simple, ou moins gourmande.
- Face à une limite, tu ne dis **jamais** « impossible » sans recherche approfondie (doc officielle, publications, GitHub, bibliothèques récentes, frameworks, moteurs, modèles IA, open source, benchmarks, comparatifs). Si une meilleure solution existe, tu l'utilises.
- Tu effectues une **veille permanente** : meilleur framework / lib / moteur de rendu / moteur UI / compilateur / architecture. Si mieux existe **et améliore réellement le résultat**, tu remplaces.

**But final concret :** le Module Code doit pouvoir produire, avec la **même exigence de qualité** et sans que la qualité ne baisse quand le projet se complexifie : une calculatrice, une landing page, un site vitrine, une web-app complexe, un SaaS, un CRM, un ERP, un IDE, un moteur graphique, un moteur 3D, un jeu, une app mobile, une app desktop, un compilateur, un OS complet, une architecture distribuée, et des projets extrêmement volumineux.

---

## 1. CONTEXTE PROJET & ENVIRONNEMENT (réel, à respecter)

- **Dépôt** : `AuroraIA` (mono-repo). Le code applicatif est sous `application/`.
- **Front** : Tauri v2 + **React 19** + TypeScript 6 + Vite 8 + Tailwind 4 + Zustand 5 + Three.js (@react-three/fiber). Le module tourne dans une **WebView** (Tauri, Linux → WebKitGTK).
- **Services** : **Python** sous `application/python-services/`.
- **Pont** : **bridge Flask** sur `http://localhost:3001` (`application/bridge_server.py`) exposant `/api/*`. Un **tunnel cloudflared** (`*.trycloudflare.com`) publie l'app (Vite `:1420`) via le bridge. URL courante dans `tunnel_url.txt`.
- **LLM** : **Ollama local**. Modèle code actuel = `qwen3-coder:30b` (18 Go, tient en VRAM). Modèle vision partagé = `qwen3-vl:30b`. Config dans `application/src/config/models.ts`.
- **Matériel réel** : Linux (kernel 6.17), **GPU RTX 5070 Ti 16 Go VRAM** + 30 Go RAM + ~71 Go swap. Le swap permet de gros modèles **mais très lentement** (<1 tok/s) → privilégier ce qui tient en VRAM+RAM ; **un seul gros modèle chargé à la fois** (sérialiser les appels Ollama).
- **Tests** : runner **natif Node** (pas de vitest/jest), **Node ≥ 22.6 requis** (hôte : v24.18). Depuis `application/` : `npm test` (= `node --experimental-strip-types --test src/__tests__/*.test.ts`, TOUS les tests). Sous-ensemble « code » (19 fichiers) : `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'`.
- **Baseline anti-régression AVANT travaux** : **391 tests « code » verts / 0 échec** (mesurés sur le sous-ensemble `code*.test.ts`). **Ré-établis ce chiffre avec le bon glob avant de t'y fier.** Tu ne descends jamais sous cette barre sans justification explicite ; tu ajoutes des tests, tu n'en retires pas.

### Démarrage de l'environnement (toutes commandes depuis `application/`)
- Dépendances front : `npm install`.
- **Bridge Flask (port 3001)** : `python bridge_server.py` (le laisser tourner ; **un seul process lourd Python à la fois** — tuer les orphelins avant relance). Vérifier qu'il répond : `curl -s http://localhost:3001/api/comfyui/status`.
- **Front web (Vite :1420)** : `npm run dev:web` (ou app native `npm run dev` = `tauri dev`).
- **Tunnel public** (optionnel) : `npm run start:cloud` ; l'URL courante est écrite dans `application/tunnel_url.txt`.
- **LLM Ollama** sur `http://localhost:11434` : lister `curl -s http://localhost:11434/api/tags` ; tirer un modèle manquant `ollama pull qwen3:32b` / `ollama pull qwen3-coder:30b`.
- **WS9/WS11/WS12/WS15 exigent le bridge + le front vivants** : démarre-les avant tout travail sur ces chantiers.

### Outils système d'isolation (WS7/WS9/WS12)
L'**infrastructure d'isolation** (Podman rootless, QEMU, Renode, navigateurs Playwright) peut être installée **une fois au niveau système**, de façon **idempotente et documentée** dans le journal : vérifie d'abord la présence (`command -v podman qemu-system-x86_64 renode`), n'installe que si absent. **Jamais d'`apt-get` non interactif déclenché pendant une génération** (c'est un bug identifié §5). La disponibilité de `sudo` n'est pas garantie : si un outil ne peut être installé, prévois un **mode dégradé documenté** plutôt qu'un échec. Les dépendances **par projet généré** et les libs d'**auto-amélioration** (WS14) vont, elles, en **venv/conteneur isolés** — jamais `.venv`.

---

## 2. CONTRAINTES DURES (violation = échec de la mission)

1. **Tu ne modifies QUE le Module Code.** Les autres modules (image, 3D, vidéo, audio/voix, vision, analyse, cyber, learning, cowork, conversation, simulator) **ne sont pas modifiés**. Tu les utilises **comme services** (via le bridge Flask / endpoints `/api/*`), jamais en les réécrivant.
2. **Le Viewer 3D existant ne doit JAMAIS être cassé.** Toute intégration UI se fait par panneau isolé + tests de non-régression 3D. Le viewer 3D reste monté tel quel.
3. **Le viewer compact actuel est conservé.** On l'enrichit, on ne le remplace pas.
4. **NE JAMAIS installer dans `application/.venv`** (cela casserait FLUX / le pipeline 3D). Toute install lourde va dans un **venv isolé dédié** (ex. `~/.local/share/auroraia/venvs/<nom>`) et/ou dans un **conteneur isolé**. Aucune accumulation : ce qui n'améliore pas réellement est retiré proprement.
5. **Licences permissives** privilégiées (Apache-2.0 / MIT). Les composants GPL/AGPL (QEMU, SearXNG…) sont utilisés **en process externe / service HTTP** (agrégation, non linké), jamais liés au code.
6. **Ne pas polluer la racine du dépôt.** Artefacts, logs, screenshots → sous `application/output/…` (gitignored ; `git add -f` si tu dois versionner un run). Documentation de refonte → sous `application/`.
7. **Ne jamais committer de secrets** (token HF, clés API). Lire uniquement via variables d'environnement.
8. **Un seul processus lourd Python à la fois** ; tuer les orphelins avant relance (règle standing du projet).
9. **Tu ne touches pas au bridge ni au module 3D côté logique métier** ; tu peux **ajouter** des endpoints `/api/code/*` au bridge si nécessaire, sans casser l'existant, et tu documentes tout ajout.

---

## 3. MÉTHODE IMPOSÉE (ordre non négociable)

Pour **chaque** chantier, et pour l'ensemble :

1. **REPRISE / ANALYSE d'abord.** Avant toute modification : lis intégralement les fichiers concernés et **confirme ou corrige** le diagnostic §5 (ne fais jamais confiance aveuglément à un diagnostic ; vérifie chaque `fichier:ligne` avant d'agir). Aucune modification avant cette analyse. **Checklist des axes à confirmer** (tous, pour chaque zone touchée) : architecture ; fonctionnalités existantes ; dépendances ; interactions inter-modules ; limites graphiques ; limites fonctionnelles ; limites d'architecture ; limites de génération ; limites UX/UI ; limites des moteurs utilisés ; composants obsolètes ; **goulets d'étranglement de performance** (latence VRAM/swap, sérialisation des appels Ollama, temps de build sandbox, taille de contexte, débit de streaming) ; améliorations possibles.
2. **Recherche** (si une limite est rencontrée) : doc officielle, GitHub, libs récentes, benchmarks. Documente ce que tu consultes et pourquoi.
3. **Implémentation** vers l'état cible du chantier.
4. **Tests exhaustifs** (voir §9) : aucune génération/chantier n'est « terminé » sans validation réelle.
5. **Auto-correction** : détecter erreurs/incohérences/régressions/pertes de perf/bugs, proposer + appliquer + **re-tester** + vérifier l'absence de régression.
6. **Validation finale** : te poser la question — « Si j'étais l'ingénieur chargé de produire le meilleur Module Code possible, serais-je satisfait de livrer cette version ? » Si non, tu continues.
7. **Traçabilité** : documenter les recherches, sites consultés, technologies évaluées, choix retenus et **raisons techniques** (mets à jour `application/AUDIT_MODULE_CODE.md` ou un journal `application/REFONTE_CODE_JOURNAL.md`).

**Protocole de travail Git** : travaille sur une branche dédiée (`refonte/module-code`), un commit atomique par sous-étape avec message clair, lance les tests après chaque changement significatif, garde l'arbre propre. Ne committe que quand un incrément est vert.

---

## 4. PÉRIMÈTRE EXACT — inventaire du Module Code

**Services TypeScript** (`application/src/services/`) — ~20 000 lignes :
`codeOrchestrator.ts` (4863, cœur pipeline), `codeIntent.ts` (3221, classification), `codeSandbox.ts` (1533), `codeSystemPrompts.ts` (1075), `codeStaticCritics.ts` (1061), `codeDesignReference.ts` (1024), `codeMissionControl.ts` (789), `codeDesignDirectives.ts` (786), `codeOutputIntelligent.ts` (639), `codePreflight.ts` (516), `codeMultiPassCritique.ts` (477), `codeDesignResearch.ts` (460), `codeAutoCorrection.ts` (437), `codeDevServer.ts` (430), `codeVisualFidelity.ts` (398), `codeStarterTemplates.ts` (393), `codeStructuralAnalysis.ts` (392), `codeResearch.ts` (361), `codeImageGen.ts` (346), `codeOutputFiles.ts` (316), `codeFidelityGate.ts` (226), `codeOutputElevate.ts` (213), `codeReasoningEngine.ts` (189), `codeDeterministicPatcher.ts` (110).

**UI** (`application/src/`) : `views/CodeView.tsx` (2626, vue active skins `manga`/`aurora_v4`), `views/AuroraV1CodeView.tsx` (1780, skins `aurora_v1`/`aurora_v3`), `views/AuroraV3CodeView.tsx` (177) ; `components/CodeProjectPreview.tsx` (486), `CodeCorrectionLog.tsx`, `CodeFileTree.tsx`, `CodeBlock.tsx`, `CodeDiff.tsx` ; `hooks/useCodeViewLogic.ts` (192) ; `stores/codeStreamStore.ts` (921), `codeWorkspaceStore.ts` (147) ; `utils/codeDownload.ts`. Câblage vues : `src/App.tsx:114-118`.

**Python** (`application/python-services/aurora_code/`) : `aurora_code_loop.py` (cœur agentique CLI — **non branché à l'app**), `aurora_code_enrich.py`, `aurora_code_validators.py`, `aurora_code_remote.py`, `cdp_drive.mjs` (pilotage Chrome headless). Mal rangés dans le module (à reclasser, **pas** du sandbox de code) : `proc_sandbox.py` (générateur 3D Blender), `runtime_prepare.py` (bootstrap ML).

**Endpoint bridge réellement appelé** : `POST /api/aurora/code/generate` → `_aurora_code` (`application/bridge_server.py:11595`) — **one-shot naïf**.

**Tests** : 19 fichiers `src/__tests__/code*.test.ts`.

---

## 5. DIAGNOSTIC DÉJÀ RÉALISÉ (à VÉRIFIER puis exploiter)

> Diagnostic issu d'une analyse multi-agents (12 sous-systèmes). **Vérifie chaque preuve avant d'agir.** Détail complet et exploitable dans deux fichiers **versionnés dans le dépôt** : `application/AUDIT_MODULE_CODE.md` (synthèse) et `application/AUDIT_MODULE_CODE_data.json` (données brutes : 32 limites classées, 30 obsolètes, 15 chantiers, 12 recommandations techno, 10 risques). ⚠️ Ce présent prompt est l'**unique source complète autonome** : n'attends aucun autre artefact externe. Si tu as besoin de plus de granularité, reconstruis-la par ta propre REPRISE §3.1.

**Double plafond structurel :**

**A) Fossé production / potentiel.** Le vrai cœur agentique (`aurora_code_loop.py` : extraction multi-fichiers `<FILE>`, validateurs par type, pilotage Chrome CDP → screenshot + rapport runtime réel, scoring vision `qwen3-vl` 0..10, retry, self-critique, remote SSH) est **intégralement mort du point de vue de l'app**. L'app appelle un **one-shot naïf** (`bridge_server.py:11595`) : non streamé, prompt système d'une ligne, sans extraction multi-fichiers, sans validateur, sans CDP, sans retry.

**B) Architecture plafonnante.** Détail des limites critiques (preuves `fichier:ligne`) :

| # | Limite critique | Preuve | Pourquoi ça plafonne la qualité |
|---|---|---|---|
| 1 | Cœur agentique non branché ; chemin réel = one-shot | `bridge_server.py:11595` | L'app livre un blob non structuré, non testé |
| 2 | Génération **mono-shot**, fenêtre unique, sortie tronquée (`num_ctx=24576`, `num_predict=16000`, tous les fichiers dans un blob `--- FICHIER: ---`) | `codeOrchestrator.ts:2506-2549` ; `codeIntent.ts:1853-1876` | Gros projets forcément incomplets/coupés — plafond absolu |
| 3 | `selectModel` **NO-OP** (ignore phase/intent/escalade, renvoie toujours le même modèle) | `codeOrchestrator.ts:730-737` ; `models.ts:83-85` | Même modèle du jouet à l'OS ; aucun vérifieur indépendant |
| 4 | Gates = **heuristiques regex/grep**, aucune vérif fonctionnelle/visuelle/tests réels | `codeOrchestrator.ts:1274-1345,921-1030` ; `codeVisualFidelity.ts:161-338` | Qualité mesurée = proxy syntaxique **gameable** ; un code faux passe à 100 % |
| 5 | **« Sandbox » sans isolation** : dossier horodaté, exécution sur l'hôte avec droits complets (RCE par conception), `sudo apt-get` auto, code **exécuté** (pas juste compilé), `.bat` Windows généré **sur Linux** | `codeSandbox.ts:1332,1477,85,828` | Danger sécurité + validation cosmétique (`fetch HEAD`, 404 = « prêt ») |
| 6 | **Juge LLM de draft neutralisé** : verdict retenu seulement si `realCodeFileCount<2` ; le fallback n'ouvre jamais le missionDossier | `codeOrchestrator.ts:4525` ; `codeMissionControl.ts:418-586` | Le contrat de mission ne sert **jamais** de gate |
| 7 | **3 modules design phares en code mort** (recherche/notation/anti-patterns jamais exécutés) | `codeVisualFidelity.ts:1-5` ; `codeDesignResearch.ts:351` ; `codeDesignDirectives.ts:748` | Le « niveau graphique » repose sur du vide |
| 8 | Blob texte **parsé par regex**, structure **plate**, collisions/écrasements silencieux | `codeOrchestrator.ts:1387-1448` ; `codeOutputFiles.ts:99-115` | Pas d'arborescence ; régressions en cascade |
| 9 | Classification **regex** + types **manquants** (embedded/compiler/OS/distribué/mobile natif) | `codeIntent.ts:6-47,2068` | Routage instable ; ~40 % des cibles inatteignables |
| 10 | **Deux UIs parallèles divergentes** ; la skin par défaut n'utilise pas le vrai orchestrateur | `App.tsx:114-118` ; `AuroraV1CodeView.tsx:433-510` | Qualité dépend du thème ; double maintenance |
| 11 | Pas d'auto-amélioration à outils ; feedback = re-prompt + régénération complète | `aurora_code_loop.py:683-705` ; `codeReasoningEngine.ts:143-145` | Aucune réparation ciblée ni acquisition d'outil/lib/modèle |
| 12 | Escalade **dégradante** (peut supprimer tests/docs, MVP mono-fichier) ; **régression non détectée** (supprimer une feature **augmente** le score) | `codeAutoCorrection.ts:200-207` ; `codeOrchestrator.ts:2572-2583` | Convergence vers un MVP appauvri |
| 13 | Preview **gelée** pendant la génération, **mono-document** ; simulation « appareils » **cosmétique** (change juste la largeur) | `CodeView.tsx:2268,2159-2170` | Aucun retour visuel réel ; simulation ~5 % de couverture |
| 14 | Pas de **décomposition** des projets massifs (objectif tronqué 220 car., review 12 fichiers×600) | `codeMissionControl.ts:265,610-614` | SaaS/ERP/IDE/OS structurellement impossibles à piloter |
| 15 | Bug JSON : **trailing comma** dans le gabarit preflight → apprend au LLM du JSON invalide ; parseur preflight plus faible (ne retire pas `<think>`) | `codePreflight.ts:361,388-398` | Fait basculer le preflight en fallback pauvre |

**Composants obsolètes / code mort à purger (après vérification)** : `selectModel` (NO-OP), endpoint one-shot `_aurora_code`, `codeVisualFidelity.ts` + `codeDesignResearch.ts` + `buildDesignDirectives` (orphelins), `runCritiqueLoop` / `deterministicPatcher` / `classifyFramework` (morts), `codeOutputElevate.ts`, `source.unsplash.com` (**mort, présent dans 4 modules**), maquettes factices `DEMO_FILES`/`BEFORE`/`MODELS`, tables de versions npm **figées**, scrape DuckDuckGo, chemins Windows (`lancement.bat`, PowerShell) sur Linux, `_find_blender` Windows-first, index CUDA `cu128` en dur.

**Interactions inter-modules — actuelles :** seule coopération câblée = **Code → Image** (FLUX/ComfyUI via `codeImageGen`). Sinon Code → Bridge (`/api/brand/enrich`, `/api/web/*`, `/api/code/repo/*`), Code → Extension Aurora-Connect (refs/versions), Code → Ollama (un modèle unique), Code → Vision (`qwen3-vl` partagé, au prix d'un swap VRAM). **Potentielles à établir :** Code → **3D** (vrais GLB au lieu de recettes Three.js recopiées), Code → **Image élargi** (icônes/SVG/textures/sprites, direction artistique unifiée), Code → **Vision juge render-in-the-loop**, Code → **RAG/Analyse** (index projet).

**Endpoints bridge RÉELS à consommer (vérifiés — ne PAS modifier ces modules ; tu peux ajouter des routes SOUS `/api/code/*`) :**

| Service | Routes réelles |
|---|---|
| **Image** (FLUX/ComfyUI) | `POST /api/comfyui/image` ; statut `GET /api/comfyui/status` ; démarrage `POST /api/comfyui/start` ; fallback web `POST /api/web/image`, `POST /api/web/images` |
| **3D** (pipeline aurora-3d, GLB réel) | `POST /api/3d/run-pipeline` ; async `POST /api/ext/3d/generate` + `GET /api/ext/3d/status/<job_id>` ; scène multi-objets `POST /api/3d/compose-scene` ; rescue `POST /api/3d/auto-rescue` ; score `POST /api/3d/mesh-score` ; viewer `POST /api/3d/viewer-html` ; récup fichier `GET /api/3d/file/<path>` |
| **Voix / narration** (SEUL service audio existant) | `POST /api/voice/tts`, `POST /api/voice/synthesize`, `POST /api/voice/tts-audio`, `GET /api/voice/personas`, enrôlement `POST /api/voice/register` |
| **Marque / Web / RAG** | `POST /api/brand/enrich` ; `POST /api/web/search`, `/api/web/image`, `/api/web/images`, `/api/web/extract`, `/api/web/download` |

⚠️ **Il n'existe AUCUN service musique / SFX / foley** : le seul audio disponible est la voix/TTS ci-dessus (voir recadrage WS15).

---

## 6. LES 15 CHANTIERS (WS) — état actuel → état cible → tâches → **critères d'acceptation testables**

> Pour chaque WS : implémente l'état cible, **puis prouve-le** par les critères d'acceptation (Definition of Done). Un WS n'est « terminé » que si TOUS ses critères sont verts **et** la baseline des 391 tests reste verte (augmentée de tes nouveaux tests).

### Pilier 8 — Fondations

**WS1 — Démonteler les monolithes + purger le code mort** *(L, moyen)*
- **Actuel** : `codeOrchestrator.ts` 4863 l., `codeIntent.ts` 3221 l. ; 5+ sous-systèmes morts ; sources de vérité dupliquées (détection langage, `isHeavyWebGLProject`, versions).
- **Cible** : modules < 400 lignes à responsabilité unique (`codeFileParsing`, `codeManifestRepair`, `codeQualityGates`, `codeAssetFetch`, `codeSupportFiles`, pipeline mince), chacun couvert de tests. Code mort **physiquement supprimé** (après avoir vérifié qu'il n'est réellement plus référencé). Une seule source de vérité par fonction.
- **DoD** : aucun fichier du module > 600 lignes ; `grep` prouve 0 import résiduel du code supprimé ; tests unitaires par nouveau module ; 391 tests toujours verts.

**WS2 — Modèle de projet unifié : VFS + graphe + protocole d'émission structuré** *(L, fort)*
- **Actuel** : blob texte parsé par regex, structure plate, casse sur fences imbriquées et `---` YAML/SQL (`codeOutputFiles.ts`).
- **Cible** : `ProjectTree` (dossiers, dédup, inférence de structure) + graphe d'imports validé + **protocole d'émission à longueur déclarée** (insensible aux backticks/tirets internes). Writer disque réel via l'API fs Tauri. Support fichiers sans extension (Dockerfile/Makefile) et binaires (union texte|base64 pour images/glb/wasm).
- **DoD** : round-trip parse→écrire→relire sur des projets piégés (backticks imbriqués, `---` en SQL/YAML, binaires) sans perte ; tests de collision de chemins ; arborescence multi-niveaux préservée.

### Pilier 1 — Génération multi-qualité

**WS3 — Moteur agentique planner-executor sur FS virtuel** *(XL, transformationnel)*
- **Actuel** : `runGenerationPhase` = **un seul appel**, plafond ~16k tokens / ~70 fichiers.
- **Cible** : boucle à outils (`write_file`/`read_file`/`apply_patch`/`run_command`) sur le `ProjectTree`. Étape 1 = architecture (manifeste structuré) ; étape 2 = exécuteur **fichier-par-fichier** avec contexte ciblé (RAG). Chaque `write` déclenche lint/compile réinjecté. **Lève le plafond de taille.**
- **Contrat d'intégration UI (obligatoire pour ne pas casser le chemin app réel)** : le moteur est exposé via une route **`/api/code/*` streamée** (SSE ou NDJSON) émettant des **événements typés** (`phase`, `file.written`, `test.result`, `visual.score`, `correction`, `done`, `error`). `codeStreamStore` et `CodeView`/`AuroraV1CodeView` sont recâblés sur cette route ; l'ancien `POST /api/aurora/code/generate` one-shot n'est **déprécié qu'une fois la parité atteinte**, avec **test de non-régression du parsing de flux** existant. Documenter le schéma d'événements dans le journal.
- **DoD** : génère un projet > 40 fichiers cohérent et buildable ; aucune troncature ; un projet « SaaS mini » (auth + CRUD + tests) construit et testé de bout en bout ; le flux d'événements typés est consommé par l'UI sans régression du streaming existant.

**WS4 — Routage multi-modèles réel + best-of-N + plan contractualisé** *(L, fort)*
- **Actuel** : `selectModel` NO-OP ; plan d'architecture en markdown libre non vérifiable.
- **Cible** : donner un corps à `selectModel` — modèle **raisonnement** pour l'architecture, **coder** pour la génération, **vérifieur DIFFÉRENT** pour le contrôle, escalade cloud sur plateau. Brancher `selectCodeModelForHardware` + `/api/tags`. Plan Architecte en **JSON validé par schéma** (contrainte dure pour l'exécuteur). Sérialiser les appels Ollama (VRAM 16 Go). Best-of-N sur les tâches critiques.
- **DoD** : le vérifieur est un modèle distinct du coder (prouvé par logs) ; le plan est un JSON schéma-valide rejeté si invalide ; démonstration d'escalade sur plateau.

**WS5 — Mémoire projet persistante + RAG + patch incrémental** *(L, fort)*
- **Actuel** : troncature du contexte (8 messages / ~13 000 car.) ; modifs par régénération → régressions.
- **Cible** : index durable (arbre + graphe d'imports + symboles + **embeddings locaux**) ; sélection **RAG** des fichiers pertinents au lieu de tronquer ; modifications = `apply_patch` ciblés contre le graphe.
- **DoD** : sur un projet existant, une demande de modif touche uniquement les fichiers pertinents (patch), sans réécrire tout ; non-régression prouvée sur les fichiers non concernés.

**WS6 — Classification sémantique + taxonomie élargie + registre de générateurs** *(XL, transformationnel)*
- **Actuel** : classifieur **regex** ; types manquants.
- **Cible** : classifieur **LLM structuré** (JSON schéma, fallback déterministe) ; `projectType` étendu (`embedded_esp32`, `embedded_arduino`, `compiler`, `os_kernel`, `distributed_system`, `mobile_ios`, `mobile_android`, `desktop_app` [Tauri/Electron/Qt], `engine_3d`, `ide`…). Interface `ProjectGenerator` (un fichier par famille), dispatch depuis `buildCodeSystemPromptFromIntent`.
- **DoD** : chaque nouveau type route vers un générateur dédié et produit un squelette buildable ; tests de classification sur prompts ambigus.
- **DoD « qualité qui ne baisse jamais » (preuve d'au moins UNE cible extrême, bout en bout)** : démontrer, avec la même métrique fraction-de-critères-verts (WS7) que les cibles web, **au moins l'une** de — (a) un **noyau/OS minimal** généré qui **boote sous QEMU** jusqu'à un heartbeat/prompt vérifiable ; (b) un **mini-compilateur** généré qui compile et exécute correctement un programme de test **figé** ; (c) un **système distribué à ≥ 2 nœuds** qui passe un test d'intégration inter-nœuds.

### Pilier 4 — Tests exhaustifs (KEYSTONE)

**WS7 — Harnais de vérification par exécution + tests d'acceptation** *(XL, transformationnel — PIERRE ANGULAIRE)*
- **Actuel** : « sandbox » sans isolation, validation cosmétique (`fetch HEAD`).
- **Cible** : **sandbox conteneurisé** (Podman rootless / Firecracker microVM — **jamais `.venv`**) exécutant le vrai toolchain (tsc/eslint/vitest/playwright ; pytest/mypy/ruff ; cargo/clippy ; go test…). **Génération systématique de tests d'acceptation** dérivés du brief (unit + property-based + intégration + e2e), **figés hors du périmètre modifiable** par le générateur. Quotas ressources (cgroups v2, quota disque, egress coupé sauf registres). Le **score devient la fraction de critères verts** (signal continu non gameable). GC des sandboxes. **Tests GPU** (WebGL/WebGPU/CUDA générés) : exposer le GPU au conteneur via **nvidia-container-toolkit** (`--device nvidia.com/gpu=all` sous Podman) ; à défaut, exécuter ces tests hors conteneur sur l'hôte avec quotas, et **documenter le compromis d'isolation**.
- **Batterie exhaustive exigée** : unitaire, intégration, e2e, fonctionnel, UI, UX, graphique, rendu, responsive, multi-appareils, multi-résolutions, performance, mémoire, CPU, GPU, réseau, stabilité, robustesse, sécurité, régression, cohérence. **Rejoués après chaque correction importante.**
- **DoD** : aucune génération déclarée « terminée » sans passage vert du harnais ; une calculatrice **fausse** échoue (ne passe plus à 100 %) ; isolation prouvée (le code ne peut pas lire hors du conteneur) ; quotas prouvés (fork-bomb/disk-fill contenus).

**WS8 — Analyse statique AST multi-langage réelle** *(L, fort)*
- **Actuel** : bugs `findClosingBrace` (accolades dans strings, `codeStructuralAnalysis.ts:94-107`), `countFunctions` par moyenne (God-functions jamais détectées, `codeStaticCritics.ts:468`), `bracketBalance`.
- **Cible** : `tree-sitter` (WASM) + tsc/ruff/clippy. McCabe/dead-code/Halstead étendus à Rust/Go/Java/C++/Swift/Kotlin/Dart. Sécurité par **data-flow (taint)**, **toutes** les occurrences rapportées (pas premier-match).
- **DoD** : les cas piégés (accolades dans strings/regex/templates) ne produisent plus de faux positifs ; une God-function est détectée ; analyse fonctionne sur ≥ 6 langages.

### Pilier 2 — Graphique / UX

**WS9 — Juge visuel render-in-the-loop + recherche de références visuelles** *(XL, transformationnel)*
- **Actuel** : `evaluateVisualFidelity` = regex sur la source (`codeVisualFidelity.ts:161-338`), de surcroît orpheline.
- **Cible** : `python-service` **Playwright** headless : screenshots multi-viewport (390 / 834 / 1440) + styles calculés → notation par modèle **vision** (rubrique ancrée : hiérarchie, rythme, contraste **WCAG mesuré sur pixels**, harmonie, densité, verdict « tutoriel vs studio »). L'infra CDP existe déjà côté CLI (`cdp_drive.mjs`) mais n'est pas reliée au chemin app → la relier. Recherche automatique des meilleures **références UX/UI** (via module image / RAG) pour guider la génération.
- **DoD** : le score visuel provient d'un **rendu réel** (screenshot), pas de la source ; une page laide est notée basse et corrigée ; contraste WCAG mesuré sur pixels ; niveau graphique **nettement supérieur** constaté sur un panel de générations.

**WS10 — Système de design structuré + prompt compiler + templates couvrants** *(XL, transformationnel)*
- **Actuel** : conflits (contrat CSS appliqué à tort à mobile/Flutter/jeu `codeSystemPrompts.ts:524-526`), starter unique `apple_product` qui viole son propre contrat, brand-gate hex littéral vs directive oklch (`codeFidelityGate.ts:107-121`), shader Fresnel forcé.
- **Cible** : passe **design-spec JSON** (palette, échelle typo, tokens, composants, wireframe) **vérifiée contre le code**. Taxonomie élargie (`data_dense_enterprise`, `ide_code_editor`, `os_shell`…). Brand-check colorimétrique **deltaE (Lab)** tolérant.
- **DoD** : la design-spec est un contrat vérifié (échec si le code s'en écarte) ; plus de contrat CSS web appliqué à du mobile/jeu ; brand-check en deltaE.

### Pilier 3 — Viewer & simulation

**WS11 — Viewer complet multi-panneaux + rendu applicatif in-browser** *(XL, transformationnel)*
- **Actuel** : preview mono-document gelée pendant la génération ; deux UIs divergentes ; le dev-server strip les imports (`codeOutputFiles.ts:271`).
- **Cible** : **CONSERVER** le viewer compact (`BigLivePreviewFrame`) et **AJOUTER** un atelier dockable couvrant **tous** les panneaux exigés : **arborescence** projet virtualisée, **fichiers**/éditeur, **preview**, **logs**, **erreurs**, **performances**, **simulations** (panneau relié au labo WS12), **états internes**. Moteur **esbuild-wasm + import-map** dans un worker → vrais projets React/Vue/Svelte multi-fichiers **sans dev-server**. Bridge runtime iframe (console/erreurs/perf). Fin du gel de preview. **Unifier** les deux UIs parallèles. **Le Viewer 3D reste intouché** (panneau isolé). Éditeur = **CodeMirror 6** + `react-window` (gros fichiers).
- **DoD** : un projet React multi-fichiers s'exécute dans le viewer sans dev-server ; logs/erreurs/perf/états visibles ; preview vivante pendant la génération ; Viewer 3D prouvé non régressé.

**WS12 — Labo de simulation multi-appareils / multi-environnements** *(XL, fort)*
- **Actuel** : les 3 « devices » ne changent que la largeur (`CodeView.tsx:2159-2170`), ~5 % de couverture.
- **Cible** : **Web** via Playwright (presets DPR/tactile/UA, throttling **réseau/CPU**, **multi-navigateurs réels** Chromium/Firefox/WebKit). **Mobile RÉEL** (téléphone + tablette) : Android via **émulateur AVD** (ou **Waydroid**) exécutant réellement l'APK/PWA ; iOS via **simulateur** si la toolchain est dispo, sinon **limite documentée** — **jamais** un simple redimensionnement de viewport (c'est l'anti-pattern « largeur cosmétique » que l'audit condamne, `CodeView.tsx:2159-2170`). **Microcontrôleurs** (ESP32, Arduino R3…) via **Renode** (MIT ; mock LCD/GPIO/série). **Raspberry par modèle** (Pi Zero/1/2/3/4/5) via **QEMU/Renode** selon le modèle. **OS / images bootables** via **QEMU** (process externe). **Consoles récentes ET vieilles** : documenter explicitement la faisabilité via émulateurs open-source dédiés, OU marquer hors-périmètre avec **justification technique** (ne jamais simuler par un simple changement de largeur). Séquences de **comportement utilisateur**. Différents niveaux de performance, tailles d'écran, OS, réseaux.
- **DoD** : simulation réelle sur ≥ 3 navigateurs + presets device ; **la simulation mobile EXÉCUTE réellement le code** (pas seulement un redimensionnement) ; un firmware ESP32/Arduino se build et se simule (Renode) ; ≥ 1 modèle de Raspberry et ≥ 1 image OS bootable se lancent sous QEMU jusqu'à un état vérifiable ; throttling réseau/CPU effectif ; consoles : couverture démontrée OU différée avec justification écrite.

### Pilier 6 — Auto-correction

**WS13 — Correction pilotée par cause + anti-régression + budget adaptatif** *(L, fort)*
- **Actuel** : stratégie pilotée par le **compteur de tentatives** (`codeAutoCorrection.ts:166-172`) ; stratégies dégradantes ; score = ratio d'étapes sandbox → supprimer une feature **améliore** le score (`codeOrchestrator.ts:2572-2583`) ; incohérence `while(true)` vs cap dur 10.
- **Cible** : stratégie fonction de **(catégorie, localité, historique)**. **Suppression** des stratégies dégradantes. **Harnais anti-régression** : snapshot comportemental (tests passants, exports/endpoints, taille fonctionnelle) avant/après chaque patch, **rollback automatique** si un patch réduit les capacités. Budget **adaptatif** par complexité + arrêt sur **plateau** → escalade de modèle. Diagnostics AST (WS8) et défauts visuels (WS9) réinjectés. **Re-test complet WS7 après chaque correction.**
- **DoD** : supprimer une feature ne peut plus augmenter le score ; un patch régressif est automatiquement rollback ; la stratégie varie selon la cause, pas le compteur.

### Pilier 5 — Auto-amélioration

**WS14 — Boucle à outils d'auto-outillage** *(XL, transformationnel)*
- **Actuel** : feedback = re-prompt texte + régénération complète ; résolveur de versions npm-only.
- **Cible** : boucle **ReAct** (`run_shell`/`run_tests`/`search_pkg`/`install_dep`/`add_model`) dans le sandbox WS7. Quand la correction **plafonne**, le module **cherche/installe/évalue** une lib/outil/modèle **dans un venv ISOLÉ** (jamais `.venv`), mesure l'effet **A/B contre la référence**, **garde si réellement meilleur sinon retire proprement** (zéro accumulation). Registre d'outils approuvés, quotas, allow-list réseau. Résolveur multi-registres (npm/PyPI/crates.io/Maven).
- **DoD** : démonstration d'un cas où le module détecte une limite, installe un outil dans un venv isolé, mesure un gain A/B réel, le conserve — et un cas où il **retire** proprement un outil inutile ; aucun résidu dans `.venv`.

### Pilier 7 — Coopération inter-modules

**WS15 — Client de services inter-modules** *(L, fort)*
- **Actuel** : seule coopération = Code → Image ; `source.unsplash.com` mort dans 4 modules ; base64 inline massif ; directive de **plagiat** (`aurora_code_enrich.py:83-85`).
- **Cible** : `generateAssetsForArchetype` → `AssetBundle` typé routé vers le module compétent **via le bridge** (aucune modif des modules) : **Image élargi** (icônes/SVG/textures/illustrations, direction artistique unifiée seed/palette/référence, via `/api/comfyui/image`), **3D réel** (GLB du pipeline `aurora-3d` via `/api/3d/run-pipeline` au lieu de recettes Three.js recopiées), **Voix/narration** (via `/api/voice/tts`|`/synthesize` — **seul service audio existant**), **Vision** (juge WS9). Assets écrits en **fichiers optimisés** (avif/webp + srcset). **Suppression totale de `source.unsplash.com`**. Recherche par **RAG réel** (fetch pages + embeddings + reranker). **Retrait de la directive de plagiat.** Ordonnancement VRAM (éviter swap coder/vision).
- **Audio — cadrage réaliste** : le bridge n'expose **que** la voix/TTS ; il n'y a **pas** de service musique/SFX. Deux options autorisées, à **documenter** : (a) traiter musique/SFX comme **hors-périmètre de cette vague** et le noter en dette ; (b) si la qualité finale l'exige, ajouter un **micro-service audio dédié EN PROCESS EXTERNE** (aucune modif d'un module existant), exposé par une nouvelle route `/api/code/audio/*`.
- **DoD** : au moins un asset image + un asset 3D (GLB) réellement produits par les autres modules et intégrés en fichiers optimisés ; **au moins un asset voix/TTS intégré** ; musique/SFX **documentés comme réalisés OU explicitement différés avec justification** ; 0 occurrence de `source.unsplash.com` ; directive de plagiat supprimée.

### Vague 0 — Quick-wins (à faire en premier, sans risque)
Purge du code mort **vérifié**, suppression d'Unsplash mort, correction des chemins Windows (`.bat`/PowerShell) sur Linux, **retrait de la directive de plagiat**, correction du **trailing-comma** du gabarit JSON preflight (`codePreflight.ts:361`), télémétrie anti-null. Aucun prérequis ; arrête immédiatement les dégradations actives.

---

## 7. SÉQUENCEMENT RECOMMANDÉ

**WS7 est le keystone** (référencé par WS13, WS14, WS9, WS12) → il doit être solide avant les vagues d'excellence et d'autonomie.

- **Vague 0** (immédiate, parallèle) : quick-wins ci-dessus.
- **Vague 1 — Fondations** : WS1 → WS2 (impossible de bâtir sur un blob-texte monolithique).
- **Vague 2 — Cerveau & vérification** : WS4 (routage + plan contractualisé + vérifieur), WS8 (AST fiable), **WS7** (exécution + tests). Pivot « aucune génération terminée sans validation ».
- **Vague 3 — Montée en puissance génération** : WS3 (agentique fichier-par-fichier), WS5 (mémoire/RAG), WS6 (classification + générateurs), WS13 (auto-correction).
- **Vague 4 — Excellence perçue & autonomie** : WS9 (juge visuel), WS10 (design-system), WS14 (auto-amélioration à outils).
- **Vague 5 — Atelier & simulation** : WS11 (viewer complet, 3D préservé), WS12 (labo multi-appareils), WS15 (coopération inter-modules).

**Rien n'est « terminé » sans passer par WS7.** Chaque vague livre une valeur autonome.

> **Note** : le commanditaire a des priorités visibles fortes sur le **graphique/UX** et le **viewer/simulation** (vagues 4-5). Si tu dois arbitrer, tu peux **avancer un socle minimal de WS9/WS11** en parallèle dès que WS7 est fonctionnel, pour livrer du visible tôt — sans jamais bâtir le juge visuel sur un harnais de vérification instable.

---

## 8. VEILLE TECHNOLOGIQUE & CHOIX (justifiés + licences)

| Domaine | Recommandé | Pourquoi (vs alternatives) | Licence |
|---|---|---|---|
| Modèle code local | **Qwen3-Coder-30B-A3B** (MoE ~3B actifs) | Meilleur rapport qualité/VRAM sur 16 Go, > dense 32B qui offloaderait. Codestral (MNPL), StarCoder2 (OpenRAIL) écartés (licences). | Apache-2.0 |
| Vérifieur/architecte | **Qwen3-32B** (raisonnement), **distinct** du coder | Signal **indépendant** indispensable (un coder qui se juge se false-flag). DeepSeek-R1-Distill (MIT) en alternative. | Apache-2.0 |
| Juge visuel | **Qwen3-VL** (déjà présent, via bridge) | Réutilisation sans nouveau téléchargement ni swap supplémentaire ; rubrique ancrée + self-consistency. | Apache-2.0 |
| Capture/e2e/device web | **Playwright** | Une lib pour capture headless + e2e + **multi-navigateurs réels** (Chromium/Firefox/WebKit) + DPR/tactile/UA + throttling. > Puppeteer (Chromium seul). | Apache-2.0 |
| Bundler viewer | **esbuild-wasm + import-map** | Résout vraiment les imports en mémoire sans serveur. WebContainers/Nodebox écartés (propriétaires). | MIT |
| AST multi-langage | **web-tree-sitter** + tsc/ruff/clippy | Supprime les bugs regex, étend à 10+ langages, WASM self-contained (CSP-compatible). | MIT |
| Sandbox exécution | **Podman rootless** + **Firecracker** (microVM) | Isolation obligatoire pour code LLM arbitraire + installs ; **jamais `.venv`**. Docker écarté (daemon root). | Apache-2.0 |
| Émulation embarquée/OS | **Renode** (ESP32/Arduino/Pi) + **QEMU** (consoles/OS, process externe) | Renode = équivalent open-source de Wokwi (SaaS exclu). QEMU GPL acceptable en agrégation (non linké). | Renode MIT / QEMU GPL-2.0 (externe) |
| Embeddings RAG | **nomic-embed-text** (via Ollama) / **bge-m3** | Local-first, déjà dans Ollama, zéro nouvelle infra ; bge-m3 excellent FR. | Apache-2.0 / MIT |
| Recherche web réelle | **SearXNG** self-host (service HTTP) | Agrégation sans clé API ni coût ; AGPL sans effet (appelé en HTTP, non linké). Tavily/Brave/Serper écartés (SaaS payant). | AGPL-3.0 (externe) |
| Éditeur viewer | **CodeMirror 6** + react-window | Virtualise nativement les très gros fichiers (l'actuel gèle > 50 Ko). Monaco plus lourd. | MIT |
| Moteur/framework UI (projets générés + atelier) | **React 19** (atelier) ; pour les projets générés, choisir selon la cible (React/Vue/Svelte/SolidJS/Qwik) | Le module doit générer plusieurs frameworks UI ; la veille compare adhérence écosystème, perf runtime, DX, accessibilité par défaut. Aucun mono-choix imposé aux projets générés. | MIT / Apache-2.0 |
| Compilateur / toolchain (cibles compiler/OS/embarqué) | Toolchains natives selon cible : **LLVM/Clang**, gcc, **cargo/rustc**, **emscripten** (WASM), **arduino-cli/PlatformIO/ESP-IDF**, cross-compilateurs | Nécessaire pour générer/valider compilateurs, OS et firmware ; exécutées dans le sandbox conteneurisé WS7. Veille sur les backends (LLVM vs cranelift) selon la cible. | Apache-2.0 / LLVM / MIT |

> Tu peux **remplacer** un de ces choix si ta veille prouve qu'un meilleur outil existe **et** améliore réellement le résultat — en documentant le comparatif.

---

## 9. EXIGENCES DE TESTS (aucune génération « terminée » sans validation)

Types à couvrir : **unitaires, intégration, e2e, fonctionnels, UI, UX, graphiques, rendu, responsive, multi-appareils, multi-résolutions, performance, mémoire, CPU, GPU, réseau, stabilité, robustesse, sécurité, régression, cohérence.** Rejoués après **chaque correction importante**.

- **Tests du module lui-même** : `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` → doit rester **≥ 391 verts** (tu ajoutes des tests par chantier).
- **Tests des projets générés** : le harnais WS7 génère et exécute des **tests d'acceptation dérivés du brief**, figés hors du périmètre modifiable, dans un conteneur isolé. Le **score = fraction de critères verts** (non gameable).
- **Non-régression** : snapshot comportemental avant/après chaque patch (WS13) ; rollback auto si capacités réduites.
- **Sécurité** : prouver l'isolation (le code généré ne peut ni lire hors du conteneur ni exfiltrer) ; data-flow taint (WS8).

---

## 10. DÉFINITION DE « TERMINÉ » & VALIDATION FINALE

Un chantier est terminé quand : (a) tous ses critères d'acceptation §6 sont verts ; (b) la batterie de tests §9 pertinente passe ; (c) la baseline 391 tests reste verte (augmentée) ; (d) aucune régression détectée ; (e) la traçabilité est documentée.

À la fin de **chaque** chantier, pose-toi : « **Si j'étais l'ingénieur chargé de produire le meilleur Module Code possible, serais-je satisfait de livrer cette version ?** » Si **non**, tu continues. Tu ne t'arrêtes **jamais** parce que c'est « assez bon » — seulement quand tu as atteint le meilleur niveau techniquement réalisable dans le contexte du projet.

---

## 11. LIVRABLES & REPORTING ATTENDUS

> **Langue** : tous tes livrables destinés à l'humain (journal, messages de commit, récapitulatifs, réponses, documentation) sont rédigés **en français** ; le code et les identifiants restent en anglais si c'est la convention du dépôt.

1. Le code (branche `refonte/module-code`), commits atomiques par sous-étape.
2. Les nouveaux tests (module + harnais + projets d'exemple).
3. Un **journal de refonte** (`application/REFONTE_CODE_JOURNAL.md`) : par chantier — ce qui a été fait, recherches/sites consultés, technos évaluées, choix retenus et **raisons techniques**, résultats de tests, avant/après mesurable.
4. Mise à jour de `application/AUDIT_MODULE_CODE.md` (marquer les limites résolues).
5. Une démonstration reproductible par chantier (commande + résultat attendu).
6. Un récapitulatif final : ce qui reste, risques ouverts, prochaines vagues.

---

## 12. GARDE-FOUS / ANTI-PATTERNS À NE PAS REPRODUIRE

- Ne **jamais** re-livrer un one-shot blob-texte : la génération doit être agentique et structurée.
- Ne **jamais** noter la qualité par regex/grep : la qualité se **mesure par exécution + rendu réel**.
- Ne **jamais** laisser un gate « cosmétique » (ex. `fetch HEAD` = « ça marche »).
- Ne **jamais** faire du score une métrique **gameable** (supprimer une feature ne doit pas améliorer le score).
- Ne **jamais** dégrader vers un MVP pour « passer » : c'est une régression.
- Ne **jamais** installer dans `.venv` ; ne **jamais** casser le Viewer 3D ; ne **jamais** modifier un autre module (l'utiliser comme service).
- Ne **jamais** accumuler des dépendances non prouvées : A/B ou on retire.
- Ne **jamais** générer des artefacts Windows (`.bat`, PowerShell) sur Linux.
- Ne **jamais** dire « impossible » sans recherche approfondie documentée.

---

**Fin du prompt maître. Commence par la REPRISE (analyse §3.1), confirme le diagnostic §5, puis exécute les vagues §7. Le seul critère est la qualité finale.**
