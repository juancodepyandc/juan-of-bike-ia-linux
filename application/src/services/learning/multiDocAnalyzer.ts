// Multi-document analyzer pour Academy : prend N documents (cours, fiches,
// PDF, notes) et construit un index BM25 cross-doc qui permet à Aurora de
// répondre à une question PRÉCISE en citant l'extrait pertinent du BON doc.
//
// Approche :
//   1. Chunk : découpe chaque doc en passages de 300-500 mots (paragraphe-based).
//   2. Index : BM25 (TF + IDF + longueur), tokenisation FR avec strip accents.
//   3. Query : retourne top-K passages avec score + référence doc.
//   4. Cross-ref : détecte les passages qui parlent du même concept dans
//      plusieurs docs (cosine similarité de leur TF normalisé).
//
// Pas de réseau, pas de LLM — tout est compute pur. La sortie alimente le
// prompt LLM pour citation précise.

export type Doc = {
  /** Nom du fichier source. */
  name: string
  /** Contenu texte brut. */
  content: string
  /** Type détecté (pdf, txt, md, docx). */
  kind?: 'pdf' | 'txt' | 'md' | 'docx' | 'unknown'
}

export type Passage = {
  docName: string
  docIndex: number
  passageIndex: number
  text: string
  /** Position de début dans le doc original (utile pour pointer). */
  start: number
  end: number
}

export type ScoredPassage = Passage & {
  score: number
  /** Mots de la query qui ont matché ici. */
  matchedTerms: string[]
}

export type CrossReference = {
  conceptTerms: string[]
  passages: Passage[]
  cosineSim: number
}

const FR_STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'a', 'au', 'aux',
  'et', 'ou', 'ni', 'mais', 'donc', 'or', 'car',
  'que', 'qui', 'quoi', 'dont', 'ou',
  'ce', 'cet', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
  'son', 'sa', 'ses', 'notre', 'votre', 'leur', 'nos', 'vos', 'leurs',
  'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
  'etre', 'avoir', 'faire', 'aller', 'voir', 'savoir', 'pouvoir', 'vouloir',
  'est', 'sont', 'etait', 'etaient', 'sera', 'seront',
  'a', 'avait', 'avaient', 'aura', 'auront',
  'pas', 'plus', 'tres', 'tres', 'aussi', 'bien', 'meme', 'tout', 'tous',
  'pour', 'par', 'sur', 'sous', 'dans', 'avec', 'sans', 'entre',
  'comme', 'si', 'sinon', 'puisque', 'parce', 'lorsque', 'quand',
  'leur', 'son', 'sa', 'ses',
])

function normaliseToken(t: string): string {
  return t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function tokenize(text: string): string[] {
  return text
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .filter((t) => t.length > 1 && !FR_STOPWORDS.has(t))
}

/**
 * Découpe un doc en passages : paragraphes (séparés par 2+ newlines), puis
 * regroupe les paragraphes courts pour atteindre ~300 mots par passage,
 * scinde les paragraphes longs.
 */
function chunkDocument(doc: Doc, docIndex: number, targetWords = 300, maxWords = 600): Passage[] {
  const paragraphs = doc.content.split(/\n\s*\n+/).filter((p) => p.trim().length > 20)
  const passages: Passage[] = []
  let pIndex = 0
  let pos = 0

  for (const para of paragraphs) {
    const words = para.trim().split(/\s+/)
    if (words.length <= maxWords) {
      const start = doc.content.indexOf(para, pos)
      const end = start + para.length
      passages.push({
        docName: doc.name,
        docIndex,
        passageIndex: pIndex++,
        text: para.trim(),
        start: start >= 0 ? start : pos,
        end: start >= 0 ? end : pos + para.length,
      })
      pos = end
    } else {
      // Split paragraphe long en chunks de ~targetWords.
      let i = 0
      while (i < words.length) {
        const slice = words.slice(i, i + targetWords).join(' ')
        const start = doc.content.indexOf(slice.split(' ')[0], pos)
        const end = start + slice.length
        passages.push({
          docName: doc.name,
          docIndex,
          passageIndex: pIndex++,
          text: slice,
          start: start >= 0 ? start : pos,
          end: start >= 0 ? end : pos + slice.length,
        })
        pos = end
        i += targetWords
      }
    }
  }
  // Fallback : si pas de paragraphes détectés, prendre le tout.
  if (passages.length === 0 && doc.content.trim().length > 0) {
    passages.push({
      docName: doc.name, docIndex, passageIndex: 0,
      text: doc.content.trim(),
      start: 0, end: doc.content.length,
    })
  }
  return passages
}

export type MultiDocIndex = {
  passages: Passage[]
  /** termFreq par passage : map term → count. */
  termFreqs: Array<Map<string, number>>
  /** docFreq global : map term → nb de passages contenant ce term. */
  docFreqs: Map<string, number>
  /** Longueur moyenne de passage en termes. */
  avgLen: number
  /** Longueur par passage. */
  lens: number[]
}

export function buildIndex(docs: Doc[]): MultiDocIndex {
  const passages: Passage[] = []
  docs.forEach((d, i) => passages.push(...chunkDocument(d, i)))

  const termFreqs: Array<Map<string, number>> = []
  const docFreqs = new Map<string, number>()
  const lens: number[] = []

  for (const passage of passages) {
    const tokens = tokenize(passage.text)
    const tf = new Map<string, number>()
    for (const t of tokens) tf.set(t, (tf.get(t) || 0) + 1)
    termFreqs.push(tf)
    lens.push(tokens.length)
    // df : count chaque term UNE FOIS par passage.
    for (const t of tf.keys()) docFreqs.set(t, (docFreqs.get(t) || 0) + 1)
  }
  const avgLen = lens.length === 0 ? 0 : lens.reduce((s, n) => s + n, 0) / lens.length

  return { passages, termFreqs, docFreqs, avgLen, lens }
}

/**
 * BM25 scoring : pour une query, retourne les top-K passages.
 *
 * Score(D, Q) = Σ IDF(qi) × tf(qi, D) × (k1+1) / (tf(qi, D) + k1 × (1 - b + b × |D|/avgL))
 */
export function queryIndex(
  index: MultiDocIndex,
  query: string,
  topK = 5,
  k1 = 1.5,
  b = 0.75,
): ScoredPassage[] {
  const queryTokens = Array.from(new Set(tokenize(query)))
  if (queryTokens.length === 0) return []
  const N = index.passages.length
  const scores = new Array<{ idx: number; score: number; matched: string[] }>(N)
  for (let i = 0; i < N; i += 1) {
    const tf = index.termFreqs[i]
    const dl = index.lens[i]
    let s = 0
    const matched: string[] = []
    for (const q of queryTokens) {
      const f = tf.get(q) || 0
      if (f === 0) continue
      matched.push(q)
      const df = index.docFreqs.get(q) || 1
      const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5))
      const norm = f * (k1 + 1) / (f + k1 * (1 - b + b * (dl / Math.max(1, index.avgLen))))
      s += idf * norm
    }
    scores[i] = { idx: i, score: s, matched }
  }
  scores.sort((a, b2) => b2.score - a.score)
  return scores
    .slice(0, topK)
    .filter((s) => s.score > 0)
    .map((s) => ({ ...index.passages[s.idx], score: s.score, matchedTerms: s.matched }))
}

/**
 * Construit un prompt block "Sources" à injecter dans le system prompt d'Aurora
 * pour qu'elle puisse citer le doc + passage exact dans sa réponse.
 */
export function buildContextBlock(scored: ScoredPassage[], maxChars = 3500): string {
  const blocks: string[] = []
  let used = 0
  for (const sp of scored) {
    const header = `[${sp.docName} · passage ${sp.passageIndex + 1}]`
    const body = sp.text.length > 800 ? sp.text.slice(0, 800) + '…' : sp.text
    const block = `${header}\n${body}`
    if (used + block.length > maxChars) break
    blocks.push(block)
    used += block.length
  }
  return blocks.join('\n\n---\n\n')
}

/**
 * Cross-référence : trouve les passages de docs différents qui parlent du
 * même concept (forte similarité TF normalisé).
 *
 * Algo : pour chaque paire (P1 de doc A, P2 de doc B) :
 *   - intersection des top-10 termes les plus forts
 *   - cosine similarité de leur vecteur TF (sur les termes en commun)
 *   - si > 0.3 → cross-ref
 */
export function findCrossReferences(index: MultiDocIndex, minSim = 0.3): CrossReference[] {
  const N = index.passages.length
  const refs: CrossReference[] = []
  // Top 8 termes par passage (par TF descending).
  const topTermsPerPassage = index.termFreqs.map((tf) => {
    return Array.from(tf.entries())
      .sort((a, b2) => b2[1] - a[1])
      .slice(0, 8)
      .map(([t]) => t)
  })
  for (let i = 0; i < N; i += 1) {
    for (let j = i + 1; j < N; j += 1) {
      if (index.passages[i].docIndex === index.passages[j].docIndex) continue
      const ti = topTermsPerPassage[i]
      const tj = topTermsPerPassage[j]
      const common = ti.filter((t) => tj.includes(t))
      if (common.length < 3) continue
      // Cosine sur les counts de termes communs.
      let dot = 0, ni = 0, nj = 0
      for (const t of common) {
        const a = index.termFreqs[i].get(t) || 0
        const b2 = index.termFreqs[j].get(t) || 0
        dot += a * b2
        ni += a * a
        nj += b2 * b2
      }
      const sim = (ni && nj) ? dot / Math.sqrt(ni * nj) : 0
      if (sim >= minSim) {
        refs.push({
          conceptTerms: common,
          passages: [index.passages[i], index.passages[j]],
          cosineSim: sim,
        })
      }
    }
  }
  refs.sort((a, b2) => b2.cosineSim - a.cosineSim)
  return refs.slice(0, 20)
}

void normaliseToken // exported via tokenize
