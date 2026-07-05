// 3D : LOD specs + rigging metadata + multi-format export plan.
//
// Demandé par le handoff "expert uplift" (section 3D) :
//   - skeletal rigging Mixamo-like
//   - UV unwrap propre + texture transfer fidèle
//   - LOD generation (2-3 niveaux : 50k, 100k, 200k faces) pour le web
//   - export multi-format (FBX, USD, glTF avec animations, OBJ avec matlib)
//   - validation physique (manifold, no self-intersection, watertight)
//
// Ici on définit les TYPES + GÉNÉRATEURS DE SPECS. La conversion 3D elle-même
// reste côté python-services/Hunyuan3D-2/Blender — ce module produit le plan
// (face budget par LOD, format cibles, contraintes physiques) que le pipeline
// Python applique.

export type Category = 'object' | 'character' | 'vehicle' | 'mech' | 'environment' | 'creature'

export type LodLevel = {
  id: 'lod0' | 'lod1' | 'lod2' | 'lod3'
  /** Distance camera à partir de laquelle ce LOD est actif (m). */
  triggerDistance: number
  /** Budget faces cible. */
  faceBudget: number
  /** Taux de décimation cible vs LOD0 (0..1, 1 = aucun décimation). */
  ratioVsLod0: number
}

/**
 * Plans LOD par catégorie — alignés sur les budgets déjà utilisés
 * (object 140k, character 180k, vehicle 220k, mech 260k).
 */
export function lodPlanForCategory(category: Category): LodLevel[] {
  const baseFaces: Record<Category, number> = {
    object: 140_000,
    character: 180_000,
    vehicle: 220_000,
    mech: 260_000,
    creature: 200_000,
    environment: 320_000,
  }
  const base = baseFaces[category]
  return [
    { id: 'lod0', triggerDistance: 0, faceBudget: base, ratioVsLod0: 1.0 },
    { id: 'lod1', triggerDistance: 5, faceBudget: Math.round(base * 0.55), ratioVsLod0: 0.55 },
    { id: 'lod2', triggerDistance: 15, faceBudget: Math.round(base * 0.28), ratioVsLod0: 0.28 },
    { id: 'lod3', triggerDistance: 40, faceBudget: Math.round(base * 0.12), ratioVsLod0: 0.12 },
  ]
}

// --- Skeletal rigging --------------------------------------------------------
//
// On vise un rig "humanoïde Mixamo-like" pour les characters/creatures, et un
// rig "mécanique simple" (root + articulations) pour les vehicles/mechs.

export type BoneId = string

export type Bone = {
  id: BoneId
  parent: BoneId | null
  /** Position locale par rapport au parent (m). */
  offset: [number, number, number]
  /** Limites de rotation Euler XYZ en radians ([min, max] par axe). */
  rotationLimits?: { x?: [number, number]; y?: [number, number]; z?: [number, number] }
  /** Tag sémantique pour rebinding multi-rig. */
  tag?: 'spine' | 'head' | 'arm' | 'leg' | 'hand' | 'foot' | 'mech-joint' | 'root'
}

export type RigKind = 'humanoid-mixamo' | 'biped-simple' | 'quadruped' | 'mech-articulated' | 'static'

export type RigDescriptor = {
  kind: RigKind
  bones: Bone[]
  /** Hauteur de référence pour rescale (m). */
  referenceHeight: number
  /** IK chains à générer côté Blender. */
  ikChains: Array<{ name: string; root: BoneId; effector: BoneId }>
  /** Set d'animations à supporter (label + durée). */
  animationLibrary: Array<{ name: string; durationMs: number; loops: boolean }>
}

/** Humanoid Mixamo standard 65-bone subset (compatible Auto-Rig). */
export function humanoidMixamoRig(referenceHeight = 1.7): RigDescriptor {
  const b = (id: string, parent: string | null, offset: [number, number, number], tag?: Bone['tag']): Bone => ({ id, parent, offset, tag })
  const bones: Bone[] = [
    b('Hips', null, [0, referenceHeight * 0.52, 0], 'root'),
    b('Spine', 'Hips', [0, 0.1, 0], 'spine'),
    b('Spine1', 'Spine', [0, 0.1, 0], 'spine'),
    b('Spine2', 'Spine1', [0, 0.1, 0], 'spine'),
    b('Neck', 'Spine2', [0, 0.1, 0], 'spine'),
    b('Head', 'Neck', [0, 0.1, 0], 'head'),
    // Left arm
    b('LeftShoulder', 'Spine2', [0.05, 0.08, 0], 'arm'),
    b('LeftArm', 'LeftShoulder', [0.15, 0, 0], 'arm'),
    b('LeftForeArm', 'LeftArm', [0.25, 0, 0], 'arm'),
    b('LeftHand', 'LeftForeArm', [0.2, 0, 0], 'hand'),
    // Right arm
    b('RightShoulder', 'Spine2', [-0.05, 0.08, 0], 'arm'),
    b('RightArm', 'RightShoulder', [-0.15, 0, 0], 'arm'),
    b('RightForeArm', 'RightArm', [-0.25, 0, 0], 'arm'),
    b('RightHand', 'RightForeArm', [-0.2, 0, 0], 'hand'),
    // Left leg
    b('LeftUpLeg', 'Hips', [0.08, 0, 0], 'leg'),
    b('LeftLeg', 'LeftUpLeg', [0, -0.4, 0], 'leg'),
    b('LeftFoot', 'LeftLeg', [0, -0.4, 0.1], 'foot'),
    b('LeftToeBase', 'LeftFoot', [0, -0.05, 0.1], 'foot'),
    // Right leg
    b('RightUpLeg', 'Hips', [-0.08, 0, 0], 'leg'),
    b('RightLeg', 'RightUpLeg', [0, -0.4, 0], 'leg'),
    b('RightFoot', 'RightLeg', [0, -0.4, 0.1], 'foot'),
    b('RightToeBase', 'RightFoot', [0, -0.05, 0.1], 'foot'),
  ]
  return {
    kind: 'humanoid-mixamo',
    bones,
    referenceHeight,
    ikChains: [
      { name: 'LeftArmIK', root: 'LeftArm', effector: 'LeftHand' },
      { name: 'RightArmIK', root: 'RightArm', effector: 'RightHand' },
      { name: 'LeftLegIK', root: 'LeftUpLeg', effector: 'LeftFoot' },
      { name: 'RightLegIK', root: 'RightUpLeg', effector: 'RightFoot' },
    ],
    animationLibrary: [
      { name: 'idle', durationMs: 2000, loops: true },
      { name: 'walk', durationMs: 1200, loops: true },
      { name: 'run', durationMs: 800, loops: true },
      { name: 'wave', durationMs: 1500, loops: false },
      { name: 'jump', durationMs: 700, loops: false },
    ],
  }
}

/** Static rig (no bones) — for non-animated props. */
export function staticRig(referenceHeight = 1): RigDescriptor {
  return { kind: 'static', bones: [], referenceHeight, ikChains: [], animationLibrary: [] }
}

/** Picks the right rig template for a category. */
export function defaultRigForCategory(category: Category, referenceHeight?: number): RigDescriptor {
  if (category === 'character' || category === 'creature') return humanoidMixamoRig(referenceHeight)
  if (category === 'mech' || category === 'vehicle') return {
    kind: 'mech-articulated',
    bones: [
      { id: 'root', parent: null, offset: [0, 0, 0], tag: 'root' },
      { id: 'chassis', parent: 'root', offset: [0, 0.5, 0], tag: 'mech-joint' },
    ],
    referenceHeight: referenceHeight ?? 2,
    ikChains: [],
    animationLibrary: [
      { name: 'idle', durationMs: 3000, loops: true },
      { name: 'mechanical_articulate', durationMs: 2000, loops: true },
    ],
  }
  return staticRig(referenceHeight)
}

// --- Export multi-format plan -----------------------------------------------
export type ExportFormat = 'glb' | 'gltf' | 'fbx' | 'usd' | 'usdz' | 'obj' | 'stl' | 'ply'

export type ExportConfig = {
  format: ExportFormat
  /** Inclure les animations dans cet export. */
  includeAnimations: boolean
  /** Inclure les textures embarquées (sinon référence externe). */
  embedTextures: boolean
  /** Compression Draco / Meshopt (glTF). */
  compression: 'none' | 'draco' | 'meshopt'
  /** Filename suffix. */
  suffix: string
}

/** Plan d'export standard pour un asset 3D complet. */
export function defaultExportPlan(category: Category): ExportConfig[] {
  const isAnimated = category === 'character' || category === 'creature' || category === 'mech' || category === 'vehicle'
  return [
    { format: 'glb', includeAnimations: isAnimated, embedTextures: true, compression: 'meshopt', suffix: '_meshopt.glb' },
    { format: 'glb', includeAnimations: isAnimated, embedTextures: true, compression: 'draco', suffix: '_draco.glb' },
    { format: 'fbx', includeAnimations: isAnimated, embedTextures: false, compression: 'none', suffix: '.fbx' },
    { format: 'usd', includeAnimations: isAnimated, embedTextures: false, compression: 'none', suffix: '.usdc' },
    { format: 'obj', includeAnimations: false, embedTextures: false, compression: 'none', suffix: '.obj' },
  ]
}

// --- Validation physique ----------------------------------------------------
export type MeshValidationIssue =
  | 'non-manifold-edges'
  | 'self-intersections'
  | 'duplicate-vertices'
  | 'inverted-normals'
  | 'open-holes'
  | 'overlapping-uvs'
  | 'face-budget-exceeded'
  | 'missing-uv'

export type MeshValidationReport = {
  manifold: boolean
  watertight: boolean
  issues: MeshValidationIssue[]
  faceCount: number
  vertexCount: number
  /** Volume m³ (négatif = normales inversées). */
  volume: number
  /** Surface m². */
  surfaceArea: number
  /** Échec critique → ne pas exporter. */
  blockingForExport: boolean
}

export type MeshValidationInput = {
  faceCount: number
  vertexCount: number
  nonManifoldEdgeCount: number
  selfIntersectionCount: number
  duplicateVertexCount: number
  invertedNormalCount: number
  openHoleCount: number
  overlappingUvCount: number
  hasUvs: boolean
  volume: number
  surfaceArea: number
  /** Budget faces du LOD0 cible. */
  faceBudgetLod0: number
  /** Mode d'usage final ("preview", "print", "vr") — module les seuils. */
  useCase: 'preview' | 'print' | 'vr' | 'studio'
}

export function validateMesh(input: MeshValidationInput): MeshValidationReport {
  const issues: MeshValidationIssue[] = []
  if (input.nonManifoldEdgeCount > 0) issues.push('non-manifold-edges')
  if (input.selfIntersectionCount > 0) issues.push('self-intersections')
  if (input.duplicateVertexCount > 50) issues.push('duplicate-vertices')
  if (input.invertedNormalCount > 0) issues.push('inverted-normals')
  if (input.openHoleCount > 0) issues.push('open-holes')
  if (input.overlappingUvCount > 0) issues.push('overlapping-uvs')
  if (!input.hasUvs) issues.push('missing-uv')
  if (input.faceCount > input.faceBudgetLod0 * 1.05) issues.push('face-budget-exceeded')

  const manifold = input.nonManifoldEdgeCount === 0 && input.invertedNormalCount === 0
  const watertight = manifold && input.openHoleCount === 0

  // Print needs watertight + manifold ; VR tolerates missing UVs but not budget overrun.
  const blockingForExport = (() => {
    if (input.useCase === 'print') return !watertight
    if (input.useCase === 'vr') return issues.includes('face-budget-exceeded') || !manifold
    if (input.useCase === 'studio') return issues.length === 0 ? false : issues.some((i) => i === 'non-manifold-edges' || i === 'inverted-normals')
    // preview
    return issues.includes('non-manifold-edges') && issues.includes('inverted-normals')
  })()

  return {
    manifold,
    watertight,
    issues,
    faceCount: input.faceCount,
    vertexCount: input.vertexCount,
    volume: input.volume,
    surfaceArea: input.surfaceArea,
    blockingForExport,
  }
}
