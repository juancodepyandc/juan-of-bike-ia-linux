import type { CodeFile } from './codeOrchestrator.ts'

export type DesignPolishReport = {
  score: number
  missing: string[]
  penalties: string[]
}

export function computeDesignPolishScore(files: CodeFile[]): number {
  return computeDesignPolishReport(files).score
}

export function computeDesignPolishReport(files: CodeFile[]): DesignPolishReport {
  const visualBlob = files
    .filter((file) => /\.(html?|css|s?css|less|tsx?|jsx?|vue|svelte|astro)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')
    .toLowerCase()

  if (visualBlob.length < 200) {
    return {
      score: 30,
      missing: ['contenu visuel insuffisant — moins de 200 caracteres de CSS/HTML detectes'],
      penalties: [],
    }
  }

  let score = 0
  const missing: string[] = []
  const checks: Array<{ label: string; pattern: RegExp; points: number }> = [
    { label: 'CSS variables / design tokens (--color-*, --space-*, etc.)', pattern: /--[a-z-]+:\s*/i, points: 12 },
    { label: 'police premium Google Fonts (Inter / Manrope / Satoshi / DM Sans / Space Grotesk / Plus Jakarta)', pattern: /inter|manrope|satoshi|dm sans|space grotesk|plus jakarta|bricolage|bangers/i, points: 10 },
    { label: 'gradients (linear-gradient / radial-gradient / conic-gradient)', pattern: /(linear|radial|conic)-gradient/i, points: 12 },
    { label: 'transitions explicites (transition: ... 250ms cubic-bezier)', pattern: /transition:\s*[^;]+\d+ms/i, points: 8 },
    { label: '@keyframes (animations CSS)', pattern: /@keyframes\s+\w+/i, points: 10 },
    { label: 'backdrop-filter blur (glassmorphism)', pattern: /backdrop-filter\s*:\s*blur/i, points: 10 },
    { label: 'clamp() pour les tailles responsive', pattern: /clamp\s*\(/i, points: 8 },
    { label: 'box-shadow multi-layer composite', pattern: /box-shadow\s*:[^;]*,[^;]*\d/i, points: 8 },
    { label: 'utilisation de var(--*) (variables CSS appliquees)', pattern: /var\(--[a-z]/i, points: 6 },
    { label: 'layout moderne grid ou flex', pattern: /display\s*:\s*(grid|flex)/i, points: 6 },
    { label: 'hover states (:hover {)', pattern: /:hover\s*\{/i, points: 5 },
  ]

  for (const { label, pattern, points } of checks) {
    if (pattern.test(visualBlob)) score += points
    else missing.push(`${label} (${points} pts manquants)`)
  }

  const hexes = new Set(visualBlob.match(/#[0-9a-f]{6}/g) || [])
  if (hexes.size >= 5) score += 5
  else if (hexes.size >= 3) score += 3
  else missing.push(`palette riche (${hexes.size} couleurs hex distinctes seulement, vise 5+)`)

  const penalties: string[] = []
  if (/font-family\s*:\s*["']?(arial|times new roman|sans-serif)\s*[;,"']/i.test(visualBlob)) {
    score -= 15
    penalties.push('police par defaut (Arial / Times / sans-serif) — utilise une Google Fonts premium')
  }
  if (/<table[^>]*>\s*<tr/i.test(visualBlob) && !/role="grid"/i.test(visualBlob)) {
    score -= 10
    penalties.push('layout en <table> — utilise CSS grid ou flexbox')
  }
  if (/(background|color)\s*:\s*(blue|red|green|yellow|black|white)\s*;/i.test(visualBlob)) {
    score -= 5
    penalties.push('couleur basique (blue/red/green) — utilise un hex code premium ou une variable CSS')
  }
  if (/<button[^>]*>(?:[^<]*?)<\/button>/.test(visualBlob)
    && !/button\s*\{[\s\S]*?(background|border-radius|transition)/i.test(visualBlob)) {
    score -= 8
    penalties.push('bouton sans style (pas de background, border-radius, ou transition) — restyle-le')
  }

  return { score: Math.max(0, Math.min(100, score)), missing, penalties }
}

export function buildDesignRetryHint(report: DesignPolishReport): string {
  const lines: string[] = [
    '═══════════════════════════════════════════════════════════',
    'AUDIT DESIGN — ton output precedent est ENCORE TROP SCOLAIRE',
    `Score: ${report.score}/100 (seuil minimum: 70)`,
    '═══════════════════════════════════════════════════════════',
    '',
  ]
  if (report.missing.length > 0) {
    lines.push('Ce que tu as OUBLIE (a ajouter imperativement):')
    for (const item of report.missing.slice(0, 8)) lines.push(`  ✗ ${item}`)
    lines.push('')
  }
  if (report.penalties.length > 0) {
    lines.push('Ce que tu as MAL FAIT (a corriger):')
    for (const item of report.penalties) lines.push(`  ⚠ ${item}`)
    lines.push('')
  }
  lines.push(
    'Refais le projet COMPLET avec TOUS ces points corriges.',
    'INTERDICTION absolue de relivrer du HTML qui ressemblerait a un tutoriel debutant.',
    '═══════════════════════════════════════════════════════════',
  )
  return lines.join('\n')
}
