import { formatArchitecturePlanDependenciesForMarkdown } from './codeArchitecturePlan.ts'
import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'

type ProjectRunbook = {
  installSteps: string[]
  runSteps: string[]
}

function buildProjectRunbook(files: CodeFile[], intent: CodeIntent): ProjectRunbook {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const hasIndexHtml = normalizedNames.includes('index.html')
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    return {
      installSteps: ['Aucune installation requise.'],
      runSteps: [hasIndexHtml ? 'Ouvrir `index.html` dans un navigateur.' : 'Le projet doit fournir un `index.html` pour la preview.'],
    }
  }

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const installSteps = ['```bash', 'npm install', '```']
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      installSteps.push('', '```bash', 'cargo build', '```')
    }
    return { installSteps, runSteps: ['```bash', resolvedRunCommand, '```'] }
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    return {
      installSteps: hasRequirements
        ? ['```bash', 'pip install -r requirements.txt', '```']
        : ['Installer Python 3.11+ puis les dependances du projet.'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    return {
      installSteps: ['```bash', 'cargo build', '```'],
      runSteps: ['```bash', runCommand || 'cargo run', '```'],
    }
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    return {
      installSteps: ['```bash', 'go mod tidy', '```'],
      runSteps: ['```bash', runCommand || 'go run .', '```'],
    }
  }

  return {
    installSteps: ['Voir les fichiers de configuration du projet pour les dependances exactes.'],
    runSteps: ['Consulter le code livre et le README pour lancer manuellement le projet.'],
  }
}

export function generateProjectReadme(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile {
  const fileList = files
    .filter((file) => file.name.toLowerCase() !== 'readme.md')
    .map((file) => `- \`${file.name}\` — ${file.language}`)
    .join('\n')
  const runbook = buildProjectRunbook(files, intent)

  let dependenciesSection = ''
  if (architecturePlan) {
    const dependencies = formatArchitecturePlanDependenciesForMarkdown(architecturePlan)
    if (dependencies) dependenciesSection = `## Dependances\n\n${dependencies}\n\n`
  }

  const content = [
    `# ${intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())}`,
    '',
    `> ${prompt.slice(0, 200)}${prompt.length > 200 ? '...' : ''}`,
    '',
    '## Structure du projet',
    '',
    fileList,
    '',
    dependenciesSection,
    '## Installation',
    '',
    runbook.installSteps.join('\n'),
    '',
    '## Lancement',
    '',
    runbook.runSteps.join('\n'),
    '',
    '## Raccourci de lancement',
    '',
    'Le fichier `start.sh` est fourni quand un demarrage automatise est possible sur Linux/macOS.',
    '',
    '---',
    '*Genere par Aurora IA — Module Code*',
  ].join('\n')

  return { name: 'README.md', language: 'markdown', content }
}
