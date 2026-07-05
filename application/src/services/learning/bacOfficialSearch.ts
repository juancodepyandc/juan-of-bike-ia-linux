// BAC official source search — produit des requêtes ciblées pour le moteur
// de recherche web (déjà branché via prepareTaskIntelligence) afin de tomber
// sur des annales officielles ou des corrigés vérifiés.
//
// Domaines officiels à privilégier :
//   - eduscol.education.fr (programmes officiels + ressources)
//   - sujetdebac.fr (annales corrigées)
//   - annabac.com (sujets + corrigés)
//   - france-examen.com (corrigés vérifiés)
//   - lerob ert.com / lalibrairie.eduscol.fr (textes officiels)
//
// La fonction de recherche réelle (fetch + parse) doit être appelée par le
// caller via prepareTaskIntelligence / researchLearningTopic — ici on
// produit juste les meilleures REQUÊTES.

export type OfficialQuery = {
  /** Texte de la requête à passer au moteur de recherche. */
  query: string
  /** Sites cibles privilégiés. */
  preferredDomains: string[]
  /** Description humaine de ce que cherche cette requête. */
  intent: string
}

/**
 * Génère plusieurs requêtes ciblées pour trouver les sources officielles
 * autour d'un sujet de cours / d'un exercice.
 */
export function buildOfficialQueries(topic: string, opts: {
  filiere?: 'STI2D-SIN' | 'STI2D-EE' | 'STI2D-ITEC' | 'STI2D-AC' | 'general'
  year?: number
  kind?: 'annale' | 'corrige' | 'programme' | 'cours'
} = {}): OfficialQuery[] {
  const filiere = opts.filiere || 'STI2D-SIN'
  const year = opts.year || new Date().getFullYear() - 1
  const cleaned = topic.trim().replace(/[^\w\s'-éèàùâêîôûäëïöü]/g, ' ').slice(0, 80)

  const queries: OfficialQuery[] = []

  // 1. Annale officielle eduscol
  queries.push({
    query: `${cleaned} BAC ${filiere} ${year} sujet site:eduscol.education.fr`,
    preferredDomains: ['eduscol.education.fr'],
    intent: `Annale officielle eduscol ${year} sur ${cleaned}`,
  })
  // 2. Corrigé sujetdebac
  queries.push({
    query: `${cleaned} BAC ${filiere} ${year} corrigé site:sujetdebac.fr`,
    preferredDomains: ['sujetdebac.fr'],
    intent: `Corrigé sujetdebac.fr`,
  })
  // 3. Annabac
  queries.push({
    query: `${cleaned} BAC ${filiere} annales corrigées site:annabac.com`,
    preferredDomains: ['annabac.com'],
    intent: 'Annales corrigées Annabac',
  })
  // 4. Programme officiel BO
  if (opts.kind === 'programme' || !opts.kind) {
    queries.push({
      query: `programme officiel ${filiere} ${cleaned} site:education.gouv.fr`,
      preferredDomains: ['education.gouv.fr'],
      intent: 'Programme officiel B.O.',
    })
  }
  // 5. Lumni / France-examen
  queries.push({
    query: `${cleaned} ${filiere} cours fiche révision site:lumni.fr`,
    preferredDomains: ['lumni.fr', 'france-examen.com'],
    intent: 'Cours / fiche révision officielle Lumni',
  })

  return queries
}

/**
 * Filtre des résultats de recherche : ne garde que ceux qui viennent de
 * domaines officiels reconnus (sécurité contre la pollution SEO).
 */
const OFFICIAL_DOMAINS_RE = /\.(?:education\.fr|education\.gouv\.fr|sujetdebac\.fr|annabac\.com|lumni\.fr|france-examen\.com|maxicours\.com|lerobert\.com|lelivrescolaire\.fr)\//i

export function filterOfficialResults<T extends { url?: string }>(results: T[]): T[] {
  return results.filter((r) => r.url && OFFICIAL_DOMAINS_RE.test(r.url))
}

/**
 * Construit un bloc "sources officielles" pour le system prompt LLM, à partir
 * des résultats de recherche.
 */
export function buildOfficialSourcesBlock(
  results: Array<{ url?: string; title?: string; snippet?: string }>,
  maxChars = 1800,
): string {
  const filtered = filterOfficialResults(results).slice(0, 5)
  if (filtered.length === 0) return ''
  const lines: string[] = ['SOURCES OFFICIELLES TROUVÉES (cite-les par URL quand tu réutilises un fait) :']
  let used = 0
  for (const r of filtered) {
    const line = `- ${r.title || '(sans titre)'} · ${r.url}\n  ${(r.snippet || '').slice(0, 200)}`
    if (used + line.length > maxChars) break
    lines.push(line)
    used += line.length
  }
  return lines.join('\n')
}
