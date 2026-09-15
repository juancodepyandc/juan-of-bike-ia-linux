/**
 * deckMindMap — turn a flashcard deck into a hierarchical mind map.
 *
 * The user asked for "interactivité sur des cartes mental etc". The Manga
 * Academy view already ships a generic MindMap React component but with a
 * static demo tree. This service takes the user's actual deck and emits a
 * mind map structure where:
 *   root = subject (matiere)
 *     level 1 = key themes detected from card tags / titles
 *       level 2 = each card title (clickable to open card detail)
 *         level 3 = up to 3 keyPoints highlights of that card
 *
 * Pure function, no LLM, deterministic — runs synchronously on every deck
 * change so the user can see their mind map update live as they generate
 * new cards.
 */

import type { Flashcard, FlashcardDeck } from '../stores/flashcardsStore.ts'

export type MindNode = {
  label: string
  children?: MindNode[]
  /** Optional payload pointing back to the source card so the UI can open detail. */
  cardId?: string
  /** Tag used for rendering in the existing MindMap component. */
  kind?: 'subject' | 'theme' | 'card' | 'point'
}

/**
 * Group cards by primary tag (or fallback "general" bucket).
 * The tag with most cards becomes the first child of the mind map.
 */
function groupCardsByTheme(cards: Flashcard[]): Map<string, Flashcard[]> {
  const groups = new Map<string, Flashcard[]>()
  for (const card of cards) {
    const primaryTag = card.tags[0]?.trim() || 'General'
    const bucket = groups.get(primaryTag) ?? []
    bucket.push(card)
    groups.set(primaryTag, bucket)
  }
  return groups
}

/** Truncate a card title for the mind map node (rendering caps at ~16 chars per node). */
function shortenTitle(text: string, max = 38): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  if (cleaned.length <= max) return cleaned
  return `${cleaned.slice(0, max - 1)}…`
}

/**
 * Build a mind map node tree from a deck and its cards.
 * - Root label = deck subject
 * - One child per theme
 * - One grandchild per card
 * - Up to 3 great-grandchildren per card (keyPoints highlights)
 */
export function buildDeckMindMap(deck: FlashcardDeck, cards: Flashcard[]): MindNode {
  if (cards.length === 0) {
    return {
      label: deck.subject || 'Deck vide',
      kind: 'subject',
      children: [],
    }
  }

  const themes = groupCardsByTheme(cards)
  const themeChildren: MindNode[] = []

  // Sort themes by card count descending so the densest theme is at the front.
  const sortedThemes = Array.from(themes.entries()).sort((a, b) => b[1].length - a[1].length)

  for (const [themeName, themeCards] of sortedThemes) {
    const cardChildren: MindNode[] = []
    for (const card of themeCards.slice(0, 12)) {
      const points = (card.keyPoints || [])
        .slice(0, 3)
        .map((kp) => ({ label: shortenTitle(kp.label, 22), kind: 'point' as const }))
      cardChildren.push({
        label: shortenTitle(card.front, 28),
        kind: 'card',
        cardId: card.id,
        children: points.length > 0 ? points : undefined,
      })
    }
    themeChildren.push({
      label: shortenTitle(themeName, 24),
      kind: 'theme',
      children: cardChildren,
    })
  }

  return {
    label: shortenTitle(deck.subject || deck.theme || 'Deck', 22),
    kind: 'subject',
    children: themeChildren,
  }
}

/**
 * Quick stats helper: how rich the mind map is for a UI preview.
 */
export function describeDeckMindMap(node: MindNode): { themes: number; cards: number; points: number } {
  let themes = 0
  let cards = 0
  let points = 0
  for (const themeNode of node.children || []) {
    themes += 1
    for (const cardNode of themeNode.children || []) {
      cards += 1
      points += (cardNode.children || []).length
    }
  }
  return { themes, cards, points }
}

/**
 * v74: scorer la qualite d une mind map de deck.
 *
 * Sans ce scorer un deck "bien organise" (5 themes equilibres, 3 keyPoints
 * par carte) et un deck plat (toutes les cartes sous "General", 0 keyPoint)
 * ressemblent identiques en UI. Les criteres ci-dessous decoulent de ce qu'
 * une fiche de revisions doit produire pour etre revisable - pas un score
 * arbitraire.
 *
 * Score / 100:
 *   theme distribution (40 pts): pas de theme > 60%, au moins 3 themes avec
 *     >= 2 cartes (sinon le mind map est juste une liste a plat deguisee)
 *   keyPoints coverage (30 pts): part des cartes avec >= 2 keyPoints
 *   tag diversity (20 pts): nombre de tags distincts vs nombre de cartes
 *   density (10 pts): cartes >= 8 minimum pour qu un mind map soit utile
 */
export type MindMapQualityReport = {
  score: number
  themes: number
  cards: number
  diagnostics: string[]
  recommendations: string[]
}

export function evaluateMindMapQuality(node: MindNode, cards: Flashcard[]): MindMapQualityReport {
  const stats = describeDeckMindMap(node)
  const diagnostics: string[] = []
  const recommendations: string[] = []
  let score = 0

  if (cards.length === 0) {
    return {
      score: 0,
      themes: 0,
      cards: 0,
      diagnostics: ['Aucune carte dans le deck.'],
      recommendations: ['Genere au moins 8 cartes pour avoir un mind map exploitable.'],
    }
  }

  // 40 pts — theme distribution
  const themeCounts = (node.children || []).map((t) => (t.children || []).length)
  const totalCards = themeCounts.reduce((a, b) => a + b, 0) || cards.length
  const dominantShare = themeCounts.length > 0 ? Math.max(...themeCounts) / totalCards : 1
  const meaningfulThemes = themeCounts.filter((c) => c >= 2).length
  if (dominantShare <= 0.4) score += 25
  else if (dominantShare <= 0.6) score += 15
  else {
    score += 5
    diagnostics.push(`Un seul theme regroupe ${Math.round(dominantShare * 100)}% des cartes`)
    recommendations.push('Ajoute des tags varies aux cartes pour creer plus de branches.')
  }
  if (meaningfulThemes >= 3) score += 15
  else if (meaningfulThemes >= 2) score += 8
  else {
    diagnostics.push(`Seulement ${meaningfulThemes} theme(s) avec >= 2 cartes`)
    recommendations.push('Genere plus de cartes pour etoffer chaque branche.')
  }

  // 30 pts — keyPoints coverage
  const cardsWithPoints = cards.filter((c) => (c.keyPoints || []).length >= 2).length
  const pointsRatio = cardsWithPoints / cards.length
  if (pointsRatio >= 0.7) score += 30
  else if (pointsRatio >= 0.4) score += 18
  else if (pointsRatio >= 0.2) score += 8
  else {
    diagnostics.push(`Seulement ${Math.round(pointsRatio * 100)}% des cartes ont >= 2 keyPoints`)
    recommendations.push('Active la generation enrichie pour avoir des keyPoints sur chaque carte.')
  }

  // 20 pts — tag diversity
  const allTags = new Set<string>()
  for (const card of cards) {
    for (const t of (card.tags || [])) {
      const cleaned = t.trim().toLowerCase()
      if (cleaned) allTags.add(cleaned)
    }
  }
  const tagRatio = allTags.size / cards.length
  if (tagRatio >= 0.5) score += 20
  else if (tagRatio >= 0.3) score += 12
  else if (tagRatio >= 0.15) score += 6
  else {
    diagnostics.push(`Diversite tags faible (${allTags.size} tags pour ${cards.length} cartes)`)
    recommendations.push('Demande au LLM de tagger chaque carte avec 2-3 tags thematiques.')
  }

  // 10 pts — density
  if (cards.length >= 16) score += 10
  else if (cards.length >= 10) score += 7
  else if (cards.length >= 6) score += 4
  else {
    diagnostics.push(`Deck peu dense (${cards.length} cartes)`)
    recommendations.push('Vise au moins 10 cartes pour qu une mind map ait du sens.')
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    themes: stats.themes,
    cards: stats.cards,
    diagnostics,
    recommendations,
  }
}
