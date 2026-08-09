// ---------------------------------------------------------------------------
// codeArchitecturePlanFallback — un architecte defaillant ne doit plus tuer le run.
//
// Panne observee en verification de bout en bout :
//
//   Plan d architecture inexploitable - generation bloquee
//     (architecture_plan_invalid:files_min_2)
//   Erreur fatale du pipeline: Echec du plan d architecture structure
//
// Le modele avait rendu, sur TOUS ses candidats, un JSON valide mais contenant
// moins de deux fichiers. `runPlanningPhase` levait alors, et `runFullPipeline`
// levait a son tour sur `isArchitecturePlanUsable`. Resultat : zero fichier
// livre, alors que l intention etait parfaitement connue.
//
// L ironie est que le repli existe DEJA un etage plus bas :
// `buildGenerationQueueWithFallback` sait deriver une file de fichiers depuis
// l intent seul. Il n etait simplement jamais atteint, parce que deux `throw`
// se declenchaient avant lui.
//
// Ce module supprime la cause plutot que le symptome : quand l architecte
// echoue, on SYNTHETISE un plan deterministe depuis l intent, valide au regard
// du meme schema, et le pipeline continue. Aucun appel modele supplementaire —
// une replanification couterait un chargement de modele que le budget VRAM de
// la machine ne supporte pas.
// ---------------------------------------------------------------------------

import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from './codeArchitecturePlan.ts'
import { defaultFilesForIntent } from './codeGenerationQueue.ts'
import { requiredEntryFilesForProject } from './codeArchitecturePlanEntryContract.ts'
import type { CodeIntent } from './codeIntentTypes.ts'

type PlanFile = {
  path: string
  role: string
  language?: string
  required: boolean
  imports: string[]
  exports: string[]
  notes: string[]
}

function languageForPath(path: string): string {
  if (/\.html?$/i.test(path)) return 'html'
  if (/\.css$/i.test(path)) return 'css'
  if (/\.tsx?$/i.test(path)) return 'typescript'
  if (/\.jsx?$/i.test(path)) return 'javascript'
  if (/\.py$/i.test(path)) return 'python'
  if (/\.json$/i.test(path)) return 'json'
  if (/\.md$/i.test(path)) return 'markdown'
  return 'text'
}

/**
 * Second fichier credible quand l intent n en produit qu un seul.
 * Le schema exige au minimum deux fichiers, et un projet a un seul fichier
 * n est de toute facon pas un livrable.
 */
function companionFileFor(projectType: string, existing: string[]): PlanFile | null {
  const has = (p: string) => existing.some((e) => e.toLowerCase() === p.toLowerCase())
  const candidates: Array<[string, string]> =
    projectType.startsWith('cli') || projectType.startsWith('api_') || projectType.startsWith('data')
      ? [['requirements.txt', 'dependances du projet'], ['README.md', 'mode d emploi']]
      : [['README.md', 'mode d emploi'], ['package.json', 'manifeste du projet']]
  for (const [path, role] of candidates) {
    if (!has(path)) {
      return {
        path,
        role,
        language: languageForPath(path),
        required: true,
        imports: [],
        exports: [],
        notes: ['Fichier de repli ajoute pour rendre le projet exploitable.'],
      }
    }
  }
  return null
}

/**
 * Construit un plan d architecture deterministe a partir du seul intent.
 *
 * Le plan produit satisfait `normalizeArchitecturePlan` : meme schema, meme
 * exigences (2 fichiers minimum, execution non vide, 2 validations, un flux de
 * donnees, un risque). Il n invente rien : tout vient de l intent et des
 * fichiers d entree deja contractualises.
 */
export function buildFallbackArchitecturePlan(intent: CodeIntent, prompt: string): string {
  const projectType = String(intent.projectType || 'static_web')

  const base = defaultFilesForIntent(intent)
  const paths = base.map((f) => f.path)

  // La porte d entree du type de projet reste non negociable, meme en repli.
  const entries = requiredEntryFilesForProject(projectType as CodeIntent['projectType'])
  const files: PlanFile[] = []
  for (const entry of entries) {
    if (!paths.some((p) => p.toLowerCase() === entry.toLowerCase())) {
      files.push({
        path: entry,
        role: /\.html?$/i.test(entry) ? 'page principale' : 'manifeste du projet',
        language: languageForPath(entry),
        required: true,
        imports: [],
        exports: [],
        notes: ['Porte d entree du projet.'],
      })
    }
  }
  for (const f of base) {
    files.push({
      path: f.path,
      role: f.role,
      language: f.language || languageForPath(f.path),
      required: true,
      imports: [],
      exports: [],
      notes: [],
    })
  }
  if (files.length < 2) {
    const companion = companionFileFor(projectType, files.map((f) => f.path))
    if (companion) files.push(companion)
  }

  const languages = Array.isArray(intent.languages) && intent.languages.length > 0
    ? intent.languages.map(String)
    : ['javascript']
  const frameworks = Array.isArray(intent.frameworks) ? intent.frameworks.map(String) : []

  const execution = {
    install: intent.projectType.startsWith('cli_python') || languages.includes('python')
      ? ['pip install -r requirements.txt']
      : ['npm install'],
    dev: intent.devCommand ? [intent.devCommand] : [],
    build: intent.buildCommand ? [intent.buildCommand] : [],
    test: intent.testCommand ? [intent.testCommand] : [],
    preview: files.some((f) => /index\.html$/i.test(f.path)) ? 'index.html' : '',
  }
  // Le schema refuse une execution entierement vide.
  if (![...execution.install, ...execution.dev, ...execution.build, ...execution.test, execution.preview].some(Boolean)) {
    execution.preview = files[0]?.path ?? 'index.html'
  }

  const title = prompt.trim().slice(0, 80) || 'projet'
  const plan = {
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType,
    summary:
      `Plan de repli deterministe derive de l intent pour: ${title}. `
      + `L architecte n a pas produit de plan exploitable; cette structure minimale garantit un livrable executable.`,
    stack: {
      runtime: languages.includes('python') ? 'python' : 'node',
      packageManager: languages.includes('python') ? 'pip' : 'npm',
      languages,
      frameworks,
      dependencies: [],
      scripts: [],
    },
    files,
    dataFlow: ['utilisateur -> interface -> logique applicative'],
    execution,
    generationOrder: files.map((f) => f.path),
    validation: [
      'Chaque fichier du plan est present et complet.',
      'Le projet se lance sans modification manuelle.',
    ],
    risks: [
      {
        risk: 'Plan de repli minimal: certaines fonctionnalites du prompt peuvent manquer.',
        mitigation: 'La boucle de validation et de correction complete les manques detectes.',
      },
    ],
    design: { palette: [], typography: [], ux: [], responsive: [] },
  }

  return JSON.stringify(plan, null, 2)
}
