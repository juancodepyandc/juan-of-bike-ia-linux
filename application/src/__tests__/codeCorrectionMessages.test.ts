import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CorrectionStrategy } from '../services/codeAutoCorrection.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import { buildCorrectionMessages } from '../services/codeCorrectionMessages.ts'

const strategy: CorrectionStrategy = {
  level: 'targeted_repair',
  escalation: 1,
  instructions: 'corriger les fichiers en erreur',
  switchModel: false,
  searchWeb: false,
}

const intent = {
  projectType: 'spa_react',
  assetPlan: { subject: null },
} as unknown as CodeIntent

function sandbox(output: string, summary = 'build failed'): CodeSandboxResult {
  return {
    ok: false,
    rootPath: '/tmp/project',
    summary,
    question: null,
    detectedLanguage: 'node',
    steps: [
      {
        label: 'Build',
        command: 'npm run build',
        ok: false,
        output,
      },
    ],
  }
}

describe('codeCorrectionMessages', () => {
  test('injecte les priorites JSON et TypeScript dans le message systeme', () => {
    const messages = buildCorrectionMessages({
      prompt: 'corrige cette app',
      files: [{ name: 'package.json', language: 'json', content: '{"name":"demo"}' }],
      validationResult: sandbox('JSONParseError in package.json\nerror TS1139: type parameter declaration expected'),
      strategy,
      researchContext: '',
      missionDossierText: 'Mission stable',
      architecturePlan: '### Stack\nReact',
      preflightReportText: 'Node disponible',
      intent,
    })

    assert.match(messages[0].content, /PRIORITE ABSOLUE/)
    assert.match(messages[0].content, /PRIORITE COMPATIBILITE TYPESCRIPT/)
    assert.match(messages[1].content, /Dossier executif:\nMission stable/)
    assert.match(messages[1].content, /Preflight local:\nNode disponible/)
    assert.match(messages[1].content, /Fichiers actuels/)
  })

  test('ajoute le contexte recherche et raisonnement quand ils existent', () => {
    const messages = buildCorrectionMessages({
      prompt: 'corrige cette app',
      files: [{ name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){return <main />}' }],
      validationResult: sandbox('Cannot find module vite'),
      strategy,
      researchContext: 'Installer vite dans devDependencies.',
      reasoningContext: 'Cause racine: manifest incomplet.',
      missionDossierText: 'Mission stable',
      architecturePlan: null,
      preflightReportText: null,
      intent,
    })

    assert.match(messages[1].content, /Solutions trouvees en ligne/)
    assert.match(messages[1].content, /Cause racine/)
  })
})
