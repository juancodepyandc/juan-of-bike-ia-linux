import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright'
import { explanationSvg } from '../src/services/drawingExplanation.ts'

const directory = resolve(process.argv[2] ?? '../audit/cycle-02-media')
await mkdir(directory, { recursive: true })
// This authored fixture checks rendering. It does not certify model reasoning.
const graph = {
  nodes: [
    { id: 'a', label: 'Évaporation' }, { id: 'b', label: 'Condensation' },
    { id: 'c', label: 'Précipitations' }, { id: 'd', label: 'Ruissellement' },
  ],
  edges: [
    { from: 'a', to: 'b', label: 'refroidissement' },
    { from: 'b', to: 'c', label: 'gouttelettes' },
    { from: 'c', to: 'd', label: 'écoulement' },
    { from: 'd', to: 'a', label: 'retour vers les océans' },
  ],
}
const svg = explanationSvg(JSON.stringify(graph))
await writeFile(resolve(directory, 'explanation-fixture.svg'), svg)
const browser = await chromium.launch({ headless: true, args: ['--disable-gpu'] })
try {
  const page = await browser.newPage({ viewport: { width: 800, height: 760 } })
  await page.setContent(`<html><body style="margin:0;background:#10131d">${svg}</body></html>`)
  const geometry = await page.locator('svg').evaluate(element => {
    const { width, height } = element.viewBox.baseVal
    const labels = [...element.querySelectorAll('text')].map(node => {
      const { x, y, width, height } = node.getBBox()
      return { text: node.textContent, bounds: { x, y, width, height } }
    })
    return {
      width, height, labels,
      overflowing: labels.filter(({ bounds: b }) => b.x < 0 || b.y < 0 || b.x + b.width > width || b.y + b.height > height),
    }
  })
  assert.equal(geometry.labels.length, 8)
  assert.deepEqual(geometry.overflowing, [])
  await writeFile(resolve(directory, 'svg-browser-measurements.json'), JSON.stringify({
    fixture_source: 'HAND_WRITTEN', evaluation: 'LAYOUT_ONLY', ...geometry,
  }, null, 2))
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
  await page.locator('svg').screenshot({ path: resolve(directory, 'explanation-fixture.png'), timeout: 10000 })
  console.log('Chromium: 8 readable labels within the SVG bounds, including a return relation.')
} finally {
  await browser.close()
}
