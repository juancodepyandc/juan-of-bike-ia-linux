/**
 * Détecteur de traces d'IA dans le code livré — justesse ET absence de faux
 * positifs.
 *
 * POURQUOI CE FICHIER EXISTE. La porte qui refuse les pictogrammes en guise
 * d'icônes énumérait des plages Unicode recopiées à la main :
 * `1F300-1FAFF`, `2600-27BF`, `1F000-1F02F`. Mesure sur 28 glyphes : elle
 * laissait passer `⭐` (U+2B50), `▶️` (U+25B6 + VS16), `⌚` (U+231A),
 * `⏰` (U+23F0), les drapeaux `🇫🇷` (paire d'indicateurs régionaux) et les
 * pavés numériques `1️⃣` — tous des icônes de pacotille de premier choix,
 * simplement situées hors des bornes recopiées.
 *
 * Le détecteur s'appuie désormais sur les propriétés Unicode, qui sont la
 * définition normative (UTS #51), et non sur des bornes.
 *
 * DEUX ÉTAGES, ASSUMÉS.
 *   étage 1, `containsTrueEmoji` : présentation graphique par défaut
 *     (`Emoji_Presentation`), ou forcée par VS16, ou drapeau. C'est ce que le
 *     navigateur rend en couleur.
 *   étage 2, `containsPictographicEmoji` : ajoute les dingbats employés EN
 *     GUISE d'icône (`★ ✓ ▶`). Ce ne sont pas des emoji — `Emoji=No` pour
 *     `★` — mais quand ils tiennent lieu d'icône produit c'est la même
 *     pauvreté visuelle.
 *
 * L'ABSENCE DE FAUX POSITIF compte autant que la détection : `©` `®` `™` `€`
 * `±` `°` `→` `«»` sont de la typographie légitime. Faire tomber la porte sur
 * un en-tête `// © 2026` obligerait à retirer une mention légale.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/codeAiTraceDetector.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  containsPictographicEmoji, containsTrueEmoji, detectEmojiIcons,
} from '../services/codeCompositionGate.ts'

/** Emoji qui doivent être refusés — sinon la trace d'IA passe en production. */
const VRAIS_EMOJI: Array<[string, string]> = [
  ['🚀', 'fusée — le poncif absolu'],
  ['✨', 'étincelles'],
  ['📊', 'graphique'],
  ['⚡', 'éclair'],
  ['✅', 'coche verte'],
  ['🎯', 'cible'],
  ['🔒', 'cadenas'],
  ['❤️', 'cœur avec VS16'],
  ['👍🏽', 'pouce avec modificateur de teint'],
  ['👨‍💻', 'emoji composé par ZWJ'],
  ['🇫🇷', 'drapeau — paire d’indicateurs régionaux, hors des plages recopiées'],
  ['♻️', 'recyclage en présentation emoji'],
  ['▶️', 'triangle lecture U+25B6 + VS16, hors des plages recopiées'],
  ['⭐', 'étoile U+2B50, hors des plages recopiées'],
  ['⌚', 'montre U+231A, hors des plages recopiées'],
  ['⏰', 'réveil U+23F0, hors des plages recopiées'],
  ['1️⃣', 'pavé numérique'],
  ['🥇', 'médaille'],
  ['☕', 'tasse'],
  ['😀', 'visage'],
]

/** Typographie légitime — la refuser serait un faux positif. */
const TYPOGRAPHIE_LEGITIME: Array<[string, string]> = [
  ['// © 2026 Aurora', 'mention de licence'],
  ['const marque = "Aurora®"', 'marque déposée'],
  ['<p>Aurora™</p>', 'marque commerciale'],
  ['<p>Prix : 12 € — soldes</p>', 'euro et tiret cadratin'],
  ['const µs = 1e-6', 'micro'],
  ['/* ½ ¼ ¾ */', 'fractions'],
  ['<p>±3 °C</p>', 'plus-ou-moins et degré'],
  ['const fleche = "→"', 'flèche typographique'],
  ['<p>« citation »</p>', 'guillemets français'],
  ['<p>Ω : R = 5Ω</p>', 'oméga'],
  ['<p>Français, œuvre, ÿ</p>', 'latin étendu'],
  ['<p>日本語のテキスト</p>', 'idéogrammes'],
  ['const a = b => c', 'flèche grosse'],
  ['if (a < b && c > d) {}', 'comparateurs'],
  ['<p>n° 4, §2, ¶3</p>', 'numéro, section, pied-de-mouche'],
]

describe('étage 1 — containsTrueEmoji', () => {
  for (const [glyphe, pourquoi] of VRAIS_EMOJI) {
    test(`refuse ${glyphe} (${pourquoi})`, () => {
      assert.equal(containsTrueEmoji(`<span>${glyphe}</span>`), true, `${glyphe} non détecté`)
    })
  }

  for (const [source, pourquoi] of TYPOGRAPHIE_LEGITIME) {
    test(`accepte — ${pourquoi}`, () => {
      assert.equal(
        containsTrueEmoji(source), false,
        `faux positif sur ${JSON.stringify(source)} : ce n’est pas un emoji.`,
      )
    })
  }

  test('les dingbats typographiques ne sont PAS des emoji', () => {
    for (const g of ['✓', '✔', '★', '☆', '▶', '●']) {
      assert.equal(containsTrueEmoji(g), false, `${g} classé emoji à tort`)
    }
  })

  test('un appel n’influence pas le suivant (pas de lastIndex partagé)', () => {
    for (let i = 0; i < 5; i += 1) {
      assert.equal(containsTrueEmoji('🚀'), true, `appel ${i + 1}`)
      assert.equal(containsTrueEmoji('rien ici'), false, `appel ${i + 1}`)
    }
  })
})

describe('étage 2 — containsPictographicEmoji', () => {
  test('couvre tout l’étage 1', () => {
    for (const [glyphe] of VRAIS_EMOJI) {
      assert.equal(containsPictographicEmoji(glyphe), true, `${glyphe} manqué`)
    }
  })

  test('ajoute les dingbats employés en guise d’icône', () => {
    for (const g of ['★', '☆', '✓', '✔', '▶', '◀', '●', '♥']) {
      assert.equal(containsPictographicEmoji(g), true, `${g} manqué`)
    }
  })

  test('la typographie légitime reste acceptée', () => {
    for (const [source, pourquoi] of TYPOGRAPHIE_LEGITIME) {
      assert.equal(
        containsPictographicEmoji(source), false,
        `faux positif sur ${JSON.stringify(source)} (${pourquoi})`,
      )
    }
  })

  test('des étoiles produites par une expression JavaScript sont vues', () => {
    // Cas mesuré au run 1061 : le navigateur les affichait, l’analyse de
    // source ne les voyait pas.
    const source = "return <div className=\"stars\">{'★'.repeat(rating)}{'☆'.repeat(5 - rating)}</div>"
    assert.equal(containsPictographicEmoji(source), true)
  })
})

describe('detectEmojiIcons — le pictogramme en POSITION d’icône', () => {
  test('un pictogramme seul dans un élément est repéré', () => {
    const trouvés = detectEmojiIcons([
      { name: 'App.tsx', content: '<span className="icon">🚀</span>' },
    ])
    assert.deepEqual(trouvés, ['🚀'])
  })

  test('les pictogrammes hors des anciennes plages sont repérés aussi', () => {
    const trouvés = detectEmojiIcons([
      { name: 'a.tsx', content: '<i>⭐</i><i>▶️</i><i>⌚</i>' },
    ])
    for (const g of ['⭐', '▶️', '⌚']) {
      assert.ok(trouvés.some((t) => t.includes(g[0])), `${g} manqué — trouvés : ${trouvés.join(' ')}`)
    }
  })

  test('un pictogramme noyé dans une phrase n’est pas une icône', () => {
    assert.deepEqual(
      detectEmojiIcons([
        { name: 'a.html', content: '<p>Le lancement 🚀 a eu lieu hier soir à Kourou.</p>' },
      ]),
      [],
    )
  })

  test('les fichiers non-markup sont ignorés', () => {
    assert.deepEqual(detectEmojiIcons([{ name: 'notes.md', content: '# 📊 titre' }]), [])
    assert.deepEqual(detectEmojiIcons([{ name: 'data.json', content: '{"a":"📊"}' }]), [])
  })

  test('aucun doublon dans le rapport', () => {
    const trouvés = detectEmojiIcons([
      { name: 'a.tsx', content: '<i>🚀</i><i>🚀</i><i>🚀</i>' },
    ])
    assert.equal(trouvés.length, 1)
  })
})
