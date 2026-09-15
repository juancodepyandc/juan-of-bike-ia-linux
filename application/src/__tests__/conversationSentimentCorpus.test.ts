/**
 * Analyse de sentiment française — corpus de polarité.
 *
 * POURQUOI CE FICHIER EXISTE. Le lexique manquait ses mots les plus utiles.
 * Mesure : « catastrophe totale, rien ne marche » sortait NEUTRE, score 0.
 * Deux causes cumulées : « catastrophe » n'était pas au lexique, et « rien »
 * n'était pas dans les négations — de sorte que « marche » était compté du
 * côté POSITIF. Une négation absente n'atténue pas le verdict, elle l'INVERSE.
 *
 * Un analyseur qui rend « neutre » sur une phrase de détresse est pire
 * qu'inutile : il fait croire que tout va bien.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/conversationSentimentCorpus.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSentiment } from '../services/conversationSentiment.ts'

type Polarité = 'positive' | 'negative' | 'neutral'

const CORPUS: Array<[string, Polarité, string]> = [
  // --- détresse : ne doivent jamais sortir neutres
  ['catastrophe totale, rien ne marche', 'negative', 'lexique de détresse + négation'],
  ['c’est un désastre complet', 'negative', 'désastre'],
  ['je suis bloqué depuis trois heures', 'negative', 'blocage'],
  ['ras le bol de ces plantages', 'negative', 'exaspération'],
  ['ce truc est inutilisable', 'negative', 'jugement fort'],
  ['j’en ai marre, c’est un cauchemar', 'negative', 'deux marqueurs'],
  ['l’application plante en boucle', 'negative', 'plantage'],
  ['c’est lamentable', 'negative', 'jugement fort'],

  // --- satisfaction
  ['tout fonctionne, impeccable', 'positive', 'satisfaction'],
  ['merci, c’est exactement ça', 'positive', 'remerciement'],
  ['génial, ça marche enfin', 'positive', 'soulagement'],
  ['le rendu est magnifique', 'positive', 'esthétique'],
  ['c’est rapide et fiable', 'positive', 'qualités techniques'],
  ['problème résolu, nickel', 'positive', 'résolution'],

  // --- négation : le lexique seul donnerait le verdict inverse
  ['je ne suis pas content du tout', 'negative', 'négation d’un positif'],
  ['ce n’est pas mauvais', 'positive', 'litote — négation d’un négatif'],
  ['rien ne fonctionne', 'negative', 'négation par « rien »'],
  ['ce n’est jamais fiable', 'negative', 'négation par « jamais »'],
  ['aucun problème', 'positive', 'négation d’un négatif'],
  ['sans aucune difficulté', 'positive', 'double négation'],

  // --- neutres : ne doivent pas être colorés
  ['la réunion est à quatorze heures', 'neutral', 'énoncé factuel'],
  ['peux-tu ouvrir le fichier de configuration ?', 'neutral', 'demande'],
  ['il y a trois modules dans ce dossier', 'neutral', 'constat'],
]

describe('analyzeSentiment — corpus de polarité', () => {
  for (const [texte, attendue, pourquoi] of CORPUS) {
    test(`${attendue.padEnd(8)} — « ${texte} »  (${pourquoi})`, () => {
      const r = analyzeSentiment(texte)
      // « mixed » compte comme la polarité du signe du score : ce qui est
      // interdit, c’est de se tromper de CAMP.
      const effective: Polarité = r.polarity === 'mixed'
        ? (r.score > 0 ? 'positive' : r.score < 0 ? 'negative' : 'neutral')
        : r.polarity
      assert.equal(
        effective, attendue,
        `« ${texte} » : attendu ${attendue}, obtenu ${r.polarity} (score ${r.score}, `
        + `positifs ${JSON.stringify(r.positiveTokens.map((t) => t.token))}, `
        + `négatifs ${JSON.stringify(r.negativeTokens.map((t) => t.token))}, `
        + `négations ${JSON.stringify(r.negations)})`,
      )
    })
  }

  test('aucune phrase de détresse ne sort neutre', () => {
    const détresse = CORPUS.filter(([, p]) => p === 'negative')
    const neutres = détresse.filter(([t]) => analyzeSentiment(t).score === 0)
    assert.deepEqual(neutres.map(([t]) => t), [], 'ces phrases de détresse sont notées 0')
  })

  test('taux de justesse ≥ 90 % sur le corpus', () => {
    const fautes = CORPUS.filter(([t, attendue]) => {
      const r = analyzeSentiment(t)
      const eff = r.polarity === 'mixed'
        ? (r.score > 0 ? 'positive' : r.score < 0 ? 'negative' : 'neutral')
        : r.polarity
      return eff !== attendue
    })
    const taux = (CORPUS.length - fautes.length) / CORPUS.length
    assert.ok(taux >= 0.9, `${(taux * 100).toFixed(1)} % — fautes : ${fautes.map(([t]) => t).join(' | ')}`)
  })
})

describe('analyzeSentiment — entrées de lexique en plusieurs mots', () => {
  /**
   * Ces entrées existaient dans la table mais étaient INATTEIGNABLES : la
   * boucle ne comparait que des jetons isolés, si bien qu'une clé contenant
   * une espace ne pouvait jamais correspondre. Elles se lisaient comme
   * couvertes et ne pesaient jamais.
   */
  const MULTI: Array<[string, string, string]> = [
    ['ras le bol de ces plantages', 'ras le bol', 'negative'],
    ['je déteste ce comportement', 'je deteste', 'negative'],
    ['ça marche enfin', 'ca marche', 'positive'],
    ['le résultat est au top', 'au top', 'positive'],
  ]
  for (const [phrase, clé, polarité] of MULTI) {
    test(`« ${clé} » est atteinte dans « ${phrase} »`, () => {
      const r = analyzeSentiment(phrase)
      const vus = [...r.positiveTokens, ...r.negativeTokens].map((t) => t.token)
      assert.ok(vus.includes(clé), `entrée « ${clé} » non atteinte — jetons vus : ${JSON.stringify(vus)}`)
      assert.equal(r.polarity === 'mixed' ? (r.score > 0 ? 'positive' : 'negative') : r.polarity, polarité)
    })
  }

  test('les deux apostrophes donnent le même verdict', () => {
    const droite = analyzeSentiment("j'adore ce rendu")
    const typographique = analyzeSentiment('j\u2019adore ce rendu')
    assert.equal(typographique.polarity, 'positive',
      'l’apostrophe typographique U+2019 est celle des claviers français : '
      + 'le même mot ne peut pas changer de sentiment selon la touche employée.')
    assert.equal(typographique.score, droite.score)
  })

  test('le pluriel se replie sur le singulier du lexique', () => {
    assert.equal(analyzeSentiment('encore des plantages').polarity, 'negative')
    assert.equal(analyzeSentiment('trop d’erreurs').polarity, 'negative')
  })

  test('le repli de pluriel n’invente pas de sentiment', () => {
    // « pas » finit par « s » mais « pa » n'est pas au lexique : rien ne doit
    // être compté.
    const r = analyzeSentiment('trois vis et deux pas de porte')
    assert.equal(r.score, 0, `jetons comptés à tort : ${JSON.stringify(r.negativeTokens)}`)
  })

  test('la correspondance la plus longue l’emporte', () => {
    // « déteste » seul vaut -2 ; « je déteste » vaut -2,5. La fenêtre longue
    // doit gagner, et le mot ne doit pas être compté deux fois.
    const r = analyzeSentiment('je déteste')
    assert.equal(r.negativeTokens.length, 1, JSON.stringify(r.negativeTokens))
    assert.equal(r.negativeTokens[0].token, 'je deteste')
  })
})

describe('analyzeSentiment — invariants', () => {
  test('texte vide et espaces : neutre, intensité nulle', () => {
    for (const t of ['', '   ', '\n\t']) {
      const r = analyzeSentiment(t)
      assert.equal(r.score, 0)
      assert.equal(r.polarity, 'neutral')
      assert.equal(r.intensity, 0)
    }
  })

  test('l’intensité reste dans [0, 1]', () => {
    for (const [t] of CORPUS) {
      const r = analyzeSentiment(t)
      assert.ok(r.intensity >= 0 && r.intensity <= 1, `${t} → ${r.intensity}`)
    }
  })

  test('les accents et la casse ne changent pas le verdict', () => {
    assert.equal(
      analyzeSentiment('CATASTROPHE').polarity,
      analyzeSentiment('catastrophe').polarity,
    )
  })

  test('l’emphase renforce sans inverser', () => {
    const calme = analyzeSentiment('merci')
    const appuyé = analyzeSentiment('MERCI !!!')
    assert.equal(appuyé.polarity, 'positive')
    assert.ok(appuyé.score >= calme.score, 'l’emphase ne doit pas affaiblir')
    assert.ok(appuyé.emphasis > calme.emphasis)
  })

  test('déterministe', () => {
    for (const [t] of CORPUS) assert.deepEqual(analyzeSentiment(t), analyzeSentiment(t))
  })
})
