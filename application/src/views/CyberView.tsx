import { Suspense, lazy, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Binary,
  Brain,
  Bug,
  FileSearch,
  Fingerprint,
  Flag,
  Globe,
  KeyRound,
  Lock,
  Network,
  Radar,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Swords,
  Terminal,
} from 'lucide-react'

const WarRoomLab = lazy(() => import('./cyber/WarRoomLab'))
const AutonomousInvestigatorLab = lazy(() => import('./cyber/AutonomousInvestigatorLab'))
const DynamicZeroDayLab = lazy(() => import('./cyber/DynamicZeroDayLab'))
const SymbolicExecutionLab = lazy(() => import('./cyber/SymbolicExecutionLab'))
const BinaryDisassemblyLab = lazy(() => import('./cyber/BinaryDisassemblyLab'))
const EbpfKernelLab = lazy(() => import('./cyber/EbpfKernelLab'))
const SoarPlaybookLab = lazy(() => import('./cyber/SoarPlaybookLab'))
const ZeroDayLab = lazy(() => import('./cyber/ZeroDayLab'))
const AttackGraphLab = lazy(() => import('./cyber/AttackGraphLab'))
const DeepReasoningLab = lazy(() => import('./cyber/DeepReasoningLab'))
const WebAuditorLab = lazy(() => import('./cyber/WebAuditorLab'))
const CryptoLab = lazy(() => import('./cyber/CryptoLab'))
const HashLab = lazy(() => import('./cyber/HashLab'))
const PasswordLab = lazy(() => import('./cyber/PasswordLab'))
const NetworkLab = lazy(() => import('./cyber/NetworkLab'))
const ForensicsLab = lazy(() => import('./cyber/ForensicsLab'))
const WebSecLab = lazy(() => import('./cyber/WebSecLab'))
const SteganographyLab = lazy(() => import('./cyber/SteganographyLab'))
const CTFLab = lazy(() => import('./cyber/CTFLab'))
const ThreatIntelLab = lazy(() => import('./cyber/ThreatIntelLab'))

type CyberTabId =
  | 'warroom'
  | 'investigator'
  | 'dynamic0day'
  | 'symbolic'
  | 'binary'
  | 'ebpf'
  | 'soar'
  | 'zeroday'
  | 'attackgraph'
  | 'deepreasoning'
  | 'webaudit'
  | 'network'
  | 'web'
  | 'threat'
  | 'forensics'
  | 'crypto'
  | 'hash'
  | 'password'
  | 'stego'
  | 'ctf'

interface CyberTab {
  id: CyberTabId
  label: string
  kicker: string
  icon: typeof ShieldCheck
  color: string
  highlight?: boolean
}

const TABS: CyberTab[] = [
  { id: 'warroom',       label: 'War Room IA',    kicker: 'Red vs Blue · Attaque/Défense Auto', icon: Swords,       color: '#f43f5e', highlight: true },
  { id: 'investigator',  label: 'Enquêteur IA',   kicker: 'Recherche Autonome · Threat Intel', icon: Radar,        color: '#fb7185', highlight: true },
  { id: 'dynamic0day',   label: '0-Day Dynamique', kicker: 'Invariants & Déduction Inédite',   icon: Brain,        color: '#e11d48', highlight: true },
  { id: 'symbolic',      label: 'Solveur SMT',     kicker: 'Exécution Symbolique · Preuves Z3',  icon: Brain,        color: '#f59e0b', highlight: true },
  { id: 'binary',        label: 'Désassembleur',   kicker: 'x86_64 · CFG · ROP Gadgets',        icon: Binary,       color: '#06b6d4', highlight: true },
  { id: 'ebpf',          label: 'Noyau eBPF / LSM', kicker: 'Sondes Ring 0 · XDP Anti-DDoS',    icon: Network,      color: '#10b981', highlight: true },
  { id: 'soar',          label: 'Riposte SOAR',    kicker: 'Orchestration d\'Incident Auto',     icon: Flag,         color: '#6366f1', highlight: true },
  { id: 'zeroday',       label: 'Lab Fuzzing',     kicker: 'UAF · BOF/ROP · Mitigations',       icon: Bug,          color: '#fb7185', highlight: true },
  { id: 'attackgraph',   label: 'Graphe d\'Attaque', kicker: 'Connexions · Blast Radius · Pivots', icon: Share2,  color: '#38bdf8', highlight: true },
  { id: 'deepreasoning', label: 'Raisonnement IA', kicker: 'Dissection · Root Cause · Playbook', icon: Brain,     color: '#c084fc', highlight: true },
  { id: 'webaudit',      label: 'Audit Web & DoS', kicker: 'Analyse Endpoint · Durcissement', icon: Globe,       color: '#34d399', highlight: true },
  { id: 'network',       label: 'Réseau',          kicker: 'Scan · DNS · TLS · Sniffing',       icon: Network,     color: '#3b82f6' },
  { id: 'web',           label: 'Web Security',    kicker: 'XSS · SQLi · CSRF · JWT',           icon: Globe,       color: '#10b981' },
  { id: 'threat',        label: 'Threat Intel',    kicker: 'CVE · MITRE · OSINT',               icon: Radar,       color: '#a855f7' },
  { id: 'forensics',     label: 'Forensics',       kicker: 'Hex · Strings · EXIF · Memory',     icon: FileSearch,  color: '#8b5cf6' },
  { id: 'crypto',        label: 'Cryptographie',   kicker: 'AES · RSA · Chiffres classiques',   icon: Lock,        color: '#ef4444' },
  { id: 'hash',          label: 'Hashing',         kicker: 'MD5 · SHA · Cracking · Salt',       icon: Fingerprint, color: '#f97316' },
  { id: 'password',      label: 'Mots de passe',   kicker: 'Entropie · Bruteforce · Policies',  icon: KeyRound,    color: '#f59e0b' },
  { id: 'stego',         label: 'Stéganographie',  kicker: 'LSB · Images · Audio',              icon: Binary,      color: '#06b6d4' },
  { id: 'ctf',           label: 'CTF Dojo',        kicker: 'Défis progressifs · Flags',         icon: Flag,        color: '#ec4899' },
]

export default function CyberView() {
  const [activeTab, setActiveTab] = useState<CyberTabId>('warroom')

  const tab = useMemo(() => TABS.find((t) => t.id === activeTab) ?? TABS[0]!, [activeTab])

  const Active = useMemo(() => {
    switch (activeTab) {
      case 'warroom':       return WarRoomLab
      case 'investigator':  return AutonomousInvestigatorLab
      case 'dynamic0day':   return DynamicZeroDayLab
      case 'symbolic':      return SymbolicExecutionLab
      case 'binary':        return BinaryDisassemblyLab
      case 'ebpf':          return EbpfKernelLab
      case 'soar':          return SoarPlaybookLab
      case 'zeroday':       return ZeroDayLab
      case 'attackgraph':   return AttackGraphLab
      case 'deepreasoning': return DeepReasoningLab
      case 'webaudit':      return WebAuditorLab
      case 'crypto':        return CryptoLab
      case 'hash':          return HashLab
      case 'password':      return PasswordLab
      case 'network':       return NetworkLab
      case 'forensics':     return ForensicsLab
      case 'web':           return WebSecLab
      case 'stego':         return SteganographyLab
      case 'ctf':           return CTFLab
      case 'threat':        return ThreatIntelLab
    }
  }, [activeTab])

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      <div className="shrink-0 px-4 py-3 border-b border-white/[0.06] bg-gradient-to-br from-red-950/30 via-transparent to-transparent">
        <div className="flex items-center gap-3 mb-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-red-500/30 to-rose-600/30 border border-red-500/30">
            <ShieldAlert size={18} className="text-red-300" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-red-300/70 font-semibold">Aurora · Cyber Ops & Lab</div>
            <h1 className="text-lg font-semibold text-white">IA Défense / Attaque Autonome · 0-Day · Raisonnement Poussé</h1>
          </div>
          <div className="ml-auto flex items-center gap-2 text-[11px] text-white/50">
            <Terminal size={12} />
            <span>exécution locale & bac à sable préventif</span>
          </div>
        </div>
        <p className="text-[12px] text-white/55 leading-relaxed max-w-3xl">
          Plateforme cybersécurité intégrale : simulation autonome d'engagements Red vs Blue, entraînement sur failles 0-day avec fuzzing et dissection mémoire,
          graphe d'attaque systémique, et co-pilote IA pour le raisonnement approfondi.
        </p>
      </div>

      <div className="shrink-0 overflow-x-auto no-scrollbar border-b border-white/[0.04] bg-black/30">
        <div className="flex gap-1.5 px-3 py-2 min-w-max">
          {TABS.map((t) => {
            const Icon = t.icon
            const active = t.id === activeTab
            return (
              <motion.button
                key={t.id}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => setActiveTab(t.id)}
                className={`group flex items-center gap-2 rounded-xl border px-3 py-2 transition-colors cursor-pointer ${
                  active
                    ? 'border-white/15 text-white'
                    : t.highlight
                    ? 'border-white/10 bg-white/[0.03] text-white/80 hover:text-white hover:bg-white/[0.06]'
                    : 'border-white/5 bg-white/[0.015] text-white/55 hover:text-white/80 hover:bg-white/[0.04]'
                }`}
                style={
                  active
                    ? {
                        background: `linear-gradient(135deg, ${t.color}26, rgba(255,255,255,0.04))`,
                        boxShadow: `0 0 0 1px ${t.color}55, 0 6px 20px ${t.color}33`,
                      }
                    : undefined
                }
              >
                <Icon size={14} className={active ? '' : 'opacity-75'} style={active ? { color: t.color } : undefined} />
                <div className="text-left leading-tight">
                  <div className="text-[11px] font-semibold whitespace-nowrap">{t.label}</div>
                  <div className="text-[9px] text-white/40 whitespace-nowrap">{t.kicker}</div>
                </div>
              </motion.button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-4">
        <Suspense fallback={<div className="text-white/40 text-sm font-mono p-4">Initialisation du module {tab.label}…</div>}>
          {Active ? <Active /> : null}
        </Suspense>
      </div>
    </div>
  )
}
