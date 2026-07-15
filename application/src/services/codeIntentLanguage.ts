// ---------------------------------------------------------------------------
// Prompt language detection
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { PromptLanguage } from './codeIntentTypes.ts'

const LANG_SIGNALS: Array<{ lang: PromptLanguage; pattern: RegExp }> = [
  { lang: 'fr', pattern: /\b(le|la|les|un|une|des|pour|avec|mais|plus|aussi|faire|fais|fait|moi|nous|vous|voir|voici|c est|si je|avec un|attirant|sur|dans|page web|site web|voici|qui|pourquoi|comment|parce que|d un|d une)\b/i },
  { lang: 'en', pattern: /\b(the|a|an|and|with|for|please|make|build|create|design|i want|should|could|about|looks|good|awesome|stunning)\b/i },
  { lang: 'es', pattern: /\b(el|la|los|las|una|uno|para|con|pero|hacer|quiero|por favor|pagina|sitio|esto|que|como)\b/i },
  { lang: 'de', pattern: /\b(der|die|das|ein|eine|und|mit|für|bitte|machen|ich möchte|webseite|seite|sollte)\b/i },
  { lang: 'it', pattern: /\b(il|la|lo|gli|le|un|una|per|con|voglio|favore|pagina|sito|fare)\b/i },
  { lang: 'pt', pattern: /\b(o|a|os|as|um|uma|para|com|quero|fazer|favor|pagina|site)\b/i },
]

export function detectPromptLanguage(prompt: string): PromptLanguage {
  // Score each language by how many of its signal words appear.
  const scores: Record<PromptLanguage, number> = { fr: 0, en: 0, es: 0, de: 0, it: 0, pt: 0, unknown: 0 }
  for (const { lang, pattern } of LANG_SIGNALS) {
    const matches = prompt.match(new RegExp(pattern.source, 'gi'))
    scores[lang] = matches ? matches.length : 0
  }
  let best: PromptLanguage = 'unknown'
  let bestScore = 1 // require at least 2 hits to claim a language
  for (const lang of ['fr', 'en', 'es', 'de', 'it', 'pt'] as const) {
    if (scores[lang] > bestScore) {
      best = lang
      bestScore = scores[lang]
    }
  }
  return best
}
