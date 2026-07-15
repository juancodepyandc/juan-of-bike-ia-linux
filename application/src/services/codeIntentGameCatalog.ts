// ---------------------------------------------------------------------------
// Known game catalogue
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { GameKind, KnownGameEntry } from './codeIntentTypes.ts'
import { containsSignal } from './codeIntentSignalUtils.ts'

export type KnownGameDef = KnownGameEntry & { tokens: string[] }

export const KNOWN_GAMES: KnownGameDef[] = [
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
export function detectKnownGame(lower: string): KnownGameDef | null {
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
export function classifyGameKind(lower: string, isGameRequest: boolean): {
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
