import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, test } from 'node:test'

import {
  buildClosureRepairDirective,
  buildModuleGraph,
  buildTransitiveClosure,
  exportsSymbol,
  resolveImport,
  symbolsFromErrors,
} from '../services/codeTransitiveClosure.ts'

const ROOT = 'output/code/audit_v124/livrable'

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

function realDeliverable() {
  return walk(ROOT).map((path) => ({
    name: path.slice(ROOT.length + 1),
    language: 'typescript',
    content: readFileSync(path, 'utf8'),
  }))
}

describe('fermeture transitive — le fichier qui plante n est pas celui a reparer', () => {
  test('un import relatif se resout, un paquet externe ne se resout pas', () => {
    const files = [
      { name: 'src/components/A.tsx', language: 'ts', content: '' },
      { name: 'src/stores/orderStore.ts', language: 'ts', content: '' },
      { name: 'src/types/index.ts', language: 'ts', content: '' },
    ]
    assert.equal(resolveImport('src/components/A.tsx', '../stores/orderStore', files), 'src/stores/orderStore.ts')
    // Un dossier resout vers son index.
    assert.equal(resolveImport('src/components/A.tsx', '../types', files), 'src/types/index.ts')
    // Une dependance externe n appartient pas au projet: on ne peut pas la reparer.
    assert.equal(resolveImport('src/components/A.tsx', 'react', files), null)
  })

  test('un export se LIT, il ne se devine pas', () => {
    assert.ok(exportsSymbol('export interface Order { id: number }', 'Order'))
    assert.ok(exportsSymbol('export type Order = { id: number }', 'Order'))
    assert.ok(exportsSymbol('const Order = 1\nexport { Order }', 'Order'))
    // Une simple mention n est pas une declaration.
    assert.equal(exportsSymbol('const x: Order = y', 'Order'), false)
    assert.equal(exportsSymbol('export interface OrderState {}', 'Order'), false)
  })

  test('seuls les symboles CITES par le compilateur sont retenus', () => {
    const symbols = symbolsFromErrors("error TS2304: Cannot find name 'Order'. error TS2339: 'clearOrders' on 'OrderState'")
    assert.deepEqual(symbols.sort(), ['Order', 'OrderState', 'clearOrders'])
    assert.deepEqual(symbolsFromErrors('error TS1002: Unterminated string literal.'), [])
  })

  // ---- Mesures sur le LIVRABLE REEL du run 1191 (39 fichiers) --------------
  test('le contrat de types reparti du run 1171 est referme, sur des fichiers reels', () => {
    const files = realDeliverable()
    const closure = buildTransitiveClosure({
      files,
      seeds: ['src/components/AdminDashboard.tsx'],
      errors: "src/components/AdminDashboard.tsx(146,3): error TS2304: Cannot find name 'Order'.",
    })

    // Le fichier fautif, mais surtout: les DEUX modules qui declarent `Order`.
    // C est cette ambiguite qui a fait osciller neuf passes au run 1171, et on
    // la retrouve telle quelle sur le livrable d un AUTRE run.
    assert.ok(closure.paths.includes('src/components/AdminDashboard.tsx'))
    assert.ok(closure.paths.includes('src/stores/orderStore.ts'))
    assert.ok(closure.paths.includes('src/types/index.ts'))
    assert.match(closure.reasons['src/stores/orderStore.ts'], /AMBIGUE \(2 modules\)/)
    assert.match(closure.reasons['src/types/index.ts'], /AMBIGUE \(2 modules\)/)
    // …et les consommateurs, sans qui la decision ne peut pas etre appliquee.
    assert.ok(closure.paths.some((path) => /OrderList|OrderItem|StatsPanel/.test(path)))
    // Chaque chemin porte sa raison: jamais de portee muette.
    for (const path of closure.paths) assert.ok(closure.reasons[path]?.length > 0)
  })

  test('l arbre de montage du run 1181 est traversable, sur des fichiers reels', () => {
    const graph = buildModuleGraph(realDeliverable())
    // La trace nommait les routes; la cause vivait au point d entree. Le graphe
    // relie l un a l autre — c est ce qui manquait a la passe ciblee.
    assert.ok(graph.imports.get('src/main.tsx')?.has('src/App.tsx'))
    assert.ok(graph.importedBy.get('src/routes/index.tsx')?.has('src/App.tsx'))
  })

  test('la portee reste bornee: au-dela on ne repare plus, on regenere', () => {
    const files = realDeliverable()
    const closure = buildTransitiveClosure({
      files,
      seeds: ['src/components/AdminDashboard.tsx'],
      errors: "Cannot find name 'Order'. Cannot find name 'OrderState'.",
      maxPaths: 3,
    })
    assert.equal(closure.paths.length, 3)
    assert.equal(Object.keys(closure.reasons).length, 3)
    // Le fichier fautif passe devant tout le reste.
    assert.equal(closure.paths[0], 'src/components/AdminDashboard.tsx')
  })

  test('la consigne nomme le cycle et interdit le va-et-vient', () => {
    const closure = buildTransitiveClosure({
      files: realDeliverable(),
      seeds: ['src/components/AdminDashboard.tsx'],
      errors: "Cannot find name 'Order'.",
    })
    const directive = buildClosureRepairDirective(closure, "AdminPage.tsx|TS2304|Cannot find name 'Order'")
    assert.match(directive, /CYCLE a ete mesure/)
    assert.match(directive, /RECREE le defaut de l autre/)
    assert.match(directive, /UNE declaration\nfaisant autorite/)
    for (const path of closure.paths) assert.ok(directive.includes(path))
    // Sans cycle, la consigne existe mais n invente aucun cycle.
    assert.doesNotMatch(buildClosureRepairDirective(closure, null), /CYCLE a ete mesure/)
  })
})
