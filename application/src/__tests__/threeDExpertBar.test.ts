/**
 * Tests barre expert pour le module 3D.
 *
 * Scénarios concrets (pas des inputs construits pour faire passer le test).
 * Le validator doit savoir différencier "preview-OK / VR-OK / print-blocking"
 * comme un pipeline Blender pro le ferait.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  defaultExportPlan,
  defaultRigForCategory,
  humanoidMixamoRig,
  lodPlanForCategory,
  validateMesh,
} from '../services/threeDLodAndRig.ts'

// --- Scénarios mesh réalistes ----------------------------------------------

/** Output Hunyuan3D typique (character) : 180k faces, UVs, watertight. */
const HUNYUAN_CHARACTER = {
  faceCount: 175_000, vertexCount: 95_000,
  nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 5,
  invertedNormalCount: 0, openHoleCount: 0, overlappingUvCount: 0,
  hasUvs: true, volume: 0.05, surfaceArea: 2.4, faceBudgetLod0: 180_000,
}

/** Output procédural simplifié (object cube) : 12 faces, watertight. */
const SIMPLE_CUBE = {
  faceCount: 12, vertexCount: 8,
  nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 0,
  invertedNormalCount: 0, openHoleCount: 0, overlappingUvCount: 0,
  hasUvs: true, volume: 0.001, surfaceArea: 0.06, faceBudgetLod0: 140_000,
}

/** Output dégradé : pas de UVs, normales inversées. */
const DEGRADED_MESH = {
  faceCount: 80_000, vertexCount: 40_000,
  nonManifoldEdgeCount: 12, selfIntersectionCount: 3, duplicateVertexCount: 200,
  invertedNormalCount: 50, openHoleCount: 8, overlappingUvCount: 0,
  hasUvs: false, volume: -0.01, surfaceArea: 1.2, faceBudgetLod0: 180_000,
}

/** Mesh "presque OK" mais open hole — bon pour preview, KO pour print 3D. */
const ALMOST_WATERTIGHT = {
  faceCount: 150_000, vertexCount: 78_000,
  nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 10,
  invertedNormalCount: 0, openHoleCount: 1, overlappingUvCount: 0,
  hasUvs: true, volume: 0.04, surfaceArea: 2.1, faceBudgetLod0: 180_000,
}

/** Budget dépassé de 30 %. */
const OVER_BUDGET = {
  faceCount: 300_000, vertexCount: 160_000,
  nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 0,
  invertedNormalCount: 0, openHoleCount: 0, overlappingUvCount: 0,
  hasUvs: true, volume: 0.05, surfaceArea: 2.5, faceBudgetLod0: 180_000,
}

describe('validateMesh — scénarios pipeline 3D', () => {
  test('Hunyuan character watertight ↦ valide pour VR et studio', () => {
    const vr = validateMesh({ ...HUNYUAN_CHARACTER, useCase: 'vr' })
    const studio = validateMesh({ ...HUNYUAN_CHARACTER, useCase: 'studio' })
    assert.equal(vr.manifold, true)
    assert.equal(vr.watertight, true)
    assert.equal(vr.blockingForExport, false)
    assert.equal(studio.blockingForExport, false)
  })

  test('Mesh dégradé ↦ bloquant pour TOUS les useCases (sauf preview qui tolère)', () => {
    for (const useCase of ['vr', 'print', 'studio'] as const) {
      const r = validateMesh({ ...DEGRADED_MESH, useCase })
      assert.equal(r.blockingForExport, true, `${useCase} laisse passer un mesh dégradé`)
    }
  })

  test('Mesh "presque watertight" : preview OK, print bloque', () => {
    const preview = validateMesh({ ...ALMOST_WATERTIGHT, useCase: 'preview' })
    const print = validateMesh({ ...ALMOST_WATERTIGHT, useCase: 'print' })
    assert.equal(preview.blockingForExport, false)
    assert.equal(print.blockingForExport, true)
    assert.ok(print.issues.includes('open-holes'))
  })

  test('Budget dépassé > 5 % ↦ flagué, bloque VR', () => {
    const vr = validateMesh({ ...OVER_BUDGET, useCase: 'vr' })
    assert.ok(vr.issues.includes('face-budget-exceeded'))
    assert.equal(vr.blockingForExport, true)
    const preview = validateMesh({ ...OVER_BUDGET, useCase: 'preview' })
    // Preview tolère le dépassement de budget tant que la topologie est OK.
    assert.equal(preview.blockingForExport, false)
  })

  test('Cube minimal valide partout', () => {
    for (const useCase of ['preview', 'vr', 'print', 'studio'] as const) {
      const r = validateMesh({ ...SIMPLE_CUBE, useCase })
      assert.equal(r.blockingForExport, false, `${useCase} bloque un cube clean`)
    }
  })

  test('Détection non-manifold isolée — assez sensible', () => {
    const r = validateMesh({
      ...HUNYUAN_CHARACTER, nonManifoldEdgeCount: 1, useCase: 'studio',
    })
    assert.equal(r.manifold, false)
    assert.equal(r.blockingForExport, true)
  })

  test('volume négatif (normales inversées globales) capturable', () => {
    const r = validateMesh({ ...DEGRADED_MESH, useCase: 'preview' })
    // L'info reste exposée même si preview ne bloque pas.
    assert.ok(r.volume < 0)
  })
})

describe('lodPlanForCategory — barre expert', () => {
  test('character génère 4 niveaux strictement décroissants', () => {
    const plan = lodPlanForCategory('character')
    assert.equal(plan.length, 4)
    for (let i = 1; i < plan.length; i += 1) {
      assert.ok(plan[i].faceBudget < plan[i - 1].faceBudget, `LOD${i} pas inférieur à LOD${i - 1}`)
      assert.ok(plan[i].triggerDistance > plan[i - 1].triggerDistance)
    }
  })

  test('LOD3 ≤ 15 % du LOD0 (utilisation web-friendly)', () => {
    const plan = lodPlanForCategory('character')
    assert.ok(plan[3].faceBudget / plan[0].faceBudget <= 0.15)
  })

  test('vehicle budget > character (handoff: 220k vs 180k)', () => {
    assert.ok(lodPlanForCategory('vehicle')[0].faceBudget > lodPlanForCategory('character')[0].faceBudget)
  })

  test('environment > vehicle', () => {
    assert.ok(lodPlanForCategory('environment')[0].faceBudget > lodPlanForCategory('vehicle')[0].faceBudget)
  })
})

describe('Rig descriptor — barre expert', () => {
  test('humanoid : 22 bones, racine Hips, parents valides', () => {
    const rig = humanoidMixamoRig()
    assert.equal(rig.bones.length, 22)
    const ids = new Set(rig.bones.map((b) => b.id))
    assert.ok(ids.has('Hips'))
    for (const bone of rig.bones) {
      if (bone.parent !== null) {
        assert.ok(ids.has(bone.parent), `parent ${bone.parent} de ${bone.id} introuvable`)
      }
    }
  })

  test('humanoid : DAG sans cycle', () => {
    const rig = humanoidMixamoRig()
    const parents = new Map(rig.bones.map((b) => [b.id, b.parent]))
    for (const id of parents.keys()) {
      let cur: string | null | undefined = parents.get(id)
      let depth = 0
      while (cur && depth < 32) {
        if (cur === id) throw new Error(`cycle détecté à ${id}`)
        cur = parents.get(cur)
        depth += 1
      }
      assert.ok(depth < 32, `chaîne trop profonde depuis ${id}`)
    }
  })

  test('humanoid : 4 IK chains avec root+effector valides', () => {
    const rig = humanoidMixamoRig()
    const ids = new Set(rig.bones.map((b) => b.id))
    assert.equal(rig.ikChains.length, 4)
    for (const chain of rig.ikChains) {
      assert.ok(ids.has(chain.root), `root ${chain.root} introuvable`)
      assert.ok(ids.has(chain.effector), `effector ${chain.effector} introuvable`)
    }
  })

  test('humanoid : effector toujours plus loin que root dans la chaîne', () => {
    const rig = humanoidMixamoRig()
    const parents = new Map(rig.bones.map((b) => [b.id, b.parent]))
    for (const chain of rig.ikChains) {
      // Remonter de effector vers root doit passer par le root.
      let cur: string | null | undefined = chain.effector
      let found = false
      for (let i = 0; i < 32; i += 1) {
        if (cur === chain.root) { found = true; break }
        if (!cur) break
        cur = parents.get(cur)
      }
      assert.ok(found, `effector ${chain.effector} ne descend pas de root ${chain.root}`)
    }
  })

  test('character category ↦ rig humanoid (pas static)', () => {
    assert.equal(defaultRigForCategory('character').kind, 'humanoid-mixamo')
  })

  test('object category ↦ static rig (pas de bones)', () => {
    assert.equal(defaultRigForCategory('object').kind, 'static')
    assert.equal(defaultRigForCategory('object').bones.length, 0)
  })
})

import { readGltfHeader, validateGltfJson } from '../services/threeDGltfValidator.ts'

describe('Validateur glTF JSON — barre expert', () => {
  const validMinimal = {
    asset: { version: '2.0', generator: 'Blender 4.0' },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    meshes: [{
      primitives: [{ attributes: { POSITION: 0 }, material: 0 }],
    }],
    materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, 1, 1, 1] } }],
    accessors: [{ componentType: 5126, count: 3, type: 'VEC3' }],
  }

  test('glTF minimal valide passe sans error/blocker', () => {
    const r = validateGltfJson(validMinimal)
    assert.equal(r.valid, true)
    assert.equal(r.hasBlocker, false)
    assert.equal(r.stats.meshes, 1)
    assert.equal(r.stats.materials, 1)
  })

  test('input non-objet → block', () => {
    const r = validateGltfJson('not json')
    assert.equal(r.hasBlocker, true)
  })

  test('asset.version manquant → block', () => {
    const r = validateGltfJson({ scenes: [] })
    assert.equal(r.hasBlocker, true)
  })

  test('version glTF 1.0 → error (non supportée)', () => {
    const r = validateGltfJson({ asset: { version: '1.0' } })
    assert.ok(r.issues.some((i) => /non support/i.test(i.message)))
  })

  test('mesh sans POSITION → error', () => {
    const r = validateGltfJson({
      ...validMinimal,
      meshes: [{ primitives: [{ attributes: { NORMAL: 0 } }] }],
    })
    assert.ok(r.issues.some((i) => /POSITION/i.test(i.message)))
  })

  test('node ref mesh inexistant → error', () => {
    const r = validateGltfJson({
      asset: { version: '2.0' },
      nodes: [{ mesh: 99 }],
      meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }],
    })
    assert.ok(r.issues.some((i) => /mesh 99 inexistant/i.test(i.message)))
  })

  test('material sans baseColor → warn', () => {
    const r = validateGltfJson({
      ...validMinimal,
      materials: [{ pbrMetallicRoughness: {} }],
    })
    assert.ok(r.issues.some((i) => /baseColor/i.test(i.message)))
  })

  test('skin avec joint hors range → error', () => {
    const r = validateGltfJson({
      ...validMinimal,
      skins: [{ joints: [42] }],
    })
    assert.ok(r.issues.some((i) => /joint/i.test(i.message)))
  })

  test('animation cohérente passe', () => {
    const r = validateGltfJson({
      asset: { version: '2.0' },
      scenes: [{ nodes: [0] }],
      nodes: [{ name: 'root' }],
      animations: [{
        channels: [{ sampler: 0, target: { node: 0, path: 'translation' } }],
        samplers: [{ input: 0, output: 1 }],
      }],
    })
    assert.equal(r.hasBlocker, false)
  })

  test('animation sampler invalide → error', () => {
    const r = validateGltfJson({
      asset: { version: '2.0' },
      nodes: [{}],
      animations: [{
        channels: [{ sampler: 99, target: { node: 0, path: 'translation' } }],
        samplers: [{ input: 0, output: 1 }],
      }],
    })
    assert.ok(r.issues.some((i) => /sampler/i.test(i.message)))
  })

  test('extensionsRequired absent de extensionsUsed → error', () => {
    const r = validateGltfJson({
      asset: { version: '2.0' },
      extensionsRequired: ['KHR_draco_mesh_compression'],
      extensionsUsed: [],
    })
    assert.ok(r.issues.some((i) => /required.*absent/i.test(i.message)))
  })

  test('stats correctement comptées sur asset complexe', () => {
    const r = validateGltfJson({
      asset: { version: '2.0' },
      scenes: [{ nodes: [0, 1] }],
      nodes: [{ mesh: 0 }, { mesh: 1 }, { mesh: 0 }],
      meshes: [
        { primitives: [{ attributes: { POSITION: 0 } }, { attributes: { POSITION: 1 } }] },
        { primitives: [{ attributes: { POSITION: 2 } }] },
      ],
      materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, 0, 0, 1] } }],
      textures: [{ source: 0 }],
      images: [{ uri: 'tex.png' }],
      animations: [{ channels: [{ sampler: 0, target: { node: 0, path: 'rotation' } }], samplers: [{ input: 0, output: 1 }] }],
    })
    assert.equal(r.stats.meshes, 2)
    assert.equal(r.stats.primitives, 3)
    assert.equal(r.stats.nodes, 3)
    assert.equal(r.stats.materials, 1)
    assert.equal(r.stats.textures, 1)
    assert.equal(r.stats.animations, 1)
  })

  test('readGltfHeader extrait version et generator', () => {
    const h = readGltfHeader({ asset: { version: '2.0', generator: 'Hunyuan3D-2' } })
    assert.equal(h?.version, '2.0')
    assert.equal(h?.generator, 'Hunyuan3D-2')
  })

  test('readGltfHeader retourne null sur input invalide', () => {
    assert.equal(readGltfHeader(null), null)
    assert.equal(readGltfHeader({ noAsset: true }), null)
  })
})

describe('Export plan — barre expert', () => {
  test('character : 5 formats au moins, animations dans GLB/FBX/USD', () => {
    const plan = defaultExportPlan('character')
    assert.ok(plan.length >= 5)
    const animated = plan.filter((p) => p.includeAnimations)
    assert.ok(animated.some((p) => p.format === 'glb'))
    assert.ok(animated.some((p) => p.format === 'fbx'))
  })

  test('object : OBJ présent (pas d\'animation)', () => {
    const plan = defaultExportPlan('object')
    const obj = plan.find((p) => p.format === 'obj')
    assert.ok(obj)
    assert.equal(obj.includeAnimations, false)
  })

  test('plans GLB ont compression définie', () => {
    const plan = defaultExportPlan('character')
    for (const preset of plan.filter((p) => p.format === 'glb')) {
      assert.notEqual(preset.compression, undefined)
    }
  })
})
