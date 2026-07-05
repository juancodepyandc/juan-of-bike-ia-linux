/**
 * Tests pour les helpers purs de utils/runtime.ts :
 *  - hostnameLooksLikeTunnel : détection des hostnames de tunnels HTTPS
 *  - toBrowserFileUrl : conversion path local → URL utilisable par <img>
 *
 * On n'importe pas runtime.ts directement (il fait référence à
 * import.meta.env qui n'existe pas sous Node) — au lieu de ça on importe
 * un fichier pure helpers, mais comme les helpers ici sont sans dépendance
 * d'import.meta on peut tenter directement.
 *
 * Si l'import casse, on devra extraire ces helpers dans runtimeCore.ts.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// import depuis le module directement, en testant uniquement les fonctions pures.
// Si jamais runtime.ts a des side effects à l'import (lecture import.meta.env),
// le test cassera et on extraira dans runtimeCore.ts.
import {
  hostnameLooksLikeTunnel,
  toBrowserFileUrl,
  getRuntimeMode,
  isTauriRuntime,
  isCloudRuntime,
  isDesktopRuntime,
  getCloudBridgeUrl,
  getBridgeUrl,
} from '../utils/runtime.ts'

describe('hostnameLooksLikeTunnel', () => {
  test('cloudflare trycloudflare.com exact', () => {
    assert.equal(hostnameLooksLikeTunnel('trycloudflare.com'), true)
  })

  test('cloudflare sous-domaine', () => {
    assert.equal(hostnameLooksLikeTunnel('aurora-test.trycloudflare.com'), true)
  })

  test('localtunnel loca.lt', () => {
    assert.equal(hostnameLooksLikeTunnel('juan-aurora-ia.loca.lt'), true)
  })

  test('ngrok variantes', () => {
    assert.equal(hostnameLooksLikeTunnel('abc.ngrok-free.app'), true)
    assert.equal(hostnameLooksLikeTunnel('xyz.ngrok.app'), true)
    assert.equal(hostnameLooksLikeTunnel('legacy.ngrok.io'), true)
  })

  test('serveo et localhost.run', () => {
    assert.equal(hostnameLooksLikeTunnel('foo.serveo.net'), true)
    assert.equal(hostnameLooksLikeTunnel('bar.localhost.run'), true)
    assert.equal(hostnameLooksLikeTunnel('baz.lhr.life'), true)
  })

  test('pinggy et bore', () => {
    assert.equal(hostnameLooksLikeTunnel('test.pinggy.link'), true)
    assert.equal(hostnameLooksLikeTunnel('alice.bore.pub'), true)
  })

  test('case-insensitive', () => {
    assert.equal(hostnameLooksLikeTunnel('Test.NGROK.app'), true)
  })

  test('domaines normaux → false', () => {
    assert.equal(hostnameLooksLikeTunnel('localhost'), false)
    assert.equal(hostnameLooksLikeTunnel('127.0.0.1'), false)
    assert.equal(hostnameLooksLikeTunnel('example.com'), false)
    assert.equal(hostnameLooksLikeTunnel('google.com'), false)
  })

  test('typo / faux positif évité', () => {
    // "trycloudflare-evil.com" n'est PAS un tunnel cloudflare
    assert.equal(hostnameLooksLikeTunnel('trycloudflare-evil.com'), false)
    // "abcloca.lt" ne matche pas .loca.lt suffix
    assert.equal(hostnameLooksLikeTunnel('abcloca.lt'), false)
  })
})

describe('toBrowserFileUrl', () => {
  test('http URL passe inchangée', () => {
    assert.equal(toBrowserFileUrl('http://example.com/img.png'), 'http://example.com/img.png')
  })

  test('https URL passe inchangée', () => {
    assert.equal(toBrowserFileUrl('https://example.com/img.png'), 'https://example.com/img.png')
  })

  test('data URL passe inchangée', () => {
    assert.equal(toBrowserFileUrl('data:image/png;base64,abc'), 'data:image/png;base64,abc')
  })

  test('blob URL passe inchangée', () => {
    assert.equal(toBrowserFileUrl('blob:http://localhost/abc'), 'blob:http://localhost/abc')
  })

  test('file URL passe inchangée', () => {
    assert.equal(toBrowserFileUrl('file:///C:/foo.png'), 'file:///C:/foo.png')
  })

  test('chemin Windows absolu → file:/// + encoding', () => {
    const out = toBrowserFileUrl('C:\\Users\\Juan\\image.png')
    assert.equal(out, 'file:///C:/Users/Juan/image.png')
  })

  test('chemin Windows avec espace → encodage', () => {
    const out = toBrowserFileUrl('C:\\Users\\Juan David\\img.png')
    assert.ok(out.includes('%20') || out.includes('Juan David'))
    assert.ok(out.startsWith('file:///C:'))
  })

  test('chemin relatif → encodé sans préfixe file', () => {
    const out = toBrowserFileUrl('output/drawings/img.png')
    assert.ok(!out.startsWith('file://'))
    assert.ok(out.includes('output/drawings/img.png'))
  })

  test('vide → vide', () => {
    assert.equal(toBrowserFileUrl(''), '')
  })

  test('backslash → forward slash', () => {
    const out = toBrowserFileUrl('D:\\projects\\test.glb')
    assert.equal(out, 'file:///D:/projects/test.glb')
  })
})

describe('runtime mode (SSR / Node env)', () => {
  test('getRuntimeMode → "browser" sous Node (typeof window === undefined)', () => {
    // Sous Node, window n'existe pas → branche immédiate "browser".
    assert.equal(getRuntimeMode(), 'browser')
  })

  test('isTauriRuntime → false sous Node', () => {
    assert.equal(isTauriRuntime(), false)
  })

  test('isCloudRuntime → false sous Node', () => {
    assert.equal(isCloudRuntime(), false)
  })

  test('isDesktopRuntime → false sous Node', () => {
    assert.equal(isDesktopRuntime(), false)
  })

  test('getCloudBridgeUrl → "" sous Node (import.meta.env undefined)', () => {
    // Avant le fix passe 40, ce test crashait avec
    // "Cannot read properties of undefined (reading 'VITE_BRIDGE_URL')".
    assert.equal(getCloudBridgeUrl(), '')
  })

  test('getBridgeUrl → localhost:3001 par défaut sous Node', () => {
    // Sans Tauri/Cloud/Vite env → fallback localhost.
    assert.equal(getBridgeUrl(), 'http://127.0.0.1:3001')
  })
})
