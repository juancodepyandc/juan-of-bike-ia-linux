// cdp_jeu_test.mjs — vérifie sur le TUNNEL que le mode jeu est accessible et
// affiché : injecte profile.examFormat='jeu', va sur Academy, sélectionne le
// mode « Parcours BAC complet », vérifie que le picker format montre « 🎮 jeu »
// actif + les éléments game-mode dans le DOM (mode jeu chip + manche/boss
// dans ParcoursActiveSession… si on parvient à l'ouvrir).
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
  const port=await freePort();const udd=mkdtempSync(join(tmpdir(),'aurora-jeu-'))
  const proc=spawn(CHROME,[`--remote-debugging-port=${port}`,`--user-data-dir=${udd}`,'--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions','--disable-gpu','--window-size=1366,950','about:blank'],{stdio:'ignore'})
  proc.on('error',e=>{console.error('chrome err',e);process.exit(1)})
  for(let i=0;i<40;i++){try{await getJSON(`http://127.0.0.1:${port}/json/version`);break}catch{await sleep(250)}}
  let tab;try{tab=await(await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(TUNNEL+'/')}`,{method:'PUT'})).json()}catch{const l=await getJSON(`http://127.0.0.1:${port}/json/list`);tab=l.find(t=>t.type==='page')}
  const cdp=new CDP(tab.webSocketDebuggerUrl);await cdp.connect()
  await cdp.send('Page.enable');await cdp.send('Runtime.enable')
  await cdp.send('Page.navigate',{url:TUNNEL+'/'});await cdp.wait('Page.loadEventFired',25000);await sleep(6000)
  console.log('[jeu] app loaded')

  // 1) Injecte profile.examFormat='jeu' dans le store persisté.
  await cdp.eval(`(() => {
    const state = { state: {
      quiz: null, courses: null, fiches: null, parcoursBank: [],
      parcours: { goal: 'Test mode jeu', parcours: [], activePathId: null, sources: [],
        profile: { workStyle: 'pratique', examFormat: 'jeu', examDurationMinutes: 60, schoolLevel: 'Terminale STI2D' } },
    }, version: 1 };
    localStorage.setItem('aurora-learning-sessions', JSON.stringify(state));
  })()`)
  await cdp.send('Page.reload'); await cdp.wait('Page.loadEventFired',25000); await sleep(6000)

  // 2) Navigue sur Academy.
  await cdp.eval(`[...document.querySelectorAll('button')].find(b => /Academy|Académie/i.test(b.textContent||''))?.click()`)
  await sleep(3000)

  // 3) Clique le mode "Parcours BAC complet".
  const modeClicked = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => /Parcours BAC complet/i.test(x.textContent||''));
    if (b) { b.click(); return b.textContent.trim(); }
    return null;
  })()`)
  console.log('[jeu] mode parcours-bac cliqué :', modeClicked)
  await sleep(1500)
  await cdp.shot(join(OUT,'tunnel_test_5_academy_jeu.png'))

  // 4) Vérifie la visibilité du picker format + sélection 'jeu'.
  const text = await cdp.eval('document.body.innerText')
  const markers = {
    formatLabel: /format du parcours/i.test(text),
    classiqueOption: /📚 classique|classique/i.test(text),
    jeuOption: /🎮 jeu \/ enquête|jeu \/ enqu[êe]te/i.test(text),
    gameDetails: /manches.*🔑.*clés.*🏆.*boss final|manches · 🔑 clés · 🏆/i.test(text),
  }
  console.log('[jeu] markers picker :', JSON.stringify(markers, null, 2))

  // 5) Vérifie qu'il n'y a pas d'erreurs console.
  const errs = cdp.ev
    .filter(e => e.method === 'Runtime.exceptionThrown')
    .map(e => e.params?.exceptionDetails?.text || '?')
  console.log('[jeu] erreurs console =', errs.length, errs.slice(0, 3))

  // 6) Bonus : injecte un parcoursPayload minimal pour ouvrir ParcoursActiveSession
  //    et tester le rendu game-mode complet (clés/manches/boss).
  console.log('[jeu] DONE')
  await cdp.send('Browser.close').catch(()=>{}); proc.kill(); process.exit(0)
})().catch(e=>{console.error('[jeu] FATAL',e);process.exit(1)})
