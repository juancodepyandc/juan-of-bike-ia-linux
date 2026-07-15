import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import {
  getArchitecturePlanCandidateCount,
  selectBestArchitecturePlan,
} from '../services/codeArchitecturePlanSelection.ts'

function plan(fileCount: number) {
  return JSON.stringify({
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: `Plan complet avec ${fileCount} fichiers et validation reproductible.`,
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['TypeScript'],
      frameworks: ['React'],
      dependencies: [{ name: 'react', type: 'runtime' }],
      scripts: [{ name: 'build', command: 'npm run build' }],
    },
    files: Array.from({ length: fileCount }, (_, index) => ({
      path: index === 0 ? 'package.json' : `src/file${index}.tsx`,
      role: `fichier ${index}`,
      required: true,
    })),
    dataFlow: ['user -> app'],
    execution: { install: ['npm install'], dev: ['npm run dev'], build: ['npm run build'], test: ['npm run build'], preview: 'vite' },
    generationOrder: ['package.json', 'src/file1.tsx'],
    validation: ['build vert', 'preview visible'],
    risks: [{ risk: 'imports', mitigation: 'generer les fichiers' }],
    design: { palette: ['oklch'], typography: ['Inter'], ux: ['fluide'], responsive: ['mobile'] },
  })
}

describe('codeArchitecturePlanSelection', () => {
  test('active best-of-2 uniquement pour les projets critiques', () => {
    assert.equal(getArchitecturePlanCandidateCount({ complexity: 'simple' } as CodeIntent), 1)
    assert.equal(getArchitecturePlanCandidateCount({ complexity: 'complex' } as CodeIntent), 2)
    assert.equal(getArchitecturePlanCandidateCount({ complexity: 'enterprise' } as CodeIntent), 2)
  })

  test('selectionne le meilleur plan valide et ignore les candidats invalides', () => {
    const selection = selectBestArchitecturePlan([
      '### Stack\nReact',
      plan(4),
      plan(2),
    ])

    assert.equal(selection.selected?.index, 1)
    assert.equal(selection.scored[0].ok, false)
    assert.ok((selection.selected?.score ?? 0) > selection.scored[2].score)
  })
})

