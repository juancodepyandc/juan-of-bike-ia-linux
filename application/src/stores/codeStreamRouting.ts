type CodeModelRouteInput = {
  baseModel: string
  installed: string[]
  isVisual: boolean
  text: string
}

type CodeModelRoute = {
  model: string
  routeReason: string
  brandHint: string | null
}

const PREFERRED_GENERAL_SPEED = [
  'qwen3:14b', 'gemma3:27b', 'mistral-small3.1:24b',
  'gemma3:12b', 'qwen3:32b', 'llama3.3',
  'qwen2.5:7b', 'qwen3-vl:30b', 'qwen3-vl:8b',
]
const PREFERRED_GENERAL_QUALITY = [
  'qwen3:14b', 'gemma3:27b', 'mistral-small3.1:24b',
  'gemma3:12b', 'qwen3:32b', 'llama3.3',
  'qwen3-vl:30b', 'qwen2.5:7b', 'qwen3-vl:8b',
]
const PREFERRED_CODER = [
  'qwen3-coder-next:q8_0', 'qwen3-coder-next:q4_K_M',
  'qwen3-coder:30b-a3b-q8_0', 'qwen3-coder:30b-a3b-q4_K_M', 'qwen3-coder:30b',
  'qwen2.5-coder:32b', 'qwen2.5-coder:14b', 'deepseek-coder-v2:16b',
  'qwen2.5-coder:7b', 'codellama:13b',
]

const BRAND_HINT_RE = /\b([A-Z][a-zA-Z]{2,}(?:[\s-][A-Z][a-zA-Z]{2,})?)\b/
const BRAND_STOP_WORDS = new Set(['Page', 'App', 'Application', 'Site', 'Landing', 'Dashboard',
  'Pour', 'Avec', 'Sans', 'Sur', 'Faire', 'Crée', 'Le', 'La', 'Les', 'Un', 'Une', 'Des'])

function pickFirstInstalled(installed: string[], candidates: string[], fallback: string) {
  return installed.length > 0
    ? candidates.find((model) => installed.some((candidate) => candidate === model || (!model.includes(':') && candidate.startsWith(model + ':')))) || fallback
    : fallback
}

export function extractBrandHint(text: string) {
  const match = text.match(BRAND_HINT_RE)
  return match && !BRAND_STOP_WORDS.has(match[1].split(/[\s-]/)[0]) ? match[1] : null
}

export function routeCodeStreamModel({ baseModel, installed, isVisual, text }: CodeModelRouteInput): CodeModelRoute {
  const isCoderModel = /coder|codellama|coding/i.test(baseModel)
  const brandHint = extractBrandHint(text)
  let model = baseModel
  let routeReason = 'configured'

  if (isVisual && isCoderModel) {
    const list = brandHint ? PREFERRED_GENERAL_QUALITY : PREFERRED_GENERAL_SPEED
    model = pickFirstInstalled(installed, list, 'qwen3:14b')
    routeReason = `visual${brandHint ? '+brand' : ''} needs general LLM`
  } else if (isVisual && brandHint) {
    const upgrade = pickFirstInstalled(installed, PREFERRED_GENERAL_QUALITY, baseModel)
    if (upgrade && upgrade !== baseModel) { model = upgrade; routeReason = `brand ${brandHint}` }
  } else if (!isVisual && !isCoderModel) {
    const upgrade = pickFirstInstalled(installed, PREFERRED_CODER, '')
    if (upgrade && upgrade !== baseModel) { model = upgrade; routeReason = 'code-heavy → coder model' }
  }

  return { model, routeReason, brandHint }
}

export function isCorrectionRequest(text: string) {
  return /\b(corrig|fix|r[ée]par|bug|erreur|[ée]cran\s*noir|plante|cass|d[ée]bogue|marche\s*pas|fonctionne\s*pas|r[ée]sou[ds]|ne\s*s'?affiche)\b/i.test(text)
}
