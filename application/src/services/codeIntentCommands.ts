// ---------------------------------------------------------------------------
// Preview and command routing
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeProjectType } from './codeIntentTypes.ts'

export const DEV_SERVER_PROJECTS = new Set<CodeProjectType>([
  'spa_react', 'spa_vue', 'spa_angular', 'spa_svelte',
  'ssr_nextjs', 'ssr_nuxt', 'ssr_remix',
  'fullstack_mern', 'fullstack_nextjs', 'fullstack_django', 'fullstack_rails',
  'api_express', 'api_fastapi', 'api_django', 'api_flask', 'api_spring',
  'api_gin', 'api_actix', 'api_dotnet',
  'desktop_electron', 'desktop_tauri', 'desktop_app', 'game_web', 'engine_3d', 'ide',
])

export const BUNDLED_PREVIEW_PROJECTS = new Set<CodeProjectType>([
  'library_npm', 'cli_node', 'engine_3d', 'ide',
])

export function getDevCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react': return 'npm run dev'
    case 'spa_vue': return 'npm run dev'
    case 'spa_angular': return 'npx ng serve'
    case 'spa_svelte': return 'npm run dev'
    case 'ssr_nextjs': return 'npm run dev'
    case 'ssr_nuxt': return 'npm run dev'
    case 'ssr_remix': return 'npm run dev'
    case 'api_express': return 'npm run dev'
    case 'api_fastapi': return 'uvicorn main:app --reload'
    case 'api_django': return 'python manage.py runserver'
    case 'api_flask': return 'flask run'
    case 'api_spring': return 'mvn spring-boot:run'
    case 'api_gin': return 'go run .'
    case 'api_actix': return 'cargo run'
    case 'api_dotnet': return 'dotnet run'
    case 'fullstack_mern': return 'npm run dev'
    case 'fullstack_nextjs': return 'npm run dev'
    case 'fullstack_django': return 'python manage.py runserver'
    case 'fullstack_rails': return 'rails server'
    case 'desktop_electron': return 'npm run dev'
    case 'desktop_tauri': return 'npm run tauri:dev'
    case 'desktop_app': return 'cmake --build build && ./build/app'
    case 'game_web': return 'npm run dev'
    case 'engine_3d': return 'npm run dev'
    case 'ide': return 'npm run dev'
    case 'mobile_android': return './gradlew installDebug'
    case 'embedded_esp32': return 'pio run --target upload'
    case 'embedded_arduino': return 'arduino-cli upload -p <port>'
    default: return null
  }
}

export function getBuildCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react':
    case 'spa_vue':
    case 'spa_svelte':
    case 'ssr_nextjs':
    case 'ssr_nuxt':
    case 'ssr_remix':
    case 'fullstack_mern':
    case 'fullstack_nextjs':
    case 'library_npm':
    case 'desktop_electron':
    case 'game_web':
    case 'engine_3d':
    case 'ide':
      return 'npm run build'
    case 'desktop_tauri':
      return 'npm run tauri:build'
    case 'mobile_ios':
      return 'xcodebuild build'
    case 'mobile_android':
      return './gradlew assembleDebug'
    case 'embedded_esp32':
      return 'pio run'
    case 'embedded_arduino':
      return 'arduino-cli compile --fqbn arduino:avr:uno .'
    case 'compiler':
      return 'cargo build'
    case 'os_kernel':
      return 'make'
    case 'distributed_system':
      return 'docker compose build'
    case 'desktop_app':
      return 'cmake --build build'
    case 'spa_angular': return 'npx ng build'
    case 'system_rust':
    case 'cli_rust':
    case 'api_actix':
      return 'cargo build'
    case 'cli_go':
    case 'api_gin':
      return 'go build ./...'
    case 'api_spring': return 'mvn compile'
    case 'api_dotnet': return 'dotnet build'
    case 'system_cpp':
    case 'cli_cpp':
      return 'cmake --build build'
    default: return null
  }
}

export function getTestCommand(projectType: CodeProjectType): string | null {
  switch (projectType) {
    case 'spa_react':
    case 'spa_vue':
    case 'spa_svelte':
    case 'spa_angular':
    case 'ssr_nextjs':
    case 'ssr_nuxt':
    case 'ssr_remix':
    case 'api_express':
    case 'fullstack_mern':
    case 'fullstack_nextjs':
    case 'library_npm':
    case 'cli_node':
    case 'desktop_electron':
    case 'game_web':
    case 'engine_3d':
    case 'ide':
      return 'npm test'
    case 'desktop_tauri':
      return 'cargo test'
    case 'mobile_ios':
      return 'xcodebuild test'
    case 'mobile_android':
      return './gradlew test'
    case 'embedded_esp32':
      return 'pio test'
    case 'embedded_arduino':
      return 'arduino-cli compile --fqbn arduino:avr:uno .'
    case 'compiler':
      return 'cargo test'
    case 'os_kernel':
      return 'make test'
    case 'distributed_system':
      return 'docker compose run --rm tests'
    case 'desktop_app':
      return 'ctest --test-dir build'
    case 'api_fastapi':
    case 'api_django':
    case 'api_flask':
    case 'cli_python':
    case 'data_python':
    case 'library_pypi':
      return 'pytest'
    case 'system_rust':
    case 'cli_rust':
    case 'api_actix':
    case 'library_crate':
      return 'cargo test'
    case 'cli_go':
    case 'api_gin':
      return 'go test ./...'
    case 'api_spring': return 'mvn test'
    case 'api_dotnet': return 'dotnet test'
    default: return null
  }
}

// ---------------------------------------------------------------------------
