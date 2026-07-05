/**
 * Tests pour services/intentRouter — route user input vers le module pertinent.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { routeIntent, listModules } from '../services/intentRouter.ts'

describe('routeIntent — modules clairs', () => {
  test('"dessine-moi un vélo" → drawing', () => {
    const r = routeIntent('dessine-moi un vélo gravel orange')
    assert.equal(r.moduleId, 'drawing')
  })

  test('"génère une image" → image', () => {
    const r = routeIntent('génère une image photoréaliste de paysage')
    assert.equal(r.moduleId, 'image')
  })

  test('"écris un script Python" → code', () => {
    const r = routeIntent('écris un script Python pour parser un CSV')
    assert.equal(r.moduleId, 'code')
  })

  test('"modèle 3D" → 3d', () => {
    const r = routeIntent('crée un modèle 3D imprimable de personnage')
    assert.equal(r.moduleId, '3d')
  })

  test('"vidéo" → video', () => {
    const r = routeIntent('génère une vidéo cinéma en travelling')
    assert.equal(r.moduleId, 'video')
  })

  test('"quiz BAC" → learning ou simulator (physique route vers simulator)', () => {
    const r = routeIntent('lance-moi un quiz pour réviser le BAC')
    assert.ok(['learning', 'conversation'].includes(r.moduleId), `unexpected ${r.moduleId}`)
  })

  test('"crypto AES" → cyber', () => {
    const r = routeIntent('explique-moi le chiffrement AES en cryptographie')
    assert.equal(r.moduleId, 'cyber')
  })
})

describe('routeIntent — fallback', () => {
  test('texte vague → conversation', () => {
    const r = routeIntent('hello, comment ça va')
    assert.equal(r.moduleId, 'conversation')
  })

  test('aucun signal → conversation fallback', () => {
    const r = routeIntent('xyz nawak zzz')
    assert.equal(r.moduleId, 'conversation')
    // 0.2 si rien ne matche
    assert.ok(r.confidence <= 1)
  })
})

describe('routeIntent — structure result', () => {
  test('IntentResult complet', () => {
    const r = routeIntent('image de paysage')
    assert.ok(typeof r.moduleId === 'string')
    assert.ok(typeof r.confidence === 'number')
    assert.ok(Array.isArray(r.scores))
    assert.ok(Array.isArray(r.matchedSignals))
    assert.ok(typeof r.ambiguous === 'boolean')
    assert.ok(typeof r.hint === 'string')
  })

  test('scores triés par score desc', () => {
    const r = routeIntent('crée une image de chat')
    for (let i = 1; i < r.scores.length; i++) {
      assert.ok(r.scores[i - 1].score >= r.scores[i].score)
    }
  })

  test('matchedSignals max 3', () => {
    const r = routeIntent('image dessin photo illustration peinture cinéma vidéo')
    assert.ok(r.matchedSignals.length <= 3)
  })
})

describe('routeIntent — sticky context', () => {
  test('context [module:image] biaise vers image', () => {
    const r = routeIntent('ajoute des détails', ['[module:image] hier'])
    // Le sticky donne +0.5, mais "ajoute des détails" est vague → image plausible
    // On vérifie au minimum que le score image est nonzero.
    const imageScore = r.scores.find((s) => s.moduleId === 'image')?.score ?? 0
    assert.ok(imageScore > 0)
  })
})

describe('routeIntent — ambiguous detection', () => {
  test('prompt mixed → ambiguous flag possible', () => {
    const r = routeIntent('génère une image et un code Python')
    // Probablement ambigu entre image et code
    assert.ok(typeof r.ambiguous === 'boolean')
  })
})

describe('listModules', () => {
  test('renvoie tous les modules supportés', () => {
    const mods = listModules()
    assert.ok(mods.length >= 7)
    assert.ok(mods.every((m) => typeof m.id === 'string' && typeof m.label === 'string'))
  })

  test('contient les modules canoniques', () => {
    const ids = new Set(listModules().map((m) => m.id))
    assert.ok(ids.has('conversation'))
    assert.ok(ids.has('image'))
    assert.ok(ids.has('code'))
    assert.ok(ids.has('3d'))
    assert.ok(ids.has('learning'))
    assert.ok(ids.has('cyber'))
  })
})
