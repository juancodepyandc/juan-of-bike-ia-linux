import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, basename, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// ---------------------------------------------------------------------------
// Garde anti-orphelin (transverse).
//
// Le Module Code a un historique de "capacites livrables debranchees": du code
// phare implemente + teste en vase clos, mais JAMAIS appele depuis le chemin de
// production (cf. aurora_code_loop.py, puis WS6/WS8/WS10/WS2/WS5 lors de la
// refonte). Un test vert n y changeait rien tant que la capacite restait inerte.
//
// Ce garde echoue si l une de ces capacites perd son (ses) appelant(s) de
// production — c.-a-d. n est plus referencee dans AUCUN fichier source hors de
// sa propre definition et hors des tests. Il rend la regression structurelle
// impossible a merger sans que la suite ne casse.
// ---------------------------------------------------------------------------

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')

function walkSourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const stats = statSync(full)
    if (stats.isDirectory()) {
      if (entry === '__tests__' || entry === 'node_modules') continue
      out.push(...walkSourceFiles(full))
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(full)
    }
  }
  return out
}

type GuardedCapability = {
  ws: string
  symbol: string
  definedIn: string
}

// Chaque entree = une capacite qui DOIT rester cablee au chemin de production.
const GUARDED_CAPABILITIES: GuardedCapability[] = [
  { ws: 'WS6', symbol: 'classifyCodeIntentWithSemanticModel', definedIn: 'codeSemanticIntentClassifier.ts' },
  { ws: 'WS6', symbol: 'buildProjectGeneratorPromptBlock', definedIn: 'codeProjectGeneratorRegistry.ts' },
  { ws: 'WS10', symbol: 'verifyCodeDesignSpecAgainstFiles', definedIn: 'codeDesignSpec.ts' },
  { ws: 'WS10', symbol: 'buildCodeDesignSpec', definedIn: 'codeDesignSpec.ts' },
  { ws: 'WS8', symbol: 'parseCodeWithTreeSitter', definedIn: 'codeTreeSitterAst.ts' },
  { ws: 'WS2', symbol: 'writeCodeFilesToDirectory', definedIn: 'codeProjectWriter.ts' },
  { ws: 'WS2', symbol: 'parseCodeFilesWithReport', definedIn: 'codeGeneratedFileParser.ts' },
  { ws: 'WS5', symbol: 'assertCodePatchNonRegression', definedIn: 'codeIncrementalPatchScope.ts' },
  { ws: 'WS9', symbol: 'blendRenderedVisualIntoFinalScore', definedIn: 'codeVisualAuditClient.ts' },
  { ws: 'WS14', symbol: 'evaluateAutoToolingForCorrection', definedIn: 'codeToolingLoop.ts' },
]

describe('anti-orphelin: chaque capacite livrable a un appelant de production', () => {
  const sourceFiles = walkSourceFiles(SRC_DIR)
  // Cache des contenus pour eviter de relire les memes fichiers a chaque cas.
  const contents = new Map<string, string>(sourceFiles.map((path) => [path, readFileSync(path, 'utf8')]))

  for (const capability of GUARDED_CAPABILITIES) {
    test(`${capability.ws}: ${capability.symbol} est reference hors de sa definition (chemin de prod, hors tests)`, () => {
      const callerRegex = new RegExp(`\\b${capability.symbol}\\b`)
      const callers = sourceFiles.filter((path) =>
        basename(path) !== capability.definedIn && callerRegex.test(contents.get(path) ?? ''),
      )
      assert.ok(
        callers.length > 0,
        `${capability.symbol} (${capability.ws}) est ORPHELIN: aucun appelant de production. `
          + 'Cette capacite a ete livree puis debranchee — cable-la au pipeline reel ou retire-la.',
      )
    })
  }
})
