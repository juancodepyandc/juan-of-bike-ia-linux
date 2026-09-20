import assert from 'node:assert/strict'
import { test } from 'node:test'
import { completedComfyImages, waitForComfyImages } from '../services/comfyJobMonitor.ts'

const ready = (filename = 'final.png') => ({ job: {
  status: { completed: true, status_str: 'success' },
  outputs: { save: { images: [{ filename, subfolder: 'explanations', type: 'output' }] } },
} })
const options = { pollMs: 1, timeoutMs: 1000 }

test('selects only the requested job and preserves the output folder', () => {
  assert.equal(completedComfyImages({ other: ready().job }, 'job'), null)
  assert.deepEqual(completedComfyImages(ready(), 'job'), [{ filename: 'final.png', subfolder: 'explanations' }])
})

test('does not deliver a temporary preview or an unfinished output', () => {
  const history = ready()
  history.job.status.completed = false
  history.job.status.status_str = 'running'
  assert.equal(completedComfyImages(history, 'job'), null)
  history.job.status.completed = true
  history.job.outputs.save.images[0].type = 'temp'
  assert.throws(() => completedComfyImages(history, 'job'), /sans image/)
})

test('reports an execution error on the first poll', async () => {
  let polls = 0
  await assert.rejects(waitForComfyImages('job', new AbortController().signal, async () => {
    polls += 1
    return { job: { status: { status_str: 'error', messages: [
      ['execution_error', { exception_message: 'CUDA out of memory' }],
    ] } } }
  }, options), /CUDA out of memory/)
  assert.equal(polls, 1)
})

test('rejects interrupted or empty completed jobs', () => {
  assert.throws(() => completedComfyImages({ job: { status: { messages: [['execution_interrupted', {}]] } } }, 'job'), /interrompue/)
  assert.throws(() => completedComfyImages({ job: { status: { completed: true }, outputs: {} } }, 'job'), /sans image/)
})

test('waits through a queue and recovers after a transient connection failure', async () => {
  let polls = 0
  const output = await waitForComfyImages('job', new AbortController().signal, async () => {
    polls += 1
    if (polls === 1) throw new Error('connection reset')
    return polls === 2 ? {} : ready()
  }, options)
  assert.equal(polls, 3)
  assert.equal(output[0].filename, 'final.png')
})

test('bounds repeated transport failures and identifies the retained job', async () => {
  let polls = 0
  await assert.rejects(waitForComfyImages('job', new AbortController().signal, async () => {
    polls += 1
    throw new Error('offline')
  }, { ...options, maxConnectionFailures: 3 }), /tâche job conservée/)
  assert.equal(polls, 3)
})

test('cancels even when a history request never settles', async () => {
  const controller = new AbortController()
  const pending = waitForComfyImages('job', controller.signal, () => new Promise(() => {}), options)
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
})

test('enforces the follow-up deadline even with a stalled request', async () => {
  await assert.rejects(waitForComfyImages('job', new AbortController().signal, () => new Promise(() => {}), {
    timeoutMs: 10, pollMs: 1,
  }), /délai de suivi dépassé/)
})

test('does not request history after cancellation', async () => {
  const controller = new AbortController()
  controller.abort()
  let polls = 0
  await assert.rejects(waitForComfyImages('job', controller.signal, async () => {
    polls += 1
    return ready()
  }, options), { name: 'AbortError' })
  assert.equal(polls, 0)
})
