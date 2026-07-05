/**
 * Tests pour services/coworkBrowserDetect — wrapper navigator + bridge fetch.
 */
import { test, describe, before, after } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectCurrentBrowser,
  scanInstalledBrowsers,
  getInstallInstructions,
} from '../services/coworkBrowserDetect.ts'

const realFetch = globalThis.fetch
const realNavigator = (globalThis as any).navigator
let fetchMock: ((url: any, init?: any) => Promise<any>) | null = null

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
})

after(() => {
  globalThis.fetch = realFetch
  if (realNavigator !== undefined) {
    (globalThis as any).navigator = realNavigator
  } else {
    delete (globalThis as any).navigator
  }
})

function setNavigator(userAgent: string, brave = false) {
  Object.defineProperty(globalThis, 'navigator', {
    value: { userAgent, ...(brave ? { brave: {} } : {}) },
    writable: true,
    configurable: true,
  })
}

describe('detectCurrentBrowser', () => {
  test('UA Chrome → id chrome + engine chromium', () => {
    setNavigator('Mozilla/5.0 AppleWebKit/537.36 Chrome/126.0 Safari/537.36')
    const r = detectCurrentBrowser()
    assert.equal(r.id, 'chrome')
    assert.equal(r.engine, 'chromium')
    assert.equal(r.detection, 'ua')
  })

  test('UA Firefox → id firefox + engine gecko', () => {
    setNavigator('Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0')
    const r = detectCurrentBrowser()
    assert.equal(r.id, 'firefox')
    assert.equal(r.engine, 'gecko')
  })

  test('UA Edge → id edge', () => {
    setNavigator('Mozilla/5.0 AppleWebKit/537.36 Chrome/126.0 Safari/537.36 Edg/126.0')
    const r = detectCurrentBrowser()
    assert.equal(r.id, 'edge')
  })

  test('brave flag → detection feature', () => {
    setNavigator('Mozilla/5.0 AppleWebKit/537.36 Chrome/126.0 Safari/537.36', true)
    const r = detectCurrentBrowser()
    assert.equal(r.id, 'brave')
    assert.equal(r.detection, 'feature')
  })

  test('navigator avec UA exotique → unknown', () => {
    setNavigator('Mozilla/5.0 (Hadron-Collider OS)')
    const r = detectCurrentBrowser()
    assert.equal(r.id, 'unknown')
  })

  test('label défini par BROWSERS catalog', () => {
    setNavigator('Mozilla/5.0 AppleWebKit Chrome/126.0 Safari/537.36')
    const r = detectCurrentBrowser()
    assert.ok(r.label.length > 0)
  })
})

describe('scanInstalledBrowsers', () => {
  test('renvoie [] sans bridge accessible', async () => {
    fetchMock = async () => { throw new Error('network down') }
    const r = await scanInstalledBrowsers()
    assert.deepEqual(r, [])
  })

  test('réponse ok=true → liste filtrée installés', async () => {
    fetchMock = async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        browsers: [
          { name: 'chrome', installed: true, label: 'Google Chrome', extension_engine: 'chromium' },
          { name: 'firefox', installed: false, label: 'Mozilla Firefox', extension_engine: 'gecko' },
          { name: 'safari', installed: true, label: 'Safari', extension_engine: 'webkit' },
        ],
      }),
    })
    const r = await scanInstalledBrowsers()
    assert.equal(r.length, 2)
    assert.equal(r[0].id, 'chrome')
    assert.equal(r[1].id, 'safari')
  })

  test('detection = "pc-scan"', async () => {
    fetchMock = async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        browsers: [{ name: 'chrome', installed: true, label: 'Chrome', extension_engine: 'chromium' }],
      }),
    })
    const r = await scanInstalledBrowsers()
    assert.equal(r[0].detection, 'pc-scan')
  })

  test('engine gecko/webkit/chromium mappé', async () => {
    fetchMock = async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        browsers: [
          { name: 'firefox', installed: true, label: 'Firefox', extension_engine: 'gecko' },
          { name: 'safari', installed: true, label: 'Safari', extension_engine: 'webkit' },
          { name: 'chrome', installed: true, label: 'Chrome', extension_engine: 'other-engine' },
        ],
      }),
    })
    const r = await scanInstalledBrowsers()
    assert.equal(r[0].engine, 'gecko')
    assert.equal(r[1].engine, 'webkit')
    // fallback chromium pour 'other-engine'
    assert.equal(r[2].engine, 'chromium')
  })

  test('name inconnu → id unknown', async () => {
    fetchMock = async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        browsers: [{ name: 'mystery-browser', installed: true, label: 'X', extension_engine: 'chromium' }],
      }),
    })
    const r = await scanInstalledBrowsers()
    assert.equal(r[0].id, 'unknown')
  })

  test('HTTP non-ok → []', async () => {
    fetchMock = async () => ({ ok: false, json: async () => ({}) })
    const r = await scanInstalledBrowsers()
    assert.deepEqual(r, [])
  })

  test('ok=false → []', async () => {
    fetchMock = async () => ({ ok: true, json: async () => ({ ok: false }) })
    const r = await scanInstalledBrowsers()
    assert.deepEqual(r, [])
  })
})

describe('getInstallInstructions', () => {
  test('chrome → instructions + loadUnpackedUrl', () => {
    const r = getInstallInstructions('chrome')
    assert.ok(r.title.includes('Chrome'))
    assert.ok(r.steps.length > 0)
  })

  test('firefox → mention about:debugging', () => {
    const r = getInstallInstructions('firefox')
    assert.ok(JSON.stringify(r).includes('about:debugging'))
  })

  test('safari → mention Xcode', () => {
    const r = getInstallInstructions('safari')
    assert.ok(JSON.stringify(r).includes('Xcode'))
  })
})
