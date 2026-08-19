// ---------------------------------------------------------------------------
// codeArrayContainerAccess — la destructuration oubliee.
//
// MESURE (run v131, 8 occurrences sur 72 erreurs):
//
//   Property 'map' does not exist on type
//     '{ events: MarketEvent[]; loading: boolean; error: string; }'
//
// Un hook rend un OBJET d etat `{ events, loading, error }`, et l appelant fait
// `.map()` directement dessus au lieu de `.events.map()`.
//
// Rien a deviner ici, tout est ECRIT: le compilateur imprime le type complet.
// Il contient exactement UN tableau, et la propriete reclamee est une methode
// de tableau. La cible est donc unique — c est le meme principe que la
// reconciliation import/export: on LIT le contrat au lieu de le supposer.
//
// Quand le type contient zero ou plusieurs tableaux, on ne touche a rien: le
// choix redeviendrait une decision, et une decision ne se confie pas a un
// patcheur mecanique.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

/** Methodes et proprietes qui n existent que sur un tableau. */
const ARRAY_MEMBERS = new Set([
  'map', 'filter', 'forEach', 'reduce', 'reduceRight', 'some', 'every', 'find',
  'findIndex', 'findLast', 'flatMap', 'flat', 'slice', 'sort', 'reverse',
  'join', 'includes', 'indexOf', 'lastIndexOf', 'concat', 'at', 'length', 'keys', 'entries',
])

const TS2339_OBJECT = /([\w@./\\-]+\.(?:tsx?|jsx?))\((\d+),(\d+)\):\s*error TS2339: Property '([A-Za-z_$][\w$]*)' does not exist on type '\{([^}]*)\}'/g

export type ArrayContainerFix = {
  file: string
  line: number
  member: string
  container: string
  before: string
  after: string
}

/** Extrait l unique propriete tableau d un type litteral imprime par tsc. */
export function soleArrayProperty(typeBody: string): string | null {
  const arrays: string[] = []
  for (const part of typeBody.split(';')) {
    const match = /^\s*([A-Za-z_$][\w$]*)\s*\??\s*:\s*(.+?)\s*$/.exec(part)
    if (!match) continue
    const type = match[2].trim()
    if (/\[\]$/.test(type) || /^(?:Array|ReadonlyArray)</.test(type)) arrays.push(match[1])
  }
  return arrays.length === 1 ? arrays[0] : null
}

const normalize = (name: string) => name.replace(/\\/g, '/')

export function planArrayContainerFixes(files: CodeFile[], compilerOutput: string): ArrayContainerFix[] {
  const fixes: ArrayContainerFix[] = []
  const seen = new Set<string>()
  let match: RegExpExecArray | null
  TS2339_OBJECT.lastIndex = 0
  while ((match = TS2339_OBJECT.exec(compilerOutput)) !== null) {
    const [, rawPath, rawLine, , member, typeBody] = match
    if (!ARRAY_MEMBERS.has(member)) continue
    const container = soleArrayProperty(typeBody)
    if (!container) continue
    if (container === member) continue

    const wanted = normalize(rawPath).replace(/^\.\//, '')
    const file = files.find((f) => {
      const name = normalize(f.name)
      return name === wanted || name.endsWith(`/${wanted}`) || wanted.endsWith(name)
    })
    if (!file) continue

    const lineIndex = Number(rawLine) - 1
    const lines = file.content.split('\n')
    const source = lines[lineIndex]
    if (source === undefined) continue

    // `<expr>.<member>` -> `<expr>.<container>.<member>`, sans toucher a un
    // acces deja correct.
    const access = new RegExp(`([A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*)*)\\.${member}\\b`)
    const found = access.exec(source)
    if (!found) continue
    if (found[1].endsWith(`.${container}`)) continue

    const key = `${normalize(file.name)}:${lineIndex}:${member}`
    if (seen.has(key)) continue
    seen.add(key)
    fixes.push({
      file: normalize(file.name),
      line: lineIndex,
      member,
      container,
      before: found[0],
      after: `${found[1]}.${container}.${member}`,
    })
  }
  return fixes
}

/** Applique les correctifs. Fonction pure. */
export function applyArrayContainerFixes(files: CodeFile[], fixes: ArrayContainerFix[]): CodeFile[] {
  if (fixes.length === 0) return files
  const byFile = new Map<string, ArrayContainerFix[]>()
  for (const fix of fixes) {
    const list = byFile.get(fix.file) ?? []
    list.push(fix)
    byFile.set(fix.file, list)
  }
  return files.map((file) => {
    const list = byFile.get(normalize(file.name))
    if (!list) return file
    const lines = file.content.split('\n')
    for (const fix of list) {
      const source = lines[fix.line]
      if (source === undefined || !source.includes(fix.before)) continue
      lines[fix.line] = source.replace(fix.before, fix.after)
    }
    return { ...file, content: lines.join('\n') }
  })
}

export function describeArrayContainerFixes(fixes: ArrayContainerFix[]): string {
  return fixes.map((f) => `${f.file}:${f.line + 1} ${f.before} -> ${f.after}`).join(' ; ')
}
