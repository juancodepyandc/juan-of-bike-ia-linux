import { Suspense, lazy, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Binary,
  FileSearch,
  Fingerprint,
  Flag,
  Globe,
  KeyRound,
  Lock,
  Network,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from 'lucide-react'

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
  | 'crypto'
  | 'hash'
  | 'password'
  | 'network'
  | 'forensics'
  | 'web'
  | 'stego'
  | 'ctf'
  | 'threat'

interface CyberTab {
  id: CyberTabId
  label: string
  kicker: string
  icon: typeof ShieldCheck
  color: string
}

const TABS: CyberTab[] = [
  { id: 'crypto',    label: 'Cryptographie',  kicker: 'AES · RSA · chiffres classiques', icon: Lock,         color: '#ef4444' },
  { id: 'hash',      label: 'Hashing',         kicker: 'MD5 · SHA · HMAC · cracking',    icon: Fingerprint,  color: '#f97316' },
  { id: 'password',  label: 'Mots de passe',   kicker: 'Entropie · bruteforce · policies', icon: KeyRound,  color: '#f59e0b' },
  { id: 'network',   label: 'Réseau',          kicker: 'Scan · DNS · TLS · sniffing',    icon: Network,      color: '#3b82f6' },
  { id: 'forensics', label: 'Forensics',       kicker: 'Hex · strings · metadata · EXIF', icon: FileSearch,  color: '#8b5cf6' },
  { id: 'web',       label: 'Web Security',    kicker: 'XSS · SQLi · CSRF · JWT',        icon: Globe,        color: '#10b981' },
  { id: 'stego',     label: 'Stéganographie',  kicker: 'LSB · images · audio',           icon: Binary,       color: '#06b6d4' },
  { id: 'ctf',       label: 'CTF',             kicker: 'Défis progressifs · flags',      icon: Flag,         color: '#ec4899' },
  { id: 'threat',    label: 'Threat Intel',    kicker: 'CVE · MITRE · OSINT',            icon: Radar,        color: '#a855f7' },
]

export default function CyberView() {
  const [activeTab, setActiveTab] = useState<CyberTabId>('crypto')

  const tab = useMemo(() => TABS.find((t) => t.id === activeTab) ?? TABS[0], [activeTab])

  const Active = useMemo(() => {
    switch (activeTab) {
      case 'crypto':    return CryptoLab
      case 'hash':      return HashLab
      case 'password':  return PasswordLab
      case 'network':   return NetworkLab
      case 'forensics': return ForensicsLab
      case 'web':       return WebSecLab
      case 'stego':     return SteganographyLab
      case 'ctf':       return CTFLab
      case 'threat':    return ThreatIntelLab
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
            <div className="text-[11px] uppercase tracking-[0.22em] text-red-300/70 font-semibold">Aurora · Cyber Lab</div>
            <h1 className="text-lg font-semibold text-white">Apprendre · Tester · Défendre</h1>
          </div>
          <div className="ml-auto flex items-center gap-2 text-[11px] text-white/50">
            <Terminal size={12} />
            <span>exécution locale · aucune cible externe</span>
          </div>
        </div>
        <p className="text-[12px] text-white/55 leading-relaxed max-w-3xl">
          Laboratoire cybersécurité autonome : cryptographie, réseau, forensics et CTF pour apprendre les fondamentaux,
          comprendre les attaques et renforcer la défense. Tous les outils s'exécutent <strong className="text-red-300">localement</strong> sur ta machine
          sans jamais émettre de requête réseau non sollicitée.
        </p>
      </div>

      <div className="shrink-0 overflow-x-auto no-scrollbar border-b border-white/[0.04] bg-black/30">
        <div className="flex gap-1 px-3 py-2 min-w-max">
          {TABS.map((t) => {
            const Icon = t.icon
            const active = t.id === activeTab
            return (
              <motion.button
                key={t.id}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => setActiveTab(t.id)}
                className={`group flex items-center gap-2 rounded-xl border px-3 py-2 transition-colors ${
                  active
                    ? 'border-white/15 text-white'
                    : 'border-white/5 bg-white/[0.02] text-white/55 hover:text-white/80 hover:bg-white/[0.04]'
                }`}
                style={active ? { background: `linear-gradient(135deg, ${t.color}26, rgba(255,255,255,0.04))`, boxShadow: `0 0 0 1px ${t.color}55, 0 6px 20px ${t.color}33` } : undefined}
              >
                <Icon size={14} className={active ? '' : 'opacity-70'} style={active ? { color: t.color } : undefined} />
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
        <Suspense fallback={<div className="text-white/40 text-sm">Chargement du lab {tab.label}…</div>}>
          {Active ? <Active /> : null}
        </Suspense>
      </div>
    </div>
  )
}
