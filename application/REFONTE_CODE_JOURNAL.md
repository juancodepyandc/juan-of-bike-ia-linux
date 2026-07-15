# Journal de refonte du Module Code

## 2026-07-15 — Vague 0 / quick-wins

### Reprise et diagnostic confirme

- Prompt maitre lu integralement : `application/PROMPT_REFONTE_MODULE_CODE.md` (325 lignes).
- Branche de travail creee : `refonte/module-code`.
- Baseline avant travaux retablie depuis `application/` :
  - `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'`
  - Resultat initial : 391 tests, 391 pass, 0 fail.
- Preuves confirmees localement :
  - `codePreflight.ts` contenait un exemple JSON avec trailing comma et un parseur qui ne retirait pas `<think>`.
  - `codeOutputIntelligent.ts`, `codeOutputElevate.ts`, `CodeProjectPreview.tsx` et `codeOrchestrator.ts` utilisaient des fallbacks `source.unsplash.com` / LoremFlickr.
  - `aurora_code_enrich.py` contenait une directive encourageant a ignorer les risques de plagiat.
  - `codeOrchestrator.ts`, `codeSandbox.ts`, `codeSystemPrompts.ts` et le chemin export Code de `saveSystem.ts` produisaient ou demandaient `lancement.bat` sur un environnement Linux.

### Recherches et choix techniques

- Aucune recherche web externe n'a ete necessaire pour cette vague : les correctifs visaient des degradations actives identifiees dans le code local.
- Choix retenu pour remplacer les fallbacks image morts : un generateur SVG inline deterministe (`codeVisualFallbacks.ts`) produisant des `data:image/svg+xml` encodes pour HTML et CSS.
- Raison technique : conserver un rendu visuel non casse sans dependance reseau morte, sans service tiers, et sans inventer de faux assets distants.
- Choix retenu pour les launchers : `start.sh` Linux/macOS au lieu de `lancement.bat` genere automatiquement. Les `.ps1` restent supportes seulement comme langage explicite a valider, pas comme artefact genere par defaut.

### Modifications realisees

- Ajout de `src/services/codeVisualFallbacks.ts`.
- Remplacement des fallbacks `source.unsplash.com` / LoremFlickr par des SVG inline deterministes dans :
  - `codeOutputIntelligent.ts`
  - `codeOutputElevate.ts`
  - `CodeProjectPreview.tsx`
  - `codeOrchestrator.ts`
- Correction du prompt preflight JSON et durcissement du parseur contre les blocs `<think>` dans `codePreflight.ts`.
- Retrait de la directive de plagiat dans `python-services/aurora_code/aurora_code_enrich.py`.
- Remplacement des launchers batch generes par `start.sh` dans :
  - `codeOrchestrator.ts`
  - `codeSandbox.ts`
  - `codeSystemPrompts.ts`
  - chemin export Code de `saveSystem.ts`
  - texte utilisateur de `CodeView.tsx`
- Tests adaptes et ajoutes :
  - `codeOutputElevate.test.ts`
  - `codeOutputIntelligent.test.ts`
  - `codeGeneratedFilesNormalization.test.ts`
  - `codeVisualFallbacks.test.ts`

### Validation

- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'`
  - Resultat final : 393 tests, 393 pass, 0 fail.
- `npm run build`
  - Resultat : succes Vite build.
- `git diff --check`
  - Resultat : aucun probleme whitespace.
- Recherche de regression active :
  - `rg "source\.unsplash\.com|Unsplash|LoremFlickr|plagi|without holding back for plagiarism|@echo off" ...`
  - Resultat : aucune occurrence restante dans le perimetre verifie.

### Limite de validation hors perimetre

- `npm test` complet lance.
- Resultat : 4230 pass, 1 fail.
- Echec unique : `src/__tests__/coworkExtract.test.ts` (`POST /api/cowork/extract-structured returns items[] for synthetic HTML`) car le bridge retourne 502.
- Decision : pas de modification du module cowork dans cette vague, conformement a la contrainte de ne modifier que le Module Code.

### Etat de satisfaction chantier

Pour la Vague 0, oui : les degradations actives visees sont retirees, le build passe, et la baseline Code augmente de 391 a 393 tests verts. Les plafonds structurels WS1-WS15 restent ouverts.

## 2026-07-15 — Vague 1 / WS1 increment 1 — extraction des blocs statiques

### Reprise et diagnostic confirme

- `codeDesignReference.ts`, `codeDesignDirectives.ts`, `codeSystemPrompts.ts` et `codeOutputIntelligent.ts` depassaient ou approchaient le seuil WS1 par accumulation de blocs statiques, recettes de prompts et code mort.
- Les tests existants importaient les facades publiques (`codeDesignReference.ts`, `codeDesignDirectives.ts`, `codeSystemPrompts.ts`) : l extraction devait donc conserver les exports existants.
- `codeOutputIntelligent.ts` contenait encore du code mort neutralise par commentaire : `SEMANTIC_ANIM_RULES`, `HEX_TO_OKLCH`, `elevateColors`, `brandRecolor` et une branche `cssAnimsInjected` jamais activee.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est une decomposition interne purement structurelle, sans changement de technologie.
- Choix retenu : facades publiques minces + modules de donnees/contracts separes, avec imports explicites et tests inchanges.
- Raison technique : reduire la charge cognitive et preparer les extractions suivantes sans modifier le comportement du pipeline.

### Modifications realisees

- `codeDesignReference.ts` est devenu une facade de composition ; ajout de :
  - `codeDesignReferenceHtml.ts`
  - `codeDesignReferenceThree.ts`
  - `codeDesignReferenceSubjects.ts`
- `codeDesignDirectives.ts` conserve la detection et l API publique ; ajout de `codeDesignDirectiveBlocks.ts` pour les blocs premium/archetypes.
- `codeSystemPrompts.ts` conserve les roles publics ; ajout de :
  - `codeSystemPromptContracts.ts`
  - `codeSystemPromptProductShapes.ts`
- `codeOutputIntelligent.ts` purge physiquement les passes de recoloration/animation qui n etaient plus appelees, tout en gardant les champs de rapport publics pour compatibilite.

### Avant / apres mesurable

- `codeDesignReference.ts` : 1024 lignes -> 116 lignes.
- `codeDesignDirectives.ts` : 786 lignes -> 214 lignes.
- `codeSystemPrompts.ts` : 1066 lignes -> 340 lignes.
- `codeOutputIntelligent.ts` : 636 lignes -> 487 lignes.
- Nouveaux modules ajoutes, tous sous 600 lignes :
  - `codeDesignDirectiveBlocks.ts` : 587 lignes.
  - `codeSystemPromptContracts.ts` : 549 lignes.
  - `codeDesignReferenceHtml.ts` : 418 lignes.
  - `codeDesignReferenceSubjects.ts` : 329 lignes.
  - `codeSystemPromptProductShapes.ts` : 198 lignes.
  - `codeDesignReferenceThree.ts` : 152 lignes.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeDesignReference.test.ts` : 26 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeDesignDirectives.test.ts` : 27 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeOutputIntelligent.test.ts` : 18 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeSystemPrompts.test.ts` : 26 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 393 pass / 0 fail.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les facades publiques restent stables, les tests Code sont verts, et quatre fichiers sortent de la zone monolithique. WS1 n est pas termine : les fichiers encore >600 lignes restent a decouper avant de passer a WS2.

## 2026-07-15 — Vague 1 / WS1 increment 2 — mission control et critiques statiques

### Reprise et diagnostic confirme

- `codeMissionControl.ts` melangeait construction de dossier, types partages, serialisation, review LLM/deterministe et prompts de regeneration.
- `codeStaticCritics.ts` melangeait sept familles de critiques statiques independantes : syntaxe, securite, structure, accessibilite, completude livrable, integrite projet et complexite.
- Les imports publics existants passent par `codeMissionControl.ts` et `codeStaticCritics.ts`; ces fichiers devaient donc rester des facades compatibles.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est un decoupage interne, oriente responsabilites.
- Choix retenu : extraire les familles fonctionnelles en modules separes et conserver les facades publiques avec reexports.
- Raison technique : preparer WS7/WS13 sans monolithe de validation, tout en gardant le comportement existant stable.

### Modifications realisees

- `codeMissionControl.ts` conserve la construction du dossier de mission et reexporte l API existante.
- Ajout de `codeMissionShared.ts` pour les types et helpers deterministes (`CodeMissionDossier`, `CodeDraftReview`, `MissionFileContext`, serialisation, parse JSON defensif).
- Ajout de `codeMissionReview.ts` pour la review de draft, le prompt de regeneration et le prompt de sauvetage.
- `codeStaticCritics.ts` devient facade + composite critic.
- Ajout de modules par famille :
  - `codeStaticSyntax.ts`
  - `codeStaticSecurity.ts`
  - `codeStaticStructure.ts`
  - `codeStaticAccessibility.ts`
  - `codeStaticCompleteness.ts`
  - `codeStaticProjectIntegrity.ts`
  - `codeStaticComplexity.ts`
  - `codeStaticCriticShared.ts`

### Avant / apres mesurable

- `codeMissionControl.ts` : 789 lignes -> 323 lignes.
- `codeStaticCritics.ts` : 1061 lignes -> 49 lignes.
- Nouveaux modules, tous sous 600 lignes :
  - `codeMissionReview.ts` : 374 lignes.
  - `codeMissionShared.ts` : 124 lignes.
  - `codeStaticSecurity.ts` : 309 lignes.
  - `codeStaticProjectIntegrity.ts` : 279 lignes.
  - autres modules `codeStatic*` entre 37 et 111 lignes.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeStaticCritics.test.ts src/__tests__/codeStaticCriticsRealWorld.test.ts` : 58 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 393 pass / 0 fail.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les facades restent compatibles et les familles de validation sont isolables/testables. WS1 reste ouvert : les fichiers >600 restants sont `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`, `codeSandbox.ts` et `codeStreamStore.ts`.

## 2026-07-15 — Vague 1 / WS1 increment 3 — sandbox en facades

### Reprise et diagnostic confirme

- `codeSandbox.ts` cumulait six responsabilites : types publics, detection OS/runtime, normalisation des fichiers, reparation npm, detection langage/commandes et orchestration de validation.
- Le diagnostic sandbox est confirme : le sandbox reste un dossier horodate execute sur l hote, donc WS7 reste ouvert. Cet increment WS1 ne pretend pas livrer l isolation conteneurisee.
- Une violation active a ete confirmee pendant la reprise : l auto-install Linux pouvait appeler `sudo apt-get install -y` depuis une generation.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est un decoupage interne et une suppression de comportement explicitement interdit par le prompt.
- Choix retenu : conserver `codeSandbox.ts` comme facade publique et deplacer les familles dans des modules mono-responsabilite.
- Raison technique : preparer WS7 sans changer les imports consommateurs (`runCodeSandboxValidation`, `CodeSandboxResult`, `CodeSandboxStepResult`) et rendre testables les briques runtime/fichiers/commandes/reparation.

### Modifications realisees

- Ajout de `codeSandboxTypes.ts` pour les types publics (`CodeFile`, resultats, commandes, runtime spec, langage detecte).
- Ajout de `codeSandboxRuntime.ts` pour OS helpers, verification de runtime et preparation de commande.
- Ajout de `codeSandboxFiles.ts` pour nettoyage JSON/manifest, tsconfig sandbox, recherche de fichiers et ecriture disque.
- Ajout de `codeSandboxRegistryRepair.ts` pour la reparation npm par registre avec cache borne.
- Ajout de `codeSandboxCommands.ts` pour detection langage, launchers et commandes par stack.
- `codeSandbox.ts` ne garde plus que l orchestration de `runCodeSandboxValidation`.
- Suppression de l auto-install privilegiee Linux : un runtime systeme absent renvoie maintenant un echec explicite et documente au lieu de lancer `sudo apt-get`.
- Nettoyage du filtre de support dans `codeOrchestrator.ts` : les artefacts `.bat` sont exclus generiquement, sans conserver l ancien nom de launcher Windows.

### Avant / apres mesurable

- `codeSandbox.ts` : 1522 lignes -> 246 lignes.
- Nouveaux modules, tous sous 600 lignes :
  - `codeSandboxCommands.ts` : 506 lignes.
  - `codeSandboxFiles.ts` : 297 lignes.
  - `codeSandboxRegistryRepair.ts` : 300 lignes.
  - `codeSandboxRuntime.ts` : 151 lignes.
  - `codeSandboxTypes.ts` : 48 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`, `codeStreamStore.ts`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxModules.test.ts` : 14 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 407 pass / 0 fail.
- `npm run build` : succes Vite build.
- `git diff --check` : aucun probleme whitespace.
- Recherche de regression active dans le perimetre Code :
  - `rg "sudo\\s*,|apt-get|sudo apt|source\\.unsplash\\.com|LoremFlickr|lancement\\.bat|@echo off|without holding back for plagiarism" ...`
  - Resultat attendu : aucune occurrence dans les fichiers Code cibles.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le sandbox est decoupe en responsabilites stables, la facade publique reste compatible, les nouveaux modules ont des tests unitaires dedies, le glob Code passe a 407 tests verts, et l auto-install Linux privilegiee est retiree. WS1 reste ouvert tant que les cinq fichiers restants depassent 600 lignes.

## 2026-07-15 — Vague 1 / WS1 increment 4 — store de streaming Code

### Reprise et diagnostic confirme

- `codeStreamStore.ts` depassait encore 600 lignes et melangeait types, snapshots de session, narration TTS, progression/ETA, routage modele et actions Zustand.
- Les consommateurs publics (`useCodeStreamStore`, `CodeWorkMode`, `RepoScanInfo`, selecteurs) passent par `codeStreamStore.ts`; la facade devait donc conserver ces exports.
- Le store reste le chemin de la skin Aurora V1/V3 : l increment devait eviter tout changement de comportement de generation, repo mode, narration ou suivi de session.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est une decomposition interne sans changement de technologie.
- Choix retenu : extraire uniquement les blocs purs et laisser les actions Zustand/repo dans la facade.
- Raison technique : reduire le store sous le seuil WS1 sans introduire d abstraction autour de `set/get` qui rendrait les actions asynchrones plus fragiles.

### Modifications realisees

- Ajout de `codeStreamTypes.ts` pour `CodeWorkMode`, `RepoScanInfo`, `CodeStreamState`, `CodeStreamStore` et `CodeSessionSnapshot`.
- Ajout de `codeStreamNarration.ts` pour la persistance du toggle voix et les phrases de narration.
- Ajout de `codeStreamSessions.ts` pour les snapshots multi-session.
- Ajout de `codeStreamProgress.ts` pour ETA, phase derivee et resume de livraison.
- Ajout de `codeStreamRouting.ts` pour l extraction de marque, le routage modele visuel/code et la detection de correction.
- `codeStreamStore.ts` conserve la creation Zustand, les actions repo/generation et les selecteurs publics.

### Avant / apres mesurable

- `codeStreamStore.ts` : 921 lignes -> 560 lignes.
- Nouveaux modules, tous sous 600 lignes :
  - `codeStreamTypes.ts` : 132 lignes.
  - `codeStreamRouting.ts` : 69 lignes.
  - `codeStreamNarration.ts` : 68 lignes.
  - `codeStreamSessions.ts` : 68 lignes.
  - `codeStreamProgress.ts` : 43 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `codeIntent.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeStreamStoreModules.test.ts` : 12 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 419 pass / 0 fail.
- `npm run build` : succes Vite build.
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le store est sous le seuil, les helpers extraits ont des tests dedies, les exports publics restent inchanges et le build passe. WS1 reste ouvert tant que les quatre monolithes restants depassent 600 lignes.

## 2026-07-15 — Vague 1 / WS1 increment 5 — intention Code en modules

### Reprise et diagnostic confirme

- `codeIntent.ts` depassait encore 600 lignes et melangeait types publics, tables de signaux, catalogue de jeux, detection marque/sujet, asset plan, complexite, commandes, classification principale et construction de prompts.
- Les consommateurs importent massivement `classifyCodeIntent`, `CodeIntent`, `CodeProjectType`, `BrandProfile`, `buildCodeSystemPromptFromIntent` et `buildArchitecturePlanningPrompt` depuis `codeIntent.ts`; la compatibilite de facade etait donc obligatoire.
- Le diagnostic WS6 reste confirme : la classification est encore heuristique/deterministe. Cet increment ne la remplace pas par un classifieur LLM structure ; il rend seulement ses sous-systemes isolables pour les vagues suivantes.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est une decomposition interne sans changement de technologie.
- Choix retenu : `codeIntent.ts` devient une facade de reexport, avec imports internes explicites `.ts` pour rester compatible avec le runner natif Node.
- Raison technique : conserver l API publique tout en separant les tables volumineuses (`BRAND_DICTIONARY`, jeux connus) et les prompts longs afin de descendre chaque fichier sous le seuil WS1.

### Modifications realisees

- Ajout de `codeIntentTypes.ts` pour les types publics (`CodeIntent`, `CodeProjectType`, `CodeAssetPlan`, `BrandProfile`, `SubjectDetection`, contexte de follow-up).
- Ajout de modules de classification : `codeIntentSignals.ts`, `codeIntentSignalUtils.ts`, `codeIntentPlatformHeuristics.ts`, `codeIntentComplexity.ts`, `codeIntentCommands.ts`, `codeIntentFileCount.ts`, `codeIntentFollowup.ts`, `codeIntentClassification.ts`.
- Ajout de modules de semantique utilisateur : `codeIntentGameCatalog.ts`, `codeIntentBrandProfiles.ts`, `codeIntentBrandProfilesA.ts`, `codeIntentBrandProfilesB.ts`, `codeIntentSubject.ts`, `codeIntentAssetTokens.ts`, `codeIntentAssets.ts`, `codeIntentLanguage.ts`.
- Ajout de modules de prompt : `codeIntentSystemPrompt.ts`, `codeIntentPromptGame.ts`, `codeIntentPromptProject.ts`, `codeIntentPromptAssets.ts`, `codeIntentArchitecturePrompt.ts`.
- Ajout de `codeIntentModules.test.ts` pour tester directement les modules extraits, pas seulement la facade.

### Avant / apres mesurable

- `codeIntent.ts` : 3221 lignes -> 22 lignes.
- Nouveaux modules, tous sous 600 lignes :
  - `codeIntentClassification.ts` : 432 lignes.
  - `codeIntentBrandProfilesB.ts` : 382 lignes.
  - `codeIntentBrandProfilesA.ts` : 339 lignes.
  - `codeIntentPromptGame.ts` : 285 lignes.
  - `codeIntentGameCatalog.ts` : 260 lignes.
  - `codeIntentPromptAssets.ts` : 229 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`, et `src/__tests__/codeStaticCritics.test.ts`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeIntent.test.ts` : 32 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeIntentModules.test.ts` : 10 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 429 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le monolithe d intention est remplace par une facade compatible, chaque responsabilite majeure a un module testable sous 600 lignes, et le glob Code gagne une couverture dediee. WS1 reste ouvert tant que les quatre fichiers listes ci-dessus depassent 600 lignes.

## 2026-07-15 — Vague 1 / WS1 increment 6 — tests critiques statiques sous seuil

### Reprise et diagnostic confirme

- Apres la modularisation de `codeIntent.ts`, le seul fichier de test Code restant au-dessus du seuil WS1 etait `src/__tests__/codeStaticCritics.test.ts` avec 618 lignes.
- Le fichier contenait deux responsabilites distinctes : les tests unitaires de critics statiques et les tests de convergence critic+patcher.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est un deplacement mecanique de tests.
- Choix retenu : extraire uniquement la suite `boucle reelle critic+patcher — convergence` dans un fichier dedie avec ses fixtures minimales.
- Raison technique : conserver les noms de tests et la couverture existante sans introduire de helper partage inutile pour un split de seuil.

### Modifications realisees

- `codeStaticCritics.test.ts` garde les suites syntaxe, securite, completude, integrite, structure, accessibilite et composite.
- Nouveau `codeStaticCriticsLoop.test.ts` pour la convergence `patchWithLog` / `runCritiqueLoop` / `deterministicPatcher`.

### Avant / apres mesurable

- `codeStaticCritics.test.ts` : 618 lignes -> 470 lignes.
- `codeStaticCriticsLoop.test.ts` : 171 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeStaticCritics.test.ts src/__tests__/codeStaticCriticsLoop.test.ts` : 54 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 429 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la couverture est preservee, les deux fichiers de test sont sous 600 lignes, et le glob Code reste vert. WS1 reste ouvert uniquement sur les trois gros fichiers de production.

## 2026-07-15 — Vague 1 / WS1 increment 7 — parser et sanitation de l'orchestrateur

### Reprise et diagnostic confirme

- `codeOrchestrator.ts` restait le plus gros fichier du module Code et contenait encore des sous-systemes purs sans dependance au pipeline : refus LLM, parsing du format fichier, detection de langage, extraction de notes, sanitation JSON/TSConfig/manifest et reparation de dependances.
- Ces fonctions sont appelees par les phases generation/correction/support files, mais leurs contrats sont deja couverts par les tests `codeOutputFiles`, `codeGeneratedFilesNormalization` et les tests de pipeline.

### Recherches et choix techniques

- Aucune recherche web externe : l increment est une extraction interne.
- Choix retenu : conserver les exports historiques depuis `codeOrchestrator.ts` via reexports, et ajouter des imports internes explicites `.ts` pour le runner Node.
- Raison technique : reduire l'orchestrateur sans changer les consommateurs, tout en donnant une surface testable directe a la sanitation.

### Modifications realisees

- Ajout de `codeLLMRefusal.ts` pour la detection refus/excuses LLM.
- Ajout de `codeGeneratedFileParser.ts` pour `parseCodeFiles`, `serializeCodeFiles`, `extractNotes`, detection de langage et rejet des narrations preflight non-code.
- Ajout de `codeGeneratedFileSanitizer.ts` pour nettoyage fences/JSONC, reparation `package.json`/`tsconfig`, dependances R3F/Vite/Tailwind et helpers de manifest.
- `codeOrchestrator.ts` reimporte/reexporte les fonctions publiques existantes (`parseCodeFiles`, `extractNotes`, `serializeCodeFiles`, `normalizeGeneratedCodeFilesForTest`, `isLLMRefusal`).
- Ajout de `codeGeneratedFileModules.test.ts` pour tester directement les modules extraits.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 4798 lignes -> 4047 lignes.
- Nouveaux modules, tous sous 600 lignes :
  - `codeGeneratedFileSanitizer.ts` : 471 lignes.
  - `codeGeneratedFileParser.ts` : 253 lignes.
  - `codeLLMRefusal.ts` : 66 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGeneratedFileModules.test.ts` : 6 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeGeneratedFilesNormalization.test.ts src/__tests__/codeOutputFiles.test.ts` : 32 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 435 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : un sous-systeme complet et deja critique du pipeline est sorti de l'orchestrateur, les exports publics restent compatibles et les tests directs + glob Code + build passent. WS1 reste ouvert sur l'orchestrateur lui-meme et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 8 — assets sujet de l'orchestrateur

### Reprise et diagnostic confirme

- Apres l'extraction parsing/sanitation, `codeOrchestrator.ts` restait a 4047 lignes.
- Le bloc initial "images sujet / marque / placeholders / merge follow-up" etait une responsabilite autonome, utilisee par la preparation de generation et la correction, mais sans dependance directe aux phases du pipeline.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et mecanique.
- Choix retenu : creer `codeSubjectAssets.ts` avec les helpers runtime (bridge/extension/image fallback) et conserver `CodeFile` en import type-only pour ne pas deplacer le contrat public de l'orchestrateur dans cet increment.
- Raison technique : reduire l'orchestrateur sans modifier les appels existants ni le comportement du pipeline image/marque.

### Modifications realisees

- Ajout de `codeSubjectAssets.ts` pour :
  - construire les requetes d'images sujet ;
  - recuperer les images via extension puis bridge, avec fallback SVG local ;
  - enrichir un profil de marque via bridge ;
  - remplacer `PLACEHOLDER_SUBJECT_IMG(_N)` ;
  - fusionner les fichiers existants et les updates de follow-up.
- `codeOrchestrator.ts` importe maintenant ces helpers au lieu de les porter inline.
- Ajout de `codeSubjectAssets.test.ts` pour tester directement la substitution de placeholders et la fusion follow-up.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 4047 lignes -> 3763 lignes.
- `codeSubjectAssets.ts` : 288 lignes.
- `codeSubjectAssets.test.ts` : 37 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSubjectAssets.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 437 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la responsabilite assets sujet est isolee dans un module sous 600 lignes, la couverture directe existe et le pipeline Code reste vert. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 9 — clarification et follow-up

### Reprise et diagnostic confirme

- Apres l'extraction assets sujet, `codeOrchestrator.ts` restait a 3763 lignes.
- Le bloc clarification/follow-up contenait trois responsabilites autonomes : filtrer les questions vagues, classer la severite des clarifications et analyser la continuite d'une demande courte avec le projet existant.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne.
- Choix retenu : creer `codeFollowUpAnalysis.ts`, conserver les reexports publics depuis `codeOrchestrator.ts`, et charger `ollamaResilience` dynamiquement uniquement dans le chemin LLM.
- Raison technique : garder les imports historiques de `CodeView` compatibles tout en permettant un test Node direct des chemins deterministes sans charger toute l'infra Ollama au chargement du module.

### Modifications realisees

- Ajout de `codeFollowUpAnalysis.ts` pour :
  - `isVagueClarification` ;
  - `classifyClarificationSeverity` ;
  - types `ClarificationSeverity`, `FollowUpKind`, `FollowUpAnalysis` ;
  - `analyzeFollowUpIntent` avec fallback heuristique.
- `codeOrchestrator.ts` reimporte/reexporte les fonctions et types publics, et conserve seulement le wrapper `buildAutonomousAssumption` lie a `codeMissionControl`.
- Ajout de `codeFollowUpAnalysis.test.ts` pour les chemins deterministes (vague/critical/optional/skip/fresh_start sans contexte).

### Avant / apres mesurable

- `codeOrchestrator.ts` : 3763 lignes -> 3464 lignes.
- `codeFollowUpAnalysis.ts` : 308 lignes.
- `codeFollowUpAnalysis.test.ts` : 46 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeFollowUpAnalysis.test.ts` : 3 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeWebIntegrity.test.ts` : 9 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 440 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le chemin clarification/follow-up est module et teste directement, les exports historiques restent compatibles et le glob Code reste vert. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 10 — gates qualite deterministes

### Reprise et diagnostic confirme

- Apres l'extraction clarification/follow-up, `codeOrchestrator.ts` restait a 3464 lignes.
- Le fichier portait encore les gates deterministes de qualite : jouabilite web, integrite page, fidelite 3D interactive, scoring contenu et scoring design.

### Recherches et choix techniques

- Aucune recherche web externe : extraction mecanique interne.
- Choix retenu : creer `codeQualityGates.ts`, reexporter les fonctions publiques depuis `codeOrchestrator.ts`, et importer `computeContentQualityScore` / `computeDesignPolishReport` pour les chemins internes de score et retry.
- Raison technique : isoler les heuristiques testables sans changer les tests historiques qui importent encore depuis l'orchestrateur.

### Modifications realisees

- Ajout de `codeQualityGates.ts` pour :
  - `checkGamePlayability` ;
  - `checkWebPageIntegrity` ;
  - `checkInteractive3DFidelity` ;
  - `computeContentQualityScore` ;
  - `computeDesignPolishReport` / `computeDesignPolishReportPublic` ;
  - `buildDesignRetryHint` et `isVisualProjectType`.
- `codeOrchestrator.ts` importe ces gates et conserve les reexports publics existants.
- Ajout de `codeQualityGates.test.ts` pour couvrir directement jouabilite, rapport design et detection de projets visuels.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 3464 lignes -> 2922 lignes.
- `codeQualityGates.ts` : 568 lignes.
- `codeQualityGates.test.ts` : 35 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeQualityGates.test.ts` : 3 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeWebIntegrity.test.ts src/__tests__/codeGeneratedFilesNormalization.test.ts` : 18 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 443 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les gates qualite deterministes sont isoles et couverts directement, tout en gardant les reexports historiques. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 11 — fichiers de support projet

### Reprise et diagnostic confirme

- Apres l'extraction des gates qualite, `codeOrchestrator.ts` restait a 2922 lignes.
- Le bloc support projet generait README, runbook, `start.sh`, index/vite SPA, injection Tailwind et purge des fichiers synthetiques ; cette responsabilite est autonome par rapport aux phases LLM/correction.

### Recherches et choix techniques

- Aucune recherche web externe : extraction mecanique interne.
- Choix retenu : creer `codeProjectSupportFiles.ts`, importer `upsertProjectSupportFiles` dans l'orchestrateur et reexporter `upsertProjectSupportFilesForTest` pour compatibilite.
- Raison technique : conserver la surface de test existante tout en isolant les transformations de fichiers post-generation.

### Modifications realisees

- Ajout de `codeProjectSupportFiles.ts` pour runbook, README, `start.sh`, Tailwind CDN/tooling, index/vite SPA, purge `.bat`/fallbacks synthetiques.
- `codeOrchestrator.ts` appelle le module au lieu de porter le bloc inline.
- Ajout de `codeProjectSupportFiles.test.ts` pour verifier les supports attendus d'une SPA Vite et la purge des artefacts synthetiques.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 2922 lignes -> 2405 lignes.
- `codeProjectSupportFiles.ts` : 527 lignes.
- `codeProjectSupportFiles.test.ts` : 31 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectSupportFiles.test.ts` : 1 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeGeneratedFilesNormalization.test.ts` : 9 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 444 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la generation des supports projet est isolee dans un module sous 600 lignes, testee directement et compatible avec les tests historiques. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 12 — validation projet

### Reprise et diagnostic confirme

- Apres l'extraction supports projet, `codeOrchestrator.ts` restait a 2405 lignes.
- Le bloc validation/rattrapage local etait autonome : validation des JSON machine, rejet des sorties docs-only ou fallback generique, verification des structures web/desktop/API et reparation locale TypeScript.
- La lecture a revele une reference orpheline : `validateOutputMatchesIntent` appelait encore `isSyntheticFallbackFile` apres son deplacement dans `codeProjectSupportFiles.ts`.

### Recherches et choix techniques

- Aucune recherche web externe : extraction mecanique interne et correction de couplage local.
- Choix retenu : creer `codeProjectValidation.ts`, importer ses fonctions dans l'orchestrateur et faire de `isSyntheticFallbackFile` la source partagee pour les supports projet.
- Raison technique : isoler les gates de recevabilite projet sans changer la boucle de correction, tout en supprimant une duplication de regex.

### Modifications realisees

- Ajout de `codeProjectValidation.ts` pour `validateStructuredFiles`, `validateOutputMatchesIntent`, `attemptLocalFileRepair`, detection d'incompatibilite TypeScript et detection des fichiers fallback synthetiques.
- `codeOrchestrator.ts` appelle ces helpers extraits et ne porte plus les constantes/fonctions de validation projet.
- `codeProjectSupportFiles.ts` importe `isSyntheticFallbackFile` depuis le module de validation.
- Ajout de `codeProjectValidation.test.ts` pour couvrir le rejet des noms generiques, `package.json` invalide, une page statique valide et la reparation TypeScript locale.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 2405 lignes -> 2129 lignes.
- `codeProjectValidation.ts` : 265 lignes.
- `codeProjectValidation.test.ts` : 85 lignes.
- `codeProjectSupportFiles.ts` : 527 lignes -> 521 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectValidation.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeProjectSupportFiles.test.ts src/__tests__/codeGeneratedFilesNormalization.test.ts` : 10 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 448 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la validation projet est isolee, testee directement, la reference fallback orpheline est corrigee et le glob Code gagne 4 tests. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 13 — runtime et diagnostics pipeline

### Reprise et diagnostic confirme

- Apres l'extraction validation projet, `codeOrchestrator.ts` restait a 2129 lignes.
- Les constantes de timebox/contexte, le routage modele actuel, la troncature de texte et les diagnostics generation/environnement etaient des helpers purs, utilises par plusieurs phases.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codePipelineRuntime.ts` pour les constantes/routage/formatage et `codeGenerationDiagnostics.ts` pour les diagnostics de sortie et de sandbox.
- Raison technique : preparer l'extraction des phases LLM sans dupliquer les constantes ni disperser les heuristiques de diagnostic.

### Modifications realisees

- Ajout de `codePipelineRuntime.ts` pour `selectModel`, `getModelShortName`, `clipText` et les constantes de timeouts/contextes.
- Ajout de `codeGenerationDiagnostics.ts` pour `buildEmptyGenerationDiagnostic` et `detectEnvironmentBlocker`.
- `codeOrchestrator.ts` importe ces modules et ne porte plus les helpers locaux.
- Ajout de tests directs pour le routage modele preserve, la troncature, les constantes critiques, les diagnostics vide/refus/narratif et les blocages environnement.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 2129 lignes -> 2034 lignes.
- `codePipelineRuntime.ts` : 41 lignes.
- `codeGenerationDiagnostics.ts` : 70 lignes.
- `codePipelineRuntime.test.ts` : 36 lignes.
- `codeGenerationDiagnostics.test.ts` : 58 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codePipelineRuntime.test.ts src/__tests__/codeGenerationDiagnostics.test.ts` : 8 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 456 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les helpers transverses sont hors orchestrateur, sous seuil, testes directement et preparent la suite de l'extraction. WS1 reste ouvert sur l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 14 — phases pipeline

### Reprise et diagnostic confirme

- Apres l'extraction runtime/diagnostics, `codeOrchestrator.ts` restait a 2034 lignes.
- Les phases intent/preflight/planning/generation formaient un bloc coherent, separe de la correction, des assets sujet et de la finalisation projet.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne.
- Choix retenu : creer `codePipelinePhases.ts`, importer les phases depuis l'orchestrateur et conserver `classifyCodeIntent` localement uniquement pour le fallback fatal.
- Raison technique : isoler les appels LLM/streaming et preparer l'extraction ulterieure de la boucle correction/validation sans changer l'API publique.
- Ajustement technique : rendre les imports Ollama, preflight et mission control paresseux dans les chemins qui les executent, pour que les tests purs du module ne chargent pas des dependances UI non resolues par Node.

### Modifications realisees

- Ajout de `codePipelinePhases.ts` pour :
  - `runIntentPhase` ;
  - `runPreflightPhase` ;
  - `runPlanningPhase` ;
  - `runGenerationPhase` ;
  - `GenerationPivotContext` ;
  - `isArchitecturePlanUsable`.
- `codeOrchestrator.ts` importe ces phases et ne porte plus le bloc generation streaming.
- Ajout de `codePipelinePhases.test.ts` pour verifier un plan exploitable et la phase intent deterministe.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 2034 lignes -> 1596 lignes.
- `codePipelinePhases.ts` : 400 lignes.
- `codePipelinePhases.test.ts` : 39 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codePipelinePhases.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 458 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les phases initiales du pipeline sont isolees dans un module sous 600 lignes, testees sur leurs chemins deterministes et le pipeline global reste vert. WS1 reste ouvert sur la boucle correction/finalisation de l'orchestrateur et les deux vues.
