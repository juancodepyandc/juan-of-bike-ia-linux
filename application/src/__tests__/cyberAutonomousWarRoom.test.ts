import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createInitialWarRoomState,
  executeWarRoomStep,
  WAR_ROOM_SCENARIOS,
} from '../services/cyber/autonomousWarRoom.ts'

describe('AutonomousWarRoomEngine', () => {
  test('Initialise un état de War Room cohérent', () => {
    const state = createInitialWarRoomState(0)
    assert.equal(state.tick, 0)
    assert.equal(state.phase, 'idle')
    assert.equal(state.redScore, 0)
    assert.equal(state.blueScore, 0)
    assert.ok(state.nodes.length >= 3, 'Au moins 3 nœuds cibles')
    assert.ok(state.events.length >= 1, 'Événement d initialisation présent')
    assert.equal(state.contained, false)
  })

  test('Exécute le cycle complet d engagement Red vs Blue jusqu au confinement et post-mortem', () => {
    let state = createInitialWarRoomState(0)
    for (let i = 1; i <= 8; i++) {
      state = executeWarRoomStep(state)
      assert.equal(state.tick, i)
    }
    assert.equal(state.phase, 'post-mortem')
    assert.equal(state.contained, true)
    assert.ok(state.redScore > 0, 'Score Red Team calculé')
    assert.ok(state.blueScore > 0, 'Score Blue Team calculé')
    assert.ok(state.activeSigmaRules.length > 0, 'Au moins une règle Sigma synthétisée')
    assert.ok(state.activeYaraRules.length > 0, 'Au moins une signature YARA générée')
    assert.ok(state.postMortemReport?.includes('Post-Mortem'), 'Rapport post-mortem généré')
  })
})
