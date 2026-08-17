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
  computeSectionFill,
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

// ---------------------------------------------------------------------------
// Run 1161 — la porte condamnait ce qu elle n avait jamais mesure.
//
// L ancienne mesure SOMMAIT l aire des elements du DOM sans enfant element. Un
// `h1` contenant un `<br>` etait donc integralement jete. Valeurs relevees
// element par element sur le livrable reel (output/code_assets/viewers/run-1161):
//
//   section hero 1440x944
//     h1.hero-title      1440x298  JETE (contient un <br>)
//     div.hero-content   1440x704  JETE (conteneur)
//     p.hero-subtitle     700x37   compte
//     img.hero-image      330x289  compte
//     a.cta-button        128x17   compte
//   -> fill = 9 %, et la porte a declare le hero « quasi vide ».
//
// Pire: une grille de quatre produits ENTIEREMENT remplie sortait a 18,7 % pour
// un seuil a 15 %. La mesure n avait aucune dynamique utile.
// ---------------------------------------------------------------------------
describe('juge de vide — occupation reellement mesuree (run 1161)', () => {
  /** Bandes relevees au rendu pour le hero de la Brulerie Nomade. */
  const HERO_BANDS: Array<[number, number]> = [
    [120, 418],  // h1.hero-title, la ligne que l ancienne mesure jetait
    [438, 475],  // p.hero-subtitle
    [495, 784],  // img.hero-image
    [804, 821],  // a.cta-button
  ]

  test('le hero de la Brulerie n est PAS vide: 9 % mesure devient une occupation reelle', () => {
    const sections = [{ label: 'Torréfié cette semaine, ', height: 944, bands: HERO_BANDS }]
    assert.deepEqual(findEmptySections(sections), [])
    assert.equal(checkComposition({ ...CLEAN, sections }).ok, true)
  })

  // Le cas qui avait CALIBRE le seuil etait lui aussi un faux positif.
  //
  // Le commentaire de `EMPTY_SECTION_FILL` disait « le cas reel mesure 12 % sur
  // 658 px ». Ce projet (output/code/audit_v94/project/dist) a ete reconstruit,
  // remesure et PHOTOGRAPHIE: output/code/audit_v117/v94_faq.png montre une FAQ
  // complete — titre, sous-titre, cinq cartes en accordeon. Elle n a jamais ete
  // vide. Les bandes ci-dessous sont celles relevees au rendu.
  //
  // Consequence a dire sans detour: cette porte n a jamais attrape un vrai
  // positif. Elle en fabriquait.
  const V94_FAQ_BANDS: Array<[number, number]> = [
    [47, 96], [115, 139], [216, 236], [303, 323], [390, 410], [477, 497], [564, 584],
    [192, 261], [217, 237], [279, 348], [304, 324], [366, 435], [391, 411],
    [453, 522], [478, 498], [540, 609], [565, 585],
  ]

  test('la FAQ de audit_v94 — 11,8 % « vide » — est en fait pleine a 85 %', () => {
    const sections = [{ label: 'Frequently Asked Questio', height: 658, bands: V94_FAQ_BANDS }]
    assert.equal(Math.round(computeSectionFill(sections[0]) * 100), 85)
    assert.deepEqual(findEmptySections(sections), [])
    assert.equal(checkComposition({ ...CLEAN, sections }).ok, true)
  })

  // La regle reste capable de dire « vide » quand la section l est vraiment.
  // Faute de vrai positif historique, ce cas est construit, et il est annonce
  // comme tel: une section de 658 px dont le contenu tient sur 79 px.
  test('une section haute dont le contenu tient sur deux lignes est bien vide', () => {
    const sections = [{ label: 'Newsletter', height: 658, bands: [[290, 369]] as Array<[number, number]> }]
    assert.equal(findEmptySections(sections).length, 1)
    assert.equal(checkComposition({ ...CLEAN, sections }).ok, false)
  })

  test('une section sans aucun contenu peint est vide', () => {
    assert.equal(findEmptySections([{ label: 'ghost', height: 800, bands: [] }]).length, 1)
  })

  test('une respiration courte entre deux blocs n est pas un trou', () => {
    // Deux blocs de 200 px separes par 80 px sur une section de 800: du padding.
    const sections = [{ label: 'duo', height: 800, bands: [[40, 240], [320, 520]] as Array<[number, number]> }]
    assert.deepEqual(findEmptySections(sections), [])
  })

  test('rien de mesure ne condamne rien', () => {
    assert.deepEqual(findEmptySections([{ label: 'inconnu', height: 900 }]), [])
  })

  test('la preuve nomme le selecteur ET le fichier, pas seulement un bout de texte', () => {
    const r = checkComposition({
      ...CLEAN,
      sections: [{
        label: 'Newsletter',
        height: 720,
        bands: [[300, 340]],
        selector: 'section.newsletter-band',
        sourceFile: 'src/components/Newsletter.tsx',
      }],
    })
    assert.equal(r.ok, false)
    assert.match(r.critique, /section\.newsletter-band/)
    assert.match(r.critique, /src\/components\/Newsletter\.tsx/)
    assert.deepEqual(r.evidencePaths, ['src/components/Newsletter.tsx'])
  })

  test('sans attribution, aucune preuve inventee', () => {
    const r = checkComposition({ ...CLEAN, sections: [{ label: 'x', height: 720, bands: [] }] })
    assert.equal(r.ok, false)
    assert.deepEqual(r.evidencePaths, [])
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
