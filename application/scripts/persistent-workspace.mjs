/** PC-owned browser sessions: the phone is a controller, never the pipeline host. */
import http from 'node:http'
import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { chromium, devices } from 'playwright'

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const stateRoot = process.env.AURORA_WORKSPACE_STATE || path.join(appRoot, '.aurora', 'persistent-workspace')
await fs.mkdir(stateRoot, { recursive:true, mode:0o700 })
const tokenFile = path.join(stateRoot, 'token')
try { await fs.writeFile(tokenFile, crypto.randomBytes(32).toString('hex'), { flag:'wx', mode:0o600 }) } catch (error) { if(error.code !== 'EEXIST') throw error }
const token = (await fs.readFile(tokenFile, 'utf8')).trim()
const sessions = new Map()
let browser
let starting
const frameIds=new WeakMap();let nextFrame=0
function frameId(frame){if(!frameIds.has(frame))frameIds.set(frame,String(++nextFrame));return frameIds.get(frame)}
const origin = process.env.AURORA_WORKSPACE_ORIGIN || 'http://127.0.0.1:3001'
const viewport = input => ({ width:Math.max(320,Math.min(1600,Math.round(Number(input?.width)||390))), height:Math.max(320,Math.min(1600,Math.round(Number(input?.height)||780))) })
function validOwner(value) { return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) }
async function session(owner, size) {
  if (sessions.has(owner)) return sessions.get(owner)
  if(sessions.size >= 3) throw Object.assign(new Error('Trois espaces sont déjà ouverts sur le PC.'), { status:429 })
  // Reserve before awaiting: simultaneous reconnects cannot create duplicate sessions.
  const pending = createSession(owner,size)
  sessions.set(owner,pending)
  try { const s=await pending; sessions.set(owner,s); return s } catch(error) { sessions.delete(owner); throw error }
}
async function createSession(owner,size) {
  if(!browser?.isConnected()) {
    starting ||= chromium.launch({ headless:true }).finally(()=>{starting=null})
    browser=await starting
  }
  const directory=path.join(stateRoot,owner)
  await fs.mkdir(directory,{recursive:true,mode:0o700})
  let saved
  try { saved=JSON.parse(await fs.readFile(path.join(directory,'storage.json'),'utf8')) } catch {}
  const context=await browser.newContext({ ...devices['Pixel 7'], viewport:viewport(size), deviceScaleFactor:2, storageState:saved, acceptDownloads:true })
  const s={id:crypto.randomUUID(),context,active:null,pages:new Map(),downloads:[],directory,chooser:null,chain:Promise.resolve(),createdAt:new Date().toISOString()}
  let nextTab=0
  context.on('page',page=>{
    const id=String(++nextTab);s.pages.set(id,page);s.active=id
    page.on('filechooser',chooser=>{s.chooser=chooser})
    page.on('download',async download=>{
      const id=crypto.randomUUID();const name=path.basename(download.suggestedFilename()).replace(/[\x00-\x1f]/g,'').slice(0,180)||'resultat'
      try { await download.saveAs(path.join(directory,id));s.downloads.push({id,name});s.downloads=s.downloads.slice(-100) } catch {}
    })
    page.on('close',()=>{s.pages.delete(id);if(s.active===id)s.active=[...s.pages.keys()].at(-1)||null})
    // External windows get no service token and no caller credentials.
  })
  const page=await context.newPage()
  await page.goto(origin+'/?persistent-worker=1',{waitUntil:'domcontentloaded',timeout:30_000})
  return s
}
function active(s) { const page=s.pages.get(s.active);if(!page||page.isClosed())throw Object.assign(new Error('Onglet fermé. Reconnectez l’espace.'),{status:409});return page }
async function focusState(s) {
  if(s.chooser)return {kind:'file',multiple:s.chooser.isMultiple()}
  let frame=active(s).mainFrame()
  while(await frame.evaluate(()=>document.activeElement?.tagName==='IFRAME').catch(()=>false)){const handle=await frame.locator(':focus').elementHandle();const child=await handle.contentFrame();if(!child)break;frame=child}
  s.focusFrame=frame
  return frame.evaluate(()=>{
    const el=document.activeElement
    if(el instanceof HTMLInputElement&&el.type==='color')return {kind:'color',value:el.value}
    if(el instanceof HTMLSelectElement)return {kind:'select',value:el.value,options:[...el.options].map(o=>({value:o.value,label:o.label,disabled:o.disabled}))}
    if((el instanceof HTMLInputElement && !['button','submit','file','checkbox','radio','range','color'].includes(el.type))||el instanceof HTMLTextAreaElement)
      return {kind:'text',value:el.value,type:el instanceof HTMLInputElement?el.type:'text',label:el.getAttribute('aria-label')||el.getAttribute('placeholder')||'Votre texte'}
    return null
  })
}
async function controlsInFrame(frame) {
  return frame.evaluate(()=>{
    window.__auroraControlId ||= 0
    return [...document.querySelectorAll('button,a[href],input,textarea,select,summary,[role="button"],[role="tab"]')].flatMap(el=>{
      const r=el.getBoundingClientRect(), style=getComputedStyle(el)
      if(!r.width||!r.height||r.bottom<0||r.right<0||r.top>innerHeight||r.left>innerWidth||style.visibility==='hidden'||style.display==='none')return []
      const x=Math.max(0,Math.min(innerWidth-1,r.x+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2))
      const top=document.elementFromPoint(x,y)
      if(!top||!(el.contains(top)||top===el))return []
      el.dataset.auroraWorkspaceControl ||= String(++window.__auroraControlId)
      const label=el.getAttribute('aria-label')||el.getAttribute('title')||el.getAttribute('placeholder')||el.innerText||el.labels?.[0]?.innerText||'Commande Aurora'
      return [{id:el.dataset.auroraWorkspaceControl,label:label.trim().slice(0,160),x:r.x,y:r.y,width:r.width,height:r.height,disabled:!!el.disabled,drag:el instanceof HTMLInputElement&&el.type==='range'}]
    }).slice(0,200)
  })
}
async function geometry(page) {
  const items=[],canvases=[]
  for(const frame of page.frames()) {
    try {
      const box=frame===page.mainFrame()?{x:0,y:0}:await (await frame.frameElement()).boundingBox()
      if(!box)continue
      const id=frameId(frame)
      for(const c of await controlsInFrame(frame))items.push({...c,frame:id,x:c.x+box.x,y:c.y+box.y})
      const drags=await frame.locator('canvas,input[type=range]').evaluateAll(els=>els.filter(el=>!el.closest('[aria-hidden=true]')&&getComputedStyle(el).pointerEvents!=='none').map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}))
      for(const c of drags)if(c.width&&c.height)canvases.push({...c,x:c.x+box.x,y:c.y+box.y})
    }catch{}
  }
  return {controls:items,canvases}
}
async function assets(page) {
  return page.evaluate(()=>{
    const result=new Map()
    for(const el of document.querySelectorAll('a[href],iframe[src],img[src],video[src],audio[src]')) {
      try {const url=new URL(el.href||el.src,location.origin)
        if(url.origin===location.origin && url.pathname.startsWith('/api/asset/') && /\.(html|png|jpe?g|webp|svg|mp4|wav|mp3)$/i.test(url.pathname)) {
          const href=url.pathname+url.search
          result.set(href,{href,label:(el.innerText||el.title||el.alt||'Ouvrir le rendu').trim().slice(0,100)})
        }
      }catch{}
    }
    return [...result.values()].slice(-24)
  })
}
async function snapshot(s) {
  const page=active(s)
  const jpeg=await page.screenshot({type:'jpeg',quality:85,timeout:10_000})
  return {id:s.id,createdAt:s.createdAt,image:jpeg.toString('base64'),viewport:page.viewportSize(),...await geometry(page),assets:await assets(page),active:s.active,tabs:await Promise.all([...s.pages].map(async([id,p])=>({id,title:await p.title().catch(()=> 'Aurora')}))),downloads:s.downloads,focus:await focusState(s)}
}
async function action(s,data) {
  const page=active(s)
  const point=()=>({x:Math.max(0,Math.min(page.viewportSize().width,Number(data.x)||0)),y:Math.max(0,Math.min(page.viewportSize().height,Number(data.y)||0))})
  switch(data.type) {
    case 'control': {
      if(!/^\d{1,9}$/.test(String(data.id)))throw Object.assign(new Error('Commande invalide.'),{status:400})
      const frame= data.frame ? page.frames().find(f=>frameId(f)===String(data.frame)) : page.mainFrame()
      if(!frame)throw Object.assign(new Error('Vue changée. Réessayez la commande.'),{status:409})
      const el=frame.locator(`[data-aurora-workspace-control="${data.id}"]`)
      const tag=await el.evaluate(e=>e.tagName.toLowerCase())
      if(['textarea','select'].includes(tag)||tag==='input'&&await el.evaluate(e=>!['file','checkbox','radio','range','button','submit'].includes(e.type)))await el.focus()
      else if(tag==='input'&&await el.evaluate(e=>e.type==='file')){const [chosen]=await Promise.all([page.waitForEvent('filechooser',{timeout:5000}),el.click({timeout:5000})]);s.chooser=chosen}
      else await el.click({timeout:5000})
      break
    }
    case 'tap': { const p=point();await page.touchscreen.tap(p.x,p.y);break }
    case 'wheel': await page.mouse.move(point().x,point().y);await page.mouse.wheel(Math.max(-1000,Math.min(1000,Number(data.dx)||0)),Math.max(-1000,Math.min(1000,Number(data.dy)||0)));break
    case 'pointer': {
      const p=point();await page.mouse.move(p.x,p.y)
      if(data.phase==='down')await page.mouse.down()
      if(data.phase==='up')await page.mouse.up()
      break
    }
    case 'text': {
      if(typeof data.value!=='string'||data.value.length>200_000)throw Object.assign(new Error('Texte trop volumineux.'),{status:400})
      await (s.focusFrame||page.mainFrame()).locator(':focus').fill(data.value);break
    }
    case 'color': {
      if(!/^#[0-9a-f]{6}$/i.test(String(data.value)))throw Object.assign(new Error('Couleur invalide.'),{status:400})
      await (s.focusFrame||page.mainFrame()).locator(':focus').evaluate((el,value)=>{
        if(!(el instanceof HTMLInputElement)||el.type!=='color')throw Error('No active color field')
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,value)
        el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))
      },data.value);break
    }
    case 'select': await (s.focusFrame||page.mainFrame()).locator(':focus').selectOption(String(data.value));break
    case 'key': {
      if(!['Enter','Escape','Tab','Backspace','Control+Enter','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(data.key))throw Object.assign(new Error('Touche refusée.'),{status:400})
      await page.keyboard.press(data.key);break
    }
    case 'resize': await page.setViewportSize(viewport(data));break
    case 'tab': if(!s.pages.has(String(data.id)))throw Object.assign(new Error('Onglet introuvable.'),{status:404});s.active=String(data.id);break
    case 'back': await page.goBack({waitUntil:'domcontentloaded',timeout:15_000});break
    case 'files': {
      if(!s.chooser||!Array.isArray(data.files)||data.files.length>20)throw Object.assign(new Error('Choisir un champ fichier dans Aurora.'),{status:400})
      await s.chooser.setFiles(data.files.map(f=>({name:path.basename(String(f.name)),mimeType:String(f.mimeType||'application/octet-stream'),buffer:Buffer.from(f.data,'base64')})))
      s.chooser=null;break
    }
    case 'cancel-file':s.chooser=null;break
    default:throw Object.assign(new Error('Action inconnue.'),{status:400})
  }
  if(['control','tap'].includes(data.type))await page.waitForTimeout(60)
  return {ok:true,focus:await focusState(s)}
}
async function body(request) {
  let length=0;const chunks=[]
  for await (const chunk of request) { length+=chunk.length;if(length>170*1024*1024)throw Object.assign(new Error('Fichiers trop volumineux.'),{status:413});chunks.push(chunk) }
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}
}
const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store')
  const supplied=Buffer.from(req.headers['x-aurora-workspace-token']||'');const expected=Buffer.from(token)
  if(supplied.length!==expected.length||!crypto.timingSafeEqual(supplied,expected)){res.writeHead(403);res.end();return}
  try {
    const url=new URL(req.url,'http://localhost')
    if(url.pathname==='/health'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,service:'aurora-persistent-workspace',sessions:sessions.size}));return}
    const owner=req.headers['x-aurora-workspace-owner']
    if(!validOwner(owner))throw Object.assign(new Error('Session non authentifiée.'),{status:403})
    const data=req.method==='POST'?await body(req):{}
    if(url.pathname==='/session'&&req.method==='POST'){const s=await session(owner,data);res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,id:s.id,createdAt:s.createdAt}));return}
    const pending=sessions.get(owner)
    if(!pending)throw Object.assign(new Error('Reconnectez l’espace persistant.'),{status:404})
    const s=await pending
    if(url.pathname.startsWith('/download/')) {
      const id=url.pathname.slice('/download/'.length);const file=s.downloads.find(f=>f.id===id)
      if(!file)throw Object.assign(new Error('Fichier introuvable.'),{status:404})
      const bytes=await fs.readFile(path.join(s.directory,id));res.setHeader('Content-Type','application/octet-stream');res.setHeader('Content-Disposition',`attachment; filename="${file.name.replace(/["\\]/g,'_')}"`);res.end(bytes);return
    }
    // Serialize per session. Polls and input cannot race with a popup or field focus.
    const run=async()=>{
      if(url.pathname==='/frame'&&req.method==='GET')return snapshot(s)
      if(url.pathname==='/action'&&req.method==='POST')return action(s,data)
      throw Object.assign(new Error('Route inconnue.'),{status:404})
    }
    const result=s.chain.then(run,run);s.chain=result.catch(()=>{})
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify(await result))
  } catch(error) { res.writeHead(error.status||503,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:false,error:error.status?error.message:'Espace momentanément indisponible. Reconnectez-vous sans relancer la génération.'})) }
})
// Durable histories on PC; losing the phone does not close any browser page.
const saveTimer=setInterval(()=>{for(const pending of sessions.values())void Promise.resolve(pending).then(s=>s.context.storageState({path:path.join(s.directory,'storage.json'),indexedDB:true})).catch(()=>{})},30_000)
saveTimer.unref()
server.listen(Number(process.env.AURORA_WORKSPACE_PORT||3034),'127.0.0.1',()=>console.log('Aurora persistent workspace ready (loopback only)'))
async function shutdown() {
  server.close()
  clearInterval(saveTimer)
  const force=setTimeout(()=>process.exit(0),5000);force.unref()
  await Promise.allSettled([...sessions.values()].map(async pending=>{const s=await pending;await s.context.storageState({path:path.join(s.directory,'storage.json'),indexedDB:true});await s.context.close()}))
  await browser?.close().catch(()=>{})
  process.exit(0)
}
process.on('SIGTERM',()=>{void shutdown()})
process.on('SIGINT',()=>{void shutdown()})
