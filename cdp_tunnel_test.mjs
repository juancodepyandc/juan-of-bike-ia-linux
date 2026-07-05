// cdp_tunnel_test.mjs — lance Chrome (headless) en remote-debugging, ouvre
// AuroraIA via le TUNNEL Cloudflare, navigue vers le module Cyber, capture
// des screenshots + vérifie que le nouveau wording est présent.
//
// Usage: node cdp_tunnel_test.mjs <tunnelUrl>
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const TUNNEL = process.argv[2] || 'https://map-friends-catalog-camps.trycloudflare.com'
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUTDIR = process.argv[3] || 'C:\\Users\\Juan\\Desktop\\ia\\AuroraIA-v2'

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
  return r.json()
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
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)) } }, 30000)
    })
  }
  async waitEvent(method, timeoutMs = 15000) {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
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
  const port = await freePort()
  const udd = mkdtempSync(join(tmpdir(), 'aurora-cdp-'))
  const args = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${udd}`,
    '--headless=new',
    '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-gpu',
    '--window-size=1366,950',
    'about:blank',
  ]
  console.log('[cdp] launching chrome on port', port)
  const proc = spawn(CHROME, args, { stdio: 'ignore', detached: false })
  proc.on('error', (e) => { console.error('chrome spawn error', e); process.exit(1) })

  // wait for the debugging endpoint
  let version = null
  for (let i = 0; i < 40; i++) {
    try { version = await getJSON(`http://127.0.0.1:${port}/json/version`); break } catch { await sleep(250) }
  }
  if (!version) { console.error('[cdp] devtools endpoint never came up'); proc.kill(); process.exit(1) }
  console.log('[cdp] browser:', version['Browser'])

  // open a new tab on the tunnel URL
  let tab
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(TUNNEL + '/')}`, { method: 'PUT' })
    tab = await r.json()
  } catch (e) {
    // fallback: GET
    const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(TUNNEL + '/')}`)
    tab = await r.json()
  }
  if (!tab?.webSocketDebuggerUrl) {
    const list = await getJSON(`http://127.0.0.1:${port}/json/list`)
    tab = list.find((t) => t.type === 'page')
  }
  console.log('[cdp] tab:', tab.url)

  const cdp = new CDP(tab.webSocketDebuggerUrl)
  await cdp.connect()
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await cdp.send('Network.enable')
  await cdp.send('Page.navigate', { url: TUNNEL + '/' })
  const loaded = await cdp.waitEvent('Page.loadEventFired', 25000)
  console.log('[cdp] loadEventFired:', !!loaded)
  await sleep(7000) // let React + tunnel settle

  const title = await cdp.evalJS('document.title')
  const bodyLen = await cdp.evalJS('document.body.innerText.length')
  const hasViteErr = await cdp.evalJS('!!document.querySelector("vite-error-overlay")')
  console.log('[cdp] title:', title, '| bodyLen:', bodyLen, '| viteErrorOverlay:', hasViteErr)
  await cdp.screenshot(join(OUTDIR, 'tunnel_test_1_home.png'))

  // collect console errors
  const consoleErrors = cdp.events
    .filter((e) => e.method === 'Runtime.exceptionThrown' || (e.method === 'Runtime.consoleAPICalled' && e.params?.type === 'error'))
    .map((e) => e.method === 'Runtime.exceptionThrown'
      ? (e.params.exceptionDetails?.exception?.description || e.params.exceptionDetails?.text)
      : e.params.args?.map((a) => a.value || a.description).join(' '))
    .slice(0, 12)
  console.log('[cdp] console errors:', JSON.stringify(consoleErrors, null, 2))

  // click "Cyber" in the sidebar
  const clickedCyber = await cdp.evalJS(`
    (() => {
      const b = [...document.querySelectorAll('button')].find(x => /Cyber/i.test(x.textContent || ''));
      if (b) { b.click(); return b.textContent.trim(); }
      return null;
    })()
  `)
  console.log('[cdp] clicked Cyber button:', clickedCyber)
  await sleep(3500)
  await cdp.screenshot(join(OUTDIR, 'tunnel_test_2_cyber.png'))
  const cyberText = await cdp.evalJS('document.body.innerText')
  const markers = {
    helpCard: /Comment ça marche|atelier de cybersécurité|l'atelier de cybersécurité/i.test(cyberText),
    startBtn: /Démarrer l['’ ]atelier/i.test(cyberText),
    rolePicker: /Tu joues le rôle/i.test(cyberText),
    atelierLabel: /Ateliers — choisis un thème/i.test(cyberText),
    lexique: /Lexique/i.test(cyberText),
  }
  console.log('[cdp] cyber markers:', JSON.stringify(markers, null, 2))
  console.log('[cdp] --- cyber view text (first 1200 chars) ---')
  console.log(cyberText.slice(0, 1200))

  // now Academy → check intake wizard has "Jeu / Enquête"
  const clickedAcad = await cdp.evalJS(`
    (() => {
      const b = [...document.querySelectorAll('button')].find(x => /Academy|Académie/i.test(x.textContent || ''));
      if (b) { b.click(); return b.textContent.trim(); }
      return null;
    })()
  `)
  console.log('[cdp] clicked Academy button:', clickedAcad)
  await sleep(3500)
  await cdp.screenshot(join(OUTDIR, 'tunnel_test_3_academy.png'))
  const acadText = await cdp.evalJS('document.body.innerText')
  console.log('[cdp] academy has "Jeu / Enquête":', /Jeu \/ Enqu[êe]te|Escape game|enquete|enquête/i.test(acadText))

  console.log('[cdp] DONE — screenshots in', OUTDIR)
  await cdp.send('Browser.close').catch(() => {})
  proc.kill()
  process.exit(0)
})().catch((e) => { console.error('[cdp] FATAL', e); process.exit(1) })
