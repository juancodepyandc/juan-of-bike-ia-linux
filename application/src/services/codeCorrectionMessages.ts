import type { OllamaMessage } from '../types/app'
import type { CodeIntent } from './codeIntent.ts'
import type { CorrectionStrategy } from './codeAutoCorrection.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { buildAuditeurSystemPrompt } from './codeSystemPrompts.ts'
import { evaluateBrandFidelity } from './codeFidelityGate.ts'
import { serializeCodeFiles } from './codeGeneratedFileParser.ts'
import {
  buildDesignRetryHint,
  computeDesignPolishReport,
} from './codeQualityGates.ts'
import { isTypeScriptCompatibilityFailure } from './codeProjectValidation.ts'
import { clipText } from './codePipelineRuntime.ts'

export function buildCorrectionMessages({
  prompt,
  files,
  validationResult,
  strategy,
  researchContext,
  reasoningContext,
  missionDossierText,
  architecturePlan,
  preflightReportText,
  intent,
}: {
  prompt: string
  files: CodeFile[]
  validationResult: CodeSandboxResult
  strategy: CorrectionStrategy
  researchContext: string
  reasoningContext?: string
  missionDossierText: string
  architecturePlan: string | null
  preflightReportText: string | null
  intent: CodeIntent
}): OllamaMessage[] {
  const failingSteps = validationResult.steps
    .filter((step) => !step.ok)
    .slice(0, 5)
    .map((step) => [
      `Step: ${step.label}`,
      `Command: ${step.command}`,
      `Output: ${clipText(step.output || 'aucune sortie exploitable')}`,
    ].join('\n'))
    .join('\n\n')

  const systemLines = [
    buildAuditeurSystemPrompt(),
    '',
    '---',
    '',
    `Strategie: ${strategy.level} (escalation ${strategy.escalation})`,
    `Cause dominante: ${strategy.cause}`,
    `Localite probable: ${strategy.locality}`,
    `Historique: stagnation=${strategy.history.stagnating ? 'oui' : 'non'}, repetition=${strategy.history.repeatedErrorCount}, budget=${strategy.history.adaptiveBudget}`,
    `Instructions: ${strategy.instructions}`,
    '',
    'Avant de toucher au code applicatif, determine si l echec vient du code, d une config locale manquante, d un script faux, d une incompatibilite de version, d un type moderne ou d un runtime absent.',
    'Si le projet utilise TypeScript, verifie d abord tsconfig.json, la version de typescript, les options du compilateur et les types installes.',
    'Ajoute ou corrige les fichiers de configuration locaux obligatoires quand ils manquent, au lieu d heriter implicitement d un dossier parent.',
    'Conserve les fichiers qui n ont pas besoin de changer.',
    'Interdiction de faire passer la validation en supprimant une fonctionnalite, un test, une doc, un script, un export public ou un endpoint existant.',
  ]

  if (/package\.json|json valide|actual JSON|EJSONPARSE|JSONParseError/i.test(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE ABSOLUE:',
      '- Corrige les fichiers JSON machine avant toute autre chose.',
      '- package.json doit etre un JSON strict, sans ```json, sans commentaires, sans explication autour.',
    )
  }

  if (isTypeScriptCompatibilityFailure(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE COMPATIBILITE TYPESCRIPT:',
      '- Cherche une incompatibilite entre la version de typescript, tsconfig.json et les declarations .d.ts installees.',
      '- Si typescript est trop ancien pour les types/config actuels, monte la version du compilateur a un niveau compatible.',
      '- Si tsconfig.json manque, cree une configuration locale explicite au lieu de laisser tsc remonter dans les dossiers parents.',
    )
  }

  if (strategy.level === 'rewrite' || strategy.level === 'strategy_change') {
    systemLines.push(
      '',
      'ATTENTION: Les corrections precedentes ont echoue.',
      strategy.level === 'strategy_change'
        ? 'Change d angle de diagnostic, mais conserve la stack, les contrats publics et le perimetre fonctionnel sauf incompatibilite locale prouvee.'
        : 'Reecris les fichiers problematiques completement. Ne te contente pas de patcher.',
    )
  }

  const userLines = [
    `Mission originale:\n${prompt}`,
    `Le sandbox a echoue:\n${validationResult.summary}`,
    failingSteps ? `Erreurs:\n${failingSteps}` : '',
    `Dossier executif:\n${missionDossierText}`,
    architecturePlan ? `Plan d architecture de reference:\n${clipText(architecturePlan, 2200)}` : '',
    preflightReportText ? `Preflight local:\n${preflightReportText}` : '',
  ]

  if (researchContext) {
    userLines.push(`\nSolutions trouvees en ligne:\n${researchContext}`)
  }

  if (reasoningContext) {
    userLines.push(`\n${reasoningContext}`)
  }

  const isVisual = files.length > 0 && files.some((file) => /\.(html?|css|s?css|tsx?|jsx?|vue|svelte)$/i.test(file.name))
  if (isVisual) {
    const designReport = computeDesignPolishReport(files)
    if (designReport.score < 70) {
      userLines.push('', buildDesignRetryHint(designReport))
    }
  }

  const brandSubject = intent.assetPlan?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const brandReport = evaluateBrandFidelity(intent, files)
    if (brandReport.shouldRetry || brandReport.scorePenalty >= 15 || brandReport.scoreCap !== null) {
      const hintBlock = [
        '## RAPPEL VERROUILLAGE SUJET (FIDELITE BRAND ECHOUEE)',
        '',
        `Le sujet de cette page est ${brandSubject.canonical}. La gate de fidelite a detecte ces violations:`,
        brandReport.retryHint || '(pas de detail)',
        '',
        'A appliquer dans cette passe de correction:',
        `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, <h1> du hero, et au moins 3 sections.`,
        brandSubject.brandProfile.primaryColor ? `- La couleur ${brandSubject.brandProfile.primaryColor} doit etre presente dans les CSS variables et utilisee pour les CTAs/accents.` : '',
        brandSubject.brandProfile.productKeywords.length ? `- Au moins 2 mots-cles produit (${brandSubject.brandProfile.productKeywords.slice(0, 4).join(', ')}) doivent apparaitre dans les titres ou paragraphes.` : '',
        '- Les markers PLACEHOLDER_SUBJECT_IMG / _1 / _2 doivent etre utilises dans les balises <img>.',
        '- Pas de derive vers un sujet adjacent (restaurant generique, blog editorial, SaaS abstrait).',
      ].filter(Boolean).join('\n')
      userLines.push('', hintBlock)
    }
  }

  userLines.push(
    '',
    'Corrige le projet complet. Modifie seulement ce qui est necessaire.',
    `\nFichiers actuels:\n${serializeCodeFiles(files)}`,
  )

  return [
    { role: 'system', content: systemLines.join('\n') },
    { role: 'user', content: userLines.filter(Boolean).join('\n\n') },
  ]
}
