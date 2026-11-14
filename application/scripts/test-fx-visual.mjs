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

  await scenario('image studio follows the real ComfyUI run and reveals the result', '?mode=image-studio&module=image&stepMs=200', async (page) => {
    // sujet verrouillé lu dans la demande, montré avant la diffusion
    await page.getByText('vase en forme de cœur').waitFor({ timeout: 15000 })
    await page.getByText('« rayen »').first().waitFor()
    await page.getByText('aucune personne · aucun animal').waitFor()
    // chaque sous-étape vient d'un nœud réellement exécuté ; l'autre rendu du serveur est ignoré
    await page.getByText(/CHAMBRE DE DIFFUSION FLUX\.2 — DIFFUSION FLUX\.2 — PAS \d+\/12/).waitFor({ timeout: 20000 })
    await page.getByText(/s\/pas mesuré/).waitFor()
    await page.getByText(/aperçu latent réel · \d+ trame/).waitFor({ timeout: 15000 })
    assert.equal(await page.getByText(/pas 7\/9/).count(), 0, 'progress of another prompt must not show')
    await page.getByText('✓ IMAGE PRÊTE').waitFor({ timeout: 30000 })
    await page.getByText('non exécutée').waitFor()
    assert.equal(await page.locator('canvas').count() >= 2, true, 'ambient canvas + WebGL diffusion chamber')
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

  // ── Données réelles du dépôt : modèle VRM riggé et référence de personnage ──
  await scenario('hologram fidelity measured on the real avatar model (aurora-avatar.vrm)', '?mode=fidelity', async (page) => {
    await page.locator('#fidelity, #fidelity-error').first().waitFor({ timeout: 120000 })
    const res = await page.evaluate(() => window.__fidelity)
    assert(res, await page.locator('#fidelity-error').textContent().catch(() => 'no result'))
    const { hull, relief } = res
    console.log(`   real model: ${res.triangles} triangles, ${res.truthSamples} surface samples`)
    for (const r of [relief, hull]) {
      console.log(`   ${r.label}: Chamfer nuage→modèle p50 ${r.chamferCloudToModel.p50} % / p90 ${r.chamferCloudToModel.p90} %, modèle→nuage p50 ${r.chamferModelToCloud.p50} % / p90 ${r.chamferModelToCloud.p90} %, IoU face ${r.iouFront} (plafond ${r.iouFrontOfTruthSamples}), IoU profil ${r.iouSide} (plafond ${r.iouSideOfTruthSamples})`)
    }
    assert.equal(hull.method, 'hull')
    assert.equal(hull.profileSign, 1, 'profile orientation recovered from colours')
    assert(hull.chamferCloudToModel.p50 <= 1.2 && hull.chamferCloudToModel.p90 <= 2.5, 'hologram points lie on the real surface')
    assert(hull.chamferModelToCloud.p90 <= 3, 'the real surface is covered by the hologram')
    assert(hull.iouFront >= 0.88 && hull.iouSide >= 0.85, 'silhouettes match the real model')
    assert(hull.iouSide > relief.iouSide, 'the profile view improves the depth')
  })

  await scenario('a real character reference (natsu.png) becomes a relief hologram', '?mode=real-ref', async (page) => {
    await page.getByText('Relief reconstruit depuis la silhouette de la vue de face').waitFor({ timeout: 30000 })
  })

  await scenario('the real rigged model materialises as a hologram', '?mode=real-mesh', async (page) => {
    await page.getByText(/Maillage réel produit par le pipeline \(36[\s\u202f]470 triangles\)/).waitFor({ timeout: 60000 })
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
