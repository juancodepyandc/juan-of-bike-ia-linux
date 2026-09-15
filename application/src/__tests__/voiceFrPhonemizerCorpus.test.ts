/**
 * Corpus de contrôle du phonémiseur français.
 *
 * POURQUOI CE FICHIER EXISTE. La suite `voiceFrPhonemizer.test.ts` passait au
 * vert sur un module qui rendait 2 prononciations justes sur 18. Elle
 * n'affirmait que des `assert.ok(r.includes('ʃ'))` : « chat » sortait /ʃat/,
 * l'assertion voyait bien le /ʃ/ et validait. Une assertion qui ne peut pas
 * échouer ne teste rien. Ici, chaque attente est la chaîne IPA EXACTE.
 *
 * VÉRITÉ TERRAIN. Prononciation académique du français standard, telle que la
 * donnent les dictionnaires de référence (Petit Robert, Larousse) pour un
 * locuteur non régional, en prononciation isolée (pas de liaison, pas de
 * schwa de soutien).
 *
 * ÉQUIVALENCES ADMISES. Deux couples sont notés différemment selon les
 * sources sans que la BOUCHE change de forme — or c'est la bouche que ce
 * module pilote. On les traite donc comme équivalents, explicitement plutôt
 * que par un assouplissement tacite de l'assertion :
 *   - /o/ ~ /ɔ/  (« bonobo » /bɔnɔbo/ ou /bonobo/ selon les régions)
 *   - /a/ ~ /ɑ/  (opposition perdue chez la plupart des locuteurs)
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/voiceFrPhonemizerCorpus.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { phonemizeWord, phonemizeSentence } from '../services/voiceFrPhonemizer.ts'

/** Réduit les distinctions inaudibles pour le lipsync. */
function classeVisuelle(ipa: string): string {
  return ipa.replace(/ɔ(?!̃)/g, 'o').replace(/ɑ(?!̃)/g, 'a')
}

type Cas = { mot: string; ipa: string; regle: string }

/**
 * 62 mots. Le corpus couvre chaque mécanisme du français écrit qui décide de
 * la prononciation, avec au moins deux témoins par mécanisme — un seul
 * témoin laisserait passer une correction ad hoc au lieu d'une règle.
 */
const CORPUS: Cas[] = [
  // --- consonne finale muette (le mécanisme le plus fréquent du français)
  { mot: 'petit', ipa: 'pəti', regle: 'consonne finale muette' },
  { mot: 'chat', ipa: 'ʃa', regle: 'consonne finale muette' },
  { mot: 'grand', ipa: 'ɡʁɑ̃', regle: 'consonne finale muette' },
  { mot: 'beaucoup', ipa: 'boku', regle: 'consonne finale muette' },
  { mot: 'nous', ipa: 'nu', regle: 'consonne finale muette' },
  { mot: 'trop', ipa: 'tʁo', regle: 'consonne finale muette' },
  { mot: 'tard', ipa: 'taʁ', regle: 'r final SONORE' },
  { mot: 'sac', ipa: 'sak', regle: 'c final SONORE' },
  { mot: 'chef', ipa: 'ʃɛf', regle: 'f final SONORE' },
  { mot: 'seul', ipa: 'sœl', regle: 'l final SONORE' },
  { mot: 'blanc', ipa: 'blɑ̃', regle: 'c muet apres nasale' },
  { mot: 'franc', ipa: 'fʁɑ̃', regle: 'c muet apres nasale' },

  // --- voyelles nasales
  { mot: 'bon', ipa: 'bɔ̃', regle: 'nasale finale' },
  { mot: 'pin', ipa: 'pɛ̃', regle: 'nasale finale' },
  { mot: 'brun', ipa: 'bʁœ̃', regle: 'nasale finale' },
  { mot: 'main', ipa: 'mɛ̃', regle: 'trigraphe ain avant digraphe ai' },
  { mot: 'plein', ipa: 'plɛ̃', regle: 'trigraphe ein' },
  { mot: 'demain', ipa: 'dəmɛ̃', regle: 'trigraphe ain non initial' },
  { mot: 'bonjour', ipa: 'bɔ̃ʒuʁ', regle: 'nasale interne' },
  { mot: 'enfin', ipa: 'ɑ̃fɛ̃', regle: 'deux nasales' },
  { mot: 'lapin', ipa: 'lapɛ̃', regle: 'nasale finale' },

  // --- la consonne double BLOQUE la nasalisation
  { mot: 'bonne', ipa: 'bɔn', regle: 'nn bloque la nasale' },
  { mot: 'homme', ipa: 'ɔm', regle: 'mm bloque la nasale' },
  { mot: 'année', ipa: 'ane', regle: 'nn bloque la nasale' },
  { mot: 'somme', ipa: 'sɔm', regle: 'mm bloque la nasale' },
  { mot: 'personne', ipa: 'pɛʁsɔn', regle: 'nn bloque la nasale' },

  // --- « on » suivi d'une VOYELLE ne nasalise pas
  { mot: 'bonobo', ipa: 'bonobo', regle: 'on + voyelle : pas de nasale' },
  { mot: 'ananas', ipa: 'anana', regle: 'an + voyelle : pas de nasale' },

  // --- e muet final / e maintenu
  { mot: 'table', ipa: 'tabl', regle: 'e final muet' },
  { mot: 'porte', ipa: 'pɔʁt', regle: 'e final muet' },
  { mot: 'je', ipa: 'ʒə', regle: 'monosyllabe outil : schwa maintenu' },
  { mot: 'le', ipa: 'lə', regle: 'monosyllabe outil : schwa maintenu' },

  // --- terminaisons verbales
  { mot: 'parlez', ipa: 'paʁle', regle: '-ez = /e/' },
  { mot: 'parler', ipa: 'paʁle', regle: '-er = /e/' },
  { mot: 'donner', ipa: 'dɔne', regle: '-er = /e/' },
  { mot: 'parlent', ipa: 'paʁl', regle: '-ent verbal entierement muet' },
  { mot: 'aiment', ipa: 'ɛm', regle: '-ent verbal entierement muet' },
  { mot: 'comment', ipa: 'kɔmɑ̃', regle: '-ent NON verbal : sonore' },
  { mot: 'souvent', ipa: 'suvɑ̃', regle: '-ent NON verbal : sonore' },
  { mot: 'vraiment', ipa: 'vʁɛmɑ̃', regle: '-ment adverbial : sonore' },

  // --- « ill »
  { mot: 'fille', ipa: 'fij', regle: 'ill = /j/' },
  { mot: 'famille', ipa: 'famij', regle: 'ill = /j/' },
  { mot: 'travail', ipa: 'tʁavaj', regle: 'ail final' },
  { mot: 'soleil', ipa: 'sɔlɛj', regle: 'eil final' },
  { mot: 'ville', ipa: 'vil', regle: 'exception lexicale : ill = /il/' },
  { mot: 'mille', ipa: 'mil', regle: 'exception lexicale : ill = /il/' },

  // --- cedille (etait supprimee par le pretraitement)
  { mot: 'ça', ipa: 'sa', regle: 'cedille = /s/' },
  { mot: 'garçon', ipa: 'ɡaʁsɔ̃', regle: 'cedille = /s/' },
  { mot: 'français', ipa: 'fʁɑ̃sɛ', regle: 'cedille + ai final' },

  // --- exceptions lexicales
  { mot: 'femme', ipa: 'fam', regle: 'exception lexicale' },
  { mot: 'monsieur', ipa: 'məsjø', regle: 'exception lexicale' },
  { mot: 'est', ipa: 'ɛ', regle: 'exception lexicale' },
  { mot: 'pied', ipa: 'pje', regle: 'exception lexicale' },
  { mot: 'temps', ipa: 'tɑ̃', regle: 'exception lexicale' },

  // --- digraphes et groupes consonantiques
  { mot: 'chose', ipa: 'ʃoz', regle: 'ch + s intervocalique = /z/' },
  { mot: 'photo', ipa: 'foto', regle: 'ph = /f/' },
  { mot: 'agneau', ipa: 'aɲo', regle: 'gn + eau' },
  { mot: 'quel', ipa: 'kɛl', regle: 'qu = /k/' },
  { mot: 'guitare', ipa: 'ɡitaʁ', regle: 'gu + i = /ɡ/' },
  { mot: 'nation', ipa: 'nasjɔ̃', regle: 'tion = /sjɔ̃/' },
  { mot: 'oiseau', ipa: 'wazo', regle: 'oi + s intervocalique + eau' },
  { mot: 'huile', ipa: 'ɥil', regle: 'ui = /ɥi/' },
]

describe('phonémiseur FR — corpus de prononciation académique', () => {
  for (const { mot, ipa, regle } of CORPUS) {
    test(`${mot} → /${ipa}/  (${regle})`, () => {
      const obtenu = phonemizeWord(mot).join('')
      assert.equal(
        classeVisuelle(obtenu),
        classeVisuelle(ipa),
        `« ${mot} » : attendu /${ipa}/, obtenu /${obtenu}/ — règle : ${regle}`,
      )
    })
  }

  test(`taux de justesse global ≥ 90 % sur les ${CORPUS.length} mots`, () => {
    const fautes = CORPUS.filter(
      (c) => classeVisuelle(phonemizeWord(c.mot).join('')) !== classeVisuelle(c.ipa),
    )
    const taux = (CORPUS.length - fautes.length) / CORPUS.length
    assert.ok(
      taux >= 0.9,
      `taux = ${(taux * 100).toFixed(1)} % (${fautes.length} fautes : `
      + `${fautes.map((f) => `${f.mot}→/${phonemizeWord(f.mot).join('')}/ au lieu de /${f.ipa}/`).join(', ')})`,
    )
  })
})

describe('phonémiseur FR — aucune consonne finale fantôme', () => {
  /**
   * Test de PROPRIÉTÉ, pas d'exemple : sur tout le corpus, aucun mot dont
   * l'orthographe finit par une consonne muette ne doit produire le phonème
   * correspondant en dernière position. C'est ce phonème fantôme qui fait
   * fermer les lèvres de l'avatar sur un son jamais prononcé.
   */
  const MUETTES: Record<string, string> = {
    t: 't', d: 'd', s: 's', x: 'ks', z: 'z', p: 'p', g: 'ɡ',
  }
  for (const { mot } of CORPUS) {
    const derniere = mot[mot.length - 1]
    const phoneme = MUETTES[derniere]
    if (!phoneme) continue
    test(`« ${mot} » ne finit pas sur un /${phoneme}/ fantôme`, () => {
      const phones = phonemizeWord(mot)
      assert.notEqual(
        phones[phones.length - 1],
        phoneme,
        `« ${mot} » → /${phones.join('')}/ : la consonne finale écrite « ${derniere} » `
        + 'est muette en français, elle ne doit pas produire de phonème.',
      )
    })
  }
})

describe('phonémiseur FR — invariants structurels', () => {
  test('aucun mot du corpus ne rend une suite vide', () => {
    for (const { mot } of CORPUS) {
      assert.ok(phonemizeWord(mot).length > 0, `« ${mot} » rend une suite vide`)
    }
  })

  test('déterministe : deux appels rendent la même suite', () => {
    for (const { mot } of CORPUS) {
      assert.deepEqual(phonemizeWord(mot), phonemizeWord(mot), mot)
    }
  })

  test('la casse et les espaces alentour ne changent rien', () => {
    for (const { mot } of CORPUS) {
      assert.deepEqual(phonemizeWord(`  ${mot.toUpperCase()} `), phonemizeWord(mot), mot)
    }
  })

  test('option « sonore » : restitue bien les consonnes finales écrites', () => {
    // Le comportement historique reste accessible et reste DISTINCT du défaut.
    assert.equal(phonemizeWord('petit', { finalesConsonnes: 'sonore' }).join(''), 'pətit')
    assert.equal(phonemizeWord('petit').join(''), 'pəti')
  })

  test('une phrase concatène exactement ses mots', () => {
    const phrase = 'le petit chat dort'
    const parMot = phrase.split(' ').flatMap((m) => phonemizeWord(m))
    assert.deepEqual(phonemizeSentence(phrase), parMot)
  })

  test('la ponctuation ne change pas la suite de phonèmes', () => {
    assert.deepEqual(
      phonemizeSentence('bonjour, comment ça va ?'),
      phonemizeSentence('bonjour comment ça va'),
    )
  })
})
