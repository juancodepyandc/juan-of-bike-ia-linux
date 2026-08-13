import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  RECOVERY_TOTAL_BUDGET_MS,
  TRANSPORT_BACKOFF_MS,
  isTransportFailure,
} from '../services/codeTransportBackoff.ts'

describe('budget de recuperation — une horloge borne, pas un compteur', () => {
  // Run 1131: la passe 8 est entree en recuperation a 15:13:40 et en est sortie
  // a 16:13:09. 59,5 minutes pour UN appel, 24 cycles, rien qui avance.
  test('le budget est de l ordre de la dizaine de minutes, pas de l heure', () => {
    assert.ok(RECOVERY_TOTAL_BUDGET_MS >= 5 * 60_000, 'trop court pour un service qui revient')
    assert.ok(RECOVERY_TOTAL_BUDGET_MS <= 15 * 60_000, 'une heure de tourniquet est un echec')
  })

  test('le compte de tentatives ne borne RIEN a lui seul', () => {
    // C est la mesure qui a rendu le budget necessaire: le bareme de backoff
    // totalise ~2 minutes, mais chaque tentative peut consommer le timeout
    // complet de l appelant (20 min pour une correction). Six tentatives x
    // 20 min = 2 h. Le nombre de tentatives ne dit donc rien de la duree.
    const backoffTotalMs = TRANSPORT_BACKOFF_MS.reduce((sum, ms) => sum + ms, 0)
    const worstCaseMs = TRANSPORT_BACKOFF_MS.length * 20 * 60_000
    assert.ok(backoffTotalMs < 5 * 60_000)
    assert.ok(worstCaseMs > RECOVERY_TOTAL_BUDGET_MS * 5)
  })

  test('une panne de transport reste reconnue comme telle', () => {
    for (const message of ['fetch failed', 'ECONNREFUSED 127.0.0.1:11434', 'socket hang up']) {
      assert.equal(isTransportFailure(message), true, message)
    }
    assert.equal(isTransportFailure('CUDA out of memory'), false)
  })
})
