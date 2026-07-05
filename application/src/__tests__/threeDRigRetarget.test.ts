/**
 * Tests pour services/threeDRigRetarget — retargeting d'animations entre rigs.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  MIXAMO_TO_AURORA,
  VRM_TO_AURORA,
  detectNamingConvention,
  planRetarget,
  retargetAnimation,
  sampleAnimation,
  rigBoneIds,
  type Animation,
  type Quaternion,
} from '../services/threeDRigRetarget.ts'
import { humanoidMixamoRig, staticRig } from '../services/threeDLodAndRig.ts'

const IDENTITY: Quaternion = [0, 0, 0, 1]

describe('MIXAMO_TO_AURORA registry', () => {
  test('Hips, Spine et Head présents', () => {
    assert.equal(MIXAMO_TO_AURORA['mixamorig:Hips'], 'Hips')
    assert.equal(MIXAMO_TO_AURORA['mixamorig:Spine'], 'Spine')
    assert.equal(MIXAMO_TO_AURORA['mixamorig:Head'], 'Head')
  })

  test('bras gauche complet (Shoulder, Arm, ForeArm, Hand)', () => {
    assert.equal(MIXAMO_TO_AURORA['mixamorig:LeftShoulder'], 'LeftShoulder')
    assert.equal(MIXAMO_TO_AURORA['mixamorig:LeftArm'], 'LeftArm')
    assert.equal(MIXAMO_TO_AURORA['mixamorig:LeftForeArm'], 'LeftForeArm')
    assert.equal(MIXAMO_TO_AURORA['mixamorig:LeftHand'], 'LeftHand')
  })
})

describe('VRM_TO_AURORA registry', () => {
  test('hips/spine/head', () => {
    assert.equal(VRM_TO_AURORA['hips'], 'Hips')
    assert.equal(VRM_TO_AURORA['head'], 'Head')
  })

  test('upperArm + lowerArm mappés', () => {
    assert.equal(VRM_TO_AURORA['leftUpperArm'], 'LeftArm')
    assert.equal(VRM_TO_AURORA['leftLowerArm'], 'LeftForeArm')
  })
})

describe('detectNamingConvention', () => {
  test('Mixamo détecté par préfixe mixamorig:', () => {
    const r = detectNamingConvention(['mixamorig:Hips', 'mixamorig:Spine'])
    assert.equal(r.convention, 'mixamo')
  })

  test('VRM détecté par hips + leftUpperArm', () => {
    const r = detectNamingConvention(['hips', 'leftUpperArm', 'rightUpperArm'])
    assert.equal(r.convention, 'vrm')
  })

  test('Aurora identifié par Hips + LeftArm', () => {
    const r = detectNamingConvention(['Hips', 'LeftArm', 'RightArm'])
    assert.equal(r.convention, 'aurora')
    // identity mapping
    assert.equal(r.mapping['Hips'], 'Hips')
  })

  test('convention inconnue → unknown + mapping vide', () => {
    const r = detectNamingConvention(['root_bone', 'random_xyz'])
    assert.equal(r.convention, 'unknown')
    assert.deepEqual(r.mapping, {})
  })

  test('liste vide → unknown', () => {
    const r = detectNamingConvention([])
    assert.equal(r.convention, 'unknown')
  })
})

describe('planRetarget', () => {
  const targetRig = humanoidMixamoRig()
  const targetIds = rigBoneIds(targetRig)

  test('source Mixamo → matches sur Aurora', () => {
    const sourceIds = ['mixamorig:Hips', 'mixamorig:Spine', 'mixamorig:Head']
    const r = planRetarget(sourceIds, targetRig)
    assert.equal(r.matched.length, 3)
    assert.ok(r.matched.some((m) => m.targetId === 'Hips'))
    assert.equal(r.rootMapped, true)
  })

  test('source Aurora → identity mapping', () => {
    const sourceIds = ['Hips', 'Spine', 'Head', 'LeftArm']
    const r = planRetarget(sourceIds, targetRig)
    assert.equal(r.matched.length, 4)
    assert.equal(r.rootMapped, true)
  })

  test('bones inconnus → orphaned', () => {
    const sourceIds = ['random_bone', 'mixamorig:Hips']
    const r = planRetarget(sourceIds, targetRig)
    assert.ok(r.orphaned.includes('random_bone'))
    assert.equal(r.matched.length, 1)
  })

  test('unanimated = bones target non-matchés', () => {
    const sourceIds = ['mixamorig:Hips'] // just hips → tous les autres targets inanimés
    const r = planRetarget(sourceIds, targetRig)
    assert.ok(r.unanimated.length >= targetIds.length - 1)
  })

  test('static rig → rootMapped=true par défaut', () => {
    const r = planRetarget(['mixamorig:Hips'], staticRig())
    assert.equal(r.rootMapped, true)
  })

  test('Hips absent → rootMapped false (sauf static)', () => {
    const r = planRetarget(['mixamorig:LeftArm'], targetRig)
    assert.equal(r.rootMapped, false)
  })
})

describe('retargetAnimation', () => {
  const targetRig = humanoidMixamoRig()

  test('animation 1 frame retargetée correctement', () => {
    const sourceIds = ['mixamorig:Hips', 'mixamorig:LeftArm']
    const anim: Animation = {
      name: 'test',
      duration: 1,
      loop: true,
      frames: [{
        t: 0,
        rotations: { 'mixamorig:Hips': [0, 1, 0, 0], 'mixamorig:LeftArm': [1, 0, 0, 0] },
      }],
    }
    const { animation, report } = retargetAnimation(anim, sourceIds, targetRig)
    assert.deepEqual(animation.frames[0].rotations['Hips'], [0, 1, 0, 0])
    assert.deepEqual(animation.frames[0].rotations['LeftArm'], [1, 0, 0, 0])
    assert.equal(report.matched.length, 2)
  })

  test('bones target non-matchés → quaternion identité', () => {
    const sourceIds = ['mixamorig:Hips']
    const anim: Animation = {
      name: 'h',
      duration: 1,
      loop: false,
      frames: [{ t: 0, rotations: { 'mixamorig:Hips': [0, 0, 0, 1] } }],
    }
    const { animation } = retargetAnimation(anim, sourceIds, targetRig)
    // LeftArm doit être identité (pas mappé)
    assert.deepEqual(animation.frames[0].rotations['LeftArm'], IDENTITY)
  })

  test('rootPosition préservée', () => {
    const anim: Animation = {
      name: 'h',
      duration: 1,
      loop: false,
      frames: [{ t: 0, rotations: { 'mixamorig:Hips': IDENTITY }, rootPosition: [0, 1.5, 0] }],
    }
    const { animation } = retargetAnimation(anim, ['mixamorig:Hips'], targetRig)
    assert.deepEqual(animation.frames[0].rootPosition, [0, 1.5, 0])
  })

  test('duration et loop préservés', () => {
    const anim: Animation = { name: 'x', duration: 2.5, loop: true, frames: [] }
    const { animation } = retargetAnimation(anim, [], targetRig)
    assert.equal(animation.duration, 2.5)
    assert.equal(animation.loop, true)
  })
})

describe('sampleAnimation', () => {
  const animation: Animation = {
    name: 'test',
    duration: 1,
    loop: false,
    frames: [
      { t: 0, rotations: { 'Hips': [0, 0, 0, 1] } },
      { t: 0.5, rotations: { 'Hips': [1, 0, 0, 0] } },
      { t: 1, rotations: { 'Hips': [0, 0, 1, 0] } },
    ],
  }

  test('t=0 → première frame', () => {
    const q = sampleAnimation(animation, 'Hips', 0)
    assert.deepEqual(q, [0, 0, 0, 1])
  })

  test('t=duration → dernière frame', () => {
    const q = sampleAnimation(animation, 'Hips', 1)
    assert.deepEqual(q, [0, 0, 1, 0])
  })

  test('t intermédiaire → quaternion interpolé normalisé', () => {
    const q = sampleAnimation(animation, 'Hips', 0.25)
    const len = Math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    assert.ok(Math.abs(len - 1) < 1e-6, `quat not normalised len=${len}`)
  })

  test('animation vide → identité', () => {
    const empty: Animation = { name: 'e', duration: 1, loop: false, frames: [] }
    const q = sampleAnimation(empty, 'Hips', 0.5)
    assert.deepEqual(q, IDENTITY)
  })

  test('loop=true → t > duration wrap', () => {
    const looping: Animation = { ...animation, loop: true }
    const a = sampleAnimation(looping, 'Hips', 0.25)
    const b = sampleAnimation(looping, 'Hips', 1.25)
    // Same modulo 1
    assert.deepEqual(a, b)
  })

  test('loop=false → t > duration clamp à dernière frame', () => {
    const q = sampleAnimation(animation, 'Hips', 5)
    assert.deepEqual(q, [0, 0, 1, 0])
  })

  test('boneId inconnu → identité', () => {
    const q = sampleAnimation(animation, 'NonExistent', 0.5)
    assert.deepEqual(q, IDENTITY)
  })
})

describe('rigBoneIds', () => {
  test('renvoie tous les IDs', () => {
    const rig = humanoidMixamoRig()
    const ids = rigBoneIds(rig)
    assert.equal(ids.length, rig.bones.length)
    assert.ok(ids.includes('Hips'))
  })

  test('rig vide → []', () => {
    const ids = rigBoneIds(staticRig())
    assert.deepEqual(ids, [])
  })
})
