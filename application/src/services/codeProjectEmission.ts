// ---------------------------------------------------------------------------
// Structured project emission protocol
// WS2 foundation: parse generated projects by declared content length instead
// of markdown fences or `--- FICHIER` separators.
// ---------------------------------------------------------------------------

import {
  buildProjectTree,
  type CodeProjectFileEncoding,
  type ProjectTree,
  type ProjectTreeInputFile,
} from './codeProjectTree.ts'

export const STRUCTURED_PROJECT_EMISSION_VERSION = 'AURORA_CODE_VFS/1'

const FILE_PREFIX = '<<<AURORA_FILE '
const TAG_CLOSE = '>>>'
const END_MARKER = '<<<AURORA_END>>>'
const END_TAG = 'AURORA_END'
/** En-tete de version tel qu il est desormais SERIALISE et DEMANDE au modele. */
export const STRUCTURED_PROJECT_EMISSION_HEADER = `<<<${STRUCTURED_PROJECT_EMISSION_VERSION}>>>`

// Run 1061, mesure sur le flux reel: le modele a emis les 14 fichiers du projet
// avec `AURORA_FILE {...}` NU (sans `<<<`/`>>>`), tout en encadrant la ligne de
// version et le marqueur de fin. Il n a pas desobei au hasard: la consigne
// donnait un en-tete de version NU et deux marqueurs ENCADRES — il a uniformise
// la seule maniere possible sans perdre d information. Le parseur, lui, exigeait
// la forme encadree au caractere pres: aucun fichier reconnu, et les 15 534
// octets du conteneur ont ete livres tels quels dans un fichier « main.js ».
//
// Deux corrections, pas une: la consigne devient symetrique (les trois marqueurs
// s ecrivent pareil) ET le parseur accepte les deux formes. Un protocole dont la
// seule forme valide est celle que le modele n ecrit pas n est pas un protocole,
// c est un piege.
//
// Forme nue: uniquement en debut de ligne, pour qu un `AURORA_FILE` cite dans du
// contenu ne puisse pas couper un fichier. Forme encadree: partout, comme avant.
const FILE_HEADER_RE = /(?:^[ \t]*AURORA_FILE[ \t]+|<<<AURORA_FILE[ \t]+)(?=\{)/gm
const END_MARKER_RE = /^[ \t]*(?:<<<AURORA_END>>>|AURORA_END)[ \t]*$/gm

type FileHeaderMatch = {
  /** Offset du debut de l en-tete (pour les diagnostics). */
  start: number
  /** Offset du premier caractere des metadonnees JSON. */
  metadataStart: number
  /** Offset de fin des metadonnees (exclu). */
  metadataEnd: number
  /** Offset du premier caractere du contenu du fichier. */
  contentStart: number
  /** L en-tete etait-il ferme par `>>>` ? (sinon: termine par la fin de ligne) */
  bracketed: boolean
}

/** Prochain en-tete de fichier, quelle que soit sa forme. */
function findFileHeader(stream: string, from: number): FileHeaderMatch | null {
  FILE_HEADER_RE.lastIndex = Math.max(0, from)
  const match = FILE_HEADER_RE.exec(stream)
  if (!match) return null

  const bracketed = match[0].includes('<<<')
  const metadataStart = match.index + match[0].length
  if (bracketed) {
    const metadataEnd = stream.indexOf(TAG_CLOSE, metadataStart)
    if (metadataEnd < 0) return { start: match.index, metadataStart, metadataEnd: -1, contentStart: -1, bracketed }
    return {
      start: match.index,
      metadataStart,
      metadataEnd,
      contentStart: skipLineBreak(stream, metadataEnd + TAG_CLOSE.length),
      bracketed,
    }
  }

  const lineEnd = stream.indexOf('\n', metadataStart)
  const metadataEnd = lineEnd < 0 ? stream.length : lineEnd
  return {
    start: match.index,
    metadataStart,
    metadataEnd,
    // `metadataEnd` pointe sur le `\n`; le `\r` eventuel est retire par le trim
    // des metadonnees. Le contenu commence apres ce saut de ligne.
    contentStart: skipLineBreak(stream, metadataEnd),
    bracketed,
  }
}

/** Offset du prochain en-tete de fichier, ou -1. */
function nextFileHeaderOffset(stream: string, from: number): number {
  return findFileHeader(stream, from)?.start ?? -1
}

/** Marqueur de fin (encadre ou nu) a cet offset exact, ou null. */
function matchEndMarkerAt(stream: string, offset: number): number | null {
  if (stream.startsWith(END_MARKER, offset)) return offset + END_MARKER.length
  if (stream.startsWith(END_TAG, offset)) {
    const after = stream[offset + END_TAG.length]
    if (after === undefined || after === '\n' || after === '\r') return offset + END_TAG.length
  }
  return null
}

export type StructuredEmissionIssueType =
  | 'malformed_header'
  | 'invalid_metadata'
  | 'invalid_length'
  | 'length_overflow'
  | 'missing_end_marker'
  // Non-fatal: la longueur declaree etait incoherente (typiquement UTF-16 vs
  // points de code) mais le fichier a ete recupere via le marqueur de fin
  // au lieu d etre avale silencieusement.
  | 'recovered_length_mismatch'

export type StructuredEmissionIssue = {
  type: StructuredEmissionIssueType
  offset: number
  message: string
}

export type StructuredEmissionParseResult = {
  tree: ProjectTree
  issues: StructuredEmissionIssue[]
}

type FileMetadata = {
  path: string
  length: number
  encoding?: CodeProjectFileEncoding
  language?: string
  mime?: string
}

function isProjectTree(input: ProjectTree | ProjectTreeInputFile[]): input is ProjectTree {
  return !Array.isArray(input) && Array.isArray(input.files) && Array.isArray(input.directories)
}

function serializeMetadata(file: ProjectTree['files'][number]) {
  const metadata: FileMetadata = {
    path: file.path,
    length: file.content.length,
    encoding: file.encoding,
  }
  if (file.language) metadata.language = file.language
  if (file.mime) metadata.mime = file.mime
  return JSON.stringify(metadata)
}

export function serializeProjectTreeEmission(input: ProjectTree | ProjectTreeInputFile[]) {
  const tree = isProjectTree(input) ? input : buildProjectTree(input)
  // Les TROIS marqueurs s ecrivent desormais pareil (`<<<...>>>`). C est ce que
  // le modele ecrit spontanement, et c est ce qui l empeche d « uniformiser » un
  // protocole asymetrique dans la mauvaise direction.
  const chunks = [STRUCTURED_PROJECT_EMISSION_HEADER]

  for (const file of tree.files) {
    chunks.push([
      `${FILE_PREFIX}${serializeMetadata(file)}${TAG_CLOSE}`,
      file.content,
      END_MARKER,
    ].join('\n'))
  }

  return `${chunks.join('\n')}\n`
}

function pushIssue(
  issues: StructuredEmissionIssue[],
  type: StructuredEmissionIssueType,
  offset: number,
  message: string,
) {
  issues.push({ type, offset, message })
}

function parseMetadata(raw: string, offset: number, issues: StructuredEmissionIssue[]) {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    pushIssue(issues, 'invalid_metadata', offset, 'Metadonnees JSON de fichier invalides.')
    return null
  }

  if (!parsed || typeof parsed !== 'object') {
    pushIssue(issues, 'invalid_metadata', offset, 'Metadonnees de fichier absentes ou non objet.')
    return null
  }

  const metadata = parsed as Partial<FileMetadata>
  if (typeof metadata.path !== 'string' || metadata.path.trim().length === 0) {
    pushIssue(issues, 'invalid_metadata', offset, 'Metadonnee path manquante ou vide.')
    return null
  }
  const length = metadata.length
  if (typeof length !== 'number' || !Number.isInteger(length) || length < 0) {
    pushIssue(issues, 'invalid_length', offset, 'Metadonnee length invalide.')
    return null
  }
  if (metadata.encoding && metadata.encoding !== 'utf8' && metadata.encoding !== 'base64') {
    pushIssue(issues, 'invalid_metadata', offset, 'Metadonnee encoding invalide.')
    return null
  }

  return {
    path: metadata.path,
    length,
    encoding: metadata.encoding,
    language: typeof metadata.language === 'string' ? metadata.language : undefined,
    mime: typeof metadata.mime === 'string' ? metadata.mime : undefined,
  } satisfies FileMetadata
}

function skipLineBreak(stream: string, offset: number) {
  if (stream.startsWith('\r\n', offset)) return offset + 2
  if (stream[offset] === '\n') return offset + 1
  return offset
}

function consumeEndMarker(stream: string, offset: number) {
  let end = matchEndMarkerAt(stream, offset)
  if (end === null) {
    // Le serialiseur insere un saut de ligne entre le contenu et le marqueur.
    const afterBreak = skipLineBreak(stream, offset)
    if (afterBreak !== offset) end = matchEndMarkerAt(stream, afterBreak)
  }
  if (end === null) return null
  return skipLineBreak(stream, end)
}

/**
 * Recovery: la longueur declaree est fausse mais le contenu reste delimite par
 * le marqueur de fin. On cherche le prochain END_MARKER a partir du debut du
 * contenu ; s il apparait AVANT le prochain en-tete de fichier, on recupere le
 * fichier avec la vraie frontiere plutot que de le laisser tomber en silence.
 * Retourne null si aucune recuperation sure n est possible (flux tronque, ou un
 * autre en-tete de fichier s intercale — on ne veut pas avaler le fichier suivant).
 */
function recoverFileToEndMarker(stream: string, contentStart: number) {
  END_MARKER_RE.lastIndex = contentStart
  const endMatch = END_MARKER_RE.exec(stream)
  if (!endMatch) return null
  const markerIndex = endMatch.index
  const markerLength = endMatch[0].length
  const nextHeader = nextFileHeaderOffset(stream, contentStart)
  if (nextHeader >= 0 && nextHeader < markerIndex) return null

  // Le serialiseur insere exactement un saut de ligne entre le contenu et le
  // marqueur (`content\nEND_MARKER`). On retire ce separateur de jointure.
  let contentEnd = markerIndex
  if (stream[contentEnd - 1] === '\n') {
    contentEnd -= 1
    if (stream[contentEnd - 1] === '\r') contentEnd -= 1
  }
  return {
    content: stream.slice(contentStart, contentEnd),
    nextCursor: skipLineBreak(stream, markerIndex + markerLength),
  }
}

export function isStructuredProjectEmission(stream: string) {
  return stream.includes(STRUCTURED_PROJECT_EMISSION_VERSION) && findFileHeader(stream, 0) !== null
}

export function parseProjectTreeEmission(stream: string): StructuredEmissionParseResult {
  const issues: StructuredEmissionIssue[] = []
  const files: ProjectTreeInputFile[] = []
  let cursor = 0

  while (cursor < stream.length) {
    const header = findFileHeader(stream, cursor)
    if (!header) break

    const { start: fileStart, metadataStart, metadataEnd, contentStart } = header
    if (metadataEnd < 0) {
      pushIssue(issues, 'malformed_header', fileStart, 'Balise de fichier non fermee.')
      break
    }

    const metadata = parseMetadata(stream.slice(metadataStart, metadataEnd).trim(), metadataStart, issues)
    if (!metadata) {
      cursor = contentStart
      continue
    }

    const contentEnd = contentStart + metadata.length
    if (contentEnd > stream.length) {
      // Longueur declaree > flux: tentative de recuperation via le marqueur de fin
      // (le flux peut avoir ete tronque ou la longueur surestimee).
      const recovered = recoverFileToEndMarker(stream, contentStart)
      if (recovered) {
        pushIssue(issues, 'recovered_length_mismatch', contentStart, 'Longueur declaree superieure au flux: fichier recupere via le marqueur de fin.')
        files.push({
          path: metadata.path,
          content: recovered.content,
          encoding: metadata.encoding,
          language: metadata.language,
          mime: metadata.mime,
        })
        cursor = recovered.nextCursor
        continue
      }
      pushIssue(issues, 'length_overflow', contentStart, 'La longueur declaree depasse la taille du flux.')
      break
    }

    const nextCursor = consumeEndMarker(stream, contentEnd)
    if (nextCursor === null) {
      // Le marqueur de fin n est pas a la longueur declaree (longueur mal comptee,
      // p.ex. UTF-16 vs points de code avec emojis/accents). On recupere le fichier
      // via le marqueur de fin reel au lieu de le laisser tomber silencieusement.
      const recovered = recoverFileToEndMarker(stream, contentStart)
      if (recovered) {
        pushIssue(issues, 'recovered_length_mismatch', contentStart, 'Longueur declaree incoherente: fichier recupere via le marqueur de fin.')
        files.push({
          path: metadata.path,
          content: recovered.content,
          encoding: metadata.encoding,
          language: metadata.language,
          mime: metadata.mime,
        })
        cursor = recovered.nextCursor
        continue
      }
      pushIssue(issues, 'missing_end_marker', contentEnd, 'Marqueur de fin absent a la longueur declaree.')
      cursor = contentEnd
      continue
    }

    files.push({
      path: metadata.path,
      content: stream.slice(contentStart, contentEnd),
      encoding: metadata.encoding,
      language: metadata.language,
      mime: metadata.mime,
    })
    cursor = nextCursor
  }

  return {
    tree: buildProjectTree(files),
    issues,
  }
}

export function buildStructuredEmissionInstructions() {
  // Consigne SYMETRIQUE: les trois marqueurs s ecrivent `<<<...>>>`. L ancienne
  // version melait un en-tete nu et deux marqueurs encadres; le run 1061 a montre
  // qu un modele uniformise ce genre d incoherence — et qu il le fait dans le
  // sens que le parseur ne lisait pas. Un exemple complet vaut mieux qu une
  // description: il ne laisse aucune place a l interpretation.
  const example = 'const A = 1\n'
  return [
    'FORMAT STRUCTURE OBLIGATOIRE:',
    `Commence par ${STRUCTURED_PROJECT_EMISSION_HEADER}`,
    `Pour chaque fichier: ${FILE_PREFIX}{"path":"src/App.tsx","length":123,"encoding":"utf8","language":"tsx"}${TAG_CLOSE}`,
    'Ecris ensuite exactement length caracteres de contenu, puis le marqueur de fin.',
    `Marqueur de fin: ${END_MARKER}`,
    'Les TROIS marqueurs sont encadres par <<< et >>>. N en ecris aucun sans ses chevrons.',
    '`length` est le nombre de caracteres du contenu REEL du fichier, jamais celui de l exemple.',
    'N utilise pas de fences markdown pour delimiter les fichiers.',
    'Les fichiers binaires doivent etre emis en base64 avec encoding="base64".',
    '',
    'EXEMPLE COMPLET (a reproduire au caractere pres):',
    STRUCTURED_PROJECT_EMISSION_HEADER,
    `${FILE_PREFIX}{"path":"src/a.ts","length":${example.length},"encoding":"utf8","language":"typescript"}${TAG_CLOSE}`,
    example.trimEnd(),
    END_MARKER,
  ].join('\n')
}
