import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CorrectionStrategy } from '../services/codeAutoCorrection.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import { buildCorrectionMessages } from '../services/codeCorrectionMessages.ts'
import { buildRegressionFeedbackBlock } from '../services/codeCorrectionRegressionFeedback.ts'

const strategy: CorrectionStrategy = {
  level: 'targeted_repair',
  escalation: 1,
  cause: 'config_error',
  locality: 'manifest',
  history: { stagnating: false, repeatedErrorCount: 0, adaptiveBudget: 8 },
  instructions: 'corriger les fichiers en erreur',
  switchModel: false,
  searchWeb: false,
}

const strategyChange: CorrectionStrategy = {
  ...strategy,
  level: 'strategy_change',
  escalation: 5,
  cause: 'build_failure',
  locality: 'multi_file',
  history: { stagnating: true, repeatedErrorCount: 3, adaptiveBudget: 10 },
  instructions: 'Preserve les contrats publics et repare la cause racine.',
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
    assert.match(messages[0].content, /Cause dominante: config_error/)
    assert.match(messages[0].content, /Localite probable: manifest/)
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

  test('strategy_change conserve le perimetre au lieu de degrader le projet', () => {
    const messages = buildCorrectionMessages({
      prompt: 'corrige cette app',
      files: [{ name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){return <main />}' }],
      validationResult: sandbox('Build failed'),
      strategy: strategyChange,
      researchContext: '',
      missionDossierText: 'Mission stable',
      architecturePlan: null,
      preflightReportText: null,
      intent,
    })

    assert.match(messages[0].content, /conserve la stack/)
    assert.match(messages[0].content, /Interdiction de faire passer la validation en supprimant/)
    assert.doesNotMatch(messages[0].content, /simplifie l architecture, utilise des patterns differents, change de librairies/i)
  })
})

describe('codeCorrectionMessages — retour du harnais anti-regression', () => {
  // Anti-orphelin: le verdict du garde EXISTE (codeCorrectionRegressionFeedback)
  // et la boucle le calcule — encore faut-il qu il arrive dans le prompt. C est
  // precisement ce qui manquait: 5 refus consecutifs, 5 fois le meme message.
  test('le verdict du garde arrive dans les messages envoyes au modele', () => {
    const feedback = buildRegressionFeedbackBlock({
      guardReport: 'Regression refusee:\n- removed_file: src/pages/adminDashboard.tsx',
      consecutiveRejections: 2,
      implicatedFiles: ['src/pages/ContactPage.tsx'],
    })
    const messages = buildCorrectionMessages({
      prompt: 'corrige cette app',
      files: [{ name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){return <main />}' }],
      validationResult: sandbox('parse error'),
      strategy,
      researchContext: '',
      missionDossierText: 'Mission stable',
      architecturePlan: null,
      preflightReportText: null,
      intent,
      regressionFeedback: feedback,
    })

    assert.match(messages[0].content, /ANNULEE PAR LE HARNAIS ANTI-REGRESSION/)
    assert.match(messages[1].content, /removed_file: src\/pages\/adminDashboard\.tsx/)
    assert.match(messages[1].content, /PORTEE RESSERREE/)
    assert.match(messages[1].content, /src\/pages\/ContactPage\.tsx/)
  })

  test('sans refus, aucun bruit n est ajoute au prompt', () => {
    const messages = buildCorrectionMessages({
      prompt: 'corrige cette app',
      files: [{ name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){return <main />}' }],
      validationResult: sandbox('parse error'),
      strategy,
      researchContext: '',
      missionDossierText: 'Mission stable',
      architecturePlan: null,
      preflightReportText: null,
      intent,
      regressionFeedback: '',
    })
    assert.doesNotMatch(messages[0].content, /ANTI-REGRESSION/)
    assert.doesNotMatch(messages[1].content, /PORTEE RESSERREE/)
  })
})
