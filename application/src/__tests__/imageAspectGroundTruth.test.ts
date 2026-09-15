/**
 * Ratio d'image recommandé — vocabulaire français des formats.
 *
 * POURQUOI CE FICHIER EXISTE. Le module se replie sur 1:1 quand aucun mot-clé
 * ne répond. Deux demandes très ordinaires tombaient dans ce repli :
 * « affiche de film » et « bannière pour un site web » rendaient toutes deux
 * un CARRÉ. Le repli ne signalait rien : la sortie était plausible et fausse,
 * le pire des deux mondes. Et « paysage de montagne panoramique » rendait
 * 3:2, parce que « panoramique » CONCURRENÇAIT « paysage » au lieu de le
 * qualifier — deux mots-clés paysage à 10 points battaient le panoramique
 * à 15.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/imageAspectGroundTruth.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { recommendAspectRatio, bestAspectRatio } from '../services/imageAspectRecommender.ts'

const ATTENDUS: Array<[string, string, string]> = [
  // sujet, ratio attendu, justification du format
  ['portrait d’une femme', '2:3', 'portrait photographique'],
  ['visage en gros plan', '2:3', 'portrait'],
  ['une cathédrale gothique', '2:3', 'sujet vertical élancé'],
  ['photo de paysage', '3:2', 'paysage standard'],
  ['un lac de montagne', '3:2', 'paysage standard'],
  ['paysage de montagne panoramique', '21:9', 'le panoramique QUALIFIE le paysage'],
  ['vue panoramique de la ville', '21:9', 'panoramique'],
  ['plan cinemascope d’un désert', '21:9', 'format cinéma'],
  ['affiche de film', '2:3', 'affiche : format vertical normalisé'],
  ['une affiche de concert', '2:3', 'affiche'],
  ['couverture de livre', '2:3', 'couverture'],
  ['flyer pour une soirée', '2:3', 'imprimé vertical'],
  ['bannière pour un site web', '21:9', 'bandeau : le plus large disponible'],
  ['bandeau d’en-tête', '21:9', 'bandeau'],
  ['image de couverture linkedin', '21:9', 'bandeau de profil'],
  ['miniature youtube', '16:9', 'vignette de plateforme vidéo'],
  ['logo carré', '1:1', 'logo'],
  ['icône d’application', '1:1', 'icône'],
  ['pochette d album', '1:1', 'pochette'],
  ['story instagram', '9:16', 'plateforme verticale'],
  ['une vidéo tiktok', '9:16', 'plateforme verticale'],
  ['un plan pour youtube', '16:9', 'plateforme large'],
]

describe('recommendAspectRatio — vocabulaire des formats', () => {
  for (const [sujet, ratio, pourquoi] of ATTENDUS) {
    test(`« ${sujet} » → ${ratio}  (${pourquoi})`, () => {
      const obtenu = bestAspectRatio(sujet)
      assert.equal(
        obtenu.ratio, ratio,
        `« ${sujet} » : attendu ${ratio}, obtenu ${obtenu.ratio} — ${obtenu.reason}`,
      )
    })
  }

  test('aucun de ces sujets ne tombe dans le repli carré', () => {
    const replis = ATTENDUS
      .map(([s]) => [s, bestAspectRatio(s)] as const)
      .filter(([, r]) => r.reason.includes('fallback'))
    assert.deepEqual(
      replis.map(([s]) => s), [],
      'ces sujets ne rencontrent aucun mot-clé et rendent un carré par défaut',
    )
  })
})

describe('recommendAspectRatio — invariants', () => {
  test('le paramètre explicite --ar l’emporte sur tout le reste', () => {
    assert.equal(bestAspectRatio('--ar 16:9 portrait d’une femme en affiche').ratio, '16:9')
    assert.equal(bestAspectRatio('#9:16 paysage panoramique').ratio, '9:16')
  })

  test('la liste est triée par confiance décroissante', () => {
    const l = recommendAspectRatio('affiche de film panoramique pour youtube')
    for (let i = 1; i < l.length; i += 1) {
      assert.ok(l[i - 1].confidence >= l[i].confidence, 'liste non triée')
    }
  })

  test('la confiance reste dans [0, 1] et chaque candidat est justifié', () => {
    for (const [sujet] of ATTENDUS) {
      for (const c of recommendAspectRatio(sujet)) {
        assert.ok(c.confidence >= 0 && c.confidence <= 1, `${sujet} → ${c.confidence}`)
        assert.ok(c.reason.length > 0, `${sujet} → candidat sans justification`)
      }
    }
  })

  test('les dimensions SDXL sont des multiples de 64 et proches d’un mégapixel', () => {
    for (const [sujet] of ATTENDUS) {
      const { width, height, ratio } = bestAspectRatio(sujet)
      assert.equal(width % 64, 0, `${ratio} : largeur ${width} non multiple de 64`)
      assert.equal(height % 64, 0, `${ratio} : hauteur ${height} non multiple de 64`)
      const mp = width * height / 1_048_576
      assert.ok(mp > 0.85 && mp < 1.15, `${ratio} : ${mp.toFixed(2)} Mpx, hors de la plage stable de SDXL`)
    }
  })

  test('sujet vide ou inconnu : repli carré assumé et annoncé', () => {
    const r = bestAspectRatio('xyzzy plugh')
    assert.equal(r.ratio, '1:1')
    assert.ok(r.reason.includes('fallback'), 'le repli doit se nommer, pas se déguiser')
  })

  test('la casse et les accents ne changent pas le verdict', () => {
    assert.equal(bestAspectRatio('AFFICHE DE FILM').ratio, bestAspectRatio('affiche de film').ratio)
    assert.equal(bestAspectRatio('banniere web').ratio, bestAspectRatio('bannière web').ratio)
  })
})
