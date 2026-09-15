/**
 * Géométrie 3D — invariants durs.
 *
 * POURQUOI CE FICHIER EXISTE. Trois défauts vivaient sous les tests
 * existants, qui portaient sur des cas uniformes ou bien formés :
 *
 *   1. ATLAS DE TEXTURES. Le découpage des zones libres recevait l'empreinte
 *      NON TOURNÉE quand une texture était couchée à 90°. La surface prise
 *      restait marquée libre et une texture suivante s'y posait. Mesure :
 *      4 paires de cases se chevauchaient sur 12 textures de tailles variées,
 *      7 sur 20 tailles impaires. Deux textures partageant des pixels, c'est
 *      la mauvaise matière plaquée sur une partie du modèle. Les jeux de
 *      tuiles CARRÉES n'exhibaient rien — la rotation y est sans effet —
 *      d'où le silence des essais uniformes.
 *   2. FRUSTUM. L'extraction des plans est juste pour une matrice rangée en
 *      lignes et fausse pour une matrice rangée en colonnes — or c'est ce
 *      dernier rangement que rend `Matrix4.elements` de Three.js. L'erreur
 *      est indétectable : les deux sont des tableaux de 16 nombres valides.
 *   3. QUATERNIONS. `sampleAnimation` rendait [NaN, NaN, NaN, NaN] pour une
 *      durée nulle en boucle, un temps NaN ou infini. Un quaternion NaN posé
 *      sur un os fait DISPARAÎTRE le maillage qui en dépend.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/threeDGeometryInvariants.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  aabbFromPoints, aabbCenter, aabbVolume, aabbIntersect,
  sphereFromPoints, pointInFrustum, aabbInFrustum, rayAabbIntersect,
  frustumFromMatrix, type Vec3,
} from '../services/threeDBoundsAndCulling.ts'
import { packAtlas } from '../services/threeDTextureAtlas.ts'
import { sampleAnimation } from '../services/threeDRigRetarget.ts'

// --- générateur déterministe (pas de Math.random dans un test) -------------
function tirages(graine: number) {
  let g = graine
  return () => { g = (g * 1103515245 + 12345) & 0x7fffffff; return g / 0x7fffffff }
}

const distance = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])

// ===========================================================================
describe('atlas de textures — deux cases ne partagent jamais un pixel', () => {
  type Cas = { nom: string; textures: Array<{ id: string; width: number; height: number }>; opts?: Record<string, unknown> }

  const CAS: Cas[] = [
    {
      nom: '12 textures de tailles variées (rotation active)',
      textures: Array.from({ length: 12 }, (_, i) => ({ id: `t${i}`, width: 64 + (i % 4) * 64, height: 64 + (i % 3) * 64 })),
    },
    {
      nom: '20 tailles impaires',
      textures: Array.from({ length: 20 }, (_, i) => ({ id: `t${i}`, width: 37 + i * 13, height: 53 + i * 7 })),
    },
    {
      nom: '64 tuiles carrées',
      textures: Array.from({ length: 64 }, (_, i) => ({ id: `t${i}`, width: 128, height: 128 })),
    },
    {
      nom: 'rectangles très allongés (la rotation change tout)',
      textures: Array.from({ length: 14 }, (_, i) => ({ id: `t${i}`, width: 16 + i * 8, height: 512 - i * 16 })),
    },
    {
      nom: 'sans marge',
      textures: Array.from({ length: 16 }, (_, i) => ({ id: `t${i}`, width: 256, height: 256 })),
      opts: { padding: 0 },
    },
    {
      nom: 'rotation interdite',
      textures: Array.from({ length: 12 }, (_, i) => ({ id: `t${i}`, width: 64 + (i % 4) * 64, height: 64 + (i % 3) * 64 })),
      opts: { allowRotation: false },
    },
  ]

  for (const { nom, textures, opts } of CAS) {
    test(nom, () => {
      const r = packAtlas(textures, opts ?? {})

      const dehors = r.slots.filter((s) => s.x < 0 || s.y < 0
        || s.x + s.width > r.atlasWidth || s.y + s.height > r.atlasHeight)
      assert.deepEqual(dehors.map((s) => s.id), [], 'des cases sortent de l’atlas')

      const chevauchements: string[] = []
      for (let i = 0; i < r.slots.length; i += 1) {
        for (let j = i + 1; j < r.slots.length; j += 1) {
          const a = r.slots[i]
          const b = r.slots[j]
          if (a.x < b.x + b.width && b.x < a.x + a.width
            && a.y < b.y + b.height && b.y < a.y + a.height) {
            chevauchements.push(
              `${a.id}(${a.x},${a.y},${a.width}x${a.height}${a.rotated ? ',tournée' : ''}) `
              + `∩ ${b.id}(${b.x},${b.y},${b.width}x${b.height}${b.rotated ? ',tournée' : ''})`,
            )
          }
        }
      }
      assert.deepEqual(
        chevauchements, [],
        `${chevauchements.length} paire(s) de cases se chevauchent — deux textures `
        + 'partageraient des pixels, donc la mauvaise matière sur une partie du modèle.',
      )

      assert.deepEqual(r.unplaced, [], 'aucune texture ne devait être rejetée')
    })
  }

  test('propriété : 300 jeux tirés au sort, aucun chevauchement', () => {
    const rnd = tirages(20260824)
    let chevauchants = 0
    let exemple = ''
    for (let essai = 0; essai < 300; essai += 1) {
      const n = 2 + Math.floor(rnd() * 18)
      const textures = Array.from({ length: n }, (_, i) => ({
        id: `t${i}`,
        width: 8 + Math.floor(rnd() * 400),
        height: 8 + Math.floor(rnd() * 400),
      }))
      const r = packAtlas(textures)
      for (let i = 0; i < r.slots.length && !exemple; i += 1) {
        for (let j = i + 1; j < r.slots.length; j += 1) {
          const a = r.slots[i]
          const b = r.slots[j]
          if (a.x < b.x + b.width && b.x < a.x + a.width
            && a.y < b.y + b.height && b.y < a.y + a.height) {
            chevauchants += 1
            exemple = `essai ${essai} : ${a.id} ∩ ${b.id}`
            break
          }
        }
      }
    }
    assert.equal(chevauchants, 0, `${chevauchants} jeu(x) avec chevauchement. ${exemple}`)
  })

  test('les UV rendus désignent exactement la case', () => {
    const r = packAtlas(Array.from({ length: 20 }, (_, i) => ({ id: `t${i}`, width: 37 + i * 13, height: 53 + i * 7 })))
    for (const s of r.slots) {
      assert.ok(Math.abs(s.uvOffsetX * r.atlasWidth - s.x) < 0.5, `${s.id} : offset X`)
      assert.ok(Math.abs(s.uvOffsetY * r.atlasHeight - s.y) < 0.5, `${s.id} : offset Y`)
      assert.ok(Math.abs(s.uvScaleX * r.atlasWidth - s.width) < 0.5, `${s.id} : échelle X`)
      assert.ok(Math.abs(s.uvScaleY * r.atlasHeight - s.height) < 0.5, `${s.id} : échelle Y`)
    }
  })

  test('une texture plus grande que l’atlas est REJETÉE, pas tronquée en silence', () => {
    const r = packAtlas([{ id: 'geante', width: 8192, height: 8192 }])
    assert.deepEqual(r.unplaced, ['geante'])
    assert.deepEqual(r.slots, [])
  })

  test('liste vide : atlas dégénéré mais cohérent', () => {
    const r = packAtlas([])
    assert.deepEqual(r.slots, [])
    assert.deepEqual(r.unplaced, [])
    assert.equal(r.occupancyRatio, 0)
  })
})

// ===========================================================================
describe('sphère englobante — elle englobe, toujours', () => {
  const CANONIQUES: Array<[string, Vec3[], number]> = [
    ['cube unité', [[-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5]], Math.sqrt(3) / 2],
    ['segment de 4,9', Array.from({ length: 50 }, (_, i) => [i * 0.1, 0, 0] as Vec3), 2.45],
    ['disque plat de rayon 1', Array.from({ length: 64 }, (_, i) => [Math.cos(i / 64 * 2 * Math.PI), 0, Math.sin(i / 64 * 2 * Math.PI)] as Vec3), 1],
    ['deux amas opposés', [[-10, 0, 0], [-9.9, 0.1, 0], [10, 0, 0], [9.9, 0.1, 0]], 10],
  ]

  for (const [nom, points, minimal] of CANONIQUES) {
    test(`${nom} : rayon proche du minimum et aucun point dehors`, () => {
      const s = sphereFromPoints(points)
      const dehors = points.filter((p) => distance(p, s.center) > s.radius + 1e-9)
      assert.deepEqual(dehors, [], `${dehors.length} point(s) hors de la sphère englobante`)
      assert.ok(
        s.radius <= minimal * 1.06,
        `rayon ${s.radius.toFixed(4)} pour un minimum de ${minimal.toFixed(4)} `
        + `(${((s.radius / minimal - 1) * 100).toFixed(1)} % d’excédent, plafond annoncé 5 %)`,
      )
    })
  }

  test('propriété : 400 nuages tirés au sort, aucun point ne sort', () => {
    const rnd = tirages(4242)
    let manquants = 0
    let pire = 0
    for (let essai = 0; essai < 400; essai += 1) {
      const n = 3 + Math.floor(rnd() * 60)
      const points: Vec3[] = Array.from({ length: n }, () => [rnd() * 40 - 20, rnd() * 40 - 20, rnd() * 40 - 20] as Vec3)
      const s = sphereFromPoints(points)
      for (const p of points) {
        const d = distance(p, s.center) - s.radius
        if (d > 1e-9) { manquants += 1; pire = Math.max(pire, d) }
      }
    }
    assert.equal(manquants, 0, `${manquants} point(s) hors sphère, dépassement max ${pire.toFixed(6)}`)
  })

  test('AABB : volume, centre, intersection et cas vide', () => {
    const cube: Vec3[] = [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]]
    const b = aabbFromPoints(cube)
    assert.equal(aabbVolume(b), 1)
    assert.deepEqual(aabbCenter(b), [0, 0, 0])
    assert.deepEqual(aabbFromPoints([]), { min: [0, 0, 0], max: [0, 0, 0] })
    assert.equal(aabbIntersect({ min: [0, 0, 0], max: [1, 1, 1] }, { min: [2, 2, 2], max: [3, 3, 3] }), false)
    assert.equal(aabbIntersect({ min: [0, 0, 0], max: [1, 1, 1] }, { min: [1, 0, 0], max: [2, 1, 1] }), true, 'le contact exact compte comme intersection')
  })
})

// ===========================================================================
describe('frustum — la disposition de la matrice est déclarée, jamais devinée', () => {
  // Perspective 90°, aspect 1, near 1, far 100, caméra vers -Z.
  const f = 1 / Math.tan(Math.PI / 4)
  const n = 1
  const fa = 100
  const COLONNES = [f, 0, 0, 0, 0, f, 0, 0, 0, 0, (fa + n) / (n - fa), -1, 0, 0, (2 * fa * n) / (n - fa), 0]
  const LIGNES = Array.from({ length: 16 }, (_, k) => COLONNES[(k % 4) * 4 + Math.floor(k / 4)])

  /** Vérité indépendante : après projection, −w ≤ x,y,z ≤ w. */
  function dansParProjection(p: Vec3): boolean {
    const e = (r: number, c: number) => COLONNES[c * 4 + r]
    const o = [0, 1, 2, 3].map((r) => e(r, 0) * p[0] + e(r, 1) * p[1] + e(r, 2) * p[2] + e(r, 3))
    const w = o[3]
    if (w <= 0) return false
    return Math.abs(o[0]) <= w && Math.abs(o[1]) <= w && Math.abs(o[2]) <= w
  }

  const POINTS: Array<[string, Vec3]> = [
    ['devant, au centre', [0, 0, -5]],
    ['devant, au loin', [0, 0, -50]],
    ['derrière la caméra', [0, 0, 5]],
    ['au-delà du plan lointain', [0, 0, -500]],
    ['avant le plan proche', [0, 0, -0.5]],
    ['très à droite', [100, 0, -5]],
    ['très en haut', [0, 100, -5]],
    ['dans le cône', [2, 2, -5]],
    ['hors du cône', [10, 0, -5]],
  ]

  for (const [nom, matrice, disposition] of [
    ['colonnes (Three.js)', COLONNES, 'column-major'],
    ['lignes', LIGNES, 'row-major'],
  ] as Array<[string, number[], 'row-major' | 'column-major']>) {
    test(`matrice rangée en ${nom} : les 9 points sont classés juste`, () => {
      const fr = frustumFromMatrix(matrice, disposition)
      for (const [desc, p] of POINTS) {
        assert.equal(
          pointInFrustum(p, fr), dansParProjection(p),
          `${desc} ${JSON.stringify(p)} mal classé avec une matrice en ${nom}`,
        )
      }
    })
  }

  test('la disposition par défaut reste « lignes » (compatibilité)', () => {
    const fr = frustumFromMatrix(LIGNES)
    for (const [, p] of POINTS) assert.equal(pointInFrustum(p, fr), dansParProjection(p))
  })

  test('aabbInFrustum est conservatif : jamais de faux négatif', () => {
    const fr = frustumFromMatrix(COLONNES, 'column-major')
    const rnd = tirages(7)
    let fautes = 0
    for (let essai = 0; essai < 500; essai += 1) {
      const c: Vec3 = [rnd() * 40 - 20, rnd() * 40 - 20, -rnd() * 60]
      const e = rnd() * 3 + 0.1
      const box = { min: [c[0] - e, c[1] - e, c[2] - e] as Vec3, max: [c[0] + e, c[1] + e, c[2] + e] as Vec3 }
      const coins: Vec3[] = []
      for (const x of [box.min[0], box.max[0]]) {
        for (const y of [box.min[1], box.max[1]]) {
          for (const z of [box.min[2], box.max[2]]) coins.push([x, y, z])
        }
      }
      if (coins.some((p) => pointInFrustum(p, fr)) && !aabbInFrustum(box, fr)) fautes += 1
    }
    assert.equal(fautes, 0, `${fautes} boîte(s) visible(s) rejetée(s) — autant de trous dans le rendu`)
  })

  test('une matrice qui n’a pas 16 éléments est refusée', () => {
    assert.throws(() => frustumFromMatrix([1, 2, 3]))
  })
})

// ===========================================================================
describe('rayon contre boîte', () => {
  const boite = { min: [-1, -1, -1] as Vec3, max: [1, 1, 1] as Vec3 }
  const CAS: Array<[string, Vec3, Vec3, number | null]> = [
    ['frontal', [0, 0, -5], [0, 0, 1], 4],
    ['latéral', [-5, 0, 0], [1, 0, 0], 4],
    ['origine à l’intérieur', [0, 0, 0], [0, 0, 1], 0],
    ['manque la boîte', [0, 5, -5], [0, 0, 1], null],
    ['dos tourné', [0, 0, 5], [0, 0, 1], null],
    ['parallèle et à côté', [0, 5, -5], [1, 0, 0], null],
    ['direction nulle', [0, 0, -5], [0, 0, 0], null],
  ]
  for (const [nom, o, d, attendu] of CAS) {
    test(nom, () => {
      const r = rayAabbIntersect(o, d, boite)
      if (attendu === null) assert.equal(r, null)
      else {
        assert.notEqual(r, null, 'intersection manquée')
        assert.ok(Math.abs(r! - attendu) < 1e-6, `t = ${r} au lieu de ${attendu}`)
      }
    })
  }
})

// ===========================================================================
describe('échantillonnage de quaternions — jamais de NaN sur un os', () => {
  type Q = [number, number, number, number]
  const rotY = (a: number): Q => [0, Math.sin(a / 2), 0, Math.cos(a / 2)]
  const anim = (duration: number, loop: boolean, frames: Array<{ t: number; q: Q }>) => ({
    name: 'test', duration, loop,
    frames: frames.map((f) => ({ t: f.t, rotations: { hips: f.q } })),
  }) as never

  const norme = (q: Q) => Math.hypot(q[0], q[1], q[2], q[3])

  test('201 échantillons : unitaires et finis', () => {
    const a = anim(2, false, [{ t: 0, q: rotY(0) }, { t: 1, q: rotY(Math.PI / 2) }, { t: 2, q: rotY(Math.PI) }])
    for (let i = 0; i <= 200; i += 1) {
      const q = sampleAnimation(a, 'hips', i / 100) as Q
      assert.ok(q.every(Number.isFinite), `t=${i / 100} rend ${JSON.stringify(q)}`)
      assert.ok(Math.abs(norme(q) - 1) < 1e-9, `t=${i / 100} : norme ${norme(q)}`)
    }
  })

  test('les extrémités sont rendues exactement', () => {
    const a = anim(2, false, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(Math.PI) }])
    assert.deepEqual(sampleAnimation(a, 'hips', 0), [0, 0, 0, 1])
    const fin = sampleAnimation(a, 'hips', 2) as Q
    assert.ok(Math.abs(fin[1] - 1) < 1e-9 && Math.abs(fin[3]) < 1e-9, JSON.stringify(fin))
  })

  test('chemin court : q et −q désignent la même rotation', () => {
    const a = anim(1, false, [{ t: 0, q: [0, 0, 0, 1] }, { t: 1, q: [0, 0, 0, -1] }])
    const milieu = sampleAnimation(a, 'hips', 0.5) as Q
    assert.ok(Math.abs(norme(milieu) - 1) < 1e-9, `interpolation dégénérée : ${JSON.stringify(milieu)}`)
  })

  const DÉGÉNÉRÉS: Array<[string, unknown, number]> = [
    ['durée nulle en boucle', anim(0, true, [{ t: 0, q: rotY(0) }, { t: 0, q: rotY(1) }]), 0.5],
    ['durée nulle sans boucle', anim(0, false, [{ t: 0, q: rotY(0) }]), 0.5],
    ['aucune image', anim(1, false, []), 0.5],
    ['une seule image', anim(1, false, [{ t: 0, q: rotY(1) }]), 0.5],
    ['deux images au même instant', anim(1, false, [{ t: 0.5, q: rotY(0) }, { t: 0.5, q: rotY(2) }]), 0.5],
    ['temps NaN', anim(2, false, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), NaN],
    ['temps infini en boucle', anim(2, true, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), Infinity],
    ['temps négatif en boucle', anim(2, true, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), -7],
    ['durée NaN', anim(NaN, true, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), 1],
  ]
  for (const [nom, animation, t] of DÉGÉNÉRÉS) {
    test(`${nom} : quaternion unitaire fini malgré tout`, () => {
      const q = sampleAnimation(animation as never, 'hips', t) as Q
      assert.ok(
        q.every(Number.isFinite),
        `${JSON.stringify(q)} — un quaternion NaN posé sur un os fait disparaître le maillage.`,
      )
      assert.ok(Math.abs(norme(q) - 1) < 1e-6, `norme ${norme(q)}`)
    })
  }

  test('un os absent de l’animation rend l’identité', () => {
    const a = anim(2, false, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }])
    assert.deepEqual(sampleAnimation(a, 'os-inexistant', 1), [0, 0, 0, 1])
  })
})
