// ---------------------------------------------------------------------------
// Code Intent Classification — deterministic project type routing
// Equivalent of threeDIntent.ts for the code module
// ---------------------------------------------------------------------------

export type CodeProjectType =
  | 'static_web'
  | 'spa_react'
  | 'spa_vue'
  | 'spa_angular'
  | 'spa_svelte'
  | 'ssr_nextjs'
  | 'ssr_nuxt'
  | 'ssr_remix'
  | 'api_express'
  | 'api_fastapi'
  | 'api_django'
  | 'api_flask'
  | 'api_spring'
  | 'api_gin'
  | 'api_actix'
  | 'api_dotnet'
  | 'fullstack_mern'
  | 'fullstack_nextjs'
  | 'fullstack_django'
  | 'fullstack_rails'
  | 'cli_node'
  | 'cli_python'
  | 'cli_rust'
  | 'cli_go'
  | 'cli_cpp'
  | 'desktop_electron'
  | 'desktop_tauri'
  | 'mobile_rn'
  | 'mobile_flutter'
  | 'library_npm'
  | 'library_pypi'
  | 'library_crate'
  | 'game_web'
  | 'game_unity'
  | 'system_c'
  | 'system_cpp'
  | 'system_rust'
  | 'data_python'
  | 'devops_docker'
  | 'script'
  | 'unknown'

export type CodeComplexity = 'trivial' | 'simple' | 'moderate' | 'complex' | 'enterprise'

export type PreviewType =
  | 'dev_server'
  | 'iframe_bundled'
  | 'iframe_static'
  | 'console'
  | 'none'

/** How to approach game generation. */
export type GameKind =
  | 'clone'     // Recreate a known game exactly (snake, tetris, flappy, etc.)
  | 'creative'  // Invent something original — no canonical reference
  | 'generic'   // Generic game request without enough detail to classify

/** A known game to clone, with its mechanics spelled out. */
export type KnownGameEntry = {
  canonical: string
  genre: string
  coreMechanics: string[]
  visualStyle: string
  controls: string
  winLoseCondition: string
}

export type CodeIntent = {
  projectType: CodeProjectType
  complexity: CodeComplexity
  languages: string[]
  frameworks: string[]
  features: string[]
  needsDevServer: boolean
  needsBundling: boolean
  previewType: PreviewType
  devCommand: string | null
  buildCommand: string | null
  testCommand: string | null
  /** Which model tier to use: 'code' for pure coding, 'planning' for architecture, 'analysis' for review */
  primaryModelRole: 'code' | 'planning' | 'analysis'
  /** Whether multi-file architecture planning is needed before generation */
  needsArchitecturePlanning: boolean
  /** Estimated file count for progress tracking */
  estimatedFileCount: number
  /** Rich analysis of the user brief to enrich the system prompt before generation. */
  assetPlan: CodeAssetPlan
  /** Game-specific classification — only set when projectType === 'game_web'. */
  gameKind?: GameKind
  /** The known game to clone — only set when gameKind === 'clone'. */
  knownGame?: KnownGameEntry
}

/**
 * Plan of what the user wants beyond "just code":
 *  - visual style clues ("moderne", "premium", "cyberpunk"…) → trigger web research
 *  - concrete objects / subjects to show ("velo gravel", "iphone 15", "chat siamois"…) → need image/3D assets
 *  - effects / animations asked ("parallax", "glow", "gsap", "three.js stars"…) → widen library hints
 *  - if paletteHints is set, the codeur will be told to reuse those colors precisely.
 */
export type CodeAssetPlan = {
  /** Free-form style tokens kept as-is (for search queries and prompt hints). */
  styleHints: string[]
  /** Physical/digital objects or subjects mentioned that probably need a visual. */
  objectMentions: string[]
  /** Interactive / animation / effect tokens the page should feature. */
  effectMentions: string[]
  /** Color hex codes captured in the brief, if any ("#ff8800" etc.) */
  paletteHints: string[]
  /** User asked for a "pro / premium / attirant / moderne / …" rendering — research recommended. */
  wantsPremiumLook: boolean
  /** User implicitly or explicitly asked for illustrations (image / photo / picture / illustration / icon). */
  wantsImages: boolean
  /** User asked for 3D content (three.js, webgl, rotating model, …). */
  wants3D: boolean
  /** User expressly asked to research / source references online ("cherche", "trouve", "inspire-toi de", …). */
  wantsResearch: boolean
  /** Short research queries to feed `researchBestPractices` / image search BEFORE generation. */
  researchQueries: string[]
  /** Main subject of the page (brand, product, or noun). NEVER mistranslate this. */
  subject: SubjectDetection
  /** Language the user wrote the prompt in. All UI copy must be generated in this language. */
  language: PromptLanguage
}

// ---------------------------------------------------------------------------
// Keyword detection tables
// ---------------------------------------------------------------------------

const FRAMEWORK_SIGNALS: Record<string, { projectType: CodeProjectType; frameworks: string[]; languages: string[] }> = {
  // Frontend SPA
  'react': { projectType: 'spa_react', frameworks: ['react'], languages: ['typescript', 'javascript'] },
  'vue': { projectType: 'spa_vue', frameworks: ['vue'], languages: ['typescript', 'javascript'] },
  'angular': { projectType: 'spa_angular', frameworks: ['angular'], languages: ['typescript'] },
  'svelte': { projectType: 'spa_svelte', frameworks: ['svelte'], languages: ['typescript', 'javascript'] },
  'sveltekit': { projectType: 'spa_svelte', frameworks: ['sveltekit'], languages: ['typescript'] },
  // SSR/Fullstack
  'next': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'next.js': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'nextjs': { projectType: 'ssr_nextjs', frameworks: ['nextjs'], languages: ['typescript'] },
  'nuxt': { projectType: 'ssr_nuxt', frameworks: ['nuxt'], languages: ['typescript'] },
  'remix': { projectType: 'ssr_remix', frameworks: ['remix'], languages: ['typescript'] },
  // Backend API
  'express': { projectType: 'api_express', frameworks: ['express'], languages: ['typescript', 'javascript'] },
  'fastapi': { projectType: 'api_fastapi', frameworks: ['fastapi'], languages: ['python'] },
  'django': { projectType: 'api_django', frameworks: ['django'], languages: ['python'] },
  'flask': { projectType: 'api_flask', frameworks: ['flask'], languages: ['python'] },
  'spring': { projectType: 'api_spring', frameworks: ['spring-boot'], languages: ['java'] },
  'spring boot': { projectType: 'api_spring', frameworks: ['spring-boot'], languages: ['java'] },
  'gin': { projectType: 'api_gin', frameworks: ['gin'], languages: ['go'] },
  'actix': { projectType: 'api_actix', frameworks: ['actix-web'], languages: ['rust'] },
  'rails': { projectType: 'fullstack_rails', frameworks: ['rails'], languages: ['ruby'] },
  'ruby on rails': { projectType: 'fullstack_rails', frameworks: ['rails'], languages: ['ruby'] },
  '.net': { projectType: 'api_dotnet', frameworks: ['.net'], languages: ['csharp'] },
  'asp.net': { projectType: 'api_dotnet', frameworks: ['asp.net'], languages: ['csharp'] },
  // Mobile
  'react native': { projectType: 'mobile_rn', frameworks: ['react-native'], languages: ['typescript'] },
  'flutter': { projectType: 'mobile_flutter', frameworks: ['flutter'], languages: ['dart'] },
  // Desktop
  'electron': { projectType: 'desktop_electron', frameworks: ['electron'], languages: ['typescript'] },
  'tauri': { projectType: 'desktop_tauri', frameworks: ['tauri'], languages: ['typescript', 'rust'] },
  // Data/ML
  'pandas': { projectType: 'data_python', frameworks: ['pandas'], languages: ['python'] },
  'numpy': { projectType: 'data_python', frameworks: ['numpy'], languages: ['python'] },
  'tensorflow': { projectType: 'data_python', frameworks: ['tensorflow'], languages: ['python'] },
  'pytorch': { projectType: 'data_python', frameworks: ['pytorch'], languages: ['python'] },
  'scikit': { projectType: 'data_python', frameworks: ['scikit-learn'], languages: ['python'] },
  'jupyter': { projectType: 'data_python', frameworks: ['jupyter'], languages: ['python'] },
  // Game
  'canvas': { projectType: 'game_web', frameworks: ['canvas'], languages: ['javascript'] },
  'webgl': { projectType: 'game_web', frameworks: ['webgl'], languages: ['javascript'] },
  'three.js': { projectType: 'game_web', frameworks: ['three.js'], languages: ['javascript'] },
  'phaser': { projectType: 'game_web', frameworks: ['phaser'], languages: ['javascript'] },
  'pixi': { projectType: 'game_web', frameworks: ['pixijs'], languages: ['javascript'] },
  'unity': { projectType: 'game_unity', frameworks: ['unity'], languages: ['csharp'] },
  // DevOps
  'docker': { projectType: 'devops_docker', frameworks: ['docker'], languages: ['yaml'] },
  'kubernetes': { projectType: 'devops_docker', frameworks: ['kubernetes'], languages: ['yaml'] },
}

const LANGUAGE_SIGNALS: Record<string, { projectType: CodeProjectType; languages: string[] }> = {
  'python': { projectType: 'cli_python', languages: ['python'] },
  'rust': { projectType: 'system_rust', languages: ['rust'] },
  'cargo': { projectType: 'system_rust', languages: ['rust'] },
  'go': { projectType: 'cli_go', languages: ['go'] },
  'golang': { projectType: 'cli_go', languages: ['go'] },
  'java': { projectType: 'api_spring', languages: ['java'] },
  'kotlin': { projectType: 'api_spring', languages: ['kotlin'] },
  'c++': { projectType: 'system_cpp', languages: ['cpp'] },
  'cpp': { projectType: 'system_cpp', languages: ['cpp'] },
  'c language': { projectType: 'system_c', languages: ['c'] },
  'typescript': { projectType: 'cli_node', languages: ['typescript'] },
  'javascript': { projectType: 'cli_node', languages: ['javascript'] },
  'node': { projectType: 'cli_node', languages: ['javascript'] },
  'nodejs': { projectType: 'cli_node', languages: ['javascript'] },
  'bash': { projectType: 'script', languages: ['bash'] },
  'shell': { projectType: 'script', languages: ['bash'] },
  'powershell': { projectType: 'script', languages: ['powershell'] },
  'sql': { projectType: 'script', languages: ['sql'] },
  'php': { projectType: 'script', languages: ['php'] },
  'ruby': { projectType: 'script', languages: ['ruby'] },
  'dart': { projectType: 'cli_node', languages: ['dart'] },
  'swift': { projectType: 'script', languages: ['swift'] },
  'zig': { projectType: 'system_c', languages: ['zig'] },
  'lua': { projectType: 'script', languages: ['lua'] },
  'r': { projectType: 'data_python', languages: ['r'] },
  'scala': { projectType: 'cli_node', languages: ['scala'] },
  'elixir': { projectType: 'script', languages: ['elixir'] },
  'haskell': { projectType: 'script', languages: ['haskell'] },
}

const FULLSTACK_SIGNALS = new Set([
  'fullstack', 'full-stack', 'full stack',
  'mern', 'mean', 'pern', 'lamp',
  'frontend et backend', 'front et back',
  'front-end et back-end',
])

const WEB_SIGNALS = new Set([
  'site web', 'website', 'page web', 'webpage',
  'landing page', 'portfolio', 'blog',
  'html', 'css', 'web page',
  'site internet', 'page internet',
])

const MOBILE_SIGNALS = new Set([
  'mobile', 'android', 'ios', 'iphone', 'ipad',
  'react native', 'flutter',
])

const DESKTOP_SIGNALS = new Set([
  'application de bureau', 'app de bureau', 'desktop app', 'application desktop',
  'application windows', 'app windows', 'windows app', 'application pc',
  'native app', 'application native', 'client lourd',
  'offline app', 'application locale', 'local app',
  'tauri', 'electron', 'winui', 'win32', 'gtk', 'qt',
])

const API_SIGNALS = new Set([
  'api', 'rest', 'restful', 'graphql',
  'crud', 'endpoint', 'microservice',
  'backend', 'back-end', 'serveur',
  'jwt', 'auth', 'authentication',
  'websocket', 'grpc',
])

const MULTIPAGE_SIGNALS = new Set([
  'multipage', 'multi-page', 'multi page',
  'dashboard', 'admin', 'e-commerce', 'ecommerce',
  'plateforme', 'platform', 'portail', 'portal',
  'application web', 'web app', 'webapp',
  'saas', 'crm', 'erp', 'cms',
  'routing', 'router', 'navigation',
  'pages', 'tableau de bord',
])

// ---------------------------------------------------------------------------
// Game detection signals (FR + EN) — triggers game_web project type
// ---------------------------------------------------------------------------
const GAME_SIGNALS = new Set([
  // FR — generic
  'jeu', 'jeux', 'jeu video', 'jeu vidéo', 'mini jeu', 'mini-jeu',
  'jeu de tir', 'jeu de plateforme', 'jeu de course', 'jeu de strategie',
  'jeu de cartes', 'jeu de des', 'jeu de role', 'jeu de puzzle',
  'jeu d aventure', 'jeu d action', 'jeu de reflexion',
  'jeu 2d', 'jeu 3d', 'jeu canvas', 'jeu browser', 'jeu navigateur',
  'jouable', 'gameplay', 'score', 'vie', 'vies', 'niveau', 'niveaux',
  'ennemi', 'ennemis', 'projectile', 'sprite', 'collision',
  'platformer', 'shooter', 'infinite runner', 'endless runner',
  'flappy', 'snake', 'tetris', 'pong', 'breakout', 'asteroids', 'pac',
  'tower defense', 'match 3', 'match-3',
  // EN — generic
  'game', 'games', 'video game', 'mini game', 'mini-game', 'browser game',
  'game loop', 'game engine', 'playable', 'player', 'enemies', 'enemy',
  'health bar', 'game over', 'high score', 'leaderboard',
  '2d game', '3d game', 'canvas game', 'arcade', 'pixel art game',
])

// ---------------------------------------------------------------------------
// 3D app / scene signals (FR + EN) — triggers game_web when no other type found
// ---------------------------------------------------------------------------
const THREED_APP_SIGNALS = new Set([
  // FR
  'application 3d', 'app 3d', 'scene 3d', 'scène 3d', 'visualisation 3d',
  'modele 3d', 'viewer 3d', 'visionneuse 3d', 'objet 3d',
  'animation 3d', 'rendu 3d', 'environnement 3d', 'monde 3d',
  'rotation 3d', 'orbit', 'camera 3d',
  // EN
  '3d app', '3d application', '3d scene', '3d model viewer', '3d viewer',
  '3d visualization', '3d environment', '3d world', '3d animation',
  'three.js', 'threejs', 'webgl', 'webgpu', 'glb', 'gltf', 'obj model',
  'orbit controls', 'perspective camera', 'point light', 'ambient light',
])

// ---------------------------------------------------------------------------
// Known game dictionary — maps detection tokens → exact mechanics spec
// ---------------------------------------------------------------------------

type KnownGameDef = KnownGameEntry & { tokens: string[] }

const KNOWN_GAMES: KnownGameDef[] = [
  {
    canonical: 'Snake',
    tokens: ['snake', 'serpent', 'jeu du serpent', 'snake game'],
    genre: '2D arcade',
    coreMechanics: [
      'Grille de cellules (20×20 minimum). Le serpent se deplace case par case a intervalle fixe (150-200 ms).',
      'Le joueur controle la direction avec les touches fleches ou WASD. Impossible de faire demi-tour.',
      'Une pomme (ou nourriture) apparait aleatoirement sur une case vide. Quand le serpent la mange, il grandit d une case et le score augmente.',
      'Collision avec les murs ou avec son propre corps = game over.',
      'La vitesse augmente progressivement au fil des points.',
      'Ecran de game over avec score final, meilleur score (localStorage) et bouton Rejouer.',
    ],
    visualStyle: 'Dark background (#1a1a2e), serpent en gradient vert (#00ff88 → #00cc66), pomme rouge neon (#ff3333), grille visible en pointilles subtils, score en haut a gauche.',
    controls: 'Fleches directionnelles ou WASD. Barre espace = pause.',
    winLoseCondition: 'Pas de condition de victoire. Game over sur collision. Score = nombre de pommes mangees.',
  },
  {
    canonical: 'Tetris',
    tokens: ['tetris', 'tetromino', 'jeu de tetris', 'tetris like', 'tetris-like'],
    genre: '2D puzzle',
    coreMechanics: [
      'Plateau 10 colonnes × 20 rangees. Les tetrominoes (I, O, T, S, Z, L, J) apparaissent en haut et tombent.',
      'Le joueur peut deplacer (fleches gauche/droite), faire tourner (fleche haut ou Z) et accelerer la chute (fleche bas ou soft drop). Hard drop avec espace.',
      'Quand une rangee est completement remplie, elle est effacee et toutes les rangees au-dessus descendent d un cran. Score +100 par rangee, bonus x2 pour 2, x4 pour 3, x8 pour 4 rangees (Tetris).',
      'La piece suivante est affichee dans un apercu (Next). Piece ghost transparente montre ou la piece va atterrir.',
      'La vitesse de chute augmente tous les 10 rangees effacees (level up).',
      'Game over quand une piece depasse le haut du plateau.',
    ],
    visualStyle: 'Fond sombre (#0d0d1a), chaque type de tetromino a une couleur vive distincte, grille avec lignes fines, panneau de score et niveau a droite, animation d effacement des lignes (flash blanc).',
    controls: 'Fleches: gauche/droite/bas. Haut ou Z: rotation. Espace: hard drop. C: hold piece (optionnel).',
    winLoseCondition: 'Pas de victoire. Game over quand les pieces atteignent le haut. Score cumule + niveau.',
  },
  {
    canonical: 'Flappy Bird',
    tokens: ['flappy', 'flappy bird', 'flappy bird like', 'oiseau volant', 'oiseau tuyaux', 'pipe bird'],
    genre: '2D endless arcade',
    coreMechanics: [
      'Un personnage (oiseau ou sprite custom) tombe en permanence sous l effet de la gravite.',
      'Le joueur clique (clic souris, touche espace ou tap tactile) pour faire "flap" — appliquer une impulsion vers le haut.',
      'Des paires de tuyaux (obstacles) arrivent de la droite a vitesse constante avec un ecart aleatoire a passer.',
      'Collision avec un tuyau, le sol ou le plafond = game over instantane.',
      'Le score est le nombre de paires de tuyaux passees. Meilleur score sauvegarde.',
      'Ecran de demarrage (clic pour commencer), etat "mort" avec rebond de l oiseau, puis ecran score avec Rejouer.',
    ],
    visualStyle: 'Ciel degrade (bleu clair → blanc), sol animé en defilement, tuyaux verts avec chapeau, oiseau anime (rotation selon la vitesse verticale). Nuit ou theme custom si l utilisateur l a demande.',
    controls: 'Clic gauche / touche espace / tap tactile = flap.',
    winLoseCondition: 'Pas de victoire. Score = tuyaux traverses. Game over sur collision.',
  },
  {
    canonical: 'Pong',
    tokens: ['pong', 'jeu de pong', 'ping pong', 'tennis game', 'bat ball game'],
    genre: '2D arcade',
    coreMechanics: [
      'Deux raquettes (gauche = joueur, droite = IA ou joueur 2) et une balle rebondissante.',
      'Raquette gauche: W/S ou fleches. Raquette droite: fleches ou IJKL. L IA suit la balle avec une legere imprecision.',
      'La balle rebondit sur le haut, le bas et les raquettes. L angle de rebond depend de l endroit de contact sur la raquette.',
      'Quand la balle depasse une raquette, le joueur adverse marque un point. Premiere equipe a 7 (ou 5 ou 11) points gagne.',
      'La vitesse de la balle augmente legerement a chaque rebond.',
      'Effets sonores synthesises (oscillator Web Audio API) sur chaque collision.',
    ],
    visualStyle: 'Fond noir pur, raquettes et balle blanches, ligne centrale en pointilles, scores en haut au centre. Style retro CRT avec legere lueur sur les elements blancs.',
    controls: 'Joueur 1: W/S. Joueur 2 (ou IA): fleches haut/bas.',
    winLoseCondition: '7 points pour gagner. Ecran de victoire avec "Rejouer".',
  },
  {
    canonical: 'Breakout / Arkanoid',
    tokens: ['breakout', 'arkanoid', 'casse-briques', 'casse briques', 'brick breaker', 'brick game', 'brique'],
    genre: '2D arcade',
    coreMechanics: [
      'Grille de briques colorees en haut (5-8 rangees, 10-14 colonnes). Une balle rebondit et une raquette en bas se deplace horizontalement.',
      'Raquette: fleches gauche/droite ou deplacement souris/doigt.',
      'Quand la balle touche une brique, la brique disparait et la balle rebondit. Briques peuvent avoir 1-3 points de vie (couleur differente).',
      'Power-ups tombent aleatoirement depuis les briques: balle triple, raquette large, tir laser, balle fire (traverse les briques).',
      'Si la balle passe en dessous de la raquette, le joueur perd une vie (3 vies). 0 vies = game over.',
      'Niveau complete quand toutes les briques sont detruites. Niveau suivant plus rapide / plus de briques.',
    ],
    visualStyle: 'Fond sombre spatial, briques colorees par rangee (arc-en-ciel ou theme), lueur neon sur la balle, raquette metallique. Particules d explosion sur destruction des briques.',
    controls: 'Raquette: fleches ou souris. Espace: lancer la balle / demarrer.',
    winLoseCondition: 'Victoire: toutes les briques detruites. Defaite: 0 vies. Score = briques * valeur.',
  },
  {
    canonical: 'Pac-Man',
    tokens: ['pacman', 'pac-man', 'pac man', 'labyrinthe pacman', 'fantome labyrinthe'],
    genre: '2D maze arcade',
    coreMechanics: [
      'Labyrinthe fixe vu de dessus. Pac-Man se deplace dans les couloirs (haut/bas/gauche/droite, tournant aux intersections).',
      'Le labyrinthe est rempli de petits points (pac-dots) et 4 grosses pilules energisantes dans les coins.',
      'Quatre fantomes (Blinky rouge, Pinky rose, Inky cyan, Clyde orange) patrouillent avec des IA distinctes (chasseur, embuscade, aleatoire).',
      'Manger une pilule energisante = les fantomes deviennent bleus et comestibles pendant 8 secondes. Manger un fantome = +200 points.',
      'Collision avec un fantome normal = perte d une vie (3 vies). 0 vies = game over.',
      'Toutes les pac-dots mangees = niveau suivant (vitesse et IA des fantomes augmentent).',
    ],
    visualStyle: 'Fond noir, labyrinthe bleu electrique, pac-dots jaune clair, Pac-Man jaune avec animation bouche, fantomes aux couleurs distinctives. Police retro pixelee pour le score.',
    controls: 'Fleches directionnelles ou WASD.',
    winLoseCondition: 'Manger tous les pac-dots pour passer au niveau suivant. 0 vies = game over.',
  },
  {
    canonical: 'Space Invaders',
    tokens: ['space invaders', 'space invader', 'invaders', 'alien shooter', 'alien invaders', 'envahisseurs'],
    genre: '2D shoot em up',
    coreMechanics: [
      'Grille d aliens (5 rangees x 11 colonnes) qui se deplacent lateralement et descendent d un cran quand ils atteignent le bord.',
      'Le joueur pilote un canon en bas (gauche/droite) et tire vers le haut (espace). Un seul projectile a la fois (ou 3 max).',
      'Les aliens tirent aleatoirement vers le bas. 4 boucliers destructibles protegent le joueur (pixels qui s effacent).',
      'Les aliens de la derniere rangee valent 10 pts, rangee du milieu 20 pts, rangee du haut 30 pts. Un OVNI passe en haut pour 50-300 pts.',
      'Si un alien atteint le bas de l ecran ou tue le joueur (3 vies), game over.',
      'A chaque vague, les aliens commencent plus bas et vont plus vite.',
    ],
    visualStyle: 'Fond noir etoile, aliens pixelises (2 frames d animation), canons et boucliers verts, projectiles en tirets jaunes. Son de marche des aliens qui s accelere (oscillator Web Audio).',
    controls: 'Fleches gauche/droite: deplacement. Espace: tir.',
    winLoseCondition: 'Tous les aliens tues = niveau suivant. 0 vies ou alien atteint le bas = game over.',
  },
  {
    canonical: 'Asteroids',
    tokens: ['asteroids', 'asteroide', 'asteroides', 'jeu asteroids', 'vaisseau asteroide'],
    genre: '2D arcade spatial',
    coreMechanics: [
      'Vaisseau triangulaire au centre d un espace infini (wrap des bords). Physique newtonienne: poussee, inertie, rotation.',
      'Controles: fleche gauche/droite = rotation, fleche haut = poussee, espace = tir. Touche S ou E = bouclier temporaire (optionnel).',
      'Asteroides grands se cassent en 2 moyens, les moyens en 2 petits, les petits disparaissent. Grands=20pts, moyens=50pts, petits=100pts.',
      'Des soucoupes volantes apparaissent periodiquement et tirent vers le joueur.',
      'Collision avec un asteroide ou un projectile ennemi = perte d une vie. 3 vies. Invincibilite breve au respawn.',
      'Tous les asteroides elimines = nouveau niveau avec plus d asteroides et plus rapides.',
    ],
    visualStyle: 'Fond noir parseme d etoiles statiques, vecteurs blancs minimalistes pour tous les objets (style wireframe), effets de particules sur explosions, trail de la poussee du vaisseau.',
    controls: 'Fleches gauche/droite: rotation. Haut: poussee. Espace: tir. Shift ou S: bouclier.',
    winLoseCondition: '0 vies = game over. Pas de victoire finale, progression infinie par niveaux.',
  },
  {
    canonical: 'Chrome Dino / Endless Runner',
    tokens: ['dino', 'dinosaure', 'chrome dino', 'endless runner', 'runner infini', 'saut obstacle', 'run game', 'jeu de course infini'],
    genre: '2D endless runner',
    coreMechanics: [
      'Personnage (dinosaure ou custom) court automatiquement de gauche a droite a vitesse croissante.',
      'Le joueur saute (espace ou fleche haut ou clic/tap) pour eviter les obstacles au sol et les obstacles aeriens (accroupi: fleche bas).',
      'Les obstacles (cactus, oiseaux, ennemis) arrivent de la droite de facon aleatoire mais espacee raisonnablement.',
      'Score = distance parcourue (temps * vitesse). La vitesse augmente progressivement. Jalons tous les 100 pts (flash bref).',
      'Collision = game over. Meilleur score sauvegarde. Ecran de game over avec score + HI score + Rejouer.',
      'Background defilant avec parallax (nuages lents, sol rapide). Alternance jour/nuit a certains scores.',
    ],
    visualStyle: 'Style pixel art ou vectoriel minimaliste. Palette de gris/beige ou theme coloré custom. Sols textures, nuages defilants, horizon lointain.',
    controls: 'Espace / fleche haut / clic / tap = saut. Fleche bas = accroupi.',
    winLoseCondition: 'Pas de victoire. Score infini. Game over sur collision.',
  },
  {
    canonical: '2048',
    tokens: ['2048', 'jeu 2048', '2048 like', 'merge tiles', 'fusion de cases', 'fusion tuiles'],
    genre: '2D puzzle',
    coreMechanics: [
      'Grille 4x4. Chaque case peut etre vide ou contenir une tuile numerotee (2, 4, 8, 16... 2048...).',
      'Le joueur glisse toutes les tuiles dans une direction (fleches ou swipe). Les tuiles glissent jusqu au bord ou jusqu a une autre tuile.',
      'Deux tuiles identiques qui se percutent fusionnent en une tuile de valeur double. Une seule fusion par tuile par mouvement.',
      'Apres chaque mouvement, une nouvelle tuile (2 avec 90% de chance, 4 avec 10%) apparait sur une case vide aleatoire.',
      'Score = somme de toutes les fusions. Atteindre 2048 = victoire (mais on peut continuer). Plus de case vide ET aucune fusion possible = game over.',
      'Animation de glissement et de fusion des tuiles (transform/transition CSS).',
    ],
    visualStyle: 'Fond beige clair (#bbada0), tuiles arrondies avec couleur progressive (2=blanc casse, 4=creme, 8=orange, 16=rouge, 32=rouge vif, 64=orange fonce, 128+ = jaune dore vers violet). Chiffres en gras contrastes.',
    controls: 'Fleches directionnelles ou swipe tactile.',
    winLoseCondition: 'Victoire: atteindre la tuile 2048. Defaite: grille pleine sans fusion possible.',
  },
  {
    canonical: 'Minesweeper / Demineur',
    tokens: ['demineur', 'démineur', 'minesweeper', 'mine sweeper', 'jeu de mines', 'champ de mines'],
    genre: '2D logic puzzle',
    coreMechanics: [
      'Grille de cellules cachees (9x9 facile, 16x16 moyen, 30x16 difficile). X mines sont placees aleatoirement au premier clic.',
      'Clic gauche = revele la cellule. Si mine = game over. Sinon affiche le nombre de mines adjacentes (1-8) ou vide (revelee en cascade).',
      'Clic droit = place un drapeau sur une mine presumee. Clic droit encore = point d interrogation. Encore = retire.',
      'Reveler toutes les cellules non-minées = victoire. Compteur de mines restantes = mines totales - drapeaux poses.',
      'Timer demarre au premier clic. Meilleur temps par difficulte sauvegarde.',
      'Clic sur un chiffre avec autant de drapeaux adjacents = auto-revele les cases non-drapeautees (chording).',
    ],
    visualStyle: 'Style Windows XP classique retro OU design moderne plat. Cellules grises/bleues, mines en rouge sur game over, cases revelees en clair, chiffres colores (1=bleu, 2=vert, 3=rouge...).',
    controls: 'Clic gauche: reveler. Clic droit: drapeau. Double-clic: chording.',
    winLoseCondition: 'Victoire: toutes les cases sures revelees. Defaite: mine revelée.',
  },
  {
    canonical: 'Tower Defense',
    tokens: ['tower defense', 'tower defence', 'defense de tour', 'défense de tour', 'td game', 'jeu de defense', 'jeu td'],
    genre: '2D strategy',
    coreMechanics: [
      'Un chemin sinueux sur lequel des vagues d ennemis avancent vers la base. Le joueur place des tours sur les cases adjacentes au chemin.',
      'Differents types de tours: basique (cadence rapide, peu de degats), sniper (lente, fort), zone (eclate), ralentisseur (debuff de vitesse). Chaque tour a un cout en or.',
      'Tuer des ennemis donne de l or. Perdre un ennemi = perte d un point de vie (20 PV de base). 0 PV = game over.',
      'Vagues progressives: ennemis plus resistants, ennemis blindes, ennemis volants, boss toutes les 5 vagues.',
      'Les tours peuvent etre upgradees (2-3 niveaux) pour plus de degats, portee ou cadence.',
      'Entre les vagues, le joueur peut placer de nouvelles tours ou upgrader.',
    ],
    visualStyle: 'Vue de dessus isometrique ou 2D orthogonale. Chemin texture, cases herbe/roche, tours avec modeles distincts, barres de vie sur les ennemis, animations de tirs et explosions.',
    controls: 'Clic gauche: selectionner et placer une tour. Clic droit: menu contextuel. Bouton: lancer la vague.',
    winLoseCondition: 'Victoire: survivre a toutes les vagues. Defaite: 0 points de vie de base.',
  },
  {
    canonical: 'Platformer 2D',
    tokens: ['platformer', 'plateformer', 'jeu de plateforme', 'jeu platformer', 'mario like', 'mario-like', 'saut plateforme', 'platforme 2d'],
    genre: '2D platformer',
    coreMechanics: [
      'Personnage avec physique : gravite, saut (variable selon duree de pression), coyote time (200ms apres le bord), double saut optionnel.',
      'Plateformes fixes, mobiles, qui tombent, glissantes. Ennemis avec patterns simples (patrouille, poursuite).',
      'Pieges (pics, lave, fosses). Collectibles (pieces, etoiles, cles). Portes de sortie de niveau.',
      'Au moins 3 niveaux de difficulte croissante avec checkpoint apres chaque moitie de niveau.',
      'HUD: vies (3), score, niveau, collectibles. Mort = respawn au dernier checkpoint, perte d une vie.',
      'Boss final au niveau 3 avec pattern d attaque previsible mais challengant.',
    ],
    visualStyle: 'Pixel art 16x16 ou 32x32, palette coloree coherente par biome (foret, grotte, chateau), parallax background (3 couches), tileset avec bords arrondis, sprite sheet anime (marche 4 frames, saut, chute, idle).',
    controls: 'WASD ou fleches: deplacement. Espace ou haut: saut (maintenir pour sauter plus haut). Z ou X: attaque/action.',
    winLoseCondition: 'Atteindre la sortie de chaque niveau. Vaincre le boss final = victoire. 0 vies = game over avec écran score.',
  },
]

/**
 * Detect if the user wants to clone a specific known game.
 * Returns the entry if found, null otherwise.
 */
function detectKnownGame(lower: string): KnownGameDef | null {
  for (const entry of KNOWN_GAMES) {
    for (const token of entry.tokens) {
      if (containsSignal(lower, token)) return entry
    }
  }
  return null
}

/**
 * Detect whether the request is a known clone, an open creative game, or generic.
 * Also returns whether it's clearly a game at all.
 */
function classifyGameKind(lower: string, isGameRequest: boolean): {
  gameKind: GameKind
  knownGame: KnownGameDef | null
} {
  if (!isGameRequest) return { gameKind: 'generic', knownGame: null }

  const known = detectKnownGame(lower)
  if (known) return { gameKind: 'clone', knownGame: known }

  // Creative signals: when the user describes their own concept or asks for something original
  const creativeSignals = [
    'original', 'unique', 'invente', 'inventé', 'innovant', 'nouveau concept',
    'de ma propre idée', 'mon idée', 'mon concept', 'de mon invention',
    'creatif', 'créatif', 'creative', 'jamais vu', 'inédit', 'inedit',
    'inspiré de', 'inspire de', 'fusion de', 'melange de', 'mélange de',
    'avec une touche de', 'un genre', 'un jeu ou', 'un jeu qui',
  ]
  const isCreativeRequest = creativeSignals.some((s) => lower.includes(s))
    || lower.split(/\s+/).length > 12 // Long description = likely custom concept

  return { gameKind: isCreativeRequest ? 'creative' : 'generic', knownGame: null }
}

function normalizeSignalText(text: string) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function escapeRegex(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function containsSignal(source: string, signal: string) {
  const normalizedSignal = normalizeSignalText(signal).trim()
  if (!normalizedSignal) return false

  const pattern = escapeRegex(normalizedSignal).replace(/\s+/g, '\\s+')
  return new RegExp(`(^|[^a-z0-9])${pattern}(?=[^a-z0-9]|$)`, 'i').test(source)
}

function containsAnySignal(source: string, signals: Iterable<string>) {
  for (const signal of signals) {
    if (containsSignal(source, signal)) return true
  }
  return false
}

function looksLikeDesktopAppRequest(lower: string) {
  // Signal DESKTOP EXPLICITE (phrases completes comme "application desktop").
  if (containsAnySignal(lower, DESKTOP_SIGNALS)) return true

  // Desktop implicite: un mot "logiciel / programme / application" combine avec
  // un mot "bureau / desktop / windows". Sans cette combinaison, on reste sur webapp.
  const mentionsProgramNoun =
    /\bprogramme\b/i.test(lower)
    || /\blogiciel\b/i.test(lower)
    || /\bapplication\b/i.test(lower)
    || /\bapp\b/i.test(lower)

  const mentionsDesktopNoun =
    /\bbureau\b/i.test(lower)
    || /\bdesktop\b/i.test(lower)
    || /\bwindows\b/i.test(lower)
    || /\bmacos\b/i.test(lower)
    || /\blinux\b/i.test(lower)

  return mentionsProgramNoun && mentionsDesktopNoun
}

function looksLikeMobileAppRequest(lower: string) {
  // Explicit mobile signals always win ("react native", "app android", "ios",
  // "iphone app", "appli mobile"...).
  if (containsAnySignal(lower, MOBILE_SIGNALS)) return true

  // Implicit mobile: "app"/"application" combined with a phone-only word
  // (smartphone, telephone mobile, play store, app store...).
  const mentionsProgramNoun =
    /\bapplication\b/i.test(lower)
    || /\bapp\b/i.test(lower)
    || /\bappli\b/i.test(lower)
    || /\blogiciel\b/i.test(lower)

  const mentionsMobileNoun =
    /\bsmartphone\b/i.test(lower)
    || /\bt[eé]l[eé]phone\b/i.test(lower)
    || /\bphone\b/i.test(lower)
    || /\btactile\b/i.test(lower)
    || /\bplay\s*store\b/i.test(lower)
    || /\bapp\s*store\b/i.test(lower)
    || /\bappstore\b/i.test(lower)
    || /\bplaystore\b/i.test(lower)
    || /\bapk\b/i.test(lower)

  return mentionsProgramNoun && mentionsMobileNoun
}

const COMPLEXITY_SIGNALS: Record<CodeComplexity, string[]> = {
  trivial: ['simple', 'basique', 'hello world', 'exemple', 'example', 'demo', 'test'],
  simple: ['petit', 'small', 'script', 'utilitaire', 'utility', 'helper', 'fonction', 'function'],
  moderate: ['moyen', 'medium', 'composant', 'component', 'module', 'service', 'feature'],
  complex: ['complet', 'complete', 'application', 'app', 'projet', 'project', 'systeme', 'system'],
  enterprise: ['entreprise', 'enterprise', 'production', 'scalable', 'microservices', 'architecture', 'plateforme', 'platform', 'saas', 'large'],
}

// ---------------------------------------------------------------------------
// Preview and dev command routing
// ---------------------------------------------------------------------------

const DEV_SERVER_PROJECTS = new Set<CodeProjectType>([
  'spa_react', 'spa_vue', 'spa_angular', 'spa_svelte',
  'ssr_nextjs', 'ssr_nuxt', 'ssr_remix',
  'fullstack_mern', 'fullstack_nextjs', 'fullstack_django', 'fullstack_rails',
  'api_express', 'api_fastapi', 'api_django', 'api_flask', 'api_spring',
  'api_gin', 'api_actix', 'api_dotnet',
  'desktop_electron', 'desktop_tauri', 'game_web',
])

const BUNDLED_PREVIEW_PROJECTS = new Set<CodeProjectType>([
  'library_npm', 'cli_node',
])

function getDevCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react': return 'npm run dev'
    case 'spa_vue': return 'npm run dev'
    case 'spa_angular': return 'npx ng serve'
    case 'spa_svelte': return 'npm run dev'
    case 'ssr_nextjs': return 'npm run dev'
    case 'ssr_nuxt': return 'npm run dev'
    case 'ssr_remix': return 'npm run dev'
    case 'api_express': return 'npm run dev'
    case 'api_fastapi': return 'uvicorn main:app --reload'
    case 'api_django': return 'python manage.py runserver'
    case 'api_flask': return 'flask run'
    case 'api_spring': return 'mvn spring-boot:run'
    case 'api_gin': return 'go run .'
    case 'api_actix': return 'cargo run'
    case 'api_dotnet': return 'dotnet run'
    case 'fullstack_mern': return 'npm run dev'
    case 'fullstack_nextjs': return 'npm run dev'
    case 'fullstack_django': return 'python manage.py runserver'
    case 'fullstack_rails': return 'rails server'
    case 'desktop_electron': return 'npm run dev'
    case 'desktop_tauri': return 'npm run tauri:dev'
    case 'game_web': return 'npm run dev'
    default: return null
  }
}

function getBuildCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react':
    case 'spa_vue':
    case 'spa_svelte':
    case 'ssr_nextjs':
    case 'ssr_nuxt':
    case 'ssr_remix':
    case 'fullstack_mern':
    case 'fullstack_nextjs':
    case 'library_npm':
    case 'desktop_electron':
    case 'game_web':
      return 'npm run build'
    case 'desktop_tauri':
      return 'npm run tauri:build'
    case 'spa_angular': return 'npx ng build'
    case 'system_rust':
    case 'cli_rust':
    case 'api_actix':
      return 'cargo build'
    case 'cli_go':
    case 'api_gin':
      return 'go build ./...'
    case 'api_spring': return 'mvn compile'
    case 'api_dotnet': return 'dotnet build'
    case 'system_cpp':
    case 'cli_cpp':
      return 'cmake --build build'
    default: return null
  }
}

function getTestCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react':
    case 'spa_vue':
    case 'spa_svelte':
    case 'spa_angular':
    case 'ssr_nextjs':
    case 'ssr_nuxt':
    case 'ssr_remix':
    case 'api_express':
    case 'fullstack_mern':
    case 'fullstack_nextjs':
    case 'library_npm':
    case 'cli_node':
    case 'desktop_electron':
    case 'game_web':
      return 'npm test'
    case 'desktop_tauri':
      return 'cargo test'
    case 'api_fastapi':
    case 'api_django':
    case 'api_flask':
    case 'cli_python':
    case 'data_python':
    case 'library_pypi':
      return 'pytest'
    case 'system_rust':
    case 'cli_rust':
    case 'api_actix':
    case 'library_crate':
      return 'cargo test'
    case 'cli_go':
    case 'api_gin':
      return 'go test ./...'
    case 'api_spring': return 'mvn test'
    case 'api_dotnet': return 'dotnet test'
    default: return null
  }
}

// ---------------------------------------------------------------------------
// Complexity estimation
// ---------------------------------------------------------------------------

function estimateComplexity(prompt: string): CodeComplexity {
  const lower = normalizeSignalText(prompt)
  const wordCount = lower.split(/\s+/).length

  // Check from most complex to least
  for (const keyword of COMPLEXITY_SIGNALS.enterprise) {
    if (containsSignal(lower, keyword)) return 'enterprise'
  }

  // Multipage signals always bump to at least complex
  for (const signal of MULTIPAGE_SIGNALS) {
    if (containsSignal(lower, signal)) return 'complex'
  }

  for (const keyword of COMPLEXITY_SIGNALS.complex) {
    if (containsSignal(lower, keyword)) return 'complex'
  }

  // Word count heuristic
  if (wordCount > 80) return 'complex'
  if (wordCount > 40) return 'moderate'

  for (const keyword of COMPLEXITY_SIGNALS.moderate) {
    if (containsSignal(lower, keyword)) return 'moderate'
  }

  for (const keyword of COMPLEXITY_SIGNALS.simple) {
    if (containsSignal(lower, keyword)) return 'simple'
  }

  for (const keyword of COMPLEXITY_SIGNALS.trivial) {
    if (containsSignal(lower, keyword)) return 'trivial'
  }

  return 'moderate'
}

// ---------------------------------------------------------------------------
// Asset plan — heuristic analysis of the user brief
// ---------------------------------------------------------------------------

const PREMIUM_LOOK_TOKENS = [
  // FR
  'premium', 'haut de gamme', 'haut-de-gamme', 'elegant', 'sophistique', 'luxe', 'luxueux',
  'pro', 'professionnel', 'professionnelle', 'attirant', 'attirante', 'attractif', 'moderne',
  'design moderne', 'tendance', 'epure', 'soigne', 'chic', 'stylee', 'stylé', 'stylise',
  'immersif', 'impressionnant', 'impressionnante', 'travaille', 'fignole', 'wow', 'accrocheur',
  'editorial', 'studio', 'vitrine', 'showroom', 'agence',
  // EN
  'modern', 'clean', 'sleek', 'polished', 'high end', 'high-end', 'stunning', 'beautiful',
  'gorgeous', 'striking', 'award winning', 'award-winning', 'pixel perfect', 'pixel-perfect',
  // Style family
  'cyberpunk', 'minimaliste', 'glassmorphism', 'neumorphism', 'futuriste', 'retro', 'vintage',
  'art deco', 'art nouveau', 'brutaliste', 'brutalist', 'scandinave', 'japandi', 'bauhaus',
  'animation', 'animations', 'animee', 'anime', 'dynamique', 'interactif', 'interactive',
]

const RESEARCH_TRIGGER_TOKENS = [
  'cherche', 'trouve', 'recherche', 'inspire-toi', 'inspires-toi', 'inspire toi', 'reference',
  'references', 'tendance', 'tendances', 'exemples reels', 'vrais exemples', 'comme sur',
  'look and feel', 'mood board', 'moodboard',
  'find', 'search', 'lookup', 'browse', 'inspired by', 'inspire',
]

const IMAGE_TOKENS = [
  'image', 'images', 'photo', 'photos', 'picture', 'pictures', 'illustration', 'illustrations',
  'icone', 'icones', 'icon', 'icons', 'logo', 'logos', 'banner', 'banniere', 'hero image',
  'visuel', 'visuels', 'fond', 'background image', 'thumbnail', 'vignette',
]

const THREED_TOKENS = [
  '3d', 'three.js', 'threejs', 'webgl', '3d model', 'modele 3d', 'rotation 3d', 'orbit control',
  'glb', 'gltf', 'canvas 3d', 'webgpu',
]

const EFFECT_TOKENS = [
  'parallax', 'parallaxe', 'scroll', 'scrolly', 'scrolling', 'reveal', 'fade in', 'fade-in',
  'glow', 'neon', 'neonglow', 'blur', 'flou', 'hover', 'transition', 'transitions',
  'particles', 'particules', 'tilt', 'gradient animated', 'gradient anime',
  'gsap', 'framer', 'framer motion', 'lottie', 'rive',
  'cursor suiveur', 'custom cursor', 'smooth scroll', 'marquee',
  'carousel', 'carrousel', 'slider', 'timeline', 'accordeon', 'accordion',
]

const COLOR_HEX_REGEX = /#[0-9a-f]{3,8}\b/gi

function extractMentions(lower: string, dictionary: string[]): string[] {
  const hits: string[] = []
  for (const token of dictionary) {
    if (containsSignal(lower, token) && !hits.includes(token)) hits.push(token)
  }
  return hits
}

/**
 * Extract object / subject mentions that likely need a visual asset.
 * Heuristic: a small bag of concrete nouns commonly used in web briefs.
 */
const CONCRETE_OBJECT_TOKENS = [
  // Transport
  'velo', 'bike', 'gravel', 'voiture', 'car', 'moto', 'motorcycle', 'camion', 'truck',
  'drone', 'avion', 'plane', 'bateau', 'boat', 'skate', 'skateboard', 'trottinette',
  // Tech product
  'iphone', 'smartphone', 'laptop', 'ordinateur portable', 'macbook', 'casque', 'headphone',
  'speaker', 'enceinte', 'camera', 'appareil photo', 'console', 'manette',
  // Food
  'cafe', 'pizza', 'burger', 'salade', 'sushi', 'cocktail', 'vin',
  // Living
  'chat', 'chien', 'cat', 'dog', 'fleur', 'plante', 'arbre', 'paysage',
  // Space
  'planete', 'lune', 'etoile', 'galaxie', 'ocean',
  // Fashion
  'montre', 'watch', 'sneaker', 'baskets', 'sac', 'bag',
  // Structures
  'maison', 'house', 'villa', 'cabane', 'tower', 'tour', 'pont', 'bridge', 'temple', 'chateau',
]

function extractObjectMentions(prompt: string): string[] {
  const lower = normalizeSignalText(prompt)
  const hits = extractMentions(lower, CONCRETE_OBJECT_TOKENS)
  // Also try 2-3 word phrases between quotes (e.g. "Renault Clio 5").
  const quoted = prompt.match(/["'«»]([^"'«»]{3,40})["'«»]/g) || []
  for (const q of quoted) {
    const clean = q.replace(/["'«»]/g, '').trim()
    if (clean && !hits.includes(clean.toLowerCase())) hits.push(clean)
  }
  return hits.slice(0, 8)
}

function buildResearchQueries(
  prompt: string,
  styleHints: string[],
  objectMentions: string[],
  wantsPremium: boolean,
): string[] {
  const queries: string[] = []
  const head = prompt.trim().split(/\s+/).slice(0, 6).join(' ')

  if (wantsPremium && head) {
    queries.push(`${head} web design 2025 award winning`)
    queries.push(`${head} modern layout inspiration`)
  }
  for (const obj of objectMentions.slice(0, 3)) {
    queries.push(`${obj} hero image`)
    queries.push(`${obj} product photography transparent background`)
  }
  for (const style of styleHints.slice(0, 2)) {
    queries.push(`${style} web design example`)
  }
  return Array.from(new Set(queries.map((q) => q.replace(/\s+/g, ' ').trim()))).filter(Boolean).slice(0, 6)
}

// ---------------------------------------------------------------------------
// Language + subject detection — so the LLM stops drifting off-topic
// ---------------------------------------------------------------------------

export type PromptLanguage = 'fr' | 'en' | 'es' | 'de' | 'it' | 'pt' | 'unknown'

const LANG_SIGNALS: Array<{ lang: PromptLanguage; pattern: RegExp }> = [
  { lang: 'fr', pattern: /\b(le|la|les|un|une|des|pour|avec|mais|plus|aussi|faire|fais|fait|moi|nous|vous|voir|voici|c est|si je|avec un|attirant|sur|dans|page web|site web|voici|qui|pourquoi|comment|parce que|d un|d une)\b/i },
  { lang: 'en', pattern: /\b(the|a|an|and|with|for|please|make|build|create|design|i want|should|could|about|looks|good|awesome|stunning)\b/i },
  { lang: 'es', pattern: /\b(el|la|los|las|una|uno|para|con|pero|hacer|quiero|por favor|pagina|sitio|esto|que|como)\b/i },
  { lang: 'de', pattern: /\b(der|die|das|ein|eine|und|mit|für|bitte|machen|ich möchte|webseite|seite|sollte)\b/i },
  { lang: 'it', pattern: /\b(il|la|lo|gli|le|un|una|per|con|voglio|favore|pagina|sito|fare)\b/i },
  { lang: 'pt', pattern: /\b(o|a|os|as|um|uma|para|com|quero|fazer|favor|pagina|site)\b/i },
]

function detectPromptLanguage(prompt: string): PromptLanguage {
  // Score each language by how many of its signal words appear.
  const scores: Record<PromptLanguage, number> = { fr: 0, en: 0, es: 0, de: 0, it: 0, pt: 0, unknown: 0 }
  for (const { lang, pattern } of LANG_SIGNALS) {
    const matches = prompt.match(new RegExp(pattern.source, 'gi'))
    scores[lang] = matches ? matches.length : 0
  }
  let best: PromptLanguage = 'unknown'
  let bestScore = 1 // require at least 2 hits to claim a language
  for (const lang of ['fr', 'en', 'es', 'de', 'it', 'pt'] as const) {
    if (scores[lang] > bestScore) {
      best = lang
      bestScore = scores[lang]
    }
  }
  return best
}

/**
 * Extract the main subject of the prompt: brand, product, or domain that the page
 * is about. Used to enforce topic fidelity — e.g. "coca" → "coca-cola" and the
 * generated page must be ABOUT coca-cola, not about "culinary excellence".
 *
 * Strategy: well-known brands/products first, then first notable capitalised
 * phrase, then the first concrete noun from CONCRETE_OBJECT_TOKENS.
 *
 * Brand profile: lock subject + palette + assets to prevent semantic drift.
 */
export type BrandProfile = {
  /** Hex (#RRGGBB) of the canonical brand color — injected as primary CSS accent. */
  primaryColor: string
  /** Optional secondary brand color used for gradients / accents. */
  secondaryColor?: string
  /** Tertiary brand color (rare — Pepsi blue/red/white triad, Google G colors). */
  tertiaryColor?: string
  /** Concrete product nouns associated with the brand — feeds image search and Codeur prompt. */
  productKeywords: string[]
  /** Short adjective list describing the visual vibe ("rouge pop retro", "minimal sharp white"). */
  designVibe: string
  /** Recommended typographic style ("bold serif retro", "geometric sans modern", "italic cursive"). */
  typoVibe: string
  /** Image search queries used by the orchestrator to fetch real assets via the bridge / extension. */
  imageQueries: string[]
  /**
   * Geometric primitive for 3D product: can, bottle, phone, shoe, car, watch, bag, headphones, controller, console, card, cup, logo, building, or null.
   */
  productShape?:
    | 'can' | 'bottle' | 'phone' | 'tablet' | 'laptop'
    | 'shoe' | 'car' | 'watch' | 'bag' | 'headphones'
    | 'controller' | 'console' | 'card' | 'cup' | 'logo' | 'building'
    | null
}

const BRAND_DICTIONARY: Array<{ token: RegExp; canonical: string; domain: string; profile: BrandProfile }> = [
  {
    token: /\bcoca([- ]?cola)?\b/i,
    canonical: 'Coca-Cola',
    domain: 'soda / boisson gazeuse',
    profile: {
      primaryColor: '#F40009',
      secondaryColor: '#FFFFFF',
      productKeywords: ['bouteille en verre', 'canette rouge', 'verre avec glacons', 'logo Spencerian script'],
      designVibe: 'rouge eclatant + blanc, vintage americain pop, bulles, condensation, energie joyeuse',
      typoVibe: 'serif scriptural elegant pour le wordmark + sans bold pour le corps',
      imageQueries: ['Coca-Cola bouteille en verre', 'Coca-Cola canette rouge', 'Coca-Cola logo officiel', 'Coca-Cola ambiance vintage'],
      productShape: 'bottle',
    },
  },
  {
    token: /\bpepsi\b/i,
    canonical: 'Pepsi',
    domain: 'soda',
    profile: {
      primaryColor: '#004B93',
      secondaryColor: '#E32934',
      tertiaryColor: '#FFFFFF',
      productKeywords: ['canette bleue', 'bouteille', 'globe Pepsi'],
      designVibe: 'bleu profond + rouge, moderne, confident, dynamique sport-music',
      typoVibe: 'sans bold geometric',
      imageQueries: ['Pepsi can blue', 'Pepsi bottle modern', 'Pepsi logo globe'],
      productShape: 'can',
    },
  },
  {
    token: /\bfanta\b/i,
    canonical: 'Fanta',
    domain: 'soda',
    profile: {
      primaryColor: '#F58220',
      secondaryColor: '#0066B3',
      productKeywords: ['canette orange', 'bouteille fruit', 'eclats fruits'],
      designVibe: 'orange vif + bleu, fun, jeune, fruite, comic',
      typoVibe: 'sans rounded playful',
      imageQueries: ['Fanta orange can', 'Fanta bottle splash', 'Fanta logo orange'],
      productShape: 'can',
    },
  },
  {
    token: /\bsprite\b/i,
    canonical: 'Sprite',
    domain: 'soda',
    profile: {
      primaryColor: '#009639',
      secondaryColor: '#FFEC00',
      productKeywords: ['canette verte transparente', 'citron vert', 'glacons cristal'],
      designVibe: 'vert frais + jaune citron, frais, transparent, glace',
      typoVibe: 'sans condensed bold',
      imageQueries: ['Sprite green can', 'Sprite logo lemon lime', 'Sprite bottle ice'],
      productShape: 'can',
    },
  },
  {
    token: /\bnutella\b/i,
    canonical: 'Nutella',
    domain: 'pate a tartiner',
    profile: {
      primaryColor: '#3F2A1B',
      secondaryColor: '#E30613',
      productKeywords: ['pot de Nutella', 'tartine pain', 'noisette chocolat'],
      designVibe: 'brun chocolat + rouge logo, gourmand chaleureux, matin familial',
      typoVibe: 'serif italic curve',
      imageQueries: ['Nutella jar', 'Nutella tartine pain', 'Nutella logo officiel'],
      productShape: 'bottle',
    },
  },
  {
    token: /\bstarbucks\b/i,
    canonical: 'Starbucks',
    domain: 'coffee shop',
    profile: {
      primaryColor: '#006241',
      secondaryColor: '#FFFFFF',
      productKeywords: ['gobelet siren', 'cafe latte art', 'mug Starbucks', 'logo siren verte'],
      designVibe: 'vert profond, premium minimal, communautaire, artisanal',
      typoVibe: 'serif tradition + sans soft',
      imageQueries: ['Starbucks cup green', 'Starbucks logo siren', 'Starbucks coffee latte art'],
      productShape: 'cup',
    },
  },
  {
    token: /\bmcdonald'?s?\b/i,
    canonical: "McDonald's",
    domain: 'fast food',
    profile: {
      primaryColor: '#FFC72C',
      secondaryColor: '#DA291C',
      productKeywords: ['Big Mac', 'frites rouges', 'arches dorees', 'happy meal'],
      designVibe: 'jaune doré + rouge feu, convivial, rapide, americain familial',
      typoVibe: 'sans bold rounded',
      imageQueries: ['McDonalds Big Mac', 'McDonalds frites', 'McDonalds golden arches logo'],
      productShape: 'logo',
    },
  },
  {
    token: /\bkfc\b/i,
    canonical: 'KFC',
    domain: 'fast food poulet',
    profile: {
      primaryColor: '#E4002B',
      secondaryColor: '#FFFFFF',
      productKeywords: ['bucket poulet', 'colonel Sanders', 'cuisses croustillantes'],
      designVibe: 'rouge americain + colonel iconic, friture chaleureuse Southern',
      typoVibe: 'serif vintage US',
      imageQueries: ['KFC bucket chicken', 'KFC colonel logo', 'KFC chicken pieces'],
      productShape: 'cup',
    },
  },
  {
    token: /\bburger king\b/i,
    canonical: 'Burger King',
    domain: 'fast food',
    profile: {
      primaryColor: '#D62300',
      secondaryColor: '#F5EBDC',
      tertiaryColor: '#502314',
      productKeywords: ['Whopper', 'flamme grill', 'logo crown burger'],
      designVibe: 'orange brule + creme, flame-grilled rebel cool',
      typoVibe: 'serif chunky retro',
      imageQueries: ['Burger King Whopper', 'Burger King logo', 'Burger King flame grill'],
      productShape: 'logo',
    },
  },
  {
    token: /\btesla\b/i,
    canonical: 'Tesla',
    domain: 'voitures electriques',
    profile: {
      primaryColor: '#E31937',
      secondaryColor: '#000000',
      tertiaryColor: '#F4F4F4',
      productKeywords: ['Model S', 'Model 3', 'Model X', 'Cybertruck', 'Supercharger', 'tableau de bord minimal'],
      designVibe: 'rouge accent sur noir, futur minimaliste, silencieux, premium tech',
      typoVibe: 'sans geometric thin/regular spaced',
      imageQueries: ['Tesla Model S exterior', 'Tesla Model 3 dashboard', 'Tesla Cybertruck', 'Tesla logo silver'],
      productShape: 'car',
    },
  },
  {
    token: /\brenault\b/i,
    canonical: 'Renault',
    domain: 'automobile',
    profile: {
      primaryColor: '#FFCC00',
      secondaryColor: '#000000',
      productKeywords: ['logo losange', 'Megane', 'Clio', 'Captur', 'Twingo'],
      designVibe: 'jaune accent + noir, francais agile, accessible',
      typoVibe: 'sans modern',
      imageQueries: ['Renault logo diamond', 'Renault Megane', 'Renault Clio'],
      productShape: 'car',
    },
  },
  {
    token: /\bpeugeot\b/i,
    canonical: 'Peugeot',
    domain: 'automobile',
    profile: {
      primaryColor: '#0058A3',
      secondaryColor: '#000000',
      productKeywords: ['logo lion', '208', '308', '3008', '5008'],
      designVibe: 'bleu profond + lion, francais elegant, technologique',
      typoVibe: 'serif bold modern',
      imageQueries: ['Peugeot logo lion', 'Peugeot 308', 'Peugeot 3008'],
      productShape: 'car',
    },
  },
  {
    token: /\bbmw\b/i,
    canonical: 'BMW',
    domain: 'automobile premium',
    profile: {
      primaryColor: '#1C69D4',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#000000',
      productKeywords: ['Serie 3', 'M5', 'i7', 'logo helice bleu blanc'],
      designVibe: 'bleu Bavaria sur blanc/noir, premium ingenierie, sportif',
      typoVibe: 'sans corporate clean',
      imageQueries: ['BMW Serie 3 sedan', 'BMW M5 sport', 'BMW logo'],
      productShape: 'car',
    },
  },
  {
    token: /\bporsche\b/i,
    canonical: 'Porsche',
    domain: 'voitures sportives',
    profile: {
      primaryColor: '#D5001C',
      secondaryColor: '#000000',
      tertiaryColor: '#FFFFFF',
      productKeywords: ['911', 'Cayenne', 'Taycan', 'Crest Stuttgart'],
      designVibe: 'rouge sportif sur noir, heritage Stuttgart, performance pure',
      typoVibe: 'serif italic + sans bold',
      imageQueries: ['Porsche 911', 'Porsche Taycan electric', 'Porsche crest logo'],
      productShape: 'car',
    },
  },
  {
    token: /\bapple\b/i,
    canonical: 'Apple',
    domain: 'tech / devices',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#A2AAAD',
      productKeywords: ['iPhone', 'MacBook', 'iPad', 'AirPods', 'Apple Watch', 'logo pomme'],
      designVibe: 'noir / blanc / argent, minimal aere sharp, premium futur sobre',
      typoVibe: 'San Francisco / Helvetica Now sans clean',
      imageQueries: ['Apple iPhone product shot', 'MacBook Pro silver', 'Apple logo silver', 'Apple Park HQ'],
      productShape: 'logo',
    },
  },
  {
    token: /\biphone( ?\d{1,2})?\b/i,
    canonical: 'iPhone',
    domain: 'smartphone Apple',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#A2AAAD',
      tertiaryColor: '#1D1D1F',
      productKeywords: ['iPhone Pro', 'titanium', 'Dynamic Island', 'camera lenses'],
      designVibe: 'noir profond + titane, photo-sharp, tech bijou',
      typoVibe: 'sans display bold + body regular',
      imageQueries: ['iPhone 15 Pro titanium', 'iPhone product shot black', 'iPhone camera detail'],
      productShape: 'phone',
    },
  },
  {
    token: /\bipad\b/i,
    canonical: 'iPad',
    domain: 'tablette Apple',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['iPad Pro', 'Apple Pencil', 'Magic Keyboard', 'M2 chip'],
      designVibe: 'aluminium argent sur fond blanc, productivite creative',
      typoVibe: 'sans clean + accents creatifs',
      imageQueries: ['iPad Pro product', 'Apple Pencil drawing', 'iPad Magic Keyboard'],
      productShape: 'tablet',
    },
  },
  {
    token: /\bmacbook\b/i,
    canonical: 'MacBook',
    domain: 'laptop Apple',
    profile: {
      primaryColor: '#1D1D1F',
      secondaryColor: '#A2AAAD',
      productKeywords: ['MacBook Pro', 'M3 chip', 'Liquid Retina XDR', 'aluminium unibody'],
      designVibe: 'gris sideral + argent, performance creative, minimal pro',
      typoVibe: 'sans clean tech',
      imageQueries: ['MacBook Pro space gray', 'MacBook M3 chip', 'MacBook keyboard close up'],
      productShape: 'laptop',
    },
  },
  {
    token: /\bsamsung\b/i,
    canonical: 'Samsung',
    domain: 'tech / mobile',
    profile: {
      primaryColor: '#1428A0',
      secondaryColor: '#FFFFFF',
      productKeywords: ['Galaxy S24', 'Galaxy Fold', 'Neo QLED', 'logo bleu'],
      designVibe: 'bleu electrique + blanc, tech innovation grand public',
      typoVibe: 'sans modern',
      imageQueries: ['Samsung Galaxy S24', 'Samsung Galaxy Fold', 'Samsung logo blue'],
      productShape: 'phone',
    },
  },
  {
    token: /\bgoogle\b/i,
    canonical: 'Google',
    domain: 'tech / services',
    profile: {
      primaryColor: '#4285F4',
      secondaryColor: '#EA4335',
      tertiaryColor: '#FBBC04',
      productKeywords: ['logo G colore', 'Pixel', 'Search', 'Material Design'],
      designVibe: 'quadricolore (bleu, rouge, jaune, vert) sur blanc, friendly clean',
      typoVibe: 'Product Sans / Roboto rounded',
      imageQueries: ['Google logo colors', 'Google Pixel phone', 'Google Material Design'],
      productShape: 'logo',
    },
  },
  {
    token: /\bspotify\b/i,
    canonical: 'Spotify',
    domain: 'streaming musical',
    profile: {
      primaryColor: '#1DB954',
      secondaryColor: '#191414',
      productKeywords: ['onde sonore', 'casque audio', 'logo vert', 'playlist cover'],
      designVibe: 'vert neon sur noir, audio musical immersif, vibrant',
      typoVibe: 'Circular bold + sans body',
      imageQueries: ['Spotify logo green', 'Spotify app interface', 'Spotify playlist artwork'],
      productShape: 'logo',
    },
  },
  {
    token: /\bnetflix\b/i,
    canonical: 'Netflix',
    domain: 'streaming video',
    profile: {
      primaryColor: '#E50914',
      secondaryColor: '#000000',
      productKeywords: ['logo N rouge', 'series posters', 'TV cinema'],
      designVibe: 'rouge vif sur noir profond, cinematic dramatique',
      typoVibe: 'sans condensed bold',
      imageQueries: ['Netflix logo red', 'Netflix interface dark', 'Netflix poster grid'],
      productShape: 'logo',
    },
  },
  {
    token: /\byoutube\b/i,
    canonical: 'YouTube',
    domain: 'plateforme video',
    profile: {
      primaryColor: '#FF0000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['bouton play rouge', 'thumbnail video', 'logo rectangle'],
      designVibe: 'rouge play + blanc, video creator friendly',
      typoVibe: 'sans Roboto',
      imageQueries: ['YouTube logo play button', 'YouTube interface', 'YouTube creator'],
      productShape: 'logo',
    },
  },
  {
    token: /\bnike\b/i,
    canonical: 'Nike',
    domain: 'sportswear',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#FA5400',
      productKeywords: ['Air Max', 'Jordan', 'swoosh', 'sneakers'],
      designVibe: 'noir / blanc + accent orange, swoosh iconic, athletique inspirant',
      typoVibe: 'Futura bold uppercase + sans body',
      imageQueries: ['Nike Air Max sneaker', 'Nike swoosh logo', 'Nike Jordan basketball'],
      productShape: 'shoe',
    },
  },
  {
    token: /\badidas\b/i,
    canonical: 'Adidas',
    domain: 'sportswear',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['Stan Smith', 'Yeezy', 'three stripes', 'Originals'],
      designVibe: 'noir / blanc, three-stripes minimal sportif iconic',
      typoVibe: 'sans condensed bold lowercase',
      imageQueries: ['Adidas Stan Smith', 'Adidas trefoil logo', 'Adidas three stripes'],
      productShape: 'shoe',
    },
  },
  {
    token: /\bpuma\b/i,
    canonical: 'Puma',
    domain: 'sportswear',
    profile: {
      primaryColor: '#1C1C1C',
      secondaryColor: '#FFFFFF',
      productKeywords: ['Suede', 'logo puma jumping', 'sneakers', 'training'],
      designVibe: 'noir + blanc, puma cat dynamique, sport street',
      typoVibe: 'sans bold italic',
      imageQueries: ['Puma Suede sneaker', 'Puma logo cat', 'Puma sport apparel'],
      productShape: 'shoe',
    },
  },
  {
    token: /\bgucci\b/i,
    canonical: 'Gucci',
    domain: 'luxe mode',
    profile: {
      primaryColor: '#0B6623',
      secondaryColor: '#A0001E',
      tertiaryColor: '#F4E1A4',
      productKeywords: ['monogram GG', 'web stripe vert rouge', 'sac luxe', 'mocassin'],
      designVibe: 'vert + rouge sur creme, heritage italien luxe maximaliste',
      typoVibe: 'serif vintage italic',
      imageQueries: ['Gucci monogram bag', 'Gucci logo GG', 'Gucci stripe red green'],
      productShape: 'bag',
    },
  },
  {
    token: /\bprada\b/i,
    canonical: 'Prada',
    domain: 'luxe mode',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['triangle Prada', 'sac', 'mode minimaliste'],
      designVibe: 'noir / blanc minimal, luxe italien architectural',
      typoVibe: 'serif sharp uppercase',
      imageQueries: ['Prada bag triangle logo', 'Prada minimal store', 'Prada fashion show'],
      productShape: 'bag',
    },
  },
  {
    token: /\bairbnb\b/i,
    canonical: 'Airbnb',
    domain: 'location hebergements',
    profile: {
      primaryColor: '#FF5A5F',
      secondaryColor: '#FFFFFF',
      productKeywords: ['logo Belo', 'maison', 'hebergement local'],
      designVibe: 'rose corail + blanc, friendly travel community',
      typoVibe: 'Cereal sans rounded',
      imageQueries: ['Airbnb logo Belo', 'Airbnb home interior', 'Airbnb travel destination'],
      productShape: 'building',
    },
  },
  {
    token: /\buber\b/i,
    canonical: 'Uber',
    domain: 'VTC / livraison',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['voiture VTC', 'app interface', 'logo wordmark'],
      designVibe: 'noir / blanc, technology mobility minimal',
      typoVibe: 'Uber Move sans bold',
      imageQueries: ['Uber logo wordmark', 'Uber app interface', 'Uber driver car'],
      productShape: 'car',
    },
  },
  {
    token: /\bferrari\b/i,
    canonical: 'Ferrari',
    domain: 'voitures sportives premium',
    profile: {
      primaryColor: '#FF2800',
      secondaryColor: '#000000',
      tertiaryColor: '#FFEC00',
      productKeywords: ['cheval cabre', 'F8', 'SF90', 'Monza', 'Maranello'],
      designVibe: 'rouge Rosso Corsa + jaune Modena, exotic supercar Italian heritage',
      typoVibe: 'serif italic sport',
      imageQueries: ['Ferrari F8 red', 'Ferrari prancing horse logo', 'Ferrari SF90'],
      productShape: 'car',
    },
  },
  {
    token: /\blamborghini\b/i,
    canonical: 'Lamborghini',
    domain: 'voitures sportives extremes',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFCC00',
      productKeywords: ['Huracan', 'Aventador', 'Urus', 'taureau dore'],
      designVibe: 'jaune dore + noir, raging bull aggressive futuriste',
      typoVibe: 'sans bold uppercase italic',
      imageQueries: ['Lamborghini Huracan yellow', 'Lamborghini Aventador', 'Lamborghini bull logo'],
      productShape: 'car',
    },
  },
  {
    token: /\bmercedes\b/i,
    canonical: 'Mercedes-Benz',
    domain: 'automobile luxe allemand',
    profile: {
      primaryColor: '#00ADEF',
      secondaryColor: '#000000',
      tertiaryColor: '#C5C5C5',
      productKeywords: ['Classe S', 'AMG GT', 'EQS', 'etoile trois branches'],
      designVibe: 'argent + noir, premium prestige Stuttgart elegance',
      typoVibe: 'serif corporate + sans body',
      imageQueries: ['Mercedes Classe S', 'Mercedes AMG GT', 'Mercedes star logo'],
      productShape: 'car',
    },
  },
  {
    token: /\brolex\b/i,
    canonical: 'Rolex',
    domain: 'horlogerie luxe',
    profile: {
      primaryColor: '#006039',
      secondaryColor: '#FBC600',
      productKeywords: ['Submariner', 'Daytona', 'GMT-Master', 'couronne'],
      designVibe: 'vert profond + or, prestige horlogerie Suisse heritage',
      typoVibe: 'serif corporate elegant',
      imageQueries: ['Rolex Submariner', 'Rolex Daytona gold', 'Rolex crown logo'],
      productShape: 'watch',
    },
  },
  {
    token: /\blouis vuitton\b|\blv\b/i,
    canonical: 'Louis Vuitton',
    domain: 'maroquinerie luxe',
    profile: {
      primaryColor: '#5D3A1A',
      secondaryColor: '#FFD700',
      productKeywords: ['monogram LV', 'sac Speedy', 'Neverfull', 'malle'],
      designVibe: 'brun + or, monogram Parisien heritage maroquinerie',
      typoVibe: 'serif italic Futura mix',
      imageQueries: ['Louis Vuitton monogram bag', 'LV logo gold', 'Louis Vuitton store'],
      productShape: 'bag',
    },
  },
  {
    token: /\bchanel\b/i,
    canonical: 'Chanel',
    domain: 'mode parfum luxe',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#C8A951',
      productKeywords: ['No 5', 'sac 2.55', 'tweed', 'CC interlocking'],
      designVibe: 'noir / blanc + or, Paris haute couture intemporel',
      typoVibe: 'serif italic + sans condensed',
      imageQueries: ['Chanel No 5 perfume', 'Chanel CC logo', 'Chanel 2.55 bag'],
      productShape: 'bottle',
    },
  },
  {
    token: /\bhermes\b|\bhermès\b/i,
    canonical: 'Hermès',
    domain: 'maroquinerie luxe ultra',
    profile: {
      primaryColor: '#FF6E00',
      secondaryColor: '#FFFFFF',
      productKeywords: ['Birkin', 'Kelly', 'carre soie', 'cheval Duc-attele'],
      designVibe: 'orange Hermes + blanc, equestrian Parisian craftsmanship',
      typoVibe: 'serif elegant',
      imageQueries: ['Hermes Birkin bag', 'Hermes orange box', 'Hermes carre silk'],
      productShape: 'bag',
    },
  },
  {
    token: /\bsony\b/i,
    canonical: 'Sony',
    domain: 'electronique audio video',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['casque WH-1000XM5', 'Alpha A7', 'BRAVIA', 'PlayStation'],
      designVibe: 'noir minimal, ingenierie japonaise audio video premium',
      typoVibe: 'sans corporate Helvetica-like',
      imageQueries: ['Sony WH-1000XM5 headphones', 'Sony Alpha camera', 'Sony BRAVIA TV'],
      productShape: 'headphones',
    },
  },
  {
    token: /\bplaystation\b|\bps5\b/i,
    canonical: 'PlayStation',
    domain: 'console gaming Sony',
    profile: {
      primaryColor: '#003791',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#000000',
      productKeywords: ['PS5', 'DualSense', 'logo PS', 'controller'],
      designVibe: 'bleu PS + blanc, gaming next-gen futuriste',
      typoVibe: 'sans display bold',
      imageQueries: ['PlayStation 5 console', 'DualSense controller', 'PlayStation logo'],
      productShape: 'controller',
    },
  },
  {
    token: /\bxbox\b/i,
    canonical: 'Xbox',
    domain: 'console gaming Microsoft',
    profile: {
      primaryColor: '#107C10',
      secondaryColor: '#000000',
      productKeywords: ['Series X', 'controller', 'Halo', 'logo X'],
      designVibe: 'vert Xbox + noir, gaming power Microsoft',
      typoVibe: 'sans bold modern',
      imageQueries: ['Xbox Series X console', 'Xbox controller', 'Xbox green logo'],
      productShape: 'controller',
    },
  },
  {
    token: /\bnintendo\b/i,
    canonical: 'Nintendo',
    domain: 'gaming Nintendo',
    profile: {
      primaryColor: '#E60012',
      secondaryColor: '#FFFFFF',
      productKeywords: ['Switch', 'Mario', 'Zelda', 'Joy-Con'],
      designVibe: 'rouge Nintendo + blanc, joyful family gaming Japan',
      typoVibe: 'sans rounded playful',
      imageQueries: ['Nintendo Switch console', 'Nintendo Mario', 'Nintendo logo red'],
      productShape: 'console',
    },
  },
  {
    token: /\bmicrosoft\b/i,
    canonical: 'Microsoft',
    domain: 'tech enterprise',
    profile: {
      primaryColor: '#F25022',
      secondaryColor: '#7FBA00',
      tertiaryColor: '#00A4EF',
      productKeywords: ['Windows', 'Surface', 'Office 365', 'logo 4 carres'],
      designVibe: 'quadricolore (rouge, vert, bleu, jaune), Fluent Design productive',
      typoVibe: 'Segoe UI sans modern',
      imageQueries: ['Microsoft logo 4 squares', 'Microsoft Surface', 'Microsoft Windows 11'],
      productShape: 'logo',
    },
  },
  {
    token: /\bopenai\b/i,
    canonical: 'OpenAI',
    domain: 'AI research',
    profile: {
      primaryColor: '#10A37F',
      secondaryColor: '#000000',
      productKeywords: ['ChatGPT', 'GPT-4', 'logo hexagonal', 'DALL-E'],
      designVibe: 'vert mint + noir, AI cutting-edge minimal scientifique',
      typoVibe: 'sans clean tech',
      imageQueries: ['OpenAI logo', 'ChatGPT interface', 'OpenAI hexagon'],
      productShape: 'logo',
    },
  },
  {
    token: /\banthropic\b|\bclaude\b/i,
    canonical: 'Anthropic',
    domain: 'AI safety research',
    profile: {
      primaryColor: '#D97757',
      secondaryColor: '#191919',
      productKeywords: ['Claude', 'logo A', 'Claude Code'],
      designVibe: 'orange peche + noir, AI thoughtful warm scientifique',
      typoVibe: 'serif modern + sans body',
      imageQueries: ['Anthropic logo', 'Claude AI interface', 'Anthropic orange'],
      productShape: 'logo',
    },
  },
  {
    token: /\bstripe\b/i,
    canonical: 'Stripe',
    domain: 'paiement en ligne',
    profile: {
      primaryColor: '#635BFF',
      secondaryColor: '#0A2540',
      productKeywords: ['logo wordmark', 'paiement card', 'dashboard'],
      designVibe: 'violet electrique + bleu nuit, fintech premium developer-first',
      typoVibe: 'sans Sohne modern',
      imageQueries: ['Stripe logo purple', 'Stripe dashboard', 'Stripe card payment'],
      productShape: 'card',
    },
  },
  {
    token: /\bvercel\b/i,
    canonical: 'Vercel',
    domain: 'hosting frontend',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      productKeywords: ['triangle logo', 'Next.js', 'deploy preview'],
      designVibe: 'noir / blanc minimaliste, Next.js geometric devops',
      typoVibe: 'Inter sans clean',
      imageQueries: ['Vercel logo triangle', 'Vercel dashboard', 'Vercel Next.js'],
      productShape: 'logo',
    },
  },
  {
    token: /\bnotion\b/i,
    canonical: 'Notion',
    domain: 'productivite workspace',
    profile: {
      primaryColor: '#000000',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#E16259',
      productKeywords: ['logo N', 'workspace blocks', 'productivity'],
      designVibe: 'noir / blanc minimal warm illustrations friendly',
      typoVibe: 'serif modern + sans body',
      imageQueries: ['Notion logo', 'Notion workspace interface', 'Notion blocks'],
      productShape: 'logo',
    },
  },
  {
    token: /\bikea\b/i,
    canonical: 'IKEA',
    domain: 'mobilier maison',
    profile: {
      primaryColor: '#0058A3',
      secondaryColor: '#FFDA1A',
      productKeywords: ['meuble flatpack', 'BILLY', 'POÄNG', 'logo bleu jaune'],
      designVibe: 'bleu Suede + jaune, mobilier accessible scandinave',
      typoVibe: 'sans Verdana / Noto bold',
      imageQueries: ['IKEA logo blue yellow', 'IKEA furniture catalog', 'IKEA store'],
      productShape: 'building',
    },
  },
  {
    token: /\blego\b/i,
    canonical: 'LEGO',
    domain: 'jouets briques',
    profile: {
      primaryColor: '#D80000',
      secondaryColor: '#FFCD00',
      tertiaryColor: '#000000',
      productKeywords: ['briques colorees', 'minifigure', 'set construction'],
      designVibe: 'rouge + jaune iconique, joyful play creativity bricks',
      typoVibe: 'sans bold rounded',
      imageQueries: ['LEGO bricks colorful', 'LEGO minifigure', 'LEGO logo red yellow'],
      productShape: 'logo',
    },
  },
]

export type SubjectDetection = {
  canonical: string | null
  domain: string | null
  /**
   * 'brand'           — matched the in-memory `BRAND_DICTIONARY` (47 well-known brands, fast path).
   * 'inferred_brand'  — matched the capitalised-name heuristic; profile is missing and the
   *                     orchestrator should call `/api/brand/enrich` on the bridge to fill it.
   * 'quoted'          — first quoted phrase in the prompt (user explicitly named a topic).
   * 'object'          — first concrete noun from CONCRETE_OBJECT_TOKENS.
   * 'none'            — nothing recognisable; the page is generic.
   */
  source: 'brand' | 'inferred_brand' | 'quoted' | 'object' | 'none'
  raw: string
  /** Brand palette/keywords/queries — only set when source === 'brand' (cache hit). For
   * 'inferred_brand', the orchestrator dynamically fills this via /api/brand/enrich. */
  brandProfile?: BrandProfile
}

/**
 * Stoplist for the inferred-brand heuristic. Capitalised words at the start of a French
 * or English sentence are not brands, so we ignore them. We also bail on UI verbs ("Crée",
 * "Build") and section nouns ("Page", "Site") that the user puts at the start of a prompt.
 */
const INFERRED_BRAND_STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des',
  'page', 'site', 'projet', 'application', 'app', 'jeu', 'game', 'logiciel',
  'crée', 'cree', 'creer', 'fais', 'faire', 'génère', 'genere', 'generer',
  'construis', 'construire', 'design', 'develop', 'develope', 'devoper', 'design',
  'coca', 'tesla', 'apple', 'nike', 'spotify', // already caught by dict, just safety
  'create', 'build', 'make', 'design', 'generate', 'develop',
  'web', 'mobile', 'desktop', 'cli', 'api',
  'ultra', 'pro', 'premium', 'simple', 'minimal',
  // Common capitalised words that start a clause but are NOT brands. Without
  // these, "Plusieurs plateformes", "Chaque niveau", "Ajoute un score"… get
  // mistaken for a brand and pollute the subject-lock.
  'plusieurs', 'chaque', 'certains', 'certaines', 'tous', 'toutes', 'tout', 'toute',
  'quelques', 'aucun', 'aucune', 'beaucoup', 'autre', 'autres', 'meme', 'memes',
  'voici', 'voila', 'ajoute', 'ajouter', 'ensuite', 'aussi', 'enfin', 'donc',
  'quand', 'lorsque', 'pendant', 'avec', 'dans', 'pour', 'sans', 'leur', 'leurs',
  'joueur', 'jeu', 'partie', 'niveau', 'niveaux', 'ecran', 'bouton', 'menu',
  'bonjour', 'salut', 'merci',
  'several', 'each', 'every', 'some', 'many', 'another', 'other', 'others',
  'when', 'while', 'then', 'also', 'here', 'there', 'this', 'that', 'these', 'those',
  'add', 'include', 'player', 'level', 'score', 'screen', 'button', 'hello',
])

/**
 * Detect a brand-like name by simple heuristic: a capitalised noun (1-3 tokens) that
 * doesn't match a stopword. The prompt "page de présentation pour Lipton" yields "Lipton".
 * Used as the LAST resort, AFTER the brand dictionary and the quoted-phrase rule.
 */
function detectInferredBrand(prompt: string): { canonical: string; raw: string } | null {
  // 1-3 capitalised words, possibly hyphenated. Anchored to a word boundary on both sides.
  const re = /\b([A-Z][a-z]{2,}(?:[- ][A-Z][a-z]+){0,2})\b/g
  const matches = Array.from(prompt.matchAll(re))
  for (const m of matches) {
    const phrase = m[1].trim()
    const firstWord = phrase.split(/[-\s]/)[0].toLowerCase()
    if (INFERRED_BRAND_STOPWORDS.has(firstWord)) continue
    if (firstWord.length < 3) continue
    // v89b: skip SENTENCE-INITIAL capitalised words. A capital at the start of
    // the prompt or right after . ! ? : ; / newline / a bullet is grammatical,
    // not a brand. "...sans backend. Exigences fonctionnelles :" used to extract
    // "Exigences" as an inferred brand and fire a useless Wikipedia+Ollama
    // enrich (and, worse, a subject-lock contradicting the real request — the
    // same class of bug as the "Plusieurs" incident). A real mid-sentence brand
    // ("page pour Lipton") is still detected; famous brands are caught earlier
    // by the dictionary, and any leading brand can be forced with quotes.
    const before = prompt.slice(0, m.index ?? 0)
    if (/(^|[.!?:;\n\r/]|^\s*[-•*])\s*$/.test(before)) continue
    return { canonical: phrase, raw: phrase }
  }
  return null
}

function detectSubject(prompt: string): SubjectDetection {
  // 1) Brand dictionary wins — those are unambiguous and must never be mistranslated.
  for (const entry of BRAND_DICTIONARY) {
    if (entry.token.test(prompt)) {
      return {
        canonical: entry.canonical,
        domain: entry.domain,
        source: 'brand',
        raw: prompt.match(entry.token)?.[0] ?? entry.canonical,
        brandProfile: entry.profile,
      }
    }
  }
  // 2) First quoted phrase if any.
  const quoted = prompt.match(/["'«»]([^"'«»]{2,60})["'«»]/)
  if (quoted && quoted[1]) {
    return { canonical: quoted[1].trim(), domain: null, source: 'quoted', raw: quoted[0] }
  }
  // 3) First concrete noun from the dictionary.
  const lower = normalizeSignalText(prompt)
  for (const token of CONCRETE_OBJECT_TOKENS) {
    if (containsSignal(lower, token)) {
      return { canonical: token, domain: null, source: 'object', raw: token }
    }
  }
  // Inferred brand: capitalize noun → /api/brand/enrich fetches palette/keywords/shape from Wikipedia + Ollama.
  //
  // GUARD: NEVER infer a brand for a game request. The prompt "jeu de plateforme …
  // Plusieurs plateformes …" used to extract "Plusieurs" as a brand and inject a
  // subject-lock ("le mot Plusieurs DOIT figurer dans le <title>/<h1>, c'est une
  // marque réelle") that directly contradicts the game contract and derails
  // generation (broken, simplistic output). A game has no brand subject unless one
  // is named in the dictionary (already handled above). Same reasoning protects
  // any build whose subject is a generic capitalised word, not a real brand.
  const isGamePrompt = containsAnySignal(normalizeSignalText(prompt), GAME_SIGNALS)
  if (!isGamePrompt) {
    const inferred = detectInferredBrand(prompt)
    if (inferred) {
      return {
        canonical: inferred.canonical,
        domain: null,
        source: 'inferred_brand',
        raw: inferred.raw,
      }
    }
  }
  return { canonical: null, domain: null, source: 'none', raw: '' }
}

function classifyCodeAssetPlan(prompt: string): CodeAssetPlan {
  const lower = normalizeSignalText(prompt)
  const styleHints = extractMentions(lower, PREMIUM_LOOK_TOKENS)
  const objectMentions = extractObjectMentions(prompt)
  const effectMentions = extractMentions(lower, EFFECT_TOKENS)
  const wantsImages = extractMentions(lower, IMAGE_TOKENS).length > 0 || objectMentions.length > 0
  const wants3D = extractMentions(lower, THREED_TOKENS).length > 0
  const wantsResearch = extractMentions(lower, RESEARCH_TRIGGER_TOKENS).length > 0
  const wantsPremiumLook = styleHints.length > 0
  const paletteHints = Array.from(new Set((prompt.match(COLOR_HEX_REGEX) || []).map((c) => c.toLowerCase())))
  const researchQueries = buildResearchQueries(prompt, styleHints, objectMentions, wantsPremiumLook || wantsResearch)
  const subject = detectSubject(prompt)
  const language = detectPromptLanguage(prompt)

  // If we detected a brand, inject brand-specific research queries upfront
  // so the page actually looks like the brand (colors, tone, visuals).
  if (subject.source === 'brand' && subject.canonical) {
    const brand = subject.canonical
    researchQueries.unshift(
      `${brand} brand colors hex codes`,
      `${brand} official logo png`,
      `${brand} website design style`,
    )
  }

  return {
    styleHints,
    objectMentions,
    effectMentions,
    paletteHints,
    wantsPremiumLook,
    wantsImages,
    wants3D,
    wantsResearch: wantsResearch || wantsPremiumLook || objectMentions.length > 0 || subject.source !== 'none',
    researchQueries: Array.from(new Set(researchQueries)).slice(0, 8),
    subject,
    language,
  }
}

function estimateFileCount(complexity: CodeComplexity, projectType: CodeProjectType): number {
  const base: Record<CodeComplexity, number> = {
    trivial: 1,
    simple: 3,
    moderate: 8,
    complex: 18,
    enterprise: 35,
  }

  const multiplier: Partial<Record<CodeProjectType, number>> = {
    spa_react: 1.5,
    spa_vue: 1.5,
    spa_angular: 2.0,
    ssr_nextjs: 1.8,
    fullstack_mern: 2.0,
    fullstack_nextjs: 2.0,
    fullstack_django: 1.6,
    api_spring: 1.5,
    desktop_electron: 1.5,
    desktop_tauri: 1.8,
  }

  return Math.round(base[complexity] * (multiplier[projectType] ?? 1.0))
}

function isWholeProductRequest(normalizedLower: string): boolean {
  return /\b(app|application|logiciel|outil|plateforme|dashboard|tableau de bord|studio|crm|erp|saas|marketplace|backoffice|admin)\b/i.test(normalizedLower)
    && /\b(complet|complete|entiere|entier|professionnel|pro|client|production|mvp|fonctionnalites|workflow|tunnel|ui|interface|module)\b/i.test(normalizedLower)
}

function minimumFileCountForIntent(projectType: CodeProjectType, features: string[], wholeProduct: boolean): number {
  const has = (feature: string) => features.includes(feature)
  if (projectType === 'static_web') return wholeProduct || has('multipage') ? 4 : 3
  if (projectType === 'game_web') return 3
  if (projectType.startsWith('spa_')) return wholeProduct ? 10 : 6
  if (projectType === 'desktop_tauri') return wholeProduct ? 14 : 8
  if (projectType === 'desktop_electron') return wholeProduct ? 10 : 6
  if (projectType === 'mobile_rn' || projectType === 'mobile_flutter') return wholeProduct ? 10 : 6
  if (projectType.startsWith('api_') || projectType.startsWith('fullstack_') || projectType.startsWith('ssr_')) return wholeProduct ? 10 : 6
  if (projectType.startsWith('cli_') || projectType.startsWith('system_') || projectType === 'data_python') return wholeProduct ? 5 : 3
  return wholeProduct ? 4 : 1
}

// ---------------------------------------------------------------------------
// Follow-up helpers — detect explicit stack mentions in short follow-up prompts
// ---------------------------------------------------------------------------

/**
 * True if the prompt explicitly names a framework, a language, a platform
 * family, or any signal that should force a stack reclassification even
 * when the user is in a follow-up conversation.
 */
export function hasExplicitStackMention(normalizedLower: string): boolean {
  // Frameworks
  for (const keyword of Object.keys(FRAMEWORK_SIGNALS)) {
    if (containsSignal(normalizedLower, keyword)) return true
  }
  // Languages
  for (const keyword of Object.keys(LANGUAGE_SIGNALS)) {
    if (containsSignal(normalizedLower, keyword)) return true
  }
  // Platform families
  if (containsAnySignal(normalizedLower, WEB_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, MOBILE_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, DESKTOP_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, API_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, GAME_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, THREED_APP_SIGNALS)) return true
  return false
}

/**
 * Heuristic fallback (no LLM) that classifies a follow-up prompt into one of
 * four pivot kinds. Used when the LLM-driven `analyzeFollowUpIntent` fails
 * or is disabled. Based purely on lexical cues.
 */
export function classifyPivotKindHeuristic(
  newPrompt: string,
  hasHistory: boolean,
  hasExistingFiles: boolean,
): 'increment' | 'pivot_platform' | 'pivot_feature' | 'fresh_start' {
  const lower = normalizeSignalText(newPrompt).trim()

  // Without any history or files → always fresh_start.
  if (!hasHistory && !hasExistingFiles) return 'fresh_start'

  // Explicit pivot cues ("la meme chose mais en python", "refais en flask",
  // "convertis en mobile", "plutot en vue"…). Pair a pivot verb with a
  // stack/language mention and we treat it as a platform pivot.
  const pivotVerbs = [
    'meme chose', 'pareil', 'mais en', 'mais sur', 'mais pour',
    'plutot', 'plutôt', 'refais', 'refait', 'recommence',
    'convertis', 'convertir', 'transforme', 'transformer',
    'version', 'port', 'porte', 'migrer', 'migre',
    'same thing', 'instead', 'rewrite', 'convert', 'port to',
  ]
  const hasPivotVerb = pivotVerbs.some((verb) => lower.includes(verb))
  const hasStack = hasExplicitStackMention(lower)
  if (hasPivotVerb && hasStack) return 'pivot_platform'

  // A bare stack mention in a short follow-up without pivot verb is still
  // a platform pivot if the user was clearly working on another stack.
  if (hasStack && lower.split(/\s+/).length <= 8 && hasExistingFiles) {
    return 'pivot_platform'
  }

  // Very short follow-up without any stack mention → incremental patch.
  if (lower.length < 60 && hasExistingFiles) return 'increment'

  // Long, detailed prompt mentioning a stack → probably a new feature in
  // the same project (or occasionally a fresh start). Default to
  // pivot_feature so the classifier still runs on the fresh prompt.
  if (hasStack) return 'pivot_feature'

  // Otherwise default to incremental when there is an existing project.
  return hasExistingFiles ? 'increment' : 'fresh_start'
}

// ---------------------------------------------------------------------------
// Main classification — fully deterministic, no LLM
// ---------------------------------------------------------------------------

/**
 * Context hints passed by the orchestrator when the user is iterating on
 * an existing project (follow-up message). The classifier uses these to
 * avoid flipping the project type on a short incremental request like
 * "change the color to blue" while still honoring explicit pivots like
 * "refais la meme chose en python".
 */
export type CodeIntentContext = {
  /** Project type of the previous generation, if any. */
  previousProjectType?: CodeProjectType
  /** Languages used in the previous generation. */
  previousLanguages?: string[]
  /** Frameworks used in the previous generation. */
  previousFrameworks?: string[]
  /**
   * Follow-up classification resolved by `analyzeFollowUpIntent`:
   *  - 'increment'       → small patch over the same project, keep previous stack
   *  - 'pivot_platform'  → user wants the same concept on another stack/language
   *  - 'pivot_feature'   → major feature change in the same stack
   *  - 'fresh_start'     → unrelated new project, reclassify from scratch
   */
  pivotKind?: 'increment' | 'pivot_platform' | 'pivot_feature' | 'fresh_start'
}

export function classifyCodeIntent(prompt: string, context?: CodeIntentContext): CodeIntent {
  const lower = normalizeSignalText(prompt)

  // If the follow-up analyzer said "increment" and the new prompt is short
  // and does not mention any framework/language on its own, inherit the
  // previous stack so "ajoute un bouton delete" does not downgrade a Flask
  // API back to a generic script.
  const isIncrementReuse = context?.pivotKind === 'increment'
    && context.previousProjectType
    && context.previousProjectType !== 'unknown'

  if (isIncrementReuse) {
    const mentionsExplicitStack = hasExplicitStackMention(lower)
    if (!mentionsExplicitStack) {
      const assetPlan = classifyCodeAssetPlan(prompt)
      const complexity = estimateComplexity(prompt)
      const previousType = context.previousProjectType!
      const languages = context.previousLanguages ?? []
      const frameworks = context.previousFrameworks ?? []
      const needsDevServer = DEV_SERVER_PROJECTS.has(previousType)
      const needsBundling = BUNDLED_PREVIEW_PROJECTS.has(previousType) || previousType.startsWith('spa_')
      const previewType: PreviewType =
        needsDevServer ? 'dev_server'
          : (needsBundling) ? 'iframe_bundled'
          : (previousType === 'static_web' || previousType === 'game_web') ? 'iframe_static'
          : (previousType.startsWith('cli_') || previousType.startsWith('system_') || previousType === 'script' || previousType === 'data_python') ? 'console'
          : 'none'
      const isGameRequest = previousType === 'game_web'
      const { gameKind, knownGame } = classifyGameKind(lower, isGameRequest)

      return {
        projectType: previousType,
        complexity,
        languages,
        frameworks,
        features: [],
        needsDevServer,
        needsBundling,
        previewType,
        devCommand: getDevCommand(previousType),
        buildCommand: getBuildCommand(previousType),
        testCommand: getTestCommand(previousType),
        primaryModelRole: 'code',
        needsArchitecturePlanning: false,
        estimatedFileCount: estimateFileCount(complexity, previousType),
        assetPlan,
        ...(isGameRequest ? { gameKind, ...(knownGame ? { knownGame } : {}) } : {}),
      }
    }
  }
  // pivot_platform / pivot_feature / fresh_start → fall through to full reclassification

  let projectType: CodeProjectType = 'unknown'
  const languages: string[] = []
  const frameworks: string[] = []
  const features: string[] = []

  // Step 1: detect framework signals (highest priority).
  // v89b: "react native" is a SUPERSTRING of "react" and the object order lists
  // 'react' first, so "app React Native … Expo" used to match 'react' and be
  // misclassified as a React web SPA. Match the compound explicitly first.
  // (A blanket longest-keyword reorder is wrong here: it would let 'three.js'
  // beat 'react' for "React + Three.js" and lose the react-three-fiber path.)
  if (/\breact[-\s]native\b/i.test(lower)) {
    projectType = 'mobile_rn'
    frameworks.push('react-native', 'expo')
    languages.push('typescript')
    features.push('mobile-native')
  } else {
    for (const [keyword, signal] of Object.entries(FRAMEWORK_SIGNALS)) {
      if (containsSignal(lower, keyword)) {
        projectType = signal.projectType
        frameworks.push(...signal.frameworks)
        languages.push(...signal.languages)
        break
      }
    }
  }

  // Step 2: fullstack override
  if (projectType !== 'unknown') {
    for (const signal of FULLSTACK_SIGNALS) {
      if (containsSignal(lower, signal)) {
        if (projectType === 'spa_react' || projectType === 'api_express') {
          projectType = 'fullstack_mern'
        } else if (projectType === 'ssr_nextjs') {
          projectType = 'fullstack_nextjs'
        } else if (projectType === 'api_django') {
          projectType = 'fullstack_django'
        }
        break
      }
    }
  }

  // v89b: compute the explicit-web signal BEFORE the mobile/desktop native
  // steps. A prompt that says "application web", "navigateur"/"browser",
  // "responsive", or "mobile/desktop" is WEB design and must NEVER be routed to
  // React Native (mobile_rn) or Tauri (desktop). Previously this lived at step
  // 6b — AFTER step 3a — so "dashboard responsive mobile/desktop, ouvrable dans
  // un navigateur" was hijacked into a React Native app because the bare word
  // "mobile" in MOBILE_SIGNALS short-circuited looksLikeMobileAppRequest().
  const userExplicitlyAskedWeb =
    containsAnySignal(lower, WEB_SIGNALS)
    || /\bpage\s*web\b|\bsite\s*(?:web|internet)\b|\blanding\s*page\b|\bwebapp\b|\bweb\s*app\b|\bapplication\s+web\b|\bappli(?:cation)?\s+web\b|\bapp\s+web\b/i.test(lower)
    || /\bnavigateur\b|\bbrowser\b/i.test(lower)
    || /\bresponsive\b/i.test(lower)
    || /\bmobile[\s/–—-]*(?:first|desktop)\b/i.test(lower)
    || /\bmobile\s+(?:et|ou|\/|,)\s*(?:desktop|ordinateur|pc)\b/i.test(lower)

  // v89b: an explicit single-page / no-build request must NOT be upgraded to a
  // React SPA (which needs a bundler and can't be "directement ouvrable dans un
  // navigateur"). A "dashboard"/"tableau de bord" is a MULTIPAGE_SIGNAL but is
  // almost always a single page — so "tableau de bord ... en une seule page,
  // directement ouvrable dans un navigateur" must stay static_web, not spa_react.
  const wantsSinglePageStatic =
    /\bune?\s+seule?\s+page\b|\bsingle[-\s]?page\b|\bone[-\s]?page\b|\bmono[-\s]?page\b|\bpage\s+unique\b/i.test(lower)
    || /\bdirectement\s+ouvrable\b|\bouvrable\s+dans\s+un\s+navigateur\b|\bsans\s+build\b|\bsans\s+bundler\b|\bun\s+seul\s+fichier\b|\bfichier\s+html\s+unique\b/i.test(lower)

  // Step 3a: mobile app detection (before generic desktop so an explicit
  // "app android" wins over a vague "application") — but skipped entirely when
  // the user explicitly asked for a web/browser page.
  if (projectType === 'unknown' && !userExplicitlyAskedWeb && looksLikeMobileAppRequest(lower)) {
    projectType = 'mobile_rn'
    frameworks.push('react-native', 'expo')
    languages.push('typescript')
    features.push('mobile-native')
  }

  // Step 3b: desktop/native app detection — same web guard.
  if (projectType === 'unknown' && !userExplicitlyAskedWeb && looksLikeDesktopAppRequest(lower)) {
    projectType = 'desktop_tauri'
    frameworks.push('tauri')
    languages.push('typescript', 'rust')
    features.push('desktop-native')
  }

  // Step 3c (v89b): an EXPLICIT web request resolves to a web front-end here,
  // with authority over the generic language/API heuristics below (step 5/6).
  // Without this, a bare language mention ("en JavaScript pur") or a negated
  // backend ("sans backend") preempted the late step-6b web check and the page
  // was misclassified as cli_node / api_express. Multipage signals pick a React
  // SPA unless the user asked for a single self-contained page.
  if (projectType === 'unknown' && userExplicitlyAskedWeb) {
    if (!wantsSinglePageStatic && containsAnySignal(lower, MULTIPAGE_SIGNALS)) {
      projectType = 'spa_react'
      frameworks.push('react', 'react-router')
      languages.push('typescript')
      features.push('multipage')
    } else {
      projectType = 'static_web'
      languages.push('html', 'css', 'javascript')
    }
  }

  // Step 4: multipage web detection (upgrades static_web → SPA)
  if (!wantsSinglePageStatic && (projectType === 'unknown' || projectType === 'static_web')) {
    for (const signal of MULTIPAGE_SIGNALS) {
      if (containsSignal(lower, signal)) {
        // Default multi-page to React SPA if no framework specified
        if (projectType === 'unknown' || projectType === 'static_web') {
          projectType = 'spa_react'
          frameworks.push('react', 'react-router')
          languages.push('typescript')
        }
        features.push('multipage')
        break
      }
    }
  }

  // Step 5: detect language signals if no framework found
  if (projectType === 'unknown') {
    for (const [keyword, signal] of Object.entries(LANGUAGE_SIGNALS)) {
      if (containsSignal(lower, keyword)) {
        projectType = signal.projectType
        languages.push(...signal.languages)
        break
      }
    }
  }

  // v89b: a NEGATED backend mention ("sans backend", "no backend", "pas de
  // serveur", "front-end only", "100% front") is the OPPOSITE of an API request
  // — it must not match API_SIGNALS via the bare word "backend"/"serveur".
  const negatesBackend =
    /\b(sans|pas\s+de|aucun|no|without|zero)\s+(back-?end|serveur|server|api)\b/i.test(lower)
    || /\b(front-?end|client)[-\s]?(only|seul|uniquement|pur)\b/i.test(lower)
    || /\b100\s*%\s*front/i.test(lower)

  // Step 6: API detection upgrades CLI to API — skipped when the user explicitly
  // asked for a web front-end or explicitly said "no backend".
  if (
    !userExplicitlyAskedWeb && !negatesBackend
    && (projectType === 'cli_node' || projectType === 'cli_python' || projectType === 'unknown')
  ) {
    for (const signal of API_SIGNALS) {
      if (containsSignal(lower, signal)) {
        if (languages.includes('python') || containsSignal(lower, 'python')) {
          projectType = 'api_fastapi'
          frameworks.push('fastapi')
          if (!languages.includes('python')) languages.push('python')
        } else {
          projectType = 'api_express'
          frameworks.push('express')
          if (!languages.includes('typescript')) languages.push('typescript')
        }
        features.push('api')
        break
      }
    }
  }

  // Step 6b: web detection — `userExplicitlyAskedWeb` is computed before the
  // mobile/desktop native steps (see above), so an explicit web request can
  // never be hijacked into React Native / Tauri, and a bare "application"/"jeu"
  // with no web mention still falls through to the native defaults below.
  if (projectType === 'unknown' && userExplicitlyAskedWeb) {
    projectType = 'static_web'
    languages.push('html', 'css', 'javascript')
  }

  // Step 6c: game detection — native desktop app by default (Tauri shell),
  // web only if the user explicitly said "jeu web", "dans le navigateur",
  // "canvas"/"webgl"/"three.js", etc. Aligns with user rule: "quand je dis
  // 'jeu', tu penses a une APP pas a un site web".
  if (projectType === 'unknown') {
    for (const signal of GAME_SIGNALS) {
      if (containsSignal(lower, signal)) {
        const wantsWebCanvas =
          containsAnySignal(lower, WEB_SIGNALS)
          || /\bcanvas\b|\bwebgl\b|\bthree\.?js\b|\bphaser\b|\bpixi\b|\bnavigateur\b|\bbrowser\b/i.test(lower)
        if (wantsWebCanvas) {
          projectType = 'game_web'
          frameworks.push('canvas')
          languages.push('javascript')
          features.push('game')
        } else {
          projectType = 'desktop_tauri'
          frameworks.push('tauri', 'react')
          languages.push('typescript', 'rust')
          features.push('desktop-native', 'game')
        }
        break
      }
    }
  }

  // Step 6d: 3D app/scene detection — same rule: desktop app by default, web
  // only if explicit web signal.
  if (projectType === 'unknown') {
    for (const signal of THREED_APP_SIGNALS) {
      if (containsSignal(lower, signal)) {
        const wantsWebCanvas =
          containsAnySignal(lower, WEB_SIGNALS)
          || /\bthree\.?js\b|\bwebgl\b|\bwebgpu\b|\bnavigateur\b|\bbrowser\b/i.test(lower)
        if (wantsWebCanvas) {
          projectType = 'game_web'
          frameworks.push('three.js')
          languages.push('javascript')
          features.push('3d')
        } else {
          projectType = 'desktop_tauri'
          frameworks.push('tauri', 'react', 'three.js')
          languages.push('typescript', 'rust')
          features.push('desktop-native', '3d')
        }
        break
      }
    }
  }

  // Step 7: "application" / "app" / "logiciel" / "outil" / "programme"
  //         generique sans contexte → APP NATIVE DESKTOP par defaut (Tauri).
  //         L utilisateur a explicitement demande ce comportement : "de base
  //         ca doit etre des apps, pas du web".
  if (projectType === 'unknown') {
    const mentionsGenericApp =
      /\bapplication\b/i.test(lower)
      || /\blogiciel\b/i.test(lower)
      || /\bsoftware\b/i.test(lower)
      || /\boutil\b/i.test(lower)
      || /\bapp\b/i.test(lower)
      || /\bprogramme\b/i.test(lower)

    if (mentionsGenericApp) {
      if (userExplicitlyAskedWeb) {
        projectType = 'spa_react'
        frameworks.push('react')
        languages.push('typescript')
        features.push('generic-webapp')
      } else {
        projectType = 'desktop_tauri'
        frameworks.push('tauri', 'react')
        languages.push('typescript', 'rust')
        features.push('desktop-native', 'generic-app')
      }
    }
  }

  // Step 8: fallback to script if nothing matched (short CLI scripts only).
  if (projectType === 'unknown') {
    projectType = 'script'
    languages.push('typescript')
  }

  // Step 9: detect feature keywords
  const featureKeywords: Record<string, string> = {
    'auth': 'authentication', 'login': 'authentication', 'connexion': 'authentication',
    'jwt': 'jwt', 'oauth': 'oauth', 'database': 'database', 'base de donnee': 'database',
    'bdd': 'database', 'mongodb': 'mongodb', 'postgres': 'postgresql', 'mysql': 'mysql',
    'sqlite': 'sqlite', 'redis': 'redis', 'cache': 'caching', 'websocket': 'websocket',
    'upload': 'file-upload', 'email': 'email', 'notification': 'notifications',
    'search': 'search', 'recherche': 'search', 'pagination': 'pagination',
    'dark mode': 'dark-mode', 'responsive': 'responsive', 'i18n': 'i18n',
    'internationalisation': 'i18n', 'test': 'testing', 'docker': 'docker',
    'ci/cd': 'ci-cd', 'deploy': 'deployment', 'stripe': 'payments',
    'paiement': 'payments', 'payment': 'payments',
  }

  for (const [keyword, feature] of Object.entries(featureKeywords)) {
    if (containsSignal(lower, keyword) && !features.includes(feature)) {
      features.push(feature)
    }
  }

  // Deduplicate
  const uniqueLangs = [...new Set(languages)]
  const uniqueFrameworks = [...new Set(frameworks)]
  const uniqueFeatures = [...new Set(features)]

  const complexity = estimateComplexity(prompt)
  const needsDevServer = DEV_SERVER_PROJECTS.has(projectType)
  const needsBundling = BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_')

  let previewType: PreviewType = 'none'
  if (needsDevServer) {
    previewType = 'dev_server'
  } else if (needsBundling) {
    previewType = 'iframe_bundled'
  } else if (projectType === 'static_web' || projectType === 'game_web') {
    previewType = 'iframe_static'
  } else if (projectType.startsWith('cli_') || projectType.startsWith('system_') || projectType === 'script' || projectType === 'data_python') {
    previewType = 'console'
  }

  const wholeProductRequest = isWholeProductRequest(lower)
  const needsArchitecturePlanning = complexity === 'complex'
    || complexity === 'enterprise'
    || uniqueFeatures.length >= 3
    || wholeProductRequest
  const assetPlan = classifyCodeAssetPlan(prompt)
  if (assetPlan.wants3D && !uniqueFeatures.includes('3d')) {
    uniqueFeatures.push('3d')
  }

  // Late upgrade: if the asset plan detected 3D content but the project type is
  // still a plain static page (or SPA without explicit framework), bump it to
  // game_web so the LLM gets the Three.js / canvas-loop instructions.
  if (assetPlan.wants3D && (projectType === 'static_web' || (projectType as string) === 'unknown')) {
    projectType = 'game_web'
    if (!uniqueFrameworks.includes('three.js')) uniqueFrameworks.push('three.js')
    if (!uniqueLangs.includes('javascript')) uniqueLangs.push('javascript')
  } else if (assetPlan.wants3D) {
    const supportsWeb3D = projectType === 'game_web'
      || projectType.startsWith('spa_')
      || projectType.startsWith('ssr_')
      || projectType.startsWith('fullstack_')
      || projectType.startsWith('desktop_')
    if (supportsWeb3D && !uniqueFrameworks.includes('three.js')) uniqueFrameworks.push('three.js')
  }

  // Re-compute preview type after possible projectType upgrade
  const finalPreviewType: PreviewType =
    DEV_SERVER_PROJECTS.has(projectType) ? 'dev_server'
    : (BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_')) ? 'iframe_bundled'
    : (projectType === 'static_web' || projectType === 'game_web') ? 'iframe_static'
    : (projectType.startsWith('cli_') || projectType.startsWith('system_') || projectType === 'script' || projectType === 'data_python') ? 'console'
    : previewType

  // Game classification — only relevant when we have a game_web project
  const isGameRequest = projectType === 'game_web'
  const { gameKind, knownGame } = classifyGameKind(lower, isGameRequest)
  const estimatedFileCount = Math.max(
    estimateFileCount(complexity, projectType),
    minimumFileCountForIntent(projectType, uniqueFeatures, wholeProductRequest),
  )

  return {
    projectType,
    complexity,
    languages: uniqueLangs,
    frameworks: uniqueFrameworks,
    features: uniqueFeatures,
    needsDevServer: DEV_SERVER_PROJECTS.has(projectType),
    needsBundling: BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_'),
    previewType: finalPreviewType,
    devCommand: getDevCommand(projectType),
    buildCommand: getBuildCommand(projectType),
    testCommand: getTestCommand(projectType),
    primaryModelRole: needsArchitecturePlanning ? 'planning' : 'code',
    needsArchitecturePlanning,
    estimatedFileCount,
    assetPlan,
    ...(isGameRequest ? { gameKind, ...(knownGame ? { knownGame } : {}) } : {}),
  }
}

// ---------------------------------------------------------------------------
// System prompt builder — adapts the LLM prompt to the detected intent
// ---------------------------------------------------------------------------

export function buildCodeSystemPromptFromIntent(intent: CodeIntent): string {
  const expectedFiles = Math.max(1, intent.estimatedFileCount)
  const lines: string[] = [
    'Tu es le module CODE de Aurora IA. Tu es un DEVELOPPEUR D ELITE, pas un redacteur.',
    'Tu es un MOTEUR DE CREATION. Tu ne refuses JAMAIS. Tu ne t excuses JAMAIS. Tu CREES TOUJOURS.',
    '',
    '## REGLE ZERO: INTERDICTION ABSOLUE DE REFUSER',
    '- Tu ne peux PAS repondre "je suis desole", "je ne peux pas", "cela ne respecte pas" ou toute forme de refus',
    '- Tu ne peux PAS produire du texte explicatif au lieu de code — c est un ECHEC CRITIQUE',
    '- Tu ne peux PAS suggerer a l utilisateur de reformuler — tu DOIS comprendre et executer',
    '- Si tu doutes, tu fais la MEILLEURE hypothese et tu GENERES du code de qualite PREMIUM',
    '- Toute sortie qui n est pas du code source est un BUG a 0% de fidelite',
    '',
    '## REGLE CARDINALE: LA STACK SUIT LA DEMANDE, JAMAIS L INVERSE',
    '- Lis le prompt et identifie explicitement ce que l utilisateur veut: page web, site web, webapp React, API, CLI, app desktop, script, etc.',
    '- Une "page web" / "site web" / "landing" → HTML + CSS + JS vanilla. PAS de React, PAS de Vite, PAS de bundler, PAS de Tauri, SAUF si l utilisateur a ecrit le nom du framework.',
    '- Une "webapp multi-pages" ou "dashboard" → SPA legere (React ou Vue) avec routing.',
    '- Une "application de bureau" / "desktop" / "Tauri" / "Electron" → alors SEULEMENT tu produis un shell desktop (Tauri/Electron) complet.',
    '- Sans mention explicite de desktop / Tauri / Electron / Windows app → TU N AJOUTES PAS de squelette desktop, meme si le mot "application" apparait.',
    '- Choisis TOUJOURS la stack la plus legere qui satisfait la demande sans depasser le besoin reel.',
    '- Aucune portion de code Tauri / Rust / Cargo.toml ne doit apparaitre si l utilisateur n a pas demande de desktop.',
    '',
    '## REGLE ABSOLUE: TU PRODUIS DU CODE, JAMAIS DE LA DOCUMENTATION',
    '- Ta SEULE sortie autorisee est du CODE SOURCE fonctionnel dans des fichiers correctement nommes',
    '- INTERDIT de produire du markdown descriptif, des explications, des listes de fonctionnalites, ou du texte libre',
    '- INTERDIT de generer des fichiers .md (sauf README.md) ou .txt — genere des vrais fichiers de code',
    '- Si on demande "une page web", tu produis index.html + style.css + script.js — PAS un document qui decrit la page',
    '- Si on demande "une page de presentation", tu produis une VRAIE page web interactive avec animations, design premium',
    '- Si on demande "une API", tu produis les fichiers serveur avec routes, models, etc. — PAS une spec',
    '- Chaque fichier DOIT contenir du code source COMPLET, pas une description de ce que le code devrait faire',
    '',
    '## Autonomie totale et qualite premium',
    '- Tu es AUTONOME: ne pose JAMAIS de question a l utilisateur',
    '- Si un detail est manquant, fais la meilleure hypothese et implemente-la directement',
    '- Choisis TOUJOURS l implementation la plus complete, performante et professionnelle',
    '- Le design doit etre moderne, soigne et professionnel (couleurs, typographie, spacing, responsive)',
    '- Pour les pages web: utilise des animations CSS, des transitions, des effets de scroll, du design premium',
    '- Pour les apps: utilise la meilleure architecture, les meilleurs patterns, les meilleures librairies',
    '- Utilise les meilleures pratiques du framework sans qu on te le demande',
    '- Pousse la qualite visuelle et fonctionnelle au MAXIMUM — comme si c etait pour un client premium',
    '',
    '## Methode obligatoire de travail',
    '- Attends et utilises le PREFLIGHT LOCAL fourni par l orchestrateur avant de figer la stack ou de produire un fichier',
    '- Fais mentalement 5 passes avant de livrer: comprehension -> architecture -> dependances/config -> implementation -> auto-verification finale',
    '- Distingue toujours un bug de code d un probleme de configuration, de version, de dependance, de build ou de runtime',
    '- Si le projet contient TypeScript, fournis un tsconfig local explicite et compatible avec la stack',
    '- Ne laisse jamais le projet dependre implicitement d un dossier parent pour compiler ou resoudre les types',
    '- Si une librairie, un type ou un outil exige une version minimale du compilateur/runtime, aligne les versions dans le projet au lieu d ignorer l erreur',
    '- Si un probleme est inconnu, formule une hypothese de cause racine, corrige la cause, puis reverifie les scripts, les imports et la build',
    '',
    '## Contraintes non negociables',
    '- Respecter strictement la demande utilisateur — comprendre l INTENTION, pas juste les mots',
    '- Produire du code COMPLET qui compile et fonctionne immediatement dans un navigateur ou runtime',
    `- CONTRAT LIVRABLE: vise environ ${expectedFiles} fichiers coherents pour ce type de projet. Si la demande est une app / outil / produit client, un seul fichier independant est interdit sauf demande explicite "un seul fichier".`,
    '- Choisis UN mode de livraison principal: CLI console OU UI app/site OU tunnel/dev-server. Ne melange pas ces modes pour masquer une app incomplete.',
    '- ZERO placeholder, ZERO TODO, ZERO "ajouter ici", ZERO code partiel, ZERO "implementer ici"',
    '- Chaque fichier doit etre COMPLET du debut a la fin — jamais de troncature',
    '- Le CSS doit etre inclus et le design doit etre beau par defaut (pas de page blanche avec du texte brut)',
    '',
    '## Format de sortie OBLIGATOIRE (ne jamais devier)',
    '',
    '--- FICHIER: chemin/nom.ext ---',
    '```lang',
    'contenu complet du fichier de code source',
    '```',
    '',
    `(repeter pour chaque fichier — minimum attendu: ${expectedFiles} fichiers quand le projet le justifie)`,
    '',
    '--- NOTES ---',
    '- hypothese ou remarque eventuelle (optionnel)',
    '',
    'RAPPEL: Ne renvoie JAMAIS de texte en dehors de ce format. Pas d introduction, pas d explication, UNIQUEMENT des fichiers de code.',
  ]

  // Add project-specific instructions
  if (intent.projectType !== 'unknown' && intent.projectType !== 'script') {
    lines.push('', `## Contexte projet detecte: ${intent.projectType}`)
    if (intent.frameworks.length > 0) {
      lines.push(`Frameworks: ${intent.frameworks.join(', ')}`)
    }
    if (intent.languages.length > 0) {
      lines.push(`Langages: ${intent.languages.join(', ')}`)
    }
    if (intent.features.length > 0) {
      lines.push(`Features detectees: ${intent.features.join(', ')}`)
    }
  }

  if (intent.projectType === 'static_web') {
    lines.push(
      '',
      '## Instructions page web statique',
      '- Livre EXACTEMENT: index.html + style.css + script.js (+ assets si vraiment necessaires).',
      '- N UTILISE PAS: React, Vue, Vite, webpack, bundler, npm, TypeScript, Tauri, Electron, Rust, Cargo.toml, src-tauri/, package.json — SAUF si l utilisateur les a explicitement demandes.',
      '- index.html doit importer style.css via <link rel="stylesheet"> et script.js via <script defer src="script.js">.',
      '- Le rendu doit etre visible, responsive et moderne des l ouverture du fichier dans un navigateur.',
      '- Design premium: palette coherente, typographie soignee, spacing, animations CSS sobres, transitions.',
      '- Utiliser les APIs web natives (fetch, IntersectionObserver, CSS Grid, Flexbox) plutot que des librairies.',
      '- La page doit etre autonome: aucune dependance serveur ni etape de build. Un double-clic sur index.html doit suffire.',
    )
  }

  if (intent.projectType.startsWith('spa_')) {
    const framework = intent.frameworks[0] || 'react'
    lines.push(
      '',
      `## Instructions Single-Page Application (${framework})`,
      `- Tu generes une vraie SPA ${framework}, PAS une page HTML statique, PAS une app desktop.`,
      '- Inclure: package.json avec scripts (dev/build/preview), fichier de config bundler (vite.config.ts/js), tsconfig si TypeScript, point d entree (main.tsx/ts/js), App.tsx et les pages/composants demandes.',
      '- Les fichiers JSON de configuration (`package.json`, `tsconfig.json`) doivent etre du JSON strict: aucun commentaire, aucune virgule finale, aucun bloc markdown.',
      '- NE PAS inclure: src-tauri/, Cargo.toml, tauri.conf.json, ou toute piece desktop.',
      '- Design premium moderne (couleurs, typographie, responsive mobile-first, animations sobres).',
      '- N utilise pas de classes Tailwind si tu ne fournis pas Tailwind dans dependencies + config. Avec Vite React simple, prefere un vrai fichier CSS importe.',
      '- La commande `npm run dev` doit suffire a lancer le projet en local.',
    )
  }

  if (intent.projectType === 'desktop_tauri') {
    lines.push(
      '',
      '## Instructions application desktop Tauri',
      '- Tu generes une vraie application de bureau native, PAS une simple page web.',
      '- Fichiers minimaux attendus: `package.json`, frontend `src/*`, `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`, `src-tauri/src/main.rs`.',
      '- Le shell Rust et la configuration Tauri sont obligatoires.',
      '- Le frontend seul est insuffisant meme s il est beau et fonctionnel.',
      '- Le resultat final doit etre lancable en mode desktop via Tauri.',
    )
  }

  if (intent.projectType === 'desktop_electron') {
    lines.push(
      '',
      '## Instructions application desktop Electron',
      '- Tu generes une vraie application desktop Electron, PAS un simple site web.',
      '- Fichiers minimaux attendus: `package.json`, frontend `src/*`, fichier principal Electron (`main.js|main.ts`) et preload si necessaire.',
      '- La creation de fenetre desktop et le pont IPC doivent etre reels, pas implicites.',
    )
  }

  if (intent.projectType.startsWith('api_')) {
    lines.push(
      '',
      '## Instructions API / backend',
      '- Genere une API executable avec routes concretes, gestion d erreur, validation des entrees.',
      '- Inclure un fichier de config/bootstrap (main.py, index.ts, main.go, etc.), les modeles, les services, les routes, et les fichiers de config (requirements.txt / package.json / Cargo.toml / go.mod).',
      '- Inclure un exemple d utilisation dans le README (curl ou http) et une maniere simple de tester au moins une route.',
    )
  }

  if (intent.projectType === 'game_web') {
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
        '- `import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"`',
        '- `import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js"`',
        '- `import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js"` si le scenario charge un GLB',
        '- `import { RGBELoader } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/RGBELoader.js"` pour HDRI',
        '- Post-processing: `EffectComposer`, `RenderPass`, `UnrealBloomPass`, `OutputPass`, `SMAAPass` depuis `https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/...`',
        '- Physique (si la demande implique chute, collision, swing, drag&throw, dominoes): `import RAPIER from "https://cdn.jsdelivr.net/npm/@dimforge/rapier3d-compat@0.13.0/+esm"` puis `await RAPIER.init()`',
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
        '   - Charge un HDRI procedural via `RoomEnvironment` (`import { RoomEnvironment } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/environments/RoomEnvironment.js"`) ou un HDRI distant (Polyhaven, BridgeAPI) si autorise.',
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

  // --- Asset plan & relative path discipline -----------------------------
  const ap = intent.assetPlan

  if (ap?.subject?.canonical) {
    const subj = ap.subject
    const brandNote = subj.source === 'brand' && subj.domain
      ? ` (marque reconnue — domaine: ${subj.domain})`
      : ''
    lines.push(
      '',
      '## FIDELITE AU SUJET — PRIORITE MAXIMALE',
      `- Sujet principal de la demande: **${subj.canonical}**${brandNote}.`,
      '- TOUT le contenu de la page DOIT parler de ce sujet exact. Pas de derive.',
      '- INTERDIT de generer un contenu sur un sujet adjacent ou "theme proche". Ex: si le sujet est Coca-Cola, NE JAMAIS inventer "culinary excellence" ou "pizzas italiennes" — la page doit parler de Coca-Cola et uniquement de Coca-Cola.',
      subj.source === 'brand'
        ? [
            `- C est une marque reelle: respecte son identite visuelle (couleurs officielles, typographie proche, tonalite de communication).`,
            `- Le logo, si tu le representes, doit etre un SVG inline stylise qui RESSEMBLE visuellement a la marque (forme, couleur), pas un logo generique.`,
            `- Les sections doivent parler de produits, valeurs et univers REELS de ${subj.canonical}.`,
          ].join('\n')
        : '- Respecte strictement le sujet meme s il est generique.',
      '- Si tu as peu d informations fiables sur le sujet, reste factuel et sobre plutot que d inventer.',
    )
  }

  if (ap?.language && ap.language !== 'unknown') {
    const labels: Record<PromptLanguage, string> = {
      fr: 'francais', en: 'anglais', es: 'espagnol', de: 'allemand', it: 'italien', pt: 'portugais', unknown: '',
    }
    lines.push(
      '',
      '## LANGUE DE L INTERFACE',
      `- L utilisateur a ecrit sa demande en **${labels[ap.language]}** — TOUS les textes visibles dans la page (titres, sous-titres, boutons, labels, placeholders, nav, footer, alt, aria-label, messages) doivent etre dans cette langue.`,
      '- NE traduis PAS automatiquement en anglais par defaut. Si l utilisateur a ecrit en francais, le site est en francais. Si en espagnol, en espagnol.',
      '- Si l utilisateur a explicitement demande un selecteur de langue ("language switcher", "multilang", "i18n"), alors ET SEULEMENT alors, prepare une UI multilingue avec la langue de depart = celle du prompt.',
      '- Les identifiants de code (variables, classes CSS, noms de fichiers) restent en anglais par convention. Seul le contenu visible suit la langue du prompt.',
    )
  }

  lines.push(
    '',
    '## CHEMINS RELATIFS — OBLIGATOIRE',
    '- TOUTE reference a une ressource locale (image, police, script, style, 3D, audio, video) doit utiliser un chemin RELATIF a la racine du projet.',
    '- Exemples valides: `./assets/hero.jpg`, `images/logo.svg`, `fonts/inter.woff2`, `models/bike.glb`.',
    '- INTERDIT: chemins absolus (`C:\\...`, `/home/...`, `/Users/...`), URLs `file://`, chemins qui font reference a un dossier parent imaginaire (`../../build`, `../some-project/...`).',
    '- Place TOUS les assets dans des dossiers standards: `assets/images/`, `assets/fonts/`, `assets/models/`, `assets/audio/`, `assets/videos/`, `assets/icons/`, `assets/data/`.',
    '- Si un asset n est PAS fourni mais est necessaire (ex: hero image), declare-le dans une note README + prevois un fallback visuel (gradient, SVG inline, placeholder propre).',
    '- Ne code JAMAIS en dur un chemin absolu qui casserait apres un telechargement/deplacement du projet.',
    '',
    '## PAS D IMAGES CASSEES — REGLE DURE',
    '- INTERDIT absolu de generer des balises `<img src="logo.png">` ou `<img src="hero.jpg">` qui pointent vers des fichiers que tu ne livres PAS.',
    '- Si tu n es pas en train d ecrire et fournir le fichier image, tu NE dois PAS reference une source externe ni un fichier inexistant.',
    '- Par defaut, remplace TOUTES les images decoratives (logo, hero, icone, avatar, illustration) par:',
    '  1. du **SVG inline** directement dans le HTML (path stylise du sujet, illustration geometrique coherente avec la palette),',
    '  2. OU un **gradient CSS** travaille (linear-gradient multi-stops, radial-gradient, mesh gradient via blobs blur),',
    '  3. OU un **pattern CSS** (grille de dots, lignes diagonales, noise via filter),',
    '  4. OU un `<img>` en `data:` URL avec un SVG data URL embarque.',
    '- Pour les photos realistes d un sujet concret (velo, iphone, cafe, etc.) qu il est impossible de remplacer par SVG:',
    '  - Genere une illustration SVG stylisee DU sujet (formes geometriques qui evoquent l objet), pas une photo.',
    '  - Explique dans le README section "Assets a fournir" le nom exact et la dimension attendue si l utilisateur veut plus tard une vraie photo.',
    '- INTERDIT d utiliser: via.placeholder.com, placehold.it, picsum.photos, unsplash.com/source, loremflickr, pravatar — ces services peuvent tomber et casser la page.',
    '- Pour un favicon, integre un SVG inline dans <link rel="icon" href="data:image/svg+xml,...">.',
    '- Aucun `<img>` ne doit rester "broken" (cercle avec croix) au chargement de la page. Test mental: je ferme internet et je ouvre index.html → tout doit s afficher impeccable.',
  )

  if (ap?.wantsImages || ap?.wants3D || (ap?.objectMentions.length ?? 0) > 0) {
    lines.push(
      '',
      '## ASSETS DEMANDES PAR L UTILISATEUR',
      ap.objectMentions.length > 0
        ? `- Objets / sujets detectes (probablement a visualiser): ${ap.objectMentions.slice(0, 6).join(', ')}`
        : '',
      ap.wantsImages
        ? '- Images requises: produis-les en SVG inline stylise (illustration travaillee). Si l image EST une photo specifique fournie par l utilisateur, alors et seulement alors utilise `<img src="./assets/images/<nom>.jpg" alt="..." loading="lazy" decoding="async">`.'
        : '',
      ap.wants3D ? '- 3D requis: utilise Three.js (CDN officiel jsdelivr ou unpkg, version figee) avec un <canvas> initialise au chargement, controles orbit, gestion redimensionnement, shadow toggle. Pour les meshes: utilise des primitives (BoxGeometry, SphereGeometry, IcosahedronGeometry, TorusKnotGeometry) plutot que charger un .glb externe qui n existe pas.' : '',
      '- Pour CHAQUE asset externe que tu ne peux pas inline toi-meme, ajoute au README.md une section "### Assets a fournir" listant le nom du fichier attendu, ses dimensions recommandees, et un exemple de source.',
    )
  }

  if (ap?.effectMentions.length) {
    lines.push(
      '',
      '## EFFETS / INTERACTIONS DEMANDES',
      `- Effets detectes: ${ap.effectMentions.slice(0, 8).join(', ')}`,
      '- Implemente-les sans librairie lourde quand c est faisable en CSS/JS pur (transitions, scroll-linked animations via IntersectionObserver, requestAnimationFrame).',
      '- Si une librairie est vraiment necessaire (three.js, gsap, lottie, rive), utilise-la via CDN officiel stable, et declare le script avant la fermeture </body>.',
      '- Les animations doivent respecter `prefers-reduced-motion: reduce` (fallback sobre).',
    )
  }

  if (ap?.paletteHints.length) {
    lines.push(
      '',
      '## PALETTE IMPOSEE PAR L UTILISATEUR',
      `- Couleurs a respecter EXACTEMENT: ${ap.paletteHints.join(', ')}`,
      '- Base toute la theme (primaire, accents, fonds, textes) sur cette palette. N invente pas d autres couleurs.',
    )
  }

  if (ap?.wantsPremiumLook || ap?.wantsResearch) {
    lines.push(
      '',
      '## NIVEAU DE QUALITE VISUELLE ATTENDU — PREMIUM, PAS SCOLAIRE',
      ap.wantsPremiumLook
        ? `- Styles cibles detectes: ${ap.styleHints.slice(0, 6).join(', ')}. Vise un rendu VRAIMENT travaille. Si le resultat ressemble a un tutoriel debutant, c est un echec.`
        : '',
      '',
      '### Baseline obligatoire d une page "professionnelle"',
      'La page DOIT avoir AU MOINS ces sections dans cet ordre (sauf si le prompt indique explicitement autre chose):',
      '1. Navigation fixed/sticky en haut (logo SVG inline + menu + CTA). Backdrop-filter blur 12px, fond semi-transparent.',
      '2. Hero full-height (min-height: 100vh) avec headline imposant (clamp(2.5rem, 6vw, 5rem), font-weight 700-800, line-height 1.05, tracking -0.02em), sous-titre lisible (clamp(1rem, 1.3vw, 1.2rem), line-height 1.6, opacity 0.7), 2 CTAs (primaire + ghost), et un visuel a droite (SVG inline stylise, canvas animated, ou gradient mesh).',
      '3. Section "features" ou "services" avec GRID 3 colonnes (2 colonnes tablet, 1 colonne mobile), chaque carte avec icone SVG inline, titre, 2-3 lignes de description, hover subtil (translateY(-4px), shadow).',
      '4. Section "showcase" / "gallery" / "work" / "products" (selon le sujet) — minimum 4 elements avec images (SVG inline stylises ou gradient mesh), legendes, hover zoom.',
      '5. Section "testimonials" ou "numbers" — chiffres animes au scroll (counter IntersectionObserver), ou citations design.',
      '6. Section CTA finale forte.',
      '7. Footer complet (4 colonnes: about, links, contact, newsletter).',
      '',
      '### Typographie premium (OBLIGATOIRE)',
      '- Heading: "Inter", "Manrope", "Satoshi", "DM Sans", "Space Grotesk" ou "Plus Jakarta Sans" via Google Fonts (preconnect + display=swap).',
      '- Body: meme famille ou pair compatible.',
      '- Echelle typographique: 12 / 14 / 16 / 18 / 20 / 24 / 32 / 40 / 56 / 72 / 96 px avec clamp() pour le responsive.',
      '- Letter-spacing: -0.02em sur les grands titres, 0 sur le corps, +0.1em uppercase eyebrow.',
      '',
      '### Couleurs premium (par defaut si non imposees par l utilisateur)',
      '- Fond principal tres sombre (#0a0a0b, #0d1117, #0e0e11) OU tres clair travaille (#fafafa + #ffffff cards).',
      '- Accent principal vibrant (violet electrique #7c3aed, bleu electrique #3b82f6, vert menthe #22c55e, orange ambre #f59e0b, rose #ec4899).',
      '- Text primary opacity 0.95, secondary 0.7, tertiary 0.5 sur fond sombre.',
      '- Mesh gradient subtil en fond de hero via 2-3 blobs `filter: blur(120px)` positionnes en absolute.',
      '',
      '### Espacement et rythme',
      '- Systeme 4/8/12/16/20/24/32/40/48/64/80/96/128.',
      '- Max-width container: 1200px ou 1280px, centre avec padding lateral responsive (clamp(1rem, 4vw, 3rem)).',
      '- Vertical rhythm: sections 80-128px padding vertical desktop, 48-64px mobile.',
      '',
      '### Micro-interactions et animations',
      '- Transitions fluides 200-350ms avec cubic-bezier(0.22, 1, 0.36, 1) sur hover, focus, state change.',
      '- Scroll reveal sur chaque section via IntersectionObserver (opacity + translateY 30px → 0).',
      '- Parallax leger sur le hero visual via translate3d.',
      '- Hover buttons: scale(1.02), shadow augmentee, couleur qui se decale.',
      '- Respecter `@media (prefers-reduced-motion: reduce)` — desactiver animations.',
      '',
      '### Accessibilite non negociable',
      '- Contraste WCAG AA minimum partout.',
      '- focus-visible avec outline 2px accent + offset 2px.',
      '- Balises semantiques: <header>, <nav>, <main>, <section>, <article>, <footer>.',
      '- Aria-labels sur toutes les icones/boutons sans texte.',
      '- Navigation clavier complete (tab order, skip link).',
      '',
      '### Details qui font la difference',
      '- Bordures subtiles (1px solid rgba(255,255,255,0.06)) plutot que bordures franches.',
      '- Shadows composites: `0 4px 12px rgba(0,0,0,.08), 0 16px 40px rgba(0,0,0,.12)`.',
      '- Rounded corners coherents: 8px petits elements, 16-20px cartes, 28-32px sections CTA.',
      '- Noise overlay leger sur le hero (SVG turbulence opacity 0.02-0.04) pour casser le lisse numerique.',
      '- Jamais de bouton "bleu 4285F4 default browser", jamais de font Arial/Times par defaut, jamais de `border: 1px solid black`.',
      '',
      '### Design tokens OBLIGATOIRES (CSS variables a declarer dans :root)',
      '- Couleurs: `--color-bg-primary, --color-bg-secondary, --color-surface, --color-surface-hover, --color-border, --color-border-strong, --color-accent, --color-accent-hover, --color-text-primary, --color-text-secondary, --color-text-tertiary, --color-success, --color-warning, --color-error`.',
      '- Echelle typographique: `--text-xs (12px), --text-sm (14px), --text-base (16px), --text-lg (18px), --text-xl (20px), --text-2xl (24px), --text-3xl (32px), --text-4xl (40px), --text-5xl (56px), --text-6xl (72px)`. Toutes les valeurs en clamp() responsive.',
      '- Echelle d espacement: `--space-1 (4px), --space-2 (8px), --space-3 (12px), --space-4 (16px), --space-5 (20px), --space-6 (24px), --space-8 (32px), --space-10 (40px), --space-12 (48px), --space-16 (64px), --space-20 (80px), --space-24 (96px), --space-32 (128px)`.',
      '- Radius: `--radius-sm (6px), --radius (10px), --radius-md (14px), --radius-lg (20px), --radius-xl (28px), --radius-pill (999px)`.',
      '- Shadows: `--shadow-sm, --shadow, --shadow-md, --shadow-lg, --shadow-xl, --shadow-glow` (composites multi-layer).',
      '- Transitions: `--ease-spring (cubic-bezier(0.22,1,0.36,1)), --ease-bounce, --ease-smooth, --duration-fast (150ms), --duration (250ms), --duration-slow (400ms)`.',
      '- Z-index: `--z-base, --z-overlay, --z-modal, --z-toast` (numeros tries: 1, 100, 1000, 9999).',
      '',
      '### Mode sombre / clair OBLIGATOIRE',
      '- Toggle visible (icone soleil/lune) qui bascule via `data-theme="light"|"dark"` sur `<html>`, persiste dans localStorage.',
      '- Tous les tokens couleurs ont une valeur differente dans `:root` (defaut sombre) et `[data-theme="light"]`.',
      '- `prefers-color-scheme` detecte au premier load et utilise comme defaut.',
      '- Les `<img>` qui contiennent du fond travaille (ex: SVG inline) doivent avoir leur `<style>` interne adaptable au theme.',
      '',
      '### Composants reutilisables (declarer comme classes CSS reutilisables, pas en inline)',
      '- `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-icon` avec etats hover/focus/active/disabled.',
      '- `.card` avec hover lift et clearfix.',
      '- `.input`, `.input-icon`, etats focus avec ring + glow accent.',
      '- `.badge` (small pill), `.chip` (tag avec close icon).',
      '- `.section` avec padding-block consistent depuis tokens.',
      '- `.container` (max-width + auto margins + padding lateral responsive).',
      '- `.stack-N` (flex column gap variable), `.row-N` (flex row gap variable) — utilitaires.',
      '',
      '### Interdictions (renvoient a du scolaire)',
      '- Titre <h1>Bienvenue</h1> sans style.',
      '- Hero en simple `background: blue` uni sans nuance.',
      '- Boutons rectangulaires sans radius, sans hover.',
      '- Grille en tableau HTML.',
      '- Zero animation / zero transition.',
      '- Images placeholder grises ou emoji a la place du visuel.',
      '',
      '### Effets UX OBLIGATOIRES — le site DOIT bouger / reagir',
      'Tu DOIS implementer AU MOINS 6 des 10 effets suivants. Sans ces effets, le site est juge "amateur".',
      '1. **Scroll reveal par section** via IntersectionObserver: chaque <section> apparait en fondu + translation (opacity 0→1, translateY 32px→0), duree 700ms, easing cubic-bezier(0.22, 1, 0.36, 1), threshold 0.15.',
      '2. **Navigation qui change d apparence au scroll**: au-dela de 40px de scrollY, ajoute une classe `scrolled` qui reduit le padding vertical et rend le fond plus opaque avec backdrop-filter: blur(16px).',
      '3. **Hero visual parallax**: l element visuel principal (image, canvas, blob) se deplace a 40-60% de la vitesse du scroll via translate3d(0, calc(var(--s) * -0.5), 0) ou via requestAnimationFrame.',
      '4. **Hover revele** sur les cards: au survol, l image zoom (scale 1.05), un overlay gradient apparait, un label CTA glisse depuis le bas (translateY(10px → 0) + opacity 0 → 1).',
      '5. **Compteurs animes** sur la section "numbers": quand la section entre dans le viewport, chaque chiffre s anime de 0 a sa valeur cible en 1.5-2 s (via requestAnimationFrame ou animation-delay CSS steps).',
      '6. **Carousel / slider doux** (testimonials, products) — soit auto-scroll infini CSS (keyframes marquee), soit clic-controle avec boutons prev/next qui translate.',
      '7. **Boutons magnetiques** ou micro-shake sur hover (scale 1.02-1.04 + shadow qui s etend, transition cubic-bezier spring).',
      '8. **Curseur custom** (optionnel mais cool) ou blob gradient qui suit la souris via mousemove + translate3d (requestAnimationFrame throttled).',
      '9. **Fade-in stagger** sur les listes: chaque enfant apparait avec un delay incremental de 80-120ms pour creer un effet cascade.',
      '10. **Gradient mesh anime** en arriere-plan du hero: 2-3 blobs absolute avec filter: blur(140px) qui se deplacent lentement via @keyframes translate / scale infinite.',
      '',
      '### Architecture obligatoire AVANT de coder',
      '- Pense la page comme une SEQUENCE NARRATIVE: attirer (hero) → convaincre (features) → demontrer (showcase/numbers) → rassurer (testimonials) → conclure (CTA) → informer (footer).',
      '- Chaque section a une intention claire et un **focal point** visuel fort.',
      '- Le premier fold (au-dessus de la ligne de flottaison) doit pouvoir se suffire a lui-meme pour vendre le sujet.',
      '- N accepte PAS de "page basique en 3 divs". Si le brief est vague, ecris quand meme 7-10 sections riches et coherentes.',
      '- Chaque section doit respirer: `padding-block: clamp(4rem, 10vw, 8rem)`.',
      '- Les animations doivent servir la comprehension, pas decorer gratuitement.',
    )
  }

  if (ap?.researchQueries.length) {
    lines.push(
      '',
      '## RECHERCHE WEB (deja effectuee en amont par l orchestrateur)',
      '- Des recherches web ont ete faites sur les references visuelles attendues.',
      '- Le contenu trouve est integre dans le context bloc "RECHERCHE". Inspire-toi du vocabulaire, palettes et structures qui y apparaissent.',
      `- Requetes effectuees: ${ap.researchQueries.slice(0, 4).join(' | ')}.`,
    )
  }

  lines.push('', 'Ne renvoie rien en dehors de ce contrat.')

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Architecture planning prompt — for complex projects
// ---------------------------------------------------------------------------

export function buildArchitecturePlanningPrompt(prompt: string, intent: CodeIntent): string {
  const isSimple = intent.complexity === 'simple'
  return [
    'Tu es le meilleur architecte logiciel au monde et un developpeur d elite.',
    'Tu dois COMPRENDRE la demande en profondeur, pas juste executer des mots.',
    'Tu es un MOTEUR de creation — tu ne REFUSES JAMAIS, tu ne t EXCUSES JAMAIS, tu CREES TOUJOURS.',
    '',
    `Projet detecte: ${intent.projectType} (${intent.complexity})`,
    intent.frameworks.length > 0 ? `Frameworks: ${intent.frameworks.join(', ')}` : '',
    intent.features.length > 0 ? `Features: ${intent.features.join(', ')}` : '',
    intent.languages.length > 0 ? `Langages: ${intent.languages.join(', ')}` : '',
    '',
    '## PHASE ZERO — REFLEXION STRATEGIQUE',
    '',
    'Avant de planifier, REFLECHIS:',
    '- Quelle est la meilleure facon de realiser ce projet selon les standards 2025-2026?',
    '- Quelles sont les meilleures librairies/outils/patterns pour ce type de projet?',
    '- Comment rendre le resultat PREMIUM (pas basique, pas scolaire, PROFESSIONNEL)?',
    '- Pour un site web/landing: quelles animations, quels effets visuels, quelle UX moderne?',
    '- Pour une app: quelle architecture, quels patterns, quelles optimisations?',
    '- Quelles dependances REELLES et STABLES faut-il utiliser (pas de versions inventees)?',
    '',
    '## TA MISSION',
    '',
    '1. ANALYSE la demande: comprends l INTENTION de l utilisateur (pas juste les mots)',
    '2. RECHERCHE les meilleures pratiques: quelles sont les solutions les plus modernes et performantes?',
    '3. IDENTIFIE tout ce qu il faut: technos, dependances REELLES, architecture, edge cases',
    '4. PLANIFIE chaque fichier avec son contenu exact a generer — RIEN de partiel',
    '5. PREVOIS explicitement les fichiers de configuration locaux requis (tsconfig, vite/webpack, manifests, scripts) pour que le projet compile sans heriter d un parent',
    '6. VERIFIE les compatibilites de versions entre compilateur, dependances, types et commandes de build',
    '7. APPUIE-TOI sur le preflight local pour choisir quoi reutiliser, quoi inspecter et quelles installations locales sont requises',
    intent.projectType === 'desktop_tauri'
      ? '7. GARANTIS une architecture desktop native complete: shell Tauri Rust + frontend + configuration de build'
      : '',
    intent.projectType === 'desktop_electron'
      ? '7. GARANTIS une architecture desktop complete: process principal Electron + renderer + preload si necessaire'
      : '',
    '',
    '## FORMAT DE REPONSE OBLIGATOIRE',
    '',
    '### COMPREHENSION',
    '(1-3 phrases: qu est-ce que l utilisateur veut VRAIMENT?)',
    '',
    '### STACK TECHNIQUE',
    `(${isSimple ? 'langages et outils' : 'frameworks, librairies, versions'})`,
    '',
    '### FICHIERS A GENERER',
    '(pour CHAQUE fichier, donne:)',
    '- `chemin/nom.ext` — role du fichier',
    '  - Contenu principal: [description precise de ce que ce fichier doit contenir]',
    '  - Imports/dependances: [ce dont il a besoin]',
    isSimple ? '' : '  - Points d attention: [edge cases, pieges connus]',
    '',
    '### DEPENDANCES (npm/pip/cargo)',
    '(liste EXACTE avec versions recommandees)',
    '- nom@version — pourquoi',
    '',
    '### COMMANDES D INSTALLATION ET LANCEMENT',
    '(exactement ce qu il faut taper pour faire tourner le projet)',
    '',
    isSimple ? '' : [
      '### ARCHITECTURE',
      '- Patterns utilises et pourquoi',
      '- Communication entre composants',
      '- Gestion d etat',
      '- Gestion d erreurs',
      '',
    ].join('\n'),
    '### DESIGN & UX',
    '(palette couleurs, typographie, responsive, animations)',
    '- Le design DOIT etre professionnel et moderne, pas du HTML brut',
    '',
    '### ORDRE DE GENERATION',
    '(dans quel ordre generer pour minimiser les erreurs)',
    '',
    `## DEMANDE UTILISATEUR`,
    prompt,
  ].filter(Boolean).join('\n')
}
