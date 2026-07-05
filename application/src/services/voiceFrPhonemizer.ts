// Phonemizer FR par règles — convertit du texte français en séquence IPA
// (puis en visèmes via la map du module voicePhonemes).
//
// Approche : ce n'est PAS eSpeak NG / Phonemizer (deps trop lourdes). C'est
// un rule-based "Lexique3-flavored" qui couvre les digraphes/trigraphes les
// plus fréquents de la langue française. Couverture cible : ~85 % des mots
// courants. Pas parfait sur les liaisons et l'élision, mais bien suffisant
// pour un lipsync d'idle talking-head.
//
// Tests de couverture : sur le corpus "bonjour, comment ça va, je suis prof"
// on doit obtenir ≥ 90 % de phonèmes corrects vs prononciation académique.

import { FR_PHONEME_TABLE, phonemeToViseme, type VisemeKeyframe } from './voicePhonemes.ts'

type Rule = {
  /** Pattern recherché (NFD lower-case). */
  pattern: string
  /** Phonème IPA produit. */
  ipa: string
  /** Contexte qui doit suivre (regex). Optionnel. */
  followedBy?: RegExp
  /** Contexte qui doit précéder (regex). Optionnel. */
  precededBy?: RegExp
}

// Ordre IMPORTANT : longs patterns d'abord (greedy match-first).
//
// Couvre les patterns FR les plus fréquents. Pour des cas exotiques
// (gn dans "examiner", "gn" dans "stagner") on accepte une légère
// imprécision — l'objectif est le lipsync, pas la transcription.
const RULES: readonly Rule[] = [
  // Trigraphes
  { pattern: 'eau', ipa: 'o' },
  { pattern: 'aux', ipa: 'o' },
  { pattern: 'oin', ipa: 'wɛ̃' },
  { pattern: 'ien', ipa: 'jɛ̃' },
  { pattern: 'ail', ipa: 'aj' },
  { pattern: 'eil', ipa: 'ɛj' },
  { pattern: 'ouil', ipa: 'uj' },

  // Digraphes voyelles
  { pattern: 'au', ipa: 'o' },
  { pattern: 'eu', ipa: 'ø' },
  { pattern: 'oe', ipa: 'œ' },
  { pattern: 'ou', ipa: 'u' },
  { pattern: 'ai', ipa: 'ɛ' },
  { pattern: 'ei', ipa: 'ɛ' },
  { pattern: 'oi', ipa: 'wa' },
  { pattern: 'ui', ipa: 'ɥi' },

  // Nasales
  { pattern: 'on', ipa: 'ɔ̃', followedBy: /^(?:[^aeiouy]|$)/ },
  { pattern: 'an', ipa: 'ɑ̃', followedBy: /^(?:[^aeiouy]|$)/ },
  { pattern: 'en', ipa: 'ɑ̃', followedBy: /^(?:[^aeiouy]|$)/ },
  { pattern: 'in', ipa: 'ɛ̃', followedBy: /^(?:[^aeiouy]|$)/ },
  { pattern: 'un', ipa: 'œ̃', followedBy: /^(?:[^aeiouy]|$)/ },
  { pattern: 'am', ipa: 'ɑ̃', followedBy: /^(?:[bp]|$)/ },
  { pattern: 'om', ipa: 'ɔ̃', followedBy: /^(?:[bp]|$)/ },
  { pattern: 'im', ipa: 'ɛ̃', followedBy: /^(?:[bp]|$)/ },

  // Consonnes digraphes
  { pattern: 'ch', ipa: 'ʃ' },
  { pattern: 'ph', ipa: 'f' },
  { pattern: 'th', ipa: 't' },
  { pattern: 'gn', ipa: 'ɲ' },
  { pattern: 'qu', ipa: 'k' },
  { pattern: 'gu', ipa: 'ɡ', followedBy: /^[ei]/ },

  // Consonnes courantes
  { pattern: 's', ipa: 'z', precededBy: /[aeiouy]$/, followedBy: /^[aeiouy]/ }, // intervocalique
  { pattern: 'c', ipa: 's', followedBy: /^[eiy]/ },
  { pattern: 'c', ipa: 'k' },
  { pattern: 'g', ipa: 'ʒ', followedBy: /^[eiy]/ },
  { pattern: 'g', ipa: 'ɡ' },

  // Voyelles simples (la dernière chance)
  { pattern: 'é', ipa: 'e' },
  { pattern: 'è', ipa: 'ɛ' },
  { pattern: 'ê', ipa: 'ɛ' },
  { pattern: 'à', ipa: 'a' },
  { pattern: 'â', ipa: 'ɑ' },
  { pattern: 'î', ipa: 'i' },
  { pattern: 'ï', ipa: 'i' },
  { pattern: 'ô', ipa: 'o' },
  { pattern: 'ù', ipa: 'y' },
  { pattern: 'û', ipa: 'y' },
  { pattern: 'a', ipa: 'a' },
  { pattern: 'e', ipa: 'ə' },
  { pattern: 'i', ipa: 'i' },
  { pattern: 'o', ipa: 'o' },
  { pattern: 'u', ipa: 'y' },
  { pattern: 'y', ipa: 'i' },

  // Consonnes simples
  { pattern: 'b', ipa: 'b' },
  { pattern: 'd', ipa: 'd' },
  { pattern: 'f', ipa: 'f' },
  { pattern: 'h', ipa: '' }, // muet
  { pattern: 'j', ipa: 'ʒ' },
  { pattern: 'k', ipa: 'k' },
  { pattern: 'l', ipa: 'l' },
  { pattern: 'm', ipa: 'm' },
  { pattern: 'n', ipa: 'n' },
  { pattern: 'p', ipa: 'p' },
  { pattern: 'r', ipa: 'ʁ' },
  { pattern: 's', ipa: 's' },
  { pattern: 't', ipa: 't' },
  { pattern: 'v', ipa: 'v' },
  { pattern: 'w', ipa: 'w' },
  { pattern: 'x', ipa: 'ks' },
  { pattern: 'z', ipa: 'z' },
]

// Pre-keep accented vowels (don't strip them before rule matching).
const ACCENTS_KEPT = new Set(['é', 'è', 'ê', 'à', 'â', 'î', 'ï', 'ô', 'ù', 'û'])

function preprocess(text: string): string {
  let out = ''
  for (const ch of text.toLowerCase()) {
    if (ACCENTS_KEPT.has(ch)) {
      out += ch
      continue
    }
    // Strip other diacritics.
    const decomposed = ch.normalize('NFD')
    const stripped = decomposed.replace(/[̀-ͯ]/g, '')
    out += stripped
  }
  return out
}

/**
 * Phonemize a single French word. Returns the IPA string (joined phonemes).
 * Silent final consonants are NOT dropped — for lipsync we want the closure.
 */
export function phonemizeWord(word: string): string[] {
  const text = preprocess(word.trim())
  if (text.length === 0) return []
  const phones: string[] = []
  let i = 0
  while (i < text.length) {
    let matched = false
    for (const rule of RULES) {
      const len = rule.pattern.length
      if (text.slice(i, i + len) !== rule.pattern) continue
      if (rule.followedBy && !rule.followedBy.test(text.slice(i + len))) continue
      if (rule.precededBy && !rule.precededBy.test(text.slice(0, i))) continue
      if (rule.ipa.length > 0) phones.push(rule.ipa)
      i += len
      matched = true
      break
    }
    if (!matched) {
      // Caractère imprévu (apostrophe, ponctuation, etc.) — on saute.
      i += 1
    }
  }
  return phones
}

/**
 * Phonemize an entire FR sentence. Words split on whitespace and punctuation.
 */
export function phonemizeSentence(text: string): string[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: string[] = []
  for (const w of words) {
    const phones = phonemizeWord(w)
    out.push(...phones)
  }
  return out
}

const FR_DURATIONS = new Map<string, number>(FR_PHONEME_TABLE.map((p) => [p.ipa, p.defaultDurationMs]))

// --- Adapter pour le viseme set de AuroraAvatar -----------------------------
// L'Avatar utilise {silence, aa, ee, ii, oo, uu, mm, ff, ss, sh, pp, nn}
// (12 visèmes). On expose un mapping IPA → avatar viseme pour pouvoir
// alimenter l'avatar directement depuis le phonemizer rule-based.

export type AvatarViseme = 'silence' | 'aa' | 'ee' | 'ii' | 'oo' | 'uu' | 'mm' | 'ff' | 'ss' | 'sh' | 'pp' | 'nn'

const IPA_TO_AVATAR: Record<string, AvatarViseme> = {
  // Voyelles ouvertes
  a: 'aa', ɑ: 'aa', 'ɑ̃': 'aa', 'ɛ̃': 'aa',
  // Voyelles fermées avant
  i: 'ii', y: 'ii', j: 'ii',
  // E
  e: 'ee', ɛ: 'ee',
  // O / ON
  o: 'oo', ɔ: 'oo', 'ɔ̃': 'oo',
  // OU
  u: 'uu', ø: 'uu', œ: 'uu', 'œ̃': 'uu', ə: 'uu', 'ɥ': 'uu', w: 'uu',
  // Bilabiales
  p: 'pp', b: 'pp', t: 'pp', d: 'pp', k: 'pp', ɡ: 'pp',
  // Nasales
  m: 'mm', n: 'nn', ɲ: 'nn', ŋ: 'nn', l: 'nn', ʁ: 'nn',
  // Fricatives labiales
  f: 'ff', v: 'ff',
  // Sifflantes
  s: 'ss', z: 'ss',
  // Postalvéolaires
  ʃ: 'sh', ʒ: 'sh',
  // Th (rare)
  θ: 'ss',
}

export type AvatarPhonemeFrame = { viseme: AvatarViseme; duration: number; stress: number }

/**
 * Convertit une phrase FR en timeline phoneme/viseme adaptée au viseme set
 * de AuroraAvatar (12 visèmes). À utiliser comme remplacement direct du
 * textToPhonemeTimeline ad-hoc de AuroraAvatar.tsx.
 *
 * Différences vs l'ancien :
 *   - Détecte les nasales (ɑ̃, ɛ̃, ɔ̃) via contexte (voyelle + n/m + consonne).
 *   - "ch", "ph", "qu" pris en compte explicitement.
 *   - R uvulaire FR (ʁ) routé sur 'nn' (langue contre palais).
 *   - Durées par IPA (table FR_PHONEME_TABLE), pas durée fixe.
 *   - Silence ajouté seulement entre mots, pas après chaque syllabe.
 */
export function textToPhonemeTimelineV2(text: string): AvatarPhonemeFrame[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: AvatarPhonemeFrame[] = []
  for (const w of words) {
    const phones = phonemizeWord(w)
    if (phones.length === 0) continue
    for (const ph of phones) {
      const viseme = IPA_TO_AVATAR[ph] ?? 'silence'
      const baseDur = FR_DURATIONS.get(ph) ?? 70
      const isVowel = ['aa', 'ee', 'ii', 'oo', 'uu'].includes(viseme)
      out.push({ viseme, duration: baseDur, stress: isVowel ? 0.8 : 0.5 })
    }
    out.push({ viseme: 'silence', duration: 60, stress: 0 })
  }
  return out
}

// --- Liaisons FR ------------------------------------------------------------
//
// La liaison réalise une consonne finale normalement muette quand le mot
// suivant commence par une voyelle. C'est un trait essentiel pour un lipsync
// crédible : sans liaison, "les enfants" produit un visème de pause là où en
// vrai on prononce un /z/ ligaturé.
//
// Règles obligatoires couvertes ici :
//   - articles définis pluriel : les/des/aux/mes/tes/ses/ces/nos/vos/leurs + voyelle → +/z/
//   - adjectifs prénominaux : grand/petit/bon/mauvais + voyelle → +/t/ (grand→/d/→/t/ devant V)
//   - pronoms : on/en/ils/elles/nous/vous + voyelle → +/n/ ou +/z/
//   - prépositions monosyllabiques : sans/dans/en/sous + voyelle
//   - "est" + voyelle → +/t/
//
// Liaisons facultatives (style soutenu) : non couvertes — gardent le mot tel quel.

const VOWEL_STARTS = /^[aeiouyâàäéèêëîïôùûüœæh]/i

const LIAISON_RULES: Array<{ word: RegExp; liaisonIpa: string }> = [
  // Articles + déterminants pluriel → /z/
  { word: /^(les|des|aux|mes|tes|ses|ces|nos|vos|leurs|quels|quelles|certains|certaines|plusieurs)$/i, liaisonIpa: 'z' },
  // Pronoms personnels → /z/ (nous/vous/ils/elles/ces/les)
  { word: /^(nous|vous|ils|elles)$/i, liaisonIpa: 'z' },
  // on/en → /n/
  { word: /^(on|en|un|aucun|bien|rien|non|son|ton|mon)$/i, liaisonIpa: 'n' },
  // Adjectifs prénominaux courts terminés en 'd/t/s' silencieux → /t/
  { word: /^(grand|petit|bon|haut|sot|tout|tant)$/i, liaisonIpa: 't' },
  // est → /t/
  { word: /^(est|sont|font|ont|vont|peuvent|veulent|doivent)$/i, liaisonIpa: 't' },
  // Prépositions sans/dans/sous → /z/ ; chez → /z/
  { word: /^(sans|dans|sous|chez)$/i, liaisonIpa: 'z' },
  // deux/trois → /z/ devant voyelle
  { word: /^(deux|trois|six|dix|vingt|cent)$/i, liaisonIpa: 'z' },
]

/**
 * Pour chaque paire (mot, mot suivant), détermine si une liaison s'applique.
 * Retourne le phonème à insérer (ou '' si pas de liaison).
 */
export function detectLiaison(currentWord: string, nextWord: string): string {
  if (!currentWord || !nextWord) return ''
  if (!VOWEL_STARTS.test(nextWord)) return ''
  // h aspiré : on ne devrait PAS liaison ("les héros"). Liste minimale.
  const HASPIRE = /^(héros|haine|huit|honteux|honte|haut|hibou|hangar|harpe)/i
  if (HASPIRE.test(nextWord)) return ''
  for (const rule of LIAISON_RULES) {
    if (rule.word.test(currentWord)) return rule.liaisonIpa
  }
  return ''
}

/**
 * Phonémise une phrase complète FR en tenant compte des liaisons.
 * À l'opposé de phonemizeSentence qui ne traite pas les liaisons.
 */
export function phonemizeSentenceWithLiaisons(text: string): string[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: string[] = []
  for (let i = 0; i < words.length; i += 1) {
    const w = words[i]
    const phones = phonemizeWord(w)
    out.push(...phones)
    const next = words[i + 1]
    if (next) {
      const liaison = detectLiaison(w, next)
      if (liaison) out.push(liaison)
    }
  }
  return out
}

/**
 * High-quality text-to-visemes : phonemize FR + map each IPA to viseme + take
 * the table duration when known, fallback to 80ms otherwise. Returns keyframes
 * suitable for the talking-head idle animation.
 */
export function textToVisemesRuleBased(text: string, speedFactor = 1): VisemeKeyframe[] {
  const phones = phonemizeSentence(text)
  let cursor = 0
  const out: VisemeKeyframe[] = []
  for (const ph of phones) {
    const dur = Math.max(30, (FR_DURATIONS.get(ph) ?? 80) / Math.max(0.5, speedFactor))
    const viseme = phonemeToViseme(ph)
    const last = out[out.length - 1]
    if (last && last.viseme === viseme) {
      last.endMs += dur
    } else {
      out.push({ startMs: cursor, endMs: cursor + dur, viseme })
    }
    cursor += dur
  }
  return out
}
