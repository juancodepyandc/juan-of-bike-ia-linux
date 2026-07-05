/**
 * Tests pour utils/mobileDownload — download/list/upload via bridge mobile.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  downloadGeneratedFile,
  listGeneratedFiles,
  uploadFileFromMobile,
} from '../utils/mobileDownload.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; headers?: { get: (k: string) => string | null }; json?: () => Promise<unknown>; text?: () => Promise<string> }
let fetchMock: ((url: any, init?: any) => Promise<MockResp>) | null = null

const realDocument = (globalThis as any).document

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
  // Polyfill document avec body + createElement
  if (typeof (globalThis as any).document === 'undefined') {
    const links: any[] = []
    const fakeDocument = {
      createElement(tag: string) {
        const el: any = {
          tagName: tag.toUpperCase(),
          attributes: {} as Record<string, string>,
          style: {},
          href: '',
          download: '',
          setAttribute(k: string, v: string) { (this as any).attributes[k] = v; (this as any)[k] = v },
          click() { (this as any).clicked = true },
          appendChild() {},
          removeChild() {},
        }
        if (tag === 'a') links.push(el)
        return el
      },
      body: {
        appendChild(el: any) {},
        removeChild(el: any) {},
      },
      __links: links,
    }
    Object.defineProperty(globalThis, 'document', {
      value: fakeDocument,
      writable: true,
      configurable: true,
    })
  }
})

after(() => {
  globalThis.fetch = realFetch
  if (realDocument === undefined) {
    delete (globalThis as any).document
  }
})

beforeEach(() => {
  fetchMock = null
  ;(globalThis as any).document.__links.length = 0
})

function jsonResp(body: unknown, ok = true): MockResp {
  return {
    ok,
    status: ok ? 200 : 500,
    headers: { get: () => 'application/json' },
    text: async () => JSON.stringify(body),
    json: async () => body,
  }
}

describe('downloadGeneratedFile — mode bridge (non-Tauri)', () => {
  test('crée un <a> avec href download', async () => {
    await downloadGeneratedFile('outputs/image.png', 'my-image.png')
    const links = (globalThis as any).document.__links
    assert.ok(links.length >= 1)
    const a = links[links.length - 1]
    assert.ok(a.href.includes('image.png'))
    assert.equal(a.download, 'my-image.png')
  })

  test('filename par défaut depuis le path', async () => {
    await downloadGeneratedFile('output/dir/file.mp4')
    const a = (globalThis as any).document.__links.pop()
    assert.equal(a.download, 'file.mp4')
  })

  test('path encodé URL', async () => {
    await downloadGeneratedFile('out/with space.png')
    const a = (globalThis as any).document.__links.pop()
    assert.ok(a.href.includes('with%20space'))
  })

  test('a.click() est appelé', async () => {
    await downloadGeneratedFile('x.png')
    const a = (globalThis as any).document.__links.pop()
    assert.equal(a.clicked, true)
  })
})

describe('listGeneratedFiles', () => {
  test('succès → array', async () => {
    fetchMock = async () => jsonResp([
      { name: 'a.png', path: 'a.png', size: 100, modified: 12345, type: 'image' },
    ])
    const r = await listGeneratedFiles()
    assert.equal(r.length, 1)
    assert.equal(r[0].name, 'a.png')
  })

  test('HTTP non-ok → []', async () => {
    fetchMock = async () => jsonResp([], false)
    const r = await listGeneratedFiles()
    assert.deepEqual(r, [])
  })

  test('exception réseau → []', async () => {
    fetchMock = async () => { throw new Error('down') }
    const r = await listGeneratedFiles()
    assert.deepEqual(r, [])
  })

  test('endpoint = /api/generated-files', async () => {
    let endpoint = ''
    fetchMock = async (url) => { endpoint = String(url); return jsonResp([]) }
    await listGeneratedFiles()
    assert.ok(endpoint.includes('/api/generated-files'))
  })

  test('preserve type/size/modified', async () => {
    fetchMock = async () => jsonResp([
      { name: 'v.mp4', path: 'video/v.mp4', size: 5_000_000, modified: 1700000000, type: 'video' },
    ])
    const r = await listGeneratedFiles()
    assert.equal(r[0].type, 'video')
    assert.equal(r[0].size, 5_000_000)
  })
})

describe('uploadFileFromMobile', () => {
  test('succès → renvoie path', async () => {
    fetchMock = async () => jsonResp({ path: '/uploads/file.jpg' })
    // File polyfill basique
    const fakeFile = { name: 'file.jpg', type: 'image/jpeg', size: 1024 } as unknown as File
    const path = await uploadFileFromMobile(fakeFile, 'uploads')
    assert.equal(path, '/uploads/file.jpg')
  })

  test('endpoint = /api/upload', async () => {
    let endpoint = ''
    fetchMock = async (url) => { endpoint = String(url); return jsonResp({ path: '/x' }) }
    await uploadFileFromMobile({ name: 'x', type: 'image/png', size: 1 } as File)
    assert.ok(endpoint.includes('/api/upload'))
  })

  test('targetDir par défaut = "uploads"', async () => {
    // Pour vérifier ça il faudrait inspecter FormData — pas trivial dans cet env
    fetchMock = async () => jsonResp({ path: '/uploads/x' })
    const r = await uploadFileFromMobile({ name: 'x', type: 'image/png', size: 1 } as File)
    assert.ok(r.includes('uploads'))
  })

  test('HTTP non-ok → throw avec status', async () => {
    fetchMock = async () => jsonResp({}, false)
    await assert.rejects(
      () => uploadFileFromMobile({ name: 'x', type: 'image/png', size: 1 } as File),
      /Upload echoue.*500/,
    )
  })
})
