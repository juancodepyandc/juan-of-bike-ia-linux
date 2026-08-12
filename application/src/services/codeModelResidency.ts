// ---------------------------------------------------------------------------
// Garde anti-crash de residence memoire (16GB VRAM + 32GB RAM = 48GB).
// Deux gros modeles code (devstral 14GB, qwen3-coder 18GB, deepseek-r1 20GB) ne
// PEUVENT PAS coexister: la somme deborde en swap -> gel machine (crash constate).
// Le routage multi-modeles (agent -> codeur -> verifieur) charge des modeles
// DIFFERENTS par role. Sans OLLAMA_MAX_LOADED_MODELS=1, Ollama les empile.
// Avant qu un role charge SON modele, on decharge tout AUTRE gros modele code
// deja resident -> un seul gros modele a la fois, jamais de swap.
// ---------------------------------------------------------------------------

const OLLAMA = 'http://localhost:11434'
// Prefixes des gros modeles code qu on ne doit jamais empiler. On ne touche PAS
// aux modeles partages legers (vision qwen3-vl, embeddings nomic, main instruct)
// qui peuvent coexister.
const HEAVY_CODE_MODEL_PREFIXES = ['devstral', 'qwen3-coder', 'deepseek-r1', 'qwen3.6']

function norm(model: string): string {
  return (model || '').trim().replace(/:latest$/i, '').toLowerCase()
}

// La liste de prefixes supposait que « vision qwen3-vl » etait un modele leger.
// Mesure reelle (run 1041): qwen3-vl:30b est un 30B — il pese autant qu un gros
// modele code. La machine etait a 0 octet de RAM libre quand Ollama a rendu
// `fetch failed`. Un modele se juge donc a sa TAILLE, pas a sa famille.
const HEAVY_SIZE_TAG = /[:\-](?:2[4-9]|[3-9]\d|\d{3,})\s*b\b/i

function isHeavyCodeModel(name: string): boolean {
  const n = norm(name)
  return HEAVY_CODE_MODEL_PREFIXES.some((p) => n.startsWith(p)) || HEAVY_SIZE_TAG.test(n)
}

let lastEnsured: string | null = null

/**
 * Garantit qu au plus UN gros modele code est charge en memoire: decharge tout
 * autre gros modele code avant que `model` prenne la main. Best-effort et
 * non-bloquant (ne fait jamais echouer une generation). Idempotent tant que le
 * modele ne change pas (evite un /api/ps a chaque token).
 */
export async function ensureExclusiveCodeModel(model: string): Promise<void> {
  const target = norm(model)
  if (!target || target === lastEnsured) return
  try {
    const res = await fetch(`${OLLAMA}/api/ps`)
    const data = (await res.json()) as { models?: Array<{ name?: string }> }
    const loaded = (data.models ?? []).map((m) => m.name ?? '').filter(Boolean)
    for (const other of loaded) {
      if (norm(other) === target) continue
      if (!isHeavyCodeModel(other)) continue
      // keep_alive:0 => Ollama decharge ce modele immediatement.
      await fetch(`${OLLAMA}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: other, keep_alive: 0 }),
      }).catch(() => undefined)
    }
    lastEnsured = target
  } catch {
    // Ollama injoignable ou schema inattendu: on ne bloque pas la generation.
  }
}

/**
 * A appeler des qu un AUTRE module a pu charger un modele (phase d assets
 * inter-modules, audit visuel...). Sans cela, `lastEnsured` fait croire que la
 * residence est deja garantie et la garde ne decharge jamais l intrus.
 *
 * Mesure reelle (run 1041): la garde etait posee pendant la planification, PUIS
 * la phase d assets chargeait un modele image, PUIS la generation reprenait avec
 * la garde en cache — donc sans jamais rien decharger. Les deux modeles ont
 * cohabite pendant toute la generation.
 */
export function invalidateModelResidencyCache(): void {
  lastEnsured = null
}

/** Pour les tests: reset du cache de residence. */
export function __resetModelResidencyCacheForTest(): void {
  lastEnsured = null
}
