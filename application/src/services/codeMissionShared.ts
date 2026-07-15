// ---------------------------------------------------------------------------
// codeMissionShared — shared types and deterministic helpers for mission control.
// ---------------------------------------------------------------------------

export type MissionFileContext = {
  name: string
  language: string
  content: string
}

export type CodeMissionDossier = {
  objective: string
  requestedDeliverables: string[]
  nonNegotiableConstraints: string[]
  workingAssumptions: string[]
  architectureDirectives: string[]
  validationChecklist: string[]
  antiFailureDirectives: string[]
  reviewFocus: string[]
}

export type CodeDraftReview = {
  score: number
  verdict: 'accept' | 'repair' | 'regenerate'
  summary: string
  strengths: string[]
  criticalIssues: string[]
  missingFiles: string[]
  mustFixBeforeSandbox: string[]
}

export function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

export function shorten(text: string, maxLength = 420) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength)}...`
}

export function summarizeExistingFiles(files: MissionFileContext[]) {
  if (files.length === 0) {
    return 'Aucun fichier existant a conserver.'
  }

  return files
    .slice(0, 10)
    .map((file) => {
      const preview = shorten(file.content, 180)
      return `- ${file.name} (${file.language}) :: ${preview}`
    })
    .join('\n')
}

export function hasFile(files: MissionFileContext[], matcher: RegExp | string) {
  return files.some((file) => {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (typeof matcher === 'string') {
      return normalized === matcher.toLowerCase()
    }
    return matcher.test(normalized)
  })
}

export function isDocumentationFile(name: string) {
  return /\.(md|txt|doc|docx|pdf|rtf)$/i.test(name)
}

function stripFormattingArtifacts(content: string) {
  let current = content
    .replace(/^\uFEFF/, '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()

  for (let index = 0; index < 3; index += 1) {
    const next = current
      .replace(/^```[\w.-]*\s*\r?\n/, '')
      .replace(/\r?\n```$/, '')
      .trim()
    if (next === current) break
    current = next
  }

  return current
}

export function parseJsonSafely(content: string) {
  try {
    return JSON.parse(stripFormattingArtifacts(content)) as Record<string, unknown>
  } catch {
    return null
  }
}

export function serializeCodeMissionDossier(dossier: CodeMissionDossier) {
  return [
    `OBJECTIF_EXECUTIF: ${dossier.objective}`,
    dossier.requestedDeliverables.length > 0
      ? `LIVRABLES_ATTENDUS:\n${dossier.requestedDeliverables.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.nonNegotiableConstraints.length > 0
      ? `CONTRAINTES_DURES:\n${dossier.nonNegotiableConstraints.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.workingAssumptions.length > 0
      ? `HYPOTHESES_AUTONOMES:\n${dossier.workingAssumptions.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.architectureDirectives.length > 0
      ? `DIRECTIVES_ARCHITECTURE:\n${dossier.architectureDirectives.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.validationChecklist.length > 0
      ? `CHECKLIST_VALIDATION:\n${dossier.validationChecklist.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.antiFailureDirectives.length > 0
      ? `GARDE_FOUS_ANTI_ECHEC:\n${dossier.antiFailureDirectives.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.reviewFocus.length > 0
      ? `FOCUS_AUDIT_INTERNE:\n${dossier.reviewFocus.map((item) => `- ${item}`).join('\n')}`
      : '',
  ].filter(Boolean).join('\n\n')
}
