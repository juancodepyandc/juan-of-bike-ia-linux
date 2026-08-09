// Capture esthetique — on REGARDE le rendu, on ne lit pas le code.
//
// La porte WS9 note le HTML/CSS livre. C est utile, mais ca ne dit pas si la
// page a l air premium ou template. Ce script rend la page dans un vrai
// Chromium, capture desktop et mobile, et releve des metriques que l oeil d un
// directeur artistique verifierait en premier: familles typographiques reelles
// (celles que le navigateur a effectivement resolues), nombre de couleurs
// distinctes, echelle d espacement, densite de sections, presence d animation.
//
// Usage:
//   node scripts/code_harness/aesthetic_capture.mjs <dir> --out <dir> [--json <path>]

import { createServer } from 'node:http'
import { pathToFileURL } from 'node:url'
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.woff': 'font/woff', '.woff2': 'font/woff2',
}

function walk(dir, base = dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, base, acc)
    else acc.push({ rel: path.relative(base, full).replace(/\\/g, '/'), full })
  }
  return acc
}

function serve(dir) {
  const files = new Map(walk(dir).map((f) => [f.rel.toLowerCase(), f.full]))
  const server = createServer((req, res) => {
    let rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\//, '')
    if (rel === '' || rel.endsWith('/')) rel += 'index.html'
    const hit = files.get(rel.toLowerCase())
    if (!hit) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[path.extname(rel).toLowerCase()] || 'application/octet-stream' })
    res.end(readFileSync(hit))
  })
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r({ server, port: server.address().port })))
}

/** Metriques relevees sur le rendu REEL, pas sur la source. */
async function measure(page) {
  return page.evaluate(() => {
    const els = Array.from(document.querySelectorAll('body *')).slice(0, 4000)
    const fonts = new Set()
    const colors = new Set()
    const bgs = new Set()
    const sizes = new Set()
    const radii = new Set()
    const shadows = new Set()
    let transitions = 0
    for (const el of els) {
      const cs = getComputedStyle(el)
      const txt = (el.textContent || '').trim()
      if (txt) {
        fonts.add(cs.fontFamily.split(',')[0].replace(/["']/g, '').trim())
        colors.add(cs.color)
        sizes.add(Math.round(parseFloat(cs.fontSize)))
      }
      if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bgs.add(cs.backgroundColor)
      if (cs.borderRadius && cs.borderRadius !== '0px') radii.add(cs.borderRadius)
      if (cs.boxShadow && cs.boxShadow !== 'none') shadows.add(cs.boxShadow)
      if ((cs.transition && cs.transition !== 'all 0s ease 0s') || (cs.animationName && cs.animationName !== 'none')) transitions += 1
    }
    const sections = document.querySelectorAll('section, main > div, header, footer, article').length
    return {
      fontFamilies: [...fonts].slice(0, 12),
      distinctTextColors: colors.size,
      distinctBackgrounds: bgs.size,
      fontSizeScale: [...sizes].sort((a, b) => a - b),
      distinctRadii: radii.size,
      distinctShadows: shadows.size,
      animatedElements: transitions,
      sections,
      images: document.querySelectorAll('img, picture, svg').length,
      canvases: document.querySelectorAll('canvas').length,
      interactive: document.querySelectorAll('button, a[href], input, select, textarea').length,
      documentHeight: document.body.scrollHeight,
      hasWebGL: !!document.querySelector('canvas') && !!window.THREE,
    }
  })
}

const dir = process.argv[2]
const outIdx = process.argv.indexOf('--out')
const outDir = outIdx !== -1 ? process.argv[outIdx + 1] : path.join(dir, '_shots')
if (!dir) { process.stderr.write('usage: aesthetic_capture.mjs <dir> --out <dir>\n'); process.exit(2) }
mkdirSync(outDir, { recursive: true })

const { chromium } = await import('playwright')
const { server, port } = await serve(path.resolve(dir))
const browser = await chromium.launch({ headless: true })
const report = { schemaVersion: 'aurora.code.aesthetic-capture/1', source: dir, viewports: {}, consoleErrors: [] }

try {
  for (const [name, vp] of Object.entries({ desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } })) {
    const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 1 })
    page.on('pageerror', (e) => report.consoleErrors.push(`${name}: ${String(e).slice(0, 160)}`))
    page.on('console', (m) => { if (m.type() === 'error') report.consoleErrors.push(`${name}: ${m.text().slice(0, 160)}`) })
    await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: 'networkidle', timeout: 30_000 })
    await page.waitForTimeout(1200) // laisse les animations d entree se jouer
    const shot = path.join(outDir, `${name}.png`)
    await page.screenshot({ path: shot, fullPage: name === 'desktop' })
    report.viewports[name] = { screenshot: shot, ...(await measure(page)) }
    await page.close()
  }
} finally {
  await browser.close().catch(() => {})
  server.close()
}

// Note le RENDU avec la meme regle que le pipeline (module TS partage), pour
// que la capture manuelle et la porte automatique ne puissent pas diverger.
try {
  const { installHeadlessCodeEnv } = await import('./harness_env.mjs')
  installHeadlessCodeEnv()
  const { scoreRenderedAesthetics } = await import(
    pathToFileURL(path.resolve('src/services/codeRenderedAestheticScore.ts')).href
  )
  report.verdict = scoreRenderedAesthetics({
    desktop: report.viewports.desktop,
    mobile: report.viewports.mobile ?? null,
    consoleErrors: report.consoleErrors,
  })
} catch (err) {
  report.verdictError = String(err?.message ?? err).slice(0, 200)
}

const ji = process.argv.indexOf('--json')
if (ji !== -1 && process.argv[ji + 1]) writeFileSync(process.argv[ji + 1], JSON.stringify(report, null, 2), 'utf8')
process.stdout.write(JSON.stringify(report, null, 2) + '\n')
