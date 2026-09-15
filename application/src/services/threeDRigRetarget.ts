// Rig retarget — convertit une animation enregistrée sur un squelette source
// vers un squelette cible. Indispensable quand on importe des animations
// Mixamo (.fbx) sur des characters Aurora générés par Hunyuan3D.
//
// Approche : bone-to-bone mapping par tag sémantique (head, spine, arm.l,
// arm.r, …). Si le source et la cible ont les mêmes tags, le retargeting
// est direct. Sinon on tente le matching par nom canonique (Mixamo,
// Aurora, MakeHuman, VRM).

import type { Bone, BoneId, RigDescriptor } from './threeDLodAndRig.ts'

export type Quaternion = [number, number, number, number]

export type PoseFrame = {
  /** Temps en secondes. */
  t: number
  /** Rotation par bone (quaternion XYZW). */
  rotations: Record<BoneId, Quaternion>
  /** Position racine (mètres). */
  rootPosition?: [number, number, number]
}

export type Animation = {
  name: string
  frames: PoseFrame[]
  /** Durée totale en secondes. */
  duration: number
  /** Boucle. */
  loop: boolean
}

export type BoneNameRegistry = Record<string, string>

// Mapping canonique → ID Aurora pour les squelettes connus.
export const MIXAMO_TO_AURORA: BoneNameRegistry = {
  'mixamorig:Hips': 'Hips',
  'mixamorig:Spine': 'Spine',
  'mixamorig:Spine1': 'Spine1',
  'mixamorig:Spine2': 'Spine2',
  'mixamorig:Neck': 'Neck',
  'mixamorig:Head': 'Head',
  'mixamorig:LeftShoulder': 'LeftShoulder',
  'mixamorig:LeftArm': 'LeftArm',
  'mixamorig:LeftForeArm': 'LeftForeArm',
  'mixamorig:LeftHand': 'LeftHand',
  'mixamorig:RightShoulder': 'RightShoulder',
  'mixamorig:RightArm': 'RightArm',
  'mixamorig:RightForeArm': 'RightForeArm',
  'mixamorig:RightHand': 'RightHand',
  'mixamorig:LeftUpLeg': 'LeftUpLeg',
  'mixamorig:LeftLeg': 'LeftLeg',
  'mixamorig:LeftFoot': 'LeftFoot',
  'mixamorig:LeftToeBase': 'LeftToeBase',
  'mixamorig:RightUpLeg': 'RightUpLeg',
  'mixamorig:RightLeg': 'RightLeg',
  'mixamorig:RightFoot': 'RightFoot',
  'mixamorig:RightToeBase': 'RightToeBase',
}

// VRM canonical bones → Aurora.
export const VRM_TO_AURORA: BoneNameRegistry = {
  hips: 'Hips',
  spine: 'Spine',
  chest: 'Spine1',
  upperChest: 'Spine2',
  neck: 'Neck',
  head: 'Head',
  leftShoulder: 'LeftShoulder',
  leftUpperArm: 'LeftArm',
  leftLowerArm: 'LeftForeArm',
  leftHand: 'LeftHand',
  rightShoulder: 'RightShoulder',
  rightUpperArm: 'RightArm',
  rightLowerArm: 'RightForeArm',
  rightHand: 'RightHand',
  leftUpperLeg: 'LeftUpLeg',
  leftLowerLeg: 'LeftLeg',
  leftFoot: 'LeftFoot',
  leftToes: 'LeftToeBase',
  rightUpperLeg: 'RightUpLeg',
  rightLowerLeg: 'RightLeg',
  rightFoot: 'RightFoot',
  rightToes: 'RightToeBase',
}

/**
 * Détecte la convention de naming d'un set de bones source et retourne le
 * registry de conversion approprié.
 */
export function detectNamingConvention(boneIds: string[]): { convention: 'mixamo' | 'vrm' | 'aurora' | 'unknown'; mapping: BoneNameRegistry } {
  const lower = boneIds.map((b) => b.toLowerCase())
  if (lower.some((b) => b.startsWith('mixamorig:'))) {
    return { convention: 'mixamo', mapping: MIXAMO_TO_AURORA }
  }
  if (lower.includes('hips') && lower.includes('leftupperarm')) {
    return { convention: 'vrm', mapping: VRM_TO_AURORA }
  }
  if (boneIds.includes('Hips') && boneIds.includes('LeftArm')) {
    const identity: BoneNameRegistry = {}
    for (const b of boneIds) identity[b] = b
    return { convention: 'aurora', mapping: identity }
  }
  return { convention: 'unknown', mapping: {} }
}

export type RetargetReport = {
  /** Bones de la source effectivement mappées vers la cible. */
  matched: Array<{ sourceId: BoneId; targetId: BoneId }>
  /** Bones source pour lesquels aucun équivalent n'a été trouvé (animation perdue). */
  orphaned: BoneId[]
  /** Bones cible qui n'ont reçu aucune anim (resteront à la pose neutre). */
  unanimated: BoneId[]
  /** True si la racine est mappée correctement (Hips). */
  rootMapped: boolean
}

export function planRetarget(sourceBoneIds: BoneId[], targetRig: RigDescriptor): RetargetReport {
  const { mapping, convention } = detectNamingConvention(sourceBoneIds)
  const targetIds = new Set(targetRig.bones.map((b) => b.id))
  const matched: RetargetReport['matched'] = []
  const orphaned: BoneId[] = []

  for (const sid of sourceBoneIds) {
    const direct = convention === 'aurora' ? sid : mapping[sid]
    if (direct && targetIds.has(direct)) {
      matched.push({ sourceId: sid, targetId: direct })
    } else {
      orphaned.push(sid)
    }
  }
  const animatedTargets = new Set(matched.map((m) => m.targetId))
  const unanimated = targetRig.bones.map((b) => b.id).filter((id) => !animatedTargets.has(id))
  const rootMapped = matched.some((m) => m.targetId === 'Hips') || targetRig.kind === 'static'

  return { matched, orphaned, unanimated, rootMapped }
}

/**
 * Applique le retargeting à une animation. Les frames sont parcourues, et
 * pour chaque rotation source on cherche le mapping vers la cible. Les
 * bones cible sans rotation source reçoivent une rotation identité.
 */
export function retargetAnimation(animation: Animation, sourceBoneIds: BoneId[], targetRig: RigDescriptor): { animation: Animation; report: RetargetReport } {
  const report = planRetarget(sourceBoneIds, targetRig)
  const mappingByLocalId = new Map(report.matched.map((m) => [m.sourceId, m.targetId]))
  const identity: Quaternion = [0, 0, 0, 1]

  const newFrames: PoseFrame[] = animation.frames.map((frame) => {
    const rotations: Record<BoneId, Quaternion> = {}
    for (const bone of targetRig.bones) rotations[bone.id] = identity
    for (const [sid, q] of Object.entries(frame.rotations)) {
      const target = mappingByLocalId.get(sid)
      if (target) rotations[target] = q
    }
    return {
      t: frame.t,
      rotations,
      rootPosition: frame.rootPosition,
    }
  })

  return {
    animation: {
      name: `${animation.name} → ${targetRig.kind}`,
      duration: animation.duration,
      loop: animation.loop,
      frames: newFrames,
    },
    report,
  }
}

/** Sample une rotation interpolée à un temps donné (linear quaternion lerp). */
export function sampleAnimation(animation: Animation, boneId: BoneId, t: number): Quaternion {
  if (animation.frames.length === 0) return [0, 0, 0, 1]

  // Garde-fous sur le temps demande. Trois entrees produisaient un quaternion
  // [NaN, NaN, NaN, NaN] :
  //   - une duree nulle avec `loop` : `t % 0` vaut NaN;
  //   - `t` non fini (NaN, Infinity) : le modulo propage;
  //   - et le NaN traversait ensuite la recherche dichotomique, le ratio
  //     d'interpolation, puis la normalisation.
  //
  // Un quaternion NaN pose sur un os ne « degrade » pas le rendu : la matrice
  // de l'os devient invalide et le maillage qui en depend DISPARAIT, ou part
  // a l'infini. Rien ne signale la cause, et le defaut se lit comme un
  // probleme de maillage alors qu'il vient de l'echantillonnage.
  const duration = Number.isFinite(animation.duration) && animation.duration > 0
    ? animation.duration
    : 0
  const tSain = Number.isFinite(t) ? t : 0
  const time = animation.loop && duration > 0
    ? ((tSain % duration) + duration) % duration
    : Math.min(tSain, duration > 0 ? duration : tSain)
  // Bornes par binary search.
  let lo = 0
  let hi = animation.frames.length - 1
  if (time <= animation.frames[0].t) return animation.frames[0].rotations[boneId] ?? [0, 0, 0, 1]
  if (time >= animation.frames[hi].t) return animation.frames[hi].rotations[boneId] ?? [0, 0, 0, 1]
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (animation.frames[mid].t <= time) lo = mid
    else hi = mid
  }
  const a = animation.frames[lo]
  const b = animation.frames[hi]
  const ratio = (time - a.t) / Math.max(1e-9, b.t - a.t)
  const qa = a.rotations[boneId] ?? [0, 0, 0, 1]
  const qb = b.rotations[boneId] ?? [0, 0, 0, 1]
  const out = quatNLerp(qa, qb, ratio)
  // Dernier filet : une image-cle porteuse d'une valeur non finie ne doit pas
  // ressortir du module. On rend l'identite, qui est visible et corrigeable,
  // plutot qu'un NaN qui fait disparaitre le sujet.
  return out.every(Number.isFinite) ? out : [0, 0, 0, 1]
}

/**
 * Normalised-LERP quaternion : assez précis pour des keyframes proches
 * (clip à 30 fps), beaucoup plus rapide qu'un SLERP, et stable (pas de
 * division par sin(θ) qui explose).
 */
function quatNLerp(a: Quaternion, b: Quaternion, t: number): Quaternion {
  const dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
  // Choisir le chemin court (sphère 4D).
  const sign = dot < 0 ? -1 : 1
  const x = a[0] + t * (sign * b[0] - a[0])
  const y = a[1] + t * (sign * b[1] - a[1])
  const z = a[2] + t * (sign * b[2] - a[2])
  const w = a[3] + t * (sign * b[3] - a[3])
  const len = Math.sqrt(x * x + y * y + z * z + w * w) || 1
  return [x / len, y / len, z / len, w / len]
}

/** Util : ID des bones d'un rig (ce que le caller passe à planRetarget). */
export function rigBoneIds(rig: RigDescriptor): BoneId[] {
  return rig.bones.map((b: Bone) => b.id)
}
