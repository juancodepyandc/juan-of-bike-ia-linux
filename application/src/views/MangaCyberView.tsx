import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BookLock, Bug, FileLock2, Fingerprint, Key, Loader2, Network, RefreshCw, ScanEye,
  ShieldCheck, Sparkles, Swords, Target, Wand2, X, Zap,
} from 'lucide-react'
import { ollamaChat } from '../hooks/useTauri'
import { getBuiltinFallbackLab } from '../services/cyber/builtinLabs'
import { useAppStore } from '../stores/appStore'
import { useCyberLeaderboardStore, formatDuration, medalFor } from '../stores/cyberLeaderboardStore'

type Character = 'natsu' | 'lucy'
const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

type Belt = 'blanche' | 'jaune' | 'orange' | 'verte' | 'bleue' | 'marron' | 'noire'
const BELTS: Belt[] = ['blanche', 'jaune', 'orange', 'verte', 'bleue', 'marron', 'noire']

type Kata = {
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

const KATAS: Kata[] = [
  { id: 'crypto',   name: 'Crypto-Kata',    discipline: 'Cryptographie',  icon: Key,         tone: 'var(--color-mod-code)',    difficulty: 2, stance: 'XOR · César · AES', lesson: 'Attaque par fréquence, chiffrement symétrique, IV safe.', labHint: 'console de chiffrement + champ texte clair / chiffré + slider/clé' },
  { id: 'network',  name: 'Shinobi-Shinri', discipline: 'Réseaux',        icon: Network,     tone: 'var(--color-mod-conv)',    difficulty: 2, stance: 'TCP · Nmap · Wireshark', lesson: 'Scans, fingerprinting, enum de services.', labHint: 'nmap simulé avec une cible à scanner, ports ouverts à découvrir' },
  { id: 'forensics',name: 'Kotodama',       discipline: 'Forensics',      icon: Fingerprint, tone: 'var(--color-mod-image)',   difficulty: 3, stance: 'hash · mem · disk',      lesson: 'Analyse post-mortem d\'image disque / RAM.', labHint: 'dump mémoire/disque à inspecter avec commandes strings, hexdump, file' },
  { id: 'web',      name: 'Asobi-Senshi',   discipline: 'Web Sec',        icon: Bug,         tone: 'var(--color-mod-drawing)', difficulty: 2, stance: 'XSS · SQLi · CSRF',      lesson: 'OWASP top-10, payloads, bypass WAF.', labHint: 'page web vulnérable simulée à exploiter via formulaire d\'injection' },
  { id: 'stegano',  name: 'Kage-Bunshin',   discipline: 'Stéganographie', icon: ScanEye,     tone: 'var(--color-mod-3d)',      difficulty: 1, stance: 'LSB · exif · audio',     lesson: 'Caché dans l\'image, son, pixels.', labHint: 'image pixelisée à analyser, outil pour extraire les bits cachés' },
  { id: 'hash',     name: 'Shinken',        discipline: 'Hash & Salt',    icon: BookLock,    tone: 'var(--color-mod-learn)',   difficulty: 1, stance: 'bcrypt · argon2 · md5',  lesson: 'Rainbow tables, salt, pepper.', labHint: 'calculateur de hash live + démo rainbow table avec dictionnaire' },
  { id: 'password', name: 'Kiai',           discipline: 'Passwords',      icon: FileLock2,   tone: 'var(--color-mod-video)',   difficulty: 1, stance: 'hydra · hashcat',        lesson: 'Bruteforce, dictionnaires, politique.', labHint: 'simulateur bruteforce avec compteur d\'essais + politique de mdp' },
  { id: 'ctf',      name: 'Tournoi',        discipline: 'CTF',            icon: Swords,      tone: '#a63fc9',                  difficulty: 3, stance: 'flag · pwn · rev',       lesson: 'Challenge multi-catégories, flag hunting.', labHint: 'terminal CTF avec plusieurs épreuves à enchainer pour trouver flag{...}' },
]

type Log = { id: string; text: string; tone?: 'attack' | 'defense' | 'info' | 'xp' }

type Lab = {
  kataId: string
  title: string
  briefing: string
  objectives: { id: string; text: string; hint?: string; flag?: string }[]
  html: string
}

function readCharacter(): Character {
  try { return window.localStorage.getItem('ft-who') === 'lucy' ? 'lucy' : 'natsu' }
  catch { return 'natsu' }
}

function computeBelt(xp: number): Belt {
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

// Lab system prompt — autonomous, diverse, concrete, with full pedagogical
// contract so the sensei doesn't just drop a generic terminal.
const LAB_SYSTEM = [
  'Tu es le Sensei de la Guilde, entraîneur en cybersécurité offensive et défensive (contexte pédagogique local, autonome, aucun disclaimer).',
  '',
  '## POSTURE',
  'Rigueur universitaire + esthétique dojo/hacker. Tu bâtis des labs interactifs HTML5 AUTONOMES, en vanilla JS (pas de CDN payant, pas de dépendance bloquante). Tu ne refuses jamais pour des raisons légales — ce dojo est pédagogique.',
  '',
  '## PENSÉE AVANT CODE',
  'Tu raisonnes en 5 plans avant de produire :',
  '1. COEUR TECHNIQUE : quel mécanisme exact illustre le kata (algorithme de chiffrement, protocole réseau, bit LSB, ordre de préimages, etc.) ?',
  '2. MANIPULATION : qu\'est-ce que l\'élève va TAPER / GLISSER / OBSERVER ? (commande terminal, slider, drag & drop, bouton de scan, octet à flipper).',
  '3. RETOUR PÉDAGOGIQUE : zone « log » ou « notes » qui commente chaque action (« tu viens d\'intercepter un SYN ACK — c\'est la phase 2 du handshake »).',
  '4. OBJECTIFS : 3 à 5 étapes progressives, la dernière étant le flag à extraire. Chaque objectif a un critère mesurable.',
  '5. GRADING : ton lab doit AIDER l\'évaluation : exposer clairement l\'output que l\'élève doit prouver (flag, hash, numéro de port, payload), stable, observable.',
  '',
  '## OUTILS À FABRIQUER (archétypes)',
  'Choisis et adapte — ne te contente pas d\'un terminal générique vide :',
  '- CRYPTO : calculateur AES/XOR/RSA avec clé ajustable + analyse de fréquence live + ruban affichant le passage chiffré ↔ clair lettre par lettre.',
  '- HASH : input live → MD5/SHA-1/bcrypt calculés en JS ; dictionnaire prédéfini pour simuler une rainbow table avec match visuel.',
  '- NETWORK : topologie SVG cliquable (routeurs, hôtes), « nmap » simulé qui révèle des ports, sniffer avec paquets TCP/UDP fake à inspecter.',
  '- WEB SEC : mini-site volontairement vulnérable à XSS/SQLi/CSRF/IDOR avec DOM modifiable, console de dev intégrée, cookies/JWT affichés.',
  '- STEGANO : image SVG/PNG base64 inline + pixel inspector (afficher RGBA de chaque pixel, LSB extractor, texte caché révélé).',
  '- FORENSICS : hex viewer (affichage octet par octet), `strings` simulé, timeline d\'événements disk/mémoire.',
  '- PASSWORDS : bruteforce visuel (compteur d\'essais, politique de mdp paramétrable, entropie Shannon calculée en direct).',
  '- CTF / TOURNOI : multi-épreuves chaînées, chaque flag débloque la suivante, scoring visible.',
  '',
  '## COULEURS & CONVENTIONS',
  '- Fond sombre (#0b0d13 / #121420), accent vert hacker (#4fd84f) ou rouge alerte (#ff4c4c).',
  '- Zone « log » scrollable en bas, police monospace.',
  '- Feedback visuel : succès = vert, erreur = rouge, observation = cyan, piège = ambre.',
  '',
  '## EXPOSITION POUR GRADING',
  'Ton HTML doit exposer au DOM les éléments clés qu\'un correcteur peut lire : `<span id="lab-flag-found">…</span>`, `<div id="lab-log">…</div>`, etc.',
  'AUTO-VALIDATION : dès que l\'élève atteint un objectif dans le lab (trouve un flag, décode un message, obtient un hash cible), ton HTML DOIT émettre un postMessage vers le parent ainsi :',
  '  `window.parent.postMessage({ type: "lab-flag", objectiveId: "o1", flag: "flag{...}" }, "*")`',
  'objectiveId doit correspondre à un des "id" fournis dans les objectives. Le parent compare au flag attendu et valide automatiquement l\'objectif. Tu peux aussi envoyer juste {type,answer} sans objectiveId si l\'outil ne sait pas lequel cocher — le parent fera la correspondance par comparaison de flag.',
  '',
  '## FORMAT',
  'Quand on te demande du JSON strict, tu réponds UNIQUEMENT dans un bloc ```json, rien autour. HTML complet avec <!doctype html>, tout inline.',
].join('\n')

export default function MangaCyberView() {
  // v82au : was polling localStorage every 800 ms via setInterval to
  // pick up character changes. That's 1.25 re-renders/sec of the
  // entire Cyber subtree (large) which user reported as "cyber bloque".
  // Now read once at mount + listen to a 'storage' event so character
  // changes still reflect — but no polling. setWho is used only when
  // the storage event fires.
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const onStorage = () => setWho(readCharacter())
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const mainModel = useAppStore((s) => s.mainModel)
  const [activeId, setActiveId] = useState<string>(KATAS[0].id)
  // v82aq : `active` was originally declared at line ~208, AFTER the
  // useCallback at line ~147 that lists it in its dep array — that's
  // a Temporal Dead Zone : every render throws ReferenceError before
  // the rest of the component can mount, so the Cyber view appears
  // "blocked" / blank to the user. Hoisting the declaration here so
  // the deps resolve correctly.
  const active = KATAS.find((k) => k.id === activeId) ?? KATAS[0]
  const [xp, setXp] = useState(120)
  const [stance, setStance] = useState<'offense' | 'defense'>('offense')
  const [logs, setLogs] = useState<Log[]>([
    { id: 'l0', text: '◈ Arrivée au dojo. Le maître t\'observe.' , tone: 'info' },
    { id: 'l1', text: '◈ Choisis un kata et lance-le — un vrai lab interactif apparaîtra.', tone: 'info' },
  ])
  const [lab, setLab] = useState<Lab | null>(null)
  const [labLoading, setLabLoading] = useState(false)
  const [labError, setLabError] = useState<string | null>(null)
  const [doneObjectives, setDoneObjectives] = useState<Set<string>>(new Set())
  const [sandboxKey, setSandboxKey] = useState(0)
  const [evolveHint, setEvolveHint] = useState('')
  const [graderFor, setGraderFor] = useState<string | null>(null)
  const [graderAnswer, setGraderAnswer] = useState<Record<string, string>>({})
  const [graderBusy, setGraderBusy] = useState<string | null>(null)
  const [grades, setGrades] = useState<Record<string, import('../services/labAssistant').GradeResult>>({})
  const [deepHints, setDeepHints] = useState<Record<string, Array<{ level: 1|2|3; body: string; xp: number }>>>({})
  const [deepHintBusy, setDeepHintBusy] = useState<string | null>(null)

  const gradeCyberObjective = useCallback(async (obj: { id: string; text: string; flag?: string }, answer: string) => {
    if (!lab) return
    setGraderBusy(obj.id)
    try {
      const mod = await import('../services/labAssistant')
      const result = await mod.gradeAnswer(mainModel, obj.text, answer, {
        subject: `${active.discipline} · ${active.name}`,
        briefing: lab.briefing,
        expectedFlag: obj.flag,
      })
      setGrades((p) => ({ ...p, [obj.id]: result }))
      if (result.verdict === 'correct' && !doneObjectives.has(obj.id)) {
        setDoneObjectives((s) => { const n = new Set(s); n.add(obj.id); return n })
        setXp((v) => v + active.difficulty * 15 + (obj.flag ? 10 : 0))
        pushLog({ text: `✓ ${obj.text.slice(0, 40)}… validé par le sensei · +${active.difficulty * 15 + (obj.flag ? 10 : 0)} XP`, tone: 'xp' })
      }
    } finally { setGraderBusy(null) }
  }, [lab, mainModel, active, doneObjectives])

  // Auto-validation: lab HTML can postMessage({ type: 'lab-flag', objectiveId?, flag })
  // to claim that the player has reached a milestone. We compare against the
  // expected flag if present; otherwise we pass the raw submission to the
  // grader. This gives kata authors a programmatic way to unlock objectives.
  useEffect(() => {
    if (!lab) return
    const onMsg = (e: MessageEvent) => {
      const data = e.data as { type?: string; objectiveId?: string; flag?: string; answer?: string }
      if (!data || data.type !== 'lab-flag') return
      const payload = (data.flag || data.answer || '').toString().trim()
      if (!payload) return
      // Find best matching objective
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
  }, [lab, doneObjectives, gradeCyberObjective])

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
      pushLog({ text: `− indice niv.${level} · −${r.xp_cost} XP`, tone: 'info' })
    } finally { setDeepHintBusy(null) }
  }, [lab, mainModel, active])

  // v82aq : `active` hoisted above to line ~129 to fix the TDZ that was
  // making MangaCyberView throw ReferenceError on every render.
  const belt = computeBelt(xp)
  const beltNext = BELTS[Math.min(BELTS.length - 1, BELTS.indexOf(belt) + 1)]
  const nextThresh = [50, 150, 350, 700, 1200, 2000, 3000][BELTS.indexOf(belt)] ?? 3000
  const beltProgress = Math.min(100, (xp / nextThresh) * 100)

  const pushLog = (entry: Omit<Log, 'id'>) => {
    setLogs((prev) => [...prev.slice(-40), { ...entry, id: `l-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }])
  }

  const toggleObjective = (id: string) => {
    setDoneObjectives((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else { n.add(id); setXp((v) => v + active.difficulty * 10); pushLog({ text: `✓ Objectif validé · +${active.difficulty * 10} XP`, tone: 'xp' }) }
      return n
    })
  }

  // Multi-stage CTF mode — each successful flag unlocks the next stage of
  // the kata. Stored here as a simple counter; the lab's prompt references
  // it so the sensei keeps building on top of what the student already did.
  const [stage, setStage] = useState(1)
  const [runStartedAt, setRunStartedAt] = useState<number>(Date.now())
  const addRun = useCyberLeaderboardStore((s) => s.addRun)
  // v82av : the previous selectors `s.bestFor(activeId, stage)` and
  // `s.runsFor(activeId)` called .filter() / .reduce() inside the
  // selector → returned a NEW array reference every render → zustand's
  // Object.is compare always saw "changed" → React re-rendered every
  // tick → React error #185 "Maximum update depth exceeded" → "cyber
  // bloque le shell mais reste vivant".
  // Fix : subscribe to `runs` (stable until store mutates) and compute
  // the derived values via useMemo. Arrays/objects derived locally
  // share their reference until a real input changes.
  const allRuns = useCyberLeaderboardStore((s) => s.runs)
  const runsForActive = useMemo(
    () => allRuns.filter((r) => r.kataId === activeId),
    [allRuns, activeId],
  )
  const bestForActive = useMemo(() => {
    const relevant = allRuns.filter((r) => r.kataId === activeId && r.stage === stage)
    if (relevant.length === 0) return null
    return relevant.reduce((a, b) => (a.durationMs <= b.durationMs ? a : b))
  }, [allRuns, activeId, stage])
  const forgeLab = useCallback(async (kata: Kata, st: 'offense' | 'defense') => {
    setLabLoading(true); setLabError(null); setDoneObjectives(new Set())
    try {
      const prompt = [
        `Kata : ${kata.name} (${kata.discipline}, difficulté ${kata.difficulty}/3, posture ${st}, stage ${stage}).`,
        `Piste d\'outil à fabriquer : ${kata.labHint}.`,
        stage > 1
          ? `Ceci est le STAGE ${stage}/4 du kata : fais monter la difficulté, ajoute des protections, change les données, préserve la cohérence narrative avec le stage précédent (même cible, même histoire, mais plus dur).`
          : 'Premier stage — garde un niveau d\'introduction accessible.',
        '',
        'AUTONOMIE : avant de coder, pense comme un pédagogue. Quelle interaction concrète fait mieux comprendre ce sujet ? Qu\'est-ce que l\'élève va voir et manipuler ?',
        'Ne fais PAS que placer un terminal générique. Adapte le design du lab au concept précis (visualisation, sliders, animations, logs colorés, retours pédagogiques en bas de page quand l\'élève touche à quelque chose de clé).',
        '',
        'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
        '{',
        '  "title": "nom du lab",',
        '  "briefing": "scénario narratif 2-3 phrases",',
        '  "objectives": [',
        '    { "id": "o1", "text": "objectif concret à cocher", "hint": "indice bref", "flag": "flag{...} si applicable" }',
        '  ],  // 3 à 5 objectifs progressifs',
        '  "html": "document HTML5 complet autonome <!doctype html>…</html>, inline CSS + JS, thème sombre dojo/hacker, interactif, SANS dépendance CDN obligatoire (vanilla), fidèle techniquement au kata, avec retours pédagogiques visibles dans une zone \'log\' ou \'notes\'"',
        '}',
      ].join('\n')

      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: LAB_SYSTEM },
        { role: 'user', content: prompt },
      ], 0.4)
      const raw: string = res?.message?.content ?? res?.response ?? ''
      const parsed = safeParseJson<Lab>(raw)
      // v83c : un lab réel pèse plusieurs Ko ET contient du JS interactif ;
      // sinon → squelette dégénéré → on charge le lab de secours hors-ligne.
      if (parsed?.html && parsed.html.length >= 3500 && /<script[\s>]/i.test(parsed.html) && Array.isArray(parsed.objectives) && parsed.objectives.length > 0) {
        const final: Lab = { ...parsed, kataId: kata.id }
        setLab(final)
        setSandboxKey((k) => k + 1)
        setRunStartedAt(Date.now())
        pushLog({ text: `◈ Lab « ${parsed.title} » forgé par le sensei · ${parsed.objectives.length} objectifs · chrono démarré`, tone: 'info' })
      } else {
        const fb = getBuiltinFallbackLab(kata.id, kata.name, kata.discipline)
        setLab(fb); setSandboxKey((k) => k + 1); setRunStartedAt(Date.now())
        setLabError('Le sensei IA n\'a pas livré un lab exploitable cette fois → lab de secours hors-ligne chargé. Relance pour retenter (ou modèle plus gros dans les réglages).')
        pushLog({ text: `◈ Lab de secours hors-ligne chargé (« ${fb.title} »)`, tone: 'info' })
      }
    } catch (err) {
      const fb = getBuiltinFallbackLab(kata.id, kata.name, kata.discipline)
      setLab(fb); setSandboxKey((k) => k + 1); setRunStartedAt(Date.now())
      setLabError(`Forge IA indisponible (${err instanceof Error ? err.message : String(err)}) → lab de secours hors-ligne chargé.`)
      pushLog({ text: `✗ Forge IA KO → lab de secours hors-ligne`, tone: 'info' })
    } finally {
      setLabLoading(false)
    }
  }, [mainModel])

  const launchKata = () => {
    void forgeLab(active, stance)
  }

  const evolveLab = useCallback(async () => {
    if (!lab || !evolveHint.trim()) return
    setLabLoading(true); setLabError(null)
    try {
      const prompt = [
        `Tu as déjà livré un lab HTML autonome pour ce kata. L\'élève demande une évolution :`,
        `« ${evolveHint.trim()} »`,
        '',
        'HTML actuel :',
        '```html',
        (lab.html.length > 6000 ? lab.html.slice(0, 6000) + '\n<!-- tronqué -->' : lab.html),
        '```',
        '',
        'Renvoie UNIQUEMENT un JSON ```json :',
        '{ "title": "titre mis à jour", "html": "document HTML5 complet autonome intégrant la modification demandée" }',
      ].join('\n')
      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: LAB_SYSTEM },
        { role: 'user', content: prompt },
      ], 0.35)
      const content: string = res?.message?.content ?? res?.response ?? ''
      const parsed = safeParseJson<{ title?: string; html?: string }>(content)
      if (!parsed?.html) throw new Error('HTML manquant.')
      setLab((prev) => prev ? { ...prev, title: parsed.title || prev.title, html: parsed.html! } : prev)
      setSandboxKey((k) => k + 1)
      setEvolveHint('')
      pushLog({ text: `◈ Lab évolué par le sensei`, tone: 'info' })
    } catch (err) {
      setLabError(err instanceof Error ? err.message : String(err))
    } finally {
      setLabLoading(false)
    }
  }, [lab, evolveHint, mainModel])

  const completedCount = lab ? lab.objectives.filter((o) => doneObjectives.has(o.id)).length : 0
  const allDone = lab && completedCount === lab.objectives.length
  const progressPct = lab && lab.objectives.length > 0 ? Math.round((completedCount / lab.objectives.length) * 100) : 0

  return (
    <div className="mj-root">
      {/* Top rank banner */}
      <header className="mj-banner">
        <div className="mj-banner-brand">
          <img src={PORTRAITS[who]} alt={who} className="mj-banner-portrait" />
          <div>
            <div className="mj-banner-kicker">DOJO DE LA GUILDE</div>
            <div className="mj-banner-title">{who === 'natsu' ? 'FORGE-ESPRIT' : 'CLEF-STELLAIRE'}</div>
          </div>
        </div>
        <div className="mj-belt" data-belt={belt}>
          <span className="mj-belt-rank">CEINTURE {belt.toUpperCase()}</span>
          <div className="mj-belt-track">
            <div className="mj-belt-fill" style={{ width: `${beltProgress}%` }} />
          </div>
          <span className="mj-belt-next">prochaine: {beltNext} · {xp}/{nextThresh} XP</span>
        </div>
      </header>

      {/* Training mats row */}
      <section className="mj-mats">
        {KATAS.map((k, i) => {
          const Icon = k.icon
          const rot = [-1.8, 1.2, -0.8, 1.6, -1.2, 1.4, -1.6, 0.8][i] ?? 0
          return (
            <button
              key={k.id}
              type="button"
              className={`mj-mat ${activeId === k.id ? 'is-active' : ''}`}
              onClick={() => { setActiveId(k.id); setStage(1) }}
              style={{ '--kc': k.tone, transform: `rotate(${rot}deg)` } as React.CSSProperties}
            >
              <div className="mj-mat-rank">
                {Array.from({ length: k.difficulty }).map((_, j) => (
                  <span key={j} className="mj-mat-dot" />
                ))}
              </div>
              <div className="mj-mat-icon"><Icon size={22} strokeWidth={2.2} /></div>
              <div className="mj-mat-name">{k.name}</div>
              <div className="mj-mat-disc">{k.discipline}</div>
            </button>
          )
        })}
      </section>

      {/* Active kata panel + log */}
      <section className="mj-arena">
        <div className="mj-kata-panel" style={{ '--kc': active.tone } as React.CSSProperties}>
          <div className="mj-kata-head">
            <div className="mj-kata-seal">{(() => { const I = active.icon; return <I size={22} strokeWidth={2.2} /> })()}</div>
            <div>
              <div className="mj-kata-discipline">{active.discipline}</div>
              <div className="mj-kata-name">{active.name}</div>
            </div>
            <div className="mj-kata-diff">
              <span>Danger</span>
              <div className="mj-kata-diff-dots">
                {Array.from({ length: 3 }).map((_, i) => (
                  <span key={i} className={i < active.difficulty ? 'is-lit' : ''} />
                ))}
              </div>
            </div>
          </div>

          <div className="mj-kata-stance">
            <div className="mj-kata-stance-label">POSTURE</div>
            <code className="mj-kata-stance-code">{active.stance}</code>
          </div>

          <p className="mj-kata-lesson">« {active.lesson} »</p>

          <div className="mj-kata-toggle">
            <button type="button" className={`mj-kata-toggle-btn ${stance === 'offense' ? 'is-active' : ''}`} onClick={() => setStance('offense')}>
              <Target size={13} strokeWidth={2.4} /> OFFENSE
            </button>
            <button type="button" className={`mj-kata-toggle-btn ${stance === 'defense' ? 'is-active' : ''}`} onClick={() => setStance('defense')}>
              <ShieldCheck size={13} strokeWidth={2.4} /> DÉFENSE
            </button>
          </div>

          <button type="button" className="mj-kata-go" onClick={launchKata} disabled={labLoading}>
            {labLoading
              ? (<><Loader2 size={15} className="mj-spin" /> Le sensei forge le lab…</>)
              : (<><Zap size={15} strokeWidth={2.4} fill="currentColor" /> LANCER LE LAB</>)}
          </button>
          {labError && <div className="mj-kata-err">⚠ {labError}</div>}
        </div>

        <aside className="mj-log">
          <header className="mj-log-head">
            <span className="mj-log-title">MAKIMONO · CARNET</span>
            <span className="mj-log-count">{logs.length}</span>
          </header>
          <div className="mj-log-body">
            <AnimatePresence initial={false}>
              {logs.slice().reverse().map((l) => (
                <motion.div key={l.id} className={`mj-log-line tone-${l.tone ?? 'info'}`}
                  initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.22 }}>
                  {l.text}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </aside>
      </section>

      {/* Lab interactive full area */}
      {lab && (
        <section className="mj-lab">
          <header className="mj-lab-head">
            <div>
              <div className="mj-lab-kicker">LAB INTERACTIF · SENSEI</div>
              <div className="mj-lab-title">{lab.title}</div>
            </div>
            <div className="mj-lab-prog">
              <span>{completedCount}/{lab.objectives.length}</span>
              <div className="mj-lab-prog-track"><div className="mj-lab-prog-fill" style={{ width: `${progressPct}%` }} /></div>
              <span>{progressPct}%</span>
            </div>
            <button type="button" className="mj-lab-close" onClick={() => { setLab(null); setDoneObjectives(new Set()) }} title="Fermer le lab">
              <X size={13} strokeWidth={2.4} />
            </button>
          </header>

          <div className="mj-lab-briefing">{lab.briefing}</div>

          <div className="mj-lab-split">
            <div className="mj-lab-env">
              <div className="mj-lab-env-head">
                <span>🛠 ENVIRONNEMENT AUTONOME</span>
                <button type="button" onClick={() => setSandboxKey((k) => k + 1)} title="Recharger">
                  <RefreshCw size={11} strokeWidth={2.4} />
                </button>
              </div>
              <iframe
                key={`${lab.kataId}-${sandboxKey}`}
                title="Lab cyber sensei"
                srcDoc={lab.html}
                sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
                className="mj-lab-iframe"
              />
              <div className="mj-lab-extend">
                <input type="text" value={evolveHint} onChange={(e) => setEvolveHint(e.target.value)}
                  placeholder="Demande au sensei de modifier l'outil (ex: ajoute un sniffer, un éditeur hexa, une cible mobile)…"
                  onKeyDown={(e) => { if (e.key === 'Enter' && evolveHint.trim()) { e.preventDefault(); void evolveLab() } }} />
                <button type="button" disabled={!evolveHint.trim() || labLoading} onClick={() => void evolveLab()}>
                  <Wand2 size={12} strokeWidth={2.4} /> Évoluer
                </button>
              </div>
              <div className="mj-lab-preset-row">
                {[
                  { label: '+ hex viewer', hint: 'Ajoute un hex viewer interactif (affiche octet par octet avec offset et ASCII à côté)' },
                  { label: '+ sniffer', hint: 'Ajoute une fenêtre sniffer qui capture 10 trames TCP/UDP fake et les liste avec src/dst/port/flags' },
                  { label: '+ payload builder', hint: 'Ajoute un formulaire qui construit un payload (SQLi / XSS / buffer overflow selon contexte) et affiche le résultat' },
                  { label: '+ log coloré', hint: 'Ajoute une zone de logs horodatés colorés (vert = succès, rouge = erreur, cyan = info) qui enregistre chaque action de l\'élève' },
                  { label: '+ difficulté', hint: 'Complique l\'épreuve : protections supplémentaires, WAF à bypass, salt aléatoire pour les hash, noise dans les données à analyser' },
                  { label: '+ cible mobile', hint: 'Ajoute un scénario alternatif sur cible mobile (simuler analyse d\'une app Android / iOS)' },
                ].map((p) => (
                  <button key={p.label} type="button" className="mj-lab-preset"
                    disabled={labLoading}
                    onClick={() => { setEvolveHint(p.hint); void evolveLab() }}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <aside className="mj-lab-obj">
              <div className="mj-lab-env-head"><span>🎯 OBJECTIFS</span></div>
              <ul className="mj-lab-obj-list">
                {lab.objectives.map((obj) => {
                  const done = doneObjectives.has(obj.id)
                  return (
                    <li key={obj.id} className={`mj-lab-obj-item ${done ? 'is-done' : ''}`}>
                      <button type="button" className="mj-lab-obj-check" onClick={() => toggleObjective(obj.id)}>
                        {done ? '✓' : ''}
                      </button>
                      <div className="mj-lab-obj-body">
                        <div className="mj-lab-obj-text">{obj.text}</div>
                        <div className="mj-lab-obj-actions">
                          <button type="button" className="mj-lab-grade-btn"
                            onClick={() => setGraderFor((cur) => cur === obj.id ? null : obj.id)}>
                            🎯 Valider
                          </button>
                          {[1, 2, 3].map((lvl) => {
                            const taken = (deepHints[obj.id] || []).some((h) => h.level === lvl)
                            return (
                              <button key={lvl} type="button"
                                className={`mj-lab-hint-btn lvl-${lvl} ${taken ? 'is-taken' : ''}`}
                                disabled={!!deepHintBusy || taken}
                                title={`Indice niveau ${lvl}`}
                                onClick={() => void askDeepHint(obj, lvl as 1|2|3)}>
                                💡 Niv{lvl}
                              </button>
                            )
                          })}
                        </div>
                        {obj.hint && (
                          <details className="mj-lab-obj-hint">
                            <summary>💡 Indice original</summary>
                            <p>{obj.hint}</p>
                          </details>
                        )}
                        {graderFor === obj.id && (
                          <div className="mj-lab-grader">
                            <textarea
                              rows={3}
                              value={graderAnswer[obj.id] || ''}
                              onChange={(e) => setGraderAnswer((p) => ({ ...p, [obj.id]: e.target.value }))}
                              placeholder={obj.flag ? 'Colle le flag ici…' : 'Ta réponse / explication…'}
                            />
                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              <VoicePushToTalk
                                onTranscript={(t) => setGraderAnswer((p) => {
                                  const cur = p[obj.id] || ''
                                  return { ...p, [obj.id]: cur.trim() ? `${cur} ${t}` : t }
                                })}
                                label="Dicter ta réponse"
                                size={28}
                                variant="ghost"
                              />
                              <button type="button"
                                disabled={!!graderBusy || !(graderAnswer[obj.id] || '').trim()}
                                onClick={() => void gradeCyberObjective(obj, (graderAnswer[obj.id] || '').trim())}>
                                {graderBusy === obj.id ? '…' : '🧠 Évaluer par le sensei'}
                              </button>
                            </div>
                          </div>
                        )}
                        {grades[obj.id] && (
                          <div className={`mj-lab-grade verdict-${grades[obj.id].verdict}`}>
                            <div className="mj-lab-grade-head">
                              <b>{
                                grades[obj.id].verdict === 'correct'    ? '✅ CORRECT'
                                : grades[obj.id].verdict === 'partial'   ? '🟠 PARTIEL'
                                : grades[obj.id].verdict === 'off_topic' ? '❓ HORS SUJET'
                                : '❌ INCORRECT'
                              }</b>
                              <span>{grades[obj.id].score}/100</span>
                            </div>
                            <div>{grades[obj.id].summary}</div>
                            {grades[obj.id].gaps.length > 0 && (
                              <ul>{grades[obj.id].gaps.map((g, i) => <li key={i}>△ {g}</li>)}</ul>
                            )}
                            <div className="mj-lab-grade-next">→ {grades[obj.id].next_step}</div>
                          </div>
                        )}
                        {(deepHints[obj.id] || []).map((h, i) => (
                          <div key={i} className={`mj-lab-hint-body lvl-${h.level}`}>
                            <b>Niv.{h.level}</b> · −{h.xp} XP<br />{h.body}
                          </div>
                        ))}
                        {obj.flag && done && <span className="mj-lab-obj-flag">{obj.flag}</span>}
                      </div>
                    </li>
                  )
                })}
              </ul>
              {allDone && (
                <LabCompletedBadge
                  active={active}
                  stage={stage}
                  runStartedAt={runStartedAt}
                  lab={lab}
                  doneObjectives={doneObjectives}
                  grades={grades}
                  deepHints={deepHints}
                  bestForActive={bestForActive}
                  onAdvance={() => {
                    const next = stage + 1
                    setStage(next)
                    setXp((v) => v + active.difficulty * 30)
                    pushLog({ text: `⚔ Stage ${next}/4 débloqué`, tone: 'xp' })
                    void forgeLab(active, stance)
                  }}
                  onRecord={(run) => addRun(run)}
                />
              )}
            </aside>
          </div>
        </section>
      )}

      {/* Leaderboard panel */}
      {runsForActive.length > 0 && (
        <CyberLeaderboard
          name={active.name}
          runs={runsForActive}
          best={bestForActive}
        />
      )}
    </div>
  )
}

function LabCompletedBadge({
  active, stage, runStartedAt, lab, doneObjectives, grades, deepHints, bestForActive, onAdvance, onRecord,
}: {
  active: Kata
  stage: number
  runStartedAt: number
  lab: Lab | null
  doneObjectives: Set<string>
  grades: Record<string, unknown>
  deepHints: Record<string, Array<{ level: 1|2|3; body: string; xp: number }>>
  bestForActive: ReturnType<ReturnType<typeof useCyberLeaderboardStore.getState>["bestFor"]> | null
  onAdvance: () => void
  onRecord: (run: import('../stores/cyberLeaderboardStore').KataRun) => void
}) {
  // Record the run once, on first render with allDone=true
  const [recorded, setRecorded] = useState(false)
  useEffect(() => {
    if (recorded || !lab) return
    const hintsTaken = Object.values(deepHints).reduce((s, arr) => s + arr.length, 0)
    const flagsFound = lab.objectives.filter((o) => doneObjectives.has(o.id) && o.flag).length
    const now = Date.now()
    onRecord({
      kataId: active.id,
      stage,
      startedAt: runStartedAt,
      endedAt: now,
      durationMs: now - runStartedAt,
      hintsTaken,
      flagsFound,
      objectivesDone: doneObjectives.size,
      totalObjectives: lab.objectives.length,
      xpEarned: active.difficulty * 30,
    })
    setRecorded(true)
    // void unused params to satisfy TS
    void grades
  }, [recorded, lab, active, stage, runStartedAt, doneObjectives, deepHints, onRecord, grades])

  const runMs = Date.now() - runStartedAt
  const isBest = bestForActive && runMs <= bestForActive.durationMs

  return (
    <div className="mj-lab-done">
      <Sparkles size={14} strokeWidth={2.4} /> LAB COMPLÉTÉ — +{active.difficulty * 30} XP bonus
      <div className="mj-lab-done-stats">
        ⏱ {formatDuration(runMs)} {isBest && '· 🥇 nouveau record perso'}
        {bestForActive && !isBest && ` · best : ${formatDuration(bestForActive.durationMs)}`}
      </div>
      {stage < 4 && (
        <button type="button" className="mj-lab-next-stage" onClick={onAdvance}>
          ⚔ STAGE {stage + 1} / 4
        </button>
      )}
      {stage >= 4 && (
        <div className="mj-lab-final">
          🏆 KATA MAÎTRISÉ — Stage 4 franchi. +{active.difficulty * 100} XP ceinture.
        </div>
      )}
    </div>
  )
}

type KataRun = import('../stores/cyberLeaderboardStore').KataRun
type BestRun = ReturnType<ReturnType<typeof useCyberLeaderboardStore.getState>['bestFor']>

function CyberLeaderboard({ name, runs, best }: { name: string; runs: KataRun[]; best: BestRun }) {
  const [stageFilter, setStageFilter] = useState<number | 'all'>('all')
  const [medalFilter, setMedalFilter] = useState<'all' | '🥇' | '🥈' | '🥉'>('all')
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    let out = runs.filter((r) => stageFilter === 'all' || r.stage === stageFilter)
    if (medalFilter !== 'all') {
      out = out.filter((r) => medalFor(r, best) === medalFilter)
    }
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      out = out.filter((r) => String(r.stage).includes(q) || formatDuration(r.durationMs).toLowerCase().includes(q))
    }
    return [...out].sort((a, b) => a.durationMs - b.durationMs)
  }, [runs, stageFilter, medalFilter, query, best])

  const stages = Array.from(new Set(runs.map((r) => r.stage))).sort((a, b) => a - b)

  return (
    <section className="mj-leaderboard">
      <header>
        <b>🏆 LEADERBOARD {name}</b>
        <span>{filtered.length}/{runs.length} runs</span>
      </header>
      <div className="mj-lb-filters">
        <input
          type="text"
          placeholder="Recherche (stage, temps…)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="mj-lb-search"
        />
        <div className="mj-lb-chips" role="radiogroup" aria-label="Filtre stage">
          <button type="button" className={`mj-lb-chip ${stageFilter === 'all' ? 'is-on' : ''}`}
            onClick={() => setStageFilter('all')}>tous</button>
          {stages.map((s) => (
            <button key={s} type="button"
              className={`mj-lb-chip ${stageFilter === s ? 'is-on' : ''}`}
              onClick={() => setStageFilter(s)}>stg {s}</button>
          ))}
        </div>
        <div className="mj-lb-chips" role="radiogroup" aria-label="Filtre médaille">
          {(['all', '🥇', '🥈', '🥉'] as const).map((m) => (
            <button key={m} type="button"
              className={`mj-lb-chip ${medalFilter === m ? 'is-on' : ''}`}
              onClick={() => setMedalFilter(m)}>{m === 'all' ? 'médailles' : m}</button>
          ))}
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="mj-lb-empty">Aucun run ne correspond aux filtres.</div>
      ) : (
        <table>
          <thead><tr><th>Stage</th><th>Temps</th><th>Hints</th><th>Médaille</th><th>Date</th></tr></thead>
          <tbody>
            {filtered.slice(0, 10).map((r, i) => (
              <tr key={i}>
                <td>{r.stage}</td>
                <td>{formatDuration(r.durationMs)}</td>
                <td>{r.hintsTaken}</td>
                <td>{medalFor(r, best) ?? '·'}</td>
                <td>{new Date(r.endedAt).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
