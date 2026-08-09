// Verrouille la porte d entree du plan d architecture.
//
// Regression reelle observee deux fois: l intention est `static_web`, mais
// l architecte produit un plan Next.js (src/app/layout.tsx, next.config.js)
// SANS index.html. L executor ne pouvant ecrire que les fichiers de la file
// issue du plan, la porte de livraison refuse (« Page web statique detectee
// mais index.html est absent »), la boucle regenere le meme plan, et le run
// brule ses passes sur un defaut que personne ne corrige.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ensureArchitecturePlanEntryFiles,
  requiredEntryFilesForProject,
} from '../services/codeArchitecturePlanEntryContract.ts'

const intentOf = (projectType: string) => ({ projectType } as never)

function planWithout(paths: string[]) {
  return JSON.stringify({
    schemaVersion: 'aurora.code.architecture-plan/1',
    projectType: 'static_web',
    files: paths.map((p) => ({ path: p, role: 'module', language: 'ts', required: true, imports: [], exports: [], notes: [] })),
    generationOrder: [...paths],
  })
}

describe('requiredEntryFilesForProject', () => {
  test('static_web et game_web exigent index.html', () => {
    assert.deepEqual(requiredEntryFilesForProject('static_web'), ['index.html'])
    assert.deepEqual(requiredEntryFilesForProject('game_web'), ['index.html'])
  })

  test('un projet sans porte d entree web n exige rien', () => {
    assert.deepEqual(requiredEntryFilesForProject('cli_python'), [])
  })
})

describe('ensureArchitecturePlanEntryFiles', () => {
  test('ajoute index.html au plan Next.js produit pour un static_web (cas reel)', () => {
    const plan = planWithout(['src/app/layout.tsx', 'src/app/page.tsx', 'next.config.js'])
    const repaired = ensureArchitecturePlanEntryFiles(plan, intentOf('static_web'))
    assert.deepEqual(repaired.added, ['index.html'])
    const parsed = JSON.parse(repaired.plan)
    assert.ok(parsed.files.some((f: { path: string }) => f.path === 'index.html'))
    assert.equal(parsed.generationOrder[0], 'index.html', 'la porte d entree se genere en premier')
  })

  test('le fichier ajoute est requis et correctement typé', () => {
    const repaired = ensureArchitecturePlanEntryFiles(planWithout(['src/main.ts']), intentOf('static_web'))
    const entry = JSON.parse(repaired.plan).files.find((f: { path: string }) => f.path === 'index.html')
    assert.equal(entry.required, true)
    assert.equal(entry.language, 'html')
  })

  test('ne touche pas un plan deja conforme', () => {
    const plan = planWithout(['index.html', 'styles.css'])
    const repaired = ensureArchitecturePlanEntryFiles(plan, intentOf('static_web'))
    assert.deepEqual(repaired.added, [])
    assert.equal(repaired.plan, plan)
  })

  test('reconnait index.html quel que soit le prefixe de chemin', () => {
    const plan = planWithout(['./index.html'])
    assert.deepEqual(ensureArchitecturePlanEntryFiles(plan, intentOf('static_web')).added, [])
  })

  test('un type sans porte d entree laisse le plan intact', () => {
    const plan = planWithout(['main.py'])
    const repaired = ensureArchitecturePlanEntryFiles(plan, intentOf('cli_python'))
    assert.deepEqual(repaired.added, [])
    assert.equal(repaired.plan, plan)
  })

  test('un plan JSON inexploitable est rendu tel quel, sans lever', () => {
    const repaired = ensureArchitecturePlanEntryFiles('pas du json', intentOf('static_web'))
    assert.equal(repaired.plan, 'pas du json')
    assert.deepEqual(repaired.added, [])
  })

  test('spa_react exige index.html ET package.json', () => {
    const repaired = ensureArchitecturePlanEntryFiles(planWithout(['src/App.tsx']), intentOf('spa_react'))
    assert.deepEqual(repaired.added.sort(), ['index.html', 'package.json'])
  })
})
