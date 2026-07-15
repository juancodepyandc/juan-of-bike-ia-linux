// ---------------------------------------------------------------------------
// Project-level prompt sections
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntentTypes.ts'

export function appendProjectPromptSections(lines: string[], intent: CodeIntent): void {
  // R3F guidance for non-game React projects that need 3D (spa_react,
  // ssr_nextjs, fullstack_nextjs). Defined outside game_web branch so the
  // type narrows to the correct projectType subset.
  if ((intent.features.includes('3d') || intent.assetPlan?.wants3D)
    && (intent.projectType === 'spa_react' || intent.projectType === 'ssr_nextjs' || intent.projectType === 'fullstack_nextjs' || intent.frameworks.includes('react'))) {
    lines.push(
      '',
      '## React + 3D: utilise React Three Fiber (R3F) plutot que Three.js vanilla',
      '- React 19 + 3D: dependances compatibles `three@^0.183.2`, `@react-three/fiber@^9.6.1`, `@react-three/drei@^10.7.7`, `@react-three/postprocessing@^3.0.4`.',
      '- React 18 + 3D: utilise `@react-three/fiber@^8.18.0`, `@react-three/drei@^9.122.0`, `@react-three/postprocessing@^2.16.3`.',
      '- Interdit dans package.json: `react-three-fiber`, `react-three/drei`, `react-three/postprocessing`.',
      '- Si physique: `npm i @react-three/rapier`',
      '- Compose la scene en JSX: `<Canvas><PerspectiveCamera/><OrbitControls/><Environment preset="studio"/><Lights/><Models/></Canvas>`',
      '- Use drei helpers: `Environment`, `OrbitControls`, `AccumulativeShadows`, `ContactShadows`, `Float`, `Sparkles`, `Stars`, `useGLTF`, `useTexture`, `Html`, `Center`.',
      '- Postprocessing via `@react-three/postprocessing`: `<EffectComposer><Bloom/><DepthOfField/><Noise/></EffectComposer>`.',
      '- Hooks: `useFrame((state, delta) => { /* dt-aware animation */ })` pour les animations, `useThree()` pour acceder a camera/scene/renderer.',
      '- Suspense: `<Suspense fallback={<LoadingSpinner/>}>` autour des `useGLTF` et autres lecteurs asynchrones.',
      '- INTERDIT d ecrire de la logique Three.js imperative dans useEffect quand un equivalent declaratif R3F existe.',
      '- Les overlays HUD en HTML doivent etre hors `<Canvas>` ou via `<Html>` de drei, jamais un `<div>` direct comme enfant de Canvas.',
      '- Refs R3F: si tu assignes a `.current`, type les refs avec `| null` (`useRef<THREE.Mesh | null>(null)`).',
      '- Stores Zustand: un setter appele avec une fonction `prev => ...` doit etre type et implemente pour accepter les updates fonctionnels.',
      '- Si la demande parle de pilotage/WASD/shift/espace: implemente un vrai etat joueur/vaisseau (position, velocity, fuel/energy) mis a jour dans `useFrame(delta)` par des handlers keydown/keyup.',
      '- Si la demande parle de minimap/radar/scanner: affiche une minimap derivee des positions reelles des objets, pas une decoration statique.',
      '- Si la demande parle de collecte/ressources/docking/scan: cable les interactions avec `distanceTo`, raycaster, collisions ou volumes 3D, et mets a jour le HUD/objectifs.',
    )
  }

  // Add complexity-specific instructions
  if (intent.complexity === 'complex' || intent.complexity === 'enterprise') {
    lines.push(
      '',
      '## Instructions architecture complexe',
      '- Organise les fichiers en modules/dossiers logiques',
      '- Separe clairement les couches (routes, services, models, utils)',
      '- Inclus un fichier de configuration principal',
      '- Inclus package.json / requirements.txt / Cargo.toml selon la stack',
      '- Inclus un README.md avec les instructions de lancement',
      '',
      '## Performance et optimisation',
      '- Applique les patterns de performance du framework (memo, useMemo, useCallback pour React)',
      '- Lazy loading des routes et composants lourds',
      '- Code splitting et dynamic imports',
      '- Gestion efficace de l etat (normalisation, selecteurs)',
      '- Pagination/virtualisation pour les listes longues',
      '- Debounce/throttle pour les inputs frequents',
      '- Caching cote serveur si API',
      '- Indexation DB si base de donnees',
    )
  }

  // Add preview-specific instructions
  if (intent.needsDevServer) {
    lines.push(
      '',
      '## Instructions dev server',
      '- Le projet DOIT pouvoir demarrer avec une seule commande',
      `- Commande attendue: ${intent.devCommand}`,
      '- Inclus tous les fichiers de configuration necessaires (vite.config, tsconfig, etc.)',
      '- Le port par defaut doit etre configurable ou standard (3000, 5173, 8000)',
    )
  }

  // Multi-page instructions
  if (intent.features.includes('multipage')) {
    lines.push(
      '',
      '## Instructions multi-page',
      '- Implemente un vrai systeme de routing (React Router, Vue Router, etc.)',
      '- Chaque page doit avoir son propre composant/fichier',
      '- Inclus une navigation coherente entre les pages',
      '- Layout partage (header, sidebar, footer) si pertinent',
      '- Gestion propre de l etat global si necessaire',
    )
  }
}
