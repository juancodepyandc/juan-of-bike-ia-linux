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
  const chunks = [STRUCTURED_PROJECT_EMISSION_VERSION]

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
  let cursor = offset
  if (stream.startsWith('\r\n', cursor) && stream.startsWith(END_MARKER, cursor + 2)) {
    cursor += 2
  } else if (stream[cursor] === '\n' && stream.startsWith(END_MARKER, cursor + 1)) {
    cursor += 1
  }

  if (!stream.startsWith(END_MARKER, cursor)) return null
  cursor += END_MARKER.length
  return skipLineBreak(stream, cursor)
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
  const markerIndex = stream.indexOf(END_MARKER, contentStart)
  if (markerIndex < 0) return null
  const nextHeader = stream.indexOf(FILE_PREFIX, contentStart)
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
    nextCursor: skipLineBreak(stream, markerIndex + END_MARKER.length),
  }
}

export function isStructuredProjectEmission(stream: string) {
  return stream.includes(FILE_PREFIX) && stream.includes(STRUCTURED_PROJECT_EMISSION_VERSION)
}

export function parseProjectTreeEmission(stream: string): StructuredEmissionParseResult {
  const issues: StructuredEmissionIssue[] = []
  const files: ProjectTreeInputFile[] = []
  let cursor = 0

  while (cursor < stream.length) {
    const fileStart = stream.indexOf(FILE_PREFIX, cursor)
    if (fileStart < 0) break

    const metadataStart = fileStart + FILE_PREFIX.length
    const metadataEnd = stream.indexOf(TAG_CLOSE, metadataStart)
    if (metadataEnd < 0) {
      pushIssue(issues, 'malformed_header', fileStart, 'Balise de fichier non fermee.')
      break
    }

    const metadata = parseMetadata(stream.slice(metadataStart, metadataEnd).trim(), metadataStart, issues)
    const contentStart = skipLineBreak(stream, metadataEnd + TAG_CLOSE.length)
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
  return [
    'FORMAT STRUCTURE OBLIGATOIRE:',
    `Commence par ${STRUCTURED_PROJECT_EMISSION_VERSION}.`,
    `Pour chaque fichier: ${FILE_PREFIX}{"path":"src/App.tsx","length":123,"encoding":"utf8","language":"tsx"}${TAG_CLOSE}`,
    'Ecris ensuite exactement length caracteres de contenu, puis le marqueur de fin.',
    `Marqueur de fin: ${END_MARKER}`,
    'N utilise pas de fences markdown pour delimiter les fichiers.',
    'Les fichiers binaires doivent etre emis en base64 avec encoding="base64".',
  ].join('\n')
}
