// cdp_drive.mjs — CDP helper: open a URL in headless Chrome, screenshot it,
// and capture console errors / JS exceptions / failed network requests during
// the load. Returns a JSON report on stdout (in addition to writing the PNG).
//
// Usage:
//   node cdp_drive.mjs screenshot <url> <out_png> [w h wait_ms]
//   node cdp_drive.mjs audit <url> <out_dir> [wait_ms]
// stdout JSON:
//   {ok, console_errors:[], exceptions:[], failed_requests:[], canvas_present, body_text_len}

import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
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

function viewportName(width, height) {
  return `${width}x${height}`
}

async function inspect(url, outPng, width = 1280, height = 800, waitMs = 2500, mobile = false) {
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
    mobile,
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

  // Probe rendered DOM and computed styles. The TypeScript scorer treats this
  // as render evidence; a Python pass may later enrich contrast with pixel
  // samples from the screenshot.
  let renderMetrics = {}
  try {
    const ev = await cdp.send('Runtime.evaluate', {
      expression:
        `(() => {
          const clamp = (n, min, max) => Math.max(min, Math.min(max, n))
          const uniq = (arr) => [...new Set(arr.filter(Boolean))]
          const rgb = (value) => {
            const m = String(value || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/i)
            if (!m) return null
            return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] }
          }
          const lum = (c) => {
            const conv = (v) => {
              const s = v / 255
              return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
            }
            return 0.2126 * conv(c.r) + 0.7152 * conv(c.g) + 0.0722 * conv(c.b)
          }
          const ratio = (fg, bg) => {
            const a = lum(fg)
            const b = lum(bg)
            return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
          }
          const visible = (el) => {
            const rect = el.getBoundingClientRect()
            const cs = getComputedStyle(el)
            return rect.width > 1 && rect.height > 1 && cs.visibility !== 'hidden' && cs.display !== 'none' && Number(cs.opacity || 1) > 0.02
          }
          const bgFor = (el) => {
            let cur = el
            while (cur && cur !== document) {
              const c = rgb(getComputedStyle(cur).backgroundColor)
              if (c && c.a > 0.15) return c
              cur = cur.parentElement
            }
            return rgb(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }
          }
          const all = Array.from(document.body ? document.body.querySelectorAll('*') : []).filter(visible)
          const textEls = all.filter((el) => (el.innerText || '').trim().length > 0)
          const textRects = textEls
            .map((el) => el.getBoundingClientRect())
            .filter((rect) => rect.width > 2 && rect.height > 2)
            .sort((a, b) => a.top - b.top)
          const gaps = []
          for (let i = 1; i < textRects.length; i++) {
            const gap = textRects[i].top - (textRects[i - 1].top + textRects[i - 1].height)
            if (gap >= 0 && gap < 300) gaps.push(gap)
          }
          gaps.sort((a, b) => a - b)
          const rootStyle = getComputedStyle(document.documentElement)
          let cssVarCount = 0
          for (let i = 0; i < rootStyle.length; i++) {
            if (rootStyle[i] && rootStyle[i].startsWith('--')) cssVarCount += 1
          }
          const contrastSamples = textEls.slice(0, 36).map((el, index) => {
            const cs = getComputedStyle(el)
            const fg = rgb(cs.color)
            const bg = bgFor(el)
            const rect = el.getBoundingClientRect()
            return fg && bg ? {
              ratio: Math.round(ratio(fg, bg) * 100) / 100,
              source: 'computed-style',
              viewport: '${viewportName(width, height)}',
              label: (el.tagName.toLowerCase() + '#' + index),
              rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
            } : null
          }).filter(Boolean)
          return {
            canvasPresent: !!document.querySelector('canvas'),
            bodyTextLength: (document.body && document.body.innerText || '').length,
            textNodeCount: textEls.length,
            headingCount: document.querySelectorAll('h1,h2,h3,[role="heading"]').length,
            mediaCount: document.querySelectorAll('img,svg,video,picture,canvas').length,
            interactiveCount: document.querySelectorAll('a[href],button,input,select,textarea,[role="button"],[tabindex]').length,
            cssVarCount,
            fontFamilies: uniq(textEls.slice(0, 80).map((el) => getComputedStyle(el).fontFamily)).slice(0, 10),
            verticalGapMedian: gaps.length ? Math.round(gaps[Math.floor(gaps.length / 2)]) : null,
            contrastSamples,
          }
        })()`,
      returnByValue: true,
    })
    renderMetrics = ev.result?.value || {}
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
    canvas_present: !!renderMetrics.canvasPresent,
    body_text_len: renderMetrics.bodyTextLength || 0,
    render_metrics: renderMetrics,
  }
}

async function audit(url, outDir, waitMs = 2500) {
  mkdirSync(outDir, { recursive: true })
  const viewports = [
    { width: 390, height: 844, mobile: true },
    { width: 834, height: 1112, mobile: true },
    { width: 1440, height: 900, mobile: false },
  ]
  const out = []
  for (const viewport of viewports) {
    const name = viewportName(viewport.width, viewport.height)
    const screenshotPath = join(outDir, `${name}.png`)
    const report = await inspect(url, screenshotPath, viewport.width, viewport.height, waitMs, viewport.mobile)
    const metrics = report.render_metrics || {}
    out.push({
      viewport: name,
      width: viewport.width,
      height: viewport.height,
      screenshotPath,
      bodyTextLength: metrics.bodyTextLength || report.body_text_len || 0,
      consoleErrors: (report.console_errors || []).map((item) => item.text || String(item)),
      exceptions: (report.exceptions || []).map((item) => item.text || String(item)),
      failedRequests: (report.failed_requests || []).map((item) => item.url ? `${item.url} ${item.errorText || ''}` : String(item)),
      canvasPresent: !!metrics.canvasPresent,
      textNodeCount: metrics.textNodeCount || 0,
      headingCount: metrics.headingCount || 0,
      mediaCount: metrics.mediaCount || 0,
      interactiveCount: metrics.interactiveCount || 0,
      cssVarCount: metrics.cssVarCount || 0,
      fontFamilies: metrics.fontFamilies || [],
      verticalGapMedian: metrics.verticalGapMedian ?? null,
      contrastSamples: metrics.contrastSamples || [],
    })
  }
  return {
    schemaVersion: 'aurora.code.visual-render-audit/1',
    url,
    createdAt: Date.now(),
    viewports: out,
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
  if (cmd === 'audit') {
    const [url, outDir, waitMs] = rest
    if (!url || !outDir) {
      console.error('usage: cdp_drive.mjs audit <url> <out_dir> [wait_ms]')
      process.exit(2)
    }
    const report = await audit(url, outDir, +waitMs || 2500)
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
