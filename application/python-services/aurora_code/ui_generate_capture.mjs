// Pilote une VRAIE generation de code dans l'UI (aurora_v4) et capture le rendu.
// Usage: node ui_generate_capture.mjs <baseUrl> <outDir> "<prompt>"
import { chromium } from 'playwright'
import { mkdirSync, writeFileSync } from 'node:fs'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const baseUrl = process.argv[2] || 'http://localhost:1420'
const outDir = process.argv[3] || '/tmp/ui_gen'
const prompt = process.argv[4] || 'Landing page moderne pour un cafe de specialite nomme Brume: hero plein ecran avec titre accrocheur et bouton CTA, section menu avec 3 cafes et prix, section notre histoire, avis clients, formulaire de reservation, footer. Design epure elegant, palette chaude, responsive, animations douces.'
const GEN_TIMEOUT_MS = 600000
mkdirSync(outDir, { recursive: true })
const log = (m) => console.log(`[${new Date().toISOString().slice(11, 19)}] ${m}`)

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const SKIN = process.argv[5] || 'aurora_v3'
const context = await browser.newContext({ viewport: { width: 1680, height: 1000 }, deviceScaleFactor: 1 })
await context.addInitScript((s) => {
  try { localStorage.setItem('aurora-ui-skin', s); localStorage.setItem('aurora-ui-skin-choice', s) } catch (e) {}
}, SKIN)
const page = await context.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e.message || e).slice(0, 200)))

await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 })
await sleep(3000)

// Nav vers Code, PUIS verification qu on est bien sur la vue Code (textarea a
// placeholder Dashboard/livrable). On tente plusieurs strategies.
async function onCodeView() {
  return await page.locator('textarea[placeholder*="Dashboard"], textarea[placeholder*="livrable"], textarea[placeholder*="Décris"]').first().count() > 0
    || (await page.locator('text=/SIMULATEUR|LIVRAISON|ATELIER/i').count()) > 0
}
for (let attempt = 0; attempt < 4 && !(await onCodeView()); attempt++) {
  try { await page.locator('[role="navigation"] >> text=/^Code$/i, [title="Code"], [aria-label="Code"]').first().click({ timeout: 3000 }) } catch (e) {}
  if (await onCodeView()) break
  try { await page.locator('text=/^Code$/').first().click({ timeout: 3000 }) } catch (e) {}
  if (await onCodeView()) break
  await page.mouse.click(5, 5) // blur tout input
  await page.keyboard.press('3') // raccourci module code
  await sleep(1800)
}
if (!(await onCodeView())) { log('ECHEC nav vers Code'); await page.screenshot({ path: `${outDir}/00_navfail.png` }); await browser.close(); process.exit(1) }
log('sur la vue Code OK')
await sleep(1500)

// Remplir la textarea Code (ciblee par placeholder, pas la 1ere venue)
const ta = page.locator('textarea[placeholder*="Dashboard"], textarea[placeholder*="livrable"], textarea[placeholder*="Décris"]').first()
await ta.waitFor({ timeout: 10000 })
await ta.click()
await ta.fill(prompt)
await ta.dispatchEvent('input')
await sleep(800)
log('prompt saisi, clic Generer...')
await page.screenshot({ path: `${outDir}/00_before.png` })

// Cliquer Generer / Continuer
let clicked = false
for (const label of ['Generer', 'Générer', 'Continuer']) {
  try { const b = page.locator(`button:has-text("${label}")`).first(); if (await b.count() && await b.isEnabled()) { await b.click({ timeout: 4000 }); clicked = true; log(`clic bouton ${label}`); break } } catch (e) {}
}
if (!clicked) { log('bouton Generer introuvable/desactive'); await page.screenshot({ path: `${outDir}/00_nobtn.png` }); await browser.close(); process.exit(2) }

// Attendre la fin: fichiers STABLES (n a plus bouge depuis 3 checks) OU erreur.
const started = Date.now()
let outcome = 'timeout'
let stableCount = 0, lastFiles = -1
while (Date.now() - started < GEN_TIMEOUT_MS) {
  await sleep(4000)
  const st = await page.evaluate(() => {
    const txt = document.body?.innerText || ''
    const fm = txt.match(/FICHIERS?\s*\((\d+)\)/i)
    const files = fm ? Number(fm[1]) : 0
    const errM = txt.match(/Erreur fatale[^\n]{0,120}|Echec de l[^\n]{0,80}/i)
    return { files, err: errM ? errM[0] : null }
  })
  const elapsed = Math.round((Date.now() - started) / 1000)
  if (st.err) { outcome = `ERREUR: ${st.err}`; log(outcome); break }
  if (st.files > 0 && st.files === lastFiles) { stableCount++ } else { stableCount = 0 }
  lastFiles = st.files
  if (st.files > 0 && stableCount >= 3) { outcome = `OK: ${st.files} fichiers`; log(`${outcome} (~${elapsed}s)`); break }
  if (elapsed % 24 === 0) log(`... ${elapsed}s (fichiers=${st.files}, stable=${stableCount})`)
}
await sleep(2500)

await page.screenshot({ path: `${outDir}/01_result.png` })
// Basculer sur le simulateur si un toggle existe
try { await page.locator('button:has-text("Simulateur")').first().click({ timeout: 3000 }); await sleep(1500) } catch (e) {}
await page.screenshot({ path: `${outDir}/02_simulator.png` })
// Plein ecran
try { await page.locator('button:has-text("Agrandir")').first().click({ timeout: 3000 }); await sleep(2000); await page.screenshot({ path: `${outDir}/03_fullscreen.png` }) } catch (e) { log('bouton Agrandir non trouve: ' + e.message) }

// Dump du HTML assemble reellement rendu (pour diagnostiquer un rendu casse).
try {
  const previewHtml = await page.evaluate(() => {
    const frames = Array.from(document.querySelectorAll('iframe'))
    const f = frames.find((x) => (x.getAttribute('srcdoc') || '').length > 20) || frames[0]
    return f ? (f.getAttribute('srcdoc') || '') : ''
  })
  writeFileSync(`${outDir}/preview.html`, previewHtml)
  log(`preview.html dumpe (${previewHtml.length} chars)`)
} catch (e) { log('dump preview echoue: ' + e.message) }

// Metrics du rendu + score affiche
const metrics = await page.evaluate(() => {
  const txt = document.body?.innerText || ''
  const scoreMatch = txt.match(/(\d{1,3})\s*%/)
  return { score: scoreMatch ? scoreMatch[1] : null, bodyLen: txt.length }
})
console.log(JSON.stringify({ outcome, metrics, errors: errors.slice(0, 5), shots: ['00_before','01_result','02_simulator','03_fullscreen'].map(s => `${outDir}/${s}.png`) }, null, 2))
await browser.close()
