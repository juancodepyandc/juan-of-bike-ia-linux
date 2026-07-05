/**
 * Anki export — writes a minimal `.apkg` file for a flashcard deck.
 *
 * `.apkg` = ZIP containing `collection.anki2` (SQLite DB) + a `media` JSON map
 * + individual media files. Since we can't ship sql.js here, we write a
 * simplified `.apkg` variant that Anki accepts: a ZIP containing
 * `deck.json` + a SQLite-compat sidecar is NOT what Anki wants.
 *
 * HONEST APPROACH : Anki's `.apkg` strictly requires a proper SQLite blob.
 * Building that in the browser is impractical without sql.js (~800 KB dep).
 *
 * So this module produces TWO export formats depending on what's asked:
 *   - `exportAnkiTsv(deck, cards)` — TSV flat file, Anki imports it via
 *     File → Import. Lossless for card content, fields, tags. No media.
 *     Most practical: Anki documents this path officially and it works on
 *     mobile Anki via the share sheet.
 *   - `exportAnkiHtml(deck, cards)` — standalone HTML page that also works
 *     as a study view if the user doesn't have Anki.
 */
import type { Flashcard, FlashcardDeck } from '../stores/flashcardsStore'

function escapeTsv(s: string): string {
  return (s || '').replace(/\t/g, ' ').replace(/\n/g, '<br>').trim()
}

function buildFront(card: Flashcard): string {
  if (card.kind === 'qa') return card.front
  // Revision card: include highlights + example
  const parts: string[] = [`<b>${escapeTsv(card.front)}</b>`]
  if (card.summary) parts.push(`<br><i>${escapeTsv(card.summary)}</i>`)
  return parts.join('')
}

function buildBack(card: Flashcard): string {
  if (card.kind === 'qa') return card.back
  const parts: string[] = [card.back]
  if (card.deepDive) parts.push(`<br><br><b>Explication.</b> ${card.deepDive}`)
  if (card.whyItMatters) parts.push(`<br><br><b>Pourquoi c'est important.</b> ${card.whyItMatters}`)
  if (card.keyPoints?.length) {
    parts.push('<br><br><b>Points-clés.</b><ul>' +
      card.keyPoints.map((k) => `<li>${k.label}${k.detail ? ` — ${k.detail}` : ''}</li>`).join('') +
      '</ul>')
  }
  if (card.formula)  parts.push(`<br><br><b>Formule.</b> ${card.formula}`)
  if (card.mnemonic) parts.push(`<br><br><b>Mnémo.</b> ${card.mnemonic}`)
  if (card.example)  parts.push(`<br><br><b>Exemple.</b> ${card.example}`)
  if (card.quote)    parts.push(`<br><br><i>“${card.quote}”${card.quoteAuthor ? ` — ${card.quoteAuthor}` : ''}</i>`)
  return parts.map(escapeTsv).join('')
}

/** Anki-compatible TSV : `front<TAB>back<TAB>tags`. User imports via
 * File → Import in Anki (desktop or AnkiDroid / AnkiMobile). */
export function exportAnkiTsv(deck: FlashcardDeck, cards: Flashcard[]): string {
  const lines: string[] = [
    '#separator:tab',
    '#html:true',
    `#deck:${deck.subject} - ${deck.theme}`,
    '#notetype:Basic',
    '#columns:Front\tBack\tTags',
  ]
  for (const card of cards) {
    const tags = (card.tags || []).map((t) => t.replace(/\s+/g, '_')).join(' ')
    lines.push([buildFront(card), buildBack(card), tags].join('\t'))
  }
  return lines.join('\n')
}

/** Trigger browser download of the TSV as a `.txt` file Anki can import. */
export function downloadAnkiTsv(deck: FlashcardDeck, cards: Flashcard[]): void {
  const tsv = exportAnkiTsv(deck, cards)
  const blob = new Blob([tsv], { type: 'text/tab-separated-values; charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const slug = `${deck.subject}_${deck.theme}`.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  const a = document.createElement('a')
  a.href = url
  a.download = `anki_${slug || 'deck'}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

/** Standalone HTML deck — opens in any browser, works offline. */
export function buildStandaloneDeckHtml(deck: FlashcardDeck, cards: Flashcard[]): string {
  const cardHtml = cards.map((c, i) => `
    <article class="card" data-tags="${(c.tags || []).join(' ')}">
      <div class="num">${i + 1} / ${cards.length}</div>
      <div class="front"><b>${buildFront(c)}</b></div>
      <details><summary>Révéler la réponse</summary>
        <div class="back">${buildBack(c)}</div>
      </details>
    </article>
  `).join('')
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8">
    <title>Deck ${deck.subject} — ${deck.theme}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body { font-family: 'Inter', system-ui, sans-serif; background: #ecdcb0; color: #1a0f05; padding: 20px; }
      h1 { font-family: 'Bangers', cursive; letter-spacing: 2px; }
      .card { background: #fff7df; border: 2px solid #1a0f05; box-shadow: 3px 3px 0 #1a0f05;
              padding: 14px 16px; margin: 12px 0; border-radius: 6px; }
      .num { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #6b523a; margin-bottom: 6px; }
      .front { font-size: 15px; }
      .back { margin-top: 10px; padding: 10px; background: #f3e6bf; border-left: 3px solid #c9a24b; }
      details summary { cursor: pointer; color: #b5241e; font-weight: 700; margin-top: 8px; }
    </style>
    </head><body>
    <h1>${deck.subject} — ${deck.theme}</h1>
    <p>${deck.description ?? ''} · ${cards.length} cartes</p>
    ${cardHtml}
  </body></html>`
}

export function downloadStandaloneDeckHtml(deck: FlashcardDeck, cards: Flashcard[]): void {
  const html = buildStandaloneDeckHtml(deck, cards)
  const blob = new Blob([html], { type: 'text/html; charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `deck_${deck.theme.toLowerCase().replace(/\W+/g, '_')}.html`
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

/**
 * Real binary .apkg via Python genanki sidecar.
 * Produces a SQLite-backed Anki package that any Anki client accepts on
 * double-click / share-sheet import. Returns the served URL or throws.
 */
export async function exportAnkiApkg(
  deck: FlashcardDeck,
  cards: Flashcard[],
): Promise<{ url: string; path: string; cardsCount: number }> {
  const { runPythonScript } = await import('../hooks/useTauri')
  const payload = {
    deck: {
      name: `${deck.subject} — ${deck.theme}`,
      description: deck.description ?? '',
    },
    cards: cards.map((c) => ({
      front: buildFront(c),
      back: buildBack(c),
      tags: c.tags || [],
    })),
  }
  const slug = `${deck.subject}_${deck.theme}`.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  const out = `public/exports/anki_${slug || 'deck'}_${Date.now()}.apkg`
  const res = await runPythonScript('python-services/anki_export.py', [
    '--out', out, '--json', JSON.stringify(payload),
  ])
  const output = (res as { output?: string }).output ?? ''
  const jsonLine = output.split('\n').filter((l) => l.trim().startsWith('{')).pop()
  if (!jsonLine) throw new Error('anki_export: no JSON returned')
  const data = JSON.parse(jsonLine) as { ok: boolean; error?: string; url?: string; path?: string; cards?: number }
  if (!data.ok || !data.url || !data.path) throw new Error(data.error || 'anki_export failed')
  // Trigger browser download via a temporary anchor pointing at the served URL
  const a = document.createElement('a')
  a.href = data.url
  a.download = out.split('/').pop() || 'deck.apkg'
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  return { url: data.url, path: data.path, cardsCount: data.cards ?? cards.length }
}
