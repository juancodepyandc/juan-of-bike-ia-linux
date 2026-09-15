import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'

installHeadlessCodeEnv()

async function main() {
  console.log('[conversation-harness] Initializing Conversation Test Harness...')

  const { runConversationTurn } = await import('../src/services/conversationOrchestrator.ts')
  const { DEFAULT_MAIN_MODEL } = await import('../src/config/models.ts')

  const model = DEFAULT_MAIN_MODEL
  console.log(`[conversation-harness] Using model: ${model}`)

  // -------------------------------------------------------------------------
  // SCENARIO 1: Conversation A (Multi-turn with progressive context chaining)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== SCENARIO 1: Conversation A — Multi-Turn & Context Memory ===')
  console.log('=============================================================')

  const convoAMessages = []

  // Turn 1: Presentation & context setup
  const userPrompt1 = "Je m'appelle Alex, je développe un outil nommé 'VortexGuard', un proxy réseau défensif écrit en Rust."
  console.log(`\n[Convo A - Turn 1] User: "${userPrompt1}"`)
  convoAMessages.push({ role: 'user', content: userPrompt1 })

  const result1 = await runConversationTurn({
    model,
    messages: convoAMessages,
    userInput: userPrompt1,
    onEvent: (ev) => {
      if (ev.type === 'stage') console.log(`  [Stage] ${ev.label} (${ev.progress}%): ${ev.detail}`)
    },
  })

  console.log(`\n[Convo A - Turn 1 Response]:\n${result1.finalText}\n`)
  convoAMessages.push({ role: 'assistant', content: result1.finalText })

  // Turn 2: Implicit context question (references "ce projet", requires remembering VortexGuard / Rust)
  const userPrompt2 = "Quels sont les 3 modules d'architecture prioritaires que tu me conseilles de concevoir pour ce projet ?"
  console.log(`\n[Convo A - Turn 2] User: "${userPrompt2}"`)
  convoAMessages.push({ role: 'user', content: userPrompt2 })

  const result2 = await runConversationTurn({
    model,
    messages: convoAMessages,
    userInput: userPrompt2,
    onEvent: (ev) => {
      if (ev.type === 'stage') console.log(`  [Stage] ${ev.label} (${ev.progress}%): ${ev.detail}`)
    },
  })

  console.log(`\n[Convo A - Turn 2 Response]:\n${result2.finalText}\n`)
  convoAMessages.push({ role: 'assistant', content: result2.finalText })

  // Turn 3: Deep follow-up referencing specific prior advice
  const userPrompt3 = "Pour le premier module que tu viens de me citer, donne-moi un squelette de code Rust structuré et propre."
  console.log(`\n[Convo A - Turn 3] User: "${userPrompt3}"`)
  convoAMessages.push({ role: 'user', content: userPrompt3 })

  const result3 = await runConversationTurn({
    model,
    messages: convoAMessages,
    userInput: userPrompt3,
    onEvent: (ev) => {
      if (ev.type === 'stage') console.log(`  [Stage] ${ev.label} (${ev.progress}%): ${ev.detail}`)
    },
  })

  console.log(`\n[Convo A - Turn 3 Response]:\n${result3.finalText}\n`)
  convoAMessages.push({ role: 'assistant', content: result3.finalText })

  // -------------------------------------------------------------------------
  // SCENARIO 2: Conversation B (Thread Isolation — Completely separate subject)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== SCENARIO 2: Conversation B — Thread Isolation Check ===')
  console.log('=============================================================')

  const convoBMessages = []

  const userPromptB1 = "Explique-moi les étapes principales de la photosynthèse chez les plantes terrestres."
  console.log(`\n[Convo B - Turn 1] User: "${userPromptB1}"`)
  convoBMessages.push({ role: 'user', content: userPromptB1 })

  const resultB1 = await runConversationTurn({
    model,
    messages: convoBMessages,
    userInput: userPromptB1,
    onEvent: (ev) => {
      if (ev.type === 'stage') console.log(`  [Stage] ${ev.label} (${ev.progress}%): ${ev.detail}`)
    },
  })

  console.log(`\n[Convo B - Turn 1 Response]:\n${resultB1.finalText}\n`)

  // -------------------------------------------------------------------------
  // Verification Analysis
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== VERIFICATION & DIAGNOSTIC REPORT ===')
  console.log('=============================================================')

  const text1 = result1.finalText.toLowerCase()
  const text2 = result2.finalText.toLowerCase()
  const text3 = result3.finalText.toLowerCase()
  const textB = resultB1.finalText.toLowerCase()

  const remembersRust = text2.includes('rust') || text3.includes('rust') || text2.includes('vortexguard') || text1.includes('alex') || text2.includes('proxy')
  const hasCodeRust = result3.finalText.includes('fn ') || result3.finalText.includes('struct ') || result3.finalText.includes('impl ') || result3.finalText.includes('pub ')
  const noRamblingA = !result2.finalText.includes('Je suis désolé') && result2.finalText.length > 80

  const leakedAlex = textB.includes('alex')
  const leakedVortex = textB.includes('vortexguard')
  const leakedRust = textB.includes('rust') && !textB.includes('chlorophylle')

  console.log(`- Convo A: Mémoire et suivi du contexte (Rust / VortexGuard / Alex) : ${remembersRust ? 'OUI (VALIDÉ)' : 'NON (ÉCHEC)'}`)
  console.log(`- Convo A: Code Rust produit en Turn 3 : ${hasCodeRust ? 'OUI (VALIDÉ)' : 'NON (ÉCHEC)'}`)
  console.log(`- Convo A: Clarté sans divagation : ${noRamblingA ? 'OUI (VALIDÉ)' : 'NON (ÉCHEC)'}`)
  console.log(`- Convo B: Isolation stricte du thread (pas de fuite d'Alex/VortexGuard) : ${(!leakedAlex && !leakedVortex && !leakedRust) ? 'PARFAITE (VALIDÉ)' : 'FUITE DÉTECTÉE (ÉCHEC)'}`)

  const allPassed = remembersRust && hasCodeRust && noRamblingA && !leakedAlex && !leakedVortex && !leakedRust
  console.log(`\nVERDICT GLOBAL DU TEST DE CONVERSATION : ${allPassed ? 'SUCCÈS TOTAL' : 'ATTENTION'}`)
}

main().catch((err) => {
  console.error('[conversation-harness] Fatal error:', err)
  process.exit(1)
})
