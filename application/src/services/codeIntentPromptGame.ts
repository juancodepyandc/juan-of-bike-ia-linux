// ---------------------------------------------------------------------------
// Game and 3D prompt sections
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntentTypes.ts'
import { CODE_THREE_ADDONS_BASE, CODE_THREE_CDN_BASE } from './codeRuntimeDependencies.ts'

export function appendGamePrompt(lines: string[], intent: CodeIntent): void {
  if (intent.projectType !== 'game_web') return
const is3D = intent.features.includes('3d') || intent.assetPlan?.wants3D
const isGame = intent.features.includes('game')
const gameKind = intent.gameKind
const knownGame = intent.knownGame

// -----------------------------------------------------------------------
// CASE 1 — 3D app / scene (no game mechanics)
// -----------------------------------------------------------------------
if (is3D && !isGame) {
  lines.push(
    '',
    '## Instructions application / scene 3D interactive PREMIUM',
    '',
    '### REGLE ABSOLUE — VRAIE 3D, PAS UN GADGET',
    "- Tu generes une SCENE 3D RICHE et INTERACTIVE qui rend a 60 fps avec un design VISUELLEMENT PREMIUM.",
    '- INTERDIT de livrer "un cube qui tourne au centre" ou "une sphere flottante seule" — le resultat doit etre a la hauteur des references comme Bruno Simon, Lusion, ou Three.js Journey.',
    '- INTERDIT de livrer du HTML qui SIMULE de la 3D (transforms CSS 3D) — il faut WebGL avec un VRAI rendu Three.js.',
    '',
    '### Stack obligatoire (CDN jsdelivr ESM, versions figees)',
    `- \`import * as THREE from "${CODE_THREE_CDN_BASE}/build/three.module.js"\``,
    `- \`import { OrbitControls } from "${CODE_THREE_ADDONS_BASE}/controls/OrbitControls.js"\``,
    `- \`import { GLTFLoader } from "${CODE_THREE_ADDONS_BASE}/loaders/GLTFLoader.js"\` si le scenario charge un GLB`,
    `- \`import { RGBELoader } from "${CODE_THREE_ADDONS_BASE}/loaders/RGBELoader.js"\` pour HDRI`,
    `- Post-processing: \`EffectComposer\`, \`RenderPass\`, \`UnrealBloomPass\`, \`OutputPass\`, \`SMAAPass\` depuis \`${CODE_THREE_ADDONS_BASE}/postprocessing/...\``,
    '- Physique (si la demande implique chute, collision, swing, drag&throw, dominoes): `import RAPIER from "https://cdn.jsdelivr.net/npm/@dimforge/rapier3d-compat@0.19/+esm"` puis `await RAPIER.init()`',
    "- Si l import echoue (mode hors ligne), utilise des primitives THREE only mais GARDE le post-processing et l environnement HDRI procedural.",
    '',
    '### Architecture obligatoire de la scene',
    '1. **Canvas fullscreen**: `width/height = window.innerWidth/Height`, listener `resize` qui met a jour `camera.aspect`, `camera.updateProjectionMatrix()`, `renderer.setSize()` ET `composer.setSize()` si post-processing.',
    '2. **Renderer premium**: `new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" })`, `setPixelRatio(Math.min(window.devicePixelRatio, 2))`, `outputColorSpace = THREE.SRGBColorSpace`, `toneMapping = THREE.ACESFilmicToneMapping`, `toneMappingExposure ≈ 1.1`, `shadowMap.enabled = true`, `shadowMap.type = THREE.PCFSoftShadowMap`.',
    '3. **Camera cinematic**: `PerspectiveCamera(45-55 fov, aspect, 0.1, 200)`, position pensee comme un cadrage photo (3/4 angle, decale du sujet), avec un look-at sur le centre d interet.',
    '4. **Scene composee**: minimum 5-15 objets distincts avec une COMPOSITION SPATIALE pensee (foreground / mid / background, regle des tiers), JAMAIS un seul mesh isole.',
    '5. **Eclairage triple-light minimum**:',
    '   - 1 `HemisphereLight` (skyBlue→groundOrange, intensity 0.4-0.6) pour la lumiere ambiante naturelle.',
    '   - 1 `DirectionalLight` cle (intensity 1.5-2.5) avec `castShadow=true`, `shadow.mapSize=2048`, `shadow.bias=-0.0001`, frustum cale sur la scene.',
    '   - 1 `PointLight` ou `SpotLight` accent coloree (rim light, fill light) qui sculpte les volumes.',
    '   - Les couleurs des lumieres doivent etre stylees (pas du blanc plat partout) — palette violet/orange, teal/magenta, gold/blue selon le mood.',
    '6. **Materials PBR** uniquement: `MeshStandardMaterial` ou `MeshPhysicalMaterial` (jamais `MeshBasicMaterial` sauf billboards/ciel). Configure `roughness`, `metalness`, `clearcoat`, `transmission`, `ior`, `iridescence`, `sheen` selon le sujet — lis chaque parametre comme un photographe lit la lumiere.',
    '7. **Environment / IBL**:',
    `   - Charge un HDRI procedural via \`RoomEnvironment\` (\`import { RoomEnvironment } from "${CODE_THREE_ADDONS_BASE}/environments/RoomEnvironment.js"\`) ou un HDRI distant (Polyhaven, BridgeAPI) si autorise.`,
    '   - Si offline only: cree un GradientTexture procedural (CanvasTexture mappee comme equirectangular) qui simule un studio 3-point.',
    '   - Affecte le resultat a `scene.environment` ET a `scene.background = environment` ou un fond travaille.',
    '8. **Sol et reflexion**: ajoute un sol PBR (plane 100x100, MeshPhysicalMaterial avec `clearcoat:0.1, roughness:0.4`) ou un MeshReflectorMaterial pour reflexion subtile. Active les ombres sur ce plan.',
    '9. **Brouillard atmospherique**: `scene.fog = new THREE.Fog(0x1a1d2e, 8, 60)` pour la profondeur — adapte la couleur au theme.',
    '10. **Animation**: boucle `animate()` via `requestAnimationFrame` avec **DELTA TIME** (`const dt = clock.getDelta()`), animations diverses (rotation, sin-flottement, pulse opacity, bobbing). PAS de transformations sans dt.',
    '11. **Controls**: `OrbitControls` avec `enableDamping=true`, `dampingFactor=0.06`, `enablePan=true`, `minDistance` et `maxDistance` raisonnables, `autoRotate=true` jusqu au premier clic utilisateur.',
    '12. **Resize**: handler unique qui touche camera + renderer + composer simultanement.',
    '13. **Cleanup**: `window.addEventListener("beforeunload", ...)` qui appelle `renderer.dispose()`, `geometry.dispose()`, `material.dispose()` sur tous les meshes et `composer.dispose()` si present.',
    '',
    '### Post-processing OBLIGATOIRE (sauf si offline force le fallback)',
    '- Pipeline: `RenderPass(scene, camera) -> UnrealBloomPass(resolution, strength=0.5-0.9, radius=0.6, threshold=0.85) -> OutputPass()`',
    "- Optionnel mais bienvenu: `SMAAPass` pour anti-aliasing post, `OutlinePass` si highlight d'objets.",
    '- Le bloom doit etre subtil et stylise, jamais "flou cloud blanc partout".',
    '- Le composer prend la place de `renderer.render()` dans la boucle.',
    '',
    '### Physique avec Rapier (uniquement si demande implicite ou explicite)',
    '- Si le prompt mentionne: chute, gravite, collision, drag and drop, dominoes, pendule, balle qui rebondit, blocs empiles, swing, cordes — tu DOIS utiliser Rapier.',
    '- Workflow: `await RAPIER.init()` -> `world = new RAPIER.World({x:0, y:-9.81, z:0})` -> chaque mesh THREE a un `RigidBodyDesc` + `ColliderDesc`. La boucle anim fait `world.step()` puis copie `body.translation()` et `body.rotation()` dans le mesh THREE.',
    '- Ne JAMAIS animer manuellement par sin si la physique est requise — laisse le solveur le faire.',
    '- Pour des cordes/cables: chaine de RigidBody + JointData.spherical entre paires consecutives.',
    '- Pour des objets statiques: `RigidBodyDesc.fixed()`, pour les objets dynamiques `dynamic()`, et `kinematic*` pour les objets qui suivent un mouvement programme.',
    '',
    '### Effets et detail premium',
    '- **Particules**: utilise `THREE.Points` avec `BufferGeometry` + custom `ShaderMaterial` ou `PointsMaterial` size attenue, pour un effet poussiere/galaxie/bulles.',
    '- **Instanced meshes**: si plus de 100 objets repetitifs (foret, grille, swarm) -> `InstancedMesh` obligatoire pour 60 fps.',
    '- **GLSL shader**: ajoute au moins un shader custom pour eviter le rendu plat.',
    '  - Vertex shader minimal: passe `vUv`, `vNormal`, `vWorldPosition` au fragment.',
    '  - Fragment shader: gradient procedural, hologramme (fresnel + scanlines), glow rim (Fresnel * emissive), water (sin(uv.x + time) noise displacement), iridescence (couleur fonction de l angle de vue).',
    '  - Uniforms: `uTime` (mis a jour dans useFrame ou animate), `uColorA`, `uColorB`, `uIntensity` exposes via dat.gui ou sliders HTML overlay.',
    '  - Shader atlas pret a l emploi: voir https://thebookofshaders.com et https://shadertoy.com pour patterns (mais reecris-les en GLSL ES 1.0 / 3.0 compatible WebGL).',
    '- **WebGPU detection** + TSL (Three Shader Language):',
    '  - Detection: `if (navigator.gpu) { const renderer = new (await import("three/webgpu")).WebGPURenderer({ antialias: true }); await renderer.init(); } else { /* fallback classic WebGLRenderer */ }`',
    '  - Pour les nouveaux projets 3D premium, prefere directement `three/webgpu` + TSL plutot que GLSL ES — TSL = nodes javascript composables avec autodiff GPU, plus expressif et compatible WebGL2 fallback automatique.',
    '  - Imports TSL: `import { uniform, time, sin, vec3, mix, fract, smoothstep, normalLocal, positionLocal } from "three/tsl"` ; `import { MeshStandardNodeMaterial } from "three/webgpu"`.',
    '  - Exemple TSL hologramme: `const fresnel = vec3(1).sub(positionLocal.length()).pow(2)` puis `material.emissiveNode = fresnel.mul(uColor.mul(uniform(time).sin().add(1)))`.',
    '  - Compute shaders TSL pour particules / instancing: `const compute = Fn(() => { const i = instanceIndex; positionStorage.element(i).addAssign(velocityStorage.element(i).mul(deltaTime)); })`.',
    '  - Fallback: si `navigator.gpu` est absent, garde le code WebGL classique avec ShaderMaterial GLSL — la sortie defaut reste universelle.',
    '- **Animation skeletale**: si la scene charge un GLB avec un AnimationClip, instancie un `AnimationMixer`, joue l action en `LoopRepeat`, et progresse `mixer.update(dt)` dans la boucle.',
    '- **Pickable / hover**: `Raycaster` sur `pointermove` pour highlight les meshes (changement subtil d emissive).',
    '- **Transitions / camera path**: si scenes multiples, tween la camera via `Tween.js` ou interpolation manuelle quaternion.',
    '',
    '### Interaction utilisateur OBLIGATOIRE',
    '- Au moins une de ces interactions selon le sujet:',
    '  - Click sur un mesh -> change couleur / pulse / camera focus / spawn particules.',
    '  - Drag mesh (avec ou sans Rapier kinematic) -> deplace dans le plan camera.',
    '  - Hover -> tooltip 2D superpose ou highlight emissive.',
    '  - Touche clavier (WASD ou fleches) -> deplace camera ou objet.',
    '  - Slider HTML overlay -> modifie un parametre temps reel (intensity, speed, count).',
    '- L UI 2D (sliders, boutons, label info) doit etre stylee (glassmorphism: `backdrop-filter: blur(14px)`, fond rgba(255,255,255,0.06), bordure rgba(255,255,255,0.12), radius 12-16px).',
    '',
    '### Code structure obligatoire',
    '- HTML: `<canvas id="scene"></canvas>` fullscreen (`position:fixed; inset:0`) + `<div id="ui">` overlay.',
    '- CSS: body `margin:0; overflow:hidden; background:#0a0a0f`, font-family premium, UI overlay glassmorphism.',
    '- JS: un fichier en `<script type="module">` avec import map si necessaire. Structure: imports -> setup renderer/scene/camera -> setup lights -> setup environment -> create meshes -> setup controls -> setup post-processing -> animate loop -> resize handler -> interaction handlers.',
    '- INTERDIT: code "tutorial debutant" en un seul script de 50 lignes — vise 250-600 lignes JS, organise par sections claires avec commentaires de section.',
    '',
    '### Verification finale (mental walk-through)',
    '- Au chargement: la scene affiche immediatement une composition 3D riche avec lumieres, ombres, materiaux, et au moins UN element en mouvement.',
    '- A l interaction souris: la camera tourne smoothly, un click sur un mesh declenche un feedback visuel.',
    '- Le canvas n est JAMAIS noir/vide. Le sol est visible avec ses ombres.',
    '- Le bloom rend la scene cinematique sans floutage abusif.',
    '- Si le prompt parlait d un sujet specifique, le sujet est clairement reconnaissable au centre de la composition.',
  )
}

// -----------------------------------------------------------------------
// CASE 2 — Known game clone
// -----------------------------------------------------------------------
else if (gameKind === 'clone' && knownGame) {
  lines.push(
    '',
    `## Instructions jeu — Clone fidele de ${knownGame.canonical}`,
    '',
    `### REGLE ABSOLUE: Tu dois recreer ${knownGame.canonical} a l IDENTIQUE`,
    `- Genre: ${knownGame.genre}`,
    '- Le joueur doit reconnaitre immediatement le jeu original. AUCUNE deviation creative sauf si l utilisateur l a explicitement demandée.',
    '- ZERO simplification des mecaniques. Tout doit etre implementé tel que décrit ci-dessous.',
    '',
    '### Mecaniques obligatoires (implementer TOUTES sans exception):',
    ...knownGame.coreMechanics.map((m) => `- ${m}`),
    '',
    `### Style visuel: ${knownGame.visualStyle}`,
    `### Controles: ${knownGame.controls}`,
    `### Conditions victoire/defaite: ${knownGame.winLoseCondition}`,
    '',
    '### Exigences techniques non-negociables:',
    '- Un seul fichier HTML auto-suffisant (canvas + JS + CSS inline). Aucune dependance externe sauf si Three.js est explicitement requis.',
    '- Boucle de jeu: requestAnimationFrame avec delta time (Date.now() ou performance.now()) pour un framerate independant.',
    '- Gestion complete des evenements clavier (keydown + keyup pour les directions, prevention du scroll par espace/fleches).',
    '- Gestion tactile (touchstart/touchend) si le jeu est jouable au tap.',
    '- localStorage pour les meilleurs scores.',
    '- Feedback visuel ET sonore: Web Audio API (AudioContext) pour au moins 3 sons synthétisés (action principale, score, game over).',
    '- Ecrans complets: demarrage, pause (touche P ou Escape), game over avec score + meilleur score + "Rejouer".',
    '- Responsive: canvas s adapte a la taille de la fenetre (resize listener).',
  )
}

// -----------------------------------------------------------------------
// CASE 3 — Creative / original game
// -----------------------------------------------------------------------
else if (gameKind === 'creative') {
  lines.push(
    '',
    '## Instructions jeu — Creation originale et creative',
    '',
    '### TU ES LIBRE ET TU DOIS SURPRENDRE',
    '- L utilisateur veut quelque chose d ORIGINAL. Ne te limite pas a un clone generique.',
    '- Invente un concept qui mixe des genres, ajoute une mechanique de twist inattendue, ou exploite une idee visuellement forte.',
    '- Exemples d originalite: physique bizarre, perspective inhabituelle, regles qui evoluent en cours de partie, meta-mechanique, ambiance narrative unique.',
    '',
    '### Qualite de la creation:',
    '- Concept clair et coherent: le joueur comprend les regles en moins de 5 secondes.',
    '- Mecaniques deep mais accessibles: facile a apprendre, difficile a maitriser.',
    '- Progression satisfaisante: difficulte croissante, courbe de progression bien dosee.',
    '- "Juice" obligatoire: particles, screen shake, sons synthetises, animations fluides, feedback immediat sur chaque action.',
    '',
    '### Exigences techniques:',
    '- Fichier HTML auto-suffisant, boucle requestAnimationFrame avec delta time.',
    '- Web Audio API pour les sons (synthetisés, pas de fichiers audio externes).',
    '- Gestion clavier complete + support tactile.',
    '- Ecrans: intro stylée avec instructions, jeu, pause, game over/victoire avec score.',
    '- localStorage pour le meilleur score.',
    '- Responsive canvas.',
    '- INTERDICTION de generer un jeu "generique" (snake/tetris/pong standard) — sois VRAIMENT creatif.',
  )
}

// -----------------------------------------------------------------------
// CASE 4 — Generic game request (no specific title, no clear creative intent)
// -----------------------------------------------------------------------
else {
  lines.push(
    '',
    '## Instructions jeu web',
    '- Tu generes un jeu jouable AU CHARGEMENT: boucle requestAnimationFrame avec delta time, controles clavier/souris/tactile responsifs.',
    '- La scene doit afficher quelque chose d interactif DES LE CHARGEMENT — PAS un ecran vide, PAS un bouton "Start" isolé sans visuel derrière.',
    '- Implemente des mecaniques completes: score, vies/HP, collision precise, feedback visuel ET sonore (Web Audio API).',
    '- Ecrans obligatoires: demarrage/intro, jeu en cours, pause, game over avec score + meilleur score + "Rejouer".',
    '- Progression: la difficulté augmente progressivement (vitesse, nombre d ennemis, patterns...).',
    '- Design premium: arriere-plan anime, particules, effets visuels sur les actions (screen shake, flash, trainees).',
    '- Fichier HTML auto-suffisant. localStorage pour le meilleur score. Responsive canvas.',
  )
}

// Shared boot + completeness contract for EVERY game kind. A weak model
// routinely defines a gameLoop() but never calls it, or leaves the start
// overlay display:none and never shows it — the page then renders a frozen
// blank canvas. These rules (mirrored by checkGamePlayability) make the
// requirement explicit and machine-checkable.
lines.push(
  '',
  '## CONTRAT DE DEMARRAGE & COMPLETUDE (OBLIGATOIRE — verifie automatiquement)',
  "- AU CHARGEMENT : l'ecran de demarrage doit etre VISIBLE immediatement (overlay visible par defaut, PAS cache en display:none sans code pour l'afficher). Le bouton/indice pour lancer doit etre cliquable a l'ecran.",
  '- DEMARRER LA BOUCLE : appelle reellement la fonction de boucle (ex. gameLoop()) au lancement (clic Demarrer OU au chargement). Une boucle seulement DEFINIE mais jamais APPELEE = ecran fige = ECHEC.',
  '- Le canvas ne doit JAMAIS rester vide : dessine la scene des la premiere frame.',
  "- Implemente TOUTES les mecaniques nommees dans la demande, SANS exception : si la demande parle de particules, de score, de vies, d'ennemis a eliminer en sautant dessus, de plusieurs ecrans (demarrage / game over / victoire), CHACUN doit etre reellement code et cable.",
  "- Controles clavier : addEventListener('keydown' ET 'keyup'), preventDefault() sur les fleches et la barre d'espace, vitesse appliquee a chaque frame (mouvement fluide).",
  '- HUD permanent : score et vies affiches en continu pendant la partie.',
  '',
  '## AUTO-VERIFICATION AVANT DE LIVRER (simule une partie dans ta tete, corrige TOI-MEME)',
  "Avant d'ecrire ta reponse finale, deroule mentalement cette partie et corrige tout point qui echoue :",
  "1. J'ouvre la page -> l'ecran d'accueil s'affiche (visible, pas cache).",
  '2. Je clique "Jouer" (ou touche) -> la BOUCLE demarre (la fonction de boucle est bien APPELEE) et le canvas se dessine.',
  '3. Je presse fleche droite/gauche -> le personnage se deplace reellement (la touche modifie sa position a chaque frame).',
  '4. Je presse espace -> il saute puis RETOMBE (gravite appliquee dans la MEME boucle qui tourne, pas une boucle morte a cote).',
  '5. Je touche un collectible -> score augmente + effet (particules) ; je remplis la condition -> ecran Victoire.',
  '6. Je perds toutes mes vies -> ecran Game Over. Un SEUL ecran visible a la fois (les autres restent caches).',
  "Chaque mecanique nommee dans la demande DOIT passer son etape. Si une etape echoue dans ta simulation, CORRIGE le code avant de repondre — ne livre jamais une etape cassee. Une seule boucle requestAnimationFrame fait foi (ne definis pas deux boucles dont une jamais appelee).",
  '',
  '## PIEGES CLASSIQUES QUI FIGENT LE JEU (verifie que tu n en fais AUCUN)',
  "- Variable de garde testee mais jamais mise a vrai : ex. `if (!this.isRunning) return` au debut de la boucle alors que `this.isRunning` n'est JAMAIS affecte a true (souvent confondu avec une variable globale du meme nom). Resultat : la boucle sort immediatement, ecran fige. -> UNE seule source de verite pour l'etat \"en cours\", et mets-la a true AVANT le premier tour de boucle.",
  '- Deux boucles dont une seule est appelee : la gravite / la mise a jour doit etre DANS la boucle reellement lancee par requestAnimationFrame, pas dans une fonction definie mais jamais appelee.',
  "- Dans une classe, utiliser `this.canvas` / `this.ctx` sans les avoir recus dans le constructeur : ils valent undefined -> calculs NaN (le joueur ne bouge pas / sort de l'ecran). Passe explicitement le canvas/contexte aux entites qui en ont besoin (ou des bornes width/height).",
  '- Ecrans superposes : game over ET victoire affiches en meme temps. Tous les overlays sont display:none PAR DEFAUT ; on en affiche UN SEUL via .style.display selon l\'etat, et on cache les autres.',
  '- Restes de Markdown (```), texte hors-code, ou commentaire "// a implementer" / "TODO" a la place du vrai code : INTERDIT. Le fichier doit etre du code pur et complet.',
)

// 3D upgrade hook: when the prompt is a known game clone or generic game
// request AND the user implicitly asks for 3D (or the game is naturally
// 3D like Subway Surfers, Crossy Road, Minecraft, FPS), apply the same
// premium 3D rules as case 1.
if (is3D && (isGame || gameKind)) {
  lines.push(
    '',
    '### Bonus 3D pour ce jeu (rendu premium)',
    '- Three.js 0.160 ESM (CDN jsdelivr) avec OrbitControls / PointerLockControls / FirstPersonControls selon le gameplay.',
    '- WebGLRenderer ACES + sRGB + PCFSoftShadowMap, toneMappingExposure ~1.05.',
    '- Eclairage triple: hemisphere + directional cle (shadow.mapSize 2048) + point/spot accent colore.',
    '- MeshStandardMaterial / MeshPhysicalMaterial uniquement, environment map (RoomEnvironment ou HDRI) attache a scene.environment.',
    '- Post-processing UnrealBloomPass (subtil, threshold 0.85) + OutputPass.',
    '- Physique Rapier3D-compat si le gameplay implique chute / impact / collision / projectiles.',
    '- Boucle: requestAnimationFrame avec delta time, world.step(dt) si Rapier, mixer.update(dt) si AnimationMixer GLB.',
    '- InstancedMesh pour tout objet repete >100 fois (foret, foule, particles geometriques).',
    '- Sol PBR avec ombres recues + skybox/fog atmospherique adapte au mood.',
  )
}

// R3F (react-three-fiber) variant: this is inside the game_web branch so
// projectType is already 'game_web', but the user might import React via
// CDN from inside that game_web project (game built on top of React). In
// that case we still want R3F-flavored guidance.
if (is3D && intent.frameworks.includes('react')) {
  lines.push(
    '',
    '## Variante React: utilise React Three Fiber (R3F) PLUTOT que Three.js vanilla',
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

// Common performance rules for all game types
lines.push(
  '',
  '## Regles de performance jeu (non-negociables):',
  '- Delta time obligatoire: `const delta = (now - lastTime) / 1000` pour etre independant du framerate.',
  '- Jamais de setInterval pour la logique de jeu — uniquement requestAnimationFrame.',
  '- Gerer le cas ou la page perd le focus (document.visibilitychange → pause automatique).',
  '- Nettoyer les event listeners quand le jeu est detruit (important si reload).',
  '- Sons: AudioContext cree au premier geste utilisateur (politique autoplay navigateur).',
  '- Canvas: utiliser `ctx.save()` / `ctx.restore()` pour isoler les transformations.',
)
}
