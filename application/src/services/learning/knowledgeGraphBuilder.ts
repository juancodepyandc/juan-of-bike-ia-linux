// Extrait un graphe de connaissances depuis un texte de cours FR.
// Identifie : termes-clés (entités), relations explicites ("X est un Y",
// "X dépend de Y", "X cause Y"), et co-occurrences forte (entités qui
// apparaissent dans la même phrase plusieurs fois).
//
// Pour STI2D : utile pour mapper "pendule -- est un -> oscillateur" ou
// "période -- dépend de -> longueur" depuis un cours brut, puis pour
// proposer des révisions sur les liens manquants.

export type Entity = {
  /** Forme canonique (lemmatisé approximatif). */
  canonical: string
  /** Mentions originales dans le texte. */
  mentions: string[]
  /** Position première mention. */
  firstSeen: number
  /** Importance estimée : fréquence × distinctivité × position. */
  importance: number
}

export type Relation = {
  source: string
  target: string
  /** Type de relation. */
  kind: 'is-a' | 'has-property' | 'depends-on' | 'causes' | 'opposite-of' | 'used-for' | 'co-occurs'
  /** Mentions contextuelles (snippets). */
  evidence: string[]
  /** Force de la relation [0..1]. */
  confidence: number
}

export type KnowledgeGraph = {
  entities: Entity[]
  relations: Relation[]
}

// Lemmatisation light : retire articles initiaux, met au singulier sur "s" final.
function normaliseTerm(term: string): string {
  let t = term.toLowerCase().trim()
  t = t.replace(/^(le |la |les |un |une |des |du |l'|d'|de la |de l'|de )/i, '')
  t = t.replace(/^(ce |cette |ces )/i, '')
  // Singulier basique
  if (t.endsWith('aux')) t = t.slice(0, -3) + 'al'
  else if (t.endsWith('eux') && t.length > 5) t = t.slice(0, -1) + 'l' // chevaux→cheval pose pb mais OK pour fr commun
  else if (t.endsWith('s') && t.length > 3) t = t.slice(0, -1)
  return t
}

// Pour matcher des mots français incluant accents, on étend la classe word.
// \b ne fonctionne pas correctement avec é/à/ô donc on évite et on borne
// par espace/début/ponctuation.
const FR_WORD = `[a-zA-Zàâäéèêëïîôùûüçœæ][a-zA-Zàâäéèêëïîôùûüçœæ'-]*`
const FR_PHRASE = `${FR_WORD}(?:\\s+${FR_WORD}){0,3}`

const RELATION_PATTERNS: Array<{ regex: RegExp; kind: Relation['kind']; group: { source: number; target: number } }> = [
  { regex: new RegExp(`(?:^|[\\s,;:.])(${FR_PHRASE})\\s+(?:est|sont)\\s+(?:un|une|des)\\s+(${FR_PHRASE})(?=[\\s,;:.!?]|$)`, 'gi'), kind: 'is-a', group: { source: 1, target: 2 } },
  { regex: new RegExp(`(?:^|[\\s,;:.])(${FR_PHRASE})\\s+(?:dépend|depend|dépendent|dependent)\\s+(?:de|du|d')\\s*(${FR_PHRASE})(?=[\\s,;:.!?]|$)`, 'gi'), kind: 'depends-on', group: { source: 1, target: 2 } },
  { regex: new RegExp(`(?:^|[\\s,;:.])(${FR_PHRASE})\\s+(?:cause|causent|provoque|provoquent)\\s+(${FR_PHRASE})(?=[\\s,;:.!?]|$)`, 'gi'), kind: 'causes', group: { source: 1, target: 2 } },
  { regex: new RegExp(`(?:^|[\\s,;:.])(${FR_PHRASE})\\s+(?:contraire|oppos[eé])\\s+(?:de|du|d')\\s*(${FR_PHRASE})(?=[\\s,;:.!?]|$)`, 'gi'), kind: 'opposite-of', group: { source: 1, target: 2 } },
  { regex: new RegExp(`(?:^|[\\s,;:.])(${FR_PHRASE})\\s+(?:sert|servent|utilis[eé])\\s+(?:à|pour)\\s+(${FR_PHRASE})(?=[\\s,;:.!?]|$)`, 'gi'), kind: 'used-for', group: { source: 1, target: 2 } },
]

const STOPWORDS_TERMS = new Set([
  'il', 'elle', 'ils', 'elles', 'ça', 'ca', 'cela', 'ceci', 'cet', 'ce',
  'cette', 'ces', 'on', 'nous', 'vous', 'je', 'tu', 'me', 'te', 'se',
  'le', 'la', 'les', 'un', 'une', 'des', 'du', 'd', 'de', 'l',
  'fois', 'chose', 'truc', 'machin', 'partie', 'côté', 'cote',
  'temps', 'cas', 'tout', 'tous', 'toute', 'toutes',
])

function isValidTerm(term: string): boolean {
  if (term.length < 3) return false
  if (STOPWORDS_TERMS.has(term)) return false
  if (/^\d+$/.test(term)) return false
  return true
}

/**
 * Extrait toutes les entités (substantifs apparaissant ≥ 2 fois ou
 * marqués comme termes techniques par leur typographie).
 */
export function extractEntities(text: string): Entity[] {
  const sentences = text.split(/(?<=[.!?])\s+/)
  const occurrences = new Map<string, { mentions: Set<string>; firstSeen: number; count: number }>()

  let charOffset = 0
  for (const sentence of sentences) {
    // Tokenize "noms" (au sens large) : suites de mots commençant majuscule ou
    // termes techniques entre guillemets/italiques approximés.
    const wordRe = /[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇŒ][\wàâäéèêëïîôùûüçœ-]+|"[^"]+"|«[^»]+»/g
    let m: RegExpExecArray | null
    while ((m = wordRe.exec(sentence)) != null) {
      const raw = m[0].replace(/^["«]|["»]$/g, '')
      const canonical = normaliseTerm(raw)
      if (!isValidTerm(canonical)) continue
      let entry = occurrences.get(canonical)
      if (!entry) {
        entry = { mentions: new Set(), firstSeen: charOffset + (m.index ?? 0), count: 0 }
        occurrences.set(canonical, entry)
      }
      entry.mentions.add(raw)
      entry.count += 1
    }
    // Termes courants (substantifs probables) — heuristique : mots > 4 lettres
    // qui apparaissent au pluriel ou avec un article défini.
    const articleRe = /\b(?:le|la|les|un|une|des|du|de la|d')\s+([\wàâäéèêëïîôùûüçœ-]{4,})/gi
    while ((m = articleRe.exec(sentence)) != null) {
      const raw = m[1]
      const canonical = normaliseTerm(raw)
      if (!isValidTerm(canonical)) continue
      let entry = occurrences.get(canonical)
      if (!entry) {
        entry = { mentions: new Set(), firstSeen: charOffset + (m.index ?? 0), count: 0 }
        occurrences.set(canonical, entry)
      }
      entry.mentions.add(raw)
      entry.count += 1
    }
    charOffset += sentence.length + 1
  }

  const total = Array.from(occurrences.values()).reduce((a, b) => a + b.count, 0)
  const entities: Entity[] = []
  for (const [canonical, data] of occurrences) {
    // Importance = freq normalisée × bonus si apparu tôt × bonus mention capitale.
    const freq = data.count / Math.max(1, total)
    const earlyBonus = 1 - data.firstSeen / Math.max(1, text.length)
    const capitalBonus = Array.from(data.mentions).some((m) => /^[A-Z]/.test(m)) ? 1.3 : 1
    const importance = freq * earlyBonus * capitalBonus
    if (data.count < 2 && capitalBonus === 1) continue // skip hapax non-capital
    entities.push({
      canonical,
      mentions: Array.from(data.mentions),
      firstSeen: data.firstSeen,
      importance,
    })
  }
  entities.sort((a, b) => b.importance - a.importance)
  return entities
}

/**
 * Extrait les relations explicites depuis le texte via les patterns.
 */
export function extractRelations(text: string): Relation[] {
  const relations: Relation[] = []
  for (const pat of RELATION_PATTERNS) {
    const re = new RegExp(pat.regex)
    let m: RegExpExecArray | null
    while ((m = re.exec(text)) != null) {
      const source = normaliseTerm(m[pat.group.source])
      const target = normaliseTerm(m[pat.group.target])
      if (!isValidTerm(source) || !isValidTerm(target)) continue
      if (source === target) continue
      relations.push({
        source,
        target,
        kind: pat.kind,
        evidence: [m[0]],
        confidence: 0.7,
      })
    }
  }
  return relations
}

/**
 * Build complet : entités + relations + co-occurrences.
 */
export function buildKnowledgeGraph(text: string, opts: { maxEntities?: number; coOccurMin?: number } = {}): KnowledgeGraph {
  const maxEntities = opts.maxEntities ?? 50
  const coOccurMin = opts.coOccurMin ?? 2
  const entities = extractEntities(text).slice(0, maxEntities)
  const explicit = extractRelations(text)

  // Co-occurrences par phrase entre entités principales.
  const entityIndex = new Map(entities.map((e) => [e.canonical, e]))
  const sentences = text.split(/(?<=[.!?])\s+/)
  const coOccurCounts = new Map<string, { source: string; target: string; count: number; evidence: string[] }>()
  for (const sentence of sentences) {
    const present: string[] = []
    for (const ent of entities) {
      // Vérifie une mention de l'entité dans la phrase (any mention form).
      if (ent.mentions.some((m) => sentence.toLowerCase().includes(m.toLowerCase()))) {
        present.push(ent.canonical)
      }
    }
    // Combinaisons paires.
    for (let i = 0; i < present.length; i += 1) {
      for (let j = i + 1; j < present.length; j += 1) {
        const [a, b] = [present[i], present[j]].sort()
        const key = `${a}||${b}`
        let entry = coOccurCounts.get(key)
        if (!entry) {
          entry = { source: a, target: b, count: 0, evidence: [] }
          coOccurCounts.set(key, entry)
        }
        entry.count += 1
        if (entry.evidence.length < 3) entry.evidence.push(sentence.trim().slice(0, 120))
      }
    }
  }

  const coOccurRelations: Relation[] = []
  for (const entry of coOccurCounts.values()) {
    if (entry.count < coOccurMin) continue
    // Skip si déjà une relation explicite source/target.
    const alreadyExplicit = explicit.some(
      (r) => (r.source === entry.source && r.target === entry.target) || (r.source === entry.target && r.target === entry.source),
    )
    if (alreadyExplicit) continue
    coOccurRelations.push({
      source: entry.source,
      target: entry.target,
      kind: 'co-occurs',
      evidence: entry.evidence,
      confidence: Math.min(0.6, entry.count / 10),
    })
  }

  return { entities, relations: [...explicit, ...coOccurRelations] }
}

/**
 * Suggère des questions de révision basées sur les relations détectées.
 * "Qu'est-ce que X ?", "De quoi dépend Y ?", "Donne un exemple de Z."
 */
export function generateReviewQuestions(graph: KnowledgeGraph, limit = 10): Array<{ question: string; topic: string }> {
  const questions: Array<{ question: string; topic: string }> = []
  for (const rel of graph.relations) {
    if (questions.length >= limit) break
    switch (rel.kind) {
      case 'is-a':
        questions.push({ question: `Qu'est-ce qu'un ${rel.source} ?`, topic: rel.source })
        break
      case 'depends-on':
        questions.push({ question: `De quoi dépend le ${rel.source} ?`, topic: rel.source })
        break
      case 'causes':
        questions.push({ question: `Quel est l'effet de ${rel.source} ?`, topic: rel.source })
        break
      case 'has-property':
        questions.push({ question: `Quelles propriétés a ${rel.source} ?`, topic: rel.source })
        break
      case 'used-for':
        questions.push({ question: `À quoi sert ${rel.source} ?`, topic: rel.source })
        break
      case 'co-occurs':
        questions.push({ question: `Quelle est la relation entre ${rel.source} et ${rel.target} ?`, topic: rel.source })
        break
    }
  }
  return questions.slice(0, limit)
}
