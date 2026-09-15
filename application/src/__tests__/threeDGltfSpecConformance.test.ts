/**
 * Validateur glTF 2.0 — conformité à la spécification.
 *
 * POURQUOI CE FICHIER EXISTE. Le validateur garde l'entrée de la bibliothèque
 * 3D : ce qu'il déclare conforme est accepté. Mesure sur 18 violations
 * caractérisées de la spécification, 7 passaient sans un mot — dont trois
 * maillons de la chaîne de données (accessor → bufferView → buffer) et, le
 * plus grave, le CYCLE dans la hiérarchie de nœuds.
 *
 * Un cycle n'abîme pas le rendu : il FIGE le programme qui lit le fichier,
 * puisque tout parcours récursif — matrices monde, export, arborescence — y
 * tourne indéfiniment. C'est le pire mode de défaillance, et il entrait
 * librement.
 *
 * MÉTHODE. Chaque cas part d'un asset minimal réellement valide et casse UNE
 * chose, avec le renvoi à la clause de la spécification concernée. Un
 * validateur se juge aussi sur ce qu'il accepte : la seconde moitié du
 * fichier vérifie qu'aucun asset conforme n'est refusé.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/threeDGltfSpecConformance.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { validateGltfJson, readGltfHeader } from '../services/threeDGltfValidator.ts'

/** Asset minimal COMPLET : toute la chaîne de données est déclarée. */
function assetValide(): Record<string, unknown> {
  return {
    asset: { version: '2.0', generator: 'Aurora' },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0 }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 }, indices: 1, material: 0 }] }],
    materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, 1, 1, 1], metallicFactor: 0, roughnessFactor: 0.5 } }],
    accessors: [
      { bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' },
      { bufferView: 1, componentType: 5123, count: 3, type: 'SCALAR' },
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: 36 },
      { buffer: 0, byteOffset: 36, byteLength: 6 },
    ],
    buffers: [{ byteLength: 42 }],
  }
}

type Violation = { nom: string; casse: (g: any) => void; clause: string }

const VIOLATIONS: Violation[] = [
  { nom: 'asset absent', casse: (g) => { delete g.asset }, clause: '3.2 — asset est requis' },
  { nom: 'asset.version absente', casse: (g) => { delete g.asset.version }, clause: '3.2 — version est requise' },
  { nom: 'version 1.0', casse: (g) => { g.asset.version = '1.0' }, clause: 'seul glTF 2.x est lisible' },
  { nom: 'mesh sans POSITION', casse: (g) => { g.meshes[0].primitives[0].attributes = { NORMAL: 0 } }, clause: '3.7.2.1 — POSITION est requis' },
  { nom: 'mesh sans primitives', casse: (g) => { delete g.meshes[0].primitives }, clause: '3.7.2 — primitives est requis' },
  { nom: 'node → mesh inexistant', casse: (g) => { g.nodes[0].mesh = 99 }, clause: 'référence non résolue' },
  { nom: 'primitive → material inexistant', casse: (g) => { g.meshes[0].primitives[0].material = 99 }, clause: 'référence non résolue' },
  { nom: 'attribut → accessor inexistant', casse: (g) => { g.meshes[0].primitives[0].attributes.POSITION = 99 }, clause: '3.7.2.1 — index d’accessor' },
  { nom: 'indices → accessor inexistant', casse: (g) => { g.meshes[0].primitives[0].indices = 99 }, clause: '3.7.2.1 — index d’accessor' },
  { nom: 'accessor → bufferView inexistant', casse: (g) => { g.accessors[0].bufferView = 99 }, clause: '3.6.2 — index de bufferView' },
  { nom: 'bufferView → buffer inexistant', casse: (g) => { g.bufferViews[0].buffer = 99 }, clause: '3.4.2 — index de buffer' },
  { nom: 'bufferView déborde son buffer', casse: (g) => { g.bufferViews[0].byteLength = 99999 }, clause: '3.4.3 — lecture hors limites' },
  { nom: 'scene inexistante', casse: (g) => { g.scene = 99 }, clause: '3.3 — index de scene' },
  { nom: 'scene → node inexistant', casse: (g) => { g.scenes[0].nodes = [99] }, clause: '3.5 — index de node' },
  { nom: 'node → enfant inexistant', casse: (g) => { g.nodes = [{ children: [99] }] }, clause: '3.5 — index de node' },
  { nom: 'CYCLE dans la hiérarchie', casse: (g) => { g.nodes = [{ children: [1] }, { children: [0] }] }, clause: '3.5.2 — la hiérarchie est un arbre' },
  { nom: 'cycle indirect sur trois nœuds', casse: (g) => { g.nodes = [{ children: [1] }, { children: [2] }, { children: [0] }] }, clause: '3.5.2 — la hiérarchie est un arbre' },
  { nom: 'nœud son propre enfant', casse: (g) => { g.nodes = [{ children: [0] }] }, clause: '3.5.2 — la hiérarchie est un arbre' },
  { nom: 'animation → node inexistant', casse: (g) => { g.animations = [{ channels: [{ sampler: 0, target: { node: 99, path: 'rotation' } }], samplers: [{ input: 0, output: 1 }] }] }, clause: '3.6 — cible non résolue' },
  { nom: 'chemin d’animation hors liste', casse: (g) => { g.animations = [{ channels: [{ sampler: 0, target: { node: 0, path: 'couleur' } }], samplers: [{ input: 0, output: 1 }] }] }, clause: '3.6.2.1 — translation/rotation/scale/weights' },
  { nom: 'sampler → accessor inexistant', casse: (g) => { g.animations = [{ channels: [{ sampler: 0, target: { node: 0, path: 'rotation' } }], samplers: [{ input: 99, output: 1 }] }] }, clause: '3.6.2 — index d’accessor' },
  { nom: 'skin → joint inexistant', casse: (g) => { g.skins = [{ joints: [99] }] }, clause: '3.9 — index de node' },
  { nom: 'texture → image inexistante', casse: (g) => { g.textures = [{ source: 99 }] }, clause: '3.8 — index d’image' },
  { nom: 'extension requise non déclarée', casse: (g) => { g.extensionsRequired = ['KHR_materials_unlit'] }, clause: '3.12 — doit figurer dans extensionsUsed' },
]

describe('glTF 2.0 — chaque violation de la spécification est refusée', () => {
  for (const { nom, casse, clause } of VIOLATIONS) {
    test(`${nom}  (${clause})`, () => {
      const g = assetValide()
      casse(g)
      const r = validateGltfJson(g)
      const refusé = r.hasBlocker || r.issues.some((i) => i.severity === 'error' || i.severity === 'block')
      assert.ok(
        refusé,
        `asset accepté alors qu’il viole « ${clause} ». `
        + `valid=${r.valid} hasBlocker=${r.hasBlocker} problèmes=${JSON.stringify(r.issues)}`,
      )
      assert.equal(r.valid, false, 'un asset non conforme ne peut pas être « valid »')
    })
  }

  test('le cycle est nommé dans le message, pas seulement signalé', () => {
    const g = assetValide()
    g.nodes = [{ children: [1] }, { children: [0] }]
    const r = validateGltfJson(g)
    const cycle = r.issues.find((i) => /cycle/i.test(i.message))
    assert.ok(cycle, `aucun problème ne mentionne le cycle : ${JSON.stringify(r.issues)}`)
    assert.match(cycle!.message, /->/, 'le message doit donner le chemin du cycle')
  })

  test('la détection de cycle ne déborde pas la pile sur une hiérarchie profonde', () => {
    // 10 000 nœuds en chaîne : une détection récursive exploserait ici.
    const g = assetValide()
    g.nodes = Array.from({ length: 10_000 }, (_, i) => (i < 9_999 ? { children: [i + 1] } : {}))
    g.scenes = [{ nodes: [0] }]
    assert.doesNotThrow(() => validateGltfJson(g))
    const r = validateGltfJson(g)
    assert.ok(!r.issues.some((i) => /cycle/i.test(i.message)), 'une chaîne n’est pas un cycle')
  })
})

describe('glTF 2.0 — aucun asset conforme n’est refusé', () => {
  test('l’asset minimal complet passe', () => {
    const r = validateGltfJson(assetValide())
    assert.equal(r.valid, true, `refusé à tort : ${JSON.stringify(r.issues)}`)
    assert.equal(r.hasBlocker, false)
  })

  test('un asset réduit à « asset » est légal', () => {
    const r = validateGltfJson({ asset: { version: '2.0' } })
    assert.equal(r.valid, true)
  })

  test('un arbre partagé (deux parents pointant le même enfant) n’est pas un cycle', () => {
    // Un DAG sans cycle : la spécification interdit le cycle, pas le partage.
    const g = assetValide()
    g.nodes = [{ children: [2] }, { children: [2] }, {}]
    g.scenes = [{ nodes: [0, 1] }]
    const r = validateGltfJson(g)
    assert.ok(!r.issues.some((i) => /cycle/i.test(i.message)), JSON.stringify(r.issues))
  })

  test('les quatre chemins d’animation de la spécification sont acceptés', () => {
    for (const path of ['translation', 'rotation', 'scale', 'weights']) {
      const g = assetValide()
      g.animations = [{ channels: [{ sampler: 0, target: { node: 0, path } }], samplers: [{ input: 0, output: 1 }] }]
      const r = validateGltfJson(g)
      assert.ok(!r.issues.some((i) => /chemin/i.test(i.message)), `« ${path} » refusé à tort`)
    }
  })

  test('un bufferView qui remplit exactement son buffer passe', () => {
    const g = assetValide()
    g.bufferViews = [{ buffer: 0, byteOffset: 0, byteLength: 42 }]
    g.accessors = [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' }]
    g.meshes = [{ primitives: [{ attributes: { POSITION: 0 } }] }]
    const r = validateGltfJson(g)
    assert.ok(!r.issues.some((i) => /deborde/i.test(i.message)), JSON.stringify(r.issues))
  })

  test('les statistiques comptent ce qui est réellement déclaré', () => {
    const r = validateGltfJson(assetValide())
    assert.deepEqual(r.stats, {
      meshes: 1, primitives: 1, materials: 1, animations: 0,
      textures: 0, skins: 0, nodes: 1,
    })
  })
})

describe('glTF 2.0 — entrées dégénérées', () => {
  for (const [nom, valeur] of [['null', null], ['chaîne', 'abc'], ['tableau', []], ['objet vide', {}], ['nombre', 42], ['undefined', undefined]] as Array<[string, unknown]>) {
    test(`${nom} : refusé sans lever d’exception`, () => {
      assert.doesNotThrow(() => validateGltfJson(valeur))
      const r = validateGltfJson(valeur)
      assert.equal(r.valid, false)
      assert.equal(r.hasBlocker, true)
    })
  }

  test('readGltfHeader lit ou rend null, sans jamais lever', () => {
    assert.deepEqual(readGltfHeader(assetValide()), { version: '2.0', generator: 'Aurora' })
    assert.equal(readGltfHeader(null), null)
    assert.equal(readGltfHeader({}), null)
    assert.equal(readGltfHeader('x'), null)
  })
})
