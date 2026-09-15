// Nettoyage des artefacts de mise en forme des fichiers generes.
//
// Extrait de `codeGeneratedFileSanitizer.ts` : ce sont les deux operations qui
// touchent au TEXTE BRUT rendu par le modele, avant toute interpretation du
// contenu. Les isoler les rend testables seules, et ramene l unite appelante
// sous la limite de 400 lignes du module.

export type StripOptions = {
  /**
   * Le contenu est un document en Markdown, ou une clôture de bloc de code en
   * fin de fichier est LEGITIME. Voir plus bas.
   */
  markdown?: boolean
}

export function stripFormattingArtifacts(content: string, options: StripOptions = {}) {
  let current = content
    .replace(/^\uFEFF/, '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()

  for (let index = 0; index < 3; index += 1) {
    // Les deux retraits etaient INDEPENDANTS : la cloture finale partait meme
    // sans ouverture correspondante. Un README qui se termine par un bloc de
    // code — le cas le plus banal qui soit :
    //
    //     # Titre
    //     ```bash
    //     npm install
    //     ```
    //
    // ressortait ampute de sa derniere ligne, donc en Markdown casse : le
    // bloc reste ouvert et tout ce qui suivrait serait avale. Mesure : le
    // fichier livre perdait sa cloture a chaque generation.
    //
    // On ne retire desormais la cloture que si une OUVERTURE l'accompagne
    // (le modele a emballe tout le fichier), ou si le fichier n'est pas du
    // Markdown — auquel cas une ligne ``` finale reste un artefact.
    // Une balise compte AU MOINS trois accents graves, et peut en compter
    // davantage : c'est ainsi qu'un modele emballe un document qui contient
    // deja des blocs de code (```` autour d'un Markdown a ```). La cloture
    // doit alors en compter autant. Ne reconnaitre que la forme a trois
    // laissait l'emballage en place, et le README livre commencait par
    // « ````md ».
    const ouvrant = /^(`{3,})[\w.-]*[ \t]*\r?\n/.exec(current)
    const fermant = /\r?\n(`{3,})[ \t]*$/.exec(current)
    const appariees = !!ouvrant && !!fermant && fermant[1].length >= ouvrant[1].length
    let next = current
    if (ouvrant && (appariees || !fermant)) next = next.slice(ouvrant[0].length)
    if (fermant && (appariees || !options.markdown)) {
      next = next.slice(0, next.length - fermant[0].length)
    }
    next = next.trim()

    if (next === current) break
    current = next
  }

  return current
}

/** Documents de prose, ou la syntaxe Markdown fait partie du contenu livre. */
export function isProseDocument(normalized: string) {
  return normalized.endsWith('.md')
    || normalized.endsWith('.markdown')
    || normalized.endsWith('.mdx')
    || normalized.endsWith('.txt')
    || normalized.endsWith('.rst')
}

/**
 * Retire commentaires et virgules finales d un JSON approximatif.
 *
 * Correction : la suppression des virgules finales se faisait par une
 * expression reguliere appliquee A LA FIN, sur tout le texte — y compris
 * l INTERIEUR des chaines. Une valeur legitime comme `"un, deux, }"` en
 * ressortait amputee : `"un, deux}"`. Le fichier restait du JSON valide, la
 * DONNEE etait fausse, et rien ne le signalait. Mesure : sur 2 des 5 JSON
 * approximatifs testes, une virgule interne a une chaine disparaissait.
 *
 * La suppression se fait desormais DANS l automate, la ou l on sait si l on
 * est dans une chaine ou non : on ne saute la virgule que si le prochain
 * caractere significatif — commentaires ignores — ferme un objet ou un
 * tableau.
 */
export function stripJsonCommentsAndTrailingCommas(content: string) {
  let out = ''
  let inString = false
  let quote = ''
  let escaped = false
  let inLineComment = false
  let inBlockComment = false

  /** Prochain caractere significatif a partir de `from`, commentaires sautes. */
  const nextSignificant = (from: number): string => {
    let k = from
    while (k < content.length) {
      const c = content[k]
      if (c === '/' && content[k + 1] === '/') {
        while (k < content.length && content[k] !== '\n') k += 1
        continue
      }
      if (c === '/' && content[k + 1] === '*') {
        k += 2
        while (k < content.length && !(content[k] === '*' && content[k + 1] === '/')) k += 1
        k += 2
        continue
      }
      if (!/\s/.test(c)) return c
      k += 1
    }
    return ''
  }

  for (let index = 0; index < content.length; index += 1) {
    const ch = content[index]
    const next = content[index + 1]

    if (inLineComment) {
      if (ch === '\n' || ch === '\r') {
        inLineComment = false
        out += ch
      }
      continue
    }

    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false
        index += 1
      }
      continue
    }

    if (inString) {
      out += ch
      if (escaped) {
        escaped = false
      } else if (ch === '\\') {
        escaped = true
      } else if (ch === quote) {
        inString = false
        quote = ''
      }
      continue
    }

    if (ch === '"' || ch === "'") {
      inString = true
      quote = ch
      out += ch
      continue
    }

    if (ch === '/' && next === '/') {
      inLineComment = true
      index += 1
      continue
    }

    if (ch === '/' && next === '*') {
      inBlockComment = true
      index += 1
      continue
    }

    // Virgule finale : hors chaine, suivie d une fermeture.
    if (ch === ',') {
      const suivant = nextSignificant(index + 1)
      if (suivant === '}' || suivant === ']') continue
    }

    out += ch
  }

  return out
}
