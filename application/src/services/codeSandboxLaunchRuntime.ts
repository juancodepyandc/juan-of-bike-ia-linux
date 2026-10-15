import { findFile } from './codeSandboxFiles.ts'
import { isWindows } from './codeSandboxRuntime.ts'
import type { CodeFile, DetectedLanguage } from './codeSandboxTypes.ts'

export function generateLaunchSh(files: CodeFile[], lang: DetectedLanguage): CodeFile | null {
  const hasLaunchScript = files.some((file) => /^(start|launch|lancement)\.(sh|bat)$/i.test(file.name.replace(/.*[/\\]/, '')))
  if (hasLaunchScript) return null

  let script = ''
  switch (lang) {
    case 'node': {
      const manifest = findFile(files, 'package.json')
      let devScript = 'npm start'
      if (manifest) {
        try {
          const parsed = JSON.parse(manifest.content)
          if (parsed.scripts?.dev) devScript = 'npm run dev'
          else if (parsed.scripts?.start) devScript = 'npm start'
          else if (parsed.scripts?.serve) devScript = 'npm run serve'
          else if (parsed.main) devScript = `node ${parsed.main}`
        } catch { /* invalid manifests are handled by validation */ }
      }
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'command -v npm >/dev/null 2>&1 || { echo "Node.js avec npm est requis." >&2; exit 1; }',
        'npm install',
        devScript,
      ].join('\n')
      break
    }
    case 'python': {
      const mainPy = files.find((file) => /main\.py$/i.test(file.name)) || files.find((file) => /app\.py$/i.test(file.name))
      const entry = mainPy ? mainPy.name.replace(/\\/g, '/') : 'main.py'
      const hasRequirements = !!findFile(files, 'requirements.txt')
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'command -v python >/dev/null 2>&1 || { echo "Python est requis." >&2; exit 1; }',
        ...(hasRequirements ? ['python -m pip install -r requirements.txt'] : []),
        `python ${entry}`,
      ].join('\n')
      break
    }
    case 'rust':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ncargo run'
      break
    case 'go':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ngo run .'
      break
    case 'java':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\njavac *.java && java Main'
      break
    case 'c':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ngcc -o out *.c && ./out'
      break
    case 'cpp':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\ng++ -o out *.cpp && ./out'
      break
    case 'assembly':
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'if ls *.asm >/dev/null 2>&1 && command -v nasm >/dev/null 2>&1; then',
        '  for f in *.asm; do nasm -f elf64 "$f" -o "${f%.asm}.o"; done',
        '  gcc -no-pie *.o -o out && ./out',
        'elif ls *.s *.S >/dev/null 2>&1; then',
        '  gcc -no-pie *.s -o out 2>/dev/null && ./out || (as *.s -o out.o && ld out.o -o out && ./out)',
        'fi',
      ].join('\n')
      break
    case 'swift':
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'if [ -f Package.swift ]; then swift run; else swiftc $(find . -name "*.swift") -o out && ./out; fi',
      ].join('\n')
      break
    case 'multi-system':
      script = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'cd "$(dirname "$0")"',
        'if [ -f verify_system.py ]; then python3 verify_system.py; elif [ -f main.py ]; then python3 main.py; elif [ -f Makefile ]; then make; fi',
      ].join('\n')
      break
    case 'typescript-standalone':
      script = '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\nnpx ts-node index.ts'
      break
    default:
      return null
  }

  return { name: 'start.sh', language: 'bash', content: script }
}
