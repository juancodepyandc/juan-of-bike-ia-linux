/**
 * Tests pour services/threeDLodAndRig — LOD specs + rigging + export plan.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  lodPlanForCategory,
  humanoidMixamoRig,
  staticRig,
  defaultRigForCategory,
  defaultExportPlan,
  validateMesh,
  type Category,
  type MeshValidationInput,
} from '../services/threeDLodAndRig.ts'

describe('lodPlanForCategory', () => {
  test('object → 4 LOD avec budget descendant', () => {
    const plan = lodPlanForCategory('object')
    assert.equal(plan.length, 4)
    assert.equal(plan[0].id, 'lod0')
    assert.equal(plan[3].id, 'lod3')
    for (let i = 1; i < plan.length; i++) {
      assert.ok(plan[i].faceBudget < plan[i - 1].faceBudget)
    }
  })

  test('character > object budget', () => {
    const obj = lodPlanForCategory('object')
    const char = lodPlanForCategory('character')
    assert.ok(char[0].faceBudget > obj[0].faceBudget)
  })

  test('mech a le plus gros budget hors environment', () => {
    const mech = lodPlanForCategory('mech')[0].faceBudget
    const veh = lodPlanForCategory('vehicle')[0].faceBudget
    const char = lodPlanForCategory('character')[0].faceBudget
    assert.ok(mech > veh)
    assert.ok(mech > char)
  })

  test('triggerDistance strictement croissante', () => {
    const plan = lodPlanForCategory('character')
    for (let i = 1; i < plan.length; i++) {
      assert.ok(plan[i].triggerDistance > plan[i - 1].triggerDistance)
    }
  })

  test('ratioVsLod0 décroissant vers 1.0 → 0.12', () => {
    const plan = lodPlanForCategory('character')
    assert.equal(plan[0].ratioVsLod0, 1.0)
    assert.ok(plan[plan.length - 1].ratioVsLod0 < 0.2)
  })

  test('environment a le plus gros budget', () => {
    const env = lodPlanForCategory('environment')[0].faceBudget
    for (const c of ['object', 'character', 'vehicle', 'mech', 'creature'] as Category[]) {
      assert.ok(env >= lodPlanForCategory(c)[0].faceBudget)
    }
  })
})

describe('humanoidMixamoRig', () => {
  test('squelette ≥ 20 bones', () => {
    const rig = humanoidMixamoRig()
    assert.ok(rig.bones.length >= 20)
  })

  test('kind = humanoid-mixamo', () => {
    assert.equal(humanoidMixamoRig().kind, 'humanoid-mixamo')
  })

  test('Hips est root', () => {
    const rig = humanoidMixamoRig()
    const hips = rig.bones.find((b) => b.id === 'Hips')
    assert.ok(hips)
    assert.equal(hips.parent, null)
    assert.equal(hips.tag, 'root')
  })

  test('Spine forme une chaîne Hips → Spine → Spine1 → Spine2 → Neck → Head', () => {
    const rig = humanoidMixamoRig()
    const head = rig.bones.find((b) => b.id === 'Head')
    assert.equal(head?.parent, 'Neck')
  })

  test('IK chains pour bras + jambes', () => {
    const rig = humanoidMixamoRig()
    const names = rig.ikChains.map((c) => c.name)
    assert.ok(names.includes('LeftArmIK'))
    assert.ok(names.includes('RightArmIK'))
    assert.ok(names.includes('LeftLegIK'))
    assert.ok(names.includes('RightLegIK'))
  })

  test('animationLibrary contient idle/walk/run', () => {
    const rig = humanoidMixamoRig()
    const names = rig.animationLibrary.map((a) => a.name)
    assert.ok(names.includes('idle'))
    assert.ok(names.includes('walk'))
    assert.ok(names.includes('run'))
  })

  test('idle/walk/run en loop', () => {
    const rig = humanoidMixamoRig()
    const idle = rig.animationLibrary.find((a) => a.name === 'idle')
    assert.equal(idle?.loops, true)
  })

  test('referenceHeight personnalisable', () => {
    const rig = humanoidMixamoRig(2.0)
    assert.equal(rig.referenceHeight, 2.0)
  })

  test('parents existent dans la liste de bones', () => {
    const rig = humanoidMixamoRig()
    const ids = new Set(rig.bones.map((b) => b.id))
    for (const b of rig.bones) {
      if (b.parent !== null) {
        assert.ok(ids.has(b.parent), `parent ${b.parent} introuvable pour ${b.id}`)
      }
    }
  })
})

describe('staticRig', () => {
  test('aucun bone, aucun IK, aucune anim', () => {
    const r = staticRig()
    assert.equal(r.bones.length, 0)
    assert.equal(r.ikChains.length, 0)
    assert.equal(r.animationLibrary.length, 0)
    assert.equal(r.kind, 'static')
  })
})

describe('defaultRigForCategory', () => {
  test('character → humanoid', () => {
    assert.equal(defaultRigForCategory('character').kind, 'humanoid-mixamo')
  })

  test('creature → humanoid', () => {
    assert.equal(defaultRigForCategory('creature').kind, 'humanoid-mixamo')
  })

  test('mech → mech-articulated', () => {
    assert.equal(defaultRigForCategory('mech').kind, 'mech-articulated')
  })

  test('vehicle → mech-articulated', () => {
    assert.equal(defaultRigForCategory('vehicle').kind, 'mech-articulated')
  })

  test('object → static', () => {
    assert.equal(defaultRigForCategory('object').kind, 'static')
  })

  test('environment → static', () => {
    assert.equal(defaultRigForCategory('environment').kind, 'static')
  })
})

describe('defaultExportPlan', () => {
  test('renvoie au moins 5 formats', () => {
    const plan = defaultExportPlan('character')
    assert.ok(plan.length >= 5)
  })

  test('character → includeAnimations true partout sauf obj', () => {
    const plan = defaultExportPlan('character')
    const obj = plan.find((c) => c.format === 'obj')
    assert.equal(obj?.includeAnimations, false)
    for (const c of plan) {
      if (c.format !== 'obj') assert.equal(c.includeAnimations, true)
    }
  })

  test('object → includeAnimations false partout', () => {
    const plan = defaultExportPlan('object')
    for (const c of plan) assert.equal(c.includeAnimations, false)
  })

  test('GLB avec meshopt et draco présent', () => {
    const plan = defaultExportPlan('object')
    const meshopt = plan.find((c) => c.format === 'glb' && c.compression === 'meshopt')
    const draco = plan.find((c) => c.format === 'glb' && c.compression === 'draco')
    assert.ok(meshopt)
    assert.ok(draco)
  })

  test('chaque export a un suffix unique', () => {
    const plan = defaultExportPlan('character')
    const suffixes = plan.map((c) => c.suffix)
    assert.equal(new Set(suffixes).size, suffixes.length)
  })
})

describe('validateMesh', () => {
  function clean(faceBudget = 100_000): MeshValidationInput {
    return {
      faceCount: 50_000,
      vertexCount: 25_000,
      nonManifoldEdgeCount: 0,
      selfIntersectionCount: 0,
      duplicateVertexCount: 0,
      invertedNormalCount: 0,
      openHoleCount: 0,
      overlappingUvCount: 0,
      hasUvs: true,
      volume: 1.5,
      surfaceArea: 12,
      faceBudgetLod0: faceBudget,
      useCase: 'preview',
    }
  }

  test('mesh propre → manifold, watertight, 0 issues', () => {
    const r = validateMesh(clean())
    assert.equal(r.manifold, true)
    assert.equal(r.watertight, true)
    assert.equal(r.issues.length, 0)
    assert.equal(r.blockingForExport, false)
  })

  test('non-manifold edges → manifold=false', () => {
    const r = validateMesh({ ...clean(), nonManifoldEdgeCount: 5 })
    assert.equal(r.manifold, false)
    assert.ok(r.issues.includes('non-manifold-edges'))
  })

  test('open holes → watertight=false même si manifold', () => {
    const r = validateMesh({ ...clean(), openHoleCount: 3 })
    assert.equal(r.manifold, true)
    assert.equal(r.watertight, false)
  })

  test('print useCase → bloquant si pas watertight', () => {
    const r = validateMesh({ ...clean(), openHoleCount: 1, useCase: 'print' })
    assert.equal(r.blockingForExport, true)
  })

  test('vr useCase → bloquant si face budget dépassé', () => {
    const r = validateMesh({ ...clean(50_000), faceCount: 200_000, useCase: 'vr' })
    assert.equal(r.blockingForExport, true)
  })

  test('missing UV reporté', () => {
    const r = validateMesh({ ...clean(), hasUvs: false })
    assert.ok(r.issues.includes('missing-uv'))
  })

  test('budget dépassé (>5%) → issue', () => {
    const r = validateMesh({ ...clean(100_000), faceCount: 110_000 })
    assert.ok(r.issues.includes('face-budget-exceeded'))
  })

  test('budget juste sous 5% over → pas d issue', () => {
    const r = validateMesh({ ...clean(100_000), faceCount: 104_000 })
    assert.ok(!r.issues.includes('face-budget-exceeded'))
  })

  test('inverted-normals reporté', () => {
    const r = validateMesh({ ...clean(), invertedNormalCount: 100 })
    assert.ok(r.issues.includes('inverted-normals'))
  })

  test('duplicate-vertices threshold (>50)', () => {
    const a = validateMesh({ ...clean(), duplicateVertexCount: 30 })
    const b = validateMesh({ ...clean(), duplicateVertexCount: 100 })
    assert.ok(!a.issues.includes('duplicate-vertices'))
    assert.ok(b.issues.includes('duplicate-vertices'))
  })

  test('preview useCase tolérant', () => {
    const r = validateMesh({ ...clean(), openHoleCount: 1, useCase: 'preview' })
    assert.equal(r.blockingForExport, false)
  })
})
