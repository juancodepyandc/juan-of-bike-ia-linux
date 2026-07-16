import type { CodeIntent, CodeProjectType } from './codeIntentTypes.ts'

export type ProjectGenerator = {
  projectType: CodeProjectType
  label: string
  requiredFiles: string[]
  qualityBar: string[]
  instructions: string[]
}

const GENERATORS: Partial<Record<CodeProjectType, ProjectGenerator>> = {
  embedded_esp32: {
    projectType: 'embedded_esp32',
    label: 'Firmware ESP32',
    requiredFiles: ['platformio.ini', 'src/main.cpp', 'test/test_main.cpp', 'README.md'],
    qualityBar: ['build PlatformIO', 'serial heartbeat', 'pin map documented'],
    instructions: ['Utilise ESP-IDF/PlatformIO', 'Expose une boucle non bloquante', 'Prevois logs serie testables'],
  },
  embedded_arduino: {
    projectType: 'embedded_arduino',
    label: 'Firmware Arduino',
    requiredFiles: ['sketch.ino', 'README.md', 'test/README.md'],
    qualityBar: ['compile arduino-cli', 'setup/loop complets', 'GPIO documentes'],
    instructions: ['Aucune dependance reseau', 'Code C++ Arduino idiomatique', 'Constantes pins explicites'],
  },
  compiler: {
    projectType: 'compiler',
    label: 'Mini compilateur',
    requiredFiles: ['Cargo.toml', 'src/lexer.rs', 'src/parser.rs', 'src/eval.rs', 'tests/language.rs'],
    qualityBar: ['lexer teste', 'parser teste', 'programme exemple execute'],
    instructions: ['Specifie la grammaire', 'Couvre erreurs de syntaxe', 'Ajoute tests figes du langage'],
  },
  os_kernel: {
    projectType: 'os_kernel',
    label: 'Noyau/OS minimal',
    requiredFiles: ['Makefile', 'kernel/main.c', 'boot/boot.s', 'linker.ld', 'README.md'],
    qualityBar: ['image bootable', 'heartbeat QEMU', 'aucun appel libc implicite'],
    instructions: ['Genere une cible QEMU', 'Ajoute un message/heartbeat verifiable', 'Documente toolchain croisee'],
  },
  distributed_system: {
    projectType: 'distributed_system',
    label: 'Systeme distribue',
    requiredFiles: ['docker-compose.yml', 'cmd/node/main.go', 'internal/protocol/protocol.go', 'tests/integration.test.go'],
    qualityBar: ['>=2 noeuds', 'test integration reseau', 'timeouts et retries'],
    instructions: ['Inclure orchestration locale', 'Journaliser chaque noeud', 'Tester un scenario inter-noeuds'],
  },
  mobile_ios: {
    projectType: 'mobile_ios',
    label: 'App iOS native',
    requiredFiles: ['Package.swift', 'Sources/App/App.swift', 'Sources/App/ContentView.swift', 'Tests/AppTests.swift'],
    qualityBar: ['SwiftUI compile', 'etat UI teste', 'accessibilite labels'],
    instructions: ['Utilise SwiftUI', 'Architecture MVVM simple', 'Aucun wrapper web'],
  },
  mobile_android: {
    projectType: 'mobile_android',
    label: 'App Android native',
    requiredFiles: ['settings.gradle.kts', 'app/build.gradle.kts', 'app/src/main/java/MainActivity.kt', 'app/src/test/java/AppTest.kt'],
    qualityBar: ['Gradle assemble', 'Compose UI', 'tests unitaires'],
    instructions: ['Utilise Kotlin + Jetpack Compose', 'Aucun wrapper web', 'State hoisting propre'],
  },
  desktop_app: {
    projectType: 'desktop_app',
    label: 'Application desktop native',
    requiredFiles: ['CMakeLists.txt', 'src/main.cpp', 'src/AppWindow.cpp', 'tests/app_test.cpp'],
    qualityBar: ['CMake build', 'fenetre native', 'tests CTest'],
    instructions: ['Utilise Qt/GTK selon le prompt', 'Aucun site web deguise', 'Separations UI/domaine'],
  },
  engine_3d: {
    projectType: 'engine_3d',
    label: 'Moteur 3D',
    requiredFiles: ['package.json', 'src/engine/Renderer.ts', 'src/engine/Scene.ts', 'src/main.ts', 'tests/engine.test.ts'],
    qualityBar: ['boucle rendu', 'scene non vide', 'tests camera/scene'],
    instructions: ['Separarer engine/demo', 'Prevoir abstraction scene/camera', 'Mesurer FPS basique'],
  },
  ide: {
    projectType: 'ide',
    label: 'IDE / editeur de code',
    requiredFiles: ['package.json', 'src/App.tsx', 'src/editor/EditorPane.tsx', 'src/workspace/fileTree.ts', 'tests/workspace.test.ts'],
    qualityBar: ['editeur utilisable', 'arborescence fichiers', 'preview/logs si demande'],
    instructions: ['Utilise CodeMirror si possible', 'Raccourcis clavier de base', 'Etat workspace persistant'],
  },
}

export function getProjectGeneratorForType(projectType: CodeProjectType) {
  return GENERATORS[projectType] ?? null
}

export function getProjectGeneratorForIntent(intent: CodeIntent) {
  return getProjectGeneratorForType(intent.projectType)
}

export function buildProjectGeneratorPromptBlock(intent: CodeIntent) {
  const generator = getProjectGeneratorForIntent(intent)
  if (!generator) return ''
  return [
    `## Generateur specialise WS6: ${generator.label}`,
    `Type: ${generator.projectType}`,
    'Fichiers structurels attendus:',
    ...generator.requiredFiles.map((file) => `- ${file}`),
    'Barre qualite:',
    ...generator.qualityBar.map((rule) => `- ${rule}`),
    'Instructions specialisees:',
    ...generator.instructions.map((rule) => `- ${rule}`),
  ].join('\n')
}
