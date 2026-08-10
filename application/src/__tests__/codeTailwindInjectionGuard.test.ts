// Verrouille l injection Tailwind — Aurora detruisait son propre design.
//
// Cas reel. Une landing Mercedes livree par le pipeline complet sortait son
// titre en 18 px sur 1440 px de large. Le modele avait pourtant ecrit ce qu il
// fallait: `--font-display: clamp(40px, 5vw, 96px)` et `h1 { font-size:
// var(--font-display) }`.
//
// C est AURORA qui cassait le rendu: `ensureTailwindCDN` declenchait sur
// `class="container"` — un nom de classe semantique parfaitement courant — et
// injectait le CDN Tailwind. Le Preflight de Tailwind remet alors
// `h1 { font-size: inherit }`, ecrasant la regle de l auteur.
//
// Preuve par la mesure: en retirant le bloc injecte de la page livree et en la
// re-rendant, l echelle typographique passe de [13,16,18] a [13,16,18,19,24,72]
// — le titre de 72 px revient — et le score de rendu de 18/100 a 46/100.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { upsertProjectSupportFilesForTest } from '../services/codeProjectSupportFiles.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const intent = classifyCodeIntent('landing page premium pour la marque Mercedes-Benz')
const html = (body: string, head = '') =>
  [{ name: 'index.html', language: 'html', content: `<html><head>${head}</head><body>${body}</body></html>` }]
const run = (files: ReturnType<typeof html>) =>
  upsertProjectSupportFilesForTest(files, intent, 'prompt', null)[0].content

describe('injection Tailwind — ne jamais ecraser une page auto-stylee', () => {
  test('une page avec sa propre feuille de style et class="container" n est PAS touchee', () => {
    const out = run(html('<div class="container"><h1>Mercedes</h1></div>', '<link rel="stylesheet" href="css/styles.css">'))
    assert.doesNotMatch(out, /cdn\.tailwindcss\.com/, 'Tailwind ne doit pas etre injecte dans une page auto-stylee')
  })

  test('les noms de classe semantiques seuls ne declenchent plus l injection', () => {
    for (const cls of ['container', 'flex', 'grid', 'hidden']) {
      const out = run(html(`<div class="${cls}"><h1>T</h1></div>`))
      assert.doesNotMatch(out, /cdn\.tailwindcss\.com/, `"${cls}" ne doit pas declencher Tailwind`)
    }
  })

  test('le vocabulaire Tailwind reel declenche toujours l injection (benefice v85g conserve)', () => {
    const out = run(html('<div class="bg-surface text-fg p-4 gap-6"><h1 class="text-4xl">T</h1></div>'))
    assert.match(out, /cdn\.tailwindcss\.com/, 'une page qui utilise le vocabulaire Aurora doit recevoir sa config')
  })

  test('quand Tailwind est injecte, le Preflight est DESACTIVE', () => {
    const out = run(html('<div class="bg-surface text-fg p-4"><h1>T</h1></div>'))
    assert.match(out, /preflight:false/, 'Preflight doit etre desactive: il ecrase la typographie de l auteur')
  })

  test('une page deja pourvue de Tailwind n est pas doublee', () => {
    const out = run(html('<div class="p-4 bg-surface"></div>', '<script src="https://cdn.tailwindcss.com"></script>'))
    assert.equal((out.match(/cdn\.tailwindcss\.com/g) || []).length, 1)
  })
})

// --- Config Vite par framework (2026-08-10) --------------------------------
// `ensureSpaViteConfig` injectait un plugin REACT pour TOUT projet `spa_*`.
// Sur le SaaS Vue livre par le run runId=940, le build echouait donc avec
// « Install @vitejs/plugin-vue to handle .vue files » — alors que le modele
// avait, lui, correctement declare plugin-vue dans package.json. Aurora rendait
// inconstruisible un livrable correct.
describe('config Vite injectee — le plugin doit suivre le framework', () => {
  const vite = (projectType: string) => {
    const intent = { ...classifyCodeIntent('app'), projectType } as never
    const out = upsertProjectSupportFilesForTest([
      { name: 'src/main.ts', language: 'typescript', content: 'export {}' },
    ], intent, 'prompt', null)
    return out.find((f) => f.name === 'vite.config.ts')?.content ?? ''
  }

  test('un projet Vue recoit plugin-vue, jamais plugin-react', () => {
    const cfg = vite('spa_vue')
    assert.match(cfg, /@vitejs\/plugin-vue/)
    assert.match(cfg, /vue\(\)/)
    assert.doesNotMatch(cfg, /plugin-react/, 'un projet Vue ne doit jamais recevoir le plugin React')
  })

  test('un projet React garde plugin-react', () => {
    const cfg = vite('spa_react')
    assert.match(cfg, /@vitejs\/plugin-react/)
    assert.match(cfg, /react\(\)/)
  })

  test('un projet Svelte recoit le plugin Svelte', () => {
    assert.match(vite('spa_svelte'), /vite-plugin-svelte/)
  })

  test('un framework inconnu ne recoit aucun plugin plutot qu un faux', () => {
    const cfg = vite('spa_angular')
    assert.doesNotMatch(cfg, /plugin-react|plugin-vue/)
    assert.match(cfg, /plugins: \[\]/)
  })
})
