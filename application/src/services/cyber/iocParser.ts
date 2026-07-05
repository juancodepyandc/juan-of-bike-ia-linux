// IOC parser — extrait les Indicators of Compromise d'un texte (rapport
// incident, mail, log) : IPs, domaines, URLs, hashes, CVE, ATT&CK techniques.
//
// Pédagogie : enseigne à un analyste SOC junior à parcourir un blob de texte
// et à en sortir les artefacts actionnables.

export type IocKind = 'ipv4' | 'ipv6' | 'domain' | 'url' | 'email' | 'md5' | 'sha1' | 'sha256' | 'cve' | 'mitre' | 'btc'

export type Ioc = {
  kind: IocKind
  value: string
  /** Position de début dans le texte source (pour mise en évidence). */
  start: number
  end: number
  /** Tags additionnels (eg. private/public IP, suspicious TLD). */
  tags: string[]
}

const RE_IPV4 = /\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}\b/g
const RE_IPV6 = /\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b/g
// Domaine : 1 ou plusieurs labels + TLD ≥2 lettres. Exclu les noms purement numériques.
const RE_DOMAIN = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b/gi
const RE_URL = /\bhttps?:\/\/[^\s<>"']+/gi
const RE_EMAIL = /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/g
const RE_MD5 = /\b[a-fA-F0-9]{32}\b/g
const RE_SHA1 = /\b[a-fA-F0-9]{40}\b/g
const RE_SHA256 = /\b[a-fA-F0-9]{64}\b/g
const RE_CVE = /\bCVE-\d{4}-\d{4,7}\b/gi
const RE_MITRE = /\bT\d{4}(?:\.\d{3})?\b/g
const RE_BTC = /\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b/g

const SUSPICIOUS_TLD = new Set([
  'tk', 'ml', 'ga', 'cf', 'gq', 'xyz', 'top', 'pw', 'work', 'click',
  'support', 'rest', 'fit', 'live', 'world',
])

function isPrivateIp(ip: string): boolean {
  const parts = ip.split('.').map((s) => parseInt(s, 10))
  if (parts.length !== 4) return false
  if (parts[0] === 10) return true
  if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true
  if (parts[0] === 192 && parts[1] === 168) return true
  if (parts[0] === 127) return true
  if (parts[0] === 169 && parts[1] === 254) return true
  return false
}

function isReservedIp(ip: string): boolean {
  const parts = ip.split('.').map((s) => parseInt(s, 10))
  if (parts.length !== 4) return false
  if (parts[0] === 0) return true
  if (parts[0] === 255 && parts[1] === 255 && parts[2] === 255 && parts[3] === 255) return true
  if (parts[0] >= 224) return true // multicast/reserved
  return false
}

function collect(re: RegExp, kind: IocKind, source: string, out: Ioc[], tagger?: (val: string) => string[]) {
  let m: RegExpExecArray | null
  re.lastIndex = 0
  const seen = new Set<string>()
  while ((m = re.exec(source)) !== null) {
    const val = m[0]
    if (seen.has(val)) continue
    seen.add(val)
    out.push({
      kind,
      value: val,
      start: m.index,
      end: m.index + val.length,
      tags: tagger ? tagger(val) : [],
    })
  }
}

/**
 * Parse complet : extrait tous les IOCs d'un texte.
 */
export function parseIocs(source: string): Ioc[] {
  if (!source) return []
  const out: Ioc[] = []

  // Hashes (par longueur DESC pour éviter qu'un SHA-1 soit aussi capturé comme MD5).
  collect(RE_SHA256, 'sha256', source, out)
  collect(RE_SHA1, 'sha1', source, out)
  collect(RE_MD5, 'md5', source, out, (val) => {
    // Si déjà capturé comme SHA-1/SHA-256, skip (32 hex chars peut être prefix).
    // Mais notre regex \b ... \b évite déjà ça si le mot est strict 32 chars.
    return [val.toLowerCase() === val ? 'lowercase' : 'mixed-case']
  })

  // CVE / MITRE.
  collect(RE_CVE, 'cve', source, out, (val) => {
    const year = parseInt(val.slice(4, 8), 10)
    return year >= new Date().getFullYear() - 1 ? ['recent'] : []
  })
  collect(RE_MITRE, 'mitre', source, out)

  // Réseau.
  collect(RE_URL, 'url', source, out, (val) => {
    const tags: string[] = []
    try {
      const u = new URL(val)
      const host = u.hostname
      const tld = host.split('.').pop()?.toLowerCase()
      if (tld && SUSPICIOUS_TLD.has(tld)) tags.push(`tld-suspect:${tld}`)
      if (u.protocol === 'http:') tags.push('http-cleartext')
      if (/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/.test(host)) tags.push('ip-as-host')
      if (u.username || u.password) tags.push('userinfo')
    } catch { /* skip */ }
    return tags
  })
  collect(RE_EMAIL, 'email', source, out)
  collect(RE_IPV4, 'ipv4', source, out, (val) => {
    const tags: string[] = []
    if (isPrivateIp(val)) tags.push('private')
    else if (isReservedIp(val)) tags.push('reserved')
    else tags.push('public')
    return tags
  })
  collect(RE_IPV6, 'ipv6', source, out)
  // Domaines : APRÈS URL+email pour ne pas re-capturer les hosts. Mais notre regex
  // s'applique sur le texte brut donc va catcher les domaines déjà dans des URLs.
  // On filtre les domaines qui sont des subdomaines d'une URL déjà capturée.
  const urlHosts = new Set<string>()
  for (const o of out) {
    if (o.kind === 'url') {
      try { urlHosts.add(new URL(o.value).hostname) } catch { /* skip */ }
    }
  }
  collect(RE_DOMAIN, 'domain', source, out, (val) => {
    const tld = val.split('.').pop()?.toLowerCase()
    const tags: string[] = []
    if (tld && SUSPICIOUS_TLD.has(tld)) tags.push(`tld-suspect:${tld}`)
    return tags
  })
  // Filtre les domaines doublons URL hosts.
  const filtered = out.filter((o) => !(o.kind === 'domain' && urlHosts.has(o.value)))

  // BTC addresses.
  collect(RE_BTC, 'btc', source, filtered)

  // Tri par position.
  filtered.sort((a, b) => a.start - b.start)
  return filtered
}

/**
 * Stat par kind.
 */
export function summariseIocs(iocs: Ioc[]): Record<IocKind, number> {
  const out = {} as Record<IocKind, number>
  for (const i of iocs) {
    out[i.kind] = (out[i.kind] || 0) + 1
  }
  return out
}
