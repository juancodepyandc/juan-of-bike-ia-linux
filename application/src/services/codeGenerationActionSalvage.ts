// ---------------------------------------------------------------------------
// codeGenerationActionSalvage — recupere une charge utile d actions WS3 abimee
// au lieu de faire tomber tout le projet.
//
// Observe en run reel, deux fois de suite sur un brief complexe: le pipeline
// meurt sur `action_producer_failed:action_protocol_invalid:json_payload_invalid`
// apres avoir deja ecrit huit a quatorze fichiers. Tout le run est perdu.
//
// Deux modes de corruption, distincts et tous deux frequents avec des modeles
// locaux qui doivent emettre un fichier de code ENTIER dans une chaine JSON:
//
//  1. `json_payload_invalid` — la charge est equilibree (accolades fermees) mais
//     `JSON.parse` la refuse, parce que le modele a insere de VRAIS retours a la
//     ligne et tabulations dans la chaine `content` au lieu de `\n` / `\t`. Le
//     scanner de JSON ne le voit pas: un saut de ligne brut ne casse pas le
//     suivi des guillemets. C est reparable exactement: on re-echappe les
//     caracteres de controle a l interieur des chaines.
//
//  2. `json_payload_missing` — la charge n a jamais ete fermee: le modele a
//     atteint sa limite de tokens au milieu du `content`. Le fichier cible est
//     alors recuperable partiellement, ce qui vaut mieux qu un run perdu: la
//     boucle de correction sait completer un fichier incomplet, elle ne sait
//     rien faire d un projet vide.
//
// Ces reparations ne s appliquent QUE sur un chemin deja en echec: elles ne
// peuvent pas degrader une charge utile valide.
// ---------------------------------------------------------------------------

const CONTROL_ESCAPES: Record<string, string> = {
  '\n': '\\n',
  '\r': '\\r',
  '\t': '\\t',
  '\b': '\\b',
  '\f': '\\f',
}

/**
 * Re-echappe les caracteres de controle bruts presents A L INTERIEUR des chaines
 * JSON. Hors chaine, ils sont de l espacement legal et restent intacts.
 */
export function repairJsonControlCharacters(json: string): string {
  let out = ''
  let inString = false
  let escaped = false

  for (let i = 0; i < json.length; i++) {
    const char = json[i]

    if (!inString) {
      if (char === '"') inString = true
      out += char
      continue
    }

    if (escaped) {
      escaped = false
      out += char
      continue
    }
    if (char === '\\') {
      escaped = true
      out += char
      continue
    }
    if (char === '"') {
      inString = false
      out += char
      continue
    }

    const mapped = CONTROL_ESCAPES[char]
    if (mapped) {
      out += mapped
      continue
    }
    // Tout autre caractere de controle non imprimable est illegal en JSON.
    if (char < ' ') {
      out += `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`
      continue
    }
    out += char
  }

  return out
}

/** Decode les echappements JSON d un fragment de chaine tronque. */
function decodeJsonStringFragment(fragment: string): string {
  let out = ''
  for (let i = 0; i < fragment.length; i++) {
    const char = fragment[i]
    if (char !== '\\') {
      out += char
      continue
    }
    const next = fragment[i + 1]
    if (next === undefined) break // echappement coupe net par la troncature
    i++
    switch (next) {
      case 'n': out += '\n'; break
      case 'r': out += '\r'; break
      case 't': out += '\t'; break
      case 'b': out += '\b'; break
      case 'f': out += '\f'; break
      case '"': out += '"'; break
      case '\\': out += '\\'; break
      case '/': out += '/'; break
      case 'u': {
        const hex = fragment.slice(i + 1, i + 5)
        if (/^[0-9a-fA-F]{4}$/.test(hex)) {
          out += String.fromCharCode(parseInt(hex, 16))
          i += 4
        }
        break
      }
      default: out += next
    }
  }
  return out
}

export type SalvagedWriteFile = {
  path: string
  language?: string
  content: string
  truncated: true
}

function readJsonStringValue(raw: string, keyIndex: number): { value: string; closed: boolean } | null {
  const colon = raw.indexOf(':', keyIndex)
  if (colon < 0) return null
  const quote = raw.indexOf('"', colon)
  if (quote < 0) return null

  let escaped = false
  for (let i = quote + 1; i < raw.length; i++) {
    const char = raw[i]
    if (escaped) { escaped = false; continue }
    if (char === '\\') { escaped = true; continue }
    if (char === '"') {
      return { value: decodeJsonStringFragment(raw.slice(quote + 1, i)), closed: true }
    }
  }
  // Jamais referme: tronque.
  return { value: decodeJsonStringFragment(raw.slice(quote + 1)), closed: false }
}

/**
 * Recupere le `write_file` d une charge utile jamais refermee (limite de tokens
 * atteinte au milieu du contenu). Retourne null si rien d exploitable.
 */
export function salvageTruncatedWriteFile(raw: string): SalvagedWriteFile | null {
  const kindIndex = raw.search(/"kind"\s*:\s*"write_file"/)
  if (kindIndex < 0) return null

  const pathKey = raw.search(/"path"\s*:/)
  if (pathKey < 0) return null
  const pathRead = readJsonStringValue(raw, pathKey)
  if (!pathRead || !pathRead.closed || !pathRead.value.trim()) return null

  const contentKey = raw.search(/"content"\s*:/)
  if (contentKey < 0) return null
  const contentRead = readJsonStringValue(raw, contentKey)
  if (!contentRead) return null

  // Un fragment minuscule n est pas un fichier: mieux vaut laisser le retry.
  if (contentRead.value.trim().length < 40) return null

  const languageKey = raw.search(/"language"\s*:/)
  const languageRead = languageKey >= 0 ? readJsonStringValue(raw, languageKey) : null

  return {
    path: pathRead.value.trim(),
    ...(languageRead?.closed && languageRead.value.trim()
      ? { language: languageRead.value.trim() }
      : {}),
    content: contentRead.value,
    truncated: true,
  }
}
