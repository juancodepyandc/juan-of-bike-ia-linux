import { getBridgeUrl } from '../utils/runtime.ts'

export type CodeStreamPreflightIssue = {
  title: string
  message: string
  suggestion: string
}

export async function checkCodeBridgeReady(): Promise<CodeStreamPreflightIssue | null> {
  try {
    const probe = await fetch(`${getBridgeUrl()}/healthz`, { signal: AbortSignal.timeout(4_000) })
    if (!probe.ok) throw new Error('bridge_unhealthy')
    return null
  } catch {
    return {
      title: 'Bridge AuroraIA non joignable',
      message: 'Le bridge Python (port 3001) ne répond pas. Aurora est peut-être fermé ou le tunnel a expiré.',
      suggestion: 'Relance Aurora avec le lanceur de ta plateforme, ou exécute "python bridge_doctor.py" puis clique OK pour réessayer.',
    }
  }
}

export async function checkCodeModelInstalled(model: string): Promise<CodeStreamPreflightIssue | null> {
  try {
    const tagsResp = await fetch(`${getBridgeUrl()}/proxy/ollama/api/tags`, { signal: AbortSignal.timeout(6_000) })
    if (!tagsResp.ok) return null
    const tags = await tagsResp.json() as { models?: Array<{ name?: string }> }
    const have = (tags.models ?? []).map((m) => m.name ?? '').filter(Boolean)
    if (have.length === 0 || have.includes(model)) return null
    return {
      title: `Modèle "${model}" non installé`,
      message: `Le modèle ${model} n'est pas dans Ollama. Disponibles : ${have.slice(0, 6).join(', ')}${have.length > 6 ? '…' : ''}.`,
      suggestion: `Lance "ollama pull ${model}" puis OK pour réessayer.`,
    }
  } catch {
    return null
  }
}
