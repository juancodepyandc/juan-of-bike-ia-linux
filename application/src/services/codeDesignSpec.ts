import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import type { DesignArchetype } from './codeDesignDirectives.ts'
import { hasPerceptualColorMatch } from './codeColorMetrics.ts'

export const CODE_DESIGN_SPEC_SCHEMA = 'aurora.code.design-spec/1'

export type CodeDesignPlatform =
  | 'web'
  | 'mobile_native'
  | 'desktop_native'
  | 'game_canvas'
  | 'ide'
  | 'os_shell'
  | 'non_visual'

export type CodeDesignSpec = {
  schemaVersion: typeof CODE_DESIGN_SPEC_SCHEMA
  platform: CodeDesignPlatform
  archetype: DesignArchetype
  palette: Array<{ role: string; value: string; required: boolean }>
  typography: Array<{ role: string; token: string; minPx: number; maxPx: number }>
  tokens: Record<string, string>
  components: string[]
  wireframe: string[]
  constraints: string[]
}

export type CodeDesignSpecIssue = {
  kind: 'palette' | 'tokens' | 'component' | 'wireframe' | 'platform'
  detail: string
}

export type CodeDesignSpecVerification = {
  ok: boolean
  issues: CodeDesignSpecIssue[]
}

function inferPlatform(intent: CodeIntent): CodeDesignPlatform {
  if (intent.projectType === 'game_web') return 'game_canvas'
  if (['mobile_rn', 'mobile_flutter', 'mobile_ios', 'mobile_android'].includes(intent.projectType)) return 'mobile_native'
  if (['desktop_tauri', 'desktop_electron', 'desktop_app'].includes(intent.projectType)) return 'desktop_native'
  if (intent.projectType === 'ide') return 'ide'
  if (intent.projectType === 'os_kernel') return 'os_shell'
  if (
    intent.projectType === 'static_web'
    || intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
  ) return 'web'
  return 'non_visual'
}

function paletteFor(intent: CodeIntent, archetype: DesignArchetype) {
  const subject = intent.assetPlan?.subject
  const brandProfile = subject?.source === 'brand' || subject?.source === 'inferred_brand'
    ? subject.brandProfile
    : null
  const accent = brandProfile?.primaryColor
    ?? (archetype === 'data_dense_enterprise' ? '#3b82f6'
      : archetype === 'game_visual_premium' ? '#22d3ee'
        : archetype === 'minimal_brutalist' ? '#ff0000'
          : '#7c3aed')
  const secondary = brandProfile?.secondaryColor ?? '#0f172a'
  return [
    { role: 'background', value: 'oklch(0.13 0.012 252)', required: true },
    { role: 'foreground', value: 'oklch(0.96 0.004 252)', required: true },
    { role: 'accent', value: accent, required: true },
    { role: 'support', value: secondary, required: false },
  ]
}

function componentsFor(archetype: DesignArchetype, platform: CodeDesignPlatform): string[] {
  if (platform === 'mobile_native') return ['safe-area shell', 'bottom tabs', 'detail screen', 'settings screen']
  if (platform === 'game_canvas') return ['canvas', 'hud', 'start screen', 'game over screen']
  if (archetype === 'data_dense_enterprise') return ['sidebar', 'topbar', 'data table', 'chart panel', 'filter bar']
  if (archetype === 'ide_code_editor') return ['file tree', 'editor pane', 'terminal panel', 'command palette']
  if (archetype === 'os_shell') return ['terminal viewport', 'process panel', 'status bar']
  if (archetype === 'dashboard_dataviz') return ['sidebar', 'topbar', 'kpi cards', 'chart panel']
  if (archetype === 'ecommerce_premium') return ['product grid', 'cart button', 'filter drawer', 'newsletter']
  if (archetype === 'apple_product') return ['hero product visual', 'hotspots', 'spec table', 'compare section']
  return ['nav', 'hero', 'feature grid', 'cta', 'footer']
}

function wireframeFor(archetype: DesignArchetype, platform: CodeDesignPlatform): string[] {
  if (platform === 'mobile_native') return ['splash', 'onboarding', 'home', 'detail', 'settings']
  if (platform === 'game_canvas') return ['start menu', 'playfield', 'pause overlay', 'game over']
  if (archetype === 'data_dense_enterprise') return ['sidebar', 'topbar', 'kpi row', 'table + chart split', 'details drawer']
  if (archetype === 'ide_code_editor') return ['activity bar', 'file tree', 'editor tabs', 'code editor', 'terminal']
  if (archetype === 'os_shell') return ['boot log', 'command prompt', 'process list', 'status footer']
  return ['nav', 'hero', 'body sections', 'cta', 'footer']
}

export function buildCodeDesignSpec(prompt: string, intent: CodeIntent, archetype: DesignArchetype): CodeDesignSpec {
  const platform = inferPlatform(intent)
  const tokens = platform === 'mobile_native'
    ? {
        spacing: '4/8/12/16/24/32 native dp',
        radius: '12 card / 20 sheet / 999 pill',
        motion: 'native spring gestures, no CSS hover contract',
      }
    : platform === 'game_canvas'
      ? {
          spacing: 'HUD 8px grid, canvas safe margins',
          radius: 'menu 8 / button 6',
          motion: 'requestAnimationFrame delta-time, particles, screen shake',
        }
      : {
          spacing: '4/8/12/16/24/32/48/64/96 CSS tokens',
          radius: '4 chip / 8 input / 12 card / 20 section / 999 pill',
          motion: 'cubic-bezier tokens + prefers-reduced-motion',
        }
  const constraints = [
    'Respecter cette design-spec comme contrat de livraison verifiable.',
    platform === 'mobile_native' ? 'Ne pas appliquer de contrat CSS web generique; utiliser les primitives natives.' : '',
    platform === 'game_canvas' ? 'Ne pas appliquer de landing-page CSS contract; prioriser gameplay, HUD et canvas responsive.' : '',
    platform === 'web' ? 'Utiliser variables CSS et styles calcules coherents avec la palette.' : '',
    prompt.toLowerCase().includes('dense') ? 'Densite informationnelle elevee mais scannable.' : '',
  ].filter(Boolean)
  return {
    schemaVersion: CODE_DESIGN_SPEC_SCHEMA,
    platform,
    archetype,
    palette: paletteFor(intent, archetype),
    typography: [
      { role: 'display', token: '--font-display', minPx: 40, maxPx: 96 },
      { role: 'body', token: '--font-body', minPx: 14, maxPx: 18 },
      { role: 'label', token: '--font-label', minPx: 11, maxPx: 13 },
    ],
    tokens,
    components: componentsFor(archetype, platform),
    wireframe: wireframeFor(archetype, platform),
    constraints,
  }
}

export function formatCodeDesignSpecPrompt(spec: CodeDesignSpec): string {
  return [
    '## DESIGN SPEC JSON — AURORA_CODE_DESIGN_SPEC/1',
    JSON.stringify(spec, null, 2),
    '',
    '## DESIGN SPEC CONTRACT',
    '- Le code livre doit implementer la palette, les tokens, les composants et le wireframe ci-dessus.',
    '- Cette spec est verifiee apres generation; un ecart palette/composant/plateforme est un echec.',
    spec.platform === 'mobile_native' ? '- Plateforme native mobile: pas de contrat CSS web generique.' : '',
    spec.platform === 'game_canvas' ? '- Jeu canvas: pas de landing page deguisee, le HUD et les ecrans de jeu priment.' : '',
  ].filter(Boolean).join('\n')
}

function aggregate(files: CodeFile[]): string {
  return files.map((file) => file.content).join('\n')
}

function cssLike(files: CodeFile[]): string {
  return files
    .filter((file) => /\.(css|scss|sass|less|html|tsx|jsx|vue|svelte)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')
}

function includesComponent(body: string, component: string): boolean {
  const words = component.toLowerCase().split(/\s+/).filter((word) => word.length > 2)
  return words.some((word) => body.includes(word))
}

export function verifyCodeDesignSpecAgainstFiles(spec: CodeDesignSpec, files: CodeFile[]): CodeDesignSpecVerification {
  if (spec.platform === 'non_visual') return { ok: true, issues: [] }
  const issues: CodeDesignSpecIssue[] = []
  const all = aggregate(files).toLowerCase()
  const styles = cssLike(files)

  for (const color of spec.palette.filter((item) => item.required)) {
    if (!hasPerceptualColorMatch(styles || aggregate(files), color.value)) {
      issues.push({ kind: 'palette', detail: `${color.role}:${color.value}` })
    }
  }

  if ((spec.platform === 'web' || spec.platform === 'ide') && !/var\(\s*--|:root\s*\{/.test(styles)) {
    issues.push({ kind: 'tokens', detail: 'css_variables_missing' })
  }

  if (spec.platform === 'mobile_native' && files.some((file) => /\.(css|scss|sass|less)$/i.test(file.name))) {
    issues.push({ kind: 'platform', detail: 'mobile_native_contains_web_css_file' })
  }
  if (spec.platform === 'game_canvas' && !/\bcanvas\b|getContext\(|requestAnimationFrame/i.test(all)) {
    issues.push({ kind: 'platform', detail: 'game_canvas_missing_canvas_loop' })
  }

  const missingComponents = spec.components
    .filter((component) => !includesComponent(all, component))
    .slice(0, 4)
  for (const component of missingComponents) {
    issues.push({ kind: 'component', detail: component })
  }

  if (spec.platform === 'web') {
    const sectionCount = (all.match(/<section\b/g) ?? []).length
    if (sectionCount < 3) issues.push({ kind: 'wireframe', detail: `sections:${sectionCount}` })
  }

  return { ok: issues.length === 0, issues }
}
