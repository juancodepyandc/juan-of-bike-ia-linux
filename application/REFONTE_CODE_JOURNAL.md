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
