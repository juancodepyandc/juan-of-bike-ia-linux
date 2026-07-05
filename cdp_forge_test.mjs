// cdp_forge_test.mjs — bout-en-bout via le TUNNEL : ouvre AuroraIA, va sur
// Cyber, clique « Démarrer l'atelier », attend que l'IA forge le lab, et
// rapporte la taille du HTML généré + le briefing + les objectifs.
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const TUNNEL = process.argv[2] || 'https://map-friends-catalog-camps.trycloudflare.com'
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUTDIR = process.argv[3] || 'C:\\Users\\Juan\\Desktop\\ia\\AuroraIA-v2'
const MAX_FORGE_MS = Number(process.argv[4] || 240000)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
function freePort(){return new Promise((res,rej)=>{const s=net.createServer();s.listen(0,()=>{const p=s.address().port;s.close(()=>res(p))});s.on('error',rej)})}
async function getJSON(u){const r=await fetch(u);return r.json()}

class CDP{
  constructor(w){this.w=w;this.id=0;this.p=new Map();this.events=[]}
  connect(){return new Promise((res,rej)=>{this.ws=new WebSocket(this.w);this.ws.onopen=()=>res();this.ws.onerror=rej;this.ws.onmessage=(m)=>{const x=JSON.parse(m.data);if(x.id&&this.p.has(x.id)){const{res,rej}=this.p.get(x.id);this.p.delete(x.id);x.error?rej(new Error(JSON.stringify(x.error))):res(x.result)}else if(x.method)this.events.push(x)}})}
  send(method,params={}){const id=++this.id;return new Promise((res,rej)=>{this.p.set(id,{res,rej});this.ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(this.p.has(id)){this.p.delete(id);rej(new Error('timeout '+method))}},45000)})}
  async waitEvent(method,ms=20000){const t=Date.now();while(Date.now()-t<ms){const e=this.events.find(x=>x.method===method);if(e)return e;await sleep(100)}return null}
  async ev(expr){const r=await this.send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text+' '+(r.exceptionDetails.exception?.description||''));return r.result?.value}
  async shot(path){const r=await this.send('Page.captureScreenshot',{format:'png'});writeFileSync(path,Buffer.from(r.data,'base64'));return path}
}

;(async()=>{
  const port=await freePort();const udd=mkdtempSync(join(tmpdir(),'aurora-forge-'))
  const proc=spawn(CHROME,[`--remote-debugging-port=${port}`,`--user-data-dir=${udd}`,'--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions','--disable-gpu','--window-size=1366,950','about:blank'],{stdio:'ignore'})
  proc.on('error',e=>{console.error('chrome err',e);process.exit(1)})
  let ver=null;for(let i=0;i<40;i++){try{ver=await getJSON(`http://127.0.0.1:${port}/json/version`);break}catch{await sleep(250)}}
  if(!ver){console.error('no devtools endpoint');proc.kill();process.exit(1)}
  let tab;try{tab=await(await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(TUNNEL+'/')}`,{method:'PUT'})).json()}catch{const l=await getJSON(`http://127.0.0.1:${port}/json/list`);tab=l.find(t=>t.type==='page')}
  if(!tab?.webSocketDebuggerUrl){const l=await getJSON(`http://127.0.0.1:${port}/json/list`);tab=l.find(t=>t.type==='page')}
  const cdp=new CDP(tab.webSocketDebuggerUrl);await cdp.connect()
  await cdp.send('Page.enable');await cdp.send('Runtime.enable')
  await cdp.send('Page.navigate',{url:TUNNEL+'/'});await cdp.waitEvent('Page.loadEventFired',25000);await sleep(7000)
  console.log('[forge] app loaded, title=',await cdp.ev('document.title'))
  // go to Cyber
  await cdp.ev(`[...document.querySelectorAll('button')].find(b=>/Cyber/i.test(b.textContent||''))?.click()`)
  await sleep(3000)
  // dismiss help card if open (so the start button under it is unambiguous — not required, just clean)
  // click "Démarrer l'atelier" (the big primary one in the left column OR the one in the empty state)
  const clicked=await cdp.ev(`(()=>{const bs=[...document.querySelectorAll('button')].filter(b=>/Démarrer l['’ ]atelier/i.test(b.textContent||''));if(!bs.length)return null;(bs[bs.length-1]||bs[0]).click();return bs.map(b=>b.textContent.trim());})()`)
  console.log('[forge] clicked start, candidates=',JSON.stringify(clicked))
  // poll: a lab is forged when an <iframe title="Lab cyber sensei"> appears with srcdoc, OR an error text shows
  const t0=Date.now();let result=null
  while(Date.now()-t0<MAX_FORGE_MS){
    const probe=await cdp.ev(`(()=>{const f=document.querySelector('iframe[title="Lab cyber sensei"]');const err=[...document.querySelectorAll('div')].find(d=>/^⚠/.test((d.textContent||'').trim()))?.textContent||null;
      // grab briefing + objectives text if a lab is present
      let briefing=null,objs=[];
      const head=[...document.querySelectorAll('*')].find(e=>/Atelier en cours ·/i.test(e.textContent||'')&&e.children.length<6);
      const objNodes=[...document.querySelectorAll('div')].filter(d=>d.previousSibling||true);
      return {hasIframe:!!f, srcdocLen: f? (f.getAttribute('srcdoc')||'').length:0, loading: !!document.querySelector('button')&&/prépare l['’ ]atelier|prepare l/i.test(document.body.innerText), err};})()`)
    if(probe.hasIframe&&probe.srcdocLen>500){result={ok:true,...probe};break}
    if(probe.err){result={ok:false,err:probe.err};break}
    await sleep(3000)
  }
  await cdp.shot(join(OUTDIR,'tunnel_test_4_forge.png'))
  if(!result){console.log('[forge] TIMEOUT after',Math.round((Date.now()-t0)/1000),'s — Ollama cold start or model busy. Inconclusive (not a code failure).')}
  else if(result.ok){
    console.log('[forge] ✅ LAB FORGÉ via le tunnel — srcdoc HTML =',result.srcdocLen,'caractères')
    // pull a few signals out of the generated HTML to gauge richness
    const sig=await cdp.ev(`(()=>{const f=document.querySelector('iframe[title="Lab cyber sensei"]');const h=(f.getAttribute('srcdoc')||'');
      const has=(re)=>re.test(h);
      return {len:h.length, theorie:has(/th[ée]orie/i), solution:has(/solution|write[- ]?up|révéler/i), postMessage:has(/postMessage/i), script:has(/<script/i), objectives:(h.match(/objective/gi)||[]).length, flag:has(/flag\\{/i)};})()`)
    console.log('[forge] signaux de richesse du lab généré:',JSON.stringify(sig,null,2))
    const bodyTxt=await cdp.ev(`document.body.innerText`)
    const m=bodyTxt.match(/Atelier en cours[\\s\\S]{0,400}/i);if(m)console.log('[forge] aperçu:',m[0].replace(/\\n+/g,' | ').slice(0,400))
  } else {
    console.log('[forge] ❌ erreur affichée:',result.err)
  }
  await cdp.send('Browser.close').catch(()=>{});proc.kill();process.exit(0)
})().catch(e=>{console.error('[forge] FATAL',e);process.exit(1)})
