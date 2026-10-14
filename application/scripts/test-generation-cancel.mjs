import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { webcrypto } from 'node:crypto'
const source=fs.readFileSync(new URL('../src/hooks/useTauri.ts',import.meta.url),'utf8')
const parsed=ts.createSourceFile('useTauri.ts',source,ts.ScriptTarget.Latest,true)
const declaration=parsed.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='runPythonScript')
const code=ts.transpileModule(declaration.getText(parsed).replace(/^export /,''),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
let spawns=0,cancellations=0,releaseSpawn
const state=new Map()
const sandbox={crypto:webcrypto,TextEncoder,AbortSignal,DOMException,console,isTauriRuntime:()=>false,isCloudRuntime:()=>true,getBridgeUrl:()=>'',recallJobId:k=>state.get(k),rememberJobId:(k,v)=>state.set(k,v),forgetJobId:k=>state.delete(k),setTimeout:(cb)=>setTimeout(cb,1),fetch:async url=>{
 if(url.endsWith('/run-async')){spawns++;await new Promise(resolve=>{releaseSpawn=resolve});return new Response(JSON.stringify({jobId:'controlled-operation'}),{headers:{'Content-Type':'application/json'}})}
 if(url.includes('/cancel/')){cancellations++;return new Response('{}')}
 throw Error('Unexpected request after cancellation: '+url)
}}
vm.runInNewContext(code,sandbox)
const first=new AbortController();first.abort(new DOMException('Cancelled','AbortError'))
await assert.rejects(sandbox.runPythonScript('fixture.py',[],{signal:first.signal}),e=>e.name==='AbortError')
assert.equal(spawns,0)
const second=new AbortController()
const pending=sandbox.runPythonScript('fixture.py',[],{signal:second.signal,resumeKey:'model_ia'})
while(!releaseSpawn)await new Promise(r=>setTimeout(r,1));second.abort(new DOMException('Cancelled','AbortError'));releaseSpawn()
await assert.rejects(pending,e=>e.name==='AbortError')
assert.equal(spawns,1);assert.equal(cancellations,1)
console.log('Actual Python client: cancellation before start and during spawn sends one stop, without replay')
// A completed job from another command must never supply this command's result.
state.set('model_ia','old-operation');releaseSpawn=undefined
const oldFetch=sandbox.fetch
sandbox.fetch=async url=>url.endsWith('/job/old-operation')?new Response(JSON.stringify({status:'done',output:'old unrelated mesh',exitCode:0,requestFingerprint:'different-request'}),{headers:{'Content-Type':'application/json'}}):oldFetch(url)
const third=new AbortController()
const fresh=sandbox.runPythonScript('fixture.py',['--prompt','new subject'],{signal:third.signal,resumeKey:'model_ia'})
while(!releaseSpawn)await new Promise(r=>setTimeout(r,1))
assert.equal(spawns,2,'different completed request starts fresh instead of returning its mesh')
third.abort(new DOMException('Cancelled','AbortError'));releaseSpawn()
await assert.rejects(fresh,e=>e.name==='AbortError')
console.log('Different completed command cannot supply an unrelated cached subject')
