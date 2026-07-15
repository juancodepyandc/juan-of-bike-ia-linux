import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
  formatArchitecturePlanDependenciesForMarkdown,
  parseArchitecturePlanJson,
} from '../services/codeArchitecturePlan.ts'

function validPlan(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: 'Application React complete avec routage, etat local et validation executable.',
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['TypeScript', 'CSS'],
      frameworks: ['React', 'Vite'],
      dependencies: [
        { name: 'react', version: '^19.0.0', type: 'runtime', reason: 'UI' },
        { name: 'vite', version: '^8.0.0', type: 'dev', reason: 'build' },
      ],
      scripts: [
        { name: 'dev', command: 'npm run dev', purpose: 'preview locale' },
        { name: 'build', command: 'npm run build', purpose: 'validation production' },
      ],
    },
    files: [
      { path: 'package.json', role: 'manifest npm', language: 'json', required: true, imports: [], exports: [], notes: [] },
      { path: 'src/App.tsx', role: 'interface principale', language: 'tsx', required: true, imports: ['./main'], exports: ['App'], notes: ['responsive'] },
    ],
    dataFlow: ['user -> App -> state -> render'],
    execution: {
      install: ['npm install'],
      dev: ['npm run dev'],
      build: ['npm run build'],
      test: ['npm run build'],
      preview: 'Vite dev server',
    },
    generationOrder: ['package.json', 'src/App.tsx'],
    validation: ['npm run build passe', 'preview affiche une interface complete'],
    risks: [{ risk: 'imports locaux manquants', mitigation: 'generer tous les fichiers references' }],
    design: {
      palette: ['oklch accents'],
      typography: ['Inter'],
      ux: ['navigation claire'],
      responsive: ['mobile et desktop'],
    },
    ...overrides,
  }
}

describe('codeArchitecturePlan', () => {
  test('parse et normalise un plan JSON meme entoure de bruit', () => {
    const raw = `<think>analyse interne</think>\n\`\`\`json\n${JSON.stringify(validPlan())}\n\`\`\``
    const parsed = parseArchitecturePlanJson(raw)

    assert.equal(parsed.ok, true)
    assert.equal(parsed.ok && parsed.plan.files.length, 2)
    assert.equal(parsed.ok && JSON.parse(parsed.serialized).schemaVersion, CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION)
  })

  test('rejette un plan markdown libre', () => {
    const parsed = parseArchitecturePlanJson('### Stack\nReact\n### Fichiers\n- `src/App.tsx`')

    assert.equal(parsed.ok, false)
    assert.match(parsed.ok ? '' : parsed.errors.join(','), /json_object_missing/)
  })

  test('rejette les chemins dangereux hors racine', () => {
    const parsed = parseArchitecturePlanJson(JSON.stringify(validPlan({
      files: [
        { path: '../package.json', role: 'dangereux', required: true },
        { path: 'src/App.tsx', role: 'app', required: true },
      ],
    })))

    assert.equal(parsed.ok, false)
    assert.match(parsed.ok ? '' : parsed.errors.join(','), /files_min_2/)
  })

  test('formate dependances et scripts depuis le plan JSON', () => {
    const formatted = formatArchitecturePlanDependenciesForMarkdown(JSON.stringify(validPlan()))

    assert.match(formatted, /react\@\^19\.0\.0/)
    assert.match(formatted, /npm run build/)
  })
})

