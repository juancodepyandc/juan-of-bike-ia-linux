/**
 * Pure utility: detect known game clones vs creative game requests.
 * No external dependencies — fully testable in Node.js.
 */

export type GameKind =
  | 'clone'     // Recreate a known game exactly
  | 'creative'  // Invent something original
  | 'generic'   // Generic game request without enough detail to classify

export type KnownGameEntry = {
  canonical: string
  genre: string
  coreMechanics: string[]
  visualStyle: string
  controls: string
  winLoseCondition: string
}

type KnownGameDef = KnownGameEntry & { tokens: string[] }

function normalizeSignalText(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function containsSignal(source: string, signal: string): boolean {
  const normalizedSignal = normalizeSignalText(signal).trim()
  if (!normalizedSignal) return false
  const pattern = escapeRegex(normalizedSignal).replace(/\s+/g, '\\s+')
  return new RegExp(`(^|[^a-z0-9])${pattern}(?=[^a-z0-9]|$)`, 'i').test(source)
}

export const KNOWN_GAMES: KnownGameDef[] = [
  {
    canonical: 'Snake',
    tokens: ['snake', 'serpent', 'jeu du serpent', 'snake game'],
    genre: '2D arcade',
    coreMechanics: [
      'Grille de cellules (20×20 minimum). Le serpent se deplace case par case a intervalle fixe (150-200 ms).',
      'Collision avec les murs ou avec son propre corps = game over.',
    ],
    visualStyle: 'Dark background (#1a1a2e), serpent en gradient vert, pomme rouge neon.',
    controls: 'Fleches directionnelles ou WASD. Barre espace = pause.',
    winLoseCondition: 'Pas de condition de victoire. Game over sur collision.',
  },
  {
    canonical: 'Tetris',
    tokens: ['tetris', 'tetromino', 'jeu de tetris', 'tetris like', 'tetris-like'],
    genre: '2D puzzle',
    coreMechanics: [
      'Plateau 10 colonnes × 20 rangees. Les tetrominoes tombent.',
      'Quand une rangee est complete, elle est effacee.',
    ],
    visualStyle: 'Fond sombre, chaque tetromino a une couleur vive distincte.',
    controls: 'Fleches: gauche/droite/bas. Haut: rotation. Espace: hard drop.',
    winLoseCondition: 'Game over quand les pieces atteignent le haut.',
  },
  {
    canonical: 'Flappy Bird',
    tokens: ['flappy', 'flappy bird', 'flappy bird like', 'oiseau volant', 'pipe bird'],
    genre: '2D endless arcade',
    coreMechanics: [
      'Un personnage tombe sous la gravite. Clic = impulsion vers le haut.',
      'Collision avec un tuyau = game over.',
    ],
    visualStyle: 'Ciel degrade, tuyaux verts, oiseau anime.',
    controls: 'Clic gauche / touche espace / tap tactile = flap.',
    winLoseCondition: 'Score = tuyaux traverses. Game over sur collision.',
  },
  {
    canonical: 'Pong',
    tokens: ['pong', 'jeu de pong', 'ping pong', 'tennis game', 'bat ball game'],
    genre: '2D arcade',
    coreMechanics: [
      'Deux raquettes et une balle rebondissante.',
      'Premiere equipe a 7 points gagne.',
    ],
    visualStyle: 'Fond noir pur, raquettes et balle blanches, style retro CRT.',
    controls: 'Joueur 1: W/S. Joueur 2 (ou IA): fleches haut/bas.',
    winLoseCondition: '7 points pour gagner.',
  },
  {
    canonical: 'Breakout / Arkanoid',
    tokens: ['breakout', 'arkanoid', 'casse-briques', 'casse briques', 'brick breaker', 'brick game', 'brique'],
    genre: '2D arcade',
    coreMechanics: [
      'Grille de briques. Une balle rebondit et une raquette en bas se deplace.',
      'Quand la balle touche une brique, elle disparait.',
    ],
    visualStyle: 'Fond sombre spatial, briques colorees, lueur neon sur la balle.',
    controls: 'Raquette: fleches ou souris. Espace: lancer la balle.',
    winLoseCondition: 'Victoire: toutes les briques detruites. Defaite: 0 vies.',
  },
  {
    canonical: 'Pac-Man',
    tokens: ['pacman', 'pac-man', 'pac man', 'labyrinthe pacman', 'fantome labyrinthe'],
    genre: '2D maze arcade',
    coreMechanics: [
      'Labyrinthe fixe. Pac-Man mange des pac-dots, evite des fantomes.',
      'Pilule energisante = fantomes comestibles pendant 8 secondes.',
    ],
    visualStyle: 'Fond noir, labyrinthe bleu electrique, Pac-Man jaune.',
    controls: 'Fleches directionnelles ou WASD.',
    winLoseCondition: 'Manger tous les pac-dots. 0 vies = game over.',
  },
  {
    canonical: 'Space Invaders',
    tokens: ['space invaders', 'space invader', 'invaders', 'alien shooter', 'alien invaders', 'envahisseurs'],
    genre: '2D shoot em up',
    coreMechanics: [
      'Grille d aliens qui descendent. Le joueur tire vers le haut.',
      'Aliens atteignant le bas = game over.',
    ],
    visualStyle: 'Fond noir etoile, aliens pixelises, canons verts.',
    controls: 'Fleches gauche/droite: deplacement. Espace: tir.',
    winLoseCondition: 'Tous les aliens tues = niveau suivant. 0 vies = game over.',
  },
  {
    canonical: 'Asteroids',
    tokens: ['asteroids', 'asteroide', 'asteroides', 'jeu asteroids', 'vaisseau asteroide'],
    genre: '2D arcade spatial',
    coreMechanics: [
      'Vaisseau triangulaire avec physique newtonienne. Asteroides se cassent en plus petits.',
      'Collision = perte d une vie.',
    ],
    visualStyle: 'Fond noir, vecteurs blancs minimalistes, style wireframe.',
    controls: 'Fleches: rotation/poussee. Espace: tir.',
    winLoseCondition: '0 vies = game over. Progression infinie par niveaux.',
  },
  {
    canonical: 'Chrome Dino / Endless Runner',
    tokens: ['dino', 'dinosaure', 'chrome dino', 'endless runner', 'runner infini', 'saut obstacle', 'run game', 'jeu de course infini'],
    genre: '2D endless runner',
    coreMechanics: [
      'Personnage court automatiquement. Saut pour eviter les obstacles.',
      'Collision = game over.',
    ],
    visualStyle: 'Pixel art minimaliste. Palette gris/beige, sols textures.',
    controls: 'Espace / fleche haut / clic = saut. Fleche bas = accroupi.',
    winLoseCondition: 'Score infini. Game over sur collision.',
  },
  {
    canonical: '2048',
    tokens: ['2048', 'jeu 2048', '2048 like', 'merge tiles', 'fusion de cases', 'fusion tuiles'],
    genre: '2D puzzle',
    coreMechanics: [
      'Grille 4x4. Tuiles glissent et fusionnent si identiques.',
      'Atteindre 2048 = victoire. Grille pleine sans fusion = game over.',
    ],
    visualStyle: 'Fond beige clair, tuiles arrondies avec couleur progressive.',
    controls: 'Fleches directionnelles ou swipe tactile.',
    winLoseCondition: 'Victoire: tuile 2048. Defaite: grille pleine sans fusion.',
  },
  {
    canonical: 'Minesweeper / Demineur',
    tokens: ['demineur', 'démineur', 'minesweeper', 'mine sweeper', 'jeu de mines', 'champ de mines'],
    genre: '2D logic puzzle',
    coreMechanics: [
      'Grille cachee avec mines. Clic gauche = revele. Clic droit = drapeau.',
      'Reveler une mine = game over.',
    ],
    visualStyle: 'Style Windows XP retro ou design moderne plat.',
    controls: 'Clic gauche: reveler. Clic droit: drapeau.',
    winLoseCondition: 'Victoire: toutes les cases sures revelees. Defaite: mine revelee.',
  },
  {
    canonical: 'Tower Defense',
    tokens: ['tower defense', 'tower defence', 'defense de tour', 'défense de tour', 'td game', 'jeu de defense', 'jeu td'],
    genre: '2D strategy',
    coreMechanics: [
      'Chemin sinueux avec vagues d ennemis. Placement de tours pour les eliminer.',
      'Ennemis passants = perte de PV. 0 PV = game over.',
    ],
    visualStyle: 'Vue de dessus, chemin texture, tours avec modeles distincts.',
    controls: 'Clic: selectionner et placer une tour. Bouton: lancer la vague.',
    winLoseCondition: 'Survivre a toutes les vagues. 0 PV de base = game over.',
  },
  {
    canonical: 'Platformer 2D',
    tokens: ['platformer', 'plateformer', 'jeu de plateforme', 'jeu platformer', 'mario like', 'mario-like', 'saut plateforme', 'platforme 2d'],
    genre: '2D platformer',
    coreMechanics: [
      'Personnage avec physique: gravite, saut variable, coyote time.',
      'Plateformes, ennemis, collectibles, niveaux.',
    ],
    visualStyle: 'Pixel art 16x16 ou 32x32, palette coloree par biome.',
    controls: 'WASD ou fleches: deplacement. Espace: saut.',
    winLoseCondition: 'Atteindre la sortie de chaque niveau. 0 vies = game over.',
  },
]

export function detectKnownGame(lower: string): KnownGameDef | null {
  for (const entry of KNOWN_GAMES) {
    for (const token of entry.tokens) {
      if (containsSignal(lower, token)) return entry
    }
  }
  return null
}

const CREATIVE_SIGNALS = [
  'original', 'unique', 'invente', 'inventé', 'innovant', 'nouveau concept',
  'de ma propre idée', 'mon idée', 'mon concept', 'de mon invention',
  'creatif', 'créatif', 'creative', 'jamais vu', 'inédit', 'inedit',
  'inspiré de', 'inspire de', 'fusion de', 'melange de', 'mélange de',
  'avec une touche de', 'un genre', 'un jeu ou', 'un jeu qui',
]

export function classifyGameKind(
  lower: string,
  isGameRequest: boolean,
): { gameKind: GameKind; knownGame: KnownGameDef | null } {
  if (!isGameRequest) return { gameKind: 'generic', knownGame: null }

  const known = detectKnownGame(lower)
  if (known) return { gameKind: 'clone', knownGame: known }

  const isCreativeRequest =
    CREATIVE_SIGNALS.some((s) => lower.includes(s))
    || lower.split(/\s+/).length > 12

  return { gameKind: isCreativeRequest ? 'creative' : 'generic', knownGame: null }
}
