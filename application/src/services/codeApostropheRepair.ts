// Reparer deterministiquement l apostrophe francaise dans un litteral.
//
// Mesure reelle (run 1051, brulerie): le pipeline a diagnostique NEUF fois de
// suite, correctement et a la bonne position, `MarketCalendar.tsx: syntaxe
// invalide` — puis a rendu « boucle infinie detectee sur la meme erreur apres
// 9 passes ». La cause tient en une ligne, presente deux fois (24 et 45):
//
//     location: 'Presqu'île',
//
// L apostrophe de « Presqu'île » ferme le litteral. Le modele echoue parce que,
// a chaque passe, il REECRIT le meme texte francais et reproduit exactement la
// meme rupture: c est un piege systematique, pas une inattention. Lui redonner
// sa chance une dixieme fois ne pouvait pas marcher.
//
// Or ce cas est mecaniquement decidable: une apostrophe encadree par deux
// lettres, a l interieur d un litteral simple, est du CONTENU — jamais un
// terminateur. Ligne directrice du module: quand une correction est
// deterministe, on ne la delegue pas a un modele probabiliste.
//
// La prudence porte sur la portee, pas sur la certitude: on ne touche qu au cas
// « lettre ' lettre », on ignore commentaires, gabarits et litterals doubles, et
// on ne modifie jamais un fichier deja valide.

type ScanState = 'code' | 'single' | 'double' | 'template' | 'line_comment' | 'block_comment'

const LETTER = /[\p{L}]/u

/**
 * Echappe les apostrophes de contenu dans les litterals a guillemets simples.
 * Retourne le texte inchange si rien n est certain.
 */
export function repairFrenchApostrophes(source: string): { code: string; repairs: number } {
  let state: ScanState = 'code'
  let out = ''
  let repairs = 0

  for (let i = 0; i < source.length; i++) {
    const ch = source[i]
    const next = source[i + 1] ?? ''
    const prev = source[i - 1] ?? ''

    if (state === 'code') {
      if (ch === '/' && next === '/') { state = 'line_comment'; out += ch; continue }
      if (ch === '/' && next === '*') { state = 'block_comment'; out += ch; continue }
      if (ch === "'") { state = 'single'; out += ch; continue }
      if (ch === '"') { state = 'double'; out += ch; continue }
      if (ch === '`') { state = 'template'; out += ch; continue }
      out += ch
      continue
    }

    if (state === 'line_comment') {
      if (ch === '\n') state = 'code'
      out += ch
      continue
    }

    if (state === 'block_comment') {
      if (ch === '*' && next === '/') state = 'code'
      out += ch
      continue
    }

    if (state === 'double') {
      if (ch === '"' && prev !== '\\') state = 'code'
      out += ch
      continue
    }

    if (state === 'template') {
      if (ch === '`' && prev !== '\\') state = 'code'
      out += ch
      continue
    }

    // state === 'single'
    if (ch === '\\') { out += ch + next; i++; continue }
    if (ch === '\n') {
      // Un litteral simple ne franchit pas la ligne: le fichier est casse
      // autrement que par une apostrophe. On rend la main sans rien inventer.
      state = 'code'
      out += ch
      continue
    }
    if (ch === "'") {
      // LE cas certain: encadre par deux lettres, c est du contenu.
      if (LETTER.test(prev) && LETTER.test(next)) {
        out += "\\'"
        repairs++
        continue
      }
      state = 'code'
      out += ch
      continue
    }
    out += ch
  }

  return { code: out, repairs }
}

/** Le fichier merite-t-il d etre examine ? (extensions a litterals JS/TS) */
export function isApostropheRepairable(name: string): boolean {
  return /\.(?:jsx?|tsx?|mjs|cjs)$/i.test(name)
}
