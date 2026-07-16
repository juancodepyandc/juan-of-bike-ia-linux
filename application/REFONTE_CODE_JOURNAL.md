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
