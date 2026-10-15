import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Wrench,
} from 'lucide-react'
import type { CodeIntent } from '../services/codeIntent.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import {
  type CodeAgentDiagnostics,
  type CodeSkillEntry,
  deleteCodeSkill,
  ensureSkillsForIntentAndPrompt,
  fetchCodeAgentsDiagnostics,
  fetchInstalledCodeSkills,
  installCodeSkill,
  resolveActiveSubAgentRolesForIntent,
  selectAndSynthesizeSkillsSync,
} from '../services/codeSkillsRegistry.ts'
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore.ts'

type CodeSkillsAndAgentsPanelProps = {
  prompt: string
  intent: CodeIntent | null
  isGenerating: boolean
  onSelectBlueprintPrompt: (blueprintPrompt: string) => void
}

const MASTER_BLUEPRINTS: Array<{
  id: string
  label: string
  badge: string
  prompt: string
}> = [
  {
    id: 'asm-x86-abi',
    label: 'Assembleur x86_64 + Harnais ABI',
    badge: 'ASM x86_64',
    prompt:
      'Conçois un projet Assembleur x86_64 NASM/GAS modulaire (System V AMD64 ABI) comprenant une routine vectorielle et arithmétique rapide (somme pondérée 64 bits, détection de débordement et hachage FNV-1a en registres rdi/rsi/rdx -> rax), un Makefile complet, et un harnais Python de vérification ABI et de test déterministe.',
  },
  {
    id: 'swift-actors-cli',
    label: 'Swift 6 Acteurs & Système',
    badge: 'SwiftPM',
    prompt:
      'Crée un projet Swift Package Manager (Package.swift) complet avec concurrence structurée (async/await, actor TaskCoordinator, Sendable), un moteur d ordonnancement de tâches résilient avec priorité et télémétrie, une interface CLI typée dans Sources/App/main.swift et des tests unitaires complets dans Tests/AppTests/AppTests.swift.',
  },
  {
    id: 'multi-system-polyglot',
    label: 'Multi-Système (C/ASM + Python IPC)',
    badge: 'Polyglotte',
    prompt:
      'Architecture multi-système polyglotte combinant : (1) un contrat formel dans architecture/contracts.json, (2) un noyau natif bas niveau en C et Assembleur x86_64 pour le traitement haute performance de trames télémétriques, (3) un orchestrateur Python complet avec pont FFI/IPC et repli pur déterministe, et (4) une suite de tests de bout en bout vérifiant la parité entre le noyau natif et l orchestrateur.',
  },
]

export default function CodeSkillsAndAgentsPanel({
  prompt,
  intent,
  isGenerating,
  onSelectBlueprintPrompt,
}: CodeSkillsAndAgentsPanelProps) {
  const [skills, setSkills] = useState<CodeSkillEntry[]>([])
  const [diagnostics, setDiagnostics] = useState<CodeAgentDiagnostics | null>(null)
  const [expanded, setExpanded] = useState<boolean>(true)
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null)
  const [showNewSkillForm, setShowNewSkillForm] = useState<boolean>(false)
  const [newSkillTitle, setNewSkillTitle] = useState<string>('')
  const [newSkillLangs, setNewSkillLangs] = useState<string>('assembly, swift, rust, python')
  const [newSkillRules, setNewSkillRules] = useState<string>('')
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [isSyncing, setIsSyncing] = useState<boolean>(false)

  const codeAgentRuntime = useAgentRuntimeStore((state) => state.agents.code)

  const effectiveIntent = useMemo(() => {
    if (intent) return intent
    if (prompt.trim().length > 3) {
      try {
        return classifyCodeIntent(prompt)
      } catch {
        return null
      }
    }
    return null
  }, [intent, prompt])

  const activeSkillsPreview = useMemo(() => {
    if (!effectiveIntent) return []
    return selectAndSynthesizeSkillsSync(prompt, effectiveIntent).activeSkills
  }, [effectiveIntent, prompt])

  const activeSkillIds = useMemo(
    () => new Set(activeSkillsPreview.map((s) => s.id)),
    [activeSkillsPreview],
  )

  const subAgentRoles = useMemo(
    () => resolveActiveSubAgentRolesForIntent(effectiveIntent),
    [effectiveIntent],
  )

  const loadSkillsAndDiagnostics = useCallback(async () => {
    setIsSyncing(true)
    try {
      const [loadedSkills, loadedDiag] = await Promise.all([
        fetchInstalledCodeSkills(),
        fetchCodeAgentsDiagnostics(),
      ])
      setSkills(loadedSkills)
      if (loadedDiag) setDiagnostics(loadedDiag)
    } finally {
      setIsSyncing(false)
    }
  }, [])

  useEffect(() => {
    void loadSkillsAndDiagnostics()
  }, [loadSkillsAndDiagnostics])

  const handleAutoAcquireForBrief = async () => {
    const targetPrompt = prompt.trim() || 'Architecture multi-système polyglotte Assembleur Swift Rust Python'
    const targetIntent = effectiveIntent ?? classifyCodeIntent(targetPrompt)
    setIsSyncing(true)
    setStatusMessage(null)
    try {
      const { activeSkills, newlyInstalled } = await ensureSkillsForIntentAndPrompt(
        targetPrompt,
        targetIntent,
      )
      const refreshed = await fetchInstalledCodeSkills()
      setSkills(refreshed)
      if (newlyInstalled.length > 0) {
        setStatusMessage(
          `${newlyInstalled.length} nouveau(x) skill(s) auto-installé(s) : ${newlyInstalled.map((s) => s.title).join(', ')}`,
        )
      } else {
        setStatusMessage(
          `${activeSkills.length} skill(s) vérifié(s) et prêt(s) pour ce brief (${targetIntent.projectType}).`,
        )
      }
    } finally {
      setIsSyncing(false)
    }
  }

  const handleInstallCustomSkill = async () => {
    if (!newSkillTitle.trim() || !newSkillRules.trim()) return
    setIsSyncing(true)
    setStatusMessage(null)
    try {
      const langs = newSkillLangs
        .split(',')
        .map((l) => l.trim().toLowerCase())
        .filter(Boolean)
      const rules = newSkillRules
        .split('\n')
        .map((r) => r.replace(/^[-*]\s*/, '').trim())
        .filter(Boolean)
      const created = await installCodeSkill({
        title: newSkillTitle.trim(),
        category: 'custom',
        languages: langs.length > 0 ? langs : ['*'],
        projectTypes: ['*'],
        summary: `Skill personnalisé : ${newSkillTitle.trim()}`,
        rules,
        source: 'user-installed',
      })
      if (created) {
        const refreshed = await fetchInstalledCodeSkills()
        setSkills(refreshed)
        setNewSkillTitle('')
        setNewSkillRules('')
        setShowNewSkillForm(false)
        setSelectedSkillId(created.id)
        setStatusMessage(`Skill "${created.title}" installé dans .aurora/skills/${created.id}.md`)
      }
    } finally {
      setIsSyncing(false)
    }
  }

  const handleDeleteSkill = async (skillId: string) => {
    setIsSyncing(true)
    try {
      await deleteCodeSkill(skillId)
      const refreshed = await fetchInstalledCodeSkills()
      setSkills(refreshed)
      if (selectedSkillId === skillId) setSelectedSkillId(null)
      setStatusMessage(`Skill ${skillId} supprimé.`)
    } finally {
      setIsSyncing(false)
    }
  }

  const selectedSkill = useMemo(
    () => skills.find((s) => s.id === selectedSkillId) ?? null,
    [skills, selectedSkillId],
  )

  return (
    <div
      className="rounded-[1.5rem] p-4 backdrop-blur-xl transition-all"
      style={{
        border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 14%, transparent))',
        background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 76%, transparent))',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="flex flex-1 items-center justify-between text-left"
        >
          <div className="flex items-center gap-2">
            <Cpu size={14} className="text-aurora-orange" />
            <span
              className="text-[10px] uppercase tracking-[0.24em] font-semibold"
              style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 65%, transparent))' }}
            >
              Escouade Agents & Skills ({skills.length})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
              {activeSkillsPreview.length} actif(s)
            </span>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </button>
        <button
          type="button"
          onClick={() => void loadSkillsAndDiagnostics()}
          title="Rafraîchir l'état des agents et skills (.aurora/skills)"
          className="rounded-lg p-1.5 transition-colors hover:bg-black/5"
        >
          <RefreshCw size={12} className={isSyncing ? 'animate-spin' : ''} />
        </button>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3">
          {/* Sub-agents live status */}
          <div
            className="rounded-2xl p-3 space-y-2"
            style={{
              border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 10%, transparent))',
              background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 65%, transparent))',
            }}
          >
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-emerald-600" />
                Sous-Agents du Pipeline Code
              </span>
              <span className="text-[10px] opacity-75">
                État : {isGenerating ? codeAgentRuntime?.state || 'working' : 'prêt'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-1.5">
              {subAgentRoles.map((role) => (
                <div
                  key={role.id}
                  className="rounded-xl px-2.5 py-2 text-[11px] transition-all"
                  style={{
                    border: role.active
                      ? '1px solid color-mix(in srgb, var(--ft-accent, #e63412) 42%, transparent)'
                      : '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 10%, transparent))',
                    background: role.active
                      ? 'color-mix(in srgb, var(--ft-accent-2, #f78324) 12%, transparent)'
                      : 'transparent',
                  }}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-semibold truncate">{role.title}</span>
                    <span
                      className={`h-2 w-2 rounded-full ${
                        role.active ? 'bg-emerald-500' : 'bg-stone-400/50'
                      }`}
                    />
                  </div>
                  <p className="mt-0.5 text-[10px] opacity-75 line-clamp-2 leading-snug">
                    {role.specialty}
                  </p>
                </div>
              ))}
            </div>

            {codeAgentRuntime?.detail && (
              <div className="rounded-xl bg-black/5 px-2.5 py-1.5 text-[10px] font-mono truncate">
                {codeAgentRuntime.detail}
              </div>
            )}

            {/* Host Toolchains */}
            {diagnostics?.toolchains && (
              <div className="flex flex-wrap items-center gap-1 pt-1">
                <span className="text-[10px] opacity-70 mr-1 flex items-center gap-1">
                  <Terminal size={10} /> Compilateurs :
                </span>
                {Object.entries(diagnostics.toolchains).map(([name, info]) => {
                  const available = typeof info === 'boolean' ? info : Boolean(info?.available)
                  const path = typeof info === 'object' && info !== null ? info.path : null
                  return (
                    <span
                      key={name}
                      title={path || `${name} (vérificateur AST/ABI de secours si absent)`}
                      className={`rounded-md px-1.5 py-0.5 text-[9px] font-mono ${
                        available
                          ? 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300'
                          : 'bg-amber-500/15 text-amber-800 dark:text-amber-300'
                      }`}
                    >
                      {name}:{available ? 'natif' : 'sandbox-ast'}
                    </span>
                  )
                })}
              </div>
            )}
          </div>

          {/* Polyglot & Master Language Blueprints */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] opacity-75">
              <span className="flex items-center gap-1">
                <Layers size={11} /> Modèles Systèmes & Langages Maîtres
              </span>
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {MASTER_BLUEPRINTS.map((bp) => (
                <button
                  key={bp.id}
                  type="button"
                  onClick={() => onSelectBlueprintPrompt(bp.prompt)}
                  className="flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-xs transition-all hover:scale-[1.01]"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
                    background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 68%, transparent))',
                  }}
                >
                  <span className="font-medium truncate">{bp.label}</span>
                  <span className="shrink-0 rounded-lg bg-amber-500/20 px-2 py-0.5 text-[10px] font-mono font-semibold">
                    {bp.badge}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Self-Installable Skills List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] uppercase tracking-[0.2em] font-semibold opacity-75 flex items-center gap-1">
                <Wrench size={11} /> Skills Auto-Installables (.aurora/skills)
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => void handleAutoAcquireForBrief()}
                  disabled={isSyncing}
                  className="flex items-center gap-1 rounded-lg bg-amber-500/20 px-2 py-1 text-[10px] font-semibold transition-colors hover:bg-amber-500/30"
                  title="Analyse le brief et auto-installe les skills manquants"
                >
                  <Sparkles size={11} />
                  <span>Auto-acquérir</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewSkillForm((prev) => !prev)}
                  className="flex items-center gap-1 rounded-lg bg-black/10 px-2 py-1 text-[10px] font-semibold transition-colors hover:bg-black/15"
                >
                  <Plus size={11} />
                  <span>Installer</span>
                </button>
              </div>
            </div>

            {statusMessage && (
              <div className="rounded-xl bg-emerald-500/15 px-3 py-2 text-[11px] text-emerald-900 dark:text-emerald-200 flex items-center gap-1.5">
                <CheckCircle2 size={13} className="shrink-0" />
                <span>{statusMessage}</span>
              </div>
            )}

            {showNewSkillForm && (
              <div
                className="rounded-2xl p-3 space-y-2"
                style={{
                  border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 16%, transparent))',
                  background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 80%, transparent))',
                }}
              >
                <p className="text-[11px] font-semibold">Installer un nouveau Skill persistant</p>
                <input
                  type="text"
                  value={newSkillTitle}
                  onChange={(e) => setNewSkillTitle(e.target.value)}
                  placeholder="Titre (ex: SIMD AVX-512 & Intrinsics C/ASM)"
                  className="w-full rounded-xl px-2.5 py-1.5 text-xs outline-none"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                    background: 'var(--bg-input, #fff)',
                  }}
                />
                <input
                  type="text"
                  value={newSkillLangs}
                  onChange={(e) => setNewSkillLangs(e.target.value)}
                  placeholder="Langages (ex: assembly, c, swift, python)"
                  className="w-full rounded-xl px-2.5 py-1.5 text-xs outline-none"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                    background: 'var(--bg-input, #fff)',
                  }}
                />
                <textarea
                  rows={3}
                  value={newSkillRules}
                  onChange={(e) => setNewSkillRules(e.target.value)}
                  placeholder="Règles d'ingénierie (une par ligne)..."
                  className="w-full rounded-xl px-2.5 py-1.5 text-xs outline-none resize-none"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                    background: 'var(--bg-input, #fff)',
                  }}
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setShowNewSkillForm(false)}
                    className="rounded-lg px-2.5 py-1 text-[11px] opacity-75"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleInstallCustomSkill()}
                    className="rounded-lg bg-emerald-600 px-3 py-1 text-[11px] font-semibold text-white"
                  >
                    Enregistrer dans .aurora/skills
                  </button>
                </div>
              </div>
            )}

            <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
              {skills.map((skill) => {
                const isActive = activeSkillIds.has(skill.id)
                const isSelected = selectedSkillId === skill.id
                return (
                  <div
                    key={skill.id}
                    onClick={() => setSelectedSkillId(isSelected ? null : skill.id)}
                    className="cursor-pointer rounded-xl px-2.5 py-2 text-xs transition-all"
                    style={{
                      border: isActive
                        ? '1px solid color-mix(in srgb, var(--ft-accent, #e63412) 45%, transparent)'
                        : '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 10%, transparent))',
                      background: isSelected
                        ? 'color-mix(in srgb, var(--ft-accent-2, #f78324) 15%, transparent)'
                        : 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 60%, transparent))',
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium truncate">{skill.title}</span>
                      <div className="flex items-center gap-1 shrink-0">
                        {isActive && (
                          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-800 dark:text-emerald-300">
                            Actif
                          </span>
                        )}
                        <span className="rounded bg-black/10 px-1.5 py-0.5 text-[9px] font-mono">
                          {skill.source === 'builtin' ? 'Maître' : 'Auto-Installé'}
                        </span>
                        {skill.source !== 'builtin' && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              void handleDeleteSkill(skill.id)
                            }}
                            title="Supprimer ce skill"
                            className="p-0.5 text-red-500 hover:bg-red-500/10 rounded"
                          >
                            <Trash2 size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                    {isSelected && (
                      <div className="mt-2 border-t border-black/10 pt-2 space-y-1 text-[11px]">
                        <p className="opacity-80">{skill.summary}</p>
                        <ul className="list-disc pl-4 space-y-0.5 opacity-90">
                          {(skill.rules && skill.rules.length > 0
                            ? skill.rules
                            : (skill.content || '')
                                .split('\n')
                                .map((l) => l.trim())
                                .filter((l) => l.startsWith('- ') || /^\d+\.\s/.test(l))
                                .map((l) => l.replace(/^(-|\d+\.)\s*/, ''))
                          ).map((rule: string, idx: number) => (
                            <li key={idx}>{rule}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
