// ---------------------------------------------------------------------------
// codeMissingModuleCompletion — un composant IMPORTE est un composant VOULU.
//
// Run 1121: 37 fichiers livres, et la compilation TypeScript reporte 234
// erreurs sur l ensemble des passes. La famille structurante:
//
//   TS2307: Cannot find module '../components/StorySection'
//   TS2307: Cannot find module './Logo'
//
// Mesure exacte sur les fichiers reels: DEUX imports locaux non resolus.
//
//   src/components/Logo          <- src/components/Header.tsx
//   src/components/StorySection  <- src/pages/AboutPage.tsx
//
// Le modele a ecrit du code qui importe des composants que la file de
// generation ne lui a jamais demande d ecrire. La boucle a ensuite passe huit
// passes a discuter de typage (`'totalWeekly' n existe pas sur OrdersState`)
// alors que des FICHIERS ENTIERS manquaient.
//
// C est mecaniquement detectable, donc deterministe: on resout les imports
// locaux et on liste ceux qui ne pointent sur rien. Aucune ambiguite, aucune
// heuristique — et donc, ligne directrice constante du module, aucune raison de
// deleguer ce constat a un modele probabiliste.
//
// On ne se contente pas de le SIGNALER: on ajoute les fichiers manquants a la
// file. Un import est une intention explicite du modele; la file etait
// simplement incomplete par rapport a ce que le code reference.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'
import type { CodeGenerationQueueItem } from './codeGenerationQueue.ts'

const RESOLVABLE_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte', '.css', '.scss', '.json']

const SPECIFIER_PATTERNS = [
  /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"](\.[^'"]+)['"]/g,
  /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"](\.[^'"]+)['"]/g,
  /\bimport\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
  /\brequire\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
]

export type UnresolvedImport = {
  /** Fichier qui contient l import. */
  importer: string
  /** Specificateur ecrit dans le code (`../components/StorySection`). */
  specifier: string
  /** Chemin de projet vise, sans extension (`src/components/StorySection`). */
  targetPath: string
  /** Liaisons attendues par l importateur, pour ecrire les bons exports. */
  bindings: string[]
}

function normalize(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '')
}

function dirnameOf(path: string) {
  const clean = normalize(path)
  const index = clean.lastIndexOf('/')
  return index < 0 ? '' : clean.slice(0, index)
}

function joinProjectPath(dir: string, specifier: string) {
  const segments = `${dir ? `${dir}/` : ''}${specifier}`.split('/')
  const stack: string[] = []
  for (const segment of segments) {
    if (!segment || segment === '.') continue
    if (segment === '..') { stack.pop(); continue }
    stack.push(segment)
  }
  return stack.join('/')
}

function hasExplicitExtension(path: string) {
  return /\.[a-z0-9]+$/i.test(path.split('/').pop() ?? '')
}

function resolves(paths: Set<string>, target: string) {
  if (paths.has(target.toLowerCase())) return true
  if (hasExplicitExtension(target)) return false
  for (const ext of RESOLVABLE_EXTENSIONS) {
    if (paths.has(`${target}${ext}`.toLowerCase())) return true
    if (paths.has(`${target}/index${ext}`.toLowerCase())) return true
  }
  return false
}

/** Noms importes depuis ce specificateur, defaut compris. */
function bindingsFor(content: string, specifier: string): string[] {
  const escaped = specifier.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  // La clause ne peut contenir aucun guillemet: `[^'"]` empeche le motif de
  // franchir l import PRECEDENT (`import React from 'react'`) et de capturer
  // deux instructions d un coup — ce qui rendait toute liaison indetectable.
  const re = new RegExp(`import\\s+([^'"]*?)\\s+from\\s+['"]${escaped}['"]`, 'g')
  const found = new Set<string>()
  for (const match of content.matchAll(re)) {
    const clause = match[1].trim()
    const named = clause.match(/\{([^}]*)\}/)
    if (named) {
      for (const part of named[1].split(',')) {
        const name = part.split(/\s+as\s+/i)[0].trim().replace(/^type\s+/, '')
        if (name) found.add(name)
      }
    }
    const defaultName = clause.replace(/\{[^}]*\}/g, '').split(',')[0].trim().replace(/^type\s+/, '')
    if (defaultName && /^[A-Za-z_$][\w$]*$/.test(defaultName)) found.add(`default:${defaultName}`)
  }
  return [...found]
}

/** Imports locaux qui ne pointent sur aucun fichier livre. Exact, pas heuristique. */
export function findUnresolvedLocalImports(files: CodeFile[]): UnresolvedImport[] {
  const paths = new Set(files.map((file) => normalize(file.name).toLowerCase()))
  const seen = new Set<string>()
  const missing: UnresolvedImport[] = []

  for (const file of files) {
    if (!/\.[cm]?[jt]sx?$|\.vue$|\.svelte$/i.test(file.name)) continue
    for (const pattern of SPECIFIER_PATTERNS) {
      pattern.lastIndex = 0
      for (const match of file.content.matchAll(pattern)) {
        const specifier = match[1]
        const target = joinProjectPath(dirnameOf(file.name), specifier)
        if (!target || resolves(paths, target)) continue
        const key = target.toLowerCase()
        if (seen.has(key)) continue
        seen.add(key)
        missing.push({
          importer: file.name,
          specifier,
          targetPath: target,
          bindings: bindingsFor(file.content, specifier),
        })
      }
    }
  }
  return missing
}

/** Extension a donner au fichier manquant, deduite de l importateur et du nom. */
export function extensionForMissingModule(entry: UnresolvedImport): string {
  if (hasExplicitExtension(entry.targetPath)) return ''
  const importerExt = (entry.importer.match(/\.([cm]?[jt]sx?)$/i)?.[1] ?? 'ts').toLowerCase()
  const base = entry.targetPath.split('/').pop() ?? ''
  const looksLikeComponent = /^[A-Z]/.test(base)
  if (importerExt.endsWith('tsx') || importerExt.endsWith('jsx')) {
    return looksLikeComponent ? `.${importerExt}` : `.${importerExt.replace('x', '')}`
  }
  return `.${importerExt}`
}

function languageFor(path: string): string {
  if (/\.tsx$/i.test(path)) return 'tsx'
  if (/\.jsx$/i.test(path)) return 'jsx'
  if (/\.ts$/i.test(path)) return 'typescript'
  if (/\.css$/i.test(path)) return 'css'
  return 'javascript'
}

/**
 * Transforme les imports non resolus en elements de file. Ils sont `required`:
 * un module absent casse la compilation, ce n est pas un ornement.
 */
export function buildCompletionQueueItems(
  missing: UnresolvedImport[],
  startOrder: number,
  maxItems = 12,
): CodeGenerationQueueItem[] {
  return missing.slice(0, maxItems).map((entry, index) => {
    const path = `${entry.targetPath}${extensionForMissingModule(entry)}`
    const named = entry.bindings.filter((b) => !b.startsWith('default:'))
    const defaultBinding = entry.bindings.find((b) => b.startsWith('default:'))?.slice('default:'.length)
    return {
      path,
      order: startOrder + index,
      required: true,
      role: `Module importe par ${entry.importer} et absent du projet`,
      language: languageFor(path),
      imports: [],
      exports: [
        ...(defaultBinding ? [`default ${defaultBinding}`] : []),
        ...named,
      ],
      notes: [
        `Importe par ${entry.importer} via \`${entry.specifier}\`.`,
        defaultBinding
          ? `Il DOIT exposer un export par defaut utilisable comme \`${defaultBinding}\`.`
          : '',
        named.length > 0 ? `Il DOIT exporter: ${named.join(', ')}.` : '',
        'Ecris un module complet et coherent avec l usage qu en fait l importateur.',
      ].filter(Boolean),
    }
  })
}

export function describeMissingModules(missing: UnresolvedImport[]): string {
  if (missing.length === 0) return ''
  return `${missing.length} module(s) importe(s) mais absent(s): ${missing.map((m) => m.targetPath).slice(0, 8).join(', ')}`
}

/**
 * Ordre causal des erreurs de compilation.
 *
 * Run 1121: 234 erreurs TypeScript, dont des `TS2307` (module introuvable) et
 * une nuee de `TS2339`/`TS7006` DANS LES MEMES FICHIERS. La boucle a discute du
 * typage de `OrdersState` pendant que `StorySection` et `Logo` n existaient pas.
 * Un fichier qui importe un module absent ne peut pas etre type correctement:
 * ses autres erreurs sont des consequences, pas des defauts.
 *
 * Meme regle que pour le crash runtime: on repare la cause, on ne conclut rien
 * des mesures que la cause a rendues impossibles.
 */
export function prioritizeCompileErrors(output: string): string {
  const text = String(output ?? '')
  if (!text.trim()) return text
  const lines = text.split('\n')
  const structural = lines.filter((line) => /error\s+TS2307/i.test(line))
  if (structural.length === 0) return text

  const affected = new Set<string>()
  for (const line of structural) {
    const file = line.match(/^([^\s(]+)\s*\(/)?.[1]
    if (file) affected.add(normalize(file).toLowerCase())
  }
  const downstream = lines.filter((line) => {
    if (/error\s+TS2307/i.test(line)) return false
    const file = line.match(/^([^\s(]+)\s*\(/)?.[1]
    return Boolean(file && affected.has(normalize(file).toLowerCase()))
  })

  return [
    '## CAUSE STRUCTURELLE — MODULES INTROUVABLES',
    'Ces imports ne pointent sur aucun fichier du projet. Cree ces modules (ou retire',
    'l import): tant qu ils manquent, le fichier ne peut PAS etre type correctement.',
    ...structural.slice(0, 20),
    '',
    downstream.length > 0
      ? `## ${downstream.length} autre(s) erreur(s) DANS CES MEMES FICHIERS — probablement des consequences`
      : '',
    downstream.length > 0
      ? 'Ne les traite pas avant d avoir resolu les modules ci-dessus: elles disparaissent souvent d elles-memes.'
      : '',
    ...downstream.slice(0, 10),
    '',
    '## SORTIE COMPLETE',
    text,
  ].filter(Boolean).join('\n')
}
