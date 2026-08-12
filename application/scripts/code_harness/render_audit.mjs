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
  '.ts': 'text/javascript; charset=utf-8', '.tsx': 'text/javascript; charset=utf-8',
  '.jsx': 'text/javascript; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp',
}

function serveFiles(files) {
  const byPath = new Map(
    files.map((f) => [String(f.name || '').replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase(), f.content ?? '']),
  )
  const server = createServer((req, res) => {
    let rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\//, '')
    if (rel === '' || rel.endsWith('/')) rel += 'index.html'
    let hit = byPath.get(rel.toLowerCase())
    if (hit === undefined && !path.extname(rel)) hit = byPath.get('index.html')
    if (hit === undefined) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[path.extname(rel).toLowerCase()] || 'text/plain; charset=utf-8' })
    res.end(hit)
  })
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r({ server, port: server.address().port })))
}

/** Mesures de COMPOSITION: chevauchements reels et remplissage des sections. */
async function measureComposition(page) {
  return page.evaluate(() => {
    const vis = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && parseFloat(cs.opacity || '1') > 0.05
    }
    const label = (el) => {
      const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30)
      return t || el.tagName.toLowerCase()
    }
    const leaves = Array.from(document.querySelectorAll('body *')).filter((el) => {
      if (!vis(el)) return false
      if (el.children.length > 0) return false
      const t = (el.innerText || '').trim()
      return t.length > 0 || /^(BUTTON|A|INPUT|IMG|SVG)$/.test(el.tagName)
    }).slice(0, 400)

    const overlaps = []
    for (let i = 0; i < leaves.length; i++) {
      for (let j = i + 1; j < leaves.length; j++) {
        const a = leaves[i], b = leaves[j]
        if (a.contains(b) || b.contains(a)) continue
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect()
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top)
        if (w <= 2 || h <= 2) continue
        const area = w * h
        const minArea = Math.min(ra.width * ra.height, rb.width * rb.height)
        if (area < minArea * 0.25) continue
        overlaps.push({ a: label(a), b: label(b), area })
      }
    }

    const sections = Array.from(document.querySelectorAll('section, header, footer, main > div')).filter(vis)
      .slice(0, 40).map((sec) => {
        const r = sec.getBoundingClientRect()
        let covered = 0
        for (const child of Array.from(sec.querySelectorAll('*'))) {
          if (!vis(child) || child.children.length > 0) continue
          const cr = child.getBoundingClientRect()
          covered += cr.width * cr.height
        }
        const area = Math.max(1, r.width * r.height)
        return { label: label(sec).slice(0, 24), height: r.height, fill: Math.min(1, covered / area) }
      })

    // Emoji EN POSITION D ICONE, mesures sur le rendu: la source peut les
    // tenir dans un tableau de donnees (`{{ feature.icon }}`), invisible a une
    // analyse statique du markup. A l ecran, ils sautent aux yeux.
    const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}]/gu
    const emojiIcons = []
    for (const el of leaves) {
      const t = (el.innerText || '').trim()
      if (!t) continue
      const stripped = t.replace(EMOJI, '').trim()
      if (stripped.length <= 2 && EMOJI.test(t)) {
        for (const e of t.match(EMOJI) || []) if (!emojiIcons.includes(e)) emojiIcons.push(e)
      }
    }
    return { overlaps: overlaps.slice(0, 20), sections, emojiIcons, viewportWidth: window.innerWidth }
  })
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
  // Un projet a bundler (Vue/React/Svelte) ne peut PAS etre juge en le servant
  // tel quel: son index.html pointe un module source (`/src/main.ts`) que seul
  // un build resout. Le servir statiquement donne une page blanche, donc un
  // score proche de 0 qui ne dit rien du design et declenche une repasse
  // esthetique inutile. Mesure: un run SaaS Vue a ete note 10/100 ainsi.
  const entry = files.find((f) => /(^|\/)index\.html?$/i.test(f.name || ''))
  const entryHtml = entry?.content ?? ''
  const needsBundler = /<script[^>]+src=["'][^"']*\/src\/[^"']+\.(ts|tsx|jsx|vue|svelte)["']/i.test(entryHtml)
    || files.some((f) => /\.(vue|svelte)$/i.test(f.name || ''))
  if (needsBundler) {
    return {
      applicable: false,
      reason: 'projet a bundler (Vue/React/Svelte): un build est requis avant tout jugement de rendu',
      needsBuild: true,
    }
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
    await page.goto(`http://127.0.0.1:${served.port}/`, { waitUntil: 'networkidle', timeout: 30_000 })
    await page.waitForTimeout(1000)
    const desktop = await measure(page)
    if (options.screenshot) await page.screenshot({ path: options.screenshot, fullPage: true })

    // Composition mesuree au rendu: chevauchements, sections vides, emoji.
    // Sans cela le canal tunnel noterait le style sans jamais voir qu un texte
    // en recouvre un autre.
    const composition = await measureComposition(page)
    const { scoreRenderedAesthetics } = await import(
      pathToFileURL(path.resolve('src/services/codeRenderedAestheticScore.ts')).href
    )
    const { checkComposition } = await import(
      pathToFileURL(path.resolve('src/services/codeCompositionGate.ts')).href
    )
    const compositionVerdict = checkComposition({
      overlaps: composition.overlaps ?? [],
      sections: composition.sections ?? [],
      emojiIcons: composition.emojiIcons ?? [],
      viewportWidth: composition.viewportWidth ?? 1440,
    })
    return {
      applicable: true, metrics: desktop, consoleErrors, composition, compositionVerdict,
      verdict: scoreRenderedAesthetics({ desktop, consoleErrors }),
    }
  } catch (err) {
    return { applicable: false, reason: String(err?.message ?? err).slice(0, 200) }
  } finally {
    await browser?.close().catch(() => {})
    server?.close()
  }
}
