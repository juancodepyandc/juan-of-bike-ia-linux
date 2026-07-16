import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import {
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
} from './codeQualityGates.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import { compositeStaticCritic } from './codeStaticCritics.ts'
import { withStaticCritiqueStep } from './codeValidationScoring.ts'
import { INTERACTIVE_3D_FIDELITY_MAX_PASSES } from './codePipelineRuntime.ts'
import { detectDesignArchetype } from './codeDesignDirectives.ts'
import { buildCodeDesignSpec, formatCodeDesignSpecPrompt, verifyCodeDesignSpecAgainstFiles } from './codeDesignSpec.ts'

// WS10: on ne fait respecter la design-spec que sur les premieres passes, pour
// nudger la conformite sans bloquer la convergence sur des ecarts mineurs.
const DESIGN_SPEC_MAX_PASSES = 2

function appendFailedGate(
  result: CodeSandboxResult,
  summary: string,
  label: string,
  command: string,
  output: string,
): CodeSandboxResult {
  return {
    ...result,
    ok: false,
    summary: result.ok ? summary : `${result.summary}\n${summary}`,
    steps: [...result.steps, { label, command, ok: false, output }],
  }
}

export async function runCorrectionQualityGates({
  result,
  files,
  prompt,
  intent,
  attempt,
  setPhase,
}: {
  result: CodeSandboxResult
  files: CodeFile[]
  prompt: string
  intent: CodeIntent
  attempt: number
  setPhase: PhaseCallback
}): Promise<CodeSandboxResult> {
  setPhase(`Sandbox passe ${attempt} - critique statique du code...`, Math.min(90, 66 + attempt * 4))
  const staticReport = await compositeStaticCritic({
    generationId: `validation-${attempt}`,
    files,
  }, intent)
  let nextResult = withStaticCritiqueStep(result, staticReport)

  const interactive3D = checkInteractive3DFidelity(files, prompt, intent)
  if (!interactive3D.ok && attempt <= INTERACTIVE_3D_FIDELITY_MAX_PASSES) {
    nextResult = appendFailedGate(
      nextResult,
      'La fidelite 3D interactive demandee est incomplete.',
      'Fidelite 3D interactive',
      'interactive-3d-fidelity-gate',
      interactive3D.hint,
    )
    setPhase(
      `Passe ${attempt} - fidelite 3D incomplete (${interactive3D.missing.join(', ')})...`,
      Math.min(90, 68 + attempt * 4),
    )
  }

  if (intent.projectType === 'game_web') {
    const gamePlay = checkGamePlayability(files, prompt)
    if (!gamePlay.ok) {
      nextResult = appendFailedGate(
        nextResult,
        `Jeu incomplet: ${gamePlay.missing.join(', ')}.`,
        'Jouabilité',
        'playability-gate',
        gamePlay.hint,
      )
      setPhase(
        `Passe ${attempt} - jeu incomplet (${gamePlay.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }
  }

  // WS10: la design-spec est un CONTRAT verifie contre le code livre (palette
  // deltaE, tokens, composants, wireframe, et surtout coherence de plateforme:
  // pas de contrat CSS web applique a du mobile natif ni a un jeu canvas). Un
  // ecart declenche une correction ciblee avec la spec en indice.
  if (attempt <= DESIGN_SPEC_MAX_PASSES) {
    const designSpec = buildCodeDesignSpec(prompt, intent, detectDesignArchetype(prompt, intent))
    const designCheck = verifyCodeDesignSpecAgainstFiles(designSpec, files)
    if (!designCheck.ok) {
      const hint = [
        'La livraison doit respecter la design-spec (contrat verifiable ci-dessous). Ecarts detectes:',
        ...designCheck.issues.map((issue) => `- ${issue.kind}: ${issue.detail}`),
        '',
        formatCodeDesignSpecPrompt(designSpec),
      ].join('\n')
      nextResult = appendFailedGate(
        nextResult,
        `Ecart design-spec (${[...new Set(designCheck.issues.map((issue) => issue.kind))].join(', ')}).`,
        'Design-spec',
        'design-spec-gate',
        hint,
      )
      setPhase(
        `Passe ${attempt} - ecart design-spec (${designCheck.issues.length} point(s)) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }
  }

  if (intent.projectType === 'static_web') {
    const webIntegrity = checkWebPageIntegrity(files, prompt)
    if (!webIntegrity.ok) {
      nextResult = appendFailedGate(
        nextResult,
        `Page non fonctionnelle: ${webIntegrity.missing.join(', ')}.`,
        'Intégrité page',
        'web-integrity-gate',
        webIntegrity.hint,
      )
      setPhase(
        `Passe ${attempt} - page non fonctionnelle (${webIntegrity.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }
  }

  return nextResult
}
