/**
 * Tests pour services/threeDGltfValidator — validation glTF 2.0 JSON.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  validateGltfJson,
  readGltfHeader,
} from '../services/threeDGltfValidator.ts'

const MIN_VALID = {
  asset: { version: '2.0' },
  scene: 0,
  scenes: [{ nodes: [0] }],
  nodes: [{ mesh: 0 }],
  meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }],
}

describe('validateGltfJson — input non-objet', () => {
  test('null → block', () => {
    const r = validateGltfJson(null)
    assert.equal(r.valid, false)
    assert.equal(r.hasBlocker, true)
  })

  test('undefined → block', () => {
    const r = validateGltfJson(undefined)
    assert.equal(r.valid, false)
    assert.equal(r.hasBlocker, true)
  })

  test('string → block', () => {
    const r = validateGltfJson('hi')
    assert.equal(r.hasBlocker, true)
  })

  test('number → block', () => {
    const r = validateGltfJson(42)
    assert.equal(r.hasBlocker, true)
  })
})

describe('validateGltfJson — asset block', () => {
  test('asset manquant → block', () => {
    const r = validateGltfJson({ scenes: [{ nodes: [] }] })
    assert.ok(r.issues.some((i) => i.severity === 'block' && i.message.includes('asset')))
  })

  test('asset sans version → block', () => {
    const r = validateGltfJson({ asset: {} })
    assert.ok(r.issues.some((i) => i.message.includes('version')))
  })

  test('version "1.0" → error', () => {
    const r = validateGltfJson({ asset: { version: '1.0' } })
    assert.ok(r.issues.some((i) => i.severity === 'error' && i.message.includes('non supportée')))
  })

  test('version "2.0" → ok', () => {
    const r = validateGltfJson(MIN_VALID)
    assert.equal(r.valid, true)
  })
})

describe('validateGltfJson — mesh validation', () => {
  test('mesh sans POSITION → error', () => {
    const broken = {
      ...MIN_VALID,
      meshes: [{ primitives: [{ attributes: { NORMAL: 0 } }] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('POSITION')))
  })

  test('mesh avec POSITION=0 (falsy mais valide) → ok', () => {
    // POSITION=0 est un accessor index valide; le code doit utiliser == null pas !truthy
    const r = validateGltfJson(MIN_VALID)
    assert.ok(!r.issues.some((i) => i.message.includes('POSITION')))
  })

  test('mesh sans primitives → error', () => {
    const broken = {
      ...MIN_VALID,
      meshes: [{ primitives: [] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('primitives')))
  })

  test('material ref invalide → error', () => {
    const broken = {
      ...MIN_VALID,
      meshes: [{ primitives: [{ attributes: { POSITION: 0 }, material: 99 }] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('material 99')))
  })
})

describe('validateGltfJson — cross-references', () => {
  test('node ref mesh inexistant → error', () => {
    const broken = {
      ...MIN_VALID,
      nodes: [{ mesh: 99 }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('mesh 99')))
  })

  test('node ref child hors range → error', () => {
    const broken = {
      ...MIN_VALID,
      nodes: [{ children: [42] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('child 42')))
  })

  test('scene index hors range → error', () => {
    const broken = {
      asset: { version: '2.0' },
      scene: 5,
      scenes: [{ nodes: [] }],
      nodes: [],
      meshes: [],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('scene index 5')))
  })

  test('aucune scene → warn', () => {
    const broken = {
      asset: { version: '2.0' },
      nodes: [],
      meshes: [],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.severity === 'warn' && i.message.toLowerCase().includes('scene')))
  })
})

describe('validateGltfJson — material', () => {
  test('material sans baseColor → warn', () => {
    const root = {
      ...MIN_VALID,
      materials: [{ name: 'm0' }],
    }
    const r = validateGltfJson(root)
    assert.ok(r.issues.some((i) => i.severity === 'warn' && i.message.includes('baseColor')))
  })

  test('material avec baseColorFactor → ok', () => {
    const root = {
      ...MIN_VALID,
      materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, 0, 0, 1] } }],
    }
    const r = validateGltfJson(root)
    assert.equal(r.valid, true)
  })
})

describe('validateGltfJson — textures', () => {
  test('texture ref image inexistante → error', () => {
    const broken = {
      ...MIN_VALID,
      textures: [{ source: 99 }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('image 99')))
  })
})

describe('validateGltfJson — animations', () => {
  test('animation vide → warn', () => {
    const root = {
      ...MIN_VALID,
      animations: [{ channels: [], samplers: [] }],
    }
    const r = validateGltfJson(root)
    assert.ok(r.issues.some((i) => i.severity === 'warn' && i.message.includes('Animation')))
  })

  test('channel sampler hors range → error', () => {
    const broken = {
      ...MIN_VALID,
      animations: [{
        channels: [{ sampler: 99, target: { node: 0, path: 'translation' } }],
        samplers: [{ input: 0, output: 1 }],
      }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('sampler 99')))
  })

  test('animation target node hors range → error', () => {
    const broken = {
      ...MIN_VALID,
      animations: [{
        channels: [{ sampler: 0, target: { node: 99, path: 'translation' } }],
        samplers: [{ input: 0, output: 1 }],
      }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('target node 99')))
  })
})

describe('validateGltfJson — skins', () => {
  test('skin sans joints → error', () => {
    const broken = {
      ...MIN_VALID,
      skins: [{ joints: [] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('Skin') && i.message.includes('joints')))
  })

  test('skin joint hors range → error', () => {
    const broken = {
      ...MIN_VALID,
      skins: [{ joints: [99] }],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('joint 99')))
  })
})

describe('validateGltfJson — extensions', () => {
  test('extension required absente de used → error', () => {
    const broken = {
      ...MIN_VALID,
      extensionsRequired: ['KHR_draco'],
      extensionsUsed: [],
    }
    const r = validateGltfJson(broken)
    assert.ok(r.issues.some((i) => i.message.includes('KHR_draco')))
  })

  test('extension required dans used → ok', () => {
    const root = {
      ...MIN_VALID,
      extensionsRequired: ['KHR_draco'],
      extensionsUsed: ['KHR_draco'],
    }
    const r = validateGltfJson(root)
    assert.equal(r.valid, true)
  })
})

describe('validateGltfJson — stats', () => {
  test('comptage correct mesh/primitive/animations', () => {
    const root = {
      asset: { version: '2.0' },
      scenes: [{ nodes: [0] }],
      nodes: [{ mesh: 0 }, { mesh: 1 }],
      meshes: [
        { primitives: [{ attributes: { POSITION: 0 } }] },
        { primitives: [{ attributes: { POSITION: 0 } }, { attributes: { POSITION: 1 } }] },
      ],
      animations: [{ channels: [{ sampler: 0, target: { node: 0, path: 't' } }], samplers: [{ input: 0, output: 1 }] }],
    }
    const r = validateGltfJson(root)
    assert.equal(r.stats.meshes, 2)
    assert.equal(r.stats.primitives, 3)
    assert.equal(r.stats.animations, 1)
    assert.equal(r.stats.nodes, 2)
  })
})

describe('readGltfHeader', () => {
  test('renvoie version + generator', () => {
    const h = readGltfHeader({ asset: { version: '2.0', generator: 'Blender 4.0' } })
    assert.equal(h?.version, '2.0')
    assert.equal(h?.generator, 'Blender 4.0')
  })

  test('sans generator → null', () => {
    const h = readGltfHeader({ asset: { version: '2.0' } })
    assert.equal(h?.generator, null)
  })

  test('input invalide → null', () => {
    assert.equal(readGltfHeader(null), null)
    assert.equal(readGltfHeader({}), null)
    assert.equal(readGltfHeader('hi'), null)
  })
})
