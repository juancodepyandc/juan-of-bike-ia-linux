import assert from 'node:assert/strict'
import { chromium, devices } from 'playwright'

// Use real mobile user agents: a narrow desktop window does not exercise ShellRouter.
const url = process.env.AURORA_TEST_URL || 'http://127.0.0.1:3001'
const browser = await chromium.launch()
try {
  for (const name of ['Pixel 7', 'iPhone 13', 'iPad Mini', 'Desktop Chrome']) {
    const context = await browser.newContext({ ...devices[name] })
    const page = await context.newPage()
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await page.locator('.v4c-root').waitFor()
    assert.equal(await page.locator('html').getAttribute('data-ui-skin'), 'aurora_v4')
    const mobile = name !== 'Desktop Chrome'
    const nav = page.getByRole('navigation', { name: 'Navigation mobile' })
    if (mobile) {
      assert(await nav.isVisible(), `${name}: navigation unavailable`)
      assert(!(await page.locator('.aurora-voice-quick-toggle').isVisible()), 'Floating voice control covers navigation')
      const draft = page.locator('[data-aurora-module=conversation] .v4c-composer textarea')
      await draft.fill('Brouillon conservé après navigation')
      await nav.getByRole('button', { name: 'Image', exact: true }).click()
      await page.locator('[data-aurora-module="image"]').waitFor({ state: 'visible' })
      await nav.getByRole('button', { name: 'Chat', exact: true }).click()
      assert.equal(await draft.inputValue(), 'Brouillon conservé après navigation')
      await page.evaluate(() => {
        for (const [type,x] of [['touchstart',5],['touchend',300]]) {
          const touch = new Touch({ identifier:1, target:document.body, clientX:x, clientY:200 })
          document.dispatchEvent(new TouchEvent(type, { changedTouches:[touch], touches:type==='touchstart'?[touch]:[], bubbles:true }))
        }
        document.dispatchEvent(new WheelEvent('wheel', { deltaX:300, bubbles:true }))
      })
      assert.equal(await nav.getByRole('button', { name:'Chat', exact:true }).getAttribute('aria-current'), 'page')
      await nav.getByRole('button', { name:'Tous les modules', exact:true }).click()
      const sheet = page.getByRole('dialog', { name:'Votre espace Aurora' })
      assert(await sheet.isVisible())
      const box = await sheet.boundingBox()
      const viewport = page.viewportSize()
      assert(box.x >= 0 && box.x + box.width <= viewport.width + 1)
      assert(box.y >= 0 && box.y + box.height <= viewport.height + 1)
      assert.equal(await sheet.locator('.aurora-v4-module-grid button').count(), 11)
      await page.keyboard.press('Escape')
      await sheet.waitFor({ state:'hidden' })
      for (const [label,id] of [['Code','code'],['Vidéo','video'],['Dessin','drawing'],['3D','3d'],['Académie','learning'],['Cyber','cyber']]) {
        await nav.getByRole('button', { name:'Tous les modules', exact:true }).click()
        await sheet.getByRole('button', { name:label, exact:true }).click()
        await page.locator(`[data-aurora-module="${id}"]`).waitFor({ state:'visible' })
      }
      await nav.getByRole('button', { name:'Chat', exact:true }).click()
      assert.equal(await draft.inputValue(), 'Brouillon conservé après navigation')
      for (const button of await nav.getByRole('button').all()) {
        const r = await button.boundingBox()
        assert(r.height >= 44 && r.width >= 44)
        assert(await button.evaluate(el => {const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}))
      }
      await page.setViewportSize({ width:844,height:390 })
      assert(await nav.isVisible())
    } else assert(!(await nav.isVisible()))
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    console.log(`${name}: routing, layout${mobile ? ', draft, gestures, dialog and touch targets' : ''} OK`)
    await context.close()
  }
} finally { await browser.close() }
