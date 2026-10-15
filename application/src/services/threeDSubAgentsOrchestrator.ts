/**
 * threeDSubAgentsOrchestrator.ts
 *
 * Orchestrateur de sous-agents spécialisés 3D / Ingénierie CAO et générateur
 * de Prompt Maître structuré + géométrie procédurale de prévisualisation
 * Holographic Gaussian Splats.
 *
 * Garantit :
 * 1. La structuration automatique d'un "Prompt Maître" même lorsque l'utilisateur
 *    formule une demande complexe sans contrainte explicite (ex: "main robotisée").
 * 2. La division visible du travail en 5 sous-agents spécialisés indépendants
 *    dont les états, livrables intermédiaires et progressions fusionnent en continu.
 * 3. La persistance (localStorage) du timestamp de départ `startedAtMs`, de l'étape
 *    courante, du pourcentage et de l'ETA pour qu'aucun changement d'onglet,
 *    navigation inter-module ou rechargement (Natif, Web, Tunnel mobile) ne fige
 *    le timer ni ne perde la progression.
 * 4. La synthèse d'un nuage 3D de Gaussian Splats holographiques adapté au sujet
 *    (main robotisée articulée à 5 doigts, bras mécatronique, mécanisme d'engrenages,
 *    véhicule/drone, personnage ou boîtier CAO).
 */

export type SubAgentId =
  | 'morphology_kinematics'
  | 'mechanical_cad'
  | 'volumetric_splatting'
  | 'pbr_materials'
  | 'assembly_verification'

export type SubAgentStatus = 'queued' | 'working' | 'done' | 'warning'

export interface ThreeDSubAgentState {
  id: SubAgentId
  index: number
  codeName: string
  role: string
  specialty: string
  status: SubAgentStatus
  progressPct: number
  currentTask: string
  deliverableSummary: string
  decisions: string[]
  accentColor: string
}

export type SplatArchetype =
  | 'robotic_hand'
  | 'robotic_arm'
  | 'gear_mechanism'
  | 'vehicle_drone'
  | 'humanoid_character'
  | 'cad_enclosure'

export interface MasterPromptBlueprint {
  rawPrompt: string
  subjectTitle: string
  archetype: SplatArchetype
  complexityLevel: 'standard' | 'avancé' | 'ingénierie_complexe'
  inferredConstraints: string[]
  kinematicChainSummary: string
  dimensionalEnvelopeMm: [number, number, number]
  degreesOfFreedom: number
  subAgentDirectives: Record<SubAgentId, string>
  formattedMasterPrompt: string
}

export interface PersistedThreeDMissionState {
  missionKey: string
  rawPrompt: string
  mode: 'mesh_3d' | 'engineering_cad'
  active: boolean
  startedAtMs: number
  lastHeartbeatMs: number
  phaseLabel: string
  phasePercent: number
  estimatedTotalSeconds: number
  stlCount: number
  verifiedCriteriaCount: number
  totalCriteriaCount: number
  masterBlueprint: MasterPromptBlueprint
  subAgents: ThreeDSubAgentState[]
  completedMeshUrl?: string | null
  completedViewerUrl?: string | null
}

export interface HolographicSplatPoint {
  /** Coordonnées 3D normalisées [-1..1] */
  x: number
  y: number
  z: number
  /** Rayon anisotrope du splat */
  radius: number
  /** Couleur principale hex/rgb */
  color: string
  /** Sous-ensemble fonctionnel (ex: paume, pouce, index, articulation, tendon) */
  partGroup: string
  /** Seuil de progression [0..1] à partir duquel ce splat se solidifie */
  solidifyThreshold: number
  /** Indique un noeud cinématique (articulation / pivot) */
  isJoint?: boolean
  /** Indice de doigt (0=pouce..4=auriculaire) et phalange (0..2) pour animation temps réel */
  fingerIdx?: number
  phalangeIdx?: number
}

const STORAGE_KEY = 'aurora.3d.activeMission.v1'
const MISSION_EVENT = 'aurora:3d-mission-sync'

export function detectSplatArchetype(prompt: string): SplatArchetype {
  const p = (prompt || '').toLowerCase()
  if (
    /\b(main\s+robot|main\s+bionique|main\s+articul|main\s+mécanique|main\s+mecanique|robotic\s+hand|bionic\s+hand|proth[eè]se\s+de\s+main|doigts?\s+articul|phalange|pince\s+anthropomorphe|main\s+cyber)\b/i.test(
      p,
    ) ||
    (/\b(main|hand)\b/i.test(p) && /\b(robot|bionique|mécanique|mecanique|servo|articul|doigt|proth[eè]se)\b/i.test(p))
  ) {
    return 'robotic_hand'
  }
  if (/\b(bras\s+robot|robot\s+arm|manipulateur|exosquelette|mécatronique|mecatronique|bip[eè]de|andro[iï]de|robot)\b/i.test(p)) {
    return 'robotic_arm'
  }
  if (/\b(engrenage|gear|pignon|réducteur|reducteur|planétaire|planetaire|charni[eè]re|vérin|verin|poulie|transmission|couple|mécanisme|mecanisme)\b/i.test(p)) {
    return 'gear_mechanism'
  }
  if (/\b(voiture|véhicule|vehicule|drone|avion|moto|vélo|velo|train|navire|rover|châssis\s+roulant|chassis)\b/i.test(p)) {
    return 'vehicle_drone'
  }
  if (/\b(personnage|guerrier|humain|humano[iï]de|créature|creature|visage|buste|statue|figurine|animal)\b/i.test(p)) {
    return 'humanoid_character'
  }
  return 'cad_enclosure'
}

export function synthesizeThreeDMasterPrompt(rawPrompt: string): MasterPromptBlueprint {
  const clean = (rawPrompt || '').trim() || 'Système mécatronique articulé haute précision'
  const archetype = detectSplatArchetype(clean)

  if (archetype === 'robotic_hand') {
    const inferredConstraints = [
      'Architecture anthropomorphe complète : 1 paume structurelle creuse + 5 doigts indépendants (pouce opposable à 3 DDL + 4 doigts à 3 phalanges : proximale, médiane, distale).',
      'Cinématique articulaire : 15 liaisons pivots (revolute) avec axes d’articulation nets, butées mécaniques anti-hyperextension (0° à 90°) et jeu radial fonctionnel de 0,25 mm.',
      'Actionnement & routage interne : canaux guides-tendons Ø2,2 mm traversant la paume jusqu’aux phalanges distales + logements pour micro-servomoteurs ou actionneurs linéaires dans la paume/avant-bras.',
      'Fabrication & tolérances : épaisseur de paroi minimale 2,4 mm, alésages d’axes Ø3,2 mm (visserie/goupilles M3), séparation géométrique franche entre les doigts (zéro fusion inter-doigts).',
      'Matériaux & lisibilité visuelle : châssis palmaire en alliage/polymère technique sombre, coques phalangiennes segmentées, anneaux articulaires contrastés et coussinets tactiles sur les pulpes.',
    ]
    const subAgentDirectives: Record<SubAgentId, string> = {
      morphology_kinematics:
        'Définir la topologie à 5 chaînes cinématiques (pouce opposable à 42° + 4 doigts) et positionner les 15 axes de rotation sans recouvrement.',
      mechanical_cad:
        'Dimensionner la paume (92 × 84 × 28 mm), les 14 phalanges cotées, les chapes de charnières (jeu 0,25 mm) et les tunnels de câbles/tendons.',
      volumetric_splatting:
        'Générer le nuage de Gaussian Splats articulé puis sculpter/construire chaque solide étanche (watertight) en pose semi-ouverte naturelle.',
      pbr_materials:
        'Appliquer la segmentation multi-matières : titane brossé sur phalanges, polymère carbone sur paume, accents anodisés sur les pivots.',
      assembly_verification:
        'Vérifier la fermeture/ouverture complète des doigts sans collision, générer la nomenclature BOM (axes M3, tendons, actionneurs) et sceller le livrable.',
    }
    const formattedMasterPrompt = [
      `# PROMPT MAÎTRE D'INGÉNIERIE & 3D — ${clean.toUpperCase()}`,
      '',
      `## 1. Objectif & Architecture Système`,
      `Concevoir et modéliser une **main robotisée anthropomorphe fonctionnelle et articulée** répondant à la demande : « ${clean} ». Même sans contrainte initiale fournie, le système applique automatiquement les standards mécatroniques de précision.`,
      '',
      `## 2. Division par Sous-Agents Spécialisés`,
      `- **[Agent 01 · Morphologie & Cinématique]** : ${subAgentDirectives.morphology_kinematics}`,
      `- **[Agent 02 · Ingénierie Mécanique & Tolérances]** : ${subAgentDirectives.mechanical_cad}`,
      `- **[Agent 03 · Sculpture Volumétrique & Splatting]** : ${subAgentDirectives.volumetric_splatting}`,
      `- **[Agent 04 · Matériaux PBR & Zones Fonctionnelles]** : ${subAgentDirectives.pbr_materials}`,
      `- **[Agent 05 · Assemblage, Cinématique & Conformité]** : ${subAgentDirectives.assembly_verification}`,
      '',
      `## 3. Contraintes Techniques Auto-Inférées`,
      ...inferredConstraints.map((c) => `- ${c}`),
      '',
      `## 4. Critères de Validation Finale`,
      `- Doigts parfaitement séparés et articulables (15 DDL, 15 liaisons revolute).`,
      `- Maillage 3D étanche (watertight), sans artefacts flottants, prêt pour le viewer temps réel et l'impression/assemblage.`,
    ].join('\n')

    return {
      rawPrompt: clean,
      subjectTitle: 'Main Robotisée Anthropomorphe Articulée (15 DDL)',
      archetype,
      complexityLevel: 'ingénierie_complexe',
      inferredConstraints,
      kinematicChainSummary: 'Paume ancrée → 5 chaînes digitales indépendantes → 14 phalanges → 15 liaisons pivots (revolute)',
      dimensionalEnvelopeMm: [195, 92, 34],
      degreesOfFreedom: 15,
      subAgentDirectives,
      formattedMasterPrompt,
    }
  }

  if (archetype === 'robotic_arm' || archetype === 'gear_mechanism') {
    const isArm = archetype === 'robotic_arm'
    const inferredConstraints = [
      isArm
        ? 'Architecture poly-articulée : embase fixe renforcée, tourelle rotative, bras, avant-bras, poignet et effecteur terminal.'
        : 'Architecture mécanique à transmission directe : carter porteur, arbres guidés, engrenages conjugués et paliers coaxiaux.',
      'Jeu fonctionnel calibré : 0,25 mm sur liaisons mobiles (revolute/prismatic), 0,18 mm sur centrages fixes et épaisseur minimale de paroi 2,5 mm.',
      'Intégration visserie standard M3 (passants Ø3,2 mm, lamages Ø6 mm, inserts thermofixés Ø4,0 × 5 mm) et accès outil dégagé.',
      'Solides 3D fermés (watertight), orientables sur plateau 220 × 220 × 250 mm sans porte-à-faux critique.',
    ]
    const subAgentDirectives: Record<SubAgentId, string> = {
      morphology_kinematics: `Décomposer « ${clean} » en sous-ensembles fixes/mobiles, définir l'arbre cinématique et les limites de course.`,
      mechanical_cad: 'Calculer les entraxes, sections porteuses, logements de roulements/axes et jeux d’assemblage en millimètres.',
      volumetric_splatting: 'Projeter l’enveloppe volumétrique par Gaussian Splats puis générer les maillages 3D haute précision.',
      pbr_materials: 'Attribuer les matériaux techniques par fonction (alliage structurel, acier sur portées, polymère sur carters).',
      assembly_verification: 'Valider l’absence d’interférence géométrique sur toute la course, l’ordre de montage et la nomenclature BOM.',
    }
    const formattedMasterPrompt = [
      `# PROMPT MAÎTRE D'INGÉNIERIE & 3D — ${clean.toUpperCase()}`,
      '',
      `## 1. Objectif & Architecture Système`,
      `Concevoir un système mécanique complet et vérifié pour : « ${clean} », avec séparation claire des organes fixes et mobiles.`,
      '',
      `## 2. Division par Sous-Agents Spécialisés`,
      `- **[Agent 01 · Morphologie & Cinématique]** : ${subAgentDirectives.morphology_kinematics}`,
      `- **[Agent 02 · Ingénierie Mécanique & Tolérances]** : ${subAgentDirectives.mechanical_cad}`,
      `- **[Agent 03 · Sculpture Volumétrique & Splatting]** : ${subAgentDirectives.volumetric_splatting}`,
      `- **[Agent 04 · Matériaux PBR & Zones Fonctionnelles]** : ${subAgentDirectives.pbr_materials}`,
      `- **[Agent 05 · Assemblage, Cinématique & Conformité]** : ${subAgentDirectives.assembly_verification}`,
      '',
      `## 3. Contraintes Techniques Auto-Inférées`,
      ...inferredConstraints.map((c) => `- ${c}`),
    ].join('\n')

    return {
      rawPrompt: clean,
      subjectTitle: isArm ? `Système Robotique Articulé — ${clean.slice(0, 48)}` : `Mécanisme de Précision — ${clean.slice(0, 48)}`,
      archetype,
      complexityLevel: 'ingénierie_complexe',
      inferredConstraints,
      kinematicChainSummary: isArm
        ? 'Embase fixe → Tourelle Z → Épaule Y → Coude Y → Poignet 2 axes → Pince/Effecteur'
        : 'Bâti fixe → Arbre primaire → Train d’engrenages → Sortie guidée',
      dimensionalEnvelopeMm: isArm ? [210, 140, 180] : [140, 110, 65],
      degreesOfFreedom: isArm ? 6 : 3,
      subAgentDirectives,
      formattedMasterPrompt,
    }
  }

  const inferredConstraints = [
    `Fidélité structurelle et silhouette nette pour « ${clean} », sans éléments parasites ni géométrie flottante.`,
    'Proportions cohérentes, symétrie bilatérale ou axiale respectée sur les éléments structurels.',
    'Séparation lisible des sous-parties fonctionnelles, épaisseur minimale 2,0 mm pour les zones fines.',
    'Texturage PBR multi-zones haute définition et maillage GLB/STL étanche prêt pour inspection 3D et fabrication.',
  ]
  const subAgentDirectives: Record<SubAgentId, string> = {
    morphology_kinematics: `Analyser l'anatomie/structure de « ${clean} », isoler les sous-ensembles et préparer la posture ou cinématique.`,
    mechanical_cad: 'Vérifier les proportions, les épaisseurs minimales, les points d’ancrage et la stabilité géométrique.',
    volumetric_splatting: 'Construire le champ de Gaussian Splats de prévisualisation puis extraire le maillage 3D dense.',
    pbr_materials: 'Générer les textures et matériaux PBR fidèles par zones (rugosité, métallicité, émission).',
    assembly_verification: 'Contrôler la qualité topologique (watertight, 0 floater), appliquer le rig/mouvement et livrer le modèle.',
  }
  const formattedMasterPrompt = [
    `# PROMPT MAÎTRE 3D & INGÉNIERIE — ${clean.toUpperCase()}`,
    '',
    `## 1. Objectif Principal`,
    `Produire un modèle 3D haute fidélité et structurellement cohérent pour : « ${clean} ».`,
    '',
    `## 2. Division par Sous-Agents Spécialisés`,
    `- **[Agent 01 · Morphologie & Cinématique]** : ${subAgentDirectives.morphology_kinematics}`,
    `- **[Agent 02 · Architecture & Proportions]** : ${subAgentDirectives.mechanical_cad}`,
    `- **[Agent 03 · Sculpture Volumétrique & Splatting]** : ${subAgentDirectives.volumetric_splatting}`,
    `- **[Agent 04 · Matériaux PBR & Zones Visuelles]** : ${subAgentDirectives.pbr_materials}`,
    `- **[Agent 05 · Contrôle Qualité & Livraison]** : ${subAgentDirectives.assembly_verification}`,
    '',
    `## 3. Contraintes Auto-Inférées`,
    ...inferredConstraints.map((c) => `- ${c}`),
  ].join('\n')

  return {
    rawPrompt: clean,
    subjectTitle: clean.length > 56 ? `${clean.slice(0, 56)}…` : clean,
    archetype,
    complexityLevel: clean.length > 60 ? 'ingénierie_complexe' : 'avancé',
    inferredConstraints,
    kinematicChainSummary: 'Racine principale → Sous-ensembles structurels → Surfaces fonctionnelles détaillées',
    dimensionalEnvelopeMm: [180, 140, 120],
    degreesOfFreedom: archetype === 'vehicle_drone' ? 4 : archetype === 'humanoid_character' ? 12 : 2,
    subAgentDirectives,
    formattedMasterPrompt,
  }
}

const AGENT_RANGES: Array<{
  id: SubAgentId
  index: number
  codeName: string
  role: string
  specialty: string
  startPct: number
  endPct: number
  accentColor: string
}> = [
  {
    id: 'morphology_kinematics',
    index: 1,
    codeName: 'AGENT-01 · ATLAS-KINEMATICS',
    role: 'Architecte Morphologique & Cinématique',
    specialty: 'Topologie, chaînes articulaires, DDL & proportions',
    startPct: 0,
    endPct: 22,
    accentColor: '#38bdf8',
  },
  {
    id: 'mechanical_cad',
    index: 2,
    codeName: 'AGENT-02 · MECANO-CAD',
    role: 'Ingénieur Mécanique & Tolérances',
    specialty: 'Cotes mm, jeux fonctionnels, visserie M3 & références',
    startPct: 18,
    endPct: 45,
    accentColor: '#a78bfa',
  },
  {
    id: 'volumetric_splatting',
    index: 3,
    codeName: 'AGENT-03 · GAUSSIAN-SCULPT',
    role: 'Sculpteur Volumétrique & Splatting 3D',
    specialty: 'Champ Gaussian Splats, reconstruction TRELLIS / CAO & maillage étanche',
    startPct: 40,
    endPct: 75,
    accentColor: '#f59e0b',
  },
  {
    id: 'pbr_materials',
    index: 4,
    codeName: 'AGENT-04 · SHADER-PBR',
    role: 'Maître Matériaux PBR & Zones',
    specialty: 'Segmentation matériaux, textures, métallicité & couleurs par pièce',
    startPct: 70,
    endPct: 90,
    accentColor: '#ec4899',
  },
  {
    id: 'assembly_verification',
    index: 5,
    codeName: 'AGENT-05 · QA-ASSEMBLY',
    role: 'Contrôleur Assemblage & Conformité',
    specialty: 'Tests géométriques, non-collision, rig/mouvement & archive livrable',
    startPct: 86,
    endPct: 100,
    accentColor: '#34d399',
  },
]

export function computeSubAgentsForProgress(
  blueprint: MasterPromptBlueprint,
  overallPercent: number,
  phaseLabel: string,
  extra?: {
    stlCount?: number
    verifiedCriteriaCount?: number
    totalCriteriaCount?: number
  },
): ThreeDSubAgentState[] {
  const pct = Math.max(0, Math.min(100, overallPercent))
  const stlCount = extra?.stlCount ?? 0
  const verifiedCount = extra?.verifiedCriteriaCount ?? 0
  const totalCriteria = extra?.totalCriteriaCount ?? 0

  return AGENT_RANGES.map((meta) => {
    const span = Math.max(1, meta.endPct - meta.startPct)
    let agentPct = 0
    let status: SubAgentStatus = 'queued'

    if (pct >= meta.endPct) {
      agentPct = 100
      status = 'done'
    } else if (pct >= meta.startPct) {
      agentPct = Math.max(8, Math.min(98, Math.round(((pct - meta.startPct) / span) * 100)))
      status = 'working'
    } else {
      agentPct = 0
      status = 'queued'
    }

    const directive = blueprint.subAgentDirectives[meta.id]
    let currentTask = directive
    if (status === 'working' && phaseLabel) {
      currentTask = phaseLabel
    } else if (status === 'done') {
      if (meta.id === 'morphology_kinematics') {
        currentTask = `Cinématique verrouillée (${blueprint.degreesOfFreedom} DDL · ${blueprint.kinematicChainSummary.split('→').length} niveaux)`
      } else if (meta.id === 'mechanical_cad') {
        currentTask = `Enveloppe ${blueprint.dimensionalEnvelopeMm.join('×')} mm & jeux calibrés`
      } else if (meta.id === 'volumetric_splatting') {
        currentTask = stlCount > 0 ? `${stlCount} solide(s) STL/GLB reconstruits sur disque` : 'Géométrie 3D principale générée'
      } else if (meta.id === 'pbr_materials') {
        currentTask = 'Zones matérielles et couleurs PBR appliquées'
      } else {
        currentTask =
          totalCriteria > 0
            ? `Conformité validée (${verifiedCount}/${totalCriteria} critères)`
            : 'Contrôle qualité finalisé — prêt pour le viewer'
      }
    }

    const decisions: string[] = [directive]
    if (meta.id === 'morphology_kinematics') {
      decisions.push(`Chaîne : ${blueprint.kinematicChainSummary}`)
    } else if (meta.id === 'mechanical_cad') {
      decisions.push(`Enveloppe cible : ${blueprint.dimensionalEnvelopeMm.join(' × ')} mm`)
    } else if (meta.id === 'volumetric_splatting' && stlCount > 0) {
      decisions.push(`Solides générés sur le PC : ${stlCount} fichier(s)`)
    } else if (meta.id === 'assembly_verification' && totalCriteria > 0) {
      decisions.push(`Preuves géométriques : ${verifiedCount}/${totalCriteria} vérifiées`)
    }

    return {
      id: meta.id,
      index: meta.index,
      codeName: meta.codeName,
      role: meta.role,
      specialty: meta.specialty,
      status,
      progressPct: agentPct,
      currentTask,
      deliverableSummary: directive,
      decisions,
      accentColor: meta.accentColor,
    }
  })
}

/**
 * Génère un nuage 3D de Gaussian Splats déterministe adapté à l'archétype du sujet.
 * Pour une "main robotisée", construit une vraie main articulée en 3D avec :
 * - Paume métacarpienne + poignet mécatronique
 * - 5 doigts (pouce opposable + index, majeur, annulaire, auriculaire)
 * - 3 phalanges par doigt + anneaux d'articulation (isJoint=true)
 * - Lignes de tendons/actionneurs internes
 */
export function generateHolographicSplats(archetype: SplatArchetype, count = 1800): HolographicSplatPoint[] {
  const points: HolographicSplatPoint[] = []
  // PRNG déterministe rapide (mulberry32)
  let seed = 0x6d2b79f5
  const rand = () => {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  if (archetype === 'robotic_hand') {
    // 1. Poignet / embase mécatronique (y de -0.82 à -0.48)
    for (let i = 0; i < 240; i++) {
      const angle = rand() * Math.PI * 2
      const r = 0.22 + (rand() - 0.5) * 0.04
      const y = -0.82 + rand() * 0.34
      points.push({
        x: Math.cos(angle) * r * 1.15,
        y,
        z: Math.sin(angle) * r * 0.72,
        radius: 1.8 + rand() * 1.6,
        color: i % 7 === 0 ? '#a78bfa' : '#38bdf8',
        partGroup: 'wrist_actuator',
        solidifyThreshold: 0.1 + rand() * 0.35,
      })
    }

    // 2. Paume structurelle (y de -0.48 à +0.08, x de -0.36 à +0.36, z de -0.11 à +0.11)
    for (let i = 0; i < 480; i++) {
      const u = (rand() - 0.5) * 2 // [-1..1]
      const v = rand() // [0..1]
      const widthAtY = 0.32 + v * 0.08
      const x = u * widthAtY
      const y = -0.48 + v * 0.56
      const zShell = (rand() > 0.5 ? 1 : -1) * (0.07 + rand() * 0.045) * (1 - 0.25 * u * u)
      points.push({
        x,
        y,
        z: zShell,
        radius: 2.0 + rand() * 1.8,
        color: Math.abs(u) > 0.75 ? '#60a5fa' : v > 0.82 ? '#34d399' : '#38bdf8',
        partGroup: 'palm_chassis',
        solidifyThreshold: 0.15 + rand() * 0.45,
      })
    }

    // 3. Les 5 doigts articulés (0=Pouce, 1=Index, 2=Majeur, 3=Annulaire, 4=Auriculaire)
    const fingerSpecs = [
      { idx: 0, name: 'thumb', baseX: -0.40, baseY: -0.22, baseZ: 0.05, angleZ: 0.52, lengths: [0.22, 0.18, 0.14], radius: 0.058 },
      { idx: 1, name: 'index', baseX: -0.25, baseY: 0.08, baseZ: 0.0, angleZ: 0.08, lengths: [0.25, 0.19, 0.14], radius: 0.050 },
      { idx: 2, name: 'middle', baseX: -0.07, baseY: 0.11, baseZ: 0.0, angleZ: 0.01, lengths: [0.28, 0.21, 0.15], radius: 0.052 },
      { idx: 3, name: 'ring', baseX: 0.11, baseY: 0.09, baseZ: 0.0, angleZ: -0.05, lengths: [0.25, 0.19, 0.14], radius: 0.049 },
      { idx: 4, name: 'pinky', baseX: 0.28, baseY: 0.04, baseZ: -0.01, angleZ: -0.13, lengths: [0.20, 0.15, 0.12], radius: 0.044 },
    ]

    for (const f of fingerSpecs) {
      let curX = f.baseX
      let curY = f.baseY
      let curZ = f.baseZ

      for (let pIdx = 0; pIdx < 3; pIdx++) {
        const segLen = f.lengths[pIdx]
        const segRad = f.radius * (1 - pIdx * 0.14)
        const dirX = -Math.sin(f.angleZ)
        const dirY = Math.cos(f.angleZ)

        // Anneau d'articulation (Joint pivot)
        for (let j = 0; j < 28; j++) {
          const a = (j / 28) * Math.PI * 2
          points.push({
            x: curX + Math.cos(a) * segRad * 1.15,
            y: curY + (rand() - 0.5) * 0.018,
            z: curZ + Math.sin(a) * segRad * 1.15,
            radius: 2.5 + rand() * 1.2,
            color: '#f59e0b',
            partGroup: `${f.name}_joint_${pIdx + 1}`,
            solidifyThreshold: 0.05 + pIdx * 0.12,
            isJoint: true,
            fingerIdx: f.idx,
            phalangeIdx: pIdx,
          })
        }

        // Corps de la phalange (coque cylindrique + tendon central)
        const splatsPerPhalange = 56
        for (let s = 0; s < splatsPerPhalange; s++) {
          const t = rand()
          const a = rand() * Math.PI * 2
          const isTendon = s < 10
          const r = isTendon ? rand() * 0.012 : segRad * (0.88 + rand() * 0.2)
          const px = curX + dirX * (t * segLen) + Math.cos(a) * r
          const py = curY + dirY * (t * segLen)
          const pz = curZ + Math.sin(a) * r
          points.push({
            x: px,
            y: py,
            z: pz,
            radius: isTendon ? 1.6 : 1.9 + rand() * 1.5,
            color: isTendon
              ? '#ec4899'
              : pIdx === 2 && t > 0.72
                ? '#34d399' // Capteur tactile bout de doigt
                : '#7dd3fc',
            partGroup: `${f.name}_phalange_${pIdx + 1}`,
            solidifyThreshold: 0.2 + pIdx * 0.22 + rand() * 0.25,
            fingerIdx: f.idx,
            phalangeIdx: pIdx,
          })
        }

        curX += dirX * segLen
        curY += dirY * segLen
      }
    }
    return points
  }

  if (archetype === 'gear_mechanism' || archetype === 'robotic_arm') {
    for (let i = 0; i < count; i++) {
      const ring = i % 3
      const angle = (i / count) * Math.PI * 18 + rand() * 0.2
      const baseR = ring === 0 ? 0.55 : ring === 1 ? 0.32 : 0.16
      const tooth = Math.sin(angle * 12) > 0.3 ? 0.07 : 0
      const r = baseR + tooth + (rand() - 0.5) * 0.03
      const y = (ring - 1) * 0.24 + (rand() - 0.5) * 0.14
      points.push({
        x: Math.cos(angle) * r,
        y,
        z: Math.sin(angle) * r,
        radius: 1.9 + rand() * 1.8,
        color: ring === 0 ? '#38bdf8' : ring === 1 ? '#f59e0b' : '#a78bfa',
        partGroup: `stage_${ring}`,
        solidifyThreshold: rand() * 0.85,
        isJoint: ring === 2 && i % 9 === 0,
      })
    }
    return points
  }

  // Archétype général : sculpture volumétrique multi-couches avec anneaux d'analyse
  for (let i = 0; i < count; i++) {
    const u = rand()
    const v = rand()
    const theta = u * 2.0 * Math.PI
    const phi = Math.acos(2.0 * v - 1.0)
    const harmonic = 0.52 + 0.16 * Math.sin(phi * 3) * Math.cos(theta * 2)
    const x = harmonic * Math.sin(phi) * Math.cos(theta)
    const y = (harmonic * Math.cos(phi)) * 1.2
    const z = harmonic * Math.sin(phi) * Math.sin(theta)
    points.push({
      x,
      y,
      z,
      radius: 1.8 + rand() * 2.0,
      color: y > 0.25 ? '#38bdf8' : y > -0.2 ? '#a78bfa' : '#34d399',
      partGroup: y > 0 ? 'upper_shell' : 'lower_base',
      solidifyThreshold: rand() * 0.9,
      isJoint: i % 45 === 0,
    })
  }
  return points
}

export function readPersistedThreeDMission(): PersistedThreeDMissionState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedThreeDMissionState
    if (!parsed || typeof parsed.startedAtMs !== 'number' || !parsed.masterBlueprint) return null
    return parsed
  } catch {
    return null
  }
}

export function writePersistedThreeDMission(state: PersistedThreeDMissionState | null): void {
  if (typeof window === 'undefined') return
  try {
    if (!state) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    }
    window.dispatchEvent(new CustomEvent(MISSION_EVENT, { detail: state }))
  } catch {
    /* ignore storage quota */
  }
}

export function startOrUpdateThreeDMission(params: {
  rawPrompt: string
  mode: 'mesh_3d' | 'engineering_cad'
  phaseLabel: string
  phasePercent: number
  active?: boolean
  startedAtMs?: number
  estimatedTotalSeconds?: number
  stlCount?: number
  verifiedCriteriaCount?: number
  totalCriteriaCount?: number
  completedMeshUrl?: string | null
  completedViewerUrl?: string | null
}): PersistedThreeDMissionState {
  const existing = readPersistedThreeDMission()
  const cleanPrompt = (params.rawPrompt || existing?.rawPrompt || 'Projet 3D').trim()
  const sameMission =
    existing &&
    existing.active &&
    existing.mode === params.mode &&
    (existing.rawPrompt === cleanPrompt || !params.rawPrompt.trim())

  const startedAtMs =
    params.startedAtMs ??
    (sameMission && existing.startedAtMs > 0 ? existing.startedAtMs : Date.now())

  const masterBlueprint =
    sameMission && existing.masterBlueprint.rawPrompt === cleanPrompt
      ? existing.masterBlueprint
      : synthesizeThreeDMasterPrompt(cleanPrompt)

  // Ne jamais faire régresser le pourcentage vers 0 en cours de route
  const rawPct = typeof params.phasePercent === 'number' ? params.phasePercent : 0
  const monotonicPct =
    sameMission && rawPct === 0 && existing.phasePercent > 0
      ? existing.phasePercent
      : Math.max(sameMission ? Math.min(existing.phasePercent, 95) : 0, Math.min(100, rawPct))

  const stlCount = params.stlCount ?? (sameMission ? existing.stlCount : 0)
  const verifiedCriteriaCount =
    params.verifiedCriteriaCount ?? (sameMission ? existing.verifiedCriteriaCount : 0)
  const totalCriteriaCount =
    params.totalCriteriaCount ?? (sameMission ? existing.totalCriteriaCount : 0)

  const subAgents = computeSubAgentsForProgress(
    masterBlueprint,
    monotonicPct,
    params.phaseLabel || existing?.phaseLabel || 'Initialisation des sous-agents…',
    { stlCount, verifiedCriteriaCount, totalCriteriaCount },
  )

  const defaultEstimate =
    params.mode === 'engineering_cad'
      ? 240
      : masterBlueprint.complexityLevel === 'ingénierie_complexe'
        ? 420
        : 300

  const nextState: PersistedThreeDMissionState = {
    missionKey: sameMission ? existing.missionKey : `mission_${startedAtMs}`,
    rawPrompt: cleanPrompt,
    mode: params.mode,
    active: params.active ?? true,
    startedAtMs,
    lastHeartbeatMs: Date.now(),
    phaseLabel: params.phaseLabel || existing?.phaseLabel || 'Exécution en cours…',
    phasePercent: monotonicPct,
    estimatedTotalSeconds: params.estimatedTotalSeconds ?? existing?.estimatedTotalSeconds ?? defaultEstimate,
    stlCount,
    verifiedCriteriaCount,
    totalCriteriaCount,
    masterBlueprint,
    subAgents,
    completedMeshUrl: params.completedMeshUrl ?? existing?.completedMeshUrl ?? null,
    completedViewerUrl: params.completedViewerUrl ?? existing?.completedViewerUrl ?? null,
  }

  writePersistedThreeDMission(nextState)
  return nextState
}

export function completeThreeDMission(result?: {
  meshUrl?: string | null
  viewerUrl?: string | null
  phaseLabel?: string
}): void {
  const existing = readPersistedThreeDMission()
  if (!existing) return
  const subAgents = computeSubAgentsForProgress(
    existing.masterBlueprint,
    100,
    result?.phaseLabel || 'Livrable 3D finalisé et vérifié',
    {
      stlCount: existing.stlCount,
      verifiedCriteriaCount: existing.totalCriteriaCount || existing.verifiedCriteriaCount,
      totalCriteriaCount: existing.totalCriteriaCount,
    },
  )
  writePersistedThreeDMission({
    ...existing,
    active: false,
    lastHeartbeatMs: Date.now(),
    phaseLabel: result?.phaseLabel || 'Livrable 3D finalisé et vérifié',
    phasePercent: 100,
    subAgents,
    completedMeshUrl: result?.meshUrl ?? existing.completedMeshUrl ?? null,
    completedViewerUrl: result?.viewerUrl ?? existing.completedViewerUrl ?? null,
  })
}

export function subscribeThreeDMission(
  callback: (state: PersistedThreeDMissionState | null) => void,
): () => void {
  if (typeof window === 'undefined') return () => {}
  const handler = (ev: Event) => {
    const detail = (ev as CustomEvent<PersistedThreeDMissionState | null>).detail
    callback(detail ?? readPersistedThreeDMission())
  }
  const storageHandler = (ev: StorageEvent) => {
    if (ev.key === STORAGE_KEY) {
      callback(readPersistedThreeDMission())
    }
  }
  window.addEventListener(MISSION_EVENT, handler)
  window.addEventListener('storage', storageHandler)
  return () => {
    window.removeEventListener(MISSION_EVENT, handler)
    window.removeEventListener('storage', storageHandler)
  }
}

export function computeLiveMissionTiming(
  mission: PersistedThreeDMissionState | null,
  nowMs = Date.now(),
  serverElapsedSeconds?: number | null,
  serverRemainingSeconds?: number | null,
): {
  elapsedSeconds: number
  remainingSeconds: number
  formattedElapsed: string
  formattedRemaining: string
  heartbeatAgeSeconds: number
  isAlive: boolean
} {
  const localElapsed = mission?.startedAtMs
    ? Math.max(0, Math.floor((nowMs - mission.startedAtMs) / 1000))
    : 0
  const elapsedSeconds =
    typeof serverElapsedSeconds === 'number' && Number.isFinite(serverElapsedSeconds)
      ? Math.max(localElapsed, Math.floor(serverElapsedSeconds))
      : localElapsed

  const pct = Math.max(2, Math.min(99, mission?.phasePercent || 8))
  const baseTotal = mission?.estimatedTotalSeconds || 300
  let remainingSeconds: number
  if (typeof serverRemainingSeconds === 'number' && Number.isFinite(serverRemainingSeconds) && serverRemainingSeconds > 0) {
    // Fait décrémenter de manière fluide entre deux polls serveur
    const sinceHeartbeat = mission?.lastHeartbeatMs
      ? Math.max(0, Math.floor((nowMs - mission.lastHeartbeatMs) / 1000))
      : 0
    remainingSeconds = Math.max(5, Math.floor(serverRemainingSeconds) - sinceHeartbeat)
  } else {
    const projectedTotal =
      pct >= 15 && elapsedSeconds > 12
        ? Math.round(elapsedSeconds / (pct / 100))
        : Math.max(baseTotal, elapsedSeconds + 45)
    remainingSeconds = Math.max(8, projectedTotal - elapsedSeconds)
  }

  const formatDuration = (sec: number) => {
    const s = Math.max(0, Math.floor(sec))
    const m = Math.floor(s / 60)
    const r = s % 60
    if (m >= 60) {
      const h = Math.floor(m / 60)
      const rm = m % 60
      return `${h}h ${String(rm).padStart(2, '0')}m ${String(r).padStart(2, '0')}s`
    }
    return m > 0 ? `${String(m).padStart(2, '0')}m ${String(r).padStart(2, '0')}s` : `${r}s`
  }

  const heartbeatAgeSeconds = mission?.lastHeartbeatMs
    ? Math.max(0, Math.floor((nowMs - mission.lastHeartbeatMs) / 1000))
    : 0

  return {
    elapsedSeconds,
    remainingSeconds,
    formattedElapsed: formatDuration(elapsedSeconds),
    formattedRemaining: `~${formatDuration(remainingSeconds)}`,
    heartbeatAgeSeconds,
    isAlive: heartbeatAgeSeconds < 120,
  }
}
