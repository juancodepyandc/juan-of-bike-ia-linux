/**
 * Tests barre expert v2 — fonctionnalités avancées :
 *   - drawing auto-layout flowchart
 *   - 3d rig retarget
 *
 * Chaque test définit une barre concrète. Si le service échoue, on itère.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'


import {
  layoutFlowchart,
  layoutRadial,
  layoutToSvg,
} from '../services/drawingAutoLayout.ts'
import { serialise } from '../services/drawingStyleAndSvg.ts'

import {
  detectNamingConvention,
  MIXAMO_TO_AURORA,
  planRetarget,
  retargetAnimation,
  rigBoneIds,
  sampleAnimation,
  VRM_TO_AURORA,
} from '../services/threeDRigRetarget.ts'
import { humanoidMixamoRig, defaultRigForCategory } from '../services/threeDLodAndRig.ts'

// =============================================================================
// DRAWING — auto-layout
// =============================================================================

describe('Drawing auto-layout — barre expert', () => {
  const simpleGraph = {
    nodes: [
      { id: 'start', label: 'Début' },
      { id: 'work', label: 'Travailler' },
      { id: 'check', label: 'OK ?' },
      { id: 'end', label: 'Fin' },
    ],
    edges: [
      { from: 'start', to: 'work' },
      { from: 'work', to: 'check' },
      { from: 'check', to: 'end', label: 'oui' },
      { from: 'check', to: 'work', label: 'non' },
    ],
  }

  test('layout TB place chaque node sur une couche topologique', () => {
    const r = layoutFlowchart(simpleGraph.nodes, [
      { from: 'start', to: 'work' },
      { from: 'work', to: 'check' },
      { from: 'check', to: 'end' },
    ], { direction: 'TB' })
    // Start au-dessus de work, work au-dessus de check, check au-dessus de end.
    const byId = new Map(r.nodes.map((n) => [n.id, n]))
    assert.ok(byId.get('start')!.y < byId.get('work')!.y)
    assert.ok(byId.get('work')!.y < byId.get('check')!.y)
    assert.ok(byId.get('check')!.y < byId.get('end')!.y)
  })

  test('layout LR aligne les couches en colonnes', () => {
    const r = layoutFlowchart(simpleGraph.nodes.slice(0, 3), [
      { from: 'start', to: 'work' },
      { from: 'work', to: 'check' },
    ], { direction: 'LR' })
    const byId = new Map(r.nodes.map((n) => [n.id, n]))
    assert.ok(byId.get('start')!.x < byId.get('work')!.x)
    assert.ok(byId.get('work')!.x < byId.get('check')!.x)
  })

  test('viewBox couvre tous les nodes', () => {
    const r = layoutFlowchart(simpleGraph.nodes, simpleGraph.edges)
    for (const n of r.nodes) {
      assert.ok(n.x >= r.viewBox.x)
      assert.ok(n.y >= r.viewBox.y)
      assert.ok(n.x + n.w <= r.viewBox.x + r.viewBox.w + 1)
      assert.ok(n.y + n.h <= r.viewBox.y + r.viewBox.h + 1)
    }
  })

  test('cycle détecté + layout produit quand même', () => {
    const r = layoutFlowchart(
      [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
      [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }],
    )
    assert.equal(r.hasCycle, true)
    assert.equal(r.nodes.length, 2)
  })

  test('nodes orphelins (sans edges) placés sur leur propre couche', () => {
    const r = layoutFlowchart(
      [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }, { id: 'c', label: 'C' }],
      [{ from: 'a', to: 'b' }],
    )
    // c devrait être placé quelque part valide.
    const c = r.nodes.find((n) => n.id === 'c')
    assert.ok(c)
    assert.ok(Number.isFinite(c.x) && Number.isFinite(c.y))
  })

  test('layoutToSvg produit du SVG valide', () => {
    const r = layoutFlowchart(simpleGraph.nodes, simpleGraph.edges)
    const doc = layoutToSvg(r)
    const xml = serialise(doc)
    assert.ok(xml.startsWith('<?xml'))
    assert.ok(xml.includes('Début'))
    assert.ok(xml.includes('Fin'))
  })

  test('graphe de 50 nodes → viewBox raisonnable', () => {
    const nodes = Array.from({ length: 50 }, (_, i) => ({ id: `n${i}`, label: `Node ${i}` }))
    const edges = Array.from({ length: 49 }, (_, i) => ({ from: `n${i}`, to: `n${i + 1}` }))
    const r = layoutFlowchart(nodes, edges)
    assert.ok(r.viewBox.w > 0 && r.viewBox.h > 0)
    assert.ok(r.viewBox.h < 10000) // 50 couches linéaires devraient rester sous 10k px
  })

  test('layoutRadial : root au centre du canvas', () => {
    const nodes = [
      { id: 'root', label: 'Centre' },
      { id: 'a', label: 'A' },
      { id: 'b', label: 'B' },
      { id: 'c', label: 'C' },
    ]
    const edges = [
      { from: 'root', to: 'a' },
      { from: 'root', to: 'b' },
      { from: 'root', to: 'c' },
    ]
    const r = layoutRadial(nodes, edges, { rootId: 'root', centerX: 400, centerY: 400 })
    const root = r.nodes.find((n) => n.id === 'root')!
    // Root should be near (400-w/2, 400-h/2)
    assert.ok(Math.abs(root.x + root.w / 2 - 400) < 10)
    assert.ok(Math.abs(root.y + root.h / 2 - 400) < 10)
  })

  test('layoutRadial : enfants équidistants du root', () => {
    const nodes = [
      { id: 'root', label: 'C' },
      { id: 'a', label: 'A' },
      { id: 'b', label: 'B' },
      { id: 'c', label: 'C' },
    ]
    const edges = [
      { from: 'root', to: 'a' },
      { from: 'root', to: 'b' },
      { from: 'root', to: 'c' },
    ]
    const r = layoutRadial(nodes, edges, { rootId: 'root', baseRadius: 200, centerX: 0, centerY: 0 })
    const dists = ['a', 'b', 'c'].map((id) => {
      const n = r.nodes.find((x) => x.id === id)!
      return Math.hypot(n.x + n.w / 2, n.y + n.h / 2)
    })
    for (const d of dists) assert.ok(Math.abs(d - 200) < 10, `dist ${d}`)
  })

  test('layoutRadial : root inexistant → fallback layoutFlowchart', () => {
    const nodes = [{ id: 'a', label: 'A' }]
    const r = layoutRadial(nodes, [], { rootId: 'no-such-root' })
    assert.equal(r.nodes.length, 1)
  })

  test('layoutRadial : nodes orphelins placés sur orbite extérieure', () => {
    const nodes = [
      { id: 'root', label: 'C' },
      { id: 'connected', label: 'A' },
      { id: 'orphan', label: 'O' },
    ]
    const r = layoutRadial(
      nodes,
      [{ from: 'root', to: 'connected' }],
      { rootId: 'root', centerX: 400, centerY: 400, baseRadius: 100 },
    )
    const orphan = r.nodes.find((n) => n.id === 'orphan')!
    const distance = Math.hypot(orphan.x + orphan.w / 2 - 400, orphan.y + orphan.h / 2 - 400)
    // Orphan distance >= 100 (base) — should be on outer orbit.
    assert.ok(distance >= 100, `orphan dist ${distance}`)
  })

  test('layoutRadial : viewBox contient tous les nodes', () => {
    const nodes = Array.from({ length: 8 }, (_, i) => ({ id: `n${i}`, label: `N${i}` }))
    const edges = nodes.slice(1).map((n) => ({ from: 'n0', to: n.id }))
    const r = layoutRadial(nodes, edges, { rootId: 'n0', baseRadius: 150, centerX: 400, centerY: 400 })
    for (const n of r.nodes) {
      assert.ok(n.x >= r.viewBox.x - 1)
      assert.ok(n.y >= r.viewBox.y - 1)
    }
  })
})

// =============================================================================
// 3D — rig retarget
// =============================================================================

describe('Rig retarget — barre expert', () => {
  test('detectNamingConvention identifie Mixamo', () => {
    const r = detectNamingConvention(['mixamorig:Hips', 'mixamorig:Spine', 'mixamorig:Head'])
    assert.equal(r.convention, 'mixamo')
    assert.equal(r.mapping['mixamorig:Hips'], 'Hips')
  })

  test('detectNamingConvention identifie VRM', () => {
    const r = detectNamingConvention(['hips', 'leftUpperArm', 'rightUpperArm', 'head'])
    assert.equal(r.convention, 'vrm')
  })

  test('detectNamingConvention identifie Aurora natif', () => {
    const r = detectNamingConvention(['Hips', 'LeftArm', 'RightArm'])
    assert.equal(r.convention, 'aurora')
  })

  test('detectNamingConvention fallback unknown', () => {
    const r = detectNamingConvention(['Bone001', 'Bone002'])
    assert.equal(r.convention, 'unknown')
  })

  test('planRetarget Mixamo→Aurora : matched ≥ 18', () => {
    const sourceBones = Object.keys(MIXAMO_TO_AURORA)
    const rig = humanoidMixamoRig()
    const report = planRetarget(sourceBones, rig)
    assert.ok(report.matched.length >= 18, `matched ${report.matched.length}`)
    assert.equal(report.rootMapped, true)
  })

  test('planRetarget VRM→Aurora : matched ≥ 18', () => {
    const sourceBones = Object.keys(VRM_TO_AURORA)
    const rig = humanoidMixamoRig()
    const report = planRetarget(sourceBones, rig)
    assert.ok(report.matched.length >= 18, `matched ${report.matched.length}`)
  })

  test('planRetarget src inconnu → orphaned, target unanimated rempli', () => {
    const sourceBones = ['CustomBone1', 'CustomBone2']
    const rig = humanoidMixamoRig()
    const report = planRetarget(sourceBones, rig)
    assert.deepEqual(report.matched, [])
    assert.equal(report.orphaned.length, 2)
    assert.ok(report.unanimated.length > 0)
  })

  test('retargetAnimation preserve nombre de frames + durée', () => {
    const sourceBones = Object.keys(MIXAMO_TO_AURORA)
    const rig = humanoidMixamoRig()
    const anim = {
      name: 'walk',
      duration: 1,
      loop: true,
      frames: [
        { t: 0, rotations: { 'mixamorig:Hips': [0, 0, 0, 1] as [number, number, number, number] } },
        { t: 0.5, rotations: { 'mixamorig:Hips': [0, 0.3, 0, 0.95] as [number, number, number, number] } },
        { t: 1, rotations: { 'mixamorig:Hips': [0, 0, 0, 1] as [number, number, number, number] } },
      ],
    }
    const { animation: retargeted, report } = retargetAnimation(anim, sourceBones, rig)
    assert.equal(retargeted.frames.length, anim.frames.length)
    assert.equal(retargeted.duration, anim.duration)
    assert.ok(report.matched.length > 0)
    // Toutes les bones de la target doivent avoir une rotation (identité par défaut).
    for (const frame of retargeted.frames) {
      for (const bone of rig.bones) {
        assert.ok(frame.rotations[bone.id], `bone ${bone.id} sans rotation à t=${frame.t}`)
      }
    }
  })

  test('sampleAnimation interpole correctement entre frames', () => {
    const anim = {
      name: 'test', duration: 1, loop: false,
      frames: [
        { t: 0, rotations: { Hips: [0, 0, 0, 1] as [number, number, number, number] } },
        { t: 1, rotations: { Hips: [0, 1, 0, 0] as [number, number, number, number] } },
      ],
    }
    const q = sampleAnimation(anim, 'Hips', 0.5)
    // À mi-chemin : normalisé, y ≈ 0.707, w ≈ 0.707
    assert.ok(Math.abs(q[1] - 0.707) < 0.05, `y ${q[1]}`)
    assert.ok(Math.abs(q[3] - 0.707) < 0.05, `w ${q[3]}`)
  })

  test('sampleAnimation respect le loop', () => {
    const anim = {
      name: 'test', duration: 1, loop: true,
      frames: [
        { t: 0, rotations: { Hips: [0, 0, 0, 1] as [number, number, number, number] } },
        { t: 1, rotations: { Hips: [0, 1, 0, 0] as [number, number, number, number] } },
      ],
    }
    const q1 = sampleAnimation(anim, 'Hips', 0.5)
    const q2 = sampleAnimation(anim, 'Hips', 1.5) // 1.5 % 1 = 0.5
    assert.deepEqual(q1, q2)
  })

  test('rigBoneIds retourne les IDs du rig (lookup pratique)', () => {
    const rig = humanoidMixamoRig()
    const ids = rigBoneIds(rig)
    assert.equal(ids.length, rig.bones.length)
    assert.ok(ids.includes('Hips'))
  })

  test('static rig accepte retarget sans crasher (skip)', () => {
    const rig = defaultRigForCategory('object')
    const report = planRetarget(['mixamorig:Hips'], rig)
    assert.equal(report.matched.length, 0)
    // rootMapped passe en true sur un rig static car aucun mapping requis.
    assert.equal(report.rootMapped, true)
  })
})
