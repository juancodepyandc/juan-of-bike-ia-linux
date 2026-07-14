// Capture a GLB through the REAL viewer path (three.js + RoomEnvironment IBL +
// ACES tone mapping, matching ModelView) using the playwright chromium. Renders
// several azimuths and, for animated GLBs, several animation times.
// Usage: node drive_view.mjs <glb_abs_or_repo_rel> <out_dir> [label] [t0,t1,...]
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const CHROME = '/home/juan/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
const REPO = '/home/juan/AuroraIA'
const GLB_IN = process.argv[2]
const OUT = process.argv[3] || '/tmp/viewcap_out'
const LABEL = process.argv[4] || 'view'
const TIMES = (process.argv[5] || '0').split(',').map(Number)
const GLB = GLB_IN.startsWith('/') ? GLB_IN.replace(REPO, '') : '/' + GLB_IN
// HEAD=1 -> gros plan sur la tete (viewcap.html ?head=1). Indispensable pour juger
// la nettete du visage: en plan large il ne fait que ~120px et tout ecart est invisible.
// AZ0 = azimut de la VRAIE face (face_refine le mesure: 'front_azimuth'). Sans lui
// on cadre un 3/4 et on mesure la nettete du mauvais cote du crane.
const HEAD = process.env.HEAD === '1'
const AZ0 = parseFloat(process.env.AZ0 || '0')
const ANGLES = HEAD
  ? [{ az: AZ0, el: 0, n: 'face' }, { az: AZ0 + 30, el: 5, n: 'a30' }, { az: AZ0 - 30, el: 5, n: 'aneg30' }]
  : [{ az: 35, el: 12, n: 'a35' }, { az: -40, el: 10, n: 'aneg40' }, { az: 90, el: 8, n: 'side' }]
mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
function freePort() { return new Promise((res, rej) => { const s = net.createServer(); s.listen(0, () => { const p = s.address().port; s.close(() => res(p)) }); s.on('error', rej) }) }
async function getJSON(u) { const r = await fetch(u); const t = await r.text(); const i = t.search(/[\[{]/); return JSON.parse(i >= 0 ? t.slice(i) : t) }
class CDP {
  constructor(w) { this.w = w; this.id = 0; this.p = new Map() }
  connect() { return new Promise((res, rej) => { this.ws = new WebSocket(this.w); this.ws.onopen = () => res(); this.ws.onerror = rej; this.ws.onmessage = (m) => { const x = JSON.parse(m.data); if (x.id && this.p.has(x.id)) { const { res, rej } = this.p.get(x.id); this.p.delete(x.id); x.error ? rej(new Error(JSON.stringify(x.error))) : res(x.result) } } }) }
  send(method, params = {}) { const id = ++this.id; return new Promise((res, rej) => { this.p.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params })); setTimeout(() => { if (this.p.has(id)) { this.p.delete(id); rej(new Error('timeout ' + method)) } }, 45000) }) }
  async evalJS(e) { const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); return r.result?.value }
  async shot(path) { const r = await this.send('Page.captureScreenshot', { format: 'png' }); writeFileSync(path, Buffer.from(r.data, 'base64')) }
}
;(async () => {
  const sp = await freePort()
  const server = spawn('python3', ['-m', 'http.server', String(sp), '--directory', REPO, '--bind', '127.0.0.1'], { stdio: 'ignore' })
  for (let i = 0; i < 30; i++) { try { const r = await fetch(`http://127.0.0.1:${sp}/scratchpad/viewcap/viewcap.html`); if (r.ok) break } catch {} await sleep(200) }
  const port = await freePort()
  const udd = mkdtempSync(join(tmpdir(), 'vcap-'))
  const proc = spawn(CHROME, [`--remote-debugging-port=${port}`, `--user-data-dir=${udd}`, '--headless=new', '--no-first-run', '--no-sandbox', '--disable-gpu-sandbox', '--enable-webgl', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--window-size=1024,1024', 'about:blank'], { stdio: 'ignore' })
  let ver = null; for (let i = 0; i < 40; i++) { try { ver = await getJSON(`http://127.0.0.1:${port}/json/version`); break } catch { await sleep(250) } }
  if (!ver) { console.error('devtools down'); proc.kill(); server.kill(); process.exit(1) }
  for (const ang of ANGLES) {
    const url = `http://127.0.0.1:${sp}/scratchpad/viewcap/viewcap.html?glb=${encodeURIComponent(GLB)}&az=${ang.az}&el=${ang.el}${HEAD ? '&head=1' : ''}`
    let tab
    try { const r = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' }); const t = await r.text(); const s = t.search(/[\[{]/); tab = JSON.parse(s >= 0 ? t.slice(s) : t) } catch {}
    if (!tab?.webSocketDebuggerUrl) { const l = await getJSON(`http://127.0.0.1:${port}/json/list`); tab = l.find((t) => t.type === 'page') }
    const cdp = new CDP(tab.webSocketDebuggerUrl); await cdp.connect()
    await cdp.send('Page.enable'); await cdp.send('Runtime.enable'); await cdp.send('Page.navigate', { url })
    let st = null; for (let i = 0; i < 120; i++) { st = await cdp.evalJS('window.__status'); if (st === 'ready' || (st && st.startsWith('error'))) break; await sleep(250) }
    const gl = await cdp.evalJS('window.__glError')
    if (st !== 'ready') { console.log(`ANGLE ${ang.n}: NOT READY (${st})`); await cdp.send('Target.closeTarget', { targetId: tab.id }).catch(() => {}); continue }
    for (const t of TIMES) {
      await cdp.evalJS(`window.__renderAt(${t})`); await sleep(120)
      const suffix = TIMES.length > 1 ? `_t${String(t).replace('.', '_')}` : ''
      await cdp.shot(join(OUT, `${LABEL}_${ang.n}${suffix}.png`))
    }
    console.log(`ANGLE ${ang.n}: ok (gl_error=${gl})`)
    await cdp.send('Target.closeTarget', { targetId: tab.id }).catch(() => {})
  }
  console.log('VIEWCAP_DONE out=' + OUT)
  proc.kill(); server.kill(); process.exit(0)
})().catch((e) => { console.error('FATAL', e); process.exit(1) })
