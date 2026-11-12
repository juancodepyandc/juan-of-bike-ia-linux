#!/usr/bin/env node
// End-to-end check of the generation screen in Chromium: real FX bus scenarios
// (scripts/fx-harness), WebGL hologram (SwiftShader when no GPU), measured ETA,
// queue state, auto-reduction and characters. Starts its own Vite server.
//   AURORA_CHROMIUM=/path/to/chrome   when the bundled Playwright revision is absent
//   AURORA_FX_SHOTS=/some/dir         to keep a screenshot of each scenario
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { chromium, devices } from 'playwright'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const server = await createServer({
  root,
  configFile: path.join(root, 'vite.config.ts'),
  server: { host: '127.0.0.1', port: 0, strictPort: false },
  logLevel: 'error',
})
await server.listen()
const base = new URL('scripts/fx-harness/index.html', server.resolvedUrls.local[0]).href
const browser = await chromium.launch({
  executablePath: process.env.AURORA_CHROMIUM || undefined,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
})
const shots = process.env.AURORA_FX_SHOTS
let failures = 0

async function scenario(name, qs, check, device) {
  const context = await browser.newContext(device ? { ...devices[device] } : { viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  try {
    await page.goto(base + qs, { waitUntil: 'load' })
    await check(page)
    assert.deepEqual(errors, [], 'page errors')
    console.log(`ok - ${name}`)
  } catch (e) {
    failures++
    console.log(`not ok - ${name}: ${e instanceof Error ? e.message.split('\n')[0] : e}`)
  } finally {
    if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`) }).catch(() => {})
    await context.close()
  }
}

const hud = (page) => page.getByRole('dialog')

try {
  await scenario('each module has its own character in 8 states', '?mode=gallery', async (page) => {
    const labels = await page.locator('svg[role=img]').evaluateAll((els) => els.map((e) => e.getAttribute('aria-label') || ''))
    assert.equal(labels.length, 11 * 8)
    const names = new Set(labels.map((l) => l.split(',')[0]))
    assert.equal(names.size, 11, `distinct characters: ${[...names].join(' / ')}`)
    for (const state of ['attend son tour', 'attend ta réponse', 'a terminé', 'vérifie']) {
      assert(labels.some((l) => l.endsWith(state)), `state shown: ${state}`)
    }
  })

  await scenario('3D hologram is rebuilt from the real reference views', '?mode=3d-refs&module=3d', async (page) => {
    await page.getByText(/Reconstruit depuis 3 vue\(s\) réelle\(s\) : silhouette de face, épaisseur du profil/).waitFor({ timeout: 20000 })
    await page.getByText('ÉTAPE 2/6', { exact: true }).waitFor()
    await page.getByText(/médiane de 4 runs mesurés du module, par étape/).waitFor()
    assert.equal(await page.locator('canvas').count() >= 2, true, 'scene canvas + WebGL hologram')
  })

  await scenario('the real GLB materialises and colours appear at the materials phase', '?mode=3d-mesh&module=3d', async (page) => {
    await page.getByText(/Maillage réel produit par le pipeline \([\d\s ]+ triangles\)/).waitFor({ timeout: 20000 })
    await page.getByText('ÉTAPE 4/6', { exact: true }).waitFor()
    await page.getByText('HOLOGRAMME — MAILLAGE RÉEL EN MATÉRIALISATION').waitFor()
  })

  await scenario('the final mesh locks in, then hands over to the viewer', '?mode=3d-done&module=3d', async (page) => {
    await page.getByText('✓ MODÈLE PRÊT').waitFor({ timeout: 20000 })
    await hud(page).waitFor({ state: 'detached', timeout: 6000 })
  })

  await scenario('queued runs show the PC position and computed wait', '?mode=queued&module=image', async (page) => {
    await page.getByText('En file · position 2 · attente ≈ 40 s').waitFor({ timeout: 8000 })
    await page.locator('svg[aria-label$="attend son tour"]').first().waitFor()
  })

  await scenario('without measured runs no countdown is invented', '?mode=image&module=image&history=0', async (page) => {
    await page.getByText(/Estimation en préparation \(0\/3 runs mesurés\)/).waitFor({ timeout: 8000 })
    await page.getByText('57 %').waitFor()
  })

  await scenario('chat screen steps aside once the answer streams', '?mode=chat&module=conversation', async (page) => {
    await page.getByText('ÉTAPE 4/6', { exact: true }).waitFor({ timeout: 8000 })
    await hud(page).waitFor({ state: 'detached', timeout: 6000 })
    await page.locator('button[title^="Lyra"]').waitFor()
  })

  await scenario('a sub-second operation never flashes a screen', '?mode=flash&module=cyber', async (page) => {
    await page.waitForTimeout(1200)
    assert.equal(await hud(page).count(), 0)
    assert.equal(await page.locator('button[title^="Phantom"]').count(), 0)
  })

  await scenario('mobile: hologram and HUD fit the screen', '?mode=3d-refs&module=3d', async (page) => {
    await page.getByText(/Reconstruit depuis 3 vue\(s\) réelle\(s\)/).waitFor({ timeout: 20000 })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    assert(overflow <= 1, `horizontal overflow ${overflow}px`)
  }, 'Pixel 7')
} finally {
  await browser.close()
  await server.close()
}
console.log(failures ? `${failures} scenario(s) failed` : 'all generation-screen scenarios passed')
process.exit(failures ? 1 : 0)
