// ---------------------------------------------------------------------------
// Prompt subject detection
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { SubjectDetection } from './codeIntentTypes.ts'
import { CONCRETE_OBJECT_TOKENS } from './codeIntentAssetTokens.ts'
import { BRAND_DICTIONARY } from './codeIntentBrandProfiles.ts'
import { GAME_SIGNALS } from './codeIntentSignals.ts'
import { containsAnySignal, containsSignal, normalizeSignalText } from './codeIntentSignalUtils.ts'

const INFERRED_BRAND_STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des',
  'page', 'site', 'projet', 'application', 'app', 'jeu', 'game', 'logiciel',
  'crée', 'cree', 'creer', 'fais', 'faire', 'génère', 'genere', 'generer',
  'construis', 'construire', 'design', 'develop', 'develope', 'devoper', 'design',
  'coca', 'tesla', 'apple', 'nike', 'spotify', // already caught by dict, just safety
  'create', 'build', 'make', 'design', 'generate', 'develop',
  'web', 'mobile', 'desktop', 'cli', 'api',
  'ultra', 'pro', 'premium', 'simple', 'minimal',
  // Common capitalised words that start a clause but are NOT brands. Without
  // these, "Plusieurs plateformes", "Chaque niveau", "Ajoute un score"… get
  // mistaken for a brand and pollute the subject-lock.
  'plusieurs', 'chaque', 'certains', 'certaines', 'tous', 'toutes', 'tout', 'toute',
  'quelques', 'aucun', 'aucune', 'beaucoup', 'autre', 'autres', 'meme', 'memes',
  'voici', 'voila', 'ajoute', 'ajouter', 'ensuite', 'aussi', 'enfin', 'donc',
  'quand', 'lorsque', 'pendant', 'avec', 'dans', 'pour', 'sans', 'leur', 'leurs',
  'joueur', 'jeu', 'partie', 'niveau', 'niveaux', 'ecran', 'bouton', 'menu',
  'bonjour', 'salut', 'merci',
  'several', 'each', 'every', 'some', 'many', 'another', 'other', 'others',
  'when', 'while', 'then', 'also', 'here', 'there', 'this', 'that', 'these', 'those',
  'add', 'include', 'player', 'level', 'score', 'screen', 'button', 'hello',
])

/**
 * Detect a brand-like name by simple heuristic: a capitalised noun (1-3 tokens) that
 * doesn't match a stopword. The prompt "page de présentation pour Lipton" yields "Lipton".
 * Used as the LAST resort, AFTER the brand dictionary and the quoted-phrase rule.
 */
function detectInferredBrand(prompt: string): { canonical: string; raw: string } | null {
  // 1-3 capitalised words, possibly hyphenated. Anchored to a word boundary on both sides.
  const re = /\b([A-Z][a-z]{2,}(?:[- ][A-Z][a-z]+){0,2})\b/g
  const matches = Array.from(prompt.matchAll(re))
  for (const m of matches) {
    const phrase = m[1].trim()
    const firstWord = phrase.split(/[-\s]/)[0].toLowerCase()
    if (INFERRED_BRAND_STOPWORDS.has(firstWord)) continue
    if (firstWord.length < 3) continue
    // v89b: skip SENTENCE-INITIAL capitalised words. A capital at the start of
    // the prompt or right after . ! ? : ; / newline / a bullet is grammatical,
    // not a brand. "...sans backend. Exigences fonctionnelles :" used to extract
    // "Exigences" as an inferred brand and fire a useless Wikipedia+Ollama
    // enrich (and, worse, a subject-lock contradicting the real request — the
    // same class of bug as the "Plusieurs" incident). A real mid-sentence brand
    // ("page pour Lipton") is still detected; famous brands are caught earlier
    // by the dictionary, and any leading brand can be forced with quotes.
    const before = prompt.slice(0, m.index ?? 0)
    if (/(^|[.!?:;\n\r/]|^\s*[-•*])\s*$/.test(before)) continue
    return { canonical: phrase, raw: phrase }
  }
  return null
}

export function detectSubject(prompt: string): SubjectDetection {
  // 1) Brand dictionary wins — those are unambiguous and must never be mistranslated.
  for (const entry of BRAND_DICTIONARY) {
    if (entry.token.test(prompt)) {
      return {
        canonical: entry.canonical,
        domain: entry.domain,
        source: 'brand',
        raw: prompt.match(entry.token)?.[0] ?? entry.canonical,
        brandProfile: entry.profile,
      }
    }
  }
  // 2) First quoted phrase if any.
  const quoted = prompt.match(/["'«»]([^"'«»]{2,60})["'«»]/)
  if (quoted && quoted[1]) {
    return { canonical: quoted[1].trim(), domain: null, source: 'quoted', raw: quoted[0] }
  }
  // 3) First concrete noun from the dictionary.
  const lower = normalizeSignalText(prompt)
  for (const token of CONCRETE_OBJECT_TOKENS) {
    if (containsSignal(lower, token)) {
      return { canonical: token, domain: null, source: 'object', raw: token }
    }
  }
  // Inferred brand: capitalize noun → /api/brand/enrich fetches palette/keywords/shape from Wikipedia + Ollama.
  //
  // GUARD: NEVER infer a brand for a game request. The prompt "jeu de plateforme …
  // Plusieurs plateformes …" used to extract "Plusieurs" as a brand and inject a
  // subject-lock ("le mot Plusieurs DOIT figurer dans le <title>/<h1>, c'est une
  // marque réelle") that directly contradicts the game contract and derails
  // generation (broken, simplistic output). A game has no brand subject unless one
  // is named in the dictionary (already handled above). Same reasoning protects
  // any build whose subject is a generic capitalised word, not a real brand.
  const isGamePrompt = containsAnySignal(normalizeSignalText(prompt), GAME_SIGNALS)
  if (!isGamePrompt) {
    const inferred = detectInferredBrand(prompt)
    if (inferred) {
      return {
        canonical: inferred.canonical,
        domain: null,
        source: 'inferred_brand',
        raw: inferred.raw,
      }
    }
  }
  return { canonical: null, domain: null, source: 'none', raw: '' }
}
