import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLearningSessionStore } from '../../stores/learningSessionStore.ts'
import type { ReactNode, RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BookOpen,
  Check,
  ChevronDown,
  Clock,
  Download,
  Flame,
  Gamepad2,
  GraduationCap,
  Heart,
  Layers,
  Lightbulb,
  Loader2,
  Map as MapIcon,
  RefreshCw,
  RotateCcw,
  Shuffle,
  Sparkles,
  Swords,
  Star,
  Target,
  Timer,
  Trophy,
  Trash2,
  Zap,
} from 'lucide-react'
import AskAboutContentBox from '../../components/AskAboutContentBox.tsx'
import ClarificationDialog from '../../components/ClarificationDialog.tsx'
import type { ClarificationRequest } from '../../components/ClarificationDialog.tsx'
import ContextFilesField from '../../components/ContextFilesField.tsx'
import VoicePushToTalk from '../../components/VoicePushToTalk.tsx'
import ModuleAssetPackCard from '../../components/ModuleAssetPackCard.tsx'
import RecoveryBanner from '../../components/RecoveryBanner.tsx'
import { buildLearningModuleAssets } from '../../config/moduleAssetPacks.ts'
import { useManagedRuntime } from '../../hooks/useManagedRuntime.ts'
import { useModuleAssetPack } from '../../hooks/useModuleAssetPack.ts'
import { ollamaChatStream } from '../../hooks/useTauri.ts'
import { prepareTaskIntelligence } from '../../services/taskIntelligence.ts'
import { researchLearningTopic, summarizeSourcesForUI, buildAcademicLevelInstructions, type LearningSource, type AcademicIntent } from '../../services/learningResearch.ts'
import { verifyFlashcards, applyVerificationReport } from '../../services/flashcardVerification.ts'
import { buildDeckMindMap, describeDeckMindMap, evaluateMindMapQuality } from '../../services/deckMindMap.ts'
import DeckMindMap from '../../components/DeckMindMap.tsx'
import { useAppStore } from '../../stores/appStore.ts'
import { useFlashcardsStore, detectSubjectKind, SUBJECT_HINTS, type Flashcard, type FlashcardDeck, type SubjectKind, type KeyPoint } from '../../stores/flashcardsStore.ts'
import MarkdownPro from '../../components/MarkdownPro.tsx'
import { useLessonProgressStore, LESSON_QUIZ_PASSING_SCORE } from '../../stores/lessonProgressStore.ts'
import { useGamificationStore } from '../../stores/gamificationStore.ts'
import { useGenerationTrackerStore } from '../../stores/generationTrackerStore.ts'
import { useModuleHistoryStore } from '../../stores/moduleHistoryStore.ts'
import { useGenerationRecovery } from '../../hooks/useGenerationRecovery.ts'
import { getErrorMessage } from '../../utils/errors.ts'
import { prepareContextFiles } from '../../utils/multimodalContext.ts'

import type { Tab, FlashcardDraft, LessonRef } from './types.ts'
import { buildLearningSystemPrompt, extractJsonArray } from './utils.ts'
import { SourcesPanel } from './sharedComponents.tsx'

function VerificationBadge({ verification }: { verification: NonNullable<Flashcard['verification']> }) {
  const styles: Record<NonNullable<Flashcard['verification']>['status'], { label: string; bg: string; text: string; emoji: string; tooltip: string }> = {
    verified: {
      label: 'Sourcee',
      bg: 'bg-emerald-400/15 border-emerald-400/40',
      text: 'text-emerald-200',
      emoji: '✓',
      tooltip: `Fait verifie par ${verification.citedSources.length} source(s) [S${verification.citedSources.join(', S')}]. ${verification.reasoning}`,
    },
    general: {
      label: 'Gen.',
      bg: 'bg-aurora-surface-2/60 border-aurora-border/60',
      text: 'text-aurora-text-dim',
      emoji: '◇',
      tooltip: `Connaissance generale (aucune source directe). ${verification.reasoning}`,
    },
    uncertain: {
      label: 'Incertain',
      bg: 'bg-amber-400/15 border-amber-400/40',
      text: 'text-amber-200',
      emoji: '?',
      tooltip: `Affirmation a verifier toi-meme. ${verification.reasoning}${verification.contradiction ? ` — ${verification.contradiction}` : ''}`,
    },
    contradicted: {
      label: 'Corrige',
      bg: 'bg-rose-400/15 border-rose-400/40',
      text: 'text-rose-200',
      emoji: '!',
      tooltip: `Correction appliquee apres contradiction par les sources. ${verification.contradiction || verification.reasoning}`,
    },
  }
  const conf = styles[verification.status]
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${conf.bg} ${conf.text}`}
      title={conf.tooltip}
    >
      <span aria-hidden>{conf.emoji}</span>
      <span>{conf.label}</span>
    </span>
  )
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightToHtml(text: string, highlights?: string[]): string {
  if (!highlights || highlights.length === 0) return escapeHtml(text)
  const unique = Array.from(new Set(highlights.filter((term) => term && term.length >= 2))).sort(
    (a, b) => b.length - a.length,
  )
  if (unique.length === 0) return escapeHtml(text)
  // Aurora-friendly palette: soft translucent fills that never obscure the text
  // underneath. Each mark gets a readable white color and a subtle underline
  // in the branch color so the highlight remains legible on both dark and
  // print backgrounds (print stylesheet below inverts to black on light).
  const palette = [
    { bg: 'rgba(116,232,255,0.18)', border: 'rgba(116,232,255,0.55)' },   // aurora-cyan
    { bg: 'rgba(167,139,250,0.18)', border: 'rgba(167,139,250,0.55)' },   // violet
    { bg: 'rgba(249,127,61,0.18)', border: 'rgba(249,127,61,0.55)' },     // aurora-orange
    { bg: 'rgba(74,222,128,0.18)', border: 'rgba(74,222,128,0.55)' },     // emerald
    { bg: 'rgba(244,114,182,0.18)', border: 'rgba(244,114,182,0.55)' },   // pink
    { bg: 'rgba(251,191,36,0.18)', border: 'rgba(251,191,36,0.55)' },     // amber
  ]
  const pattern = new RegExp(`(${unique.map(escapeRegExp).join('|')})`, 'gi')
  let colorIndex = 0
  const colorByTerm = new Map<string, typeof palette[number]>()
  for (const term of unique) {
    colorByTerm.set(term.toLowerCase(), palette[colorIndex % palette.length])
    colorIndex += 1
  }
  const escaped = escapeHtml(text)
  return escaped.replace(pattern, (match) => {
    const c = colorByTerm.get(match.toLowerCase()) ?? palette[0]
    return `<mark class="aurora-highlight" style="background:${c.bg};border-bottom:1px solid ${c.border};border-radius:3px;padding:2px 3px;color:rgba(255,255,255,0.95);font-weight:500;">${match}</mark>`
  })
}

function cardToMarkdown(card: Flashcard, subject: string, theme: string): string {
  const lines: string[] = []
  lines.push(`# ${card.front}`)
  if (subject || theme) {
    lines.push(`_${[subject, theme].filter(Boolean).join(' · ')}_`)
  }
  lines.push('')
  if (card.whyItMatters) {
    lines.push(`> **Pourquoi c'est important:** ${card.whyItMatters}`)
    lines.push('')
  }
  if (card.summary) {
    lines.push(`**L'essentiel**`)
    lines.push('')
    lines.push(card.summary)
    lines.push('')
  }
  if (card.deepDive) {
    lines.push(`**Comprendre en profondeur**`)
    lines.push('')
    lines.push(card.deepDive)
    lines.push('')
  }
  if (card.keyPoints && card.keyPoints.length > 0) {
    lines.push('**Points clés**')
    lines.push('')
    for (const point of card.keyPoints) {
      lines.push(`- **${point.label}**${point.detail ? ` — ${point.detail}` : ''}`)
    }
    lines.push('')
  }
  if (card.formula) {
    lines.push(`**Formule** — \`${card.formula}\``)
    lines.push('')
  }
  if (card.quote) {
    lines.push(`> « ${card.quote} »${card.quoteAuthor ? ` — ${card.quoteAuthor}` : ''}`)
    lines.push('')
  }
  if (card.dates && card.dates.length > 0) {
    lines.push('**Chronologie**')
    lines.push('')
    for (const entry of card.dates) {
      lines.push(`- **${entry.year}** · ${entry.event}`)
    }
    lines.push('')
  }
  if (card.example) {
    lines.push(`**Exemple** — ${card.example}`)
    lines.push('')
  }
  if (card.mnemonic) {
    lines.push(`**Astuce mémo** — ${card.mnemonic}`)
    lines.push('')
  }
  if (card.highlights && card.highlights.length > 0) {
    lines.push(`**À surligner:** ${card.highlights.join(' · ')}`)
    lines.push('')
  }
  if (card.tags.length > 0) {
    lines.push(`**Tags:** ${card.tags.map((t) => `#${t}`).join(' ')}`)
  }
  return lines.join('\n')
}

function deckToMarkdown(deck: FlashcardDeck, cards: Flashcard[]): string {
  const header = [
    `# ${deck.subject}${deck.theme ? ` — ${deck.theme}` : ''}`,
    `_Niveau ${deck.level} · ${cards.length} fiche(s) · genere le ${new Date(deck.createdAt).toLocaleDateString('fr-FR')}_`,
    '',
    '---',
    '',
  ].join('\n')
  const body = cards
    .map((card) => cardToMarkdown(card, deck.subject, deck.theme))
    .join('\n\n---\n\n')
  return header + body + '\n'
}

function cardSectionsHtml(card: Flashcard, subjectMeta: { label: string; emoji: string }): string {
  const blocks: string[] = []
  const highlights = card.highlights
  const emoji = subjectMeta.emoji.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  blocks.push(
    `<div class="card-meta">${emoji} ${escapeHtml(subjectMeta.label)}${
      card.tags.length > 0 ? ` · ${card.tags.map((t) => `#${escapeHtml(t)}`).join(' ')}` : ''
    }</div>`,
  )
  blocks.push(`<h2>${escapeHtml(card.front)}</h2>`)
  if (card.whyItMatters) {
    blocks.push(
      `<aside class="why"><strong>Pourquoi c'est important</strong><p>${highlightToHtml(card.whyItMatters, highlights)}</p></aside>`,
    )
  }
  if (card.summary) {
    blocks.push(
      `<section class="section"><h3>L'essentiel</h3><p>${highlightToHtml(card.summary, highlights)}</p></section>`,
    )
  }
  if (card.deepDive) {
    const paragraphs = card.deepDive
      .split(/\n\n+/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean)
      .map((paragraph) => `<p>${highlightToHtml(paragraph, highlights)}</p>`)
      .join('')
    blocks.push(`<section class="section deep"><h3>Comprendre en profondeur</h3>${paragraphs}</section>`)
  }
  if (card.keyPoints && card.keyPoints.length > 0) {
    const items = card.keyPoints
      .map(
        (point) =>
          `<li><strong>${highlightToHtml(point.label, highlights)}</strong>${
            point.detail ? `<span> — ${highlightToHtml(point.detail, highlights)}</span>` : ''
          }</li>`,
      )
      .join('')
    blocks.push(`<section class="section keypoints"><h3>Points clés</h3><ol>${items}</ol></section>`)
  }
  if (card.formula) {
    blocks.push(
      `<aside class="formula"><strong>Formule</strong><code>${escapeHtml(card.formula)}</code></aside>`,
    )
  }
  if (card.quote) {
    blocks.push(
      `<figure class="quote"><blockquote>« ${escapeHtml(card.quote)} »</blockquote>${
        card.quoteAuthor ? `<figcaption>— ${escapeHtml(card.quoteAuthor)}</figcaption>` : ''
      }</figure>`,
    )
  }
  if (card.dates && card.dates.length > 0) {
    const items = card.dates
      .map((entry) => `<li><strong>${escapeHtml(entry.year)}</strong> · ${escapeHtml(entry.event)}</li>`)
      .join('')
    blocks.push(`<section class="section chrono"><h3>Chronologie</h3><ul>${items}</ul></section>`)
  }
  if (card.example) {
    blocks.push(
      `<aside class="example"><strong>Exemple</strong><p>${highlightToHtml(card.example, highlights)}</p></aside>`,
    )
  }
  if (card.mnemonic) {
    blocks.push(
      `<aside class="mnemo"><strong>Astuce mémo</strong><p>${escapeHtml(card.mnemonic)}</p></aside>`,
    )
  }
  return `<article class="card">${blocks.join('')}</article>`
}

const EXPORT_CSS = `
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  background: #f8fafc;
  color: #0f172a;
  line-height: 1.55;
}
.deck-header {
  max-width: 840px;
  margin: 0 auto 24px;
  padding: 24px 28px;
  background: linear-gradient(135deg, #ec4899, #8b5cf6);
  color: white;
  border-radius: 18px;
  box-shadow: 0 12px 32px rgba(139,92,246,0.2);
}
.deck-header h1 { margin: 0; font-size: 26px; letter-spacing: -0.01em; }
.deck-header p { margin: 6px 0 0; opacity: 0.85; font-size: 13px; }
.deck { max-width: 840px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
.card {
  background: white;
  border-radius: 20px;
  padding: 28px 32px;
  box-shadow: 0 6px 24px rgba(15,23,42,0.08);
  border: 1px solid rgba(15,23,42,0.06);
  page-break-inside: avoid;
}
.card-meta {
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #64748b;
  font-weight: 600;
}
.card h2 {
  margin: 10px 0 16px;
  font-size: 24px;
  color: #0f172a;
}
.card h3 {
  margin: 18px 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #6366f1;
  font-weight: 700;
}
.card p { margin: 6px 0; font-size: 14px; color: #1e293b; }
.card .section { margin-top: 10px; }
.card .section.deep { background: #f1f5f9; border-radius: 14px; padding: 16px 18px; }
.card ol, .card ul { padding-left: 24px; margin: 6px 0; }
.card li { margin: 4px 0; font-size: 14px; }
.card .why {
  margin-top: 6px;
  border-left: 3px solid #ec4899;
  background: #fdf2f8;
  padding: 10px 14px;
  border-radius: 8px;
}
.card .why strong { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: #be185d; }
.card .why p { margin-top: 4px; font-style: italic; color: #831843; }
.card .formula {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #e0f2fe;
  border-left: 4px solid #0284c7;
}
.card .formula strong { font-size: 11px; letter-spacing: 0.2em; color: #075985; }
.card .formula code { display: block; margin-top: 4px; font-family: "JetBrains Mono", "Fira Code", monospace; font-size: 14px; color: #0c4a6e; }
.card .quote {
  margin: 14px 0 0;
  padding: 14px 18px;
  border-radius: 12px;
  background: #fdf4ff;
  border-left: 4px solid #a855f7;
}
.card .quote blockquote { margin: 0; font-style: italic; color: #581c87; }
.card .quote figcaption { margin-top: 6px; font-size: 12px; color: #7e22ce; letter-spacing: 0.1em; text-transform: uppercase; }
.card .chrono { border-radius: 12px; background: #fffbeb; padding: 12px 16px; }
.card .chrono li strong { color: #b45309; }
.card .example {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #ecfdf5;
  border-left: 4px solid #10b981;
}
.card .example strong { font-size: 11px; letter-spacing: 0.2em; color: #047857; }
.card .example p { margin-top: 4px; color: #064e3b; }
.card .mnemo {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #fff7ed;
  border-left: 4px solid #f97316;
}
.card .mnemo strong { font-size: 11px; letter-spacing: 0.2em; color: #c2410c; }
.card .mnemo p { margin-top: 4px; color: #7c2d12; }
mark { padding: 0 3px; border-radius: 3px; font-weight: 500; color: inherit; }
@media print {
  body { background: white; padding: 0; }
  .deck-header { box-shadow: none; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .card { box-shadow: none; border: 1px solid #e2e8f0; break-inside: avoid; page-break-inside: avoid; }
  mark { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
@media (prefers-color-scheme: dark) {
  body { background: #0f172a; color: #e2e8f0; }
  .card { background: #1e293b; border-color: rgba(255,255,255,0.08); }
  .card p { color: #cbd5e1; }
  .card h2 { color: #f1f5f9; }
}
`

function buildDeckHtml(deck: FlashcardDeck, cards: Flashcard[], subjectMeta: { label: string; emoji: string }): string {
  const title = `${deck.subject}${deck.theme ? ` — ${deck.theme}` : ''}`
  const generatedDate = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })
  // Add page-break-after on all but the last card so print yields one card per page
  const cardsHtml = cards.map((card, index) => {
    const inner = cardSectionsHtml(card, subjectMeta)
    return index < cards.length - 1 ? inner.replace('<article class="card">', '<article class="card page-break">') : inner
  }).join('\n')
  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>${EXPORT_CSS}
.page-break { break-after: page; page-break-after: always; }
</style>
</head>
<body>
<header class="deck-header">
  <h1>${escapeHtml(title)}</h1>
  <p>Niveau ${escapeHtml(deck.level)} · ${cards.length} fiche(s) · Généré le ${generatedDate} par Aurora Académie</p>
</header>
<main class="deck">${cardsHtml}</main>
</body>
</html>`
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function openPrintWindow(html: string) {
  const win = window.open('', '_blank', 'noopener,noreferrer,width=900,height=1200')
  if (!win) {
    downloadBlob(html, 'fiches.html', 'text/html;charset=utf-8')
    return
  }
  win.document.open()
  win.document.write(html)
  win.document.close()
  win.focus()
  setTimeout(() => {
    try {
      win.print()
    } catch {
      // Impression bloquee — la fenetre reste ouverte pour impression manuelle
    }
  }, 400)
}

function sanitizeFilename(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'fiches'
}

function normalizeFlashcardDraft(draft: FlashcardDraft) {
  const title = (draft.title ?? draft.front ?? '').trim().slice(0, 160)
  const summary = (draft.summary ?? draft.back ?? '').trim().slice(0, 620)
  if (!title || !summary) return null
  const deepDive = draft.deepDive ? draft.deepDive.trim().slice(0, 1200) : undefined
  const whyItMatters = draft.whyItMatters ? draft.whyItMatters.trim().slice(0, 360) : undefined

  const keyPoints = Array.isArray(draft.keyPoints)
    ? draft.keyPoints
        .map((point) => {
          if (typeof point === 'string') return { label: point.trim().slice(0, 140) }
          if (point && typeof point === 'object' && point.label) {
            return {
              label: String(point.label).trim().slice(0, 140),
              detail: point.detail ? String(point.detail).trim().slice(0, 240) : undefined,
            }
          }
          return null
        })
        .filter((point): point is { label: string; detail?: string } => Boolean(point?.label))
        .slice(0, 8)
    : undefined

  const highlights = Array.isArray(draft.highlights)
    ? Array.from(
        new Set(
          draft.highlights
            .map((term) => String(term).trim())
            .filter((term) => term.length >= 2 && term.length <= 60),
        ),
      ).slice(0, 10)
    : undefined

  const dates = Array.isArray(draft.dates)
    ? draft.dates
        .map((entry) => ({
          year: entry?.year ? String(entry.year).trim().slice(0, 12) : '',
          event: entry?.event ? String(entry.event).trim().slice(0, 160) : '',
        }))
        .filter((entry) => entry.year && entry.event)
        .slice(0, 8)
    : undefined

  const tags = Array.isArray(draft.tags)
    ? Array.from(
        new Set(
          draft.tags
            .map((tag) => String(tag).trim())
            .filter((tag) => tag.length > 0 && tag.length <= 32),
        ),
      ).slice(0, 4)
    : []

  return {
    kind: 'revision' as const,
    front: title,
    back: summary,
    summary,
    deepDive,
    whyItMatters,
    keyPoints: keyPoints && keyPoints.length > 0 ? keyPoints : undefined,
    highlights: highlights && highlights.length > 0 ? highlights : undefined,
    mnemonic: draft.mnemonic ? draft.mnemonic.trim().slice(0, 240) : undefined,
    example: draft.example ? draft.example.trim().slice(0, 320) : undefined,
    formula: draft.formula ? draft.formula.trim().slice(0, 200) : undefined,
    quote: draft.quote ? draft.quote.trim().slice(0, 240) : undefined,
    quoteAuthor: draft.quoteAuthor ? draft.quoteAuthor.trim().slice(0, 80) : undefined,
    dates: dates && dates.length > 0 ? dates : undefined,
    hint: draft.hint ? draft.hint.trim().slice(0, 180) : undefined,
    tags,
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const HIGHLIGHT_PALETTE = [
  { bg: 'rgba(116,232,255,0.18)', border: 'rgba(116,232,255,0.55)' },   // aurora-cyan
  { bg: 'rgba(167,139,250,0.18)', border: 'rgba(167,139,250,0.55)' },   // violet
  { bg: 'rgba(249,127,61,0.18)', border: 'rgba(249,127,61,0.55)' },     // aurora-orange
  { bg: 'rgba(74,222,128,0.18)', border: 'rgba(74,222,128,0.55)' },     // emerald
  { bg: 'rgba(244,114,182,0.18)', border: 'rgba(244,114,182,0.55)' },   // pink
  { bg: 'rgba(251,191,36,0.18)', border: 'rgba(251,191,36,0.55)' },     // amber
]

function renderHighlightedText(text: string, highlights?: string[]): ReactNode[] {
  if (!highlights || highlights.length === 0) return [text]
  const unique = Array.from(new Set(highlights.filter((term) => term && term.length >= 2))).sort(
    (a, b) => b.length - a.length,
  )
  if (unique.length === 0) return [text]
  const paletteByTerm = new Map<string, typeof HIGHLIGHT_PALETTE[number]>()
  unique.forEach((term, index) => {
    paletteByTerm.set(term.toLowerCase(), HIGHLIGHT_PALETTE[index % HIGHLIGHT_PALETTE.length])
  })
  const pattern = new RegExp(`(${unique.map(escapeRegExp).join('|')})`, 'gi')
  const parts = text.split(pattern)
  return parts.map((part, index) => {
    const lower = part.toLowerCase()
    const hl = paletteByTerm.get(lower)
    if (!hl) return <span key={`t-${index}`}>{part}</span>
    return (
      <mark
        key={`hl-${index}`}
        className="aurora-highlight"
        style={{
          background: hl.bg,
          borderBottom: `1px solid ${hl.border}`,
          borderRadius: '3px',
          padding: '2px 3px',
          color: 'rgba(255,255,255,0.95)',
          fontWeight: 500,
        }}
      >
        {part}
      </mark>
    )
  })
}

function renderParagraphs(text: string, highlights?: string[]): ReactNode[] {
  return text
    .split(/\n\n+/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0)
    .map((paragraph, index) => (
      <p key={`par-${index}`} className="text-sm leading-relaxed text-aurora-text-dim">
        {renderHighlightedText(paragraph, highlights)}
      </p>
    ))
}

const MINDMAP_BRANCH_COLORS = [
  { stroke: '#06b6d4', fill: 'rgba(6,182,212,0.15)', glow: 'rgba(6,182,212,0.5)' },
  { stroke: '#8b5cf6', fill: 'rgba(139,92,246,0.15)', glow: 'rgba(139,92,246,0.5)' },
  { stroke: '#10b981', fill: 'rgba(16,185,129,0.15)', glow: 'rgba(16,185,129,0.5)' },
  { stroke: '#f97316', fill: 'rgba(249,115,22,0.15)', glow: 'rgba(249,115,22,0.5)' },
  { stroke: '#f43f5e', fill: 'rgba(244,63,94,0.15)', glow: 'rgba(244,63,94,0.5)' },
  { stroke: '#0ea5e9', fill: 'rgba(14,165,233,0.15)', glow: 'rgba(14,165,233,0.5)' },
  { stroke: '#a855f7', fill: 'rgba(168,85,247,0.15)', glow: 'rgba(168,85,247,0.5)' },
  { stroke: '#eab308', fill: 'rgba(234,179,8,0.15)', glow: 'rgba(234,179,8,0.5)' },
]

const MindmapSvg = memo(function MindmapSvg({
  title,
  points,
  subject,
  notionContext,
}: {
  title: string
  points: KeyPoint[]
  accentColor?: string
  subject?: string
  notionContext?: string
}) {
  const primaryNodes = useMemo(() => {
    const count = Math.min(points.length, 10)
    if (count < 3) return []
    const width = 900
    const height = 580
    const cx = width / 2
    const cy = height / 2
    const radiusX = 340
    const radiusY = 215
    return points.slice(0, count).map((point, index) => {
      const angle = (index / count) * 2 * Math.PI - Math.PI / 2
      const x = cx + radiusX * Math.cos(angle)
      const y = cy + radiusY * Math.sin(angle)
      const detailText = typeof point.detail === 'string' ? point.detail.trim() : ''
      const subBranches: string[] = detailText
        ? detailText
            .split(/(?:\. |[,;]|\n)+/)
            .map((segment) => segment.trim())
            .filter((segment) => segment.length >= 6 && segment.length <= 90)
            .slice(0, 3)
        : []
      const color = MINDMAP_BRANCH_COLORS[index % MINDMAP_BRANCH_COLORS.length]
      return { point, index, x, y, angle, cx, cy, width, height, subBranches, detailText, color }
    })
  }, [points])

  const { mainModel } = useAppStore()
  const [activeIndex, setActiveIndex] = useState<number | null>(null)

  if (primaryNodes.length === 0) return null
  const { width, height, cx, cy } = primaryNodes[0]
  const activeNode = activeIndex !== null ? primaryNodes[activeIndex] : null

  return (
    <div
      className="mt-5 overflow-hidden rounded-2xl p-4"
      style={{
        background: 'rgba(8,14,30,0.7)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.08)',
        boxShadow: '0 4px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <p
          className="text-[10px] font-semibold uppercase tracking-[0.22em]"
          style={{ background: 'linear-gradient(90deg,#06b6d4,#8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
        >
          Carte mentale
        </p>
        <p className="text-[10px] text-aurora-text-dim">
          {primaryNodes.length} branche{primaryNodes.length > 1 ? 's' : ''} · clic sur un nœud = détail
        </p>
      </div>
      <div className="mt-3 w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-auto w-full min-w-[40rem]"
          onClick={() => setActiveIndex(null)}
          style={{ overflow: 'visible' }}
        >
          <defs>
            <style>{`
              @keyframes mmFadeIn { from { opacity:0; transform:scale(0.6); } to { opacity:1; transform:scale(1); } }
              @keyframes mmPulse { 0%,100% { filter:drop-shadow(0 0 6px var(--mm-glow,#06b6d4)); } 50% { filter:drop-shadow(0 0 14px var(--mm-glow,#06b6d4)); } }
              @keyframes mmDash { to { stroke-dashoffset:-24; } }
              .mm-node { animation: mmFadeIn 0.4s ease both; }
              .mm-active { animation: mmPulse 2s ease-in-out infinite; }
            `}</style>
            <radialGradient id="mm-center-fill" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.6" />
              <stop offset="60%" stopColor="#8b5cf6" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.05" />
            </radialGradient>
            <filter id="mm-glow-soft" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="mm-glow-strong" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Curved branch edges */}
          {primaryNodes.map((node) => {
            const dx = node.x - cx
            const dy = node.y - cy
            const perpX = -dy * 0.18
            const perpY = dx * 0.18
            const cp1x = cx + dx * 0.35 + perpX
            const cp1y = cy + dy * 0.35 + perpY
            const cp2x = cx + dx * 0.65 - perpX
            const cp2y = cy + dy * 0.65 - perpY
            const isActive = activeIndex === node.index
            const dim = activeIndex !== null && !isActive
            return (
              <path
                key={`edge-${node.index}`}
                d={`M ${cx} ${cy} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${node.x} ${node.y}`}
                fill="none"
                stroke={node.color.stroke}
                strokeOpacity={dim ? 0.1 : isActive ? 0.9 : 0.45}
                strokeWidth={isActive ? 2.2 : 1.5}
                strokeDasharray="6 4"
                strokeLinecap="round"
                style={isActive ? { animation: 'mmDash 1.2s linear infinite', strokeDashoffset: 0 } : undefined}
              />
            )
          })}

          {/* Center node */}
          <circle cx={cx} cy={cy} r={82} fill="url(#mm-center-fill)" />
          <circle cx={cx} cy={cy} r={82} fill="none" stroke="rgba(6,182,212,0.6)" strokeWidth="1.5" filter="url(#mm-glow-soft)" />
          <circle cx={cx} cy={cy} r={82} fill="none" stroke="rgba(139,92,246,0.3)" strokeWidth="0.8" />
          <foreignObject x={cx - 74} y={cy - 32} width={148} height={64}>
            <div
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: '100%', textAlign: 'center', fontFamily: 'inherit',
                fontSize: '12px', fontWeight: 700, lineHeight: 1.25,
                background: 'linear-gradient(135deg,#06b6d4,#a78bfa)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                padding: '0 4px',
              }}
            >
              {title.length > 52 ? `${title.slice(0, 50)}…` : title}
            </div>
          </foreignObject>

          {/* Branch nodes */}
          {primaryNodes.map((node) => {
            const label = node.point.label.length > 36 ? `${node.point.label.slice(0, 34)}…` : node.point.label
            const isActive = activeIndex === node.index
            const dim = activeIndex !== null && !isActive
            return (
              <g
                key={`node-${node.index}`}
                className={`mm-node ${isActive ? 'mm-active' : ''}`}
                onClick={(event) => { event.stopPropagation(); setActiveIndex(isActive ? null : node.index) }}
                style={{
                  cursor: 'pointer',
                  opacity: dim ? 0.25 : 1,
                  animationDelay: `${node.index * 0.08}s`,
                  ['--mm-glow' as string]: node.color.glow,
                }}
              >
                {/* Node glow ring */}
                <circle
                  cx={node.x} cy={node.y} r={52}
                  fill={node.color.fill}
                  stroke={node.color.stroke}
                  strokeOpacity={isActive ? 1 : 0.6}
                  strokeWidth={isActive ? 2 : 1.2}
                  filter={isActive ? 'url(#mm-glow-strong)' : 'url(#mm-glow-soft)'}
                />
                {/* Inner circle subtle */}
                <circle
                  cx={node.x} cy={node.y} r={50}
                  fill="rgba(8,14,30,0.65)"
                  stroke={node.color.stroke}
                  strokeOpacity="0.2"
                  strokeWidth="0.5"
                />
                <foreignObject x={node.x - 44} y={node.y - 28} width={88} height={56}>
                  <div
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      height: '100%', textAlign: 'center', fontFamily: 'inherit',
                      fontSize: '10px', fontWeight: 600, lineHeight: 1.2,
                      color: isActive ? node.color.stroke : '#e2e8f0',
                      padding: '0 4px',
                      transition: 'color 0.2s',
                    }}
                  >
                    {label}
                  </div>
                </foreignObject>

                {/* Sub-branches */}
                {node.subBranches.map((branch, branchIndex) => {
                  const subAngle = node.angle + (branchIndex - (node.subBranches.length - 1) / 2) * 0.24
                  const subRadius = 98
                  const subX = node.x + subRadius * Math.cos(subAngle)
                  const subY = node.y + subRadius * Math.sin(subAngle)
                  const textWidth = 112
                  return (
                    <g key={`sub-${node.index}-${branchIndex}`}>
                      <line
                        x1={node.x} y1={node.y} x2={subX} y2={subY}
                        stroke={node.color.stroke} strokeOpacity="0.3" strokeWidth="0.9"
                        strokeDasharray="3 3"
                      />
                      <foreignObject x={subX - textWidth / 2} y={subY - 14} width={textWidth} height={30}>
                        <div
                          style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            height: '100%', textAlign: 'center', fontFamily: 'inherit',
                            fontSize: '8.5px', lineHeight: 1.15,
                            color: node.color.stroke, opacity: 0.75,
                            padding: '2px 4px',
                          }}
                        >
                          {branch.length > 50 ? `${branch.slice(0, 48)}…` : branch}
                        </div>
                      </foreignObject>
                    </g>
                  )
                })}
              </g>
            )
          })}
        </svg>
      </div>

      {activeNode && (
        <div
          className="mt-3 rounded-xl p-3"
          style={{
            background: `linear-gradient(135deg, ${activeNode.color.fill}, rgba(8,14,30,0.5))`,
            border: `1px solid ${activeNode.color.stroke}40`,
            boxShadow: `0 0 20px ${activeNode.color.glow}30`,
          }}
        >
          <p className="text-[11px] uppercase tracking-[0.18em]" style={{ color: activeNode.color.stroke }}>Branche</p>
          <p className="mt-1 text-sm font-semibold text-aurora-text">{activeNode.point.label}</p>
          {activeNode.detailText ? (
            <p className="mt-2 text-xs leading-relaxed text-aurora-text-dim">{activeNode.detailText}</p>
          ) : (
            <p className="mt-2 text-xs text-aurora-text-dim">Pas de détail pour cette branche — creuse la notion ci-dessous.</p>
          )}
          <AskAboutContentBox
            className="mt-3"
            label="Creuser cette notion"
            subject={subject || title}
            model={mainModel}
            context={[
              `Sujet general: ${subject || title}`,
              `Branche: ${activeNode.point.label}`,
              activeNode.detailText ? `Detail: ${activeNode.detailText}` : '',
              notionContext ? `Contexte du contenu: ${notionContext}` : '',
            ].filter(Boolean).join('\n')}
            placeholder="Ex: donne un exemple concret de cette branche / comment c est lie au reste du sujet ?"
          />
        </div>
      )}
    </div>
  )
})

const SUBJECT_LABEL: Record<SubjectKind, { label: string; emoji: string; accent: string }> = {
  philo: { label: 'Philosophie', emoji: '🧠', accent: 'from-purple-500/40 via-fuchsia-400/20 to-transparent' },
  histoire: { label: 'Histoire', emoji: '📜', accent: 'from-amber-500/40 via-orange-400/20 to-transparent' },
  geo: { label: 'Geographie', emoji: '🗺️', accent: 'from-emerald-500/40 via-teal-400/20 to-transparent' },
  maths: { label: 'Mathematiques', emoji: '∑', accent: 'from-sky-500/40 via-cyan-400/20 to-transparent' },
  science: { label: 'Sciences', emoji: '🧪', accent: 'from-lime-500/40 via-emerald-400/20 to-transparent' },
  langue: { label: 'Langue', emoji: '🗣️', accent: 'from-pink-500/40 via-rose-400/20 to-transparent' },
  litterature: { label: 'Litterature', emoji: '📚', accent: 'from-indigo-500/40 via-violet-400/20 to-transparent' },
  informatique: { label: 'Informatique', emoji: '</>', accent: 'from-cyan-500/40 via-blue-400/20 to-transparent' },
  economie: { label: 'Economie', emoji: '📈', accent: 'from-yellow-500/40 via-amber-400/20 to-transparent' },
  art: { label: 'Arts', emoji: '🎨', accent: 'from-rose-500/40 via-pink-400/20 to-transparent' },
  general: { label: 'General', emoji: '✦', accent: 'from-aurora-accent/30 via-aurora-accent/10 to-transparent' },
}

function DeckIndexModal({
  deck,
  cards,
  onClose,
  onStudyCard,
  onDeleteCard,
}: {
  deck: FlashcardDeck
  cards: Flashcard[]
  onClose: () => void
  onStudyCard: (cardId: string) => void
  onDeleteCard: (cardId: string) => void
}) {
  const [search, setSearch] = useState('')
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<'index' | 'box' | 'accuracy'>('index')
  const [showMindMap, setShowMindMap] = useState(false)
  const mindMap = useMemo(() => buildDeckMindMap(deck, cards), [deck, cards])
  const mindMapStats = useMemo(() => describeDeckMindMap(mindMap), [mindMap])
  // v74: judge la qualite du mind map (theme distribution, keypoints,
  // diversite tags, density). Affiche pourquoi un deck a un mind map plat.
  const mindMapQuality = useMemo(() => evaluateMindMapQuality(mindMap, cards), [mindMap, cards])
  // v77: deck-level verification summary so the user sees at a glance how
  // many cards passed fact-check vs got flagged. Without this badge the
  // per-card verification dots are visible but the aggregate trust signal
  // ('5 cartes fact-checked / 12 sans source / 1 contredite') is buried.
  const verificationSummary = useMemo(() => {
    const total = cards.length
    const buckets = { verified: 0, general: 0, uncertain: 0, contradicted: 0, none: 0 }
    for (const card of cards) {
      const status = card.verification?.status
      if (status === 'verified') buckets.verified++
      else if (status === 'general') buckets.general++
      else if (status === 'uncertain') buckets.uncertain++
      else if (status === 'contradicted') buckets.contradicted++
      else buckets.none++
    }
    const trustedPct = total > 0 ? Math.round(((buckets.verified + buckets.general) / total) * 100) : 0
    return { ...buckets, total, trustedPct }
  }, [cards])

  const tags = useMemo(() => {
    const set = new Set<string>()
    for (const card of cards) for (const tag of card.tags) set.add(tag)
    return Array.from(set).slice(0, 16)
  }, [cards])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    let list = cards.filter((card) => {
      if (activeTag && !card.tags.includes(activeTag)) return false
      if (!needle) return true
      const haystack = `${card.front} ${card.summary ?? card.back} ${card.tags.join(' ')}`.toLowerCase()
      return haystack.includes(needle)
    })
    if (sortKey === 'box') {
      list = [...list].sort((a, b) => b.box - a.box)
    } else if (sortKey === 'accuracy') {
      const accuracy = (card: Flashcard) => {
        const total = card.timesCorrect + card.timesWrong
        return total === 0 ? -1 : card.timesCorrect / total
      }
      list = [...list].sort((a, b) => accuracy(b) - accuracy(a))
    }
    return list
  }, [activeTag, cards, search, sortKey])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/65 backdrop-blur-sm p-4">
      <div className="flex h-full max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-aurora-border bg-aurora-surface shadow-2xl">
        <div className="border-b border-aurora-border/40 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.22em] text-aurora-text-dim">Deck · {cards.length} fiche(s)</p>
              <h2 className="mt-1 text-lg font-semibold text-aurora-text">{deck.subject}</h2>
              {deck.theme && <p className="text-xs text-aurora-text-dim">{deck.theme}</p>}
            </div>
            <button
              onClick={onClose}
              className="rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text"
            >
              Fermer (Esc)
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Recherche dans titre, resume, tags..."
              className="min-w-0 flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
            />
            <select
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as typeof sortKey)}
              className="rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-[11px] text-aurora-text outline-none"
            >
              <option value="index">Ordre deck</option>
              <option value="box">Boite Leitner</option>
              <option value="accuracy">Taux de reussite</option>
            </select>
            {cards.length > 0 && (
              <button
                onClick={() => setShowMindMap((v) => !v)}
                className={`rounded-xl border px-3 py-2 text-[11px] transition-colors ${
                  showMindMap
                    ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent'
                    : 'border-aurora-border bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                }`}
                title={`Carte mentale (${mindMapStats.themes} themes · ${mindMapStats.cards} fiches · ${mindMapStats.points} points)`}
              >
                <MapIcon size={12} className="inline mr-1.5" />
                {showMindMap ? 'Liste' : 'Carte mentale'}
              </button>
            )}
          </div>
          {tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              <button
                onClick={() => setActiveTag(null)}
                className={`rounded-full border px-2.5 py-0.5 text-[10px] ${
                  activeTag == null ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border text-aurora-text-dim hover:text-aurora-text'
                }`}
              >
                Tous
              </button>
              {tags.map((tag) => (
                <button
                  key={tag}
                  onClick={() => setActiveTag((value) => (value === tag ? null : tag))}
                  className={`rounded-full border px-2.5 py-0.5 text-[10px] ${
                    activeTag === tag ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border text-aurora-text-dim hover:text-aurora-text'
                  }`}
                >
                  #{tag}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {/* v77: trust panel - always visible (independent of mind map toggle) */}
          {cards.length > 0 && (
            <details className="mb-3 rounded-xl border border-aurora-border/50 bg-aurora-surface-2/40 px-3 py-2">
              <summary className="cursor-pointer flex items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span>{verificationSummary.contradicted > 0 ? '⚠' : verificationSummary.verified >= verificationSummary.total / 2 ? '✓' : '◐'}</span>
                  <span className="text-aurora-text">Confiance fact-check</span>
                  <span className={`font-semibold ${
                    verificationSummary.contradicted > 0
                      ? 'text-rose-300'
                      : verificationSummary.trustedPct >= 75
                        ? 'text-emerald-300'
                        : verificationSummary.trustedPct >= 50
                          ? 'text-amber-300'
                          : 'text-rose-300'
                  }`}>
                    {verificationSummary.trustedPct}%
                  </span>
                </div>
                <span className="text-[10px] text-aurora-text-muted">
                  {verificationSummary.verified} verifie · {verificationSummary.uncertain + verificationSummary.contradicted} a verifier
                </span>
              </summary>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[10.5px] text-aurora-text-muted sm:grid-cols-5">
                <div className="rounded bg-emerald-400/10 px-2 py-1 text-emerald-200">verifie {verificationSummary.verified}</div>
                <div className="rounded bg-sky-400/10 px-2 py-1 text-sky-200">general {verificationSummary.general}</div>
                <div className="rounded bg-amber-400/10 px-2 py-1 text-amber-200">incertain {verificationSummary.uncertain}</div>
                <div className="rounded bg-rose-400/10 px-2 py-1 text-rose-200">corrige {verificationSummary.contradicted}</div>
                <div className="rounded bg-zinc-400/10 px-2 py-1 text-zinc-300">sans badge {verificationSummary.none}</div>
              </div>
            </details>
          )}
          {showMindMap && cards.length > 0 && (
            <div className="mb-4 space-y-3">
              <DeckMindMap root={mindMap} onCardSelect={onStudyCard} />
              <p className="text-[11px] text-aurora-text-dim">
                Clique un noeud carte pour ouvrir la fiche correspondante. Glisse pour panner, molette pour zoomer.
              </p>
              <details className="rounded-xl border border-aurora-border/50 bg-aurora-surface-2/40 px-3 py-2">
                <summary className="cursor-pointer flex items-center justify-between gap-2 text-[11px]">
                  <div className="flex items-center gap-2">
                    <span>{mindMapQuality.score >= 80 ? '✨' : mindMapQuality.score >= 60 ? '🧠' : '⚠'}</span>
                    <span className="text-aurora-text">Qualite mind map</span>
                    <span className={`font-semibold ${mindMapQuality.score >= 80 ? 'text-emerald-300' : mindMapQuality.score >= 60 ? 'text-amber-300' : 'text-rose-300'}`}>
                      {mindMapQuality.score}/100
                    </span>
                  </div>
                  <span className="text-[10px] text-aurora-text-muted">
                    {mindMapQuality.themes} themes · {mindMapQuality.cards} cartes
                  </span>
                </summary>
                {(mindMapQuality.diagnostics.length > 0 || mindMapQuality.recommendations.length > 0) && (
                  <div className="mt-2 space-y-2 text-[10.5px]">
                    {mindMapQuality.diagnostics.length > 0 && (
                      <div>
                        <div className="text-amber-300 font-semibold mb-1">Diagnostics</div>
                        <ul className="space-y-0.5 pl-3 list-disc text-aurora-text-muted">
                          {mindMapQuality.diagnostics.map((d, i) => <li key={i}>{d}</li>)}
                        </ul>
                      </div>
                    )}
                    {mindMapQuality.recommendations.length > 0 && (
                      <div>
                        <div className="text-cyan-300 font-semibold mb-1">Pistes</div>
                        <ul className="space-y-0.5 pl-3 list-disc text-aurora-text-muted">
                          {mindMapQuality.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </details>
            </div>
          )}
          {filtered.length === 0 ? (
            <p className="py-12 text-center text-xs text-aurora-text-dim">Aucune fiche ne correspond a ces criteres.</p>
          ) : (
            <ul className="space-y-2">
              {filtered.map((card) => {
                const total = card.timesCorrect + card.timesWrong
                const accuracy = total === 0 ? null : Math.round((card.timesCorrect / total) * 100)
                const summaryText = card.summary ?? card.back
                return (
                  <li
                    key={card.id}
                    className="rounded-2xl border border-aurora-border/50 bg-aurora-surface-2/70 px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-aurora-text truncate">{card.front}</p>
                        <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-aurora-text-dim">{summaryText}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-aurora-text-dim">
                          <span className="rounded bg-aurora-accent/15 px-1.5 py-0.5 text-aurora-accent">Boite {card.box}/5</span>
                          {card.verification && (() => {
                            const v = card.verification
                            const styles: Record<typeof v.status, { label: string; cls: string }> = {
                              verified: { label: '✓ sourcee', cls: 'bg-emerald-400/15 text-emerald-200 border border-emerald-400/30' },
                              general: { label: '◇ gen.', cls: 'bg-aurora-surface-2/60 text-aurora-text-dim border border-aurora-border/40' },
                              uncertain: { label: '? incertain', cls: 'bg-amber-400/15 text-amber-200 border border-amber-400/30' },
                              contradicted: { label: '! corrige', cls: 'bg-rose-400/15 text-rose-200 border border-rose-400/30' },
                            }
                            const conf = styles[v.status]
                            return (
                              <span
                                className={`rounded px-1.5 py-0.5 ${conf.cls}`}
                                title={`${v.reasoning}${v.contradiction ? ` — ${v.contradiction}` : ''}`}
                              >
                                {conf.label}
                              </span>
                            )
                          })()}
                          {accuracy != null && (
                            <span className={`rounded px-1.5 py-0.5 ${accuracy >= 70 ? 'bg-aurora-green/15 text-aurora-green' : accuracy >= 40 ? 'bg-aurora-accent/10 text-aurora-accent' : 'bg-aurora-red/10 text-aurora-red'}`}>
                              {accuracy}% ({total} reponses)
                            </span>
                          )}
                          {card.tags.slice(0, 3).map((tag, tagIndex) => (
                            <span key={`${tag}-${tagIndex}`} className="rounded border border-aurora-border/50 px-1.5 py-0.5">
                              #{tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col gap-1.5">
                        <button
                          onClick={() => {
                            onStudyCard(card.id)
                            onClose()
                          }}
                          className="rounded-lg gradient-accent px-3 py-1 text-[10px] font-medium text-white"
                        >
                          Etudier
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Supprimer la fiche "${card.front.slice(0, 60)}" ?`)) {
                              onDeleteCard(card.id)
                            }
                          }}
                          className="rounded-lg border border-aurora-border bg-aurora-surface-2 px-3 py-1 text-[10px] text-aurora-text-dim hover:text-aurora-red hover:border-aurora-red/30"
                        >
                          Supprimer
                        </button>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function FullDeckDownloadButton({ deck, cards }: { deck: FlashcardDeck; cards: Flashcard[] }) {
  const subjectMeta = SUBJECT_LABEL[deck.subjectKind ?? 'general']
  return (
    <div className="flex justify-center">
      <button
        onClick={() => {
          const html = buildDeckHtml(deck, cards, subjectMeta)
          downloadBlob(html, `${sanitizeFilename(deck.subject)}-deck-complet.html`, 'text/html;charset=utf-8')
        }}
        className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all hover:scale-[1.03] active:scale-[0.98]"
        style={{
          background: 'linear-gradient(135deg, #06b6d4, #8b5cf6)',
          boxShadow: '0 0 16px rgba(6,182,212,0.3)',
        }}
      >
        <Download size={14} />
        <span>Télécharger le deck complet ({cards.length} fiches)</span>
      </button>
    </div>
  )
}

function DeckExportMenu({
  deck,
  cards,
  label = 'Exporter',
  variant = 'default',
}: {
  deck: FlashcardDeck
  cards: Flashcard[]
  label?: string
  variant?: 'default' | 'compact'
}) {
  const [open, setOpen] = useState(false)
  const subjectMeta = SUBJECT_LABEL[deck.subjectKind ?? 'general']
  const baseName = sanitizeFilename(`${deck.subject}-${deck.theme}`)

  const exportAs = useCallback(
    (format: 'md' | 'html' | 'pdf') => {
      setOpen(false)
      if (cards.length === 0) return
      if (format === 'md') {
        downloadBlob(deckToMarkdown(deck, cards), `${baseName}.md`, 'text/markdown;charset=utf-8')
        return
      }
      const html = buildDeckHtml(deck, cards, subjectMeta)
      if (format === 'html') {
        downloadBlob(html, `${baseName}.html`, 'text/html;charset=utf-8')
        return
      }
      openPrintWindow(html)
    },
    [cards, deck, baseName, subjectMeta],
  )

  return (
    <div className="relative inline-flex">
      <button
        onClick={() => setOpen((v) => !v)}
        className={
          variant === 'compact'
            ? 'inline-flex items-center gap-1 rounded-xl border border-aurora-border/50 bg-aurora-surface-2 px-2.5 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text transition-colors'
            : 'inline-flex items-center gap-1.5 rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-[11px] font-medium text-aurora-text hover:border-aurora-accent/40 transition-colors'
        }
      >
        <Download size={variant === 'compact' ? 11 : 12} />
        <span>{label}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 flex w-44 flex-col overflow-hidden rounded-xl border border-aurora-border bg-aurora-surface-2 shadow-xl">
          <button
            onClick={() => exportAs('pdf')}
            className="px-3 py-2 text-left text-[11px] text-aurora-text hover:bg-aurora-accent/10"
          >
            PDF (via impression)
          </button>
          <button
            onClick={() => exportAs('html')}
            className="px-3 py-2 text-left text-[11px] text-aurora-text hover:bg-aurora-accent/10"
          >
            HTML autonome
          </button>
          <button
            onClick={() => exportAs('md')}
            className="px-3 py-2 text-left text-[11px] text-aurora-text hover:bg-aurora-accent/10"
          >
            Markdown (.md)
          </button>
        </div>
      )}
    </div>
  )
}

function RevisionCardView({
  card,
  subjectKind,
  printMode = false,
}: {
  card: Flashcard
  subjectKind?: SubjectKind
  printMode?: boolean
}) {
  const meta = SUBJECT_LABEL[subjectKind ?? 'general']
  const summary = card.summary ?? card.back
  const keyPoints = card.keyPoints ?? []
  const highlights = card.highlights ?? []

  return (
    <div
      className={`relative overflow-hidden rounded-3xl border border-aurora-border bg-aurora-surface-2 shadow-xl ${
        printMode ? 'break-inside-avoid' : ''
      }`}
      data-revision-card
    >
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b ${meta.accent}`} aria-hidden />
      <div className="relative p-6 sm:p-8">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-1.5 rounded-full border border-aurora-border/60 bg-aurora-surface/60 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">
              <span>{meta.emoji}</span>
              <span>{meta.label}</span>
            </p>
            <h3 className="mt-3 text-2xl font-semibold text-aurora-text leading-tight">{card.front}</h3>
          </div>
          {!printMode && (
            <div className="flex items-start gap-3 text-right text-[10px] uppercase tracking-widest text-aurora-text-dim">
              {card.verification && (
                <VerificationBadge verification={card.verification} />
              )}
              <div>
                <p>Boite</p>
                <p className="mt-1 text-lg font-semibold text-aurora-accent">{card.box}/5</p>
              </div>
            </div>
          )}
        </div>

        {card.whyItMatters && (
          <div className="mt-4 rounded-2xl border border-aurora-accent/30 bg-aurora-accent/5 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-accent">Pourquoi c est important</p>
            <p className="mt-1 text-sm italic leading-relaxed text-aurora-text">
              {renderHighlightedText(card.whyItMatters, highlights)}
            </p>
          </div>
        )}

        {summary && (
          <div className="mt-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-text-dim">L essentiel</p>
            <p className="mt-2 text-[15px] leading-relaxed text-aurora-text">
              {renderHighlightedText(summary, highlights)}
            </p>
          </div>
        )}

        {card.deepDive && (
          <div className="mt-5 rounded-2xl border border-aurora-border/50 bg-aurora-surface/40 px-4 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-text-dim">Comprendre en profondeur</p>
            <div className="mt-2 space-y-3">
              {renderParagraphs(card.deepDive, highlights)}
            </div>
          </div>
        )}

        {keyPoints.length > 0 && (
          <div className="mt-5 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-accent">Points cles</p>
            <ul className="space-y-2">
              {keyPoints.map((point, index) => (
                <li key={`kp-${index}`} className="flex gap-3 rounded-xl bg-aurora-surface/60 px-3 py-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-aurora-accent/20 text-[11px] font-semibold text-aurora-accent">
                    {index + 1}
                  </span>
                  <div className="min-w-0 text-sm text-aurora-text leading-relaxed">
                    <p className="font-medium">{renderHighlightedText(point.label, highlights)}</p>
                    {point.detail && (
                      <p className="mt-1 text-[13px] text-aurora-text-dim">
                        {renderHighlightedText(point.detail, highlights)}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {card.formula && (
          <div className="mt-5 rounded-2xl border border-sky-400/30 bg-sky-500/10 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-sky-300">Formule</p>
            <p className="mt-1 font-mono text-base text-aurora-text break-words">{card.formula}</p>
          </div>
        )}

        {card.quote && (
          <figure className="mt-5 rounded-2xl border border-purple-400/30 bg-purple-500/10 px-4 py-3">
            <blockquote className="text-sm italic text-aurora-text leading-relaxed">
              <span className="mr-1 text-2xl leading-none text-purple-300">«</span>
              {card.quote}
              <span className="ml-1 text-2xl leading-none text-purple-300">»</span>
            </blockquote>
            {card.quoteAuthor && (
              <figcaption className="mt-1 text-[11px] uppercase tracking-[0.2em] text-purple-300">
                — {card.quoteAuthor}
              </figcaption>
            )}
          </figure>
        )}

        {card.dates && card.dates.length > 0 && (
          <div className="mt-5 rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-amber-300">Chronologie</p>
            <ol className="mt-3 relative border-l border-amber-400/30 pl-4 space-y-2">
              {card.dates.map((entry, index) => (
                <li key={`date-${index}`} className="text-[13px] text-aurora-text">
                  <span className="absolute -left-[5px] mt-1 h-2 w-2 rounded-full bg-amber-400" aria-hidden />
                  <span className="font-semibold text-amber-200">{entry.year}</span>
                  <span className="ml-2 text-aurora-text-dim">{entry.event}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {card.example && (
          <div className="mt-5 rounded-2xl border border-aurora-accent/30 bg-aurora-accent/10 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-accent">Exemple</p>
            <p className="mt-1 text-sm leading-relaxed text-aurora-text">{renderHighlightedText(card.example, highlights)}</p>
          </div>
        )}

        {card.mnemonic && (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-aurora-orange/30 bg-aurora-orange/10 px-4 py-3">
            <Lightbulb size={18} className="mt-0.5 shrink-0 text-aurora-orange" />
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-aurora-orange">Astuce mnemo</p>
              <p className="mt-1 text-sm text-aurora-text">{card.mnemonic}</p>
            </div>
          </div>
        )}

        {keyPoints.length >= 3 && !printMode && (
          <MindmapSvg
            title={card.front}
            points={keyPoints}
            subject={card.front}
            notionContext={[
              card.summary ? `Resume: ${card.summary}` : '',
              card.deepDive ? `Approfondissement: ${card.deepDive}` : '',
              card.whyItMatters ? `Importance: ${card.whyItMatters}` : '',
              card.example ? `Exemple: ${card.example}` : '',
            ].filter(Boolean).join('\n')}
          />
        )}

        {card.tags.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-1.5">
            {card.tags.map((tag, index) => (
              <span
                key={`${tag}-${index}`}
                className="rounded-full border border-aurora-border/50 bg-aurora-surface/60 px-2 py-0.5 text-[10px] text-aurora-text-dim"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function FichesPanel({
  recoveryPrompt,
  clearRecoveryPrompt,
  lessonContext,
}: {
  recoveryPrompt?: string | null
  clearRecoveryPrompt?: () => void
  lessonContext?: LessonRef | null
}) {
  const markFichesSeen = useLessonProgressStore((state) => state.markFichesSeen)
  const { mainModel, visionModel } = useAppStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const { executeWithRuntime } = useManagedRuntime()
  const activeTrackerIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  useEffect(() => () => { abortRef.current?.abort() }, [])
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'learning',
    title: 'Pack modele academie',
    assets: buildLearningModuleAssets(mainModel, visionModel, contextFiles.length > 0),
  })
  const { decks, cards, addDeckWithCards, removeDeck, removeCard, answerCard, resetDeckProgress, cardsForDeck, dueCardsForDeck } =
    useFlashcardsStore()
  const { addXp } = useGamificationStore()
  // Restore session state persisted across restarts
  const _savedFiches = useLearningSessionStore((s) => s.fiches)
  const saveFiches = useLearningSessionStore((s) => s.saveFiches)

  const [subject, setSubject] = useState(_savedFiches?.subject ?? '')
  const [theme, setTheme] = useState(_savedFiches?.theme ?? '')
  const [level, setLevel] = useState<'debutant' | 'intermediaire' | 'avance'>(_savedFiches?.level ?? 'intermediaire')
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState('Aucune fiche generee.')
  const [activeDeckId, setActiveDeckId] = useState<string | null>(_savedFiches?.activeDeckId ?? null)
  const [studyQueue, setStudyQueue] = useState<Flashcard[]>([])
  const [studyIndex, setStudyIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [reviewOnly, setReviewOnly] = useState(false)
  const [sources, setSources] = useState<LearningSource[]>([])
  const [showSources, setShowSources] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const [indexDeckId, setIndexDeckId] = useState<string | null>(null)
  const activeModel = contextFiles.length > 0 ? visionModel : mainModel

  // Persist session state so it survives app restarts
  useEffect(() => {
    saveFiches({ subject, theme, level, activeDeckId })
  }, [subject, theme, level, activeDeckId, saveFiches])

  const indexDeck = useMemo<FlashcardDeck | null>(
    () => decks.find((deck) => deck.id === indexDeckId) ?? null,
    [decks, indexDeckId],
  )
  const indexCards = useMemo(
    () => (indexDeck ? cards.filter((card) => card.deckId === indexDeck.id) : []),
    [indexDeck, cards],
  )

  useEffect(() => {
    if (recoveryPrompt) {
      setSubject(recoveryPrompt)
      clearRecoveryPrompt?.()
    }
  }, [recoveryPrompt, clearRecoveryPrompt])

  const activeDeck = useMemo<FlashcardDeck | null>(
    () => decks.find((deck) => deck.id === activeDeckId) ?? null,
    [decks, activeDeckId],
  )

  const beginStudy = useCallback(
    (deckId: string, options: { reviewOnly?: boolean } = {}) => {
      const base = options.reviewOnly ? dueCardsForDeck(deckId) : cardsForDeck(deckId)
      const shuffled = [...base].sort(() => Math.random() - 0.5)
      if (shuffled.length === 0) {
        setStatus('Aucune fiche disponible pour cette session.')
        return
      }
      setActiveDeckId(deckId)
      setStudyQueue(shuffled)
      setStudyIndex(0)
      setFlipped(false)
      setReviewOnly(Boolean(options.reviewOnly))
      setStatus(options.reviewOnly ? 'Revision espacee — boites dues.' : 'Etude complete du deck.')
    },
    [cardsForDeck, dueCardsForDeck],
  )

  const generateFiches = useCallback(async () => {
    if (!subject.trim()) return

    setIsLoading(true)
    setSources([])
    setStatus('Preparation des fiches...')

    activeTrackerIdRef.current = trackGeneration({
      module: 'learning',
      type: 'ollama_stream',
      prompt: `fiches: ${subject.trim()}${theme ? ` / ${theme}` : ''}`,
      startedAt: Date.now(),
    })

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    try {
      await executeWithRuntime({
        module: 'learning',
        title: 'Generation fiches academie',
        services: ['ollama'],
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const taskContext = await prepareTaskIntelligence({
            module: 'learning',
            prompt: `Fiches de revision: ${subject} ${theme}`.trim(),
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 42,
            phaseSpan: 14,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant fabrication des fiches.', 56)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
            }
          }

          setPhase('Recherche de sources factuelles (Wikipedia + web)...', 60)
          setStatus('Ancrage des fiches sur sources verifiees...')
          const research = await researchLearningTopic(subject.trim(), theme.trim() || level)
          if (research.hasExternalSources) {
            setSources(research.sources)
            setStatus(`Sources: ${summarizeSourcesForUI(research.sources)}${research.academicIntent.isExamFocus ? ` · Niveau ${research.academicIntent.level}` : ''}`)
          }

          // v80: when the request looks like a BAC revision, pull real past
          // exam subjects from ecebac.fr/sujetsdebac to ground the fiches on
          // actual format/progression/level instead of letting the LLM
          // invent the exam style. The block is appended to research as an
          // extra system message before generation.
          let bacEnrichmentBlock: string | null = null
          if (research.academicIntent.isExamFocus) {
            setPhase('Recuperation sujets BAC officiels (ecebac.fr)...', 64)
            try {
              const { buildBacEnrichment } = await import('../../services/bacResources')
              bacEnrichmentBlock = await buildBacEnrichment(`${subject} ${theme}`.trim(), 4)
              if (bacEnrichmentBlock) {
                setStatus((prev) => prev ? `${prev} · sujets BAC officiels charges` : 'Sujets BAC officiels charges')
              }
            } catch {
              // best-effort - bac_resources.py may not be reachable
            }
          }

          const subjectKind = detectSubjectKind(subject, theme)
          setPhase(`Fabrication des fiches (${subjectKind})...`, 72)
          const userContent = [
            `Sujet / matiere: ${subject}`,
            theme ? `Theme: ${theme}` : '',
            `Niveau: ${level}`,
            `Niveau academique detecte: ${research.academicIntent.level} (profondeur ${research.academicIntent.depth}${research.academicIntent.isExamFocus ? ', mode examen' : ''}).`,
            `Matiere detectee: ${subjectKind}`,
            `Contexte enrichi: ${taskContext.enrichedPrompt}`,
            'Retourne un tableau JSON de 6 a 10 fiches structurees selon la matiere.',
          ].filter(Boolean).join('\n')

          const rawChunks: string[] = []
          // v82lm: same TTFB widening as courses + parcours panels — academic
          // flashcard generation on a vision model with research/BAC context
          // can spend 60-180s in cold-start before yielding the first token.
          await ollamaChatStream(
            activeModel,
            [
              { role: 'system', content: buildLearningSystemPrompt('flashcards', { subjectKind, academicIntent: research.academicIntent }) },
              ...(research.contextBlock
                ? [{ role: 'system' as const, content: research.contextBlock }]
                : []),
              ...(research.examContextBlock
                ? [{ role: 'system' as const, content: research.examContextBlock }]
                : []),
              ...(bacEnrichmentBlock
                ? [{ role: 'system' as const, content: bacEnrichmentBlock }]
                : []),
              {
                role: 'user',
                content: userContent,
                images: preparedContext.flatMap((file) => file.imageBase64 ? [file.imageBase64] : []),
              },
            ],
            (token) => { rawChunks.push(token) },
            () => undefined,
            { signal: abortRef.current?.signal ?? undefined, firstByteTimeoutMs: 240_000 },
          )
          const raw = rawChunks.join('')

          setPhase('Validation et sauvegarde des fiches...', 88)
          const drafts = extractJsonArray<FlashcardDraft>(raw)
          const cardPayloads = drafts
            .map((draft) => normalizeFlashcardDraft(draft))
            .filter((card): card is NonNullable<ReturnType<typeof normalizeFlashcardDraft>> => card !== null)
          if (cardPayloads.length === 0) {
            throw new Error('Aucune fiche exploitable genere.')
          }

          // Anti-fausses-cartes: relit chaque fiche contre les sources et drop
          // celles que les sources contredisent sans correctif possible.
          let verifiedPayloads = cardPayloads
          let verificationSummary = ''
          if (research.hasExternalSources && cardPayloads.length > 0) {
            setPhase('Fact-check des fiches contre les sources...', 92)
            try {
              const report = await verifyFlashcards({
                cards: cardPayloads,
                sources: research.sources,
                auditModel: activeModel,
                signal: abortRef.current?.signal ?? undefined,
              })
              const applied = applyVerificationReport(cardPayloads, report)
              verifiedPayloads = applied.cards
              verificationSummary = applied.summary
            } catch {
              // Fact-check is best-effort: keep originals on failure.
            }
          }

          if (verifiedPayloads.length === 0) {
            throw new Error('Toutes les fiches ont ete rejetees par le fact-check.')
          }

          const deckId = `deck-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
          const deck = addDeckWithCards(
            {
              id: deckId,
              subject: subject.trim(),
              theme: theme.trim(),
              description: taskContext.enrichedPrompt.slice(0, 240),
              level,
              subjectKind,
            },
            verifiedPayloads,
          )

          const summarySuffix = verificationSummary ? ` (fact-check: ${verificationSummary})` : ''
          setStatus(`Deck "${deck.subject}" pret: ${verifiedPayloads.length} fiches (matiere: ${subjectKind})${summarySuffix}.`)
          beginStudy(deck.id)
        },
      })

      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {
          resultFilename: subject ? `fiches de ${subject.slice(0, 60)}` : undefined,
        })
        activeTrackerIdRef.current = null
      }
    } catch (error) {
      const errMsg = getErrorMessage(error, 'Echec de generation des fiches.')
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, errMsg)
        activeTrackerIdRef.current = null
      }
      setStatus(errMsg)
    } finally {
      setIsLoading(false)
    }
  }, [activeModel, addDeckWithCards, beginStudy, completeGeneration, contextFiles, executeWithRuntime, failGeneration, level, preparePack, subject, theme, trackGeneration, visionModel])

  const currentCard = studyQueue[studyIndex] ?? null

  const answerCurrentCard = useCallback(
    (correct: boolean) => {
      if (!currentCard) return
      answerCard(currentCard.id, correct)
      addXp(correct ? 8 : 3)
      setFlipped(false)
      setStudyIndex((index) => index + 1)
    },
    [addXp, answerCard, currentCard],
  )

  const endStudySession = useCallback(() => {
    setStudyQueue([])
    setStudyIndex(0)
    setFlipped(false)
  }, [])

  const deckStats = useMemo(() => {
    if (!activeDeck) return null
    const deckCards = cards.filter((card) => card.deckId === activeDeck.id)
    const boxCounts = [0, 0, 0, 0, 0]
    let totalCorrect = 0
    let totalAnswers = 0
    for (const card of deckCards) {
      boxCounts[card.box - 1]++
      totalCorrect += card.timesCorrect
      totalAnswers += card.timesCorrect + card.timesWrong
    }
    const accuracy = totalAnswers === 0 ? 0 : Math.round((totalCorrect / totalAnswers) * 100)
    return { total: deckCards.length, boxCounts, accuracy, totalAnswers }
  }, [activeDeck, cards])

  const studyFinished = studyQueue.length > 0 && studyIndex >= studyQueue.length

  // Mark lesson step as seen once the user has gone through the deck
  useEffect(() => {
    if (studyFinished && lessonContext) {
      markFichesSeen(lessonContext.pathId, lessonContext.nodeIndex)
    }
  }, [studyFinished, lessonContext, markFichesSeen])

  // Keyboard shortcuts during study session
  useEffect(() => {
    if (!currentCard || studyFinished) return
    const handler = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault()
        setFlipped((v) => !v)
      } else if (event.key === '1' || event.key.toLowerCase() === 'r') {
        event.preventDefault()
        answerCurrentCard(false)
      } else if (event.key === '2' || event.key.toLowerCase() === 'v') {
        event.preventDefault()
        answerCurrentCard(true)
      } else if (event.key === 'Escape') {
        event.preventDefault()
        endStudySession()
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        setFlipped(false)
        setStudyIndex((index) => Math.min(studyQueue.length, index + 1))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [answerCurrentCard, currentCard, endStudySession, studyFinished, studyQueue.length])

  return (
    <div className="space-y-4 animate-fade-in">
      <ClarificationDialog request={clarification} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="glass rounded-2xl p-5 space-y-4">
          <div>
            <label className="block text-xs text-aurora-text-dim">Matiere ou sujet principal</label>
            <div className="mt-2 flex items-center gap-2">
              <input
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                placeholder="Ex: Revolution francaise, biochimie lipides, formules trigo..."
                className="flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                onKeyDown={(event) => event.key === 'Enter' && void generateFiches()}
              />
              <VoicePushToTalk
                onTranscript={(text) => setSubject((prev) => (prev?.trim() ? `${prev} ${text}` : text))}
                label="Dicter la matière"
                size={40}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-aurora-text-dim">Theme specifique (optionnel)</label>
            <div className="mt-2 flex items-center gap-2">
              <input
                value={theme}
                onChange={(event) => setTheme(event.target.value)}
                placeholder="Ex: causes economiques, acides gras satures, identites remarquables..."
                className="flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
              />
              <VoicePushToTalk
                onTranscript={(text) => setTheme((prev) => (prev?.trim() ? `${prev} ${text}` : text))}
                label="Dicter le thème"
                size={40}
              />
            </div>
          </div>
          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute un cours, un chapitre PDF, des notes pour ancrer les fiches."
          />
        </div>

        <div className="glass rounded-2xl p-5 space-y-4">
          <div>
            <label className="block text-xs text-aurora-text-dim">Niveau des fiches</label>
            <select
              value={level}
              onChange={(event) => setLevel(event.target.value as typeof level)}
              className="mt-2 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none"
            >
              <option value="debutant">Debutant</option>
              <option value="intermediaire">Intermediaire</option>
              <option value="avance">Avance</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => void generateFiches()}
              disabled={!subject.trim() || isLoading}
              className="flex-1 rounded-2xl gradient-accent px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
            >
              {isLoading ? 'Generation...' : 'Generer les fiches'}
            </button>
            {isLoading && (
              <button
                onClick={() => { abortRef.current?.abort(); abortRef.current = null }}
                className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400 hover:bg-red-500/20 transition-colors"
              >
                ✕
              </button>
            )}
          </div>
          <p className="text-[11px] text-aurora-text-dim">{status}</p>
        </div>
      </div>

      <ModuleAssetPackCard pack={assetPack} />

      {sources.length > 0 && (
        <SourcesPanel sources={sources} open={showSources} onToggle={() => setShowSources((v) => !v)} />
      )}

      {decks.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-aurora-text">Mes decks ({decks.length})</h3>
            <span className="text-[11px] text-aurora-text-dim">Clique un deck pour l etudier</span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {decks.map((deck) => {
              const deckCards = cards.filter((card) => card.deckId === deck.id)
              const masteredPct = deck.cardCount === 0 ? 0 : Math.round((deck.masteredCount / deck.cardCount) * 100)
              const dueCount = deckCards.filter((card) => card.dueAt <= Date.now() || card.box <= 2).length
              const isActive = deck.id === activeDeckId
              const subjectMeta = SUBJECT_LABEL[deck.subjectKind ?? 'general']
              return (
                <div
                  key={deck.id}
                  className="rounded-2xl p-4 transition-all duration-200"
                  style={{
                    background: isActive
                      ? 'linear-gradient(135deg, rgba(6,182,212,0.12), rgba(139,92,246,0.08))'
                      : 'rgba(255,255,255,0.03)',
                    backdropFilter: 'blur(8px)',
                    border: isActive
                      ? '1px solid rgba(6,182,212,0.4)'
                      : '1px solid rgba(255,255,255,0.07)',
                    boxShadow: isActive ? '0 0 20px rgba(6,182,212,0.12)' : 'none',
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex items-center gap-2">
                      <span className="text-base">{subjectMeta.emoji}</span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-aurora-text">{deck.subject}</p>
                        {deck.theme && <p className="truncate text-[11px] text-aurora-text-dim">{deck.theme}</p>}
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        removeDeck(deck.id)
                        if (activeDeckId === deck.id) setActiveDeckId(null)
                      }}
                      className="text-aurora-text-dim hover:text-aurora-red transition-colors"
                      title="Supprimer le deck"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${masteredPct}%`,
                        background: 'linear-gradient(90deg, #06b6d4, #8b5cf6)',
                        boxShadow: masteredPct > 0 ? '0 0 6px rgba(6,182,212,0.5)' : 'none',
                      }}
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-aurora-text-dim">
                    <span>{deck.cardCount} fiches</span>
                    <span style={{ color: masteredPct >= 80 ? '#10b981' : undefined }}>Maîtrise {masteredPct}%</span>
                    <span style={{ color: dueCount > 0 ? '#f97316' : undefined }}>{dueCount} à revoir</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => beginStudy(deck.id)}
                      className="flex-1 rounded-xl gradient-accent px-3 py-2 text-[11px] font-medium text-white"
                    >
                      Etudier tout
                    </button>
                    <button
                      onClick={() => beginStudy(deck.id, { reviewOnly: true })}
                      disabled={dueCount === 0}
                      className="flex-1 rounded-xl border border-aurora-accent/40 px-3 py-2 text-[11px] font-medium text-aurora-accent disabled:opacity-40"
                    >
                      Revoir ({dueCount})
                    </button>
                    <button
                      onClick={() => setIndexDeckId(deck.id)}
                      className="rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-[11px] text-aurora-text-dim hover:text-aurora-text"
                      title="Voir toutes les fiches du deck"
                    >
                      Toutes
                    </button>
                    <DeckExportMenu deck={deck} cards={deckCards} label="Export" variant="compact" />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {activeDeck && studyQueue.length > 0 && !studyFinished && currentCard && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="glass rounded-2xl p-5">
            <div className="flex items-center justify-between text-[11px] text-aurora-text-dim">
              <span>
                {reviewOnly ? 'Mode revision' : 'Lecture'} — {activeDeck.subject}
                {activeDeck.theme ? ` · ${activeDeck.theme}` : ''}
              </span>
              <span>
                Fiche {studyIndex + 1}/{studyQueue.length} · boite {currentCard.box}/5
              </span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-aurora-surface-2">
              <motion.div
                key={studyIndex}
                initial={{ width: `${(studyIndex / studyQueue.length) * 100}%` }}
                animate={{ width: `${((studyIndex + 1) / studyQueue.length) * 100}%` }}
                className="h-full gradient-accent rounded-full"
              />
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={currentCard.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              {currentCard.kind === 'qa' || (!currentCard.summary && !currentCard.keyPoints) ? (
                <button
                  onClick={() => setFlipped((value) => !value)}
                  className="group relative block w-full"
                >
                  <motion.div
                    animate={{ rotateY: flipped ? 180 : 0 }}
                    transition={{ duration: 0.45 }}
                    style={{ transformStyle: 'preserve-3d' }}
                    className="relative mx-auto min-h-[14rem] w-full overflow-hidden rounded-3xl border border-aurora-border bg-aurora-surface-2 p-8 text-left shadow-lg"
                  >
                    <div style={{ backfaceVisibility: 'hidden' }} className="flex min-h-[12rem] flex-col justify-between">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">Recto · question</p>
                        <p className="mt-4 text-lg font-medium text-aurora-text">{currentCard.front}</p>
                      </div>
                      {currentCard.hint && (
                        <p className="mt-6 text-xs text-aurora-accent/80">Indice: {currentCard.hint}</p>
                      )}
                      <p className="mt-6 text-[10px] text-aurora-text-dim">Clique la fiche pour voir la reponse.</p>
                    </div>
                    <div
                      style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
                      className="absolute inset-0 flex flex-col justify-between bg-aurora-accent/5 p-8"
                    >
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-aurora-accent">Verso · reponse</p>
                        <p className="mt-4 text-base leading-relaxed text-aurora-text">{currentCard.back}</p>
                      </div>
                      {currentCard.tags.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-1.5">
                          {currentCard.tags.map((tag, tagIndex) => (
                            <span
                              key={`${tag}-${tagIndex}`}
                              className="rounded-full border border-aurora-accent/30 px-2 py-0.5 text-[10px] text-aurora-accent"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                </button>
              ) : (
                <RevisionCardView card={currentCard} subjectKind={activeDeck.subjectKind} />
              )}
            </motion.div>
          </AnimatePresence>

          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => answerCurrentCard(false)}
              className="rounded-2xl border border-aurora-red/40 bg-aurora-red/10 px-4 py-3 text-sm font-medium text-aurora-red hover:bg-aurora-red/15 transition-colors"
            >
              A retravailler
              <span className="ml-2 rounded-md border border-aurora-red/40 bg-aurora-red/5 px-1.5 py-0.5 text-[10px] text-aurora-red/80">R · 1</span>
            </button>
            <button
              onClick={() => answerCurrentCard(true)}
              className="rounded-2xl gradient-accent px-4 py-3 text-sm font-medium text-white"
            >
              Comprise
              <span className="ml-2 rounded-md bg-white/20 px-1.5 py-0.5 text-[10px] text-white/90">V · 2</span>
            </button>
          </div>

          {/* Full deck download — primary action */}
          {activeDeck && (
            <FullDeckDownloadButton deck={activeDeck} cards={cards.filter((c) => c.deckId === activeDeck.id)} />
          )}

          <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] text-aurora-text-dim">
            <button
              onClick={() => {
                if (!currentCard) return
                if (confirm(`Supprimer la fiche "${currentCard.front.slice(0, 60)}" ?`)) {
                  removeCard(currentCard.id)
                  setStudyQueue((queue) => queue.filter((_, index) => index !== studyIndex))
                }
              }}
              className="inline-flex items-center gap-1 rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 hover:text-aurora-red hover:border-aurora-red/30 transition-colors"
            >
              <Trash2 size={11} />
              <span>Supprimer</span>
            </button>
            <button
              onClick={() => {
                if (!currentCard || !activeDeck) return
                const md = cardToMarkdown(currentCard, activeDeck.subject, activeDeck.theme)
                downloadBlob(md, `${sanitizeFilename(currentCard.front)}.md`, 'text/markdown;charset=utf-8')
              }}
              className="inline-flex items-center gap-1 rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 hover:text-aurora-text transition-colors"
            >
              <Download size={11} />
              <span>Fiche .md</span>
            </button>
            <button
              onClick={() => {
                if (!currentCard || !activeDeck) return
                const meta = SUBJECT_LABEL[activeDeck.subjectKind ?? 'general']
                const html = buildDeckHtml(
                  { ...activeDeck, cardCount: 1 },
                  [currentCard],
                  meta,
                )
                openPrintWindow(html)
              }}
              className="inline-flex items-center gap-1 rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 hover:text-aurora-text transition-colors"
            >
              <Download size={11} />
              <span>Fiche PDF</span>
            </button>
          </div>

          <p className="text-center text-[10px] text-aurora-text-dim">
            Raccourcis: <kbd className="mx-0.5 rounded border border-aurora-border bg-aurora-surface-2 px-1">Espace</kbd> retourner (Q/R) · <kbd className="mx-0.5 rounded border border-aurora-border bg-aurora-surface-2 px-1">1/R</kbd> retravailler · <kbd className="mx-0.5 rounded border border-aurora-border bg-aurora-surface-2 px-1">2/V</kbd> comprise · <kbd className="mx-0.5 rounded border border-aurora-border bg-aurora-surface-2 px-1">→</kbd> suivante · <kbd className="mx-0.5 rounded border border-aurora-border bg-aurora-surface-2 px-1">Esc</kbd> quitter
          </p>

          {currentCard && (
            <AskAboutContentBox
              key={currentCard.id}
              label="Je ne comprends pas cette fiche"
              subject={`${activeDeck.subject}${activeDeck.theme ? ` · ${activeDeck.theme}` : ''}`}
              level={activeDeck.level}
              model={activeModel}
              context={[
                `Fiche: ${currentCard.front}`,
                currentCard.summary ? `Resume: ${currentCard.summary}` : '',
                currentCard.back ? `Reponse: ${currentCard.back}` : '',
                currentCard.deepDive ? `Explication approfondie: ${currentCard.deepDive}` : '',
                currentCard.whyItMatters ? `Pourquoi c est important: ${currentCard.whyItMatters}` : '',
                currentCard.example ? `Exemple: ${currentCard.example}` : '',
                currentCard.formula ? `Formule: ${currentCard.formula}` : '',
                currentCard.keyPoints && currentCard.keyPoints.length > 0
                  ? `Points cles: ${currentCard.keyPoints.map((kp) => typeof kp === 'string' ? kp : `${kp.label}${kp.detail ? ` — ${kp.detail}` : ''}`).join(' | ')}`
                  : '',
              ].filter(Boolean).join('\n')}
              placeholder="Ex: pourquoi la reponse est X et pas Y ? / explique-moi cette formule..."
            />
          )}
        </div>
      )}

      {activeDeck && studyFinished && (
        <div className="mx-auto max-w-md rounded-3xl glass p-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full gradient-accent-pink">
            <Sparkles size={28} className="text-white" />
          </div>
          <h3 className="mt-5 text-lg font-semibold gradient-text">Session terminee</h3>
          {deckStats && (
            <div className="mt-4 space-y-3 text-xs text-aurora-text-dim">
              <p>
                Deck "{activeDeck.subject}" — {deckStats.total} fiches
              </p>
              {deckStats.totalAnswers > 0 && (
                <p>
                  Taux de reussite cumule: <span className="font-semibold text-aurora-text">{deckStats.accuracy}%</span>
                  {' '}sur {deckStats.totalAnswers} reponse(s)
                </p>
              )}
              <div className="grid grid-cols-5 gap-2">
                {deckStats.boxCounts.map((count, boxIndex) => (
                  <div
                    key={`box-${boxIndex}`}
                    className={`rounded-xl border px-2 py-3 text-center ${
                      boxIndex >= 3 ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green' : 'border-aurora-border/50 bg-aurora-surface-2'
                    }`}
                  >
                    <p className="text-[10px] uppercase tracking-widest">B{boxIndex + 1}</p>
                    <p className="mt-1 text-sm font-semibold text-aurora-text">{count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mt-5 flex flex-col gap-2">
            <button
              onClick={() => beginStudy(activeDeck.id, { reviewOnly: true })}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-accent/40 bg-aurora-accent/10 px-5 py-3 text-sm font-medium text-aurora-accent hover:bg-aurora-accent/15 transition-colors"
            >
              <RefreshCw size={14} />
              <span>Revoir les dues</span>
            </button>
            <button
              onClick={() => beginStudy(activeDeck.id)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border bg-aurora-surface-2 px-5 py-3 text-sm text-aurora-text-dim hover:text-aurora-text transition-colors"
            >
              <Shuffle size={14} />
              <span>Nouvelle passe aleatoire</span>
            </button>
            <button
              onClick={() => resetDeckProgress(activeDeck.id)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border bg-aurora-surface-2 px-5 py-3 text-sm text-aurora-text-dim hover:text-aurora-red transition-colors"
            >
              <RotateCcw size={14} />
              <span>Reinitialiser Leitner</span>
            </button>
          </div>
        </div>
      )}

      {decks.length === 0 && !isLoading && (
        <div className="glass rounded-2xl p-8 text-center text-xs text-aurora-text-dim">
          <Layers size={22} className="mx-auto mb-3 text-aurora-text-dim" />
          <p>Aucun deck pour le moment. Saisis une matiere puis "Generer les fiches".</p>
          <p className="mt-1">Les fiches suivent un systeme Leitner (5 boites, revisions espacees).</p>
        </div>
      )}

      {indexDeck && (
        <DeckIndexModal
          deck={indexDeck}
          cards={indexCards}
          onClose={() => setIndexDeckId(null)}
          onStudyCard={(cardId) => {
            const card = cards.find((c) => c.id === cardId)
            if (card) {
              setActiveDeckId(card.deckId)
              setStudyQueue([card])
              setStudyIndex(0)
              setFlipped(false)
              setIndexDeckId(null)
            }
          }}
          onDeleteCard={(cardId) => {
            removeCard(cardId)
          }}
        />
      )}
    </div>
  )
}

export default FichesPanel
