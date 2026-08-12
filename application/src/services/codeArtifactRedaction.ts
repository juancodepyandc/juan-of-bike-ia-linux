// Caviardage des artefacts PUBLIES.
//
// Le hub et les viewers sont servis par le pont, donc joignables par le tunnel
// public. Ils embarquent le code source integral de chaque projet genere. Rien
// de sensible n y figure aujourd hui — je l ai verifie sur les sept projets —
// mais c est une propriete qu il faut TENIR, pas constater: il suffit qu un
// modele ecrive une cle en dur une seule fois pour qu elle parte sur une URL
// publique, et personne ne le saura.
//
// La regle est volontairement etroite: on ne caviarde qu une VALEUR litterale
// assignee a un nom de secret. Un champ de formulaire `type="password"`, un
// `process.env.API_KEY`, un `placeholder="votre cle"` sont du code legitime et
// doivent rester lisibles — caviarder a l aveugle rendrait le viewer inutile.

export type CodeRedactionHit = {
  file: string
  key: string
  preview: string
}

export type CodeRedactionResult<T> = {
  files: T[]
  hits: CodeRedactionHit[]
}

export const REDACTION_MARKER = '[valeur masquee par Aurora avant publication]'

const SECRET_KEY = String.raw`(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|secret[_-]?key|client[_-]?secret|private[_-]?key|password|passwd|secret|token|bearer)`

// `clef: "valeur"` ou `CLEF = 'valeur'` — la valeur seule est remplacee.
const ASSIGNMENT_RE = new RegExp(
  String.raw`(['"\`]?\b${SECRET_KEY}\b['"\`]?\s*[:=]\s*)(['"\`])([^'"\`\n]{8,})\2`,
  'gi',
)

// `KEY=valeur` d un fichier d environnement (sans guillemets).
const ENV_LINE_RE = new RegExp(String.raw`^(\s*(?:export\s+)?[A-Z0-9_]*${SECRET_KEY}[A-Z0-9_]*\s*=\s*)(\S{8,})$`, 'gim')

// Cles reconnaissables par leur FORME, quel que soit leur nom de variable.
const SHAPED_SECRET_RE = /\b(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{25,})\b/g
const PEM_RE = /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g

/** Une valeur qui n est manifestement pas un secret reel. */
function isPlaceholder(value: string): boolean {
  const normalized = value.trim().toLowerCase()
  if (normalized.length < 8) return true
  if (/^(process\.env|import\.meta\.env|\$\{|<%|\{\{)/.test(value.trim())) return true
  return /^(your|votre|my|ma|xxx+|changeme|change-me|placeholder|example|exemple|todo|a-?remplir|dummy|test|fake|none|null|undefined|password|motdepasse)/.test(normalized)
}

function previewOf(value: string): string {
  const clean = value.trim()
  return clean.length <= 6 ? '***' : `${clean.slice(0, 3)}***${clean.slice(-2)}`
}

/**
 * Remplace les valeurs de secrets par un marqueur, en conservant la structure
 * du code (la cle reste visible: le lecteur sait qu il y a une variable a
 * renseigner). Retourne aussi la liste de ce qui a ete masque, pour que le
 * livrable puisse le DIRE au lieu de le cacher.
 */
export function redactSecretsForPublication<T extends { name: string; content: string }>(
  files: readonly T[],
): CodeRedactionResult<T> {
  const hits: CodeRedactionHit[] = []

  const redacted = files.map((file) => {
    let content = file.content
    if (!content) return file

    content = content.replace(ASSIGNMENT_RE, (match, head: string, quote: string, value: string) => {
      if (isPlaceholder(value)) return match
      const key = head.replace(/['"`\s:=]/g, '')
      hits.push({ file: file.name, key, preview: previewOf(value) })
      return `${head}${quote}${REDACTION_MARKER}${quote}`
    })

    content = content.replace(ENV_LINE_RE, (match, head: string, value: string) => {
      if (isPlaceholder(value)) return match
      hits.push({ file: file.name, key: head.replace(/[\s=]|export/g, ''), preview: previewOf(value) })
      return `${head}${REDACTION_MARKER}`
    })

    content = content.replace(SHAPED_SECRET_RE, (match) => {
      hits.push({ file: file.name, key: 'cle reconnue a sa forme', preview: previewOf(match) })
      return REDACTION_MARKER
    })

    content = content.replace(PEM_RE, () => {
      hits.push({ file: file.name, key: 'cle privee PEM', preview: '***' })
      return REDACTION_MARKER
    })

    return content === file.content ? file : { ...file, content }
  })

  return { files: redacted, hits }
}
