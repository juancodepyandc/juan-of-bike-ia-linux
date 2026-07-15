import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { BrandFidelityReport } from '../services/codeFidelityGate.ts'
import {
  applyBestAttemptFallback,
  buildBrandRetryBlock,
  countRealCodeFiles,
  isNetworkGenerationError,
  rememberBestAttempt,
} from '../services/codeGenerationOutputRetry.ts'

const files = {
  html: { name: 'index.html', language: 'html', content: '<main>ok</main>' },
  css: { name: 'style.css', language: 'css', content: 'body{}' },
  readme: { name: 'README.md', language: 'markdown', content: '# doc' },
}

function brandSubject(): NonNullable<CodeIntent['assetPlan']>['subject'] {
  return {
    source: 'brand',
    canonical: 'Aurora Cola',
    domain: 'boisson',
    brandProfile: {
      canonical: 'Aurora Cola',
      primaryColor: '#e60012',
      secondaryColor: '#ffffff',
      tertiaryColor: null,
      productShape: 'canette',
      productKeywords: ['cola', 'canette'],
      designVibe: 'iconique rouge',
      typoVibe: 'script',
      imageQueries: ['Aurora Cola canette'],
    },
  } as NonNullable<CodeIntent['assetPlan']>['subject']
}

const failingBrandReport: BrandFidelityReport = {
  scorePenalty: 30,
  scoreCap: 30,
  issues: ['subject_name_missing'],
  retryHint: 'Le nom de marque manque.',
  shouldRetry: true,
}

describe('codeGenerationOutputRetry helpers', () => {
  test('compte les vrais fichiers code en ignorant la documentation', () => {
    assert.equal(countRealCodeFiles([files.html, files.css, files.readme]), 2)
    assert.equal(countRealCodeFiles([files.readme]), 0)
  })

  test('detecte les erreurs reseau typiques de generation', () => {
    assert.equal(isNetworkGenerationError('TypeError: failed to fetch'), true)
    assert.equal(isNetworkGenerationError('524 connection closed'), true)
    assert.equal(isNetworkGenerationError('SyntaxError: unexpected token'), false)
  })

  test('memorise le meilleur essai par nombre de fichiers puis score', () => {
    const first = { files: [files.html], notes: 'one', score: 80 }
    const moreFiles = { files: [files.html, files.css], notes: 'two', score: 60 }
    const betterScore = { files: [files.html, files.css], notes: 'better', score: 90 }

    let best = rememberBestAttempt(null, first)
    best = rememberBestAttempt(best, moreFiles)
    best = rememberBestAttempt(best, betterScore)

    assert.equal(best?.notes, 'better')
    assert.equal(best?.score, 90)
  })

  test('livre le meilleur essai quand la derniere sortie est vide', () => {
    const originalWarn = console.warn
    console.warn = () => {}
    let fallback: ReturnType<typeof applyBestAttemptFallback> | null = null
    try {
      fallback = applyBestAttemptFallback([], '', {
        files: [files.html],
        notes: 'meilleur essai',
        score: 55,
      })
    } finally {
      console.warn = originalWarn
    }

    assert.ok(fallback)
    assert.deepEqual(fallback.files, [files.html])
    assert.match(fallback.notes, /Livré malgré des réserves/)
  })

  test('construit un bloc retry marque uniquement en cas de hard failure', () => {
    const block = buildBrandRetryBlock(failingBrandReport, brandSubject())

    assert.match(block, /Aurora Cola/)
    assert.match(block, /#e60012/)
    assert.match(block, /cola, canette/)
    assert.match(block, /INTERDIT/)

    assert.equal(buildBrandRetryBlock({ ...failingBrandReport, shouldRetry: false }, brandSubject()), '')
  })
})
