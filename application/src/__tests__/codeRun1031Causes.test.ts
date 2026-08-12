// Les trois verrous du run 1031 (brulerie), chacun mesure sur le cas reel.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { evaluateVisualFidelity } from '../services/codeVisualFidelity.ts'
import { usesTailwind } from '../services/codeTailwindSignals.ts'
import { hasServerSide, secretRemediation } from '../services/codeSecretRemediation.ts'
import { isMachineCriticalJson, validateStructuredFiles } from '../services/codeProjectValidation.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const SPA: CodeIntent = { projectType: 'spa_react' } as unknown as CodeIntent
const PKG = { name: 'package.json', language: 'json', content: '{"name":"b","devDependencies":{"tailwindcss":"^3.4.0"}}' }

// Reproduction du projet reel: Tailwind, aucune propriete CSS ecrite a la main.
const TW_FILES = [
  PKG,
  { name: 'src/index.css', language: 'css', content: '@tailwind base;\n@tailwind components;\n@tailwind utilities;' },
  { name: 'index.html', language: 'html', content: '<!doctype html><html><body><div id="root"></div></body></html>' },
  ...['Home', 'About', 'CoffeeList', 'Contact', 'Admin', 'Header', 'Footer'].map((n) => ({
    name: `src/components/${n}.tsx`, language: 'typescript',
    content: `export const ${n} = () => (<section className="rounded-lg shadow-md hover:bg-amber-100 transition">
      <h2 className="text-2xl">${n}</h2><p>Contenu editorial reel pour la section ${n}, avec du texte suffisant pour etre juge serieusement.</p>
      <img src="/${n}.avif" alt="${n}" width="400" height="300" /></section>)`,
  })),
]

describe('run 1031 — cause 1: le juge etait aveugle a Tailwind', () => {
  test('Tailwind est reconnu', () => {
    assert.equal(usesTailwind(TW_FILES), true)
    assert.equal(usesTailwind([{ name: 'index.html', content: '<p>x</p>' }]), false)
  })

  test('arrondis et survols exprimes en utilitaires sont VUS', () => {
    const report = evaluateVisualFidelity(TW_FILES, SPA, null, 'site vitrine pour ma marque de cafe')
    for (const id of ['has_radius', 'has_hover']) {
      assert.equal(report.checks.find((c) => c.id === id)?.passed, true, `${id} doit passer: rounded-lg / hover: presents`)
    }
  })

  test('chaque composant de page compte comme une section', () => {
    const report = evaluateVisualFidelity(TW_FILES, SPA, null, 'site vitrine pour ma marque de cafe')
    assert.equal(report.checks.find((c) => c.id === 'min_sections')?.passed, true)
  })

  test('un projet SANS ces proprietes reste refuse — pas de laissez-passer Tailwind', () => {
    // Markup VISIBLE (sinon c est la regle « non mesure » qui repond, pas la
    // notation) mais depourvu d arrondis et de survols.
    const bare = [PKG, { name: 'src/App.tsx', language: 'typescript', content: `export const App = () => (<div className="p-4 bg-white">
      <h1>Brulerie</h1><p>${'Texte editorial sans aucune finition visuelle. '.repeat(12)}</p></div>)` }]
    const report = evaluateVisualFidelity(bare, SPA, null, 'site vitrine pour ma marque de cafe')
    assert.equal(report.checks.find((c) => c.id === 'has_radius')?.passed, false)
  })
})

describe('run 1031 — cause 1bis: ne jamais condamner ce qu on n a pas vu', () => {
  test('coquille de bundler sans composants lisibles: NON MESURE, pas condamne', () => {
    const shell = [PKG, { name: 'index.html', language: 'html', content: '<!doctype html><html><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>' },
      { name: 'src/main.tsx', language: 'typescript', content: 'render(<App/>)' }]
    const report = evaluateVisualFidelity(shell, SPA, null, 'site vitrine')
    assert.equal(report.notMeasured, true)
    assert.match(report.summary, /NON MESURE/)
  })

  test('des que le markup est lisible, la porte juge normalement', () => {
    const report = evaluateVisualFidelity(TW_FILES, SPA, null, 'site vitrine pour ma marque de cafe')
    assert.notEqual(report.notMeasured, true)
    assert.ok(report.checks.length > 0)
  })
})

describe('run 1031 — cause 2: un conseil irrealisable fait boucler le modele', () => {
  test('sans backend, on NE conseille PAS une variable d environnement', () => {
    const advice = secretRemediation([PKG, { name: 'src/lib/auth.ts', language: 'typescript', content: "const correctPassword = 'brulerie2024'" }])
    assert.match(advice, /AUCUN cote serveur/)
    assert.match(advice, /INLINE dans le bundle/)
    assert.doesNotMatch(advice, /^Deplacer la valeur hors du code/)
  })

  test('avec un backend, le conseil .env redevient le bon', () => {
    const advice = secretRemediation([PKG, { name: 'server/app.py', language: 'python', content: 'from flask import Flask' }])
    assert.match(advice, /variable d environnement/)
    assert.match(advice, /SERVEUR/)
  })

  test('la detection de backend ne se laisse pas tromper par un dossier src/api front', () => {
    assert.equal(hasServerSide([PKG, { name: 'src/App.tsx', language: 'typescript', content: 'x' }]), false)
    assert.equal(hasServerSide([{ name: 'server/index.js', language: 'javascript', content: "require('express')" }]), true)
  })
})

describe('run 1031 — cause 3: un JSON annexe ne condamne pas la passe', () => {
  test('main.json casse n annule plus toute la passe de correction', () => {
    assert.equal(validateStructuredFiles([
      { name: 'src/data/main.json', language: 'json', content: '{ casse' },
      { name: 'package.json', language: 'json', content: '{"name":"ok"}' },
    ]), null)
  })

  test('package.json casse condamne TOUJOURS: le build en depend', () => {
    const issue = validateStructuredFiles([{ name: 'package.json', language: 'json', content: '{ casse' }])
    assert.match(issue ?? '', /JSON valide/)
  })

  test('la liste des JSON critiques couvre les manifestes de build', () => {
    for (const name of ['package.json', 'tsconfig.json', 'src-tauri/tauri.conf.json', 'manifest.json']) {
      assert.equal(isMachineCriticalJson(name), true, name)
    }
    assert.equal(isMachineCriticalJson('src/data/cafes.json'), false)
  })
})
