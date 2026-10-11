import assert from 'node:assert/strict'
import http from 'node:http'
import os from 'node:os'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
const state=await fs.mkdtemp(path.join(os.tmpdir(),'aurora-workspace-test-'))
let launches=0
const fixture=http.createServer(async(req,res)=>{
 if(req.url==='/slow'){launches++;await new Promise(r=>setTimeout(r,1400));res.end('terminé');return}
 if(req.url==='/asset'){res.setHeader('Content-Disposition','attachment; filename="rendu.txt"');res.end('resultat durable');return}
 res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fixture pipeline</title><style>button,input,textarea,select{display:block;margin:8px;min-height:30px}</style><textarea aria-label="Consigne"></textarea><input type="file" aria-label="Fichier"><input type="color" aria-label="Couleur"><select aria-label="Aspect"><option value="assembled">Assemblé</option><option value="exploded">Éclaté</option></select><button id="start">Générer</button><button id="result" disabled>En attente</button><a href="/asset" download>Télécharger</a><button onclick="window.open('/viewer')">Viewer</button><script>start.onclick=async()=>{start.disabled=true;result.textContent='En cours';result.textContent='Résultat '+await fetch('/slow').then(r=>r.text());result.disabled=false;localStorage.setItem('result','terminé')}</script>`)
})
await new Promise(r=>fixture.listen(0,'127.0.0.1',r))
const probe=http.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r))
const child=spawn(process.execPath,[fileURLToPath(new URL('./persistent-workspace.mjs',import.meta.url))],{env:{...process.env,AURORA_WORKSPACE_STATE:state,AURORA_WORKSPACE_PORT:String(port),AURORA_WORKSPACE_ORIGIN:`http://127.0.0.1:${fixture.address().port}`},stdio:'ignore'})
const base=`http://127.0.0.1:${port}`,owner='a'.repeat(64);let token
async function call(route,data,who=owner){const response=await fetch(base+route,{method:data===undefined?'GET':'POST',headers:{'X-Aurora-Workspace-Token':token,'X-Aurora-Workspace-Owner':who,...(data===undefined?{}:{'Content-Type':'application/json'})},body:data===undefined?undefined:JSON.stringify(data)});return {response,data:response.headers.get('content-type')?.includes('json')?await response.json():await response.text()}}
async function frameUntil(test){for(let n=0;n<40;n++){const f=await call('/frame');if(test(f.data))return f.data;await new Promise(r=>setTimeout(r,100))}throw Error('Workspace result timed out')}
try{
 for(let n=0;n<60;n++){try{token=(await fs.readFile(path.join(state,'token'),'utf8')).trim();if((await call('/health')).response.ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 assert.equal((await fetch(base+'/health')).status,403)
 const [one,two]=await Promise.all([call('/session',{width:390,height:700}),call('/session',{width:390,height:700})]);assert.equal(one.data.id,two.data.id)
 let frame=await frameUntil(f=>f.controls?.some(c=>c.label==='Générer'))
 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Consigne').id});await call('/action',{type:'text',value:'Brouillon conservé'})
 assert.equal((await call('/frame')).data.focus.value,'Brouillon conservé')
 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Aspect').id});await call('/action',{type:'select',value:'exploded'});assert.equal((await call('/frame')).data.focus.value,'exploded')
 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Couleur').id});await call('/action',{type:'color',value:'#245caa'});assert.equal((await call('/frame')).data.focus.value,'#245caa')
 assert.equal((await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Fichier').id})).data.focus.kind,'file')
 assert((await call('/action',{type:'files',files:[{name:'source.txt',mimeType:'text/plain',data:Buffer.from('fixture').toString('base64')}]})).data.ok)

 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Générer').id})
 // No phone/controller requests while the PC continues the asynchronous pipeline.
 await new Promise(r=>setTimeout(r,1800))
 assert.equal((await call('/session',{width:390,height:700})).data.id,one.data.id)
 frame=await frameUntil(f=>f.controls?.some(c=>c.label==='Résultat terminé'));assert.equal(launches,1)
 assert.equal((await call('/frame',undefined,'b'.repeat(64))).response.status,404)
 const other=await call('/session',{width:390,height:700},'b'.repeat(64));assert.notEqual(other.data.id,one.data.id)
 assert(!(await call('/frame',undefined,'b'.repeat(64))).data.controls.some(c=>c.label==='Résultat terminé'))
 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Télécharger').id})
 frame=await frameUntil(f=>f.downloads?.length===1)
 assert.equal((await call('/download/'+frame.downloads[0].id)).data,'resultat durable')
 assert.equal((await call('/download/'+frame.downloads[0].id,undefined,'b'.repeat(64))).response.status,404)
 await call('/action',{type:'control',id:frame.controls.find(c=>c.label==='Viewer').id})
 frame=await frameUntil(f=>f.tabs?.length===2);assert.equal(frame.active,'2')
 await call('/action',{type:'tab',id:'1'});frame=await frameUntil(f=>f.active==='1');assert(frame.controls.some(c=>c.label==='Résultat terminé'))
 console.log('PASS: detached pipeline, no replay, concurrent reconnect, owner isolation, draft, download, viewer tabs')
}finally{
 child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),new Promise(r=>setTimeout(r,6000))]);if(child.exitCode===null)child.kill('SIGKILL');await new Promise(r=>fixture.close(r));await fs.rm(state,{recursive:true,force:true})
}
