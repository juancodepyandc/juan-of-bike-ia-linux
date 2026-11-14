#!/usr/bin/env node
// Pure reading of the professor autopilot status; no bridge, no Kaggle, no Ollama.
import assert from 'node:assert/strict'
import { test } from 'node:test'

const { describeStatus, describeStudent, formatDuration } = await import('../src/utils/professorStatus.ts')

const base = {
  enabled: true, running: true, busy: null, activate: true, owner: 'compte',
  quota: { remaining_seconds: 6053, refresh_at: 1794614400 },
  students: {
    'qwen2.5:7b': { phase: 'waiting_quota', cycle: 4, best_cycle: 3, installed_cycle: 3, kernel: null, until: 1794614400, why: 'verify', deliveries: [] },
    'qwen2.5-coder:7b': { phase: 'training', cycle: 2, best_cycle: 0, installed_cycle: 0, kernel: 'compte/k-c2', until: null, why: null, deliveries: [] },
  },
  events: [{ at: 1794600000, student: 'qwen2.5:7b', message: 'cycle 3 : installé' }],
}

test('a running autopilot offers stop, not start, and names each student state in French', () => {
  const view = describeStatus(base)
  assert.equal(view.supported, true)
  assert.equal(view.canStart, false)
  assert.equal(view.canStop, true)
  assert.equal(view.tone, 'running')
  assert.match(view.quota, /1 h 41 de GPU Kaggle restantes/)
  const [q25, coder] = view.students
  assert.equal(q25.phase, 'en attente du quota Kaggle')
  assert.match(q25.detail, /reprise vers/)
  assert.equal(coder.active, true)
  assert.match(coder.detail, /cycle 2/)
  assert.equal(view.events[0].text, 'qwen2.5:7b : cycle 3 : installé')
})

test('an enabled autopilot without heartbeat is reported as interrupted and can be started again', () => {
  const view = describeStatus({ ...base, running: false })
  assert.equal(view.canStart, true)
  assert.equal(view.canStop, false)
  assert.equal(view.tone, 'warning')
  assert.match(view.headline, /interrompu/)
})

test('a stop request keeps the stop button off until the runner confirms', () => {
  const view = describeStatus({ ...base, enabled: false, running: true })
  assert.equal(view.canStop, false)
  assert.equal(view.canStart, false)
  assert.match(view.headline, /Arrêt demandé/)
})

test('missing numbers read « non mesuré », never 0', () => {
  const view = describeStatus({ ...base, quota: null })
  assert.equal(view.quota, 'quota Kaggle non mesuré')
  assert.equal(formatDuration(undefined), 'non mesuré')
  const student = describeStudent('x', { phase: 'ready', cycle: null, best_cycle: null, installed_cycle: null, kernel: null, until: null, why: null })
  assert.equal(student.best, 'aucun')
  assert.equal(student.installed, 'aucun')
})

test('a paused student and a refused exam are explained, an unsupported PC disables both buttons', () => {
  const paused = describeStudent('x', { phase: 'stalled', cycle: 3, best_cycle: 1, installed_cycle: 1, kernel: null, until: null,
    why: '2 cycles de suite sans amélioration vérifiée', last: { cycle: 3, verdict: 'reject', problems: ['régression'] } })
  assert.equal(paused.warning, true)
  assert.match(paused.detail, /sans amélioration vérifiée/)
  assert.match(paused.detail, /cycle 3 refusé/)
  const off = describeStatus({ supported: false, error: 'Identifiants Kaggle absents sur ce PC.' })
  assert.equal(off.canStart, false)
  assert.equal(off.canStop, false)
  assert.equal(off.headline, 'Identifiants Kaggle absents sur ce PC.')
})
