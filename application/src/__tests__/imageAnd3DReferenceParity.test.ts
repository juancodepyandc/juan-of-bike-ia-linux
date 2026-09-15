import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseImageIntent } from '../utils/imagePromptParser.ts'
import { detectSubjectToResearch } from '../services/selfInformedReference.ts'

describe('Image & 3D Reference Architecture & Intent Handling', () => {
  it('parses reference-based edit intent accurately', () => {
    const intent = parseImageIntent('ajoute une armure dorée sur le personnage', { hasReference: true })
    assert.strictEqual(intent.isEditIntent, true)
    assert.ok(intent.additions.length > 0 || intent.editMode === 'add_element')
  })

  it('preserves creation mode when no reference is provided', () => {
    const intent = parseImageIntent('un guerrier cybernétique avec une épée laser', { hasReference: false })
    assert.strictEqual(intent.isEditIntent, false)
    assert.strictEqual(intent.editMode, 'create')
  })

  it('detects specific character targets for visual research without false positives on generic nouns', () => {
    const target = detectSubjectToResearch('ajoute le personnage Natsu Dragneel dans la scène', {
      isEditIntent: true,
      cleanedPrompt: 'ajoute le personnage Natsu Dragneel dans la scène',
      removals: [],
      additions: ['Natsu Dragneel'],
      replacements: [],
      editMode: 'add_element',
      editContract: {
        mode: 'add_element',
        label: 'add',
        denoise: 0.7,
        stepsBoost: 0,
        promptLines: [],
        negativeLines: [],
        requestedTargets: ['Natsu Dragneel'],
        preserveLines: [],
      },
    })
    assert.ok(target !== null)
    assert.strictEqual(target?.kind, 'character')
    assert.ok(target?.subject.toLowerCase().includes('natsu'))
  })

  it('handles generic prompt without forcing hallucinated character research', () => {
    const target = detectSubjectToResearch('une maison en bois au bord du lac', {
      isEditIntent: false,
      cleanedPrompt: 'une maison en bois au bord du lac',
      removals: [],
      additions: [],
      replacements: [],
      editMode: 'create',
      editContract: {
        mode: 'create',
        label: 'create',
        denoise: null,
        stepsBoost: 0,
        promptLines: [],
        negativeLines: [],
        requestedTargets: [],
        preserveLines: [],
      },
    })
    assert.strictEqual(target, null)
  })
})
