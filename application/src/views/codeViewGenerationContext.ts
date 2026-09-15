import type { Dispatch, SetStateAction } from 'react'
import type { ClarificationRequest } from '../components/ClarificationDialog.tsx'
import {
  buildAutonomousAssumption,
  classifyClarificationSeverity,
} from '../services/codeOrchestrator.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import { prepareTaskIntelligence } from '../services/taskIntelligence.ts'
import { prepareContextFiles } from '../utils/multimodalContext.ts'

export async function prepareCodeViewTaskContext({
  activePrompt,
  activeModel,
  visionModel,
  contextFiles,
  setPhase,
  setProgress,
  setClarification,
}: {
  activePrompt: string
  activeModel: string
  visionModel: string
  contextFiles: File[]
  setPhase: (detail: string, progress: number) => void
  setProgress: Dispatch<SetStateAction<string>>
  setClarification: Dispatch<SetStateAction<ClarificationRequest | null>>
}) {
  const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
  setProgress('Analyse de la demande...')
  const taskContext = await prepareTaskIntelligence({
    module: 'code',
    prompt: activePrompt,
    model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
    files: preparedContext,
    setPhase,
    phaseBase: 2,
    phaseSpan: 8,
  })

  if (taskContext.clarificationQuestion) {
    const earlyIntent = classifyCodeIntent(activePrompt)
    const severity = classifyClarificationSeverity(
      taskContext.clarificationQuestion,
      earlyIntent,
      activePrompt,
    )

    if (severity === 'critical') {
      setPhase('Clarification critique requise.', 12)
      const userAnswer = await new Promise<string | null>((resolve) => {
        setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
      })
      setClarification(null)
      if (userAnswer) {
        taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
        taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`
      } else {
        const assumption = buildAutonomousAssumption(activePrompt, earlyIntent)
        taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nHypotheses autonomes (utilisateur a passe la clarification):\n${assumption}`
      }
    } else if (severity === 'optional') {
      const assumption = buildAutonomousAssumption(activePrompt, earlyIntent)
      taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nHypotheses autonomes du module (choix par defaut documente):\n${assumption}`
      taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nAutonomous assumptions:\n${assumption}`
    }
  }

  const userFileDataUrls: Record<string, string> = {}
  for (const [index, file] of preparedContext.entries()) {
    if (file.imageBase64) {
      userFileDataUrls[`USER_FILE_${index}`] = `data:image/jpeg;base64,${file.imageBase64}`
    }
  }

  if (preparedContext.length > 0) {
    taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\n${buildUserFilesSection(preparedContext)}`
  }

  return { preparedContext, taskContext, userFileDataUrls }
}

function buildUserFilesSection(
  preparedContext: Awaited<ReturnType<typeof prepareContextFiles>>,
): string {
  const lines = [
    '## FICHIERS FOURNIS PAR L UTILISATEUR (a integrer fidelement)',
    '- Ces fichiers sont joints au prompt. Tu DOIS comprendre leur role et les incorporer.',
    '- Images → utilise-les comme <img src="USER_FILE_<id>"> (placeholder) — elles seront injectees au build en data URL.',
    '- CSS → fusionne leurs regles dans ta feuille de styles (conserve la palette/typographie qui y figure).',
    '- JSON → utilise leurs donnees pour remplir la page (products, faqs, testimonials, features, etc.).',
    '- Texte / Markdown → traite leur contenu comme le copywriting attendu dans la page.',
    '',
  ]
  for (const [index, file] of preparedContext.entries()) {
    const id = `USER_FILE_${index}`
    if (file.kind === 'image') {
      lines.push(`### ${file.name} — IMAGE (${file.kind})`)
      lines.push(`  Reference prompt: ${id}`)
      lines.push(`  Consigne: remplace les visuels adaptes par <img src="${id}" alt="...">.`)
      continue
    }

    const extension = file.name.split('.').pop()?.toLowerCase() || ''
    const role = extension === 'css' || extension === 'scss' ? 'FEUILLE DE STYLE A FUSIONNER'
      : extension === 'json' ? 'DONNEES JSON A UTILISER DANS LA PAGE'
        : extension === 'md' || extension === 'markdown' ? 'COPY EDITORIAL'
          : extension === 'html' || extension === 'htm' ? 'FRAGMENT HTML A INTEGRER'
            : 'CONTEXTE TEXTE'
    lines.push(`### ${file.name} — ${role}`)
    const excerpt = (file.extractedText || '').slice(0, 2500)
    if (excerpt) lines.push('```', excerpt, '```')
  }
  return lines.join('\n')
}
