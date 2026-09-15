#!/usr/bin/env node
/**
 * Reparation des LIVRABLES REELS, avec les reparations que le projet EMBARQUE.
 *
 * On n'invente aucun correctif ici : on rejoue sur les fichiers presents dans
 * `application/output/` les memes fonctions qui tournent en production —
 * `sanitizeGeneratedFileContent` (apostrophes francaises, balises Markdown,
 * JSON approximatif) et `parseProjectTreeEmission` (enveloppe de protocole
 * multi-fichiers). Si la reparation embarquee ne suffit pas, on le DIT plutot
 * que de bricoler a cote.
 *
 * Chaque fichier repare est verifie par le COMPILATEUR TypeScript avant et
 * apres : on ne remplace un fichier que si le nombre de diagnostics baisse.
 * L original est conserve sous `<nom>.avant-reparation`.
 *
 *   node --experimental-strip-types scripts/reparer-livrables.mjs [--appliquer]
 *
 * Sans `--appliquer`, rien n'est ecrit : la sortie montre ce qui serait fait.
 */
import { createRequire } from 'node:module'
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync } from 'node:fs'
import { join, relative, extname, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { sanitizeGeneratedFileContent } from '../src/services/codeGeneratedFileSanitizer.ts'
import { isStructuredProjectEmission, parseProjectTreeEmission } from '../src/services/codeProjectEmission.ts'

const require_ = createRequire(import.meta.url)
const ts = require_('typescript')

const RACINE = fileURLToPath(new URL('..', import.meta.url))
const CIBLE = join(RACINE, 'output', 'code')
const APPLIQUER = process.argv.includes('--appliquer')

// On ne touche qu'au LIVRABLE. `target/`, `.fingerprint/` et consorts sont des
// artefacts de construction : les reformater serait du bruit, pas une reparation.
const IGNORE = new Set(['node_modules', 'dist', '.git', '.vite', 'build', 'coverage',
                        'target', '.fingerprint', '.cargo', 'venv', '__pycache__'])
const KIND = { '.ts': 'TS', '.mts': 'TS', '.cts': 'TS', '.tsx': 'TSX', '.jsx': 'TSX',
               '.js': 'JS', '.mjs': 'JS', '.cjs': 'JS' }

function diagnostics(contenu, ext, chemin) {
  if (!KIND[ext]) return null
  const kind = { TS: ts.ScriptKind.TS, TSX: ts.ScriptKind.TSX, JS: ts.ScriptKind.JS }[KIND[ext]]
  const sf = ts.createSourceFile(chemin, contenu, ts.ScriptTarget.Latest, true, kind)
  return (sf.parseDiagnostics || []).length
}

function marche(dossier, out = []) {
  let entrees
  try { entrees = readdirSync(dossier, { withFileTypes: true }) } catch { return out }
  for (const e of entrees) {
    if (IGNORE.has(e.name) || e.name.endsWith('.avant-reparation')) continue
    const p = join(dossier, e.name)
    if (e.isDirectory()) marche(p, out)
    else out.push(p)
  }
  return out
}

const actions = []

for (const f of marche(CIBLE)) {
  const ext = extname(f)
  let contenu
  try { contenu = readFileSync(f, 'utf8') } catch { continue }
  const rel = relative(RACINE, f)

  // --- 1. Enveloppe de protocole ecrite telle quelle -----------------------
  if (isStructuredProjectEmission(contenu)) {
    const r = parseProjectTreeEmission(contenu)
    const fichiers = r?.tree?.files || r?.files || []
    if (fichiers.length > 0) {
      const cible = join(dirname(f), '_extrait_' + basename(f, ext))
      actions.push({
        type: 'enveloppe-de-protocole', fichier: rel,
        quoi: `${fichiers.length} fichier(s) recuperes de l enveloppe`,
        detail: fichiers.slice(0, 4).map((x) => x.name || x.path).join(', '),
        appliquer: () => {
          for (const item of fichiers) {
            const nom = item.name || item.path
            if (!nom) continue
            const dest = join(cible, nom)
            mkdirSync(dirname(dest), { recursive: true })
            writeFileSync(dest, item.content ?? '', 'utf8')
          }
          writeFileSync(f + '.avant-reparation', contenu, 'utf8')
          writeFileSync(f, `// Enveloppe de protocole ${'AURORA_CODE_VFS/1'} depliee par\n`
            + `// scripts/reparer-livrables.mjs. Les ${fichiers.length} fichiers qu'elle portait\n`
            + `// se trouvent dans ./_extrait_${basename(f, ext)}/ ; l'original est conserve\n`
            + `// sous ${basename(f)}.avant-reparation\n`, 'utf8')
        },
      })
      continue
    }
  }

  // --- 2. Reparation embarquee, verifiee par le compilateur ---------------
  if (!KIND[ext] && ext !== '.json' && ext !== '.md') continue
  const avant = diagnostics(contenu, ext, f)
  // On ne repare QUE ce qui est casse. Premiere version de cet outil : elle
  // proposait 270 « reparations » dont la quasi-totalite n'etaient qu'un
  // reindentage de JSON parfaitement valide — des payloads d'audit et des
  // artefacts de construction Rust. Reecrire un fichier sain n'est pas une
  // reparation, c'est une modification gratuite, et elle efface la trace de
  // ce qu'il contenait.
  if (avant === null || avant === 0) continue
  let repare
  try { repare = sanitizeGeneratedFileContent(basename(f), contenu) } catch { continue }
  if (repare === contenu) {
    // La reparation embarquee ne change rien alors que le compilateur refuse
    // le fichier : le contenu MANQUE. Le dire, plutot que de passer en
    // silence — un fichier casse qu'aucun outil ne signale est pire qu'un
    // fichier casse qu'on nomme.
    actions.push({ type: 'irreparable', fichier: rel,
                   quoi: `${avant} diagnostic(s) que la reparation embarquee ne resout pas`,
                   detail: 'contenu perdu a la generation : il faut REGENERER, pas rafistoler' })
    continue
  }
  const apres = diagnostics(repare, ext, f)
  if (apres !== null && apres >= avant) {
    if (avant > 0) {
      actions.push({ type: 'irreparable', fichier: rel,
                     quoi: `${avant} diagnostic(s) ; la reparation embarquee n'y change rien`,
                     detail: 'contenu perdu a la generation : il faut REGENERER, pas rafistoler' })
    }
    continue
  }
  actions.push({
    type: 'reparation-embarquee', fichier: rel,
    quoi: `${avant} diagnostic(s) -> ${apres}`,
    detail: '',
    appliquer: () => {
      writeFileSync(f + '.avant-reparation', contenu, 'utf8')
      writeFileSync(f, repare, 'utf8')
    },
  })
}

console.log(`\n\x1b[1mREPARATION DES LIVRABLES REELS\x1b[0m — ${CIBLE}`)
console.log('='.repeat(100))
if (!actions.length) console.log('\x1b[32maucune reparation necessaire\x1b[0m')
for (const a of actions) {
  const couleur = a.type === 'irreparable' ? '\x1b[31m' : '\x1b[33m'
  console.log(`${couleur}${a.type}\x1b[0m  ${join(RACINE, a.fichier)}`)
  console.log(`   ${a.quoi}${a.detail ? '  |  ' + a.detail : ''}`)
  if (APPLIQUER && a.appliquer) a.appliquer()
}
console.log('-'.repeat(100))
const reparables = actions.filter((a) => a.appliquer).length
console.log(APPLIQUER
  ? `\x1b[32m${reparables} fichier(s) repare(s)\x1b[0m — originaux conserves en .avant-reparation`
  : `${reparables} reparation(s) possible(s) ; relancer avec --appliquer pour les ecrire`)
const perdus = actions.filter((a) => a.type === 'irreparable').length
if (perdus) console.log(`\x1b[31m${perdus} fichier(s) irreparables\x1b[0m : le contenu manque, il faut regenerer`)
