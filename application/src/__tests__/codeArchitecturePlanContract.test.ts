import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import {
  checkArchitecturePlanFileContract,
  describeArchitecturePlanContractIssue,
} from '../services/codeArchitecturePlanContract.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function plan(files: Array<{ path: string; required?: boolean }>) {
  return JSON.stringify({
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: 'Application React complete avec contrat de fichiers machine-verifiable.',
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['TypeScript'],
      frameworks: ['React'],
      dependencies: [{ name: 'react', type: 'runtime', reason: 'ui' }],
      scripts: [{ name: 'build', command: 'npm run build', purpose: 'validation' }],
    },
    files: files.map((file) => ({
      path: file.path,
      role: 'fichier requis',
      language: file.path.endsWith('.json') ? 'json' : 'tsx',
      required: file.required ?? true,
      imports: [],
      exports: [],
      notes: [],
    })),
    dataFlow: ['user -> app -> state'],
    execution: {
      install: ['npm install'],
      dev: ['npm run dev'],
      build: ['npm run build'],
      test: ['npm run build'],
      preview: 'vite',
    },
    generationOrder: files.map((file) => file.path),
    validation: ['build vert', 'preview visible'],
    risks: [{ risk: 'fichier oublie', mitigation: 'contrat machine' }],
    design: { palette: ['oklch'], typography: ['Inter'], ux: ['fluide'], responsive: ['mobile'] },
  })
}

function file(name: string): CodeFile {
  return { name, language: 'text', content: 'x' }
}

describe('codeArchitecturePlanContract', () => {
  test('accepte une livraison qui contient tous les fichiers requis du plan', () => {
    const report = checkArchitecturePlanFileContract(
      [file('package.json'), file('src/App.tsx')],
      plan([{ path: 'package.json' }, { path: 'src/App.tsx' }]),
    )

    assert.equal(report?.ok, true)
    assert.deepEqual(report?.missingRequiredFiles, [])
  })

  test('signale les fichiers requis absents et ignore les fichiers optionnels', () => {
    const issue = describeArchitecturePlanContractIssue(
      [file('package.json')],
      plan([
        { path: 'package.json' },
        { path: 'src/App.tsx' },
        { path: 'src/OptionalPanel.tsx', required: false },
      ]),
    )

    assert.match(issue ?? '', /src\/App\.tsx/)
    assert.doesNotMatch(issue ?? '', /OptionalPanel/)
  })

  test('ignore les plans invalides et les fichiers de documentation ajoutes ailleurs', () => {
    assert.equal(describeArchitecturePlanContractIssue([file('package.json')], '### Stack\nReact'), null)
    assert.equal(
      describeArchitecturePlanContractIssue(
        [file('package.json')],
        plan([{ path: 'package.json' }, { path: 'README.md' }]),
      ),
      null,
    )
  })
})
