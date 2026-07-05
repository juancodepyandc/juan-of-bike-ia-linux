// cdp_tutor_img_test.mjs — vérifie sur le TUNNEL que l'IA prof accepte une
// image jointe (bouton 📎, vignette, input file présent) et que rien ne casse.
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const TUNNEL = process.argv[2] || 'https://map-friends-catalog-camps.trycloudflare.com'
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUT = process.argv[3] || 'C:\\Users\\Juan\\Desktop\\ia\\AuroraIA-v2'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
function freePort(){return new Promise((res,rej)=>{const s=net.createServer();s.listen(0,()=>{const p=s.address().port;s.close(()=>res(p))});s.on('error',rej)})}
async function getJSON(u){const r=await fetch(u);return r.json()}
class CDP{
  constructor(w){this.w=w;this.id=0;this.p=new Map();this.ev=[]}
  connect(){return new Promise((res,rej)=>{this.ws=new WebSocket(this.w);this.ws.onopen=()=>res();this.ws.onerror=rej;this.ws.onmessage=(m)=>{const x=JSON.parse(m.data);if(x.id&&this.p.has(x.id)){const{res,rej}=this.p.get(x.id);this.p.delete(x.id);x.error?rej(new Error(JSON.stringify(x.error))):res(x.result)}else if(x.method)this.ev.push(x)}})}
  send(method,params={}){const id=++this.id;return new Promise((res,rej)=>{this.p.set(id,{res,rej});this.ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(this.p.has(id)){this.p.delete(id);rej(new Error('timeout '+method))}},30000)})}
  async wait(method,ms=15000){const t=Date.now();while(Date.now()-t<ms){const e=this.ev.find(x=>x.method===method);if(e)return e;await sleep(100)}return null}
  async eval(expr){const r=await this.send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)console.warn('eval err:',r.exceptionDetails.text);return r.result?.value}
  async shot(p){const r=await this.send('Page.captureScreenshot',{format:'png'});writeFileSync(p,Buffer.from(r.data,'base64'))}
}
;(async()=>{
  const port=await freePort();const udd=mkdtempSync(join(tmpdir(),'aurora-tutori-'))
  const proc=spawn(CHROME,[`--remote-debugging-port=${port}`,`--user-data-dir=${udd}`,'--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions','--disable-gpu','--window-size=1366,950','about:blank'],{stdio:'ignore'})
  proc.on('error',e=>{console.error('chrome err',e);process.exit(1)})
  for(let i=0;i<40;i++){try{await getJSON(`http://127.0.0.1:${port}/json/version`);break}catch{await sleep(250)}}
  let tab;try{tab=await(await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(TUNNEL+'/')}`,{method:'PUT'})).json()}catch{const l=await getJSON(`http://127.0.0.1:${port}/json/list`);tab=l.find(t=>t.type==='page')}
  const cdp=new CDP(tab.webSocketDebuggerUrl);await cdp.connect();await cdp.send('Page.enable');await cdp.send('Runtime.enable');await cdp.send('DOM.enable')
  await cdp.send('Page.navigate',{url:TUNNEL+'/'});await cdp.wait('Page.loadEventFired',25000);await sleep(6500)
  await cdp.eval(`[...document.querySelectorAll('button')].find(b=>/Academy|Académie/i.test(b.textContent||''))?.click()`);await sleep(3000)
  await cdp.eval(`[...document.querySelectorAll('button')].find(b=>/Demande au prof/i.test(b.textContent||''))?.click()`);await sleep(1500)
  const txt=await cdp.eval('document.body.innerText')
  const m={
    hasFileInput: !!(await cdp.eval(`!!document.querySelector('input[type=file]')`)),
    welcomeMentionsPhoto: /coller ou joindre une photo|photo de ton cours/i.test(txt),
    placeholderMentionsPhoto: !!(await cdp.eval(`!!document.querySelector('input[placeholder*="photo"]')`)),
  }
  console.log('[tutor-img] markers UI :', JSON.stringify(m,null,2))
  // Attache une image 1x1 réelle via DOM.setFileInputFiles
  const pngB64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  const pixelPath=join(OUT,'_tutor_pixel.png'); writeFileSync(pixelPath,Buffer.from(pngB64,'base64'))
  const doc=await cdp.send('DOM.getDocument',{depth:-1})
  const q=await cdp.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'input[type=file]'})
  let attached=false
  if(q.nodeId){ try{ await cdp.send('DOM.setFileInputFiles',{files:[pixelPath],nodeId:q.nodeId}); attached=true }catch(e){ console.warn('setFileInputFiles:',e.message) } }
  await sleep(900)
  const thumbVisible = !!(await cdp.eval(`!!document.querySelector('img[src^="data:image"]')`))
  console.log('[tutor-img] image attachée via CDP :', attached, '· vignette base64 visible :', thumbVisible)
  await cdp.shot(join(OUT,'tunnel_test_7_tutor_img.png'))
  const errs=cdp.ev.filter(e=>e.method==='Runtime.exceptionThrown').map(e=>e.params?.exceptionDetails?.text||'?')
  console.log('[tutor-img] erreurs console =',errs.length,errs.slice(0,3))
  console.log('[tutor-img] DONE')
  await cdp.send('Browser.close').catch(()=>{});proc.kill();process.exit(0)
})().catch(e=>{console.error('[tutor-img] FATAL',e);process.exit(1)})
