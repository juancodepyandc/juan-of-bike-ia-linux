/**
 * Tests pour les analyses structurelles.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeCyclomaticComplexity,
  buildImportGraph,
  computeHalstead,
  detectDeadCode,
} from '../services/codeStructuralAnalysis.ts'

describe('Cyclomatic complexity — barre expert', () => {
  test('fonction simple → CC = 1', () => {
    const code = `function id(x: number) { return x }`
    const r = analyzeCyclomaticComplexity(code, 'ts')
    assert.equal(r.length, 1)
    assert.equal(r[0].cyclomaticComplexity, 1)
    assert.equal(r[0].rating, 'simple')
  })

  test('if + else + 2 && → CC = 4', () => {
    const code = `
function f(x: number, y: number) {
  if (x > 0 && y > 0 && x < 100) {
    return 1
  } else {
    return 2
  }
}
`
    const r = analyzeCyclomaticComplexity(code, 'ts')
    // 1 (base) + 1 if + 2 && = 4
    assert.equal(r[0].cyclomaticComplexity, 4)
  })

  test('boucle for + switch case → CC > 5', () => {
    const code = `
function f(arr: number[]) {
  let total = 0
  for (const x of arr) {
    switch (x) {
      case 1: total += 1; break
      case 2: total += 2; break
      case 3: total += 3; break
      default: total -= 1
    }
  }
  return total
}
`
    const r = analyzeCyclomaticComplexity(code, 'ts')
    assert.ok(r[0].cyclomaticComplexity >= 5)
  })

  test('CC ≥ 41 → rating "très-complexe" ou "ingérable"', () => {
    // Génère une fonction avec 50 if
    let body = ''
    for (let i = 0; i < 50; i += 1) body += `  if (x === ${i}) return ${i}\n`
    const code = `function f(x: number) {\n${body}  return -1\n}`
    const r = analyzeCyclomaticComplexity(code, 'ts')
    assert.ok(['très-complexe', 'ingérable'].includes(r[0].rating))
  })

  test('Python def avec elif chain', () => {
    const code = `
def f(x):
    if x > 0:
        return 1
    elif x > -10:
        return 0
    else:
        return -1
`
    const r = analyzeCyclomaticComplexity(code, 'py')
    assert.equal(r.length, 1)
    // base 1 + if 1 + elif 1 = 3
    assert.equal(r[0].cyclomaticComplexity, 3)
  })

  test('plusieurs fonctions Python détectées', () => {
    const code = `
def a():
    return 1

def b(x):
    if x: return 1
    return 0
`
    const r = analyzeCyclomaticComplexity(code, 'py')
    assert.equal(r.length, 2)
    assert.equal(r[0].name, 'a')
    assert.equal(r[1].name, 'b')
  })
})

describe('Dead code detector', () => {
  test('import non utilisé détecté', () => {
    const code = `import { foo } from 'lib'\nexport const x = 1\n`
    const issues = detectDeadCode(code, 'ts')
    assert.ok(issues.some((i) => i.kind === 'unused-import' && i.symbol === 'foo'))
  })

  test('import utilisé non flaggé', () => {
    const code = `import { foo } from 'lib'\nexport const x = foo()\n`
    const issues = detectDeadCode(code, 'ts')
    assert.equal(issues.filter((i) => i.kind === 'unused-import').length, 0)
  })

  test('if (true) détecté', () => {
    const code = `if (true) { console.log('hi') }`
    const issues = detectDeadCode(code, 'ts')
    assert.ok(issues.some((i) => i.kind === 'always-true'))
  })

  test('code après return → unreachable', () => {
    const code = `function f() {\n  return 1\n  console.log("dead")\n}`
    const issues = detectDeadCode(code, 'ts')
    assert.ok(issues.some((i) => i.kind === 'unreachable'))
  })

  test('imports * as Name détecté + utilisé', () => {
    const code = `import * as React from 'react'\nexport const x = React.useState()\n`
    const issues = detectDeadCode(code, 'ts')
    assert.equal(issues.filter((i) => i.kind === 'unused-import').length, 0)
  })

  test('default import non utilisé détecté', () => {
    const code = `import lib from 'thing'\nconst x = 1\n`
    const issues = detectDeadCode(code, 'ts')
    assert.ok(issues.some((i) => i.symbol === 'lib'))
  })
})

describe('Import graph + cycles', () => {
  test('graphe linéaire sans cycle', () => {
    const files = [
      { name: 'a.ts', content: `import { b } from './b'\nexport const x = b()` },
      { name: 'b.ts', content: `import { c } from './c'\nexport const b = () => c` },
      { name: 'c.ts', content: `export const c = 1` },
    ]
    const g = buildImportGraph(files)
    assert.equal(g.cycles.length, 0)
    assert.equal(g.edges.length, 2)
  })

  test('cycle 2-fichiers détecté', () => {
    const files = [
      { name: 'a.ts', content: `import { b } from './b'\nexport const a = b` },
      { name: 'b.ts', content: `import { a } from './a'\nexport const b = a` },
    ]
    const g = buildImportGraph(files)
    assert.ok(g.cycles.length >= 1)
  })

  test('cycle 3-fichiers détecté', () => {
    const files = [
      { name: 'a.ts', content: `import { b } from './b'` },
      { name: 'b.ts', content: `import { c } from './c'` },
      { name: 'c.ts', content: `import { a } from './a'` },
    ]
    const g = buildImportGraph(files)
    assert.ok(g.cycles.length >= 1)
  })
})

describe('Halstead metrics', () => {
  test('fonction triviale → bugs prédits faibles', () => {
    const code = `function id(x: number) { return x }`
    const h = computeHalstead(code, 'ts')
    assert.ok(h.predictedBugs < 0.05, `bugs ${h.predictedBugs}`)
  })

  test('vocabulary + length consistant', () => {
    const code = `function f(x: number) { return x * 2 + 1 }`
    const h = computeHalstead(code, 'ts')
    assert.ok(h.n1 > 0)
    assert.ok(h.n2 > 0)
    assert.equal(h.vocabulary, h.n1 + h.n2)
    assert.equal(h.length, h.N1 + h.N2)
  })

  test('volume > 0 si code non vide', () => {
    const code = `const x = 1\nconst y = x + 2`
    const h = computeHalstead(code, 'ts')
    assert.ok(h.volume > 0)
  })

  test('Python : retourne metrics 0 (Python pas géré)', () => {
    const code = `def f(x): return x`
    const h = computeHalstead(code, 'py')
    assert.equal(h.volume, 0)
  })
})
