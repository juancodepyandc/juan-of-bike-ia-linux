// Acceptation COMPORTEMENTALE WS7 — on execute le livrable au lieu de le relire.
//
// Reproche explicite de l audit de juillet: « les tests d acceptation sont une
// checklist REGEX statique fixe (aucune execution). Une calculatrice au calcul
// FAUX passe 100 %. » C etait exact: `evaluateAcceptanceCriteria` se contente de
// verifier la presence de code et l absence de placeholder, plus quelques motifs
// pour les calculatrices. Aucune regex ne peut prouver que 2 + 3 fait 5.
//
// Ce module rend la page dans un vrai navigateur (Chromium headless), clique sur
// ses vrais boutons et LIT le resultat affiche. Un livrable dont le calcul est
// faux echoue, quelle que soit la propreté de son code source.
//
// Utilisable de deux facons:
//   - comme bibliotheque: `runBehaviourAcceptance(files, prompt)`
//   - en ligne de commande sur un dossier: node acceptance_behaviour.mjs <dir> [--json <path>]

import { createServer } from 'node:http'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.ts': 'text/javascript; charset=utf-8',
  '.tsx': 'text/javascript; charset=utf-8',
  '.jsx': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
}

/**
 * Sert un ensemble de fichiers en memoire. Pas de serveur de dev, donc pas de
 * dependance a Tauri: ce chemin fonctionne en CLI comme dans le tunnel.
 */
function serveFiles(files) {
  const byPath = new Map()
  for (const file of files) {
    const clean = String(file.name || '').replace(/\\/g, '/').replace(/^\.?\//, '')
    byPath.set(clean.toLowerCase(), file.content ?? '')
  }
  const server = createServer((req, res) => {
    let rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\//, '')
    if (rel === '' || rel.endsWith('/')) rel += 'index.html'
    const hit = byPath.get(rel.toLowerCase())
    if (hit === undefined) {
      res.writeHead(404, { 'content-type': 'text/plain' })
      res.end('not found')
      return
    }
    res.writeHead(200, { 'content-type': MIME[path.extname(rel).toLowerCase()] || 'text/plain; charset=utf-8' })
    res.end(hit)
  })
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }))
  })
}

const CALCULATOR_RE = /\b(calculatrice|calculator|calculette)\b/i

/**
 * Pilote la calculatrice livree: clique ses vrais boutons, lit son vrai
 * affichage. On cherche les boutons par leur texte visible, ce qui marche quel
 * que soit le nommage interne choisi par le modele.
 */
async function driveCalculator(page, a, op, b) {
  return page.evaluate(async ({ a, op, b }) => {
    const norm = (s) => (s || '').trim().toLowerCase()
    const clickables = Array.from(document.querySelectorAll('button, [role="button"], input[type="button"], td, div, span'))
      .filter((el) => el.offsetParent !== null || el.tagName === 'BUTTON')

    const findByText = (targets) => clickables.find((el) => {
      const t = norm(el.innerText ?? el.value ?? el.textContent)
      return targets.some((x) => t === x)
    })

    const OP_ALIASES = {
      '+': ['+', 'add', 'plus'],
      '-': ['-', '−', 'sub', 'minus'],
      '*': ['*', '×', 'x', 'mul', 'times'],
      '/': ['/', '÷', 'div'],
    }

    const press = (targets) => {
      const el = findByText(targets)
      if (!el) return false
      el.click()
      return true
    }

    // Reinitialise si un bouton clear existe.
    press(['c', 'ac', 'clear'])

    const seq = [...String(a).split(''), null, ...String(b).split('')]
    for (const ch of seq) {
      if (ch === null) {
        if (!press(OP_ALIASES[op])) return { ok: false, reason: `operateur ${op} introuvable` }
        continue
      }
      if (!press([ch])) return { ok: false, reason: `touche ${ch} introuvable` }
    }
    if (!press(['=', 'egal', 'equals'])) return { ok: false, reason: 'touche = introuvable' }

    await new Promise((r) => setTimeout(r, 120))

    // Lit l affichage: l element le plus plausible contenant un nombre.
    const candidates = Array.from(document.querySelectorAll(
      '#display, .display, #result, .result, #screen, .screen, output, input[readonly], input[type="text"], .calculator-display',
    ))
    for (const el of candidates) {
      const raw = (el.value ?? el.innerText ?? el.textContent ?? '').trim()
      if (/-?\d/.test(raw)) return { ok: true, shown: raw }
    }
    const anyNumber = Array.from(document.querySelectorAll('div, span, p, h1, h2'))
      .map((el) => (el.innerText || '').trim())
      .filter((t) => /^-?\d+(\.\d+)?$/.test(t))
    if (anyNumber.length > 0) return { ok: true, shown: anyNumber[anyNumber.length - 1] }
    return { ok: false, reason: 'aucun affichage numerique trouve' }
  }, { a, op, b })
}

const CALC_CASES = [
  { a: 2, op: '+', b: 3, expect: 5 },
  { a: 9, op: '-', b: 4, expect: 5 },
  { a: 6, op: '*', b: 7, expect: 42 },
  { a: 8, op: '/', b: 2, expect: 4 },
]

/**
 * Execute le livrable et retourne des criteres COMPORTEMENTAUX.
 * Retourne `applicable:false` quand le livrable n est pas une page pilotable.
 */
export async function runBehaviourAcceptance(inputFiles, prompt, options = {}) {
  let files = inputFiles
  const hasHtml = files.some((f) => /\.html?$/i.test(f.name || ''))
  if (!hasHtml) return { applicable: false, reason: 'aucun HTML a executer', criteria: [] }

  // Un projet a bundler ne peut PAS etre juge en le servant tel quel: son
  // index.html pointe un module source (`/src/main.tsx`) que seul un build
  // resout. Servi brut, le navigateur refuse le module ("MIME text/plain",
  // strict MIME checking) et la page reste vide.
  //
  // Mesure reelle (run 991, site Brulerie Nomade, 43 fichiers): l acceptation a
  // conclu « runtime-no-error FAIL » et « renders-content: 0 caracteres », le
  // livrable a ete declare casse, et la boucle a brule NEUF passes a corriger
  // une application qui n avait simplement jamais ete construite.
  //
  // Le juge de RENDU tient deja cette garde (`needsBundler`); l acceptation
  // comportementale ne l avait pas. Un juge qui ne peut pas mesurer doit dire
  // qu il n a pas mesure — jamais condamner.
  const entry = files.find((f) => /(^|\/)index\.html?$/i.test(f.name || ''))
  const entryHtml = entry?.content ?? ''
  const needsBundler = /<script[^>]+src=["'][^"']*\/?src\/[^"']+\.(ts|tsx|jsx|vue|svelte)["']/i.test(entryHtml)
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
        criteria: [],
      }
    }
    files = build.files
  }

  const { chromium } = await import('playwright')
  const { server, port } = await serveFiles(files)
  const browser = await chromium.launch({ headless: true })
  const criteria = []
  const consoleErrors = []
  try {
    // Run 1091: cette porte ouvrait `/index.html` et concluait « page vide ».
    // Mesure sur les fichiers reels, memes fichiers, memes requetes (3 x 200),
    // zero erreur:
    //     GET /index.html -> 0 caractere,   15 elements
    //     GET /           -> 1492 caracteres, 130 elements
    // La SPA livree utilise react-router: aucune route ne correspond a
    // `/index.html`, donc `<Routes>` ne rend rien. On jugeait une URL que
    // l application ne sert pas, puis on l accusait d etre une coquille vide —
    // et la boucle de correction a brule neuf passes a chercher un bug
    // inexistant. Une application web s ouvre a sa RACINE, comme le fait
    // deja l audit de rendu (qui, lui, notait 92/100 au meme instant).
    const page = await browser.newPage()
    page.on('pageerror', (err) => consoleErrors.push(String(err).slice(0, 200)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200))
    })
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle', timeout: 20_000 })

    // Critere universel: la page ne doit pas exploser au chargement.
    criteria.push({
      id: 'runtime-no-error',
      label: 'La page se charge sans erreur JavaScript',
      category: 'robustness',
      ok: consoleErrors.length === 0,
      detail: consoleErrors.length === 0 ? 'Aucune erreur runtime.' : `Erreurs: ${consoleErrors.slice(0, 3).join(' | ')}`,
    })

    // Critere universel: la page n est pas une coquille vide. Le seuil ne peut
    // pas etre un simple nombre de caracteres — une calculatrice correcte
    // n affiche que des chiffres et des operateurs. On accepte donc du texte
    // OU de vrais elements pilotables OU une surface graphique.
    const shell = await page.evaluate(() => ({
      textLength: (document.body?.innerText || '').trim().length,
      interactive: document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]').length,
      surfaces: document.querySelectorAll('canvas, svg, img, video').length,
    }))
    criteria.push({
      id: 'renders-content',
      label: 'La page n est pas une coquille vide',
      category: 'functional',
      ok: shell.textLength > 0 || shell.interactive > 0 || shell.surfaces > 0,
      detail: `${shell.textLength} caracteres, ${shell.interactive} controles, ${shell.surfaces} surfaces.`,
    })

    if (CALCULATOR_RE.test(prompt || '') || options.forceCalculator) {
      for (const c of CALC_CASES) {
        const res = await driveCalculator(page, c.a, c.op, c.b)
        const shownNumber = res.ok ? Number(String(res.shown).replace(/[^\d.-]/g, '')) : NaN
        const ok = res.ok && Math.abs(shownNumber - c.expect) < 1e-9
        criteria.push({
          id: `calc-${c.a}${c.op}${c.b}`,
          label: `${c.a} ${c.op} ${c.b} = ${c.expect}`,
          category: 'functional',
          ok,
          detail: res.ok ? `affiche "${res.shown}" (attendu ${c.expect})` : res.reason,
        })
        // Recharge entre deux operations pour repartir d un etat propre.
        await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle', timeout: 20_000 })
      }
    }
  } finally {
    await browser.close().catch(() => {})
    server.close()
  }

  return { applicable: true, criteria }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
if (import.meta.url === `file://${process.argv[1]}`) {
  const dir = process.argv[2]
  if (!dir) {
    process.stderr.write('usage: acceptance_behaviour.mjs <dir> [--prompt "..."] [--json <path>]\n')
    process.exit(2)
  }
  const walk = (d, base = d, acc = []) => {
    for (const entry of readdirSync(d)) {
      const full = path.join(d, entry)
      if (statSync(full).isDirectory()) walk(full, base, acc)
      else acc.push({ name: path.relative(base, full).replace(/\\/g, '/'), language: path.extname(entry).slice(1), content: readFileSync(full, 'utf8') })
    }
    return acc
  }
  const pi = process.argv.indexOf('--prompt')
  const prompt = pi !== -1 ? process.argv[pi + 1] : 'calculatrice'
  const result = await runBehaviourAcceptance(walk(path.resolve(dir)), prompt)
  const passed = result.criteria.filter((c) => c.ok).length
  const report = {
    schemaVersion: 'aurora.code.behaviour-acceptance/1',
    ok: result.applicable && result.criteria.every((c) => c.ok),
    applicable: result.applicable,
    score: result.criteria.length ? Math.round((passed / result.criteria.length) * 100) : 0,
    criteria: result.criteria,
  }
  const ji = process.argv.indexOf('--json')
  if (ji !== -1 && process.argv[ji + 1]) {
    const { writeFileSync } = await import('node:fs')
    writeFileSync(process.argv[ji + 1], JSON.stringify(report, null, 2), 'utf8')
  }
  process.stdout.write(JSON.stringify(report, null, 2) + '\n')
  process.exit(report.ok ? 0 : 1)
}
