// Bulletin officiel STI2D / SIN — taxonomie des thèmes à connaître pour le BAC.
//
// Source principale : programme officiel STI2D (BO spécial n°8 de juillet 2019,
// arrêté du 17-1-2019, en vigueur classe de Première dès rentrée 2019, classe
// de Terminale depuis 2020).
//
// Le module learning utilise cette taxonomie pour :
//   • étiqueter les exercices via `curriculumRefs`,
//   • construire l'arbre de progression (Hub.tsx),
//   • aider le LLM à générer du contenu *centré sur le programme officiel*.
//
// Convention d'identifiant : `<niveau>.<bloc>.<sousbloc>`
//   - niveau ∈ {1, T}            (Première / Terminale)
//   - bloc en MAJUSCULES (tronc commun) ou nom de spécialité (SIN, EE, ITEC…)
//   - sousbloc en kebab-case
// Ex.: `T.SIN.protocoles-reseau`, `1.MAT.suites`, `1.PC.energie-mecanique`.
//
// L'idée est que ces refs survivent même si le BO bouge un peu — on attache
// l'exercice à un concept, pas à un numéro de page.

export type SchoolYear = '1' | 'T'

export type CurriculumNode = {
  id: string
  year: SchoolYear
  /** Discipline (tronc commun) ou spécialité. */
  track: 'MAT' | 'PC' | 'I2D' | 'SIN' | 'EE' | 'ITEC' | 'AC' | 'PHILO' | 'LV1' | 'FR'
  label: string
  /** Compétences typiques (vocabulaire BO). */
  competences: string[]
  /** Concepts clés — clé de voûte pour l'évaluateur sémantique. */
  keywords: string[]
  /** Pré-requis (liste d'autres ids). */
  prerequisites?: string[]
}

// --- Mathématiques tronc commun --------------------------------------------
const MATH_1: CurriculumNode[] = [
  {
    id: '1.MAT.suites-recurrence',
    year: '1',
    track: 'MAT',
    label: 'Suites numériques et raisonnement par récurrence',
    competences: ["Calculer un terme", "Étudier monotonie/limite", "Démontrer par récurrence"],
    keywords: ['arithmétique', 'géométrique', 'récurrence', 'limite'],
  },
  {
    id: '1.MAT.fonction-derivee',
    year: '1',
    track: 'MAT',
    label: 'Fonction dérivée et tangente',
    competences: ['Calculer une dérivée', "Lire le sens de variation", "Équation de la tangente"],
    keywords: ['dérivée', 'tangente', 'tableau de variations'],
  },
  {
    id: '1.MAT.exponentielle',
    year: '1',
    track: 'MAT',
    label: 'Fonction exponentielle',
    competences: ['Propriétés algébriques', "Étudier exp(ax+b)", "Modéliser une croissance"],
    keywords: ['exp', 'décroissance radioactive', 'croissance exponentielle'],
  },
  {
    id: '1.MAT.trigonometrie',
    year: '1',
    track: 'MAT',
    label: 'Trigonométrie : cercle, équations, dérivées',
    competences: ['Mesures principales', "Résolution cos x = a", "Dérivées sin/cos"],
    keywords: ['cercle trigo', 'équations trigonométriques'],
  },
  {
    id: '1.MAT.probas-conditionnelles',
    year: '1',
    track: 'MAT',
    label: 'Probabilités conditionnelles et indépendance',
    competences: ['Arbre pondéré', 'Formule des probabilités totales', 'Indépendance'],
    keywords: ['arbre', 'Bayes', 'indépendance'],
  },
]

const MATH_T: CurriculumNode[] = [
  {
    id: 'T.MAT.limites-continuite',
    year: 'T',
    track: 'MAT',
    label: 'Limites de fonctions et continuité',
    competences: ['Limite en l’infini', 'Limites de référence', 'Théorème des valeurs intermédiaires'],
    keywords: ['limite', 'asymptote', 'continuité'],
    prerequisites: ['1.MAT.fonction-derivee'],
  },
  {
    id: 'T.MAT.derivation-composee',
    year: 'T',
    track: 'MAT',
    label: 'Dérivation et composées',
    competences: ['Dérivée d’une composée', 'Étude de variations', 'Convexité'],
    keywords: ['dérivée', 'composée', 'convexité'],
  },
  {
    id: 'T.MAT.primitives-integrales',
    year: 'T',
    track: 'MAT',
    label: 'Primitives et intégrales',
    competences: ["Trouver une primitive", "Calcul d’aire", "Valeur moyenne"],
    keywords: ['primitive', 'intégrale', 'aire sous la courbe'],
  },
  {
    id: 'T.MAT.equations-differentielles',
    year: 'T',
    track: 'MAT',
    label: "Équations différentielles y' = ay + b",
    competences: ['Résoudre y’ = ay + f(t)', 'Modéliser circuit RC, désintégration'],
    keywords: ['équation différentielle', 'régime transitoire', 'RC'],
    prerequisites: ['T.MAT.derivation-composee'],
  },
  {
    id: 'T.MAT.loi-binomiale',
    year: 'T',
    track: 'MAT',
    label: 'Loi binomiale, échantillonnage, intervalle de fluctuation',
    competences: ['Espérance/variance binomiale', 'Coefficients binomiaux', 'Estimation'],
    keywords: ['binomiale', 'intervalle de confiance'],
  },
]

// --- Physique-Chimie tronc commun ------------------------------------------
const PC_1: CurriculumNode[] = [
  {
    id: '1.PC.energie-mecanique',
    year: '1',
    track: 'PC',
    label: 'Énergie cinétique, potentielle, mécanique',
    competences: ['Bilan énergétique', 'PFD pour système isolé', 'Restitution de l’énergie'],
    keywords: ['énergie cinétique', 'énergie potentielle', 'conservation'],
  },
  {
    id: '1.PC.signaux-electriques',
    year: '1',
    track: 'PC',
    label: 'Caractéristiques des signaux électriques',
    competences: ['Période, fréquence, amplitude', 'Valeur efficace', 'Conversion analogique-numérique'],
    keywords: ['signal', 'oscillogramme', 'CAN'],
  },
  {
    id: '1.PC.transferts-thermiques',
    year: '1',
    track: 'PC',
    label: 'Transferts thermiques et bilan énergétique',
    competences: ['Conduction/convection/rayonnement', 'Résistance thermique', 'Isolation'],
    keywords: ['flux thermique', 'résistance thermique', 'Fourier'],
  },
  {
    id: '1.PC.chimie-quantitative',
    year: '1',
    track: 'PC',
    label: 'Chimie quantitative : mole, concentration, avancement',
    competences: ['Tableau d’avancement', 'Concentration molaire', 'Suivi cinétique'],
    keywords: ['mole', 'avancement', 'cinétique'],
  },
]

const PC_T: CurriculumNode[] = [
  {
    id: 'T.PC.evolution-temporelle',
    year: 'T',
    track: 'PC',
    label: 'Évolution temporelle des systèmes électriques (RC, RLC)',
    competences: ['Régime transitoire', 'Constante de temps', 'Régime libre RLC'],
    keywords: ['RC', 'RLC', 'τ', 'pulsation propre'],
    prerequisites: ['1.PC.signaux-electriques', 'T.MAT.equations-differentielles'],
  },
  {
    id: 'T.PC.ondes-mecaniques',
    year: 'T',
    track: 'PC',
    label: 'Ondes mécaniques et acoustique',
    competences: ['Célérité', 'Effet Doppler', 'Niveau sonore en dB'],
    keywords: ['onde', 'Doppler', 'décibel'],
  },
  {
    id: 'T.PC.diffraction-interferences',
    year: 'T',
    track: 'PC',
    label: 'Optique : diffraction, interférences',
    competences: ["Calcul d'un interfrange", 'Conditions d’interférences constructives'],
    keywords: ['diffraction', 'fentes d’Young', 'interfrange'],
  },
  {
    id: 'T.PC.cinetique-chimique',
    year: 'T',
    track: 'PC',
    label: 'Cinétique chimique et catalyse',
    competences: ['Vitesse de réaction', 'Loi de vitesse', "Effet de la température"],
    keywords: ['cinétique', 'Arrhénius', 'catalyseur'],
  },
]

// --- I2D : Innovation Technologique et Éco-Conception (commun aux STI2D) ---
const I2D_1: CurriculumNode[] = [
  {
    id: '1.I2D.matiere-energie-information',
    year: '1',
    track: 'I2D',
    label: 'Matière–énergie–information : modéliser un système',
    competences: ['Schéma fonctionnel', 'Chaîne d’énergie / d’information', 'Diagramme SysML'],
    keywords: ['MEI', 'SysML', 'cahier des charges'],
  },
  {
    id: '1.I2D.cycle-vie-eco',
    year: '1',
    track: 'I2D',
    label: 'Cycle de vie, ACV, éco-conception',
    competences: ['Analyse de cycle de vie', 'Impact environnemental', "Réutilisation"],
    keywords: ['ACV', 'éco-conception', 'recyclabilité'],
  },
]

// --- SIN : spécialité Systèmes d’Information Numériques --------------------
const SIN_T: CurriculumNode[] = [
  {
    id: 'T.SIN.acquisition-numerisation',
    year: 'T',
    track: 'SIN',
    label: "Chaîne d’acquisition et numérisation d'un signal",
    competences: ['Capteur, conditionneur, CAN', 'Théorème de Shannon', 'Quantification'],
    keywords: ['capteur', 'CAN', 'échantillonnage', 'résolution'],
    prerequisites: ['1.PC.signaux-electriques'],
  },
  {
    id: 'T.SIN.microcontroleur',
    year: 'T',
    track: 'SIN',
    label: 'Microcontrôleur et programmation embarquée',
    competences: ['GPIO', 'PWM', 'Interruptions', 'Mesure ADC'],
    keywords: ['Arduino', 'ESP32', 'Raspberry Pi Pico', 'PWM'],
  },
  {
    id: 'T.SIN.protocoles-reseau',
    year: 'T',
    track: 'SIN',
    label: 'Protocoles réseau et adressage',
    competences: ['Modèle TCP/IP', 'IPv4/IPv6', 'HTTP, MQTT'],
    keywords: ['TCP', 'HTTP', 'MQTT', 'IoT'],
  },
  {
    id: 'T.SIN.algorithmique-python',
    year: 'T',
    track: 'SIN',
    label: 'Algorithmique et programmation Python',
    competences: ['Structures de contrôle', 'Listes/dictionnaires', 'Modularité', 'Complexité élémentaire'],
    keywords: ['Python', 'algorithme', 'complexité'],
  },
  {
    id: 'T.SIN.iot-objets-connectes',
    year: 'T',
    track: 'SIN',
    label: 'Objets connectés, sécurité, IHM',
    competences: ['Communication sans fil', 'Sécurité (TLS)', 'IHM web/embarquée'],
    keywords: ['IoT', 'TLS', 'WebSocket', 'HMI'],
    prerequisites: ['T.SIN.microcontroleur', 'T.SIN.protocoles-reseau'],
  },
  {
    id: 'T.SIN.intelligence-artificielle',
    year: 'T',
    track: 'SIN',
    label: 'Initiation à l’IA et systèmes adaptatifs',
    competences: ['Apprentissage supervisé', 'Réseau de neurones', 'Cas d’usage embarqué'],
    keywords: ['IA', 'machine learning', 'réseau de neurones'],
  },
]

// --- EE (Energies & Environnement) — minimum vital pour les exos transverses
const EE_T: CurriculumNode[] = [
  {
    id: 'T.EE.machines-electriques',
    year: 'T',
    track: 'EE',
    label: 'Machines électriques : moteur CC, asynchrone',
    competences: ['Caractéristique couple/vitesse', 'Rendement', 'Variation de vitesse'],
    keywords: ['MCC', 'asynchrone', 'rendement'],
  },
]

// --- Catalog -----------------------------------------------------------------
export const BAC_STI2D_CURRICULUM: readonly CurriculumNode[] = [
  ...MATH_1,
  ...MATH_T,
  ...PC_1,
  ...PC_T,
  ...I2D_1,
  ...SIN_T,
  ...EE_T,
] as const

export function findNode(id: string): CurriculumNode | undefined {
  return BAC_STI2D_CURRICULUM.find((n) => n.id === id)
}

export function nodesByYear(year: SchoolYear): CurriculumNode[] {
  return BAC_STI2D_CURRICULUM.filter((n) => n.year === year)
}

export function nodesByTrack(track: CurriculumNode['track']): CurriculumNode[] {
  return BAC_STI2D_CURRICULUM.filter((n) => n.track === track)
}

/** Suggested next concept after mastering `id` — based on prerequisite graph. */
export function suggestNext(id: string): CurriculumNode[] {
  return BAC_STI2D_CURRICULUM.filter((n) => n.prerequisites?.includes(id))
}

/** Sanity check: prerequisite ids resolve and don't cycle. */
export function validateCurriculumGraph(): string[] {
  const issues: string[] = []
  const ids = new Set(BAC_STI2D_CURRICULUM.map((n) => n.id))
  for (const node of BAC_STI2D_CURRICULUM) {
    if (!node.prerequisites) continue
    for (const pre of node.prerequisites) {
      if (!ids.has(pre)) issues.push(`Node ${node.id} requires unknown ${pre}`)
    }
  }
  // Cycle detection (DFS).
  const adj = new Map<string, string[]>()
  for (const node of BAC_STI2D_CURRICULUM) adj.set(node.id, node.prerequisites ?? [])
  const WHITE = 0, GREY = 1, BLACK = 2
  const color = new Map<string, number>()
  for (const id of ids) color.set(id, WHITE)
  const stack: string[] = []
  function visit(u: string): boolean {
    color.set(u, GREY)
    stack.push(u)
    for (const v of adj.get(u) ?? []) {
      if (color.get(v) === GREY) {
        issues.push(`Cycle: ${[...stack, v].join(' -> ')}`)
        return false
      }
      if (color.get(v) === WHITE && !visit(v)) return false
    }
    stack.pop()
    color.set(u, BLACK)
    return true
  }
  for (const id of ids) if (color.get(id) === WHITE) visit(id)
  return issues
}
