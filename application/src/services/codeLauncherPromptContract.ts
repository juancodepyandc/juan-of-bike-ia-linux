import type { CodeIntent } from './codeIntent.ts'

export function buildLauncherInstructionBlock(intent: CodeIntent): string {
  if (intent.projectType === 'static_web') {
    return [
      '## LANCEMENT',
      '- NE genere PAS de script de lancement. Il suffit d ouvrir index.html dans un navigateur.',
      '- Le README.md (optionnel mais apprecie) peut mentionner: "Ouvrir index.html dans un navigateur ou servir via `npx serve`".',
    ].join('\n')
  }

  if (intent.projectType === 'script') {
    return [
      '## LANCEMENT',
      '- Si le projet se lance via une commande directe (ex. `python main.py`), un README.md suffit.',
      '- Les scripts de lancement ne sont PAS obligatoires pour un simple script.',
    ].join('\n')
  }

  const devCommand = intent.devCommand || 'npm run dev'
  return [
    '## LANCEMENT — SCRIPT LOCAL LINUX/MAC',
    'Genere a la racine du projet un fichier `start.sh` executable pour lancer le projet sur cet environnement Linux.',
    '',
    '```bash',
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    'cd "$(dirname "$0")"',
    'echo "=== Installation des dependances ==="',
    inferInstallCommand(intent),
    'echo "=== Lancement du projet ==="',
    devCommand,
    '```',
    '',
    '- N ajoute PAS de fichier `.bat` ni de script PowerShell dans cette generation Linux.',
    '- Adapte les commandes au projet reel (pip, npm, cargo, go, maven, etc.).',
    '- Pour les projets multi-services (frontend + backend), chaque service doit pouvoir etre lance correctement.',
  ].join('\n')
}

function inferInstallCommand(intent: CodeIntent): string {
  if (intent.languages.includes('python')) return 'pip install -r requirements.txt'
  if (intent.languages.includes('rust')) return 'cargo build'
  if (intent.languages.includes('go')) return 'go mod download'
  if (intent.languages.includes('java') || intent.languages.includes('kotlin')) return 'mvn install'
  if (intent.languages.includes('csharp')) return 'dotnet restore'
  if (intent.languages.includes('ruby')) return 'bundle install'
  if (intent.languages.includes('php')) return 'composer install'
  return 'npm install'
}
