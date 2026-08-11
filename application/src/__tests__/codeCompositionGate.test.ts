// Verrouille les trois juges de COMPOSITION.
//
// Le juge de rendu notait 100/100 une page ou « View Demo » et « Scroll to
// explore » se superposaient, ou la section FAQ occupait 658 px remplis a 12 %,
// et ou les six icones de fonctionnalites etaient des emoji. Il comptait les
// tailles, les fonds et les ombres — jamais la composition.
//
// Les valeurs des cas « reel » ci-dessous sont celles MESUREES sur
// output/code/audit_v94/project/dist.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  checkComposition,
  detectEmojiIcons,
  findEmptySections,
  type CompositionMetrics,
} from '../services/codeCompositionGate.ts'

const CLEAN: CompositionMetrics = {
  overlaps: [],
  sections: [{ label: 'hero', height: 800, fill: 0.4 }, { label: 'faq', height: 600, fill: 0.35 }],
  emojiIcons: [],
  viewportWidth: 1440,
}

describe('juge de chevauchement', () => {
  test('attrape le cas reel « View Demo » x « Scroll to explore »', () => {
    const r = checkComposition({ ...CLEAN, overlaps: [{ a: 'View Demo', b: 'Scroll to explore', area: 2914 }] })
    assert.equal(r.ok, false)
    assert.ok(r.failedChecks.includes('no_overlap'))
    assert.match(r.critique, /View Demo/)
    assert.match(r.critique, /superposent/)
  })

  test('une page sans chevauchement passe', () => {
    assert.equal(checkComposition(CLEAN).ok, true)
  })
})

describe('juge de vide', () => {
  test('attrape le cas reel: 658 px remplis a 12 %', () => {
    const r = checkComposition({ ...CLEAN, sections: [{ label: 'Frequently Asked Questio', height: 658, fill: 0.12 }] })
    assert.equal(r.ok, false)
    assert.ok(r.failedChecks.includes('no_empty_section'))
    assert.match(r.critique, /658/)
  })

  test('une petite section peu remplie ne declenche rien (elle a le droit de respirer)', () => {
    assert.deepEqual(findEmptySections([{ label: 'bandeau', height: 120, fill: 0.05 }]), [])
  })

  test('une grande section bien remplie passe', () => {
    assert.deepEqual(findEmptySections([{ label: 'features', height: 900, fill: 0.45 }]), [])
  })

  test('une grande section vide est signalee', () => {
    assert.equal(findEmptySections([{ label: 'hero', height: 900, fill: 0.03 }]).length, 1)
  })
})

describe('contrat anti-emoji', () => {
  test('attrape les six emoji du cas reel', () => {
    const r = checkComposition({ ...CLEAN, emojiIcons: ['📊', '🎨', '🔌', '🔒', '👥', '🤖'] })
    assert.equal(r.ok, false)
    assert.ok(r.failedChecks.includes('real_iconography'))
    assert.match(r.critique, /SVG inline/)
  })

  test('une vraie iconographie passe', () => {
    assert.equal(checkComposition({ ...CLEAN, emojiIcons: [] }).ok, true)
  })

  test('detectEmojiIcons repere un emoji seul dans le markup', () => {
    const found = detectEmojiIcons([
      { name: 'index.html', content: '<div class="icon">📊</div><h3>Analytics</h3>' },
    ])
    assert.deepEqual(found, ['📊'])
  })

  test('detectEmojiIcons ignore un emoji NOYE dans une phrase', () => {
    const found = detectEmojiIcons([
      { name: 'index.html', content: '<p>On torrefie avec amour 🔥 chaque semaine dans notre atelier</p>' },
    ])
    assert.deepEqual(found, [])
  })

  test('detectEmojiIcons ignore les fichiers non-markup', () => {
    assert.deepEqual(detectEmojiIcons([{ name: 'notes.md', content: '# 📊 titre' }]), [])
  })
})

describe('rapport global', () => {
  test('les trois defauts reels sont signales ensemble', () => {
    const r = checkComposition({
      overlaps: [{ a: 'View Demo', b: 'Scroll to explore', area: 2914 }],
      sections: [{ label: 'faq', height: 658, fill: 0.12 }],
      emojiIcons: ['📊'],
      viewportWidth: 1440,
    })
    assert.deepEqual(r.failedChecks.sort(), ['no_empty_section', 'no_overlap', 'real_iconography'])
  })

  test('une page saine ne produit aucune critique', () => {
    assert.equal(checkComposition(CLEAN).critique, '')
  })
})
