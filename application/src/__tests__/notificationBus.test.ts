/**
 * Tests pour utils/notificationBus — pub/sub minimal.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { subscribe, emit, type NotifEvent } from '../utils/notificationBus.ts'

describe('notificationBus.subscribe / emit', () => {
  test('subscribe puis emit → handler reçoit l évènement', () => {
    let received: NotifEvent | null = null
    const off = subscribe((ev) => { received = ev })
    emit({ kind: 'info', title: 'hello' })
    off()
    assert.ok(received !== null)
    assert.equal(received!.kind, 'info')
    assert.equal(received!.title, 'hello')
  })

  test('unsubscribe → plus d évènements reçus', () => {
    let count = 0
    const off = subscribe(() => { count++ })
    emit({ kind: 'info', title: 'a' })
    off()
    emit({ kind: 'info', title: 'b' })
    assert.equal(count, 1)
  })

  test('multiple subscribers → tous notifiés', () => {
    const received: number[] = []
    const off1 = subscribe(() => received.push(1))
    const off2 = subscribe(() => received.push(2))
    const off3 = subscribe(() => received.push(3))
    emit({ kind: 'info', title: 'x' })
    off1(); off2(); off3()
    assert.deepEqual(received.sort(), [1, 2, 3])
  })

  test('id auto-incrémenté', () => {
    const ev1 = emit({ kind: 'info', title: '1' })
    const ev2 = emit({ kind: 'info', title: '2' })
    assert.ok(ev2.id > ev1.id)
  })

  test('timestamp "at" présent', () => {
    const before = Date.now()
    const ev = emit({ kind: 'info', title: 'ts test' })
    const after = Date.now()
    assert.ok(ev.at >= before && ev.at <= after)
  })

  test('handler qui throw ne casse pas le bus', () => {
    let secondHandlerCalled = false
    const off1 = subscribe(() => { throw new Error('subscriber crashed') })
    const off2 = subscribe(() => { secondHandlerCalled = true })
    emit({ kind: 'info', title: 'survive' })
    off1(); off2()
    assert.equal(secondHandlerCalled, true)
  })

  test('event payload préservé (source, body, tone, seal)', () => {
    let received: NotifEvent | null = null
    const off = subscribe((ev) => { received = ev })
    emit({
      kind: 'generation.finished',
      source: 'image',
      title: 'Done',
      body: 'Image generation complete',
      jobId: 'job-123',
      tone: 'ok',
      seal: '◉',
    })
    off()
    assert.equal(received!.source, 'image')
    assert.equal(received!.body, 'Image generation complete')
    assert.equal(received!.jobId, 'job-123')
    assert.equal(received!.tone, 'ok')
    assert.equal(received!.seal, '◉')
  })

  test('plusieurs unsubscribe en cascade', () => {
    let n = 0
    const off1 = subscribe(() => { n++ })
    const off2 = subscribe(() => { n++ })
    emit({ kind: 'info', title: '1' })
    assert.equal(n, 2)
    off1()
    emit({ kind: 'info', title: '2' })
    assert.equal(n, 3) // un seul handler restant
    off2()
    emit({ kind: 'info', title: '3' })
    assert.equal(n, 3) // plus aucun handler
  })
})
