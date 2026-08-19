/**
 * Test de PARITÉ TS↔Python du contrat VideoJobSpec.
 *
 * Charge les fixtures générées par `python-services/gen_video_parity_fixtures.py`
 * — chaque entrée = { intent, expected_spec_hash }. Reconstruit la spec côté
 * TS via `buildSpecFromIntent`, calcule `specHash`, exige l'égalité byte-à-byte.
 *
 * Toute divergence est un bug de parité — c'est le comportement voulu, elle
 * doit casser CI plutôt que se corriger silencieusement.
 */

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { buildSpecFromIntent, deterministicSeedFromPrompt } from '../services/videoSpecBuilder.ts'
import { specHash } from '../services/videoJobSpec.ts'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURE_PATH = resolve(HERE, 'fixtures', 'video-spec-hashes.json')

type FixtureEntry = {
  intent: Record<string, unknown>
  expected_spec_hash: string
  resolved: Record<string, unknown>
}

type FixtureFile = {
  spec_version: number
  count: number
  entries: FixtureEntry[]
}

function loadFixtures(): FixtureFile {
  return JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8')) as FixtureFile
}

test('parité TS↔Python : chaque intent → spec_hash identique', () => {
  const file = loadFixtures()
  assert.ok(file.entries.length > 0, 'fixtures vides — régénérer via gen_video_parity_fixtures.py')

  for (const entry of file.entries) {
    // Le fixture contient des snake_case (contrat Python). buildSpecFromIntent
    // TS accepte les mêmes clés — mapping direct.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const spec = buildSpecFromIntent(entry.intent as any)
    const actual = specHash(spec)
    assert.strictEqual(
      actual,
      entry.expected_spec_hash,
      `divergence de hash pour intent ${JSON.stringify(entry.intent)}\n` +
        `  attendu (Python) : ${entry.expected_spec_hash}\n` +
        `  obtenu (TS)      : ${actual}\n` +
        `  résolution Python : ${JSON.stringify(entry.resolved)}\n` +
        `  résolution TS    : w=${spec.width}×${spec.height}, delivered=${spec.delivered_width}×${spec.delivered_height}, ` +
        `frames=${spec.num_frames}, steps=${spec.num_inference_steps}, seed=${spec.seed}\n` +
        `  prompt_composed TS : ${JSON.stringify(spec.prompt_composed)}`,
    )
  }
})

test('FNV-1a deterministicSeedFromPrompt : valeur de contrôle depuis fixture', () => {
  // Le fixture intent[0] (prompt "a red bike rolling down a hill", pas de motion_suffix)
  // documente seed=1122230888 côté Python. Si cette valeur diverge en TS, la boucle
  // FNV-1a est cassée et tous les seeds dérivés le sont aussi. Test dur.
  assert.strictEqual(deterministicSeedFromPrompt('a red bike rolling down a hill'), 1122230888)
})
