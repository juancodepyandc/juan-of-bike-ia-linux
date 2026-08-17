/**
 * Run 1161 — deux facons de lire un brief de travers.
 *
 * Les cas marques « brief reel » sont des extraits textuels du brief de la
 * Brulerie Nomade (output/code/audit_v118/payload.json).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  hintOccurrences,
  isNegatedAt,
  matchedHints,
  matchesAnyHint,
  matchesHint,
  normalizeHintText,
} from '../services/codePromptHints.ts'

const BRIEF_STYLE = "on n'est PAS un truc minimaliste blanc scandinave comme tout le monde fait "
  + "pour le café en ce moment, j'en ai marre de voir ça partout. On veut plutôt des couleurs "
  + 'chaudes, terracotta, marron torréfié, un peu de vert olive peut-être'
const BRIEF_IDEE = "un slogan (genre \"Torréfié cette semaine, pas l'an dernier\" ou un truc dans "
  + "le genre, trouve mieux si t'as une idée), et direct en dessous nos 3-4 cafés du moment"

describe('recherche par MOT ENTIER, pas par sous-chaine', () => {
  test('brief reel: « idée » ne demande pas un IDE', () => {
    const text = normalizeHintText(BRIEF_IDEE)
    assert.equal(text.includes('idee'), true, 'le mot est bien la')
    assert.equal(matchesHint(text, 'ide'), false)
    assert.equal(matchesAnyHint(text, ['ide', 'code editor', 'vscode']), false)
  })

  test('les autres sous-chaines piegeuses du francais sont neutralisees', () => {
    assert.equal(matchesHint(normalizeHintText('une carte du monde'), 'cart'), false)
    assert.equal(matchesHint(normalizeHintText('un ton monotone'), 'mono'), false)
    assert.equal(matchesHint(normalizeHintText('des options'), 'ops'), false)
    assert.equal(matchesHint(normalizeHintText('un histoire de stores'), 'store'), true)
  })

  test('une locution ne compte que si ses mots sont adjacents', () => {
    assert.equal(matchesHint(normalizeHintText('un editeur de code moderne'), 'editeur de code'), true)
    assert.equal(matchesHint(normalizeHintText('un editeur de texte, du code'), 'editeur de code'), false)
  })

  test('accents et apostrophes ne cachent pas un mot', () => {
    assert.equal(matchesHint(normalizeHintText("un évènement d'entreprise"), 'evenement'), true)
    assert.equal(matchesHint(normalizeHintText('e-commerce complet'), 'e-commerce'), true)
  })

  test('les occurrences multiples sont toutes trouvees', () => {
    assert.equal(hintOccurrences(normalizeHintText('blog puis blog puis blog'), 'blog').length, 3)
    assert.deepEqual(hintOccurrences(normalizeHintText('rien ici'), ''), [])
  })
})

describe('un mot NIE n est pas une commande', () => {
  test('brief reel: « PAS un truc minimaliste » ne demande pas du minimalisme', () => {
    const text = normalizeHintText(BRIEF_STYLE)
    assert.equal(hintOccurrences(text, 'minimaliste').length, 1, 'le mot est bien la')
    assert.equal(matchesHint(text, 'minimaliste'), false)
    assert.equal(matchesHint(text, 'blanc'), false)
    // …et ce que la cliente demande VRAIMENT est bien lu.
    assert.deepEqual(
      matchedHints(text, ['minimaliste', 'blanc', 'terracotta', 'olive']),
      ['terracotta', 'olive'],
    )
  })

  test('la negation ne franchit pas la ponctuation', () => {
    const text = normalizeHintText('pas de tableau de bord, juste un blog')
    assert.equal(matchesHint(text, 'blog'), true)
    assert.equal(matchesHint(text, 'tableau de bord'), false)
  })

  test('la negation ne porte pas au-dela de sa fenetre', () => {
    const loin = normalizeHintText('sans photo ni logo et vraiment tout ce qu il faut prevoir ensuite un blog')
    assert.equal(matchesHint(loin, 'blog'), true)
  })

  test('un mot nie une fois mais demande ailleurs reste demande', () => {
    const text = normalizeHintText('pas de blog corporate. Je veux un blog personnel')
    assert.equal(matchesHint(text, 'blog'), true)
  })

  test('marqueurs anglais aussi', () => {
    assert.equal(matchesHint(normalizeHintText('no dashboard please'), 'dashboard'), false)
    assert.equal(matchesHint(normalizeHintText('without any dashboard'), 'dashboard'), false)
    assert.equal(matchesHint(normalizeHintText('a clean dashboard'), 'dashboard'), true)
  })

  test('isNegatedAt se lit directement', () => {
    const text = normalizeHintText('surtout pas de gadget')
    const [at] = hintOccurrences(text, 'gadget')
    assert.equal(isNegatedAt(text, at), true)
  })
})
