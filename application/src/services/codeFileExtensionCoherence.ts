// ---------------------------------------------------------------------------
// codeFileExtensionCoherence — l extension doit correspondre a la GRAMMAIRE que
// le contenu exige.
//
// MESURE (run v126, sur le livrable reel, 31 fichiers, toutes les portes
// passees — rendu 100/100, acceptation comportementale 2/2):
//
//   24x  TS1110: Type expected.
//        TS1161: Unterminated regular expression literal
//        -> src/vitest.setup.ts(35,84)
//
//   Ligne 35 du fichier emis:
//     AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
//
// C est du JSX dans un fichier `.ts`. TypeScript refuse le JSX hors `.tsx`: il
// lit `<>` comme une assertion de type, puis la suite comme une expression
// reguliere non terminee. La SYNTAXE est correcte; c est l EXTENSION qui est
// fausse.
//
// Le run a brule sept passes de modele — puis s est arrete sur « boucle infinie
// detectee apres 7 passes » — a essayer de reparer une syntaxe juste. Aucune
// reecriture ne pouvait aboutir: le correctif n est pas dans le contenu.
//
// C est le miroir exact d un defaut deja ferme (« la grammaire suivait le
// libelle: `.tsx` -> grammaire typescript qui refuse le JSX »). Ici, le sens
// inverse. On traite donc la FAMILLE: extension, libelle de langage et contenu
// doivent s accorder, dans les deux sens.
//
// La correction est DETERMINISTE — renommer un fichier et recoller ses
// references — donc elle ne passe pas par un modele probabiliste.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

/**
 * Retire chaines, gabarits, commentaires et litteraux d expression reguliere,
 * pour que la detection ne se declenche pas sur du texte.
 */
function stripNonCode(source: string): string {
  let out = ''
  let i = 0
  while (i < source.length) {
    const char = source[i]
    const next = source[i + 1]
    if (char === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') i += 1
      continue
    }
    if (char === '/' && next === '*') {
      i += 2
      while (i < source.length && !(source[i] === '*' && source[i + 1] === '/')) i += 1
      i += 2
      continue
    }
    if (char === '"' || char === "'" || char === '`') {
      const quote = char
      i += 1
      while (i < source.length && source[i] !== quote) {
        if (source[i] === '\\') i += 1
        i += 1
      }
      i += 1
      out += '""'
      continue
    }
    out += char
    i += 1
  }
  return out
}

const CLOSING_ELEMENT = /<\/[A-Za-z][\w.:-]*\s*>/
const CLOSING_FRAGMENT = /<\/\s*>/
const SELF_CLOSING_ELEMENT = /<[A-Za-z][\w.:-]*(?:\s[^<>]*?)?\/>/

/**
 * Le contenu exige-t-il une grammaire JSX ?
 *
 * Volontairement etroit et ancre sur des formes qu aucune autre construction
 * TypeScript ne produit: une balise fermante `</Foo>`, un fragment fermant
 * `</>`, ou un element auto-fermant `<Foo />`. Les generiques (`<T,>(x: T)`),
 * les assertions (`<string>x`) et les comparaisons n en produisent aucune.
 */
export function containsJsx(content: string): boolean {
  const code = stripNonCode(content)
  return CLOSING_ELEMENT.test(code) || CLOSING_FRAGMENT.test(code) || SELF_CLOSING_ELEMENT.test(code)
}

const JSX_CAPABLE_EXTENSION = /\.(tsx|jsx|mdx|vue|svelte|astro)$/i
const TS_EXTENSION = /\.ts$/i
const JS_EXTENSION = /\.(js|mjs|cjs)$/i

/**
 * La convention du PROJET, pas une convention inventee ici.
 *
 * `codeGeneratedFileParser.detectLanguage` etiquette `.tsx` en `typescript` et
 * `.jsx` en `javascript`. Une premiere version de ce module imposait `tsx`/`jsx`
 * comme libelles: mesure sur le livrable reel du run v126, **7 fichiers sur 31**
 * auraient ete « realignes » a chaque passe, puis re-etiquetes par l analyseur
 * a la generation suivante. Une reparation qui oscille contre l analyseur du
 * projet, et qui consomme une passe a chaque tour pour ne rien corriger.
 *
 * La coherence se mesure donc contre la table du projet. Sans cette
 * verification, le durcissement aurait introduit exactement le defaut qu il
 * pretend fermer.
 */
const LANGUAGE_FOR_EXTENSION: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
}

export type ExtensionFix = {
  from: string
  to: string
  reason: string
}

/**
 * Renomme uniquement ce qui CASSE: un `.ts` ou un `.js` qui contient du JSX.
 * Un `.tsx` sans JSX est parfaitement valide et n est pas touche — on ne
 * redecide pas a la place du modele quand rien n est casse.
 */
export function planExtensionFixes(files: CodeFile[]): ExtensionFix[] {
  const fixes: ExtensionFix[] = []
  const taken = new Set(files.map((file) => file.name.replace(/\\/g, '/')))
  for (const file of files) {
    const name = file.name.replace(/\\/g, '/')
    if (JSX_CAPABLE_EXTENSION.test(name)) continue
    if (!TS_EXTENSION.test(name) && !JS_EXTENSION.test(name)) continue
    if (!containsJsx(file.content)) continue
    const to = TS_EXTENSION.test(name)
      ? name.replace(TS_EXTENSION, '.tsx')
      : name.replace(JS_EXTENSION, '.jsx')
    // Ne jamais ecraser un fichier existant: on prefere ne rien faire et
    // laisser le diagnostic parler plutot que perdre du contenu.
    if (taken.has(to)) continue
    taken.add(to)
    fixes.push({
      from: name,
      to,
      reason: `${name} contient du JSX: hors d une extension JSX, le compilateur lit \`<\` comme une assertion de type puis une expression reguliere non terminee (TS1110/TS1161)`,
    })
  }
  return fixes
}

/** Le libelle de langage doit suivre l extension, jamais l inverse. */
function languageForName(name: string, fallback: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return LANGUAGE_FOR_EXTENSION[ext] ?? fallback
}

function rewriteReferences(content: string, fixes: ExtensionFix[]): string {
  let next = content
  for (const fix of fixes) {
    const base = fix.from.split('/').pop() ?? fix.from
    const withoutExt = base.replace(/\.[^.]+$/, '')
    const newBase = fix.to.split('/').pop() ?? fix.to
    // On ne remplace QUE les references qui portent l extension: les imports
    // sans extension (`./vitest.setup`) resolvent toujours. Ancre sur une
    // frontiere pour ne jamais reecrire deux fois.
    const pattern = new RegExp(`(^|[^\\w.-])${escapeRegExp(withoutExt)}\\.${escapeRegExp(base.split('.').pop() ?? '')}(?![\\w])`, 'g')
    next = next.replace(pattern, (_match, prefix: string) => `${prefix}${newBase}`)
  }
  return next
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Applique les renommages ET recolle les references qui portent l extension
 * (config vitest/vite `setupFiles`, `include` de tsconfig, imports explicites).
 * Renommer sans recoller casserait le projet autrement.
 */
export function applyExtensionFixes(files: CodeFile[], fixes: ExtensionFix[]): CodeFile[] {
  if (fixes.length === 0) return files
  const renamed = new Map(fixes.map((fix) => [fix.from, fix.to]))
  return files.map((file) => {
    const name = file.name.replace(/\\/g, '/')
    const nextName = renamed.get(name) ?? name
    return {
      ...file,
      name: nextName,
      language: languageForName(nextName, file.language),
      content: rewriteReferences(file.content, fixes),
    }
  })
}

/**
 * Accorde le libelle de langage sur l extension pour TOUS les fichiers — c est
 * l autre sens de la meme famille: un `.tsx` etiquete `typescript` recevait une
 * grammaire qui refuse le JSX.
 */
export function alignLanguageLabels(files: CodeFile[]): { files: CodeFile[]; changed: string[] } {
  const changed: string[] = []
  const next = files.map((file) => {
    const expected = languageForName(file.name.replace(/\\/g, '/'), file.language)
    if (expected === file.language) return file
    changed.push(`${file.name}: ${file.language} -> ${expected}`)
    return { ...file, language: expected }
  })
  return { files: next, changed }
}
