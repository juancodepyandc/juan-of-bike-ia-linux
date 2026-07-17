import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  CODE_ASSET_BUNDLE_SCHEMA,
  CODE_ASSET_MANIFEST_PATH,
  buildAssetManifestFile,
  buildInterModuleAssetRoutes,
  generateAssetsForArchetype,
  isCodeAssetBundle,
  runInterModuleAssetPhase,
  selectInterModuleAssetKinds,
  summarizeAssetBundle,
  upsertAssetManifestFile,
  type CodeAssetBundle,
} from '../services/codeInterModuleAssets.ts'
import {
  applyInterModuleAssetPlaceholders,
  collectAssetExportEntries,
  materializeInterModuleAssetReferences,
  rewriteAssetUrlsForExport,
} from '../services/codeInterModuleAssetIntegration.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import { finalizeCodePipelineDelivery } from '../services/codePipelineFinalization.ts'

function sampleBundle(): CodeAssetBundle {
  return {
    schemaVersion: CODE_ASSET_BUNDLE_SCHEMA,
    createdAt: 1,
    runId: 'ws15-test',
    prompt: 'showroom produit avec narration',
    archetype: 'static_web',
    outDir: 'output/code_assets/ws15-test',
    requiredKinds: ['image', 'model3d', 'voice'],
    missingRequired: [],
    assets: [
      {
        id: 'image-hero',
        kind: 'image',
        role: 'hero',
        path: 'assets/generated/ws15-test/images/hero-1400.avif',
        storagePath: 'output/code_assets/ws15-test/images/hero-1400.avif',
        previewUrl: '/api/code/assets/file/ws15-test/images/hero-1400.avif',
        mimeType: 'image/avif',
        bytes: 2048,
        sourceModule: 'image',
        bridgeEndpoint: '/api/comfyui/image',
        optimized: true,
        srcset: '/api/code/assets/file/ws15-test/images/hero-1400.avif 1400w, /api/code/assets/file/ws15-test/images/hero-800.avif 800w',
        projectSrcset: 'assets/generated/ws15-test/images/hero-1400.avif 1400w, assets/generated/ws15-test/images/hero-800.avif 800w',
        variants: [{
          path: 'assets/generated/ws15-test/images/hero-1400.webp',
          previewUrl: '/api/code/assets/file/ws15-test/images/hero-1400.webp',
          width: 1400,
          height: 900,
          mimeType: 'image/webp',
          bytes: 1900,
        }],
      },
      {
        id: 'model-primary',
        kind: 'model3d',
        role: 'product-model',
        path: 'assets/generated/ws15-test/models/product.glb',
        previewUrl: '/api/code/assets/file/ws15-test/models/product.glb',
        mimeType: 'model/gltf-binary',
        bytes: 8192,
        sourceModule: '3d',
        bridgeEndpoint: '/api/3d/run-pipeline',
        optimized: true,
      },
      {
        id: 'voice-narration',
        kind: 'voice',
        role: 'narration',
        path: 'assets/generated/ws15-test/voice/narration.wav',
        previewUrl: '/api/code/assets/file/ws15-test/voice/narration.wav',
        mimeType: 'audio/wav',
        bytes: 4096,
        sourceModule: 'voice',
        bridgeEndpoint: '/api/voice/tts',
        optimized: true,
      },
    ],
    routes: [],
    rag: {
      searchEndpoint: '/api/web/search',
      extractEndpoint: '/api/web/extract',
      embedding: 'ollama:nomic-embed-text',
      reranker: 'embedding-cosine+lexical-overlap',
      fetchedPages: 3,
      results: [{ title: 'Reference', url: 'https://example.test', score: 0.82 }],
    },
    deferred: [{ kind: 'music_sfx', reason: 'Aucun service dedie dans le bridge.' }],
  }
}

describe('codeInterModuleAssets routage', () => {
  test('declare chaque service reel impose par WS15', () => {
    const routes = buildInterModuleAssetRoutes()
    assert.deepEqual(routes.map((route) => route.endpoint), [
      '/api/comfyui/image',
      '/api/3d/run-pipeline',
      '/api/voice/tts',
      '/api/code/visual-audit',
      '/api/web/search',
    ])
    assert.deepEqual(routes[0].fallbackEndpoints, ['/api/web/image', '/api/web/images'])
    assert.deepEqual(routes[2].fallbackEndpoints, ['/api/voice/synthesize'])
    assert.deepEqual(routes[4].fallbackEndpoints, ['/api/web/extract'])
  })

  test('selectionne les assets selon la cible et la demande explicite', () => {
    assert.deepEqual(selectInterModuleAssetKinds({
      prompt: 'landing page avec narration vocale et modele 3D',
      projectType: 'static_web',
      wants3D: true,
    }), ['image', 'model3d', 'voice'])
    assert.deepEqual(selectInterModuleAssetKinds({
      prompt: 'outil CLI Python',
      projectType: 'cli_python',
    }), [])
    assert.deepEqual(selectInterModuleAssetKinds({
      prompt: 'outil CLI documente par une illustration',
      projectType: 'cli_python',
      wantsImages: true,
    }), ['image'])
  })
})

describe('codeInterModuleAssets manifeste', () => {
  test('valide, resume et materialise un manifeste sans base64 inline', () => {
    const bundle = sampleBundle()
    assert.equal(isCodeAssetBundle(bundle), true)
    assert.match(summarizeAssetBundle(bundle), /image:1/)
    assert.match(summarizeAssetBundle(bundle), /model3d:1/)
    assert.match(summarizeAssetBundle(bundle), /voice:1/)

    const manifest = buildAssetManifestFile(bundle, 'http://127.0.0.1:3001')
    assert.equal(manifest.name, CODE_ASSET_MANIFEST_PATH)
    assert.doesNotMatch(manifest.content, /data:(?:image|audio)\//)
    assert.match(manifest.content, /hero-1400\.avif/)
    assert.match(manifest.content, /hero-1400\.webp/)
    assert.match(manifest.content, /http:\/\/127\.0\.0\.1:3001\/api\/code\/assets\/file/)
    assert.match(manifest.content, /ollama:nomic-embed-text/)
  })

  test('reinsere le manifeste apres une correction qui l aurait supprime', () => {
    const files = upsertAssetManifestFile([
      { name: 'index.html', language: 'html', content: '<main>OK</main>' },
      { name: CODE_ASSET_MANIFEST_PATH, language: 'json', content: '{}' },
    ], sampleBundle(), 'http://bridge.test')
    assert.equal(files.filter((file) => file.name === CODE_ASSET_MANIFEST_PATH).length, 1)
    assert.match(files.find((file) => file.name === CODE_ASSET_MANIFEST_PATH)!.content, /bridge\.test/)
  })

  test('prepare tous les binaires pour le ZIP sans doublon ni chemin dangereux', () => {
    const manifest = buildAssetManifestFile(sampleBundle(), 'http://bridge.test')
    const parsed = JSON.parse(manifest.content)
    parsed.assets.push({
      path: '../outside.bin',
      previewUrl: 'http://bridge.test/api/code/assets/file/outside.bin',
    })
    manifest.content = JSON.stringify(parsed)

    const entries = collectAssetExportEntries([manifest])
    assert.deepEqual(entries.map((entry) => entry.path), [
      'assets/generated/ws15-test/images/hero-1400.avif',
      'assets/generated/ws15-test/images/hero-1400.webp',
      'assets/generated/ws15-test/models/product.glb',
      'assets/generated/ws15-test/voice/narration.wav',
    ])
    assert.ok(entries.every((entry) => entry.url.startsWith('http://bridge.test/')))
  })

  test('FILET #6: un hotlink externe (Unsplash/CDN) est reecrit vers l asset LOCAL du bundle', () => {
    // Le modele hotlink souvent une image externe hors-sujet (iPhone Unsplash) au
    // lieu d'utiliser l'asset reel. Le filet deterministe la remplace par l'asset local.
    const source = '<img src="https://images.unsplash.com/photo-1695?w=600" alt="iPhone 15 Pro" class="hero">'
    const out = applyInterModuleAssetPlaceholders(source, sampleBundle(), 'http://bridge.test')
    assert.doesNotMatch(out, /images\.unsplash\.com/, 'le hotlink externe doit disparaitre')
    assert.match(out, /http:\/\/bridge\.test\/api\/code\/assets\/file\/ws15-test\/images\/hero-1400\.avif/, 'remplace par l asset local du bundle')
  })

  test('FILET #6: les images LOCALES / data: / SVG inline ne sont pas touchees', () => {
    const source = '<img src="./assets/logo.svg"><img src="data:image/svg+xml,abc"><svg><path/></svg>'
    const out = applyInterModuleAssetPlaceholders(source, sampleBundle(), 'http://bridge.test')
    assert.match(out, /\.\/assets\/logo\.svg/)
    assert.match(out, /data:image\/svg\+xml,abc/)
  })

  test('resout les marqueurs pour la preview puis restaure les chemins dans le ZIP', () => {
    const source = '<img src="PLACEHOLDER_IMG_HERO"><model-viewer src="PLACEHOLDER_ASSET_GLB"></model-viewer>'
    const preview = applyInterModuleAssetPlaceholders(source, sampleBundle(), 'http://bridge.test')
    assert.match(preview, /http:\/\/bridge\.test\/api\/code\/assets\/file\/ws15-test\/images\/hero-1400\.avif/)
    assert.match(preview, /http:\/\/bridge\.test\/api\/code\/assets\/file\/ws15-test\/models\/product\.glb/)

    const manifest = buildAssetManifestFile(sampleBundle(), 'http://bridge.test')
    const files = materializeInterModuleAssetReferences([
      { name: 'index.html', language: 'html', content: source },
      manifest,
    ], sampleBundle(), 'http://bridge.test')
    const entries = collectAssetExportEntries(files)
    const exported = rewriteAssetUrlsForExport(files[0].content, entries)
    assert.match(exported, /assets\/generated\/ws15-test\/images\/hero-1400\.avif/)
    assert.match(exported, /assets\/generated\/ws15-test\/models\/product\.glb/)
    assert.doesNotMatch(exported, /bridge\.test/)
  })

  test('rejette un bundle qui signale une forme incomplete', () => {
    const invalid = { ...sampleBundle(), runId: undefined }
    assert.equal(isCodeAssetBundle(invalid), false)
  })
})

describe('codeInterModuleAssets client bridge', () => {
  test('transmet les familles, la preuve 3D et les routes attendues', async () => {
    let body: Record<string, unknown> = {}
    const bundle = await generateAssetsForArchetype({
      prompt: 'showroom 3D avec narration',
      archetype: 'static_web',
      requestedKinds: ['image', 'model3d', 'voice'],
      bridgeUrl: 'http://127.0.0.1:3001',
      fresh3d: true,
      sourceImageRunId: 'proof-image',
      source3dRunId: 'proof-3d',
      sourceVoiceRunId: 'proof-voice',
      timeoutSec: 30,
      fetchImpl: async (input, init) => {
        assert.equal(String(input), 'http://127.0.0.1:3001/api/code/assets/generate')
        body = JSON.parse(String(init?.body))
        return new Response(JSON.stringify({ ok: true, bundle: sampleBundle() }), { status: 200 })
      },
    })
    assert.equal(bundle.assets.length, 3)
    assert.deepEqual(body.requestedKinds, ['image', 'model3d', 'voice'])
    assert.equal(body.fresh3d, true)
    assert.equal(body.sourceImageRunId, 'proof-image')
    assert.equal(body.source3dRunId, 'proof-3d')
    assert.equal(body.sourceVoiceRunId, 'proof-voice')
    assert.equal((body.expectedRoutes as unknown[]).length, 5)
  })

  test('execute la phase et injecte le manifeste dans le contexte du codeur', async () => {
    const phases: string[] = []
    const result = await runInterModuleAssetPhase({
      prompt: 'landing page avec narration et modele 3D',
      enrichedPrompt: 'brief enrichi original',
      projectType: 'static_web',
      wants3D: true,
      existingFiles: [{ name: 'index.html', language: 'html', content: '<main />' }],
      bridgeUrl: 'http://bridge.test',
      setPhase: (detail) => phases.push(detail),
      fetchImpl: async () => new Response(JSON.stringify({ ok: true, bundle: sampleBundle() })),
    })
    assert.equal(result.bundle?.assets.length, 3)
    assert.ok(result.files.some((file) => file.name === CODE_ASSET_MANIFEST_PATH))
    assert.match(phases.join('\n'), /Assets integres/)
  })
})

describe('codePipelineFinalization', () => {
  test('preserve le manifeste et expose les assets dans les notes finales', () => {
    const intent = classifyCodeIntent('Cree une landing page React premium avec une image hero')
    const delivery = finalizeCodePipelineDelivery({
      files: [{ name: 'index.html', language: 'html', content: '<main>Produit</main>' }],
      notes: 'Validation verte',
      score: 92,
      intent,
      enrichedPrompt: 'Landing page produit originale et premium',
      architecturePlan: null,
      assetBundle: sampleBundle(),
    })
    assert.ok(delivery.files.some((file) => file.name === CODE_ASSET_MANIFEST_PATH))
    assert.match(delivery.notes, /ASSETS INTER-MODULES/)
    assert.match(delivery.notes, /model3d:1/)
    assert.ok(delivery.score <= 92)
  })
})

describe('codeInterModuleAssets garde-fous', () => {
  test('retire les sources mortes et toute directive de replication', () => {
    const bridge = readFileSync(new URL('../../bridge_server.py', import.meta.url), 'utf8')
    const enrich = readFileSync(new URL('../../python-services/aurora_code/aurora_code_enrich.py', import.meta.url), 'utf8')
    assert.doesNotMatch(bridge, /source\.unsplash\.com/i)
    assert.doesNotMatch(enrich, /precisely replicate|personal use/i)
    assert.match(enrich, /original information[\s\S]*architecture/i)
  })
})

const migratedPlaceholderCases = [
  ['PLACEHOLDER_SUBJECT_IMG_6', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG_5', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG_4', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG_3', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG_2', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG_1', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_SUBJECT_IMG', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_IMG_LIFESTYLE2', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_IMG_LIFESTYLE1', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_IMG_DETAIL', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_IMG_HERO', 'image', 'hero-1400.avif'],
  ['PLACEHOLDER_MODEL_3D', 'model3d', 'product.glb'],
  ['PLACEHOLDER_ASSET_GLB', 'model3d', 'product.glb'],
  ['PLACEHOLDER_VOICE_NARRATION', 'voice', 'narration.wav'],
  ['PLACEHOLDER_ASSET_VOICE', 'voice', 'narration.wav'],
] as const

describe('codeInterModuleAssets migrations des anciens post-traitements', () => {
  for (const [marker, kind, expectedFile] of migratedPlaceholderCases) {
    test(`materialise ${marker} avec l asset ${kind}`, () => {
      const materialized = applyInterModuleAssetPlaceholders(
        `<div data-asset="${marker}">${marker}</div>`,
        sampleBundle(),
        'http://bridge.test',
      )
      assert.doesNotMatch(materialized, new RegExp(marker))
      assert.match(materialized, new RegExp(expectedFile.replace('.', '\\.')))
      assert.match(materialized, /^<div data-asset="http:\/\/bridge\.test\//)
    })
  }

  test('ne touche pas au contenu en absence de bundle', () => {
    const content = '<img src="PLACEHOLDER_IMG_HERO">'
    assert.equal(applyInterModuleAssetPlaceholders(content, null, 'http://bridge.test'), content)
  })

  test('ignore un manifeste de schema inconnu', () => {
    const entries = collectAssetExportEntries([{
      name: CODE_ASSET_MANIFEST_PATH,
      language: 'json',
      content: JSON.stringify({ schemaVersion: 'unknown', assets: sampleBundle().assets }),
    }])
    assert.deepEqual(entries, [])
  })
})
