import { lazy, Suspense, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, Award, BookOpen, Check, CheckCircle2, ChevronDown, ChevronUp, Clipboard, Copy, Dice5, Download, Flame,
  HelpCircle, Lightbulb, Loader2, MessageSquare, Play, RefreshCw, Send, Shield, ShieldCheck, Sparkles,
  Target, Terminal, TerminalSquare, Trash2, Trophy, Upload, Wand2, X, Zap,
} from 'lucide-react'
import AuroraMascot from '../components/generationFx/mascots.tsx'
import MarkdownPro from '../components/MarkdownPro.tsx'
import Sparkline from '../components/Sparkline.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { useCyberViewLogic } from '../hooks/useCyberViewLogic.ts'
import { ollamaGenerate } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'
import { generateCyberAdvisory } from '../services/cyber/advisory.ts'

const WarRoomToolBench = lazy(() => import('./cyber/WarRoomLab'))
const AutonomousInvestigatorToolBench = lazy(() => import('./cyber/AutonomousInvestigatorLab'))
const DynamicZeroDayToolBench = lazy(() => import('./cyber/DynamicZeroDayLab'))
const SymbolicExecutionToolBench = lazy(() => import('./cyber/SymbolicExecutionLab'))
const BinaryDisassemblyToolBench = lazy(() => import('./cyber/BinaryDisassemblyLab'))
const EbpfKernelToolBench = lazy(() => import('./cyber/EbpfKernelLab'))
const SoarPlaybookToolBench = lazy(() => import('./cyber/SoarPlaybookLab'))
const ZeroDayToolBench = lazy(() => import('./cyber/ZeroDayLab'))
const AttackGraphToolBench = lazy(() => import('./cyber/AttackGraphLab'))
const DeepReasoningToolBench = lazy(() => import('./cyber/DeepReasoningLab'))
const WebAuditorToolBench = lazy(() => import('./cyber/WebAuditorLab'))
const NetworkToolBench = lazy(() => import('./cyber/NetworkLab'))
const ForensicsToolBench = lazy(() => import('./cyber/ForensicsLab'))
const WebSecToolBench = lazy(() => import('./cyber/WebSecLab'))
const ThreatIntelToolBench = lazy(() => import('./cyber/ThreatIntelLab'))

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'
const FG = '#E6EAF5'
const DIM = '#8B93A7'
const MUTE = '#5A6377'

const glass: CSSProperties = {
  background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
  border: '1px solid rgba(255,255,255,.09)',
  borderRadius: 18,
  backdropFilter: 'blur(18px)',
}
const monoLabel: CSSProperties = {
  fontFamily: "'Cascadia Code',Consolas,monospace",
  fontSize: 10,
  letterSpacing: '.2em',
  textTransform: 'uppercase',
  color: DIM,
}
const mono: CSSProperties = { fontFamily: "'Cascadia Code',Consolas,monospace" }
const inputBase: CSSProperties = {
  background: 'rgba(10,15,30,.6)',
  border: '1px solid rgba(255,255,255,.12)',
  borderRadius: 11,
  color: FG,
  fontFamily: 'inherit',
  outline: 'none',
}
const gradNum: CSSProperties = {
  background: `linear-gradient(115deg, ${ACCENT} 15%, #FFD9E1 60%, #FFFFFF 95%)`,
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
}
const pillMeta: CSSProperties = {
  padding: '3px 9px',
  borderRadius: 999,
  border: '1px solid rgba(255,255,255,.1)',
  background: 'rgba(255,255,255,.03)',
}

const CYBER_REQUEST_PRESETS = [
  {
    label: 'War Room Red/Blue',
    stance: 'defense' as const,
    text: "Engage une simulation War Room autonome : confrontation Red Team vs Blue Team, telemetrie temps reel, generation de regles Sigma/YARA, isolation eBPF et containment.",
  },
  {
    label: 'Entraînement 0-Day & Fuzz',
    stance: 'offense' as const,
    text: "Simule la decouverte et la remediation d'une faille 0-day (UAF / Heap BOF / Deserialization) avec fuzzing mutatif, dissection de memoire et validation de correctif.",
  },
  {
    label: 'Graphe Attaque & Pivots',
    stance: 'offense' as const,
    text: "Analyse le graphe d'attaque systemique : cartographie des dependances reseau, modelisation des chemins de pivot vers les actifs critiques et calcul du blast radius.",
  },
  {
    label: 'Raisonnement IA Poussé',
    stance: 'defense' as const,
    text: "Effectue une dissection cognitive approfondie : modelisation de menace, analyse dialectique attaque/defense, cause racine et playbook de remediation definitive.",
  },
  {
    label: 'Audit web autorise',
    stance: 'offense' as const,
    text: "Prepare un audit web autorise sur mon application : perimetre, recon read-only, surface d'attaque, hypotheses OWASP, outils a verifier, preuves a collecter et correctifs.",
  },
  {
    label: 'Incident forensic',
    stance: 'defense' as const,
    text: "Analyse ces logs et artefacts comme un incident forensic : timeline, extraction d'indicateurs IOCs, hypotheses d'attaque et rapport d'incident.",
  },
]

const CYBER_TOOL_GROUPS = [
  { name: 'War Room IA', tools: 'Attaque vs Defense autonome, telemetrie live, confinement eBPF, regles Sigma/YARA', bench: 'warroom' as const, highlight: true },
  { name: 'Enquêteur IA', tools: 'Investigation autonome multi-sources, Threat Intel CVE/EPSS, deduction de causes racines', bench: 'investigator' as const, highlight: true },
  { name: '0-Day Dynamique', tools: 'Deduction heuristique de failles inedites sans catalogue, invariants de securite', bench: 'dynamic0day' as const, highlight: true },
  { name: 'Solveur SMT', tools: 'Verification formelle Z3, exploration symbolique, preuves de crash mathématiques', bench: 'symbolic' as const, highlight: true },
  { name: 'Désassembleur', tools: 'x86_64/ARM64, blocs CFG, ROP Gadgets, analyse d\'entropie des sections', bench: 'binary' as const, highlight: true },
  { name: 'Noyau eBPF / LSM', tools: 'Sondes Ring 0, hooks de securite LSM anti-shell, filtrage réseau XDP', bench: 'ebpf' as const, highlight: true },
  { name: 'Riposte SOAR', tools: 'Playbooks automatisés, enrichissement IOC, mitigation active & post-mortem', bench: 'soar' as const, highlight: true },
  { name: 'Lab 0-Day & Fuzz', tools: 'Fuzzing mutatif, dissection memoire, UAF, Heap/Stack ROP, mitigations ASLR/Canary', bench: 'zeroday' as const, highlight: true },
  { name: 'Graphe Attaque', tools: 'Cartographie des flux, chemins de pivot, calcul Blast Radius, chokepoints', bench: 'attackgraph' as const, highlight: true },
  { name: 'Raisonnement IA', tools: 'Analyse dialectique, cause racine, modelisation de menaces & playbooks', bench: 'deepreasoning' as const, highlight: true },
  { name: 'Audit Web & DoS', tools: 'Audit endpoint passif, analyse en-tetes HTTP, resilience DoS, export output/cyber', bench: 'webaudit' as const, highlight: true },
  { name: 'Recon Reseau', tools: 'DNS, TLS, WHOIS, headers HTTP, scan local/RFC1918, PCAP demo', bench: 'network' as const },
  { name: 'Web Security', tools: 'OWASP, SSRF/JWT/XSS/SQLi en lab, headers, remediations', bench: 'web' as const },
  { name: 'Threat Intel', tools: 'MITRE ATT&CK, CVE/CWE, OSINT, parseur d\'IOCs temps reel', bench: 'intel' as const },
  { name: 'Forensic', tools: 'Magic bytes, hash fichier, strings, EXIF, entropy, scan memoire, hex', bench: 'forensics' as const },
  { name: 'Auto-Config', tools: 'nmap/httpx/nuclei/trivy/osquery/etc. proposes selon mission', bench: 'strategy' as const },
]

type ToolBenchId = 'warroom' | 'investigator' | 'dynamic0day' | 'symbolic' | 'binary' | 'ebpf' | 'soar' | 'zeroday' | 'attackgraph' | 'deepreasoning' | 'webaudit' | 'network' | 'forensics' | 'web' | 'intel'

function toneColor(t?: string): string {
  if (t === 'xp' || t === 'ok') return OK
  if (t === 'attack') return ACCENT
  if (t === 'defense') return BLUE
  if (t === 'warn') return WARN
  return DIM
}
function verdictColor(v?: string): string {
  if (v === 'correct') return OK
  if (v === 'partial') return WARN
  if (v === 'incorrect') return ACCENT
  return DIM
}
function fmtDur(ms: number): string {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function Dot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span style={{
      width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0,
      boxShadow: `0 0 10px ${color}`,
      animation: pulse ? 'cyberPulse 1.6s ease-in-out infinite' : undefined,
    }} />
  )
}

function Label({ children, dot, style }: { children: ReactNode; dot?: string; style?: CSSProperties }) {
  return (
    <div style={{ ...monoLabel, display: 'flex', alignItems: 'center', gap: 8, ...style }}>
      {dot && <Dot color={dot} pulse />}
      {children}
    </div>
  )
}

function Card({ children, style, accent, className }: { children: ReactNode; style?: CSSProperties; accent?: boolean; className?: string }) {
  return (
    <div className={className} style={{
      ...glass,
      padding: 16,
      ...(accent ? { border: `1px solid ${ACCENT}44`, boxShadow: `0 0 24px ${ACCENT}18` } : null),
      ...style,
    }}>
      {children}
    </div>
  )
}

function Btn({ children, onClick, variant = 'ghost', disabled, title, style, block }: {
  children: ReactNode; onClick?: () => void; variant?: 'primary' | 'ghost' | 'danger'
  disabled?: boolean; title?: string; style?: CSSProperties; block?: boolean
}) {
  const [hover, setHover] = useState(false)
  const base: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
    fontFamily: 'inherit', fontSize: 12.5, cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1, transition: 'all .25s cubic-bezier(.22,1,.36,1)',
    width: block ? '100%' : undefined, whiteSpace: 'nowrap',
  }
  const skin: CSSProperties = variant === 'primary'
    ? {
        background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`, color: '#0A0F1E',
        fontWeight: 750, borderRadius: 12, border: 'none', padding: '10px 18px',
        boxShadow: `0 6px 24px ${ACCENT}66`,
        transform: hover && !disabled ? 'translateY(-2px)' : 'none',
      }
    : variant === 'danger'
    ? {
        background: hover && !disabled ? `${ACCENT}22` : 'rgba(255,255,255,.03)',
        color: ACCENT, border: `1px solid ${ACCENT}55`, borderRadius: 11, padding: '8px 14px',
      }
    : {
        background: hover && !disabled ? 'rgba(255,255,255,.06)' : 'rgba(255,255,255,.03)',
        color: DIM, border: '1px solid rgba(255,255,255,.14)', borderRadius: 11, padding: '8px 14px',
      }
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      className={variant === 'primary' ? 'cyber-btn-primary' : 'cyber-btn-ghost'}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...skin, ...style }}>
      {children}
    </button>
  )
}

function Chip({ children, active, tone, title, onClick }: {
  children: ReactNode; active?: boolean; tone?: string; title?: string; onClick?: () => void
}) {
  const c = tone || ACCENT
  const style: CSSProperties = {
    fontSize: 11, padding: '5px 11px', borderRadius: 999, whiteSpace: 'nowrap',
    cursor: onClick ? 'pointer' : 'default',
    display: 'inline-flex', alignItems: 'center', gap: 6,
    border: `1px solid ${active ? c : 'rgba(255,255,255,.1)'}`,
    background: active ? c : 'rgba(255,255,255,.03)',
    color: active ? '#0A0F1E' : DIM, fontWeight: active ? 700 : 500,
    fontFamily: 'inherit',
  }
  if (onClick) {
    return (
      <button type="button" className="cyber-chip" title={title} onClick={onClick} style={style}>
        {children}
      </button>
    )
  }
  return (
    <span title={title} style={style}>
      {children}
    </span>
  )
}

function Diff({ n, on }: { n: number; on?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
      {[1, 2, 3].map((i) => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: '50%',
          background: i <= n ? (on ? '#0A0F1E' : ACCENT) : 'rgba(255,255,255,.2)',
        }} />
      ))}
    </span>
  )
}

export default function AuroraV4CyberView() {
  const C = useCyberViewLogic()
  const [helpOpen, setHelpOpen] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const [briefingCopied, setBriefingCopied] = useState(false)
  const [activeToolBench, setActiveToolBench] = useState<ToolBenchId | null>(null)
  const logEndRef = useRef<HTMLDivElement | null>(null)
  const [directRunning, setDirectRunning] = useState(false)
  const [directSteps, setDirectSteps] = useState<Array<{ id: string; label: string; status: 'pending' | 'running' | 'done' | 'error'; detail?: string; durationMs?: number }>>([])
  const [directLogs, setDirectLogs] = useState<Array<{ id: string; time: string; text: string; tone?: 'info' | 'warn' | 'ok' | 'accent' }>>([])
  const [isConsoleOpen, setIsConsoleOpen] = useState(false)
  const [directResult, setDirectResult] = useState<string | null>(null)
  const consoleEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (isConsoleOpen) {
      consoleEndRef.current?.scrollIntoView({ block: 'nearest' })
    }
  }, [directLogs, isConsoleOpen])

  const [cyberMode, setCyberMode] = useState<'chat' | 'lab'>('chat')
  const [chatMessages, setChatMessages] = useState<Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    time: string
    target?: string
    steps?: Array<{ id: string; label: string; status: 'pending' | 'running' | 'done' | 'error'; detail?: string; durationMs?: number }>
  }>>(() => [
    {
      id: 'welcome',
      role: 'assistant',
      content: `### 🛡️ Aurora Cyber Engine · Espace d'Audit & Ingénierie
Bienvenue dans votre environnement d'analyse de sécurité et d'audit technique.
- **💬 Mode Discussion & Audit** : Posez des questions techniques, demandez des analyses d'invariants, des audits d'API/Web ou des revues de code sans restrictions artificielles.
- **⚒️ Mode Forge Laboratoire** : Basculez dans l'onglet **Forger son Laboratoire** pour créer et manipuler des environnements sandboxés et résoudre des épreuves interactives.`,
      time: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const chatBottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, directRunning])

  function extractTargetAndType(brief: string, scope: string): { target: string; targetType: string; isWeb: boolean } {
    const combined = `${scope} ${brief}`
    const urlMatch = combined.match(/https?:\/\/[^\s"'<>]+/i)
    if (urlMatch) {
      return { target: urlMatch[0], targetType: 'Cible Web & Réseau Distant (URL)', isWeb: true }
    }
    const domainMatch = combined.match(/\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|fr|org|net|io|dev|app|ai|tech|cloud|edu|gov|co|local|internal|xyz|eu|ch|ca|de|uk)\b(?::\d+)?(?:\/[^\s]*)?/i)
    if (domainMatch) {
      const full = domainMatch[0].startsWith('http') ? domainMatch[0] : `https://${domainMatch[0]}`
      return { target: full, targetType: 'Cible Web & Domaine Distant (FQDN)', isWeb: true }
    }
    const ipMatch = combined.match(/\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b/)
    if (ipMatch) {
      return { target: ipMatch[0], targetType: 'Hôte Réseau / Adresse IP', isWeb: true }
    }
    if (scope.trim()) {
      const isWebScope = /https?:\/\/|www\.|\.com|\.fr|\.org|\.io|\.net/i.test(scope)
      return { target: scope.trim(), targetType: isWebScope ? 'Cible Web Distante' : 'Système / Dépôt Local', isWeb: isWebScope }
    }
    const lowerBrief = brief.toLowerCase()
    if (lowerBrief.includes('site') || lowerBrief.includes('web') || lowerBrief.includes('api') || lowerBrief.includes('url') || lowerBrief.includes('endpoint') || lowerBrief.includes('http') || lowerBrief.includes('domaine') || lowerBrief.includes('serveur distant') || lowerBrief.includes('portail')) {
      return { target: 'Service Web & API en ligne', targetType: 'Cible Applicative Web', isWeb: true }
    }
    return { target: 'Environnement Local / Code Source', targetType: 'Environnement Local', isWeb: false }
  }

  const handleDirectExecute = async () => {
    if (!C.customBrief.trim() || directRunning) return
    const inputContent = C.customBrief.trim()
    setDirectRunning(true)
    setDirectResult(null)
    const startTime = Date.now()
    const nowStamp = () => new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    const { target, targetType, isWeb } = extractTargetAndType(inputContent, C.scopeTarget)

    const userMsg = {
      id: `u_${Date.now()}`,
      role: 'user' as const,
      content: inputContent,
      time: nowStamp(),
      target: target,
    }
    setChatMessages((prev) => [...prev, userMsg])
    C.setCustomBrief('')

    const steps = [
      { id: 's1', label: '1. Lecture de la demande', status: 'done' as const, detail: `Cible mentionnée : ${target} ; accès non vérifié` },
      { id: 's2', label: '2. Analyse du contexte fourni', status: 'running' as const, detail: 'Hypothèses et contrôles à préparer' },
      { id: 's3', label: '3. Synthèse et recommandations', status: 'pending' as const, detail: 'Restitution de l’analyse' },
    ]
    setDirectSteps(steps)
    setDirectLogs([
      { id: 'l1', time: nowStamp(), text: `[ANALYSE] Demande reçue : "${inputContent.slice(0, 80)}"`, tone: 'accent' },
      { id: 'l2', time: nowStamp(), text: `[CONTEXTE] Type déduit du texte : ${targetType} | Cible mentionnée : ${target}`, tone: 'info' },
      { id: 'l3', time: nowStamp(), text: '[PREUVES] Analyse du texte fourni ; aucune collecte ni vérification de la cible effectuée dans cette discussion.', tone: 'info' },
    ])

    try {
      const { mainModel } = useAppStore.getState()
      const effectiveModel = (mainModel && mainModel.trim()) ? mainModel : 'qwen-cyber'
      const advisory = await generateCyberAdvisory({
        model: effectiveModel,
        request: inputContent,
        target,
        targetType,
        isWeb,
        stance: C.stance,
      }, ollamaGenerate)
      const rawText = `Analyse fondée sur la demande fournie. Cible non vérifiée par des outils.\n\n${advisory.content}`
      setDirectResult(rawText)

      const finishedSteps = steps.map((s, i) => i === 1 ? { ...s, status: 'done' as const, durationMs: Date.now() - startTime } : { ...s, status: 'done' as const })
      setDirectSteps(finishedSteps)

      const assistantMsg = {
        id: `a_${Date.now()}`,
        role: 'assistant' as const,
        content: rawText,
        time: nowStamp(),
        target: target,
        steps: finishedSteps,
      }
      setChatMessages((prev) => [...prev, assistantMsg])

      setDirectLogs((prev) => [
        ...prev,
        { id: `l_${Date.now()}`, time: nowStamp(), text: `[RÉSULTAT] Analyse disponible (${advisory.content.length} caractères). Vérifications techniques à effectuer.`, tone: 'ok' }
      ])
      C.addXp(30)
      C.pushLog({ text: `✓ Analyse préparée : ${inputContent.slice(0, 35)}… (+30 XP)`, tone: 'xp' })
    } catch (err) {
      const errStr = err instanceof Error ? err.message : String(err)
      setDirectSteps((prev) => prev.map((s) => s.status === 'running' ? { ...s, status: 'error', detail: errStr } : s))
      setDirectLogs((prev) => [...prev, { id: `l_${Date.now()}`, time: nowStamp(), text: `[ERREUR] ${errStr}`, tone: 'warn' }])
      setDirectResult(`Échec de l’analyse : ${errStr}`)
      setChatMessages((prev) => [...prev, {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Erreur lors de l’analyse :**\n\`\`\`\n${errStr}\n\`\`\``,
        time: nowStamp(),
      }])
    } finally {
      setDirectRunning(false)
    }
  }

  useEffect(() => {
    if (!briefingCopied) return
    const t = window.setTimeout(() => setBriefingCopied(false), 1600)
    return () => window.clearTimeout(t)
  }, [briefingCopied])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: 'nearest' })
  }, [C.logs])

  const drop = useFileDrop({
    onFiles: (fs) => void C.uploadNotesMulti(fs),
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: C.notesUploading,
  })

  const notesEdited = C.notesOriginalText !== C.notesText
  const epreuveScores = useMemo(
    () => C.epreuveRunsForActive.slice().sort((a, b) => a.startedAt - b.startedAt).map((r) => r.score ?? 0).filter((s) => s > 0),
    [C.epreuveRunsForActive],
  )
  const ActiveToolBench =
    activeToolBench === 'warroom' ? WarRoomToolBench
    : activeToolBench === 'investigator' ? AutonomousInvestigatorToolBench
    : activeToolBench === 'dynamic0day' ? DynamicZeroDayToolBench
    : activeToolBench === 'symbolic' ? SymbolicExecutionToolBench
    : activeToolBench === 'binary' ? BinaryDisassemblyToolBench
    : activeToolBench === 'ebpf' ? EbpfKernelToolBench
    : activeToolBench === 'soar' ? SoarPlaybookToolBench
    : activeToolBench === 'zeroday' ? ZeroDayToolBench
    : activeToolBench === 'attackgraph' ? AttackGraphToolBench
    : activeToolBench === 'deepreasoning' ? DeepReasoningToolBench
    : activeToolBench === 'webaudit' ? WebAuditorToolBench
    : activeToolBench === 'network' ? NetworkToolBench
    : activeToolBench === 'forensics' ? ForensicsToolBench
    : activeToolBench === 'web' ? WebSecToolBench
    : activeToolBench === 'intel' ? ThreatIntelToolBench
    : null

  return (
    <div
      {...drop.bind}
      className="cyberv4"
      style={{
        padding: '22px 26px', minHeight: '100%', color: FG, position: 'relative',
        fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif",
      }}
    >
      <style>{`
        @keyframes cyberPulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes cyberRise { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:none} }
        @keyframes cyberSpin { to { transform: rotate(360deg) } }
        @keyframes cyberBlink { 50% { opacity: 0 } }
        @keyframes cyberSweep { from{ left:-45%; opacity:.9 } to{ left:130%; opacity:0 } }
        @keyframes cyberHalo { 0%,100%{ opacity:.55; transform:scale(1) } 50%{ opacity:1; transform:scale(1.08) } }
        @keyframes cyberFloat { 0%,100%{ transform: translateY(0) } 50%{ transform: translateY(-5px) } }
        @keyframes cyberScan { 0%{ top:-9%; opacity:0 } 12%{ opacity:1 } 62%{ opacity:1 } 100%{ top:109%; opacity:0 } }
        @keyframes cyberBandSweep { 0%{ left:-18% } 62%,100%{ left:118% } }
        @keyframes cyberShimmer { from{ background-position: 200% 0 } to{ background-position: -100% 0 } }
        .cyber-rise {
          position: relative;
          animation: cyberRise .5s cubic-bezier(.22,1,.36,1) backwards;
          transition: transform .3s cubic-bezier(.22,1,.36,1), box-shadow .3s cubic-bezier(.22,1,.36,1);
        }
        .cyber-rise::before {
          content: ''; position: absolute; top: 0; left: 18px; right: 18px; height: 1px; pointer-events: none;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,.24), transparent);
          opacity: .5; transition: opacity .3s ease;
        }
        .cyber-rise:hover::before { opacity: 1 }
        .cyber-rise:hover {
          transform: translateY(-3px);
          box-shadow: 0 0 0 1px ${ACCENT}3d, 0 24px 48px -24px rgba(0,0,0,.8), 0 12px 36px ${ACCENT}17 !important;
        }
        .cyber-kata { animation: cyberRise .45s cubic-bezier(.22,1,.36,1) backwards }
        .cyber-kata:hover {
          transform: translateY(-2px);
          box-shadow: inset 0 0 0 1px ${ACCENT}40, 0 12px 26px -14px ${ACCENT}59 !important;
        }
        .cyber-log { animation: cyberRise .35s cubic-bezier(.22,1,.36,1) backwards }
        .cyber-btn-primary { position: relative; overflow: hidden }
        .cyber-btn-primary::after {
          content: ''; position: absolute; top: -20%; bottom: -20%; left: -45%; width: 34%;
          background: linear-gradient(105deg, transparent, rgba(255,255,255,.6), transparent);
          transform: skewX(-18deg); opacity: 0; pointer-events: none;
        }
        .cyber-btn-primary:hover::after { animation: cyberSweep .7s ease-out forwards }
        .cyber-btn-primary:hover:not(:disabled) { filter: saturate(1.15) brightness(1.06) }
        .cyber-btn-ghost:hover:not(:disabled) { transform: translateY(-1px); border-color: ${ACCENT}59 !important }
        .cyber-chip { transition: transform .2s ease, box-shadow .2s ease }
        .cyber-chip:hover { transform: translateY(-1px); box-shadow: 0 5px 16px -7px ${ACCENT}88 }
        .cyber-toolrow { transition: transform .25s cubic-bezier(.22,1,.36,1), border-color .25s ease }
        .cyber-toolrow:hover { transform: translateX(3px); border-color: ${ACCENT}55 !important }
        .cyber-float { animation: cyberFloat 6s ease-in-out infinite }
        .cyber-band { overflow: hidden }
        .cyber-band::after {
          content: ''; position: absolute; top: 0; bottom: 0; left: -18%; width: 70px; pointer-events: none;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,.75), transparent);
          animation: cyberBandSweep 4.4s cubic-bezier(.55,.1,.45,.9) infinite;
        }
        .cyber-xpfill { position: relative; overflow: hidden }
        .cyber-xpfill::after {
          content: ''; position: absolute; inset: 0; pointer-events: none;
          background-image: linear-gradient(105deg, transparent 32%, rgba(255,255,255,.42) 50%, transparent 68%);
          background-size: 220% 100%;
          animation: cyberShimmer 3s linear infinite;
        }
        .cyber-term { background-image: repeating-linear-gradient(0deg, rgba(255,255,255,.02) 0 1px, transparent 1px 3px) }
        .cyberv4-bg {
          position: absolute; inset: 0; z-index: 0; pointer-events: none; overflow: hidden;
          background-image:
            radial-gradient(1100px 640px at 88% -8%, ${ACCENT}14, transparent 62%),
            radial-gradient(920px 560px at -12% 36%, ${ACCENT}0e, transparent 64%),
            radial-gradient(780px 780px at 58% 112%, ${ACCENT}0a, transparent 60%),
            radial-gradient(rgba(255,255,255,.05) 1px, transparent 1.4px),
            radial-gradient(rgba(255,255,255,.028) 1px, transparent 1.3px);
          background-size: auto, auto, auto, 34px 34px, 56px 56px;
          background-position: 0 0, 0 0, 0 0, 0 0, 17px 23px;
        }
        .cyberv4-bg::after {
          content: ''; position: absolute; left: 0; right: 0; top: -9%; height: 160px; pointer-events: none;
          background: linear-gradient(180deg, transparent, ${ACCENT}0f 48%, ${ACCENT}16 52%, transparent);
          animation: cyberScan 12s cubic-bezier(.45,.05,.55,.95) infinite;
          opacity: 0;
        }
        .cyberv4 ::selection { background: ${ACCENT}66; color: #fff }
        .cyberv4 *::-webkit-scrollbar { width: 7px; height: 7px }
        .cyberv4 *::-webkit-scrollbar-track { background: transparent }
        .cyberv4 *::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius: 99px }
        .cyberv4 *::-webkit-scrollbar-thumb:hover { background: ${ACCENT}77 }
        .cyber-in input:focus, .cyber-in textarea:focus, .cyber-in select:focus {
          border-color: ${ACCENT} !important; box-shadow: 0 0 16px ${ACCENT}40 !important;
        }
        .cyber-brief-md {
          text-align: left;
          color: ${FG};
        }
        .cyber-brief-md h1,
        .cyber-brief-md h2,
        .cyber-brief-md h3 {
          margin-top: 14px;
          margin-bottom: 8px;
          color: ${FG};
          letter-spacing: 0;
        }
        .cyber-brief-md p,
        .cyber-brief-md li {
          color: ${DIM};
          font-size: 13px;
          line-height: 1.6;
        }
        .cyber-brief-md code {
          background: rgba(244,63,94,.12);
          color: #FFD9E1;
          border: 1px solid rgba(244,63,94,.18);
        }
        .cyber-brief-md pre {
          background: rgba(5,8,16,.78);
          border: 1px solid rgba(255,255,255,.09);
        }
        @media (prefers-reduced-motion: reduce) {
          .cyberv4 *, .cyberv4 ::before, .cyberv4 ::after {
            animation-duration: .001s !important;
            animation-iteration-count: 1 !important;
            transition: none !important;
          }
          .cyber-rise:hover, .cyber-kata:hover, .cyber-btn-primary:hover, .cyber-btn-ghost:hover,
          .cyber-chip:hover, .cyber-toolrow:hover { transform: none !important }
        }
        @media (max-width: 900px) {
          .cyberv4 {
            padding: 16px 12px !important;
            overflow-x: hidden !important;
          }
          .cyber-in {
            grid-template-columns: minmax(0, 1fr) !important;
            gap: 14px !important;
          }
          .cyber-in > div {
            min-width: 0 !important;
            width: 100% !important;
          }
          .cyber-in > div:last-child {
            position: static !important;
            top: auto !important;
          }
          .cyber-in > div:last-child > .cyber-log {
            height: auto !important;
            min-height: 560px !important;
          }
          .cyber-empty-head {
            flex-direction: column !important;
            align-items: flex-start !important;
          }
          .cyber-empty-head > button {
            width: 100% !important;
          }
        }
        @media (max-width: 520px) {
          .cyberv4 {
            padding: 12px 10px !important;
          }
          .cyberv4 header {
            align-items: flex-start !important;
          }
          .cyber-kata {
            border-radius: 10px !important;
          }
        }
      `}</style>
      <div aria-hidden className="cyberv4-bg" />

      {drop.isDraggingOver && (
        <div style={{
          position: 'fixed', inset: '52px 0 0 68px', zIndex: 30, pointerEvents: 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(5,7,13,.55)', backdropFilter: 'blur(4px)',
        }}>
          <div style={{ ...glass, padding: '16px 28px', border: `1px solid ${ACCENT}`, ...mono, fontSize: 12, letterSpacing: '.2em', textTransform: 'uppercase', color: ACCENT }}>
            Déposer notes · txt / md / pdf / docx
          </div>
        </div>
      )}

      <header style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14, position: 'relative', zIndex: 1 }}>
        <span className="cyber-float" style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}>
          <span aria-hidden style={{
            position: 'absolute', inset: -14, borderRadius: '50%', pointerEvents: 'none',
            background: `radial-gradient(circle, ${ACCENT}38, transparent 70%)`,
            animation: 'cyberHalo 3.2s ease-in-out infinite',
          }} />
          <span style={{ position: 'relative', filter: `drop-shadow(0 0 14px ${ACCENT}55)` }}>
            <AuroraMascot module="cyber" size={46} state={C.labLoading ? 'working' : 'idle'} />
          </span>
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{
            margin: 0, fontWeight: 800, letterSpacing: '-0.02em', fontSize: 27, lineHeight: 1.1,
            background: `linear-gradient(115deg, #FFFFFF 30%, #FFD9E1 62%, ${ACCENT})`,
            WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            filter: `drop-shadow(0 4px 22px ${ACCENT}40)`,
          }}>
            Cyber
          </h1>
          <div style={{ ...monoLabel, marginTop: 7, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: ACCENT }}>Salle de crise</span>
            <span style={{ color: MUTE }}>//</span>
            <span>{C.active.discipline}</span>
            <span style={{ ...pillMeta, color: DIM }}>Étape {C.stage}/4</span>
            <span style={{ ...pillMeta, color: MUTE }}>{C.mainModel || 'modèle local'}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span title="Perimetre preventif : lab local, audit autorise, defense et OSINT/read-only"
            style={{
              ...mono, fontSize: 9.5, letterSpacing: '.16em', textTransform: 'uppercase',
              color: ACCENT, padding: '5px 10px', borderRadius: 999,
              background: `${ACCENT}18`, border: `1px solid ${ACCENT}55`,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
            <Dot color={ACCENT} pulse /> Expert · preventif
          </span>
          <Btn variant="ghost" onClick={() => setHelpOpen((v) => !v)} title="Comment ça marche ?">
            <HelpCircle size={14} /> Aide
          </Btn>
        </div>
      </header>

      <div aria-hidden className="cyber-band" style={{
        position: 'relative', zIndex: 1, height: 2, borderRadius: 99, marginBottom: 18,
        background: `linear-gradient(90deg, ${ACCENT}, ${ACCENT}33 34%, rgba(255,255,255,.06) 70%, transparent)`,
        boxShadow: `0 0 14px ${ACCENT}66`,
      }} />

      {helpOpen && (
        <Card accent style={{ marginBottom: 16, position: 'relative', zIndex: 1 }} >
          <button type="button" onClick={() => setHelpOpen(false)} aria-label="Fermer l'aide"
            style={{ position: 'absolute', top: 12, right: 12, background: 'transparent', border: 'none', cursor: 'pointer', color: DIM }}>
            <X size={15} />
          </button>
          <Label dot={ACCENT}>Module cyber exploitable</Label>
          <p style={{ margin: '10px 0 12px', fontSize: 13.5, lineHeight: 1.6, color: FG, maxWidth: 620 }}>
            Tu pars d'une demande claire : briefing expert, analyse d'artefacts, lab interactif,
            attaque sandboxee ou defense concrete avec preuves et corrections.
          </p>
          <div style={{ display: 'grid', gap: 8 }}>
            {[
              'Ecris une demande cyber ou choisis une mission lisible.',
              'Demande un brief expert ou forge directement un lab sandboxe.',
              'Manipule le lab, valide les preuves, puis passe en defense ou en durcissement.',
            ].map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{
                  flexShrink: 0, width: 22, height: 22, borderRadius: 999, ...mono, fontSize: 12, fontWeight: 800,
                  background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`, color: '#0A0F1E',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}>{i + 1}</span>
                <span style={{ fontSize: 13, lineHeight: 1.5, color: DIM }}>{s}</span>
              </div>
            ))}
          </div>
          <div style={{ ...mono, fontSize: 11, lineHeight: 1.8, color: MUTE, marginTop: 12, paddingTop: 10, borderTop: '1px dashed rgba(255,255,255,.1)' }}>
            <b style={{ color: DIM }}>Lexique</b> — mission = objectif cyber · lab = cible sandboxee · offense = attaque autorisee/simulee ·
            defense = detection, correction, durcissement · flag = preuve de reussite dans le lab.
          </div>
        </Card>
      )}

      {/* 2-Mode Segmented Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18, position: 'relative', zIndex: 1, flexWrap: 'wrap' }}>
        <div style={{ display: 'inline-flex', padding: 4, background: 'rgba(10,15,30,.85)', borderRadius: 14, border: '1px solid rgba(255,255,255,.12)', gap: 4 }}>
          <button
            type="button"
            onClick={() => setCyberMode('chat')}
            style={{
              padding: '8px 20px',
              borderRadius: 10,
              border: cyberMode === 'chat' ? `1px solid ${ACCENT}` : '1px solid transparent',
              background: cyberMode === 'chat' ? `linear-gradient(135deg, ${ACCENT}33, rgba(255,255,255,.06))` : 'transparent',
              color: cyberMode === 'chat' ? '#fff' : DIM,
              fontWeight: cyberMode === 'chat' ? 800 : 500,
              fontSize: 13,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              boxShadow: cyberMode === 'chat' ? `0 4px 18px ${ACCENT}44` : 'none',
              transition: 'all .2s ease',
            }}
          >
            <MessageSquare size={15} color={cyberMode === 'chat' ? ACCENT : DIM} />
            <span>💬 Discussion & Audit Cyber</span>
          </button>
          <button
            type="button"
            onClick={() => setCyberMode('lab')}
            style={{
              padding: '8px 20px',
              borderRadius: 10,
              border: cyberMode === 'lab' ? `1px solid ${BLUE}` : '1px solid transparent',
              background: cyberMode === 'lab' ? `linear-gradient(135deg, ${BLUE}33, rgba(255,255,255,.06))` : 'transparent',
              color: cyberMode === 'lab' ? '#fff' : DIM,
              fontWeight: cyberMode === 'lab' ? 800 : 500,
              fontSize: 13,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              boxShadow: cyberMode === 'lab' ? `0 4px 18px ${BLUE}44` : 'none',
              transition: 'all .2s ease',
            }}
          >
            <Wand2 size={15} color={cyberMode === 'lab' ? BLUE : DIM} />
            <span>⚒️ Forger son Laboratoire</span>
          </button>
        </div>
        <span style={{ flex: 1 }} />
        {cyberMode === 'chat' ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Chip tone={C.stance === 'offense' ? ACCENT : BLUE} active onClick={() => C.setStance(C.stance === 'offense' ? 'defense' : 'offense')} title="Cliquer pour basculer de posture">
              {C.stance === 'offense' ? '🔴 Posture Offensive (Red Team)' : '🔵 Posture Défensive (Blue Team)'}
            </Chip>
            {chatMessages.length > 1 && (
              <Btn variant="ghost" onClick={() => setChatMessages([chatMessages[0]])} title="Effacer l'historique de conversation">
                <Trash2 size={13} />
              </Btn>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Chip tone={ACCENT} active>
              Ceinture {C.belt} · {C.xp} XP
            </Chip>
            <Chip tone={BLUE}>
              Stage {C.stage}/4
            </Chip>
          </div>
        )}
      </div>

      {cyberMode === 'chat' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: 18, alignItems: 'start', position: 'relative', zIndex: 1 }} className="cyber-in">
          {/* Colonne Principale de Conversation */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Card style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 560, background: 'rgba(10,15,30,.75)', border: '1px solid rgba(255,255,255,.1)' }}>
              
              {/* En-tête du Chat */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 18px', borderBottom: '1px solid rgba(255,255,255,.08)', background: 'rgba(5,8,16,.5)' }}>
                <MessageSquare size={16} color={ACCENT} />
                <span style={{ fontWeight: 750, fontSize: 13, color: FG }}>Discussion Technique & Audit d'Invariants</span>
                <span style={{ flex: 1 }} />
                <span style={{ ...mono, fontSize: 10.5, color: DIM }}>
                  Modèle : <b style={{ color: FG }}>{C.mainModel || 'Qwen Cyber'}</b>
                </span>
              </div>

              {/* Flux de messages */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 16, maxHeight: 'calc(100vh - 380px)', minHeight: 380 }}>
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: MUTE, ...mono }}>
                      {msg.role === 'user' ? (
                        <>
                          <span>{msg.time}</span>
                          <span style={{ color: ACCENT, fontWeight: 700 }}>Opérateur</span>
                        </>
                      ) : (
                        <>
                          <span style={{ color: OK, fontWeight: 700 }}>🛡️ Aurora Cyber Engine</span>
                          <span>{msg.time}</span>
                        </>
                      )}
                    </div>
                    <div
                      style={{
                        maxWidth: '92%',
                        padding: msg.role === 'user' ? '12px 16px' : '16px 20px',
                        borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                        background: msg.role === 'user' ? 'rgba(244,63,94,.12)' : 'rgba(255,255,255,.03)',
                        border: msg.role === 'user' ? `1px solid ${ACCENT}44` : '1px solid rgba(255,255,255,.09)',
                        color: FG,
                        fontSize: 13.5,
                        lineHeight: 1.6,
                        boxShadow: '0 4px 16px rgba(0,0,0,.25)',
                      }}
                    >
                      {msg.role === 'user' ? (
                        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.content}</div>
                      ) : (
                        <div className="cyber-brief-md">
                          <MarkdownPro content={msg.content} />
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {directRunning && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '14px 18px', borderRadius: 14, background: 'rgba(244,63,94,.06)', border: `1px solid ${ACCENT}33` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Loader2 size={15} color={ACCENT} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                      <span style={{ ...mono, fontSize: 11.5, fontWeight: 700, color: FG }}>
                        Audit technique & déduction d'invariants en cours…
                      </span>
                    </div>
                    <div style={{ display: 'grid', gap: 6, marginTop: 4 }}>
                      {directSteps.map((step) => (
                        <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, ...mono }}>
                          {step.status === 'running' ? (
                            <Loader2 size={12} color={ACCENT} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                          ) : step.status === 'done' ? (
                            <CheckCircle2 size={12} color={OK} />
                          ) : step.status === 'error' ? (
                            <AlertTriangle size={12} color={WARN} />
                          ) : (
                            <span style={{ width: 12, height: 12, borderRadius: '50%', border: '1px solid rgba(255,255,255,.2)' }} />
                          )}
                          <span style={{ color: step.status === 'running' ? FG : step.status === 'done' ? OK : MUTE }}>{step.label}</span>
                          <span style={{ flex: 1 }} />
                          {step.durationMs ? <span style={{ color: OK, fontSize: 10 }}>{step.durationMs}ms</span> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Barre de saisie conversationnelle */}
              <div style={{ padding: '14px 16px', background: 'rgba(5,8,16,.75)', borderTop: '1px solid rgba(255,255,255,.08)' }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                  <textarea
                    value={C.customBrief}
                    onChange={(e) => C.setCustomBrief(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !directRunning && C.customBrief.trim()) {
                        e.preventDefault()
                        void handleDirectExecute()
                      }
                    }}
                    disabled={directRunning}
                    rows={2}
                    placeholder="Posez votre question cyber, URL cible, audit d'API ou analyse de code... (Ctrl + Entrée)"
                    style={{ ...inputBase, flex: 1, padding: '10px 12px', fontSize: 12.5, resize: 'none', lineHeight: 1.5 }}
                  />
                  <VoicePushToTalk
                    onTranscript={(text) => C.setCustomBrief((C.customBrief ? C.customBrief + ' ' : '') + text)}
                    label="Dicter la demande"
                    disabled={directRunning}
                    variant="ghost"
                    size={38}
                  />
                  <Btn
                    variant="primary"
                    disabled={!C.customBrief.trim() || directRunning}
                    onClick={() => void handleDirectExecute()}
                    style={{ padding: '10px 18px', height: 38, fontWeight: 750 }}
                  >
                    {directRunning ? (
                      <Loader2 size={15} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                    ) : (
                      <>
                        <Send size={14} />
                        <span>Envoyer</span>
                      </>
                    )}
                  </Btn>
                </div>
              </div>
            </Card>

            {/* Console Déployable */}
            <Card style={{ padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Terminal size={14} color={ACCENT} />
                <Label>Journal de l’analyse</Label>
                <span style={{ flex: 1 }} />
                <button
                  type="button"
                  onClick={() => setIsConsoleOpen(!isConsoleOpen)}
                  style={{
                    background: isConsoleOpen ? `${ACCENT}22` : 'rgba(255,255,255,.05)',
                    border: `1px solid ${isConsoleOpen ? ACCENT : 'rgba(255,255,255,.14)'}`,
                    borderRadius: 8,
                    padding: '4px 9px',
                    color: isConsoleOpen ? ACCENT : DIM,
                    fontSize: 10.5,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    cursor: 'pointer',
                    ...mono,
                  }}
                >
                  <Terminal size={11} />
                  {isConsoleOpen ? 'Réduire la console' : 'Déployer la console'}
                  {isConsoleOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              </div>
              {isConsoleOpen && (
                <div style={{ marginTop: 10, padding: '10px 11px', borderRadius: 10, background: '#070B14', border: '1px solid rgba(255,255,255,.15)', maxHeight: 200, overflowY: 'auto', ...mono, fontSize: 10.5, lineHeight: 1.45 }}>
                  <div style={{ color: MUTE, marginBottom: 6, borderBottom: '1px solid rgba(255,255,255,.08)', paddingBottom: 4 }}>
                    --- FLUX DE TÉLÉMÉTRIE & LOGS D'AUDIT EN DIRECT ---
                  </div>
                  {directLogs.map((log) => (
                    <div key={log.id} style={{ color: log.tone === 'ok' ? OK : log.tone === 'accent' ? ACCENT : log.tone === 'warn' ? WARN : DIM, marginBottom: 3 }}>
                      <span style={{ color: MUTE, marginRight: 6 }}>[{log.time}]</span>
                      {log.text}
                    </div>
                  ))}
                  <div ref={consoleEndRef} />
                </div>
              )}
            </Card>
          </div>

          {/* Panneau Latéral Droit : Scénarios rapides & Statut */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Card>
              <Label style={{ marginBottom: 10 }}>Scénarios d'Audit Prédéfinis</Label>
              <div style={{ display: 'grid', gap: 7 }}>
                {CYBER_REQUEST_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => {
                      C.setStance(preset.stance)
                      C.setCustomBrief(preset.text)
                    }}
                    style={{
                      textAlign: 'left',
                      padding: '9px 11px',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,.03)',
                      border: '1px solid rgba(255,255,255,.08)',
                      color: FG,
                      cursor: 'pointer',
                      fontSize: 12,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 3,
                    }}
                  >
                    <span style={{ fontWeight: 700, color: preset.stance === 'offense' ? ACCENT : BLUE }}>{preset.label}</span>
                    <span style={{ fontSize: 11, color: DIM, lineHeight: 1.4 }}>{preset.text.slice(0, 75)}…</span>
                  </button>
                ))}
              </div>
            </Card>

            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <ShieldCheck size={16} color={OK} />
                <Label>Moteur d'Audit Actif</Label>
              </div>
              <div style={{ ...mono, fontSize: 11, color: DIM, lineHeight: 1.6 }}>
                Modèle : <b style={{ color: FG }}>{C.mainModel || 'Qwen Cyber'}</b><br />
                Contexte : <span style={{ color: OK }}>4096 / 8192 tokens</span><br />
                Invariants : <span style={{ color: OK }}>Code/Data, Timing O(1), PQC</span><br />
                Posture : <span style={{ color: C.stance === 'offense' ? ACCENT : BLUE }}>{C.stance === 'offense' ? 'Offensive (Red Team)' : 'Défensive (Blue Team)'}</span>
              </div>
            </Card>
          </div>
        </div>
      ) : (
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 430px) 1fr', gap: 18, alignItems: 'start', position: 'relative', zIndex: 1 }} className="cyber-in">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          <Card className="cyber-rise" accent style={{ animationDelay: '.02s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
              <TerminalSquare size={16} color={ACCENT} />
              <Label dot={C.briefStatus === 'thinking' || C.toolStrategyStatus === 'thinking' ? ACCENT : undefined}>Demande cyber</Label>
              <span style={{ flex: 1 }} />
              <Chip tone={C.stance === 'offense' ? ACCENT : BLUE} active title="Posture actuelle">
                {C.stance === 'offense' ? 'attaque sandbox / audit' : 'defense / incident'}
              </Chip>
            </div>
            <textarea
              value={C.customBrief}
              onChange={(e) => C.setCustomBrief(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !C.labLoading && !directRunning && C.customBrief.trim()) {
                  e.preventDefault()
                  void handleDirectExecute()
                }
              }}
              disabled={C.labLoading || C.briefStatus === 'thinking'}
              rows={4}
              placeholder="Ex : analyse ces logs SSH · prepare un audit web autorise · forge un lab XSS/SQLi · explique et corrige une CVE · durcis mon API"
              style={{ ...inputBase, width: '100%', padding: '11px 12px', fontSize: 12.5, boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.5 }}
            />
            <input
              value={C.scopeTarget}
              onChange={(e) => C.setScopeTarget(e.target.value)}
              disabled={C.labLoading || C.briefStatus === 'thinking' || C.toolStrategyStatus === 'thinking'}
              placeholder="Perimetre autorise : domaine, IP privee, repo, machine lab, logs, plage interne..."
              style={{ ...inputBase, width: '100%', marginTop: 9, padding: '9px 11px', fontSize: 12.2, boxSizing: 'border-box' }}
            />
            <div style={{ marginTop: 9, padding: '10px 11px', borderRadius: 12, border: `1px solid ${C.scopeAuthorized ? OK + '55' : WARN + '55'}`, background: C.scopeAuthorized ? 'rgba(74,222,128,.06)' : 'rgba(245,158,11,.08)' }}>
              <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer', color: DIM, fontSize: 11.5, lineHeight: 1.45 }}>
                <input
                  type="checkbox"
                  checked={C.scopeAuthorized}
                  onChange={(e) => {
                    C.setScopeAuthorized(e.target.checked)
                    if (!e.target.checked) C.setAutonomyEnabled(false)
                  }}
                  style={{ marginTop: 2 }}
                />
                <span>
                  Je confirme que le perimetre est a moi, autorise, local ou sandboxe. Les actions actives contre un tiers sans autorisation peuvent etre illegales.
                </span>
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: C.scopeAuthorized ? 'pointer' : 'not-allowed', color: C.scopeAuthorized ? DIM : MUTE, fontSize: 11.5, lineHeight: 1.45, marginTop: 8 }}>
                <input
                  type="checkbox"
                  checked={C.autonomyEnabled && C.scopeAuthorized}
                  disabled={!C.scopeAuthorized}
                  onChange={(e) => C.setAutonomyEnabled(e.target.checked)}
                  style={{ marginTop: 2 }}
                />
                <span>Autoriser Aurora a planifier en autonomie bornee : choisir les outils, preparer l'installation/config et enchainer uniquement ce que le backend autorise dans le perimetre confirme.</span>
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
              <Btn
                variant="primary"
                disabled={!C.customBrief.trim() || directRunning || C.labLoading}
                onClick={() => void handleDirectExecute()}
                title="Analyse les informations fournies et prépare les vérifications à effectuer"
                style={{ justifyContent: 'center', padding: '12px 14px', fontSize: 13, fontWeight: 800 }}
              >
                {directRunning ? (
                  <>
                    <Loader2 size={15} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                    Analyse en cours…
                  </>
                ) : (
                  <>
                    <Play size={15} fill="#0A0F1E" color="#0A0F1E" />
                    Préparer l’analyse
                  </>
                )}
              </Btn>

              <Btn
                variant="ghost"
                disabled={!C.customBrief.trim() || C.labLoading || directRunning}
                onClick={() => void C.forgeCustomKata()}
                title="Forge un lab interactif sandboxé complet depuis cette demande"
                style={{
                  justifyContent: 'center',
                  padding: '12px 14px',
                  fontSize: 13,
                  fontWeight: 750,
                  border: `1px solid ${BLUE}66`,
                  background: 'rgba(96,165,250,.08)',
                  color: BLUE,
                }}
              >
                {C.labLoading ? (
                  <>
                    <Loader2 size={15} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                    Forgeage du lab…
                  </>
                ) : (
                  <>
                    <Wand2 size={15} color={BLUE} />
                    Forger le lab
                  </>
                )}
              </Btn>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
              <VoicePushToTalk
                onTranscript={(text) => C.setCustomBrief((C.customBrief ? C.customBrief + ' ' : '') + text)}
                label="Dicter la demande cyber"
                disabled={C.labLoading || directRunning}
                variant="ghost"
                size={34}
              />
              <Btn
                variant="ghost"
                disabled={!C.customBrief.trim() || C.briefStatus === 'thinking'}
                onClick={() => void C.discussCyberBrief()}
                style={{ padding: '6px 12px', fontSize: 11 }}
                title="Génère un cadrage d'ingénierie et d'architecture préalable"
              >
                <Activity size={12} /> Brief expert
              </Btn>
              <Btn
                variant="ghost"
                disabled={(!C.customBrief.trim() && !C.scopeTarget.trim()) || C.toolStrategyStatus === 'thinking'}
                onClick={() => void C.buildToolStrategy()}
                style={{ padding: '6px 12px', fontSize: 11 }}
                title="Choisit les vrais outils et prépare l'installation"
              >
                <TerminalSquare size={12} /> Outils requis
              </Btn>
            </div>

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
              {CYBER_REQUEST_PRESETS.map((preset) => (
                <Chip key={preset.label} tone={preset.stance === 'offense' ? ACCENT : BLUE}
                  onClick={() => { C.setStance(preset.stance); C.setCustomBrief(preset.text) }}
                  title="Remplir la demande avec ce scenario">
                  {preset.label}
                </Chip>
              ))}
            </div>

            {directSteps.length > 0 && (
              <div style={{ marginTop: 14, padding: '12px 13px', borderRadius: 14, background: 'rgba(10,15,30,.75)', border: '1px solid rgba(255,255,255,.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <Activity size={14} color={ACCENT} />
                  <span style={{ ...mono, fontSize: 11, fontWeight: 700, color: FG }}>
                    {directRunning ? 'Analyse en cours' : 'Résultat de l’analyse'}
                  </span>
                  <span style={{ flex: 1 }} />
                  <button
                    type="button"
                    onClick={() => setIsConsoleOpen(!isConsoleOpen)}
                    style={{
                      background: isConsoleOpen ? `${ACCENT}22` : 'rgba(255,255,255,.05)',
                      border: `1px solid ${isConsoleOpen ? ACCENT : 'rgba(255,255,255,.14)'}`,
                      borderRadius: 8,
                      padding: '4px 9px',
                      color: isConsoleOpen ? ACCENT : DIM,
                      fontSize: 10.5,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 5,
                      cursor: 'pointer',
                      ...mono,
                    }}
                  >
                    <Terminal size={11} />
                    {isConsoleOpen ? 'Réduire la console' : 'Déployer la console'}
                    {isConsoleOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                </div>

                <div style={{ display: 'grid', gap: 6 }}>
                  {directSteps.map((step) => (
                    <div
                      key={step.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 9px',
                        borderRadius: 8,
                        background: step.status === 'running' ? 'rgba(244,63,94,.08)' : step.status === 'done' ? 'rgba(74,222,128,.04)' : 'rgba(255,255,255,.02)',
                        border: `1px solid ${step.status === 'running' ? ACCENT + '44' : step.status === 'done' ? OK + '33' : 'rgba(255,255,255,.05)'}`,
                      }}
                    >
                      {step.status === 'running' ? (
                        <Loader2 size={13} color={ACCENT} style={{ animation: 'cyberSpin 1s linear infinite' }} />
                      ) : step.status === 'done' ? (
                        <CheckCircle2 size={13} color={OK} />
                      ) : step.status === 'error' ? (
                        <AlertTriangle size={13} color={WARN} />
                      ) : (
                        <span style={{ width: 13, height: 13, borderRadius: '50%', border: '1px solid rgba(255,255,255,.2)' }} />
                      )}
                      <span style={{ ...mono, fontSize: 11, color: step.status === 'running' ? FG : step.status === 'done' ? FG : MUTE, fontWeight: step.status === 'running' ? 700 : 500 }}>
                        {step.label}
                      </span>
                      <span style={{ flex: 1 }} />
                      {step.durationMs ? (
                        <span style={{ ...mono, fontSize: 9.5, color: OK }}>
                          {step.durationMs} ms
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>

                {isConsoleOpen && (
                  <div style={{ marginTop: 10, padding: '10px 11px', borderRadius: 10, background: '#070B14', border: '1px solid rgba(255,255,255,.15)', maxHeight: 220, overflowY: 'auto', ...mono, fontSize: 10.5, lineHeight: 1.45 }}>
                    <div style={{ color: MUTE, marginBottom: 6, borderBottom: '1px solid rgba(255,255,255,.08)', paddingBottom: 4 }}>
                      --- CONSOLE D'EXÉCUTION CYBER & TÉLÉMÉTRIE EN DIRECT ---
                    </div>
                    {directLogs.map((log) => (
                      <div key={log.id} style={{ color: log.tone === 'ok' ? OK : log.tone === 'accent' ? ACCENT : log.tone === 'warn' ? WARN : DIM, marginBottom: 3 }}>
                        <span style={{ color: MUTE, marginRight: 6 }}>[{log.time}]</span>
                        {log.text}
                      </div>
                    ))}
                    <div ref={consoleEndRef} />
                  </div>
                )}

                {directResult && (
                  <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 10, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)', fontSize: 11.5, lineHeight: 1.55, color: FG, maxHeight: 280, overflowY: 'auto' }}>
                    <MarkdownPro content={directResult} />
                  </div>
                )}
              </div>
            )}

            {C.briefStatus === 'ready' && (
              <div style={{ ...mono, fontSize: 10.5, color: OK, marginTop: 9 }}>
                Brief pret dans le panneau de droite. Tu peux enchainer sur un lab ou coller des artefacts.
              </div>
            )}
            {C.briefError && (
              <div style={{ ...mono, fontSize: 10.5, color: WARN, marginTop: 9 }}>
                Brief impossible : {C.briefError}
              </div>
            )}
            {C.toolStrategyError && (
              <div style={{ ...mono, fontSize: 10.5, color: WARN, marginTop: 9 }}>
                Strategie outils impossible : {C.toolStrategyError}
              </div>
            )}
          </Card>

          <Card className="cyber-rise" style={{ animationDelay: '.04s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
              <ShieldCheck size={15} color={C.scopeAuthorized ? OK : WARN} />
              <Label>Outils reels</Label>
              <span style={{ flex: 1 }} />
              <Chip tone={C.scopeAuthorized ? OK : WARN} active={C.scopeAuthorized}>
                {C.scopeAuthorized ? 'perimetre confirme' : 'read-only / lab'}
              </Chip>
            </div>
            <div style={{ display: 'grid', gap: 7 }}>
              {CYBER_TOOL_GROUPS.map((group) => (
                <button key={group.name} type="button" className="cyber-toolrow"
                  onClick={() => {
                    if (group.bench === 'strategy') void C.buildToolStrategy()
                    else setActiveToolBench(group.bench)
                  }}
                  style={{
                  display: 'grid', gridTemplateColumns: '96px 1fr', gap: 8, alignItems: 'start',
                  padding: '8px 9px', borderRadius: 10,
                  border: activeToolBench === group.bench ? `1px solid ${ACCENT}` : group.highlight ? `1px solid ${ACCENT}33` : '1px solid rgba(255,255,255,.08)',
                  background: activeToolBench === group.bench ? `${ACCENT}22` : group.highlight ? 'rgba(244,63,94,.05)' : 'rgba(255,255,255,.025)',
                  cursor: 'pointer', textAlign: 'left', color: FG,
                }}>
                  <span style={{ ...mono, fontSize: 10, color: group.highlight ? ACCENT : FG, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 4 }}>
                    {group.highlight && <Dot color={ACCENT} />} {group.name}
                  </span>
                  <span style={{ ...mono, fontSize: 10.5, color: DIM, lineHeight: 1.45 }}>{group.tools}</span>
                </button>
              ))}
            </div>
            <div style={{ ...mono, fontSize: 10.5, lineHeight: 1.55, color: MUTE, marginTop: 9 }}>
              Aurora selectionne la pile utile, verifie les binaires, propose l'installation/config, puis borne l'execution selon le perimetre confirme.
            </div>
          </Card>

          <Card className="cyber-rise">
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
              <Award size={16} color={ACCENT} />
              <span style={{ fontWeight: 800, letterSpacing: '-.01em', fontSize: 15, textTransform: 'capitalize' }}>Ceinture {C.belt}</span>
              <span style={{ flex: 1 }} />
              <span style={{ ...mono, fontSize: 13, fontWeight: 800, ...gradNum }}>{C.xp}</span>
              <span style={{ ...mono, fontSize: 11, color: MUTE }}>/ {C.nextThresh} XP</span>
            </div>
            <div style={{ height: 8, borderRadius: 99, overflow: 'hidden', background: 'rgba(255,255,255,.06)' }}>
              <div className="cyber-xpfill" style={{
                height: '100%', width: `${C.beltProgress}%`,
                background: `linear-gradient(90deg, ${ACCENT}, #ffffff66)`, boxShadow: `0 0 12px ${ACCENT}88`,
                transition: 'width .5s cubic-bezier(.22,1,.36,1)',
              }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <span style={{ ...mono, fontSize: 10, color: MUTE }}>Prochain palier · {C.beltNext}</span>
              <span style={{ flex: 1 }} />
              {C.bestRank && (
                <Chip tone={ACCENT} active title={`Rang Cyber · ${C.bestRank.xp} XP cumulés · ${C.bestRank.katas} mission(s)`}>
                  <Trophy size={11} /> {C.bestRank.label}
                </Chip>
              )}
              {C.currentStreak > 0 && (
                <Chip tone={WARN} title={`Série actuelle : ${C.currentStreak} j · record ${C.longestStreak} j`}>
                  <Flame size={11} color={WARN} /> {C.currentStreak}j{C.longestStreak > C.currentStreak ? ` · rec ${C.longestStreak}j` : ''}
                </Chip>
              )}
              <Btn variant="ghost" title="Remettre l'XP à zéro (runs et trophées conservés)"
                onClick={() => { if (window.confirm('Remettre l\'XP à zéro (ceinture blanche) ?\nLes runs et trophées ne sont pas touchés.')) C.resetXpOnly() }}
                style={{ padding: '5px 10px', fontSize: 11 }}>
                <RefreshCw size={11} /> Reset XP
              </Btn>
            </div>
            {C.xpCumulativeSeries.length >= 3 && (
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ ...mono, fontSize: 9.5, letterSpacing: '.16em', textTransform: 'uppercase', color: MUTE }}>XP cumulé</span>
                <Sparkline values={C.xpCumulativeSeries} width={150} height={22} color={ACCENT} smooth smoothWindow={5} showAxis />
              </div>
            )}
          </Card>

          <Card className="cyber-rise" style={{ animationDelay: '.06s' }}>
            <Label style={{ marginBottom: 9 }}>Posture</Label>
            <div style={{ display: 'flex', gap: 8 }}>
              <Btn variant={C.stance === 'offense' ? 'primary' : 'ghost'} block onClick={() => C.setStance('offense')}
                title="Tu attaques uniquement un lab, une cible autorisee ou un scenario fictif.">
                <Target size={13} /> Offense
              </Btn>
              <Btn variant={C.stance === 'defense' ? 'primary' : 'ghost'} block onClick={() => C.setStance('defense')}
                title="Tu analyses, detectes, corriges et durcis.">
                <ShieldCheck size={13} /> Defense
              </Btn>
            </div>
          </Card>

          <Card className="cyber-rise" style={{ animationDelay: '.12s' }}>
            <Label style={{ marginBottom: 10 }}>Missions operationnelles</Label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {C.operationalKatas.map((k, i) => {
                const Icon = k.icon
                const on = k.id === C.activeId
                const daily = k.id === C.dailyKata.id
                return (
                  <button key={k.id} type="button" onClick={() => C.setActiveKata(k.id)}
                    className="cyber-kata"
                    style={{
                      textAlign: 'left', cursor: 'pointer', padding: '11px 12px', borderRadius: 13,
                      display: 'flex', flexDirection: 'column', gap: 7, position: 'relative',
                      animationDelay: `${0.14 + i * 0.04}s`,
                      transition: 'all .25s cubic-bezier(.22,1,.36,1)',
                      background: on ? `linear-gradient(150deg, ${ACCENT}, #ffffff22)` : 'rgba(255,255,255,.03)',
                      border: `1px solid ${on ? ACCENT : 'rgba(255,255,255,.09)'}`,
                      boxShadow: on ? `0 6px 22px ${ACCENT}55` : 'none',
                      color: on ? '#0A0F1E' : FG,
                    }}>
                    {daily && (
                      <span title="Mission du jour" style={{
                        position: 'absolute', top: 8, right: 8, width: 6, height: 6, borderRadius: '50%',
                        background: on ? '#0A0F1E' : WARN, boxShadow: on ? 'none' : `0 0 8px ${WARN}`,
                      }} />
                    )}
                    <Icon size={17} strokeWidth={1.7} />
                    <div style={{ fontSize: 12.5, fontWeight: 700, lineHeight: 1.1 }}>{k.name}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ ...mono, fontSize: 9, opacity: on ? 0.75 : 0.6 }}>{k.discipline}</span>
                      <span style={{ flex: 1 }} />
                      <Diff n={k.difficulty} on={on} />
                    </div>
                  </button>
                )
              })}
            </div>

            <details style={{ marginTop: 11 }}>
              <summary style={{ ...mono, color: DIM, fontSize: 10.5, cursor: 'pointer', userSelect: 'none' }}>
                Facultatif / Academy cyber : crypto, hash, password, stegano
              </summary>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 9 }}>
                {C.academyKatas.map((k) => (
                  <Chip key={k.id} tone={k.tone} active={k.id === C.activeId}
                    onClick={() => C.setActiveKata(k.id)}
                    title="Lab d'apprentissage, a ranger cote Academy cyber">
                    {k.name}
                  </Chip>
                ))}
              </div>
            </details>

            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <Chip tone={ACCENT} title="Discipline de la mission active">{C.active.discipline}</Chip>
              <Chip title="Techniques travaillées">{C.active.stance}</Chip>
              <Chip title="Mission active">{C.active.name}</Chip>
            </div>
            <p style={{ margin: '10px 0 0', fontSize: 12.5, lineHeight: 1.55, color: DIM }}>{C.active.lesson}</p>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14 }}>
              <Btn variant="primary" block onClick={C.launchKata} disabled={C.labLoading}
                title="Aurora genere un lab interactif sur cette mission.">
                {C.labLoading
                  ? <><Loader2 size={14} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Aurora prepare le lab…</>
                  : <><Play size={14} fill="currentColor" /> Forger le lab</>}
              </Btn>
            </div>
            {C.labError && (
              <div style={{ marginTop: 10, fontSize: 12, lineHeight: 1.5, color: WARN, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <Activity size={14} style={{ flexShrink: 0, marginTop: 1 }} /> <span>{C.labError}</span>
              </div>
            )}
          </Card>

          <Card className="cyber-rise" style={{ animationDelay: '.18s', ...(C.dailyDone ? { border: `1px solid ${OK}44` } : null) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Label dot={C.dailyDone ? OK : WARN}>Mission du jour</Label>
              <span style={{ flex: 1 }} />
              <span style={{ ...mono, fontSize: 10, color: MUTE }}>{C.dailyDateKey}</span>
              {C.dailyDone && (
                <span style={{ ...mono, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: OK, fontWeight: 700 }}>Réussi</span>
              )}
            </div>
            <div style={{ fontSize: 14, fontWeight: 750, letterSpacing: '-.01em' }}>{C.dailyKata.name}</div>
            <div style={{ ...mono, fontSize: 10.5, color: DIM, marginTop: 5, lineHeight: 1.5 }}>
              {C.dailyKata.discipline} · difficulté {C.dailyKata.difficulty}/3
            </div>
            <div style={{ fontSize: 11.5, color: MUTE, marginTop: 5, lineHeight: 1.5 }}>
              {C.dailyKata.lesson}
            </div>
            <div style={{ marginTop: 10 }}>
              <Btn variant={C.dailyDone ? 'ghost' : 'primary'} block disabled={C.labLoading}
                onClick={() => void C.launchDailyChallenge()}>
                {C.labLoading
                  ? <><Loader2 size={13} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Forge…</>
                  : C.dailyDone ? <><Sparkles size={13} /> Refaire la mission</> : <><Zap size={13} /> Engager la mission</>}
              </Btn>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Btn variant="ghost" block disabled={C.labLoading} onClick={C.randomKata} title="Tirer une mission au hasard">
                <Dice5 size={13} /> Mission aleatoire
              </Btn>
              <Btn variant="ghost" block disabled={C.labLoading} onClick={() => void C.randomKataAndForge()} title="Mission au hasard + forge immediate">
                <Zap size={13} /> Aleatoire + lab
              </Btn>
            </div>
          </Card>

          <Card className="cyber-rise" style={{ animationDelay: '.3s', ...(C.mode === 'epreuve' ? { border: `1px solid ${ACCENT}` } : null) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: C.mode === 'epreuve' ? 12 : 8, flexWrap: 'wrap' }}>
              <Label dot={C.mode === 'epreuve' ? ACCENT : undefined}>Mode · {C.mode === 'epreuve' ? 'Épreuve live' : 'Libre'}</Label>
              <span style={{ flex: 1 }} />
              {C.mode === 'libre' && C.lab && [300, 600, 900, 1800].map((sec) => (
                <Chip key={sec} tone={ACCENT} title={`Lancer une épreuve chrono de ${Math.round(sec / 60)} minutes`} onClick={() => C.startEpreuve(sec)}>
                  {Math.round(sec / 60)} min
                </Chip>
              ))}
              {C.mode === 'epreuve' && (
                <Btn variant="danger" onClick={() => C.stopEpreuve('abandon')} style={{ padding: '5px 12px', fontSize: 11 }}>Abandonner</Btn>
              )}
            </div>

            {C.mode === 'epreuve' && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 8 }}>
                  <div style={{
                    ...mono, fontSize: 34, fontWeight: 750, lineHeight: 1, fontVariantNumeric: 'tabular-nums',
                    ...(C.epreuveTimeLeftSec < 60 ? { color: ACCENT, animation: 'cyberPulse 1.1s ease-in-out infinite' } : gradNum),
                  }}>
                    {Math.floor(C.epreuveTimeLeftSec / 60)}:{String(C.epreuveTimeLeftSec % 60).padStart(2, '0')}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ ...monoLabel }}>Score</div>
                    <div style={{ ...mono, fontSize: 22, fontWeight: 750, ...gradNum }}>{C.epreuveScore}</div>
                  </div>
                </div>
                <div style={{ height: 4, borderRadius: 99, overflow: 'hidden', background: 'rgba(255,255,255,.06)' }}>
                  <div className="cyber-xpfill" style={{
                    height: '100%', width: `${(C.epreuveTimeLeftSec / Math.max(1, C.epreuveDurationSec)) * 100}%`,
                    background: C.epreuveTimeLeftSec < 60 ? ACCENT : `linear-gradient(90deg, ${ACCENT}, #ffffff66)`,
                    transition: 'width .5s linear',
                  }} />
                </div>
                <div style={{ ...mono, fontSize: 10.5, color: DIM, display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
                  <span>obj {C.completedCount}/{C.lab?.objectives.length ?? 0}</span>
                  <span>indices {C.hintsUsedInRun} · −{C.hintCostInRun}</span>
                  {C.allDone && <span style={{ color: OK }}>tous validés</span>}
                </div>
              </>
            )}

            {C.mode === 'libre' && C.epreuveResult && (
              <div style={{ padding: 10, borderRadius: 12, background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)' }}>
                <div style={{ fontWeight: 750, fontSize: 14, color: C.epreuveResult.timeoutHit ? WARN : C.epreuveResult.completed === C.epreuveResult.total ? OK : DIM }}>
                  {C.epreuveResult.timeoutHit ? 'Temps écoulé' : C.epreuveResult.completed === C.epreuveResult.total ? 'Épreuve réussie' : 'Épreuve abandonnée'}
                </div>
                <div style={{ ...mono, fontSize: 11, color: DIM, display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 6 }}>
                  <span>score <b style={{ color: ACCENT }}>{C.epreuveResult.score}</b></span>
                  <span>{C.epreuveResult.completed}/{C.epreuveResult.total} obj</span>
                  <span>{Math.floor(C.epreuveResult.timeUsedSec / 60)}m {C.epreuveResult.timeUsedSec % 60}s</span>
                  <span>{C.epreuveResult.hintsUsed} indice(s)</span>
                </div>
              </div>
            )}

            {C.mode === 'libre' && !C.lab && (
              <div style={{ ...mono, fontSize: 11, color: MUTE }}>Forge un lab pour armer le mode epreuve.</div>
            )}
            {C.mode === 'libre' && C.lab && !C.epreuveResult && (
              <div style={{ ...mono, fontSize: 11, color: MUTE }}>Choisis une durée pour démarrer la course chrono, ou entraîne-toi librement.</div>
            )}

            {C.lab && (
              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                <Btn variant="ghost" onClick={C.exportLabSessionMarkdown} title="Exporter le labo + objectifs + journal en .md"
                  style={{ padding: '5px 11px', fontSize: 11 }}>
                  <Download size={12} /> Export .md
                </Btn>
              </div>
            )}
          </Card>

          {C.epreuveRunsForActive.length > 0 && (
            <Card className="cyber-rise" accent style={{ animationDelay: '.34s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Label dot={ACCENT}>Top scores · épreuve</Label>
                <span style={{ flex: 1 }} />
                {epreuveScores.length >= 2 && <Sparkline values={epreuveScores} width={72} height={18} color={ACCENT} />}
                <span style={{ ...mono, fontSize: 10, color: MUTE }}>{C.epreuveRunsForActive.length} run(s)</span>
              </div>
              {C.bestScoreForActive && (
                <div style={{ ...mono, fontSize: 10.5, color: DIM, marginBottom: 8 }}>
                  Meilleur · <b style={{ color: ACCENT }}>{C.bestScoreForActive.score ?? 0}</b> pts · étape {C.bestScoreForActive.stage}
                </div>
              )}
              {C.epreuveRunsForActive.slice().sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 3).map((r, i) => (
                <div key={r.startedAt} className="cyber-log" style={{
                  display: 'flex', alignItems: 'baseline', gap: 8, padding: '5px 0', ...mono, fontSize: 11,
                  animationDelay: `${0.38 + i * 0.06}s`,
                  borderTop: i > 0 ? '1px dashed rgba(255,255,255,.06)' : 'none',
                }}>
                  <span style={{ width: 16, color: MUTE }}>{i + 1}</span>
                  <span style={{ fontWeight: 700, color: ACCENT, minWidth: 46, fontVariantNumeric: 'tabular-nums' }}>{r.score ?? 0}</span>
                  <span style={{ color: DIM }}>{r.objectivesDone}/{r.totalObjectives} obj</span>
                  <span style={{ color: MUTE }}>{r.hintsTaken} ind.</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ color: MUTE }}>{Math.floor(r.durationMs / 1000 / 60)}m {Math.floor(r.durationMs / 1000) % 60}s</span>
                </div>
              ))}
            </Card>
          )}

          {C.runsForActive.length === 0 && (
            <Card className="cyber-rise" style={{ animationDelay: '.38s' }}>
              <Label>Historique · {C.active.name}</Label>
              <div style={{ ...mono, fontSize: 11, color: MUTE, marginTop: 8, lineHeight: 1.5 }}>
                Aucune run sur cette mission — sois le premier a la completer.
              </div>
            </Card>
          )}

          {C.runsForActive.length > 0 && (
            <Card className="cyber-rise" style={{ animationDelay: '.38s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Label>Historique · {C.active.name}</Label>
                <span style={{ flex: 1 }} />
                <span style={{ ...mono, fontSize: 10, color: MUTE }}>{C.runsForActive.length} run(s)</span>
              </div>
              {(() => {
                const runs = C.runsForActive
                const done = runs.filter((r) => r.objectivesDone >= r.totalObjectives).length
                const sr = Math.round((done / runs.length) * 100)
                const avg = Math.round(runs.reduce((s, r) => s + r.durationMs, 0) / runs.length)
                const xpT = runs.reduce((s, r) => s + (r.xpEarned || 0), 0)
                const cells = [
                  { k: 'réussite', v: `${sr}%`, c: sr >= 75 ? OK : sr >= 50 ? WARN : ACCENT },
                  { k: 'temps moy', v: fmtDur(avg), c: FG },
                  { k: 'xp total', v: `${xpT}`, c: ACCENT },
                ]
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginBottom: 10 }}>
                    {cells.map((c) => (
                      <div key={c.k} style={{ padding: '8px 10px', borderRadius: 10, background: 'rgba(255,255,255,.03)' }}>
                        <div style={{ ...monoLabel, fontSize: 9 }}>{c.k}</div>
                        <div style={{ ...mono, fontSize: 14, fontWeight: 700, color: c.c, marginTop: 3 }}>{c.v}</div>
                      </div>
                    ))}
                  </div>
                )
              })()}
              {C.bestForActive && (
                <div style={{ ...mono, fontSize: 10.5, color: MUTE, marginBottom: 8 }}>
                  Record vitesse · {fmtDur(C.bestForActive.durationMs)} · étape {C.bestForActive.stage}
                </div>
              )}
              {C.runsForActive.slice(0, 4).map((r, i) => (
                <div key={i} className="cyber-log" style={{
                  display: 'grid', gridTemplateColumns: '20px 1fr auto auto', gap: 10, ...mono, fontSize: 11, padding: '4px 0',
                  animationDelay: `${0.42 + i * 0.05}s`,
                  color: i === 0 ? ACCENT : DIM,
                }}>
                  <span style={{ color: MUTE }}>{String(i + 1).padStart(2, '0')}</span>
                  <span>étape {r.stage} · {r.flagsFound} flag(s)</span>
                  <span>{Math.round(r.durationMs / 1000)}s</span>
                  <span style={{ color: ACCENT }}>+{r.xpEarned}xp</span>
                </div>
              ))}
            </Card>
          )}

          <Card className="cyber-rise" style={{ animationDelay: '.44s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Label dot={C.notesName ? ACCENT : undefined}>Notes / writeup</Label>
              <span style={{ flex: 1 }} />
              {C.notesUploading && <Loader2 size={13} style={{ animation: 'cyberSpin 1s linear infinite', color: DIM }} />}
            </div>
            <p style={{ margin: '8px 0 10px', fontSize: 11.5, lineHeight: 1.5, color: MUTE }}>
              Charge ou colle un writeup — il sert de contexte à l'évaluateur IA. Glisser-déposer accepté.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <label title="Charger un ou plusieurs fichiers (.txt/.md/.pdf/.docx)"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, cursor: C.notesUploading ? 'wait' : 'pointer',
                  fontSize: 11.5, padding: '8px 12px', borderRadius: 11, border: '1px solid rgba(255,255,255,.14)',
                  background: 'rgba(255,255,255,.03)', color: DIM,
                }}>
                <Upload size={13} /> Charger
                <input type="file" multiple disabled={C.notesUploading}
                  accept=".txt,.md,.markdown,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => { const fs = Array.from(e.target.files || []); if (fs.length) void C.uploadNotesMulti(fs); e.target.value = '' }}
                  style={{ display: 'none' }} />
              </label>
              <Btn variant="ghost" disabled={C.notesUploading} onClick={() => void C.pasteNotesFromClipboard()} title="Coller depuis le presse-papiers">
                <Clipboard size={13} /> Coller
              </Btn>
              {C.notesName && (
                <Btn variant="ghost" onClick={C.clearNotes} title="Retirer les notes" style={{ padding: '8px 11px' }}>
                  <X size={13} /> Retirer
                </Btn>
              )}
            </div>
            {C.notesName && (
              <div style={{ marginTop: 10 }}>
                <button type="button" onClick={() => setNotesOpen((v) => !v)}
                  style={{ width: '100%', background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.09)', borderRadius: 11, padding: '8px 11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: FG }}>
                  <span style={{ ...mono, fontSize: 11, color: ACCENT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{C.notesName}</span>
                  {notesEdited && <span style={{ ...mono, fontSize: 9, color: WARN, letterSpacing: '.12em', textTransform: 'uppercase' }}>édité</span>}
                  <span style={{ flex: 1 }} />
                  <span style={{ ...mono, fontSize: 10, color: MUTE }}>{C.notesText.length} car.</span>
                  <ChevronDown size={14} color={DIM} style={{ transform: notesOpen ? 'rotate(180deg)' : 'none', transition: 'transform .25s' }} />
                </button>
                {notesOpen && (
                  <textarea
                    value={C.notesText}
                    onChange={(e) => C.setNotesText(e.target.value)}
                    rows={6}
                    style={{ ...inputBase, width: '100%', marginTop: 8, padding: 10, fontSize: 12, ...mono, resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.5 }}
                  />
                )}
              </div>
            )}
          </Card>

        </div>

        <div style={{ position: 'sticky', top: 8 }}>
          <Card className="cyber-log" style={{ padding: 0, overflow: 'hidden', height: 'calc(100vh - 128px)', display: 'flex', flexDirection: 'column', minHeight: 0, animationDelay: '.1s' }}>
            {C.lab ? (
              <>
                <div style={{ padding: '13px 18px', borderBottom: '1px solid rgba(255,255,255,.09)', display: 'flex', alignItems: 'center', gap: 12, background: `linear-gradient(90deg, ${ACCENT}0d, transparent 55%)` }}>
                  <Label dot={ACCENT} style={{ minWidth: 0 }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Atelier · {C.lab.title}</span>
                  </Label>
                  <span style={{ flex: 1 }} />
                  <span style={{ ...mono, fontSize: 11, color: DIM }}>{C.completedCount}/{C.lab.objectives.length} · {C.progressPct}%</span>
                  <button type="button" onClick={C.reloadSandbox} title="Recharger le labo"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: DIM, display: 'flex' }}>
                    <RefreshCw size={14} />
                  </button>
                  <button type="button" onClick={C.closeLab} title="Fermer le labo"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: DIM, display: 'flex' }}>
                    <X size={15} />
                  </button>
                </div>

                {C.lab.briefing && (
                  <div style={{ padding: '11px 18px', fontSize: 12.5, lineHeight: 1.55, color: DIM, borderBottom: '1px solid rgba(255,255,255,.06)', position: 'relative' }}>
                    {C.lab.briefing}
                    <button type="button" title={briefingCopied ? 'Copié' : 'Copier le briefing'}
                      onClick={async () => { try { if (C.lab?.briefing) { await navigator.clipboard.writeText(C.lab.briefing); setBriefingCopied(true) } } catch { void 0 } }}
                      style={{
                        position: 'absolute', top: 8, right: 10, padding: '3px 9px', ...mono, fontSize: 9,
                        borderRadius: 8, cursor: 'pointer',
                        background: briefingCopied ? `${ACCENT}22` : 'transparent',
                        color: briefingCopied ? ACCENT : MUTE,
                        border: `1px solid ${briefingCopied ? `${ACCENT}66` : 'rgba(255,255,255,.16)'}`,
                      }}>
                      {briefingCopied ? 'copié' : 'copier'}
                    </button>
                  </div>
                )}

                <iframe
                  key={`${C.lab.kataId}-${C.sandboxKey}`}
                  title="Labo cyber Aurora"
                  srcDoc={C.lab.html}
                  sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
                  style={{ flex: 1, width: '100%', border: 'none', background: '#0b0d13', minHeight: 180 }}
                />

                <div style={{ padding: '9px 18px', display: 'flex', gap: 8, alignItems: 'center', borderTop: '1px solid rgba(255,255,255,.09)', background: 'rgba(255,255,255,.02)' }}>
                  <input type="text" value={C.evolveHint}
                    onChange={(e) => C.setEvolveHint(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && C.evolveHint.trim() && !C.labLoading) { e.preventDefault(); void C.evolveLab() } }}
                    placeholder="Fais évoluer le labo (ex : ajoute un visualiseur hexa · rends-le plus dur)…"
                    style={{ ...inputBase, flex: 1, padding: '8px 11px', fontSize: 12, ...mono }} />
                  <VoicePushToTalk
                    onTranscript={(text) => C.setEvolveHint((C.evolveHint ? C.evolveHint + ' ' : '') + text)}
                    label="Dicter la mutation du labo"
                    disabled={C.labLoading}
                    variant="ghost"
                    size={30}
                  />
                  <Btn variant="ghost" onClick={() => void C.evolveLab()} disabled={!C.evolveHint.trim() || C.labLoading} style={{ padding: '8px 13px' }}>
                    {C.labLoading ? <Loader2 size={13} style={{ animation: 'cyberSpin 1s linear infinite' }} /> : <Wand2 size={13} />} Évoluer
                  </Btn>
                </div>

                <div style={{ padding: '11px 18px', maxHeight: 240, overflowY: 'auto', borderTop: '1px solid rgba(255,255,255,.09)', background: 'rgba(255,255,255,.015)' }}>
                  <Label dot={ACCENT} style={{ marginBottom: 8 }}>Objectifs</Label>
                  {C.lab.objectives.map((obj) => {
                    const done = C.doneObjectives.has(obj.id)
                    const grade = C.grades[obj.id]
                    const hints = C.deepHints[obj.id] || []
                    return (
                      <div key={obj.id} style={{ padding: '6px 0', borderTop: '1px solid rgba(255,255,255,.05)' }}>
                        <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
                          <button type="button" onClick={() => C.toggleObjective(obj.id)}
                            style={{
                              width: 19, height: 19, borderRadius: 6, flexShrink: 0, marginTop: 1, cursor: 'pointer',
                              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                              background: done ? ACCENT : 'transparent',
                              border: `1px solid ${done ? ACCENT : 'rgba(255,255,255,.18)'}`,
                              color: '#0A0F1E',
                            }}>{done && <Check size={12} strokeWidth={3} />}</button>
                          <div style={{ flex: 1, fontSize: 12.5, lineHeight: 1.45, color: done ? MUTE : FG, textDecoration: done ? 'line-through' : 'none' }}>
                            {obj.text}
                          </div>
                          <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                            <button type="button" onClick={() => C.setGraderFor(C.graderFor === obj.id ? null : obj.id)}
                              title="Faire évaluer ta réponse par l'IA"
                              style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 8, cursor: 'pointer', background: C.graderFor === obj.id ? `${ACCENT}22` : 'transparent', color: ACCENT, border: `1px solid ${ACCENT}55` }}>
                              valider
                            </button>
                            {[1, 2, 3].map((lvl) => {
                              const taken = hints.some((h) => h.level === lvl)
                              return (
                                <button key={lvl} type="button" disabled={!!C.deepHintBusy || taken}
                                  onClick={() => void C.askDeepHint(obj, lvl as 1 | 2 | 3)}
                                  title={`Indice niveau ${lvl}`}
                                  style={{
                                    ...mono, fontSize: 10, padding: '3px 7px', borderRadius: 8,
                                    cursor: taken ? 'default' : 'pointer',
                                    display: 'inline-flex', alignItems: 'center', gap: 2,
                                    background: taken ? `${WARN}22` : 'transparent',
                                    color: taken ? WARN : DIM,
                                    border: `1px solid ${taken ? `${WARN}55` : 'rgba(255,255,255,.14)'}`,
                                  }}>
                                  <Lightbulb size={9} />{lvl}
                                </button>
                              )
                            })}
                          </div>
                        </div>

                        {hints.map((h, i) => (
                          <div key={i} style={{ ...mono, fontSize: 11, color: DIM, lineHeight: 1.45, marginTop: 6, marginLeft: 28, paddingLeft: 8, borderLeft: `2px solid ${WARN}44` }}>
                            <span style={{ color: WARN }}>Indice niv.{h.level}</span> (−{h.xp} XP) — {h.body}
                          </div>
                        ))}

                        {C.graderFor === obj.id && (
                          <div style={{ marginTop: 8, marginLeft: 28 }}>
                            <textarea rows={2}
                              value={C.graderAnswer[obj.id] || ''}
                              onChange={(e) => C.setGraderAnswer({ ...C.graderAnswer, [obj.id]: e.target.value })}
                              placeholder={obj.flag ? 'Colle le flag…' : 'Ta réponse…'}
                              style={{ ...inputBase, width: '100%', padding: 8, fontSize: 12, ...mono, resize: 'vertical', boxSizing: 'border-box' }} />
                            <div style={{ marginTop: 6 }}>
                              <Btn variant="primary" disabled={!!C.graderBusy || !(C.graderAnswer[obj.id] || '').trim()}
                                onClick={() => void C.gradeCyberObjective(obj, (C.graderAnswer[obj.id] || '').trim())}
                                style={{ padding: '7px 14px' }}>
                                {C.graderBusy === obj.id ? <><Loader2 size={12} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Évaluation…</> : <><Target size={12} /> Évaluer</>}
                              </Btn>
                            </div>
                          </div>
                        )}

                        {grade && (
                          <div style={{ marginTop: 8, marginLeft: 28, padding: 9, borderRadius: 10, background: 'rgba(255,255,255,.03)', border: `1px solid ${verdictColor(grade.verdict)}44` }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ ...mono, fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: verdictColor(grade.verdict), fontWeight: 700 }}>{grade.verdict}</span>
                              <span style={{ flex: 1 }} />
                              <span style={{ ...mono, fontSize: 11, color: verdictColor(grade.verdict), fontWeight: 700 }}>{grade.score}/100</span>
                            </div>
                            {grade.summary && <div style={{ fontSize: 12, lineHeight: 1.45, color: DIM, marginTop: 5 }}>{grade.summary}</div>}
                            {grade.next_step && <div style={{ fontSize: 11.5, lineHeight: 1.45, color: MUTE, marginTop: 4 }}>Prochaine étape · {grade.next_step}</div>}
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {C.allDone && (
                    <div style={{
                      marginTop: 10, padding: 11, borderRadius: 12, display: 'flex', alignItems: 'center', gap: 10,
                      background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`, color: '#0A0F1E', fontWeight: 750,
                    }}>
                      <Sparkles size={15} />
                      <span style={{ flex: 1, fontSize: 13 }}>Atelier complété — +{C.active.difficulty * 30} XP</span>
                      {C.stage < 4 && (
                        <button type="button" onClick={C.advanceStage}
                          style={{ ...mono, fontSize: 11.5, fontWeight: 700, padding: '6px 12px', borderRadius: 10, cursor: 'pointer', background: '#0A0F1E', color: FG, border: 'none' }}>
                          Étape {C.stage + 1}/4
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div style={{ padding: '22px 24px 18px', borderBottom: '1px solid rgba(255,255,255,.06)', display: 'flex', flexDirection: 'column', gap: 13 }}>
                  <div className="cyber-empty-head" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <span className="cyber-float" style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}>
                      <span aria-hidden style={{
                        position: 'absolute', inset: -24, borderRadius: '50%', pointerEvents: 'none',
                        background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`,
                        animation: 'cyberHalo 3.6s ease-in-out infinite',
                      }} />
                      <span aria-hidden style={{
                        position: 'absolute', inset: -9, borderRadius: '50%', pointerEvents: 'none',
                        border: `1px dashed ${ACCENT}4d`,
                        animation: 'cyberSpin 16s linear infinite',
                      }} />
                      <span style={{ position: 'relative', filter: `drop-shadow(0 0 22px ${ACCENT}44)` }}>
                        <AuroraMascot module="cyber" size={90} state={C.labLoading || C.briefStatus === 'thinking' || C.toolStrategyStatus === 'thinking' ? 'working' : 'idle'} />
                      </span>
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Label dot={C.briefStatus === 'thinking' || C.toolStrategyStatus === 'thinking' ? ACCENT : undefined}>
                        {C.briefAnswer || C.toolStrategyAnswer || C.briefStatus !== 'idle' || C.toolStrategyStatus !== 'idle' ? 'Mission cyber' : 'Demande ou lab'}
                      </Label>
                      <div style={{
                        marginTop: 7, fontSize: 21, fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.2,
                        background: `linear-gradient(110deg, #FFFFFF 45%, #FFD9E1 78%, ${ACCENT})`,
                        WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
                      }}>
                        {C.toolStrategyAnswer ? 'Strategie outillee.' : C.briefAnswer ? 'Mission clarifiee.' : 'Pose une demande, Aurora prepare le plan.'}
                      </div>
                      <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.55, color: DIM }}>
                        Utilise la barre a gauche pour cadrer le perimetre, preparer les outils reels, analyser des artefacts ou forger un lab interactif.
                      </div>
                    </div>
                    <Btn variant="primary" onClick={C.launchKata} disabled={C.labLoading}>
                      {C.labLoading
                        ? <><Loader2 size={14} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Forge…</>
                        : <><Play size={14} fill="currentColor" /> Lab {C.active.discipline}</>}
                    </Btn>
                  </div>
                  <div style={{ ...mono, fontSize: 11, color: MUTE, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span style={pillMeta}>posture · <b style={{ color: DIM }}>{C.stance === 'offense' ? 'attaque sandbox/audit' : 'défense/incident'}</b></span>
                    <span style={pillMeta}>mission · <b style={{ color: DIM }}>{C.active.name}</b></span>
                    <span style={pillMeta}>perimetre · <b style={{ color: C.scopeAuthorized ? OK : WARN }}>{C.scopeAuthorized ? 'confirme' : 'a confirmer'}</b></span>
                    <span style={pillMeta}>ceinture · <b style={{ color: DIM }}>{C.belt}</b> ({C.xp} XP)</span>
                  </div>
                  {(C.briefStatus === 'thinking' || C.briefError || C.briefAnswer) && (
                    <div style={{ marginTop: 2, padding: '12px 14px', borderRadius: 13, background: 'rgba(255,255,255,.025)', border: '1px solid rgba(255,255,255,.08)', maxHeight: 430, overflowY: 'auto' }}>
                      {C.briefStatus === 'thinking' && !C.briefAnswer && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: DIM, ...mono, fontSize: 12 }}>
                          <Loader2 size={14} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Construction du briefing…
                        </div>
                      )}
                      {C.briefError && (
                        <div style={{ color: WARN, ...mono, fontSize: 12, lineHeight: 1.5 }}>
                          {C.briefError}
                        </div>
                      )}
                      {C.briefAnswer && (
                        <MarkdownPro content={C.briefAnswer} idPrefix="cyber-brief" className="cyber-brief-md" />
                      )}
                    </div>
                  )}
                  {(C.toolStrategyStatus === 'thinking' || C.toolStrategyError || C.toolStrategyAnswer) && (
                    <div style={{ marginTop: 2, padding: '12px 14px', borderRadius: 13, background: 'rgba(255,255,255,.025)', border: `1px solid ${ACCENT}22`, maxHeight: 430, overflowY: 'auto' }}>
                      {C.toolStrategyStatus === 'thinking' && !C.toolStrategyAnswer && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: DIM, ...mono, fontSize: 12 }}>
                          <Loader2 size={14} style={{ animation: 'cyberSpin 1s linear infinite' }} /> Selection et auto-configuration des outils…
                        </div>
                      )}
                      {C.toolStrategyError && (
                        <div style={{ color: WARN, ...mono, fontSize: 12, lineHeight: 1.5 }}>
                          {C.toolStrategyError}
                        </div>
                      )}
                      {C.toolStrategyAnswer && (
                        <MarkdownPro content={C.toolStrategyAnswer} idPrefix="cyber-tools" className="cyber-brief-md" />
                      )}
                    </div>
                  )}
                  {ActiveToolBench && (
                    <div style={{ marginTop: 2, borderRadius: 13, background: 'rgba(0,0,0,.22)', border: '1px solid rgba(255,255,255,.08)', maxHeight: 560, overflowY: 'auto', padding: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                        <TerminalSquare size={14} color={ACCENT} />
                        <Label>Atelier outils reels</Label>
                        <span style={{ flex: 1 }} />
                        <button type="button" onClick={() => setActiveToolBench(null)}
                          style={{ background: 'transparent', border: 'none', color: DIM, cursor: 'pointer', display: 'flex' }}
                          title="Fermer l'atelier">
                          <X size={14} />
                        </button>
                      </div>
                      <Suspense fallback={<div style={{ ...mono, color: DIM, fontSize: 12 }}>Chargement de l'atelier…</div>}>
                        <ActiveToolBench />
                      </Suspense>
                    </div>
                  )}
                </div>

                <div className="cyber-term" style={{ flex: 1, padding: 20, ...mono, fontSize: 12, lineHeight: 1.7, color: DIM, overflowY: 'auto' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: MUTE, marginBottom: 10 }}>
                    <TerminalSquare size={14} /> journal de session
                  </div>
                  {C.logs.length === 0 && <div style={{ color: MUTE }}>— rien pour l'instant —</div>}
                  {C.logs.slice(-14).map((l) => (
                    <div key={l.id} className="cyber-log" style={{ fontSize: 11.5, marginBottom: 4, color: toneColor(l.tone) }}>{l.text}</div>
                  ))}
                  <div ref={logEndRef} style={{ marginTop: 10, color: ACCENT }}>
                    $ <span style={{ borderRight: `8px solid ${ACCENT}`, animation: 'cyberBlink 1s steps(2) infinite' }}>&nbsp;</span>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
      )}
    </div>
  )
}
