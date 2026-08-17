// ---------------------------------------------------------------------------
// codeCompositionAttribution — dire QUEL FICHIER porte la section mesuree.
//
// Le juge de composition mesure le DOM rendu; le correcteur, lui, edite des
// fichiers. Entre les deux il manquait le nom. Run 1161, mesure sur le livrable
// reel: la porte `no_empty_section` a rendu pour toute preuve
//
//     « Torréfié cette semaine, : 944px remplie a 9% »
//
// sur un projet de 31 fichiers. La passe ciblee a reecrit cinq pages et une
// feuille de style — et JAMAIS `src/components/HeroSection.tsx`, seul fichier a
// contenir cette section. Elle ne pouvait pas: son heuristique de portee cherche
// `<section` dans la source, et le composant ecrit `<motion.section>`.
//
// L attribution est deterministe: le rendu connait la classe et le texte de la
// section, la source les contient. Rien a demander a un modele.
// ---------------------------------------------------------------------------

export type AttributableSection = {
  /** Selecteur CSS produit par la mesure, ex. `section.hero-section`. */
  selector?: string
  /** Texte visible de la section, tel que mesure a l ecran. */
  label?: string
}

export type AttributionFile = { name: string; content: string }

const MARKUP_RE = /\.(html?|vue|svelte|[jt]sx)$/i

/** Tokens `#id` et `.classe` d un selecteur, sans le nom de balise. */
export function selectorTokens(selector: string | undefined): string[] {
  if (!selector) return []
  return [...selector.matchAll(/[.#]([A-Za-z_][\w-]*)/g)]
    .map((m) => m[1])
    .filter((token) => token.length >= 3)
}

function collapse(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/**
 * Le plus long prefixe du texte visible qui apparaisse tel quel dans la source.
 *
 * Un titre rendu « Torréfié cette semaine, pas l an dernier » est ecrit avec un
 * `<br />` au milieu: seul le debut est contigu dans le fichier. On cherche donc
 * du plus long au plus court, et on s arrete a 10 caracteres — en dessous, une
 * coincidence ne prouve rien.
 */
function longestMatchingPrefix(label: string, haystack: string): string | null {
  const text = collapse(label)
  for (let end = text.length; end >= 10; end -= 1) {
    const candidate = text.slice(0, end).trim()
    if (candidate.length < 10) break
    if (haystack.includes(candidate)) return candidate
  }
  return null
}

/**
 * Attribue une section rendue au fichier source qui la porte. Renvoie `null`
 * quand rien ne designe un fichier: une attribution douteuse enverrait le
 * correcteur au mauvais endroit, ce qui est pire que pas d attribution.
 */
export function attributeSectionToFile(
  section: AttributableSection,
  files: AttributionFile[],
): string | null {
  const tokens = selectorTokens(section.selector)
  const label = section.label ?? ''
  let best: { name: string; score: number } | null = null

  for (const file of files) {
    if (!MARKUP_RE.test(file.name)) continue
    const collapsed = collapse(file.content)
    let score = 0

    for (const token of tokens) {
      // La classe doit apparaitre comme VALEUR, pas au hasard dans un mot.
      if (new RegExp(`["'\\s{\`]${token}["'\\s}\`]`).test(collapsed)) score += 3
    }
    const prefix = longestMatchingPrefix(label, collapsed)
    if (prefix) score += 2 + Math.min(4, Math.floor(prefix.length / 10))

    if (score > 0 && (!best || score > best.score)) best = { name: file.name, score }
  }

  return best ? best.name : null
}

/** Attribue toutes les sections mesurees, en place, sans jamais en perdre une. */
export function attributeSections<T extends AttributableSection>(
  sections: T[],
  files: AttributionFile[],
): Array<T & { sourceFile?: string }> {
  return sections.map((section) => {
    const sourceFile = attributeSectionToFile(section, files)
    return sourceFile ? { ...section, sourceFile } : section
  })
}
