// Le dernier verrou du run 1051: neuf passes sur une apostrophe francaise.
//
// Le pipeline diagnostiquait juste, a la bonne position, neuf fois de suite —
// et le modele reproduisait la meme rupture a chaque reecriture. Ce test verrouille
// les deux sens: le cas certain est repare, le reste n est JAMAIS touche.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { isApostropheRepairable, repairFrenchApostrophes } from '../services/codeApostropheRepair.ts'
import { sanitizeGeneratedFileContent } from '../services/codeGeneratedFileSanitizer.ts'

// Ligne VERBATIM du run 1051 (MarketCalendar.tsx, lignes 24 et 45).
const RUN_1051 = "      location: 'Presqu'île',"

describe('apostrophe francaise — le cas certain est repare', () => {
  test('la ligne exacte du run 1051', () => {
    const { code, repairs } = repairFrenchApostrophes(RUN_1051)
    assert.equal(repairs, 1)
    assert.equal(code, "      location: 'Presqu\\'île',")
  })

  test('les autres apostrophes francaises courantes', () => {
    for (const raw of ["const a = 'aujourd'hui'", "const b = 'l'atelier'", "const c = 'd'accord'"]) {
      assert.equal(repairFrenchApostrophes(raw).repairs, 1, raw)
    }
  })

  test('plusieurs occurrences dans un meme fichier', () => {
    assert.equal(repairFrenchApostrophes(`${RUN_1051}\n${RUN_1051}`).repairs, 2)
  })
})

describe('apostrophe francaise — ce qui ne doit JAMAIS bouger', () => {
  const untouched = (source: string, why: string) => {
    const { code, repairs } = repairFrenchApostrophes(source)
    assert.equal(repairs, 0, why)
    assert.equal(code, source, why)
  }

  test('du code valide reste identique, octet pour octet', () => {
    untouched("const a = 'x'; const b = 'y'", 'litterals normaux')
    untouched("const list = ['a', 'b', 'c']", 'tableau de litterals')
    untouched("const s = 'a' + 'b'", 'concatenation')
    untouched('const s = "Presqu\'île"', 'guillemets doubles: deja valide')
    untouched('const s = `Presqu\'île`', 'gabarit: deja valide')
  })

  test('une apostrophe DEJA echappee n est pas doublement echappee', () => {
    untouched("const s = 'Presqu\\'île'", 'echappement existant preserve')
  })

  test('les commentaires ne sont pas touches', () => {
    untouched("// c'est un commentaire avec l'apostrophe", 'commentaire de ligne')
    untouched("/* aujourd'hui on ne touche a rien */", 'commentaire de bloc')
  })

  test('un litteral non ferme ne declenche aucune invention', () => {
    // Fichier casse autrement: on rend la main plutot que de deviner.
    untouched("const s = 'ouvert\nconst t = 2", 'litteral non ferme')
  })

  test('seuls les fichiers a litterals JS/TS sont concernes', () => {
    assert.equal(isApostropheRepairable('src/App.tsx'), true)
    assert.equal(isApostropheRepairable('src/main.js'), true)
    assert.equal(isApostropheRepairable('README.md'), false)
    assert.equal(isApostropheRepairable('data.json'), false)
    assert.equal(isApostropheRepairable('style.css'), false)
  })
})

describe('apostrophe francaise — la reparation est branchee sur le pipeline', () => {
  test('le fichier assaini du run 1051 ne casse plus le litteral', () => {
    const out = sanitizeGeneratedFileContent('src/components/MarketCalendar.tsx', `const markets = [\n${RUN_1051}\n];`)
    assert.match(out, /Presqu\\'île/)
  })

  test('un markdown contenant la meme phrase reste intact', () => {
    const md = "Le marche de la Presqu'île a lieu le mercredi."
    assert.equal(sanitizeGeneratedFileContent('README.md', md).trim(), md)
  })
})
