// cdp_tunnel_test_3d.mjs — spawn a local static HTTP server for the
// standalone PBR viewer (since Vite's public-dir cache is stale on the
// 36h-old dev server), open it in headless Chrome, and capture screenshots
// of pbr2.glb + pbr_mech.glb. Validates that three.js GLTFLoader renders
// our PBR meshes (baseColor + metallicRoughness + any normalMap attached
// by Stage 3.6) correctly.
//
// Usage: node cdp_tunnel_test_3d.mjs [unused] [outDir]
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUTDIR = process.argv[3] || 'C:\\Users\\Juan\\Desktop\\ia\\AuroraIA-v2'
const TEST_DIR = 'C:\\Users\\Juan\\Desktop\\ia\\AuroraIA-v2\\application\\public\\_pbr_test'
const MESHES = ['pbr_maldives_proc.glb']
const VIEWS = ['front_3q', 'left', 'back_3q']  // 3 camera angles per mesh

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer()
    s.listen(0, () => { const p = s.address().port; s.close(() => res(p)) })
    s.on('error', rej)
  })
}

async function getJSON(url) {
  const r = await fetch(url)
  const txt = await r.text()
  // Chrome's /json/* endpoints sometimes prepend a non-JSON warning line
  // ("Using unsafe HTTP verb …"); strip it before parsing.
  const start = txt.search(/[\[{]/)
  return JSON.parse(start >= 0 ? txt.slice(start) : txt)
}

class CDP {
  constructor(wsUrl) { this.wsUrl = wsUrl; this.id = 0; this.pending = new Map(); this.events = [] }
  connect() {
    return new Promise((res, rej) => {
      this.ws = new WebSocket(this.wsUrl)
      this.ws.onopen = () => res()
      this.ws.onerror = (e) => rej(e)
      this.ws.onmessage = (m) => {
        const msg = JSON.parse(m.data)
        if (msg.id && this.pending.has(msg.id)) {
          const { res, rej } = this.pending.get(msg.id); this.pending.delete(msg.id)
          msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result)
        } else if (msg.method) {
          this.events.push(msg)
        }
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)) } }, 45000)
    })
  }
  async waitEvent(method, timeoutMs = 20000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeoutMs) {
      const e = this.events.find((x) => x.method === method)
      if (e) return e
      await sleep(100)
    }
    return null
  }
  async evalJS(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    return r.result?.value
  }
  async screenshot(path) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' })
    writeFileSync(path, Buffer.from(r.data, 'base64'))
    return path
  }
}

;(async () => {
  // 1. spawn a local static http server on a free port serving TEST_DIR
  const staticPort = await freePort()
  console.log('[cdp3d] static server on port', staticPort, 'dir', TEST_DIR)
  const staticProc = spawn(
    'python',
    ['-m', 'http.server', String(staticPort), '--directory', TEST_DIR, '--bind', '127.0.0.1'],
    { stdio: 'ignore', detached: false }
  )
  staticProc.on('error', (e) => { console.error('static server error', e); process.exit(1) })
  // wait for the http server to come up
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${staticPort}/viewer.html`)
      if (r.ok) break
    } catch {}
    await sleep(200)
  }
  console.log('[cdp3d] static server ready')

  const port = await freePort()
  const udd = mkdtempSync(join(tmpdir(), 'aurora-cdp-3d-'))
  // NOTE: we enable GPU because the viewer needs WebGL; --headless=new supports it.
  const args = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${udd}`,
    '--headless=new',
    '--no-first-run', '--no-default-browser-check',
    '--disable-extensions',
    '--enable-webgl', '--use-gl=swiftshader',
    '--window-size=1280,960',
    'about:blank',
  ]
  console.log('[cdp3d] launching chrome on port', port)
  const proc = spawn(CHROME, args, { stdio: 'ignore', detached: false })
  proc.on('error', (e) => { console.error('chrome spawn error', e); process.exit(1) })

  let version = null
  for (let i = 0; i < 40; i++) {
    try { version = await getJSON(`http://127.0.0.1:${port}/json/version`); break } catch { await sleep(250) }
  }
  if (!version) { console.error('[cdp3d] devtools never came up'); proc.kill(); staticProc.kill(); process.exit(1) }
  console.log('[cdp3d] browser:', version['Browser'])

  for (const mesh of MESHES) {
   for (const view of VIEWS) {
    const url = `http://127.0.0.1:${staticPort}/viewer.html?mesh=${encodeURIComponent(mesh)}&view=${encodeURIComponent(view)}`
    let tab
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' })
      const t = await r.text(); const s = t.search(/[\[{]/); tab = JSON.parse(s >= 0 ? t.slice(s) : t)
    } catch {
      try {
        const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`)
        const t = await r.text(); const s = t.search(/[\[{]/); tab = JSON.parse(s >= 0 ? t.slice(s) : t)
      } catch { /* fall through to list-based fallback below */ }
    }
    if (!tab?.webSocketDebuggerUrl) {
      // Chrome sometimes prepends a non-JSON warning ("Using unsafe ...");
      // fall back to /json/list which is more tolerant.
      try {
        const list = await getJSON(`http://127.0.0.1:${port}/json/list`)
        tab = list.find((t) => t.type === 'page' && (t.url.includes('viewer.html') || t.url.includes('127.0.0.1')))
      } catch { /* ignore */ }
    }
    if (!tab?.webSocketDebuggerUrl) {
      // Last resort: list pages, take any page tab.
      try {
        const list = await getJSON(`http://127.0.0.1:${port}/json/list`)
        tab = list.find((t) => t.type === 'page')
      } catch {}
    }
    if (!tab?.webSocketDebuggerUrl) {
      console.error(`[cdp3d] ${mesh}: could not obtain a tab`); continue
    }
    console.log(`[cdp3d] ${mesh} → ${url}`)
    const cdp = new CDP(tab.webSocketDebuggerUrl)
    await cdp.connect()
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Page.navigate', { url })
    await cdp.waitEvent('Page.loadEventFired', 30000)
    // poll the viewer-readiness flag
    let info = null
    for (let i = 0; i < 60; i++) {
      info = await cdp.evalJS('window.__pbrViewerReady || null')
      if (info && (info.ok === true || info.ok === false)) break
      await sleep(500)
    }
    console.log(`[cdp3d] ${mesh} ready=`, JSON.stringify(info, null, 2))
    await sleep(800) // let the first frame paint
    const out = join(OUTDIR, `pbr_viewer_${mesh.replace('.glb', '')}_${view}.png`)
    await cdp.screenshot(out)
    console.log('[cdp3d] saved', out)
    // close the tab, NOT the browser (we need it alive for the next mesh)
    if (tab?.id) {
      await fetch(`http://127.0.0.1:${port}/json/close/${tab.id}`).catch(() => {})
    }
   }
  }

  console.log('[cdp3d] DONE')
  try { await fetch(`http://127.0.0.1:${port}/json/close`).catch(() => {}) } catch {}
  proc.kill()
  staticProc.kill()
  process.exit(0)
})().catch((e) => { console.error('[cdp3d] FATAL', e); process.exit(1) })
