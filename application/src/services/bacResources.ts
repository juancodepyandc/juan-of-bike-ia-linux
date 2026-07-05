/**
 * Front-end wrapper for bac_resources.py — fetches real BAC exam subjects
 * from ecebac.fr + a catalog of trusted French education sites.
 *
 * The Academy generation flow calls `findRelevantSubjects(topic)` which
 * inspects the user's category / subcategory / topic hint, picks the right
 * filière + matière, and returns a list of real past-exam subjects the AI
 * can study before generating a new exercise.
 */
import { runPythonScript } from '../hooks/useTauri'

export interface BacSubject {
  id: string
  title: string
  url: string
  source: string
  filiere?: string
  matiere?: string
  session?: number
}

export interface BacSubjectDetail {
  id: string
  url: string
  source: string
  title: string
  text: string
  files: string[]
}

export interface TrustedSite {
  name: string
  description: string
  root: string
  types: string[]
}

async function callPy<T>(args: string[]): Promise<T> {
  const res = await runPythonScript('python-services/bac_resources.py', args)
  const output = (res as { output?: string }).output ?? ''
  const jsonLine = output.split('\n').filter((l) => l.trim().startsWith('{')).pop()
  if (!jsonLine) throw new Error('bac_resources: no JSON returned')
  const data = JSON.parse(jsonLine)
  if (!data.ok) throw new Error(data.error || 'bac_resources failed')
  return data as T
}

export async function listBacSubjects(
  filiere: string,
  matiere: string,
  session = 2026,
): Promise<BacSubject[]> {
  const res = await callPy<{ ok: true; subjects: BacSubject[] }>([
    '--list', '--filiere', filiere, '--matiere', matiere, '--session', String(session),
  ])
  return res.subjects || []
}

export async function fetchBacSubject(subjectId: string): Promise<BacSubjectDetail> {
  const res = await callPy<{ ok: true; subject: BacSubjectDetail }>([
    '--subject', subjectId,
  ])
  return res.subject
}

export async function discoverBacResources(query: string): Promise<BacSubject[]> {
  const res = await callPy<{ ok: true; results: BacSubject[] }>([
    '--discover', query,
  ])
  return res.results || []
}

export async function getTrustedSites(): Promise<TrustedSite[]> {
  const res = await callPy<{ ok: true; sites: TrustedSite[] }>(['--catalog'])
  return res.sites
}

// ---------------------------------------------------------------------------
// Smart routing — match a free-text topic to a (filière, matière) pair so
// the AI can pull real exam subjects automatically. Heuristic only — safe
// fallback to discover() when nothing matches.
// ---------------------------------------------------------------------------

export interface RouteHit {
  filiere: string
  matiere: string
  reason: string
}

const ROUTING_TABLE: Array<{ keywords: RegExp; route: Omit<RouteHit, 'reason'>; reason: string }> = [
  { keywords: /\b(sti2d|systèmes d'information|sin)\b/i,  route: { filiere: 'sti2d', matiere: 'sin' },  reason: 'STI2D · Systèmes d\'Information et Numérique' },
  { keywords: /\b(architecture|constructions?)\b/i,        route: { filiere: 'sti2d', matiere: 'ac' },   reason: 'STI2D · Architecture & Construction' },
  { keywords: /\b(énergie|electrique|eee?)\b/i,            route: { filiere: 'sti2d', matiere: 'ee' },   reason: 'STI2D · Énergie & Environnement' },
  { keywords: /\b(itec|mécanique|matériaux|innovation technologique)\b/i, route: { filiere: 'sti2d', matiere: 'itec' }, reason: 'STI2D · ITEC' },
  { keywords: /\b(nsi|algorithme|programmation|python)\b/i, route: { filiere: 'gen',   matiere: 'nsi' },  reason: 'Général · NSI' },
  { keywords: /\b(physique[ -]chimie|mécanique classique|thermo|ondes)\b/i, route: { filiere: 'gen', matiere: 'pc' }, reason: 'Général · PC (ECE)' },
  { keywords: /\b(svt|biologie|géologie|écologie)\b/i,     route: { filiere: 'gen',   matiere: 'svt' },  reason: 'Général · SVT (ECE)' },
]

export function routeToBac(topic: string): RouteHit | null {
  for (const r of ROUTING_TABLE) {
    if (r.keywords.test(topic)) {
      return { ...r.route, reason: r.reason }
    }
  }
  return null
}

/**
 * Produce a ready-to-inject prompt block that lists real exam subjects for a
 * topic. Returns null when we couldn't find anything worth enriching.
 */
export async function buildBacEnrichment(topic: string, maxSubjects = 3): Promise<string | null> {
  const route = routeToBac(topic)
  if (!route) return null
  try {
    const subjects = await listBacSubjects(route.filiere, route.matiere)
    if (subjects.length === 0) return null
    const picks = subjects.slice(0, maxSubjects)
    const lines = [
      '',
      '--- VRAIS SUJETS D\'EXAMEN OFFICIELS (pour calibrer le niveau/format) ---',
      `Source : ecebac.fr · ${route.reason} · session 2026`,
      ...picks.map((s) => `  • ${s.title} (${s.source}/${s.id})`),
      'Inspire-toi du FORMAT, de la PROGRESSION et du NIVEAU de ces sujets pour calibrer ton exercice.',
      '--- FIN DES SUJETS ---',
      '',
    ]
    return lines.join('\n')
  } catch {
    return null
  }
}
