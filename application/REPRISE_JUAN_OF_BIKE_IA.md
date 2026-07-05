# Reprise juan of bike IA

## Etat actuel
- La base active `C:\Users\Juan\Desktop\AuroraIA-v2` est maintenant alignee sur le shell Tauri avance de `juan of bike IA`.
- Build frontend verifie le 29/03/2026:
  - `npm run build` OK
- Build natif Tauri verifie le 29/03/2026:
  - `npm run tauri:build` OK
  - binaire genere: `C:\Users\Juan\Desktop\AuroraIA-v2\src-tauri\target\release\juan-of-bike-ia.exe`

## Refonte UI appliquee
- Nouveau shell radical "command deck / top dock":
  - `src/App.tsx`
  - `src/styles/globals.css`
  - `src/components/TitleBar.tsx`
  - `src/components/Sidebar.tsx`
  - `src/components/MissionControlRail.tsx`
- La colonne gauche a ete supprimee.
- Navigation modules transformee en dock horizontal compact.
- Header module simplifie en bandeau d etat.
- Rail lateral reduit aux infos utiles.
- Mode focus + bouton plein ecran dans `src/components/TitleBar.tsx`.
- Boot overlay anime dans une direction sombre / reactor.
- Garde-fous anti-crash:
  - `src/components/AppErrorBoundary.tsx`
  - `src/components/ModuleErrorBoundary.tsx`
- Les corps de modules sont scrollables, le bas des vues ne reste plus bloque.
- Le Copilote a maintenant un grand composeur visible en permanence dans `src/views/ConversationView.tsx`.
- Le Copilote est traite comme IA globale:
  - demande libre
  - progression visible
  - verification
  - orientation vers les ateliers si necessaire
- La vue conversation a ete refaite en deck compact:
  - zone d ecriture centrale
  - cartes runtime / machine / modele
  - raccourcis modules a droite
  - beaucoup moins de texte descriptif

## Runtime et autonomie
- Runtime Tauri et orchestration locale synchronises:
  - `src/hooks/useTauri.ts`
  - `src/hooks/useManagedRuntime.ts`
  - `src/hooks/useRuntimeTelemetry.ts`
  - `src/hooks/useStudioDiagnostics.ts`
  - `src/utils/runtime.ts`
  - `src/stores/appStore.ts`
  - `src/types/app.ts`
- Backend Tauri aligne avec auto-demarrage / inspection / liberation:
  - `src-tauri/src/commands.rs`
  - `src-tauri/src/lib.rs`
- Les modules visuels et code utilisent le runtime gere pour preparer, generer puis nettoyer les ressources.

## Fidelite et precision
- Contrat de prompt durci par module:
  - `src/services/realityAnalyzer.ts`
- Regles de qualite globales ajoutees au workflow FLUX:
  - `src/utils/fluxWorkflow.ts`
- Modules relies a ce contrat:
  - `src/views/ImageView.tsx`
  - `src/views/CodeView.tsx`
  - `src/views/DrawingView.tsx`
  - `src/views/VideoView.tsx`
  - `src/views/ModelView.tsx`

## Modules recables sur le shell avance
- `src/views/ConversationView.tsx`
- `src/views/ImageView.tsx`
- `src/views/CodeView.tsx`
- `src/views/DrawingView.tsx`
- `src/views/VideoView.tsx`
- `src/views/ModelView.tsx`

## Points utiles si on reprend
- Si l utilisateur veut encore plus de rupture visuelle:
  - pousser le dock modules vers un vrai systeme de piles / cartes animées
  - rendre chaque atelier specialise (`image`, `code`, `video`, `3d`) aussi radical que le shell principal
  - introduire un vrai canvas de fond reactif leger au lieu des simples halos
- Si l utilisateur veut plus de precision generation:
  - specialiser encore `buildModuleRules()` par sous-cas (portrait, produit, scene, code app, etc.)
  - brancher une validation automatique post-generation par module

## Commandes de reprise
- Frontend: `npm run build`
- Dev Tauri: `npm run tauri:dev`
- Build Tauri: `npm run tauri:build`
