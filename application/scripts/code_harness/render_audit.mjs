// Audit de rendu reutilisable — sert les fichiers livres, les ouvre dans
// Chromium, mesure le rendu et le note avec la regle TS partagee.
//
// Existe pour que la boucle esthetique ne reste pas prisonniere de l UI Tauri.
// L audit rendu historique passe par `startDevServer` -> `spawnWorkspaceCommand`,
// couple a Tauri: le CLI et le tunnel n y avaient donc pas acces. Ici, un
// serveur en memoire suffit — aucun serveur de dev, aucune dependance Tauri.

import { createServer } from 'node:http'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp',
}

function serveFiles(files) {
  const byPath = new Map(
    files.map((f) => [String(f.name || '').replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase(), f.content ?? '']),
  )
  const server = createServer((req, res) => {
    let rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\//, '')
    if (rel === '' || rel.endsWith('/')) rel += 'index.html'
    const hit = byPath.get(rel.toLowerCase())
    if (hit === undefined) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[path.extname(rel).toLowerCase()] || 'text/plain; charset=utf-8' })
    res.end(hit)
  })
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r({ server, port: server.address().port })))
}

async function measure(page) {
  return page.evaluate(() => {
    const els = Array.from(document.querySelectorAll('body *')).slice(0, 4000)
    const fonts = new Set(); const colors = new Set(); const bgs = new Set()
    const sizes = new Set(); const radii = new Set(); const shadows = new Set()
    let animated = 0
    for (const el of els) {
      const cs = getComputedStyle(el)
      if ((el.textContent || '').trim()) {
        fonts.add(cs.fontFamily.split(',')[0].replace(/["']/g, '').trim())
        colors.add(cs.color); sizes.add(Math.round(parseFloat(cs.fontSize)))
      }
      if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bgs.add(cs.backgroundColor)
      if (cs.borderRadius && cs.borderRadius !== '0px') radii.add(cs.borderRadius)
      if (cs.boxShadow && cs.boxShadow !== 'none') shadows.add(cs.boxShadow)
      if ((cs.transition && cs.transition !== 'all 0s ease 0s') || (cs.animationName && cs.animationName !== 'none')) animated += 1
    }
    return {
      fontFamilies: [...fonts].slice(0, 12),
      distinctTextColors: colors.size, distinctBackgrounds: bgs.size,
      fontSizeScale: [...sizes].sort((a, b) => a - b),
      distinctRadii: radii.size, distinctShadows: shadows.size,
      animatedElements: animated,
      sections: document.querySelectorAll('section, main > div, header, footer, article').length,
      images: document.querySelectorAll('img, picture, svg').length,
      canvases: document.querySelectorAll('canvas').length,
      interactive: document.querySelectorAll('button, a[href], input, select, textarea').length,
      documentHeight: document.body.scrollHeight,
    }
  })
}

/**
 * Rend les fichiers et retourne le verdict esthetique.
 * `applicable:false` quand il n y a pas de page a ouvrir.
 * Ne leve jamais: une panne de navigateur ne doit pas empecher une livraison.
 */
export async function renderAndScoreAesthetics(files, options = {}) {
  if (!files.some((f) => /\.html?$/i.test(f.name || ''))) {
    return { applicable: false, reason: 'aucun HTML a rendre' }
  }
  let browser = null; let server = null
  try {
    const { chromium } = await import('playwright')
    const served = await serveFiles(files); server = served.server
    browser = await chromium.launch({ headless: true })
    const consoleErrors = []
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
    page.on('pageerror', (e) => consoleErrors.push(String(e).slice(0, 160)))
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 160)) })
    await page.goto(`http://127.0.0.1:${served.port}/index.html`, { waitUntil: 'networkidle', timeout: 30_000 })
    await page.waitForTimeout(1000)
    const desktop = await measure(page)
    if (options.screenshot) await page.screenshot({ path: options.screenshot, fullPage: true })

    const { scoreRenderedAesthetics } = await import(
      pathToFileURL(path.resolve('src/services/codeRenderedAestheticScore.ts')).href
    )
    return { applicable: true, metrics: desktop, consoleErrors, verdict: scoreRenderedAesthetics({ desktop, consoleErrors }) }
  } catch (err) {
    return { applicable: false, reason: String(err?.message ?? err).slice(0, 200) }
  } finally {
    await browser?.close().catch(() => {})
    server?.close()
  }
}
