// cdp_drive.mjs — CDP helper: open a URL in headless Chrome, screenshot it,
// and capture console errors / JS exceptions / failed network requests during
// the load. Returns a JSON report on stdout (in addition to writing the PNG).
//
// Usage:
//   node cdp_drive.mjs screenshot <url> <out_png> [w h wait_ms]
// stdout JSON:
//   {ok, console_errors:[], exceptions:[], failed_requests:[], canvas_present, body_text_len}

import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const CHROME =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer()
    s.listen(0, () => {
      const p = s.address().port
      s.close(() => res(p))
    })
    s.on('error', rej)
  })
}

async function getJSON(url) {
  const r = await fetch(url)
  const txt = await r.text()
  const start = txt.search(/[\[{]/)
  return JSON.parse(start >= 0 ? txt.slice(start) : txt)
}

class CDP {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.id = 0
    this.pending = new Map()
    this.events = []
    this.handlers = new Map()
  }
  on(method, fn) {
    if (!this.handlers.has(method)) this.handlers.set(method, [])
    this.handlers.get(method).push(fn)
  }
  connect() {
    return new Promise((res, rej) => {
      this.ws = new WebSocket(this.wsUrl)
      this.ws.onopen = () => res()
      this.ws.onerror = (e) => rej(e)
      this.ws.onmessage = (m) => {
        const msg = JSON.parse(m.data)
        if (msg.id && this.pending.has(msg.id)) {
          const { res, rej } = this.pending.get(msg.id)
          this.pending.delete(msg.id)
          msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result)
        } else if (msg.method) {
          this.events.push(msg)
          const hs = this.handlers.get(msg.method) || []
          for (const h of hs) try { h(msg.params) } catch (_) {}
        }
      }
    })
  }
  send(method, params = {}) {
    const id = ++this.id
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          rej(new Error('timeout ' + method))
        }
      }, 30000)
    })
  }
  async waitEvent(method, timeoutMs = 15000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeoutMs) {
      const e = this.events.find((x) => x.method === method)
      if (e) return e
      await sleep(80)
    }
    return null
  }
}

async function inspect(url, outPng, width = 1280, height = 800, waitMs = 2500) {
  const userDir = mkdtempSync(join(tmpdir(), 'cdp_drive_'))
  const port = await freePort()
  const chrome = spawn(
    CHROME,
    [
      '--headless=new',
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${userDir}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-gpu',
      `--window-size=${width},${height}`,
      'about:blank',
    ],
    { stdio: 'ignore', detached: false },
  )

  let json = null
  for (let i = 0; i < 50; i++) {
    try {
      json = await getJSON(`http://127.0.0.1:${port}/json/version`)
      break
    } catch (_) {
      await sleep(100)
    }
  }
  if (!json) {
    chrome.kill()
    throw new Error('chrome did not expose CDP port')
  }
  const targets = await getJSON(`http://127.0.0.1:${port}/json`)
  const target = targets.find((t) => t.type === 'page')
  if (!target) {
    chrome.kill()
    throw new Error('no page target')
  }

  const cdp = new CDP(target.webSocketDebuggerUrl)
  await cdp.connect()
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await cdp.send('Log.enable')
  await cdp.send('Network.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: false,
  })

  const consoleErrors = []
  const exceptions = []
  const failedRequests = []
  const consoleAll = []

  cdp.on('Runtime.consoleAPICalled', (p) => {
    const text = (p.args || [])
      .map((a) => (a.value !== undefined ? String(a.value) : a.description || ''))
      .join(' ')
    consoleAll.push({ type: p.type, text: text.slice(0, 300) })
    if (p.type === 'error' || p.type === 'warning')
      consoleErrors.push({ type: p.type, text: text.slice(0, 300) })
  })
  cdp.on('Runtime.exceptionThrown', (p) => {
    const e = p.exceptionDetails
    exceptions.push({
      text: (e.text || '').slice(0, 200),
      url: e.url,
      line: e.lineNumber,
      col: e.columnNumber,
      stack: (e.exception?.description || '').split('\n').slice(0, 4).join('\n'),
    })
  })
  cdp.on('Network.loadingFailed', (p) => {
    failedRequests.push({ url: p.url, errorText: p.errorText, type: p.type })
  })
  cdp.on('Log.entryAdded', (p) => {
    const e = p.entry
    if (e.level === 'error') consoleErrors.push({ type: 'log', text: (e.text || '').slice(0, 300) })
  })

  await cdp.send('Page.navigate', { url })
  await cdp.waitEvent('Page.loadEventFired', 15000)
  await sleep(waitMs)

  // probe for canvas + body text length
  let canvasPresent = false
  let bodyLen = 0
  try {
    const ev = await cdp.send('Runtime.evaluate', {
      expression:
        '({c: !!document.querySelector("canvas"), b: (document.body && document.body.innerText || "").length})',
      returnByValue: true,
    })
    canvasPresent = !!ev.result?.value?.c
    bodyLen = ev.result?.value?.b || 0
  } catch (_) {}

  const shot = await cdp.send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(outPng, Buffer.from(shot.data, 'base64'))

  cdp.ws.close()
  chrome.kill()
  try { await sleep(200) } catch (_) {}

  return {
    ok: true,
    console_errors: consoleErrors.slice(0, 20),
    console_all: consoleAll.slice(0, 30),
    exceptions,
    failed_requests: failedRequests.slice(0, 20),
    canvas_present: canvasPresent,
    body_text_len: bodyLen,
  }
}

async function main() {
  const [cmd, ...rest] = process.argv.slice(2)
  if (cmd === 'screenshot') {
    const [url, out, w, h, waitMs] = rest
    if (!url || !out) {
      console.error('usage: cdp_drive.mjs screenshot <url> <out.png> [w h wait_ms]')
      process.exit(2)
    }
    const report = await inspect(url, out, +w || 1280, +h || 800, +waitMs || 2500)
    process.stdout.write(JSON.stringify(report))
    return
  }
  console.error('unknown command:', cmd)
  process.exit(2)
}

main().catch((e) => {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e) }))
  process.exit(1)
})
