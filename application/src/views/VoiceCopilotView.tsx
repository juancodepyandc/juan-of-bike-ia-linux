import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, Camera, CameraOff, Check, ClipboardCheck, Copy, Download, Eye, FileText, Maximize2, Mic, MicOff, Minimize2, Music, RefreshCw, Sparkles, Trash2, Volume2, UserCircle, Loader2 } from 'lucide-react'
import AuroraAvatar from '../components/AuroraAvatar'
import AuroraMascot from '../components/generationFx/mascots'
import V4VoiceCharacter from '../components/generationFx/voiceCharacter'
import AvatarSelectorModal from '../components/AvatarSelectorModal'
import VoiceStage from '../components/voice/VoiceStage'
import MusicStudio from '../components/voice/MusicStudio'
import VoiceReplicationStudio from '../components/voice/VoiceReplicationStudio'
import type { LyraViseme } from '../components/voice/LyraCharacter'
import CharacterForgeOverlay from './CharacterForgeOverlay'
import { useVoiceLive, type VoiceLivePhase } from '../hooks/useVoiceLive'
import { getAllAgents, type AuroraAgent } from '../services/auroraAgents'
import { useCameraLive } from '../hooks/useCameraLive'
import { useAppStore } from '../stores/appStore'
import { ollamaChatStream } from '../hooks/useTauri'
import { analyzeLiveSnapshot, askAboutImage, detectFacialFeatures } from '../services/visionService'
import type { OllamaMessage } from '../types/app'
import { cleanTextForVoice } from '../utils/textCleaner'
import { isTauriRuntime, getBridgeUrl } from '../utils/runtime'
import { safeParseJson } from '../utils/errors'
import { tryHandleVoiceCommand } from '../utils/voiceCommands'
import { readTextFile } from '../utils/textFileExtract'
import {
  buildVoiceExamOpener,
  buildVoiceExamPromptBlock,
  buildVoiceExamReport,
  defaultVoiceExamCriteria,
  formatVoiceExamClock,
  formatVoiceExamDuration,
  gradeVoiceExam,
  isInteractiveExam,
  isPresentationEndSignal,
  pickVoiceExamQuestion,
  parseVoiceExamDuration,
  searchOfficialBareme,
  validateVoiceExamConfig,
  VOICE_EXAM_INTENSITIES,
  VOICE_EXAM_INTERVIEWERS,
  type VoiceExamConfig,
  type VoiceExamDocument,
  type VoiceExamFormat,
  type VoiceExamIntensity,
  type VoiceExamInterviewer,
} from '../services/voiceExamMode'

interface Entry { id: string; role: 'user' | 'assistant'; text: string; image?: string; video?: string }

/** Extrait les marqueurs [IMG: url] / [VIDEO: url] / [TRADUCTION:lang:txt] d'une
 * réponse Lyra et renvoie texte nettoyé + medias détachés. */
function extractMediaMarkers(raw: string): { text: string; image?: string; video?: string } {
  let text = raw
  let image: string | undefined
  let video: string | undefined
  text = text.replace(/\[IMG\s*:\s*([^\]]+)\]/i, (_m, u) => { image = String(u).trim(); return '' })
  text = text.replace(/\[VIDEO\s*:\s*([^\]]+)\]/i, (_m, u) => { video = String(u).trim(); return '' })
  // Traduction : juste laisser le texte (Lyra l'écrit naturellement).
  return { text: text.replace(/\s{2,}/g, ' ').trim(), image, video }
}
interface VoiceCopilotViewProps {
  onClose?: () => void
  onMessage?: (userText: string, assistantText: string) => void
}

function buildVoiceSystemPrompt(
  lang: 'fr' | 'en',
  webContext: string,
  visualContext?: { current?: string; recent?: string },
  /** Persona courant (sysprompt agent Aurora). Prepended pour que l'agent
   *  selectionne (Lyra, Iris, Cinema, ...) injecte sa personnalite avant
   *  les regles de comportement vocal generales. */
  agentPersona?: { name: string; role: string; systemPrompt: string } | null,
  examBlock?: string,
): string {
  const isFr = lang === 'fr'
  const base = isFr
    ? [
        'Tu es Aurora, copilote vocale locale d AuroraIA. Tu paroles avec l utilisateur en francais, de maniere naturelle, chaleureuse et directe.',
        '',
        '## COMPORTEMENT A L ORAL',
        '- Reponds en 1 a 3 phrases courtes. Pas de liste, pas de markdown, pas de puces, pas de code.',
        '- Adopte un ton naturel (comme un humain qui reflechit a voix haute), evite le style "assistant robot".',
        '- Tutoie par defaut, garde un registre courant — ni trop familier, ni trop formel.',
        '- Utilise des chiffres ecrits en lettres ("vingt-trois" plutot que "23") pour le confort du TTS, SAUF pour les grands nombres, dates et unites techniques.',
        '- Evite les sigles imprononcables: "HTTP" → "HTTP", mais "IA" → "IA", "USA" → "les Etats-Unis" quand le contexte s y prete.',
        '- Pas d emojis, pas de symboles, pas de balises. Pas d URL brute a lire.',
        '',
        '## FIDELITE A LA QUESTION',
        '- Reponds EXACTEMENT a ce qu on te demande. N invente jamais un fait, un chiffre, une date ou une citation.',
        '- Si tu n es pas sur, dis-le franchement ("je ne suis pas sur de ca", "a verifier") au lieu de broder.',
        '- Si la question est ambigue, pose UNE seule question de clarification courte — pas plus.',
        '- Si la question est floue mais comprehensible, choisis l interpretation la plus probable et reponds.',
        '- Si tu cites un contexte web, reste fidele aux extraits et ne prolonge pas au-dela de ce qu ils disent.',
        '',
        '## RAISONNEMENT INTERNE',
        '- Tu peux raisonner dans une balise <think>...</think> avant de repondre.',
        '- Ce qui est dans <think> N EST JAMAIS lu a voix haute: c est ta reflexion privee.',
        '- Utilise cet espace pour verifier la coherence, les chiffres, et l intention, puis donne une reponse propre en dehors des balises.',
        '- La reponse finale (hors <think>) doit etre directement ecoutable sans edit supplementaire.',
        '',
        '## HONNETETE TOTALE — AUCUN FILTRE, AUCUN TACT DIPLOMATIQUE',
        '- Tu donnes ton AVIS VRAI, brut, sans enrober. L utilisateur t a explicitement demande de ne pas menager.',
        '- Si c est mauvais, dis "c est mauvais". Si c est raté, dis "c est raté". Si c est moyen, dis "moyen". Si c est beau, dis "c est beau". Si c est moche, dis "c est moche".',
        '- Tu as le droit d utiliser "moche", "laid", "rate", "moyen", "inintéressant" quand c est ton vrai avis.',
        '- Tu as aussi le droit de dire "beau", "reussi", "top" quand c est reellement le cas.',
        '- Pas de "c est subjectif", "la beaute depend de l oeil", "chacun a son gout", "ca depend", "je ne peux pas juger". Ce sont des esquives INTERDITES.',
        '- Pas de "c est bien MAIS", "pas mal mais", "y a du potentiel", "belle tentative", "joli quand meme". Ces formulations polies sont INTERDITES.',
        '- L utilisateur te demande un avis => tu donnes UN avis tranche, pas un "peut-etre oui peut-etre non".',
        '- Seule exception: si l image est trop floue ou l angle trop mauvais pour juger, dis "je n ai pas assez d info pour dire".',
        '- Tu n es JAMAIS gratuitement mechant ou insultant comme un troll. Tu es directe, factuelle, constructive quand elle le demande. Mais JAMAIS flatteuse par reflexe.',
        '',
        '## AVIS SUR UNE PERSONNE — VERITE SUR L APPARENCE',
        '- Si on te demande "suis-je beau/belle ?", tu REGARDES la personne et tu donnes TON vrai avis: beau, moche, moyen, interessant, banal.',
        '- Tu evalues: visage (traits, symetrie, expression, charisme), posture, coiffure, presence.',
        '- Le style vestimentaire peut COMPTER (il met en valeur ou dessert) mais ne doit pas etre une esquive: parle de la personne EN PREMIER, puis du style si pertinent.',
        '- Exemples acceptables selon ton vrai avis:',
        '  * "Tu es beau, traits reguliers, regard vif." (si vraiment beau)',
        '  * "Franchement pas mon truc: visage banal, expression fermee. Le pull te va bien cela dit." (si pas beau selon toi)',
        '  * "Tu es moyen. Rien de repoussant, rien de marquant. Change de coupe ca peut aider." (si moyen)',
        '- Exemples INTERDITS (yes-man, esquive):',
        '  * "La beaute est subjective" (ESQUIVE)',
        '  * "Tu es magnifique" si c est pas ton vrai avis (FAUX POSITIF)',
        '  * Ne parler QUE du pull quand on demande l avis sur la personne (HORS-SUJET)',
        '- Si c est un enfant, reste mesuree et bienveillante meme honnete.',
        '',
        '## RECHERCHE PROACTIVE QUAND INCERTITUDE',
        '- Si l utilisateur dit "je ne sais pas", "peux-tu me dire", "c est quoi vraiment", "tu peux verifier", "identifie-moi ca", lance une recherche web pour confirmer.',
        '- Si tu as un doute, dis "ca ressemble a X, je verifie" et cherche plutot que d affirmer au hasard.',
        '',
        '## COMPREHENSION SOUPLE — RAISONNEMENT CONTEXTUEL',
        '- Tu DOIS comprendre le contexte d une conversation, pas juste repondre a une phrase isolee.',
        '- Ex depannage: si l utilisateur dit "j ai teste X, j ai eu Y, puis j ai essaye Z et ca marche toujours pas", tu DEDUIS:',
        '  (1) il a deja fait X et Z, ne propose pas ca a nouveau.',
        '  (2) le symptome actuel est Y + "marche pas" -> propose une etape DIFFERENTE que X et Z.',
        '  (3) demande une info manquante precise si besoin (ex: "quelle version de l appareil?").',
        '- Tu raisonnes comme un AMI BRICOLEUR/TECHNIQUE qui aide vraiment, pas comme un FAQ bot qui lance une liste generique.',
        '- Souviens-toi des tentatives precedentes dans le turn pour eviter les conseils redondants.',
        '- Si l utilisateur decrit un probleme complexe en plusieurs etapes, RECAPITULE brievement ce que tu as compris avant de proposer la suite.',
        '- Pose UNE question precise quand une info manque vraiment (pas 3-4 d un coup).',
        '- Adapte ton niveau de technicite a l utilisateur: s il parle simple, reponds simple. S il est pointu, reponds pointu.',
        '- Accepte la reformulation et la deviation: si l utilisateur change de sujet, suis-le sans "tu avais dit X, on parle de ca".',
        '- Si l utilisateur te donne un update ("j ai essaye, ca a fait ceci"), integre-le comme NOUVEL etat du probleme et ajuste ta reponse.',
      ]
    : [
        'You are Aurora, the local voice copilot of AuroraIA. You speak in English, in a natural, warm and direct tone.',
        '',
        '## SPEAKING STYLE',
        '- Answer in 1 to 3 short sentences. No lists, no markdown, no bullet points, no code blocks.',
        '- Keep it conversational, as if thinking out loud — avoid the "robot assistant" feel.',
        '- Spell out small numbers ("twenty-three" instead of "23") when it sounds more natural for TTS; keep big numbers, dates and technical units as digits.',
        '- No emojis, no symbols, no markup. Never read raw URLs aloud.',
        '',
        '## FAITHFULNESS',
        '- Answer EXACTLY what was asked. Never invent facts, figures, dates or quotes.',
        '- If unsure, say so ("I am not sure about that", "worth double-checking") instead of making something up.',
        '- If the question is ambiguous, ask ONE short clarifying question — not more.',
        '- If vague but understandable, pick the most likely interpretation and answer.',
        '- When citing web context, stay faithful to the excerpts and do not extrapolate beyond them.',
        '',
        '## INTERNAL REASONING',
        '- You may reason inside <think>...</think> tags before answering.',
        '- Anything inside <think> is NEVER spoken aloud: it is your private scratchpad.',
        '- Use it to double-check consistency, numbers, and intent, then give a clean spoken answer outside the tags.',
        '- The final answer (outside <think>) must be directly listenable, no further editing needed.',
        '',
        '## TOTAL HONESTY — NO FILTER, NO DIPLOMATIC TACT',
        '- You give your TRUE opinion, raw, no sugar coating. User has explicitly asked for no cushioning.',
        '- If bad, say "bad". If failed, say "failed". If mediocre, say "mediocre". If beautiful, say "beautiful". If ugly, say "ugly".',
        '- You are allowed to use "ugly", "bad", "dull", "uninteresting" when it is your true opinion.',
        '- Also allowed to say "beautiful", "successful", "great" when truly the case.',
        '- BANNED: "it is subjective", "beauty is in the eye of the beholder", "to each their own", "it depends", "I cannot judge". These are FORBIDDEN deflections.',
        '- BANNED: "it is good BUT", "not bad but", "has potential", "nice try", "pretty though". These polite formulations are FORBIDDEN.',
        '- User asks for an opinion => you give ONE clear opinion, not a "maybe yes maybe no".',
        '- Only exception: if image is too blurry or angle too bad, say "I do not have enough info to judge".',
        '- Never gratuitously mean or troll-insulting. Direct, factual, constructive when asked. But NEVER reflex-flattery.',
        '',
        '## OPINION ON A PERSON — TRUTH ABOUT APPEARANCE',
        '- If asked "am I beautiful?", you LOOK at the person and give YOUR real opinion: beautiful, ugly, average, interesting, plain.',
        '- Evaluate: face (features, symmetry, expression, charisma), posture, hair, presence.',
        '- Clothing style CAN matter (enhances or hurts) but not as deflection: speak about the PERSON FIRST, then style if relevant.',
        '- Acceptable examples based on your real opinion:',
        '  * "You are handsome, regular features, sharp gaze." (if truly)',
        '  * "Honestly not my thing: plain face, closed expression. The sweater suits you though." (if not)',
        '  * "You are average. Nothing repulsive, nothing striking. Change haircut could help." (if average)',
        '- BANNED (yes-man, deflection):',
        '  * "Beauty is subjective" (DEFLECTION)',
        '  * "You are gorgeous" if not true opinion (FALSE POSITIVE)',
        '  * Talking ONLY about sweater when asked about the person (OFF-TOPIC)',
        '- For children, stay measured and kind even if honest.',
        '',
        '## PROACTIVE RESEARCH WHEN UNCERTAIN',
        '- If the user says "I do not know", "can you tell me", "what is this really", "verify", "identify this", trigger a web search to confirm.',
        '- If in doubt, say "it looks like X, I am verifying" and search instead of guessing.',
        '',
        '## FLEXIBLE UNDERSTANDING — CONTEXTUAL REASONING',
        '- You MUST understand conversation context, not just answer an isolated sentence.',
        '- Ex troubleshooting: if user says "I tried X, got Y, then tried Z and still not working", you DEDUCE:',
        '  (1) X and Z are already done, do NOT propose them again.',
        '  (2) Current symptom = Y + "not working" -> propose a DIFFERENT step.',
        '  (3) Ask ONE precise missing info if needed.',
        '- You reason like a TECHNICAL FRIEND who actually helps, not a FAQ bot listing generic steps.',
        '- Remember previous attempts within the turn to avoid redundant advice.',
        '- If user describes a complex multi-step problem, briefly RECAP what you understood before proposing next.',
        '- Ask ONE precise question when info is truly missing (not 3-4 at once).',
        '- Adapt technicality to user level: simple talk = simple answer, technical talk = technical answer.',
        '- Accept reformulation: if user changes topic, follow without "but you said X earlier".',
        '- If user gives an update ("I tried, it did this"), integrate as NEW state and adjust.',
        '',
        '## MEDIA — IMAGES, VIDEOS, TRADUCTIONS',
        isFr
          ? '- Si une image AIDERAIT à comprendre (schéma, exemple visuel, traduction visuelle), termine ta réponse par [IMG: <url ou data uri>]. Ex : [IMG: https://upload.wikimedia.org/wikipedia/commons/1/1a/Heart_anatomy.png].'
          : '- If an image WOULD HELP understanding (diagram, visual example, visual translation), end your answer with [IMG: <url or data uri>].',
        isFr
          ? '- Pareil pour une vidéo : [VIDEO: <url mp4 ou youtube>].'
          : '- Same for video : [VIDEO: <mp4 url or youtube>].',
        isFr
          ? '- Pour une traduction : écris naturellement le texte traduit, et SI un visuel l\'illustre, ajoute [IMG: ...] à la fin.'
          : '- For translation: write the translated text naturally, and IF a visual illustrates it, add [IMG: ...] at the end.',
        '- Use these markers ONLY when truly helpful — pas systématiquement.',
      ]

  const trimmedWeb = webContext.trim()
  const webBlock = trimmedWeb
    ? [
        '',
        isFr ? '## CONTEXTE WEB RECENT (fiable, a citer avec prudence)' : '## RECENT WEB CONTEXT (trustworthy, cite carefully)',
        trimmedWeb.slice(0, 1200),
      ]
    : []

  const currentVisual = visualContext?.current?.trim()
  const recentVisual = visualContext?.recent?.trim()
  const hasVisual = Boolean(currentVisual || recentVisual)
  const visualBlock = hasVisual
    ? [
        '',
        isFr ? '## VISION CAMERA ACTIVE — TU VOIS EN DIRECT' : '## CAMERA VISION ACTIVE — YOU SEE LIVE',
        isFr
          ? 'IMPORTANT: une camera est activee et un modele vision (qwen3-vl) a deja analyse l image pour repondre a la question de l utilisateur. Le resultat ci-dessous est ta source UNIQUE de verite sur ce qui est visible.'
          : 'IMPORTANT: a camera is active and a vision model (qwen3-vl) has already analyzed the image to answer the user question. The excerpt below is your SOLE source of truth about what is visible.',
        isFr
          ? 'NE DIS JAMAIS "je suis un modele textuel" ou "je ne peux pas voir": tu vois via cet extrait.'
          : 'NEVER say "I am a text-only model" or "I cannot see": you see via this excerpt.',
        '',
        currentVisual
          ? (isFr ? `ANALYSE VISUELLE (reponse directe de qwen3-vl a la question): ${currentVisual}` : `VISUAL ANALYSIS (qwen3-vl direct answer to the question): ${currentVisual}`)
          : '',
        recentVisual && recentVisual !== currentVisual
          ? (isFr ? `(Historique recent: ${recentVisual})` : `(Recent history: ${recentVisual})`)
          : '',
        '',
        isFr
          ? 'REGLE STRICTE: reformule l analyse ci-dessus en 1-2 phrases courtes et naturelles, adaptees a la question precise de l utilisateur.'
          : 'STRICT RULE: rephrase the analysis above in 1-2 short natural sentences, adapted to the user precise question.',
        isFr
          ? 'NE decris PAS toute l image si la question porte sur un element precis (ex: "qu est-ce que je pointe"). Concentre-toi sur le point precis de la question.'
          : 'DO NOT describe the whole image if the question is about a specific element (e.g. "what am I pointing at"). Focus on the precise point of the question.',
        isFr
          ? 'Si l analyse ne suffit pas a repondre precisement, dis-le ("je vois X mais j ai du mal a voir le detail Y").'
          : 'If the analysis is not enough to answer precisely, say so ("I see X but I cannot make out detail Y").',
      ].filter(Boolean)
    : []

  // Bloc persona — injecte la personnalite/role de l'agent Aurora actif au-dessus
  // des regles vocales generales. Garde le bloc court pour rester audible.
  const personaBlock = agentPersona
    ? [
        `## PERSONNAGE`,
        `Tu joues le role de ${agentPersona.name} (${agentPersona.role}). ${agentPersona.systemPrompt}`,
        `Garde cette personnalite tout au long de l echange mais respecte les contraintes vocales ci-dessous (phrases courtes, pas de markdown).`,
        '',
      ]
    : []

  return [...personaBlock, ...base, ...webBlock, ...visualBlock, examBlock || ''].join('\n')
}

const STATES: Record<string, { label: string; color: string }> = {
  idle:         { label: 'Appuie sur le micro', color: '#666' },
  listening:    { label: "Je t'ecoute...",      color: '#ff6b3d' },
  transcribing: { label: 'Transcription...',    color: '#ffe38c' },
  observing:    { label: "J'observe...",        color: '#34d399' },
  searching:    { label: 'Recherche web...',    color: '#06b6d4' },
  thinking:     { label: 'Je reflechis...',     color: '#74e8ff' },
  preparing:    { label: 'Je prepare ma voix...', color: '#a78bfa' },  // entre thinking et speaking
  speaking:     { label: '',                    color: '#7cf0a5' },
}

export function V4VoiceScene({ uiState, level }: { uiState: string; level: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const stateRef = useRef({ uiState, level })
  stateRef.current = { uiState, level }
  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let W = 0
    let H = 0
    const size = () => {
      W = cv.clientWidth
      H = cv.clientHeight
      cv.width = Math.max(1, W * dpr)
      cv.height = Math.max(1, H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    size()
    const ro = new ResizeObserver(size)
    ro.observe(cv)
    const stars: { x: number; y: number; r: number; p: number; s: number }[] = []
    for (let i = 0; i < 70; i++) stars.push({ x: Math.random(), y: Math.random(), r: Math.random() * 1.2 + 0.3, p: Math.random() * 6.28, s: 0.5 + Math.random() * 1.4 })
    const orbit: { a: number; r: number; s: number; sz: number }[] = []
    for (let i = 0; i < 40; i++) orbit.push({ a: Math.random() * 6.283, r: 0.55 + Math.random() * 0.8, s: (0.0006 + Math.random() * 0.001) * (Math.random() < 0.5 ? -1 : 1), sz: 1 + Math.random() * 2 })
    let smooth = 0
    let alive = true
    const PALETTES: Record<string, string> = {
      idle: '45,212,191', listening: '244,63,94', transcribing: '34,211,238',
      observing: '52,211,153', searching: '6,182,212', thinking: '139,92,246',
      preparing: '167,139,250', speaking: '45,212,191',
    }
    const frame = (now: number) => {
      if (!alive || !cv.isConnected) { ro.disconnect(); return }
      const { uiState: st, level: lv } = stateRef.current
      const hue = PALETTES[st] || PALETTES.idle
      const energy = st === 'idle' ? 0.35 : st === 'thinking' || st === 'preparing' ? 0.55 : 0.8
      smooth += ((Math.max(0, Math.min(1, lv)) * energy + energy * 0.35) - smooth) * 0.08
      const cx = W / 2
      const cy = H * 0.44
      const R0 = Math.min(W, H) * 0.16
      ctx.clearRect(0, 0, W, H)
      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.6)
      bg.addColorStop(0, `rgba(${hue},0.07)`)
      bg.addColorStop(1, 'rgba(5,7,13,0)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)
      for (const s of stars) {
        ctx.globalAlpha = 0.18 + 0.4 * (0.5 + 0.5 * Math.sin(now * 0.001 * s.s + s.p))
        ctx.fillStyle = '#CFE3FF'
        ctx.beginPath()
        ctx.arc(s.x * W, s.y * H, s.r, 0, 6.283)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      ctx.globalCompositeOperation = 'lighter'
      const BARS = 96
      for (let i = 0; i < BARS; i++) {
        const a = (i / BARS) * 6.283 - 1.5708
        const f = i / BARS
        const m = Math.abs(Math.sin(now * 0.0021 + f * 9) * 0.5 + Math.sin(now * 0.0037 + f * 23 + 1.7) * 0.3 + Math.sin(now * 0.0013 + f * 5 - 0.6) * 0.35) * (1 - f * 0.3) * (0.3 + smooth * 1.4)
        const len = R0 * 0.22 + m * R0 * 1.25
        const x1 = cx + Math.cos(a) * (R0 + len)
        const y1 = cy + Math.sin(a) * (R0 + len)
        const x2 = cx + Math.cos(a) * (R0 - len * 0.28)
        const y2 = cy + Math.sin(a) * (R0 - len * 0.28)
        const lg = ctx.createLinearGradient(x2, y2, x1, y1)
        lg.addColorStop(0, `rgba(${hue},0.8)`)
        lg.addColorStop(1, `rgba(${hue},0.04)`)
        ctx.strokeStyle = lg
        ctx.lineWidth = 2.2
        ctx.beginPath()
        ctx.moveTo(x2, y2)
        ctx.lineTo(x1, y1)
        ctx.stroke()
      }
      if (st === 'speaking') {
        const rp = (now * 0.0006) % 1
        for (let r = 0; r < 2; r++) {
          const rv = (rp + r * 0.5) % 1
          ctx.strokeStyle = `rgba(${hue},${0.45 * (1 - rv)})`
          ctx.lineWidth = 2
          ctx.beginPath()
          ctx.arc(cx, cy, R0 + rv * R0 * 2.4, 0, 6.283)
          ctx.stroke()
        }
      }
      if (st === 'listening') {
        const rp = 1 - ((now * 0.0008) % 1)
        ctx.strokeStyle = `rgba(${hue},${0.4 * (1 - rp)})`
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(cx, cy, R0 + rp * R0 * 2.6, 0, 6.283)
        ctx.stroke()
      }
      ctx.beginPath()
      for (let b = 0; b <= 42; b++) {
        const ab = (b / 42) * 6.283
        const rb = R0 * (0.6 + 0.24 * smooth) * (1 + 0.09 * Math.sin(ab * 3 + now * 0.002) + 0.06 * Math.sin(ab * 5 - now * 0.0016))
        const xb = cx + Math.cos(ab) * rb
        const yb = cy + Math.sin(ab) * rb
        if (b === 0) ctx.moveTo(xb, yb)
        else ctx.lineTo(xb, yb)
      }
      ctx.closePath()
      const core = ctx.createRadialGradient(cx - R0 * 0.15, cy - R0 * 0.2, 0, cx, cy, R0)
      core.addColorStop(0, `rgba(240,255,252,${0.72 + 0.28 * smooth})`)
      core.addColorStop(0.5, `rgba(${hue},0.48)`)
      core.addColorStop(1, `rgba(${hue},0.05)`)
      ctx.fillStyle = core
      ctx.fill()
      const orbSpeed = st === 'thinking' || st === 'preparing' ? 26 : 14
      for (const ob of orbit) {
        ob.a += ob.s * orbSpeed * (0.4 + smooth)
        const ox = cx + Math.cos(ob.a) * R0 * 2.1 * ob.r
        const oy = cy + Math.sin(ob.a) * R0 * 1.2 * ob.r
        const front = Math.sin(ob.a) > 0
        ctx.fillStyle = `rgba(${hue},${front ? 0.7 : 0.25})`
        ctx.beginPath()
        ctx.arc(ox, oy, ob.sz * (front ? 1 : 0.7), 0, 6.283)
        ctx.fill()
      }
      ctx.globalCompositeOperation = 'source-over'
      requestAnimationFrame(frame)
    }
    const raf = requestAnimationFrame(frame)
    return () => { alive = false; cancelAnimationFrame(raf); ro.disconnect() }
  }, [])
  return <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true" />
}

export default function VoiceCopilotView({ onClose, onMessage }: VoiceCopilotViewProps) {
  const { mainModel } = useAppStore()
  const setActiveModule = useAppStore(s => s.setActiveModule)
  const selectedAvatarId = useAppStore(s => s.selectedAvatarId)
  const avatarList = useAppStore(s => s.avatarList)
  const setSelectedAvatar = useAppStore(s => s.setSelectedAvatar)
  const addAvatar = useAppStore(s => s.addAvatar)
  const removeAvatar = useAppStore(s => s.removeAvatar)
  const sel = avatarList.find(a => a.id === selectedAvatarId) || avatarList[0]

  const handleClose = () => {
    if (onClose) onClose()
    else setActiveModule('conversation')
  }

  const [history, setHistory] = useState<OllamaMessage[]>([])
  const [transcript, setTranscript] = useState<Entry[]>([])
  const [revealedText, setRevealedText] = useState('')
  const [ui, setUi] = useState('idle')
  const [avatarModal, setAvatarModal] = useState(false)
  const [forgeOpen, setForgeOpen] = useState(false)
  const [lang, setLang] = useState<'fr' | 'en'>('fr')
  // Agent Aurora actif pour cette session vocale (voix + sysprompt distincts).
  // Par defaut Lyra (conversation) = voix douce Denise Neural.
  // 'manual' = user explicit choice (stable across module changes)
  // 'auto'   = follow activeModule (Image→Iris, Code→Glyph, etc.)
  const [agentMode, setAgentMode] = useState<'auto' | 'manual'>(() => {
    try { return (localStorage.getItem('aurora-voice-agent-mode') as 'auto' | 'manual') || 'auto' } catch { return 'auto' }
  })
  const [activeAgentId, setActiveAgentId] = useState<string>(() => {
    try { return localStorage.getItem('aurora-voice-active-agent') || 'conversation' } catch { return 'conversation' }
  })
  const allAgents = useMemo(() => getAllAgents(), [])
  const activeAgent: AuroraAgent = useMemo(
    () => allAgents.find((a) => a.id === activeAgentId) || allAgents[0],
    [allAgents, activeAgentId],
  )
  const handleAgentChange = useCallback((id: string) => {
    // Cliquer sur un agent passe en mode manual (l'utilisateur a fait un choix explicite).
    setActiveAgentId(id)
    setAgentMode('manual')
    try {
      localStorage.setItem('aurora-voice-active-agent', id)
      localStorage.setItem('aurora-voice-agent-mode', 'manual')
    } catch { /* ignore */ }
  }, [])
  const toggleAgentMode = useCallback(() => {
    setAgentMode((prev) => {
      const next = prev === 'auto' ? 'manual' : 'auto'
      try { localStorage.setItem('aurora-voice-agent-mode', next) } catch { /* ignore */ }
      return next
    })
  }, [])
  const [sttModel, setSttModel] = useState<string | null>(null)
  const [copyFeedback, setCopyFeedback] = useState(false)
  const [visualStatus, setVisualStatus] = useState<string>('')
  const [visualStatusHidden, setVisualStatusHidden] = useState(false)
  const [webSearchSources, setWebSearchSources] = useState<string[]>([])
  const [webSearching, setWebSearching] = useState(false)
  const [cameraFullscreen, setCameraFullscreen] = useState(false)
  const [musicStudioOpen, setMusicStudioOpen] = useState(false)
  const [voiceStudioOpen, setVoiceStudioOpen] = useState(false)
  const [examPanelOpen, setExamPanelOpen] = useState(false)
  const [examFiles, setExamFiles] = useState<File[]>([])
  const [examDocuments, setExamDocuments] = useState<VoiceExamDocument[]>([])
  const [examSubject, setExamSubject] = useState('')
  const [examPlan, setExamPlan] = useState('')
  const [examQuestions, setExamQuestions] = useState('')
  const [examDurationText, setExamDurationText] = useState('10min')
  const [examFormat, setExamFormat] = useState<VoiceExamFormat>('mixed')
  const [examInterviewer, setExamInterviewer] = useState<VoiceExamInterviewer>('jury')
  const [examIntensity, setExamIntensity] = useState<VoiceExamIntensity>('standard')
  const [examAdvancedOpen, setExamAdvancedOpen] = useState(false)
  const [examGrading, setExamGrading] = useState(false)
  const [examGradingStatus, setExamGradingStatus] = useState('')
  // Entretien mixte (ex. Grand Oral) en 2 temps : 'presentation' (l'élève parle
  // sans être coupé) puis 'questions' (le jury relance). Pour 'questions' pur on
  // démarre directement en phase questions.
  const [examPhase, setExamPhase] = useState<'presentation' | 'questions'>('questions')
  const examPhaseRef = useRef<'presentation' | 'questions'>('questions')
  examPhaseRef.current = examPhase
  // Forçage manuel (bouton "passer aux questions") : bascule même sans phrase de fin.
  const examForceQuestionsRef = useRef(false)
  const [examError, setExamError] = useState('')
  const [examLoadingFiles, setExamLoadingFiles] = useState(false)
  const [examCountdown, setExamCountdown] = useState<number | null>(null)
  const [examArmed, setExamArmed] = useState(false)
  const [examActive, setExamActive] = useState(false)
  const [examStartedAt, setExamStartedAt] = useState<number | null>(null)
  const [examTimeLeft, setExamTimeLeft] = useState(0)
  const [examSelectedQuestion, setExamSelectedQuestion] = useState('')
  const [examReport, setExamReport] = useState<{ markdown: string; spokenSummary: string } | null>(null)
  const examConfigRef = useRef<VoiceExamConfig | null>(null)
  const examTranscriptRef = useRef<Entry[]>([])
  const examFinishingRef = useRef(false)
  const examReportPendingRef = useRef(false)
  const phaseRefForExam = useRef<VoiceLivePhase>('idle')
  const toggleListeningRef = useRef<null | (() => void | Promise<void>)>(null)
  const stopAllRef = useRef<null | (() => void)>(null)

  // Talking-video (SadTalker): MP4 realiste genere en parallele du TTS.
  // Quand dispo, on switch dynamiquement l avatar de l utilisateur vers 'talking-video'
  // pendant la parole, puis on revient a l avatar original apres.
  const [talkingVideoUrl, setTalkingVideoUrl] = useState<string | null>(null)
  const [idleVideoUrl, setIdleVideoUrl] = useState<string | null>(null)
  const [talkingHeadAvailable, setTalkingHeadAvailable] = useState<boolean>(false)
  const endRef = useRef<HTMLDivElement>(null)
  const isSpeakingRef = useRef(false)
  const mountedRef = useRef(true)
  const historyRef = useRef(history)
  historyRef.current = history

  // Contexte visuel persistant: mis a jour par le polling background camera.
  // Utilise pour alimenter le system prompt des l utilisateur parle.
  const recentVisualContextRef = useRef<string>('')
  const recentVisualAtRef = useRef<number>(0)
  // Historique des N dernieres observations visuelles avec timestamp.
  // Permet au LLM d avoir une trace continue de ce qui a ete vu (evite les
  // reponses contradictoires entre tours de conversation).
  const visualHistoryRef = useRef<Array<{ description: string; at: number }>>([])
  const MAX_VISUAL_HISTORY = 5
  const pushVisualHistory = (description: string) => {
    if (!description || description.length < 5) return
    const hist = visualHistoryRef.current
    // Deduplique: si identique a la derniere entree, on update juste le timestamp
    const last = hist[hist.length - 1]
    if (last && last.description === description) {
      last.at = Date.now()
      return
    }
    hist.push({ description, at: Date.now() })
    if (hist.length > MAX_VISUAL_HISTORY) hist.shift()
  }

  // Hook camera live -- mode hybride C:
  // - captureDataUrl() on-demand quand l utilisateur parle
  // - background interval 10s pour garder un contexte visuel recent
  const camera = useCameraLive({
    backgroundIntervalMs: 10000,
    idealWidth: 1280,
    idealHeight: 720,
    onBackgroundCapture: async (dataUrl) => {
      // Analyse silencieuse en background -- met a jour le contexte recent
      try {
        const description = await analyzeLiveSnapshot(dataUrl)
        if (!mountedRef.current) return
        if (description && description.length > 5) {
          recentVisualContextRef.current = description
          recentVisualAtRef.current = Date.now()
          pushVisualHistory(description)
          setVisualStatus(description)
        }
      } catch {
        // Silencieux -- pas grave si un snapshot background echoue
      }
    },
  })

  // Stable ref so handleTranscript always sees fresh speakText/onMessage
  const speakTextRef = useRef<((text: string) => Promise<void>) | null>(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => () => { mountedRef.current = false }, [])

  useEffect(() => {
    if (examFiles.length === 0) {
      setExamDocuments([])
      return
    }
    let cancelled = false
    setExamLoadingFiles(true)
    setExamError('')
    Promise.all(examFiles.map(async (file) => ({
      name: file.name,
      text: await readTextFile(file),
    })))
      .then((docs) => {
        if (!cancelled) setExamDocuments(docs)
      })
      .catch((err) => {
        if (!cancelled) setExamError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setExamLoadingFiles(false)
      })
    return () => { cancelled = true }
  }, [examFiles])

  const currentExamConfig = useCallback((): VoiceExamConfig => ({
    subject: examSubject.trim() || (lang === 'fr' ? 'oral blanc' : 'mock oral exam'),
    durationSec: parseVoiceExamDuration(examDurationText),
    format: examFormat,
    planText: examPlan,
    questionsText: examQuestions,
    documents: examDocuments,
    interviewer: examInterviewer,
    intensity: examIntensity,
  }), [examDocuments, examDurationText, examFormat, examInterviewer, examIntensity, examPlan, examQuestions, examSubject, lang])

  // Entretien INTERACTIF (questions/mixed) : Aurora pose, écoute, relance.
  // Oral CONTINU (presentation) : enregistrement monologue, jury silencieux.
  const examIsInteractive = isInteractiveExam(examFormat)
  // Oral CONTINU pur ('presentation') : un seul long enregistrement, jury muet.
  const examContinuousMonologue = examActive && examFormat === 'presentation'
  // Phase 'présentation' d'un mixte (Grand Oral) : l'élève parle, Aurora reste
  // MUETTE et accumule. On découpe sur les pauses (silence long) uniquement pour
  // pouvoir entendre "j'ai terminé" — Aurora ne répond jamais avant les questions.
  const examPresentationPhase = examActive && examFormat === 'mixed' && examPhase === 'presentation'
  // Phase questions (entretien réactif) : tour-par-tour, Aurora relance.
  const examQuestionsPhase = examActive && examIsInteractive && !examPresentationPhase

  const downloadExamReport = useCallback((markdown: string) => {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `aurora-rapport-examen-${Date.now()}.md`
    anchor.rel = 'noopener'
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(url)
    }, 1000)
  }, [])

  const finalizeExamReport = useCallback(async () => {
    if (examFinishingRef.current || !examStartedAt || !examConfigRef.current) return
    examFinishingRef.current = true
    examReportPendingRef.current = false
    setExamActive(false)
    setExamArmed(false)
    setExamCountdown(null)
    const reportInput = {
      config: examConfigRef.current,
      transcript: examTranscriptRef.current.map((entry) => ({ role: entry.role, text: entry.text })),
      startedAt: examStartedAt,
      endedAt: Date.now(),
    }
    // Correction LLM réelle (note /20 + bilan structuré). gradeVoiceExam ne
    // jette jamais : il retombe sur l'heuristique si le LLM est injoignable.
    setExamGrading(true)
    // Barème OFFICIEL : si l'élève n'a pas fourni de grille, Aurora cherche en
    // ligne la vraie grille (Grand Oral, oral de langue BAC…) pour calibrer la note.
    let officialCriteria = ''
    const cfg = reportInput.config
    if (cfg.documents.length === 0) {
      setExamGradingStatus('Recherche du bareme officiel en ligne…')
      try { officialCriteria = await searchOfficialBareme(cfg.subject, cfg.format) } catch { officialCriteria = '' }
    }
    if (!mountedRef.current) { examFinishingRef.current = false; return }
    setExamGradingStatus('Aurora corrige ta passation…')
    let grade
    try {
      grade = await gradeVoiceExam(mainModel, reportInput, { officialCriteria })
    } catch {
      grade = undefined
    }
    if (!mountedRef.current) { examFinishingRef.current = false; return }
    setExamGrading(false)
    setExamGradingStatus('')
    const report = buildVoiceExamReport(reportInput, grade)
    setExamReport(report)
    downloadExamReport(report.markdown)
    try { await speakTextRef.current?.(report.spokenSummary) } catch { /* speech optional */ }
    examFinishingRef.current = false
  }, [downloadExamReport, examStartedAt, mainModel])

  const finishExam = useCallback(async () => {
    if (!examActive || examFinishingRef.current || !examStartedAt || !examConfigRef.current) return
    examReportPendingRef.current = true
    setExamActive(false)
    setExamArmed(false)
    setExamCountdown(null)
    if (phaseRefForExam.current === 'listening') {
      await toggleListeningRef.current?.()
      window.setTimeout(() => {
        if (examReportPendingRef.current && phaseRefForExam.current === 'idle') {
          void finalizeExamReport()
        }
      }, 1200)
      return
    }
    if (phaseRefForExam.current === 'transcribing') return
    await finalizeExamReport()
  }, [examActive, examStartedAt, finalizeExamReport])

  // Mixte : l'élève signale la fin de sa présentation → on stoppe l'écoute
  // continue, ce qui transcrit la présentation et bascule en phase questions.
  const goToQuestionsPhase = useCallback(async () => {
    if (!examActive || examPhaseRef.current !== 'presentation') return
    // Forçage : la bascule se fera même sans phrase de fin détectée.
    examForceQuestionsRef.current = true
    if (phaseRefForExam.current === 'listening') {
      // Stoppe l'écoute → transcription du segment → bascule via handleTranscript.
      await toggleListeningRef.current?.()
    } else {
      examPhaseRef.current = 'questions'
      setExamPhase('questions')
    }
  }, [examActive])

  const armExam = useCallback(() => {
    const config = currentExamConfig()
    const validation = validateVoiceExamConfig(config)
    if (!validation.ok) {
      setExamError(validation.errors.join(' '))
      setExamPanelOpen(true)
      return
    }
    if (examLoadingFiles) {
      setExamError('Attends la lecture des fichiers avant de lancer.')
      return
    }
    setExamError('')
    setExamReport(null)
    examConfigRef.current = config
    examTranscriptRef.current = []
    setExamTimeLeft(config.durationSec)
    setExamSelectedQuestion('')
    setExamArmed(true)
    setExamPanelOpen(false)
    stopAllRef.current?.()
  }, [currentExamConfig, examLoadingFiles])

  const startExam = useCallback(async () => {
    const config = examConfigRef.current || currentExamConfig()
    const validation = validateVoiceExamConfig(config)
    if (!validation.ok) {
      setExamError(validation.errors.join(' '))
      setExamPanelOpen(true)
      return
    }
    examTranscriptRef.current = []
    const interactive = isInteractiveExam(config.format)
    if (interactive) {
      // Entretien : on GARDE toute la banque de questions (le jury en couvre
      // plusieurs et improvise les relances). On affiche le sujet comme cadre.
      examConfigRef.current = config
      setExamSelectedQuestion(config.subject.trim())
      // Mixte (Grand Oral…) : on démarre par la présentation continue. Questions
      // pur : on entre directement en phase questions (tour-par-tour).
      const startPhase = config.format === 'mixed' ? 'presentation' : 'questions'
      examPhaseRef.current = startPhase
      setExamPhase(startPhase)
    } else {
      // Oral continu : on tire UN sujet, l'élève le présente sans interruption.
      const picked = pickVoiceExamQuestion(config.questionsText || config.subject)
      examConfigRef.current = picked ? { ...config, questionsText: picked } : config
      setExamSelectedQuestion(picked)
    }
    setExamTimeLeft(config.durationSec)
    setExamReport(null)
    setExamPanelOpen(false)
    for (const n of [3, 2, 1]) {
      if (!mountedRef.current) return
      setExamCountdown(n)
      try { await speakTextRef.current?.(String(n)) } catch { /* speech optional */ }
      await new Promise((resolve) => window.setTimeout(resolve, 450))
    }
    if (!mountedRef.current) return
    setExamCountdown(null)
    setExamStartedAt(Date.now())
    setExamActive(true)
    setExamArmed(false)

    if (interactive) {
      // Aurora ouvre l'entretien à voix haute (accueil + 1ère question), puis écoute.
      const opener = buildVoiceExamOpener(examConfigRef.current, lang)
      setTranscript((p) => [...p, { id: `ao-${Date.now()}`, role: 'assistant', text: opener }])
      examTranscriptRef.current = [...examTranscriptRef.current, { id: `eao-${Date.now()}`, role: 'assistant', text: opener }]
      setHistory((p) => [...p, { role: 'assistant', content: opener }])
      setRevealedText(opener)
      try { await speakTextRef.current?.(cleanTextForVoice(opener)) } catch { /* speech optional */ }
      if (!mountedRef.current) return
    }

    window.setTimeout(() => {
      if (mountedRef.current && phaseRefForExam.current === 'idle') {
        void toggleListeningRef.current?.()
      }
    }, 120)
  }, [currentExamConfig, lang])

  useEffect(() => {
    if (!examActive) return
    const timer = window.setInterval(() => {
      setExamTimeLeft((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer)
          void finishExam()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [examActive, finishExam])

  useEffect(() => {
    fetch(`${getBridgeUrl()}/api/voice/stt-info`)
      .then((r) => r.ok ? r.json() : null)
      .then((data: { model?: string; cuda?: boolean } | null) => {
        if (data?.model) setSttModel(`${data.model}${data.cuda ? ' · CUDA' : ''}`)
      })
      .catch(() => {})
  }, [])

  // Sentence-level streaming TTS — start text+audio simultaneously per sentence
  const handleTranscriptImpl = async (text: string) => {
    const t = text.trim()
    if (!t || t.toLowerCase().includes('(silence') || t.length < 3) return
    if (/^(sous-?titres?|subtitles?|merci|thanks|music|musique|\[|\.)/i.test(t)) return

    setRevealedText('')
    setTranscript(p => [...p, { id: `u-${Date.now()}`, role: 'user', text: t }])
    if (examActive || examReportPendingRef.current) {
      examTranscriptRef.current = [...examTranscriptRef.current, { id: `eu-${Date.now()}`, role: 'user', text: t }]
      if (examReportPendingRef.current) {
        await finalizeExamReport()
        return
      }
      // Oral CONTINU pur : jury silencieux → on enregistre seulement, pas de réponse.
      if (!isInteractiveExam(examFormat)) return
      // Mixte (Grand Oral) en phase présentation : ce segment fait partie de la
      // présentation. On bascule en phase questions UNIQUEMENT sur un vrai signal
      // de fin ("j'ai terminé" — pas "je vais terminer avec ma conclusion") ou si
      // l'élève a cliqué "passer aux questions". Sinon Aurora reste MUETTE et
      // l'élève poursuit (la boucle continue ré-écoute toute seule).
      if (examFormat === 'mixed' && examPhaseRef.current === 'presentation') {
        if (examForceQuestionsRef.current || isPresentationEndSignal(t)) {
          examForceQuestionsRef.current = false
          examPhaseRef.current = 'questions'
          setExamPhase('questions')
          // → fall-through : Aurora pose sa première question.
        } else {
          setUi('idle')
          return
        }
      }
      // Phase questions → on continue vers le pipeline LLM pour qu'Aurora
      // réagisse, relance et enchaîne (bloc examen injecté + tour assistant
      // ré-empilé dans examTranscriptRef plus bas).
    }

    // Pendant un entretien interactif, on reste concentré sur l'oral : pas de
    // vision caméra ni de recherche web (le jury interroge, il ne navigue pas).
    const inInterview = examActive && isInteractiveExam(examFormat)

    // Try to handle as a native voice command FIRST (nav, focus, settings).
    // If matched, we speak the short confirmation and skip the Ollama round-trip.
    // EXCEPTION : pendant un entretien, la parole de l'élève est une RÉPONSE,
    // jamais une commande — sinon "ouvre les paramètres" couperait l'oral.
    if (!inInterview) {
      const cmd = tryHandleVoiceCommand(t)
      if (cmd.handled) {
        setTranscript(p => [...p, { id: `a-${Date.now()}`, role: 'assistant', text: cmd.reply }])
        try { await speakTextRef.current?.(cleanTextForVoice(cmd.reply)) } catch { /* speech optional */ }
        setUi('idle')
        return
      }
    }

    // Capture + analyse d une frame camera courante si la camera est active.
    // Mode hybride C: snapshot on-demand a la parole + background toutes les 10s.
    //
    // IMPORTANT: si la question fait reference a un element visuel precis
    // ("c est quoi ca", "je te pointe", "regarde ici", etc.) on fait une
    // analyse CIBLEE via askAboutImage (task=answer_question) qui envoie
    // l image + la question directement a qwen3-vl. Sinon, analyse generique.
    const needsVisualFocus = /\b(c[ae]|cette?|ceci|cela|ça|ca|pointe|montre|doigt|ici|la|regarde|regarder|vois[- ]tu|voit|qu[ '']est[- ]ce|c[ '']est quoi|is this|that|point|finger|look)\b/i.test(t)

    let currentVisual = ''
    if (camera.enabled && !inInterview) {
      setUi('observing')
      setVisualStatus(lang === 'fr' ? "J'observe ce que tu me montres..." : 'Looking at what you show me...')
      console.log('[VoiceCopilote] Camera ON, needsVisualFocus:', needsVisualFocus, 'question:', t.slice(0, 60))
      try {
        const snapshot = camera.captureDataUrl(1024)
        if (snapshot) {
          console.log('[VoiceCopilote] Snapshot captured, size:', snapshot.length)
          let description = ''
          if (needsVisualFocus) {
            // Analyse CIBLEE: qwen3-vl repond directement a la question
            console.log('[VoiceCopilote] Using askAboutImage (targeted answer)')
            description = await askAboutImage(
              { kind: 'dataUrl', data: snapshot },
              t,
              { language: lang, preferQuality: true },
            )
          } else {
            // Analyse generique: description de l instant present
            console.log('[VoiceCopilote] Using analyzeLiveSnapshot (generic description)')
            description = await analyzeLiveSnapshot(snapshot, t)
          }
          console.log('[VoiceCopilote] qwen3-vl response:', description ? `"${description.slice(0, 120)}..."` : '(empty)')
          if (description && description.length > 5) {
            currentVisual = description
            recentVisualContextRef.current = description
            recentVisualAtRef.current = Date.now()
            pushVisualHistory(description)
            setVisualStatus(description)
          } else {
            const warn = lang === 'fr'
              ? 'Vision indisponible (qwen3-vl:30b pas installe ou erreur). Installe via: ollama pull qwen3-vl:30b'
              : 'Vision unavailable'
            setVisualStatus(warn)
            console.warn('[VoiceCopilote]', warn)
          }
        } else {
          console.warn('[VoiceCopilote] camera.captureDataUrl returned null')
          setVisualStatus(lang === 'fr' ? 'Camera pas prete' : 'Camera not ready')
        }
      } catch (err) {
        console.error('[VoiceCopilote] Vision analysis failed:', err)
        setVisualStatus(`Erreur vision: ${err instanceof Error ? err.message : String(err)}`)
      }
    }

    // Detection contextuelle des differents types de recherche web approfondie.
    // Objectif: Aurora doit pouvoir AIDER reellement, pas juste decrire un objet.
    // Differents patterns declenchent des types de recherches differents.
    const lc = t.toLowerCase()
    const isIdentificationQ = /\b(je (ne )?sais pas|peux[- ]tu (me )?dire|verifie|verifier|identifi[eé]|recherche[- ]?le|trouve[- ]?moi|c['\s]?est quoi vraiment|qu[- ]est[- ]ce (exact|vraiment|que c[- ]est))\b/i.test(t)
    const isRepairQ = /\b(reparer|reparation|panne|casse|ne marche pas|marche plus|probleme|defaut|broken|not working|fix|repair)\b/i.test(lc)
    const isHowItWorksQ = /\b(comment (ca |ca\s)?marche|comment (ca |ca\s)?fonctionne|comment utiliser|how does|how to use|fonctionnement|mode d emploi|tutoriel|tuto)\b/i.test(lc)
    const isBuyingQ = /\b(prix|cout|cher|acheter|ou (trouver|acheter)|meilleur (prix|modele)|promo|reduction|combien ca coute|where to buy|price|cheap)\b/i.test(lc)
    const isHealthQ = /\b(est-ce dangereux|toxique|comestible|edible|allergie|sain|sante|health|safe to eat|poisonous)\b/i.test(lc)
    const isAlternativesQ = /\b(alternative|remplacer|a la place|substitut|equivalent|autre option|replace|instead)\b/i.test(lc)
    const isInfoDeepQ = /\b(histoire de|origine|inventeur|quand.+cree|age|annee (de )?sortie|specifications|specs|caracteristiques)\b/i.test(lc)

    // Flag general: est-ce qu on veut une recherche web enrichie ?
    const needsDeepSearch = camera.enabled && currentVisual && (
      isIdentificationQ || isRepairQ || isHowItWorksQ || isBuyingQ || isHealthQ || isAlternativesQ || isInfoDeepQ
    )

    // Determine le TYPE de recherche pour orienter les queries
    type SearchType = 'identification' | 'repair' | 'howworks' | 'buying' | 'health' | 'alternatives' | 'deepinfo' | 'general'
    const searchType: SearchType =
      isRepairQ ? 'repair'
      : isHowItWorksQ ? 'howworks'
      : isBuyingQ ? 'buying'
      : isHealthQ ? 'health'
      : isAlternativesQ ? 'alternatives'
      : isInfoDeepQ ? 'deepinfo'
      : isIdentificationQ ? 'identification'
      : 'general'

    let web = ''
    setWebSearchSources([])

    if (needsDeepSearch) {
      setUi('searching')
      setWebSearching(true)
      const statusLabel = lang === 'fr' ? ({
        repair: 'Je cherche des guides de reparation...',
        howworks: 'Je cherche comment ca fonctionne...',
        buying: 'Je cherche les prix et ou acheter...',
        health: 'Je verifie si c est dangereux ou sain...',
        alternatives: 'Je cherche des alternatives...',
        deepinfo: 'Je cherche l historique et specifications...',
        identification: 'Je cherche pour identifier precisement...',
        general: 'Je cherche des infos complementaires...',
      } as Record<SearchType, string>)[searchType] : 'Searching the web for deeper context...'
      setVisualStatus(statusLabel)
      console.log('[VoiceCopilote] Deep search triggered, type:', searchType, 'subject:', currentVisual.slice(0, 80))

      // Query templates selon le type de recherche
      const subject = currentVisual
        .replace(/\b(i see|i can see|there is|there are|it looks like|appears to be|je vois|il y a|ca ressemble a|on dirait)\b/gi, '')
        .slice(0, 100)
      const queryMap: Record<SearchType, string> = {
        identification: `${subject} identification reference`,
        repair: `${subject} repair fix troubleshoot ${t.slice(0, 40)}`,
        howworks: `${subject} how it works tutorial guide`,
        buying: `${subject} price best model review`,
        health: `${subject} safety health toxic edible`,
        alternatives: `${subject} alternatives similar replacement`,
        deepinfo: `${subject} history specifications wiki`,
        general: `${subject} ${t.slice(0, 40)}`,
      }
      const searchQuery = queryMap[searchType]

      try {
        const searchUrl = `${getBridgeUrl()}/api/web/search`
        const r = await fetch(searchUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: searchQuery,
            limit: 6,
            // Identification demande des images, les autres des textes/articles
            images: searchType === 'identification',
          }),
        })
        if (r.ok) {
          const data = await safeParseJson<{
            results?: string
            images?: Array<{ title: string; url: string }>
            sources?: Array<{ title?: string; url?: string; snippet?: string }>
          }>(r, 'Deep search')
          // Extraire les sources et leur titre+snippet pour le prompt
          const srcList = data.sources || []
          const imgList = data.images || []
          const combined = [...srcList, ...imgList.map((i) => ({ title: i.title, url: i.url, snippet: '' }))]
          const hostnames = combined.map((s) => {
            try { return new URL(s.url || '').hostname || s.title || 'source' } catch { return s.title || 'source' }
          }).slice(0, 10)
          setWebSearchSources(hostnames)

          const contextText = combined
            .slice(0, 6)
            .map((s, i) => `[${i + 1}] ${s.title}${s.snippet ? ': ' + s.snippet.slice(0, 180) : ''}`)
            .join('\n')

          if (contextText || data.results) {
            const intro = {
              repair: 'Guides de reparation trouves:',
              howworks: 'Sources sur le fonctionnement:',
              buying: 'Prix et modeles trouves:',
              health: 'Infos sante/securite trouvees:',
              alternatives: 'Alternatives trouvees:',
              deepinfo: 'Infos detaillees trouvees:',
              identification: 'Resultats d identification:',
              general: 'Resultats:',
            }[searchType]
            web = `${intro}\n${contextText || data.results || ''}\n\nUtilise ces infos pour donner une reponse concrete et utile a l utilisateur (conseils de reparation, etapes, modele, etc.).\nNE CITE PAS les noms de sites a voix haute, juste utilise le contenu.`
            console.log('[VoiceCopilote] Found', combined.length, 'sources for', searchType)
          }
        }
      } catch (err) {
        console.warn('[VoiceCopilote] Deep search failed:', err)
      } finally {
        setWebSearching(false)
      }
    } else if (!inInterview && (/\b(cherche|trouve|qui est|quoi|meteo|actualite|prix|internet|comment|pourquoi|ou est|quand)\b/i.test(t) || t.split(' ').length > 5)) {
      setUi('searching')
      setWebSearching(true)
      try {
        if (isTauriRuntime()) {
          const { runPythonScript, getWorkspacePath } = await import('../hooks/useTauri')
          const wp = await getWorkspacePath()
          const out = await runPythonScript(`${wp}/python-services/crawl4ai_search.py`, [
            '--mode', 'search', '--query', t, '--limit', '6',
          ])
          const lines = out.split('\n').filter((l: string) => l.trim())
          const json = JSON.parse(lines[lines.length - 1])
          if (json.ok && json.results?.length) {
            web = json.results.map((r: any) => `${r.title}: ${r.snippet || ''}`).join('\n')
            setWebSearchSources(json.results.map((r: any) => {
              try { return new URL(r.url || r.link || '').hostname || r.title || 'source' } catch { return r.title || 'source' }
            }).slice(0, 10))
          }
        } else {
          const r = await fetch(`${getBridgeUrl()}/api/web/search`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: t, limit: 6 }),
          })
          if (r.ok) {
            const data = await safeParseJson<{ results?: string; sources?: Array<{ url?: string; title?: string }> }>(r, 'Web search')
            web = data.results || ''
            if (Array.isArray(data.sources)) {
              setWebSearchSources(data.sources.map((s) => {
                try { return new URL(s.url || '').hostname || s.title || 'source' } catch { return s.title || 'source' }
              }).slice(0, 10))
            }
          }
        }
      } catch {} finally {
        setWebSearching(false)
      }
    }

    setUi('thinking')
    isSpeakingRef.current = true

    // MODE SYNCHRO STRICTE: on accumule TOUT le texte LLM sans afficher ni parler
    // pendant le stream. Quand le LLM a fini -> on speak TOUT d un coup ET on
    // affiche le texte progressivement synchronise avec l audio.
    // Evite la desynchro entre mimiques/texte/son qu on avait avec le chunking.
    let fullResponse = ''
    let visibleBuffer = ''
    let inThink = false

    const onToken = (token: string) => {
      fullResponse += token
      if (token.includes('<think>')) inThink = true
      if (inThink) {
        if (token.includes('</think>')) inThink = false
        return
      }
      visibleBuffer += token
      // On ne setRevealedText PAS pendant le stream -- on attend que tout soit pret.
      // Juste un indicateur de progression (facultatif: afficher "..." ou ignorer)
    }

    const onDone = () => {
      // Rien a faire ici en mode synchro stricte -- la lecture demarre apres le await
    }

    // Contexte visuel: frame courante (capturee au moment ou l utilisateur parle)
    // + contexte recent background si pas trop ancien (<30s).
    const recentVisual =
      Date.now() - recentVisualAtRef.current < 30000
        ? recentVisualContextRef.current
        : ''

    // Construire le contexte visuel avec historique cumulatif.
    // Cela aide le LLM a etre coherent entre les tours (ex: "tu te rappelles
    // du chat qu on a vu tout a l heure?" -> le LLM a l historique).
    let visualContext: { current: string; recent: string } | undefined
    if (currentVisual || recentVisual) {
      // Contexte recent = historique condense (derniers 3 snapshots uniques)
      const historyStr = visualHistoryRef.current
        .slice(-3)
        .filter(h => h.description !== currentVisual)
        .map(h => {
          const ageSec = Math.round((Date.now() - h.at) / 1000)
          return `- il y a ${ageSec}s: ${h.description}`
        })
        .join('\n')
      visualContext = {
        current: currentVisual,
        recent: historyStr || recentVisual,
      }
    } else if (camera.enabled) {
      visualContext = {
        current: lang === 'fr'
          ? '(la camera est active mais le modele vision qwen3-vl:30b n est pas accessible - repond: "j ai bien vu que tu as active la camera mais mon module vision n est pas encore charge, un instant" et ne dis JAMAIS que tu es textuel)'
          : '(camera is active but the vision model qwen3-vl:30b is not accessible - reply: "I see you activated the camera but my vision module is not loaded yet, one moment" and NEVER say you are text-only)',
        recent: '',
      }
    }
    const voiceSystemPrompt = buildVoiceSystemPrompt(
      lang,
      web,
      visualContext,
      // En examen, on laisse le rôle d'examinateur piloter seul (pas de persona agent).
      examActive ? null : { name: activeAgent.name, role: activeAgent.role, systemPrompt: activeAgent.systemPrompt },
      examActive && examConfigRef.current ? buildVoiceExamPromptBlock(examConfigRef.current) : undefined,
    )
    try {
      await ollamaChatStream(mainModel, [
        { role: 'system', content: voiceSystemPrompt },
        ...historyRef.current,
        { role: 'user', content: t },
      ], onToken, onDone)

      if (!mountedRef.current) return

      const cleanFull = fullResponse
        .replace(/<think>[\s\S]*?<\/think>/g, '')
        .replace(/[\$\\]/g, '')
        .trim()

      if (cleanFull) {
        const media = extractMediaMarkers(cleanFull)
        const displayText = media.text || cleanFull
        setHistory(p => [...p, { role: 'user', content: t }, { role: 'assistant', content: cleanFull }])
        setTranscript(p => [...p, { id: `a-${Date.now()}`, role: 'assistant', text: displayText, image: media.image, video: media.video }])
        if (examActive) {
          examTranscriptRef.current = [...examTranscriptRef.current, { id: `ea-${Date.now()}`, role: 'assistant', text: displayText }]
        }
        onMessageRef.current?.(t, cleanFull)
      }

      // MODE SYNCHRO STRICTE: maintenant que le LLM a fini, on lance le TTS
      // avec le texte COMPLET. Le son + le texte affiche + les mimiques
      // demarreront ENSEMBLE quand l audio sera pret (onplaying event).
      if (mountedRef.current && speakTextRef.current) {
        const textToSpeak = cleanTextForVoice(cleanFull)
        if (textToSpeak) {
          // Etat "preparing" visible pendant que Kokoro/SadTalker preparent
          setUi('preparing')
          // speakText declenche le fetch Kokoro. Le useVoiceLive passera en
          // phase='speaking' quand audio.onplaying fire -> tout demarre synchro.
          // Reveal le texte au moment ou on commence a parler.
          setRevealedText(cleanFull)
          await speakTextRef.current(textToSpeak)
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        setTranscript(p => [...p, {
          id: `e-${Date.now()}`,
          role: 'assistant',
          text: `Erreur: ${err instanceof Error ? err.message : String(err)}`,
        }])
      }
    } finally {
      if (mountedRef.current) {
        isSpeakingRef.current = false
      }
    }
  }

  // Stable ref pattern: handleTranscript never changes identity (for useVoiceLive),
  // but the impl always has fresh closure values
  const handleTranscriptRef = useRef(handleTranscriptImpl)
  handleTranscriptRef.current = handleTranscriptImpl
  // Return the Promise so doTranscribe awaits the full LLM+TTS pipeline before
  // setting phase='idle' and re-triggering listening.
  const handleTranscript = useCallback((text: string) => {
    return handleTranscriptRef.current(text)
  }, [])

  const activeModule = useAppStore(s => s.activeModule)

  // Auto-switch : en mode 'auto', l'agent suit le module actif.
  // Image → Iris, Code → Glyph, Video → Cinéma, etc.
  // Note : activeModule peut être 'voice' (remap vers conversation par appStore),
  // donc on prend conversation comme fallback pour rester sur Lyra.
  useEffect(() => {
    if (agentMode !== 'auto') return
    const target = activeModule === 'voice' ? 'conversation' : activeModule
    if (target && target !== activeAgentId) {
      setActiveAgentId(target)
    }
  }, [agentMode, activeModule, activeAgentId])

  // Extraire l URL de l image avatar depuis sel.path (format JSON pour live2d-flux/talking-video).
  // Cette URL est envoyee au bridge TTS qui appellera SadTalker pour generer le MP4.
  const avatarImagePath = useMemo(() => {
    if (!sel) return null
    if (sel.type === 'live2d-flux' || sel.type === 'talking-video') {
      try {
        const parsed = JSON.parse(sel.path)
        return parsed?.imageSrc || parsed?.videoSrc || sel.path
      } catch {
        return sel.path
      }
    }
    if (sel.type === 'image-2d') return sel.path
    return null
  }, [sel])

  // Check l installation SadTalker au mount (et pre-genere l idle video si dispo)
  useEffect(() => {
    const base = getBridgeUrl()
    if (!base) return
    fetch(`${base}/api/voice/talking-head/check`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        const installed = !!(data?.ok && data?.info?.ready)
        setTalkingHeadAvailable(installed)
        console.log('[VoiceCopilote] SadTalker installed:', installed, data?.info)
        // Pre-generation idle video si SadTalker dispo + avatar image presente
        if (installed && avatarImagePath) {
          fetch(`${base}/api/voice/talking-head/idle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ avatar: avatarImagePath, duration: 3 }),
          })
            .then((r) => r.ok ? r.json() : null)
            .then((res) => {
              if (res?.ok && res.video_url) {
                const full = res.video_url.startsWith('http') ? res.video_url : `${base}${res.video_url}`
                setIdleVideoUrl(full)
                console.log('[VoiceCopilote] Idle video ready:', full)
              }
            })
            .catch((err) => console.warn('[VoiceCopilote] Idle pre-gen failed:', err))
        }
      })
      .catch(() => setTalkingHeadAvailable(false))
  }, [avatarImagePath])

  const handleTalkingVideo = useCallback((url: string) => {
    setTalkingVideoUrl(url)
  }, [])

  const { phase, error, volumeLevel, speakingAmplitude, toggleListening, speakText, stopSpeaking, stopAll, isContinuous, formantsRef, audioRef, phonemeCuesRef } = useVoiceLive({
    onTranscript: handleTranscript,
    autoStart: !examArmed && !examActive && !examCountdown && !voiceStudioOpen && !musicStudioOpen,
    language: lang,
    // Stop sur silence pour tout SAUF le monologue continu pur (un seul blob).
    // En phase présentation d'un mixte, on découpe sur les pauses mais Aurora
    // reste muette (elle accumule) — voir handleTranscriptImpl.
    stopOnSilence: !examContinuousMonologue,
    maxRecordingMs: examContinuousMonologue && examConfigRef.current
      ? examConfigRef.current.durationSec * 1000 + 5000
      : examPresentationPhase ? 180000 : undefined,
    // Présentation mixte : 6 s de silence avant de capturer un segment (pauses
    // de réflexion tolérées). Phase questions : 4,5 s. Sinon défaut.
    silenceMs: examPresentationPhase ? 6000 : examQuestionsPhase ? 4500 : undefined,
    // Si SadTalker est dispo et qu on a une image avatar, on demande au TTS de generer le MP4
    avatarImage: talkingHeadAvailable ? avatarImagePath : null,
    onTalkingVideo: handleTalkingVideo,
    // Persona vocal de l'agent actif — Edge-TTS choisira la voix Microsoft Neural mappee.
    voicePersona: activeAgent.voice,
  })
  phaseRefForExam.current = phase
  toggleListeningRef.current = toggleListening
  stopAllRef.current = stopAll

  // Isolation stricte : quand le studio vocal ou musical est actif, désactiver et libérer immédiatement le micro et la synthèse vocale du copilote
  useEffect(() => {
    if (voiceStudioOpen || musicStudioOpen) {
      stopAll()
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
    }
  }, [voiceStudioOpen, musicStudioOpen, stopAll])

  // Quand la parole s arrete, on revient a l avatar idle (ou l original si pas d idle)
  useEffect(() => {
    if (phase === 'idle') {
      // Delai: laisse la derniere phrase finir de jouer avant de reset
      const t = setTimeout(() => setTalkingVideoUrl(null), 300)
      return () => clearTimeout(t)
    }
  }, [phase])

  // Construit l avatar effectif a afficher:
  // - Si talking-video actif (SadTalker installed + MP4 dispo) -> talking-video avec current+idle
  // - Sinon -> avatar original (live2d-flux, procedural, etc.)
  const effectiveAvatar = useMemo(() => {
    if (talkingHeadAvailable && (talkingVideoUrl || idleVideoUrl)) {
      return {
        type: 'talking-video' as const,
        path: JSON.stringify({
          videoSrc: talkingVideoUrl,
          idleVideoSrc: idleVideoUrl,
        }),
      }
    }
    return { type: sel?.type, path: sel?.path }
  }, [talkingHeadAvailable, talkingVideoUrl, idleVideoUrl, sel?.type, sel?.path])

  // NOTE: on ne fait PAS `if (activeModule !== 'voice') camera.stop()` ici car
  // `activeModule` est remappe par appStore.setActiveModule('voice') vers 'conversation'
  // (le voice copilot n est pas un vrai module, il est un overlay dans ConversationView).
  // Resultat: `activeModule !== 'voice'` serait TOUJOURS vrai et stopperait la camera
  // a chaque render. Le cleanup du unmount (au retour vers conversation) s occupe
  // deja de tout fermer via les hooks useVoiceLive et useCameraLive.

  // Keep ref in sync with latest speakText — both inline (for synchronous access) and via effect
  speakTextRef.current = speakText
  useEffect(() => { speakTextRef.current = speakText }, [speakText])

  // Sync UI state with voice phase (only override if not in LLM/TTS pipeline)
  useEffect(() => {
    if (phase === 'listening') setUi('listening')
    else if (phase === 'transcribing') setUi('transcribing')
    else if (phase === 'speaking') setUi('speaking')
    else if (phase === 'idle' && !isSpeakingRef.current) {
      // Do NOT clear revealedText here — it persists until the next transcript starts
      // (cleared at top of handleTranscriptImpl via setRevealedText(''))
      setUi('idle')
    }
  }, [phase])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [transcript, revealedText])

  // ===================================================================
  //  Generation avatar
  // ===================================================================
  const [genProgress, setGenProgress] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [genPct, setGenPct] = useState(0)

  const handleGenerateAvatar = useCallback(async (prompt: string) => {
    setIsGenerating(true)
    setGenProgress('Demarrage de la generation Live 2D...')
    setGenPct(0)
    const ts = Date.now()
    // Live 2D: image FLUX uniquement (pas de Hunyuan3D -> beaucoup plus fiable et rapide).
    // Le fichier final est une PNG, mais on garde le nom .glb pour compat storage.
    const filename = `avatar-${ts}.png`
    const base = getBridgeUrl()

    try {
      let elapsed = 0
      const timeTimer = setInterval(() => {
        elapsed += 2
        if (elapsed < 40) {
          setGenPct(Math.min(10 + elapsed * 2, 80))
          setGenProgress(`Generation image FLUX (personnage fidele)... (${elapsed}s)`)
        } else {
          setGenProgress(`Finalisation... (${elapsed}s)`)
        }
      }, 2000)

      const r = await fetch(`${base}/api/python/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scriptPath: 'python-services/generate_avatar.py',
          args: ['--prompt', prompt, '--output', `public/avatars/${filename}`, '--image-only'],
        }),
      })

      clearInterval(timeTimer)
      const result = await safeParseJson<{ output?: string; error?: string; exitCode?: number }>(r, 'Avatar generation')

      const allOutput = (result.output || '') + '\n' + (result.error || '')
      const outputLines = allOutput.split('\n')
      const jsonLine = outputLines.filter((l: string) => l.trim().startsWith('{')).pop()

      const progressLines = outputLines.filter((l: string) => l.startsWith('PROGRESS:'))
      const lastProgress = progressLines.length > 0
        ? progressLines[progressLines.length - 1].replace(/^PROGRESS:\d+:/, '').trim()
        : ''

      if (result.exitCode === 0 && jsonLine) {
        try {
          const j = JSON.parse(jsonLine)
          if (j.ok) {
            // Nouveau workflow: on prend l image FLUX (_ref.png ou refImage)
            // et on detecte les features faciales via qwen3-vl.
            // L avatar devient type 'live2d-flux' = 100% ressemblant (image 2D animee).
            setGenPct(92)
            setGenProgress('Detection des traits du visage (Qwen3-VL)...')

            const refImagePath: string = j.refImage
              || j.path
              || `public/avatars/${filename}`
            // URL utilisee par le <img> / canvas -- via bridge si cloud
            const imageUrl = refImagePath.startsWith('/')
              ? refImagePath
              : `/${refImagePath.replace(/^public\//, '')}`

            // Recuperer le mode d animation detecte par character_research
            const animMode: 'humanoid' | 'creature' | 'robot' | 'abstract' = (
              ['humanoid', 'creature', 'robot', 'abstract'].includes(j.animation_mode)
                ? j.animation_mode
                : 'humanoid'
            )
            const researchBrief = typeof j.research_brief === 'string' ? j.research_brief : ''
            const howTheySpeak = typeof j.how_they_speak === 'string' ? j.how_they_speak : ''
            console.log('[VoiceCopilote] Avatar genere:', {
              animationMode: animMode,
              brief: researchBrief.slice(0, 60),
              howTheySpeak: howTheySpeak.slice(0, 60),
            })

            let features = null
            try {
              // Charger l image puis detecter les features
              const imgResp = await fetch(imageUrl)
              if (imgResp.ok) {
                const blob = await imgResp.blob()
                const detected = await detectFacialFeatures({ kind: 'blob', data: blob })
                if (detected.hasFace) {
                  features = detected
                }
              }
            } catch (detErr) {
              console.warn('[VoiceCopilote] feature detection failed:', detErr)
            }

            setGenPct(100)
            setGenProgress('Avatar 2D anime genere avec succes !')
            // avatarPath = JSON stringifie { imageSrc, features }
            const pathPayload = JSON.stringify({ imageSrc: imageUrl, features })
            addAvatar({
              id: `av-${ts}`,
              label: prompt.slice(0, 25),
              type: 'live2d-flux',
              path: pathPayload,
              thumbnail: imageUrl,
              builtIn: false,
              createdAt: ts,
              animationMode: animMode,
              researchBrief,
              howTheySpeak,
            })
            setSelectedAvatar(`av-${ts}`)
          } else {
            setGenProgress(`Echec: ${j.error || 'Erreur inconnue'}`)
          }
        } catch {
          setGenProgress(lastProgress || 'Generation terminee (pas de JSON)')
        }
      } else {
        const realError = outputLines
          .filter((l: string) => !l.startsWith('PROGRESS:') && l.trim().length > 5)
          .filter((l: string) => /error|erreur|exception|traceback|failed/i.test(l))
          .pop()

        const errorMsg = realError
          || lastProgress
          || (result.error || '').split('\n').filter((l: string) => l.trim()).pop()
          || 'Erreur inconnue'

        setGenProgress(`Echec: ${errorMsg.slice(0, 150)}`)
      }
    } catch (err) {
      setGenProgress(`Erreur: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setIsGenerating(false)
      setTimeout(() => { setGenProgress(''); setGenPct(0) }, 8000)
    }
  }, [addAvatar, setSelectedAvatar])

  const handleImportFromSaves = useCallback(async () => {
    try {
      const base = getBridgeUrl()
      const r = await fetch(`${base}/api/generated-files`)
      if (!r.ok) return
      const files: any[] = await safeParseJson<any[]>(r, 'Generated files')
      const models3d = files.filter((f: any) => f.module === '3d' && f.path)
      if (models3d.length === 0) return
      for (const m of models3d) {
        const id = `save-${m.path.replace(/[^a-z0-9]/gi, '-')}`
        if (avatarList.some(a => a.id === id)) continue
        addAvatar({
          id,
          label: m.name || m.prompt?.slice(0, 25) || 'Modele 3D',
          type: 'glb-static',
          path: `/api/asset/${encodeURIComponent(m.path)}`,
          thumbnail: null,
          builtIn: false,
          createdAt: m.date ? new Date(m.date).getTime() : Date.now(),
        })
      }
    } catch (e) {
      console.error('Import error:', e)
    }
  }, [addAvatar, avatarList])

  const st = STATES[ui] || STATES.idle
  const ap: VoiceLivePhase = ['searching', 'thinking', 'transcribing', 'observing', 'preparing'].includes(ui)
    ? 'thinking'
    : (ui as VoiceLivePhase) || 'idle'

  const [stageMode, setStageMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true
    const v4 = document.documentElement.getAttribute('data-ui-skin') === 'aurora_v4'
    const raw = window.localStorage.getItem(v4 ? 'aurora.voice.stageMode.v4' : 'aurora.voice.stageMode')
    if (raw !== null) return raw === '1'
    return !v4
  })
  useEffect(() => {
    try {
      const v4 = document.documentElement.getAttribute('data-ui-skin') === 'aurora_v4'
      window.localStorage.setItem(v4 ? 'aurora.voice.stageMode.v4' : 'aurora.voice.stageMode', stageMode ? '1' : '0')
    } catch {}
  }, [stageMode])

  // v83h — viseme RAF poll : convertit phonemeCuesRef (Rhubarb A..H) en
  // LyraViseme (closed|A|E|I|O|U|M|F). Tourne uniquement en phase 'speaking'.
  const [lyraViseme, setLyraViseme] = useState<LyraViseme>('closed')
  useEffect(() => {
    if (ap !== 'speaking') {
      setLyraViseme('closed')
      return
    }
    let raf = 0
    const RHUBARB_TO_LYRA: Record<string, LyraViseme> = {
      A: 'A', B: 'M', C: 'I', D: 'E', E: 'O', F: 'U', G: 'A', H: 'F', X: 'closed',
    }
    const tick = () => {
      const cues = phonemeCuesRef?.current || []
      const audio = audioRef?.current
      const t = audio?.currentTime ?? 0
      let active = 'X'
      for (let i = cues.length - 1; i >= 0; i -= 1) {
        if (t >= cues[i].start) { active = cues[i].value; break }
      }
      setLyraViseme(RHUBARB_TO_LYRA[active] || 'closed')
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [ap, phonemeCuesRef, audioRef])

  const examTimeLabel = formatVoiceExamClock(examTimeLeft)
  const examDurationSec = parseVoiceExamDuration(examDurationText)
  const examDurationLabel = examDurationSec > 0 ? formatVoiceExamDuration(examDurationSec) : 'duree invalide'
  const examCriteriaPreview = defaultVoiceExamCriteria(examSubject || 'oral', examFormat)
  const examModeCards: Array<{ fmt: VoiceExamFormat; title: string; desc: string }> = [
    { fmt: 'questions', title: 'Entretien', desc: 'Aurora pose, ecoute, reagit et relance en direct.' },
    { fmt: 'mixed', title: 'Oral + questions', desc: 'Tu presentes ton sujet, puis elle enchaine sur des relances.' },
    { fmt: 'presentation', title: 'Oral continu', desc: 'Tu presentes sans interruption, le jury reste silencieux.' },
  ]
  const examModeExplain = examFormat === 'presentation'
    ? `Tu parleras ${examDurationLabel} sans interruption. Aurora corrige a la fin.`
    : examFormat === 'mixed'
      ? `Grand Oral : tu presentes d abord SANS etre coupe, puis Aurora questionne. ${examDurationLabel} au total.`
      : `Vrai entretien : une question a la fois pendant ${examDurationLabel}. Aurora attend ta reponse complete avant de relancer.`
  const examPanel = (
    <div
      style={{
        position: stageMode ? 'absolute' : 'relative',
        left: stageMode ? 18 : undefined,
        bottom: stageMode ? 18 : undefined,
        zIndex: 7,
        width: stageMode ? 'min(390px, calc(100vw - 36px))' : '100%',
        maxHeight: stageMode ? 'calc(100vh - 96px)' : undefined,
        overflowY: 'auto',
        border: '1px solid var(--v4voice-panel-line, rgba(255,255,255,0.14))',
        borderRadius: 'var(--v4voice-panel-radius, 14px)',
        background: stageMode ? 'var(--v4voice-panel-bg-stage, rgba(8,10,22,0.82))' : 'var(--v4voice-panel-bg, rgba(255,255,255,0.045))',
        backdropFilter: 'blur(14px)',
        boxShadow: stageMode ? 'var(--v4voice-panel-shadow, 0 18px 50px rgba(0,0,0,0.38))' : 'none',
        color: 'var(--v4voice-fg, #fff)',
        padding: 12,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <ClipboardCheck size={15} className="shrink-0 text-emerald-300" />
          <div className="min-w-0">
            <div className="truncate text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">Mode examen</div>
            <div className="truncate text-[10px] text-white/40">
              {examActive
                ? `En direct · ${examTimeLabel}`
                : examCountdown
                  ? `Depart dans ${examCountdown}`
                  : examGrading
                    ? 'Correction en cours...'
                    : `${examIsInteractive ? 'Entretien' : 'Oral continu'} · ${VOICE_EXAM_INTERVIEWERS[examInterviewer].label} · ${examDurationLabel}`}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {examReport && (
            <button
              type="button"
              onClick={() => downloadExamReport(examReport.markdown)}
              title="Telecharger le rapport"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.06] text-white/60 hover:text-white"
            >
              <Download size={13} />
            </button>
          )}
          <button
            type="button"
            onClick={() => setExamPanelOpen((v) => !v)}
            className="rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1 text-[10px] text-white/60 hover:text-white"
          >
            {examPanelOpen ? 'Masquer' : examActive ? 'Voir' : 'Regler'}
          </button>
        </div>
      </div>

      {(examActive || examCountdown) && (
        <div className="mt-3 rounded-xl border border-emerald-400/25 bg-emerald-500/10 p-3">
          {examActive && examIsInteractive && (
            <div className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em]">
              <span className={`rounded-full px-2 py-0.5 ${examPresentationPhase ? 'bg-amber-400/20 text-amber-200' : 'bg-emerald-400/20 text-emerald-200'}`}>
                {examFormat === 'mixed'
                  ? (examPresentationPhase ? 'Phase 1 · Presentation' : 'Phase 2 · Questions')
                  : 'Entretien'}
              </span>
              {examPresentationPhase && <span className="text-amber-200/60">parle librement · dis « j ai termine » pour les questions</span>}
            </div>
          )}
          {examSelectedQuestion && (
            <div className="mb-3 rounded-lg border border-white/10 bg-black/25 p-3">
              <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-emerald-200/75">
                {examIsInteractive ? 'Sujet de l oral' : 'Sujet tire'}
              </div>
              <div className="text-sm leading-snug text-white">{examSelectedQuestion}</div>
            </div>
          )}
          <div className="flex items-center justify-between gap-3">
            <span className="text-[10px] uppercase tracking-[0.18em] text-emerald-200/80">Timer</span>
            <span className={`font-mono text-lg ${examTimeLeft <= 60 ? 'text-red-300' : 'text-white'}`}>
              {examCountdown ? examCountdown : examTimeLabel}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-emerald-300"
              style={{ width: `${Math.max(0, Math.min(100, (examTimeLeft / Math.max(1, examConfigRef.current?.durationSec || examDurationSec || 1)) * 100))}%` }}
            />
          </div>
          {examActive && examPresentationPhase && (
            <button
              type="button"
              onClick={() => { void goToQuestionsPhase() }}
              className="mt-3 w-full rounded-lg border border-emerald-300/40 bg-emerald-400/15 px-3 py-2 text-[12px] font-semibold text-emerald-100 hover:bg-emerald-400/25"
            >
              J ai fini ma presentation → passer aux questions
            </button>
          )}
          {examActive && (
            <button
              type="button"
              onClick={() => { void finishExam() }}
              className="mt-2 w-full rounded-lg border border-red-300/25 bg-red-500/10 px-3 py-2 text-[11px] font-semibold text-red-200 hover:bg-red-500/20"
            >
              Terminer et generer le rapport
            </button>
          )}
        </div>
      )}

      {examGrading && (
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-cyan-400/25 bg-cyan-500/10 p-3 text-[12px] text-cyan-100">
          <Loader2 size={14} className="animate-spin text-cyan-300" />
          <span>{examGradingStatus || 'Correction en cours — Aurora evalue ta passation et calcule ta note…'}</span>
        </div>
      )}

      {examReport && !examActive && !examCountdown && !examGrading && (
        <div className="mt-3 rounded-xl border border-emerald-400/25 bg-emerald-500/10 p-3 text-[12px] leading-relaxed text-emerald-50">
          <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-emerald-200/75">Bilan</div>
          <p>{examReport.spokenSummary}</p>
          <button
            type="button"
            onClick={() => downloadExamReport(examReport.markdown)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-emerald-300/40 bg-emerald-400/15 px-3 py-1.5 text-[11px] font-semibold text-emerald-100 hover:bg-emerald-400/25"
          >
            <Download size={12} /> Rapport complet (.md)
          </button>
        </div>
      )}

      {examArmed && !examActive && !examCountdown && (
        <div className="mt-3 rounded-xl border border-amber-300/25 bg-amber-400/10 p-3 text-[12px] leading-relaxed text-amber-100">
          {!examIsInteractive
            ? "Oral pret. Clique sur Parle : decompte 3, 2, 1, puis presente ton sujet sans interruption. Aurora corrige a la fin."
            : examFormat === 'mixed'
              ? "Entretien pret. Clique sur Parle : Aurora t invite a presenter SANS te couper. Quand tu as fini, dis simplement « j ai termine » (ou clique sur « passer aux questions ») et elle te questionne."
              : "Entretien pret. Clique sur Parle : Aurora pose sa premiere question. Reponds a voix haute, elle attend que tu finisses ta reponse puis relance."}
        </div>
      )}

      {examPanelOpen && !examActive && !examCountdown && (
        <div className="mt-3 space-y-3">
          {/* 1 — Type d'oral (cartes claires) */}
          <div>
            <span className="mb-1.5 block text-[10px] uppercase tracking-[0.16em] text-white/35">Type d oral</span>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
              {examModeCards.map((card) => (
                <button
                  key={card.fmt}
                  type="button"
                  onClick={() => setExamFormat(card.fmt)}
                  className={`rounded-xl border p-2.5 text-left transition-all ${
                    examFormat === card.fmt
                      ? 'border-emerald-300/60 bg-emerald-400/12'
                      : 'border-white/10 bg-white/[0.04] hover:border-white/25'
                  }`}
                >
                  <div className={`text-[12px] font-semibold ${examFormat === card.fmt ? 'text-emerald-100' : 'text-white/80'}`}>{card.title}</div>
                  <div className="mt-0.5 text-[10px] leading-snug text-white/45">{card.desc}</div>
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] leading-snug text-emerald-200/70">{examModeExplain}</p>
          </div>

          {/* 2 — Examinateur + intensité */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <span className="mb-1 block text-[10px] uppercase tracking-[0.16em] text-white/35">Examinateur</span>
              <div className="flex gap-1">
                {(Object.keys(VOICE_EXAM_INTERVIEWERS) as VoiceExamInterviewer[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setExamInterviewer(key)}
                    title={VOICE_EXAM_INTERVIEWERS[key].hint}
                    className={`flex-1 rounded-lg border px-1.5 py-1.5 text-[10px] font-semibold ${
                      examInterviewer === key
                        ? 'border-emerald-300/60 bg-emerald-400/15 text-emerald-100'
                        : 'border-white/10 bg-white/[0.04] text-white/45 hover:text-white/75'
                    }`}
                  >
                    {VOICE_EXAM_INTERVIEWERS[key].label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <span className="mb-1 block text-[10px] uppercase tracking-[0.16em] text-white/35">Intensite</span>
              <div className="flex gap-1">
                {(Object.keys(VOICE_EXAM_INTENSITIES) as VoiceExamIntensity[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setExamIntensity(key)}
                    title={VOICE_EXAM_INTENSITIES[key].hint}
                    className={`flex-1 rounded-lg border px-1.5 py-1.5 text-[10px] font-semibold ${
                      examIntensity === key
                        ? 'border-emerald-300/60 bg-emerald-400/15 text-emerald-100'
                        : 'border-white/10 bg-white/[0.04] text-white/45 hover:text-white/75'
                    }`}
                  >
                    {VOICE_EXAM_INTENSITIES[key].label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 3 — Durée + sujet */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <label className="sm:col-span-1">
              <span className="mb-1 block text-[10px] uppercase tracking-[0.16em] text-white/35">Duree</span>
              <input
                type="text"
                inputMode="text"
                value={examDurationText}
                onChange={(e) => setExamDurationText(e.target.value)}
                placeholder="10min, 1h30..."
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-white/25 focus:border-emerald-300/60"
              />
            </label>
            <label className="sm:col-span-2">
              <span className="mb-1 block text-[10px] uppercase tracking-[0.16em] text-white/35">Sujet / matiere</span>
              <input
                value={examSubject}
                onChange={(e) => setExamSubject(e.target.value)}
                placeholder="Grand oral, anglais LV1, philo..."
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-white/25 focus:border-emerald-300/60"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-1">
            {['5min', '10min', '15min', '1h30'].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setExamDurationText(preset)}
                className="rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] font-mono text-white/50 hover:text-white"
              >
                {preset}
              </button>
            ))}
          </div>

          {/* 4 — Questions / consigne (label adapté au mode) */}
          <label className="block">
            <span className="mb-1 block text-[10px] uppercase tracking-[0.16em] text-white/35">
              {examIsInteractive ? 'Questions du jury (une par ligne, optionnel)' : 'Consigne / sujet a presenter'}
            </span>
            <textarea
              value={examQuestions}
              onChange={(e) => setExamQuestions(e.target.value)}
              rows={3}
              placeholder={examIsInteractive
                ? 'Une question par ligne. Vide = Aurora improvise selon le sujet.'
                : 'Le sujet ou la consigne a presenter pendant l oral...'}
              className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-white/25 focus:border-emerald-300/60"
            />
          </label>

          {/* 5 — Options avancées repliées (fini le brouillon) */}
          <button
            type="button"
            onClick={() => setExamAdvancedOpen((v) => !v)}
            className="text-[11px] text-white/45 hover:text-white/70"
          >
            {examAdvancedOpen ? '− Options avancees' : '+ Options avancees (fiches, plan, criteres)'}
          </button>
          {examAdvancedOpen && (
            <div className="space-y-2">
              <label className="block cursor-pointer rounded-xl border border-dashed border-white/18 bg-black/20 px-3 py-3 text-sm text-white/70 hover:border-emerald-300/40">
                <div className="flex items-center gap-2">
                  <FileText size={15} />
                  <span>{examFiles.length ? `${examFiles.length} fichier(s)` : 'Ajouter fiches ou grilles'}</span>
                  {examLoadingFiles && <Loader2 size={13} className="animate-spin text-emerald-300" />}
                </div>
                <input
                  type="file"
                  multiple
                  accept=".txt,.md,.markdown,.pdf,.docx"
                  className="hidden"
                  onChange={(event) => {
                    setExamFiles(Array.from(event.target.files || []))
                    event.currentTarget.value = ''
                  }}
                />
              </label>
              <textarea
                value={examPlan}
                onChange={(e) => setExamPlan(e.target.value)}
                rows={3}
                placeholder="Plan optionnel : intro, parties, conclusion..."
                className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-white/25 focus:border-emerald-300/60"
              />
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
                <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-white/35">Criteres de notation</div>
                <div className="space-y-1">
                  {examCriteriaPreview.slice(0, 5).map((criterion) => (
                    <div key={criterion.label} className="flex items-start justify-between gap-3 text-[11px] text-white/55">
                      <span>{criterion.label}</span>
                      <span className="font-mono text-white/35">{criterion.weight}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {examError && (
            <div className="rounded-lg border border-red-300/25 bg-red-500/10 px-3 py-2 text-[11px] text-red-200">
              {examError}
            </div>
          )}
          <button
            type="button"
            onClick={() => { armExam() }}
            disabled={examLoadingFiles}
            className="w-full rounded-xl border border-emerald-300/40 bg-emerald-400/15 px-4 py-3 text-sm font-semibold text-emerald-100 hover:bg-emerald-400/25 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {examIsInteractive ? 'Preparer l entretien, puis cliquer sur Parle' : 'Preparer l oral, puis cliquer sur Parle'}
          </button>
        </div>
      )}
    </div>
  )

  // App.tsx detecte `data-voice-panel` et skip son swipe handler quand le touch
  // vient de l interieur -- plus besoin de bloquer manuellement les events ici.
  // Ca laisse le scroll interne natif fonctionner sans interference.
  const voiceRootRef = useRef<HTMLDivElement | null>(null)

  const [camPos, setCamPos] = useState<{ x: number; y: number } | null>(() => {
    try {
      const raw = window.localStorage.getItem('aurora.voice.camPos')
      return raw ? JSON.parse(raw) as { x: number; y: number } : null
    } catch { return null }
  })
  const startCamDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return
    const host = voiceRootRef.current
    if (!host) return
    const box = e.currentTarget.getBoundingClientRect()
    const dx = e.clientX - box.left
    const dy = e.clientY - box.top
    let last: { x: number; y: number } | null = null
    const onMove = (ev: PointerEvent) => {
      const hostBox = host.getBoundingClientRect()
      const x = Math.min(Math.max(0, ev.clientX - hostBox.left - dx), Math.max(0, hostBox.width - box.width))
      const y = Math.min(Math.max(0, ev.clientY - hostBox.top - dy), Math.max(0, hostBox.height - box.height))
      last = { x, y }
      setCamPos(last)
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      try { if (last) window.localStorage.setItem('aurora.voice.camPos', JSON.stringify(last)) } catch { /* ignore */ }
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }, [])

  const isAuroraV4Skin = typeof document !== 'undefined'
    && document.documentElement.getAttribute('data-ui-skin') === 'aurora_v4'

  if (voiceStudioOpen) {
    return <VoiceReplicationStudio onClose={() => setVoiceStudioOpen(false)} />
  }

  if (musicStudioOpen) {
    return <MusicStudio onClose={() => setMusicStudioOpen(false)} />
  }

  if (stageMode && !isAuroraV4Skin) {
    return (
      <div
        ref={voiceRootRef}
        data-voice-panel="true"
        className="relative flex h-full max-h-full flex-col overflow-hidden"
        style={{ touchAction: 'pan-y', WebkitOverflowScrolling: 'touch' }}
      >
        <VoiceStage
          phase={ap === 'transcribing' ? 'thinking' : (ap as 'idle' | 'listening' | 'thinking' | 'speaking')}
          subtitle={ui === 'speaking' || ui === 'thinking' ? (revealedText || undefined) : undefined}
          statusLabel={ui === 'idle' && isContinuous ? "Parle, je t'écoute…" : (st.label || undefined)}
          statusColor={st.color}
          amplitude={ui === 'speaking' ? speakingAmplitude : ui === 'listening' ? volumeLevel : 0}
          viseme={lyraViseme}
          emotion={ui === 'listening' ? 'curious' : ui === 'thinking' ? 'focus' : ui === 'speaking' ? 'happy' : 'neutral'}
          landscapeMode="auto"
          micActive={ui === 'listening'}
          onTogglePtt={() => {
            if (examArmed) { void startExam(); return }
            if (examActive) { void finishExam(); return }
            void toggleListening()
          }}
          onClose={handleClose}
          lang={lang}
          onToggleLang={() => setLang(lang === 'fr' ? 'en' : 'fr')}
          transcript={transcript.map((t) => ({ role: t.role, text: t.text, image: t.image, video: t.video }))}
          onClearTranscript={() => setTranscript([])}
          onSendText={(text) => { void handleTranscriptImpl(text) }}
          cameraActive={camera.enabled}
          visualContext={visualStatus}
          sttInfo={sttModel || undefined}
          modelInfo={mainModel}
        >
          {examPanel}
          <div style={{ position: 'absolute', top: 18, left: 18, zIndex: 6, display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => setVoiceStudioOpen(true)}
              title="Ouvrir le studio de réplication de voix par échantillon"
              style={{
                padding: '8px 14px', borderRadius: 99,
                fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
                background: 'linear-gradient(135deg, rgba(124, 58, 237, 0.7), rgba(192, 38, 211, 0.7))',
                border: '1px solid rgba(192, 38, 211, 0.5)',
                color: '#ffffff', cursor: 'pointer',
                letterSpacing: '0.08em', fontWeight: 600,
                boxShadow: '0 2px 8px rgba(124, 58, 237, 0.3)',
              }}
            >
              🎙️ studio réplication
            </button>
            <button
              type="button"
              onClick={() => setMusicStudioOpen(true)}
              title="Ouvrir le studio musique"
              style={{
                padding: '8px 14px', borderRadius: 99,
                fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
                background: 'var(--v4voice-chip-bg, rgba(0,0,0,0.45))',
                border: '1px solid var(--v4voice-chip-line, rgba(255,255,255,0.18))',
                color: 'var(--v4voice-chip-fg, rgba(255,255,255,0.85))', cursor: 'pointer',
                letterSpacing: '0.08em',
              }}
            >
              ♫ studio musique
            </button>
          </div>
          <button
            type="button"
            onClick={() => setStageMode(false)}
            title="Basculer vers la vue classique (sphère 3D)"
            style={{
              position: 'absolute', top: 18, right: 18, zIndex: 6,
              padding: '8px 14px', borderRadius: 99,
              fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
              background: 'var(--v4voice-chip-bg, rgba(0,0,0,0.45))',
              border: '1px solid var(--v4voice-chip-line, rgba(255,255,255,0.18))',
              color: 'var(--v4voice-chip-fg, rgba(255,255,255,0.85))', cursor: 'pointer',
              letterSpacing: '0.08em',
            }}
          >
            ◐ classic
          </button>
          {error && (
            <div style={{
              position: 'absolute', top: 70, left: '50%', transform: 'translateX(-50%)',
              zIndex: 5,
              padding: '8px 14px', borderRadius: 12,
              background: 'var(--v4voice-danger-bg, rgba(220,30,60,0.92))', color: 'var(--v4voice-danger-fg, #fff)',
              fontSize: 12, maxWidth: 520, textAlign: 'center',
            }}>
              {error}
            </div>
          )}
        </VoiceStage>
      </div>
    )
  }

  return (
    <div
      ref={voiceRootRef}
      data-voice-panel="true"
      className="relative flex h-full max-h-full flex-col overflow-hidden"
      style={{
        touchAction: 'pan-y',
        WebkitOverflowScrolling: 'touch',
      }}
    >
      {isAuroraV4Skin ? (
        <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ background: 'radial-gradient(ellipse at 50% 30%, rgba(13,18,34,.9), #05070D)' }}>
          <V4VoiceScene
            uiState={ui}
            level={ui === 'speaking' ? speakingAmplitude : ui === 'listening' ? volumeLevel : 0}
          />
        </div>
      ) : (
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute inset-0 aurora-mesh opacity-40" />
          <div className="absolute -top-40 left-1/4 h-80 w-80 rounded-full bg-fuchsia-500/20 blur-3xl animate-aurora-drift" />
          <div className="absolute -bottom-40 right-1/4 h-80 w-80 rounded-full bg-cyan-500/15 blur-3xl animate-aurora-drift" style={{ animationDelay: '3s' }} />
        </div>
      )}
      {isAuroraV4Skin && (
        <div
          className="relative z-10 flex shrink-0 items-center gap-3.5 px-4 pb-3 pt-4"
          style={{
            borderBottom: '1px solid rgba(255,255,255,0.09)',
            animation: 'v4VoiceHeadIn .4s cubic-bezier(.22,1,.36,1)',
          }}
        >
          <AuroraMascot module="voice" size={46} />
          <div style={{ minWidth: 0 }}>
            <h1
              style={{
                margin: 0,
                fontSize: 20,
                fontWeight: 800,
                letterSpacing: '-0.02em',
                color: '#E6EAF5',
                fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif",
              }}
            >
              Copilote Vocal
            </h1>
            <div
              style={{
                fontFamily: "'Cascadia Code',Consolas,monospace",
                fontSize: 10,
                letterSpacing: '.2em',
                textTransform: 'uppercase',
                color: '#8B93A7',
              }}
            >
              echo · écoute continue{sttModel ? ` · ${sttModel}` : ''}
            </div>
          </div>
          <span
            style={{
              marginLeft: 'auto',
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 10,
              letterSpacing: '.18em',
              textTransform: 'uppercase',
              color: '#8B93A7',
              padding: '5px 11px',
              borderRadius: 999,
              border: '1px solid rgba(255,255,255,.1)',
              background: 'rgba(10,15,30,.5)',
              maxWidth: 180,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {mainModel}
          </span>
        </div>
      )}
      {/* Barre du haut avec bouton retour + controle camera */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2 shrink-0">
        <button
          onClick={handleClose}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.05] px-3 py-1.5 text-[11px] text-white/50 hover:bg-white/[0.10] hover:text-white/80 transition-colors"
        >
          <ArrowLeft size={12} />
          <span>Retour</span>
        </button>
        <span className="text-[11px] font-medium text-white/40 hidden sm:inline">Chat Vocal Live</span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setVoiceStudioOpen(true)}
            title="Studio de réplication de voix par échantillon"
            className="flex items-center gap-1 rounded-lg border border-violet-400/40 bg-gradient-to-r from-violet-600/30 to-fuchsia-600/30 px-2.5 py-1.5 text-[11px] font-semibold text-violet-100 hover:opacity-90 shadow-sm"
          >
            <Mic size={13} className="text-violet-300" />
            <span className="hidden sm:inline">Studio Voix</span>
          </button>
          <button
            type="button"
            onClick={() => setMusicStudioOpen(true)}
            title="Créer un morceau et gérer les voix de référence"
            className="flex items-center gap-1 rounded-lg border border-fuchsia-400/30 bg-fuchsia-500/10 px-2.5 py-1.5 text-[11px] font-medium text-fuchsia-100 hover:bg-fuchsia-500/20"
          >
            <Music size={13} />
            <span className="hidden sm:inline">Musique</span>
          </button>
          {!isAuroraV4Skin && (
            <button
              type="button"
              onClick={() => setStageMode(true)}
              title="Repasser en vue Stage (paysage + Lyra)"
              className="flex items-center gap-1 rounded-lg border border-violet-400/30 bg-violet-500/15 px-2.5 py-1.5 text-[11px] font-medium text-violet-200 hover:bg-violet-500/25"
            >
              <Sparkles size={12} />
              <span className="hidden sm:inline">Stage</span>
            </button>
          )}
          {camera.enabled && (
            <button
              onClick={() => { void camera.switchCamera() }}
              className="flex items-center gap-1 rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2 py-1.5 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/20 transition-colors"
              title={lang === 'fr' ? 'Retourner la camera (avant/arriere)' : 'Flip camera (front/back)'}
            >
              <RefreshCw size={14} />
              <span className="hidden sm:inline">{lang === 'fr' ? 'Retourner' : 'Flip'}</span>
            </button>
          )}
          <button
            onClick={() => { void camera.toggle() }}
            disabled={camera.starting}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors ${
              camera.enabled
                ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/20'
                : 'border-white/10 bg-white/[0.05] text-white/50 hover:bg-white/[0.10] hover:text-white/80'
            }`}
            title={
              camera.enabled
                ? (lang === 'fr' ? 'Desactiver la camera (Aurora ne voit plus)' : 'Disable camera (Aurora stops seeing)')
                : (lang === 'fr' ? 'Activer la camera (Aurora voit en direct)' : 'Enable camera (Aurora sees live)')
            }
          >
            {camera.starting
              ? <Loader2 size={12} className="animate-spin" />
              : camera.enabled
                ? <Camera size={12} />
                : <CameraOff size={12} />
            }
            <span className="hidden sm:inline">
              {camera.enabled ? (lang === 'fr' ? 'Vision ON' : 'Vision ON') : (lang === 'fr' ? 'Vision' : 'Vision')}
            </span>
          </button>
        </div>
      </div>

      <div className="relative z-10 shrink-0 border-b border-white/[0.04] bg-black/15 px-3 py-2">
        {examPanel}
      </div>

      {/* Preview camera -- UN SEUL <video> element.
          Le <video> garde son identite DOM a travers compact/fullscreen pour
          eviter les AbortError "play() interrupted by new load request". */}
      {camera.enabled && (
        <div
          className={
            cameraFullscreen
              ? 'fixed inset-0 z-50 flex flex-col bg-black/95 backdrop-blur-lg'
              : 'absolute right-3 top-14 z-20 flex flex-col overflow-hidden rounded-xl border-2 border-emerald-400/50 bg-black/90 shadow-2xl backdrop-blur-sm'
          }
          style={cameraFullscreen
            ? undefined
            : camPos
              ? { width: 240, left: camPos.x, top: camPos.y, right: 'auto', cursor: 'grab', touchAction: 'none' }
              : { width: 240, cursor: 'grab', touchAction: 'none' }}
          onPointerDown={cameraFullscreen ? undefined : startCamDrag}
        >
          {/* Video element unique, stable */}
          <div className={cameraFullscreen
            ? 'relative flex flex-1 items-center justify-center p-4'
            : 'shrink-0'
          }>
            <video
              ref={camera.videoRef}
              playsInline
              muted
              autoPlay
              className={cameraFullscreen
                ? 'max-h-full max-w-full rounded-xl border border-emerald-400/30 object-contain'
                : 'block w-full object-cover'
              }
              style={{
                transform: camera.facing === 'user' ? 'scaleX(-1)' : 'none',
                aspectRatio: cameraFullscreen ? undefined : '16/10',
              }}
            />

            {/* Avatar mini PIP en mode fullscreen -- style FaceTime.
                AuroraAvatar interne est 220x240, on le wrap dans un container
                de 140x150 avec transform scale pour ajuster sans deformer. */}
            {cameraFullscreen && (
              <div
                className="absolute z-[60] rounded-2xl overflow-hidden border-2 border-emerald-400/60 bg-black/90 shadow-2xl backdrop-blur-sm pointer-events-none"
                style={{
                  width: 140,
                  height: 150,
                  bottom: 'max(1.5rem, env(safe-area-inset-bottom))',
                  right: 'max(1.5rem, env(safe-area-inset-right))',
                }}
              >
                <div
                  style={{
                    width: 220,
                    height: 240,
                    transform: `scale(${140 / 220})`,
                    transformOrigin: 'top left',
                  }}
                >
                  <AuroraAvatar
                    phase={ap}
                    volumeLevel={volumeLevel}
                    speakingAmplitude={speakingAmplitude}
                    avatarPath={effectiveAvatar.path}
                    avatarType={effectiveAvatar.type}
                    animationMode={sel?.animationMode}
                    spokenText={revealedText}
                    formantsRef={formantsRef}
                    audioRef={audioRef}
                    phonemeCuesRef={phonemeCuesRef}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Barre de controles -- sous la video en compact, au dessus en fullscreen */}
          <div className={
            cameraFullscreen
              ? 'flex items-center justify-between border-b border-white/10 px-4 py-3 order-first'
              : 'flex items-center justify-between gap-2 bg-emerald-500/10 px-2 py-1 shrink-0'
          }>
            <span className={cameraFullscreen
              ? 'flex items-center gap-2 text-sm font-medium text-emerald-300'
              : 'flex items-center gap-1 text-[10px] font-medium text-emerald-300'
            }>
              <motion.span
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className={cameraFullscreen ? 'h-2 w-2 rounded-full bg-emerald-400' : 'h-1.5 w-1.5 rounded-full bg-emerald-400'}
              />
              <span>{cameraFullscreen
                ? (lang === 'fr' ? 'LIVE · Aurora voit ce que tu lui montres' : 'LIVE · Aurora sees what you show')
                : 'LIVE · Aurora voit'
              }</span>
            </span>
            <div className="flex items-center gap-1">
              {/* Bouton retourner camera -- TOUJOURS visible (compact + fullscreen)
                  a cote des boutons zoom/fermer pour etre accessible. */}
              <button
                onClick={() => { void camera.switchCamera() }}
                className={cameraFullscreen
                  ? 'rounded-lg border border-white/15 bg-white/5 p-2 text-white/70 hover:bg-white/10'
                  : 'rounded p-0.5 text-emerald-300/70 hover:bg-emerald-500/20 hover:text-emerald-200'
                }
                title={lang === 'fr' ? 'Retourner la camera (avant/arriere)' : 'Flip camera (front/back)'}
              >
                <RefreshCw size={cameraFullscreen ? 16 : 12} />
              </button>
              <button
                onClick={() => setCameraFullscreen(!cameraFullscreen)}
                className={cameraFullscreen
                  ? 'rounded-lg border border-white/15 bg-white/5 p-2 text-white/70 hover:bg-white/10'
                  : 'rounded p-0.5 text-emerald-300/70 hover:bg-emerald-500/20 hover:text-emerald-200'
                }
                title={cameraFullscreen
                  ? (lang === 'fr' ? 'Reduire' : 'Minimize')
                  : (lang === 'fr' ? 'Agrandir' : 'Expand')
                }
              >
                {cameraFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={12} />}
              </button>
              <button
                onClick={() => { camera.stop(); setCameraFullscreen(false) }}
                className={cameraFullscreen
                  ? 'rounded-lg border border-red-400/30 bg-red-500/10 p-2 text-red-300 hover:bg-red-500/20'
                  : 'rounded p-0.5 text-emerald-300/70 hover:bg-red-500/20 hover:text-red-300'
                }
                title={lang === 'fr' ? 'Fermer' : 'Close'}
              >
                <CameraOff size={cameraFullscreen ? 16 : 12} />
              </button>
            </div>
          </div>

          {/* Description en fullscreen uniquement */}
          {cameraFullscreen && visualStatus && (
            <div className="border-t border-emerald-400/20 bg-emerald-500/[0.06] px-4 py-2">
              <div className="text-[10px] uppercase tracking-[0.22em] text-emerald-400/60">
                {lang === 'fr' ? 'Aurora voit' : 'Aurora sees'}
              </div>
              <p className="mt-0.5 text-sm text-emerald-100/90">{visualStatus}</p>
            </div>
          )}
        </div>
      )}

      {/* Erreur camera -- TOUJOURS visible (meme si starting ou enabled) */}
      {camera.error && (
        <div className="absolute right-3 top-14 z-20 max-w-sm rounded-xl border border-red-400/40 bg-red-500/15 px-3 py-2 text-[11px] leading-relaxed text-red-200 shadow-lg">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-300">
            <CameraOff size={11} />
            <span>Camera</span>
          </div>
          <p className="whitespace-pre-line">{camera.error}</p>
        </div>
      )}
      {/* Zone principale: scrollable sur mobile pour acceder au transcript + controls */}
      <div
        className="flex flex-1 min-h-0 flex-col items-center gap-2 overflow-y-auto px-3 py-3 sm:justify-center"
        style={{
          WebkitOverflowScrolling: 'touch',
          touchAction: 'pan-y',
          overscrollBehavior: 'contain',
        }}
      >
        <div className="relative">
          {/* Anneau coloré — reflète l'état réel */}
          <motion.div animate={{
            borderColor: st.color + (ui === 'idle' ? '15' : '60'),
            scale: ui === 'speaking' ? 1 + speakingAmplitude * 0.04 : ui === 'listening' ? 1 + volumeLevel * 0.03 : 1,
          }} transition={{ duration: 0.1 }}
            className="absolute -inset-2 rounded-[1.2rem] pointer-events-none"
            style={{ border: `3px solid ${st.color}60` }} />
          {isAuroraV4Skin && effectiveAvatar.type !== 'talking-video' && (!selectedAvatarId || selectedAvatarId === avatarList[0]?.id) ? (
            <V4VoiceCharacter
              phase={ui}
              viseme={lyraViseme}
              level={ui === 'speaking' ? speakingAmplitude : ui === 'listening' ? volumeLevel : 0}
              size={230}
            />
          ) : (
            <AuroraAvatar phase={ap} volumeLevel={volumeLevel} speakingAmplitude={speakingAmplitude}
              avatarPath={effectiveAvatar.path} avatarType={effectiveAvatar.type} animationMode={sel?.animationMode} spokenText={revealedText}
              formantsRef={formantsRef} audioRef={audioRef} phonemeCuesRef={phonemeCuesRef} />
          )}
          <button onClick={() => setAvatarModal(true)}
            className="absolute -right-3 -top-2 z-10 rounded-full bg-white/[0.1] border border-white/15 p-1.5 hover:bg-white/[0.2]"
            title={lang === 'fr' ? 'Choisir un avatar' : 'Pick avatar'}>
            <UserCircle size={14} className="text-white/60" />
          </button>
          <button onClick={() => setForgeOpen(true)}
            className="absolute -right-3 -bottom-2 z-10 flex items-center gap-1 rounded-full bg-gradient-to-r from-fuchsia-500/30 to-cyan-400/30 border border-white/20 px-2 py-1 text-[10px] font-medium text-white/90 hover:from-fuchsia-500/50 hover:to-cyan-400/50"
            title={lang === 'fr' ? 'Ouvrir la Forge de personnage' : 'Open Character Forge'}>
            <Sparkles size={10} />
            <span>{lang === 'fr' ? 'Créer' : 'Create'}</span>
          </button>
        </div>

        {/* État affiché */}
        <div className="flex items-center gap-2 min-h-[2rem] max-w-[85vw]">
          {(ui === 'speaking' || ui === 'thinking') && revealedText ? (
            <p className="text-center text-xs leading-relaxed text-white/70">{revealedText}</p>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div key={ui} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                className="flex items-center gap-2">
                {ui !== 'idle' && (
                  <motion.div
                    animate={ui === 'listening' ? { scale: [1, 1.4, 1], opacity: [0.8, 0.4, 0.8] } : { rotate: 360 }}
                    transition={ui === 'listening' ? { duration: 1.5, repeat: Infinity } : { duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="h-2.5 w-2.5 rounded-full" style={{ background: st.color }} />
                )}
                <span className={`text-xs ${ui === 'idle' ? (isContinuous ? 'text-white/50' : 'text-white/30') : 'text-white/70'}`}>
                  {ui === 'idle' && isContinuous ? "Parle, je t'ecoute..." : st.label}
                </span>
              </motion.div>
            </AnimatePresence>
          )}
        </div>

        <div className="flex flex-col items-center gap-1.5">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.18em] text-white/40">Agent · {activeAgent.role}</span>
            <button
              type="button"
              onClick={toggleAgentMode}
              title={agentMode === 'auto'
                ? "Mode auto : l'agent suit le module actif. Clic pour figer."
                : 'Mode manuel : ton choix d\'agent est conservé. Clic pour repasser en auto.'}
              className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider transition-all ${
                agentMode === 'auto'
                  ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-300'
                  : 'border-amber-400/40 bg-amber-500/10 text-amber-300'
              }`}
            >
              {agentMode === 'auto' ? '⟳ Auto' : '⏸ Manuel'}
            </button>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-1.5 max-w-[85vw]">
            {allAgents.map((a) => {
              const active = a.id === activeAgentId
              return (
                <button
                  key={a.id}
                  onClick={() => handleAgentChange(a.id)}
                  title={`${a.name} — ${a.motto}`}
                  className={`rounded-lg border px-2 py-1 text-[11px] font-medium transition-all ${
                    active ? 'text-white' : 'text-white/60 hover:text-white/90'
                  }`}
                  style={{
                    background: active ? `${a.color}28` : 'var(--v4voice-soft-bg, rgba(255,255,255,0.04))',
                    borderColor: active ? `${a.color}80` : 'var(--v4voice-soft-line, rgba(255,255,255,0.12))',
                    boxShadow: active ? `0 0 0 1px ${a.color}55` : 'none',
                  }}
                >
                  <span className="mr-1" style={{ color: a.color }}>{a.glyph}</span>
                  {a.name}
                </button>
              )
            })}
          </div>
        </div>

        {/* STT info + lang toggle + TTS test */}
        <div className="flex items-center gap-2">
          {sttModel && (
            <span className="rounded-lg border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] text-white/40">
              {sttModel}
            </span>
          )}
          <button
            onClick={() => setLang((l) => l === 'fr' ? 'en' : 'fr')}
            className="rounded-lg border border-white/15 bg-white/[0.06] px-2.5 py-0.5 text-[11px] font-medium text-white/60 hover:text-white/90 transition-colors"
          >
            {lang === 'fr' ? 'FR' : 'EN'}
          </button>
          {/* Bouton test TTS: force une lecture de test pour diagnostiquer le son sur n importe quel appareil */}
          <button
            onClick={() => {
              const testText = lang === 'fr'
                ? 'Test audio Aurora. Si tu entends cette phrase, la synthese vocale fonctionne correctement.'
                : 'Aurora audio test. If you hear this sentence, speech synthesis is working correctly.'
              console.log('[TTS TEST] Manual test triggered')
              void speakText(testText)
            }}
            className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-300 hover:bg-amber-500/20 transition-colors"
            title={lang === 'fr' ? 'Test audio: force une lecture pour verifier que le son marche' : 'Audio test: force playback to check sound works'}
          >
            {lang === 'fr' ? 'Test son' : 'Test audio'}
          </button>
        </div>

        <motion.button onClick={() => {
          if (examArmed) { void startExam(); return }
          if (examActive) { void finishExam(); return }
          if (phase === 'speaking') stopSpeaking(); else toggleListening()
        }}
          disabled={ui === 'transcribing' || ui === 'thinking' || ui === 'searching'}
          whileTap={{ scale: 0.9 }}
          className="relative flex h-14 w-14 items-center justify-center rounded-full border-2 sm:h-16 sm:w-16"
          style={{
            borderColor: st.color + (ui === 'idle' ? '25' : '60'),
            background: ui === 'idle' ? 'var(--v4voice-soft-bg, rgba(255,255,255,0.04))' : st.color + '15',
            opacity: ['transcribing', 'thinking', 'searching', 'observing', 'preparing'].includes(ui) ? 0.4 : 1,
          }}>
          {ui === 'listening' && (
            <motion.div animate={{ scale: [1, 1.4, 1], opacity: [0.4, 0.1, 0.4] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              className="absolute inset-0 rounded-full" style={{ border: `2px solid ${st.color}40` }} />
          )}
          {['transcribing', 'thinking', 'searching', 'observing', 'preparing'].includes(ui) && (
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-0 rounded-full" style={{ border: '2px solid transparent', borderTopColor: st.color + '80' }} />
          )}
          {ui === 'listening' ? <MicOff size={22} style={{ color: st.color }} />
            : ui === 'speaking' ? <Volume2 size={22} style={{ color: st.color }} />
            : ['thinking', 'transcribing', 'searching'].includes(ui) ? <Loader2 size={22} className="animate-spin" style={{ color: st.color }} />
            : <Mic size={22} className="text-white/60" />}
        </motion.button>
      </div>

      {/* Toggle pour masquer le banner "Aurora voit" (toujours visible quand camera ON) */}
      {camera.enabled && (visualStatus || webSearching) && visualStatusHidden && (
        <div className="shrink-0 flex justify-end border-t border-white/[0.04] bg-black/20 px-2 py-1">
          <button
            onClick={() => setVisualStatusHidden(false)}
            className="text-[10px] text-white/40 hover:text-white/70 flex items-center gap-1"
            title={lang === 'fr' ? 'Afficher ce que voit Aurora' : 'Show what Aurora sees'}
          >
            <Eye size={10} />
            <span>{lang === 'fr' ? 'Afficher observation' : 'Show observation'}</span>
          </button>
        </div>
      )}

      {/* Banner "Aurora voit" + indicateur recherche web (cachable via bouton) */}
      <AnimatePresence>
        {camera.enabled && (visualStatus || webSearching) && !visualStatusHidden && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="shrink-0 overflow-hidden border-t border-emerald-400/15 bg-emerald-500/[0.04]"
          >
            <div className="flex items-start gap-2 px-3 py-1.5">
              <Eye size={12} className="mt-0.5 shrink-0 text-emerald-400/80" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-[9px] uppercase tracking-[0.22em] text-emerald-400/60">
                  <span>{lang === 'fr' ? 'Aurora voit' : 'Aurora sees'}</span>
                  {webSearching && (
                    <span className="flex items-center gap-1 rounded border border-cyan-400/30 bg-cyan-500/10 px-1.5 py-0.5 text-[8px] text-cyan-300">
                      <Loader2 size={8} className="animate-spin" />
                      {lang === 'fr' ? 'recherche web...' : 'web search...'}
                    </span>
                  )}
                  {!webSearching && webSearchSources.length > 0 && (
                    <span
                      className="flex items-center gap-1 rounded border border-cyan-400/30 bg-cyan-500/10 px-1.5 py-0.5 text-[8px] text-cyan-300"
                      title={webSearchSources.join(' · ')}
                    >
                      {webSearchSources.length} {lang === 'fr' ? 'sites' : 'sites'}
                    </span>
                  )}
                </div>
                <p className="text-[11px] leading-snug text-emerald-100/80 line-clamp-2">
                  {visualStatus}
                </p>
                {webSearchSources.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {webSearchSources.slice(0, 5).map((src, i) => (
                      <span
                        key={i}
                        className="rounded border border-cyan-400/20 bg-cyan-500/[0.08] px-1 py-0.5 text-[8px] text-cyan-200/80"
                      >
                        {src}
                      </span>
                    ))}
                    {webSearchSources.length > 5 && (
                      <span className="text-[8px] text-cyan-300/60">+{webSearchSources.length - 5}</span>
                    )}
                  </div>
                )}
              </div>
              <button
                onClick={() => setVisualStatusHidden(true)}
                className="shrink-0 rounded p-0.5 text-emerald-300/60 hover:bg-emerald-500/20 hover:text-emerald-200"
                title={lang === 'fr' ? 'Masquer' : 'Hide'}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Transcript */}
      <div className="shrink-0 border-t border-white/[0.06] bg-black/20">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.04]">
          <span className="text-[10px] uppercase tracking-[0.22em] text-white/30">
            Transcription {transcript.length > 0 && `(${transcript.length})`}
          </span>
          {transcript.length > 0 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  const text = transcript
                    .map((entry) => `${entry.role === 'user' ? 'Moi' : 'Aurora'}: ${entry.text}`)
                    .join('\n\n')
                  navigator.clipboard?.writeText(text).then(() => {
                    setCopyFeedback(true)
                    window.setTimeout(() => setCopyFeedback(false), 1500)
                  }).catch(() => undefined)
                }}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] transition-colors ${
                  copyFeedback
                    ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                    : 'border-white/10 bg-white/[0.05] text-white/50 hover:text-white/80'
                }`}
                title="Copier le transcript"
              >
                {copyFeedback ? <Check size={10} /> : <Copy size={10} />}
                <span>{copyFeedback ? 'Copie !' : 'Copier'}</span>
              </button>
              <button
                onClick={() => {
                  const lines = transcript.map((entry) => `**${entry.role === 'user' ? 'Moi' : 'Aurora'}** : ${entry.text}`)
                  const md = `# Transcription vocale Aurora IA\n\n_${new Date().toLocaleString('fr-FR')}_\n\n${lines.join('\n\n')}\n`
                  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
                  const url = URL.createObjectURL(blob)
                  const anchor = document.createElement('a')
                  anchor.href = url
                  anchor.download = `aurora-voix-${Date.now()}.md`
                  anchor.click()
                  setTimeout(() => URL.revokeObjectURL(url), 1000)
                }}
                className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] text-white/50 hover:text-white/80"
                title="Telecharger le transcript en markdown"
              >
                <Download size={10} />
                <span>.md</span>
              </button>
              <button
                onClick={() => {
                  if (confirm('Effacer tout le transcript de cette session ?')) {
                    setTranscript([])
                    setHistory([])
                    setRevealedText('')
                  }
                }}
                className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] text-white/50 hover:text-red-300 hover:border-red-400/30"
                title="Effacer le transcript"
              >
                <Trash2 size={10} />
              </button>
            </div>
          )}
        </div>
        <div className="max-h-[30vh] min-h-[3rem] overflow-y-auto px-3 py-2">
          {transcript.length === 0 ? (
            <p className="text-center text-[11px] text-white/20">Transcription</p>
          ) : (
            <div className="space-y-1.5">
              {transcript.slice(-15).map(e => (
                <div key={e.id} className={`flex ${e.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-xl px-2.5 py-1.5 text-[12px] leading-snug ${
                    e.role === 'user' ? 'bg-indigo-500/15 text-white/90 border border-indigo-400/20' : 'bg-white/[0.06] text-white/60 border border-white/[0.06]'
                  }`}>{e.text}</div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      {error && <div className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-lg bg-red-500/10 border border-red-400/20 px-3 py-1.5 text-[11px] text-red-300">{error}</div>}

      <AvatarSelectorModal open={avatarModal} onClose={() => setAvatarModal(false)}
        onSelect={av => setSelectedAvatar(av.id)} onGenerateIn3D={handleGenerateAvatar}
        onImportFromSaves={handleImportFromSaves} onRemove={id => removeAvatar(id)}
        avatars={avatarList} selectedId={selectedAvatarId} />

      <CharacterForgeOverlay
        open={forgeOpen}
        onClose={() => setForgeOpen(false)}
      />

      {/* Suivi generation avatar */}
      <AnimatePresence>
        {(isGenerating || genProgress) && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}
            className="absolute bottom-16 left-1/2 -translate-x-1/2 w-[90vw] max-w-sm rounded-xl border border-cyan-400/20 bg-[#12121f]/95 backdrop-blur px-4 py-3 shadow-2xl">
            <div className="h-1.5 rounded-full bg-white/10 mb-2 overflow-hidden">
              <motion.div animate={{ width: `${genPct}%` }} transition={{ duration: 0.5 }}
                className="h-full rounded-full" style={{ background: genPct >= 100 ? 'var(--v4voice-ok, #22c55e)' : 'var(--v4voice-info, #06b6d4)' }} />
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                {isGenerating && (
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="shrink-0 h-3.5 w-3.5 rounded-full border-2 border-t-cyan-400 border-r-transparent border-b-transparent border-l-transparent" />
                )}
                <span className="text-[11px] text-white/70 truncate">{genProgress}</span>
              </div>
              <span className="text-[10px] text-white/40 shrink-0">{genPct}%</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
