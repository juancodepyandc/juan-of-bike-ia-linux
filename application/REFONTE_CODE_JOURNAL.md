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

## 2026-08-09 — WS7 n etait pas bloque par l hote, mais par un nom de champ

### Reprise et diagnostic

Le journal repetait depuis juillet : « Podman rootless reste bloque par la
configuration de l hote ». Verification faite sur la machine actuelle :

```
podman version 4.9.3
podman info --format '{{.Host.Security.Rootless}}'   -> true
stat -fc %T /sys/fs/cgroup                            -> cgroup2fs
podman run --rm --network=none alpine echo PODMAN_OK  -> PODMAN_OK
```

Podman fonctionne, en rootless, avec cgroups v2. L hote n est plus la cause.

En executant la vraie fonction de detection sur cette machine, la cause
apparait :

```
podman info --format '{{.Host.Security.Rootless}} {{.Host.CgroupVersion}}'
Error: template: info:1:35: can't evaluate field CgroupVersion in type *define.HostInfo
```

Podman 4.x expose `.Host.CgroupsVersion` (avec un s). Le gabarit du module
utilisait `.Host.CgroupVersion`. La commande echouait donc TOUJOURS,
`detectPodmanIsolation` renvoyait `unavailable`, et WS7 restait fail-closed en
permanence — sur n importe quel hote, aussi bien equipe soit-il. Ce n etait pas
une limite de machine, c etait un nom de champ.

Second defaut, decouvert en executant reellement la chaine : le volume de
workspace est cree avec `--opt o=size=...`, qui exige le Project Quota du
systeme de fichiers. Ici :

```
Error: volume options size and inodes not supported. Filesystem does not support Project Quota
```

et `prepareSandboxWorkspace` faisait `if (!create.ok) return { ok: false }`.
Autrement dit : un quota disque inapplicable desactivait TOUTE l isolation —
reseau coupe, racine en lecture seule, plafond de PID, memoire, CPU — alors que
ces confinements-la, eux, fonctionnent parfaitement. Une garantie souple faisait
tomber les garanties dures.

### Recherches et choix

- Le gabarit est corrige, ET un repli sur `podman info --format json` est ajoute :
  les cles JSON sont stables entre versions, la ou les noms de champs Go ne le
  sont pas. Dependre d un nom instable est precisement ce qui a coute six
  semaines d isolation desactivee.
- Le quota disque devient degradable : si le systeme de fichiers le refuse, le
  volume est cree sans lui et l etape l ecrit noir sur blanc
  (`workspace-size=NON APPLIQUE ...; les autres confinements restent actifs`).
  Jamais silencieux, jamais bloquant.

### Modifications realisees

- `src/services/codeSandboxIsolation.ts` — gabarit corrige, `parsePodmanIsolationJson`
  en repli, `buildPodmanSandboxVolumeCreateArgsWithoutQuota`,
  `isVolumeQuotaUnsupportedError`.
- `src/services/codeSandboxWorkspace.ts` — degradation explicite du quota disque.
- `src/__tests__/codeSandboxIsolation.test.ts` — 5 tests ajoutes (10 -> 15).
- `scripts/code_harness/ws7_isolation_proof.mjs` (nouveau) — preuve d execution
  reelle, qui appelle les fonctions de production plutot que de les reimplementer.

### Avant-apres mesurable

| Controle | Avant | Apres |
|---|---|---|
| `detectPodmanIsolation` sur cet hote | `unavailable` (gabarit refuse) | `podman-rootless`, cgroup v2 |
| Sandbox si le FS n a pas de Project Quota | **desactivee entierement** | active, quota disque declare non applique |
| Code execute dans le conteneur | jamais execute | `hello from sandbox` |
| Sortie reseau | non prouvee | **refusee** |
| Racine du conteneur | non prouvee | **lecture seule** (`Errno 30`) |
| Fork bomb | non prouvee | **contenue en 242 ms** (`BlockingIOError`), hote intact |

Preuve : 10/10 controles verts dans
`application/output/code/audit_v90/ws7_isolation_proof.json`.

Tests : **773 -> 778 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
podman pull docker.io/library/python:3.12-slim   # --pull=never exige l image locale
node scripts/code_harness/ws7_isolation_proof.mjs --json output/code/audit_v90/ws7_isolation_proof.json
jq '{ok, checks: [.checks[] | {check, ok}]}' output/code/audit_v90/ws7_isolation_proof.json
```

### Etat de satisfaction chantier

WS7 est prouve en execution reelle pour la premiere fois, fork bomb comprise.
Restent ouverts et explicites :

- **le quota disque du workspace n est pas applique sur cet hote** (Project Quota
  absent du systeme de fichiers). C est une vraie limite machine, desormais
  declaree au lieu de tout desactiver.
- `--pull=never` impose de pre-telecharger les images par langage. Seules
  `python:3.12-slim` et `alpine` sont presentes ici ; les autres langages
  echoueront tant que leur image n est pas tiree. Aucun test ne pretend le
  contraire.
- l acceptation WS7 reste une checklist regex ; la remplacer par une vraie
  execution de tests dans le conteneur devient possible maintenant que le
  conteneur tourne, mais n est pas fait ici.

## 2026-08-09 — Le detecteur d orphelins mentait dans le mauvais sens

### Reprise et diagnostic

Le scanner anti-orphelin livre en debut de session s est trompe sur son propre
auteur. Apres avoir ecrit des commentaires expliquant que `buildDesignDirectives`
et `getSystemPromptForRole` etaient orphelins, le scan les a declares... cables.

Cause : il comptait toute occurrence du nom, commentaires compris. Un symbole
seulement CITE dans une explication devenait un appelant. C est le sens d erreur
le plus dangereux pour cet outil : il fabrique des verdicts « cable » et masque
donc exactement ce qu il doit trouver.

Second manque : le corpus s arretait a `src/`. Or le runner NDJSON vit dans
`scripts/code_harness/` et le bridge le lance en production ; les symboles qu il
utilise etaient donc comptes orphelins a tort.

### Modifications realisees

- `scripts/code_harness/orphan_scan.mjs` — `stripComments()` avant tout comptage
  de references (volontairement conservateur : lignes de commentaire entieres et
  blocs `/* */`, pour ne jamais abimer un `//` present dans une chaine comme une
  URL) ; `scripts/code_harness/*.mjs` entre dans le corpus de production.

### Avant-apres mesurable

Mesure a outillage IDENTIQUE (le scanner courant rejoue sur le commit `2df159f`
via un worktree jetable, puis sur HEAD) — sans quoi la comparaison n aurait
aucun sens :

| Mesure | Avant (`2df159f`) | Apres |
|---|---|---|
| Modules de service Code | 156 | 159 |
| Modules cables | 155 | 158 |
| Modules orphelins | 1 | 1 |
| Symboles orphelins | **22** | **21** |
| Symboles resolus | — | `serializeCodeStreamEvent` |
| Nouveaux orphelins introduits | — | **0** |

Les trois modules ajoutes cette session sont tous atteignables depuis la
production : le compte de modules cables monte de 155 a 158 sans creer d orphelin.

### Demonstration reproductible

```bash
cd application
node scripts/code_harness/orphan_scan.mjs --json output/code/audit_v90/orphan_scan_after.json

# comparaison a outillage identique
git worktree add -q --detach /tmp/wt_before 2df159f
cp scripts/code_harness/orphan_scan.mjs /tmp/wt_before/application/scripts/code_harness/
(cd /tmp/wt_before/application && node scripts/code_harness/orphan_scan.mjs --json /tmp/orphan_before.json)
git worktree remove --force /tmp/wt_before
```

### Etat de satisfaction chantier

L outil ne peut plus produire de faux « cable ». Limite connue et assumee : il
ne modelise pas la mort TRANSITIVE. `buildCommonPremiumBaseline`,
`depthDirectivesBlock` et `autoDepsBlock` ne sont appeles que par
`buildDesignDirectives`, lui-meme orphelin : ils ne sont donc pas signales alors
qu aucun chemin de production ne les atteint. `archetypeBlock`, en revanche, est
desormais reellement atteint via le contrat qualite de l executor.

## 2026-08-09 — Un plan sans porte d entree condamnait le run

### Reprise et diagnostic

Observe en direct, deux fois, sur le meme brief. L intention est correctement
`static_web` (une fois le garde-fou semantique en place), mais l architecte
produit un plan **Next.js** — `src/app/layout.tsx`, `src/app/page.tsx`,
`next.config.js`, `tailwind.config.ts` — **sans `index.html`**. Ensuite :

- le contrat plan/livraison passe : les fichiers livres correspondent au plan ;
- la porte de livraison refuse : « Page web statique detectee mais `index.html`
  est absent » ;
- la boucle de sortie regenere... a partir du meme plan, donc le meme manque.

Le run consomme ses passes (`tentative 1/6`, `tentative 2/6`, ...) sur un defaut
que personne ne corrige. Rien ne validait le plan contre le `projectType` de
l intention : `checkArchitecturePlanFileContract` verifie seulement que les
fichiers LIVRES correspondent au PLAN, pas que le plan soit coherent avec le
type de projet.

Point cle : dire au codeur « `index.html` est obligatoire » — ce que fait
desormais le contrat qualite — **ne suffit pas**, parce que l executor WS3 ne
peut ecrire QUE les fichiers de la file issue du plan. Si le plan ne le contient
pas, le fichier ne peut pas exister.

### Recherches et choix

Deux options : replanifier, ou reparer. La replanification coute un chargement
de modele supplementaire par passe, ce que le budget VRAM de la machine (modele
de 18,6 Go sur un GPU de 16 Go) ne supporte pas. La reparation est donc
**deterministe et sans appel modele** : on injecte la porte d entree manquante
dans le plan, en tete de `generationOrder` puisque les autres fichiers s y
raccrochent.

La liste des portes d entree devient une **source de verite unique**, partagee
avec le contrat qualite envoye au codeur. Deux listes separees auraient fini par
diverger, produisant un plan et un contrat qui se contredisent.

### Modifications realisees

- `src/services/codeArchitecturePlanEntryContract.ts` (nouveau) —
  `requiredEntryFilesForProject` (source unique) et
  `ensureArchitecturePlanEntryFiles`, sans effet quand le plan est deja conforme
  et sans lever quand le JSON est inexploitable.
- `src/services/codePipelinePhases.ts` — reparation branchee juste apres la
  selection du plan, TRACEE dans la phase (« porte d entree ajoutee (...) »).
- `src/services/codeExecutorQualityContract.ts` — consomme la source unique au
  lieu de sa propre copie.
- `src/__tests__/codeArchitecturePlanEntryContract.test.ts` (nouveau) — 9 tests.

### Avant-apres mesurable

| Plan produit pour un `static_web` | Avant | Apres |
|---|---|---|
| Plan Next.js sans `index.html` | passes brulees jusqu au budget, run perdu | `index.html` injecte, genere en premier |
| Plan deja conforme | inchange | inchange (verrouille par test) |
| `cli_python` | inchange | inchange |
| Plan JSON inexploitable | — | rendu tel quel, sans lever |

Tests : **778 -> 787 verts, 0 echec.** Typecheck : 31 diagnostics, tous hors
perimetre Code, identiques a la baseline.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeArchitecturePlanEntryContract.test.ts'
```

Trace du defaut avant correction, run reel :
```bash
python3 -c "
import json
for l in open('output/code/audit_v90/bridge_runner_after/_stream.ndjson'):
    e=json.loads(l); m=e.get('message','')
    if 'tentative' in m or 'ecartee' in m: print(m)
"
```

### Etat de satisfaction chantier

La porte d entree ne peut plus manquer. Reste ouvert et assume : l architecte
continue de produire une structure Next.js pour une intention `static_web` — la
reparation garantit la porte d entree, elle ne realigne pas toute la stack du
plan sur le type de projet. Contraindre l architecte au `projectType` (ou faire
converger l intention vers la stack planifiee) est un chantier distinct.

## 2026-08-09 — Etat final de session et ce qui reste casse

### Verification de bout en bout, resultat honnete

Un dernier run complet a ete lance sur le canal tunnel, toutes corrections
actives, avec le meme brief Mercedes-Benz. Il **n a pas abouti** :

```
Plan d architecture inexploitable - generation bloquee (architecture_plan_invalid:files_min_2)
Erreur fatale du pipeline: Echec du plan d architecture structure: architecture_plan_invalid:files_min_2
```

L architecte a rendu, sur TOUS ses candidats, un plan JSON valide mais contenant
moins de deux fichiers. Aucun repli n existe a cet endroit : c est un echec dur.

Ce qui a bien fonctionne dans ce run, et qui est verifiable dans
`output/code/audit_v90/final_after/_stream.ndjson` :

- le garde-fou semantique a de nouveau ecarte l hallucination `ide`
  (« Classification semantique ecartee (ide non corrobore) -> static_web ») —
  troisieme reproduction consecutive du defaut, trois fois rattrapee ;
- le runner a emis un evenement `error`, **pas** un `done` de complaisance,
  conformement a la regle anti-echec-silencieux posee cette session.

### Ce qui reste casse, explicitement

1. **`architecture_plan_invalid:files_min_2` n a aucun repli.** Quand
   l architecte rend un plan trop pauvre sur tous ses candidats, le run meurt.
   C est aujourd hui le point de rupture le plus proche de l utilisateur sur
   cette machine. Piste directe : appliquer au parseur de plan la meme
   reparation de caracteres de controle que celle livree pour le protocole
   d actions (`repairJsonControlCharacters`), puis, si le plan reste trop
   pauvre, le completer depuis l intent au lieu d avorter — la file de repli
   existe deja (`buildGenerationQueueWithFallback`) mais n est jamais atteinte
   parce que `runPlanningPhase` leve avant.
2. **L architecte ignore le `projectType`.** Il produit une structure Next.js
   pour une intention `static_web`. La porte d entree est desormais garantie,
   la stack ne l est pas.
3. **La boucle du juge visuel WS9 reste dans la couche vue**
   (`codeViewVisualCorrectionLoop.ts`), donc seul `CodeView.tsx` en beneficie.
   Le CLI et le tunnel partagent maintenant le meme moteur, mais aucun des deux
   n execute cette boucle. La divergence n est plus cachee ; elle n est pas
   fermee. La deplacer dans le pipeline suppose d injecter le dev-server, qui
   passe par Tauri (`spawnWorkspaceCommand`).
4. **21 symboles orphelins** subsistent (liste exacte dans
   `output/code/audit_v90/orphan_scan_after.json`), dont `buildDesignDirectives`,
   `getSystemPromptForRole`, `evaluateVisualFidelity` et
   `buildVisualFidelityCritique`. Aucun n a ete supprime : la suppression est un
   chantier a part, et le contrat compact livre cette session remplace
   fonctionnellement les deux premiers dans le chemin WS3.
5. **La route bridge n est active qu apres redemarrage du bridge.** Non fait ici
   pour ne pas interrompre le travail video/3D en cours de l utilisateur.
6. **L acceptation WS7 reste une checklist regex.** Le conteneur tourne
   desormais vraiment, donc la remplacer par une execution de tests reelle est
   devenu possible — mais ce n est pas fait.

### Etat de satisfaction session

Sept increments livres, chacun avec sa preuve. La suite passe de 743 a
**787 tests verts**, le typecheck du perimetre Code reste sans diagnostic, et
aucun fichier des chantiers video/3D/voix en cours n a ete committe.

## 2026-08-09 — Un architecte defaillant ne tue plus le run

### Reprise et diagnostic

Point de rupture le plus proche de l utilisateur, constate sur le run de
verification precedent :

```
Plan d architecture inexploitable - generation bloquee (architecture_plan_invalid:files_min_2)
Erreur fatale du pipeline: Echec du plan d architecture structure
```

Le modele avait rendu, sur TOUS ses candidats, un JSON valide mais contenant
moins de deux fichiers. Zero fichier livre, alors que l intention etait
parfaitement connue.

L ironie: le repli existe DEJA un etage plus bas.
`buildGenerationQueueWithFallback` sait deriver une file de fichiers depuis le
seul intent (`defaultFilesForIntent`). Il n etait simplement jamais atteint,
parce que deux `throw` se declenchent avant lui — celui de `runPlanningPhase`,
puis celui de `isArchitecturePlanUsable` dans `runFullPipeline`.

Second defaut trouve au passage: `parseArchitecturePlanJson` souffrait de la
MEME corruption que le protocole d actions (vrais caracteres de controle dans
une chaine, typiquement un `summary` multi-lignes), sans la reparation livree
plus tot dans la session.

### Recherches et choix

On supprime la cause, pas le symptome. Quand l architecte echoue, on
SYNTHETISE un plan deterministe depuis l intent, valide au regard du meme
schema, et le pipeline continue. Aucun appel modele supplementaire : une
replanification couterait un chargement de modele que le budget VRAM de la
machine ne supporte pas.

Le plan de repli n invente rien. Il reprend `defaultFilesForIntent` (deja source
de verite de la file de repli) et `requiredEntryFilesForProject` (deja source de
verite du contrat de livraison). Il satisfait toutes les exigences du schema, y
compris le minimum de deux fichiers qui avait tue le run — un projet Python
mono-fichier recoit donc un `requirements.txt`.

Il se declare aussi pour ce qu il est : son `summary` dit « repli », et il
inscrit son propre risque (« certaines fonctionnalites du prompt peuvent
manquer »), pour que la degradation ne soit jamais silencieuse.

### Modifications realisees

- `src/services/codeArchitecturePlanFallback.ts` (nouveau) —
  `buildFallbackArchitecturePlan(intent, prompt)`.
- `src/services/codeGenerationQueue.ts` — `defaultFilesForIntent` exporte pour
  redevenir source de verite unique au lieu d etre recopie.
- `src/services/codePipelinePhases.ts` — le `catch` construit le repli et
  poursuit ; il ne leve que si le repli lui-meme est invalide (impossible en
  pratique, verrouille par test).
- `src/services/codeArchitecturePlan.ts` — `repairJsonControlCharacters` branche
  sur le parseur de plan, uniquement apres un echec de parse.
- `src/__tests__/codeArchitecturePlanFallback.test.ts` (nouveau) — 8 tests.

### Avant-apres mesurable

| Situation | Avant | Apres |
|---|---|---|
| Plan a moins de 2 fichiers sur tous les candidats | **run mort, 0 fichier** | plan de repli valide, generation poursuivie |
| Projet Python mono-fichier | `files_min_2` fatal | `main.py` + `requirements.txt` |
| Plan avec vrais sauts de ligne dans `summary` | `json_parse_failed` | repare et accepte |
| Plan valide | inchange | inchange (verrouille par test) |

Le repli produit un plan valide pour les 5 types de projets courants testes, et
la file de generation qui en decoule contient au moins 2 fichiers.

Tests : **795 -> 803 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeArchitecturePlanFallback.test.ts'
```

### Etat de satisfaction chantier

Le pipeline ne peut plus rendre zero fichier a cause de l architecte. Reste
assume : le plan de repli est volontairement minimal — il garantit un livrable
executable, pas la richesse d un plan reussi. La boucle de correction reste
chargee de completer.

## 2026-08-09 — Le type de projet etait une information, pas une contrainte

### Reprise et diagnostic

Defaut observe : intention `static_web`, plan rendu en Next.js
(`src/app/layout.tsx`, `next.config.js`, `tailwind.config.ts`) sans
`index.html`. Deux mecanismes s additionnaient, et aucun n etait un hasard du
modele.

**1. Le prompt informait au lieu de contraindre.** Il annonce « Projet detecte:
static_web », puis demande, quelques lignes plus bas, « Quelles sont les
meilleures librairies/outils/patterns pour ce type de projet ? » et « les
solutions les plus modernes ». On invite donc explicitement le modele a choisir
une stack, c est-a-dire a contredire le type detecte.

**2. Le scoreur recompensait la derive.** `scoreArchitecturePlan` additionne
`requiredFiles * 4`, `files.length * 2`, `dependencySignal * 2`,
`executionSignal * 3`. Un candidat Next.js — plus de fichiers, plus de
dependances, plus de scripts — obtenait donc MECANIQUEMENT un meilleur score
qu un candidat statique correct. **Le mauvais plan gagnait par construction**,
independamment de la qualite du modele.

### Recherches et choix

Rendre le type contraignant des deux cotes, sans jamais rejeter durement :

- **Prompt** : un bloc « TYPE DE PROJET — CONTRAINTE, PAS SUGGESTION » qui
  impose la valeur du champ `projectType`, cite les fichiers d entree
  obligatoires (depuis la source de verite deja partagee) et nomme les interdits
  concrets. Il precise que la question « quelle est la stack la plus moderne »
  ne s applique QU A L INTERIEUR de la contrainte.
- **Selection** : une penalite de conformite retranchee du score. Calibree pour
  renverser le biais structurel, pas pour eliminer : si tous les candidats
  derivent, mieux vaut le moins mauvais qu aucun plan.

Le contrat est declare par type, pas en dur : Next.js reste parfaitement
legitime pour une intention `ssr_nextjs`, et le bloc ne lui interdit rien.

### Modifications realisees

- `src/services/codeProjectTypeStackContract.ts` (nouveau) — marqueurs interdits
  par type, `checkPlanProjectTypeConformity`, `projectTypeConformityPenalty`,
  `buildProjectTypeStackContract`.
- `src/services/codeArchitecturePlanSelection.ts` — `selectBestArchitecturePlan`
  accepte un `intent` optionnel (retro-compatible) et applique la penalite.
- `src/services/codePipelinePhases.ts` — le contrat entre dans le prompt de
  planification et l intent est transmis a la selection.
- `src/__tests__/codeProjectTypeStackContract.test.ts` (nouveau) — 11 tests.

### Avant-apres mesurable

Le test decisif compare les DEUX chemins sur les memes candidats (un plan
Next.js lourd et un plan statique correct, intention `static_web`) :

| Selection | Candidat retenu |
|---|---|
| `selectBestArchitecturePlan([next, static])` (sans intent) | **le plan Next.js** — biais historique reproduit |
| `selectBestArchitecturePlan([next, static], intent)` | **le plan statique correct** |

| Conformite | Verdict |
|---|---|
| Plan Next.js pour `static_web` | non conforme, `index.html` manquant |
| Plan statique pour `static_web` | conforme |
| Plan Next.js pour `ssr_nextjs` | conforme (aucune regression sur le type qui l attend) |
| Plan se declarant d un autre type que l intent | non conforme |
| `cli_python` avec `package.json` | non conforme |

Tests : **803 -> 806 verts** cumules avec l increment precedent, 0 echec.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeProjectTypeStackContract.test.ts'
```

### Etat de satisfaction chantier

Le type est desormais contraignant dans le prompt ET dans la selection. Reste
assume : la penalite ne peut pas inventer un bon candidat quand tous derivent —
elle choisit alors le moins mauvais, et la reparation de porte d entree livree
plus tot garantit malgre tout le fichier d entree.

## 2026-08-09 — La porte visuelle ne servait qu'a un seul canal

### Reprise et diagnostic

WS9 avait ete mis « in-loop » en juillet, mais dans la couche VUE :
`codeViewGeneration.ts` appelle `runVisualCorrectionLoop`
(`codeViewVisualCorrectionLoop.ts`). Consequence directe, verifiee par grep :
seul `CodeView.tsx` en beneficie. Le CLI (`run.mjs`) et le canal tunnel
appellent `orchestrateCodeGeneration` directement et livraient donc **sans
aucune garde visuelle** — precisement la parite exigee entre canaux.

Le blocage suppose etait `startDevServer` -> `spawnWorkspaceCommand`, couple a
Tauri. Mais en relisant `codeVisualFidelity.ts`, il existe DEUX portes
visuelles, pas une :

- l audit RENDU (navigateur + serveur de dev) — celui qui est couple ;
- `evaluateVisualFidelity`, une porte **source-statique** qui inspecte le
  HTML/CSS/JS livre, sans navigateur ni serveur.

La seconde etait un ORPHELIN : implementee, testee, jamais appelee en
production. Elle accepte en plus un audit rendu optionnel, donc elle unifie les
deux chemins au lieu de les concurrencer.

### Recherches et choix

Cabler la porte source-statique dans `finalizeCodePipelineDelivery`, c est-a-dire
dans le pipeline lui-meme, donc sur les TROIS canaux. Zero navigateur, zero
serveur, zero appel modele supplementaire — donc aucun cout sur le budget de
passes ni sur la VRAM.

Le mixage du score reprend la semantique deja en place pour la porte de marque
juste au-dessus : la correction du modele reste dominante (0,75), l apparence
pese (0,25), et un rendu qui echoue son seuil est plafonne a 84 — la meme valeur
que celle utilisee par le mixage de l audit rendu, pour que les deux chemins
notent pareil.

La critique precise part avec la livraison (`## QUALITE VISUELLE`), donc la
degradation n est jamais silencieuse et la directive de repasse esthetique est
deja redigee.

### Modifications realisees

- `src/services/codePipelineFinalization.ts` — porte visuelle evaluee,
  `blendVisualFidelityIntoScore` (exporte et teste), critique jointe aux notes,
  `visualFidelity` ajoute au type de livraison.
- `src/services/codeOrchestratorTypes.ts` / `codeOrchestrator.ts` — le rapport
  remonte dans le resultat, donc lisible par n importe quel canal.
- `scripts/code_harness/bridge_ndjson_runner.mjs` — emet un evenement
  `visual.score` sur le flux tunnel.
- `src/__tests__/codeVisualGateParity.test.ts` (nouveau) — 7 tests.
- `src/services/codeOrchestrator.ts` — bloc de re-export compacte pour rester
  sous la limite des 400 lignes (le garde structurel l a attrape a 400 pile).

### Avant-apres mesurable

| Canal | Garde visuelle avant | Apres |
|---|---|---|
| UI Tauri (`CodeView.tsx`) | audit rendu (couche vue) | audit rendu **+** porte source-statique |
| CLI (`run.mjs`) | **aucune** | porte source-statique |
| Tunnel / cowork | **aucune** | porte source-statique + evenement `visual.score` |

| Cas | Avant | Apres |
|---|---|---|
| Page scolaire (Arial, `#fff`/`#000`, `color: blue`) notee 95 par le modele | livree a **95** | porte echouee, score **plafonne a 84** |
| Projet non visuel note 90 | 90 | 90 (aucune penalite) |
| Page sous le seuil | aucune trace | critique `## QUALITE VISUELLE` jointe |

Orphelins resolus au passage : `evaluateVisualFidelity`,
`buildVisualFidelityCritique`, `buildCodeStreamVisualScoreEvent`.

Tests : **806 -> 813 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeVisualGateParity.test.ts'
node scripts/code_harness/orphan_scan.mjs --json output/code/audit_v91/orphan_scan_after.json
```

### Etat de satisfaction chantier

Les trois canaux ont desormais une garde visuelle qui COMPTE dans le score.
Reste ouvert et assume : la boucle de REGENERATION esthetique (audit rendu ->
repasse ciblee) demeure exclusive a l UI Tauri, parce qu elle depend d un
serveur de dev lance via Tauri. Le CLI et le tunnel detectent et penalisent une
page faible, et emportent la critique, mais ne declenchent pas d eux-memes la
repasse.

## 2026-08-09 — Une calculatrice fausse passait l acceptation

### Reprise et diagnostic

Reproche explicite de l audit de juillet, jamais traite : « les tests
d acceptation sont une checklist REGEX statique fixe (aucune execution). Une
calculatrice au calcul FAUX passe 100 %. »

Verification directe, plutot que sur parole. Deux calculatrices ont ete
fabriquees, identiques a une ligne pres :

- `calc_correct` : `if(o==='+')return a+b; if(o==='-')return a-b; ...`
- `calc_faux`    : `if(o==='+')return a-b; if(o==='-')return a+b; ...`

Puis `evaluateAcceptanceCriteria` a ete execute sur les deux :

```
checklist REGEX statique — calc_correct: score=71%
checklist REGEX statique — calc_faux:    score=71%
   PASS calculator-operator-correctness      <-- sur la calculatrice INVERSEE
```

**Score identique, au point pres.** Le critere cense verifier la justesse des
operateurs passe sur celle qui les inverse. Aucune regex ne peut prouver que
2 + 3 fait 5 : elle ne lit que la forme du code, jamais son comportement.

### Recherches et choix

Le conteneur Podman tourne desormais reellement (chantier precedent), mais pour
une page web l execution utile n est pas un conteneur : c est un NAVIGATEUR.
Playwright/Chromium est deja installe et deja utilise ailleurs dans le depot
pour d autres preuves.

Le module sert donc les fichiers livres depuis un petit serveur en memoire
(aucun serveur de dev, donc aucune dependance a Tauri : le chemin marche en CLI
comme dans le tunnel), ouvre la page dans Chromium headless, **clique sur ses
vrais boutons** et **lit son vrai affichage**.

Les boutons sont trouves par leur TEXTE visible, avec alias (`*`, `×`, `x`),
pour rester independant du nommage interne choisi par le modele.

Deux criteres universels s appliquent a toute page livree — pas d erreur
JavaScript au chargement, et la page n est pas une coquille vide. Ce second
critere ne peut pas etre un simple nombre de caracteres : une calculatrice
correcte n affiche que des chiffres. Il accepte donc du texte OU de vrais
controles OU une surface graphique.

Branchement fail-soft dans le runner : l absence de navigateur n empeche jamais
une livraison.

### Modifications realisees

- `scripts/code_harness/acceptance_behaviour.mjs` (nouveau) — serveur memoire,
  pilotage Chromium, criteres comportementaux, plus une CLI autonome.
- `scripts/code_harness/bridge_ndjson_runner.mjs` — acceptation comportementale
  branchee, resultat emis en `test.result`, desactivable par
  `AURORA_CODE_BEHAVIOUR_ACCEPTANCE=0`.

### Avant-apres mesurable

| Livrable | Checklist regex (avant) | Acceptation comportementale (apres) |
|---|---|---|
| Calculatrice correcte | 71 % | **100 %** |
| Calculatrice aux operateurs inverses | **71 %** | **50 %** |

Detail du verdict comportemental sur la calculatrice fausse :

```
FAIL calc-2+3 | affiche "-1" (attendu 5)
FAIL calc-9-4 | affiche "13" (attendu 5)
FAIL calc-6*7 | affiche "13" (attendu 42)
PASS calc-8/2 | affiche "4"  (attendu 4)
```

La division reste juste dans la version fausse — et le test le dit, au lieu de
noyer le tout dans un score global.

### Demonstration reproductible

```bash
cd application
node scripts/code_harness/acceptance_behaviour.mjs \
  output/code/audit_v91/ws7_acceptance/calc_correct --prompt "calculatrice"
node scripts/code_harness/acceptance_behaviour.mjs \
  output/code/audit_v91/ws7_acceptance/calc_faux --prompt "calculatrice"
```

Rapports : `output/code/audit_v91/ws7_acceptance/report_correct.json` (ok=true,
score 100) et `report_faux.json` (ok=false, score 50).

### Etat de satisfaction chantier

Une calculatrice au calcul faux ne peut plus passer. Reste ouvert et assume :

- le pilotage comportemental couvre aujourd hui les calculatrices et deux
  criteres universels ; d autres familles (tri de tableau, filtre, panier)
  demandent chacune leur scenario de pilotage ;
- la checklist regex de `codeAcceptanceCriteria.ts` reste en place dans le
  sandbox : elle est rapide et sans navigateur. Le gate comportemental s ajoute
  au lieu de la remplacer, et c est lui qui tranche sur le comportement.

## 2026-08-09 — Le plafond de tokens generes n'etait jamais transmis

### Reprise et diagnostic

Trouve en triant les orphelins, pas en cherchant ce bug : le scan signalait
`CODE_EXPERT_OUTPUT_TOKENS` comme symbole exporte sans aucun appelant de
production. La constante vaut `16_000`, elle est meme verrouillee par un test
(`assert.equal(CODE_EXPERT_OUTPUT_TOKENS, 16_000)`)... et elle n etait passee
a personne.

En suivant la chaine d appel de la generation :

- `codeAgenticGenerationPhase` passe `numCtx` au producteur d actions, jamais
  de `numPredict` ;
- `defaultChatClient` appelle `resilientOllamaChat(model, messages, 0.2, { signal, num_ctx, firstByteTimeoutMs })` ;
- `resilientOllamaChat` ne transmettait AUCUN `num_predict` a `ollamaChat` ;
- `ollamaChat` ne l accepte meme pas dans sa signature.

Or le depot documente lui-meme la consequence, dans le commentaire de
`ollamaChatStream` :

> « v82nd : max tokens to GENERATE. Some models (qwen3-coder default, certain
> Modelfile presets) cap num_predict at 256-1024 → output truncates after a
> single fence opener. **Pass 8000+ for code-gen.** »

Le correctif etait donc ecrit dans le code, et jamais applique au chemin de
generation du module Code. C est la cause racine des troncatures que la session
avait jusque-la traitees en aval par reparation de charge utile : un fichier
coupe en plein milieu produit une charge d actions JSON invalide.

### Recherches et choix

Le chemin non-streamant (`ollamaChat`) ne sait pas transmettre `num_predict`, et
`useTauri.ts` fait partie des fichiers modifies par le chantier video en cours :
interdit d y toucher. Mais `ollamaChatStream`, lui, est exporte ET accepte
`num_predict`.

`resilientOllamaChat` gagne donc un `num_predict` **optionnel** qui, lorsqu il
est fourni, emprunte le flux et l accumule. Les autres modules (conversation,
learning, cyber, voix) ne passent pas ce parametre et gardent donc EXACTEMENT
leur chemin actuel — la resilience, les paliers de `num_ctx` et l escalade sont
inchanges.

Le plafond est borne par la fenetre (`min(num_predict, max(512, ctx * 0.6))`),
exactement comme le fait deja le chemin `generate`.

### Modifications realisees

- `src/services/ollamaResilience.ts` — `num_predict` optionnel, helper
  `chatAccumulatingStream`, bornage par la fenetre.
- `src/services/codeGenerationActionProducer.ts` — `numPredict` dans les options
  et transmis au client de chat.
- `src/services/codeAgenticGenerationPhase.ts` — passe
  `CODE_EXPERT_OUTPUT_TOKENS`.

### Avant-apres mesurable

| Etage | Avant | Apres |
|---|---|---|
| `CODE_EXPERT_OUTPUT_TOKENS` | defini, teste, **0 appelant** | passe a chaque appel de generation |
| `num_predict` envoye au modele | **aucun** (plafond Modelfile, parfois 256) | jusqu a 16 000, borne par la fenetre |
| Symboles orphelins | 19 | 18 |

Non-regression sur les autres modules, controle sur la suite COMPLETE du depot :
**4 673 tests, 4 670 verts, 0 echec, 3 ignores.** Le journal de juillet notait
3 echecs Cowork sur 4 545 tests ; il n y en a plus.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/*.test.ts' | tail -6
grep -n "numPredict: CODE_EXPERT_OUTPUT_TOKENS" src/services/codeAgenticGenerationPhase.ts
```

### Etat de satisfaction chantier

La cause racine des troncatures est traitee a la source, et la reparation de
charge utile livree plus tot reste comme filet. Reste assume : le plafond est
uniforme (16 000) et non adapte a la taille attendue du fichier ; un budget par
fichier serait plus fin, mais demanderait une estimation fiable de la taille
cible.

## 2026-08-09 — Tri des orphelins: cabler ou supprimer, pas de statu quo

### Reprise et diagnostic

Le scan anti-orphelin listait 19 symboles exportes sans aucun appelant de
production. Chacun devait recevoir une decision, pas un commentaire.

Deux d entre eux etaient des bugs deguises en code mort, et ont ete traites dans
les increments precedents (`CODE_EXPERT_OUTPUT_TOKENS`,
`STREAM_GENERATION_TOTAL_TIMEOUT_MS`). Les autres se repartissaient en deux
familles: des capacites reelles jamais branchees, et des constructeurs de prompt
rendus caducs par le passage a WS3.

### Modifications realisees

**Cables (capacite reelle rendue au pipeline)**

- `depthDirectivesBlock` + `autoDepsBlock` -> contrat qualite de l executor.
  Ce sont les regles three.js concretes (renderer, lumieres, materiaux,
  `dispose()`, `pixelRatio`, pause sur `visibilitychange`) qui separent une
  scene 3D credible d un cube qui tourne. Elles n etaient atteignables que par
  `buildDesignDirectives`, orphelin, donc jamais transmises.
- `formatGenerationQueueForPrompt` -> message utilisateur de l executor. Le
  modele ne voyait qu une fenetre de +/-3 fichiers autour de sa cible; il recoit
  desormais le manifeste complet du projet et sait a quoi son fichier se
  raccorde.

**Supprimes (physiquement, avec leurs tests)**

- `buildCodeurSystemPrompt`, `getSystemPromptForRole`,
  `buildCodeSystemPromptFromIntent`, `buildDesignDirectives`,
  `describeDesignArchetype`, `buildCommonPremiumBaseline`.
- Quatre modules devenus integralement injoignables:
  `codeIntentSystemPrompt.ts`, `codeIntentPromptAssets.ts`,
  `codeIntentPromptGame.ts`, `codeIntentPromptProject.ts`.

Leur role est couvert par ce qui est reellement cable: `codeSubjectPromptContract`
pour le verrouillage marque et les images, `buildDesignContractBlock` pour la
barre design, les blocs d archetype pour le jeu et le projet, et
`codeExecutorQualityContract` pour la synthese envoyee au codeur.

**Robustesse au passage**

- `formatGenerationQueueForPrompt` ne suppose plus `omittedOrderPaths` present.
- Une note de methode: le premier decoupage automatique des fonctions a coupe au
  milieu d un corps et laisse un token orphelin (`e`). Les fichiers ont ete
  restaures depuis HEAD et l outil corrige pour apparier vraiment les accolades
  en ignorant chaines, gabarits et commentaires. Aucune suppression n a ete
  conservee tant que la suite n etait pas verte.

### Avant-apres mesurable

| Mesure | Avant | Apres |
|---|---|---|
| Modules de service Code | 162 | **158** |
| Modules orphelins | 4 | **1** |
| Symboles orphelins | 19 | **13** |
| Suite Code | 813 verts | 782 verts (les tests des fonctions supprimees partent avec elles) |
| Suite COMPLETE du depot | — | **4 642 tests, 4 639 verts, 0 echec** |
| Typecheck perimetre Code | 0 diagnostic | **0 diagnostic** |

### Demonstration reproductible

```bash
cd application
node scripts/code_harness/orphan_scan.mjs --json output/code/audit_v91/orphan_scan_after.json
node --experimental-strip-types --test 'src/__tests__/*.test.ts' | tail -5
npx tsc --noEmit 2>&1 | grep -E "error TS" | sed -E 's/\(.*//' | sort | uniq -c
```

### Etat de satisfaction chantier

13 symboles orphelins subsistent, tous documentes dans
`output/code/audit_v91/orphan_scan_after.json`. Ils se repartissent ainsi, et
aucun n est laisse sans raison:

- **Superseded par le conteneur** — `checkRuntimeAvailable`, `autoInstallRuntime`,
  `getExecutableRuntimeSpec`, `getRuntimeSpec`: installer un runtime sur l HOTE
  n a plus de sens depuis que le sandbox WS7 s execute dans une image par
  langage. A supprimer quand le chemin hote sera officiellement retire.
- **Moities de protocole** — `parseCodeStreamEventLine` (le producteur
  `serializeCodeStreamEvent` est cable): utile a tout consommateur TS futur du
  flux NDJSON.
- **Capacites reelles non encore branchees** — `detectDeadCode`,
  `resolveToolPackageVersion`, `executeCodeGenerationToolSequence`,
  `projectTreeToCodeFiles`, `roundTripProjectTreeOnFs`,
  `listTreeSitterSupportedLanguages`, `isVagueClarification`,
  `buildAuditeurDiagnosticPrompt`. Chacune demande sa propre integration
  raisonnee, pas un appel decoratif pour faire baisser un compteur.

`codeStarterTemplates.ts` reste le seul module orphelin: il produit des projets
de demarrage complets, capacite reelle mais concurrente de la generation par
plan. Le trancher demande un choix produit, pas une correction technique.

## 2026-08-09 — Le tunnel savait creer un projet, pas le poursuivre

### Reprise et diagnostic

Passe de parite systematique apres l unification du moteur. Les trois canaux
partagent bien `orchestrateCodeGeneration`, mais ils ne lui donnent pas le meme
contexte. Le runner NDJSON codait en dur :

```js
conversationHistory: [],
existingFiles: [],
```

Consequence: une relance par le tunnel (« ajoute une section tarifs »,
« corrige le formulaire ») repartait de ZERO, alors que l UI poursuit le projet
en cours. Le pipeline sait pourtant faire un vrai suivi — analyse de pivot
(`analyzeFollowUpIntent`), portee de patch incremental WS5 — mais il ne peut
rien faire sans contexte.

La route bridge ne transmettait pas non plus ces champs: elle ne construisait le
payload qu avec `prompt`, `model`, `planningModel`, `ollamaUrl`, `runId`.

### Modifications realisees

- `scripts/code_harness/bridge_ndjson_runner.mjs` — `conversationHistory`,
  `existingFiles` et `contextImages` acceptes et normalises defensivement (le
  payload vient du reseau): roles filtres, 8 derniers tours, fichiers exigeant
  un `content` et un chemin.
- `bridge_server.py` — la route transmet les deux champs quand ils sont
  fournis, bornes (8 tours, 200 fichiers). Optionnels: un appel one-shot reste
  strictement inchange.
- `scripts/code_harness/verify_bridge_parity.py` — 4 controles ajoutes, dont un
  qui echoue si le contexte de suivi redevient code en dur a vide.

### Avant-apres mesurable

| Capacite via le tunnel | Avant | Apres |
|---|---|---|
| Creer un projet | oui | oui |
| Poursuivre un projet existant | **non** (repart de zero) | oui |
| Analyse de pivot de suivi | jamais declenchee | declenchee si historique fourni |
| Patch incremental WS5 | jamais (aucun fichier existant) | possible |

Controle de parite: **15/15 verts** (11 avant cet increment), code de sortie 0.

### Demonstration reproductible

```bash
cd application
python3 scripts/code_harness/verify_bridge_parity.py
jq '{ok, checks: [.checks[] | select(.check | test("followup|forwards|hardcode")) | {check, ok}]}' \
  output/code/audit_v91/bridge_parity_report.json
```

### Etat de satisfaction chantier

Le tunnel peut desormais poursuivre un projet. Reste assume : `_aurora_code()`,
le connecteur cowork one-shot, n expose pas encore ces champs a ses appelants —
il faudrait qu il tienne une session. La route, elle, les accepte.

## 2026-08-09 — Plus la demande etait complexe, moins elle etait finie

### Reprise et diagnostic

Dette documentee depuis juillet sous le nom « asymetrie #7 : le budget de retry
ignore le nombre de fichiers ». Verifiee dans le code :

```ts
export function computeAdaptiveCorrectionBudget(errorCategories, _correctionLog) {
  let budget = 6
  if (categories.length >= 2) budget += 1
  if (categories.some(/* categories lourdes */)) budget += 2
  return Math.max(4, Math.min(MAX_CORRECTION_PASSES, budget))
}
```

Le budget ne dependait QUE des categories d erreur. Un livrable de 30 fichiers
recevait donc exactement le meme nombre de passes de correction qu un livrable
de 3, alors qu il offre dix fois plus de surface a corriger.

L effet est exactement celui que la mission cherche a supprimer: **plus la
demande est complexe, moins elle est finie proportionnellement**.

### Recherches et choix

Le plafond ne bouge PAS. `MAX_CORRECTION_PASSES` est decrit dans le code comme
« plafond dur machine, jamais depasser », et chaque passe recharge un modele et
des processus de sandbox: relever la pointe, c est risquer le swap et le gel.

On se contente donc de REPARTIR le budget existant: resserre sur les livrables
triviaux, relache sur les gros, plafond inchange.

- <= 3 fichiers : base 5 (au lieu de 6)
- 4 a 10 fichiers : base 6 (inchange)
- > 10 fichiers : base 7

Les bonus par categorie d erreur restent identiques, et le maximum atteignable
(7 + 1 + 2 = 10) egale exactement le plafond dur deja en vigueur. La pointe de
consommation memoire est donc rigoureusement la meme qu avant.

Retro-compatibilite: sans information de taille, le comportement historique est
conserve a l identique — verrouille par un test.

### Modifications realisees

- `src/services/codeAutoCorrection.ts` — `computeAdaptiveCorrectionBudget`
  accepte `fileCount`; `shouldContinueLoop` le transmet. Liste des categories
  lourdes compactee pour rester sous la limite des 400 lignes (le garde
  structurel l a attrapee a 416, puis 408, puis 403).
- `src/services/codeValidationCorrectionLoop.ts` — passe `currentFiles.length`.
- `src/__tests__/codeAutoCorrection.test.ts` — 4 tests ajoutes.

### Avant-apres mesurable

| Projet | Budget avant | Budget apres |
|---|---|---|
| 2 fichiers, erreur simple | 6 | **5** |
| 8 fichiers, erreur simple | 6 | 6 |
| 25 fichiers, erreur simple | 6 | **7** |
| 25 fichiers, erreurs lourdes | 9 | **10** (= plafond dur, inchange) |
| Taille inconnue | 6 | 6 (retro-compatible) |

Tests : **782 -> 786 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeAutoCorrection.test.ts'
```

### Etat de satisfaction chantier

L asymetrie de finition entre projets simples et complexes est corrigee sans
toucher au plafond machine. Reste ouvert et assume : l escalade de modele reste
indexee sur le NUMERO de passe et non sur la trajectoire du score (asymetrie #5
du meme rapport) ; `isCorrectionScoreClimbing` existe et est deja consulte pour
prolonger la boucle, mais pas pour decider QUAND changer de modele.

## 2026-08-09 — Cloture de reprise: mesures finales et limites reelles

### Ce qui a ete verifie a la fin

| Mesure | Valeur |
|---|---|
| Suite Code | **786 verts, 0 echec** |
| Suite COMPLETE du depot | **4 646 tests, 4 643 verts, 0 echec, 3 ignores** |
| Typecheck, perimetre Code | **0 diagnostic** (31 au total, tous hors Code, allow-listes) |
| Modules de service Code | 158 (162 au debut de reprise) |
| Modules orphelins | **1** (4 au debut) |
| Symboles orphelins | **13** (19 au debut) |
| Parite bridge | **15/15** |
| Isolation WS7 | **10/10** |

### Limite d environnement rencontree, et pourquoi elle n invalide rien

Les generations reelles longues n ont pas pu etre menees jusqu au bout dans
cette session: les processus detaches sont recycles entre deux commandes, et une
generation complexe depasse la duree d une commande unique. Le meilleur run
observe est alle jusqu a **52 evenements, 9 fichiers ecrits, 3 validations
sandbox et 6 passes de correction** avant d etre recycle — le pipeline atteint
donc bien la validation et la boucle de correction.

Second facteur, decouvert en fin de reprise: **le bridge (port 3001) s est
arrete pendant la session**. Je ne l ai ni arrete ni redemarre, conformement a
la consigne de ne pas toucher au processus vivant. Cela explique l integralite
des `fetch failed` observes dans les runs live — assets inter-modules, preflight,
validation sandbox — qui sont tous des appels au bridge. Ce ne sont pas des
defauts du code livre.

Les preuves deterministes (tests, controle de parite, isolation Podman,
acceptation comportementale) ne dependent pas du bridge et restent valides.

### Ce qui reste ouvert, explicitement

1. **Boucle de REGENERATION esthetique** encore exclusive a l UI Tauri: elle
   depend d un serveur de dev lance via Tauri. Les trois canaux ont desormais la
   PORTE visuelle (score + critique), mais seul l UI declenche la repasse.
2. **13 symboles orphelins**, tries et justifies un par un dans l entree
   « Tri des orphelins » — dont 4 rendus caducs par le conteneur WS7 et qui
   partiront avec le retrait officiel du chemin hote.
3. **`codeStarterTemplates.ts`**, seul module orphelin restant: capacite reelle
   mais concurrente de la generation par plan. Trancher demande un choix produit.
4. **Escalade de modele indexee sur le numero de passe** et non sur la
   trajectoire du score (asymetrie #5). `isCorrectionScoreClimbing` existe deja
   et sert a prolonger la boucle, pas a decider du changement de modele.
5. **Pilotage comportemental** limite aux calculatrices et a deux criteres
   universels; chaque autre famille (tri, filtre, panier) demande son scenario.
6. **La route bridge n est active qu apres redemarrage du bridge**, qui est
   actuellement arrete.

## 2026-08-10 — Huit passes de correction contre une panne de reseau

### Reprise et diagnostic

Le bridge a ete redemarre (il etait arrete, GPU idle, aucun worker video/3D en
cours). Avant de relancer des generations, profilage des runs deja captures, a
partir des HORODATAGES du flux NDJSON — donc du temps reel, pas une estimation.

Un run est alle au bout: **167 evenements, 3 332 s (55 minutes)**. Sa
decomposition est accablante :

```
8 passes de correction, TOUTES a score 0, TOUTES sur la meme erreur: fetch failed
  attempt 1 strategy initial          errs ['fetch failed', ... lint=95%]
  attempt 2 strategy targeted_repair  errs ['fetch failed', ... lint=95%]
  attempt 3 strategy targeted_repair  errs ['fetch failed', ... lint=85%]
  attempt 4 strategy rewrite          errs ['fetch failed', ... lint=80%]
  attempt 5..8 strategy strategy_change  errs ['fetch failed', ... lint=80%]
```

La validation sandbox passe par le bridge; le bridge etait arrete. Le pipeline a
donc demande **huit fois** au modele de corriger du code a cause d une panne
d infrastructure qu aucune modification de code ne pouvait resoudre.

Le cout n est pas seulement du temps (~17 minutes de passes, escalade complete
`targeted_repair` -> `rewrite` -> `strategy_change` x4, 30 fichiers reecrits).
**La qualite a REGRESSE pendant l operation**: le score lint est passe de 95 % a
85 % puis 80 %. Le modele a degrade du code correct en cherchant une faute
inexistante.

C est une erreur de CATEGORIE: une validation qui n a pas pu s executer ne dit
rien sur le code.

### Recherches et choix

Le classifieur est volontairement ETROIT: on ne veut surtout pas requalifier une
vraie erreur de compilation en « probleme d environnement », ce qui masquerait
de vrais defauts. Deux conditions cumulatives pour declarer une panne
d infrastructure :

1. le resultat est en echec, ET
2. le `summary` porte une signature reseau/bridge, OU **toutes** les etapes en
   echec en portent une.

Un echec MIXTE (une etape reseau + une erreur de syntaxe) reste donc un echec de
code, et la boucle de correction tourne normalement. Verrouille par test.

Quand la panne est confirmee: on sort immediatement, et la degradation est
ecrite noir sur blanc dans la livraison (`## VALIDATION INDISPONIBLE`), en
precisant que ce n est PAS un defaut du code livre.

### Modifications realisees

- `src/services/codeInfrastructureFailure.ts` (nouveau) — classifieur etroit,
  note de livraison, et le traitement complet (notification, note, phase) pour
  garder la boucle mince.
- `src/services/codeValidationCorrectionLoop.ts` — sortie immediate sur panne
  d infrastructure. Quatre blocs d import compactes (pur formatage) pour rester
  sous la limite des 400 lignes.
- `src/__tests__/codeInfrastructureFailure.test.ts` (nouveau) — 10 tests.

### Avant-apres mesurable

| Situation | Avant | Apres |
|---|---|---|
| Sandbox injoignable (`fetch failed`) | **8 passes**, ~17 min brulees, lint 95 % -> 80 % | **0 passe**, sortie immediate, note explicite |
| Echec de compilation | boucle de correction | boucle de correction (inchange) |
| Echec mixte reseau + syntaxe | boucle | boucle (inchange, verrouille par test) |
| Sandbox vert | livraison | livraison (inchange) |

Tests : **786 -> 796 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeInfrastructureFailure.test.ts'

# le profil qui a revele le gaspillage, rejouable sur n importe quel flux capture
python3 - <<'EOF'
import json
ev=[json.loads(l) for l in open('output/code/audit_v91/e2e_final/_stream.ndjson') if l.strip()]
for e in ev:
    if e['kind']=='correction':
        print('attempt',e['attempt'],'score',e['score'],'strategy',e['strategy'],e['errors'][:1])
EOF
```

### Etat de satisfaction chantier

Le gaspillage le plus cher mesure sur ce module est supprime. Reste assume: la
detection repose sur des signatures de message; un mode de panne reseau au
libelle inedit passerait au travers et retomberait dans l ancien comportement.

## 2026-08-10 — Le juge notait 87/100 une page vide et cassee

### Reprise et diagnostic

Bridge redemarre, puis jugement du RESULTAT et non du cablage. Les fichiers du
run complet (167 evenements) ont ete extraits du flux NDJSON, servis, ouverts
dans Chromium, captures en desktop et mobile, et regardes.

Verdict de la porte source-statique sur cette page: **87/100, « Rendu visuel
acceptable »**. Verdict de l oeil et de la mesure sur le rendu:

- un **vide blanc d environ 1 000 px** en guise de hero;
- la plus grosse typographie de la page, sur 1440 px de large: **18 px**
  (echelle complete: 13/16/18) — donc aucune typo d affichage;
- familles reellement resolues par le navigateur: **Helvetica Neue et Georgia**,
  soit exactement les polices par defaut que le contrat design interdit;
- **0 image**, 0 ombre, 4 elements interactifs, un « Envoyer » sans style;
- accent cyan sans rapport avec la palette Mercedes;
- et la page est **CASSEE au chargement**: `ReferenceError: Lenis is not defined`,
  `SyntaxError: Unexpected identifier 'email'`.

La liste des fichiers livres raconte la meme histoire: `index.html` ET
`main.html`, plus `style-2.css`, `script-3.js`, `module-4.js`, `bloc-5.md` —
residus des huit passes de correction inutiles corrigees dans l increment
precedent.

**La cause est structurelle**: une porte qui lit la SOURCE est trompable par
construction. Le CSS peut declarer « Instrument Serif », des animations et une
echelle riche; si la police ne charge jamais et que le titre sort en 18 px, le
rendu est pauvre malgre une source flatteuse. Seul le rendu tranche.

### Recherches et choix

Le blocage historique — l audit rendu passe par `startDevServer` ->
`spawnWorkspaceCommand`, couple a Tauri — n en est plus un: un **serveur en
memoire** suffit a servir les fichiers livres, et Playwright/Chromium est deja
installe. Aucun serveur de dev, aucune dependance Tauri, donc le CLI et le
tunnel y ont acces.

La regle de notation est un module TS **pur** (`codeRenderedAestheticScore.ts`),
testable sans navigateur; le navigateur vit dans les scripts. La capture
manuelle et la porte automatique importent la MEME regle, elles ne peuvent donc
pas diverger.

Chaque seuil correspond a un defaut constate sur cette page, pas a une
intuition: >= 40 px pour la typo d affichage, >= 4 tailles distinctes, police
non-fallback, au moins un visuel, de la profondeur, une densite proportionnee a
la hauteur, >= 5 controles. Une erreur JavaScript au chargement est
**eliminatoire**: une page cassee ne peut pas passer, quel que soit son score.

La repasse esthetique est **bornee a UNE passe**: le budget VRAM ne supporte pas
davantage de rechargements de modele.

### Modifications realisees

- `src/services/codeRenderedAestheticScore.ts` (nouveau) — regle pure + critique
  actionnable citant la mesure constatee.
- `scripts/code_harness/render_audit.mjs` (nouveau) — sert, ouvre, mesure, note.
  Ne leve jamais: une panne de navigateur n empeche pas une livraison.
- `scripts/code_harness/aesthetic_capture.mjs` (nouveau) — captures desktop et
  mobile + metriques + verdict, pour inspection humaine.
- `scripts/code_harness/bridge_ndjson_runner.mjs` — audit de rendu emis en
  `visual.score` (`source: render_audit`), et **repasse esthetique ciblee**
  quand le rendu echoue, avec re-mesure apres coup.
- `src/__tests__/codeRenderedAestheticScore.test.ts` (nouveau) — 9 tests, dont
  les metriques REELLES de la page Mercedes.

### Avant-apres mesurable

| Juge | Note sur la MEME page livree |
|---|---|
| Porte source-statique (avant) | **87/100 — « Rendu visuel acceptable »** |
| Juge de rendu (apres) | **18/100 — echec** |

Detail du verdict de rendu :

```
FAIL runtime_clean       4 erreur(s): Lenis is not defined | SyntaxError ...
FAIL display_typography  plus grande taille rendue: 18px
FAIL type_scale          3 taille(s): 13/16/18
FAIL real_typeface       familles resolues: Helvetica Neue, Georgia
FAIL visual_content      0 image(s)/svg, 0 canvas
FAIL interactivity       4 element(s) interactif(s)
PASS depth / content_density
```

Parite du canal tunnel: **15/15**. Tests : **796 -> 805 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node scripts/code_harness/aesthetic_capture.mjs \
  output/code/audit_v92/mercedes_full \
  --out output/code/audit_v92/mercedes_full/_shots \
  --json output/code/audit_v92/mercedes_full/_shots/report.json
jq '.verdict | {score, passed, failedChecks}' output/code/audit_v92/mercedes_full/_shots/report.json
node --experimental-strip-types --test 'src/__tests__/codeRenderedAestheticScore.test.ts'
```

Captures: `output/code/audit_v92/mercedes_full/_shots/desktop.png` et
`mobile.png`.

### Etat de satisfaction chantier

Le juge ne peut plus qualifier d acceptable une page vide et cassee, et la
repasse esthetique existe desormais hors UI Tauri. Reste ouvert et assume :

- la repasse est bornee a UNE passe et n est pas encore verifiee sur un cycle
  complet degrade -> regenere -> ameliore, faute de pouvoir mener une generation
  longue au bout dans cet environnement;
- le juge mesure la FORME (typo, profondeur, densite, erreurs) et non le GOUT:
  il ne dira pas qu une palette est laide, seulement qu elle est plate ou
  par defaut.

## 2026-08-10 — Aurora ecrasait son propre design

### Reprise et diagnostic

Le juge etait repare (87 -> 18), mais la page restait ratee: on avait soigne le
thermometre, pas la fievre. Retour a la cause sur le run Mercedes, en lisant le
code REELLEMENT livre.

**Premiere surprise: le modele avait raison.** Son CSS contient
`--font-display: clamp(40px, 5vw, 96px)` et `h1 { font-size: var(--font-display) }`.
Le titre AURAIT du sortir entre 40 et 96 px.

**La coupable est Aurora.** `codeProjectSupportFiles.ts` injecte dans chaque page
HTML un bloc de theme suivi de `<script src="https://cdn.tailwindcss.com">`. Le
**Preflight** de Tailwind remet `h1 { font-size: inherit }` — et comme il est
injecte au runtime, il gagne la cascade sur la feuille de l auteur.

Le declencheur? Une regex qui matchait `class="container"`. Le commentaire du
fichier admettait deja le probleme (« the utility-class heuristic below
false-positives on plain class names like "container" ») mais ne l avait
neutralise que pour `game_web`.

**Preuve par la mesure.** Meme page, bloc injecte retire, re-rendue:

| Mesure | Avec injection Aurora | Sans |
|---|---|---|
| Echelle typographique | `[13, 16, 18]` | **`[13, 16, 18, 19, 24, 72]`** |
| `display_typography` | echec | **passe** |
| `type_scale` | echec | **passe** |
| Score de rendu | 18/100 | **46/100** |

**Deuxieme cause: une URL de CDN inventee.** Le modele a ecrit
`lenis@1.0.48/dist/lenis.min.js` — verifie: **404** — puis appele `new Lenis(...)`.
Le bloc `autoDepsBlock` NOMMAIT Lenis sans jamais donner son adresse. Le registre
`CODE_DESIGN_CDN_LIBS` contient pourtant l URL correcte (`lenis@1/dist/...`,
verifiee 200), elle n etait simplement pas transmise. Nommer ne suffit pas: il
faut fournir.

**Troisieme point, verifie et NON confirme comme bug.** L accent cyan semblait
hors charte. Verification du profil de marque: `Mercedes-Benz` a bien
`primaryColor: '#00ADEF'`. Le verrouillage de marque a donc fonctionne
correctement — le cyan EST la couleur declaree. Il paraissait faux parce qu il
etait pose en accent vif sur une page par ailleurs non stylee, pas parce que la
palette avait ete manquee. Aucune correction apportee: il n y avait rien a
corriger.

### Modifications realisees

- `src/services/codeProjectSupportFiles.ts` —
  - `corePlugins:{preflight:false}` dans la config injectee: Tailwind ne
    reinitialise plus la typographie de l auteur;
  - declencheur resserre sur du vocabulaire SANS ambiguite (tokens numeriques,
    prefixes responsives, vocabulaire Aurora). `flex`, `grid`, `hidden` et
    `container` ne declenchent plus rien;
  - une page qui apporte deja sa propre feuille de style n est plus touchee.
- `src/services/codeDesignDirectiveBlocks.ts` — `autoDepsBlock` livre les **URL
  exactes** des 11 librairies du registre + regle dure « tout global appele DOIT
  avoir sa balise script prise dans cette liste ». Nouveau
  `typographyContractBlock` avec des seuils MESURABLES.
- `src/services/codeExecutorQualityContract.ts` — contrat typographique cable et
  place en tete des blocs esthetiques (il etait tronque par le budget), budget
  visuel porte a 16 000 caracteres.
- `src/__tests__/codeTailwindInjectionGuard.test.ts` (nouveau) — 5 tests.
- `src/__tests__/codeExecutorQualityContract.test.ts` — 4 tests de regression.

**Alignement juge/directive**: le juge mesure « hero >= 40 px, >= 4 tailles,
police non-fallback »; la directive exige desormais `clamp(48px, 7vw, 96px)`,
quatre tailles minimum et une balise `<link>` Google Fonts. Les deux bouclent sur
le meme seuil, au lieu de noter une regle jamais demandee.

### Avant-apres mesurable

| Contrat livre au codeur | Avant | Apres |
|---|---|---|
| URL Lenis exacte | absente (modele inventait un 404) | **fournie et verifiee 200** |
| Seuil hero `clamp(48px…)` | absent | **present** (markup + style) |
| Chargement reel de police | absent | **exige** |
| Verrouillage marque | present | present (inchange) |

Tests : **805 -> 814 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeTailwindInjectionGuard.test.ts'

# la preuve du mecanisme: meme page, bloc injecte retire
node scripts/code_harness/aesthetic_capture.mjs output/code/audit_v92/mercedes_nopreflight \
  --out output/code/audit_v92/mercedes_nopreflight/_shots \
  --json output/code/audit_v92/mercedes_nopreflight/_shots/report.json
jq '.viewports.desktop.fontSizeScale, .verdict.score' \
  output/code/audit_v92/mercedes_nopreflight/_shots/report.json   # [13,16,18,19,24,72] / 46
jq '.viewports.desktop.fontSizeScale, .verdict.score' \
  output/code/audit_v92/mercedes_full/_shots/report.json          # [13,16,18] / 18

# les URL du registre sont joignables
curl -o /dev/null -w '%{http_code}\n' https://cdn.jsdelivr.net/npm/lenis@1/dist/lenis.min.js       # 200
curl -o /dev/null -w '%{http_code}\n' https://cdn.jsdelivr.net/npm/lenis@1.0.48/dist/lenis.min.js  # 404
```

### Etat de satisfaction chantier

Les trois leviers pipeline sont epuises: le framework n ecrase plus le design,
les dependances sont fournies au lieu d etre devinees, et le seuil typographique
est exige dans les memes termes qu il est mesure. Reste ouvert et assume: ces
corrections agissent sur la PROCHAINE generation; la page deja livree sert de
cas de regression, elle n est pas retro-corrigee.

## 2026-08-10 — Asymetrie #5: l'escalade suivait le compteur, pas la trajectoire

### Reprise et diagnostic

Dette documentee depuis juillet. Lecture de `buildCorrectionStrategy`:

```ts
if (isStagnating) escalation = Math.min(5, attempt)
else              escalation = Math.min(5, Math.ceil(attempt / 2))
```

La stagnation etait bien prise en compte, mais la branche NORMALE restait
indexee sur le numero de passe. Consequence: un run dont le score **monte**
franchement (10 -> 50 -> 80) changeait quand meme de modele toutes les deux
passes. Or chaque changement d escalade recharge un gros modele, et c est la
premiere cause de swap VRAM sur cette machine (18,6 Go de modele sur 16 Go de
GPU). On payait donc un risque de gel pour punir un run qui progressait.

`isCorrectionScoreClimbing` existait deja et servait a PROLONGER la boucle — mais
pas a decider du changement de modele.

### Modifications realisees

- `src/services/codeAutoCorrection.ts` — trois regimes explicites: stagnation ->
  escalade rapide, progression -> escalade freinee (`min(2, ceil(attempt/3))`,
  on garde le modele), sinon comportement historique. Deux blocs d import
  compactes pour rester sous 400 lignes.
- `src/__tests__/codeAutoCorrection.test.ts` — le test encodait l ANCIEN
  comportement sur un log qui grimpe; il exprime desormais l intention, et un
  test compare les deux trajectoires a numero de passe EGAL.

### Avant-apres mesurable

| Trajectoire (passe 3) | Escalade avant | Apres |
|---|---|---|
| Score 10 -> 50 -> 80 (grimpe) | 2 | **1** |
| Score 40 -> 41 -> 42 (patine) | 2 | **2** |
| Stagnation detectee | 3 | 3 (inchange) |

A numero de passe egal, un run qui patine escalade desormais STRICTEMENT plus
qu un run qui progresse — ce qui n etait pas le cas avant.

Tests : **814 -> 815 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeAutoCorrection.test.ts'
```

### Etat de satisfaction chantier

L escalade suit la trajectoire. Reste assume: le seuil de « progression » vient
de `isCorrectionScoreClimbing` (3 passes, +5 points minimum); un run qui
progresse tres lentement est encore traite comme un run qui patine.

## 2026-08-10 — Run complexe reel: trois defauts que seul le reel revele

### Reprise et diagnostic

Run de bout en bout sur un brief volontairement lourd (plateforme SaaS
analytics: accueil marketing + tableau de bord avec graphiques reels + nav
responsive + theme sombre + interaction animee + formulaire). Le pipeline a
planifie **25 fichiers**.

**Daemonisation** — le blocage des tours precedents est resolu. `tmux` et
`screen` sont absents de l hote; la forme qui survit est:

```bash
setsid nohup node scripts/code_harness/bridge_ndjson_runner.mjs \
  > output/code/audit_v93/stream.ndjson 2> output/code/audit_v93/run.log \
  < output/code/audit_v93/payload.json & disown
echo $! > output/code/audit_v93/run.pid
```

Piege coute un run: mettre `< /dev/null` APRES la redirection d entree ecrase
celle-ci (la derniere gagne) — le runner recevait un prompt vide et sortait
aussitot. L ordre des redirections compte.

### Ce que le run a prouve

- **Le garde-fou semantique tient sur un brief different.** Le modele a de
  nouveau classe la demande en `ide` — quatrieme reproduction — et le garde l a
  ecarte: `Classification semantique ecartee (ide non corrobore) -> spa_vue`.
  C est exactement la degradation « IDE au lieu du produit demande », desormais
  empechee en conditions reelles.
- **Le plan respecte le type et la porte d entree**: 25 fichiers, `index.html`
  genere en premier.
- **La porte visuelle de rendu s execute sur le canal tunnel** (evenement
  `visual.score`, `source: render_audit`).

### Trois defauts trouves, que seule une vraie execution revele

**1. Le repli de quota WS7 etait inerte.** Mesure directe sur le bridge:

```
podman volume create --opt o=size=768m …  -> exitCode 125, output ""
podman volume create (sans --opt)          -> exitCode 0
```

`/api/command/run` ne renvoie PAS stderr. Mon repli testait
`isVolumeQuotaUnsupportedError(create.output)` — sur une chaine vide, il ne
matchait jamais. Le run a donc brule **sept passes de correction** sur
« Quota disque total WS7 indisponible », scores plats (40/25/33/33/33/33/33).
Le quota disque est une garantie SOUPLE: on reessaie desormais sans lui **quelle
que soit la raison** de l echec, sans dependre d un message absent.

**2. Le classifieur d infrastructure ne couvrait que le reseau.** Meme erreur de
categorie que `fetch failed` — le juge n a pas pu etre CONSTRUIT — mais une
signature differente. Les pannes de provisionnement du sandbox sont ajoutees.

**3. Mon propre juge de rendu notait ce qu il ne pouvait pas juger.** Le projet
etant un SPA Vue, son `index.html` pointe `/src/main.ts`, que seul un build
resout. Servi tel quel, il donne une page blanche: le juge a rendu **10/100** et
declenche une repasse esthetique inutile. Un score de 10 ne disait rien du
design, seulement qu il manquait un build. Le juge repond desormais
`applicable:false` sur un projet a bundler au lieu de fabriquer un verdict.

### Avant-apres mesurable

| Situation | Avant | Apres |
|---|---|---|
| `volume create --opt` refuse, stderr vide | repli inerte -> 7 passes brulees | repli inconditionnel, isolation conservee |
| Panne de provisionnement sandbox | traitee comme defaut de code | classee infrastructure, boucle arretee |
| Projet a bundler passe au juge de rendu | note 10/100 + repasse inutile | `applicable:false`, aucune repasse |

Tests : **815 -> 819 verts, 0 echec.**

### Performance mesuree sur ce run

- 25 fichiers planifies, **~28 s par fichier** en generation.
- Pic **VRAM 15 171 MiB / 16 303**, pic **RAM 12 205 MiB / 30 Go**.
- GPU a 22-24 % d utilisation: le modele de 18,6 Go ne tient pas dans 16 Go de
  VRAM, il deborde en RAM — le facteur limitant est materiel, pas logiciel.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeSandboxWorkspace.test.ts'
node --experimental-strip-types --test 'src/__tests__/codeInfrastructureFailure.test.ts'

# la mesure qui a revele le repli inerte
curl -s -X POST http://127.0.0.1:3001/api/command/run -H 'Content-Type: application/json' \
  -d '{"executable":"podman","args":["volume","create","--opt","o=size=768m","t1"],"cwd":"/tmp"}'
```

### Etat de satisfaction chantier

Les trois defauts sont corriges et testes. Reste ouvert et assume: juger
l esthetique d un projet a bundler demande un `npm install && build` reel avant
capture — non fait ici.

## 2026-08-10 — Un patch introuvable detruisait 46 minutes de travail

### Reprise et diagnostic

Le run complexe precedent est mort ainsi, apres **36 fichiers emis et 46
minutes**:

```
[CodeOrchestrator] Pipeline fatal error: agentic_retry_failed:patch_search_not_found
```

Deux defauts distincts s additionnaient.

**1. La recherche etait litterale.** `apply_patch` exigeait
`file.content.includes(action.search)`. Or le modele reconstitue le bloc a
chercher de MEMOIRE: une indentation de 2 au lieu de 4 espaces, une tabulation
convertie, un espace en fin de ligne, et la recherche echoue alors que le texte
est present a l identique aux blancs pres.

**2. L echec etait disproportionne.** Un seul patch rate sur un fichier
`required` faisait remonter `ok:false` -> `agentic_retry_failed` -> erreur
fatale. Le fichier existait pourtant, ecrit et valide. On perdait tout le run
pour une recherche de texte.

### Recherches et choix

- **Egalite stricte d abord**, puis repli INSENSIBLE AUX BLANCS. Le repli
  parcourt le contenu avec deux curseurs qui sautent les blancs des deux cotes,
  et rend les indices REELS du fichier d origine — le remplacement ne touche
  donc ni l indentation voisine ni les fins de ligne.
- `all: true` reste sur correspondance stricte uniquement: repeter une
  recherche floue sur un fichier entier ferait plus de degats que de bien.
- **Degradation proportionnee**: un `patch_search_not_found` sur un fichier deja
  ecrit et non vide est trace (`patch_ignore:`) et la file continue. La boucle de
  correction re-jugera le livrable. On n abandonne plus 46 minutes de travail
  pour un bloc de texte introuvable.

### Modifications realisees

- `src/services/codePatchMatching.ts` (nouveau) — `findPatchTarget` et
  `applyPatchToContent`.
- `src/services/codeGenerationTools.ts` — `apply_patch` passe par le matcher
  tolerant.
- `src/services/codeGenerationExecutor.ts` — echec de patch non fatal quand la
  cible existe deja.
- `src/__tests__/codePatchMatching.test.ts` (nouveau) — 11 tests.

### Avant-apres mesurable

| Recherche du modele | Avant | Apres |
|---|---|---|
| Bloc exact | trouve | trouve (strategie `exact`, prioritaire) |
| Sur-indentation (8 espaces vs 4) | **echec fatal** | trouve |
| Tabulation au lieu d espaces | **echec fatal** | trouve |
| Espace en fin de ligne | **echec fatal** | trouve |
| Bloc multi-lignes mal re-indente | **echec fatal** | trouve |
| Texte reellement absent | echec | echec (inchange, verrouille par test) |
| Identifiant proche (`messages` vs `message`) | — | **non confondu** |

| Consequence d un patch introuvable | Avant | Apres |
|---|---|---|
| Fichier cible deja ecrit | **run entier perdu** | trace, file poursuivie |

Tests : **819 -> 830 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codePatchMatching.test.ts'
```

Trace de la panne d origine: `output/code/audit_v93/run.log` (derniere ligne).

### Etat de satisfaction chantier

Le mode d echec qui a coute le run le plus long de la session est traite des
deux cotes: la recherche pardonne les blancs, et son echec ne condamne plus la
livraison. Reste assume: le repli ignore les blancs, pas les differences
reelles de code — un bloc que le modele a paraphrase reste introuvable, et c est
voulu (patcher approximativement serait pire).

## 2026-08-10 — Orphelins: le chemin d'installation sur l'HOTE est mort

### Reprise et diagnostic

Quatre des treize symboles orphelins formaient une famille coherente:
`checkRuntimeAvailable`, `autoInstallRuntime`, `getExecutableRuntimeSpec` et
`getRuntimeSpec`. Tous servaient a detecter puis INSTALLER un runtime sur la
machine hote (winget, brew, apt) avant d executer le code genere.

Depuis que WS7 s execute reellement dans un conteneur Podman avec une image par
langage (`python:3.12-slim`, `node:22-bookworm-slim`...), le runtime est fourni
par l image: installer quoi que ce soit sur l hote n a plus de sens, et ne
devrait plus jamais arriver pendant une generation.

Verification avant suppression: `codeSandboxRuntime.ts` n etait importe que pour
`isWindows` et `nodeExecutable`; les trois autres exports n avaient **aucun**
consommateur. `getRuntimeSpec` etait re-exporte par `codeSandboxCommands.ts`
sans que personne ne le consomme — une chaine de re-export morte.

### Note de methode

Le decoupeur automatique de fonctions a de nouveau echoue, differemment: il
prenait l accolade de `Promise<{ ok: boolean; output: string }>` pour celle du
CORPS, et coupait au mauvais endroit. Les fichiers ont ete restaures depuis HEAD
et la suppression refaite par plages de lignes explicites, verifiee par un
chargement reel du module (`import()` + liste des exports) avant de lancer la
suite. Lecon: sur du TypeScript, apparier les accolades sans tenir compte des
types generiques ne suffit pas.

### Modifications realisees

- `src/services/codeSandboxRuntime.ts` — 151 -> 17 lignes; ne garde que
  `isWindows` et `nodeExecutable`, seuls exports reellement consommes. Imports
  devenus inutiles retires.
- `src/services/codeSandboxLaunchRuntime.ts` — `getRuntimeSpec` supprime,
  import `AutoInstallSpec` retire.
- `src/services/codeSandboxCommands.ts` — re-export mort nettoye.
- `src/__tests__/codeSandboxModules.test.ts` — les 3 tests des fonctions
  supprimees partent avec elles.

### Avant-apres mesurable

| Mesure | Avant | Apres |
|---|---|---|
| Symboles orphelins | 13 | **9** |
| `codeSandboxRuntime.ts` | 151 lignes | **17 lignes** |
| Typecheck perimetre Code | 0 diagnostic | **0 diagnostic** |
| Suite Code | 830 verts | 827 verts (les tests des fonctions supprimees partent avec elles) |

### Demonstration reproductible

```bash
cd application
node scripts/code_harness/orphan_scan.mjs --json output/code/audit_v94/orphan_scan.json
node --experimental-strip-types -e "import('./src/services/codeSandboxRuntime.ts').then(m=>console.log(Object.keys(m)))"
```

### Etat de satisfaction chantier

Neuf symboles orphelins restent, chacun avec sa raison documentee. Aucun n est
un vestige d architecture comme l etait le chemin d installation hote: ce sont
des capacites reelles non encore branchees (`detectDeadCode`,
`resolveToolPackageVersion`, `executeCodeGenerationToolSequence`, le writer
disque) ou des moities de protocole (`parseCodeStreamEventLine`). Les brancher
demande une integration raisonnee, pas un appel decoratif.

## 2026-08-10 — Le sandbox accusait le quota disque pour une image absente

### Reprise et diagnostic

Le run complexe `runId=940` (25 fichiers planifies, 32 livres) s est termine sur:

```
## VALIDATION INDISPONIBLE
La validation sandbox n a pas pu s executer: Quota disque total WS7
indisponible pour le workspace conteneurise.
Ce n est PAS un defaut du code livre.
```

**Premier constat, positif**: le garde d infrastructure livre a l increment
precedent a FONCTIONNE. La boucle de correction s est arretee immediatement
(« livraison sans passe de correction ») au lieu de bruler sept a huit passes
comme le run precedent sur la meme famille de panne. Le comportement corrige se
verifie donc en conditions reelles.

**Second constat**: le message etait FAUX, et il m a envoye chercher au mauvais
endroit. Verification directe:

```
podman volume create --ignore --label ... aurora-diag-1   -> exitCode 0   (le volume passe)
podman run --pull=never node:22-bookworm-slim echo ok     -> "image not known"
podman images -> python:3.12-slim, alpine  (pas de node)
```

La creation du volume reussit. C est l ETAPE D INIT qui echoue, parce que le
projet est un SPA Vue -> langage `node` -> image `node:22-bookworm-slim`, jamais
telechargee sur cet hote, et `--pull=never` interdit de la recuperer pendant une
generation.

`prepareSandboxWorkspaceVolume` renvoyait un `ok:false` nu; l appelant
retombait sur un libelle code en dur mentionnant le quota disque — quelle que
soit la cause reelle. **Le sandbox WS7 etait donc silencieusement indisponible
pour TOUT projet JS/TS sur cet hote, en accusant le disque.**

### Modifications realisees

- `src/services/codeSandboxWorkspace.ts` — le resultat porte desormais
  `failedStage` (`volume` | `init`) et un `reason` actionnable. L image absente
  est reconnue (`image not known`) et nommee, avec la consigne
  (`podman pull` hors generation, puisque `--pull=never` est deliberé).
- `src/services/codeSandbox.ts` — relaie le vrai diagnostic au lieu du libelle
  quota code en dur.
- `src/services/codeInfrastructureFailure.ts` — le classifieur suit le nouveau
  libelle, sinon la boucle recommencerait a bruler des passes.
- `src/__tests__/codeInfrastructureFailure.test.ts` — 2 tests.
- Image `node:22-bookworm-slim` telechargee sur l hote; verifiee:
  `podman run --pull=never node:22-bookworm-slim` -> `WS7_NODE_OK`.

### Avant-apres mesurable

| Situation | Avant | Apres |
|---|---|---|
| Image langage absente | « Quota disque total WS7 indisponible » (faux) | « Sandbox WS7 indisponible (init): image conteneur absente pour "node" — lancez podman pull » |
| Volume refuse | meme message | « (volume): creation du volume refusee » |
| Projet JS/TS sur cet hote | sandbox muette, cause introuvable | image presente, `WS7_NODE_OK` verifie |
| Boucle de correction sur cette panne | 7-8 passes brulees (run precedent) | **0 passe** (verifie sur ce run) |

Tests : **827 -> 829 verts, 0 echec.**

### Performance mesuree sur `runId=940`

| Mesure | Valeur |
|---|---|
| Fichiers planifies / livres | 25 / **32** |
| Temps au premier fichier | **206 s** |
| Generation des 25 fichiers | **875 s** |
| Total jusqu a livraison | **1 013 s (16,9 min)** |
| Pic VRAM | **15 172 MiB / 16 303** |
| Pic RAM | 11 899 MiB / 30 720 |
| Passes de correction gaspillees | **0** (contre 7-8 au run precedent) |

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeInfrastructureFailure.test.ts'
podman run --rm --pull=never --network=none docker.io/library/node:22-bookworm-slim node -e "console.log('WS7_NODE_OK')"
```

### Etat de satisfaction chantier

Le sandbox ne ment plus sur la cause de son indisponibilite, et il fonctionne
desormais pour les projets JS/TS sur cet hote. Reste assume: chaque langage
demande son image pre-telechargee; les autres (rust, go, java, gcc) echoueront
tant qu elles ne le sont pas — mais elles le DIRONT desormais clairement.

## 2026-08-10 — Le build echouait a cause d'Aurora, le rendu a cause du modele

### Reprise et diagnostic

Le projet livre par `runId=940` (SaaS analytics Vue, 32 fichiers) a ete
reellement installe, builde, servi et REGARDE.

**1. `npm install` -> OK. `vite build` -> ECHEC.**

```
[vite:build-import-analysis] src/app.vue (5:8): Failed to parse source for
import analysis... Install @vitejs/plugin-vue to handle .vue files.
```

Cause: `vite.config.ts` importait **`@vitejs/plugin-react`** et appelait
`react()` — dans un projet **Vue**, dont le `package.json` declarait pourtant
correctement `@vitejs/plugin-vue`. Le fichier venait d Aurora:
`ensureSpaViteConfig` injectait une config REACT pour TOUT projet `spa_*`.
**Aurora rendait donc inconstruisible un livrable correct** — meme famille que
l injection Tailwind corrigee plus tot.

Preuve: en remplacant la seule config par son equivalent Vue,
`vite build` -> **exit 0**, `dist/index.html` + 283 Ko de JS + 25 Ko de CSS en
954 ms. Rien d autre n a ete touche.

**2. Mon propre outil de capture jugeait une page vide.**

Premier rendu du build: en-tete seul, corps vide, 52/100. L application utilise
`createWebHistory`; la capture ouvrait `/index.html`, qui ne correspond a AUCUNE
route — le `<router-view>` restait donc vide. Ce n etait pas l application qui
etait vide, c etait la facon de la servir. Corrige: repli SPA (tout chemin sans
extension rend `index.html`) et navigation sur la RACINE.

Apres correction, la meme page mesure:
`[13,14,16,18,20,24,28,32,40,48,96]` px de typo, 7 sections, 30 images,
40 controles, 3 099 px de haut, **80/100, aucune erreur runtime**.

**3. Le rendu reste plat — et cette fois c est le MODELE.**

Le CSS embarque utilise `var(--accent)`, `var(--bg)`, `var(--card-bg)`,
`var(--border)`… et le bundle ne contient **aucune definition** de ces
variables. Verification: `main.ts` n importe **aucun** CSS, alors que le modele
a bien ecrit une feuille de tokens dans `src/assets/styles/`. Jamais importee ->
chaque `var()` est invalide -> la declaration est jetee -> fond unique, une
seule couleur de texte, zero ombre, police serif par defaut.

Contrairement aux points 1 et 2, ce defaut n est pas d Aurora: le modele a
oublie l import global.

### Modifications realisees

- `src/services/codeProjectSupportFiles.ts` — la config Vite injectee suit le
  framework: `spa_react` -> plugin-react, `spa_vue` -> plugin-vue,
  `spa_svelte` -> plugin-svelte, sinon aucun plugin plutot qu un faux.
- `scripts/code_harness/aesthetic_capture.mjs` et `render_audit.mjs` — repli SPA
  et navigation racine, sinon toute application en history mode est jugee vide.
- `src/__tests__/codeTailwindInjectionGuard.test.ts` — 4 tests.

### Avant-apres mesurable

| Etape | Avant | Apres |
|---|---|---|
| `vite build` du projet Vue livre | **echec** (plugin React) | **exit 0**, 283 Ko JS + 25 Ko CSS en 954 ms |
| Rendu mesure par la capture | 52/100, corps vide | **80/100**, 7 sections, 30 images, 40 controles |
| Typo maximale rendue | 24 px | **96 px** |
| Erreurs runtime | 0 | 0 |

### Jugement esthetique honnete

**Structurellement complet**: en-tete + navigation + bascule de theme, hero avec
accroche et deux CTA, 6 cartes de fonctionnalites, 3 paliers tarifaires
($29/$79/$199) avec listes et CTA, tableau comparatif, temoignage avec portrait,
FAQ en accordeon (5 questions), pied de page a 4 colonnes avec inscription
newsletter. La demande (1) du brief est reellement honoree.

**Mais ce n est PAS premium.** En directeur artistique: tout est centre dans une
colonne etroite sans grille; les « cartes » n en sont pas (ni fond, ni bordure,
ni ombre); les icones sont des EMOJI, signature du prototype et non du produit;
les boutons sont ceux du navigateur; « HomeDashboard » colle faute d espacement;
le tableau comparatif n affiche que des tirets; de grands vides verticaux
subsistent; et toute la page tombe en Times New Roman.

L essentiel de ces defauts decoule d une seule cause: **les tokens de design ne
sont jamais charges**. Le squelette est bon, l habillage n arrive pas.

### Performance complete de `runId=940`

| Mesure | Valeur |
|---|---|
| Temps au premier fichier | 206 s |
| Generation des 25 fichiers | 875 s |
| Total jusqu a livraison | **1 013 s (16,9 min)** |
| `npm install` + `vite build` | ~35 s |
| **Total bout en bout** | **~17,5 min** |
| Pic VRAM | 15 172 MiB / 16 303 |
| Pic RAM | 11 899 MiB / 30 720 |
| Passes de correction gaspillees | **0** (contre 7-8 au run precedent) |

### Demonstration reproductible

```bash
cd application/output/code/audit_v94/project
npm install --no-audit --no-fund && npx vite build   # exit 0 avec la config Vue
cd /home/juan/AuroraIA/application
node scripts/code_harness/aesthetic_capture.mjs output/code/audit_v94/project/dist \
  --out output/code/audit_v94/shots --json output/code/audit_v94/shots/report.json
jq '.verdict | {score, passed, failedChecks}' output/code/audit_v94/shots/report.json
```

Captures: `output/code/audit_v94/shots/desktop.png` et `mobile.png`.

### Etat de satisfaction chantier

Les deux causes cote OUTILLAGE sont corrigees et testees. Reste le dernier
obstacle, precis et identifie: **rien ne verifie que les tokens de design
utilises sont reellement definis et charges**. Une porte deterministe — toute
variable `var(--x)` employee doit avoir une definition dans le CSS effectivement
charge, et un projet a bundler doit importer sa feuille globale — aurait attrape
ce cas ET le cas Mercedes. C est le prochain chantier, non fait ici.

## 2026-08-10 — Une variable CSS non chargee jetait tout l'habillage

### Reprise et diagnostic

Dernier obstacle identifie au tour precedent, traite ici. Le SaaS analytics Vue
livre par `runId=940` buildait, ne produisait aucune erreur runtime, et sortait
pourtant **entierement plat**: Times New Roman, un seul fond, une seule couleur
de texte, zero ombre.

Cause exacte: le CSS employait `var(--accent)`, `var(--bg)`, `var(--card-bg)`…
et le bundle ne contenait **aucune definition** de ces variables. Le modele
avait bien ecrit `src/assets/styles/variables.css` avec tous les tokens — mais
`main.ts` n importait **aucun** CSS. La feuille existait sur le disque et n etait
jamais chargee. Or le navigateur JETTE silencieusement toute declaration dont la
variable est inconnue: le CSS parait correct a la lecture, et ne peint rien.

**Verification de l hypothese partagee sur le cas Mercedes: elle est FAUSSE.**
Passe a la meme porte, le projet Mercedes (`audit_v92/mercedes_full`) ressort
`ok: true` — ses 16 variables utilisees sont toutes definies dans la feuille
reellement liee. Sa platitude venait du Preflight Tailwind (corrige au tour 4),
pas d une resolution de tokens. Les deux cas ne partagent donc PAS le meme
mecanisme, et la porte ne doit pas se voir crediter d un cas qu elle n attrape
pas.

### Recherches et choix

La porte raisonne sur le **graphe de chargement**, pas sur la presence des
fichiers — c est tout l objet: *une definition presente sur disque mais jamais
importee compte comme absente*.

- HTML statique: `<link rel=stylesheet>` + `<style>` de la page, `@import`
  suivis transitivement.
- Projet a bundler: CSS importe par le point d entree JS, suivi transitivement
  a travers les modules intermediaires.
- Composants monofichiers (`.vue`, `.svelte`): leur bloc `<style>` est compile
  avec le composant, donc toujours charge — il compte.
- Cas limite traite: un token pose en JS (`setProperty('--x', …)`) compte comme
  defini, sinon un theme applique dynamiquement serait signale a tort.
- Cas limite assume: un nom de variable **calcule** a l execution est
  indetectable statiquement. La porte ne le voit pas et ne pretend pas le voir.

### Modifications realisees

- `src/services/codeDesignTokenGate.ts` (nouveau) — `collectLoadedCss`,
  `checkDesignTokens`, critique nommant les variables orphelines ET la feuille
  a importer, avec le chemin du point d entree.
- `src/services/codePipelineFinalization.ts` — porte cablee: un livrable dont
  l habillage ne charge pas est **plafonne a 70** et emporte la consigne de
  correction, comme les portes de marque et de rendu.
- `src/__tests__/codeDesignTokenGate.test.ts` (nouveau) — 11 tests, dont les
  trois demandes: defini+importe = passe, defini mais non importe = echoue,
  jamais defini = echoue.

### Avant-apres mesurable — sur les DEUX cas reels

Porte appliquee aux projets tels qu ils ont ete livres:

| Projet | Verdict | Tokens orphelins | Feuille non chargee |
|---|---|---|---|
| SaaS Vue (`audit_v94`) | **echec** | **37** | `src/assets/styles/variables.css` |
| Mercedes (`audit_v92`) | passe | 0 | aucune |

Puis application du correctif EXACT que la porte prescrit (ajouter l import de
la feuille de tokens dans `main.ts`), rebuild, re-capture:

| Mesure du rendu | Avant | Apres |
|---|---|---|
| Police reellement resolue | **Times New Roman** | **Inter** |
| Fonds distincts | 1 | **4** |
| Rayons distincts | 1 | **5** |
| Ombres distinctes | 0 | **1** |
| Couleurs de texte | 1 | 2 |
| Hauteur de page | 3 099 px | **5 263 px** |
| Verdict du juge de rendu | 80/100 | **100/100, 0 echec** |
| Erreurs runtime | 0 | 0 |

Build: `vite build` -> exit 0, CSS de 25,3 Ko -> **28,7 Ko** (les tokens entrent
enfin dans le bundle).

### Jugement visuel, capture regardee

Transformation reelle, verifiee a l oeil sur
`output/code/audit_v94/shots_after/desktop.png`: la navigation est espacee
(« Home  Dashboard » au lieu de « HomeDashboard »), les titres de section
portent l accent indigo de la marque, les fonctionnalites sont de VRAIES cartes
(fond, bordure, rayon, ombre) sur une grille 3 colonnes, les tarifs sont trois
cartes dont « Professional » est mise en avant par une bordure d accent avec un
CTA plein, le tableau comparatif est cadre proprement, le temoignage est une
carte avec portrait, la FAQ est un accordeon borde, et le pied de page tient sur
4 colonnes.

**Ce n est pourtant pas encore « fini ».** Trois defauts subsistent, visibles:
le hero reste un grand vide et ses deux libelles se CHEVAUCHENT (« Get Started »
et « Scroll to explore » se superposent); les icones sont des EMOJI, signature
du prototype; le tableau comparatif n affiche que des tirets, sans donnees.

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeDesignTokenGate.test.ts'

# la porte sur les deux projets reels
node scripts/code_harness/orphan_scan.mjs >/dev/null   # env headless
cd output/code/audit_v94/project && npx vite build && cd -
node scripts/code_harness/aesthetic_capture.mjs output/code/audit_v94/project/dist \
  --out output/code/audit_v94/shots_after --json output/code/audit_v94/shots_after/report.json
jq '.verdict | {score, passed, failedChecks}' output/code/audit_v94/shots_after/report.json
```

Captures avant/apres: `output/code/audit_v94/shots/desktop.png` (plat, serif) et
`output/code/audit_v94/shots_after/desktop.png` (habille, Inter).

### Etat de satisfaction chantier

La porte ferme le mecanisme identifie: un habillage qui ne charge pas ne peut
plus etre livre en silence. Reste precisement, et c est different de ce qui
precedait: le CONTENU du hero (vide + chevauchement de deux libelles), les
icones emoji, et un tableau comparatif sans donnees. Ce ne sont plus des
mecanismes caches — ce sont des defauts de composition que le juge de rendu ne
mesure pas encore (il compte les tailles, les fonds et les ombres, pas les
collisions ni la vacuite d une section).

## 2026-08-11 — Trois juges de composition: chevauchement, vide, emoji

### Reprise et diagnostic

Le juge de rendu notait **100/100** la page SaaS du tour precedent. En la
regardant, trois defauts sautaient aux yeux qu aucune de ses metriques ne
mesurait: « View Demo » et « Scroll to explore » se SUPERPOSAIENT dans le hero,
la section FAQ etait un grand vide, et les six icones de fonctionnalites etaient
des EMOJI. Il comptait les tailles de police, les fonds et les ombres — jamais
la COMPOSITION.

### Recherches et choix

Les trois mesures viennent du NAVIGATEUR (rectangles reels apres mise en page);
la regle de notation est un module TS pur, donc testable sans navigateur.

- **Chevauchement**: on ne compare que les FEUILLES porteuses de texte ou de
  controles (ce que l oeil lit), en excluant les paires parent/enfant. Un simple
  frolement ne compte pas: l intersection doit couvrir au moins 25 % du plus
  petit des deux elements, sinon toute ombre ou bordure declencherait.
- **Vide**: pour chaque section, part de sa surface reellement couverte par du
  contenu. Seules les sections de plus de 400 px sont jugees — une petite
  section a le droit de respirer. Seuil a 15 %: le cas reel mesure 12 % sur
  658 px, il fallait donc passer au-dessus pour l attraper.
- **Emoji**: detecte d abord sur le RENDU. La detection a la source manquait le
  cas reel, parce que les emoji vivaient dans un tableau de donnees
  (`{{ feature.icon }}`) et non dans le markup — invisibles a une analyse
  statique, evidents a l ecran. La detection source reste en repli.

**Directive alignee sur la mesure**: le contrat design exige desormais des SVG
inline (meme grille 24x24, meme epaisseur, `currentColor`), interdit les emoji,
et interdit explicitement les chevauchements et les grandes sections vides. On
ne note pas un critere qu on n a jamais demande.

### Modifications realisees

- `src/services/codeCompositionGate.ts` (nouveau) — `checkComposition`,
  `findEmptySections`, `detectEmojiIcons`, critique nommant le defaut constate.
- `scripts/code_harness/aesthetic_capture.mjs` et `render_audit.mjs` —
  `measureComposition()` en navigateur (chevauchements, remplissage, emoji).
- `src/services/codePipelineFinalization.ts` — un livrable a icones emoji est
  plafonne a 80 et emporte la consigne de remplacement.
- `src/services/codeDesignDirectiveBlocks.ts` — contrat iconographie +
  composition.
- `src/__tests__/codeCompositionGate.test.ts` (nouveau) — 13 tests.

### Avant-apres mesurable — sur la page reelle

Les trois juges appliques a `output/code/audit_v94/project/dist`, la page que le
juge de style notait 100/100:

```
FAIL no_overlap        "View Demo" x "Scroll to explore" (2914px2)
FAIL no_empty_section  Frequently Asked Questio: 658px remplie a 12%
FAIL real_iconography  6 emoji en position d icone: 📊 🎨 🔌 🔒 👥 🤖
```

Les trois correspondent exactement a ce que j avais releve a l oeil au tour
precedent. Le juge de style disait 100/100; la composition dit 0/3.

Tests : **844 -> 857 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeCompositionGate.test.ts'
node scripts/code_harness/aesthetic_capture.mjs output/code/audit_v94/project/dist \
  --out output/code/audit_v94/shots_after --json output/code/audit_v94/shots_after/report.json
jq '.compositionVerdict | {ok, failedChecks}' output/code/audit_v94/shots_after/report.json
```

### Etat de satisfaction chantier

Les trois defauts de composition que je voyais et que la machine ne voyait pas
sont desormais mesures, nommes et corriges en consigne. Reste assume: le juge
mesure la GEOMETRIE (superposition, remplissage, nature des icones), pas
l harmonie — il ne dira pas qu une palette est laide, seulement qu une zone est
vide ou qu un texte en recouvre un autre.

## 2026-08-11 — Test capstone: « marche sur mobile » livrait une appli native

### Reprise et diagnostic

Test capstone: un brief ecrit comme un vrai humain l ecrirait (2 820
caracteres, verbatim, non structure) — un artisan torrefacteur lyonnais qui
veut un site pour sa marque, avec une mini page interne pour suivre les
commandes.

Le pipeline a commence a livrer... une **application React Native**:
`babel.config.js`, `App.tsx`, `src/navigation/AppNavigator.tsx`,
`src/theme/ThemeContext.tsx`.

Or le brief dit « un vrai **site** » (trois fois), « une **page d accueil** »,
« on vend **en ligne** », et sa seule mention de mobile est:
« Doit marcher nickel sur **mobile** parce que 80% des gens qui nous trouvent
c est sur leur telephone » — c est-a-dire RESPONSIVE, pas natif.

Diagnostic mesure sur le prompt reel:

```
projectType classifie : mobile_rn
looksLikeMobileApp    : true
   application  false      <- la regle implicite ne peut PAS avoir declenche
   telephone    true
   mobile       true
   site         true
```

`looksLikeMobileAppRequest` a donc declenche sur la LISTE EXPLICITE, car
`MOBILE_SIGNALS` contient le mot **nu** « mobile ». Par contraste,
`DESKTOP_SIGNALS` n emploie que des locutions (« application de bureau »,
« desktop app ») — jamais « bureau » seul. L asymetrie etait la.

Un garde web existait pourtant (v89b), et son commentaire nomme exactement ce
bug. Mais ses motifs ne couvrent que la formulation TECHNIQUE: `site web`,
`page web`, `responsive`, `navigateur`. Un humain ecrit « un vrai site », « page
d accueil », « en ligne » — aucun ne matchait.

**Le defaut n est donc pas que le garde manquait: c est qu il ne parlait que la
langue d un developpeur.**

### Modifications realisees

- `src/services/codeIntentClassification.ts` — le garde web couvre la
  formulation humaine: `site` nu (avec exclusion de « sur site », qui signifie
  « sur place »), « page d accueil », « nos pages / une page ».
- `src/__tests__/codeIntentModules.test.ts` — 4 tests.

### Avant-apres mesurable

| Brief | Avant | Apres |
|---|---|---|
| « un vrai site […] doit marcher sur mobile » (cas reel) | **mobile_rn** | **static_web** |
| « application mobile React Native android et ios » | mobile_rn | mobile_rn (inchange) |
| « une appli pour telephone, sur le play store » | mobile_rn | mobile_rn (inchange) |
| « site vitrine pour mon restaurant » | static_web | static_web (inchange) |
| « dashboard responsive mobile et desktop » | spa_react | spa_react (inchange) |
| « interventions **sur site** de nos techniciens » | — | non-mobile (« sur site » = sur place) |

Aucune demande d application native reellement exprimee n est affectee.

Tests : **857 -> 861 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeIntentModules.test.ts'
```

### Etat de satisfaction chantier

La classification comprend desormais la langue ordinaire, pas seulement le
vocabulaire technique. Reste assume: la liste `MOBILE_SIGNALS` garde le mot nu
« mobile »; c est le GARDE web qui le neutralise quand le contexte est un site.
Retirer le mot de la liste serait plus propre, mais toucherait aussi
`codeIntentFollowup`, ou « mobile » seul reste un signal legitime de pivot.

## 2026-08-11 — Capstone Brulerie Nomade: neuf passes contre un bug inexistant

### Reprise et diagnostic

Le run 960 (brief humain non nettoye de 2 820 caracteres: une torrefactrice
lyonnaise qui veut un site + une mini page admin interne) a echoue apres ~2 h.
Symptomes rapportes: 9 passes de correction sur la meme erreur de parentheses,
rejets anti-regression en boucle, puis un repli qui livre 50/100 avec
« 0 section trouvee, 0 ko de HTML » alors que le run avait DEJA produit du
contenu substantiel.

J ai extrait les 33 fichiers reellement livres depuis le flux
(`output/code/audit_v96/stream.ndjson`, evenements `file.written` avec contenu,
sequences 209 a 241) et je les ai passes aux portes du pipeline. La chaine
complete est **cinq defauts distincts**, pas un.

**1. L AST reel etait mort sur les canaux CLI et tunnel.** Le harnais headless
declare `globalThis.window` pour les modules a saveur UI. Or web-tree-sitter
(Emscripten) commence par:

```js
document = "object" == typeof window ? {currentScript: window.document.currentScript} : null
```

Un `window` sans `document` fait donc LEVER le module a l import. Mesure:

```
WITH harness_env shims -> {"ok":false,"reason":"Cannot read properties of undefined (reading 'currentScript')"}
```

`parseCodeWithTreeSitter` retournait `ok:false`, et `syntaxCritic` retombait
**en silence** sur son compteur de blocs lexical. Le juge de syntaxe annonce
donc « analyse AST tree-sitter » dans ses messages et n en faisait jamais.

**2. Le compteur lexical ne sait pas lire du JSX.** Dans un texte JSX, `'` est
un CARACTERE. Le francais en met partout: « 123 Rue de l'Atelier », « pas l'an
dernier », « page d'accueil ». Chaque apostrophe ouvrait une chaine et masquait
la moitie du fichier. Sur les fichiers reels du run:

```
Footer.tsx           lexical= parens diff 1   | AST: hasError=false
StorySection.tsx     lexical= parens diff 1   | AST: hasError=false
SubscriptionForm.tsx lexical= parens diff 2   | AST: hasError=false
ContactForm.tsx      lexical= braces diff 3   | AST: hasError=false
MarketCalendar.tsx   lexical= parens diff -1  | AST: hasError=TRUE
ContactPage.tsx      lexical= parens diff 1   | AST: hasError=TRUE
```

Cinq blocages sur six etaient FAUX. `Footer.tsx` est un composant parfaitement
valide dont le seul tort est de contenir l adresse de l atelier. Le modele a
donc recu neuf fois de suite l ordre de reparer un fichier sain — il ne pouvait
que renvoyer le meme fichier, d ou le plateau a 53 et la boucle.

**3. La grammaire suivait le LIBELLE, pas l extension.** `detectLanguage()`
mappe `tsx -> 'typescript'`. La grammaire `typescript` REFUSE le JSX. Verifie:

```
Footer.tsx  grammaire tsx        -> hasError=false
Footer.tsx  grammaire typescript -> hasError=true
```

Rallumer l AST sans corriger ce point aurait remplace un faux positif par un
autre, sur TOUS les fichiers React.

**4. Le refus anti-regression ne parlait jamais au correcteur.**
`buildCorrectionMessages` ne recoit que la sortie du sandbox. Le verdict du
garde etait ecrit dans `pass.errors` (journal de l UI) et s arretait la. Cinq
refus consecutifs, cinq fois le meme prompt, cinq fois le meme patch. Ce n est
PAS un defaut d escalade — l escalade fonctionne (`targeted_repair` ->
`partial_rewrite` -> `strategy_change` + 4 rotations d angle, visibles dans le
flux). C est que la diversification change d angle **sans jamais apprendre du
garde**.

**5. La passe esthetique jetait le meilleur etat.** Une fois la boucle arretee,
le livrable est audite au rendu reel: 44/100. Le runner relance alors une
generation complete et fait:

```js
if (regen?.files?.length) {
  files = regen.files                                  // adoption inconditionnelle
  const after = await renderAndScoreAesthetics(files)  // mesure... jetee
```

Le score d apres etait calcule, journalise, et jamais compare. La boucle de
l UI avait le meme defaut, avec un commentaire qui disait le contraire
(« regen infructueuse -> on garde le meilleur etat »). La relance repartait en
`fresh_start` et perdait meme le sujet: a la sequence 265 elle cherchait
« Google brand colors hex codes » pour un site de cafe.

**6. La porte visuelle jugeait un SPA sur sa coquille Vite.**
`evaluateVisualFidelity` n agrege que les `.html`. Dans un projet React,
`index.html` est une coquille autour de `<div id="root">` — d ou le
« 0 section, 0 ko » du verdict final sur un projet de 71 ko de markup. Second
aveuglement du meme genre: le pipeline INJECTE Tailwind lui-meme, puis cherchait
le degrade dans `linear-gradient` et le flex dans `display: flex`, la ou un
projet Tailwind n ecrit jamais rien.

Enfin, l avertissement « URL http:// sur endpoint sensible sur index.html:2 »
n etait pas un faux positif du critique: `index.html` etait passe de 569 octets
de document a 223 octets contenant **un fragment JSX**
(`<img src="http://127.0.0.1:3001/..." className=... />`). Le point d entree du
site avait ete detruit par une passe de correction, et le garde n avait rien vu
— `.html` n est ni un fichier source, ni un test, ni un fichier vide.

### Modifications realisees

- `scripts/code_harness/harness_env.mjs` — le shim expose `window.document` et
  `currentScript: null`; Emscripten reprend sa branche Node et l AST revit.
- `src/services/codeTreeSitterAst.ts` — `resolveTreeSitterLanguage()`: la
  grammaire se choisit sur l EXTENSION, le libelle n est qu un repli.
- `src/services/codeStaticSyntax.ts` — utilise la grammaire resolue, nomme la
  grammaire reellement employee, et ne BLOQUE plus sur du JSX quand l AST
  manque (une heuristique qui ne sait pas lire le fichier n a pas le droit de
  mettre la note de compilation a zero).
- `src/services/codeLexicalAnalysis.ts` — une apostrophe collee a un caractere
  de mot n ouvre plus de chaine (le backtick reste inconditionnel: un template
  balise suit legitimement un identifiant).
- `src/services/codeCorrectionRegressionFeedback.ts` (nouveau) — le verdict du
  garde devient une consigne; au 2e refus consecutif la portee est resserree
  aux seuls fichiers nommes par les erreurs.
- `src/services/codeCorrectionContextGathering.ts` (nouveau) — extraction
  (recherche, outillage, cause racine) pour tenir sous 400 lignes.
- `src/services/codeValidationCorrectionLoop.ts`, `codeCorrectionMessages.ts` —
  cablage du retour de garde; 2 libelles mojibakes corriges.
- `src/services/codeBestDeliverySelection.ts` (nouveau) — `pickBestDelivery`:
  on ne remplace un livrable que sur preuve (score strictement meilleur, aucune
  capacite perdue, pipeline non en erreur). Cable sur les DEUX canaux.
- `src/services/codeRegressionGuard.ts` — un `.html` qui perd son doctype est
  une regression nommee (`broken_html_document`).
- `src/services/codeVisualFidelity.ts` + `codeVisualFidelityDetectors.ts` — le
  markup juge = document + composants; detecteurs conscients de Tailwind.

### Avant-apres mesurable — sur les 33 fichiers reels du run 960

Critique statique, dans les conditions exactes du run (harnais headless,
`.tsx` etiquetes « typescript »):

| | avant | apres |
|---|---|---|
| fichiers bloques | 7 | **2** |
| dont faux positifs | 5 | **0** |
| message | « parens non equilibres (diff 1) » | « erreur de syntaxe (analyse AST tree-sitter tsx) » |

Porte visuelle source-statique sur le meme projet:

| | avant | apres |
|---|---|---|
| score | 50/100 | **70/100** |
| echecs | 10 | **5** |
| dont faux | « 0 section », « 0 ko de HTML », « 1 image » | aucun |

Les 5 echecs restants sont VRAIS du projet (4 sections, pas de blur, pas de
keyframes, pas de 3D, un seul degrade). Un `static_web` sans composants garde
un comportement strictement identique.

Tests : **861 -> 907 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeCapstoneBrulerie.test.ts'

# la cause racine, isolee: l AST sous le harnais headless
node --experimental-strip-types --input-type=module --eval "
const { installHeadlessCodeEnv } = await import('./scripts/code_harness/harness_env.mjs')
installHeadlessCodeEnv()
const m = await import('./src/services/codeTreeSitterAst.ts')
console.log(await m.parseCodeWithTreeSitter('const a = (1 + 2)', 'tsx'))"
```

### Etat de satisfaction chantier

Les cinq mecanismes sont fermes et chacun est mesure sur les fichiers reels du
run qui a echoue. Reste assume, et c est different de ce qui precedait: le
compteur lexical reste faux sur du JSX (il n est plus bloquant, mais il n est
pas juste — 3 desaccords subsistent avec l AST sur les 9 fichiers testes); il
ne sert que de repli quand aucune grammaire n existe. Et la porte visuelle
mesure toujours des TRAITS (degrade, profondeur, sections), jamais le gout.

## 2026-08-12 — L excellence ne tenait pas sur le simple: un seul gabarit pour tout

### Reprise et diagnostic

Test volontairement au BAS du spectre (run 971): « Salut, j'aurais besoin d'un
petit truc tout simple : une page web unique pour convertir des temperatures
[...] pour ma fille qui apprend les conversions au college. Rien d'autre, pas
de compte, pas de base de donnees, juste la page. »

Le pipeline a livre **exactement** ce qui etait demande — je l ai lu ligne a
ligne: HTML semantique, conversion a la frappe dans les deux sens, aucun bouton
valider, Inter, variables CSS en oklch, `clamp()` pour le rythme, ombre douce.
Puis il l a declare **en echec**. Trois causes, toutes fausses:

**1. Aurora echouait sur son propre fichier.** Mesure:

```
scores = {... "security":0 ...}   BLOQUANT = true
[error] assets/aurora-asset-bundle.json:16 — URL http:// (non-TLS) sur endpoint sensible
[error] assets/aurora-asset-bundle.json:18 — URL http:// (non-TLS) sur endpoint sensible
   ... 10 occurrences
```

Le manifest d assets ecrit par AURORA reference AURORA: `http://127.0.0.1:3001/
api/code/assets/...`. Le motif matchait sur `api/`, la note de securite tombait
a 0, la critique statique devenait bloquante, le run entier partait en erreur.
C est aussi la reponse a la question laissee ouverte au tour precedent sur
l avertissement « http:// sur index.html:2 »: **faux positif**, et il coutait la
livraison. Une adresse de boucle locale ne traverse aucun reseau.

**2. Un seul gabarit pour tout.** Le verdict reclamait au convertisseur:

```
- Au moins 6 sections (trouve: 0)      - Transformations 3D (rotateY/X, perspective)
- Au moins 2 images (trouve: 0)        - Animation pilotee par scroll
- SVG inline travaille                 - Au moins 2 gradients layered
- HTML > 6 ko (trouve: 1 ko)           - hero / galerie / specs / KPIs / testimonials
```

C est le gabarit d une landing marketing premium, applique tel quel a un outil
a une page. **Les satisfaire aurait activement degrade le produit**: un
convertisseur avec un hero, une galerie et une rotation 3D au scroll est un
convertisseur moins bon. Un seuil universel ne mesure pas la qualite, il mesure
la ressemblance a UN genre.

**3. Un ecart d habillage tuait une livraison qui marche.** Le sandbox etait
vert, l acceptation comportementale a 2/2, le score a 100, la boucle s arretait
meme sur « livraison validee a 100% » — et `phase` valait `'error'`, parce que
la porte design-spec avait bascule `ok` a false.

### Recherches et choix

La barre ne bouge pas (70). Ce qui change, c est la LISTE des criteres qui
comptent, par genre — et le genre se lit dans ce qu on a deja: le brief, le
sujet de marque resolu par l intent, et la taille reelle du livrable.

- **vitrine** — on vend quelque chose, l apparence EST le produit. Rubrique
  complete, strictement inchangee.
- **application** — un poste de travail n est pas une page qui se scrolle: pas
  de sections narratives, pas de parallaxe, pas de photos d ambiance imposees.
- **outil** — une tache, un ecran, zero ceremonie: clarte, typographie,
  finition (rayons, ombres, survol), interface vivante. Ni hero, ni galerie,
  ni parallaxe.

Un projet muet et minuscule (3 fichiers, 5 ko) n est pas une vitrine, quoi
qu en dise un classifieur: c est le livrable qui tranche.

### Modifications realisees

- `src/services/codeVisualFidelityProfiles.ts` (nouveau) —
  `resolveVisualAmbition`, la table des criteres exclus par genre, et la
  definition en clair de la barre de chaque genre.
- `src/services/codeVisualFidelity.ts` — la note se calcule sur les criteres
  APPLICABLES; le resume nomme la barre appliquee; le brief est transmis.
- `src/services/codeStaticSecurityRules.ts` — la regle http:// exempte la
  boucle locale (localhost, 127.x, ::1, 0.0.0.0, *.local, host.docker.internal).
- `src/services/codeValidationScoring.ts` — `isDeliveryRunnable`: les portes de
  STYLE pesent sur le score, jamais sur le verdict d executabilite.
- `src/services/codeOrchestrator.ts` — `phase` derive de `isDeliveryRunnable`.
- `src/services/codePipelineFinalization.ts` — passe le brief a la porte.
- `src/__tests__/codeSimpleProjectCalibration.test.ts` (nouveau) — 14 tests.

### Avant-apres mesurable — les deux extremes reels

| Projet reel | Avant | Apres |
|---|---|---|
| Convertisseur (run 971, 3 fichiers) | **53/100 REFUSE** | **89/100 ACCEPTE** (barre outil) |
| Site Brulerie Nomade (run 960, 33 fichiers) | 70/100 accepte | **70/100 accepte** (barre vitrine, intacte) |

Les 2 echecs restants sur le convertisseur sont VRAIS et pertinents pour un
outil: `border-radius` a 8 px (< 10) et aucun etat `:hover`. Sur la vitrine,
sections, profondeur, mouvement et 3D restent exiges — rien n a ete relache.

Tests : **907 -> 921 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeSimpleProjectCalibration.test.ts'
```

### Etat de satisfaction chantier

« Excellent » a maintenant une definition ecrite par categorie, au lieu d un
seuil unique qui confondait qualite et ressemblance a une landing. Reste
assume: la detection du genre repose sur du vocabulaire et sur la taille du
livrable — un brief ambigu (« une page pour mon club ») tombera dans le repli
vitrine, qui est le plus exigeant. Se tromper vers le PLUS exigeant est le bon
sens de l erreur, mais c est bien une heuristique, pas une certitude.

## 2026-08-12 — Viewer en conditions reelles, et l acces web verifie

### Reprise et diagnostic

Deux demandes restaient a prouver pour de vrai, pas en test unitaire: le viewer
plein ecran avec arborescence, et « que ca fonctionne partout » — c est-a-dire
depuis le lien web, y compris sur telephone.

### Modifications realisees

- `src/services/codeProjectReadme.ts` — le titre d un projet statique tombait
  sur le TYPE (`# Static Web`). Le modele avait deja choisi un nom: il est dans
  le `<title>` de la page livree. On le lit, en refusant les titres de gabarit
  (Vite, React App, Document, Sans titre).
- `src/__tests__/codeCorrectionMessages.test.ts` — garde ANTI-ORPHELIN: le
  verdict du harnais anti-regression doit arriver dans les messages envoyes au
  modele. Le module pouvait exister et etre calcule sans jamais etre lu — c est
  le pattern que ce module paie depuis le debut.

### Avant-apres mesurable

**Viewer, en conditions reelles.** Le composant reel monte dans un navigateur
(Chromium headless, vite dev), nourri par les 5 fichiers du convertisseur
reellement genere. La preuve n est pas une capture decorative: j ai TAPE dans
la page a travers le viewer.

```
dans le rendu: {"title":"Convertisseur de Température","h1":"Convertisseur de Température","inputs":2}
conversion live 100C -> 212.0°F
erreurs JS: aucune
```

Capture regardee: `proof/v971-3-conversion-live.png` — arborescence a gauche
(« 5 FICHIERS · 12,7 KO », assets/, index.html, README.md, script.js,
style.css avec leurs tailles), rendu a droite, `100` saisi dans le champ
Celsius et `212.0°F` affiche. Le viewer montre la structure ET fait tourner le
produit.

**Acces web.** Tunnel Cloudflare deja en place (`cloudflared tunnel --url
http://localhost:3001`, actif depuis 4 j 17 h), URL inchangee apres le
redemarrage du pont:

```
https://exotic-sage-liabilities-information.trycloudflare.com
  /                             HTTP 200  (l application complete, pas seulement l API)
  /api/health                   HTTP 200
  /api/code/generate/stream     HTTP 400 en POST  -> la route EXISTE et repond
```

Rendu reel a travers le tunnel, deux formats:

| | viewport | debordement horizontal | erreurs JS |
|---|---|---|---|
| desktop | 1440 | non | aucune |
| mobile (iPhone 13) | 390 | non | aucune |

Le mobile n est pas un desktop comprime: c est une mise en page dediee
(navigation radiale, barre d onglets basse, banniere d installation PWA).

**README, aux deux extremes** — verifie fichier par fichier contre le livrable:

| | titre | contenu |
|---|---|---|
| complexe (33 fichiers) | `# Brulerie Nomade` | 4 scripts npm reels, 6 routes dont `/admin`, Node >= 20 deduit de `vite ^8` |
| simple (5 fichiers) | `# Convertisseur de Température` | aucun script npm, aucune URL, aucun `start.sh` — « un navigateur suffit » |

Les 4 scripts, les 6 routes et la version de Vite correspondent exactement au
`package.json` et a `AppRoutes.tsx` livres.

Tests : **921 -> 925 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
curl -s -o /dev/null -w "%{http_code}\n" https://exotic-sage-liabilities-information.trycloudflare.com/api/health
node --experimental-strip-types --test 'src/__tests__/codeProjectReadme.test.ts' 'src/__tests__/codeCorrectionMessages.test.ts'
```

### Etat de satisfaction chantier

Le viewer fait ce qui etait demande et je l ai verifie en m en servant, pas en
lisant un score. Reste assume, vu a l oeil sur la capture mobile: deux defauts
de mise en page du SHELL de l application (pas du module Code) — « JOURNAL DU
JOUR » chevauche le libelle « GALERIE », et l onglet « CANVAS » est rogne au
bord droit de la barre basse. C est hors du perimetre de ce chantier, mais
c est vu et note plutot que passe sous silence.

## 2026-08-12 — Une reponse illisible tuait le run, et le viewer devient un lien

### Reprise et diagnostic

Le run 981 (convertisseur de temperature, rejoue apres la calibration) a montre
deux choses opposees.

**Ce qui a tenu.** Le garde anti-gaspillage du tour precedent a fonctionne sur
un run REEL:

```
[bridge-runner] rendu: 58/100 (seuil 70) -> passe esthetique ciblee
[bridge-runner] rendu apres passe esthetique: 82/100
[bridge-runner] passe esthetique: rendu 82/100 contre 58/100 avant — regeneration adoptee
```

La passe est mesuree AVANT et APRES, et la decision suit la mesure.

**Ce qui a casse.** Le run s est quand meme termine en
`FAILED phase=error files=10`, sur une cause encore jamais vue:

```
Echec de l executor agentique WS3:
  action_producer_failed:action_protocol_invalid:protocol_marker_missing
```

La TOUTE PREMIERE etape de l executor a recu une reponse dont il ne restait
rien d exploitable, et le run entier est mort avant d avoir ecrit un fichier.

Le repli tolerant de juillet existe et il est correct — il rattrape le cas « le
modele a rendu du CODE BRUT sans le marqueur ». Il ne pouvait rien ici: il n y
avait pas de code brut a rattraper, il n y avait RIEN (moins de 20 caracteres
exploitables apres nettoyage). **Aucune tolerance d ANALYSE ne peut extraire du
contenu du vide.** La seule reponse correcte est de redemander, autrement — ce
que le producteur ne faisait jamais: un appel, une chance, et le run mourait.

### Modifications realisees

- `src/services/codeGenerationActionProducer.ts` — trois tentatives, avec des
  consignes qui se durcissent: (1) normale, (2) « le JSON seul, pas de phrase,
  pas de raisonnement », (3) « oublie le protocole, ecris le fichier nu dans un
  bloc ``` » — recupere par le repli code-brut existant.
- `src/services/codeGenerationExecutor.ts` — un fichier SECONDAIRE encore
  illisible apres ces trois tentatives est saute, la generation continue. Un
  fichier requis reste bloquant: sans point d entree, pas de livrable.
- `src/services/codeViewerHtml.ts` (nouveau) — viewer AUTONOME en un fichier.
- `scripts/code_harness/bridge_ndjson_runner.mjs` — chaque run materialise son
  viewer et journalise son lien.

### Avant-apres mesurable

| | avant | apres |
|---|---|---|
| reponse vide a l etape 1 | run mort, 0 fichier | 3 tentatives, puis fichier nu |
| fichier secondaire illisible | run mort | fichier saute, run poursuivi |

**Le lien viewer, verifie a travers le tunnel public** (pas en local):

```
GET https://<tunnel>/api/code/assets/file/viewers/run-971/index.html
  HTTP 200 · text/html · 22 829 octets
  arborescence : 6 lignes avec tailles
  rendu        : h1 « Convertisseur de Température » + 2 champs
  saisie 37 dans le champ Celsius -> 98.6°F affiche
  clic script.js -> « script.js · javascript », source affichee
  erreurs JS   : aucune, en desktop 1440 ET en mobile iPhone 13
```

Aucune route n a ete ajoutee au serveur bridge: `bridge_server.py` porte 445
lignes de travail NON COMMITE de l utilisateur. La route GET
`/api/code/assets/file/<path>` sert deja les fichiers materialises — le viewer
passe par elle, sans toucher un fichier qui ne m appartient pas.

Tests : **929 -> 935 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeGenerationActionProducer.test.ts' \
  'src/__tests__/codeViewerHtml.test.ts'
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" \
  "https://<tunnel>/api/code/assets/file/viewers/run-971/index.html"
```

### Etat de satisfaction chantier

Le viewer est un lien, et je l ai ouvert moi-meme dans un navigateur avant de
le dire. Reste assume: le viewer est materialise par le RUNNER (canal CLI et
tunnel). Une generation lancee depuis l UI Tauri ne produit pas encore son
lien — le meme appel doit y etre branche. Et la passe esthetique continue de
repartir d une page blanche: sur ce run elle a ecrit un `game.js` pour un
convertisseur. Le garde empeche desormais cette derive d ecraser le bon
travail; il ne l empeche pas de se produire.

## 2026-08-12 — Hub de tous les projets, et un vrai APK signe

### Reprise et diagnostic

Trois chantiers, plus deux verdicts de runs reels.

**Le run SIMPLE aboutit proprement.** Rejoue avec le correctif de protocole:

```
[bridge-runner] acceptation comportementale 2/2
[bridge-runner] rendu: 70/100 (seuil 70)
[bridge-runner] done files=5 score=99 attempts=1
```

Une seule passe de correction, aucune boucle, livraison `done`. C est le succes
complet demande, sur le bas du spectre.

**Le run COMPLEXE a revele une cause encore jamais vue.** Verdict:

```
FAIL runtime-no-error: Failed to load module script: Expected a
     JavaScript-or-Wasm module script but the server responded with a MIME type
     of "text/plain". Strict MIME type checking is enforced.
FAIL renders-content: 0 caracteres, 0 controles, 0 surfaces.
```

Le livrable de 43 fichiers a ete declare casse et la boucle a brule NEUF passes
a corriger une application qui n avait jamais ete CONSTRUITE. Le harnais sert
les sources telles quelles; l `index.html` d un projet Vite pointe
`/src/main.tsx`, que seul un build resout. Le juge de RENDU tenait deja cette
garde (`needsBundler`); l acceptation comportementale ne l avait jamais eue.

**Le lien par run ne suffisait pas.** Une adresse jetable par generation oblige
a retrouver la bonne. Il fallait une adresse STABLE listant tout.

**Et l APK: l evaluation de faisabilite s est inversee en cours de route.**
Premier verdict, honnete mais faux: `adb`, `aapt2`, `apksigner` absents du PATH,
`ANDROID_HOME` vide — donc impossible. En cherchant ou WS12 prenait ses outils,
le SDK est apparu: 3,2 Go sous `~/.local/share/auroraia/tools/android-sdk`,
build-tools 36, plateforme android-36, DEUX AVD (phone et tablet), JDK 21. Il
n est pas sur le PATH, c est `_android_env()` qui l y met. La faisabilite
n etait pas une question d outillage, mais de savoir ou il etait range.

### Modifications realisees

- `scripts/code_harness/acceptance_behaviour.mjs` — la garde `needsBundler`,
  plus `.ts/.tsx/.jsx` dans les tables MIME des deux harnais.
- `src/services/codeViewerIndex.ts` (nouveau) — le HUB: liste, pastilles de
  plateforme, selecteur de projet, lien APK.
- `src/services/codeViewerAssets.ts` (nouveau) — habillage partage.
- `scripts/code_harness/viewer_publish.mjs` (nouveau) — publication disque,
  reconstruction de l index, import des runs passes, empaquetage APK.
- `python-services/aurora_code/code_apk_package.py` (nouveau) — APK signe qui
  EMBARQUE le projet (`aapt2 link -A assets/`, WebView sur
  `file:///android_asset/www/index.html`). Ne touche pas a WS12.

### Avant-apres mesurable

| | avant | apres |
|---|---|---|
| SPA jugee sans build | « 0 caractere », run condamne, 9 passes | `applicable:false, needsBuild:true` |
| acces aux projets | 1 lien jetable par run | 1 hub stable, 7 projets importes |
| changer de projet | recharger une autre page | selecteur, meme page |
| projet mobile | rien | APK signe telechargeable (4 projets sur 7) |

**Preuve, pilotee a travers le tunnel public:**

```
hub                     HTTP 200 · 7 cartes · pastilles « Web ✓ | Mobile ✓ »
ouverture du complexe   53 lignes d arborescence
bascule au selecteur    6 lignes, MEME page (pas de rechargement)
retour a la liste       7 cartes · erreurs JS: aucune
APK par le tunnel       HTTP 200 · 12 998 o · application/vnd.android.package-archive
APK telecharge          apksigner: CN=Aurora Code, O=AuroraIA, C=FR
contenu de l APK        assets/www/index.html = <title>Convertisseur de Température</title>
```

Tests : **935 -> 943 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types scripts/code_harness/viewer_publish.mjs --import --apk
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" \
  "https://<tunnel>/api/code/assets/file/viewers/run-1001/app.apk"
~/.local/share/auroraia/tools/android-sdk/build-tools/36.0.0/apksigner verify --print-certs \
  output/code_assets/viewers/run-1001/app.apk
```

### Etat de satisfaction chantier

Le hub existe, je l ai pilote moi-meme au bout du tunnel, et l APK telecharge
par ce meme tunnel est signe et contient bien l application.

Reste assume, mesure, non contourne:
- un projet a bundler n a ni rendu ni APK — il affiche desormais la RAISON
  (« npm install && npm run build ») au lieu d un cadre blanc. C est honnete,
  mais ce n est pas resolu: construire les SPA generees reste le prochain vrai
  chantier, et c est lui qui debloquerait a la fois le rendu, l acceptation et
  l APK des projets complexes;
- React Native reste hors cadre (chaine Gradle et node_modules absents);
- l apercu de l emulateur en direct dans le navigateur n est pas livre: il
  demanderait un etage de streaming disproportionne ici. Les deux AVD existent,
  donc `adb install` reste la voie courte;
- le hub est alimente par le RUNNER: une generation lancee depuis l UI Tauri n y
  apparait pas encore.

## 2026-08-12 — Construire les SPA, et durcir les recoins

### Reprise et diagnostic

Le verrou que j avais nomme au tour precedent: un projet a bundler ne peut pas
etre juge en servant ses sources. Les deux juges se declaraient « non
applicables », donc tout le haut du spectre restait NON MESURE — ni rendu, ni
acceptation, ni APK.

La reponse n est pas une heuristique de plus: c est de CONSTRUIRE, avec la
commande que le README promet. Le build ne devine pas, il compile.

Premier essai sur le projet reel du run 991, et il donne immediatement ce
qu aucune heuristique n avait su nommer:

```
src/__tests__/MarketCalendar.test.tsx(15,28): error TS1002: Unterminated string literal.
src/components/Footer.tsx(5,6): error TS17008: JSX element 'footer' has no corresponding closing tag.
```

A comparer avec ce que le meme projet produisait avant: « renders-content:
0 caracteres, 0 controles, 0 surfaces ». Meme verdict d echec, mais l un
envoyait le modele chasser un fantome pendant neuf passes, l autre lui donne le
fichier, la ligne et la colonne.

Trois obstacles reels rencontres en chemin, chacun mesure et ferme:

- `Cannot find package '@vitejs/plugin-react'` — le `vite.config` importait un
  plugin que le manifeste ne declarait pas. On lit les imports du fichier de
  config et on complete: c est verifiable, pas devine.
- `ERR_PACKAGE_PATH_NOT_EXPORTED` — installer le dernier plugin a cote d un
  vite 5 ne marche pas. La version suit desormais le vite DECLARE.
- `Could not resolve dependency` — les projets generes melangent des versions
  qui ne se parlent pas. Repli `--legacy-peer-deps`, exactement ce pour quoi il
  existe.

### Avant-apres mesurable

| Sur un projet a bundler | Avant | Apres |
|---|---|---|
| acceptation comportementale | « non applicable » | **applicable, 2/2 verts** |
| audit de rendu | « non applicable » | **applicable, 54/100** |
| projet reellement casse | « 0 caractere » | **erreurs du compilateur, fichier:ligne:colonne** |

### Les recoins durcis

**Caviardage avant publication.** Le hub sert le code source integral par le
tunnel PUBLIC. Rien de sensible n y figure aujourd hui — verifie sur les sept
projets, zero occurrence — mais c est une propriete a TENIR. Les valeurs de
secrets sont masquees; un `<input type="password">`, un `process.env.API_KEY` et
un `your-api-key-here` restent intacts. Verifie de bout en bout: un projet
portant `apiKey = "sk_live_..."` publie un `project.json` ou le secret est
ABSENT et le champ de formulaire intact.

**Traversee de chemin.** Quatre tentatives par le tunnel
(`../../../etc/passwd`, encodages `%2e%2e`, remontee depuis `viewers/`):
**HTTP 404 partout**.

**Fichiers de reprise.** Aucun des sept projets n avait de `.gitignore`: le
premier geste de son proprietaire aurait ete de commiter `node_modules/`. Trois
fichiers desormais, tous derives du reel: `.gitignore` suit la pile detectee,
`.env.example` ne liste que les variables que le code LIT, `.nvmrc` porte la
version deduite. Aucune licence n est generee — choisir a la place de l auteur
serait une faute.

**Le hub a l echelle.** Filtre plein texte avec compteur, tri (date, taille,
score, nom), et surtout un ETAT DE BUILD lisible sans ouvrir le projet:
« Construit » / « Ne compile pas » avec les erreurs en infobulle. Sur les sept
projets reels, trois sortent « Ne compile pas », et c est vrai.

**Accessibilite mesuree a l ecran.** Sept criteres dans le navigateur, dont le
contraste CALCULE. Prouve dans les deux sens: le convertisseur livre obtient
100/100, une page volontairement fautive tombe a 0/100 avec les sept defauts
nommes — dont « texte gris clair » a **1.66:1**, ce qu aucune regex ne peut
trouver.

**Un bug que je me suis inflige, et le garde qui en sort.** `join('\n')` dans un
template literal TS devient un VRAI retour a la ligne dans le script emis:
« Invalid or unexpected token », hub mort, zero carte. Tous les tests de contenu
passaient — ils verifiaient la presence des balises, pas que la page VIT. Trois
tests verrouillent desormais que les scripts des deux pages viewer PARSENT.

Tests : **954 -> 990 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeProjectBuild.test.ts' \
  'src/__tests__/codeArtifactRedaction.test.ts' \
  'src/__tests__/codeProjectScaffoldFiles.test.ts' \
  'src/__tests__/codeAccessibilityGate.test.ts'
curl -s -o /dev/null -w "%{http_code}\n" "https://<tunnel>/api/code/assets/file/../../../etc/passwd"
```

### Etat de satisfaction chantier

Le verrou est leve: un projet a bundler est construit, donc mesure, donc
corrigeable sur des erreurs de compilateur au lieu d heuristiques.

Reste assume: le build tourne dans le HARNAIS (rendu, acceptation, viewer), pas
encore dans la boucle de correction elle-meme. Les erreurs du compilateur sont
donc visibles apres coup, mais elles ne nourrissent pas encore les passes de
correction — c est le branchement qui rendrait le gain complet, et c est le
prochain vrai chantier.

## 2026-08-12 — Le parser dit OU, et la matrice de capacite est mesuree

### Reprise et diagnostic

**Le compilateur comme source de verite dans la boucle.** Le run 1011 a depense
quatre passes sur « AboutPage.tsx: erreur de syntaxe ». Vrai, et inexploitable:
le modele devait relire 200 lignes pour deviner quoi corriger. Le parser
connaissait pourtant la position exacte depuis le debut — personne ne la lisait.

Sur les fichiers REELS du run 991:

```
avant  src/__tests__/MarketCalendar.test.tsx: erreur de syntaxe
apres  src/__tests__/MarketCalendar.test.tsx:15:23 — jeton inattendu
       pres de: location: 'Presqu'île',
```

L apostrophe non echappee dans une chaine a guillemets simples: la cause exacte,
nommee. C est le meme diagnostic que `error TS1002: Unterminated string literal`
— obtenu sans npm, dans CHAQUE passe, sur les trois canaux.

Deux raffinements imposes par les fichiers reels: on garde le noeud fautif le
plus PRECIS (un ERROR racine couvre tout le fichier, « 1:1 » n aide personne),
et quand l erreur part de l octet 0 on pointe la FRONTIERE d analyse. Footer.tsx
passe ainsi de « 1:1 » a « 34: », exactement la ligne que tsc designe.

### La matrice de capacite, mesuree

L utilisateur demande jusqu ou le module peut aller. Une estimation ne vaut
rien: chaque case est un artefact compile sur cet hote.

| Plateforme | Etat | Preuve |
|---|---|---|
| Android natif (Java) | **PROUVE** | APK signe 8 605 o, `CN=Aurora Natif`, vraie Activity |
| Android natif (Kotlin) | **PROUVE** | APK signe 610 717 o, `CN=Aurora Kotlin` |
| Apple / iOS (Swift) | **PARTIEL** | swiftc 5.10.1 compile ET execute; `.ipa` impossible hors macOS |
| Embarque (Rust) | **PROUVE** | binaire natif execute, marqueur observe |
| OS / bas niveau (C) | **PROUVE** | objet freestanding, QEMU disponible |
| WebAssembly | **PROUVE** | module wasm valide (magic `0asm`) |

Trois verrous ont ete LEVES plutot que rapportes: le compilateur Kotlin, la
cible `wasm32` et la chaine Swift Linux manquaient — installes dans le dossier
prive d Aurora, puis prouves par un artefact. Swift a coute 605 Mo pour pouvoir
dire « ce code Swift est valide » au lieu de « je ne sais pas ».

Sur Apple, la matrice separe deux questions qu on confond toujours: le code
est-il VALIDE (verifiable ici) et peut-on produire un `.ipa` INSTALLABLE (non,
jamais, hors macOS — limite de plateforme, pas d outillage).

**L ecart que seule la mesure revele:** l HOTE compilait du Kotlin, le SANDBOX
non. Aucune image n etait declaree pour kotlin ni swift, ils retombaient sur
`debian:bookworm-slim` ou `kotlinc` n existe pas — un projet Kotlin genere
echouait sur « command not found », pas sur son code. Les chaines sont
desormais montees en LECTURE SEULE depuis le dossier prive d Aurora, avec
l image temurin pour Kotlin qui a besoin d une JVM.

### Avant-apres mesurable

| | avant | apres |
|---|---|---|
| erreur de syntaxe rapportee | « fichier: erreur de syntaxe » | « fichier:15:23 — pres de `location: 'Presqu'île',` » |
| plateformes prouvees | 1 (web) | **5 prouvees + 1 partielle** |
| Kotlin dans le sandbox | `command not found` | chaine montee, image JVM |

Tests : **998 -> 1006 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types scripts/code_harness/capability_probe.mjs --publish
curl -s -o /dev/null -w "%{http_code}\n" "https://<tunnel>/api/code/assets/file/viewers/capacites.html"
```

La matrice est publiee et lisible: `/api/code/assets/file/viewers/capacites.html`.

### Etat de satisfaction chantier

La position exacte des erreurs de syntaxe ferme la cause qui brulait le plus de
passes. La matrice ne repose plus sur une impression: cinq plateformes portent
un artefact, la sixieme porte une raison.

Reste assume: `tsc` complet (erreurs de TYPE, pas seulement de syntaxe) tourne
dans le harnais, pas encore dans la boucle. Et les APK natifs Java/Kotlin sont
prouves au niveau CHAINE — le pipeline sait desormais les compiler, mais aucun
run n a encore genere un projet Kotlin de bout en bout.

## 2026-08-12 — La quatrieme porte: la performance

### Reprise et diagnostic

Le module jugeait deja trois choses A L ECRAN — style, composition,
accessibilite. La performance manquait, et c est celle qui separe « joli » de
« professionnel ». Une page magnifique qui met deux secondes a peindre, qui
saute pendant le chargement ou qui empile 4 800 noeuds est un mauvais livrable,
quel que soit son score esthetique.

### Modifications realisees

- `src/services/codePerformanceGate.ts` (nouveau) — sept criteres notes par un
  module pur: premiere peinture, DOM interactif, saut de page (CLS), images non
  dimensionnees, poids du DOM, octets transferes, taches longues.
- `scripts/code_harness/render_audit.mjs` — `measurePerformance()` dans le
  navigateur (PerformanceObserver layout-shift et longtask, navigation timing,
  poids reel des ressources).
- `src/services/codeSandboxToolchains.ts` (nouveau) — montage des chaines
  Kotlin/Swift dans le bac isole.

### Avant-apres mesurable

| Page reelle | Verdict |
|---|---|
| convertisseur livre (run 971) | **100/100** — FCP 244 ms, CLS 0, 22 noeuds, 7,3 Ko |
| page de 1 200 lignes | **88/100** — « Moins de 2500 noeuds DOM — mesure: 4810 » |

Les budgets sont plus severes que les reperes publics de Web Vitals parce qu on
mesure en LOCAL: ni reseau ni latence serveur, donc 1200 ms de premiere peinture
et pas 1800. Un detail qui compte pour l honnetete: un FCP a 0 signifie « non
mesure », pas « instantane » — il compte comme un echec, jamais comme une
reussite gratuite.

Tests : **1006 -> 1018 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codePerformanceGate.test.ts' \
  'src/__tests__/codeSandboxToolchains.test.ts'
```

### Etat de satisfaction chantier

Les quatre portes de rendu sont en place et chacune est prouvee dans les DEUX
sens — une porte qui ne fait que passer ne vaut rien. Reste assume: ces mesures
ne concernent que le web. Un APK natif n a pas encore d equivalent (temps de
demarrage, fluidite) — l emulateur existe, la mesure reste a ecrire.

## 2026-08-12 — Le juge reclamait le gadget que la cliente avait refuse

### Reprise et diagnostic

Run 1021, brulerie artisanale lyonnaise: livraison refusee a **65/100** pour un
seuil de 70 (contre 50 avant les correctifs precedents — le progres est reel,
l echec aussi). Les criteres qui manquaient:

```
- Transformations 3D (rotateY/X, perspective, preserve-3d)
- Animation pilotee par scroll (sticky/IntersectionObserver)
- Au moins 2 images · border-radius >= 10px · etats :hover
```

Or le brief de la cliente dit, textuellement:

> « Des animations discretes c est cool (un peu de mouvement au scroll, les
> cafes qui apparaissent progressivement) mais **je veux pas que ca fasse
> gadget**, faut que ca reste elegant. »

**Le juge reclamait exactement le gadget qu elle avait refuse** — des rotations
3D sur une brulerie artisanale. C est le motif de TOUS les defauts corriges
depuis le debut de cette refonte: une porte qui juge selon un gabarit interne
au lieu de juger selon ce qui a ete demande. Le profil « vitrine » du tour
precedent distingue bien outil / application / vitrine, mais il restait sourd
aux contraintes exprimees DANS le brief.

Verification faite avant de coder: l information n existait nulle part en amont.
`codeDesignDirectives` porte du vocabulaire d ARCHETYPE (brutaliste, immersif),
pas de contrainte de retenue. Il fallait donc l extraire.

### Modifications realisees

- `src/services/codeStyleConstraints.ts` (nouveau) — lecture des contraintes
  explicites du brief, la liste des criteres « gadget » a retirer et celle des
  criteres a renforcer, plus une explication citant le brief.
- `src/services/codeVisualFidelity.ts` — sous retenue, les criteres
  spectaculaires sortent de la notation et la finition pese plus lourd.
- `src/services/codeVisualFidelityCritique.ts` — la critique DIT que la barre a
  change et pourquoi.
- `scripts/code_harness/bridge_ndjson_runner.mjs` — les quatre portes decident.
- `scripts/code_harness/capability_probe.mjs` — artefacts hors de /tmp.

### Avant-apres mesurable — sur les fichiers reels du run 1021

| | avant | apres |
|---|---|---|
| score visuel | **65/100 REFUSE** | **88/100 ACCEPTE** |
| criteres exiges | 3D, parallaxe, degrades empiles | retires (contredisent le brief) |
| echecs restants | gadgets manquants | fond plat, pas de SVG inline, rayons < 10 px |

Les trois echecs restants sont de VRAIS defauts de finition — exactement ce que
la cliente demande quand elle dit « elegant ».

**Le risque etait d ouvrir une porte de sortie universelle.** Quatre tests le
verrouillent: « elegant » seul n active rien (presque tous les briefs le
disent); une page pauvre reste refusee meme avec un brief sobre; un brief
neutre garde exactement le comportement d avant; et la finition est notee plus
severement sous retenue (poids compares).

### Deux recoins fermes dans la foulee

**Regle du projet violee par moi au tour precedent:** les artefacts de la
matrice de capacite vivaient dans `/tmp`. C est purge au redemarrage — une
matrice qui reference des artefacts disparus ne devient pas inutile, elle MENT
en silence. Ils vivent desormais sous
`application/output/code/capacites/<plateforme>/`, chemins cites dans la page.

**Deux portes mesuraient dans le vide:** le canal tunnel lisait le style et la
composition, et ignorait accessibilite et performance — calculees a chaque
audit, puis jetees. Mot pour mot le « mesurer sans decider » deja corrige sur la
passe esthetique: un defaut se reintroduit toujours par la porte qu on vient
d ouvrir. Les quatre verdicts sont maintenant journalises, emis dans le flux, et
declenchent la passe ciblee. Verifie sur le convertisseur: style 70 OK,
composition 100 OK, accessibilite 100 OK, performance 100 OK.

Tests : **1018 -> 1029 verts, 0 echec.**

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/codeStyleConstraints.test.ts'
```

### Etat de satisfaction chantier

La derniere cause de refus injustifie du brief Brulerie est fermee, et elle
l est de la seule maniere qui vaille: en faisant lire au juge ce qui a ete
demande, sans lui retirer sa severite. Le run complet qui doit le confirmer de
bout en bout est lance (runId 1031).

## 2026-08-12 (suite) — Run 1031: trois causes, dont un juge aveugle a Tailwind

Le run 1031 a echoue a 64/100. Le correctif de retenue stylistique, lui,
fonctionne en reel: le juge ecrit « Retenue demandee par le brief: criteres
spectaculaires retires ». Les rotations 3D ne sont plus exigees. Restaient
trois verrous mecaniques, tous mesures sur les fichiers reels du run.

### Cause 1 — le juge etait aveugle a Tailwind

Il reprochait au projet l absence d arrondis, de survols et de degrades. Le
projet en a. Compte dans ses fichiers:

```
rounded-lg x21 · rounded-md x3 · rounded-full x1
hover:text-olive x3 · hover:bg-amber-* x3 · hover:bg-olive x1
```

La porte cherchait `border-radius:` et `:hover` dans du CSS. **Tailwind
n ecrit jamais ces proprietes** — il les genere au build depuis les classes
utilitaires, et son `index.css` ne contient que trois directives `@tailwind`.
Aucune SPA Tailwind ne pouvait donc passer ces criteres. Meme defaut que le
reste de cette refonte: juger la FORME de la reponse au lieu de sa substance.

Idem pour les sections: 14 composants de page (About, CoffeeList, Contact,
Admin...) comptaient pour « 2 sections », faute de balise `<section>`.

| sur les fichiers reels du run 1031 | avant | apres |
|---|---|---|
| fidelite visuelle | **64/100 REFUSE** | **85/100 ACCEPTE** |
| finition (polish gate) | **43/100** | **80/100** |

Les manques restants — degrades, SVG inline, images — sont reels.

**La meme cecite frappait la porte de finition, en pire:** son rapport alimente
`codeCorrectionMessages`. On ne se contentait pas de mal noter un projet
Tailwind, on lui envoyait la liste de ce qui « manque » — donc on demandait au
modele d ajouter du CSS qu un projet Tailwind ne doit pas ecrire.

### Cause 2 — un conseil irrealisable fait boucler le modele

Les passes 5 a 8 etaient bloquees sur « Secret en dur dans src/lib/auth.ts ».
Ce n est pas un faux positif: `brulerie2024` est bien en dur. Mais le conseil
donne — « deplacer vers .env » — est **faux sur ce projet**: 0 fichier serveur
sur 31, et dans un bundle front une variable `VITE_*` est inline au build, donc
tout aussi publique. Le modele appliquait le conseil, le probleme restait, la
regle se redeclenchait: **quatre passes perdues dans une boucle sans sortie,
parce que la sortie proposee n existait pas.**

Un conseil irrealisable est pire qu un silence: il transforme une porte de
qualite en piege. La remediation depend desormais de l architecture reelle.

### Cause 3 — un JSON annexe condamnait toute la passe

`main.json` invalide a fait jeter deux passes de correction entieres, avec
toutes les corrections valides qu elles contenaient. Seuls les JSON dont depend
le build (package.json, tsconfig, tauri.conf, manifest) condamnent encore.

### Regle structurelle

Celle posee au tour precedent, contournee ici par un autre chemin: **une porte
ne condamne jamais ce qu elle n a pas vu.** Sur un projet a bundler dont le
markup source se reduit a la coquille `<div id="root">`, sans rendu construit,
le verdict est « NON MESURE » — pas 64/100.

Aucun laissez-passer: projet Tailwind reellement pauvre = toujours refuse,
package.json casse = toujours condamne, « non mesure » n est pas une reussite.

Tests : **1029 -> 1044 verts, 0 echec.**

## 2026-08-12 (suite) — Run 1041: une panne reseau detruisait 32 fichiers

Le run 1041 n a pas echoue sur la qualite: il est mort avant d etre juge.

```
[CodeOrchestrator] Pipeline fatal error: Ollama: toutes les tentatives
epuisees (3). Modeles testes: qwen3-coder:30b x3. Derniere erreur: fetch failed
```

Aucun `visual.score` emis. 32 fichiers produits, **tous jetes** — le
gestionnaire fatal renvoyait `files: []`. Contexte machine au moment de la
panne: 30 Go de RAM, **0 libre**, 14,7 Go de VRAM occupes.

C est la regle des portes de qualite prise dans l autre sens. Un juge qui ne
peut pas mesurer ne condamne pas ; donc **un generateur qui perd son modele ne
detruit pas ses fichiers**. Une panne reseau ne dit rien sur la valeur du
travail deja produit.

### 1. Le travail est preserve

Le dernier etat non vide des fichiers est capture en continu et livre si le
pipeline meurt, sous une phase dediee `interrupted` — ni `done` ni `error`. Les
notes disent explicitement que **l interruption n est pas un verdict de
qualite**, pour qu aucune lecture ulterieure ne confonde « pas fini » et
« mauvais ». Le runner sort sur son propre chemin (code 2): sans cela, un
travail non valide aurait ete annonce `done` aux consommateurs — le mensonge
exact que ce fichier denonce dix lignes plus haut pour le cas `error`.

### 2. On attend un service qui revient

Le bareme (800 ms, 2 s, 4 s) totalise **~7 secondes**. Sous pression memoire, un
rechargement de modele prend des dizaines de secondes: on abandonnait un run de
32 fichiers pendant que le service etait en train de revenir.

Quand l erreur decrit un TRANSPORT casse (`fetch failed`, `ECONNREFUSED`,
`socket hang up`...), le bareme passe a **6 tentatives sur ~132 s**. Un modele
qui REFUSE le travail garde ses 3 tentatives rapides: s acharner sur une erreur
deterministe serait le gaspillage inverse, deja corrige ailleurs. Attendre ne
consomme ni RAM ni VRAM — seule forme de resilience acceptable sur cette
machine, dont les gels historiques sont d origine memoire.

### 3. La garde de residence etait aveugle deux fois

- **Son cache la neutralisait.** `lastEnsured` etait pose pendant la
  planification, PUIS la phase d assets chargeait le modele d un autre module,
  PUIS la generation reprenait avec la garde en cache — donc sans jamais rien
  decharger. Les deux modeles ont cohabite pendant toute la generation.
- **Elle croyait la vision legere.** Le commentaire disait « vision qwen3-vl,
  legere, peut coexister ». `qwen3-vl:30b` est un 30B: il pese autant qu un gros
  modele code. **Un modele se juge a sa taille, pas a sa famille.** Le test qui
  affirmait l inverse encodait l hypothese que la mesure a dementie; il est
  corrige et documente. La cible n est jamais dechargee, y compris quand la
  cible EST la vision (test dedie).

Tests : **1047 -> 1056 verts, 0 echec.**

## 2026-08-13 — Run 1051: 97/100 au juge, bloque par une apostrophe

Percee: **le juge visuel accepte a 97/100** (barre vitrine, retenue du brief
appliquee). Trajectoire mesuree sur le meme brief: **50 -> 64 -> 65 -> 97**. La
cecite Tailwind et la lecture des contraintes de style tiennent en conditions
reelles sur un run frais, et la memoire est restee saine (1280 MiB de VRAM en
fin de run contre 14 800 auparavant).

Restait le dernier verrou: `boucle infinie detectee sur la meme erreur apres
9 passes`, `FAILED phase=error files=38`.

### Le diagnostic etait bon — c est la reparation qui manquait

```
Passe 2  MarketCalendar.tsx : syntaxe invalide
Passe 3  MarketCalendar.tsx : syntaxe invalide
Passe 4  MarketCalendar.tsx : erreur de syntaxe
Passe 5  MarketCalendar.tsx : syntaxe invalide
Passe 8  chaine contenant une apostrophe non echappee
```

Neuf fois le bon diagnostic, a la bonne position. La cause, deux fois dans le
fichier (lignes 24 et 45):

```js
location: 'Presqu'île',
```

Le modele echoue parce qu a chaque passe **il reecrit le meme texte francais et
reproduit la meme rupture**. C est un piege systematique, pas une inattention:
une dixieme passe n aurait rien change. Verifie dans le flux — une seule
version du fichier a ete ecrite sur tout le run, le modele n a jamais pose de
correction.

### Deterministe, donc pas delegue

Une apostrophe encadree par DEUX LETTRES a l interieur d un litteral simple est
du contenu, jamais un terminateur. Ligne directrice du module: **quand une
correction est deterministe, on ne la delegue pas a un modele probabiliste.**
Elle est appliquee a l assainissement, avant la validation.

Mesure sur le projet reel, avec le vrai compilateur (esbuild):

| | fichiers qui refusent de compiler |
|---|---|
| avant | **3** — mockData.ts, MarketCalendar.tsx, SubscriptionForm.tsx |
| apres | **0** |

Le piege n etait donc pas isole a MarketCalendar: il frappait partout ou du
contenu francais rencontrait un litteral simple.

### La prudence porte sur la portee, pas sur la certitude

Un scanner d etats (code / simple / double / gabarit / commentaires) remplace
toute heuristique de regex. Le correcteur ne touche qu au cas « lettre ' lettre ».
Sept cas verrouillent qu il ne modifie RIEN, octet pour octet: code valide,
concatenation, guillemets doubles, gabarits, echappement deja present,
commentaires, et litteral non ferme — dans ce dernier cas le fichier est casse
autrement, on rend la main plutot que de deviner. Les .md, .json et .css ne sont
jamais examines.

Tests : **1056 -> 1066 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1061: six causes, dont quatre rendaient `done` IMPOSSIBLE

Le run 1061 est le meilleur de la serie et il finit quand meme en `error`:

```
acceptation comportementale  2/2         OK
rendu REEL                   100/100     OK   (seuil 70, aucun echec)
accessibilite                100/100     OK   (seuil 80)
performance                  80/100      OK   (seuil 70)
composition                  real_iconography  <- seul echec
FAILED phase=error files=36
```

Toutes les portes de qualite franchies, et pourtant un echec. En descendant
dans le flux reel, ce n etait pas une cause mais **six**, empilees. Quatre
d entre elles rendaient `done` mecaniquement inatteignable, quel que soit le
code produit — ce qui explique toute la serie de runs precedents.

### Cause A — le protocole lisait une forme que le modele n ecrit pas

Le fichier livre `main.js` faisait 15 534 octets et n etait pas du JavaScript:
c etait le conteneur multi-fichiers brut, non deballe. Le critique statique
lisait `<<<AURORA_CODE_VFS/1>>>` en tete et diagnostiquait « jeton inattendu
pres de import ». **Il avait raison.** Neuf passes brulees a reparer une erreur
de syntaxe qui n existait pas.

Pourquoi le conteneur n a-t-il pas ete reconnu ? La consigne melait un en-tete
de version **nu** et deux marqueurs **encadres**:

```
Commence par AURORA_CODE_VFS/1.          <- nu
Pour chaque fichier: <<<AURORA_FILE {…}>>>   <- encadre
Marqueur de fin: <<<AURORA_END>>>            <- encadre
```

Le modele a uniformise — dans l autre sens: il a encadre la version et **denude
les en-tetes de fichier**. Le parseur, lui, exigeait `<<<AURORA_FILE ` au
caractere pres. Zero fichier reconnu. Un protocole dont la seule forme valide
est celle que le modele n ecrit pas n est pas un protocole, c est un piege.

Traite aux trois niveaux: consigne symetrique (les trois marqueurs s ecrivent
pareil, plus un exemple complet), parseur tolerant aux deux formes (forme nue
ancree en debut de ligne, pour qu une citation dans du contenu ne coupe pas un
fichier), et **garde de derniere ligne**: un fichier dont le contenu COMMENCE
par un marqueur Aurora est deballe, ou ecarte — jamais livre.

| sur le fichier reel du run 1061 | avant | apres |
|---|---|---|
| fichiers extraits | **1** (`main.js`, 15 534 o, non compilable) | **14** aux vrais chemins |
| marqueurs de protocole residuels | 1 | **0** |

### Cause B — la passe « ciblee » reecrivait le projet

Un seul critere echouait (`real_iconography`). La passe appelait
`orchestrateCodeGeneration` **en entier**: nouvelle intention, nouveau plan
d architecture, nouvelle generation. Elle repartait d une page blanche et
rendait un projet AUTRE, ampute (`removed_file, removed_script,
removed_export`). Le garde anti-regression la refusait — a raison — et le
defaut restait.

Corriger des emoji, c est editer les fichiers qui portent des emoji. La portee
est desormais DEDUITE d une preuve dans le contenu (pour l iconographie, le
detecteur du juge lui-meme, fichier par fichier), bornee a 8 fichiers, et la
fusion est **structurellement incapable de supprimer**: on remplace des chemins
existants et autorises, on n en retire aucun. Un fichier neuf n est accepte que
s il est reellement importe par un fichier patche.

Second piege, dans l arbitre: le livrable etait a **100/100 en style** ET en
echec de composition. Une passe qui repare exactement ce defaut ne peut pas
faire monter un score deja au plafond — `pickBestDelivery` la condamnait donc
quoi qu elle repare. Reparer la porte qui echouait EST le progres; le score
sert alors a verifier qu on n a rien casse, pas a prouver une hausse.

### Causes C a F — le bac a sable ne pouvait PAS reussir

En regardant les verdicts sandbox du run 1061, une ligne saute aux yeux:

```
seq 128  ok=false score=86  Preuve isolation host-read
seq 140  ok=false score=86  Preuve isolation host-read
seq 152  ok=false score=86  Preuve isolation host-read
```

Aux passes 3, 4 et 5, **tout le reste etait vert**. Le seul echec etait une
preuve d isolation — et elle bloque `isDeliveryRunnable`, donc `phase: 'error'`.
Cette preuve echouait sur chaque run, pour chaque projet, depuis toujours.

**C. Les preuves tournaient dans une image absente.** Construites avec le
langage `'unknown'`, elles retombaient sur `debian:bookworm-slim`. Aurora ne
provisionne que trois images (node, python, alpine) et `--pull=never` interdit
de telecharger pendant une generation.

```
image debian:bookworm-slim  -> Error: image not known
image node:22-bookworm-slim -> HOST-READ PROBE: PASS
```

Les preuves tournent desormais dans **l image qui va reellement executer le
code**. Prouver qu un conteneur debian ne lit pas l hote ne dit rien du
conteneur node dans lequel le projet tourne: c est plus juste, pas seulement
plus pratique.

**D. Deux probes sur quatre etaient du shell INVALIDE.** Les corps de boucle
etaient joints par un espace: `i=$((i + 1)) dd …` devenait un prefixe
d affectation a `dd` (jamais persiste) et `done` collait a la commande
precedente.

```
$ sh -n -c '<script de la preuve quota disque>'
sh: 1: Syntax error: end of file unexpected (expecting "done")
```

`dash` sort alors en **2** — exactement le statut que la preuve reservait a
« confinement NON applique ». Une erreur de syntaxe etait rapportee comme une
faille d isolation. Le test qui manquait est ajoute: **chaque script de probe
doit passer `sh -n`**. Il a immediatement attrape deux fautes de ponctuation
dans ma propre reecriture.

La preuve de plafond PID avait le meme defaut de fond: le shell **meurt** sur
« Cannot fork » avec le statut 2, le meme statut que « pas de plafond ». Les
deux cas etaient indiscernables. La rafale est confinee dans un sous-shell et
le verdict ne tient plus qu a un marqueur. Temoin negatif verifie: sans
`--pids-limit`, la preuve echoue toujours.

**E. On exigeait la preuve d un quota jamais demande.** Ce systeme de fichiers
ne supporte pas le Project Quota (`volume options size and inodes not
supported`), et Aurora cree **deliberement** le volume sans quota de taille.
Exiger ensuite la preuve de ce quota, c est faire contredire par une porte une
decision prise en amont. La preuve devient NON APPLICABLE — et n est pas
declaree acquise pour autant.

**F. Le HOME inscriptible n etait jamais declare, et le plafond de taille de
fichier valait 1 Mio.** Deux reglages, un meme symptome: `npm install`
impossible.

- La racine est en lecture seule avec un tmpfs sur `/home/aurora`, mais
  `--userns keep-id` donne `HOME=/home/node` dans l image node — un chemin de la
  racine en lecture seule. Mesure: `npm error enoent … mkdir '/home/node/.npm'`.
  Le bac a sable montait un HOME inscriptible **sans jamais le dire au
  processus**. Un seul reglage repare npm, pip, cargo et go.
- `fileSizeBlocks: '1048576'` encodait une hypothese fausse. Podman passe la
  valeur telle quelle a `RLIMIT_FSIZE`, **qui est en octets** — c est `ulimit -f`
  du shell qui compte en blocs de 512 o, pas l API. Le plafond reel etait donc
  de 1 Mio. Mesure: un `dd` de 2 Mio s arrete a exactement 1 048 576 octets, et
  `npm install` de react echoue en `EFBIG: file too large`.

**Tous ces echecs arrivaient au pipeline avec une sortie VIDE**: le pont ne
renvoie que stdout et podman ecrit sur stderr. Un echec sans message est
indiagnosticable — c est ainsi qu une image absente a pu passer pendant des
dizaines de runs pour une violation d isolation. Une etape en echec sans sortie
est desormais nommee.

### Avant-apres mesurable

Validation isolee, projet React/Vite reel, meme machine, meme pipeline:

| | avant | apres |
|---|---|---|
| verdict sandbox | **ok=false** | **ok=true** |
| etapes atteintes | 4 | **13** |
| preuves d isolation | **0/4** (1re en echec) | **7/7 vertes** |
| `npm install` | EFBIG / ENOENT | **passe** |
| `vite build` | jamais atteint | **passe** |
| `phase` possible | `error`, toujours | **`done`** |

### Demonstration reproductible

```bash
cd application
node --experimental-strip-types --test 'src/__tests__/code*.test.ts'
# 1099 tests, 0 echec

# la preuve d isolation, a la main, dans les deux images
podman run --rm --pull=never --network none docker.io/library/debian:bookworm-slim true
#   -> Error: docker.io/library/debian:bookworm-slim: image not known
podman run --rm --pull=never --network none docker.io/library/node:22-bookworm-slim true
#   -> (rien: succes)

# l unite reelle de --ulimit fsize
podman run --rm --pull=never --ulimit fsize=1048576:1048576 --read-only \
  --tmpfs /tmp:rw,size=256m docker.io/library/node:22-bookworm-slim \
  sh -lc 'dd if=/dev/zero of=/tmp/x bs=1M count=2 status=none; ls -l /tmp/x'
#   -> File size limit exceeded, 1048576 octets ecrits
```

### Etat de satisfaction chantier

Six causes, et la lecon est la meme pour cinq d entre elles: **une porte qui ne
peut pas mesurer ne doit pas condamner**. Une image absente, un script invalide,
un quota jamais demande, un HOME jamais declare — aucun de ces quatre faits ne
dit quoi que ce soit sur le code livre, et tous les quatre le condamnaient.

La regle avait deja ete posee dans ce journal pour le juge visuel et pour les
pannes reseau. Elle n avait jamais ete appliquee au bac a sable, qui est
pourtant le seul juge dont le verdict decide de `done`.

## 2026-08-13 (suite) — Run 1081: on demandait a un modele de texte d ecrire des JPEG

Le run 1081 rejoue le brief Brulerie avec les six correctifs precedents. Il meurt
a **29/30 fichiers**, apres pres d une heure:

```
[CodeOrchestrator] Pipeline fatal error: Echec de l executor agentique WS3:
  action_producer_failed:action_protocol_invalid:protocol_marker_missing
[warn] 30 fichier(s) preserves malgre la erreur du pipeline.
[bridge-runner] INTERROMPU files=30 — travail preserve, validation incomplete
```

### Ce qui a marche

La garde de preservation a tire et la phase `interrupted` s affiche comme prevu,
avec la mention explicite que ce n est **pas** un verdict de qualite. Avant les
correctifs des tours precedents, ces 30 fichiers auraient ete detruits et le run
classe `error`. Le comportement est correct.

### Les deux fausses pistes, ecartees par la mesure

1. **Regression du protocole VFS ?** Non. `buildStructuredEmissionInstructions()`
   n apparait que dans le prompt de l AUDITEUR (boucle de correction), jamais
   dans celui de l executor WS3, qui utilise `buildCodeGenerationActionInstructions`
   et `buildExecutorQualityContract`. Les deux protocoles ne se croisent nulle
   part. Verifie par lecture des quatre sites d appel.
2. **Defaut de tolerance du parseur ?** Non plus. `parseCodeGenerationActions`
   accepte deja un marqueur absent: il cherche la premiere valeur JSON dans tout
   le texte. `protocol_marker_missing` ne signifie pas « marqueur absent » mais
   « rien d exploitable nulle part ». Le repli en 3 tentatives existe et a bien
   tourne trois fois.

### La cause, lisible dans les fichiers preserves

La file de generation WS3 contenait des **images binaires**. On demandait a
qwen3-coder d en ecrire le contenu:

```
public/team-photo.jpg    42 297 o de base64 tape a la main
public/coffee-hero.jpg      388 o — un JPEG tronque des l en-tete
```

Le second n est meme pas une image valide. Le premier a coute des dizaines de
milliers de jetons pour produire un fichier tout aussi mort. Puis le 30e et
dernier element a rendu une reponse dont il ne restait rien.

**Aucune consigne, aucune relance, aucun repli ne fera ecrire un JPEG valide a un
modele de texte.** La bonne reponse n est pas de mieux redemander: c est de ne
pas poser la question. Aurora a deja une phase d assets inter-modules qui appelle
le module Image — elle avait d ailleurs tourne dans ce run.

`.svg` reste dans la file: c est du XML, et le run 1081 a produit un
`public/logo.svg` valide. **Le critere est « binaire », pas « ressource ».**

Le meme predicat filtre le contrat de plan. Sans cette symetrie, le contrat
reclamerait un fichier que la file ne produit plus, declencherait une
regeneration, et celle-ci echouerait a nouveau: c est exactement le piege du
conseil irrealisable paye quatre passes au run 1031.

### « Requis » ne veut pas dire « sans lui rien ne tourne »

Le 30e fichier etait marque `required` par l architecte. Son illisibilite a donc
fait jeter les **29 fichiers deja ecrits**. Un plan qui declare tout requis
transforme n importe quel accident sur le dernier composant en perte totale.

Ne bloquent desormais que les fichiers **porteurs de la livraison** — point
d entree, coquille HTML, manifeste de dependances, config de build — et seulement
tant qu il n y a pas deja de quoi livrer. Un composant de page manquant se voit,
se signale et se rattrape par la boucle de correction; un run de 29 fichiers
detruit, non.

| | avant | apres |
|---|---|---|
| images dans la file WS3 | 2 (42 685 o de base64 mort) | **0** |
| contrat de plan reclamant un binaire | oui | **non** |
| 30e fichier requis illisible | run entier perdu | **saute et signale** |

Tests : **1101 -> 1109 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1091: la passe ciblee prouvee, et une page blanche qui n existait pas

Le run 1091 valide en reel le correctif de la passe ciblee:

```
composition: real_iconography -> passe ciblee
passe ciblee (real_iconography): 1 fichier(s) corrige(s): src/components/Testimonials.tsx
passe esthetique: composition reparee sans perte de rendu (92/100 contre 92/100) — adoptee
```

**Un seul fichier touche, defaut repare, zero perte.** Au run 1061, la meme
passe supprimait fichiers, scripts et exports et se faisait rejeter en bloc.
Scores: rendu 92/100, performance **100/100**, accessibilite 86/100.

Restait `acceptation comportementale 1/2` — `FAIL renders-content: 0 caracteres,
0 controles, 0 surfaces` — et neuf passes de correction a chercher un bug de
montage React avec des diagnostics de plus en plus vagues (« incoherence dans
les dependances », « configuration incorrecte de React », « configuration
incomplete de Tailwind »). Le modele devinait.

### La page blanche n existait pas

Mesure sur les fichiers reels du run, memes fichiers, memes trois requetes
(3 x HTTP 200), zero erreur navigateur:

```
GET /index.html  ->    0 caractere,   15 elements
GET /            -> 1492 caracteres, 130 elements
```

La SPA livree utilise `react-router-dom` avec les routes `/`, `/about`,
`/markets`… **Aucune route ne correspond a `/index.html`**, donc `<Routes>` ne
rend rien. La porte d acceptation ouvrait une URL que l application ne sert pas,
puis l accusait d etre une coquille vide.

L audit de rendu, lui, ouvrait deja la RACINE — d ou 92/100 au meme instant, sur
la meme livraison. **Ce sont les deux portes qui divergeaient, pas le code.**
Une application web s ouvre a sa racine, comme le fait un utilisateur.

| sur les fichiers reels du run 1091 | avant | apres |
|---|---|---|
| acceptation comportementale | **1/2** | **2/2** |
| renders-content | 0 car., 0 ctrl., 0 surf. | **1492 car., 1 ctrl., 4 surf.** |

Note: la consigne de depart etait de capturer les erreurs console et de les
injecter dans la boucle. La capture existait deja des deux cotes — et elle
disait la verite: **zero erreur**. C est en la croyant, au lieu de chercher un
bug plus profond, qu on trouve la vraie cause. Il n y avait rien a reparer dans
le livrable.

### Deux autres verrous du meme run, tous deux du meme genre

**Une suite de tests ABSENTE traitee comme une suite en echec.** Mesure dans le
conteneur reel:

```
$ npm run test     # "test": "vitest"
No test files found, exiting with code 1
```

Le code 1 faisait echouer « Verifier test », donc `isDeliveryRunnable` renvoyait
false, donc `phase: 'error'` — pour TOUT projet qui declare un script `test`
sans en ecrire. Et la boucle ne pouvait rien y faire: ecrire une suite que le
brief n a jamais demandee n est pas une correction. Un lanceur qui ne trouve
aucun test **n a rien mesure du code livre**. L etape devient NON APPLICABLE, la
sortie d origine conservee. Un test qui EXISTE et echoue reste bloquant.

**Le juge aveugle condamnait celui qui voit.** « Classes Tailwind detectees sans
configuration Tailwind » porte `axis: 'preview'` et severite `error`: un defaut
d APPARENCE lu dans la SOURCE bloquait le verdict d executabilite — pendant que
le navigateur mesurait 92/100 de rendu, 100/100 de performance et 1492
caracteres affiches. Deux juges sur l apparence, et c est l aveugle qui gagnait.

La regle posee pour la design-spec est etendue a son jumeau: **l axe `preview`
pese sur le score, jamais sur « est-ce que ca tourne »**. Une severite `block`
reste bloquante quel que soit l axe.

### La constante de cette serie

Six causes au run 1061, une au 1081, trois au 1091. Sur ces dix, **huit sont des
portes qui condamnaient ce qu elles n avaient pas mesure**: une image absente,
un script shell invalide, un quota jamais demande, un HOME jamais declare, une
suite de tests inexistante, une URL que l application ne sert pas, un defaut
d apparence juge sur la source, un binaire demande a un modele de texte.

Aucune ne disait quoi que ce soit sur le code livre. Toutes le condamnaient.

Tests : **1109 -> 1117 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1101: une trace en langage de bundle, et six symptomes soignes

Le run 1101 attrape une VRAIE panne — la capture d erreurs, qui disait « zero
erreur » au run precedent et avait raison, rapporte cette fois un crash reel:

```
TypeError: Cannot read properties of undefined (reading 'map')
    at hd (http://127.0.0.1:34141/assets/index-C-nmfp7n.js:8:193411)
rendu: 10/100  echecs=runtime_clean,display_typography,type_scale,
                      real_typeface,visual_content,depth,interactivity
```

Deux defauts distincts empechaient la boucle de le reparer.

### 1. La trace disait OU — en langage de bundle

`assets/index-C-nmfp7n.js:8:193411` ne nomme ni fichier, ni ligne, ni composant.
C est exactement le trou deja bouche cote compilateur (« il disait QU il y a une
erreur, jamais OU »), mais cote navigateur. Le modele ne pouvait que deviner, et
il a devine.

- le bundle est reconstruit avec ses cartes des qu il n en a pas
  (`vite build --sourcemap`) ;
- les traces sont resolues en positions SOURCE avant d atteindre le correcteur ;
- la capture passe de **160 a 1200 caracteres** — 160 coupait juste apres le
  message, donc avant la moindre frame ;
- une position de bundle non resolue est **signalee comme telle**, pour qu aucun
  correcteur ne devine un fichier au hasard.

| sur le projet reel du run 1101 | avant | apres |
|---|---|---|
| position transmise | `assets/index-C-nmfp7n.js:8:193411` | **`src/components/CoffeeCard.tsx:35:19`** |

Verification a la ligne 35 du fichier livre:

```jsx
{notes.map((note, index) => (
```

La carte dit vrai.

### 2. On soignait six symptomes

La porte declarait sept echecs, et la passe ciblee a corrige **huit fichiers de
style** (`App.css`, `Header.css`, `animations.css`, `variables.css`...).
Resultat: 10/100 avant, 10/100 apres, livrable precedent conserve.

Or **six de ces sept echecs n etaient pas des defauts**. Quand la page ne monte
pas, il n y a ni typographie, ni profondeur, ni interactivite A MESURER. On
notait l absence de rendu comme un defaut de gout, puis on envoyait le modele
repeindre une page qui ne s affiche pas.

C est la regle constante de ce module poussee d un cran: *un juge qui ne peut pas
mesurer ne condamne pas* — et **un juge dont la page n a jamais monte n a rien
mesure du tout**. Tant que le crash n est pas repare, les criteres en aval ne
sont pas « echoues », ils sont NON CONCLUANTS.

La passe ne recoit plus que la cause, avec une consigne qui interdit
explicitement de toucher aux styles et qui exige de reparer a la SOURCE de la
donnee (import, export par defaut, valeur initiale, props) plutot que de poser
un `?.` sur le symptome. Et sa portee est le fichier que la trace NOMME — une
preuve, plus une heuristique.

| memes fichiers | avant | apres |
|---|---|---|
| echecs envoyes au correcteur | 7 | **1 cause + 6 non concluants** |
| portee du patch | 8 fichiers de style | **1 fichier: `src/components/CoffeeCard.tsx`** |

Tests : **1117 -> 1124 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1111: un diagnostic parfait, une reparation impossible

Le run 1111 meurt dans la boucle de correction, avant meme les portes de
qualite. Et cette fois le pipeline diagnostique JUSTE, a chaque passe:

```
Passe 5 — importation manquante du fichier ./routeTree.gen dans src/App.tsx
Passe 6 — Le fichier routeTree.gen est requis par App.tsx mais n existe pas
Passe 7 — import manquant du fichier ./routeTree.gen dans src/App.tsx
Passe 8 — import manquant du fichier ./routeTree.gen dans src/App.tsx
Arret de la boucle : boucle infinie detectee sur la meme erreur apres 9 passes.
```

Mesure sur les fichiers reels:

```
package.json : "@tanstack/react-router": "1.42.13"
src/App.tsx  : import { routeTree } from './routeTree.gen'
fichiers routeTree* livres : AUCUN
```

`routeTree.gen` est produit par le plugin de codegen de TanStack Router — un
plugin qui **n etait meme pas dans les devDependencies**. Le modele ne pouvait
donc ni l ecrire (il est genere), ni l obtenir (le generateur est absent).

**Le diagnostic etait juste et aucune action disponible ne le resolvait.** Neuf
passes perdues d avance. C est le troisieme membre d une meme famille:

| run | conseil donne | pourquoi il est impossible |
|---|---|---|
| 1031 | « mets le secret dans `.env` » | aucun serveur dans le projet |
| 1081 | « ecris ce JPEG » | modele de texte |
| 1111 | « ajoute `routeTree.gen` » | fichier produit par un generateur absent |

### La regle: on n interdit pas la bibliotheque, on interdit de la choisir sans son generateur

- un **registre** des dependances a generateur, avec ce qu elles produisent et
  par quoi les remplacer (TanStack Router -> `react-router-dom`, Prisma ->
  `better-sqlite3`, Relay -> `@apollo/client`, graphql-codegen -> retire) ;
- l interdiction est **nommee dans la consigne du planificateur**, remplacant
  compris — pas un « evite les outils complexes » ;
- la substitution est **DETERMINISTE a la lecture du plan**: quand une
  correction n a qu une seule bonne reponse, on ne la delegue pas a un modele
  probabiliste ;
- les artefacts generes sont retires du plan, de la file **ET** du contrat — les
  trois, sinon le contrat reclame ce que la file ne produit plus, exactement le
  piege deja paye au run 1031 ;
- le conseil « ajoute le fichier » devient « **REMPLACE tel paquet par tel
  autre** ». Un conseil irrealisable transforme une porte en piege.

Detail qui aurait coute un run: le predicat couvre le specificateur **sans
extension** (`from './routeTree.gen'`), qui est la forme reellement ecrite dans
le code. Un test l a attrape avant le lancement.

Effet de bord voulu, releve par la coordination: la pile de routage cesse de
changer d un run a l autre sur le meme brief, puisque la seule option restante
est celle qui marchait deja aux runs precedents.

Note d honnetete: la 2e voie proposee — executer reellement le codegen — n a pas
ete prise. Installer et configurer un generateur par bibliotheque ouvrirait une
famille entiere d outils, mais chaque generateur a sa propre CLI, sa propre
configuration et ses propres versions; le cout et le risque sont sans commune
mesure avec le fait de ne pas choisir l outil. La porte reste ouverte.

Tests : **1124 -> 1133 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1121: huit passes de typage pendant que des fichiers manquaient

Le correctif codegen a tenu: plus aucune trace de `routeTree.gen`, et le run est
alle bien plus loin — jusqu a la compilation TypeScript reelle. Elle a reporte
**234 erreurs** sur l ensemble des passes:

```
TS2307: Cannot find module '../components/StorySection'
TS2307: Cannot find module './Logo'
TS2339: Property 'totalWeekly' does not exist on type 'OrdersState'
TS7006: Parameter 'link' implicitly has an 'any' type
```

Mesure exacte sur les 37 fichiers reellement livres: **deux** imports locaux non
resolus, et rien d autre.

```
src/components/Logo          <- src/components/Header.tsx
src/components/StorySection  <- src/pages/AboutPage.tsx
```

Le modele a ecrit du code qui importe des composants **que la file de generation
ne lui a jamais demande d ecrire**. La boucle a ensuite brule huit passes a
discuter du typage de `OrdersState` alors que des fichiers entiers manquaient.

### Un constat exact ne se delegue pas

Resoudre des imports locaux est mecanique: extensions, `/index`, `..`, paquets
npm exclus par construction. Aucune ambiguite, aucune heuristique — donc, ligne
directrice constante de ce module, aucune raison de confier ce constat a un
modele probabiliste.

Et on ne se contente pas de le SIGNALER: **les modules absents sont ajoutes a la
file et generes**. Un import est une intention explicite du modele; la file
etait simplement incomplete par rapport a ce que le code reference. Les liaisons
attendues (`import Logo from`, `import { helper } from`) sont relevees et
transmises comme exports a produire, pour que le module ecrit corresponde a
l usage qu en fait l importateur.

Deux tours au plus: un module cree peut a son tour en importer un autre, et le
budget VRAM est fini. Une completion qui echoue ne detruit rien.

### Ordre causal, deuxieme application

Un fichier qui importe un module absent **ne peut pas etre type correctement**.
Ses `TS2339`/`TS7006` sont des consequences, pas des defauts. Les `TS2307`
passent donc en tete, leurs consequences dans LES MEMES fichiers sont nommees
comme telles, et la sortie d origine reste integralement disponible. Une erreur
dans un AUTRE fichier n est jamais classee en consequence.

C est la meme regle qu au run 1101 (six criteres visuels non concluants sur une
page qui ne monte pas), appliquee cette fois au compilateur.

| | avant | apres |
|---|---|---|
| modules importes absents | 2, jamais generes | **ajoutes a la file et generes** |
| erreurs presentees au correcteur | 234 a plat | **cause structurelle en tete, consequences nommees** |

Detail: un test a attrape un bug de mon propre extracteur avant le lancement —
le motif de liaison franchissait l import PRECEDENT (`import React from
'react'`) et capturait deux instructions d un coup, rendant toute liaison
indetectable. Le test valait le run.

Tests : **1133 -> 1143 verts, 0 echec.**

## 2026-08-13 (suite) — Run 1131: il ne meurt plus, mais il ne finit plus

Le run 1131 ne detruit rien — il livre 31 fichiers en phase `interrupted`, avec
la cause exacte. C est l inverse du run 1041 qui jetait 32 fichiers apres sept
secondes. Mais il a tourne **111 minutes**, dont une heure sur place:

```
passe 8 entree en recuperation   15:13:40
passe 8 sortie (epuisee)         16:13:09
soit 59,5 min pour UN SEUL appel, 24 cycles, 0 Go de RAM libre
```

### Un compteur de tentatives ne borne aucune duree

Le bareme de backoff totalise ~2 minutes, et les six tentatives avaient ete
calibrees sur des echecs **rapides** — `fetch failed` revient tout de suite.
Mais chaque tentative peut consommer le timeout complet de l appelant: **20
minutes** pour une correction. Six tentatives x 20 min = **deux heures de pire
cas**, pendant lesquelles rien n avance.

C est une erreur de raisonnement, pas un mauvais reglage: **un nombre de
tentatives ne dit rien d une duree**. Seule une horloge borne une duree.

Budget d horloge TOTAL de 10 minutes par appel. Passe ce budget, on rend la
main, et le pipeline livre le travail preserve en `interrupted` — chemin deja
construit et teste au run 1041. Un `interrupted` honnete au bout de dix minutes
vaut mieux qu une heure de tourniquet muet.

### La verification de sante mentait

Elle interrogeait `/api/tags`, concluait « le service ecoute », et en deduisait
« le service peut generer » — alors que toutes les generations echouaient. D ou
la sequence repetee vingt-quatre fois:

```
health_check -> release_models -> model_fallback -> retry
```

**Pour la douzieme fois dans cette serie, une porte declarait ce qu elle n avait
jamais mesure.** Ici: elle mesurait que le serveur ecoute.

On mesure desormais la GENERATION — sans rien charger: on ne sonde qu un modele
**deja resident** (`/api/ps`), un seul jeton, 15 s de plafond. Si rien n est
resident, on ne devine pas: un echec de transport repete signe un service
degrade. Forcer un chargement ici aurait ajoute de la pression memoire sur une
machine dont les gels sont d origine memoire — exclu par principe.

Trois etats au lieu de deux (`down` / `degraded` / `ok`), et un service
**degrade se redemarre**: c est la seule action qui le repare. Le relacher et
retenter etait exactement le tourniquet.

| | avant | apres |
|---|---|---|
| plafond de recuperation | 6 tentatives (duree non bornee) | **10 min d horloge** |
| pire cas theorique | ~2 h | **10 min** |
| sante « ok » | le serveur ecoute | **une generation a repondu** |
| service qui ecoute mais ne sert pas | retry infini | **redemarrage** |

Tests : **1143 -> 1146 verts, 0 echec.**

## 2026-08-17 — Runs 1151/1161: les portes tombent, l arbitre reste

Deux runs consecutifs qui atteignent enfin les portes de qualite, et les
franchissent.

```
run 1151   acceptation 2/2 · rendu 100/100 · a11y 86 · perf 80   21,3 min
run 1161   acceptation 2/2 · rendu  80/100 · a11y 100 · perf 100  16,1 min
           « Arret de la boucle : livraison validee a 100% »  <- la SANDBOX valide
```

Cinq correctifs jusque-la non valides en conditions reelles le sont: budget de
prompt (les appels sans fin ont disparu — 58+ min -> 16), URL racine de
l acceptation, ordre causal du rendu, passe ciblee chirurgicale, budget de
recuperation.

### Trois verrous levés au run 1151

1. **Un branchement manquant.** Le bridge est devenu injoignable en cours de
   validation. Le classifieur l a reconnu, a arrete les passes et a ecrit « Ce
   n est PAS un defaut du code livre » — puis le run est sorti `error`. La phase
   `interrupted`, construite pour ce cas exact et deja utilisee sur le chemin
   Ollama, n etait pas branchee sur le chemin sandbox. Trois issues, pas deux.

2. **Une note qui affirmait une cause non mesuree** (« bridge arrete ou reseau
   coupe »). Verification: le bridge etait vivant, health 200. Affirmer une
   cause qu on n a pas mesuree envoie chercher au mauvais endroit. La note dit
   maintenant ce qu on sait, et liste des pistes sans en designer une.

3. **La passe ciblee ne verifiait pas son propre patch.** Elle a « corrige »
   `Footer.tsx` pour `real_iconography` et l emoji y etait toujours — mesure sur
   les fichiers livres. Elle mesure desormais son resultat avant de le proposer,
   sur ce qui est verifiable sans navigateur.

### Le dernier verrou: l arbitre jugeait sur le mauvais critere

Au run 1161 la passe reparait `no_empty_section` — de la COMPOSITION. L arbitre
l a jugee sur le score de RENDU: 80/100 avant, 80/100 apres. Inchange, ce qui
est normal — elle n avait aucune raison de le changer. Donc rejetee.

C est le piege du run 1091 revenu par une autre porte. Je l avais corrige **en
cas particulier** pour la composition; il revenait des qu une autre porte etait
concernee. La regle est generale:

> **Une passe se juge sur le critere qu elle repare, jamais sur un score voisin
> qu elle n avait aucune raison de changer.**

L arbitre recoit desormais toutes les portes mesurees. Toute porte qui etait en
echec et qui passe, sans perte de rendu, vaut adoption. Une porte CASSEE au
passage est verifiee AVANT — echanger un defaut contre un autre n est pas un
progres, et un test a attrape que mes controles etaient dans le mauvais ordre.

Honnetete: au run 1161 la passe n avait de toute facon pas repare la
composition. Ce correctif seul n aurait pas suffi a CE run — il supprime la
condamnation structurelle qui rendait toute passe non-rendu ininteressante.

Tests : **1157 -> 1162 verts, 0 echec.**

## 2026-08-17 (suite) — Run 1171: deux portes qui reclamaient l impossible

### Reprise et diagnostic

Le run 1161 franchissait tout: sandbox « livraison validee a 100% », acceptation
comportementale 2/2, accessibilite 100/100, performance 100/100, rendu 80/100
(seuil 70), en 16,1 min contre 58+ auparavant. Et il sortait `FAILED phase=error`.

J ai repris les deux blocages par la mesure, sur les fichiers REELS du run
(`output/code_assets/viewers/run-1161/project.json`, 31 fichiers), jamais sur
des fixtures.

**Premier blocage — une seule ligne de gabarit.** `index.html` livre contenait

```html
<link rel="icon" href="/favicon.ico" />
```

la ligne que tout modele recopie d un projet Vite. La critique statique a
repondu, en `severity: error` sur l axe `runtime` — donc bloquante:

```
[error] index.html - ressource locale referencee mais absente (/favicon.ico).
        Suggestion: Livrer le fichier reference.
```

« Livrer le fichier » est **inachevable**. Depuis le run 1081 les binaires sont
volontairement hors de la file de generation, parce qu aucun modele de texte
n ecrit un `.ico` valide — la preuve avait coute 42 297 octets de base64 tape a
la main et un JPEG tronque a 388 octets. Une porte reclamait donc exactement ce
que la file a cesse de produire. Quatrieme membre d une famille deja fermee
trois fois: le secret sans backend au run 1031, le JPEG au 1081, le fichier de
codegen au 1111.

**Deuxieme blocage — la porte du vide.** Elle declarait `no_empty_section`, la
passe ciblee reecrivait six fichiers, et le defaut restait. J ai remesure le
livrable element par element (`output/code/audit_v117/fill_probe.json`):

```
section.hero-section 1440x944  ->  fill 9 %  « quasi vide »
  h1.hero-title      1440x298   JETE (contient un <br>)
  div.hero-content   1440x704   JETE (conteneur)
  compte: p 700x37 + img 330x289 + a 128x17
```

La mesure **sommait l aire des elements du DOM sans enfant element**. Un titre
contenant un `<br>` — donc la quasi-totalite des titres reels — n etait jamais
compte. Le hero occupait 704 px sur 944 et la porte le declarait vide a 9 %.

Elle n avait meme aucune dynamique utile: une grille de quatre produits
entierement remplie sortait a 18,7 %, pour un seuil a 15 %.

**Et le cas qui avait CALIBRE ce seuil etait lui aussi un faux positif.** Le
commentaire disait « le cas reel mesure 12 % sur 658 px ». J ai reconstruit ce
projet (`output/code/audit_v94/project/dist`), remesure et **photographie**:
`output/code/audit_v117/v94_faq.png` montre une FAQ complete — titre,
sous-titre, cinq cartes en accordeon. Elle n a jamais ete vide.

> **Cette porte n a jamais attrape un vrai positif. Elle en fabriquait**, et
> chaque tir coutait une passe de modele.

Troisieme couche, du meme ordre: la preuve ne nommait **aucun fichier**. Le
correcteur recevait « Torréfié cette semaine, : 944px remplie a 9% » sur un
projet de 31 fichiers. Il a reecrit AdminPage, ContactPage, HomePage,
MarketCalendarPage, SubscriptionPage et `index.css` — et jamais
`src/components/HeroSection.tsx`, seul fichier a contenir cette section. Il ne
pouvait pas: la sonde de portee cherche `<section` dans la source, et le
composant ecrit `<motion.section>`.

### Modifications realisees

**Binaire lie et absent — reparer, puis ne plus condamner.**

1. `codeDanglingBinaryAssets.ts` (neuf). La reparation est **mecanique**: une
   icone se fabrique en SVG, qui est du texte. `repairDanglingIconLinks`
   remplace le lien pendant par un SVG inline en data URL, monogramme tire du
   `<title>` livre. Une correction deterministe ne se delegue pas a un modele
   probabiliste. `apple-touch-icon` et `mask-icon`, qui ne savent pas lire un
   SVG, sont retires plutot que mentis.
2. `codeStaticProjectIntegrity.ts`. Un binaire absent devient `warn` / axe
   `preview`: il pese sur le score, il porte un conseil **realisable** (SVG
   inline, data URL, ou retirer la reference), il ne fait plus echouer une
   livraison qui tourne. Symetrie tenue: un fichier **texte** absent reste
   bloquant — celui-la, le pipeline peut l ecrire.
3. Le predicat `isBinaryAssetPath` filtrait deja le contrat de plan (run 1081);
   la file et le contrat restent donc d accord avec la porte.

**Porte du vide — mesurer le contenu, et nommer le fichier.**

4. `codeCompositionGate.ts`. `computeSectionFill` mesure l **occupation
   verticale reelle**: l union des bandes ou du contenu est peint, les
   respirations courtes recollees (`SECTION_GAP_TOLERANCE`).
5. `render_audit.mjs`. Le texte est mesure au `Range` — donc **independant de
   l imbrication DOM** — plus les medias et les fonds image. Pas les degrades:
   c est justement le `min-height:100vh` degrade a deux lignes que cette porte
   doit continuer d attraper.
6. `codeCompositionAttribution.ts` (neuf). Attribution deterministe d une
   section rendue a son fichier source, par la classe et par le texte. La
   critique nomme desormais selecteur ET fichier, et cette liste alimente
   `evidencePaths` — la preuve prime deja sur toute heuristique de portee.
7. `codeTargetedRepairScope.ts`. La sonde ne rate plus `<motion.section>` ni
   `<HeroSection>`.

### Avant-apres mesurable

Fichiers reels du run 1161, mesures rejouees:

| | avant | apres |
|---|---|---|
| `<link rel="icon">` | `/favicon.ico`, absent | SVG inline en data URL |
| critique statique bloquante | **oui** | **non** |
| hero `section.hero-section` 944 px | 9,1 % « vide » | **72,0 %** |
| grille cafes 652 px | 18,7 % | **62,2 %** |
| temoignages 465 px | 17,9 % | **25,0 %** |
| composition | KO `no_empty_section` | **OK** |
| section attribuee | — | `src/components/HeroSection.tsx` |

Cas de calibration `audit_v94`, rejoue:

| section | ancien | nouveau |
|---|---|---|
| `section.hero-section` 900 px | 14,8 % → **declaree vide** | 46,2 % |
| `section.faq-section` 658 px | 11,8 % → **declaree vide** | **85,4 %** |
| `footer.footer` 478 px | 13,8 % → **declaree vide** | 63,7 % |
| sections declarees vides | **3** | **0** |

### Demonstration reproductible

```
node --experimental-strip-types --test 'src/__tests__/code*.test.ts'
```

Artefacts de mesure, tous sous `application/output/code/audit_v117/`:
`fill_probe.json` (detail element par element du hero), `compo_before.json` /
`compo_after.json` (composition du run 1161 avant/apres),
`compo_v94_calibration.json` (les deux mesures cote a cote sur le cas de
calibration), `static_before_after.json` (critique statique), et
`v94_faq.png` — la photo qui prouve que la FAQ « vide » etait pleine.

### Etat de satisfaction

Tests : **1162 -> 1192 verts, 0 echec.** `tsc` : 0 erreur dans le perimetre Code.

Les deux causes sont fermees a la racine et la meme faute revient une fois de
plus sous les deux: **une porte qui condamne quelque chose qu elle n a jamais
mesure.** L une reclamait un fichier que la file ne produit plus; l autre
comptait tout sauf le titre.

Ce qui reste ouvert et que je ne cache pas: la design-spec du run 1161 classait
une brulerie de cafe en archetype `ide_code_editor` (palette sombre violette)
— la porte est consultative, mais la classification est fausse. Et l image du
hero est materialisee en URL absolue vers le bridge local
(`http://127.0.0.1:3001/...`), ce qui casserait le site hors de cette machine.

## 2026-08-17 (suite) — Troisieme porte: le mot « idee » contient « ide »

Pendant que le run 1171 tournait, j ai repris la derniere anomalie du run 1161
que j avais signalee sans la traiter: la design-spec classait une brulerie de
cafe lyonnaise en archetype `ide_code_editor`, et signalait « Ecart design-spec
(palette) » a chaque passe. C est la meme faute, une troisieme fois.

### Reprise et diagnostic

**1. Recherche par sous-chaine.** `detectDesignArchetype` testait
`text.includes(hint)`. L indice `'ide'` est tombe dans le mot francais « idee »,
present deux fois dans le brief:

```
« …un slogan […] ou un truc dans le genre, trouve mieux si t'as une IDEe),
  et direct en dessous nos 3-4 cafes du moment… »
```

Mesure directe sur le brief reel: une seule occurrence suffisait.

**2. Aveuglement a la negation.** La cliente ecrit, textuellement:

```
« on n'est PAS un truc minimaliste blanc scandinave comme tout le monde fait
  pour le cafe en ce moment, j'en ai marre de voir ca partout »
```

`minimaliste` et `scandinave` etaient extraits comme **indices de style
demandes**. Ils partaient donc dans l archetype ET dans les requetes de
recherche de references: on allait chercher en ligne des exemples de ce que la
cliente venait de rejeter. C est le run 1021 (« le juge reclamait le gadget que
la cliente avait refuse »), revenu par une autre porte.

**3. Palette codee en dur.** `paletteFor` exigeait, en `required: true` et pour
**tout** projet web, un fond `oklch(0.13 0.012 252)` — un noir bleute — plus
l accent `#7c3aed` herite de l archetype IDE. Le brief demande:

```
« des couleurs chaudes, terracotta, marron torrefie, un peu de vert olive »
```

La porte mesurait donc un ecart contre une valeur que **personne n avait
demandee**, et poussait le modele a s eloigner du brief pendant deux passes.

### Modifications realisees

`codePromptHints.ts` (neuf) — un indice ne compte que comme **mot entier** et
**non nie**. La portee de la negation s arrete a la ponctuation: « pas de
tableau de bord, juste un blog » demande bien un blog.

> Piege paye pendant l ecriture, et je le note parce qu il illustre la regle:
> ma premiere version acceptait les pluriels en ajoutant `es`. Or `ide` + `es`
> = `idees` — j avais rouvert exactement le trou que je fermais. La mesure l a
> attrape tout de suite. Les suffixes `es` sont desormais reserves aux indices
> d au moins cinq lettres.

`codeBriefPalette.ts` (neuf) — les couleurs nommees dans le brief font autorite.
Distinction qui porte tout le module: ce qui est seulement **nomme**
(« terracotta ») est **propose**, jamais exige — une famille de couleur n est pas
un hex. Un hex ecrit dans le brief, lui, fait loi. Et un fond que le brief
contredit ne peut pas etre `required`.

`codeIntentAssets.ts` — un style refuse ne remonte plus dans `styleHints`, donc
plus dans la recherche de references.

### Avant-apres mesurable

Sur le brief REEL (`output/code/audit_v117/designspec_after.json`):

| | avant | apres |
|---|---|---|
| archetype | `ide_code_editor` | `dashboard_dataviz` |
| styleHints | …`minimaliste`, `scandinave`… | `elegant, pro, stylé, animations` |
| background | `oklch(0.13 0.012 252)` **required** | `#faf6f0`, **non requis** |
| foreground | `oklch(0.96 0.004 252)` **required** | `#2b2119`, **non requis** |
| accent | `#7c3aed` (violet d IDE) | `#5b3a26` (marron torrefie) |
| support | `#0f172a` | `#6b7a3a` (vert olive) |

### Etat de satisfaction

Tests : **1192 -> 1215 verts, 0 echec.** `tsc` : 0 erreur dans le perimetre Code.

Ce que je ne maquille pas: `dashboard_dataviz` vient du mot « /admin », que le
brief demande reellement — mais le livrable dominant reste une vitrine de
marque. Un archetype UNIQUE pour un brief qui porte deux produits est une limite
de la taxonomie, pas un defaut de mesure. Je la signale plutot que de la
recouvrir d une heuristique de plus.

## 2026-08-17 (suite) — Run 1171: deux portes tombent, une quatrieme se revele

### Verdict brut

```
run 1171   acceptation 2/2 · a11y 100/100 · perf 80/100 · rendu 62/100
           composition — AUCUNE ligne (donc OK)
           FAILED phase=error files=27      30,7 min, 9 passes
```

### Ce qui est prouve en reel

Les deux blocages vises sont fermes, sur le meme brief et le meme pipeline:

| | run 1161 | run 1171 |
|---|---|---|
| favicon / critique statique | `[error]` **bloquant** | absent |
| composition | `no_empty_section` **KO** | **OK** |

Pour le favicon, la seule occurrence du mot dans tout le flux du run 1171 est la
note de saut du contrat de plan (« Un modele de texte ne peut pas ecrire un
binaire valide »). L erreur bloquante a disparu.

Pour la composition, le runner n ecrit sa ligne que lorsque le verdict est KO.
Au run 1161, ligne 5: `composition: no_empty_section`. Au run 1171: aucune
ligne, et la passe ciblee rapporte `composition OK -> OK (aucun echec)`.

### La quatrieme porte

Le dernier sandbox du run 1171 passe **10 etapes sur 11**, score 91. La seule en
echec: « Installer les dependances » — **sortie de zero octet**.

J ai rejoue l installation sur le livrable reel:

```
npm install sur l hote                       exit 0 · 153 paquets · 5 s
npm install sous les MEMES drapeaux podman   exit 0
  (slirp4netns sans loopback, keep-id, read-only, tmpfs 256m, memory 2g,
   pids 256, fsize 512 Mio, volume nomme, registre npm joignable)
```

**Le projet s installe.** Le pipeline a rendu un verdict de QUALITE sur une
etape dont il ne reste aucune trace.

`isSandboxInfrastructureFailure` exigeait une SIGNATURE reconnue dans la sortie.
Une sortie vide ne correspond a aucun motif, donc elle tombait dans « defaut du
code ». Or une sortie vide ne decrit aucun defaut, ne se donne a aucun
correcteur, et ne se repare pas. Le precedent etait deja ecrit dans
`codeSandboxIsolation.ts`: un `RLIMIT_FSIZE` mal converti faisait echouer
`npm install` en EFBIG « avec une sortie vide cote pipeline, donc sans
diagnostic possible ».

Une etape en echec qui n a **rien produit** vaut desormais `interrupted` —
travail preserve, validation incomplete — et non `error`. Une etape muette **a
cote** d une erreur lisible ne blanchit rien: le test le verrouille.

### Ce qui reste ouvert, sans arrondi

1. **La cause exacte de l echec silencieux de `npm install` dans le sandbox
   n est pas trouvee.** Elle n est reproductible ni sur l hote, ni en podman nu
   avec les memes drapeaux, ni via le pont. Je corrige la CONSEQUENCE (ne plus
   condamner sans mesure), pas la cause. Le prochain run dira `interrupted` au
   lieu de `error` sur ce chemin — c est plus honnete, ce n est pas un `done`.

2. **Oscillation de la boucle de correction.** Neuf passes, score 20 -> 65 -> 68
   -> 72 -> 73, sans convergence. Les erreurs tournent en rond sur un contrat de
   types reparti entre plusieurs fichiers (`Order` / `OrderState`, le store,
   `AdminPage.tsx`, les formulaires react-hook-form): le modele aligne l usage
   sur le type, puis a la passe suivante aligne le type sur l usage. Ce n est PAS
   un conseil irrealisable — il peut le reparer, il ne le fait jamais des deux
   cotes a la fois. La reparation demande de traiter le type et TOUS ses
   consommateurs comme une seule unite, et de detecter le cycle (le score bouge,
   donc le detecteur de stagnation actuel ne le voit pas).

3. **Le rendu a 62/100** (contre 80 au run 1161) n est pas interpretable en
   l etat: ce run reclamait encore `editor pane`, `terminal panel` et un accent
   violet a une torrefactrice, le correctif d archetype ayant ete livre APRES son
   lancement. A remesurer sur un run parti sans ce handicap.

Tests : **1215 -> 1219 verts, 0 echec.**
