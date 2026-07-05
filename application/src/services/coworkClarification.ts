export type CoworkConversationTurn = {
  role: 'user' | 'aurora'
  content: string
}

export type ResolvedClarification = {
  originalRequest: string
  clarificationQuestion: string
  clarificationAnswer: string
}

const CLARIFICATION_QUESTION_RE = /(\?|precis|souhait|veux|voulez|lequel|laquelle|choix|choisir|confirme|option|physique|informatique|bureau|officiel|theorique|complementaire|eduscol|ressource)/i
const ACTION_REQUEST_RE = /\b(analyse|analyser|resume|resumer|fiche|recap|liste|lister|trouve|cherche|recherche|lis|ouvre|modifie|cree|scan|verifie|telecharge|connecte|scrape|bureau|dossier|fichier|site|page|pc|ordinateur|workspace|espace|pdf|tp|bac|annale|sujet)\b/i
const SHORT_CLARIFICATION_RE = /^(oui|non|ok|d'accord|dac|plutot|celui|celle|ca|ceci|cela|le premier|la premiere|le second|la seconde|informatique|physique|espace informatique|bureau informatique|ordinateur|pc|fichiers?|dossiers?|workspace|navigateur|site|page|officiel|officiels|officielle|officielles|eduscol|theorique|theoriques|ressources? officielles?)\b/i

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function compact(text: string, max = 260): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max - 1)}...` : clean
}

export function resolveClarificationContinuation(
  userPrompt: string,
  conversationHistory: CoworkConversationTurn[] | undefined,
): ResolvedClarification | null {
  const current = userPrompt.trim()
  if (!current || !conversationHistory?.length) return null

  const turns = conversationHistory
    .map((turn) => ({
      role: turn.role,
      content: (turn.content || '').trim(),
    }))
    .filter((turn) => turn.content.length > 0)

  const currentNorm = normalize(current)
  while (turns.length > 0) {
    const last = turns[turns.length - 1]
    if (last.role !== 'user' || normalize(last.content) !== currentNorm) break
    turns.pop()
  }

  const likelyShortAnswer = current.length <= 140 || SHORT_CLARIFICATION_RE.test(normalize(current))
  if (!likelyShortAnswer) return null

  let questionIndex = -1
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const turn = turns[i]
    if (turn.role === 'user') continue
    if (CLARIFICATION_QUESTION_RE.test(normalize(turn.content))) {
      questionIndex = i
      break
    }
  }
  if (questionIndex < 0) return null

  const originalCandidates: Array<{ index: number; content: string }> = []
  for (let i = questionIndex - 1; i >= 0; i -= 1) {
    if (turns[i].role === 'user') {
      const content = turns[i].content
      if (ACTION_REQUEST_RE.test(normalize(content))) {
        originalCandidates.push({ index: i, content })
      }
    }
  }

  const original = pickOriginalRequestCandidate(originalCandidates)
  if (!original) return null

  return {
    originalRequest: original.content,
    clarificationQuestion: turns[questionIndex].content,
    clarificationAnswer: current,
  }
}

function pickOriginalRequestCandidate(
  candidates: Array<{ index: number; content: string }>,
): { index: number; content: string } | null {
  if (candidates.length === 0) return null
  const artifact = candidates
    .slice()
    .sort((a, b) => a.index - b.index)
    .find((candidate) => /\b(pdf|excel|xlsx|docx|fiche|rapport|site|app|script|projet|cree|creer|genere|produis|produire)\b/i.test(normalize(candidate.content)))
  return artifact ?? candidates[0]
}

export function buildClarificationContinuationHint(
  userPrompt: string,
  conversationHistory: CoworkConversationTurn[] | undefined,
): string {
  const resolved = resolveClarificationContinuation(userPrompt, conversationHistory)
  if (!resolved) return ''

  return [
    '## Clarification utilisateur detectee',
    `Le dernier message utilisateur ("${compact(resolved.clarificationAnswer)}") repond a une question de clarification d Aurora: "${compact(resolved.clarificationQuestion)}".`,
    `Demande originale a reprendre: "${compact(resolved.originalRequest)}".`,
    `Objectif fusionne: "${compact(resolved.originalRequest)}" + precision utilisateur: "${compact(resolved.clarificationAnswer)}".`,
    'Regle: traite ce tour comme une reprise d action. Ne donne pas une definition du terme de clarification. Planifie les actions necessaires pour accomplir la demande originale clarifiee.',
  ].join('\n')
}
