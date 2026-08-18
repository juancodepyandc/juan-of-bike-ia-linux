import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, test } from 'node:test'

import { withTimeout } from '../services/llmTimebox.ts'

import {
  CALLER_CANCEL_MARK,
  FIRST_BYTE_TIMEOUT_MARK,
  createFirstByteWatchdog,
  isCallerCancellation,
  isFirstByteTimeout,
} from '../services/ollamaFirstByteWatchdog.ts'
import {
  isCancellationMessage,
  isInfrastructureFailureMessage,
} from '../services/codeInfrastructureFailure.ts'
import { buildInterruptedDelivery } from '../services/codeInterruptedDelivery.ts'

/** Ordonnanceur factice: on declenche les minuteries a la main. */
function fakeClock() {
  const pending = new Map<number, () => void>()
  let nextId = 1
  return {
    setTimeoutImpl: (fn: () => void, _ms: number) => {
      const id = nextId++
      pending.set(id, fn)
      return id
    },
    clearTimeoutImpl: (handle: unknown) => {
      pending.delete(handle as number)
    },
    armedCount: () => pending.size,
    fireAll: () => {
      for (const [id, fn] of [...pending]) {
        pending.delete(id)
        fn()
      }
    },
  }
}

describe('ollamaFirstByteWatchdog — le budget mesure ce qu il pretend', () => {
  test('le budget est REARME a chaque point d entree, pas partage par la cascade', () => {
    // Regression du run v125: 480 s pour la cascade entiere. Le bridge relaie
    // Ollama avec un timeout de 180 s, donc deux points d entree condamnes
    // brulaient 360 s du budget avant que le troisieme — le seul capable
    // d aboutir — soit tente. Le chien de garde coupait alors en pleine
    // generation.
    const clock = fakeClock()
    const watchdog = createFirstByteWatchdog({ model: 'qwen3-coder:30b', budgetMs: 480_000, ...clock })

    watchdog.arm('http://bridge/proxy/ollama/api/chat')
    assert.equal(clock.armedCount(), 1)
    // Le point d entree suivant repart avec un budget ENTIER: l ancienne
    // minuterie doit avoir disparu, pas s etre accumulee.
    watchdog.arm('http://bridge/api/ollama/chat')
    assert.equal(clock.armedCount(), 1)
    watchdog.arm('http://127.0.0.1:11434/api/chat')
    assert.equal(clock.armedCount(), 1)
    assert.equal(watchdog.signal.aborted, false, 'aucun abandon apres trois tentatives armees')

    // Desarme des les en-tetes: le budget ne borne jamais la duree du flux.
    watchdog.disarm()
    assert.equal(clock.armedCount(), 0)
    clock.fireAll()
    assert.equal(watchdog.signal.aborted, false, 'le flux ne peut plus etre coupe par le budget TTFB')
  })

  test('l abandon nomme le point d entree, le modele et le budget', () => {
    const clock = fakeClock()
    const watchdog = createFirstByteWatchdog({ model: 'qwen3-coder:30b', budgetMs: 480_000, ...clock })
    watchdog.arm('http://127.0.0.1:11434/api/chat')
    clock.fireAll()

    assert.equal(watchdog.signal.aborted, true)
    const reason = watchdog.signal.reason as Error
    // Le run v125 est mort sur « This operation was aborted »: un message qui ne
    // nomme ni le modele, ni l appel, ni le budget, ni meme le fait qu il
    // s agisse d un delai. C est pour cela que ~35 runs ne l ont pas identifie.
    assert.notEqual(reason.message, 'This operation was aborted')
    assert.match(reason.message, /premier octet absent/)
    assert.match(reason.message, /480s/)
    assert.match(reason.message, /127\.0\.0\.1:11434/)
    assert.match(reason.message, /qwen3-coder:30b/)
    assert.equal(watchdog.timedOutOn(), 'http://127.0.0.1:11434/api/chat')
    assert.ok(isFirstByteTimeout(reason))
    assert.ok(!isCallerCancellation(reason))
  })

  test('une annulation de l appelant reste une annulation, pas un delai', () => {
    const clock = fakeClock()
    const caller = new AbortController()
    const watchdog = createFirstByteWatchdog({ model: 'm', budgetMs: 1_000, callerSignal: caller.signal, ...clock })
    watchdog.arm('http://x/api/chat')

    caller.abort()

    assert.equal(watchdog.signal.aborted, true)
    const reason = watchdog.signal.reason as Error
    assert.ok(isCallerCancellation(reason))
    assert.ok(!isFirstByteTimeout(reason))
    // La minuterie est desarmee: un arret demande ne doit pas se transformer en
    // delai depasse quelques secondes plus tard.
    assert.equal(clock.armedCount(), 0)
  })

  test('un signal appelant deja abandonne coupe immediatement', () => {
    const caller = new AbortController()
    caller.abort()
    const watchdog = createFirstByteWatchdog({ model: 'm', budgetMs: 1_000, callerSignal: caller.signal, ...fakeClock() })
    assert.equal(watchdog.signal.aborted, true)
    assert.ok(isCallerCancellation(watchdog.signal.reason))
  })

  test('dispose detache l ecoute du signal appelant', () => {
    const clock = fakeClock()
    const caller = new AbortController()
    const watchdog = createFirstByteWatchdog({ model: 'm', budgetMs: 1_000, callerSignal: caller.signal, ...clock })
    watchdog.dispose()
    caller.abort()
    assert.equal(watchdog.signal.aborted, false, 'plus aucune reaction apres dispose')
  })
})

describe('un budget qui abandonne doit ARRETER ce qu il abandonne', () => {
  test('withTimeout seul n annule rien: la mesure qui justifie le signal par tentative', async () => {
    // Mesure du mecanisme, pas une opinion. `withTimeout` est un
    // `Promise.race`: quand le budget gagne, l operation perdante CONTINUE.
    // Applique a un appel Ollama, cela veut dire que le modele reste occupe
    // pendant que la tentative suivante en charge un autre — exactement la
    // contention relevee dans le journal Ollama du run v125 (cinq POST
    // /api/generate simultanes, chargement de modele avorte a 3m30s).
    let stillRunning = false
    let finished = false
    const operation = (async () => {
      stillRunning = true
      await new Promise((resolve) => setTimeout(resolve, 40))
      finished = true
    })()

    await assert.rejects(withTimeout(operation, { label: 'sonde', timeoutMs: 1 }), /timed out after 1ms/)
    assert.equal(stillRunning, true)
    assert.equal(finished, false, 'l operation n est pas terminee — et surtout, elle n est pas arretee')

    await operation
    assert.equal(finished, true, 'elle s est terminee toute seule APRES l abandon: rien ne l avait stoppee')
  })

  test('le budget d une tentative se propage bien en signal jusqu a l appel modele', () => {
    // Garde de source, dans l esprit de codeModuleStructure.test.ts: les
    // closures passees a `withResilience` doivent transmettre le signal DE LA
    // TENTATIVE, jamais celui de l appelant. Sinon l annulation declenchee par
    // l expiration du budget n atteint pas l appel et le modele reste occupe.
    const source = readFileSync('src/services/ollamaResilience.ts', 'utf8')
    const closureBodies = source.slice(source.indexOf('async function withResilience'))
    assert.doesNotMatch(
      closureBodies,
      /signal: opts\?\.signal,/,
      'une closure transmet encore le signal de l appelant au lieu de celui de la tentative',
    )
    assert.match(source, /execute: \(model: string, attemptSignal: AbortSignal \| undefined\) => Promise<T>/)
    assert.match(source, /if \(isLlmTimeboxError\(err\)\) \{/)
    assert.match(source, /opts\?\.signal\?\.removeEventListener\('abort', relayCallerAbort\)/)
  })
})

describe('classification: un delai n est pas un verdict sur le code', () => {
  test('le delai de premier octet est reconnu comme panne d infrastructure', () => {
    const message = `Ollama: ${FIRST_BYTE_TIMEOUT_MARK} apres 480s sur http://x (modele m) — delai depasse, aucun octet recu`
    assert.ok(isInfrastructureFailureMessage(message))
    assert.ok(!isCancellationMessage(message))

    const delivery = buildInterruptedDelivery(message, [{ name: 'a.ts', language: 'ts', content: 'x' }], '')
    assert.equal(delivery.cause, 'panne d infrastructure')
    assert.equal(delivery.infrastructure, true)
    assert.match(delivery.notes, /aucune conclusion sur sa qualite/)
  })

  test('une annulation est livree comme annulation, ni panne ni erreur du pipeline', () => {
    const message = `Generation interrompue: ${CALLER_CANCEL_MARK}`
    assert.ok(isCancellationMessage(message))
    const delivery = buildInterruptedDelivery(message, [{ name: 'a.ts', language: 'ts', content: 'x' }], '')
    assert.equal(delivery.cause, 'annulation demandee')
    assert.equal(delivery.infrastructure, false)
    assert.match(delivery.notes, /L arret est une decision, pas un verdict/)
  })

  test('« This operation was aborted » n est plus classe comme erreur du pipeline', () => {
    // Le message exact qui a tue le run v125. Meme si plus aucun chien de garde
    // ne le produit, il ne doit jamais redevenir un verdict sur le livrable.
    const delivery = buildInterruptedDelivery('This operation was aborted', [{ name: 'a.ts', language: 'ts', content: 'x' }], '')
    assert.notEqual(delivery.cause, 'erreur du pipeline')
    assert.equal(delivery.cause, 'annulation demandee')
  })

  test('une vraie erreur de code reste une erreur du pipeline', () => {
    const delivery = buildInterruptedDelivery("Cannot read properties of undefined (reading 'map')", [{ name: 'a.ts', language: 'ts', content: 'x' }], '')
    assert.equal(delivery.cause, 'erreur du pipeline')
    assert.equal(delivery.infrastructure, false)
  })

  test('un flux coupe par le relais est une panne, pas un defaut du code', () => {
    assert.ok(isInfrastructureFailureMessage('TypeError: terminated — SocketError: other side closed'))
  })

  test('BALAYAGE: les causes fatales REELLEMENT observees sont classees correctement', () => {
    // Chaines relevees telles quelles dans les `run.log` d audit conserves.
    // Trois des cinq causes distinctes etaient rangees en « erreur du pipeline ».
    const observedInfrastructure = [
      'Ollama: budget de recuperation epuise apres 20 min. Le travail deja produit est preserve; ce n est PAS un verdict de qualite. Derniere erreur: Ollama qwen3-coder:30b timed out after 1200000ms',
      'Ollama: toutes les tentatives epuisees (6). Modeles testes: qwen3-coder:30b, qwen3-coder:30b. Derniere erreur: fetch failed',
      'Ollama: toutes les tentatives epuisees (3). Modeles testes: qwen3-coder:30b. Derniere erreur: Ollama error: 500',
    ]
    for (const message of observedInfrastructure) {
      assert.ok(isInfrastructureFailureMessage(message), `doit etre une panne: ${message.slice(0, 60)}`)
      assert.equal(buildInterruptedDelivery(message, [{ name: 'a.ts', language: 'ts', content: 'x' }], '').cause, 'panne d infrastructure')
    }

    // Ces deux-la sont de VRAIES erreurs de pipeline et doivent le rester: le
    // classifieur doit rester etroit, sinon il absout tout.
    const observedPipelineErrors = [
      'Echec de l executor agentique WS3: action_producer_failed:action_protocol_invalid:protocol_marker_missing',
      'agentic_retry_failed:patch_search_not_found',
    ]
    for (const message of observedPipelineErrors) {
      assert.ok(!isInfrastructureFailureMessage(message), `doit rester une erreur de pipeline: ${message.slice(0, 60)}`)
      assert.equal(buildInterruptedDelivery(message, [{ name: 'a.ts', language: 'ts', content: 'x' }], '').cause, 'erreur du pipeline')
    }
  })
})
