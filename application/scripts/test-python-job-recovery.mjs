import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
import ts from 'typescript'
const source=fs.readFileSync(new URL('../src/hooks/useTauri.ts',import.meta.url),'utf8')
const parsed=ts.createSourceFile('useTauri.ts',source,ts.ScriptTarget.Latest,true)
const fn=parsed.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='peekResumableJob')
const code=ts.transpileModule(fn.getText(parsed).replace(/^export /,''),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
let handle='retained-job',response=new Response('{"status":"running"}',{headers:{'Content-Type':'application/json'}})
const sandbox={getBridgeUrl:()=>'',isTauriRuntime:()=>true,recallJobId:()=>handle,forgetJobId:()=>{handle=null},fetch:async()=>response}
vm.runInNewContext(code,sandbox)
assert.equal((await sandbox.peekResumableJob('model_ia')).status,'running','native async jobs must also reconnect')
response=new Response('{"error":"unauthorized"}',{status:401,headers:{'Content-Type':'application/json'}})
assert.equal(await sandbox.peekResumableJob('model_ia'),null);assert.equal(handle,'retained-job')
response=new Response('<html>proxy</html>',{headers:{'Content-Type':'text/html'}})
assert.equal(await sandbox.peekResumableJob('model_ia'),null);assert.equal(handle,'retained-job')
response=new Response('{}',{status:404})
assert.equal(await sandbox.peekResumableJob('model_ia'),null);assert.equal(handle,null)
console.log('Native/browser job recovery: a missing job clears its handle; authentication or HTML proxy failures preserve it')
