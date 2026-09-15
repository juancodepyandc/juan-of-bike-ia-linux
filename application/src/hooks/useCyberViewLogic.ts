/**
 * useCyberViewLogic — Cyber dojo state extracted from MangaCyberView so
 * Aurora V1 (Editorial Kata 0341) and V3 (DEFCON red-alarm) can render
 * their own chrome over the same feature set:
 *   • 8 katas (crypto, network, forensics, web, stegano, hash, password, ctf)
 *   • XP-based belt progression (blanche → noire)
 *   • offense / defense stance toggle
 *   • multi-stage CTF (1..4) with leaderboard recording
 *   • lab forging via ollamaChat + LAB_SYSTEM prompt → autonomous HTML lab
 *   • lab evolution via free-form hint (auto preset suggestions)
 *   • objective auto-validation via window postMessage from sandbox
 *   • per-objective grading (correct/partial/off/incorrect) via labAssistant
 *   • 3-level deep hints with XP cost
 *   • secure log of every action
 *
 * Both ports must keep ALL of these. Only the visual surface differs.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useGenerationFxEmitter } from '../components/generationFx/fxBus.ts'
import { ollamaChat, ollamaChatStream } from './useTauri.ts'
import { getBuiltinFallbackLab } from '../services/cyber/builtinLabs.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useCyberLeaderboardStore } from '../stores/cyberLeaderboardStore.ts'
import { computeStreak } from '../utils/streak.ts'
import type { GradeResult } from '../services/labAssistant.ts'
import {
  BookLock, Bug, FileLock2, Fingerprint, Key, Network, ScanEye, Swords,
} from 'lucide-react'

export type Character = 'natsu' | 'lucy'
export const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

export type Belt = 'blanche' | 'jaune' | 'orange' | 'verte' | 'bleue' | 'marron' | 'noire'
export const BELTS: Belt[] = ['blanche', 'jaune', 'orange', 'verte', 'bleue', 'marron', 'noire']

export type Kata = {
  id: string
  name: string
  discipline: string
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; fill?: string }>
  tone: string
  difficulty: 1 | 2 | 3
  stance: string
  lesson: string
  labHint: string
}

export const KATAS: Kata[] = [
  { id: 'crypto',   name: 'Crypto attaque/defense',     discipline: 'Cryptographie', icon: Key,         tone: 'var(--color-mod-code, #6b9eff)',    difficulty: 2, stance: 'XOR · Vigenere · AES · RSA',   lesson: 'Casser, expliquer puis corriger des erreurs crypto : frequence, nonce reuse, IV, KDF.', labHint: 'console de chiffrement + attaques guidees + correctif crypto compare' },
  { id: 'network',  name: 'Recon reseau autorise',      discipline: 'Reseaux',       icon: Network,     tone: 'var(--color-mod-conv, #7df9c4)',    difficulty: 2, stance: 'TCP · Nmap · Wireshark',       lesson: 'Cartographier une surface exposee, lire les banners, prioriser les risques et les mitigations.', labHint: 'nmap simule avec ports, services, versions, faux bruit reseau et plan de durcissement' },
  { id: 'forensics',name: 'Incident & forensic',        discipline: 'Forensics',     icon: Fingerprint, tone: 'var(--color-mod-image, #c574ff)',   difficulty: 3, stance: 'logs · mem · disk · IOC',      lesson: "Reconstituer une compromission depuis logs, artefacts disque/RAM et indicateurs d'attaque.", labHint: 'dump memoire/disque a inspecter avec strings, hexdump, timeline, IOC et rapport' },
  { id: 'web',      name: 'Web app vuln exploitable',   discipline: 'Web Sec',       icon: Bug,         tone: 'var(--color-mod-drawing, #ffb947)', difficulty: 2, stance: 'XSS · SQLi · CSRF · SSRF',     lesson: 'Comprendre les failles OWASP sur une cible sandboxee, exploiter, prouver, puis patcher.', labHint: "mini app vulnerable simulee avec formulaire, payloads, logs serveur et correctif" },
  { id: 'stegano',  name: 'Stegano & exfil cachee',     discipline: 'Steganographie',icon: ScanEye,     tone: 'var(--color-mod-3d, #ff6a3d)',      difficulty: 1, stance: 'LSB · exif · audio',           lesson: "Detecter et extraire de l'information cachee dans image, metadata ou signal.", labHint: 'image canvas ou artefact audio a analyser avec extraction LSB/EXIF et flag derive' },
  { id: 'hash',     name: 'Hash cracking lab',          discipline: 'Hash & Salt',   icon: BookLock,    tone: 'var(--color-mod-learn, #ff4a4a)',   difficulty: 1, stance: 'MD5 · bcrypt · Argon2id',      lesson: 'Comparer hash faible, salage, cout KDF, rainbow table et defense de stockage.', labHint: 'calculateur live + dictionnaire limite + comparaison MD5/PBKDF2/bcrypt/Argon2id' },
  { id: 'password', name: 'Audit mots de passe',        discipline: 'Passwords',     icon: FileLock2,   tone: 'var(--color-mod-video, #6b9eff)',   difficulty: 1, stance: 'policy · wordlist · lockout',  lesson: 'Tester une politique de mots de passe et comprendre brute force, dictionnaires et lockout.', labHint: "simulateur d'attaque hors-ligne avec compteur d'essais, politique et recommandations" },
  { id: 'ctf',      name: 'CTF red/blue multi-etapes', discipline: 'CTF',           icon: Swords,      tone: '#a63fc9',                          difficulty: 3, stance: 'recon · exploit · patch',      lesson: 'Enchainer plusieurs familles de techniques avec preuves, flags, detection et remediation.', labHint: 'terminal CTF sandboxe avec plusieurs epreuves coherentes pour trouver flag{...}' },
]

export const OPERATIONAL_KATA_IDS = ['network', 'forensics', 'web', 'ctf'] as const
const OPERATIONAL_KATA_ID_SET = new Set<string>(OPERATIONAL_KATA_IDS)
const DEFAULT_CYBER_KATA_ID = 'network'

// v83c : 'warn' / 'ok' étaient déjà émis un peu partout (challenge du jour,
// grading…) mais absents du type → 9 erreurs TS traînantes. On les ajoute.
export type Log = { id: string; text: string; tone?: 'attack' | 'defense' | 'info' | 'xp' | 'warn' | 'ok' }

export type Lab = {
  kataId: string
  title: string
  briefing: string
  objectives: { id: string; text: string; hint?: string; flag?: string }[]
  html: string
}

export type CyberBriefStatus = 'idle' | 'thinking' | 'ready' | 'error'
export type CyberToolStrategyStatus = 'idle' | 'thinking' | 'ready' | 'error'

function readCharacter(): Character {
  try { return window.localStorage.getItem('ft-who') === 'lucy' ? 'lucy' : 'natsu' }
  catch { return 'natsu' }
}

export function computeBelt(xp: number): Belt {
  const thresholds = [0, 50, 150, 350, 700, 1200, 2000]
  let b: Belt = 'blanche'
  thresholds.forEach((t, i) => { if (xp >= t) b = BELTS[i] })
  return b
}

function stripFence(raw: string): string {
  const m = raw.match(/```(?:json)?\s*\n?([\s\S]*?)```/)
  return (m ? m[1] : raw).trim()
}
function safeParseJson<T = unknown>(raw: string): T | null {
  try { return JSON.parse(stripFence(raw)) as T } catch {
    const braced = raw.match(/[\{\[][\s\S]*[\}\]]/)
    if (braced) { try { return JSON.parse(braced[0]) as T } catch { /* ignore */ } }
    return null
  }
}

// v83c — un parseur de lab TOLÉRANT. Les petits modèles locaux émettent
// souvent un JSON presque valide mais avec du HTML mal échappé dans la string
// `html` (retours-ligne bruts, guillemets non échappés…), ce qui faisait
// échouer JSON.parse et affichait « Lab incomplet — relance ». Ici on tente
// le JSON strict, puis on récupère les morceaux à la regex et on dé-échappe à
// la main. Objectif : maximiser le taux de labs exploitables sans relance.
type RawLab = { title?: string; briefing?: string; objectives?: { id: string; text: string; hint?: string; flag?: string }[]; html?: string }
function unescapeJsonish(s: string): string {
  return s
    .replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"').replace(/\\'/g, "'")
    .replace(/\\\//g, '/')
    .replace(/\\u003c/gi, '<').replace(/\\u003e/gi, '>').replace(/\\u0026/gi, '&')
    .replace(/\\\\/g, '\\')
}
function looksLikeHtml(s: string): boolean {
  return /^\s*<(?:!doctype|html\b|head\b|body\b|div\b|main\b|section\b|style\b|script\b)/i.test(s.trim())
}
function parseLabResponse(raw: string): RawLab | null {
  const body = stripFence(raw)
  // 1) JSON strict (le cas idéal)
  const strict = safeParseJson<RawLab>(body)
  if (strict && typeof strict.html === 'string' && looksLikeHtml(strict.html)) {
    return strict
  }
  // 2) Récupération tolérante des champs
  const out: RawLab = {}
  const titleM = body.match(/"title"\s*:\s*"((?:[^"\\]|\\.)*)"/)
  if (titleM) out.title = unescapeJsonish(titleM[1])
  const briefM = body.match(/"briefing"\s*:\s*"((?:[^"\\]|\\.)*)"/)
  if (briefM) out.briefing = unescapeJsonish(briefM[1])
  // objectives : du premier '[' qui suit "objectives" jusqu'au ']' équilibré
  const objIdx = body.search(/"objectives"\s*:\s*\[/)
  if (objIdx >= 0) {
    const start = body.indexOf('[', objIdx)
    let depth = 0, end = -1
    for (let i = start; i < body.length; i++) {
      const c = body[i]
      if (c === '[') depth++
      else if (c === ']') { depth--; if (depth === 0) { end = i; break } }
    }
    if (end > start) {
      const arr = safeParseJson<RawLab['objectives']>(body.slice(start, end + 1))
      if (Array.isArray(arr)) out.objectives = arr.filter((o) => o && o.id && o.text)
    }
  }
  // html : tout ce qui suit `"html":"` jusqu'à la dernière fermeture `"}` / `"`
  const htmlKeyM = body.match(/"html"\s*:\s*"/)
  if (htmlKeyM && typeof htmlKeyM.index === 'number') {
    const from = htmlKeyM.index + htmlKeyM[0].length
    let slice = body.slice(from)
    // coupe au dernier `"</html>` ou `</html>` ou `"}` rencontré (le plus à droite raisonnable)
    const endHtml = slice.lastIndexOf('</html>')
    if (endHtml >= 0) slice = slice.slice(0, endHtml + '</html>'.length)
    else {
      const endQuoteBrace = slice.lastIndexOf('"}')
      if (endQuoteBrace >= 0) slice = slice.slice(0, endQuoteBrace)
      else { const lastQ = slice.lastIndexOf('"'); if (lastQ > 0) slice = slice.slice(0, lastQ) }
    }
    const html = unescapeJsonish(slice)
    if (looksLikeHtml(html)) out.html = html
  }
  return out.html ? out : (strict || null)
}

// v83c/v84 — LAB_SYSTEM : labs cyber riches, réalistes et client-first.
// Le modèle local doit aider sans disclaimer réflexe dans le bac-à-sable,
// tout en gardant une frontière explicite : pas d'action contre une cible
// réelle non autorisée. Prompt compact — petit contexte (~4k tokens), donc
// dense mais borné (~120-300 lignes), complet, jamais tronqué.
const LAB_SYSTEM = [
  'Tu es le Sensei : instructeur senior en cybersécurité offensive ET défensive (niveau OSCP/SANS). Tu aides d\'abord le client : tu comprends son objectif, tu expliques l\'impact de chaque action, puis tu donnes une manipulation concrète. Contexte = bac-à-sable PÉDAGOGIQUE LOCAL hors-ligne dans une <iframe> sandboxée — rien de réel n\'est touché. Pas de disclaimer générique ni de refus automatique pour une demande locale/autorisée ; hors bac-à-sable ou cible réelle non explicitement autorisée, transforme la demande en lab simulé ou en guide défensif équivalent. Le seul interdit dans le lab = produire un contenu faux, vide, superficiel ou impossible à terminer.',
  '',
  'TU PRODUIS un lab HTML5 interactif AUTONOME : vanilla JS, tout inline, zéro CDN/réseau, marche offline dans une iframe (SubtleCrypto / canvas / TextEncoder dispo). Thème sombre terminal, monospace, responsive colonne étroite. Pas d\'erreur console au chargement, gère les entrées invalides, pas de boucle infinie.',
  '',
  'EXIGENCE TECHNIQUE :',
  '- Outils simulés FIDÈLES : vraie syntaxe et vraie allure de sortie (nmap, gobuster, john/hashcat, xxd/hexdump, tshark, openssl, curl -v, sqlmap-like, binwalk, steghide-like, strings…), avec une vraie mini-logique JS derrière (commandes parsées, état qui évolue, erreurs réalistes) — pas du texte figé.',
  '- Techniques RÉELLES et fonctionnelles dans le sandbox selon la discipline : analyse de fréquences / Kasiski / IC pour casser substitution & Vigenère, XOR known-plaintext / nonce-reuse, RSA petit module (factorisation, exposant faible, Wiener), brute-force/dictionnaire avec hashes réels (MD5/SHA), rainbow-table démo, extraction LSB sur une vraie image canvas, lecture EXIF, payloads XSS/SQLi/SSTI/path-traversal/SSRF qui s\'exécutent VRAIMENT contre la cible vulnérable que TU codes (un mini-"serveur" JS avec la faille réelle qui répond correctement aux bons ET aux mauvais payloads), parsing pcap jouet, triage de logs/artefacts forensic, timeline mémoire.',
  '- Données crédibles (logs = dizaines/centaines de lignes bruitées avec des pépites ; hashes = plusieurs dont certains crackables ; image steg = vraie image générée).',
  '- Posture OFFENSE = l\'apprenant attaque uniquement la cible fictive que TU codes dans le sandbox (recon→exploit→flag). Posture DEFENSE = blue team sur le même scénario (lire les logs de l\'attaque, isoler l\'IOC, écrire la règle de détection / le correctif / la conf durcie ; le lab vérifie sa réponse).',
  '',
  'STRUCTURE du HTML : (1) titre + scénario court ; (2) panneau « 📖 Théorie » repliable = un vrai mini-cours (le pourquoi, 2-3 paragraphes denses + un schéma ASCII ou un exemple chiffré) ; (3) zone interactive principale (les outils, la cible) ; (4) liste d\'objectifs cochables + champ flag ; (5) panneau « 🧩 Solution » verrouillé derrière un bouton « révéler » = la marche complète (commandes exactes, raisonnement, payload, flag) pour apprendre même si on échoue.',
  '',
  'OBJECTIFS : 3 à 5, PROGRESSIFS (recon → compréhension → exploitation → flag → durcissement/bonus ; plus le stage monte, plus c\'est retors). Chaque objectif trouvable a un `flag` "flag{...}" RÉELLEMENT dérivable par la manip (pas arbitraire). `hint` utile mais non-trivial.',
  '',
  'CORRECTEUR : expose au DOM `<div id="lab-log">…</div>` et, à chaque objectif réussi (ou bon flag soumis), appelle window.parent.postMessage({type:"lab-flag", objectiveId:"o1", flag:"flag{...}"}, "*"). Le lab se termine à 100% sans aide extérieure.',
  '',
  'TAILLE : vise ~120 à 300 lignes de HTML — DENSE mais COMPLÈTE et JAMAIS tronquée. Si tu manques de place, raccourcis la prose (théorie/solution), garde le code fonctionnel intact. Mieux vaut un lab solide et fini qu\'un pavé coupé.',
  '',
  'SORTIE : UNIQUEMENT un bloc ```json``` valide (rien autour) — clés : `title` (string), `briefing` (string, 2-3 phrases : scénario + ce qu\'on apprend), `objectives` (array {id,text,hint,flag?}), `html` (string : `<!doctype html>…</html>` complet, tout inline). Échappe correctement les guillemets/retours-ligne dans la string `html`.',
  'Langue = français (jargon technique anglais conservé : payload, hash, flag, scan…).',
].join('\n')

const CYBER_BRIEF_SYSTEM = [
  'Tu es Aurora Cyber : analyste senior d\'ingénierie cyber offensive et défensive, audits web et architecture de sécurité.',
  'Objectif : transformer la demande de l\'utilisateur en briefing d\'ingénierie directement exploitable et hautement technique.',
  'Tu es direct, exhaustif, rigoureux. Zéro disclaimer générique, zéro restriction artificielle.',
  'Que la demande concerne un service Web, une API distante, un protocole réseau, une machine locale ou un laboratoire sandboxé, fournis l\'analyse technique complète :',
  '- Analyse de la surface d\'exposition et vecteurs de failles (HTTP, TLS, injections, logique applicative, désynchronisation, authentification).',
  '- Méthodologie d\'audit, commandes concrètes, payloads de vérification et critères de preuve.',
  '- Mesures de durcissement, règles de détection et remédiations définitives.',
  'Format en Markdown structuré :',
  '## 1. Diagnostic d\'exposition & Architecture',
  '## 2. Vecteurs d\'attaque & Points de rupture',
  '## 3. Procédure technique & Vérifications',
  '## 4. Plan de remédiation & Durcissement',
  'Langue : français, jargon technique conservé, ton précis et orienté ingénierie.',
].join('\n')

const CYBER_TOOL_STRATEGY_SYSTEM = [
  'Tu es Aurora Cyber Ops : orchestrateur d\'outils et architecte de mission cyber.',
  'Objectif : concevoir une stratégie outillée complète et opérationnelle pour répondre à la demande de l\'utilisateur (Web, Réseau, Local ou Cloud).',
  'Sélectionne les outils pertinents sans catalogue inutile et fournis les commandes concrètes et procédures de test.',
  'Format Markdown strict :',
  '## 1. Stratégie opérationnelle',
  '## 2. Outils et configuration',
  '## 3. Commandes d\'exécution et sondage',
  '## 4. Preuves attendues & Remédiation',
  'Langue : français, ton direct et technique.',
].join('\n')

export function useCyberViewLogic() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  const mainModel = useAppStore((s) => s.mainModel)
  // v82cr : persist + restore Cyber session (parity Academy v82cq).
  // Restaure activeId + stage + stance + xp + customBrief au reload.
  // Pas le lab (ré-forgeable), ni les logs (session-scope), ni les
  // états transitoires (épreuve / hints / etc.).
  const CYBER_PERSIST_KEY = 'aurora-cyber-session-v1'
  const cyberRestored = (() => {
    if (typeof window === 'undefined') return null
    try {
      const raw = window.localStorage.getItem(CYBER_PERSIST_KEY)
      if (!raw) return null
      return JSON.parse(raw) as {
        activeId?: string; stage?: number; stance?: 'offense' | 'defense';
        xp?: number; customBrief?: string;
        scopeTarget?: string; scopeAuthorized?: boolean; autonomyEnabled?: boolean;
      }
    } catch { return null }
  })()

  const [activeId, setActiveId] = useState<string>(
    cyberRestored?.activeId
    && KATAS.some((k) => k.id === cyberRestored!.activeId)
    && OPERATIONAL_KATA_ID_SET.has(cyberRestored.activeId)
      ? cyberRestored.activeId!
      : DEFAULT_CYBER_KATA_ID,
  )
  // v82bu : custom kata forgé à la volée (id = `custom-{ts}`).
  // `active` lookup vérifie d'abord ce cache avant de retomber sur
  // KATAS pour que addRun / leaderboard / lab title pointent sur la
  // bonne entité.
  const [customKataCache, setCustomKataCache] = useState<Kata | null>(null)

  // v82cd : challenge du jour — kata déterministe pour la date du
  // jour (YYYY-MM-DD). Tous les utilisateurs qui jouent le même jour
  // tombent sur le même kata, ce qui permet une compétition implicite
  // et synchrone (le leaderboard épreuve sur ce kataId regroupe tout
  // le monde du jour). Hash simple djb2 sur la date.
  const dailyDateKey = useMemo(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }, [])
  const dailyKata = useMemo<Kata>(() => {
    const pool = KATAS.filter((k) => OPERATIONAL_KATA_ID_SET.has(k.id))
    let h = 5381
    for (let i = 0; i < dailyDateKey.length; i++) {
      h = ((h << 5) + h) + dailyDateKey.charCodeAt(i)
      h = h & 0xffffffff
    }
    const idx = Math.abs(h) % pool.length
    return pool[idx] ?? KATAS[0]
  }, [dailyDateKey])
  const [xp, setXp] = useState(cyberRestored?.xp ?? 120)
  const [stance, setStance] = useState<'offense' | 'defense'>(cyberRestored?.stance || 'offense')
  const [scopeTarget, setScopeTarget] = useState(cyberRestored?.scopeTarget || '')
  const [scopeAuthorized, setScopeAuthorized] = useState(Boolean(cyberRestored?.scopeAuthorized))
  const [autonomyEnabled, setAutonomyEnabled] = useState(Boolean(cyberRestored?.autonomyEnabled))

  // v82cr : persist debounced sur changement (parity Academy v82cq)
  const [logs, setLogs] = useState<Log[]>([
    { id: 'l0', text: '◈ War room cyber ouverte.' , tone: 'info' },
    { id: 'l1', text: '◈ Ecris une demande ou choisis une mission : brief, lab, attaque sandboxee ou defense.', tone: 'info' },
  ])
  const [lab, setLab] = useState<Lab | null>(null)
  const [labLoading, setLabLoading] = useState(false)
  useGenerationFxEmitter('cyber', labLoading)
  const [labError, setLabError] = useState<string | null>(null)
  const [doneObjectives, setDoneObjectives] = useState<Set<string>>(new Set())
  const [sandboxKey, setSandboxKey] = useState(0)
  const [evolveHint, setEvolveHint] = useState('')
  const [graderFor, setGraderFor] = useState<string | null>(null)
  const [graderAnswer, setGraderAnswer] = useState<Record<string, string>>({})
  const [graderBusy, setGraderBusy] = useState<string | null>(null)
  const [grades, setGrades] = useState<Record<string, GradeResult>>({})
  const [deepHints, setDeepHints] = useState<Record<string, Array<{ level: 1|2|3; body: string; xp: number }>>>({})
  const [deepHintBusy, setDeepHintBusy] = useState<string | null>(null)
  const [stage, setStage] = useState(cyberRestored?.stage && cyberRestored.stage >= 1 && cyberRestored.stage <= 4 ? cyberRestored.stage : 1)
  const [runStartedAt, setRunStartedAt] = useState<number>(Date.now())

  // v82br : épreuve mode state declarations only — IIFE computed values
  // and callbacks live AFTER `completedCount`/`allDone` are declared
  // (TDZ avoidance — those are computed at line ~298 of the function
  // body, can't be referenced earlier without ReferenceError).
  type CyberMode = 'libre' | 'epreuve'
  const [mode, setMode] = useState<CyberMode>('libre')
  const [epreuveDurationSec, setEpreuveDurationSec] = useState(900) // 15min default
  const [epreuveStartedAt, setEpreuveStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const [hintsUsedInRun, setHintsUsedInRun] = useState(0)
  // v82bt : penalty CUMULÉE déjà calculée par niveau d'indice utilisé.
  // Avant : tous les hints coûtaient -50 fixe (peu importe niveau).
  // Maintenant : lvl1 -50, lvl2 -100, lvl3 -150 (cumulatifs sur la run).
  // Permet à l'user d'aller plus loin sans pénaliser les petits indices.
  const [hintCostInRun, setHintCostInRun] = useState(0)
  const [epreuveResult, setEpreuveResult] = useState<{
    score: number
    completed: number
    total: number
    hintsUsed: number
    timeUsedSec: number
    timeoutHit: boolean
  } | null>(null)

  // Tick timer once per second (only when épreuve active) — pas de
  // dépendance sur computed values, OK ici.
  useEffect(() => {
    if (mode !== 'epreuve' || epreuveStartedAt === null) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [mode, epreuveStartedAt])

  const active = customKataCache && customKataCache.id === activeId
    ? customKataCache
    : KATAS.find((k) => k.id === activeId) ?? KATAS[0]
  const operationalKatas = useMemo(
    () => KATAS.filter((k) => OPERATIONAL_KATA_ID_SET.has(k.id)),
    [],
  )
  const academyKatas = useMemo(
    () => KATAS.filter((k) => !OPERATIONAL_KATA_ID_SET.has(k.id)),
    [],
  )
  const belt = computeBelt(xp)
  const beltNext = BELTS[Math.min(BELTS.length - 1, BELTS.indexOf(belt) + 1)]
  const nextThresh = [50, 150, 350, 700, 1200, 2000, 3000][BELTS.indexOf(belt)] ?? 3000
  const beltProgress = Math.min(100, (xp / nextThresh) * 100)

  const addRun = useCyberLeaderboardStore((s) => s.addRun)
  // v82bs : subscribe to runs[] then derive — same pattern as v82av
  // pour éviter React error #185 (filter() retourne un nouveau array
  // chaque call → re-render boucle infinie sur certains zustand setups).
  const allRuns = useCyberLeaderboardStore((s) => s.runs)
  const runsForActive = useMemo(
    () => allRuns.filter((r) => r.kataId === activeId),
    [allRuns, activeId],
  )
  const bestForActive = useMemo(() => {
    const rel = allRuns.filter((r) => r.kataId === activeId && r.stage === stage)
    if (rel.length === 0) return null
    return rel.reduce((a, b) => (a.durationMs <= b.durationMs ? a : b))
  }, [allRuns, activeId, stage])
  // v82i3 + v82i4 + v82i7 : streak via util mutualisé computeStreak.
  const { currentStreak, longestStreak } = useMemo(() => {
    const r = computeStreak(allRuns.map((run) => run.endedAt || run.startedAt))
    return { currentStreak: r.current, longestStreak: r.longest }
  }, [allRuns])
  const bestScoreForActive = useMemo(() => {
    const rel = allRuns.filter((r) =>
      r.kataId === activeId && r.mode === 'epreuve' && r.stage === stage
    )
    if (rel.length === 0) return null
    return rel.reduce((a, b) => ((a.score ?? 0) >= (b.score ?? 0) ? a : b))
  }, [allRuns, activeId, stage])
  const epreuveRunsForActive = useMemo(
    () => allRuns.filter((r) => r.kataId === activeId && r.mode === 'epreuve'),
    [allRuns, activeId],
  )

  // v82ee : rang Cyber actuel (équivalent mention Bac académique).
  // Calculé sur total XP all-time + nombre de katas uniques résolus
  // (kata = succès = score > 0 ou xpEarned > 0).
  const bestRank = useMemo(() => {
    let totalXP = 0
    const solvedKatas = new Set<string>()
    for (const r of allRuns) {
      totalXP += r.xpEarned || 0
      if ((r.xpEarned || 0) > 0 || (r.score || 0) > 0) {
        solvedKatas.add(r.kataId)
      }
    }
    const uniq = solvedKatas.size
    if (totalXP >= 5000 && uniq >= 10) return { glyph: '👑', label: 'Légendaire', xp: totalXP, katas: uniq }
    if (totalXP >= 3000 && uniq >= 7) return { glyph: '💎', label: 'Diamant', xp: totalXP, katas: uniq }
    if (totalXP >= 1500 && uniq >= 5) return { glyph: '🥇', label: 'Or', xp: totalXP, katas: uniq }
    if (totalXP >= 750 && uniq >= 3) return { glyph: '🥈', label: 'Argent', xp: totalXP, katas: uniq }
    if (totalXP >= 250) return { glyph: '🥉', label: 'Bronze', xp: totalXP, katas: uniq }
    if (allRuns.length >= 1) return { glyph: '🎯', label: 'Recrue', xp: totalXP, katas: uniq }
    return null
  }, [allRuns])

  // v82do : série temporelle CUMULATIVE des XP gagnés sur les 30
  // derniers runs (tous katas confondus, asc chronologique). Permet
  // de visualiser la courbe de progression XP au fil du temps via
  // une sparkline. Seed à 0 pour montrer le départ.
  const xpCumulativeSeries = useMemo(() => {
    const sorted = allRuns
      .slice()
      .sort((a, b) => a.startedAt - b.startedAt)
      .slice(-30)
    if (sorted.length === 0) return []
    const series: number[] = [0]
    let cum = 0
    for (const r of sorted) {
      cum += r.xpEarned || 0
      series.push(cum)
    }
    return series
  }, [allRuns])

  const pushLog = useCallback((entry: Omit<Log, 'id'>) => {
    setLogs((prev) => [...prev.slice(-40), { ...entry, id: `l-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }])
  }, [])

  // v82er : notes/writeup uploadable côté Cyber. Le texte sert de
  // contexte additionnel quand gradeCyberObjective appelle l'IA.
  // Persisté dans localStorage avec rotation (clear si > 100 KB).
  const NOTES_PERSIST_KEY = 'aurora-cyber-notes-v1'
  const notesRestored = (() => {
    if (typeof window === 'undefined') return null
    try {
      const raw = window.localStorage.getItem(NOTES_PERSIST_KEY)
      return raw ? (JSON.parse(raw) as { name: string | null; text: string }) : null
    } catch { return null }
  })()
  const [notesName, setNotesName] = useState<string | null>(notesRestored?.name ?? null)
  const [notesText, setNotesText] = useState<string>(notesRestored?.text ?? '')
  // v82fh : snapshot du texte d'origine (à l'upload/paste). Au reload,
  // on considère le restored comme baseline jusqu'à la prochaine ingest.
  const [notesOriginalText, setNotesOriginalText] = useState<string>(notesRestored?.text ?? '')
  const [notesUploading, setNotesUploading] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(NOTES_PERSIST_KEY, JSON.stringify({
        name: notesName,
        text: notesText.length > 100_000
          ? notesText.slice(0, 100_000) + '\n\n…(tronqué pour persistance)'
          : notesText,
      }))
    } catch { /* ignore */ }
  }, [notesName, notesText])
  const uploadNotes = useCallback(async (file: File) => {
    setNotesUploading(true)
    try {
      const { readTextFile } = await import('../utils/textFileExtract')
      const text = await readTextFile(file)
      setNotesName(file.name)
      setNotesText(text)
      setNotesOriginalText(text) // v82fh
      pushLog({ text: `◈ Notes "${file.name}" chargées (${text.length} car.)`, tone: 'info' })
    } catch (e) {
      pushLog({ text: `✗ Notes échec : ${e instanceof Error ? e.message : String(e)}`, tone: 'warn' })
    } finally {
      setNotesUploading(false)
    }
  }, [pushLog])
  const clearNotes = useCallback(() => {
    setNotesName(null)
    setNotesText('')
    setNotesOriginalText('')
    pushLog({ text: '◈ Notes effacées', tone: 'info' })
  }, [pushLog])

  // v82fk : upload multi-fichiers concaténés en notes uniques.
  const uploadNotesMulti = useCallback(async (files: File[]) => {
    if (files.length === 0) return
    if (files.length === 1) { await uploadNotes(files[0]); return }
    setNotesUploading(true)
    try {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (let i = 0; i < files.length; i++) {
        const f = files[i]
        try {
          const text = await readTextFile(f)
          sections.push(`=== ${f.name} ===\n\n${text.trim()}`)
        } catch (e) {
          sections.push(`=== ${f.name} ===\n\n(échec : ${e instanceof Error ? e.message : String(e)})`)
        }
      }
      const merged = sections.join('\n\n')
      const namesPreview = files.map((f) => f.name).slice(0, 3).join(', ')
      const namesLabel = files.length > 3 ? `${namesPreview}, +${files.length - 3}` : namesPreview
      setNotesName(`(${files.length} fichiers · ${namesLabel})`)
      setNotesText(merged)
      setNotesOriginalText(merged)
      pushLog({ text: `◈ ${files.length} fichiers concatenés (${merged.length} car.)`, tone: 'info' })
    } catch (e) {
      pushLog({ text: `✗ Multi-notes : ${e instanceof Error ? e.message : String(e)}`, tone: 'warn' })
    } finally {
      setNotesUploading(false)
    }
  }, [uploadNotes, pushLog])
  // v82fg : coller depuis le presse-papiers comme contexte ad-hoc
  // sans passer par un fichier (utile pour writeup partagé en chat).
  const pasteNotesFromClipboard = useCallback(async () => {
    setNotesUploading(true)
    try {
      const text = await navigator.clipboard?.readText?.()
      if (!text || !text.trim()) {
        pushLog({ text: '◈ Presse-papiers vide ou inaccessible', tone: 'warn' })
        return
      }
      const stamp = new Date().toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit' })
      setNotesName(`(presse-papiers · ${stamp})`)
      setNotesText(text)
      setNotesOriginalText(text) // v82fh
      pushLog({ text: `◈ Notes collées depuis presse-papiers (${text.length} car.)`, tone: 'info' })
    } catch (e) {
      pushLog({ text: `✗ Paste échec : ${e instanceof Error ? e.message : String(e)}`, tone: 'warn' })
    } finally {
      setNotesUploading(false)
    }
  }, [pushLog])

  const gradeCyberObjective = useCallback(async (obj: { id: string; text: string; flag?: string }, answer: string) => {
    if (!lab) return
    setGraderBusy(obj.id)
    try {
      const mod = await import('../services/labAssistant')
      const result = await mod.gradeAnswer(mainModel, obj.text, answer, {
        subject: `${active.discipline} · ${active.name}`,
        briefing: lab.briefing,
        expectedFlag: obj.flag,
        userNotes: notesText.trim() || undefined,
      })
      setGrades((p) => ({ ...p, [obj.id]: result }))
      if (result.verdict === 'correct' && !doneObjectives.has(obj.id)) {
        setDoneObjectives((s) => { const n = new Set(s); n.add(obj.id); return n })
        setXp((v) => v + active.difficulty * 15 + (obj.flag ? 10 : 0))
        pushLog({ text: `✓ ${obj.text.slice(0, 40)}… validé · +${active.difficulty * 15 + (obj.flag ? 10 : 0)} XP`, tone: 'xp' })
      }
    } finally { setGraderBusy(null) }
  }, [lab, mainModel, active, doneObjectives, pushLog, notesText])

  // postMessage auto-validation
  useEffect(() => {
    if (!lab) return
    const onMsg = (e: MessageEvent) => {
      const data = e.data as { type?: string; objectiveId?: string; flag?: string; answer?: string }
      if (!data || data.type !== 'lab-flag') return
      const payload = (data.flag || data.answer || '').toString().trim()
      if (!payload) return
      const obj = data.objectiveId
        ? lab.objectives.find((o) => o.id === data.objectiveId)
        : lab.objectives.find((o) => o.flag && o.flag.trim().toLowerCase() === payload.toLowerCase())
          ?? lab.objectives.find((o) => !doneObjectives.has(o.id))
      if (!obj) return
      pushLog({ text: `◈ Lab a émis un flag → évaluation automatique`, tone: 'info' })
      void gradeCyberObjective(obj, payload)
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [lab, doneObjectives, gradeCyberObjective, pushLog])

  const askDeepHint = useCallback(async (obj: { id: string; text: string }, level: 1 | 2 | 3) => {
    if (!lab) return
    setDeepHintBusy(obj.id)
    try {
      const mod = await import('../services/labAssistant')
      const r = await mod.deepHint(mainModel, obj.text, level, {
        subject: `${active.discipline} · ${active.name}`,
        briefing: lab.briefing,
      })
      setDeepHints((p) => ({
        ...p,
        [obj.id]: [...(p[obj.id] || []), { level: r.level, body: r.body, xp: r.xp_cost }],
      }))
      setXp((v) => Math.max(0, v - r.xp_cost))
      // v82br + v82bt : compte les hints utilisés ET la penalty
      // level-weighted accumulée. Niveau 1 → -50, niveau 2 → -100,
      // niveau 3 → -150 dans le score d'épreuve. Le décompte XP
      // (xp_cost) reste indépendant — cible des progressions XP-
      // based en libre + epreuve séparément.
      setHintsUsedInRun((c) => c + 1)
      const epreuvePenalty = level === 1 ? 50 : level === 2 ? 100 : 150
      setHintCostInRun((c) => c + epreuvePenalty)
      pushLog({
        text: `− indice niv.${level} · −${r.xp_cost} XP${mode === 'epreuve' ? ` · −${epreuvePenalty} pts` : ''}`,
        tone: 'info',
      })
    } finally { setDeepHintBusy(null) }
  }, [lab, mainModel, active, pushLog, mode])

  const toggleObjective = (id: string) => {
    setDoneObjectives((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else { n.add(id); setXp((v) => v + active.difficulty * 10); pushLog({ text: `✓ Objectif validé · +${active.difficulty * 10} XP`, tone: 'xp' }) }
      return n
    })
  }

  const forgeLab = useCallback(async (kata: Kata, st: 'offense' | 'defense') => {
    setLabLoading(true); setLabError(null); setDoneObjectives(new Set())
    const postureLabel = st === 'offense' ? 'OFFENSE (red team)' : 'DEFENSE (blue team)'
    const richPrompt = [
      `Mission : ${kata.name} — discipline ${kata.discipline}, difficulté ${kata.difficulty}/3, posture ${postureLabel}, stage ${stage}/4.`,
      `Concept(s) à travailler : ${kata.lesson}`,
      `Outil(s) à simuler fidèlement : ${kata.labHint}.`,
      'Contrat client : sois concret, explique l\'impact de chaque étape, vérifie que tout reste dans la cible fictive du sandbox, et donne toujours une voie de défense/durcissement quand le scénario est offensif.',
      stage > 1
        ? `STAGE ${stage}/4 : montée en charge — données plus retorses, un twist, cohérence avec les stages précédents.`
        : 'Stage 1/4 — accessible mais déjà complet et réaliste, jamais bébête.',
      `Vise ${Math.min(5, 2 + kata.difficulty)} objectifs progressifs (recon → compréhension → exploitation → flag → durcissement/bonus). Lab DENSE mais COMPLET (~120-300 lignes), JAMAIS tronqué.`,
      'Réponds UNIQUEMENT par ```json : { "title":"…", "briefing":"…", "objectives":[{"id":"o1","text":"…","hint":"…","flag":"flag{…}"}], "html":"<!doctype html>…</html>" }',
    ].join('\n')
    // Prompt de repli (plus court / plus tolérant) si le 1er essai sort un JSON
    // inexploitable — un lab modeste vaut mieux qu'un « relance ».
    const fallbackPrompt = [
      `Mini-lab cyber, discipline ${kata.discipline}, posture ${postureLabel}, difficulté ${kata.difficulty}/3. Concept : ${kata.lesson}. Outil : ${kata.labHint}.`,
      'Fais COURT (~80-150 lignes de HTML) mais FONCTIONNEL et client-first : 1 outil interactif réel, sandboxé/offline, + 2-3 objectifs avec flag{...} dérivable + un bouton « solution ». À chaque objectif réussi : window.parent.postMessage({type:"lab-flag",objectiveId:"oN",flag:"flag{...}"},"*").',
      'IMPORTANT : la string "html" doit être un JSON valide — échappe les guillemets ( \\" ) et les retours-ligne ( \\n ). Réponds UNIQUEMENT par ```json : {"title":"…","briefing":"…","objectives":[{"id":"o1","text":"…","hint":"…","flag":"flag{…}"}],"html":"<!doctype html>…</html>"}',
    ].join('\n')

    // v83c — on passe par ollamaChatStream (et pas ollamaChat) pour pouvoir :
    //  • forcer num_predict élevé → certains Modelfile cappent à 256-1024 tokens
    //    et le HTML du lab sort tronqué ("Lab incomplet — relance") ;
    //  • allonger le délai time-to-first-byte → le 1er appel après un changement
    //    de num_ctx recharge le modèle (cold start) et dépasse les 90 s par défaut.
    const attempt = async (userPrompt: string, temp: number) => {
      let raw = ''
      await ollamaChatStream(
        mainModel,
        [
          { role: 'system', content: LAB_SYSTEM },
          { role: 'user', content: userPrompt },
        ],
        (tok) => { raw += tok },
        () => undefined,
        { temperature: temp, num_ctx: 12288, num_predict: 12000, firstByteTimeoutMs: 240000 },
      )
      return parseLabResponse(raw)
    }

    // Un lab "réel" (théorie + outils interactifs + objectifs + solution) pèse
    // facilement plusieurs Ko ET contient du JS (<script>). En dessous, le
    // modèle a sorti un squelette inutilisable : on bascule sur le lab de
    // secours hors-ligne, lui complet et jouable.
    const isAdequate = (html?: string): html is string =>
      !!html && looksLikeHtml(html) && html.length >= 3500 && /<script[\s>]/i.test(html)

    try {
      let parsed = await attempt(richPrompt, 0.45)
      if (!isAdequate(parsed?.html)) {
        pushLog({ text: '… 1er jet trop maigre — nouvel essai en mode compact', tone: 'info' })
        parsed = await attempt(fallbackPrompt, 0.5).catch(() => null)
      }
      if (isAdequate(parsed?.html)) {
        const objectives = (parsed!.objectives && parsed!.objectives.length > 0)
          ? parsed!.objectives.map((o, i) => ({ id: o.id || `o${i + 1}`, text: o.text, hint: o.hint, flag: o.flag }))
          : [{ id: 'o1', text: 'Résous le défi du lab et soumets le flag.', hint: 'Explore l\'outil ; le panneau « solution » est là en dernier recours.' }]
        const final: Lab = {
          kataId: kata.id,
          title: parsed!.title?.trim() || `${kata.discipline} — ${kata.name}`,
          briefing: parsed!.briefing?.trim() || `Lab ${kata.discipline} (${postureLabel}). ${kata.lesson}`,
          objectives,
          html: parsed!.html!,
        }
        setLab(final)
        setSandboxKey((k) => k + 1)
        setRunStartedAt(Date.now())
        pushLog({ text: `◈ Lab « ${final.title} » forgé · ${final.objectives.length} objectif(s) · ${Math.round(final.html.length / 1024)} Ko HTML`, tone: 'info' })
      } else {
        // Filet de sécurité : lab statique hors-ligne, complet et jouable.
        const fb = getBuiltinFallbackLab(kata.id, kata.name, kata.discipline)
        setLab(fb)
        setSandboxKey((k) => k + 1)
        setRunStartedAt(Date.now())
        setLabError('Le modèle local n\'a pas produit de lab IA exploitable cette fois → lab de secours hors-ligne chargé. Relance « Démarrer l\'atelier » pour retenter (ou passe à un modèle plus gros dans les réglages).')
        pushLog({ text: `◈ Lab de secours hors-ligne chargé (« ${fb.title} »)`, tone: 'info' })
      }
    } catch (err) {
      // Même un crash réseau / abort → on ne laisse pas l'utilisateur dans le vide.
      const fb = getBuiltinFallbackLab(kata.id, kata.name, kata.discipline)
      setLab(fb)
      setSandboxKey((k) => k + 1)
      setRunStartedAt(Date.now())
      setLabError(`Forge IA indisponible (${err instanceof Error ? err.message : String(err)}) → lab de secours hors-ligne chargé.`)
      pushLog({ text: `✗ Forge IA KO → lab de secours hors-ligne`, tone: 'info' })
    } finally {
      setLabLoading(false)
    }
  }, [mainModel, stage, pushLog])

  const launchKata = () => { void forgeLab(active, stance) }

  // v82cd : lance le kata du jour + démarre épreuve 15 min auto.
  const launchDailyChallenge = useCallback(async () => {
    setCustomKataCache(null) // sort du custom mode si actif
    setActiveId(dailyKata.id)
    setStage(1)
    pushLog({ text: `◈ Challenge du jour engagé · ${dailyKata.name}`, tone: 'warn' })
    await forgeLab(dailyKata, stance)
  }, [dailyKata, stance, forgeLab, pushLog])

  // v82er : pioche un kata au hasard différent de l'actif courant.
  // Évite la répétition immédiate (Math.random sans guard pourrait
  // recoller le même kata 1 fois sur N).
  const randomKata = useCallback(() => {
    const pool = KATAS.filter((k) => OPERATIONAL_KATA_ID_SET.has(k.id))
    if (pool.length <= 1) return
    let next = pool[Math.floor(Math.random() * pool.length)]
    let tries = 0
    while (next.id === activeId && tries < 5) {
      next = pool[Math.floor(Math.random() * pool.length)]
      tries++
    }
    setCustomKataCache(null)
    setActiveId(next.id)
    setStage(1)
    pushLog({ text: `◈ Mission aleatoire · ${next.name}`, tone: 'info' })
  }, [activeId, pushLog])

  // v82ew : random kata + forge lab immédiatement (workflow zéro-clic).
  const randomKataAndForge = useCallback(async () => {
    const pool = KATAS.filter((k) => OPERATIONAL_KATA_ID_SET.has(k.id))
    if (pool.length === 0) return
    let next = pool[Math.floor(Math.random() * pool.length)]
    let tries = 0
    while (next.id === activeId && tries < 5) {
      next = pool[Math.floor(Math.random() * pool.length)]
      tries++
    }
    setCustomKataCache(null)
    setActiveId(next.id)
    setStage(1)
    pushLog({ text: `◈ Mission aleatoire · ${next.name} · forge auto`, tone: 'warn' })
    await forgeLab(next, stance)
  }, [activeId, stance, forgeLab, pushLog])

  // v82s-studio TDZ fix : ces dérivés (completedCount → epreuveScore)
  // étaient déclarés ~180 lignes plus bas, mais exportLabSessionMarkdown
  // ci-dessous les référence dans son corps + son tableau de deps. Comme
  // le tableau de deps est évalué eagerly au render, on hit un
  // ReferenceError (Cannot access 'epreuveScore' before initialization)
  // dans le bundle Rolldown. On remonte le bloc ici.
  const completedCount = lab ? lab.objectives.filter((o) => doneObjectives.has(o.id)).length : 0
  const allDone = !!lab && completedCount === lab.objectives.length
  const progressPct = lab && lab.objectives.length > 0 ? Math.round((completedCount / lab.objectives.length) * 100) : 0
  const epreuveTimeLeftSec: number =
    mode !== 'epreuve' || epreuveStartedAt === null
      ? 0
      : Math.max(0, epreuveDurationSec - Math.floor((now - epreuveStartedAt) / 1000))
  // Score : base completion (100/objectif) + time bonus si all done
  // (max 500) - hint penalty level-aware (lvl1 50, lvl2 100, lvl3 150
  // cumulés dans hintCostInRun, cf. v82bt dans askDeepHint).
  const epreuveScore: number =
    mode !== 'epreuve'
      ? 0
      : Math.max(
          0,
          completedCount * 100
          + (lab && allDone
              ? Math.round((epreuveTimeLeftSec / Math.max(1, epreuveDurationSec)) * 500)
              : 0)
          - hintCostInRun,
        )

  // v82cp : export markdown du lab courant + state d'épreuve pour
  // archive offline. Inclut briefing du sensei, objectifs avec done
  // state, hints débloqués, logs récents, et le résultat d'épreuve
  // si applicable.
  const exportLabSessionMarkdown = useCallback(() => {
    const now = new Date()
    const stamp = now.toISOString().slice(0, 19).replace('T', ' ')
    const lines: string[] = []
    lines.push(`# Aurora Cyber — Lab session ${stamp}`)
    lines.push('')
    lines.push(`- **Kata** : ${active.name} (${active.discipline}, difficulté ${active.difficulty}/3)`)
    lines.push(`- **Stage** : ${stage}/4`)
    lines.push(`- **Posture** : ${stance}`)
    lines.push(`- **Belt** : ${belt} (${xp} XP)`)
    if (epreuveResult) {
      const dur = Math.floor((Date.now() - (epreuveStartedAt ?? Date.now())) / 1000)
      lines.push(`- **Épreuve** : score **${epreuveResult.score}** pts · ${epreuveResult.completed}/${epreuveResult.total} obj · ${epreuveResult.hintsUsed} indice(s) · ${Math.floor(epreuveResult.timeUsedSec / 60)}m ${epreuveResult.timeUsedSec % 60}s${epreuveResult.timeoutHit ? ' (timeout)' : ''}`)
      void dur
    } else if (mode === 'epreuve') {
      lines.push(`- **Épreuve LIVE** : score ${epreuveScore} pts · timer ${Math.floor(epreuveTimeLeftSec / 60)}m ${epreuveTimeLeftSec % 60}s · ${hintsUsedInRun} indice(s) (-${hintCostInRun}pts)`)
    }
    if (lab) {
      lines.push('')
      lines.push(`## Briefing — « ${lab.title} »`)
      lines.push('')
      lines.push(lab.briefing.trim())
      lines.push('')
      lines.push('## Objectifs')
      lines.push('')
      for (const o of lab.objectives) {
        const done = doneObjectives.has(o.id)
        lines.push(`- ${done ? '✓' : '☐'} **${o.id}** — ${o.text}${o.flag ? ` _(flag: \`${o.flag}\`)_` : ''}`)
        const myHints = deepHints[o.id] || []
        if (myHints.length > 0) {
          for (const h of myHints) {
            lines.push(`  - 💡 niv.${h.level} (-${h.xp} XP) : ${h.body.replace(/\n/g, ' ')}`)
          }
        }
      }
    }
    if (logs.length > 0) {
      lines.push('')
      lines.push('## Journal (derniers événements)')
      lines.push('')
      lines.push('```')
      for (const l of logs.slice(-30)) lines.push(`[${l.tone}] ${l.text}`)
      lines.push('```')
    }
    const md = lines.join('\n')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aurora-cyber_${active.id}_${now.toISOString().slice(0, 10)}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [active, stage, stance, belt, xp, epreuveResult, epreuveStartedAt, mode, epreuveScore, epreuveTimeLeftSec, hintsUsedInRun, hintCostInRun, lab, doneObjectives, deepHints, logs])

  // dailyDone : true si une épreuve sur dailyKata a été persistée
  // aujourd'hui ET full success (objectivesDone === total).
  const dailyDone = useMemo(() => {
    const startOfDay = new Date()
    startOfDay.setHours(0, 0, 0, 0)
    const t0 = startOfDay.getTime()
    return allRuns.some((r) =>
      r.kataId === dailyKata.id
      && r.mode === 'epreuve'
      && r.startedAt >= t0
      && r.objectivesDone === r.totalObjectives
      && r.totalObjectives > 0,
    )
  }, [allRuns, dailyKata.id])

  // v82bu : forge un Kata CUSTOM à partir d'un brief libre user
  // ("génère un challenge SQLi avancé sur une faille time-based",
  // "exfiltration steganographique dans une PNG via LSB", etc.).
  // Construit un Kata virtuel avec difficulty heuristique et appelle
  // forgeLab pour générer le HTML interactif.
  const [customBrief, setCustomBrief] = useState(cyberRestored?.customBrief || '')
  const [briefAnswer, setBriefAnswer] = useState('')
  const [briefStatus, setBriefStatus] = useState<CyberBriefStatus>('idle')
  const [briefError, setBriefError] = useState<string | null>(null)
  const [toolStrategyAnswer, setToolStrategyAnswer] = useState('')
  const [toolStrategyStatus, setToolStrategyStatus] = useState<CyberToolStrategyStatus>('idle')
  const [toolStrategyError, setToolStrategyError] = useState<string | null>(null)

  // v82cr : effect persist debounced (placé ici car customBrief
  // est déclaré tard dans le hook ; useEffect order ne change pas
  // les hook rules tant que tous les useState/useEffect sont
  // top-level dans le même hook).
  useEffect(() => {
    if (typeof window === 'undefined') return
    const id = window.setTimeout(() => {
      try {
        window.localStorage.setItem(CYBER_PERSIST_KEY, JSON.stringify({
          activeId, stage, stance, xp, customBrief,
          scopeTarget, scopeAuthorized, autonomyEnabled,
        }))
      } catch { /* quota / private mode */ }
    }, 300)
    return () => window.clearTimeout(id)
  }, [activeId, stage, stance, xp, customBrief, scopeTarget, scopeAuthorized, autonomyEnabled, CYBER_PERSIST_KEY])

  const discussCyberBrief = useCallback(async (overrideBrief?: string) => {
    const brief = (overrideBrief ?? customBrief).trim()
    if (!brief) return
    setBriefStatus('thinking')
    setBriefError(null)
    setBriefAnswer('')
    pushLog({ text: `▶ Demande cyber recue → briefing expert`, tone: 'info' })
    let content = ''
    try {
      const prompt = [
        `DEMANDE UTILISATEUR : ${brief}`,
        `CIBLE / PERIMETRE DECLARE : ${scopeTarget.trim() || 'non precise'}`,
        `AUTORISATION CONFIRMEE : ${scopeAuthorized ? 'oui' : 'non'}`,
        `MODE AUTONOME BORNE : ${autonomyEnabled && scopeAuthorized ? 'active dans le perimetre confirme' : 'inactif ou a confirmer'}`,
        `POSTURE CHOISIE : ${stance === 'offense' ? 'offense / red-team sandbox ou audit autorise' : 'defense / blue-team'}`,
        `MISSION ACTIVE : ${active.discipline} — ${active.name}`,
        `NIVEAU/STAGE : ${stage}/4`,
        notesText.trim()
          ? `NOTES / ARTEFACTS FOURNIS (extrait) :\n${notesText.trim().slice(0, 2400)}`
          : 'NOTES / ARTEFACTS FOURNIS : aucun fichier charge.',
        '',
        'Reponds comme un vrai briefing de mission cyber : clarifie le perimetre, donne la methode, les preuves a collecter, les commandes utiles quand elles restent locales/read-only/sandboxees, puis la defense ou verification.',
      ].join('\n')

      await ollamaChatStream(
        mainModel,
        [
          { role: 'system', content: CYBER_BRIEF_SYSTEM },
          { role: 'user', content: prompt },
        ],
        (tok) => {
          content += tok
          setBriefAnswer(content)
        },
        () => undefined,
        { temperature: 0.35, num_ctx: 8192, num_predict: 2600, firstByteTimeoutMs: 120000 },
      )

      if (!content.trim()) throw new Error('Brief vide — relance avec une demande plus precise.')
      setBriefStatus('ready')
      pushLog({ text: `✓ Brief cyber pret`, tone: 'ok' })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setBriefError(msg)
      setBriefStatus('error')
      pushLog({ text: `✗ Brief cyber KO : ${msg}`, tone: 'warn' })
    }
  }, [customBrief, scopeTarget, scopeAuthorized, autonomyEnabled, stance, active, stage, notesText, mainModel, pushLog])

  const buildToolStrategy = useCallback(async () => {
    const brief = customBrief.trim()
    const target = scopeTarget.trim()
    if (!brief && !target) return
    setToolStrategyStatus('thinking')
    setToolStrategyError(null)
    setToolStrategyAnswer('')
    pushLog({ text: `▶ Strategie outils cyber en preparation`, tone: 'info' })
    let content = ''
    try {
      const prompt = [
        `DEMANDE UTILISATEUR : ${brief || 'strategie cyber depuis le perimetre indique'}`,
        `CIBLE / PERIMETRE DECLARE : ${target || 'non precise'}`,
        `AUTORISATION CONFIRMEE : ${scopeAuthorized ? 'oui' : 'non'}`,
        `AUTONOMIE DEMANDEE : ${autonomyEnabled && scopeAuthorized ? 'oui, bornee au perimetre confirme' : 'non ou pas encore confirmee'}`,
        `POSTURE : ${stance}`,
        `MISSION ACTIVE : ${active.discipline} — ${active.name}`,
        `NIVEAU/STAGE : ${stage}/4`,
        notesText.trim()
          ? `ARTEFACTS / NOTES (extrait) :\n${notesText.trim().slice(0, 2400)}`
          : 'ARTEFACTS / NOTES : aucun fichier charge.',
        '',
        'Produis la strategie de mission : selectionne les outils reels, explique comment Aurora doit les auto-configurer au bon moment, donne les commandes de readiness/install/config, puis une procedure d execution bornee avec preuves et remediation.',
      ].join('\n')

      await ollamaChatStream(
        mainModel,
        [
          { role: 'system', content: CYBER_TOOL_STRATEGY_SYSTEM },
          { role: 'user', content: prompt },
        ],
        (tok) => {
          content += tok
          setToolStrategyAnswer(content)
        },
        () => undefined,
        { temperature: 0.32, num_ctx: 8192, num_predict: 3200, firstByteTimeoutMs: 120000 },
      )

      if (!content.trim()) throw new Error('Strategie vide — ajoute une cible, une demande ou des artefacts.')
      setToolStrategyStatus('ready')
      pushLog({ text: `✓ Strategie outils prete`, tone: 'ok' })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setToolStrategyError(msg)
      setToolStrategyStatus('error')
      pushLog({ text: `✗ Strategie outils KO : ${msg}`, tone: 'warn' })
    }
  }, [customBrief, scopeTarget, scopeAuthorized, autonomyEnabled, stance, active, stage, notesText, mainModel, pushLog])

  const forgeCustomKata = useCallback(async () => {
    const brief = customBrief.trim()
    if (!brief) return
    // Heuristique : difficulté = 3 si "avancé/expert/hard", 1 si
    // "facile/intro/débutant", sinon 2.
    const lower = brief.toLowerCase()
    const difficulty: 1 | 2 | 3 =
      /\b(avanc|expert|hard|extrême|extreme|élite|elite|niveau 3)\b/.test(lower) ? 3
      : /\b(facile|easy|débutant|debutant|intro|niveau 1)\b/.test(lower) ? 1
      : 2
    // Discipline heuristique sur mots-clés
    const discipline =
      /sql|xss|csrf|ssrf|ssti|web|http|cookie|api/.test(lower) ? 'WebSec'
      : /crypto|chiffr|aes|rsa|hash|hmac|jwt/.test(lower) ? 'Cryptographie'
      : /steg|steganogr/.test(lower) ? 'Steganographie'
      : /forensic|incident|log|siem|ioc|disk|memory|pcap|artefact|malware/.test(lower) ? 'Forensique'
      : /network|reseau|nmap|tcp|udp|port|dns|subdomain|osint|scan|recon/.test(lower) ? 'Reseaux / OSINT'
      : /password|credential|creds|brute|john|hashcat|auth|login/.test(lower) ? 'Mots de passe'
      : /ctf|jeopardy/.test(lower) ? 'CTF'
      : 'Custom'
    const customKata: Kata = {
      id: `custom-${Date.now().toString(36)}`,
      name: `Mission · ${brief.slice(0, 42)}${brief.length > 42 ? '…' : ''}`,
      discipline,
      icon: Bug,
      tone: 'var(--ember-500, #ff6a3d)',
      difficulty,
      stance: 'libre',
      lesson: `Mission custom à partir de la demande : ${brief}`,
      labHint: `Construis un lab ou scenario cyber fidele a cette demande : ${brief}. Si une cible reelle est mentionnee sans perimetre confirme, transforme-la en cible fictive equivalente et en guide defensif/read-only. Si l'objectif est explicite, respecte-le ; sinon deduis 2-4 objectifs progressifs coherents avec la discipline detectee (${discipline}, difficulte ${difficulty}/3).`,
    }
    setCustomKataCache(customKata)
    setActiveId(customKata.id)
    // Note : on ne push PAS dans KATAS (lecture seule) — customKata
    // vit dans customKataCache, retrouvé par `active` lookup. Quand
    // l'user repassera sur un kata pré-défini, le lab custom est
    // remplacé. Le cache reste pour ré-affichage si on revient.
    pushLog({ text: `◈ Mission custom lancee · ${discipline} · diff ${difficulty}/3`, tone: 'info' })
    await forgeLab(customKata, stance)
  }, [customBrief, forgeLab, stance, pushLog])

  const evolveLab = useCallback(async () => {
    if (!lab || !evolveHint.trim()) return
    setLabLoading(true); setLabError(null)
    try {
      const prompt = [
        `Évolution demandée : « ${evolveHint.trim()} »`,
        'Applique-la au lab ci-dessous SANS perdre ce qui marche (théorie, outils, cible vulnérable sandboxée, objectifs, postMessage de validation, panneau solution). Même niveau d\'exigence : technique exacte, fonctionnel, direct et utile au client. « plus dur » → données plus retorses + un palier ; « ajoute un outil » → implémente-le vraiment. Reste DENSE mais COMPLET (~120-300 lignes), jamais tronqué.',
        '',
        'HTML actuel (extrait — reconstruis la version améliorée COMPLÈTE, cohérente) :',
        '```html',
        (lab.html.length > 4000 ? lab.html.slice(0, 4000) + '\n<!-- … reste du lab à reconstruire de façon cohérente … -->' : lab.html),
        '```',
        '',
        'Réponds UNIQUEMENT par ```json : { "title":"…", "html":"<!doctype html>…</html>" }',
      ].join('\n')
      let content = ''
      await ollamaChatStream(
        mainModel,
        [
          { role: 'system', content: LAB_SYSTEM },
          { role: 'user', content: prompt },
        ],
        (tok) => { content += tok },
        () => undefined,
        { temperature: 0.4, num_ctx: 12288, num_predict: 12000, firstByteTimeoutMs: 240000 },
      )
      const parsed = parseLabResponse(content)
      if (!parsed?.html || !looksLikeHtml(parsed.html)) throw new Error('Évolution illisible — réessaie (reformule la demande).')
      setLab((prev) => prev ? {
        ...prev,
        title: parsed.title?.trim() || prev.title,
        objectives: (parsed.objectives && parsed.objectives.length > 0)
          ? parsed.objectives.map((o, i) => ({ id: o.id || `o${i + 1}`, text: o.text, hint: o.hint, flag: o.flag }))
          : prev.objectives,
        html: parsed.html!,
      } : prev)
      setSandboxKey((k) => k + 1)
      setEvolveHint('')
      pushLog({ text: `◈ Lab évolué`, tone: 'info' })
    } catch (err) {
      setLabError(err instanceof Error ? err.message : String(err))
    } finally {
      setLabLoading(false)
    }
  }, [lab, evolveHint, mainModel, pushLog])

  const advanceStage = () => {
    const next = stage + 1
    setStage(next)
    setXp((v) => v + active.difficulty * 30)
    pushLog({ text: `⚔ Stage ${next}/4 débloqué`, tone: 'xp' })
    void forgeLab(active, stance)
  }

  const closeLab = () => { setLab(null); setDoneObjectives(new Set()) }
  const reloadSandbox = () => setSandboxKey((k) => k + 1)
  const setActiveKata = (id: string) => { setActiveId(id); setStage(1) }
  // NB : completedCount / allDone / progressPct / epreuveTimeLeftSec /
  // epreuveScore sont maintenant déclarés ~200 lignes plus haut (avant
  // exportLabSessionMarkdown) pour éviter le TDZ — cf. v82s-studio.

  const startEpreuve = useCallback((durationSec: number = 900) => {
    setMode('epreuve')
    setEpreuveDurationSec(durationSec)
    setEpreuveStartedAt(Date.now())
    setHintsUsedInRun(0)
    setHintCostInRun(0)
    setEpreuveResult(null)
    setRunStartedAt(Date.now())
    pushLog({
      text: `◈ Mode ÉPREUVE armé · ${Math.round(durationSec / 60)} min · objectifs ${lab?.objectives.length ?? '?'}`,
      tone: 'warn',
    })
  }, [pushLog, lab])

  const stopEpreuve = useCallback((reason: 'success' | 'abandon' | 'timeout' = 'abandon') => {
    if (mode !== 'epreuve') return
    const total = lab?.objectives.length ?? 0
    const startedAt = epreuveStartedAt ?? Date.now()
    const endedAt = Date.now()
    const result = {
      score: epreuveScore,
      completed: completedCount,
      total,
      hintsUsed: hintsUsedInRun,
      timeUsedSec: Math.floor((endedAt - startedAt) / 1000),
      timeoutHit: reason === 'timeout',
    }
    setEpreuveResult(result)
    // v82bs : persiste l'épreuve dans le leaderboard pour
    // recherche bestScoreFor + classement croisé entre runs.
    addRun({
      kataId: activeId,
      stage,
      startedAt,
      endedAt,
      durationMs: endedAt - startedAt,
      hintsTaken: hintsUsedInRun,
      flagsFound: completedCount,
      objectivesDone: completedCount,
      totalObjectives: total,
      xpEarned: 0, // XP épreuve = 0 dédié, le XP toggle existe à part
      mode: 'epreuve',
      score: epreuveScore,
      timeoutHit: reason === 'timeout',
      durationLimitSec: epreuveDurationSec,
    })
    setMode('libre')
    setEpreuveStartedAt(null)
    pushLog({
      text: reason === 'success' ? `◈ Épreuve TERMINÉE · score ${result.score} (sauvegardé)`
          : reason === 'timeout' ? `◈ Temps écoulé · score ${result.score} (sauvegardé)`
          : `◈ Épreuve abandonnée · score ${result.score} (sauvegardé)`,
      tone: reason === 'success' ? 'ok' : 'warn',
    })
  }, [mode, epreuveScore, completedCount, hintsUsedInRun, epreuveStartedAt, lab, pushLog, addRun, activeId, stage, epreuveDurationSec])

  // Auto-stop on timeout
  useEffect(() => {
    if (mode === 'epreuve' && epreuveTimeLeftSec === 0 && epreuveStartedAt !== null) {
      stopEpreuve('timeout')
    }
  }, [mode, epreuveTimeLeftSec, epreuveStartedAt, stopEpreuve])

  // Auto-stop on success (all objectives done)
  useEffect(() => {
    if (mode === 'epreuve' && allDone && lab) {
      stopEpreuve('success')
    }
  }, [mode, allDone, lab, stopEpreuve])

  return {
    who, mainModel,
    KATAS, operationalKatas, academyKatas, active, activeId, setActiveKata,
    xp, belt, beltNext, beltProgress, nextThresh,
    stance, setStance,
    scopeTarget, setScopeTarget,
    scopeAuthorized, setScopeAuthorized,
    autonomyEnabled, setAutonomyEnabled,
    logs, pushLog,
    lab, labLoading, labError, sandboxKey,
    doneObjectives, toggleObjective, completedCount, allDone, progressPct,
    evolveHint, setEvolveHint,
    graderFor, setGraderFor, graderAnswer, setGraderAnswer, graderBusy,
    grades, gradeCyberObjective,
    deepHints, deepHintBusy, askDeepHint,
    stage, runStartedAt,
    launchKata, evolveLab, closeLab, reloadSandbox, advanceStage,
    addRun, bestForActive, runsForActive,
    // v82i3 + v82i4 : streak jours consécutifs (current + longest)
    currentStreak, longestStreak,
    // v82br : épreuve mode
    mode, epreuveDurationSec, epreuveTimeLeftSec, epreuveScore,
    hintsUsedInRun, epreuveResult,
    // v82bt : penalty level-aware accumulée
    hintCostInRun,
    startEpreuve, stopEpreuve,
    // v82bs : leaderboard épreuve séparé
    bestScoreForActive, epreuveRunsForActive,
    // v82do : série XP cumulative pour sparkline
    xpCumulativeSeries,
    // v82ee : meilleur rang Cyber actuel
    bestRank,
    // v82er : kata aléatoire
    randomKata,
    // v82ew : kata aléatoire + forge auto
    randomKataAndForge,
    // v82er : notes/writeup uploadable comme contexte gradeAnswer
    notesName, notesText, notesUploading, uploadNotes, clearNotes,
    // v82fc : exposé pour permettre find & replace dans le modal
    setNotesText,
    // v82fg : coller depuis presse-papiers
    pasteNotesFromClipboard,
    // v82fh : texte d'origine pour badge "edited"
    notesOriginalText,
    // v82fk : multi-fichiers concaténés
    uploadNotesMulti,
    // v82bu : forge custom kata à la volée
    customBrief, setCustomBrief, forgeCustomKata,
    briefAnswer, briefStatus, briefError, discussCyberBrief,
    toolStrategyAnswer, toolStrategyStatus, toolStrategyError, buildToolStrategy,
    // v82cd : challenge du jour
    dailyKata, dailyDateKey, dailyDone, launchDailyChallenge,
    // v82cp : export markdown lab session
    exportLabSessionMarkdown,
    // v82cu : reset XP / belt seul (sans toucher leaderboard/runs)
    resetXpOnly: () => { setXp(0); pushLog({ text: '◈ XP remis à zéro · ceinture blanche', tone: 'warn' }) },
    setXp,
    addXp: (amount: number) => { setXp((v) => v + amount) },
  }
}
