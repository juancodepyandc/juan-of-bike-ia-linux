// ---------------------------------------------------------------------------
// codeDesignDirectiveBlocks — static premium design directive blocks.
// Extracted from codeDesignDirectives so the public facade keeps one job:
// detect the archetype and compose the final block.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'
import type { DesignArchetype } from './codeDesignDirectives.ts'
import {
  dataDenseEnterpriseBlock,
  ideCodeEditorBlock,
  osShellBlock,
} from './codeDesignSpecializedBlocks.ts'
import { CODE_REACT_THREE_COMPATIBILITY } from './codeRuntimeDependencies.ts'
import { CODE_DESIGN_CDN_LIBS as CDN_LIBS } from './codeDesignDirectiveLibraries.ts'
import { marketingArchetypeBlock } from './codeDesignMarketingArchetypes.ts'

// ---------------------------------------------------------------------------
// Inspirations and CDN library hints — surfaced to the model so it knows what
// world-class output looks like and which libraries to wire in.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Common premium baseline — applied on top of every visual archetype.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Archetype-specific blocks
// ---------------------------------------------------------------------------

function scroll3DJourneyBlock(): string[] {
  return [
    '## ARCHETYPE: SCROLL 3D JOURNEY — experience cinematique pinned (style Apple, Igloo Inc, Active Theory)',
    '',
    '### Principe',
    '- Une scene three.js en plein ecran (canvas absolute z-1) qui reagit au scroll: la camera, les positions, les rotations, les materiaux changent au fil de la timeline.',
    '- Le scroll de la page est REELLEMENT PINNE: la scene reste fixe pendant 5-7 chapitres, et chaque chapitre a son timing dans la timeline (0-15%, 15-35%, 35-55%, etc.).',
    '- Chaque chapitre ajoute des overlays HTML (titre, sous-titre, CTA) qui apparaissent et disparaissent au bon moment.',
    '',
    '### Implementation',
    `- Three.js: ${CDN_LIBS.three}.`,
    `- GSAP + ScrollTrigger (PINNED + scrub): ${CDN_LIBS.gsap}, ${CDN_LIBS.scrollTrigger}.`,
    `- Lenis pour smooth scroll: ${CDN_LIBS.lenis}.`,
    '- Structure HTML: section pin avec hauteur calculee (ex: 600vh), canvas fixed inside, et 5-7 .chapter overlays absolutely positioned by GSAP.',
    '- Eclairage PBR: HemisphereLight + DirectionalLight, MeshStandardMaterial / MeshPhysicalMaterial avec roughness/metalness/clearcoat.',
    '- Camera animee (position + lookAt) via tween scroll progress.',
    '- Geometrie principale: composer des primitives ou un .glb minimaliste fait main (sphere + box + lathe + extrude).',
    '- Postprocessing optionnel: Bloom + Vignette + ChromaticAberration via EffectComposer.',
    '',
    '### Garde-fous',
    '- Garder un mode degraded mobile: si window.innerWidth < 720, replier en mode statique (fond + sections classiques) plutot que faire ramer.',
    '- prefers-reduced-motion: desactiver scroll scrub.',
    '- Chargement: afficher un loader simple (logo SVG centre + barre progress) tant que three.js + textures pas pretes.',
  ]
}

function micrositeEventBlock(): string[] {
  return [
    '## ARCHETYPE: MICROSITE EVENT — landing evenement / festival / conference',
    '',
    '### Sections obligatoires',
    '1. Hero immersif: titre evenement tres grand, dates et lieu, CTA "Buy ticket" / "Register", visuel/affiche.',
    '2. Countdown live (jours / heures / minutes / secondes) avec ticking animation.',
    '3. Section "Lineup / Speakers" — grille de cartes (photo, nom, role, social).',
    '4. Section "Schedule / Agenda" — timeline jours (tabs Day 1 / Day 2 / Day 3) avec liste sessions horaire+titre+intervenant.',
    '5. Section "Venue" — carte interactive (Leaflet OSM optionnel ou SVG schematique), adresse, transport.',
    '6. Section "Sponsors" — grille logos.',
    '7. Section "FAQ" — accordeon.',
    '8. CTA final ticket + footer.',
    '',
    '### Effets',
    '- Countdown anime (recalcul chaque seconde, transitions sur les chiffres flip).',
    '- Tab schedule avec slider pile sur le tab actif (translateX selon index).',
    '- Cards lineup hover scale + reveal social icons.',
    '- Background hero avec mesh gradient ou particules soft.',
  ]
}

function brutalistBlock(): string[] {
  return [
    '## ARCHETYPE: MINIMAL BRUTALIST — typographie raw, palette monochrome, no-bullshit',
    '',
    '### Direction artistique',
    '- Typo display imposante (clamp(4rem, 14vw, 14rem)) en sans-serif geometrique (Helvetica, Neue Haas Grotesk, Inter Tight).',
    '- Palette: noir sur blanc OU blanc sur noir, avec UN accent rouge electrique #ff0000 ou jaune fluo #fff200.',
    '- Aucun radius sauf sur des elements specifiques. Aucun shadow. Aucun gradient.',
    '- Bordures franches 1-2px solid black/white.',
    '- Grid layout strict avec colonnes visibles (grid-template-columns repeat(12, 1fr) + gutters).',
    '',
    '### Effets autorises',
    '- Hover: invert couleurs ou fond change.',
    '- Marquee de texte (band horizontal qui defile).',
    '- Cursor underscore qui clignote sur certains elements.',
    '- Effet "glitch" tres ponctuel (translateX random + clip-path).',
    '',
    '### Anti-patterns interdits dans cet archetype',
    '- Pas de mesh gradient.',
    '- Pas de glassmorphism.',
    '- Pas de neumorphism.',
    '- Pas de pastels.',
    '- Pas de border-radius generique partout.',
  ]
}

function mobileNativePremiumBlock(intent: CodeIntent): string[] {
  const isFlutter = intent.projectType === 'mobile_flutter'
  return [
    `## ARCHETYPE: MOBILE NATIVE PREMIUM (${isFlutter ? 'Flutter' : 'React Native + Expo'})`,
    '',
    '### Visual quality',
    '- Theme dark + light avec switch persistant (AsyncStorage / SharedPreferences).',
    '- Typo: Inter / SF Pro / Plus Jakarta Sans. Echelle 12/14/16/20/28/40.',
    '- Palette systeme + accent unique vibrant.',
    '- Spacing 4/8/12/16/20/24/32.',
    '- Header avec blur (BlurView ou ImageFilter.blur Flutter).',
    '- Cards radius 16-20, ombre soft, padding genereux.',
    '',
    '### Interactions natives',
    '- Bottom sheet (gorhom/react-native-bottom-sheet OU showModalBottomSheet Flutter) pour les actions secondaires.',
    '- Swipe gestures (Gesture Handler / GestureDetector).',
    '- Haptic feedback sur les actions importantes (Haptics.impactAsync ou HapticFeedback.lightImpact).',
    '- Skeletons sur loading (Animated linear gradient).',
    '- Pull-to-refresh natif.',
    '- Tab bar bottom avec icones Lucide ou material symbols.',
    '',
    '### Pages obligatoires',
    '1. Splash screen (logo + spinner ou animation lottie).',
    '2. Onboarding 3 ecrans (carousel paginee).',
    '3. Home avec hero + sections.',
    '4. Detail page accessible par push.',
    '5. Profil / settings avec switch dark/light, language, notifications, sign out.',
    '',
    '### Production',
    isFlutter
      ? '- pubspec.yaml avec flutter, cupertino_icons, http, shared_preferences, google_fonts.'
      : '- package.json avec expo, react-native, react-navigation, expo-linear-gradient, lucide-react-native, react-native-reanimated.',
    '- README avec commandes lancement (expo start ou flutter run).',
  ]
}

function desktopAppBlock(intent: CodeIntent): string[] {
  const isTauri = intent.projectType === 'desktop_tauri'
  return [
    `## ARCHETYPE: DESKTOP APP (${isTauri ? 'Tauri' : 'Electron'})`,
    '',
    '### Visual quality',
    '- Title bar custom (cacher la title bar OS, dessiner une nous-meme avec drag region).',
    '- Sidebar gauche avec navigation, avatar/profile en bas.',
    '- Main panel scrollable. Optionnel: panel droite repliable (split-pane).',
    '- Theme follow systeme + override manuel.',
    '- Iconographie Lucide / Phosphor.',
    '',
    '### Patterns recommandes',
    '- Command palette cmd+k avec recherche actions.',
    '- Toast notifications discretes en bas a droite.',
    '- Settings page avec sections (General, Apparence, Raccourcis, A propos).',
    '- Onboarding au premier lancement.',
    '- Persistence d etat (Zustand + persist OU localStorage si frontend pur).',
    '',
    '### Tech stack',
    isTauri
      ? '- Frontend: Vite + React + TypeScript + Tailwind ou CSS module premium.\n- Backend: Tauri Rust pour acces fichier et commands IPC.'
      : '- Frontend Electron renderer + main process (electron 28+) + preload.',
  ]
}

function gamePremiumBlock(): string[] {
  return [
    '## ARCHETYPE: GAME WEB PREMIUM — visual juice maximum',
    '',
    '### Visual & juice obligatoire',
    '- Palette neon ou cinematique (cyber, retrowave, cyberpunk, vapor) avec un fond tres sombre.',
    '- Particules sur chaque action significative (explosion, score, dash, mort).',
    '- Screen shake (translation 2-6px aleatoire 80-150ms) sur impacts.',
    '- Trainees / motion blur sur projectiles ou personnages rapides.',
    '- Camera offset leger qui suit le joueur (smoothing 0.08).',
    '- Sons synthetises Web Audio (oscillator, noise, envelope ADSR) pour shoot/score/death/jump.',
    '- HUD propre: score top-left grand, vies/HP top-right en pictos, level center top.',
    '- Animations easing sur menus (ease-out spring).',
    '- Game over screen anime (flash + pulse texte score + bouton Rejouer).',
    '',
    '### Implementation',
    '- requestAnimationFrame avec delta time.',
    '- Boucle propre: input -> update -> draw, jamais setInterval.',
    '- localStorage best score.',
    '- Responsive canvas (resize listener) avec viewport scale uniforme.',
    '- prefers-reduced-motion: reduire screen shake et particules.',
  ]
}

function defaultPremiumBlock(): string[] {
  return [
    '## ARCHETYPE: DEFAULT PREMIUM — produit visuel polished generique',
    '',
    'Aucun archetype precis n a ete identifie. Tu produis un site/page premium standard avec:',
    '- Nav fixed blur + logo SVG.',
    '- Hero plein ecran avec mesh gradient + headline imposante + CTA + visuel.',
    '- 3-4 sections riches (features, showcase, numbers, testimonials).',
    '- CTA final + footer 4 colonnes.',
    '- Tous les effets baseline (scroll reveal, hover cards, counter, parallax leger).',
  ]
}

// ---------------------------------------------------------------------------
// Building block — assemble final directives
// ---------------------------------------------------------------------------

export function archetypeBlock(archetype: DesignArchetype, intent: CodeIntent): string[] {
  const marketingBlock = marketingArchetypeBlock(archetype, intent)
  if (marketingBlock) return marketingBlock

  switch (archetype) {
    case 'scroll_3d_journey': return scroll3DJourneyBlock()
    case 'microsite_event': return micrositeEventBlock()
    case 'minimal_brutalist': return brutalistBlock()
    case 'mobile_native_premium': return mobileNativePremiumBlock(intent)
    case 'desktop_native_app': return desktopAppBlock(intent)
    case 'game_visual_premium': return gamePremiumBlock()
    case 'data_dense_enterprise': return dataDenseEnterpriseBlock()
    case 'ide_code_editor': return ideCodeEditorBlock()
    case 'os_shell': return osShellBlock()
    default: return defaultPremiumBlock()
  }
}

export function depthDirectivesBlock(intent: CodeIntent): string[] {
  // Always-on depth/3D suggestions for visual web projects
  const wants3D = intent.assetPlan?.wants3D || intent.features.includes('3d')
  if (!wants3D && intent.projectType !== 'static_web' && !intent.projectType.startsWith('spa_') && !intent.projectType.startsWith('ssr_')) {
    return []
  }

  const lines = [
    '## PROFONDEUR ET 3D — toujours preferer la profondeur a la platitude',
    '- Aucun ecran ne doit etre 100% plat. Si la stack est web, ajoute au moins UN effet de profondeur:',
    '  1. Parallax sur 2-3 couches (translate3d en fonction du scroll).',
    '  2. Mesh gradient avec blobs blur en arriere-plan.',
    '  3. Layered z-index (cards qui se chevauchent legerement avec ombres composites).',
    '  4. Mini scene three.js (canvas inline) pour le hero ou une section dediee.',
    '- Si la stack permet WebGL et que le sujet le justifie, prefere une mini scene 3D meme courte (cube anime, sphere materielle, scrolling planet) plutot que des photos statiques.',
  ]

  if (wants3D) {
    lines.push(
      '',
      '### Three.js — implementation premium obligatoire (puisque 3D demande)',
      `- Importer via CDN module: ${CDN_LIBS.three}.`,
      `- OrbitControls si manipulation utilisateur: ${CDN_LIBS.threeOrbit}.`,
      `- GLTFLoader si modele externe: ${CDN_LIBS.threeGLTF}.`,
      '- Renderer: { antialias: true, alpha: true, powerPreference: "high-performance" }, shadowMap.enabled = true.',
      '- Camera PerspectiveCamera(45-60, aspect, 0.1, 1000) bien positionnee, jamais 0,0,0.',
      '- Lighting: HemisphereLight + DirectionalLight castShadow + (optionnel) PointLight colore.',
      '- Materials: MeshStandardMaterial avec metalness/roughness + envMap (PMREMGenerator) si possible.',
      '- Composition: minimum 1 mesh principal anime (rotation + flottement Math.sin(t)).',
      '- Postprocessing optionnel: Bloom, FXAA, ChromaticAberration via EffectComposer.',
      '- Cleanup: dispose() des geometries/materials/textures, cancelAnimationFrame au demontage, resize listener.',
      '- Performance: pixelRatio min(2, devicePixelRatio), pause scene si tab cache (visibilitychange).',
    )
  }

  return lines
}

export function autoDepsBlock(): string[] {
  // Les URL sont donnees TELLES QUELLES parce que le modele en invente sinon.
  // Cas reel: il a ecrit `lenis@1.0.48/dist/lenis.min.js` — un 404 — puis
  // appele `new Lenis(...)`, donc la page cassait au chargement avec
  // `Lenis is not defined`. Le bloc nommait la librairie sans jamais donner son
  // adresse: nommer ne suffit pas, il faut fournir.
  return [
    '## DEPENDANCES — URL EXACTES, AUCUNE INVENTION',
    '',
    'INTERDIT d inventer une URL de CDN. Si tu utilises une de ces librairies, copie l URL EXACTEMENT telle qu ecrite ici (elles sont verifiees et pointent sur une plage de version majeure stable):',
    `- Three.js (module ESM): ${CDN_LIBS.three}`,
    `- OrbitControls: ${CDN_LIBS.threeOrbit}`,
    `- GLTFLoader: ${CDN_LIBS.threeGLTF}`,
    `- GSAP: ${CDN_LIBS.gsap}`,
    `- ScrollTrigger: ${CDN_LIBS.scrollTrigger}`,
    `- Lenis (scroll fluide): ${CDN_LIBS.lenis}`,
    `- SplitType: ${CDN_LIBS.splitText}`,
    `- Lottie: ${CDN_LIBS.lottie}`,
    `- Chart.js: ${CDN_LIBS.chartjs}`,
    `- D3: ${CDN_LIBS.d3}`,
    `- Motion One: ${CDN_LIBS.motionone}`,
    '',
    'REGLE DURE: tout identifiant global que tu appelles (`new Lenis`, `gsap`, `THREE`, `Chart`) DOIT avoir sa balise <script> correspondante dans le <head>, prise dans la liste ci-dessus. Si la librairie n est pas dans cette liste, NE L UTILISE PAS: ecris l effet en CSS/JS natif.',
    'Une page qui reference une librairie non chargee casse au premier rendu — c est un echec de livraison, pas un detail.',
    `- Pour SPA bundler: resous les versions stables via le registre. Matrice 3D testee par le viewer: ${CODE_REACT_THREE_COMPATIBILITY}.`,
    '- Si une lib est lourde et qu une alternative CSS pure existe, prefere la version CSS (transition + @keyframes) pour un loading instantane.',
  ]
}

/**
 * Contrat typographique MESURABLE, aligne sur le juge de rendu.
 *
 * Le juge verifie sur le rendu reel: >= 40 px pour la typo d affichage et >= 4
 * tailles distinctes. La directive doit donc exiger la meme chose en clair,
 * sinon on note un seuil qu on n a jamais demande.
 */
export function typographyContractBlock(): string[] {
  return [
    '## TYPOGRAPHIE — SEUILS VERIFIES SUR LE RENDU',
    '- Le titre principal (hero h1) DOIT etre rendu a 48 px MINIMUM en desktop. Utilise `font-size: clamp(48px, 7vw, 96px)`. Un hero dont le plus gros texte fait 18 px est un ECHEC mesure, pas une question de gout.',
    '- Au moins QUATRE tailles de police distinctes doivent exister dans la page (echelle 12/14/16/20/28/40/56/72/96).',
    '- La police choisie doit REELLEMENT charger: ajoute la balise `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=...&display=swap">` dans le <head>. Un `font-family` declare sans chargement retombe sur Georgia/Helvetica — exactement le rendu par defaut interdit.',
    '- Ne compte JAMAIS sur les tailles par defaut du navigateur: un framework CSS peut les reinitialiser. Declare explicitement la taille de chaque niveau de titre.',
    '',
    '## ICONOGRAPHIE — AUCUN EMOJI',
    '- Les icones de fonctionnalites, de services ou de navigation sont des SVG INLINE, jamais des emoji. Un emoji en guise d icone est la signature d un prototype et sera rejete.',
    '- Les SVG partagent la meme grille (24x24), la meme epaisseur de trait (1.5-2), le meme style (outline OU solid, pas les deux melanges) et heritent de `currentColor`.',
    '',
    '## COMPOSITION — CE QUI SE VOIT A L ECRAN',
    '- AUCUN chevauchement: deux elements ne doivent jamais se superposer. Utilise `display:flex` avec `gap` plutot qu un positionnement absolu qui sort du flux.',
    '- AUCUNE grande section quasi vide: si une section fait plus de 400px de haut, elle doit etre REMPLIE (visuel, accroche, indicateurs, CTA). Un `min-height:100vh` sur deux lignes de texte produit un vide blanc.',
  ]
}
