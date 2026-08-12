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

// Accessibilite mesuree DANS le navigateur: contraste calcule, noms
// accessibles resolus, ordre des titres reel. Une regex sur la source ne peut
// voir aucun des quatre.
async function measureAccessibility(page) {
  return page.evaluate(() => {
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const st = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'
    }
    const describe = (el) => {
      const id = el.id ? `#${el.id}` : ''
      const cls = typeof el.className === 'string' && el.className ? `.${el.className.trim().split(/\s+/)[0]}` : ''
      return `${el.tagName.toLowerCase()}${id}${cls}`
    }
    const accessibleName = (el) => (
      el.getAttribute('aria-label')
      || el.getAttribute('title')
      || (el.getAttribute('aria-labelledby') ? document.getElementById(el.getAttribute('aria-labelledby'))?.textContent : '')
      || el.textContent
      || ''
    ).trim()

    const parse = (color) => {
      const m = String(color).match(/rgba?\(([^)]+)\)/)
      if (!m) return null
      const [r, g, b, a] = m[1].split(',').map((v) => parseFloat(v))
      return { r, g, b, a: a === undefined ? 1 : a }
    }
    const lum = ({ r, g, b }) => {
      const f = (v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    }
    const bgOf = (el) => {
      let node = el
      while (node && node !== document.documentElement) {
        const c = parse(getComputedStyle(node).backgroundColor)
        if (c && c.a > 0.1) return c
        node = node.parentElement
      }
      return { r: 255, g: 255, b: 255, a: 1 }
    }

    const imagesWithoutName = []
    for (const img of document.querySelectorAll('img')) {
      if (!visible(img)) continue
      const alt = img.getAttribute('alt')
      // alt="" est un choix VALIDE pour une image decorative: on ne le punit pas.
      if (alt === null) imagesWithoutName.push(describe(img))
    }

    const controlsWithoutName = []
    const unreachableByKeyboard = []
    for (const el of document.querySelectorAll('button, a[href], [role="button"], summary')) {
      if (!visible(el)) continue
      if (!accessibleName(el)) controlsWithoutName.push(describe(el))
      if (Number(el.getAttribute('tabindex')) < 0) unreachableByKeyboard.push(describe(el))
    }
    for (const el of document.querySelectorAll('[onclick]')) {
      if (!visible(el)) continue
      if (!el.matches('button, a[href], input, select, textarea, [role="button"], [tabindex]')) {
        unreachableByKeyboard.push(describe(el))
      }
    }

    const fieldsWithoutLabel = []
    for (const field of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
      if (!visible(field)) continue
      const labelled = field.getAttribute('aria-label')
        || field.getAttribute('aria-labelledby')
        || (field.id && document.querySelector(`label[for="${CSS.escape(field.id)}"]`))
        || field.closest('label')
      if (!labelled) fieldsWithoutLabel.push(describe(field))
    }

    const headingLevels = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
      .filter(visible)
      .map((h) => Number(h.tagName[1]))

    const lowContrastSamples = []
    for (const el of document.querySelectorAll('p, span, li, a, h1, h2, h3, h4, label, button, td')) {
      if (lowContrastSamples.length >= 8 || !visible(el)) continue
      const text = (el.textContent || '').trim()
      if (text.length < 4) continue
      if ([...el.children].some((child) => (child.textContent || '').trim().length > 0)) continue
      const st = getComputedStyle(el)
      const fg = parse(st.color)
      if (!fg) continue
      const bg = bgOf(el)
      const l1 = lum(fg); const l2 = lum(bg)
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
      // Le gros texte a droit a 3:1; on ne juge que le texte normal.
      const size = parseFloat(st.fontSize) || 16
      const bold = Number(st.fontWeight) >= 700
      const threshold = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5
      if (ratio < threshold) lowContrastSamples.push({ text: text.slice(0, 60), ratio })
    }

    return {
      documentLang: document.documentElement.getAttribute('lang') || '',
      imagesWithoutName, controlsWithoutName, fieldsWithoutLabel,
      headingLevels, lowContrastSamples, unreachableByKeyboard,
    }
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
export async function renderAndScoreAesthetics(inputFiles, options = {}) {
  let files = inputFiles
  // `files` est reassigne quand un build produit un dist/ a servir.
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
    // On ne se contente plus de dire « non applicable »: on CONSTRUIT, avec la
    // commande que le README promet. Le build est la verite terrain.
    const { buildGeneratedProject } = await import('./project_build.mjs')
    const build = buildGeneratedProject(files)
    if (!build.built) {
      return {
        applicable: false,
        needsBuild: true,
        buildFailed: true,
        buildErrors: build.errors ?? [],
        reason: `build impossible (${build.reason}): ${(build.errors ?? []).slice(0, 3).join(' | ') || 'voir journal'}`,
      }
    }
    files = build.files
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
    // Accessibilite: mesuree au rendu comme la composition, notee par un
    // module pur (donc testable sans navigateur).
    const { scoreAccessibility } = await import(
      pathToFileURL(path.resolve('src/services/codeAccessibilityGate.ts')).href
    )
    const accessibility = await measureAccessibility(page)
    const accessibilityVerdict = scoreAccessibility(accessibility)
    return {
      applicable: true, metrics: desktop, consoleErrors, composition, compositionVerdict,
      accessibility, accessibilityVerdict,
      verdict: scoreRenderedAesthetics({ desktop, consoleErrors }),
    }
  } catch (err) {
    return { applicable: false, reason: String(err?.message ?? err).slice(0, 200) }
  } finally {
    await browser?.close().catch(() => {})
    server?.close()
  }
}
