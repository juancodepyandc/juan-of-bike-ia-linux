// Pilote CDP minimal (WebSocket natif node 24, zero dependance) pour piloter
// le site Aurora reel sur localhost:1420.
//
// On passe par l'endpoint BROWSER + Target.attachToTarget{flatten:true} :
// la connexion directe /devtools/page/<id> s'ouvre mais ne repond pas aux
// commandes sur ce Chrome — le canal browser+sessionId, lui, marche.
//
// Usage :
//   import { connect } from './cdp.mjs'
//   const c = await connect()
//   await c.eval('document.title')
//   await c.setFiles('input[type=file]', ['/path/to/file'])
//   c.close()
const PORT = process.env.CDP_PORT || '9223'
const DEBUG = `http://127.0.0.1:${PORT}`

export async function connect(urlMatch = 'localhost:1420') {
  const ver = await fetch(`${DEBUG}/json/version`).then((r) => r.json())
  const ws = new WebSocket(ver.webSocketDebuggerUrl)
  let id = 0
  const pending = new Map()
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data)
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  })
  await new Promise((res, rej) => {
    const t = setTimeout(() => rej(new Error('WS open timeout')), 8000)
    ws.addEventListener('open', () => { clearTimeout(t); res() })
    ws.addEventListener('error', (e) => { clearTimeout(t); rej(new Error('WS error ' + (e?.message || ''))) })
  })

  const rawSend = (method, params = {}, sessionId) => {
    const i = ++id
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => { pending.delete(i); reject(new Error(`${method}: timeout`)) }, 20000)
      pending.set(i, (m) => { clearTimeout(t); m.error ? reject(new Error(`${method}: ${JSON.stringify(m.error)}`)) : resolve(m.result) })
      ws.send(JSON.stringify({ id: i, method, params, sessionId }))
    })
  }

  const { targetInfos } = await rawSend('Target.getTargets')
  const page = targetInfos.find((t) => t.type === 'page' && (t.url || '').includes(urlMatch))
  if (!page) throw new Error('cible page introuvable')
  const { sessionId } = await rawSend('Target.attachToTarget', { targetId: page.targetId, flatten: true })

  const send = (method, params = {}) => rawSend(method, params, sessionId)
  await send('Runtime.enable').catch(() => {})
  await send('DOM.enable').catch(() => {})

  const evaluate = async (expression, opts = {}) => {
    const r = await send('Runtime.evaluate', {
      expression,
      returnByValue: opts.byValue !== false,
      awaitPromise: true,
      userGesture: true,
    })
    if (r.exceptionDetails) throw new Error('JS: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text))
    return opts.byValue === false ? r.result : r.result?.value
  }
  const setFiles = async (selector, files) => {
    const r = await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(selector)})`, returnByValue: false })
    const objectId = r.result?.objectId
    if (!objectId) throw new Error(`input introuvable: ${selector}`)
    await send('DOM.setFileInputFiles', { files, objectId })
  }
  return { send, eval: evaluate, setFiles, close: () => ws.close() }
}
