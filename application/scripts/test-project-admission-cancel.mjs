import fs from 'node:fs'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import ts from 'typescript'
import { webcrypto } from 'node:crypto'
const source=fs.readFileSync(new URL('../src/utils/projectAdmission.ts',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace('export async function acquireProject','async function acquireProject')
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const calls=[]
let queued=true
const sandbox={crypto:webcrypto,console,getBridgeUrl:()=>'',setTimeout:cb=>setTimeout(cb,1),setInterval:()=>0,clearInterval:()=>{},bridgeFetch:async(path,options)=>{
 calls.push(path)
 let payload={}
 if(path.endsWith('/api/projects/admission'))payload={id:'test-ticket'}
 else if(path.endsWith('/cancel'))payload={status:'stopped'}
 else if(path.endsWith('/finish'))payload={status:'completed'}
 else payload=queued?{status:'queued',scheduling:{queue_position:1,ahead_count:1,blockers:[{id:'old-ticket',status:'interrupted',title:'Ancienne génération'}]}}:{status:'running',granted:true}
 return new Response(JSON.stringify(payload),{headers:{'Content-Type':'application/json'}})
}}
vm.runInNewContext(code,sandbox)
const controller=new AbortController()
const lines=[]
const waiting=sandbox.acquireProject({request_id:'one-request',module:'3d',title:'Test'},line=>{lines.push(line);controller.abort(new DOMException('Cancelled','AbortError'))},controller.signal)
await assert.rejects(waiting,e=>e.name==='AbortError')
assert(lines.some(line=>line.includes('old-ticket')&&line.includes('interrompue')))
assert.equal(calls.filter(path=>path.endsWith('/cancel')).length,1)
assert.equal(calls.filter(path=>path.endsWith('/api/projects/admission')).length,1)
queued=false
const active=new AbortController()
const finish=await sandbox.acquireProject({request_id:'next-request',module:'3d',title:'Test'},()=>{},active.signal)
active.abort(new DOMException('Cancelled','AbortError'))
await finish('failed')
assert.equal(calls.filter(path=>path.endsWith('/finish')).length,1,'release must still work after abort')
console.log('Admission: explicit stale blocker, queued cancellation without replay, release after abort passed')
