# AUDIT & FEUILLE DE ROUTE — Refonte du Module Code d'AuroraIA

**Date :** 2026-07-15  
**Objectif :** excellence technique absolue du Module Code (le seul critère est la qualité finale).  
**Périmètre :** tout ce qui concerne le Module Code. Les autres modules ne sont pas modifiés — ils sont consommés **comme services**.  
**Méthode :** analyse multi-agents (12 sous-systèmes cartographiés → diagnostic consolidé → feuille de route). Baseline tests avant travaux : **391/391 tests « code » verts**.

**Traçabilité :** cartographies structurées brutes (10 clusters + diagnostic complet 32 limites classées + 30 obsolètes + roadmap 15 chantiers / 12 recos / 10 risques) dans **`application/AUDIT_MODULE_CODE_data.json`** (versionné dans le dépôt) ; 2 clusters complémentaires (sandbox-exec, mission-preflight) ré-analysés séparément et résumés dans la section « COMPLÉMENT » ci-dessous.

---

## SUIVI DES RESOLUTIONS

### 2026-07-15 — Vague 0 / quick-wins appliques

- **Unsplash/LoremFlickr supprimes du chemin Code** : les fallbacks reseau morts sont remplaces par des SVG inline deterministes et encodes (`codeVisualFallbacks.ts`) dans l'orchestrateur, la preview compacte et les post-processeurs.
- **Directive de plagiat retiree** : `aurora_code_enrich.py` demande maintenant une execution originale inspiree du niveau de qualite des meilleurs produits, sans copier des designs proteges.
- **Preflight JSON corrige** : suppression du trailing comma dans l'exemple de schema et nettoyage des blocs `<think>` avant `JSON.parse`.
- **Launchers Linux/macOS** : les generations automatiques et exports Code ajoutent `start.sh` au lieu de `lancement.bat` sur l'environnement Linux.
- **Validation** : baseline Code passee de 391 a **393 tests verts / 0 echec** ; `npm run build` vert. `npm test` complet reste bloque par un test cowork hors perimetre (`/api/cowork/extract-structured` -> 502 bridge).

### 2026-07-15 — Vague 1 / WS1 increment 1 applique

- **Facades publiques mincies** : `codeDesignReference.ts`, `codeDesignDirectives.ts` et `codeSystemPrompts.ts` conservent leurs exports existants mais deleguent les gros blocs statiques vers des modules dedies.
- **Code mort purge** : `codeOutputIntelligent.ts` ne contient plus les passes neutralisees `SEMANTIC_ANIM_RULES`, `HEX_TO_OKLCH`, `elevateColors`, `brandRecolor` ni la branche `cssAnimsInjected`.
- **Reduction mesurable** : `codeDesignReference.ts` 1024 -> 116 lignes, `codeDesignDirectives.ts` 786 -> 214, `codeSystemPrompts.ts` 1066 -> 340, `codeOutputIntelligent.ts` 636 -> 487. Nouveaux modules sous 600 lignes.
- **Validation** : `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` reste a **393 tests verts / 0 echec**.
- **Reste ouvert WS1** : les monolithes principaux (`codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`, `codeSandbox.ts`, `codeStaticCritics.ts`, `codeStreamStore.ts`, `codeMissionControl.ts`) depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 2 applique

- **Mission control separe** : `codeMissionControl.ts` est reduit a la construction du dossier et reexporte la review/regeneration depuis `codeMissionReview.ts`; les types/helpers communs vivent dans `codeMissionShared.ts`.
- **Critiques statiques modularisees** : `codeStaticCritics.ts` devient une facade composite ; syntaxe, securite, structure, accessibilite, completude, integrite projet et complexite sont dans des modules dedies.
- **Reduction mesurable** : `codeMissionControl.ts` 789 -> 323 lignes, `codeStaticCritics.ts` 1061 -> 49 lignes. Tous les nouveaux modules restent sous 600 lignes.
- **Validation** : tests dedies critiques statiques 58 verts / 0 echec ; glob Code complet a **393 tests verts / 0 echec**.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx` et `codeStreamStore.ts` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 3 applique

- **Sandbox modularise** : `codeSandbox.ts` conserve l API publique mais delegue les types, le runtime, les fichiers, la reparation npm et les commandes vers des modules specialises.
- **Auto-install privilegiee retiree du chemin Code** : sur Linux, l absence d un runtime systeme ne lance plus `sudo apt-get`; elle renvoie un echec explicite en attendant le sandbox conteneurise WS7.
- **Artefacts Windows generes nettoyes** : l orchestrateur exclut generiquement les `.bat` des fichiers de support remplaces par `start.sh`.
- **Reduction mesurable** : `codeSandbox.ts` 1522 -> 246 lignes. Nouveaux modules `codeSandboxCommands.ts` (506), `codeSandboxFiles.ts` (297), `codeSandboxRegistryRepair.ts` (300), `codeSandboxRuntime.ts` (151), `codeSandboxTypes.ts` (48).
- **Validation** : tests dedies sandbox 14 verts / 0 echec ; glob Code a **407 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx` et `codeStreamStore.ts` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 4 applique

- **Store Code modularise** : `codeStreamStore.ts` conserve `useCodeStreamStore`, les selecteurs et les types publics, mais delegue types, narration, snapshots, progression et routage modele a des modules dedies.
- **Reduction mesurable** : `codeStreamStore.ts` 921 -> 560 lignes. Nouveaux modules `codeStreamTypes.ts` (132), `codeStreamRouting.ts` (69), `codeStreamNarration.ts` (68), `codeStreamSessions.ts` (68), `codeStreamProgress.ts` (43).
- **Validation** : tests dedies store 12 verts / 0 echec ; glob Code a **419 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 5 applique

- **Intent Code modularise** : `codeIntent.ts` devient une facade publique compatible et delegue types, signaux, catalogue de jeux, marques/sujets, asset plan, complexite, commandes, classification et prompts vers des modules dedies.
- **Reduction mesurable** : `codeIntent.ts` 3221 -> 22 lignes. Les plus gros modules extraits restent sous 600 lignes : `codeIntentClassification.ts` (432), `codeIntentBrandProfilesB.ts` (382), `codeIntentBrandProfilesA.ts` (339), `codeIntentPromptGame.ts` (285), `codeIntentGameCatalog.ts` (260), `codeIntentPromptAssets.ts` (229).
- **Validation** : test dedie intent modules 10 verts / 0 echec ; glob Code a **429 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Limite fonctionnelle non resolue** : cet increment traite WS1 (taille/responsabilites) mais ne pretend pas livrer WS6 ; la classification reste deterministe/heuristique en attendant le classifieur structure et la taxonomie etendue.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx` et `src/__tests__/codeStaticCritics.test.ts` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 6 applique

- **Test monolithe separe** : le bloc de convergence critic+patcher quitte `codeStaticCritics.test.ts` pour `codeStaticCriticsLoop.test.ts`.
- **Reduction mesurable** : `codeStaticCritics.test.ts` 618 -> 470 lignes ; nouveau `codeStaticCriticsLoop.test.ts` 171 lignes.
- **Validation** : tests dedies statiques + boucle 54 verts / 0 echec ; glob Code a **429 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : seuls `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 7 applique

- **Parsing/sanitation extraits de l'orchestrateur** : detection de refus LLM, parsing du contrat `--- FICHIER: ---`, detection de langage, notes, nettoyage JSON/TSConfig/manifest et reparation de dependances quittent `codeOrchestrator.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 4798 -> 4047 lignes. Nouveaux modules : `codeGeneratedFileSanitizer.ts` (471), `codeGeneratedFileParser.ts` (253), `codeLLMRefusal.ts` (66).
- **Validation** : test dedie parsing/sanitation 6 verts / 0 echec ; glob Code a **435 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 8 applique

- **Assets sujet extraits de l'orchestrateur** : recherche d'images sujet, enrichissement de profil marque, substitution des placeholders image et fusion follow-up quittent `codeOrchestrator.ts` pour `codeSubjectAssets.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 4047 -> 3763 lignes. Nouveau module `codeSubjectAssets.ts` (288 lignes) et test dedie `codeSubjectAssets.test.ts` (37 lignes).
- **Validation** : test dedie assets sujet 2 verts / 0 echec ; glob Code a **437 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 9 applique

- **Clarification/follow-up extraits de l'orchestrateur** : filtre de questions vagues, severite des clarifications et analyse de continuite/pivot quittent `codeOrchestrator.ts` pour `codeFollowUpAnalysis.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 3763 -> 3464 lignes. Nouveau module `codeFollowUpAnalysis.ts` (308 lignes) et test dedie `codeFollowUpAnalysis.test.ts` (46 lignes).
- **Validation** : test dedie follow-up 3 verts / 0 echec ; test integration web 9 verts / 0 echec ; glob Code a **440 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 10 applique

- **Gates qualite extraits de l'orchestrateur** : jouabilite web, integrite page, fidelite 3D interactive, score contenu et rapport/retry design quittent `codeOrchestrator.ts` pour `codeQualityGates.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 3464 -> 2922 lignes. Nouveau module `codeQualityGates.ts` (568 lignes) et test dedie `codeQualityGates.test.ts` (35 lignes).
- **Validation** : test dedie gates qualite 3 verts / 0 echec ; tests ciblés web/3D/normalisation 18 verts / 0 echec ; glob Code a **443 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 11 applique

- **Fichiers de support projet extraits de l'orchestrateur** : runbook, README, `start.sh`, injection Tailwind CDN, support SPA Vite/index.html, tooling Tailwind/PostCSS et purge des fallbacks synthetiques quittent `codeOrchestrator.ts` pour `codeProjectSupportFiles.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 2922 -> 2405 lignes. Nouveau module `codeProjectSupportFiles.ts` (527 lignes) et test dedie `codeProjectSupportFiles.test.ts` (31 lignes).
- **Validation** : test dedie supports projet 1 vert / 0 echec ; normalisation generation 9 verts / 0 echec ; glob Code a **444 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 12 applique

- **Validation projet extraite de l'orchestrateur** : validation de sortie vs intent, rejet des fichiers docs-only/generiques, validation `package.json`, detection des structures desktop/web/API et reparation locale TypeScript quittent `codeOrchestrator.ts` pour `codeProjectValidation.ts`.
- **Source de verite corrigee** : `isSyntheticFallbackFile` devient partage par validation et supports projet, ce qui corrige la reference locale orpheline introduite par l'extraction precedente.
- **Reduction mesurable** : `codeOrchestrator.ts` 2405 -> 2129 lignes. Nouveau module `codeProjectValidation.ts` (265 lignes) et test dedie `codeProjectValidation.test.ts` (85 lignes). `codeProjectSupportFiles.ts` reste sous seuil (521 lignes).
- **Validation** : test dedie validation projet 4 verts / 0 echec ; supports + normalisation 10 verts / 0 echec ; glob Code a **448 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 13 applique

- **Runtime et diagnostics pipeline extraits** : constantes de timebox/contexte, routage modele actuel, nom court modele, troncature de texte, diagnostic de generation vide/refus/narrative et detection des blocages environnement quittent `codeOrchestrator.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 2129 -> 2034 lignes. Nouveaux modules `codePipelineRuntime.ts` (41 lignes), `codeGenerationDiagnostics.ts` (70 lignes), tests dedies `codePipelineRuntime.test.ts` (36 lignes) et `codeGenerationDiagnostics.test.ts` (58 lignes).
- **Validation** : tests dedies runtime/diagnostics 8 verts / 0 echec ; glob Code a **456 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 14 applique

- **Phases pipeline extraites de l'orchestrateur** : classification intent, preflight, planning architecte, generation streaming, contexte pivot et validation d'utilisabilite du plan quittent `codeOrchestrator.ts` pour `codePipelinePhases.ts`.
- **Imports lourds rendus paresseux** : Ollama, preflight et mission control sont charges dynamiquement dans les chemins LLM/preflight afin que les tests purs du module restent executables avec le runner Node natif.
- **Reduction mesurable** : `codeOrchestrator.ts` 2034 -> 1596 lignes. Nouveau module `codePipelinePhases.ts` (400 lignes) et test dedie `codePipelinePhases.test.ts` (39 lignes).
- **Validation** : test dedie phases 2 verts / 0 echec ; glob Code a **458 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 15 applique

- **Messages de correction extraits de l'orchestrateur** : construction du prompt auditeur, priorites JSON/TypeScript, contexte recherche/raisonnement, hints design/brand et serialisation des fichiers courants quittent `codeOrchestrator.ts` pour `codeCorrectionMessages.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 1596 -> 1446 lignes. Nouveau module `codeCorrectionMessages.ts` (148 lignes) et test dedie `codeCorrectionMessages.test.ts` (77 lignes).
- **Validation** : test dedie messages correction 2 verts / 0 echec ; glob Code a **460 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 16 applique

- **Scoring validation extrait de l'orchestrateur** : calcul du score sandbox, decision bloquante de critique statique, formatage du rapport et injection de l'etape interne quittent `codeOrchestrator.ts` pour `codeValidationScoring.ts`.
- **Reduction mesurable** : `codeOrchestrator.ts` 1446 -> 1356 lignes. Nouveau module `codeValidationScoring.ts` (95 lignes) et test dedie `codeValidationScoring.test.ts` (120 lignes).
- **Validation** : test dedie scoring validation 4 verts / 0 echec ; glob Code a **464 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 17 applique

- **Boucle validation/correction extraite de l'orchestrateur** : validation sandbox, critiques statiques, gates jouabilite/integrite/3D, strategie correction, recherche, analyse cause racine, regeneration de secours et merge des corrections quittent `codeOrchestrator.ts` pour `codeValidationCorrectionLoop.ts`.
- **Imports LLM/recherche rendus paresseux** : Ollama, recherche de correction, raisonnement et mission-control de secours sont charges dynamiquement dans la boucle, pour garder le module testable sans dependances runtime lourdes.
- **Reduction mesurable** : `codeOrchestrator.ts` 1356 -> 939 lignes. Nouveau module `codeValidationCorrectionLoop.ts` (407 lignes) et test dedie `codeValidationCorrectionLoop.test.ts` (96 lignes).
- **Validation** : test dedie boucle validation/correction 4 verts / 0 echec ; glob Code a **468 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 18 applique

- **Preparation planning extraite de l'orchestrateur** : recherche best-practices, heuristique brief simple, enrichissement dynamique de marque, recuperation d'images sujet et construction des blocs planning quittent `codeOrchestrator.ts` pour `codePipelinePreparation.ts`.
- **Imports bridge/recherche rendus paresseux** : recherche web, enrichissement marque et images sujet sont charges dynamiquement dans la preparation pour garder les helpers purs testables.
- **Reduction mesurable** : `codeOrchestrator.ts` 939 -> 772 lignes. Nouveau module `codePipelinePreparation.ts` (189 lignes) et test dedie `codePipelinePreparation.test.ts` (87 lignes).
- **Validation** : test dedie preparation planning 4 verts / 0 echec ; glob Code a **472 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `codeOrchestrator.ts`, `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 19 applique

- **Retry qualite de sortie extrait de l'orchestrateur** : parsing initial, merge follow-up, review draft, brand-gate, prompt de regeneration, detection reseau et fallback meilleur essai quittent `codeOrchestrator.ts` pour `codeGenerationOutputRetry.ts`.
- **Seuil WS1 atteint cote orchestrateur** : `codeOrchestrator.ts` descend sous 600 lignes et devient une facade de pipeline lisible.
- **Reduction mesurable** : `codeOrchestrator.ts` 772 -> 560 lignes. Nouveau module `codeGenerationOutputRetry.ts` (311 lignes) et test dedie `codeGenerationOutputRetry.test.ts` (100 lignes).
- **Validation** : test dedie retry sortie 5 verts / 0 echec ; glob Code a **477 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 20 applique

- **Panneaux CodeView extraits** : console pipeline, preview live, barre navigateur, critique statique, commentaire Lyra et puce langage quittent `CodeView.tsx` pour des modules de vue dedies.
- **Helpers purs separes** : detection langage fichier et detection de preview WebGL lourde vivent dans des modules `.ts` testables sans charger React/JSX.
- **Reduction mesurable** : `CodeView.tsx` 2626 -> 1945 lignes. Nouveaux modules `codeViewPreviewPanel.tsx` (289), `codeViewInspectorPanels.tsx` (349), `codeViewLanguage.ts` (41), `codeViewPreviewHeuristics.ts` (12) et test `codeViewExtractedHelpers.test.ts` (50).
- **Validation** : test dedie helpers vue 4 verts / 0 echec ; glob Code a **481 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 21 applique

- **Panneau livraison CodeView extrait** : arborescence fichiers, actions copier/telecharger, toggle lignes, simulateur/code viewer, recherche fichier, resultat sandbox et notes quittent `CodeView.tsx` pour `codeViewDeliveryPanel.tsx`.
- **Recherche fichier testable** : le comptage des occurrences de recherche est sorti dans `codeViewSearch.ts`, sans importer React/JSX dans les tests.
- **Reduction mesurable** : `CodeView.tsx` 1945 -> 1642 lignes. Nouveau module `codeViewDeliveryPanel.tsx` (385 lignes), helper `codeViewSearch.ts` (10 lignes), test vue etendu a 59 lignes.
- **Validation** : test dedie helpers vue 5 verts / 0 echec ; glob Code a **482 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 22 applique

- **Colonne gauche CodeView extraite** : mission, guide de brief, fichiers contexte, pack assets, runtime, intent, preflight, corrections, design polish, conversation, export, actions et diagnostics quittent `CodeView.tsx`.
- **Sous-decoupage sous seuil** : la colonne est scindee en `codeViewControlPanel.tsx` et `codeViewControlActions.tsx` afin de ne pas recreer un nouveau monolithe UI.
- **Reduction mesurable** : `CodeView.tsx` 1642 -> 1071 lignes. Nouveaux modules `codeViewControlPanel.tsx` (552 lignes) et `codeViewControlActions.tsx` (193 lignes).
- **Validation** : test dedie helpers vue 5 verts / 0 echec ; glob Code a **482 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : `CodeView.tsx` et `AuroraV1CodeView.tsx` depassent encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 23 applique

- **Generation CodeView extraite** : le callback principal de generation, la reprise apres reload, le streaming coalesce, la clarification et la sauvegarde finale quittent `CodeView.tsx` pour `codeViewGeneration.ts`.
- **Chrome et helpers shell separes** : le decor/hero CodeView vit dans `codeViewChrome.tsx`; les libelles projet, le guide de brief, le label pipeline et la detection vision contexte vivent dans `codeViewShellHelpers.ts`.
- **Seuil WS1 atteint cote CodeView principal** : `CodeView.tsx` descend sous 600 lignes et redevient un shell d'etat/callbacks lisible.
- **Reduction mesurable** : `CodeView.tsx` 1071 -> 595 lignes. Nouveaux modules `codeViewGeneration.ts` (537 lignes), `codeViewChrome.tsx` (55 lignes), `codeViewShellHelpers.ts` (81 lignes). Test helpers vue etendu a 98 lignes.
- **Validation** : test dedie helpers vue 8 verts / 0 echec ; glob Code a **485 tests verts / 0 echec** ; `npm run build` vert ; `git diff --check` vert.
- **Reste ouvert WS1** : seul `AuroraV1CodeView.tsx` depasse encore 600 lignes.

### 2026-07-15 — Vague 1 / WS1 increment 24 applique

- **Aurora V1 CodeView decoupee** : helpers, preview instrumentee, live view, overlays, sidebar, preview centrale et colonne output/composer quittent `AuroraV1CodeView.tsx` pour des composants dedies.
- **Helpers purs testes** : detection langage stream et instrumentation HTML de preview sont extraites dans `auroraV1CodeHelpers.ts` et couvertes par `codeAuroraV1Helpers.test.ts`.
- **Seuil WS1 atteint partout dans le module Code applicatif** : le scan des fichiers `*code*` / vues Code ne remonte plus aucun fichier au-dessus de 600 lignes.
- **Reduction mesurable** : `AuroraV1CodeView.tsx` 1780 -> 414 lignes. Nouveaux modules : `auroraV1CodeOutputPane.tsx` (438), `auroraV1CodeOverlays.tsx` (304), `auroraV1CodeSidebar.tsx` (261), `auroraV1CodeHelpers.ts` (142), `auroraV1CodePreviewPane.tsx` (135), `auroraV1CodePreviewFrame.tsx` (124), `auroraV1CodeLiveView.tsx` (90), `auroraV1CodeMachinePanel.tsx` (16), `auroraV1CodePrimitives.tsx` (15).
- **Validation** : test dedie helpers V1 3 verts / 0 echec ; glob Code a **488 tests verts / 0 echec** ; `npm run build` vert ; scan lignes WS1 vert ; `git diff --check` vert.
- **WS1 cloture** : tous les fichiers applicatifs du Module Code identifies sont sous 600 lignes.

### 2026-07-15 — Vague 1 / WS2 increment 25 applique

- **Socle `ProjectTree` introduit** : nouveau modele VFS pur dans `codeProjectTree.ts` avec fichiers, dossiers, collisions de chemins, encodage texte/base64 et graphe d'imports.
- **Limite #6 partiellement reduite** : la sortie peut maintenant etre representee autrement qu'en liste plate, avec deduplication deterministe, detection case-insensitive, recuperation des chemins dangereux sous `recovered/` et preservation des dossiers multi-niveaux.
- **Cas WS2 couverts** : fichiers sans extension (`Dockerfile`, `Makefile`), chemins Windows normalises, collisions exactes/casse, imports relatifs resolus, imports locaux manquants signales, binaires `base64` preserves.
- **Reduction mesurable / nouveaux fichiers** : `codeProjectTree.ts` 449 lignes ; `codeProjectTree.test.ts` 102 lignes.
- **Validation** : test dedie ProjectTree 5 verts / 0 echec ; glob Code a **493 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS2 reste ouvert** : protocole d'emission a longueur declaree, round-trip parse/ecrire/relire et writer disque Tauri restent a brancher sur ce socle.

### 2026-07-15 — Vague 1 / WS2 increment 26 applique

- **Protocole d'emission structure introduit** : `codeProjectEmission.ts` ajoute le format `AURORA_CODE_VFS/1` avec metadonnees JSON et contenu tranche par `length`, au lieu des fences markdown ou separateurs `---`.
- **Robustesse prouvee** : le parser conserve les backticks imbriques, les blocs YAML/SQL contenant `---`, les marqueurs de fin presents dans le contenu, les binaires base64 et les collisions de chemins.
- **Detection d'erreurs** : longueur incoherente, header malforme, metadonnees invalides et marqueur de fin absent remontent des issues structurees sans avaler le fichier valide suivant.
- **Reduction mesurable / nouveaux fichiers** : `codeProjectEmission.ts` 207 lignes ; `codeProjectEmission.test.ts` 110 lignes.
- **Validation** : test dedie emission 5 verts / 0 echec ; glob Code a **498 tests verts / 0 echec**.
- **WS2 reste ouvert** : brancher ce protocole dans les prompts/parseurs existants et ajouter le writer disque Tauri + round-trip fichier reel.

### 2026-07-15 — Vague 1 / WS2 increment 27 applique

- **Parseurs recables en compatibilite ascendante** : `parseCodeFiles` et `extractGeneratedFiles` lisent maintenant `AURORA_CODE_VFS/1` en priorite, tout en gardant le vieux format `--- FICHIER` pour les historiques et les retries existants.
- **Prompts Code bascules vers WS2** : Codeur, retry, rescue, starter templates, expert prompt et prompt intent demandent le protocole structure a longueur declaree au lieu des fences markdown.
- **Refus LLM durci** : une sortie `AURORA_CODE_VFS/1` n'est plus classable comme refus, meme si elle contient du texte susceptible de ressembler a une reponse narrative.
- **Validation** : tests parseurs/prompts cibles 90 verts / 0 echec ; glob Code a **500 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; scan WS1 toujours vert.
- **WS2 reste ouvert** : le writer disque Tauri et le round-trip ecrire/relire reel restent a livrer pour cloturer les criteres d'acceptation.

### 2026-07-15 — Vague 1 / WS2 increment 28 applique

- **Writer disque WS2 introduit** : `codeProjectWriter.ts` ecrit un `ProjectTree` via les wrappers fs Tauri existants (`fsMkdir`, `fsWriteText`, `fsWriteBinary`) et peut relire via `fsReadText`/`fsReadBinary`.
- **Round-trip prouve** : test `parse -> write -> read` sur contenu piege (`---`, backticks, marqueur interne), arborescence multi-niveaux, `Dockerfile` et binaire base64/WASM.
- **Support binaire reel** : les fichiers `encoding="base64"` sont decodes en bytes a l'ecriture puis re-encodes a la lecture, au lieu d'etre ecrits comme texte base64.
- **Validation** : test dedie writer 3 verts / 0 echec ; glob Code a **503 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; scan WS1 toujours vert.
- **WS2 cloturable cote fondation** : `ProjectTree`, graphe d'imports, protocole longueur declaree, parseurs, prompts et writer sont presents. Les integrations profondes WS3/WS5 devront maintenant utiliser ce socle plutot que les listes plates.

### 2026-07-15 — Vague 2 / WS4 increment 29 applique

- **`selectModel` n'est plus un NO-OP** : `codePipelineRuntime.ts` delegue a `codeModelRouting.ts`, qui route par phase (`planning`, `generation`, `review`, `correction`) au lieu de renvoyer systematiquement le modele configure.
- **Branchement `/api/tags` effectif** : `codeStreamStore.ts` propage `installedModels` et `hardware` a l'orchestrateur ; planning, generation, retry et correction recoivent ce contexte via `CodeModelRoutingContext`.
- **Roles distincts quand disponibles** : generation selectionne le Codeur via `selectCodeModelForHardware`; planning/correction selectionnent `qwen3:32b` ou une variante Qwen3-32B installee comme Architecte/Verifieur independant. Si aucun verifieur n'est connu dans `/api/tags`, le fallback vers le Codeur est explicite et teste.
- **Constantes de role Code ajoutees** : `CODE_REASONING_MODEL`, `CODE_VERIFIER_MODEL`, `CODE_PLANNING_MODEL`, `CODE_REVIEW_MODEL`. `AUXILIARY_ANALYSIS_MODEL` reste inchange pour eviter une regression hors Module Code.
- **Validation** : `codeModelRouting.test.ts` 4 verts ; `codePipelineRuntime.test.ts` 5 verts ; `codePipelinePhases.test.ts` 2 verts ; glob Code a **508 tests verts / 0 echec**.
- **WS4 reste ouvert** : le plan Architecte est encore du markdown libre ; le schema JSON, le best-of-N et l'escalade cloud sur plateau restent a implementer et a prouver.

### 2026-07-15 — Vague 2 / WS4 increment 30 applique

- **Plan Architecte contractualise** : `codeArchitecturePlan.ts` introduit `CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION`, un schema JSON local, un parseur robuste, une normalisation canonique et un rejet des plans invalides.
- **Prompts Architecte recables** : `buildArchitecteSystemPrompt` et `buildArchitecturePlanningPrompt` demandent maintenant un objet JSON valide uniquement, sans markdown ni prose hors JSON.
- **Gate de plan durcie** : `isArchitecturePlanUsable` valide le schema au lieu de compter des sections markdown ; `runPlanningPhase` retourne le JSON canonique ou rejette le plan.
- **Consommateur README migre** : `codeProjectSupportFiles.ts` extrait dependances et scripts depuis le plan JSON, avec fallback legacy pour les anciens plans markdown.
- **Validation** : `codeArchitecturePlan.test.ts` 4 verts ; tests cibles prompts/phases 64 verts ; glob Code a **512 tests verts / 0 echec**.
- **WS4 reste ouvert** : best-of-N et escalade cloud sur plateau ne sont pas encore livres.

### 2026-07-15 — Vague 2 / WS4 increment 31 applique

- **Best-of-N Architecte branche** : `codeArchitecturePlanSelection.ts` active un best-of-2 pour les projets `complex`/`enterprise`, valide chaque plan JSON et selectionne le meilleur par score deterministe.
- **Planning multi-candidat reel** : `runPlanningPhase` effectue plusieurs appels Architecte serialises pour les taches critiques, puis transmet uniquement le plan canonique gagnant a l'executeur.
- **Escalade plateau branchee** : le signal de stagnation de `codeValidationCorrectionLoop.ts` (`isFlatlining`) est transmis au routeur modele via `plateau: true`.
- **Route plateau prouvee** : si `/api/tags` expose un modele cloud/haut de gamme (`CODE_CLOUD_HIGH_MODEL`, `CODE_NEXT_MODEL`, Qwen3-32B), `codeModelRouting.ts` le prefere en correction avec une raison `plateau-cloud-escalation`; sinon fallback local inchange.
- **Validation** : `codeArchitecturePlanSelection.test.ts` 2 verts ; `codeModelRouting.test.ts` 5 verts ; `codePipelinePhases.test.ts` 2 verts ; glob Code a **515 tests verts / 0 echec**.
- **WS4 socle TypeScript cloturable** : restent a rejouer des generations reelles avec Ollama/bridge dans WS7/WS3 pour prouver le comportement end-to-end sous charge.

### 2026-07-15 — Vague 2 / WS8 increment 32 applique

- **Scanner lexical partage** : `codeLexicalAnalysis.ts` masque commentaires, strings, regex et templates en conservant les lignes ; `findMatchingBraceLine` et `bracketBalanceIgnoringLiterals` remplacent les comptages bruts d'accolades/brackets.
- **McCabe/Halstead multi-langage et God-functions** : `codeStructuralAnalysis.ts` detecte les fonctions TS/JS, Python, Rust, Go, Java, C/C++, Swift, Kotlin et Dart ; `codeStaticStructure.ts` mesure les vraies bornes de fonctions au lieu d'une moyenne.
- **Securite plus exploitable** : `securityCritic` rapporte toutes les occurrences de chaque regle et ajoute une propagation locale de taint vers sinks HTML, reseau, SQL, commande, redirect, header et eval sans dependre uniquement des noms `req`/`input`.
- **Validation** : `codeStructuralAnalysis.test.ts` 22 verts ; `codeStaticCritics.test.ts` 49 verts ; glob Code a **522 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS8 reste ouvert** : le DoD fonctionnel pieges/God-function/>=6 langages est couvert ; restent l'integration `web-tree-sitter` WASM et les diagnostics toolchain reels `tsc`/`ruff`/`clippy` a brancher dans un increment suivant.

### 2026-07-15 — Vague 2 / WS8 increment 33 applique

- **Diagnostics toolchain branches au sandbox** : `codeToolchainDiagnostics.ts` produit des commandes optionnelles `tsc --noEmit`, `ruff check .` et `cargo clippy --all-targets --all-features -- -D warnings` selon les fichiers/langages presents.
- **Insertion sans pollution d'environnement** : les diagnostics Node/Python sont inseres apres les etapes d'installation d'environnement existantes ; `ruff` passe par le Python `aurora-python-env` du sandbox ; aucune installation systeme Linux non interactive n'est ajoutee.
- **Runner conserve** : `runCodeSandboxValidation` enrichit le plan de validation via `withToolchainDiagnostics` sans changer le comportement bloquant des commandes principales.
- **Validation** : `codeSandboxModules.test.ts` 17 verts ; glob Code a **525 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS8 reste ouvert** : les diagnostics `tsc`/`ruff`/`clippy` sont maintenant dans le pipeline sandbox ; reste l'AST WASM `web-tree-sitter` a brancher pour remplacer les heuristiques par parser quand les grammaires sont disponibles.

### 2026-07-15 — Vague 2 / WS8 increment 34 applique

- **AST WASM reel ajoute** : dependances `web-tree-sitter@0.20.8` (MIT) et `tree-sitter-wasms@0.1.13` (Unlicense), alignees ABI 0.20 pour charger les grammaires precompilees.
- **Adaptateur paresseux** : `codeTreeSitterAst.ts` mappe TS/TSX/JS/Python/Rust/Go/Java/C/C++/Swift/Kotlin/Dart vers les WASM, initialise `web-tree-sitter` a la demande et retourne un resume AST compact.
- **Preuve executable** : `codeTreeSitterAst.test.ts` parse reellement JavaScript via WASM et verifie les grammaires WS8.
- **Validation** : `codeTreeSitterAst.test.ts` 2 verts ; glob Code a **527 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code). `npm audit` signale encore 4 vulnerabilites sur `postcss`/`react-router`/`vite`, pas introduites par les deux paquets AST.
- **WS8 cloturable cote socle** : scanner lexical, DoD pieges/God-function/>=6 langages, taint, occurrences multiples, diagnostics `tsc`/`ruff`/`clippy` et adaptateur `web-tree-sitter` sont presents et testes. Le remplacement integral des heuristiques par requetes AST par langage pourra maintenant se faire incrementalement.

### 2026-07-15 — Vague 2 / WS7 increment 35 applique

- **Critere d'acceptation interne ajoute** : `codeAcceptanceCriteria.ts` derive un pas `internal:acceptance-criteria` depuis le brief et expose un `acceptance-score=N` base sur la fraction de criteres verts.
- **Calculatrice fausse refusee** : une demande de calculatrice exige maintenant etat de saisie/resultat, quatre operations en logique, flux egal/resultat et clear/reset ; une UI statique avec boutons ne peut plus passer a 100 %.
- **Aucune livraison verte sans acceptation** : `runCodeSandboxValidation` execute ce pas apres les commandes sandbox, y compris quand aucune commande toolchain n'est applicable, et retourne un echec si l'acceptation echoue.
- **Score non gameable renforce** : `computeSandboxScore` lit `acceptance-score` et borne le score final par cette fraction de criteres verts, au lieu de se contenter du ratio d'etapes sandbox.
- **Validation** : `codeAcceptanceCriteria.test.ts` 2 verts ; tests cibles acceptance/scoring/sandbox 24 verts ; glob Code a **530 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS7 reste ouvert** : l'isolation Podman/Firecracker, les quotas cgroups/disque, le GC de sandboxes, la preuve de lecture hors conteneur impossible et le compromis GPU ne sont pas encore livres dans cet increment.

### 2026-07-15 — Vague 2 / WS7 increment 36 applique

- **Nom Python sandbox durci** : les commandes Python creent maintenant `aurora-python-env` dans le sandbox au lieu d'un chemin `.venv`, via `codePythonEnvironment.ts`.
- **Consommateurs unifies** : `codeSandboxCommands.ts`, `codeToolchainDiagnostics.ts` et `codeDevServer.ts` utilisent le meme executable Python Aurora pour requirements, pytest, compileall, ruff et serveurs FastAPI/Django/Flask.
- **Preuve anti-regression** : `codeSandboxModules.test.ts` verifie la creation de l'environnement Python Aurora, l'executable ruff et l'absence de chemin interdit dans les commandes du Module Code.
- **Validation** : scan `rg` sur `src/services/code*` et `src/__tests__/code*` sans occurrence de chemin `.venv` ; `codeSandboxModules.test.ts` 18 verts ; glob Code a **531 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS7 reste ouvert** : ce durcissement retire un anti-pattern d'environnement, mais ne remplace pas encore l'isolation conteneurisee et les quotas.

### 2026-07-15 — Vague 2 / WS7 increment 37 applique

- **Preflight isolation bloquant** : `runCodeSandboxValidation` detecte Podman rootless + cgroups v2 avant toute commande executable ; si indisponible, il retourne un echec WS7 au lieu d'executer le code genere sur l'hote.
- **Wrapper Podman par commande** : `codeSandboxIsolation.ts` encapsule les commandes dans `podman run --rm --pull=never`, avec `--userns keep-id`, `--security-opt no-new-privileges`, `--cap-drop ALL`, `--read-only`, reseau coupe par defaut et image par langage.
- **Quotas branches** : plan Podman avec `--memory 2g`, `--cpus 2`, `--pids-limit 256`, `--ulimit fsize=1048576:1048576`, tmpfs `/tmp` et `/home/aurora` a 256m. Les installs utilisent `slirp4netns:allow_host_loopback=false` ; les autres commandes utilisent `--network none`.
- **Preuve hote** : sur cette machine, `podman`/Firecracker sont absents et cgroups v2 est present ; le mode degrade documente est donc un echec propre demandant installation hors generation, pas un fallback dangereux.
- **Validation** : `codeSandboxIsolation.test.ts` + tests sandbox/scoring cibles 30 verts / 0 echec ; glob Code a **536 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS7 reste ouvert** : la limitation disque totale du workspace bind-mounte, la preuve runtime de lecture hors conteneur impossible, le GC des sandboxes et le compromis GPU restent a livrer.

### 2026-07-15 — Vague 2 / WS7 increment 38 applique

- **GC des sandboxes ajoute** : `codeSandboxGc.ts` planifie et supprime les anciens dossiers horodates sous `output/code-sandbox`, par age et nombre maximal conserve, sans toucher les noms non horodates.
- **Suppression structuree** : `useTauri.ts` expose les commandes existantes `fs_list_dir` et `fs_remove_dir_all` cote desktop/cloud ; pas de `rm -rf` shell ajoute.
- **Integration non bloquante** : `runCodeSandboxValidation` lance le GC avant de creer le nouveau sandbox et journalise un step `internal:sandbox-gc` quand une suppression a lieu ; une erreur GC est signalee sans masquer la validation.
- **Validation** : `codeSandboxGc.test.ts` + tests isolation/sandbox cibles 27 verts / 0 echec ; glob Code a **540 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS7 reste ouvert** : GC livre ; restent la preuve runtime d'isolation avec Podman installe, fork-bomb/disk-fill/host-read, disque total et GPU.

### 2026-07-15 — Vague 2 / WS7 increment 39 applique

- **Probes d'isolation ajoutees** : `codeSandboxIsolationProbes.ts` cree une sentinelle host hors sandbox, la nettoie apres execution, puis lance apres preflight Podman vert trois preuves avant les commandes projet : host-read, quota PIDs et quota taille fichier.
- **GC des sentinelles** : le GC WS7 supprime aussi les `AURORA_HOST_SENTINEL_*` abandonnees si l'application est interrompue avant le nettoyage `finally`.
- **Blocage avant validation projet** : `runCodeSandboxValidation` ajoute les steps de probes et retourne un echec si l'une des preuves echoue ; les commandes du projet ne demarrent qu'apres ces preuves vertes.
- **Preuves testees sans Podman local** : les commandes Podman generees sont testees en unitaire ; sur l'hote actuel, elles ne s'executent pas car l'increment 37 bloque deja Podman absent.
- **Validation** : `codeSandboxIsolationProbes.test.ts` + tests isolation/GC/sandbox cibles 32 verts / 0 echec ; glob Code a **545 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS7 reste ouvert** : probes prêtes, mais preuve runtime effective encore dependante de Podman installe ; disque total workspace et GPU restent a traiter.

### 2026-07-15 — Vague 2 / WS7 increment 40 applique

- **GPU conteneurise branche** : `codeSandboxGpu.ts` detecte les signaux WebGL/WebGPU/CUDA/NVIDIA dans le brief et les fichiers ; si GPU requis, le harnais exige `nvidia-smi` hote + `nvidia-ctk cdi list` avec `nvidia.com/gpu=all`.
- **Exposition GPU Podman** : `buildPodmanSandboxArgs` ajoute `--security-opt label=disable --device nvidia.com/gpu=all` uniquement quand le preflight CDI est vert ; pas de fallback hote silencieux.
- **Mode degrade documente** : sur cet hote, `nvidia-smi -L` voit la RTX 5070 Ti, mais `podman` et `nvidia-ctk` sont absents ; les projets GPU restent donc bloques proprement jusqu'a installation hors generation.
- **Validation** : tests GPU/isolation/probes/GC/sandbox cibles 38 verts / 0 echec ; glob Code a **551 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS7 reste ouvert** : GPU policy livree ; restent la limitation disque totale workspace, l'egress strictement limite aux registres, et l'execution runtime effective sur hote equipe Podman+nvidia-container-toolkit.

### 2026-07-15 — Vague 2 / WS7 increment 41 applique

- **Egress durci par politique explicite** : `codeSandboxNetworkPolicy.ts` remplace la regex large `install|restore` par une allowlist de package managers reconnus ; le reseau Podman reste `none` par defaut.
- **Registres fixes** : npm/PyPI/crates.io/Go proxy/pub.dev/NuGet/Hex/RubyGems/Maven injectent des variables d'environnement de registre/proxy ; npm desactive audit/fund et les lifecycle scripts dans le sandbox.
- **Pseudo-installs bloquees** : une commande inconnue contenant `install` (`curl .../install.sh`, `wget`, script arbitraire) ne gagne plus de reseau par simple libelle.
- **Validation** : tests reseau/isolation/GPU/probes/GC/sandbox cibles 44 verts / 0 echec ; glob Code a **557 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS7 reste ouvert** : cette couche livre une allowlist au niveau commande/env et coupe le host loopback, mais ne prouve pas encore un filtrage domaine paquet par paquet ; restent la limitation disque totale workspace et l'execution runtime effective sur hote equipe Podman.

### 2026-07-15 — Vague 2 / WS7 increment 42 applique

- **Fuite host npm fermee** : l'auto-reparation npm n'execute plus `npm view` directement sur l'hote ; `runNodeInstallWithAutoRepair` exige maintenant un builder de commande registre fourni par `codeSandbox.ts`.
- **Resolution registre sandboxee** : le lookup `npm view <pkg> versions --json` passe par `wrapCommandForPodman`, avec le meme reseau registre et les memes quotas que les autres commandes WS7.
- **Politique reseau completee** : `npm view` est explicitement allowliste comme operation registre npm, sans ouvrir les commandes inconnues.
- **Validation** : tests cibles reseau/modules/isolation 32 verts / 0 echec ; glob Code a **559 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS7 reste ouvert** : restent la limitation disque totale workspace, l'execution runtime effective sur hote equipe Podman et le filtrage domaine paquet par paquet.

### 2026-07-15 — Vague 2 / WS7 increment 43 applique

- **Workspace quota remplace le bind rw direct** : les commandes projet ne montent plus `${sandboxRoot}:/workspace:rw`; elles montent un volume Podman nomme `aurora-code-ws-*:/workspace:rw,z`.
- **Quota disque total obligatoire** : `prepareSandboxWorkspaceVolume` cree le volume avec `--opt o=size=768m`, copie le sandbox hote en lecture seule depuis `/aurora-input`, puis bloque la validation si la creation ou l'initialisation echoue.
- **Probe disk-fill totale ajoutee** : les preuves WS7 incluent maintenant une ecriture de nombreux fichiers de 3 Mo, differente du probe `fsize`, pour verifier que la somme des fichiers est contenue.
- **Nettoyage anti-accumulation** : le volume workspace est supprime en `finally`, y compris apres echec partiel d'initialisation ; l'auto-reparation npm resynchronise le volume apres modification de `package.json`.
- **Validation** : tests WS7 cibles 53 verts / 0 echec ; glob Code a **566 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS7 reste ouvert** : la preuve runtime effective reste dependante d'un hote equipe Podman rootless avec support quota volume ; le filtrage domaine paquet par paquet reste a traiter.

### 2026-07-15 — Vague 3 / WS3 increment 44 applique

- **Contrat fichier-par-fichier du plan** : `codeArchitecturePlanContract.ts` compare les fichiers livres aux fichiers requis du plan architecte JSON et signale les absences avant validation.
- **Retry pilote par le plan** : `runGeneratedOutputRetryLoop` traite maintenant un fichier requis manquant comme une sortie incorrecte, au meme niveau qu'une narration non-code ou une violation d'intention.
- **Premiere marche WS3** : la generation reste encore un appel LLM stream, mais le plan n'est plus seulement un texte de contexte ; il devient un contrat machine qui force la livraison des fichiers requis.
- **Validation** : tests cibles plan/retry 14 verts / 0 echec ; glob Code a **569 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS3 reste ouvert** : l'executeur outil-par-outil `write_file/read_file/apply_patch/run_command`, les evenements stream typés `/api/code/*` et la generation >40 fichiers end-to-end restent a livrer.

### 2026-07-15 — Vague 3 / WS3 increment 45 applique

- **Contrat stream type** : `codeStreamEvents.ts` definit le schema NDJSON `aurora.code.stream/1` avec les evenements requis `phase`, `file.written`, `test.result`, `visual.score`, `correction`, `done`, `error`, plus validation runtime.
- **Store prepare pour `/api/code/*`** : `codeStreamStore` conserve maintenant un journal borne d'evenements typés et traduit les callbacks existants phase/fichiers/validation/correction/fin/erreur sans casser l'UI actuelle ; l'adaptation et le preflight sont extraits pour garder le store sous 600 lignes.
- **Parite progressive** : `visual.score` est formalise mais restera emis par WS9 quand le juge visuel render-in-the-loop sera branche ; le bridge `/api/code/*` reste a ajouter ensuite sur ce contrat.
- **Validation** : tests cibles stream 17 verts / 0 echec ; glob Code a **574 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS3 reste ouvert** : route stream bridge, consommation directe SSE/NDJSON par l'UI et executeur fichier-par-fichier restent a livrer.

### 2026-07-15 — Vague 3 / WS3 increment 46 applique

- **File d'execution architecte** : `codeGenerationQueue.ts` derive une queue ordonnee depuis `generationOrder[]` puis `files[]`, conserve required/optional, imports/exports/notes et signale les chemins d'ordre absents.
- **Prompt Codeur contractualise** : `runGenerationPhase` injecte maintenant un manifeste `FILE-BY-FILE EXECUTION MANIFEST — WS3` en plus du plan JSON, afin de preparer le futur executeur `write_file/read_file/apply_patch/run_command`.
- **Limite explicite** : la generation reste un appel LLM stream unique ; cet increment fournit la file machine stable, pas encore l'execution outil-par-outil.
- **Validation** : tests cibles plan/queue/phases 12 verts / 0 echec ; glob Code a **577 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS3 reste ouvert** : consommer cette queue par un executor reel, emettre `file.written` par fichier et brancher `/api/code/*` restent a livrer.

### 2026-07-15 — Vague 3 / WS3 increment 47 applique

- **Outils VFS WS3** : `codeGenerationTools.ts` formalise `write_file`, `read_file`, `apply_patch` et `run_command` sur un VFS `CodeFile[]`, avec resultats typés.
- **Securite de base** : chemins absolus, `..`, NUL et fichiers secrets (`.env`, `.npmrc`, `.pypirc`) sont bloques avant ecriture ; `run_command` refuse de s'executer sans runner WS7 explicite.
- **Execution sequencee** : `executeCodeGenerationToolSequence` applique les actions dans l'ordre et stoppe au premier echec, premiere brique du futur executor fichier-par-fichier.
- **Validation** : tests cibles outils/queue/phases 10 verts / 0 echec ; glob Code a **582 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `git diff --check` propre.
- **WS3 reste ouvert** : brancher cette brique au LLM planner-executor, au sandbox WS7 pour `run_command`, au stream `file.written` live et au bridge `/api/code/*`.

### 2026-07-15 — Vague 3 / WS3 increment 48 applique

- **Executor de queue WS3** : `codeGenerationExecutor.ts` consomme la queue architecte, demande des actions outil a un producteur injecte, applique `write_file/read_file/apply_patch/run_command` sur le VFS et conserve les resultats par item.
- **Stream fichier-par-fichier** : chaque mutation de fichier genere des evenements typés `file.written`; l'executor emet aussi `phase`, `done` et `error` avec le schema `aurora.code.stream/1`.
- **Controle de completude requis** : un fichier requis sans action ou absent apres execution bloque la queue; un echec optionnel peut etre consigne sans perdre les fichiers deja produits.
- **Validation** : tests cibles executor/outils/queue/stream 15 verts / 0 echec ; glob Code a **585 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS3 reste ouvert** : le producteur d'actions doit maintenant etre branche au LLM fichier-par-fichier, puis expose via `/api/code/*` NDJSON/SSE et consomme directement par l'UI.

### 2026-07-15 — Vague 3 / WS3 increment 49 applique

- **Protocole d'actions LLM** : `codeGenerationActionProtocol.ts` introduit `AURORA_CODE_ACTIONS/1`, parse un JSON strict `actions[]`, retire `<think>`/fences et rejette les sorties hors protocole.
- **Producteur LLM injectable** : `codeGenerationActionProducer.ts` construit un contexte cible par fichier (prompt, plan, fenetre de queue, fichiers pertinents), appelle un client LLM injectable ou `resilientOllamaChat`, puis renvoie des actions typées a l'executor.
- **Contexte non global** : seuls le fichier cible, `package.json`/configs et imports proches sont envoyes, ce qui prepare la generation fichier-par-fichier sans regonfler un blob projet complet.
- **Validation** : tests cibles protocole/producteur/executor/outils 16 verts / 0 echec ; glob Code a **593 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS3 reste ouvert** : brancher cette boucle au chemin `runGenerationPhase`, exposer le stream `/api/code/*`, puis prouver une generation >40 fichiers buildable.

### 2026-07-15 — Vague 3 / WS3 increment 50 applique

- **Chemin applicatif agentique** : `runFullPipeline` appelle maintenant `runAgenticGenerationPhase` avant le mono-appel historique quand un plan JSON fournit une queue exploitable.
- **Emission live vers l'UI existante** : la phase agentique pousse `onFilesUpdate` apres chaque fichier ecrit, ce qui alimente le viewer compact et le journal `file.written` sans toucher au Viewer 3D.
- **Fallback transitoire** : si le producteur LLM sort du protocole ou si l'executor echoue, le pipeline bascule encore sur `runGenerationPhase` mono-appel afin de conserver la parite pendant la migration `/api/code/*`.
- **Validation** : tests cibles phase agentique/producteur/executor/phases 10 verts / 0 echec ; glob Code a **595 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; `codeOrchestrator.ts` reste a 595 lignes.
- **WS3 reste ouvert** : brancher un runner WS7 pour `run_command`, exposer la route `/api/code/*` stream et prouver une generation >40 fichiers buildable.

### 2026-07-15 — Vague 3 / WS3 increment 51 applique

- **Route bridge stream** : ajout de `POST /api/code/generate/stream` dans `bridge_server.py`, sous le namespace autorise `/api/code/*`, avec sortie `application/x-ndjson`.
- **Contrat evenementiel HTTP** : la route emet des evenements `aurora.code.stream/1` (`phase`, `file.written`, `done`, `error`) compatibles avec le schema TS, et parse `AURORA_CODE_VFS/1` ou le vieux separateur fichier en fallback.
- **Transitoire explicite** : le moteur applicatif principal reste l'executor TS agentique ; la route bridge sert de contrat stream HTTP pendant la migration UI/bridge complete, sans toucher aux autres modules ni au Viewer 3D.
- **Validation** : `python3 -m py_compile bridge_server.py` vert ; tests cibles stream/agentique 6 verts / 0 echec ; glob Code a **595 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS3 reste ouvert** : faire consommer cette route par l'UI ou remplacer la route transitoire par le moteur agentique TS expose, puis prouver la generation >40 fichiers buildable.

### 2026-07-15 — Vague 3 / WS3 increment 52 applique

- **Consommation UI/store** : `codeStreamStore` consomme maintenant `POST /api/code/generate/stream` pour les generations neuves online ; corrections, repos et suites de conversation restent sur l'orchestrateur TS local pour preserver la parite.
- **Client NDJSON testable** : ajout de `codeBridgeStreamClient` pour lire les chunks, parser chaque ligne avec `aurora.code.stream/1`, rejeter les lignes non conformes et relayer les evenements types.
- **Adaptateur state** : ajout de `codeStreamRemoteState` / `codeStreamRemoteTurn` pour appliquer `phase`, `file.written`, `test.result`, `visual.score`, `correction`, `done`, `error` au store sans alourdir `CodeView` ni casser le viewer compact.
- **Validation** : tests cibles stream/store 23 verts / 0 echec ; glob Code a **601 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code) ; controle elargi `npm test` tente et bloque sur 1 echec Cowork/bridge 502 hors fichiers modifies ; `codeStreamStore.ts` reste a 591 lignes.
- **WS3 reste ouvert** : brancher le runner WS7 pour `run_command` et produire la preuve reelle d'un projet >40 fichiers coherent/buildable, idealement avec le flux UI actif.

### 2026-07-15 — Vague 3 / WS3 increment 53 applique

- **Runner WS7 pour `run_command`** : ajout de `codeGenerationCommandRunner`, qui ecrit le VFS courant dans un sandbox, exige Podman rootless/cgroups v2, prepare le volume quota WS7 et execute la commande dans le conteneur via `wrapCommandForPodman`.
- **Integration executor** : `CodeGenerationToolRunner` recoit maintenant les fichiers VFS courants ; la phase agentique branche `createCodeGenerationSandboxRunner()` pour ne plus rejeter systematiquement les actions `run_command`.
- **Isolation preservée** : aucune commande LLM n'est executee sur l'hote ; si Podman rootless est absent, le runner retourne un echec explicite au lieu de degrader en execution locale.
- **Validation** : tests cibles runner/tools/executor/phase 13 verts / 0 echec ; glob Code a **604 tests verts / 0 echec** ; `npm run build` vert (avertissements cowork dynamiques existants, hors perimetre Code).
- **WS3 reste ouvert** : produire la preuve reelle >40 fichiers coherent/buildable et, si necessaire, remplacer la route bridge transitoire par l'exposition directe du moteur agentique TS.

---

## SYNTHÈSE EXÉCUTIVE

L'audit établit un **double plafond structurel** :

1. **Fossé production/potentiel** — le vrai cœur agentique (`aurora_code_loop.py` : extraction multi-fichiers, validateurs par type, pilotage Chrome CDP, scoring vision, retry, remote SSH) est **intégralement mort côté application**. L'endpoint réellement appelé (`POST /api/aurora/code/generate`, `bridge_server.py:11595`) est un **one-shot naïf** non streamé, sans validateur ni retry.
2. **Architecture plafonnante** — génération en **un seul appel** (blob texte `--- FICHIER: ---`, `num_predict=16000`), `selectModel` **NO-OP** (un seul modèle du jouet à l'OS), gates **regex/grep** sans exécution réelle, **5+ sous-systèmes entiers en code mort**, et des **fichiers-dieu** (`codeOrchestrator.ts` 4863 l., `codeIntent.ts` 3221 l.).

**Trois déverrouillages transformationnels** brisent ce plafond : **(1)** génération agentique fichier-par-fichier sur FS virtuel (lève la limite de taille) ; **(2)** vérification réelle par exécution + tests + juge visuel headless (remplace les proxys regex gameables) ; **(3)** routage multi-modèles avec vérifieur **indépendant**.

---

## DIAGNOSTIC — Module Code d'AuroraIA

### 1. Architecture de bout en bout : comment un prompt devient un projet

Le Module Code repose sur **deux chemins totalement disjoints**, et c'est le fait structurant le plus important de tout l'audit.

**a) Le chemin réellement exécuté par l'application (dégradé).** L'UI (`CodeView.tsx` pour les skins manga/aurora_v4, `AuroraV1CodeView.tsx` via `codeStreamStore` pour aurora_v1/aurora_v3, `AuroraV3CodeView.tsx` qui monte la vraie `CodeView`) capte le prompt, enrichit via `taskIntelligence` (clarification, hypothèses autonomes, bloc « fichiers fournis ») et appelle `orchestrateCodeGeneration` (`codeOrchestrator.ts:3981`). `runFullPipeline` enchaîne : analyse de continuité follow-up (LLM + fallback heuristique), **classification d'intent 100 % déterministe par regex** (`classifyCodeIntent`, `codeIntent.ts:1999`), preflight local, recherche de best-practices (snippets web + versions npm via l'extension), enrichissement de marque (bridge Wikipedia+Ollama), téléchargement d'images (FLUX/ComfyUI via `codeImageGen`, fallback Unsplash mort), planification d'architecture LLM (plan **markdown libre**, non contractualisé), puis **génération en UN SEUL appel** `resilientOllamaChatStream` (`num_ctx=24576`, `num_predict=16000`) où tous les fichiers sont empilés dans un **blob texte** `--- FICHIER: path ---`. `parseCodeFiles` (`codeOrchestrator.ts:1387`) splitte ce blob par regex en `CodeFile[]`, puis une couche de sanitization applique des réparations TS/`package.json`/`tsconfig` par **regex hardcodées** avec des **versions figées**. La boucle `runValidationAndCorrectionLoop` (`while(true)`, `codeOrchestrator.ts:2680`) exécute le sandbox, `compositeStaticCritic` (7 critics regex sans LLM), des gates déterministes (`checkGamePlayability`/`checkWebPageIntegrity`/`checkInteractive3DFidelity`, tous par grep), un scoring en paliers grossiers, une stratégie de correction **pilotée par le compteur de tentatives**, une recherche web et `mergeExistingWithUpdates` avant de reboucler. Enfin : `intelligentlyElevateFiles` (répare `<img>`/boutons/CSS par DOMParser), injection Tailwind/vite/index.html/README/`lancement.bat`, `evaluateBrandFidelity` et `designReport`. L'UI parse le stream (`extractGeneratedFiles`) et assemble un preview HTML **mono-document** (`buildPreviewHtml`) dans une iframe `srcdoc` — **gelée pendant toute la génération** (`shouldSkipLivePreview = isGenerating`, `CodeView.tsx:2268`).

**b) Le vrai cœur agentique (jamais branché).** `aurora_code_loop.py` implémente ce que le module devrait être : `enrich()` fabrique system/user prompt par type, une génération streaming produit le projet, `extract_files()` parse des balises `<FILE>`, `write_project()` écrit l'arbre, des **validateurs par type** buildent/lancent le projet, `cdp_drive.mjs` pilote Chrome headless pour un **screenshot + rapport runtime réel** (erreurs console, exceptions, requêtes échouées, présence canvas), `qwen3-vl` **note le rendu 0..10**, un score composite décide retry/self-critique, et une variante `aurora_code_remote.py` déploie/valide en SSH. **Rien de cela n'est appelé par l'app** : l'endpoint réel `POST /api/aurora/code/generate` (`_aurora_code`, `bridge_server.py:11595`) est un one-shot naïf, non streamé, prompt système d'une ligne, sans extraction multi-fichiers, sans validateur, sans CDP, sans retry.

### 2. Forces réelles

- **Ossature de pipeline multi-phasée** réellement en place sur le chemin orchestrateur (follow-up, classification, planning, génération, sandbox, critique, correction, brand-gate) avec streaming complet vers l'UI.
- **Classification d'intent déterministe riche** (40 projectTypes, 5 complexités, `assetPlan` palette/marque/objets/langue) exploitable comme prior/validateur.
- **Parsing de flux tolérant** aux 4 formats de header et aux fences dégénérées des modèles locaux.
- **Le cœur agentique CLI** (extraction multi-fichiers, validateurs, CDP + rapport runtime, scoring vision, retry, remote SSH) : de loin le meilleur design du module, prêt à être promu.
- **Résilience Ollama** (timebox, recovery, fallback multi-modèles).
- **Coopération inter-modules amorcée** : le code demande réellement des images au module image (FLUX/ComfyUI) et substitue des placeholders.
- **Critique statique multi-axes structurée** (McCabe/Halstead/OWASP-like/a11y/complétude) et modèle de rapport pondéré.
- **Intégration atelier** : persistance workspace, snapshots session, mode repo (pick/scan/write/install), export ZIP, iframe instrumentée (ready/error/console).

### 3. Limites consolidées, classées par impact décroissant

Voir le **tableau structuré `rankedLimits`** ci-joint (32 limites dédupliquées, chacune avec cluster d'origine, preuve `fichier:ligne` et raison du plafonnement). Synthèse des grappes dominantes :

| Rang | Grappe | Sévérité | Preuve clé | Pourquoi ça plafonne la qualité |
|---|---|---|---|---|
| 1 | Cœur agentique non branché ; chemin réel = one-shot naïf | critique | `bridge_server.py:11595-11617` ; 0 import de `aurora_code_loop` hors dossier | L'app livre un blob non structuré, non testé ; toute la sophistication est morte |
| 2 | Mono-shot, fenêtre unique, sortie tronquée | critique | `codeOrchestrator.ts:2506-2535,2547-2549` ; `codeIntent.ts:1853-1876` ; `aurora_code_loop.py:99-101,439` | Gros projets forcément incomplets/coupés ; ceiling absolu |
| 3 | `selectModel` NO-OP, aucun routage/escalade | critique | `codeOrchestrator.ts:730-737` ; `models.ts:83-85` | Même modèle du jouet à l'OS ; pas de vérifieur indépendant |
| 4 | Gates = heuristiques regex, aucune vérif fonctionnelle/visuelle/tests | critique | `codeOrchestrator.ts:1274-1345,921-1030` ; `codeVisualFidelity.ts:161-338` ; `codeStaticCritics.ts:632-697` | La qualité mesurée est un proxy syntaxique gameable ; un code faux passe à 100 % |
| 5 | 3 modules design phares en code mort | critique | `codeVisualFidelity.ts:1-5` ; `codeDesignResearch.ts:351` ; `codeDesignDirectives.ts:748` | Recherche/notation/anti-patterns jamais exécutés |
| 6 | Blob texte parsé par regex, structure plate, collisions | critique | `codeOrchestrator.ts:1387-1448` ; `codeOutputFiles.ts:99-115,58-87` | Pas d'arborescence, écrasements silencieux, régressions en suite |
| 7 | Classification regex + types manquants (embedded/compiler/OS/distribué/mobile natif) | critique | `codeIntent.ts:2068,6-47,209,194` ; `aurora_code_enrich.py:113-118` | Routage instable ; 40 % des cibles inatteignables |
| 8 | Deux UIs parallèles divergentes ; skin défaut sans vrai orchestrateur | critique | `App.tsx:114-118` ; `AuroraV1CodeView.tsx:9-14,433-510` | La qualité dépend du thème ; double maintenance |
| 9 | Pas d'auto-amélioration à outils ; feedback = re-prompt + régénération | critique | `aurora_code_loop.py:683-705` ; `codeReasoningEngine.ts:143-145` | Aucune réparation ciblée ni acquisition d'outils/libs/modèles |
| 10-16 | Escalade dégradante, régression non détectée, budget incohérent, mono-échantillon, preview gelée/mono-doc, simulation cosmétique, chemins Windows | majeur/critique | `codeAutoCorrection.ts:200-207,411` ; `codeMultiPassCritique.ts:141` ; `CodeView.tsx:2268` ; `aurora_code_loop.py:45`, `cdp_drive.mjs:16-18` | Convergence vers un MVP appauvri ; pas de non-régression ; casse sur Linux |
| 17-32 | Échecs silencieux, validation par accolades, critics sécurité premier-match, scoring optimiste (axes=1.0), design biaisé landing sur mobile/jeu, recherche snippets circulaire, assets sans contrôle, versions figées, interactivité FR mensongère, Unsplash mort, fichiers-dieu, troncature contexte, analyse TS/Python-only, remote non sandboxé/TOFU, directive de plagiat, recettes 3D figées | majeur/mineur | cf. `rankedLimits` | Chaque item retire un signal de qualité fiable ou introduit une régression/faux positif |

### 4. Inventaire des composants obsolètes

Détail exhaustif (30 entrées) dans `obsoleteInventory`. Têtes de liste : `selectModel` (NO-OP), l'endpoint one-shot `_aurora_code`, `codeVisualFidelity.ts` + `codeDesignResearch.ts` + `buildDesignDirectives` (orphelins), `runCritiqueLoop`/`deterministicPatcher`/`classifyFramework` (code mort), `codeOutputElevate.ts` entier + passes couleur/anim neutralisées v82nl, projectTypes jamais assignés (`library_*`, `cli_rust/cpp`), R3F dupliqué, tables de versions figées + rustines TS regex, scrape DuckDuckGo, **`source.unsplash.com` (mort, présent dans 4 modules)**, maquettes factices `DEMO_FILES`/`BEFORE`/`MODELS`, mode « live » dégradé + chrome V3 inaccessible, doublons `isHeavyWebGLProject`/détection langage, Blob URL preview compact, chemins Windows + modèle par défaut non chargeable, `--tunnel` localtunnel bloquant, syntax-check par accolades, méta-slogans internes.

### 5. Carte des interactions inter-modules (actuelles et potentielles)

**Actuelles (câblées).** La **seule coopération inter-modules effective** est Code → Image (FLUX/ComfyUI via `codeImageGen`). Sinon : Code → Bridge Python (`/api/brand/enrich`, `/api/web/search|image`, `/api/code/repo/*`, install-model/detect-editor/open-folder), Code → Extension Aurora-Connect (images de référence, versions npm, doc), Code → Ollama (planning/génération/correction/draft-review/reasoning sur un **modèle unique** ; vision seulement si contextImages), Code → Vision (qwen3-vl partagé pour le scoring CLI et les fichiers image, au prix d'un **swap VRAM** contredisant `models.ts`), Code → Voix (dictée + narration TTS), services externes (Unsplash mort, unpkg, DuckDuckGo, localtunnel, picsum), dispatcher partagé `aurora_module_dispatch`.

**Potentielles (à établir pour l'excellence).** Code → **Module 3D** (vrais GLB pour configurateurs/jeux/moteurs, au lieu de recettes Three.js recopiées) ; Code → **Audio** (sons UI, musique, voix — absent) ; Code → **Image élargi** (icônes/SVG/textures/sprites + direction artistique unifiée seed/palette/référence, remplaçant Unsplash et le base64 inline) ; Code → **Vision juge render-in-the-loop** (l'infra `cdp_drive.mjs` existe côté CLI mais n'est pas reliée au chemin app — c'est le levier n°1 pour tuer les gates regex) ; Code → **RAG/Analyse** (index de projet persistant + patch incrémental contre la troncature) ; **routage multi-modèles réel** (`selectCodeModelForHardware` + `/api/tags`, aujourd'hui décoratif) ; **résolveur de versions multi-registres** (npm/PyPI/crates.io/Maven, aujourd'hui npm seul) ; **sandbox conteneurisé partagé** pour build/test/e2e, remplaçant les validateurs shell non isolés.

### Conclusion sans complaisance

Le Module Code souffre d'un **double plafond structurel** : (1) un **fossé production/potentiel** — le vrai cœur agentique (validateurs, CDP, vision, retry, remote) est intégralement mort côté app, qui n'exécute qu'un one-shot naïf ; (2) une **architecture mono-shot/blob-texte/modèle-unique/gates-regex** qui rend « la même qualité de la calculatrice à l'OS » mathématiquement inatteignable. À cela s'ajoute une **dette de code mort massive** (5+ sous-systèmes entiers orphelins) qui donne une fausse impression de robustesse et alourdit la maintenance. Les trois déverrouillages transformationnels convergent depuis les 12 cartographies : **génération agentique sur FS virtuel avec tool-calling** (lève le plafond de taille et l'absence d'auto-amélioration), **vérification réelle par exécution/tests + juge visuel headless** (remplace les proxys regex), et **routage multi-modèles avec vérifieur indépendant**. Tant que ces trois piliers ne sont pas posés, chaque correctif local restera borné par ces plafonds de fond.

---

## COMPLÉMENT — 2 clusters ré-analysés (sandbox-exec, mission-preflight)

> Les 2 lecteurs correspondants avaient échoué au premier passage (cap de sortie structurée) ; ré-exécutés séparément, ils confirment et **aggravent** le diagnostic. Le diagnostic et la feuille de route ci-dessous restent valides ; ces compléments renforcent surtout WS7 (vérification/sandbox) et WS3/WS13 (décomposition + auto-correction).

### Sandbox-exec (`codeSandbox.ts`, `codeDevServer.ts`)

Découverte de périmètre : `proc_sandbox.py` (générateur 3D Blender) et `runtime_prepare.py` (bootstrap ML torch/diffusers) sont **mal rangés** — aucun rapport avec l'exécution de code. Le vrai sandbox se limite à 2 fichiers TS.

**Limites critiques (preuves `fichier:ligne`) :**
- **Faux sandbox : aucune isolation, RCE par conception** — « isolé » = un simple dossier horodaté ; le code LLM s'exécute sur l'hôte avec les droits complets de l'utilisateur (pas de conteneur/VM/namespace/seccomp). `codeSandbox.ts:1332,1477`.
- **Le code est exécuté, pas seulement compilé** — binaires C/C++ lancés (`./out`), bash/ruby/php/lua/pytest exécutés → chaque génération = exécution d'inconnu. `codeSandbox.ts:828,846,853`.
- **Auto-install privilégiée bloquante** — `sudo apt-get install -y` non interactif, Debian-only, gèle en contexte GUI. `codeSandbox.ts:85`.
- **Aucune limite de ressources** (RAM/CPU/disque/réseau) — seul garde-fou = timeout par commande ; fork-bomb / remplissage disque / exfiltration possibles. `codeSandbox.ts:749`.
- **Aucun test comportemental réel** — la « preuve » qu'une app tourne = `fetch HEAD`, tout statut < 500 (donc un 404) compte comme « prêt ». Zéro Playwright, zéro matrice navigateurs, zéro screenshot, zéro e2e. `codeDevServer.ts:329-345`.

**Limites majeures :** `lancement.bat` (batch Windows) injecté même sur Linux (`:1099,1319`) ; détection **mono-langage** premier-match (tout repo avec `package.json` = « node », fullstack/monorepo impossibles, `:1103`) ; dev-server **singleton global** (un seul serveur, fullstack front+back impossible, `codeDevServer.ts:186-196,81-91`) ; **cibles de la mission non supportées** (ESP32/Arduino, mobile natif, OS, WASM, jeux natifs, distribué — `:1006-1012`) ; validation *compile-only* (Rust `cargo check`, Maven `mvn compile`, .NET build sans test) ; **aucun GC** des dossiers sandbox/`node_modules` (fuite disque monotone) ; auto-install Linux limitée à `apt` (pas dnf/pacman/apk) ; readiness fragile (faux positifs sur stderr) ; kill par PID unique → enfants orphelins.

→ **Confirme WS7 (keystone) : sandbox conteneurisé + quotas + validation comportementale réelle (Playwright) + toolchains cibles.**

### Mission-preflight (`codeMissionControl.ts`, `codePreflight.ts`)

**Limites critiques :**
- **Le juge LLM de draft est neutralisé** — `reviewGeneratedCodeDraft` construit un audit riche (120 s de compute) mais son verdict « regenerate » n'est retenu que si `realCodeFileCount < 2` (cas déjà couvert par les gates déterministes) ; la voie déterministe `buildDraftReviewFallback` **n'ouvre jamais le missionDossier**. Le contrat de mission ne sert donc **jamais** de critère de validation. `codeOrchestrator.ts:4525` ; `codeMissionControl.ts:418-586`.
- **Aucune décomposition des projets massifs** — pipeline mono-passe, objectif tronqué à 220 car., plan à 2800, review limitée à 12 fichiers × 600 car. ; pas de milestones/modules/sous-tâches. Un SaaS/ERP/IDE/OS (des centaines de fichiers) est **structurellement impossible** à piloter ici. `codeMissionControl.ts:265,324,610-614`.
- **Phases rigides, dossier figé, zéro re-planification** — le même dossier est ré-injecté à l'identique en génération, en régénération et en sauvetage ; aucun feedback des échecs ne le met à jour. `codeMissionControl.ts:741-762,687-714`.

**Limites majeures :** **trailing comma** dans le gabarit JSON du preflight → apprend au LLM à produire du JSON invalide (`codePreflight.ts:361`) ; parseur JSON preflight plus faible (n'enlève pas `<think>`, `:388-398`) ; `normalizeDossier` **remplace** les garde-fous déterministes par la sortie LLM au lieu de fusionner (invariants de sécurité optionnels, `:280-303`) ; couverture de probes incomplète (pas ruby/dart/docker/gradle) ; sondage limité à `--version` (pas de version-satisfies/RAM/GPU/disque/réseau/ports) ; `buildDraftReviewFallback` biaisé jeux (règles WASD/minimap/docking câblées, `:533-554`) ; budgets de timeout fixes non calibrés à la complexité ; aucune mémoïsation.

→ **Confirme WS3/WS6 (décomposition + classification) et WS13 (auto-correction pilotée par cause, pas par compteur).**


---

# FEUILLE DE ROUTE DE REFONTE — Module Code d'AuroraIA

## Vision directrice

Le Module Code doit cesser d'etre un **pipeline mono-shot / blob-texte / modele-unique / gates-regex** et devenir un **systeme agentique verifie**. La cible est un orchestrateur multi-modeles qui **planifie puis construit un projet fichier-par-fichier sur un systeme de fichiers virtuel** (levant le plafond de taille), qui ne declare **jamais** un livrable termine sans l'avoir **reellement execute, teste et note visuellement**, qui **detecte ses propres limites** et va chercher/installer/evaluer l'outil ou le modele manquant (en venvs isoles, sans jamais toucher `.venv`), et qui **demande aux autres modules Aurora** (image/3D/audio/vision) leurs ressources plutot que de les recreer.

Le critere de reussite est unique et mesurable : **la qualite ne baisse jamais** quand le projet passe de la calculatrice a l'OS complet, au systeme distribue, aux projets tres volumineux. Le **Viewer 3D existant reste intact** ; le **viewer compact est conserve** et complete par un atelier complet et un labo de simulation multi-appareils reel.

Cette feuille de route couvre explicitement les **8 piliers** de la mission, chaque chantier etant rattache a un pilier, avec justification technique tracable (references `fichier:ligne` issues de l'audit).

---

## 1. Constat de depart (rappel synthetique)

L'audit consolide (12 cartographies) etablit un **double plafond structurel** :

1. **Fosse production/potentiel.** Le vrai coeur agentique (`aurora_code_loop.py` : validateurs par type, pilotage Chrome CDP, scoring vision, retry, remote SSH) est **integralement mort du point de vue de l'app**. L'endpoint reellement appele, `POST /api/aurora/code/generate` (`bridge_server.py:11595`), est un **one-shot naif** non-streame, sans extraction multi-fichiers, sans validateur, sans retry.
2. **Architecture plafonnante.** Generation en **un seul appel** (`num_ctx=24576`, `num_predict=16000`, tous les fichiers dans un blob `--- FICHIER: ---`), `selectModel` **NO-OP** (`codeOrchestrator.ts:730`), gates par **regex/grep** sans execution reelle, **5+ sous-systemes entiers en code mort** (`codeVisualFidelity`, `codeDesignResearch`, `buildDesignDirectives`, `runCritiqueLoop`, `deterministicPatcher`), et des **fichiers-dieu** (`codeOrchestrator.ts` 4863 lignes, `codeIntent.ts` 3221 lignes).

Trois deverrouillages transformationnels convergent depuis toutes les cartographies : **generation agentique sur FS virtuel avec tool-calling**, **verification reelle par execution/tests + juge visuel headless**, et **routage multi-modeles avec verifieur independant**. Tant que ces piliers ne sont pas poses, tout correctif local reste borne.

---

## 2. Contraintes dures respectees par la refonte

- **Ne pas modifier les autres modules** : image/3D/audio/vision/analyse sont consommes **comme services** via le bridge Flask (port 3001) et cloudflared (WS15).
- **Ne jamais casser le Viewer 3D** : integration par panneau isole, tests de non-regression 3D systematiques (WS11/WS12).
- **Ne jamais installer dans `application/.venv`** (casserait FLUX/3D) : toutes les installs lourdes vont dans des **venvs jetables dedies** et des **conteneurs isoles** (WS7/WS14).
- **Environnement reel** : Linux, RTX 5070 Ti **16 Go VRAM** + 30 Go RAM + swap ; LLM via **Ollama local** ; front **Tauri/React/TS**, services **Python**, bridge **Flask 3001**, tunnel **cloudflared**.
- **Licences permissives** privilegiees (Apache-2.0 / MIT) ; les rares composants GPL/AGPL (QEMU, SearXNG) sont utilises **en process externe / service HTTP** (aggregation, non linke).

---

## 3. Les chantiers, par pilier

### Pilier 1 — generation-multi-qualite

**WS3 — Moteur agentique planner-executor sur FS virtuel (XL, transformationnel).** Remplace `runGenerationPhase` mono-appel par une boucle a outils (`write_file`/`read_file`/`apply_patch`/`run_command`) sur le `ProjectTree`. Etage 1 architecture (manifeste structure), etage 2 executeur par fichier avec contexte cible (RAG). Chaque `write` declenche un lint/compile reinjecte. Leve le plafond de 16k tokens de sortie et des ~70 fichiers (`codeIntent.ts:1853-1876`).

**WS4 — Routage multi-modeles reel + best-of-N + plan contractualise (L, fort).** Donne un corps a `selectModel` : modele de raisonnement pour l'architecture, coder specialise pour la generation, **verifieur DIFFERENT** pour le controle, escalade cloud sur plateau. Branche `selectCodeModelForHardware` + `/api/tags`. Plan Architecte en **JSON valide par schema** (contrainte dure pour l'executeur), remplacant le markdown libre non verifiable (`codeSystemPrompts.ts:45-76`).

**WS5 — Memoire projet persistante + RAG + patch incremental (L, fort).** Index durable (arbre + graphe d'imports + symboles + embeddings locaux) ; selection RAG des fichiers pertinents au lieu de la troncature (8 messages / ~13 000 chars, `codeOrchestrator.ts:2344/2384`). Modifications = `apply_patch` cibles contre le graphe, eliminant les regressions/pertes documentees.

**WS6 — Classification semantique + taxonomie elargie + registre de generateurs (XL, transformationnel).** Classifieur LLM structure (JSON schema, fallback deterministe) et enum `projectType` etendu (embedded_esp32/arduino, compiler, os_kernel, distributed_system, mobile natif iOS/Android, engine_3d, ide) — aujourd'hui inexistants (`codeIntent.ts:6-47`). Interface `ProjectGenerator` avec un fichier par famille, dispatch depuis `buildCodeSystemPromptFromIntent`.

### Pilier 2 — graphique-ux

**WS9 — Juge visuel render-in-the-loop + recherche de references visuelles (XL, transformationnel).** `python-service` Playwright headless : screenshots multi-viewport (390/834/1440) + styles calcules -> notation par modele vision (rubrique ancree : hierarchie, rythme, contraste WCAG mesure sur pixels, harmonie, densite, verdict tutoriel vs studio). Remplace `evaluateVisualFidelity` (regex sur la source, `codeVisualFidelity.ts:161-338`, de surcroit orpheline). L'infra CDP existe deja cote CLI (`cdp_drive.mjs`) mais n'est pas reliee au chemin app.

**WS10 — Systeme de design structure + prompt compiler + templates couvrants (XL, transformationnel).** Passe design-spec JSON (palette, echelle typo, tokens, composants, wireframe) verifiee contre le code. Taxonomie elargie (data_dense_enterprise, ide_code_editor, os_shell). Fin des conflits actuels : contrat CSS applique a tort a mobile/Flutter/jeu (`codeSystemPrompts.ts:524-526`), starter unique `apple_product` qui viole son propre contrat, brand-gate hex litteral vs directive oklch (`codeFidelityGate.ts:107-121`), shader Fresnel force. Brand-check colorimetrique **deltaE (Lab)** tolerant.

### Pilier 3 — viewer-simulation

**WS11 — Viewer complet multi-panneaux + rendu applicatif in-browser (XL, transformationnel).** **Conserve** le viewer compact (`BigLivePreviewFrame`) et **ajoute** un atelier dockable : arbo virtualisee, editeur, preview, logs, erreurs, perf, etats internes. Moteur **esbuild-wasm + import-map** dans un worker -> vrais projets React/Vue/Svelte multi-fichiers sans dev-server (l'actuel strip tous les imports, `codeOutputFiles.ts:271`). Bridge runtime iframe (console/erreurs/perf). Fin du gel de la preview (`shouldSkipLivePreview = isGenerating`, `CodeView.tsx:2268`). Unification des deux UIs paralleles divergentes ; **le Viewer 3D reste intouche**.

**WS12 — Labo de simulation multi-appareils / multi-environnements (XL, fort).** Web via Playwright (presets DPR/tactile/UA, throttling reseau/CPU, multi-navigateurs reels). **Microcontroleurs** (ESP32/Arduino/Raspberry) via **Renode** (MIT, mock LCD/GPIO/serial). **Consoles/OS/raspberry complets** via **QEMU** (process externe). Sequences de comportement utilisateur. Aujourd'hui les 3 devices ne changent que la largeur (`CodeView.tsx:2159-2170`) — couverture ~5%.

### Pilier 4 — tests-exhaustifs

**WS7 — Harnais de verification par execution + tests d'acceptation (XL, transformationnel).** **Keystone de la refonte.** Sandbox conteneurise (Podman/Firecracker, jamais `.venv`) executant le vrai toolchain (tsc/eslint/vitest/playwright, pytest/mypy/ruff, cargo/clippy, go test). **Generation systematique de tests d'acceptation** derives du brief (unit + property-based + integration + e2e), **figes hors du perimetre modifiable**. Batterie exhaustive : unitaire/integration/e2e/fonctionnel/UI/rendu/responsive/multi-appareils/multi-resolution/perf/memoire/CPU/GPU/reseau/stabilite/robustesse/securite/regression/coherence. Le score devient la **fraction de criteres verts** (signal continu non gameable), remplacant les gates regex ou une calculatrice fausse passe a 100%. **Aucune generation terminee sans validation ; rejouee apres chaque correction importante.**

**WS8 — Analyse statique AST multi-langage reelle (L, fort).** `tree-sitter` (WASM) + tsc/ruff/clippy. Supprime les bugs `findClosingBrace` (accolades dans strings, `codeStructuralAnalysis.ts:94-107`), `countFunctions` par moyenne (God-functions jamais detectees, `codeStaticCritics.ts:468`), `bracketBalance` (`:47-83`), et etend McCabe/dead-code/Halstead a Rust/Go/Java/C++/Swift/Kotlin/Dart. Securite par **data-flow (taint)** sans dependance a `req.`/`input`, **toutes** les occurrences rapportees.

### Pilier 5 — auto-amelioration

**WS14 — Boucle a outils d'auto-outillage (XL, transformationnel).** Boucle ReAct (`run_shell`/`run_tests`/`search_pkg`/`install_dep`/`add_model`) dans le sandbox WS7. Quand la correction plafonne, le module **cherche/installe/evalue** une lib/outil/modele **dans un venv ISOLE** (jamais `application/.venv`), mesure l'effet **A/B contre la reference**, et **garde si reellement meilleur sinon retire proprement** (zero accumulation). Registre d'outils approuves, quotas, allowlist reseau. Remplace le feedback actuel = re-prompt texte + regeneration complete (`aurora_code_loop.py:683-705`). Inclut le resolveur de versions multi-registres (npm/PyPI/crates.io/Maven), aujourd'hui npm-only.

### Pilier 6 — auto-correction

**WS13 — Correction pilotee par cause + anti-regression + budget adaptatif (L, fort).** Strategie fonction de **(categorie, localite, historique)** et non du compteur de tentatives (`codeAutoCorrection.ts:166-172`). **Suppression des strategies degradantes** (supprimer tests/docs, MVP mono-fichier, `:200-207`). **Harnais anti-regression** : snapshot comportemental (tests passants, exports/endpoints, taille fonctionnelle) avant/apres chaque patch, **rollback automatique** si un patch reduit les capacites — car aujourd'hui le score = ratio d'etapes sandbox, donc supprimer une feature **ameliore** le score (`codeOrchestrator.ts:2572-2583`). Budget **adaptatif** par complexite + arret sur **plateau** -> escalade de modele, remplacant l'incoherence `while(true)` vs cap dur 10. Diagnostics AST/tsc (WS8) et defauts visuels (WS9) reinjectes. Re-test complet WS7 apres chaque correction.

### Pilier 7 — cooperation-inter-modules

**WS15 — Client de services inter-modules (L, fort).** `generateAssetsForArchetype` retournant un `AssetBundle` type route vers le module competent **via le bridge** (aucune modification des modules) : **Image elargi** (icones/SVG/textures/illustrations, direction artistique unifiee seed/palette/reference), **3D reel** (GLB du pipeline `aurora-3d` au lieu de recettes Three.js recopiees), **Audio** (sons UI/musique/voix), **Vision** (juge WS9). Assets ecrits en **fichiers optimises** (avif/webp + srcset) au lieu du base64 inline massif. **Suppression totale de `source.unsplash.com`** (mort, present dans 4 modules). Recherche par **RAG reel** (fetch de pages + embeddings + reranker) remplacant les snippets circulaires. **Retrait de la directive de plagiat** (`aurora_code_enrich.py:83-85`). Ordonnancement VRAM pour eviter le swap coder/vision non maitrise.

### Pilier 8 — architecture-fondations

**WS1 — Demonteler les monolithes et purger le code mort (L, moyen).** Extraction en modules < 400 lignes (`codeFileParsing`, `codeManifestRepair`, `codeQualityGates`, `codeAssetFetch`, `codeSupportFiles`, pipeline mince), chacun couvert de tests unitaires. Suppression physique du code mort inventorie. Source de verite unique par fonction (langage, `isHeavyWebGLProject`, versions).

**WS2 — Modele de projet unifie : VFS + graphe + protocole d'emission structure (L, fort).** `ProjectTree` (dossiers, dedup, inference de structure), graphe d'imports valide, **protocole d'emission a longueur declaree** insensible aux backticks/tirets internes (le parser actuel casse sur fences imbriquees et `---` YAML/SQL, `codeOutputFiles.ts`). Writer disque reel via l'API fs Tauri. Support des fichiers sans extension (Dockerfile/Makefile) et binaires (union texte|base64 pour porter images/glb/wasm).

---

## 4. Veille technologique et choix (justifies + licences)

Le detail complet figure dans le tableau structure `techRecommendations`. Synthese des choix majeurs :

| Domaine | Recommande | Pourquoi (vs alternatives) | Licence |
|---|---|---|---|
| Modele code local | **Qwen3-Coder-30B-A3B** (MoE ~3B actifs) | Meilleur rapport qualite/VRAM sur 16 Go, bien plus rapide qu'un dense 32B qui offloaderait. Codestral (MNPL) et StarCoder2 (OpenRAIL) ecartes pour licences. | Apache-2.0 |
| Verifieur/architecte | **Qwen3-32B** (raisonnement), distinct du coder | Signal **independant** indispensable (le coder qui se juge lui-meme false-flag). DeepSeek-R1-Distill (MIT) en alternative. | Apache-2.0 |
| Juge visuel | **Qwen3-VL** (deja present, via bridge) | Reutilisation sans nouveau telechargement ni swap supplementaire ; rubrique ancree + self-consistency. | Apache-2.0 |
| Capture/e2e/device web | **Playwright** | Couvre en une lib capture headless, e2e, multi-navigateurs reels (Chromium+Firefox+WebKit), DPR/tactile/UA, throttling. Superieur a Puppeteer (Chromium seul). | Apache-2.0 |
| Bundler viewer | **esbuild-wasm + import-map** | Resout vraiment les imports en memoire sans serveur. WebContainers/Nodebox ecartes (licences proprietaires). | MIT |
| AST multi-langage | **web-tree-sitter** + tsc/ruff/clippy | Supprime les bugs regex, etend l'analyse a 10+ langages, WASM self-contained (compatible CSP). | MIT |
| Sandbox execution | **Podman rootless** + **Firecracker** (microVM) | Isolation obligatoire pour code LLM arbitraire + installs ; **jamais `.venv`**. Docker ecarte (daemon root). | Apache-2.0 |
| Emulation embarquee/OS | **Renode** (ESP32/Arduino/Pi) + **QEMU** (consoles/OS, process externe) | Renode = equivalent open-source de Wokwi (SaaS exclu). QEMU GPL acceptable en aggregation (non linke). | Renode MIT / QEMU GPL-2.0 (externe) |
| Embeddings RAG | **nomic-embed-text** (via Ollama) / bge-m3 | Local-first, deja dans Ollama, zero nouvelle infra. | Apache-2.0 / MIT |
| Recherche web reelle | **SearXNG** self-host (service HTTP) | Agregation sans cle API ni cout ; AGPL sans effet car appele en HTTP (non linke). Tavily/Brave/Serper ecartes (SaaS payant). | AGPL-3.0 (externe) |
| Editeur viewer | **CodeMirror 6** + react-window | Virtualise nativement les tres gros fichiers (l'actuel gele au-dela de 50 Ko). Monaco plus lourd. | MIT |

---

## 5. Sequencement recommande

Le detail figure dans le champ `sequencing`. Principe : **WS7 (verification reelle) est le keystone** — il est reference par WS13, WS14, WS9 et WS12, donc il doit etre solide avant les vagues d'excellence et d'autonomie.

- **Vague 0 (immediate, parallele).** Quick wins : purge du code mort, suppression d'Unsplash mort, chemins Windows, retrait du plagiat, telemetrie anti-null. Aucun prerequis, arret immediat des degradations actives.
- **Vague 1 — Fondations.** WS1 puis WS2 : impossible de construire le reste sur un blob-texte monolithique.
- **Vague 2 — Cerveau & verification.** WS4 (routage + plan contractualise + verifieur), WS8 (AST fiable), **WS7** (execution + tests). Pivot de « aucune generation terminee sans validation ».
- **Vague 3 — Montee en puissance generation.** WS3 (agentique fichier-par-fichier), WS5 (memoire/RAG), WS6 (classification+generateurs), WS13 (auto-correction).
- **Vague 4 — Excellence percue & autonomie.** WS9 (juge visuel), WS10 (design-system), WS14 (auto-amelioration a outils).
- **Vague 5 — Atelier & simulation.** WS11 (viewer complet, 3D preserve), WS12 (labo multi-appareils), WS15 (cooperation inter-modules).

**Rien n'est « termine » sans passer par WS7.**

---

## 6. Risques principaux et attenuations

Le detail figure dans `risks`. Les plus structurants :

1. **VRAM 16 Go** : coder + verifieur + juge vision + FLUX/3D ne peuvent co-charger. Attenuation : file d'attente de modeles Ollama (un gros modele a la fois), escalade cloud (cloudflared) pour les taches dures, ordonnancement strict.
2. **Contrainte `.venv`** : l'auto-amelioration et les tests installent des dependances. Attenuation **non-negociable** : venvs jetables + conteneurs isoles, jamais le venv racine.
3. **Viewer 3D** : l'unification UI et le labo GPU pourraient le regresser. Attenuation : integration par panneau isole + tests de non-regression 3D ; le Viewer 3D reste monte tel quel.
4. **Effort cumule** (7 chantiers XL) : chaque vague livre une valeur autonome ; ne pas demarrer WS3/WS9/WS14 avant que WS7 soit solide.
5. **Licences GPL/AGPL** (QEMU/SearXNG) : strictement en process externe / HTTP, jamais de linking.
6. **Cout des tests exhaustifs + best-of-N** : temps de generation allonge — acceptable (« le seul critere est la qualite »), attenue par streaming d'avancement, parallelisation et caches.

---

## 7. Conclusion

La refonte repose sur **trois deverrouillages** qui, ensemble, brisent le double plafond diagnostique : **(1)** la generation agentique sur FS virtuel (WS2/WS3) qui supprime la limite de taille et rend possible « la meme qualite de la calculatrice a l'OS » ; **(2)** la verification reelle par execution, tests exhaustifs et juge visuel headless (WS7/WS8/WS9) qui remplace les proxys regex gameables par un signal continu et honnete ; **(3)** le routage multi-modeles avec verifieur independant (WS4). Autour de ces piliers se greffent l'auto-correction anti-regression (WS13), l'auto-amelioration a outils (WS14), la cooperation inter-modules par services (WS15), l'atelier + simulation multi-appareils (WS11/WS12) et l'assainissement des fondations (WS1). Chaque pilier de la mission est couvert par au moins un chantier, avec des technologies **recentes, permissives et adaptees au materiel reel** (Linux, RTX 5070 Ti 16 Go, Ollama, Tauri/React, bridge Flask). Le Viewer 3D et les autres modules restent intouches ; ils deviennent des **services** que le Module Code orchestre plutot que des roues qu'il reinvente.

---

## ANNEXE — Provenance & reproductibilité

- Workflow d'audit : `audit-module-code` (run `wf_cee2ff19-c98` — simple identifiant de traçabilité, **pas** un chemin de fichier ; les données exploitables sont dans `application/AUDIT_MODULE_CODE_data.json`), 12 lecteurs experts (un par sous-système) + diagnostic + roadmap.
- Cartographies structurées complètes (JSON, avec preuve `fichier:ligne` par limite, 32 rankedLimits + 30 obsoleteInventory + 15 workstreams + 12 techRecommendations + 10 risks) : **`application/AUDIT_MODULE_CODE_data.json`**.
- Clusters ré-analysés : `sandbox-exec`, `mission-preflight` (agents `a32ca9145aa2aefb8`, `a91a6d8a7e6805776`).
- Baseline anti-régression : `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` → 391 pass / 0 fail.
