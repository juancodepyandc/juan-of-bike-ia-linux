/**
 * Tests pour services/coworkBrowserDetectPure — détection navigateur via UA.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  BROWSERS,
  detectIdFromUA,
  getInstallInstructionsFor,
} from '../services/coworkBrowserDetectPure.ts'

const UA = {
  chrome: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  edge: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
  firefox: 'Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
  safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
  opera: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/110.0.0.0',
  vivaldi: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Vivaldi/6.7.3329.21',
  chromium: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chromium/126.0.0.0',
}

describe('BROWSERS catalogue', () => {
  test('contient toutes les ids attendues', () => {
    const ids = ['chrome', 'edge', 'firefox', 'safari', 'brave', 'opera', 'vivaldi', 'chromium', 'arc', 'unknown']
    for (const id of ids) {
      assert.ok(id in BROWSERS, `${id} manquant`)
    }
  })

  test('chaque entrée a label + engine', () => {
    for (const id of Object.keys(BROWSERS) as Array<keyof typeof BROWSERS>) {
      const m = BROWSERS[id]
      assert.ok(m.label)
      assert.ok(['chromium', 'gecko', 'webkit', 'unknown'].includes(m.engine))
    }
  })

  test('Firefox engine gecko', () => {
    assert.equal(BROWSERS.firefox.engine, 'gecko')
  })

  test('Safari engine webkit', () => {
    assert.equal(BROWSERS.safari.engine, 'webkit')
  })
})

describe('detectIdFromUA', () => {
  test('Chrome UA → chrome', () => {
    assert.equal(detectIdFromUA(UA.chrome), 'chrome')
  })

  test('Edge UA → edge', () => {
    assert.equal(detectIdFromUA(UA.edge), 'edge')
  })

  test('Firefox UA → firefox', () => {
    assert.equal(detectIdFromUA(UA.firefox), 'firefox')
  })

  test('Safari UA (pas Chrome dedans) → safari', () => {
    assert.equal(detectIdFromUA(UA.safari), 'safari')
  })

  test('Opera UA → opera', () => {
    assert.equal(detectIdFromUA(UA.opera), 'opera')
  })

  test('Vivaldi UA → vivaldi', () => {
    assert.equal(detectIdFromUA(UA.vivaldi), 'vivaldi')
  })

  test('Chromium UA → chromium', () => {
    assert.equal(detectIdFromUA(UA.chromium), 'chromium')
  })

  test('Brave flag=true → brave (même UA Chrome)', () => {
    assert.equal(detectIdFromUA(UA.chrome, true), 'brave')
  })

  test('UA vide → unknown', () => {
    assert.equal(detectIdFromUA(''), 'unknown')
  })

  test('UA exotique → unknown', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (Hadron-Collider OS)'), 'unknown')
  })

  test('Edge prioritaire sur Chrome (UA contient les deux)', () => {
    // L'UA Edge contient à la fois Chrome/X et Edg/X — il faut renvoyer 'edge'
    assert.equal(detectIdFromUA(UA.edge), 'edge')
  })

  test('Brave non flagué + UA Chrome → chrome', () => {
    assert.equal(detectIdFromUA(UA.chrome, false), 'chrome')
  })
})

describe('getInstallInstructionsFor', () => {
  test('Chrome → titre Chrome + steps non vides', () => {
    const r = getInstallInstructionsFor('chrome')
    assert.ok(r.title.includes('Chrome'))
    assert.ok(r.steps.length > 0)
  })

  test('Edge → mentionne edge://extensions', () => {
    const r = getInstallInstructionsFor('edge')
    assert.ok(JSON.stringify(r).includes('edge://extensions'))
  })

  test('Firefox → mentionne about:debugging', () => {
    const r = getInstallInstructionsFor('firefox')
    assert.ok(r.steps.some((s) => s.detail?.includes('about:debugging') || s.label?.includes('about:debugging')))
  })

  test('Safari → mentionne Xcode', () => {
    const r = getInstallInstructionsFor('safari')
    assert.ok(JSON.stringify(r).includes('Xcode'))
  })

  test('Unknown → fallback générique', () => {
    const r = getInstallInstructionsFor('unknown')
    assert.ok(r.title.toLowerCase().includes('inconnu') || r.steps.length > 0)
  })

  test('loadUnpackedUrl passé est conservé', () => {
    const r = getInstallInstructionsFor('chrome', 'file:///path/to/extension')
    assert.equal(r.loadUnpackedUrl, 'file:///path/to/extension')
  })

  test('Arc → instructions spécifiques', () => {
    const r = getInstallInstructionsFor('arc')
    assert.ok(r.title.includes('Arc'))
  })

  test('Opera → instructions spécifiques', () => {
    const r = getInstallInstructionsFor('opera')
    assert.ok(r.title.includes('Opera'))
  })

  test('Brave → instructions spécifiques', () => {
    const r = getInstallInstructionsFor('brave')
    assert.ok(r.title.includes('Brave'))
  })

  test('chaque step a un label', () => {
    for (const id of ['chrome', 'edge', 'firefox', 'safari', 'brave', 'opera', 'vivaldi', 'arc'] as const) {
      const r = getInstallInstructionsFor(id)
      for (const s of r.steps) {
        assert.ok(s.label && s.label.length > 0, `${id} step sans label`)
      }
    }
  })
})
