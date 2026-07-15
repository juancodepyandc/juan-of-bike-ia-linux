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
