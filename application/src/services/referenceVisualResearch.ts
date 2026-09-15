import { getWorkspacePath, ollamaChat, runPythonScript } from '../hooks/useTauri.ts'

export type ReferenceVisualCandidate = {
  title: string
  imageUrl: string
  pageUrl: string
  width: number
  height: number
  query: string
}

export type ReferenceVisualSelection = ReferenceVisualCandidate & {
  blob: Blob
  score: number
  notes: string
}

export type ReferenceSearchProfile = {
  subjectLabel: string
  requiredElements: string[]
  forbiddenElements: string[]
  preferIsolatedSubject: boolean
  allowAdditionalSubjects: boolean
  strictIdentity: boolean
  identityTerms?: string[]
  forbiddenPageTerms?: string[]
  requiredPageTerms?: string[]
  preferredDomains?: string[]
  blockedDomains?: string[]
  minimumScore?: number
  viewLabel?: string
  verificationChecks?: string[]
  lightingRequirements?: string[]
  allowMirroredEquivalent?: boolean
}

export type ReferenceVisualAssessment = {
  usable: boolean
  score: number
  pixelated: boolean
  cluttered: boolean
  exactEnough: boolean
  wrongSubject?: boolean
  notes: string
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function shorten(text: string, limit = 180) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= limit) return normalized
  return `${normalized.slice(0, limit)}...`
}

function extractJson<T>(text: string): T | null {
  const match = text.match(/\{[\s\S]*\}/)
  if (!match) return null

  try {
    return JSON.parse(match[0]) as T
  } catch {
    return null
  }
}

function bytesToBase64(bytes: Uint8Array) {
  const chunkSize = 0x8000
  let binary = ''

  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize))
  }

  return btoa(binary)
}

function base64ToBytes(base64: string) {
  const binary = atob(base64)
  const output = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index)
  }
  return output
}

const WIKIPEDIA_LANGUAGES = ['fr', 'en'] as const

async function blobToBase64(blob: Blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  return bytesToBase64(bytes)
}

async function searchWebVisuals(query: string) {
  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/reference_visual_search.py`, ['--query', shorten(query, 160), '--limit', '8'])
    const parsed = extractJson<{ ok?: boolean; candidates?: ReferenceVisualCandidate[] }>(output)
    if (!parsed?.ok || !Array.isArray(parsed.candidates)) return []
    return parsed.candidates
      .filter((candidate) => candidate?.imageUrl && candidate?.pageUrl)
      .map((candidate) => ({
        ...candidate,
        width: Number(candidate.width || 0),
        height: Number(candidate.height || 0),
        query,
      }))
  } catch {
    return []
  }
}

async function downloadCandidateBlob(url: string) {
  try {
    const imageResponse = await fetch(url, { signal: AbortSignal.timeout(6000) })
    if (imageResponse.ok) {
      return await imageResponse.blob()
    }
  } catch {}

  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/reference_visual_search.py`, ['--download-url', url])
    const parsed = extractJson<{ ok?: boolean; base64?: string; contentType?: string }>(output)
    if (!parsed?.ok || !parsed.base64) return null
    return new Blob([base64ToBytes(parsed.base64)], { type: parsed.contentType || 'application/octet-stream' })
  } catch {
    return null
  }
}

async function searchCommons(query: string) {
  try {
    const url = new URL('https://commons.wikimedia.org/w/api.php')
    url.searchParams.set('action', 'query')
    url.searchParams.set('format', 'json')
    url.searchParams.set('origin', '*')
    url.searchParams.set('generator', 'search')
    url.searchParams.set('gsrnamespace', '6')
    url.searchParams.set('gsrlimit', '6')
    url.searchParams.set('gsrsearch', shorten(query, 120))
    url.searchParams.set('prop', 'imageinfo')
    url.searchParams.set('iiprop', 'url|size')
    url.searchParams.set('iiurlwidth', '1024')

    const response = await fetch(url.toString(), { signal: AbortSignal.timeout(4500) })
    if (!response.ok) return []

    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return []
    const payload = JSON.parse(text) as {
      query?: {
        pages?: Record<string, {
          title: string
          imageinfo?: Array<{
            url?: string
            thumburl?: string
            descriptionurl?: string
            width?: number
            height?: number
            thumbwidth?: number
            thumbheight?: number
          }>
        }>
      }
    }

    return Object.values(payload.query?.pages || {})
      .map((page) => {
        const info = page.imageinfo?.[0]
        if (!info?.url || !info.descriptionurl) return null
        return {
          title: page.title,
          imageUrl: info.thumburl || info.url,
          pageUrl: info.descriptionurl,
          width: info.thumbwidth || info.width || 0,
          height: info.thumbheight || info.height || 0,
          query,
        } satisfies ReferenceVisualCandidate
      })
      .filter((candidate): candidate is ReferenceVisualCandidate => Boolean(candidate))
      .filter((candidate) => candidate.width >= 320 && candidate.height >= 320)
  } catch {
    return []
  }
}

async function searchWikipediaVisuals(query: string) {
  const candidates: ReferenceVisualCandidate[] = []
  const seen = new Set<string>()

  for (const wiki of WIKIPEDIA_LANGUAGES) {
    try {
      const searchUrl = new URL(`https://${wiki}.wikipedia.org/w/api.php`)
      searchUrl.searchParams.set('action', 'query')
      searchUrl.searchParams.set('format', 'json')
      searchUrl.searchParams.set('origin', '*')
      searchUrl.searchParams.set('list', 'search')
      searchUrl.searchParams.set('utf8', '1')
      searchUrl.searchParams.set('srlimit', '4')
      searchUrl.searchParams.set('srsearch', shorten(query, 120))

      const searchResponse = await fetch(searchUrl.toString(), { signal: AbortSignal.timeout(4500) })
      if (!searchResponse.ok) {
        continue
      }

      const searchText = await searchResponse.text()
      if (!searchText || searchText.trimStart().startsWith('<')) continue
      const searchPayload = JSON.parse(searchText) as {
        query?: {
          search?: Array<{
            title: string
          }>
        }
      }

      for (const result of searchPayload.query?.search || []) {
        try {
          const summaryResponse = await fetch(
            `https://${wiki}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(result.title)}`,
            { signal: AbortSignal.timeout(4500) },
          )
          if (!summaryResponse.ok) {
            continue
          }

          const summaryText = await summaryResponse.text()
          if (!summaryText || summaryText.trimStart().startsWith('<')) continue
          const summary = JSON.parse(summaryText) as {
            title?: string
            thumbnail?: {
              source?: string
              width?: number
              height?: number
            }
            originalimage?: {
              source?: string
              width?: number
              height?: number
            }
            content_urls?: {
              desktop?: {
                page?: string
              }
            }
          }

          const imageUrl = summary.originalimage?.source || summary.thumbnail?.source
          const pageUrl = summary.content_urls?.desktop?.page
          const width = summary.originalimage?.width || summary.thumbnail?.width || 0
          const height = summary.originalimage?.height || summary.thumbnail?.height || 0
          const dedupeKey = `${pageUrl || ''}::${imageUrl || ''}`

          if (!imageUrl || !pageUrl || width < 320 || height < 320 || seen.has(dedupeKey)) {
            continue
          }

          seen.add(dedupeKey)
          candidates.push({
            title: summary.title || result.title,
            imageUrl,
            pageUrl,
            width,
            height,
            query,
          })
        } catch {
          // Continue with the next page result.
        }
      }
    } catch {
      // Continue with the next wiki.
    }
  }

  return candidates
}

async function assessCandidate(
  prompt: string,
  model: string,
  candidate: ReferenceVisualCandidate,
  blob: Blob,
  profile?: ReferenceSearchProfile,
): Promise<ReferenceVisualAssessment | null> {
  try {
    const base64 = await blobToBase64(blob)
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          'You evaluate whether an image is a strong visual reference for a generation request.',
          'Return only valid JSON with this exact shape:',
          '{"usable":true,"score":0,"pixelated":false,"cluttered":false,"exactEnough":true,"wrongSubject":false,"notes":"..."}',
          'MOST CRITICAL CHECK: Is this image showing the CORRECT subject? If the user asks for a cable and the image shows a PC case, wrongSubject=true and score=0.',
          'If the user asks for a Strimer cable and the image shows a tower/case/motherboard, wrongSubject=true and score=0.',
          'If the user asks for a character and the image shows a completely different character, wrongSubject=true and score=0.',
          'wrongSubject=true immediately means usable=false and exactEnough=false regardless of image quality.',
          'Usable means the image is focused on the EXACT requested subject and can improve fidelity.',
          'Reject images that are too cluttered, too low-res, visibly pixelated, collages, memes, screenshots with UI, or clearly the wrong subject.',
          'If strict identity is requested, reject images showing another character, another product variant, or another main subject even if the art style looks similar.',
          'If extra subjects are not allowed, reject group shots, mascot companions, host devices, full environments, or parasite objects that dominate the requested element.',
          'If the request is about anime or an existing fictional character, clean official art or clean illustration is acceptable.',
          'For character references, reject merchandise or product photos where the character is printed on a watch, shirt, poster, box, packaging, ad, or collectible packaging instead of being the visual subject itself.',
          'If the request is about a product, component, cable or mechanism, prefer focused photos or clean technical renders with minimal parasite elements.',
          'A cable is NOT a case. A GPU is NOT a motherboard. A fan is NOT a cooler. An SSD is NOT a RAM stick. Check the actual product type matches.',
          'If a specific view is requested, reject images that clearly show the wrong side unless mirrored equivalence is explicitly allowed.',
          'Use verification checks to confirm connectors, hinges, shafts, LED guides, or other functional details when they are requested.',
          'Score 0-100 for usefulness as a reference seed. Score 0 for wrong subject.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `User request: ${prompt}`,
          profile?.subjectLabel ? `Exact subject to match: ${profile.subjectLabel}` : '',
          profile?.requiredElements.length ? `Required visible elements: ${profile.requiredElements.join(', ')}` : '',
          profile?.forbiddenElements.length ? `Forbidden or parasite elements: ${profile.forbiddenElements.join(', ')}` : '',
          profile ? `Prefer isolated subject: ${profile.preferIsolatedSubject ? 'yes' : 'no'}` : '',
          profile ? `Allow additional subjects: ${profile.allowAdditionalSubjects ? 'yes' : 'no'}` : '',
          profile ? `Strict identity required: ${profile.strictIdentity ? 'yes' : 'no'}` : '',
          profile?.viewLabel ? `Requested view: ${profile.viewLabel}` : '',
          profile?.allowMirroredEquivalent !== undefined ? `Mirrored equivalent allowed: ${profile.allowMirroredEquivalent ? 'yes' : 'no'}` : '',
          profile?.verificationChecks?.length ? `Functional verification checks: ${profile.verificationChecks.join(', ')}` : '',
          profile?.lightingRequirements?.length ? `Lighting or emissive requirements: ${profile.lightingRequirements.join(', ')}` : '',
          `Candidate title: ${candidate.title}`,
          `Candidate source page: ${candidate.pageUrl}`,
        ].join('\n'),
        images: [base64],
      },
    ], 0.05)

    return extractJson<ReferenceVisualAssessment>(response?.message?.content || '')
  } catch {
    return null
  }
}

function normalizedTokens(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length >= 3)
}

function extractHostname(value: string) {
  try {
    return new URL(value).hostname.toLowerCase()
  } catch {
    return ''
  }
}

function hostMatchesDomain(hostname: string, domain: string) {
  const normalizedDomain = domain.toLowerCase().replace(/^www\./, '')
  const normalizedHost = hostname.toLowerCase().replace(/^www\./, '')
  return normalizedHost === normalizedDomain || normalizedHost.endsWith(`.${normalizedDomain}`)
}

function scoreCandidateSource(candidate: ReferenceVisualCandidate, profile?: ReferenceSearchProfile) {
  const searchableText = `${candidate.title} ${candidate.pageUrl}`.toLowerCase()
  const hostname = extractHostname(candidate.pageUrl)
  let score = 0

  if (profile?.preferredDomains?.some((domain) => hostMatchesDomain(hostname, domain))) {
    score += 45
  }
  if (profile?.blockedDomains?.some((domain) => hostMatchesDomain(hostname, domain))) {
    score -= 80
  }
  if (profile?.requiredPageTerms?.length) {
    const requiredMatches = profile.requiredPageTerms.filter((term) => searchableText.includes(term.toLowerCase())).length
    score += requiredMatches * 8
    if (requiredMatches === 0 && profile.strictIdentity) {
      score -= 35
    }
  }
  if (profile?.forbiddenPageTerms?.some((term) => searchableText.includes(term.toLowerCase()))) {
    score -= 60
  }
  if (candidate.width >= 900 || candidate.height >= 900) {
    score += 4
  }

  return score
}

function candidateLooksTitleCompatible(candidate: ReferenceVisualCandidate, profile?: ReferenceSearchProfile) {
  if (!profile?.subjectLabel?.trim()) return true

  const searchableText = `${candidate.title} ${candidate.pageUrl}`.toLowerCase()
  const hostname = extractHostname(candidate.pageUrl)
  if (profile.blockedDomains?.some((domain) => hostMatchesDomain(hostname, domain))) {
    return false
  }
  if (profile.forbiddenPageTerms?.some((term) => searchableText.includes(term.toLowerCase()))) {
    return false
  }
  if (
    profile.requiredPageTerms?.length
    && profile.strictIdentity
    && !profile.requiredPageTerms.some((term) => searchableText.includes(term.toLowerCase()))
  ) {
    return false
  }

  if (!profile.strictIdentity) return true

  const subjectTokens = (profile.identityTerms && profile.identityTerms.length > 0
    ? profile.identityTerms
    : normalizedTokens(profile.subjectLabel))
    .map((token) => token.toLowerCase())
  if (subjectTokens.length === 0) return true

  const titleTokens = new Set(normalizedTokens(searchableText))
  const overlap = subjectTokens.filter((token) => titleTokens.has(token)).length

  if (subjectTokens.length === 1) {
    return overlap >= 1
  }

  if (subjectTokens.length === 2) {
    return overlap >= 2
  }

  return overlap >= Math.max(2, Math.ceil(subjectTokens.length * 0.6))
}

function candidateLooksStrongTextReference(candidate: ReferenceVisualCandidate, profile?: ReferenceSearchProfile) {
  if (!profile?.strictIdentity) return false
  const identityTerms = (profile.identityTerms && profile.identityTerms.length > 0
    ? profile.identityTerms
    : normalizedTokens(profile.subjectLabel || '')).map((token) => token.toLowerCase())
  const requiredPageTerms = (profile.requiredPageTerms || []).map((term) => term.toLowerCase())
  if (identityTerms.length === 0 || requiredPageTerms.length === 0) return false

  const title = candidate.title.toLowerCase()
  const pageUrl = candidate.pageUrl.toLowerCase()
  const imageUrl = candidate.imageUrl.toLowerCase()
  const searchableText = `${title} ${pageUrl} ${imageUrl}`
  if (!requiredPageTerms.some((term) => searchableText.includes(term))) return false
  return identityTerms.some((term) => imageUrl.includes(term) || title.includes(term))
}

export async function verifyGeneratedReferenceVisual({
  prompt,
  model,
  blob,
  profile,
  label = 'Generated reference image',
}: {
  prompt: string
  model: string
  blob: Blob
  profile?: ReferenceSearchProfile
  label?: string
}): Promise<ReferenceVisualAssessment | null> {
  return assessCandidate(prompt, model, {
    title: label,
    imageUrl: 'generated://reference-image',
    pageUrl: 'generated://reference-image',
    width: 0,
    height: 0,
    query: 'generated',
  }, blob, profile)
}

export async function findBestReferenceVisual({
  prompt,
  model,
  queries,
  profile,
}: {
  prompt: string
  model: string
  queries: string[]
  profile?: ReferenceSearchProfile
}): Promise<ReferenceVisualSelection | null> {
  const candidateQueries = uniqueStrings(queries.map((query) => shorten(query, 160))).slice(0, 3)
  let best: ReferenceVisualSelection | null = null
  const minimumScore = profile?.minimumScore ?? (profile?.strictIdentity ? 84 : 68)

  for (const query of candidateQueries) {
    const candidatePool = [
      ...(await searchWebVisuals(query)),
      ...(await searchWikipediaVisuals(query)),
      ...(await searchCommons(query)),
    ].sort((left, right) => scoreCandidateSource(right, profile) - scoreCandidateSource(left, profile))
    const seen = new Set<string>()

    for (const candidate of candidatePool.filter((entry) => {
      const key = `${entry.pageUrl}::${entry.imageUrl}`
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return candidateLooksTitleCompatible(entry, profile)
    }).slice(0, 10)) {
      try {
        const blob = await downloadCandidateBlob(candidate.imageUrl)
        if (!blob) continue
        const assessment = await assessCandidate(prompt, model, candidate, blob, profile)
        const strongTextReference = candidateLooksStrongTextReference(candidate, profile)
        if ((!assessment?.usable || !assessment.exactEnough || assessment.pixelated || assessment.cluttered || assessment.score < minimumScore) && !strongTextReference) {
          continue
        }

        const selection: ReferenceVisualSelection = {
          ...candidate,
          blob,
          score: assessment?.usable ? assessment.score : minimumScore,
          notes: assessment?.notes || 'Accepted by strict identity/context metadata fallback.',
        }

        if (!best || selection.score > best.score) {
          best = selection
        }
      } catch {
        // Continue with the next candidate.
      }
    }
  }

  return best && best.score >= minimumScore ? best : null
}

/**
 * Find multiple high-quality reference visuals (up to maxResults) for comprehensive
 * multi-angle coverage. Returns results sorted by score descending.
 * Used when building a reference pack with images from different angles.
 */
export async function findMultipleReferenceVisuals({
  prompt,
  model,
  queries,
  profile,
  maxResults = 4,
}: {
  prompt: string
  model: string
  queries: string[]
  profile?: ReferenceSearchProfile
  maxResults?: number
}): Promise<ReferenceVisualSelection[]> {
  const candidateQueries = uniqueStrings(queries.map((query) => shorten(query, 160))).slice(0, 4)
  const results: ReferenceVisualSelection[] = []
  const minimumScore = profile?.minimumScore ?? (profile?.strictIdentity ? 84 : 68)
  const globalSeen = new Set<string>()

  for (const query of candidateQueries) {
    if (results.length >= maxResults) break

    const candidatePool = [
      ...(await searchWebVisuals(query)),
      ...(await searchWikipediaVisuals(query)),
      ...(await searchCommons(query)),
    ].sort((left, right) => scoreCandidateSource(right, profile) - scoreCandidateSource(left, profile))

    for (const candidate of candidatePool.filter((entry) => {
      const key = `${entry.pageUrl}::${entry.imageUrl}`
      if (globalSeen.has(key)) return false
      globalSeen.add(key)
      return candidateLooksTitleCompatible(entry, profile)
    }).slice(0, 12)) {
      if (results.length >= maxResults) break
      try {
        const blob = await downloadCandidateBlob(candidate.imageUrl)
        if (!blob) continue
        const assessment = await assessCandidate(prompt, model, candidate, blob, profile)
        const strongTextReference = candidateLooksStrongTextReference(candidate, profile)
        if ((!assessment?.usable || !assessment.exactEnough || assessment.pixelated || assessment.cluttered || assessment.score < minimumScore) && !strongTextReference) {
          continue
        }

        results.push({
          ...candidate,
          blob,
          score: assessment?.usable ? assessment.score : minimumScore,
          notes: assessment?.notes || 'Accepted by strict identity/context metadata fallback.',
        })
      } catch {
        // Continue with the next candidate.
      }
    }
  }

  return results.sort((a, b) => b.score - a.score)
}
