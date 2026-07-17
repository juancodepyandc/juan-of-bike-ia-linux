// Capture reelle de l'UI du module Code, par skin, pour analyse visuelle.
// Usage: node ui_capture.mjs <baseUrl> <outDir> [skin1,skin2,...]
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const baseUrl = process.argv[2] || 'http://localhost:1420'
const outDir = process.argv[3] || '/tmp/ui_caps'
const skins = (process.argv[4] || 'aurora_v4,aurora_v1,aurora_v3').split(',')
mkdirSync(outDir, { recursive: true })

async function captureSkin(browser, skin) {
  const context = await browser.newContext({
    viewport: { width: 1680, height: 1000 },
    deviceScaleFactor: 1,
  })
  // Force la skin AVANT le chargement des scripts app.
  await context.addInitScript((s) => {
    try {
      localStorage.setItem('aurora-ui-skin', s)
      localStorage.setItem('aurora-ui-skin-choice', s)
    } catch (e) { /* ignore */ }
  }, skin)
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e.message || e).slice(0, 200)))
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await sleep(2500)

  // Aller au module Code: on tente le clic sur l'item de dock "Code", sinon raccourci.
  let navMethod = 'none'
  try {
    const codeNav = page.locator('[role="navigation"] >> text=/^Code$/i').first()
    if (await codeNav.count()) { await codeNav.click({ timeout: 3000 }); navMethod = 'dock-click' }
  } catch (e) { /* fallthrough */ }
  if (navMethod === 'none') {
    try { await page.locator('text=/^Code$/').first().click({ timeout: 3000 }); navMethod = 'text-click' } catch (e) { /* */ }
  }
  if (navMethod === 'none') { await page.keyboard.press('o'); navMethod = 'key-o' }
  await sleep(2500)

  const shot = `${outDir}/code_${skin}.png`
  await page.screenshot({ path: shot, fullPage: false })

  // Sonde: le bouton "Agrandir" (viewer plein ecran) et "Onglet" sont-ils presents ?
  const probe = await page.evaluate(() => {
    const txt = (document.body?.innerText || '')
    const hasAgrandir = /agrandir/i.test(txt)
    const hasOnglet = /onglet/i.test(txt)
    const hasDesktopTabletMobile = /desktop/i.test(txt) && /mobile/i.test(txt)
    const buttons = Array.from(document.querySelectorAll('button')).map((b) => (b.getAttribute('title') || b.innerText || '').trim()).filter(Boolean)
    return {
      hasAgrandir, hasOnglet, hasDesktopTabletMobile,
      buttonTitles: buttons.filter((t) => /agrandir|onglet|plein|viewer|desktop|tablet|mobile/i.test(t)).slice(0, 12),
      bodyLen: txt.length,
    }
  })
  await context.close()
  return { skin, navMethod, shot, probe, errors: errors.slice(0, 5) }
}

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const results = []
for (const skin of skins) {
  try { results.push(await captureSkin(browser, skin)) }
  catch (e) { results.push({ skin, error: String(e.message || e).slice(0, 300) }) }
}
await browser.close()
console.log(JSON.stringify(results, null, 2))
