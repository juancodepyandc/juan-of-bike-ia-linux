import type { CodeIntent, CodeProjectType } from '../services/codeIntent'

const PROJECT_TYPE_LABELS: Record<CodeProjectType, string> = {
  static_web: 'Page web statique',
  spa_react: 'App React (SPA)',
  spa_vue: 'App Vue (SPA)',
  spa_angular: 'App Angular (SPA)',
  spa_svelte: 'App Svelte (SPA)',
  ssr_nextjs: 'Next.js (SSR)',
  ssr_nuxt: 'Nuxt.js (SSR)',
  ssr_remix: 'Remix (SSR)',
  api_express: 'API Express (Node)',
  api_fastapi: 'API FastAPI (Python)',
  api_django: 'API Django (Python)',
  api_flask: 'API Flask (Python)',
  api_spring: 'API Spring Boot (Java)',
  api_gin: 'API Gin (Go)',
  api_actix: 'API Actix (Rust)',
  api_dotnet: 'API ASP.NET',
  fullstack_mern: 'Fullstack MERN',
  fullstack_nextjs: 'Fullstack Next.js',
  fullstack_django: 'Fullstack Django',
  fullstack_rails: 'Fullstack Rails',
  cli_node: 'CLI Node.js',
  cli_python: 'Script Python',
  cli_rust: 'CLI Rust',
  cli_go: 'CLI Go',
  cli_cpp: 'CLI C++',
  desktop_electron: 'App desktop Electron',
  desktop_tauri: 'App desktop Tauri',
  mobile_rn: 'App mobile React Native',
  mobile_flutter: 'App mobile Flutter',
  library_npm: 'Librairie npm',
  library_pypi: 'Package PyPI',
  library_crate: 'Crate Rust',
  game_web: 'Jeu / App 3D (canvas / WebGL)',
  game_unity: 'Jeu Unity (C#)',
  system_c: 'Système C',
  system_cpp: 'Système C++',
  system_rust: 'Système Rust',
  data_python: 'Data / ML (Python)',
  devops_docker: 'DevOps / Docker',
  script: 'Script',
  unknown: 'Type inconnu',
}

export const CODE_VIEW_PROMPT_GUIDE: string[] = [
  'But concret et stack attendue (React, FastAPI, Rust CLI...)',
  'Fonctions obligatoires et comportement attendu',
  'Multi-page: routing, navigation, layout partage',
  'Architecture: API REST, GraphQL, fullstack, microservices',
]

export function formatProjectType(type: CodeProjectType): string {
  return PROJECT_TYPE_LABELS[type] ?? type.replace(/_/g, ' ')
}

export function isVisionContextFile(file: Pick<File, 'name' | 'type'>): boolean {
  const filename = file.name.toLowerCase()
  const mime = file.type.toLowerCase()
  return mime.startsWith('image/')
    || mime.includes('pdf')
    || /\.(png|jpe?g|webp|gif|bmp|pdf|xlsx?|xlsm|csv|tsv)$/i.test(filename)
}

export function codeContextNeedsVision(files: Pick<File, 'name' | 'type'>[]): boolean {
  return files.some(isVisionContextFile)
}

export function buildCodePipelineLabel(intent: CodeIntent | null): string {
  if (!intent) return 'Intent, preflight local, planning, generation, sandbox, correction, preview.'

  const parts: string[] = ['Preflight local']
  if (intent.needsArchitecturePlanning) parts.push('Planning archi')
  parts.push('Generation modele expert')
  parts.push('Sandbox isole')
  parts.push('Boucle auto-correction')
  if (intent.needsDevServer) parts.push('Dev server')
  if (intent.previewType !== 'none') parts.push('Preview')
  return parts.join(' → ')
}
