/**
 * Smoke tests for the v80ag mesh stage priority — the React app was picking
 * stale GLB paths from session history because findSessionAssets returned
 * the FIRST .glb match per message. Result: viewer fell back to reference
 * image when the early-stage path no longer existed on disk.
 *
 * This test mirrors the same regex array used in ModelView.tsx and verifies
 * that newer pipeline stages outrank older ones.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const MESH_STAGE_PRIORITY: { match: RegExp; rank: number }[] = [
  { match: /_split_k\d+\.glb$/i,        rank: 100 },
  { match: /_split\.glb$/i,             rank:  95 },
  { match: /_anim(_v\d+)?\.glb$/i,      rank:  90 },
  { match: /_textured\.glb$/i,          rank:  80 },
  { match: /_RIGGED.*\.glb$/i,          rank:  70 },
  { match: /_manifoldfixed\.glb$/i,     rank:  60 },
  { match: /_reshaped\.glb$/i,          rank:  55 },
  { match: /_baked\.glb$/i,             rank:  50 },
  { match: /_mesh\.glb$/i,              rank:  40 },
  { match: /\.(glb|gltf|obj)$/i,        rank:  10 },
]

function rank(filePath: string): number {
  for (const { match, rank } of MESH_STAGE_PRIORITY) {
    if (match.test(filePath)) return rank
  }
  return 0
}

describe('mesh stage priority (v80ag)', () => {
  test('split_k4 outranks textured and earlier stages', () => {
    const cases = [
      ['cat3_meca_split_k4.glb',          100],
      ['cat3_meca_split.glb',              95],
      ['cat3_meca_RIGGED_anim_v3.glb',     90],
      ['cat3_meca_RIGGED_anim.glb',        90],
      ['cat3_meca_mesh_textured.glb',      80],
      ['cat3_meca_RIGGED_rotating_v2.glb', 70],
      ['cat3_meca_RIGGED.glb',             70],
      ['cat3_meca_mesh_manifoldfixed.glb', 60],
      ['cat3_meca_mesh_reshaped.glb',      55],
      ['cat3_meca_mesh_baked.glb',         50],
      ['cat3_meca_mesh.glb',               40],
      ['something_random.glb',             10],
      ['random_thing.obj',                 10],
      ['not_a_mesh.png',                    0],
    ] as const
    for (const [name, expected] of cases) {
      assert.equal(rank(name), expected, `rank('${name}') should be ${expected}`)
    }
  })

  test('user case: when both textured and split exist, split wins', () => {
    const candidates = [
      'application/output/3d/v80x_cat3_meca/cat3_meca_mesh_baked.glb',
      'application/output/3d/v80x_cat3_meca/cat3_meca_mesh_textured.glb',
      'application/output/3d/v80x_cat3_meca/cat3_meca_split_k4.glb',
    ]
    let best = ''
    let bestRank = -1
    for (const c of candidates) {
      const r = rank(c)
      if (r > bestRank) { best = c; bestRank = r }
    }
    assert.match(best, /_split_k4\.glb$/, 'split_k4 should win the priority race')
  })

  test('regression: rigged-then-anim files are picked over textured', () => {
    const candidates = [
      'cat2_perso_mv_RIGGED_walking_anim_v3.glb',  // rank 90
      'cat2_perso_mv_mesh_textured.glb',           // rank 80
    ]
    let best = ''
    let bestRank = -1
    for (const c of candidates) {
      const r = rank(c)
      if (r > bestRank) { best = c; bestRank = r }
    }
    assert.match(best, /_anim_v3\.glb$/)
  })
})
