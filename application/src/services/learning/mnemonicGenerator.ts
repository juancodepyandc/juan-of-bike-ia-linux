// Générateur de mnémotechniques. 4 stratégies :
//
//   1. Acronyme : "Mon Vieux Tu M'As Servi Une Pizza Nutella" → Mercure
//      Vénus Terre Mars Saturne Uranus Pluton Neptune (planètes).
//   2. Phrase initiale : la première lettre de chaque mot d'une phrase
//      mémorable forme la séquence.
//   3. Méthode des loci : associe chaque item à un emplacement physique
//      familier.
//   4. Chunking par groupes : découpe une liste longue en groupes de 3-4.
//
// Module pur. Utilise un dictionnaire FR léger pour proposer des mots de
// remplacement quand l'initiale est rare.

export type MnemonicStrategy = 'acronyme' | 'phrase-initiale' | 'loci' | 'chunking' | 'rime'

export type MnemonicResult = {
  strategy: MnemonicStrategy
  text: string
  /** Termes originaux ordonnés. */
  items: string[]
  /** Difficulté à mémoriser estimée [0..1] (plus bas = plus facile). */
  difficulty: number
  /** Notes explicatives. */
  notes: string[]
}

/** Mots FR usuels par initiale, sélectionnés pour leur image mentale forte. */
const FR_BY_INITIAL: Record<string, string[]> = {
  a: ['Aurore', 'Avion', 'Abeille', 'Arc-en-ciel', 'Atlantique'],
  b: ['Brave', 'Banane', 'Bateau', 'Brebis', 'Boomerang'],
  c: ['Chat', 'Cerise', 'Cabane', 'Cyclope', 'Chocolat'],
  d: ['Dragon', 'Danse', 'Diamant', 'Dauphin', 'Désert'],
  e: ['Étoile', 'Éléphant', 'Étincelle', 'Émeraude', 'Empire'],
  f: ['Forêt', 'Flèche', 'Fanfare', 'Flamboyant', 'Fontaine'],
  g: ['Géant', 'Galaxie', 'Grenade', 'Glacier', 'Guépard'],
  h: ['Hibou', 'Héros', 'Hêtre', 'Horloge', 'Histoire'],
  i: ['Île', 'Igloo', 'Iris', 'Immense', 'Iceberg'],
  j: ['Jardin', 'Journal', 'Jeune', 'Joue', 'Jolly'],
  k: ['Kangourou', 'Karma', 'Kit'],
  l: ['Lune', 'Lion', 'Lac', 'Lanterne', 'Lumière'],
  m: ['Montagne', 'Mer', 'Magicien', 'Miroir', 'Mystère'],
  n: ['Nuage', 'Nuit', 'Navire', 'Neige', 'Naturel'],
  o: ['Océan', 'Or', 'Olympique', 'Orchestre', 'Olive'],
  p: ['Papillon', 'Pirate', 'Pomme', 'Pluie', 'Phare'],
  q: ['Quatre', 'Quartz', 'Quai', 'Quenelle'],
  r: ['Roi', 'Rivière', 'Renard', 'Robot', 'Rose'],
  s: ['Soleil', 'Serpent', 'Sirène', 'Saphir', 'Sapin'],
  t: ['Tigre', 'Tornade', 'Tableau', 'Trésor', 'Tonnerre'],
  u: ['Univers', 'Unique', 'Utopie', 'Urgent', 'Urne'],
  v: ['Volcan', 'Vélo', 'Voile', 'Voyage', 'Voltage'],
  w: ['Wagon', 'Wifi'],
  x: ['Xylophone'],
  y: ['Yak', 'Yacht', 'Yodel'],
  z: ['Zèbre', 'Zen', 'Zodiac'],
}

function firstLetter(word: string): string {
  return word.normalize('NFD').replace(/[̀-ͯ]/g, '')[0]?.toLowerCase() ?? ''
}

/** Génère un acronyme + une phrase mnémo associant chaque lettre. */
export function generateAcronymMnemonic(items: string[]): MnemonicResult {
  const initials = items.map(firstLetter)
  const acronym = initials.join('').toUpperCase()
  const sentence = initials
    .map((letter) => FR_BY_INITIAL[letter]?.[0] ?? letter.toUpperCase())
    .join(' ')
  const difficulty = items.length > 7 ? 0.7 : 0.3 + items.length * 0.05
  return {
    strategy: 'acronyme',
    text: `${acronym} → ${sentence}`,
    items,
    difficulty,
    notes: [
      `${items.length} initiales chaînées. Une phrase fait office d'ancre visuelle.`,
    ],
  }
}

/** Méthode des loci : associe les items à des emplacements communs. */
const LOCI_PATH = [
  "porte d'entrée", 'couloir', 'salon', 'cuisine', 'salle à manger',
  'bureau', 'salle de bain', 'chambre', 'balcon', 'jardin',
  'garage', 'cave', 'grenier', 'voiture', 'parc',
]

export function generateLociMnemonic(items: string[]): MnemonicResult {
  const pairs = items.map((item, i) => `${LOCI_PATH[i] ?? `pièce ${i + 1}`} → ${item}`)
  return {
    strategy: 'loci',
    text: pairs.join('\n'),
    items,
    difficulty: items.length > LOCI_PATH.length ? 0.6 : 0.35,
    notes: [
      'Méthode des palais de mémoire (Simonidès, ~500 av. J.-C.).',
      "Visualise-toi traversant ta maison ; à chaque pièce, l'item s'y trouve de façon insolite.",
    ],
  }
}

/** Chunking : groupe les items en blocs de N (3-4 idéal pour Miller). */
export function generateChunkingMnemonic(items: string[], groupSize = 4): MnemonicResult {
  const groups: string[][] = []
  for (let i = 0; i < items.length; i += groupSize) {
    groups.push(items.slice(i, i + groupSize))
  }
  const text = groups.map((g, i) => `Groupe ${i + 1} : ${g.join(', ')}`).join('\n')
  return {
    strategy: 'chunking',
    text,
    items,
    difficulty: Math.min(0.9, 0.2 + items.length / 30),
    notes: [
      `Découpé en ${groups.length} groupe(s) de ${groupSize} (règle de Miller : 7±2).`,
      'Mémorise chaque groupe indépendamment, puis chaîne-les.',
    ],
  }
}

/** Phrase initiale : on injecte les premières lettres dans une phrase. */
export function generatePhraseMnemonic(items: string[]): MnemonicResult {
  const initials = items.map(firstLetter)
  const phrase = initials
    .map((letter) => {
      const pool = FR_BY_INITIAL[letter] ?? [letter.toUpperCase()]
      return pool[Math.floor((letter.charCodeAt(0) * 17) % pool.length)]
    })
    .join(' ')
  return {
    strategy: 'phrase-initiale',
    text: phrase,
    items,
    difficulty: 0.4,
    notes: [
      'Forme une phrase ridicule avec les initiales. Plus c\'est absurde, mieux ça reste.',
    ],
  }
}

/** Rime : ajoute une rime à un mot clé pour le rendre plus mémorable. */
const RIME_PAIRS: Array<{ pattern: RegExp; rime: string }> = [
  { pattern: /tion$/, rime: 'attention/ambition/passion' },
  { pattern: /ée$/, rime: 'idée/durée/journée' },
  { pattern: /eur$/, rime: 'cœur/peur/heure' },
  { pattern: /age$/, rime: 'sage/page/voyage' },
  { pattern: /eau$/, rime: 'beau/seau/cadeau' },
]

export function generateRimeMnemonic(item: string): MnemonicResult {
  const lower = item.toLowerCase()
  let rime = ''
  for (const r of RIME_PAIRS) {
    if (r.pattern.test(lower)) {
      rime = r.rime
      break
    }
  }
  if (!rime) rime = 'ami/midi/cri'
  return {
    strategy: 'rime',
    text: `${item} — rime avec : ${rime}`,
    items: [item],
    difficulty: 0.2,
    notes: [
      'Mnémonique rimée : utile pour ancrer un terme isolé (ex: formule physique).',
    ],
  }
}

/**
 * Stratégie auto : choisit la meilleure mnémo selon les items.
 *   - 1 item → rime
 *   - 2-7 items + initiales prononçables → acronyme
 *   - > 7 items → chunking
 *   - Pour les listes "spatiales" (lieux, étapes) → loci
 */
export function chooseStrategy(items: string[]): MnemonicStrategy {
  if (items.length === 1) return 'rime'
  if (items.length <= 7) {
    const initials = items.map(firstLetter)
    if (isPronounceable(initials)) return 'acronyme'
    return 'phrase-initiale'
  }
  return 'chunking'
}

function isPronounceable(letters: string[]): boolean {
  // Approximation : présence d'au moins une voyelle.
  const vowels = new Set(['a', 'e', 'i', 'o', 'u', 'y'])
  return letters.some((l) => vowels.has(l))
}

export function generateAuto(items: string[]): MnemonicResult {
  const strategy = chooseStrategy(items)
  switch (strategy) {
    case 'rime': return generateRimeMnemonic(items[0])
    case 'acronyme': return generateAcronymMnemonic(items)
    case 'phrase-initiale': return generatePhraseMnemonic(items)
    case 'chunking': return generateChunkingMnemonic(items)
    case 'loci': return generateLociMnemonic(items)
  }
}
