import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import JSZip from 'jszip'
import { CODE_ASSET_BUNDLE_SCHEMA, CODE_ASSET_MANIFEST_PATH } from '../services/codeInterModuleAssets.ts'
import { buildProjectZipBlob } from '../utils/codeDownload.ts'

const assets = [
  { path: 'assets/generated/proof/hero.avif', url: 'http://bridge.test/hero.avif', bytes: [1, 2, 3] },
  { path: 'assets/generated/proof/product.glb', url: 'http://bridge.test/product.glb', bytes: [4, 5, 6, 7] },
  { path: 'assets/generated/proof/narration.wav', url: 'http://bridge.test/narration.wav', bytes: [8, 9] },
]

function files() {
  return [
    {
      name: 'src/main.ts',
      language: 'ts',
      content: assets.map((asset) => `export const ref = '${asset.url}'`).join('\n'),
    },
    {
      name: CODE_ASSET_MANIFEST_PATH,
      language: 'json',
      content: JSON.stringify({
        schemaVersion: CODE_ASSET_BUNDLE_SCHEMA,
        assets: assets.map((asset) => ({
          path: asset.path,
          previewUrl: asset.url,
          mimeType: 'application/octet-stream',
        })),
      }),
    },
  ]
}

describe('buildProjectZipBlob assets WS15', () => {
  test('integre les trois familles binaires et localise les references', async () => {
    const requested: string[] = []
    const blob = await buildProjectZipBlob(files(), async (input) => {
      const url = String(input)
      requested.push(url)
      const asset = assets.find((candidate) => candidate.url === url)
      return asset
        ? new Response(Uint8Array.from(asset.bytes), { status: 200 })
        : new Response('missing', { status: 404 })
    })
    const zip = await JSZip.loadAsync(await blob.arrayBuffer())
    assert.deepEqual(requested, assets.map((asset) => asset.url))
    for (const asset of assets) {
      const extracted = await zip.file(asset.path)?.async('uint8array')
      assert.deepEqual([...extracted ?? []], asset.bytes)
    }
    const source = await zip.file('src/main.ts')?.async('string')
    assert.ok(source)
    assert.doesNotMatch(source, /bridge\.test/)
    for (const asset of assets) assert.match(source, new RegExp(asset.path.replaceAll('/', '\\/')))
  })

  test('refuse un asset HTTP absent au lieu de livrer une archive incomplete', async () => {
    await assert.rejects(
      buildProjectZipBlob(files(), async () => new Response('missing', { status: 404 })),
      /Export asset impossible \(404\)/,
    )
  })

  test('preserve une arborescence multi-niveaux', async () => {
    const blob = await buildProjectZipBlob([
      { name: 'src/features/deep/index.ts', language: 'ts', content: 'export const ok = true' },
    ], async () => new Response())
    const zip = await JSZip.loadAsync(await blob.arrayBuffer())
    assert.equal(await zip.file('src/features/deep/index.ts')?.async('string'), 'export const ok = true')
  })

  test('n exporte jamais un chemin asset traversant', async () => {
    const manifest = {
      name: CODE_ASSET_MANIFEST_PATH,
      language: 'json',
      content: JSON.stringify({
        schemaVersion: CODE_ASSET_BUNDLE_SCHEMA,
        assets: [{ path: 'assets/generated/../secret', previewUrl: 'http://bridge.test/secret' }],
      }),
    }
    let fetched = false
    const blob = await buildProjectZipBlob([manifest], async () => {
      fetched = true
      return new Response()
    })
    const zip = await JSZip.loadAsync(await blob.arrayBuffer())
    assert.equal(fetched, false)
    assert.equal(zip.file('assets/secret'), null)
  })
})
