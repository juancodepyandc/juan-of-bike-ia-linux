#!/usr/bin/env node
// Le banc de vraies générations, mode FLUX.2 : il doit soumettre le VRAI graphe
// FLUX.2-dev d'Aurora (flux_reference_synth, celui du module 3D) à ComfyUI, lire
// les pas de diffusion sur le websocket et relayer vues, pas et audit. ComfyUI
// est simulé ici (HTTP + websocket minimal) : ce test vérifie le câblage, pas la
// qualité des images FLUX.2, qui exige le PC avec GPU et poids.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import readline from 'node:readline'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import zlib from 'node:zlib'

const here = path.dirname(fileURLToPath(import.meta.url))
const STEPS = 5

/** PNG RGB minimal : fond blanc, sujet rayé (contours nets pour l'audit), largeur rx. */
function subjectPng(rx) {
  const W = 256
  const H = 256
  const raw = Buffer.alloc((W * 3 + 1) * H)
  for (let y = 0; y < H; y++) {
    raw[y * (W * 3 + 1)] = 0
    for (let x = 0; x < W; x++) {
      const inside = ((x - 128) / rx) ** 2 + ((y - 128) / 112) ** 2 <= 1
      const stripe = Math.floor(y / 6) % 2 === 0
      const c = inside ? (stripe ? [196, 48, 40] : [40, 70, 190]) : [255, 255, 255]
      c.forEach((v, k) => { raw[y * (W * 3 + 1) + 1 + x * 3 + k] = v })
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4)
    len.writeUInt32BE(data.length)
    const body = Buffer.concat([Buffer.from(type), data])
    const crc = Buffer.alloc(4)
    crc.writeUInt32BE(zlib.crc32(body) >>> 0)
    return Buffer.concat([len, body, crc])
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(W, 0)
  ihdr.writeUInt32BE(H, 4)
  ihdr[8] = 8
  ihdr[9] = 2
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

function frame(opcode, payload) {
  const len = payload.length
  const head = len < 126 ? Buffer.from([0x80 | opcode, len]) : Buffer.from([0x80 | opcode, 126, len >> 8, len & 255])
  return Buffer.concat([head, payload])
}

function mockComfy() {
  const sockets = new Set()
  const history = new Map()
  const graphs = []
  const pongs = []
  const broadcast = (msg) => { for (const s of sockets) s.write(frame(1, Buffer.from(JSON.stringify(msg)))) }
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    const json = (code, body) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)) }
    if (url.pathname === '/system_stats') return json(200, { devices: [{ name: 'cuda:0 simulé' }] })
    if (url.pathname === '/queue') return json(200, { queue_running: [...history].filter(([, v]) => !v).map(([id]) => [0, id]), queue_pending: [] })
    if (url.pathname.startsWith('/history/')) {
      const id = url.pathname.slice('/history/'.length)
      const entry = history.get(id)
      return json(200, entry ? { [id]: entry } : {})
    }
    if (url.pathname === '/view') {
      const name = url.searchParams.get('filename') || ''
      res.writeHead(200, { 'Content-Type': 'image/png' })
      return res.end(subjectPng(/_(left|right)_/.test(name) ? 34 : 78))
    }
    if (url.pathname === '/prompt' && req.method === 'POST') {
      let body = ''
      req.on('data', (c) => { body += c })
      req.on('end', () => {
        const { prompt } = JSON.parse(body)
        graphs.push(prompt)
        const id = crypto.randomUUID()
        history.set(id, null)
        const prefix = prompt['9']?.inputs?.filename_prefix || 'aurora'
        json(200, { prompt_id: id })
        for (let k = 1; k <= STEPS; k++) {
          setTimeout(() => {
            broadcast({ type: 'progress', data: { value: k, max: STEPS, prompt_id: id, node: '31' } })
            if (k === 2) for (const s of sockets) s.write(frame(2, Buffer.alloc(300, 7)))
            if (k === 3) for (const s of sockets) s.write(frame(9, Buffer.from('hb')))
          }, 60 * k)
        }
        setTimeout(() => {
          history.set(id, { status: { completed: true }, outputs: { 9: { images: [{ filename: `${prefix}_00001_.png`, subfolder: '', type: 'output' }] } } })
        }, 60 * STEPS + 80)
      })
      return
    }
    json(404, { error: 'not found' })
  })
  server.on('upgrade', (req, socket) => {
    const key = req.headers['sec-websocket-key']
    const accept = crypto.createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64')
    socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`)
    sockets.add(socket)
    socket.write(frame(1, Buffer.from(JSON.stringify({ type: 'status', data: { status: { exec_info: { queue_remaining: 0 } } } }))))
    socket.on('data', (d) => { if ((d[0] & 0x0f) === 0x0a) pongs.push(d) })
    socket.on('close', () => sockets.delete(socket))
    socket.on('error', () => sockets.delete(socket))
  })
  return { server, graphs, pongs, close: () => { for (const s of sockets) s.destroy(); server.close() } }
}

test('the FLUX.2 bench submits Aurora’s real FLUX.2 graph and relays real ComfyUI steps', { timeout: 120000 }, async () => {
  const mock = mockComfy()
  await new Promise((r) => mock.server.listen(0, '127.0.0.1', r))
  const port = mock.server.address().port
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'aurora-flux2-bench-'))
  const py = spawn(process.env.AURORA_TEST_PYTHON || 'python3', [
    path.join(here, 'real-gen', 'real_reference_views.py'),
    '--backend', 'comfy-flux2', '--comfy-base', `http://127.0.0.1:${port}`, '--output-dir', out, '--steps', String(STEPS), '--size', '512',
  ], { stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, OLLAMA_URL: 'http://127.0.0.1:9' } })
  let stderr = ''
  py.stderr.on('data', (c) => { stderr += c })
  const events = []
  const done = new Promise((resolve, reject) => {
    readline.createInterface({ input: py.stdout }).on('line', (line) => {
      try {
        const ev = JSON.parse(line)
        events.push(ev)
        if (ev.ev === 'done' || ev.ev === 'error') resolve(ev)
      } catch { /* ligne non JSON */ }
    })
    py.on('exit', (code) => reject(new Error(`exit ${code}\n${stderr}`)))
  })
  try {
    py.stdin.write(JSON.stringify({ id: 'benchA', request: 'un robot jouet jaune et bleu', seed: 7 }) + '\n')
    const last = await done
    assert.equal(last.ev, 'done', JSON.stringify(last))
    const ready = events.find((e) => e.ev === 'backend_ready')
    assert.equal(ready.unet, 'flux2-dev-Q4_K_M.gguf')
    assert.equal(events.find((e) => e.ev === 'start').websocket, true, 'progress websocket connected before the run')

    // The graph is Aurora's FLUX.2-dev production graph, one per view.
    assert.equal(mock.graphs.length, 4)
    for (const g of mock.graphs) {
      const types = Object.values(g).map((n) => n.class_type)
      for (const t of ['UnetLoaderGGUF', 'CLIPLoader', 'EmptyFlux2LatentImage', 'Flux2Scheduler', 'SamplerCustomAdvanced', 'CFGGuider', 'SaveImage']) assert.ok(types.includes(t), `${t} in graph`)
      assert.equal(g['40'].inputs.steps, STEPS)
      assert.equal(g['11'].inputs.type, 'flux2')
    }
    assert.match(mock.graphs[2]['6'].inputs.text, /exact left side profile view, 90 degree side view/)

    // Views in production order, with the real sampler steps between start and end.
    const starts = events.filter((e) => e.ev === 'view_start').map((e) => e.view)
    assert.deepEqual(starts, ['face', 'dos', 'gauche', 'droite'])
    for (const view of starts) {
      const steps = events.filter((e) => e.ev === 'step' && e.view === view)
      assert.ok(steps.length >= STEPS - 1, `${view}: ${steps.length} steps relayed`)
      assert.ok(steps.every((s) => s.steps === STEPS && s.total === 4))
      const s = events.findIndex((e) => e.ev === 'view_start' && e.view === view)
      const d = events.findIndex((e) => e.ev === 'view_done' && e.view === view)
      assert.ok(s < d && events.slice(s, d).some((e) => e.ev === 'step'), `${view}: steps arrive while the view runs`)
      assert.ok(fs.existsSync(events[d].path), `${view}: image saved`)
    }
    assert.equal(last.views.length, 4)
    assert.equal(last.ok, true, `turnaround audit: ${JSON.stringify(last.audit_failures)}`)
    assert.ok(mock.pongs.length >= 1, 'ping answered')
  } finally {
    py.stdin.end()
    py.kill()
    mock.close()
    fs.rmSync(out, { recursive: true, force: true })
  }
})
