// ---------------------------------------------------------------------------
// codePatchMatching — retrouver le texte a patcher meme quand le modele l a
// recopie de memoire.
//
// Panne observee sur un run reel de 46 minutes: apres 36 fichiers emis, le
// pipeline meurt sur `agentic_retry_failed:patch_search_not_found`. Tout le run
// est perdu.
//
// `apply_patch` exigeait une correspondance de sous-chaine EXACTE
// (`file.content.includes(action.search)`). Or le modele reconstitue le bloc a
// chercher de memoire: une indentation de 2 au lieu de 4 espaces, une tabulation
// convertie, un espace en fin de ligne, un retour CRLF — et la recherche echoue
// alors que le texte est bien la, a l identique aux blancs pres.
//
// On garde donc l egalite stricte en premier (rapide, sans risque), puis on
// retombe sur une comparaison INSENSIBLE AUX BLANCS pour localiser la region,
// et on decoupe sur les indices d origine afin de preserver le fichier reel.
// ---------------------------------------------------------------------------

export type PatchMatch = {
  /** Index de debut dans le contenu ORIGINAL. */
  start: number
  /** Index de fin (exclu) dans le contenu ORIGINAL. */
  end: number
  /** Comment la correspondance a ete obtenue. */
  strategy: 'exact' | 'whitespace_insensitive'
}

/** Signature d un caractere d espacement (espace, tab, CR, LF, NBSP). */
function isSpace(ch: string): boolean {
  return ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n' || ch === ' '
}

/**
 * Cherche `search` dans `content` en ignorant les differences d espacement.
 *
 * Parcourt le contenu en avancant deux curseurs qui sautent les blancs de part
 * et d autre. Rend les indices REELS dans le contenu d origine, pour que le
 * remplacement n abime ni l indentation ni les fins de ligne voisines.
 */
function findWhitespaceInsensitive(content: string, search: string): PatchMatch | null {
  const trimmedSearch = search.trim()
  if (!trimmedSearch) return null

  for (let start = 0; start < content.length; start++) {
    // On n amorce que sur un caractere significatif identique au premier du motif.
    if (isSpace(content[start])) continue
    if (content[start] !== trimmedSearch[0]) continue

    let i = start
    let j = 0
    while (i < content.length && j < trimmedSearch.length) {
      const c = content[i]
      const s = trimmedSearch[j]
      if (isSpace(c) && isSpace(s)) {
        // Les deux cotes sont sur du blanc: on consomme les deux sequences.
        while (i < content.length && isSpace(content[i])) i++
        while (j < trimmedSearch.length && isSpace(trimmedSearch[j])) j++
        continue
      }
      if (isSpace(s)) { // blanc attendu, absent du fichier -> tolere
        while (j < trimmedSearch.length && isSpace(trimmedSearch[j])) j++
        continue
      }
      if (isSpace(c)) { // blanc en trop dans le fichier -> tolere
        while (i < content.length && isSpace(content[i])) i++
        continue
      }
      if (c !== s) break
      i++
      j++
    }
    // Motif entierement consomme (les blancs de fin ne comptent pas).
    while (j < trimmedSearch.length && isSpace(trimmedSearch[j])) j++
    if (j >= trimmedSearch.length) {
      return { start, end: i, strategy: 'whitespace_insensitive' }
    }
  }
  return null
}

/**
 * Localise le bloc a remplacer. Egalite stricte d abord, tolerance aux blancs
 * ensuite. Retourne null si le texte est reellement absent.
 */
export function findPatchTarget(content: string, search: string): PatchMatch | null {
  if (!search) return null
  const exact = content.indexOf(search)
  if (exact !== -1) return { start: exact, end: exact + search.length, strategy: 'exact' }
  return findWhitespaceInsensitive(content, search)
}

/**
 * Applique le patch. `all: true` remplace toutes les occurrences (strictes
 * uniquement: repeter une recherche floue sur un fichier entier ferait plus de
 * degats que de bien).
 */
export function applyPatchToContent(
  content: string,
  search: string,
  replace: string,
  all = false,
): { ok: boolean; content: string; strategy?: PatchMatch['strategy'] } {
  if (all && content.includes(search)) {
    return { ok: true, content: content.split(search).join(replace), strategy: 'exact' }
  }
  const match = findPatchTarget(content, search)
  if (!match) return { ok: false, content }
  return {
    ok: true,
    content: content.slice(0, match.start) + replace + content.slice(match.end),
    strategy: match.strategy,
  }
}
