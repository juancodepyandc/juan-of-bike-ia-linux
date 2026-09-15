/**
 * entDocParser — extraction texte + LLM structuration depuis cours/exos
 * harvested via Aurora-Connect (PDF, DOCX, HTML).
 *
 * v82jh Pass 4/9 — Phase 2 P2.3 parsing.
 *
 * Pipeline :
 *   1. extractTextFromBlob(blob, mime) → string brut
 *      - PDF via pdfjs-dist (déjà bundlé)
 *      - DOCX via mammoth (déjà bundlé)
 *      - HTML / TXT direct decode
 *   2. classifyDocument(text, hint?) → { kind, subject, chapter, level }
 *      via LLM Ollama mainModel structured JSON
 *   3. summarizeDocument(text, kind) → { abstract, keyPoints, exos[] }
 *      via LLM ; permet d'inspirer parcours révision (Pass 8)
 *
 * Le content-script Aurora-Connect télécharge les pièces jointes via
 * fetch(blob URL) authenticated puis POST le blob ici via uploadDoc().
 */
import { ollamaChat } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'

export type DocKind = 'cours' | 'exo' | 'devoir' | 'corrige' | 'fiche-revision' | 'autre'
export type DocLevel = '6e' | '5e' | '4e' | '3e' | '2nde' | '1ere' | 'Tle' | 'inconnu'

export type DocStructured = {
  kind: DocKind
  subject?: string         // "Maths", "Physique-Chimie", ...
  chapter?: string         // "Suites numériques"
  level?: DocLevel
  /** Concepts clés détectés (3-7). */
  keyPoints?: string[]
  /** Si exo détecté, liste des questions ou consignes (1-10). */
  exercises?: string[]
  /** Synthèse en 2-3 phrases pour révision rapide. */
  abstract?: string
}

const SYSTEM_CLASSIFY = `Tu es un classifieur académique français. Tu reçois le texte d'un document scolaire récupéré depuis l'ENT d'un élève (Pronote/ÉcoleDirecte/etc.). Réponds STRICTEMENT en JSON valide avec ces champs :
{
  "kind": "cours" | "exo" | "devoir" | "corrige" | "fiche-revision" | "autre",
  "subject": "Maths"|"Physique-Chimie"|"SVT"|"Histoire-Géo"|"Français"|"Anglais"|"Espagnol"|"Allemand"|"Philosophie"|"NSI"|"SES"|"EMC"|"EPS"|"Arts"|null,
  "chapter": "string court ou null",
  "level": "6e"|"5e"|"4e"|"3e"|"2nde"|"1ere"|"Tle"|"inconnu",
  "keyPoints": ["3 à 7 concepts clés"],
  "exercises": ["consignes des exos si applicable, sinon []"],
  "abstract": "2-3 phrases de synthèse pour révision"
}
Pas de markdown fence, pas de prose, JSON pur.`

/** Extrait le texte d'un blob PDF/DOCX/TXT/HTML. */
export async function extractTextFromBlob(blob: Blob, mime?: string): Promise<string> {
  const t = (mime || blob.type || '').toLowerCase()
  if (t.includes('pdf')) {
    const pdf = await import('pdfjs-dist')
    // pdfjs-dist en mode browser nécessite un worker. Essai d'utiliser le
    // worker bundled, fallback CDN si non disponible.
    try {
      // Use the bundled fake worker (works without network)
      pdf.GlobalWorkerOptions.workerSrc = ''
    } catch { /* ignore */ }
    const buf = await blob.arrayBuffer()
    const doc = await pdf.getDocument({ data: buf }).promise
    const pages: string[] = []
    for (let i = 1; i <= Math.min(doc.numPages, 50); i++) {
      const page = await doc.getPage(i)
      const content = await page.getTextContent()
      const text = content.items
        .map((item) => 'str' in item ? (item as { str: string }).str : '')
        .join(' ')
      pages.push(text)
    }
    return pages.join('\n\n').slice(0, 50_000)
  }
  if (t.includes('word') || t.includes('docx') || t.includes('officedocument')) {
    const mammoth = await import('mammoth')
    const buf = await blob.arrayBuffer()
    const result = await mammoth.extractRawText({ arrayBuffer: buf })
    return (result.value || '').slice(0, 50_000)
  }
  if (t.includes('html')) {
    const text = await blob.text()
    // Simple HTML strip
    return text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 50_000)
  }
  // Default text/plain
  const text = await blob.text()
  return text.slice(0, 50_000)
}

/** Tente de classifier un document via Ollama. Retourne null si échec parsing. */
export async function classifyDocument(text: string, hint?: { subject?: string; filename?: string }): Promise<DocStructured | null> {
  const sample = text.slice(0, 8_000)  // garder context budget LLM raisonnable
  const userPrompt = [
    hint?.filename ? `Fichier source : ${hint.filename}` : '',
    hint?.subject ? `Matière connue (à confirmer ou corriger) : ${hint.subject}` : '',
    '---',
    sample,
  ].filter(Boolean).join('\n')
  try {
    const model = useAppStore.getState().mainModel
    const result = await ollamaChat(
      model,
      [
        { role: 'system', content: SYSTEM_CLASSIFY },
        { role: 'user', content: userPrompt },
      ],
      0.2,
    ) as { message?: { content?: string } } | null
    const response = result?.message?.content
    if (!response) return null
    // Cherche JSON dans la réponse (LLM peut ajouter du texte malgré la consigne)
    const match = response.match(/\{[\s\S]*\}/)
    if (!match) return null
    const json = JSON.parse(match[0]) as Record<string, unknown>
    return {
      kind: typeof json.kind === 'string' ? json.kind as DocKind : 'autre',
      subject: typeof json.subject === 'string' ? json.subject : undefined,
      chapter: typeof json.chapter === 'string' ? json.chapter : undefined,
      level: typeof json.level === 'string' ? json.level as DocLevel : 'inconnu',
      keyPoints: Array.isArray(json.keyPoints) ? json.keyPoints.filter((k): k is string => typeof k === 'string').slice(0, 7) : [],
      exercises: Array.isArray(json.exercises) ? json.exercises.filter((e): e is string => typeof e === 'string').slice(0, 10) : [],
      abstract: typeof json.abstract === 'string' ? json.abstract : undefined,
    }
  } catch {
    return null
  }
}

/** Pipeline complet : blob → texte → classification structurée. */
export async function parseAndClassify(
  blob: Blob,
  hint?: { mime?: string; subject?: string; filename?: string },
): Promise<{ text: string; structured: DocStructured | null }> {
  const text = await extractTextFromBlob(blob, hint?.mime)
  if (text.length < 50) {
    // Document quasi-vide, pas la peine de spend LLM tokens
    return { text, structured: null }
  }
  const structured = await classifyDocument(text, hint)
  return { text, structured }
}
