// ---------------------------------------------------------------------------
// Code Skills Registry & Self-Installation Engine
// Connects the Code module (Architect, Coder, Auditor) to persistent skills
// in `.aurora/skills/*.md` via `/api/code/skills*` with full offline/CLI fallback.
// Enables autonomous skill acquisition before planning and post-run learning.
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeProjectType } from './codeIntentTypes.ts'
import type { CodeFile } from './codeOrchestrator.ts'

export type CodeSkillSource = 'builtin' | 'self_installed' | 'user' | 'user-installed' | 'auto-learned'

export interface CodeSkill {
  id: string
  title: string
  category: 'low-level' | 'master-language' | 'architecture' | 'application' | 'algorithms' | 'meta-agent' | 'auto-learned' | string
  languages: string[]
  projectTypes: string[]
  triggers: string[]
  source: CodeSkillSource
  summary: string
  content: string
  rules?: string[]
  installedAt: number
  usageCount: number
  path?: string
}

export type CodeSkillEntry = CodeSkill

export interface CodeAgentRoleStatus {
  id: string
  name: string
  title: string
  role: string
  specialty: string
  active: boolean
  status: 'idle' | 'active' | 'verifying' | 'done' | 'ready'
  detail?: string
}

export interface CodeAgentsDiagnostics {
  ok: boolean
  skillsCount: number
  builtinSkillsCount: number
  selfInstalledSkillsCount: number
  officialAgents: Array<{
    id: string
    module: string
    description: string
    canCreateSubagents: boolean
    source: string
  }>
  dynamicAgents: Array<{
    id: string
    module: string
    description: string
    canCreateSubagents: boolean
    source: string
  }>
  codePipelineRoles: CodeAgentRoleStatus[]
  toolchains: Record<string, boolean | { available: boolean; path?: string | null }>
}

export type CodeAgentDiagnostics = CodeAgentsDiagnostics

const LOCAL_STORAGE_SKILLS_KEY = 'aurora.code.self_installed_skills.v1'

export const DEFAULT_CODE_SKILLS: CodeSkill[] = [
  {
    id: 'asm-x86_64-arm64-abi',
    title: 'Assembleur x86_64 & ARM64 (NASM / GAS / ABI System V / FFI)',
    category: 'low-level',
    languages: ['assembly', 'asm', 'nasm', 'gas', 'c'],
    projectTypes: ['system_asm', 'os_kernel', 'system_c', 'multi_system'],
    triggers: ['assembleur', 'assembly', 'nasm', 'gas', 'x86_64', 'arm64', 'aarch64', 'syscall', 'registre', 'simd', 'avx', 'bootloader', '.asm', '.s'],
    source: 'builtin',
    summary: 'Conventions d appel System V AMD64 & ARM64, alignement de pile 16 octets, appels systeme Linux/macOS et interfacage C/FFI.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/asm-x86_64-arm64-abi.md',
    content: [
      '# Skill: Assembleur x86_64 & ARM64 (NASM / GAS / ABI System V / FFI)',
      '',
      '## Convention d appel System V AMD64 (Linux / macOS x86_64)',
      '- Arguments entiers/pointeurs dans l ordre: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`.',
      '- Valeur de retour: `rax` (et `rdx` pour 128 bits).',
      '- Registres callee-saved (a preserver par `push`/`pop`): `rbx`, `rbp`, `r12`, `r13`, `r14`, `r15`.',
      '- Alignement de pile: `rsp` DOIT etre aligne sur 16 octets (`rsp % 16 == 0`) juste AVANT toute instruction `call`.',
      '- En fin de fichier GAS (`.s`), inclure `.section .note.GNU-stack,"",@progbits` pour eviter le warning linker.',
      '- Appels systeme Linux x86_64: `rax=1` (write), `rax=60` (exit), instruction `syscall`.',
      '- Compilation: `gcc -no-pie -O2 main.s -o app && ./app` ou `nasm -f elf64 main.asm -o main.o && gcc -no-pie main.o -o app && ./app`.',
    ].join('\n'),
  },
  {
    id: 'swift-modern-systems',
    title: 'Swift 5.10/6 Système, Concurrence Structurée & SwiftPM',
    category: 'master-language',
    languages: ['swift'],
    projectTypes: ['cli_swift', 'mobile_ios', 'multi_system', 'desktop_app'],
    triggers: ['swift', 'swiftui', 'swiftpm', 'package.swift', 'actor', 'sendable', 'async/await', 'ios', 'macos'],
    source: 'builtin',
    summary: 'Architecture Swift Package Manager, typage fort par valeur, concurrence structuree (async/await, actors) et interoperabilite C/systeme.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/swift-modern-systems.md',
    content: [
      '# Skill: Swift 5.10/6 Système, Concurrence Structurée & SwiftPM',
      '',
      '## Organisation et Rigueur Swift',
      '- Pour un projet multi-fichiers ou executable structure, fournir un `Package.swift` valide (`// swift-tools-version: 5.9`) avec `executableTarget` sous `Sources/`.',
      '- Privilegier `struct`, `enum` a valeurs associees, `protocol` et `actor` pour l isolation d etat.',
      '- Bannir le force-unwrap `!` non prouve ; utiliser `guard let` et `Result<T, Error>`.',
      '- Pour la portabilite Linux/macOS: `#if canImport(Darwin) import Darwin #elseif canImport(Glibc) import Glibc #endif`.',
      '- Inclure des assertions d auto-verification deterministes retournant un code de sortie 0.',
    ].join('\n'),
  },
  {
    id: 'multi-system-polyglot-architecture',
    title: 'Architecture Multi-Systèmes Polyglotte & Contrats IPC / FFI',
    category: 'architecture',
    languages: ['multi-system', 'c', 'cpp', 'rust', 'assembly', 'swift', 'python', 'go', 'typescript'],
    projectTypes: ['multi_system', 'distributed_system', 'os_kernel', 'compiler', 'desktop_tauri'],
    triggers: ['multi-système', 'multi systeme', 'multi-system', 'polyglotte', 'polyglot', 'ffi', 'ipc', 'ctypes', 'cffi', 'bridge', 'hybride', 'orchestrateur'],
    source: 'builtin',
    summary: 'Decoupage topologique de systemes hybrides (moteur bas niveau ASM/C/Rust + orchestrateur Python/Go/Swift + interface/API), contrats FFI/IPC et validation bout-en-bout.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/multi-system-polyglot-architecture.md',
    content: [
      '# Skill: Architecture Multi-Systèmes Polyglotte & Contrats IPC / FFI',
      '',
      '## Principes d Ingenierie Multi-Systemes',
      '1. Separation stricte par couche: Couche Noyau/Calcul Bas Niveau (`core/`, `native/`, `asm/`) en Assembleur/C/C++/Rust ; Couche Pont (`bridge/`, `protocol/`) via ABI C (`extern "C"`), `.so`/ctypes ou JSON-RPC sur stdio/socket ; Couche Orchestration/UI (`orchestrator/`, `api/`, `web/`) en Python/Swift/Go/TypeScript.',
      '2. Ordre topologique: definir le contrat d interface en premier, compiler et tester le sous-systeme natif, puis executer l orchestrateur haut niveau.',
      '3. Resoudre tous les chemins inter-sous-systemes relativement a la racine du projet.',
    ].join('\n'),
  },
  {
    id: 'rust-c-cpp-systems',
    title: 'Ingénierie Système C / C++20 / Rust & Sûreté Mémoire',
    category: 'low-level',
    languages: ['c', 'cpp', 'rust', 'zig'],
    projectTypes: ['system_c', 'system_cpp', 'system_rust', 'cli_rust', 'cli_cpp', 'compiler', 'os_kernel'],
    triggers: ['rust', 'cargo', 'c++', 'cpp', 'cmake', 'pointeur', 'allocateur', 'zero-copy', 'raii', 'mutex', 'mmap'],
    source: 'builtin',
    summary: 'Gestion memoire deterministe, zero comportement indefini (UB), ABI C propre, construction Cargo/CMake/GCC reproductible.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/rust-c-cpp-systems.md',
    content: [
      '# Skill: Ingénierie Système C / C++20 / Rust & Sûreté Mémoire',
      '',
      '- Compiler sans erreur sous `-Wall -Wextra` (`-std=c11` ou `-std=c++20`).',
      '- En C++, utiliser RAII (`std::unique_ptr`, `std::vector`, `std::optional`) et proscrire `new`/`delete` nus.',
      '- En Rust, fournir un `Cargo.toml` propre (`edition = "2021"`), modeliser les erreurs via `Result<T, E>` et inclure des tests `#[cfg(test)]`.',
    ].join('\n'),
  },
  {
    id: 'python-clean-architecture',
    title: 'Python Modulaire, Typage Strict, Interfaçage Natif & Pytest',
    category: 'application',
    languages: ['python'],
    projectTypes: ['cli_python', 'api_fastapi', 'api_flask', 'api_django', 'data_python', 'multi_system'],
    triggers: ['python', 'fastapi', 'pytest', 'asyncio', 'ctypes', 'numpy', 'pandas', 'pipeline', 'orchestrateur'],
    source: 'builtin',
    summary: 'Architecture modulaire en Python, dataclasses immuables, typage complet, ctypes/subprocess et auto-validation pytest/unittest.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/python-clean-architecture.md',
    content: [
      '# Skill: Python Modulaire, Typage Strict, Interfaçage Natif & Pytest',
      '',
      '- Separer le domaine pur (`dataclass`, fonctions pures typees) des adaptateurs CLI/HTTP/FFI (`ctypes`, `subprocess`).',
      '- Fournir des tests compatibles a la fois avec `pytest` et `python3 -m unittest` pour garantir l execution dans tout sandbox.',
    ].join('\n'),
  },
  {
    id: 'algorithmic-problem-solving',
    title: 'Résolution Algorithmique Complexe & Preuve par Invariants',
    category: 'algorithms',
    languages: ['python', 'rust', 'cpp', 'c', 'swift', 'go', 'typescript', 'assembly'],
    projectTypes: ['compiler', 'system_rust', 'system_cpp', 'system_c', 'cli_python', 'multi_system'],
    triggers: ['algorithme', 'algorithm', 'graphe', 'graph', 'programmation dynamique', 'optimisation', 'arbre', 'concurrence', 'cryptographie', 'solveur', 'solver', 'simulation', 'complexite'],
    source: 'builtin',
    summary: 'Methode formelle de decomposition par invariants, bornes de complexite O(T)/O(S), cas degeneres et oracle d auto-test.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/algorithmic-problem-solving.md',
    content: [
      '# Skill: Résolution Algorithmique Complexe & Preuve par Invariants',
      '',
      '- Specifier les invariants et bornes de complexite temporelle/spatiale.',
      '- Eviter les recursions profondes non bornees (utiliser une pile explicite au-dela de 500 niveaux).',
      '- Couvrir les cas limites (entree vide, singleton, cycles, overflow 64-bit) et verifier le resultat par un oracle.',
    ].join('\n'),
  },
  {
    id: 'compiler-vm-kernel-design',
    title: 'Compilateurs, Machines Virtuelles Bytecode & Noyaux Bas Niveau',
    category: 'low-level',
    languages: ['rust', 'c', 'cpp', 'assembly', 'python', 'swift', 'go'],
    projectTypes: ['compiler', 'os_kernel', 'system_asm', 'system_c', 'system_rust', 'multi_system'],
    triggers: ['compilateur', 'compiler', 'lexer', 'parser', 'ast', 'bytecode', 'machine virtuelle', 'vm', 'jit', 'kernel', 'noyau', 'interpreteur'],
    source: 'builtin',
    summary: 'Pipeline complet Lexer -> Parser Pratt -> AST -> Verificateur -> Bytecode/IR -> VM ou emission Assembleur avec tests.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/compiler-vm-kernel-design.md',
    content: [
      '# Skill: Compilateurs, Machines Virtuelles Bytecode & Noyaux Bas Niveau',
      '',
      '- Structurer en étapes pures et testables: Lexer (avec ligne/colonne) -> Parser (Pratt / descente recursive) -> AST type -> Analyse semantique -> VM Bytecode ou generation ASM.',
      '- Inclure une suite de programmes sources de test verifiant l execution et le diagnostic des erreurs de syntaxe.',
    ].join('\n'),
  },
  {
    id: 'self-organization-execution-protocol',
    title: 'Protocole d Auto-Organisation Multi-Agents & Auto-Correction',
    category: 'meta-agent',
    languages: ['all'],
    projectTypes: [],
    triggers: ['organisation', 'architecture', 'complexe', 'complet', 'multi', 'agent', 'systeme'],
    source: 'builtin',
    summary: 'Coordination entre Architecte Systeme, Ingenieurs Specialises (Bas Niveau / Applicatif) et Auditeur Sandbox pour livrer sans dette technique.',
    installedAt: 1729000000,
    usageCount: 1,
    path: '.aurora/skills/self-organization-execution-protocol.md',
    content: [
      '# Skill: Protocole d Auto-Organisation Multi-Agents & Auto-Correction',
      '',
      '- Generer les contrats, types partages et manifestes en premier, puis les moteurs bas niveau, puis les ponts et tests bout-en-bout.',
      '- Verifier que chaque import correspond a un export reellement defini.',
      '- Aucun TODO, stub ou fonction tronquee.',
    ].join('\n'),
  },
]

function loadLocalSelfInstalledSkills(): CodeSkill[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(LOCAL_STORAGE_SKILLS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveLocalSelfInstalledSkill(skill: CodeSkill): void {
  try {
    if (typeof localStorage === 'undefined') return
    const current = loadLocalSelfInstalledSkills().filter((item) => item.id !== skill.id)
    current.unshift(skill)
    localStorage.setItem(LOCAL_STORAGE_SKILLS_KEY, JSON.stringify(current.slice(0, 40)))
  } catch {
    // Ignore storage quota or SSR/CLI environment
  }
}

function mergeSkillsLists(primary: CodeSkill[], secondary: CodeSkill[]): CodeSkill[] {
  const map = new Map<string, CodeSkill>()
  for (const item of secondary) {
    map.set(item.id, item)
  }
  for (const item of primary) {
    map.set(item.id, item)
  }
  return Array.from(map.values()).sort((a, b) => {
    const aSelf = a.source === 'self_installed' ? 0 : 1
    const bSelf = b.source === 'self_installed' ? 0 : 1
    if (aSelf !== bSelf) return aSelf - bSelf
    return a.id.localeCompare(b.id)
  })
}

export async function fetchInstalledCodeSkills(): Promise<CodeSkill[]> {
  const localSkills = mergeSkillsLists(loadLocalSelfInstalledSkills(), DEFAULT_CODE_SKILLS)
  try {
    if (typeof fetch === 'undefined') return localSkills
    const response = await fetch('/api/code/skills', {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return localSkills
    const data = await response.json()
    if (data && Array.isArray(data.skills)) {
      return mergeSkillsLists(data.skills as CodeSkill[], localSkills)
    }
  } catch {
    // Fallback to local/builtin skills when offline or in Node CLI runner
  }
  return localSkills
}

export async function installCodeSkill(input: {
  id?: string
  title: string
  category?: string
  languages?: string[]
  projectTypes?: string[]
  triggers?: string[]
  summary?: string
  content?: string
  rules?: string[]
  source?: CodeSkillSource
}): Promise<CodeSkill> {
  const slug = (input.id || input.title)
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || `skill-${Date.now()}`

  const rulesList = Array.isArray(input.rules) && input.rules.length > 0
    ? input.rules
    : (input.content || '')
        .split('\n')
        .filter((line) => line.trim().startsWith('- '))
        .map((line) => line.trim().slice(2).trim())
  const rawContent = input.content?.trim()
    || (rulesList.length > 0 ? rulesList.map((r) => `- ${r}`).join('\n') : input.title.trim())

  const fallbackSkill: CodeSkill = {
    id: slug,
    title: input.title.trim(),
    category: input.category || 'self-installed',
    languages: input.languages && input.languages.length > 0 ? input.languages : ['multi-system'],
    projectTypes: input.projectTypes || [],
    triggers: input.triggers && input.triggers.length > 0
      ? input.triggers
      : slug.split('-').filter((w) => w.length >= 3),
    source: input.source || 'self_installed',
    summary: input.summary || rawContent.split('\n').find((l) => l.trim() && !l.trim().startsWith('#'))?.slice(0, 180) || input.title,
    content: rawContent.startsWith('#') ? rawContent : `# Skill: ${input.title.trim()}\n\n${rawContent}`,
    rules: rulesList,
    installedAt: Math.floor(Date.now() / 1000),
    usageCount: 1,
    path: `.aurora/skills/${slug}.md`,
  }

  saveLocalSelfInstalledSkill(fallbackSkill)

  try {
    if (typeof fetch !== 'undefined') {
      const response = await fetch('/api/code/skills/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: slug,
          title: fallbackSkill.title,
          category: fallbackSkill.category,
          languages: fallbackSkill.languages,
          projectTypes: fallbackSkill.projectTypes,
          triggers: fallbackSkill.triggers,
          summary: fallbackSkill.summary,
          content: fallbackSkill.content,
          rules: fallbackSkill.rules,
          source: fallbackSkill.source,
        }),
      })
      if (response.ok) {
        const data = await response.json()
        if (data?.skill) {
          saveLocalSelfInstalledSkill(data.skill as CodeSkill)
          return data.skill as CodeSkill
        }
      }
    }
  } catch {
    // Persisted locally when bridge is not reachable
  }

  return fallbackSkill
}

export async function deleteCodeSkill(skillId: string): Promise<CodeSkill[]> {
  try {
    if (typeof localStorage !== 'undefined') {
      const filtered = loadLocalSelfInstalledSkills().filter((item) => item.id !== skillId)
      localStorage.setItem(LOCAL_STORAGE_SKILLS_KEY, JSON.stringify(filtered))
    }
  } catch {
    // Ignore
  }

  try {
    if (typeof fetch !== 'undefined') {
      const response = await fetch(`/api/code/skills/${encodeURIComponent(skillId)}`, {
        method: 'DELETE',
      })
      if (response.ok) {
        const data = await response.json()
        if (Array.isArray(data?.skills)) {
          return data.skills as CodeSkill[]
        }
      }
    }
  } catch {
    // Ignore
  }
  return fetchInstalledCodeSkills()
}

export async function fetchCodeAgentsDiagnostics(): Promise<CodeAgentsDiagnostics> {
  const skills = await fetchInstalledCodeSkills()
  const fallback: CodeAgentsDiagnostics = {
    ok: true,
    skillsCount: skills.length,
    builtinSkillsCount: skills.filter((s) => s.source === 'builtin').length,
    selfInstalledSkillsCount: skills.filter((s) => s.source !== 'builtin').length,
    officialAgents: [
      { id: 'code', module: 'code', description: 'Ingénieur logiciel polyglotte, architecture et débogage', canCreateSubagents: true, source: 'official' },
      { id: 'system-architect', module: 'code', description: 'Architecture multi-systèmes, contrats IPC/FFI et topologie', canCreateSubagents: true, source: 'official' },
    ],
    dynamicAgents: [],
    codePipelineRoles: resolveActiveSubAgentRolesForIntent(null),
    toolchains: {
      assembly_gas: { available: true, path: '/usr/bin/gcc' },
      c_gcc_clang: { available: true, path: '/usr/bin/gcc' },
      cpp_gpp_clangpp: { available: true, path: '/usr/bin/g++' },
      rust_cargo: { available: true, path: '/usr/bin/cargo' },
      python3: { available: true, path: '/usr/bin/python3' },
      node: { available: true, path: '/usr/bin/node' },
    },
  }

  try {
    if (typeof fetch === 'undefined') return fallback
    const response = await fetch('/api/code/agents-status', {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return fallback
    const data = await response.json()
    if (data?.ok) {
      return data as CodeAgentsDiagnostics
    }
  } catch {
    // Fallback
  }
  return fallback
}

/**
 * Sélectionne déterministement les skills pertinents pour un prompt et une intention,
 * et synthétise/installe automatiquement un nouveau skill si une combinaison polyglotte
 * ou un domaine avancé inédit est demandé.
 */
export function selectAndSynthesizeSkillsSync(
  prompt: string,
  intent: CodeIntent,
  availableSkills: CodeSkill[] = DEFAULT_CODE_SKILLS,
): { activeSkills: CodeSkill[]; synthesizedSkill: CodeSkill | null } {
  const lower = (prompt || '').toLowerCase()
  const reqLangs = intent.languages.map((l) => l.toLowerCase())
  const reqFws = intent.frameworks.map((f) => f.toLowerCase())

  const scored: Array<{ score: number; skill: CodeSkill }> = []
  for (const skill of availableSkills) {
    let score = 0
    if (skill.projectTypes.map((t) => t.toLowerCase()).includes(intent.projectType.toLowerCase())) {
      score += 4
    }
    for (const lang of reqLangs) {
      if (skill.languages.map((l) => l.toLowerCase()).includes(lang)) {
        score += 3
      }
    }
    for (const fw of reqFws) {
      if (skill.triggers.some((t) => t.toLowerCase() === fw)) {
        score += 2
      }
    }
    for (const trigger of skill.triggers) {
      if (trigger && lower.includes(trigger.toLowerCase())) {
        score += 2
      }
    }
    if (skill.id === 'self-organization-execution-protocol' && (intent.complexity === 'complex' || intent.complexity === 'enterprise' || reqLangs.length >= 2)) {
      score += 2
    }
    if (score >= 2) {
      scored.push({ score, skill })
    }
  }

  scored.sort((a, b) => b.score - a.score || a.skill.id.localeCompare(b.skill.id))
  const activeSkills = scored.slice(0, 5).map((item) => item.skill)

  // Synthèse autonome si projet polyglotte (>= 2 langages systèmes/applicatifs distincts)
  const coreLangs = reqLangs.filter((l) => !['html', 'css', 'yaml', 'json', 'markdown'].includes(l))
  let synthesizedSkill: CodeSkill | null = null
  if (coreLangs.length >= 2) {
    const comboKey = [...coreLangs].sort().slice(0, 3).join('-')
    const sid = `polyglot-bridge-${comboKey}`
    const existing = availableSkills.find((s) => s.id === sid)
    if (!existing) {
      const label = coreLangs.slice(0, 3).map((l) => l.toUpperCase()).join(' + ')
      synthesizedSkill = {
        id: sid,
        title: `Pont Multi-Systèmes ${label} (Auto-Installé)`,
        category: 'auto-learned',
        languages: coreLangs,
        projectTypes: [intent.projectType, 'multi_system'],
        triggers: [...coreLangs, 'multi-system', 'ffi', 'ipc'],
        source: 'self_installed',
        summary: `Protocole d interfaçage FFI/IPC, topologie de fichiers et validation croisée pour ${label}.`,
        installedAt: Math.floor(Date.now() / 1000),
        usageCount: 1,
        path: `.aurora/skills/${sid}.md`,
        content: [
          `# Skill: Pont Multi-Systèmes ${label} (Auto-Installé)`,
          '',
          `## Architecture et Interfaçage (${label})`,
          `- Séparer clairement chaque sous-système (${label}) avec des responsabilités et points d entrée explicites.`,
          '- Définir un contrat d interface strict entre les langages (ABI C `extern "C"`, bibliothèque partagée `.so`, ou protocole JSON/CLI via `stdin`/`stdout` avec code de retour vérifié).',
          '- Valider chaque sous-système individuellement dans le sandbox puis exécuter le test d intégration inter-langages.',
        ].join('\n'),
      }
      activeSkills.unshift(synthesizedSkill)
    }
  }

  return { activeSkills: activeSkills.slice(0, 5), synthesizedSkill }
}

/**
 * Acquiert et installe automatiquement les skills requis auprès du bridge (ou en local)
 * avant la phase d'architecture et de génération.
 */
export async function ensureSkillsForIntentAndPrompt(
  prompt: string,
  intent: CodeIntent,
): Promise<{ activeSkills: CodeSkill[]; newlyInstalled: CodeSkill[] }> {
  const currentSkills = await fetchInstalledCodeSkills()
  const { activeSkills, synthesizedSkill } = selectAndSynthesizeSkillsSync(prompt, intent, currentSkills)
  const newlyInstalled: CodeSkill[] = []

  if (synthesizedSkill) {
    saveLocalSelfInstalledSkill(synthesizedSkill)
    newlyInstalled.push(synthesizedSkill)
  }

  try {
    if (typeof fetch !== 'undefined') {
      const response = await fetch('/api/code/skills/auto-acquire', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          projectType: intent.projectType,
          languages: intent.languages,
          frameworks: intent.frameworks,
        }),
      })
      if (response.ok) {
        const data = await response.json()
        if (Array.isArray(data?.activeSkills) && data.activeSkills.length > 0) {
          const serverNew = Array.isArray(data.newlyInstalled) ? (data.newlyInstalled as CodeSkill[]) : []
          for (const item of serverNew) {
            saveLocalSelfInstalledSkill(item)
          }
          return {
            activeSkills: data.activeSkills as CodeSkill[],
            newlyInstalled: serverNew.length > 0 ? serverNew : newlyInstalled,
          }
        }
      }
    }
  } catch {
    // Fallback to local selection
  }

  return { activeSkills, newlyInstalled }
}

/**
 * Après une génération/validation réussie sur un problème complexe ou multi-système,
 * synthétise et persiste un skill d'organisation capitalisant la topologie validée.
 */
export async function learnSkillFromCompletedProject({
  prompt,
  intent,
  files,
  sandboxOk,
  correctionPassesCount,
}: {
  prompt: string
  intent: CodeIntent
  files: CodeFile[]
  sandboxOk: boolean
  correctionPassesCount: number
}): Promise<CodeSkill | null> {
  if (!sandboxOk || files.length < 2) return null

  const isMasterOrComplex =
    intent.projectType === 'multi_system'
    || intent.projectType === 'system_asm'
    || intent.projectType === 'cli_swift'
    || intent.projectType === 'compiler'
    || intent.projectType === 'os_kernel'
    || intent.projectType === 'distributed_system'
    || intent.languages.includes('assembly')
    || intent.languages.includes('swift')
    || intent.languages.length >= 2
    || correctionPassesCount >= 1

  if (!isMasterOrComplex) return null

  const fileNames = files.map((f) => f.name).slice(0, 12)
  const langTag = intent.languages.length > 0 ? intent.languages.slice(0, 3).join('-') : intent.projectType
  const slug = `learned-${intent.projectType.replace(/_/g, '-')}-${langTag}`
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .slice(0, 56)

  const title = `Pattern Validé: ${intent.projectType} (${intent.languages.join(' + ') || 'polyglotte'})`
  const summary = `Organisation validée en sandbox (${files.length} fichiers: ${fileNames.slice(0, 5).join(', ')}) pour ${intent.projectType}.`
  const content = [
    `# Skill: ${title}`,
    '',
    '## Topologie de Fichiers Validée en Sandbox',
    ...fileNames.map((name) => `- \`${name}\``),
    '',
    '## Règles d Organisation Retenues',
    `- Type de projet: \`${intent.projectType}\` | Langages: ${intent.languages.join(', ') || 'auto'}.`,
    `- Ce pattern a passé la validation sandbox${correctionPassesCount > 0 ? ` après ${correctionPassesCount} passe(s) d auto-correction` : ' dès la première passe'}.`,
    '- Conserver cette séparation des points d entrée, manifestes et modules lors des prochaines missions similaires.',
    `Extrait du brief résolu: "${prompt.slice(0, 140).replace(/\s+/g, ' ').trim()}"`,
  ].join('\n')

  return installCodeSkill({
    id: slug,
    title,
    category: 'auto-learned',
    languages: intent.languages,
    projectTypes: [intent.projectType],
    triggers: [...intent.languages, intent.projectType.replace(/_/g, ' ')],
    summary,
    content,
    source: 'self_installed',
  })
}

/**
 * Construit le bloc de prompt injecté dans l'Architecte, le Codeur et l'Auditeur.
 */
export function buildActiveSkillsPromptBlock(skills: CodeSkill[], maxChars = 3200): string {
  if (!skills || skills.length === 0) return ''

  const lines: string[] = [
    '## SKILLS D INGENIERIE ACTIFS (.aurora/skills)',
    'Applique strictement ces protocoles techniques et d organisation pour ce projet :',
    '',
  ]

  for (const skill of skills.slice(0, 4)) {
    lines.push(`### [${skill.id}] ${skill.title} (${skill.source === 'self_installed' ? 'Auto-Installé' : 'Maître'})`)
    lines.push(skill.content.trim())
    lines.push('')
  }

  const block = lines.join('\n')
  return block.length > maxChars ? `${block.slice(0, maxChars)}\n` : block
}

export function resolveActiveSubAgentRolesForIntent(
  intent?: CodeIntent | null,
): CodeAgentRoleStatus[] {
  const langs = (intent?.languages ?? []).map((l) => l.toLowerCase())
  const pt = intent?.projectType ?? 'static_web'
  const hasLowLevel =
    langs.some((l) => ['assembly', 'asm', 'c', 'cpp', 'rust', 'zig', 'swift'].includes(l))
    || ['system_asm', 'system_c', 'system_cpp', 'system_rust', 'os_kernel', 'compiler', 'cli_swift', 'multi_system'].includes(pt)
  const hasHighLevel =
    langs.some((l) => ['python', 'typescript', 'javascript', 'go', 'kotlin', 'java', 'dart', 'html', 'css'].includes(l))
    || pt === 'multi_system'
    || !hasLowLevel

  return [
    {
      id: 'code-architect',
      name: 'Architecte Système & Topologie',
      title: 'Architecte Système',
      role: `Planification ${pt} (${langs.join(' + ') || 'auto'}) & sélection des skills`,
      specialty: `Planification ${pt} (${langs.join(' + ') || 'auto'}), contrats FFI/IPC & acquisition de skills`,
      active: true,
      status: 'ready',
    },
    {
      id: 'code-lowlevel-engineer',
      name: 'Ingénieur Bas Niveau (ASM / Native / Swift / Rust / C)',
      title: 'Ingénieur Bas Niveau',
      role: 'Implémentation des modules natifs, registres/ABI, gestion mémoire et compilation stricte',
      specialty: 'Assembleur x86_64/ARM64, Swift, Rust, C/C++, ABI System V & sûreté mémoire',
      active: hasLowLevel,
      status: hasLowLevel ? 'active' : 'ready',
    },
    {
      id: 'code-app-engineer',
      name: 'Ingénieur Applicatif & Orchestration (Python / TS / Go)',
      title: 'Ingénieur Applicatif',
      role: 'Logique métier, interfaces, ponts IPC/FFI et intégration inter-modules',
      specialty: 'Orchestration Python/TypeScript/Go, ponts FFI/IPC, APIs & interfaces',
      active: hasHighLevel,
      status: hasHighLevel ? 'active' : 'ready',
    },
    {
      id: 'code-auditor-verifier',
      name: 'Auditeur Impitoyable & Juge Sandbox',
      title: 'Auditeur Sandbox',
      role: 'Validation multi-systèmes dans le sandbox isolé et boucle d auto-correction sans régression',
      specialty: 'Exécution sandbox multi-système, vérification ABI/AST & auto-correction',
      active: true,
      status: 'ready',
    },
  ]
}

