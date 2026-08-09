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

## 2026-07-15 — Vague 1 / WS1 increment 15 — messages de correction

### Reprise et diagnostic confirme

- Apres l'extraction des phases pipeline, `codeOrchestrator.ts` restait a 1596 lignes.
- Le bloc `buildCorrectionMessages` etait une responsabilite autonome : transformer un resultat sandbox, une strategie, un dossier mission et les contextes recherche/raisonnement en messages auditeur.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne.
- Choix retenu : creer `codeCorrectionMessages.ts` et lui passer `missionDossierText` / `preflightReportText` deja serialises.
- Raison technique : garder le module pur et testable directement par Node, sans charger `missionControl` ni `codePreflight`, qui ont des dependances runtime plus lourdes.

### Modifications realisees

- Ajout de `codeCorrectionMessages.ts` pour construire les messages system/user de correction.
- `codeOrchestrator.ts` serialise le dossier mission et le preflight avant l'appel puis delegue la construction du prompt.
- Ajout de `codeCorrectionMessages.test.ts` pour couvrir les priorites JSON/TypeScript, la presence mission/preflight/fichiers et l'injection recherche/raisonnement.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 1596 lignes -> 1446 lignes.
- `codeCorrectionMessages.ts` : 148 lignes.
- `codeCorrectionMessages.test.ts` : 77 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeCorrectionMessages.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 460 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la construction des prompts auditeur est isolee, sous seuil, testee directement et sans dependances lourdes au chargement. WS1 reste ouvert sur la boucle validation/correction, la finalisation de l'orchestrateur et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 16 — scoring validation

### Reprise et diagnostic confirme

- Apres l'extraction des messages de correction, `codeOrchestrator.ts` restait a 1446 lignes.
- Le calcul de score sandbox et l'injection de la critique statique etaient des helpers deterministes, appeles par la boucle validation/correction mais sans dependance directe au streaming.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codeValidationScoring.ts` pour le score sandbox, le formatage de rapport statique et l'etape `internal:static-critique`.
- Raison technique : isoler le signal de validation avant d'extraire la boucle correction complete, tout en rendant les seuils de blocage testables directement.

### Modifications realisees

- Ajout de `codeValidationScoring.ts` pour `computeSandboxScore`, `isStaticCritiqueBlocking`, `formatStaticCritiqueReport` et `withStaticCritiqueStep`.
- `codeOrchestrator.ts` importe ces helpers et ne porte plus le bloc de scoring/formatage.
- Ajout de `codeValidationScoring.test.ts` couvrant les plafonds de score contenu, le score partiel avec bonus et les critiques statiques bloquantes/non bloquantes.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 1446 lignes -> 1356 lignes.
- `codeValidationScoring.ts` : 95 lignes.
- `codeValidationScoring.test.ts` : 120 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeValidationScoring.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 464 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le scoring de validation est isole, sous seuil, teste directement et l'orchestrateur ne conserve plus ces helpers. WS1 reste ouvert sur l'extraction de la boucle validation/correction et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 17 — boucle validation/correction

### Reprise et diagnostic confirme

- Apres l'extraction du scoring validation, `codeOrchestrator.ts` restait a 1356 lignes.
- La boucle validation/correction etait le dernier grand bloc autonome de l'orchestrateur : sandbox, critique statique, gates deterministes, strategie, recherche, raisonnement, regeneration de secours et merge des corrections.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codeValidationCorrectionLoop.ts` pour porter la boucle complete et exposer des helpers purs testables.
- Raison technique : isoler le cycle de validation/correction avant la finalisation du pipeline, tout en gardant les imports LLM/recherche/mission-control dynamiques pour eviter de charger `useTauri` et les configs runtime au simple import du module.

### Modifications realisees

- Ajout de `codeValidationCorrectionLoop.ts` pour `runValidationAndCorrectionLoop`, `normalizedFilesChanged`, `collectFailingStepOutputs`, `truncateCorrectionErrors` et `compactCorrectionLog`.
- `codeOrchestrator.ts` importe la boucle extraite et ne porte plus les 400+ lignes de validation/correction.
- Ajout de `codeValidationCorrectionLoop.test.ts` pour verifier le changement de fichiers normalises, la collecte/troncature d'erreurs et le compactage des anciennes passes de correction.
- Les appels Ollama, recherche de solution, raisonnement et prompts de secours sont importes dynamiquement dans la boucle.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 1356 lignes -> 939 lignes.
- `codeValidationCorrectionLoop.ts` : 407 lignes.
- `codeValidationCorrectionLoop.test.ts` : 96 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeValidationCorrectionLoop.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 468 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la boucle validation/correction est isolee, sous seuil, testee sur ses helpers purs et le chemin global reste vert. WS1 reste ouvert sur la finalisation de `codeOrchestrator.ts` et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 18 — preparation planning

### Reprise et diagnostic confirme

- Apres l'extraction de la boucle validation/correction, `codeOrchestrator.ts` restait a 939 lignes.
- La preparation du contexte de planning etait un bloc coherent : recherche best-practices, detection de brief simple, enrichissement marque, images sujet et assemblage des blocs de prompt.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codePipelinePreparation.ts` avec des helpers purs pour les heuristiques et blocs de prompt, et une fonction `prepareCodePlanningContext`.
- Raison technique : sortir les appels bridge/recherche de l'orchestrateur sans rendre les tests dependants du bridge ou d'Ollama ; les imports recherche, marque et images restent dynamiques.

### Modifications realisees

- Ajout de `codePipelinePreparation.ts` pour `prepareCodePlanningContext`, `looksLikeSimpleTechBrief`, `buildResearchPhaseLabel`, `buildSubjectImagePromptBlock` et `buildBrandProfileBlock`.
- `codeOrchestrator.ts` delegue la construction du `planningPrompt` enrichi et ne porte plus les blocs recherche/marque/images.
- Ajout de `codePipelinePreparation.test.ts` couvrant l'heuristique brief simple, le libelle de recherche, les markers d'images sujet et le bloc profil marque.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 939 lignes -> 772 lignes.
- `codePipelinePreparation.ts` : 189 lignes.
- `codePipelinePreparation.test.ts` : 87 lignes.
- Fichiers Module Code encore >600 lignes : `codeOrchestrator.ts`, `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codePipelinePreparation.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 472 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la preparation planning est isolee, sous seuil, testee directement et les appels bridge/recherche restent paresseux. WS1 reste ouvert sur la finalisation de `codeOrchestrator.ts` et les deux vues.

## 2026-07-15 — Vague 1 / WS1 increment 19 — retry qualite de sortie

### Reprise et diagnostic confirme

- Apres l'extraction de la preparation planning, `codeOrchestrator.ts` restait a 772 lignes.
- Le retry de qualite de sortie etait le dernier bloc massif cote orchestrateur : parsing initial, merge follow-up, review draft, brand-gate, regeneration, erreurs reseau et fallback meilleur essai.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codeGenerationOutputRetry.ts` pour isoler la boucle de retry post-generation et exposer des helpers purs testables.
- Raison technique : faire passer `codeOrchestrator.ts` sous le seuil WS1 sans modifier le contrat public, tout en gardant `codeMissionControl` charge dynamiquement dans le retry.

### Modifications realisees

- Ajout de `codeGenerationOutputRetry.ts` pour `runGeneratedOutputRetryLoop`, `countRealCodeFiles`, `isNetworkGenerationError`, `rememberBestAttempt`, `applyBestAttemptFallback` et `buildBrandRetryBlock`.
- `codeOrchestrator.ts` delegue le retry post-generation et conserve seulement l'enchainement pipeline, validation et finalisation.
- Ajout de `codeGenerationOutputRetry.test.ts` couvrant le comptage fichiers code, les erreurs reseau, la selection du meilleur essai, le fallback et le bloc retry marque.

### Avant / apres mesurable

- `codeOrchestrator.ts` : 772 lignes -> 560 lignes.
- `codeGenerationOutputRetry.ts` : 311 lignes.
- `codeGenerationOutputRetry.test.ts` : 100 lignes.
- Fichiers Module Code encore >600 lignes : `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationOutputRetry.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 477 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : l'orchestrateur passe sous 600 lignes, le retry de sortie est isole et teste, et le pipeline global reste vert. WS1 reste ouvert sur les deux vues Code.

## 2026-07-15 — Vague 1 / WS1 increment 20 — panneaux CodeView

### Reprise et diagnostic confirme

- Apres le passage de `codeOrchestrator.ts` sous 600 lignes, les deux depassements WS1 restants etaient `CodeView.tsx` (2626 lignes) et `AuroraV1CodeView.tsx` (1780 lignes).
- La fin de `CodeView.tsx` contenait des blocs autonomes : console pipeline, preview live multi-viewport, barre navigateur, critique statique, commentaire Lyra, puce langage et heuristiques associees.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : separer les panneaux TSX (`codeViewPreviewPanel.tsx`, `codeViewInspectorPanels.tsx`) et sortir les heuristiques pures dans des modules `.ts` directement testables (`codeViewLanguage.ts`, `codeViewPreviewHeuristics.ts`).
- Raison technique : reduire `CodeView.tsx` sans importer de JSX dans le runner Node, tout en gardant le viewer compact et la logique de preview existants intacts.

### Modifications realisees

- `CodeView.tsx` importe maintenant `BigLivePreviewFrame`, `CodeConsolePanel`, `CodeCritiquePanel`, `CodeLanguageChip` et `CodeLyraCommentator` depuis des modules dedies.
- Ajout de `codeViewLanguage.ts` pour `detectFileLanguage`, avec support propre des fichiers sans extension connus (`Dockerfile`, `Makefile`) et fallback `plaintext`.
- Ajout de `codeViewPreviewHeuristics.ts` pour `isHeavyWebGLProject`, reutilise par la preview live.
- Ajout de `codeViewExtractedHelpers.test.ts` couvrant detection langage, shebang, signatures source, WebGL/Three.js et seuil de taille preview.

### Avant / apres mesurable

- `CodeView.tsx` : 2626 lignes -> 1945 lignes.
- `codeViewPreviewPanel.tsx` : 289 lignes.
- `codeViewInspectorPanels.tsx` : 349 lignes.
- `codeViewLanguage.ts` : 41 lignes.
- `codeViewPreviewHeuristics.ts` : 12 lignes.
- `codeViewExtractedHelpers.test.ts` : 50 lignes.
- Fichiers Module Code encore >600 lignes : `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeViewExtractedHelpers.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 481 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : les panneaux extraits sont sous seuil, les helpers critiques sont testes sans charger l'UI, et la preview compacte reste conservee. WS1 reste ouvert car `CodeView.tsx` et `AuroraV1CodeView.tsx` doivent encore etre descendus sous 600 lignes.

## 2026-07-15 — Vague 1 / WS1 increment 21 — panneau livraison CodeView

### Reprise et diagnostic confirme

- Apres l'extraction des panneaux console/preview/inspection, `CodeView.tsx` restait a 1945 lignes.
- Le panneau droit "Livraison" etait autonome : actions fichier, arborescence, inspecteurs deja extraits, console deja extraite, viewer code/preview, resultat sandbox et notes.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codeViewDeliveryPanel.tsx` pour le panneau TSX complet et `codeViewSearch.ts` pour le comptage de recherche pur.
- Raison technique : retirer un bloc JSX dense sans changer les props/state owners de `CodeView`, et continuer a couvrir les helpers de vue via le runner Node sans TSX.

### Modifications realisees

- `CodeView.tsx` delegue le panneau droit a `CodeViewDeliveryPanel` avec les memes etats: fichier actif, preview, recherche, console, sandbox, notes et dev-server.
- `codeViewDeliveryPanel.tsx` porte le lazy import de `CodeBlock`, `AnimatePresence`/`motion`, `CodeFileTree` et les composants viewer/inspection deja extraits.
- `codeViewSearch.ts` expose `countFileSearchMatches`, utilise par le panneau et couvert par le test dedie.
- `codeViewExtractedHelpers.test.ts` couvre maintenant aussi l'echappement de la recherche utilisateur et les recherches invalides.

### Avant / apres mesurable

- `CodeView.tsx` : 1945 lignes -> 1642 lignes.
- `codeViewDeliveryPanel.tsx` : 385 lignes.
- `codeViewSearch.ts` : 10 lignes.
- `codeViewExtractedHelpers.test.ts` : 59 lignes.
- Fichiers Module Code encore >600 lignes : `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeViewExtractedHelpers.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 482 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : le panneau livraison est isole, sous seuil et le helper de recherche est teste. WS1 reste ouvert sur la poursuite de `CodeView.tsx` et `AuroraV1CodeView.tsx`.

## 2026-07-15 — Vague 1 / WS1 increment 22 — colonne controle CodeView

### Reprise et diagnostic confirme

- Apres extraction du panneau livraison, `CodeView.tsx` restait a 1642 lignes.
- La colonne gauche de controle etait le dernier gros bloc JSX autonome : mission, guide, contexte, runtime, intent, preflight, correction log, design polish, conversation, export, actions et diagnostics.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : creer `codeViewControlPanel.tsx` pour la colonne et extraire son bas de panneau dans `codeViewControlActions.tsx`.
- Raison technique : eviter de deplacer un monolithe vers un autre fichier ; chaque nouveau module reste sous 600 lignes tout en gardant `CodeView.tsx` proprietaire des etats/callbacks.

### Modifications realisees

- `CodeView.tsx` delegue la colonne gauche a `CodeViewControlPanel`.
- `codeViewControlPanel.tsx` porte mission, brief, runtime, intent, preflight, logs de correction, design polish, conversation, recovery et export persistant.
- `codeViewControlActions.tsx` porte les boutons Generer/Stop, audit design, regeneration design ciblee, statut, erreurs, diagnostics et recommandations connecteurs.
- Le rendu du panneau droit reste delegue a `CodeViewDeliveryPanel`.

### Avant / apres mesurable

- `CodeView.tsx` : 1642 lignes -> 1071 lignes.
- `codeViewControlPanel.tsx` : 552 lignes.
- `codeViewControlActions.tsx` : 193 lignes.
- Fichiers Module Code encore >600 lignes : `CodeView.tsx`, `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeViewExtractedHelpers.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 482 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : la colonne de controle est extraite sans nouveau fichier >600 et le chemin global reste vert. WS1 reste ouvert sur la logique centrale de `CodeView.tsx` et sur `AuroraV1CodeView.tsx`.

## 2026-07-15 — Vague 1 / WS1 increment 23 — generation et shell CodeView

### Reprise et diagnostic confirme

- Apres extraction de la colonne de controle, `CodeView.tsx` restait a 1071 lignes.
- Le plus gros bloc restant etait le callback `generate` : preparation runtime, clarification, contexte multimodal, orchestration, streaming, validation, conversation, dev-server et payload de sauvegarde.
- Les helpers shell restants (libelles de projet, guide, label pipeline, detection vision contexte) etaient purs et donc directement testables.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : deplacer la generation dans `codeViewGeneration.ts`, et isoler le chrome UI + helpers purs dans des modules dedies.
- Raison technique : faire passer le `CodeView.tsx` principal sous le seuil WS1 sans changer le proprietaire des etats, tout en evitant un nouveau fichier >600 lignes.

### Modifications realisees

- Ajout de `codeViewGeneration.ts` pour `runCodeViewGeneration`, appele par le callback `generate` de `CodeView.tsx`.
- Ajout de `codeViewChrome.tsx` pour le decor et le `StudioHero` du module Code.
- Ajout de `codeViewShellHelpers.ts` pour `formatProjectType`, `codeContextNeedsVision`, `isVisionContextFile`, `buildCodePipelineLabel` et `CODE_VIEW_PROMPT_GUIDE`.
- `codeViewExtractedHelpers.test.ts` couvre maintenant les helpers shell en plus des helpers langage, preview WebGL et recherche.

### Avant / apres mesurable

- `CodeView.tsx` : 1071 lignes -> 595 lignes.
- `codeViewGeneration.ts` : 537 lignes.
- `codeViewShellHelpers.ts` : 81 lignes.
- `codeViewChrome.tsx` : 55 lignes.
- `codeViewExtractedHelpers.test.ts` : 98 lignes.
- Fichier Module Code encore >600 lignes : `AuroraV1CodeView.tsx`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeViewExtractedHelpers.test.ts` : 8 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 485 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour cet increment WS1, oui : `CodeView.tsx` est sous seuil, les modules extraits restent sous 600 lignes et les helpers purs sont testes. WS1 reste ouvert sur `AuroraV1CodeView.tsx`.

## 2026-07-15 — Vague 1 / WS1 increment 24 — cloture AuroraV1CodeView

### Reprise et diagnostic confirme

- Apres l'increment 23, le seul fichier Module Code encore au-dessus du seuil WS1 etait `AuroraV1CodeView.tsx` a 1780 lignes.
- Le fichier melangeait helpers purs, preview instrumentee, live view, overlays, sidebar, preview centrale, output/composer et panneau machines.
- Les helpers de detection langage stream et instrumentation HTML etaient purs et pouvaient etre testes sans React.

### Recherches et choix techniques

- Aucune recherche web externe : extraction interne et preservation comportementale.
- Choix retenu : garder `AuroraV1CodeView.tsx` proprietaire des etats/effets, et deplacer les blocs JSX dans des composants de vue dedies.
- Raison technique : cloturer WS1 sans casser le wiring `useCodeViewLogic`, en gardant chaque composant sous 600 lignes et en ajoutant une couverture pure pour les helpers extraits.

### Modifications realisees

- Ajout de `auroraV1CodeHelpers.ts` pour constantes, labels, detection langage stream et instrumentation HTML de preview.
- Ajout de `auroraV1CodePreviewFrame.tsx`, `auroraV1CodeLiveView.tsx`, `auroraV1CodeOverlays.tsx`, `auroraV1CodeSidebar.tsx`, `auroraV1CodePreviewPane.tsx`, `auroraV1CodeOutputPane.tsx`, `auroraV1CodeMachinePanel.tsx` et `auroraV1CodePrimitives.tsx`.
- `AuroraV1CodeView.tsx` devient une composition lisible : etats/effets au-dessus, composants dedies dans le rendu.
- Ajout de `codeAuroraV1Helpers.test.ts` pour `detectStreamLanguage` et `instrumentPreviewHtml`.

### Avant / apres mesurable

- `AuroraV1CodeView.tsx` : 1780 lignes -> 414 lignes.
- `auroraV1CodeOutputPane.tsx` : 438 lignes.
- `auroraV1CodeOverlays.tsx` : 304 lignes.
- `auroraV1CodeSidebar.tsx` : 261 lignes.
- `auroraV1CodeHelpers.ts` : 142 lignes.
- `auroraV1CodePreviewPane.tsx` : 135 lignes.
- `auroraV1CodePreviewFrame.tsx` : 124 lignes.
- `auroraV1CodeLiveView.tsx` : 90 lignes.
- `auroraV1CodeMachinePanel.tsx` : 16 lignes.
- `auroraV1CodePrimitives.tsx` : 15 lignes.
- Scan WS1 : aucun fichier applicatif Module Code `*code*` / vue Code au-dessus de 600 lignes.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeAuroraV1Helpers.test.ts` : 3 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 488 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.

### Etat de satisfaction chantier

Pour WS1, oui : tous les fichiers applicatifs du Module Code identifies sont maintenant sous 600 lignes, les extractions critiques sont testees et le build reste vert. La suite de la refonte peut passer aux chantiers fonctionnels WS2+.

## 2026-07-15 — Vague 1 / WS2 increment 25 — socle ProjectTree/VFS

### Reprise et diagnostic confirme

- Prompt maitre relu jusqu'a la fin : WS2 demande un `ProjectTree`, une arborescence preservee, une deduplication explicite, un graphe d'imports et un protocole d'emission robuste.
- `codeOutputFiles.ts` et `codeGeneratedFileParser.ts` confirment le diagnostic : le chemin actuel extrait des blobs `--- FICHIER: ... ---` vers des listes plates, sans modele d'arbre, sans collision documentee et sans graphe.
- Les fichiers de validation/support/sandbox consomment encore des `CodeFile[]`; l'increment devait donc poser un socle pur sans casser le comportement existant.

### Recherches et choix techniques

- Aucune recherche web externe : la limite traitee est interne au modele de donnees et au parsing existant.
- Choix retenu : module TypeScript pur, browser-compatible, sans `path` Node, pour pouvoir etre reutilise par l'UI, l'orchestrateur et le futur writer Tauri.
- Choix de securite : les chemins absolus, traversals et noms vides sont recuperes sous `recovered/` au lieu d'etre ecrits a leur emplacement declare ; les collisions exactes et insensibles a la casse recoivent un suffixe deterministe `__N`.
- Choix VFS : l'encodage est une union `utf8 | base64`, ce qui prepare les images/GLB/WASM sans forcer leur passage par du texte.

### Modifications realisees

- Ajout de `src/services/codeProjectTree.ts` avec :
  - types `ProjectTree`, `ProjectTreeFile`, `ProjectTreeDirectory`, `ProjectPathCollision`, `ProjectImportGraph` ;
  - normalisation de chemins projet ;
  - construction de dossiers multi-niveaux ;
  - deduplication deterministe des chemins ;
  - graphe d'imports JS/TS/CSS/JSON/Vue/Svelte/Astro pour imports statiques, side-effect, `require` et `import()` ;
  - export `projectTreeToCodeFiles` pour compatibilite transitoire avec les APIs actuelles.
- Ajout de `src/__tests__/codeProjectTree.test.ts` couvrant chemins, arborescence, collisions, fichiers sans extension, imports, binaires base64 et export texte.

### Avant / apres mesurable

- Avant : pas de modele VFS partage ; seulement des listes plates `ParsedFile[]` / `CodeFile[]`.
- Apres : `codeProjectTree.ts` 449 lignes, `codeProjectTree.test.ts` 102 lignes.
- Baseline Code : 488 tests verts apres WS1 -> 493 tests verts apres ce nouvel increment.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectTree.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 493 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS2, oui : le modele de projet unifie existe, reste sous seuil, et couvre les premiers criteres critiques (arborescence, collisions, imports, extensionless, base64). WS2 reste ouvert : le prochain increment doit ajouter le protocole d'emission a longueur declaree et le round-trip parse -> ecrire -> relire.

## 2026-07-15 — Vague 1 / WS2 increment 26 — protocole a longueur declaree

### Reprise et diagnostic confirme

- Le parser historique depend de marqueurs texte et de fences markdown ; le prompt WS2 demande explicitement un protocole insensible aux backticks et aux `---` internes.
- Le `ProjectTree` de l'increment 25 fournit deja la cible memoire ; il manquait le format d'emission stable pour alimenter ce modele sans regex fragile.

### Recherches et choix techniques

- Aucune recherche web externe : le besoin est un contrat local entre le prompt Code, le parser et le futur writer.
- Choix retenu : format `AURORA_CODE_VFS/1` avec une balise de fichier contenant des metadonnees JSON (`path`, `length`, `encoding`, `language`, `mime`) et un contenu lu par longueur declaree.
- Raison technique : le parser ne cherche jamais de fence ou de separateur dans le contenu ; un fichier peut contenir des backticks, `---`, SQL/YAML ou meme `<<<AURORA_END>>>` sans couper le flux.
- Compromis documente : la longueur est mesuree en caracteres JS (`string.length`) pour rester synchrone et browser-compatible ; le support byte-level pourra etre ajoute si un flux binaire non-base64 devient necessaire.

### Modifications realisees

- Ajout de `src/services/codeProjectEmission.ts` avec :
  - `serializeProjectTreeEmission` ;
  - `parseProjectTreeEmission` ;
  - `isStructuredProjectEmission` ;
  - `buildStructuredEmissionInstructions` ;
  - issues structurees (`invalid_metadata`, `invalid_length`, `length_overflow`, `missing_end_marker`, `malformed_header`).
- Ajout de `src/__tests__/codeProjectEmission.test.ts` couvrant round-trip piege, base64, collisions, longueur invalide et instructions de contrat.

### Avant / apres mesurable

- Avant : aucun protocole robuste a longueur declaree ; seulement du parsing par fences/regex.
- Apres : `codeProjectEmission.ts` 207 lignes, `codeProjectEmission.test.ts` 110 lignes.
- Baseline Code : 493 tests verts apres l'increment ProjectTree -> 498 tests verts apres ce protocole.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectEmission.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 498 pass / 0 fail.

### Etat de satisfaction chantier

Pour cet increment WS2, oui : le format a longueur declaree existe et les cas que le prompt nomme explicitement ne cassent plus le parsing. WS2 reste ouvert : il faut maintenant brancher ce protocole dans les prompts/parseurs existants, puis ecrire/relire via le filesystem Tauri.

## 2026-07-15 — Vague 1 / WS2 increment 27 — branchement parseurs et prompts

### Reprise et diagnostic confirme

- Apres l'increment 26, le protocole existait mais le chemin app continuait a demander et parser prioritairement `--- FICHIER`.
- Les deux points d'entree a proteger sont `parseCodeFiles` (orchestrateur) et `extractGeneratedFiles` (viewer compact/Aurora V1). Les deux devaient accepter le nouveau protocole sans casser les historiques.

### Recherches et choix techniques

- Aucune recherche web externe : integration locale du contrat WS2.
- Choix retenu : compatibilite ascendante. `AURORA_CODE_VFS/1` est prioritaire ; le format `--- FICHIER` reste parse pour les conversations anciennes, les contextes existants et les tests de non-regression.
- Raison technique : eviter une rupture brutale du streaming et des retries pendant que le writer Tauri n'est pas encore branche.

### Modifications realisees

- `parseCodeFiles` parse `AURORA_CODE_VFS/1` via `parseProjectTreeEmission` et retourne des `CodeFile[]` transitoires.
- `extractGeneratedFiles` parse le meme protocole et alimente les viewers existants en `ParsedFile[]`.
- `isLLMRefusal` reconnait `AURORA_CODE_VFS/1` comme sortie structuree valide.
- Les prompts Code actifs basculent vers `buildStructuredEmissionInstructions` :
  - `codeSystemPrompts.ts` ;
  - `codeIntentSystemPrompt.ts` ;
  - `codeGenerationOutputRetry.ts` ;
  - `codeMissionReview.ts` ;
  - `codeOrchestrator.ts` rescue ;
  - `codeStarterTemplates.ts` ;
  - `auroraExpertPrompts.ts`.
- Tests mis a jour/ajoutes pour prompts et parseurs structurés.

### Avant / apres mesurable

- Avant : protocole WS2 disponible mais non consomme par les parseurs principaux et non demande par les prompts.
- Apres : les sorties nouvelles sont demandees en `AURORA_CODE_VFS/1`, et les parseurs principaux acceptent ce format.
- Baseline Code : 498 tests verts apres protocole -> 500 tests verts apres branchement.

### Validation

- Tests cibles prompts/parseurs : 90 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 500 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.
- Scan WS1 fichiers Module Code >600 lignes : aucun resultat.

### Etat de satisfaction chantier

Pour cet increment WS2, oui : le protocole n'est plus un module mort, il est demande par les prompts et consomme par les parseurs sans regression. WS2 reste ouvert sur le writer disque Tauri et le round-trip ecrire/relire reel.

## 2026-07-15 — Vague 1 / WS2 increment 28 — writer disque ProjectTree

### Reprise et diagnostic confirme

- WS2 exige un writer disque reel via l'API fs Tauri et un round-trip parse -> ecrire -> relire sur des projets pieges.
- Les wrappers existants dans `useTauri.ts` exposent deja `fsMkdir`, `fsWriteText`, `fsWriteBinary`, `fsReadText` et `fsReadBinary`; il fallait les utiliser comme API locale sans ajouter de nouveau bridge.

### Recherches et choix techniques

- Aucune recherche web externe : integration avec l'API Tauri deja presente dans le depot.
- Choix retenu : writer dedie `codeProjectWriter.ts` avec backend FS injectable. En production, il utilise les wrappers Tauri; en test, un FS memoire prouve le round-trip sans effet de bord disque.
- Choix binaire : les fichiers `encoding="base64"` sont decodes en bytes a l'ecriture et re-encodes a la lecture. Cela evite le faux support binaire qui consisterait a ecrire la base64 comme texte.

### Modifications realisees

- Ajout de `src/services/codeProjectWriter.ts` avec :
  - `writeProjectTreeToDirectory` ;
  - `readProjectTreeFromDirectory` ;
  - `roundTripProjectTreeOnFs` ;
  - helpers base64 bytes et `joinProjectRoot`.
- Ajout de `src/__tests__/codeProjectWriter.test.ts` couvrant :
  - parse -> write -> read sur contenu avec `---`, backticks et `<<<AURORA_END>>>` ;
  - arborescence multi-niveaux ;
  - fichier sans extension `Dockerfile` ;
  - binaire base64/WASM ecrit en bytes puis relu sans perte.

### Avant / apres mesurable

- Avant : `ProjectTree` et protocole parseables, mais aucun writer Tauri dedie ni round-trip fichier.
- Apres : `codeProjectWriter.ts` 176 lignes, `codeProjectWriter.test.ts` 87 lignes.
- Baseline Code : 500 tests verts apres branchement prompts/parseurs -> 503 tests verts apres writer.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectWriter.test.ts` : 3 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 503 pass / 0 fail.
- `npm run build` : succes Vite build (avertissements cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : aucun probleme whitespace.
- Scan WS1 fichiers Module Code >600 lignes : aucun resultat.

### Etat de satisfaction chantier

Pour WS2 fondations, oui : le modele de projet, le graphe d'imports, le protocole a longueur declaree, le parsing compatible, les prompts et le writer Tauri sont en place et testes. Les prochains chantiers devront s'appuyer sur ce socle pour remplacer progressivement les chemins `CodeFile[]` plats dans WS3/WS5.

## 2026-07-15 — Vague 2 / WS4 increment 29 — routage multi-modeles par roles

### Reprise et diagnostic confirme

- `selectModel` etait encore un NO-OP dans `codePipelineRuntime.ts` : il renvoyait toujours le modele configure, sans tenir compte de la phase, de l'intention, de l'escalade ou des modeles installes.
- `CODE_PLANNING_MODEL` et `CODE_REVIEW_MODEL` pointaient encore sur `CODE_SINGLE_MODEL`, donc l'Architecte, le Codeur et l'Auditeur partageaient le meme modele.
- Le store Code recuperait deja `/proxy/ollama/api/tags` et `installedModels`, mais cette information servait surtout a verifier la presence du modele avant generation ; elle n'etait pas propagee comme contexte de routage dans le pipeline.

### Recherches et choix techniques

- Aucune recherche web externe : le chantier touche un contrat local deja documente par le prompt maitre et les constantes Ollama existantes.
- Choix retenu : routeur pur `codeModelRouting.ts`, branche par `selectModel`, qui prend en entree la phase, l'intention, le niveau d'escalade, le profil hardware et la liste `/api/tags`.
- Raison technique : le chemin live ne bascule jamais aveuglement vers un modele absent. Le verifieur/architecte distinct n'est utilise que si `/api/tags` prouve un candidat installe (`qwen3:32b`, variante quantisee, ou modele Qwen3-32B GGUF). Sinon, fallback explicite vers le codeur operationnel pour preserver la generation.
- Compromis documente : cet increment ne cloture pas WS4. Il livre le routage reel et le branchement `/api/tags`; restent le plan Architecte JSON schema-valide, le best-of-N et l'escalade cloud sur plateau.

### Modifications realisees

- Ajout de `src/services/codeModelRouting.ts` :
  - normalisation de noms Ollama (`:latest`, casse) ;
  - selection du Codeur via `selectCodeModelForHardware` ;
  - selection Architecte/Verifieur independante si un modele raisonnement est installe ;
  - decision structuree (`role`, `reason`, `distinctFromCoder`, `installedMatch`).
- `selectModel` expose maintenant `selectModelDecision` et route par phase au lieu de renvoyer le modele configure.
- `codeStreamStore.ts` transmet `installedModels` et `hardware` a l'orchestrateur ; la generation garde le role Codeur meme si l'ancien helper propose un generaliste visuel.
- `codePipelinePhases.ts`, `codeGenerationOutputRetry.ts`, `codeValidationCorrectionLoop.ts` et `codeOrchestrator.ts` propagent le contexte de routage jusque dans planning, generation, retry et correction.
- `models.ts` declare des constantes de role Code (`CODE_REASONING_MODEL`, `CODE_VERIFIER_MODEL`, `CODE_PLANNING_MODEL`, `CODE_REVIEW_MODEL`) sans changer `AUXILIARY_ANALYSIS_MODEL` global hors Module Code.

### Avant / apres mesurable

- Avant : `selectModel('planning'|'correction', ..., 'qwen3-coder:30b')` retournait toujours `qwen3-coder:30b`.
- Apres : avec `/api/tags = ['qwen3-coder:30b', 'qwen3:32b']`, planning et correction retournent `qwen3:32b`, distinct du Codeur ; avec seulement `qwen3-coder:30b`, le fallback reste explicite et teste.
- Baseline Code : 503 tests verts apres WS2 -> 508 tests verts apres ce routage.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeModelRouting.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codePipelineRuntime.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codePipelinePhases.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 508 pass / 0 fail.

### Etat de satisfaction chantier

Pour cet increment WS4, oui : le NO-OP est remplace par un routage multi-roles reel, branche a `/api/tags` et prouve par tests. WS4 reste ouvert : le prochain increment doit remplacer le plan markdown libre par un plan JSON valide par schema, puis ajouter best-of-N et escalade sur plateau.

## 2026-07-15 — Vague 2 / WS4 increment 30 — plan Architecte JSON schema-valide

### Reprise et diagnostic confirme

- Apres l'increment 29, le routage modele etait reel mais le plan Architecte restait du markdown libre (`### COMPREHENSION`, `### STACK`, `### FICHIERS A GENERER`) valide par heuristiques.
- `isArchitecturePlanUsable` acceptait un plan par presence de sections et de chemins entre backticks, donc un plan non machine-readable pouvait encore piloter l'execution.
- `codeProjectSupportFiles.ts` extrayait les dependances par regex `### DEPENDANCES`, preuve que le plan n'etait pas encore un contrat parseable.

### Recherches et choix techniques

- Aucune recherche web externe : le besoin est un schema local et stable entre l'Architecte, l'orchestrateur et l'executeur.
- Choix retenu : `codeArchitecturePlan.ts` contient le schema, le parseur, la normalisation, le rejet des chemins dangereux et la serialisation canonique JSON.
- Raison technique : garder `architecturePlan: string | null` dans les signatures pour ne pas cascader une refonte large, mais stocker une chaine JSON canonique qui peut etre parsee par les consommateurs actuels et futurs.
- Compatibilite : le README garde un fallback regex legacy pour les anciens plans markdown deja presents, mais les nouveaux plans LLM sont rejetes s'ils ne valident pas le schema.

### Modifications realisees

- Ajout de `src/services/codeArchitecturePlan.ts` avec :
  - `CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION` ;
  - `CODE_ARCHITECTURE_PLAN_SCHEMA` ;
  - `parseArchitecturePlanJson` ;
  - `normalizeArchitecturePlan` ;
  - `buildArchitecturePlanJsonInstructions` ;
  - `formatArchitecturePlanDependenciesForMarkdown`.
- Les prompts Architecte (`codeSystemPrompts.ts` et `codeIntentArchitecturePrompt.ts`) demandent maintenant uniquement un objet JSON valide, sans markdown ni texte hors JSON.
- `runPlanningPhase` parse et valide le plan ; si le JSON est absent ou invalide, il est rejete et le Codeur opere sans plan plutot que de suivre un contrat faux.
- `isArchitecturePlanUsable` devient un vrai test schema-valide.
- `codeProjectSupportFiles.ts` lit les dependances et scripts depuis le JSON canonique.

### Avant / apres mesurable

- Avant : `isArchitecturePlanUsable('### Stack\nReact')` pouvait etre etendu par heuristiques markdown ; le contrat restait non verifiable.
- Apres : seul un plan avec `schemaVersion: aurora.code.architecture-plan.v1`, fichiers relatifs, stack, execution, validations et risques requis est accepte.
- Baseline Code : 508 tests verts apres routage modeles -> 512 tests verts apres plan JSON.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeArchitecturePlan.test.ts` : 4 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codePipelinePhases.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeSystemPrompts.test.ts` : 26 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeIntent.test.ts` : 32 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 512 pass / 0 fail.

### Etat de satisfaction chantier

Pour cet increment WS4, oui : le plan Architecte est maintenant un contrat JSON schema-valide et les plans invalides sont rejetes. WS4 reste ouvert sur le best-of-N et l'escalade sur plateau, qui devront s'appuyer sur ce plan contractualise.

## 2026-07-15 — Vague 2 / WS4 increment 31 — best-of-N planning et escalation plateau

### Reprise et diagnostic confirme

- WS4 demandait encore deux criteres non couverts : best-of-N sur taches critiques et demonstration d'escalade sur plateau.
- La boucle de correction calculait deja une stagnation (`isFlatlining`) pour lancer l'analyse de cause racine, mais ce signal n'etait pas transmis au routage modele.
- La phase Architecte etait l'endroit le plus sur pour introduire un best-of-N reel sans polluer le stream de code livre a l'UI.

### Recherches et choix techniques

- Aucune recherche web externe : extension locale du pipeline WS4 deja en place.
- Choix retenu : best-of-2 uniquement pour les projets `complex` et `enterprise`, avec validation schema et scoring deterministe des candidats JSON.
- Raison technique : la planification est la tache critique qui conditionne toute la generation ; scorer plusieurs plans JSON evite d'augmenter le risque de stream UI incoherent sur les fichiers.
- Escalade plateau : si les trois derniers scores stagnent et que `/api/tags` expose un modele cloud/haut de gamme (`CODE_CLOUD_HIGH_MODEL`, `CODE_NEXT_MODEL`, Qwen3-32B), le routeur le prefere pour la correction. Sinon, fallback local inchange.

### Modifications realisees

- Ajout de `src/services/codeArchitecturePlanSelection.ts` :
  - `getArchitecturePlanCandidateCount` ;
  - `scoreArchitecturePlan` ;
  - `selectBestArchitecturePlan`.
- `runPlanningPhase` produit 2 candidats Architecte pour les projets critiques, valide chaque JSON, score les plans valides et transmet le meilleur plan canonique.
- `CodeModelRoutingContext` accepte `plateau`.
- `codeValidationCorrectionLoop.ts` transmet `plateau: true` au routeur quand les scores stagnent.
- `codeModelRouting.ts` ajoute les candidats d'escalade cloud/haut de gamme quand `plateau` est actif.

### Avant / apres mesurable

- Avant : un seul plan Architecte et aucune difference de modele en cas de stagnation, sauf les heuristiques de retry existantes.
- Apres : projet complexe/enterprise -> 2 plans Architecte valides/scorés ; plateau de correction + modele d'escalade installe -> route `plateau-cloud-escalation`.
- Baseline Code : 512 tests verts apres plan JSON -> 515 tests verts apres best-of-N/plateau.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeArchitecturePlanSelection.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeModelRouting.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codePipelinePhases.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 515 pass / 0 fail.

### Etat de satisfaction chantier

Pour WS4, oui cote socle TypeScript : routage multi-modeles reel, verifieur distinct si installe, plan JSON schema-valide, best-of-N planning et escalade plateau sont branches et testes. Les validations de generation reelle sous Ollama resteront a rejouer avec le bridge/front vivants pendant les chantiers WS7/WS3.

## 2026-07-15 — Vague 2 / WS8 increment 32 — scanner lexical, multi-langage et taint

### Reprise et diagnostic confirme

- Le bug `findClosingBrace` etait bien un comptage brut des caracteres `{`/`}` : une accolade dans une string, une regex ou un template pouvait fermer artificiellement une fonction.
- `bracketBalance` utilisait une pile de regex de stripping fragile ; les templates/regex pieges pouvaient encore polluer le signal syntaxique.
- `countFunctions` dans le critic structurel calculait `total lignes / nombre de fonctions`, donc une God-function noyee parmi de petites fonctions n'etait pas mesuree comme telle.
- `securityCritic` ne rapportait que le premier match de chaque regle (`exec` unique) et les regles SSRF/XSS etaient trop dependantes de noms `req`/`input`.

### Recherches et choix techniques

- Aucune recherche web externe : le DoD WS8 de cet increment se traite dans le socle local existant.
- Choix retenu : un scanner lexical TypeScript local (`codeLexicalAnalysis.ts`) qui masque commentaires, strings, templates et regex en conservant les offsets de lignes.
- Raison technique : corriger immediatement les faux positifs critiques et partager le meme masquage entre McCabe et syntax critic, avant l'integration plus lourde `web-tree-sitter` WASM.
- Compromis explicite : cet increment couvre le DoD fonctionnel WS8 mais ne pretend pas remplacer l'integration future `web-tree-sitter` + `tsc`/`ruff`/`clippy`.

### Modifications realisees

- Ajout de `src/services/codeLexicalAnalysis.ts` :
  - `maskCodeLiterals` ;
  - `findMatchingBraceLine` ;
  - `bracketBalanceIgnoringLiterals`.
- `codeStructuralAnalysis.ts` :
  - remplace `findClosingBrace` par le scanner lexical ;
  - etend la detection de fonctions a TS/JS, Python, Rust, Go, Java, C/C++, Swift, Kotlin et Dart ;
  - calcule McCabe sur langages a accolades avec masquage lexical ;
  - etend Halstead generique aux langages a accolades supportes.
- `codeStaticSyntax.ts` reutilise `bracketBalanceIgnoringLiterals`.
- `codeStaticStructure.ts` utilise les bornes reelles de fonctions issues de `analyzeCyclomaticComplexity` pour detecter les fonctions de plus de 200 lignes.
- `codeStaticSecurity.ts` :
  - clone chaque regle en regex globale pour rapporter toutes les occurrences ;
  - ajoute une propagation locale de taint par affectation ;
  - detecte les flux utilisateur vers sinks HTML, reseau, SQL, commande, redirect, header et eval.

### Avant / apres mesurable

- Avant : `function f(){ const x = "}"; } function g(){}` pouvait casser les bornes de fonction ; apres : le test piege strings/regex/templates trouve correctement `trapped` puis `after`.
- Avant : une fonction de 214 lignes pouvait etre diluee par moyenne ; apres : `structureCritic` emet `fonction de plus de 200 lignes`.
- Avant : `eval('a'); eval('b')` ne rapportait qu'une occurrence ; apres : les deux lignes sont rapportees.
- Avant : `const next = new URLSearchParams(location.search)...; fetch(next)` n'etait pas un SSRF si aucun nom `req`/`input` n'apparaissait ; apres : le flux tainted vers `network URL sink` et `DOM HTML sink` est detecte.
- Baseline Code : 515 tests verts apres WS4 -> 522 tests verts apres cet increment WS8.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeStructuralAnalysis.test.ts` : 22 pass / 0 fail.
- `node --experimental-strip-types --test src/__tests__/codeStaticCritics.test.ts` : 49 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 522 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment WS8, le DoD explicite est couvert : cas pieges strings/regex/templates sans faux positif, God-function detectee, analyse fonctionnelle sur plus de 6 langages. WS8 reste ouvert pour l'AST WASM `web-tree-sitter` et les diagnostics toolchain reels (`tsc`, `ruff`, `clippy`) qui devront s'integrer au harnais WS7.

## 2026-07-15 — Vague 2 / WS8 increment 33 — diagnostics toolchain tsc/ruff/clippy

### Reprise et diagnostic confirme

- Apres l'increment 32, le DoD fonctionnel etait couvert mais la cible WS8 mentionnait encore explicitement `tsc`, `ruff` et `clippy`.
- Le sandbox possedait deja des commandes par langage, mais aucun plan de diagnostics statiques toolchain unifie ni teste.
- Le runner respecte deja `optional: true`, ce qui permet d'ajouter des diagnostics utiles sans bloquer une stack quand l'outil n'est pas installe dans le sandbox.

### Recherches et choix techniques

- Aucune recherche web externe : les commandes visees sont stables et deja referencees dans le prompt.
- Choix retenu : `codeToolchainDiagnostics.ts` separe de `codeSandboxCommands.ts`, pour eviter de regonfler ce dernier.
- Les diagnostics Node/Python sont inseres apres les etapes d'installation d'environnement existantes, afin de profiter des dependances deja preparees.
- Compromis explicite : ces commandes sont optionnelles pour enrichir les logs WS8/WS7 ; le build/test principal reste le signal bloquant.

### Modifications realisees

- Ajout de `src/services/codeToolchainDiagnostics.ts` :
  - `buildToolchainDiagnosticCommands` ;
  - `withToolchainDiagnostics`.
- Diagnostics produits :
  - TypeScript : `npx tsc --noEmit --pretty false` ou script `typecheck` si present ;
  - Python : `aurora-python-env/bin/python -m ruff check .` ;
  - Rust : `cargo clippy --all-targets --all-features -- -D warnings`.
- `runCodeSandboxValidation` enveloppe maintenant `buildCommandsForLanguage` avec `withToolchainDiagnostics`.
- Tests sandbox et glob Code etendus.

### Avant / apres mesurable

- Avant : un projet TS pouvait passer par `npm run build` sans diagnostic typecheck dedie si aucun script ne le faisait explicitement.
- Apres : tout projet TS avec fichiers `.ts/.tsx` ou `tsconfig.json` recoit un diagnostic `tsc --noEmit` optionnel apres `npm install`.
- Avant : les projets Python/Rust n'exposaient pas `ruff`/`clippy` dans le plan sandbox.
- Apres : `ruff` et `clippy` apparaissent comme diagnostics optionnels et ordonnes, sans installation systeme automatique Linux.
- Baseline Code : 522 tests verts apres increment 32 -> 525 tests verts apres diagnostics toolchain.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxModules.test.ts` : 17 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 525 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment, la partie `tsc`/`ruff`/`clippy` de WS8 est branchee au sandbox sans casser les validations existantes. WS8 reste ouvert uniquement sur l'integration `web-tree-sitter` WASM, qui demande un adaptateur et des grammaires disponibles sans polluer le repo.

## 2026-07-15 — Vague 2 / WS8 increment 34 — adaptateur AST web-tree-sitter WASM

### Reprise et diagnostic confirme

- Le dernier trou WS8 cote socle etait l'absence d'un vrai parser `tree-sitter` WASM.
- `web-tree-sitter@0.26.11` ne chargeait pas les grammaires de `tree-sitter-wasms@0.1.13` : erreur de metadata dylink, liee a l'ABI/generation des WASM.
- `tree-sitter-wasms@0.1.13` est construit sur l'ecosysteme 0.20.x et couvre les langages WS8, y compris Swift, Kotlin et Dart.

### Recherches et choix techniques

- Sources consultees : documentation officielle `web-tree-sitter`/Tree-sitter et metadata npm locale.
- Choix retenu : aligner `web-tree-sitter` sur `0.20.8`, compatible avec les grammaires precompilees `tree-sitter-wasms`.
- Raison technique : `@vscode/tree-sitter-wasm` est plus coherent cote runtime/grammaires, mais ne couvre pas Swift/Kotlin/Dart ; `tree-sitter-wasms` couvre le perimetre WS8 complet.
- Chargement paresseux : l'adaptateur n'importe et n'initialise le parser que lors d'un appel explicite a `parseCodeWithTreeSitter`.

### Modifications realisees

- Ajout des dependances :
  - `web-tree-sitter@0.20.8` (MIT) ;
  - `tree-sitter-wasms@0.1.13` (Unlicense).
- Ajout de `src/services/codeTreeSitterAst.ts` :
  - mapping langage -> WASM pour TS/TSX/JS/Python/Rust/Go/Java/C/C++/Swift/Kotlin/Dart ;
  - `isTreeSitterLanguageSupported` ;
  - `getTreeSitterGrammarWasmPath` ;
  - `listTreeSitterSupportedLanguages` ;
  - `parseCodeWithTreeSitter`.
- Normalisation des chemins WASM : URLs statiques pour Vite, conversion `file://` -> chemin local pour les tests Node.
- Ajout de `src/__tests__/codeTreeSitterAst.test.ts` avec un parse JavaScript reel via WASM.

### Avant / apres mesurable

- Avant : WS8 avait un scanner lexical robuste et des diagnostics toolchain, mais aucun parser AST WASM executable.
- Apres : `parseCodeWithTreeSitter('function f(x) { return x + 1 }', 'javascript')` retourne un root `program`, sans erreur, avec S-expression contenant `function_declaration`.
- Avant : la compatibilite ABI des grammaires etait inconnue.
- Apres : l'ABI 0.20 est prouvee par test executable.
- Baseline Code : 525 tests verts apres diagnostics toolchain -> 527 tests verts apres adaptateur AST.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeTreeSitterAst.test.ts` : 2 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 527 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `npm audit --json` : 4 vulnerabilites restantes sur `postcss`, `react-router`, `react-router-dom`, `vite`; elles ne viennent pas de `web-tree-sitter` ni `tree-sitter-wasms` et devront etre traitees dans un chantier dependances separe.

### Etat de satisfaction chantier

Pour WS8 cote socle, oui : `web-tree-sitter` WASM est present et executable, les grammaires des langages demandes sont mappees, les toolchains `tsc`/`ruff`/`clippy` sont branchees, les faux positifs de littéraux sont corriges, les God-functions sont detectees, la couverture multi-langage depasse le DoD, et la securite rapporte les occurrences multiples avec taint local. Le remplacement fin des heuristiques par requetes AST specialisees peut maintenant se faire sans changer le contrat public.

## 2026-07-15 — Vague 2 / WS7 increment 35 — criteres d'acceptation figes et score fractionnel

### Reprise et diagnostic confirme

- Le prompt maitre impose que WS7 devienne le signal de qualite central : aucune generation terminee sans validation, score = fraction de criteres verts, et une calculatrice fausse ne doit plus passer a 100 %.
- Le sandbox executait deja des commandes par stack et des diagnostics toolchain, mais n'avait pas encore de pas d'acceptation derive du brief et lisible par le scoring.
- Le scoring pouvait encore recomposer un score a partir du ratio d'etapes sandbox et de la qualite de contenu sans borne explicite par des criteres fonctionnels.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment cible un trou fonctionnel local identifie par WS7.
- Choix retenu : un module `codeAcceptanceCriteria.ts` dedie, appele depuis le sandbox et teste independamment du runner de commandes.
- Le format `acceptance-score=N` est volontairement simple et stable pour que `codeValidationScoring.ts` puisse le consommer sans dependance circulaire.
- Compromis explicite : cet increment livre le score fractionnel et le cas calculatrice fausse, mais ne clot pas WS7 ; l'isolation conteneur, les quotas, le GC et le GPU restent a implementer.

### Modifications realisees

- Ajout de `src/services/codeAcceptanceCriteria.ts` :
  - detection de fichiers code executables ;
  - refus des placeholders evidents ;
  - criteres calculatrice derives du brief : etat, quatre operations, egal/resultat, clear/reset ;
  - generation d'un pas `internal:acceptance-criteria`.
- `runCodeSandboxValidation` :
  - execute le pas d'acceptation apres les commandes sandbox ;
  - execute aussi ce pas quand aucune commande toolchain n'est applicable ;
  - retourne un echec si un critere d'acceptation est rouge.
- `codeValidationScoring.ts` :
  - extrait `acceptance-score=N` ;
  - borne le score final par cette fraction de criteres verts.
- Tests ajoutes :
  - une fausse calculatrice HTML statique avec `demo only` echoue et reste sous 100 % ;
  - une calculatrice quatre operations avec logique TS passe a 100 % ;
  - le scoring utilise bien le score fractionnel d'acceptation quand il est present.

### Avant / apres mesurable

- Avant : une livraison avec boutons de calculatrice sans vraie logique pouvait obtenir un score eleve si les proxys sandbox/contenu etaient verts.
- Apres : le meme livrable echoue sur `calculator-operations` et `no-placeholder-code`, et le sandbox ne le declare pas pret.
- Avant : le score final ne disposait pas d'un canal standard pour exprimer la fraction de criteres fonctionnels verts.
- Apres : `acceptance-score=50` borne le score final a 50, meme si le build passe.
- Baseline Code : 527 tests verts apres WS8 -> 530 tests verts apres cet increment WS7.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeAcceptanceCriteria.test.ts src/__tests__/codeValidationScoring.test.ts src/__tests__/codeSandboxModules.test.ts` : 24 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 530 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment WS7, le premier verrou mesurable est leve : une generation n'est plus declaree verte sans acceptation, le score fractionnel existe, et une fausse calculatrice echoue. WS7 reste volontairement ouvert : il manque encore le sandbox conteneurise Podman/Firecracker, les quotas cgroups/disque, le GC des sandboxes, la preuve d'isolation par lecture hors conteneur impossible et le traitement documente des tests GPU.

## 2026-07-15 — Vague 2 / WS7 increment 36 — environnement Python Aurora sans chemin .venv

### Reprise et diagnostic confirme

- Le prompt maitre interdit explicitement les installs dans `application/.venv` et WS7 precise sandbox conteneurise, jamais `.venv`.
- Le sandbox Python creeait encore un dossier `.venv` dans le dossier de validation, et le diagnostic ruff comme le dev-server Python pointaient vers ce chemin.
- Meme si ce dossier etait local au sandbox, le nom restait un anti-pattern dangereux : il peut etre confondu avec le venv racine et contredit le contrat "jamais `.venv`".

### Recherches et choix techniques

- Aucune recherche web externe : il s'agit d'un durcissement local de chemins et de contrats.
- Choix retenu : un helper partage `codePythonEnvironment.ts` avec un nom explicite `aurora-python-env`.
- Raison technique : eviter trois sources de verite (`codeSandboxCommands`, `codeToolchainDiagnostics`, `codeDevServer`) et rendre le scan des chemins interdit reproductible.
- Compromis explicite : l'environnement reste cree par `python -m venv` dans le sandbox courant ; l'isolation forte Podman/Firecracker reste le prochain verrou WS7.

### Modifications realisees

- Ajout de `src/services/codePythonEnvironment.ts` :
  - `AURORA_PYTHON_ENV_DIR = 'aurora-python-env'` ;
  - `auroraPythonExecutable()` compatible Linux/Windows.
- `codeSandboxCommands.ts` :
  - cree `aurora-python-env` ;
  - utilise ce Python pour requirements, installation editable, pytest et compileall.
- `codeToolchainDiagnostics.ts` :
  - utilise le meme executable pour `ruff check .` ;
  - insere les diagnostics apres la creation d'environnement Python Aurora.
- `codeDevServer.ts` :
  - utilise le meme Python pour FastAPI, Django et Flask.
- `codeSandboxModules.test.ts` :
  - prouve que les commandes Python utilisent `aurora-python-env` ;
  - prouve que le diagnostic ruff pointe vers le meme executable ;
  - verifie l'absence de chemin interdit dans ces commandes.

### Avant / apres mesurable

- Avant : le sandbox produisait `python -m venv .venv`, puis executait `.venv/bin/python`.
- Apres : il produit `python -m venv aurora-python-env`, puis execute `aurora-python-env/bin/python`.
- Avant : ruff et dev-server Python avaient chacun leur chemin Python duplique.
- Apres : sandbox, diagnostics et dev-server consomment `auroraPythonExecutable()`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxModules.test.ts` : 18 pass / 0 fail.
- `rg -n "\\.venv" src/services/code* src/__tests__/code*` : aucune occurrence.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 531 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment WS7, le contrat "pas de chemin `.venv` dans le Module Code" est durci et testable. WS7 reste ouvert pour le vrai conteneur rootless, les quotas, la coupure egress, le GC et les preuves d'isolation host/container.

## 2026-07-15 — Vague 2 / WS7 increment 37 — preflight Podman rootless et wrapper de commandes

### Reprise et diagnostic confirme

- Le prompt maitre identifie le sandbox actuel comme dangereux : execution sur l'hote avec droits complets et validation cosmetique.
- L'hote courant ne fournit ni `podman` ni Firecracker (`command -v podman` et `command -v firecracker` vides), mais expose cgroups v2 (`/sys/fs/cgroup/cgroup.controllers` contient `cpu`, `memory`, `pids`, etc.).
- Continuer a executer du code genere directement sur l'hote violerait WS7 ; le mode degrade correct est donc un echec explicite avant execution, avec installation Podman hors generation.

### Recherches et choix techniques

- Aucune installation systeme : le prompt interdit les installs non interactives pendant une generation, et `sudo` n'est pas suppose disponible.
- Choix retenu : preflight `podman --version` puis `podman info --format '{{.Host.Security.Rootless}} {{.Host.CgroupVersion}}'`.
- Le runner ne fait plus de fallback hote pour les commandes executables : si Podman rootless/cgroups v2 manque, la validation echoue avant `npm`, `python`, `cargo`, etc.
- Compromis explicite : les quotas CPU/memoire/PIDs/fsize/tmpfs sont branches dans le plan Podman ; la quota disque totale d'un workspace bind-mounte n'est pas encore une preuve suffisante contre disk-fill.

### Modifications realisees

- Ajout de `src/services/codeSandboxIsolation.ts` :
  - detection Podman rootless + cgroups v2 ;
  - pas de diagnostic `internal:sandbox-isolation` ;
  - mapping langage -> image OCI ;
  - construction `podman run --rm --pull=never` ;
  - quotas `memory=2g`, `cpus=2`, `pids=256`, `fsize=1048576`, tmpfs 256m ;
  - `--security-opt no-new-privileges`, `--cap-drop ALL`, `--read-only`, `--userns keep-id` ;
  - reseau `none` par defaut, et `slirp4netns:allow_host_loopback=false` pour les commandes d'installation.
- `runCodeSandboxValidation` :
  - construit les commandes toolchain ;
  - si au moins une commande doit etre executee, lance le preflight isolation ;
  - retourne un echec WS7 si l'isolation est indisponible ;
  - encapsule chaque commande executable via Podman quand l'isolation est verte ;
  - garde l'auto-repair npm dans le meme wrapper Podman.
- Ajout de `src/__tests__/codeSandboxIsolation.test.ts`.

### Avant / apres mesurable

- Avant : `npm install`, `python -m pytest`, `cargo check` et autres commandes pouvaient s'executer directement dans `output/code-sandbox/<timestamp>` sur l'hote.
- Apres : ces commandes sont refusees sans Podman rootless ; si Podman est disponible, elles deviennent `podman run ... <image> <commande>`.
- Avant : aucun quota n'etait encode dans le plan d'execution.
- Apres : les arguments Podman testent explicitement CPU, memoire, PIDs, taille de fichier et tmpfs.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxModules.test.ts src/__tests__/codeAcceptanceCriteria.test.ts src/__tests__/codeValidationScoring.test.ts` : 30 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 536 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment WS7, le plus gros risque est reduit : le Module Code ne doit plus executer silencieusement du code LLM sur l'hote quand le harnais conteneurise manque. WS7 reste ouvert sur la preuve runtime complete avec Podman installe, la limitation disque totale, le GC des sandboxes, les tests host-read/fork-bomb/disk-fill et le compromis GPU/nvidia-container-toolkit.

## 2026-07-15 — Vague 2 / WS7 increment 38 — GC des sandboxes de validation

### Reprise et diagnostic confirme

- WS7 demande explicitement le GC des sandboxes.
- Le runner ecrit sous `output/code-sandbox/<timestamp>` mais ne supprimait aucun ancien dossier.
- Les commandes Tauri `fs_list_dir` et `fs_remove_dir_all` existaient deja cote Rust, et le bridge exposait deja `/api/fs/list` et `/api/fs/remove-dir`; le hook front ne les rendait simplement pas accessibles.

### Recherches et choix techniques

- Aucune recherche web externe : le besoin est local et les primitives filesystem existent deja.
- Choix retenu : GC par noms horodates, age maximal 24h et plafond 25 entrees conservees.
- Les noms non horodates sont conserves pour eviter toute suppression inattendue d'un fichier manuel ou d'un marqueur.
- Le GC est non bloquant : une erreur de nettoyage ne doit pas masquer un diagnostic de build/test, mais elle est journalisee dans les steps.

### Modifications realisees

- Ajout de `src/services/codeSandboxGc.ts` :
  - `planSandboxGarbageCollection` ;
  - `collectCodeSandboxGarbage` ;
  - `buildSandboxGcStep`.
- `runCodeSandboxValidation` :
  - nettoie `output/code-sandbox` avant de creer le nouveau dossier ;
  - ajoute un step `internal:sandbox-gc` quand des dossiers sont supprimes ;
  - signale une indisponibilite GC comme avertissement non bloquant.
- `useTauri.ts` :
  - expose `fsListDir` ;
  - expose `fsRemoveDirAll` ;
  - reutilise les commandes/endpoints deja presents, sans commande shell destructive.
- Ajout de `src/__tests__/codeSandboxGc.test.ts`.

### Avant / apres mesurable

- Avant : chaque validation ajoutait un dossier horodate sans strategie de retention.
- Apres : les sandboxes de plus de 24h ou au-dela des 25 plus recents sont planifies pour suppression.
- Avant : supprimer via le front aurait impose un contournement shell ou un import direct Tauri repete.
- Apres : le Module Code utilise des wrappers filesystem structures et testables.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxGc.test.ts src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxModules.test.ts` : 27 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 540 pass / 0 fail.
- `npm run build` : succes ; seuls les avertissements dynamiques cowork preexistants restent affiches.
- `git diff --check` : aucun probleme.

### Etat de satisfaction chantier

Pour cet increment WS7, le GC des sandboxes est livre sans ajouter de commande shell destructive ni toucher les autres modules. WS7 reste ouvert pour les preuves runtime host-read/fork-bomb/disk-fill, la limitation disque totale du workspace, le compromis GPU et l'execution reelle dans Podman lorsque l'hote sera equipe.

## 2026-07-15 — Vague 2 / WS7 increment 39 — probes host-read, PIDs et fsize

### Reprise et diagnostic confirme

- WS7 demande de prouver que le code ne peut pas lire hors conteneur et que les quotas contiennent fork-bomb/disk-fill.
- L'increment 37 a ajoute le preflight et le wrapper Podman, mais ne lancait pas encore de probes avant les commandes du projet.
- L'hote courant n'a toujours pas Podman ; les probes doivent donc etre construites et testees sans pretendre a une preuve runtime locale.

### Recherches et choix techniques

- Aucune recherche web externe : les probes utilisent les primitives Podman et shell deja choisies dans l'increment 37.
- Choix retenu : creer une sentinelle host hors sandbox, la nettoyer en `finally`, puis lancer trois commandes `sh -lc` encapsulees par le meme wrapper Podman que les commandes projet.
- Les probes s'executent apres preflight rootless/cgroups v2 et avant `npm install`, `pytest`, `cargo`, etc.
- Compromis explicite : le probe `fsize` prouve la limite de taille de fichier ; il ne prouve pas encore une limite de disque totale sur tous les petits fichiers du workspace bind-mounte.

### Modifications realisees

- Ajout de `src/services/codeSandboxIsolationProbes.ts` :
  - `buildSandboxIsolationProbeCommands` ;
  - `runSandboxIsolationProbes` ;
  - `sandboxHostSentinelPath`.
- Probes ajoutees :
  - `Preuve isolation host-read` : verifie que des chemins host sensibles et une sentinelle creee hors workspace ne sont pas visibles ;
  - `Preuve quota pids` : tente de creer 400 processus et echoue si le quota ne bloque pas ;
  - `Preuve quota taille fichier` : tente d'ecrire un fichier de 2 Go et echoue si la limite `fsize` ne bloque pas.
- `runCodeSandboxValidation` :
  - execute les probes apres `internal:sandbox-isolation` ;
  - stoppe la validation si une probe echoue ;
  - ne lance les commandes projet qu'apres probes vertes.
- `codeSandboxGc.ts` supprime aussi les sentinelles `AURORA_HOST_SENTINEL_*` abandonnees par une interruption brutale avant le nettoyage `finally`.
- Ajout de `src/__tests__/codeSandboxIsolationProbes.test.ts`.

### Avant / apres mesurable

- Avant : Podman pouvait etre detecte, puis les commandes projet auraient demarre sans preuve d'isolation active.
- Apres : le chemin vert exige d'abord host-read, PIDs et fsize verts.
- Avant : les quotas etaient presents dans les arguments Podman mais non consommes par des probes.
- Apres : les tests verifient que les scripts de probes ciblent les regressions attendues et que la sentinelle host est nettoyee.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxIsolationProbes.test.ts src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxGc.test.ts src/__tests__/codeSandboxModules.test.ts` : 32 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 545 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS7, les preuves d'isolation sont maintenant dans le chemin de validation quand Podman sera disponible. WS7 reste ouvert sur l'execution runtime effective sur une machine equipee, la limitation disque totale, l'egress strictement limite aux registres et le compromis GPU/nvidia-container-toolkit.

## 2026-07-15 — Vague 2 / WS7 increment 40 — GPU NVIDIA via CDI Podman

### Reprise et diagnostic confirme

- WS7 demande explicitement que les tests GPU (WebGL/WebGPU/CUDA) exposent le GPU au conteneur via `nvidia-container-toolkit`, ou documentent un compromis d'isolation.
- L'increment 37 savait isoler les commandes dans Podman, mais ne differenciait pas les projets GPU.
- L'hote courant a un GPU visible (`nvidia-smi -L` -> RTX 5070 Ti), mais `podman` et `nvidia-ctk` sont absents ; aucun run GPU conteneurise local ne peut donc etre prouve aujourd'hui.

### Recherches et choix techniques

- Sources officielles consultees :
  - NVIDIA Container Toolkit CDI : `https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html`.
  - NVIDIA sample workload Podman : `https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html`.
- Choix retenu : utiliser CDI, comme recommande par NVIDIA pour Podman, avec le device `nvidia.com/gpu=all`.
- Choix de securite : ne pas executer de code genere GPU sur l'hote en fallback tant que les quotas hote equivalentes au conteneur ne sont pas prouves. Le harnais bloque donc proprement et documente l'installation requise.

### Modifications realisees

- Ajout de `src/services/codeSandboxGpu.ts` :
  - detection des signaux GPU dans brief et fichiers ;
  - preflight `nvidia-smi -L` ;
  - preflight `nvidia-ctk cdi list` exigeant `nvidia.com/gpu=all` ;
  - construction du step `internal:sandbox-gpu`.
- `codeSandboxIsolation.ts` accepte une option `{ gpu: true }` et ajoute `--security-opt label=disable --device nvidia.com/gpu=all` aux commandes Podman.
- `runCodeSandboxValidation` :
  - execute le preflight GPU seulement si des signaux GPU existent ;
  - bloque les projets GPU si CDI n'est pas disponible ;
  - passe l'option GPU aux commandes projet uniquement apres preflight vert.
- Ajout de `src/__tests__/codeSandboxGpu.test.ts` et extension de `codeSandboxIsolation.test.ts`.

### Avant / apres mesurable

- Avant : un projet WebGPU/CUDA suivait le meme chemin qu'un projet CPU et n'avait aucun contrat explicite d'exposition GPU.
- Apres : un projet GPU exige une preuve CDI avant validation projet.
- Avant : le compromis GPU etait une dette documentaire.
- Apres : le fallback hote non isole est refuse par defaut ; le mode degrade est explicite et testable.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxGpu.test.ts src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxIsolationProbes.test.ts src/__tests__/codeSandboxGc.test.ts src/__tests__/codeSandboxModules.test.ts` : 38 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 551 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS7, les projets GPU ne peuvent plus passer par le harnais comme des projets CPU ordinaires. La vraie preuve runtime reste dependante d'un hote equipe de Podman rootless et du NVIDIA Container Toolkit/CDI ; le disque total et l'egress registry-only restent ouverts.

## 2026-07-15 — Vague 2 / WS7 increment 41 — Egress coupe par defaut et registres allowlistes

### Reprise et diagnostic confirme

- WS7 impose `egress coupe sauf registres`.
- L'increment 37 avait un choix trop large : tout texte de commande contenant `install`, `requirements`, `deps.get`, `pub get` ou `restore` obtenait `slirp4netns:allow_host_loopback=false`.
- Cette regex pouvait donc donner un acces reseau a une pseudo-install inconnue (`curl https://.../install.sh`) alors que WS7 demande un comportement non gameable.

### Recherches et choix techniques

- Pas de nouvelle recherche web necessaire pour cet increment : les sources officielles Podman deja consultees documentaient le mode `slirp4netns:allow_host_loopback=false`, et le besoin restant etait la politique applicative au-dessus de Podman.
- Choix retenu : reseau `none` par defaut, ouverture seulement pour des executables de package managers connus et des sous-commandes attendues.
- Choix de securite : injecter les registres/proxys par variables d'environnement pour rendre l'intention testable et eviter qu'un libelle contenant `install` suffise a ouvrir le reseau.
- Limite volontairement documentee : ce n'est pas encore un pare-feu domaine/IP au niveau paquet ; c'est une allowlist de commandes avec registres imposes, a prouver plus finement quand Podman sera disponible.

### Modifications realisees

- Ajout de `src/services/codeSandboxNetworkPolicy.ts` :
  - `buildSandboxNetworkPolicy` ;
  - `podmanEnvArgs` ;
  - politique `network:none` par defaut.
- Package managers reconnus avec reseau registre :
  - npm/pnpm/yarn `install` ou `ci` vers `https://registry.npmjs.org/`, audit/fund/scripts desactives ;
  - pip/Python `pip install` vers `https://pypi.org/simple` avec prompts desactives ;
  - cargo `check`/`fetch`/`build`/`test` via index crates.io sparse ;
  - go `test`/`build`/`mod download` via `https://proxy.golang.org` et `sum.golang.org` ;
  - dart `pub get`, dotnet `restore`, mix `deps.get`, bundle `install`, mvn/gradle/gradlew.
- `buildPodmanSandboxArgs` consomme maintenant cette politique et ajoute les `--env` correspondants.
- Ajout de `src/__tests__/codeSandboxNetworkPolicy.test.ts` et extension de `codeSandboxIsolation.test.ts`.

### Avant / apres mesurable

- Avant : une regex ouvrait le reseau a toute commande ressemblant a une installation.
- Apres : une commande inconnue contenant `install` reste en `--network none`.
- Avant : l'ouverture reseau n'exprimait pas le registre attendu.
- Apres : la commande Podman porte explicitement les registres/proxys attendus et garde `allow_host_loopback=false`.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxNetworkPolicy.test.ts src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxGpu.test.ts src/__tests__/codeSandboxIsolationProbes.test.ts src/__tests__/codeSandboxGc.test.ts src/__tests__/codeSandboxModules.test.ts` : 44 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 557 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS7, le harnais ne peut plus ouvrir le reseau sur simple occurrence textuelle de `install`. WS7 reste ouvert sur deux preuves dures : quota disque total du workspace et execution runtime effective sur hote equipe Podman. Le filtrage domaine paquet par paquet reste egalement a traiter si l'on veut aller au-dela de l'allowlist commande/env actuelle.

## 2026-07-15 — Vague 2 / WS7 increment 42 — Auto-reparation npm sans fuite hote

### Reprise et diagnostic confirme

- En relisant l'integration WS7, j'ai trouve une fuite non couverte par l'increment 41.
- `runNodeInstallWithAutoRepair` recevait bien `npm install` deja encapsule dans Podman, mais son lookup de secours `npm view <pkg> versions --json` appelait encore `runWorkspaceCommand(npm, ...)` directement.
- Cette execution hote contredisait l'objectif WS7 : aucun code ou acces registre lie a une generation ne doit echapper au sandbox.

### Recherches et choix techniques

- Aucune nouvelle recherche web externe : le probleme etait dans le code local et le wrapper Podman WS7 existait deja.
- Choix retenu : rendre le lookup registre injectable et obligatoire, construit depuis `codeSandbox.ts` ou `wrapCommandForPodman` et le statut GPU/reseau sont disponibles.
- Choix de securite : ne pas conserver de fallback implicite vers `npm` hote dans `codeSandboxRegistryRepair.ts`.

### Modifications realisees

- `runNodeInstallWithAutoRepair` exige maintenant `buildRegistryLookupCommand`.
- `codeSandbox.ts` construit `npm view <pkg> versions --json` via `wrapCommandForPodman`.
- `codeSandboxNetworkPolicy.ts` allowliste `npm view` comme operation registre npm, avec les memes variables `NPM_CONFIG_*`.
- `codeSandboxModules.test.ts` prouve que la resolution de version passe par `podman`, pas par `npm` hote.

### Avant / apres mesurable

- Avant : un paquet npm invalide pouvait declencher une commande reseau hote pendant la correction automatique.
- Apres : la correction automatique reste dans le meme chemin sandbox/quotas/reseau que l'installation initiale.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxNetworkPolicy.test.ts src/__tests__/codeSandboxModules.test.ts src/__tests__/codeSandboxIsolation.test.ts` : 32 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 559 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS7, l'egress registre ne fuit plus par l'auto-reparation npm. WS7 reste ouvert sur la limite disque totale du workspace et la preuve runtime sur un hote equipe Podman.

## 2026-07-15 — Vague 2 / WS7 increment 43 — Quota disque total du workspace sandbox

### Reprise et diagnostic confirme

- WS7 demande que `disk-fill` soit contenu.
- Les increments precedents prouvaient `ulimit fsize`, donc un gros fichier unique, mais pas la somme de nombreux petits fichiers.
- Le chemin courant montait `${sandboxRoot}:/workspace:rw,Z` : ce bind mount hote n'a pas de quota total encode dans les arguments Podman.
- Un simple `tmpfs /workspace` par commande aurait perdu les artefacts d'installation entre `npm install` et `npm run build`, car le harnais garde volontairement un conteneur par commande pour changer le reseau selon la politique egress.

### Recherches et choix techniques

- Sources officielles Podman consultees :
  - `podman volume create` : `https://docs.podman.io/en/latest/markdown/podman-volume-create.1.html` documente `--opt o=size=...`, les volumes, et la contrainte XFS/project quota.
  - `--mount` Podman : `https://docs.podman.io/en/v4.4/markdown/options/mount.html` documente les mounts `tmpfs` et `tmpfs-size`, utile pour verifier que tmpfs est borne mais non adapte seul a la persistance multi-commandes.
  - `podman run` : `https://docs.podman.io/en/latest/markdown/podman-run.1.html` confirme le modele `podman run` par commande et ses options.
- Choix retenu : volume Podman nomme et quote pour `/workspace`, initialise depuis le dossier hote monte en lecture seule `/aurora-input`.
- Raison technique : le volume persiste entre conteneurs successifs, ce qui conserve `node_modules`/artefacts d'installation, tout en gardant le reseau decide par commande (`none` pour build/test, registre pour install/view).
- Limite documentee : sur un hote sans Podman, ou sans support quota volume rootless, le harnais bloque proprement. La preuve runtime locale reste impossible aujourd'hui car `podman` est absent.

### Modifications realisees

- `codeSandboxIsolation.ts` :
  - ajoute `workspaceSize=768m` au profil de quotas ;
  - ajoute `sandboxWorkspaceVolumeName` ;
  - ajoute `buildPodmanSandboxVolumeCreateArgs` / `buildPodmanSandboxVolumeRemoveArgs` ;
  - ajoute `buildPodmanSandboxWorkspaceInitArgs` ;
  - remplace le bind rw `/workspace` par `aurora-code-ws-*:/workspace:rw,z`.
- Nouveau `codeSandboxWorkspace.ts` :
  - cree le volume quote ;
  - initialise `/workspace` depuis `/aurora-input` ;
  - nettoie le volume ;
  - signale les echecs de quota comme step bloquant.
- `codeSandbox.ts` :
  - prepare le volume apres le preflight Podman et avant les probes ;
  - nettoie le volume en `finally` ;
  - resynchronise le volume apres une auto-correction npm.
- `codeSandboxIsolationProbes.ts` :
  - ajoute `Preuve quota disque workspace`, qui ecrit 384 fichiers de 3 Mo pour tester la limite totale sans declencher `fsize`.

### Avant / apres mesurable

- Avant : `/workspace` etait un bind hote rw sans quota total ; seul un fichier individuel de 2 Go etait teste.
- Apres : `/workspace` est un volume Podman quote a 768 Mo, les commandes projet ne voient plus le chemin hote en rw, et une probe disk-fill totale est obligatoire avant les commandes projet.
- Avant : une correction npm pouvait modifier `package.json` sur l'hote sans mettre a jour le support d'execution si celui-ci devenait non-binde.
- Apres : la resynchronisation du volume est appelee apres chaque correction registre.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSandboxWorkspace.test.ts src/__tests__/codeSandboxIsolation.test.ts src/__tests__/codeSandboxIsolationProbes.test.ts src/__tests__/codeSandboxNetworkPolicy.test.ts src/__tests__/codeSandboxModules.test.ts src/__tests__/codeSandboxGpu.test.ts src/__tests__/codeSandboxGc.test.ts` : 53 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 566 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS7, la dette "disque total workspace" est traitee cote architecture et tests unitaires : le chemin vert exige un volume quote puis une probe disk-fill totale. La preuve runtime effective reste suspendue a l'installation de Podman rootless et a un stockage supportant les quotas de volume. WS7 reste ouvert sur cette preuve hote et sur le filtrage egress domaine/IP plus fin que l'allowlist commande/env actuelle.

## 2026-07-15 — Vague 3 / WS3 increment 44 — Contrat de fichiers requis du plan architecte

### Reprise et diagnostic confirme

- Le Module Code possede deja un plan architecte JSON valide (WS4), un protocole VFS structure (WS2) et une boucle de retry de sortie.
- Le diagnostic WS3 reste vrai sur le fond : `runGenerationPhase` est encore un appel LLM stream unique, pas un executeur outil-par-outil.
- Avant cet increment, le plan etait injecte au Codeur comme contexte, mais la boucle de sortie ne prouvait pas que les fichiers requis par `plan.files[]` avaient ete livres.

### Recherches et choix techniques

- Aucune recherche web externe : le besoin est local et s'appuie sur les modules deja livres (`codeArchitecturePlan.ts`, `codeGenerationOutputRetry.ts`).
- Choix retenu : commencer WS3 par un contrat machine faible mais executable, avant la refonte plus large en agent a outils.
- Raison technique : un plan JSON qui ne contraint pas la livraison reste un prompt ; le verifier dans la boucle de retry transforme le plan en garde-fou non silencieux.

### Modifications realisees

- Ajout de `src/services/codeArchitecturePlanContract.ts` :
  - parse le plan architecte JSON ;
  - extrait les fichiers `required !== false` ;
  - ignore les fichiers de documentation generes ensuite par le support automatique ;
  - retourne un diagnostic quand un fichier requis manque.
- `codeGenerationOutputRetry.ts` :
  - appelle `describeArchitecturePlanContractIssue` ;
  - declenche une regeneration si un fichier requis du plan manque ;
  - logge explicitement `plan=true` dans les diagnostics de retry.
- Ajout de `src/__tests__/codeArchitecturePlanContract.test.ts`.

### Avant / apres mesurable

- Avant : un plan pouvait exiger `src/App.tsx` et `src/main.tsx`, mais une sortie avec seulement `package.json` pouvait passer aux gates suivantes si les heuristiques d'intention ne l'attrapaient pas.
- Apres : les fichiers requis du plan sont verifies avant la validation sandbox ; une absence devient une cause de regeneration.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeArchitecturePlanContract.test.ts src/__tests__/codeGenerationOutputRetry.test.ts src/__tests__/codeArchitecturePlan.test.ts src/__tests__/codePipelinePhases.test.ts` : 14 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 569 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : c'est une marche de securisation qui rend le plan executable au niveau des fichiers requis. Il reste a remplacer le mono-appel par un executeur agentique fichier-par-fichier, puis a brancher les evenements typés vers l'UI et le bridge `/api/code/*`.

## 2026-07-15 — Vague 3 / WS3 increment 45 — Contrat d'evenements typés pour le stream Code

### Reprise et diagnostic confirme

- Le prompt WS3 exige une route `/api/code/*` streamée en SSE ou NDJSON avec evenements typés.
- Le chemin app reel reste encore local au front : `codeStreamStore` appelle directement `orchestrateCodeGeneration` et consomme des callbacks libres (`setPhase`, `onToken`, `onFilesUpdate`, `onValidationUpdate`, `onCorrectionLogUpdate`).
- Avant cet increment, aucune source de verite ne definissait le schema `phase` / `file.written` / `test.result` / `visual.score` / `correction` / `done` / `error`.

### Recherches et choix techniques

- Aucune recherche web externe : le besoin est un contrat interne entre orchestrateur, bridge et UI.
- Choix retenu : NDJSON versionne `aurora.code.stream/1`, validable a l'execution et independant de React/Zustand.
- Raison technique : poser le schema avant la route bridge evite de figer une API implicite et rend la migration UI incrementalement testable.

### Modifications realisees

- Ajout de `src/services/codeStreamEvents.ts` :
  - types d'evenements stream obligatoires ;
  - builders deterministes pour phase, fichier ecrit, resultat sandbox, score visuel, correction, fin et erreur ;
  - serialisation NDJSON + parsing defensif ;
  - validation runtime `isCodeStreamEvent`.
- `codeStreamStore.ts` :
  - initialise un `runId` et une sequence par generation ;
  - conserve un journal borne de 240 evenements ;
  - traduit les callbacks existants en evenements typés sans modifier le rendu actuel.
- `codeStreamEventLog.ts` et `codeStreamPreflight.ts` :
  - sortent l'adaptation stream et les prevols bridge/modele du store ;
  - maintiennent `codeStreamStore.ts` sous le seuil WS1 de 600 lignes.
- `codeStreamTypes.ts` et `codeStreamSessions.ts` :
  - ajout du champ `events` aux snapshots de session.
- Ajout de `src/__tests__/codeStreamEvents.test.ts` et adaptation de `codeStreamStoreModules.test.ts`.

### Avant / apres mesurable

- Avant : la progression Code etait un ensemble de champs libres (`phaseMessage`, `progressPct`, `files`, `finalScore`) impossible a exposer tel quel en API stable.
- Apres : le meme chemin produit une chronologie typée et serialisable. Le bridge `/api/code/*` pourra streamer cette chronologie sans inventer de nouveau format.
- Limite assumee : `visual.score` est defini mais pas encore emis par le store, faute de juge visuel reel avant WS9.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeStreamEvents.test.ts src/__tests__/codeStreamStoreModules.test.ts` : 17 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 574 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est toujours pas termine : le contrat stream est maintenant explicite et teste, mais l'ancien chemin direct reste actif tant que le bridge `/api/code/*` et l'executeur fichier-par-fichier ne sont pas branches.

## 2026-07-15 — Vague 3 / WS3 increment 46 — File d'execution depuis le plan architecte

### Reprise et diagnostic confirme

- `runGenerationPhase` restait un mono-appel LLM stream.
- Le plan architecte JSON contenait deja `files[]` et `generationOrder[]`, mais ces champs servaient surtout de contexte textuel.
- Pour passer vers un moteur planner-executor, il faut une file machine stable avant de brancher les outils d'ecriture.

### Recherches et choix techniques

- Aucune recherche web externe : la source de verite est le plan JSON local valide par `codeArchitecturePlan.ts`.
- Choix retenu : deriver une queue deterministic depuis `generationOrder[]`, puis completer avec les fichiers non ordonnes de `files[]`.
- Raison technique : l'ordre explicite de l'architecte doit piloter le futur executor, mais on ne doit pas perdre un fichier requis oublie dans `generationOrder[]`.

### Modifications realisees

- Ajout de `src/services/codeGenerationQueue.ts` :
  - `buildGenerationQueueFromArchitecturePlan` parse le plan valide ;
  - deduplique les chemins avec normalisation `./` et séparateurs Windows ;
  - preserve `required`, role, language, imports, exports, notes ;
  - signale les chemins de `generationOrder[]` absents de `files[]`.
- `codePipelinePhases.ts` :
  - injecte `formatGenerationQueueForPrompt(queue)` dans le contexte systeme du Codeur ;
  - conserve le plan JSON complet/tronque existant pour compatibilite.
- Ajout de `src/__tests__/codeGenerationQueue.test.ts`.

### Avant / apres mesurable

- Avant : le Codeur recevait le plan comme un bloc JSON, sans file compacte directement exploitable par un executor.
- Apres : chaque generation avec plan valide reçoit un manifeste ordonne `FILE-BY-FILE EXECUTION MANIFEST — WS3`, pret a etre consomme par le futur moteur outil-par-outil.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationQueue.test.ts src/__tests__/codePipelinePhases.test.ts src/__tests__/codeArchitecturePlan.test.ts src/__tests__/codeArchitecturePlanContract.test.ts` : 12 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 577 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : le moteur n'execute pas encore la queue fichier par fichier. Mais la donnee de pilotage est maintenant construite, testee et branchee au chemin de generation actif.

## 2026-07-15 — Vague 3 / WS3 increment 47 — Outils VFS du planner-executor

### Reprise et diagnostic confirme

- WS3 cible explicitement une boucle a outils `write_file/read_file/apply_patch/run_command`.
- Le Module Code avait deja le VFS/protocole WS2 et la queue WS3, mais pas d'API locale commune pour appliquer des actions outil-par-outil sur le projet en memoire.
- `run_command` ne doit pas contourner WS7 : il doit passer par un runner sandbox explicite.

### Recherches et choix techniques

- Aucune recherche web externe : il s'agit d'un contrat interne sur `CodeFile[]` et `codeProjectTree.normalizeProjectPath`.
- Choix retenu : un executor pur, synchrone sur le VFS pour les fichiers, asynchrone uniquement pour `run_command`.
- Raison technique : separer l'effet fichier de l'execution sandbox permet de tester les mutations sans lancer de process et de brancher WS7 ensuite sans reecrire l'API.

### Modifications realisees

- Ajout de `src/services/codeGenerationTools.ts` :
  - types `CodeGenerationToolAction` et `CodeGenerationToolResult` ;
  - `write_file` upsert un fichier normalise ;
  - `read_file` retourne le contenu VFS ;
  - `apply_patch` fait un remplacement exact, premier match par defaut ou tous les matchs avec `all=true` ;
  - `run_command` exige un runner explicite.
- Ajout de `executeCodeGenerationToolSequence` pour appliquer une suite d'actions et stopper au premier echec.
- Ajout de `src/__tests__/codeGenerationTools.test.ts`.

### Avant / apres mesurable

- Avant : le futur executor n'avait pas de primitive VFS testee ; les reparations restaient des regenerations globales ou des merges post-generation.
- Apres : les actions de base existent, sont testees, refusent les chemins dangereux et peuvent etre branchees a un agent sans toucher au disque hote.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationTools.test.ts src/__tests__/codeGenerationQueue.test.ts src/__tests__/codePipelinePhases.test.ts` : 10 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 582 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `git diff --check` : propre.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : les outils VFS sont prets, mais ils ne pilotent pas encore la generation LLM. La prochaine marche consiste a les connecter a une boucle executor qui traite la queue architecte et emet les evenements stream.

## 2026-07-15 — Vague 3 / WS3 increment 48 — Executor de queue fichier-par-fichier

### Reprise et diagnostic confirme

- WS3 demande explicitement une etape 2 "executeur fichier-par-fichier" au-dessus du plan architecte.
- Les increments precedents avaient pose le plan JSON, la queue, le schema stream et les outils VFS, mais aucune boucle ne consommait encore la queue.
- `CodeView.tsx` et `codeStreamStore.ts` sont proches du seuil 600 lignes ; l'increment doit donc rester dans un service isole.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment assemble des contrats internes deja poses (`CodeGenerationQueue`, `CodeGenerationToolAction`, `CodeStreamEvent`).
- Choix retenu : `executeCodeGenerationQueue` reçoit un `produceActions` injecte au lieu d'appeler directement le LLM.
- Raison technique : cette separation permet de tester la boucle deterministement, puis de brancher un producteur LLM NDJSON/SSE sans reecrire l'execution ni le stream.

### Modifications realisees

- Ajout de `src/services/codeGenerationExecutor.ts` :
  - iteration ordonnee des items de queue ;
  - emission `phase` par fichier ;
  - application des actions VFS via `executeCodeGenerationTool` ;
  - emission `file.written` a chaque mutation detectee ;
  - blocage d'un fichier requis non produit ;
  - tolerance configurable des echecs optionnels ;
  - emission finale `done` ou `error`.
- Ajout de `src/__tests__/codeGenerationExecutor.test.ts`.

### Avant / apres mesurable

- Avant : la queue et les outils existaient separement ; aucun composant ne prouvait un flux fichier-par-fichier complet.
- Apres : une queue issue du plan architecte peut produire plusieurs fichiers en ordre, streamer chaque ecriture et s'arreter proprement si un fichier requis manque.
- Limite assumee : le producteur d'actions est encore injecte dans les tests ; le branchement LLM et la route `/api/code/*` restent a faire.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationExecutor.test.ts src/__tests__/codeGenerationTools.test.ts src/__tests__/codeGenerationQueue.test.ts src/__tests__/codeStreamEvents.test.ts` : 15 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 585 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est toujours pas termine : la boucle executor existe et est testee, mais la production d'actions n'est pas encore assuree par le LLM fichier-par-fichier ni exposee par le bridge stream `/api/code/*`.

## 2026-07-15 — Vague 3 / WS3 increment 49 — Producteur LLM d'actions outil

### Reprise et diagnostic confirme

- L'executor WS3 consomme deja des actions outil, mais le producteur restait simule par les tests.
- Le protocole `AURORA_CODE_VFS/1` livre des fichiers complets ; il ne suffit pas pour une boucle `read_file/write_file/apply_patch/run_command`.
- Pour brancher le LLM sans recreer un blob global, il faut un protocole d'actions distinct et un contexte cible par item de queue.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment s'appuie sur les contrats internes WS2/WS3 et sur `resilientOllamaChat` deja present.
- Choix retenu : `AURORA_CODE_ACTIONS/1` + JSON strict `actions[]`, parse defensif et client LLM injectable.
- Raison technique : le parseur strict empeche de melanger narration, markdown et actions executables ; l'injection du client rend la chaine testable sans charger Ollama.

### Modifications realisees

- Ajout de `src/services/codeGenerationActionProtocol.ts` :
  - constante `AURORA_CODE_ACTIONS/1` ;
  - `parseCodeGenerationActions` avec stripping `<think>`/fences ;
  - validation des actions `write_file`, `read_file`, `apply_patch`, `run_command` ;
  - `buildCodeGenerationActionInstructions` specialise par item de queue.
- Ajout de `src/services/codeGenerationActionProducer.ts` :
  - `buildCodeGenerationActionMessages` pour le contexte cible ;
  - selection des fichiers pertinents au lieu d'envoyer tout le projet ;
  - `createCodeGenerationLLMActionProducer` branche sur client injecte ou `resilientOllamaChat`.
- Ajout de `src/__tests__/codeGenerationActionProtocol.test.ts` et `src/__tests__/codeGenerationActionProducer.test.ts`.

### Avant / apres mesurable

- Avant : l'executor pouvait appliquer des actions, mais aucune sortie LLM structuree ne produisait ces actions.
- Apres : un client LLM peut etre branche fichier par fichier et ses reponses sont transformees en actions VFS typées, rejetées si le protocole est absent ou invalide.
- Limite assumee : ce producteur n'est pas encore utilise par `runGenerationPhase` et aucun endpoint `/api/code/*` ne stream encore cette boucle.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationActionProtocol.test.ts src/__tests__/codeGenerationActionProducer.test.ts src/__tests__/codeGenerationExecutor.test.ts src/__tests__/codeGenerationTools.test.ts` : 16 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 593 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : la production d'actions LLM est testable, mais elle doit encore remplacer le mono-appel de generation dans le chemin applicatif, puis etre exposee en stream bridge `/api/code/*`.

## 2026-07-15 — Vague 3 / WS3 increment 50 — Branchement agentique dans le pipeline actif

### Reprise et diagnostic confirme

- Le producteur d'actions LLM et l'executor etaient prets, mais `runFullPipeline` appelait encore directement `runGenerationPhase`.
- L'orchestrateur est proche du seuil WS1 : toute integration doit rester courte et deleguer la logique a un service dedie.
- La migration doit conserver la parite tant que `/api/code/*` n'est pas expose et tant que `run_command` n'a pas de runner WS7 branche.

### Recherches et choix techniques

- Aucune recherche web externe : il s'agit d'un branchement interne entre les briques WS3 deja testees.
- Choix retenu : `runAgenticGenerationPhase` se place avant le mono-appel historique, uniquement si `buildGenerationQueueFromArchitecturePlan` retourne une queue.
- Raison technique : le chemin applicatif commence a produire fichier par fichier sans supprimer le fallback tant que la route stream bridge n'est pas livree.

### Modifications realisees

- Ajout de `src/services/codeAgenticGenerationPhase.ts` :
  - construit la queue depuis le plan ;
  - cree le producteur LLM d'actions ;
  - execute la queue VFS ;
  - pousse `onFilesUpdate` apres chaque fichier ecrit ;
  - serialise le resultat final en `AURORA_CODE_VFS/1` pour le reste du pipeline existant.
- `codeOrchestrator.ts` :
  - tente la phase agentique avant `runGenerationPhase` ;
  - conserve le fallback mono-appel avec message de phase explicite en cas d'echec ;
  - garde l'annulation utilisateur prioritaire.
- `codeGenerationExecutor.ts` expose `onFilesUpdate` par mutation reussie.
- `codeGenerationActionProducer.ts` propage les images contexte dans le message utilisateur.
- Ajout de `src/__tests__/codeAgenticGenerationPhase.test.ts`.

### Avant / apres mesurable

- Avant : les briques agentiques etaient testees mais non appelees par la generation reelle.
- Apres : le chemin applicatif tente d'abord l'execution fichier-par-fichier, alimente les fichiers live, puis livre un flux final parseable par les validations existantes.
- Limite assumee : le fallback mono-appel existe encore pour parite ; WS3 ne sera clos qu'apres route `/api/code/*`, runner WS7 et preuve >40 fichiers buildable.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeAgenticGenerationPhase.test.ts src/__tests__/codeGenerationActionProducer.test.ts src/__tests__/codeGenerationExecutor.test.ts src/__tests__/codePipelinePhases.test.ts` : 10 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 595 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- Controle taille : `codeOrchestrator.ts` 595 lignes, sous le seuil dur 600.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : le chemin applicatif prefere maintenant l'executor agentique, mais la route `/api/code/*`, le runner WS7 de commandes et la demonstration >40 fichiers restent a livrer.

## 2026-07-15 — Vague 3 / WS3 increment 51 — Route bridge NDJSON `/api/code/generate/stream`

### Reprise et diagnostic confirme

- Le prompt WS3 impose une route `/api/code/*` streamée avec evenements typés.
- Le bridge avait deja des routes `/api/code/repo/*` et l'ancien dispatcher `/api/aurora/code/generate`, mais aucune route de generation Code streamée.
- `aurora_code_loop.py` n'est pas promu tel quel : il contient encore un chemin Windows et un modele par defaut obsolète, donc l'utiliser directement aurait reintroduit une dette.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment verifie les conventions locales Flask et le schema `aurora.code.stream/1` deja versionne.
- Choix retenu : ajouter une route transitoire `POST /api/code/generate/stream` qui stream du NDJSON typé et parse les fichiers produits.
- Raison technique : poser le contrat HTTP maintenant permet de brancher un client UI/bridge progressivement, sans degrader le nouveau chemin applicatif TS agentique.

### Modifications realisees

- `bridge_server.py` :
  - ajout de `CODE_STREAM_SCHEMA = "aurora.code.stream/1"` ;
  - ajout de `_code_stream_event`, `_code_stream_language`, `_code_stream_parse_files` ;
  - ajout de `POST /api/code/generate/stream` ;
  - streaming `phase`, `file.written`, `done`, `error` au format `application/x-ndjson`.
- La route demande a Ollama une sortie `AURORA_CODE_VFS/1`, puis extrait les fichiers pour emettre des evenements `file.written`.
- Aucun autre module n'est modifie ; le Viewer 3D reste intouche.

### Avant / apres mesurable

- Avant : aucun endpoint `/api/code/*` ne streamait la generation Code ; seul `/api/aurora/code/generate` renvoyait un JSON one-shot.
- Apres : un client HTTP peut consommer un flux NDJSON typé compatible avec le store TS.
- Limite assumee : cette route reste transitoire et ne remplace pas encore le moteur TS agentique ; la consommation directe par l'UI reste a brancher.

### Validation

- `python3 -m py_compile bridge_server.py` : vert.
- `node --experimental-strip-types --test src/__tests__/codeStreamEvents.test.ts src/__tests__/codeAgenticGenerationPhase.test.ts` : 6 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 595 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : le contrat HTTP stream existe, mais l'UI ne le consomme pas encore et la preuve >40 fichiers buildable reste a produire.

## 2026-07-15 — Vague 3 / WS3 increment 52 — Consommation UI/store du flux `/api/code/*`

### Reprise et diagnostic confirme

- `codeStreamStore` fabriquait deja un journal d'evenements local, mais n'appelait pas encore la route `/api/code/generate/stream`.
- `CodeView.tsx`, `codeStreamStore.ts` et `codeOrchestrator.ts` sont proches du seuil dur 600 lignes ; le branchement doit donc passer par des modules courts.
- Les corrections, repos et follow-ups dependent du contexte riche TS existant ; les basculer brutalement sur la route bridge transitoire appauvrirait le chemin applicatif.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment s'appuie sur le schema local `aurora.code.stream/1`, `getBridgeUrl` et le runner Node natif.
- Choix retenu : client NDJSON strict + adaptateur d'etat pur + micro-branchement dans `codeStreamStore`.
- Raison technique : l'UI consomme enfin un vrai flux `/api/code/*`, tout en conservant le fallback local si la route HTTP est indisponible avant le premier evenement.

### Modifications realisees

- Ajout de `src/services/codeBridgeStreamClient.ts` :
  - POST vers `/api/code/generate/stream` ;
  - lecture chunk par chunk du NDJSON ;
  - validation de chaque ligne via `parseCodeStreamEventLine`.
- Ajout de `src/stores/codeStreamRemoteState.ts` :
  - transformation pure des evenements `phase`, `file.written`, `test.result`, `visual.score`, `correction`, `done`, `error` vers le state UI.
- Ajout de `src/stores/codeStreamRemoteTurn.ts` :
  - activation par defaut pour une generation neuve online ;
  - exclusion par defaut des corrections, repos et suites de conversation ;
  - fallback local si la route echoue avant tout evenement.
- `src/stores/codeStreamStore.ts` :
  - appelle `runCodeBridgeStreamTurn` avant l'orchestrateur local ;
  - garde l'ancien chemin agentique TS quand le flux bridge n'est pas applicable.
- Ajout de tests `codeBridgeStreamClient.test.ts` et `codeStreamRemoteState.test.ts`.

### Avant / apres mesurable

- Avant : l'UI exposait un journal d'evenements simule par callbacks internes, sans consommer `/api/code/*`.
- Apres : une generation neuve online passe par le flux NDJSON bridge et met a jour fichiers, phase, score, notes et erreurs via evenements types.
- Limite assumee : la route bridge reste transitoire et ne couvre pas encore le runner WS7 `run_command`; le moteur TS agentique reste le chemin riche pour les cas contextuels.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeBridgeStreamClient.test.ts src/__tests__/codeStreamRemoteState.test.ts src/__tests__/codeStreamEvents.test.ts src/__tests__/codeStreamStoreModules.test.ts` : 23 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 601 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `npm test` complet : 4438 pass / 1 fail ; echec hors perimetre Module Code dans `src/__tests__/coworkExtract.test.ts` (`POST /api/cowork/extract-structured` retourne bridge 502).
- Controle taille : `codeStreamStore.ts` 591 lignes ; `CodeView.tsx` et le Viewer 3D restent intouches.

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : l'UI consomme maintenant la route stream, mais il reste le runner WS7 pour `run_command` et la demonstration >40 fichiers coherent/buildable.

## 2026-07-15 — Vague 3 / WS3 increment 53 — Runner WS7 pour `run_command`

### Reprise et diagnostic confirme

- `write_file`, `read_file` et `apply_patch` travaillaient deja dans le VFS projet.
- `run_command` etait volontairement bloque avec `run_command_requires_ws7_runner`, ce qui empechait l'executor WS3 de reinjecter un vrai signal lint/build pendant la generation.
- Le sandbox WS7 existant fournit deja les briques necessaires : ecriture sandbox, detection Podman rootless, volume quota, wrapping Podman, cleanup.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment reutilise l'infra WS7 locale deja testee.
- Choix retenu : un runner dedie `codeGenerationCommandRunner`, injectable en tests, branche dans `runAgenticGenerationPhase`.
- Raison technique : garder une frontiere nette entre outils VFS et execution systeme, tout en garantissant qu'aucune commande LLM ne tombe sur l'hote en direct.

### Modifications realisees

- `src/services/codeGenerationTools.ts` :
  - le `CodeGenerationToolRunner` recoit maintenant `(command, reason, files)` ;
  - `executeCodeGenerationTool` transmet le VFS courant au runner.
- Ajout de `src/services/codeGenerationCommandRunner.ts` :
  - normalise les fichiers via `normalizeSandboxFiles` ;
  - ecrit le projet dans `output/code-command-runner/<timestamp>` ;
  - exige `detectPodmanIsolation` OK ;
  - prepare/nettoie le volume quota WS7 ;
  - execute `sh -lc <commande>` uniquement dans le conteneur Podman.
- `src/services/codeAgenticGenerationPhase.ts` :
  - branche `createCodeGenerationSandboxRunner()` dans `executeCodeGenerationQueue`.
- Ajout de `src/__tests__/codeGenerationCommandRunner.test.ts` et extension de `codeGenerationTools.test.ts`.

### Avant / apres mesurable

- Avant : toute action `run_command` echouait, meme si le modele produisait une commande de validation utile.
- Apres : une action `run_command` peut etre executee dans le sandbox WS7 contre les fichiers VFS courants ; absence de Podman = echec explicite, pas fallback dangereux.
- Limite assumee : le runner depend de l'image Podman deja disponible (`--pull=never`, politique sandbox existante) ; la demonstration live >40 fichiers reste a produire.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeGenerationCommandRunner.test.ts src/__tests__/codeGenerationTools.test.ts src/__tests__/codeGenerationExecutor.test.ts src/__tests__/codeAgenticGenerationPhase.test.ts` : 13 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 604 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS3, non, WS3 n'est pas termine : le runner WS7 est branche, mais la preuve reelle d'un projet >40 fichiers coherent/buildable reste a executer et documenter.

## 2026-07-15 — Vague 3 / WS3 increment 54 — Preuve >40 fichiers buildable

### Reprise et diagnostic confirme

- WS3 demandait explicitement de prouver qu'un projet de plus de 40 fichiers peut etre genere sans troncature et reste buildable.
- Les briques etaient en place : plan JSON, queue d'execution, outils VFS, stream typé, runner WS7.
- Il manquait une preuve reproductible dans la suite Code, pas seulement une affirmation documentaire.

### Recherches et choix techniques

- Aucune recherche web externe : preuve basee sur Node natif et l'executor local.
- Choix retenu : test de preuve deterministe qui genere un mini SaaS auth + CRUD + tests sans dependance externe.
- Raison technique : le test reste rapide, reproductible, et mesure le vrai point WS3 : volume de fichiers + coherence importable + scripts executables.

### Modifications realisees

- Ajout de `src/__tests__/codeAgenticLargeProjectProof.test.ts` :
  - construit 48 fichiers via un plan architecte schema-valide ;
  - inclut 32 modules d'entites, auth, CRUD, index, scripts et tests ;
  - fait produire chaque fichier par `executeCodeGenerationQueue` ;
  - ecrit le projet genere dans un dossier temporaire ;
  - execute reellement `npm run build` puis `npm test` sur ce projet genere.

### Avant / apres mesurable

- Avant : WS3 avait l'executor et le runner, mais aucune preuve automatique du seuil >40 fichiers.
- Apres : le glob Code contient une preuve verte qui genere plus de 40 fichiers et valide build + tests sur un mini SaaS coherent.
- Limite assumee : preuve deterministe locale, pas encore generation LLM live longue via Ollama ; la route bridge reste transitoire pour le flux HTTP.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeAgenticLargeProjectProof.test.ts` : 1 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 605 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour WS3 local, les criteres majeurs sont maintenant couverts : executor VFS, route `/api/code/*`, UI stream, runner WS7 et preuve >40 fichiers buildable. Je ne marque pas WS3 totalement clos tant que la route bridge de generation reste transitoire au lieu d'exposer directement le moteur agentique TS.

## 2026-07-15 — Vague 3 / WS5 increment 55 — Memoire projet locale pour contexte cible

### Reprise et diagnostic confirme

- WS5 demande de remplacer la troncature de contexte par une memoire projet exploitable et des patchs incrementaux cibles.
- Le producteur d'actions WS3 recevait deja une fenetre de queue et les fichiers existants, mais la selection de contexte reposait encore sur quelques heuristiques de chemins/imports.
- Le socle WS2 (`ProjectTree` + graphe d'imports) etait disponible ; il fallait l'utiliser dans le chemin de generation fichier-par-fichier sans grossir `codeOrchestrator.ts`, `codeStreamStore.ts` ou `CodeView.tsx`, deja proches du seuil 600 lignes.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment est une integration RAG locale fondee sur les structures WS2 deja testees.
- Choix retenu : une memoire projet pure et deterministe, reconstruite depuis le VFS courant, avec scoring explicable par raisons (`target`, `config`, `same-dir`, `imports`, `imported-by`, `plan-import`, `prompt-term`).
- Raison technique : apporter un gain immediat de pertinence et de tracabilite au contexte du codeur, tout en gardant l'etape embeddings/persistance pour l'increment suivant.

### Modifications realisees

- Ajout de `src/services/codeProjectMemory.ts` :
  - construit un index par fichier depuis `buildProjectTree` ;
  - conserve langage, taille, imports, importeurs, symboles et termes ;
  - selectionne un contexte borne via `selectCodeProjectMemoryContext`.
- `src/services/codeGenerationActionProducer.ts` :
  - supprime la selection heuristique `isRelevantFile` ;
  - selectionne les fichiers existants via la memoire projet ;
  - ajoute les raisons de selection dans les entetes `--- EXISTING ... ---` fournis au modele.
- Ajout de `src/__tests__/codeProjectMemory.test.ts`.

### Avant / apres mesurable

- Avant : un fichier etait considere pertinent par egalite de chemin, configs globales ou inclusion textuelle fragile d'un import.
- Apres : le contexte cible s'appuie sur l'arbre projet, le graphe d'imports, les symboles, les importeurs et les termes du prompt, avec raisons auditables.
- Limite assumee : cette memoire est encore locale/en RAM ; elle ne contient pas d'embeddings persistants et ne prouve pas encore le patch incremental anti-regression demande par le DoD WS5.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectMemory.test.ts src/__tests__/codeGenerationActionProducer.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 607 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS5, oui : la selection RAG locale exploitable est branchee sur le chemin agentique. Pour WS5 complet, non : il reste a ajouter la persistance/embeddings et a prouver une modification par `apply_patch` ciblee avec non-regression des fichiers non concernes.

## 2026-07-15 — Vague 3 / WS5 increment 56 — Index durable, portee patch et non-regression protegee

### Reprise et diagnostic confirme

- L'increment 55 selectionnait deja mieux le contexte, mais reconstruisait l'index en memoire et ne prouvait pas encore le DoD WS5 sur patch/non-regression.
- Le fallback mono-shot `runGenerationPhase` conservait encore l'ancien comportement : parcourir les fichiers existants dans l'ordre jusqu'a epuisement du budget, donc retomber dans la troncature que WS5 doit supprimer.
- Les prompts utilisateur sont frequemment en francais alors que les chemins/symboles de code sont en anglais (`facturation` vs `billing`, `devise` vs `currency`) ; sans pont lexical local, le RAG peut manquer les bons fichiers.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment s'appuie sur les choix deja actés dans le prompt maitre (index local, embeddings locaux, patch incremental contre graphe).
- Choix retenu : embeddings locaux deterministes par feature hashing, persistables avec l'index, puis schema stable `aurora.code.project-memory/1`.
- Raison technique : obtenir une memoire durable et testable sans bloquer le build sur Ollama ; le schema reste compatible avec un futur embedder local de modele (`nomic-embed-text` ou `bge-m3`) sans changer les consommateurs.

### Modifications realisees

- `src/services/codeProjectMemory.ts` :
  - ajoute `embedding` par fichier ;
  - ajoute `buildLocalCodeEmbedding` ;
  - ajoute une selection par prompt seul pour les patchs incrementaux ;
  - ajoute un lexique FR/EN minimal pour les termes projet courants.
- Ajout de `src/services/codeProjectMemoryPersistence.ts` :
  - fingerprint stable des fichiers ;
  - snapshot durable avec schema, date, fichiers indexes et embeddings ;
  - restauration/cache `localStorage` quand disponible.
- Ajout de `src/services/codeIncrementalPatchScope.ts` :
  - calcule fichiers cibles, fichiers proteges et raisons ;
  - formate la portee pour le prompt ;
  - detecte les modifications/suppressions sur fichiers proteges.
- Ajout de `src/services/codeExistingProjectContext.ts` :
  - remplace le contexte legacy sequentiel par un contexte RAG cible ;
  - montre uniquement les fichiers cibles et marque les autres comme proteges.
- `src/services/codeGenerationActionProducer.ts` :
  - utilise l'index persistant ;
  - inclut la portee WS5 ;
  - demande explicitement `apply_patch` en modification.
- `src/services/codePipelinePhases.ts` :
  - le fallback mono-shot consomme `buildExistingProjectPatchContext` au lieu d'envoyer tous les fichiers jusqu'a troncature.
- Tests ajoutes :
  - `codeProjectMemoryPersistence.test.ts`
  - `codeIncrementalPatchScope.test.ts`
  - `codeExistingProjectContext.test.ts`
  - extensions de `codeProjectMemory.test.ts` et `codeGenerationActionProducer.test.ts`.

### Avant / apres mesurable

- Avant : contexte existant = ordre arbitraire des fichiers, troncature par budget, pas de cache durable, pas de verification que les fichiers non concernes restent identiques.
- Apres : index durable par fingerprint, embeddings locaux, selection par graphe/termes/embedding, portee de patch explicable, fichiers proteges explicites et assertion de non-regression.
- Limite assumee : la preuve est deterministe et locale ; une generation LLM live de modification incrementaliste reste a rejouer pour marquer WS5 complet cote produit.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeProjectMemory.test.ts src/__tests__/codeProjectMemoryPersistence.test.ts src/__tests__/codeIncrementalPatchScope.test.ts src/__tests__/codeExistingProjectContext.test.ts src/__tests__/codeGenerationActionProducer.test.ts src/__tests__/codePipelinePhases.test.ts` : 14 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 614 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS5, oui : durabilite, embeddings locaux, RAG cible, patch incremental et non-regression protegee sont couverts par les services et les tests. Pour WS5 complet, il reste a produire une preuve live avec le modele sur un projet existant et a decider si l'embedder local deterministe suffit ou si le schema doit etre alimente par Ollama.

## 2026-07-15 — Vague 3 / WS6 increment 57 — Taxonomie extreme, classifieur semantique et registre de generateurs

### Reprise et diagnostic confirme

- La decomposition WS1 avait laisse `codeIntentClassification.ts` en classifieur deterministe/heuristique, sans les cibles extremes demandees par le prompt maitre.
- Les types `embedded_esp32`, `embedded_arduino`, `compiler`, `os_kernel`, `distributed_system`, `mobile_ios`, `mobile_android`, `desktop_app`, `engine_3d` et `ide` n'existaient pas dans `CodeProjectType`.
- `buildCodeSystemPromptFromIntent` n'avait aucun registre de generateurs specialise ; les familles extremes etaient donc forcees dans des prompts generiques.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment applique la taxonomie explicitement demandee par le prompt maitre.
- Choix retenu : classification hybride. Le chemin synchrone existant garde un fallback deterministe, et un nouveau classifieur semantique accepte une sortie LLM JSON schema-versionnee quand un client modele est fourni.
- Raison technique : ne pas casser le pipeline actuel synchrone, tout en posant le contrat LLM structure exige par WS6.

### Modifications realisees

- `src/services/codeIntentTypes.ts` :
  - ajout des nouveaux `CodeProjectType` WS6.
- `src/services/codeIntentSemanticSignals.ts` :
  - signaux semantiques deterministes pour embarque, compilateur, OS, distribue, mobile natif, desktop natif, moteur 3D et IDE.
- `src/services/codeIntentClassification.ts` :
  - applique les signaux semantiques avant les signaux frameworks/langages generiques ;
  - evite de classer une CLI Rust avec `parser` comme compilateur ;
  - preview console pour embarque/compiler/OS/distribue.
- `src/services/codeSemanticIntentClassifier.ts` :
  - prompt de classifieur LLM strict JSON ;
  - parser schema `aurora.code.semantic-intent/1` ;
  - application d'une classification de modele avec seuil de confiance ;
  - fallback deterministe en cas de JSON invalide, type inconnu, confiance basse ou exception.
- `src/services/codeProjectGeneratorRegistry.ts` :
  - interface `ProjectGenerator` ;
  - generateurs dedies pour chaque nouvelle famille ;
  - bloc prompt specialise injecte dans `buildCodeSystemPromptFromIntent`.
- `src/services/codeIntentCommands.ts` et `src/services/codeIntentFileCount.ts` :
  - commandes build/test/dev et tailles minimales par nouvelle famille.
- Tests ajoutes/etendus :
  - `codeIntent.test.ts`
  - `codeProjectGeneratorRegistry.test.ts`
  - `codeSemanticIntentClassifier.test.ts`.

### Avant / apres mesurable

- Avant : une demande "noyau OS", "firmware ESP32", "compilateur", "systeme distribue" ou "IDE" tombait dans des types generiques (`script`, `desktop_tauri`, `system_rust`, etc.) sans prompt dedie.
- Apres : ces demandes ont un type explicite, des commandes, une taille attendue, un generateur specialise et un contrat LLM JSON structure.
- Limite assumee : cet increment route et prompt correctement ; il ne prouve pas encore un projet extreme buildable/bootable bout en bout.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeIntent.test.ts src/__tests__/codeIntentModules.test.ts src/__tests__/codeProjectGeneratorRegistry.test.ts src/__tests__/codeSemanticIntentClassifier.test.ts` : 53 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 625 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour cet increment WS6, oui : la taxonomie, le contrat semantique structure, le fallback deterministe et le registre de generateurs sont en place. Pour WS6 complet, non : il reste la preuve d'au moins une cible extreme de bout en bout sous WS7.

## 2026-07-15 — Vague 3 / WS6 increment 58 — Preuve extreme mini-compilateur buildable

### Reprise et diagnostic confirme

- Le DoD WS6 demande explicitement une preuve d'au moins une cible extreme bout en bout : OS QEMU, mini-compilateur ou systeme distribue >=2 noeuds.
- Apres l'increment 57, la cible `compiler` etait routable et promptable, mais pas encore prouvee par execution reelle.
- `cargo` est disponible sur l'hote (`cargo 1.96.1`), ce qui permet une preuve locale fiable sans installer de dependances et sans toucher a `.venv`.

### Recherches et choix techniques

- Aucune recherche web externe : la preuve s'appuie sur Rust/Cargo disponible localement et sur l'executor VFS WS3 deja valide.
- Choix retenu : mini-compilateur/interpreteur d'expressions arithmetiques en Rust, avec lexer, parser AST, evaluation, CLI et tests.
- Raison technique : c'est une cible extreme representable par un projet court mais reel, dont la correction peut etre verifiee objectivement par `cargo test` et `cargo run`.

### Modifications realisees

- Ajout de `src/__tests__/codeExtremeCompilerProof.test.ts` :
  - construit un plan architecte schema-valide `projectType: "compiler"` ;
  - genere les fichiers via `executeCodeGenerationQueue` et actions `write_file` ;
  - ecrit le projet dans un dossier temporaire ;
  - lance `cargo test --quiet` ;
  - lance `cargo run --quiet -- 2+3*4` et verifie la sortie `14`.
- Projet genere dans la preuve :
  - `Cargo.toml`
  - `src/lib.rs`
  - `src/lexer.rs`
  - `src/parser.rs`
  - `src/eval.rs`
  - `src/main.rs`
  - `tests/language.rs`
  - `README.md`

### Avant / apres mesurable

- Avant : WS6 avait la taxonomie et les prompts specialises, mais aucune cible extreme n'etait compilee/executée.
- Apres : une cible extreme `compiler` est generee par le planner-executor, compile, passe ses tests et execute un programme fige.
- Limite assumee : preuve deterministe locale ; les preuves OS QEMU et systeme distribue restent a ajouter comme extensions WS6/WS12/WS7.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeExtremeCompilerProof.test.ts` : 1 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 626 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour WS6 local, oui : les criteres majeurs sont maintenant couverts, y compris une cible extreme bout en bout. Je ne marque pas WS6 comme definitivement clos pour toutes les familles tant que les generateurs specialises n'ont pas chacun une preuve buildable equivalente.

## 2026-07-15 — Vague 3 / WS13 increment 59 — Auto-correction anti-regression

### Reprise et diagnostic confirme

- Le prompt maitre identifie WS13 comme un chantier fort : correction pilotee par cause, suppression des strategies degradantes, harnais anti-regression et budget adaptatif.
- `codeAutoCorrection.ts` pilotait encore l'escalade surtout par compteur et contenait des rotations degradantes apres la passe 5 : changement de stack/framework, reduction au strict minimum, suppression tests/config/docs et mono/deux fichiers.
- `codeCorrectionMessages.ts` reinjectait une consigne de simplification/changement de librairies en `strategy_change`.
- `codeReasoningEngine.ts` pouvait reinjecter une "simplification" demandant de reduire le nombre de fichiers au strict minimum.
- `codeValidationCorrectionLoop.ts` acceptait un candidat des qu'il passait `validateOutputMatchesIntent`, sans snapshot comportemental avant/apres.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment traite un defaut local explicitement documente dans le prompt.
- Choix retenu : snapshot comportemental deterministe et leger, calcule sur le VFS courant avant/apres patch, plutot qu'une execution supplementaire couteuse a chaque fusion.
- Signaux du snapshot : fichiers non vides, fichiers de tests, scripts `package.json`, exports publics, endpoints/routes et taille fonctionnelle source.
- Raison technique : ce garde bloque les regressions "gameables" avant meme que le score sandbox puisse etre ameliore artificiellement par suppression de capacites.

### Modifications realisees

- `src/services/codeAutoCorrection.ts` :
  - ajout de `CorrectionLocality`, `CorrectionHistorySignal`, `buildCorrectionDiagnosis` et `computeAdaptiveCorrectionBudget` ;
  - chaque `CorrectionStrategy` expose `cause`, `locality` et `history` ;
  - budget adaptatif par complexite, plafonne par `MAX_CORRECTION_PASSES` ;
  - suppression des consignes degradantes et remplacement par des variations conservatrices ;
  - les tests restent des contrats d'acceptation, pas une variable a simplifier.
- `src/services/codeRegressionGuard.ts` :
  - nouveau schema `aurora.code.regression-snapshot/1` ;
  - extraction des scripts, exports, endpoints Express/Flask/FastAPI/Django/Next route handlers, tests et taille source ;
  - comparaison avant/apres et rapport formatte.
- `src/services/codeValidationCorrectionLoop.ts` :
  - rollback automatique des reparations locales, regenerations de secours et corrections LLM qui reduisent les capacites detectees ;
  - ajout du rapport anti-regression dans `CorrectionPass.errors`.
- `src/services/codeCorrectionMessages.ts` :
  - injection cause/localite/historique dans le system prompt ;
  - interdiction explicite de faire passer la validation en supprimant fonctionnalite, test, doc, script, export ou endpoint.
- `src/services/codeReasoningEngine.ts` :
  - remplacement de la simplification "strict minimum" par une simplification structurelle conservatrice ;
  - import `ollamaResilience` rendu lazy pour tester la fonction pure sans charger le pont Tauri.
- Tests ajoutes/etendus :
  - `codeRegressionGuard.test.ts`
  - `codeReasoningEngine.test.ts`
  - `codeAutoCorrection.test.ts`
  - `codeCorrectionMessages.test.ts`.

### Avant / apres mesurable

- Avant : une passe tardive pouvait demander explicitement de supprimer tests/docs/config, de produire un MVP mono-fichier ou de changer de stack pour passer.
- Apres : ces consignes ne sont plus emises par la strategie, les messages de correction ni le raisonnement de plateau.
- Avant : un candidat appauvri pouvait etre accepte si son intention generale semblait encore plausible.
- Apres : un candidat qui retire fichier non vide, test, script, export, endpoint ou taille fonctionnelle importante est refuse et le VFS courant est conserve.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeAutoCorrection.test.ts src/__tests__/codeCorrectionMessages.test.ts src/__tests__/codeRegressionGuard.test.ts src/__tests__/codeReasoningEngine.test.ts src/__tests__/codeValidationCorrectionLoop.test.ts` : 53 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 636 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- Recherche anti-regression textuelle : plus d'ancienne consigne degradante dans les chemins de correction Code ; les occurrences restantes sont des assertions de tests ou un gabarit jeu HTML auto-suffisant hors auto-correction.

### Etat de satisfaction chantier

Pour WS13 local, le socle est couvert : strategie fonction de categorie/localite/historique, suppression des strategies degradantes, snapshot comportemental et rollback automatique, budget adaptatif avec plafond machine. Restent a enrichir : reinjection plus detaillee des diagnostics AST/visuels dans le choix de strategie, preuve live longue d'une correction LLM sur projet reel et re-test WS7 complet apres cette correction.

## 2026-07-15 — Vague 4 / WS9 increment 60 — Socle juge visuel rendu reel

### Reprise et diagnostic confirme

- Le prompt maitre demande que le score visuel provienne d'un rendu reel, pas d'une inspection regex de la source.
- `codeVisualFidelity.ts` reste utile comme fallback deterministe, mais son score etait jusqu'ici source-only.
- L'infra historique `python-services/aurora_code/cdp_drive.mjs` savait deja ouvrir une URL et capturer un screenshot, mais ne produisait pas de contrat multi-viewport ni de styles calcules exploitables par l'app.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment relie l'infra CDP deja presente au contrat WS9.
- Choix retenu : schema `aurora.code.visual-render-audit/1` separe du scoreur. Le collecteur CDP produit screenshots et metriques ; le scoreur TypeScript reste pur et testable.
- Pour le contraste, le CDP collecte les rectangles/styles de texte, puis `visual_render_audit.py` lit les PNG avec Pillow et ajoute des echantillons `source: "pixel"` derives des luminances du screenshot.
- Raison technique : on peut tester le scoreur sans lancer Chrome, tout en gardant un chemin executable pour le vrai audit rendu.

### Modifications realisees

- `src/services/codeVisualRenderAudit.ts` :
  - types du schema rendu ;
  - scoreur multi-viewport avec checks screenshots, breakpoints 390/834/1440, contraste pixel WCAG, erreurs runtime, hierarchie, densite, medias, interactions, tokens, rythme et verdict vision optionnel ;
  - critique render-in-the-loop.
- `src/services/codeVisualFidelity.ts` :
  - `evaluateVisualFidelity(files, intent, renderAudit?)` utilise le score rendu en priorite quand il est fourni ;
  - `VisualFidelityReport` indique `source` et `viewports` ;
  - `buildVisualFidelityCritique` route vers la critique WS9 quand `source === "render_audit"`.
- `python-services/aurora_code/cdp_drive.mjs` :
  - collecte de styles calcules, compteurs DOM, contrastes computed-style, erreurs runtime ;
  - nouvelle commande `audit <url> <out_dir> [wait_ms]` sur 390x844, 834x1112 et 1440x900.
- `python-services/aurora_code/visual_render_audit.py` :
  - wrapper executable du CDP ;
  - enrichissement des contrastes depuis les pixels du screenshot via Pillow.
- Tests ajoutes :
  - `codeVisualRenderAudit.test.ts`.

### Avant / apres mesurable

- Avant : le score visuel ne pouvait pas prouver qu'un navigateur avait rendu la page.
- Apres : un rapport rendu avec screenshots multi-breakpoints peut etre score ; sans screenshot, sans breakpoint complet ou sans contraste pixel, le rendu echoue.
- Avant : la critique de regeneration parlait seulement de patterns sources.
- Apres : la critique peut pointer des echecs reels : screenshots absents, responsive 390/834/1440, contraste pixel, erreurs console, densite, hierarchie et verdict vision.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeVisualFidelity.test.ts src/__tests__/codeVisualRenderAudit.test.ts src/__tests__/codeStreamEvents.test.ts` : 31 pass / 0 fail.
- `python3 -m py_compile python-services/aurora_code/visual_render_audit.py` : vert.
- `node --check python-services/aurora_code/cdp_drive.mjs` : vert.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 640 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

Pour WS9, le socle technique est pose mais le chantier n'est pas clos : il faut encore brancher l'appel automatique apres dev-server/sandbox, emettre `visual.score` depuis le flux `/api/code/*`, envoyer le screenshot au modele vision reel et relier la recherche de references UX/UI.

## 2026-07-16 — Vague 4 / WS10 increment 61 — Contrat design-spec verifiable

### Reprise et diagnostic confirme

- Le prompt maitre demande une passe design-spec JSON verifiee contre le code, une taxonomie etendue et un brand-check colorimetrique tolerant.
- `buildDesignDirectives` appliquait encore le baseline CSS web a des cibles mobile/jeu, alors que ces plateformes n'ont pas le meme contrat d'interface.
- `codeFidelityGate.ts` verifiait la couleur de marque par inclusion de hex litteral, ce qui contredisait les directives `oklch()` et les tokens proches.
- Le gate brand_landing poussait un effet Fresnel unique au lieu d'accepter une execution visuelle signature adaptee a la stack.

### Recherches et choix techniques

- Aucune recherche web externe : l'increment corrige des conflits locaux explicites du prompt.
- Choix retenu : verifier les couleurs par conversion sRGB/OKLCH vers Lab puis deltaE76, suffisamment deterministe et sans dependance runtime.
- Choix retenu : compiler une `aurora.code.design-spec/1` lisible par le modele et testable localement, plutot qu'ajouter encore des directives libres.
- Raison technique : le contrat design devient executable par tests et gates, tout en restant compatible avec les plateformes non-web.

### Modifications realisees

- `src/services/codeDesignSpec.ts` :
  - nouveau schema `aurora.code.design-spec/1` ;
  - generation palette, typographie, tokens, composants, wireframe et contraintes ;
  - inference de plateforme `web`, `mobile_native`, `desktop_native`, `game_canvas`, `ide`, `os_shell`, `non_visual` ;
  - verification contre fichiers generes : palette perceptuelle, tokens CSS web/IDE, interdiction CSS web mobile native, boucle canvas jeu, composants et wireframe.
- `src/services/codeColorMetrics.ts` :
  - parsing hex, `rgb()` et `oklch()` ;
  - conversion sRGB/OKLCH -> Lab ;
  - `hasPerceptualColorMatch` avec deltaE tolerant, y compris pour cibles `oklch()`.
- `src/services/codeDesignDirectives.ts` et `codeDesignDirectiveBlocks.ts` :
  - taxonomie ajoutee : `data_dense_enterprise`, `ide_code_editor`, `os_shell` ;
  - design-spec JSON injectee en tete du prompt design ;
  - mobile natif et jeu canvas recoivent un standard plateforme dedie, sans baseline CSS web generique ;
  - blocs specialises extraits dans `codeDesignSpecializedBlocks.ts` pour rester sous 600 lignes.
- `src/services/codeFidelityGate.ts` :
  - brand-check primaire par deltaE/Lab au lieu du hex litteral ;
  - effet signature brand_landing assoupli : shader, iridescence/bloom, CSS 3D, canvas product treatment ou traitement visuel adapte.
- Tests ajoutes/etendus :
  - `codeDesignSpec.test.ts`
  - `codeColorMetrics.test.ts`
  - `codeDesignDirectives.test.ts`
  - `codeFidelityGate.test.ts`.

### Avant / apres mesurable

- Avant : une couleur de marque proche en `rgb()` ou `oklch()` pouvait etre refusee si le hex exact etait absent.
- Apres : le deltaE valide les couleurs perceptuellement proches et rejette les couleurs eloignees.
- Avant : la directive premium web etait appliquee a tort aux jeux canvas et apps natives mobiles.
- Apres : ces plateformes ont un contrat propre et les tests prouvent l'absence du baseline CSS web generique.
- Avant : aucun objet design-spec n'etait verifie contre les fichiers.
- Apres : une spec JSON structuree peut echouer sur palette, tokens, composant, wireframe ou plateforme.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeDesignDirectives.test.ts src/__tests__/codeDesignSpec.test.ts src/__tests__/codeFidelityGate.test.ts src/__tests__/codeColorMetrics.test.ts` : 56 pass / 0 fail.
- `find src/__tests__ -name 'code*.test.ts' -print | sort | xargs node --experimental-strip-types --test` : 655 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- `wc -l` : les nouveaux fichiers et fichiers touches du Module Code restent sous 600 lignes (`codeDesignDirectiveBlocks.ts` 595 lignes).

### Etat de satisfaction chantier

Pour WS10 local, le coeur du contrat est couvert : design-spec JSON, verification locale, taxonomie etendue, deltaE/Lab, et fin du contrat CSS web sur mobile/jeu. Le chantier n'est pas declare clos a 100 % tant que les templates couvrants n'ont pas tous ete enrichis par famille et relies aux futures generations longues.

## 2026-07-16 — Vague 4 / WS9 increment 62 — Audit rendu branche dans le chemin app

### Reprise et diagnostic confirme

- L'increment 60 avait pose le scoreur rendu et le collecteur CDP, mais l'app ne lancait pas encore l'audit apres dev-server.
- Le contrat `visual.score` existait, mais aucun score issu d'un vrai screenshot n'etait emis par le chemin applicatif.
- La recherche de references UX/UI (`codeDesignResearch.ts`) restait orpheline.
- Le test reel a expose un bug du helper CDP : sur Linux, il tentait de lancer le chemin Chrome Windows.

### Recherches et choix techniques

- Verification locale : bridge et Vite etaient vivants ; le bridge a ete relance avec `.venv/bin/python` existant pour charger la nouvelle route, sans installation ni modification de `.venv`.
- Choix retenu : endpoint bridge `/api/code/visual-audit` sous le perimetre autorise `/api/code/*`, qui enveloppe `visual_render_audit.py`.
- Choix retenu : client TS `codeVisualAuditClient.ts` qui score le rapport cote app et produit un evenement `visual.score` strict.
- Choix retenu : jugement vision optionnel dans le bridge via screenshots + Ollama VL, afin de ne charger le modele vision que lorsque l'app le demande.
- Choix retenu : recherche UX/UI branchee dans `prepareCodePlanningContext`, timeboxee et non bloquante, pour injecter les references avant generation.

### Modifications realisees

- `bridge_server.py` :
  - route `POST /api/code/visual-audit` ;
  - validation d'URL locale de dev-server pour eviter SSRF ;
  - execution du wrapper Python/CDP dans `output/code_visual_audits/` ;
  - enrichissement optionnel `vision` par screenshots + Ollama VL.
- `python-services/aurora_code/cdp_drive.mjs` :
  - detection Chrome/Chromium multi-plateforme ;
  - support du Chromium installe par Playwright dans `~/.cache/ms-playwright` ;
  - flags Linux headless `--no-sandbox` et `--disable-dev-shm-usage` ;
  - erreur explicite si aucun navigateur n'est disponible.
- `src/services/codeVisualAuditClient.ts` :
  - client bridge `/api/code/visual-audit` ;
  - scoring du rapport rendu via `scoreRenderedVisualAudit` ;
  - conversion pure en evenement `visual.score`.
- `src/services/codeStreamEvents.ts` :
  - `visual.score` transporte maintenant `source`, `viewports` et `failedChecks`.
- `src/views/codeViewGeneration.ts` :
  - apres `startDevServer`, lancement automatique de l'audit rendu reel ;
  - mise a jour du design report UI avec score, checks rates et penalites ;
  - resume final enrichi par le verdict rendu.
- `src/services/codePipelinePreparation.ts` et `codeDesignResearch.ts` :
  - recherche references UX/UI branchee avant planning pour les vrais projets visuels ;
  - base de references completee pour `data_dense_enterprise`, `ide_code_editor`, `os_shell`.
- Tests ajoutes/etendus :
  - `codeVisualAuditClient.test.ts`
  - `codePipelinePreparation.test.ts`
  - `codeStreamEvents.test.ts`.

### Avant / apres mesurable

- Avant : WS9 pouvait scorer un audit fourni par test, mais l'app ne demandait jamais ce rapport apres lancement dev-server.
- Apres : une generation avec dev-server lance `/api/code/visual-audit`, score le rendu reel et expose le resultat dans l'UI.
- Avant : `visual.score` ne portait pas la provenance du score.
- Apres : l'evenement indique `source: "render_audit"`, les viewports et les checks echoues.
- Avant : le CDP etait bloque sur Linux par un chemin Chrome Windows.
- Apres : le helper trouve le Chromium Playwright local et capture les trois breakpoints.

### Validation

- `node --experimental-strip-types --test src/__tests__/codePipelinePreparation.test.ts src/__tests__/codeVisualAuditClient.test.ts src/__tests__/codeVisualRenderAudit.test.ts src/__tests__/codeStreamEvents.test.ts src/__tests__/codeStreamRemoteState.test.ts` : 18 pass / 0 fail.
- `python3 -m py_compile bridge_server.py python-services/aurora_code/visual_render_audit.py` : vert.
- `node --check python-services/aurora_code/cdp_drive.mjs` : vert.
- Audit reel via bridge : `POST /api/code/visual-audit` sur `http://localhost:1420`, `waitMs=800`, `vision=false` -> `ok: true`, screenshots presents sur `390x844`, `834x1112`, `1440x900`, 24 echantillons pixel par viewport.
- `find src/__tests__ -name 'code*.test.ts' -print | sort | xargs node --experimental-strip-types --test` : 658 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).

### Etat de satisfaction chantier

WS9 est maintenant branche dans le chemin applicatif principal : rendu reel, contraste pixel, emission `visual.score`, endpoint bridge et references UX/UI sont relies. Reste a faire une campagne qualitative de generations longues avec vision active pour calibrer les seuils, mais le verrou "score visuel source-only" est leve.

## 2026-07-16 — Vague 5 / WS11 increment 63 — Viewer atelier et runtime navigateur

### Reprise et diagnostic confirme

- `BigLivePreviewFrame` gelait encore toute preview pendant generation via `shouldSkipLivePreview = isGenerating`.
- `CodeProjectPreview` savait inliner HTML/CSS/JS simples, mais pas executer un workspace React/TSX multi-fichiers sans dev-server.
- Le panneau livraison exposait une arborescence et un viewer code, mais pas l'atelier multi-panneaux exige par WS11.
- L'editeur principal utilisait encore Prism (`CodeBlock`) dans la vue Code principale, avec un fallback brut pour gros fichiers.
- Le Viewer 3D n'est pas touche : l'integration reste strictement dans les composants du Module Code.

### Recherches et choix techniques

- Verification locale des paquets installes : `esbuild-wasm@0.28.1`, CodeMirror 6 et `react-window@2.2.7`.
- Lecture des types `react-window` v2 : API actuelle `List`/`Grid`, pas l'ancienne `FixedSizeList`.
- Lecture de l'entree package locale `esbuild-wasm/esm/browser` : l'API browser expose bien `initialize`; le premier audit reel a prouve que l'import racine CDN ne l'expose pas.
- Choix retenu : runtime iframe autonome avec VFS JSON, import-map, worker module et `esbuild-wasm` browser API.
- Choix retenu : CodeMirror 6 pour les fichiers courants, puis `react-window` pour les fichiers gigantesques afin de conserver la reactivite.

### Modifications realisees

- `src/services/codeBrowserWorkspaceRuntime.ts` :
  - detection d'entree `src/main.tsx|jsx|ts|js` et fallback synthetique `App.tsx` ;
  - normalisation de chemins VFS et resolution d'imports locaux extensionless ;
  - generation d'un document iframe autonome avec import-map React/lucide/framer/three/vue/svelte ;
  - worker `esbuild-wasm` (`esm/browser`) qui bundle TS/TSX/JSX/CSS/JSON/SVG depuis la VFS ;
  - bridge runtime iframe vers parent : `console`, `error`, `perf`, source `aurora-code-runtime`.
- `src/components/CodeProjectPreview.tsx` :
  - preview web et `buildLivePreviewHtml` savent maintenant utiliser le runtime workspace quand aucun HTML statique n'est present.
- `src/services/codeLivePreviewPolicy.ts` et `src/views/codeViewPreviewPanel.tsx` :
  - fin du gel global pendant generation ;
  - pause live seulement si generation + projet WebGL/lourd ou taille > 150 KB.
- `src/components/CodeMirrorViewer.tsx` :
  - editeur read-only CodeMirror 6 ;
  - fallback virtualise `react-window` pour tres gros fichiers.
- `src/views/codeViewWorkspaceAtelier.tsx` et `codeViewDeliveryPanel.tsx` :
  - atelier dockable gauche/bas/masque ;
  - panneaux arborescence virtualisee, fichier, preview, logs, erreurs, perf, simulations, etats internes ;
  - la vue Code principale utilise CodeMirror.
- Dependances ajoutees :
  - `esbuild-wasm`, `@codemirror/state`, `@codemirror/view`, `@codemirror/lang-javascript`, `@codemirror/lang-html`, `@codemirror/lang-css`, `react-window`.

### Avant / apres mesurable

- Avant : un projet React multi-fichiers sans `index.html` n'etait pas executable dans l'iframe statique.
- Apres : un workspace `src/main.tsx` + `src/App.tsx` + CSS est compile en navigateur et execute sans dev-server.
- Avant : la preview live affichait le placeholder pendant toute generation.
- Apres : elle reste vivante pour projets legers et ne se met en pause que pour les projets lourds/WebGL.
- Avant : pas de panneau centralisant logs, erreurs, perf, simulations et etats internes.
- Apres : l'atelier expose ces panneaux sans remplacer le viewer compact.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeBrowserWorkspaceRuntime.test.ts` : 5 pass / 0 fail.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 663 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- Preuve runtime reelle : HTML genere dans `output/ws11_browser_runtime/index.html`, servi sur `http://127.0.0.1:4179`, audite via `visual_render_audit.py`.
  - viewports `390x844`, `834x1112`, `1440x900` ;
  - `headingCount=1`, `mediaCount=1`, `textNodeCount=5`, `bodyTextLength=69` ;
  - `consoleErrors=[]`, `exceptions=[]`, `failedRequests=[]` ;
  - contrastes pixel : H1 a `17.1`, paragraphe a `10.43`.
- `wc -l` : nouveaux fichiers sous 600 lignes (`codeBrowserWorkspaceRuntime.ts` 390, `CodeMirrorViewer.tsx` 204, `codeViewWorkspaceAtelier.tsx` 349).

### Etat de satisfaction chantier

WS11 a maintenant un socle fonctionnel : viewer compact conserve, runtime applicatif navigateur prouve, preview non gelee pour projets legers, atelier multi-panneaux et editeur CodeMirror/virtualisation. Restent a poursuivre dans WS12 le branchement du panneau simulations sur le labo multi-environnements reel, et a reduire progressivement la divergence historique avec les vues AuroraV1.

## 2026-07-16 — Vague 5 / WS12 increment 64 — Labo de simulation multi-environnements

### Reprise et diagnostic confirme

- La simulation UI historique restait essentiellement une variation de largeur (`desktop/tablet/mobile`) dans le viewer.
- Aucun endpoint `/api/code/*` ne permettait de lancer un labo multi-device/multi-browser depuis l'app.
- Les outils systeme disponibles au depart : Firefox systeme present mais inutilisable en headless avec profil existant ; Chromium Playwright en cache ; pas de `qemu-system-*`, pas de `renode`, pas de `adb/emulator/waydroid`, pas de WebKit headless CLI.
- Le prompt interdit de maquiller mobile/embarque/OS par un simple redimensionnement ; les environnements absents doivent etre declares indisponibles.

### Recherches et choix techniques

- Verification locale `command -v` pour Podman/QEMU/Renode/Chromium/Firefox/WebKit/Android/Waydroid.
- Ajout de `playwright` en devDependency et telechargement des navigateurs Playwright en cache utilisateur (`chromium`, `firefox`, `webkit`), sans installation dans `.venv`.
- Playwright a signale des dependances systeme manquantes pour WebKit (`libevent`, `libavif`, `libwoff`) ; aucune commande `sudo install-deps` n'a ete lancee automatiquement.
- Choix retenu : reutiliser CDP pour les profils Chromium avances (DPR/touch/UA/network/CPU throttling + metriques Performance) et Playwright pour la matrice multi-browser.
- Choix retenu : rapport `aurora.code.simulation-lab/1` avec statuts explicites `executed`, `unavailable`, `deferred`, au lieu de cacher les trous.

### Modifications realisees

- `python-services/aurora_code/cdp_drive.mjs` :
  - nouveau mode `simulate` ;
  - profils Chromium desktop, mobile 4G touch, tablet slow-3G touch ;
  - `Emulation.setDeviceMetricsOverride`, `setTouchEmulationEnabled`, `Network.emulateNetworkConditions`, `Emulation.setCPUThrottlingRate`, `Performance.getMetrics`.
- `python-services/aurora_code/playwright_simulate.mjs` :
  - matrice Playwright Chromium/Firefox/WebKit ;
  - screenshots, compteurs DOM et erreurs console par navigateur.
- `python-services/aurora_code/simulation_lab.py` :
  - orchestration CDP + Playwright ;
  - probes WebKit CLI, Android/Waydroid, Renode, QEMU ;
  - consoles marquees `deferred` avec justification technique.
- `bridge_server.py` :
  - route `POST /api/code/simulation-lab` sous perimetre `/api/code/*` ;
  - URLs limitees au local comme WS9, timeouts bornes.
- `src/services/codeSimulationLab.ts` :
  - schema/type guard/client bridge/summarizer.
- `src/views/codeViewWorkspaceAtelier.tsx` :
  - panneau Simu branche au labo quand un dev-server local est actif ;
  - affiche executions reelles, indisponibles et justifications.
- Tests :
  - `codeSimulationLab.test.ts`.

### Avant / apres mesurable

- Avant : la "simulation mobile" ne changeait que la largeur.
- Apres : le profil mobile Chromium utilise DPR 3, touch, UA Android, CPU throttle 4x et reseau 4G via CDP.
- Avant : aucun signal sur WebKit/Firefox/Android/Renode/QEMU.
- Apres : Playwright lance Chromium et Firefox quand possible ; WebKit, Android, Renode et QEMU sont explicitement indisponibles avec raison.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeSimulationLab.test.ts src/__tests__/codeBrowserWorkspaceRuntime.test.ts` : 8 pass / 0 fail.
- `node --check python-services/aurora_code/cdp_drive.mjs python-services/aurora_code/playwright_simulate.mjs` : vert.
- `python3 -m py_compile bridge_server.py python-services/aurora_code/simulation_lab.py python-services/aurora_code/visual_render_audit.py` : vert.
- `node --experimental-strip-types --test 'src/__tests__/code*.test.ts'` : 666 pass / 0 fail.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- Preuve runtime `output/ws12_simulation_lab_proof3` sur `http://127.0.0.1:4179` :
  - CDP Chromium desktop 1440x900 execute, `headingCount=1`, `mediaCount=1`, erreurs vides ;
  - CDP Chromium Pixel 8 touch 4G execute, DPR 3, CPU x4, reseau 4G, erreurs vides ;
  - CDP Chromium tablet slow-3G touch execute, DPR 2, CPU x6, reseau slow-3G ; le rapport expose que le bundle ne charge pas completement dans la fenetre courte (`headingCount=0`), ce qui est un signal de perf reel ;
  - Playwright Chromium execute, Playwright Firefox execute, `headingCount=1`, erreurs vides ;
  - Playwright WebKit indisponible faute de dependances systeme ; Android/Renode/QEMU indisponibles car outils absents.

### Etat de satisfaction chantier

WS12 n'est plus une largeur cosmetique : le labo execute de vrais navigateurs avec profils et throttling, et documente les environnements non disponibles sans les simuler faussement. Le DoD complet mobile/ESP32/Raspberry/OS boot reste conditionne a l'installation systeme de Waydroid/AVD, Renode et QEMU, explicitement absents de cette machine pendant l'increment.

## 2026-07-16 — Vague 4 / WS14 increment 65 — Boucle d'auto-outillage isolee

### Reprise et diagnostic confirme

- La boucle de correction WS13 detectait deja cause, localite, historique et plateau, mais elle ne pouvait pas acquerir puis evaluer un outil externe.
- Le prompt impose que les installs d'auto-amelioration n'aillent jamais dans `application/.venv`.
- Le besoin n'est pas seulement "installer une lib" : il faut mesurer A/B contre la reference, conserver si meilleur, et retirer si inutile.

### Recherches et choix techniques

- Point d'insertion retenu : plateau dans `runValidationAndCorrectionLoop`, apres recherche web et avant injection du diagnostic de cause racine.
- Isolation retenue : venvs dedies sous `~/.local/share/auroraia/venvs/code-auto-tools`, avec allow-list stricte.
- Cas de preuve retenu : `python-slugify==8.0.4` sur PyPI, car il montre un gain mesurable sur translitteration Unicode sans dependance lourde.
- Resolveur ajoute cote TS pour npm, PyPI, crates.io et Maven ; l'installation automatique reste allow-listee pour eviter une acquisition arbitraire.

### Modifications realisees

- `src/services/codeToolingLoop.ts` :
  - registre ReAct (`run_shell`, `run_tests`, `search_pkg`, `install_dep`, `add_model`) ;
  - resolveur multi-registres avec URLs allow-list ;
  - detection de plateau et selection de candidat PyPI pour blocage Python slug/Unicode ;
  - client `POST /api/code/tooling-eval`, type guard, resume et format d'injection correction.
- `python-services/aurora_code/tooling_eval.py` :
  - creation de venv isole ;
  - installation pip allow-listee ;
  - evaluation baseline vs outil ;
  - conservation du venv avec marqueur si gain reel, suppression si gain insuffisant.
- `bridge_server.py` :
  - route `POST /api/code/tooling-eval` sous namespace Code.
- `src/services/codeValidationCorrectionLoop.ts` :
  - appel WS14 non bloquant lorsque les trois derniers scores plafonnent.
- Tests :
  - `codeToolingLoop.test.ts`.

### Avant / apres mesurable

- Avant : un plateau relancait surtout recherche, reasoning et regeneration.
- Apres : un plateau peut declencher une acquisition outillee mesuree en A/B.
- Avant : aucun contrat n'empechait une install d'auto-outillage dans `.venv`.
- Apres : le chemin WS14 expose explicitement `appVenvInstallForbidden=true` et n'ecrit que dans le venv dedie.

### Validation

- `node --experimental-strip-types --test src/__tests__/codeToolingLoop.test.ts src/__tests__/codeValidationCorrectionLoop.test.ts src/__tests__/codeAutoCorrection.test.ts` : 52 pass / 0 fail.
- `python3 -m py_compile python-services/aurora_code/tooling_eval.py bridge_server.py` : vert.
- `npm run build` : vert (avertissements Vite cowork dynamiques existants, hors perimetre Code).
- Preuve reelle `output/ws14_tooling_eval_proof/report.json` :
  - candidat utile `proof-python-slugify-kept` : baseline 80, outil 100, gain +20, venv conserve sous `~/.local/share/auroraia/venvs/code-auto-tools` ;
  - candidat inutile `proof-python-slugify-removed` : baseline 100, outil 100, gain 0, venv supprime ;
  - `application/.venv` contient 0 marqueur `aurora_tooling_eval.json`.

### Etat de satisfaction chantier

WS14 dispose maintenant d'un chemin reel d'auto-outillage : detection de plateau, acquisition PyPI en venv isole, mesure A/B, conservation ou retrait propre. L'extension vers des outils plus lourds ou des modeles reste volontairement derriere allow-list et quotas pour eviter l'accumulation ou le swap VRAM.

## 2026-07-16 — Vague 5 / WS15 increment 66 — Assets inter-modules reels

### Reprise et diagnostic confirme

- `source.unsplash.com` etait encore une dependance morte dans les chemins Code, l'image etait souvent inline/base64, et la generation 3D retombait sur des recettes recopiees au lieu de consommer le pipeline existant.
- Le bridge expose reellement Image/ComfyUI, pipeline 3D, voix/TTS, recherche/extraction web et vision. Il n'expose aucun service musique, SFX ou foley.
- L'ancienne boucle Python et plusieurs post-traitements TypeScript conservaient des chemins morts ou des transformations redondantes qui masquaient le chemin agentique reel.

### Recherches et choix techniques

- Les contrats HTTP du bridge et les artefacts reels ont ete pris comme source de verite; aucun module Image, 3D, Voix ou Vision n'a ete modifie.
- Pillow, deja present dans l'environnement applicatif et verifie avec le codec AVIF, produit AVIF/WebP et les variantes 480/800/1280. Les assets binaires restent des fichiers, jamais des data URLs massives.
- Le GLB vient du pipeline `aurora-3d`; son score mesh et un rendu Playwright du viewer servent de preuve independante. La voix vient du TTS du bridge.
- Le RAG inter-module exige fetch de page, segmentation, embeddings et reranking. Une simple liste de snippets issus du prompt n'est plus acceptee comme recherche.
- Musique/SFX sont differes explicitement : creer silencieusement un faux service aurait viole le cadrage du prompt et la contrainte de perimetre.

### Modifications realisees

- `src/services/codeInterModuleAssets.ts` : contrat `AssetBundle`, client bridge, validation et orchestration typee.
- `src/services/codeInterModuleAssetIntegration.ts` et `codeRuntimeDependencies.ts` : integration des chemins d'assets, dependances de runtime et export autonome.
- `python-services/aurora_code/intermodule_assets.py` : orchestration Image/3D/TTS, conversions, stockage borne et manifeste.
- `intermodule_rag.py` et `intermodule_asset_reuse.py` : recherche reelle et reutilisation controlee par provenance.
- `bridge_agentic_stream.py` et les routes `/api/code/*` : chemin agentique consolide et appels inter-modules serialises pour eviter la contention VRAM.
- Suppression physique des anciens patchers/elevateurs sans valeur, des chemins Unsplash et de la directive de plagiat.
- Tests TypeScript/Python ajoutes pour schema, refus des payloads invalides, traversal, export ZIP, assets telechargeables, RAG et non-regression agentique.

### Avant / apres mesurable

- Avant : image inline ou URL fragile, 3D synthetique, aucun bundle exportable, voix absente.
- Apres : bundle reel avec AVIF/WebP responsives, GLB du pipeline 3D et WAV TTS; dix fichiers sont embarques dans un ZIP autonome, sans URL bridge residuelle.
- Image 1280x768 : 35 482 octets en AVIF. GLB : 10 014 192 octets. WAV : 535 244 octets.
- Mesh : score 81,4/100, 149 996 faces, 86 795 sommets, aucun axe echoue et aucun retry recommande.

### Demonstration reproductible

```bash
node --experimental-strip-types scripts/code_harness/ws15_asset_export_proof.ts \
  ws15-live-selected-v6 http://127.0.0.1:3001 \
  > output/ws15_inter_module_proof/v6_selected_zip_export_report.json
jq . output/ws15_inter_module_proof/v6_selected_zip_export_report.json
sha256sum -c output/ws15_inter_module_proof/v6_selected_sha256.txt
```

Resultat attendu : `ok=true`, dix entrees d'archive, `bridgeUrlsRemaining=false`, huit controles binaires `sourceMatch=true` et des SHA-256 valides.

### Etat de satisfaction chantier

WS15 satisfait le DoD pour image, 3D, voix, optimisation, integration et export. Musique/SFX restent une dette explicite, car le seul service audio disponible est TTS; aucun asset fictif n'est revendique.

## 2026-07-16 — Vague 1 / WS1 increments 67 a 69 — Limite stricte sous 400 lignes

### Reprise et diagnostic confirme

- Le seuil initial de 600 lignes avait ete atteint, mais plusieurs facades et orchestrateurs restaient trop denses pour une maintenance rigoureuse.
- Les plus gros points etaient les orchestrateurs TypeScript, le store de streaming, les vues Code, le runtime Python et le pilote CDP.

### Choix et implementation

- Extraction par responsabilite et conservation des API publiques : contrats/types, callbacks de generation, persistance workspace, panneaux atelier, commandes CDP, etat/CLI de boucle Python.
- Les extractions ne changent pas les contrats publics; les tests structuraux verifient imports, reexports et absence des anciens modules morts.
- Seuil automatise strict : toute unite de production Code doit faire moins de 400 lignes.

### Avant / apres mesurable

- Avant la refonte : `codeOrchestrator.ts` 4 863 lignes, `codeIntent.ts` 3 221 lignes, plusieurs vues/stores au-dela de 600.
- Apres : environ 39 000 lignes de production Code; maximum 398 lignes (`CodeView.tsx`, `codeDesignReferenceHtml.ts`, `codeAutoCorrection.ts`); zero unite a 400 lignes ou plus.
- La decomposition ajoute des tests de structure et retire physiquement les implementations sans import.

### Demonstration reproductible

```bash
node --experimental-strip-types --test src/__tests__/codeModuleStructure.test.ts
find src python-services/aurora_code -type f \
  \( -name '*code*.ts' -o -name '*Code*.tsx' -o -path 'python-services/aurora_code/*' \) \
  -not -path '*/__tests__/*' -print0 | xargs -0 wc -l | sort -nr | head
```

Resultat attendu : test structurel vert et aucune unite de production Code a 400 lignes ou plus.

### Etat de satisfaction chantier

WS1 depasse le DoD d'origine (<600) avec une borne stricte <400, testee automatiquement. Les gros fichiers des autres modules ne sont pas modifies, conformement au perimetre.

## 2026-07-16 — Vague 5 / WS12 increments 70 et 71 — Environnements reels definitifs

### Reprise et diagnostic corrige

- Le premier increment WS12 etait honnete mais incomplet : Chromium/Firefox etaient executes, tandis que WebKit, Android, Renode et QEMU etaient indisponibles.
- La reprise a installe les outils au niveau utilisateur/systeme autorise, sans toucher `application/.venv`, puis a remplace chaque probe par une execution verifiable.
- Une premiere preuve Android ne couvrait qu'un telephone; le DoD exige explicitement telephone et tablette. Un second profil AVD reel a donc ete ajoute.

### Recherches et choix techniques

- Playwright officiel pour Chromium, Firefox et WebKit; CDP pour DPR, tactile, UA, throttling CPU/reseau et metriques fines.
- Android Emulator/ADB pour installer et lancer l'APK/PWA sur Pixel 6 et Pixel Tablet. Une interaction UI et un marqueur dans le contenu prouvent l'execution, au-dela du screenshot.
- Renode en process externe MIT pour un firmware Arduino Nano 33 BLE et son marqueur serie.
- QEMU en process externe GPL pour Raspberry Pi 2B bare-metal et image x86 bootable; les heartbeats deterministes servent d'oracles.
- iOS reste indisponible sous Linux faute de toolchain Apple; consoles differees avec matrice de faisabilite, comme le prompt l'autorise.

### Modifications realisees

- `simulation_android.py`, `simulation_android_app.py`, `simulation_android_profiles.py` : profils AVD, application de preuve, installation, lancement et interaction.
- `simulation_embedded.py` : build/run Renode et images QEMU avec marqueurs attendus.
- `simulation_tooling.py` : decouverte multiplateforme idempotente et chemins d'outils.
- `simulation_lab.py` : onze stages reels, timeout/cleanup et stage consoles honnetement differe.
- Contrats TypeScript et tests Python/TypeScript etendus au telephone et a la tablette.

### Avant / apres mesurable

- Avant reprise : 5 executions reelles, 5 environnements indisponibles et consoles differees.
- Apres : **11 stages `executed` avec `realExecution=true` sur 12**, aucun stage indisponible/degrade/detecte; seul le stage consoles est differe.
- Web : Chromium CDP sur trois profils + Chromium/Firefox/WebKit reels.
- Mobile : Pixel 6 et Pixel Tablet executent la meme application et une interaction verifiee.
- Embarque/OS : `0xA6120042`, `AURORA_WS12_RASPBERRY_HEARTBEAT`, `AURORA_WS12_OS_HEARTBEAT`.

### Demonstration reproductible

```bash
mkdir -p output/ws12_simulation_definitive
.venv/bin/python python-services/aurora_code/simulation_lab.py \
  http://127.0.0.1:1431 output/ws12_simulation_definitive 2500 \
  > output/ws12_simulation_definitive/report.json
jq '[.stages[] | select(.status == "executed" and .realExecution == true)] | length' \
  output/ws12_simulation_definitive/report.json
```

Resultat attendu : `11`; les captures Android et les logs Renode/QEMU sont sous le dossier de sortie choisi.

### Etat de satisfaction chantier

WS12 satisfait les criteres techniques executables sur cet hote. Les consoles sont differees avec justification; iOS est une limite de plateforme Linux, jamais remplacee par une largeur cosmetique.

## 2026-07-16 — Relecture depot entier et correction visuelle finale

### Analyse globale

- 1 652 fichiers suivis, dont 539 Python. Les fichiers hors Code les plus volumineux restent `bridge_server.py`, `ModelView.tsx` et `CoworkOverlay.tsx`; ils ne sont pas refactorises car le prompt interdit de modifier les autres modules.
- `npm ls --depth=0` ne remonte aucun probleme; `npm audit --json` donne 0 vulnerabilite sur 413 dependances; la metadata Cargo est valide.
- Tous les Python suivis sont parsables par `ast`. `pip check` ne remonte que les extras externes image `facexlib`, `gfpgan` et `tb-nightly`, absents avant la reprise et volontairement non installes dans `.venv`.
- Le typecheck global expose seulement des erreurs hors Code dans Cowork, stockage temporaire, Flux Kontext, Pixel Art et AuroraCoworkView. Le perimetre Code n'apparait dans aucune erreur.
- Le sandbox WS7 echoue ferme lorsque Podman rootless est bloque par AppArmor/user namespaces. Cette limite hote est documentee; aucun test ne pretend qu'un conteneur a tourne quand ce n'est pas le cas.

### Corrections UI issues de l'inspection

- Aurora V3 route maintenant vers `AuroraV3CodeView` et applique une couche visuelle scopee au Module Code.
- La grille principale garde deux colonnes utiles a 1024 px; le hero V4 et les actions de livraison s'adaptent a 390 px.
- Les recommandations connecteur peuvent revenir a la ligne; les enfants de `AnimatePresence` ont des cles stables, supprimant le warning React observe par le probe.
- `final_visual_proof.mjs` injecte un projet dashboard reel dans les stores V1/V3/V4, attend le `postMessage` emis par le code execute dans l'iframe, mesure les debordements visibles et masques, les boutons tronques et capture les erreurs console/page/reseau.
- `final_screenshot_pixel_audit.mjs` relit les PNG dans Chromium/Canvas et controle dimensions, entropie et dispersion des canaux afin d'exclure les rendus vides.

### Preuve visuelle reproductible

```bash
AURORA_URL=http://127.0.0.1:1431 \
  node scripts/code_harness/final_visual_proof.mjs
jq '{ok, failures, profiles: [.profiles[] | {id, previewExecution, horizontalOverflowPx}]}' \
  output/final_code_refonte_validation/screens/report.json
```

Resultat observe : sept profils, `ok=true`, `failures=[]`, iframe `verified`, 0 px de debordement, aucune erreur console/page/reseau et aucun warning React de cle. Les PNG desktop/tablette/mobile sont dans le meme dossier.

### Limites globales laissees ouvertes

- Le shell global `index.html` autorise V1/V3 alors que le registre expose V4. Le harnais direct `visual_shell.html` isole les skins pour la preuve; corriger le shell depasserait le perimetre Module Code.
- Podman rootless reste bloque par la configuration de l'hote. Les politiques fail-closed et tests d'isolation restent actives en attendant un hote equipe.
- Les extras Python du pipeline image externe ne sont pas resolus dans `.venv`, conformement a l'interdiction explicite du prompt.
- Musique/SFX restent sans service bridge. WS15 ne fabrique pas de resultat fictif.

## 2026-07-16 — Auto-correction de la campagne lourde finale

### Premier passage et signaux conserves

- Le lanceur `final_heavy_validation.sh` a execute toute sa matrice jusqu'aux screenshots, meme apres un echec, afin de ne pas perdre les signaux suivants.
- Suite Code : verte; suite Python Code : verte; preuves critiques agentiques/extreme/sandbox/visuelles/simulation : vertes; build Vite et `cargo check` : verts.
- Suite Node du depot : **4 545 tests**, **4 542 verts**, **3 echecs**, tous dans `src/__tests__/coworkExtract.test.ts` : un 502 de l'endpoint Cowork et deux timeouts vision de 85 s. Aucun echec Code.
- WS15 : huit assets/variantes relus via le bridge, export ZIP autonome, huit SHA-256 identiques.
- UI : sept profils V1/V3/V4 verts, iframe executee, 0 px de debordement, aucun bouton tronque ou controle hors viewport, aucune erreur runtime. Les sept PNG ont les dimensions exactes et sont non vides selon l'audit pixel.
- WS12 : trois navigateurs, telephone, tablette et deux boots QEMU verts; Renode a subi un timeout transitoire alors que le meme script rejoue seul a termine en 1,6 s avec `0xA6120042`.

### Corrections appliquees avant le run definitif

- `simulation_embedded.py` utilise maintenant `run_until_marker` pour Renode : le runner observe le heartbeat reel puis termine tout le groupe de processus, sans dependre de la fermeture interactive du moniteur.
- Un test Python verifie le marqueur transmis, l'execution reelle et la duree rapportee.
- `final_node_test_scope_check.mjs` parse le resume Node et n'autorise comme dette que `coworkExtract.test.ts`; tout autre fichier, test annule ou suite incomplete fait echouer la campagne.
- Le rapport JSON final recoit son booleen `ok` explicitement, supprimant une ambiguite de precedence `jq` decouverte au premier passage.

### Campagne definitive reproductible

```bash
./scripts/code_harness/final_heavy_validation.sh
jq '{ok, steps: (.steps | length), requiredFailures, knownDebts}' \
  output/final_code_refonte_validation/heavy_final/final-report.json
(cd output/final_code_refonte_validation/heavy_final && sha256sum -c SHA256SUMS)
```

Le rapport n'est vert que si tous les controles requis passent. Les erreurs globales Cowork, le typecheck hors Code, les extras image et la restriction Podman restent visibles dans `knownDebts`; ils ne peuvent pas etre reclasses silencieusement en succes.

## 2026-08-09 — Le codeur ne connaissait pas la barre de qualite

### Reprise et diagnostic

Reprise sans faire confiance aux auto-declarations : un scanner d'orphelins a ete
ecrit AVANT toute modification (`scripts/code_harness/orphan_scan.mjs`), qui
construit le vrai graphe d'imports depuis les points d'entree de production
(`codeStreamStore.ts`, `codeOrchestrator.ts`, `CodeView.tsx`) et marque ce qui
n'est atteignable par personne. Deux niveaux : module et symbole exporte.

Le scan a remonte un symbole qui explique la plainte de fond « les generations
restent basiques » : `getSystemPromptForRole` n'a **aucun appelant de
production**. Or c'est le seul appelant restant de `buildCodeurSystemPrompt`.
Quand WS3 est devenu le moteur de generation (un appel modele par fichier),
l'ancien appel unique a disparu et avec lui tout le prompt du CODEUR.

Verification directe du prompt reellement envoye au modele pendant la
generation (`codeGenerationActionProducer.ts:136-146`) : **huit lignes de
plomberie**, « produis des actions JSON pour le VFS ». Rien d'autre. Etaient donc
absents du prompt de generation : contrat design, verrouillage sujet/marque,
contrat de livraison, contrat d'interactivite v89b, contrat d'ingenierie expert,
reference design premium, directives d'archetype.

Deux consequences directes, et non theoriques :
- le contrat `PLACEHOLDER_SUBJECT_IMG` (assets reels deja telecharges) vivait
  dans le verrouillage sujet : le codeur n'en entendait jamais parler ;
- la recette shader Fresnel, que la gate de fidelite **rejette si absente**,
  vivait au meme endroit : la gate exigeait une regle jamais transmise.

### Recherches et choix

Mesure avant de decider. Le prompt codeur complet fait **42 411 caracteres
(~10 600 tokens)** sur un brief de marque. WS3 appelant le modele une fois par
fichier, le recabler tel quel ajouterait ~95 000 tokens de prompt systeme sur un
projet de neuf fichiers, avec `num_ctx = 24 576` et un modele de 18,6 Go sur un
GPU de 16 Go : swap garanti, donc crash. Le recablage naif etait donc exclu.

Choix retenu : un contrat **compact, cible sur le fichier en cours et borne**,
dans un module dedie `codeExecutorQualityContract.ts`. Deux regimes de budget,
parce que le cout se paie a chaque appel :
- fichier visuel : 12 000 caracteres, assez pour le verrouillage marque COMPLET
  (il porte les deux contrats que les gates verifient ensuite) plus l'archetype
  et l'interactivite ;
- fichier de configuration : 1 200 caracteres. Un `tsconfig.json` n'a que faire
  d'une palette de marque. `vite.config.ts` et consorts sont reconnus comme
  configuration malgre leur extension `.ts`.

La troncature se fait sur une frontiere de ligne : couper au milieu d'une regle
la rend fausse.

### Modifications realisees

- `src/services/codeExecutorQualityContract.ts` (nouveau) — contrat compact :
  verrouillage sujet/marque, contrat de livraison (fichiers d'entree obligatoires
  par type de projet), barre visuelle condensee, bloc d'archetype, contrat
  d'interactivite. Bornage et priorisation explicites.
- `src/services/codeGenerationActionProducer.ts` — `intent` optionnel ajoute aux
  options et aux messages ; le contrat est injecte dans le prompt SYSTEME.
  Sans `intent`, le comportement precedent est conserve a l'identique.
- `src/services/codeAgenticGenerationPhase.ts` — transmet l'`intent` du run.
- `src/services/codeDesignDirectives.ts` — correction d'un vrai bug de
  robustesse : `ap?.styleHints.some(...)` levait un `TypeError` des qu'un
  `assetPlan` existait sans `styleHints`, ce qui faisait tomber toute la
  detection d'archetype. L'optional chaining porte desormais sur le tableau.
- `src/__tests__/codeExecutorQualityContract.test.ts` (nouveau) — 10 tests.
- `scripts/code_harness/orphan_scan.mjs` (nouveau) — garde anti-orphelin.

### Avant-apres mesurable

Run reel de reference AVANT correction, sur un brief complexe de marque
(`qwen3-coder:30b`, machine reelle, 16 Go de VRAM) :

| Mesure | Avant |
|---|---|
| Verdict | **echec** (`ok:false`, `phaseFinal:"error"`) |
| Duree | 464 s |
| Fichiers produits | 14 |
| `index.html` sur un `static_web` | **absent** |
| Score final | 0 |
| Erreur fatale | `action_protocol_invalid:json_payload_invalid` |

Le run a brule une passe de regeneration complete pour decouvrir apres coup
l'absence de page d'entree — information que le contrat de livraison lui aurait
donnee d'emblee.

Cout du contrat injecte, mesure (brief de marque, `static_web`) :

| Cible | Avant | Apres |
|---|---|---|
| Prompt codeur complet (recablage naif) | 42 411 car. (~10 600 tok) | — |
| `index.html` | 0 car. | 12 000 car. (~3 000 tok) |
| `src/main.ts` | 0 car. | 11 996 car. |
| `tsconfig.json` | 0 car. | 509 car. (~127 tok) |
| `vite.config.ts` (SPA) | 0 car. | 526 car. |
| Projet non visuel (`main.py`) | 0 car. | 206 car. |

Soit 3,5x moins cher que le recablage naif sur les fichiers qui en ont besoin,
et 23x moins cher sur les fichiers de configuration.

Tests : **743 verts avant, 753 verts apres, 0 echec.** Typecheck : 31
diagnostics, tous hors perimetre Code (cowork, stockage temporaire, pixel art),
soit exactement la dette deja allow-listee par `final_tsc_scope_check.mjs` ;
**aucun diagnostic Code**.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/code*.test.ts'
node scripts/code_harness/orphan_scan.mjs --json output/code/audit_v90/orphan_scan_before.json
npx tsc --noEmit 2>&1 | grep -E "error TS" | sed -E 's/\(.*//' | sort | uniq -c
```

Preuve du run de reference avant correction :
`application/output/code/audit_v90/cli_baseline/_harness_summary.json`
(`ok:false`, `fileCount:14`, aucun `index.html` dans `files`).

### Etat de satisfaction chantier

Le codeur recoit desormais la barre de qualite, le verrouillage de marque et le
contrat de livraison, sans faire exploser le contexte. Reste ouvert et assume :
`buildCodeurSystemPrompt` et `getSystemPromptForRole` demeurent orphelins — le
contrat compact les remplace dans le chemin WS3 ; les supprimer ou les reduire a
la version compacte est un chantier de nettoyage distinct, non traite ici pour
ne pas melanger correction fonctionnelle et suppression de code.

## 2026-08-09 — Le classifieur LLM pouvait transformer une landing page en IDE

### Reprise et diagnostic

Decouvert en observant un run reel, pas en relisant du code. Le meme prompt
(« landing page premium pour la marque Mercedes-Benz, hero anime, section specs,
formulaire de contact, responsive ») a donne **deux resultats differents sur deux
runs consecutifs** :

- run CLI : aucune ligne « Classification semantique » (classifieur en timeout),
  `projectType = static_web` — correct ;
- run bridge : `Classification semantique: ide (LLM)`, `projectType = ide`.

`runIntentPhase` (`codePipelinePhases.ts:74`) acceptait le verdict du modele des
que `source === 'semantic_model'`, **sans le moindre controle**, et remplacait
l heuristique qui avait pourtant repondu juste.

L impact n est pas cosmetique : le `projectType` pilote l archetype design, le
contrat de livraison (page d entree obligatoire ou non), les directives, les
commandes dev/build et les templates. Le run classe `ide` a livre
`src/workspace/fileTree.jsx`, `src/workspace/TerminalPanel.jsx`,
`src/components/CommandPalette.jsx` et `src/hooks/useWorkspaceState.js` : **un
editeur de code, pas une page Mercedes-Benz**.

C est aussi une rupture de conformite pure : demande identique, livraison
differente d un run a l autre, sur n importe quel canal.

### Recherches et choix

Le classifieur semantique n est pas a jeter : il existe pour couvrir les types
exotiques que les regex ne voient pas (`compiler`, `os_kernel`, `embedded_*`,
`distributed_system`). Le desactiver ferait perdre cette couverture.

Regle retenue, dans un module dedie `codeSemanticIntentGuard.ts` : le modele
garde la main quand il APPORTE de l information, il la perd quand il CONTREDIT
une heuristique confiante sans le moindre appui lexical.

- meme type -> accepte ;
- heuristique muette (`unknown`, `script`) -> accepte, le modele informe ;
- meme famille (`static_web` -> `spa_react`) -> accepte, c est un affinage ;
- changement de famille -> exige qu au moins un mot du prompt aille dans le sens
  du verdict, sinon l heuristique est conservee.

Les familles et leurs indices lexicaux (FR + EN) sont explicites et testes. Le
but n est pas de re-implementer la classification, seulement d exiger un indice.

### Modifications realisees

- `src/services/codeSemanticIntentGuard.ts` (nouveau) — familles de projet et
  `decideSemanticIntentOverride`, avec une raison explicite par decision.
- `src/services/codePipelinePhases.ts` — le verdict semantique passe par le
  garde-fou ; un rejet est TRACE dans la phase
  (« Classification semantique ecartee (... non corrobore) -> ... »), jamais
  avale en silence.
- `src/__tests__/codeSemanticIntentGuard.test.ts` (nouveau) — 8 tests, dont le
  cas reel `static_web` -> `ide` rejete, et les types exotiques corrobores qui
  doivent continuer a passer.

### Avant-apres mesurable

| Situation | Avant | Apres |
|---|---|---|
| `static_web` + modele dit `ide`, prompt sans indice IDE | override accepte -> IDE livre | **rejete**, `static_web` conserve |
| `static_web` + prompt « IDE, file tree, terminal integre » | accepte | accepte (inchange) |
| `unknown` + modele dit `compiler` | accepte | accepte (inchange) |
| `static_web` -> `spa_react` | accepte | accepte (inchange) |
| Determinisme sur le prompt Mercedes | 2 verdicts sur 2 runs | verdict stable |

Preuve du dommage, run reel avant correction :
`application/output/code/audit_v90/bridge_runner/_stream.ndjson` — les evenements
`file.written` listent `fileTree.jsx`, `TerminalPanel.jsx`, `CommandPalette.jsx`
pour une demande de landing page de marque.

Tests : **753 -> 761 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeSemanticIntentGuard.test.ts'
python3 -c "
import json
for l in open('output/code/audit_v90/bridge_runner/_stream.ndjson'):
    e=json.loads(l)
    if e['kind']=='file.written' and 'content' in e: print(e['path'])
"
```

### Etat de satisfaction chantier

Le garde-fou est volontairement permissif : il ne bloque QUE le changement de
famille sans aucun indice. Reste assume : si le modele hallucine DANS la bonne
famille (par exemple `spa_vue` au lieu de `spa_react`), rien ne l arrete — mais
le cout d une telle erreur est faible, la famille pilotant l essentiel des
contrats.

## 2026-08-09 — Une reponse modele mal formee tuait tout le projet

### Reprise et diagnostic

Deux runs reels consecutifs sur un brief complexe sont morts exactement de la
meme facon, APRES avoir deja ecrit des fichiers valides :

```
Erreur fatale du pipeline: Echec de l executor agentique WS3:
  action_producer_failed:action_protocol_invalid:json_payload_invalid
```

Run CLI : 14 fichiers ecrits, puis run perdu. Run bridge : 8 fichiers ecrits,
puis run perdu. Une seule reponse modele mal formee suffisait a annuler tout le
travail deja produit.

Lecture du parseur (`codeGenerationActionProtocol.ts`) : `findFirstJsonValue`
renvoie `null` quand la charge n est jamais refermee. Donc `json_payload_invalid`
ne signifie PAS « tronque » : il signifie qu une charge **equilibree** a ete
refusee par `JSON.parse`. La cause dominante avec un modele local qui doit
emettre un fichier de code entier dans une chaine JSON est connue : de VRAIS
retours a la ligne inseres dans `content` au lieu de `\n`. Le scanner ne le voit
pas — un saut de ligne brut ne casse pas le suivi des guillemets — donc il rend
une charge d apparence valide que `JSON.parse` rejette.

Le repli existant (`extractRawFileContent`) ne pouvait pas sauver ce cas : il
REFUSE explicitement tout texte contenant `"kind":"write_file"` pour ne pas
ecrire un payload JSON comme contenu de fichier. Le run n avait donc aucune
issue.

### Recherches et choix

Deux modes de corruption distincts, tous deux reparables :

1. charge equilibree refusee par `JSON.parse` -> re-echapper les caracteres de
   controle bruts **a l interieur des chaines uniquement** ; hors chaine ils sont
   de l espacement legal et doivent rester intacts ;
2. charge jamais refermee (limite de tokens atteinte au milieu du contenu) ->
   recuperer le `write_file` partiel. Un fichier incomplet vaut mieux qu un
   projet vide : la boucle de correction sait completer un fichier, elle ne sait
   rien faire d un run perdu.

Garde-fou sur le point 2 : un fragment de moins de 40 caracteres n est pas un
fichier, on laisse le retry faire son travail plutot que d ecrire un moignon.

Les deux reparations ne s appliquent QUE sur un chemin deja en echec : elles ne
peuvent pas degrader une charge utile valide. Un test le verrouille explicitement.

### Modifications realisees

- `src/services/codeGenerationActionSalvage.ts` (nouveau) —
  `repairJsonControlCharacters` et `salvageTruncatedWriteFile`, avec un decodeur
  d echappements tolerant a une troncature en plein `\u`.
- `src/services/codeGenerationActionProtocol.ts` — les deux chemins de
  recuperation sont branches dans `parseCodeGenerationActions`, apres l echec du
  parse normal et jamais avant.
- `src/__tests__/codeGenerationActionSalvage.test.ts` (nouveau) — 12 tests.

### Avant-apres mesurable

| Charge utile modele | Avant | Apres |
|---|---|---|
| `content` avec de vrais sauts de ligne | `json_payload_invalid` -> **run perdu** | fichier ecrit correctement |
| charge jamais refermee (tokens epuises) | `json_payload_missing` -> **run perdu** | fichier partiel livre, correction possible |
| charge valide | parsee | parsee a l identique (verrouille par test) |
| charge vraiment inexploitable | echec | echec (inchange) |

Tests : **761 -> 773 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeGenerationActionSalvage.test.ts'
```

Trace des deux echecs reels avant correction :
`application/output/code/audit_v90/cli_baseline/_harness_summary.json` (champ
`notes`) et `application/output/code/audit_v90/bridge_runner/_stream.ndjson`
(evenement `done`, champ `notes`).

### Etat de satisfaction chantier

Les deux modes de corruption observes sont couverts. Reste assume : la
reparation ecrit un fichier partiel sans le signaler au modele lors de la passe
suivante — la boucle de correction le detectera comme fichier incomplet, mais un
signal explicite « ce fichier a ete tronque, termine-le » serait plus direct.

## 2026-08-09 — Le tunnel tournait sur un autre moteur que l UI

### Reprise et diagnostic

Le rapport de juillet signalait un « moteur bridge NDJSON dormant » derriere le
flag `VITE_CODE_STREAM_ENGINE`. Verification faite, le diagnostic etait a la
fois exact et incomplet.

Exact : le flag n existe nulle part ailleurs que dans un commentaire
(`codeStreamStore.ts:187`), qui affirme que le second moteur « a ete retire ».

Incomplet : il n a ete retire que du store UI. La route
`POST /api/code/generate/stream` lancait toujours
`python-services/aurora_code/bridge_agentic_stream.py`, et surtout cette route
est appelee par `_aurora_code()` (`bridge_server.py`), c est-a-dire par le
dispatcher `/api/aurora/code/generate` que **cowork, le tunnel et tout client
externe** utilisent. Le moteur mort n etait donc pas mort : il servait un canal
entier.

Cartographie reelle des trois canaux avant correction :

| Canal | Moteur | Gates |
|---|---|---|
| `CodeView.tsx` (UI Tauri) | `orchestrateCodeGeneration` | pipeline complet |
| CLI `scripts/code_harness/run.mjs` | `orchestrateCodeGeneration` | pipeline complet |
| bridge / tunnel / cowork | `bridge_agentic_stream.py` (394 l.) | **aucune** |

Le moteur Python n a ni classification d intention, ni plan d architecture
bloquant, ni assets inter-modules, ni validation sandbox, ni boucle
d auto-correction, ni rapport de finition. C est exactement le « chemin degrade
cache » que la conformite CLI/tunnel/UI interdit.

### Recherches et choix

Trancher, pas maintenir deux moteurs. Le moteur TS est celui qui porte les
gates et celui que l UI utilise : c est lui la reference. Restait a le rendre
appelable depuis le bridge.

Le terrain etait deja pret : `run.mjs` prouve que le graphe TS de production se
charge sous Node (shims navigateur + hook de resolution pour les imports sans
extension), et `codeStreamEvents.ts` definit deja le protocole NDJSON
`aurora.code.stream/1` — le MEME identifiant de schema que `CODE_STREAM_SCHEMA`
cote Python. Les constructeurs d evenements TS etaient orphelins : personne ne
les appelait.

Choix : un runner Node qui lit le payload sur stdin, execute
`orchestrateCodeGeneration` et emet les evenements avec ces constructeurs
partages. Le schema ne bouge pas, donc `_aurora_code()` et ses consommateurs
continuent de fonctionner sans modification.

Deux precautions non evidentes :
- **`console.log` est redirige vers stderr** dans le runner. Le pipeline logue
  librement ; une seule ligne de log sur stdout corromprait le flux NDJSON que
  le bridge lit ligne par ligne.
- **un pipeline en erreur n est jamais annonce `done`**, meme s il a produit des
  fichiers partiels. Les consommateurs lisent `done` comme une livraison valide ;
  emettre `done` sur un echec transformerait une panne en succes silencieux.
  Les fichiers partiels sont emis, puis un `error` explicite clot le flux.

L environnement headless (shims + hook) est extrait dans `harness_env.mjs`
partage par le CLI et le bridge : deux copies auraient re-diverge, ce qui est
precisement la maladie soignee ici.

### Modifications realisees

- `scripts/code_harness/harness_env.mjs` (nouveau) — environnement headless
  partage, plus `routeConsoleToStderr()`.
- `scripts/code_harness/bridge_ndjson_runner.mjs` (nouveau) — le runner.
- `scripts/code_harness/run.mjs` — utilise l environnement partage.
- `bridge_server.py` — la route lance le runner Node au lieu du moteur Python
  (diff minimal : 3 hunks, aucun autre chantier touche).
- `scripts/code_harness/verify_bridge_parity.py` (nouveau) — controle
  reproductible en 11 points, sans dependre d un bridge demarre.

### Avant-apres mesurable

| Mesure | Avant | Apres |
|---|---|---|
| Moteurs distincts en production | **2** | **1** |
| Gates sur le canal tunnel/cowork | aucune | pipeline complet |
| Schema NDJSON | `aurora.code.stream/1` | inchange |
| Constructeurs d evenements TS | orphelins | utilises |

Run reel du runner sur un brief complexe : **38 evenements NDJSON**, 21 `phase`,
16 `file.written`, 1 `done`, toutes les lignes au schema `aurora.code.stream/1`,
aucune pollution de stdout. Les phases tracent le vrai pipeline (classification
semantique, preflight, recherche de marque Mercedes-Benz, references UX/UI, plan
d architecture, executor WS3) — toutes absentes du moteur Python.

Controle de parite : **11/11 verts**, code de sortie 0.

### Demonstration reproductible

```bash
cd application
python3 scripts/code_harness/verify_bridge_parity.py
jq '{ok, checks: [.checks[] | {check, ok}]}' output/code/audit_v90/bridge_parity_report.json

# flux NDJSON reel produit par le runner
python3 -c "
import json, collections
ev=[json.loads(l) for l in open('output/code/audit_v90/bridge_runner/_stream.ndjson') if l.strip()]
print(len(ev), 'evenements', dict(collections.Counter(e['kind'] for e in ev)))
print('schemas:', {e['schema'] for e in ev})
"
```

### Etat de satisfaction chantier

Les trois canaux partagent desormais un seul moteur. Reste ouvert et explicite :

- **la route n est active qu apres un redemarrage du bridge** (Flask a charge
  l ancien module en memoire). Le bridge n a pas ete redemarre ici pour ne pas
  interrompre le travail video/3D en cours de l utilisateur ; le controle de
  parite ne depend volontairement pas d un bridge demarre.
- `bridge_agentic_stream.py` et son test sont **laisses en place**, plus
  references par aucune route. Les supprimer est un nettoyage a part entiere,
  separe de la correction fonctionnelle.
- la boucle du juge visuel WS9 vit toujours dans la couche vue
  (`codeViewVisualCorrectionLoop.ts`), donc seul `CodeView.tsx` en beneficie :
  le CLI et le bridge ne l ont pas. La divergence n est plus cachee (les trois
  canaux partagent le moteur), mais elle n est pas fermee.
