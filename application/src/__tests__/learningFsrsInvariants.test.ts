/**
 * Répétition espacée FSRS — invariants du planificateur.
 *
 * POURQUOI CE FICHIER EXISTE. Le module se comportait bien sur les cas
 * simples, mais trois écarts documentés ne l'étaient par aucun test :
 *
 *   1. le RETOUR À LA MOYENNE de la difficulté visait D₀(Good) = w4 au lieu
 *      de D₀(Easy) = w4 − w5, ce que fixe la référence FSRS. L'écart par
 *      révision est minuscule (0,0124) mais il déplace le POINT FIXE de la
 *      suite : la difficulté d'équilibre s'établissait à 7,21 au lieu de
 *      6,68 — une demi-graduation de trop sur toute la collection, donc des
 *      intervalles systématiquement raccourcis ;
 *   2. le brouillage d'intervalle annonçait ±5 % et valait ±2,5 % (mesure sur
 *      5 000 cartes : amplitude [0,9750 ; 1,0250]) — deux fois moins
 *      d'étalement que voulu, donc des paquets de révision qui restent
 *      groupés le même jour, ce que le brouillage doit précisément éviter ;
 *   3. l'absence d'amortissement linéaire collait la difficulté au plafond
 *      après quelques échecs, et l'échelle perdait toute résolution dans le
 *      haut — là où se trouvent justement les cartes qui posent problème.
 *
 * MÉTHODE. Des invariants, pas des valeurs figées : un planificateur se juge
 * sur ses propriétés (monotonie, bornes, convergence), qui restent vraies
 * quels que soient les poids. Chaque test énonce la propriété qu'il défend.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/learningFsrsInvariants.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  review, makeNewCard, RATING, retrievability, isDue, pickDueCards, forecast,
  fuzzInterval, DEFAULT_FSRS_PARAMS, FSRS_DEFAULT_WEIGHTS,
  type FsrsCard, type Rating,
} from '../services/learning/spacedRepetition.ts'

const T0 = new Date('2026-01-01T00:00:00.000Z')
const JOUR = 86_400_000
const plus = (d: Date, jours: number) => new Date(d.getTime() + jours * JOUR)

describe('courbe d’oubli — accord entre R et l’intervalle', () => {
  test('R(S, S) vaut exactement la rétention visée par défaut (0,9)', () => {
    for (const S of [1, 5, 10, 100, 1000, 36500]) {
      assert.ok(
        Math.abs(retrievability(S, S) - 0.9) < 1e-9,
        `R(${S}, ${S}) = ${retrievability(S, S)} — la stabilité EST par définition `
        + 'l’intervalle au bout duquel il reste 90 % de chances de se souvenir.',
      )
    }
  })

  test('R décroît strictement avec le temps écoulé', () => {
    let précédent = 1
    for (let t = 0; t <= 200; t += 5) {
      const r = retrievability(t, 20)
      assert.ok(r <= précédent, `R remonte à t=${t}`)
      précédent = r
    }
  })

  test('R croît avec la stabilité, à temps écoulé constant', () => {
    let précédent = 0
    for (const S of [1, 2, 5, 10, 50, 200]) {
      const r = retrievability(10, S)
      assert.ok(r >= précédent, `R décroît quand S passe à ${S}`)
      précédent = r
    }
  })

  test('cas dégénérés', () => {
    assert.equal(retrievability(0, 5), 1, 'juste après la révision, on sait')
    assert.equal(retrievability(1, 0), 0, 'stabilité nulle : rien de mémorisé')
    assert.equal(retrievability(-3, 5), 1, 'temps négatif traité comme t=0')
  })
})

describe('planification — monotonie des notes', () => {
  test('Again ≤ Hard ≤ Good ≤ Easy, à tout stade de la carte', () => {
    let carte = review(makeNewCard(T0), RATING.Good, T0).card
    let horloge = T0
    for (let étape = 0; étape < 12; étape += 1) {
      horloge = plus(horloge, carte.scheduledDays)
      const intervalles = ([1, 2, 3, 4] as Rating[])
        .map((n) => review(carte, n, horloge).card.scheduledDays)
      for (let i = 1; i < 4; i += 1) {
        assert.ok(
          intervalles[i] >= intervalles[i - 1],
          `étape ${étape} : intervalles ${intervalles.join(' ≤ ')} — une note meilleure `
          + 'ne peut pas rapprocher la révision.',
        )
      }
      carte = review(carte, RATING.Good, horloge).card
    }
  })

  test('Easy augmente strictement la stabilité, Again la réduit', () => {
    const base = review(makeNewCard(T0), RATING.Good, T0).card
    const à = plus(T0, base.scheduledDays)
    assert.ok(review(base, RATING.Easy, à).card.stability > base.stability)
    assert.ok(review(base, RATING.Again, à).card.stability < base.stability)
  })
})

describe('planification — bornes qui ne cèdent jamais', () => {
  test('difficulté dans [1, 10] sur 500 révisions aléatoires', () => {
    let carte = makeNewCard(T0)
    let horloge = T0
    let graine = 42
    for (let i = 0; i < 500; i += 1) {
      graine = (graine * 1103515245 + 12345) & 0x7fffffff
      const note = ((graine % 4) + 1) as Rating
      horloge = plus(horloge, Math.max(1, carte.scheduledDays))
      carte = review(carte, note, horloge).card
      assert.ok(
        carte.difficulty >= 1 && carte.difficulty <= 10,
        `difficulté ${carte.difficulty} à la révision ${i}`,
      )
      assert.ok(carte.stability > 0, `stabilité ${carte.stability} à la révision ${i}`)
      assert.ok(Number.isFinite(carte.stability), `stabilité non finie à la révision ${i}`)
      assert.ok(carte.scheduledDays >= 1, `intervalle ${carte.scheduledDays} à la révision ${i}`)
      assert.ok(carte.scheduledDays <= DEFAULT_FSRS_PARAMS.maximumInterval)
    }
  })

  test('200 « Easy » d’affilée : l’intervalle plafonne sans déborder', () => {
    let carte = review(makeNewCard(T0), RATING.Easy, T0).card
    let horloge = T0
    for (let i = 0; i < 200; i += 1) {
      horloge = plus(horloge, carte.scheduledDays)
      carte = review(carte, RATING.Easy, horloge).card
    }
    assert.equal(carte.scheduledDays, DEFAULT_FSRS_PARAMS.maximumInterval)
    assert.ok(carte.difficulty >= 1)
  })

  test('200 « Again » d’affilée : les échecs sont comptés, l’état est cohérent', () => {
    let carte = review(makeNewCard(T0), RATING.Again, T0).card
    let horloge = T0
    for (let i = 0; i < 200; i += 1) {
      horloge = plus(horloge, 1)
      carte = review(carte, RATING.Again, horloge).card
    }
    // La toute premiere note « Again » porte sur une carte NEUVE : elle la
    // fait passer en apprentissage sans compter d'echec. Les 200 suivantes
    // comptent chacune le leur.
    assert.equal(carte.lapses, 200)
    assert.equal(carte.state, 'relearning')
    assert.ok(carte.stability > 0)
  })

  test('l’amortissement laisse de la résolution en haut de l’échelle', () => {
    // Sans amortissement linéaire, la difficulté se colle à 10 et toutes les
    // cartes difficiles deviennent indiscernables entre elles.
    let carte = review(makeNewCard(T0), RATING.Again, T0).card
    let horloge = T0
    for (let i = 0; i < 30; i += 1) {
      horloge = plus(horloge, 1)
      carte = review(carte, RATING.Again, horloge).card
    }
    assert.ok(
      carte.difficulty < 10,
      `difficulté collée au plafond (${carte.difficulty}) : l’échelle ne distingue `
      + 'plus les cartes difficiles entre elles.',
    )
    assert.ok(carte.difficulty > 8, `difficulté ${carte.difficulty} : trop clémente après 30 échecs`)
  })
})

describe('brouillage d’intervalle', () => {
  test('l’amplitude est bien de ±5 %, comme annoncé', () => {
    let min = Infinity
    let max = -Infinity
    for (let i = 0; i < 5000; i += 1) {
      const facteur = fuzzInterval(1000, `carte-${i}`) / 1000
      min = Math.min(min, facteur)
      max = Math.max(max, facteur)
    }
    assert.ok(max >= 1.04, `amplitude haute mesurée à ${max.toFixed(4)} au lieu de ~1,05`)
    assert.ok(min <= 0.96, `amplitude basse mesurée à ${min.toFixed(4)} au lieu de ~0,95`)
    assert.ok(max <= 1.06 && min >= 0.94, `amplitude hors bornes : [${min.toFixed(4)} ; ${max.toFixed(4)}]`)
  })

  test('déterministe pour une même carte', () => {
    for (let i = 0; i < 50; i += 1) {
      assert.equal(fuzzInterval(300, `c${i}`), fuzzInterval(300, `c${i}`))
    }
  })

  test('les cartes se répartissent au lieu de rester groupées', () => {
    // 200 cartes échues le même jour à 30 jours : le brouillage doit les
    // étaler sur plusieurs journées distinctes.
    const jours = new Set(Array.from({ length: 200 }, (_, i) => fuzzInterval(30, `c${i}`)))
    assert.ok(jours.size >= 3, `${jours.size} journée(s) distincte(s) — étalement insuffisant`)
  })

  test('les intervalles courts ne sont pas brouillés', () => {
    assert.equal(fuzzInterval(1, 'x'), 1)
    assert.equal(fuzzInterval(2, 'x'), 2)
  })

  test('jamais en dessous d’un jour', () => {
    for (let i = 0; i < 200; i += 1) assert.ok(fuzzInterval(3, `c${i}`) >= 1)
  })
})

describe('file de révision', () => {
  const carteÀ = (due: string): FsrsCard => ({ ...makeNewCard(T0), due })

  test('isDue compare bien à l’instant fourni', () => {
    const c = carteÀ(plus(T0, 5).toISOString())
    assert.equal(isDue(c, T0), false)
    assert.equal(isDue(c, plus(T0, 5)), true)
    assert.equal(isDue(c, plus(T0, 6)), true)
  })

  test('pickDueCards : les plus en retard d’abord, et rien qui ne soit échu', () => {
    const paquet = [
      { id: 'futur', card: carteÀ(plus(T0, 3).toISOString()) },
      { id: 'retard-2j', card: carteÀ(plus(T0, -2).toISOString()) },
      { id: 'retard-5j', card: carteÀ(plus(T0, -5).toISOString()) },
      { id: 'aujourdhui', card: carteÀ(T0.toISOString()) },
    ]
    const dus = pickDueCards(paquet, T0)
    assert.deepEqual(dus.map((d) => d.id), ['retard-5j', 'retard-2j', 'aujourdhui'])
  })

  test('pickDueCards respecte la limite', () => {
    const paquet = Array.from({ length: 50 }, (_, i) => ({
      id: String(i), card: carteÀ(plus(T0, -i - 1).toISOString()),
    }))
    assert.equal(pickDueCards(paquet, T0, 10).length, 10)
  })

  test('forecast compte chaque carte une fois et une seule', () => {
    const paquet = [
      { card: carteÀ(plus(T0, -3).toISOString()) },
      { card: carteÀ(plus(T0, 0).toISOString()) },
      { card: carteÀ(plus(T0, 2).toISOString()) },
      { card: carteÀ(plus(T0, 7).toISOString()) },
      { card: carteÀ(plus(T0, 99).toISOString()) },
    ]
    const seaux = forecast(paquet, 7, T0)
    assert.equal(seaux.length, 8)
    const total = seaux.reduce((a, b) => a + b, 0)
    assert.equal(total, 4, 'la carte à 99 jours est hors horizon ; les 4 autres sont comptées')
    assert.equal(seaux[0], 2, 'le retard et le jour même tombent dans le seau 0')
  })
})

describe('cohérence du paramétrage annoncé', () => {
  test('le vecteur de poids a la taille déclarée', () => {
    assert.equal(FSRS_DEFAULT_WEIGHTS.length, 21)
    assert.equal(DEFAULT_FSRS_PARAMS.w.length, 21)
    for (const w of FSRS_DEFAULT_WEIGHTS) assert.ok(Number.isFinite(w), 'poids non fini')
  })

  test('la rétention visée est atteinte par l’intervalle planifié', () => {
    // Propriété d'accord : l'intervalle rendu doit être celui auquel la
    // rétrievabilité retombe sur la cible. C'est ce qui lie la courbe et son
    // inverse ; les découpler produirait un planificateur incohérent.
    const carte = review(makeNewCard(T0), RATING.Good, T0).card
    const r = retrievability(carte.scheduledDays, carte.stability)
    assert.ok(
      Math.abs(r - DEFAULT_FSRS_PARAMS.requestRetention) < 0.05,
      `intervalle de ${carte.scheduledDays} j pour S=${carte.stability.toFixed(2)} : `
      + `R = ${r.toFixed(3)} au lieu de ${DEFAULT_FSRS_PARAMS.requestRetention}`,
    )
  })

  test('une rétention plus exigeante rapproche les révisions', () => {
    const carte = review(makeNewCard(T0), RATING.Good, T0).card
    const à = plus(T0, carte.scheduledDays)
    const exigeant = review(carte, RATING.Good, à, { ...DEFAULT_FSRS_PARAMS, requestRetention: 0.95 })
    const relâché = review(carte, RATING.Good, à, { ...DEFAULT_FSRS_PARAMS, requestRetention: 0.8 })
    assert.ok(
      exigeant.card.scheduledDays < relâché.card.scheduledDays,
      `95 % → ${exigeant.card.scheduledDays} j, 80 % → ${relâché.card.scheduledDays} j`,
    )
  })

  test('le journal de révision reflète la carte produite', () => {
    const { card, log } = review(makeNewCard(T0), RATING.Good, T0)
    assert.equal(log.due, card.due)
    assert.equal(log.stability, card.stability)
    assert.equal(log.difficulty, card.difficulty)
    assert.equal(log.state, card.state)
    assert.equal(log.reviewedAt, T0.toISOString())
  })

  test('une révision est pure : la carte d’entrée n’est pas modifiée', () => {
    const avant = review(makeNewCard(T0), RATING.Good, T0).card
    const copie = JSON.parse(JSON.stringify(avant))
    review(avant, RATING.Again, plus(T0, 10))
    assert.deepEqual(avant, copie, 'review() a muté son argument')
  })
})
