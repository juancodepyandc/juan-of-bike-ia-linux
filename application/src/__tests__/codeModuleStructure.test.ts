import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, test } from 'node:test'

const SOURCE_ROOTS = ['src/services', 'src/views', 'src/components', 'src/stores', 'src/hooks']
const PYTHON_ROOT = 'python-services/aurora_code'
const DEAD_MODULES = ['codeImageGen', 'codeOutputElevate', 'codeDeterministicPatcher', 'CodeDiff']

function walk(root: string): string[] {
  return readdirSync(root).flatMap((name) => {
    const path = join(root, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

function productionCodeFiles(): string[] {
  const frontend = SOURCE_ROOTS
    .flatMap(walk)
    .filter((path) => /\.(ts|tsx)$/.test(path) && /code/i.test(path.split('/').pop() || ''))
  const services = walk(PYTHON_ROOT)
    .filter((path) => /\.(py|mjs)$/.test(path) && !/(^|\/)test_|__pycache__/.test(path))
  return [...frontend, ...services].sort()
}

function lineCount(path: string): number {
  const source = readFileSync(path, 'utf8')
  return source.split(/\r?\n/).length - (source.endsWith('\n') ? 1 : 0)
}

describe('WS1 module Code structure', () => {
  test('chaque unite de production reste strictement sous 400 lignes', () => {
    const oversized = productionCodeFiles()
      .map((path) => ({ path, lines: lineCount(path) }))
      .filter(({ lines }) => lines >= 400)
    assert.deepEqual(oversized, [])
  })

  test('aucun import du code mort supprime ne reapparait', () => {
    const corpus = SOURCE_ROOTS.flatMap(walk)
      .filter((path) => /\.(ts|tsx)$/.test(path) && !path.includes('/__tests__/'))
      .map((path) => `${path}\n${readFileSync(path, 'utf8')}`)
      .join('\n')
    for (const deadModule of DEAD_MODULES) {
      assert.doesNotMatch(corpus, new RegExp(`(?:from\\s+['"][^'"]*|import\\s*\\(['"][^'"]*)${deadModule}`))
    }
  })
})
