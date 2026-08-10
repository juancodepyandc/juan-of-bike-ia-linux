// Verrouille la porte des tokens de design.
//
// Cas reel (run runId=940, SaaS analytics Vue, 32 fichiers, build vert): le
// rendu sortait entierement plat — serif par defaut, un seul fond, zero ombre.
// Le modele avait pourtant ecrit `src/assets/styles/variables.css` avec tous
// les tokens, et les composants les utilisaient. Mais `main.ts` n importait
// AUCUN CSS: la feuille existait sur le disque et n etait jamais chargee, donc
// chaque `var()` etait invalide et le navigateur jetait la declaration entiere.
//
// La porte mesure le GRAPHE DE CHARGEMENT: une definition presente sur disque
// mais jamais importee compte comme ABSENTE.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { checkDesignTokens, collectLoadedCss } from '../services/codeDesignTokenGate.ts'

const VARS = ':root { --accent: #4f46e5; --bg: #0a0a0c; }'
const USE = '.btn { background: var(--accent); color: var(--bg); }'

describe('checkDesignTokens — HTML statique', () => {
  test('feuille liee qui definit ET utilise: passe', () => {
    const r = checkDesignTokens([
      { name: 'index.html', content: '<html><head><link rel="stylesheet" href="style.css"></head><body></body></html>' },
      { name: 'style.css', content: `${VARS}\n${USE}` },
    ])
    assert.equal(r.ok, true, `orphelins: ${r.orphanTokens.join(',')}`)
  })

  test('feuille NON liee qui definit les tokens: echoue (cas reel)', () => {
    const r = checkDesignTokens([
      { name: 'index.html', content: '<html><head><link rel="stylesheet" href="style.css"></head><body></body></html>' },
      { name: 'style.css', content: USE },
      { name: 'tokens.css', content: VARS },
    ])
    assert.equal(r.ok, false)
    assert.deepEqual(r.orphanTokens, ['--accent', '--bg'])
    assert.deepEqual(r.unreachableStylesheets, ['tokens.css'])
    assert.match(r.critique, /tokens\.css/)
  })

  test('variable jamais definie nulle part: echoue', () => {
    const r = checkDesignTokens([
      { name: 'index.html', content: '<html><head><link rel="stylesheet" href="style.css"></head></html>' },
      { name: 'style.css', content: '.x { color: var(--jamais-defini); }' },
    ])
    assert.equal(r.ok, false)
    assert.deepEqual(r.orphanTokens, ['--jamais-defini'])
    assert.deepEqual(r.unreachableStylesheets, [])
  })

  test('un <style> inline definit aussi les tokens', () => {
    const r = checkDesignTokens([
      { name: 'index.html', content: `<html><head><style>${VARS}</style><link rel="stylesheet" href="s.css"></head></html>` },
      { name: 's.css', content: USE },
    ])
    assert.equal(r.ok, true)
  })
})

describe('checkDesignTokens — projet a bundler', () => {
  const component = { name: 'src/App.vue', content: `<template><b/></template><style scoped>${USE}</style>` }
  const tokens = { name: 'src/assets/styles/variables.css', content: VARS }

  test('entree qui N IMPORTE PAS le CSS: echoue (bug reel runId=940)', () => {
    const r = checkDesignTokens([
      { name: 'src/main.ts', content: "import { createApp } from 'vue'\nimport App from './App.vue'\ncreateApp(App).mount('#app')" },
      component,
      tokens,
    ])
    assert.equal(r.ok, false)
    assert.deepEqual(r.orphanTokens, ['--accent', '--bg'])
    assert.ok(r.unreachableStylesheets.includes('src/assets/styles/variables.css'))
    assert.match(r.critique, /import/i)
  })

  test('entree qui importe le CSS: passe', () => {
    const r = checkDesignTokens([
      { name: 'src/main.ts', content: "import './assets/styles/variables.css'\nimport App from './App.vue'" },
      component,
      tokens,
    ])
    assert.equal(r.ok, true, `orphelins: ${r.orphanTokens.join(',')}`)
  })

  test('import transitif via un module intermediaire', () => {
    const r = checkDesignTokens([
      { name: 'src/main.ts', content: "import './theme'\nimport App from './App.vue'" },
      { name: 'src/theme.ts', content: "import './assets/styles/variables.css'" },
      component,
      tokens,
    ])
    assert.equal(r.ok, true, `orphelins: ${r.orphanTokens.join(',')}`)
  })

  test('un token pose en JS par setProperty compte comme defini', () => {
    const r = checkDesignTokens([
      { name: 'src/main.ts', content: "document.documentElement.style.setProperty('--accent', '#fff')\nimport App from './App.vue'" },
      { name: 'src/App.vue', content: '<template><b/></template><style>.b{color:var(--accent)}</style>' },
    ])
    assert.equal(r.ok, true, `orphelins: ${r.orphanTokens.join(',')}`)
  })

  test('un projet sans aucun CSS ne declenche rien', () => {
    const r = checkDesignTokens([{ name: 'main.py', content: 'print(1)' }])
    assert.equal(r.ok, true)
    assert.deepEqual(r.orphanTokens, [])
  })
})

describe('collectLoadedCss', () => {
  test('suit @import a l interieur d une feuille chargee', () => {
    const { css } = collectLoadedCss([
      { name: 'index.html', content: '<html><head><link rel="stylesheet" href="a.css"></head></html>' },
      { name: 'a.css', content: "@import 'b.css';" },
      { name: 'b.css', content: VARS },
    ])
    assert.match(css, /--accent/)
  })

  test('ignore une feuille jamais referencee', () => {
    const { css, loaded } = collectLoadedCss([
      { name: 'index.html', content: '<html><head></head></html>' },
      { name: 'orpheline.css', content: VARS },
    ])
    assert.doesNotMatch(css, /--accent/)
    assert.deepEqual(loaded, [])
  })
})
