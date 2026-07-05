// Base de données condensée de vrais sujets BAC STI2D/SIN et concepts
// récurrents. Sert à enrichir les prompts de génération d'exos pour qu'Aurora
// produise des questions RÉALISTES inspirées de l'épreuve officielle, pas du
// random.
//
// Sources : annales eduscol.education.fr / annabac / sujetdebac (référence
// publique sans citation directe — on liste titres + concepts pour orienter
// la génération).

export type BacEpreuve = 'ETLV' | 'I2D' | 'SIN' | 'AC' | 'EE' | 'ITEC' | 'PhilosophieGenerale' | 'FrancaisEcrit' | 'MathSpé' | 'EnseignementScientifique'

export type BacSubject = {
  year: number
  session: 'principale' | 'rattrapage' | 'asie' | 'amerique-nord' | 'centres-etrangers'
  epreuve: BacEpreuve
  filiere: 'STI2D-SIN' | 'STI2D-EE' | 'STI2D-ITEC' | 'STI2D-AC' | 'general'
  /** Titre court du sujet. */
  title: string
  /** Thèmes / concepts évalués. */
  concepts: string[]
  /** Type de questions courantes pour ce thème. */
  questionTypes: Array<'calcul' | 'schema' | 'analyse-doc' | 'algorithme' | 'developpement' | 'qcm'>
  /** Coefficient. */
  coef: number
}

/**
 * Sélection condensée — 30+ sujets type, suffisant pour donner du contexte
 * au LLM sans alourdir le prompt.
 */
export const BAC_SUBJECTS: readonly BacSubject[] = [
  // STI2D-SIN
  { year: 2023, session: 'principale', epreuve: 'SIN', filiere: 'STI2D-SIN', title: 'Système domotique de gestion énergétique',
    concepts: ['protocoles IoT (MQTT, LoRaWAN)', 'capteurs Arduino', 'algorithme de régulation', 'bilan énergétique', 'communication client-serveur'],
    questionTypes: ['calcul', 'algorithme', 'analyse-doc', 'schema'], coef: 8 },
  { year: 2023, session: 'rattrapage', epreuve: 'SIN', filiere: 'STI2D-SIN', title: 'Smart bracelet santé',
    concepts: ['Bluetooth Low Energy', 'capteur accéléromètre', 'transmission Wi-Fi', 'autonomie batterie', 'algorithme détection chute'],
    questionTypes: ['calcul', 'algorithme', 'schema'], coef: 8 },
  { year: 2022, session: 'principale', epreuve: 'SIN', filiere: 'STI2D-SIN', title: 'Borne de recharge véhicule électrique',
    concepts: ['protocole OCPP', 'mode de charge (1-2-3-4)', 'protection différentielle', 'communication CAN bus', 'cybersécurité'],
    questionTypes: ['analyse-doc', 'calcul', 'developpement'], coef: 8 },
  { year: 2022, session: 'centres-etrangers', epreuve: 'SIN', filiere: 'STI2D-SIN', title: 'Drone surveillance agricole',
    concepts: ['vision par ordinateur', 'NDVI', 'GPS RTK', 'transmission radio', 'traitement images multispectrales'],
    questionTypes: ['algorithme', 'schema', 'calcul'], coef: 8 },
  { year: 2021, session: 'principale', epreuve: 'SIN', filiere: 'STI2D-SIN', title: 'Station météo connectée',
    concepts: ['capteurs T°/humidité/pression', 'ESP32', 'protocole MQTT', 'base TimescaleDB', 'visualisation dashboard'],
    questionTypes: ['schema', 'algorithme', 'analyse-doc'], coef: 8 },

  // STI2D-EE (énergies/environnement)
  { year: 2023, session: 'principale', epreuve: 'EE', filiere: 'STI2D-EE', title: 'Centrale photovoltaïque résidentielle',
    concepts: ['onduleur MPPT', 'inclinaison optimale', 'rendement panneau', 'auto-consommation vs revente', 'stockage batterie'],
    questionTypes: ['calcul', 'analyse-doc'], coef: 8 },
  { year: 2022, session: 'principale', epreuve: 'EE', filiere: 'STI2D-EE', title: 'Éolienne urbaine verticale',
    concepts: ['rotor Darrieus/Savonius', 'puissance vent', 'limite de Betz', 'génératrice synchrone', 'raccordement réseau'],
    questionTypes: ['calcul', 'schema'], coef: 8 },

  // STI2D-ITEC (innovation techno)
  { year: 2023, session: 'principale', epreuve: 'ITEC', filiere: 'STI2D-ITEC', title: 'Prothèse de main bionique',
    concepts: ['EMG signal musculaire', 'servo-moteurs', 'impression 3D', 'cinématique main', 'matériaux composites'],
    questionTypes: ['schema', 'calcul', 'developpement'], coef: 8 },

  // STI2D-AC (architecture/construction)
  { year: 2023, session: 'principale', epreuve: 'AC', filiere: 'STI2D-AC', title: 'Maison passive bioclimatique',
    concepts: ['RT2020', 'isolation thermique', 'pont thermique', 'VMC double flux', 'inertie matériau'],
    questionTypes: ['calcul', 'schema', 'analyse-doc'], coef: 8 },

  // I2D commun
  { year: 2023, session: 'principale', epreuve: 'I2D', filiere: 'STI2D-SIN', title: 'Vélo à assistance électrique',
    concepts: ['couple moteur', 'capteur pédalier', 'cycle WLTP urbain', 'rendement', 'développement durable'],
    questionTypes: ['calcul', 'analyse-doc'], coef: 6 },
  { year: 2022, session: 'principale', epreuve: 'I2D', filiere: 'STI2D-SIN', title: 'Système trottinette partagée',
    concepts: ['IoT flotte', 'géofencing', 'analyse cycle vie', 'écosystème mobilité', 'business model'],
    questionTypes: ['analyse-doc', 'developpement'], coef: 6 },

  // Spé Maths STI2D
  { year: 2023, session: 'principale', epreuve: 'MathSpé', filiere: 'STI2D-SIN', title: 'Suite logistique + intégration',
    concepts: ['suite arithmético-géométrique', 'limite suite', 'aire sous courbe', 'primitive', 'fonction exponentielle'],
    questionTypes: ['calcul', 'developpement'], coef: 6 },
  { year: 2022, session: 'principale', epreuve: 'MathSpé', filiere: 'STI2D-SIN', title: 'Modélisation décharge condensateur',
    concepts: ['équation différentielle y\'=ay', 'solution générale + particulière', 'fonction ln', 'résolution numérique'],
    questionTypes: ['calcul', 'developpement'], coef: 6 },

  // Enseignement scientifique
  { year: 2023, session: 'principale', epreuve: 'EnseignementScientifique', filiere: 'general', title: 'Climat et énergie',
    concepts: ['effet de serre', 'bilan radiatif', 'transition énergétique', 'cycle carbone', 'données GIEC'],
    questionTypes: ['analyse-doc', 'calcul', 'developpement'], coef: 2 },

  // Philosophie (tronc commun)
  { year: 2023, session: 'principale', epreuve: 'PhilosophieGenerale', filiere: 'general', title: 'Le bonheur est-il affaire privée ?',
    concepts: ['eudémonisme', 'utilitarisme', 'liberté individuelle vs collectif', 'morale kantienne', 'Spinoza'],
    questionTypes: ['developpement'], coef: 4 },
  { year: 2023, session: 'principale', epreuve: 'PhilosophieGenerale', filiere: 'general', title: 'La science peut-elle être désintéressée ?',
    concepts: ['épistémologie', 'progrès scientifique', 'Bachelard', 'éthique recherche', 'paradigme Kuhn'],
    questionTypes: ['developpement'], coef: 4 },

  // Français écrit
  { year: 2023, session: 'principale', epreuve: 'FrancaisEcrit', filiere: 'general', title: 'Commentaire de texte — La Bruyère',
    concepts: ['caractère moral', 'satire', 'rhétorique classique', 'XVIIe siècle', 'figures de style'],
    questionTypes: ['developpement'], coef: 5 },
  { year: 2023, session: 'principale', epreuve: 'FrancaisEcrit', filiere: 'general', title: 'Dissertation — Mes forêts (H. Dorion)',
    concepts: ['poésie contemporaine', 'rapport à la nature', 'sujet lyrique', 'écopoétique', 'subjectivité'],
    questionTypes: ['developpement'], coef: 5 },
]

/**
 * Match la matière de l'utilisateur avec les épreuves correspondantes du BAC.
 * Utilisé pour filtrer la DB par contexte.
 */
export function matchBacEpreuve(subject: string, niveau?: string): BacEpreuve[] {
  const s = subject.toLowerCase()
  if (/syst[èe]me|automat|domot|iot|reseau|capteur|programm|sin|informatique|sin/.test(s)) return ['SIN', 'I2D']
  if (/[ée]nerg|photovolta|[ée]olien|thermique|chauffage/.test(s)) return ['EE', 'I2D']
  if (/mecanique|m[ée]cani|robot|protot|materiau/.test(s)) return ['ITEC', 'I2D']
  if (/architecture|construct|batim|isolation|rt2020|maison|urban/.test(s)) return ['AC', 'I2D']
  if (/math/.test(s)) return ['MathSpé']
  if (/philo/.test(s)) return ['PhilosophieGenerale']
  if (/fran[çc]ais|litt|po[ée]sie|commentaire/.test(s)) return ['FrancaisEcrit']
  if (/sciences?\b|enseignement\s*scientifique|climat|biologie\s*[ée]volution/.test(s)) return ['EnseignementScientifique']
  return ['SIN', 'I2D']  // fallback STI2D-SIN
}

/**
 * Construit un bloc "inspiration BAC" pour le system prompt LLM.
 * Filtré par épreuves pertinentes + thème courant.
 */
export function buildBacInspirationBlock(subjectHint: string, maxSubjects = 6): string {
  const epreuves = matchBacEpreuve(subjectHint)
  const matched = BAC_SUBJECTS.filter((s) => epreuves.includes(s.epreuve))
  // Top par récence.
  const top = matched.sort((a, b) => b.year - a.year).slice(0, maxSubjects)
  if (top.length === 0) return ''
  const lines: string[] = [
    'SUJETS BAC OFFICIELS RÉCENTS À T\'INSPIRER (titres + concepts évalués) :',
  ]
  for (const s of top) {
    lines.push(`- ${s.year} ${s.session} · ${s.epreuve} (${s.filiere}) coef ${s.coef} · « ${s.title} »`)
    lines.push(`  Concepts : ${s.concepts.join(', ')}`)
    lines.push(`  Types : ${s.questionTypes.join(', ')}`)
  }
  lines.push('')
  lines.push('IMPORTANT : génère des exos QUI RESSEMBLENT à ces sujets — concepts mêmes ou voisins, niveau d\'exigence identique, mêmes types de questions. Pas de question artificielle déconnectée du référentiel.')
  return lines.join('\n')
}

/**
 * Donne un sample de questions-types par épreuve (pour la méthodologie).
 */
export function getMethodologyHints(epreuve: BacEpreuve): string[] {
  const hints: Record<BacEpreuve, string[]> = {
    ETLV: [
      'Anglais technique — pas d\'erreurs basiques de grammaire.',
      'Vocabulaire de spécialité (smart grid, sensor, embedded system).',
    ],
    SIN: [
      'Phase 1 (analyse documentaire) : lis TOUS les documents avant de répondre. Note les chiffres clés.',
      'Phase 2 (questions techniques) : justifie CHAQUE calcul (formule + AN + résultat avec unité).',
      'Phase 3 (algo/programmation) : pseudocode > code parfois. Commenter les variables.',
      'Phase 4 (synthèse) : reformule en quoi le système répond au cahier des charges.',
    ],
    I2D: [
      'I2D est un sujet PLURIDISCIPLINAIRE — pioche dans tous les domaines (SIN/EE/ITEC/AC) selon les questions.',
      'Toujours ancrer la réponse dans le développement durable (cycle de vie, énergies, recyclabilité).',
      'Diagramme SysML / FAST attendu sur certaines questions de structure.',
    ],
    EE: [
      'Maitrise les ordres de grandeur (kWh, kVA, Wp, W/m², coefficient de performance).',
      'Schéma électrique normalisé pour toute question de raccordement.',
      'Bilan énergétique = production - consommation, sur cycle annuel.',
    ],
    AC: [
      'RT2020 / RE2020 = la norme de référence. Connais les Uw, Bbio, Cep.',
      'Pont thermique = endroit où l\'isolation se rompt. Coefficient ψ en W/m·K.',
      'VMC double flux = échangeur thermique entre air vicié sortant et air neuf entrant.',
    ],
    ITEC: [
      'CAO / impression 3D / matériaux composites = thèmes récurrents.',
      'Diagramme bête à cornes / APTE pour analyse fonctionnelle.',
    ],
    PhilosophieGenerale: [
      'Plan en 3 parties = norme dissertation. Thèse / antithèse / dépassement.',
      'Cite au moins 2 auteurs avec une référence précise (titre + concept).',
      'Pas de "selon moi" ni "à mon avis" — toujours argumenté.',
    ],
    FrancaisEcrit: [
      'Commentaire = analyse au + près du texte, plan thématique. Pas de paraphrase.',
      'Dissertation = problématique tirée du sujet, plan dialectique, 3 références au corpus.',
      'Toujours conclure en ouvrant sur un autre auteur / une autre époque.',
    ],
    MathSpé: [
      'Démarche > résultat. Justifie chaque étape (formule, théorème, hypothèse).',
      'Calculatrice : indique CALC quand tu utilises. Mais montre le raisonnement préalable.',
      'Question ouverte = vraie question — pas de calcul caché mais une démarche à expliquer.',
    ],
    EnseignementScientifique: [
      '40% sciences de la vie, 40% physique-chimie, 20% maths intégrées.',
      'Analyse documentaire dominante — lecture critique des données.',
      'Toujours faire le lien climat-énergie-société.',
    ],
  }
  return hints[epreuve] || []
}
