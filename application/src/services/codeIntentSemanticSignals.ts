import type { CodeProjectType } from './codeIntentTypes.ts'
import { containsSignal } from './codeIntentSignalUtils.ts'

export type CodeSemanticProjectSignal = {
  projectType: CodeProjectType
  keywords: string[]
  languages: string[]
  frameworks: string[]
  features: string[]
}

export const SEMANTIC_PROJECT_SIGNALS: CodeSemanticProjectSignal[] = [
  {
    projectType: 'embedded_esp32',
    keywords: ['esp32', 'esp-idf', 'idf esp32', 'firmware esp32', 'microcontroleur esp32'],
    languages: ['c', 'cpp'],
    frameworks: ['esp-idf'],
    features: ['embedded', 'firmware', 'serial'],
  },
  {
    projectType: 'embedded_arduino',
    keywords: ['arduino', 'arduino uno', 'arduino r3', 'sketch arduino', 'firmware arduino'],
    languages: ['cpp'],
    frameworks: ['arduino-cli'],
    features: ['embedded', 'firmware', 'gpio'],
  },
  {
    projectType: 'compiler',
    keywords: ['compilateur', 'compiler', 'lexer parser', 'parser ast', 'langage de programmation', 'interpreteur', 'interpreter'],
    languages: ['rust'],
    frameworks: ['cargo'],
    features: ['compiler', 'lexer', 'parser', 'tests'],
  },
  {
    projectType: 'os_kernel',
    keywords: ['noyau os', 'noyau systeme', 'kernel', 'os kernel', 'systeme d exploitation', 'bootable', 'qemu boot'],
    languages: ['c', 'assembly'],
    frameworks: ['qemu', 'make'],
    features: ['bootable', 'kernel', 'qemu'],
  },
  {
    projectType: 'distributed_system',
    keywords: ['systeme distribue', 'distributed system', 'cluster', 'multi noeuds', 'multi node', 'raft', 'consensus'],
    languages: ['go'],
    frameworks: ['docker-compose'],
    features: ['distributed', 'network', 'integration-tests'],
  },
  {
    projectType: 'mobile_ios',
    keywords: ['ios native', 'app ios native', 'swiftui', 'uikit', 'xcode project'],
    languages: ['swift'],
    frameworks: ['swiftui'],
    features: ['mobile-native', 'ios'],
  },
  {
    projectType: 'mobile_android',
    keywords: ['android native', 'app android native', 'kotlin android', 'jetpack compose', 'gradle android'],
    languages: ['kotlin'],
    frameworks: ['jetpack-compose', 'gradle'],
    features: ['mobile-native', 'android'],
  },
  {
    projectType: 'desktop_app',
    keywords: ['qt app', 'application qt', 'gtk app', 'application gtk', 'desktop native app'],
    languages: ['cpp'],
    frameworks: ['qt'],
    features: ['desktop-native'],
  },
  {
    projectType: 'engine_3d',
    keywords: ['moteur 3d', '3d engine', 'moteur graphique', 'rendering engine', 'game engine 3d'],
    languages: ['typescript', 'javascript'],
    frameworks: ['three.js', 'webgpu'],
    features: ['3d', 'rendering-engine'],
  },
  {
    projectType: 'ide',
    keywords: ['ide', 'editeur de code', 'éditeur de code', 'code editor', 'studio de code'],
    languages: ['typescript'],
    frameworks: ['react', 'codemirror'],
    features: ['editor', 'workspace', 'preview'],
  },
]

export function matchSemanticProjectSignal(normalizedPrompt: string): CodeSemanticProjectSignal | null {
  for (const signal of SEMANTIC_PROJECT_SIGNALS) {
    if (signal.keywords.some((keyword) => containsSignal(normalizedPrompt, keyword))) return signal
  }
  return null
}
