#!/usr/bin/env node
// Visite à pied d'une scène générée : le marcheur bute sur les murs et glisse le long, monte une marche
// mais pas un meuble, tombe sous la gravité, traverse l'eau, ouvre les portes en approchant.
// Scène synthétique en three.js (vraies sources de src/services/sceneWalk.ts), aucun navigateur.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { BoxGeometry, Group, Mesh, MeshStandardMaterial, Object3D } from 'three'
import { Marcheur, MARCHE, lireDepart } from '../src/services/sceneWalk.ts'

function bloc(sx, sy, sz, x, y, z, nom = 'solide') {
  const m = new Mesh(new BoxGeometry(sx, sy, sz), new MeshStandardMaterial({ name: nom }))
  m.position.set(x, y + sy / 2, z)
  return m
}

function scene() {
  const racine = new Group()
  racine.add(bloc(30, 0.1, 30, 0, -0.1, 0, 'parquet_chene'))       // sol, dessus à y = 0
  racine.add(bloc(30, 2.5, 0.2, 0, 0, -3, 'platre_peint'))           // mur, face avant à z = -2.9
  racine.add(bloc(2, 0.3, 2, 6, 0, 0, 'pierre'))                      // marche de 30 cm
  racine.add(bloc(2, 0.8, 2, -6, 0, 0, 'bois_chene'))                 // meuble de 80 cm
  racine.add(bloc(4, 0.05, 4, 0, 0, 8, 'eau'))                        // surface d'eau posée sur le sol
  const porte = new Object3D()
  porte.name = 'porte_salon_couloir'
  porte.userData = { pivot: 'charniere', angle_ouverture_rad: Math.PI / 2 }
  porte.position.set(10, 0, 3)
  porte.add(bloc(0.9, 2.0, 0.04, 0.45, 0, 0, 'bois_peint'))          // vantail qui part du gond
  racine.add(porte)
  racine.userData = { extras: { depart: { x: 0, z: 2, direction: [0, -1] } } }
  racine.updateMatrixWorld(true)
  return racine
}

const RIEN = { avant: false, arriere: false, gauche: false, droite: false, courir: false, monter: false, descendre: false, sauter: false }

function marcher(m, commandes, secondes, dt = 1 / 60) {
  for (let t = 0; t < secondes; t += dt) m.pas(dt, { ...RIEN, ...commandes })
}

test('the start point is read from the scene extras, on the floor, facing the given direction', () => {
  const racine = scene()
  const depart = lireDepart(racine)
  assert.deepEqual(depart, { x: 0, z: 2, direction: [0, -1] })
  const m = new Marcheur(racine)
  m.placer(depart)
  assert.ok(Math.abs(m.pieds.y) < 1e-6, `pieds à ${m.pieds.y}`)
  assert.ok(Math.abs(m.lacet) < 1e-9)                                  // regarder vers -z
  assert.equal(m.nombrePortes, 1)
  assert.ok(Math.abs(m.oeil().y - MARCHE.yeux) < 1e-6)
})

test('walking into a wall stops at the body radius; walking at an angle slides along it', () => {
  const m = new Marcheur(scene())
  m.placer({ x: 0, z: 2, direction: [0, -1] })
  marcher(m, { avant: true }, 4)
  assert.ok(m.pieds.z > -2.9, `traversé le mur : z = ${m.pieds.z}`)
  assert.ok(m.pieds.z < -2.9 + MARCHE.rayon + 0.05, `arrêté trop tôt : z = ${m.pieds.z}`)
  const x0 = m.pieds.x
  m.lacet = Math.PI / 4                                                // de biais contre le mur
  marcher(m, { avant: true }, 2)
  assert.ok(m.pieds.z > -2.9, 'toujours devant le mur')
  assert.ok(Math.abs(m.pieds.x - x0) > 1.0, `pas de glissade le long du mur (x ${x0} → ${m.pieds.x})`)
})

test('a 30 cm step is climbed, an 80 cm piece of furniture blocks', () => {
  const m = new Marcheur(scene())
  m.placer({ x: 3, z: 0, direction: [1, 0] })
  marcher(m, { avant: true }, 2)                                       // 3 m : on s'arrête au milieu de la marche (x 5 → 7)
  assert.ok(m.pieds.x > 5.5 && m.pieds.x < 6.8, `x = ${m.pieds.x}`)
  assert.ok(Math.abs(m.pieds.y - 0.3) < 0.02, `pas monté sur la marche : y = ${m.pieds.y}`)
  marcher(m, { avant: true }, 1.5)
  assert.ok(m.pieds.x > 7.2 && Math.abs(m.pieds.y) < 0.02, `pas redescendu de l'autre côté : y = ${m.pieds.y}`)
  const b = new Marcheur(scene())
  b.placer({ x: -3, z: 0, direction: [-1, 0] })
  marcher(b, { avant: true }, 3)
  assert.ok(b.pieds.x > -5.0 + MARCHE.rayon - 0.05, `traversé le meuble : x = ${b.pieds.x}`)
  assert.ok(Math.abs(b.pieds.y) < 0.02, 'resté au sol devant le meuble')
})

test('gravity brings a walker down to the floor and a jump comes back down', () => {
  const m = new Marcheur(scene())
  m.placer({ x: 0, z: 2 })
  m.pieds.y = 4
  m.auSol = false
  marcher(m, {}, 2)
  assert.ok(Math.abs(m.pieds.y) < 1e-6 && m.auSol, `pas retombé : y = ${m.pieds.y}`)
  m.pas(1 / 60, { ...RIEN, sauter: true })
  marcher(m, {}, 0.2)
  assert.ok(m.pieds.y > 0.3, 'le saut monte')
  marcher(m, {}, 2)
  assert.ok(Math.abs(m.pieds.y) < 1e-6, 'et redescend')
})

test('water is walked through and a door opens on approach without blocking the way', () => {
  const m = new Marcheur(scene())
  m.placer({ x: 0, z: 5, direction: [0, 1] })
  marcher(m, { avant: true }, 3)
  assert.ok(m.pieds.z > 9.5, `bloqué par l'eau : z = ${m.pieds.z}`)
  const p = new Marcheur(scene())
  p.placer({ x: 10.4, z: 6, direction: [0, -1] })
  assert.ok(p.ouvertures()[0] < 0.01, 'porte fermée au départ')
  marcher(p, { avant: true }, 3)
  assert.ok(p.ouvertures()[0] > 0.5, `porte restée fermée : ${p.ouvertures()[0]}`)
  assert.ok(p.pieds.z < 2.0, `bloqué par le vantail : z = ${p.pieds.z}`)
  marcher(p, { avant: true }, 4)
  assert.ok(p.ouvertures()[0] < 0.2, 'la porte se referme quand on s’éloigne')
})

test('fly mode crosses walls and climbs freely', () => {
  const m = new Marcheur(scene())
  m.placer({ x: 0, z: 2, direction: [0, -1] })
  m.vol = true
  marcher(m, { avant: true, monter: true }, 1)
  assert.ok(m.pieds.z < -3.5, 'le vol traverse')
  assert.ok(m.pieds.y > 5, 'et monte')
})

// ── Une vraie maison générée par le moteur de scènes (fichier local, test sauté s'il manque) ─────────────
const MAISON = '/home/juan/AuroraIA/application/output/3d/essais/monde/integration/visite_maison/modele/scene_monde.glb'

/** Le même GLB sans ses textures : Node ne sait pas décoder d'images, la géométrie suffit pour marcher. */
function sansTextures(octets) {
  const vue = new DataView(octets.buffer, octets.byteOffset, octets.byteLength)
  const longueurJson = vue.getUint32(12, true)
  const json = JSON.parse(new TextDecoder().decode(octets.subarray(20, 20 + longueurJson)))
  delete json.images
  delete json.textures
  delete json.samplers
  for (const m of json.materials || []) {
    const pbr = m.pbrMetallicRoughness || {}
    delete pbr.baseColorTexture
    delete pbr.metallicRoughnessTexture
    delete m.normalTexture
    delete m.occlusionTexture
    delete m.emissiveTexture
  }
  const brut = new TextEncoder().encode(JSON.stringify(json))
  const texte = new Uint8Array(brut.length + ((4 - (brut.length % 4)) % 4)).fill(0x20)
  texte.set(brut)
  const binaire = octets.subarray(20 + longueurJson)
  const sortie = new Uint8Array(20 + texte.length + binaire.length)
  const dv = new DataView(sortie.buffer)
  dv.setUint32(0, 0x46546c67, true)
  dv.setUint32(4, 2, true)
  dv.setUint32(8, sortie.length, true)
  dv.setUint32(12, texte.length, true)
  dv.setUint32(16, 0x4e4f534a, true)
  sortie.set(texte, 20)
  sortie.set(binaire, 20 + texte.length)
  return sortie.buffer
}

test('a real generated house: start inside on the floor, walls hold on a long walk, doors open', async (t) => {
  const fs = await import('node:fs')
  if (!fs.existsSync(MAISON)) {
    t.skip('maison de démonstration absente (python -m monde.composer --sortie …/visite_maison)')
    return
  }
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
  const gltf = await new Promise((ok, ko) => new GLTFLoader().parse(sansTextures(fs.readFileSync(MAISON)), '', ok, ko))
  const racine = gltf.scene
  racine.updateMatrixWorld(true)
  const depart = lireDepart(racine)
  assert.ok(depart, 'le départ est écrit dans les extras de la scène')
  const m = new Marcheur(racine)
  assert.ok(m.nombrePortes >= 3, `${m.nombrePortes} portes`)
  m.placer(depart)
  assert.ok(m.auSol && Math.abs(m.pieds.y) < 0.05, `départ sur le plancher : y = ${m.pieds.y}`)
  const { boite } = m
  let ouverture = 0
  // longue marche en lacets : les murs et façades doivent tenir, on ne sort jamais de la maison
  for (let s = 0; s < 90; s += 1) {
    m.lacet += (s % 7 === 0 ? 1.9 : 0.35)
    marcher(m, { avant: true, courir: s % 3 === 0 }, 1)
    ouverture = Math.max(ouverture, ...m.ouvertures())
    assert.ok(m.pieds.x > boite.min.x + 0.1 && m.pieds.x < boite.max.x - 0.1 &&
              m.pieds.z > boite.min.z + 0.1 && m.pieds.z < boite.max.z - 0.1, `sorti de la maison à la seconde ${s}`)
    assert.ok(m.pieds.y > -0.05 && m.pieds.y < 0.8, `hauteur anormale ${m.pieds.y} à la seconde ${s}`)
  }
  assert.ok(ouverture > 0.5, 'au moins une porte s’est ouverte pendant la visite')
})
