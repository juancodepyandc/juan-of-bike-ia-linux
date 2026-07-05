/**
 * Tests pour services/entAdapters — détection adapter ENT par hostname + brief.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  ENT_ADAPTERS,
  detectAdapter,
  buildSectionUrl,
  adapterBrief,
} from '../services/entAdapters.ts'

describe('ENT_ADAPTERS catalogue', () => {
  test('contient au moins Pronote et ÉcoleDirecte', () => {
    const ids = ENT_ADAPTERS.map((a) => a.id)
    assert.ok(ids.includes('pronote'))
    assert.ok(ids.includes('ecoledirecte'))
  })

  test('chaque adapter a id/label/hostMatch/authMarkers/sections', () => {
    for (const a of ENT_ADAPTERS) {
      assert.ok(a.id)
      assert.ok(a.label)
      assert.ok(a.hostMatch instanceof RegExp)
      assert.ok(Array.isArray(a.authMarkers))
      assert.ok(typeof a.sections === 'object')
    }
  })

  test('ids uniques', () => {
    const ids = ENT_ADAPTERS.map((a) => a.id)
    assert.equal(new Set(ids).size, ids.length)
  })

  test('au moins 3 sections par adapter', () => {
    for (const a of ENT_ADAPTERS) {
      const sectionCount = Object.keys(a.sections).filter((k) => a.sections[k as never]).length
      assert.ok(sectionCount >= 3, `${a.id} a moins de 3 sections`)
    }
  })
})

describe('detectAdapter', () => {
  test('hostname Pronote → adapter pronote', () => {
    const r = detectAdapter('0780015h.index-education.com')
    assert.equal(r?.id, 'pronote')
  })

  test('hostname pronote.example.fr → pronote (via regex)', () => {
    const r = detectAdapter('pronote.example.fr')
    assert.equal(r?.id, 'pronote')
  })

  test('hostname ÉcoleDirecte → adapter ecoledirecte', () => {
    const r = detectAdapter('www.ecoledirecte.com')
    assert.equal(r?.id, 'ecoledirecte')
  })

  test('hostname inconnu → null', () => {
    assert.equal(detectAdapter('random-website.com'), null)
  })

  test('hostname vide → null', () => {
    assert.equal(detectAdapter(''), null)
  })

  test('case insensitive', () => {
    const r = detectAdapter('SOMETHING.INDEX-EDUCATION.COM')
    assert.equal(r?.id, 'pronote')
  })
})

describe('buildSectionUrl', () => {
  test('section existante → URL absolue https', () => {
    const adapter = detectAdapter('lycee.index-education.com')!
    const url = buildSectionUrl(adapter, 'lycee.index-education.com', 'home')
    assert.ok(url?.startsWith('https://'))
    assert.ok(url?.includes('lycee.index-education.com'))
  })

  test('section absente → null', () => {
    const adapter = ENT_ADAPTERS[0]
    const r = buildSectionUrl(adapter, 'host.com', '__inexistant__' as never)
    assert.equal(r, null)
  })

  test('chemin sans / leading → ajouté', () => {
    const fakeAdapter = {
      ...ENT_ADAPTERS[0],
      sections: { home: 'no-leading-slash' } as never,
      baseUrl: () => 'https://test.com',
    }
    const url = buildSectionUrl(fakeAdapter as never, 'test.com', 'home')
    assert.equal(url, 'https://test.com/no-leading-slash')
  })
})

describe('adapterBrief', () => {
  test('renvoie un texte multi-lignes décrivant l adapter', () => {
    const adapter = ENT_ADAPTERS[0]
    const brief = adapterBrief(adapter)
    assert.ok(brief.includes(adapter.id))
    assert.ok(brief.includes(adapter.label))
    assert.ok(brief.includes('Sections'))
    assert.ok(brief.includes('Markers auth'))
  })

  test('mentionne iCal si présent', () => {
    const adapter = ENT_ADAPTERS.find((a) => a.icalExportPath)
    if (adapter) {
      const brief = adapterBrief(adapter)
      assert.ok(brief.toLowerCase().includes('ical'))
    }
  })
})
