// Construction reelle des projets a bundler.
//
// Le verrou: un projet React/Vue/Svelte servi tel quel donne une page vide, et
// les juges concluaient « 0 caractere, livrable casse ». Mesure reelle
// (run 991): NEUF passes brulees a corriger une application qui n avait jamais
// ete construite. On construit donc, et le compilateur dit la verite.
//
// Ce fichier teste les parties PURES (aucun appel npm): detection, reparation
// de dependances, extraction des erreurs.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  completeMissingConfigDeps,
  extractBuildErrors,
  projectNeedsBuild,
  specForConfigPlugin,
} from '../../scripts/code_harness/project_build.mjs'

const ESC = String.fromCharCode(27)

const VITE_CONFIG = {
  name: 'vite.config.ts',
  content: "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\nexport default defineConfig({ plugins: [react()] })",
}

describe('project_build — reconnaitre un projet a construire', () => {
  test('un index.html qui pointe un module source doit etre construit', () => {
    assert.equal(projectNeedsBuild([
      { name: 'index.html', content: '<script type="module" src="/src/main.tsx"></script>' },
    ]), true)
  })

  test('une page statique ne doit pas etre construite', () => {
    assert.equal(projectNeedsBuild([
      { name: 'index.html', content: '<script src="script.js"></script>' },
      { name: 'script.js', content: 'console.log(1)' },
    ]), false)
  })

  test('un composant Vue ou Svelte suffit a exiger un build', () => {
    assert.equal(projectNeedsBuild([{ name: 'src/App.vue', content: '<template/>' }]), true)
  })
})

describe('project_build — la dependance manquante du fichier de config', () => {
  test('un plugin importe mais non declare est ajoute', () => {
    const manifest = { devDependencies: { vite: '^5.4.11' } }
    const { manifest: next, added } = completeMissingConfigDeps(manifest, [VITE_CONFIG], () => 'latest')
    assert.deepEqual(added, ['@vitejs/plugin-react'])
    assert.equal(next.devDependencies['@vitejs/plugin-react'], '^4')
  })

  test('un plugin deja declare n est pas retouche', () => {
    const manifest = { devDependencies: { vite: '^5', '@vitejs/plugin-react': '^3.1.0' } }
    const { added, manifest: next } = completeMissingConfigDeps(manifest, [VITE_CONFIG], () => 'latest')
    assert.deepEqual(added, [])
    assert.equal(next.devDependencies['@vitejs/plugin-react'], '^3.1.0')
  })

  test('la version du plugin suit le vite DECLARE, pas la derniere publiee', () => {
    // Mesure reelle: plugin-react recent + vite 5 => ERR_PACKAGE_PATH_NOT_EXPORTED.
    assert.equal(specForConfigPlugin('@vitejs/plugin-react', { devDependencies: { vite: '^5.4.11' } }, () => 'latest'), '^4')
    assert.equal(specForConfigPlugin('@vitejs/plugin-react', { devDependencies: { vite: '^8.1.0' } }, () => 'latest'), '^6')
    assert.equal(specForConfigPlugin('@vitejs/plugin-vue', { devDependencies: { vite: '^5' } }, () => 'latest'), '^5')
  })

  test('un paquet inconnu retombe sur la politique de l appelant', () => {
    assert.equal(specForConfigPlugin('vite-plugin-inconnu', { devDependencies: { vite: '^5' } }, () => '^9'), '^9')
  })

  test('sans fichier de config, rien n est invente', () => {
    assert.deepEqual(completeMissingConfigDeps({ devDependencies: {} }, [], () => 'x').added, [])
  })
})

describe('project_build — des erreurs lisibles par un modele', () => {
  test('garde les vraies erreurs et jette le bruit', () => {
    const log = [
      'added 214 packages in 3s',
      `${ESC}[31msrc/components/Footer.tsx(34,25): error TS1002: Unterminated string literal.${ESC}[0m`,
      'vite v8.1.5 building for production...',
      "Could not resolve './routes/Contact'",
    ].join('\n')
    const errors = extractBuildErrors(log)
    assert.equal(errors.some((line) => /TS1002: Unterminated string literal/.test(line)), true)
    assert.equal(errors.some((line) => /Could not resolve/.test(line)), true)
    assert.equal(errors.some((line) => /added 214 packages/.test(line)), false)
    // Les couleurs ANSI sont retirees: un modele ne doit pas lire des codes de terminal.
    assert.equal(errors.some((line) => line.includes(ESC)), false)
  })

  test('sans erreur, la liste est vide', () => {
    assert.deepEqual(extractBuildErrors('built in 1.2s\n42 modules transformed'), [])
  })

  test('la liste est bornee', () => {
    const log = Array.from({ length: 50 }, (_, index) => `error TS100${index}: souci ${index}`).join('\n')
    assert.equal(extractBuildErrors(log, 5).length, 5)
  })
})
