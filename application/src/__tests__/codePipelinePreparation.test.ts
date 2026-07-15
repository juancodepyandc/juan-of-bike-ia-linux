import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import {
  buildBrandProfileBlock,
  buildResearchPhaseLabel,
  buildSubjectImagePromptBlock,
  looksLikeSimpleTechBrief,
} from '../services/codePipelinePreparation.ts'

function intent(assetPlan: Partial<NonNullable<CodeIntent['assetPlan']>>): CodeIntent {
  return {
    projectType: 'static_web',
    assetPlan: {
      wantsPremiumLook: false,
      wantsImages: false,
      researchQueries: [],
      objectMentions: [],
      subject: null,
      palette: [],
      language: 'fr',
      ...assetPlan,
    },
  } as unknown as CodeIntent
}

describe('codePipelinePreparation', () => {
  test('distingue les briefs techniques simples des vrais briefs marque', () => {
    assert.equal(looksLikeSimpleTechBrief('une page HTML simple avec un bouton de calcul'), true)
    assert.equal(looksLikeSimpleTechBrief('fais le site de Coca-Cola avec logo et produit hero'), false)
    assert.equal(looksLikeSimpleTechBrief('landing premium pour une marque de parfum'), false)
  })

  test('construit le libelle de recherche selon assetPlan', () => {
    assert.match(
      buildResearchPhaseLabel(intent({ researchQueries: ['dashboard premium', 'crm ui'] })),
      /dashboard premium \| crm ui/,
    )
    assert.match(
      buildResearchPhaseLabel(intent({ wantsPremiumLook: true })),
      /tendances de design premium/,
    )
    assert.match(
      buildResearchPhaseLabel(intent({})),
      /meilleures pratiques/,
    )
  })

  test('construit un bloc images sujet avec markers et budget de taille', () => {
    const block = buildSubjectImagePromptBlock([
      { dataUrl: 'data:image/png;base64,AAA', query: 'logo', source: 'bridge' },
      { dataUrl: 'data:image/png;base64,BBB', query: 'produit', source: 'extension' },
      { dataUrl: `data:image/png;base64,${'x'.repeat(360_000)}`, query: 'trop lourd', source: 'bridge' },
    ])

    assert.match(block, /PLACEHOLDER_SUBJECT_IMG/)
    assert.match(block, /PLACEHOLDER_SUBJECT_IMG_2/)
    assert.match(block, /logo -> bridge/)
    assert.doesNotMatch(block, /trop lourd/)
  })

  test('construit le bloc profil marque avec palette et mots cles', () => {
    const block = buildBrandProfileBlock(intent({
      subject: {
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
      },
    }))

    assert.match(block, /Aurora Cola/)
    assert.match(block, /#e60012/)
    assert.match(block, /cola, canette/)
    assert.match(block, /iconique rouge/)
  })
})
