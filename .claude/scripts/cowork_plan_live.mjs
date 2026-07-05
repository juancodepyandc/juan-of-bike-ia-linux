// Live planner probe: runs the REAL coworkPlanner against the local Ollama
// (gemma3:12b, 16GB-safe) for representative création / accompagnement prompts,
// and prints the resulting plan so we can judge ACT-vs-ASK.
//
// Node has no localStorage / window — shim the minimum so settings + appStore
// load cleanly. isTauriRuntime() stays false → ollamaChat hits 127.0.0.1 directly.
const store = new Map()
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  clear: () => store.clear(),
}

const { useAppStore } = await import('../../application/src/stores/appStore.ts')
useAppStore.setState({ mainModel: 'gemma3:12b' })

const { planNextStep } = await import('../../application/src/services/coworkPlanner.ts')

const PROMPTS = process.argv.slice(2).length
  ? process.argv.slice(2)
  : [
      'écoute, je suis débordé en ce moment, aide-moi à m\'organiser pour la semaine',
      'planifie ma semaine de révision du bac',
      'crée un fichier idees.md avec 5 idées de startup détaillées',
    ]

function summarizeAction(a) {
  const head = a.kind
  if (a.kind === 'reply') return `reply: "${(a.message || '').replace(/\s+/g, ' ').slice(0, 220)}…"`
  if (a.kind === 'think') return `think[${a.topic}]: ${(a.thought || '').slice(0, 90)}…`
  if (a.kind === 'finish') return `finish: ${a.summary}`
  if (a.kind === 'write_file' || a.kind === 'read_file' || a.kind === 'list_dir') return `${head}: ${a.path}`
  if (a.kind === 'connector') return `connector ${a.connector}.${a.action} ${JSON.stringify(a.params || {}).slice(0, 80)}`
  if (a.kind === 'web_search') return `web_search: ${a.query}`
  if (a.kind === 'shell') return `shell: ${a.command} ${(a.args || []).join(' ')}`
  return head + ' ' + JSON.stringify(a).slice(0, 80)
}

for (const p of PROMPTS) {
  console.log('\n================================================================')
  console.log('PROMPT:', p)
  const t0 = Date.now()
  try {
    const plan = await planNextStep({
      userPrompt: p,
      runtime: 'tauri-desktop',
      capabilities: [
        { id: 'filesystem', label: 'Filesystem', description: '', enabled: true, destructive: true },
        { id: 'shell', label: 'Shell', description: '', enabled: true, destructive: true },
        { id: 'fetch', label: 'Fetch', description: '', enabled: true, destructive: false },
      ],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [],
    })
    const reply = plan.actions.find((a) => a.kind === 'reply')
    const msg = (reply?.message || '').trim()
    const activeKinds = plan.actions.filter((a) => !['finish', 'voice_speak'].includes(a.kind))
    const hasRealTool = activeKinds.some((a) => !['reply', 'think'].includes(a.kind))
    // Accompaniment quality: opens with a deliverable (not a bare question),
    // is structured, and offers concrete follow-through.
    const opensWithQuestion = /^[^.\n]{0,120}\?\s*$/.test(msg.split('\n')[0] || '') || /^(bien s[uû]r|d accord|pour (t|vous) aider).{0,80}\?/i.test(msg)
    const structured = /(^|\n)\s*(#{1,3}\s|\d+\.\s|[-*]\s)/.test(msg)
    const hasFollowThrough = /prochaine [ée]tape|je (te|peux te) (cr[ée]e|propose|mets)|veux-tu|souhaites-tu|cr[ée]er (le|un) fichier|rappels?/i.test(msg)
    let verdict
    if (hasRealTool) verdict = 'ACTIF (outil concret)'
    else if (!structured || opensWithQuestion) verdict = 'PAUVRE (question/générique)'
    else verdict = `DELIVRABLE structuré${hasFollowThrough ? ' + suivi proposé' : ''}`
    console.log(`(${((Date.now() - t0) / 1000).toFixed(1)}s) reasoning: ${plan.reasoning}`)
    console.log('VERDICT:', verdict)
    if (msg) {
      const lines = msg.split('\n')
      console.log('  ── reply (début) ──')
      lines.slice(0, 6).forEach((l) => console.log('  | ' + l.slice(0, 110)))
      if (lines.length > 8) { console.log('  | …'); console.log('  | ' + lines.slice(-3).join(' / ').slice(0, 200)) }
    }
    plan.actions.forEach((a, i) => console.log(`  ${i + 1}. ${a.kind}`))
  } catch (e) {
    console.log('ERROR:', e?.message || e)
  }
}
